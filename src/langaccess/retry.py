# -*- coding: utf-8 -*-
"""Re-read the sites a clean browser could not reach, through the browser the user already trusts.

`unreachable` is the instrument's weakest outcome on every scoring ever run, and the cause is
mostly the door and not the site: a bot wall that challenges a fresh headless Chromium seldom
challenges the browser a person actually uses, with its own profile, its own history and its own
network. Playwright can attach to that browser over the DevTools protocol, so the retry borrows
it instead of imitating it.

    # start a SEPARATE Chrome profile once, with debugging on:
    #   Windows  chrome.exe --user-data-dir=%TEMP%\\la-retry --remote-debugging-port=9222
    #   macOS    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \\
    #                --user-data-dir=/tmp/la-retry --remote-debugging-port=9222
    #   Linux    google-chrome --user-data-dir=/tmp/la-retry --remote-debugging-port=9222
    langaccess retry run.jsonl --your-browser -o retried.jsonl

A SEPARATE PROFILE, AND WHY THE INSTRUCTION SAYS SO. A debugging port on your everyday profile
lets any local process, and any page able to reach 127.0.0.1, read the cookies and sessions of
every site you are signed in to, for as long as the window is open. `--user-data-dir` gives the
retry a profile of its own: it still carries a real browser's fingerprint and none of your
logins. Nothing here can enforce that, so it is said in every
place the command is written.

Only the records a person would have to open anyway are retried, the ones `review.needs_human`
already queues as unread. Everything else in the run is carried through byte-identical, and every
retried record says how it was read: `read_with_user_browser` is stamped true, because a reading
taken with a person's own fingerprint is a different observation from the clean-room one and a
study must be able to separate the two. The clean reading it replaces is kept beside it under
`clean_room_verdict`, so nothing is overwritten silently.

WHAT THIS MODULE REFUSES TO DO WITH A RUN FILE. The addresses come out of a file, and a file
arrives from a collaborator, a shared drive or an earlier run nobody has read since. Pointed at
the user's own browser, on the user's own network, an address is an instruction: `http://
169.254.169.254/…` is a cloud metadata service, `http://192.168.1.1/admin` is a router, and
`--keep-pages` would write whatever came back into the output. So the retry admits `http` and
`https` on the default ports and nothing else, refuses a private or loopback host by handing
`block_private_hosts` to every read, and counts what it refused in its own report rather than
passing over it in silence. The clean-room audit makes that guard optional because a study may
deliberately audit an intranet; borrowing somebody's browser is not that case.
"""
import asyncio
import ipaddress
import json
import gzip
import os
from urllib.parse import urlsplit

from .core import _audit_async, read_store
from .files import replace_atomically
from .review import unsettled_kind, UNREAD

DEFAULT_CDP = 'http://localhost:9222'
DEFAULT_TIMEOUT = 120
ALLOWED_SCHEMES = ('http', 'https')
ALLOWED_PORTS = (None, 80, 443)

START_CHROME = (
    'Start a separate Chrome profile with debugging on and leave it open:\n'
    '    Windows  chrome.exe --user-data-dir=%TEMP%\\la-retry --remote-debugging-port=9222\n'
    '    macOS    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" '
    '--user-data-dir=/tmp/la-retry --remote-debugging-port=9222\n'
    '    Linux    google-chrome --user-data-dir=/tmp/la-retry --remote-debugging-port=9222\n'
    'A separate profile carries a real browser\'s fingerprint and none of your logins.')


class BrowserNotAttached(RuntimeError):
    """No browser is listening where the retry was told to attach.

    Its own class so the command line can answer with the exit code it reserves for a machine that
    cannot run a browser, rather than a traceback on the code reserved for a crash.
    """


def refused(url):
    """Why this address is not one the retry will point a person's browser at, or ''.

    Read before anything is opened. Loopback and private addresses are refused by literal too, so
    a run file naming `http://127.0.0.1:9222/json/new` is stopped here and not only by the host
    guard inside the audit.
    """
    if not url:
        return 'no address on the record'
    p = urlsplit(url if '://' in url else 'https://' + url)
    if p.scheme not in ALLOWED_SCHEMES:
        return 'scheme %r is not http or https' % p.scheme
    try:
        if p.port not in ALLOWED_PORTS:
            return 'port %s is not 80 or 443' % p.port
    except ValueError:
        return 'the address does not carry a readable port'
    host = (p.hostname or '').strip('[]')
    if not host:
        return 'the address names no host'
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return ''            # a name, resolved and guarded inside the audit
    # `not ip.is_global` is the same test the web front door uses in `public_http_url`, so the two
    # agree on what "private" means; the explicit flags stay for the message and because is_global
    # alone does not name which one it was. It also catches the shared and reserved ranges a flag
    # list misses, carrier NAT (100.64.0.0/10) among them.
    if (ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved
            or not ip.is_global):
        return 'the address is a private or loopback host'
    return ''


async def _attach(pw, cdp):
    """The user's running browser, or the sentence that says how to start one."""
    try:
        return await pw.chromium.connect_over_cdp(cdp)
    except Exception as e:
        raise BrowserNotAttached(
            'no browser is listening at %s.\n%s\n(%s: %s)'
            % (cdp, START_CHROME, type(e).__name__, str(e)[:120])) from e


