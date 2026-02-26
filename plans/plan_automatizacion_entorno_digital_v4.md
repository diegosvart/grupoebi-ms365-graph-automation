# Plan Maestro — Automatización Entorno Digital por Proyecto
## Python + Microsoft Graph API · v4

---

## 1. Principios de Diseño

- **Planner es la fuente de verdad operativa.** No existe documento paralelo que replique su contenido.
- **El canal de Teams es el espacio oficial del proyecto.** Toda comunicación formal ocurre ahí.
- **Mínima fricción:** el PM encuentra el entorno listo, no lo construye.
- **Dos etapas de activación:** el entorno se crea con los roles que tienen tareas. El equipo completo se activa cuando el PM confirma los participantes restantes.
- **Criterio de separación entre etapas:** ¿el rol tiene tareas en la carga inicial? Sí → Etapa 1. No → Etapa 2.
- **Independencia del PM:** el directorio de ayuda en SharePoint permite que cualquier participante opere sin depender de disponibilidad del PM. Reduce riesgo de concentración de conocimiento en un cargo.

---

## 2. Roles y Comportamiento

| Rol | Identificado en | Tareas carga inicial | Entra al canal | Etapa |
|---|---|---|---|---|
| `PM` | Ficha de Proyecto | ✅ Ciclo completo | ✅ Owner | 1 |
| `LIDER` | Ficha de Proyecto | ✅ Control + Cierre | ✅ Owner | 1 |
| `SPONSOR` | Ficha de Proyecto | ❌ Sin tareas | ✅ Member | 2 |
| `REVISOR` | CSV2 | ⏳ Por hito (post Gateway 2) | ✅ Member | 2 |
| `EJECUTOR` | CSV2 | ⏳ Post Gateway 2 | ✅ Member | 2 |
| `OBSERVADOR` | CSV2 | ❌ Sin tareas | ❌ No entra | 2 |

> **OBSERVADOR:** recibe Reporte de Avance mensual vía mención en canal o email.

---

## 3. Flujo General — Dos Etapas

```
╔══════════════════════════════════════════════════════════════╗
║  ETAPA 1 — create_environment.py + CSV1                      ║
║                                                              ║
║  INPUT: ProjectID · ProjectName · PMEmail ·                  ║
║         LiderEmail · StartDate                               ║
║                                                              ║
║  PASO 1 → Resolver IDs estáticos (cachear)                   ║
║  PASO 2 → Crear canal en Teams                               ║
║  PASO 3 → Agregar PM y Líder al canal                        ║
║  PASO 4 → Crear Plan + Buckets + Tareas (PM + Líder)         ║
║  PASO 5 → Anclar Plan como Tab en el canal                   ║
║  PASO 6 → Crear carpeta del proyecto + subcarpetas           ║
║  PASO 7 → Subir plantillas base (2 documentos)               ║
║  PASO 8 → Guardar project_config.json (status: pending)      ║
║                                                              ║
║  RESULTADO: entorno operativo · sin mensaje de bienvenida    ║
╚══════════════════════════════════════════════════════════════╝
                          │
                          │  PM confirma Sponsor y participantes
                          │  (puede ocurrir días después)
                          ▼
╔══════════════════════════════════════════════════════════════╗
║  ETAPA 2 — activate_environment.py + CSV2                    ║
║                                                              ║
║  INPUT: ProjectID · Email · Role · ChannelMember             ║
║                                                              ║
║  PASO 1 → Leer project_config por ProjectID                  ║
║  PASO 2 → Agregar participantes al canal (channel: True)     ║
║  PASO 3 → Crear tareas de Revisores en Planner (si aplica)   ║
║  PASO 4 → Resolver links de recursos del proyecto            ║
║  PASO 5 → Disparar mensaje de bienvenida con links           ║
║  PASO 6 → Actualizar project_config (status: active)         ║
║                                                              ║
║  RESULTADO: equipo completo · mensaje enviado · activo       ║
╚══════════════════════════════════════════════════════════════╝
```

---

## 4. Especificación de CSVs

### CSV1 — Creación del entorno

```csv
ProjectID;ProjectName;PMEmail;LiderEmail;StartDate
PRJ-2026-001;Nombre del Proyecto;pm@dom.com;lider@dom.com;2026-03-01
```

### CSV2 — Alta de participantes y activación

