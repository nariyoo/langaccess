# -*- coding: utf-8 -*-
"""The readings this package cannot settle, handed out as a work queue and read back in.

    langaccess review run.jsonl -o review.csv           # one row per site a person has to decide
    langaccess ingest review.csv run.jsonl              # the filled sheet, back into the run

    from langaccess import review_queue, needs_human, ingest_review
    q = review_queue('run.jsonl')
    q['rows']                       # the queue, as data
    needs_human(record)             # whether one reading needs a person

This instrument has a ceiling and every result already says where it is. A site behind a bot wall
was not read at all, and an absence claim made on two pages is not worth what the same claim is
worth on fifteen; `verdict` and `read_quality` record both, on every reading, and neither is a
number anybody should publish as a finding. What had been missing is the step after that admission.
A ceiling stated inside a verdict is a caveat nobody acts on; a ceiling handed out as a list of
addresses with a blank column beside each is work that gets done.

NOTHING HERE JUDGES A SITE. `review` arranges what the reading already recorded, on the pattern of
`explain` and `diff`: the predicate reads `verdict` and `read_quality` and computes no new opinion
of a page, and the sheet's every filled cell was written by the audit. `ingest` writes down what a
person decided and never derives anything from it.

A HAND VERDICT IS RECORDED AS A HAND VERDICT. It wins over the machine's, and it arrives with an
evidence entry of its own whose mechanism is `hand_coding`, carrying the verdict the machine
reached, the coder's name and the date where the sheet supplies them, and the coder's note as the
words that decided it. A later reader can therefore ask of any figure what share of it came from a
person, which is the question a table of mixed machine and hand readings has to be able to answer
and cannot once the two are the same field with no mark between them. `hand_coding(record)` is that
lookup. The mechanism name is deliberately not one of those the crawl produces, so
`counted_evidence` can never count it and no hand coding can move a machine judgement: the entry
sits beside the reading and is not folded into it.

THE EMPTY STAGE IS AN ERROR AND NOT A RESULT. A `review` over a run holding no records stops and
says so; a `review` that finds nothing to review says that, and exits non-zero when asked to; an
`ingest` that applies nothing says so rather than reporting a completed merge. This project's most
frequent bug, six distinct instances, is a stage that produced nothing and reported success, and a
queue is exactly the shape that invites it, since "no sites need a person" and "the predicate never
fired" print the same way unless one of them is made to fail.

WHAT A RUN FILE IS. One JSON object per line, as `--json --output` and `--store` both write, read
through `read_store`, so a capture and a plain result file are the same input here. A site written
twice in one file is the store appending; the LAST row is the one a hand coding lands on, which is
the row `_stored_record` and `diff_runs` both read.
"""
import collections
import csv
import gzip
import os
import json

from .core import (AUTHOR_UNKNOWN_WIDGET, MT_ERROR, READ_ENOUGH_PAGES, SWITCHER_ENGLISH, _snip,
                   _ev_lang, _ev_quote, _ev_url, _utc_now, read_store)
# One definition of each, rather than a second copy that can answer differently. `_key` is the form
# two stored addresses are compared on everywhere in this package, and `_field` is how a Result and
# the dict a stored run holds are read through one expression.
from .diff import _key
from .explain import _field


# The classes this package defines. A verdict outside them is not a class this tool disagrees
# with; it is a reading that never settled, and it goes in the queue for that reason.
VERDICTS = ('english_only', 'machine_translate', 'machine_translate_error',
            'true_multilingual', 'unreachable')
UNREACHABLE = 'unreachable'
ENGLISH_ONLY = 'english_only'

# The mechanism a hand coding is recorded under. Not one of OWN_MECHANISMS, on purpose: see the
# module docstring. `counted_evidence` tests membership of that tuple, so an entry carrying this
# name cannot enter a machine verdict however the record is later re-read.
HAND_CODING = 'hand_coding'

# Why a reading is in the queue. The sheet carries the sentence rather than the code, because the
# person reading the sheet has to act on it and a code is something to look up.
UNREAD = 'unread'
THIN_ABSENCE = 'thin_absence'
NO_CLASS = 'no_class'
UNNAMED_CONTROL = 'unnamed_control'
OFF_SITE_DECLARATION = 'off_site_declaration'
DEAD_CONTROL = 'dead_control'
KIND_TITLE = {
    UNREAD: 'the site was not read',
    THIN_ABSENCE: 'english_only on a search too thin to rest it on',
    NO_CLASS: 'no class this package defines',
    UNNAMED_CONTROL: 'a translation control this package cannot name',
    DEAD_CONTROL: 'a translation control that was worked and changed nothing',
    OFF_SITE_DECLARATION: 'the only non-English language is declared at another site',
}
# The order the summary prints them in, and the roll `review_text` iterates. It is a name and not a
# literal inside that function because a fifth kind was added on 2026-08-05 and the function held a
# hand-written tuple of four: the site went into the sheet, the sheet was right, and the line a
# person reads did not mention it. A queue that hides one of its own kinds is this project's most
# frequent bug wearing a different coat. `test_every_queue_kind_is_printed` holds the two together.
KIND_ORDER = (UNREAD, DEAD_CONTROL, THIN_ABSENCE, NO_CLASS, UNNAMED_CONTROL,
              OFF_SITE_DECLARATION)

