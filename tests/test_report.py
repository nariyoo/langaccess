# -*- coding: utf-8 -*-
"""One reading as a document about one site, and the three ways a document can lie.

`report` is a presentation layer on the pattern of `explain`, `diff` and `review`. Everything it
renders was written by the audit, and the tests that matter are the ones that hold it to that: it
moves no verdict, it counts as counted only what `counted_evidence` counted, and it renders no
document at all over a record that never held a reading.

The three ways the feature could go wrong, each with a test below.

  It could claim more than the reading. A document is the artifact that leaves this project, and a
  page of headings over a record with nothing in it reads as a finished audit of a site with
  nothing to find. `test_a_record_that_never_held_a_reading_gets_no_document` is that line.

  It could drop the statement of what it is not. The document is handed to the organization whose
  site was read, which is exactly where a description gets read as a verdict, so the compliance
  limit is asserted in BOTH rendered forms and by its words rather than by its presence in a list.

  It could quote without saying where from. A quotation with no address is not checkable, and the
  only reason to hand somebody this document is that they can go and look.
"""
import asyncio
import json
import re

import pytest

from langaccess import core as LA
from langaccess import report, report_html, report_text, write_report
from langaccess.report import (CLASS_MEANING, LIMITS, NO_LANGUAGE, NothingToReport, QUOTE_CHARS,
                               form_for, render)
from langaccess.review import HAND_CODING
from test_engineering import _MapBrowser, _PlainClient, _page


# The same fixture the explanation tests use: an English home page linking a Spanish services page,
# read by a real crawl over a fake browser, so what is reported is a reading this package took.
_ES = ('Nuestros servicios para la comunidad son gratuitos. Ofrecemos informacion y recursos '
       'para las familias que necesitan ayuda con este proceso, y todos pueden hacer una cita. ')
_HOME_TEXT = 'Welcome to our center. We help families with legal questions every day of the week.'
_SITE = {
    'https://x.org/': ('<html><head><title>Centro</title></head><body>'
                       '<a href="/servicios">Servicios</a><p>' + _HOME_TEXT + '</p></body></html>',
                       _HOME_TEXT, 200),
    'https://x.org/servicios': _page(_ES * 3),
}


def _audit(site=None, url='https://x.org/', **kw):
    b = _MapBrowser(site or _SITE, plain=_PlainClient({}))
    return asyncio.run(LA._audit_async(url, browser=b, **kw))


def _both(r):
    """The two rendered forms of one reading, for a check that has to hold of each.

    Whitespace is collapsed in each, because the plain form wraps a paragraph and the HTML form
    holds the same paragraph on one line; a sentence that a check looks for by its words would
    otherwise be found in one form and missed in the other for no reason a reader would notice.
    """
    return {'text': ' '.join(report_text(r).split()), 'html': ' '.join(report_html(r).split())}


# ------------------------------------------------------------------ what the document has to carry
def test_the_document_names_the_class_and_says_what_it_means():
    """The four words this package uses are its own vocabulary. A document that prints
    `machine_translate` and stops has handed a reader a token to look up."""
    r = _audit()
    assert r.verdict == 'true_multilingual', 'the fixture has to have something to report'
    d = report(r)
    assert d['verdict'] == r.verdict
    assert d['verdict_meaning'] == CLASS_MEANING[r.verdict]
    for form, text in _both(r).items():
        assert r.verdict in text, form
        # the sentence itself, not a reference to one somewhere else
        assert 'no browser-side widget produced it' in text, form


def test_every_quotation_carries_the_address_it_was_read_at():
    """The one reason to hand an organization this document is that they can go and check it."""
    d = report(_audit())
    quoted = [f for row in d['languages'] for f in row['findings'] if f['quote']]
    assert quoted, 'the fixture produced a finding and the document has to quote it'
    for f in quoted:
        assert f['url'].startswith('http'), 'a quotation with no address is not checkable'
    for form, text in _both(_audit()).items():
        assert 'https://x.org/servicios' in text, form
        assert 'servicios para la comunidad' in text, form


