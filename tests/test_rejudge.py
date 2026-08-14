# -*- coding: utf-8 -*-
"""Judging a stored capture again, without going back to the web.

`store=` has written the pages of every audited site since it was added, and nothing could read
them back. That gap is what made evaluating a rule change cost two hours of live crawling, made
every diagnosis refetch the same sites, and made a validation sample impossible to code twice
against one snapshot: the second coding read a different web.

Two things have to hold or the function is worse than not having it. It must not touch the network,
because a re-judge that quietly refetches is a live audit with a misleading name. And it must apply
the SAME detection and judgement the live audit applies, because a second copy of the rule is a
second answer.
"""
import asyncio
import json

import pytest

from langaccess import core as LA
from test_engineering import _MapBrowser, _PlainClient, _page


# A site whose second language is on one interior page: an English home page linking /servicios,
# and a Spanish services page behind it. Small on purpose, so that what the browser laid out and
# what `_text_from_html` reads back out of the stored HTML are the same text and the round trip is
# a test of the judgement rather than of the two extractors.
_ES = ('Nuestros servicios para la comunidad son gratuitos. Ofrecemos informacion y recursos '
       'para las familias que necesitan ayuda con este proceso, y todos pueden hacer una cita. ')
_HOME_TEXT = 'Welcome to our center. We help families with legal questions every day of the week.'
_SITE = {
    'https://x.org/': ('<html><head><title>Centro</title></head><body>'
                       '<a href="/servicios">Servicios</a><p>' + _HOME_TEXT + '</p></body></html>',
                       _HOME_TEXT, 200),
    'https://x.org/servicios': _page(_ES * 3),
}


def _audit_and_store(site, path, url='https://x.org/', **kw):
    """Run the crawl over a fake browser and write the record the way `audit_async(store=)` does."""
    b = _MapBrowser(site, plain=_PlainClient({}))
    r = asyncio.run(LA._audit_async(url, browser=b, keep_pages=True, **kw))
    LA._store_result(str(path), r)
    return r


def test_a_stored_capture_is_judged_to_the_same_answer_as_the_live_run(tmp_path):
    """The round trip. Audit, store, re-judge, and the verdict, the languages, the authorship and
    the sufficiency are the ones the live crawl reached."""
    path = tmp_path / 'run.jsonl'
    live = _audit_and_store(_SITE, path)
    assert live.verdict == 'true_multilingual', 'the fixture has to have something to find'

    again = LA.rejudge(str(path), 'https://x.org/')
    assert again.verdict == live.verdict
    assert again.languages == live.languages == ['English', 'Spanish']
    assert again.authorship == live.authorship == LA.AUTHOR_AUTHORED
    assert again.sufficiency == live.sufficiency
    assert again.by_language == live.by_language
    assert again.machine_translation == live.machine_translation
    assert again.rules == live.rules
    assert [e.mechanism for e in again.evidence] == [e.mechanism for e in live.evidence]
    assert [e.language for e in again.evidence] == [e.language for e in live.evidence]
    assert [e.sufficiency for e in again.evidence] == [e.sufficiency for e in live.evidence]
    assert [e.authorship for e in again.evidence] == [e.authorship for e in live.evidence]
    # and the reading it re-judged keeps the date and the version of the reading it came from,
    # because a re-judged row describes the site as it was, not as it is
    assert again.audited_at == live.audited_at
    assert again.tool_version == live.tool_version


def test_a_re_judge_says_what_it_could_not_reproduce(tmp_path):
    """The fields that cannot match are named rather than silently answered differently. A live
    audit reproduces everything by definition, so the list is empty there and is the first thing a
    reader of a re-judged row has to see."""
    path = tmp_path / 'run.jsonl'
    live = _audit_and_store(_SITE, path)
    again = LA.rejudge(str(path), 'https://x.org/')

    assert live.unreproducible == []
    assert set(again.unreproducible) == {LA.REJUDGE_BROWSER_TEXT, LA.REJUDGE_SERVER_CONFIRMATION,
                                         LA.REJUDGE_CLICKED_CONTROLS, LA.REJUDGE_ROUTE_PROBE,
                                         LA.REJUDGE_PAGE_ORIGIN, LA.REJUDGE_ESCALATION}
    for code in again.unreproducible:
        assert code in LA.REJUDGE_LIMITS
        assert len(LA.REJUDGE_LIMITS[code]) > 80, f'{code} needs a reason a person can act on'
    # and the codes survive into the row a census would store
    back = json.loads(json.dumps(again.to_dict(), ensure_ascii=False))
    assert LA.REJUDGE_SERVER_CONFIRMATION in back['unreproducible']


