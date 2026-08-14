# -*- coding: utf-8 -*-
"""langaccess audits the language accessibility of a website. Given a URL, the tool renders the
site in a headless browser and classifies, per language, the access provided: English only,
machine translation, or the site's own text.

    from langaccess import audit
    r = audit('https://example.org')
    r.verdict      # english_only | machine_translate | machine_translate_error
                   #  | true_multilingual | unreachable
    r.languages    # ['Chinese', 'English', 'Spanish']
    r.evidence     # [Evidence(mechanism=..., url=..., quote=...), ...]
    r.authorship   # authored | server_plugin | client_widget | unknown_widget | none
    r.sufficiency  # 0 none, 1 token, 2 notice, 3 page, 4 section     -- what a reader can do with it
    r.by_language  # {'Spanish': {'authorship': 'authored', 'sufficiency': 3}, ...}
    r.read_quality # how much reading the verdict rests on, and whether that is enough for an
                   # ABSENCE claim: english_only is the only verdict that asserts one

The verdict is derived from those two axes alone, by `class_for`, so a boundary argument about a
site is an argument about a threshold on a recorded scale.

There are five verdicts because two would not suffice. A site with a translation widget provides an
offering different from a site whose own staff wrote a Spanish page, and the two are reported
separately; a site that could not be read at all is recorded as a read outcome, since nothing is
established about its access. Every mechanism the judgement rests on is returned with the URL at
which it was observed and the words that decided it, so any classification can be verified without
repeating the crawl.

See docs/USAGE.md for the result fields and LIMITATIONS.md for the measured accuracy and the limits of the
current detector. Importing this package does not launch a browser; a browser opens only when audit() or
audit_async() runs.

A list of addresses is audited with one browser instead of one per site, which is the appropriate
mode for a run over thousands of them:

    from langaccess import audit_many
    results = audit_many(urls, concurrency=4, timeout=120)

A reading taken with `store=` can be judged again later without network access, which makes a rule
change checkable over a whole run and a validation sample codable twice against the same stored
capture:

    from langaccess import rejudge
    r = rejudge('run.jsonl', 'https://example.org/')
    r.verdict          # judged over the stored pages, with no network access
    r.unreproducible   # the steps of a live audit a stored capture cannot carry

`english_only` is the only class that asserts an absence, and an absence claim is worth
what the search behind it was worth. Every Result carries `read_quality`, and a crawl about to
return `english_only` on a search too thin to support the claim continues reading instead: it takes
the routes a first pass skips and judges again, on the same classes. `capture_acceptance` is
the run-level form, applied by `audit_many` to its own output, so a run degraded by machine load
reports the degradation in its own output.

Every decision names the numbered rule that made it. `RULES` is the registry of those rules, keyed
by number, each record carrying the rule's title and the objects in `langaccess.core` that apply
it, and `Result.rules` and `Evidence.rules` record what decided a site and a finding.
`rule_titles(r.rules)` turns the numbers a result carries into their titles. `explain` arranges all
of that for one site into the working behind its verdict, and judges nothing itself:

    from langaccess import explain_text
    print(explain_text(r))     # the rules that fired, their evidence, the axes, the read quality

Two runs over one set of addresses are compared by `diff_runs`, which is what every measurement in
this project does. Movement toward `unreachable` is reported separately and is never netted against
the rest, and an address in one run and not the other is counted and named:

    from langaccess import diff_runs
    d = diff_runs('before.jsonl', 'after.jsonl')
    d['unreachable']['toward']    # the sites that stopped being readable, first and on their own
    d['sites']['only_in_a']       # never silently dropped
    d['moved']                    # every site that changed, as data

The readings this package cannot settle are handed out as a work queue rather than published as
verdicts. `needs_human` reads the verdict and `read_quality` of one reading and answers whether a
person has to decide it; `review_queue` collects them with everything a coder needs in the row, and
`ingest_review` reads the filled sheet back, where a hand verdict wins over the machine's and is
recorded as a piece of evidence naming it hand coding, so a later reader can ask what share of a
figure came from a person:

    from langaccess import needs_human, review_queue, ingest_review, hand_coding
    q = review_queue('run.jsonl')
    q['unsettled']                # how many of the run need a person, beside q['records']
    q['contested']                # settled readings carrying a shape trained coders split over
    records, report = ingest_review('review.csv', 'run.jsonl')
    hand_coding(records[0])       # the coding a person did, or None

`contested` is the second of those counts on one reading: a settled verdict the package stands
behind, whose SHAPE is where the validation's blind coders disagreed with each other. No figure is
attached to the flag; it names where a coder's time buys the most, and it moves no result.

One reading, as a document about one site for a person outside this project, is what `report`
arranges and `report_text` and `report_html` render. It carries the class and what that class means
in a sentence, the languages one at a time, every quotation with the address it was read at, the
rules that decided it, what the search reached and what it did not, the date and the version, and
the statement that this package makes no determination of compliance with any law, regulation or
professional guidance and holds no threshold at which a site becomes adequate:

    from langaccess import report_html, write_report
    write_report(r, 'example.html')      # one HTML file, fetching nothing from anywhere
    write_report(r, 'example.txt')       # the same document as plain text
"""
from .core import (MT_ERROR, audit, audit_async, audit_many, audit_many_async, Result, Evidence,
                   BrowserUnavailable,
                   languages_in, class_for, authorship_of, sufficiency_of,
                   AUTHOR_AUTHORED, AUTHOR_SERVER_PLUGIN, AUTHOR_CLIENT_WIDGET,
                   AUTHOR_UNKNOWN_WIDGET, AUTHOR_NONE,
                   widget_name, unnamed_control,
                   SUFF_NONE, SUFF_TOKEN, SUFF_NOTICE, SUFF_PAGE, SUFF_SECTION,
                   SUFFICIENCY_NAMES,
                   RULES, Rule, rule_titles, verdict_rules,
                   rejudge, rejudge_store, read_store, REJUDGE_LIMITS,
                   read_quality_of, capture_acceptance, READ_ENOUGH_PAGES,
                   set_page_delay, set_acceptance,
                   sector_caveat, GOVERNMENT_TM_CAVEAT,
                   failure_kind, FAILURE_KINDS,
                   page_language, undeclared_languages)
