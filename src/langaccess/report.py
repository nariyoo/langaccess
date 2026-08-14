# -*- coding: utf-8 -*-
"""One reading of one site, as a document a person outside this project can read.

    langaccess report run.jsonl https://example.org -o report.html
    langaccess report run.jsonl --all --dir reports/

    from langaccess import audit, report, report_text, report_html, write_report
    r = audit('https://example.org')
    print(report_text(r))
    write_report(r, 'example.html')

The other three layers over a reading are for the people who took it. `explain` answers a
methodologist, `diff` answers a study comparing two runs, and `review` hands a coder a spreadsheet.
None of the three can be handed to the organization whose site was read, and this module writes the
document this project keeps being asked for: one site, one page of paper, addressed to a city clerk or a
hospital's language-access officer who has never heard of this package and has no reason to trust it.

NOTHING HERE JUDGES A SITE. On the pattern of `explain`, `diff` and `review`: every number, every
quotation and every class below was written by the audit that produced the reading, and this module
arranges them. The one function it calls that decides anything is `counted_evidence`, which is the
same call the verdict made, and `explain` is where the rule statuses come from rather than a second
copy of them.

WHAT THE DOCUMENT CARRIES, and why each part is not optional. The classification, with a sentence
saying what that class means, because the five words this package uses are its own vocabulary and
`machine_translate` is not self-explaining. The languages, one at a time, with the two axes the
class was derived from, because a site with Spanish its staff wrote and Vietnamese a widget produces
has one of each and a single summary hides it. The evidence, quoted, each quotation with the address
it was read at, so that somebody handed a reading can go and check it
against their own site. The rules that decided it, by number and title. What the crawl read and what
it did not, because the `english_only` class asserts an ABSENCE and an absence claim is worth what
the search behind it was worth. The date and the version, because a reading describes one address at
one moment under one rule set.

WHAT IT STATES ABOUT ITSELF. `LIMITS` is the part of this module to change most carefully. A
document handed to an organization is exactly where a description gets read as a verdict, and this
package makes no determination of compliance with any law, regulation or professional guidance and
holds no threshold at which a site becomes adequate. That statement is rendered in full in every
form of the document, at the foot where a reader who has read the finding arrives at it, and it is
not abbreviated for the plain-text form or dropped from the HTML.

AN EMPTY DOCUMENT IS AN ERROR. A record with no address, and a record carrying no class, no
evidence, no languages and no record of the search, is not a site with nothing to report; it is a
row that never held a reading, and `report` raises `NothingToReport` rather than rendering a page of
headings over blanks. This project's most frequent bug is a stage that produced nothing and reported
success, and a per-site document is the shape that invites it, since a site with genuinely nothing
found and a record that was never filled in render the same way unless one of them is made to fail.
"""
import html
import textwrap

from .core import (RULES, SUFFICIENCY_NAMES, _snip,
                   AUTHOR_AUTHORED, AUTHOR_CLIENT_WIDGET, AUTHOR_NONE, AUTHOR_SERVER_PLUGIN,
                   AUTHOR_UNKNOWN_WIDGET,
                   SUFF_NONE, SUFF_NOTICE, SUFF_PAGE, SUFF_SECTION, SUFF_TOKEN,
                   counted_evidence, _ev_lang, _ev_mech, _ev_quote, _ev_recorded, _ev_url)
# One definition of each rather than a second copy that can answer differently. `explain` is where a
# rule's status is decided, `_field` is how a Result and a stored dict are read through one
# expression, and `_stopped_by` is the sentence `review` already puts in front of a coder.
from .explain import FIRED, FIRED_UNCOUNTED, _field, explain
from .review import HAND_CODING, _stopped_by, hand_coding, unsettled_kind, unsettled_reason


class NothingToReport(ValueError):
    """A record that never held a reading, handed to a function that renders one.

    Raised rather than returned, and raised rather than rendering a document with empty sections in
    it, because a document is the artifact that leaves this project: a page of headings over blanks
    reads as a finished audit of a site with nothing to find.
    """


