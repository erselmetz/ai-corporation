from fastapi.testclient import TestClient

from app.local import create_local_app
from app.runtime.factory import create_corporation_runtime

PASSWORD = "test-owner-passphrase"
ORIGIN = "http://127.0.0.1:8000"


def _client():
    runtime = create_corporation_runtime()
    app = create_local_app(password=PASSWORD, application_service=runtime.application_service)
    return TestClient(app, base_url=ORIGIN, client=("127.0.0.1", 50000))


def test_visualization_page_is_3d_first_with_accessible_alternatives_and_setup_links():
    with _client() as client:
        response = client.get("/ui/visualization")
        assert response.status_code == 200
        html = response.text
        for fragment in ('id="viz-canvas"', 'tabindex="0"', 'id="viz-list"', 'id="viz-reduce-motion"',
                         'id="viz-effects"', 'href="/ui/chat"', 'href="/ui/providers"'):
            assert fragment in html
        assert "<script" in html and "onclick" not in html.lower()
        assert "script-src 'self'" in response.headers["content-security-policy"]


def test_vendored_three_is_served_same_origin_as_javascript_with_license():
    with _client() as client:
        for name in ("three.module.js", "three.core.js"):
            response = client.get(f"/ui/static/vendor/three/{name}")
            assert response.status_code == 200
            assert "javascript" in response.headers["content-type"] or name.endswith(".js")
        assert "MIT" in client.get("/ui/static/vendor/three/LICENSE").text
        assert client.get("/ui/static/visualization.mjs").headers["content-type"].startswith("text/javascript")