def test_a_re_judge_makes_no_network_call_at_all(tmp_path, monkeypatch):
    """A re-judge that quietly refetches is a live audit with a misleading name, and it would make
    the archive useless for the thing it exists for: reading the pages as they were."""
    path = tmp_path / 'run.jsonl'
    _audit_and_store(_SITE, path)

    def boom(*a, **k):
        raise AssertionError('the re-judge reached the network')

    async def aboom(*a, **k):
        raise AssertionError('the re-judge reached the network')

    for name in ('_playwright', '_launch', '_plain_fetch', '_confirm_server_html',
                 '_robots_allowed', '_sitemap_pages', '_host_is_public', '_read',
                 '_click_language_controls', '_install_host_guard'):
        monkeypatch.setattr(LA, name, aboom if name != '_playwright' else boom)
    monkeypatch.setattr(LA.asyncio, 'get_running_loop', boom)

    r = LA.rejudge(str(path), 'https://x.org/')
    assert isinstance(r, LA.Result)
    assert r.verdict == 'true_multilingual'
    assert r.languages == ['English', 'Spanish']


def test_the_judgement_is_the_same_functions_and_not_a_second_copy(tmp_path, monkeypatch):
    """If `verdict_for` moves, the re-judge moves with it. A parallel implementation would answer
    the old way and nothing would say so."""
    path = tmp_path / 'run.jsonl'
    _audit_and_store(_SITE, path)
    monkeypatch.setattr(LA, 'verdict_for', lambda *a, **k: 'a made-up class')
    assert LA.rejudge(str(path), 'https://x.org/').verdict == 'a made-up class'


def test_a_record_can_be_handed_over_directly_as_well_as_by_path(tmp_path):
    path = tmp_path / 'run.jsonl'
    _audit_and_store(_SITE, path)
    rec = list(LA.read_store(str(path)))[0]
    assert LA.rejudge(rec).verdict == 'true_multilingual'
    # a file with one record needs no url; a file with several does
    _audit_and_store(_SITE, path, url='https://x.org/')
    with pytest.raises(ValueError):
        LA.rejudge(str(path))
    assert LA.rejudge(str(path), 'https://x.org').verdict == 'true_multilingual'
    with pytest.raises(KeyError):
        LA.rejudge(str(path), 'https://not-in-the-file.org')


def test_a_gzipped_store_is_read_back(tmp_path):
    path = tmp_path / 'run.jsonl.gz'
    _audit_and_store(_SITE, path)
    assert LA.rejudge(str(path)).verdict == 'true_multilingual'


def test_a_site_that_was_never_read_re_judges_to_what_it_was(tmp_path):
    """A record with no pages is a site nobody read, and there is nothing to re-read. Deriving
    `english_only` from an empty capture would say something that was never checked, which is the
    one confusion the classes exist to prevent."""
    path = tmp_path / 'run.jsonl'
    b = _MapBrowser({'https://www.facebook.com/someorg': _page('A page about the organization.')})
    live = asyncio.run(LA._audit_async('https://www.facebook.com/someorg', browser=b,
                                       keep_pages=True))
    LA._store_result(str(path), live)
    again = LA.rejudge(str(path))
    assert again.verdict == live.verdict == 'unreachable'
    assert again.rules == live.rules == [1]
    assert again.unreproducible == [LA.REJUDGE_NO_PAGES]


# ---------------------------------------------------------------- what a capture cannot carry
_WIDGET_SITE = {
    'https://y.org/': ('<html><head><title>Casa</title>'
                       '<script src="//translate.google.com/translate_a/element.js"></script>'
                       '</head><body><p>' + _HOME_TEXT + '</p>'
                       '<a href="/services">Services</a></body></html>',
                       _HOME_TEXT, 200),
    'https://y.org/services': _page('Our office helps with paperwork. ' + _ES * 2),
}


