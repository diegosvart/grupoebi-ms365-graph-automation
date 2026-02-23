---
description: Guardar el estado actual de la sesión para continuar en la próxima sin perder contexto.
allowed-tools: Write, Bash
---

Guardar checkpoint de la sesión actual:

1. Identificar el archivo CSV activo (revisar CSV_PATH en planner_import.py)
2. Resumir en 3 líneas: qué se completó, qué falta, cuál es el próximo paso
3. Guardar en `.claude/sessions/checkpoint-[fecha].json`:
   ```json
   {
     "last_updated": "[ISO timestamp]",
     "completed": ["lista de lo que se completó esta sesión"],
     "pending": ["lista de lo que queda pendiente"],
     "next_step": "descripción concreta del próximo paso"
   }
   ```

Confirmar: "Checkpoint guardado. La proxima sesion empezara con este contexto."
