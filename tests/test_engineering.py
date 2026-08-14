# -*- coding: utf-8 -*-
"""Tests for the parts of the package that are not the detector.

The detector's own known-answer cases live in tests/test_core.py and are not touched here. What
this file guards is everything around them: that the frozen constants are still the frozen
constants, that a result can be written to JSON, and that the blocking entry point works inside a
notebook, where an event loop is already running.
"""
import ast
import asyncio
import dataclasses
import hashlib
import inspect
import io
import json
import os
import re
import subprocess
import sys

import pytest

from langaccess import core as LA

# Where a subprocess has to look to import the same two modules this one imported.
_TESTS = os.path.dirname(os.path.abspath(__file__))
_SRC_PATH = os.path.join(os.path.dirname(_TESTS), 'src')


# The freeze gate, derived. Until 2026-08-02 the fingerprint below was a hand-written list of
# `repr(LA.X)` lines, one per constant somebody had remembered to add, and a constant reached the
# code by simply not being on it. On 2026-08-01 that happened four times in one day and every one
# was found after the reading had already moved: ROBOTS_MAX_BYTES, which decides how much of a
# robots.txt is obeyed and therefore which pages a crawl may read; OPEN_CLICK_MS and OPEN_SETTLE_MS,
# which decide whether a collapsed switcher opens in time and therefore whether `language_control`
# evidence exists at all; and SCRIPTS with CYRILLIC, AUX_SCRIPT, AUX_SCRIPT_RX, KANA and
# CJK_CALENDAR, which is the package's primary non-Latin detector and was never in the gate, so a
# twelfth script could have been added with the hash sitting still.
#
# A longer list is not the fix for a list that gets forgotten. The fingerprint is now taken over
# every name `core.py` assigns at module level, read off the module's own source, so a constant is
# covered the moment it is written and adding one MOVES THE HASH BY ITSELF. Leaving one out is still
# allowed and is now an act somebody has to perform: a name in `_FINGERPRINT_EXCLUDE` with a reason
# beside it, checked by `test_every_constant_is_accounted_for` and visible in the diff of any commit
# that adds it.
#
# The per-constant notes that used to sit inside this function are gone with the list they annotated.
# They answered "why is this one in", which is not a question the gate asks any more, because in is
# the default. What still needs answering is why one is OUT, and the ledger below holds those answers.
def _module_constants():
    """Every name `core.py` assigns at module level, and its current value.

    Read off the module's own source rather than off `vars()`, because `vars()` cannot tell a
    constant this module defines from a name it imported: `re`, `json` and `asyncio` are in there
    too, and so is everything `from x import *` would drag in if anyone ever wrote one. The parse
    walks into `if` and `try` at module level, which is where a platform-dependent constant would
    be, and does not walk into a function or a class, so a local named PARA_WINDOW inside some
    helper cannot enter the gate and a class attribute cannot either.

    Assignment is the test, not spelling. A constant added in lower case, or added without a comment
    explaining itself, is still covered; nothing here depends on anybody following a convention.
    """
    tree = ast.parse(inspect.getsource(LA))
    names = []

    def targets(node):
        if isinstance(node, ast.Name):
            names.append(node.id)
        elif isinstance(node, (ast.Tuple, ast.List)):
            for e in node.elts:
                targets(e)
        elif isinstance(node, ast.Starred):
            targets(node.value)

    def walk(body):
        for n in body:
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue
            if isinstance(n, ast.Assign):
                for t in n.targets:
                    targets(t)
            elif isinstance(n, (ast.AnnAssign, ast.AugAssign)):
                targets(n.target)
            for field in ('body', 'orelse', 'finalbody'):
                sub = getattr(n, field, None)
                if isinstance(sub, list):
                    walk(sub)
            for handler in getattr(n, 'handlers', []):
                walk(handler.body)

    walk(tree.body)
    return {n: getattr(LA, n) for n in sorted(set(names)) if hasattr(LA, n)}


# The constants the fingerprint deliberately does not hold, and why for each one. Two kinds are
# here and only two. The first kind CANNOT be hashed to a stable value: a cache that an audit fills,
# a flag a warning flips, an object whose repr carries its address, a set of error numbers the
# operating system chooses. Hashing any of those makes the gate fail on the order the tests ran in
# or on which machine ran them, and a gate that cries wolf is a gate people re-record without
# reading. The second kind is the four run-scheduling constants, whose reasoning is in the ledger
# below.
#
# Nothing else belongs here. If a constant is arguably incidental, cover it: the cost of covering
# one that turns out not to matter is one line of comment in the commit that changes it, and the
# cost of leaving out one that does matter is a run of readings nobody can compare with anything.
_FINGERPRINT_EXCLUDE = {
    '_ROBOTS_CACHE': (
        'A cache an audit fills and `clear_robots_cache` empties. Its contents are whichever hosts '
        'this process happened to fetch, so hashing it makes the gate depend on test order.'),
    'RUN_RX_CACHE': (
        'A memo of compiled script-run patterns, filled on first use. The patterns it holds are '
        'derived from SCRIPT_SEP and the SCRIPTS ranges, both of which ARE covered, so nothing '
        'about a reading escapes by leaving the memo out.'),
    '_FT_WARNED': (
        'A flag set once, the first time the language identifier is asked for and cannot load. It '
        'records what has happened in this process and decides nothing about a page.'),
    '_FT_MODEL': (
        'The loaded lid.176 model, a process-lifetime memo whose repr carries an object address. '
        'What decides readings is the model FILE, whose bytes ship in the package and whose '
        'sha256 the reading freeze exercises through every auxiliary fixture; and FT_MIN_CONF, '
        'which IS covered.'),
    '_BATCH_ROBOTS': (
        'A ContextVar. Its repr carries the object address, so it is a different string in every '
        'process; the value it carries is _ROBOTS_CACHE, excluded above.'),
    '_DNS_NO_SUCH_HOST': (
        'The resolver error numbers that mean a name is not registered, collected with getattr '
        'because the set differs between platforms. Windows and Linux would hash differently and '
        'the gate would fail on whichever machine did not record it.'),
    'AUDIT_BATCH': (
        'Batching and watchdog, with DEAD_SECONDS, DEAD_STREAK and AUDIT_MAX_ATTEMPTS below. They '
        'decide nothing about a site the run reads; they decide what a run does once its browser '
        'driver is dead, which used to be that it recorded a fifth of the frame as sites that '
        'answered nothing.'),
    'DEAD_SECONDS': (
        'How long a site may take before the run treats its browser driver as dead. Watchdog, with '
        'AUDIT_BATCH above, and excluded for the reason written there.'),
    'DEAD_STREAK': (
        'How many dead sites in a row end the batch. Watchdog, with AUDIT_BATCH above, and excluded '
        'for the reason written there.'),
    'AUDIT_MAX_ATTEMPTS': (
        'How many times a site is handed back to a fresh driver. Watchdog, with AUDIT_BATCH above, '
        'and excluded for the reason written there.'),
}


# A pattern that is one flat alternation and nothing else: an optional literal prefix, `(?:a|b|c)`
# with no nested group and no character class inside it, and an optional literal suffix. Every word
# list this package compiles has that shape, and it is the only shape `_canonical` reorders.
_FLAT_ALTERNATION = re.compile(r'^([^()\[\]]*)\(\?:([^()\[\]]+)\)([^()\[\]]*)$')


def _canonical_pattern(rx):
    """A compiled pattern as a string that is the same in every process.

    Faithful text, with one exception that has to be here. SCRIPT_FUNC_RX compiles each particle
    list with `sorted(set(...), key=len, reverse=True)`, and `set` iterates in an order that depends
    on the interpreter's hash seed, so two words of the SAME length come out in a different order in
    every process. The pattern text is therefore not stable across runs even though the pattern is
    the same pattern, and a gate hashing it fails at random on a machine that did not record it.

    A flat alternation of literals is reordered into a canonical order and its ORIGINAL sequence of
    alternative lengths is kept beside it. That pair is exact rather than merely stable. Two orders
    that differ only within a group of equal-length alternatives produce the same string, and they
    are interchangeable: alternation is first-match-wins, and two alternatives of the same length
    that both match at one position are the same string. Any reordering that crosses lengths, which
    is the reordering that can change which alternative wins under `(?:...)` with no word boundary,
    changes the length sequence and so changes the string.

    Everything else keeps its literal text. `repr` on a pattern is not usable at all here: it
    truncates past 200 characters, which would leave the gate blind to the tail of MT_RX and
    WALL_RX, the two longest patterns in the package.

    The pattern text is rendered with `%a` and not `%r`, for the reason written on `_canonical`:
    every character range in this package is non-Latin, and `repr` renders a non-Latin character
    differently on two interpreters carrying different Unicode data.
    """
    m = _FLAT_ALTERNATION.match(rx.pattern)
    if m:
        alts = m.group(2).split('|')
        if len(alts) > 1:
            return 'regex_alt(%a, %a, %a, %a, flags=%d)' % (
                m.group(1), sorted(alts), [len(a) for a in alts], m.group(3), rx.flags)
    return 'regex(%a, flags=%d)' % (rx.pattern, rx.flags)


def _canonical(value):
    """One string for a constant's value, the same string on every machine and every run.

    `repr` alone will not do it, for two reasons. A set and a dict iterate in an order that depends
    on the hash seed, so `repr(SCRIPT_FUNC_SPACED)` is a different string in two processes and the
    gate would fail at random; both are sorted here. Patterns go through `_canonical_pattern` for
    that reason and one more. A list and a tuple keep their order, because the order of SCRIPTS and
    AUTHORSHIP_ORDER is itself a decision.

    The second reason is the interpreter's Unicode data, and it is why the fallback is `ascii` and
    not `repr`. `repr` of a string escapes a character it considers unprintable and emits one it
    considers printable as itself, and printability is read off the Unicode database compiled into
    that interpreter. U+9FFF, the top of the CJK ideograph range SCRIPTS uses for Chinese and for
    Japanese, is unassigned in Unicode 13, which Python 3.10 carries, and assigned in Unicode 15.1,
    which Python 3.13 carries. The same SCRIPTS therefore came out with that character escaped on
    3.10 and written as itself on 3.13, and the gate failed on the one version that did not agree
    with the machine the hash was recorded on. `ascii` escapes every non-ASCII character whatever
    the database says about it, so the listing is one listing on every interpreter. Version
    independence is part of what this gate promises.
    """
    if isinstance(value, re.Pattern):
        return _canonical_pattern(value)
    if isinstance(value, (set, frozenset)):
        return '{%s}' % ', '.join(sorted(_canonical(v) for v in value))
    if isinstance(value, dict):
        return '{%s}' % ', '.join(sorted('%s: %s' % (_canonical(k), _canonical(v))
                                         for k, v in value.items()))
    if isinstance(value, (list, tuple)):
        return '[%s]' % ', '.join(_canonical(v) for v in value)
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return '%s(%s)' % (type(value).__name__,
                           ', '.join('%s=%s' % (f.name, _canonical(getattr(value, f.name)))
                                     for f in dataclasses.fields(value)))
    return ascii(value)


def _freeze_lines():
    """`NAME = value` for every covered constant, sorted, plus the roll of what was left out.

    The exclusion names are in the hash so that moving a constant out of the gate moves the hash
    too. Without that, adding a constant and excluding it in the same commit would cancel out and
    leave the gate exactly where it was, which is the shape of the failure this whole change is
    about. The reasons are held out of the hash so that a person can improve the wording of one
    without re-recording anything, and they are held to a length by a test instead.
    """
    out = ['%s = %s' % (n, _canonical(v)) for n, v in sorted(_module_constants().items())
           if n not in _FINGERPRINT_EXCLUDE]
    out.append('not covered: ' + ', '.join(sorted(_FINGERPRINT_EXCLUDE)))
    return out


def _freeze_fingerprint():
    """A single string standing for every constant the instrument's readings depend on."""
    return hashlib.sha256('\n'.join(_freeze_lines()).encode('utf-8')).hexdigest()


def test_every_constant_is_accounted_for():
    """No constant is in `core.py` and outside the gate without somebody having said so.

    A hand list could not have this test. A name added to `core.py` is covered the moment
    it is written, and the only way out is the ledger above, which means the omission is in the diff
    of the commit that makes it instead of being the absence of a line nobody was looking for.
    """
    names = set(_module_constants())
    stale = sorted(set(_FINGERPRINT_EXCLUDE) - names)
    assert stale == [], (
        'the exclusion ledger names constants that are no longer in core.py: %s. Remove them, or '
        'the ledger becomes the same kind of stale list the gate was built to replace.' % stale)
    thin = sorted(n for n, why in _FINGERPRINT_EXCLUDE.items() if len(why.strip()) < 20)
    assert thin == [], 'these exclusions carry no reason worth reading: %s' % thin


def test_the_rule_registry_names_nothing_the_gate_leaves_out():
    """A constant the registry says enforces a rule cannot be excluded from the gate.

    `RULES` already declares, per numbered rule, which objects in the module apply it. Seven of the
    constants it names were outside the hand list on the day this was written (ARCHIVE_PATH for rule
    18, SOCIAL_HOST for rule 1, LOCALE_ROOT for rule 17, LOCALE_ROUTE for rule 6, FUNC_RX and
    FUNC_ONLY_RX for rules 9 and 6, SCRIPT_FUNC_RX for rule 7), so the package's own registry could
    have named most of the gaps the hand list had. It cannot go the other way again.
    """
    names = set(_module_constants())
    declared = {n for r in LA.RULES.values() for n in r.enforced_in} & names
    assert declared, 'the registry named no constants at all, which means it stopped resolving'
    out = sorted(declared & set(_FINGERPRINT_EXCLUDE))
    assert out == [], 'the registry says these enforce a rule and the gate does not hold them: %s' % out


# Every word list, path list and threshold in the fingerprint is part of the instrument, so a
# reading taken after one of them changes cannot be compared with a reading taken before it. This
# test failing means a frozen constant moved. The fix is to put it back, or, if the change is
# wanted, to record a new fingerprint here in the same commit that says in LIMITATIONS.md which
# figure no longer applies.
#
# THE MAP, development -> release, which is what a record written before 2026-08-09 resolves
# through (5 and 12 of the development numbering were retired 2026-08-08 and have no release
# number; the release numbering has no gaps):
#     11->1   13->2   1->3   2->4   9->5   3->6   7->7   14->8   17->9   16->10
#      8->11  10->12  18->13  4->14  6->15 (an advertised locale route in English)
#                                    6->16 (a worked control without effect)  15->17
#
# THREE PROPOSALS WERE MEASURED AND REFUSED, recorded so they are not made again: an English guard
# on counted_evidence moves real language lists, rule 11's gate-ran reporting is the semantics rule
# 13 already has, and a recorded sufficiency of zero cannot be told from the dataclass default.
FREEZE = '8c385efdf73136b14d659dfd581d058f01b86d754c2984ccb13954cc9cfcb51f'


