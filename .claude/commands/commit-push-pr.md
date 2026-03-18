# Slash Command: `/commit-push-pr`

Automatiza el flujo completo: **commit → push → pull request** en un solo comando.

## Invocación

```bash
/commit-push-pr                                    # Flujo interactivo completo
/commit-push-pr "feat: descripción del cambio"   # Con mensaje predefinido
```

## Flujo de ejecución

### 1. Validación previa

- [ ] Ejecutar `git status` — verificar si hay cambios
- [ ] Si el working tree está limpio: **detener y notificar**
  ```
  ⚠️  No hay cambios. Working tree limpio.
  Nada que commitear.
  ```
- [ ] Detectar branch actual: `git rev-parse --abbrev-ref HEAD`
- [ ] Detectar branch base (main/master/develop): `git rev-parse --abbrev-ref origin/HEAD` o inspeccionar HEAD remoto
- [ ] **Regla de protección**: Si branch es `main`, `master` o `develop` → **ADVERTENCIA CRÍTICA**
  ```
  ⚠️  ADVERTENCIA: Estás en rama protegida: {branch}

  Regla del proyecto: cambios en {branch} requieren PR aprobada desde feature/*.
  ¿Deseas continuar? (s/n)
  ```

---

### 2. Staging inteligente

- [ ] Ejecutar `git diff --staged` y `git diff` para entender estado
- [ ] Si hay archivos unstaged:
  ```
  📋 Estado actual:

  Staged:    {num} archivo(s)
  Unstaged:  {num} archivo(s)

  Opciones:
  1. Agregar todos los cambios (git add .)
  2. Seleccionar archivos específicos (git add <archivos>)
  3. Commitear solo staged
  4. Cancelar
  ```
- [ ] Mostrar resumen visual:
  ```
  ✅ Cambios a commitear:
  - planner_import.py (M)
  - tests/test_graph_api.py (A, M)
  - docs/RUNBOOK.md (M)
  ```

---

### 3. Generación del commit message

#### 3a. Inferir tipo de commit (Conventional Commits)

Analizar archivos modificados y contenido para determinar:

| Tipo | Detectar si... | Scope sugerido |
|------|---|---|
| **feat** | Nuevo código, nuevas funciones | Nombre del módulo/función |
| **fix** | Bug fixes, correcciones | Nombre del bug/función |
| **docs** | Solo cambios en .md, comentarios | docs/ |
| **style** | Formato, whitespace, imports | Archivo principal |
| **refactor** | Reorganización sin cambios funcionales | Módulo refactorizado |
| **test** | Nuevos tests, modificación de tests | test-type |
| **chore** | Dependencies, versiones, configs | package.json, .env.example |
| **ci** | GitHub Actions, .github/, Makefile | ci-service |

**Reglas de inferencia:**
1. Si solo archivos en `tests/` → type = `test`
2. Si solo archivos `.md` → type = `docs`
3. Si archivos en `src/` o `planner_import.py` → type = `feat` o `fix` (ver contenido)
4. Si hay cambios en `requirements.txt` → type = `chore`

#### 3b. Generar descripción

Analizar el diff más significativo y generar descripción en presente: `"agregar XYZ"`, `"corregir XYZ"`

#### 3c. Presentar al usuario

```
📝 Commit message propuesto:

  {type}({scope}): {description}

  Editar:
  1. Aceptar (Enter)
  2. Editar título
  3. Agregar body (descripción larga)
  4. Cancelar
```

- Si usuario elige "Editar" → mostrar editor o campo de entrada
- Si usuario pasa mensaje como argumento (`$ARGUMENTS`) → usar ese directamente (sin preguntar)

#### 3d. Ejecutar commit

```bash
git commit -m "{mensaje_final}"
```

Capturar hash: `git rev-parse --short HEAD`

---

### 4. Push

- [ ] Detectar upstream: `git rev-parse --abbrev-ref --symbolic-full-name @{u}`
- [ ] Si NO tiene upstream:
  ```
  🔗 Branch sin upstream.

  Ejecutando: git push --set-upstream origin {branch}
  ```
  ```bash
  git push --set-upstream origin {branch}
  ```
- [ ] Si YA tiene upstream:
  ```bash
  git push
  ```

**Manejo de errores comunes:**

