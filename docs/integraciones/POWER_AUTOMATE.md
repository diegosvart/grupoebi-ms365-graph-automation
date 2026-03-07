# Integracion: Power Automate

## Que es

Power Automate es la plataforma de automatizacion de bajo codigo de Microsoft 365. En este proyecto, Power Automate actua como **capa de interfaz para usuarios no tecnicos**: en lugar de ejecutar comandos CLI, RRHH puede usar formularios de Teams o disparadores automaticos que invocan los flujos de Python a traves de una Azure Function.

```
RRHH completa formulario en Teams
        │
        │ Power Automate flow
        ▼
Azure Function (HTTP trigger)
        │
        │ Llama al CLI Python internamente
        ▼
Microsoft Graph API
```

---

## Arquitectura de la integracion

### Componentes

| Componente | Rol |
|---|---|
| **Forms / Adaptive Cards en Teams** | Interfaz de usuario para RRHH (sin CLI) |
| **Power Automate Flow** | Orquesta el proceso: recibe datos del formulario, llama a la Azure Function |
| **Azure Function (HTTP trigger)** | Wrapper del CLI Python que expone los flujos como endpoints HTTP |
| **Python CLI** | Logica de negocio + llamadas a Graph API |

---

## Azure Function — Wrapper HTTP

La Azure Function expone el CLI Python como endpoints REST. Esto permite que Power Automate (u otros sistemas) invoquen los flujos sin acceso directo al CLI.

### Endpoint: alta de usuario

```http
POST {AZURE_FUNCTION_URL}/onboard-user
x-functions-key: {AZURE_FUNCTION_KEY}
Content-Type: application/json

{
  "displayName": "Juan Perez Gonzalez",
  "mailNickname": "jperez",
  "userPrincipalName": "jperez@empresa.com",
  "jobTitle": "Analista RRHH",
  "department": "Recursos Humanos",
  "employeeId": "12345678-9",
  "manager": "ggerente@empresa.com",
  "ticketRef": "TICKET-2026-0123",
  "dryRun": false
}
```

Respuesta exitosa:
```json
{
  "status": "success",
  "userId": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "email": "jperez@empresa.com",
  "profile": "rrhh_analyst",
  "license": "M365 E3",
  "groupsAdded": ["GRP-RRHH", "GRP-VPN", "GRP-Intranet"],
  "channelsAdded": ["General", "Anuncios", "RRHH-Equipo"]
}
```

### Endpoint: baja de usuario

```http
POST {AZURE_FUNCTION_URL}/offboard-user
x-functions-key: {AZURE_FUNCTION_KEY}
Content-Type: application/json

{
  "userEmail": "jperez@empresa.com",
  "managerEmail": "ggerente@empresa.com",
  "ticketRef": "TICKET-2026-0456",
  "dryRun": false
}
```

### Endpoint: nuevo proyecto

```http
POST {AZURE_FUNCTION_URL}/create-project
x-functions-key: {AZURE_FUNCTION_KEY}
Content-Type: application/json

{
  "projectName": "Proyecto Alpha 2026",
  "groupId": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "pmEmail": "pm@empresa.com",
  "teamEmails": ["dev1@empresa.com", "dev2@empresa.com"],
  "csvTemplate": "default",
  "ticketRef": "TICKET-2026-0789",
  "dryRun": false
}
```

---

## Flujo de Power Automate — Alta de usuario

### Trigger: Adaptive Card en Teams

El analista de RRHH completa un formulario en Teams con:
- Nombre completo
- RUT
- Cargo (dropdown con valores del catalogo de perfiles)
- Area (dropdown)
- Fecha de ingreso
- Manager (people picker)
- Numero de ticket de autorizacion

### Pasos del flow

```
1. Trigger: "When a new response is submitted" (Teams Adaptive Card)
        │
2. Action: "Get response details" — extraer campos del formulario
        │
3. Condition: ¿Tiene numero de ticket de autorizacion?
        ├── No → Enviar mensaje de error al solicitante
        └── Si →
               │
4. Action: "HTTP" — POST a Azure Function /onboard-user
   Body: { nombre, rut, cargo, area, fecha_ingreso, manager, ticket }
        │
5. Condition: ¿Respuesta exitosa (status 200)?
        ├── No → Enviar alerta al canal de TI con detalles del error
        └── Si →
               │
6. Action: "Post message in a chat" — notificar a RRHH y al manager
   Mensaje: "La cuenta de {nombre} ha sido creada. Email: {email}"
```

