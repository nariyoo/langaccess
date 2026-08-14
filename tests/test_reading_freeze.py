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
  2026-08-01, decide a reading on a live site and decide nothing here. One fixture is read through a
  browser that answers the chrome-removal script off its own markup, so the SELECTOR that decides
  what `_main_text` hides is exercised; the script itself is JavaScript and is exercised in
  `tests/test_live.py`.

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
from test_engineering import _MapBrowser, _MapCtx, _MapPage, _PlainClient

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


# ------------------------------------------------------------------ a browser with a document in it
#
# WHY THIS EXISTS. `_main_text` hands the browser a script, and every fake page in this suite answers
# `evaluate` with None, which is the value that means "this page could not be asked" and sends the
# audit back to reading the whole body. So the chrome removal ran 364 times over these fixtures and
# decided nothing, and the defect that motivated the whole gate was invisible to it: CHROME_SEL
# written without the leading `a` matches `id="wp--skip-link--target"`, the id WordPress block themes
# put on the `<main>` that wraps the page, and the selector then hid the document and returned the
# empty string. Substituting the defective selector into a run of this file moved nothing.
#
# WHAT IS REAL HERE AND WHAT IS NOT. The four constants the script is called with arrive from
# `langaccess.core` through the `evaluate` argument, and the skip-link phrase list is read out of
# `_CHROME_JS` itself, so the things a change would move are the things this reads. The ALGORITHM is
# a second implementation of the same three steps and can drift from the JavaScript; what it is here
# to answer is which elements a selector reaches, which is where the defect was. The JavaScript is
# exercised against a real browser in `tests/test_live.py`.
#
# WHY ONE FIXTURE AND NOT ALL OF THEM. A fixture records the browser's text beside its HTML and
# the two do not agree on the rest: `english_only` keeps a `<a href="/services">Services</a>`
# in its markup that its recorded text does not carry. Deriving the text from the document would
# move readings that have nothing to do with the chrome rule, so a fixture asks for this by carrying
# `dom`, and the one that does is written so that its recorded text is what this returns with
# nothing hidden.
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


class _DomPage(_MapPage):
    """A map page that answers the chrome-removal script off the document it is serving."""

    async def evaluate(self, script, arg=None):
        if not (isinstance(script, str) and 'laHidden' in script):
            return None
        selector, min_items, share, label_max = arg
        return _chrome_free_text(self._html, selector, min_items, share, label_max)


class _DomCtx(_MapCtx):
    async def new_page(self):
        return _DomPage(self)


class _DomBrowser(_MapBrowser):
    async def new_context(self, **k):
        ctx = _DomCtx(self)
        self.contexts.append(ctx)
        return ctx


def _read(fixture):
    """Audit one fixture through the fake browser, with the resolver answered from the fixture.

    The audit invents eight locale subdomains per site and asks a real resolver whether each one
    exists. That is a live network call, so a recorded reading would depend on which machine ran it
    and on whether the resolver hijacks NXDOMAIN. It is answered here from the fixture's own address
    map instead, which is deterministic and still exercises the subdomain path for a fixture that
    declares one.

    A fixture carrying `dom` is read through the browser above, which answers the chrome-removal
    script off its own markup; every other fixture is read through the browser that declines to
    answer it, which is what all twenty were recorded under.
    """
    pages = {u: tuple(v) for u, v in fixture['pages'].items()}
    hosts = {u.split('/')[2] for u in pages}

    async def resolves(host, cache, timeout=None):
        return host in hosts

    real = LA._resolves
    LA._resolves = resolves
    try:
        make = _DomBrowser if fixture.get('dom') else _MapBrowser
        browser = make(pages, plain=_PlainClient(dict(fixture.get('plain', {}))))
        return asyncio.run(LA._audit_async(fixture['url'], browser=browser))
    finally:
        LA._resolves = real


def _reading(r):
    """Everything about a Result that describes the SITE.

    `audited_at` and `tool_version` describe the run and are left out: a clock that moved is not a
    reading that moved, and a version bump would otherwise re-record this gate for nothing. `pages`
    is left out because it is the input echoed back.
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
READINGS = '99859d1d637ff286fbb0b43e974fb9d7180e3aaa684b20456ff31fa7b382b193'


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
    assert languages == {'English', 'Spanish', 'Japanese', 'Chinese', 'Ukrainian', 'Persian',
                         'Urdu', 'Swahili'}, (
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


def test_the_corpus_reads_a_page_the_markup_says_is_mostly_furniture():
    """`_main_text` is a reading path and a corpus that cannot reach it does not freeze it.

    Two things are held. The audit of `skip_link_target_wrapper` has to ask the browser for the
    chrome-free text and get an ANSWER, since a fixture whose browser returns None sends the audit
    back to reading the whole body and takes the selector out of the gate without moving the digest.
    And the answer has to be narrower than the body, since a chrome-free text identical to the body
    would pass the first half while hiding nothing.
    """
    fixture = CORPUS_BY_NAME['skip_link_target_wrapper']
    assert fixture.get('dom'), 'the fixture no longer asks for a browser that answers the script'
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