# Why a SETTLED reading is nonetheless worth a second look. A different question from the six
# above, so a different vocabulary and a bucket the queue never mixes into `unsettled`: these
# readings rest on something found, the package stands behind them, and what is being said is that
# they carry the shape the model coders split over.
CONTESTED_FRAGMENT = 'fragment_beside_widget'
CONTESTED_ONE_LANGUAGE = 'one_language_notice'
CONTESTED_LOCALE_MIRRORS = 'locale_mirrors_over_a_reading'
CONTESTED_KINDS = (CONTESTED_FRAGMENT, CONTESTED_ONE_LANGUAGE, CONTESTED_LOCALE_MIRRORS)
CONTESTED_TITLE = {
    CONTESTED_FRAGMENT: 'authored text at notice level beside a named widget',
    CONTESTED_ONE_LANGUAGE: 'one language, at notice level, carrying the class alone',
    CONTESTED_LOCALE_MIRRORS: 'rule 17 set aside a reading the site had already carried',
}

# What the audit wrote, and then what the coder writes. The machine columns are everything a person
# needs in order to decide the site without going and finding context, because a coder who has to go
# and find context will not: the address, the class reached, why it is here, when it was read, what
# the search was worth, what was found, what the menu offered, and the words behind the findings.
MACHINE_COLUMNS = ('url', 'verdict', 'reason', 'audited_at', 'pages_read', 'crawl_stopped_by',
                   'languages', 'widget', 'switcher', 'declared_off_site', 'evidence')
HUMAN_COLUMNS = ('human_verdict', 'human_languages', 'note', 'coder', 'coded_at')
COLUMNS = MACHINE_COLUMNS + HUMAN_COLUMNS

# Written with a BOM and read tolerant of one. The sheet is opened in Excel or Google Sheets by the
# person filling it in, and Excel reads a UTF-8 file without the BOM as the system code page, which
# turns every quoted Khmer, Arabic and Amharic word in the evidence column into mojibake on the one
# machine the coder is using.
WRITE_ENCODING = 'utf-8-sig'
READ_ENCODING = 'utf-8-sig'

# How many pieces of evidence one row prints, and how much of a quotation. Three, because the row is
# a spreadsheet cell a person reads at a glance and the sites in this queue rarely carry more; the
# rest stay in the run file, which the row's address points at.
EVIDENCE_SHOWN = 3
QUOTE_CHARS = 200

# What a coder writes in `human_languages` to mean the list is empty, as against leaving the cell
# blank, which means they have not said anything about it. Without a word for "none" the two are the
# same cell and a coder cannot state the one finding an english_only verdict rests on.
EMPTY_WORDS = ('none', 'no', '-', 'n/a', 'na')


class SheetRejected(ValueError):
    """A filled sheet that cannot be applied to this run, and every reason it cannot.

    Raised rather than returned, because a report a caller can ignore is a report that gets ignored
    and the thing being ignored here is a row of hand coding landing on the wrong site, or on no
    site at all. `problems` holds one sentence per fault, each naming the sheet row and the address.
    """

    def __init__(self, problems):
        self.problems = list(problems)
        super().__init__('\n'.join(self.problems))


def _records(source):
    """A run as a list of records, plus the path it came from.

    `source` is a path to a JSON-lines file, or an iterable of records already in hand, on the terms
    `diff_runs` takes them: a caller that has read the run itself does not write it back out to work
    on it. A `Result` is converted with `to_dict()`, so both commands work on one shape.
    """
    if isinstance(source, (str, bytes)) or hasattr(source, '__fspath__'):
        path, rows = str(source), read_store(source)
    else:
        path, rows = '', source
    return path, [r if isinstance(r, dict) else r.to_dict() for r in rows]


def _count(q, name):
    return int(q.get(name) or 0)


def _stopped_by(q, pages_stated=False):
    """What ended the crawl, in words, out of what `read_quality_of` recorded.

    Every clause is a field of that record and none is inferred. `unread_locale_links` is here and
    is said separately from `unread`, because it is the one that tells a coder where to look: the
    one Portuguese cultural centre called fifteen pages a sufficient search while twenty
    addresses of the `/pt/` tree it advertises sat unread, and they held the only Portuguese on the
    site.

    `pages_stated` drops the shallow clause for a caller that has just printed the page count, since
    "2 pages read, fewer than 3 pages were read" is one fact charging a reader twice.
    """
    if not q:
        return 'the run recorded nothing about the search'
    parts = []
    if not _count(q, 'pages_read'):
        parts.append('no page answered')
    elif q.get('shallow') and not pages_stated:
        parts.append('fewer than %d pages were read' % READ_ENOUGH_PAGES)
    if q.get('clock_exhausted'):
        parts.append('the time budget ran out')
    if q.get('budget_exhausted'):
        parts.append('the page budget ran out')
    if _count(q, 'reads_timed_out'):
        parts.append('%d reads timed out' % _count(q, 'reads_timed_out'))
    if _count(q, 'reads_failed'):
        parts.append('%d reads failed' % _count(q, 'reads_failed'))
    if _count(q, 'unread'):
        parts.append('%d addresses were found and not read' % _count(q, 'unread'))
    if _count(q, 'unread_locale_links'):
        parts.append('%d %s in the locale tree the site advertises'
                     % (_count(q, 'unread_locale_links'),
                        'of them' if _count(q, 'unread') else 'were found and not read'))
    if q.get('escalated'):
        parts.append('the crawl escalated and kept reading')
    return ', '.join(parts) or 'nothing: the crawl ran out of addresses to look at'


