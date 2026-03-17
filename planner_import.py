"""
planner_import.py — Importación masiva de CSV a Microsoft Planner via Graph API.

Diseñado para migración futura como tools del MCP fornado-planner-mcp:
  create_plan, create_bucket, create_task (ampliado), patch_task_details → graph/client.py
  run_import → task_tools.py
  @mcp.tool() wrappers → server.py

Uso:
  python planner_import.py [--dry-run]
  python planner_import.py --csv <ruta> --group-id <guid>
  python planner_import.py --mode tasks --csv <ruta>
  python planner_import.py --mode buckets --csv <ruta>
  python planner_import.py --mode plan --csv <ruta> --group-id <guid>
  python planner_import.py --mode list [--filter <texto>]
  python planner_import.py --mode delete [--filter <texto>] [--dry-run]
  python planner_import.py --mode sp-list [--site-url <url>] [--folder <ruta>] [--filter <texto>]
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import os
import re
import sys
import uuid
import webbrowser
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx
from dotenv import load_dotenv

# ── Auth reutilizada del MCP ──────────────────────────────────────────────────
# Ruta por defecto: %USERPROFILE%\mcp-servers\fornado-planner-mcp (override con env MCP_PATH)
MCP_PATH = Path(os.environ.get("MCP_PATH", Path.home() / "mcp-servers" / "fornado-planner-mcp"))
if not MCP_PATH.is_dir():
    sys.exit(
        f"[ERROR] No se encontró el MCP fornado-planner-mcp en:\n  {MCP_PATH}\n"
        "  Instálalo ahí o define la variable de entorno MCP_PATH con la ruta correcta.\n"
        "  Ver MANUAL.md § 6 (Errores comunes)."
    )
sys.path.insert(0, str(MCP_PATH))
load_dotenv(MCP_PATH / ".env")

from src.auth.microsoft import MicrosoftAuthManager  # noqa: E402
from src.config import Settings  # noqa: E402

# ── Constantes ────────────────────────────────────────────────────────────────
GROUP_ID = "198b4a0a-39c7-4521-a546-6a008e3a254a"
# ASSIGNEE_GUID anterior (ahora resuelto dinámicamente desde AssignedToEmail del CSV):
# ASSIGNEE_GUID = "eed15e14-17d2-46fb-ac5f-d415b6e9db1f"
CSV_PATH = Path(r"C:\Users\dmorales\OneDrive - Cosemar\PM\Definicion plan control y gestión de proyectos\Docs\Borradores_proyectos_tareas\Planner_Imp_PROJ1.csv")
GRAPH_BASE = "https://graph.microsoft.com/v1.0"
SHAREPOINT_SITE_URL = "https://cosemar.sharepoint.com/sites/Gestioncontrolproyectos"

CHECKLIST_TITLE_MAX = 100  # límite Planner — ítems más largos causan 400

PRIORITY_MAP: dict[str, int] = {
    "urgent": 1,
    "important": 2,
    "medium": 3,
    "low": 5,
    "none": 9,
}

# Orden operativo de buckets en reportes
BUCKET_ORDER: dict[str, int] = {
    "backlog": 0,
    "en curso": 1,
    "gateway": 2,
    "completado": 3,
    "completados": 3,
}

# Se construye en runtime por configure_plan_labels(): {"TI": "category1", ...}
LABEL_MAP: dict[str, str] = {}

# Cache de resolución GUID → email (para modo email-report)
_GUID_TO_EMAIL_CACHE: dict[str, str | None] = {}

# Cache de resolución GUID → displayName (para reportes HTML)
_GUID_TO_NAME_CACHE: dict[str, str | None] = {}


# ── Transformaciones ──────────────────────────────────────────────────────────

def _default_date() -> str:
    """Fecha de fallback: hoy + 7 días en ISO 8601 UTC."""
    return (date.today() + timedelta(days=7)).strftime("%Y-%m-%dT00:00:00Z")


def parse_date(ddmmyyyy: str) -> tuple[str | None, str | None]:
    """Parsea DDMMYYYY a ISO 8601 UTC.

    Returns:
        (iso_string, None)      → fecha válida
        (None, None)            → vacío / '00000000' (sin fecha)
        (fallback_iso, warning) → formato incorrecto; fallback = hoy+7
    """
    raw = ddmmyyyy.strip()
    # Normalizar DD-MM-YYYY → DDMMYYYY (el linter usa guiones)
    if len(raw) == 10 and raw[2] == "-" and raw[5] == "-":
        raw = raw[:2] + raw[3:5] + raw[6:]
    if not raw or raw.strip("0") == "":
        return None, None
    if len(raw) != 8 or not raw.isdigit():
        return _default_date(), f"'{ddmmyyyy.strip()}' no es DDMMYYYY — se usará hoy+7"
    try:
        datetime.strptime(raw, "%d%m%Y")
    except ValueError:
        return _default_date(), f"'{ddmmyyyy.strip()}' es una fecha inválida — se usará hoy+7"
    d, m, y = raw[:2], raw[2:4], raw[4:]
    return f"{y}-{m}-{d}T00:00:00Z", None


def map_priority(label: str) -> int:
    return PRIORITY_MAP.get(label.lower(), 5)


def build_checklist(items_str: str) -> tuple[dict[str, Any], list[str]]:
    """'item1;item2;item3' → ({uuid: {title, isChecked, orderHint}, ...}, warnings)

    Ítems que superan CHECKLIST_TITLE_MAX se truncan; se incluye una advertencia
    por cada uno para que el caller la notifique antes de llamar a Graph.
    """
    result: dict[str, Any] = {}
    warnings: list[str] = []
    for item in items_str.split(";"):
        item = item.strip()
        if not item:
            continue
        if len(item) > CHECKLIST_TITLE_MAX:
            warnings.append(
                f"  ⚠ Ítem de checklist truncado ({len(item)} chars): '{item[:40]}…'"
            )
            item = item[:CHECKLIST_TITLE_MAX]
        result[str(uuid.uuid4())] = {
            "@odata.type": "#microsoft.graph.plannerChecklistItem",
            "title": item,
            "isChecked": False,
            "orderHint": " !",
        }
    return result, warnings


def parse_labels(labels_str: str) -> dict[str, bool]:
    """'TI;PM' → {'category1': True, 'category2': True} según LABEL_MAP"""
    applied: dict[str, bool] = {}
    for label in labels_str.split(";"):
        label = label.strip()
        if label and label in LABEL_MAP:
            applied[LABEL_MAP[label]] = True
    return applied


def _derive_task_status(percent_complete: int) -> str:
    """Convierte percentComplete a estado legible.
    0 → 'notStarted'
    1-99 → 'inProgress'
    100 → 'completed'
    """
    if percent_complete == 0:
        return "notStarted"
    elif percent_complete == 100:
        return "completed"
    else:
        return "inProgress"


def _parse_due(task: dict[str, Any]) -> date | None:
    """Extrae dueDateTime de una tarea como objeto date, o None si no tiene."""
    raw = task.get("dueDateTime") or ""
    if not raw or raw == "-":
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def _format_datetime(dt_str: str) -> str:
    """Convierte ISO 8601 a 'dd-mm-yyyy hh:mm' en hora local del sistema. Retorna '-' si falla."""
    if not dt_str:
        return "-"
    try:
        dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        return dt.astimezone().strftime("%d-%m-%Y %H:%M")
    except ValueError:
        return "-"


def _status_badge(percent: int) -> str:
    """Genera pill badge HTML coloreado según estado (Completada / En Progreso / Sin Iniciar). Fix 4.4: colores vibrantes."""
    if percent == 100:
        status_text = "Completada"
        color = "white"
        bg_color = "#107c10"  # verde más vibrante, texto blanco
    elif percent > 0:
        status_text = "En Progreso"
        color = "#333"
        bg_color = "#e07800"  # naranja más vivo
    else:
        status_text = "Sin Iniciar"
        color = "white"
        bg_color = "#605e5c"  # gris más oscuro
    return f'<span style="background-color:{bg_color}; color:{color}; padding:4px 8px; border-radius:4px; font-weight:bold;">{status_text}</span>'


def _progress_bar(percent: int) -> str:
    """Genera barra CSS con porcentaje."""
    color = "#107c10" if percent == 100 else "#ff8c00" if percent > 0 else "#8a8886"
    return f'<div style="width:60px; height:20px; background-color:#f0f0f0; border-radius:3px; overflow:hidden;"><div style="width:{percent}%; height:100%; background-color:{color};"></div></div> {percent}%'


def _checklist_badge(done: int, total: int) -> str:
    """Genera checklist badge coloreado."""
    if total == 0:
        return "—"
    if done == total:
        color = "#107c10"
        bg = "#dff0d8"
    else:
        color = "#0078d4"
        bg = "#e8f4fd"
    return f'<span style="background-color:{bg}; color:{color}; padding:2px 6px; border-radius:3px;">{done}/{total}</span>'


def _build_donut_svg(
    completadas: int, en_progreso: int, sin_iniciar: int, vencidas: int, total: int
) -> str:
    """Genera SVG donut chart 150×150 con circunferencia 251.33 px (radio 40px). Fix 4.3: tamaño ampliado."""
    if total == 0:
        return '<svg width="150" height="150" viewBox="0 0 100 100"><circle cx="50" cy="50" r="40" fill="#f3f2f1"/></svg>'

    circ = 251.33
    segments = [
        (completadas, "#107c10"),  # verde
        (en_progreso, "#ff8c00"),  # naranja
        (sin_iniciar, "#8a8886"),  # gris
        (vencidas, "#d13438"),  # rojo
    ]
    paths = []
    offset = 0.0
    for count, color in segments:
        dash = count / total * circ
        paths.append(
            f'<circle cx="50" cy="50" r="40" fill="none" stroke="{color}" stroke-width="18" '
            f'stroke-dasharray="{dash:.1f} {circ - dash:.1f}" '
            f'stroke-dashoffset="-{offset:.1f}" transform="rotate(-90 50 50)"/>'
        )
        offset += dash
    pct = f"{int(completadas / total * 100)}%"
    legend_svg = f'''<svg width="150" height="150" viewBox="0 0 100 100">
    {"".join(paths)}
    <text x="50" y="55" text-anchor="middle" font-size="20" font-weight="bold" fill="#333">{pct}</text>
  </svg>'''
    return legend_svg


def _print_report_table(
    plan_title: str,
    buckets_dict: dict[str, str],
    tasks: list[dict[str, Any]],
    show_comments: bool = False,
    show_checklist: bool = False,
) -> None:
    """Imprime tabla de reporte con tareas agrupadas por bucket.

    Columnas: Bucket | Título | Asignado | Estado | % | Vence [| Checklist] [| Último comentario]

    Nota: el campo Assignee muestra el userId de Azure AD (GUID),
    no el email ni el nombre del usuario.
    """
    print(f"\n📋 {plan_title}")
    # Calculando ancho: 20+35+20+12+3+12 = 102 base + checklist 8 + comentario 39
    base_width = 20 + 35 + 20 + 12 + 3 + 12  # 102
    checklist_width = 8 if show_checklist else 0
    comments_width = 39 if show_comments else 0
    width = base_width + checklist_width + comments_width

    print("  " + "─" * width)
    header_parts = [
        f"{'Bucket':<20}",
        f"{'Título':<35}",
        f"{'Asignado':<20}",
        f"{'Estado':<12}",
        f"{'%':>3}",
        f"{'Vence':<12}",
    ]
    if show_checklist:
        header_parts.append(f"{'Checklist':<8}")
    if show_comments:
        header_parts.append(f"{'Último comentario':<39}")

    print("  " + " ".join(header_parts))
    print("  " + "─" * width)

    for task in tasks:
        bucket_id = task.get("bucketId", "")
        bucket_name = buckets_dict.get(bucket_id, "?")
        title = task.get("title", "")[:34]

        # Extraer asignado (assignments es {userId: {...}})
        assignments = task.get("assignments", {})
        assignee = ", ".join(assignments.keys())[:19] if assignments else "(sin asignar)"

        percent = task.get("percentComplete", 0)
        status = _derive_task_status(percent)

        due = task.get("dueDateTime", "")[:10] if task.get("dueDateTime") else "-"

        # Checklist: mostrar x/y si show_checklist, sino "-"
        cl_total = task.get("ChecklistTotal", 0)
        cl_done = task.get("ChecklistDone", 0)
        checklist_display = f"{cl_done}/{cl_total}" if cl_total > 0 else "-"

        # Construir fila dinámicamente
        row_parts = [
            f"{bucket_name:<20}",
            f"{title:<35}",
            f"{assignee:<20}",
            f"{status:<12}",
            f"{percent:>3}",
            f"{due:<12}",
        ]
        if show_checklist:
            row_parts.append(f"{checklist_display:<8}")
        if show_comments:
            comment_text = task.get("LastCommentText", "")[:38] or "-"
            row_parts.append(f"{comment_text:<39}")

        print("  " + " ".join(row_parts))

    print("  " + "─" * width)
    print()


def _print_kpi_block(
    plan_title: str,
    buckets_dict: dict[str, str],
    tasks: list[dict[str, Any]],
    show_comments: bool = False,
) -> None:
    """Imprime bloque de KPIs con métricas globales, señales por bucket y alertas."""
    if not tasks:
        return

    today = date.today()
    total = len(tasks)
    completadas = sum(1 for t in tasks if t.get("percentComplete", 0) == 100)
    en_progreso = sum(1 for t in tasks if 0 < t.get("percentComplete", 0) < 100)
    sin_iniciar = sum(1 for t in tasks if t.get("percentComplete", 0) == 0)
    vencidas = sum(
        1 for t in tasks
        if _parse_due(t) and _parse_due(t) < today and t.get("percentComplete", 0) < 100
    )

    # Estancadas: >7 días sin modificar (graceful skip si no disponible)
    modified_available = any(
        t.get("lastModifiedDateTime") not in ("", "-", None) for t in tasks
    )
    stagnadas = []
    if modified_available:
        cutoff = today - timedelta(days=7)
        stagnadas = [
            t for t in tasks
            if t.get("percentComplete", 0) < 100
            and t.get("lastModifiedDateTime") not in ("", "-", None)
            and datetime.fromisoformat(
                t["lastModifiedDateTime"].replace("Z", "+00:00")
            ).date() < cutoff
        ]

    # Imprime encabezado
    kpi_width = 85
    print("  " + "─" * kpi_width)
    print(f"  KPIs — {plan_title}")
    print("  " + "─" * kpi_width)

    # Métricas globales
    pct_comp = (completadas / total * 100) if total > 0 else 0
    pct_inprog = (en_progreso / total * 100) if total > 0 else 0
    pct_noinit = (sin_iniciar / total * 100) if total > 0 else 0

    print(f"  Total: {total}   ✅ Completadas: {completadas} ({pct_comp:.0f}%)   🔄 En progreso: {en_progreso} ({pct_inprog:.0f}%)   ⏸ Sin iniciar: {sin_iniciar} ({pct_noinit:.0f}%)")
    print(f"  Vencidas (no completadas): {vencidas}")

    # Cobertura de gestión si --comments
    if show_comments:
        commented = sum(1 for t in tasks if t.get("LastCommentText", "").strip())
        pct_commented = (commented / total * 100) if total > 0 else 0
        print(f"  Gestión (comentarios): {commented}/{total} comentadas ({pct_commented:.0f}%)")

    # Estancadas
    if modified_available and stagnadas:
        print(f"  Estancadas >7d sin modificar: {len(stagnadas)} tareas")

    print("  " + "─" * kpi_width)
    print()

    # Algoritmo de señal por bucket
    def _bucket_signal(bucket_name: str, bucket_tasks: list) -> str:
        bucket_total = len(bucket_tasks)
        if bucket_total == 0:
            return "—"
        comp = sum(1 for t in bucket_tasks if t.get("percentComplete", 0) == 100)
        inprog = sum(1 for t in bucket_tasks if 0 < t.get("percentComplete", 0) < 100)
        venc = sum(
            1 for t in bucket_tasks
            if _parse_due(t) and _parse_due(t) < today and t.get("percentComplete", 0) < 100
        )
        is_gateway = "gateway" in bucket_name.lower()

        if is_gateway and venc > 0:
            return "⛔ GATEWAY"
        if (inprog / bucket_total > 0.6 and venc > 0) or (inprog / bucket_total > 0.5 and comp == 0):
            return "⚠  CUELLO"
        if comp / bucket_total >= 0.5 or (inprog / bucket_total >= 0.3 and venc == 0):
            return "✅ FLUYE"
        return "🔵 PENDIENTE"

    # Tabla de buckets
    print("  Por Bucket:")
    print("  " + "─" * kpi_width)
    print(f"  {'Bucket':<20} {'Total':>6} {'✅Comp':>7} {'🔄InProg':>9} {'⏸NoInic':>9} {'⚠Venc':>7} {'Señal':<15}")
    print("  " + "─" * kpi_width)

    bucket_signals = {}
    for bucket_id, bucket_name in buckets_dict.items():
        bucket_tasks = [t for t in tasks if t.get("bucketId") == bucket_id]
        if not bucket_tasks:
            bucket_tasks = []  # Bucket vacío

        bt = len(bucket_tasks)
        b_comp = sum(1 for t in bucket_tasks if t.get("percentComplete", 0) == 100)
        b_inprog = sum(1 for t in bucket_tasks if 0 < t.get("percentComplete", 0) < 100)
        b_noinit = sum(1 for t in bucket_tasks if t.get("percentComplete", 0) == 0)
        b_venc = sum(
            1 for t in bucket_tasks
            if _parse_due(t) and _parse_due(t) < today and t.get("percentComplete", 0) < 100
        )

        signal = _bucket_signal(bucket_name, bucket_tasks)
        bucket_signals[bucket_name] = signal

        print(f"  {bucket_name:<20} {bt:>6} {b_comp:>7} {b_inprog:>9} {b_noinit:>9} {b_venc:>7} {signal:<15}")

    print("  " + "─" * kpi_width)
    print()

    # Cobertura de gestión por bucket si --comments
    if show_comments:
        print("  Cobertura de gestión por bucket:")
        print("  " + "─" * kpi_width)
        for bucket_id, bucket_name in buckets_dict.items():
            bucket_tasks = [t for t in tasks if t.get("bucketId") == bucket_id]
            if bucket_tasks:
                commented = sum(1 for t in bucket_tasks if t.get("LastCommentText", "").strip())
                pct = (commented / len(bucket_tasks) * 100) if bucket_tasks else 0
                print(f"  {bucket_name:<20}: {commented}/{len(bucket_tasks)} ({pct:.0f}%) comentadas")
        print("  " + "─" * kpi_width)
        print()

        # Urgentes sin comentario
        print("  Sin comentario con vencimiento próximo (<7 días):")
        cutoff_urgente = today + timedelta(days=7)
        urgentes_sin_comentario = [
            t for t in tasks
            if not t.get("LastCommentText", "").strip()
            and _parse_due(t)
            and today <= _parse_due(t) <= cutoff_urgente
        ]
        if urgentes_sin_comentario:
            for t in urgentes_sin_comentario:
                due_str = _parse_due(t).strftime("%Y-%m-%d") if _parse_due(t) else "—"
                print(f"    · {t.get('title', ''):<30} [Vence: {due_str}]")
        else:
            print("    (Ninguna)")
        print()
        print("  " + "─" * kpi_width)
        print()

    # Indicador final
    cuellos = [name for name, signal in bucket_signals.items() if "CUELLO" in signal]
    gateways_bloq = [name for name, signal in bucket_signals.items() if "GATEWAY" in signal]

    if not vencidas and not cuellos and not gateways_bloq:
        verdict = "El plan avanza sin fricción notable."
    elif vencidas and not cuellos and not gateways_bloq:
        verdict = f"{vencidas} tarea(s) vencida(s) — revisar fechas."
    elif gateways_bloq:
        verdict = "Bucket Gateway bloqueado — dependencias externas pendientes."
        if cuellos:
            verdict += f"\nDetectado cuello en: {', '.join(cuellos)}."
    elif cuellos:
        verdict = f"Detectado cuello en: {', '.join(cuellos)}."
    else:
        verdict = ""

    if verdict:
        print("  " + "─" * kpi_width)
        print(f"  {verdict}")
        print("  " + "─" * kpi_width)
        print()


def build_report_html(
    plan_title: str,
    buckets_dict: dict[str, str],
    tasks: list[dict[str, Any]],
    report_date: str,
    proximas_7d: int = 0,
) -> str:
    """Genera HTML con tabla de tareas y bloque de KPIs. Estilos inline (compatibilidad Outlook).

    Args:
        plan_title: Nombre del plan.
        buckets_dict: {bucketId: bucketName}.
        tasks: Lista de tareas enriquecidas (con assignments, percentComplete, dueDateTime, etc).
        report_date: Fecha del reporte en formato DD-MM-YYYY.
        proximas_7d: Cantidad de tareas que vencen en los próximos 7 días. Default: 0.

    Returns:
        HTML como string.
    """
    today = date.today()

    # Calcular KPIs
    total = len(tasks)
    completadas = sum(1 for t in tasks if t.get("percentComplete", 0) == 100)
    en_progreso = sum(1 for t in tasks if 0 < t.get("percentComplete", 0) < 100)
    sin_iniciar = sum(1 for t in tasks if t.get("percentComplete", 0) == 0)
    vencidas = sum(
        1 for t in tasks
        if _parse_due(t) and _parse_due(t) < today and t.get("percentComplete", 0) < 100
    )

    # Calcular señal por bucket
    bucket_signals: dict[str, dict[str, int]] = {}
    for task in tasks:
        bucket_id = task.get("bucketId", "")
        if bucket_id not in bucket_signals:
            bucket_signals[bucket_id] = {
                "total": 0,
                "completadas": 0,
                "en_progreso": 0,
                "sin_iniciar": 0,
                "vencidas": 0,
            }
        bucket_signals[bucket_id]["total"] += 1
        pct = task.get("percentComplete", 0)
        if pct == 100:
            bucket_signals[bucket_id]["completadas"] += 1
        elif pct > 0:
            bucket_signals[bucket_id]["en_progreso"] += 1
        else:
            bucket_signals[bucket_id]["sin_iniciar"] += 1
        if _parse_due(task) and _parse_due(task) < today and pct < 100:
            bucket_signals[bucket_id]["vencidas"] += 1

    # Función para determinar color de fila de tarea (Fix 4.3: colores vibrantes alineados con chart)
    def _get_task_row_color(task: dict[str, Any]) -> str:
        pct = task.get("percentComplete", 0)
        due = _parse_due(task)
        if pct == 100:
            return "#c8e6c8"  # verde — Completada (más vivo que #d4edda)
        if due and due < today and pct < 100:
            return "#f9d0d0"  # rojo claro — Vencida (coincide con #d13438 del chart)
        if pct > 0:
            return "#ffe0b0"  # naranja claro — En Progreso (coincide con #ff8c00)
        return "#e8e8e8"  # gris claro — Sin Iniciar (coincide con #8a8886)

    # Construir HTML
    html_parts: list[str] = []

    # Cabecera con banner degradado
    html_parts.append(f"""<html>
