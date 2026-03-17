#!/usr/bin/env python3
"""Hook Stop: guarda el estado de la sesión actual para la próxima.

Prioridad de fuentes:
1. Variables de entorno (CLAUDE_COMPLETED_TASKS, CLAUDE_PENDING_TASKS, CLAUDE_NEXT_STEP)
2. Último checkpoint guardado (precompact-*.json o checkpoint-*.json)
3. Sesión anterior del mismo día (fallback)
"""
import json
import os
from datetime import datetime
from pathlib import Path

sessions_dir = Path(__file__).parent.parent / ".claude" / "sessions"
sessions_dir.mkdir(parents=True, exist_ok=True)

today = datetime.now().strftime("%Y-%m-%d")
file = sessions_dir / f"{today}.json"

# Cargar sesión anterior del mismo día
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

# 2. Si env vars están vacías, intentar leer último checkpoint
if not completed and not pending and not next_step:
    checkpoints = sorted(
        list(sessions_dir.glob("precompact-*.json")) + list(sessions_dir.glob("checkpoint-*.json")),
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

data = {
    **existing,
    "last_updated": datetime.now().isoformat(),
    "completed":    completed or existing.get("completed", []),
    "pending":      pending   or existing.get("pending",   []),
    "next_step":    next_step or existing.get("next_step", ""),
}

file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