def unsettled_kind(r):
    """Which of the six the reading is, or '' when a person is not needed.

    `r` is a Result from `audit` or `rejudge`, or the dict a stored run holds. Only `verdict`,
    `read_quality`, `authorship` and `declared_off_site` are read; see `needs_human` for what the
    six are and what they leave alone.
    """
    verdict = str(_field(r, 'verdict', '') or '')
    if verdict == UNREACHABLE:
        return UNREAD
    if verdict not in VERDICTS:
        return NO_CLASS
    # Before UNNAMED_CONTROL, which a site can also be in. That one says nothing here can NAME
    # what runs the control; this says the control was named, worked, and did nothing, which is
    # the narrower observation and the one a coder settles in a single look.
    if verdict == MT_ERROR:
        return DEAD_CONTROL
    if str(_field(r, 'authorship', '') or '') == AUTHOR_UNKNOWN_WIDGET:
        return UNNAMED_CONTROL
    # Before the thin-search kind, and for the reason `UNNAMED_CONTROL` is: a site in this state is
    # usually ALSO resting an absence on too little, since a crawl that found no non-English text is
    # what puts it here, and of the two sentences this is the one a coder can act on in a single
    # look. The thin-search clause is carried along in the reason rather than dropped.
    if _only_off_site(r):
        return OFF_SITE_DECLARATION
    if verdict == ENGLISH_ONLY and not (_field(r, 'read_quality', {}) or {}).get('sufficient'):
        return THIN_ABSENCE
    return ''


def _off_site(r):
    """The reading's `declared_off_site`, in the shape this module expects, whatever it holds.

    A record written before the field existed carries nothing, and a record from a run that never
    passed a base carries zeros. Both mean the same thing here, which is that nothing was observed.
    """
    got = _field(r, 'declared_off_site', {}) or {}
    if not isinstance(got, dict):
        return 0, []
    return int(got.get('alternates') or 0), [str(x) for x in (got.get('languages') or [])]


def _only_off_site(r):
    """Did every non-English language on this record ARRIVE from an address at another site?

    The shape a person settles in one look: the crawl read this site and found nothing but English,
    and the record names another language anyway, on the word of an alternate pointing somewhere
    else. Either the organization publishes that language on a second domain of its own, which is
    ordinary, or this address is not the organization's any more. Nothing in the document decides
    which, so the reading goes to a person with the alternate's address in the row.

    BOTH HALVES ARE REQUIRED, and the second is the strict one. There has to be a language that no
    alternate on this site named, AND the reading's own findings have to name no non-English
    language at all. A language the crawl read off this site's own pages did not arrive from
    anywhere else, whatever the declaration also says: one supplementary school publishes its
    Chinese and Korean under a `/training` path of its own, where the crawl read them, and declares
    its alternates on a second domain it also owns. An earlier form of this predicate asked only
    whether the found languages were a SUBSET of the declared-elsewhere ones and put that site in
    the queue, where there is nothing for a coder to decide.

    English is left out of the comparison for the reason it is left out everywhere else here.
    """
    _alternates, off = _off_site(r)
    if not off:
        return False
    found = {str(x) for x in (_field(r, 'languages', []) or [])} - {SWITCHER_ENGLISH}
    return not found


