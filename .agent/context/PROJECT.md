# Project Context

## Stack
Python 3.14, `httpx`, Microsoft Graph API, `fornado-planner-mcp`

## Purpose
This repository automates Microsoft 365 project operations around Planner.
The current implemented core is `planner_import.py`, a CLI that imports tasks from CSV into Microsoft Planner and generates operational reports.

## Current Capabilities
- Import a full plan from CSV: plan, labels, buckets, tasks
- Create only plan headers, buckets, or tasks on existing plans
- List and delete plans
- Export task reports to CSV
- Generate and send HTML email reports
- Inspect SharePoint library contents

## Key Commands
- `python planner_import.py --dry-run`
- `python planner_import.py`
- `python planner_import.py --mode plan --csv <path> --group-id <guid>`
- `python planner_import.py --mode buckets --csv <path>`
- `python planner_import.py --mode tasks --csv <path>`
- `python planner_import.py --mode list --filter <text>`
- `python planner_import.py --mode report --export <path>`
- `python planner_import.py --mode email-report --preview`
- `pytest -v`

## Architecture
- Main entrypoint: `planner_import.py`
- Auth and settings come from the external MCP project
- Graph HTTP orchestration currently lives in `graph_request()` and related helpers in `planner_import.py`
- Operational and future architecture references live in `docs/` and `plans/`

## External Dependencies
- Microsoft Graph API
- Microsoft Entra app registration with the required permissions
- Corporate network/VPN connectivity
- External `.env` managed by `fornado-planner-mcp`

## Operating Principles
- Planner is the operational source of truth
- Teams is the formal communication channel
- SharePoint stores project artifacts and shared help material
- Dry runs must work without Graph credentials

## Non-Negotiable Rules
1. Never log or commit secrets, tokens, or client credentials.
2. Respect Graph throttling and `Retry-After`.
3. Obtain ETag before PATCH on Planner details endpoints.
4. Keep the cross-IDE canonical context in `.agent/`.

## Learned Constraints
- The repo contains current functionality and future-state design; implementation work must distinguish both.
- Branch policy is `feature/* -> develop -> main`.
- Some historical project docs contain exposed secrets and must be treated as contaminated until remediated.
