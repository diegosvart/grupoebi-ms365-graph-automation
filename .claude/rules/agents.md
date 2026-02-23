# Cuándo delegar a subagentes

## SIEMPRE delegar si la tarea implica:
- Leer más de 5 archivos para completar el análisis
- Output esperado mayor a 100 líneas (logs, análisis, diffs)
- Dominio especializado con agente disponible (graph-reviewer)
- Tarea paralela que no bloquea el flujo principal

## NUNCA delegar si:
- La tarea requiere el contexto de la conversación actual
- El resultado se necesita inmediatamente para el siguiente paso
- Es una sola lectura/edición puntual (usar Read/Edit directamente)

## Criterios concretos para este proyecto

| Tarea | Acción |
|-------|--------|
| Agregar endpoint nuevo que llame a Graph API | Delegar a graph-reviewer |
| Modificar graph_request() o lógica de retry | Delegar a graph-reviewer |
| Analizar errores de Graph API en runtime | Subagente general-purpose |
| Editar planner_import.py (lógica CSV, parsing) | Hacer directamente |
| Buscar patrones en múltiples archivos | Subagente Explore |
| Planificar migración a MCP | /plan → Plan subagent |
| Revisar antes de un cambio grande | Delegar a graph-reviewer |
