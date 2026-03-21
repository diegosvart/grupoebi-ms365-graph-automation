#!/usr/bin/env python3
"""Hook Stop: guarda el estado de la sesion actual en la capa neutral.

Prioridad de fuentes:
1. Variables de entorno (CLAUDE_COMPLETED_TASKS, CLAUDE_PENDING_TASKS, CLAUDE_NEXT_STEP)
2. Último checkpoint guardado (precompact-*.json o checkpoint-*.json)
3. Sesión anterior del mismo día (fallback)
"""
import json
import os
import subprocess
from datetime import datetime
from pathlib import Path

root = Path(__file__).parent.parent
memory_dir = root / ".agent" / "memory"
checkpoints_dir = memory_dir / "checkpoints"
memory_dir.mkdir(parents=True, exist_ok=True)
checkpoints_dir.mkdir(parents=True, exist_ok=True)

file = memory_dir / "current-session.json"

# Cargar sesion anterior
existing = {}
if file.exists():
    try:
        existing = json.loads(file.read_text(encoding="utf-8"))
    except Exception:
        pass

# 1. Intentar obtener datos de env vars
completed = [t for t in os.environ.get("CLAUDE_COMPLETED_TASKS", "").split("\n") if t.strip()]
pending   = [t for t in os.environ.get("CLAUDE_PENDING_TASKS",   "").split("\n") if t.strip()]
next_step = os.environ.get("CLAUDE_NEXT_STEP", "")

# 2. Si env vars estan vacias, intentar leer ultimo checkpoint
if not completed and not pending and not next_step:
    checkpoints = sorted(
        list(checkpoints_dir.glob("precompact-*.json")) + list(checkpoints_dir.glob("checkpoint-*.json")),
        key=lambda f: f.stat().st_mtime,
        reverse=True
    )
    if checkpoints:
        try:
            checkpoint = json.loads(checkpoints[0].read_text(encoding="utf-8"))
            # Extraer info útil del checkpoint para next_step
            if "git" in checkpoint:
                git_info = checkpoint["git"]
                branch = git_info.get("branch", "unknown")
                next_step = f"Continuar en rama '{branch}'" if branch else ""
        except Exception:
            pass

branch = existing.get("branch", "")
try:
    branch = subprocess.check_output(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        text=True,
        stderr=subprocess.DEVNULL,
    ).strip()
except Exception:
    pass

focus = os.environ.get("CLAUDE_SESSION_FOCUS", "").strip() or existing.get("focus", "")
risks = [r for r in os.environ.get("CLAUDE_SESSION_RISKS", "").split("\n") if r.strip()] or existing.get("risks", [])
files_touched = [
    f for f in os.environ.get("CLAUDE_SESSION_FILES_TOUCHED", "").split("\n") if f.strip()
] or existing.get("files_touched", [])

data = {
    **existing,
    "last_updated": datetime.now().isoformat(),
    "branch": branch,
    "focus": focus,
    "completed": completed or existing.get("completed", []),
    "pending": pending or existing.get("pending", []),
    "next_step": next_step or existing.get("next_step", ""),
    "risks": risks,
    "files_touched": files_touched,
}

file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
