# -*- coding: utf-8 -*-
"""A web front end for langaccess: paste an address, get the verdict and the evidence behind it.

The package needs a real browser, so this is an ordinary long-running service rather than a
serverless function. It is deliberately small: one page, one endpoint, and the guards a public
endpoint that fetches arbitrary URLs has to have.

  uvicorn app:app --reload --port 8000

Guards, in the order they run:

  rate               a per-address budget and a global cap on how many browsers run at once, since
                     each audit holds a Chrome instance for tens of seconds. This runs first,
                     because the address check below costs a DNS lookup and an unlimited number of
                     those is itself something to hand an attacker.
  caller address     behind a proxy the X-Forwarded-For header carries the only real client
                     address, and reached directly the caller writes that header themselves and
                     spends the budget of whatever address they invent. Set
                     LANGACCESS_TRUST_XFF=0 when the service is exposed with nothing in front of
                     it, and the socket address is used instead.
  scheme and host    only http and https, only a public address. A checker that will fetch any
                     address you hand it is a way to read a private network from outside it, so
                     every resolved address is tested for being globally routable before the
                     browser is started.
  every request      the check above tests the address, not the fetch. The browser resolves the
                     name again itself and follows redirects wherever they point, so the audit runs
                     with block_private_hosts=True, which resolves the host of every request the
                     browser makes and aborts the ones that land off the public internet.
  time               every audit is capped; a site with many language controls can otherwise run for
                     the better part of an hour.
"""
import os, sys, time, socket, asyncio, ipaddress, collections
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

HERE = os.path.dirname(os.path.abspath(__file__))
# importable both from a checkout (web/ beside src/) and from an installed package
for cand in (os.path.join(HERE, '..', 'src'), os.path.join(HERE, '..', 'langaccess', 'src')):
    if os.path.isdir(os.path.join(cand, 'langaccess')):
        sys.path.insert(0, cand)
        break
from langaccess import audit_async, Result                                # noqa: E402
from langaccess.address import AddressRejected, auditable_url            # noqa: E402

AUDIT_TIMEOUT = float(os.environ.get('LANGACCESS_TIMEOUT', 120))
MAX_CONCURRENT = int(os.environ.get('LANGACCESS_CONCURRENCY', 2))
PER_IP_PER_HOUR = int(os.environ.get('LANGACCESS_PER_IP_PER_HOUR', 20))
# A ceiling on how many callers may be WAITING for a browser at once. Each request holds a
# connection while it waits on the semaphore, so an unbounded queue is a way to tie the service up
# with almost no traffic. Past this, the endpoint says 503 rather than accepting work it cannot get
# to; the browser cap itself stays at MAX_CONCURRENT.
MAX_WAITING = int(os.environ.get('LANGACCESS_MAX_WAITING', 16))
# A ceiling on how many addresses the rate-limiter remembers. `within_budget` already drops entries
# older than an hour on every call, but an attacker rotating addresses can still grow the table
# inside that hour; this bounds it. It is far above any real caller count.
MAX_HITS = int(os.environ.get('LANGACCESS_MAX_HITS', 100000))

app = FastAPI(title='langaccess', docs_url=None, redoc_url=None)
_browsers = asyncio.Semaphore(MAX_CONCURRENT)
_waiting = 0
_hits = collections.defaultdict(list)
# NAT64 (64:ff9b::/96) is a globally routable IPv6 prefix that embeds an IPv4 address, so is_global
# answers yes on 64:ff9b::7f00:1, which is 127.0.0.1 wrapped. A resolver can hand that back, so the
# embedded v4 has to be judged on its own.
_NAT64 = ipaddress.ip_network('64:ff9b::/96')


def _off_public(ip):
    """True when a resolved address must not be fetched. `is_global` catches private, loopback,
    link-local, carrier-NAT and reserved ranges in one test; NAT64 is the exception it cannot see."""
    if not ip.is_global:
        return True
    if ip.version == 6 and ip in _NAT64:
        return not ipaddress.IPv4Address(int(ip) & 0xffffffff).is_global
    return False


class AuditRequest(BaseModel):
    url: str
    deep: bool = False


