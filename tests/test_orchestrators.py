"""Tests de orquestadores: run_list, run_delete, run_import_* — dry_run sin API."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import planner_import
from planner_import import (
    run_delete,
    run_import_buckets,
    run_import_full,
    run_import_plan,
    run_import_tasks,
    run_list,
)
from tests.conftest import make_async_client_ctx


# ── run_list ──────────────────────────────────────────────────────────────────

class TestRunList:
    async def test_no_filter_prints_all_plans(self, capsys, mock_auth, sample_plans):
        mock_client = MagicMock()

        with (
            patch("planner_import.httpx.AsyncClient", return_value=make_async_client_ctx(mock_client)),
            patch("planner_import.list_plans", new=AsyncMock(return_value=sample_plans)),
        ):
            await run_list("group-id")

        out = capsys.readouterr().out
        assert "Planes encontrados: 2" in out
        assert "Plan Alpha" in out
        assert "Plan Beta" in out

    async def test_filter_shows_only_matching_plan(self, capsys, mock_auth, sample_plans):
        mock_client = MagicMock()

        with (
            patch("planner_import.httpx.AsyncClient", return_value=make_async_client_ctx(mock_client)),
            patch("planner_import.list_plans", new=AsyncMock(return_value=sample_plans)),
        ):
            await run_list("group-id", filter_text="Alpha")

        out = capsys.readouterr().out
        assert "Plan Alpha" in out
        assert "Plan Beta" not in out

    async def test_filter_no_match_shows_zero(self, capsys, mock_auth, sample_plans):
        mock_client = MagicMock()

        with (
            patch("planner_import.httpx.AsyncClient", return_value=make_async_client_ctx(mock_client)),
            patch("planner_import.list_plans", new=AsyncMock(return_value=sample_plans)),
        ):
            await run_list("group-id", filter_text="Inexistente")

        out = capsys.readouterr().out
        assert "Planes encontrados: 0" in out


# ── run_delete ────────────────────────────────────────────────────────────────

class TestRunDelete:
    async def test_dry_run_does_not_call_delete_plan(self, capsys, mock_auth, sample_plans):
        mock_client = MagicMock()
        mock_delete = AsyncMock()

        with (
            patch("planner_import.httpx.AsyncClient", return_value=make_async_client_ctx(mock_client)),
            patch("planner_import.list_plans", new=AsyncMock(return_value=sample_plans)),
            patch("planner_import.delete_plan", mock_delete),
            patch("builtins.input", return_value="1"),
        ):
            result = await run_delete("group-id", dry_run=True)

        mock_delete.assert_not_called()
        assert result["deleted"] == []

    async def test_confirm_n_does_not_delete(self, capsys, mock_auth, sample_plans):
        mock_client = MagicMock()
        mock_delete = AsyncMock()
        inputs = iter(["1", "n"])

        with (
            patch("planner_import.httpx.AsyncClient", return_value=make_async_client_ctx(mock_client)),
            patch("planner_import.list_plans", new=AsyncMock(return_value=sample_plans)),
            patch("planner_import.delete_plan", mock_delete),
            patch("builtins.input", side_effect=inputs),
        ):
            result = await run_delete("group-id")

        mock_delete.assert_not_called()
        assert result["deleted"] == []

    async def test_empty_selection_prints_sin_seleccion(self, capsys, mock_auth, sample_plans):
        mock_client = MagicMock()

        with (
            patch("planner_import.httpx.AsyncClient", return_value=make_async_client_ctx(mock_client)),
            patch("planner_import.list_plans", new=AsyncMock(return_value=sample_plans)),
            patch("builtins.input", return_value=""),
        ):
            result = await run_delete("group-id")

        out = capsys.readouterr().out
        assert "Sin selección" in out
        assert result["deleted"] == []

    async def test_select_1_and_2_confirms_deletes_both(self, mock_auth, sample_plans):
        mock_client = MagicMock()
        mock_delete = AsyncMock()
        inputs = iter(["1,2", "s"])

        with (
            patch("planner_import.httpx.AsyncClient", return_value=make_async_client_ctx(mock_client)),
            patch("planner_import.list_plans", new=AsyncMock(return_value=sample_plans)),
            patch("planner_import.delete_plan", mock_delete),
            patch("planner_import.asyncio.sleep", new_callable=AsyncMock),
            patch("builtins.input", side_effect=inputs),
        ):
            result = await run_delete("group-id")

        assert mock_delete.call_count == 2
        assert "plan-id-001" in result["deleted"]
        assert "plan-id-002" in result["deleted"]

    async def test_todos_deletes_all_plans(self, mock_auth, sample_plans):
        mock_client = MagicMock()
        mock_delete = AsyncMock()
        inputs = iter(["todos", "s"])

        with (
            patch("planner_import.httpx.AsyncClient", return_value=make_async_client_ctx(mock_client)),
            patch("planner_import.list_plans", new=AsyncMock(return_value=sample_plans)),
            patch("planner_import.delete_plan", mock_delete),
            patch("planner_import.asyncio.sleep", new_callable=AsyncMock),
            patch("builtins.input", side_effect=inputs),
        ):
            result = await run_delete("group-id")

        assert mock_delete.call_count == len(sample_plans)

    async def test_error_in_one_plan_continues_and_reports(self, mock_auth, sample_plans):
        mock_client = MagicMock()
        inputs = iter(["1,2", "s"])

        async def delete_side_effect(client, token, plan_id):
            if plan_id == "plan-id-001":
                raise Exception("API error")

        with (
            patch("planner_import.httpx.AsyncClient", return_value=make_async_client_ctx(mock_client)),
            patch("planner_import.list_plans", new=AsyncMock(return_value=sample_plans)),
            patch("planner_import.delete_plan", side_effect=delete_side_effect),
            patch("planner_import.asyncio.sleep", new_callable=AsyncMock),
            patch("builtins.input", side_effect=inputs),
        ):
            result = await run_delete("group-id")

        assert "plan-id-002" in result["deleted"]
        assert len(result["errors"]) == 1
        assert "Plan Alpha" in result["errors"][0]

    async def test_no_plans_prints_no_encontraron(self, capsys, mock_auth):
        mock_client = MagicMock()

        with (
            patch("planner_import.httpx.AsyncClient", return_value=make_async_client_ctx(mock_client)),
            patch("planner_import.list_plans", new=AsyncMock(return_value=[])),
        ):
            result = await run_delete("group-id")

        out = capsys.readouterr().out
        assert "No se encontraron" in out
        assert result["deleted"] == []


# ── run_import_full (dry_run) ─────────────────────────────────────────────────

class TestRunImportFullDryRun:
    async def test_dry_run_returns_empty_import_result(self, capsys, fixture_full_csv):
        with patch("planner_import.create_plan", new_callable=AsyncMock) as mock_create:
            result = await run_import_full(fixture_full_csv, "group-id", dry_run=True)

        mock_create.assert_not_called()
        assert result.plan_id == ""
        assert result.task_ids == []
        assert result.bucket_ids == {}

    async def test_dry_run_output_contains_dry_run(self, capsys, fixture_full_csv):
        with patch("planner_import.create_plan", new_callable=AsyncMock):
            await run_import_full(fixture_full_csv, "group-id", dry_run=True)

        out = capsys.readouterr().out
        assert "DRY RUN" in out

    async def test_dry_run_prints_bucket_names(self, capsys, fixture_full_csv):
        with patch("planner_import.create_plan", new_callable=AsyncMock):
            await run_import_full(fixture_full_csv, "group-id", dry_run=True)

        out = capsys.readouterr().out
        assert "Bucket Alpha" in out
        assert "Bucket Beta" in out


# ── run_import_plan (dry_run) ─────────────────────────────────────────────────

class TestRunImportPlanDryRun:
    async def test_dry_run_create_plan_not_called(self, fixture_plan_csv):
        with patch("planner_import.create_plan", new_callable=AsyncMock) as mock_create:
            result = await run_import_plan(fixture_plan_csv, "group-id", dry_run=True)

        mock_create.assert_not_called()
        assert result.plan_id == ""

    async def test_dry_run_output_contains_plan_name(self, capsys, fixture_plan_csv):
        with patch("planner_import.create_plan", new_callable=AsyncMock):
            await run_import_plan(fixture_plan_csv, "group-id", dry_run=True)

        out = capsys.readouterr().out
        assert "Plan Solo Cabecera" in out


# ── run_import_buckets (dry_run) ──────────────────────────────────────────────

class TestRunImportBucketsDryRun:
    async def test_dry_run_create_bucket_not_called(self, fixture_buckets_csv):
        with patch("planner_import.create_bucket", new_callable=AsyncMock) as mock_create:
            result = await run_import_buckets(fixture_buckets_csv, dry_run=True)

        mock_create.assert_not_called()
        assert result.bucket_ids == {}

    async def test_dry_run_prints_bucket_names(self, capsys, fixture_buckets_csv):
        with patch("planner_import.create_bucket", new_callable=AsyncMock):
            await run_import_buckets(fixture_buckets_csv, dry_run=True)

        out = capsys.readouterr().out
        assert "Bucket Nuevo A" in out
        assert "Bucket Nuevo B" in out

    async def test_multiple_plan_ids_raises_value_error(self, tmp_path):
        csv_file = tmp_path / "multi_plan.csv"
        csv_file.write_text(
            "PlanID;BucketName\nplan-001;Bucket A\nplan-002;Bucket B\n",
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="mismo PlanID"):
            await run_import_buckets(csv_file, dry_run=True)


# ── run_import_tasks (dry_run) ────────────────────────────────────────────────

class TestRunImportTasksDryRun:
    async def test_dry_run_create_task_full_not_called(self, fixture_tasks_csv):
        with patch("planner_import.create_task_full", new_callable=AsyncMock) as mock_create:
            result = await run_import_tasks(fixture_tasks_csv, dry_run=True)

        mock_create.assert_not_called()
        assert result.task_ids == []

    async def test_dry_run_prints_plan_id(self, capsys, fixture_tasks_csv):
        with patch("planner_import.create_task_full", new_callable=AsyncMock):
            await run_import_tasks(fixture_tasks_csv, dry_run=True)

        out = capsys.readouterr().out
        assert "aaa11111-0000-0000-0000-000000000001" in out
