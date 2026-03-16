#!/usr/bin/env python3
"""Hook SessionStart: muestra contexto de sesión anterior y resumen Planner."""
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


# Mostrar sesión anterior
sessions_dir = Path(__file__).parent.parent / ".claude" / "sessions"
if sessions_dir.exists():
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

# Mostrar resumen Planner
try:
    asyncio.run(_planner_summary())
except Exception:
    pass
