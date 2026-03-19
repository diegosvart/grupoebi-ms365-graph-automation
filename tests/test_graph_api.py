"""Tests de graph_request, list_plans, delete_plan, create_plan, create_bucket,
resolve_email_to_guid, create_task_full, get_task_details, _print_report_table,
run_report — sin red real."""
from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, call, patch

import httpx
import pytest

import planner_import
from planner_import import (
    GRAPH_BASE,
    _build_outlook_bar_fallback,
    _derive_task_status,
    _parse_due,
    _print_kpi_block,
    _print_report_table,
    build_report_html,
    create_bucket,
    create_plan,
    create_task_full,
    delete_plan,
    get_last_comment,
    get_task_details,
    graph_request,
    list_buckets,
    list_plans,
    list_tasks,
    resolve_email_to_guid,
    resolve_guid_to_email,
    run_report,
    send_mail_report,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_response(status_code: int, json_data=None, headers=None) -> MagicMock:
    """Construye un mock de httpx.Response."""
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.headers = httpx.Headers(headers or {})
    if json_data is not None:
        resp.json.return_value = json_data
    if status_code >= 400:
        resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "error", request=MagicMock(), response=resp
        )
    else:
        resp.raise_for_status.return_value = None
    return resp


async def _make_client(responses: list) -> MagicMock:
    """Mock de httpx.AsyncClient con múltiples respuestas secuenciales."""
    client = MagicMock(spec=httpx.AsyncClient)
    client.request = AsyncMock(side_effect=responses)
    return client


# ── graph_request básico ──────────────────────────────────────────────────────

class TestGraphRequestBasic:
    async def test_get_200_returns_json(self, fake_token):
        client = await _make_client([_make_response(200, {"id": "abc"})])
        result = await graph_request(client, "GET", "/planner/plans", fake_token)
        assert result == {"id": "abc"}

    async def test_204_returns_none(self, fake_token):
        client = await _make_client([_make_response(204)])
        result = await graph_request(client, "DELETE", "/planner/plans/x", fake_token)
        assert result is None

    async def test_202_empty_body_returns_none(self, fake_token):
        """POST que retorna 202 con body vacío (ej: sendMail) debe retornar None sin error."""
        resp = _make_response(202)
        resp.content = b""  # simula body vacío
        client = await _make_client([resp])
        result = await graph_request(client, "POST", "/users/x@test.com/sendMail", fake_token)
        assert result is None

    async def test_etag_adds_if_match_header(self, fake_token):
        client = await _make_client([_make_response(200, {})])
        await graph_request(
            client, "PATCH", "/planner/tasks/x/details", fake_token, etag='W/"abc"'
        )
        _, kwargs = client.request.call_args
        assert kwargs["headers"]["If-Match"] == 'W/"abc"'

    async def test_authorization_header_present(self, fake_token):
        client = await _make_client([_make_response(200, {})])
        await graph_request(client, "GET", "/planner/plans", fake_token)
        _, kwargs = client.request.call_args
        assert kwargs["headers"]["Authorization"] == f"Bearer {fake_token}"

    async def test_url_prefixed_with_graph_base(self, fake_token):
        client = await _make_client([_make_response(200, {})])
        await graph_request(client, "GET", "/planner/plans", fake_token)
        args, _ = client.request.call_args
        assert args[1].startswith(GRAPH_BASE)

    async def test_404_raises_http_status_error(self, fake_token):
        client = await _make_client([_make_response(404)])
        with pytest.raises(httpx.HTTPStatusError):
            await graph_request(client, "GET", "/planner/plans/nope", fake_token)

    async def test_json_payload_forwarded(self, fake_token):
        client = await _make_client([_make_response(201, {"id": "new"})])
        payload = {"title": "Mi Plan", "owner": "group-id"}
        await graph_request(client, "POST", "/planner/plans", fake_token, json=payload)
        _, kwargs = client.request.call_args
        assert kwargs["json"] == payload

    async def test_no_etag_no_if_match_header(self, fake_token):
        client = await _make_client([_make_response(200, {})])
        await graph_request(client, "GET", "/planner/plans", fake_token)
        _, kwargs = client.request.call_args
        assert "If-Match" not in kwargs["headers"]


# ── graph_request retry 429 ───────────────────────────────────────────────────

class TestGraphRequestRetry:
    async def test_429_then_200_returns_json(self, fake_token):
        resp_429 = _make_response(429, headers={"Retry-After": "1"})
        resp_200 = _make_response(200, {"value": "ok"})
        client = await _make_client([resp_429, resp_200])

        with patch.object(planner_import.asyncio, "sleep", new_callable=AsyncMock) as mock_sleep:
            result = await graph_request(client, "GET", "/planner/plans", fake_token)

        assert result == {"value": "ok"}
        mock_sleep.assert_called_once_with(1)

    async def test_uses_retry_after_header(self, fake_token):
        resp_429 = _make_response(429, headers={"Retry-After": "42"})
        resp_200 = _make_response(200, {})
        client = await _make_client([resp_429, resp_200])

        with patch.object(planner_import.asyncio, "sleep", new_callable=AsyncMock) as mock_sleep:
            await graph_request(client, "GET", "/planner/plans", fake_token)

        mock_sleep.assert_called_once_with(42)

    async def test_no_retry_after_sleeps_60(self, fake_token):
        resp_429 = _make_response(429)
        resp_200 = _make_response(200, {})
        client = await _make_client([resp_429, resp_200])

        with patch.object(planner_import.asyncio, "sleep", new_callable=AsyncMock) as mock_sleep:
            await graph_request(client, "GET", "/planner/plans", fake_token)

        mock_sleep.assert_called_once_with(60)

    async def test_three_consecutive_429_raises_runtime_error(self, fake_token):
        resp_429 = _make_response(429, headers={"Retry-After": "1"})
        client = await _make_client([resp_429, resp_429, resp_429])

        with patch.object(planner_import.asyncio, "sleep", new_callable=AsyncMock):
            with pytest.raises(RuntimeError, match="reintentos"):
                await graph_request(client, "GET", "/planner/plans", fake_token)

    async def test_three_429_client_called_three_times(self, fake_token):
        resp_429 = _make_response(429, headers={"Retry-After": "1"})
        client = await _make_client([resp_429, resp_429, resp_429])

        with patch.object(planner_import.asyncio, "sleep", new_callable=AsyncMock):
            with pytest.raises(RuntimeError):
                await graph_request(client, "GET", "/planner/plans", fake_token)

        assert client.request.call_count == 3


# ── list_plans ────────────────────────────────────────────────────────────────

class TestListPlans:
    async def test_no_next_link_returns_all_plans(self, fake_token, sample_plans):
        client = await _make_client([
            _make_response(200, {"value": sample_plans})
        ])
        result = await list_plans(client, fake_token, "group-123")
        assert result == sample_plans

    async def test_with_next_link_concatenates_pages(self, fake_token):
        page1 = {"value": [{"id": "p1", "title": "Plan 1"}], "@odata.nextLink": f"{GRAPH_BASE}/groups/g/planner/plans?$skip=2"}
        page2 = {"value": [{"id": "p2", "title": "Plan 2"}]}
        client = await _make_client([
            _make_response(200, page1),
            _make_response(200, page2),
        ])
        result = await list_plans(client, fake_token, "g")
        assert len(result) == 2
        assert client.request.call_count == 2

    async def test_empty_group_returns_empty_list(self, fake_token):
        client = await _make_client([_make_response(200, {"value": []})])
        result = await list_plans(client, fake_token, "empty-group")
        assert result == []

    async def test_endpoint_includes_group_id_and_planner_plans(self, fake_token):
        group_id = "my-group-id"
        client = await _make_client([_make_response(200, {"value": []})])
        await list_plans(client, fake_token, group_id)
        args, _ = client.request.call_args
        url: str = args[1]
        assert group_id in url
        assert "planner/plans" in url


# ── delete_plan ───────────────────────────────────────────────────────────────

class TestDeletePlan:
    async def test_get_called_before_delete(self, fake_token):
        get_resp = _make_response(200, {"id": "plan-001", "@odata.etag": 'W/"etag-xyz"'})
        del_resp = _make_response(204)
        client = await _make_client([get_resp, del_resp])

        with patch.object(planner_import.asyncio, "sleep", new_callable=AsyncMock):
            await delete_plan(client, fake_token, "plan-001")

        assert client.request.call_count == 2
        first_call_args = client.request.call_args_list[0]
        assert first_call_args[0][0] == "GET"

    async def test_delete_uses_etag_from_get(self, fake_token):
        etag = 'W/"etag-from-get"'
        get_resp = _make_response(200, {"id": "plan-001", "@odata.etag": etag})
        del_resp = _make_response(204)
        client = await _make_client([get_resp, del_resp])

        with patch.object(planner_import.asyncio, "sleep", new_callable=AsyncMock):
            await delete_plan(client, fake_token, "plan-001")

        # Segunda llamada es el DELETE — verificar que If-Match contiene el etag
        second_call_kwargs = client.request.call_args_list[1][1]
        assert second_call_kwargs["headers"]["If-Match"] == etag

    async def test_delete_endpoint_includes_plan_id(self, fake_token):
        plan_id = "plan-abc-123"
        get_resp = _make_response(200, {"id": plan_id, "@odata.etag": 'W/"e"'})
        del_resp = _make_response(204)
        client = await _make_client([get_resp, del_resp])

        with patch.object(planner_import.asyncio, "sleep", new_callable=AsyncMock):
            await delete_plan(client, fake_token, plan_id)

        second_call_args = client.request.call_args_list[1][0]
        assert plan_id in second_call_args[1]


# ── create_plan ───────────────────────────────────────────────────────────────

class TestCreatePlan:
    async def test_payload_has_owner_and_title(self, fake_token):
        client = await _make_client([_make_response(201, {"id": "new-plan"})])
        await create_plan(client, fake_token, "group-id", "Mi Plan")
        _, kwargs = client.request.call_args
        assert kwargs["json"]["owner"] == "group-id"
        assert kwargs["json"]["title"] == "Mi Plan"

    async def test_returns_plan_dict(self, fake_token):
        client = await _make_client([_make_response(201, {"id": "plan-xyz", "title": "Mi Plan"})])
        result = await create_plan(client, fake_token, "group-id", "Mi Plan")
        assert result["id"] == "plan-xyz"


# ── create_bucket ─────────────────────────────────────────────────────────────

class TestCreateBucket:
    async def test_payload_has_plan_id_and_name(self, fake_token):
        client = await _make_client([_make_response(201, {"id": "bucket-new"})])
        await create_bucket(client, fake_token, "plan-abc", "Bucket X")
        _, kwargs = client.request.call_args
        assert kwargs["json"]["planId"] == "plan-abc"
        assert kwargs["json"]["name"] == "Bucket X"

    async def test_returns_bucket_dict(self, fake_token):
        client = await _make_client([_make_response(201, {"id": "bucket-id"})])
        result = await create_bucket(client, fake_token, "plan-abc", "Bucket X")
        assert result["id"] == "bucket-id"


# ── resolve_email_to_guid ─────────────────────────────────────────────────────

class TestResolveEmailToGuid:
    async def test_returns_guid_on_success(self, fake_token):
        client = await _make_client([_make_response(200, {"id": "guid-user-001"})])
        cache: dict = {}
        result = await resolve_email_to_guid(client, fake_token, "user@test.com", cache)
        assert result == "guid-user-001"

    async def test_caches_result(self, fake_token):
        client = await _make_client([_make_response(200, {"id": "guid-user-001"})])
        cache: dict = {}
        await resolve_email_to_guid(client, fake_token, "user@test.com", cache)
        # Segunda llamada — no debe llamar a graph_request
        result2 = await resolve_email_to_guid(client, fake_token, "user@test.com", cache)
        assert client.request.call_count == 1
        assert result2 == "guid-user-001"

    async def test_error_returns_none_and_caches(self, fake_token):
        client = await _make_client([_make_response(404)])
        cache: dict = {}
        result = await resolve_email_to_guid(client, fake_token, "bad@test.com", cache)
        assert result is None
        assert "bad@test.com" in cache
        assert cache["bad@test.com"] is None

    async def test_cached_none_not_retried(self, fake_token):
        client = await _make_client([])
        cache: dict = {"cached@test.com": None}
        result = await resolve_email_to_guid(client, fake_token, "cached@test.com", cache)
        assert result is None
        assert client.request.call_count == 0


# ── create_task_full ──────────────────────────────────────────────────────────