def unsettled_reason(r):
    """Why this reading needs a person, in a sentence, or '' when it does not.

    The sentence is what goes in the sheet, in place of the kind, because the coder acts on it. It
    carries the note where the reading left one, since 'bot wall' and 'HTTP 403 on the home page'
    are the difference between an address worth opening by hand and one that is gone.
    """
    kind = unsettled_kind(r)
    if not kind:
        return ''
    if kind == UNREAD:
        note = str(_field(r, 'note', '') or '')
        return ('the site was not read%s, so nothing is established about its languages in either '
                'direction. Open the address and record what a visitor finds.'
                % (' (%s)' % note if note else ''))
    if kind == NO_CLASS:
        verdict = str(_field(r, 'verdict', '') or '')
        return ('the run recorded %s for this address, so no reading of it has been settled. Open '
                'the address and record what a visitor finds.'
                % ('no verdict' if not verdict else 'the verdict %r, which is not one of the '
                                                    'classes this package defines' % verdict))
    if kind == DEAD_CONTROL:
        note = str(_field(r, 'note', '') or '')
        return ('a translation widget is on this site, a control on it was operated, and the '
                'page did not change%s. That is what an automated browser could obtain and not '
                'a finding about the site: a widget can work in one browser and not another, '
                'and one government site in this state translates for a visitor on a phone. '
                'Open the address, operate the control, and record whether a visitor gets '
                'another language.' % (' (%s)' % note if note else ''))
    if kind == UNNAMED_CONTROL:
        # A site can be in this state AND resting its absence claim on too thin a search, and a
        # coder needs both facts. This kind is reported first because the control is the thing one
        # click settles, and the thin-search clause is carried along rather than dropped.
        q = dict(_field(r, 'read_quality', {}) or {})
        thin = ('' if q.get('sufficient') else
                ' The search behind the absence is also too thin to rest it on: %d pages read, %s.'
                % (_count(q, 'pages_read') or int(_field(r, 'pages_read', 0) or 0),
                   _stopped_by(q, pages_stated=True)))
        return ('a control labelled Translate is on this site, no pattern here can name what runs '
                'it, and no non-English text was found. The reading stands at %r and that is the '
                'absence claim, not a finding about the control: it may be a working machine '
                'translator, a link to an English page about translating, or a menu into the '
                "organization's own languages. Click it and record which.%s"
                % (str(_field(r, 'verdict', '') or ''), thin))
    if kind == OFF_SITE_DECLARATION:
        alternates, off = _off_site(r)
        q = dict(_field(r, 'read_quality', {}) or {})
        thin = ('' if q.get('sufficient') else
                ' The search behind the absence is also too thin to rest it on: %d pages read, %s.'
                % (_count(q, 'pages_read') or int(_field(r, 'pages_read', 0) or 0),
                   _stopped_by(q, pages_stated=True)))
        return ('every non-English language on this record (%s) was named only by an alternate '
                'whose address is on another site, and %d alternate%s here leave%s it. The '
                'declaration is a true statement about the document; whose site it points at is a '
                'different question and this package cannot answer it. Open the address: either '
                'the organization publishes that language on a second domain of its own, which is '
                'ordinary, or this address has lapsed and now serves somebody else, in which case '
                'nothing here describes the organization at all.%s'
                % (', '.join(off), alternates, '' if alternates == 1 else 's',
                   's' if alternates == 1 else '', thin))
    q = dict(_field(r, 'read_quality', {}) or {})
    return ('no non-English text was found and the search behind that absence is too thin to rest '
            'it on: %d pages read, %s. Look for a language the crawl did not reach.'
            % (_count(q, 'pages_read') or int(_field(r, 'pages_read', 0) or 0),
               _stopped_by(q, pages_stated=True)))


def needs_human(r):
    """Does this reading need a person to settle it.

    Six states, read off the verdict, `read_quality`, `authorship` and `declared_off_site` and off
    nothing else:

      unreachable       always. The site was not read at all, so the record holds no reading to
                        disagree with, and a person opening the address is the only thing that
                        turns it into one.
      english_only      where `read_quality['sufficient']` is false, which is the field's own
                        statement that the search will not carry an ABSENCE claim, and
                        `english_only` is the only class that makes one. A record
                        with no `read_quality` at all is in this state for the same reason: nothing
                        says how much reading the absence rests on.
      machine_translate_error
                        always. A widget was there, a control on it was worked, and the page did
                        not change, which is what THIS client could obtain and not a finding about
                        the site. A person opening the address and operating the control is the
                        only thing that settles it, and one government site in the class translates
                        for a visitor on a phone.
      no class          a verdict outside those this package defines, the empty string included.
                        The run did not settle on a class, and a blank read as a class is how a
                        gap becomes a finding.

      off-site          every non-English language on the record was named only by an alternate
      declaration       whose address is on another site, and the reading's own findings name
                        nothing else. `declared_languages` reports the language, because the
                        document does declare it and that is true of the bytes; whether the address
                        it points at belongs to this organization is a separate fact no document
                        settles. Refusing the language instead was written and measured on
                        2026-08-05 and was wrong on eleven of nineteen hand-read moves, all of them
                        an organization publishing on a second domain of its own. One look settles
                        it, so it is asked for rather than guessed at.

      unnamed control   `authorship` is `unknown_widget`: a control labelled Translate was drawn,
                        no vendor pattern could name it, and no non-English text was found.
                        Over the county-gap draw of 2026-08-05, a
                        rule flooring such a site at machine_translate would have named 44 sites
                        that nothing else names and been wrong on three of them, and all three
                        wrong the same way: a county whose Translate button opens an English page
                        about using the browser's own translator, and two cities whose second
                        language they wrote themselves. The reading these sites carry is an absence
                        claim that stands on its own terms; what is unsettled is the control, and
                        one click settles it.

    WHAT IT DELIBERATELY DOES NOT FLAG. A thin search behind `machine_translate` or
    `true_multilingual`: those verdicts rest on something that was FOUND, and a thin search that
    found it is right for the same reason a thorough one is, which is `read_quality_of`'s own
    statement about its own field. An `english_only` verdict on a search the record calls
    sufficient: the claim is bounded by the routes that were read and the bound is on the record,
    and flagging it would put the whole run in the queue and settle nothing. A language menu
    carrying entries this package cannot name: the menu is not the verdict, and a site whose reading
    is otherwise settled is not unsettled by it. The count is on the record and the sheet prints it
    beside the menu, so a coder queueing those sites by hand has the number in front of them, but no
    reading enters this queue on it alone. A verdict a person would disagree with: this predicate
    reads the record, and the record does not know that. The agreement figure in
    LIMITATIONS.md is where a disagreement rate lives, and no queue can stand in for it.
    """
    return bool(unsettled_kind(r))


