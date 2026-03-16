#!/usr/bin/env python
"""Encuentra el group-id de un plan en Microsoft Planner dado su planId.

Uso:
  python scripts/find_plan_group.py U_9Ox1FJ10misOuS7zgrJmUADhvP

Resultado: Imprime el group-id que puedes usar con planner_import.py --mode report --group-id <id>
"""
import asyncio
import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

# Cargar .env del MCP
mcp_path = Path(os.environ.get("MCP_PATH", Path.home() / "mcp-servers" / "fornado-planner-mcp"))
env_file = mcp_path / ".env"
load_dotenv(env_file)

# Agregar parent dir al path para importar planner_import
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.auth.microsoft import MicrosoftAuthManager
from src.config import Settings


async def find_plan_group(plan_id: str) -> str:
    """Obtiene el group-id propietario de un plan en Planner.

    Args:
        plan_id: ID del plan (ej: U_9Ox1FJ10misOuS7zgrJmUADhvP)

    Returns:
        Group ID (UUID) propietario del plan

    Raises:
        Exception: Si la API devuelve error
    """
    settings = Settings()
    auth = MicrosoftAuthManager(
        tenant_id=settings.azure_tenant_id,
        client_id=settings.azure_client_id,
        client_secret=settings.azure_client_secret,
    )
    token = auth.get_token()

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            f"https://graph.microsoft.com/v1.0/planner/plans/{plan_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        response.raise_for_status()
        data = response.json()
        group_id = data.get("owner")
        if not group_id:
            raise ValueError(f"Plan {plan_id} no tiene propietario (owner) definido")
        return group_id


async def main():
    if len(sys.argv) < 2:
        print("Uso: python scripts/find_plan_group.py <plan-id>")
        print("\nEjemplo:")
        print("  python scripts/find_plan_group.py U_9Ox1FJ10misOuS7zgrJmUADhvP")
        sys.exit(1)

    plan_id = sys.argv[1]
    print(f"[*] Buscando group-id del plan: {plan_id}...")

    try:
        group_id = await find_plan_group(plan_id)
        print(f"[+] Group ID encontrado: {group_id}")
        print(f"\nUsa este comando para ver el reporte:")
        print(f"  python planner_import.py --mode report --group-id {group_id}")
    except Exception as e:
        print(f"[-] Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
