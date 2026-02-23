# Manual de usuario — planner_import.py

Importación masiva de tareas desde CSV a Microsoft Planner vía Graph API.

---

## 1. Requisitos previos

- **Python 3.x** con dependencias: `pip install httpx python-dotenv`
- **Conexión a red** corporativa o VPN (Graph API es inaccesible desde redes externas sin VPN)
- **`.env` configurado** en `C:\Users\usuario\mcp-servers\fornado-planner-mcp\.env` con:
  ```
  AZURE_TENANT_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
  AZURE_CLIENT_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
  AZURE_CLIENT_SECRET=...
  ```
- **`GROUP_ID`** hardcodeado en el script (línea 41 de `planner_import.py`). Editar si se trabaja con un grupo M365 diferente.

---

## 2. Referencia rápida de flags

| Flag | Descripción | Ejemplo |
|------|-------------|---------|
| `--mode` | Modo de operación (default: `full`) | `--mode tasks` |
| `--csv` | Ruta al CSV (default: ruta hardcodeada en el script) | `--csv C:\data\mi.csv` |
| `--group-id` | Object ID del grupo M365 | `--group-id xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx` |
| `--dry-run` | Simula sin llamar a la API | `--dry-run` |
| `--filter` | Filtra planes por título (solo modos `list` y `delete`) | `--filter "PROJ1"` |

---

## 3. Modos de operación

### 3.1 `--mode full` (por defecto)

**Qué hace:** Crea el plan completo: cabecera + labels + buckets + tareas.

**Cuándo usarlo:** Importación desde cero cuando no existe ningún plan en Planner.

**Llamadas a Graph API:** `~1 (plan) + 2 (labels GET+PATCH) + N_buckets + N_tareas × 3`

#### CSV requerido

El delimitador es `;`. Los campos multi-valor (ChecklistItems, Labels) usan también `;` como separador interno: **deben ir entre comillas dobles** cuando contienen más de un elemento.

**Mínimo** — solo columnas obligatorias:

```
PlanName;BucketName;TaskTitle;StartDate;DueDate;Priority
Control PROJ1;Inicio;Definir alcance;01032026;15032026;medium
Control PROJ1;Inicio;Reunión de arranque;03032026;04032026;urgent
Control PROJ1;Ejecución;Entrega hito 1;01042026;30042026;important
```

**Completo** — todos los campos disponibles:

```
PlanName;BucketName;TaskTitle;TaskDescription;AssignedToEmail;StartDate;DueDate;Priority;PercentComplete;ChecklistItems;Labels
Control PROJ1;Inicio;Definir alcance;Acordar alcance con el cliente;jefe@empresa.com;01032026;15032026;medium;0;"Redactar acta;Validar con cliente";TI
Control PROJ1;Inicio;Reunión de arranque;;coordinador@empresa.com;03032026;04032026;urgent;0;;PM
Control PROJ1;Ejecución;Entrega hito 1;Entrega del primer hito documentado;jefe@empresa.com;01042026;30042026;important;25;"Preparar informe;Enviar a cliente";"TI;PM"
```

> **Campos opcionales:** Si se omite `TaskDescription` la tarea se crea sin descripción. Si se omite `AssignedToEmail` la tarea queda sin asignar. Si se omiten `ChecklistItems` o `Labels` se ignoran. Si se omite `PercentComplete` se asume 0.
>
> **Columnas ignoradas del template:** `ProjectID`, `ProjectName`, `TaskGroupID`, `IsParentTask`, `Status` — pueden existir en el CSV pero el script no las lee.

#### Comando

```bash
python planner_import.py --mode full --csv C:\data\control_proj1.csv --group-id xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
```

O usando los valores por defecto del script:

```bash
python planner_import.py
```

#### Salida esperada