def test_the_server_confirmation_is_carried_forward_rather_than_re_derived(tmp_path):
    """The decisive authored-against-widget test fetches the address with no JavaScript running.
    A stored page is the RENDERED DOM, which a client-side widget has already written into, so the
    test cannot be re-run from it. The mark is carried from the reading that could take it, and the
    fact that it was carried is on the record."""
    path = tmp_path / 'run.jsonl'
    server = {'https://y.org/services': '<html><body><p>' + _ES * 2 + '</p></body></html>'}
    b = _MapBrowser(_WIDGET_SITE, plain=_PlainClient(server))
    live = asyncio.run(LA._audit_async('https://y.org/', browser=b, keep_pages=True))
    LA._store_result(str(path), live)

    assert live.machine_translation == 'Google Translate'
    assert any(e.server_html for e in live.evidence), 'the fixture has to confirm one page'
    assert live.verdict == 'true_multilingual'

    again = LA.rejudge(str(path))
    assert again.machine_translation == 'Google Translate'
    assert again.verdict == live.verdict
    assert again.authorship == live.authorship == LA.AUTHOR_AUTHORED
    assert [e.server_html for e in again.evidence] == [e.server_html for e in live.evidence]
    assert LA.REJUDGE_SERVER_CONFIRMATION in again.unreproducible


def test_a_clicked_control_is_carried_forward_because_it_cannot_be_clicked_again():
    """A control with no href is found by clicking it in a browser. Nothing about that is in a
    stored document, so the evidence is carried and the limit is stated."""
    rec = {'url': 'https://z.org/', 'verdict': 'true_multilingual', 'machine_translation': '',
           'note': '', 'pages_read': 1, 'audited_at': '2026-07-30T00:00:00Z',
           'tool_version': '0.2.0',
           'evidence': [{'mechanism': 'language_control', 'url': 'https://z.org/',
                         'quote': 'Nuestros servicios son gratuitos', 'language': 'Spanish',
                         'server_html': False, 'server_plugin': False,
                         'authorship': '', 'sufficiency': 0, 'rules': [6, 8, 9]}],
           'pages': {'https://z.org/': '<html><body><p>' + _HOME_TEXT + '</p></body></html>'}}
    r = LA.rejudge(rec)
    assert [e.mechanism for e in r.evidence] == ['language_control']
    assert r.evidence[0].language == 'Spanish'
    assert r.evidence[0].rules == [6, 8, 9]
    assert LA.REJUDGE_CLICKED_CONTROLS in r.unreproducible
    # and it is judged by the rule the live audit applies, not by a rule of its own
    assert r.verdict == LA.verdict_for(r.evidence, '')


def test_rule_fifteen_comes_off_the_stored_note_because_the_route_is_not_captured():
    """The crawl never stores a page that came back identical to the home page, so whether an
    advertised route returned English is not in the capture. It is read from the note, which is
    where the live audit wrote it, and the limit says so."""
    rec = {'url': 'https://w.org/', 'note': 'locale route returned English',
           'machine_translation': 'Weglot', 'pages_read': 1, 'evidence': [],
           'pages': {'https://w.org/':
                     '<html><head><script src="//cdn.weglot.com/weglot.min.js"></script></head>'
                     '<body><p>' + _HOME_TEXT + '</p></body></html>'}}
    r = LA.rejudge(rec)
    assert r.machine_translation == 'Weglot', 'the widget is re-read from the stored document'
    assert r.verdict == 'english_only'
    assert 15 in r.rules
    assert LA.REJUDGE_ROUTE_PROBE in r.unreproducible
    # without the note the same capture is machine_translate, which is what the live audit said
    # about a widget that was not shown to translate nothing
    r2 = LA.rejudge(dict(rec, note=''))
    assert r2.verdict == 'machine_translate'


def test_a_whole_store_file_is_judged_at_once(tmp_path):
    path = tmp_path / 'run.jsonl'
    _audit_and_store(_SITE, path)
    b = _MapBrowser(_WIDGET_SITE, plain=_PlainClient({}))
    LA._store_result(str(path), asyncio.run(LA._audit_async('https://y.org/', browser=b,
                                                            keep_pages=True)))
    got = LA.rejudge_store(str(path))
    assert [r.url for r in got] == ['https://x.org/', 'https://y.org/']
    assert [r.url for r in LA.rejudge_store(str(path), ['https://y.org'])] == ['https://y.org/']