def test_the_frozen_constants_have_not_moved():
    """The gate. `LANGACCESS_FREEZE_DUMP=<path>` writes the canonical listing this hash was taken
    over, so two revisions can be diffed line by line to see which constant moved."""
    dump = os.environ.get('LANGACCESS_FREEZE_DUMP')
    if dump:
        with io.open(dump, 'w', encoding='utf-8') as fh:
            fh.write('\n'.join(_freeze_lines()))
    assert _freeze_fingerprint() == FREEZE, (
        'a constant this instrument reads has moved, or one has been added or removed. %d '
        'constants are covered and %d are excluded by name. Re-run with LANGACCESS_FREEZE_DUMP set '
        'on this revision and on the last one to see which.'
        % (len(_module_constants()) - len(_FINGERPRINT_EXCLUDE), len(_FINGERPRINT_EXCLUDE)))


def test_the_fingerprint_is_the_same_in_another_process():
    """A gate that answers differently in two processes is worse than no gate.

    Python randomises string hashing per process, so any constant built by iterating a `set` has a
    process-dependent order, and a fingerprint that picked that order up would fail on whichever
    machine did not record it. SCRIPT_FUNC_RX is exactly that constant and it entered the gate on
    2026-08-02; this runs the fingerprint under two fixed hash seeds and requires all three answers,
    including this process's, to agree.
    """
    code = ('import sys; sys.path[:0] = %r\n'
            'import test_engineering as T; print(T._freeze_fingerprint())' % [_SRC_PATH, _TESTS])
    seen = {_freeze_fingerprint()}
    for seed in ('0', '1'):
        env = dict(os.environ, PYTHONHASHSEED=seed, PYTHONIOENCODING='utf-8', PYTHONUTF8='1')
        out = subprocess.run([sys.executable, '-c', code], capture_output=True, text=True, env=env)
        assert out.returncode == 0, out.stderr
        seen.add(out.stdout.strip())
    assert len(seen) == 1, 'the fingerprint depends on the hash seed: %s' % sorted(seen)


def test_the_fingerprint_does_not_depend_on_the_interpreter_version():
    """The sibling of the test above, for the other thing that made the listing not one listing.

    A gate that answers differently on two interpreters is worth as little as one that answers
    differently in two processes, and it fails in a nastier way: the matrix goes red on one cell
    only, on every push, and the value looks correct to whoever recorded it. It happened
    from 2026-08-02 to 2026-08-04, when `test (3.10)` alone failed because `repr` renders a string
    against the Unicode database compiled into the interpreter and U+9FFF changed from unassigned
    to assigned between Unicode 13 and 15.1.

    Running the fingerprint under a second interpreter is not something a test can do; there may not
    be one installed, and requiring one would make the suite depend on the machine. What is checked
    instead is the property that makes the version irrelevant, which is stronger than a spot check
    against whichever second version happens to be around: the listing carries no non-ASCII
    character at all, so there is nothing in it for a Unicode database to disagree about. Every
    escape below is chosen by rules that have not moved since Python 3.0.
    """
    offenders = [line.split(' = ')[0] for line in _freeze_lines() if not line.isascii()]
    assert offenders == [], (
        'these constants render with a non-ASCII character in the freeze listing: %s. `repr` prints '
        'a character as itself or escapes it according to the Unicode database built into the '
        'running interpreter, so a listing holding one is a different listing on two Python '
        'versions and this gate fails on whichever version did not record it. Render through '
        '`ascii`, or `%%a` for a pattern, as `_canonical` does.' % offenders)


def test_every_language_keeps_a_word_of_its_own():
    """A language with no word of its own is a language that stops being checked for one.

    languages_in only requires a unique word when FUNC_ONLY_RX has an entry for the language, and
    that entry is built by subtracting the words shared with another list. So a word added to two
    lists at once can empty one of them, and the effect is silent: the language starts matching on
    vocabulary it shares with its neighbour, which is what reported every Spanish page as
    Portuguese as well.
    """
    missing = sorted(set(LA.FUNC) - set(LA.FUNC_ONLY_RX))
    assert missing == [], f'no unique function words left for: {missing}'


def test_a_result_survives_json():
    """A quote is in the language that was found, so a JSON writer that assumes ASCII loses it."""
    r = LA.Result(url='https://x.org/', verdict='true_multilingual',
                  languages=['Korean', 'Khmer'],
                  evidence=[LA.Evidence('inline_text', 'https://x.org/', '무료 법률 상담을 제공합니다', 'Korean'),
                            LA.Evidence('translated_page', 'https://x.org/km',
                                        'មជ្ឈមណ្ឌលវប្បធម៌កម្ពុជាផ្តល់ថ្នាក់រៀនភាសាខ្មែរ', 'Khmer')],
                  audited_at='2026-07-29T12:00:00Z', tool_version='0.2.0')
    line = json.dumps(r.to_dict(), ensure_ascii=False)
    back = json.loads(line)
    assert back['audited_at'] == '2026-07-29T12:00:00Z'
    assert back['tool_version'] == '0.2.0'
    assert back['evidence'][0]['quote'] == '무료 법률 상담을 제공합니다'
    assert back['evidence'][1]['language'] == 'Khmer'
    assert 'pages' not in back


def test_a_reading_records_when_and_by_what_it_was_taken():
    for f in ('audited_at', 'tool_version'):
        assert f in LA.Result(url='https://x.org/').to_dict()


def test_audit_works_inside_a_running_event_loop():
    """A notebook has a loop running already, and asyncio.run refuses to start a second one in the
    same thread. The blocking form is the one a person writes in a cell, so it has to work there."""
    stub = LA.Result(url='https://x.org/', verdict='english_only', note='stub')

    async def fake_audit(url, max_pages=6, deep=False, keep_pages=False, block_private_hosts=False):
        return stub

    async def call_it_from_inside_a_loop():
        return LA.audit('https://x.org')

    real = LA._audit_async
    LA._audit_async = fake_audit
    try:
        got = asyncio.run(call_it_from_inside_a_loop())
    finally:
        LA._audit_async = real
    assert got is stub


def test_audit_with_no_loop_running_still_works():
    stub = LA.Result(url='https://x.org/', verdict='english_only', note='stub')

    async def fake_audit(url, max_pages=6, deep=False, keep_pages=False, block_private_hosts=False):
        return stub

    real = LA._audit_async
    LA._audit_async = fake_audit
    try:
        assert LA.audit('https://x.org') is stub
    finally:
        LA._audit_async = real


def test_the_private_host_test_reads_a_scoped_address():
    """fe80::1%eth0 is a link-local address with a scope on it, and the scope is not part of the
    address. Parsing it whole raised ValueError."""
    async def go():
        cache = {}
        return await LA._host_is_public('should-not-resolve.invalid', cache)
    assert asyncio.run(go()) is False


def test_blocking_private_hosts_is_off_by_default():
    """A research run has to read exactly what it read before, so the guard is opt-in."""
    import inspect
    for fn in (LA.audit, LA.audit_async):
        p = inspect.signature(fn).parameters
        assert p['block_private_hosts'].default is False
        assert p['block_private_hosts'].kind is inspect.Parameter.KEYWORD_ONLY


class _FakeResponse:
    def __init__(self, body, ok=True):
        self._body, self.ok = body, ok

    async def text(self):
        return self._body


class _FakeRequestClient:
    """Playwright's APIRequestContext, reduced to the one method _sitemap_pages uses."""

    def __init__(self, files):
        self.files, self.asked = files, []

    async def get(self, url, timeout=None):
        self.asked.append(url)
        body = self.files.get(url)
        return _FakeResponse('', ok=False) if body is None else _FakeResponse(body)


class _FakeContext:
    def __init__(self, files):
        self.request = _FakeRequestClient(files)


_SITEMAP_INDEX = ('<?xml version="1.0"?><sitemapindex>'
                  '<sitemap><loc>https://evil.example/inner.xml</loc></sitemap>'
                  '<sitemap><loc>https://good.example/inner.xml</loc></sitemap>'
                  '</sitemapindex>')
_SITEMAP_INNER = ('<?xml version="1.0"?><urlset>'
                  '<url><loc>https://good.example/servicios</loc></url>'
                  '</urlset>')
_SITEMAP_FILES = {'https://good.example/sitemap.xml': _SITEMAP_INDEX,
                  'https://good.example/inner.xml': _SITEMAP_INNER}


def test_a_nested_sitemap_on_somebody_elses_host_is_not_fetched():
    """The route handler the browser runs under does not see ctx.request.get, so a sitemap index
    pointing at http://169.254.169.254/ was a fetch the guard never tested. A nested sitemap gets
    the same same-site test every other address in the crawl gets."""
    ctx = _FakeContext(_SITEMAP_FILES)
    out = asyncio.run(LA._sitemap_pages(ctx, 'https://good.example/'))
    assert 'https://evil.example/inner.xml' not in ctx.request.asked
    assert 'https://good.example/inner.xml' in ctx.request.asked
    assert out == ['https://good.example/servicios']


def test_blocking_private_hosts_reaches_the_sitemap_fetches(monkeypatch):
    """With the guard on, no sitemap address is fetched before its host is resolved."""
    async def never_public(host, cache):
        return False

    monkeypatch.setattr(LA, '_host_is_public', never_public)
    ctx = _FakeContext(_SITEMAP_FILES)
    out = asyncio.run(LA._sitemap_pages(ctx, 'https://good.example/', block_private_hosts=True))
    assert ctx.request.asked == []
    assert out == []


def test_the_sitemap_guard_is_off_unless_it_is_asked_for():
    """Every research run reads sitemaps with no DNS lookup at all, as it did before."""
    import inspect
    p = inspect.signature(LA._sitemap_pages).parameters
    assert p['block_private_hosts'].default is False


class _FakeBrowser:
    def __init__(self):
        self.closed = False

    def is_connected(self):
        return not self.closed

    async def close(self):
        self.closed = True


class _FakePlaywright:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


def _no_real_browser(monkeypatch):
    """Stand in for Playwright and for the launch, so a batch test opens nothing."""
    launched = []

    async def fake_launch(pw):
        b = _FakeBrowser()
        launched.append(b)
        return b

    monkeypatch.setattr(LA, '_playwright', lambda: _FakePlaywright())
    monkeypatch.setattr(LA, '_launch', fake_launch)
    return launched


# -------------------------------------------------------- a machine that cannot start a browser
#
# `core._playwright` and `core._launch` are the two seams every audit passes through on its way to a
# browser, which is what lets this be tested without uninstalling anything. What they raise decides
# whether the command line can tell an infrastructure failure from a site that answered nothing, and
# an earlier revision raised a bare RuntimeError here, which is what every crashed page raises too.


class _NoBrowserPlaywright:
    """Playwright with the library present, the driver up, and no browser installed on the disk."""
    class _Chromium:
        async def launch(self, **kw):
            raise RuntimeError("Executable doesn't exist at ...\\chrome-headless-shell.exe")

    chromium = _Chromium()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


def test_a_machine_with_no_browser_names_itself_as_one(monkeypatch):
    """The message was already right and already reached the user. What it could not do was say
    that this is a property of the machine, so every caller treated it as a property of the site."""
    with pytest.raises(LA.BrowserUnavailable) as got:
        asyncio.run(LA._launch(_NoBrowserPlaywright()))
    assert 'python -m playwright install chromium' in str(got.value)
    assert isinstance(got.value, RuntimeError), (
        'a caller that already catches RuntimeError around an audit has to go on catching this')


def test_a_machine_without_playwright_at_all_says_the_same_kind_of_thing(monkeypatch):
    """The import is the other seam, and a machine that has never installed the library reaches it
    first. Same class, so one handler answers both."""
    import builtins
    real = builtins.__import__

    def fake(name, *a, **k):
        if name.startswith('playwright'):
            raise ImportError('No module named %r' % name)
        return real(name, *a, **k)

    monkeypatch.setattr(builtins, '__import__', fake)
    with pytest.raises(LA.BrowserUnavailable) as got:
        LA._playwright()
    assert 'pip install playwright' in str(got.value)


def test_the_missing_browser_leaves_the_audit_rather_than_becoming_a_reading(monkeypatch):
    """An audit that could not open a browser must not return a Result. `unreachable` is a reading
    of a site, and no site was opened."""
    async def boom(pw):
        raise LA.BrowserUnavailable('no browser')

    monkeypatch.setattr(LA, '_playwright', lambda: _NoBrowserPlaywright())
    monkeypatch.setattr(LA, '_launch', boom)
    with pytest.raises(LA.BrowserUnavailable):
        asyncio.run(LA._audit_async('https://x.example/'))


def test_the_batch_lets_the_missing_browser_out_before_it_reads_anything(monkeypatch):
    """`audit_many_async` launches once per batch, before the first address, so the failure arrives
    with nothing read and nothing to lose by raising."""
    async def boom(pw):
        raise LA.BrowserUnavailable('no browser')

    monkeypatch.setattr(LA, '_playwright', lambda: _NoBrowserPlaywright())
    monkeypatch.setattr(LA, '_launch', boom)
    with pytest.raises(LA.BrowserUnavailable):
        asyncio.run(LA.audit_many_async(['a.org', 'b.org']))


def test_the_package_exports_the_infrastructure_failure(monkeypatch):
    """A caller outside this package has to be able to name the thing it is meant to catch."""
    import langaccess
    assert langaccess.BrowserUnavailable is LA.BrowserUnavailable
    assert 'BrowserUnavailable' in langaccess.__all__


def test_a_batch_returns_its_results_in_the_order_the_urls_were_given(monkeypatch):
    """The audits finish in whatever order they finish in; the list does not depend on that."""
    naps = {'a.org': 0.06, 'b.org': 0.005, 'c.org': 0.03}

    async def stub(url, max_pages=6, deep=False, keep_pages=False, block_private_hosts=False,
                   browser=None):
        await asyncio.sleep(naps[url])
        return LA.Result(url=url, verdict='english_only')

    launched = _no_real_browser(monkeypatch)
    monkeypatch.setattr(LA, '_audit_async', stub)
    got = asyncio.run(LA.audit_many_async(list(naps), concurrency=3))
    assert [r.url for r in got] == ['a.org', 'b.org', 'c.org']
    assert len(launched) == 1, 'the point of the batch is one browser for the whole run'
    assert launched[0].closed is True


def test_one_site_that_raises_does_not_take_the_batch_with_it(monkeypatch):
    async def stub(url, max_pages=6, deep=False, keep_pages=False, block_private_hosts=False,
                   browser=None):
        if url == 'bad.org':
            raise RuntimeError('the browser went away')
        return LA.Result(url=url, verdict='english_only')

    _no_real_browser(monkeypatch)
    monkeypatch.setattr(LA, '_audit_async', stub)
    got = asyncio.run(LA.audit_many_async(['good.org', 'bad.org', 'also-good.org'], concurrency=2))
    assert [r.url for r in got] == ['good.org', 'bad.org', 'also-good.org']
    assert got[1].verdict == 'unreachable'
    assert 'RuntimeError' in got[1].note
    assert got[0].verdict == 'english_only' and got[2].verdict == 'english_only'


