# -*- coding: utf-8 -*-
"""The gate for a change that moves a reading without moving a constant.

`tests/test_engineering.py` freezes every constant the instrument reads. That gate cannot see one
whole class of change, and the class is not hypothetical. On 2026-08-01 a change scoped the
unique-word test to the window the function words fired in instead of to the whole page. It moved
readings on seven sites and it introduced no constant and altered none: what it changed was WHERE
PARA_WINDOW is applied. A fingerprint over values is blind to that by construction, and so is any
fingerprint over values, however complete.

WHAT THIS IS. Thirty-one synthetic sites, in `tests/fixtures/reading_corpus.json`, each audited
through the same fake browser the rest of the suite uses, with the whole reading recorded in
`tests/fixtures/reading_expected.json`: the verdict, the languages, the two axes, the machine
translation, the codebook rules, the pages read, the note, the switcher, and every piece of evidence
with its mechanism, address, language, rung, authorship, server flags, rules and quoted text. A
single sha256 over all thirty-one sits in `READINGS` below and moves when any of that moves.

The count in this paragraph has been wrong before, and it is derived nowhere: it is prose beside a
corpus that grows. `test_the_corpus_covers_the_classes_it_was_built_from` is what actually holds the
corpus to its job, and it is a statement about what the fixtures REACH rather than how many there
are.

WHY THIS AND NOT A HASH OVER THE SOURCE OF THE FUNCTIONS THAT DECIDE A READING. That was the other
candidate and it is more precise about WHERE a change is. It is also noisy in the one way that
matters: a comment edit, a rename, a black run and a docstring fix all trip it, and every one of
those trips teaches the person holding the hash to re-record without reading, which is the habit
this whole file exists to prevent. This gate fires only when a reading actually changed, so a
failure is always worth reading. It is also what the freeze is FOR. The instrument's claim is about
readings, and a reading is the thing a validation figure is computed from.

WHAT IT CANNOT CATCH, which is the honest half.

  Anything these sites do not exercise. A change to the Somali function words, to the
  sitemap reader, to the time budget, to the boilerplate cut or to the batch driver moves nothing
  here. The constant gate covers the first of those and nothing covers the rest; the way to close a
  gap is to add the site that shows it, which is why
  `test_the_corpus_covers_the_classes_it_was_built_from` states what the corpus is currently known
  to reach and fails when that shrinks.

  Anything the fake browser cannot do. These pages are served from a map, so no capture here goes
  through a real layout, a real click on a collapsed switcher, a real challenge wait, a real DNS
  answer or a real robots.txt. OPEN_CLICK_MS and OPEN_SETTLE_MS, the two constants missed on
  2026-08-01, decide a reading on a live site and decide nothing here. Nor does the chrome removal:
  from 0.2.0 it decides only what a page says after a language control is CLICKED, this corpus's
  browser has nothing to click, and the selector is held against a second implementation of the
  script in `test_the_chrome_selector_still_names_what_it_was_written_to_name` while the script
  itself runs against a real browser in `tests/test_live.py`.

  A change that moves a reading on a real site while these stay put. Thirty-one sites is
  thirty-one sites. This says a change is not inert; it never says a change is safe. Three changes
  of 2026-08-05 are the case in point, and none of them moved anything here until fixtures were
  written for the shapes they are about: the vendor change needed two, the declaration work needed
  two more because no fixture of the twenty-seven carried an `hreflang` alternate at all, and the
  tag stripper needed two more again because no fixture of the twenty-nine carried an attribute
  value with a literal `>` in it.

  A change to the corpus itself. The fixtures are inputs and nothing checks them against the web,
  because they are not from the web.

WHY THE PAGES ARE INVENTED. The census capture is deliberately not distributed, so nothing in it can
be committed here. Every page below was written for this file: the addresses are all under `.example`
except two that name a platform on purpose, and the prose in every fixture, in every language any of
them is written in, is made up. `test_every_address_in_the_corpus_is_a_reserved_one` keeps it that
way.
"""
import asyncio
import hashlib
import io
import json
import os
import re
from html.parser import HTMLParser

import pytest

from langaccess import core as LA
from test_engineering import _MapBrowser, _PlainClient

_FIXTURE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fixtures')
_CORPUS_PATH = os.path.join(_FIXTURE_DIR, 'reading_corpus.json')
_EXPECTED_PATH = os.path.join(_FIXTURE_DIR, 'reading_expected.json')

with io.open(_CORPUS_PATH, encoding='utf-8') as _fh:
    CORPUS = json.load(_fh)
CORPUS_BY_NAME = {f['name']: f for f in CORPUS}

# The two hosts in the corpus that are not `.example`. Both are named because the reading turns on
# the host itself: DIRECTORY_HOST and SOCIAL_HOST are lists of real platforms, and a fixture for
# the directory stop and codebook rule 1 that used an invented host would test nothing. Neither
# carries a page
# from either platform; the body of both is the same invented English paragraph as the rest.
_PLATFORM_HOSTS = ('www.guidestar.org', 'www.facebook.com')