def test_the_cli_re_judges_a_store_file_without_a_browser(tmp_path, capsys):
    from langaccess import cli as CLI

    path = tmp_path / 'run.jsonl'
    _audit_and_store(_SITE, path)
    assert CLI.main(['--rejudge', str(path), '--json']) == 0
    rows = [json.loads(l) for l in capsys.readouterr().out.splitlines() if l.strip()]
    assert len(rows) == 1
    assert rows[0]['verdict'] == 'true_multilingual'
    assert rows[0]['languages'] == ['English', 'Spanish']
    assert LA.REJUDGE_BROWSER_TEXT in rows[0]['unreproducible']
    assert rows[0]['rules']

    # and the human output names the rules and the limits
    assert CLI.main(['--rejudge', str(path)]) == 0
    out = capsys.readouterr().out
    assert 'rules' in out and 'not re-run' in out


# A RECORD IN THE OLD SHAPE, AS THE VALIDATION-ERA STORES ON DISK WROTE IT.
#
# The axis that answers "who produced this text" was called `provenance` in earlier revisions and
# is called `authorship` now. A stored capture is read years after it was taken, which is why
# one is stored, so the key those revisions wrote has to go on answering under its own name
# for good. That is a different promise from the deprecated aliases in the code, which last one
# release.
def _as_old_shape(rec):
    """The same record with the old key names, at every depth, as those stores hold it."""
    def ren(o):
        if isinstance(o, dict):
            return {('provenance' if k == 'authorship' else k): ren(v) for k, v in o.items()}
        if isinstance(o, list):
            return [ren(v) for v in o]
        return o
    out = ren(rec)
    # the stamp the validation capture store actually carries on its old-shape rows
    out['tool_version'] = '0.2.0'
    return out


def test_a_record_in_the_old_shape_still_round_trips(tmp_path):
    """Re-judge a capture in the old shape and get the answer the same capture gives today."""
    path = tmp_path / 'run.jsonl'
    _audit_and_store(_SITE, path)
    now = json.loads((tmp_path / 'run.jsonl').read_text(encoding='utf-8').splitlines()[0])
    old = _as_old_shape(now)
    assert 'provenance' in old['evidence'][0] and 'authorship' not in old['evidence'][0], (
        'the fixture has to actually be in the old shape or this test proves nothing')

    a, b = LA.rejudge(now), LA.rejudge(old)
    assert b.verdict == a.verdict == 'true_multilingual'
    assert b.languages == a.languages == ['English', 'Spanish']
    assert b.authorship == a.authorship == LA.AUTHOR_AUTHORED
    assert b.sufficiency == a.sufficiency
    assert b.by_language == a.by_language
    assert b.rules == a.rules
    assert [(e.mechanism, e.language, e.authorship, e.sufficiency) for e in b.evidence] == \
           [(e.mechanism, e.language, e.authorship, e.sufficiency) for e in a.evidence]
    # the record's own date and stamp are carried, so a re-judged old row still says what wrote it
    assert b.tool_version == '0.2.0'


def test_the_old_key_is_read_off_a_stored_row_and_not_merely_re_derived(tmp_path):
    """The decisive case, because agreement above could be the derivation agreeing by luck.

    `authorship_of` prefers a value the audit already recorded over deriving one. An old-shape row
    records that value under `provenance`, so the alias is doing work exactly when the stored value
    is one the derivation would NOT reach on its own. `server_plugin` is such a value here: nothing
    about this evidence carries a CMS marker, so a derivation says `authored`.
    """
    row = {'mechanism': 'inline_text', 'url': 'https://x.org/a', 'language': 'Spanish',
           'quote': '...', 'server_html': True, 'server_plugin': False}
    assert LA.authorship_of(dict(row)) == LA.AUTHOR_AUTHORED, 'the derivation says authored'
    assert LA.authorship_of(dict(row, provenance='server_plugin')) == LA.AUTHOR_SERVER_PLUGIN
    assert LA.authorship_of(dict(row, authorship='server_plugin')) == LA.AUTHOR_SERVER_PLUGIN
    # the new key wins where a row somehow carries both, since it is the one this version writes
    assert LA.authorship_of(dict(row, authorship='client_widget',
                                 provenance='server_plugin')) == LA.AUTHOR_CLIENT_WIDGET