def test_a_site_gets_one_retry_on_a_fresh_browser(monkeypatch):
    """The browser is the one thing every site in a batch shares, so a site that fails once is
    tried again on a replacement before it is written off."""
    tries = []

    async def stub(url, max_pages=6, deep=False, keep_pages=False, block_private_hosts=False,
                   browser=None):
        tries.append(browser)
        if len(tries) == 1:
            raise RuntimeError('target closed')
        return LA.Result(url=url, verdict='english_only')

    launched = _no_real_browser(monkeypatch)
    monkeypatch.setattr(LA, '_audit_async', stub)
    got = asyncio.run(LA.audit_many_async(['x.org']))
    assert got[0].verdict == 'english_only'
    assert len(tries) == 2 and tries[0] is not tries[1]
    assert len(launched) == 2 and launched[0].closed is True


def test_a_batch_hands_every_site_the_shared_browser(monkeypatch):
    handed = []

    async def stub(url, max_pages=6, deep=False, keep_pages=False, block_private_hosts=False,
                   browser=None):
        handed.append(browser)
        return LA.Result(url=url, verdict='english_only')

    _no_real_browser(monkeypatch)
    monkeypatch.setattr(LA, '_audit_async', stub)
    asyncio.run(LA.audit_many_async(['a.org', 'b.org', 'c.org'], concurrency=1))
    assert len(set(map(id, handed))) == 1


# ------------------------------------------------- the batch boundary, and the driver that dies
#
# The failure these four cases are about destroyed a run's data and left a log saying every site had
# finished. A 992-site capture ran 7 hours 36 minutes, lost the pipe to the Playwright node driver
# somewhere around site 780, and returned the last fifth of the frame in under a second each with no
# page. The repair path in this function relaunched the BROWSER through the same dead connection, so
# it could never work, and nothing anywhere watched for the shape the collapse has.


def _counting_browser(monkeypatch):
    """Stand in for Playwright and for the launch, counting both.

    Two counts and not one, because the batch boundary opens a new DRIVER and
    not merely a new browser on the old one.
    """
    opened, launched = [], []

    class _PW:
        async def __aenter__(self):
            opened.append(self)
            return self

        async def __aexit__(self, *exc):
            return False

    async def fake_launch(pw):
        b = _FakeBrowser()
        launched.append(b)
        return b

    monkeypatch.setattr(LA, '_playwright', lambda: _PW())
    monkeypatch.setattr(LA, '_launch', fake_launch)
    return opened, launched


def test_the_list_is_read_in_batches_each_on_a_driver_of_its_own(monkeypatch):
    """A driver is never asked to outlive one batch, and the order still does not depend on it."""
    urls = [f's{n}.org' for n in range(7)]

    async def stub(url, max_pages=6, deep=False, keep_pages=False, block_private_hosts=False,
                   browser=None):
        return LA.Result(url=url, verdict='english_only', pages_read=1)

    opened, launched = _counting_browser(monkeypatch)
    monkeypatch.setattr(LA, '_audit_async', stub)
    monkeypatch.setattr(LA, 'AUDIT_BATCH', 3)
    got = asyncio.run(LA.audit_many_async(urls, concurrency=2))
    assert [r.url for r in got] == urls, 'results come back in the order given'
    assert len(opened) == 3 and len(launched) == 3, '7 sites in batches of 3 is three drivers'
    assert all(b.closed for b in launched)


def test_a_run_of_fast_empty_results_tears_the_batch_down_and_is_recorded_as_failure(
        monkeypatch, tmp_path):
    """The collapse, and what the run is allowed to say about the sites caught in it.

    Every site here answers instantly with no page, which is what a dead driver produces and what no
    real read looks like. The watchdog has to see it, take the driver down, and then, once the sites
    have been offered every driver they are going to get, record them as FAILURES. Recording them as
    readings is precisely what cost the 992-site run its last fifth.
    """
    urls = [f's{n}.org' for n in range(20)]

    async def stub(url, max_pages=6, deep=False, keep_pages=False, block_private_hosts=False,
                   browser=None):
        return LA.Result(url=url, verdict='unreachable')          # no page, and instantly

    opened, launched = _counting_browser(monkeypatch)
    monkeypatch.setattr(LA, '_audit_async', stub)
    store = tmp_path / 'store.jsonl'
    got = asyncio.run(LA.audit_many_async(urls, concurrency=4, store=str(store)))

    assert [r.url for r in got] == urls
    assert len(opened) == LA.AUDIT_MAX_ATTEMPTS, (
        'the batch was torn down and a FRESH DRIVER opened, which is the repair the old code could '
        'not make; and the run stopped after three drivers that read nothing rather than going on')
    assert all(b.closed for b in launched), 'a torn batch closes its browser on the way out'
    # the finding: not one of these is recorded as a site that answered nothing
    assert all(r.note for r in got), 'every site caught in the collapse carries what happened to it'
    assert all(r.pages_read == 0 and r.verdict == 'unreachable' for r in got)
    lines = [json.loads(x) for x in store.read_text(encoding='utf-8').splitlines() if x.strip()]
    assert len(lines) == len(urls), 'one store line per attempted site, failures included'
    assert {d['url'] for d in lines} == set(urls)
    assert all(d['note'] for d in lines)


def test_the_watchdog_does_not_fire_on_a_site_that_is_merely_empty(monkeypatch):
    """A site can answer nothing honestly, and a run of them shorter than the streak is not a
    collapse. Nothing here may be turned into a failure, and no driver may be replaced."""
    urls = [f's{n}.org' for n in range(LA.DEAD_STREAK - 1)]

    async def stub(url, max_pages=6, deep=False, keep_pages=False, block_private_hosts=False,
                   browser=None):
        return LA.Result(url=url, verdict='english_only', note='')

    opened, launched = _counting_browser(monkeypatch)
    monkeypatch.setattr(LA, '_audit_async', stub)
    got = asyncio.run(LA.audit_many_async(urls, concurrency=2))
    assert [r.url for r in got] == urls
    assert len(opened) == 1 and len(launched) == 1
    assert all(r.verdict == 'english_only' and not r.note for r in got), (
        'held, then believed when the batch finished: these are readings, not failures')


def test_a_run_of_pre_crawl_stops_does_not_tear_the_batch_down(monkeypatch):
    """A social profile, a directory listing and a parked domain are decided in milliseconds with no
    page read, which is the shape a dead driver produces. A census input sorted by address clusters
    them, so a run longer than the streak must NOT replace the driver or turn these real decisions
    into failures."""
    urls = [f's{n}.org' for n in range(LA.DEAD_STREAK + 4)]

    async def stub(url, max_pages=6, deep=False, keep_pages=False, block_private_hosts=False,
                   browser=None):
        return LA.Result(url=url, verdict='english_only', rules=[1],
                         note="a social media page, not the organization's own website")

    opened, launched = _counting_browser(monkeypatch)
    monkeypatch.setattr(LA, '_audit_async', stub)
    got = asyncio.run(LA.audit_many_async(urls, concurrency=2))
    assert [r.url for r in got] == urls
    assert len(opened) == 1 and len(launched) == 1, 'the driver was replaced on deliberate stops'
    assert all(r.rules == [1] and r.pages_read == 0 for r in got), (
        'settled as the pre-crawl decisions they are, not written off as a collapse')


def test_retain_false_frees_results_but_still_streams_and_warns(monkeypatch):
    """A very large run holds one Result per site for its whole length; retain=False frees each once
    it has gone to on_result and store, returns an empty list, and still raises the degradation
    warning from a light tally. sectors are stamped on each Result, and on_result works on the sync
    form too."""
    urls = [f's{n}.org' for n in range(5)]

    async def stub(url, max_pages=6, deep=False, keep_pages=False, block_private_hosts=False,
                   browser=None):
        return LA.Result(url=url, verdict='english_only', pages_read=15,
                         read_quality=LA.read_quality_of(15))

    _counting_browser(monkeypatch)
    monkeypatch.setattr(LA, '_audit_async', stub)
    seen = []
    got = LA.audit_many(urls, concurrency=2,
                        on_result=lambda i, r: seen.append((i, r.sector)),
                        retain=False, sectors=['government'] * 5)
    assert got == [], 'retain=False returns no list; results come through on_result'
    assert len(seen) == 5 and all(s == 'government' for _i, s in seen), 'streamed, sector stamped'


def test_retain_true_returns_the_list_with_sectors_stamped(monkeypatch):
    """The default holds the list, and sectors ride on it whichever way retention is set."""
    urls = ['a.org', 'b.org']

    async def stub(url, max_pages=6, deep=False, keep_pages=False, block_private_hosts=False,
                   browser=None):
        return LA.Result(url=url, verdict='english_only', pages_read=15,
                         read_quality=LA.read_quality_of(15))

    _counting_browser(monkeypatch)
    monkeypatch.setattr(LA, '_audit_async', stub)
    got = LA.audit_many(urls, concurrency=2, sectors=['nonprofit', 'government'])
    assert [r.url for r in got] == urls
    assert [r.sector for r in got] == ['nonprofit', 'government']


def test_a_failed_site_leaves_a_line_in_the_store(monkeypatch, tmp_path):
    """`_failed` builds a Result and nothing used to write it, so a site that failed left no line
    and a caller could not tell it apart from a site that was never attempted."""
    async def stub(url, max_pages=6, deep=False, keep_pages=False, block_private_hosts=False,
                   browser=None):
        if url == 'bad.org':
            raise RuntimeError('the driver went away')
        return LA.Result(url=url, verdict='english_only', pages_read=1)

    _counting_browser(monkeypatch)
    monkeypatch.setattr(LA, '_audit_async', stub)
    store = tmp_path / 'store.jsonl'
    got = asyncio.run(LA.audit_many_async(['good.org', 'bad.org', 'also-good.org'],
                                          store=str(store)))
    assert [r.url for r in got] == ['good.org', 'bad.org', 'also-good.org']
    lines = [json.loads(x) for x in store.read_text(encoding='utf-8').splitlines() if x.strip()]
    assert len(lines) == 3, 'the failure is written down like the other two'
    bad = [d for d in lines if d['url'] == 'bad.org']
    assert len(bad) == 1 and 'RuntimeError' in bad[0]['note']
    assert bad[0]['audited_at'] and bad[0]['tool_version'], (
        'a failure line is dated and versioned like a reading, or it cannot be compared with one')


def test_a_browser_handed_in_is_not_closed_by_the_audit():
    """A shared browser outlives the site, so `browser=` closes the context this audit opened and
    leaves the browser for the next site. With no browser handed in nothing changes: the close of
    the browser takes its contexts with it, which is what it always did."""
    closed = []

    class _Ctx:
        async def close(self):
            closed.append('ctx')

        async def add_init_script(self, *a, **k):
            raise RuntimeError('far enough: the site itself is not what is being tested')

    class _B:
        def __init__(self):
            self.closed = False

        async def new_context(self, **k):
            return _Ctx()

        async def close(self):
            self.closed = True

    b = _B()
    with pytest.raises(RuntimeError):
        asyncio.run(LA._audit_async('https://x.org', browser=b))
    assert closed == ['ctx']
    assert b.closed is False


def test_a_noise_code_can_never_name_a_language(monkeypatch):
    """A code in AUX_NOISE is dropped before AUX_ISO is consulted, so an entry in both lists is
    dead code. Today that is exactly Irish. Pinning it here means un-deadening it is a decision
    somebody makes rather than a side effect of adding a language."""
    import sys
    import types

    both = set(LA.AUX_NOISE) & set(LA.AUX_ISO)
    assert both == {'ga'}, f'the codes that are in both lists changed: {sorted(both)}'

    # THE SECOND DEAD ENTRY, and it was live in this file's prose for months. `lt` is in AUX_ISO and
    # Lithuanian is one of the twenty FUNC lists, so it is in COVERED, so `_aux_languages` filters
    # the name out after the lookup. It cannot produce a reading, exactly as `ga` cannot, and it was
    # named in two comments as the language the auxiliary reader exists for. Pinned by the same rule
    # and for the same reason: waking it up should be a decision somebody makes.
    dead = sorted(c for c, name in LA.AUX_ISO.items() if name in LA.COVERED)
    assert dead == ['lt'], f'the AUX_ISO codes shadowed by a word list changed: {dead}'

    fake = types.ModuleType('langid')
    fake.classify = lambda text: ('ga', 1.0)
    monkeypatch.setitem(sys.modules, 'langid', fake)
    block = ('Tá an eagraíocht seo ag obair le teaghlaigh ar fud an chontae gach lá den tseachtain '
             'agus tá gach seirbhís saor in aisce do gach duine sa phobal áitiúil anseo. ')
    assert LA._aux_languages(block * 3, set()) == []


def test_an_auxiliary_language_is_quoted_from_the_text_that_found_it():
    """The quote for a language langid found used to be the opening words of the page, which are
    English on a page whose second language is further down."""
    pytest.importorskip('langid')
    english = ('Welcome to our organization. We serve families across the county with legal help, '
               'English classes and case management every day of the week. ')
    swahili = ('Shirika letu linatoa huduma za msaada kwa familia zote katika mkoa wetu na maeneo '
               'yanayozunguka kwa lugha ya Kiswahili kila siku ya wiki bila malipo yoyote. ')
    q = LA._quote(english + swahili, 'Swahili')
    assert 'Shirika' in q and 'Welcome to our organization' not in q


# ---------------------------------------------------------------- accuracy pass, 2026-07-29
_SM_INDEX = ('<?xml version="1.0"?><sitemapindex>'
             '<sitemap><loc>https://good.example/posts.xml</loc></sitemap>'
             '<sitemap><loc>https://good.example/pages.xml</loc></sitemap>'
             '</sitemapindex>')
_SM_POSTS = ('<?xml version="1.0"?><urlset>'
             + ''.join(f'<url><loc>https://good.example/2019/0{i}/post-{i}</loc></url>'
                       for i in range(1, 10))
             + '</urlset>')
_SM_PAGES = ('<?xml version="1.0"?><urlset>'
             '<url><loc>https://good.example/about</loc></url>'
             '<url><loc>https://good.example/services/immigration</loc></url>'
             '</urlset>')


def test_a_file_of_posts_cannot_starve_the_file_of_pages():
    """Nested sitemaps were concatenated, so on a site with a blog every post came before every
    page and the page carrying the second language fell outside the limit. Round-robin costs no
    extra fetch, and an address shaped like a dated post goes last."""
    files = {'https://good.example/sitemap.xml': _SM_INDEX,
             'https://good.example/posts.xml': _SM_POSTS,
             'https://good.example/pages.xml': _SM_PAGES}
    out = asyncio.run(LA._sitemap_pages(_FakeContext(files), 'https://good.example/'))
    assert out[:2] == ['https://good.example/about', 'https://good.example/services/immigration']
    assert all(LA.DATED_POST.search(u) for u in out[2:])
    assert len(out) == 11                      # nothing is dropped, only reordered


