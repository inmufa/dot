import pytest
from dot_browser.guard import Blocked, UrlGuard, ip_blocked
from dot_browser.settings import Settings


def guard(resolver=None, **cfg) -> UrlGuard:
    return UrlGuard(Settings(**cfg), resolver)


@pytest.mark.parametrize(
    "ip",
    [
        "127.0.0.1",
        "10.1.2.3",
        "172.16.0.1",
        "192.168.1.1",
        "169.254.169.254",
        "100.64.0.1",
        "100.100.100.200",
        "0.0.0.0",  # noqa: S104
        "::1",
        "fe80::1",
        "fc00::1",
        "::ffff:127.0.0.1",
        "::ffff:10.0.0.1",
        "64:ff9b::a00:1",
        "::7f00:1",
        "::a00:1",
        "fec0::1",
        "192.88.99.1",
        "2002:7f00:1::",
        "224.0.0.1",
        "fd00:ec2::254",
        "garbage",
    ],
)
def test_private_ips_blocked(ip: str) -> None:
    assert ip_blocked(ip)


def test_public_ip_allowed() -> None:
    assert not ip_blocked("93.184.216.34")
    assert not ip_blocked("2606:2800:220:1:248:1893:25c8:1946")


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/",
        "http://localhost:8080/",
        "https://[::1]/",
        "http://169.254.169.254/latest/meta-data",
        "http://10.0.0.1/",
        "http://metadata.google.internal/",
        "http://foo.localhost/",
        "http://[::ffff:7f00:1]/",
        "http://2130706433/",
    ],
)
async def test_default_denies_private_urls(url: str) -> None:
    async def res(host: str) -> list[str]:
        return {"2130706433": ["127.0.0.1"]}.get(host, [])

    with pytest.raises(Blocked):
        await guard(res).check(url, navigation=True)


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "chrome://settings",
        "ftp://x/y",
        "data:text/html,hi",
        "javascript:alert(1)",
        "view-source:http://a/",
    ],
)
async def test_bad_schemes_blocked(url: str) -> None:
    with pytest.raises(Blocked):
        await guard().check(url, navigation=True)


async def test_data_allowed_only_as_subresource() -> None:
    await guard().check("data:image/png;base64,AAAA", navigation=False)
    with pytest.raises(Blocked):
        await guard().check("data:image/png;base64,AAAA", navigation=True)


async def test_loopback_opt_in_is_loopback_only() -> None:
    g = guard(unsafe_allow_loopback=True)
    await g.check("http://127.0.0.1:9/", navigation=True)
    with pytest.raises(Blocked):
        await g.check("http://169.254.169.254/", navigation=True)
    with pytest.raises(Blocked):
        await g.check("http://10.0.0.1/", navigation=True)


async def test_public_host_resolves_and_is_pinned() -> None:
    calls: list[str] = []

    async def res(host: str) -> list[str]:
        calls.append(host)
        return ["93.184.216.34"]

    g = guard(res)
    await g.check("https://example.test/a", navigation=True)
    await g.check("https://example.test/b", navigation=True)
    assert calls == ["example.test"]


async def test_dns_rebinding_flip_blocked() -> None:
    answers = iter([["93.184.216.34"], ["127.0.0.1"]])

    async def res(_host: str) -> list[str]:
        return next(answers)

    g = guard(res, dns_pin_seconds=0)
    await g.check("http://rebind.test/", navigation=True)
    with pytest.raises(Blocked):
        await g.check("http://rebind.test/", navigation=True)


async def test_mixed_answer_blocked_and_not_pinned() -> None:
    async def res(_host: str) -> list[str]:
        return ["93.184.216.34", "10.0.0.7"]

    g = guard(res)
    for _ in range(2):
        with pytest.raises(Blocked):
            await g.check("http://mixed.test/", navigation=True)


async def test_unresolvable_blocked() -> None:
    async def res(_host: str) -> list[str]:
        raise OSError

    with pytest.raises(Blocked):
        await guard(res).check("http://nx.test/", navigation=True)


async def test_allow_and_deny_lists() -> None:
    async def res(_h: str) -> list[str]:
        return ["93.184.216.34"]

    g = guard(res, allow_hosts="good.test", deny_hosts="bad.good.test")
    await g.check("http://good.test/", navigation=True)
    await g.check("http://www.good.test/", navigation=True)
    with pytest.raises(Blocked):
        await g.check("http://bad.good.test/", navigation=True)
    with pytest.raises(Blocked):
        await g.check("http://other.test/", navigation=True)
