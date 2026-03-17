# Workflow de Git — Checklist Obligatorio

**IMPORTANTE:** Este checklist DEBE ejecutarse ANTES de cualquier operación de git (commit, push, merge).

## Antes de `git commit`

**Rama correcta:**
- [ ] ¿Estoy en una rama `feature/*`, `bugfix/*`, o `hotfix/*`?
  - ✓ Correcto: `feature/add-comments`, `bugfix/fix-api-error`
  - ✗ Incorrecto: directamente en `develop` o `main`
  - **Comando:** `git branch --show-current`

**Código testeado:**
- [ ] ¿Ejecuté la suite de tests y todos pasan?
  - **Comando:** `pytest tests/ -v`
  - ✗ Nunca commitear con tests fallando

**Mensaje de commit:**
- [ ] ¿Sigue el patrón convencional?
  - `feat:` — feature nueva
  - `fix:` — bug fix
  - `refactor:` — cambio de código sin cambiar funcionalidad
  - `docs:` — solo documentación
  - `test:` — agregar/actualizar tests
  - `chore:` — tareas de mantenimiento
- [ ] ¿Primera línea ≤ 70 caracteres?
- [ ] ¿Incluye descripción detallada (qué, por qué)?

**Cambios en memoria:**
- [ ] ¿Hay cambios en Graph API o autenticación?
  - Sí → Actualizar `.claude/projects/*/memory/` con impacto
- [ ] ¿Hay errores que debo recordar para evitar repetirlos?
  - Sí → Crear/actualizar `feedback_*.md` en memory/

**Historial limpio:**
- [ ] ¿La rama diverge correctamente de `develop`?
  - **Comando:** `git log --oneline --graph develop..HEAD`
  - Debe mostrar solo mis commits, basado en un punto común en develop

---

## Antes de `git push`

**Rama remota:**
- [ ] ¿Esta rama va a empujar a una rama remota nueva o existente?
  - **Comando:** `git branch -vv`
  - Si es nueva: `git push -u origin feature/...`
  - Si existe: `git push origin feature/...`

**Cambios sincronizados:**
- [ ] ¿develop ha cambiado en origin desde que creé la rama?
  - **Comando:** `git fetch origin && git log --oneline origin/develop..develop`
  - Si hay cambios: considera `git rebase origin/develop` (si aún no hiciste PR)

---

## Antes de crear/mergear un PR

**Descripción del PR:**
- [ ] ¿Incluye título claro (<70 chars)?
- [ ] ¿Explica QUÉ cambia y POR QUÉ?
- [ ] ¿Referencia issues relacionados?
- [ ] ¿Incluye pasos de verificación (manual testing)?

**Rama base correcta:**
- [ ] ¿El PR apunta a `develop` o `main`?
  - ✓ Features → `develop`
  - ✓ Hotfixes → `main` (luego mergear de vuelta a develop)
  - ✗ Features a `main` directamente = ERROR CRÍTICO

**Tests y CI:**
- [ ] ¿Pasaron todos los tests en CI?
- [ ] ¿El linter pasó?

**Code review:**
- [ ] ¿Alguien aprobó el PR? (o es auto-merge del agente?)
- [ ] ¿Resolviste todos los comentarios?

---

## Antes de mergear a `develop` o `main`

**Último checklist:**
- [ ] ¿Puedo hacer fast-forward merge? (preferido)
  - **Comando:** `git merge --ff-only origin/feature/...`
- [ ] ¿O necesito merge commit? (OK si hay conflictos resueltos)
- [ ] ¿Todos los commits tienen buenos mensajes?
- [ ] ¿NO estoy forzando push a `develop` o `main`?
  - ✗ `git push --force` = NUNCA
  - ✗ `git reset --hard` en ramas compartidas = NUNCA

---

## Flujo completo (referencia visual)

```
1. Crear rama desde develop
   git checkout develop && git pull origin develop
   git checkout -b feature/my-feature

2. Hacer cambios + tests
   ... editar código ...
   pytest tests/ -v

3. Commitear (ejecutar checklist primero)
   ... revisar checklist arriba ...
   git add <archivos-específicos>
   git commit -m "feat: descripción clara"

4. Push a remote
   git push -u origin feature/my-feature

5. Crear PR en GitHub
   - Título claro, descripción detallada
   - Rama base: develop

6. Esperar aprobación/CI
   - Si falla: fix → commit → push
   - Si pasa: mergear

7. Mergear a develop (después de aprobación)
   git checkout develop
   git pull origin develop
   git merge --ff-only origin/feature/my-feature
   git push origin develop

8. Limpiar rama local/remota
   git branch -d feature/my-feature
   git push origin --delete feature/my-feature
```

---

## Errores históricos a evitar

1. **2026-02-26:** PR de feature mergeado a `main` saltando `develop`
   - **Causa:** No verificar ramas existentes antes de proponer rama base
   - **Solución:** SIEMPRE revisar estructura actual con `git branch -a` antes de crear PR

2. **Esta sesión:** Commit directo en `develop` sin crear feature branch
   - **Causa:** No ejecutar checklist pre-commit
   - **Solución:** Pre-commit hook + checklist deben consultarse siempre

---

## Automatización disponible

### Pre-commit hook (previene commits en develop/main)
```bash
# .git/hooks/pre-commit (ejecutado automáticamente)
BRANCH=$(git rev-parse --abbrev-ref HEAD)
if [[ "$BRANCH" == "main" || "$BRANCH" == "develop" ]]; then
    echo "❌ Error: No puedes commitear directamente en $BRANCH"
    echo "✓ Crea una rama feature/* primero"
    exit 1
fi
```

### Task tracking (Claude Code)
- Crear `TaskCreate` para cada feature/fix
- Marcar como `in_progress` antes de empezar
- Marcar como `completed` después de mergear PR

---

## Cuándo consultar este documento

**Antes de CUALQUIER operación:**
- `git commit` — checklist "Antes de git commit"
- `git push` — checklist "Antes de git push"
- Crear PR — checklist "Antes de crear/mergear PR"
- Mergear PR — checklist "Antes de mergear"

**Si tienes dudas:**
- ¿Qué rama debería usar? → Ver "Flujo completo"
- ¿Qué pasa si commiteo en develop? → Pre-commit hook lo previene
- ¿Cómo mergeo correctamente? → "Flujo completo" paso 7
