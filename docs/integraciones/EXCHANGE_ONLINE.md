# Integracion: Exchange Online

## Que es

Exchange Online es el servicio de correo electronico de Microsoft 365. En este proyecto se usa para:
- Enviar el **email de bienvenida** al nuevo colaborador al hacer onboarding
- Configurar **forwarding del buzon** al manager durante el offboarding
- Activar el **mensaje de fuera de oficina (OOF)** durante el offboarding
- Crear **grupos de distribucion** por area o proyecto

El buzon de Exchange se crea automaticamente cuando se asigna una licencia M365 que incluye Exchange (E3, E5). No requiere un paso separado de creacion.

---

## Permisos Graph API requeridos

| Permiso | Tipo | Para que |
|---|---|---|
| `Mail.Send` | Application | Enviar emails como la cuenta de sistema |
| `MailboxSettings.ReadWrite` | Application | Configurar OOF y forwarding |
| `Mail.ReadWrite` | Application | Leer mensajes (solo si se necesita procesamiento de respuestas) |

> Estos permisos requieren **consentimiento de administrador de tenant**.

---

## Endpoints implementados

### Enviar email de bienvenida

```http
POST /v1.0/users/{from-user-id}/sendMail
Content-Type: application/json

{
  "message": {
    "subject": "Bienvenido/a a Grupo EBI — Tu entorno digital esta listo",
    "body": {
      "contentType": "HTML",
      "content": "<h2>Bienvenido/a, {{nombre}}!</h2><p>Tu cuenta Microsoft 365 esta lista...</p>"
    },
    "toRecipients": [
      { "emailAddress": { "address": "jperez@empresa.com" } }
    ],
    "ccRecipients": [
      { "emailAddress": { "address": "ggerente@empresa.com" } }
    ]
  },
  "saveToSentItems": false
}
```

> El email se envia **desde la cuenta de sistema** configurada en la App Registration. Verificar que la cuenta de sistema tiene buzon activo y permiso `Mail.Send`.

### Configurar forwarding del buzon (offboarding)

```http
PATCH /v1.0/users/{id}/mailboxSettings
Content-Type: application/json

{
  "forwardingSmtpAddress": "ggerente@empresa.com",
  "automaticRepliesSetting": {
    "status": "AlwaysEnabled",
    "externalAudience": "none",
    "internalReplyMessage": "Juan Perez ya no trabaja en Grupo EBI. Para consultas, contactar a Gerencia de RRHH.",
    "externalReplyMessage": "Esta direccion de correo ya no esta activa. Por favor contacte a contacto@empresa.com."
  }
}
```

### Obtener configuracion actual del buzon

```http
GET /v1.0/users/{id}/mailboxSettings
```

Respuesta relevante:
```json
{
  "forwardingSmtpAddress": "ggerente@empresa.com",
  "automaticRepliesSetting": {
    "status": "AlwaysEnabled"
  },
  "timeZone": "America/Santiago"
}
```

### Crear grupo de distribucion

```http
POST /v1.0/groups
Content-Type: application/json

{
  "displayName": "Equipo Finanzas",
  "mailNickname": "equipo-finanzas",
  "mailEnabled": true,
  "securityEnabled": false,
  "groupTypes": []
}
```

### Crear evento de calendario (kick-off)

```http
POST /v1.0/users/{pm-id}/events
Content-Type: application/json

{
  "subject": "Kick-off: Proyecto Alpha",
  "start": { "dateTime": "2026-04-05T09:00:00", "timeZone": "America/Santiago" },
  "end": { "dateTime": "2026-04-05T10:00:00", "timeZone": "America/Santiago" },
  "attendees": [
    { "emailAddress": { "address": "equipo@empresa.com" }, "type": "required" }
  ],
  "isOnlineMeeting": true,
  "onlineMeetingProvider": "teamsForBusiness"
}
```

---

## Plantilla de email de bienvenida

```html
<h2>Bienvenido/a a Grupo EBI, {{nombre}}!</h2>

<p>Tu entorno digital Microsoft 365 esta listo. Aqui tienes lo que necesitas para comenzar:</p>

<h3>Tus credenciales</h3>
<ul>
  <li><strong>Email corporativo:</strong> {{email_corporativo}}</li>
  <li><strong>Contrasena temporal:</strong> <em>(entregada por tu jefatura directa)</em></li>
</ul>

<h3>Primeros pasos</h3>
<ol>
  <li>Accede a <a href="https://office.com">office.com</a> y cambia tu contrasena.</li>
  <li>Configura la verificacion en dos pasos en <a href="https://aka.ms/mysignins">aka.ms/mysignins</a>.</li>
  <li>Abre Microsoft Teams — encontraras los canales de tu area ya configurados.</li>
  <li>Revisa tus tareas de incorporacion en Microsoft Planner.</li>
</ol>

<h3>Tus recursos</h3>
<ul>
  <li>Teams: {{teams_channel_link}}</li>
  <li>Plan de onboarding: {{planner_link}}</li>
  <li>SharePoint del area: {{sharepoint_link}}</li>
</ul>

<p>Si tienes dudas, contacta a tu jefatura directa o al area de TI.</p>

<p>Bienvenido/a al equipo.</p>
```

---

## Troubleshooting

| Problema | Causa probable | Solucion |
|---|---|---|
| `ErrorAccessDenied` en sendMail | Permiso `Mail.Send` no otorgado o sin consentimiento de admin | Otorgar consentimiento en Azure Portal |
| Email no llega | Cuenta origen sin buzon activo | Usar una cuenta con buzon activo como remitente o esperar que Exchange cree el buzon tras asignar licencia |
| Forwarding no se activa | `MailboxSettings.ReadWrite` faltante | Agregar permiso y otorgar consentimiento |
| `Request_ResourceNotFound` | Usuario sin buzon (licencia F3 no incluye buzon completo) | Verificar que la licencia incluye Exchange; F3 tiene capacidades limitadas de correo |
| OOF no se activa externamente | `externalAudience: "none"` en el payload | Cambiar a `"all"` si se requiere respuesta externa |

---

## Notas sobre licencias y Exchange

| Licencia | Tipo de buzon |
|---|---|
| M365 E3 | Buzon completo (50 GB) |
| M365 E5 | Buzon completo (100 GB) |
| M365 F3 | Buzon limitado (2 GB, solo Teams + correo basico) |

Los colaboradores con licencia F3 pueden tener limitaciones al configurar reglas de buzon avanzadas. Verificar antes de aplicar configuraciones de forwarding o OOF.