def test_read_store_hands_back_an_old_shape_row_untouched_and_the_judgement_reads_it(tmp_path):
    """`read_store` is the raw reader, and the census judges those dicts without `rejudge`.

    So the stored-key promise has to hold for the judgement functions taken on their own, not only
    for the re-judge that rebuilds evidence from the pages.
    """
    path = tmp_path / 'run.jsonl'
    _audit_and_store(_SITE, path)
    now = json.loads(path.read_text(encoding='utf-8').splitlines()[0])
    old = _as_old_shape(now)
    old_path = tmp_path / 'old_shape.jsonl'
    old_path.write_text(json.dumps(old, ensure_ascii=False) + '\n', encoding='utf-8')

    got = list(LA.read_store(str(old_path)))
    assert len(got) == 1 and 'provenance' in got[0]['evidence'][0]

    ev_old, ev_now = got[0]['evidence'], now['evidence']
    assert LA.verdict_for(ev_old, '') == LA.verdict_for(ev_now, '') == 'true_multilingual'
    assert LA.authorship_summary(ev_old, '') == LA.authorship_summary(ev_now, '')
    assert LA.language_summary(ev_old, '') == LA.language_summary(ev_now, '')
    assert [LA.authorship_of(e) for e in ev_old] == [LA.authorship_of(e) for e in ev_now]


def test_the_deprecated_names_still_answer_for_one_release():
    """Code written against earlier revisions names the axis `provenance`, and this release keeps
    answering to that.

    Deliberately without a warning. A run over thousands of sites reads these on every piece of
    evidence, so a per-read warning is noise; the deprecation is in the docstrings and in the
    docstring of each name below.
    """
    import langaccess

    assert (langaccess.PROV_AUTHORED, langaccess.PROV_SERVER_PLUGIN,
            langaccess.PROV_CLIENT_WIDGET, langaccess.PROV_NONE) == (
        LA.AUTHOR_AUTHORED, LA.AUTHOR_SERVER_PLUGIN, LA.AUTHOR_CLIENT_WIDGET, LA.AUTHOR_NONE)
    for name in ('provenance_of', 'provenance_summary',
                 'PROV_AUTHORED', 'PROV_SERVER_PLUGIN', 'PROV_CLIENT_WIDGET', 'PROV_NONE'):
        assert name in langaccess.__all__, '%s is deprecated, not withdrawn' % name

    ev = [{'mechanism': 'inline_text', 'url': 'https://x.org/a', 'language': 'Spanish',
           'quote': '...'}]
    assert langaccess.provenance_of(ev[0]) == LA.authorship_of(ev[0])
    assert langaccess.provenance_summary(ev, '') == LA.authorship_summary(ev, '')
    assert 'authorship' in langaccess.provenance_of.__doc__

    r = LA.Result(url='https://x.org/', authorship=LA.AUTHOR_SERVER_PLUGIN)
    assert r.provenance == r.authorship == LA.AUTHOR_SERVER_PLUGIN
    e = LA.Evidence('inline_text', 'https://x.org/', language='Spanish',
                    authorship=LA.AUTHOR_CLIENT_WIDGET)
    assert e.provenance == e.authorship == LA.AUTHOR_CLIENT_WIDGET
    # and the record this version WRITES carries only the new name
    assert 'authorship' in r.to_dict() and 'provenance' not in r.to_dict()


# ---------------------------------------------------------------- which bytes did the judging
#
# A re-judged Result carried the CAPTURING run's `tool_version` forward and recorded nothing about
# the code that applied the rules, so a figure computed from a re-judged run could not name the
# build that produced it. Every figure this package has published was computed that way, and the
# sha256 beside each one was attached by the measurement harness rather than carried by the result.


