# Reporte de Tareas Planner

Modo interactivo para listar, filtrar y exportar tareas de planes Planner.

## Uso básico

```bash
# Listar todos los planes y seleccionar uno
python planner_import.py --mode report

# Filtrar por texto en el título del plan
python planner_import.py --mode report --filter "2026"

# Exportar reporte a CSV
python planner_import.py --mode report --export reports/planner_2026-03-16.csv
```

## Características

- **Selección interactiva**: Elige qué planes ver
- **Tabla por plan**: Buckets, Títulos, Asignados, Estado, % Completado, Fecha de vencimiento
- **Exportación CSV**: Guarda el reporte en CSV con todas las columnas
- **Filtrado**: Busca planes por nombre
- **Sin throttling**: Respeta rate limits de Graph API

## Ejemplos

```bash
# Ver reporte de planes activos en 2026
python planner_import.py --mode report --filter "2026"

# Exportar reporte para análisis
python planner_import.py --mode report --export /tmp/planner_report.csv

# Combinado: filtrar + exportar
python planner_import.py --mode report --filter "Q1" --export reports/q1_tasks.csv
```

## Salida

```
  #    ID                                  Título                               Creado

  1    abc12345...                         Plan Q1 2026                         2026-01-15
  2    def67890...                         Plan Q2 2026                         2026-01-20

Introduce los números a seleccionar (separados por coma) o 'todos': 1,2

📋 Plan Q1 2026
  ────────────────────────────────────────────────────────────────────────────────────────────────────────────
  Bucket              Título                          Asignado             Estado       %  Vence
  ────────────────────────────────────────────────────────────────────────────────────────────────────────────
  Diseño              Mockups finales                 user@domain.com      inProgress  75  2026-03-30
  ...
```

## Exportación CSV

El CSV exportado contiene:
- PlanID, PlanTitle
- BucketID, BucketName
- TaskID, TaskTitle
- Assignee (IDs de usuario)
- Status (notStarted, inProgress, completed)
- PercentComplete (0-100)
- DueDate, CreatedDate
