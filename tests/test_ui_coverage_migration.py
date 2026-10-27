"""Every legacy case must keep an explicit, reviewable disposition."""
from collections import Counter
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def test_no_browser_electron_or_docs_case_disappears_from_migration_ledger():
    ledger=json.loads((ROOT/'review/task-227-coverage-migration.json').read_text(encoding='utf-8'))
    cases=ledger['cases'];assert Counter(row['suite'] for row in cases)==ledger['legacy_counts']=={'browser':295,'electron':44,'docs':23}
    identities={(row['suite'],row['legacy_file'],row['legacy_name']) for row in cases};assert len(identities)==362
    for row in cases:
        assert row['reason'] and row['replacement_checks']
        assert all((ROOT/name).is_file() for name in row['replacement_checks'])
        assert row['disposition'] in {'ported','replaced','retired'}
    browser=[row for row in cases if row['suite']=='browser']
    assert Counter(row['disposition'] for row in browser)=={'ported':284,'replaced':11}
    manifest=json.loads((ROOT/'tests/browser_contracts/manifest.json').read_text(encoding='utf-8'))
    assert sum(len(row['cases']) for row in manifest['retired'])==manifest['retired_cases']==11
    preserved={(record['legacy_file'],name) for record in manifest['files'] for name in record['cases']}
    assert {(row['legacy_file'],row['legacy_name']) for row in browser if row['disposition']=='ported'}==preserved