def test_the_languages_are_reported_one_at_a_time_with_both_axes_named():
    """A single summary hides the shape this instrument exists to see: Spanish an organization
    wrote beside Vietnamese a widget produced."""
    d = report(_audit())
    rows = {row['language']: row for row in d['languages']}
    assert 'Spanish' in rows
    es = rows['Spanish']
    assert es['authorship'] == LA.AUTHOR_AUTHORED
    assert es['authorship_meaning'], 'the axis has to say what it means, not only what it is'
    assert es['sufficiency_meaning']
    assert es['counted'] is True


def test_the_rules_that_decided_it_are_named_by_number_and_by_heading():
    r = _audit()
    d = report(r)
    fired = [rule for block in d['rules'] if block['status'] == 'fired' for rule in block['rules']]
    assert [rule['number'] for rule in fired] == sorted(r.rules)
    for rule in fired:
        assert rule['heading'] == LA.RULES[rule['number']].heading
    for form, text in _both(r).items():
        assert LA.RULES[r.rules[0]].heading in text, form


def test_the_search_behind_the_reading_is_reported_and_an_absence_says_so():
    """`english_only` is the one class that asserts an absence, and an absence claim is worth what
    the search behind it was worth. The document says which of the two it is holding."""
    r = _audit({'https://x.org/': _page(_HOME_TEXT)})
    assert r.verdict == 'english_only'
    d = report(r)
    assert d['reading']['absence_claim'] is True
    assert d['reading']['pages_read'] == r.read_quality['pages_read']
    for form, text in _both(r).items():
        assert 'claim of absence' in text, form
        assert 'Pages read' in text, form

    # and the other way: a class that rests on something FOUND says the search is not what it turns
    # on, so a reader does not take a thin search for a doubt about the finding
    other = _both(_audit())
    for form, text in other.items():
        assert 'is not a claim of absence' in text, form


def test_the_date_and_the_version_are_on_the_document():
    """A reading describes one site at one moment under one rule set, and a document with neither
    on it is a reading somebody will still be quoting in three years."""
    r = _audit()
    d = report(r)
    assert d['audited_at'] == r.audited_at and d['audited_at']
    assert d['tool_version'] == r.tool_version and d['tool_version']
    for form, text in _both(r).items():
        assert r.audited_at in text, form
        assert r.tool_version in text, form


def test_the_addresses_the_document_can_name_are_described_as_the_set_they_are():
    """A plain result row holds no page list, so the only addresses on it are the ones its findings
    were read at. Calling those "the pages the crawl read" would overstate a search."""
    d = report(_audit())
    assert d['reading']['addresses'] == ['https://x.org/servicios']
    assert 'not all of them' in d['reading']['addresses_are']

    # a capture holds every page, and then the document says so
    with_pages = report(_audit(keep_pages=True))
    assert set(with_pages['reading']['addresses']) == set(_SITE)
    assert with_pages['reading']['addresses_are'] == 'every page the crawl read'


# ------------------------------------------------------------------ the statement of what it is not
def test_both_forms_carry_the_compliance_limit_in_its_own_words():
    """The wording of this one matters more than anything else in the package: a document handed to
    an organization is where a description gets read as a verdict. Asserted by its words, so that
    dropping the sentence and keeping the heading fails."""
    r = _audit()
    d = report(r)
    assert [lim['heading'] for lim in d['limits']] == [h for h, _ in LIMITS]
    for form, text in _both(r).items():
        assert 'not a determination of compliance' in text, form
        assert 'no threshold at which a site becomes adequate' in text, form
        assert 'does not judge how good the writing is' in text, form
        assert 'A website is not a service' in text, form
        # every limit, in full, in both forms: an abbreviated statement in the plain-text form is
        # the version somebody prints
        for lim in LIMITS:
            assert lim[0] in text, (form, lim[0])