# ------------------------------------------------------------- a second reading of the chrome script
#
# WHY THIS EXISTS. The defect that motivated the whole gate was invisible to an audit of these
# fixtures: CHROME_SEL written without the leading `a` matches `id="wp--skip-link--target"`, the id
# WordPress block themes put on the `<main>` that wraps the page, and the selector then hid the
# document and returned the empty string. Substituting the defective selector into a run of this
# file moved nothing, because every fake page here answers `evaluate` with None.
#
# WHAT THE SCRIPT STILL DECIDES. Not a page reading, from 0.2.0 on: `_read` takes that off the
# served document through `_page_text`, which is the function `rejudge` reads a stored page with,
# and it calls no script. What is left is the text a page reports AFTER a language control has been
# clicked, which `_click_language_controls` asks `_main_text` for, and the defect above is still
# reachable there: a hidden document is a control read as dead, which is rule 16.
#
# WHAT IS REAL HERE AND WHAT IS NOT. The four constants the script is called with arrive from
# `langaccess.core`, and the skip-link phrase list is read out of `_CHROME_JS` itself, so the things
# a change would move are the things this reads. The ALGORITHM is a second implementation of the
# same three steps and can drift from the JavaScript; what it is here to answer is which elements a
# selector reaches, which is where the defect was. The JavaScript is exercised against a real
# browser in `tests/test_live.py`, where a click is a click.
_SKIP_PHRASES = re.compile(re.search(r'const SKIP = /(.*?)/i;', LA._CHROME_JS).group(1), re.I)
_VOID = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'param',
         'source', 'track', 'wbr'}
# `head` joins the raw-text elements because `inner_text` is taken on the body and a title is not
# body text. An unterminated `<style>` needs nothing here: HTMLParser puts the parser into character
# data mode on the opening tag, exactly as a browser does, so the rest of the document is stylesheet.
_RAW = {'script', 'style', 'noscript', 'template', 'head'}
_BLOCK = {'address', 'article', 'aside', 'blockquote', 'body', 'div', 'dd', 'dl', 'dt', 'fieldset',
          'figcaption', 'figure', 'footer', 'form', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'header',
          'hr', 'li', 'main', 'nav', 'ol', 'p', 'pre', 'section', 'table', 'tr', 'ul'}
_SEL_TAG = re.compile(r'^([\w-]+)')
_SEL_ATTR = re.compile(r'\[\s*([\w-]+)\s*(?:([*^$]?=)\s*"([^"]*)"\s*)?\]')


class _Node:
    __slots__ = ('tag', 'attrs', 'children', 'parent')

    def __init__(self, tag, attrs=None, parent=None):
        self.tag, self.attrs, self.children, self.parent = tag, dict(attrs or {}), [], parent

    def walk(self):
        for c in self.children:
            if isinstance(c, _Node):
                yield c
                for g in c.walk():
                    yield g

    def find(self, tag):
        return next((n for n in self.walk() if n.tag == tag), None)

    def text(self):
        return ''.join(c if isinstance(c, str) else c.text() for c in self.children)


class _TreeParser(HTMLParser):
    def __init__(self):
        HTMLParser.__init__(self, convert_charrefs=True)
        self.root = _Node('#document')
        self._at = self.root

    def handle_starttag(self, tag, attrs):
        node = _Node(tag, attrs, self._at)
        self._at.children.append(node)
        if tag not in _VOID:
            self._at = node

    def handle_startendtag(self, tag, attrs):
        self._at.children.append(_Node(tag, attrs, self._at))

    def handle_endtag(self, tag):
        node = self._at
        while node is not self.root and node.tag != tag:
            node = node.parent
        if node is not self.root:
            self._at = node.parent

    def handle_data(self, data):
        self._at.children.append(data)


def _parse(html):
    parser = _TreeParser()
    parser.feed(html or '')
    return parser.root


def _select(root, selector):
    """The elements a comma-separated list of tag-and-attribute selectors reaches.

    Every clause CHROME_SEL and the skip-link rule are made of has this shape, and matching
    rather than naming keeps the selector under test the string the module holds.
    """
    out = []
    for one in selector.split(','):
        one = one.strip()
        if not one:
            continue
        named = _SEL_TAG.match(one)
        tag = named.group(1).lower() if named else ''
        clauses = [(m.group(1).lower(), m.group(2) or '', m.group(3) or '')
                   for m in _SEL_ATTR.finditer(one)]
        for node in root.walk():
            if tag and node.tag != tag:
                continue
            ok = True
            for name, op, want in clauses:
                got = node.attrs.get(name)
                if got is None or (op == '=' and got != want) \
                        or (op == '*=' and want not in got) \
                        or (op == '^=' and not got.startswith(want)) \
                        or (op == '$=' and not got.endswith(want)):
                    ok = False
                    break
            if ok and node not in out:
                out.append(node)
    return out


def _inner_text(node, hidden):
    """What a browser lays out, to the extent this matters: block elements break the line."""
    parts = []

    def go(n):
        if n in hidden or n.tag in _RAW:
            return
        block = n.tag in _BLOCK
        if block:
            parts.append('\n')
        for c in n.children:
            parts.append(c) if isinstance(c, str) else go(c)
        if block:
            parts.append('\n')

    go(node)
    lines = [' '.join(x.split()) for x in ''.join(parts).split('\n')]
    return '\n'.join(x for x in lines if x)