class _FakeMouse:
    async def wheel(self, x, y):
        return None


class _FakeResp:
    def __init__(self, status):
        self.status = status


class _FakePage:
    """Enough of a Playwright page for _read: a status, a body, and the calls _read makes."""

    def __init__(self, ctx, status, body):
        self._ctx, self._status, self._body = ctx, status, body
        self.mouse = _FakeMouse()
        self.url = 'https://x.org/'

    async def goto(self, url, wait_until=None, timeout=None):
        self._ctx.reads.append(url)
        self.url = url
        return _FakeResp(self._status)

    async def wait_for_timeout(self, ms):
        return None

    async def inner_text(self, sel):
        return self._body

    async def content(self):
        return '<html><body>' + self._body + '</body></html>'

    async def evaluate(self, *a, **k):
        return None


class _FakeCtx2:
    def __init__(self, reads, status, body):
        self.reads, self._status, self._body = reads, status, body
        self.closed = False

    async def add_init_script(self, *a, **k):
        return None

    async def new_page(self):
        return _FakePage(self, self._status, self._body)

    async def close(self):
        self.closed = True


class _FakeBrowser2:
    def __init__(self, status, body):
        self.reads, self.contexts = [], []
        self._status, self._body = status, body

    async def new_context(self, **k):
        c = _FakeCtx2(self.reads, self._status, self._body)
        self.contexts.append(c)
        return c

    async def close(self):
        return None


def test_a_short_403_body_is_unreachable_and_not_english_only(monkeypatch):
    """One site answers this machine with 145 characters of "Server Error 403 Forbidden", and the
    audit gated only on the body being non-empty, so a site that refused to be read was published as
    having no language access. The status is already in hand; this uses it."""
    async def no_sleep(_s):
        return None

    monkeypatch.setattr(LA.asyncio, 'sleep', no_sleep)
    body = ('Server Error 403 Forbidden You do not have permission to access this document. '
            "That's what you can do Reload Page Back to Previous Page Home Page")
    b = _FakeBrowser2(403, body)
    r = asyncio.run(LA._audit_async('https://x.org', browser=b))
    assert r.verdict == 'unreachable'
    assert '403' in r.note
    assert r.pages_read == 0


def test_the_home_read_is_retried_once_before_a_site_is_called_dead(monkeypatch):
    """Two of 115 sites flipped between true_multilingual, machine_translate and unreachable across
    eight runs of identical code. Reading a live site as dead is the expensive direction, so the
    home read gets one more try in a fresh context, and the note says so."""
    async def no_sleep(_s):
        return None

    monkeypatch.setattr(LA.asyncio, 'sleep', no_sleep)
    b = _FakeBrowser2(200, '')                     # an empty body on every variant
    r = asyncio.run(LA._audit_async('https://x.org', browser=b))
    assert r.verdict == 'unreachable'
    assert '(home read retried once)' in r.note
    # every address variant, twice over, and the second attempt in a context of its own
    assert len(b.reads) == 2 * len(LA._variants('https://x.org'))
    assert len(b.contexts) == 2 and all(c.closed for c in b.contexts)


# ---------------------------------------------------------------- accuracy pass 2, 2026-07-29
# These exercise the CRAWL rather than the detector: which addresses the audit queues, and what
# happens to the text between the browser and languages_in. No network and no browser; the fake
# below serves a fixed map of addresses and records every one that was asked for.


class _MapPage:
    """A page over a fixed map of addresses. Unknown addresses answer 404 with an empty body."""

    def __init__(self, ctx):
        self._ctx = ctx
        self.mouse = _FakeMouse()
        self.url = ''
        self._html = self._text = ''
        self._status = 404

    async def goto(self, url, wait_until=None, timeout=None):
        self._ctx.reads.append(url)
        self.url = url
        got = self._ctx.pages.get(url.rstrip('/').lower())
        if got is None:
            self._html, self._text, self._status = '', '', 404
        else:
            # A fourth element is where the address FORWARDED to, which the audit reads off
            # `page.url` and which nothing here could express before. Without it no test in this
            # suite could reach the two guards that compare where a read was sent with where it
            # arrived, and neither guard had one.
            self._html, self._text, self._status = got[:3]
            if len(got) > 3:
                self.url = got[3]
        return _FakeResp(self._status)

    async def wait_for_timeout(self, ms):
        return None

    async def inner_text(self, sel):
        return self._text

    async def content(self):
        return self._html

    async def evaluate(self, *a, **k):
        return None


class _MapCtx:
    def __init__(self, browser):
        self.reads, self.pages = browser.reads, browser.pages
        self.closed = False
        self.routes = []
        if browser.plain is not None:
            self.request = browser.plain

    async def add_init_script(self, *a, **k):
        return None

    async def route(self, pattern, handler):
        # _install_host_guard registers a route handler when block_private_hosts is on, which
        # the retry now passes unconditionally. Recording it rather than raising keeps the fake a
        # fake: the guard's own behaviour is tested against a real context elsewhere, and here
        # what matters is that a caller asking for the guard still gets a page.
        self.routes.append(pattern)
        return None

    async def new_page(self):
        return _MapPage(self)

    async def close(self):
        self.closed = True


class _MapBrowser:
    """pages maps a lowercased address with no trailing slash to (html, text, status)."""

    def __init__(self, pages, plain=None):
        self.pages = {k.rstrip('/').lower(): v for k, v in pages.items()}
        self.reads, self.contexts, self.plain = [], [], plain

    async def new_context(self, **k):
        c = _MapCtx(self)
        self.contexts.append(c)
        return c

    async def close(self):
        return None


def _page(text, html=None):
    return (html if html is not None else '<html><body>' + text + '</body></html>', text, 200)


_ENTRY = 'https://x.org/us/about/fund/'
_SUBPATH_SITE = {
    _ENTRY: _page('The fund supports scholarships for students. Read about our programs here.',
                  '<html><body><a href="/us/about/fund/programs">Programs</a></body></html>'),
    'https://x.org/': _page('Welcome to the association. We run classes, events and a newsletter.'),
}


def test_the_front_door_is_read_when_the_address_on_file_has_a_path():
    """One organization is recorded at <host>/us/about/<name>/ and its home page was never fetched,
    because "/" matches no keyword and nothing else queues it."""
    b = _MapBrowser(_SUBPATH_SITE)
    r = asyncio.run(LA._audit_async(_ENTRY, browser=b))
    assert 'https://x.org/' in b.reads
    assert r.pages_read >= 2, 'the root was queued but never counted as a page'


# ---- the address on file, and where it landed
#
# A characterization test, not a fix. `_read_home` sets `r.url` to `page.url`, so a recorded address
# that forwards to another domain becomes the site, and every same-site test afterwards is taken
# against the new address. The interior crawl refuses a link that lands off the site; the home read
# does not, and the internal defect record carries the measurement that says why closing the gap the
# obvious way costs more than it saves. This pins what the audit does today, so that a change to it
# has to move a test rather than pass unnoticed.
_REBRAND = ('El condado ofrece servicios de salud publica y asistencia para las familias que viven '
            'aqui. Nuestra oficina esta abierta de lunes a viernes para atender a la comunidad.')


def test_the_site_is_whatever_the_home_address_landed_on():
    b = _MapBrowser({'http://co.example.mn.us/': ('<html><body>' + _REBRAND + '</body></html>',
                                                  _REBRAND, 200, 'https://examplecounty.gov/')})
    r = asyncio.run(LA._audit_async('http://co.example.mn.us/', browser=b))
    # right for a rebrand, which is what 52 of the 56 government redirects in the corpus are
    assert r.url == 'https://examplecounty.gov/' and r.pages_read >= 1
    assert 'Spanish' in r.languages
    assert 1 not in r.rules and 2 not in r.rules, (
        'a rebrand redirect is not a social profile or a parked domain')

    # and wrong for a lapsed domain, which is the other four. One county is recorded at a `.com`
    # address it let go, the address now answers at a football-streaming site, and the audit
    # reports the county in the language that site is written in.
    other = ('Trang web truc tiep bong da hom nay voi day du lich thi dau va bang xep hang cua cac '
             'giai dau lon, cung tin tuc va nhan dinh moi ngay cho nguoi ham mo ca nuoc.')
    b = _MapBrowser({'http://www.example.com/': ('<html><body>' + other + '</body></html>',
                                                 other, 200, 'https://www.example.net/')})
    r = asyncio.run(LA._audit_async('http://www.example.com/', browser=b))
    assert r.url == 'https://www.example.net/'
    assert 1 not in r.rules and 2 not in r.rules, (
        'a redirected home is not a social profile or a parked domain')


_ES_LANDING = ('La organizacion ofrece servicios de salud y asistencia legal para las familias '
               'inmigrantes de la comunidad, con clases de ingles y ayuda para la ciudadania.')
# The browser follows the redirect, so navigating either interior link returns the ONE Spanish
# landing's content with `page.url` at that landing, exactly as the rebrand test above models it.
_ES_LANDED = ('<html><body>' + _ES_LANDING + '</body></html>', _ES_LANDING, 200,
              'https://x.org/es/inicio')
_TWO_LINKS_ONE_LANDING = {
    'https://x.org/': _page(
        'Welcome to the association. We run classes, events and a weekly newsletter for members.',
        '<html><body><a href="/servicios">Servicios en espanol</a>'
        '<a href="/programas">Programas en espanol</a></body></html>'),
    'https://x.org/servicios': _ES_LANDED,
    'https://x.org/programas': _ES_LANDED,
}


def test_two_links_that_forward_to_one_page_are_read_once():
    """`seen` held the QUEUED address, so two links that both 302 to one landing were each read and
    counted; the shared Spanish then sat on two of three pages and boilerplate removal deleted it as
    furniture, leaving english_only. The dedup is on where the browser LANDED, so the one page is one
    read, boilerplate never triggers (two pages, below its floor of three), and the reading survives."""
    b = _MapBrowser(_TWO_LINKS_ONE_LANDING)
    r = asyncio.run(LA._audit_async('https://x.org/', browser=b))
    assert r.pages_read == 2, 'home plus the one landing, not the landing twice'
    assert 'Spanish' in r.languages, 'the Spanish page survives instead of reading as boilerplate'


_IFRAME_SITE = {
    'https://x.org/': _page(
        'Welcome. Use the panel below for our services, classes and legal help.',
        '<html><body><p>Welcome. Use the panel below for our services, classes and legal help.</p>'
        '<iframe src="/embed/es"></iframe>'
        '<iframe src="https://maps.example.com/here"></iframe></body></html>'),
    'https://x.org/embed/es': _page(_ES_LANDING),
}


def test_a_same_site_iframe_of_content_is_read():
    """`_read` reads the main frame only, so a page whose content is a same-site iframe was read as
    an empty shell and reported english_only. The iframe's address is queued like an interior link;
    a cross-site iframe (a map) is refused the way an off-site link is."""
    b = _MapBrowser(_IFRAME_SITE)
    r = asyncio.run(LA._audit_async('https://x.org/', browser=b))
    assert 'https://x.org/embed/es' in b.reads, 'the same-site iframe was queued'
    assert not any('maps.example.com' in u for u in b.reads), 'the cross-site iframe was not'
    assert 'Spanish' in r.languages


def test_the_subdomain_locale_probes_are_queued_behind_everything_else():
    """A locale mirror lives at a subdomain as often as at a path, and nothing ever asked for one."""
    b = _MapBrowser(_SUBPATH_SITE)
    asyncio.run(LA._audit_async(_ENTRY, browser=b))
    for u in ('https://es.x.org/', 'https://ko.x.org/', 'https://vi.x.org/'):
        assert u in b.reads
    # behind the site's own pages: the front door is asked for before any guess is
    assert b.reads.index('https://x.org/') < b.reads.index('https://es.x.org/')


_JAPANESE = ('当センターは日本語を母語とする家族のために、日本語学校と生活相談の窓口を運営しています。'
             '毎週土曜日に授業を行っており、新入生の登録を受け付けています。')


class _PlainResp:
    def __init__(self, status, body):
        self.status, self._body = status, body

    async def text(self):
        return self._body


class _PlainClient:
    """An APIRequestContext with one document on it, which is all _plain_fetch asks for."""

    def __init__(self, files):
        self.files, self.asked = files, []

    async def get(self, url, timeout=None, headers=None):
        self.asked.append(url)
        body = self.files.get(url.rstrip('/'))
        return _PlainResp(404, '') if body is None else _PlainResp(200, body)


def test_a_403_to_the_browser_is_retried_once_with_a_plain_fetch(monkeypatch):
    """One site answers Chromium with a 32-character 403 and answers an ordinary HTTP client, same
    user agent, with 20 KB of Japanese. Calling that unreachable is right and still loses the site.
    Only the home page, and only once: a site is being rescued, not a page."""
    async def no_sleep(_s):
        return None

    monkeypatch.setattr(LA.asyncio, 'sleep', no_sleep)
    doc = '<html><head><title>Center</title></head><body><p>' + _JAPANESE * 6 + '</p></body></html>'
    plain = _PlainClient({'https://x.org': doc})
    b = _MapBrowser({}, plain=plain)          # every address 404s to the browser with no body
    b.pages['https://x.org'] = ('<html><body>Forbidden</body></html>', 'Forbidden', 403)
    r = asyncio.run(LA._audit_async('https://x.org', browser=b))
    assert r.verdict == 'true_multilingual'
    assert r.languages == ['Japanese']
    assert 'plain HTTP fetch' in r.note
    assert plain.asked.count('https://x.org') == 1, 'the plain fetch is once per audit'


def test_an_interior_page_gets_no_plain_fetch():
    """The rescue is for a site that could not be read at all, not for one page of one that could."""
    plain = _PlainClient({'https://x.org/hidden': '<html><body>' + _JAPANESE * 3 + '</body></html>'})
    b = _MapBrowser({'https://x.org': _page(
        'Welcome to our community center, with classes and legal help for families.',
        '<html><body><a href="/hidden">Our services</a></body></html>')}, plain=plain)
    r = asyncio.run(LA._audit_async('https://x.org', browser=b))
    assert 'https://x.org/hidden' not in plain.asked
    assert r.verdict == 'english_only'


class _RedirectingPlainResp:
    """A plain response that LANDED somewhere other than where it was asked, the way a home address
    that forwards to a hosting provider or a donation processor does."""

    def __init__(self, status, body, url):
        self.status, self._body, self.url = status, body, url

    async def text(self):
        return self._body


class _RedirectingPlainClient:
    def __init__(self, body, landed):
        self._body, self._landed, self.asked = body, landed, []

    async def get(self, url, timeout=None, headers=None):
        self.asked.append(url)
        return _RedirectingPlainResp(200, self._body, self._landed)


