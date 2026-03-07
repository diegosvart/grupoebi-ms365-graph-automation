# grupoebi-ms365-graph-automation

Herramienta CLI en Python para automatizar entornos de proyecto en Microsoft 365 mediante la Graph API. Crea y gestiona Planes en Microsoft Planner, canales en Teams y estructuras de carpetas en SharePoint a partir de archivos CSV, sin intervención manual en la interfaz web.

---

## Tabla de contenidos

- [Descripcion general](#descripcion-general)
- [Acciones funcionales actuales](#acciones-funcionales-actuales)
- [Arquitectura](#arquitectura)
- [Requisitos](#requisitos)
- [Instalacion](#instalacion)
- [Configuracion](#configuracion)
- [Uso](#uso)
- [Estructura del proyecto](#estructura-del-proyecto)
- [Escalamiento hacia otros servicios](#escalamiento-hacia-otros-servicios)
- [Contribuir](#contribuir)
- [Seguridad](#seguridad)
- [Licencia](#licencia)

---

## Descripcion general

Este proyecto resuelve la friccion operativa de crear entornos digitales de proyecto de forma repetitiva y manual dentro del ecosistema Microsoft 365. A traves de un archivo CSV estructurado y credenciales de una App Registration en Azure Entra ID, el CLI orquesta multiples llamadas a la Graph API para dejar un proyecto listo para operar en minutos.

**Tecnologias principales:** Python 3.x · Microsoft Graph API v1.0 · httpx · python-dotenv · pytest

---

## Acciones funcionales actuales

Las acciones estan organizadas por servicio de destino dentro de Microsoft 365.

### Microsoft Planner

| Accion | Descripcion |
|---|---|
| Crear plan completo | Genera el plan, configura etiquetas de categoria, crea todos los buckets y tareas en una sola ejecucion |
| Crear solo encabezado de plan | Crea el plan con sus etiquetas sin buckets ni tareas |
| Agregar buckets a plan existente | Incorpora nuevos buckets a un plan ya creado, identificado por su PlanID |
| Agregar tareas a plan/bucket existente | Inserta tareas en un plan y bucket existentes usando sus IDs |
| Listar planes del grupo | Muestra todos los planes vinculados al grupo M365 en formato tabla |
| Eliminar planes | Seleccion interactiva y eliminacion de planes con confirmacion |
| Asignar tareas por email | Resuelve direcciones de correo a GUIDs de Azure Entra ID para asignar responsables |
| Configurar checklists y descripciones | Agrega subitems y texto detallado a cada tarea via PATCH |

### Microsoft Teams

| Accion | Descripcion |
|---|---|
| Crear canal de proyecto | Genera un canal estandar dentro del Team del grupo |
| Agregar miembros al Team | Incorpora usuarios con rol owner o member segun su funcion en el proyecto |
| Anclar pestaña de Planner | Vincula el plan recien creado como tab dentro del canal del proyecto |

### Microsoft SharePoint / OneDrive

| Accion | Descripcion |
|---|---|
| Crear jerarquia de carpetas | Genera la estructura de directorios del proyecto en el sitio SharePoint del grupo |
| Subir archivos de plantilla | Copia documentos base (acta de inicio, fichas) a la carpeta del proyecto al momento de su creacion |
| Listar contenido de biblioteca | Navega y muestra elementos de una biblioteca de documentos SharePoint |

### Resolucion de identidades (Azure Entra ID — lectura)

| Accion | Descripcion |
|---|---|
| Resolver email a GUID | Consulta `/users/{email}` para obtener el identificador unico del usuario y asignarlo en Planner/Teams |
| Listar usuarios del grupo | Consulta miembros de un grupo M365 para validar pertenencia antes de operar |

> Todas las acciones de escritura soportan modo `--dry-run`, que valida el CSV y simula el flujo sin realizar ninguna llamada a la API.

---

## Arquitectura

```
CSV de entrada
      |
      v
 planner_import.py / create_environment.py
      |
      |-- parse_csv()         Normaliza y valida filas
      |-- resolve_email()     Resuelve emails -> GUIDs (con cache en memoria)
      |-- graph_request()     Cliente httpx con reintentos en 429
      |
      v
 Microsoft Graph API v1.0
      |
      |-- /planner/*          Planes, buckets, tareas
      |-- /teams/*            Canales, miembros, tabs
      |-- /sites/*            SharePoint, carpetas, archivos
      |-- /users/*            Resolucion de identidades
      |
      v
 Microsoft 365 (Planner + Teams + SharePoint)
```

**Autenticacion:** Client Credentials Flow (OAuth 2.0) via `MicrosoftAuthManager`. Las credenciales (Tenant ID, Client ID, Client Secret) se cargan desde variables de entorno. El token se renueva automaticamente cuando expira.

**Manejo de throttling:** La funcion `graph_request()` intercepta respuestas HTTP 429 y respeta el header `Retry-After` antes de reintentar, garantizando que el script no rompa los limites de tasa de la Graph API.

**Idempotencia:** Las operaciones de creacion de canales y carpetas verifican existencia previa antes de crear, evitando duplicados en ejecuciones repetidas.

---

## Requisitos

- Python 3.10 o superior
- Acceso a red corporativa o VPN con salida a `graph.microsoft.com`
- Una **App Registration** en Azure Entra ID con los siguientes permisos de aplicacion (sin usuario):

| Permiso | Tipo | Proposito |
|---|---|---|
| `Tasks.ReadWrite` | Application | Crear y modificar tareas en Planner |
| `Tasks.ReadWrite.Shared` | Application | Acceder a planes compartidos del grupo |
| `Group.ReadWrite.All` | Application | Crear planes vinculados a grupos M365 |
| `User.Read.All` | Application | Resolver emails a GUIDs |
| `Team.ReadBasic.All` | Application | Leer informacion de Teams |
| `Channel.Create` | Application | Crear canales en Teams |
| `TeamMember.ReadWrite.All` | Application | Agregar miembros al Team |
| `Sites.ReadWrite.All` | Application | Operar sobre SharePoint |
| `Files.ReadWrite.All` | Application | Subir archivos a OneDrive/SharePoint |

---

## Instalacion

```bash
# 1. Clonar el repositorio
git clone https://github.com/diegosvart/grupoebi-ms365-graph-automation.git
cd grupoebi-ms365-graph-automation

# 2. Crear entorno virtual
python -m venv .venv
source .venv/bin/activate        # Linux/macOS
.\.venv\Scripts\activate         # Windows

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Configurar variables de entorno
cp .env.example .env
# Editar .env con las credenciales de la App Registration
```

---

## Configuracion

Editar el archivo `.env` con las credenciales de Azure:

```env
AZURE_TENANT_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
AZURE_CLIENT_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
AZURE_CLIENT_SECRET=tu-secreto-aqui
```

> **Nunca** incluir el `.env` en control de versiones. El archivo `.gitignore` ya lo excluye.

### Variables opcionales

```env
GROUP_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx   # ID del grupo M365 destino
MCP_PATH=/ruta/al/mcp-server                    # Ruta del servidor MCP alternativo
```

---

## Uso

### Crear un entorno de proyecto completo

```bash
python planner_import.py --csv templates/full.csv --group-id <GUID>
```

### Modos disponibles

```bash
# Crear plan completo (encabezado + buckets + tareas)
python planner_import.py --mode full --csv mi_plan.csv --group-id <GUID>

# Solo crear el encabezado del plan
python planner_import.py --mode plan --csv mi_plan.csv --group-id <GUID>

# Agregar buckets a plan existente
python planner_import.py --mode buckets --csv buckets.csv --group-id <GUID>

# Agregar tareas a plan y bucket existentes
python planner_import.py --mode tasks --csv tasks.csv --group-id <GUID>

# Listar planes del grupo
python planner_import.py --mode list --group-id <GUID>

# Filtrar planes por nombre
python planner_import.py --mode list --filter "Q1 2026" --group-id <GUID>

# Eliminar planes (interactivo)
python planner_import.py --mode delete --group-id <GUID>

# Simular sin llamadas a la API
python planner_import.py --mode full --csv mi_plan.csv --group-id <GUID> --dry-run
```

### Crear entorno completo de proyecto (Teams + Planner + SharePoint)

```bash
python create_environment.py --csv templates/default_init/Planner_Template_DEFAULT_V3.csv --group-id <GUID>
```

### Formato del CSV

El CSV usa `;` como delimitador. Las fechas van en formato `DDMMYYYY`.

```csv
PlanName;BucketName;TaskTitle;AssignedTo;DueDate;Priority;Description;Checklist
Proyecto Alpha;Inicio;Definir alcance;pm@empresa.com;01042026;urgent;Documento de alcance inicial;"Revisar brief;Validar con sponsor"
Proyecto Alpha;Inicio;Kick-off meeting;lider@empresa.com;05042026;important;;
```

**Valores de prioridad aceptados:** `urgent` · `important` · `medium` · `low` · `none`

### Ejecutar tests

```bash
pytest
pytest tests/test_graph_api.py -v        # Test especifico
pytest --co -q                           # Solo listar tests sin ejecutar
```

---

## Estructura del proyecto

```
grupoebi-ms365-graph-automation/
|
|-- planner_import.py          # CLI principal: importacion desde CSV a Planner
|-- create_environment.py      # Orquestador: crea entorno completo (Teams+Planner+SP)
|-- pytest.ini                 # Configuracion de pytest
|
|-- templates/                 # Plantillas CSV listas para usar
|   |-- full.csv               # Plan completo: encabezado + buckets + tareas
|   |-- plan.csv               # Solo encabezado del plan
|   |-- buckets.csv            # Solo buckets
|   |-- tasks.csv              # Solo tareas
|   `-- default_init/          # Plantillas de inicio de proyecto
|       |-- Planner_Template_DEFAULT_V3.csv
|       |-- Acta_de_Inicio_de_Proyecto.docx
|       `-- Ficha_de_Proyecto_Nueva_Iniciativa.docx
|
|-- tests/                     # Suite de pruebas
|   |-- fixtures/              # Datos CSV de prueba
|   |-- conftest.py            # Configuracion y fixtures de pytest
|   |-- test_graph_api.py      # Tests de llamadas a la Graph API
|   |-- test_orchestrators.py  # Tests de flujos de orquestacion
|   |-- test_transforms.py     # Tests de transformaciones CSV
|   `-- test_create_environment.py
|
|-- docs/                      # Documentacion tecnica
|   |-- ESCALAMIENTO_GRAPH.md  # Guia de escalamiento de la Graph API
|   `-- deep-research-github-agent.md
|
|-- hooks/                     # Hooks de sesion de Claude Code
|   |-- guard-sensitive.py     # Detecta y bloquea exposicion de secretos
|   |-- session-start.py       # Validaciones al inicio de sesion
|   `-- session-end.py         # Acciones al cerrar sesion
|
|-- plans/                     # Documentos de planificacion del proyecto
|-- .claude/                   # Configuracion de Claude Code (agentes, reglas)
|-- .env.example               # Plantilla de variables de entorno
|-- CLAUDE.md                  # Instrucciones para el agente de IA
|-- AGENTS.md                  # Definicion del agente Git especializado
`-- MANUAL.md                  # Manual de usuario detallado
```

---

## Escalamiento hacia otros servicios

La base de autenticacion (Client Credentials + Graph API) y el cliente HTTP ya implementados permiten extender este proyecto hacia cualquier recurso de la Graph API sin cambios estructurales. A continuacion se describen los escalamientos de mayor impacto operativo.

### Azure Entra ID — Gestion de identidades

El escalamiento mas directo: pasar de *leer* usuarios (resolucion de email a GUID) a *operar* sobre ellos.

| Accion | Endpoint | Caso de uso |
|---|---|---|
| Alta de usuario | `POST /users` | Onboarding automatizado al crear un proyecto |
| Baja de usuario | `DELETE /users/{id}` o deshabilitar cuenta | Offboarding al cerrar proyecto |
| Resetear contrasena | `POST /users/{id}/authentication/passwordMethods/{id}/resetPassword` | Soporte a PM al incorporar colaboradores externos |
| Asignar licencia M365 | `POST /users/{id}/assignLicense` | Activar licencia E3/E5 al dar de alta |
| Agregar a grupo de seguridad | `POST /groups/{id}/members/$ref` | Control de acceso a recursos corporativos |
| Quitar de grupo | `DELETE /groups/{id}/members/{id}/$ref` | Revocar acceso al terminar colaboracion |
| Listar usuarios por departamento | `GET /users?$filter=department eq 'TI'` | Asignacion automatica de tareas por area |

**Permiso adicional requerido:** `User.ReadWrite.All` · `Directory.ReadWrite.All`

### Microsoft Exchange / Outlook — Comunicaciones

| Accion | Endpoint | Caso de uso |
|---|---|---|
| Enviar email de bienvenida | `POST /users/{id}/sendMail` | Notificar al equipo cuando el entorno esta listo |
| Crear evento de kick-off | `POST /users/{id}/events` | Agendar reunion de inicio automaticamente |
| Crear sala de reunion | `POST /places` | Reservar sala al programar eventos del proyecto |
| Crear grupo de distribucion | `POST /groups` con `mailEnabled: true` | Canal de comunicacion del equipo por correo |

**Permiso adicional requerido:** `Mail.Send` · `Calendars.ReadWrite`

### Microsoft Intune — Gestion de dispositivos

| Accion | Endpoint | Caso de uso |
|---|---|---|
| Enrolar dispositivo | `POST /deviceManagement/managedDevices` | Registrar equipo de colaborador nuevo |
| Asignar politica de compliance | `POST /deviceManagement/deviceCompliancePolicies/{id}/assign` | Aplicar politicas al incorporar usuario |
| Listar dispositivos del usuario | `GET /users/{id}/managedDevices` | Auditar equipos al hacer offboarding |

**Permiso adicional requerido:** `DeviceManagementManagedDevices.ReadWrite.All`

### Microsoft Defender / Purview — Seguridad y compliance

| Accion | Endpoint | Caso de uso |
|---|---|---|
| Crear etiqueta de sensibilidad | Purview API | Clasificar documentos del proyecto al crearlos |
| Auditar accesos | `GET /auditLogs/signIns` | Reportes de actividad en el proyecto |
| Crear alerta de DLP | Purview API | Proteger informacion sensible de proyectos criticos |

**Permiso adicional requerido:** `AuditLog.Read.All` · `InformationProtectionPolicy.Read`

### Power Automate / Logic Apps — Automatizacion de bajo codigo

En lugar de ampliar este CLI, flujos de mayor complejidad pueden implementarse en Power Automate consumiendo la Graph API via conectores o HTTP custom, con este proyecto como referencia de endpoints y payloads.

| Integracion | Descripcion |
|---|---|
| Trigger al crear plan | Notificar por Teams cuando un plan nuevo esta disponible |
| Sincronizacion bidireccional | Actualizar tareas de Planner desde sistemas externos (Jira, Azure DevOps) |
| Reporte semanal automatico | Generar resumen de avance de tareas cada lunes y enviarlo por correo |

### Resumen de permisos por area de escalamiento

```
Permisos actuales
  Tasks.ReadWrite, Tasks.ReadWrite.Shared
  Group.ReadWrite.All, User.Read.All
  Channel.Create, TeamMember.ReadWrite.All
  Sites.ReadWrite.All, Files.ReadWrite.All

Escalamiento Entra ID (identidades)
  + User.ReadWrite.All
  + Directory.ReadWrite.All

Escalamiento Exchange/Outlook
  + Mail.Send
  + Calendars.ReadWrite

Escalamiento Intune (dispositivos)
  + DeviceManagementManagedDevices.ReadWrite.All

Escalamiento Defender/Purview
  + AuditLog.Read.All
  + InformationProtectionPolicy.Read
```

> Todos los permisos anteriores son de tipo **Application** (sin usuario interactivo), compatibles con la arquitectura Client Credentials ya implementada.

---

## Contribuir

### Flujo de trabajo

```bash
# 1. Crear rama desde main
git checkout -b feature/nombre-descriptivo

# 2. Desarrollar y testear
pytest

# 3. Commit con mensaje convencional
git commit -m "feat: agregar resolucion de grupos de seguridad en Entra ID"

# 4. Abrir Pull Request hacia main
```

### Convenciones de commits

| Prefijo | Uso |
|---|---|
| `feat:` | Nueva funcionalidad |
| `fix:` | Correccion de error |
| `docs:` | Cambios solo en documentacion |
| `test:` | Agregar o modificar tests |
| `refactor:` | Cambio de codigo sin corregir bug ni agregar feature |
| `chore:` | Tareas de mantenimiento (dependencias, CI) |

### Checklist para Pull Request

- [ ] Los tests existentes pasan (`pytest`)
- [ ] Se agregaron tests para la nueva funcionalidad
- [ ] El modo `--dry-run` funciona sin credenciales
- [ ] No se exponen tokens, secretos ni GUIDs reales en el codigo
- [ ] El CSV de ejemplo en `templates/` refleja el nuevo comportamiento si aplica

---

## Seguridad

- **Nunca** hacer commit del archivo `.env` ni de credenciales en texto plano.
- Las App Registrations deben usar el **principio de minimo privilegio**: otorgar solo los permisos necesarios para las operaciones activas.
- Rotar el `AZURE_CLIENT_SECRET` cada 90 dias y registrarlo en el portal de Azure.
- El hook `hooks/guard-sensitive.py` detecta patrones de secretos antes de cada sesion de agente.
- En entornos de produccion, usar **Azure Key Vault** en lugar de archivos `.env` para almacenar credenciales.

Para reportar una vulnerabilidad de seguridad, contactar directamente al mantenedor del repositorio sin abrir un issue publico.

---

## Licencia

Uso interno — Grupo EBI. Ver `LICENSE` para detalles.