---

## Flujo de Power Automate — Notificacion al completar entorno de proyecto

```
1. Trigger: HTTP request (llamado por la Azure Function al terminar)
        │
2. Parse JSON — extraer datos del proyecto
        │
3. Action: "Post adaptive card in Teams channel"
   Canal: General del Team del grupo
   Contenido:
   ┌────────────────────────────────────────────┐
   │  Nuevo entorno de proyecto creado          │
   │  Proyecto: Proyecto Alpha 2026             │
   │  Plan de Planner: [Ver plan]               │
   │  Canal de Teams: [Ir al canal]             │
   │  Carpetas SharePoint: [Ver documentos]     │
   └────────────────────────────────────────────┘
```

---

## Como implementar el wrapper en Azure Functions

### Estructura del proyecto de Azure Functions

```
azure-functions/
|-- host.json
|-- local.settings.json    (excluido de git — contiene credenciales locales)
|-- requirements.txt
|
|-- onboard_user/
|   |-- __init__.py        # Handler HTTP
|   `-- function.json      # Configuracion del trigger
|
|-- offboard_user/
|   |-- __init__.py
|   `-- function.json
|
`-- create_project/
    |-- __init__.py
    `-- function.json
```

### Ejemplo de handler (`onboard_user/__init__.py`)

```python
import azure.functions as func
import json
import subprocess
import sys

def main(req: func.HttpRequest) -> func.HttpResponse:
    try:
        body = req.get_json()
    except ValueError:
        return func.HttpResponse("Invalid JSON", status_code=400)

    # Validar campos requeridos
    required = ["userPrincipalName", "jobTitle", "department", "ticketRef"]
    missing = [f for f in required if f not in body]
    if missing:
        return func.HttpResponse(
            json.dumps({"error": f"Missing fields: {missing}"}),
            status_code=400,
            mimetype="application/json"
        )

    # Construir comando CLI
    cmd = [sys.executable, "create_environment.py", "--mode", "onboard-user"]
    if body.get("dryRun"):
        cmd.append("--dry-run")

    # Ejecutar CLI (el .env esta configurado en la Azure Function App Settings)
    result = subprocess.run(cmd, capture_output=True, text=True, input=json.dumps(body))

    if result.returncode == 0:
        return func.HttpResponse(result.stdout, mimetype="application/json")
    else:
        return func.HttpResponse(
            json.dumps({"error": result.stderr}),
            status_code=500,
            mimetype="application/json"
        )
```

---

## Variables de entorno en Azure Function App

Las variables del `.env` se configuran como **Application Settings** en la Azure Function App (equivalente al `.env` en entorno local):

```
AZURE_TENANT_ID          = <valor real>
AZURE_CLIENT_ID          = <valor real>
AZURE_CLIENT_SECRET      = <secreto — preferir referencia a Key Vault>
TALANA_API_KEY           = <secreto — preferir referencia a Key Vault>
GROUP_ID                 = <valor real>
```

> En produccion, usar referencias a Azure Key Vault en lugar de valores directos:
> `@Microsoft.KeyVault(SecretUri=https://mi-keyvault.vault.azure.net/secrets/AZURE-CLIENT-SECRET/)`

---

## Troubleshooting

| Problema | Causa probable | Solucion |
|---|---|---|
| `401 Unauthorized` en Azure Function | `AZURE_FUNCTION_KEY` invalida en el header | Verificar el header `x-functions-key` |
| Flow de Power Automate falla en HTTP | URL incorrecta o Function App sin publicar | Verificar que la Function App este deployada y la URL sea correcta |
| Timeout del flow | El CLI tarda mas de 230 segundos (limite de Power Automate) | Usar Durable Functions o dividir el flujo en pasos asincronos |
| Variables de entorno no disponibles | Application Settings no configurados en Function App | Configurar en Azure Portal > Function App > Configuration > Application Settings |
