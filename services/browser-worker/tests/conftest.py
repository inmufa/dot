import threading
from collections.abc import AsyncIterator, Awaitable, Callable, Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import httpx
import pytest
from dot_browser.guard import Resolver
from dot_browser.main import create_app
from dot_browser.settings import Settings
from playwright.sync_api import sync_playwright

FORM = """<!doctype html><html><head><title>Fixture Form</title></head><body>
<h1>Welcome page</h1><p>Some visible paragraph text.</p>
<a href="/page2">Next page</a>
<form action="/result" method="get">
<label for="q">Query</label><input id="q" name="q" type="text">
<input name="pw" type="password" aria-label="Secret">
<select name="color" aria-label="Color"><option value="r">Red</option>
<option value="g">Green</option></select>
<button type="submit">Search</button></form>
<button id="hid" style="display:none">Hidden</button>
<button onclick="document.getElementById('out').textContent='clicked'">Press me</button>
<div id="out"></div>
</body></html>"""

ARTICLE = (
    "<html><head><title>Article</title></head><body><nav>menu</nav><article>"
    "<h1>Big Story</h1>"
    + "<p>This is a long paragraph about nothing in particular. "
    * 20
    + "</p><p>Second paragraph with <a href='/page2'>a link</a>.</p></article>"
    "<footer>footer junk</footer></body></html>"
)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_args: object) -> None:
        return

    def _send(self, body: str, status: int = 200, **headers: str) -> None:
        data = body.encode()
        self.send_response(status)
        self.send_header("Content-Type", headers.pop("ctype", "text/html"))
        self.send_header("Content-Length", str(len(data)))
        for k, v in headers.items():
            self.send_header(k.replace("_", "-"), v)
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:
        path = self.path.split("?")[0]
        if path == "/result":
            return self._send(
                f"<title>Result</title><body><p>got {self.path}</p></body>"
            )
        body, status, headers = ROUTES.get(path, ("nope", 404, {}))
        return self._send(body, status, **headers)


def _redirect(target: str) -> tuple[str, int, dict[str, str]]:
    return "", 302, {"Location": target}


POPUP_JS = "for(let i=0;i<20;i++)window.open('/page2');"
ROUTES: dict[str, tuple[str, int, dict[str, str]]] = {
    "/form": (FORM, 200, {}),
    "/page2": ("<title>Second</title><body><p>page two</p></body>", 200, {}),
    "/article": (ARTICLE, 200, {}),
    "/big": ("<body>" + "<p>word</p>" * 5000 + "</body>", 200, {}),
    "/many": (
        "<body>"
        + "".join(f"<a href='/page2?{i}'>L{i}</a> " for i in range(60))
        + "</body>",
        200,
        {},
    ),
    "/to-private": _redirect("http://169.254.169.254/latest/meta-data"),
    "/to-lan": _redirect("http://10.0.0.5/"),
    "/to-page2": _redirect("/page2"),
    "/loop": _redirect("/loop"),
    "/subres": (
        "<title>Sub</title><body><img src='http://169.254.169.254/x.png'><p>ok</p></body>",
        200,
        {},
    ),
    "/dialog": (
        "<title>Dlg</title><body><script>alert('hi');</script>ok</body>",
        200,
        {},
    ),
    "/popups": (
        f'<title>Pop</title><body><button onclick="{POPUP_JS}">go</button></body>',
        200,
        {},
    ),
    "/download": (
        "data",
        200,
        {
            "ctype": "application/octet-stream",
            "Content_Disposition": "attachment; filename=a.bin",
        },
    ),
    "/img.png": ("x", 200, {"ctype": "image/png"}),
    "/imgpage": (
        "<title>Img</title><body><img src='/img.png'><p>t</p></body>",
        200,
        {},
    ),
}


@pytest.fixture(scope="session")
def server() -> Iterator[str]:
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()


@pytest.fixture(scope="session")
def _chromium_available() -> None:
    try:
        with sync_playwright() as p:
            p.chromium.launch().close()
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"chromium unavailable: {str(exc).splitlines()[0][:120]}")


Make = Callable[..., Awaitable[httpx.AsyncClient]]


@pytest.fixture
async def make(_chromium_available: None) -> AsyncIterator[Make]:
    apps, clients = [], []

    async def _make(
        *,
        resolver: Resolver | None = None,
        session: str = "s1",
        loopback: bool = True,
        **cfg: object,
    ) -> httpx.AsyncClient:
        settings = Settings(unsafe_allow_loopback=loopback, **cfg)
        app = create_app(settings, resolver=resolver)
        c = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://t",
            headers={"X-Session-Id": session},
        )
        apps.append(app)
        clients.append(c)
        c.app = app  # type: ignore[attr-defined]
        return c

    yield _make
    for c in clients:
        await c.aclose()
    for a in apps:
        await a.state.manager.shutdown()


@pytest.fixture
async def client(make: Make) -> httpx.AsyncClient:
    return await make()