<head>
  <meta charset="UTF-8" />
  <style>
    body {{ font-family: Segoe UI, Arial, sans-serif; font-size: 12px; color: #333; }}
    table {{ border-collapse: collapse; width: 100%; margin: 10px 0; }}
    th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
    th {{ background-color: #0078d4; color: white; font-weight: bold; }}
    .header-banner {{ background: linear-gradient(135deg, #0078d4, #005a9e); border-radius: 8px; padding: 20px 24px; margin-bottom: 16px; color: white; }}
    .header-banner h1 {{ font-size: 20px; font-weight: 700; margin: 0; }}
    .header-banner p {{ font-size: 12px; color: rgba(255,255,255,0.8); margin: 5px 0 0 0; }}
    .kpi-cards {{ display: table; width: 100%; margin-bottom: 16px; }}
    .kpi-card {{ display: table-cell; width: 20%; padding: 12px 8px; border-left: 4px solid #0078d4; background-color: #f5f9ff; text-align: center; }}
    .kpi-card.green {{ border-left-color: #107c10; background-color: #dff0d8; }}
    .kpi-card.orange {{ border-left-color: #ff8c00; background-color: #fff4ce; }}
    .kpi-card.gray {{ border-left-color: #8a8886; background-color: #f3f2f1; }}
    .kpi-card.red {{ border-left-color: #d13438; background-color: #fde7e9; }}
    .kpi-card .number {{ font-size: 32px; font-weight: bold; color: #333; display: block; }}
    .kpi-card .label {{ font-size: 11px; color: #666; margin-top: 4px; }}
    .kpi-section {{ margin-top: 20px; padding: 15px; background-color: #f5f5f5; border-radius: 5px; }}
    .kpi-table {{ width: 100%; }}
    .donut-container {{ display: table; width: 100%; }}
    .donut-cell {{ display: table-cell; width: 150px; text-align: center; padding: 10px; }}
    .legend-cell {{ display: table-cell; padding: 10px; vertical-align: middle; }}
    .legend-item {{ font-size: 11px; margin: 4px 0; }}
    .legend-dot {{ display: inline-block; width: 12px; height: 12px; border-radius: 2px; margin-right: 4px; vertical-align: middle; }}
    .footer {{ margin-top: 20px; padding: 10px; font-size: 11px; color: #999; border-top: 1px solid #ddd; }}
  </style>
</head>
<body>
  <div class="header-banner">
    <h1 style="margin: 0;">{plan_title}</h1>
    <p style="margin: 5px 0 0 0;">Reporte de gestión · {report_date} · {total} tareas</p>
  </div>

  <!-- Fix 4.1-4.4: Layout 50/50 KPI (izquierda) + Donut chart (derecha) -->
  <h3>📊 Resumen de Gestión</h3>
  <table width="100%" style="margin-bottom:16px;" cellspacing="8" cellpadding="0" border="0">
    <tr valign="top">
      <!-- COLUMNA IZQUIERDA: Total arriba + grid 2x2 debajo -->
      <td width="50%" style="padding-right: 12px;" valign="top">
        <!-- Total — fila superior completa -->
        <table width="100%" cellspacing="0" cellpadding="0" style="margin-bottom:6px;">
          <tr>
            <td style="border-left:5px solid #0078d4; background:#e8f4fd; padding:10px 14px; border-radius:4px;">
              <span style="font-size:32px; font-weight:bold; color:#0055a0;">{total}</span>
              <span style="font-size:13px; color:#555; margin-left:8px;">Total</span>
            </td>
          </tr>
        </table>
        <!-- Grid 2×2: 4 estados -->
        <table width="100%" cellspacing="4" cellpadding="0">
          <tr>
            <td width="50%" style="border-left:4px solid #107c10; background:#c8e6c8; padding:8px 10px; border-radius:4px;">
              <div style="font-size:24px; font-weight:bold; color:#0d6e0d;">{completadas}</div>
              <div style="font-size:11px; color:#3f5f3f;">Completadas</div>
            </td>
            <td width="4"></td>
            <td width="50%" style="border-left:4px solid #e07800; background:#ffe0b0; padding:8px 10px; border-radius:4px;">
              <div style="font-size:24px; font-weight:bold; color:#8c5d00;">{en_progreso}</div>
              <div style="font-size:11px; color:#8c5d00;">En Progreso</div>
            </td>
          </tr>
          <tr><td colspan="3" style="height:4px;"></td></tr>
          <tr>
            <td width="50%" style="border-left:4px solid #605e5c; background:#e8e8e8; padding:8px 10px; border-radius:4px;">
              <div style="font-size:24px; font-weight:bold; color:#3f3d3b;">{sin_iniciar}</div>
              <div style="font-size:11px; color:#3f3d3b;">Sin Iniciar</div>
            </td>
            <td width="4"></td>
            <td width="50%" style="border-left:4px solid #d13438; background:#f9d0d0; padding:8px 10px; border-radius:4px;">
              <div style="font-size:24px; font-weight:bold; color:#8c2a2e;">{vencidas}</div>
              <div style="font-size:11px; color:#8c2a2e;">Vencidas</div>
            </td>
          </tr>
        </table>
      </td>
      <!-- COLUMNA DERECHA: Donut SVG + leyenda -->
      <td width="50%" style="text-align: center; padding-left: 12px;">
        <div style="text-align: center; margin-bottom: 12px;">
          {_build_donut_svg(completadas, en_progreso, sin_iniciar, vencidas, total)}
        </div>
        <!-- Leyenda debajo del donut -->
        <table style="margin: 8px auto; font-size:11px;">
          <tr>
            <td><span style="color:#107c10; font-weight:bold;">■</span> Completadas: {completadas}</td>
            <td style="padding-left: 12px;"><span style="color:#ff8c00; font-weight:bold;">■</span> En Progreso: {en_progreso}</td>
          </tr>
          <tr style="margin-top: 4px;">
            <td><span style="color:#8a8886; font-weight:bold;">■</span> Sin Iniciar: {sin_iniciar}</td>
            <td style="padding-left: 12px;"><span style="color:#d13438; font-weight:bold;">■</span> Vencidas: {vencidas}</td>
          </tr>
        </table>
      </td>
    </tr>
  </table>

  <!-- Próximas a vencer en 7 días -->
  <table width="100%" cellspacing="0" cellpadding="0" style="margin-top: 12px;">
    <tr>
      <td style="border-left:4px solid #ff8c00; background:#fff4e0; padding:8px 10px; border-radius:4px;">
        <span style="font-size:20px; font-weight:bold; color:#8c5000;">{proximas_7d}</span>
        <span style="font-size:11px; color:#8c5000; margin-left:6px;">Vencen en 7 días</span>
      </td>
    </tr>
  </table>

  <h3>📋 Tareas por Bucket</h3>
  <table>
    <thead>
      <tr>
        <th>Bucket</th>
        <th>Título</th>
        <th>Asignado</th>
        <th>Estado</th>
        <th>%</th>
        <th>Vence</th>
        <th>Checklist</th>
      </tr>
    </thead>
    <tbody>""")

    # Ordenar tareas por bucket (Backlog → En curso → Gateway → Completado)
    sorted_tasks = sorted(
        tasks,
        key=lambda t: (
            BUCKET_ORDER.get(
                buckets_dict.get(t.get("bucketId", ""), "").lower(), 99
            ),
            buckets_dict.get(t.get("bucketId", ""), ""),
        ),
    )

    for task in sorted_tasks:
        bucket_id = task.get("bucketId", "")
        bucket_name = buckets_dict.get(bucket_id, "?")
        title = task.get("title", "")[:50]

        # Extraer asignados — usar AssigneeDisplay si está disponible
        assignee = task.get("AssigneeDisplay", "(sin asignar)")

        percent = task.get("percentComplete", 0)
        status_badge = _status_badge(percent)
        due = task.get("dueDateTime", "")[:10] if task.get("dueDateTime") else "-"

        # Checklist badge coloreado
        cl_total = task.get("ChecklistTotal", 0)
        cl_done = task.get("ChecklistDone", 0)
        checklist_badge_html = _checklist_badge(cl_done, cl_total)

        # Columna % muestra ratio de checklist si está disponible, sino percentComplete
        if cl_total > 0:
            checklist_pct = int(cl_done / cl_total * 100)
            pct_display = f"{checklist_pct}%"
        else:
            pct_display = "-"

        row_color = _get_task_row_color(task)

        html_parts.append(f"""      <tr style="background-color: {row_color};">
        <td>{bucket_name}</td>
        <td>{title}</td>
        <td>{assignee}</td>
        <td>{status_badge}</td>
        <td style="text-align: center;">{pct_display}</td>
        <td>{due}</td>
        <td style="text-align: center;">{checklist_badge_html}</td>
      </tr>""")

    html_parts.append("""    </tbody>
  </table>

  <div class="footer">
    <p>Generado por automatización de procesos · Creado y desarrollado por Diego Morales - Project Manager 2026 · Gestión de proyectos e iniciativas: {total}</p>
  </div>
</body>
</html>""".format(report_date=report_date, total=total))

    return "\n".join(html_parts)


def parse_csv(path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    """Lee el CSV y devuelve lista de tareas normalizadas y advertencias de fecha."""
    tasks: list[dict[str, Any]] = []
    warnings: list[str] = []
    with path.open(encoding="utf-8-sig") as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            start_val, start_warn = parse_date(row["StartDate"].strip())
            due_val,   due_warn   = parse_date(row["DueDate"].strip())
            if start_warn:
                warnings.append(f"  Fila {reader.line_num}: StartDate {start_warn}")
            if due_warn:
                warnings.append(f"  Fila {reader.line_num}: DueDate   {due_warn}")
            tasks.append({
                "plan_name": row["PlanName"].strip(),
                "bucket_name": row["BucketName"].strip(),
                "title": row["TaskTitle"].strip(),
                "description": row.get("TaskDescription", "").strip(),
                "start_date": start_val,
                "due_date": due_val,
                "priority": map_priority(row["Priority"].strip()),
                "percent_complete": int(row.get("PercentComplete", 0)),
                "checklist_raw": row.get("ChecklistItems", "").strip(),
                "labels_raw": row.get("Labels", "").strip(),
                "assignee_email": row.get("AssignedToEmail", "").strip(),
            })
    return tasks, warnings


def extract_ordered_unique(tasks: list[dict], key: str) -> list[str]:
    seen: list[str] = []
    for t in tasks:
        val = t[key]
        if val not in seen:
            seen.append(val)
    return seen


def parse_csv_tasks(path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    """Modo tasks: requiere columnas PlanID y BucketID."""
    tasks: list[dict[str, Any]] = []
    warnings: list[str] = []
    with path.open(encoding="utf-8-sig") as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            plan_id = row.get("PlanID", "").strip()
            bucket_id = row.get("BucketID", "").strip()
            if not plan_id or not bucket_id:
                raise ValueError(
                    f"Modo 'tasks' requiere PlanID y BucketID. Fila: {dict(row)}"
                )
            start_val, start_warn = parse_date(row["StartDate"].strip())
            due_val,   due_warn   = parse_date(row["DueDate"].strip())
            if start_warn:
                warnings.append(f"  Fila {reader.line_num}: StartDate {start_warn}")
            if due_warn:
                warnings.append(f"  Fila {reader.line_num}: DueDate   {due_warn}")
            tasks.append({
                "plan_id": plan_id,
                "bucket_id": bucket_id,
                "title": row["TaskTitle"].strip(),
                "description": row.get("TaskDescription", "").strip(),
                "start_date": start_val,
                "due_date": due_val,
                "priority": map_priority(row["Priority"].strip()),
                "percent_complete": int(row.get("PercentComplete", 0) or 0),
                "checklist_raw": row.get("ChecklistItems", "").strip(),
                "labels_raw": row.get("Labels", "").strip(),
                "assignee_email": row.get("AssignedToEmail", "").strip(),
            })
    return tasks, warnings


def parse_csv_buckets(path: Path) -> list[dict[str, Any]]:
    """Modo buckets: requiere columnas PlanID y BucketName."""
    buckets: list[dict[str, Any]] = []
    with path.open(encoding="utf-8-sig") as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            plan_id = row.get("PlanID", "").strip()
            bucket_name = row.get("BucketName", "").strip()
            if not plan_id or not bucket_name:
                raise ValueError(
                    "Modo 'buckets' requiere PlanID y BucketName."
                )
            buckets.append({"plan_id": plan_id, "bucket_name": bucket_name})
    return buckets


def parse_csv_plan(path: Path) -> dict[str, Any]:
    """Modo plan: lee solo la primera fila. Requiere PlanName."""
    with path.open(encoding="utf-8-sig") as f:
        reader = csv.DictReader(f, delimiter=";")
        row = next(reader, None)
        if row is None:
            raise ValueError("El CSV de modo 'plan' está vacío.")
        plan_name = row.get("PlanName", "").strip()
        labels_raw = row.get("Labels", "").strip()
        if not plan_name:
            raise ValueError("Modo 'plan' requiere columna PlanName.")
        labels = [lbl.strip() for lbl in labels_raw.split(";") if lbl.strip()]
        return {"plan_name": plan_name, "labels": labels}


def confirm_date_warnings(warnings: list[str], dry_run: bool) -> bool:
    """Muestra las advertencias de fecha y pide confirmación si no es dry-run.

    Returns:
        True  → continuar
        False → abortar (solo posible en ejecución real)
    """
    if not warnings:
        return True
    print()
    print("⚠  Fechas inválidas en el CSV — se usará hoy+7 como fallback:")
    for w in warnings:
        print(w)
    if dry_run:
        print("   (dry-run: se continuaría con estos valores)")
        return True
    print()
    resp = input("¿Proceder de todos modos? [s/N]: ").strip().lower()
    return resp in ("s", "si", "sí", "y", "yes")


# ── Graph API ─────────────────────────────────────────────────────────────────

async def graph_request(
    client: httpx.AsyncClient,
    method: str,
    endpoint: str,
    token: str,
    *,
    json: Any = None,
    etag: str | None = None,
) -> Any:
    """Wrapper con retry para 429 y raise_for_status.
    FUTURO MCP: patrón idéntico a GraphAPIClient._make_request()
    """
    headers: dict[str, str] = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    if etag:
        headers["If-Match"] = etag

    for attempt in range(3):
        resp = await client.request(
            method,
            f"{GRAPH_BASE}{endpoint}",
            headers=headers,
            json=json,
        )
        if resp.status_code == 429:
            wait = int(resp.headers.get("Retry-After", 60))
            print(f"      [throttle] esperando {wait}s...")
            await asyncio.sleep(wait)
            continue
        if resp.status_code == 204:
            return None
        resp.raise_for_status()
        return resp.json()

    raise RuntimeError(f"Máximo de reintentos para {method} {endpoint}")


async def create_plan(
    client: httpx.AsyncClient, token: str, group_id: str, title: str
) -> dict[str, Any]:
    """POST /planner/plans → FUTURO MCP: GraphAPIClient.create_plan()"""
    return await graph_request(
        client, "POST", "/planner/plans", token,
        json={"owner": group_id, "title": title},
    )


async def configure_plan_labels(
    client: httpx.AsyncClient, token: str, plan_id: str, labels: list[str]
) -> None:
    """Define categorías del plan y construye LABEL_MAP global.
    FUTURO MCP: GraphAPIClient.patch_plan_details()
    """
    details = await graph_request(client, "GET", f"/planner/plans/{plan_id}/details", token)
    etag = details["@odata.etag"]
    category_descriptions = {f"category{i + 1}": lbl for i, lbl in enumerate(labels)}
    await graph_request(
        client, "PATCH", f"/planner/plans/{plan_id}/details", token,
        json={"categoryDescriptions": category_descriptions},
        etag=etag,
    )
    for i, lbl in enumerate(labels):
        LABEL_MAP[lbl] = f"category{i + 1}"


async def create_bucket(
    client: httpx.AsyncClient,
    token: str,
    plan_id: str,
    name: str,
    order_hint: str = " !",
) -> dict[str, Any]:
    """POST /planner/buckets → FUTURO MCP: GraphAPIClient.create_bucket()"""
    return await graph_request(
        client, "POST", "/planner/buckets", token,
        json={"planId": plan_id, "name": name, "orderHint": order_hint},
    )


async def list_plans(
    client: httpx.AsyncClient, token: str, group_id: str
) -> list[dict[str, Any]]:
    """GET /groups/{groupId}/planner/plans con paginación @odata.nextLink.
    Devuelve lista de dicts con al menos: id, title, createdDateTime, @odata.etag
    """
    plans: list[dict[str, Any]] = []
    endpoint: str = f"/groups/{group_id}/planner/plans"
    while endpoint:
        data = await graph_request(client, "GET", endpoint, token)
        plans.extend(data.get("value", []))
        next_link: str = data.get("@odata.nextLink", "")
        endpoint = next_link.replace(GRAPH_BASE, "") if next_link else ""
    return plans


async def list_buckets(
    client: httpx.AsyncClient,
    token: str,
    plan_id: str,
) -> list[dict[str, Any]]:
    """GET /planner/plans/{id}/buckets con paginación @odata.nextLink.
    Devuelve lista de dicts con al menos: id, name
    """
    buckets: list[dict[str, Any]] = []
    endpoint: str = f"/planner/plans/{plan_id}/buckets"
    while endpoint:
        data = await graph_request(client, "GET", endpoint, token)
        buckets.extend(data.get("value", []))
        next_link: str = data.get("@odata.nextLink", "")
        endpoint = next_link.replace(GRAPH_BASE, "") if next_link else ""
    return buckets


async def list_tasks(
    client: httpx.AsyncClient,
    token: str,
    plan_id: str,
) -> list[dict[str, Any]]:
    """GET /planner/plans/{id}/tasks con paginación @odata.nextLink.
    Por defecto, Microsoft Graph devuelve: id, title, bucketId, percentComplete, assignments,
    dueDateTime, createdDateTime, completedDateTime, priority.
    Nota: commentCount y conversationThreadId no están disponibles en este endpoint —
    se obtienen en get_task_details() si es necesario.
    """
    tasks: list[dict[str, Any]] = []
    endpoint: str = f"/planner/plans/{plan_id}/tasks"
    while endpoint:
        data = await graph_request(client, "GET", endpoint, token)
        tasks.extend(data.get("value", []))
        next_link: str = data.get("@odata.nextLink", "")
        endpoint = next_link.replace(GRAPH_BASE, "") if next_link else ""
    return tasks


async def get_task_details(
    client: httpx.AsyncClient,
    token: str,
    task_id: str,
) -> dict[str, Any]:
    """GET /planner/tasks/{id}/details para extraer descripción y checklist.
    Sin paginación (objeto único).
    """
    return await graph_request(client, "GET", f"/planner/tasks/{task_id}/details", token)


async def get_last_comment(
    client: httpx.AsyncClient,
    token: str,
    group_id: str,
    thread_id: str,
) -> dict[str, str]:
    """GET el post más reciente del hilo de conversación de una tarea.
    Endpoint: GET /groups/{group_id}/threads/{thread_id}/posts
              ?$top=1&$orderby=receivedDateTime%20desc&$select=body,receivedDateTime
    Returns {"text": str, "date": "YYYY-MM-DD"} o {"text": "-", "date": "-"} si 404/sin posts.
    """
    try:
        data = await graph_request(
            client,
            "GET",
            f"/groups/{group_id}/threads/{thread_id}/posts"
            "?$top=1&$orderby=receivedDateTime%20desc&$select=body,receivedDateTime",
            token,
        )
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            return {"text": "-", "date": "-"}
        raise
    posts = data.get("value", [])
    if not posts:
        return {"text": "-", "date": "-"}
    post = posts[0]
    raw_html = post.get("body", {}).get("content", "") or ""
    text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", raw_html)).strip()[:200] or "-"
    date_str = (post.get("receivedDateTime") or "")[:10] or "-"
    return {"text": text, "date": date_str}


async def delete_plan(
    client: httpx.AsyncClient, token: str, plan_id: str
) -> None:
    """GET /planner/plans/{id} para obtener ETag → DELETE /planner/plans/{id}.
    graph_request() ya maneja 429 y raise_for_status.
    """
    plan = await graph_request(client, "GET", f"/planner/plans/{plan_id}", token)
    etag: str = plan["@odata.etag"]
    await graph_request(
        client, "DELETE", f"/planner/plans/{plan_id}", token, etag=etag
    )


async def send_mail_report(
    client: httpx.AsyncClient,
    token: str,
    to_emails: list[str],
    subject: str,
    html_body: str,
) -> None:
    """Envía correo HTML via POST /me/sendMail.
    Permiso requerido: Mail.Send

    Args:
        client: httpx.AsyncClient.
        token: Access token.
        to_emails: Lista de emails de destinatarios.
        subject: Asunto del correo.
        html_body: Cuerpo HTML del correo.

    Raises:
        ValueError: Si to_emails está vacío.
        httpx.HTTPStatusError: Si Graph API retorna error.
    """
    if not to_emails:
        raise ValueError("to_emails no puede estar vacío")

    payload: dict[str, Any] = {
        "message": {
            "subject": subject,
            "body": {"contentType": "HTML", "content": html_body},
            "toRecipients": [
                {"emailAddress": {"address": email}} for email in to_emails
            ],
        },
        "saveToSentItems": True,
    }

    # POST /me/sendMail retorna 202 Accepted (sin body)
    await graph_request(client, "POST", "/me/sendMail", token, json=payload)


async def get_site_id(
    client: httpx.AsyncClient,
    token: str,
    site_url: str,
) -> str:
    """GET /sites/{hostname}:/{site_path} → devuelve el site ID."""
    parsed = urlparse(site_url)
    hostname = parsed.netloc                    # cosemar.sharepoint.com
    site_path = parsed.path.rstrip("/")        # /sites/Gestioncontrolproyectos
    data = await graph_request(
        client, "GET", f"/sites/{hostname}:{site_path}", token
    )
    return data["id"]


async def list_site_drive_items(
    client: httpx.AsyncClient,
    token: str,
    site_id: str,
    folder_path: str = "",
) -> list[dict[str, Any]]:
    """
    GET /sites/{siteId}/drive/root/children           (raíz)
    GET /sites/{siteId}/drive/root:/{path}:/children  (subcarpeta)
    Pagina con @odata.nextLink. Devuelve lista de DriveItems.
    """
    select = "name,size,file,folder,webUrl,lastModifiedDateTime,createdBy"
    if folder_path:
        endpoint = f"/sites/{site_id}/drive/root:/{folder_path}:/children?$select={select}&$top=100"
    else:
        endpoint = f"/sites/{site_id}/drive/root/children?$select={select}&$top=100"

    items: list[dict[str, Any]] = []
    while endpoint:
        data = await graph_request(client, "GET", endpoint, token)
        items.extend(data.get("value", []))
        next_link: str = data.get("@odata.nextLink", "")
        endpoint = next_link.replace(GRAPH_BASE, "") if next_link else ""
    return items


def _print_plans_table(plans: list[dict[str, Any]]) -> None:
    """Imprime tabla numerada con id, título y fecha de creación."""
    print(f"\n  {'#':<4} {'ID':<36} {'Título':<40} {'Creado'}")
    print("  " + "─" * 86)
    for i, p in enumerate(plans, 1):
        created = p.get("createdDateTime", "")[:10]
        print(f"  {i:<4} {p['id']:<36} {p['title']:<40} {created}")
    print()


def _print_docs_table(items: list[dict[str, Any]], filter_text: str = "") -> None:
    """Imprime tabla de DriveItems (archivos/carpetas) de SharePoint."""
    if filter_text:
        items = [i for i in items if filter_text.lower() in i["name"].lower()]
    print(f"\nDocumentos encontrados: {len(items)}\n")
    print(f"  {'#':<4} {'Tipo':<7} {'Nombre':<50} {'Modificado':<12} {'Tamaño':>10}")
    print(f"  {'-'*4} {'-'*7} {'-'*50} {'-'*12} {'-'*10}")
    for i, item in enumerate(items, 1):
        tipo = "Carpeta" if "folder" in item else "Archivo"
        size = f"{item.get('size', 0):,}" if "file" in item else "-"
        modified = item.get("lastModifiedDateTime", "")[:10]
        name = item["name"][:49]
        print(f"  {i:<4} {tipo:<7} {name:<50} {modified:<12} {size:>10}")


async def resolve_email_to_guid(
    client: httpx.AsyncClient,
    token: str,
    email: str,
    cache: dict[str, str | None],
) -> str | None:
    """GET /users/{email} → extrae 'id'. Caché en memoria por sesión.
    Devuelve None si el email no existe o la API falla (warning impreso).
    """
    if email in cache:
        return cache[email]
    try:
        data = await graph_request(client, "GET", f"/users/{email}", token)
        guid: str = data["id"]
        cache[email] = guid
        return guid
    except Exception as exc:
        print(f"      [WARN] No se pudo resolver '{email}': {exc}")
        cache[email] = None
        return None


async def resolve_guid_to_email(
    client: httpx.AsyncClient, token: str, guid: str
) -> str | None:
    """Resuelve GUID de usuario Azure AD a email. Usa cache global.
    Retorna None si falla.
    Permiso requerido: User.Read.All
    """
    if guid in _GUID_TO_EMAIL_CACHE:
        return _GUID_TO_EMAIL_CACHE[guid]
    try:
        data = await graph_request(client, "GET", f"/users/{guid}?$select=mail,userPrincipalName", token)
        email = data.get("mail") or data.get("userPrincipalName")
    except (httpx.HTTPStatusError, httpx.RequestError):
        email = None
    _GUID_TO_EMAIL_CACHE[guid] = email
    return email


async def resolve_guid_to_display_name(
    client: httpx.AsyncClient, token: str, guid: str
) -> str | None:
    """Resuelve GUID de usuario Azure AD a nombre legible. Usa caché global.
    Retorna None si falla.
    Permiso requerido: User.Read.All
    """
    if guid in _GUID_TO_NAME_CACHE:
        return _GUID_TO_NAME_CACHE[guid]
    try:
        data = await graph_request(
            client, "GET", f"/users/{guid}?$select=displayName,givenName,surname", token
        )
        name = (
            data.get("displayName")
            or f"{data.get('givenName', '')} {data.get('surname', '')}".strip()
            or None
        )
    except (httpx.HTTPStatusError, httpx.RequestError):
        name = None
    _GUID_TO_NAME_CACHE[guid] = name
    return name


async def create_task_full(
    client: httpx.AsyncClient,
    token: str,
    plan_id: str,
    bucket_id: str,
    task: dict[str, Any],
    assignee_guid: str | None,
) -> str:
    """Crea tarea + PATCH details en secuencia.
    FUTURO MCP: tool create_task ampliado en server.py
    3 llamadas: POST /tasks → GET /tasks/{id}/details → PATCH /tasks/{id}/details
    """
    # 1. Crear tarea base
    payload: dict[str, Any] = {
        "planId": plan_id,
        "bucketId": bucket_id,
        "title": task["title"],
        "priority": task["priority"],
        "percentComplete": task["percent_complete"],
    }
    if task["start_date"] is not None:
        payload["startDateTime"] = task["start_date"]
    if task["due_date"] is not None:
        payload["dueDateTime"] = task["due_date"]
    if assignee_guid is not None:
        payload["assignments"] = {
            assignee_guid: {
                "@odata.type": "#microsoft.graph.plannerAssignment",
                "orderHint": " !",
            }
        }
    labels = parse_labels(task["labels_raw"])
    if labels:
        payload["appliedCategories"] = labels

    created = await graph_request(client, "POST", "/planner/tasks", token, json=payload)
    task_id: str = created["id"]

    # 2. GET /details para obtener su ETag (distinto al ETag de la tarea)
    details = await graph_request(client, "GET", f"/planner/tasks/{task_id}/details", token)
    details_etag: str = details["@odata.etag"]

    # 3. PATCH /details con descripción y checklist
    body: dict[str, Any] = {}
    if task["description"]:
        body["description"] = task["description"]
    checklist, checklist_warnings = build_checklist(task["checklist_raw"])
    for w in checklist_warnings:
        print(w)
    if checklist:
        body["checklist"] = checklist

    if body:
        await graph_request(
            client, "PATCH", f"/planner/tasks/{task_id}/details", token,
            json=body, etag=details_etag,
        )

    return task_id


async def run_list(group_id: str, filter_text: str = "") -> None:
    """Modo list: muestra tabla de planes; no realiza ninguna acción."""
    settings = Settings()
    auth = MicrosoftAuthManager(
        tenant_id=settings.azure_tenant_id,
        client_id=settings.azure_client_id,
        client_secret=settings.azure_client_secret,
    )
    token = auth.get_token()
    async with httpx.AsyncClient(timeout=30.0) as client:
        plans = await list_plans(client, token, group_id)
    if filter_text:
        plans = [p for p in plans if filter_text.lower() in p["title"].lower()]
    print(
        f"Planes encontrados: {len(plans)}"
        + (f" (filtro: '{filter_text}')" if filter_text else "")
    )
    _print_plans_table(plans)


async def run_delete(
    group_id: str,
    filter_text: str = "",
    dry_run: bool = False,
) -> dict[str, Any]:
    """Modo delete: lista planes → selección interactiva → elimina.
    Devuelve {'deleted': list[str], 'errors': list[str]}
    """
    result: dict[str, Any] = {"deleted": [], "errors": []}

    settings = Settings()
    auth = MicrosoftAuthManager(
        tenant_id=settings.azure_tenant_id,
        client_id=settings.azure_client_id,
        client_secret=settings.azure_client_secret,
    )
    token = auth.get_token()

    async with httpx.AsyncClient(timeout=30.0) as client:
        plans = await list_plans(client, token, group_id)
        if filter_text:
            plans = [p for p in plans if filter_text.lower() in p["title"].lower()]

        if not plans:
            print("No se encontraron planes.")
            return result

        _print_plans_table(plans)

        # Selección interactiva
        raw = input(
            "  Introduce los números a eliminar (separados por coma) o 'todos': "
        ).strip()
        if raw.lower() == "todos":
            selected = plans
        else:
            indices = [int(x.strip()) - 1 for x in raw.split(",") if x.strip().isdigit()]
            selected = [plans[i] for i in indices if 0 <= i < len(plans)]

        if not selected:
            print("  Sin selección. Saliendo.")
            return result

        print(f"\n  Planes seleccionados para eliminar ({len(selected)}):")
        for p in selected:
            print(f"    - {p['title']}  [{p['id']}]")

        if dry_run:
            print("\n[DRY RUN] Sin cambios en Planner.")
            return result

        confirm = input(
            f"\n  ¿Confirmar eliminación de {len(selected)} planes? (s/N): "
        ).strip().lower()
        if confirm != "s":
            print("  Cancelado.")
            return result

        for i, p in enumerate(selected, 1):
            print(f"  [{i}/{len(selected)}] Eliminando '{p['title']}'...", end=" ", flush=True)
            try:
                await delete_plan(client, token, p["id"])
                result["deleted"].append(p["id"])
                print("✓")
                await asyncio.sleep(0.5)
            except Exception as exc:
                result["errors"].append(f"'{p['title']}': {exc}")
                print(f"✗ {exc}")

    return result


# ── Orquestador ───────────────────────────────────────────────────────────────

@dataclass
class ImportResult:
    plan_id: str = ""
    bucket_ids: dict[str, str] = field(default_factory=dict)
    task_ids: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    guids_resolved: int = 0
    guids_failed: list[str] = field(default_factory=list)
    tasks_unassigned: int = 0
    # Campos dry-run (poblados desde CSV, sin llamada a la API)
    dry_run: bool = False
    plan_name: str = ""
    buckets_total: int = 0
    tasks_total: int = 0


async def run_import_full(
    csv_path: Path,
    group_id: str,
    dry_run: bool = False,
) -> ImportResult:
    """Orquestador principal.
    FUTURO MCP: task_tools.py → TaskTools.import_plan_from_csv()
    """
    result = ImportResult()
    tasks, date_warnings = parse_csv(csv_path)
    plan_name: str = tasks[0]["plan_name"]
    buckets_ordered = extract_ordered_unique(tasks, "bucket_name")
    all_labels = extract_ordered_unique(
        [{"labels_raw": lbl}
         for t in tasks
         for lbl in t["labels_raw"].split(";")
         if lbl.strip()],
        "labels_raw",
    )

    total_calls = 1 + 1 + len(buckets_ordered) + len(tasks) * 3
    print(f"Plan     : '{plan_name}'")
    print(f"Group    : {group_id}")
    print(f"Labels   : {all_labels}")
    print(f"Buckets  : {len(buckets_ordered)}")
    print(f"Tareas   : {len(tasks)}")
    print(f"Llamadas : ~{total_calls}")

    if not confirm_date_warnings(date_warnings, dry_run):
        print("Importación cancelada por el usuario.")
        return result

    print()
    if dry_run:
        result.dry_run = True
        result.plan_name = plan_name
        result.buckets_total = len(buckets_ordered)
        result.tasks_total = len(tasks)
        print("[DRY RUN] Sin cambios en Planner.")
        for b in buckets_ordered:
            bucket_tasks = [t for t in tasks if t["bucket_name"] == b]
            print(f"  Bucket '{b}' -> {len(bucket_tasks)} tareas")
        return result

    settings = Settings()
    auth = MicrosoftAuthManager(
        tenant_id=settings.azure_tenant_id,
        client_id=settings.azure_client_id,
        client_secret=settings.azure_client_secret,
    )
    token = auth.get_token()

    async with httpx.AsyncClient(timeout=30.0) as client:
        # 1. Plan
        print("[1/4] Creando plan...")
        plan = await create_plan(client, token, group_id, plan_name)
        result.plan_id = plan["id"]
        print(f"      plan_id: {result.plan_id}")
        await asyncio.sleep(2)

        # 2. Labels
        print(f"[2/4] Configurando labels {all_labels}...")
        await configure_plan_labels(client, token, result.plan_id, all_labels)
        print(f"      {LABEL_MAP}")

        # 3. Buckets
        print(f"[3/4] Creando {len(buckets_ordered)} buckets...")
        for bucket_name in buckets_ordered:
            bucket = await create_bucket(client, token, result.plan_id, bucket_name)
            result.bucket_ids[bucket_name] = bucket["id"]
            print(f"      ✓ '{bucket_name}'")
            await asyncio.sleep(0.5)

        # 4. Tareas
        # Caché de resolución email → GUID (compartido por todas las tareas)
        guid_cache: dict[str, str | None] = {}

        print(f"[4/4] Creando {len(tasks)} tareas (3 llamadas c/u)...")
        for i, task in enumerate(tasks, 1):
            try:
                # Resolver email → GUID
                email = task.get("assignee_email", "")
                if email:
                    assignee_guid = await resolve_email_to_guid(client, token, email, guid_cache)
                    if assignee_guid is not None:
                        result.guids_resolved += 1
                    else:
                        result.guids_failed.append(email)
                else:
                    assignee_guid = None
                    result.tasks_unassigned += 1

                bucket_id = result.bucket_ids[task["bucket_name"]]
                task_id = await create_task_full(
                    client, token, result.plan_id, bucket_id, task, assignee_guid
                )
                result.task_ids.append(task_id)
                print(f"      [{i:02d}/{len(tasks)}] ✓ {task['title']}")
                await asyncio.sleep(0.3)
            except Exception as exc:
                msg = f"[{i:02d}/{len(tasks)}] ✗ '{task['title']}': {exc}"
                result.errors.append(msg)
                print(f"      {msg}")

    return result


async def run_import_plan(
    csv_path: Path,
    group_id: str,
    dry_run: bool = False,
) -> ImportResult:
    """Modo plan: crea solo la cabecera del plan y configura sus labels."""
    result = ImportResult()
    data = parse_csv_plan(csv_path)
    plan_name: str = data["plan_name"]
    labels: list[str] = data["labels"]

    print(f"Plan     : '{plan_name}'")
    print(f"Group    : {group_id}")
    print(f"Labels   : {labels}")
    print()

    if dry_run:
        result.dry_run = True
        result.plan_name = plan_name
        print("[DRY RUN] Sin cambios en Planner.")
        return result

    settings = Settings()
    auth = MicrosoftAuthManager(
        tenant_id=settings.azure_tenant_id,
        client_id=settings.azure_client_id,
        client_secret=settings.azure_client_secret,
    )
    token = auth.get_token()

    async with httpx.AsyncClient(timeout=30.0) as client:
        print("[1/2] Creando plan...")
        plan = await create_plan(client, token, group_id, plan_name)
        result.plan_id = plan["id"]
        print(f"      plan_id: {result.plan_id}")
        await asyncio.sleep(2)

        print(f"[2/2] Configurando labels {labels}...")
        await configure_plan_labels(client, token, result.plan_id, labels)
        print(f"      {LABEL_MAP}")

    return result


async def run_import_buckets(
    csv_path: Path,
    dry_run: bool = False,
) -> ImportResult:
    """Modo buckets: crea buckets en un plan existente (PlanID desde CSV)."""
    result = ImportResult()
    buckets = parse_csv_buckets(csv_path)

    plan_ids = extract_ordered_unique(buckets, "plan_id")
    if len(plan_ids) > 1:
        raise ValueError(
            f"Modo 'buckets' requiere que todos los registros tengan el mismo PlanID. "
            f"Encontrados: {plan_ids}"
        )
    plan_id = plan_ids[0]
    bucket_names = extract_ordered_unique(buckets, "bucket_name")

    print(f"PlanID   : {plan_id}")
    print(f"Buckets  : {len(bucket_names)}")
    print()

    if dry_run:
        result.dry_run = True
        result.buckets_total = len(bucket_names)
        print("[DRY RUN] Sin cambios en Planner.")
        for name in bucket_names:
            print(f"  Bucket '{name}'")
        return result

    settings = Settings()
    auth = MicrosoftAuthManager(
        tenant_id=settings.azure_tenant_id,
        client_id=settings.azure_client_id,
        client_secret=settings.azure_client_secret,
    )
    token = auth.get_token()

    async with httpx.AsyncClient(timeout=30.0) as client:
        print(f"[1/1] Creando {len(bucket_names)} buckets...")
        for bucket_name in bucket_names:
            bucket = await create_bucket(client, token, plan_id, bucket_name)
            result.bucket_ids[bucket_name] = bucket["id"]
            print(f"      ✓ '{bucket_name}'")
            await asyncio.sleep(0.5)

    return result


async def run_import_tasks(
    csv_path: Path,
    dry_run: bool = False,
) -> ImportResult:
    """Modo tasks: agrega tareas a plan/bucket existentes (PlanID/BucketID desde CSV).
    LIMITACIÓN: LABEL_MAP vacío en este modo — labels del CSV no se aplican.
    """
    result = ImportResult()
    tasks, date_warnings = parse_csv_tasks(csv_path)

    print(f"Tareas   : {len(tasks)}")
    print(f"Llamadas : ~{len(tasks) * 3}")

    if not confirm_date_warnings(date_warnings, dry_run):
        print("Importación cancelada por el usuario.")
        return result

    print()
    if dry_run:
        result.dry_run = True
        result.tasks_total = len(tasks)
        print("[DRY RUN] Sin cambios en Planner.")
        for t in tasks:
            print(f"  PlanID={t['plan_id']} BucketID={t['bucket_id']} -> '{t['title']}'")
        return result

    settings = Settings()
    auth = MicrosoftAuthManager(
        tenant_id=settings.azure_tenant_id,
        client_id=settings.azure_client_id,
        client_secret=settings.azure_client_secret,
    )
    token = auth.get_token()

    async with httpx.AsyncClient(timeout=30.0) as client:
        guid_cache: dict[str, str | None] = {}

        print(f"[1/1] Creando {len(tasks)} tareas (3 llamadas c/u)...")
        for i, task in enumerate(tasks, 1):
            try:
                email = task.get("assignee_email", "")
                if email:
                    assignee_guid = await resolve_email_to_guid(client, token, email, guid_cache)
                    if assignee_guid is not None:
                        result.guids_resolved += 1
                    else:
                        result.guids_failed.append(email)
                else:
                    assignee_guid = None
                    result.tasks_unassigned += 1

                task_id = await create_task_full(
                    client, token, task["plan_id"], task["bucket_id"], task, assignee_guid
                )
                result.task_ids.append(task_id)
                print(f"      [{i:02d}/{len(tasks)}] ✓ {task['title']}")
                await asyncio.sleep(0.3)
            except Exception as exc:
                msg = f"[{i:02d}/{len(tasks)}] ✗ '{task['title']}': {exc}"
                result.errors.append(msg)
                print(f"      {msg}")

    return result


async def run_sp_list(
    site_url: str,
    folder_path: str,
    filter_text: str,
) -> None:
    """Modo sp-list: lista archivos/carpetas de la librería de documentos de un sitio SharePoint."""
    settings = Settings()
    auth = MicrosoftAuthManager(
        tenant_id=settings.azure_tenant_id,
        client_id=settings.azure_client_id,
        client_secret=settings.azure_client_secret,
    )
    token = auth.get_token()

    async with httpx.AsyncClient(timeout=30.0) as client:
        print(f"Sitio  : {site_url}")
        print(f"Carpeta: {folder_path or '(raíz)'}\n")
        site_id = await get_site_id(client, token, site_url)
        try:
            items = await list_site_drive_items(client, token, site_id, folder_path)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                print(f'[ERROR] Carpeta no encontrada: "{folder_path}"')
                return
            raise
        _print_docs_table(items, filter_text)


async def run_report(
    group_id: str,
    filter_text: str = "",
    export_csv: Path | None = None,
    fetch_comments: bool = False,
    fetch_checklist: bool = False,
) -> None:
    """Lista planes con selección interactiva e imprime tareas por plan, opcionalmente exporta a CSV.

    Args:
        group_id: ID del grupo M365 cuyos planes se listan.
        filter_text: Filtra planes cuyo título lo contenga (case-insensitive). Vacío = sin filtro.
        export_csv: Si se especifica, exporta el reporte a CSV con delimitador ';'.
                    No puede apuntar a un archivo .env (ValueError).
        fetch_comments: Si True, obtiene el último comentario por tarea (1 llamada Graph extra por tarea).
        fetch_checklist: Si True, obtiene el contador de checklist por tarea (1 llamada Graph extra por tarea).

    Raises:
        ValueError: Si export_csv contiene '.env' en la ruta.
    """
    # Validar export_csv si se proporciona
    if export_csv and ".env" in str(export_csv):
        raise ValueError("No se permite exportar a .env por razones de seguridad")

    settings = Settings()
    auth = MicrosoftAuthManager(
        tenant_id=settings.azure_tenant_id,
        client_id=settings.azure_client_id,
        client_secret=settings.azure_client_secret,
    )
    token = auth.get_token()

    async with httpx.AsyncClient(timeout=30.0) as client:
        # 1. Listar planes
        plans = await list_plans(client, token, group_id)
        if filter_text:
            plans = [p for p in plans if filter_text.lower() in p["title"].lower()]

        if not plans:
            print("No se encontraron planes.")
            return

        _print_plans_table(plans)

        # 2. Selección interactiva
        raw = input(
            "  Introduce los números a seleccionar (separados por coma) o 'todos': "
        ).strip()
        if raw.lower() == "todos":
            selected = plans
        else:
            indices = [int(x.strip()) - 1 for x in raw.split(",") if x.strip().isdigit()]
            selected = [plans[i] for i in indices if 0 <= i < len(plans)]

        if not selected:
            print("  Sin selección. Saliendo.")
            return

        # 3. Procesar cada plan
        all_rows: list[dict[str, Any]] = []

        for plan in selected:
            plan_id = plan["id"]
            plan_title = plan["title"]

            try:
                # Obtener buckets y tasks
                buckets = await list_buckets(client, token, plan_id)
                buckets_dict = {b["id"]: b["name"] for b in buckets}

                tasks = await list_tasks(client, token, plan_id)

                # Pre-fetch checklist paralelo si se solicita (con semáforo para respetar rate limit)
                checklist_map: dict[str, tuple[int, int]] = {}  # task_id → (done, total)
                if fetch_checklist:
                    sem = asyncio.Semaphore(5)

                    async def _fetch_one_checklist(task_id: str) -> tuple[str, int, int]:
                        async with sem:
                            try:
                                details = await get_task_details(client, token, task_id)
                                cl = details.get("checklist", {})
                                total = len(cl)
                                done = sum(1 for v in cl.values() if v.get("isChecked", False))
                                await asyncio.sleep(0.1)
                                return task_id, done, total
                            except (httpx.HTTPStatusError, httpx.RequestError):
                                return task_id, 0, 0

                    results = await asyncio.gather(
                        *[_fetch_one_checklist(t.get("id", "")) for t in tasks]
                    )
                    checklist_map = {tid: (done, total) for tid, done, total in results}

                # Enriquecer tareas con comentario si --comments fue solicitado
                enriched_tasks = []
                for task in tasks:
                    task_id = task.get("id", "")
                    thread_id = ""
                    comment = {"text": "", "date": ""}

                    if fetch_comments and task_id:
                        try:
                            # Obtener conversationThreadId de /planner/tasks/{id}
                            task_details = await graph_request(
                                client, "GET", f"/planner/tasks/{task_id}", token
                            )
                            thread_id = task_details.get("conversationThreadId") or ""
                            if thread_id:
                                comment = await get_last_comment(client, token, group_id, thread_id)
                                await asyncio.sleep(0.5)  # rate-limit: threads/posts tiene límite propio
                        except (httpx.HTTPStatusError, httpx.RequestError):
                            # Si falla obtener detalles, continuar sin comentario
                            pass

                    cl_done, cl_total = checklist_map.get(task_id, (0, 0))

                    enriched_tasks.append({
                        **task,
                        "LastCommentText": comment["text"],
                        "LastCommentDate": comment["date"],
                        "CommentCount": task.get("commentCount", 0),
                        "ChecklistDone": cl_done,
                        "ChecklistTotal": cl_total,
                        "priority": task.get("priority", 5),
                    })

                # Imprimir tabla para este plan
                _print_report_table(plan_title, buckets_dict, enriched_tasks, show_comments=fetch_comments, show_checklist=fetch_checklist)
                _print_kpi_block(plan_title, buckets_dict, enriched_tasks, show_comments=fetch_comments)

                # Preparar filas para exportación
                for task in enriched_tasks:
                    bucket_id = task.get("bucketId", "")
                    bucket_name = buckets_dict.get(bucket_id, "")
                    assignments = task.get("assignments", {})
                    assignee_ids = ", ".join(assignments.keys())

                    row = {
                        "PlanID": plan_id,
                        "PlanTitle": plan_title,
                        "BucketID": bucket_id,
                        "BucketName": bucket_name,
                        "TaskID": task.get("id", ""),
                        "TaskTitle": task.get("title", ""),
                        "Assignee": assignee_ids,
                        "Status": _derive_task_status(task.get("percentComplete", 0)),
                        "PercentComplete": task.get("percentComplete", 0),
                        "DueDate": task.get("dueDateTime", "")[:10] if task.get("dueDateTime") else "",
                        "CreatedDate": task.get("createdDateTime", "")[:10] if task.get("createdDateTime") else "",
                        "ChecklistDone": task.get("ChecklistDone", 0),
                        "ChecklistTotal": task.get("ChecklistTotal", 0),
                    }
                    all_rows.append(row)

                await asyncio.sleep(0.3)
            except httpx.HTTPStatusError as exc:
                print(f"  ✗ Error Graph al procesar '{plan_title}': {exc.response.status_code}")
            except httpx.RequestError as exc:
                print(f"  ✗ Error de red al procesar '{plan_title}': {exc}")

        # 4. Exportar si se solicita
        if export_csv and all_rows:
            export_csv.parent.mkdir(parents=True, exist_ok=True)
            with export_csv.open("w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(
                    f,
                    fieldnames=[
                        "PlanID",
                        "PlanTitle",
                        "BucketID",
                        "BucketName",
                        "TaskID",
                        "TaskTitle",
                        "Assignee",
                        "Status",
                        "PercentComplete",
                        "DueDate",
                        "CreatedDate",
                        "ChecklistDone",
                        "ChecklistTotal",
                    ],
                    delimiter=";",
                )
                writer.writeheader()
                writer.writerows(all_rows)
            print(f"\n✓ Reporte exportado a: {export_csv}")
        elif all_rows:
            print(f"\nReporte de {len(all_rows)} tareas completado.")


async def run_email_report(
    group_id: str,
    filter_text: str = "",
    preview: bool = False,
    to_override: str = "",
    fetch_checklist: bool = False,
) -> None:
    """Envía reporte HTML por correo a los asignados de cada plan.
    Completamente separado de run_report() — sin modificar el flujo terminal.

    Args:
        group_id: ID del grupo M365 cuyos planes se listan.
        filter_text: Filtra planes cuyo título lo contenga (case-insensitive). Vacío = sin filtro.
        preview: Si True, guarda HTML en reports/ y abre en navegador. No envía correo.
        to_override: Si no vacío, envía sólo a este email (bypass de asignados).
        fetch_checklist: Si True, obtiene el contador de checklist por tarea (1 llamada Graph extra por tarea).

    Notes:
        - Realiza pre-fetch paralelo de commentCount para todas las tareas (GET /planner/tasks/{id}?$select=commentCount).
          Usa semáforo 5 + sleep(0.2) para respetar rate limits. Sin este pre-fetch, commentCount siempre sería 0.
    """
    settings = Settings()
    auth = MicrosoftAuthManager(
        tenant_id=settings.azure_tenant_id,
        client_id=settings.azure_client_id,
        client_secret=settings.azure_client_secret,
    )
    token = auth.get_token()

    async with httpx.AsyncClient(timeout=30.0) as client:
        # 1. Listar planes
        plans = await list_plans(client, token, group_id)
        if filter_text:
            plans = [p for p in plans if filter_text.lower() in p["title"].lower()]

        if not plans:
            print("No se encontraron planes.")
            return

        _print_plans_table(plans)

        # 2. Selección interactiva
        raw = input(
            "  Introduce los números a seleccionar (separados por coma) o 'todos': "
        ).strip()
        if raw.lower() == "todos":
            selected = plans
        else:
            indices = [int(x.strip()) - 1 for x in raw.split(",") if x.strip().isdigit()]
            selected = [plans[i] for i in indices if 0 <= i < len(plans)]

        if not selected:
            print("  Sin selección. Saliendo.")
            return

        # 3. Procesar cada plan
        for plan in selected:
            plan_id = plan["id"]
            plan_title = plan["title"]

            try:
                # Obtener buckets y tasks
                buckets = await list_buckets(client, token, plan_id)
                buckets_dict = {b["id"]: b["name"] for b in buckets}

                tasks = await list_tasks(client, token, plan_id)

                if not tasks:
                    print(f"  ⚠  {plan_title}: sin tareas.")
                    await asyncio.sleep(0.3)
                    continue

                # Pre-fetch checklist paralelo si se solicita (con semáforo para respetar rate limit)
                checklist_map: dict[str, tuple[int, int]] = {}  # task_id → (done, total)
                if fetch_checklist:
                    sem = asyncio.Semaphore(5)

                    async def _fetch_one_checklist(task_id: str) -> tuple[str, int, int]:
                        async with sem:
                            try:
                                details = await get_task_details(client, token, task_id)
                                cl = details.get("checklist", {})
                                total = len(cl)
                                done = sum(1 for v in cl.values() if v.get("isChecked", False))
                                await asyncio.sleep(0.1)
                                return task_id, done, total
                            except (httpx.HTTPStatusError, httpx.RequestError):
                                return task_id, 0, 0

                    results = await asyncio.gather(
                        *[_fetch_one_checklist(t.get("id", "")) for t in tasks]
                    )
                    checklist_map = {tid: (done, total) for tid, done, total in results}

                # Fix 3: Pre-fetch paralelo de commentCount (GET /planner/tasks/{id}?$select=commentCount)
                comment_count_map: dict[str, int] = {}
                sem_cc = asyncio.Semaphore(5)

                async def _fetch_comment_count(task_id: str) -> tuple[str, int]:
                    async with sem_cc:
                        try:
                            t = await graph_request(
                                client,
                                "GET",
                                f"/planner/tasks/{task_id}?$select=commentCount",
                                token,
                            )
                            await asyncio.sleep(0.2)
                            return task_id, t.get("commentCount", 0)
                        except (httpx.HTTPStatusError, httpx.RequestError):
                            return task_id, 0

                cc_results = await asyncio.gather(
                    *[_fetch_comment_count(t.get("id", "")) for t in tasks]
                )
                comment_count_map = {tid: cc for tid, cc in cc_results}

                # Pre-fetch paralelo de nombres de asignados
                all_guids: set[str] = {
                    g for t in tasks for g in t.get("assignments", {}).keys()
                }
                names_map: dict[str, str] = {}
                if all_guids:
                    sem_names = asyncio.Semaphore(5)

                    async def _fetch_one_name(guid: str) -> tuple[str, str | None]:
                        async with sem_names:
                            name = await resolve_guid_to_display_name(client, token, guid)
                            await asyncio.sleep(0.1)
                            return guid, name

                    name_results = await asyncio.gather(
                        *[_fetch_one_name(g) for g in all_guids]
                    )
                    names_map = {g: n for g, n in name_results if n is not None}

                # Enriquecer tareas (igual que en run_report)
                enriched_tasks = []
                for task in tasks:
                    task_id = task.get("id", "")
                    cl_done, cl_total = checklist_map.get(task_id, (0, 0))

                    assignments = task.get("assignments", {})
                    assignee_names = [
                        names_map.get(g, g[:12]) for g in assignments.keys()
                    ]
                    assignee_display = ", ".join(assignee_names)[:40] if assignee_names else "(sin asignar)"

                    enriched_tasks.append({
                        **task,
                        "CommentCount": comment_count_map.get(task_id, 0),  # Fix 3: usar pre-fetch en lugar de campo lista
                        "ChecklistDone": cl_done,
                        "ChecklistTotal": cl_total,
                        "priority": task.get("priority", 5),
                        "AssigneeDisplay": assignee_display,
                    })

                # Generar HTML (para preview o envío)
                report_date = date.today().strftime("%d-%m-%Y")

                # Calcular tareas que vencen en los próximos 7 días
                today = date.today()
                proximas_7d = sum(
                    1 for t in enriched_tasks
                    if t.get("dueDateTime")
                    and t.get("percentComplete", 0) < 100
                    and today <= datetime.fromisoformat(
                        t["dueDateTime"].replace("Z", "+00:00")
                    ).date() <= today + timedelta(days=7)
                )

                html = build_report_html(plan_title, buckets_dict, enriched_tasks, report_date, proximas_7d)
                subject = f"[Planner] Reporte de gestión — {plan_title} ({report_date})"

                # Preview mode: guardar HTML y abrir en navegador (sin enviar correo)
                if preview:
                    slug = re.sub(r"[^\w\-]", "_", plan_title.lower())[:40]
                    out_path = Path("reports") / f"preview_{slug}.html"
                    out_path.parent.mkdir(exist_ok=True)
                    out_path.write_text(html, encoding="utf-8")
                    print(f"  [preview] HTML guardado: {out_path}")
                    webbrowser.open(out_path.resolve().as_uri())
                    await asyncio.sleep(0.3)
                    continue

                # Resolver destinatarios (bypass si to_override activo)
                if to_override:
                    to_emails = [to_override]
                else:
                    # Resolver GUIDs → emails (con cache global)
                    assignee_guids: set[str] = set()
                    for task in enriched_tasks:
                        assignments = task.get("assignments", {})
                        assignee_guids.update(assignments.keys())

                    to_emails: list[str] = []
                    for guid in assignee_guids:
                        email = await resolve_guid_to_email(client, token, guid)
                        if email:
                            to_emails.append(email)

                    if not to_emails:
                        print(f"  ⚠  {plan_title}: sin asignados con email. Correo no enviado.")
                        await asyncio.sleep(0.3)
                        continue

                # Enviar correo (modo normal o to_override)
                await send_mail_report(client, token, to_emails, subject, html)
                print(f"  ✉  {plan_title}: correo enviado a {len(to_emails)} destinatario(s).")

                await asyncio.sleep(0.3)
            except httpx.HTTPStatusError as exc:
                print(f"  ✗ Error Graph al procesar '{plan_title}': {exc.response.status_code}")
            except httpx.RequestError as exc:
                print(f"  ✗ Error de red al procesar '{plan_title}': {exc}")
            except ValueError as exc:
                print(f"  ✗ Error de validación en '{plan_title}': {exc}")


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    parser = argparse.ArgumentParser(description="Importar CSV a Microsoft Planner")
    parser.add_argument("--csv", type=Path, default=CSV_PATH, help="Ruta al CSV")
    parser.add_argument("--group-id", default=GROUP_ID, help="Object ID del grupo M365")
    parser.add_argument("--dry-run", action="store_true", help="Simula sin llamar a la API")
    parser.add_argument(
        "--mode",
        choices=["full", "plan", "buckets", "tasks", "list", "delete", "sp-list", "report", "email-report"],
        default="full",
        help="Modo: full (default), plan, buckets, tasks, list, delete, sp-list, report o email-report",
    )
    parser.add_argument(
        "--filter", dest="filter_text", default="", help="Filtrar por título/nombre (modos list/delete/sp-list/report)"
    )
    parser.add_argument(
        "--site-url",
        default=SHAREPOINT_SITE_URL,
        help="URL del sitio SharePoint (default: SHAREPOINT_SITE_URL)",
    )
    parser.add_argument(
        "--folder",
        default="",
        help="Subcarpeta dentro de la librería (ej: 'Proyectos/2026'). Vacío = raíz.",
    )
    parser.add_argument(
        "--export", type=Path, default=None,
        help="CSV de salida para el modo report",
    )
    parser.add_argument(
        "--comments", action="store_true", dest="fetch_comments",
        help="En modo report: obtiene el último comentario por tarea. 1 llamada Graph extra por tarea.",
    )
    parser.add_argument(
        "--checklist", action="store_true", dest="fetch_checklist",
        help="report/email-report: muestra contador de checklist (x/y). 1 llamada Graph extra por tarea.",
    )
    parser.add_argument(
        "--preview",
        action="store_true",
        help="email-report: guarda HTML en reports/ y abre en navegador. No envía correo.",
    )
    parser.add_argument(
        "--to",
        dest="to_override",
        default="",
        metavar="EMAIL",
        help="email-report: enviar sólo a este email (bypass de asignados).",
    )
    args = parser.parse_args()

    if args.mode == "report":
        asyncio.run(run_report(
            args.group_id,
            args.filter_text or "",
            args.export,
            args.fetch_comments,
            args.fetch_checklist,
        ))
        return

    if args.mode == "email-report":
        asyncio.run(run_email_report(
            args.group_id,
            args.filter_text or "",
            preview=args.preview,
            to_override=args.to_override,
            fetch_checklist=args.fetch_checklist,
        ))
        return

    if args.mode == "list":
        asyncio.run(run_list(args.group_id, args.filter_text))
        return

    if args.mode == "sp-list":
        asyncio.run(run_sp_list(args.site_url, args.folder, args.filter_text))
        return

    if args.mode == "delete":
        res = asyncio.run(run_delete(args.group_id, args.filter_text, args.dry_run))
        print(f"\nEliminados : {len(res['deleted'])}")
        if res["errors"]:
            for e in res["errors"]:
                print(f"  ✗ {e}")
        return

    if args.mode == "full":
        result = asyncio.run(run_import_full(args.csv, args.group_id, args.dry_run))
    elif args.mode == "plan":
        result = asyncio.run(run_import_plan(args.csv, args.group_id, args.dry_run))
    elif args.mode == "buckets":
        result = asyncio.run(run_import_buckets(args.csv, args.dry_run))
    elif args.mode == "tasks":
        result = asyncio.run(run_import_tasks(args.csv, args.dry_run))

    print()
    print("── RESUMEN ──────────────────────────────")
    if result.dry_run:
        print("Modo      : Simulación — sin cambios en Planner")
        if result.plan_name:
            print(f"Plan      : '{result.plan_name}'")
        if result.buckets_total:
            print(f"Buckets   : {result.buckets_total}")
        if result.tasks_total:
            print(f"Tareas    : {result.tasks_total}")
    else:
        print(f"Plan ID   : {result.plan_id or '(sin ID)'}")
        print(f"Buckets   : {len(result.bucket_ids)}")
        print(f"Tareas OK : {len(result.task_ids)}")
        print(f"GUIDs OK  : {result.guids_resolved}")
        if result.guids_failed:
            print(f"GUIDs FAIL: {len(result.guids_failed)} — {result.guids_failed}")
        if result.tasks_unassigned:
            print(f"Sin asignar: {result.tasks_unassigned}")
        if result.errors:
            print(f"Errores   : {len(result.errors)}")
            for e in result.errors:
                print(f"  {e}")
    print("─────────────────────────────────────────")


if __name__ == "__main__":
    main()