# What each class means, in a sentence somebody who has never used this package can
# read. The words are the ones README.md settles on, and they belong here rather than in the
# renderer so that both forms of the document say the same thing.
CLASS_MEANING = {
    'english_only': (
        'No text in a language other than English was found on the pages this reading covered. '
        'The statement is bounded by those pages, which are listed under the search below, and it '
        'is not a statement about the site as a whole.'),
    'machine_translate': (
        'The site carries a translation widget, and no text in another language was found outside '
        "what that widget produces. A widget rewrites the English page in a reader's browser: the "
        # The clause here used to read `and no person at the organization has read them`. It said
        # two things it had no right to. It asserted a fact about the organization's staff that no
        # crawler observed and that may be false, since somebody may have checked the output. And it
        # stated, almost word for word, the operative test of a regulatory definition: 45 CFR 92.4
        # defines machine translation as automated translation "without the assistance of or review
        # by a qualified human translator". This module's output goes TO the organization, so
        # in front of a covered entity that sentence reads as a finding under the rule. What the
        # crawler actually saw is in the replacement.
        'words it shows were not written by the organization, they are unavailable whenever the '
        'widget does not load, and they are produced in the reader\'s browser at the moment of '
        'reading rather than published by the organization.'),
    'machine_translate_error': (
        'The site carries a translation widget, a control on it was operated, and the page did '
        'not change. What the reading establishes is that this automated browser could not '
        'obtain a translation through it on the date above. That is not the same as the site '
        'having no other language, and it is not the same as the widget being broken for every '
        'visitor: a widget can work in one browser and not another. Anyone acting on this '
        'should open the site and operate the control.'),
    'true_multilingual': (
        'Text in another language was in the document the server sent, so no browser-side widget '
        'produced it. Whether the organization wrote it or a translation plugin on the server did '
        'is recorded per language below.'),
    'unreachable': (
        'The site was not read. This is an outcome of the reading and not a description of the '
        'site: a bot wall, a timeout, a parked domain or an empty response leaves nothing '
        'established about the languages the site offers, in either direction.'),
}

# Who produced the non-English text, in the same register. `unknown_widget` is the one that has to
# be careful: it is a statement about a control nobody here could name and not a finding about what
# the control does.
AUTHORSHIP_MEANING = {
    AUTHOR_AUTHORED: (
        'the text was in the document the server sent, and nothing on the page indicated a '
        'translation tool produced it'),
    AUTHOR_SERVER_PLUGIN: (
        'the text was in the document the server sent, and that document also carried the marker '
        'of a translation plugin, so the plugin may have produced it'),
    AUTHOR_CLIENT_WIDGET: (
        'a translation widget runs in the browser and the text was not in the document the server '
        'sent, so the widget produced it'),
    AUTHOR_UNKNOWN_WIDGET: (
        'a control labelled Translate is on the page and no pattern in this package can name what '
        'runs it. What a visitor gets from that control is unsettled here'),
    AUTHOR_NONE: 'no text in another language was found',
}

# What a reader of the site actually receives at each rung, which is the second axis. The rung names
# come from SUFFICIENCY_NAMES; these are what the names mean.
SUFFICIENCY_MEANING = {
    SUFF_NONE: 'nothing in this language',
    SUFF_TOKEN: 'a name, a slogan or a menu label, and no connected writing',
    SUFF_NOTICE: 'a passage in this language inside a page that is otherwise in another language',
    SUFF_PAGE: 'a page written in this language',
    SUFF_SECTION: (
        'two or more pages in this language, or a set of addresses the site publishes for this '
        'language'),
}

# What each kind of finding is. `translation_plugin` names a tool and no language, which is why a
# marker on its own carries no reading; see rule 11.
MECHANISM_MEANING = {
    'inline_text': 'a passage in this language, inside a page',
    'translated_page': 'a page written in this language',
    'language_control': "a page reached through the site's own language control",
    'translation_plugin': (
        'a marker of a translation plugin in the document the server sent. It names a tool and no '
        'language, and on its own it is not a translation'),
    HAND_CODING: 'a reading a person took by hand, recorded beside the reading this package took',
}

# The two rule states this document reports, and what each means to somebody reading it about their
# own site. The full five-state table, including the rules a reading says nothing about, is what
# `langaccess --explain` prints; a document for an organization reports what happened rather than a
# grid of what did not.
RULE_STATUS_MEANING = {
    FIRED: 'The rules that decided the classification above',
    FIRED_UNCOUNTED: (
        'Rules that read a finding the classification did not count. The finding is on the record '
        'and is quoted with the rest'),
}

