# -*- coding: utf-8 -*-
"""Why one site was classified as it was, out of what the reading already recorded.

    from langaccess import audit, explain_text
    print(explain_text(audit('https://example.org')))

Nothing here judges anything. Every number, every quote and every axis below was written by the
audit that produced the Result, and this module arranges them so that a person disagreeing with a
verdict has the working in front of them instead of the conclusion. `explain` returns the same
arrangement as a dict, for a caller that wants it as data.

WHAT A READER OF AN EXPLANATION GETS. The rules that fired, in the order the package applies them;
the evidence each one rests on, with the address it was read at and the words that decided it; the
two axes per language; and what the search behind the reading was worth, which is what an
`english_only` verdict rests on entirely, since that verdict is the one that asserts an absence.

THE FIVE THINGS A RULE NUMBER CAN MEAN HERE, and the reason the distinction is drawn. A rule
absent from `Result.rules` has not been shown not to apply. `verdict_rules` reports what FIRED, and
a reader who takes silence for a negative finding will read "rule 17 is not listed" as "this site
does not mirror its front door", which the record does not say. So a rule number lands in one of
five places:

  fired                the number is on `Result.rules`, so it decided the class
  fired on a finding   the number is on a piece of evidence that `counted_evidence` did not count,
                       so the gate ran and the finding it passed did not reach the verdict
  tested, did not fire `verdict_rules` tests this rule on every call it makes, on the branch this
                       reading took, and it is not on the result. See TESTED_ALWAYS below
  not in code          the rule's own record says nothing in this package can apply it, and
                       never a property of this reading. No rule says this today; the bucket
                       stays because the field does, and a rule may earn it again
  not recorded         everything else. The reading says nothing about whether the rule was reached

The third bucket is the one worth having and it is deliberately small: it holds only the rules
`verdict_rules` asks about unconditionally, which is a fact about that function and is pinned by a
test rather than asserted here. Nothing in this module infers a rule did not fire from the shape of
a site, because that would be this package inventing a counterfactual out of a record that does not
hold one.
"""
import collections
import textwrap

from .core import (ARCHIVE_PATH, RULES, SUFFICIENCY_NAMES, REJUDGE_LIMITS, _STORED_ALIAS, _snip,
                   counted_evidence,
                   failure_kind, _ev_lang, _ev_mech, _ev_quote, _ev_recorded, _ev_url)


# The order the package applies its rules, as stages, because the order is the one thing a set of
# numbers cannot carry. `Result.rules` is sorted numerically by `verdict_rules`, and the numbering
# is not application order: rule 2 answers before a page is read and rule 14 answers after
# everything is. Each stage names where in the pipeline its rules are applied, so the sequence below
# is `_audit_async`'s own sequence and not a narrative laid over it.
#
# Within a stage there is no order. The record does not preserve one, and inventing one would be the
# same fault as inventing a rule that did not fire.
# Printed with every explanation, because a verdict gets pasted into a spreadsheet, a slide or a
# complaint, and the documentation is not there when it does. An organization recorded here as
# `english_only` may serve people in six languages by phone or at an intake desk, and a crawler sees
# none of that. `report.LIMITS` says the same thing at more length for the document handed to an
# organization.
SCOPE = ('Read by machine from the website on the date above. This is not a finding of compliance '
         'with any law or regulation. It does not show whether anyone can get help in a language, '
         'which depends on staff, phone lines and interpreters that are not on the website.')

# Five labels, and none of them carries an article: three of the five did until 2026-08-11, which
# made a printed list where two names read as labels and three read as sentence fragments. `site
# class` also pairs with `site identity`, which is the other stage where the rules answer about the
# site rather than about a page or a passage.
STAGES = (
    # answered before or at the home read: SOCIAL_HOST and `is_parked`. `_directory_profile`
    # answers here too and carries no number since the directory rule (5 of the development
    # numbering) left the published set, so its stop is
    # on the note and not in this listing.
    ('site identity', (1, 2)),
    # what the crawl queued and how far out it went: the document extensions, the depth, the sitemap
    ('pages in the reading', (3, 4, 5)),
    # the detection gates, applied as a page's text becomes a language finding
    ('text against label', (6, 7, 8, 9)),
    # what a finding is worth to the verdict, which is the set `verdict_rules` asks on every call:
    # `language_coverage` against PAGE_COVERAGE, which is what set the rung, and then
    # `counted_evidence`, which drops the archive address, holds true_multilingual to a named
    # language, and takes a plugin marker only alongside content
    ('evidence and its rung', (10, 11, 12, 13)),
    # `verdict_for` and `class_for`, where the site-level rules answer
    ('site class', (14, 15, 16, 17)),
)

