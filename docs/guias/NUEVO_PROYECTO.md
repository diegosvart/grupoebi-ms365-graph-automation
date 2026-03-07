# Guia: Crear un Nuevo Entorno de Proyecto

## Que hace este flujo

Crea en una sola ejecucion el entorno digital completo de un nuevo proyecto:
1. Canal de Teams con el nombre del proyecto
2. Agrega al PM como owner y al equipo como members
3. Plan de Planner completo (encabezado, etiquetas de categoria, buckets y tareas)
4. Estructura de carpetas en SharePoint
5. Sube los archivos de plantilla (Acta de Inicio, Ficha de Proyecto)
6. Ancla la pestana de Planner en el canal de Teams

**Comando principal:** `create_environment.py`

---

## Autorizacion requerida

| Quien autoriza | Que se necesita |
|---|---|
| Lider de area o Gerencia | Aprobacion de apertura del proyecto (ticket o email registrado) |

Registrar el numero de referencia antes de ejecutar el flujo.

---

## Informacion necesaria antes de ejecutar

Tener a mano:
- **Nombre del proyecto** (sera el nombre del canal de Teams y del plan de Planner)
- **ID del grupo M365** del Team de destino (ver como obtenerlo abajo)
- **Email del PM** del proyecto (se agregara como owner del canal y del plan)
- **Emails del equipo** inicial (se agregaran como members)
- **CSV de tareas** (usar plantilla `templates/default_init/Planner_Template_DEFAULT_V3.csv` o personalizar)

### Como obtener el GROUP_ID

```bash
# Listar grupos M365 disponibles y filtrar por nombre
python planner_import.py --mode list --group-id <GUID-del-team>

# O via Graph Explorer:
# GET https://graph.microsoft.com/v1.0/groups?$filter=displayName eq 'Nombre del Team'
```

---

## Paso a paso

### Paso 1 — Preparar el CSV de tareas

Copiar la plantilla base y adaptarla al proyecto:

```bash
cp templates/default_init/Planner_Template_DEFAULT_V3.csv mi_proyecto.csv
```

Estructura del CSV (delimitador `;`):

```csv
PlanName;BucketName;TaskTitle;AssignedTo;DueDate;Priority;Description;Checklist
Proyecto Alpha;Inicio;Definir alcance;pm@empresa.com;01042026;urgent;Documento de alcance inicial;"Revisar brief;Validar con sponsor"
Proyecto Alpha;Inicio;Kick-off meeting;lider@empresa.com;05042026;important;;
Proyecto Alpha;Diseno;Wireframes;disenador@empresa.com;15042026;medium;;
```

**Valores de prioridad:** `urgent` · `important` · `medium` · `low` · `none`
**Formato de fecha:** `DDMMYYYY` (ejemplo: `01042026` = 1 de abril de 2026)

### Paso 2 — Simular (dry-run obligatorio)

```bash
python create_environment.py \
  --csv mi_proyecto.csv \
  --group-id xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx \
  --dry-run
```

**Verificar en el output:**
- [ ] Nombre del plan correcto
- [ ] Buckets en el orden esperado
- [ ] Tareas con responsables correctos (emails resueltos a nombres)
- [ ] Fechas de vencimiento correctas
- [ ] Sin errores de validacion de CSV

### Paso 3 — Ejecutar en produccion

Solo despues de verificar el dry-run:

```bash
python create_environment.py \
  --csv mi_proyecto.csv \
  --group-id xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
```

### Paso 4 — Verificar resultado

Despues de la ejecucion exitosa, verificar en Microsoft 365:

- [ ] **Teams:** nuevo canal visible con el nombre del proyecto
- [ ] **Teams:** PM aparece como Owner del canal
- [ ] **Planner:** nuevo plan visible en el Team con todos los buckets y tareas
- [ ] **SharePoint:** estructura de carpetas creada en el sitio del grupo
- [ ] **SharePoint:** archivos de plantilla subidos (Acta de Inicio, Ficha de Proyecto)
- [ ] **Teams:** pestana de Planner anclada en el canal del proyecto

---

## Modo solo Planner (sin Teams ni SharePoint)

Si el equipo ya tiene un canal existente y solo necesita el plan de Planner:

```bash
# Dry-run primero
python planner_import.py \
  --mode full \
  --csv mi_proyecto.csv \
  --group-id xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx \
  --dry-run

# Ejecucion real
python planner_import.py \
  --mode full \
  --csv mi_proyecto.csv \
  --group-id xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
```

Ver [Guia: Importar Tareas](IMPORTAR_TAREAS.md) para todos los modos disponibles.

---

## Advertencias importantes

> **Idempotencia:** Si ejecutas el comando dos veces con el mismo CSV y group-id, el sistema verifica si el canal y las carpetas ya existen antes de crearlos. Sin embargo, **los planes de Planner se crean nuevos cada vez** — podria resultar en planes duplicados. Siempre verifica con `--mode list` antes de re-ejecutar.

> **Asignacion de tareas:** Los emails de responsables se resuelven a GUIDs en tiempo de ejecucion. Si un email no existe en Entra ID, la tarea se crea sin asignado y se registra una advertencia en el log. Verificar que todos los emails del CSV son validos y pertenecen al tenant.

---

## Que hacer si falla

| Error | Causa probable | Solucion |
|---|---|---|
| `401 Unauthorized` | Token expirado o permisos insuficientes | Verificar `.env` y permisos en Azure Portal |
| `403 Forbidden` | La App Registration no tiene permiso para esta operacion | Agregar permiso en App Registration + consentimiento del admin |
| `404 Not Found` | El `GROUP_ID` no existe o es incorrecto | Verificar el ID del grupo con `--mode list` |
| `409 Conflict` | El canal ya existe | Normal — el sistema lo detecta y no crea duplicado |
| `429 Too Many Requests` | Throttling de la Graph API | El sistema reintenta automaticamente; esperar y verificar log |
| Email no resuelto | El email no existe en Entra ID del tenant | Verificar el email en Azure Portal > Users |
| Error en CSV | Formato incorrecto de fecha o prioridad | Revisar formato: fechas `DDMMYYYY`, prioridades en minuscula |