def test_no_heading_in_the_rendered_document_carries_a_verb(tmp_path):
    """A heading names; it does not narrate. The rule applies to every heading this package prints
    where a stranger will read it, and every conditional section is rendered here, because a
    heading that only appears on an unsettled or a re-judged reading is the one that escapes."""
    verbs = re.compile(r'\b(is|are|was|were|has|have|can|could|should|will|shows?|makes?|means?|'
                       r'gives?|tells?|says?|does|do|be|been|being|read|reads)\b', re.I)
    for heading, _statement in LIMITS:
        assert not verbs.search(heading), heading

    path = tmp_path / 'run.jsonl'
    LA._store_result(str(path), _audit(keep_pages=True))
    seen = set()
    for r in (_audit(), LA.Result(url='https://x.org/', verdict='unreachable', note='bot wall'),
              LA.rejudge(str(path), 'https://x.org/')):
        html = report_html(r)
        for heading in re.findall(r'<h[123][^>]*>(.*?)</h[123]>', html, re.S):
            plain = re.sub(r'<[^>]+>', ' ', heading).strip()
            seen.add(plain)
            assert not verbs.search(plain), plain
    # the conditional sections were actually rendered, so the check above met them
    assert 'The unsettled part of this reading' in seen
    assert 'A re-judged capture' in seen


# ------------------------------------------------------------ the line this feature must not cross
def test_a_record_that_never_held_a_reading_gets_no_document():
    """This project's most frequent bug is a stage that produced nothing and reported success. A
    per-site document is the shape that invites it, because a site with nothing found and a row
    nobody filled in render the same way unless one of them is made to fail."""
    with pytest.raises(NothingToReport):
        report(LA.Result(url=''))
    with pytest.raises(NothingToReport):
        report({'url': 'https://x.org/', 'verdict': '', 'evidence': [], 'languages': [],
                'read_quality': {}})
    # and a site that was genuinely not read IS a reading, and gets a document that says so
    d = report(LA.Result(url='https://x.org/', verdict='unreachable', note='bot wall'))
    assert d['verdict'] == 'unreachable'
    assert 'bot wall' in report_text(d)
    assert 'nothing established' in d['verdict_meaning']


def test_a_document_never_renders_an_empty_section():
    """The count a caller can assert on and the document a reader gets are the same list, so a
    section cannot be announced and then come out blank."""
    for r in (_audit(), _audit({'https://x.org/': _page(_HOME_TEXT)}),
              LA.Result(url='https://x.org/', verdict='unreachable', note='bot wall')):
        d = report(r)
        assert d['sections'], 'every reading has at least the class, the search and the limits'
        assert ('evidence' in d['sections']) == bool(d['findings_total'])
        assert ('rules' in d['sections']) == bool(d['rules'])
        assert 'limits' in d['sections'] and 'classification' in d['sections']


def test_which_findings_were_counted_comes_from_the_function_the_verdict_used():
    """Not a second copy of the counting rule. If `counted_evidence` changes, this changes with it."""
    r = _audit()
    d = report(r)
    counted = {(LA._ev_url(e), LA._ev_lang(e))
               for e in LA.counted_evidence(r.evidence, r.machine_translation)}
    seen = {(f['url'], f['language'])
            for row in d['languages'] for f in row['findings'] if f['counted']}
    assert seen <= counted and seen
    assert d['findings_counted'] == sum(1 for row in d['languages']
                                        for f in row['findings'] if f['counted'])


def test_a_finding_the_classification_set_aside_is_shown_and_marked():
    """An archive page's Spanish passed the paragraph gates and was then dropped by rule 13. A
    document showing the quote without the mark says the site has Spanish the class counted; one
    dropping the quote hides the reason the class came out as it did."""
    old = LA.Evidence('inline_text', 'https://x.org/gallery/2019/', 'aviso en espanol', 'Spanish',
                      rules=[6, 8, 10, 9])
    r = LA.Result(url='https://x.org/', verdict='english_only', evidence=[old],
                  rules=LA.verdict_rules([old], ''))
    d = report(r)
    rows = {row['language']: row for row in d['languages']}
    assert rows['Spanish']['findings'][0]['counted'] is False
    for form, text in _both(r).items():
        assert 'aviso en espanol' in text, form
        assert 'not counted' in text, form