def contested(r):
    """The shapes the model coders split over, when this reading carries one. A tuple, often empty.

    A different question from `needs_human`, and the two never overlap by construction:
    `needs_human` flags a reading the package cannot stand behind, and this flags a reading it
    STANDS BEHIND whose shape is where the blind coders of the validation disagreed with each other.
    The docstring of `needs_human` says a queue cannot know which verdicts a person would dispute;
    this function is the exception, because those splits concentrate in two shapes a Result records
    about itself.

      fragment_beside_widget   a named widget on the site, verdict `true_multilingual`, and the
                               authored evidence reaching only the notice rung. The organization
                               wrote SOMETHING in the language and a widget offers the rest, so the
                               verdict turns on whether one authored passage outweighs the widget.
      one_language_notice      one non-English language on the record, at notice level, carrying
                               the class by itself. No second language corroborates, and one
                               misread passage is the whole verdict.

    No figure is attached to this function, and no reading moves on it: it writes no field, and a
    caller who ignores it holds exactly the reading they held before.
    """
    if unsettled_kind(r):
        return ()
    verdict = str(_field(r, 'verdict', '') or '')
    widget = str(_field(r, 'machine_translation', '') or '')
    # A record with no sufficiency field carries no observation of the rung, and both shapes are
    # statements ABOUT the rung, so such a record carries neither. Reading the absence as zero
    # instead would flag every row of a run written before the axis existed.
    suff = _field(r, 'sufficiency', None)
    if suff is None:
        return ()
    suff = int(suff or 0)
    langs = [str(x) for x in (_field(r, 'languages', []) or []) if str(x) != 'English']
    out = []
    if widget and verdict == 'true_multilingual' and suff <= 2:
        out.append(CONTESTED_FRAGMENT)
    if verdict in ('true_multilingual', 'machine_translate') and len(langs) == 1 and suff <= 2:
        out.append(CONTESTED_ONE_LANGUAGE)
    # RULE 15 IS THE ONLY RULE THAT CAN OVERRIDE THE TWO AXES. It returns from `verdict_for` before
    # `class_for` is ever asked, so a site whose reading reached the page or section rung on its own
    # authorship still lands in machine_translate on the shape of its addresses. Over the 1,000-site
    # validation capture the rule fires on six sites and ALL SIX are that case: four `authored` at
    # rung 4, one `authored` at rung 3, one `server_plugin` at rung 4. Not one of them reached this
    # queue or the unsettled one, so the shape with the most power in the file was also the least
    # visible.
    #
    # Read off `rules` rather than re-derived, so this says only that the rule fired. The reading is
    # untouched: a localization engineer proposed a guard that would move two of the six into
    # true_multilingual, and the settled coding for one of those two, an adult literacy centre,
    # is machine_translate by two coders to one. A shape people disagree about is what this layer
    # is for, and it is not an argument for changing the verdict.
    try:
        fired = {int(x) for x in (_field(r, 'rules', []) or [])}
    except (TypeError, ValueError):
        fired = set()
    if 17 in fired and verdict == 'machine_translate' and suff >= 3:
        out.append(CONTESTED_LOCALE_MIRRORS)
    return tuple(out)


def contested_reason(r):
    """Why this settled reading is worth a second look, in a sentence, or '' when it is not."""
    kinds = contested(r)
    if not kinds:
        return ''
    parts = [CONTESTED_TITLE[k] for k in kinds]
    return ('settled, and carrying the shape the model coders split over: %s. The reading stands; '
            'this row is here because a person who disagrees with it is in measured company.'
            % '; '.join(parts))


def _evidence_cell(r):
    """The words behind the findings, each with the address it was read at, for one cell."""
    evidence = list(_field(r, 'evidence', []) or [])
    out = []
    for e in evidence[:EVIDENCE_SHOWN]:
        quote = ' '.join(_ev_quote(e).split())
        # `_snip` and not a bare slice, and the ellipsis says the cell was cut: a coder reading
        # this sheet was shown a quote that stopped inside a word with nothing to say it had.
        shown = _snip(quote, 0, QUOTE_CHARS) if quote else ''
        if shown and len(quote) > len(shown):
            shown += '...'
        out.append(('%s %s %s' % (_ev_lang(e) or '-', _ev_url(e),
                                  '"%s"' % shown if shown else '')).strip())
    if len(evidence) > EVIDENCE_SHOWN:
        out.append('and %d more, all of them in the run file' % (len(evidence) - EVIDENCE_SHOWN))
    return ' | '.join(out)


