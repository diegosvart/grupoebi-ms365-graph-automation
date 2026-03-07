# Catalogo de Perfiles por Rol

## Concepto

El sistema de perfilamiento elimina la necesidad de que RRHH configure permisos individuales en M365. Cuando se da de alta a un nuevo colaborador, el analista de RRHH **solo indica el cargo y area**. El sistema resuelve automaticamente todo lo que ese perfil debe recibir.

```
Cargo: Analista RRHH  ──►  Perfil: rrhh_analyst
Area: Recursos Humanos         │
                               ├── Licencia M365 E3
                               ├── Grupos: GRP-RRHH, GRP-VPN, GRP-Intranet
                               ├── Canales Teams: General, Anuncios, RRHH-Equipo
                               ├── Apps: Office 365, HR Portal, Talana Web
                               └── Onboarding CSV: templates/onboarding/rrhh_analyst.csv
```

---

## Perfiles definidos

### Analista RRHH (`rrhh_analyst`)

| Campo | Valor |
|---|---|
| **Licencia M365** | Microsoft 365 E3 |
| **Grupos de seguridad** | GRP-RRHH, GRP-VPN, GRP-Intranet |
| **Canales Teams** | General, Anuncios, RRHH-Equipo |
| **Aplicaciones** | Office 365, HR Portal, Talana Web |
| **CSV onboarding** | `templates/onboarding/rrhh_analyst.csv` |
| **Permisos especiales** | Acceso de lectura a directorio de empleados en SharePoint |

**Grupos de seguridad — detalle:**

| Grupo | Proposito |
|---|---|
| `GRP-RRHH` | Acceso a recursos del area de RRHH (carpetas SharePoint, apps internas) |
| `GRP-VPN` | Acceso a red corporativa via VPN |
| `GRP-Intranet` | Acceso a la intranet de Grupo EBI |

---

### Gerente de Area (`gerente_area`)

| Campo | Valor |
|---|---|
| **Licencia M365** | Microsoft 365 E5 |
| **Grupos de seguridad** | GRP-Gerencia, GRP-VPN, GRP-PowerBI, GRP-ERP-Admin, GRP-Intranet |
| **Canales Teams** | General, Anuncios, Gerencia, canal de su area |
| **Aplicaciones** | Office 365, Power BI Pro, ERP, HR Portal |
| **CSV onboarding** | `templates/onboarding/gerente.csv` |
| **Permisos especiales** | Owner del canal de su area en Teams; acceso a reportes de Power BI |

**Grupos de seguridad — detalle:**

| Grupo | Proposito |
|---|---|
| `GRP-Gerencia` | Acceso a recursos exclusivos de gerencia (documentos estrategicos) |
| `GRP-VPN` | Acceso a red corporativa via VPN |
| `GRP-PowerBI` | Licencia y acceso a reportes de Power BI Pro |
| `GRP-ERP-Admin` | Acceso administrativo al ERP corporativo |
| `GRP-Intranet` | Acceso a la intranet de Grupo EBI |

---

### Colaborador Operaciones (`colaborador_operaciones`)

| Campo | Valor |
|---|---|
| **Licencia M365** | Microsoft 365 F3 (Frontline Worker) |
| **Grupos de seguridad** | GRP-Operaciones, GRP-Intranet |
| **Canales Teams** | General, Operaciones-Turno |
| **Aplicaciones** | Microsoft Teams (mobile), Office Basic |
| **CSV onboarding** | `templates/onboarding/operaciones.csv` |
| **Permisos especiales** | Ninguno adicional |

**Nota:** La licencia F3 (Frontline Worker) es adecuada para colaboradores operativos que acceden principalmente desde dispositivos moviles y no requieren el suite completo de Office.

**Grupos de seguridad — detalle:**

| Grupo | Proposito |
|---|---|
| `GRP-Operaciones` | Acceso a recursos del area operativa |
| `GRP-Intranet` | Acceso a la intranet de Grupo EBI |

---

### Ejecutivo Finanzas (`ejecutivo_finanzas`)

| Campo | Valor |
|---|---|
| **Licencia M365** | Microsoft 365 E3 |
| **Grupos de seguridad** | GRP-Finanzas, GRP-VPN, GRP-ERP, GRP-PowerBI, GRP-Intranet |
| **Canales Teams** | General, Finanzas-Equipo |
| **Aplicaciones** | Office 365, ERP, Power BI, Excel Advanced |
| **CSV onboarding** | `templates/onboarding/finanzas.csv` |
| **Permisos especiales** | Acceso a reportes financieros en Power BI y SharePoint Finanzas |

