# -*- coding: utf-8 -*-
"""The working behind one verdict, and the line between reporting it and inventing it.

`explain` is a presentation layer. Everything it prints was written by the audit that produced the
Result, and the tests that matter here are the ones that hold it to that: it moves no verdict, it
reads the same `counted_evidence` the verdict read, and it never turns the absence of a rule number
into the claim that the rule did not apply.

That last one is the whole risk of the feature. `Result.rules` names what FIRED. A reader who takes
silence for a negative finding reads "rule 17 is not listed" as "this site does not mirror its front
door", which the record does not say and this package has no way to say. So the one negative finding
here covers exactly the rules `verdict_rules` asks on every call, and
`test_the_tested_set_is_exactly_what_verdict_rules_asks` pins that set against the function itself
rather than against a comment.
"""
import asyncio
import json

from langaccess import core as LA
from langaccess import explain, explain_text
from langaccess.explain import (EVIDENCE_SHOWN, FIRED, FIRED_UNCOUNTED, NOT_IN_CODE, NOT_RECORDED,
                                STAGES, TESTED_ALWAYS, TESTED_NOT_FIRED, TESTED_WITH_WIDGET,
                                TESTED_WITHOUT_WIDGET, rules_tested)
from test_engineering import _MapBrowser, _PlainClient, _page


# Built like the re-judge fixture: an English home page linking a Spanish services page. A
# real crawl over a fake browser, so what is explained is a reading this package actually took.
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


def test_the_explanation_names_the_rules_that_decided_the_site():
    """The numbers on the result, with their titles, and nothing invented alongside them."""
    r = _audit()
    assert r.verdict == 'true_multilingual', 'the fixture has to have something to explain'
    x = explain(r)
    assert x['rules'][FIRED] == sorted(r.rules)
    titles = {row['number']: row['title']
              for stage in x['stages'] for row in stage['rules']}
    for n in r.rules:
        assert titles[n] == LA.RULES[n].title


def test_every_numbered_rule_appears_exactly_once_and_in_pipeline_order():
    """A rule this package holds itself to and does not report on is the state the registry exists
    to prevent, and a rule reported twice is a reader counting it twice."""
    numbers = [row['number'] for stage in explain(_audit())['stages'] for row in stage['rules']]
    assert sorted(numbers) == list(range(1, 18))
    assert len(numbers) == len(set(numbers))
    # since 2026-08-09 the numbering IS the stage order, which is the release numbering's
    # promise: rule 2 answers before a page is read and rule 14 after everything is
    assert numbers == sorted(numbers)


def test_the_evidence_behind_a_rule_carries_its_address_and_its_words():
    """A rule number on its own is a second conclusion. The page it was read at and the text that
    decided it make it checkable."""
    x = explain(_audit())
    rows = {row['number']: row for stage in x['stages'] for row in stage['rules']}
    got = rows[6]['evidence']                    # the paragraph gate, on every finding
    assert got, 'rule 6 decided a finding here and has to say which'
    assert any(e['url'] == 'https://x.org/servicios' and 'servicios' in e['quote']
               and e['language'] == 'Spanish' for e in got)


def test_the_two_axes_are_reported_per_language_with_the_rung_named():
    r = _audit()
    x = explain(r)
    assert x['authorship'] == r.authorship
    assert x['sufficiency_name'] == LA.SUFFICIENCY_NAMES[r.sufficiency]
    assert x['by_language']['Spanish']['authorship'] == LA.AUTHOR_AUTHORED
    assert x['by_language']['Spanish']['sufficiency_name'] in LA.SUFFICIENCY_NAMES.values()
    assert x['by_language']['Spanish']['counted'] is True


def test_the_read_quality_is_reported_and_an_absence_claim_says_so():
    """`english_only` is the one class of the four that asserts an absence, and what it is worth is
    what the search behind it was worth. The flag is on the record so a reader does not have to
    remember which of the four verdicts this applies to."""
    english = {'https://x.org/': _page(_HOME_TEXT)}
    r = _audit(english)
    assert r.verdict == 'english_only'
    x = explain(r)
    assert x['absence_claim'] is True
    assert x['read_quality'] == r.read_quality
    text = explain_text(r)
    assert 'absence claim' in text
    assert 'pages read' in text

    x2 = explain(_audit())
    assert x2['absence_claim'] is False, 'a verdict that found something asserts no absence'


