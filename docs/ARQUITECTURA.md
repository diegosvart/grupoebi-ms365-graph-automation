# Arquitectura del Sistema

## Diagrama general

```
┌──────────────────────────────────────────────────────────────────┐
│                        FUENTES DE TRIGGER                        │
│                                                                  │
│  Talana HRIS ──webhook──► Azure Function  ◄──formulario── Teams  │
│  (alta/baja empleado)     (HTTP endpoint)   (Power Automate)     │
└────────────────────────────────┬─────────────────────────────────┘
                                 │
                                 ▼
┌──────────────────────────────────────────────────────────────────┐
│                   CAPA DE ORQUESTACION (Python)                  │
│                                                                  │
│   planner_import.py          create_environment.py               │
│   (importacion CSV →         (nuevo proyecto: Teams +            │
│    Planner)                   Planner + SharePoint)              │
│                                                                  │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │                   Modulos compartidos                    │   │
│   │  MicrosoftAuthManager  graph_request()  parse_csv()     │   │
│   │  resolve_email()       throttle_handler()               │   │
│   └─────────────────────────────────────────────────────────┘   │
└────────────────────────────────┬─────────────────────────────────┘
                                 │
                     Client Credentials Flow
                     (OAuth 2.0 — sin usuario)
                                 │
                                 ▼
┌──────────────────────────────────────────────────────────────────┐
│                    MICROSOFT GRAPH API v1.0                      │
│               https://graph.microsoft.com/v1.0/                 │
│                                                                  │
│  /users/*           Azure Entra ID — identidades y licencias    │
│  /groups/*          Grupos M365 — seguridad y distribucion      │
│  /planner/*         Microsoft Planner — planes y tareas         │
│  /teams/*           Microsoft Teams — canales y miembros        │
│  /sites/*           SharePoint — documentos y carpetas          │
│  /deviceManagement/ Microsoft Intune — dispositivos             │
└────────────────────────────────┬─────────────────────────────────┘
                                 │
                                 ▼
┌──────────────────────────────────────────────────────────────────┐
│                     MICROSOFT 365 (servicios)                    │
│                                                                  │
│  Azure Entra ID  │  Exchange Online  │  Microsoft Teams          │
│  Planner         │  SharePoint       │  Microsoft Intune         │
└──────────────────────────────────────────────────────────────────┘
                                 │
                                 │ actualizacion de estado
                                 ▼
                          Talana HRIS
                    (ms365_id, email, estado)
```

---

## Flujo de autenticacion

```
Python CLI
    │
    │ POST /[tenant-id]/oauth2/v2.0/token
    │ grant_type=client_credentials
    │ client_id=[AZURE_CLIENT_ID]
    │ client_secret=[AZURE_CLIENT_SECRET]
    │ scope=https://graph.microsoft.com/.default
    │
    ▼
Azure Entra ID (STS)
    │
    │ access_token (JWT, expira en 3600s)
    │
    ▼
Python CLI (MicrosoftAuthManager)
    │
    │ Authorization: Bearer [access_token]
    │ GET/POST/PATCH https://graph.microsoft.com/v1.0/...
    │
    ▼
Microsoft Graph API
```

**Renovacion automatica:** `MicrosoftAuthManager` verifica la expiracion del token antes de cada llamada y solicita uno nuevo si ha expirado o le quedan menos de 60 segundos de vida.

---

## Descripcion de modulos

### `planner_import.py`

CLI principal para importacion de planes desde CSV hacia Microsoft Planner.

**Modos:**

| Modo | Que hace |
|---|---|
| `full` | Crea encabezado del plan, labels, buckets y tareas |
| `plan` | Solo crea el encabezado del plan con labels |
| `buckets` | Agrega buckets a un plan existente |
| `tasks` | Agrega tareas a plan y bucket existentes |
| `list` | Lista planes del grupo en formato tabla |
| `delete` | Eliminacion interactiva de planes con confirmacion |

**Argumentos:**

```bash
python planner_import.py \
  --mode full \
  --csv templates/full.csv \
  --group-id <GUID> \
  [--dry-run]
```

### `create_environment.py`

Orquestador de alto nivel que crea un entorno de proyecto completo en una sola ejecucion:

1. Canal de Teams + agrega miembros (PM como owner, equipo como members)
2. Plan de Planner completo (encabezado + labels + buckets + tareas)
3. Estructura de carpetas en SharePoint
4. Sube archivos de plantilla (Acta de Inicio, Ficha de Proyecto)
5. Ancla la pestana de Planner en el canal de Teams

**Uso:**

```bash
python create_environment.py \
  --csv templates/default_init/Planner_Template_DEFAULT_V3.csv \
  --group-id <GUID> \
  [--dry-run]
```

### `MicrosoftAuthManager`

Clase responsable de:
- Obtener y cachear el access token via Client Credentials Flow
- Renovar el token automaticamente antes de su expiracion
- Exponer el token como header `Authorization: Bearer` para `graph_request()`

### `graph_request()`

Funcion central de todas las llamadas HTTP a la Graph API:
- Manejo de reintentos con backoff exponencial
- Intercepta HTTP 429 (throttling) y respeta el header `Retry-After`
- Propaga errores estructurados con el cuerpo de respuesta de la API

### `resolve_email()`

