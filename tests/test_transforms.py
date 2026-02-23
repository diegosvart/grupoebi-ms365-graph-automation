"""Tests de funciones puras — sin red ni credenciales."""
from __future__ import annotations

import uuid
from io import StringIO
from pathlib import Path

import pytest

import planner_import
from planner_import import (
    build_checklist,
    extract_ordered_unique,
    map_priority,
    parse_csv,
    parse_csv_buckets,
    parse_csv_plan,
    parse_csv_tasks,
    parse_date,
    parse_labels,
    _print_plans_table,
)


# ── parse_date ────────────────────────────────────────────────────────────────

class TestParseDate:
    def test_basic_conversion(self):
        assert parse_date("17022026") == "2026-02-17T00:00:00Z"

    def test_first_day_of_year(self):
        assert parse_date("01012025") == "2025-01-01T00:00:00Z"

    def test_ends_with_time_suffix(self):
        result = parse_date("15062024")
        assert result.endswith("T00:00:00Z")

    def test_year_first_in_iso(self):
        result = parse_date("28022026")
        assert result.startswith("2026-")


# ── map_priority ──────────────────────────────────────────────────────────────

class TestMapPriority:
    def test_urgent(self):
        assert map_priority("urgent") == 1

    def test_important(self):
        assert map_priority("important") == 2

    def test_medium(self):
        assert map_priority("medium") == 3

    def test_low(self):
        assert map_priority("low") == 5

    def test_none(self):
        assert map_priority("none") == 9

    def test_unknown_falls_back_to_5(self):
        assert map_priority("desconocido") == 5

    def test_empty_falls_back_to_5(self):
        assert map_priority("") == 5

    def test_uppercase_normalized(self):
        assert map_priority("URGENT") == 1
        assert map_priority("Medium") == 3


# ── build_checklist ───────────────────────────────────────────────────────────

class TestBuildChecklist:
    def test_empty_string_returns_empty_dict(self):
        assert build_checklist("") == {}

    def test_single_item(self):
        result = build_checklist("Solo item")
        assert len(result) == 1
        item = next(iter(result.values()))
        assert item["title"] == "Solo item"
        assert item["isChecked"] is False
        assert item["orderHint"] == " !"
        assert item["@odata.type"] == "#microsoft.graph.plannerChecklistItem"

    def test_multiple_items(self):
        result = build_checklist("A;B;C")
        assert len(result) == 3

    def test_keys_are_valid_uuids(self):
        result = build_checklist("Item 1;Item 2")
        for key in result:
            uuid.UUID(key)  # raises ValueError if not valid UUID

    def test_strips_whitespace(self):
        result = build_checklist("  Hola  ;  Mundo  ")
        titles = [v["title"] for v in result.values()]
        assert "Hola" in titles
        assert "Mundo" in titles

    def test_empty_segments_ignored(self):
        result = build_checklist("A;;B;;;C")
        assert len(result) == 3

    def test_whitespace_only_segment_ignored(self):
        result = build_checklist("  ;  ;Valido")
        assert len(result) == 1


# ── parse_labels ──────────────────────────────────────────────────────────────

class TestParseLabels:
    def test_known_labels_mapped(self):
        planner_import.LABEL_MAP["TI"] = "category1"
        planner_import.LABEL_MAP["PM"] = "category2"
        result = parse_labels("TI;PM")
        assert result == {"category1": True, "category2": True}

    def test_unknown_labels_ignored(self):
        planner_import.LABEL_MAP["TI"] = "category1"
        result = parse_labels("TI;DESCONOCIDO;OTRO")
        assert result == {"category1": True}

    def test_empty_label_map_returns_empty(self):
        # LABEL_MAP vacío (reset_label_map fixture lo garantiza)
        result = parse_labels("TI;PM")
        assert result == {}

    def test_empty_string_returns_empty(self):
        planner_import.LABEL_MAP["TI"] = "category1"
        result = parse_labels("")
        assert result == {}

    def test_strips_whitespace_in_labels(self):
        planner_import.LABEL_MAP["TI"] = "category1"
        result = parse_labels(" TI ; PM ")
        assert "category1" in result


# ── extract_ordered_unique ────────────────────────────────────────────────────

