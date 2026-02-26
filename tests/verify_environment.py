"""verify_environment.py — Verificación de integración real del entorno de proyecto.

Script standalone (NO es un test de pytest). Requiere credenciales reales
(.env del MCP activo). Verifica 8 recursos via Graph API por proyecto.

Uso:
    python tests/verify_environment.py
    python tests/verify_environment.py --config path/cfg.json
    python tests/verify_environment.py --project-id PRJ-TEST-001
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any

# Bootstrap: raíz del proyecto al path antes de importar planner_import
PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import httpx  # noqa: E402

import planner_import  # noqa: F401, E402 — activa dotenv + auth setup al importar
from planner_import import (  # noqa: E402
    MicrosoftAuthManager,
    Settings,
    SHAREPOINT_SITE_URL,
    get_site_id,
    graph_request,
)

# ── Constantes ────────────────────────────────────────────────────────────────

CHECKS = [
    "Canal Teams",
    "Miembros canal",
    "Plan Planner",
    "Buckets del plan",
    "Carpeta SharePoint",
    "Subcarpetas SP",
    "Templates en 01_INICIO",
    "_AYUDA_PM",
]

DEFAULT_CONFIG_PATH = Path("project_config.json")


# ── Verificaciones individuales ───────────────────────────────────────────────

async def verify_project(
    client: httpx.AsyncClient,
    token: str,
    project_id: str,
    entry: dict[str, Any],
    site_id: str,
) -> dict[str, tuple[str, str]]:
    """Verifica los 8 recursos del entorno para un proyecto.

    Devuelve {nombre_check: (símbolo, detalle)} — símbolo es '✓' o '✗'.
    Nunca lanza excepción: los errores quedan capturados en el resultado.
    """
    results: dict[str, tuple[str, str]] = {}

    group_id: str = entry.get("group_id", "")
    channel_id: str = entry.get("channel_id", "")
    plan_id: str = entry.get("plan_id", "")
    folder_id: str = entry.get("folder_id", "")
    subfolder_ids: dict[str, str] = entry.get("subfolder_ids", {})

    # 1. Canal Teams — GET /teams/{group_id}/channels/{channel_id}
    if channel_id:
        try:
            data = await graph_request(
                client, "GET", f"/teams/{group_id}/channels/{channel_id}", token
            )
            results["Canal Teams"] = ("✓", data.get("displayName", "OK"))
        except Exception as exc:
            results["Canal Teams"] = ("✗", f"{type(exc).__name__}: {exc}")
    else:
        results["Canal Teams"] = ("✗", "channel_id no encontrado en config")

    # 2. Miembros canal — GET /teams/{group_id}/channels/{channel_id}/members
    if channel_id:
        try:
            data = await graph_request(
                client, "GET",
                f"/teams/{group_id}/channels/{channel_id}/members", token,
            )
            members = data.get("value", [])
            results["Miembros canal"] = ("✓", f"{len(members)} miembro(s)")
        except Exception as exc:
            results["Miembros canal"] = ("✗", f"{type(exc).__name__}: {exc}")
    else:
        results["Miembros canal"] = ("✗", "channel_id no encontrado en config")

    # 3. Plan Planner — GET /planner/plans/{plan_id}
    if plan_id:
        try:
            data = await graph_request(client, "GET", f"/planner/plans/{plan_id}", token)
            results["Plan Planner"] = ("✓", data.get("title", "OK"))
        except Exception as exc:
            results["Plan Planner"] = ("✗", f"{type(exc).__name__}: {exc}")
    else:
        results["Plan Planner"] = ("✗", "plan_id no encontrado en config")

    # 4. Buckets — GET /planner/plans/{plan_id}/buckets
    if plan_id:
        try:
            data = await graph_request(
                client, "GET", f"/planner/plans/{plan_id}/buckets", token
            )
            count = len(data.get("value", []))
            results["Buckets del plan"] = (
                "✓" if count > 0 else "✗",
                f"{count} bucket(s)",
            )
        except Exception as exc:
            results["Buckets del plan"] = ("✗", f"{type(exc).__name__}: {exc}")
    else:
        results["Buckets del plan"] = ("✗", "plan_id no encontrado en config")

    # 5. Carpeta SharePoint — GET /sites/{site_id}/drive/items/{folder_id}
    if folder_id:
        try:
            data = await graph_request(
                client, "GET", f"/sites/{site_id}/drive/items/{folder_id}", token
            )
            results["Carpeta SharePoint"] = ("✓", data.get("name", "OK"))
        except Exception as exc:
            results["Carpeta SharePoint"] = ("✗", f"{type(exc).__name__}: {exc}")
    else:
        results["Carpeta SharePoint"] = ("✗", "folder_id no encontrado en config")

    # 6. Subcarpetas SP — GET /sites/{site_id}/drive/items/{folder_id}/children
    if folder_id:
        try:
            data = await graph_request(
                client, "GET",
                f"/sites/{site_id}/drive/items/{folder_id}/children", token,
            )
            count = len(data.get("value", []))
            results["Subcarpetas SP"] = (
                "✓" if count >= 5 else "✗",
                f"{count} subcarpeta(s)",
            )
        except Exception as exc:
            results["Subcarpetas SP"] = ("✗", f"{type(exc).__name__}: {exc}")
    else:
        results["Subcarpetas SP"] = ("✗", "folder_id no encontrado en config")

    # 7. Templates en 01_INICIO — GET /sites/{site_id}/drive/items/{inicio_id}/children
    inicio_id = subfolder_ids.get("01_INICIO", "")
    if inicio_id:
        try:
            data = await graph_request(
                client, "GET",
                f"/sites/{site_id}/drive/items/{inicio_id}/children", token,
            )
            docx_files = [
                f for f in data.get("value", []) if f.get("name", "").endswith(".docx")
            ]
            count = len(docx_files)
            results["Templates en 01_INICIO"] = (
                "✓" if count >= 2 else "✗",
                f"{count} .docx",
            )
        except Exception as exc:
            results["Templates en 01_INICIO"] = ("✗", f"{type(exc).__name__}: {exc}")
    else:
        results["Templates en 01_INICIO"] = (
            "✗", "01_INICIO no encontrado en subfolder_ids"
        )

    # 8. _AYUDA_PM — GET /sites/{site_id}/drive/root:/_AYUDA_PM
    try:
        await graph_request(
            client, "GET", f"/sites/{site_id}/drive/root:/_AYUDA_PM", token
        )
        results["_AYUDA_PM"] = ("✓", "200 OK")
    except Exception as exc:
        results["_AYUDA_PM"] = ("✗", f"{type(exc).__name__}: {exc}")

    return results


# ── Salida ────────────────────────────────────────────────────────────────────

def _print_table(project_id: str, results: dict[str, tuple[str, str]]) -> int:
    """Imprime tabla ASCII con el resultado de cada check. Devuelve conteo de ✓."""
    print(f"\n{'─' * 62}")
    print(f"Proyecto: {project_id}")
    print(f"{'─' * 62}")
    ok_count = 0
    for check in CHECKS:
        status, detail = results.get(check, ("?", "sin resultado"))
        print(f"  {status}  {check:<35}  {detail}")
        if status == "✓":
            ok_count += 1
    print(f"{'─' * 62}")
    print(f"Resultado: {ok_count}/{len(CHECKS)} ✓")
    return ok_count


# ── Orquestador ───────────────────────────────────────────────────────────────

async def _run(config_path: Path, project_id_filter: str | None) -> int:
    """Ejecuta la verificación. Devuelve 0 si todo OK, 1 si hay fallos."""
    if not config_path.exists():
        print(f"[ERROR] Config no encontrada: {config_path}", file=sys.stderr)
        return 1

    config: dict[str, Any] = json.loads(config_path.read_text(encoding="utf-8"))

    if project_id_filter:
        if project_id_filter not in config:
            print(
                f"[ERROR] Proyecto '{project_id_filter}' no encontrado en {config_path}",
                file=sys.stderr,
            )
            return 1
        projects_to_verify: dict[str, Any] = {project_id_filter: config[project_id_filter]}
    else:
        projects_to_verify = config

    if not projects_to_verify:
        print("[WARN] No hay proyectos en la config para verificar")
        return 0

    settings = Settings()
    auth = MicrosoftAuthManager(
        tenant_id=settings.azure_tenant_id,
        client_id=settings.azure_client_id,
        client_secret=settings.azure_client_secret,
    )

    total_ok = 0
    total_checks = 0

    async with httpx.AsyncClient(timeout=30.0) as client:
        token = auth.get_token()

        print("Obteniendo site_id de SharePoint...")
        site_id = await get_site_id(client, token, SHAREPOINT_SITE_URL)
        print(f"  site_id: {site_id}")

        for proj_id, entry in projects_to_verify.items():
            results = await verify_project(client, token, proj_id, entry, site_id)
            ok_count = _print_table(proj_id, results)
            total_ok += ok_count
            total_checks += len(CHECKS)

    print(f"\n{'=' * 62}")
    print(f"TOTAL: {total_ok}/{total_checks} verificaciones ✓")
    print(f"{'=' * 62}")

    return 0 if total_ok == total_checks else 1


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Verificación de integración real — entorno de proyecto "
            "en Teams + SharePoint + Planner"
        )
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG_PATH,
        help=f"Ruta al project_config.json (default: {DEFAULT_CONFIG_PATH})",
    )
    parser.add_argument(
        "--project-id",
        dest="project_id",
        default=None,
        help="Verificar solo un proyecto específico por ProjectID",
    )
    args = parser.parse_args()

    exit_code = asyncio.run(_run(args.config, args.project_id))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
