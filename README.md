# grupoebi-ms365-graph-automation

> CLI en Python para automatizar el ciclo de vida de usuarios y proyectos en Microsoft 365 via Graph API.
> Orquesta Planner, Teams, SharePoint, Entra ID y Talana HRIS desde una sola herramienta.

[![Security Policy](https://img.shields.io/badge/Security-Policy-red)](SECURITY.md)
[![License](https://img.shields.io/badge/Licencia-Interno-blue)](LICENSE)

---

## Para quien es esta herramienta

| Si eres... | Ve a... |
|---|---|
| **Analista de RRHH** — dar de alta/baja un usuario | [Guia: Alta de Usuario](docs/guias/ALTA_USUARIO.md) · [Guia: Baja de Usuario](docs/guias/BAJA_USUARIO.md) |
| **PM o Lider** — crear un entorno de proyecto | [Guia: Nuevo Proyecto](docs/guias/NUEVO_PROYECTO.md) · [Guia: Importar Tareas](docs/guias/IMPORTAR_TAREAS.md) |
| **RRHH** — incorporar alguien a un proyecto existente | [Guia: Incorporacion a Proyecto](docs/guias/INCORPORACION_PROYECTO.md) |
| **RRHH / Manager** — cambiar el rol de un colaborador | [Guia: Cambio de Rol](docs/guias/CAMBIO_ROL.md) |
| **Tecnico / Desarrollador** — entender la arquitectura | [Arquitectura](docs/ARQUITECTURA.md) · [API Referencia](docs/API_REFERENCIA.md) |
| **Nuevo en el proyecto** | [Inicio Rapido](docs/guias/INICIO_RAPIDO.md) |

---

## Flujos disponibles

| Flujo | Trigger | Audiencia | Guia |
|---|---|---|---|
| Alta de usuario | Webhook Talana / formulario Teams | RRHH | [ALTA_USUARIO.md](docs/guias/ALTA_USUARIO.md) |
| Baja de usuario | Webhook Talana / solicitud RRHH + IT | RRHH + IT | [BAJA_USUARIO.md](docs/guias/BAJA_USUARIO.md) |
| Cambio de rol | Solicitud RRHH con autorizacion | RRHH + Manager | [CAMBIO_ROL.md](docs/guias/CAMBIO_ROL.md) |
| Nuevo proyecto | PM o Lider de area | PM / Tecnico | [NUEVO_PROYECTO.md](docs/guias/NUEVO_PROYECTO.md) |
| Importar tareas CSV | PM / Tecnico | PM / Tecnico | [IMPORTAR_TAREAS.md](docs/guias/IMPORTAR_TAREAS.md) |
| Incorporar a proyecto | RRHH / PM | RRHH / PM | [INCORPORACION_PROYECTO.md](docs/guias/INCORPORACION_PROYECTO.md) |

---

## Arquitectura en una pagina

```
Talana HRIS (fuente de verdad)
        |
        | webhook alta_empleado / baja_empleado
        v
  Python CLI / Azure Function
        |
        |-- Azure Entra ID   POST /users, assignLicense, grupos de seguridad
        |-- Exchange Online  sendMail, mailboxSettings
        |-- Microsoft Teams  canales, miembros, tabs
        |-- Planner          planes, buckets, tareas desde CSV
        |-- SharePoint       carpetas, archivos de plantilla
        |-- Intune           enrollment, politicas de compliance
        |
        v
  Talana HRIS (actualizacion: ms365_id, email_corporativo, estado)
```

Ver [docs/ARQUITECTURA.md](docs/ARQUITECTURA.md) para el diagrama completo, flujo de autenticacion y descripcion de modulos.

---

## Instalacion rapida

```bash
# 1. Clonar
git clone https://github.com/diegosvart/grupoebi-ms365-graph-automation.git
cd grupoebi-ms365-graph-automation

# 2. Entorno virtual
python -m venv .venv
source .venv/bin/activate        # Linux/macOS
.\.venv\Scripts\activate         # Windows

# 3. Dependencias
pip install -r requirements.txt

# 4. Configurar variables de entorno
cp .env.example .env
# Editar .env con credenciales reales (ver SECURITY.md)
```

Requisitos: Python 3.10+, acceso a `graph.microsoft.com`, App Registration en Azure Entra ID.

---

## Permisos Graph API requeridos

Ver tabla completa en [SECURITY.md](SECURITY.md#app-registration--permisos-de-la-graph-api).

Permisos minimos actuales:
`Tasks.ReadWrite` · `Group.ReadWrite.All` · `User.Read.All` · `Channel.Create` · `TeamMember.ReadWrite.All` · `Sites.ReadWrite.All` · `Files.ReadWrite.All`

---

## Sistema de perfiles por rol

El analista de RRHH **no configura permisos individuales**. Solo indica el cargo y area del nuevo colaborador. El sistema resuelve automaticamente:

- Licencia M365 (E3 / E5 / F3 segun cargo)
- Grupos de seguridad
- Canales de Teams
- Aplicaciones asignadas
- Plantilla de tareas de onboarding en Planner

Ver el catalogo completo en [docs/PERFILES_ROLES.md](docs/PERFILES_ROLES.md).

---

## Documentacion

```
docs/
|-- ARQUITECTURA.md          Diagrama del sistema, auth, modulos
|-- PERFILES_ROLES.md        Catalogo de perfiles cargo → licencias + accesos
|-- API_REFERENCIA.md        Endpoints Graph implementados y planeados
|-- TESTING.md               Estrategia de tests y cobertura
|-- GLOSARIO.md              Terminos M365, Talana y tecnicos
|
|-- guias/
|   |-- INICIO_RAPIDO.md
|   |-- NUEVO_PROYECTO.md
|   |-- IMPORTAR_TAREAS.md
|   |-- ALTA_USUARIO.md
|   |-- BAJA_USUARIO.md
|   |-- INCORPORACION_PROYECTO.md
|   `-- CAMBIO_ROL.md
|
`-- integraciones/
    |-- ENTRA_ID.md
    |-- EXCHANGE_ONLINE.md
    |-- TALANA.md
    |-- TEAMS.md
    |-- SHAREPOINT.md
    |-- INTUNE.md
    `-- POWER_AUTOMATE.md
```

---

## Seguridad

- Todas las credenciales van en `.env` (excluido de git). Ver [SECURITY.md](SECURITY.md).
- Modo `--dry-run` disponible en todos los comandos — ejecutarlo **siempre antes** de operar en produccion.
- El hook `hooks/guard-sensitive.py` bloquea exposicion accidental de secretos.
- Rotar `AZURE_CLIENT_SECRET` cada 90 dias. Ver procedimiento en [SECURITY.md](SECURITY.md#ciclo-de-vida-de-secretos).

**Para reportar una vulnerabilidad:** contactar directamente al mantenedor. No abrir issues publicos.

---

## Contribuir

Ver [CONTRIBUTING.md](CONTRIBUTING.md) para setup de desarrollo, convenios de commits y proceso de PR.

---

## Licencia

Uso interno — Grupo EBI. Ver `LICENSE` para detalles.