class TestExtractOrderedUnique:
    def test_preserves_order(self):
        tasks = [
            {"bucket_name": "Gamma"},
            {"bucket_name": "Alpha"},
            {"bucket_name": "Beta"},
        ]
        result = extract_ordered_unique(tasks, "bucket_name")
        assert result == ["Gamma", "Alpha", "Beta"]

    def test_eliminates_duplicates(self):
        tasks = [
            {"bucket_name": "A"},
            {"bucket_name": "B"},
            {"bucket_name": "A"},
            {"bucket_name": "C"},
            {"bucket_name": "B"},
        ]
        result = extract_ordered_unique(tasks, "bucket_name")
        assert result == ["A", "B", "C"]

    def test_empty_list(self):
        assert extract_ordered_unique([], "bucket_name") == []

    def test_single_element(self):
        assert extract_ordered_unique([{"k": "v"}], "k") == ["v"]


# ── _print_plans_table ────────────────────────────────────────────────────────

class TestPrintPlansTable:
    def test_empty_list_prints_header_only(self, capsys):
        _print_plans_table([])
        out = capsys.readouterr().out
        assert "#" in out
        assert "ID" in out
        assert "Título" in out

    def test_two_plans_in_output(self, capsys):
        plans = [
            {
                "id": "plan-id-001",
                "title": "Plan Alpha",
                "createdDateTime": "2026-01-15T10:00:00Z",
            },
            {
                "id": "plan-id-002",
                "title": "Plan Beta",
                "createdDateTime": "2026-01-20T12:00:00Z",
            },
        ]
        _print_plans_table(plans)
        out = capsys.readouterr().out
        assert "Plan Alpha" in out
        assert "Plan Beta" in out
        assert "plan-id-001" in out
        assert "plan-id-002" in out

    def test_date_truncated_to_10_chars(self, capsys):
        plans = [
            {
                "id": "abc",
                "title": "T",
                "createdDateTime": "2026-01-15T10:00:00Z",
            }
        ]
        _print_plans_table(plans)
        out = capsys.readouterr().out
        assert "2026-01-15" in out
        assert "T10:00:00Z" not in out

    def test_numbering_starts_at_1(self, capsys):
        plans = [{"id": "x", "title": "One", "createdDateTime": "2026-01-01T00:00:00Z"}]
        _print_plans_table(plans)
        out = capsys.readouterr().out
        assert "1" in out

    def test_missing_date_field_does_not_raise(self, capsys):
        plans = [{"id": "x", "title": "Sin fecha"}]
        # No debe lanzar excepción
        _print_plans_table(plans)
        out = capsys.readouterr().out
        assert "Sin fecha" in out


# ── parse_csv ─────────────────────────────────────────────────────────────────

class TestParseCsv:
    def test_returns_list(self, fixture_full_csv):
        result = parse_csv(fixture_full_csv)
        assert isinstance(result, list)

    def test_three_rows(self, fixture_full_csv):
        result = parse_csv(fixture_full_csv)
        assert len(result) == 3

    def test_two_distinct_buckets(self, fixture_full_csv):
        result = parse_csv(fixture_full_csv)
        buckets = extract_ordered_unique(result, "bucket_name")
        assert len(buckets) == 2
        assert "Bucket Alpha" in buckets
        assert "Bucket Beta" in buckets

    def test_title_field(self, fixture_full_csv):
        result = parse_csv(fixture_full_csv)
        assert result[0]["title"] == "Tarea Uno"

    def test_priority_is_int(self, fixture_full_csv):
        result = parse_csv(fixture_full_csv)
        for t in result:
            assert isinstance(t["priority"], int)

    def test_percent_complete_is_int(self, fixture_full_csv):
        result = parse_csv(fixture_full_csv)
        assert result[0]["percent_complete"] == 0
        assert result[1]["percent_complete"] == 50
        assert result[2]["percent_complete"] == 100

    def test_start_date_iso_format(self, fixture_full_csv):
        result = parse_csv(fixture_full_csv)
        assert result[0]["start_date"] == "2026-02-01T00:00:00Z"

    def test_due_date_iso_format(self, fixture_full_csv):
        result = parse_csv(fixture_full_csv)
        assert result[0]["due_date"] == "2026-02-28T00:00:00Z"

    def test_plan_name(self, fixture_full_csv):
        result = parse_csv(fixture_full_csv)
        assert all(t["plan_name"] == "Plan Test" for t in result)

    def test_assignee_email(self, fixture_full_csv):
        result = parse_csv(fixture_full_csv)
        assert result[0]["assignee_email"] == "alice@test.com"
        assert result[1]["assignee_email"] == "bob@test.com"


