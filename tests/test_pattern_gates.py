# -*- coding: utf-8 -*-
"""Two standing gates over the wall, placeholder and widget patterns.

Both were designed during the release round of 2026-08-02/03 and neither was built then. They are
here because the
patterns in this family have a history: every defect in it so far has been a pattern that reached
one character further than it meant to, and every one of them was found by hand, late, and after a
run of readings had already been taken under it.

THE BOUNDARY GATE, `test_no_alternative_matches_inside_a_longer_word`. For every alternative of the
eight patterns, the shipped form and the same form with a left word boundary in front of it must
match the same strings over `fixtures/pattern_boundary.json`, or the pair must be named in
`INTENDED_DIFFERENCE` with the reason. Two defects are the class this is for. `parked (?:free
)?(?:courtesy of|by)` shipped with no boundary, matched inside `sparked by`, and its only two
matches over 44,284 corpus pages were live organization sites the instrument was calling
unreachable. The bare word `captcha` matched inside `reCAPTCHA` in the footer sentence every
GoDaddy, Wix and Squarespace contact page prints, and left 64 live organization pages unreachable.
Both were fixed in the release; nothing stopped the third.

WHAT IT DOES NOT COVER, and the corpus says so in its own fixture. A left boundary says nothing
about the right-hand side: `security check` matches inside `security checklist` under both forms and
this gate is silent about it. Whether the vocabulary needs a right boundary as well is a
measurement over the census render store, not a transcription.

THE UNREACHABLE WARD, `test_the_ward_has_not_moved`. `unreachable` is the class that says a site was
never read, and a pattern that widens moves live organization pages into it silently: the same
release round converted 962 rows over 739 sites in that direction and 101 the other way, and both
numbers had to be measured by hand before anyone could say whether the change was worth making. The
gate freezes what the patterns catch over a synthetic corpus of pages, and when it fires it reports
the two directions with the pages named, so a pattern change arrives in front of whoever made it as
"this many pages became unreachable" instead of as a green suite. It is the reading-freeze gate's
shape, applied to the one decision that gate cannot reach, because `is_wall` and `is_parked` run on
a home read before any reading is taken.

WHY THE PAGES ARE INVENTED. The census render store is not distributed and nothing captured from an
organization can be committed here. Every string in both corpora was written for this file.
"""
import hashlib
import io
import json
import os
import re

import pytest

from langaccess import core as LA

_FIXTURE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fixtures')
_BOUNDARY_PATH = os.path.join(_FIXTURE_DIR, 'pattern_boundary.json')
_WARD_CORPUS_PATH = os.path.join(_FIXTURE_DIR, 'ward_corpus.json')
_WARD_EXPECTED_PATH = os.path.join(_FIXTURE_DIR, 'ward_expected.json')

# The eight patterns the boundary gate covers, by name. The names are transcribed and nothing else
# is: the alternatives are split off the live compiled pattern, so an alternative added tomorrow is
# covered without anybody adding it here, and a fixture for it has to be written before the suite
# goes green again.
GUARDED = ['PARKED_RX', 'PARKED_EXPIRED_RX', 'PARKED_SOON_RX', 'WALL_UNGATED_RX', 'WALL_GATED_RX',
           'WALL_NOTFOUND_RX', 'MT_RX', 'ROUTE_WIDGET']

# A left word boundary, written as a lookbehind rather than as `\b` because `\b` means different
# things in front of different first characters and this has to mean one thing: the character before
# the match is not part of a word.
LEFT_BOUNDARY = r'(?<![0-9A-Za-z_])'