```csv
ProjectID;Email;Role;ChannelMember
PRJ-2026-001;sponsor@dom.com;SPONSOR;True
PRJ-2026-001;revisor@dom.com;REVISOR;True
PRJ-2026-001;ejecutor@dom.com;EJECUTOR;True
PRJ-2026-001;observador@dom.com;OBSERVADOR;False
```

---

## 5. Registro de Estado del Proyecto

```json
{
  "PRJ-2026-001": {
    "project_name": "Nombre del Proyecto",
    "pm_email":     "pm@dom.com",
    "lider_email":  "lider@dom.com",
    "start_date":   "2026-03-01",
    "group_id":     "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
    "channel_id":   "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
    "channel_url":  "https://teams.microsoft.com/l/channel/...",
    "plan_id":      "xxxxxxxxxxxxxxxxxxxxxxxx",
    "plan_url":     "https://tasks.office.com/.../Home/PlanViews/...",
    "bucket_ids": {
      "01_INICIO":       "xxxxxxxxxxxxxxxxxxxxxxxx",
      "02_PLANIFICACION":"xxxxxxxxxxxxxxxxxxxxxxxx",
      "03_EJECUCION":    "xxxxxxxxxxxxxxxxxxxxxxxx",
      "04_CONTROL":      "xxxxxxxxxxxxxxxxxxxxxxxx",
      "05_CIERRE":       "xxxxxxxxxxxxxxxxxxxxxxxx",
      "RIESGOS_ACTIVOS": "xxxxxxxxxxxxxxxxxxxxxxxx"
    },
    "folder_id":    "xxxxxxxxxxxxxxxxxxxxxxxx",
    "folder_url":   "https://{tenant}.sharepoint.com/sites/.../PRJ-2026-001",
    "meeting_day":  "MON",
    "meeting_time": "10:00",
    "status":       "pending_activation",
    "created_at":   "2026-03-01T10:00:00",
    "activated_at": null
  }
}
```

> Los campos `channel_url`, `plan_url` y `folder_url` se resuelven y guardan
> en Etapa 1. Se usan en Etapa 2 para construir el mensaje de bienvenida
> sin llamadas adicionales a Graph.

---

## 6. Estructura SharePoint — Proyecto

```
📁 PRJ-2026-001 · Nombre del Proyecto
│
├── 01_INICIO
│   ├── Ficha_de_Proyecto.docx       ← template según tipo — subido en Etapa 1
│   └── Acta_de_Inicio.docx          ← template vacío estructurado — subido en Etapa 1
│
├── 02_PLANIFICACION
│   └── (vacía — el plan vive en Planner)
│
├── 03_EJECUCION
│   └── (entregables reales durante ejecución)
│
├── 04_CONTROL
│   └── (vacía — el control vive en Planner)
│
└── 05_CIERRE
    ├── Reporte_de_Avance_Final.docx  ← creado por PM al cerrar
    └── Acta_de_Cierre.docx           ← creado por PM al cerrar
```

---

## 7. Directorio de Ayuda — SharePoint Compartido ← NUEVO

### Propósito

Repositorio único accesible desde cualquier proyecto activo.
Permite que cualquier participante opere con autonomía sin depender
de la disponibilidad del PM. Reduce riesgo de concentración de
conocimiento en un cargo.

### Ubicación

```
📁 _AYUDA_PM  ← carpeta en la raíz del sitio SharePoint del grupo
│             ← el prefijo _ la mantiene primera en el listado
│
├── 01_Guias_de_Proceso
│   ├── Guia_Ciclo_de_Vida_del_Proyecto.pdf
│   ├── Guia_Uso_de_Planner.pdf
│   ├── Guia_Seguimiento_Semanal.pdf
│   └── Guia_Gateways_y_Decisiones.pdf
│
├── 02_Plantillas
│   ├── Ficha_de_Proyecto_Nueva_Iniciativa.docx
│   ├── Ficha_de_Regularizacion.docx
│   ├── Acta_de_Inicio.docx
│   └── Acta_de_Cierre.docx
│
└── 03_Referencias
    ├── Roles_y_Responsabilidades.pdf
    ├── Glosario_PM.pdf
    └── Preguntas_Frecuentes.pdf
```

### Comportamiento en la automatización

- La carpeta `_AYUDA_PM` se crea **una sola vez**, no por proyecto.
- El script de Etapa 1 verifica si existe antes de intentar crearla.
- La URL del directorio de ayuda es **estática** → se cachea en config.
- Se referencia en el mensaje de bienvenida de todos los proyectos.

