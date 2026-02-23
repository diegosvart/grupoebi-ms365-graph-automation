# Planner Import Script

## Stack
Python 3.14 · httpx · Microsoft Graph API · fornado-planner-mcp

## Qué hace
Importación masiva de tareas desde CSV a Microsoft Planner vía Graph API.
Un CSV = un Plan. Un run = crear plan + buckets + tareas (3 llamadas Graph por tarea).

## Comandos
- `python planner_import.py --dry-run` — simula sin llamar a la API
- `python planner_import.py` — importación real con CSV y group-id por defecto
- `python planner_import.py --csv <ruta> --group-id <guid>` — parámetros personalizados
- `python planner_import.py --mode tasks --csv <ruta>` — agrega tareas a plan existente (requiere PlanID y BucketID en CSV)
- `python planner_import.py --mode buckets --csv <ruta>` — agrega buckets a plan existente (requiere PlanID en CSV)
- `python planner_import.py --mode plan --csv <ruta> --group-id <guid>` — crea solo cabecera de plan
- `python planner_import.py --mode list [--filter <texto>]` — lista planes del grupo
- `python planner_import.py --mode delete [--filter <texto>] [--dry-run]` — selección interactiva y borrado

## Arquitectura
- Auth: `MicrosoftAuthManager` + `Settings` importados desde `fornado-planner-mcp/src/`
- .env: `C:\Users\usuario\mcp-servers\fornado-planner-mcp\.env`
- Graph client: `graph_request()` en `planner_import.py` — retry en 429, raise_for_status
- Flujo full (default): parse_csv → create_plan → configure_plan_labels → create_bucket × N → create_task_full × N
- Flujo tasks: parse_csv_tasks → create_task_full × N (PlanID/BucketID desde CSV)
- Flujo buckets: parse_csv_buckets → create_bucket × N (PlanID desde CSV)
- Flujo plan: parse_csv_plan → create_plan → configure_plan_labels
- Flujo list: list_plans → _print_plans_table
- Flujo delete: list_plans → selección interactiva → delete_plan × N (GET ETag + DELETE)
- Constantes fijas: `GROUP_ID`, `ASSIGNEE_GUID`, `CSV_PATH` (sobreescribibles por CLI)

## Variables de entorno requeridas
Ver `.env.example` — residen en el .env del MCP, no en este directorio

## Diseño futuro (MCP)
- `create_plan`, `create_bucket`, `create_task` → `graph/client.py`
- `run_import` → `task_tools.py`
- `@mcp.tool()` wrappers → `server.py`

## Reglas no negociables
1. Nunca loggear `access_token` ni `client_secret`
2. Manejar 429 con retry — nunca ignorar throttling de Graph
3. Siempre obtener ETag antes de PATCH (plans/details, tasks/details)
4. `--dry-run` debe funcionar sin credenciales

## MCP activo
- **fornado-planner-mcp** — activar ANTES de iniciar sesión si la sesión involucra Graph API
- **GitHub** — servidor remoto (Streamable HTTP). Copiar `.cursor/mcp.json.example` → `.cursor/mcp.json`, reemplazar `YOUR_GITHUB_PAT` por un [Personal Access Token](https://github.com/settings/tokens). Requiere Cursor v0.48.0+. Reiniciar Cursor tras configurar. Guía: [Install GitHub MCP Server in Cursor](https://github.com/github/github-mcp-server/blob/main/docs/installation-guides/install-cursor.md)

## Agentes
- **Control de versiones (Git)** — definido en `AGENTS.md` en la raíz. Especialista en ramas, commits, PR/MR con niveles L0–L3 y límites estrictos (no force push, no secretos en salida). Comandos slash: `.cursor/commands/prepare-commit.md` (L2: diff → commit sin push), `.cursor/commands/open-pr.md` (L3: push → crear PR). Regla: `.cursor/rules/version-control.mdc`.

## Estado en GitHub
- **Repositorio:** [grupoebi-ms365-graph-automation](https://github.com/diegosvart/grupoebi-ms365-graph-automation)
- **Remoto:** `origin` → `https://github.com/diegosvart/grupoebi-ms365-graph-automation.git`
- **Rama por defecto:** `main` (tracking `origin/main`).

## Errores aprendidos
<!-- Agregar después de cada corrección: qué salió mal y la regla nueva -->
