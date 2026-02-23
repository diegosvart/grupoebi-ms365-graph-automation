#!/usr/bin/env python3
"""Hook PreToolUse (Edit|Write): bloquea escritura en archivos sensibles."""
import json
import os
import re
import sys

BLOCKED = [
    re.compile(r"\.env($|\.)"),
    re.compile(r"client_secret"),
    re.compile(r"\.pem$"),
    re.compile(r"\.key$"),
    re.compile(r"\.pfx$"),
]

# Claude Code pasa el input del tool como JSON en stdin
try:
    tool_input = json.load(sys.stdin)
    file_path = tool_input.get("file_path", "") or tool_input.get("path", "")
except Exception:
    file_path = os.environ.get("CLAUDE_TOOL_INPUT_FILE_PATH", "")

if any(p.search(file_path) for p in BLOCKED):
    print(json.dumps({
        "decision": "block",
        "reason": f"Escritura bloqueada en archivo sensible: {file_path}",
    }))
    sys.exit(0)