def test_reporting_a_result_changes_nothing_about_it():
    """A presentation layer that mutated the reading it presents would be a classification change
    wearing a document's clothes."""
    r = _audit()
    before = json.dumps(r.to_dict(), ensure_ascii=False, sort_keys=True)
    report_text(r)
    report_html(r)
    report(r)
    assert json.dumps(r.to_dict(), ensure_ascii=False, sort_keys=True) == before


def test_the_document_is_json_serialisable_and_renders_from_the_dict():
    """The two forms render one arrangement, so they cannot come apart on what the reading said,
    and that arrangement has to survive the file it is written to."""
    r = _audit()
    d = report(r)
    back = json.loads(json.dumps(d, ensure_ascii=False))
    assert back['sections'] == d['sections']
    assert report_text(back) == report_text(d) == report_text(r)
    assert report_html(back) == report_html(d) == report_html(r)
    assert '<!doctype html>' in report_html(back)


# ------------------------------------------------------------------------------ the HTML form
def test_the_html_document_fetches_nothing_from_anywhere():
    """It is opened from an attachment, from a shared drive and from a machine with no network. A
    stylesheet or a font fetched from somewhere else makes it a page that is sometimes readable."""
    html = report_html(_audit())
    assert html.startswith('<!doctype html>') and html.rstrip().endswith('</html>')
    assert '<link' not in html.lower(), 'no external stylesheet'
    assert '<script' not in html.lower(), 'no script at all'
    assert '<img' not in html.lower(), 'no image to fetch'
    # every href in the document is one of the site's own addresses, which is a link a reader
    # follows and never an asset the page loads
    for href in re.findall(r'href="([^"]+)"', html):
        assert href.startswith('https://x.org'), href


def test_the_html_escapes_what_a_site_put_on_its_own_page():
    """The quotations are somebody else's markup, and a document that pastes them through is a
    document that renders whatever the site wrote."""
    ev = LA.Evidence('inline_text', 'https://x.org/es', '<script>alert("hola")</script> aviso',
                     'Spanish', rules=[6, 8, 10, 9])
    r = LA.Result(url='https://x.org/', verdict='true_multilingual', languages=['Spanish'],
                  evidence=[ev], rules=LA.verdict_rules([ev], ''))
    html = report_html(r)
    assert '<script>alert' not in html
    assert '&lt;script&gt;alert' in html


def test_a_quotation_is_held_to_the_length_the_document_prints():
    """Bounded by QUOTE_CHARS, and cut at a word. The bound used to be exact, which is what a bare
    slice gives, and a bare slice is what left one demo reading opening inside a Korean word; the
    quote now travels back to the nearest space, so it ends at or just under the bound."""
    long_quote = 'aviso ' * 400
    ev = LA.Evidence('inline_text', 'https://x.org/es', long_quote, 'Spanish',
                     rules=[6, 8, 10, 9])
    r = LA.Result(url='https://x.org/', verdict='true_multilingual', languages=['Spanish'],
                  evidence=[ev], rules=LA.verdict_rules([ev], ''))
    got = report(r)['languages'][0]['findings'][0]['quote']
    assert len(got) <= QUOTE_CHARS
    assert len(got) > QUOTE_CHARS - LA.QUOTE_SNAP, 'the cut travelled further than it may'
    assert got.endswith('aviso'), 'the document ends a quotation inside a word'


