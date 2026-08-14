# -*- coding: utf-8 -*-
"""The rules as records, and the gate that keeps them honest.

The rules bind both the model coders and this instrument, so a disagreement between them
is supposed to be a detection error and never a difference of definition. That only holds while
every rule is actually applied somewhere. Rule 8, "a name is not content", sat in the written
rules with no implementation for weeks and nothing in this package could tell that from one that was
implemented but never mentioned in a comment.

axe-core's answer is that a rule is a record and the catalogue is generated from the records, with
a schema gate that refuses a record naming an evaluator which is not a file on disk. This file runs
the same two checks at the scale this package needs: every rule names somewhere it is enforced and
every one of those names resolves, or the rule says in words why there is nothing to name; and the
registry covers exactly the published numbers, which are 1 to 17 with no gaps.
"""
import pytest

from langaccess import core as LA


def test_the_registry_covers_exactly_the_rule_numbers():
    """No gaps and no inventions: the release numbering runs 1 to 17 in pipeline order,
    assigned 2026-08-09 before the first release. A rule 18 nobody wrote, or a rule 7 somebody
    deleted, would otherwise pass every other check here."""
    assert tuple(sorted(LA.RULES)) == tuple(range(1, 18))
    for n, rule in LA.RULES.items():
        assert rule.number == n, f'rule {n} is keyed under the wrong number'


def test_every_rule_is_enforced_at_a_named_site_or_says_why_it_is_not():
    """The guard that would have caught rule 8.

    A rule with an empty `enforced_in` and an empty `not_in_code` is a rule this package claims
    nothing about, which is the state that let a documented rule go unimplemented unnoticed. One or
    the other, never neither and never both.
    """
    for n, rule in sorted(LA.RULES.items()):
        has_site = bool(rule.enforced_in)
        has_reason = bool(rule.not_in_code.strip())
        assert has_site or has_reason, (
            f'rule {n} ({rule.title}) names nowhere it is enforced and gives no reason. '
            'Either name the objects that apply it, or say on the record why nothing can.')
        assert not (has_site and has_reason), (
            f'rule {n} ({rule.title}) claims both an enforcement site and a reason it cannot be '
            'in code. One of the two is wrong.')


def test_every_named_enforcement_site_exists_in_the_module():
    """axe-core's schema gate requires the named evaluate function to be a file on disk. This is
    that: a name in `enforced_in` that no longer resolves means the rule moved, was renamed, or was
    deleted, and the registry has to move with it rather than keep pointing at nothing."""
    for n, rule in sorted(LA.RULES.items()):
        for name in rule.enforced_in:
            assert hasattr(LA, name), (
                f'rule {n} ({rule.title}) says it is enforced in {name!r}, which does not exist '
                'in langaccess.core')


def test_every_published_rule_is_applied_by_this_package():
    """One development rule held the `not_in_code` field open on its own: a scoring rule for a
    validation table that no reading could apply. It left the published set on 2026-08-08 with
    that table, and every rule that remains names the code that applies it. A rule that earns
    the field again is a decision somebody makes rather than a side effect, so it fails here
    first."""
    not_in_code = sorted(n for n, r in LA.RULES.items() if r.not_in_code.strip())
    assert not_in_code == [], f'a rule with no implementation appeared: {not_in_code}'
    assert all(r.enforced_in for r in LA.RULES.values())


def test_the_pipeline_order_is_the_number_order():
    """The release numbering has one promise: a reader walking the numbers walks the pipeline.
    The stages in `explain.STAGES` are the order the package applies its rules, so the numbers
    they hold have to be contiguous and ascending across stages. Records written before
    2026-08-09 carry the development numbering; the map is in the freeze note in test_engineering.py,
    and it is one-for-one except the development rule that split into 15 and 16."""
    from langaccess.explain import STAGES
    flat = [n for _, ns in STAGES for n in ns]
    assert flat == sorted(flat), "a stage holds a number out of pipeline order"
    assert flat == list(range(1, 18))


def test_every_rule_carries_its_heading_verbatim():
    """The heading is the join back to the coding document. A retitled or renumbered rule
    shows up as a diff here rather than as two documents quietly disagreeing."""
    for n, rule in sorted(LA.RULES.items()):
        assert rule.heading.startswith(f'{n}. '), rule.heading
        assert rule.title and rule.title == rule.title.strip()


