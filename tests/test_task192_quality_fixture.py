import json
from pathlib import Path


def test_task192_small_model_quality_fixture_has_ten_bounded_retrieval_cases():
    fixture_dir = Path(__file__).parent / "fixtures"
    fixture = json.loads((fixture_dir / "task192_small_model_quality_v1.json").read_text(encoding="utf-8"))
    assert fixture["version"] == "1.0.0"
    assert len(fixture["cases"]) == 10
    assert len({case["id"] for case in fixture["cases"]}) == 10
    assert all(case["question"].strip() and case["source"].strip()
               and case["note"].strip() and case["expected"].strip()
               for case in fixture["cases"])
    results = json.loads((fixture_dir / "task192_small_model_quality_v1_results.json").read_text(encoding="utf-8"))
    assert results["model"] == fixture["model"]
    assert len(results["results"]) == 20
    assert {row["retrieval"] for row in results["results"]} == {False, True}
    assert {row["id"] for row in results["results"]} == {case["id"] for case in fixture["cases"]}
