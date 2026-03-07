# Security Policy / Politica de Seguridad

## English

### Supported Versions

| Version | Supported |
|---|---|
| main (latest) | Yes |
| older branches | No |

### Reporting a Vulnerability

**Do NOT open a public GitHub issue for security vulnerabilities.**

Contact the repository maintainer directly via email. Include:
- Description of the vulnerability
- Steps to reproduce
- Potential impact assessment
- Suggested remediation (if any)

You will receive acknowledgment within 48 business hours and a resolution timeline within 5 business days.

---

## Espanol

### Politica de seguridad

Este documento describe los controles de seguridad del proyecto `grupoebi-ms365-graph-automation`, los permisos de la App Registration de Azure, los procedimientos de rotacion de secretos y las responsabilidades de cada rol.

---

## App Registration — Permisos de la Graph API

La App Registration en Azure Entra ID usa **Client Credentials Flow** (sin usuario interactivo). Todos los permisos son de tipo **Application**, no Delegated.

### Permisos activos (funcionalidad implementada)

| Permiso | Tipo | Justificacion |
|---|---|---|
| `Tasks.ReadWrite` | Application | Crear y modificar tareas en Planner |
| `Tasks.ReadWrite.Shared` | Application | Acceder a planes compartidos de grupo M365 |
| `Group.ReadWrite.All` | Application | Crear planes vinculados a grupos M365 |
| `User.Read.All` | Application | Resolver emails a GUIDs de Entra ID |
| `Team.ReadBasic.All` | Application | Leer informacion de Teams |
| `Channel.Create` | Application | Crear canales de proyecto en Teams |
| `TeamMember.ReadWrite.All` | Application | Agregar/quitar miembros del Team |
| `Sites.ReadWrite.All` | Application | Operar sobre bibliotecas de SharePoint |
| `Files.ReadWrite.All` | Application | Subir archivos de plantilla a OneDrive/SharePoint |

### Permisos para escalamientos futuros (no activos por defecto)

| Permiso | Tipo | Cuando agregar |
|---|---|---|
| `User.ReadWrite.All` | Application | Al implementar onboarding/offboarding de usuarios |
| `Directory.ReadWrite.All` | Application | Al gestionar grupos de seguridad dinamicamente |
| `Mail.Send` | Application | Al implementar emails de bienvenida/offboarding |
| `Calendars.ReadWrite` | Application | Al crear eventos de kick-off automaticamente |
| `DeviceManagementManagedDevices.ReadWrite.All` | Application | Al implementar enrollment Intune |
| `DeviceManagementConfiguration.ReadWrite.All` | Application | Al asignar politicas de compliance |

> **Principio de minimo privilegio:** Agregar permisos solo cuando la funcionalidad que los requiere este en produccion. Documentar cada adicion en este archivo y en el CHANGELOG.

---

## Gestion de Credenciales

### Que se considera credencial sensible

- `AZURE_TENANT_ID` — identifica el tenant de Azure del cliente
- `AZURE_CLIENT_ID` — identifica la App Registration
- `AZURE_CLIENT_SECRET` — secreto de la App Registration (equivale a una contrasena)
- `TALANA_API_KEY` — llave API del HRIS Talana
- `WEBHOOK_SECRET` — secreto de validacion de webhooks entrantes
- `AZURE_FUNCTION_KEY` — llave de autenticacion de Azure Functions

### Reglas de manejo

1. **Nunca** incluir credenciales reales en el codigo fuente, commits o comentarios.
2. **Nunca** compartir credenciales por canales no cifrados (Slack, email, Teams chat).
3. **Siempre** usar el archivo `.env` (excluido de git por `.gitignore`) para desarrollo local.
4. **En produccion:** usar Azure Key Vault con referencias de secretos gestionadas.
5. El archivo `.env.example` solo puede contener placeholders, nunca valores reales.

### Ciclo de vida de secretos