# The scope statement, rendered in full in every form of the document. The wording is the one
# README.md settles on, and the ordering is deliberate: the compliance limit first, because it is
# the one a document handed to an organization is most likely to be read against.
LIMITS = (
    ('The limit of this document',
     'This is a description of what one website presented to a crawler on one day. It is not a '
     'determination of compliance with any federal or state law, with any regulation made under '
     'one, or with any professional guidance on interpretation, and this package holds no '
     'threshold at which a site becomes adequate. Nothing here has been reviewed by a lawyer or by '
     'any agency, and no part of it should be quoted as a finding of adequacy or of failure.'),
    ('Translation quality',
     'The reading records which languages were found and who produced the text. It does not judge '
     'how good the writing is, so fluent Spanish an organization wrote and clumsy Spanish an '
     'organization wrote are classified alike.'),
    ('Service beyond the website',
     'A website is not a service. Whether a person can obtain help in a language turns on the '
     'telephone line, the intake desk, the interpreter roster and the hours at which somebody '
     'answers. None of that is stated on a website and none of it was read here.'),
    ('The bound on an absence',
     'Where this reading found no text in a language, that covers the pages the search reached and '
     'nothing else. A page the crawl did not reach, a document behind a download link, and content '
     'behind a login are all outside it. The search is reported above so that the bound can be '
     'read rather than assumed.'),
    ('One site, one moment, one rule set',
     'A reading describes one address, on the date printed above, under the rule set of the '
     'version printed beside it. Sites change and rules are revised, so a reading is not carried '
     'forward: a later question about this site is answered by reading the site again.'),
)

# How much of a quotation is printed. Longer than the terminal and sheet forms allow, because this
# document exists to be checked against the site and a reader matching a sentence needs the
# sentence. The full text of every quotation is on the record the document was rendered from.
QUOTE_CHARS = 400

# The width the plain-text form wraps a paragraph to.
TEXT_WIDTH = 92

# What a language with no name is called in the document. A translation-plugin marker is the piece
# of evidence that names a tool and no language, and it is reported rather than dropped.
NO_LANGUAGE = '(no language named)'


def _findings(n):
    """`1 finding`, `4 findings`. A count a person reads should not read as a template."""
    return '%d finding%s' % (n, '' if n == 1 else 's')


def _under(row):
    """What one language has below it, said so that nothing reads as a count of nothing."""
    if not row['findings']:
        return 'No quotation in this language is on the record.'
    return '%s, quoted below.' % _findings(len(row['findings']))


def _carries_a_reading(r):
    """Does this record hold a reading at all.

    An address plus any one of: a class, a piece of evidence, a language, or a record of the search.
    A record with none of them is not a site on which nothing was found; it is a row nobody ever
    filled in, and rendering it produces a document that reads as a finished audit.
    """
    if not str(_field(r, 'url', '') or '').strip():
        return False
    return bool(str(_field(r, 'verdict', '') or '').strip()
                or (_field(r, 'evidence', []) or [])
                or (_field(r, 'languages', []) or [])
                or (_field(r, 'read_quality', {}) or {}))


def _finding(e, counted):
    """One piece of evidence as a reader checking it against their own site needs it."""
    rung = int(_ev_recorded(e, 'sufficiency') or 0)
    mech = _ev_mech(e)
    return {
        'mechanism': mech,
        'mechanism_meaning': MECHANISM_MEANING.get(mech, ''),
        'url': _ev_url(e),
        # `_snip`, so the words a stranger reads in this document do not stop inside one
        'quote': _snip(' '.join(_ev_quote(e).split()), 0, QUOTE_CHARS),
        'language': _ev_lang(e),
        'authorship': _ev_recorded(e, 'authorship') or '',
        'sufficiency': rung,
        'sufficiency_name': SUFFICIENCY_NAMES.get(rung, ''),
        'server_html': bool(_ev_recorded(e, 'server_html')),
        'rules': sorted(set(_ev_recorded(e, 'rules') or ())),
        'counted': bool(counted),
    }


def _languages(x, evidence, counted_ids):
    """Every language this reading has anything to say about, with its findings under it.

    The two axes come from `by_language`, which the audit wrote. A language that appears in the
    evidence and not in `by_language` keeps its findings and reports the axes as unrecorded, rather
    than having them derived here, because deriving them would be this module reaching a reading of
    its own.
    """
    rows, order = {}, []
    for lg, axes in x['by_language'].items():
        rows[lg] = {'language': lg, 'counted': bool(axes['counted']),
                    'authorship': axes['authorship'],
                    'authorship_meaning': AUTHORSHIP_MEANING.get(axes['authorship'], ''),
                    'sufficiency': axes['sufficiency'],
                    'sufficiency_name': axes['sufficiency_name'],
                    'sufficiency_meaning': SUFFICIENCY_MEANING.get(axes['sufficiency'], ''),
                    'axes_recorded': True, 'findings': []}
        order.append(lg)

    seen = set()
    for e in evidence:
        if _ev_mech(e) == HAND_CODING:
            continue
        lg = _ev_lang(e) or NO_LANGUAGE
        if lg not in rows:
            rows[lg] = {'language': lg, 'counted': lg in x['languages'], 'authorship': '',
                        'authorship_meaning': '', 'sufficiency': 0, 'sufficiency_name': '',
                        'sufficiency_meaning': '', 'axes_recorded': False, 'findings': []}
            order.append(lg)
        f = _finding(e, id(e) in counted_ids)
        key = (lg, f['mechanism'], f['url'], f['quote'])
        if key in seen:
            continue
        seen.add(key)
        rows[lg]['findings'].append(f)

    # named languages first and alphabetically, with the marker bucket last, because a reader is
    # looking for a language and not for a plugin name
    named = sorted(lg for lg in order if lg != NO_LANGUAGE)
    return [rows[lg] for lg in named + [lg for lg in order if lg == NO_LANGUAGE]]


