# API Referencia — Microsoft Graph API

## Endpoints implementados

Todos los endpoints usan la base URL: `https://graph.microsoft.com/v1.0/`

### Microsoft Planner

| Metodo | Endpoint | Descripcion | Permiso requerido |
|---|---|---|---|
| `GET` | `/groups/{id}/planner/plans` | Listar planes de un grupo | `Tasks.Read` |
| `POST` | `/planner/plans` | Crear nuevo plan | `Tasks.ReadWrite` |
| `PATCH` | `/planner/plans/{id}` | Actualizar plan (labels, etc.) | `Tasks.ReadWrite` + `If-Match` header |
| `DELETE` | `/planner/plans/{id}` | Eliminar plan | `Tasks.ReadWrite` + `If-Match` header |
| `POST` | `/planner/buckets` | Crear bucket en un plan | `Tasks.ReadWrite` |
| `DELETE` | `/planner/buckets/{id}` | Eliminar bucket | `Tasks.ReadWrite` + `If-Match` header |
| `POST` | `/planner/tasks` | Crear tarea | `Tasks.ReadWrite` |
| `PATCH` | `/planner/tasks/{id}/details` | Agregar descripcion y checklist | `Tasks.ReadWrite` + `If-Match` header |

> **Nota sobre ETag:** Los endpoints PATCH y DELETE de Planner requieren el header `If-Match` con el valor ETag obtenido del GET previo. El sistema lo maneja automaticamente en `graph_request()`.

### Microsoft Teams

| Metodo | Endpoint | Descripcion | Permiso requerido |
|---|---|---|---|
| `GET` | `/teams/{id}/channels` | Listar canales | `Team.ReadBasic.All` |
| `POST` | `/teams/{id}/channels` | Crear canal | `Channel.Create` |
| `GET` | `/teams/{id}/members` | Listar miembros del Team | `TeamMember.Read.All` |
| `POST` | `/teams/{id}/members` | Agregar miembro al Team | `TeamMember.ReadWrite.All` |
| `DELETE` | `/teams/{id}/members/{membership-id}` | Quitar miembro del Team | `TeamMember.ReadWrite.All` |
| `POST` | `/teams/{id}/channels/{id}/members` | Agregar miembro a canal | `ChannelMember.ReadWrite.All` |
| `POST` | `/teams/{id}/channels/{id}/tabs` | Anclar pestana en canal | `TeamsTab.ReadWrite.All` |
| `POST` | `/teams/{id}/channels/{id}/messages` | Enviar mensaje al canal | `ChannelMessage.Send` |

### SharePoint / OneDrive

| Metodo | Endpoint | Descripcion | Permiso requerido |
|---|---|---|---|
| `GET` | `/groups/{id}/sites/root` | Obtener sitio del grupo | `Sites.Read.All` |
| `GET` | `/sites/{id}/drive` | Obtener drive del sitio | `Files.Read.All` |
| `GET` | `/drives/{id}/root:/{path}` | Verificar si existe item | `Files.Read.All` |
| `PUT` | `/drives/{id}/root:/{path}:/children` | Crear carpeta | `Files.ReadWrite.All` |
| `PUT` | `/drives/{id}/root:/{path}:/content` | Subir archivo (< 4 MB) | `Files.ReadWrite.All` |
| `POST` | `/drives/{id}/root:/{path}:/createUploadSession` | Iniciar upload de archivo grande | `Files.ReadWrite.All` |
| `GET` | `/drives/{id}/root:/{path}:/children` | Listar contenido de carpeta | `Files.Read.All` |

### Azure Entra ID — Usuarios

| Metodo | Endpoint | Descripcion | Permiso requerido |
|---|---|---|---|
| `GET` | `/users/{email}` | Resolver email a GUID | `User.Read.All` |
| `GET` | `/users?$filter=department eq '{dept}'` | Listar por departamento | `User.Read.All` |
| `POST` | `/users` | Crear usuario | `User.ReadWrite.All` |
| `PATCH` | `/users/{id}` | Actualizar atributos | `User.ReadWrite.All` |
| `POST` | `/users/{id}/assignLicense` | Asignar/quitar licencia | `User.ReadWrite.All` |
| `POST` | `/users/{id}/revokeSignInSessions` | Revocar sesiones activas | `User.ReadWrite.All` |
| `DELETE` | `/users/{id}` | Eliminar usuario | `User.ReadWrite.All` |
| `GET` | `/subscribedSkus` | Listar licencias del tenant | `Organization.Read.All` |

### Azure Entra ID — Grupos

