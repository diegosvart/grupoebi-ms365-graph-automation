# Reglas de seguridad — Python + Microsoft Graph

## Credenciales (CRÍTICO)
- `client_secret`, `access_token`, `refresh_token` NUNCA en logs ni prints
- Variables de entorno cargadas desde el .env del MCP — nunca hardcodear
- MSAL cachea tokens automáticamente — no reimplementar token storage
- `ASSIGNEE_GUID` y `GROUP_ID` son UUIDs no sensibles — pueden estar en código

## Microsoft Graph
- Validar permisos antes de implementar: https://graphpermissions.merill.net
- Usar scopes mínimos necesarios — documentar qué permiso requiere cada función
- Manejar 429 con Retry-After header — nunca ignorar throttling
- Manejar paginación con @odata.nextLink — nunca asumir que la primera respuesta es completa
- PATCH en /details siempre requiere ETag del GET previo — nunca omitir

## Python
- Type hints obligatorios en funciones que llaman a Graph API
- Timeouts explícitos en httpx.AsyncClient (no dejar indefinido — actualmente 30s)
- No capturar `Exception` genérica — ser específico con errores de Graph
- `asyncio.sleep()` entre operaciones masivas para respetar rate limits de Planner

## Archivos
- `.env` nunca en control de versiones
- No crear archivos `.pem`, `.pfx`, `.key` en este directorio
- `CLAUDE.md` no debe contener valores reales de credenciales
