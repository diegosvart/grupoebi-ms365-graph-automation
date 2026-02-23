# Índice de Agent Skills — Planner Import Script

Skills recomendadas para este proyecto según [awesome-agent-skills](https://github.com/VoltAgent/awesome-agent-skills). En Cursor las skills de proyecto se cargan desde `.cursor/skills/`.

## Revisión de seguridad

- **Última revisión:** 2026-02-23
- **Criterios:** Solo se referencian skills del listado curado awesome-agent-skills. Orígenes verificados: equipos oficiales (Trail of Bits, Anthropic, Microsoft, Vercel, Sentry, etc.) o repositorios comunitarios citados en ese listado. Este índice **no ejecuta código externo**; solo enlaza a documentación y repos. Al copiar una skill localmente en el futuro, revisar que no contenga rutas absolutas, secretos ni patrones de prompt injection.
- **Fuente:** [awesome-agent-skills](https://github.com/VoltAgent/awesome-agent-skills) — Security Notice: skills are curated, not audited; validate source before use.

---

## Fase actual (script CLI + Graph + MCP)

| Área | Skill | Origen | Enlace / Notas |
|------|--------|--------|----------------|
| Python y calidad | modern-python | trailofbits | uv, ruff, ty, pytest. Repo: [Trail of Bits](https://github.com/VoltAgent/awesome-agent-skills#security-skills-by-trail-of-bits-team). |
| Seguridad / defaults | insecure-defaults | trailofbits | Detección de secretos y configs inseguras. Refuerza reglas de CLAUDE.md. |
| Revisión de código | fix-review | trailofbits | Verificar que correcciones no introduzcan nuevos fallos (p. ej. graph_request, ETag). |
| MCP | mcp-builder | anthropics / microsoft | Crear o extender MCP servers; alineado con create_plan, create_bucket, create_task como tools. |
| Git / PR | — | — | Cubierto por AGENTS.md y `.cursor/commands/`. Opcional: getsentry/commit, callstackincubator/github. |

---

## Fase backend ampliado (API + más servicios Graph)

| Área | Skill | Origen | Enlace / Notas |
|------|--------|--------|----------------|
| API REST | fastapi-router-py | microsoft | Routers CRUD y auth. Coherente con "API propia" en docs/ESCALAMIENTO_GRAPH.md. |
| Modelos | pydantic-models-py | microsoft | Esquemas request/response y validación. |
| Autenticación | better-auth (create-auth, best-practices) | better-auth | Solo si la API expone auth además de Graph. |

---

## Fase frontend

| Área | Skill | Origen | Enlace / Notas |
|------|--------|--------|----------------|
| React / Next | next-best-practices, react-best-practices | vercel-labs | Si el frontend es Next.js/React. |
| UI / diseño | shadcn-ui, frontend-design | google-labs-code / anthropics | Componentes y estándares de UI. |
| Figma → código | figma, figma-implement-design | openai | Solo si el diseño viene de Figma. |

---

## Opcionales transversales

- **agents-md** (getsentry): mantener AGENTS.md si se añaden más agentes.
- **security-best-practices** (openai): revisión de vulnerabilidades por lenguaje.
- **code-review** (getsentry): revisión de código estructurada antes de PR.

---

## Skill de proyecto incluida

- **planner-graph-csv** — Reglas Graph/Planner, flujos (plan → buckets → tasks) y diseño futuro. Ver `.cursor/skills/planner-graph-csv/SKILL.md`.
