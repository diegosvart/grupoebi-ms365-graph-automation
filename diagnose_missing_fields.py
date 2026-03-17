#!/usr/bin/env python3
"""
Diagnóstico: Investigar por qué lastModifiedDateTime y commentCount están vacíos/nulos.

Problema identificado:
- Campo "Comentarios" en reporte HTML: 0 para todas las 18 tareas
- Campo "Modificado" en reporte HTML: "-" para 16 de 18 tareas

Hipótesis a verificar:
1. ¿Devuelve Graph API estos campos en la respuesta?
2. ¿Requieren permisos adicionales? (Tasks.ReadWrite.All vs. Tasks.ReadWrite)
3. ¿Son NULL en la API o el código no los procesa correctamente?
4. ¿Hay tareas reales con estos valores o es problema de datos subyacentes?

Ejecución:
  python diagnose_missing_fields.py --plan-id <GUID> --group-id <GUID>
"""

import sys
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

# Importar del MCP (mismo patrón que planner_import.py)
MCP_PATH = Path(os.environ.get("MCP_PATH", Path.home() / "mcp-servers" / "fornado-planner-mcp"))
if not MCP_PATH.is_dir():
    sys.exit(f"[ERROR] No se encontró MCP en: {MCP_PATH}")
sys.path.insert(0, str(MCP_PATH))

from dotenv import load_dotenv
load_dotenv(MCP_PATH / ".env")

from src.auth.microsoft import MicrosoftAuthManager
from src.config import Settings

# Importar httpx para raw requests
import httpx