def _chrome_free_text(html, selector, min_items, share, label_max):
    root = _parse(html)
    hidden = set(_select(root, selector))
    for anchor in _select(root, 'a[href^="#"]'):
        label = anchor.text().strip()
        if len(label) <= 60 and _SKIP_PHRASES.match(label):
            hidden.add(anchor)
    for lst in _select(root, 'ul, ol'):
        items = [c for c in lst.children if isinstance(c, _Node) and c.tag == 'li']
        if len(items) < min_items:
            continue
        linky = 0
        for li in items:
            whole, link = li.text().strip(), li.find('a')
            if link is None or len(whole) > label_max:
                continue
            if len(link.text().strip()) >= len(whole) - 2:
                linky += 1
        if linky >= share * len(items):
            hidden.add(lst)
    return _inner_text(root.find('body') or root, hidden)


def _read(fixture):
    """Audit one fixture through the fake browser, with the resolver answered from the fixture.

    The audit invents eight locale subdomains per site and asks a real resolver whether each one
    exists. That is a live network call, so a recorded reading would depend on which machine ran it
    and on whether the resolver hijacks NXDOMAIN. It is answered here from the fixture's own address
    map instead, which is deterministic and still exercises the subdomain path for a fixture that
    declares one.

    Every fixture is read through the same browser. A fixture used to be able to ask for one that
    answered the chrome-removal script off its own markup, and that browser is gone with the reading
    it served: from 0.2.0 `_read` takes the page reading off the document through `_page_text` and
    calls no script at all, so the two browsers had become one and the flag decided nothing.
    """
    pages = {u: tuple(v) for u, v in fixture['pages'].items()}
    hosts = {u.split('/')[2] for u in pages}

    async def resolves(host, cache, timeout=None):
        return host in hosts

    real = LA._resolves
    LA._resolves = resolves
    try:
        browser = _MapBrowser(pages, plain=_PlainClient(dict(fixture.get('plain', {}))))
        return asyncio.run(LA._audit_async(fixture['url'], browser=browser))
    finally:
        LA._resolves = real


def _reading(r):
    """Everything about a Result that describes the SITE.

    `audited_at` and `tool_version` describe the run and are left out: a clock that moved is not a
    reading that moved, and a version bump would otherwise re-record this gate for nothing.
    `tool_build` and `judged_build` are left out on the same ground and for one more reason of their
    own: they are the sha256 of `core.py`, so a comment edited anywhere in that file would move them
    and re-record a gate whose subject is what the instrument READS. The record is an allowlist
    rather than a list of exclusions, so a field added to `Result` stays out of the digest until
    somebody names it here. `pages` is left out because it is the input echoed back.
    """
    return {
        'verdict': r.verdict,
        'languages': list(r.languages),
        'authorship': r.authorship,
        'sufficiency': r.sufficiency,
        'machine_translation': r.machine_translation,
        'by_language': r.by_language,
        'rules': sorted(r.rules),
        'pages_read': r.pages_read,
        # What the search behind the verdict was worth, and whether the crawl escalated because it
        # was about to assert an absence on too little. In the record because it is something the
        # instrument now REPORTS, and because escalation is otherwise invisible here: it fires on
        # four of these fixtures and changes none of their classes, so a change that switched it off
        # would move nothing else in this file.
        'read_quality': r.read_quality,
        'note': r.note,
        'switcher_languages': list(r.switcher_languages),
        'switcher_unresolved': r.switcher_unresolved,
        # Where the declaration pointed. In the record because it is something the instrument now
        # REPORTS and because a field outside this gate is a field a change can move silently: the
        # observation is all of what replaced the refusal that was measured and rejected on
        # 2026-08-05, and `offsite_alternate_only` is the fixture that carries a non-empty one.
        'declared_off_site': dict(r.declared_off_site or {}),
        'evidence': [{'mechanism': e.mechanism, 'url': e.url, 'language': e.language,
                      'sufficiency': e.sufficiency, 'authorship': e.authorship,
                      'server_html': e.server_html, 'server_plugin': e.server_plugin,
                      'rules': sorted(e.rules), 'quote': e.quote} for e in r.evidence],
    }


_CACHE = {}


def _readings():
    """Every fixture read once per process, because four tests ask for the same audits."""
    if not _CACHE:
        for f in CORPUS:
            _CACHE[f['name']] = _reading(_read(f))
    return _CACHE


def _dump(readings):
    return json.dumps(readings, ensure_ascii=False, indent=1, sort_keys=True) + '\n'


def _digest(readings):
    return hashlib.sha256(_dump(readings).encode('utf-8')).hexdigest()


