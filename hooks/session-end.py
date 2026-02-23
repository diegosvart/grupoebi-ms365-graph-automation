#!/usr/bin/env python3
"""Hook Stop: guarda el estado de la sesión actual para la próxima."""
import json
import os
from datetime import datetime
from pathlib import Path

sessions_dir = Path(__file__).parent.parent / ".claude" / "sessions"
sessions_dir.mkdir(parents=True, exist_ok=True)

today = datetime.now().strftime("%Y-%m-%d")
file = sessions_dir / f"{today}.json"

existing = {}
if file.exists():
    try:
        existing = json.loads(file.read_text(encoding="utf-8"))
    except Exception:
        pass

completed = [t for t in os.environ.get("CLAUDE_COMPLETED_TASKS", "").split("\n") if t.strip()]
pending   = [t for t in os.environ.get("CLAUDE_PENDING_TASKS",   "").split("\n") if t.strip()]
next_step = os.environ.get("CLAUDE_NEXT_STEP", "")

data = {
    **existing,
    "last_updated": datetime.now().isoformat(),
    "completed":    completed or existing.get("completed", []),
    "pending":      pending   or existing.get("pending",   []),
    "next_step":    next_step or existing.get("next_step", ""),
}

file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
