# Integracion: Azure Entra ID

## Que es

Azure Entra ID (antes Azure Active Directory) es el directorio de identidades de Microsoft 365. Es la fuente autoritativa de usuarios, grupos de seguridad y licencias del tenant. Todos los demas servicios M365 (Teams, SharePoint, Planner, Exchange) delegan la autenticacion y autorizacion a Entra ID.

**Rol en este proyecto:** Entra ID es el punto de entrada de todos los flujos de ciclo de vida de usuarios (alta, baja, cambio de rol). La App Registration que autentica este sistema tambien vive en Entra ID.

---

## Permisos Graph API requeridos

| Permiso | Tipo | Para que operacion |
|---|---|---|
| `User.Read.All` | Application | Leer usuarios, resolver emails a GUIDs |
| `User.ReadWrite.All` | Application | Crear, modificar y deshabilitar usuarios |
| `Directory.ReadWrite.All` | Application | Gestionar miembros de grupos de seguridad |
| `Group.ReadWrite.All` | Application | Crear planes Planner vinculados a grupos |

> Los permisos `User.ReadWrite.All` y `Directory.ReadWrite.All` requieren **consentimiento de administrador de tenant** en Azure Portal.

---

## Endpoints implementados

### Resolver email a GUID

```http
GET /v1.0/users/{email}
```

Respuesta relevante:
```json
{
  "id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "displayName": "Juan Perez",
  "mail": "jperez@empresa.com",
  "userPrincipalName": "jperez@empresa.com"
}
```

### Crear usuario

```http
POST /v1.0/users
Content-Type: application/json

{
  "accountEnabled": true,
  "displayName": "Juan Perez Gonzalez",
  "mailNickname": "jperez",
  "userPrincipalName": "jperez@empresa.com",
  "passwordProfile": {
    "forceChangePasswordNextSignIn": true,
    "password": "<contrasena-temporal-generada>"
  },
  "jobTitle": "Analista RRHH",
  "department": "Recursos Humanos",
  "employeeId": "12345678-9",
  "usageLocation": "CL"
}
```

> `usageLocation` es obligatorio para asignar licencias. Usar `"CL"` para Chile.

### Asignar licencia

```http
POST /v1.0/users/{id}/assignLicense
Content-Type: application/json

{
  "addLicenses": [
    { "skuId": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx" }
  ],
  "removeLicenses": []
}
```

**SKU IDs de licencias comunes:**

| Licencia | SKU Name | SKU ID (referencia — verificar en tenant) |
|---|---|---|
| Microsoft 365 E3 | `SPE_E3` | Obtener via `GET /subscribedSkus` |
| Microsoft 365 E5 | `SPE_E5` | Obtener via `GET /subscribedSkus` |
| Microsoft 365 F3 | `SPE_F1` | Obtener via `GET /subscribedSkus` |

Para obtener los SKU IDs reales del tenant:
```http
GET /v1.0/subscribedSkus
```

### Deshabilitar usuario (offboarding)

```http
PATCH /v1.0/users/{id}
Content-Type: application/json

{
  "accountEnabled": false
}
```

### Revocar sesiones activas

```http
POST /v1.0/users/{id}/revokeSignInSessions
```

### Actualizar atributos de usuario

```http
PATCH /v1.0/users/{id}
Content-Type: application/json

{
  "jobTitle": "Ejecutivo Finanzas",
  "department": "Finanzas",
  "employeeId": "12345678-9"
}
```

### Actualizar manager

```http
PUT /v1.0/users/{id}/manager/$ref
Content-Type: application/json

{
  "@odata.id": "https://graph.microsoft.com/v1.0/users/{manager-id}"
}
```

### Agregar usuario a grupo

```http
POST /v1.0/groups/{group-id}/members/$ref
Content-Type: application/json

{
  "@odata.id": "https://graph.microsoft.com/v1.0/directoryObjects/{user-id}"
}
```

### Quitar usuario de grupo

```http
DELETE /v1.0/groups/{group-id}/members/{user-id}/$ref
```

### Eliminar usuario (definitivo — despues de 30 dias)

```http
DELETE /v1.0/users/{id}
```

### Listar usuarios por departamento

```http
GET /v1.0/users?$filter=department eq 'Recursos Humanos'&$select=id,displayName,mail,jobTitle
```

---

## Flujo completo de alta de usuario

```python
# Pseudocodigo — ver implementacion real en create_environment.py

def onboard_user(config, perfil):
    # 1. Crear usuario
    user = graph_request("POST", "/users", body=user_payload(config))

    # 2. Asignar licencia
    graph_request("POST", f"/users/{user.id}/assignLicense",
                  body={"addLicenses": [{"skuId": perfil.license_sku}],
                        "removeLicenses": []})

    # 3. Agregar a grupos de seguridad
    for group_id in perfil.security_groups:
        graph_request("POST", f"/groups/{group_id}/members/$ref",
                      body={"@odata.id": f"https://graph.microsoft.com/v1.0/directoryObjects/{user.id}"})

    # 4. Actualizar manager
    manager_id = resolve_email(config.manager_email)
    graph_request("PUT", f"/users/{user.id}/manager/$ref",
                  body={"@odata.id": f"https://graph.microsoft.com/v1.0/users/{manager_id}"})

    return user.id
```

---

## Troubleshooting

| Problema | Diagnostico | Solucion |
|---|---|---|
| `Authorization_RequestDenied` | Falta consentimiento de admin para permisos de escritura | En Azure Portal: App Registration > API permissions > Grant admin consent |
| `Request_BadRequest` en create user | Campo `usageLocation` faltante | Agregar `"usageLocation": "CL"` al payload |
| `License_AssignmentFailed` | No hay licencias disponibles del SKU | Adquirir mas licencias en M365 Admin Center |
| `Directory_QuotaExceeded` | Limite de objetos del tenant alcanzado | Contactar a Microsoft Support |
| `Request_ResourceNotFound` en manager | El manager no existe en el tenant | Verificar el email del manager en Azure Portal |

---

## Como se conecta con los flujos de las guias

| Guia | Operaciones Entra ID |
|---|---|
| [Alta de Usuario](../guias/ALTA_USUARIO.md) | POST /users, assignLicense, grupos, manager |
| [Baja de Usuario](../guias/BAJA_USUARIO.md) | PATCH accountEnabled:false, revokeSignInSessions, removeLicense, DELETE grupos |
| [Cambio de Rol](../guias/CAMBIO_ROL.md) | PATCH jobTitle/department, swap grupos, swap licencia |
| [Incorporacion a Proyecto](../guias/INCORPORACION_PROYECTO.md) | GET /users/{email} (resolver GUID) |