# **A change to this value is a change to what the instrument reports.** Unlike the constant freeze,
# which can move because the gate widened, this one can only move because a reading moved. When it
# does, say which fixture moved and from what to what, name the shape of real site that shares that
# shape, and say which measured figure no longer applies, exactly as CONTRIBUTING.md asks for FREEZE.
# `test_every_fixture_reads_as_it_did` prints the field-level difference, so the note can be written
# from the failure output. Re-record by running the suite once with LANGACCESS_RECORD_READINGS=1,
# which rewrites tests/fixtures/reading_expected.json, and then pasting the digest it reports.
# 2026-09-17, Ethiopic. One record was added, `tigrinya_pages`, and no existing fixture moved: the
# diff of reading_expected.json is that record and nothing else. The site reads true_multilingual
# on English and Tigrinya where the same pages read english_only before, because the Ethiopic range
# could only answer Amharic and a Tigrinya paragraph carries no Amharic particle.
#
# 2026-09-17, Devanagari. One record was added, `nepali_pages`, and again no existing fixture moved,
# which is the half worth checking here: the same commit changes how SCRIPT_FUNC['Hindi'] is
# matched, from a boundary that could only see fragments to the script's own edge, and no page in
# this corpus was carrying a Devanagari reading for that to disturb. The new site reads English and
# Nepali where the same pages read English and Hindi before.
#
# 2026-09-17, the Bengali script. One record added, `assamese_pages`, and no existing fixture moved.
# The site reads English and Assamese where the same pages read English and Bengali before.
#
# 2026-09-17, four Brahmic ranges. One record added, `south_asian_locale_tree`, and no existing
# fixture moved. It reads true_multilingual over five pages in English, Punjabi, Gujarati, Tamil
# and Telugu, where the same five pages read english_only before: each notice is one sentence and
# the identifier's gate wants two of 140 characters.
#
# 2026-09-17, Armenian and Georgian. One record added, `armenian_pages`, and no existing fixture
# moved. Georgian has no fixture, because no invented Georgian page was written for this corpus;
# its range and its list are held by unit tests alone, which is the weaker of the two and is stated
# rather than papered over.
#
# 2026-09-17, Oromo. One record added, `oromo_word_gate`, and no existing fixture moved, which is
# the check a new Latin-script word list most needs: a list that fired on somebody else's page
# would move a reading here rather than only adding one.
#
# 2026-09-17, Lithuanian. One record added, `lithuanian_help_notice`, and no existing fixture
# moved. It is the first fixture here whose non-English page is a single short notice rather than a
# paragraph, which is the shape a thin word list loses.
# 2026-09-17, the merge of the recall and language branches: forty-one records, the thirty-three
# of the base plus the one the recall branch added and the seven the language branch added; every
# record was checked equal to the branch that wrote it and no earlier record moved.
#
# 2026-09-17, codebook rule 9 inside a script. One record added, `armenian_event_subtitles`, and no
# existing fixture moved, which is the half that matters here: this commit makes a gate STRICTER,
# so a fixture moving would have been a reading lost. The 41 that existed, including the Armenian,
# Tigrinya, Nepali, Assamese and four-script South Asian pages added earlier today, all still read
# what they read. The new record reads english_only on three verbless bilingual subtitles joined by
# a conjunction, which is the shape that moved one real site off its settled class.
#
# 2026-09-18, one reader for the live audit and the re-judge. No record was added and 11 of the 42
# moved: armenian_pages, assamese_pages, granicus_lang_update, lithuanian_help_notice,
# nepali_pages, onsite_alternate_declares, oromo_word_gate, persian_mission_page,
# south_asian_locale_tree, swahili_word_gate and urdu_arabic_full_stop.
#
# WHAT MOVED ON ALL ELEVEN IS THE QUOTE AND ONLY THE QUOTE. The diff of reading_expected.json is
# `evidence[n]['quote']` on those eleven and nothing else: no verdict, no language, no rule number,
# no authorship, no rung, no note, no page count. Each quote now opens one word earlier, with the
# document's own `<title>` ("Huduma", "Center", "केन्द्र") in front of the paragraph it always
# quoted. The reading is `_page_text` of the served document now, which is the function `rejudge`
# has always read a stored page with, and `_text_from_html` takes the title because a title is text
# in the document; `inner_text('body')`, which the live audit read before, does not. So the eleven
# are the live reader arriving at the reading every published agreement figure was computed on.
#
# THE TITLE IS NOT A NEW HAZARD AND IS NOT DEFENDED AGAINST. A title alone cannot produce a
# reading: rule 6 wants four distinct function words inside one 500-character window of connected
# prose, and rule 8 puts the home document's own title in `_site_names`, which `languages_in`
# excludes. What it can do is sit at the left edge of a quote, which is what these eleven records
# show, and a consumer reading `evidence` sees it there.
#
# 2026-09-18, the shapes a browser does not lay out. Three records were added and no existing
# record moved. `hidden_language_span_pair` and `display_none_language_panel` read
# true_multilingual in English and Spanish, with the Spanish quoted and `server_html` true on it,
# where the same two pages read english_only under the reader this release replaced: their browser
# text is the English half and the document carries both. `hidden_english_mobile_menu` is their
# control and reads english_only with no evidence at all, which is what says the new reader finds
# the Spanish on those two and does not manufacture a language out of any unrendered text it meets.
# The three are the corpus's first fixtures whose recorded browser text is deliberately NARROWER
# than their document; every other fixture's two halves agree or differ only in furniture.
# 2026-09-18, the same merge: the reader branch's three fixtures join, and every earlier record
# reads as the branch that last wrote it (the eleven quote shifts the reader branch recorded,
# the placeholder branch's untouched records).
# 2026-09-18, a quoted testimonial is recorded and not counted. TWO records added,
# `quoted_testimonial_only` and `own_paragraph_beside_testimonials`, and no existing fixture
# moved: the diff of reading_expected.json is those two records and nothing else. That is the half
# worth checking here, because this commit takes text OUT of the counted stream and a fixture
# moving would have been a reading lost. The first site reads english_only with the Spanish
# testimonial on the record as a `testimonial` row at rung 1, where the same pages read
# true_multilingual before. The second is the boundary: its own Spanish paragraph sits beside the
# same two testimonial cards, is counted at rung 2, and the site still reads true_multilingual,
# which is the shape that refused a rule over the TEXT in September 2026. Measured figures: no
# accuracy figure in LIMITATIONS 1 is recomputed, because the 2,000-site gold standard is not
# coded in this tree; what the change moves on the two captures is in LIMITATIONS 7.2 and in the
# commit message.
# 2026-09-18, the same merge: the testimonial branch's two fixtures join (forty-seven records) and
# every record equals the branch that last wrote it.
READINGS = 'b704aac2f4bd1be35c39073d975e166a239d66a6cb445ca503c615066aed6ab7'