def test_the_registry_is_read_only():
    """A rule record is a fact about the rules, not a place to keep state."""
    with pytest.raises(Exception):
        LA.RULES[3].title = 'something else'


# ---------------------------------------------------------------- rules on the decisions
def test_a_piece_of_evidence_records_the_rules_that_decided_it():
    """The gates each finding passed, by number. Rule 6 and rule 9 are the function-word gates,
    rule 8 the name exclusion, rule 10 the page-against-fragment cut, rule 7 the same paragraph
    standard restated for a script, and rule 4 the two-click bound, which says nothing about the
    home page."""
    assert LA._evidence_rules('Spanish', 'inline_text', home=True) == [6, 8, 9, 10]
    assert LA._evidence_rules('Spanish', 'translated_page', home=False) == [4, 6, 8, 9, 10]
    # a script language is held to rule 7 as well
    assert 7 in LA._evidence_rules('Korean', 'inline_text', home=True)
    assert 7 in LA._evidence_rules('Ukrainian', 'inline_text', home=True)
    assert 7 not in LA._evidence_rules('French', 'inline_text', home=True)
    # a clicked control is not a coverage question, so rule 10 is not one of its rules
    assert 10 not in LA._evidence_rules('Spanish', 'language_control', home=True)


def test_the_field_defaults_to_empty_so_nothing_existing_breaks():
    """A row written before this field existed, and a piece of evidence a caller built by hand,
    both read exactly as they did."""
    e = LA.Evidence('inline_text', 'https://x.org/', 'aviso', 'Spanish')
    assert e.rules == []
    assert LA.Result(url='https://x.org/').rules == []
    assert LA.verdict_rules([e], '') == [10, 12]      # nothing on the evidence to gather
    old_row = {'mechanism': 'inline_text', 'url': 'https://x.org/', 'quote': 'aviso',
               'language': 'Spanish'}
    assert LA.verdict_rules([old_row], '') == [10, 12]


def test_the_rules_are_in_the_row_a_census_stores():
    import json
    r = LA.Result(url='https://x.org/', verdict='true_multilingual', rules=[6, 8, 9, 10, 12],
                  evidence=[LA.Evidence('inline_text', 'https://x.org/', 'aviso', 'Spanish',
                                        rules=[6, 8, 10, 9])])
    back = json.loads(json.dumps(r.to_dict(), ensure_ascii=False))
    assert back['rules'] == [6, 8, 9, 10, 12]
    assert back['evidence'][0]['rules'] == [6, 8, 10, 9]
    assert back['unreproducible'] == []


def test_a_verdict_names_the_rules_that_actually_fired():
    """Only the ones that fired. A site with no archive page does not say 18, and a site with no
    widget does not say 4, or the field would be the same numbers on every row."""
    es = LA.Evidence('inline_text', 'https://x.org/services/', 'aviso', 'Spanish',
                     rules=[6, 8, 10, 9], server_html=True)
    assert LA.verdict_rules([es], '') == [6, 8, 9, 10, 12]

    # rule 14: a widget is present, so the floor is machine translation
    assert 14 in LA.verdict_rules([es], 'Google Translate')

    # rule 15: an advertised route came back in English and the widget produced nothing anywhere
    assert 15 in LA.verdict_rules([], 'Weglot', route_was_english=True)
    assert 15 not in LA.verdict_rules([], 'Weglot')
    # rule 16: a worked control changed nothing, the other half of the development rule
    assert 16 in LA.verdict_rules([], 'Weglot', control_dead=True)
    assert 16 not in LA.verdict_rules([], 'Weglot')

    # rule 11: a plugin marker, which counts only alongside content
    marker = LA.Evidence('translation_plugin', 'https://x.org/', 'wpml', '', rules=[11])
    assert 11 in LA.verdict_rules([marker], '')

    # rule 17: five front doors with no vendor marker is a platform
    assert 17 in LA.verdict_rules([es], '', advertised_roots=5)
    assert 17 not in LA.verdict_rules([es], '', advertised_roots=4)

    # rule 13: an archive page's language was set aside
    old = LA.Evidence('inline_text', 'https://x.org/category/past_events/', 'Weihnachtsfeier',
                      'German', rules=[6, 8, 10, 9])
    assert 13 in LA.verdict_rules([old], '')
    assert LA.verdict_for([old], '') == 'english_only'

    # rule 12 is on every site, because a verdict that cannot name its language carries nothing
    assert 12 in LA.verdict_rules([], '')


