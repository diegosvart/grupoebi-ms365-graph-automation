# Validación Crítica de Datos — Reportes HTML/Email

## Regla Principal

**En revisiones de reportes HTML, CSV exportados, o cualquier salida con datos:**
1. **NO confundir** validación de estructura (HTML válido, CSS correcto, layout) con validación de datos (campos presentes, valores no vacíos, sensatos)
2. **SIEMPRE verificar de primera fuente:**
   - Abrir/leer el archivo generado (HTML, CSV, PDF)
   - Inspeccionar DATOS reales, no solo estructura
   - Identificar patrones anómalos (campos en "0" global, "-" sistemático, vacíos)
   - Investigar la causa antes de reportar "completado"

## Checklist de Validación (siempre aplicar)

| Aspecto | Qué revisar | Cómo detectar problema |
|---------|-----------|----------------------|
| **Estructura HTML** | Tablas, divs, clases CSS están presentes y anidados correctamente | Validador HTML o lectura manual del árbol DOM |
| **Estilos CSS** | Colores, anchos, borders, padding aplicados correctamente | Inspeccionar elemento en navegador o leer inline styles |
| **Completitud de datos** | Todos los campos esperados están presentes en la salida | Campo "Comentarios" ≠ 0 para todos, "Modificado" ≠ "-" para mayoría |
| **Sensatez de datos** | Valores reales, no defaults/placeholders globales | ¿Hay tareas con lastModifiedDateTime real? ¿Alguna tarea tiene commentCount > 0? |
| **Redondez de investigación** | Si encuentras anomalía, investigar causa antes de cerrar | No cerrar "Fixed: commentCount" si sigue siendo 0 para todas las tareas |

## Qué hace la diferencia

❌ **MALO (pasado):**
> "Revisé el HTML generado. La estructura de la tabla 50/50 es correcta, badges tienen los colores, footer muestra autoría. Todos los requerimientos implementados correctamente."
>
> **Problema:** No noté que campos críticos ("Comentarios", "Modificado") estaban vacíos/nulos.

✅ **BIEN (futuro):**
> "Revisé el HTML generado. Estructura 50/50 ✓, badges ✓, footer ✓.
> **Datos:** 18 tareas listadas, pero detecté anomalías:
> - Comentarios: 0 para todas las 18 tareas (problema pre-existente de `commentCount`, registrado en tarea pendiente)
> - Modificado: "-" para 16 de 18 tareas (investigar si `lastModifiedDateTime` se obtiene correctamente de API)
>
> Estructura lista, pero datos incompletos. Recomiendo investigación de campos vacíos antes de marcar como Release Ready."

## Regla de Oro

**Si revisar un reporte y encuentras valores anómalos (0 global, "-" sistemático, campos vacíos), INVESTIGAR antes de reportar completado.** No es suficiente que el código esté "bien escrito" — necesita generar DATOS completos y sensatos.

## Aplicación a este proyecto

- **Reportes HTML (`--mode email-report`, `--preview`)**: Validar datos de tareas (estado, fechas, comentarios, etc.)
- **Exportación CSV (`--export`)**: Verificar que todas las 14 columnas tienen valores sensatos
- **Reportes de texto (`--mode report`)**: Confirmar que tablas tienen datos reales, no placeholders
- **Gráficos/donut charts**: Números que suman correctamente a total, no inconsistencias

## Integración con workflow

1. Implementar fix de código
2. Generar preview/reporte
3. **Validar datos** (no solo estructura)
4. Si hay anomalías → investigar causa
5. Recién entonces reportar "completado"