```
Plan     : 'Control PROJ1'
Group    : 198b4a0a-39c7-4521-a546-6a008e3a254a
Labels   : ['TI', 'PM']
Buckets  : 2
Tareas   : 3
Llamadas : ~14

[1/4] Creando plan...
      plan_id: aabbccdd-1234-5678-abcd-000000000001
[2/4] Configurando labels ['TI', 'PM']...
      {'TI': 'category1', 'PM': 'category2'}
[3/4] Creando 2 buckets...
      ✓ 'Inicio'
      ✓ 'Ejecución'
[4/4] Creando 3 tareas (3 llamadas c/u)...
      [01/03] ✓ Definir alcance
      [02/03] ✓ Reunión de arranque
      [03/03] ✓ Entrega hito 1

── RESUMEN ──────────────────────────────
Plan ID   : aabbccdd-1234-5678-abcd-000000000001
Buckets   : 2
Tareas OK : 3
GUIDs OK  : 2
Sin asignar (vacío): 1
─────────────────────────────────────────
```

#### Advertencias

- Si un email no existe en el tenant aparece `[WARN] No se pudo resolver 'email@...': ...` y la tarea se crea sin asignar.
- Si Graph API devuelve 429 aparece `[throttle] esperando Xs...` — el script espera y reintenta automáticamente hasta 3 veces.
- Los labels del CSV solo se aplican si el nombre coincide exactamente con los definidos en la columna `Labels` del CSV (case-sensitive después de `strip()`).

---

### 3.2 `--mode plan`

**Qué hace:** Crea únicamente la cabecera del plan en Planner y configura sus etiquetas (labels). No crea buckets ni tareas.

**Cuándo usarlo:** Cuando se quiere crear el plan primero y añadir buckets/tareas en pasos separados, o para reservar el nombre del plan.

**Llamadas a Graph API:** `1 (POST plan) + 2 (GET+PATCH details para labels)`

#### CSV requerido

Solo se lee la **primera fila** del CSV.

**Mínimo:**

```
PlanName
Control PROJ1
```

**Completo:**

```
PlanName;Labels
Control PROJ1;"TI;PM"
```

> **`Labels`** es opcional. Si se omite el plan se crea sin etiquetas. Si se incluyen múltiples labels, separarlas con `;` dentro de comillas: `"TI;PM;Diseño"`.
>
> Las filas adicionales del CSV son ignoradas en este modo.

#### Comando

```bash
python planner_import.py --mode plan --csv C:\data\plan.csv --group-id xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
```

#### Salida esperada

```
Plan     : 'Control PROJ1'
Group    : 198b4a0a-39c7-4521-a546-6a008e3a254a
Labels   : ['TI', 'PM']

[1/2] Creando plan...
      plan_id: aabbccdd-1234-5678-abcd-000000000001
[2/2] Configurando labels ['TI', 'PM']...
      {'TI': 'category1', 'PM': 'category2'}

── RESUMEN ──────────────────────────────
Plan ID   : aabbccdd-1234-5678-abcd-000000000001
Buckets   : 0
Tareas OK : 0
GUIDs OK  : 0
─────────────────────────────────────────
```

#### Advertencias

- Si se omite la columna `PlanName` o está vacía, el script lanza `ValueError` antes de llamar a la API.

---

### 3.3 `--mode buckets`

**Qué hace:** Añade buckets a un plan ya existente en Planner. El plan se identifica por su ID.

**Cuándo usarlo:** Cuando el plan ya existe (creado con `--mode plan` o manualmente) y se quiere añadir o reorganizar sus buckets.

**Llamadas a Graph API:** `N_buckets × 1 (POST bucket cada uno)`

#### CSV requerido

**Mínimo (y completo):** Solo se leen `PlanID` y `BucketName`.

```
PlanID;BucketName
aabbccdd-1234-5678-abcd-000000000001;Inicio
aabbccdd-1234-5678-abcd-000000000001;Ejecución
aabbccdd-1234-5678-abcd-000000000001;Cierre
```

> **Restricción:** Todos los registros deben tener el **mismo PlanID**. Si hay PlanIDs distintos el script lanza `ValueError` antes de hacer ninguna llamada.
>
> **Columnas ignoradas del template:** `ProjectID`, `ProjectName` — pueden estar en el CSV.

#### Comando

```bash
python planner_import.py --mode buckets --csv C:\data\buckets.csv
```