# Where the shipped form deliberately reaches inside a longer word, keyed by (constant, alternative)
# and carrying the reason. The gate asks for an entry here instead of a boundary, and an entry is a
# decision somebody wrote down.
#
# `covered` is the half of the entry a person cannot get wrong by writing prose. It says whether the
# PATTERN AS A WHOLE would still match the same strings with the boundary in front of this one
# alternative, and the gate checks the claim rather than believing it. `covered` False means the
# boundary would cost the pattern a real match and the reach is load-bearing; `covered` True means
# another alternative catches the same string and the reach is redundant. An entry claiming the
# wrong one fails, which is what keeps this from becoming a list of excuses.
INTENDED_DIFFERENCE = {
    ('MT_RX', 'gtranslate'): {
        'covered': False,
        'why': "GTranslate's own function name is `doGTranslate`, and on some installs it is the "
               "only marker in the page. core.py records that `doGTranslate` was REMOVED from this "
               "pattern precisely because `gtranslate` already matched inside it, measured at 0 "
               "organizations added over the 45,100 of the census capture. A left boundary here "
               "would lose the marker that removal relied on."},
    ('ROUTE_WIDGET', 'gtranslate'): {
        'covered': False,
        'why': "The same alternative and the same reason as in MT_RX. This one decides whether a "
               "locale route coming back in English says the widget translates nothing, so losing "
               "the marker would move a site from machine_translate toward english_only."},
    ('WALL_UNGATED_RX', 'site not found'): {
        'covered': True,
        'why': "Found by this gate on the day it was written, and it is redundancy rather than "
               "reach: `site not found` matches inside `website not found`, which is the very next "
               "alternative of the same pattern, so the pattern as a whole answers the same either "
               "way and `website not found` catches nothing `site not found` does not. Both "
               "wordings are a host saying there is nothing at this address, so no live page is at "
               "risk from the reach, and no reading moves whichever way this is settled. Left as "
               "shipped because a change to a wall pattern is a change to which sites are reported "
               "as never read, and this one buys nothing to pay for that."},
    ('MT_RX', 'prisna-google-website-translator'): {
        'covered': False,
        'why': "The vendor writes its own id as `widget_prisna-google-website-translator-2`, with "
               "WordPress's `widget_` prefix in front of it and an underscore between, so a left "
               "word boundary would look at the underscore and refuse the only marker four of the "
               "installs carry. Those four are the whole reason this alternative exists: they load "
               "the Google runtime on demand, so a capture taken before the click carries the "
               "wrapper and none of the Google patterns. The reach is one prefix long and the "
               "string it reaches through is the vendor's own."},
}


def _split_alternatives(pattern):
    """The top-level alternatives of a pattern: split on `|` outside every group and class.

    Read off the compiled pattern rather than listed here, so nothing in this file is a copy of
    something in `core.py` that can drift away from it.
    """
    out, depth, in_class, buf, i = [], 0, False, [], 0
    while i < len(pattern):
        c = pattern[i]
        if c == '\\':
            buf.append(pattern[i:i + 2])
            i += 2
            continue
        if in_class:
            in_class = c != ']'
            buf.append(c)
            i += 1
            continue
        if c == '[':
            in_class = True
        elif c == '(':
            depth += 1
        elif c == ')':
            depth -= 1
        elif c == '|' and depth == 0:
            out.append(''.join(buf))
            buf = []
            i += 1
            continue
        buf.append(c)
        i += 1
    out.append(''.join(buf))
    return out


def _starts_on_a_word_character(alt):
    """Can this alternative begin its match on a letter, a digit or an underscore?

    Only those can be preceded by a word character, so only those are what a left boundary is about.
    An alternative beginning `//`, as the two proxy-address markers do, is skipped: putting a
    boundary in front of a slash asks a question about the character before a slash, which is not
    the question this gate exists for.
    """
    while alt:
        if alt.startswith('(?<'):
            alt = alt[alt.index(')') + 1:]
            continue
        if alt.startswith(r'\b'):
            alt = alt[2:]
            continue
        if alt.startswith('(?:'):
            alt = _split_alternatives(alt[3:alt.rindex(')')])[0] if ')' in alt else ''
            continue
        break
    return bool(alt) and (alt[0].isalnum() or alt[0] == '_')


def _alternatives():
    """(constant name, alternative) for every alternative of the eight patterns."""
    out = []
    for name in GUARDED:
        for alt in _split_alternatives(getattr(LA, name).pattern):
            out.append((name, alt))
    return out


with io.open(_BOUNDARY_PATH, encoding='utf-8') as _fh:
    BOUNDARY = json.load(_fh)
BOUNDARY_STRINGS = list(BOUNDARY['wordings']) + [t['text'] for t in BOUNDARY['traps']]


@pytest.mark.parametrize('name,alt', _alternatives(),
                         ids=['%s:%s' % (n, a[:40]) for n, a in _alternatives()])
