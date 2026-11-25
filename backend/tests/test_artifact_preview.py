from backend.sessions.services.workspace.preview import _RENDER, preview_response


def _html(src: str):
    return preview_response(src.encode(), "/w/a.html", render=True)


def test_render_csp_allows_scripts_but_no_network_and_no_same_origin():
    r = _html("<h1>x</h1>")
    csp = r.headers["content-security-policy"]
    assert csp == _RENDER
    assert csp.startswith("sandbox allow-scripts;")
    assert "allow-same-origin" not in csp
    assert "default-src 'none'" in csp
    assert "connect-src 'none'" in csp
    assert "script-src 'unsafe-inline'" in csp
    assert "http" not in csp  # no remote source anywhere


def test_chart_tag_is_inlined_and_reporter_prepended():
    body = _html(
        "<html><head><title>t</title></head><body>"
        '<script src="dot-chart.js"></script><script>new Chart(1,{})</script></body></html>'
    ).body.decode()
    assert 'src="dot-chart.js"' not in body
    assert "Chart.js v4" in body  # vendored library text
    assert body.index("dotArtifact") < body.index("new Chart(1,{})")
    assert body.startswith("<html><head><script>")


def test_html_without_head_gets_reporter_first():
    assert _html("<p>hi</p>").body.decode().startswith("<script>")


def test_plain_preview_stays_locked_and_unmodified():
    r = preview_response(b"<script>x</script>", "/w/a.html", render=False)
    assert r.body == b"<script>x</script>"
    assert r.headers["content-security-policy"] == "default-src 'none'; sandbox"