| Error | Acción |
|-------|--------|
| `fatal: 'origin' does not appear to be a git repository` | Verificar `.git/config` |
| `Permission denied (publickey)` | Sugerir autenticación SSH |
| `rejected (non-fast-forward)` | Sugerir `git pull --rebase` y reintentar |
| `fatal: The current branch ... has no upstream branch` | Reintentar push con `-u origin` |

---

### 5. Creación del Pull Request

#### 5a. Detectar proveedor remoto

```bash
git config --get remote.origin.url  # ej: https://github.com/user/repo.git
```

Parsear URL para determinar:
- GitHub: `github.com/user/repo`
- GitLab: `gitlab.com/user/repo`
- Azure DevOps: `dev.azure.com/...`

#### 5b. Crear PR (GitHub con `gh`)

**Verificar disponibilidad:**
```bash
which gh  # ¿está instalado?
```

**Si SÍ está disponible:**

1. Detectar branch base:
   ```bash
   git rev-parse --abbrev-ref origin/HEAD  # origin/main, origin/develop, etc.
   ```

2. Preparar título y descripción:
   - **Title**: `{type}({scope}): {description}` (del commit message)
   - **Body**: template Markdown
   - **Base**: detectado automáticamente
   - **Labels**: mapear desde type
     - `feat` → `enhancement`
     - `fix` → `bug`
     - `docs` → `documentation`
     - `test` → `testing`

3. Crear PR:
   ```bash
   gh pr create --title "{title}" --body "{body}" --base {base_branch} --label "{labels}"
   ```

4. Capturar URL del PR creado:
   ```bash
   gh pr view --json url --jq .url
   ```

#### 5c. Fallback: URL manual para GitHub

Si `gh` no está disponible o falla:

```
🔗 GitHub CLI no disponible.
   Abre manualmente:

   https://github.com/{owner}/{repo}/pull/new/{branch}?...

   Título sugerido:
   {type}({scope}): {description}

   Descripción sugerida:
   ## Descripción
   {descripción del cambio}

   ## Cambios
   - {lista de cambios}

   ## Testing
   - [ ] Tests unitarios pasan
   - [ ] Revisión manual completada
```

#### 5d. Mensaje de éxito

```
✅ Pull Request creado exitosamente

  Title:  {type}({scope}): {description}
  Branch: {branch} → {base_branch}
  URL:    {pr_url}
```

---

### 6. Resumen final

Mostrar:
```
═══════════════════════════════════════════════════════════
✅ FLUJO COMPLETADO EXITOSAMENTE

📋 Commit
   Hash:    {hash}
   Message: {type}({scope}): {description}

🚀 Push
   Branch:  {branch} → origin
   Status:  ✓ Pusheado

🔗 Pull Request
   URL:     {pr_url}
   Base:    {base_branch}
   Title:   {type}({scope}): {description}

═══════════════════════════════════════════════════════════

💡 Próximos pasos:
   1. Revisar el PR en GitHub: {pr_url}
   2. Solicitar review a compañeros
   3. Mergear cuando esté aprobado
```

---

## Validaciones y reglas

### Reglas del proyecto (verificar contra CLAUDE.md)

- ✅ No permitir commits directos en `main`, `master`, `develop`
  - **Acción**: Advertencia y confirmación explícita requerida
  - **Referencia**: `.claude/rules/version-control.mdc`, MEMORY.md "Flujo de ramas"

- ✅ Seguir Conventional Commits (`type(scope): description`)
  - **Acción**: Validar formato antes de permitir commit
  - **Referencia**: CLAUDE.md "Convención CSV1", feedback de commits

- ✅ No commitear credenciales (`.env`, `credentials.json`, `.pem`, `.pfx`)
  - **Acción**: Advertencia si se detectan archivos sensibles
  - **Referencia**: `.claude/rules/security.md`

- ✅ Verificar que no hay `TODO` sin resolver o archivos en conflicto
  - **Acción**: Alertar antes de push si se detectan conflictos

---

## Manejo de errores completo

