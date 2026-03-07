# Integracion: Talana HRIS

## Que es

Talana es el sistema de informacion de recursos humanos (HRIS) de Grupo EBI. Gestiona contratos, liquidaciones, vacaciones y la estructura organizacional. En este proyecto, **Talana es la fuente de verdad del estado de los empleados**: M365 sigue a Talana, no al reves.

**API Key activa:** La integracion tiene una API key activa. Configurar en la variable `TALANA_API_KEY` del archivo `.env`.

---

## Modelo de integracion: webhook-first

La integracion prioriza el flujo via **webhook**: Talana notifica al sistema Python cuando ocurre un evento de alta o baja. El sistema orquesta todo el resto automaticamente. El analista de RRHH solo actua en Talana.

```
Talana ──webhook──► Sistema Python ──► M365 (Entra ID, Teams, Planner, Exchange)
                                   └──► Talana (actualiza ms365_id y email)
```

El **polling** (consultar Talana periodicamente) es el mecanismo de fallback si los webhooks no estan disponibles o fallan.

---

## Permisos requeridos

| Permiso | Descripcion |
|---|---|
| `TALANA_API_KEY` | API Key para autenticar llamadas REST a Talana |
| `TALANA_WEBHOOK_SECRET` | Secreto HMAC para validar la firma de webhooks entrantes |

No se requieren permisos de Graph API adicionales para la integracion con Talana (los permisos son de Talana hacia este sistema, y de este sistema hacia Graph API).

---

## Webhooks de Talana

### Configuracion

En Talana > Configuracion > Integraciones > Webhooks:

- **URL del webhook:** `https://tu-function-app.azurewebsites.net/api/talana-webhook`
- **Eventos suscritos:** `alta_empleado`, `baja_empleado`, `modificacion_empleado`
- **Secreto:** valor de `TALANA_WEBHOOK_SECRET` en `.env`

### Evento: alta_empleado

Payload enviado por Talana al registrar un nuevo colaborador:

```json
{
  "evento": "alta_empleado",
  "timestamp": "2026-04-01T08:00:00Z",
  "empleado": {
    "id": "12345",
    "rut": "12345678-9",
    "nombre": "Juan",
    "apellido_paterno": "Perez",
    "apellido_materno": "Gonzalez",
    "cargo": "Analista RRHH",
    "departamento": "Recursos Humanos",
    "fecha_ingreso": "2026-04-01",
    "email_personal": "juanperez@gmail.com",
    "manager_rut": "98765432-1"
  }
}
```

### Evento: baja_empleado

```json
{
  "evento": "baja_empleado",
  "timestamp": "2026-03-31T23:59:00Z",
  "empleado": {
    "id": "12345",
    "rut": "12345678-9",
    "nombre": "Juan",
    "apellido_paterno": "Perez",
    "fecha_baja": "2026-03-31",
    "motivo_baja": "Renuncia voluntaria"
  }
}
```

### Evento: modificacion_empleado

Incluye solo los campos que cambiaron:

```json
{
  "evento": "modificacion_empleado",
  "timestamp": "2026-04-15T10:00:00Z",
  "empleado": {
    "id": "12345",
    "rut": "12345678-9",
    "cargo": "Ejecutivo Finanzas",
    "departamento": "Finanzas",
    "manager_rut": "55555555-5"
  }
}
```

---

## Validacion de firma del webhook

Talana firma cada webhook con HMAC-SHA256 usando el `TALANA_WEBHOOK_SECRET`. Verificar la firma antes de procesar cualquier evento:

```python
import hmac
import hashlib

def verify_talana_webhook(payload_bytes: bytes, signature_header: str, secret: str) -> bool:
    """
    Verifica la firma HMAC-SHA256 del webhook de Talana.
    signature_header: valor del header X-Talana-Signature
    """
    expected = hmac.new(
        secret.encode("utf-8"),
        payload_bytes,
        hashlib.sha256
    ).hexdigest()
    received = signature_header.replace("sha256=", "")
    return hmac.compare_digest(expected, received)
```

**Si la firma no es valida:** rechazar el request con HTTP 401 y registrar el intento en el log. No procesar el payload.

---

## Endpoints de la API REST de Talana

### Obtener datos de empleado por ID