# The names the authorship axis carried in earlier revisions, re-exported for one release and then
# removed. See the block at the foot of core.py for what each one now is; a stored capture's
# `provenance` key is a separate matter and is read for good.
from .core import (provenance_of, provenance_summary,
                   PROV_AUTHORED, PROV_SERVER_PLUGIN, PROV_CLIENT_WIDGET, PROV_NONE)
# Three layers over what a reading already recorded. None judges a site, and none is imported by
# `core`, so nothing here can move a classification. `review` is the one that takes a decision back
# IN, and it records a hand verdict as a hand verdict rather than as a reading.
# The address check the command line runs before an audit, exported so a library caller can run
# it too: a string that was never an address, handed straight to `audit`, comes back as an
# unreachable site, and this is the way to tell that apart from a site that is down.
from .address import auditable_url, AddressRejected
from .explain import explain, explain_text
from .diff import diff_runs, diff_text
from .review import (needs_human, unsettled_kind, unsettled_reason, review_queue, review_row,
                     review_text, write_review, read_review, ingest_review, ingest_text,
                     write_records, hand_coding, SheetRejected, HAND_CODING,
                     contested, contested_reason, CONTESTED_KINDS, CONTESTED_TITLE,
                     COLUMNS as REVIEW_COLUMNS)
# The fourth layer, and the only one addressed to somebody outside this project. It reads what the
# other three read and renders it as one document about one site; `LIMITS` is what that document
# says about itself, and it is rendered in full in both forms.
from .report import (report, report_text, report_html, render, write_report, form_for,
                     NothingToReport, LIMITS as REPORT_LIMITS, CLASS_MEANING)
# A roster CSV in, a tidy table out: the two ends of the pipe a study runs, one reading the address
# and sector columns a run takes, the other turning results into a pandas frame joined on
# requested_url. pandas is optional and imported only inside `to_frame`.
from .frames import read_roster, to_frame, FRAME_COLUMNS
# How far each language reaches into the pages a capture holds, the completeness question no
# class can carry. A layer over a finished record, with no validated figure and none claimed.
from .depth import depth_of, depth_run
# The unreachable rows re-read through the browser the user already trusts, attached over the
# DevTools protocol. Every retried record says so, and keeps the clean-room verdict beside it.
from .retry import (retry_unreachable_async, retry_text, write_retry,
                    DEFAULT_CDP as RETRY_DEFAULT_CDP)

# 0.1.0 is the released version, and it names this tree. The agreement figure measured against it,
# the kappa and the sample are in LIMITATIONS.md. A figure repeated here would be a second record of
# one fact and would fall out of step with the scoring the first time either moved.
__version__ = "0.1.0"

__all__ = ['audit', 'audit_async', 'audit_many', 'audit_many_async', 'Result', 'Evidence',
           'BrowserUnavailable',
           'languages_in', 'class_for', 'MT_ERROR', 'authorship_of', 'sufficiency_of',
           'AUTHOR_AUTHORED', 'AUTHOR_SERVER_PLUGIN', 'AUTHOR_CLIENT_WIDGET',
           'AUTHOR_UNKNOWN_WIDGET', 'AUTHOR_NONE',
           'widget_name', 'unnamed_control',
           'SUFF_NONE', 'SUFF_TOKEN', 'SUFF_NOTICE', 'SUFF_PAGE', 'SUFF_SECTION',
           'SUFFICIENCY_NAMES',
           'RULES', 'Rule', 'rule_titles', 'verdict_rules',
           'rejudge', 'rejudge_store', 'read_store', 'REJUDGE_LIMITS',
           'read_quality_of', 'capture_acceptance', 'READ_ENOUGH_PAGES',
           'set_page_delay', 'set_acceptance',
           'sector_caveat', 'GOVERNMENT_TM_CAVEAT',
           'failure_kind', 'FAILURE_KINDS', 'page_language', 'undeclared_languages',
           'auditable_url', 'AddressRejected',
           'explain', 'explain_text', 'diff_runs', 'diff_text',
           'needs_human', 'unsettled_kind', 'unsettled_reason', 'review_queue', 'review_row',
           'review_text', 'write_review', 'read_review', 'ingest_review', 'ingest_text',
           'write_records', 'hand_coding', 'SheetRejected', 'HAND_CODING', 'REVIEW_COLUMNS',
           'contested', 'contested_reason', 'CONTESTED_KINDS', 'CONTESTED_TITLE',
           'report', 'report_text', 'report_html', 'render', 'write_report', 'form_for',
           'NothingToReport', 'REPORT_LIMITS', 'CLASS_MEANING',
           'depth_of', 'depth_run',
           'read_roster', 'to_frame', 'FRAME_COLUMNS',
           'retry_unreachable_async', 'retry_text', 'write_retry', 'RETRY_DEFAULT_CDP',
           # deprecated, one release only
           'provenance_of', 'provenance_summary',
           'PROV_AUTHORED', 'PROV_SERVER_PLUGIN', 'PROV_CLIENT_WIDGET', 'PROV_NONE']