| Escenario | Error esperado | Acción |
|-----------|---|---|
| Working tree limpio | N/A | Detener, mostrar mensaje |
| Branch es main/develop | N/A | Advertencia, pedir confirmación |
| Archivos sin staging | N/A | Ofrecer opciones de staging |
| Commit message vacío | N/A | Rechazar, pedir descripción |
| Push rechazado (non-fast-forward) | `rejected` | Sugerir `git pull --rebase` |
| Autenticación fallida | `Permission denied` | Verificar credenciales SSH/token |
| Branch sin upstream | `fatal: The current branch...` | Crear upstream automáticamente |
| `gh` no disponible | Command not found | Usar fallback de URL manual |
| PR creation falla | `gh pr create` error | Mostrar URL manual y error específico |
| Network error durante push | `connection timeout` | Reintentar o mostrar error |

---

## Argumentos del comando

```
$ARGUMENTS — contiene el mensaje de commit si se pasa manualmente

Ejemplos:
  /commit-push-pr                                    # Interactivo completo
  /commit-push-pr "fix: corregir validación"       # Con mensaje directo
  /commit-push-pr "feat(auth): agregar SSO"        # Con scope
```

Si `$ARGUMENTS` no está vacío:
- Validar formato (¿contiene `:`?)
- Si es válido → usar como commit message (skip generación automática)
- Si es inválido → pedir confirmación al usuario

---

## Implementación técnica (para Claude Code)

### Pseudocódigo

```
FUNCIÓN commit_push_pr(arguments: str):
  // 1. Validación previa
  git_status = ejecutar("git status")
  IF clean(git_status):
    PRINT "⚠️  Working tree limpio"
    RETURN
  END IF

  current_branch = ejecutar("git rev-parse --abbrev-ref HEAD")
  base_branch = detectar_base_branch()

  IF current_branch EN [main, master, develop]:
    PRINT "⚠️  ADVERTENCIA: Branch protegido"
    IF NO confirmar("¿Continuar?"):
      RETURN
    END IF
  END IF

  // 2. Staging
  staged = ejecutar("git diff --staged")
  unstaged = ejecutar("git diff")
  IF unstaged:
    opción = preguntar("¿Agregar todos los cambios?")
    IF opción == "sí":
      ejecutar("git add .")
    END IF
  END IF

  // 3. Commit message
  IF arguments NOT empty:
    msg = arguments
  ELSE:
    type = inferir_tipo(cambios)
    scope = inferir_scope(cambios)
    description = inferir_descripción(cambios)
    msg = "{type}({scope}): {description}"
    msg = confirmar_editar(msg)
  END IF

  hash = ejecutar("git commit -m '{msg}'")

  // 4. Push
  upstream = ejecutar("git rev-parse --abbrev-ref @{u}")
  IF NO upstream:
    ejecutar("git push --set-upstream origin {current_branch}")
  ELSE:
    ejecutar("git push")
  END IF

  // 5. PR
  provider = detectar_provider(remote_url)
  IF provider == "github":
    IF gh_disponible():
      pr_url = crear_pr_gh(...)
    ELSE:
      PRINT fallback_url(...)
    END IF
  END IF

  // 6. Resumen
  PRINT resumen_final(hash, msg, pr_url)
FIN FUNCIÓN
```

### Herramientas a usar

- **Bash tool**: para ejecutar comandos git
- **AskUserQuestion**: para confirmaciones y selecciones
- **Read tool**: para leer archivos de configuración (.git/config, CLAUDE.md)
- **Grep tool**: para detectar archivos sensibles (`.env`, `.pem`, etc.)

---

## Integración con reglas existentes

Este comando **respeta y refuerza**:

1. **Convención de ramas** (MEMORY.md):
   - ✅ No permite commits directos en `main`/`develop`
   - ✅ Crea PRs hacia `develop` (no `main`)

2. **Seguridad** (.claude/rules/security.md):
   - ✅ Advierte sobre credenciales en staging
   - ✅ No incluye `client_secret`, `access_token` en commits

3. **Git workflow** (.claude/workflows/git-workflow.md):
   - ✅ Ejecuta pre-commit hooks si existen
   - ✅ Valida Conventional Commits format
   - ✅ Muestra grafo de ramas después de push

---

## Referencias

- **Git workflow enforcement**: `.claude/workflows/git-workflow.md`
- **Security rules**: `.claude/rules/security.md`
- **Version control rules**: `.claude/rules/version-control.mdc` (si existe)
- **GitHub project integration**: CLAUDE.md "GitHub Project — Gestión de tareas"
- **Memory de proyecto**: `.claude/projects/*/memory/MEMORY.md`
