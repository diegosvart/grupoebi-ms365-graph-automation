# Guia: Alta de Usuario (Onboarding)

## Que hace este flujo

Da de alta a un nuevo colaborador en el ecosistema Microsoft 365 de Grupo EBI de forma completa y automatica:

1. Crea la cuenta de usuario en Azure Entra ID
2. Asigna la licencia M365 segun el perfil del cargo
3. Agrega al usuario a los grupos de seguridad del perfil
4. Agrega al usuario a los canales de Teams correspondientes
5. Crea las tareas de onboarding en Planner (desde el CSV del perfil)
6. Envia email de bienvenida con links a recursos y guias
7. Actualiza Talana con el ID M365 generado y el email corporativo

---

## Flujo normal — via webhook de Talana (automatico)

En la configuracion habitual, el analista de RRHH **solo trabaja en Talana**. El sistema M365 se actualiza automaticamente:

```
Analista RRHH registra alta en Talana
        │
        │ Talana envia webhook automaticamente al sistema
        ▼
Sistema Python recibe el evento y ejecuta todo el flujo
        │
        ├── Resuelve perfil segun cargo + area
        ├── Crea cuenta Entra ID
        ├── Asigna licencia
        ├── Agrega a grupos y canales
        ├── Crea tareas onboarding
        ├── Envia email de bienvenida
        └── Actualiza Talana con ms365_id y email
```

**El analista no necesita ejecutar ningun comando CLI en este modo.**

---

## Flujo manual — si el webhook no esta configurado

Si la integracion de webhook con Talana no esta activa, ejecutar el flujo manualmente.

### Autorizacion requerida

| Quien autoriza | Que necesitas |
|---|---|
| Jefatura directa del nuevo colaborador | Aprobacion por escrito (ticket, email) |
| Administrador de Azure | No requerida para ejecutar, pero debe estar informado |

**Registrar el numero de ticket o referencia antes de ejecutar.**

---

## Informacion necesaria

| Campo | Descripcion | Ejemplo |
|---|---|---|
| `nombre` | Nombre completo del colaborador | Juan Perez Gonzalez |
| `rut` | RUT chileno (usado como `employeeId`) | 12345678-9 |
| `cargo` | Cargo oficial segun Talana | Analista RRHH |
| `area` | Area o departamento | Recursos Humanos |
| `fecha_ingreso` | Fecha de inicio de contrato | 2026-04-01 |
| `email_corporativo` | Email que se le asignara | jperez@empresa.com |
| `manager_email` | Email del jefatura directa | ggerente@empresa.com |
| `numero_ticket` | Referencia de autorizacion | TICKET-2026-0123 |

---

## Paso a paso (modo manual)

### Paso 1 — Verificar que el usuario no existe ya

```bash
# Dry-run de verificacion: busca si el email ya esta en uso
python create_environment.py \
  --mode check-user \
  --email jperez@empresa.com \
  --dry-run
```

Si el usuario ya existe, **no continuar** — coordinar con el administrador de Azure.

### Paso 2 — Preparar archivo de configuracion del usuario

Crear un archivo `usuario_nuevo.json` (o usar el formulario de Teams si esta disponible):

```json
{
  "displayName": "Juan Perez Gonzalez",
  "mailNickname": "jperez",
  "userPrincipalName": "jperez@empresa.com",
  "employeeId": "12345678-9",
  "jobTitle": "Analista RRHH",
  "department": "Recursos Humanos",
  "manager": "ggerente@empresa.com",
  "startDate": "2026-04-01",
  "ticketRef": "TICKET-2026-0123"
}
```

### Paso 3 — Simular (dry-run obligatorio)

```bash
python create_environment.py \
  --mode onboard-user \
  --config usuario_nuevo.json \
  --dry-run
```

**Verificar en el output:**
- [ ] Perfil resuelto correctamente segun cargo y area
- [ ] Licencia M365 correcta (E3 / E5 / F3)
- [ ] Lista de grupos de seguridad correcta
- [ ] Lista de canales de Teams correcta
- [ ] CSV de onboarding correcto para el perfil
- [ ] Email de bienvenida configurado

### Paso 4 — Ejecutar en produccion

Solo tras verificar el dry-run:

```bash
python create_environment.py \
  --mode onboard-user \
  --config usuario_nuevo.json
```

### Paso 5 — Verificar resultado

- [ ] **Entra ID:** usuario visible en Azure Portal > Users
- [ ] **Entra ID:** licencia asignada correctamente
- [ ] **Entra ID:** miembro de los grupos de seguridad del perfil
- [ ] **Teams:** usuario visible en los canales del perfil
- [ ] **Planner:** tareas de onboarding creadas y asignadas al usuario
- [ ] **Email:** el usuario recibio el email de bienvenida
- [ ] **Talana:** registro actualizado con `ms365_id` y `email_corporativo`

---

## Que recibe el nuevo colaborador

El sistema envia automaticamente un email de bienvenida con:
- Email y contrasena temporal (debe cambiarse en el primer acceso)
- Link a [aka.ms/mysignins](https://aka.ms/mysignins) para configurar MFA
- Links a los canales de Teams de su area
- Link al Plan de Planner con sus tareas de onboarding
- Link a la guia de primer acceso para colaboradores

---

## Perfil resuelto automaticamente

El sistema consulta el catalogo de perfiles ([docs/PERFILES_ROLES.md](../PERFILES_ROLES.md)) y asigna automaticamente segun el cargo:

| Cargo | Perfil aplicado | Licencia |
|---|---|---|
| Analista RRHH | `rrhh_analyst` | M365 E3 |
| Gerente de Area | `gerente_area` | M365 E5 |
| Colaborador Operaciones | `colaborador_operaciones` | M365 F3 |
| Ejecutivo Finanzas | `ejecutivo_finanzas` | M365 E3 |
| Ejecutivo Comercial | `ejecutivo_comercial` | M365 E3 |
| Analista TI | `analista_ti` | M365 E5 |

---

## Advertencias

> **Contrasena temporal:** El sistema asigna una contrasena temporal que requiere cambio en el primer acceso. La contrasena temporal se envia al manager del nuevo colaborador (no al usuario directamente), para que la entregue de forma segura.

> **MFA obligatorio:** El acceso a recursos corporativos requiere MFA. El usuario debera configurarlo en el primer acceso desde [aka.ms/mysignins](https://aka.ms/mysignins).

> **No ejecutar dos veces:** Crear el mismo usuario dos veces genera un error 409 en la Graph API. Si el flujo fallo a mitad de camino, revisar el estado en Azure Portal antes de re-ejecutar.

---

## Que hacer si falla

| Error | Causa probable | Solucion |
|---|---|---|
| `409 Conflict` en creacion de usuario | El UPN ya existe en el tenant | Verificar en Azure Portal > Users si ya existe |
| `License not available` | No hay licencias disponibles del tipo requerido | Contactar al administrador de Azure para adquirir licencias |
| `Group not found` | Un grupo del perfil no existe en el tenant | Verificar los grupos en Azure Portal > Groups |
| `403 Forbidden` | La App Registration no tiene `User.ReadWrite.All` | Agregar permiso en Azure Portal y otorgar consentimiento de admin |
| Talana no se actualiza | Error en el PATCH de Talana | Verificar `TALANA_API_KEY` en `.env` y actualizar manualmente en Talana |
| Email de bienvenida no llega | Permiso `Mail.Send` no configurado | Agregar permiso `Mail.Send` a la App Registration |