def _rules(x):
    """The rules that decided this reading, and the rules that read a finding it set aside."""
    out = []
    for status in (FIRED, FIRED_UNCOUNTED):
        numbers = x['rules'][status]
        if not numbers:
            continue
        out.append({'status': status, 'meaning': RULE_STATUS_MEANING[status],
                    'rules': [{'number': n, 'title': RULES[n].title, 'heading': RULES[n].heading}
                              for n in numbers if n in RULES]})
    return out


def _addresses(r, evidence):
    """The addresses this document can name, and an honest statement of which set they are.

    A capture written with `store=` holds every page the crawl read, and those are the addresses. A
    plain result row does not, and the only addresses on it are the ones its findings were read at,
    which are a subset of what was read and are reported as such. Nothing is inferred either way.
    """
    pages = _field(r, 'pages', {}) or {}
    if pages:
        return sorted(str(u) for u in pages), 'every page the crawl read'
    urls = sorted({_ev_url(e) for e in evidence if _ev_url(e)})
    if urls:
        return urls, ('the addresses the findings below were read at, which are some of the pages '
                      'the crawl read and not all of them')
    return [], 'the record does not name the addresses that were read'


def report(r):
    """One reading arranged as the document, as data.

    `r` is a Result from `audit` or `rejudge`, or the dict a stored run holds. `report_text` and
    `report_html` render this same dict, so the two forms cannot disagree about what the reading
    said. Raises `NothingToReport` for a record that never held a reading; see this module's
    docstring for why that is an error rather than an empty document.
    """
    if not _carries_a_reading(r):
        raise NothingToReport(
            'this record holds no reading, so no document was rendered. A reportable record needs '
            'an address and at least one of: a class, a piece of evidence, a language, or the '
            'record of the search (%r)' % (str(_field(r, 'url', '') or '') or 'no address',))

    x = explain(r)
    evidence = list(_field(r, 'evidence', []) or [])
    counted_ids = {id(e) for e in counted_evidence(evidence, x['machine_translation'])}
    languages = _languages(x, evidence, counted_ids)
    addresses, addresses_are = _addresses(r, evidence)
    q = x['read_quality'] or {}
    by_hand = hand_coding(r)

    doc = {
        'url': x['url'],
        'audited_at': x['audited_at'],
        'tool_version': x['tool_version'],
        'verdict': x['verdict'],
        'verdict_meaning': CLASS_MEANING.get(x['verdict'], ''),
        'note': x['note'],
        'authorship': x['authorship'],
        'authorship_meaning': AUTHORSHIP_MEANING.get(x['authorship'], ''),
        'sufficiency': x['sufficiency'],
        'sufficiency_name': x['sufficiency_name'],
        'sufficiency_meaning': SUFFICIENCY_MEANING.get(x['sufficiency'], ''),
        'machine_translation': x['machine_translation'],
        'counted_languages': list(x['languages']),
        'languages': languages,
        'switcher': x['switcher'],
        'rules': _rules(x),
        'findings_total': sum(len(row['findings']) for row in languages),
        'findings_counted': sum(1 for row in languages for f in row['findings'] if f['counted']),
        'reading': {
            'pages_read': int(q.get('pages_read', x['pages_read']) or 0),
            'unread': int(q.get('unread', 0) or 0),
            'unread_locale_links': int(q.get('unread_locale_links', 0) or 0),
            'stopped_by': _stopped_by(q, pages_stated=True),
            'sufficient': bool(q.get('sufficient')),
            'escalated': bool(q.get('escalated')),
            'recorded': bool(q),
            'addresses': addresses,
            'addresses_are': addresses_are,
            'absence_claim': x['absence_claim'],
        },
        # only ever non-empty on a re-judged capture, and the first thing a reader of one has to see
        'unreproducible': x['unreproducible'],
        # a reading a person settled wins over the machine's, and a document that did not say so
        # would be presenting a hand coding as an instrument reading
        'hand_coded': None if by_hand is None else {
            'machine_verdict': str(_ev_recorded(by_hand, 'machine_verdict') or ''),
            'coder': str(_ev_recorded(by_hand, 'coder') or ''),
            'coded_at': str(_ev_recorded(by_hand, 'coded_at') or ''),
            'note': _ev_quote(by_hand),
        },
        # '' where the package settled the reading; otherwise the sentence `review` puts in front of
        # a coder, which is the sentence a reader of this document needs for the same reason
        'unsettled_kind': unsettled_kind(r),
        'unsettled_reason': unsettled_reason(r),
        'limits': [{'heading': h, 'statement': s} for h, s in LIMITS],
    }
    doc['sections'] = _sections(doc)
    return doc


