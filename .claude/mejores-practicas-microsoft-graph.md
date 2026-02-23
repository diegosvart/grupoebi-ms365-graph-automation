# Mejores Prácticas — Implementación Rápida para Claude Code
## Extraídas de proyecto Next.js + Supabase · Adaptadas para Python + Microsoft Graph

---

> **Para Claude Code:** Este documento contiene mejoras concretas para implementar en el ambiente actual.
> El proyecto tiene: MCP de Microsoft + API Python que se comunica con Microsoft Graph.
> Implementa en orden de prioridad. Cada práctica tiene un criterio de éxito verificable.

---

## PRIORIDAD 1 — Implementar ahora (impacto inmediato, menos de 30 minutos)

---

### P1.1 — CLAUDE.md conciso con contexto real del proyecto

**El problema que resuelve:** Sin CLAUDE.md, Claude Code reconstruye el contexto del proyecto en cada sesión leyendo archivos. Con él, el contexto está disponible desde el primer mensaje.

**Crear o reemplazar `CLAUDE.md` en la raíz del proyecto:**

```markdown
# [nombre del proyecto]

## Stack
Python 3.x · FastAPI (o Flask) · Microsoft Graph API · [nombre del MCP de Microsoft]

## Qué hace este proyecto
[Una línea: qué problema resuelve, para quién]

## Comandos
- `[comando para correr la API]` — servidor de desarrollo
- `[comando para tests]` — suite de tests
- `[comando para lint]` — verificación de código
- `[comando para tipos]` — mypy o pyright

## Arquitectura
- Autenticación: OAuth 2.0 / MSAL → Microsoft Graph
- Cliente Graph: `src/graph/client.py`
- Endpoints propios: `src/api/`
- Modelos: `src/models/`

## Variables de entorno requeridas
Ver `.env.example` — nunca commitear `.env`

## Reglas no negociables
1. Nunca loggear `access_token` ni `client_secret`
2. Validar input antes de llamar a Graph API
3. Manejar errores de Graph API explícitamente (no swallow exceptions)
4. Tests deben pasar antes de cualquier commit

## MCP activo
[nombre del MCP de Microsoft] — para operaciones con Microsoft 365/Graph
Activar antes de iniciar sesión si la sesión involucra operaciones con Microsoft.

## Errores aprendidos
<!-- Agregar aquí después de cada corrección: qué salió mal y la regla nueva -->
```

**Criterio:** `wc -l CLAUDE.md` ≤ 80 líneas. Sin secciones vacías.

---

### P1.2 — Política de MCP: activar antes, nunca durante la sesión

**El problema que resuelve:** Activar un MCP en medio de una sesión activa invalida el cache completo de Claude. En una sesión larga, esto puede multiplicar el costo de tokens por hasta 12.5×.

**Regla operativa inmediata:**

```bash
# ✅ Correcto — activar ANTES de iniciar sesión
claude mcp enable microsoft && claude

# ❌ Incorrecto — activar después de haber iniciado
# (dentro de una sesión ya activa)
claude mcp enable microsoft
```

**Por qué:** Claude cachea el system prompt (que incluye las definiciones de herramientas de los MCPs) al inicio. Si agregas un MCP después, el prefijo cambia → cache miss total → pagas 1.25× en lugar de 0.1× por todos los tokens cacheados.

**Para este proyecto:** Si la sesión involucra operaciones con Microsoft Graph (llamadas a la API, consultas, etc.) → activar el MCP antes. Si la sesión es solo trabajo en Python sin tocar Microsoft → no activar el MCP → ahorro de tokens inmediato.

**Criterio:** Añadir esta decisión al inicio de cada sesión como hábito verificable.

---

### P1.3 — `.env.example` con instrucciones inline

**El problema que resuelve:** Variables de entorno mal configuradas son la causa #1 de errores en proyectos con APIs externas. Un `.env.example` descriptivo elimina ambigüedad.

**Crear `/.env.example`:**

```bash
# Microsoft Entra ID (Azure AD)
# Obtener en: https://portal.azure.com → Azure Active Directory → App registrations
AZURE_TENANT_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
AZURE_CLIENT_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
AZURE_CLIENT_SECRET=              # NUNCA commitear este valor

# Microsoft Graph
# Scopes requeridos para este proyecto: [listar scopes exactos]
GRAPH_API_BASE_URL=https://graph.microsoft.com/v1.0

# API propia
API_PORT=8000
API_ENV=development               # development | staging | production

# [Agregar otras variables del proyecto]
```

