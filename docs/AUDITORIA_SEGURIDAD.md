# Auditoria de Seguridad — Informe de Revision

> **Referencia interna — no publicar**
> Este documento es para referencia del equipo de desarrollo. No debe publicarse ni compartirse externamente.

**Fecha de auditoria:** 2026-03-07
**Archivos auditados:** todos los existentes al momento de la revision
**Ejecutado por:** Claude Sonnet 4.6 (agente de IA) + revision manual

---

## Metodologia

Se busco en todos los archivos del repositorio los siguientes patrones:
- GUIDs con formato UUID real que no sean placeholders
- Emails con dominio corporativo real (`@grupoebi.*` u otros)
- Rutas absolutas con nombre de usuario real
- Nombres de tenant de Azure
- Numeros de RUT chilenos
- Tokens o secretos (aunque esten truncados)
- Nombres completos de empleados reales
- IDs de Planner, Teams o SharePoint de produccion

---

## Resultado de la revision

### Estado al inicio de la auditoria

| Archivo | Estado | Hallazgos |
|---|---|---|
| `README.md` | Limpio | Usa placeholders correctos: `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`, `pm@empresa.com`, `lider@empresa.com` |
| `.claude/settings.local.json` | Limpio | Solo configuracion del agente, sin datos sensibles |
| `.gitignore` | Limpio | Sin datos sensibles |

**Archivos Python referenciados en README pero no existentes en el repositorio:**
- `planner_import.py` — NO existe aun en raiz
- `create_environment.py` — NO existe aun en raiz
- `hooks/guard-sensitive.py` — NO existe aun en raiz
- `templates/` — NO existe aun en raiz
- `tests/` — NO existe aun en raiz

El proyecto esta en etapa inicial (scaffold). Los archivos de codigo a implementar en la siguiente fase deben seguir las convenciones de seguridad documentadas.

---

## Hallazgos sensibles — NINGUNO

No se detectaron datos sensibles en los archivos existentes al momento de la auditoria.

---

## Subdirectorios excluidos (proyectos no relacionados)

Los siguientes directorios en la raiz del repositorio de desarrollo **NO pertenecen** a este proyecto y han sido excluidos via `.gitignore`. Contienen datos sensibles de otros proyectos que **nunca deben incluirse** en este repositorio:

| Directorio | Tipo de dato sensible detectado |
|---|---|
| `jarwiss-molt-assistant/` | Tokens Telegram, gateway tokens |
| `dont-forget/` | IP de servidor, root credentials, SSH keys, GitHub PATs |
| `hcingenieros/` | Credenciales DB, FTP |
| `wordpress-local-dckr/` | Credenciales MySQL/WordPress |
| `import-planner-project/` | Email corporativo real en CSV |

**Accion tomada:** Todos estos directorios estan listados explicitamente en `.gitignore` y verificados como excluidos del repositorio.

---

## Convenciones de seguridad para implementacion futura

Cuando se creen los archivos de codigo (`planner_import.py`, `create_environment.py`, etc.), deben seguir estas convenciones:

1. **GUIDs en ejemplos:** usar `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx` o constantes como `<YOUR_GROUP_ID>`
2. **Emails en ejemplos:** usar `usuario@empresa.com`, `pm@empresa.com`
3. **Rutas de ejemplo:** usar `C:\Users\tu-usuario\...` nunca el nombre de usuario real
4. **Fixture de tests:** usar datos completamente ficticios (ver `docs/TESTING.md`)
5. **Variables hardcodeadas:** NUNCA. Siempre desde variables de entorno via `os.getenv()` o `python-dotenv`

---

## Auditoria continua

El hook `hooks/guard-sensitive.py` (a implementar) ejecutara una version automatica de esta auditoria antes de cada sesion del agente de IA. Los patrones a detectar estan documentados en `SECURITY.md`.

Para auditoria manual periodica:
```bash
# Buscar GUIDs que parecen reales (no placeholders)
grep -r "[0-9a-f]\{8\}-[0-9a-f]\{4\}-[0-9a-f]\{4\}-[0-9a-f]\{4\}-[0-9a-f]\{12\}" \
  --include="*.py" --include="*.csv" --include="*.md" \
  --exclude-dir=".git" .

# Buscar emails con dominios corporativos
grep -r "@grupoebi\." . --include="*.py" --include="*.csv" --include="*.md"

# Buscar RUTs (formato chileno)
grep -r "[0-9]\{7,8\}-[0-9kK]" . --include="*.py" --include="*.csv"
```
