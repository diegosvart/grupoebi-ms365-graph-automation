---
description: Guardar el estado actual de la sesión para continuar en la próxima sin perder contexto.
allowed-tools: Write, Bash
---

Guardar checkpoint de la sesión actual:

1. Leer `.agent/memory/current-session.json` si existe para mantener continuidad
2. Identificar el foco actual de la sesión y resumir:
   - qué se completó
   - qué falta
   - cuál es el próximo paso
   - riesgos o bloqueos relevantes
3. Guardar en `.agent/memory/checkpoints/checkpoint-[fecha].json`:
   ```json
   {
     "last_updated": "[ISO timestamp]",
     "branch": "[rama actual]",
     "focus": "[foco de la sesión]",
     "completed": ["lista de lo que se completó esta sesión"],
     "pending": ["lista de lo que queda pendiente"],
     "next_step": "descripción concreta del próximo paso",
     "risks": ["riesgos o advertencias"],
     "files_touched": ["archivos relevantes tocados en la sesión"]
   }
   ```
4. Actualizar `.agent/memory/current-session.json` con el mismo formato si quedó desactualizado.

Confirmar: "Checkpoint guardado en la capa compartida `.agent/`."