def test_the_plain_fetch_refuses_a_cross_site_redirect(monkeypatch):
    """The browser 403s, the rescue fetches with a plain client, and the client follows a redirect
    off the site to a parked page. Accepting it recorded that page's language as the organization's
    own server document at the audited address; the rescue now checks where the fetch landed."""
    async def no_sleep(_s):
        return None

    monkeypatch.setattr(LA.asyncio, 'sleep', no_sleep)
    plain = _RedirectingPlainClient('<html><body><p>' + _JAPANESE * 6 + '</p></body></html>',
                                    'https://parked.example.net/for-sale')
    b = _MapBrowser({}, plain=plain)                        # every address 403s to the browser
    b.pages['https://x.org'] = ('<html><body>Forbidden</body></html>', 'Forbidden', 403)
    r = asyncio.run(LA._audit_async('https://x.org', browser=b))
    assert r.verdict != 'true_multilingual', 'a parked page it forwarded to is not the org writing'
    assert r.languages == []
    assert 'plain HTTP fetch' not in r.note
    assert r.url == 'https://x.org' or r.url == 'https://x.org/'


_NAV = 'Про нас Фестиваль Особливості Стати Спонсором Спонсори Паркінг Програма Контакти'
_BOILER_SITE = {
    'https://x.org': (
        '<html><head><title>Society</title></head><body>'
        '<a href="/about">About</a><a href="/program">Program</a><a href="/contact">Contact</a>'
        '</body></html>',
        _NAV + '\nWelcome to the society. We hold a festival every summer in the park.', 200),
    'https://x.org/about': _page(_NAV + '\nThe society was founded in 1949 by a group of families.'),
    'https://x.org/program': _page(_NAV + '\nThe program runs from Friday evening to Sunday night.'),
    'https://x.org/contact': _page(_NAV + '\nCall the office on weekdays or write to the address.'),
}


def test_a_navigation_column_on_every_page_does_not_carry_the_site():
    """The whole audit's longest run on one site was 226 characters of navigation column, and its
    stored quote was that row rather than the paragraphs underneath. What a nav, a footer, a cookie
    banner and a widget menu have in common is that they are on most of the pages."""
    b = _MapBrowser(_BOILER_SITE)
    r = asyncio.run(LA._audit_async('https://x.org', browser=b))
    assert r.pages_read >= 4, 'the fixture needs enough pages for the repeat to be measurable'
    assert r.verdict == 'english_only'
    assert r.languages == []


def test_the_same_navigation_on_one_page_alone_is_still_read():
    """Below three pages there is nothing to compare, so a short audit is left as it was and the
    reading errs towards finding the language rather than towards silence."""
    b = _MapBrowser({'https://x.org': _page(_NAV + '\nWelcome to the society.')})
    r = asyncio.run(LA._audit_async('https://x.org', browser=b))
    assert r.languages == ['Ukrainian']


def test_a_directory_profile_is_not_audited_at_all():
    """Rule 5: nothing has been measured about the organization's own website, so no browser is
    opened and no verdict is claimed. The row goes to the website-field queue."""
    b = _MapBrowser({'https://app.candid.org/profile/0000000': _page('A profile page.')})
    r = asyncio.run(LA._audit_async('https://app.candid.org/profile/0000000', browser=b))
    assert r.verdict == 'unreachable'
    assert "not the organization's own website" in r.note
    assert b.reads == [], 'the directory was read before it was recognised'


# ---------------------------------------------------------------- accuracy pass 3, 2026-07-30
# These exercise the parts of the audit that sit between the browser and the judgement: which text
# reaches `languages_in`, what the clock does to a crawl, what robots.txt does to it, whether the
# document the server sent is consulted, and whether a reading can be written down. No network and
# no browser; the fakes above are extended where a new signal has to be emulated.


class _ChromePage(_MapPage):
    """A page that can answer the chrome-removal script, which needs a DOM the fake has not got.

    `mains` maps an address to the text the browser would report with the navigation, header and
    footer hidden. The real removal is JavaScript and is exercised in tests/test_live.py; what is
    pinned here is the WIRING, that the chrome-free text and not the whole body is what the language
    reading is taken on.
    """

    async def evaluate(self, script, arg=None):
        if isinstance(script, str) and 'laHidden' in script:
            return self._ctx.mains.get(self.url.rstrip('/').lower(), self._text)
        return None


class _ChromeCtx(_MapCtx):
    def __init__(self, browser):
        super().__init__(browser)
        self.mains = browser.mains

    async def new_page(self):
        return _ChromePage(self)


class _ChromeBrowser(_MapBrowser):
    def __init__(self, pages, mains, plain=None):
        super().__init__(pages, plain=plain)
        self.mains = {k.rstrip('/').lower(): v for k, v in mains.items()}

    async def new_context(self, **k):
        c = _ChromeCtx(self)
        self.contexts.append(c)
        return c


_FR_CHROME = ('Passer au contenu principal ACCUEIL NOS SERVICES POUR LES FAMILLES QUI ONT BESOIN '
              'DE NOUS ÉVÉNEMENTS RELIER PRENDRE CONTACT New Page New Page New Page')


def test_a_page_whose_only_second_language_is_its_menu_is_not_a_page_in_that_language():
    """One site reads a language off a single locale page whose whole text is menu chrome: a skip
    link, a translated navigation bar and a footer, interleaved with untranslated placeholders. One
    page, so the cross-page repeat test has nothing to compare; one locale mirror, so the
    three-front-doors rule cannot fire either. The markup says which parts are navigation."""
    site = {'https://x.org/fr': _page(_FR_CHROME)}
    assert LA.languages_in(_FR_CHROME) == ['French'], 'the fixture has to be readable as French'
    b = _ChromeBrowser(site, mains={'https://x.org/fr': ''})
    r = asyncio.run(LA._audit_async('https://x.org/fr', browser=b))
    assert r.languages == []
    assert r.verdict == 'english_only'


def test_the_body_underneath_the_chrome_is_still_read():
    """Removing the furniture must not remove the page: the same nav with a paragraph under it is a
    page in the language, and it is the paragraph that says so."""
    prose = ('Nuestros servicios para la comunidad son gratuitos. Ofrecemos informacion y recursos '
             'para las familias que necesitan ayuda con este proceso, y todos pueden hacer una cita.')
    site = {'https://x.org/': _page(_FR_CHROME + '\n' + prose)}
    b = _ChromeBrowser(site, mains={'https://x.org/': prose})
    r = asyncio.run(LA._audit_async('https://x.org', browser=b))
    assert r.languages == ['Spanish']


def test_the_whole_body_is_still_what_the_wall_and_the_widget_tests_read():
    """Only the text handed to `languages_in` is narrowed. A bot wall lives in the chrome as often
    as anywhere, and a site whose interstitial was hidden before the wall test would be read as an
    empty English page, which is the confusion the unreachable class exists to prevent."""
    wall = 'Just a moment... Checking your browser before accessing the site.'
    b = _ChromeBrowser({'https://x.org/': _page(wall)}, mains={'https://x.org/': ''})
    r = asyncio.run(LA._audit_async('https://x.org', browser=b))
    assert r.verdict == 'unreachable'


# ---- F4: the page budget outruns the time budget
_SPANISH_HOME = ('Nuestros servicios para la comunidad son gratuitos. Ofrecemos informacion y '
                 'recursos para las familias que necesitan ayuda con este proceso, y todos '
                 'pueden hacer una cita con un abogado.')
_MANY_PAGES = dict(
    {'https://x.org/': (
        '<html><head><title>Centro</title></head><body>'
        + ''.join('<a href="/services/%d">Servicios %d</a>' % (i, i) for i in range(12))
        + '</body></html>', _SPANISH_HOME, 200)},
    **{'https://x.org/services/%d' % i: _page('Page %d about our work in the county.' % i)
       for i in range(12)})


def test_a_crawl_cut_short_by_the_clock_still_reports_what_it_read():
    """A timeout used to cancel the audit and throw away everything it had found, and the caller
    recorded `unreachable`, which says a live multilingual site could not be read. The crawl now
    stops queueing while there is still time to judge, and the note says how much it managed."""
    async def go():
        b = _MapBrowser(_MANY_PAGES)
        # a deadline already inside the reserve, so no interior page is ever queued
        deadline = asyncio.get_running_loop().time() + 1
        return b, await LA._audit_async('https://x.org', browser=b, deadline=deadline)

    b, r = asyncio.run(go())
    assert r.verdict == 'true_multilingual'
    assert r.languages == ['Spanish']
    assert 'crawl cut short by the time budget after 1 pages' in r.note
    assert not any('/services/' in u for u in b.reads), 'a page was queued inside the reserve'


def test_a_crawl_with_time_to_spare_reads_the_whole_site():
    """The cut is a floor on the clock and not a new page limit: with the budget nowhere near
    spent, the same site is read exactly as it was."""
    async def go():
        b = _MapBrowser(_MANY_PAGES)
        deadline = asyncio.get_running_loop().time() + 6000
        return b, await LA._audit_async('https://x.org', browser=b, deadline=deadline)

    b, r = asyncio.run(go())
    assert r.pages_read > 1
    assert 'cut short' not in r.note


# ---- F5: robots.txt
class _RobotsClient(_PlainClient):
    """A plain client that answers /robots.txt on any origin with one body."""

    def __init__(self, robots, files=None):
        super().__init__(files or {})
        self.robots = robots

    async def get(self, url, timeout=None, headers=None):
        if url.endswith('/robots.txt'):
            self.asked.append(url)
            return _PlainResp(200, self.robots)
        return await super().get(url, timeout=timeout, headers=headers)


def test_a_home_page_robots_disallows_is_not_read_and_is_not_english_only():
    """Rule 5's shape for a different reason: nothing about the site has been read, so nothing is
    claimed about it. Recording english_only would say something that was never checked."""
    b = _MapBrowser({'https://x.org/': _page('Welcome to our center.')},
                    plain=_RobotsClient('User-agent: *\nDisallow: /\n'))
    r = asyncio.run(LA._audit_async('https://x.org', browser=b))
    assert r.verdict == 'unreachable'
    assert 'robots.txt disallowed the home page' in r.note
    assert b.reads == [], 'the browser fetched a page the host asked it not to'


def test_a_disallowed_interior_page_is_skipped_and_the_audit_goes_on():
    """robots.txt is a statement about addresses, not about the site, so one disallowed address is
    one page not read and not a site written off."""
    site = {'https://x.org/': (
        '<html><head><title>Centro</title></head><body><a href="/private">Private</a>'
        '<a href="/servicios">Servicios</a></body></html>',
        'Welcome to our center, with legal help and classes for families.', 200),
        'https://x.org/private': _page('Staff only.'),
        'https://x.org/servicios': _page(_SPANISH_HOME)}
    b = _MapBrowser(site, plain=_RobotsClient('User-agent: *\nDisallow: /private\n'))
    r = asyncio.run(LA._audit_async('https://x.org', browser=b))
    assert 'https://x.org/private' not in b.reads
    assert r.languages == ['English', 'Spanish']
    assert r.verdict == 'true_multilingual'


def test_robots_is_read_by_default_and_switching_it_off_is_an_override():
    """A published instrument reads robots.txt. The way to not read it has to be asked for."""
    import inspect
    for fn in (LA.audit, LA.audit_async, LA.audit_many, LA.audit_many_async):
        p = inspect.signature(fn).parameters
        assert p['respect_robots'].default is True
        assert p['respect_robots'].kind is inspect.Parameter.KEYWORD_ONLY
    site = {'https://x.org/': (
        '<html><head><title>Centro</title></head><body><a href="/private">Private</a></body></html>',
        'Welcome to our center, with legal help and classes for families.', 200),
        'https://x.org/private': _page(_SPANISH_HOME)}
    b = _MapBrowser(site, plain=_RobotsClient('User-agent: *\nDisallow: /private\n'))
    r = asyncio.run(LA._audit_async('https://x.org', browser=b, respect_robots=False))
    assert 'https://x.org/private' in b.reads
    assert r.languages == ['English', 'Spanish']


def test_a_robots_file_that_cannot_be_fetched_stops_nothing():
    """A momentary server error must not turn a readable site into an unreadable one, so anything
    other than a 200 is read as no restrictions."""
    b = _MapBrowser({'https://x.org/': _page(_SPANISH_HOME)}, plain=_PlainClient({}))
    r = asyncio.run(LA._audit_async('https://x.org', browser=b))
    assert r.verdict == 'true_multilingual'


# ---- F1: the document the server sent
_ES_SERVER = ('<html><head><title>Centro</title></head><body><p>' + _SPANISH_HOME
              + '</p></body></html>')


def _server_confirm(evidence, files):
    plain = _PlainClient(files)
    ctx = type('C', (), {'request': plain})()
    asyncio.run(LA._confirm_server_html(ctx, evidence))
    return plain


def test_a_language_in_the_server_response_was_not_written_by_a_browser_widget():
    """Google Translate, GTranslate and ConveyThis rewrite the page in the browser, so their output
    cannot be in the document the server sent. This test is the only direct one the package has for
    the question every other signal answers by proxy."""
    ev = [LA.Evidence('translated_page', 'https://x.org/es', 'texto', 'Spanish')]
    plain = _server_confirm(ev, {'https://x.org/es': _ES_SERVER})
    assert ev[0].server_html is True
    assert plain.asked == ['https://x.org/es']
    # the confirmation mechanics work, and at a locale address they no longer prove authorship:
    # ConveyThis serves its own output at ?locale= routes, server-side
    assert LA.verdict_for(ev, 'ConveyThis') == 'machine_translate'
    own = [LA.Evidence('translated_page', 'https://x.org/servicios', 'texto', 'Spanish')]
    _server_confirm(own, {'https://x.org/servicios': _ES_SERVER})
    assert own[0].server_html is True
    assert LA.verdict_for(own, 'ConveyThis') == 'true_multilingual'


def test_a_server_side_plugin_page_is_not_confirmed_and_a_proxy_is_not_even_fetched():
    """The boundary belongs in the code. WPML, Polylang, TranslatePress, Weglot in proxy mode and a
    *.translate.goog address all translate BEFORE the response leaves the host, so the server
    document does not settle who wrote the words there. The claim `server_html` supports is 'not
    client-side widget output', never 'the organization wrote it'.

    Since 2026-07-30 the withheld mark is not the whole answer: the REASON it was withheld is
    recorded, on `server_plugin`, and the two reasons are different things. A CMS plugin marker is
    rule 11, where a marker counts alongside content, and this page has a whole Spanish page
    of content, so the verdict is true_multilingual (it was machine_translate before this pass; see
    the report and `LA.class_for`). A *.translate.goog address is Google Translate's own output
    served from Google's host, so it stays `client_widget` and the class does not move."""
    plugin = [LA.Evidence('translated_page', 'https://y.org/es', 'texto', 'Spanish')]
    _server_confirm(plugin, {'https://y.org/es': _ES_SERVER.replace(
        '<body>', '<body><!-- wpml-language-switcher -->')})
    assert plugin[0].server_html is False
    assert plugin[0].server_plugin is True
    assert LA.authorship_of(plugin[0], 'ConveyThis') == LA.AUTHOR_SERVER_PLUGIN
    assert LA.verdict_for(plugin, 'ConveyThis') == 'true_multilingual'

    proxy = [LA.Evidence('translated_page', 'https://x-org.translate.goog/es', 'texto', 'Spanish')]
    plain = _server_confirm(proxy, {'https://x-org.translate.goog/es': _ES_SERVER})
    assert proxy[0].server_html is False
    assert proxy[0].server_plugin is False
    assert plain.asked == [], 'a translation proxy was fetched to be told what it is'
    assert LA.authorship_of(proxy[0], 'Google Translate') == LA.AUTHOR_CLIENT_WIDGET
    assert LA.verdict_for(proxy, 'Google Translate') == 'machine_translate'


