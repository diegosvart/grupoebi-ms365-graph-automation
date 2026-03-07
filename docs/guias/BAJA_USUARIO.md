# Guia: Baja de Usuario (Offboarding)

## Que hace este flujo

Ejecuta el proceso de offboarding completo de un colaborador que deja Grupo EBI:

1. **Deshabilita** la cuenta en Azure Entra ID (acceso bloqueado inmediatamente)
2. **Revoca** todas las sesiones activas
3. **Configura** el buzon: forwarding al manager + mensaje de fuera de oficina automatico
4. **Revoca** la licencia M365 (libera la licencia para reasignacion)
5. **Elimina** al usuario de todos los grupos de seguridad del perfil
6. **Actualiza** Talana con el nuevo estado (`inactivo`)
7. **30 dias despues** (con aprobacion IT): elimina la cuenta de Entra ID

---

## Flujo normal — via webhook de Talana (automatico)

El webhook de Talana dispara el flujo automaticamente cuando se registra la baja:

```
Analista RRHH registra baja en Talana
        │
        │ Talana envia webhook baja_empleado
        ▼
Sistema Python ejecuta pasos 1-6 automaticamente
        │
        ├── PATCH /users/{id} { accountEnabled: false }
        ├── POST /users/{id}/revokeSignInSessions
        ├── PATCH mailboxSettings (forwarding + OOF)
        ├── POST /users/{id}/assignLicense { removeLicenses: [...] }
        ├── DELETE /groups/{id}/members/{id} (por cada grupo del perfil)
        └── PATCH Talana { estado: "inactivo" }

[30 dias despues, con aprobacion IT]
        └── DELETE /users/{id}
```

---

## Flujo manual — si el webhook no esta configurado

### Autorizacion requerida

| Nivel | Quien autoriza | Para que paso |
|---|---|---|
| RRHH | Analista RRHH con registro en Talana | Pasos 1-6 (deshabilitar, revocar, forwarding) |
| IT | Administrador Azure o TI | Paso 7 (eliminacion definitiva de la cuenta) |

**IMPORTANTE:** La eliminacion definitiva de la cuenta (paso 7) requiere aprobacion separada de IT y debe ejecutarse con al menos 30 dias de distancia desde la baja. Esta es una medida de seguridad para preservar datos y posibilitar auditorias.

---

## Informacion necesaria

| Campo | Descripcion | Ejemplo |
|---|---|---|
| `email_corporativo` | Email M365 del colaborador que sale | jperez@empresa.com |
| `manager_email` | Email del manager (recibe forwarding del buzon) | ggerente@empresa.com |
| `fecha_baja` | Fecha efectiva de termino de contrato | 2026-03-31 |
| `numero_ticket` | Referencia de autorizacion de RRHH | TICKET-2026-0456 |
| `motivo` | Renuncia / termino de contrato / otro | Renuncia voluntaria |

---

## Paso a paso (modo manual)

### Paso 1 — Verificar que el usuario existe y esta activo

```bash
python create_environment.py \
  --mode check-user \
  --email jperez@empresa.com
```

Verificar en el output:
- [ ] Usuario existe en el tenant
- [ ] Cuenta habilitada (`accountEnabled: true`)
- [ ] Licencia asignada

### Paso 2 — Simular offboarding (dry-run obligatorio)

```bash
python create_environment.py \
  --mode offboard-user \
  --email jperez@empresa.com \
  --manager ggerente@empresa.com \
  --ticket TICKET-2026-0456 \
  --dry-run
```

**Verificar en el output:**
- [ ] Perfil resuelto correctamente (grupos que se eliminaran)
- [ ] Forwarding configurado hacia el manager correcto
- [ ] Licencia que se liberara
- [ ] Fecha estimada de eliminacion definitiva (30 dias)

### Paso 3 — Ejecutar offboarding

Solo tras verificar el dry-run y con autorizacion registrada:

```bash
python create_environment.py \
  --mode offboard-user \
  --email jperez@empresa.com \
  --manager ggerente@empresa.com \
  --ticket TICKET-2026-0456
```

### Paso 4 — Verificar resultado inmediato

- [ ] **Entra ID:** cuenta deshabilitada (`accountEnabled: false`)
- [ ] **Entra ID:** sesiones revocadas (usuario no puede acceder)
- [ ] **Exchange:** forwarding activo hacia el manager
- [ ] **Exchange:** mensaje OOF activo con texto de ausencia indefinida
- [ ] **Entra ID:** licencia M365 liberada
- [ ] **Entra ID:** usuario removido de grupos de seguridad del perfil
- [ ] **Talana:** estado actualizado a `inactivo`

### Paso 5 — Eliminacion definitiva (30 dias despues, con aprobacion IT)

```bash
# Requiere autorizacion de IT (ticket separado)
python create_environment.py \
  --mode delete-user \
  --email jperez@empresa.com \
  --ticket TICKET-2026-0789-IT \
  --dry-run

# Ejecucion real (IRREVERSIBLE)
python create_environment.py \
  --mode delete-user \
  --email jperez@empresa.com \
  --ticket TICKET-2026-0789-IT
```

---

## Que pasa con los datos del usuario

| Recurso | Que pasa | Cuanto tiempo |
|---|---|---|
| Sesiones activas | Revocadas inmediatamente | Inmediato |
| Acceso a recursos | Bloqueado inmediatamente | Inmediato |
| Buzon de correo | Redirigido al manager | 30 dias (luego se elimina con la cuenta) |
| Archivos en OneDrive | Accesibles para el manager (via SharePoint admin) | 30 dias despues de baja |
| Cuenta de Entra ID | Deshabilitada (soft delete) | 30 dias, luego eliminacion definitiva |
| Datos en Planner | Las tareas asignadas quedan sin responsable | No se eliminan automaticamente |
| Licencia M365 | Liberada para reasignacion | Inmediato tras el offboarding |

---

## Advertencias

> **La eliminacion de cuenta es IRREVERSIBLE.** Una vez ejecutado el paso 5 (DELETE /users/{id}), la cuenta no puede recuperarse. El buzon, OneDrive y datos del usuario se eliminan permanentemente. Confirmar dos veces con IT antes de ejecutar.

> **Tareas de Planner sin responsable:** Las tareas asignadas al usuario dado de baja quedan sin responsable en Planner. El manager o PM del proyecto debe reasignarlas manualmente.

> **Acceso inmediato bloqueado:** El paso 1 (deshabilitar cuenta) tiene efecto inmediato. Si la fecha de baja efectiva es futura, coordinar el momento exacto de ejecucion con RRHH y el colaborador.

---

## Que hacer si falla

| Error | Causa probable | Solucion |
|---|---|---|
| `User not found` | Email incorrecto o usuario ya eliminado | Verificar en Azure Portal > Users |
| `403 Forbidden` en revokeSignInSessions | Permiso insuficiente | Requiere `User.ReadWrite.All` en App Registration |
| Forwarding no se activa | Permiso `Mail.ReadWrite` no configurado | Agregar permiso y consentimiento de admin |
| Talana no se actualiza | API key invalida o empleado no encontrado por ID | Verificar `TALANA_API_KEY` y el `employeeId` en Talana |
| Grupos no se eliminan | Algunos grupos son dinamicos y no permiten eliminacion manual | Contactar administrador Azure para revisar configuracion del grupo |
