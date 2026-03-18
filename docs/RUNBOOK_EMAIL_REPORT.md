# RUNBOOK: Email Report — Envío de reportes Planner vía correo

## 1. Descripción del sistema

El modo `--mode email-report` genera un reporte HTML de tareas Planner y lo envía directamente al buzón del usuario vía Microsoft Graph API.

**Flujo:**
1. **Parse CSV / Selección interactiva** — usuario elige Plan del grupo
2. **Enriquecimiento de tareas** — obtiene datos desde Graph: asignados, checklists, comentarios (opcional)
3. **Generación HTML** — tabla con Bucket/Título/Asignado/Estado/%/Vence + KPIs arriba
4. **Envío vía Graph** — POST `/users/{upn}/sendMail` con `Content-Type: text/html`
5. **Logging** — imprime estado (✓ enviado o ✗ error) en stdout

---

## 2. Comandos de referencia

### Generar preview local (sin enviar)

```bash
python planner_import.py --mode email-report \
  --group-id d0f1fcf9-08e5-4415-a2f8-2111b569e0ec \
  --preview
```

**Output:**
- `reports/preview_tareas_diarias_pm_-_dm.html` — archivo HTML para revisar
- No se envía correo
- No requiere parámetro `--to`

---

### Enviar correo a destinatario específico

```bash
python planner_import.py --mode email-report \
  --group-id d0f1fcf9-08e5-4415-a2f8-2111b569e0ec \
  --to dmorales@grupoebi.cl
```

**Output:**
- Genera HTML internamente
- Envía vía `/users/dmorales@grupoebi.cl/sendMail`
- Imprime: `✉ correo enviado a dmorales@grupoebi.cl` (si success)

---

### Selección interactiva de Plan

```bash
python planner_import.py --mode email-report --to dmorales@grupoebi.cl
```

**Output:**
- Lista planes disponibles en el grupo (Group ID del .env por defecto)
- Usuario elige número (1, 2, ...) o digita para filtrar
- Envía al Plan seleccionado

---

### Con comentarios en la tabla (slower)

```bash
python planner_import.py --mode email-report \
  --to dmorales@grupoebi.cl \
  --comments
```

**Nota:** Agrega columna "Último comentario" + fetches adicionales (1 llamada Graph por tarea).
- Riesgo: Rate limit 429 si >100 tareas con hilo activo
- Recomendación: úsalo solo si necesitas auditar actividad reciente

---

## 3. Parámetros CLI

| Flag | Tipo | Obligatorio | Ejemplo | Notas |
|------|------|-------------|---------|-------|
| `--mode email-report` | str | ✓ | | Activa este modo |
| `--group-id` | UUID | ✗ | `d0f1fcf9...` | Por defecto: del .env (GROUP_ID) |
| `--to` | email | ✗ | `user@example.com` | Obligatorio si NO `--preview` |
| `--preview` | bool | ✗ | (flag) | Genera HTML sin enviar |
| `--comments` | bool | ✗ | (flag) | Agrega último comentario por tarea |
| `--no-checklist` | bool | ✗ | (flag) | Desactiva obtención de checklist (más rápido con >100 tareas) |

---

## 4. Permisos requeridos en Azure AD

### Scopes necesarios (Application)

| Permiso | Tipo | Requiere | Detalles |
|---------|------|----------|---------|
| `Mail.Send` | **Application** | ✓ | Enviar correo como usuario (NOT Delegated) |
| `User.Read.All` | Application | ✓ | Leer nombres de usuarios asignados |
| `Group.Read.All` | Application | ✓ | Acceder a planes del grupo |
| `PlannerTask.Read.All` | Application | ✓ | Leer tareas Planner |

**Verificar permisos:** https://graphpermissions.merill.net (buscar `Mail.Send`)

---

## 5. Interpretación del log

### Salida típica exitosa

```
[info] Token cacheado desde MCP
[info] Listando planes del grupo d0f1fcf9-08e5-4415-a2f8-2111b569e0ec
[info]   1. Tareas diarias PM - DM (123 tareas)
[info]   2. PMO 2026 (45 tareas)
Selecciona plan (1-2) o digita para filtrar: 1
[info] Plan: Tareas diarias PM - DM
[info] Obteniendo detalles de 123 tareas...
[info]   Buckets OK, Checklist OK, Asignados OK
[info] Generando HTML...
[info] Enviando correo...
✉ correo enviado a dmorales@grupoebi.cl
```

---

### Salida con errores comunes

#### ✗ Error: 403 Forbidden

```
[error] 403 Forbidden POST /users/dmorales@grupoebi.cl/sendMail
        "Authorization_RequestDenied" — permiso insuficiente
```

**Solución:** El token no tiene scope `Mail.Send` en Azure AD. Solicita al admin de IT:
1. Abrir Azure Portal → Roles y administradores
2. Buscar la app de Planner Import
3. Agregar permiso `Mail.Send` (Application, NOT Delegated)
4. Reiniciar la sesión (limpiar token cacheado)