def _expected():
    with io.open(_EXPECTED_PATH, encoding='utf-8') as fh:
        return json.load(fh)


@pytest.mark.parametrize('name', sorted(CORPUS_BY_NAME))
def test_every_fixture_reads_as_it_did(name):
    """One test per site, so a failure names the site and the field rather than a hash."""
    got, want = _readings()[name], _expected()[name]
    moved = sorted(k for k in want if got.get(k) != want[k])
    assert moved == [], (
        '%s reads differently than it did.\n  what this fixture is for: %s\n%s'
        % (name, CORPUS_BY_NAME[name]['why'],
           '\n'.join('  %s\n    was: %r\n    now: %r' % (k, want[k], got.get(k)) for k in moved)))


def test_the_readings_digest_has_not_moved():
    """The single value a person re-records, and the one that belongs in a release note."""
    readings = _readings()
    if os.environ.get('LANGACCESS_RECORD_READINGS'):
        with io.open(_EXPECTED_PATH, 'w', encoding='utf-8', newline='\n') as fh:
            fh.write(_dump(readings))
    assert _digest(readings) == READINGS, (
        'the instrument reads these pages differently than it did. Run the suite once with '
        'LANGACCESS_RECORD_READINGS=1 to rewrite the expected file, read the diff of that file, and '
        'record the new digest with a note saying which reading moved and why.')


def test_the_run_fields_are_not_in_the_record():
    """The gate is over readings, so nothing that describes the RUN may enter it. The two builds
    are the field this test was written for: they are the hash of `core.py`, and a gate that held
    them would have to be re-recorded by every edit to a comment in that file, which is how a gate
    stops being read."""
    r = _read(CORPUS[0])
    assert r.tool_build and r.tool_build == r.judged_build, 'the fixture audit has to stamp them'
    record = _reading(r)
    for f in ('audited_at', 'tool_version', 'tool_build', 'judged_at', 'judged_version',
              'judged_build', 'pages'):
        assert f not in record, '%s describes the run, not the site' % f


def test_the_corpus_covers_the_classes_it_was_built_from():
    """What the corpus is currently known to reach, stated so that it cannot quietly shrink.

    A gate over a sample says nothing about what the sample stopped exercising. If a fixture is
    edited until it no longer produces machine_translate, the digest moves once, somebody records
    the new value, and the class is gone from the gate with nobody having decided that. The floor is
    every verdict the codebook defines, every value of the authorship axis, four rungs of the
    sufficiency ladder, and the fourteen codebook rules these pages are written to fire.
    """
    readings = _readings().values()
    verdicts = {r['verdict'] for r in readings}
    from langaccess.review import VERDICTS
    # tied to the published set the way the authorship line below is tied to its constant,
    # so a sixth class cannot arrive without this floor noticing. machine_translate_error is
    # the one absence this floor accepts, named here rather than blocked in silence: it needs
    # a clicked control that changes nothing, and this corpus's fake browser cannot click.
    # The default-suite wire for that class is in test_engineering
    # (test_a_dead_control_reaches_machine_translate_error_without_a_real_browser).
    assert verdicts == set(VERDICTS) - {'machine_translate_error'}, (
        'the corpus no longer reaches every verdict it can: %s' % sorted(verdicts))
    authorship = {r['authorship'] for r in readings}
    assert authorship == {LA.AUTHOR_NONE, LA.AUTHOR_AUTHORED, LA.AUTHOR_SERVER_PLUGIN,
                          LA.AUTHOR_CLIENT_WIDGET, LA.AUTHOR_UNKNOWN_WIDGET}, (
        'the corpus no longer reaches every authorship: %s' % sorted(authorship))
    assert set(authorship) == set(LA.AUTHORSHIP_ORDER), (
        'the axis gained or lost a value and this floor did not move with it, which is how a value '
        'leaves the gate with nobody deciding that')
    rungs = {r['sufficiency'] for r in readings}
    assert rungs == {LA.SUFF_NONE, LA.SUFF_NOTICE, LA.SUFF_PAGE, LA.SUFF_SECTION}, (
        'the corpus no longer reaches these rungs: %s' % sorted(rungs))
    rules = {n for r in readings for n in r['rules']}
    # 15 joined 2026-08-07. `platform_locale_mirrors`
    # was written for rule 17 and did not fire it, because the crawl saw two of its three advertised
    # front doors and the rule needs three. The absence was recorded here, in a set of numbers that
    # nobody compared against the corpus's own notes, for as long as this gate has existed.
    # 5 left on 2026-08-08 with the rule. `directory_profile` still stops and still comes back
    # unreachable; what it no longer does is name a number, so the fixture that exercises it is
    # held by its note and its verdict rather than here.
    # Renumbered 2026-08-09 with the registry. Release 3 (rendered pages) and release 5 (pages
    # still in service) have never been in the fired set, and release 16 (a worked control
    # without effect) cannot be: it needs a click and a re-judge never clicks, which is the
    # same fact that keeps the agreement figure untouched by that rule.
    assert rules == {1, 2, 4, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 17}, (
        'the corpus fires a different set of codebook rules than it was built to fire: %s'
        % sorted(rules))
    languages = {lang for r in readings for lang in r['languages']}
    # Swahili joined 2026-08-06 with `swahili_word_gate`: the first language here the package's
    # own word lists cannot express, read through langid and the closed-class word gate, so the
    # auxiliary path finally has a fixture on its positive side.
    # Tigrinya joined with `tigrinya_pages`. It is the second language of a script the corpus
    # already carried, so what it adds is not a script but the resolution inside one: before
    # ETHIOPIC the Ethiopic range could only answer Amharic, and a Tigrinya page answered nothing.
    # Nepali joined with `nepali_pages`, and it is the first Devanagari page here at all, so the
    # boundary SCRIPT_FUNC_EDGE fixes is exercised by a reading and not only by a unit test.
    # Assamese joined with `assamese_pages`, the first Bengali-script page here, so the boundary is
    # exercised by a reading in that script too.
    # Punjabi, Gujarati, Tamil and Telugu joined together with `south_asian_locale_tree`, one site
    # publishing the same notice on four locale routes, which is the shape the four Brahmic ranges
    # were added for.
    assert languages == {'English', 'Spanish', 'Japanese', 'Chinese', 'Ukrainian', 'Persian',
                         'Urdu', 'Swahili', 'Tigrinya', 'Nepali', 'Assamese',
                         'Punjabi', 'Gujarati', 'Tamil', 'Telugu', 'Armenian', 'Oromo',
                         'Lithuanian'}, (
        'the corpus no longer reads these languages: %s' % sorted(languages))