```python
# En config / .env
HELP_FOLDER_URL = "https://{tenant}.sharepoint.com/sites/ProyectosTI/_AYUDA_PM"

# Verificación antes de crear (idempotente)
def ensure_help_directory(site_id: str, root_id: str, graph_client):
    existing = get_children(site_id, root_id)
    if "_AYUDA_PM" not in [f["name"] for f in existing]:
        create_folder(site_id, root_id, "_AYUDA_PM")
        create_subfolders(...)
        upload_base_documents(...)
    # Si ya existe → no hace nada
```

---

## 8. Estructura del Plan en Planner

```
PLAN: PRJ-2026-001 · Nombre del Proyecto
│
├── BUCKET: 01_INICIO
│   ├── [PM]    Completar y validar Ficha de Proyecto
│   ├── [PM]    Preparar resumen ejecutivo para reunión de viabilidad
│   ├── [PM]    Agendar reunión de viabilidad (PM + Líder + Sponsor)
│   └── [PM]    Entorno digital creado ✓  ← tarea pre-completada (registro)
│
├── BUCKET: 02_PLANIFICACION
│   ├── [PM]    Agendar reunión de planificación detallada
│   ├── [LIDER] Desglosar entregables y definir dependencias
│   ├── [LIDER] Validar fechas y disponibilidad del equipo
│   └── [PM]    Presentar plan al Sponsor — Gateway 2
│
├── BUCKET: 03_EJECUCION
│   ├── [PM]    Conducir Kick Off oficial
│   └── [LIDER] Coordinar ejecución — seguimiento continuo
│
├── BUCKET: 04_CONTROL
│   ├── [PM]    Seguimiento Semana 1 · [FECHA]          ← checklist PM
│   └── [LIDER] Revisión Técnica Semana 1 · [FECHA]    ← checklist Líder
│
├── BUCKET: 05_CIERRE
│   ├── [PM]    Validar entregables con Líder y Sponsor
│   ├── [LIDER] Confirmar aceptación formal de entregables
│   ├── [PM]    Completar Acta de Cierre
│   ├── [PM]    Facilitar sesión de Lecciones Aprendidas
│   └── [PM]    Lecciones Aprendidas · PRJ-XXXX
│
└── BUCKET: RIESGOS_ACTIVOS
    └── (vacío — se puebla durante ejecución)
```

---

## 9. Tarea del Líder — Campos para CSV de Carga

Formato exacto alineado al CSV de implementación existente.
Agregar estas dos filas al template DEFAULT junto a las tareas del PM.

```csv
ProjectID;ProjectName;PlanName;BucketName;TaskGroupID;TaskTitle;TaskDescription;AssignedToEmail;StartDate;DueDate;Priority;PercentComplete;IsParentTask;ChecklistItems;Labels;Status
[PRJ-ID];[PROYECTO_NOMBRE];[PLAN_NOMBRE];02_PLANIFICACION;TG-LIDER;Desglosar entregables y definir dependencias;Identificar todos los entregables del proyecto y sus dependencias en conjunto con el PM;[LIDER_EMAIL];[START_DATE];[DUE_DATE];medium;0;True;"Listar entregables comprometidos;Identificar dependencias entre tareas;Estimar esfuerzo por entregable;Confirmar disponibilidad del equipo;Validar con PM antes de presentar al Sponsor";LIDER;Planned
[PRJ-ID];[PROYECTO_NOMBRE];[PLAN_NOMBRE];04_CONTROL;TG-LIDER;Revisión Técnica Semana 1 · [FECHA];Revisión semanal del estado técnico del proyecto para sincronizar con el PM en la reunión de seguimiento;[LIDER_EMAIL];[START_DATE];[DUE_DATE];medium;0;False;"Tareas del equipo actualizadas en Planner;Bloqueos técnicos identificados y comunicados en el canal;Entregables de la semana: estado confirmado;Recursos disponibles próxima semana confirmados;Nuevas tareas técnicas identificadas para cargar con PM";LIDER;Planned
```

### Notas de implementación para el mapper

```python
# Los placeholders se resuelven en runtime igual que las tareas del PM
LIDER_TASK_PLACEHOLDERS = {
    "[PRJ-ID]":           project["project_id"],
    "[PROYECTO_NOMBRE]":  project["project_name"],
    "[PLAN_NOMBRE]":      f"{project['project_id']} · {project['project_name']}",
    "[LIDER_EMAIL]":      project["lider_email"],
    "[START_DATE]":       project["start_date"],
    "[DUE_DATE]":         calculate_due_date(project["start_date"], offset_days=7),
    "[FECHA]":            format_date(project["start_date"]),
}
```

