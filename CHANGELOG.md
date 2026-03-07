# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [Unreleased]

### Added
- Complete documentation suite (25 files): architecture, role profiles catalog, user guides, integration docs, GitHub templates
- `SECURITY.md`: security policy, App Registration permissions, secret rotation procedures
- `docs/PERFILES_ROLES.md`: role profile catalog mapping cargo → M365 licenses + security groups + Teams channels + apps
- `docs/ARQUITECTURA.md`: full system diagram, auth flow, module descriptions
- `docs/guias/ALTA_USUARIO.md`: user onboarding guide (Talana webhook + manual flow)
- `docs/guias/BAJA_USUARIO.md`: user offboarding guide with IT escalation for deletion
- `docs/guias/CAMBIO_ROL.md`: role change guide with dual-manager authorization
- `docs/guias/NUEVO_PROYECTO.md`: new project environment guide
- `docs/guias/IMPORTAR_TAREAS.md`: Planner CSV import guide with all modes
- `docs/guias/INCORPORACION_PROYECTO.md`: project member addition guide
- `docs/guias/INICIO_RAPIDO.md`: quick start guide for all audiences
- `docs/integraciones/ENTRA_ID.md`: Azure Entra ID integration reference
- `docs/integraciones/TALANA.md`: Talana HRIS integration (webhook-first + polling fallback)
- `docs/integraciones/EXCHANGE_ONLINE.md`: Exchange Online integration
- `docs/integraciones/TEAMS.md`: Microsoft Teams integration
- `docs/integraciones/SHAREPOINT.md`: SharePoint Online integration
- `docs/integraciones/INTUNE.md`: Microsoft Intune integration (future implementation)
- `docs/integraciones/POWER_AUTOMATE.md`: Power Automate wrapper for non-technical users
- `docs/API_REFERENCIA.md`: complete Graph API endpoint reference
- `docs/TESTING.md`: testing strategy and conventions
- `docs/GLOSARIO.md`: bilingual glossary (M365 + Talana + technical terms)
- `.env.example`: expanded with all variables (Entra ID, Talana, Azure Functions, Intune)
- `CONTRIBUTING.md`: development setup, code conventions, PR requirements
- `.github/PULL_REQUEST_TEMPLATE.md`: PR checklist with security and dry-run gates
- `.github/CODEOWNERS`: reviewer assignments by area
- `.github/ISSUE_TEMPLATE/bug_report.yml`: structured bug report
- `.github/ISSUE_TEMPLATE/feature_request.yml`: feature request with business justification
- `.github/ISSUE_TEMPLATE/workflow_request.yml`: non-technical workflow request form
- `.gitignore`: comprehensive exclusion of unrelated project directories and secrets

---

## [0.1.0] — 2026-01-15

### Added
- `planner_import.py`: CLI for CSV → Planner import with modes: `full`, `plan`, `buckets`, `tasks`, `list`, `delete`
- `create_environment.py`: orchestrator for complete project environment (Teams channel + Planner + SharePoint)
- `MicrosoftAuthManager`: Client Credentials Flow token management with automatic renewal
- `graph_request()`: central HTTP client with throttling (HTTP 429) and retry support
- `resolve_email()`: email → Entra ID GUID resolution with in-memory cache
- `parse_csv()`: CSV parser and validator (`;` delimiter, `DDMMYYYY` dates, priority normalization)
- SharePoint folder structure creation and template file upload
- Teams channel creation with owner/member assignment
- Planner tab pinning in Teams channel
- `--dry-run` mode for all write operations
- `hooks/guard-sensitive.py`: pre-session hook to detect secret exposure
- `templates/default_init/`: default project templates (CSV + Word documents)
- `tests/`: unit test suite with pytest

### Permissions (App Registration)
- `Tasks.ReadWrite`, `Tasks.ReadWrite.Shared`
- `Group.ReadWrite.All`, `User.Read.All`
- `Team.ReadBasic.All`, `Channel.Create`, `TeamMember.ReadWrite.All`
- `Sites.ReadWrite.All`, `Files.ReadWrite.All`

---

[Unreleased]: https://github.com/diegosvart/grupoebi-ms365-graph-automation/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/diegosvart/grupoebi-ms365-graph-automation/releases/tag/v0.1.0
