"""Tests de graph_request, list_plans, delete_plan, create_plan, create_bucket,
resolve_email_to_guid y create_task_full — sin red real."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, call, patch

import httpx
import pytest

import planner_import
from planner_import import (
    GRAPH_BASE,
    create_bucket,
    create_plan,
    create_task_full,
    delete_plan,
    graph_request,
    list_plans,
    resolve_email_to_guid,
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