# The sections a rendered document holds, in order. Computed rather than written into each renderer,
# so that the count a caller can assert on and the document a reader gets cannot come apart.
def _sections(doc):
    out = ['classification']
    if doc['hand_coded']:
        out.append('hand coding')
    if doc['unsettled_reason']:
        out.append('the unsettled part of this reading')
    if doc['languages']:
        out.append('languages')
    if doc['findings_total']:
        out.append('evidence')
    if doc['rules']:
        out.append('rules')
    if doc['unreproducible']:
        out.append('a re-judged capture')
    out.append('the search behind this reading')
    out.append('limits')
    return out


# ------------------------------------------------------------------------------- the plain form
def _wrap(text, indent='  '):
    return textwrap.wrap(text, width=TEXT_WIDTH, initial_indent=indent, subsequent_indent=indent)


def _heading(title):
    return ['', title, '-' * len(title)]


def report_text(r):
    """The document as lines a person reads. `r` is a reading, or the dict `report` returned."""
    d = r if (isinstance(r, dict) and 'sections' in r) else report(r)
    out = ['langaccess reading', d['url']]
    add = out.append
    add('read %s by langaccess %s'
        % (d['audited_at'] or 'at an unrecorded time', d['tool_version'] or 'of an unrecorded version'))

    out.extend(_heading('Classification'))
    add('  %s' % d['verdict'])
    out.extend(_wrap(d['verdict_meaning'] or 'no class this package defines was recorded.'))
    if d['note']:
        out.extend(_wrap('The reading recorded: %s' % d['note']))
    if d['machine_translation']:
        out.extend(_wrap('Translation widget on the site: %s' % d['machine_translation']))
    out.extend(_wrap('Authorship over the site: %s, meaning %s.'
                     % (d['authorship'], d['authorship_meaning'] or 'unrecorded')))
    out.extend(_wrap('Extent over the site: %s, meaning %s.'
                     % (d['sufficiency_name'], d['sufficiency_meaning'] or 'unrecorded')))
    out.extend(_wrap('Languages the classification counted: %s'
                     % (', '.join(d['counted_languages']) or 'none')))
    if d['switcher']['languages']:
        more = (' The tool has no name for %d further entries.' % d['switcher']['unresolved']
                if d['switcher']['unresolved'] else '')
        out.extend(_wrap("The site's language menu offers %d: %s.%s"
                         % (len(d['switcher']['languages']),
                            ', '.join(d['switcher']['languages']), more)))

    if d['hand_coded']:
        h = d['hand_coded']
        out.extend(_heading('Hand coding'))
        out.extend(_wrap('A person settled this reading. The class above is theirs; this package '
                         'had reached %s.' % (h['machine_verdict'] or 'no class')))
        if h['coder'] or h['coded_at']:
            out.extend(_wrap('Coded by %s%s.' % (h['coder'] or 'an unnamed coder',
                                                 ' on %s' % h['coded_at'] if h['coded_at'] else '')))
        if h['note']:
            out.extend(_wrap('Their note: %s' % h['note']))

    if d['unsettled_reason']:
        out.extend(_heading('The unsettled part of this reading'))
        out.extend(_wrap(d['unsettled_reason']))

    if d['languages']:
        out.extend(_heading('Languages'))
        for row in d['languages']:
            add('  %s%s' % (row['language'], '' if row['counted'] else '   (not counted)'))
            if row['axes_recorded']:
                out.extend(_wrap('%s: %s.' % (row['authorship'], row['authorship_meaning']),
                                 indent='      '))
                out.extend(_wrap('%s: %s.' % (row['sufficiency_name'], row['sufficiency_meaning']),
                                 indent='      '))
            out.extend(_wrap(_under(row), indent='      '))

    if d['findings_total']:
        out.extend(_heading('Evidence'))
        out.extend(_wrap('Every quotation below was read at the address printed above it, so a '
                         'reader can open that address and look. %s on the record, of which %d '
                         'counted toward the classification.'
                         % (_findings(d['findings_total']), d['findings_counted'])))
        for row in d['languages']:
            if not row['findings']:
                continue
            add('')
            add('  %s' % row['language'])
            for f in row['findings']:
                add('    %s%s' % (f['url'], '' if f['counted'] else '   (not counted)'))
                add('    %s' % (f['mechanism_meaning'] or f['mechanism']))
                if f['quote']:
                    out.extend(_wrap('"%s"' % f['quote'], indent='      '))

    if d['rules']:
        out.extend(_heading('Rules'))
        for block in d['rules']:
            out.extend(_wrap('%s:' % block['meaning']))
            for rule in block['rules']:
                # the heading carries the number, so the number is not printed twice
                out.extend(_wrap(rule['heading'], indent='      '))

    if d['unreproducible']:
        out.extend(_heading('A re-judged capture'))
        out.extend(_wrap('This reading was taken again over pages stored earlier, with no site '
                         'read. These steps of a live reading were not carried:'))
        for lim in d['unreproducible']:
            add('    %s' % lim['code'])
            out.extend(_wrap(lim['statement'], indent='      '))

    q = d['reading']
    out.extend(_heading('The search behind this reading'))
    out.extend(_wrap('Pages read: %d. Addresses found and not read: %d, of which %d were in the '
                     'set of addresses the site publishes for its other languages.'
                     % (q['pages_read'], q['unread'], q['unread_locale_links'])))
    # on its own line and not after a colon, because `_stopped_by` can itself begin with one
    add('  what ended the search')
    out.extend(_wrap(q['stopped_by'], indent='      '))
    out.extend(_wrap('This package %s call the search enough to rest a claim of absence on.'
                     % ('does' if q['sufficient'] else 'does NOT')))
    if q['absence_claim']:
        out.extend(_wrap('The class above IS a claim of absence. No text in another language was '
                         'found on the addresses below, and the claim covers those addresses and '
                         'no others.'))
    elif d['verdict'] == 'unreachable':
        # neither an absence claim nor a finding: nothing was read, and the sentence written
        # for the other classes said this one rests on something that was found
        out.extend(_wrap('The class above is not a claim about the site at all. Nothing was '
                         'read, so nothing is established about the languages it does or '
                         'does not publish, and the line above says how far the attempt got.'))
    else:
        out.extend(_wrap('The class above is not a claim of absence: it rests on something that '
                         'was found. The line above therefore says how much of the site the '
                         'reading saw, and it is not a doubt about the class.'))
    out.extend(_wrap('%s:' % q['addresses_are']))
    for u in q['addresses']:
        add('    %s' % u)
    if not q['addresses']:
        add('    none')

    out.extend(_heading('Limits'))
    for lim in d['limits']:
        add('  %s' % lim['heading'])
        out.extend(_wrap(lim['statement'], indent='      '))
    return '\n'.join(out)