def test_the_rules_a_site_was_excluded_under_are_on_the_result():
    """The site-level exclusions answer before any evidence exists, so their rule numbers have to
    be written where the verdict is, not gathered from evidence that was never collected."""
    import asyncio

    from test_engineering import _MapBrowser, _page      # the fake browser, no network

    # a third-party directory profile, answered before a browser is even started. This was rule 5
    # until 2026-08-08. The behaviour stayed and the number went, so the note carries the reason
    # alone and the assertion is that the stop still happens and claims no rule.
    r = asyncio.run(LA._audit_async('https://app.candid.org/profiles/0000000'))
    assert r.verdict == 'unreachable' and r.rules == []
    assert 'directory profile' in r.note

    # rule 1, on the address the site landed at
    b = _MapBrowser({'https://www.facebook.com/someorg': _page('A page about the organization.')})
    r = asyncio.run(LA._audit_async('https://www.facebook.com/someorg', browser=b))
    assert r.rules == [1]

    # rule 2, read off the home text
    b = _MapBrowser({'https://x.org/': _page('This domain is for sale. Inquire about this domain '
                                            'today through our registrar partner.')})
    r = asyncio.run(LA._audit_async('https://x.org/', browser=b))
    assert r.rules == [2]


def test_the_short_titles_are_available_for_a_reader():
    assert LA.rule_titles([10, 6, 6]) == [(6, LA.RULES[6].title), (10, LA.RULES[10].title)]
    assert LA.rule_titles([99]) == [(99, 'unknown, not in this registry')]

# ------------------------------------------------ rules 15 and 16, one number in development
def test_a_dead_control_is_its_own_class_and_not_an_absence_claim():
    """Rules 15 and 16 answer two different observations that shared one development number.

    A locale route the SITE advertises, fetched and coming back in English, is the server's answer
    and nothing about the reader's browser enters it, so english_only is sound and rule 15 keeps
    it. A control that was found, clicked, and changed nothing is what THIS CLIENT could obtain,
    and one government site it fired on translates for a person on a phone. Answering that
    english_only made the package assert an absence it had not established, so rule 16 answers it
    machine_translate_error instead. Split 2026-08-09."""
    assert LA.class_for(LA.AUTHOR_NONE, 0, widget=True) == 'machine_translate'
    assert LA.class_for(LA.AUTHOR_NONE, 0, widget=True, route_was_english=True) == 'english_only'
    assert LA.class_for(LA.AUTHOR_NONE, 0, widget=True, control_dead=True) == LA.MT_ERROR
    assert LA.MT_ERROR == 'machine_translate_error'


def test_the_server_answer_wins_over_the_client_one():
    """A site carrying both observations is english_only. An advertised route returning English is
    client-independent and is the stronger of the two, so it is not softened by a dead control."""
    assert LA.class_for(LA.AUTHOR_NONE, 0, widget=True,
                        route_was_english=True, control_dead=True) == 'english_only'


def test_a_dead_control_without_a_widget_claims_nothing():
    """Rule 16 says a WIDGET could not be worked. With no vendor named there is no widget to have
    failed, and the reading falls through to what it always was."""
    assert LA.class_for(LA.AUTHOR_NONE, 0, widget=False, control_dead=True) == 'english_only'


def test_a_widget_that_worked_somewhere_is_not_in_error():
    """The `produced` guard, which predates the split and has to survive it: a widget that returned
    another language anywhere on the site has not been shown to fail, whatever one control did."""
    es = LA.Evidence('language_control', 'https://x.org/es', 'aviso en espanol', 'Spanish',
                     rules=[6])
    assert LA.verdict_for([es], 'Google Translate', control_dead=True) == 'machine_translate'
    assert LA.verdict_for([], 'Google Translate', control_dead=True) == LA.MT_ERROR


def test_each_half_of_the_development_rule_owns_its_number():
    """The record says which observation was made, which one number never could."""
    assert 15 in LA.verdict_rules([], 'Google Translate', route_was_english=True)
    assert 16 not in LA.verdict_rules([], 'Google Translate', route_was_english=True)
    assert 16 in LA.verdict_rules([], 'Google Translate', control_dead=True)
    assert 15 not in LA.verdict_rules([], 'Google Translate', control_dead=True)