| Metodo | Endpoint | Descripcion | Permiso requerido |
|---|---|---|---|
| `GET` | `/groups/{id}/members` | Listar miembros del grupo | `GroupMember.Read.All` |
| `POST` | `/groups/{id}/members/$ref` | Agregar miembro al grupo | `GroupMember.ReadWrite.All` |
| `DELETE` | `/groups/{id}/members/{user-id}/$ref` | Quitar miembro del grupo | `GroupMember.ReadWrite.All` |

### Exchange Online

| Metodo | Endpoint | Descripcion | Permiso requerido |
|---|---|---|---|
| `POST` | `/users/{id}/sendMail` | Enviar email | `Mail.Send` |
| `GET` | `/users/{id}/mailboxSettings` | Obtener configuracion del buzon | `MailboxSettings.Read` |
| `PATCH` | `/users/{id}/mailboxSettings` | Configurar forwarding y OOF | `MailboxSettings.ReadWrite` |

### Microsoft Intune

| Metodo | Endpoint | Descripcion | Permiso requerido |
|---|---|---|---|
| `GET` | `/users/{id}/managedDevices` | Listar dispositivos del usuario | `DeviceManagementManagedDevices.Read.All` |
| `GET` | `/deviceManagement/deviceCompliancePolicies` | Listar politicas de compliance | `DeviceManagementConfiguration.Read.All` |
| `POST` | `/deviceManagement/deviceCompliancePolicies/{id}/assign` | Asignar politica | `DeviceManagementConfiguration.ReadWrite.All` |
| `POST` | `/deviceManagement/managedDevices/{id}/retire` | Retire (BYOD) | `DeviceManagementManagedDevices.ReadWrite.All` |
| `POST` | `/deviceManagement/managedDevices/{id}/wipe` | Wipe (corporativo) | `DeviceManagementManagedDevices.ReadWrite.All` |

---

## Endpoints planeados (no implementados)

| Servicio | Endpoint | Descripcion | Estado |
|---|---|---|---|
| Entra ID | `PUT /users/{id}/manager/$ref` | Asignar manager | Planeado — Alta usuario |
| Teams | `POST /teams/{id}/channels/{id}/messages` | Notificaciones de proyecto | Planeado |
| Exchange | `POST /users/{id}/events` | Crear evento kick-off | Planeado |
| Intune | `GET /deviceAppManagement/mobileApps` | Listar apps disponibles | Planeado |
| Intune | `POST /deviceAppManagement/mobileApps/{id}/assign` | Asignar app a grupo | Planeado |

---

## Manejo de errores HTTP

| Codigo HTTP | Significado | Accion del sistema |
|---|---|---|
| `200 OK` | Exito | Continuar |
| `201 Created` | Recurso creado | Continuar, extraer ID del recurso creado |
| `204 No Content` | Exito sin cuerpo (DELETE, PATCH) | Continuar |
| `400 Bad Request` | Payload invalido | Lanzar excepcion con cuerpo de respuesta |
| `401 Unauthorized` | Token invalido o expirado | Renovar token y reintentar una vez |
| `403 Forbidden` | Permiso insuficiente | Lanzar excepcion — requiere accion en Azure Portal |
| `404 Not Found` | Recurso no existe | Lanzar `GraphNotFoundError` |
| `409 Conflict` | Recurso ya existe | Manejar como warning segun el contexto |
| `429 Too Many Requests` | Throttling | Esperar `Retry-After` segundos y reintentar |
| `500+ Server Error` | Error en Microsoft | Reintentar con backoff exponencial (max `MAX_RETRIES`) |

---

## Headers requeridos por la Graph API

| Header | Valor | Cuando |
|---|---|---|
| `Authorization` | `Bearer {access_token}` | Todas las llamadas |
| `Content-Type` | `application/json` | POST, PATCH con body JSON |
| `If-Match` | `{etag-value}` | PATCH y DELETE de recursos Planner |
| `Prefer` | `return=representation` | Cuando se necesita el recurso creado en la respuesta de POST |
| `ConsistencyLevel` | `eventual` | Consultas avanzadas con `$count`, `$search` en directorio |

---

## Limites de la Graph API relevantes

| Recurso | Limite |
|---|---|
| Solicitudes por segundo (por app) | ~120 req/s (varia por endpoint) |
| Solicitudes por segundo (por usuario) | ~10 req/s |
| Tamano maximo de body | 4 MB (usar upload session para archivos mayores) |
| Retries en throttling | Hasta `MAX_RETRIES` (configurado en `.env`) |
| Expiracion del access token | 3600 segundos (1 hora) |
| Tamano maximo de checklist en Planner | 20 items por tarea |
| Buckets maximos por plan de Planner | Sin limite documentado |
| Tareas maximas por bucket de Planner | Sin limite documentado |