class TestCreateTaskFull:
    def _base_task(self) -> dict:
        return {
            "title": "Test Task",
            "priority": 3,
            "percent_complete": 0,
            "start_date": "2026-02-01T00:00:00Z",
            "due_date": "2026-02-28T00:00:00Z",
            "description": "Una descripción",
            "checklist_raw": "Item A;Item B",
            "labels_raw": "",
            "assignee_email": "",
        }

    async def test_three_calls_with_description_and_checklist(self, fake_token):
        post_resp = _make_response(201, {"id": "task-001"})
        get_resp = _make_response(200, {"@odata.etag": 'W/"det-etag"'})
        patch_resp = _make_response(204)
        client = await _make_client([post_resp, get_resp, patch_resp])

        await create_task_full(
            client, fake_token, "plan-x", "bucket-y", self._base_task(), None
        )
        assert client.request.call_count == 3

    async def test_patch_uses_details_etag(self, fake_token):
        etag = 'W/"details-etag-123"'
        post_resp = _make_response(201, {"id": "task-001"})
        get_resp = _make_response(200, {"@odata.etag": etag})
        patch_resp = _make_response(204)
        client = await _make_client([post_resp, get_resp, patch_resp])

        await create_task_full(
            client, fake_token, "plan-x", "bucket-y", self._base_task(), None
        )
        patch_call_kwargs = client.request.call_args_list[2][1]
        assert patch_call_kwargs["headers"]["If-Match"] == etag

    async def test_assignee_guid_in_assignments(self, fake_token):
        post_resp = _make_response(201, {"id": "task-001"})
        get_resp = _make_response(200, {"@odata.etag": 'W/"e"'})
        patch_resp = _make_response(204)
        client = await _make_client([post_resp, get_resp, patch_resp])

        task = self._base_task()
        await create_task_full(
            client, fake_token, "plan-x", "bucket-y", task, "guid-assignee-001"
        )
        post_call_kwargs = client.request.call_args_list[0][1]
        assert "guid-assignee-001" in post_call_kwargs["json"]["assignments"]

    async def test_two_calls_when_no_description_no_checklist(self, fake_token):
        post_resp = _make_response(201, {"id": "task-001"})
        get_resp = _make_response(200, {"@odata.etag": 'W/"e"'})
        client = await _make_client([post_resp, get_resp])

        task = self._base_task()
        task["description"] = ""
        task["checklist_raw"] = ""
        await create_task_full(
            client, fake_token, "plan-x", "bucket-y", task, None
        )
        assert client.request.call_count == 2

    async def test_returns_task_id(self, fake_token):
        post_resp = _make_response(201, {"id": "returned-task-id"})
        get_resp = _make_response(200, {"@odata.etag": 'W/"e"'})
        patch_resp = _make_response(204)
        client = await _make_client([post_resp, get_resp, patch_resp])

        task_id = await create_task_full(
            client, fake_token, "plan-x", "bucket-y", self._base_task(), None
        )
        assert task_id == "returned-task-id"


# ── list_buckets ──────────────────────────────────────────────────────────────

class TestListBuckets:
    async def test_no_next_link_returns_all(self, fake_token):
        sample_buckets = [
            {"id": "bucket-1", "name": "Diseño"},
            {"id": "bucket-2", "name": "Backend"},
        ]
        client = await _make_client([_make_response(200, {"value": sample_buckets})])
        result = await list_buckets(client, fake_token, "plan-123")
        assert result == sample_buckets

    async def test_with_next_link_paginates(self, fake_token):
        page1 = {
            "value": [{"id": "bucket-1", "name": "Diseño"}],
            "@odata.nextLink": f"{GRAPH_BASE}/planner/plans/plan-123/buckets?$skip=1",
        }
        page2 = {"value": [{"id": "bucket-2", "name": "Backend"}]}
        client = await _make_client([
            _make_response(200, page1),
            _make_response(200, page2),
        ])
        result = await list_buckets(client, fake_token, "plan-123")
        assert len(result) == 2
        assert client.request.call_count == 2

    async def test_endpoint_contains_plan_id(self, fake_token):
        plan_id = "my-plan-xyz"
        client = await _make_client([_make_response(200, {"value": []})])
        await list_buckets(client, fake_token, plan_id)
        args, _ = client.request.call_args
        url: str = args[1]
        assert plan_id in url
        assert "planner/plans" in url
        assert "buckets" in url

    async def test_empty_returns_empty_list(self, fake_token):
        client = await _make_client([_make_response(200, {"value": []})])
        result = await list_buckets(client, fake_token, "plan-123")
        assert result == []


# ── list_tasks ────────────────────────────────────────────────────────────────

class TestListTasks:
    async def test_no_next_link_returns_all(self, fake_token):
        sample_tasks = [
            {
                "id": "task-1",
                "title": "Mockup inicio",
                "bucketId": "bucket-1",
                "percentComplete": 50,
                "assignments": {"user-1": {}},
                "dueDateTime": "2026-03-30T00:00:00Z",
                "createdDateTime": "2026-03-01T00:00:00Z",
            },
        ]
        client = await _make_client([_make_response(200, {"value": sample_tasks})])
        result = await list_tasks(client, fake_token, "plan-123")
        assert result == sample_tasks

    async def test_with_next_link_paginates(self, fake_token):
        task1 = {
            "id": "task-1",
            "title": "Task 1",
            "bucketId": "b1",
            "percentComplete": 0,
            "assignments": {},
            "dueDateTime": None,
            "createdDateTime": "2026-03-01T00:00:00Z",
        }
        task2 = {
            "id": "task-2",
            "title": "Task 2",
            "bucketId": "b1",
            "percentComplete": 100,
            "assignments": {"user-2": {}},
            "dueDateTime": "2026-04-01T00:00:00Z",
            "createdDateTime": "2026-03-02T00:00:00Z",
        }
        page1 = {
            "value": [task1],
            "@odata.nextLink": f"{GRAPH_BASE}/planner/plans/plan-123/tasks?$select=...&$skip=1",
        }
        page2 = {"value": [task2]}
        client = await _make_client([
            _make_response(200, page1),
            _make_response(200, page2),
        ])
        result = await list_tasks(client, fake_token, "plan-123")
        assert len(result) == 2
        assert client.request.call_count == 2

    async def test_endpoint_contains_plan_id(self, fake_token):
        plan_id = "my-plan-xyz"
        client = await _make_client([_make_response(200, {"value": []})])
        await list_tasks(client, fake_token, plan_id)
        args, _ = client.request.call_args
        url: str = args[1]
        assert plan_id in url
        assert "planner/plans" in url
        assert "tasks" in url

    async def test_endpoint_url_no_select_parameter(self, fake_token):
        """URL no incluye $select — Microsoft Graph devuelve campos por defecto."""
        client = await _make_client([_make_response(200, {"value": []})])
        await list_tasks(client, fake_token, "plan-123")
        args, _ = client.request.call_args
        url: str = args[1]
        assert "$select" not in url
        # Verificar estructura básica de la URL
        assert "planner/plans/plan-123/tasks" in url

    async def test_returns_default_fields(self, fake_token):
        """Respuesta contiene campos devueltos por defecto: id, title, lastModifiedDateTime."""
        response_data = {
            "value": [
                {
                    "id": "t1",
                    "title": "Task",
                    "bucketId": "b1",
                    "percentComplete": 50,
                    "lastModifiedDateTime": "2026-03-15T00:00:00Z",
                }
            ]
        }
        client = await _make_client([_make_response(200, response_data)])
        result = await list_tasks(client, fake_token, "plan-123")
        assert len(result) == 1
        assert result[0]["id"] == "t1"
        assert result[0]["lastModifiedDateTime"] == "2026-03-15T00:00:00Z"

    async def test_conversation_thread_not_in_response(self, fake_token):
        """conversationThreadId NO está disponible en este endpoint."""
        response_data = {"value": [{"id": "t1", "title": "Task"}]}
        client = await _make_client([_make_response(200, response_data)])
        result = await list_tasks(client, fake_token, "plan-123")
        assert "conversationThreadId" not in result[0]


# ── _derive_task_status ────────────────────────────────────────────────────────

class TestDeriveTaskStatus:
    def test_zero_is_not_started(self):
        assert _derive_task_status(0) == "notStarted"

    def test_hundred_is_completed(self):
        assert _derive_task_status(100) == "completed"

    def test_fifty_is_in_progress(self):
        assert _derive_task_status(50) == "inProgress"

    def test_one_is_in_progress(self):
        assert _derive_task_status(1) == "inProgress"

    def test_ninety_nine_is_in_progress(self):
        assert _derive_task_status(99) == "inProgress"


# ── get_task_details ──────────────────────────────────────────────────────────

class TestGetTaskDetails:
    async def test_returns_task_details_dict(self, fake_token):
        """GET exitoso devuelve dict con description y checklist."""
        response_data = {
            "description": "Una descripción detallada",
            "@odata.etag": 'W/"etag-details"',
        }
        client = await _make_client([_make_response(200, response_data)])
        result = await get_task_details(client, fake_token, "task-123")
        assert result == response_data
        assert "description" in result

    async def test_endpoint_contains_task_id(self, fake_token):
        """URL contiene el task_id correcto."""
        task_id = "task-abc-xyz-123"
        client = await _make_client([_make_response(200, {})])
        await get_task_details(client, fake_token, task_id)
        args, _ = client.request.call_args
        url: str = args[1]
        assert task_id in url
        assert "planner/tasks" in url
        assert "details" in url

    async def test_single_call_no_pagination(self, fake_token):
        """Solo se hace 1 llamada (objeto único, sin @odata.nextLink)."""
        client = await _make_client([_make_response(200, {"id": "task-1"})])
        await get_task_details(client, fake_token, "task-123")
        assert client.request.call_count == 1

    async def test_propagates_http_status_error(self, fake_token):
        """Error 404 se propaga (raise_for_status lanza HTTPStatusError)."""
        client = await _make_client([_make_response(404)])
        with pytest.raises(httpx.HTTPStatusError):
            await get_task_details(client, fake_token, "nonexistent-task")


# ── _print_report_table ────────────────────────────────────────────────────────

class TestPrintReportTable:
    def test_task_without_due_date_shows_dash(self, capsys):
        """dueDateTime ausente → imprime '-'."""
        tasks = [
            {
                "title": "Sin fecha",
                "bucketId": "b1",
                "percentComplete": 0,
                "assignments": {},
            }
        ]
        buckets_dict = {"b1": "Backlog"}
        planner_import._print_report_table("Plan Test", buckets_dict, tasks)
        captured = capsys.readouterr()
        assert "-" in captured.out

    def test_task_without_assignments_shows_sin_asignar(self, capsys):
        """assignments vacío → imprime '(sin asignar)'."""
        tasks = [
            {
                "title": "Tarea huérfana",
                "bucketId": "b1",
                "percentComplete": 0,
                "assignments": {},
            }
        ]
        buckets_dict = {"b1": "Backlog"}
        planner_import._print_report_table("Plan Test", buckets_dict, tasks)
        captured = capsys.readouterr()
        assert "(sin asignar)" in captured.out

    def test_unknown_bucket_id_shows_question_mark(self, capsys):
        """bucketId no existe en buckets_dict → imprime '?'."""
        tasks = [
            {
                "title": "Tarea",
                "bucketId": "unknown-bucket",
                "percentComplete": 0,
                "assignments": {},
            }
        ]
        buckets_dict = {}
        planner_import._print_report_table("Plan Test", buckets_dict, tasks)
        captured = capsys.readouterr()
        assert "?" in captured.out

    def test_title_truncated_to_34_chars(self, capsys):
        """Título mayor a 34 chars se trunca."""
        long_title = "A" * 50
        tasks = [
            {
                "title": long_title,
                "bucketId": "b1",
                "percentComplete": 0,
                "assignments": {},
            }
        ]
        buckets_dict = {"b1": "Backlog"}
        planner_import._print_report_table("Plan Test", buckets_dict, tasks)
        captured = capsys.readouterr()
        # Debe aparecer truncado a 34
        assert "A" * 34 in captured.out
        assert "A" * 50 not in captured.out

    def test_empty_task_list_prints_header_only(self, capsys):
        """Lista vacía → imprime encabezado sin filas de datos."""
        planner_import._print_report_table("Plan Test", {}, [])
        captured = capsys.readouterr()
        assert "Bucket" in captured.out
        assert "Título" in captured.out
        assert "Plan Test" in captured.out

    def test_plan_title_in_output(self, capsys):
        """plan_title aparece en la salida."""
        plan_title = "MI PLAN ESPECIAL"
        planner_import._print_report_table(plan_title, {}, [])
        captured = capsys.readouterr()
        assert plan_title in captured.out