**Regla:** `.env` y `.env.local` en `.gitignore`. `.env.example` commiteado siempre.

**Criterio:** `git ls-files .env` retorna vacío. `git ls-files .env.example` retorna el archivo.

---

## PRIORIDAD 2 — Implementar esta semana (impacto alto, 1-2 horas)

---

### P2.1 — Agente especializado para Microsoft Graph

**El problema que resuelve:** Sin un agente específico, Claude Code maneja las consultas de Graph API con conocimiento genérico. Un agente especializado conoce los patrones, errores comunes y convenciones de Microsoft Graph.

**Crear `.claude/agents/graph-reviewer.md`:**

```markdown
---
name: graph-reviewer
description: Revisa llamadas a Microsoft Graph API, manejo de tokens OAuth y permisos de aplicación. USAR antes de implementar cualquier endpoint nuevo que llame a Graph. Especializado en Python + MSAL + Graph API.
tools: Read, Bash, Glob
model: sonnet
---

Eres un experto en Microsoft Graph API y autenticación OAuth 2.0 con MSAL.

## Checklist de revisión

### Autenticación
- [ ] `client_secret` nunca aparece en logs ni en respuestas de API
- [ ] Tokens se obtienen con MSAL, no implementación manual de OAuth
- [ ] Token refresh se maneja automáticamente (no manual)
- [ ] Scopes son los mínimos necesarios (principio de mínimo privilegio)

### Llamadas a Graph API
- [ ] Errores HTTP de Graph se manejan explícitamente (401, 403, 404, 429, 503)
- [ ] Rate limiting: 429 Too Many Requests tiene retry con exponential backoff
- [ ] Paginación: respuestas con `@odata.nextLink` se iteran completamente
- [ ] Filtros OData en el query, no en Python (más eficiente)

### Permisos
- [ ] Permisos de aplicación vs delegados — usar el correcto según el caso
- [ ] Documentar en comentarios qué permiso de Graph requiere cada función
- [ ] No solicitar `Directory.ReadWrite.All` cuando `User.Read` es suficiente

### Python específico
- [ ] Type hints en todas las funciones que llaman a Graph
- [ ] Modelos Pydantic para validar respuestas de Graph antes de procesarlas
- [ ] Timeouts configurados en las requests (no dejar indefinido)

## Output
[CRÍTICO] — bloquea el merge
[ADVERTENCIA] — debe resolverse antes del PR
[INFO] — mejora opcional
```

**Criterio:** El archivo existe en `.claude/agents/`. `/agents` en Claude Code lo muestra disponible.

---

### P2.2 — Hooks de memory persistence entre sesiones

**El problema que resuelve:** Cada sesión de Claude Code empieza desde cero. Con estos hooks, el contexto de la sesión anterior (branch, tareas completadas, próximo paso) se carga automáticamente al iniciar.

**Crear `hooks/session-start.js`:**

```javascript
#!/usr/bin/env node
const fs = require('fs');
const path = require('path');

const sessionsDir = path.join(process.cwd(), '.claude', 'sessions');
if (!fs.existsSync(sessionsDir)) process.exit(0);

const sevenDaysAgo = Date.now() - 7 * 24 * 60 * 60 * 1000;
const sessions = fs.readdirSync(sessionsDir)
  .filter(f => f.endsWith('.json'))
  .map(f => ({ name: f, path: path.join(sessionsDir, f), mtime: fs.statSync(path.join(sessionsDir, f)).mtimeMs }))
  .filter(s => s.mtime > sevenDaysAgo)
  .sort((a, b) => b.mtime - a.mtime);

if (sessions.length === 0) process.exit(0);

try {
  const s = JSON.parse(fs.readFileSync(sessions[0].path, 'utf8'));
  console.log('\n📋 Sesión anterior:');
  if (s.branch) console.log(`Branch: ${s.branch}`);
  if (s.pending?.length) console.log(`Pendiente: ${s.pending.join(', ')}`);
  if (s.next_step) console.log(`Próximo paso: ${s.next_step}`);
  console.log('');
} catch { process.exit(0); }
```

**Crear `hooks/session-end.js`:**

