# Guia: Importar Tareas a Microsoft Planner

## Que hace este flujo

Importa, actualiza o elimina planes y tareas en Microsoft Planner a partir de un archivo CSV. Permite operar sobre componentes individuales (solo el plan, solo buckets, solo tareas) o sobre el plan completo en una sola ejecucion.

**Comando principal:** `planner_import.py`

---

## Autorizacion requerida

| Modo | Quien autoriza |
|---|---|
| `list` (solo lectura) | Cualquier usuario con acceso al grupo |
| `full`, `plan`, `buckets`, `tasks` | PM del proyecto o lider de area |
| `delete` | Lider de area + confirmacion interactiva |

---

## Modos disponibles

| Modo | Que hace | Cuando usarlo |
|---|---|---|
| `full` | Crea encabezado del plan + labels + buckets + tareas | Proyecto nuevo sin plan |
| `plan` | Crea solo el encabezado del plan con labels | Cuando los buckets se agregan despues |
| `buckets` | Agrega buckets a un plan existente | El plan ya existe, faltan buckets |
| `tasks` | Agrega tareas a plan y bucket existentes | Incorporar tareas nuevas a un plan en curso |
| `list` | Lista todos los planes del grupo en formato tabla | Encontrar el PLAN_ID de un plan existente |
| `delete` | Eliminacion interactiva con confirmacion | Limpiar planes de prueba o duplicados |

---

## Formato del CSV

Delimitador: punto y coma (`;`)

```csv
PlanName;BucketName;TaskTitle;AssignedTo;DueDate;Priority;Description;Checklist
Proyecto Alpha;Inicio;Definir alcance;pm@empresa.com;01042026;urgent;Documento de alcance;"Revisar brief;Validar con sponsor"
Proyecto Alpha;Inicio;Kick-off;lider@empresa.com;05042026;important;;
Proyecto Alpha;Ejecucion;Entrega v1;dev@empresa.com;01052026;medium;Primera version funcional;
```

**Columnas:**

| Columna | Obligatoria | Formato | Ejemplo |
|---|---|---|---|
| `PlanName` | Si | Texto libre | `Proyecto Alpha 2026` |
| `BucketName` | Si | Texto libre | `Inicio` |
| `TaskTitle` | Si | Texto libre | `Definir alcance del proyecto` |
| `AssignedTo` | No | Email corporativo | `pm@empresa.com` |
| `DueDate` | No | DDMMYYYY | `15042026` |
| `Priority` | No | Ver valores validos | `urgent` |
| `Description` | No | Texto libre | `Descripcion detallada` |
| `Checklist` | No | Items separados por `;` | `"Paso 1;Paso 2;Paso 3"` |

**Valores de prioridad:** `urgent` · `important` · `medium` · `low` · `none`

---

## Paso a paso por modo

### Listar planes del grupo

```bash
# Ver todos los planes disponibles
python planner_import.py --mode list --group-id <GROUP_ID>

# Filtrar por nombre
python planner_import.py --mode list --filter "Q1 2026" --group-id <GROUP_ID>
```

Output esperado:
```
ID                                    | Nombre del plan
--------------------------------------|----------------------------
xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx  | Proyecto Alpha 2026
yyyyyyyy-yyyy-yyyy-yyyy-yyyyyyyyyyyy  | Proyecto Beta 2026
```

### Crear plan completo (modo full)

```bash
# Dry-run primero (obligatorio)
python planner_import.py \
  --mode full \
  --csv mi_plan.csv \
  --group-id <GROUP_ID> \
  --dry-run

# Ejecucion real (solo tras verificar dry-run)
python planner_import.py \
  --mode full \
  --csv mi_plan.csv \
  --group-id <GROUP_ID>
```

### Agregar tareas a plan existente (modo tasks)

Cuando el plan ya existe y solo necesitas agregar tareas nuevas:

```bash
# Necesitas el PLAN_ID (obtenlo con --mode list)
# Necesitas el BUCKET_ID del bucket destino

python planner_import.py \
  --mode tasks \
  --csv nuevas_tareas.csv \
  --group-id <GROUP_ID> \
  --plan-id <PLAN_ID> \
  --bucket-id <BUCKET_ID> \
  --dry-run

# Ejecucion real
python planner_import.py \
  --mode tasks \
  --csv nuevas_tareas.csv \
  --group-id <GROUP_ID> \
  --plan-id <PLAN_ID> \
  --bucket-id <BUCKET_ID>
```

### Eliminar planes (modo delete)

```bash
python planner_import.py --mode delete --group-id <GROUP_ID>
```

El sistema muestra la lista de planes y pide seleccion interactiva con confirmacion antes de eliminar. Esta operacion **no tiene dry-run** — el prompt de confirmacion es la salvaguarda.

---

## Verificacion post-ejecucion

- [ ] Abrir Microsoft Planner y verificar que el plan aparece con el nombre correcto
- [ ] Verificar que los buckets estan en el orden esperado
- [ ] Verificar que las tareas tienen los responsables correctos
- [ ] Verificar fechas de vencimiento
- [ ] Verificar que los checklists se crearon (abrir una tarea y revisar)

---

## Advertencias

> **Tareas duplicadas:** Si ejecutas el modo `tasks` o `full` dos veces con el mismo CSV, se crean tareas duplicadas en Planner. Verificar con `--mode list` antes de re-ejecutar y usar `--dry-run` para confirmar el estado esperado.

> **Eliminacion irreversible:** El modo `delete` elimina planes permanentemente. No hay papelera de reciclaje en Planner. Confirmar dos veces antes de ejecutar.

> **Emails no encontrados:** Si un email en la columna `AssignedTo` no existe en el tenant de Entra ID, la tarea se crea sin responsable asignado. Se registra una advertencia en el log. Verificar los emails con el administrador de Azure si hay problemas.

---

## Que hacer si falla

| Error | Causa probable | Solucion |
|---|---|---|
| `Error parsing CSV` | Encoding o delimitador incorrecto | Guardar el CSV como UTF-8 con delimitador `;` |
| `Invalid date format` | Fecha en formato incorrecto | Usar formato `DDMMYYYY` sin separadores |
| `Invalid priority` | Valor de prioridad no reconocido | Usar solo: `urgent`, `important`, `medium`, `low`, `none` |
| `Plan not found` | PLAN_ID incorrecto | Obtener el ID correcto con `--mode list` |
| `401 Unauthorized` | Token o credenciales invalidas | Verificar `.env` y App Registration en Azure |
| `403 Forbidden` | Permisos insuficientes | Verificar `Tasks.ReadWrite` en App Registration |
