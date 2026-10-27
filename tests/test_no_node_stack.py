"""Prevent retired runtime/build dependencies from silently returning."""
import ast,re,subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def test_final_source_has_no_node_manifests_legacy_shells_or_runtime_imports():
    assert not (ROOT/'desktop').exists() and not (ROOT/'desktop-ui').exists()
    names=subprocess.check_output(['git','ls-files','--cached','--others','--exclude-standard','-z'],cwd=ROOT).decode('utf-8').split('\0')
    paths=[ROOT/name for name in set(names) if name and (ROOT/name).is_file()]
    assert not [str(path.relative_to(ROOT)) for path in paths if path.name in {'package.json','package-lock.json','yarn.lock','pnpm-lock.yaml'} or path.suffix=='.cjs']
    for path in paths:
        if not path.is_relative_to(ROOT/'app'):continue
        if path.suffix=='.py':
            tree=ast.parse(path.read_text(encoding='utf-8-sig'))
            for node in ast.walk(tree):
                if isinstance(node,ast.Import):imports=[name.name for name in node.names]
                elif isinstance(node,ast.ImportFrom):imports=[node.module or '']
                else:continue
                assert not any(name.split('.')[0] in {'playwright','electron'} for name in imports),path
        if path.suffix in {'.js','.mjs'}:
            source=path.read_text(encoding='utf-8')
            assert not re.search(r'''(?:from\s*|import\s*\()\s*["'](?:node:|electron|next/)''',source),path
            assert 'WebGLRenderer' not in source and 'vendor/three' not in source,path
    requirements=(ROOT/'requirements.txt').read_text(encoding='utf-8').lower()
    assert not any(line.startswith(('playwright=','pyee=','greenlet=')) for line in requirements.splitlines())
