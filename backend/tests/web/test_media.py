import httpx
import pytest
from backend.cognition.services.tools.web.fetch_http import IMAGE_POLICY
from backend.cognition.services.tools.web.search import (
    SearxngClient,
    make_image_search_tool,
    render_images,
)
from backend.core.exceptions import DomainException
from backend.routing.clients.sandbox_client import SandboxResponse
from backend.sessions.services.workspace.media import MediaService
from web_helpers import ctx, fetcher, fixed

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
ROOT = "/ws"


def img(body: bytes = PNG, ctype: str = "image/png") -> httpx.Response:
    return httpx.Response(200, content=body, headers={"content-type": ctype})


async def remote(handler, resolver=None) -> MediaService:
    return MediaService(None, ROOT, fetcher(handler, resolver))  # type: ignore[arg-type]


async def code_of(awaitable) -> int:
    with pytest.raises(DomainException) as exc:
        await awaitable
    return exc.value.code


async def test_remote_image_ok_with_pinned_headers():
    seen: list[httpx.Request] = []

    def handler(req):
        seen.append(req)
        return img()

    m = await remote(handler)
    out = await m.load("s", "https://example.com/a.png")
    assert (out.mime, out.data) == ("image/png", PNG)
    assert "cookie" not in seen[0].headers
    assert "authorization" not in seen[0].headers


async def test_private_ip_blocked():
    m = await remote(lambda _r: img())
    assert await code_of(m.load("s", "http://127.0.0.1/a.png")) == 4020
    m = await remote(lambda _r: img(), fixed("10.0.0.5"))
    assert await code_of(m.load("s", "http://example.com/a.png")) == 4020


async def test_redirect_to_private_blocked():
    def handler(req):
        return httpx.Response(302, headers={"location": "http://169.254.169.254/x.png"})

    m = await remote(handler)
    assert await code_of(m.load("s", "http://example.com/a.png")) == 4020


async def test_too_many_redirects():
    m = await remote(lambda _r: httpx.Response(302, headers={"location": "/n"}))
    assert IMAGE_POLICY.max_redirects == 3
    assert await code_of(m.load("s", "http://example.com/a.png")) == 4023


async def test_size_cap():
    big = PNG + b"\x00" * (8 * 1024 * 1024)
    m = await remote(lambda _r: img(big))
    assert await code_of(m.load("s", "http://example.com/a.png")) == 4022


async def test_non_image_header_and_magic_rejected():
    m = await remote(lambda _r: img(b"<html>x</html>", "text/html"))
    assert await code_of(m.load("s", "http://example.com/a")) == 4021
    m = await remote(lambda _r: img(b"<html>not an image</html>", "image/png"))
    assert await code_of(m.load("s", "http://example.com/a")) == 4021
    m = await remote(lambda _r: img(PNG, "image/jpeg"))  # header/magic mismatch
    assert await code_of(m.load("s", "http://example.com/a")) == 4021


async def test_svg_ok():
    svg = b'<?xml version="1.0"?><svg xmlns="http://www.w3.org/2000/svg"/>'
    m = await remote(lambda _r: img(svg, "image/svg+xml"))
    assert (await m.load("s", "http://example.com/a.svg")).mime == "image/svg+xml"


class FakeSandbox:
    """Files as {path: bytes}; links as {path: real}; root resolves to /ws."""

    def __init__(self, files: dict[str, bytes], links: dict[str, str] | None = None):
        self.files, self.links = files, links or {}

    async def post(self, _sid, _path, payload):
        p = payload["path"]
        real = self.links.get(p, p)
        return SandboxResponse(
            200, {"path": real, "inside": real == ROOT or real.startswith(ROOT + "/")}
        )

    async def get_raw(self, _sid, path, _max):
        if path in self.files:
            return SandboxResponse(200, {}), self.files[path]
        return SandboxResponse(404, {}), b""