# ── run_report ────────────────────────────────────────────────────────────────

class TestRunReport:
    async def test_no_plans_exits_early(self, mock_auth, monkeypatch, capsys):
        """list_plans retorna [] → imprime 'No se encontraron planes.' y retorna."""
        with patch.object(planner_import, "list_plans", new_callable=AsyncMock) as mock_list:
            mock_list.return_value = []
            await planner_import.run_report("group-id")
            captured = capsys.readouterr()
            assert "No se encontraron planes" in captured.out

    async def test_seleccion_todos_procesa_todos(self, mock_auth, monkeypatch, capsys):
        """Input 'todos' → llama list_buckets y list_tasks para cada plan."""
        plans = [
            {"id": "p1", "title": "Plan 1"},
            {"id": "p2", "title": "Plan 2"},
        ]
        with patch.object(planner_import, "list_plans", new_callable=AsyncMock) as mock_list:
            with patch.object(planner_import, "list_buckets", new_callable=AsyncMock) as mock_buckets:
                with patch.object(planner_import, "list_tasks", new_callable=AsyncMock) as mock_tasks:
                    mock_list.return_value = plans
                    mock_buckets.return_value = []
                    mock_tasks.return_value = []
                    monkeypatch.setattr("builtins.input", lambda _: "todos")

                    await planner_import.run_report("group-id")

                    assert mock_buckets.call_count == 2
                    assert mock_tasks.call_count == 2

    async def test_seleccion_numerica(self, mock_auth, monkeypatch, capsys):
        """Input '1' → procesa solo el primer plan de la lista."""
        plans = [
            {"id": "p1", "title": "Plan 1"},
            {"id": "p2", "title": "Plan 2"},
        ]
        with patch.object(planner_import, "list_plans", new_callable=AsyncMock) as mock_list:
            with patch.object(planner_import, "list_buckets", new_callable=AsyncMock) as mock_buckets:
                with patch.object(planner_import, "list_tasks", new_callable=AsyncMock) as mock_tasks:
                    mock_list.return_value = plans
                    mock_buckets.return_value = []
                    mock_tasks.return_value = []
                    monkeypatch.setattr("builtins.input", lambda _: "1")

                    await planner_import.run_report("group-id")

                    assert mock_buckets.call_count == 1
                    assert mock_tasks.call_count == 1

    async def test_seleccion_vacia_sale(self, mock_auth, monkeypatch, capsys):
        """Input '' → imprime mensaje de salida y retorna sin procesar planes."""
        plans = [{"id": "p1", "title": "Plan 1"}]
        with patch.object(planner_import, "list_plans", new_callable=AsyncMock) as mock_list:
            with patch.object(planner_import, "list_buckets", new_callable=AsyncMock) as mock_buckets:
                mock_list.return_value = plans
                monkeypatch.setattr("builtins.input", lambda _: "")

                await planner_import.run_report("group-id")

                captured = capsys.readouterr()
                assert "Sin selección" in captured.out or "Saliendo" in captured.out
                mock_buckets.assert_not_called()

    async def test_export_csv_creates_file(self, mock_auth, monkeypatch, tmp_path):
        """--export crea archivo CSV con columnas correctas."""
        csv_path = tmp_path / "test_report.csv"
        plans = [
            {"id": "p1", "title": "Plan 1"},
        ]
        buckets = [{"id": "b1", "name": "Backlog"}]
        tasks = [
            {
                "id": "t1",
                "title": "Task 1",
                "bucketId": "b1",
                "assignments": {"user-1": {}},
                "percentComplete": 50,
                "dueDateTime": "2026-03-30T00:00:00Z",
                "createdDateTime": "2026-03-01T00:00:00Z",
            }
        ]
        with patch.object(planner_import, "list_plans", new_callable=AsyncMock) as mock_list:
            with patch.object(planner_import, "list_buckets", new_callable=AsyncMock) as mock_buckets:
                with patch.object(planner_import, "list_tasks", new_callable=AsyncMock) as mock_tasks:
                    mock_list.return_value = plans
                    mock_buckets.return_value = buckets
                    mock_tasks.return_value = tasks
                    monkeypatch.setattr("builtins.input", lambda _: "1")

                    await planner_import.run_report("group-id", export_csv=csv_path)

                    assert csv_path.exists()
                    content = csv_path.read_text(encoding="utf-8")
                    assert "PlanID" in content
                    assert "TaskTitle" in content
                    assert ";" in content  # Delimitador

    async def test_export_to_env_raises_value_error(self, mock_auth, monkeypatch):
        """export_csv con '.env' en ruta lanza ValueError antes de procesar."""
        env_path = Path("/some/path/.env")
        with pytest.raises(ValueError, match="seguridad"):
            await planner_import.run_report("group-id", export_csv=env_path)

    async def test_filter_text_excluye_planes(self, mock_auth, monkeypatch, capsys):
        """filter_text filtra planes por título — los no coincidentes no aparecen."""
        plans = [
            {"id": "p1", "title": "Plan 2026-Q1"},
            {"id": "p2", "title": "Proyecto Viejo 2025"},
        ]
        with patch.object(planner_import, "list_plans", new_callable=AsyncMock) as mock_list:
            with patch.object(planner_import, "list_buckets", new_callable=AsyncMock) as mock_buckets:
                with patch.object(planner_import, "list_tasks", new_callable=AsyncMock) as mock_tasks:
                    mock_list.return_value = plans
                    mock_buckets.return_value = []
                    mock_tasks.return_value = []
                    monkeypatch.setattr("builtins.input", lambda _: "todos")

                    await planner_import.run_report("group-id", filter_text="2026")

                    captured = capsys.readouterr()
                    assert "2026-Q1" in captured.out
                    assert "Viejo 2025" not in captured.out


# ── get_last_comment (B2) ──────────────────────────────────────────────────────

class TestGetLastComment:
    async def test_returns_text_and_date(self, fake_token):
        """Respuesta 200 con posts → devuelve dict con text y date."""
        from planner_import import get_last_comment

        response_data = {
            "value": [
                {
                    "body": {"content": "<div>Último comentario de la tarea</div>"},
                    "receivedDateTime": "2026-03-15T10:30:00Z",
                }
            ]
        }
        client = await _make_client([_make_response(200, response_data)])
        result = await get_last_comment(client, fake_token, "group-id", "thread-id")
        assert isinstance(result, dict)
        assert "text" in result
        assert "date" in result
        assert "Último comentario" in result["text"]
        assert "2026-03-15" in result["date"]

    async def test_strips_html_tags(self, fake_token):
        """HTML tags se eliminan, solo queda el contenido de texto."""
        from planner_import import get_last_comment

        response_data = {
            "value": [
                {
                    "body": {
                        "content": "<div><p>Clean <strong>text</strong> only</p></div>"
                    },
                    "receivedDateTime": "2026-03-15T10:30:00Z",
                }
            ]
        }
        client = await _make_client([_make_response(200, response_data)])
        result = await get_last_comment(client, fake_token, "group-id", "thread-id")
        assert "<" not in result["text"]
        assert ">" not in result["text"]
        assert "Clean" in result["text"]
        assert "text" in result["text"]

    async def test_truncates_to_200(self, fake_token):
        """Texto mayor a 200 caracteres se trunca."""
        from planner_import import get_last_comment

        long_text = "A" * 250
        response_data = {
            "value": [
                {
                    "body": {"content": f"<div>{long_text}</div>"},
                    "receivedDateTime": "2026-03-15T10:30:00Z",
                }
            ]
        }
        client = await _make_client([_make_response(200, response_data)])
        result = await get_last_comment(client, fake_token, "group-id", "thread-id")
        assert len(result["text"]) <= 200

    async def test_no_posts_returns_dashes(self, fake_token):
        """value: [] (sin posts) → devuelve {'-', '-'}."""
        from planner_import import get_last_comment

        response_data = {"value": []}
        client = await _make_client([_make_response(200, response_data)])
        result = await get_last_comment(client, fake_token, "group-id", "thread-id")
        assert result == {"text": "-", "date": "-"}

    async def test_404_returns_dashes(self, fake_token):
        """404 → se absorbe silenciosamente, devuelve {'-', '-'}."""
        from planner_import import get_last_comment

        client = await _make_client([_make_response(404)])
        result = await get_last_comment(client, fake_token, "group-id", "thread-id")
        assert result == {"text": "-", "date": "-"}

    async def test_non_404_propagates(self, fake_token):
        """500 u otro error → se propaga (no se absorbe)."""
        from planner_import import get_last_comment

        client = await _make_client([_make_response(500)])
        with pytest.raises(httpx.HTTPStatusError):
            await get_last_comment(client, fake_token, "group-id", "thread-id")


# ── _print_report_table con comentarios (B2) ──────────────────────────────────

class TestPrintReportTableComments:
    def test_show_comments_shows_column(self, capsys):
        """show_comments=True → columna 'Último comentario' aparece."""
        tasks = [
            {
                "title": "Tarea con comentario",
                "bucketId": "b1",
                "percentComplete": 0,
                "assignments": {},
                "lastModifiedDateTime": "2026-03-10T15:30:00Z",
                "LastCommentText": "Este es un comentario",
                "LastCommentDate": "2026-03-14",
            }
        ]
        buckets_dict = {"b1": "Backlog"}
        planner_import._print_report_table("Plan Test", buckets_dict, tasks, show_comments=True)
        captured = capsys.readouterr()
        assert "Último comentario" in captured.out
        assert "Este es un comentario" in captured.out

    def test_no_comments_hides_column(self, capsys):
        """show_comments=False (default) → columna 'Último comentario' NO aparece."""
        tasks = [
            {
                "title": "Tarea sin comentario",
                "bucketId": "b1",
                "percentComplete": 0,
                "assignments": {},
                "lastModifiedDateTime": "2026-03-10T15:30:00Z",
            }
        ]
        buckets_dict = {"b1": "Backlog"}
        planner_import._print_report_table("Plan Test", buckets_dict, tasks, show_comments=False)
        captured = capsys.readouterr()
        assert "Último comentario" not in captured.out

    def test_comment_text_truncated_to_38(self, capsys):
        """Texto de comentario > 38 chars se trunca en display."""
        long_comment = "A" * 50
        tasks = [
            {
                "title": "Tarea",
                "bucketId": "b1",
                "percentComplete": 0,
                "assignments": {},
                "lastModifiedDateTime": "2026-03-10T15:30:00Z",
                "LastCommentText": long_comment,
                "LastCommentDate": "2026-03-14",
            }
        ]
        buckets_dict = {"b1": "Backlog"}
        planner_import._print_report_table("Plan Test", buckets_dict, tasks, show_comments=True)
        captured = capsys.readouterr()
        # Se trunca en [:38] en la línea de print, así que máximo 38 A's pueden aparecer consecutivos
        assert "A" * 38 in captured.out
        assert "A" * 50 not in captured.out


# ── run_report con comentarios (B2) ────────────────────────────────────────────