# ------------------------------------------------------------ a hand coding and a re-judged capture
def test_a_reading_a_person_settled_says_so():
    """A hand verdict wins over the machine's, and a document presenting it as an instrument
    reading would be this package taking credit for a person's judgement."""
    entry = {'mechanism': HAND_CODING, 'url': 'https://x.org/', 'quote': 'clicked the control',
             'language': '', 'machine_verdict': 'english_only', 'machine_languages': [],
             'human_verdict': 'machine_translate', 'coder': 'NY', 'coded_at': '2026-08-05'}
    r = {'url': 'https://x.org/', 'verdict': 'machine_translate', 'languages': [],
         'evidence': [entry], 'read_quality': {'pages_read': 4, 'sufficient': True}}
    d = report(r)
    assert d['hand_coded']['machine_verdict'] == 'english_only'
    assert d['hand_coded']['coder'] == 'NY'
    for form, text in _both(r).items():
        assert 'A person settled this reading' in text, form
        assert 'english_only' in text, form
    # and the hand coding is not shown as a language finding, since it is a statement about the site
    assert all(row['language'] != NO_LANGUAGE for row in d['languages'])


def test_a_re_judged_capture_names_what_it_could_not_carry(tmp_path):
    """What a stored capture cannot reproduce is the first thing a reader of one has to know, and a
    document is the form of the reading most likely to be read years later."""
    path = tmp_path / 'run.jsonl'
    LA._store_result(str(path), _audit(keep_pages=True))
    again = LA.rejudge(str(path), 'https://x.org/')
    d = report(again)
    codes = [lim['code'] for lim in d['unreproducible']]
    assert LA.REJUDGE_SERVER_CONFIRMATION in codes
    for form, text in _both(again).items():
        assert LA.REJUDGE_SERVER_CONFIRMATION in text, form


def test_a_reading_this_package_could_not_settle_says_which_and_why():
    """`review` puts that sentence in front of a coder. A reader of the document needs it for the
    same reason, and reading a queued site's document as a settled one is the misreading."""
    r = LA.Result(url='https://x.org/', verdict='unreachable', note='bot wall')
    d = report(r)
    assert d['unsettled_kind'] == 'unread'
    assert 'nothing is established' in d['unsettled_reason']
    for form, text in _both(r).items():
        assert 'The unsettled part of this reading' in text, form


def test_a_stored_json_row_is_reported_without_being_re_judged():
    """A census has the dict it wrote and no Result object, which is the ordinary case for this
    command: a document is asked for long after the run."""
    live = _audit()
    row = json.loads(json.dumps(live.to_dict(), ensure_ascii=False))
    d = report(row)
    assert d['url'] == live.url and d['verdict'] == live.verdict
    assert any(row['language'] == 'Spanish' for row in d['languages'])


# ------------------------------------------------------------------------------ writing a file
def test_the_form_follows_the_extension_and_the_flag_overrides_it(tmp_path):
    assert form_for('a/b/site.html') == 'html'
    assert form_for('a/b/site.HTM') == 'html'
    assert form_for('a/b/site.txt') == 'text'
    assert form_for('a/b/site.txt', 'html') == 'html'
    with pytest.raises(ValueError):
        render(_audit(), 'pdf')

    r = _audit()
    p = tmp_path / 'site.html'
    n = write_report(r, str(p))
    assert n > 0 and p.read_text(encoding='utf-8').startswith('<!doctype html>')
    q = tmp_path / 'site.txt'
    write_report(r, str(q))
    assert 'langaccess reading' in q.read_text(encoding='utf-8')


# ------------------------------------------------------------------------------ the command line
def test_the_command_line_writes_one_document_for_one_address(tmp_path, capsys):
    from langaccess import cli as CLI

    run = tmp_path / 'run.jsonl'
    LA._store_result(str(run), _audit())
    out = tmp_path / 'site.html'
    assert CLI.main(['report', str(run), 'https://x.org/', '-o', str(out)]) == CLI.EXIT_OK
    printed = capsys.readouterr().out
    assert 'written to' in printed and 'findings quoted' in printed
    doc = out.read_text(encoding='utf-8')
    assert 'not a determination of compliance' in doc
    assert 'servicios' in doc


