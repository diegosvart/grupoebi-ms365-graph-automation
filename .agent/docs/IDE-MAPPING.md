# IDE Mapping

## Goal
`.agent/` is the canonical, shared layer for project context, session memory, security rules, and Graph guidance.

## Canonical Files
- `.agent/context/PROJECT.md`
- `.agent/context/WORKFLOW.md`
- `.agent/context/SECURITY.md`
- `.agent/context/GRAPH.md`
- `.agent/memory/session.schema.json`
- `.agent/memory/current-session.json`
- `.agent/memory/checkpoints/*.json`

## Claude
- `.claude/settings.json` remains a Claude-specific adapter
- Claude hooks in `hooks/` read and write `.agent/memory/*`
- `.claude/rules/*` should stay thin and point back to `.agent/context/*`
- `.claude/commands/checkpoint.md` should save checkpoints in `.agent/memory/checkpoints/`

## Cursor
- `.cursor/rules/*` should reference `.agent/context/*`
- `.cursor/commands/*` and `.cursor/skills/*` remain Cursor-specific UX
- If Cursor hooks are added later, they must target `.agent/memory/current-session.json`

## Codex / Other IDEs
- Read `.agent/context/PROJECT.md` plus `.agent/memory/current-session.json` at the start of a task
- Update `.agent/memory/current-session.json` or save a checkpoint manually at major handoff points
- Do not assume hook support exists

## Local-Only Material
- `.claude/settings.local.json` is not portable and is intentionally excluded from the canonical layer
- `.cursor/mcp.json` remains local because it may contain secrets or machine-specific transport details
