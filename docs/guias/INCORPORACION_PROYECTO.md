# Guia: Incorporar Usuario a un Proyecto Existente

## Que hace este flujo

Agrega a un colaborador ya existente en M365 a un proyecto en curso:

1. Agrega al usuario como miembro del canal de Teams del proyecto
2. Crea tareas de incorporacion en el Plan de Planner del proyecto
3. Envia email de notificacion al usuario con links al proyecto

---

## Autorizacion requerida

| Quien autoriza |
|---|
| PM del proyecto o lider de area |

Registrar el numero de ticket o referencia antes de ejecutar.

---

## Informacion necesaria

| Campo | Descripcion | Ejemplo |
|---|---|---|
| `email_usuario` | Email M365 del colaborador a incorporar | jperez@empresa.com |
| `group_id` | ID del grupo M365 del Team del proyecto | xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx |
| `channel_id` | ID del canal del proyecto en Teams | yyyyyyyy-yyyy-yyyy-yyyy-yyyyyyyyyyyy |
| `plan_id` | ID del plan de Planner del proyecto | zzzzzzzz-zzzz-zzzz-zzzz-zzzzzzzzzzzz |
| `rol` | `member` o `owner` | member |
| `numero_ticket` | Referencia de autorizacion | TICKET-2026-0234 |

### Como obtener los IDs

```bash
# Obtener channel_id y plan_id de un proyecto
python planner_import.py --mode list --group-id <GROUP_ID>

# Para canales del Team:
# GET https://graph.microsoft.com/v1.0/teams/{GROUP_ID}/channels
```

---

## Paso a paso

### Paso 1 — Simular (dry-run obligatorio)

```bash
python create_environment.py \
  --mode add-to-project \
  --email jperez@empresa.com \
  --group-id xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx \
  --channel-id yyyyyyyy-yyyy-yyyy-yyyy-yyyyyyyyyyyy \
  --plan-id zzzzzzzz-zzzz-zzzz-zzzz-zzzzzzzzzzzz \
  --role member \
  --ticket TICKET-2026-0234 \
  --dry-run
```

**Verificar en el output:**
- [ ] Usuario resuelto correctamente (nombre y email)
- [ ] Canal de Teams correcto (nombre del proyecto)
- [ ] Plan de Planner correcto
- [ ] Rol asignado (`member` o `owner`)

### Paso 2 — Ejecutar

```bash
python create_environment.py \
  --mode add-to-project \
  --email jperez@empresa.com \
  --group-id xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx \
  --channel-id yyyyyyyy-yyyy-yyyy-yyyy-yyyyyyyyyyyy \
  --plan-id zzzzzzzz-zzzz-zzzz-zzzz-zzzzzzzzzzzz \
  --role member \
  --ticket TICKET-2026-0234
```

### Paso 3 — Verificar

- [ ] Usuario visible en el canal de Teams del proyecto
- [ ] Tareas de incorporacion creadas en Planner y asignadas al usuario
- [ ] Email de notificacion enviado con links al canal y al plan

---

## Advertencias

> Si el usuario ya es miembro del canal, la operacion es idempotente (no crea duplicado) y registra una advertencia en el log.

> El usuario debe tener una cuenta activa en M365 antes de ejecutar este flujo. Si el usuario es nuevo, ejecutar primero el flujo de [Alta de Usuario](ALTA_USUARIO.md).

---

## Que hacer si falla

| Error | Causa probable | Solucion |
|---|---|---|
| `User not found` | Email incorrecto o usuario sin cuenta M365 | Verificar en Azure Portal o ejecutar Alta de Usuario primero |
| `Channel not found` | `CHANNEL_ID` incorrecto | Obtener el ID correcto con Graph Explorer o `--mode list` |
| `403 Forbidden` | Permiso `TeamMember.ReadWrite.All` faltante | Agregar permiso en Azure Portal |
| `Already a member` | Usuario ya es miembro del canal | Normal — no requiere accion |
