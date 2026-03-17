# Preview — Reporte HTML de PMO 2026 (16-03-2026)

## Resumen visual

El reporte HTML generado contiene:

### 1. Encabezado
```
PMO 2026
Reporte de gestión — 16-03-2026
```

### 2. Tabla de Tareas por Bucket (21 tareas totales)

| Estado | Color | Ejemplo |
|--------|-------|---------|
| **Completadas** | Verde (#d4edda) | Validar integridad de datos |
| **En Progreso** | Gris (#f8f9fa) | Medir adopción inicial |
| **Vencidas** | Amarillo (#fff3cd) | Todas las tareas sin completar vencidas |

**Columnas mostradas:**
- Bucket (Fase del proyecto)
- Título de tarea
- Asignado (GUID del usuario)
- Estado (inProgress, notStarted, completed)
- % de completitud
- Fecha de vencimiento

### 3. KPIs — Resumen del Plan

```
Total: 21 tareas
✅ Completadas: 6 (29%)
🔄 En progreso: 2 (10%)
⏸ Sin iniciar: 13 (62%)
⚠ Vencidas (no completadas): 12
```

### 4. Señal por Bucket

| Bucket | Señal | Estado |
|--------|-------|--------|
| FASE 7 - Adopción | ⚠ | En progreso, pero vencidas |
| FASE 6 - Power BI | ⛔ | Bloqueada (todas vencidas, sin iniciar) |
| FASE 5 - Automatización | ⛔ | Bloqueada |
| FASE 4 - Gobernanza | ⛔ | Bloqueada |
| FASE 3 - Carga Masiva | ⛔ | Completada al 67%, pero con vencidas |
| FASE 2 - Diseño Planner | ⛔ | Bloqueada |
| FASE 1 - Normalización | ✅ | 100% Completada |

---

## Archivo generado

```
reports/preview_pmo_2026.html
```

Puedes:
- ✅ Abrirlo en cualquier navegador
- ✅ Guardarlo como PDF (Ctrl+S en Firefox/Chrome → Guardar como PDF)
- ✅ Enviarlo manualmente vía Outlook
- ✅ Compartirlo por Teams/WhatsApp/Email

---

## Cómo generar el preview

```bash
# En la terminal, desde el directorio del script:
cd "C:\Users\dmorales\OneDrive - Cosemar\PM\Automatización_procesos_MsGraph\Planner_Import_script"

# Ejecutar el comando (se abrirá el navegador automáticamente):
echo "1" | python planner_import.py --mode email-report \
  --group-id 198b4a0a-39c7-4521-a546-6a008e3a254a \
  --preview

# Para otros planes, cambia el número:
echo "2" | python planner_import.py --mode email-report \
  --group-id 198b4a0a-39c7-4521-a546-6a008e3a254a \
  --preview
```

---

## Observaciones del reporte actual (PMO 2026)

🔴 **Criticidades detectadas:**
1. **12 tareas vencidas** sin completar (⚠️ URGENTE)
2. **6 buckets bloqueados** con tareas sin iniciar
3. Solo **1 bucket completado** (FASE 1 - Normalización)

🟢 **Avances:**
- 29% de tareas completadas
- 10% en progreso activo
- FASE 1 - Normalización al 100%

📅 **Próximos vencimientos:**
- FASE 6 & 5: 2026-03-05 (VENCIDAS)
- FASE 7: 2026-03-18 (próximas 2 días)

---

## Alternativas sin Mail.Send

Si deseas **visualizar sin enviar email**:

### Opción A: Ver en terminal (con colores y tablas)
```bash
echo "1" | python planner_import.py --mode report \
  --group-id 198b4a0a-39c7-4521-a546-6a008e3a254a
```

### Opción B: Exportar a CSV y abrir en Excel
```bash
echo "1" | python planner_import.py --mode report \
  --group-id 198b4a0a-39c7-4521-a546-6a008e3a254a \
  --export mis_reportes.csv
```

### Opción C: Ver HTML en navegador (actual)
```bash
echo "1" | python planner_import.py --mode email-report \
  --group-id 198b4a0a-39c7-4521-a546-6a008e3a254a \
  --preview
```
✅ **RECOMENDADO** — Lo que ves es exactamente lo que recibirías por email

---

## Próximos pasos

1. ✅ **HOY**: Ver el preview HTML (sin cambios en Azure AD)
2. 📋 **MAÑANA**: Habilitar `Mail.Send` en Azure AD (ver MAIL_SEND_SETUP.md)
3. 📧 **MAÑANA**: Enviar reporte via `--to dmorales@grupoebi.cl` (prueba)
4. 📨 **PRODUCCIÓN**: Enviar a todos los asignados (sin `--to`)