Resuelve una direccion de email a un GUID de Entra ID llamando a `GET /users/{email}`. Usa cache en memoria para evitar llamadas redundantes dentro de la misma ejecucion.

### `parse_csv()`

Lee y valida el archivo CSV de entrada:
- Delimitador: punto y coma (`;`)
- Fechas: formato `DDMMYYYY`
- Prioridades aceptadas: `urgent`, `important`, `medium`, `low`, `none`
- Devuelve lista de diccionarios normalizados listos para la API

---

## Variables de entorno

Ver [`.env.example`](../.env.example) para la lista completa con descripcion de cada variable.

| Variable | Uso | Obligatoria |
|---|---|---|
| `AZURE_TENANT_ID` | ID del tenant de Azure | Si |
| `AZURE_CLIENT_ID` | ID de la App Registration | Si |
| `AZURE_CLIENT_SECRET` | Secreto de la App Registration | Si |
| `GROUP_ID` | ID del grupo M365 destino | Si (o via `--group-id`) |
| `SHAREPOINT_SITE_ID` | ID del sitio SharePoint | Para operaciones SharePoint |
| `SHAREPOINT_SITE_URL` | URL del sitio SharePoint | Para operaciones SharePoint |
| `TALANA_API_KEY` | API Key de Talana HRIS | Para flujos con Talana |
| `TALANA_WEBHOOK_SECRET` | Secreto de validacion webhook | Para recibir webhooks Talana |
| `AZURE_FUNCTION_URL` | URL de la Azure Function | Para usuarios no tecnicos |
| `LOG_LEVEL` | Nivel de logging (default: INFO) | No |
| `DEFAULT_DRY_RUN` | Activar dry-run por defecto | No |
| `MAX_RETRIES` | Reintentos en throttling | No (default: 3) |

---

## Manejo de errores y throttling

La Graph API puede devolver HTTP 429 cuando se supera el limite de solicitudes por segundo. El manejador de throttling implementado:

```
graph_request() recibe respuesta 429
    │
    │ Lee header: Retry-After: N (segundos)
    │
    ├── Si N <= 60: espera N segundos y reintenta
    ├── Si N > 60: lanza excepcion con mensaje claro
    └── Maximo MAX_RETRIES intentos antes de fallar
```

---

## Idempotencia

Las siguientes operaciones verifican existencia antes de crear:

| Operacion | Verificacion |
|---|---|
| Crear canal de Teams | `GET /teams/{id}/channels?$filter=displayName eq '...'` |
| Crear carpeta SharePoint | `GET /drives/{id}/root:/{ruta}` |
| Crear plan de Planner | Lista planes del grupo antes de crear |
| Agregar miembro a Team | Verifica si el usuario ya es miembro |

Las operaciones sobre usuarios (alta, baja, licencias) **no son idempotentes por defecto**. Las guias de usuario advierten esto y exigen dry-run previo.

---

## Estructura de archivos

```
grupoebi-ms365-graph-automation/
|-- planner_import.py          CLI: importacion CSV → Planner
|-- create_environment.py      Orquestador: Teams + Planner + SharePoint
|-- requirements.txt           Dependencias Python
|-- pytest.ini                 Configuracion de pytest
|
|-- templates/                 Plantillas CSV
|   |-- full.csv               Plan completo
|   |-- plan.csv               Solo encabezado
|   |-- buckets.csv            Solo buckets
|   |-- tasks.csv              Solo tareas
|   `-- default_init/          Plantillas de inicio de proyecto
|       |-- Planner_Template_DEFAULT_V3.csv
|       |-- onboarding/        CSVs de onboarding por perfil de rol
|       |   |-- rrhh_analyst.csv
|       |   |-- gerente.csv
|       |   |-- operaciones.csv
|       |   `-- finanzas.csv
|       |-- Acta_de_Inicio_de_Proyecto.docx
|       `-- Ficha_de_Proyecto_Nueva_Iniciativa.docx
|
|-- tests/                     Suite de pruebas
|   |-- fixtures/              Datos CSV de prueba (datos ficticios)
|   |-- conftest.py            Fixtures de pytest
|   |-- test_graph_api.py      Tests de llamadas a la API
|   |-- test_orchestrators.py  Tests de flujos de orquestacion
|   |-- test_transforms.py     Tests de transformaciones CSV
|   `-- test_create_environment.py
|
|-- docs/                      Documentacion
|   |-- ARQUITECTURA.md        (este archivo)
|   |-- PERFILES_ROLES.md      Catalogo de perfiles por cargo
|   |-- API_REFERENCIA.md      Endpoints Graph implementados
|   |-- TESTING.md             Estrategia de tests
|   |-- GLOSARIO.md            Glosario de terminos
|   |-- guias/                 Guias para usuarios no tecnicos
|   `-- integraciones/         Documentacion por servicio
|
|-- hooks/                     Hooks de Claude Code
|   |-- guard-sensitive.py     Detecta exposicion de secretos
|   |-- session-start.py       Validaciones al inicio
|   `-- session-end.py         Acciones al cerrar
|
|-- .github/                   Plantillas de GitHub
|-- .claude/                   Configuracion Claude Code
|-- .env.example               Plantilla de variables de entorno
|-- .gitignore
|-- SECURITY.md
|-- CONTRIBUTING.md
|-- CHANGELOG.md
`-- README.md
```