def test_no_alternative_matches_inside_a_longer_word(name, alt):
    """The shipped form and the left-bounded form answer the same over the committed strings.

    One test per alternative, so a failure names the alternative and the string rather than a count.
    """
    if not _starts_on_a_word_character(alt):
        pytest.skip('begins on a character no word boundary is about')
    flags = getattr(LA, name).flags
    shipped = re.compile(alt, flags)
    bounded = re.compile(LEFT_BOUNDARY + alt, flags)
    moved = [s for s in BOUNDARY_STRINGS if bool(shipped.search(s)) != bool(bounded.search(s))]
    excuse = INTENDED_DIFFERENCE.get((name, alt))
    if excuse:
        assert moved, (
            'INTENDED_DIFFERENCE claims %s / %r reaches inside a longer word and no string in the '
            'corpus shows it doing so. Either the pattern changed and the entry is stale, or the '
            'string that showed it was removed.' % (name, alt))
        # and the half of the entry that is checked rather than read: what the WHOLE pattern would
        # answer with the boundary in front of this one alternative
        alts = _split_alternatives(getattr(LA, name).pattern)
        patched = re.compile('|'.join(LEFT_BOUNDARY + a if a == alt else a for a in alts), flags)
        whole = getattr(LA, name)
        lost = [s for s in BOUNDARY_STRINGS if bool(whole.search(s)) != bool(patched.search(s))]
        if excuse['covered']:
            assert lost == [], (
                'the ledger says %s / %r reaches inside a longer word that another alternative '
                'catches anyway, and the pattern as a whole answers differently on:\n%s\nSo the '
                'reach is load-bearing after all and the entry is wrong.'
                % (name, alt, '\n'.join('  %r' % s for s in lost)))
        else:
            assert lost, (
                'the ledger says a left boundary on %s / %r would cost the pattern a match, and '
                'over this corpus it costs nothing. Either the boundary is free and belongs in the '
                'pattern, or the string that showed the cost has left the corpus.' % (name, alt))
        return
    assert moved == [], (
        '%s alternative %r matches inside a longer word.\n'
        'It matches these strings and the same alternative with a left word boundary does not:\n%s\n'
        'This is the shape of the `sparked by` and `reCAPTCHA` defects: one wording, a false '
        'positive rate near 100 percent, and one character to fix it. Either put the boundary in, '
        'or add the pair to INTENDED_DIFFERENCE with the reason.'
        % (name, alt, '\n'.join('  %r' % s for s in moved)))


def test_every_alternative_is_exercised_by_the_corpus():
    """A gate over a corpus that never reaches an alternative has said nothing about it.

    Reaching every alternative is what keeps the test above standing rather than historical: an alternative added to any
    of the eight patterns fails here until somebody writes a string that reaches it, and that string
    then joins the corpus every other alternative is checked against.
    """
    unreached = []
    for name, alt in _alternatives():
        rx = re.compile(alt, getattr(LA, name).flags)
        if not any(rx.search(s) for s in BOUNDARY_STRINGS):
            unreached.append('%s: %r' % (name, alt))
    assert unreached == [], (
        'no string in tests/fixtures/pattern_boundary.json reaches these alternatives, so the '
        'boundary gate says nothing about them:\n%s' % '\n'.join('  ' + u for u in unreached))


def test_the_boundary_corpus_carries_the_two_defects_it_was_built_from():
    """The corpus can be edited, and these two strings are why it exists."""
    joined = '\n'.join(BOUNDARY_STRINGS).lower()
    assert 'sparked by' in joined, 'the `sparked by` case is gone from the corpus'
    assert 'recaptcha' in joined, 'the `reCAPTCHA` footer case is gone from the corpus'
    thin = [t['text'][:40] for t in BOUNDARY['traps'] if len(t.get('why', '').strip()) < 40]
    assert thin == [], 'these corpus entries do not say what they are for: %s' % thin


# ---------------------------------------------------------------- the unreachable ward
#
# `is_wall` and `is_parked` decide, on the home read and before any language is looked for, that a
# site was not read at all. That decision is upstream of every reading, so `tests/test_reading_
# freeze.py` cannot see it: a page these two catch never becomes a reading to freeze.
#
# The corpus is written to reach both directions and every gate. Most of it exercises the length
# gates: `PAGE_IS_SUBSTANTIAL` releases a gated wording on a page of 1,500 characters or more,
# `WALL_NOTFOUND_MAX` and `PARKED_SOON_MAX` hold the two riskiest wordings to 300 and 200, and
# `WALL_WINDOW` and `PARKED_WINDOW` decide how far into a page either family is read at all.

with io.open(_WARD_CORPUS_PATH, encoding='utf-8') as _fh:
    WARD_CORPUS = json.load(_fh)
WARD_BY_NAME = {p['name']: p for p in WARD_CORPUS}


def _catch():
    """What the shipped patterns say about every page in the corpus."""
    return {p['name']: {'wall': bool(LA.is_wall(p['text'])),
                        'parked': bool(LA.is_parked(p['text'])),
                        'chars': len(p['text'])}
            for p in WARD_CORPUS}


def _dump(catch):
    return json.dumps(catch, ensure_ascii=False, indent=1, sort_keys=True) + '\n'