def test_only_a_page_that_produced_evidence_costs_a_request():
    """One extra lightweight request per evidence-bearing page, and none at all for the fourteen
    pages of an ordinary site that produced none."""
    ev = [LA.Evidence('inline_text', 'https://x.org/', 'q', ''),          # no language named
          LA.Evidence('translation_plugin', 'https://x.org/about', 'wpml', ''),
          LA.Evidence('inline_text', 'https://x.org/servicios', 'texto', 'Spanish')]
    plain = _server_confirm(ev, {'https://x.org/servicios': _ES_SERVER})
    assert plain.asked == ['https://x.org/servicios']


def test_the_language_has_to_be_in_the_server_response_and_not_merely_the_page():
    """An English document coming back from the server is what a client-side widget's page looks
    like underneath, and the mark exists to tell that case apart."""
    ev = [LA.Evidence('translated_page', 'https://x.org/es', 'texto', 'Spanish')]
    _server_confirm(ev, {'https://x.org/es': '<html><body><p>Our services for the community are '
                                             'free. Resources and information for families.</p>'
                                             '</body></html>'})
    assert ev[0].server_html is False


# ---- F6: a reading nobody can re-check later
def _stub_result():
    r = LA.Result(url='https://x.org/', verdict='true_multilingual', languages=['Spanish'],
                  evidence=[LA.Evidence('inline_text', 'https://x.org/', 'texto', 'Spanish')],
                  audited_at='2026-07-30T12:00:00Z', tool_version='0.2.0')
    r.pages['https://x.org/'] = '<html><body><p>texto en espanol</p></body></html>'
    return r


def test_a_store_file_holds_one_line_per_site_with_the_pages_that_were_read(tmp_path, monkeypatch):
    """Three of the seven disagreements in this project's history were sites that had CHANGED
    rather than rules that were wrong, and there was no way to tell those apart after the fact."""
    stub = _stub_result()

    async def fake(url, max_pages=6, deep=False, keep_pages=False, block_private_hosts=False):
        assert keep_pages is True, 'the pages have to be kept for the store to have anything to write'
        return stub

    monkeypatch.setattr(LA, '_audit_async', fake)
    path = tmp_path / 'audit.jsonl'
    got = asyncio.run(LA.audit_async('https://x.org', store=str(path)))
    lines = path.read_text(encoding='utf-8').splitlines()
    assert len(lines) == 1
    rec = json.loads(lines[0])
    for key in ('url', 'audited_at', 'tool_version', 'verdict', 'languages', 'evidence', 'pages'):
        assert key in rec
    assert rec['pages']['https://x.org/'].startswith('<html>')
    assert rec['evidence'][0]['language'] == 'Spanish'
    # the caller did not ask for the pages, so it does not get megabytes of HTML it never wanted
    assert got.pages == {}
    asyncio.run(LA.audit_async('https://x.org', store=str(path)))
    assert len(path.read_text(encoding='utf-8').splitlines()) == 2, 'the store appends'


def test_a_store_path_ending_gz_is_written_compressed(tmp_path, monkeypatch):
    import gzip as _gzip
    stub = _stub_result()

    async def fake(url, max_pages=6, deep=False, keep_pages=False, block_private_hosts=False):
        return stub

    monkeypatch.setattr(LA, '_audit_async', fake)
    path = tmp_path / 'audit.jsonl.gz'
    asyncio.run(LA.audit_async('https://x.org', store=str(path)))
    with _gzip.open(path, 'rt', encoding='utf-8') as fh:
        assert json.loads(fh.read().strip())['verdict'] == 'true_multilingual'


def test_storing_is_off_by_default():
    import inspect
    for fn in (LA.audit, LA.audit_async, LA.audit_many, LA.audit_many_async):
        p = inspect.signature(fn).parameters
        assert p['store'].default is None
        assert p['store'].kind is inspect.Parameter.KEYWORD_ONLY


# ---- the two axes, on the record rather than only inside the rule
def test_an_audit_writes_both_axes_onto_the_result_and_onto_every_piece_of_evidence():
    """A verdict is a conclusion. What it was read off has to be in the row beside it, or the next
    person to disagree with the verdict has nothing to disagree with but the verdict."""
    b = _MapBrowser({'https://x.org/': _page(_SPANISH_HOME)}, plain=_PlainClient({}))
    r = asyncio.run(LA._audit_async('https://x.org', browser=b))
    assert r.verdict == 'true_multilingual'
    assert r.authorship == LA.AUTHOR_AUTHORED
    assert r.sufficiency >= LA.SUFF_NOTICE
    assert r.by_language['Spanish']['authorship'] == LA.AUTHOR_AUTHORED
    assert r.by_language['Spanish']['sufficiency'] >= LA.SUFF_NOTICE
    for e in r.evidence:
        assert e.authorship in LA.AUTHORSHIP_ORDER
        assert e.sufficiency in LA.SUFFICIENCY_NAMES


def test_a_site_that_was_never_read_records_neither_axis():
    """`unreachable` is decided before either axis is asked for, and a site nobody read has no
    authorship and no sufficiency. Saying `none` about it would be a measurement nobody took."""
    r = LA.Result(url='https://x.org/')
    assert r.verdict == 'unreachable'
    assert r.authorship == LA.AUTHOR_NONE and r.sufficiency == LA.SUFF_NONE
    assert r.by_language == {}


def test_both_axes_survive_json():
    """The row is what a census stores, so the axes have to be in `to_dict`, not only on the object."""
    r = LA.Result(url='https://x.org/', verdict='true_multilingual', languages=['Spanish'],
                  authorship=LA.AUTHOR_AUTHORED, sufficiency=LA.SUFF_NOTICE,
                  by_language={'Spanish': {'authorship': LA.AUTHOR_AUTHORED,
                                           'sufficiency': LA.SUFF_NOTICE},
                               'Vietnamese': {'authorship': LA.AUTHOR_CLIENT_WIDGET,
                                              'sufficiency': LA.SUFF_NONE}},
                  evidence=[LA.Evidence('inline_text', 'https://x.org/', 'aviso', 'Spanish',
                                        server_html=True, authorship=LA.AUTHOR_AUTHORED,
                                        sufficiency=LA.SUFF_NOTICE)])
    back = json.loads(json.dumps(r.to_dict(), ensure_ascii=False))
    assert back['authorship'] == 'authored' and back['sufficiency'] == 2
    assert back['by_language']['Vietnamese'] == {'authorship': 'client_widget', 'sufficiency': 0}
    assert back['evidence'][0]['authorship'] == 'authored'
    assert back['evidence'][0]['sufficiency'] == 2
    assert back['evidence'][0]['server_plugin'] is False


# ---------------------------------------------------------------- the clock, 2026-07-30
#
# A run over 113 development sites came back with 15 of them recorded as the words "timed out after
# 300.0s", and the reading each of those sites had already produced went with it: a home page and
# eight or more interior pages, read, and then thrown away because one step begun inside the reserve
# ran past the caller's cancel. The reserve stopped the QUEUE and nothing stopped the step. These
# guard the four places that could overrun it.


class _SlowPage:
    """A page that records the timeout it was navigated with, and never navigates anywhere."""

    def __init__(self):
        self.gotos = []
        self.url = ''
        self.mouse = _FakeMouse()

    async def goto(self, url, wait_until=None, timeout=None):
        self.gotos.append((url, timeout))
        self.url = url
        return _FakeResp(200)

    async def wait_for_timeout(self, ms):
        return None

    async def inner_text(self, sel):
        return 'A page of ordinary English text about the work of the organization.'

    async def content(self):
        return '<html><body>hello</body></html>'

    async def evaluate(self, *a, **k):
        return None


def test_a_page_read_is_given_only_the_time_the_audit_has_left():
    """The navigation carried a fixed 25 seconds and no knowledge of the deadline, so a page begun
    with twenty seconds left was allowed twenty-five to answer and the audit was cancelled holding
    the site."""
    async def go():
        pg = _SlowPage()
        deadline = asyncio.get_running_loop().time() + 40
        await LA._read(pg, 'https://x.org/a', 25000, deadline=deadline,
                       keep=LA.TIME_BUDGET_RESERVE + LA.READ_TAIL_RESERVE)
        return pg

    pg = asyncio.run(go())
    url, ms = pg.gotos[0]
    assert ms <= (40 - LA.TIME_BUDGET_RESERVE - LA.READ_TAIL_RESERVE) * 1000 + 50
    assert ms < 25000, 'the navigation was allowed longer than the audit had'


def test_a_page_that_cannot_finish_inside_the_clock_is_not_begun():
    """Below the floor there is no read to be had, and starting one spends the reserve that exists
    to get what was already read judged and written down."""
    async def go():
        pg = _SlowPage()
        deadline = asyncio.get_running_loop().time() + 1
        try:
            await LA._read(pg, 'https://x.org/a', 25000, deadline=deadline,
                           keep=LA.TIME_BUDGET_RESERVE)
        except TimeoutError:
            return pg
        raise AssertionError('the read was begun with no time to finish it')

    assert asyncio.run(go()).gotos == [], 'the browser was sent to the address anyway'


def test_a_read_with_no_keep_is_the_read_it_always_was():
    """`keep` is passed by the interior crawl and by nothing else. The home read is deliberately
    unbounded: a site whose home page is slow is a site being read, and cutting that short is how a
    live site becomes unreachable."""
    async def go():
        pg = _SlowPage()
        deadline = asyncio.get_running_loop().time() + 1
        await LA._read(pg, 'https://x.org/', 35000, deadline=deadline)
        return pg

    assert asyncio.run(go()).gotos[0][1] == 35000


def test_the_language_controls_stop_when_the_clock_is_inside_the_reserve():
    """Eight controls, each a click, a settle and a navigation back, is up to two hundred seconds,
    and this knew nothing about the deadline at all."""
    class _Els:
        def __init__(self):
            self.asked = 0

        async def query_selector_all(self, sel):
            self.asked += 1
            return []

    async def go():
        page = _Els()
        deadline = asyncio.get_running_loop().time() + 1
        out, _dead, _stuck = await LA._click_language_controls(page, 'home', 'https://x.org/', deadline=deadline)
        return page, out

    page, out = asyncio.run(go())
    assert out == []
    assert page.asked == 0, 'the page was asked for its controls inside the reserve'


def test_the_language_controls_are_taken_when_there_is_time():
    """The guard is a floor on the clock. With time to spare the page is asked exactly as before."""
    class _Els:
        def __init__(self):
            self.asked = 0

        async def query_selector_all(self, sel):
            self.asked += 1
            return []

    async def go():
        page = _Els()
        deadline = asyncio.get_running_loop().time() + 6000
        await LA._click_language_controls(page, 'home', 'https://x.org/', deadline=deadline)
        return page

    assert asyncio.run(go()).asked == 1


def test_the_sitemap_is_not_fetched_inside_the_reserve():
    """Up to eight fifteen-second fetches sat between the home read and the first interior page."""
    async def go():
        plain = _PlainClient(_SITEMAP_FILES)
        ctx = type('C', (), {'request': plain})()
        deadline = asyncio.get_running_loop().time() + 1
        out = await LA._sitemap_pages(ctx, 'https://good.example/', deadline=deadline)
        return out, plain.asked

    out, asked = asyncio.run(go())
    assert out == [] and asked == []


def test_a_subdomain_whose_name_does_not_resolve_is_left_alone():
    """Eight locale subdomains are invented for every site and most do not exist. Each was a new
    origin, so each brought a robots.txt fetch, a navigation and the waits that follow it."""
    async def go():
        cache = {}
        got = await LA._resolves('this-name-does-not-exist.example', cache)
        return got, cache

    got, cache = asyncio.run(go())
    assert got is False
    assert cache == {'this-name-does-not-exist.example': False}, 'the answer was not remembered'


def test_a_resolver_that_does_not_answer_keeps_the_candidate():
    """None, not False, when the lookup fails for any reason other than the name not being there:
    a resolver that did not answer has shown nothing, and losing a real locale mirror is the
    expensive direction."""
    async def go():
        async def hang(*a, **k):
            await asyncio.sleep(10)

        loop = asyncio.get_running_loop()
        loop.getaddrinfo = hang
        return await LA._resolves('es.x.org', {}, timeout=0.01)

    assert asyncio.run(go()) is None


def test_a_batch_asks_each_origin_for_robots_once():
    """The cache was per audit, so a run over ten thousand sites re-fetched the same file for every
    one of them, and every site also asked eight locale subdomains of its own host."""
    async def go():
        LA.clear_robots_cache()
        plain = _RobotsClient('User-agent: *\nDisallow: /private\n')
        ctx = type('C', (), {'request': plain})()
        token = LA._BATCH_ROBOTS.set(LA._ROBOTS_CACHE)
        try:
            cache = LA._BATCH_ROBOTS.get()
            for u in ('https://x.org/a', 'https://x.org/b', 'https://x.org/private'):
                await LA._robots_allowed(ctx, u, cache)
        finally:
            LA._BATCH_ROBOTS.reset(token)
            LA.clear_robots_cache()
        return plain.asked

    asked = asyncio.run(go())
    assert asked == ['https://x.org/robots.txt'], asked


def test_an_audit_on_its_own_does_not_read_another_audit_s_robots():
    """Outside a batch the cache is the audit's own, so nothing one site was told can answer for
    another. The batch cache is opt-in and a single audit never sets it."""
    assert LA._BATCH_ROBOTS.get() is None


def test_the_audit_aims_to_finish_before_the_caller_cancels_it():
    """The audit's deadline and the caller's cancel used to be the same instant, so any step that
    overran by a second turned a site that had been read into `unreachable`."""
    async def go():
        return LA._audit_extras(300, True)['deadline'] - asyncio.get_running_loop().time()

    left = asyncio.run(go())
    assert 300 - LA.AUDIT_GRACE - 1 <= left <= 300 - LA.AUDIT_GRACE + 1


