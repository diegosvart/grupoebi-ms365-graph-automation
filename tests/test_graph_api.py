"""Tests de graph_request, list_plans, delete_plan, create_plan, create_bucket,
resolve_email_to_guid, create_task_full, get_task_details, _print_report_table,
run_report — sin red real."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, call, patch

import httpx
import pytest

import planner_import
from planner_import import (
    GRAPH_BASE,
    _derive_task_status,
    _print_report_table,
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
    run_report,
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

    async def test_endpoint_url_no_select(self, fake_token):
        """URL no incluye $select (Microsoft Graph devuelve campos por defecto)."""
        client = await _make_client([_make_response(200, {"value": []})])
        await list_tasks(client, fake_token, "plan-123")
        args, _ = client.request.call_args
        url: str = args[1]
        assert "$select" not in url

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

    def test_modified_column_appears(self, capsys):
        """Columna 'Modificado' aparece en la salida."""
        tasks = [
            {
                "title": "Tarea",
                "bucketId": "b1",
                "percentComplete": 0,
                "assignments": {},
                "lastModifiedDateTime": "2026-03-10T15:30:00Z",
            }
        ]
        buckets_dict = {"b1": "Backlog"}
        planner_import._print_report_table("Plan Test", buckets_dict, tasks)
        captured = capsys.readouterr()
        assert "Modificado" in captured.out
        assert "2026-03-10" in captured.out

    def test_task_without_last_modified_shows_dash(self, capsys):
        """lastModifiedDateTime ausente → imprime '-'."""
        tasks = [
            {
                "title": "Tarea",
                "bucketId": "b1",
                "percentComplete": 0,
                "assignments": {},
            }
        ]
        buckets_dict = {"b1": "Backlog"}
        planner_import._print_report_table("Plan Test", buckets_dict, tasks)
        captured = capsys.readouterr()
        # Debe haber un dash en la columna Modificado
        lines = [l for l in captured.out.split("\n") if "Tarea" in l]
        assert len(lines) > 0
        # Verificar que hay un dash en el campo de fecha modificada
        assert "-" in captured.out


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

    async def test_csv_includes_all_comment_columns(self, mock_auth, monkeypatch, tmp_path):
        """CSV siempre incluye LastCommentText y LastCommentDate, incluso sin --comments."""
        csv_path = tmp_path / "test_report.csv"
        plans = [{"id": "p1", "title": "Plan 1"}]
        buckets = [{"id": "b1", "name": "Backlog"}]
        tasks = [
            {
                "id": "t1",
                "title": "Task 1",
                "bucketId": "b1",
                "conversationThreadId": "thread-123",
                "assignments": {"user-1": {}},
                "percentComplete": 50,
                "dueDateTime": "2026-03-30T00:00:00Z",
                "createdDateTime": "2026-03-01T00:00:00Z",
                "lastModifiedDateTime": "2026-03-10T00:00:00Z",
            }
        ]
        with patch.object(planner_import, "list_plans", new_callable=AsyncMock) as mock_list:
            with patch.object(planner_import, "list_buckets", new_callable=AsyncMock) as mock_buckets:
                with patch.object(planner_import, "list_tasks", new_callable=AsyncMock) as mock_tasks:
                    mock_list.return_value = plans
                    mock_buckets.return_value = buckets
                    mock_tasks.return_value = tasks
                    monkeypatch.setattr("builtins.input", lambda _: "1")

                    await planner_import.run_report("group-id", export_csv=csv_path, fetch_comments=False)

                    assert csv_path.exists()
                    content = csv_path.read_text(encoding="utf-8")
                    assert "LastCommentText" in content
                    assert "LastCommentDate" in content