---

#### ✗ Error: 400 Bad Request

```
[error] 400 Bad Request POST /users/dmorales@grupoebi.cl/sendMail
        "InvalidRequest" — cuerpo del correo malformado
```

**Solución:** Revisar que el HTML generado no tenga caracteres especiales sin escape (ej: `<`, `>`, `&`).

---

#### ✗ Error: Line 1 Column 1 (char 0) — FALSO NEGATIVO (RESUELTO)

```
✗ Error de validación ... Expecting value: line 1 column 1 (char 0)
```

**Era causado por:** `POST /users/{upn}/sendMail` retorna **202 Accepted** con body vacío. El código anterior intentaba `resp.json()` sin validar si había contenido.

**Resuelto en:** Commit a677c8e (`if not resp.content: return None`)

---

## 6. Problemas conocidos y hoja de ruta

| Problema | Estado | Workaround | Ticket |
|----------|--------|-----------|--------|
| ✅ **202 body vacío → falso negativo** | ✓ RESUELTO | (ninguno necesario) | [Commit a677c8e](../../../OneDrive%20-%20Cosemar/PM/Automatización_procesos_MsGraph/Planner_Import_script/planner_import.py) |
| ✅ **Títulos truncados sin indicación** | ✓ RESUELTO | (ninguno necesario) | Commit a677c8e (añade `…`) |
| ✅ **% muestra "-" para tareas sin checklist con avance** | ✓ RESUELTO | (ninguno necesario) | Commit a677c8e (muestra percentComplete) |
| ✅ **Asignado truncado en medio de palabra** | ✓ RESUELTO | (ninguno necesario) | Commit a677c8e (trunca por nombre) |
| 🟡 **Rate limit 429 con >100 tareas + --comments** | Mitigado | Ejecutar fuera de horario pico | Backlog |
| 🟡 **Correos largos (>25MB) pueden no enviarse** | Mitigado | Dividir por Plan o rango de fechas | Backlog |

---

## 7. Troubleshooting

### Paso 1: Verificar credenciales

```bash
# ¿El token está cacheado?
ls -la ~/.cache/msal/  # MSAL cache

# ¿El .env del MCP tiene valores?
cat C:\Users\usuario\mcp-servers\fornado-planner-mcp\.env | grep -E "^(TENANT_ID|CLIENT_ID|CLIENT_SECRET)" | wc -l
# Debe mostrar 3
```

---

### Paso 2: Comprobar acceso al grupo

```bash
python planner_import.py --mode list --group-id d0f1fcf9-08e5-4415-a2f8-2111b569e0ec
# ¿Aparecen planes? → OK
# ¿Error 403? → usuario sin acceso al grupo
```

---

### Paso 3: Verificar permisos Mail.Send

```bash
# En Azure Portal (https://portal.azure.com):
# 1. App Registrations → {tu app}
# 2. API Permissions
# 3. Buscar "Mail.Send" → debe estar ✓ granted
```

---

### Paso 4: Revisar HTML generado

```bash
# Generar preview local
python planner_import.py --mode email-report \
  --group-id d0f1fcf9-08e5-4415-a2f8-2111b569e0ec \
  --preview

# Abrir el archivo
open reports/preview_*.html  # macOS
explorer reports/preview_*.html  # Windows
```

Revisar:
- ¿Tabla tiene datos?
- ¿KPIs muestran números sensatos?
- ¿Colores y badges están presentes?

---

### Paso 5: Habilitar modo debug

Editar `planner_import.py` línea 50:

```python
# Antes
logging.basicConfig(level=logging.INFO)

# Después
logging.basicConfig(level=logging.DEBUG)
```

Re-ejecutar:

```bash
python planner_import.py --mode email-report \
  --to dmorales@grupoebi.cl 2>&1 | tee /tmp/debug.log
```

Ver `/tmp/debug.log` para detalles de cada llamada Graph.

---

## 8. Historial de fixes

| Fecha | Commit | Descripción |
|-------|--------|-------------|
| 2026-03-18 | a677c8e | Fix: 202 body vacío, títulos truncados, % en tareas sin checklist, asignado truncado |
| 2026-03-17 | 95d8bb2 | KPI: agregar "Vencen en 7 días", eliminar "Señal por Bucket" |
| 2026-03-16 | a3b1c2d | Añadir `--comments` y `--export` para reportes |
| 2026-02-27 | (histórico) | Primera versión de `--mode email-report` |

---

## 9. Contacto y escalación

- **Soporte técnico:** [Diego Morales](mailto:dmorales@grupoebi.cl) (Project Manager)
- **Errores API:** Verificar scopes en Azure AD → solicitar a IT
- **Problemas de datos:** Revisar `--mode report --comments` para auditar actividad
- **Reportar bugs:** Abrir issue en GitHub con el debug log (`/tmp/debug.log`)
