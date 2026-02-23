# Abrir PR (L3)

Hacer push de la rama actual y abrir un Pull Request (o Merge Request) hacia la rama base (p. ej. `main`). **Solo si el usuario autoriza L3**; no mergear a rama protegida.

## Pasos

1. **Confirmar rama base:** comprobar la rama objetivo del PR (normalmente `main` o `master`). Ejecutar `git branch --show-current` y `git remote -v` si hace falta.

2. **Push con upstream:** ejecutar `git push -u origin <rama-actual>` para subir la rama y configurar el tracking. No usar `--force` ni `--force-with-lease` salvo aprobación explícita.

3. **Abrir PR/MR:** si está configurado GitHub CLI: `gh pr create` (con opciones como `--base main`, `--title`, `--body`). En GitLab: `glab mr create`. Incluir en la descripción:
   - Título claro del cambio
   - Descripción del "por qué" y "qué"
   - Checklist de verificación (tests, revisión, etc.)
   - Notas de riesgos o rollback si aplica

4. **Dejar enlace y resumen:** devolver la URL del PR/MR creado y un resumen de lo subido.

5. **Recomendar método de merge:** según la política del repo (historial lineal → squash o rebase merge; si no está definida, proponer squash por defecto).

## Recordatorio

- Nivel L3: requiere autorización del usuario para push y creación de PR.
- No mergear a la rama principal desde el agente; solo crear el PR y solicitar revisión humana.
- No incluir tokens ni secretos en el título o cuerpo del PR.
