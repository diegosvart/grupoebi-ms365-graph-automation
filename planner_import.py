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
import sys
import uuid
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

# Se construye en runtime por configure_plan_labels(): {"TI": "category1", ...}
LABEL_MAP: dict[str, str] = {}


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


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    parser = argparse.ArgumentParser(description="Importar CSV a Microsoft Planner")
    parser.add_argument("--csv", type=Path, default=CSV_PATH, help="Ruta al CSV")
    parser.add_argument("--group-id", default=GROUP_ID, help="Object ID del grupo M365")
    parser.add_argument("--dry-run", action="store_true", help="Simula sin llamar a la API")
    parser.add_argument(
        "--mode",
        choices=["full", "plan", "buckets", "tasks", "list", "delete", "sp-list"],
        default="full",
        help="Modo: full (default), plan, buckets, tasks, list, delete o sp-list",
    )
    parser.add_argument(
        "--filter", dest="filter_text", default="", help="Filtrar por título/nombre (modos list/delete/sp-list)"
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
    args = parser.parse_args()

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
