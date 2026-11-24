import ipaddress

import pytest
from backend.core.ssrf import Blocked, ip_problem, vet
from web_helpers import PUBLIC, counting, fixed

BLOCKED_URLS = [
    "http://127.0.0.1/",
    "http://127.1/",
    "http://127.255.255.254/",
    "http://0.0.0.0/",
    "http://10.1.2.3/",
    "http://172.16.0.1/",
    "http://192.168.1.1/",
    "http://169.254.169.254/latest/meta-data/",
    "http://100.64.0.1/",  # CGNAT
    "http://100.100.100.200/",  # Alibaba metadata
    "http://224.0.0.1/",
    "http://240.0.0.1/",
    "http://[::1]/",
    "http://[::]/",
    "http://[fe80::1]/",
    "http://[fc00::1]/",
    "http://[fd00:ec2::254]/",  # AWS IPv6 metadata
    "http://[::ffff:127.0.0.1]/",
    "http://[::ffff:7f00:1]/",
    "http://[::ffff:169.254.169.254]/",
    "http://[::7f00:1]/",  # deprecated IPv4-compatible
    "http://[::127.0.0.1]/",
    "http://[fec0::1]/",  # site-local
    "http://192.88.99.1/",  # 6to4 relay anycast
    "http://[64:ff9b::7f00:1]/",  # NAT64 to loopback
    "http://[2002:7f00:1::]/",  # 6to4 to loopback
    "http://2130706433/",  # decimal
    "http://0x7f000001/",  # hex
    "http://0x7f.0.0.1/",
    "http://0177.0.0.1/",  # octal
    "http://017700000001/",
    "http://localhost/",
    "http://localhost./",
    "http://LOCALHOST/",
    "http://foo.localhost/",
    "http://metadata.google.internal/",
    "http://printer.local/",
    "http://intranet/",  # single-label host
    "http://good@127.0.0.1/",
    "http://127.0.0.1@example.com/",
    "http://user:pw@example.com/",
    "http://example.com%00.evil.com@127.0.0.1/",
    "http://0x/",
    "ftp://example.com/",
    "file:///etc/passwd",
    "gopher://example.com/",
    "javascript:alert(1)",
    "//example.com/",
    "http:///path",
    "http://example.com/ x",
    "http://example.com/\r\nHost: evil",
    "http://example.com:99999/",
]


@pytest.mark.parametrize("url", BLOCKED_URLS)
async def test_blocked(url: str):
    with pytest.raises(Blocked):
        await vet(url, fixed(PUBLIC))


@pytest.mark.parametrize(
    "ip", ["10.0.0.1", "127.0.0.1", "::1", "169.254.1.1", "100.64.0.1", "fe80::1"]
)
async def test_resolver_answers_are_vetted_too(ip: str):
    with pytest.raises(Blocked):
        await vet("http://example.com/", fixed(ip))


async def test_any_private_answer_blocks_a_mixed_record_set():
    with pytest.raises(Blocked):
        await vet("http://example.com/", fixed(PUBLIC, "10.0.0.5"))


async def test_unresolvable_and_empty():
    with pytest.raises(Blocked):
        await vet("http://example.com/", fixed())


@pytest.mark.parametrize(
    "url",
    [
        "http://example.com/",
        "https://example.com:8443/a/b?q=1#frag",
        "http://example.com./",
        "http://[2606:4700::1111]/",
        "http://1.1.1.1/",
        "http://8.8.8.8:8080/x",
    ],
)
async def test_public_urls_pass(url: str):
    target = await vet(url, fixed(PUBLIC))
    assert target.host
    assert target.ip


async def test_target_is_pinned_and_resolved_once():
    resolver, seen = counting(PUBLIC)
    target = await vet("https://Example.COM./a?b=1", resolver)
    assert seen == ["example.com"]
    assert (target.scheme, target.host, target.port) == ("https", "example.com", 443)
    assert target.ip == PUBLIC
    assert target.path == "/a?b=1"


async def test_ip_literal_skips_the_resolver():
    resolver, seen = counting("127.0.0.1")
    target = await vet("http://1.1.1.1/", resolver)
    assert seen == []
    assert target.ip == "1.1.1.1"


async def test_allow_loopback_is_only_for_loopback():
    assert (await vet("http://127.0.0.1:8000/", fixed(), allow_loopback=True)).ip
    for url in (
        "http://10.0.0.1/",
        "http://169.254.169.254/",
        "http://[::ffff:10.0.0.1]/",
    ):
        with pytest.raises(Blocked):
            await vet(url, fixed(), allow_loopback=True)


def test_ip_problem_public_is_none():
    assert ip_problem(ipaddress.ip_address("8.8.8.8")) is None
    assert ip_problem(ipaddress.ip_address("2606:4700::1111")) is None