# Which rules `verdict_rules` asks about on EVERY call, so their absence from a result is a negative
# finding and not silence. Rule 12 is in the first tuple and always fires, which is why it is never
# reported as tested and not fired; it is here because the honest statement is about what the
# function asks, not about what it happens to answer.
TESTED_ALWAYS = (10, 11, 12, 13)
# The two branches of that function. A widget was named, so rules 14, 15 and 16 were reached
# and rule 17 was not; or none was, and the other way round.
TESTED_WITH_WIDGET = (14, 15, 16)
TESTED_WITHOUT_WIDGET = (17,)
# A site turned away before any of that: `_audit_async` writes the rule number and returns, so
# `verdict_rules` never ran and nothing below it was tested at all.
SITE_LEVEL_STOP = (1, 2)

FIRED = 'fired'
FIRED_UNCOUNTED = 'fired_on_uncounted_evidence'
TESTED_NOT_FIRED = 'tested_not_fired'
NOT_IN_CODE = 'not_in_code'
NOT_RECORDED = 'not_recorded'

# How many pieces of evidence one rule prints before the rest are left to the JSON form. Four,
# because the detection gates are on every finding a site produced and a site with thirty findings
# would print thirty of them under each of rules 6, 8, 10 and 9.
EVIDENCE_SHOWN = 4


def _field(r, name, default=None):
    """One field of a Result, or of the dict a stored JSON line holds.

    A caller has a Result from `audit` or `rejudge`, and a census has the dict it wrote to a file
    years ago. Both are explained, through this, for the same reason `_ev_mech` exists in core.
    """
    if isinstance(r, dict):
        got = r.get(name, default)
        if got is default and name in _STORED_ALIAS:
            # a capture written under the field's old name is read forever, the same promise
            # core._STORED_ALIAS keeps for evidence-level reads (e.g. authorship<-provenance)
            for old in _STORED_ALIAS[name]:
                if old in r:
                    got = r[old]
                    break
    else:
        got = getattr(r, name, default)
    return default if got is None else got


def rules_tested(r):
    """The rule numbers this reading is known to have been asked, whatever the answer was.

    Read off `verdict_rules`, which is the function that wrote `Result.rules`: it tests
    TESTED_ALWAYS unconditionally and then takes one of two branches on whether a translation vendor
    was named. A site stopped before a reading never reached it, and the empty set that returns is
    the accurate answer for such a site rather than a convenient one.

    `failure_kind` is what answers whether a reading happened, and the rule numbers are a second
    check behind it. The numbers alone stopped answering on 2026-08-08, when the directory-profile
    stop kept its behaviour and lost its number: a result with no numbers on it read here as a site
    that had been through `verdict_rules` and fired nothing, so the explanation reported rules 11,
    12, 17, 10 and 13 as tested on a site no browser had opened.
    """
    if failure_kind(r):
        return set()
    fired = set(_field(r, 'rules', []) or [])
    if fired & set(SITE_LEVEL_STOP):
        return set()
    out = set(TESTED_ALWAYS)
    out |= set(TESTED_WITH_WIDGET if _field(r, 'machine_translation', '')
               else TESTED_WITHOUT_WIDGET)
    return out


def _evidence_view(e, counted):
    """One piece of evidence as a reader needs it: where it was read and what it said."""
    return {
        'mechanism': _ev_mech(e),
        'url': _ev_url(e),
        'language': _ev_lang(e),
        'quote': _ev_quote(e),
        'authorship': _ev_recorded(e, 'authorship') or '',
        'sufficiency': int(_ev_recorded(e, 'sufficiency') or 0),
        'counted': bool(counted),
    }


def _evidence_for_rule(n, evidence, counted_ids, event_aside_ids=frozenset()):
    """The evidence that carries this rule number, plus the one join a number cannot carry itself.

    Rule 13 is recorded on the RESULT and on no piece of evidence, because it is the rule that
    throws evidence away: `counted_evidence` drops an archive address and `verdict_rules` notes the
    number. The address it dropped is the evidence a reader of rule 13 wants, so it is joined here
    on ARCHIVE_PATH, which is the same expression both of those functions test.

    `event_aside_ids` is the same join for rule 13's event-page half, which shares the number:
    a dated event page set aside because it was a language's sole page-rung carrier is shown
    under 13 beside the archive addresses, with `counted` False saying it did not reach the
    verdict.
    """
    out = []
    for e in evidence:
        on_evidence = n in set(_ev_recorded(e, 'rules') or ())
        archive = n == 13 and _ev_lang(e) and ARCHIVE_PATH.search(_ev_url(e))
        event = n == 13 and id(e) in event_aside_ids
        if on_evidence or archive or event:
            out.append(_evidence_view(e, id(e) in counted_ids))
    return out


