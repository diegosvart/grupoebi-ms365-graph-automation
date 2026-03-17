# Configuración de Mail.Send para email-report

## Problema actual
El endpoint `POST /me/sendMail` retorna error 400 porque falta el permiso `Mail.Send` en la aplicación Azure AD.

---

## Permiso requerido

| Permiso | Descripción | Scope | Tipo |
|---------|-------------|-------|------|
| `Mail.Send` | Enviar correos en nombre del usuario autenticado | `https://graph.microsoft.com/Mail.Send` | Delegado |

**Permiso gráfico en Azure AD:** `Microsoft Graph` → `Mail` → `Mail.Send`

---

## Cómo habilitarlo (para mañana)

### En Azure Portal

1. Ve a **Azure Portal** → **Azure Active Directory** → **App registrations**
2. Busca la app: `fornado-planner-mcp` (o similar)
3. En el menu izquierdo: **API permissions**
4. Click en **+ Add a permission**
5. Selecciona **Microsoft Graph**
6. Elige **Delegated permissions**
7. Busca y selecciona: **Mail** → **Mail.Send**
8. Click en **Add permissions**
9. **IMPORTANTE:** Click en **Grant admin consent for [Tenant]** (requiere permisos de admin)

### Via PowerShell (alternativa)

```powershell
# Requiere módulo: Install-Module -Name Microsoft.Graph.Authentication

$tenantId = "tu-tenant-id"
$appId = "tu-app-id"

Connect-MgGraph -TenantId $tenantId -Scopes "AppRoleAssignment.ReadWrite.All"

$sp = Get-MgServicePrincipal -Filter "appId eq '$appId'"
$graphSp = Get-MgServicePrincipal -Filter "appId eq '00000003-0000-0000-c000-000000000000'"

$role = $graphSp.AppRoles | Where-Object { $_.Value -eq "Mail.Send" }

New-MgServicePrincipalAppRoleAssignment -ServicePrincipalId $sp.Id `
  -PrincipalId $sp.Id `
  -AppRoleId $role.Id `
  -ResourceId $graphSp.Id
```

---

## Verificación

Una vez habilitado, ejecuta:

```bash
echo "1" | python planner_import.py --mode email-report \
  --group-id 198b4a0a-39c7-4521-a546-6a008e3a254a \
  --to dmorales@grupoebi.cl
```

Deberías recibir el email en tu Outlook.

---

## Alternativas de visualización (SIN necesidad de Mail.Send)

### Opción 1: Preview HTML en navegador (RECOMENDADO HOY)
```bash
echo "1" | python planner_import.py --mode email-report \
  --group-id 198b4a0a-39c7-4521-a546-6a008e3a254a \
  --preview
```
✅ Abre el HTML en navegador instantáneamente
✅ No requiere permisos de Mail.Send
✅ Permite guardar como PDF desde el navegador

### Opción 2: Exportar a CSV y abrir en Excel
```bash
echo "1" | python planner_import.py --mode report \
  --group-id 198b4a0a-39c7-4521-a546-6a008e3a254a \
  --export reportes/tareas_diarias.csv
```
✅ Genera CSV con 14 columnas (PlanID, BucketName, TaskTitle, Estado, %, Vence, etc.)
✅ Abre en Excel para análisis

### Opción 3: Ver en terminal (sin gráficos)
```bash
echo "1" | python planner_import.py --mode report \
  --group-id 198b4a0a-39c7-4521-a546-6a008e3a254a
```
✅ Tabla en terminal con todas las tareas
✅ KPIs y señales por bucket
✅ Vencidas resaltadas

---

## Flujo de trabajo recomendado

**HOY (16-03-2026):**
```bash
# Visualizar reporte
echo "1" | python planner_import.py --mode email-report \
  --group-id 198b4a0a-39c7-4521-a546-6a008e3a254a \
  --preview
```

**MAÑANA (después de habilitar Mail.Send):**
```bash
# Enviar a un email específico (prueba)
echo "1" | python planner_import.py --mode email-report \
  --group-id 198b4a0a-39c7-4521-a546-6a008e3a254a \
  --to dmorales@grupoebi.cl

# Enviar a todos los asignados (producción)
echo "1" | python planner_import.py --mode email-report \
  --group-id 198b4a0a-39c7-4521-a546-6a008e3a254a
```

---

## Contexto técnico

- **Endpoint:** `POST /me/sendMail`
- **Scope mínimo:** `Mail.Send` (delegado)
- **Token:** Se obtiene automáticamente de `fornado-planner-mcp/.env`
- **Timeout:** 30 segundos (configurable)
- **Rate limit:** 4 MB payload, máx 500 destinatarios por correo

---

## Archivos generados

Cuando uses `--preview`, los HTMLs se guardan en:
```
reports/preview_<plan_name_slug>.html
```

Ejemplo: `reports/preview_pmo_2026.html`

Para abrir en Outlook directamente (después de habilitado Mail.Send), usa:
```bash
echo "1" | python planner_import.py --mode email-report \
  --group-id <guid> \
  --to dmorales@grupoebi.cl
```

---

## Contacto / Soporte

Si el error persiste después de habilitar el permiso:
1. Espera 5-10 minutos para que se propague el cambio
2. Cierra todas las sesiones de PowerShell/terminal
3. Abre una nueva terminal y reintenta
4. Si aún falla, verifica que **Grant admin consent** haya sido ejecutado