# ------------------------------------------------------------ the line this feature must not cross
def test_the_tested_set_is_exactly_what_verdict_rules_asks():
    """The one negative finding this module makes, pinned against the function that makes it.

    Each number below is claimed to be a rule `verdict_rules` asks about on every call, on the
    branch named. The claim is checked by constructing inputs that make it fire: a rule that cannot
    be made to fire on that branch is not being asked about there, and reporting it as tested and
    not fired would be this package inventing a negative.
    """
    es = LA.Evidence('inline_text', 'https://x.org/services/', 'aviso', 'Spanish',
                     rules=[6, 8, 10, 9], server_html=True)
    archive = LA.Evidence('inline_text', 'https://x.org/category/past_events/', 'Weihnachtsfeier',
                          'German', rules=[6, 8, 10, 9])
    marker = LA.Evidence('translation_plugin', 'https://x.org/', 'wpml', '', rules=[11])

    fires_without_widget = set(LA.verdict_rules([es, archive, marker], '', advertised_roots=5))
    fires_widget_plain = set(LA.verdict_rules([es, archive, marker], 'Google Translate'))
    # the overrides fire only where the authored reading did not win, so their exclusivity
    # is pinned on an empty reading; 15 and 16 are both ASKED on every widget call and can
    # never both FIRE on one, since the server's answer outranks the client's
    fires_route = set(LA.verdict_rules([], 'Google Translate', route_was_english=True))
    fires_dead = set(LA.verdict_rules([], 'Google Translate', control_dead=True))
    fires_with_widget = fires_widget_plain | fires_route | fires_dead
    assert set(TESTED_ALWAYS) <= fires_without_widget & fires_widget_plain
    assert set(TESTED_WITH_WIDGET) <= fires_with_widget
    assert 15 in fires_route and 16 not in fires_route
    assert 16 in fires_dead and 15 not in fires_dead
    # and neither override reaches a reading the authored evidence already settled
    settled = set(LA.verdict_rules([es, archive, marker], 'Google Translate',
                                   route_was_english=True, control_dead=True))
    assert 15 not in settled and 16 not in settled
    assert set(TESTED_WITHOUT_WIDGET) <= fires_without_widget
    # and the two branches are branches: rule 17 cannot fire where a vendor was named, and rules 14
    # and 6 cannot fire where none was
    assert not set(TESTED_WITHOUT_WIDGET) & fires_with_widget
    assert not set(TESTED_WITH_WIDGET) & fires_without_widget


def test_a_rule_that_was_never_asked_is_unrecorded_and_not_denied():
    """The defect this feature could most easily introduce. Rule 5 is about which pages the crawl
    kept; nothing in a Result records whether it was reached, so the explanation says so instead of
    reporting a rule that did not fire."""
    x = explain(_audit())
    assert 5 in x['rules'][NOT_RECORDED]
    assert 5 not in x['rules'][TESTED_NOT_FIRED]
    rows = {row['number']: row for stage in x['stages'] for row in stage['rules']}
    assert rows[5]['status'] == NOT_RECORDED
    # and the two words are different words in the printed form as well
    text = explain_text(_audit())
    assert 'unrecorded' in text and 'not fired' in text


def test_a_site_stopped_before_the_browser_claims_nothing_below_it():
    """A third-party directory profile answers before a browser is started, so `verdict_rules`
    never ran and no rule under it was tested. An explanation that reported rules 11, 12, 10 and 13
    as tested and not fired here would be describing a function that was not called. The stop
    carries no rule number since 2026-08-08, when rule 5 left the published set, so the note is
    what says why and the explanation still has to claim nothing."""
    r = asyncio.run(LA._audit_async('https://app.candid.org/profiles/0000000'))
    assert r.verdict == 'unreachable' and r.rules == []
    assert 'directory profile' in r.note
    assert rules_tested(r) == set()
    x = explain(r)
    assert x['rules'][TESTED_NOT_FIRED] == []