def test_a_re_judged_result_names_both_the_build_that_captured_it_and_the_one_that_judged_it(
        tmp_path, monkeypatch):
    """Four facts, not two: which bytes were read and when they were fetched, which rules were
    applied to them and when."""
    path = tmp_path / 'run.jsonl'
    monkeypatch.setattr(LA, '_tool_version', lambda: '0.0.1-capture')
    monkeypatch.setattr(LA, '_utc_now', lambda: '2020-01-01T00:00:00Z')
    live = _audit_and_store(_SITE, path)
    assert live.tool_version == live.judged_version == '0.0.1-capture', (
        'a live audit captures and judges in one act, so the two versions agree there')
    assert live.audited_at == live.judged_at == '2020-01-01T00:00:00Z'

    monkeypatch.setattr(LA, '_tool_version', lambda: '9.9.9-rejudge')
    monkeypatch.setattr(LA, '_utc_now', lambda: '2026-08-05T12:00:00Z')
    again = LA.rejudge(str(path), 'https://x.org/')
    assert again.tool_version == '0.0.1-capture', 'the capture keeps its own version'
    assert again.audited_at == '2020-01-01T00:00:00Z', 'and its own clock'
    assert again.judged_version == '9.9.9-rejudge', 'the judging build is the one running now'
    assert again.judged_at == '2026-08-05T12:00:00Z'
    # the pair a consumer tests to tell a re-judged row from a live one, without being told
    assert (again.tool_version == again.judged_version) is False
    assert (live.tool_version == live.judged_version) is True
    # and it survives the round trip through the record a store writes
    assert LA.rejudge(again.to_dict(with_pages=True)).judged_version == '9.9.9-rejudge'


def test_a_capture_with_no_pages_still_names_the_build_that_judged_it(monkeypatch):
    """The early return for a record holding no pages is a re-judge too, and a Result that carries
    the stored verdict forward is still a Result some figure will be computed from."""
    rec = {'url': 'https://x.org/', 'verdict': 'unreachable', 'pages': {},
           'tool_version': '0.0.1-capture', 'audited_at': '2020-01-01T00:00:00Z'}
    monkeypatch.setattr(LA, '_tool_version', lambda: '9.9.9-rejudge')
    r = LA.rejudge(rec)
    assert r.unreproducible == [LA.REJUDGE_NO_PAGES]
    assert r.tool_version == '0.0.1-capture' and r.judged_version == '9.9.9-rejudge'
    assert r.judged_at


def test_a_re_judge_under_a_different_build_is_recorded_and_never_refused(tmp_path, monkeypatch):
    """Lighthouse hard-fails an audit-mode run whose settings differ from the gathering run's and
    names the differing key (`core/runner.js`). The equivalent refusal does not belong here, and the
    difference is what `rejudge` is FOR: judging a stored capture under code the capture was not
    taken with is how a rule change is evaluated over a whole run in seconds instead of over two
    hours of live crawling. A refusal would forbid the feature it is meant to protect. What the
    guard is actually about, a comparison whose two halves were produced differently, is served by
    RECORDING the difference on the row, where a consumer can filter on it.

    The prerequisite the package still lacks is a level below this: `_store_result` writes no crawl
    settings at all, so a capture taken under `deep=True` and one taken under `deep=False` are
    indistinguishable in a store and no guard anywhere could compare them. The second half of this
    test is that statement made mechanical, so it fails on the day the settings do get written and
    somebody has to decide what the guard should do with them.
    """
    path = tmp_path / 'run.jsonl'
    monkeypatch.setattr(LA, '_tool_version', lambda: '0.0.1-capture')
    _audit_and_store(_SITE, path)
    monkeypatch.setattr(LA, '_tool_version', lambda: '9.9.9-rejudge')
    r = LA.rejudge(str(path), 'https://x.org/')       # no exception, no warning, a reading
    assert r.verdict == 'true_multilingual'
    assert r.judged_version != r.tool_version

    stored = json.loads(open(str(path), encoding='utf-8').readline())
    settings = [k for k in stored
                if k in ('max_pages', 'deep', 'escalate', 'respect_robots', 'settings')]
    assert settings == [], (
        'the store now records %s, so a re-judge can compare the capture it was taken under with '
        'the one it is being judged under, and this package has to decide whether that is a '
        'refusal, a note on the Result, or nothing' % settings)