#### Salida esperada

```
PlanID   : aabbccdd-1234-5678-abcd-000000000001
Buckets  : 3

[1/1] Creando 3 buckets...
      ✓ 'Inicio'
      ✓ 'Ejecución'
      ✓ 'Cierre'

── RESUMEN ──────────────────────────────
Plan ID   :
Buckets   : 3
Tareas OK : 0
GUIDs OK  : 0
─────────────────────────────────────────
```

> El campo `Plan ID` del resumen aparece vacío en este modo (el plan ya existía, no se crea aquí). Es el comportamiento esperado.

#### Advertencias

- Si el PlanID no existe en Planner, Graph API devolverá 404 al intentar crear el primer bucket.
- Usar un CSV por plan. Para añadir buckets a varios planes, ejecutar el script una vez por cada plan.

---

### 3.4 `--mode tasks`

**Qué hace:** Añade tareas a un plan y bucket ya existentes. El plan y el bucket se identifican por sus IDs en el CSV.

**Cuándo usarlo:** Cuando el plan y los buckets ya existen y solo hay que importar tareas. También útil para importaciones incrementales.

**Llamadas a Graph API:** `N_tareas × 3 (POST task + GET details + PATCH details)`

**Limitación importante:** En este modo `LABEL_MAP` está vacío porque no se ejecuta `configure_plan_labels()`. Los labels del campo `Labels` del CSV **no se aplican** a las tareas.

#### CSV requerido

**Mínimo:**

```
PlanID;BucketID;TaskTitle;StartDate;DueDate;Priority
aabbccdd-1234-5678-abcd-000000000001;bbccddee-1234-5678-abcd-000000000002;Definir alcance;01032026;15032026;medium
aabbccdd-1234-5678-abcd-000000000001;bbccddee-1234-5678-abcd-000000000002;Reunión arranque;03032026;04032026;urgent
```

**Completo:**

```
PlanID;BucketID;TaskTitle;TaskDescription;AssignedToEmail;StartDate;DueDate;Priority;PercentComplete;ChecklistItems;Labels
aabbccdd-1234-5678-abcd-000000000001;bbccddee-1234-5678-abcd-000000000002;Definir alcance;Acordar con cliente;jefe@empresa.com;01032026;15032026;medium;0;"Redactar acta;Validar";TI
aabbccdd-1234-5678-abcd-000000000001;bbccddee-1234-5678-abcd-000000000002;Reunión arranque;;coord@empresa.com;03032026;04032026;urgent;0;;
```

> **Cómo obtener PlanID y BucketID:** Usar `--mode list` para ver los IDs de los planes. Los IDs de buckets se obtienen directamente desde la interfaz de Planner (URL del bucket) o via Graph Explorer.
>
> **Labels ignorados:** el campo `Labels` se puede incluir en el CSV pero no tendrá efecto en este modo.
>
> **Columnas ignoradas del template:** `ProjectID`, `ProjectName`, `TaskGroupID`, `IsParentTask`, `Status`.

#### Comando

```bash
python planner_import.py --mode tasks --csv C:\data\tareas.csv
```

#### Salida esperada

```
Tareas   : 2
Llamadas : ~6

[1/1] Creando 2 tareas (3 llamadas c/u)...
      [01/02] ✓ Definir alcance
      [02/02] ✓ Reunión arranque

── RESUMEN ──────────────────────────────
Plan ID   :
Buckets   : 0
Tareas OK : 2
GUIDs OK  : 1
Sin asignar (vacío): 1
─────────────────────────────────────────
```

#### Advertencias

- Si `PlanID` o `BucketID` están vacíos en alguna fila, el script lanza `ValueError` indicando la fila problemática.
- Si el BucketID no pertenece al PlanID indicado, Graph API devolverá 400.

---

### 3.5 `--mode list`

**Qué hace:** Lista todos los planes del grupo M365 en una tabla numerada. Solo lectura — no modifica nada.

**Cuándo usarlo:** Para obtener los IDs de planes antes de usar `--mode tasks`, `--mode buckets` o `--mode delete`. También útil para auditar qué planes existen.

