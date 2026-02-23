# Plan a ejecutar: Buenas prácticas del agente (Cursor)

Origen: [.cursor/BUENAS-PRACTICAS-AGENTE.md](../BUENAS-PRACTICAS-AGENTE.md)

Marcar con `[x]` al completar cada ítem.

---

## Fase 1 — Bajo esfuerzo, alto impacto

- [ ] **1.1** Crear carpeta `.cursor/plans/` y usarla para planes de tareas grandes.
  - Entregable: carpeta existente; guardar aquí planes con "Save to workspace" tras Plan Mode (Shift+Tab).
  - Criterio: los planes de features/refactors se guardan en `.cursor/plans/` y se referencian en conversaciones.

- [ ] **1.2** Documentar cuándo nueva conversación y uso de @Past Chats.
  - Entregable: `.cursor/rules/contexto.md` (3–5 líneas).
  - Contenido mínimo: cuándo iniciar nueva conversación (nueva tarea, agente confundido, unidad de trabajo terminada); cuándo continuar (misma feature, depurando); usar @Past Chats al empezar nueva en lugar de pegar conversaciones.
  - Criterio: el archivo existe y está en `.cursor/rules/`.

- [ ] **1.3** Añadir regla "objetivos verificables".
  - Entregable: `.cursor/rules/workflow.md` (o ampliar `contexto.md`).
  - Contenido: tras cambios de código, ejecutar tests (`pytest`); iterar hasta que pasen; opcional ejecutar linter.
  - Criterio: la regla indica explícitamente "ejecutar tests tras cambios" y "iterar hasta que pasen".

---

## Fase 2 — Rules enfocadas

- [ ] **2.1** Crear `.cursor/rules/` con rules cortas (si no existe tras Fase 1).
  - Entregable: carpeta `.cursor/rules/` con archivos < ~30 líneas que referencian archivos (no copian bloques grandes).

- [ ] **2.2** Rule de comandos.
  - Entregable: `.cursor/rules/commands.md`.
  - Contenido: comandos del proyecto (los de CLAUDE.md): `python planner_import.py --dry-run`, `pytest`, modos list/delete/tasks/buckets/plan. Referenciar CLAUDE.md para detalle.

- [ ] **2.3** Rule de workflow (si no se cubrió todo en 1.3).
  - Entregable: `.cursor/rules/workflow.md` completo.
  - Contenido: dry-run antes de ejecución real; tests tras cambios; no loggear tokens/secrets; ETag antes de PATCH; reglas no negociables (referencia a CLAUDE.md).

- [ ] **2.4** (Opcional) Rule de código/estilo.
  - Entregable: `.cursor/rules/codigo.md`.
  - Contenido: "Ver `planner_import.py` para estructura de flujos; ver `tests/` para patrones de tests."

---

## Fase 3 — Comandos slash en Cursor

- [ ] **3.1** Crear carpeta `.cursor/commands/`.
  - Entregable: carpeta existente.

- [ ] **3.2** Comando `/review`.
  - Entregable: `.cursor/commands/review.md`.
  - Contenido: descripción en Markdown para el agente: revisar cambios, ejecutar dry-run, comprobar seguridad (tokens, ETag, 429), reportar OK/ALERTA. Puede basarse en `.claude/commands/review.md`.

- [ ] **3.3** (Opcional) Comando `/pr`.
  - Entregable: `.cursor/commands/pr.md`.
  - Contenido: pasos para el agente: `git diff` → mensaje de commit → commit → push → `gh pr create` (si se usa GitHub CLI).

---

## Fase 4 — Hooks (opcional; requiere Cursor Nightly)

- [ ] **4.1** Configurar hook "stop" para iterar hasta que pasen tests.
  - Entregable: `.cursor/hooks.json` y script (ej. `.cursor/hooks/grind.ts` o `.py`).
  - Comportamiento: tras "completed", si los tests fallan, el hook devuelve `followup_message` para que el agente corrija y vuelva a ejecutar tests.
  - Criterio: solo si usas canal Nightly; si no, dejar sin hacer.

---

## Resumen de entregables

| Fase | Entregables |
|------|-------------|
| 1 | `.cursor/plans/`, `.cursor/rules/contexto.md`, `.cursor/rules/workflow.md` (o uno solo con contexto + objetivos verificables) |
| 2 | `.cursor/rules/commands.md`, completar `workflow.md`, opcional `codigo.md` |
| 3 | `.cursor/commands/`, `review.md`, opcional `pr.md` |
| 4 | `.cursor/hooks.json`, `.cursor/hooks/grind.*` (opcional) |

---

## Orden recomendado

1. Ejecutar Fase 1 completa (1.1 → 1.2 → 1.3).
2. Ejecutar Fase 2 (2.1 → 2.2 → 2.3; 2.4 opcional).
3. Ejecutar Fase 3 (3.1 → 3.2; 3.3 opcional).
4. Fase 4 solo si usas Cursor Nightly y quieres el bucle automático.

Al terminar cada ítem, marcar con `[x]` en este archivo.