def explain(r):
    """The working behind one classification, as data.

    `r` is a Result from `audit` or `rejudge`, or the dict a stored run holds. Nothing is computed
    that the reading did not already record, with one exception that is a lookup and not a
    judgement: `counted_evidence` is called to say which pieces of evidence the verdict counted,
    which is the same call `verdict_for` made when it produced the verdict being explained.
    """
    evidence = list(_field(r, 'evidence', []) or [])
    widget = _field(r, 'machine_translation', '')
    event_aside = []
    counted_ids = {id(e) for e in counted_evidence(evidence, widget,
                                                   event_set_aside=event_aside)}
    event_aside_ids = {id(e) for e in event_aside}

    fired = set(_field(r, 'rules', []) or [])
    on_evidence = set()
    for e in evidence:
        on_evidence |= set(_ev_recorded(e, 'rules') or ())
    tested = rules_tested(r)

    def status(n):
        if n in fired:
            return FIRED
        if n in on_evidence:
            return FIRED_UNCOUNTED
        if RULES[n].not_in_code.strip():
            return NOT_IN_CODE
        if n in tested:
            return TESTED_NOT_FIRED
        return NOT_RECORDED

    stages, by_status = [], collections.defaultdict(list)
    for name, numbers in STAGES:
        rows = []
        for n in numbers:
            rule = RULES[n]
            st = status(n)
            by_status[st].append(n)
            rows.append({'number': n, 'title': rule.title, 'heading': rule.heading, 'status': st,
                         'evidence': _evidence_for_rule(n, evidence, counted_ids,
                                                        event_aside_ids)})
        stages.append({'stage': name, 'rules': rows})

    suff = int(_field(r, 'sufficiency', 0) or 0)
    languages = {}
    for lg, row in sorted((_field(r, 'by_language', {}) or {}).items()):
        rung = int(row.get('sufficiency', 0) or 0)
        languages[lg] = {'authorship': row.get('authorship', ''), 'sufficiency': rung,
                         'sufficiency_name': SUFFICIENCY_NAMES.get(rung, '?'),
                         'counted': lg in (_field(r, 'languages', []) or [])}

    return {
        'url': _field(r, 'url', ''),
        'verdict': _field(r, 'verdict', ''),
        'note': _field(r, 'note', ''),
        'audited_at': _field(r, 'audited_at', ''),
        'tool_version': _field(r, 'tool_version', ''),
        'authorship': _field(r, 'authorship', ''),
        'sufficiency': suff,
        'sufficiency_name': SUFFICIENCY_NAMES.get(suff, '?'),
        'languages': list(_field(r, 'languages', []) or []),
        'by_language': languages,
        'machine_translation': widget,
        'switcher': {'languages': list(_field(r, 'switcher_languages', []) or []),
                     'unresolved': int(_field(r, 'switcher_unresolved', 0) or 0)},
        'pages_read': int(_field(r, 'pages_read', 0) or 0),
        'read_quality': dict(_field(r, 'read_quality', {}) or {}),
        # `english_only` is the one class that asserts an ABSENCE, and an absence claim
        # is worth what the search behind it was worth. Flagged rather than left for a reader to
        # remember.
        'absence_claim': _field(r, 'verdict', '') == 'english_only',
        'stages': stages,
        'rules': {FIRED: sorted(by_status[FIRED]),
                  FIRED_UNCOUNTED: sorted(by_status[FIRED_UNCOUNTED]),
                  TESTED_NOT_FIRED: sorted(by_status[TESTED_NOT_FIRED]),
                  NOT_IN_CODE: sorted(by_status[NOT_IN_CODE]),
                  NOT_RECORDED: sorted(by_status[NOT_RECORDED])},
        # only ever non-empty on a re-judged capture, where it is the first thing a reader has to
        # see, so the statement of each limit travels with the code rather than the code alone
        'unreproducible': [{'code': c, 'statement': REJUDGE_LIMITS.get(c, '')}
                           for c in (_field(r, 'unreproducible', []) or [])],
    }


# The five statuses in the width the rule table prints them at. The words are the short form of the
# five paragraphs at the top of this file, and `unrecorded` is deliberately not the word `no`.
_SHORT_STATUS = {FIRED: 'fired', FIRED_UNCOUNTED: 'uncounted', TESTED_NOT_FIRED: 'not fired',
                 NOT_IN_CODE: 'not in code', NOT_RECORDED: 'unrecorded'}