# ------------------------------------------------------------------------------- the HTML form
#
# One file, no request to anywhere. A document handed to an organization is opened from an email
# attachment, from a shared drive and from a machine with no network, and a stylesheet or a font
# fetched from somewhere else turns it into a page that is sometimes readable. The type stack is
# whatever the reader's machine already has.
_CSS = """
:root { color-scheme: light; }
body { margin: 0; background: #ffffff; color: #16181d;
       font-family: "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
       font-size: 16px; line-height: 1.55; }
main { max-width: 44rem; margin: 0 auto; padding: 3rem 1.25rem 5rem; }
h1 { font-size: 1.5rem; font-weight: 700; letter-spacing: -0.01em; margin: 0 0 0.25rem; }
h2 { font-size: 1.05rem; font-weight: 700; letter-spacing: -0.01em;
     margin: 2.75rem 0 0.75rem; padding-bottom: 0.35rem; border-bottom: 1px solid #16181d; }
h3 { font-size: 0.95rem; font-weight: 700; margin: 1.5rem 0 0.35rem; }
p { margin: 0 0 0.75rem; }
a { color: #16181d; }
.addr { font-size: 1rem; word-break: break-all; }
.meta { color: #5a6069; font-size: 0.85rem; margin-bottom: 0.5rem; }
.verdict { font-size: 1.25rem; font-weight: 700; margin: 0 0 0.5rem; }
dl { margin: 0 0 0.75rem; }
dt { font-weight: 700; margin-top: 0.5rem; }
dd { margin: 0; }
.finding { border-left: 1px solid #c9ccd1; padding: 0 0 0 0.9rem; margin: 0 0 1.1rem; }
.finding .at { font-size: 0.85rem; word-break: break-all; }
.finding .kind { color: #5a6069; font-size: 0.85rem; }
blockquote { margin: 0.35rem 0 0; padding: 0; font-size: 1rem; }
.uncounted { color: #5a6069; font-size: 0.85rem; }
ul { margin: 0 0 0.75rem; padding-left: 1.1rem; }
li { margin-bottom: 0.2rem; }
.addresses { font-size: 0.85rem; word-break: break-all; }
.limits { margin-top: 3rem; border-top: 1px solid #16181d; padding-top: 0.5rem; }
@media print { body { font-size: 11pt; } main { padding: 0; max-width: none; } }
"""


