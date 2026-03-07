# Contributing Guide

## Development Setup

### Prerequisites

- Python 3.10+
- Git
- Access to the development Azure tenant (contact the repository maintainer)

### Local Setup

```bash
# 1. Clone the repository
git clone https://github.com/diegosvart/grupoebi-ms365-graph-automation.git
cd grupoebi-ms365-graph-automation

# 2. Create virtual environment
python -m venv .venv
source .venv/bin/activate        # Linux/macOS
.\.venv\Scripts\activate         # Windows

# 3. Install dependencies (including dev dependencies)
pip install -r requirements.txt
pip install -r requirements-dev.txt   # pytest, pytest-mock, pytest-cov, ruff

# 4. Configure environment
cp .env.example .env
# Edit .env with development tenant credentials (NOT production)
```

### Environment Variables for Development

Use the development tenant credentials, not production. Request access from the repository maintainer. See `.env.example` for all required variables.

---

## Workflow

### 1. Create a branch

```bash
git checkout -b feat/nombre-descriptivo        # nueva funcionalidad
git checkout -b fix/descripcion-del-bug        # correccion de bug
git checkout -b docs/descripcion-del-cambio    # solo documentacion
```

### 2. Develop and test

```bash
# Run all tests before committing
pytest

# Run with coverage
pytest --cov=. --cov-report=term-missing

# Lint
ruff check .
ruff format .
```

### 3. Commit with conventional messages

```bash
git commit -m "feat: agregar soporte para cambio de rol via Graph API"
```

| Prefix | Use |
|---|---|
| `feat:` | New functionality |
| `fix:` | Bug fix |
| `docs:` | Documentation changes only |
| `test:` | Add or modify tests |
| `refactor:` | Code change without bug fix or new feature |
| `chore:` | Maintenance tasks (dependencies, config) |
| `security:` | Security improvements or fixes |

### 4. Open a Pull Request

```bash
git push origin feat/nombre-descriptivo
# Then open a PR on GitHub toward main
```

---

## Code Conventions

### Python Style

- **Formatter:** `ruff format` (Black-compatible, 88 characters line length)
- **Linter:** `ruff check` with rules: E, W, F, I (isort), UP (pyupgrade)
- **Type hints:** Required for all public functions
- **Docstrings:** Required for public functions and classes (Google style)

### Security Conventions

- **Never hardcode credentials** — all sensitive values must come from environment variables.
- **Never commit real GUIDs** from production (group IDs, plan IDs, user IDs).
- **Use placeholder values** in examples and documentation: `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`.
- **Test data must be fictional** — no real employee names, emails, or RUTs in `tests/fixtures/`.
- Run `hooks/guard-sensitive.py` before committing if you modified files that touch credentials.

### CSV Templates

- Use `;` as delimiter (not comma)
- Use `DDMMYYYY` format for dates
- Use placeholder emails: `pm@empresa.com`, `usuario@empresa.com`
- Never include real employee data

---

## Pull Request Requirements

All PRs must pass the checklist in `.github/PULL_REQUEST_TEMPLATE.md`:

- [ ] `pytest` passes with no failures
- [ ] New functionality has test coverage
- [ ] `--dry-run` mode works without credentials
- [ ] No real credentials, GUIDs, or emails in the code or docs
- [ ] CSV templates in `templates/` reflect new behavior if applicable
- [ ] Documentation updated (`docs/` or relevant `.md` files)

### Required Reviewers

PRs that modify the following files require review from the security lead (see `.github/CODEOWNERS`):

- `hooks/`
- `SECURITY.md`
- `.env.example`
- Any file containing Graph API authentication logic

---

## Testing Requirements

See [docs/TESTING.md](docs/TESTING.md) for the full testing strategy.

**Summary:**
- Unit tests: mock all HTTP calls, no network required
- Integration tests: use development tenant, marked with `@pytest.mark.integration`
- Minimum coverage: 80% on business logic modules
- All test fixtures must use fictional data

---

## Reporting Issues

- **Bugs:** Use the [bug report template](.github/ISSUE_TEMPLATE/bug_report.yml)
- **Feature requests:** Use the [feature request template](.github/ISSUE_TEMPLATE/feature_request.yml)
- **Workflow requests (non-technical users):** Use the [workflow request template](.github/ISSUE_TEMPLATE/workflow_request.yml)
- **Security vulnerabilities:** See [SECURITY.md](SECURITY.md) — do NOT open public issues
