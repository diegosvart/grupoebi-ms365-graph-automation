#!/usr/bin/env python3
"""Hook PreCompact: captura estado de sesion antes de auto-compact para recuperabilidad."""
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

memory_dir = Path(__file__).parent.parent / ".agent" / "memory"
sessions_dir = memory_dir / "checkpoints"
sessions_dir.mkdir(parents=True, exist_ok=True)

timestamp = datetime.now().isoformat()
precompact_file = sessions_dir / f"precompact-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"

state = {
    "timestamp": timestamp,
    "git": {},
    "planner": {},
    "session": {}
}

# Capturar estado de git
try:
    branch = subprocess.check_output(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        text=True,
        stderr=subprocess.DEVNULL
    ).strip()
    state["git"]["branch"] = branch
except Exception:
    pass

try:
    status = subprocess.check_output(
        ["git", "status", "--porcelain"],
        text=True,
        stderr=subprocess.DEVNULL
    ).strip()
    state["git"]["status"] = status if status else "clean"
except Exception:
    pass

try:
    sha = subprocess.check_output(
        ["git", "rev-parse", "HEAD"],
        text=True,
        stderr=subprocess.DEVNULL
    ).strip()
    state["git"]["sha"] = sha
except Exception:
    pass

# Capturar variables de entorno relacionadas con Planner
for var in ["CLAUDE_COMPLETED_TASKS", "CLAUDE_PENDING_TASKS", "PLANNER_PLAN_ID", "PLANNER_NEXT_STEP"]:
    if var in os.environ:
        state["planner"][var] = os.environ[var]

current_session_file = memory_dir / "current-session.json"
if current_session_file.exists():
    try:
        state["session"] = json.loads(current_session_file.read_text(encoding="utf-8"))
    except Exception:
        pass

# Guardar checkpoint
try:
    precompact_file.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[PreCompact] Checkpoint guardado: {precompact_file.name}")
except Exception as e:
    print(f"[PreCompact] Error al guardar checkpoint: {e}", file=sys.stderr)
    sys.exit(1)
