# Integracion: Microsoft Teams

## Que es

Microsoft Teams es la plataforma de comunicacion y colaboracion del ecosistema M365. En este proyecto se usa para:
- Crear **canales de proyecto** dentro del Team del grupo
- Agregar **miembros** con roles de owner o member
- Anclar **pestanas** de Planner en los canales de proyecto
- Enviar **mensajes de notificacion** al canal cuando un entorno esta listo

---

## Permisos Graph API requeridos

| Permiso | Tipo | Para que |
|---|---|---|
| `Team.ReadBasic.All` | Application | Leer informacion de Teams |
| `Channel.Create` | Application | Crear canales estandar |
| `Channel.ReadBasic.All` | Application | Leer canales existentes |
| `ChannelMember.ReadWrite.All` | Application | Agregar/quitar miembros de canales |
| `TeamMember.ReadWrite.All` | Application | Agregar/quitar miembros del Team |
| `TeamsTab.ReadWrite.All` | Application | Crear y gestionar tabs (pestanas) |

---

## Endpoints implementados

### Listar canales del Team

```http
GET /v1.0/teams/{team-id}/channels
```

Respuesta relevante:
```json
{
  "value": [
    {
      "id": "yyyyyyyy-yyyy-yyyy-yyyy-yyyyyyyyyyyy",
      "displayName": "Proyecto Alpha",
      "membershipType": "standard"
    }
  ]
}
```

### Crear canal de proyecto

```http
POST /v1.0/teams/{team-id}/channels
Content-Type: application/json

{
  "displayName": "Proyecto Alpha",
  "description": "Canal del proyecto Alpha — Q1 2026",
  "membershipType": "standard"
}
```

> `membershipType: "standard"` crea un canal accesible para todos los miembros del Team. Para canal privado, usar `"private"` (requiere que el Team tenga esta caracteristica habilitada).

### Agregar miembro al Team (como owner o member)

```http
POST /v1.0/teams/{team-id}/members
Content-Type: application/json

{
  "@odata.type": "#microsoft.graph.aadUserConversationMember",
  "roles": ["owner"],
  "user@odata.bind": "https://graph.microsoft.com/v1.0/users/{user-id}"
}
```

Para agregar como `member`, usar `"roles": []` (array vacio).

### Agregar miembro a canal especifico

```http
POST /v1.0/teams/{team-id}/channels/{channel-id}/members
Content-Type: application/json

{
  "@odata.type": "#microsoft.graph.aadUserConversationMember",
  "roles": [],
  "user@odata.bind": "https://graph.microsoft.com/v1.0/users/{user-id}"
}
```

### Quitar miembro del Team

```http
DELETE /v1.0/teams/{team-id}/members/{membership-id}
```

Para obtener el `membership-id`:
```http
GET /v1.0/teams/{team-id}/members?$filter=microsoft.graph.aadUserConversationMember/userId eq '{user-id}'
```

### Anclar pestana de Planner en canal

```http
POST /v1.0/teams/{team-id}/channels/{channel-id}/tabs
Content-Type: application/json

{
  "displayName": "Plan del Proyecto",
  "teamsApp@odata.bind": "https://graph.microsoft.com/v1.0/appCatalogs/teamsApps/com.microsoft.teamspace.tab.planner",
  "configuration": {
    "entityId": "{plan-id}",
    "contentUrl": "https://tasks.office.com/{tenant-id}/Home/PlanViews/{plan-id}?Type=PlanLink&Channel=TeamsTab",
    "removeUrl": "https://tasks.office.com/{tenant-id}/Home/PlanViews/{plan-id}?Type=PlanLink&Channel=TeamsTab",
    "websiteUrl": "https://tasks.office.com/{tenant-id}/Home/PlanViews/{plan-id}"
  }
}
```

### Enviar mensaje al canal

```http
POST /v1.0/teams/{team-id}/channels/{channel-id}/messages
Content-Type: application/json

{
  "body": {
    "contentType": "html",
    "content": "<p>El entorno del <strong>Proyecto Alpha</strong> esta listo. El plan de Planner y las carpetas de SharePoint han sido configurados.</p>"
  }
}
```

---

## Flujo de creacion de entorno de proyecto (Teams)

```python
# Pseudocodigo — ver create_environment.py para implementacion real

def setup_teams_channel(team_id, project_name, pm_id, members):
    # 1. Verificar si el canal ya existe
    channels = graph_request("GET", f"/teams/{team_id}/channels")
    existing = [c for c in channels if c["displayName"] == project_name]

    if existing:
        channel_id = existing[0]["id"]
        log.warning(f"Canal '{project_name}' ya existe. Usando existente.")
    else:
        # 2. Crear canal
        channel = graph_request("POST", f"/teams/{team_id}/channels",
                                body={"displayName": project_name,
                                      "membershipType": "standard"})
        channel_id = channel["id"]

    # 3. Agregar PM como owner
    graph_request("POST", f"/teams/{team_id}/members",
                  body={"@odata.type": "#microsoft.graph.aadUserConversationMember",
                        "roles": ["owner"],
                        "user@odata.bind": f".../{pm_id}"})

    # 4. Agregar equipo como members
    for member_id in members:
        graph_request("POST", f"/teams/{team_id}/members",
                      body={"roles": [], "user@odata.bind": f".../{member_id}"})

    return channel_id
```

---

## Idempotencia

La creacion de canales verifica existencia previa antes de crear. Si el canal ya existe, usa el existente y registra un warning. La adicion de miembros devuelve `409 Conflict` si ya son miembros — el sistema lo maneja como advertencia (no como error).

---

## Troubleshooting

| Problema | Causa probable | Solucion |
|---|---|---|
| `403 Forbidden` en crear canal | `Channel.Create` no otorgado | Agregar permiso en App Registration |
| `404 Not Found` en Team | `team-id` (= `group-id`) incorrecto | Verificar el ID del grupo en Azure Portal |
| `409 Conflict` al agregar miembro | Usuario ya es miembro del Team | Normal — ignorar o manejar como warning |
| Tab de Planner no aparece | `plan-id` incorrecto en la configuracion | Verificar el ID del plan con `GET /groups/{id}/planner/plans` |
| Usuario no puede ser owner | El usuario no tiene licencia de Teams | Asignar licencia que incluya Teams antes de agregarlo |

---

## Notas sobre tipos de canales

| Tipo | Visibilidad | Cuando usar |
|---|---|---|
| `standard` | Todos los miembros del Team | Proyectos de equipo general |
| `private` | Solo miembros invitados explicitamente | Proyectos con informacion restringida |
| `shared` | Puede incluir usuarios externos | Colaboracion con proveedores externos |

> Los canales privados requieren que el Team tenga `isMembershipLimitedToOwners: false` en su configuracion. Verificar antes de crear.
