# Análisis: Buenas prácticas del agente (Cursor Blog) vs estado del proyecto

Referencia: [Best practices for coding with agents · Cursor](https://cursor.com/blog/agent-best-practices)

---

## 1. Resumen ejecutivo

| Área | Estado | Notas |
|------|--------|--------|
| Planes antes de codificar | ❌ No aplicado | No hay uso de Plan Mode ni `.cursor/plans/` |
| Contexto (Rules) | ⚠️ Parcial | `CLAUDE.md` actúa como regla única; el blog recomienda `.cursor/rules/` |
| Comandos (slash `/`) | ❌ No aplicado | No existe `.cursor/commands/` para Cursor |
| Hooks / Skills | ❌ No aplicado | No hay `.cursor/hooks.json` ni bucles (ej. hasta que pasen tests) |
| Objetivos verificables | ✅ Aplicado | pytest en `tests/` |
| Cuándo nueva conversación / @Past Chats | ❌ No documentado | No hay regla ni guía en el repo |
| Revisión de código (Agent Review) | ⚠️ Uso manual | Existe `.claude/commands/review.md` pero no equivalente en Cursor |
| TDD documentado para el agente | ❌ No aplicado | No hay flujo explícito “tests → fallan → implementar → iterar” |
| MCP | ✅ Aplicado | `fornado-planner-mcp`, GitHub en `.cursor/mcp.json` |

---

## 2. Buenas prácticas del blog (checklist)

### 2.1 Empezar con planes
- **Plan Mode (Shift+Tab):** investigar código, preguntas, plan en Markdown, aprobación antes de construir.
- **Guardar planes:** “Save to workspace” → `.cursor/plans/` para documentar y retomar.
- **Volver al plan:** si el agente se desvía, revertir, refinar el plan y volver a ejecutar.

**Estado:** No hay carpeta `.cursor/plans/` ni instrucción en el proyecto para usar Plan Mode o guardar planes ahí.

---

### 2.2 Gestionar contexto
- **Dejar que el agente encuentre contexto:** no etiquetar todos los archivos; usar búsqueda.
- **Cuándo nueva conversación:** nueva tarea, agente confundido o misma unidad de trabajo terminada → nueva. Misma feature, depurar lo recién construido → continuar.
- **Referenciar trabajo pasado:** usar `@Past Chats` en lugar de pegar conversaciones largas.

**Estado:** No hay regla ni doc que indique “cuándo nueva conversación” o “usar @Past Chats” para este repo.

---

### 2.3 Extender el agente

#### Rules (contexto estático)
- Archivos Markdown en `.cursor/rules/`.
- Incluir: comandos, estilo de código, workflow, **referencias a archivos** (no copiar contenido).
- Evitar: guías enormes, documentar cada comando, edge cases raros.

**Estado:** El proyecto usa `CLAUDE.md` como regla única (workspace rule). Equivale a “una rule grande”; el blog sugiere rules **enfocadas** en `.cursor/rules/`.

#### Skills / Comandos (dinámicos)
- **Comandos:** workflows con `/` en el input; guardar en `.cursor/commands/` (Markdown).
- Ejemplos: `/pr`, `/review`, `/fix-issue [number]`, `/update-deps`.
- **Hooks:** scripts antes/después (ej. `.cursor/hooks.json` + script que devuelve `followup_message` para seguir hasta que pasen tests).

**Estado:** No existe `.cursor/commands/`. Hay `.claude/commands/` (review, checkpoint) para otra herramienta, no para el agente de Cursor.

---

### 2.4 Objetivos verificables
- Tests, tipado, linters como señal clara de “correcto”.
- TDD: escribir tests → confirmar que fallan → implementar → iterar hasta que pasen.

**Estado:** ✅ Hay `tests/` con pytest. ❌ No hay regla que diga “iterar hasta que pasen los tests” ni flujo TDD escrito para el agente.

---

### 2.5 Revisión de código
- Durante generación: ver diffs, Esc para cortar.
- Después: Review → Find Issues.
- Para cambios locales: Source Control → Agent Review vs main.
- Diagramas: pedir Mermaid para flujos/arquitectura.

**Estado:** Uso manual posible; no hay regla en el repo que obligue a “Find Issues” o “Agent Review” después de cambios.

---

### 2.6 Workflows habituales
- **TDD:** tests → fallan → commit tests → implementar sin tocar tests → iterar hasta verde.
- **Git:** comando tipo `/pr`: diff → mensaje → commit → push → `gh pr create`.
- **Comandos:** guardar en `.cursor/commands/` y versionar.

**Estado:** TDD y `/pr` no están definidos como comandos ni como reglas en Cursor para este proyecto.

---

## 3. Plan de implementación (prácticas no aplicadas)

### Fase 1 — Bajo esfuerzo, alto impacto

| # | Acción | Entregable | Criterio de éxito |
|---|--------|------------|-------------------|
| 1.1 | Crear carpeta y uso de planes | `.cursor/plans/` (puede estar vacía al inicio) | Los planes de tareas grandes se guardan en `.cursor/plans/` y se referencian en conversaciones. |
| 1.2 | Documentar cuándo nueva conversación y @Past Chats | Un archivo en `.cursor/rules/` (ej. `contexto.md`) | Contiene 3–5 líneas: cuándo nueva conversación, cuándo continuar, usar @Past Chats al empezar nueva. |
| 1.3 | Añadir regla “objetivos verificables” | Misma rule o `workflow.md` en `.cursor/rules/` | Indica: tras cambios de código, ejecutar tests (y opcionalmente linter); iterar hasta que pasen. |

### Fase 2 — Rules enfocadas (sustituir/complementar CLAUDE.md)

| # | Acción | Entregable | Criterio de éxito |
|---|--------|------------|-------------------|
| 2.1 | Crear `.cursor/rules/` con rules cortas | `commands.md`, `workflow.md`, `codigo.md` (o nombres similares) | Cada archivo < ~30 líneas; referencian `planner_import.py` o `tests/` en lugar de copiar código. |
| 2.2 | commands.md | Comandos del proyecto (los de CLAUDE.md) | Incluye: `python planner_import.py --dry-run`, `pytest`, y los modos list/delete/tasks/buckets/plan. |
| 2.3 | workflow.md | Flujo de trabajo para el agente | Incluye: dry-run antes de ejecución real, tests tras cambios, no loggear tokens/secrets, ETag antes de PATCH. |
| 2.4 | codigo.md (opcional) | Estilo / referencias | Ej.: “Ver `planner_import.py` para estructura de flujos; ver `tests/` para patrones de tests.” |

Mantener **CLAUDE.md** como resumen del proyecto (stack, arquitectura, MCP, GitHub, errores aprendidos) y usar **rules** para comportamiento del agente (comandos, workflow, contexto).

### Fase 3 — Comandos slash en Cursor

| # | Acción | Entregable | Criterio de éxito |
|---|--------|------------|-------------------|
| 3.1 | Crear `.cursor/commands/` | Carpeta existente | Equivalente Cursor a lo que hace `.claude/commands/review.md`. |
| 3.2 | Comando `/review` | `.cursor/commands/review.md` | Descripción en Markdown: revisar cambios, dry-run, seguridad (tokens, ETag, 429), reportar OK/ALERTA. |
| 3.3 | Comando `/pr` (opcional) | `.cursor/commands/pr.md` | Pasos: `git diff` → mensaje → commit → push → `gh pr create` (si usas GitHub CLI). |

### Fase 4 — Hooks (opcional, canal Nightly)

| # | Acción | Entregable | Criterio de éxito |
|---|--------|------------|-------------------|
| 4.1 | Hook “stop” hasta tests verdes | `.cursor/hooks.json` + script (ej. `.cursor/hooks/grind.py` o `.ts`) | Tras “completed”, si tests fallan, el hook devuelve `followup_message` para que el agente corrija y vuelva a ejecutar tests. |

Requisito: Cursor en canal Nightly para Skills/hooks. Si no usas Nightly, dejar esta fase para más adelante.

---

## 4. Orden sugerido de ejecución

1. **Fase 1** (1.1 + 1.2 + 1.3): crear `.cursor/plans/`, una rule de contexto y una de “tests/objetivos verificables”.
2. **Fase 2** (2.1–2.4): crear `.cursor/rules/` y repartir contenido de CLAUDE.md en rules enfocadas, sin duplicar bloques enormes.
3. **Fase 3** (3.1–3.3): añadir `/review` (y opcionalmente `/pr`) en `.cursor/commands/`.
4. **Fase 4** (4.1): solo si usas Nightly y quieres bucles automáticos “hasta que pasen tests”.

---

## 5. Qué no hace falta cambiar

- **CLAUDE.md:** seguir como documento principal del proyecto (stack, arquitectura, MCP, reglas no negociables, errores aprendidos). Las rules en `.cursor/rules/` pueden **referenciar** CLAUDE.md para “reglas no negociables” y “comandos” en lugar de duplicarlos.
- **Tests:** mantener pytest y la estructura actual; solo añadir la **regla** de que el agente debe ejecutar tests tras cambios relevantes.
- **MCP:** configuración actual en `.cursor/mcp.json` está alineada con las buenas prácticas (activar antes de sesión, documentado en CLAUDE.md).

---

## 6. Referencia rápida blog → proyecto

| Práctica (blog) | En este proyecto |
|-----------------|------------------|
| Plan Mode / .cursor/plans/ | ❌ → Fase 1.1 |
| Rules en .cursor/rules/ | ⚠️ CLAUDE.md único → Fase 2 |
| Comandos en .cursor/commands/ | ❌ → Fase 3 |
| Hooks (stop/grind) | ❌ → Fase 4 (opcional) |
| Nueva conversación / @Past Chats | ❌ → Fase 1.2 |
| Objetivos verificables (tests) | ✅ tests; ❌ regla → Fase 1.3 |
| TDD documentado para agente | ❌ → Fase 1.3 / workflow.md |
| Agent Review / Find Issues | Uso manual; opcional mencionar en workflow.md |

Si quieres, el siguiente paso puede ser implementar la Fase 1 (crear `.cursor/plans/` y los dos archivos de rules: contexto + objetivos verificables).