---

## 10. Diseño de Tareas Clave en Planner

### 10.1 Tarea de Seguimiento Semanal — PM

```
Título:       Seguimiento Semana 1 · DD/MMM/YYYY
Asignado:     PM
Bucket:       04_CONTROL

Checklist:
  [ ] Avance 1 — [Responsable]
  [ ] Avance 2 — [Responsable]
  ─── BLOQUEOS ───────────────
  [ ] Bloqueo activo — acción:
  ─── ACUERDOS ───────────────
  [ ] [Responsable · Fecha] Acuerdo
  ─── NUEVAS TAREAS ──────────
  [ ] Tarea identificada → cargar en Planner
  ─── RIESGOS ────────────────
  [ ] Riesgo nuevo → nivel → mitigación → cargar en bucket Riesgos
```

### 10.2 Tarea de Revisión Técnica Semanal — Líder

```
Título:       Revisión Técnica Semana 1 · DD/MMM/YYYY
Asignado:     LIDER
Bucket:       04_CONTROL

Checklist:
  [ ] Tareas del equipo actualizadas en Planner
  [ ] Bloqueos técnicos comunicados en el canal
  [ ] Entregables de la semana: estado confirmado
  [ ] Recursos próxima semana confirmados
  [ ] Nuevas tareas técnicas identificadas
```

### 10.3 Riesgo activo

```
Título:       Riesgo: [descripción breve] — Nivel [A/M/B]
Bucket:       RIESGOS_ACTIVOS
Label:        RIESGO-ALTO / RIESGO-MEDIO / RIESGO-BAJO
Descripción:  Contexto · Probabilidad · Impacto · Mitigación · Detectado en Semana N
```

### 10.4 Lecciones Aprendidas — cierre

```
Título:       Lecciones Aprendidas · PRJ-XXXX
Bucket:       05_CIERRE
Asignado:     PM

Descripción:
  ─── QUÉ FUNCIONÓ ─────────────────────
  1.
  ─── QUÉ NO FUNCIONÓ ──────────────────
  1.
  ─── RECOMENDACIONES ──────────────────
  1.

Checklist:
  [ ] Sesión de cierre realizada con el equipo
  [ ] Lecciones documentadas en esta tarea
  [ ] Acta de Cierre firmada por Sponsor
  [ ] Canal archivado en Teams
  [ ] Plan cerrado en Planner
  [ ] status → closed en project_config
```

---

## 11. Visibilidad del Sponsor

### Nivel 1 — Pasiva (desde Etapa 2)
Sponsor en el canal como miembro. Ve historial, Planner y SharePoint en cualquier momento.

### Nivel 2 — Activa mensual
PM publica Reporte de Avance en el canal con mención `@Sponsor`. Sin emails, sin adjuntos fuera del canal.

### Nivel 3 — Dashboard consolidado (Phase 2)
Power BI conectado a Planner vía Graph API, o página SharePoint con webparts.
No se implementa en Phase 1.

---

## 12. Mensaje de Bienvenida con Links (Etapa 2) ← ACTUALIZADO

Los links se construyen desde los valores guardados en `project_config` durante Etapa 1.
No se realizan llamadas adicionales a Graph en este paso.

```python
def build_welcome_message(project: dict, members: list) -> str:
    team_list = "\n".join([
        f"  {'📋 PM' if m['role']=='PM' else '👤 Líder' if m['role']=='LIDER' else '🎯 Sponsor' if m['role']=='SPONSOR' else '👁 ' + m['role']}: {m['email']}"
        for m in members if m["channel_member"]
    ])

    return f"""
<h3>🚀 {project['project_id']} · {project['project_name']} — Entorno activado</h3>

<p><b>Equipo del proyecto:</b><br/>{team_list}</p>

<p>Este canal es el espacio oficial del proyecto durante todo su ciclo de vida.<br/>
Toda comunicación formal, acuerdos y decisiones se registran aquí.</p>

<p><b>Recursos del proyecto:</b><br/>
📌 <a href="{project['plan_url']}">Plan en Planner</a> — tareas, avances y seguimiento semanal<br/>
📁 <a href="{project['folder_url']}">Repositorio SharePoint</a> — documentos del proyecto<br/>
📚 <a href="{HELP_FOLDER_URL}">Directorio de Ayuda</a> — guías, plantillas y referencias</p>

<p><b>Próximo paso:</b> Reunión de Inicio — coordinar con el PM.</p>
"""
```