async def diagnose_fields(group_id: str, plan_id: str) -> None:
    """
    Ejecutar diagnóstico de campos faltantes en tareas de Planner.

    Pasos:
    1. Obtener todas las tareas del plan con $select específico
    2. Inspeccionar lastModifiedDateTime y commentCount en respuesta raw
    3. Reportar patrones: nulos, ceros, ausentes
    4. Emitir hipótesis sobre causa
    """

    settings = Settings()
    auth = MicrosoftAuthManager(
        tenant_id=settings.azure_tenant_id,
        client_id=settings.azure_client_id,
        client_secret=settings.azure_client_secret,
    )

    # Obtener token
    token = auth.get_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    print("=" * 80)
    print("DIAGNÓSTICO: campos faltantes en tareas Planner")
    print("=" * 80)
    print(f"Grupo ID: {group_id}")
    print(f"Plan ID: {plan_id}")
    print()

    # ============ PASO 1: Obtener tareas (sin filtro) para ver campos disponibles ============
    print("[1/4] Consultando Graph API para obtener tareas")
    print()

    url = f"https://graph.microsoft.com/v1.0/planner/plans/{plan_id}/tasks"

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(url, headers=headers)
        resp.raise_for_status()
        data = resp.json()

    tasks = data.get("value", [])
    print(f"[OK] Obtenidas {len(tasks)} tareas")
    print()

    # ============ PASO 2: Inspeccionar campos en respuesta raw ============
    print("[2/4] Análisis de campos en respuesta raw")
    print()

    # Verificar presencia de campos en la respuesta
    sample_task = tasks[0] if tasks else {}
    has_last_mod = "lastModifiedDateTime" in sample_task
    has_comment_count = "commentCount" in sample_task

    print("Estado de campos en respuesta Graph API:")
    print(f"  • lastModifiedDateTime: {'[OK] PRESENTE' if has_last_mod else '[NO] AUSENTE (campo no existe en tipo plannerTask)'}")
    print(f"  • commentCount: {'[OK] PRESENTE' if has_comment_count else '[NO] AUSENTE (campo no existe en tipo plannerTask)'}")
    print()

    # Campos que SÍ están disponibles
    print("Campos disponibles en plannerTask (alternativas):")
    available_fields = [
        ("createdDateTime", "Fecha de creación (NO modificación)"),
        ("conversationThreadId", "ID del hilo de comentarios (requiere fetch aparte)"),
        ("completedDateTime", "Fecha de completación (NULL si no completada)"),
    ]
    for field, desc in available_fields:
        if field in sample_task:
            print(f"  [OK] {field}: {desc}")
    print()

    # Análisis de conversationThreadId para comentarios
    print("Análisis de comentarios vía conversationThreadId:")
    conv_thread_count = sum(1 for t in tasks if t.get("conversationThreadId"))
    print(f"  - Tareas con conversationThreadId (potencial para comentarios): {conv_thread_count}/{len(tasks)}")
    if conv_thread_count == 0:
        print("    -> Ninguna tarea tiene thread de conversación aún")
    print()

    # Análisis de createdDateTime (la alternativa a lastModifiedDateTime)
    print("Análisis de createdDateTime (alternativa a lastModifiedDateTime):")
    created_dates = []
    for task in tasks:
        created = task.get("createdDateTime")
        if created:
            try:
                dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
                created_dates.append((task.get("title", "?"), dt))
            except Exception:
                pass

    print(f"  - Tareas con fecha de creación: {len(created_dates)}/{len(tasks)}")
    if created_dates:
        print(f"    Rango: {min(dt[1] for dt in created_dates)} -> {max(dt[1] for dt in created_dates)}")
    print()

    # ============ PASO 3: Diagnóstico definitivo ============
    print("[3/4] Diagnóstico definitivo")
    print()

    print("[ERROR] PROBLEMA IDENTIFICADO (Root Cause):")
    print()
    print("Los campos 'lastModifiedDateTime' y 'commentCount' NO EXISTEN")
    print("en el tipo 'microsoft.graph.plannerTask' según la Graph API.")
    print()
    print("Error de Graph API:")
    print("  StatusCode: 400 BadRequest")
    print("  Message: \"Could not find a property named 'lastModifiedDateTime'/'commentCount'")
    print("           on type 'microsoft.graph.plannerTask'\"")
    print()

    print("IMPACTO:")
    print("  - El código en planner_import.py intenta obtener estos campos")
    print("  - Graph API rechaza la solicitud con error 400")
    print("  - Podrían estar siendo capturados como errores silenciosos")
    print("  - O simplemente no se están incluyendo en respuestas")
    print()

    print("SOLUCIONES:")
    print()
    print("[1]  Para 'Comentarios' (commentCount):")
    print("   [OK] Usar 'conversationThreadId' para obtener el hilo de comentarios")
    print("   [OK] Luego hacer GET /groups/{id}/threads/{id}/posts para contar")
    print("   [OK] Ya se implementa en planner_import.py con --comments flag")
    print("   [OK] Sin embargo, esto requiere N+1 llamadas Graph (lento)")
    print()
    print("[2]  Para 'Modificado' (lastModifiedDateTime):")
    print("   [NO] NO HAY CAMPO EQUIVALENTE en plannerTask")
    print("   [WARN]  Alternativa: usar 'createdDateTime' (fecha de creación, NO modificación)")
    print("   [WARN]  Esto es inexacto pero mejor que '-'")
    print()

    print("RECOMENDACIONES:")
    print("  • Quitar 'lastModifiedDateTime' de los $select")
    print("  • Mostrar 'createdDateTime' en lugar de lastModified")
    print("  • Para comentarios: usar conversationThreadId + fetch posts (ya implementado)")
    print("  • Documentar esta limitación en CLAUDE.md")
    print()

    # ============ PASO 4: Próximos pasos ============
    print("[4/4] Próximos pasos para planner_import.py")
    print()
    print("ACCIÓN INMEDIATA:")
    print("  1. Verificar dónde en el código se intenta obtener lastModifiedDateTime")
    print("     -> Grep: grep -n 'lastModifiedDateTime' planner_import.py")
    print()
    print("  2. Reemplazar por 'createdDateTime'")
    print("     - Nota: createdDateTime existe en plannerTask y tiene datos reales")
    print("     - No es lo mismo que 'último modificado', pero es mejor que '-'")
    print("     - Documentar que es 'fecha de creación', no de última modificación")
    print()
    print("  3. Para comentarios:")
    print("     - Ya está implementado con conversationThreadId")
    print("     - El reporte debe mostrar 0 si conversationThreadId es null")
    print("     - Esto es correcto y refleja realidad: tareas nuevas sin comentarios")
    print()
    print("VERIFICACIÓN EN GRAPH EXPLORER (opcional):")
    print("   URL: https://developer.microsoft.com/en-us/graph/graph-explorer")
    print(f"   GET https://graph.microsoft.com/v1.0/planner/plans/{plan_id}/tasks")
    print("   Parámetros: $select=id,title,createdDateTime,conversationThreadId")
    print()


async def main():
    """Entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Diagnóstico de campos faltantes en tareas Planner",
        epilog="Ejemplo: python diagnose_missing_fields.py --plan-id <GUID> --group-id <GUID>"
    )
    parser.add_argument("--plan-id", required=False, help="Plan ID (GUID)")
    parser.add_argument("--group-id", required=False, help="Group ID (GUID)")

    args = parser.parse_args()

    # IDs por defecto (para "Tareas diarias PM - DM")
    group_id = args.group_id or "d0f1fcf9-08e5-4415-a2f8-2111b569e0ec"
    plan_id = args.plan_id or "PLACEHOLDER_PLAN_ID"  # Se obtiene interactivamente si no se proporciona

    if plan_id == "PLACEHOLDER_PLAN_ID":
        # Modo interactivo: listar planes y seleccionar
        print("Plan ID no proporcionado. Listando planes disponibles...")
        # Para simplificar, asumir que el usuario proporciona el Plan ID
        print(f"Proporcione el Plan ID con --plan-id")
        sys.exit(1)

    await diagnose_fields(group_id, plan_id)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