```javascript
#!/usr/bin/env node
const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

const sessionsDir = path.join(process.cwd(), '.claude', 'sessions');
if (!fs.existsSync(sessionsDir)) fs.mkdirSync(sessionsDir, { recursive: true });

let branch = 'unknown';
try { branch = execSync('git rev-parse --abbrev-ref HEAD', { encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'] }).trim(); } catch {}

const today = new Date().toISOString().split('T')[0];
const file = path.join(sessionsDir, `${today}.json`);
let existing = {};
try { existing = JSON.parse(fs.readFileSync(file, 'utf8')); } catch {}

fs.writeFileSync(file, JSON.stringify({
  ...existing,
  branch,
  last_updated: new Date().toISOString(),
  completed: process.env.CLAUDE_COMPLETED_TASKS?.split('\n').filter(Boolean) || existing.completed || [],
  pending: process.env.CLAUDE_PENDING_TASKS?.split('\n').filter(Boolean) || existing.pending || [],
  next_step: process.env.CLAUDE_NEXT_STEP || existing.next_step || ''
}, null, 2));
```

**Crear o actualizar `.claude/settings.json`:**

```json
{
  "hooks": {
    "SessionStart": [
      { "type": "command", "command": "node hooks/session-start.js" }
    ],
    "Stop": [
      { "type": "command", "command": "node hooks/session-end.js", "async": true }
    ],
    "PreToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [{ "type": "command", "command": "node hooks/guard-sensitive.js" }]
      }
    ]
  }
}
```

**Crear `hooks/guard-sensitive.js`** (protege archivos críticos):

```javascript
#!/usr/bin/env node
const filePath = process.env.CLAUDE_TOOL_INPUT_FILE_PATH || '';
const BLOCKED = [/\.env($|\.)/, /client_secret/, /\.pem$/, /\.key$/];
if (BLOCKED.some(p => p.test(filePath))) {
  console.error(`🚫 Escritura bloqueada: ${filePath}`);
  process.exit(2);
}
```

**Agregar al `.gitignore`:**
```
.claude/sessions/
CLAUDE.local.md
```

**Criterio:** Al iniciar `claude`, si existe una sesión del día anterior, aparece el contexto en los primeros mensajes. `node hooks/session-start.js` no lanza errores.

---

### P2.3 — Rule de delegación a agentes (cuándo no actuar directamente)

**El problema que resuelve:** Sin criterios explícitos, Claude Code hace todo en el contexto principal, contaminándolo con output verbose de tareas que podría delegar.

**Crear `.claude/rules/agents.md`:**

```markdown
# Cuándo delegar a subagentes

## SIEMPRE delegar si la tarea implica:
- Leer más de 5 archivos para completar el análisis
- Output esperado mayor a 100 líneas (logs, análisis, diffs)
- Dominio especializado con agente disponible (graph-reviewer, etc.)
- Tarea paralela que no bloquea el flujo principal

## NUNCA delegar si:
- La tarea requiere el contexto de la conversación actual
- El resultado se necesita inmediatamente para el siguiente paso
- Es una sola lectura/edición puntual (usar Read/Edit directamente)

## Criterios concretos para este proyecto:

| Tarea | Acción |
|-------|--------|
| Revisar nueva función que llama a Graph API | Delegar a graph-reviewer |
| Analizar logs de error de Microsoft Graph | Subagente general-purpose |
| Escribir/editar un archivo Python | Hacer directamente |
| Buscar patrones en múltiples archivos | Subagente Explore (built-in) |
| Planificar feature compleja | /plan → planner subagent |
| Revisar antes de PR | Delegar a code-reviewer |
```

**Criterio:** El archivo existe. El contenido refleja la realidad del proyecto (ajustar la tabla según los agentes disponibles).

---

### P2.4 — Rule de seguridad para Microsoft Graph y Python

**Crear `.claude/rules/security.md`:**

```markdown
# Reglas de seguridad — Python + Microsoft Graph

## Credenciales (CRÍTICO)
- `client_secret`, `access_token`, `refresh_token` NUNCA en logs
- Usar variables de entorno — nunca hardcodear en código
- MSAL cachea tokens automáticamente — no reimplementar token storage

## Microsoft Graph
- Validar permisos antes de implementar: https://graphpermissions.merill.net
- Usar scopes mínimos necesarios — documentar cuál requiere cada función
- Manejar 429 (rate limit) con exponential backoff obligatorio
- Manejar paginación con @odata.nextLink — nunca asumir que la primera respuesta es completa

## Python
- Type hints obligatorios en funciones que llaman a Graph API
- Modelos Pydantic para validar respuestas externas (no confiar en el schema de Graph)
- Timeouts explícitos en todas las HTTP requests (default: 30s)
- No capturar Exception genérica — ser específico con los errores de Graph

## Git
- `.env` en .gitignore siempre
- No commitear archivos `.pem`, `.pfx`, `.key`
- Conventional commits: feat/fix/docs/refactor/test/chore
```

