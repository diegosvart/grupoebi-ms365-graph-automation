#!/usr/bin/env python3
"""Hook SessionStart: muestra contexto neutral de la ultima sesion y resumen Planner."""
import asyncio
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

import httpx


async def _planner_summary() -> None:
    """Fetch y muestra resumen ligero de planes activos en Planner.
    Timeout corto (10s) para no bloquear SessionStart.
    Token nunca en logs.
    """
    try:
        # Cargar MCP si existe
        mcp_path = Path(os.environ.get("MCP_PATH", Path.home() / "mcp-servers" / "fornado-planner-mcp"))
        if not mcp_path.is_dir():
            return

        sys.path.insert(0, str(mcp_path))
        from dotenv import load_dotenv
        from src.auth.microsoft import MicrosoftAuthManager
        from src.config import Settings

        load_dotenv(mcp_path / ".env")

        settings = Settings()
        auth = MicrosoftAuthManager(
            tenant_id=settings.azure_tenant_id,
            client_id=settings.azure_client_id,
            client_secret=settings.azure_client_secret,
        )
        token = auth.get_token()
        group_id = os.environ.get("PLANNER_GROUP_ID", "198b4a0a-39c7-4521-a546-6a008e3a254a")

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"https://graph.microsoft.com/v1.0/groups/{group_id}/planner/plans",
                headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
            )
            resp.raise_for_status()
            plans = resp.json().get("value", [])

        if not plans:
            return

        print(f"\n--- Planner: {len(plans)} planes activos ---")
        for p in plans[:5]:
            created = p.get("createdDateTime", "")[:10]
            print(f"  {p['title']:<40}  (creado {created})")
        if len(plans) > 5:
            print(f"  ... y {len(plans) - 5} más")
        print()
    except Exception:
        # Fallback silencioso — no bloquear carga de Claude Code
        pass


# Mostrar sesion anterior desde la capa canonica; fallback a la ubicacion legacy
root = Path(__file__).parent.parent
memory_dir = root / ".agent" / "memory"
sessions_dir = memory_dir / "checkpoints"
current_session = memory_dir / "current-session.json"
legacy_sessions_dir = root / ".claude" / "sessions"

if current_session.exists():
    try:
        data = json.loads(current_session.read_text(encoding="utf-8"))
        print("\n--- Sesion actual compartida ---")
        if data.get("branch"):
            print(f"Branch     : {data['branch']}")
        if data.get("focus"):
            print(f"Foco       : {data['focus']}")
        if data.get("completed"):
            print(f"Completado : {', '.join(data['completed'])}")
        if data.get("pending"):
            print(f"Pendiente  : {', '.join(data['pending'])}")
        if data.get("next_step"):
            print(f"Proximo    : {data['next_step']}")
        print("")
    except Exception:
        pass
elif sessions_dir.exists():
    cutoff = datetime.now() - timedelta(days=7)
    sessions = sorted(
        [f for f in sessions_dir.glob("*.json") if datetime.fromtimestamp(f.stat().st_mtime) > cutoff],
        key=lambda f: f.stat().st_mtime,
        reverse=True,
    )

    if sessions:
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
            pass
elif legacy_sessions_dir.exists():
    cutoff = datetime.now() - timedelta(days=7)
    sessions = sorted(
        [f for f in legacy_sessions_dir.glob("*.json") if datetime.fromtimestamp(f.stat().st_mtime) > cutoff],
        key=lambda f: f.stat().st_mtime,
        reverse=True,
    )

    if sessions:
        try:
            data = json.loads(sessions[0].read_text(encoding="utf-8"))
            print("\n--- Sesion anterior (legacy) ---")
            if data.get("completed"):
                print(f"Completado : {', '.join(data['completed'])}")
            if data.get("pending"):
                print(f"Pendiente  : {', '.join(data['pending'])}")
            if data.get("next_step"):
                print(f"Proximo    : {data['next_step']}")
            print("")
        except Exception:
            pass

# Mostrar resumen Planner
try:
    asyncio.run(_planner_summary())
except Exception:
    pass
