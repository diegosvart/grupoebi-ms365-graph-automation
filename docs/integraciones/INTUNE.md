# Integracion: Microsoft Intune

## Que es

Microsoft Intune es la solucion de gestion de dispositivos moviles (MDM) y de aplicaciones moviles (MAM) de Microsoft 365. En este proyecto se usara para:
- Registrar el dispositivo del nuevo colaborador al hacer onboarding
- Asignar politicas de compliance al dispositivo
- Asignar aplicaciones empresariales al usuario
- Auditar dispositivos al hacer offboarding

> **Estado:** Esta integracion esta documentada para implementacion futura. Los endpoints y permisos estan validados contra la Graph API de produccion.

---

## Permisos Graph API requeridos

| Permiso | Tipo | Para que |
|---|---|---|
| `DeviceManagementManagedDevices.ReadWrite.All` | Application | Gestionar dispositivos enrolados |
| `DeviceManagementConfiguration.ReadWrite.All` | Application | Asignar politicas de compliance y configuracion |
| `DeviceManagementApps.ReadWrite.All` | Application | Gestionar asignacion de apps |

> Estos permisos son de alto privilegio. Requieren **consentimiento de administrador de tenant** y aprobacion del equipo de seguridad.

---

## Endpoints relevantes

### Listar dispositivos del usuario

```http
GET /v1.0/users/{user-id}/managedDevices
```

Respuesta relevante:
```json
{
  "value": [
    {
      "id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
      "deviceName": "LAPTOP-JPEREZ",
      "operatingSystem": "Windows",
      "osVersion": "10.0.22631.0",
      "complianceState": "compliant",
      "enrolledDateTime": "2026-04-01T10:00:00Z",
      "lastSyncDateTime": "2026-04-15T08:30:00Z"
    }
  ]
}
```

### Listar todos los dispositivos del tenant

```http
GET /v1.0/deviceManagement/managedDevices
```

Con filtro por usuario:
```http
GET /v1.0/deviceManagement/managedDevices?$filter=userId eq '{user-id}'
```

### Obtener estado de compliance de un dispositivo

```http
GET /v1.0/deviceManagement/managedDevices/{device-id}?$select=deviceName,complianceState,lastSyncDateTime
```

### Listar politicas de compliance disponibles

```http
GET /v1.0/deviceManagement/deviceCompliancePolicies
```

### Asignar politica de compliance a grupo

```http
POST /v1.0/deviceManagement/deviceCompliancePolicies/{policy-id}/assign
Content-Type: application/json

{
  "assignments": [
    {
      "target": {
        "@odata.type": "#microsoft.graph.groupAssignmentTarget",
        "groupId": "{group-id}"
      }
    }
  ]
}
```

> La asignacion de politicas es por **grupo**, no por usuario individual. El usuario debe pertenecer al grupo de Intune para recibir la politica.

### Listar aplicaciones disponibles en Intune

```http
GET /v1.0/deviceAppManagement/mobileApps?$filter=isAssigned eq true
```

### Asignar aplicacion a grupo

```http
POST /v1.0/deviceAppManagement/mobileApps/{app-id}/assign
Content-Type: application/json

{
  "mobileAppAssignments": [
    {
      "intent": "required",
      "target": {
        "@odata.type": "#microsoft.graph.groupAssignmentTarget",
        "groupId": "{group-id}"
      }
    }
  ]
}
```

---

## Flujo de onboarding con Intune

Al dar de alta a un usuario, el sistema agrega al usuario al grupo de Intune correspondiente a su perfil. Las politicas y apps se asignan automaticamente al grupo:

```python
# Pseudocodigo — implementacion futura en create_environment.py

def setup_intune_for_user(user_id, perfil):
    # Agregar al grupo de Intune del perfil
    # (las politicas y apps se aplican automaticamente al grupo)
    intune_group_id = perfil.intune_group_id  # desde INTUNE_DEFAULT_DEVICE_GROUP_ID o catalogo

    graph_request("POST", f"/groups/{intune_group_id}/members/$ref",
                  body={"@odata.id": f"https://graph.microsoft.com/v1.0/directoryObjects/{user_id}"})

    log.info(f"Usuario {user_id} agregado al grupo de Intune {intune_group_id}")
    log.info("El dispositivo recibira politicas al registrarse en Intune.")
```

---

## Flujo de offboarding con Intune

Al dar de baja a un usuario, auditar y limpiar dispositivos:

```python
# Pseudocodigo

def cleanup_intune_for_user(user_id):
    # Listar dispositivos del usuario
    devices = graph_request("GET", f"/users/{user_id}/managedDevices")

    for device in devices["value"]:
        device_id = device["id"]
        device_name = device["deviceName"]

        # Opcion 1: Retire (elimina datos corporativos, deja datos personales)
        graph_request("POST", f"/deviceManagement/managedDevices/{device_id}/retire")

        # Opcion 2: Wipe (elimina todo — solo para dispositivos corporativos)
        # graph_request("POST", f"/deviceManagement/managedDevices/{device_id}/wipe")

        log.info(f"Dispositivo {device_name} dado de baja de Intune")
```

> **Retire vs Wipe:**
> - **Retire:** Elimina datos corporativos y desregistra el dispositivo. Los datos personales quedan intactos. Usar para dispositivos BYOD.
> - **Wipe:** Resetea el dispositivo a configuracion de fabrica. Solo usar para dispositivos corporativos.

---

## Variables de entorno requeridas

```env
# En .env
INTUNE_DEFAULT_COMPLIANCE_POLICY_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
INTUNE_DEFAULT_DEVICE_GROUP_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
```

---

## Troubleshooting

| Problema | Causa probable | Solucion |
|---|---|---|
| `403 Forbidden` | Permisos de Intune no otorgados | Agregar `DeviceManagementManagedDevices.ReadWrite.All` y consentimiento admin |
| `404 Not Found` en politica | Policy ID incorrecto | Obtener el ID correcto con `GET /deviceManagement/deviceCompliancePolicies` |
| Dispositivo no recibe politica | Usuario no en el grupo asignado | Verificar pertenencia del usuario al grupo de Intune |
| `wipe` no funciona | Dispositivo no enrolado como corporativo | Verificar tipo de enrollment; usar `retire` para BYOD |

---

## Auditoria de dispositivos (offboarding checklist)

Al dar de baja a un usuario, verificar:

- [ ] Listar dispositivos del usuario (`GET /users/{id}/managedDevices`)
- [ ] Confirmar si hay dispositivos corporativos activos
- [ ] Ejecutar `retire` (BYOD) o `wipe` (corporativo) segun politica de la empresa
- [ ] Verificar que el dispositivo queda en estado `retired` en el portal de Intune
- [ ] Remover al usuario del grupo de Intune

---

## Como se conecta con los flujos de las guias

| Guia | Operaciones Intune |
|---|---|
| [Alta de Usuario](../guias/ALTA_USUARIO.md) | Agregar usuario al grupo de Intune del perfil |
| [Baja de Usuario](../guias/BAJA_USUARIO.md) | Listar dispositivos, ejecutar retire/wipe, remover del grupo |