class _NeverAnswers:
    """A browser whose every address answers with an empty body, however it is asked."""

    def __init__(self):
        self.reads = []
        self.pages = {}
        self.contexts = []
        self.plain = None

    async def new_context(self, **k):
        c = _MapCtx(self)
        self.contexts.append(c)
        return c

    async def close(self):
        return None


def test_only_the_first_home_address_is_tried_when_the_clock_is_spent(monkeypatch):
    """Six addresses at up to forty seconds each is longer than most caps, and all six were tried
    however little time was left, so an audit could be cancelled inside the home read with nothing
    to show for it. The first is always asked for; the rest are begun only if there is time."""
    async def no_sleep(_s):
        return None

    monkeypatch.setattr(LA.asyncio, 'sleep', no_sleep)

    async def go():
        b = _NeverAnswers()
        deadline = asyncio.get_running_loop().time() + 1
        return b, await LA._audit_async('https://x.org', browser=b, deadline=deadline)

    b, r = asyncio.run(go())
    assert r.verdict == 'unreachable'
    assert len(b.reads) == 1, b.reads
    assert b.reads[0] == 'https://x.org'
    assert all(c.closed for c in b.contexts), 'a context was left open'


def test_every_address_is_tried_when_there_is_time():
    """The guard is a floor on the clock and not a new limit on how many addresses are tried."""
    async def go():
        b = _NeverAnswers()
        deadline = asyncio.get_running_loop().time() + 6000
        return b, await LA._audit_async('https://x.org', browser=b, deadline=deadline)

    b, r = asyncio.run(go())
    assert len(b.reads) == 2 * len(LA._variants('https://x.org'))


# ---------------------------------------------------------------- the click step, 2026-08-01
#
# `_read` ends by deleting WIDGET_SEL, and on the Google Translate and GTranslate families WIDGET_SEL
# is the switcher, so the read that positioned the throwaway context deleted the controls
# `_click_language_controls` then went looking for: two clickable Spanish candidates before the strip
# and none after, measured on a live page.
#
# The repair is two-sided and the second side is not optional. Skipping the strip on the positioning
# read alone would hand the widget's own menu, a list of language autonyms, to `languages_in` one
# step later, which is the reading the strip was added to stop. So the click step strips the page
# itself, after the click has settled and before anything is read.
#
# The ORDER inside the loop is what these pin. tests/test_live.py runs the same two cases against a
# real DOM, where the strip is JavaScript that removes nodes and the click is a click; the fakes here
# can only pin the wiring, which is what a later edit is most likely to get wrong.


class _StripSpyPage:
    """A page that records the argument of every evaluate() a read makes."""

    def __init__(self):
        self.evaluated = []
        self.mouse = _FakeMouse()
        self.url = 'https://x.org/'

    async def goto(self, url, wait_until=None, timeout=None):
        self.url = url
        return _FakeResp(200)

    async def wait_for_timeout(self, ms):
        return None

    async def inner_text(self, sel):
        return 'A page of ordinary English text about the work of the organization.'

    async def content(self):
        return '<html><body>hello</body></html>'

    async def evaluate(self, script, arg=None):
        self.evaluated.append(arg)
        return None

    @property
    def stripped(self):
        return LA.WIDGET_SEL in self.evaluated


def test_a_read_still_takes_the_widget_out_of_the_page_it_returns():
    """The default is unchanged, because every caller that uses the returned text needs it: the
    widget's menu is a list of language autonyms and reading one counted a menu as Russian."""
    pg = _StripSpyPage()
    asyncio.run(LA._read(pg, 'https://x.org/'))
    assert pg.stripped


def test_a_read_asked_not_to_strip_leaves_the_switcher_in_the_page():
    pg = _StripSpyPage()
    asyncio.run(LA._read(pg, 'https://x.org/', strip=False))
    assert not pg.stripped


def test_the_click_context_is_the_only_read_taken_without_the_strip(monkeypatch):
    """One call site, and the one that throws the text away. Anywhere else this would put the
    widget's menu into a reading."""
    real = LA._read
    seen = []

    async def spy(page, url, *a, **k):
        seen.append((url, k.get('strip', True)))
        return await real(page, url, *a, **k)

    monkeypatch.setattr(LA, '_read', spy)
    b = _MapBrowser({'https://x.org/': _page('We run classes, legal clinics and a food pantry '
                                             'for families in the neighborhood.')})
    asyncio.run(LA._audit_async('https://x.org/', browser=b))
    assert [u for u, s in seen if not s] == ['https://x.org/'], seen
    assert len(seen) > 1, 'the interior crawl never ran, so this proves nothing about the rest'


class _LangControl:
    """A control whose label is a language name, which is what the click step goes looking for."""

    def __init__(self, page, label):
        self._page, self._label = page, label

    async def inner_text(self):
        return self._label

    async def click(self, timeout=None):
        self._page.calls.append('click')


class _ClickDomPage:
    """A page for `_click_language_controls` that records what it was asked, in order.

    `before` is what the body says with the widget still in it, `after` what it says once the
    widget's nodes are gone. Which one this answers with depends on whether the strip has run, which
    is the whole question the ordering decides.
    """

    def __init__(self, before, after, label='Espanol'):
        self.calls = []
        self.url = 'https://x.org/'
        self.before, self.after, self._label = before, after, label
        self._stripped = False

    def _text(self):
        return self.after if self._stripped else self.before

    async def query_selector_all(self, sel):
        return [_LangControl(self, self._label)]

    async def wait_for_timeout(self, ms):
        self.calls.append('wait')

    async def inner_text(self, sel):
        self.calls.append('read')
        return self._text()

    async def evaluate(self, script, arg=None):
        if arg == LA.WIDGET_SEL:
            self.calls.append('strip')
            self._stripped = True
            return None
        self.calls.append('chrome')          # `_main_text`, which answers with the text it laid out
        return self._text()

    async def goto(self, url, wait_until=None, timeout=None):
        self.calls.append('back')
        self.url = url
        return _FakeResp(200)


_HOME_EN = ('We run English classes, legal clinics and a food pantry for families in the '
            'neighborhood, and the office is open on weekdays.')
_MENU_ES = ('Ofrecemos clases de ingles y una despensa de alimentos para las familias de la '
            'comunidad. La oficina esta abierta de lunes a viernes y no es necesario pedir una '
            'cita.')


def test_the_widget_is_taken_out_after_the_click_and_before_the_page_is_read():
    """Both halves of the ordering in one assertion. Later than the click, because the control being
    clicked is part of the widget; earlier than the read, because everything read here is handed to
    `languages_in`."""
    page = _ClickDomPage(_MENU_ES + ' ' + _HOME_EN, _HOME_EN)
    out, _dead, _stuck = asyncio.run(LA._click_language_controls(page, 'nothing like the page', 'https://x.org/'))
    assert page.calls.index('click') < page.calls.index('strip') < page.calls.index('read')
    assert out == [], 'a language was read off the widget furniture'


def test_a_language_the_clicked_page_really_carries_is_still_reported():
    """The strip removes the widget and not the page. A control that produces Spanish still reports
    Spanish, which is the evidence this whole step exists to collect."""
    page = _ClickDomPage('Select Language ' + _MENU_ES, _MENU_ES)
    out, _dead, _stuck = asyncio.run(LA._click_language_controls(page, _HOME_EN, 'https://x.org/'))
    assert [(lg, label) for lg, _u, label, _q in out] == [('Spanish', 'Espanol')]
    assert 'back' in page.calls, 'the loop did not navigate back to the address it started from'


def test_the_guard_on_a_control_that_changed_nothing_still_fires():
    """`home_text` came from a stripped read. An unstripped `after` carries the widget's menu on top
    of the page, so it could never compare equal, and the early exit for a control that did nothing
    would quietly stop working. The strip has to be the earlier of the two."""
    page = _ClickDomPage('Select Language Espanol Francais ' + _HOME_EN, _HOME_EN)
    assert page.before[:400] != _HOME_EN[:400], 'the unstripped page has to differ, or this is empty'
    out, _dead, _stuck = asyncio.run(LA._click_language_controls(page, _HOME_EN, 'https://x.org/'))
    assert out == []
    assert 'chrome' not in page.calls and 'back' not in page.calls, \
        'the guard did not fire: the page was read and navigated away from anyway'


# ---- a control that opens a new tab, and one that starts a download (F5)
#
# A window.open switcher puts its result in a NEW tab and a document link starts a download; both
# leave THIS page unchanged, so the same-page comparison recorded a dead control and drove the site
# to machine_translate_error or english_only on text it plainly serves. The fix catches the tab and
# the download around the click. These stand up the two events the way Playwright fires them.


class _EventBus:
    def __init__(self):
        self._handlers = {}

    def on(self, event, cb):
        self._handlers.setdefault(event, []).append(cb)

    def remove_listener(self, event, cb):
        if cb in self._handlers.get(event, []):
            self._handlers[event].remove(cb)

    def fire(self, event, arg):
        for cb in list(self._handlers.get(event, [])):
            cb(arg)


class _PopupTab:
    """The new tab a window.open control lands on: it carries the translated content."""

    def __init__(self, text, url='https://translate.example/x'):
        self._text, self.url, self.closed = text, url, False

    async def wait_for_load_state(self, state=None, timeout=None):
        return None

    async def inner_text(self, sel):
        return self._text

    async def evaluate(self, *a, **k):
        return None                # _main_text and the widget hide both fall through

    async def close(self):
        self.closed = True


class _NewTabControl:
    def __init__(self, page, label, download=False):
        self._page, self._label, self._download = page, label, download

    async def inner_text(self):
        return self._label

    async def click(self, timeout=None):
        if self._download:
            self._page.fire('download', object())
        else:
            self._page.context.fire('page', self._page.new_tab)


class _NewTabClickPage(_EventBus):
    """A click page whose one control opens a new tab or starts a download; the page never changes."""

    def __init__(self, home, new_tab=None, download=False):
        super().__init__()
        self.url = 'https://x.org/'
        self._home, self.new_tab, self._download = home, new_tab, download
        self.context = _EventBus()

    async def query_selector_all(self, sel):
        return [_NewTabControl(self, 'Espanol', download=self._download)]

    async def wait_for_timeout(self, ms):
        return None

    async def inner_text(self, sel):
        return self._home          # unchanged, whatever the control did

    async def evaluate(self, *a, **k):
        return None

    async def goto(self, url, wait_until=None, timeout=None):
        self.url = url
        return _FakeResp(200)


def test_a_control_that_opens_a_same_site_tab_is_read_from_the_tab():
    tab = _PopupTab(_MENU_ES, url='https://x.org/es')          # the org's own page, in a new tab
    page = _NewTabClickPage(_HOME_EN, new_tab=tab)
    out, dead, _stuck = asyncio.run(LA._click_language_controls(page, _HOME_EN, 'https://x.org/'))
    assert [(lg, label) for lg, _u, label, _q in out] == [('Spanish', 'Espanol')]
    assert dead == [], 'the tab carried the reading; this page is not a dead control'
    assert tab.closed, 'the tab was left open'


def test_a_control_that_opens_a_cross_site_tab_is_not_read_as_the_orgs_content():
    """A window.open onto someone else's host, a Google Translate tab or an external site, is not the
    organization's writing, so its language is not recorded and this page is not marked dead."""
    tab = _PopupTab(_MENU_ES, url='https://translate.google.com/x')
    page = _NewTabClickPage(_HOME_EN, new_tab=tab)
    out, dead, _stuck = asyncio.run(LA._click_language_controls(page, _HOME_EN, 'https://x.org/'))
    assert out == [], 'a cross-site tab was read as the org content'
    assert dead == [], 'nor is it a dead control'
    assert tab.closed


def test_a_control_that_starts_a_download_is_not_a_dead_control():
    page = _NewTabClickPage(_HOME_EN, download=True)
    out, dead, _stuck = asyncio.run(LA._click_language_controls(page, _HOME_EN, 'https://x.org/'))
    assert out == [] and dead == [], \
        'a download is a document the crawl records and the codebook does not judge, not a dead control'


# ---------------------------------------------------------------- reachability, 2026-08-01
#
# A collapsed dropdown answers `inner_text` with the labels of the items it is hiding, so a language
# a visitor cannot see is queued as a candidate; `el.click(timeout=3000)` then waits three seconds
# for it to become visible and gives up. 128 of the 157 candidates on the 53 Google Translate and
# GTranslate sites of the two development regression frames are in that state, and on 14 of the 20
# sites that have a candidate at all, every one of them is.
#
# The answer has two halves and the second is not optional. Skipping what cannot be clicked stops
# paying for it; opening the container first is what keeps a real switcher from being dropped, and
# on 12 of those 14 the thing that opens it is the nearest ancestor the visitor can see.
#
# These pin the wiring. tests/test_live.py runs the same shapes against a real DOM, where visibility
# is layout and opening is a click.


class _Handle:
    """A JSHandle, which is what evaluate_handle answers with."""

    def __init__(self, el):
        self._el = el

    def as_element(self):
        return self._el


class _Opener:
    """The ancestor a hidden candidate sits inside. Clicking it makes the candidate reachable."""

    def __init__(self, page, opens=True):
        self._page, self._opens, self.marked = page, opens, False

    async def click(self, timeout=None):
        self._page.calls.append('open')
        if not self._opens:
            raise RuntimeError('nothing happened')

    async def evaluate(self, script, arg=None):
        self.marked = True          # the loop recording that this opener does not open


class _Candidate:
    """A control whose label names a language, with the two answers a click waits on."""

    def __init__(self, page, label='Espanol', visible=True, tag='a', href=None,
                 opener=None, value=None, opens_to_visible=True):
        self._page, self._label, self._tag, self._href = page, label, tag, href
        self.visible, self.opener, self.value = visible, opener, value
        self._opens_to_visible = opens_to_visible
        self.clicked = 0

    async def inner_text(self):
        return self._label

    async def evaluate(self, script, arg=None):
        return self._tag.upper()

    async def is_visible(self):
        return self.visible

    async def bounding_box(self):
        return {'x': 0, 'y': 0, 'width': 10, 'height': 10} if self.visible else None

    async def get_attribute(self, name):
        return {'href': self._href, 'value': self.value}.get(name)

    async def evaluate_handle(self, script):
        if 'closest' in script:
            return _Handle(self._page.select)
        if self.opener is not None and self._opens_to_visible:
            # the loop is asking for the opener; clicking it makes this reachable
            self.visible = True
        return _Handle(self.opener)

    async def click(self, timeout=None):
        self.clicked += 1
        self._page.calls.append('click')


class _Select:
    """A <select> switcher: not clicked, driven."""

    def __init__(self, page, options, current='', visible=True):
        self._page, self._options, self._current = page, options, current
        self.visible = visible
        self.picked = []
        self.used = False

    async def is_visible(self):
        return self.visible

    async def bounding_box(self):
        return {'x': 0, 'y': 0, 'width': 80, 'height': 20} if self.visible else None

    async def input_value(self):
        return self._current

    async def eval_on_selector_all(self, sel, script):
        return [list(o) for o in self._options]

    async def evaluate(self, script, arg=None):
        was, self.used = self.used, True
        return was

    async def select_option(self, value=None, timeout=None):
        self.picked.append(value)
        self._page.calls.append('select')

    async def click(self, timeout=None):
        self._page.calls.append('click')


