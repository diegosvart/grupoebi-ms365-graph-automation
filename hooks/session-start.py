#!/usr/bin/env python3
"""Hook SessionStart: muestra contexto de la sesión anterior si existe."""
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

sessions_dir = Path(__file__).parent.parent / ".claude" / "sessions"
if not sessions_dir.exists():
    sys.exit(0)

cutoff = datetime.now() - timedelta(days=7)
sessions = sorted(
    [f for f in sessions_dir.glob("*.json") if datetime.fromtimestamp(f.stat().st_mtime) > cutoff],
    key=lambda f: f.stat().st_mtime,
    reverse=True,
)

if not sessions:
    sys.exit(0)

try:
    data = json.loads(sessions[0].read_text(encoding="utf-8"))
    print("\n--- Sesion anterior ---")
    if data.get("completed"):
        print(f"Completado : {', '.join(data['completed'])}")
    if data.get("pending"):
        print(f"Pendiente  : {', '.join(data['pending'])}")
    if data.get("next_step"):
        print(f"Proximo    : {data['next_step']}")
    print("")
except Exception:
    sys.exit(0)
