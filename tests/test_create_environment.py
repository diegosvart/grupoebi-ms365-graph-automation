"""Tests unitarios para create_environment.py — sin red real."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

import create_environment
from create_environment import (
    add_channel_member,
    add_team_member,
    add_planner_tab,
    create_sp_folder,
    create_team_channel,
    ensure_help_dir,
    graph_request_bytes,
    load_project_config,
    parse_csv1,
    run_create_environment,
    save_project_config,
    upload_file,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_response(status_code: int, json_data=None, headers=None) -> MagicMock:
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
    client = MagicMock(spec=httpx.AsyncClient)
    client.request = AsyncMock(side_effect=responses)
    return client


def _make_409() -> httpx.HTTPStatusError:
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = 409
    return httpx.HTTPStatusError("conflict", request=MagicMock(), response=resp)


def _mock_httpx_constructor() -> MagicMock:
    """Devuelve un reemplazo para httpx.AsyncClient (constructor mock)."""
    mock_client = MagicMock(spec=httpx.AsyncClient)
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=mock_client)
    ctx.__aexit__ = AsyncMock(return_value=False)
    return MagicMock(return_value=ctx)


# ── TestParseCsv1 ─────────────────────────────────────────────────────────────

class TestParseCsv1:
    def test_fields_parsed_correctly(self, fixture_csv1_sample):
        result = parse_csv1(fixture_csv1_sample)
        assert len(result) == 1
        row = result[0]
        assert row["project_id"] == "PRJ-TEST-001"
        assert row["project_name"] == "Proyecto Test"
        assert row["pm_email"] == "pm@test.com"
        assert row["lider_email"] == "lider@test.com"
        assert row["start_date"] == "01-03-2026"

    def test_trim_whitespace(self, tmp_path):
        csv = tmp_path / "test.csv"
        csv.write_text(
            "ProjectID;ProjectName;PMEmail;LiderEmail;StartDate;PlannerCSV\n"
            " PRJ-001 ; Mi Proyecto ; pm@test.com ; lider@test.com ; 01-03-2026 ; path/to.csv \n",
            encoding="utf-8-sig",
        )
        result = parse_csv1(csv)
        assert result[0]["project_id"] == "PRJ-001"
        assert result[0]["project_name"] == "Mi Proyecto"
        assert result[0]["pm_email"] == "pm@test.com"

    def test_planner_csv_is_path(self, fixture_csv1_sample):
        result = parse_csv1(fixture_csv1_sample)
        assert isinstance(result[0]["planner_csv"], Path)
        assert result[0]["planner_csv"] == Path("tests/fixtures/full.csv")


# ── TestGraphRequestBytes ─────────────────────────────────────────────────────

class TestGraphRequestBytes:
    async def test_put_binary_sends_bytes(self, fake_token):
        client = await _make_client([_make_response(200, {"id": "file-id"})])
        result = await graph_request_bytes(
            client, "PUT", "/sites/s/drive/items/f:/test.bin:/content",
            fake_token, data=b"hello bytes",
        )
        assert result == {"id": "file-id"}
        _, kwargs = client.request.call_args
        assert kwargs["content"] == b"hello bytes"
        assert kwargs["headers"]["Content-Type"] == "application/octet-stream"

    async def test_retry_429_sleeps_and_retries(self, fake_token):
        resp_429 = _make_response(429, headers={"Retry-After": "1"})
        resp_200 = _make_response(200, {"id": "ok"})
        client = await _make_client([resp_429, resp_200])

        with patch.object(create_environment.asyncio, "sleep", new_callable=AsyncMock) as mock_sleep:
            result = await graph_request_bytes(client, "PUT", "/test", fake_token, data=b"x")

        assert result == {"id": "ok"}
        mock_sleep.assert_called_once_with(1)

    async def test_raise_on_4xx(self, fake_token):
        client = await _make_client([_make_response(403)])
        with pytest.raises(httpx.HTTPStatusError):
            await graph_request_bytes(client, "PUT", "/test", fake_token, data=b"x")


# ── TestCreateTeamChannel ─────────────────────────────────────────────────────

class TestCreateTeamChannel:
    async def test_endpoint_correct(self, fake_token):
        with patch("create_environment.graph_request", new_callable=AsyncMock) as mock_gr:
            mock_gr.return_value = {"id": "ch-id", "webUrl": "http://..."}
            await create_team_channel(MagicMock(), fake_token, "group-abc", "Mi Canal")

        args = mock_gr.call_args[0]
        endpoint: str = args[2]
        assert "group-abc" in endpoint
        assert "channels" in endpoint

    async def test_name_truncated_to_50(self, fake_token):
        long_name = "A" * 60
        with patch("create_environment.graph_request", new_callable=AsyncMock) as mock_gr:
            mock_gr.return_value = {"id": "ch-id"}
            await create_team_channel(MagicMock(), fake_token, "group-abc", long_name)

        kwargs = mock_gr.call_args[1]
        assert len(kwargs["json"]["displayName"]) == 50


# ── TestAddChannelMember ──────────────────────────────────────────────────────

class TestAddChannelMember:
    async def test_endpoint_and_roles_owner(self, fake_token):
        with patch("create_environment.graph_request", new_callable=AsyncMock) as mock_gr:
            mock_gr.return_value = None
            await add_channel_member(MagicMock(), fake_token, "group-g", "ch-c", "user-u", "owner")

        args = mock_gr.call_args[0]
        endpoint: str = args[2]
        assert "group-g" in endpoint
        assert "ch-c" in endpoint
        assert "members" in endpoint
        kwargs = mock_gr.call_args[1]
        assert kwargs["json"]["roles"] == ["owner"]

    async def test_empty_role_gives_empty_roles_list(self, fake_token):
        with patch("create_environment.graph_request", new_callable=AsyncMock) as mock_gr:
            mock_gr.return_value = None
            await add_channel_member(MagicMock(), fake_token, "group-g", "ch-c", "user-u", "")

        kwargs = mock_gr.call_args[1]
        assert kwargs["json"]["roles"] == []


# ── TestAddPlannerTab ─────────────────────────────────────────────────────────

class TestAddPlannerTab:
    async def test_endpoint_correct(self, fake_token):
        with patch("create_environment.graph_request", new_callable=AsyncMock) as mock_gr:
            mock_gr.return_value = {"id": "tab-id"}
            await add_planner_tab(MagicMock(), fake_token, "group-g", "ch-c", "plan-p", "tenant-t")

        args = mock_gr.call_args[0]
        endpoint: str = args[2]
        assert "group-g" in endpoint
        assert "ch-c" in endpoint
        assert "tabs" in endpoint

    async def test_login_hint_literal_in_content_url(self, fake_token):
        with patch("create_environment.graph_request", new_callable=AsyncMock) as mock_gr:
            mock_gr.return_value = {"id": "tab-id"}
            await add_planner_tab(MagicMock(), fake_token, "group-g", "ch-c", "plan-p", "tenant-t")

        kwargs = mock_gr.call_args[1]
        content_url: str = kwargs["json"]["configuration"]["contentUrl"]
        assert "{loginHint}" in content_url


# ── TestCreateSpFolder ────────────────────────────────────────────────────────

class TestCreateSpFolder:
    async def test_endpoint_includes_site_and_parent(self, fake_token):
        with patch("create_environment.graph_request", new_callable=AsyncMock) as mock_gr:
            mock_gr.return_value = {"id": "folder-id"}
            await create_sp_folder(MagicMock(), fake_token, "site-s", "parent-p", "MiCarpeta")

        args = mock_gr.call_args[0]
        endpoint: str = args[2]
        assert "site-s" in endpoint
        assert "parent-p" in endpoint

    async def test_conflict_behavior_fail(self, fake_token):
        with patch("create_environment.graph_request", new_callable=AsyncMock) as mock_gr:
            mock_gr.return_value = {"id": "folder-id"}
            await create_sp_folder(MagicMock(), fake_token, "site-s", "parent-p", "MiCarpeta")

        kwargs = mock_gr.call_args[1]
        assert kwargs["json"]["@microsoft.graph.conflictBehavior"] == "fail"


# ── TestUploadFile ────────────────────────────────────────────────────────────

class TestUploadFile:
    async def test_endpoint_includes_folder_and_filename(self, fake_token, tmp_path):
        test_file = tmp_path / "plantilla.docx"
        test_file.write_bytes(b"fake docx content")

        with patch("create_environment.graph_request_bytes", new_callable=AsyncMock) as mock_grb:
            mock_grb.return_value = {"id": "file-id"}
            await upload_file(MagicMock(), fake_token, "site-s", "folder-f", test_file)

        args = mock_grb.call_args[0]
        endpoint: str = args[2]
        assert "folder-f" in endpoint
        assert "plantilla.docx" in endpoint

    async def test_file_bytes_sent(self, fake_token, tmp_path):
        test_file = tmp_path / "doc.docx"
        test_bytes = b"real file bytes here"
        test_file.write_bytes(test_bytes)

        with patch("create_environment.graph_request_bytes", new_callable=AsyncMock) as mock_grb:
            mock_grb.return_value = {"id": "file-id"}
            await upload_file(MagicMock(), fake_token, "site-s", "folder-f", test_file)

        kwargs = mock_grb.call_args[1]
        assert kwargs["data"] == test_bytes


# ── TestEnsureHelpDir ─────────────────────────────────────────────────────────

class TestEnsureHelpDir:
    async def test_200_skips_creation_and_returns_id(self, fake_token):
        with patch("create_environment.graph_request", new_callable=AsyncMock) as mock_gr:
            mock_gr.return_value = {"id": "existing-id"}
            result = await ensure_help_dir(MagicMock(), fake_token, "site-s", "root-r")

        assert result == "existing-id"
        mock_gr.assert_called_once()

    async def test_404_creates_folder_and_returns_id(self, fake_token):
        resp_404 = MagicMock(spec=httpx.Response)
        resp_404.status_code = 404
        err_404 = httpx.HTTPStatusError("not found", request=MagicMock(), response=resp_404)

        with patch("create_environment.graph_request", new_callable=AsyncMock) as mock_gr, \
             patch("create_environment.create_sp_folder", new_callable=AsyncMock) as mock_create:
            mock_gr.side_effect = err_404
            mock_create.return_value = {"id": "new-folder-id"}
            result = await ensure_help_dir(MagicMock(), fake_token, "site-s", "root-r")

        assert result == "new-folder-id"
        mock_create.assert_called_once()

    async def test_other_error_reraises(self, fake_token):
        resp_500 = MagicMock(spec=httpx.Response)
        resp_500.status_code = 500
        err_500 = httpx.HTTPStatusError("server error", request=MagicMock(), response=resp_500)

        with patch("create_environment.graph_request", new_callable=AsyncMock) as mock_gr:
            mock_gr.side_effect = err_500
            with pytest.raises(httpx.HTTPStatusError):
                await ensure_help_dir(MagicMock(), fake_token, "site-s", "root-r")


# ── TestProjectConfig ─────────────────────────────────────────────────────────

class TestProjectConfig:
    def test_save_load_roundtrip(self, tmp_path, monkeypatch):
        monkeypatch.setattr(create_environment, "PROJECT_CONFIG_PATH", tmp_path / "cfg.json")
        data = {"PRJ-001": {"plan_id": "abc123", "channel_id": "ch-xyz"}}
        save_project_config(data)
        result = load_project_config()
        assert result == data

    def test_load_returns_empty_dict_if_not_exists(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            create_environment, "PROJECT_CONFIG_PATH", tmp_path / "does_not_exist.json"
        )
        result = load_project_config()
        assert result == {}

    def test_utf8_no_ascii_escape(self, tmp_path, monkeypatch):
        cfg_path = tmp_path / "cfg.json"
        monkeypatch.setattr(create_environment, "PROJECT_CONFIG_PATH", cfg_path)
        data = {"key": "Ñoño — España"}
        save_project_config(data)
        text = cfg_path.read_text(encoding="utf-8")
        assert "Ñoño" in text
        assert "\\u00d1" not in text  # ensure_ascii=False → no unicode escapes


# ── TestRunCreateEnvironmentDryRun ────────────────────────────────────────────

class TestRunCreateEnvironmentDryRun:
    async def test_returns_empty_dict(self, fixture_csv1_sample):
        result = await run_create_environment(fixture_csv1_sample, "group-id", dry_run=True)
        assert result == {}

    async def test_prints_project_name(self, fixture_csv1_sample, capsys):
        await run_create_environment(fixture_csv1_sample, "group-id", dry_run=True)
        captured = capsys.readouterr()
        assert "Proyecto Test" in captured.out

    async def test_no_graph_functions_called(self, fixture_csv1_sample):
        with patch("create_environment.create_team_channel", new_callable=AsyncMock) as mock_canal, \
             patch("create_environment.create_plan", new_callable=AsyncMock) as mock_plan, \
             patch("create_environment.create_sp_folder", new_callable=AsyncMock) as mock_folder:
            await run_create_environment(fixture_csv1_sample, "group-id", dry_run=True)

        mock_canal.assert_not_called()
        mock_plan.assert_not_called()
        mock_folder.assert_not_called()


# ── TestRunCreateEnvironment409 ───────────────────────────────────────────────

class TestRunCreateEnvironment409:
    """Tests de idempotencia: los 409 no abortan el orquestador."""

    def _base_patches(self):
        """Diccionario de parches con comportamiento happy-path."""
        return {
            "httpx.AsyncClient": _mock_httpx_constructor(),
            "create_environment.get_site_id": AsyncMock(return_value="site-id"),
            "create_environment.graph_request": AsyncMock(return_value={"id": "root-id"}),
            "create_environment.ensure_help_dir": AsyncMock(return_value="help-id"),
            "create_environment.resolve_email_to_guid": AsyncMock(return_value="guid-123"),
            "create_environment.create_team_channel": AsyncMock(
                return_value={"id": "ch-id", "webUrl": ""}
            ),
            "create_environment.add_channel_member": AsyncMock(return_value=None),
            "create_environment.add_team_member": AsyncMock(return_value=None),
            "create_environment.parse_csv": MagicMock(return_value=([], [])),
            "create_environment.extract_ordered_unique": MagicMock(return_value=[]),
            "create_environment.create_plan": AsyncMock(return_value={"id": "plan-id"}),
            "create_environment.configure_plan_labels": AsyncMock(return_value=None),
            "create_environment.add_planner_tab": AsyncMock(return_value={"id": "tab-id"}),
            "create_environment.create_sp_folder": AsyncMock(
                return_value={"id": "folder-id", "webUrl": ""}
            ),
            "create_environment.upload_file": AsyncMock(return_value={}),
            "create_environment.load_project_config": MagicMock(return_value={}),
            "create_environment.save_project_config": MagicMock(return_value=None),
            "asyncio.sleep": AsyncMock(return_value=None),
        }

    def _apply_patches(self, patches, **overrides):
        """Aplica el dict de patches como context managers anidados (helper interno)."""
        p = {**patches, **overrides}
        return [patch(k, v) for k, v in p.items()]

    async def test_canal_409_skips_and_planner_continues(
        self, fixture_csv1_sample, mock_auth_env
    ):
        patches = self._base_patches()
        patches["create_environment.create_team_channel"] = AsyncMock(
            side_effect=_make_409()
        )

        with patch("httpx.AsyncClient", patches["httpx.AsyncClient"]), \
             patch("create_environment.get_site_id", patches["create_environment.get_site_id"]), \
             patch("create_environment.graph_request", patches["create_environment.graph_request"]), \
             patch("create_environment.ensure_help_dir", patches["create_environment.ensure_help_dir"]), \
             patch("create_environment.resolve_email_to_guid", patches["create_environment.resolve_email_to_guid"]), \
             patch("create_environment.create_team_channel", patches["create_environment.create_team_channel"]), \
             patch("create_environment.add_channel_member", patches["create_environment.add_channel_member"]), \
             patch("create_environment.add_team_member", patches["create_environment.add_team_member"]), \
             patch("create_environment.parse_csv", patches["create_environment.parse_csv"]), \
             patch("create_environment.extract_ordered_unique", patches["create_environment.extract_ordered_unique"]), \
             patch("create_environment.create_plan", patches["create_environment.create_plan"]) as mock_plan, \
             patch("create_environment.configure_plan_labels", patches["create_environment.configure_plan_labels"]), \
             patch("create_environment.add_planner_tab", patches["create_environment.add_planner_tab"]), \
             patch("create_environment.create_sp_folder", patches["create_environment.create_sp_folder"]), \
             patch("create_environment.upload_file", patches["create_environment.upload_file"]), \
             patch("create_environment.load_project_config", patches["create_environment.load_project_config"]), \
             patch("create_environment.save_project_config", patches["create_environment.save_project_config"]), \
             patch("asyncio.sleep", patches["asyncio.sleep"]):
            await run_create_environment(fixture_csv1_sample, "group-id")

        mock_plan.assert_called_once()

    async def test_folder_409_skips_and_does_not_raise(
        self, fixture_csv1_sample, mock_auth_env
    ):
        patches = self._base_patches()
        patches["create_environment.create_sp_folder"] = AsyncMock(
            side_effect=_make_409()
        )

        with patch("httpx.AsyncClient", patches["httpx.AsyncClient"]), \
             patch("create_environment.get_site_id", patches["create_environment.get_site_id"]), \
             patch("create_environment.graph_request", patches["create_environment.graph_request"]), \
             patch("create_environment.ensure_help_dir", patches["create_environment.ensure_help_dir"]), \
             patch("create_environment.resolve_email_to_guid", patches["create_environment.resolve_email_to_guid"]), \
             patch("create_environment.create_team_channel", patches["create_environment.create_team_channel"]), \
             patch("create_environment.add_channel_member", patches["create_environment.add_channel_member"]), \
             patch("create_environment.add_team_member", patches["create_environment.add_team_member"]), \
             patch("create_environment.parse_csv", patches["create_environment.parse_csv"]), \
             patch("create_environment.extract_ordered_unique", patches["create_environment.extract_ordered_unique"]), \
             patch("create_environment.create_plan", patches["create_environment.create_plan"]), \
             patch("create_environment.configure_plan_labels", patches["create_environment.configure_plan_labels"]), \
             patch("create_environment.add_planner_tab", patches["create_environment.add_planner_tab"]), \
             patch("create_environment.create_sp_folder", patches["create_environment.create_sp_folder"]), \
             patch("create_environment.upload_file", patches["create_environment.upload_file"]), \
             patch("create_environment.load_project_config", patches["create_environment.load_project_config"]), \
             patch("create_environment.save_project_config", patches["create_environment.save_project_config"]), \
             patch("asyncio.sleep", patches["asyncio.sleep"]):
            await run_create_environment(fixture_csv1_sample, "group-id")

    async def test_subfolder_409_skips_and_continues_loop(
        self, fixture_csv1_sample, mock_auth_env
    ):
        subfolder_side_effects = [
            {"id": "folder-id", "webUrl": ""},
            _make_409(),                            # 01_INICIO → 409
            {"id": "sub-02", "webUrl": ""},
            {"id": "sub-03", "webUrl": ""},
            {"id": "sub-04", "webUrl": ""},
            {"id": "sub-05", "webUrl": ""},
        ]
        patches = self._base_patches()
        patches["create_environment.create_sp_folder"] = AsyncMock(
            side_effect=subfolder_side_effects
        )

        with patch("httpx.AsyncClient", patches["httpx.AsyncClient"]), \
             patch("create_environment.get_site_id", patches["create_environment.get_site_id"]), \
             patch("create_environment.graph_request", patches["create_environment.graph_request"]), \
             patch("create_environment.ensure_help_dir", patches["create_environment.ensure_help_dir"]), \
             patch("create_environment.resolve_email_to_guid", patches["create_environment.resolve_email_to_guid"]), \
             patch("create_environment.create_team_channel", patches["create_environment.create_team_channel"]), \
             patch("create_environment.add_channel_member", patches["create_environment.add_channel_member"]), \
             patch("create_environment.add_team_member", patches["create_environment.add_team_member"]), \
             patch("create_environment.parse_csv", patches["create_environment.parse_csv"]), \
             patch("create_environment.extract_ordered_unique", patches["create_environment.extract_ordered_unique"]), \
             patch("create_environment.create_plan", patches["create_environment.create_plan"]), \
             patch("create_environment.configure_plan_labels", patches["create_environment.configure_plan_labels"]), \
             patch("create_environment.add_planner_tab", patches["create_environment.add_planner_tab"]), \
             patch("create_environment.create_sp_folder", patches["create_environment.create_sp_folder"]), \
             patch("create_environment.upload_file", patches["create_environment.upload_file"]), \
             patch("create_environment.load_project_config", patches["create_environment.load_project_config"]), \
             patch("create_environment.save_project_config", patches["create_environment.save_project_config"]), \
             patch("asyncio.sleep", patches["asyncio.sleep"]):
            await run_create_environment(fixture_csv1_sample, "group-id")

    async def test_member_409_skips_and_planner_continues(
        self, fixture_csv1_sample, mock_auth_env
    ):
        # add_team_member es la función que usa run_create_environment (canales estándar)
        patches = self._base_patches()
        patches["create_environment.add_team_member"] = AsyncMock(
            side_effect=_make_409()
        )

        with patch("httpx.AsyncClient", patches["httpx.AsyncClient"]), \
             patch("create_environment.get_site_id", patches["create_environment.get_site_id"]), \
             patch("create_environment.graph_request", patches["create_environment.graph_request"]), \
             patch("create_environment.ensure_help_dir", patches["create_environment.ensure_help_dir"]), \
             patch("create_environment.resolve_email_to_guid", patches["create_environment.resolve_email_to_guid"]), \
             patch("create_environment.create_team_channel", patches["create_environment.create_team_channel"]), \
             patch("create_environment.add_channel_member", patches["create_environment.add_channel_member"]), \
             patch("create_environment.add_team_member", patches["create_environment.add_team_member"]), \
             patch("create_environment.parse_csv", patches["create_environment.parse_csv"]), \
             patch("create_environment.extract_ordered_unique", patches["create_environment.extract_ordered_unique"]), \
             patch("create_environment.create_plan", patches["create_environment.create_plan"]) as mock_plan, \
             patch("create_environment.configure_plan_labels", patches["create_environment.configure_plan_labels"]), \
             patch("create_environment.add_planner_tab", patches["create_environment.add_planner_tab"]), \
             patch("create_environment.create_sp_folder", patches["create_environment.create_sp_folder"]), \
             patch("create_environment.upload_file", patches["create_environment.upload_file"]), \
             patch("create_environment.load_project_config", patches["create_environment.load_project_config"]), \
             patch("create_environment.save_project_config", patches["create_environment.save_project_config"]), \
             patch("asyncio.sleep", patches["asyncio.sleep"]):
            await run_create_environment(fixture_csv1_sample, "group-id")

        mock_plan.assert_called_once()
