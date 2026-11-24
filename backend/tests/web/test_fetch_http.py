import httpx
import pytest
from backend.cognition.services.tools.web.fetch_http import MAX_BYTES
from backend.core.exceptions import DomainException
from web_helpers import PUBLIC, counting, fetcher, fixed, gz, html_page

OK = httpx.Response(200, text="hi", headers={"content-type": "text/plain"})


async def code_of(awaitable) -> int:
    with pytest.raises(DomainException) as exc:
        await awaitable
    return exc.value.code


async def test_connects_to_the_vetted_ip_with_host_and_sni():
    seen: list[httpx.Request] = []

    def handler(req: httpx.Request) -> httpx.Response:
        seen.append(req)
        return OK

    resolver, calls = counting(PUBLIC)
    page = await fetcher(handler, resolver).get("https://Example.com:8443/a?b=1")
    (req,) = seen
    assert req.url.host == PUBLIC
    assert req.url.port == 8443
    assert req.url.path == "/a"
    assert req.headers["host"] == "example.com:8443"
    assert req.extensions["sni_hostname"] == "example.com"
    assert calls == ["example.com"]  # resolved once per hop
    assert page.body == b"hi"
    assert "authorization" not in req.headers
    assert "cookie" not in req.headers


async def test_ipv6_pin_is_bracketed():
    seen: list[httpx.Request] = []

    def handler(req: httpx.Request) -> httpx.Response:
        seen.append(req)
        return OK

    await fetcher(handler, fixed("2606:4700::1111")).get("http://example.com/")
    assert seen[0].url.host == "2606:4700::1111"


async def test_redirect_to_private_ip_is_blocked():
    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"location": "http://169.254.169.254/x"})

    assert await code_of(fetcher(handler).get("http://example.com/")) == 4012


async def test_redirect_to_hostname_resolving_private_is_blocked():
    answers = {"example.com": PUBLIC, "evil.example.org": "10.0.0.7"}

    async def resolve(host: str, _port: int) -> list[str]:
        return [answers[host]]

    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(301, headers={"location": "http://evil.example.org/"})

    assert await code_of(fetcher(handler, resolve).get("http://example.com/")) == 4012


async def test_dns_rebinding_second_answer_is_vetted():
    answers = iter([[PUBLIC], ["127.0.0.1"]])

    async def resolve(_host: str, _port: int) -> list[str]:
        return next(answers)

    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"location": "/again"})

    assert (
        await code_of(fetcher(handler, resolve).get("http://rebind.example.com/"))
        == 4012
    )


async def test_relative_redirect_and_flag():
    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.path == "/a":
            return httpx.Response(302, headers={"location": "/b"})
        return OK

    page = await fetcher(handler).get("http://example.com/a")
    assert page.redirected
    assert page.url == "http://example.com/b"


async def test_redirect_limit():
    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"location": "/loop"})

    assert await code_of(fetcher(handler).get("http://example.com/")) == 4013


async def test_five_redirects_are_followed():
    def handler(req: httpx.Request) -> httpx.Response:
        n = int(req.url.path.strip("/") or 0)
        if n < 5:
            return httpx.Response(302, headers={"location": f"/{n + 1}"})
        return OK

    assert (await fetcher(handler).get("http://example.com/")).body == b"hi"


async def test_size_cap_truncates():
    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=b"a" * (MAX_BYTES + 5000),
            headers={"content-type": "text/plain"},
        )

    page = await fetcher(handler).get("http://example.com/")
    assert page.truncated
    assert len(page.body) == MAX_BYTES


async def test_decompression_bomb_is_capped():
    bomb = gz(b"a" * 80_000_000)
    assert len(bomb) < MAX_BYTES  # small on the wire

    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=bomb,
            headers={"content-type": "text/plain", "content-encoding": "gzip"},
        )

    page = await fetcher(handler).get("http://example.com/")
    assert page.truncated
    assert len(page.body) <= MAX_BYTES


async def test_gzip_body_is_decoded():
    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=gz(b"hello gzip"),
            headers={"content-type": "text/plain", "content-encoding": "gzip"},
        )

    assert (await fetcher(handler).get("http://example.com/")).body == b"hello gzip"


async def test_unknown_encoding_is_rejected():
    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=b"x",
            headers={"content-type": "text/plain", "content-encoding": "br"},
        )

    assert await code_of(fetcher(handler).get("http://example.com/")) == 4014


@pytest.mark.parametrize(
    "ctype",
    [
        "image/png",
        "application/octet-stream",
        "application/pdf",
        "video/mp4",
        "application/zip",
    ],
)
async def test_binary_content_types_are_rejected(ctype: str):
    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, content=b"\x89PNG\r\n", headers={"content-type": ctype}
        )

    assert await code_of(fetcher(handler).get("http://example.com/")) == 4014


async def test_nul_bytes_without_type_are_rejected():
    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"ab\x00cd")

    assert await code_of(fetcher(handler).get("http://example.com/")) == 4014


@pytest.mark.parametrize(
    "ctype",
    ["application/json", "application/ld+json", "application/atom+xml", "text/xml"],
)
async def test_text_like_types_pass(ctype: str):
    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"{}", headers={"content-type": ctype})

    assert (await fetcher(handler).get("http://example.com/")).body == b"{}"


async def test_http_errors_and_timeouts():
    def err(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(404, text="nope")

    def slow(_req: httpx.Request) -> httpx.Response:
        msg = "slow"
        raise httpx.ReadTimeout(msg)

    def down(_req: httpx.Request) -> httpx.Response:
        msg = "refused"
        raise httpx.ConnectError(msg)

    for handler in (err, slow, down):
        assert await code_of(fetcher(handler).get("http://example.com/")) == 4013


async def test_blocked_url_never_hits_the_network():
    hits = []

    def handler(req: httpx.Request) -> httpx.Response:
        hits.append(req)
        return OK

    f = fetcher(handler)
    for url in (
        "http://127.0.0.1/",
        "http://good@127.0.0.1/",
        "http://2130706433/",
        "http://localhost./",
    ):
        assert await code_of(f.get(url)) == 4012
    assert hits == []


async def test_charset_is_reported():
    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content="é".encode("latin-1"),
            headers={"content-type": "text/html; charset=ISO-8859-1"},
        )

    page = await fetcher(handler).get("http://example.com/")
    assert page.charset == "iso-8859-1"


async def test_html_helper_roundtrip():
    page = await fetcher(lambda _r: html_page("<p>x</p>")).get("http://example.com/")
    assert page.content_type == "text/html"
