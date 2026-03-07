# Guia de Inicio Rapido

## Que es esta herramienta

`grupoebi-ms365-graph-automation` es el sistema que automatiza la configuracion de entornos digitales en Microsoft 365 para Grupo EBI. En lugar de que cada persona configure manualmente Teams, Planner, SharePoint y los permisos de cada colaborador, esta herramienta lo hace en segundos a partir de los datos que ya existen en Talana.

**Lo que el sistema hace por ti:**
- Al ingresar un nuevo colaborador en Talana, crea automaticamente su cuenta M365, asigna la licencia correcta segun su cargo, lo agrega a los grupos y canales de Teams de su area, y le envia un email de bienvenida.
- Al crear un nuevo proyecto, genera el canal de Teams, el Plan de Planner con todas las tareas, la estructura de carpetas en SharePoint y sube los documentos base.
- Al dar de baja a un colaborador, deshabilita la cuenta, archiva el buzon y revoca los accesos de forma ordenada.

---

## Quienes pueden usar esta herramienta

| Rol | Que puede hacer |
|---|---|
| **Analista de RRHH** | Alta, baja y cambio de rol de usuarios (via Talana o formulario Teams) |
| **Project Manager / Lider de area** | Crear entornos de proyecto, importar tareas desde CSV |
| **Tecnico / Desarrollador** | Todas las operaciones via CLI, incluyendo modos avanzados |

---

## Tabla de flujos disponibles

| Necesitas... | Guia a seguir | Audiencia |
|---|---|---|
| Ingresar un nuevo colaborador | [Alta de Usuario](ALTA_USUARIO.md) | RRHH |
| Dar de baja a un colaborador | [Baja de Usuario](BAJA_USUARIO.md) | RRHH + IT |
| Cambiar el cargo o area de alguien | [Cambio de Rol](CAMBIO_ROL.md) | RRHH + Manager |
| Crear un entorno de proyecto nuevo | [Nuevo Proyecto](NUEVO_PROYECTO.md) | PM / Tecnico |
| Importar o actualizar tareas en Planner | [Importar Tareas](IMPORTAR_TAREAS.md) | PM / Tecnico |
| Agregar a alguien a un proyecto existente | [Incorporacion a Proyecto](INCORPORACION_PROYECTO.md) | RRHH / PM |

---

## Conceptos clave antes de empezar

### Perfil de rol
Cada cargo en Grupo EBI tiene un **perfil predefinido** que determina automaticamente:
- Que licencia M365 recibe (E3, E5 o F3)
- A que grupos de seguridad pertenece
- A que canales de Teams se le agrega
- Que aplicaciones tiene disponibles

El analista de RRHH **no configura esto manualmente**. Solo indica el cargo y area, y el sistema asigna todo lo que corresponde. Ver el catalogo completo en [PERFILES_ROLES.md](../PERFILES_ROLES.md).

### Dry-run (simulacion sin efecto)
Todos los comandos tienen un modo `--dry-run` que **simula la ejecucion sin hacer nada real**. Siempre ejecutar primero en dry-run para verificar que el comando hace lo que esperas antes de operar en produccion.

### Talana como fuente de verdad
Talana es el sistema de registro de empleados. M365 sigue a Talana: cuando un empleado se da de alta o baja en Talana, M365 se actualiza automaticamente via webhook. Si hay discrepancias, Talana prevalece.

### Autorizacion requerida
Cada flujo que modifica cuentas de usuario requiere una autorizacion previa registrada (numero de ticket o referencia). Esto crea trazabilidad fuera del sistema.

---

## Como funciona la integracion con Talana

```
Analista RRHH registra alta en Talana
          │
          │ Talana envia webhook automaticamente
          ▼
    Sistema de automatizacion
          │
          ├── Crea cuenta en Entra ID
          ├── Asigna licencia segun perfil del cargo
          ├── Agrega a grupos de seguridad
          ├── Agrega a canales de Teams
          ├── Crea tareas de onboarding en Planner
          ├── Envia email de bienvenida
          └── Actualiza Talana con ms365_id y email corporativo
```

El analista de RRHH **no necesita ejecutar ningun comando**. El sistema se activa solo cuando Talana registra el evento.

Si la integracion de webhook no esta configurada, las guias de usuario documentan como ejecutar el flujo manualmente.

---

## Para usuarios tecnicos: setup inicial

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
# Editar .env con las credenciales reales (ver SECURITY.md)

# 5. Verificar configuracion con dry-run
python planner_import.py --mode list --group-id <GUID> --dry-run
```

---

## Donde pedir ayuda

- Si el comando falla con un error de permisos: contactar al administrador de Azure.
- Si hay un problema con los datos de Talana: contactar al administrador de HRIS.
- Para reportar un bug en la herramienta: abrir un [issue en GitHub](.github/ISSUE_TEMPLATE/bug_report.yml).
- Para solicitar una nueva funcionalidad: usar el [formulario de feature request](.github/ISSUE_TEMPLATE/feature_request.yml).
- **Para reportar una vulnerabilidad de seguridad:** ver [SECURITY.md](../../SECURITY.md) — no abrir issues publicos.