class TestRunReportComments:
    async def test_comments_flag_calls_get_last_comment(self, mock_auth, monkeypatch):
        """Con fetch_comments=True, se llama get_last_comment para cada tarea con hilo."""
        plans = [{"id": "p1", "title": "Plan 1"}]
        buckets = [{"id": "b1", "name": "Backlog"}]
        tasks = [
            {
                "id": "t1",
                "title": "Task 1",
                "bucketId": "b1",
                "assignments": {},
                "percentComplete": 0,
            },
            {
                "id": "t2",
                "title": "Task 2",
                "bucketId": "b1",
                "assignments": {},
                "percentComplete": 0,
            }
        ]
        task_details_responses = [
            {"conversationThreadId": "thread-123"},
            {"conversationThreadId": "thread-456"},
        ]
        with patch.object(planner_import, "list_plans", new_callable=AsyncMock) as mock_list:
            with patch.object(planner_import, "list_buckets", new_callable=AsyncMock) as mock_buckets:
                with patch.object(planner_import, "list_tasks", new_callable=AsyncMock) as mock_tasks:
                    with patch.object(planner_import, "get_last_comment", new_callable=AsyncMock) as mock_comment:
                        with patch.object(planner_import, "graph_request", new_callable=AsyncMock) as mock_graph:
                            mock_list.return_value = plans
                            mock_buckets.return_value = buckets
                            mock_tasks.return_value = tasks
                            mock_graph.side_effect = task_details_responses
                            mock_comment.return_value = {"text": "Comment", "date": "2026-03-14"}
                            monkeypatch.setattr("builtins.input", lambda _: "1")

                            await planner_import.run_report("group-id", fetch_comments=True)

                            assert mock_comment.call_count == 2

    async def test_no_comments_flag_skips_calls(self, mock_auth, monkeypatch):
        """Sin fetch_comments (default), get_last_comment NO se llama."""
        plans = [{"id": "p1", "title": "Plan 1"}]
        buckets = [{"id": "b1", "name": "Backlog"}]
        tasks = [
            {
                "id": "t1",
                "title": "Task 1",
                "bucketId": "b1",
                "assignments": {},
                "percentComplete": 0,
            }
        ]
        with patch.object(planner_import, "list_plans", new_callable=AsyncMock) as mock_list:
            with patch.object(planner_import, "list_buckets", new_callable=AsyncMock) as mock_buckets:
                with patch.object(planner_import, "list_tasks", new_callable=AsyncMock) as mock_tasks:
                    with patch.object(planner_import, "get_last_comment", new_callable=AsyncMock) as mock_comment:
                        mock_list.return_value = plans
                        mock_buckets.return_value = buckets
                        mock_tasks.return_value = tasks
                        monkeypatch.setattr("builtins.input", lambda _: "1")

                        await planner_import.run_report("group-id", fetch_comments=False)

                        mock_comment.assert_not_called()


class TestPrintKpiBlock:
    """Tests para _print_kpi_block — 14 tests."""

    def _make_kpi_task(
        self,
        bucket_id="b1",
        percent=0,
        due_days=None,
        modified_days=None,
        comment_text="",
    ) -> dict:
        """Factory helper para crear tareas de test.

        due_days: None = sin fecha, <0 = vencida, >0 = futura
        modified_days: None = sin dato, número = días atrás
        """
        from datetime import date, timedelta

        today = date.today()
        due = None
        if due_days is not None:
            due = (today + timedelta(days=due_days)).isoformat() + "T00:00:00Z"
        modified = "-"
        if modified_days is not None:
            modified = (today - timedelta(days=modified_days)).isoformat() + "T00:00:00Z"
        return {
            "id": "tid",
            "title": "Test task",
            "bucketId": bucket_id,
            "percentComplete": percent,
            "assignments": {},
            "dueDateTime": due,
            "lastModifiedDateTime": modified,
            "LastCommentText": comment_text,
            "LastCommentDate": "",
            "priority": 5,
        }

    def test_empty_task_list(self, capsys):
        """Lista vacía no lanza excepción, imprime encabezado con plan_title."""
        tasks = []
        buckets_dict = {}
        _print_kpi_block("Test Plan", buckets_dict, tasks)
        captured = capsys.readouterr()
        # Con lista vacía, _print_kpi_block retorna sin imprimir nada
        assert captured.out == ""

    def test_totals_correct(self, capsys):
        """1 comp + 1 inProgress + 1 notStarted → totales y % en output."""
        tasks = [
            self._make_kpi_task(bucket_id="b1", percent=100),
            self._make_kpi_task(bucket_id="b1", percent=50),
            self._make_kpi_task(bucket_id="b1", percent=0),
        ]
        buckets_dict = {"b1": "Backlog"}
        _print_kpi_block("Test Plan", buckets_dict, tasks)
        captured = capsys.readouterr()
        assert "Total: 3" in captured.out
        assert "Completadas: 1" in captured.out
        assert "En progreso: 1" in captured.out
        assert "Sin iniciar: 1" in captured.out

    def test_vencidas_count(self, capsys):
        """2 tareas con due pasado y <100%, 1 completada pasada → vencidas = 2."""
        from datetime import date, timedelta

        today = date.today()
        tasks = [
            self._make_kpi_task(bucket_id="b1", percent=0, due_days=-1),  # vencida
            self._make_kpi_task(bucket_id="b1", percent=50, due_days=-2),  # vencida
            self._make_kpi_task(bucket_id="b1", percent=100, due_days=-3),  # completada, no cuenta
        ]
        buckets_dict = {"b1": "Backlog"}
        _print_kpi_block("Test Plan", buckets_dict, tasks)
        captured = capsys.readouterr()
        assert "Vencidas (no completadas): 2" in captured.out

    def test_vencidas_zero_no_alert(self, capsys):
        """0 vencidas → output contiene '0' sin alertas."""
        tasks = [
            self._make_kpi_task(bucket_id="b1", percent=0, due_days=5),
            self._make_kpi_task(bucket_id="b1", percent=50, due_days=10),
        ]
        buckets_dict = {"b1": "Backlog"}
        _print_kpi_block("Test Plan", buckets_dict, tasks)
        captured = capsys.readouterr()
        assert "Vencidas (no completadas): 0" in captured.out

    def test_signal_cuello_inprogreso_con_vencidas(self, capsys):
        """4/6 inProgress + 1 vencida → 'CUELLO' en output."""
        tasks = [
            self._make_kpi_task(bucket_id="b1", percent=50, due_days=-1),
            self._make_kpi_task(bucket_id="b1", percent=50),
            self._make_kpi_task(bucket_id="b1", percent=50),
            self._make_kpi_task(bucket_id="b1", percent=50),
            self._make_kpi_task(bucket_id="b1", percent=0),
            self._make_kpi_task(bucket_id="b1", percent=0),
        ]
        buckets_dict = {"b1": "Backlog"}
        _print_kpi_block("Test Plan", buckets_dict, tasks)
        captured = capsys.readouterr()
        assert "CUELLO" in captured.out

    def test_signal_cuello_sin_completadas(self, capsys):
        """4/7 inProgress + 0 completadas → 'CUELLO' en output."""
        tasks = [
            self._make_kpi_task(bucket_id="b1", percent=50),
            self._make_kpi_task(bucket_id="b1", percent=50),
            self._make_kpi_task(bucket_id="b1", percent=50),
            self._make_kpi_task(bucket_id="b1", percent=50),
            self._make_kpi_task(bucket_id="b1", percent=0),
            self._make_kpi_task(bucket_id="b1", percent=0),
            self._make_kpi_task(bucket_id="b1", percent=0),
        ]
        buckets_dict = {"b1": "Backlog"}
        _print_kpi_block("Test Plan", buckets_dict, tasks)
        captured = capsys.readouterr()
        assert "CUELLO" in captured.out

    def test_signal_gateway_vencidas(self, capsys):
        """bucket 'Gateway' + 1 vencida → 'GATEWAY' en output."""
        tasks = [
            self._make_kpi_task(bucket_id="b1", percent=0, due_days=-1),
            self._make_kpi_task(bucket_id="b1", percent=50),
        ]
        buckets_dict = {"b1": "Gateway"}
        _print_kpi_block("Test Plan", buckets_dict, tasks)
        captured = capsys.readouterr()
        assert "GATEWAY" in captured.out

    def test_signal_fluye(self, capsys):
        """5/8 completadas → 'FLUYE' en output."""
        tasks = [
            self._make_kpi_task(bucket_id="b1", percent=100),
            self._make_kpi_task(bucket_id="b1", percent=100),
            self._make_kpi_task(bucket_id="b1", percent=100),
            self._make_kpi_task(bucket_id="b1", percent=100),
            self._make_kpi_task(bucket_id="b1", percent=100),
            self._make_kpi_task(bucket_id="b1", percent=50),
            self._make_kpi_task(bucket_id="b1", percent=0),
            self._make_kpi_task(bucket_id="b1", percent=0),
        ]
        buckets_dict = {"b1": "Backlog"}
        _print_kpi_block("Test Plan", buckets_dict, tasks)
        captured = capsys.readouterr()
        assert "FLUYE" in captured.out

    def test_signal_pendiente(self, capsys):
        """todo notStarted → 'PENDIENTE' en output."""
        tasks = [
            self._make_kpi_task(bucket_id="b1", percent=0),
            self._make_kpi_task(bucket_id="b1", percent=0),
            self._make_kpi_task(bucket_id="b1", percent=0),
        ]
        buckets_dict = {"b1": "Backlog"}
        _print_kpi_block("Test Plan", buckets_dict, tasks)
        captured = capsys.readouterr()
        assert "PENDIENTE" in captured.out

    def test_bucket_vacio_dash(self, capsys):
        """bucket en buckets_dict sin tareas → '—' en output."""
        tasks = [
            self._make_kpi_task(bucket_id="b1", percent=0),
        ]
        buckets_dict = {"b1": "Backlog", "b2": "EmptyBucket"}
        _print_kpi_block("Test Plan", buckets_dict, tasks)
        captured = capsys.readouterr()
        # EmptyBucket debe tener '—' como señal
        assert "—" in captured.out

    def test_no_comments_hides_cobertura(self, capsys):
        """show_comments=False → 'Cobertura de gestión' NO en output."""
        tasks = [
            self._make_kpi_task(bucket_id="b1", percent=0, comment_text="test"),
        ]
        buckets_dict = {"b1": "Backlog"}
        _print_kpi_block("Test Plan", buckets_dict, tasks, show_comments=False)
        captured = capsys.readouterr()
        assert "Cobertura de gestión por bucket:" not in captured.out

    def test_con_comments_cobertura_aparece(self, capsys):
        """show_comments=True + tasks con texto → 'Cobertura de gestión' en output."""
        tasks = [
            self._make_kpi_task(bucket_id="b1", percent=0, comment_text="test"),
        ]
        buckets_dict = {"b1": "Backlog"}
        _print_kpi_block("Test Plan", buckets_dict, tasks, show_comments=True)
        captured = capsys.readouterr()
        assert "Cobertura de gestión por bucket:" in captured.out

    def test_urgentes_sin_comentario(self, capsys):
        """tarea sin comentario + due en 3 días → aparece en 'vencimiento próximo'."""
        tasks = [
            self._make_kpi_task(
                bucket_id="b1",
                percent=0,
                due_days=3,
                comment_text="",
            ),
        ]
        buckets_dict = {"b1": "Backlog"}
        _print_kpi_block("Test Plan", buckets_dict, tasks, show_comments=True)
        captured = capsys.readouterr()
        assert "Sin comentario con vencimiento próximo" in captured.out
        assert "Test task" in captured.out

    def test_stagnadas_skipped_when_no_data(self, capsys):
        """todos lastModifiedDateTime = '-' → 'Estancadas' NO en output."""
        tasks = [
            self._make_kpi_task(bucket_id="b1", percent=0, modified_days=None),
        ]
        buckets_dict = {"b1": "Backlog"}
        _print_kpi_block("Test Plan", buckets_dict, tasks, show_comments=False)
        captured = capsys.readouterr()
        # Sin datos de lastModified, no debe mostrar "Estancadas"
        assert "Estancadas" not in captured.out or "0 tareas" not in captured.out


# ── TestResolveGuidToEmail ────────────────────────────────────────────────────

class TestResolveGuidToEmail:
    async def test_returns_mail_field(self, fake_token):
        """Si 'mail' está presente, retorna ese valor."""
        client = await _make_client(
            [_make_response(200, {"id": "user-guid", "mail": "user@example.com"})]
        )
        result = await resolve_guid_to_email(client, fake_token, "user-guid")
        assert result == "user@example.com"

    async def test_falls_back_to_upn(self, fake_token):
        """Si 'mail' es vacío, retorna 'userPrincipalName'."""
        client = await _make_client(
            [_make_response(200, {"id": "user-guid", "mail": None, "userPrincipalName": "user@tenant.onmicrosoft.com"})]
        )
        result = await resolve_guid_to_email(client, fake_token, "user-guid")
        assert result == "user@tenant.onmicrosoft.com"

    async def test_http_error_returns_none(self, fake_token):
        """Si falla (HTTPStatusError), retorna None sin lanzar excepción."""
        client = await _make_client([_make_response(404)])
        result = await resolve_guid_to_email(client, fake_token, "nonexistent-guid")
        assert result is None


# ── TestBuildReportHtml ───────────────────────────────────────────────────────

