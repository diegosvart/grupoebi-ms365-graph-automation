# Opciones de escalamiento y alineación con Microsoft Graph API v1.0

## 1. Referencia y patrón de la API

Según la [referencia de Microsoft Graph REST API v1.0](https://learn.microsoft.com/en-us/graph/api/overview?view=graph-rest-1.0&preserve-view=true):

- **Endpoint:** `https://graph.microsoft.com/v1.0/{resource}?[query_parameters]`
- **Estado:** GA; cambios aditivos, sin romper escenarios existentes.
- **Ventaja:** Un solo endpoint para cruzar entidades y relaciones (usuarios, grupos, Planner, OneDrive, calendario, etc.).

El proyecto ya usa ese patrón (`GRAPH_BASE = "https://graph.microsoft.com/v1.0"`) y recursos como `/planner/plans`, `/groups/{id}/planner/plans`, `/users/{email}`. Cualquier escalamiento debe seguir el mismo patrón y versión v1.0 para producción.

---

## 2. Uso actual de Graph en el proyecto

| Recurso Graph | Uso en el script |
|---------------|------------------|
| `POST /planner/plans` | Crear plan asociado a un grupo |
| `GET/PATCH /planner/plans/{id}/details` | Configurar categorías (labels) |
| `POST /planner/buckets` | Crear buckets en un plan |
| `GET /groups/{id}/planner/plans` | Listar planes del grupo (con paginación) |
| `GET /planner/plans/{id}` + `DELETE` | Borrar plan (con ETag) |
| `POST /planner/tasks` | Crear tarea |
| `GET/PATCH /planner/tasks/{id}/details` | Descripción y checklist |
| `GET /users/{email}` | Resolver email → GUID para asignaciones |

Todo encaja con el patrón v1.0 y con los casos de uso “group-centric” y “user” que documenta Microsoft (planes del grupo, tareas asignadas a usuarios).

---

## 3. Opciones de escalamiento a otras aplicaciones y funcionalidades

### 3.1 Escalamiento horizontal (más servicios Graph con la misma base)

La documentación v1.0 agrupa casos en **user-centric** y **Microsoft 365 group**. Con una **arquitectura basada en cliente Graph reutilizable + token provider + configuración unificada**, se pueden añadir flujos nuevos sin reescribir auth ni retry:

| Área | Recursos Graph v1.0 típicos | Funcionalidad posible |
|------|-----------------------------|------------------------|
| **OneDrive / SharePoint** | `driveitem-list-children`, `driveitem-get`, subida de archivos | Adjuntar archivos a tareas, sincronizar CSV desde OneDrive, listar documentos del grupo |
| **Calendario / Outlook** | `calendar-get`, `event-create`, `user-findmeetingtimes` | Crear eventos desde hitos del plan, sugerir reuniones para tareas |
| **Usuarios y organización** | `user-get`, `user-list-manager`, `user-list-directreports` | Asignaciones por jerarquía, reportes por manager, perfiles en reportes |
| **Grupos M365** | `group-post-conversations`, `group-post-groups`, `plannergroup-list-plans` | Crear grupos desde plantillas, listar planes de varios grupos, notificar en el grupo |
| **OneNote (grupo)** | `notebook-get`, `section-post-pages` | Crear páginas de notas por plan o bucket, actas vinculadas al plan |
| **Suscripciones (webhooks)** | `subscription-post-subscriptions`, `event-delta` | Notificar cambios en planes/tareas (plazos, asignaciones) a sistemas externos |
| **Reporting** | `reportroot-getoffice365groupsactivitycounts` y similares | Dashboards de actividad de grupos/planes |

Requisito común: **mismo cliente HTTP** (retry 429, timeouts, ETag donde aplique), **mismo token provider** y **scopes adicionales** en la app registration según el recurso (por ejemplo `Files.ReadWrite.All`, `Calendars.ReadWrite`, `User.Read.All`).

### 3.2 Escalamiento vertical (más funcionalidad sobre Planner)

Sobre la base actual de Planner se puede extender sin cambiar de recurso:

- **Actualización masiva de tareas:** PATCH de `percentComplete`, fechas o asignaciones desde CSV (reusando `graph_request` + ETag).
- **Sincronización bidireccional:** GET de tareas existentes, comparar con CSV y crear/actualizar/archivar (delta).
- **Múltiples planes por ejecución:** Mismo CSV con varios `PlanName` o varios CSVs en un run; reutilizar `create_plan` + `create_bucket` + `create_task_full` por plan.
- **Plantillas de plan:** Guardar estructura de buckets/labels y clonar a nuevos grupos (crear plan + buckets + opcionalmente tareas plantilla).
- **Integración con MCP:** Exponer `create_plan`, `create_bucket`, `create_task` (y en el futuro `run_import`) como tools del MCP para que otras apps o flujos del workspace invoquen Planner sin duplicar lógica.

### 3.3 Nuevas aplicaciones o flujos en el workspace

Si el objetivo es “participar en otros flujos y apps del workspace de Microsoft Graph”:

- **Otro script o CLI:** Por ejemplo “OneDrive sync” o “Calendar from Planner”: mismo patrón que hoy (entrypoint, orquestador, módulo de dominio que llama al cliente Graph). El cliente y la auth se comparten.
- **Servicio o API propia:** Si más adelante se expone una API (p. ej. FastAPI) que llama a Graph, la capa “cliente Graph + token provider” se reutiliza; solo cambia el orquestador (HTTP handlers en lugar de CLI).
- **MCP como hub:** El MCP puede ofrecer tools de Planner (actual), y en el futuro tools de OneDrive, Calendar o Users reutilizando el mismo `graph/client` y la misma app registration (con los scopes necesarios). La arquitectura sugerida (cliente reutilizable, operaciones por dominio) está alineada con ese hub.

---

## 4. Comprobación: alineación con la nueva arquitectura sugerida

El plan de revisión técnica propone:

1. **Cliente Graph reutilizable** (retry 429, ETag, timeouts) recibiendo token o token provider.
2. **Token provider inyectado** (no instanciar auth dentro de cada orquestador).
3. **Modularización:** transforms/CSV, graph/Planner, orquestación/CLI.
4. **Configuración unificada** (base URL, timeout, group_id, etc.).

Comprobación frente a Graph v1.0 y escalamiento:

| Criterio | Alineación |
|----------|-------------|
| **Un solo endpoint base** (`https://graph.microsoft.com/v1.0`) | Un único cliente con `base_url` configurable permite v1.0 hoy y, si se necesita, beta en otro cliente/config. |
| **Mismo patrón de llamadas** (GET/POST/PATCH/DELETE + headers + body) | Un `request(method, path, json=..., etag=...)` genérico sirve para Planner, Users, Groups, OneDrive, Calendar, etc. |
| **Paginación `@odata.nextLink`** | La lógica de “seguir nextLink” puede vivir en el cliente reutilizable; ya se hace en `list_plans`. |
| **429 y Retry-After** | Centralizar retry en el cliente garantiza que todos los flujos (Planner, futuros) lo respeten. |
| **ETag en PATCH** | Regla de negocio de Graph; mantenerla en el cliente o en helpers por recurso (Planner details, etc.) mantiene alineación. |
| **Scopes y permisos** | Cada flujo (Planner, OneDrive, Calendar) puede documentar sus scopes; el token provider sigue siendo único (MSAL con los scopes que pida la app). |
| **MCP y otros consumidores** | Cliente + token provider permite que el script actual y el MCP (u otra app) usen la misma capa; solo cambia quién invoca (CLI vs `@mcp.tool()`). |

Conclusión: la arquitectura sugerida está **alineada** con el modelo de Graph v1.0 (un endpoint, recursos bajo `/{resource}`, mismos patrones HTTP y de errores) y con el objetivo de escalar a más aplicaciones y funcionalidades dentro del mismo workspace.

---

## 5. Resumen y siguientes pasos

- **Opciones de escalamiento:** Incluyen más servicios v1.0 (OneDrive, Calendar, Users, Groups, OneNote, subscriptions) y más funcionalidad sobre Planner (actualizaciones masivas, sincronización, plantillas, MCP).
- **Arquitectura:** Cliente Graph reutilizable + token provider + módulos por dominio + configuración unificada es compatible con Graph v1.0 y con ese escalamiento.
- **Recomendación:** Implementar primero la extracción del cliente Graph y el token provider; luego añadir flujos nuevos como nuevos módulos que usen el mismo cliente y la misma config, documentando en cada uno los recursos y scopes de [Microsoft Graph v1.0](https://learn.microsoft.com/en-us/graph/api/overview?view=graph-rest-1.0&preserve-view=true).
