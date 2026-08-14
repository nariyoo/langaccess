# -*- coding: utf-8 -*-
"""Tests for the address guard on the public web front end.

DNS is replaced throughout, so nothing here resolves a real name or opens a browser. What is being
tested is the one thing a public endpoint that fetches arbitrary URLs has to get right: an address
that points inside a private network is refused, and refusing it is not itself a crash.
"""
import os
import socket
import sys

import pytest

pytest.importorskip('fastapi')

HERE = os.path.dirname(os.path.abspath(__file__))
# app.py finds the package the same way when it is run from a checkout
for _cand in (os.path.join(HERE, '..', 'web'),):
    if os.path.isdir(_cand):
        sys.path.insert(0, _cand)
import app as APP                                                              # noqa: E402
from fastapi import HTTPException                                              # noqa: E402


def _resolves_to(monkeypatch, addr, family=socket.AF_INET):
    def fake_getaddrinfo(host, port, *a, **k):
        return [(family, socket.SOCK_STREAM, 6, '', (addr, 0))]
    monkeypatch.setattr(socket, 'getaddrinfo', fake_getaddrinfo)


PRIVATE = [
    ('loopback', '127.0.0.1'),
    ('a private range', '10.0.0.1'),
    ('carrier NAT', '100.64.0.1'),
    ('the cloud metadata address', '169.254.169.254'),
]


@pytest.mark.parametrize('name,addr', PRIVATE, ids=[n for n, _ in PRIVATE])
def test_an_address_off_the_public_internet_is_refused(monkeypatch, name, addr):
    _resolves_to(monkeypatch, addr)
    with pytest.raises(HTTPException) as e:
        APP.public_http_url('https://inside.example')
    assert e.value.status_code == 400


def test_a_scoped_ipv6_address_is_refused_and_does_not_crash(monkeypatch):
    """fe80::1%eth0 carries a scope that is not part of the address. Parsing it whole raised
    ValueError, which reached the client as HTTP 500 instead of a refusal."""
    _resolves_to(monkeypatch, 'fe80::1%eth0', family=socket.AF_INET6)
    with pytest.raises(HTTPException) as e:
        APP.public_http_url('https://inside.example')
    assert e.value.status_code == 400


def test_a_public_address_is_accepted(monkeypatch):
    _resolves_to(monkeypatch, '93.184.216.34')
    assert APP.public_http_url('example.com') == 'https://example.com'


def test_only_http_and_https(monkeypatch):
    _resolves_to(monkeypatch, '93.184.216.34')
    with pytest.raises(HTTPException) as e:
        APP.public_http_url('ftp://example.com/file')
    assert e.value.status_code == 400


def test_only_the_standard_web_ports(monkeypatch):
    _resolves_to(monkeypatch, '93.184.216.34')
    with pytest.raises(HTTPException) as e:
        APP.public_http_url('https://example.com:8080/')
    assert e.value.status_code == 400
    assert APP.public_http_url('https://example.com:443/') == 'https://example.com:443/'


def test_healthz_answers():
    from fastapi.testclient import TestClient
    with TestClient(APP.app) as client:
        resp = client.get('/healthz')
    assert resp.status_code == 200 and resp.json() == {'ok': True}


def test_the_rate_limit_does_not_keep_every_address_that_ever_called():
    """_hits held one list per address for the life of the process."""
    import time
    APP._hits.clear()
    APP._hits['1.2.3.4'] = [time.time() - 7200]      # last seen two hours ago

    class _Req:
        headers = {'x-forwarded-for': '5.6.7.8'}
        client = None

    APP.within_budget(_Req())
    assert '1.2.3.4' not in APP._hits
    assert '5.6.7.8' in APP._hits
    APP._hits.clear()


class _Forwarded:
    headers = {'x-forwarded-for': '5.6.7.8'}

    class client:
        host = '9.9.9.9'


def test_the_forwarded_header_is_ignored_when_it_is_not_trusted(monkeypatch):
    """Reached directly, a caller writes X-Forwarded-For themselves and spends the budget of any
    address they invent, so the per-address limit stops limiting anything."""
    monkeypatch.setenv('LANGACCESS_TRUST_XFF', '0')
    APP._hits.clear()
    APP.within_budget(_Forwarded())
    assert '9.9.9.9' in APP._hits and '5.6.7.8' not in APP._hits
    APP._hits.clear()


def test_the_forwarded_header_is_trusted_by_default(monkeypatch):
    """Behind a proxy it is the only real client address, so the default has to stay as it was."""
    monkeypatch.delenv('LANGACCESS_TRUST_XFF', raising=False)
    APP._hits.clear()
    APP.within_budget(_Forwarded())
    assert '5.6.7.8' in APP._hits and '9.9.9.9' not in APP._hits
    APP._hits.clear()


class _Chained:
    # `client, proxy1`: each proxy appends the address it received from, so the trusted edge's
    # entry is the LAST one. The leftmost is written by the caller and is spoofable.
    headers = {'x-forwarded-for': '1.1.1.1, 5.6.7.8'}

    class client:
        host = '9.9.9.9'


def test_the_rightmost_forwarded_hop_is_the_one_trusted(monkeypatch):
    """Taking the leftmost let a caller prepend any address and spend its budget. The value the
    trusted edge appended is the last one."""
    monkeypatch.delenv('LANGACCESS_TRUST_XFF', raising=False)
    APP._hits.clear()
    APP.within_budget(_Chained())
    assert '5.6.7.8' in APP._hits and '1.1.1.1' not in APP._hits
    APP._hits.clear()


def test_a_nat64_wrapped_private_address_is_refused(monkeypatch):
    """64:ff9b::7f00:1 is 127.0.0.1 wrapped in a globally routable IPv6 prefix, so is_global answers
    yes on it. A resolver behind a NAT64 gateway can hand that back, so the embedded v4 is judged."""
    _resolves_to(monkeypatch, '64:ff9b::7f00:1', family=socket.AF_INET6)
    with pytest.raises(HTTPException) as e:
        APP.public_http_url('https://inside.example')
    assert e.value.status_code == 400


def test_a_nat64_wrapped_public_address_is_accepted(monkeypatch):
    """The same prefix wrapping a public v4 (93.184.216.34) is a real, reachable address."""
    _resolves_to(monkeypatch, '64:ff9b::5db8:d822', family=socket.AF_INET6)
    assert APP.public_http_url('example.com') == 'https://example.com'


def test_the_openapi_ui_is_off():
    """docs_url=None: the interactive schema browser is not exposed on a service that fetches
    arbitrary URLs for the public."""
    from fastapi.testclient import TestClient
    with TestClient(APP.app) as client:
        assert client.get('/openapi').status_code == 404
        assert client.get('/docs').status_code == 404


def test_the_retry_front_door_refuses_carrier_nat():
    """`refused` and the web `public_http_url` have to agree on what private means, so a list that
    misses carrier NAT (100.64.0.0/10) does not let one front door in where the other keeps it out."""
    from langaccess.retry import refused
    assert refused('http://100.64.0.1/') != ''
    assert refused('http://10.0.0.1/') != ''
    assert refused('https://example.com/') == ''