async def retry_unreachable_async(run, cdp=DEFAULT_CDP, browser=None, timeout=DEFAULT_TIMEOUT,
                                  keep_pages=False, output=''):
    """Retry every unread record of `run` through the attached browser.

    Returns (records, report): the full run with retried records replaced in place, and the
    counts. `browser` is injectable so a test can hand in a fake; when it is None the DevTools
    attach happens here and is DETACHED at the end. The attached browser is never closed, because
    it is the user's own: `pw.stop()` disconnects, and `_audit_async` closes every context it
    opened in its own `finally`.

    `timeout` bounds each site, and it is the whole reason the parameter exists: without a
    deadline every clock guard inside the audit is inert, and one page with a long switcher can
    hold a borrowed browser for the better part of an hour. A site that exceeds it is left as the
    unreachable reading it already was, with the timeout in its note.

    `output`, when given, is appended to as each retried record lands, so a run interrupted after
    an hour of browser reads keeps what it read. The caller still writes the whole file at the
    end; the appended file is the crash copy, and it is named `<output>.part`.
    """
    records = list(read_store(run)) if isinstance(run, (str, bytes)) else [
        dict(r) for r in run]
    targets = [i for i, r in enumerate(records) if unsettled_kind(r) == UNREAD]
    report = {'records': len(records), 'unread': len(targets), 'retried': 0,
              'now_read': 0, 'still_unreachable': 0, 'timed_out': 0,
              'refused': [], 'moved': []}
    if not targets:
        return records, report

    part = (output + '.part') if output else ''
    # the crash copy starts EMPTY on every retry: it is removed by a finished write_retry,
    # so one surviving a kill would otherwise take this run's appends on top of the last
    # run's and hold two rows for one record
    if part and os.path.exists(part):
        os.remove(part)
    own_attach = browser is None
    pw = None
    if own_attach:
        from playwright.async_api import async_playwright
        pw = await async_playwright().start()
        browser = await _attach(pw, cdp)
    try:
        for i in targets:
            old = records[i]
            url = old.get('url') or old.get('requested_url') or ''
            why = refused(url)
            if why:
                report['refused'].append((url, why))
                continue
            try:
                r = await asyncio.wait_for(
                    _audit_async(url, browser=browser, keep_pages=keep_pages,
                                 block_private_hosts=True), timeout)
            except asyncio.TimeoutError:
                report['timed_out'] += 1
                report['retried'] += 1
                report['still_unreachable'] += 1
                continue
            d = r.to_dict(with_pages=keep_pages)
            d['read_with_user_browser'] = True
            d['clean_room_verdict'] = old.get('verdict', '')
            for k in ('site_id',):
                if old.get(k):
                    d[k] = old[k]
            records[i] = d
            report['retried'] += 1
            if d['verdict'] != 'unreachable':
                report['now_read'] += 1
                report['moved'].append((url, d['verdict']))
            else:
                report['still_unreachable'] += 1
            if part:
                with open(part, 'a', encoding='utf-8') as fh:
                    fh.write(json.dumps(d, ensure_ascii=False) + '\n')
                    fh.flush()
    finally:
        if own_attach:
            await pw.stop()
    return records, report


def retry_text(report, output=''):
    """The retry as lines a person reads."""
    out = ['langaccess retry']
    add = out.append
    add('  %d records read; %d were unreachable in a clean browser' %
        (report['records'], report['unread']))
    add('  retried through your browser   %d' % report['retried'])
    add('    now read                     %d' % report['now_read'])
    add('    still unreachable            %d' % report['still_unreachable'])
    if report.get('timed_out'):
        add('      of those, timed out         %d' % report['timed_out'])
    for url, verdict in report['moved']:
        add('      %s -> %s' % (url, verdict))
    if report.get('refused'):
        add('  refused, never opened   %d' % len(report['refused']))
        for url, why in report['refused']:
            add('      %s   (%s)' % (url or '(no address)', why))
    if report['now_read']:
        add('  each retried record carries read_with_user_browser and keeps the clean-room '
            'verdict beside the new one')
    if output:
        add('  written to %s' % output)
    return '\n'.join(out)


def write_retry(records, path):
    """The run with the retried records in place, written whole and moved into place.

    Written to a temporary beside the destination and renamed, so an interrupted write cannot
    leave a half file at the path a later stage will read as a run. The rename waits out a
    destination another process is holding open, and raises `ReplaceBlocked` naming the finished
    file when it cannot be made; see `files.replace_atomically`.
    """
    tmp = path + '.tmp'
    opener = (lambda: gzip.open(tmp, 'wt', encoding='utf-8')) if str(path).endswith('.gz') \
        else (lambda: open(tmp, 'w', encoding='utf-8'))
    with opener() as fh:
        for r in records:
            fh.write(json.dumps(r, ensure_ascii=False) + '\n')
        fh.flush()
        os.fsync(fh.fileno())
    replace_atomically(tmp, path)
    part = path + '.part'
    if os.path.exists(part):
        os.remove(part)      # the crash copy did its job and is not left to confuse a later read
    return len(records)