---

## PRIORIDAD 3 — Implementar cuando haya tiempo (impacto medio, configuración)

---

### P3.1 — Slash command `/review` para revisión antes de PR

**Crear `.claude/commands/review.md`:**

```markdown
---
description: Revisión completa antes de crear un PR. Delega a graph-reviewer si hay cambios en llamadas a Microsoft Graph.
allowed-tools: Read, Bash, Glob
---

Revisar los cambios actuales antes del PR:

1. Ejecutar tests: `[comando de tests del proyecto]`
2. Ejecutar lint: `[comando de lint]`
3. Si hay cambios en archivos que llaman a Graph API → delegar a graph-reviewer
4. Verificar que `.env` no aparece en `git diff`
5. Verificar que no hay `client_secret` o `access_token` en el diff
6. Reportar: tests ✅/❌, lint ✅/❌, seguridad ✅/❌

No crear el PR hasta que los 3 checks pasen.
```

---

### P3.2 — Slash command `/checkpoint` para guardar estado

**Crear `.claude/commands/checkpoint.md`:**

```markdown
---
description: Guardar el estado actual de la sesión para continuar en la próxima.
allowed-tools: Write, Bash
---

Guardar checkpoint de la sesión actual:

1. Identificar branch actual con `git rev-parse --abbrev-ref HEAD`
2. Listar cambios pendientes con `git status`
3. Resumir en 3 líneas: qué se completó, qué falta, cuál es el próximo paso
4. Guardar en `.claude/sessions/checkpoint-[fecha].json`:
   ```json
   {
     "branch": "[branch]",
     "completed": ["..."],
     "pending": ["..."],
     "next_step": "..."
   }
   ```

Confirmar: "✅ Checkpoint guardado. Próxima sesión empezará con este contexto."
```

---

### P3.3 — Estructura mínima de rules recomendada

Si el proyecto no tiene rules, esta es la estructura mínima útil:

```
.claude/
├── agents/
│   └── graph-reviewer.md        # Creado en P2.1
├── commands/
│   ├── review.md                # Creado en P3.1
│   └── checkpoint.md            # Creado en P3.2
├── rules/
│   ├── agents.md                # Creado en P2.3
│   └── security.md              # Creado en P2.4
├── sessions/                    # Creado automáticamente por hooks
└── settings.json                # Creado en P2.2
```

---

## Lo que NO implementar en este proyecto

Estas prácticas del proyecto de origen **no aplican** aquí:

| Práctica | Por qué no aplica |
|----------|-------------------|
| Skills de Next.js / Shadcn / Supabase | Stack diferente |
| MCPs de Vercel, Playwright, Supabase | No son parte de este proyecto |
| Arquitectura de 3 capas de MCPs | Solo hay 1 MCP relevante aquí |
| Hooks de Prettier / format-on-save para TypeScript | El proyecto es Python |
| ecc-agentshield | Útil si el proyecto escala a configuración compleja de Claude |

---

## Verificación final — checklist de implementación

Ejecutar en el directorio del proyecto después de implementar:

```bash
# Estructura mínima creada
ls CLAUDE.md .env.example .claude/settings.json .claude/agents/graph-reviewer.md

# Hooks son Node.js puro y no fallan
node hooks/session-start.js 2>&1 || echo "revisar hook"
node hooks/guard-sensitive.js 2>&1 || echo "revisar hook"

# .env no está en git
git ls-files .env | wc -l  # debe ser 0

# Sessions está en .gitignore
grep ".claude/sessions" .gitignore  # debe encontrarlo

# Agente disponible en Claude Code
# (verificar corriendo claude y ejecutando /agents)
```

---

*Extraído de proyecto Next.js + Supabase Plugin — Febrero 2026*
*Adaptado para Python + Microsoft Graph + MCP de Microsoft*
*Implementación estimada: Prioridad 1 = 30 min · Prioridad 2 = 1-2 hrs · Prioridad 3 = 30 min*