def public_http_url(raw):
    """Return a normalized URL, or raise. Everything about the address is checked before a browser
    is started, because starting one is the expensive and dangerous part.

    The shape of the address is decided by `langaccess.address.auditable_url`, which the command
    line uses too, so that the two front doors of this package cannot disagree about what an
    address is. What stays here is the half that is this endpoint's own problem: a name that
    resolves inside a private network is a way to read that network from outside it, and the
    command line, which audits a list its own operator wrote, has `--block-private-hosts` for the
    runs where that matters.
    """
    if not (raw or '').strip():
        raise HTTPException(400, 'Enter a web address.')
    try:
        u = auditable_url(raw, ports=(80, 443))
    except AddressRejected as e:
        raise HTTPException(400, 'That is not an address that can be checked: %s.' % e.reason)
    host = urlsplit(u).hostname
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        raise HTTPException(400, f'No such host: {host}')
    for info in infos:
        # A scope goes on the end of an IPv6 address (fe80::1%eth0) and is not part of the address.
        # Handing it to ip_address raised ValueError, which reached the client as HTTP 500.
        ip = ipaddress.ip_address(info[4][0].split('%')[0])
        # is_global rather than a list of flags: the list missed the shared range 100.64.0.0/10 that
        # carrier NAT uses and several reserved blocks, and a list has to be kept up to date by hand.
        # `_off_public` adds the one thing is_global cannot see, a private IPv4 wrapped in NAT64.
        if _off_public(ip):
            raise HTTPException(400, 'That address resolves inside a private network.')
    return u


def trust_xff():
    """Whether X-Forwarded-For names the caller. Read per call, not at import, so the setting can
    be changed without rebuilding, and so a test does not have to fight the import cache."""
    return os.environ.get('LANGACCESS_TRUST_XFF', '1') != '0'


def within_budget(request: Request):
    # The RIGHTMOST hop when the header is trusted, not the leftmost. A chain reads
    # `client, proxy1, ...` where each proxy appends the address it received from, so the value your
    # own trusted edge appended is the last one; everything to its left is written by the caller and
    # is exactly what an attacker spoofs to spend another address's budget.
    forwarded = request.headers.get('x-forwarded-for', '') if trust_xff() else ''
    ip = (forwarded.split(',')[-1].strip()
          or (request.client.host if request.client else 'unknown'))
    now = time.time()
    # Drop the addresses whose last check has aged out. Without this the dictionary keeps one entry
    # per address that ever called, for as long as the process runs.
    for old in [k for k, v in _hits.items() if not v or now - v[-1] >= 3600]:
        del _hits[old]
    # A backstop for an attacker rotating addresses fast enough to grow the table inside the hour the
    # cleanup above works on. Drop the least-recently-seen down to the ceiling.
    if len(_hits) > MAX_HITS:
        for old in sorted(_hits, key=lambda k: _hits[k][-1])[:len(_hits) - MAX_HITS]:
            del _hits[old]
    recent = [t for t in _hits[ip] if now - t < 3600]
    if len(recent) >= PER_IP_PER_HOUR:
        raise HTTPException(429, f'That is {PER_IP_PER_HOUR} checks in an hour from this address. '
                                 'Each one drives a real browser, so the limit is low on purpose. '
                                 'Install the package if you need to run many.')
    recent.append(now)
    _hits[ip] = recent


@app.post('/api/audit')
async def api_audit(body: AuditRequest, request: Request):
    # the budget first: public_http_url resolves the host, and an endpoint that will do a DNS
    # lookup for anyone who asks, before any limit applies, is a way to drive DNS work for free
    within_budget(request)
    url = public_http_url(body.url)
    # A browser cap alone still lets callers pile up WAITING for one, each holding a connection. Past
    # MAX_WAITING in flight, say so rather than accepting work that cannot be reached; the count
    # spans both the ones running and the ones queued behind them.
    global _waiting
    if _waiting >= MAX_WAITING:
        raise HTTPException(503, 'The checker is busy right now. Try again in a moment, or install '
                                 'the package to run it locally.')
    _waiting += 1
    try:
        async with _browsers:
            try:
                r = await audit_async(url, deep=body.deep, timeout=AUDIT_TIMEOUT,
                                      block_private_hosts=True)
            # A site that could not be read is a Result and not a hand-written dict. Building the
            # shape here by hand meant that every field added to Result was missing from exactly the
            # two answers a client is least able to guess the shape of.
            except asyncio.TimeoutError:
                return JSONResponse(Result(
                    url=url, requested_url=url,
                    note=f'gave up after {int(AUDIT_TIMEOUT)} seconds').to_dict())
            except Exception as e:
                return JSONResponse(
                    Result(url=url, requested_url=url, note=type(e).__name__).to_dict())
        return JSONResponse(r.to_dict())
    finally:
        _waiting -= 1


@app.get('/config.js')
async def config_js():
    # The same page is served here and, as static files, from the documentation site. This file is
    # what tells it which it is: served by the app, a live check exists.
    return Response("window.LANGACCESS_API_BASE='';window.LANGACCESS_LIVE=true;",
                    media_type='application/javascript')


@app.get('/healthz')
async def healthz():
    return {'ok': True}


@app.get('/')
async def index():
    return FileResponse(os.path.join(HERE, 'static', 'index.html'))


_api = os.path.join(HERE, 'static', 'api-reference')
if os.path.isdir(_api):        # built by pdoc; absent in a bare checkout
    app.mount('/api-reference', StaticFiles(directory=_api, html=True), name='api-reference')
app.mount('/', StaticFiles(directory=os.path.join(HERE, 'static'), html=True), name='static')
