# Glosario

Terminos usados en este proyecto, explicados en lenguaje simple.

---

## Microsoft 365 y Azure

**App Registration**
Una "identidad" de aplicacion registrada en Azure que permite a este sistema conectarse a Microsoft 365 sin usuario. Tiene su propio Client ID y Client Secret (como usuario y contrasena de la app).

**Azure Entra ID**
El directorio de identidades de Microsoft 365 (antes llamado Azure Active Directory o Azure AD). Guarda los usuarios, grupos, licencias y permisos de toda la organizacion. Es la fuente autoritativa de identidades.

**Client Credentials Flow**
Metodo de autenticacion donde la aplicacion se identifica con su propio Client ID y Client Secret, sin necesidad de que un usuario inicie sesion. Es el metodo que usa este sistema para hacer llamadas a la Graph API.

**Graph API (Microsoft Graph)**
La API REST central de Microsoft 365. Permite operar sobre todos los servicios de M365 (Teams, Planner, SharePoint, Exchange, Intune, etc.) desde un solo punto de entrada: `https://graph.microsoft.com/v1.0/`.

**GUID / UUID**
Identificador unico universal. Formato: `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`. En M365, cada usuario, grupo, plan, canal o tarea tiene un GUID unico.

**Group M365**
Un grupo de Microsoft 365 es la unidad base que agrupa a los colaboradores de un Team. Tiene un solo ID (el `GROUP_ID`) que sirve para Teams, Planner y SharePoint del mismo equipo.

**Licencia M365**
La suscripcion que habilita los servicios de Microsoft 365 para un usuario.
- **E3:** Suite completa de productividad (Office, Teams, Exchange, SharePoint). Para trabajo de escritorio.
- **E5:** E3 + seguridad avanzada, Power BI Pro, Defender. Para gerentes y TI.
- **F3 (Frontline Worker):** Version basica para colaboradores sin escritorio fijo. Incluye Teams mobile y correo basico.

**MFA (Multi-Factor Authentication)**
Verificacion en dos pasos. Ademas de la contrasena, se requiere un segundo factor (codigo de autenticador, SMS, etc.). Obligatorio en Grupo EBI para acceder a recursos corporativos.

**Permisos de aplicacion (Application permissions)**
Permisos que la App Registration tiene sobre los datos de M365, sin depender de que un usuario especifico este conectado. Todos los permisos de este sistema son de tipo Application (no Delegated).

**Principio de minimo privilegio**
Regla de seguridad: otorgar solo los permisos estrictamente necesarios para la operacion que se realizara. No dar acceso de administrador si solo se necesita lectura.

**SharePoint Site**
El sitio web de SharePoint asociado a un grupo M365. Contiene las bibliotecas de documentos del equipo. La URL tipica es `https://empresa.sharepoint.com/sites/nombre-equipo`.

**SKU ID**
Identificador de la licencia M365. Necesario para asignar licencias via Graph API. Se obtiene con `GET /subscribedSkus`.

**Tenant**
La "instancia" de Microsoft 365 de una organizacion. Grupo EBI tiene un tenant con su propio Tenant ID. Todos los usuarios y recursos de M365 pertenecen a este tenant.

**Throttling (HTTP 429)**
Cuando la Graph API rechaza llamadas porque se supero el limite de solicitudes por segundo. El sistema espera el tiempo indicado en el header `Retry-After` y reintenta automaticamente.

**UPN (User Principal Name)**
El identificador de inicio de sesion del usuario en M365. Generalmente es el email corporativo: `jperez@empresa.com`.

---

## Microsoft Planner

**Bucket**
Una columna o categoria dentro de un Plan de Planner. Agrupa tareas por fase, tipo o responsable. Ejemplo: "Inicio", "Ejecucion", "Cierre".

**ETag**
Valor de control de concurrencia que Planner requiere en las operaciones PATCH y DELETE. Garantiza que no se sobreescriban cambios hechos por otro proceso. El sistema lo obtiene automaticamente con el GET previo.

**Plan**
Un tablero de Planner que contiene buckets y tareas. Asociado a un grupo M365.

**Task (Tarea)**
Una unidad de trabajo en Planner. Tiene titulo, responsable, fecha de vencimiento, prioridad, descripcion y checklist de subtareas.

---

## Talana HRIS

**HRIS (Human Resources Information System)**
Sistema de Informacion de Recursos Humanos. Talana es el HRIS de Grupo EBI. Gestiona contratos, liquidaciones, vacaciones y la estructura organizacional.

**Webhook**
Una notificacion HTTP que Talana envia automaticamente a este sistema cuando ocurre un evento (alta, baja, modificacion de empleado). Es como un "aviso push" que dispara la automatizacion sin que nadie tenga que hacerlo manualmente.

**Polling**
Alternativa al webhook: en lugar de esperar que Talana avise, el sistema consulta Talana periodicamente para detectar cambios. Es menos eficiente pero sirve como fallback.

**API Key**
Credencial de autenticacion para la API REST de Talana. Se configura en la variable `TALANA_API_KEY`.

---

## Terminos tecnicos del proyecto

**CSV (Comma-Separated Values)**
Archivo de texto que organiza datos en filas y columnas. En este proyecto se usa punto y coma (`;`) como delimitador en lugar de coma. Se usa para definir planes, buckets y tareas de Planner.

**Dry-run**
Modo de simulacion que ejecuta toda la logica del programa pero **sin hacer llamadas reales a la API**. Sirve para verificar que el comando hara lo que se espera antes de operar en produccion. Siempre ejecutar dry-run primero.

**Hook (Claude Code)**
Script que se ejecuta automaticamente en eventos del agente de IA (inicio de sesion, escritura de archivo). El hook `guard-sensitive.py` detecta y bloquea la exposicion de secretos antes de que el agente pueda escribirlos en documentos.

**Idempotencia**
Propiedad de una operacion que produce el mismo resultado sin importar cuantas veces se ejecute. Ejemplo: crear una carpeta es idempotente si el sistema verifica su existencia antes de crearla.

**OAuth 2.0**
Protocolo estandar de autorizacion. Este sistema usa el flujo "Client Credentials" de OAuth 2.0 para obtener tokens de acceso a la Graph API.

**Access Token (JWT)**
Token de acceso temporal (dura 3600 segundos) que la Graph API acepta como credencial. El sistema lo renueva automaticamente cuando expira.

**Perfil de rol**
Configuracion predefinida que mapea un cargo/area a un conjunto de licencias, grupos de seguridad, canales de Teams y apps. Ver catalogo completo en [PERFILES_ROLES.md](PERFILES_ROLES.md).

**Onboarding**
Proceso de alta e incorporacion de un nuevo colaborador: crear su cuenta M365, asignar licencias y permisos, agregarlo a Teams y Planner, y enviarle el email de bienvenida.

**Offboarding**
Proceso de baja de un colaborador: deshabilitar cuenta, revocar accesos, archivar buzon, liberar licencia y eventualmente eliminar la cuenta.
