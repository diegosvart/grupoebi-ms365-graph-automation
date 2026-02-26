# Visualización del repo tras operaciones git

## Regla

Después de cada operación que suba cambios al remoto (push, merge, PR) mostrar
siempre el grafo de ramas con:

```bash
git log --graph --oneline --all --decorate --color
```

Esto da una vista rápida del estado de branches en terminal mientras el usuario
abre **Git Graph** en VS Code (extensión recomendada: `mhutchie.git-graph`).

## Cuándo ejecutar

| Operación | Mostrar grafo |
|-----------|---------------|
| `git push` | Sí |
| `git merge` | Sí |
| PR mergeado | Sí |
| `git pull` exitoso | Sí |
| `git commit` local (sin push) | No |

## Apertura de Git Graph en VS Code

Git Graph no puede lanzarse desde CLI. Recordar al usuario:
> "Abre Git Graph en VS Code (Ctrl+Shift+P → 'Git Graph: View Git Graph')"
