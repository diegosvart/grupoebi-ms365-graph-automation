# Planner Import Script

Este archivo es un resumen de entrada para herramientas compatibles con `CLAUDE.md`.
La fuente de verdad compartida para contexto, memoria y reglas vive en `.agent/`.

## Leer primero
- `.agent/context/PROJECT.md`
- `.agent/context/WORKFLOW.md`
- `.agent/context/SECURITY.md`
- `.agent/context/GRAPH.md`
- `.agent/memory/current-session.json`

## Stack
Python 3.14 · `httpx` · Microsoft Graph API · `fornado-planner-mcp`

## Qué hace
Automatiza operaciones de Microsoft Planner desde CSV y genera reportería operativa.

## Comandos clave
- `python planner_import.py --dry-run`
- `python planner_import.py`
- `python planner_import.py --mode plan --csv <ruta> --group-id <guid>`
- `python planner_import.py --mode buckets --csv <ruta>`
- `python planner_import.py --mode tasks --csv <ruta>`
- `python planner_import.py --mode list --filter <texto>`
- `python planner_import.py --mode report --export <ruta>`
- `python planner_import.py --mode email-report --preview`
- `pytest -v`

## Adaptadores específicos
- Claude hooks: `hooks/`
- Claude commands: `.claude/commands/`
- Claude rules: `.claude/rules/`

## Notas
- `.claude/settings.local.json` es local-only y no forma parte de la capa portable.
- Para Git y PRs, seguir `AGENTS.md` y `.agent/context/WORKFLOW.md`.
