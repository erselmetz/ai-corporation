"""Versioned, deterministic relevance and safety evaluation for Task 130 retrieval."""
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

from app.application.services.context_retrieval import ContextRetrievalService
from app.knowledge.service import SemanticMemoryService
from app.memory import ConversationMemoryStore, MemoryRecord, MemoryScope, MemoryType
from app.runtime.factory import create_corporation_runtime
from tests.test_semantic_memory import FakeEmbeddingProvider, MemoryVectorStore

NOW = datetime(2026, 10, 2, tzinfo=timezone.utc)
FIXTURE_PATH = Path(__file__).parent / "fixtures" / "semantic_retrieval_v1.json"
REPORT_PATH = Path(__file__).parent / "fixtures" / "semantic_retrieval_v1_report.json"


class EvaluationEmbeddingProvider(FakeEmbeddingProvider):
    """Disjoint synthetic token groups make fixture relevance labels exact."""
    groups = {**FakeEmbeddingProvider.groups, "animal": "animal", "space": "space", "stars": "space"}


def _record(item):
    created_at = NOW
    expires_at = NOW + timedelta(minutes=item["expires_minutes"])
    return MemoryRecord(item["id"], item["owner_id"], MemoryScope.CONVERSATION,
                        item["scope_id"], MemoryType.NOTE, item["content"],
                        f"synthetic-source-{item['id']}", created_at, expires_at, True)


def _metrics(cases, results, *, k=5):
    relevant_total = sum(len(case["relevant_ids"]) for case in cases)
    retrieved_relevant = 0
    retrieved_total = 0
    reciprocal_ranks = []
    false_positives = []
    false_negatives = []
    excluded_leaks = []
    for case in cases:
        result_ids = results[case["id"]][:k]
        expected = set(case["relevant_ids"])
        retrieved_relevant += len(expected.intersection(result_ids))
        retrieved_total += len(result_ids)
        reciprocal_ranks.append(next((1.0 / rank for rank, identifier in enumerate(result_ids, 1)
                                      if identifier in expected), 0.0))
        extra = sorted(set(result_ids) - expected)
        missing = sorted(expected - set(result_ids))
        leaked = sorted(set(result_ids).intersection(case.get("excluded_ids", [])))
        if extra:
            false_positives.append({"case_id": case["id"], "record_ids": extra})
        if missing:
            false_negatives.append({"case_id": case["id"], "record_ids": missing})
        if leaked:
            excluded_leaks.append({"case_id": case["id"], "record_ids": leaked})
    return {
        "recall_at_5": retrieved_relevant / relevant_total if relevant_total else 1.0,
        "precision_at_5": retrieved_relevant / retrieved_total if retrieved_total else 1.0,
        "mrr": sum(reciprocal_ranks) / len(reciprocal_ranks) if reciprocal_ranks else 1.0,
        "false_positive_examples": false_positives,
        "false_negative_examples": false_negatives,
        "excluded_record_leaks": excluded_leaks,
    }


def test_versioned_retrieval_evaluation_meets_relevance_and_access_thresholds():
    fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    assert fixture["version"] == "1.0.0"
    runtime = create_corporation_runtime()
    manager = runtime.application_service.memory_management()
    store = ConversationMemoryStore()
    vectors = MemoryVectorStore()
    semantic = SemanticMemoryService(manager, EvaluationEmbeddingProvider(), vectors)
    runtime.application_service.configure_semantic_memory(semantic)

    stale_vectors = []
    stale_metadata = []
    for item in fixture["records"]:
        record = _record(item)
        store.retain(record, now=NOW)
        semantic.index(record.id, actor_id=item["owner_id"], scope=record.scope,
                       scope_id=record.scope_id, now=NOW)
        if item.get("state") == "stale":
            for chunk_id, (vector, metadata) in vectors.items.items():
                if metadata["memory_id"] == record.id:
                    stale_vectors.append((chunk_id, vector))
                    stale_metadata.append(metadata.copy())
            detail = manager.inspect(record.id, actor_id=item["owner_id"], scope=record.scope,
                                     scope_id=record.scope_id, now=NOW)
            manager.update(record.id, actor_id=item["owner_id"], scope=record.scope,
                           scope_id=record.scope_id, revision=detail["revision"],
                           content=item["updated_content"], expires_at=record.expires_at,
                           retention_opt_in=True, now=NOW)
            # Reinsert the prior derived vector to model an interrupted/stale index.
            vectors.upsert(tuple(chunk for chunk, _ in stale_vectors),
                           tuple(vector for _, vector in stale_vectors), tuple(stale_metadata))

    semantic_cases = [case for case in fixture["cases"] if case["mode"] == "semantic"]
    results = {}
    stale_counts = {}
    for case in semantic_cases:
        result = semantic.search(case["query"], actor_id="owner", scope=MemoryScope.CONVERSATION,
                                 scope_id=case["scope_id"],
                                 now=NOW + timedelta(minutes=case["at_minutes"]), limit=5)
        results[case["id"]] = [hit.memory_id for hit in result.hits]
        stale_counts[case["id"]] = result.stale_candidates

    lexical_case = next(case for case in fixture["cases"] if case["mode"] == "lexical")
    lexical = ContextRetrievalService(manager).retrieve(
        lexical_case["query"], actor_id="owner", scope=MemoryScope.CONVERSATION,
        scope_id=lexical_case["scope_id"], now=NOW, limit=5)
    results[lexical_case["id"]] = [hit.source.memory_id for hit in lexical.hits]

    semantic_report = _metrics(semantic_cases, results)
    lexical_report = _metrics([lexical_case], results)
    report = {
        "fixture_version": fixture["version"],
        "semantic": semantic_report,
        "lexical": {"recall_at_5": lexical_report["recall_at_5"],
                    "false_positive_examples": lexical_report["false_positive_examples"],
                    "false_negative_examples": lexical_report["false_negative_examples"]},
        "stale_candidates_rejected": stale_counts,
    }
    expected_report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    expected_report.pop("excluded_synthetic_record_ids")
    expected_report.pop("quality_claim")
    assert report == expected_report, json.dumps(report, indent=2)

    thresholds = fixture["metrics"]
    assert semantic_report["recall_at_5"] >= thresholds["semantic_recall_at_5_min"], json.dumps(report, indent=2)
    assert semantic_report["precision_at_5"] >= thresholds["semantic_precision_at_5_min"], json.dumps(report, indent=2)
    assert semantic_report["mrr"] >= thresholds["semantic_mrr_min"], json.dumps(report, indent=2)
    assert lexical_report["recall_at_5"] >= thresholds["lexical_recall_at_5_min"], json.dumps(report, indent=2)
    assert len(semantic_report["excluded_record_leaks"]) <= thresholds["unauthorized_stale_expired_leakage_max"], json.dumps(report, indent=2)
    assert semantic_report["false_positive_examples"] == []
    assert semantic_report["false_negative_examples"] == []
    galaxy_case = next(case for case in semantic_cases if case["id"] == "semantic-galaxy-with-invalid-candidates")
    assert sum(stale_counts.values()) == 2
    assert all(identifier not in results[galaxy_case["id"]] for identifier in galaxy_case["excluded_ids"])
