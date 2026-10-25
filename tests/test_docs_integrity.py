from pathlib import Path
import importlib.util
import json
import pytest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("docs_integrity",ROOT/"tools/docs_integrity.py")
integrity=importlib.util.module_from_spec(spec); spec.loader.exec_module(integrity)


def test_public_documentation_sources_are_utf8_clean_and_unique():
    assert integrity.check()==[]


@pytest.mark.parametrize("bad",["\u00e2\u20ac\u201c","\u00e2\u2020\u2019","\u00c2\u00b7","Tasks 180?184","Task details ?"])
def test_corrupt_utf8_and_lost_separators_are_detected(bad):
    assert integrity.MOJIBAKE.search(bad)


def test_canonical_record_duplicates_fail(tmp_path):
    (tmp_path/"docs").mkdir()
    records=[{"number":180},{"number":180}]
    (tmp_path/"docs/tasks-data.mjs").write_text("export const post100Tasks = "+json.dumps(records)+";",encoding="utf-8")
    (tmp_path/"corporation_updates.json").write_text('{"items":[]}',encoding="utf-8")
    assert "Duplicate authoritative task 180" in integrity.check(tmp_path)


def test_duplicate_current_history_and_html_ids_fail(tmp_path):
    (tmp_path/"docs").mkdir()
    (tmp_path/"docs/tasks-data.mjs").write_text('export const post100Tasks = [];',encoding="utf-8")
    (tmp_path/"docs/updates.html").write_text('<article id="task-184"></article><article id="task-184"></article>',encoding="utf-8")
    (tmp_path/"corporation_updates.json").write_text(json.dumps({"items":[{"title":"Task 184 first"},{"title":"Task 184 second"}]}),encoding="utf-8")
    errors=integrity.check(tmp_path)
    assert any("duplicate HTML id task-184" in error for error in errors)
    assert any("Duplicate current changelog task 184" in error for error in errors)