**No requiere CSV.**

#### Comando

```bash
# Listar todos los planes del grupo
python planner_import.py --mode list

# Filtrar por título (coincidencia parcial, insensible a mayúsculas)
python planner_import.py --mode list --filter "PROJ1"
```

#### Salida esperada

```
Planes encontrados: 3 (filtro: 'PROJ1')

  #    ID                                   Título                                   Creado
  ──────────────────────────────────────────────────────────────────────────────────────────
  1    aabbccdd-1234-5678-abcd-000000000001 Control PROJ1                            2026-02-01
  2    bbccddee-1234-5678-abcd-000000000002 Control PROJ1 (borrador)                 2026-02-10
  3    ccddeeaa-1234-5678-abcd-000000000003 Control PROJ1 v2                         2026-02-20

```

#### Advertencias

- `--dry-run` no tiene efecto en modo `list` (ya es de solo lectura).
- Si el grupo tiene muchos planes, el script pagina automáticamente con `@odata.nextLink`.

---

### 3.6 `--mode delete`

**Qué hace:** Muestra la lista de planes → permite seleccionar cuáles eliminar → pide confirmación → los elimina.

**Cuándo usarlo:** Para limpiar planes de prueba o eliminar planes obsoletos de forma controlada.

**No requiere CSV.**

**Llamadas a Graph API por plan:** `1 (GET para obtener ETag) + 1 (DELETE)`

#### Comando

```bash
# Interactivo — muestra todos los planes y pide selección
python planner_import.py --mode delete

# Con filtro previo por título
python planner_import.py --mode delete --filter "borrador"

# Simular borrado sin ejecutar (muestra selección pero no llama a la API)
python planner_import.py --mode delete --filter "borrador" --dry-run
```

#### Flujo interactivo paso a paso

```
Planes encontrados: 2 (filtro: 'borrador')

  #    ID                                   Título                                   Creado
  ──────────────────────────────────────────────────────────────────────────────────────────
  1    aabbccdd-1234-5678-abcd-000000000001 Control PROJ1 (borrador)                 2026-02-10
  2    bbccddee-1234-5678-abcd-000000000002 Prueba borrador Feb                      2026-02-15

  Introduce los números a eliminar (separados por coma) o 'todos': 1,2
```

> Escribir los números de la tabla separados por coma (`1,2`) o `todos` para seleccionar todos.

```
  Planes seleccionados para eliminar (2):
    - Control PROJ1 (borrador)  [aabbccdd-1234-5678-abcd-000000000001]
    - Prueba borrador Feb  [bbccddee-1234-5678-abcd-000000000002]

  ¿Confirmar eliminación de 2 planes? (s/N): s
  [1/2] Eliminando 'Control PROJ1 (borrador)'... ✓
  [2/2] Eliminando 'Prueba borrador Feb'... ✓

Eliminados : 2
```

> Escribir `s` para confirmar o cualquier otra tecla (o Enter) para cancelar.

#### Con `--dry-run`

Muestra los planes seleccionados pero se detiene antes de pedir confirmación:

```
  Planes seleccionados para eliminar (2):
    - Control PROJ1 (borrador)  [aabbccdd-...]
    - Prueba borrador Feb  [bbccddee-...]

[DRY RUN] Sin cambios en Planner.

Eliminados : 0
```

#### Advertencias

- **La eliminación es irreversible.** Una vez borrado un plan no se puede recuperar.
- Si no se selecciona ningún número válido, aparece `Sin selección. Saliendo.` y el script termina sin borrar nada.
- Si un plan falla al eliminarse aparece `✗ <motivo>` y el script continúa con el siguiente.

---

## 4. Tabla de valores válidos