class TestBuildReportHtml:
    def test_returns_string(self):
        """Retorna str, no vacío."""
        html = build_report_html("Test Plan", {}, [], "01-01-2026")
        assert isinstance(html, str)
        assert len(html) > 0

    def test_plan_title_in_html(self):
        """Plan title aparece en el HTML."""
        html = build_report_html("Mi Plan Especial", {}, [], "01-01-2026")
        assert "Mi Plan Especial" in html

    def test_task_title_in_html(self):
        """Título de tarea aparece en el HTML."""
        tasks = [
            {
                "id": "task1",
                "title": "Mi Tarea Importante",
                "bucketId": "b1",
                "percentComplete": 50,
                "assignments": {},
                "dueDateTime": "2026-03-20T00:00:00Z",
            }
        ]
        html = build_report_html("Test", {"b1": "Backlog"}, tasks, "01-01-2026")
        assert "Mi Tarea Importante" in html

    def test_bucket_name_in_html(self):
        """Nombre de bucket aparece en el HTML."""
        tasks = [
            {
                "id": "task1",
                "title": "Task",
                "bucketId": "b1",
                "percentComplete": 0,
                "assignments": {},
            }
        ]
        html = build_report_html("Test", {"b1": "Mi Bucket Especial"}, tasks, "01-01-2026")
        assert "Mi Bucket Especial" in html


# ── TestSendMailReport ────────────────────────────────────────────────────────

class TestSendMailReport:
    async def test_calls_sendmail_endpoint(self, fake_token):
        """graph_request llamado con /users/{sender_upn}/sendMail."""
        client = await _make_client([_make_response(202)])
        await send_mail_report(
            client, fake_token, ["user@example.com"], "Subject", "<p>Body</p>",
            sender_upn="sender@test.com"
        )
        args, kwargs = client.request.call_args
        assert "/users/sender@test.com/sendMail" in args[1]

    async def test_payload_has_recipients(self, fake_token):
        """Payload contiene toRecipients con los emails."""
        client = await _make_client([_make_response(202)])
        await send_mail_report(
            client, fake_token, ["user1@example.com", "user2@example.com"], "Subj", "<p>Body</p>",
            sender_upn="sender@test.com"
        )
        _, kwargs = client.request.call_args
        payload = kwargs["json"]
        recipients = payload["message"]["toRecipients"]
        emails = [r["emailAddress"]["address"] for r in recipients]
        assert "user1@example.com" in emails
        assert "user2@example.com" in emails

    async def test_subject_in_payload(self, fake_token):
        """Subject correcto en message.subject."""
        client = await _make_client([_make_response(202)])
        await send_mail_report(
            client, fake_token, ["user@example.com"], "Mi Asunto", "<p>Body</p>",
            sender_upn="sender@test.com"
        )
        _, kwargs = client.request.call_args
        payload = kwargs["json"]
        assert payload["message"]["subject"] == "Mi Asunto"

    async def test_empty_recipients_raises(self, fake_token):
        """Lista vacía lanza ValueError, no llama a Graph."""
        client = await _make_client([])
        with pytest.raises(ValueError, match="to_emails no puede estar vacío"):
            await send_mail_report(client, fake_token, [], "Subject", "<p>Body</p>",
                                 sender_upn="sender@test.com")
        client.request.assert_not_called()


# ── TestRunEmailReport ────────────────────────────────────────────────────────

class TestRunEmailReport:
    async def test_sends_for_each_plan(self, fake_token):
        """send_mail_report llamado una vez por plan seleccionado."""
        # Mock list_plans, list_buckets, list_tasks, resolve_guid_to_email, build_report_html, send_mail_report
        with patch.object(planner_import, "list_plans", new_callable=AsyncMock) as mock_list_plans, \
             patch.object(planner_import, "list_buckets", new_callable=AsyncMock) as mock_list_buckets, \
             patch.object(planner_import, "list_tasks", new_callable=AsyncMock) as mock_list_tasks, \
             patch.object(planner_import, "resolve_guid_to_email", new_callable=AsyncMock) as mock_resolve, \
             patch.object(planner_import, "send_mail_report", new_callable=AsyncMock) as mock_send, \
             patch.object(planner_import, "_print_plans_table"), \
             patch("builtins.print"), \
             patch("builtins.input", return_value="1"):
            mock_list_plans.return_value = [
                {"id": "plan1", "title": "Plan 1"},
                {"id": "plan2", "title": "Plan 2"},
            ]
            mock_list_buckets.return_value = [{"id": "b1", "name": "Backlog"}]
            mock_list_tasks.return_value = [
                {
                    "id": "task1",
                    "title": "Task",
                    "bucketId": "b1",
                    "percentComplete": 50,
                    "assignments": {"guid1": {}},
                }
            ]
            mock_resolve.return_value = "user@example.com"

            from planner_import import run_email_report

            await run_email_report("group-id", fetch_checklist=False)
            # send_mail_report debe haber sido llamado 1 vez (solo el plan seleccionado)
            assert mock_send.call_count == 1

    async def test_skips_plan_with_no_assignees(self, fake_token):
        """Plan sin asignados → imprime aviso, no llama send_mail_report."""
        with patch.object(planner_import, "list_plans", new_callable=AsyncMock) as mock_list_plans, \
             patch.object(planner_import, "list_buckets", new_callable=AsyncMock) as mock_list_buckets, \
             patch.object(planner_import, "list_tasks", new_callable=AsyncMock) as mock_list_tasks, \
             patch.object(planner_import, "send_mail_report", new_callable=AsyncMock) as mock_send, \
             patch.object(planner_import, "_print_plans_table"), \
             patch("builtins.print"), \
             patch("builtins.input", return_value="1"):
            mock_list_plans.return_value = [{"id": "plan1", "title": "Plan"}]
            mock_list_buckets.return_value = [{"id": "b1", "name": "Backlog"}]
            mock_list_tasks.return_value = [
                {
                    "id": "task1",
                    "title": "Task",
                    "bucketId": "b1",
                    "percentComplete": 50,
                    "assignments": {},  # sin asignados
                }
            ]

            from planner_import import run_email_report

            await run_email_report("group-id", fetch_checklist=False)
            # send_mail_report NO debe ser llamado
            mock_send.assert_not_called()

    async def test_filter_text_applied(self, fake_token):
        """Planes que no coinciden con filter_text son ignorados."""
        with patch.object(planner_import, "list_plans", new_callable=AsyncMock) as mock_list_plans, \
             patch.object(planner_import, "_print_plans_table"), \
             patch("builtins.print"), \
             patch("builtins.input", return_value=""):
            mock_list_plans.return_value = [
                {"id": "plan1", "title": "Project A"},
                {"id": "plan2", "title": "Project B"},
            ]

            from planner_import import run_email_report

            await run_email_report("group-id", filter_text="Project A", fetch_checklist=False)
            # list_plans debe llamarse, pero el filtro se aplica en memoria
            assert mock_list_plans.call_count == 1


class TestRunEmailReportPreview:
    """Tests para --preview flag en email-report."""

    async def test_preview_saves_html_file(self, fake_token):
        """Con preview=True, se crea un archivo .html en reports/."""
        with patch.object(planner_import, "list_plans", new_callable=AsyncMock) as mock_list_plans, \
             patch.object(planner_import, "list_buckets", new_callable=AsyncMock) as mock_buckets, \
             patch.object(planner_import, "list_tasks", new_callable=AsyncMock) as mock_tasks, \
             patch.object(planner_import, "build_report_html") as mock_build, \
             patch.object(planner_import, "_print_plans_table"), \
             patch("builtins.print"), \
             patch("builtins.input", return_value="1"), \
             patch("webbrowser.open") as mock_browser, \
             patch.object(Path, "write_text") as mock_write:

            mock_list_plans.return_value = [{"id": "p1", "title": "Test Plan"}]
            mock_buckets.return_value = [{"id": "b1", "name": "Backlog"}]
            mock_tasks.return_value = [
                {"id": "t1", "title": "Task", "bucketId": "b1", "assignments": {}, "percentComplete": 0}
            ]
            mock_build.return_value = "<html>test</html>"

            from planner_import import run_email_report

            await run_email_report("group-id", preview=True, fetch_checklist=False)
            # Debe haberse creado el archivo
            mock_write.assert_called_once()
            args, kwargs = mock_write.call_args
            assert args[0] == "<html>test</html>"
            assert kwargs.get("encoding") == "utf-8"

    async def test_preview_does_not_call_send(self, fake_token):
        """Con preview=True, send_mail_report NO es llamado."""
        with patch.object(planner_import, "list_plans", new_callable=AsyncMock) as mock_list_plans, \
             patch.object(planner_import, "list_buckets", new_callable=AsyncMock) as mock_buckets, \
             patch.object(planner_import, "list_tasks", new_callable=AsyncMock) as mock_tasks, \
             patch.object(planner_import, "build_report_html") as mock_build, \
             patch.object(planner_import, "send_mail_report", new_callable=AsyncMock) as mock_send, \
             patch.object(planner_import, "_print_plans_table"), \
             patch("builtins.print"), \
             patch("builtins.input", return_value="1"), \
             patch("webbrowser.open"), \
             patch.object(Path, "write_text"):

            mock_list_plans.return_value = [{"id": "p1", "title": "Test Plan"}]
            mock_buckets.return_value = [{"id": "b1", "name": "Backlog"}]
            mock_tasks.return_value = [
                {"id": "t1", "title": "Task", "bucketId": "b1", "assignments": {}, "percentComplete": 0}
            ]
            mock_build.return_value = "<html>test</html>"

            from planner_import import run_email_report

            await run_email_report("group-id", preview=True, fetch_checklist=False)
            # send_mail_report NO debe ser llamado
            mock_send.assert_not_called()

    async def test_preview_opens_browser(self, fake_token):
        """Con preview=True, webbrowser.open es llamado una vez por plan."""
        with patch.object(planner_import, "list_plans", new_callable=AsyncMock) as mock_list_plans, \
             patch.object(planner_import, "list_buckets", new_callable=AsyncMock) as mock_buckets, \
             patch.object(planner_import, "list_tasks", new_callable=AsyncMock) as mock_tasks, \
             patch.object(planner_import, "build_report_html") as mock_build, \
             patch.object(planner_import, "_print_plans_table"), \
             patch("builtins.print"), \
             patch("builtins.input", return_value="1"), \
             patch("webbrowser.open") as mock_browser, \
             patch.object(Path, "write_text"):

            mock_list_plans.return_value = [{"id": "p1", "title": "Test Plan"}]
            mock_buckets.return_value = [{"id": "b1", "name": "Backlog"}]
            mock_tasks.return_value = [
                {"id": "t1", "title": "Task", "bucketId": "b1", "assignments": {}, "percentComplete": 0}
            ]
            mock_build.return_value = "<html>test</html>"

            from planner_import import run_email_report

            await run_email_report("group-id", preview=True, fetch_checklist=False)
            # webbrowser.open debe ser llamado una vez
            mock_browser.assert_called_once()
            call_args = mock_browser.call_args[0][0]
            assert "preview_" in call_args
            assert ".html" in call_args


class TestRunEmailReportTo:
    """Tests para --to <email> flag en email-report."""

    async def test_to_override_sends_to_single_email(self, fake_token):
        """Con to_override, send_mail_report es llamado con [to_override]."""
        with patch.object(planner_import, "list_plans", new_callable=AsyncMock) as mock_list_plans, \
             patch.object(planner_import, "list_buckets", new_callable=AsyncMock) as mock_buckets, \
             patch.object(planner_import, "list_tasks", new_callable=AsyncMock) as mock_tasks, \
             patch.object(planner_import, "build_report_html") as mock_build, \
             patch.object(planner_import, "send_mail_report", new_callable=AsyncMock) as mock_send, \
             patch.object(planner_import, "resolve_guid_to_email", new_callable=AsyncMock) as mock_resolve, \
             patch.object(planner_import, "_print_plans_table"), \
             patch("builtins.print"), \
             patch("builtins.input", return_value="1"):

            mock_list_plans.return_value = [{"id": "p1", "title": "Test Plan"}]
            mock_buckets.return_value = [{"id": "b1", "name": "Backlog"}]
            mock_tasks.return_value = [
                {
                    "id": "t1",
                    "title": "Task",
                    "bucketId": "b1",
                    "assignments": {"guid1": {}},  # tiene asignado
                    "percentComplete": 0,
                }
            ]
            mock_build.return_value = "<html>test</html>"

            from planner_import import run_email_report

            await run_email_report("group-id", to_override="dmorales@grupoebi.cl", fetch_checklist=False)

            # send_mail_report debe ser llamado con [to_override]
            mock_send.assert_called_once()
            call_args = mock_send.call_args
            assert call_args[0][2] == ["dmorales@grupoebi.cl"]
            # resolve_guid_to_email NO debe ser llamado (bypass de resolución)
            mock_resolve.assert_not_called()

    async def test_to_override_skips_guid_resolution(self, fake_token):
        """Con to_override, resolve_guid_to_email NO es llamado."""
        with patch.object(planner_import, "list_plans", new_callable=AsyncMock) as mock_list_plans, \
             patch.object(planner_import, "list_buckets", new_callable=AsyncMock) as mock_buckets, \
             patch.object(planner_import, "list_tasks", new_callable=AsyncMock) as mock_tasks, \
             patch.object(planner_import, "build_report_html") as mock_build, \
             patch.object(planner_import, "send_mail_report", new_callable=AsyncMock) as mock_send, \
             patch.object(planner_import, "resolve_guid_to_email", new_callable=AsyncMock) as mock_resolve, \
             patch.object(planner_import, "_print_plans_table"), \
             patch("builtins.print"), \
             patch("builtins.input", return_value="1"):

            mock_list_plans.return_value = [{"id": "p1", "title": "Test Plan"}]
            mock_buckets.return_value = [{"id": "b1", "name": "Backlog"}]
            mock_tasks.return_value = [
                {
                    "id": "t1",
                    "title": "Task",
                    "bucketId": "b1",
                    "assignments": {"guid1": {}, "guid2": {}},  # múltiples asignados
                    "percentComplete": 0,
                }
            ]
            mock_build.return_value = "<html>test</html>"

            from planner_import import run_email_report

            await run_email_report("group-id", to_override="pm@example.com", fetch_checklist=False)

            # resolve_guid_to_email NO debe ser llamado
            mock_resolve.assert_not_called()
            # send_mail_report debe ser llamado con el email simple
            mock_send.assert_called_once()
            call_args = mock_send.call_args
            assert call_args[0][2] == ["pm@example.com"]