def _switcher_cell(r):
    """What the site's language MENU offered, which is a different question from what it is written
    in, and how many of its entries this package has no name for."""
    names = [str(x) for x in (_field(r, 'switcher_languages', []) or [])]
    unresolved = int(_field(r, 'switcher_unresolved', 0) or 0)
    if not unresolved:
        return ', '.join(names)
    return ((', '.join(names) + '  ') if names else '') + \
        '(+%d this tool cannot name)' % unresolved


def _off_site_cell(r):
    """Where the declaration pointed, for one cell, and nothing about whose site that is."""
    alternates, off = _off_site(r)
    if not alternates:
        return ''
    return ('%d alternate%s on another site%s'
            % (alternates, '' if alternates == 1 else 's',
               (': %s named there and nowhere on this one' % ', '.join(off)) if off else ''))


def review_row(r):
    """One reading as the row a coder fills in. Every filled cell was written by the audit."""
    q = dict(_field(r, 'read_quality', {}) or {})
    return {
        'url': str(_field(r, 'url', '') or ''),
        'verdict': str(_field(r, 'verdict', '') or ''),
        'reason': unsettled_reason(r),
        'audited_at': str(_field(r, 'audited_at', '') or ''),
        'pages_read': _count(q, 'pages_read') or int(_field(r, 'pages_read', 0) or 0),
        'crawl_stopped_by': _stopped_by(q),
        'languages': ', '.join(str(x) for x in (_field(r, 'languages', []) or [])),
        'widget': str(_field(r, 'machine_translation', '') or ''),
        'switcher': _switcher_cell(r),
        'declared_off_site': _off_site_cell(r),
        'evidence': _evidence_cell(r),
        'human_verdict': '',
        'human_languages': '',
        'note': '',
        'coder': '',
        'coded_at': '',
    }


def review_queue(run):
    """Every reading in a run that needs a person, with what a coder needs in order to decide it.

    `run` is a path to a JSON-lines run file, or an iterable of records already in hand. The dict
    returned is the machine-readable form; `review_text` renders it for a person and `write_review`
    writes the sheet. `records` is the count scanned and is reported whatever it is, because a queue
    of nothing and a run of nothing print the same sentence unless the denominator is said.
    """
    path, records = _records(run)
    rows, kinds = [], collections.Counter()
    contested_rows, contested_kinds = [], collections.Counter()
    for rec in records:
        kind = unsettled_kind(rec)
        if kind:
            kinds[kind] += 1
            rows.append(review_row(rec))
            continue
        shapes = contested(rec)
        if shapes:
            for s in shapes:
                contested_kinds[s] += 1
            row = review_row(rec)
            row['reason'] = contested_reason(rec)
            contested_rows.append(row)
    # The contested rows ride at the END of the sheet, after the unsettled, and are counted apart
    # everywhere: a reading the package cannot settle and a reading it settled in disputed shape
    # are different kinds of work, and a queue that sums them hides the one number a run is judged
    # by, how much of it a person MUST do.
    return {'path': path, 'records': len(records), 'unsettled': len(rows),
            'settled': len(records) - len(rows), 'kinds': dict(kinds),
            'contested': len(contested_rows), 'contested_kinds': dict(contested_kinds),
            'rows': rows + contested_rows, 'columns': list(COLUMNS)}


def write_review(q, path):
    """Write the queue as a sheet a person fills in, and return how many rows were written.

    `q` is a queue from `review_queue` or a run to build one from. A queue with no rows raises
    rather than writing a header and reporting success: an empty sheet is indistinguishable from a
    finished one once it is on disk, and this project has shipped that mistake six times.
    """
    if not (isinstance(q, dict) and 'rows' in q):
        q = review_queue(q)
    if not q['rows']:
        raise ValueError('nothing to review: none of the %d records in this run needs a person, so '
                         'no sheet was written' % q['records'])
    def _safe(v):
        # a cell a spreadsheet would read as a formula (=, +, -, @, tab, CR lead) is prefixed
        # with an apostrophe, so a site's own text cannot execute when the sheet is opened
        s = '' if v is None else str(v)
        lead = s[0] if s else ''
        return (chr(39) + s) if lead in (chr(61), chr(43), chr(45), chr(64), chr(9), chr(13)) else s
    with open(path, 'w', encoding=WRITE_ENCODING, newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=list(COLUMNS))
        w.writeheader()
        w.writerows({k: _safe(v) for k, v in row.items()} for row in q['rows'])
    return len(q['rows'])


def _sites(n):
    """`1 site`, `4 sites`. A count a person reads should not read as a template."""
    return '%d site%s' % (n, '' if n == 1 else 's')