# ── parse_csv_tasks ───────────────────────────────────────────────────────────

class TestParseCsvTasks:
    def test_ok_returns_list(self, fixture_tasks_csv):
        result = parse_csv_tasks(fixture_tasks_csv)
        assert len(result) == 2

    def test_plan_id_present(self, fixture_tasks_csv):
        result = parse_csv_tasks(fixture_tasks_csv)
        assert result[0]["plan_id"] == "aaa11111-0000-0000-0000-000000000001"

    def test_bucket_id_present(self, fixture_tasks_csv):
        result = parse_csv_tasks(fixture_tasks_csv)
        assert result[0]["bucket_id"] == "bbb22222-0000-0000-0000-000000000002"

    def test_missing_plan_id_raises(self, tmp_path):
        csv_file = tmp_path / "bad.csv"
        csv_file.write_text(
            "PlanID;BucketID;TaskTitle;StartDate;DueDate;Priority;PercentComplete\n"
            ";bbb-001;Tarea;01012026;31012026;medium;0\n",
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="PlanID"):
            parse_csv_tasks(csv_file)

    def test_missing_bucket_id_raises(self, tmp_path):
        csv_file = tmp_path / "bad.csv"
        csv_file.write_text(
            "PlanID;BucketID;TaskTitle;StartDate;DueDate;Priority;PercentComplete\n"
            "aaa-001;;Tarea;01012026;31012026;medium;0\n",
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="BucketID"):
            parse_csv_tasks(csv_file)


# ── parse_csv_buckets ─────────────────────────────────────────────────────────

class TestParseCsvBuckets:
    def test_ok_returns_list(self, fixture_buckets_csv):
        result = parse_csv_buckets(fixture_buckets_csv)
        assert len(result) == 2

    def test_bucket_names(self, fixture_buckets_csv):
        result = parse_csv_buckets(fixture_buckets_csv)
        names = [b["bucket_name"] for b in result]
        assert "Bucket Nuevo A" in names
        assert "Bucket Nuevo B" in names

    def test_missing_plan_id_raises(self, tmp_path):
        csv_file = tmp_path / "bad.csv"
        csv_file.write_text(
            "PlanID;BucketName\n;Mi Bucket\n",
            encoding="utf-8",
        )
        with pytest.raises(ValueError):
            parse_csv_buckets(csv_file)

    def test_missing_bucket_name_raises(self, tmp_path):
        csv_file = tmp_path / "bad.csv"
        csv_file.write_text(
            "PlanID;BucketName\naaa-001;\n",
            encoding="utf-8",
        )
        with pytest.raises(ValueError):
            parse_csv_buckets(csv_file)


# ── parse_csv_plan ────────────────────────────────────────────────────────────

class TestParseCsvPlan:
    def test_ok_returns_dict(self, fixture_plan_csv):
        result = parse_csv_plan(fixture_plan_csv)
        assert isinstance(result, dict)
        assert result["plan_name"] == "Plan Solo Cabecera"

    def test_labels_parsed(self, fixture_plan_csv):
        result = parse_csv_plan(fixture_plan_csv)
        assert "TI" in result["labels"]
        assert "PM" in result["labels"]

    def test_empty_csv_raises_value_error(self, tmp_path):
        csv_file = tmp_path / "empty.csv"
        csv_file.write_text("PlanName;Labels\n", encoding="utf-8")
        with pytest.raises(ValueError, match="vacío"):
            parse_csv_plan(csv_file)

    def test_missing_plan_name_raises(self, tmp_path):
        csv_file = tmp_path / "noname.csv"
        csv_file.write_text("PlanName;Labels\n;TI\n", encoding="utf-8")
        with pytest.raises(ValueError, match="PlanName"):
            parse_csv_plan(csv_file)

    def test_empty_labels_returns_empty_list(self, tmp_path):
        csv_file = tmp_path / "nolabels.csv"
        csv_file.write_text("PlanName;Labels\nMi Plan;\n", encoding="utf-8")
        result = parse_csv_plan(csv_file)
        assert result["labels"] == []