def _ward_expected():
    with io.open(_WARD_EXPECTED_PATH, encoding='utf-8') as fh:
        return json.load(fh)


def _unreachable(row):
    """One page, one question: does the audit stop here and report a site it never read?"""
    return bool(row['wall'] or row['parked'])


# Recorded 2026-08-03, against core.py sha256
# d4c011b32788912803ea849a2f30a822fed481c4177e264b679fd8292c8602a4, the tree of 2026-08-03, plus
# the later changes to `_same_site` and to how a missing browser is raised. Neither of those touches
# a wall or placeholder pattern, and this digest is what says so rather than the reasoning.
#
# **A change to this value is a change to which sites the instrument reports as never read.** Moving
# it is allowed and is a decision: re-record it in the same commit that says, in LIMITATIONS.md, how
# many pages moved toward unreachable and how many the other way over a store of real sites, as two
# numbers and never as a net. The gate reports those two counts over this corpus in its own failure
# message, which is where the sentence starts; the corpus is thirty synthetic pages and is not the
# measurement.
WARD = '6fb3d7ae05d7922c850aaab1f2a85bbc89b8b44f3b4224565c08ac24648b4a43'


def test_the_ward_has_not_moved():
    """The gate. The two direction counts are in the message, because they are what the decision
    turns on and nobody should have to go and compute them to read the failure."""
    got = _catch()
    if os.environ.get('LANGACCESS_RECORD_WARD'):
        with io.open(_WARD_EXPECTED_PATH, 'w', encoding='utf-8', newline='\n') as fh:
            fh.write(_dump(got))
    want = _ward_expected()
    toward = sorted(n for n, row in got.items()
                    if n in want and _unreachable(row) and not _unreachable(want[n]))
    away = sorted(n for n, row in got.items()
                  if n in want and not _unreachable(row) and _unreachable(want[n]))
    assert got == want, (
        'the wall and placeholder patterns catch a different set of pages than they did.\n'
        '  toward unreachable: %d %s\n'
        '  toward readable:    %d %s\n'
        'A page that moves toward unreachable is a site the instrument stops reading and reports as '
        'never read, which is the direction that costs an organization its language access on the '
        'record. Before accepting this, count both directions over a store of real sites, judged '
        'once under the current patterns and once under the changed ones, write the two counts into '
        'the freeze note as two numbers and never as a net, and re-record with '
        'LANGACCESS_RECORD_WARD=1.'
        % (len(toward), toward, len(away), away))
    assert hashlib.sha256(_dump(got).encode('utf-8')).hexdigest() == WARD, (
        'the recorded catch and the expected file agree and the digest does not, which means the '
        'expected file was edited without the digest being re-recorded.')


@pytest.mark.parametrize('name', sorted(WARD_BY_NAME))
def test_every_ward_page_is_caught_as_it_was(name):
    """One test per page, so a failure names the page and what it is for."""
    got, want = _catch()[name], _ward_expected()[name]
    assert got == want, (
        '%s is caught differently than it was.\n  what this page is for: %s\n  was: %r\n  now: %r'
        % (name, WARD_BY_NAME[name]['why'], want, got))


def test_the_ward_corpus_reaches_both_directions_and_every_gate():
    """What the corpus is currently known to reach, so that it cannot quietly shrink.

    A corpus of walls alone would go green on a pattern that called every page in the world a wall.
    Both answers have to be in it, on pages of both lengths, for each of the three gated families.
    """
    got = _catch()
    caught = [n for n, row in got.items() if _unreachable(row)]
    read = [n for n, row in got.items() if not _unreachable(row)]
    assert len(caught) >= 10 and len(read) >= 10, (
        'the corpus has stopped reaching both answers: %d caught, %d read' % (len(caught),
                                                                              len(read)))
    long_pages = [n for n, row in got.items() if row['chars'] >= LA.PAGE_IS_SUBSTANTIAL]
    assert len(long_pages) >= 5, (
        'the length gates are most of what these patterns are, and the corpus no longer carries '
        'enough substantial pages to hold them: %s' % sorted(long_pages))
    assert any(not _unreachable(got[n]) for n in long_pages), (
        'no substantial page in the corpus is read, so nothing holds the release of a gated wording')
    assert any(_unreachable(got[n]) for n in long_pages), (
        'no substantial page in the corpus is caught, so nothing holds an ungated wording ungated')


def test_every_ward_page_says_what_it_is_for():
    thin = sorted(p['name'] for p in WARD_CORPUS if len(p.get('why', '').strip()) < 40)
    assert thin == [], 'these pages do not say what they pin: %s' % thin