def review_text(q, output=''):
    """The queue as lines a person reads, the count drawn from beside the count found."""
    contested_n = int(q.get('contested', 0) or 0)
    contested_kinds = q.get('contested_kinds', {}) or {}
    out = ['langaccess review']
    add = out.append
    # the column is as wide as its own longest title; 52 was set by hand and five titles
    # outgrew it, so the count column went ragged
    width = max(len(v) for v in list(KIND_TITLE.values()) + list(CONTESTED_TITLE.values()))
    add('  %s   %d records read' % (q['path'] or '(records)', q['records']))
    add('  need a person   %s of %d' % (_sites(q['unsettled']), q['records']))
    for kind in KIND_ORDER:
        if q['kinds'].get(kind):
            add('    %-*s %d' % (width, KIND_TITLE[kind], q['kinds'][kind]))
    add('  settled by the package   %d' % q['settled'])
    if contested_n:
        # settled and counted as settled; this block is the second look, never the queue
        add('  settled, in a shape the model coders split over   %s' % _sites(contested_n))
        for kind in CONTESTED_KINDS:
            if contested_kinds.get(kind):
                add('    %-52s %d' % (CONTESTED_TITLE[kind], contested_kinds[kind]))
    if not q['rows']:
        add('  nothing to review, so no sheet was written')
        return '\n'.join(out)
    if output:
        add('')
        add('  written to %s, %s' % (output, _sites(len(q['rows']))))
        add('  fill human_verdict, human_languages and note, then:')
        add('    langaccess ingest %s %s' % (output, q['path'] or 'run.jsonl'))
    return '\n'.join(out)


def read_review(sheet):
    """The filled sheet as a list of rows, in the order the file holds them.

    `sheet` is a path to the CSV `write_review` wrote, or an iterable of row dicts. A file whose
    header holds neither `url` nor `human_verdict` is not this sheet and is rejected as one, rather
    than read as a sheet in which nobody wrote anything.
    """
    if not (isinstance(sheet, (str, bytes)) or hasattr(sheet, '__fspath__')):
        return [dict(row) for row in sheet]
    with open(sheet, 'r', encoding=READ_ENCODING, newline='') as fh:
        reader = csv.DictReader(fh)
        header = list(reader.fieldnames or ())
        rows = [dict(row) for row in reader]
    for want in ('url', 'human_verdict'):
        if want not in header:
            raise SheetRejected(['%s has no %s column, so it is not a review sheet. The columns '
                                 'written by `langaccess review` are: %s'
                                 % (sheet, want, ', '.join(COLUMNS))])
    return rows


def _cell(row, name):
    return str(row.get(name) or '').strip()


def _languages_from(text):
    """A coder's language list, or None where they left the cell alone.

    None and the empty list are different answers: a blank cell is a
    coder who has said nothing about the languages, and the machine's list stands; one of
    EMPTY_WORDS is a coder saying there are none, and it clears the list. Without the distinction an
    `english_only` hand verdict either cannot state its own finding or silently wipes a list nobody
    looked at.
    """
    text = str(text or '').strip()
    if not text:
        return None
    if text.lower() in EMPTY_WORDS:
        return []
    return [part.strip() for part in text.replace(';', ',').split(',') if part.strip()]


def _ev_mech_of(e):
    """The mechanism of a piece of evidence, whichever shape it is in.

    `core._ev_mech` indexes a dict rather than getting, which is right for evidence the crawl wrote
    and wrong for a record a caller assembled by hand; this is asked of records from anywhere.
    """
    if isinstance(e, dict):
        return str(e.get('mechanism') or '')
    return str(getattr(e, 'mechanism', '') or '')


def hand_coding(record):
    """The hand coding on one record, or None where a person never touched it.

    The last one, because a record coded twice was coded a second time for a reason. Counting the
    records this answers on is how a table of mixed readings says what share of a figure came from a
    person:

        share = sum(1 for rec in read_store('run.jsonl') if hand_coding(rec)) / n
    """
    got = None
    for e in (_field(record, 'evidence', []) or []):
        if _ev_mech_of(e) == HAND_CODING:
            got = e
    return got


def _hand_coding_entry(record, row, verdict, languages, ingested_at):
    """One act of hand coding, as a piece of evidence the record carries from here on.

    It is evidence and not a field, because that is where this package puts a thing it observed
    along with what it observed it from. `machine_verdict` and `machine_languages` are the reading
    this replaced, kept beside it: a hand verdict that overwrites a machine verdict and leaves no
    trace of it makes the two indistinguishable in every later count.

    `language` is deliberately empty. Every reader of an evidence list asks it for a language, and a
    hand coding is a statement about the SITE; the languages the coder named are on the record and
    on `human_languages` here, where nothing derives a per-language reading from them.
    """
    entry = {
        'mechanism': HAND_CODING,
        'url': str(_field(record, 'url', '') or ''),
        'quote': _cell(row, 'note'),
        'language': '',
        'server_html': False,
        'server_plugin': False,
        'authorship': '',
        'sufficiency': 0,
        'rules': [],
        'machine_verdict': str(_field(record, 'verdict', '') or ''),
        'machine_languages': [str(x) for x in (_field(record, 'languages', []) or [])],
        'human_verdict': verdict,
        'human_languages': list(languages) if languages is not None else None,
        'reason': _cell(row, 'reason'),
        'coder': _cell(row, 'coder'),
        'coded_at': _cell(row, 'coded_at'),
        'ingested_at': ingested_at,
    }
    return entry


