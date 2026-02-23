---
description: Revisión completa de planner_import.py antes de ejecutar en producción. Delega a graph-reviewer si hay cambios en llamadas a Microsoft Graph.
allowed-tools: Read, Bash, Glob
---

Revisar el estado actual del script antes de ejecución en producción:

1. Leer `planner_import.py` completo y verificar:
   - No hay `access_token`, `client_secret` ni contraseñas en el código
   - Todas las funciones Graph tienen type hints
   - `graph_request()` maneja 429 con Retry-After
   - Cada PATCH usa ETag obtenido del GET previo

2. Verificar constantes hardcodeadas:
   - `GROUP_ID` — confirmar que corresponde al grupo correcto
   - `ASSIGNEE_GUID` — confirmar que corresponde al PM correcto
   - `CSV_PATH` — confirmar que el archivo existe antes de ejecutar

3. Validar el CSV objetivo:
   - Ejecutar `python planner_import.py --dry-run` y revisar el output
   - Confirmar: plan name, buckets, número de tareas, llamadas estimadas

4. Si hay cambios recientes en funciones que llaman a Graph API → delegar a graph-reviewer

5. Reportar:
   - Seguridad: OK/ALERTA
   - Constantes: OK/REVISAR
   - Dry-run: OK/ERROR
   - Listo para producción: SI/NO + motivo
