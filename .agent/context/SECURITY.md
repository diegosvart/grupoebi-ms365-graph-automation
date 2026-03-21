# Security Rules

## Secrets
- Never log, print, or commit `client_secret`, access tokens, refresh tokens, API keys, passwords, or session cookies
- Never store tokens or real secrets in repository documentation
- `.env` files stay out of version control; use `.env.example` as the public template
- Treat any discovered secret in docs or diffs as a stop condition and raise it immediately

## Graph Operational Safety
- Use the minimum Microsoft Graph permissions required for each flow
- Handle `429 Too Many Requests` with `Retry-After`
- Handle pagination via `@odata.nextLink`
- Fetch ETag before PATCH on Planner `details` endpoints
- Keep explicit `httpx` timeouts; do not rely on implicit defaults

## Local Files
- Do not create `.pem`, `.pfx`, `.key`, or equivalent secret-bearing files in this repo
- Do not commit machine-specific config such as `.claude/settings.local.json` or `.cursor/mcp.json`
- Keep local-only automation outside the canonical `.agent/` layer

## Documentation Hygiene
- Do not copy host-specific absolute paths into shared context unless strictly required
- If a file is known to contain secrets, summarize its purpose without reproducing secret values
- Prefer references to source docs over duplicating large blocks of content
