---
name: planner-graph-csv
description: Reglas y flujos para trabajar con Microsoft Graph (Planner), CSV y MCP en el proyecto Planner Import Script. Usar al modificar planner_import.py, lógica Graph o diseño futuro.
---

# Planner + Graph + CSV — Skill de proyecto

Contexto para trabajar en este repositorio: importación masiva CSV → Microsoft Planner vía Microsoft Graph API v1.0.

## Reglas no negociables

1. **Nunca** loggear ni exponer `access_token` ni `client_secret`.
2. **Siempre** manejar 429 (throttling) con retry; respetar `Retry-After` si viene en la respuesta.
3. **Siempre** obtener el ETag actual antes de cualquier PATCH en `planner/plans/{id}/details` y `planner/tasks/{id}/details`.
4. **`--dry-run`** debe poder ejecutarse sin credenciales (simulación sin llamadas a la API).

## Patrón Graph

- Base: `https://graph.microsoft.com/v1.0`
- Recursos usados: `POST /planner/plans`, `GET/PATCH .../plans/{id}/details`, `POST /planner/buckets`, `GET /groups/{id}/planner/plans`, `POST /planner/tasks`, `GET/PATCH .../tasks/{id}/details`, `GET /users/{email}` (resolver asignaciones).
- Cliente: una función o módulo reutilizable (retry 429, timeouts, `raise_for_status`); token inyectado o provisto por el auth del MCP.

## Flujos

- **Full (default):** parse_csv → create_plan → configure_plan_labels → create_bucket × N → create_task_full × N.
- **Tasks:** parse_csv_tasks → create_task_full × N (PlanID y BucketID desde CSV).
- **Buckets:** parse_csv_buckets → create_bucket × N (PlanID desde CSV).
- **Plan:** parse_csv_plan → create_plan → configure_plan_labels.
- **List:** list_plans (paginación `@odata.nextLink`) → salida en tabla.
- **Delete:** list_plans → selección interactiva → GET ETag por plan → DELETE.

## Diseño futuro

- Cliente Graph reutilizable + token provider inyectado.
- Módulos: transforms/CSV, graph/Planner, orquestación/CLI (y en su momento API/MCP).
- MCP: `create_plan`, `create_bucket`, `create_task`, `run_import` como tools; wrappers en server, lógica en graph/client y task_tools.
- Escalamiento: ver **docs/ESCALAMIENTO_GRAPH.md** (horizontal: OneDrive, Calendar, Users, Groups, OneNote, webhooks; vertical: actualizaciones masivas, sync, plantillas; nuevas apps: API propia, MCP como hub).

## Referencias en repo

- **CLAUDE.md** — Stack, comandos, arquitectura, reglas.
- **AGENTS.md** — Control de versiones (Git) y niveles L0–L3.
- **docs/ESCALAMIENTO_GRAPH.md** — Opciones de escalamiento y alineación con Graph v1.0.
