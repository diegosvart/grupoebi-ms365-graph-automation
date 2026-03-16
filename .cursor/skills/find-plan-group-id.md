# Find Plan Group ID

Encuentra el `group-id` de un plan en Microsoft Planner dado su `plan-id`.

## Problema

Cuando ves un plan en Planner (planner.cloud.microsoft), la URL contiene el `plan-id`:
```
https://planner.cloud.microsoft/webui/v1/plan/U_9Ox1FJ10misOuS7zgrJmUADhvP?tid=...
```

Pero para usar `planner_import.py --mode report`, necesitas el `group-id` del grupo M365 propietario del plan, no el `plan-id`.

## Solución

Ejecuta el script `find_plan_group.py` con el `plan-id`:

```bash
python scripts/find_plan_group.py U_9Ox1FJ10misOuS7zgrJmUADhvP
```

## Salida esperada

```
[*] Buscando group-id del plan: U_9Ox1FJ10misOuS7zgrJmUADhvP...
[+] Group ID encontrado: d0f1fcf9-08e5-4415-a2f8-2111b569e0ec

Usa este comando para ver el reporte:
  python planner_import.py --mode report --group-id d0f1fcf9-08e5-4415-a2f8-2111b569e0ec
```

## Cómo obtener el `plan-id`

1. Ve a [Planner](https://planner.cloud.microsoft)
2. Abre cualquiera de tus planes
3. Copia el `plan-id` de la URL: `https://planner.cloud.microsoft/webui/v1/plan/{PLAN-ID}?tid=...`
4. Pasa ese ID al script

## Caso de uso

**Problema típico:**
- Ves 4 planes en Planner
- Pero `python planner_import.py --mode list` solo muestra 2

**Razón:** Tus planes están en **diferentes grupos M365**.

**Solución:**
1. Obtén el `group-id` de cada plan con este script
2. Ejecuta `planner_import.py --mode report --group-id {ID}` para cada grupo

## Implementación

- **Script:** `scripts/find_plan_group.py`
- **Dependencias:** httpx, pydantic-settings, structlog (ya instaladas)
- **Autenticación:** USA el .env del MCP (`C:\Users\usuario\mcp-servers\fornado-planner-mcp\.env`)
- **Output:** Imprime el group-id en stdout

## Notas

- El script requiere credenciales válidas en el .env del MCP
- El `plan-id` es específico del plan (copiar de la URL de Planner)
- El `group-id` es el ID del grupo M365 propietario del plan
- Un grupo puede tener múltiples planes
