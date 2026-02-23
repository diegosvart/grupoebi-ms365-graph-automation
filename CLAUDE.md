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
`fornado-planner-mcp` — activar ANTES de iniciar sesión si la sesión involucra Graph API

## Estado en GitHub
- **Repositorio Git:** inicializado (`git init`); existe `.git` y `.gitignore` en la raíz.
- **Remoto GitHub:** no definido; hay que crear el repo en GitHub y asociar el remote.
- **Primer push (ejecutar en la raíz del proyecto):**
  ```bash
  git add .
  git commit -m "Initial commit: Planner Import script"
  git remote add origin https://github.com/<org-o-usuario>/<repo>.git
  git branch -M main
  git push -u origin main
  ```
  Sustituir `<org-o-usuario>` y `<repo>` por la URL real del repositorio en GitHub.

## Errores aprendidos
<!-- Agregar después de cada corrección: qué salió mal y la regla nueva -->
