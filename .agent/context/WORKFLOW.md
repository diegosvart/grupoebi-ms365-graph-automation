# Workflow Rules

## Branching
- Create short-lived branches: `feature/*`, `fix/*`, `chore/*`
- Base feature work on `develop`, never directly on `main`
- Do not merge features into `main` directly

## Git Safety
- Default posture is read-only unless the task explicitly requires local changes
- Never use `git push --force` or published-history rewrites without explicit approval
- Prefer `git revert` over destructive rollback on shared branches

## Before Commit
- Confirm the current branch is not `develop` or `main`
- Review the diff and stage intentionally
- Run relevant tests and checks when the repo defines them
- Use a clear conventional commit message

## Before Push or PR
- Verify the upstream branch and remote target
- Confirm the PR base branch is `develop` unless it is a true hotfix
- Include change context, verification steps, and rollback notes

## Verification
- Prefer `--dry-run` before real Planner mutations when supported
- After code changes, run the narrowest useful verification first, then broader tests if needed
- Review Graph-facing changes with extra rigor around permissions, retries, pagination, ETags, and timeouts

## Cross-IDE Session Handling
- At session start, read `.agent/context/PROJECT.md` and `.agent/memory/current-session.json`
- During substantial work, keep `completed`, `pending`, and `next_step` up to date
- On session end or handoff, save a checkpoint in `.agent/memory/checkpoints/`

## Destructive Actions
- Never reset, force-push, or remove history without explicit approval
- Never print or paste secrets into terminals, PRs, or docs