---

## 13. Tarea Semanal — Creación Automática (Implementación futura)

### Estado actual
Primera tarea de PM y Líder creada en carga inicial.
PM duplica manualmente cada semana: abrir tarea anterior → duplicar → actualizar fecha en título.

### Especificación del scheduler

```python
# Trigger: cada lunes (configurable por proyecto)
# Condición: status == "active"

def create_weekly_tasks(project_config: dict, graph_client):
    for project_id, project in project_config.items():
        if project["status"] != "active":
            continue

        week_number = calculate_week_number(project["start_date"])
        week_date   = get_next_meeting_date(project)

        create_task(
            plan_id   = project["plan_id"],
            bucket_id = project["bucket_ids"]["04_CONTROL"],
            title     = f"Seguimiento Semana {week_number} · {week_date}",
            assigned  = project["pm_email"],
            checklist = CHECKLIST_TEMPLATE_PM,
            due_date  = week_date
        )

        create_task(
            plan_id   = project["plan_id"],
            bucket_id = project["bucket_ids"]["04_CONTROL"],
            title     = f"Revisión Técnica Semana {week_number} · {week_date}",
            assigned  = project["lider_email"],
            checklist = CHECKLIST_TEMPLATE_LIDER,
            due_date  = week_date
        )

# Opciones de scheduler (orden de complejidad):
# 1. Power Automate con recurrencia semanal — sin infraestructura adicional
# 2. Cron job en servidor existente
# 3. Azure Function con TimerTrigger (cron: "0 8 * * 1")
```

---

## 14. Permisos Requeridos

| Permiso | Para qué |
|---|---|
| `Group.Read.All` | Resolver groupId del Team |
| `Channel.Create` | Crear canal |
| `ChannelMember.ReadWrite.All` | Agregar miembros al canal |
| `TeamsTab.ReadWrite.All` | Anclar plan como tab |
| `Tasks.ReadWrite.All` | Planner — plan, buckets, tareas |
| `Sites.ReadWrite.All` | Carpetas, subcarpetas y archivos SharePoint |
| `ChannelMessage.Send` | Mensaje de bienvenida |
| `User.Read.All` | Resolver userId desde email |

---

## 15. Consideraciones Técnicas

| Punto | Detalle |
|---|---|
| **IDs estáticos** | `groupId`, `siteId`, `rootItemId`, `HELP_FOLDER_URL` → cachear en `.env`. No llamar Graph en cada ejecución. |
| **Links en project_config** | `channel_url`, `plan_url`, `folder_url` se resuelven y guardan en Etapa 1. Etapa 2 los lee directamente sin llamadas adicionales. |
| **Directorio de ayuda** | Creación idempotente: verificar existencia antes de crear. URL estática en config. |
| **Tab de Planner** | `contentUrl` requiere `tenantId` y `{{loginHint}}` literal. Validar en tenant antes de automatizar. |
| **Rate limiting** | `time.sleep(0.5)` entre creaciones de subcarpetas en batch. |
| **Idempotencia** | `conflictBehavior: rename` en todas las carpetas. Verificar canal antes de crear. |
| **Nombre del canal** | Máximo 50 caracteres. Truncar `project_name` si supera el límite. |
| **project_config** | JSON local para Phase 1. Migrar a SharePoint List cuando se necesite visibilidad consolidada desde Teams. |

---

## 16. Orden de Desarrollo

```
Sprint 1
  ├── Paso 1:  resolver y cachear IDs estáticos
  ├── Paso 2:  crear canal Teams + guardar channel_url
  └── Paso 3:  agregar PM y Líder al canal

Sprint 2
  ├── Paso 6:  crear carpeta proyecto + subcarpetas + guardar folder_url
  ├── Paso 7:  subir 2 plantillas base a 01_INICIO
  └──          crear/verificar directorio _AYUDA_PM (idempotente)

Sprint 3
  ├── Paso 4:  extender Planner con tarea del Líder + bucket Riesgos
  │            guardar plan_url en project_config
  └── Paso 8:  guardar project_config.json completo

Sprint 4
  ├──          activate_environment.py completo (Etapa 2)
  └── Paso 5:  anclar tab Planner en canal (validar en tenant primero)

Sprint 5
  ├──          Integración orquestadora completa
  ├──          Manejo de errores y logging
  └──          Documentar y preparar scheduler semanal
```
