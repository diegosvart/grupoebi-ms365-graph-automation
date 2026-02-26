"""
create_environment.py — Etapa 1: Crear entorno de proyecto en Teams + SharePoint + Planner.

Orquesta:
  - Teams: crear canal estándar, agregar PM y Líder como Owners, anclar tab Planner
  - Planner: crear plan + buckets + tareas (reutiliza planner_import.py)
  - SharePoint: crear carpeta de proyecto + 5 subcarpetas + subir 2 plantillas + _AYUDA_PM
  - Persistencia: guardar project_config.json con IDs y URLs del entorno

Uso:
  python create_environment.py --csv templates/default_init/csv1_template.csv [--dry-run]
  python create_environment.py --csv <ruta> --group-id <guid>
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import json
import sys
from pathlib import Path
from typing import Any

import httpx

# ── Importar funciones reutilizables de planner_import ────────────────────────
# El bloque MCP path + dotenv + auth se ejecuta al importar el módulo.
import planner_import as _pi
from planner_import import (
    GROUP_ID,
    GRAPH_BASE,
    SHAREPOINT_SITE_URL,
    MicrosoftAuthManager,
    Settings,
    create_bucket,
    create_plan,
    configure_plan_labels,
    create_task_full,
    extract_ordered_unique,
    get_site_id,
    graph_request,
    parse_csv,
    resolve_email_to_guid,
)

# ── Constantes ────────────────────────────────────────────────────────────────
PROJECT_CONFIG_PATH = Path("project_config.json")

SUBCARPETAS = ["01_INICIO", "02_PLANIFICACION", "03_EJECUCION", "04_CONTROL", "05_CIERRE"]
HELP_DIR_NAME = "_AYUDA_PM"

TEMPLATES_DIR = Path(__file__).parent / "templates" / "default_init"
TEMPLATE_FICHA = TEMPLATES_DIR / "Ficha_de_Proyecto_Nueva_Iniciativa.docx"
TEMPLATE_ACTA = TEMPLATES_DIR / "Acta_de_Inicio_de_Proyecto.docx"


# ── Parsing CSV1 ──────────────────────────────────────────────────────────────

def parse_csv1(path: Path) -> list[dict[str, Any]]:
    """Lee CSV1 (delimitador ';', UTF-8 BOM) con columnas de entorno de proyecto.

    Columnas requeridas: ProjectID, ProjectName, PMEmail, LiderEmail, StartDate, PlannerCSV
    """
    projects: list[dict[str, Any]] = []
    with path.open(encoding="utf-8-sig") as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            projects.append({
                "project_id":   row["ProjectID"].strip(),
                "project_name": row["ProjectName"].strip(),
                "pm_email":     row["PMEmail"].strip(),
                "lider_email":  row["LiderEmail"].strip(),
                "start_date":   row["StartDate"].strip(),
                "planner_csv":  Path(row["PlannerCSV"].strip()),
            })
    return projects


# ── Graph API — upload binario ────────────────────────────────────────────────

async def graph_request_bytes(
    client: httpx.AsyncClient,
    method: str,
    endpoint: str,
    token: str,
    data: bytes,
    content_type: str = "application/octet-stream",
) -> Any:
    """PUT/POST con body binario (upload de archivos a SharePoint).

    Maneja throttling 429 con Retry-After igual que graph_request().
    No acepta JSON — usa content= para bytes.
    """
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": content_type,
    }
    for attempt in range(3):
        resp = await client.request(
            method,
            f"{GRAPH_BASE}{endpoint}",
            headers=headers,
            content=data,
        )
        if resp.status_code == 429:
            wait = int(resp.headers.get("Retry-After", 60))
            print(f"      [throttle] esperando {wait}s...")
            await asyncio.sleep(wait)
            continue
        resp.raise_for_status()
        return resp.json()

    raise RuntimeError(f"Máximo de reintentos para {method} {endpoint}")


# ── Teams ─────────────────────────────────────────────────────────────────────

async def create_team_channel(
    client: httpx.AsyncClient,
    token: str,
    group_id: str,
    name: str,
) -> dict[str, Any]:
    """POST /teams/{groupId}/channels — crea canal estándar.

    Permiso requerido: ChannelSettings.ReadWrite.All (aplicación)
    Devuelve dict con al menos: id, webUrl
    """
    return await graph_request(
        client, "POST", f"/teams/{group_id}/channels", token,
        json={"displayName": name[:50], "membershipType": "standard"},
    )


async def get_channel_by_name(
    client: httpx.AsyncClient,
    token: str,
    group_id: str,
    name: str,
) -> tuple[str, str]:
    """GET /teams/{groupId}/channels — busca canal por displayName.

    Devuelve (channel_id, webUrl) o ("", "") si no se encuentra.
    Usado para recuperar el ID de un canal ya existente tras 400/409.
    Permiso requerido: ChannelSettings.ReadWrite.All (aplicación)
    """
    data = await graph_request(client, "GET", f"/teams/{group_id}/channels", token)
    display_name = name[:50]
    for ch in data.get("value", []):
        if ch.get("displayName") == display_name:
            return ch["id"], ch.get("webUrl", "")
    return "", ""


async def add_channel_member(
    client: httpx.AsyncClient,
    token: str,
    group_id: str,
    channel_id: str,
    user_id: str,
    role: str = "owner",
) -> None:
    """POST /teams/{groupId}/channels/{channelId}/members — agrega usuario con rol dado.

    Solo válido para canales privados o compartidos. Para canales estándar usar add_team_member.
    Permiso requerido: ChannelMember.ReadWrite.All (aplicación)
    role: "owner" o "" (miembro normal)
    """
    roles = [role] if role else []
    await graph_request(
        client, "POST",
        f"/teams/{group_id}/channels/{channel_id}/members", token,
        json={
            "@odata.type": "#microsoft.graph.aadUserConversationMember",
            "roles": roles,
            "user@odata.bind": f"https://graph.microsoft.com/v1.0/users/{user_id}",
        },
    )


async def add_team_member(
    client: httpx.AsyncClient,
    token: str,
    group_id: str,
    user_id: str,
    role: str = "owner",
) -> None:
    """POST /teams/{groupId}/members — agrega usuario al equipo con rol dado.

    Correcto para canales estándar (la membresía se hereda del equipo).
    Permiso requerido: TeamMember.ReadWrite.All (aplicación)
    role: "owner" o "" (miembro normal)
    """
    roles = [role] if role else []
    await graph_request(
        client, "POST",
        f"/teams/{group_id}/members", token,
        json={
            "@odata.type": "#microsoft.graph.aadUserConversationMember",
            "roles": roles,
            "user@odata.bind": f"https://graph.microsoft.com/v1.0/users/{user_id}",
        },
    )


async def add_planner_tab(
    client: httpx.AsyncClient,
    token: str,
    group_id: str,
    channel_id: str,
    plan_id: str,
    tenant_id: str,
) -> dict[str, Any]:
    """POST /teams/{groupId}/channels/{channelId}/tabs — ancla tab Planner al canal.

    Permiso requerido: TeamsTab.ReadWrite.All (aplicación)
    {loginHint} es literal en la URL — Teams lo reemplaza en runtime.
    """
    content_url = (
        f"https://tasks.office.com/{tenant_id}/Home/PlannerFrame"
        f"?page=7&auth_pvr=Orgid&auth_upn={{loginHint}}"
        f"&groupId={group_id}&planId={plan_id}&taskId=&hideNav=true"
    )
    website_url = f"https://tasks.office.com/{tenant_id}/Home/PlanViews/{plan_id}"

    return await graph_request(
        client, "POST",
        f"/teams/{group_id}/channels/{channel_id}/tabs", token,
        json={
            "displayName": "Planner",
            "teamsApp@odata.bind": (
                "https://graph.microsoft.com/v1.0/appCatalogs/teamsApps/"
                "com.microsoft.teamspace.tab.planner"
            ),
            "configuration": {
                "entityId": plan_id,
                "contentUrl": content_url,
                "websiteUrl": website_url,
                "removeUrl": None,
            },
        },
    )


# ── SharePoint ────────────────────────────────────────────────────────────────

async def create_sp_folder(
    client: httpx.AsyncClient,
    token: str,
    site_id: str,
    parent_id: str,
    name: str,
) -> dict[str, Any]:
    """POST /sites/{siteId}/drive/items/{parentId}/children — crea carpeta.

    conflictBehavior: fail → lanza 409 si la carpeta ya existe.
    Permiso requerido: Files.ReadWrite.All (aplicación)
    """
    return await graph_request(
        client, "POST",
        f"/sites/{site_id}/drive/items/{parent_id}/children", token,
        json={
            "name": name,
            "folder": {},
            "@microsoft.graph.conflictBehavior": "fail",
        },
    )


async def upload_file(
    client: httpx.AsyncClient,
    token: str,
    site_id: str,
    folder_id: str,
    local_path: Path,
) -> dict[str, Any]:
    """PUT /sites/{siteId}/drive/items/{folderId}:/{filename}:/content — sube archivo.

    Lee bytes desde local_path y los envía como application/octet-stream.
    Permiso requerido: Files.ReadWrite.All (aplicación)
    """
    file_bytes = local_path.read_bytes()
    filename = local_path.name
    return await graph_request_bytes(
        client, "PUT",
        f"/sites/{site_id}/drive/items/{folder_id}:/{filename}:/content",
        token, data=file_bytes,
    )


async def ensure_help_dir(
    client: httpx.AsyncClient,
    token: str,
    site_id: str,
    root_id: str,
) -> str:
    """Crea _AYUDA_PM en la raíz si no existe. Devuelve folder_id. Idempotente.

    GET /sites/{siteId}/drive/root:/{name} → si 404 → POST crear carpeta.
    """
    try:
        data = await graph_request(
            client, "GET",
            f"/sites/{site_id}/drive/root:/{HELP_DIR_NAME}", token,
        )
        print(f"      [skip] '{HELP_DIR_NAME}' ya existe → {data['id']}")
        return data["id"]
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            folder = await create_sp_folder(client, token, site_id, root_id, HELP_DIR_NAME)
            print(f"      ✓ '{HELP_DIR_NAME}' creada → {folder['id']}")
            return folder["id"]
        raise


# ── Persistencia ──────────────────────────────────────────────────────────────

def load_project_config() -> dict[str, Any]:
    """Lee project_config.json si existe; devuelve {} si no."""
    if PROJECT_CONFIG_PATH.exists():
        return json.loads(PROJECT_CONFIG_PATH.read_text(encoding="utf-8"))
    return {}


def save_project_config(config: dict[str, Any]) -> None:
    """Escribe project_config.json (UTF-8, indentado). Sobrescribe el archivo completo."""
    PROJECT_CONFIG_PATH.write_text(
        json.dumps(config, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


# ── Orquestador ───────────────────────────────────────────────────────────────

async def run_create_environment(
    csv_path: Path,
    group_id: str,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Etapa 1: para cada proyecto en CSV1 crea canal Teams + Planner + carpetas SharePoint.

    Maneja 409 (recursos ya existentes) como idempotente en todos los pasos.
    Refresca token antes de bloques de operaciones pesadas (scripts > 1h).
    Persiste project_config.json tras cada proyecto (tolerante a interrupciones).
    """
    projects = parse_csv1(csv_path)
    print(f"Proyectos encontrados: {len(projects)}")

    if dry_run:
        print("\n[DRY RUN] Plan de acción (sin llamadas a Graph API):\n")
        for proj in projects:
            print(f"  Proyecto   : {proj['project_id']} — {proj['project_name']}")
            print(f"  PM Email   : {proj['pm_email']}")
            print(f"  Líder Email: {proj['lider_email']}")
            print(f"  CSV Plan   : {proj['planner_csv']}")
            print(f"  Canal Teams: '{proj['project_name'][:50]}' (standard) en grupo {group_id}")
            folder_name = f"{proj['project_id']}_{proj['project_name']}"
            print(f"  Carpeta SP : {folder_name}")
            print(f"  Subcarpetas: {', '.join(SUBCARPETAS)}")
            print(f"  Templates  : {TEMPLATE_FICHA.name}, {TEMPLATE_ACTA.name}")
            print()
        return {}

    settings = Settings()
    auth = MicrosoftAuthManager(
        tenant_id=settings.azure_tenant_id,
        client_id=settings.azure_client_id,
        client_secret=settings.azure_client_secret,
    )
    tenant_id: str = settings.azure_tenant_id

    config = load_project_config()

    async with httpx.AsyncClient(timeout=30.0) as client:

        # ── Preparación global (una vez por ejecución) ─────────────────────────
        token = auth.get_token()

        print("Obteniendo site_id de SharePoint...")
        site_id = await get_site_id(client, token, SHAREPOINT_SITE_URL)
        print(f"  site_id: {site_id}")

        root_data = await graph_request(client, "GET", f"/sites/{site_id}/drive/root", token)
        root_id: str = root_data["id"]
        print(f"  root_id: {root_id}")

        print("\n  Verificando directorio _AYUDA_PM (idempotente)...")
        await ensure_help_dir(client, token, site_id, root_id)

        # ── Procesamiento por proyecto ─────────────────────────────────────────
        for proj_idx, proj in enumerate(projects, 1):
            print(f"\n{'='*60}")
            print(f"[{proj_idx}/{len(projects)}] {proj['project_id']} — {proj['project_name']}")
            print(f"{'='*60}")

            # Refrescar token al inicio de cada proyecto (scripts largos)
            token = auth.get_token()

            project_entry: dict[str, Any] = {
                "group_id": group_id,
                "status": "pending_activation",
            }

            # ── [RESOLVE] ──────────────────────────────────────────────────────
            print("\n  [RESOLVE] Resolviendo emails a GUIDs...")
            guid_cache: dict[str, str | None] = {}
            pm_guid = await resolve_email_to_guid(client, token, proj["pm_email"], guid_cache)
            lider_guid = await resolve_email_to_guid(client, token, proj["lider_email"], guid_cache)

            if pm_guid:
                print(f"    PM    : {proj['pm_email']} → {pm_guid}")
            else:
                print(f"    [WARN] PM email no resuelto: {proj['pm_email']}")
            if lider_guid:
                print(f"    Líder : {proj['lider_email']} → {lider_guid}")
            else:
                print(f"    [WARN] Líder email no resuelto: {proj['lider_email']}")

            # ── [TEAMS — Canal] ────────────────────────────────────────────────
            print("\n  [TEAMS] Creando canal de proyecto...")
            channel_id = ""
            channel_url = ""
            try:
                channel = await create_team_channel(client, token, group_id, proj["project_name"])
                channel_id = channel["id"]
                channel_url = channel.get("webUrl", "")
                print(f"    channel_id : {channel_id}")
                print(f"    channel_url: {channel_url}")
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 404:
                    raise RuntimeError(
                        f"El grupo '{group_id}' no tiene Teams habilitado. "
                        "Ejecuta PUT /groups/{group_id}/team para habilitarlo "
                        "y vuelve a ejecutar el script."
                    ) from exc
                elif exc.response.status_code in (400, 409):
                    print(f"    [skip] Canal ya existe ({exc.response.status_code}) — recuperando ID...")
                    channel_id, channel_url = await get_channel_by_name(
                        client, token, group_id, proj["project_name"]
                    )
                    if channel_id:
                        print(f"    channel_id (existing): {channel_id}")
                        print(f"    channel_url          : {channel_url}")
                    else:
                        print(f"    [WARN] No se pudo recuperar channel_id del canal existente")
                else:
                    raise
            print("    [wait] Esperando 60s para propagación del canal en Teams...")
            await asyncio.sleep(60)

            project_entry["channel_id"] = channel_id
            project_entry["channel_url"] = channel_url

            # ── [TEAMS — Members] ──────────────────────────────────────────────
            if channel_id:
                print("\n  [TEAMS] Agregando PM y Líder como Owners...")
                for role_label, user_guid, user_email in [
                    ("PM",    pm_guid,    proj["pm_email"]),
                    ("Líder", lider_guid, proj["lider_email"]),
                ]:
                    if not user_guid:
                        print(f"    [skip] {role_label} sin GUID — no se puede agregar")
                        continue
                    try:
                        await add_team_member(client, token, group_id, user_guid, "owner")
                        print(f"    ✓ {role_label} {user_email}")
                    except httpx.HTTPStatusError as exc:
                        if exc.response.status_code == 409:
                            print(f"    [skip] {role_label} ya es miembro (409)")
                        else:
                            raise
                    await asyncio.sleep(0.5)

            # ── [PLANNER] ──────────────────────────────────────────────────────
            print(f"\n  [PLANNER] Importando desde {proj['planner_csv']}...")
            tasks, date_warnings = parse_csv(proj["planner_csv"])
            for w in date_warnings:
                print(f"    {w}")

            buckets_ordered = extract_ordered_unique(tasks, "bucket_name")
            all_labels = extract_ordered_unique(
                [{"labels_raw": lbl}
                 for t in tasks
                 for lbl in t["labels_raw"].split(";")
                 if lbl.strip()],
                "labels_raw",
            )

            # Limpiar LABEL_MAP global antes de configurar nuevas categorías
            _pi.LABEL_MAP.clear()

            token = auth.get_token()  # Refrescar antes del bloque de Planner
            print(f"    Creando plan '{proj['project_name']}'...")
            plan = await create_plan(client, token, group_id, proj["project_name"])
            plan_id: str = plan["id"]
            print(f"    plan_id: {plan_id}")
            await asyncio.sleep(2)

            print(f"    Configurando labels: {all_labels}")
            await configure_plan_labels(client, token, plan_id, all_labels)

            bucket_ids: dict[str, str] = {}
            print(f"    Creando {len(buckets_ordered)} buckets...")
            for bucket_name in buckets_ordered:
                bucket = await create_bucket(client, token, plan_id, bucket_name)
                bucket_ids[bucket_name] = bucket["id"]
                print(f"      ✓ '{bucket_name}'")
                await asyncio.sleep(0.5)

            task_ids: list[str] = []
            task_guid_cache: dict[str, str | None] = {}
            print(f"    Creando {len(tasks)} tareas...")
            for i, task in enumerate(tasks, 1):
                try:
                    email = task.get("assignee_email", "")
                    assignee_guid = (
                        await resolve_email_to_guid(client, token, email, task_guid_cache)
                        if email else None
                    )
                    bucket_id = bucket_ids[task["bucket_name"]]
                    task_id = await create_task_full(
                        client, token, plan_id, bucket_id, task, assignee_guid
                    )
                    task_ids.append(task_id)
                    print(f"      [{i:02d}/{len(tasks)}] ✓ {task['title']}")
                    await asyncio.sleep(0.3)
                except Exception as exc:
                    print(f"      [{i:02d}/{len(tasks)}] ✗ '{task['title']}': {exc}")

            plan_url = f"https://tasks.office.com/{tenant_id}/Home/PlanViews/{plan_id}"
            project_entry["plan_id"] = plan_id
            project_entry["plan_url"] = plan_url
            project_entry["bucket_ids"] = bucket_ids
            project_entry["task_count"] = len(task_ids)

            # ── [TEAMS — Tab Planner] ──────────────────────────────────────────
            if channel_id and plan_id:
                print("\n  [TEAMS] Anclando tab Planner al canal...")
                try:
                    tab = await add_planner_tab(
                        client, token, group_id, channel_id, plan_id, tenant_id
                    )
                    tab_id = tab.get("id", "")
                    print(f"    tab_id: {tab_id}")
                    project_entry["tab_id"] = tab_id
                except httpx.HTTPStatusError as exc:
                    if exc.response.status_code == 409:
                        print(f"    [skip] Tab Planner ya existe (409)")
                    else:
                        print(f"    [WARN] No se pudo anclar tab Planner: {exc}")
                await asyncio.sleep(0.5)

            # ── [SHAREPOINT — Carpetas] ────────────────────────────────────────
            print("\n  [SHAREPOINT] Creando carpetas de proyecto...")
            folder_name = f"{proj['project_id']}_{proj['project_name']}"
            folder_id = ""
            folder_url = ""

            try:
                proj_folder = await create_sp_folder(client, token, site_id, root_id, folder_name)
                folder_id = proj_folder["id"]
                folder_url = proj_folder.get("webUrl", "")
                print(f"    ✓ Carpeta principal: {folder_name}")
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 409:
                    print(f"    [skip] Carpeta '{folder_name}' ya existe (409)")
                else:
                    raise

            project_entry["folder_id"] = folder_id
            project_entry["folder_url"] = folder_url

            subfolder_ids: dict[str, str] = {}
            inicio_folder_id = ""

            if folder_id:
                for sub in SUBCARPETAS:
                    try:
                        sf = await create_sp_folder(client, token, site_id, folder_id, sub)
                        subfolder_ids[sub] = sf["id"]
                        if sub == "01_INICIO":
                            inicio_folder_id = sf["id"]
                        print(f"    ✓ Subcarpeta: {sub}")
                    except httpx.HTTPStatusError as exc:
                        if exc.response.status_code == 409:
                            print(f"    [skip] Subcarpeta '{sub}' ya existe (409)")
                        else:
                            raise
                    await asyncio.sleep(0.3)

            project_entry["subfolder_ids"] = subfolder_ids

            # ── [SHAREPOINT — Upload plantillas] ──────────────────────────────
            if inicio_folder_id:
                print("\n  [SHAREPOINT] Subiendo plantillas a 01_INICIO...")
                token = auth.get_token()  # Refrescar antes del upload
                for template in [TEMPLATE_FICHA, TEMPLATE_ACTA]:
                    if not template.exists():
                        print(f"    [WARN] Plantilla no encontrada: {template}")
                        continue
                    try:
                        await upload_file(client, token, site_id, inicio_folder_id, template)
                        print(f"    ✓ {template.name}")
                    except Exception as exc:
                        print(f"    [WARN] Error subiendo '{template.name}': {exc}")
                    await asyncio.sleep(0.5)

            # ── [PERSISTENCIA] ────────────────────────────────────────────────
            config[proj["project_id"]] = project_entry
            save_project_config(config)
            print(f"\n  ✓ '{proj['project_id']}' guardado en project_config.json")

    print(f"\n{'='*60}")
    print(f"Entornos creados: {len(projects)}")
    print(f"Config guardada en: {PROJECT_CONFIG_PATH.resolve()}")
    print(f"{'='*60}")
    return config


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(
        description="Etapa 1 — Crear entorno de proyecto: canal Teams + Planner + carpetas SharePoint"
    )
    parser.add_argument(
        "--csv", required=True, type=Path,
        help="Ruta al CSV1 de proyectos (campos: ProjectID, ProjectName, PMEmail, LiderEmail, StartDate, PlannerCSV)",
    )
    parser.add_argument(
        "--group-id", default=GROUP_ID,
        help=f"Group ID del equipo Teams/Planner (default: {GROUP_ID})",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Simula sin llamar a la API — parsea CSV y muestra plan de acción",
    )
    args = parser.parse_args()

    print("-" * 41)
    print("  create_environment.py -- Etapa 1")
    print("-" * 41)
    print(f"CSV      : {args.csv}")
    print(f"Group ID : {args.group_id}")
    if args.dry_run:
        print("Modo     : Simulación — sin llamadas a Graph API")
    print()

    asyncio.run(run_create_environment(args.csv, args.group_id, args.dry_run))


if __name__ == "__main__":
    main()