| Campo | Valores aceptados | Notas |
|-------|-------------------|-------|
| `Priority` | `urgent` · `important` · `medium` · `low` · `none` | Insensible a mayúsculas. Valor desconocido → `low` (5) |
| `StartDate` / `DueDate` | `DDMMAAAA` | Ej: `01032026` = 1 marzo 2026 |
| `PercentComplete` | Entero `0`–`100` | Si se omite se asume `0` |
| `ChecklistItems` | Items separados por `;` | Un item: `Revisar`. Varios: `"Revisar;Aprobar;Publicar"` (comillas obligatorias con el delimitador `;`) |
| `Labels` | Nombres de etiqueta separados por `;` | Un label: `TI`. Varios: `"TI;PM"`. Solo funcionan en modo `full` y `plan`. Los nombres deben coincidir exactamente con los definidos en la columna `Labels` del CSV |

### Mapeo de prioridad a valor numérico de Graph API

| Texto en CSV | Valor Graph API |
|--------------|-----------------|
| `urgent` | 1 |
| `important` | 2 |
| `medium` | 3 |
| `low` | 5 |
| `none` | 9 |
| (cualquier otro) | 5 (low) |

---

## 5. Modo dry-run

Disponible en todos los modos excepto `list` (que ya es de solo lectura).

- **No requiere `.env` ni credenciales** — útil para validar el CSV antes de una importación real.
- No hace ninguna llamada a Graph API.
- Imprime el plan de ejecución: nombre del plan, buckets, tareas (en modo `full`), o la selección de planes a borrar (en modo `delete`).

```bash
# Validar un CSV de importación completa sin credenciales
python planner_import.py --mode full --csv C:\data\mi.csv --dry-run

# Simular borrado
python planner_import.py --mode delete --filter "prueba" --dry-run
```

Salida de ejemplo (modo `full` con `--dry-run`):

```
Plan     : 'Control PROJ1'
Group    : 198b4a0a-39c7-4521-a546-6a008e3a254a
Labels   : ['TI', 'PM']
Buckets  : 2
Tareas   : 3
Llamadas : ~14

[DRY RUN] Sin cambios en Planner.
  Bucket 'Inicio' -> 2 tareas
  Bucket 'Ejecución' -> 1 tareas

── RESUMEN ──────────────────────────────
Plan ID   : (dry run)
Buckets   : 0
Tareas OK : 0
GUIDs OK  : 0
─────────────────────────────────────────
```

---

## 6. Errores comunes y solución

| Error / Mensaje | Causa | Solución |
|-----------------|-------|---------|
| `ModuleNotFoundError: No module named 'src'` | MCP no instalado en `C:\Users\usuario\mcp-servers\fornado-planner-mcp` o la ruta de `MCP_PATH` en el script no es correcta | Verificar que el MCP existe en esa ruta; editar `MCP_PATH` en el script si es distinta |
| `[throttle] esperando Xs...` | Graph API devolvió 429 (demasiadas peticiones) | Normal — el script espera el tiempo indicado y reintenta. No cerrar la terminal |
| `RuntimeError: Máximo de reintentos para POST /planner/tasks` | 3 intentos consecutivos con 429 sin recuperación | Esperar unos minutos y volver a lanzar el script |
| `[WARN] No se pudo resolver 'email@...'` | El email no existe en el tenant o no tiene licencia asignada | Verificar el email en el CSV; la tarea se crea igualmente sin asignar |
| `ValueError: Modo 'buckets' requiere que todos los registros tengan el mismo PlanID` | El CSV de modo `buckets` mezcla varios PlanIDs | Dividir en un CSV por plan y ejecutar una vez por cada plan |
| `ValueError: Modo 'tasks' requiere PlanID y BucketID. Fila: {...}` | Alguna fila tiene PlanID o BucketID vacíos | Revisar el CSV y completar los campos faltantes |
| `ValueError: El CSV de modo 'plan' está vacío` | El CSV no tiene filas de datos | Añadir al menos una fila con PlanName |
| `httpx.HTTPStatusError: 404` | El PlanID o BucketID del CSV no existe en Planner | Verificar los IDs con `--mode list`; los IDs son sensibles a mayúsculas |
| `httpx.HTTPStatusError: 401` | Token expirado o credenciales incorrectas en el `.env` | Verificar `AZURE_TENANT_ID`, `AZURE_CLIENT_ID` y `AZURE_CLIENT_SECRET` en el `.env` |