def _e(s):
    return html.escape(str(s or ''), quote=True)


def _href(u):
    """An escaped href only for a scheme a browser should follow from this document; anything
    else (javascript:, data:) is rendered as inert text, so a crafted stored url cannot become a
    clickable vector even though every real crawl url is http(s)."""
    s = str(u or '')
    scheme = s.split(':', 1)[0].lower() if ':' in s else ''
    return _e(s) if scheme in ('http', 'https', 'mailto') else ''


def _p(text):
    return '<p>%s</p>' % _e(text)


def report_html(r):
    """The document as one HTML file that needs nothing else to render.

    `r` is a reading, or the dict `report` returned. No stylesheet, script, font or image is
    fetched from anywhere: the file opens the same from an attachment, a shared drive and a machine
    with no network.
    """
    d = r if (isinstance(r, dict) and 'sections' in r) else report(r)
    o = ['<!doctype html>', '<html lang="en">', '<head>', '<meta charset="utf-8">',
         '<meta name="viewport" content="width=device-width, initial-scale=1">',
         '<title>langaccess reading: %s</title>' % _e(d['url']),
         '<style>%s</style>' % _CSS, '</head>', '<body>', '<main>']
    add = o.append

    add('<h1>Language access reading</h1>')
    _u = _href(d['url'])
    add('<p class="addr"><a href="%s">%s</a></p>' % (_u, _e(d['url'])) if _u
        else '<p class="addr">%s</p>' % _e(d['url']))
    add('<p class="meta">Read %s by langaccess %s</p>'
        % (_e(d['audited_at'] or 'at an unrecorded time'),
           _e(d['tool_version'] or 'of an unrecorded version')))

    add('<h2>Classification</h2>')
    add('<p class="verdict">%s</p>' % _e(d['verdict']))
    add(_p(d['verdict_meaning'] or 'No class this package defines was recorded.'))
    if d['note']:
        add(_p('The reading recorded: %s' % d['note']))
    add('<dl>')
    if d['machine_translation']:
        add('<dt>Translation widget on the site</dt><dd>%s</dd>' % _e(d['machine_translation']))
    add('<dt>Authorship over the site</dt><dd>%s, meaning %s.</dd>'
        % (_e(d['authorship']), _e(d['authorship_meaning'] or 'unrecorded')))
    add('<dt>Extent over the site</dt><dd>%s, meaning %s.</dd>'
        % (_e(d['sufficiency_name']), _e(d['sufficiency_meaning'] or 'unrecorded')))
    add('<dt>Languages the classification counted</dt><dd>%s</dd>'
        % _e(', '.join(d['counted_languages']) or 'none'))
    if d['switcher']['languages']:
        more = (' The tool has no name for %d further entries.' % d['switcher']['unresolved']
                if d['switcher']['unresolved'] else '')
        add('<dt>The language menu on the site</dt><dd>%s offered: %s.%s</dd>'
            % (len(d['switcher']['languages']), _e(', '.join(d['switcher']['languages'])),
               _e(more)))
    add('</dl>')

    if d['hand_coded']:
        h = d['hand_coded']
        add('<h2>Hand coding</h2>')
        add(_p('A person settled this reading. The class above is theirs; this package had '
               'reached %s.' % (h['machine_verdict'] or 'no class')))
        if h['coder'] or h['coded_at']:
            add(_p('Coded by %s%s.' % (h['coder'] or 'an unnamed coder',
                                       ' on %s' % h['coded_at'] if h['coded_at'] else '')))
        if h['note']:
            add(_p('Their note: %s' % h['note']))

    if d['unsettled_reason']:
        add('<h2>The unsettled part of this reading</h2>')
        add(_p(d['unsettled_reason']))

    if d['languages']:
        add('<h2>Languages</h2>')
        for row in d['languages']:
            add('<h3>%s%s</h3>' % (_e(row['language']),
                                   '' if row['counted']
                                   else ' <span class="uncounted">(not counted)</span>'))
            if row['axes_recorded']:
                add('<dl>')
                add('<dt>%s</dt><dd>%s.</dd>' % (_e(row['authorship']),
                                                 _e(row['authorship_meaning'])))
                add('<dt>%s</dt><dd>%s.</dd>' % (_e(row['sufficiency_name']),
                                                 _e(row['sufficiency_meaning'])))
                add('</dl>')
            add(_p(_under(row)))

    if d['findings_total']:
        add('<h2>Evidence</h2>')
        add(_p('Every quotation below was read at the address printed above it, so a reader can '
               'open that address and look. %s on the record, of which %d counted toward the '
               'classification.' % (_findings(d['findings_total']), d['findings_counted'])))
        for row in d['languages']:
            if not row['findings']:
                continue
            add('<h3>%s</h3>' % _e(row['language']))
            for f in row['findings']:
                add('<div class="finding">')
                _uf = _href(f['url'])
                _flag = '' if f['counted'] else ' <span class="uncounted">(not counted)</span>'
                if _uf:
                    add('<p class="at"><a href="%s">%s</a>%s</p>' % (_uf, _e(f['url']), _flag))
                else:
                    add('<p class="at">%s%s</p>' % (_e(f['url']), _flag))
                add('<p class="kind">%s</p>' % _e(f['mechanism_meaning'] or f['mechanism']))
                if f['quote']:
                    # dir="auto" so a quotation in Arabic, Hebrew or Urdu reads in its own direction
                    add('<blockquote dir="auto">%s</blockquote>' % _e(f['quote']))
                add('</div>')

    if d['rules']:
        add('<h2>Rules</h2>')
        for block in d['rules']:
            add(_p('%s:' % block['meaning']))
            add('<ul>')
            for rule in block['rules']:
                # the heading carries the number, so the number is not printed twice
                add('<li>%s</li>' % _e(rule['heading']))
            add('</ul>')

    if d['unreproducible']:
        add('<h2>A re-judged capture</h2>')
        add(_p('This reading was taken again over pages stored earlier, with no site read. These '
               'steps of a live reading were not carried:'))
        for lim in d['unreproducible']:
            add('<h3>%s</h3>' % _e(lim['code']))
            add(_p(lim['statement']))

    q = d['reading']
    add('<h2>The search behind this reading</h2>')
    add(_p('Pages read: %d. Addresses found and not read: %d, of which %d were in the set of '
           'addresses the site publishes for its other languages.'
           % (q['pages_read'], q['unread'], q['unread_locale_links'])))
    # in a list and not after a colon, because `_stopped_by` can itself begin with one
    add('<dl><dt>What ended the search</dt><dd>%s</dd></dl>' % _e(q['stopped_by']))
    add(_p('This package %s call the search enough to rest a claim of absence on.'
           % ('does' if q['sufficient'] else 'does NOT')))
    if q['absence_claim']:
        add(_p('The class above IS a claim of absence. No text in another language was found on '
               'the addresses below, and the claim covers those addresses and no others.'))
    elif d['verdict'] == 'unreachable':
        add(_p('The class above is not a claim about the site at all. Nothing was read, so '
               'nothing is established about the languages it does or does not publish, and '
               'the line above says how far the attempt got.'))
    else:
        add(_p('The class above is not a claim of absence: it rests on something that was found. '
               'The line above therefore says how much of the site the reading saw, and it is not '
               'a doubt about the class.'))
    add(_p('%s:' % q['addresses_are']))
    add('<ul class="addresses">')
    for u in q['addresses']:
        _ul = _href(u)
        add('<li><a href="%s">%s</a></li>' % (_ul, _e(u)) if _ul
            else '<li>%s</li>' % _e(u))
    if not q['addresses']:
        add('<li>none</li>')
    add('</ul>')

    add('<section class="limits">')
    add('<h2>Limits</h2>')
    for lim in d['limits']:
        add('<h3>%s</h3>' % _e(lim['heading']))
        add(_p(lim['statement']))
    add('</section>')

    o.extend(['</main>', '</body>', '</html>'])
    return '\n'.join(o)


HTML_SUFFIXES = ('.html', '.htm')


def render(r, form='text'):
    """The document in one of the two forms. `form` is `html` or `text`."""
    if form not in ('html', 'text'):
        raise ValueError('form is html or text, not %r' % (form,))
    return report_html(r) if form == 'html' else report_text(r)


def form_for(path, form=''):
    """Which form a path asks for: what `form` says, or the file's own extension."""
    if form:
        return form
    return 'html' if str(path).lower().endswith(HTML_SUFFIXES) else 'text'


def write_report(r, path, form=''):
    """Write one document and return how many characters it holds.

    The form is `form` where it is given, and otherwise the one the path's extension asks for. A
    document that rendered to nothing raises rather than leaving an empty file on disk.
    """
    text = render(r, form_for(path, form))
    if not text.strip():
        raise NothingToReport('the document rendered to nothing, so %s was not written' % path)
    with open(path, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(text)
    return len(text)
