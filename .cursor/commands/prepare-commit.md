# Preparar commit limpio (L2)

Preparar un commit siguiendo el playbook L2 de AGENTS.md. **No hacer push**; nivel L2 (solo cambios locales).

## Pasos

1. **Revisar cambios:** ejecutar `git status` y `git diff` (o `git diff --staged` si ya hay staging). Resumir qué archivos y líneas cambian.

2. **Proponer mensaje de commit:** usar Conventional Commits si el repo lo adopta (`type(scope): descripción`). El mensaje debe describir con precisión el diff.

3. **Staging:** si conviene hacer staging parcial, usar `git add -p` para elegir hunks; si no, `git add <paths>`. No añadir archivos que no deban ir en este commit (secretos, temporales).

4. **Commit:** ejecutar `git commit -m "<mensaje>"` con el mensaje acordado.

5. **Verificación:** ejecutar `git show --stat HEAD` y `git status` para confirmar que el working tree queda limpio (o solo con los cambios que se quieran dejar para el siguiente commit).

## Recordatorio

- Nivel L2: no ejecutar `git push`.
- Antes de commitear, comprobar que no hay secretos en el diff.
- Si el repo define tests/linters, recordar ejecutarlos antes de dar por cerrada la tarea (el usuario puede pedirlo aparte).