```http
GET /api/empleados/{talana_id}
Authorization: Token {TALANA_API_KEY}
```

Respuesta:
```json
{
  "id": "12345",
  "rut": "12345678-9",
  "nombre_completo": "Juan Perez Gonzalez",
  "cargo": "Analista RRHH",
  "departamento": "Recursos Humanos",
  "estado": "activo",
  "ms365_id": null,
  "email_corporativo": null
}
```

### Actualizar empleado (escribir de vuelta desde M365)

```http
PATCH /api/empleados/{talana_id}
Authorization: Token {TALANA_API_KEY}
Content-Type: application/json

{
  "ms365_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "email_corporativo": "jperez@empresa.com",
  "estado": "activo"
}
```

### Listar empleados activos (polling fallback)

```http
GET /api/empleados?estado=activo&page=1&page_size=100
Authorization: Token {TALANA_API_KEY}
```

---

## Mapeo de campos Talana → Entra ID

| Campo Talana | Campo Entra ID | Transformacion |
|---|---|---|
| `nombre` + `apellido_paterno` + `apellido_materno` | `displayName` | Concatenar |
| `nombre` | `givenName` | Directo |
| `apellido_paterno` | `surname` | Directo |
| `rut` | `employeeId` | Directo (formato: 12345678-9) |
| `cargo` | `jobTitle` | Directo |
| `departamento` | `department` | Directo |
| `nombre` + `apellido_paterno` (normalizado) | `mailNickname` | Minuscula, sin tildes ni espacios |
| `email_personal` | No se usa en M365 | Solo referencia |
| `manager_rut` | `manager` (via resolve) | RUT → buscar en Entra ID por `employeeId` |

**Generacion del UPN (email corporativo):**

```python
def generate_upn(nombre: str, apellido: str, dominio: str = "empresa.com") -> str:
    """
    Genera el userPrincipalName a partir del nombre y apellido.
    Ejemplo: Juan Perez -> jperez@empresa.com
    """
    inicial = nombre[0].lower()
    apellido_norm = apellido.lower().replace(" ", "").translate(str.maketrans("áéíóú", "aeiou"))
    return f"{inicial}{apellido_norm}@{dominio}"
```

---

## Polling fallback

Si los webhooks no estan disponibles, el sistema puede consultar Talana periodicamente para detectar cambios:

```python
# Ejecutar via cron job o Azure Timer Function cada 15 minutos
def poll_talana_changes():
    empleados = talana_client.list_employees(estado="activo")
    for empleado in empleados:
        if not empleado.ms365_id:
            # Nuevo empleado sin cuenta M365 → ejecutar onboarding
            onboard_user(empleado)
        elif empleado.estado == "inactivo" and has_active_m365_account(empleado.ms365_id):
            # Empleado dado de baja en Talana pero con cuenta activa → offboarding
            offboard_user(empleado)
```

> El polling es mas lento y puede tener latencia de hasta 15 minutos. El webhook es siempre preferido.

---

## Troubleshooting

| Problema | Causa probable | Solucion |
|---|---|---|
| Webhook no llega | URL incorrecta o firewall | Verificar URL en configuracion de Talana y que la Azure Function es publica |
| Firma invalida | `TALANA_WEBHOOK_SECRET` no coincide | Regenerar el secreto en Talana y actualizar `.env` |
| `401 Unauthorized` en API | `TALANA_API_KEY` invalida o expirada | Regenerar la API key en Talana > Configuracion > API |
| `404 Not Found` en PATCH empleado | ID de empleado incorrecto | Verificar el `talana_id` con un GET primero |
| Datos desincronizados | Webhook perdido o procesado con error | Ejecutar reconciliacion manual con polling |

---

## Como se conecta con los flujos de las guias

| Guia | Operaciones Talana |
|---|---|
| [Alta de Usuario](../guias/ALTA_USUARIO.md) | Recibe webhook `alta_empleado`; al final PATCH `ms365_id` y `email_corporativo` |
| [Baja de Usuario](../guias/BAJA_USUARIO.md) | Recibe webhook `baja_empleado`; al final PATCH `estado: inactivo` |
| [Cambio de Rol](../guias/CAMBIO_ROL.md) | Recibe webhook `modificacion_empleado`; al final PATCH `cargo` y `departamento` |
