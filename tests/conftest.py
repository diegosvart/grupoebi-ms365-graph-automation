"""Stubs de módulos MCP + fixtures compartidos."""
from __future__ import annotations

import sys
import types
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

# 1. Path al módulo principal
PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# 2. Stubs de módulos MCP externos (antes de importar planner_import)
def _register_stubs() -> None:
    for name in ("src", "src.auth", "src.auth.microsoft", "src.config"):
        sys.modules.setdefault(name, types.ModuleType(name))

    auth_mod = sys.modules["src.auth.microsoft"]
    mock_mgr_cls = MagicMock()
    mock_mgr_cls.return_value.get_token.return_value = "fake-token-stub"
    auth_mod.MicrosoftAuthManager = mock_mgr_cls

    cfg_mod = sys.modules["src.config"]
    mock_settings_cls = MagicMock()
    mock_settings_cls.return_value.azure_tenant_id = "fake-tenant"
    mock_settings_cls.return_value.azure_client_id = "fake-client"
    mock_settings_cls.return_value.azure_client_secret = "fake-secret"
    cfg_mod.Settings = mock_settings_cls


_register_stubs()
import planner_import  # noqa: E402

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixture_full_csv() -> Path:
    return FIXTURES_DIR / "full.csv"


@pytest.fixture
def fixture_tasks_csv() -> Path:
    return FIXTURES_DIR / "tasks.csv"


@pytest.fixture
def fixture_buckets_csv() -> Path:
    return FIXTURES_DIR / "buckets.csv"


@pytest.fixture
def fixture_plan_csv() -> Path:
    return FIXTURES_DIR / "plan.csv"


@pytest.fixture(autouse=True)
def reset_label_map():
    """LABEL_MAP es global mutable — resetear entre tests."""
    original = dict(planner_import.LABEL_MAP)
    planner_import.LABEL_MAP.clear()
    yield
    planner_import.LABEL_MAP.clear()
    planner_import.LABEL_MAP.update(original)


@pytest.fixture
def fake_token() -> str:
    return "test-bearer-token"


@pytest.fixture
def sample_plans() -> list[dict]:
    return [
        {
            "id": "plan-id-001",
            "title": "Plan Alpha",
            "createdDateTime": "2026-01-15T10:00:00Z",
            "@odata.etag": 'W/"etag-001"',
        },
        {
            "id": "plan-id-002",
            "title": "Plan Beta",
            "createdDateTime": "2026-01-20T12:00:00Z",
            "@odata.etag": 'W/"etag-002"',
        },
    ]


@pytest.fixture
def mock_auth(monkeypatch):
    """Parchea Settings y MicrosoftAuthManager en el namespace de planner_import."""
    mock_settings = MagicMock()
    mock_settings.azure_tenant_id = "t"
    mock_settings.azure_client_id = "c"
    mock_settings.azure_client_secret = "s"

    mock_mgr = MagicMock()
    mock_mgr.get_token.return_value = "test-token"

    monkeypatch.setattr(planner_import, "Settings", lambda: mock_settings)
    monkeypatch.setattr(
        planner_import, "MicrosoftAuthManager", lambda **kw: mock_mgr
    )
    return mock_mgr


def make_async_client_ctx(mock_client):
    """Envuelve mock_client en async context manager para `async with httpx.AsyncClient(...)`."""
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=mock_client)
    ctx.__aexit__ = AsyncMock(return_value=False)
    return ctx