def test_no_rule_is_carried_without_an_implementation():
    """The bucket exists because rule 12 once needed it, and rule 12 left the published set with
    the validation table it scored. Every rule that remains names the code that applies it, so a
    number a reader looks up resolves to something in this package."""
    x = explain(_audit())
    assert x['rules'][NOT_IN_CODE] == []
    assert all(r.enforced_in for r in LA.RULES.values())


def test_a_gate_that_passed_a_finding_the_verdict_threw_away_says_which():
    """An archive page's Spanish passes rules 6, 8, 9 and 10 and is then dropped by rule 13. Both
    halves are on the record, and reporting only the first would say the site has Spanish the
    verdict counted."""
    old = LA.Evidence('inline_text', 'https://x.org/gallery/2019/', 'aviso en espanol', 'Spanish',
                      rules=[6, 8, 10, 9])
    r = LA.Result(url='https://x.org/', verdict='english_only', evidence=[old],
                  rules=LA.verdict_rules([old], ''))
    x = explain(r)
    assert 13 in x['rules'][FIRED]
    assert 6 in x['rules'][FIRED_UNCOUNTED], 'the gate ran and its finding did not reach the class'
    rows = {row['number']: row for stage in x['stages'] for row in stage['rules']}
    assert rows[13]['evidence'][0]['url'] == 'https://x.org/gallery/2019/'
    assert rows[6]['evidence'][0]['counted'] is False


def test_which_evidence_was_counted_comes_from_the_function_the_verdict_used():
    """Not a second copy of the counting rule. If `counted_evidence` changes, this changes with it."""
    r = _audit()
    x = explain(r)
    counted = {(LA._ev_url(e), LA._ev_lang(e))
               for e in LA.counted_evidence(r.evidence, r.machine_translation)}
    seen = {(e['url'], e['language'])
            for stage in x['stages'] for row in stage['rules'] for e in row['evidence']
            if e['counted']}
    assert seen <= counted and seen


def test_explaining_a_result_changes_nothing_about_it():
    """A presentation layer that mutated the reading it presents would be a classification change
    wearing a report's clothes."""
    r = _audit()
    before = json.dumps(r.to_dict(), ensure_ascii=False, sort_keys=True)
    explain_text(r)
    explain(r)
    assert json.dumps(r.to_dict(), ensure_ascii=False, sort_keys=True) == before


# ------------------------------------------------------------ a stored capture and a stored row
def test_a_re_judged_capture_is_explained_and_names_what_it_could_not_carry(tmp_path):
    """Re-judging a capture is how this package is normally debugged, so an explanation that only
    worked on a live audit would not be reaching the case it exists for. What a capture cannot
    reproduce is the first thing a reader of one has to see."""
    path = tmp_path / 'run.jsonl'
    live = _audit(keep_pages=True)
    LA._store_result(str(path), live)
    again = LA.rejudge(str(path), 'https://x.org/')

    x = explain(again)
    assert x['verdict'] == live.verdict
    assert x['rules'][FIRED] == sorted(again.rules) == sorted(live.rules)
    codes = [lim['code'] for lim in x['unreproducible']]
    assert LA.REJUDGE_SERVER_CONFIRMATION in codes
    for lim in x['unreproducible']:
        assert len(lim['statement']) > 80, '%s needs the reason a person acts on' % lim['code']
    assert LA.REJUDGE_SERVER_CONFIRMATION in explain_text(again)


def test_a_stored_json_row_is_explained_without_being_re_judged(tmp_path):
    """A census has the dict it wrote years ago and no Result object. It reads through the same
    accessors `core` reads a stored evidence row through."""
    live = _audit()
    row = json.loads(json.dumps(live.to_dict(), ensure_ascii=False))
    x = explain(row)
    assert x['url'] == live.url and x['verdict'] == live.verdict
    assert x['rules'][FIRED] == sorted(live.rules)
    assert 'Spanish' in x['by_language']


