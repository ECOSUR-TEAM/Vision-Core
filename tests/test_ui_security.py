"""Seguridad de output encoding del monitor: sinks prohibidos y payloads literales."""

import json
import re
import shutil
import subprocess
import threading
from html.parser import HTMLParser
from pathlib import Path
from urllib.request import urlopen

import pytest

from vision_core.core.domain.event import Event
from vision_core.features.monitor.infrastructure.http.server import make_server
from vision_core.features.monitor.infrastructure.state import MonitorState

PROJECT_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_ROOTS = (PROJECT_ROOT / "src" / "vision_core" / "features" / "monitor" / "infrastructure" / "http",)
INDEX = FRONTEND_ROOTS[0] / "static" / "index.html"

FORBIDDEN_SINKS = (
    "innerHTML",
    "outerHTML",
    "insertAdjacentHTML",
    "document.write",
    "eval(",
    "new Function",
)
PAYLOADS = (
    "<script>alert(1)</script>",
    "<img src=x onerror=alert(1)>",
    "javascript:alert(1)",
)


class _ScriptExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._in_script = False
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "script":
            self._in_script = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "script":
            self._in_script = False

    def handle_data(self, data: str) -> None:
        if self._in_script:
            self.parts.append(data)


DOM_HARNESS = r"""
class StubElement {
  constructor(tag) {
    this.tagName = String(tag).toUpperCase();
    this.children = [];
    this.textContent = '';
    this.hidden = false;
    this.className = '';
    this.src = '';
    this.classList = { toggle: () => {} };
  }
  replaceChildren(...nodes) { this.children = nodes.slice(); }
  append(...nodes) { this.children.push(...nodes); }
}
const nodes = {};
globalThis.document = {
  getElementById(id) {
    if (!nodes[id]) nodes[id] = new StubElement(id === 'video' ? 'IMG' : 'DIV');
    return nodes[id];
  },
  createElement(tag) { return new StubElement(tag); }
};
globalThis.performance = { now: () => 1000 };
globalThis.AbortSignal = { timeout: () => undefined };
globalThis.fetch = () => new Promise(() => {});
globalThis.setTimeout = () => 0;
globalThis.URL = { createObjectURL: () => 'blob:stub', revokeObjectURL: () => {} };
globalThis.Image = class { constructor() { this.src = ''; } decode() { return Promise.resolve(); } };
"""

DOM_DRIVER = r"""
state = globalThis.__STATE__;
lastImageAt = performance.now();
videoFailed = false;
render();
const texts = [];
const tags = [];
function collect(node) {
  tags.push(node.tagName);
  if (typeof node.textContent === 'string') texts.push(node.textContent);
  for (const child of node.children) collect(child);
}
collect(document.getElementById('people'));
collect(document.getElementById('events'));
globalThis.__RESULT__ = JSON.stringify({ texts, tags, videoSrc: document.getElementById('video').src });
console.log(globalThis.__RESULT__);
"""

QUALITY_DRIVER = r"""
state = globalThis.__STATE__;
lastImageAt = performance.now();
render();
globalThis.__RESULT__ = JSON.stringify({
  hidden: document.getElementById('qualityNotice').hidden,
  text: document.getElementById('qualityNotice').textContent,
  statusText: document.getElementById('statusText').textContent,
});
console.log(globalThis.__RESULT__);
"""

IMAGE_SOURCE_DRIVER = r"""
const video = document.getElementById('video');
const results = [];
for (const url of globalThis.__URLS__) {
  video.src = '';
  try {
    setImageSource(video, url);
    results.push({ url, src: video.src, error: null });
  } catch (error) {
    results.push({ url, src: video.src, error: error.message });
  }
}
console.log(JSON.stringify(results));
"""