def test_the_corpus_holds_a_reading_the_review_queue_asks_a_person_about_for_its_declaration():
    """The observation has to reach the consumer that acts on it, or the corpus freezes a field
    nothing reads. `offsite_alternate_only` is the only fixture whose record names a language no
    address on its own site named, and it is the shape `review.needs_human` was extended for."""
    from langaccess.review import OFF_SITE_DECLARATION, unsettled_kind
    rd = _readings()
    off = rd['offsite_alternate_only']
    assert off['declared_off_site'] == {'alternates': 1, 'languages': ['Turkish']}
    assert off['languages'] == ['English'], 'the crawl found nothing but English on this site'
    queued = sorted(n for n, r in rd.items()
                    if unsettled_kind(dict(r, url='https://%s.example/' % n))
                    == OFF_SITE_DECLARATION)
    assert queued == ['offsite_alternate_only'], (
        'the corpus reaches the off-site queue kind on %s, and it is written to reach it on one'
        % (queued or 'nothing'))
    control = rd['onsite_alternate_declares']
    assert control['declared_off_site'] == {'alternates': 0, 'languages': []}


def test_the_chrome_selector_still_names_what_it_was_written_to_name():
    """The selector is no longer a page reading and it still has to be right.

    `_CHROME_JS` decides one thing from 0.2.0 on: the text a page reports after a language control
    is clicked. This corpus's browser has no control to click, so nothing here exercises it through
    an audit, and asserting that it did would be the pretence this file exists to refuse. What is
    held instead is the selector, against the second implementation above, over the one fixture
    written for the shape that broke it: the answer has to be narrower than the body, since a
    chrome-free text identical to the body would hide nothing, and the wrapper the defect was about
    has to survive with its Spanish in it.

    The last two lines are the other half. The same page's READING is taken the other way now, off
    the served document, and the Spanish under the wrapper has to come through that as well.
    """
    fixture = CORPUS_BY_NAME['skip_link_target_wrapper']
    html, body = fixture['pages'][fixture['url']][0], fixture['pages'][fixture['url']][1]
    main = _chrome_free_text(html, LA.CHROME_SEL, LA.CHROME_LIST_MIN_ITEMS, LA.CHROME_LIST_SHARE,
                             LA.CHROME_LABEL_MAX)
    assert main and main != body, (
        'the chrome-free text of this page is the whole page, so nothing in it is furniture and the '
        'selector decides nothing here')
    assert 'Skip to content' in body and 'Skip to content' not in main
    # the wrapper the defect was about survives, and the Spanish inside it is the reading
    assert 'id="wp--skip-link--target"' in html
    assert 'El Centro de Bienvenida' in main
    assert _readings()['skip_link_target_wrapper']['languages'] == ['English', 'Spanish']


def test_the_corpus_holds_a_document_whose_attribute_carries_a_greater_than():
    """The shape the corpus did not reach until 2026-08-05, held so it cannot leave again.

    A whole rewrite of the tag stripper moved this file's digest not at all, because no fixture
    carried an attribute value with a literal `>` in it. Asserting the reading is not enough: a
    later edit could keep the verdicts and drop the character, and the gate would go quiet without
    anybody deciding that. So this asserts the INPUT as well as the answer.
    """
    carriers = sorted(f['name'] for f in CORPUS
                      for h in list(f['pages'].values()) + list(f.get('plain', {}).values())
                      for doc in ([h[0]] if isinstance(h, list) else [h])
                      if re.search(r'''=\s*"[^"<]*>[^"<]*"''', doc))
    assert 'attribute_greater_than_over_the_floor' in carriers, (
        'no fixture carries an attribute value with a literal greater-than sign, so the corpus '
        'cannot tell the tag stripper from a character class: %s' % carriers)
    rd = _readings()
    over, prose = (rd['attribute_greater_than_over_the_floor'],
                   rd['attribute_greater_than_in_the_prose'])
    # the direction that costs coverage: leaked markup used to carry this over the length floor
    assert over['verdict'] == 'unreachable' and over['pages_read'] == 0
    # and the direction no floor sees: the rung, on a page whose prose is real
    assert prose['verdict'] == 'true_multilingual'
    assert prose['by_language']['Spanish'] == {'authorship': 'authored',
                                               'sufficiency': LA.SUFF_PAGE}
    assert all('class=' not in e['quote'] and 'data-' not in e['quote']
               for e in prose['evidence']), 'markup reached a quoted piece of evidence'