def ingest_review(sheet, run, ingested_at=None):
    """Read a filled sheet back into a run, and report what a person decided.

    Returns `(records, report)`. `records` is every record of the run, in the order the run holds
    them, with the hand codings applied; `report` is what was applied and what was not.
    `write_records` writes the first, `ingest_text` renders the second.

    A hand verdict wins over the machine's and is recorded as one, on the terms in the module
    docstring. A blank `human_verdict` is a row nobody finished, and it is counted and left alone
    rather than read as agreement, since a coder who wrote nothing has not agreed with anything.

    The sheet is rejected whole, by `SheetRejected`, when any row cannot be applied: an address that
    is not in this run, an address written twice, an address missing, or a `human_verdict` outside
    the classes this package defines. Rejected whole and not row by row, because a sheet with a wrong address in it
    is a sheet somebody built against a different run, and applying the rows that happen to match
    would put half a coding round into a file and report success.
    """
    rows = read_review(sheet)
    sheet_path = str(sheet) if isinstance(sheet, (str, bytes)) or hasattr(sheet, '__fspath__') \
        else ''
    run_path, records = _records(run)

    # every address in the run, and the LAST record holding it, which is the row a store's appending
    # leaves as the current reading and the one `_stored_record` and `diff_runs` both read
    at = {}
    for i, rec in enumerate(records):
        key = _key(_field(rec, 'url', ''))
        if key:
            at[key] = i

    problems, seen, wanted = [], {}, {}
    # the header is row 1, so the first row of data is row 2, which is what the coder's spreadsheet
    # shows them and therefore what a message about a bad row has to say
    for n, row in enumerate(rows, start=2):
        url = _cell(row, 'url')
        key = _key(url)
        if not key:
            problems.append('row %d has no address' % n)
            continue
        if key not in at:
            problems.append('row %d: %s is not in %s' % (n, url, run_path or 'this run'))
            continue
        if key in seen:
            problems.append('row %d: %s is also on row %d' % (n, url, seen[key]))
            continue
        seen[key] = n
        verdict = _cell(row, 'human_verdict')
        if not verdict:
            continue
        if verdict not in VERDICTS:
            problems.append('row %d: %s has human_verdict %r, which is not one of %s'
                            % (n, url, verdict, ', '.join(VERDICTS)))
            continue
        wanted[key] = (n, row, verdict)
    if problems:
        raise SheetRejected(problems)

    out, applied, moved = [], [], collections.Counter()
    for i, rec in enumerate(records):
        key = _key(_field(rec, 'url', ''))
        got = wanted.get(key) if at.get(key) == i else None
        if got is None:
            out.append(rec)
            continue
        _n, row, verdict = got
        languages = _languages_from(row.get('human_languages'))
        entry = _hand_coding_entry(rec, row, verdict, languages,
                                   ingested_at or _utc_now())
        settled = dict(rec)
        settled['verdict'] = verdict
        if languages is not None:
            settled['languages'] = list(languages)
        settled['evidence'] = list(rec.get('evidence') or []) + [entry]
        out.append(settled)
        applied.append(settled['url'] if settled.get('url') else _field(rec, 'url', ''))
        moved['%s -> %s' % (entry['machine_verdict'] or '(none)', verdict)] += 1

    report = {
        'sheet': sheet_path, 'run': run_path,
        'records': len(records), 'rows': len(rows),
        'applied': applied, 'blank': len(rows) - len(wanted),
        'verdicts': dict(moved),
        'unchanged': len(records) - len(applied),
    }
    return out, report


def write_records(records, path):
    """Write a run back out, one JSON object per line, gzipped when the path says so.

    The same form `--store` and `--json --output` write, so what comes out of an ingest is a run
    file every other command in this package already reads.
    """
    opener = (lambda: gzip.open(path, 'wt', encoding='utf-8')) if str(path).endswith('.gz') \
        else (lambda: open(path, 'w', encoding='utf-8'))
    n = 0
    with opener() as fh:
        for rec in records:
            fh.write(json.dumps(rec, ensure_ascii=False) + '\n')
            n += 1
        # flushed to disk before the atomic rename that follows at the ingest call site, the
        # way retry has always done it: the rename's guarantee is only as good as the bytes
        # being on disk when it runs
        fh.flush()
        os.fsync(fh.fileno())
    return n


def ingest_text(report, written=''):
    """What a person decided, as lines a person reads."""
    out = ['langaccess ingest']
    add = out.append
    add('  %s   %d rows' % (report['sheet'] or '(rows)', report['rows']))
    add('  %s   %d records' % (report['run'] or '(records)', report['records']))
    add('  hand verdicts applied   %d' % len(report['applied']))
    # as wide as the widest move actually present, since 46 was set before
    # machine_translate_error existed and 'machine_translate_error -> machine_translate_error'
    # is fifty characters
    moves = sorted(report['verdicts'].items(), key=lambda kv: (-kv[1], kv[0]))
    move_w = max([len(p) for p, _ in moves] or [0])
    for pair, n in moves:
        add('    %-*s %d' % (move_w, pair, n))
    add('  rows left blank   %d' % report['blank'])
    add('  records the machine reading still stands on   %d' % report['unchanged'])
    if not report['applied']:
        add('  nothing was applied: no row of this sheet carries a human_verdict')
    if written:
        add('  written to %s' % written)
    return '\n'.join(out)