def test_the_printed_form_holds_the_long_evidence_lists_back():
    """The detection gates are on every finding a site produced, so a site with thirty of them would
    print thirty lines under each of four rules. The count is still exact in the data."""
    many = [LA.Evidence('inline_text', 'https://x.org/p%d' % i, 'aviso %d' % i, 'Spanish',
                        rules=[6, 8, 10, 9]) for i in range(EVIDENCE_SHOWN + 3)]
    r = LA.Result(url='https://x.org/', verdict='true_multilingual', languages=['Spanish'],
                  evidence=many, rules=LA.verdict_rules(many, ''))
    rows = {row['number']: row for stage in explain(r)['stages'] for row in stage['rules']}
    assert len(rows[6]['evidence']) == EVIDENCE_SHOWN + 3
    assert 'and 3 more' in explain_text(r)


def test_the_explanation_is_json_serialisable():
    """The machine-readable half has to survive the file it is written to."""
    back = json.loads(json.dumps(explain(_audit()), ensure_ascii=False))
    assert back['stages'][0]['rules'][0]['number'] == STAGES[0][1][0]


# ------------------------------------------------------------ the command line
def test_the_command_line_explains_a_live_address(monkeypatch, capsys):
    from langaccess import cli as CLI

    async def fake(u, deep=False, timeout=None):
        return LA.Result(url=u, verdict='true_multilingual', languages=['Spanish'],
                         authorship='authored', sufficiency=3, rules=[6, 12, 8, 10, 9],
                         by_language={'Spanish': {'authorship': 'authored', 'sufficiency': 3}},
                         evidence=[LA.Evidence('inline_text', 'https://x.org/es', 'aviso',
                                               'Spanish', rules=[6, 8, 10, 9])])

    monkeypatch.setattr(CLI, 'audit_async', fake)
    assert CLI.main(['--explain', 'https://x.org/']) == 0
    out = capsys.readouterr().out
    assert 'rules, in the order this package applies them' in out
    assert LA.RULES[6].title in out
    assert 'aviso' in out


def test_the_command_line_explains_a_stored_capture(monkeypatch, capsys, tmp_path):
    """`--rejudge` is how a capture is read, and `--explain` says why each record came out as it
    did, with no network access on either side."""
    from langaccess import cli as CLI

    path = tmp_path / 'run.jsonl'
    LA._store_result(str(path), _audit(keep_pages=True))
    assert CLI.main(['--rejudge', str(path), '--explain']) == 0
    out = capsys.readouterr().out
    assert 'https://x.org/' in out
    assert LA.REJUDGE_SERVER_CONFIRMATION in out, (
        'a re-judged explanation has to say what a capture could not carry')


def test_the_json_explanation_is_one_object_per_site_and_the_output_file_keeps_the_row(
        monkeypatch, capsys, tmp_path):
    """`--output` is what a census reads, so it holds the result row whatever the screen shows."""
    from langaccess import cli as CLI

    out_path = tmp_path / 'out.jsonl'

    async def fake(u, deep=False, timeout=None):
        return LA.Result(url=u, verdict='english_only', rules=[12])

    monkeypatch.setattr(CLI, 'audit_async', fake)
    assert CLI.main(['--json', '--explain', '--output', str(out_path), 'a.org', 'b.org']) == 0
    printed = [json.loads(l) for l in capsys.readouterr().out.splitlines() if l.strip()]
    assert [x['url'] for x in printed] == ['a.org', 'b.org']
    assert all('stages' in x for x in printed)
    written = [json.loads(l) for l in out_path.read_text(encoding='utf-8').splitlines() if l.strip()]
    assert [r['url'] for r in written] == ['a.org', 'b.org']
    assert all('stages' not in r and 'verdict' in r for r in written)


def test_without_the_flag_the_output_is_the_one_it_has_always_been(monkeypatch, capsys):
    from langaccess import cli as CLI

    async def fake(u, deep=False, timeout=None):
        return LA.Result(url=u, verdict='english_only', rules=[12])

    monkeypatch.setattr(CLI, 'audit_async', fake)
    assert CLI.main(['x.org']) == 0
    out = capsys.readouterr().out
    assert 'verdict   english_only' in out
    assert 'rules, in the order this package applies them' not in out