class _ReachPage(_ClickDomPage):
    """`_ClickDomPage` with the candidates named by the test rather than one fixed control."""

    def __init__(self, before, after, candidates, select=None):
        _ClickDomPage.__init__(self, before, after)
        self.candidates, self.select, self.wanted = candidates, select, ''

    async def query_selector_all(self, sel):
        self.wanted = sel
        return list(self.candidates)

    async def evaluate(self, script, arg=None):
        # the parent records both of these as one thing, because to it the widget going out of the
        # text is the whole question; here the two directions have to be told apart
        if script is LA._WIDGET_HIDE_JS:
            self.calls.append('hide')
        elif script is LA._WIDGET_SHOW_JS:
            self.calls.append('show')
        return await _ClickDomPage.evaluate(self, script, arg)


def _run(page, home=_HOME_EN, **kw):
    return asyncio.run(LA._click_language_controls(page, home, 'https://x.org/', **kw))[0]


def test_the_query_asks_for_the_elements_a_select_switcher_is_built_from():
    page = _ReachPage(_HOME_EN, _HOME_EN, [])
    _run(page)
    for tag in ('a', 'button', 'span', 'li', 'div', 'select', 'option'):
        assert tag in page.wanted.split(','), tag


def test_a_candidate_a_click_cannot_reach_is_not_clicked():
    """Three seconds of waiting for a control that will never become visible, per candidate. The
    answer is one round trip."""
    page = _ReachPage(_HOME_EN, _HOME_EN, [])
    hidden = _Candidate(page, visible=False)
    page.candidates = [hidden]
    assert _run(page) == []
    assert hidden.clicked == 0
    assert 'click' not in page.calls


def test_a_hidden_candidate_is_reached_by_opening_the_control_it_sits_in():
    """A collapsed dropdown is a switcher a visitor uses, so it is opened rather than dropped."""
    page = _ReachPage('Select Language ' + _MENU_ES, _MENU_ES, [])
    opener = _Opener(page)
    page.candidates = [_Candidate(page, visible=False, opener=opener)]
    out = _run(page)
    assert page.calls.index('open') < page.calls.index('click')
    assert [(lg, label) for lg, _u, label, _q in out] == [('Spanish', 'Espanol')]


def test_an_opener_that_opens_nothing_is_not_asked_twice():
    """Otherwise a fourteen-item switcher whose opener does not open costs its timeout fourteen
    times, which is worse than the defect being fixed."""
    page = _ReachPage(_HOME_EN, _HOME_EN, [])
    opener = _Opener(page, opens=False)
    page.candidates = [_Candidate(page, visible=False, opener=opener, opens_to_visible=False)]
    assert _run(page) == []
    assert opener.marked, 'the loop did not record that this opener opens nothing'
    assert page.calls.count('click') == 0


def test_a_candidate_that_is_a_link_to_another_document_is_not_opened_into():
    """This step is for a control with no link behind it; a link is the crawl's business. On one
    refugee resettlement organization's local office page the collapsed container is an accordion of
    PDF handouts, one of them named for Arabic, and opening it to click a PDF is not reading a
    switcher."""
    page = _ReachPage(_HOME_EN, _HOME_EN, [])
    opener = _Opener(page)
    page.candidates = [_Candidate(page, label='What is Trauma Arabic', visible=False,
                                  href='https://x.org/trauma-arabic.pdf', opener=opener)]
    assert _run(page) == []
    assert 'open' not in page.calls and 'click' not in page.calls


def test_a_select_switcher_is_driven_and_not_clicked():
    """Chromium draws a select with the platform's own widget, an option has no box, and what swaps
    the page is the change event. Twenty of the 53 sites measured carry one, and eighteen of those
    carry nothing else."""
    page = _ReachPage('Select Language ' + _MENU_ES, _MENU_ES, [])
    sel = _Select(page, [('Select Language', ''), ('English', 'en'), ('Espanol', 'es')])
    page.select = sel
    page.candidates = [_Candidate(page, label='Espanol', tag='option', value='es', visible=False)]
    out = _run(page)
    assert sel.picked == ['es']
    assert 'click' not in page.calls
    assert [(lg, label) for lg, _u, label, _q in out] == [('Spanish', 'Espanol')]


def test_one_option_of_a_select_is_taken_and_not_eight():
    """A select is ONE control however many languages it lists. A Google Translate combo carries 249
    options, of which 26 name a language this package knows, and taking eight of them would spend
    the whole budget on one widget."""
    page = _ReachPage('Select Language ' + _HOME_EN, _HOME_EN, [])
    sel = _Select(page, [('Select Language', ''), ('Espanol', 'es'), ('Francais', 'fr'),
                         ('Korean', 'ko')])
    page.select = sel
    page.candidates = [_Candidate(page, label=t, tag='option', value=v, visible=False)
                       for t, v in (('Espanol', 'es'), ('Francais', 'fr'), ('Korean', 'ko'))]
    _run(page)
    assert sel.picked == ['es']


def test_an_option_that_is_already_selected_is_not_taken():
    """Selecting what is selected fires no change event, so it swaps nothing and costs a settle."""
    page = _ReachPage(_HOME_EN, _HOME_EN, [])
    sel = _Select(page, [('English', 'en'), ('Espanol', 'es')], current='es')
    page.select = sel
    page.candidates = [_Candidate(page, label='Espanol', tag='option', value='es', visible=False)]
    assert _run(page) == []
    assert sel.picked == []


def test_a_select_a_click_cannot_reach_is_not_driven():
    """The same measurement as the click: on the six sites whose language select is not rendered,
    select_option waits its whole timeout and swaps nothing."""
    page = _ReachPage(_HOME_EN, _HOME_EN, [])
    sel = _Select(page, [('English', 'en'), ('Espanol', 'es')], visible=False)
    page.select = sel
    page.candidates = [_Candidate(page, label='Espanol', tag='option', value='es', visible=False)]
    assert _run(page) == []
    assert sel.picked == []


def test_the_budget_counts_controls_worked_and_not_candidates_seen():
    """A candidate that is skipped costs a round trip and no wait, so spending the budget on it
    would be spending it on nothing."""
    page = _ReachPage('Select Language ' + _MENU_ES, _MENU_ES, [])
    page.candidates = ([_Candidate(page, label='Francais', visible=False) for _ in range(8)] +
                       [_Candidate(page, label='Espanol', visible=True)])
    out = _run(page, limit=1)
    assert [(lg, label) for lg, _u, label, _q in out] == [('Spanish', 'Espanol')]


def test_the_widget_is_put_back_when_the_control_changed_nothing():
    """The strip inside the loop REMOVED the widget's nodes, so from the first candidate on, every
    remaining candidate answered `Element is not attached to the DOM`: six of six on one
    organization's site and five of five on another's. The navigation at the end of the
    loop has always had that effect, but it only runs on a control that changed the page. A control
    that changed nothing leaves the document standing, and the next control in the same switcher has
    to still be there to work."""
    page = _ReachPage('Select Language Espanol Francais ' + _HOME_EN, _HOME_EN, [])
    first = _Candidate(page, label='Francais')
    second = _Candidate(page, label='Espanol')
    page.candidates = [first, second]
    _run(page)
    assert first.clicked == 1 and second.clicked == 1, \
        'the second control in the same switcher was never worked'
    # the ordering, which is why the second click reaches anything: out of the text for the
    # read, back into the document before the next control is worked
    assert page.calls.index('hide') < page.calls.index('show') < page.calls.index('click', 1)
    assert 'back' not in page.calls, 'neither control changed the page, so neither may navigate'


# ---- an href that is not an address
#
# Since Python 3.11 `urlsplit` and `urljoin` RAISE `ValueError` on a bracketed netloc that is not an
# IP literal, and `<a href="//[telephone_number_link]/...">` is exactly that. Every address
# collector in this package ran `urljoin` unguarded, so one such link on one page raised out of the
# middle of `_crawl` and took the whole audit of that site with it, before any reading was judged.
# A site in the census render store publishes it; a corpus pass crashed on it on 2026-08-04 after
# 28,801 captures, which is where this came from.
_UNPARSEABLE = ('<html><body>'
                '<a href="//[telephone_number_link]/call">Call us</a>'
                '<a href="/servicios">Servicios</a>'
                '<link rel="alternate" hreflang="es" href="//[telephone_number_link]/es"/>'
                '<p>The center offers legal advice and classes for adults.</p>'
                '</body></html>')


@pytest.mark.parametrize('call', [
    lambda: LA._interior(_UNPARSEABLE, 'https://x.org/'),
    lambda: LA._routes(_UNPARSEABLE, 'https://x.org/'),
    lambda: LA.declared_languages(_UNPARSEABLE, 'https://x.org/'),
    lambda: LA.switcher_languages(_UNPARSEABLE),
    lambda: LA._same_site('https://x.org/', 'https://[telephone_number_link]/x'),
])
def test_a_link_that_cannot_be_parsed_is_not_a_link(call):
    """Every collector answers rather than raising. A link nothing can parse is dropped, which is
    the same answer they already give a `mailto:`, a fragment and an address off the site."""
    call()


def test_the_audit_reads_a_site_whose_page_carries_an_unparseable_href():
    """The site is still read and still judged."""
    b = _MapBrowser({'https://x.org': (_UNPARSEABLE,
                                       'The center offers legal advice and classes for adults.',
                                       200),
                     'https://x.org/servicios': _page(
                         'El centro ofrece asesoria legal y clases para adultos que necesitan '
                         'ayuda con una solicitud o con documentos de inmigracion en el condado.')})
    r = asyncio.run(LA._audit_async('https://x.org', browser=b))
    assert r.verdict == 'true_multilingual' and r.languages == ['Spanish']
    assert 'https://x.org/servicios' in b.reads


def test_a_dead_control_is_recorded_rather_than_dropped():
    """A clicked control that changes nothing is rule 16's own observation, and until 2026-08-06
    it was watched in flight and thrown away: one Chinese-American community association renders a
    Chinese control whose click changes not one character, the human coder wrote "button doesn't
    work" by hand, and the audit had seen exactly that and said nothing. The dead list is the
    record, an English-labelled control stays out of it because English coming back IS that control
    working, and the note sentence is the one constant three verdict derivations read rule 16 off."""
    page = _ClickDomPage(_HOME_EN, _HOME_EN, label='Chinese')
    worked, dead, _stuck = asyncio.run(LA._click_language_controls(page, _HOME_EN, 'https://x.org/'))
    assert worked == [] and dead == [('Chinese', 'https://x.org/')]
    page = _ClickDomPage(_HOME_EN, _HOME_EN, label='English')
    worked, dead, _stuck = asyncio.run(LA._click_language_controls(page, _HOME_EN, 'https://x.org/'))
    assert worked == [] and dead == []
    # the note channel: a dead control with a widget and nothing produced is rule 16's class,
    # and the advertised-route observation keeps rule 15's, since the split of 2026-08-09
    ev = [LA.Evidence('translation_plugin', 'https://x.org/', 'gtranslate', '')]
    assert LA.ROUTE_ENGLISH_NOTE not in LA.CONTROL_DEAD_NOTE
    assert LA.CONTROL_DEAD_NOTE not in LA.ROUTE_ENGLISH_NOTE
    assert LA.verdict_for(ev, 'Google Translate', route_was_english=True) == 'english_only'
    assert 15 in LA.verdict_rules(ev, 'Google Translate', route_was_english=True)
    assert LA.verdict_for(ev, 'Google Translate', control_dead=True) == LA.MT_ERROR
    assert 16 in LA.verdict_rules(ev, 'Google Translate', control_dead=True)

def test_a_dead_control_reaches_machine_translate_error_without_a_real_browser(monkeypatch):
    """The whole wire of the fifth class, in the default suite for the first time: the dead list
    becomes evidence, the evidence sets the note, the note sets the flag, and the flag is the
    class. Until this test, deleting the three lines that append the note broke only a live-marked
    test that CI never runs."""
    async def fake_click(page, home_text, base, limit=8, exclude=(), deadline=None):
        return [], [('Chinese', 'https://x.org/')], []

    monkeypatch.setattr(LA, '_click_language_controls', fake_click)
    b = _MapBrowser({'https://x.org/': _page(
        _HOME_EN + ' <div id="google_translate_element"></div>'
        '<script src="//translate.google.com/translate_a/element.js"></script>')})
    r = asyncio.run(LA._audit_async('https://x.org/', browser=b))
    assert r.machine_translation, 'the fixture has to name a vendor or there is no widget to fail'
    assert LA.CONTROL_DEAD_NOTE in r.note
    assert r.verdict == LA.MT_ERROR
    assert 16 in r.rules and 15 not in r.rules


def test_a_stuck_control_is_evidence_and_moves_nothing_without_a_real_browser(monkeypatch):
    """The stuck list's caller contract, in the default suite: an entry becomes evidence saying the
    control could not be operated, with no language and no rule number, and the class stands on
    what else was found."""
    async def fake_click(page, home_text, base, limit=8, exclude=(), deadline=None):
        return [], [], [('Arabic', 'https://x.org/')]

    monkeypatch.setattr(LA, '_click_language_controls', fake_click)
    b = _MapBrowser({'https://x.org/': _page(
        _HOME_EN + ' <div id="google_translate_element"></div>'
        '<script src="//translate.google.com/translate_a/element.js"></script>')})
    r = asyncio.run(LA._audit_async('https://x.org/', browser=b))
    say = [e for e in r.evidence if 'could not be operated' in LA._ev_quote(e)]
    assert say, 'the abandoned control left no trace on the record'
    assert all(not LA._ev_lang(e) and not LA._ev_recorded(e, 'rules') for e in say)
    assert r.verdict == 'machine_translate', 'recording the control may not move the class'


def test_the_two_note_sentences_are_not_substrings_of_each_other():
    """Three call sites derive both flags by substring-testing one note, so if either sentence ever
    contains the other, every dead control also sets the route flag and rule 16 collapses back into
    rule 15. The old assertion here compared a constant to a hardcoded copy of itself."""
    assert LA.ROUTE_ENGLISH_NOTE not in LA.CONTROL_DEAD_NOTE
    assert LA.CONTROL_DEAD_NOTE not in LA.ROUTE_ENGLISH_NOTE


def test_every_name_in_all_resolves():
    """`from langaccess import MT_ERROR` raised ImportError for half a day because the name was in
    `__all__` and not imported; the fix was recorded as "checked mechanically", and a check that is
    not a test does not keep checking."""
    import langaccess
    missing = [n for n in langaccess.__all__ if not hasattr(langaccess, n)]
    assert not missing, missing