def test_the_command_line_prints_the_text_form_with_no_output_path(tmp_path, capsys):
    from langaccess import cli as CLI

    run = tmp_path / 'run.jsonl'
    LA._store_result(str(run), _audit())
    assert CLI.main(['report', str(run)]) == CLI.EXIT_OK
    out = capsys.readouterr().out
    assert 'langaccess reading' in out and 'Limits' in out


def test_a_run_holding_no_records_is_not_a_finished_report(tmp_path, capsys):
    from langaccess import cli as CLI

    run = tmp_path / 'empty.jsonl'
    run.write_text('', encoding='utf-8')
    assert CLI.main(['report', str(run)]) == CLI.EXIT_NOTHING
    assert 'nothing to report on' in capsys.readouterr().err


def test_every_address_in_a_run_gets_its_own_document_and_none_is_lost(tmp_path, capsys):
    from langaccess import cli as CLI

    run = tmp_path / 'run.jsonl'
    LA._store_result(str(run), _audit())
    LA._store_result(str(run), LA.Result(url='https://y.org/', verdict='english_only',
                                         read_quality=LA.read_quality_of(4)))
    # a row that never held a reading, which has to be named rather than quietly not written
    with open(run, 'a', encoding='utf-8') as fh:
        fh.write(json.dumps({'url': 'https://z.org/', 'verdict': ''}) + '\n')
    where = tmp_path / 'docs'
    where.mkdir()
    assert CLI.main(['report', str(run), '--all', '--dir', str(where)]) == CLI.EXIT_OK
    out = capsys.readouterr().out
    assert '3 records read' in out
    assert 'documents written   2' in out
    assert 'https://z.org/' in out, 'a record holding no reading is named, not dropped'
    assert len(list(where.glob('*.html'))) == 2


def test_a_run_of_records_that_hold_no_reading_writes_nothing_and_says_so(tmp_path, capsys):
    from langaccess import cli as CLI

    run = tmp_path / 'run.jsonl'
    run.write_text(json.dumps({'url': 'https://z.org/', 'verdict': ''}) + '\n', encoding='utf-8')
    where = tmp_path / 'docs'
    where.mkdir()
    assert CLI.main(['report', str(run), '--all', '--dir', str(where)]) == CLI.EXIT_NOTHING
    assert 'no document was written' in capsys.readouterr().err
    assert list(where.iterdir()) == []


def test_two_addresses_of_one_site_do_not_land_on_one_file(tmp_path, capsys):
    from langaccess import cli as CLI

    run = tmp_path / 'run.jsonl'
    for u in ('https://x.org/one/', 'https://x.org/two/', 'https://x.org/one'):
        LA._store_result(str(run), LA.Result(url=u, verdict='english_only',
                                             read_quality=LA.read_quality_of(4)))
    where = tmp_path / 'docs'
    where.mkdir()
    assert CLI.main(['report', str(run), '--all', '--dir', str(where)]) == CLI.EXIT_OK
    assert len(list(where.glob('*.html'))) == 3, 'a collision is numbered, never overwritten'


def test_an_address_the_run_does_not_hold_is_a_usage_error(tmp_path):
    from langaccess import cli as CLI

    run = tmp_path / 'run.jsonl'
    LA._store_result(str(run), _audit())
    with pytest.raises(SystemExit) as got:
        CLI.main(['report', str(run), 'https://nowhere.example/'])
    assert got.value.code == CLI.EXIT_USAGE

def test_every_published_class_has_a_meaning_sentence():
    """The renderer looks the verdict up with .get and an absent class prints a class name with no
    meaning at all, in the document handed to an organization. The two vocabularies are one
    decision, so they are asserted equal rather than trusted to agree."""
    from langaccess.report import CLASS_MEANING
    from langaccess.review import VERDICTS
    assert set(CLASS_MEANING) == set(VERDICTS)
    for k, v in CLASS_MEANING.items():
        assert isinstance(v, str) and len(v) > 40, k
