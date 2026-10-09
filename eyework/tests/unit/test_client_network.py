"""
مفتاح الشبكة الواحدة
====================
عنوان IPv4 كما هو، وIPv6 بشبكته /64 — المشترك يُعطى /64 كاملة ويغيّر عنوانه فيها
متى شاء، فحدٌّ على العنوان الواحد لا يحدّ شيئاً — وIPv4 المغلَّف في IPv6 عنوان IPv4
نفسه؛ وما ليس عنواناً يبقى كما هو مفتاحاً واحداً.
"""

from __future__ import annotations

import pytest
from starlette.requests import Request

from eyework.web.deps import client_ip, client_network


def _request(host: str | None) -> Request:
    scope = {"type": "http", "method": "GET", "path": "/", "headers": [], "query_string": b"", "scheme": "http",
             "server": ("testserver", 80), "client": (host, 50000) if host else None}
    return Request(scope)


@pytest.mark.parametrize(("host", "network"), [
    ("203.0.113.7", "203.0.113.7"),
    ("::ffff:203.0.113.7", "203.0.113.7"),
    ("2001:db8:1:2::1", "2001:db8:1:2::/64"),
    ("2001:db8:1:2:ffff:ffff:ffff:ffff", "2001:db8:1:2::/64"),
    ("2001:db8:1:3::1", "2001:db8:1:3::/64"),
    ("testclient", "testclient"),
])
def test_the_network_key_is_the_address_or_its_64(host, network):
    assert client_ip(_request(host)) == host
    assert client_network(_request(host)) == network


def test_two_addresses_in_one_64_share_a_key_and_neighbours_do_not():
    assert client_network(_request("2001:db8:1:2::1")) == client_network(_request("2001:db8:1:2:8::9"))
    assert client_network(_request("2001:db8:1:2::1")) != client_network(_request("2001:db8:1:3::1"))


def test_a_request_without_a_client_is_one_unknown_key():
    assert client_ip(_request(None)) == "unknown"
    assert client_network(_request(None)) == "unknown"
