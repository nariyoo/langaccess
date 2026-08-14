# -*- coding: utf-8 -*-
"""The codebook table in README, held to the registry it was generated from.

Every result names the rules that decided it by number, so a reader with a table of results needs
somewhere those numbers resolve. README carries them. A table typed once and left alone is a
document that becomes wrong quietly: a rule renamed in `RULES` and not in the README would mislead
anybody reading a published table, and nothing would fail.

So the block between the two markers is compared against `RULES` row for row, in order, on every
run. Regenerate it with `scratchpad/write_codebook_table.py` rather than editing it by hand.
"""
import io
import re
from pathlib import Path

import pytest

from langaccess.core import RULES

README = Path(__file__).resolve().parent.parent / 'README.md'
BEGIN = '<!-- codebook: generated from RULES, do not edit by hand -->'
END = '<!-- end codebook -->'


def _table_rows():
    """(number, stage, title, criterion) per row. One table, four columns: five tables sized their
    columns separately and the same column came out a different width in each."""
    t = io.open(README, encoding='utf-8').read()
    assert BEGIN in t and END in t, 'the codebook markers are gone from README'
    body = t.split(BEGIN, 1)[1].split(END, 1)[0]
    rows = []
    for line in body.strip().split('\n'):
        m = re.match(r'^\|\s*(\d+)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|$', line.strip())
        if m:
            rows.append((int(m.group(1)), m.group(2), m.group(3), m.group(4)))
    return rows


def test_the_table_holds_every_rule_and_no_others():
    ns = [r[0] for r in _table_rows()]
    assert sorted(ns) == sorted(RULES)
    assert len(ns) == len(set(ns)), 'a rule is in the table twice'


def test_every_title_is_the_registry_title():
    for n, _stage, title, crit in _table_rows():
        assert title == RULES[n].title, 'rule %d reads %r in README and %r in RULES' % (
            n, title, RULES[n].title)


def test_the_rows_run_in_number_order_down_the_page():
    """The numbers were assigned by the pipeline, so the table is readable in one pass only while
    the rows keep that order."""
    ns = [r[0] for r in _table_rows()]
    assert ns == sorted(ns), 'the table is out of order: %s' % ns


def test_every_row_names_its_stage():
    """The stage column replaced five separate tables. A blank cell there leaves a rule with no
    place in the pipeline the numbering claims to follow."""
    for n, stage, _title, _crit in _table_rows():
        assert stage.strip(), 'rule %d has no stage' % n


def test_the_stage_column_is_the_stage_the_package_prints():
    """The table's stage column and `explain.STAGES` are one thing said twice, and for a day they
    disagreed: the printed headings lost their articles and the generator, which had the same list
    written out in its own words, kept `The class` and `The evidence and its rung`. The suite stayed
    green the whole time, because nothing compared them. This does.

    Case is the table's own, since its other columns are sentence case; the words and the grouping
    are not.
    """
    from langaccess.explain import STAGES
    want = {n: name for name, ns in STAGES for n in ns}
    assert want, 'STAGES is empty, so this test would pass on nothing'
    for n, stage, _title, _crit in _table_rows():
        assert n in want, 'rule %d is in the table and in no stage' % n
        assert stage.lower() == want[n].lower(), (
            'rule %d: the table says %r and the package prints %r' % (n, stage, want[n]))


def test_no_title_carries_markdown_that_would_break_the_row():
    for n, stage, title, crit in _table_rows():
        assert '|' not in title and '|' not in crit and '|' not in stage, (
            'rule %d has a pipe in a cell and breaks the table' % n)


@pytest.mark.parametrize('n', sorted(RULES))
def test_every_rule_is_applied_somewhere_or_says_why_not(n):
    """The claim the table makes about the registry: a number resolves to code, or to a reason."""
    r = RULES[n]
    assert r.enforced_in or r.not_in_code, 'rule %d names neither code nor a reason' % n


# ------------------------------------------------------- the titles, and the shape they must keep


@pytest.mark.parametrize('n', sorted(RULES))
def test_no_title_is_an_oppositional_pair(n):
    """"A paragraph, not a label" and its kind: the shape this project's writing rules forbid in a
    heading, and the shape all of these had grown into one at a time."""
    t = RULES[n].title.lower()
    for bad in (', not ', ' rather than ', ' is not ', ' are not ', ' does not '):
        assert bad not in t, 'rule %d is an oppositional pair: %r' % (n, RULES[n].title)


@pytest.mark.parametrize('n', sorted(RULES))
def test_no_title_is_a_sentence(n):
    """A heading names a topic. A finite verb makes it a clause instead."""
    words = re.findall(r"[a-z']+", RULES[n].title.lower())
    finite = {'is', 'are', 'was', 'were', 'has', 'have', 'does', 'do', 'counts', 'count',
              'carries', 'carry', 'makes', 'make', 'reads', 'serves', 'translates', 'appears',
              'can', 'cannot', 'will', 'must', 'should'}
    hit = finite.intersection(words)
    assert not hit, 'rule %d reads as a sentence, on %s: %r' % (n, sorted(hit), RULES[n].title)


def test_every_row_carries_the_criterion_from_the_registry():
    """The column exists so a rule number resolves without the coding document, which this
    distribution does not carry. A criterion that drifts from RULES is worse than none."""
    for n, _stage, _title, crit in _table_rows():
        assert crit == RULES[n].criterion, (
            'rule %d reads %r in README and %r in RULES' % (n, crit, RULES[n].criterion))


@pytest.mark.parametrize('n', sorted(RULES))
def test_every_rule_states_the_test_it_applies(n):
    assert RULES[n].criterion, 'rule %d has no criterion' % n
    assert len(RULES[n].criterion) > 25, 'rule %d says too little to resolve a number' % n