def local(files, links=None) -> MediaService:
    return MediaService(FakeSandbox(files, links), ROOT, None)  # type: ignore[arg-type]


async def test_workspace_image_ok_relative_and_absolute():
    m = local({"/ws/pics/a.png": PNG})
    assert (await m.load("s", "pics/a.png")).mime == "image/png"
    assert (await m.load("s", "/ws/pics/a.png")).data == PNG


@pytest.mark.parametrize(
    "src",
    ["../etc/a.png", "/etc/a.png", "/ws/../etc/a.png", "pics/../../x.png"],
)
async def test_traversal_rejected(src):
    assert await code_of(local({}).load("s", src)) == 4020


@pytest.mark.parametrize("src", [".git/a.png", ".dot/x/a.png", "a/.env.png", ".env"])
async def test_dot_paths_rejected(src):
    assert await code_of(local({}).load("s", src)) in (4020, 4021)


async def test_symlink_escape_rejected():
    m = local({"/etc/x.png": PNG}, {"/ws/link.png": "/etc/x.png"})
    assert await code_of(m.load("s", "link.png")) == 4020


async def test_symlink_into_dot_dir_rejected():
    m = local({"/ws/.git/a.png": PNG}, {"/ws/l.png": "/ws/.git/a.png"})
    assert await code_of(m.load("s", "l.png")) == 4020


async def test_non_image_extension_and_magic_rejected():
    m = local({"/ws/a.txt": PNG, "/ws/b.png": b"hello world"})
    assert await code_of(m.load("s", "a.txt")) == 4021
    assert await code_of(m.load("s", "b.png")) == 4021


async def test_missing_file():
    assert await code_of(local({}).load("s", "nope.png")) == 4023


async def test_endpoint_headers_and_auth(client, app):
    app.state.media = await remote(lambda _r: img())
    token = {"Authorization": "Bearer " + "t" * 32}
    r = await client.get("/v1/media", params={"src": "http://example.com/a.png"})
    assert r.status_code == 401
    r = await client.get(
        "/v1/media", params={"src": "http://example.com/a.png"}, headers=token
    )
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/png"
    assert r.headers["content-security-policy"] == "sandbox"
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["cache-control"] == "private, max-age=3600"
    r = await client.get(
        "/v1/media", params={"src": "http://10.0.0.1/a"}, headers=token
    )
    assert r.status_code == 400


RESULTS = [
    {
        "title": "Cat | big",
        "img_src": "https://i.example.com/c.jpg",
        "url": "https://p.example.com/c",
    },
    {"title": "no img", "url": "https://p.example.com/x"},
    {
        "title": "bad",
        "img_src": "javascript:alert(1)",
        "url": "https://p.example.com/y",
    },
    {"title": "data", "img_src": "data:image/png;base64,AAAA"},
] + [
    {
        "title": f"t{i}",
        "img_src": f"https://i.example.com/{i}.png",
        "url": f"https://p.example.com/{i}",
    }
    for i in range(12)
]


def test_render_images_format_and_cap():
    lines = render_images(RESULTS).splitlines()
    assert len(lines) == 8
    assert (
        lines[0]
        == "1. Cat / big | https://i.example.com/c.jpg | https://p.example.com/c"
    )
    assert lines[1].startswith("2. t0 | https://i.example.com/0.png | ")


async def test_image_search_tool():
    seen: list[httpx.Request] = []

    def handler(req):
        seen.append(req)
        return httpx.Response(200, json={"results": RESULTS})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    t = make_image_search_tool(SearxngClient("http://searx:8080", client))
    d = t.definition
    assert (d.name, d.deferred, d.mutating) == ("ImageSearch", False, False)
    r = await t.run(ctx(), {"query": "cats"})
    assert r.tainted
    assert seen[0].url.params["categories"] == "images"
    assert r.output.startswith("1. Cat / big | ")
    empty = await t.run(ctx(), {"query": " "})
    assert empty.is_error