class TestRunEmailReportChecklistDefault:
    """fetch_checklist=True debe ser el default — get_task_details siempre se llama."""

    async def test_checklist_fetched_by_default(self, fake_token):
        """Sin pasar fetch_checklist, run_email_report llama get_task_details por cada tarea."""
        with patch.object(planner_import, "list_plans", new_callable=AsyncMock) as mock_plans, \
             patch.object(planner_import, "list_buckets", new_callable=AsyncMock) as mock_buckets, \
             patch.object(planner_import, "list_tasks", new_callable=AsyncMock) as mock_tasks, \
             patch.object(planner_import, "get_task_details", new_callable=AsyncMock) as mock_details, \
             patch.object(planner_import, "send_mail_report", new_callable=AsyncMock), \
             patch.object(planner_import, "_print_plans_table"), \
             patch("builtins.print"), \
             patch("builtins.input", return_value="1"):

            mock_plans.return_value = [{"id": "p1", "title": "Plan"}]
            mock_buckets.return_value = [{"id": "b1", "name": "Backlog"}]
            mock_tasks.return_value = [
                {"id": "t1", "title": "Task", "bucketId": "b1",
                 "assignments": {"guid1": {}}, "percentComplete": 0}
            ]
            mock_details.return_value = {"checklist": {}}  # sin ítems, pero se llamó

            from planner_import import run_email_report
            await run_email_report("group-id")   # sin pasar fetch_checklist explícito

            # get_task_details debe haberse llamado una vez (fetch_checklist=True es el default)
            mock_details.assert_called_once()


# ── Nuevos tests para _format_datetime, CommentCount, Checklist ─────────────────

class TestFormatDatetime:
    """Tests para la nueva función _format_datetime()."""

    def test_utc_z_format(self):
        """Convierte ISO 8601 Z a formato local dd-mm-yyyy hh:mm."""
        from planner_import import _format_datetime

        result = _format_datetime("2026-03-16T23:40:45Z")
        # Esperamos que contenga la fecha y hora (puede variar por zona horaria)
        assert "2026" in result or "03-2026" in result  # año presente
        assert ":" in result  # hora presente

    def test_empty_string_returns_dash(self):
        """Cadena vacía retorna '-'."""
        from planner_import import _format_datetime

        assert _format_datetime("") == "-"

    def test_invalid_returns_dash(self):
        """Formato inválido retorna '-'."""
        from planner_import import _format_datetime

        assert _format_datetime("no-es-fecha") == "-"


class TestCommentCount:
    """Tests para extracción de commentCount en enriquecimiento de tareas."""

    async def test_comment_count_extracted_from_task(self, fake_token):
        """commentCount en tarea → campo CommentCount en enriched_task."""
        with patch.object(planner_import, "list_plans", new_callable=AsyncMock) as mock_list, \
             patch.object(planner_import, "list_buckets", new_callable=AsyncMock) as mock_buckets, \
             patch.object(planner_import, "list_tasks", new_callable=AsyncMock) as mock_tasks, \
             patch.object(planner_import, "_print_report_table") as mock_table, \
             patch.object(planner_import, "_print_kpi_block"), \
             patch("builtins.print"), \
             patch("builtins.input", return_value="1"):

            mock_list.return_value = [{"id": "plan1", "title": "Plan"}]
            mock_buckets.return_value = [{"id": "bucket1", "name": "Backlog"}]
            mock_tasks.return_value = [
                {
                    "id": "task1",
                    "title": "Task with comments",
                    "bucketId": "bucket1",
                    "commentCount": 3,
                    "assignments": {},
                    "percentComplete": 50,
                }
            ]

            from planner_import import run_report

            await run_report("group1", fetch_comments=False, fetch_checklist=False)

            # Verificar que _print_report_table fue llamado
            mock_table.assert_called_once()
            tasks_arg = mock_table.call_args[0][2]
            assert len(tasks_arg) == 1
            assert tasks_arg[0]["CommentCount"] == 3

    async def test_comment_count_defaults_to_zero(self, fake_token):
        """Sin commentCount en tarea → CommentCount=0."""
        with patch.object(planner_import, "list_plans", new_callable=AsyncMock) as mock_list, \
             patch.object(planner_import, "list_buckets", new_callable=AsyncMock) as mock_buckets, \
             patch.object(planner_import, "list_tasks", new_callable=AsyncMock) as mock_tasks, \
             patch.object(planner_import, "_print_report_table") as mock_table, \
             patch.object(planner_import, "_print_kpi_block"), \
             patch("builtins.print"), \
             patch("builtins.input", return_value="1"):

            mock_list.return_value = [{"id": "plan1", "title": "Plan"}]
            mock_buckets.return_value = [{"id": "bucket1", "name": "Backlog"}]
            mock_tasks.return_value = [
                {
                    "id": "task1",
                    "title": "Task without commentCount",
                    "bucketId": "bucket1",
                    "assignments": {},
                    "percentComplete": 0,
                }
            ]

            from planner_import import run_report

            await run_report("group1", fetch_comments=False, fetch_checklist=False)

            tasks_arg = mock_table.call_args[0][2]
            assert tasks_arg[0]["CommentCount"] == 0


class TestChecklistInReport:
    """Tests para el nuevo parámetro --checklist en run_report."""

    async def test_checklist_calls_get_task_details(self, fake_token):
        """Con fetch_checklist=True, get_task_details es llamado por tarea."""
        with patch.object(planner_import, "list_plans", new_callable=AsyncMock) as mock_list, \
             patch.object(planner_import, "list_buckets", new_callable=AsyncMock) as mock_buckets, \
             patch.object(planner_import, "list_tasks", new_callable=AsyncMock) as mock_tasks, \
             patch.object(planner_import, "get_task_details", new_callable=AsyncMock) as mock_details, \
             patch.object(planner_import, "_print_report_table"), \
             patch.object(planner_import, "_print_kpi_block"), \
             patch("builtins.print"), \
             patch("builtins.input", return_value="1"):

            mock_list.return_value = [{"id": "plan1", "title": "Plan"}]
            mock_buckets.return_value = [{"id": "bucket1", "name": "Backlog"}]
            mock_tasks.return_value = [
                {
                    "id": "task1",
                    "title": "Task",
                    "bucketId": "bucket1",
                    "assignments": {},
                    "percentComplete": 50,
                }
            ]
            mock_details.return_value = {
                "checklist": {
                    "item1": {"title": "Do X", "isChecked": True},
                    "item2": {"title": "Do Y", "isChecked": False},
                    "item3": {"title": "Do Z", "isChecked": True},
                }
            }

            from planner_import import run_report

            await run_report("group1", fetch_comments=False, fetch_checklist=True)

            # get_task_details debe ser llamado para la tarea
            mock_details.assert_called()

    async def test_checklist_count_format(self, fake_token):
        """ChecklistDone=2, ChecklistTotal=5 → '2/5' en salida."""
        with patch.object(planner_import, "list_plans", new_callable=AsyncMock) as mock_list, \
             patch.object(planner_import, "list_buckets", new_callable=AsyncMock) as mock_buckets, \
             patch.object(planner_import, "list_tasks", new_callable=AsyncMock) as mock_tasks, \
             patch.object(planner_import, "get_task_details", new_callable=AsyncMock) as mock_details, \
             patch.object(planner_import, "_print_report_table") as mock_table, \
             patch.object(planner_import, "_print_kpi_block"), \
             patch("builtins.print"), \
             patch("builtins.input", return_value="1"):

            mock_list.return_value = [{"id": "plan1", "title": "Plan"}]
            mock_buckets.return_value = [{"id": "bucket1", "name": "Backlog"}]
            mock_tasks.return_value = [
                {
                    "id": "task1",
                    "title": "Task",
                    "bucketId": "bucket1",
                    "assignments": {},
                    "percentComplete": 50,
                }
            ]
            mock_details.return_value = {
                "checklist": {
                    "item1": {"isChecked": True},
                    "item2": {"isChecked": True},
                    "item3": {"isChecked": False},
                    "item4": {"isChecked": False},
                    "item5": {"isChecked": False},
                }
            }

            from planner_import import run_report

            await run_report("group1", fetch_comments=False, fetch_checklist=True)

            tasks_arg = mock_table.call_args[0][2]
            assert tasks_arg[0]["ChecklistDone"] == 2
            assert tasks_arg[0]["ChecklistTotal"] == 5

    async def test_checklist_skipped_without_flag(self, fake_token):
        """Sin --checklist, get_task_details NO es llamado."""
        with patch.object(planner_import, "list_plans", new_callable=AsyncMock) as mock_list, \
             patch.object(planner_import, "list_buckets", new_callable=AsyncMock) as mock_buckets, \
             patch.object(planner_import, "list_tasks", new_callable=AsyncMock) as mock_tasks, \
             patch.object(planner_import, "get_task_details", new_callable=AsyncMock) as mock_details, \
             patch.object(planner_import, "_print_report_table"), \
             patch.object(planner_import, "_print_kpi_block"), \
             patch("builtins.print"), \
             patch("builtins.input", return_value="1"):

            mock_list.return_value = [{"id": "plan1", "title": "Plan"}]
            mock_buckets.return_value = [{"id": "bucket1", "name": "Backlog"}]
            mock_tasks.return_value = [
                {
                    "id": "task1",
                    "title": "Task",
                    "bucketId": "bucket1",
                    "assignments": {},
                    "percentComplete": 50,
                }
            ]

            from planner_import import run_report

            await run_report("group1", fetch_comments=False, fetch_checklist=False)

            # get_task_details NO debe ser llamado
            mock_details.assert_not_called()