def explain_text(r, quote=90):
    """The same working as lines a person reads. `quote` caps how much of a quotation is printed."""
    x = r if (isinstance(r, dict) and 'stages' in r) else explain(r)
    out = [x['url']]
    add = out.append
    add('  verdict   %s%s' % (x['verdict'], '  (%s)' % x['note'] if x['note'] else ''))
    add('  axes      authorship %s   sufficiency %d %s'
        % (x['authorship'], x['sufficiency'], x['sufficiency_name']))
    if x['machine_translation']:
        add('  widget    %s' % x['machine_translation'])
    if x['audited_at'] or x['tool_version']:
        add('  read at   %s by langaccess %s' % (x['audited_at'] or '?', x['tool_version'] or '?'))

    add('')
    add('  rules, in the order this package applies them')
    for stage in x['stages']:
        add('    %s' % stage['stage'])
        for row in stage['rules']:
            add('      %-2d %-11s %s'
                % (row['number'], _SHORT_STATUS[row['status']], row['title']))
            for e in row['evidence'][:EVIDENCE_SHOWN]:
                add('           %s%s' % (e['url'], '' if e['counted'] else '   (not counted)'))
                if e['quote']:
                    q = e['quote']
                    # `_snip` and not a bare slice: a fixed width opens or closes inside a word,
                    # which is the same defect the stored quote itself carried until 2026-08-10.
                    shown = _snip(q, 0, quote) + ('...' if len(q) > quote else '')
                    add('           %s  %r' % (e['language'] or '-', shown))
            if len(row['evidence']) > EVIDENCE_SHOWN:
                add('           and %d more, all of them in the JSON form'
                    % (len(row['evidence']) - EVIDENCE_SHOWN))
    add('')
    add('  "not fired" is the one negative finding here, and it covers the rules verdict_rules '
        'asks on every')
    add('  call. "unrecorded" means the reading says nothing either way about that rule.')

    add('')
    add('  languages the verdict counted   %s' % (', '.join(x['languages']) or '-'))
    for lg, row in x['by_language'].items():
        add('    %-16s %-14s %d %s%s' % (lg, row['authorship'], row['sufficiency'],
                                         row['sufficiency_name'],
                                         '' if row['counted'] else '   (not counted)'))
    # printed whenever the page has a menu at all, including one whose entries this package cannot
    # name: silence there reads as a site with no switcher, which is a different fact
    if x['switcher']['languages'] or x['switcher']['unresolved']:
        more = ('  (+%d this tool cannot name)' % x['switcher']['unresolved']
                if x['switcher']['unresolved'] else '')
        if x['switcher']['languages']:
            add('  switcher offers %d%s' % (len(x['switcher']['languages']), more))
        else:
            add('  switcher offers %d, none of which this tool can name'
                % x['switcher']['unresolved'])

    q = x['read_quality'] or {}
    add('')
    # printed for every class, and said twice as loudly for the one that asserts an absence
    add('  the search behind this reading')
    add('    pages read %d, unread %d, locale addresses found and unread %d'
        % (q.get('pages_read', x['pages_read']), q.get('unread', 0),
           q.get('unread_locale_links', 0)))
    why = [k for k in ('shallow', 'clock_exhausted', 'budget_exhausted') if q.get(k)]
    if q.get('reads_timed_out'):
        why.append('%d reads timed out' % q['reads_timed_out'])
    if q.get('escalated'):
        why.append('escalated')
    add('    %s%s' % ('enough to rest an absence claim on' if q.get('sufficient')
                      else 'NOT enough to rest an absence claim on',
                      '  (%s)' % ', '.join(why) if why else ''))
    if x['absence_claim']:
        add('    this verdict IS an absence claim: no non-English text was found on the routes '
            'above, and the claim is bounded by them')

    if x['unreproducible']:
        add('')
        add('  a re-judged capture, so these steps of a live audit were not carried')
        for lim in x['unreproducible']:
            add('    %s' % lim['code'])
            # wrapped, because each of these is a paragraph and a terminal is not a document viewer
            out.extend(textwrap.wrap(lim['statement'], width=96, initial_indent='      ',
                                     subsequent_indent='      '))

    # The scope, printed with the working rather than left in a file. A verdict travels: it is
    # quoted in a spreadsheet, a slide, a complaint, and by then nobody has README beside it. The
    # two sentences that stop a reading being read as a finding therefore go where the reading is.
    add('')
    for line in textwrap.wrap(SCOPE, width=96, initial_indent='  ', subsequent_indent='  '):
        add(line)
    return '\n'.join(out)
