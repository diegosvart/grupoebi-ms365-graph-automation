# Microsoft Graph Guidance

## Current Graph Pattern
- Base URL: `https://graph.microsoft.com/v1.0`
- Current repository usage centers on Planner, Groups, Users, Mail, and SharePoint listing
- The current script relies on a reusable request helper pattern that should remain the foundation for future modularization

## Core Rules
- Use explicit timeouts in `httpx.AsyncClient`
- Respect `Retry-After` on throttling responses
- Iterate through paginated responses using `@odata.nextLink`
- Fetch ETag before PATCH on Planner details
- Do not implement manual token storage; rely on MSAL and the MCP auth layer

## Planner-Specific Expectations
- `create_plan` must send `owner` and `title`
- Label configuration requires GET details then PATCH with ETag
- Full task creation currently follows POST task -> GET details -> PATCH details
- `appliedCategories` must use `category1`..`category6`
- Checklist items require stable keys, `isChecked`, and `orderHint`

## Permissions Discipline
- Document the minimum permission required by each new Graph-facing function
- Prefer app permissions only when the workflow truly requires them
- Re-check permissions before implementing new Outlook, SharePoint, or Teams flows

## When to Review Graph Changes More Rigorously
- Changes to auth, token acquisition, or scope selection
- Changes to retry, throttling, timeout, or pagination behavior
- New Planner mutations or bulk update flows
- Any move toward Teams, OneDrive, Calendar, or webhook integrations

## Future Direction
- The intended architecture is a reusable Graph client plus token provider, with domain modules for Planner and future Microsoft 365 surfaces
- Planner remains the first-class domain, but the same patterns should support SharePoint, Calendar, Users, and group automation