class TestResolveGuidToDisplayName:
    """Tests para la nueva función resolve_guid_to_display_name()."""

    async def test_returns_display_name(self, fake_token):
        """Devuelve displayName de la respuesta de Graph."""
        mock_client = AsyncMock()
        mock_response = {
            "id": "guid-123",
            "displayName": "Diego Morales",
            "givenName": "Diego",
            "surname": "Morales",
        }

        with patch.object(planner_import, "graph_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = mock_response

            result = await planner_import.resolve_guid_to_display_name(
                mock_client, fake_token, "guid-123"
            )

            assert result == "Diego Morales"
            mock_req.assert_called_once()

    async def test_returns_none_on_404(self, fake_token):
        """Retorna None si Graph API retorna 404."""
        mock_client = AsyncMock()

        with patch.object(
            planner_import, "graph_request", new_callable=AsyncMock
        ) as mock_req:
            mock_req.side_effect = httpx.HTTPStatusError(
                "404", request=AsyncMock(), response=AsyncMock(status_code=404)
            )

            result = await planner_import.resolve_guid_to_display_name(
                mock_client, fake_token, "invalid-guid"
            )

            assert result is None

    async def test_uses_cache_on_second_call(self, fake_token):
        """Segunda llamada usa caché, no llama a Graph."""
        mock_client = AsyncMock()
        mock_response = {"displayName": "Test User"}

        with patch.object(planner_import, "graph_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = mock_response

            # Primera llamada
            result1 = await planner_import.resolve_guid_to_display_name(
                mock_client, fake_token, "guid-cache-test"
            )

            # Segunda llamada
            result2 = await planner_import.resolve_guid_to_display_name(
                mock_client, fake_token, "guid-cache-test"
            )

            assert result1 == "Test User"
            assert result2 == "Test User"
            # graph_request solo debe llamarse una vez (primera llamada)
            assert mock_req.call_count == 1


class TestBuildReportHtmlBucketOrder:
    """Test para verificar ordenamiento de buckets en HTML."""

    def test_backlog_before_gateway(self):
        """Tareas Backlog aparecen antes que Gateway."""
        tasks = [
            {
                "id": "task1",
                "title": "Gateway Task",
                "bucketId": "bucket-gateway",
                "percentComplete": 50,
                "assignments": {},
                "dueDateTime": None,
                "createdDateTime": "2026-01-01T00:00:00Z",
                "lastModifiedDateTime": "2026-01-01T00:00:00Z",
                "CommentCount": 0,
                "ChecklistDone": 0,
                "ChecklistTotal": 0,
            },
            {
                "id": "task2",
                "title": "Backlog Task",
                "bucketId": "bucket-backlog",
                "percentComplete": 0,
                "assignments": {},
                "dueDateTime": None,
                "createdDateTime": "2026-01-01T00:00:00Z",
                "lastModifiedDateTime": "2026-01-01T00:00:00Z",
                "CommentCount": 0,
                "ChecklistDone": 0,
                "ChecklistTotal": 0,
            },
        ]
        buckets_dict = {
            "bucket-backlog": "Backlog",
            "bucket-gateway": "Gateway",
        }

        html = planner_import.build_report_html("Test Plan", buckets_dict, tasks, "15-01-2026")

        # Encontrar índices de aparición
        backlog_idx = html.find("Backlog Task")
        gateway_idx = html.find("Gateway Task")

        # Backlog debe aparecer antes que Gateway
        assert backlog_idx > 0, "Backlog Task no encontrada"
        assert gateway_idx > 0, "Gateway Task no encontrada"
        assert backlog_idx < gateway_idx, "Backlog debe aparecer antes que Gateway"


class TestBuildReportHtmlCreatedColumn:
    """Test para verificar columna 'Creado' en HTML."""


# ── Fixes Round 2: Tests para columnas %, Modificado, y colores ─────────────────

class TestPercentColumnWithChecklist:
    """Fix 1: Columna % usa ratio de checklist, no percentComplete."""

    def test_percent_column_shows_checklist_ratio(self):
        """Tarea con ChecklistDone=3, ChecklistTotal=5 → columna % muestra 60%."""
        tasks = [
            {
                "id": "task1",
                "title": "Task with Checklist",
                "bucketId": "bucket1",
                "percentComplete": 50,  # valor manual del PM (irrelevante)
                "assignments": {},
                "dueDateTime": None,
                "createdDateTime": "2026-01-15T10:30:00Z",
                "lastModifiedDateTime": "2026-01-15T10:30:00Z",
                "CommentCount": 0,
                "ChecklistDone": 3,
                "ChecklistTotal": 5,
            }
        ]
        buckets_dict = {"bucket1": "Backlog"}
        html = planner_import.build_report_html("Test Plan", buckets_dict, tasks, "15-01-2026")
        # La columna % debe mostrar "60%" (3/5)
        assert "60%" in html, "Columna % no muestra ratio de checklist"

    def test_percent_column_shows_percent_without_checklist(self):
        """Tarea sin checklist pero con percentComplete → columna % muestra percentComplete."""
        tasks = [
            {
                "id": "task1",
                "title": "Task without Checklist",
                "bucketId": "bucket1",
                "percentComplete": 50,
                "assignments": {},
                "dueDateTime": None,
                "createdDateTime": "2026-01-15T10:30:00Z",
                "lastModifiedDateTime": "2026-01-15T10:30:00Z",
                "CommentCount": 0,
                "ChecklistDone": 0,
                "ChecklistTotal": 0,
            }
        ]
        buckets_dict = {"bucket1": "Backlog"}
        html = planner_import.build_report_html("Test Plan", buckets_dict, tasks, "15-01-2026")
        # Verificar que la columna % muestra percentComplete (50%)
        assert "Task without Checklist" in html
        # La columna % debe mostrar "50%" porque percentComplete=50
        assert "<td style=\"text-align: center;\">50%</td>" in html

    def test_percent_column_shows_dash_without_checklist_without_percent(self):
        """Tarea sin checklist y sin percentComplete → columna % muestra '-'."""
        tasks = [
            {
                "id": "task2",
                "title": "Task Zero Progress",
                "bucketId": "bucket1",
                "percentComplete": 0,
                "assignments": {},
                "dueDateTime": None,
                "createdDateTime": "2026-01-15T10:30:00Z",
                "lastModifiedDateTime": "2026-01-15T10:30:00Z",
                "CommentCount": 0,
                "ChecklistDone": 0,
                "ChecklistTotal": 0,
            }
        ]
        buckets_dict = {"bucket1": "Backlog"}
        html = planner_import.build_report_html("Test Plan", buckets_dict, tasks, "15-01-2026")
        # Verificar que la columna % muestra "-" para 0% sin checklist
        assert "Task Zero Progress" in html
        # La columna % debe mostrar "-" porque percentComplete=0 y sin checklist
        assert "<td style=\"text-align: center;\">-</td>" in html




class TestTaskRowColors:
    """Fix 4.3: Colores de fila alineados con chart."""

    def test_row_color_completed_is_green(self):
        """Tarea completada (percentComplete=100) → fondo verde."""
        tasks = [
            {
                "id": "task1",
                "title": "Completed Task",
                "bucketId": "bucket1",
                "percentComplete": 100,
                "assignments": {},
                "dueDateTime": None,
                "createdDateTime": "2026-01-15T10:30:00Z",
                "lastModifiedDateTime": "2026-01-15T10:30:00Z",
                "CommentCount": 0,
                "ChecklistDone": 0,
                "ChecklistTotal": 0,
            }
        ]
        buckets_dict = {"bucket1": "Backlog"}
        html = planner_import.build_report_html("Test Plan", buckets_dict, tasks, "15-01-2026")
        # Buscar color verde #c8e6c8 en la fila
        assert '#c8e6c8' in html, "Color verde para tarea completada no encontrado"

    def test_row_color_in_progress_is_orange(self):
        """Tarea en progreso (0 < percentComplete < 100) → fondo naranja."""
        tasks = [
            {
                "id": "task1",
                "title": "In Progress Task",
                "bucketId": "bucket1",
                "percentComplete": 50,  # En progreso
                "assignments": {},
                "dueDateTime": None,
                "createdDateTime": "2026-01-15T10:30:00Z",
                "lastModifiedDateTime": "2026-01-15T10:30:00Z",
                "CommentCount": 0,
                "ChecklistDone": 0,
                "ChecklistTotal": 0,
            }
        ]
        buckets_dict = {"bucket1": "Backlog"}
        html = planner_import.build_report_html("Test Plan", buckets_dict, tasks, "15-01-2026")
        # Buscar color naranja #ffe0b0 en la fila
        assert '#ffe0b0' in html, "Color naranja para tarea en progreso no encontrado"

    def test_row_color_overdue_is_red(self):
        """Tarea vencida (due < today, percentComplete < 100) → fondo rojo."""
        from datetime import date, timedelta
        yesterday = (date.today() - timedelta(days=1)).strftime("%Y-%m-%d")

        tasks = [
            {
                "id": "task1",
                "title": "Overdue Task",
                "bucketId": "bucket1",
                "percentComplete": 30,  # No completada
                "assignments": {},
                "dueDateTime": f"{yesterday}T00:00:00Z",  # vencida
                "createdDateTime": "2026-01-15T10:30:00Z",
                "lastModifiedDateTime": "2026-01-15T10:30:00Z",
                "CommentCount": 0,
                "ChecklistDone": 0,
                "ChecklistTotal": 0,
            }
        ]
        buckets_dict = {"bucket1": "Backlog"}
        html = planner_import.build_report_html("Test Plan", buckets_dict, tasks, "15-01-2026")
        # Buscar color rojo #f9d0d0 en la fila
        assert '#f9d0d0' in html, "Color rojo para tarea vencida no encontrado"

    def test_row_color_not_started_is_gray(self):
        """Tarea sin iniciar (percentComplete=0) → fondo gris."""
        tasks = [
            {
                "id": "task1",
                "title": "Not Started Task",
                "bucketId": "bucket1",
                "percentComplete": 0,  # Sin iniciar
                "assignments": {},
                "dueDateTime": None,
                "createdDateTime": "2026-01-15T10:30:00Z",
                "lastModifiedDateTime": "2026-01-15T10:30:00Z",
                "CommentCount": 0,
                "ChecklistDone": 0,
                "ChecklistTotal": 0,
            }
        ]
        buckets_dict = {"bucket1": "Backlog"}
        html = planner_import.build_report_html("Test Plan", buckets_dict, tasks, "15-01-2026")
        # Buscar color gris #e8e8e8 en la fila
        assert '#e8e8e8' in html, "Color gris para tarea sin iniciar no encontrado"


class TestStatusBadgeVibrantColors:
    """Fix 4.4: Status badges con colores vibrantes."""

    def test_status_badge_completada_white_on_green(self):
        """Completada: texto blanco sobre fondo verde #107c10."""
        from planner_import import _status_badge
        badge = _status_badge(100)
        assert "#107c10" in badge, "Color de fondo para 'Completada' incorrecto"
        assert "Completada" in badge
        assert "white" in badge, "Color de texto debe ser blanco"

    def test_status_badge_en_progreso_dark_on_orange(self):
        """En Progreso: texto oscuro sobre naranja #e07800."""
        from planner_import import _status_badge
        badge = _status_badge(50)
        assert "#e07800" in badge, "Color de fondo para 'En Progreso' incorrecto"
        assert "En Progreso" in badge

    def test_status_badge_sin_iniciar_white_on_gray(self):
        """Sin Iniciar: texto blanco sobre gris #605e5c (Fix Round 3)."""
        from planner_import import _status_badge
        badge = _status_badge(0)
        assert "#605e5c" in badge, "Color de fondo para 'Sin Iniciar' incorrecto"
        assert "Sin Iniciar" in badge
        assert "white" in badge, "Color de texto debe ser blanco para mejor contraste"


class TestLayoutKPI50Plus50:
    """Fix 4.1: Layout 50/50 KPI + Chart."""

    def test_html_contains_50_50_table_layout(self):
        """HTML contiene tabla con width 50% para KPI y 50% para Chart."""
        tasks = [
            {
                "id": "task1",
                "title": "Test Task",
                "bucketId": "bucket1",
                "percentComplete": 50,
                "assignments": {},
                "dueDateTime": None,
                "createdDateTime": "2026-01-15T10:30:00Z",
                "lastModifiedDateTime": "2026-01-15T10:30:00Z",
                "CommentCount": 0,
                "ChecklistDone": 0,
                "ChecklistTotal": 0,
            }
        ]
        buckets_dict = {"bucket1": "Backlog"}
        html = planner_import.build_report_html("Test Plan", buckets_dict, tasks, "15-01-2026")
        # Verificar que hay dos columnas de 50%
        assert 'width="50%"' in html, "Layout 50/50 no encontrado en HTML"
        # Verificar que hay un SVG donut
        assert '<svg' in html, "SVG donut no encontrado"

    def test_donut_svg_is_150x150(self):
        """SVG donut es 150×150 (no 100×100)."""
        from planner_import import _build_donut_svg
        svg = _build_donut_svg(1, 1, 1, 1, 4)
        assert 'width="150"' in svg, "SVG width no es 150"
        assert 'height="150"' in svg, "SVG height no es 150"

    def test_kpi_cards_in_left_column(self):
        """KPI cards están en columna izquierda (Fix Round 3: grid 2x2 con border-left:4px)."""
        tasks = [
            {
                "id": "task1",
                "title": "Test Task",
                "bucketId": "bucket1",
                "percentComplete": 50,
                "assignments": {},
                "dueDateTime": None,
                "createdDateTime": "2026-01-15T10:30:00Z",
                "lastModifiedDateTime": "2026-01-15T10:30:00Z",
                "CommentCount": 0,
                "ChecklistDone": 0,
                "ChecklistTotal": 0,
            }
        ]
        buckets_dict = {"bucket1": "Backlog"}
        html = planner_import.build_report_html("Test Plan", buckets_dict, tasks, "15-01-2026")
        # Verificar que hay KPI cards con estilos de border-left en el grid 2x2
        assert 'border-left:4px solid' in html, "KPI cards grid con border-left:4px no encontrados"
        # Verificar Total con border-left:5px (en la fila superior)
        assert 'border-left:5px solid #0078d4' in html, "Total card no encontrado"

    def test_total_card_on_top(self):
        """Total card aparece primero en columna izquierda (Fix Round 3)."""
        tasks = [
            {
                "id": "task1",
                "title": "Test Task",
                "bucketId": "bucket1",
                "percentComplete": 50,
                "assignments": {},
                "dueDateTime": None,
                "createdDateTime": "2026-01-15T10:30:00Z",
                "lastModifiedDateTime": "2026-01-15T10:30:00Z",
                "CommentCount": 0,
                "ChecklistDone": 0,
                "ChecklistTotal": 0,
            }
        ]
        buckets_dict = {"bucket1": "Backlog"}
        html = planner_import.build_report_html("Test Plan", buckets_dict, tasks, "15-01-2026")
        # Verificar que Total aparece antes del grid 2x2
        total_idx = html.find('border-left:5px solid #0078d4')
        grid_idx = html.find('border-left:4px solid #107c10')
        assert total_idx > 0, "Total card no encontrado"
        assert grid_idx > 0, "Grid 2x2 no encontrado"
        assert total_idx < grid_idx, "Total debe aparecer antes del grid 2x2"

    def test_footer_contains_author(self):
        """Footer contiene texto de autoría de Diego Morales (Fix Round 3)."""
        tasks = [
            {
                "id": "task1",
                "title": "Test Task",
                "bucketId": "bucket1",
                "percentComplete": 50,
                "assignments": {},
                "dueDateTime": None,
                "createdDateTime": "2026-01-15T10:30:00Z",
                "lastModifiedDateTime": "2026-01-15T10:30:00Z",
                "CommentCount": 0,
                "ChecklistDone": 0,
                "ChecklistTotal": 0,
            }
        ]
        buckets_dict = {"bucket1": "Backlog"}
        html = planner_import.build_report_html("Test Plan", buckets_dict, tasks, "15-01-2026")
        # Verificar que footer contiene el nombre del autor
        assert "Diego Morales" in html, "Nombre de autor 'Diego Morales' no encontrado en footer"
        assert "Project Manager 2026" in html, "Título 'Project Manager 2026' no encontrado"
        assert "automatización de procesos" in html, "Descripción de automatización no encontrada"


class TestKPIProximas7Dias:
    """Tests para el nuevo KPI 'Próximas a vencer en 7 días'."""

    def test_kpi_proximas_a_vencer_appears_in_html(self):
        """El stat card 'Vencen en 7 días' aparece en el HTML con el count correcto."""
        today = date.today()
        # Tarea que vence en 3 días, sin completar
        tarea_en_ventana = {
            "id": "task1",
            "bucketId": "bucket1",
            "title": "Tarea que vence pronto",
            "percentComplete": 50,
            "dueDateTime": (today + timedelta(days=3)).isoformat() + "T00:00:00Z",
            "assignments": {},
            "ChecklistDone": 0,
            "ChecklistTotal": 0,
        }
        # Tarea que vence en 10 días, sin completar (fuera de ventana de 7 días)
        tarea_fuera_ventana = {
            "id": "task2",
            "bucketId": "bucket1",
            "title": "Tarea que vence lejos",
            "percentComplete": 50,
            "dueDateTime": (today + timedelta(days=10)).isoformat() + "T00:00:00Z",
            "assignments": {},
            "ChecklistDone": 0,
            "ChecklistTotal": 0,
        }
        # Tarea completada que vence en 2 días (no cuenta porque está completada)
        tarea_completada = {
            "id": "task3",
            "bucketId": "bucket1",
            "title": "Tarea completada pronto",
            "percentComplete": 100,
            "dueDateTime": (today + timedelta(days=2)).isoformat() + "T00:00:00Z",
            "assignments": {},
            "ChecklistDone": 0,
            "ChecklistTotal": 0,
        }
        tasks = [tarea_en_ventana, tarea_fuera_ventana, tarea_completada]
        buckets_dict = {"bucket1": "Backlog"}

        html = planner_import.build_report_html("Test Plan", buckets_dict, tasks, "15-01-2026", proximas_7d=1)

        # Verificar que el stat card contiene el número correcto y el texto
        assert "Vencen en 7 días" in html, "Texto 'Vencen en 7 días' no encontrado en HTML"
        assert ">1</span>" in html or ">1<" in html, "Número 1 no encontrado para próximas a vencer"

    def test_kpi_proximas_a_vencer_zero_when_none(self):
        """El stat card muestra 0 cuando no hay tareas próximas a vencer."""
        tasks = [
            {
                "id": "task1",
                "bucketId": "bucket1",
                "title": "Tarea lejana",
                "percentComplete": 50,
                "dueDateTime": (date.today() + timedelta(days=15)).isoformat() + "T00:00:00Z",
                "assignments": {},
                "ChecklistDone": 0,
                "ChecklistTotal": 0,
            }
        ]
        buckets_dict = {"bucket1": "Backlog"}

        html = planner_import.build_report_html("Test Plan", buckets_dict, tasks, "15-01-2026", proximas_7d=0)

        # Verificar que el stat card contiene 0
        assert "Vencen en 7 días" in html, "Texto 'Vencen en 7 días' no encontrado"
        assert ">0</span>" in html or ">0<" in html, "Número 0 no encontrado para próximas a vencer"


class TestOutlookFallback:
    """Tests para fallback de Outlook — conditional comments y barra HTML."""

    def test_donut_output_contains_mso_conditional(self):
        """Verifica que el SVG tenga conditional comments para Outlook."""
        result = planner_import._build_donut_svg(5, 3, 2, 1, 11)
        assert "<!--[if mso]>" in result, "Conditional comment para MSO no encontrado"
        assert "<!--[if !mso]><!-->" in result, "Conditional comment para no-MSO no encontrado"
        assert "<!--<![endif]-->" in result, "Cierre de conditional comment no encontrado"

    def test_donut_output_still_contains_svg(self):
        """Verifica que el SVG no haya desaparecido en clientes modernos."""
        result = planner_import._build_donut_svg(5, 3, 2, 1, 11)
        assert '<svg width="150" height="150"' in result, "SVG desapareció"
        assert "<circle" in result, "Paths SVG no encontrados"

    def test_outlook_fallback_has_four_colors(self):
        """Verifica que la barra HTML de Outlook tenga los 4 colores cuando todos > 0."""
        result = planner_import._build_outlook_bar_fallback(5, 3, 2, 1, 11)
        assert "#107c10" in result, "Color verde (completadas) no encontrado"
        assert "#ff8c00" in result, "Color naranja (en progreso) no encontrado"
        assert "#8a8886" in result, "Color gris (sin iniciar) no encontrado"
        assert "#d13438" in result, "Color rojo (vencidas) no encontrado"

    def test_outlook_fallback_omits_zero_segment(self):
        """Verifica que segmentos con count=0 no se emitan en la barra."""
        result = planner_import._build_outlook_bar_fallback(5, 3, 0, 0, 8)
        # Contar celdas <td> en la barra (deberían ser 2, no 4)
        td_count = result.count("<td")
        assert td_count == 2, f"Se esperaban 2 celdas (5+3), pero se encontraron {td_count}"

    def test_outlook_fallback_total_zero_shows_gray_bar(self):
        """Verifica que total=0 muestre barra gris con 'Sin datos'."""
        result = planner_import._build_outlook_bar_fallback(0, 0, 0, 0, 0)
        assert "Sin datos" in result, "Texto 'Sin datos' no encontrado para total=0"
        assert "#f3f2f1" in result, "Color gris de fondo no encontrado"

    def test_outlook_fallback_bar_widths_sum_to_100(self):
        """Verifica que los anchos de las celdas sumen exactamente 100%."""
        result = planner_import._build_outlook_bar_fallback(25, 25, 25, 25, 100)
        # Extraer los width atributos de las celdas de la barra
        import re
        widths = re.findall(r'width="(\d+)%"', result)
        # Deberían haber 4 celdas con 25% cada una
        assert len(widths) == 4, f"Se esperaban 4 celdas, se encontraron {len(widths)}"
        bar_widths = [int(w) for w in widths]
        assert sum(bar_widths) == 100, f"Los anchos no suman 100: {bar_widths}"

    def test_outlook_fallback_returns_only_bar_no_legend(self):
        """Verifica que el fallback NO incluye leyenda (proporcionada por build_report_html)."""
        result = planner_import._build_outlook_bar_fallback(20, 10, 5, 5, 40)
        # NO debe contener "Completado:" (que era parte de la leyenda removida)
        assert "Completado:" not in result, "Fallback no debe incluir leyenda"
        # Pero SÍ debe tener la barra de colores
        assert "<table" in result, "Fallback debe contener tabla de barra"

    def test_conditional_comments_correctly_nested(self):
        """Verifica que los conditional comments estén correctamente anidados."""
        result = planner_import._build_donut_svg(10, 5, 3, 2, 20)
        # El SVG debe estar DENTRO de <!--[if !mso]><!--> ... <!--<![endif]-->
        # El fallback debe estar DENTRO de <!--[if mso]> ... <![endif]-->
        assert result.index("<!--[if !mso]><!-->") < result.index("<svg"), "SVG no está dentro del conditional !mso"
        assert result.index("<!--[if mso]>") < result.index("<table"), "Fallback no está dentro del conditional mso"
        assert result.rindex("<![endif]-->") > result.rindex("</table>"), "Cierre no está después del fallback"


class TestAssigneeDisplayLogic:
    """Verifica que el nombre del asignado se muestra siempre completo."""

    def test_single_assignee_shows_full_name(self):
        """Valida que un nombre largo se muestra sin truncamiento."""
        names_map = {"guid1": "Diego Elias Morales Contreras"}
        assignments = {"guid1": {}}
        assignee_names = [names_map.get(g, g[:12]) for g in assignments.keys()]
        result = ", ".join(assignee_names) if assignee_names else "(sin asignar)"
        assert result == "Diego Elias Morales Contreras"

    def test_multiple_assignees_shows_full_names(self):
        """Valida que múltiples asignados se muestran con nombres completos."""
        names_map = {"guid1": "Diego Elias Morales Contreras", "guid2": "Ana Gomez"}
        assignments = {"guid1": {}, "guid2": {}}
        assignee_names = [names_map.get(g, g[:12]) for g in assignments.keys()]
        result = ", ".join(assignee_names) if assignee_names else "(sin asignar)"
        assert "Diego Elias Morales Contreras" in result
        assert "Ana Gomez" in result

    def test_empty_assignments_shows_sin_asignar(self):
        """Valida que sin asignados muestra '(sin asignar)'."""
        assignee_names = []
        result = ", ".join(assignee_names) if assignee_names else "(sin asignar)"
        assert result == "(sin asignar)"


class TestTaskTitleLink:
    """Verifica que el título de cada tarea incluye un deep-link a Planner."""

    def test_task_title_has_link_when_id_present(self):
        """Con task_id presente, el HTML incluye href a tasks.office.com."""
        tasks = [
            {
                "id": "abc123",
                "title": "Mi tarea",
                "bucketId": "b1",
                "percentComplete": 0,
                "assignments": {},
                "AssigneeDisplay": "(sin asignar)",
                "ChecklistDone": 0,
                "ChecklistTotal": 0,
            }
        ]
        html = planner_import.build_report_html(
            "Plan", {"b1": "Bucket"}, tasks, "2026-03-19"
        )
        assert 'href="https://tasks.office.com/Home/Task/abc123"' in html
        assert 'target="_blank"' in html

    def test_task_title_plain_text_when_no_id(self):
        """Sin task_id, el título se muestra como texto plano (sin <a>)."""
        tasks = [
            {
                "id": "",
                "title": "Mi tarea",
                "bucketId": "b1",
                "percentComplete": 0,
                "assignments": {},
                "AssigneeDisplay": "(sin asignar)",
                "ChecklistDone": 0,
                "ChecklistTotal": 0,
            }
        ]
        html = planner_import.build_report_html(
            "Plan", {"b1": "Bucket"}, tasks, "2026-03-19"
        )
        assert "tasks.office.com" not in html
        assert "Mi tarea" in html
