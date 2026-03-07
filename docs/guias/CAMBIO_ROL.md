# Guia: Cambio de Rol de Usuario

## Que hace este flujo

Actualiza el perfil M365 de un colaborador cuando cambia de cargo o area:

1. Actualiza `jobTitle`, `department` y `manager` en Entra ID
2. Elimina al usuario de los grupos de seguridad del perfil anterior
3. Agrega al usuario a los grupos de seguridad del nuevo perfil
4. Ajusta la licencia M365 si el nuevo perfil requiere una diferente
5. Agrega al usuario a los canales de Teams del nuevo perfil
6. Actualiza Talana con el nuevo cargo y departamento

---

## Autorizacion requerida

| Quien autoriza |
|---|
| Manager del area anterior + Manager del area nueva |

Ambas autorizaciones deben estar registradas antes de ejecutar el flujo. Este requisito existe porque el cambio de rol afecta los accesos a dos areas distintas.

---

## Informacion necesaria

| Campo | Descripcion | Ejemplo |
|---|---|---|
| `email_usuario` | Email M365 del colaborador | jperez@empresa.com |
| `cargo_nuevo` | Nuevo cargo oficial | Ejecutivo Finanzas |
| `area_nueva` | Nueva area o departamento | Finanzas |
| `manager_nuevo_email` | Email del nuevo jefatura directa | gfinanzas@empresa.com |
| `ticket_manager_anterior` | Referencia autorizacion manager saliente | TICKET-2026-0301 |
| `ticket_manager_nuevo` | Referencia autorizacion manager entrante | TICKET-2026-0302 |

---

## Paso a paso

### Paso 1 — Verificar estado actual del usuario

```bash
python create_environment.py \
  --mode check-user \
  --email jperez@empresa.com
```

Anotar: perfil actual, grupos actuales, licencia actual.

### Paso 2 — Simular cambio de rol (dry-run obligatorio)

```bash
python create_environment.py \
  --mode change-role \
  --email jperez@empresa.com \
  --new-job-title "Ejecutivo Finanzas" \
  --new-department "Finanzas" \
  --new-manager gfinanzas@empresa.com \
  --ticket-prev TICKET-2026-0301 \
  --ticket-new TICKET-2026-0302 \
  --dry-run
```

**Verificar en el output:**
- [ ] Perfil anterior detectado correctamente
- [ ] Nuevo perfil resuelto correctamente
- [ ] Grupos que se eliminaran (perfil anterior)
- [ ] Grupos que se agregaran (nuevo perfil)
- [ ] Cambio de licencia (si aplica): de E3 a E5, de F3 a E3, etc.
- [ ] Canales de Teams que se agregaran

### Paso 3 — Ejecutar

```bash
python create_environment.py \
  --mode change-role \
  --email jperez@empresa.com \
  --new-job-title "Ejecutivo Finanzas" \
  --new-department "Finanzas" \
  --new-manager gfinanzas@empresa.com \
  --ticket-prev TICKET-2026-0301 \
  --ticket-new TICKET-2026-0302
```

### Paso 4 — Verificar resultado

- [ ] **Entra ID:** `jobTitle` y `department` actualizados
- [ ] **Entra ID:** manager actualizado al nuevo manager
- [ ] **Entra ID:** usuario removido de grupos del perfil anterior
- [ ] **Entra ID:** usuario agregado a grupos del nuevo perfil
- [ ] **Entra ID:** licencia actualizada si correspondia
- [ ] **Teams:** usuario en canales del nuevo perfil
- [ ] **Talana:** cargo y departamento actualizados

---

## Advertencias

> **Acceso inmediato a recursos anteriores bloqueado:** Al eliminar al usuario de los grupos del perfil anterior, pierde acceso a esos recursos inmediatamente. Coordinar con ambos managers el momento exacto de ejecucion.

> **Datos en areas anteriores:** Si el colaborador tiene archivos en OneDrive o es responsable de tareas en Planner del area anterior, esas responsabilidades deben transferirse manualmente antes o despues del cambio de rol.

> **Licencia downgrade:** Si el nuevo perfil tiene una licencia de menor capacidad (ej: de E5 a E3), el usuario pierde acceso a herramientas Premium (Power BI Pro, Defender avanzado, etc.). Verificar el impacto antes de ejecutar.

---

## Que hacer si falla

| Error | Causa probable | Solucion |
|---|---|---|
| `Profile not found` | El nuevo cargo no esta en el catalogo de perfiles | Agregar el perfil en [PERFILES_ROLES.md](../PERFILES_ROLES.md) y en el codigo |
| `License downgrade conflict` | El usuario tiene apps exclusivas de la licencia anterior en uso | Revisar con IT antes de bajar la licencia |
| `Group not found` | Un grupo del nuevo perfil no existe en el tenant | Crear el grupo en Entra ID o corregir el catalogo de perfiles |
| Talana no se actualiza | Error en PATCH de Talana | Actualizar manualmente en Talana y registrar incidente |