def test_the_corpus_holds_a_site_of_each_shape_the_english_reading_can_take():
    """English is a reported field, and a field with one shape in the corpus is a field untested.

    Three shapes, named here so that editing a fixture until one of them is gone fails rather than
    moving the digest once and taking the case with it. `languages` is what the classification
    counted, so English joins it on the same terms Spanish does and a site written only in Spanish
    says so by leaving English out.
    """
    rd = _readings()
    only_english = rd['english_only']
    assert only_english['languages'] == ['English'], (
        'a site written only in English has to say English and nothing else: %s'
        % only_english['languages'])

    only_spanish = rd['unique_word_outside_the_window']
    assert only_spanish['languages'] == ['Spanish'], (
        'a site written only in Spanish has to say Spanish and NOT English, which is the half of '
        'this that carries information: %s' % only_spanish['languages'])
    assert 'English' not in only_spanish['by_language']

    for name in ('authored_spanish_page', 'bilingual_notice'):
        assert rd[name]['languages'] == ['English', 'Spanish'], (
            '%s is a bilingual site and has to name both: %s' % (name, rd[name]['languages']))
        assert set(rd[name]['by_language']) == {'English', 'Spanish'}

    # and the axes on the English row come out of the same machinery as every other language's
    assert rd['english_only']['by_language']['English'] == {'authorship': 'authored',
                                                            'sufficiency': LA.SUFF_PAGE}
    # a site that was not read at all reports no English either, because nothing was read
    assert rd['bot_wall']['by_language'] == {} and rd['bot_wall']['languages'] == []

    # THE INVARIANT UNDER ALL OF IT. English is reported and never counted, so no piece of English
    # evidence is on any Result in the corpus; the classes are what they were, and a site whose only
    # second language is English is still an absence claim.
    stray = sorted(name for name, r in rd.items()
                   if any(e['language'] == 'English' for e in r['evidence']))
    assert stray == [], (
        'English evidence reached Result.evidence on %s, which is the list every verdict, rule and '
        'axis is derived from' % stray)
    assert only_english['verdict'] == 'english_only'
    assert rd['authored_spanish_page']['verdict'] == 'true_multilingual'


def test_the_corpus_holds_a_page_whose_second_language_is_inside_a_social_feed():
    """A feed embed is somebody else's writing, and the container is what says so.

    Three things are held, because asserting the verdict alone would pass on a corpus whose feed
    carried no Spanish at all. The document HAS the Spanish; the reader that takes the containers
    out does not find it; and the site reads `english_only` on that reading. The DOM half of the
    same strip is not exercised here: this corpus's fake browser answers every `evaluate` with
    None, so the reading comes through the plain-client rescue, which is the one route where the
    markup decides the text. `tests/test_core.py` holds the selector and the byte reader to one
    list of containers.
    """
    fixture = CORPUS_BY_NAME['social_feed_container']
    doc = list(fixture['plain'].values())[0]
    assert 'id="sb_instagram"' in doc and 'class="sbi_item"' in doc, (
        'the fixture no longer carries a feed container, so nothing in it is a feed')
    assert 'Spanish' in LA.languages_in(LA._text_from_html(doc)), (
        'the feed in this fixture carries no Spanish, so removing it proves nothing')
    assert 'Spanish' not in LA.languages_in(LA._page_text(doc))
    reading = _readings()['social_feed_container']
    assert reading['verdict'] == 'english_only' and reading['languages'] == ['English']


def test_the_corpus_holds_the_shapes_a_browser_does_not_lay_out():
    """The reading is the served document from 0.2.0, and these three fixtures are what that buys.

    Four things are held on each of the two positive fixtures, because asserting the verdict alone
    would pass on a fixture whose hidden half carried no Spanish. The document HAS the Spanish; the
    browser text recorded beside it does NOT, which is the fixture modelling a page whose markup
    keeps that half out of the layout; the reading finds it; and the site reads true_multilingual
    with the Spanish quoted and confirmed against the server document.

    The third is the control, and it is the half that keeps this honest. Reading text a browser did
    not lay out could have been a licence to read anything, and a hidden English mobile menu is
    what a theme leaves in nearly every document there is. That site reads english_only with no
    evidence on it at all.

    These are the two mechanisms a reviewer confirmed on real sites: paired language-tagged spans
    and a panel behind `display:none`, which is also what a tab, an accordion and a carousel slide
    that is not the visible one leave in a document.
    """
    rd = _readings()
    for name, host in (('hidden_language_span_pair', 'hidden-span'),
                       ('display_none_language_panel', 'hidden-panel')):
        fixture = CORPUS_BY_NAME[name]
        doc, browser_text = fixture['pages'][fixture['url']][:2]
        assert 'Nuestro centro' in doc, (
            '%s no longer carries Spanish in its document, so hiding it proves nothing' % name)
        assert 'Nuestro centro' not in browser_text, (
            '%s records a browser text that already carried the Spanish, so the fixture no longer '
            'models a page whose markup keeps it out of the layout' % name)
        assert 'Nuestro centro' in LA._page_text(doc)
        reading = rd[name]
        assert reading['verdict'] == 'true_multilingual'
        assert reading['languages'] == ['English', 'Spanish']
        quoted = [e for e in reading['evidence'] if e['language'] == 'Spanish']
        assert len(quoted) == 1 and 'Nuestro centro' in quoted[0]['quote']
        assert quoted[0]['server_html'], 'the server ships it, which is what authorship turns on'

    control = CORPUS_BY_NAME['hidden_english_mobile_menu']
    doc = control['pages'][control['url']][0]
    assert 'display:none' in doc and 'Volunteer' in doc, (
        'the control no longer carries a hidden menu, so it controls for nothing')
    assert 'Volunteer' in LA._page_text(doc), 'the reader does read it; that is the point'
    assert rd['hidden_english_mobile_menu']['verdict'] == 'english_only'
    assert rd['hidden_english_mobile_menu']['languages'] == ['English']
    assert rd['hidden_english_mobile_menu']['evidence'] == []


