# Integracion: SharePoint Online

## Que es

SharePoint Online es la plataforma de gestion documental de Microsoft 365. En este proyecto se usa para:
- Crear la **estructura de carpetas** de cada proyecto
- Subir **archivos de plantilla** al momento de crear el entorno (Acta de Inicio, Ficha de Proyecto)
- Gestionar **permisos de acceso** a nivel de carpeta o biblioteca

---

## Permisos Graph API requeridos

| Permiso | Tipo | Para que |
|---|---|---|
| `Sites.ReadWrite.All` | Application | Leer y escribir en sitios SharePoint |
| `Files.ReadWrite.All` | Application | Crear carpetas y subir archivos |
| `Sites.Manage.All` | Application | Gestionar permisos de sitio (si se requiere) |

---

## Endpoints implementados

### Obtener informacion del sitio

```http
GET /v1.0/groups/{group-id}/sites/root
```

Respuesta relevante:
```json
{
  "id": "empresa.sharepoint.com,xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx,yyyyyyyy-yyyy-yyyy-yyyy-yyyyyyyyyyyy",
  "name": "Nombre del Team",
  "webUrl": "https://empresa.sharepoint.com/sites/nombre-team"
}
```

### Obtener drive principal del sitio

```http
GET /v1.0/sites/{site-id}/drive
```

### Crear carpeta

```http
PUT /v1.0/drives/{drive-id}/root:/{ruta-carpeta}:/children
Content-Type: application/json

{
  "name": "Documentos",
  "folder": {},
  "@microsoft.graph.conflictBehavior": "rename"
}
```

> `@microsoft.graph.conflictBehavior: "rename"` evita errores si la carpeta ya existe — la renombra con un sufijo numerico. Para idempotencia real, verificar existencia con GET primero.

### Verificar si carpeta existe

```http
GET /v1.0/drives/{drive-id}/root:/{ruta-carpeta}
```

Retorna `404 Not Found` si no existe. Retorna el item si existe.

### Subir archivo (archivos hasta 4 MB)

```http
PUT /v1.0/drives/{drive-id}/root:/{ruta}/{nombre-archivo}:/content
Content-Type: application/vnd.openxmlformats-officedocument.wordprocessingml.document

[contenido binario del archivo]
```

### Subir archivo grande (mas de 4 MB — upload session)

```http
# Paso 1: Crear sesion de upload
POST /v1.0/drives/{drive-id}/root:/{ruta}/{nombre}:/createUploadSession
Content-Type: application/json

{
  "item": {
    "@microsoft.graph.conflictBehavior": "replace",
    "name": "archivo.docx"
  }
}

# Respuesta incluye: uploadUrl (valida por 15 minutos)

# Paso 2: Subir contenido en chunks de hasta 320 KB
PUT {uploadUrl}
Content-Range: bytes 0-327679/1048576
Content-Length: 327680

[chunk de datos binarios]
```

### Listar contenido de carpeta

```http
GET /v1.0/drives/{drive-id}/root:/{ruta}:/children
```

---

## Estructura de carpetas por defecto

Al crear un nuevo proyecto con `create_environment.py`, se genera la siguiente estructura en SharePoint:

```
Documentos/
└── Proyectos/
    └── {Nombre del Proyecto}/
        ├── 01 - Inicio/
        │   ├── Acta de Inicio de Proyecto.docx
        │   └── Ficha de Proyecto.docx
        ├── 02 - Planificacion/
        ├── 03 - Ejecucion/
        ├── 04 - Cierre/
        └── 05 - Archivo/
```

---

## Flujo de creacion de estructura de proyecto

```python
# Pseudocodigo — ver create_environment.py para implementacion real

def setup_sharepoint_structure(site_id, project_name, templates_dir):
    drive = graph_request("GET", f"/sites/{site_id}/drive")
    drive_id = drive["id"]

    folders = [
        f"Documentos/Proyectos/{project_name}",
        f"Documentos/Proyectos/{project_name}/01 - Inicio",
        f"Documentos/Proyectos/{project_name}/02 - Planificacion",
        f"Documentos/Proyectos/{project_name}/03 - Ejecucion",
        f"Documentos/Proyectos/{project_name}/04 - Cierre",
        f"Documentos/Proyectos/{project_name}/05 - Archivo",
    ]

    for folder_path in folders:
        # Verificar existencia antes de crear
        try:
            graph_request("GET", f"/drives/{drive_id}/root:/{folder_path}")
            log.info(f"Carpeta ya existe: {folder_path}")
        except GraphNotFoundError:
            create_folder(drive_id, folder_path)

    # Subir plantillas
    upload_template(drive_id, f"Documentos/Proyectos/{project_name}/01 - Inicio",
                    f"{templates_dir}/Acta_de_Inicio_de_Proyecto.docx")
    upload_template(drive_id, f"Documentos/Proyectos/{project_name}/01 - Inicio",
                    f"{templates_dir}/Ficha_de_Proyecto_Nueva_Iniciativa.docx")
```

---

## Idempotencia

La creacion de carpetas usa un patron check-before-create:
1. `GET /drives/{id}/root:/{ruta}` — si retorna 200, la carpeta existe → no crear
2. Si retorna 404 → crear la carpeta

Esto garantiza que ejecutar `create_environment.py` dos veces no genera carpetas duplicadas.

---

## Troubleshooting

| Problema | Causa probable | Solucion |
|---|---|---|
| `403 Forbidden` | `Sites.ReadWrite.All` no otorgado | Agregar permiso y otorgar consentimiento de admin |
| `404 Not Found` en sitio | `SHAREPOINT_SITE_ID` incorrecto | Obtener el ID correcto con `GET /groups/{id}/sites/root` |
| `413 Request Entity Too Large` | Archivo mayor a 4 MB sin usar upload session | Usar el endpoint de upload session para archivos grandes |
| Carpeta duplicada con sufijo numerico | `conflictBehavior: "rename"` activo sin verificacion previa | Activar el check de existencia antes de crear |
| Permisos de sitio no heredados | El sitio tiene herencia de permisos rota | Revisar en SharePoint Admin Center y restaurar herencia |