| Secreto | Rotacion maxima | Responsable |
|---|---|---|
| `AZURE_CLIENT_SECRET` | Cada 90 dias | Administrador Azure |
| `TALANA_API_KEY` | Segun politica Talana | Administrador HRIS |
| `WEBHOOK_SECRET` | Cada 180 dias o tras incidente | Administrador Azure |
| `AZURE_FUNCTION_KEY` | Cada 180 dias | Administrador Azure |

**Procedimiento de rotacion de `AZURE_CLIENT_SECRET`:**

```
1. Acceder a Azure Portal > Entra ID > App Registrations > [nombre-app] > Certificates & secrets
2. Crear nuevo secreto con fecha de expiracion no mayor a 90 dias
3. Copiar el valor INMEDIATAMENTE (no se vuelve a mostrar)
4. Actualizar el secreto en Azure Key Vault (produccion) y en .env local (desarrollo)
5. Validar que el sistema funciona con el nuevo secreto ejecutando: python planner_import.py --mode list --group-id <GUID>
6. Eliminar el secreto anterior del portal de Azure
7. Registrar la rotacion en el CHANGELOG.md
```

---

## Controles de Seguridad del Repositorio

### Hook: guard-sensitive.py

El archivo `hooks/guard-sensitive.py` se ejecuta antes de cada sesion de agente de IA y detecta los siguientes patrones en archivos staged o modificados:

- GUIDs con formato UUID real que no sean placeholders
- Cadenas que coincidan con patrones de secretos de Azure (`xxxxx~xxxxx`)
- Emails con dominio corporativo real
- Rutas absolutas con nombre de usuario real
- Numeros de RUT chilenos (formato XX.XXX.XXX-X)

Si detecta un patron sensible, la sesion se interrumpe y se muestra una advertencia.

### .gitignore

El archivo `.gitignore` excluye:
- `.env` y variantes (`.env.local`, `.env.production`, etc.)
- Directorios de entorno virtual (`.venv/`, `venv/`)
- Cache de Python (`__pycache__/`, `*.pyc`)
- Todos los subdirectorios de proyectos no relacionados en el directorio raiz

### Revision de Pull Requests

Todo PR que modifique los siguientes archivos requiere revision obligatoria del security lead:
- `hooks/`
- `SECURITY.md`
- `.env.example`
- Cualquier archivo que contenga endpoints de la Graph API o logica de autenticacion

Ver `.github/CODEOWNERS` para la asignacion de revisores.

---

## Clasificacion de Datos

| Tipo de dato | Clasificacion | Almacenamiento permitido |
|---|---|---|
| `AZURE_CLIENT_SECRET` | Confidencial | Azure Key Vault / .env local (no git) |
| `TALANA_API_KEY` | Confidencial | Azure Key Vault / .env local (no git) |
| GUIDs de Entra ID (produccion) | Interno | Azure Key Vault / variables de entorno CI |
| Emails de empleados | Personal | Solo en sistemas autorizados, nunca en git |
| RUT de empleados | Personal-Sensible | Solo en sistemas autorizados, nunca en git |
| GUIDs de grupos/planes (prod) | Interno | Variables de entorno, no hardcodeados |
| Placeholders de ejemplo | Publico | Puede aparecer en documentacion y codigo |

---

## Incidentes de Seguridad

### Procedimiento de respuesta

Si sospechas que una credencial fue expuesta (por ejemplo, commiteada por error):

1. **Revocar inmediatamente:** en Azure Portal, eliminar el secreto comprometido antes de hacer cualquier otra accion.
2. **Crear nuevo secreto:** generar uno nuevo y actualizar todos los entornos.
3. **Revisar git log:** identificar si el commit con datos sensibles fue pusheado al remoto.
4. **Si fue pusheado:** contactar al administrador para hacer force-push y purgar el historial (requiere coordinacion del equipo).
5. **Auditar accesos:** revisar logs de sign-in en Entra ID para detectar uso no autorizado.
6. **Documentar:** registrar el incidente, causa raiz y acciones tomadas en un documento interno.

### Contacto de seguridad

Reportar vulnerabilidades directamente al mantenedor del repositorio. No abrir issues publicos.