ZONE_VALIDATION_DRIVER = r"""
const valid = {
  version: '1.0', frame_size: [640, 480],
  exterior: [[0, 0], [320, 0], [320, 479], [0, 479]],
  interior: [[320, 0], [639, 0], [639, 479], [320, 479]],
  door: [[290, 120], [350, 120], [350, 420], [290, 420]]
};
const short = JSON.parse(JSON.stringify(valid));
short.door = [[1, 1], [2, 2]];
const selfCrossing = JSON.parse(JSON.stringify(valid));
selfCrossing.door = [[300, 100], [500, 400], [350, 120], [350, 420]];
const oversized = JSON.parse(JSON.stringify(valid));
oversized.exterior = 'x'.repeat(101 * 1024);
globalThis.__RESULT__ = JSON.stringify({
  valid: validateZoneDraft(valid),
  short: validateZoneDraft(short),
  crossing: validateZoneDraft(selfCrossing),
  oversized: validateZoneDraft(oversized),
});
console.log(globalThis.__RESULT__);
"""

ZONE_XSS_DRIVER = r"""
const payload = '<script>alert(1)</script>';
const node = zoneLabelNode(payload);
showZoneIssue(payload);
const issue = document.getElementById('zoneValidation');
globalThis.__RESULT__ = JSON.stringify({
  tag: node.tagName,
  text: node.textContent,
  children: node.children.length,
  issue: issue.textContent,
  issueChildren: issue.children.length,
});
console.log(globalThis.__RESULT__);
"""


def _frontend_files():
    for root in FRONTEND_ROOTS:
        if root.exists():
            yield from (path for path in root.rglob("*") if path.suffix in {".html", ".js"})


def _frontend_source():
    return "\n".join(path.read_text(encoding="utf-8") for path in _frontend_files())


@pytest.mark.parametrize("sink", FORBIDDEN_SINKS)
def test_frontend_has_no_unsafe_dom_sink(sink):
    hits = []
    for path in _frontend_files():
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if sink in line:
                hits.append(f"{path.relative_to(PROJECT_ROOT)}:{lineno}")
    assert not hits, f"Sink prohibido {sink!r} en el frontend: {hits}"


@pytest.mark.parametrize("field", ("display_name", "person_id", "metadata", "zone"))
def test_dynamic_fields_are_rendered_with_text_content(field):
    pattern = rf"\.textContent\s*=\s*[^\n;]*{re.escape(field)}"
    assert re.search(pattern, _frontend_source()), f"El campo {field} no se asigna mediante textContent"


def test_dynamic_image_sources_are_restricted_to_monitor_blobs():
    source = _frontend_source()
    assert "image.tagName !== 'IMG'" in source
    assert "normalized.startsWith('javascript:')" in source
    assert "normalized.startsWith('data:text/html')" in source
    assert "!normalized.startsWith('blob:')" in source
    assert "setImageSource(decoded, next)" in source
    assert "setImageSource(el('video'), next)" in source
    assert ".setAttribute(" not in source
    assert re.search(r"\.href\s*=", source) is None


def _run_monitor_js(state, driver):
    parser = _ScriptExtractor()
    parser.feed(INDEX.read_text(encoding="utf-8"))
    script = "".join(parser.parts)
    program = DOM_HARNESS + f"\nglobalThis.__STATE__ = {json.dumps(state)};\n" + script + "\n" + driver
    result = subprocess.run(["node", "-e", program], capture_output=True, timeout=15, check=False)
    assert result.returncode == 0, f"El renderizado JS falló: {result.stderr.decode('utf-8', errors='replace')}"
    return result.stdout.decode("utf-8").strip()


def _render_with_node(state):
    return json.loads(_run_monitor_js(state, DOM_DRIVER))


def _image_source_results(urls):
    driver = f"globalThis.__URLS__ = {json.dumps(urls)};\n" + IMAGE_SOURCE_DRIVER
    return json.loads(_run_monitor_js(None, driver))


def _render_quality(state):
    return json.loads(_run_monitor_js(state, QUALITY_DRIVER))


def _zone_validation_results():
    return json.loads(_run_monitor_js(None, ZONE_VALIDATION_DRIVER))


def _zone_xss_result():
    return json.loads(_run_monitor_js(None, ZONE_XSS_DRIVER))