def test_the_corpus_holds_a_page_whose_only_second_language_is_a_quoted_testimonial():
    """A testimonial is somebody else's writing and the container is what says so.

    Four things are held, because asserting the verdict alone would pass on a corpus whose
    testimonial carried no Spanish at all. The document HAS the Spanish; the reader that takes the
    containers out does not find it; the site reads `english_only` on that reading; and the
    quotation is ON THE RECORD at rung 1, which is the half that separates this from the feed
    strip, where a removed container leaves no trace. The DOM half of the same strip is not
    exercised here, for the reason the feed test above gives.
    """
    fixture = CORPUS_BY_NAME['quoted_testimonial_only']
    doc = list(fixture['plain'].values())[0]
    assert 'class="testimonial-card"' in doc, (
        'the fixture no longer carries a testimonial container, so nothing in it is a testimonial')
    assert 'Spanish' in LA.languages_in(LA._text_from_html(doc)), (
        'the testimonial in this fixture carries no Spanish, so removing it proves nothing')
    assert 'Spanish' not in LA.languages_in(LA._page_text(doc))
    reading = _readings()['quoted_testimonial_only']
    assert reading['verdict'] == 'english_only' and reading['languages'] == ['English']
    quoted = [e for e in reading['evidence'] if e['mechanism'] == LA.MECH_TESTIMONIAL]
    assert [(e['language'], e['sufficiency'], e['authorship']) for e in quoted] == [
        ('Spanish', LA.SUFF_TOKEN, LA.AUTHOR_NONE)], (
        'the quotation has to stay on the record, or this is a reading that vanished')
    assert reading['by_language']['Spanish']['sufficiency'] == LA.SUFF_NONE


def test_the_corpus_holds_the_page_the_container_rule_must_not_take():
    """The boundary, and the case that refused a rule over the TEXT in September 2026.

    One organization of the reviewed sample publishes four participant testimonials in Spanish AND
    its own Spanish paragraph about its programme on the same page, and it does publish in
    Spanish. This fixture is that shape: the paragraph is outside the containers, so it is counted
    and the site stays `true_multilingual` while the quotations beside it are recorded and counted
    by nothing. A change that widened a container until it swallowed the paragraph would move this
    fixture, which is what it is here for.
    """
    fixture = CORPUS_BY_NAME['own_paragraph_beside_testimonials']
    doc = list(fixture['plain'].values())[0]
    assert 'class="testimonial-card"' in doc and 'Nuestro centro ofrece' in doc
    reading = _readings()['own_paragraph_beside_testimonials']
    assert reading['verdict'] == 'true_multilingual'
    assert reading['languages'] == ['English', 'Spanish']
    counted = [e for e in reading['evidence'] if e['mechanism'] == 'inline_text']
    assert [e['language'] for e in counted] == ['Spanish'], (
        "the organization's own paragraph is what the verdict rests on")
    assert 'Nuestro centro ofrece' in counted[0]['quote']
    assert any(e['mechanism'] == LA.MECH_TESTIMONIAL for e in reading['evidence'])


def test_every_address_in_the_corpus_is_a_reserved_one():
    """Nothing captured from a real organization can be committed here, so nothing is.

    `.example` is reserved by RFC 2606 and can never belong to anybody. The two platform hosts are
    named above and are in the corpus because DIRECTORY_HOST and SOCIAL_HOST are lists of real
    platforms and a fixture for the directory stop and codebook rule 1 has to use one. This test is
what stops a
    page from the census capture being dropped in later as a convenient extra case.
    """
    for f in CORPUS:
        addresses = [f['url']] + sorted(f['pages']) + sorted(f.get('plain', {}))
        for a in addresses:
            host = a.split('/')[2]
            assert host.endswith('.example') or host in _PLATFORM_HOSTS, (
                '%s carries the address %s, which is neither a reserved name nor one of the two '
                'platforms the corpus names on purpose' % (f['name'], a))


def test_every_fixture_says_what_it_is_for():
    """A fixture nobody can read is a fixture nobody will fix when it fails."""
    thin = sorted(f['name'] for f in CORPUS if len(f.get('why', '').strip()) < 40)
    assert thin == [], 'these fixtures do not say what they pin: %s' % thin