**Grupos de seguridad — detalle:**

| Grupo | Proposito |
|---|---|
| `GRP-Finanzas` | Acceso a recursos financieros (carpetas SharePoint, apps contables) |
| `GRP-VPN` | Acceso a red corporativa via VPN |
| `GRP-ERP` | Acceso al ERP corporativo (usuario estandar) |
| `GRP-PowerBI` | Licencia y acceso a reportes de Power BI |
| `GRP-Intranet` | Acceso a la intranet de Grupo EBI |

---

### Ejecutivo Comercial (`ejecutivo_comercial`)

| Campo | Valor |
|---|---|
| **Licencia M365** | Microsoft 365 E3 |
| **Grupos de seguridad** | GRP-Comercial, GRP-VPN, GRP-CRM, GRP-Intranet |
| **Canales Teams** | General, Comercial-Equipo |
| **Aplicaciones** | Office 365, CRM, Power BI (lectura) |
| **CSV onboarding** | `templates/onboarding/comercial.csv` |
| **Permisos especiales** | Acceso de lectura a Power BI comercial |

---

### Analista TI (`analista_ti`)

| Campo | Valor |
|---|---|
| **Licencia M365** | Microsoft 365 E5 |
| **Grupos de seguridad** | GRP-TI, GRP-VPN, GRP-Admins-M365, GRP-Intranet |
| **Canales Teams** | General, TI-Equipo, TI-Soporte |
| **Aplicaciones** | Office 365, Azure Portal, Power Platform, Intune Portal |
| **CSV onboarding** | `templates/onboarding/ti_analyst.csv` |
| **Permisos especiales** | Acceso al portal de Azure y Intune para administracion de dispositivos |

---

## Tabla resumen de licencias por perfil

| Perfil | Licencia | Costo mensual aprox. | Cuando usar |
|---|---|---|---|
| Gerente de Area | M365 E5 | Mayor | Liderazgo con necesidades avanzadas de seguridad y analytics |
| Analista TI | M365 E5 | Mayor | Administracion de sistemas y seguridad |
| Analista RRHH | M365 E3 | Medio | Trabajo de escritorio con Office completo |
| Ejecutivo Finanzas | M365 E3 | Medio | Trabajo de escritorio con Office completo |
| Ejecutivo Comercial | M365 E3 | Medio | Trabajo de escritorio con Office completo |
| Colaborador Operaciones | M365 F3 | Menor | Trabajo de campo / sin escritorio fijo |

---

## Como se usa el perfil en los flujos de alta

En el flujo de alta de usuario (ver [ALTA_USUARIO.md](guias/ALTA_USUARIO.md)), el sistema resuelve el perfil de la siguiente manera:

```python
# Pseudocodigo — la implementacion real esta en create_environment.py
perfil = catalogo_perfiles[cargo][area]

# Luego ejecuta automaticamente:
POST /users                           # Crear cuenta Entra ID
POST /users/{id}/assignLicense        # Licencia segun perfil
POST /groups/{id}/members/$ref        # Por cada grupo en perfil.grupos
POST /teams/{id}/members              # Por cada canal en perfil.canales
POST /planner/tasks                   # Tareas onboarding del CSV del perfil
POST /users/{id}/sendMail             # Email de bienvenida
```

---

## Como agregar un nuevo perfil

1. Definir el nuevo perfil siguiendo la estructura de los existentes (licencia, grupos, canales, apps, CSV onboarding).
2. Crear el CSV de onboarding en `templates/onboarding/nuevo_perfil.csv`.
3. Agregar el perfil a este documento y al catalogo en codigo (`catalogo_perfiles` en `create_environment.py`).
4. Crear los grupos de seguridad necesarios en Entra ID si no existen.
5. Abrir un PR con los cambios. El PR requiere revision del administrador de Azure y aprobacion del area de RRHH.

---

## Mantenimiento del catalogo

| Accion | Responsable | Proceso |
|---|---|---|
| Agregar nuevo perfil | Administrador Azure + RRHH | PR con revision obligatoria |
| Modificar grupos de un perfil existente | Administrador Azure | PR + notificacion a RRHH |
| Cambiar licencia de un perfil | Gerencia + Administrador Azure | PR + validacion de impacto en usuarios existentes |
| Revisar y actualizar el catalogo | Administrador Azure | Revision trimestral |
