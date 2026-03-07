# Pull Request

## Summary

<!-- Brief description of what this PR does and why. -->

## Type of change

- [ ] Bug fix
- [ ] New feature
- [ ] Documentation update
- [ ] Refactor
- [ ] Security improvement
- [ ] Dependency update

## Related issue

Closes # <!-- issue number -->

---

## Checklist

### Functionality
- [ ] `pytest` passes with no failures (`pytest`)
- [ ] New functionality has test coverage
- [ ] `--dry-run` mode works without API credentials for all modified flows
- [ ] Existing `--dry-run` behavior is unchanged

### Security (required for all PRs)
- [ ] No real credentials, tokens, or secrets in code or documentation
- [ ] No hardcoded GUIDs from production (group IDs, plan IDs, user IDs, tenant IDs)
- [ ] No real employee emails, names, or RUTs in code, templates, or fixtures
- [ ] Test fixtures use fictional data only (`tests/fixtures/`)
- [ ] `.env.example` contains only placeholders, no real values

### Graph API permissions
- [ ] Any new Graph API endpoint is documented in `docs/API_REFERENCIA.md`
- [ ] Any new permission required is documented in `SECURITY.md` and `README.md`
- [ ] Throttling (HTTP 429) is handled by the existing `graph_request()` — no custom retry logic added

### Documentation
- [ ] Relevant guide in `docs/guias/` is created or updated
- [ ] Relevant integration doc in `docs/integraciones/` is created or updated
- [ ] `CHANGELOG.md` updated under `[Unreleased]`

### Required reviews (check applicable)
- [ ] **Security lead review required** — this PR modifies: `hooks/`, `SECURITY.md`, `.env.example`, or authentication logic
- [ ] **Standard review** — no security-sensitive files modified

---

## Testing done

<!-- Describe what you tested, including dry-run verification. -->

### Dry-run output

```
# Paste the --dry-run output here to confirm expected behavior
```

### Test environment

- [ ] Tested against development tenant (not production)
- [ ] Tested on Windows
- [ ] Tested on Linux/macOS