@pytest.fixture
def monitor_server():
    state = MonitorState()
    server = make_server("127.0.0.1", 0, state)
    thread = threading.Thread(target=server.serve_forever)
    thread.start()
    try:
        yield server, state
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js es necesario para ejecutar el DOM simulado")
def test_backend_transmits_payloads_and_frontend_renders_them_as_text(monitor_server):
    server, state = monitor_server
    people = [
        {
            "person_id": PAYLOADS[2],
            "display_name": PAYLOADS[1],
            "zone": PAYLOADS[0],
        }
    ]
    state.publish(b"jpeg", people, 1)
    state.event(Event(event="PERSON_ENTERED", person_id=PAYLOADS[2], metadata={"detail": PAYLOADS[0]}))

    with urlopen(f"http://127.0.0.1:{server.server_port}/api/v1/state") as response:
        body = json.load(response)

    # El backend no sanitiza: transmite los payloads exactamente igual.
    assert body["people"][0]["person_id"] == PAYLOADS[2]
    assert body["people"][0]["display_name"] == PAYLOADS[1]
    assert body["people"][0]["zone"] == PAYLOADS[0]
    assert body["events"][0]["person_id"] == PAYLOADS[2]
    assert body["events"][0]["metadata"]["detail"] == PAYLOADS[0]

    result = _render_with_node(body)

    # El frontend los coloca como texto literal, nunca como marcado ni como URL activa.
    for payload in PAYLOADS:
        assert any(payload in text for text in result["texts"]), f"{payload!r} no aparece como texto literal"
    assert not {"SCRIPT", "IMG"}.intersection(result["tags"])
    assert result["videoSrc"] == ""


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js es necesario para ejecutar el DOM simulado")
@pytest.mark.parametrize(
    ("url", "accepted"),
    [
        ("blob:https://localhost:8000/frame-1", True),
        ("javascript:alert(1)", False),
        ("JAVASCRIPT:alert(1)", False),
        ("data:text/html,<script>alert(1)</script>", False),
        ("https://example.com/image.png", False),
    ],
)
def test_image_source_guard_allows_only_monitor_blobs(url, accepted):
    result = _image_source_results([url])[0]

    assert result["url"] == url
    if accepted:
        assert result["error"] is None
        assert result["src"] == url
    else:
        assert result["error"]
        assert result["src"] == ""


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js es necesario para ejecutar el DOM simulado")
def test_quality_warning_is_visible_without_blocking_live_view():
    result = _render_quality(
        {
            "status": "running",
            "demo_zones": False,
            "people": [],
            "events": [],
            "camera_quality": {"status": "degraded", "reason": "BLURRY_FRAME", "signals": {"BLURRY_FRAME": True}},
        }
    )

    assert result["hidden"] is False
    assert "borrosa" in result["text"]
    assert result["statusText"] == "En vivo"


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js es necesario para ejecutar el DOM simulado")
def test_quality_warning_is_hidden_when_camera_is_ok():
    result = _render_quality(
        {
            "status": "running",
            "demo_zones": False,
            "people": [],
            "events": [],
            "camera_quality": {"status": "ok", "reason": None, "signals": {}},
        }
    )

    assert result["hidden"] is True
    assert result["text"] == ""


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js es necesario para ejecutar el DOM simulado")
def test_unknown_zone_with_prototype_key_falls_back_to_camera_label():
    result = _render_with_node(
        {
            "status": "running",
            "demo_zones": False,
            "people": [{"person_id": "p1", "display_name": "Persona 1", "zone": "toString"}],
            "events": [],
        }
    )

    assert "En cámara" in result["texts"]
    assert not any("function" in text for text in result["texts"])


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js es necesario para ejecutar el DOM simulado")
def test_zone_editor_validates_geometry_and_size_before_saving():
    result = _zone_validation_results()

    assert result["valid"] is None
    assert "al menos 3 vértices" in result["short"]
    assert "cruza consigo mismo" in result["crossing"]
    assert "tamaño máximo" in result["oversized"]


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js es necesario para ejecutar el DOM simulado")
def test_zone_editor_renders_dynamic_labels_as_text():
    result = _zone_xss_result()

    assert result["tag"] == "OPTION"
    assert result["text"] == "<script>alert(1)</script>"
    assert result["children"] == 0
    assert result["issue"] == "<script>alert(1)</script>"
    assert result["issueChildren"] == 0
