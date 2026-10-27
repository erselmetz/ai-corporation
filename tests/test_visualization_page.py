from fastapi.testclient import TestClient

from app.local import create_local_app
from app.runtime.factory import create_corporation_runtime

PASSWORD = "test-owner-passphrase"
ORIGIN = "http://127.0.0.1:8000"


def _client():
    runtime = create_corporation_runtime()
    app = create_local_app(password=PASSWORD, application_service=runtime.application_service)
    return TestClient(app, base_url=ORIGIN, client=("127.0.0.1", 50000))


def test_advanced_map_starts_as_accessible_list_with_native_3d_help_and_setup_links():
    with _client() as client:
        response = client.get("/ui/visualization")
        assert response.status_code == 200
        html = response.text
        for fragment in ('id="viz-canvas"', 'aria-label="3D organizational globe, not geographic"',
                         'id="viz-mode-3d" type="button" aria-pressed="false">Desktop 3D help</button>',
                         'The globe is a visual layout, not a geographic map', 'tabindex="0"',
                         'id="viz-list"', 'Accessible list view of the same records and relationships', 'id="viz-reduce-motion"',
                         'id="viz-effects"', 'id="viz-evidence-data"',
                         'id="viz-layer-organization"', 'id="viz-layer-projects"', 'id="viz-layer-tasks"',
                         'id="viz-layer-workflows"', 'id="viz-layer-providers"', 'id="viz-layer-capabilities"',
                         'id="viz-layer-resources"', 'id="viz-layer-knowledge"', 'id="viz-zoom-in"',
                         'id="viz-frame-measure"', 'id="viz-frame-metric"', 'Measure 300 frames',
                         'id="viz-pan-down"', 'id="viz-search"', 'Find records by name, ID, type, or state',
                         'Current APIs expose no department records', 'Separate source snapshots may have different timestamps',
                         'href="/ui/chat"', 'href="/ui/providers"'):
            assert fragment in html
        assert "<script" in html and "onclick" not in html.lower()
        assert "script-src 'self'" in response.headers["content-security-policy"]


def test_advanced_map_has_no_vendored_webgl_and_keeps_same_origin_client():
    with _client() as client:
        for name in ("three.module.js", "three.core.js"):
            response = client.get(f"/ui/static/vendor/three/{name}")
            assert response.status_code == 404
        assert client.get('/ui/static/brain-three.mjs').status_code==404
        assert client.get('/ui/static/three-scene.mjs').status_code==404
        module=client.get("/ui/static/visualization.mjs")
        assert module.headers["content-type"].startswith("text/javascript")
        assert 'vendor/three' not in module.text and 'import("./three-scene.mjs")' not in module.text


def test_sage_core_page_is_a_read_only_agent_map_with_accessible_fallback():
    with _client() as client:
        response = client.get("/ui/sage-core")
        assert response.status_code == 200
        html = response.text
        for fragment in ('<h1>Sage Core</h1>', 'id="sage-core-canvas" tabindex="0"',
                         'id="sage-core-accessible-list"', 'id="sage-core-reduced-motion"',
                         'id="sage-core-detail-content"', 'src="/ui/static/sage-core.mjs"',
                         'href="/ui/sage-core"', 'It cannot start or approve work.'):
            assert fragment in html
        assert "onclick" not in html.lower()
        assert "script-src 'self'" in response.headers["content-security-policy"]
        script = client.get("/ui/static/sage-core.mjs")
        assert script.status_code == 200
        assert script.headers["content-type"].startswith("text/javascript")
