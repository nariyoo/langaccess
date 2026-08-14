# -*- coding: utf-8 -*-
"""Command-line entry point for langaccess.

    langaccess https://example.org https://other.org
    langaccess --json https://example.org          # one JSON object per line, to stdout
    langaccess --concurrency 4 url1 url2 url3 ...   # audit several URLs at once
    langaccess --deep --timeout 240 https://example.org   # slower routes, capped per site
    langaccess --from-file sites.txt --json --output out.jsonl   # a list in, a file out
    langaccess --shared-browser --concurrency 8 --from-file sites.txt   # one browser for the run
    langaccess --explain https://example.org        # the working behind one verdict
    langaccess --explain --rejudge run.jsonl https://example.org   # the same, off a stored capture
    langaccess diff run_a.jsonl run_b.jsonl         # what moved between two runs of one frame
    langaccess review run.jsonl -o review.csv       # the readings that need a person, as a sheet
    langaccess ingest review.csv run.jsonl          # the filled sheet, back into the run
    langaccess report run.jsonl URL -o site.html    # one reading, as a document about one site

The human-readable output format below is the same one the original script printed; --json,
--concurrency, --deep, --no-escalate, --timeout, --from-file, --output, --shared-browser,
--block-private-hosts, --ignore-robots, --store, --explain and --version are additions for
packaging, not changes to the judgement logic. `diff`, `review`, `ingest`, `report` and
`depth` are subcommands that read files, reach no site, and judge nothing; `retry` is the one that
reaches sites, exactly the sites a clean browser could not, through the user's own browser and
saying so on every record.

    langaccess demo                                          # four invented sites, no browser
    langaccess retry run.jsonl --your-browser -o out.jsonl   # unreachable rows, a separate Chrome profile
    langaccess depth run.jsonl                               # how far each language reaches

A result is printed as soon as the results before it are ready, so a run over a thousand sites shows
its work while it goes and a run that is killed halfway has printed what it finished. The order is
the order the URLs were given in, whatever order the audits complete in.

A site that cannot be audited is a result and the run continues. A machine that cannot start a
browser is not: the run stops where it stands, says so once on stderr, and exits EXIT_NO_BROWSER.
A string that is not an address is neither: it is refused before any browser work, named on stderr,
audited not at all, and kept out of every output, because a row in an output file says a site was
read. The exit codes are documented below.
"""
import argparse
import asyncio
import gzip
import json
import os
import sys
import time

from . import __version__
from .address import AddressRejected, auditable_url
from .files import ReplaceBlocked, replace_atomically
from .core import (audit_async, audit_many_async, BrowserUnavailable, Result, SUFFICIENCY_NAMES,
                   _snip,
                   StoreWriteFailed, probe_store,
                   set_page_delay, set_acceptance, IGNORE_ROBOTS_MIN_DELAY,
                   RULES, read_store, rejudge_store, _stored_record)
from .diff import diff_runs, diff_text
from .explain import explain, explain_text
from .report import NothingToReport, form_for, render, report, write_report
from .review import (SheetRejected, ingest_review, ingest_text, review_queue, review_text,
                     write_records, write_review)


# What the process says about itself when it ends, and why these three numbers.
#
# 0 means the run was PERFORMED. It says nothing about the verdicts: a file of a thousand addresses
# that all came back `unreachable` because a thousand sites refused the crawler exits 0, because
# that is a reading and the reading is in the output.
#
# 2 is argparse's own code for a command line it could not parse, and it is named here rather than
# used, so that nothing else in this tool takes it. A machine that cannot run a browser and a
# command typed wrong are opposite problems and must not answer the same.
#
# 1 is what an unhandled exception already produces, and it is left to that. Reserving it keeps
# "this tool crashed" separable from "this tool refused to begin a run it could not perform".
#
# 3 is therefore the first code no convention here claims, and it means: no browser could be
# started, nothing was read, and no result below the failure line was written. An earlier revision
# exited 0 in this case with one `unreachable` row per address, so a `--from-file` run over a
# thousand addresses reported success over a thousand sites nobody had looked at.
#
# 4 is a stage that produced nothing: a run holding no records, a `review` that found nothing to
# review with --fail-on-empty, an `ingest` whose sheet applied nothing with the same flag, a
# `report` over records none of which held a reading. It is
# separate from 0 because an empty result reported as a completed one is this project's most
# frequent bug, six distinct instances of it, and separate from 1 because nothing crashed: the
# stage ran, it produced nothing, and it said so.
#
# 5 is a review sheet that cannot be applied to the run it was given with. Nothing is written and
# every fault is named. Not 2, because argparse's code means a command line that could not be
# parsed, and this command line parsed: what does not match is a file's contents.
#
# 6 is at least one string that was given as an address and is not one. It is not 0, because the run
# read fewer sites than the list held and a caller that exits 0 has been told the list was audited.
# It is not 2: the command line parsed, and on a `--from-file` run the offending string is not on
# the command line at all but on line 617 of somebody's spreadsheet export, which is a different
# thing to go and look at. It is not 4, which says a stage ran over its input and produced nothing,
# because here part of the input was never a site and the run may have audited the rest of it
# perfectly well. It is not 3, which outranks it: a missing browser means nothing was read at all,
# and that is the more serious statement, so a run that hits both answers 3.
#
# 7 is a finished file that could not be moved onto the path it replaces, because something else on
# the machine was holding that path open. It is not 1: nothing crashed and nothing was lost, and the
# completed file is named in the message, so the action is a rename and not a re-run. Windows only in
# practice; see `files.replace_atomically` for the measurement that put it here.
#
# One code covers both the run in which every address was rejected and the run in which two of four
# were. The fact a pipeline has to act on is the same either way, that the output no longer covers
# the list it was given, and the counts are on stderr in both cases. Splitting the two would mean
# a caller has to test for two codes to catch one condition, and the caller that tests for one of
# them treats the other as a clean run.
EXIT_OK = 0
EXIT_USAGE = 2
EXIT_NO_BROWSER = 3
EXIT_NOTHING = 4
EXIT_SHEET_REJECTED = 5
EXIT_INPUT_REJECTED = 6
EXIT_WRITE_BLOCKED = 7
# the run's own store stopped taking writes (disk full, path revoked): the run stops where it
# stands, what was appended is safe on disk, and no site after the failure gets a row
EXIT_STORE_FAILED = 8


def _rung(n):
    """A sufficiency level as the number and the name of the rung, for a person reading output."""
    return f'{n} {SUFFICIENCY_NAMES.get(n, "?")}'


def _print_human(r):
    print(f'\n{r.url}')
    # the note whenever there is one, not only on an unreachable site. 'locale route returned
    # English' is the sentence behind an english_only verdict on a site with a widget, and it was
    # written to the JSON and invisible to anyone reading the human output.
    print(f'  verdict   {r.verdict}' + (f'  ({r.note})' if r.note else ''))
    # The two axes the verdict is derived from. A verdict is a conclusion and these are what it was
    # read off, so a person checking one should not have to open the JSON to see them.
    print(f'  evidence  authorship {r.authorship}   sufficiency {_rung(r.sufficiency)}')
    print(f'  languages {", ".join(r.languages) or "-"}')
    # per language, because one summary hides a site with authored Spanish and widget Vietnamese
    for lg in sorted(r.by_language):
        row = r.by_language[lg]
        print(f'    {lg:<16} {row["authorship"]:<14} {_rung(row["sufficiency"])}')
    print(f'  widget    {r.machine_translation or "-"}   pages read {r.pages_read}')
    # What the search behind the verdict was worth. Printed for every site, not only for
    # english_only, because the field exists so that a run degraded by machine load says so
    # in its own output instead of having to be caught by hand.
    q = r.read_quality or {}
    if q:
        why = [k for k in ('shallow', 'clock_exhausted', 'budget_exhausted') if q.get(k)]
        if q.get('reads_timed_out'):
            why.append(f'{q["reads_timed_out"]} reads timed out')
        thin = 'enough to rest an absence claim on' if q.get('sufficient') else 'NOT enough'
        print(f'  search    {thin}' + (f'  ({", ".join(why)})' if why else '')
              + ('  [escalated]' if q.get('escalated') else ''))
    # The MENU, which is not the site's own writing and is printed apart from `languages` so that it
    # cannot be read as though it were. The unresolved count is shown whenever there is one, because
    # eight names with sixty unknowns beside them is a different fact from eight names.
    # A menu whose every entry is a code this package cannot name is still a menu, and the line was
    # printed only when at least one name resolved, so the reader was told nothing while the JSON
    # carried `switcher_unresolved`. An hreflang of `hmong` or `karen` does exactly that.
    if r.switcher_languages or r.switcher_unresolved:
        more = f' (+{r.switcher_unresolved} this tool cannot name)' if r.switcher_unresolved else ''
        offered = ', '.join(r.switcher_languages[:12])
        if len(r.switcher_languages) > 12:
            offered += f', and {len(r.switcher_languages) - 12} more'
        if r.switcher_languages:
            print(f'  switcher  offers {len(r.switcher_languages)}{more}: {offered}')
        else:
            print(f'  switcher  offers {r.switcher_unresolved}, none of which this tool can name')
    # which numbered rules decided this, by number and short title, so a person disagreeing with
    # the verdict has something to disagree with other than the verdict
    if r.rules:
        print('  rules     ' + '; '.join(f'{n} {RULES[n].title}' for n in r.rules if n in RULES))
    # only ever set on a re-judged capture, and the one thing a reader of one has to know
    if r.unreproducible:
        print('  not re-run  ' + ', '.join(r.unreproducible))
    for e in r.evidence[:6]:
        # `_snip` and not a bare slice: the terminal line has room for about eighty characters and
        # cutting at exactly eighty ended one demo reading on '[Productivit'. The stored quote is
        # unaffected; this is the width of one line of output.
        print(f'    {e.mechanism:<18} {e.language or "":<16} {_snip(e.quote, 0, 80)!r}')


def _emit(r, as_json, sink=None, explaining=False):
    """Print one result, and append it to the file `--output` names when there is one.

    `--explain` changes only what is printed. The file keeps the result row whatever the screen
    shows, because a run's output file is what a census reads and an explanation is for a person.
    """
    if as_json:
        row = json.dumps(r.to_dict(), ensure_ascii=False)
        print(json.dumps(explain(r), ensure_ascii=False) if explaining else row)
        if sink is not None:
            sink.write(row + '\n')
            sink.flush()
    elif explaining:
        print('\n' + explain_text(r))
    else:
        _print_human(r)
    try:
        sys.stdout.flush()
    except Exception:
        pass


# A stderr heartbeat for a run long enough to want one. Off for a handful of sites; otherwise a line
# every PROGRESS_EVERY seconds and one at the end, so a census logged to a file gets a readable trail
# and not a flood. It goes to stderr, so it never mixes with the results a run writes to stdout.
PROGRESS_MIN_SITES = 20
PROGRESS_EVERY = 30.0


def _progress(done, total, t0):
    """One heartbeat line: how far, how fast, how long is left. Elapsed and ETA in whole seconds."""
    el = max(1e-9, time.monotonic() - t0)
    rate = done / el
    eta = (total - done) / rate if rate > 0 and done < total else 0.0
    print('  ... %d/%d done, %.0fs elapsed, ~%.0fs left (%.1f sites/min)'
          % (done, total, el, eta, rate * 60), file=sys.stderr, flush=True)


async def _run(urls, concurrency, as_json, deep=False, timeout=None, output=None,
               shared_browser=False, block_private_hosts=False, ignore_robots=False, store=None,
               escalate=True, explaining=False, max_pages=None):
    """Audit the addresses and print each result. Returns (infrastructure failure or None, printed).

    The second half of that return is what separates the two kinds of ending. A site that could not
    be audited is a Result and is printed; a machine that cannot start a browser produces no Result
    at all, stops the run where it stands, and is handed back for `main` to report once and exit on.
    """
    sem = asyncio.Semaphore(max(1, concurrency))
    # passed only when it was asked for, so an ordinary run calls audit_async exactly as before
    extra = {}
    if block_private_hosts:
        extra['block_private_hosts'] = True
    if ignore_robots:
        extra['respect_robots'] = False
    if store:
        # fail in the first second, not the two-hundredth hour: a path that cannot take the
        # run's appends is an infrastructure failure before it is anything else
        probe_store(store)
        extra['store'] = store
    if not escalate:
        extra['escalate'] = False
    if max_pages is not None:
        extra['max_pages'] = max_pages

    # A stderr heartbeat, throttled, for a run long enough to want one. See `_progress`.
    total = len(urls)
    _t0 = time.monotonic()
    _prog = {'done': 0, 'last': time.monotonic()}

    def _tick():
        _prog['done'] += 1
        now = time.monotonic()
        if total < PROGRESS_MIN_SITES:
            return
        if _prog['done'] < total and now - _prog['last'] < PROGRESS_EVERY:
            return
        _prog['last'] = now
        _progress(_prog['done'], total, _t0)

    async def one(u):
        async with sem:
            try:
                return await audit_async(u, deep=deep, timeout=timeout, **extra)
            except asyncio.TimeoutError:
                return Result(url=u, requested_url=u, note=f'timed out after {timeout}s')
            except (BrowserUnavailable, StoreWriteFailed):
                # NOT a result. Every address on the list would come back the same way, because
                # what failed is the machine and not the site, and a row saying `unreachable` here
                # is a claim about a site that was never opened. A store that stopped taking
                # writes is the same kind of fact: before it was named, a disk that filled
                # mid-run turned every remaining site into an unreachable row and exited 0. Out
                # to the loop below, which stops the run.
                raise
            except Exception as e:
                # One site that raises used to take the whole batch down through gather, and every
                # result already computed was lost with it. A site that cannot be audited is a
                # result: unreachable, with what went wrong written in the note.
                return Result(url=u, requested_url=u, note=f'{type(e).__name__}: {e}'[:200])

    async def slot(i, u):
        return i, await one(u)

    sink = None
    if output and as_json:
        # a .gz name is honoured here the way --store has always honoured it; before this,
        # out.jsonl.gz got plain text and --resume then refused its own file as not-gzip
        sink = (gzip.open(output, 'at', encoding='utf-8') if str(output).endswith('.gz')
                else open(output, 'a', encoding='utf-8'))
    done_by_index, nxt = {}, 0
    broken = None                       # the one infrastructure failure that stopped the run

    def drain():
        # print the run of results that is complete from the front, and hold the rest
        nonlocal nxt
        while nxt in done_by_index:
            _emit(done_by_index.pop(nxt), as_json, sink, explaining)
            nxt += 1

    pending = set()
    try:
        if shared_browser:
            # one Chromium for the whole run. The results still print in the order the addresses
            # were given, as the prefix that is finished completes.
            def landed(i, r):
                done_by_index[i] = r
                drain()
                _tick()

            got = None
            try:
                got = await audit_many_async(urls, concurrency=concurrency, deep=deep,
                                             timeout=timeout, on_result=landed, **extra)
            except (BrowserUnavailable, StoreWriteFailed) as e:
                # The batch launches its browser before it reads anything, so this arrives with
                # nothing read and everything the run had already settled already printed. A
                # store that stopped taking writes ends the run the same way, with what was
                # already appended safe on disk.
                broken = e
            for i, r in enumerate(got or []):
                if i >= nxt and i not in done_by_index:
                    done_by_index[i] = r
            drain()
            return broken, nxt
        pending = {asyncio.ensure_future(slot(i, u)) for i, u in enumerate(urls)}
        while pending and broken is None:
            finished, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
            for f in finished:
                err = f.exception()
                if isinstance(err, (BrowserUnavailable, StoreWriteFailed)):
                    # the first one wins and the rest of the run is abandoned. Reported once, by
                    # `main`, to stderr, instead of once per address on stdout
                    broken = broken or err
                    continue
                if err is not None:
                    raise err
                i, r = f.result()
                done_by_index[i] = r
                _tick()
            drain()
        return broken, nxt
    finally:
        # Whatever ended the run, nothing is left running behind it and the file holds what was read.
        for f in pending:
            f.cancel()
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)
        if sink is not None:
            sink.close()


def _addresses_already_done(path):
    """Every address a previous run finished, from its `--output` or `--store` file.

    Both files are JSON lines and both carry `requested_url`, the address as the run was given it,
    which is the only field a resume can match on: `url` is where the browser ended up, and on the
    1,000-site round of 2026-08-07 that was a different address for 209 of the 1,000. Matching on
    `url` would re-read a fifth of a list on every resume and write a second row for each.

    A capture written before `requested_url` existed answers with `url`, which is right for the
    sites that did not redirect and re-reads the ones that did. The count is printed either way, so
    a resume that skips fewer rows than expected is visible rather than silent.
    """
    seen, lines, old = set(), 0, 0
    opener = (lambda: gzip.open(path, 'rt', encoding='utf-8')) if str(path).endswith('.gz') \
        else (lambda: open(path, encoding='utf-8'))
    with opener() as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            lines += 1
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            a = rec.get('requested_url') or ''
            if not a:
                a, old = rec.get('url') or '', old + 1
            if a:
                seen.add(_resume_key(a))
    return seen, lines, old


def _resume_key(u):
    """An address as a resume compares it: no scheme, no trailing slash, lower case."""
    s = str(u or '').strip().lower()
    for pre in ('https://', 'http://'):
        if s.startswith(pre):
            s = s[len(pre):]
            break
    return s.rstrip('/')


class InputFileUnusable(Exception):
    """A `--from-file` path that cannot be read, carrying the sentence a person acts on.

    Raised instead of letting the underlying OSError out, because a mistyped path is the most
    ordinary mistake there is and it used to answer with a traceback ending in `_urls_from_file`,
    which names this package's internals and not the thing the user got wrong. The callers turn it
    into `parser.error`, so a missing file answers exactly as an empty one already did.
    """


def _urls_from_file(path):
    """One address per line. A blank line and a line starting with # are skipped.

    Three ways of not being a readable list of addresses are named rather than raised: the path does
    not exist, it is a directory, and it is bytes that are not UTF-8. The third is the one worth
    catching by hand, because the usual cause is a spreadsheet or a gzipped run file handed to
    `--from-file`, and the UnicodeDecodeError it produces says nothing about which file that was.
    """
    if path == '-':
        text = sys.stdin.read()
    else:
        # Tested before the open, because a directory answers differently on different systems: a
        # POSIX open of one raises IsADirectoryError and a Windows one raises PermissionError, which
        # would otherwise be reported as a file this account may not read.
        if os.path.isdir(path):
            raise InputFileUnusable(
                '%s is a directory. --from-file wants a text file holding one address per line.'
                % path)
        try:
            with open(path, encoding='utf-8') as fh:
                text = fh.read()
        except FileNotFoundError:
            raise InputFileUnusable(
                '%s does not exist. --from-file wants a text file holding one address per line, or '
                '- to read the list from standard input.' % path)
        except UnicodeDecodeError:
            raise InputFileUnusable(
                '%s is not UTF-8 text, so it holds no list this can read. A spreadsheet, a gzipped '
                'run file and a UTF-16 export all fail here; save the addresses as plain UTF-8 '
                'text, one per line.' % path)
        except OSError as e:
            raise InputFileUnusable('%s could not be read: %s' % (path, e))
    out = []
    for line in text.splitlines():
        line = line.strip()
        if line and not line.startswith('#'):
            out.append(line)
    return out


def _reject_what_is_not_an_address(urls):
    """Split what was given into the addresses to audit and the strings that are not addresses.

    The rejected ones are named on stderr here, one line each, and go no further: they are not
    audited, they produce no verdict, and they appear in neither `--json` nor `--store`, because a
    row in either of those says a site was read. Handing `hello world` and `htp://example.org` to
    the audit produced `unreachable` for both, which in a study is counted as a site that refused
    the crawler; the second is the one that does real damage, because a scheme a letter out of true
    is a typo nobody spots in a thousand-row file and every other field of the row looks ordinary.

    Nothing is dropped silently: the count is reported by the caller whether some addresses survived
    or none did, and the process answers EXIT_INPUT_REJECTED either way.
    """
    good, rejected = [], []
    for u in urls:
        try:
            auditable_url(u)
        except AddressRejected as e:
            rejected.append(e)
            print('langaccess did not audit %r: %s. It was given no verdict and it is in no output.'
                  % (e.raw, e.reason), file=sys.stderr)
        else:
            good.append(u)
    return good, rejected


def _main_diff(argv):
    """`langaccess diff a.jsonl b.jsonl`, which reads two run files and reaches no site.

    Its own parser, because every option of the audit parser is meaningless here and a subcommand
    sharing them would accept `langaccess diff --deep`, which means nothing. The rest of the tool
    keeps the flat command line it has always had.
    """
    p = argparse.ArgumentParser(
        prog='langaccess diff',
        description='Compare two runs over one set of addresses and report what moved. Movement '
                    'toward unreachable is reported separately and first, and an address in one '
                    'run and not the other is counted and named.')
    p.add_argument('a', metavar='RUN_A', help='the earlier run, one JSON object per line')
    p.add_argument('b', metavar='RUN_B', help='the later run, in the same form')
    p.add_argument('--json', action='store_true',
                   help='print the comparison as one JSON object, holding every moved site as data')
    args = p.parse_args(argv)
    for path in (args.a, args.b):
        if not os.path.exists(path):
            p.error('%s does not exist. A run file is what --json --output or --store wrote.'
                    % path)
    d = diff_runs(args.a, args.b)
    print(json.dumps(d, ensure_ascii=False) if args.json else diff_text(d))
    return EXIT_OK


def _main_review(argv):
    """`langaccess review run.jsonl -o review.csv`, the readings a person has to settle.

    Its own parser, for the reason `diff` has one. Nothing here reaches a site: the queue is read
    off `verdict` and `read_quality`, which every reading already carries.
    """
    p = argparse.ArgumentParser(
        prog='langaccess review',
        description='Write the readings this package could not settle to a sheet for a person to '
                    'finish: the sites that were not read, the english_only verdicts whose search '
                    'was too thin to rest an absence claim on, and any record holding no class.')
    p.add_argument('run', metavar='RUN',
                   help='a run, one JSON object per line, as --json --output or --store wrote it')
    p.add_argument('-o', '--output', metavar='PATH', required=True,
                   help='where to write the sheet, as CSV')
    p.add_argument('--fail-on-empty', dest='fail_on_empty', action='store_true',
                   help='exit %d when no reading in the run needs a person, for a pipeline that '
                        'must not treat an empty queue as a finished one' % EXIT_NOTHING)
    args = p.parse_args(argv)
    if not os.path.exists(args.run):
        p.error('%s does not exist. A run file is what --json --output or --store wrote.'
                % args.run)

    q = review_queue(args.run)
    # An empty INPUT is a broken stage whatever was asked for, and it stops here rather than
    # reporting that a run of nothing needed nobody.
    if not q['records']:
        print('%s holds no records, so there was nothing to review. Nothing was written.'
              % args.run, file=sys.stderr)
        return EXIT_NOTHING
    if not q['unsettled']:
        print(review_text(q))
        return EXIT_NOTHING if args.fail_on_empty else EXIT_OK
    write_review(q, args.output)
    print(review_text(q, output=args.output))
    return EXIT_OK


def _main_ingest(argv):
    """`langaccess ingest review.csv run.jsonl`, the filled sheet read back into the run.

    The settled run is written over RUN unless `-o` names somewhere else, and it is written whole
    and moved into place, so a run being replaced by its own settled form is never left half
    written by an interruption.
    """
    p = argparse.ArgumentParser(
        prog='langaccess ingest',
        description='Read a filled review sheet back into a run. A human verdict wins over the '
                    "machine's and is recorded as a piece of evidence naming it hand coding, so a "
                    'later reader can ask what share of a figure came from a person.')
    p.add_argument('sheet', metavar='SHEET', help='the filled sheet `langaccess review` wrote')
    p.add_argument('run', metavar='RUN', help='the run the sheet was drawn from')
    p.add_argument('-o', '--output', metavar='PATH',
                   help='write the settled run here instead of over RUN')
    p.add_argument('--dry-run', dest='dry_run', action='store_true',
                   help='report what would be applied and write nothing')
    p.add_argument('--fail-on-empty', dest='fail_on_empty', action='store_true',
                   help='exit %d when no row of the sheet carries a human verdict' % EXIT_NOTHING)
    args = p.parse_args(argv)
    for path in (args.sheet, args.run):
        if not os.path.exists(path):
            p.error('%s does not exist.' % path)

    try:
        records, report = ingest_review(args.sheet, args.run)
    except SheetRejected as e:
        # Named one by one and applied not at all. A sheet with a wrong address in it is a sheet
        # built against a different run, and applying the rows that happen to match would put half
        # a coding round into a file and report success.
        print('langaccess ingest refused %s, and applied nothing:' % args.sheet, file=sys.stderr)
        for line in e.problems:
            print('  %s' % line, file=sys.stderr)
        return EXIT_SHEET_REJECTED
    if not report['rows']:
        print('%s holds no rows, so there was nothing to ingest. Nothing was written.'
              % args.sheet, file=sys.stderr)
        return EXIT_NOTHING

    written = ''
    if not args.dry_run:
        target = args.output or args.run
        # the temp name KEEPS the target's suffix, because `write_records` decides compression
        # off the name it is given: a bare '.ingest-tmp' wrote plain text and the atomic rename
        # then put it over a gzip archive, which no reader of the store could open afterwards
        tmp = (target + '.ingest-tmp.gz') if str(target).endswith('.gz') \
            else (target + '.ingest-tmp')
        write_records(records, tmp)
        try:
            replace_atomically(tmp, target)
        except ReplaceBlocked as e:
            # A hand-coding round is the most expensive input this tool takes, and a traceback here
            # reads as having lost one. The settled run is complete at `e.finished`.
            print('langaccess ingest could not finish writing: %s' % e, file=sys.stderr)
            return EXIT_WRITE_BLOCKED
        written = target
    print(ingest_text(report, written=written))
    if not report['applied'] and args.fail_on_empty:
        return EXIT_NOTHING
    return EXIT_OK


def _slug(url, taken):
    """A file name for one address, unique within this run.

    The host and path with everything that is not a letter, a digit or a dash turned into a dash, so
    two addresses of one site do not land on one file. A collision is numbered rather than resolved
    silently, because a run that wrote 900 documents into 880 files has lost twenty readings.
    """
    raw = str(url or '').split('://', 1)[-1].strip('/').lower()
    out = ''.join(c if (c.isalnum() or c == '-') else '-' for c in raw).strip('-')
    while '--' in out:
        out = out.replace('--', '-')
    out = out[:120] or 'site'
    name, n = out, 1
    while name in taken:
        n += 1
        name = '%s-%d' % (out, n)
    taken.add(name)
    return name


def _main_report(argv):
    """`langaccess report run.jsonl URL -o site.html`, one reading as a document about one site.

    Its own parser, for the reason `diff` has one. Nothing here reaches a site: the document is
    arranged out of what the reading already recorded, and `report` judges nothing.
    """
    p = argparse.ArgumentParser(
        prog='langaccess report',
        description='Write one reading as a document about one site, for a person outside this '
                    'project: the class and what it means, the languages one at a time, every '
                    'quotation with the address it was read at, the rules that decided it, what '
                    'the search reached, the date and the version, and the statement that this '
                    'package determines no compliance with any law, regulation or professional '
                    'guidance.')
    p.add_argument('run', metavar='RUN',
                   help='a run, one JSON object per line, as --json --output or --store wrote it')
    p.add_argument('url', metavar='URL', nargs='?',
                   help='which address to write about. Needed where the run holds more than one')
    p.add_argument('-o', '--output', metavar='PATH',
                   help='where to write the document. With none, it is printed as text')
    p.add_argument('--format', dest='form', choices=('html', 'text'),
                   help='which form to render. With none, the extension of --output decides, and '
                        'text is what is printed')
    p.add_argument('--all', dest='every', action='store_true',
                   help='write one document per address in the run, into --dir')
    p.add_argument('--dir', metavar='DIR',
                   help='the directory --all writes into. It has to exist')
    args = p.parse_args(argv)
    if not os.path.exists(args.run):
        p.error('%s does not exist. A run file is what --json --output or --store wrote.'
                % args.run)
    if args.every and not args.dir:
        p.error('--all writes one document per address, so it needs --dir DIR to write them into.')
    if args.every and args.url:
        p.error('--all writes about every address in the run, so URL selects nothing. Give one or '
                'the other.')

    records = list(read_store(args.run))
    if not records:
        print('%s holds no records, so there was nothing to report on. Nothing was written.'
              % args.run, file=sys.stderr)
        return EXIT_NOTHING

    if args.every:
        if not os.path.isdir(args.dir):
            p.error('%s is not a directory. --all writes one file per address into an existing '
                    'directory.' % args.dir)
        form = args.form or 'html'
        ext = '.html' if form == 'html' else '.txt'
        taken, written, skipped = set(), [], []
        for rec in records:
            try:
                doc = report(rec)
            except NothingToReport:
                # named, not counted silently: a record that held no reading is the row somebody
                # has to go and look at, and a run that quietly wrote fewer files than it read
                # records is the shape this project has shipped six times
                skipped.append(str(rec.get('url', '') or '(no address)'))
                continue
            path = os.path.join(args.dir, _slug(doc['url'], taken) + ext)
            write_report(doc, path, form)
            written.append(path)
        print('langaccess report')
        print('  %s   %d records read' % (args.run, len(records)))
        print('  documents written   %d, into %s' % (len(written), args.dir))
        if skipped:
            print('  records holding no reading   %d' % len(skipped))
            for u in skipped[:20]:
                print('    %s' % u)
            if len(skipped) > 20:
                print('    and %d more' % (len(skipped) - 20))
        if not written:
            print('no record in %s held a reading, so no document was written.' % args.run,
                  file=sys.stderr)
            return EXIT_NOTHING
        return EXIT_OK

    try:
        rec = _stored_record(args.run, args.url)
    except (KeyError, ValueError) as e:
        # a KeyError stringifies to its own repr, so one fault was reported inside quotes
        # while the ValueError two lines away was not
        p.error(e.args[0] if e.args and isinstance(e.args[0], str) else str(e))
    try:
        doc = report(rec)
    except NothingToReport as e:
        print('langaccess report wrote nothing: %s' % e, file=sys.stderr)
        return EXIT_NOTHING

    if not args.output:
        print(render(doc, args.form or 'text'))
        return EXIT_OK
    chars = write_report(doc, args.output, args.form or '')
    print('langaccess report')
    print('  %s' % doc['url'])
    print('  %d sections, %d findings quoted' % (len(doc['sections']), doc['findings_total']))
    print('  written to %s as %s, %d characters'
          % (args.output, form_for(args.output, args.form or ''), chars))
    return EXIT_OK


# The words that change what runs, taken off the front before the audit parser sees anything. An
# address is never one of these bare words, so nothing a person could mean by the old command line
# is caught here.
def _main_retry(argv):
    """`langaccess retry run.jsonl --your-browser`, the unreachable rows through the user's own
    Chrome, attached over the DevTools protocol. The one subcommand that reaches sites, which is
    its whole point: the sites are the ones a clean browser could not reach."""
    from .retry import (retry_unreachable_async, retry_text, write_retry, BrowserNotAttached,
                        DEFAULT_CDP, DEFAULT_TIMEOUT, START_CHROME)
    ap = argparse.ArgumentParser(
        prog='langaccess retry',
        description='Re-read the unreachable rows of a run through your own browser. Use a '
                    'SEPARATE Chrome profile (--user-data-dir) with --remote-debugging-port=9222 '
                    'and leave it open: a debugging port on your everyday profile exposes every '
                    'session you are signed in to. The retry attaches, closes nothing of yours, '
                    'opens only http and https addresses on ports 80 and 443, refuses private and '
                    'loopback hosts, and stamps every retried record read_with_user_browser with '
                    'the clean-room verdict kept beside it.',
        epilog=START_CHROME)
    ap.add_argument('run', help='the JSON-lines run file')
    ap.add_argument('--your-browser', dest='yours', action='store_true', required=True,
                    help='required, so that borrowing the browser is always said out loud')
    ap.add_argument('--timeout', type=int, default=DEFAULT_TIMEOUT,
                    help='seconds per site (default %(default)s). Without it every clock guard '
                         'inside the audit is inert and one page can hold your browser for an hour')
    ap.add_argument('--cdp', default=DEFAULT_CDP,
                    help='where the browser is listening (default %(default)s)')
    ap.add_argument('-o', '--output', required=True, help='where to write the updated run')
    ap.add_argument('--keep-pages', action='store_true',
                    help='store the pages of the retried reads, as audit --store would')
    a = ap.parse_args(argv)
    if not os.path.exists(a.run):
        ap.error('no such run file: %s' % a.run)
    try:
        records, report = asyncio.run(
            retry_unreachable_async(a.run, cdp=a.cdp, timeout=a.timeout,
                                    keep_pages=a.keep_pages, output=a.output))
    except BrowserNotAttached as e:
        print(str(e), file=sys.stderr)
        return EXIT_NO_BROWSER
    if not report['records']:
        print('langaccess retry\n  %s holds no records, so nothing was retried' % a.run,
              file=sys.stderr)
        return EXIT_NOTHING
    try:
        write_retry(records, a.output)
    except ReplaceBlocked as e:
        # The reads are already done and paid for; only the move failed. Same answer as ingest.
        print('langaccess retry could not finish writing: %s' % e, file=sys.stderr)
        return EXIT_WRITE_BLOCKED
    print(retry_text(report, output=a.output))
    return EXIT_OK


def _main_depth(argv):
    """`langaccess depth run.jsonl`, how far each language reaches into the stored pages."""
    # the same three lines the five sibling subcommands have; without them a mistyped path
    # answered with a traceback
    from .depth import depth_run
    ap = argparse.ArgumentParser(
        prog='langaccess depth',
        description='For each record of a run stored with pages, how many of the read pages each '
                    'language reaches. A completeness description beside the classes; no figure '
                    'of it is validated and none is claimed.')
    ap.add_argument('run', help='a JSON-lines store written with --store')
    ap.add_argument('--json', action='store_true', help='print the whole result as JSON')
    a = ap.parse_args(argv)
    if not os.path.exists(a.run):
        ap.error('%s does not exist. A run file is what --json --output or --store wrote.'
                 % a.run)
    d = depth_run(a.run)
    if a.json:
        print(json.dumps(d, ensure_ascii=False, indent=1))
    else:
        print('langaccess depth')
        # The trailing clause only when there is a list to introduce. On an empty run it promised
        # names and then printed none.
        print('  %d records; %d hold pages; %d hold none%s'
              % (d['records'], len(d['measured']), len(d['no_pages']),
                 ' and are named below' if d['no_pages'] else ''))
        for url, m in d['measured'].items():
            langs = ', '.join('%s %d/%d' % (lang, k, m['pages_read'])
                              for lang, k in sorted(m['pages_by_language'].items()))
            print('  %s' % url)
            print('    %s' % langs)
        for url in d['no_pages']:
            print('  %s   (stored without pages, so depth is unmeasurable for it)' % url)
    # A run holding no records is EXIT_NOTHING, as it is for `review`, `ingest`, `report` and
    # `retry`. A `--store` path is opened for append before the first site is read, so a run that
    # died early leaves a zero-byte file, and this stage answered 0 over it: an empty result
    # reported as a completed one, which is the failure this project has hit most often.
    if not d['records']:
        print('%s holds no records, so there was nothing to measure.' % a.run, file=sys.stderr)
        return EXIT_NOTHING
    return EXIT_OK


# The one address this package will fetch without being given one. It belongs to the author, which
# is the whole reason it can be here: a demo target baked into a published tool is fetched once per
# person who ever installs it, and nobody else's site was asked. It is also the example worth having,
# because it carries a Google Translate widget offering eleven languages and its own Korean writing
# on archive pages, so `langaccess https://nariyoo.com` reads machine_translate and not
# true_multilingual, and names the rule that drew the line (13: an archive page does not carry the
# reading). `calibrate --demo` itself prints no verdict, because calibrate discards its probe
# readings; what it shows on this address is the ladder working. A site advertising eleven languages
# that the package declines to call multilingual is the distinction this package exists to make.
DEMO_URL = 'https://nariyoo.com'


def calibrate_plan(urls, attempts, quick=False):
    """The ladder of settings a calibration walks, and where it stops.

    Separated from the running so it can be tested without a browser. Each rung is tried in order
    and the walk stops at the first one the run-level gate accepts.

    The ladder raises the per-site clock before it touches anything else, because an exhausted clock
    is the failure that makes every other figure meaningless: a site that ran out of time read one
    page, so its depth says nothing about the machine and its verdict says nothing about the site.
    Concurrency only ever comes DOWN here. Raising it is left to the person, because on a machine
    that is already busy it makes each site slower and can push readings back into clock_exhausted,
    which is a change that undoes itself and should not happen without somebody watching.
    """
    ladder = [(120, 4), (240, 4), (480, 2)] if not quick else [(120, 4), (300, 2)]
    return ladder[:max(1, min(attempts, len(ladder)))]


def calibrate_reading(results):
    """The four figures a person is told to read, taken off one probe run.

    `sites` counts every address tried, `read` only those that produced a reading, and every share
    below is over `read`. An address that was never reachable has no search to judge, and counting
    it as a thin reading would make a list of dead addresses look like a slow machine.
    """
    from .core import capture_acceptance
    got = [dict(r.read_quality or {}) for r in results]
    read = [q for q in got if (q.get('pages_read') or 0) > 0]
    n = len(read)
    depths = sorted(int(q.get('pages_read') or 0) for q in read)
    acc = capture_acceptance(results)
    return {
        'sites': len(got), 'read': n,
        'clock_exhausted': sum(1 for q in read if q.get('clock_exhausted')),
        'escalated': sum(1 for q in read if q.get('escalated')),
        'sufficient': sum(1 for q in read if q.get('sufficient')),
        'median_pages': depths[n // 2] if n else 0,
        'accepted': acc['accepted'], 'why': acc['why'],
        'min_median_pages': acc.get('min_median_pages'),
        'max_thin_share': acc.get('max_thin_share'),
    }


def _main_calibrate(argv):
    """`langaccess calibrate --from-file sites.txt`, settings measured on THIS machine.

    Section 12.2 of USAGE as a command. A timeout copied out of somebody else's documentation is an
    observation about their machine, and on a slower one it produces a run that ends early, looks
    finished, and reports english_only where a language was. This measures instead.

    The sample is taken from the head of the user's own list rather than from a set of demo
    addresses shipped with the package. Two reasons, and the second is the stronger. A calibration is
    only worth anything if it meets the hosts, page weights and redirects the real run will meet. And
    a demo list baked into a published tool is a handful of sites fetched once per person who ever
    installs it, which is a load those site owners never agreed to.

    Probe readings are thrown away. What this prints is a setting, not a result: the addresses are
    read again by the real run, all of them under the one setting, so that no two sites in a run were
    measured under different conditions.
    """
    ap = argparse.ArgumentParser(
        prog='langaccess calibrate',
        description='Measure how long this machine needs per site, and print the settings for a '
                    'full run. Reads a small sample of your own list and discards the readings.')
    ap.add_argument('urls', nargs='*', help='addresses to probe with')
    ap.add_argument('--from-file', dest='from_file', metavar='PATH',
                    help='read the list from a file and take the sample from the head of it')
    ap.add_argument('--demo', action='store_true',
                    help='probe %s, the author\'s own site, to see the tool work before you have a '
                         'list. One address calibrates nothing; it shows the shape of the output'
                         % DEMO_URL)
    ap.add_argument('-n', '--sample', type=int, default=20, metavar='N',
                    help='how many addresses to probe (default 20)')
    ap.add_argument('--for', dest='total', type=int, default=None, metavar='N',
                    help='how many addresses the real run will have, for the projection. Defaults '
                         'to the length of the list given')
    ap.add_argument('--attempts', type=int, default=3, metavar='N',
                    help='how many rungs of the settings ladder to try before giving up (default 3)')
    ap.add_argument('--quick', action='store_true',
                    help='a shorter ladder, for a first look rather than a decision')
    ap.add_argument('--delay', type=float, default=None, metavar='SECONDS',
                    help='probe with this pause before each fetch, so the projection includes it')
    ap.add_argument('--ignore-robots', dest='ignore_robots', action='store_true',
                    help='probe the addresses a host disallows, with the owner\'s permission')
    ap.add_argument('--json', action='store_true', help='print the whole calibration as JSON')
    a = ap.parse_args(argv)

    from .core import audit_many_async, set_page_delay, IGNORE_ROBOTS_MIN_DELAY

    urls = list(a.urls)
    if a.from_file:
        try:
            urls += _urls_from_file(a.from_file)
        except InputFileUnusable as e:
            ap.error(str(e))
    if a.demo:
        # only when nothing else was given, so --demo can never quietly replace a real list
        if urls:
            print('--demo ignored: addresses were given', file=sys.stderr)
        else:
            urls = [DEMO_URL]
            print('demo: reading %s, the author\'s own site. One address settles no setting; what it'
                  '\nshows is the shape of a reading. Give --from-file your own list to calibrate.'
                  % DEMO_URL, file=sys.stderr)
    if not urls:
        print('calibrate needs addresses: give some, --from-file PATH, or --demo', file=sys.stderr)
        return 2
    total = a.total or len(urls)
    sample = urls[:max(1, a.sample)]
    # An empty sample from a non-empty list would make every figure below a division by zero and the
    # recommendation a confident statement about nothing.
    assert sample, 'the sample is empty although the list is not'

    delay = a.delay
    if a.ignore_robots and (delay is None or delay < IGNORE_ROBOTS_MIN_DELAY):
        delay = IGNORE_ROBOTS_MIN_DELAY
    if delay:
        set_page_delay(delay)

    plan = calibrate_plan(sample, a.attempts, a.quick)
    print('langaccess calibrate: %d of %d addresses, %d setting%s to try'
          % (len(sample), len(urls), len(plan), '' if len(plan) == 1 else 's'), file=sys.stderr)
    if delay:
        print('  pausing %g s before each fetch, which the projection includes' % delay,
              file=sys.stderr)

    tried, chosen = [], None
    for timeout, conc in plan:
        t0 = time.time()
        try:
            results = asyncio.run(audit_many_async(
                sample, concurrency=conc, timeout=timeout, respect_robots=not a.ignore_robots))
        except BrowserUnavailable as e:
            print('no browser: %s' % e, file=sys.stderr)
            return 3
        el = time.time() - t0
        got = calibrate_reading(results)
        got.update({'timeout': timeout, 'concurrency': conc, 'seconds': round(el, 1),
                    'seconds_per_site': round(el / len(sample), 1)})
        tried.append(got)
        _print_calibration_rung(got)
        if got['accepted']:
            chosen = got
            break

    out = {'sample': len(sample), 'list': len(urls), 'for': total, 'delay': delay or 0,
           'attempts': tried, 'chosen': chosen}
    if chosen:
        hours = chosen['seconds_per_site'] * total / 3600.0
        out['projected_hours'] = round(hours, 1)
        out['command'] = ('langaccess --from-file YOUR_LIST --json --output out.jsonl '
                          '--store run.jsonl.gz --shared-browser --concurrency %d --timeout %d%s'
                          % (chosen['concurrency'], chosen['timeout'],
                             ' --delay %g' % delay if delay else ''))
    if a.json:
        print(json.dumps(out, ensure_ascii=False, indent=1))
        return 0 if chosen else 1

    print()
    if not chosen:
        print('No setting on the ladder read deeply enough on this machine.')
        print('The last attempt said: %s' % tried[-1]['why'])
        print('Raise --attempts, or give the run more clock by hand with a larger --timeout and a')
        print('smaller --concurrency. A machine that cannot clear the floor is not a machine to run')
        print('a thousand addresses on: the run would finish and the verdicts would not be usable.')
        return 1
    print('Settings for this machine: --concurrency %d --timeout %d%s'
          % (chosen['concurrency'], chosen['timeout'], ' --delay %g' % delay if delay else ''))
    print('  %.1f seconds per site here, so %d addresses take about %.1f hours.'
          % (chosen['seconds_per_site'], total, out['projected_hours']))
    print()
    print(out['command'])
    print()
    print('The probe readings were discarded. Run the whole list under the one setting above, so')
    print('that no two addresses in the run were read under different conditions.')
    return 0


def _print_calibration_rung(g):
    """One rung of the ladder, in the order a person should read it."""
    print('\n  --timeout %-4d --concurrency %d' % (g['timeout'], g['concurrency']), file=sys.stderr)
    print('    %5.1f s per site, %d of %d addresses produced a reading'
          % (g['seconds_per_site'], g['read'], g['sites']), file=sys.stderr)
    if not g['read']:
        print('    nothing was read, so there is no depth to judge', file=sys.stderr)
        return
    print('    clock ran out on   %d of %d' % (g['clock_exhausted'], g['read']), file=sys.stderr)
    print('    search sufficient  %d of %d  (over %.0f%% needed)'
          % (g['sufficient'], g['read'], 100.0 * (1 - (g['max_thin_share'] or 0.25))),
          file=sys.stderr)
    print('    median pages       %d  (floor %s)' % (g['median_pages'], g['min_median_pages']),
          file=sys.stderr)
    print('    %s' % ('ACCEPTED' if g['accepted'] else 'refused: ' + g['why']), file=sys.stderr)


def _main_demo(argv):
    """`langaccess demo`, the whole reading on four invented sites, with no browser and no network.

    A fresh install has nothing to read and the only address this package would fetch unasked
    belongs to its author, so the first thing a new user saw was somebody's real site and, in the
    printed evidence, somebody's real writing. These four sites are written for this purpose, one
    per class, and they ship inside the package as a stored capture: `demo` judges the stored pages
    exactly as `--rejudge` judges any capture, so what it prints is the instrument's own output and
    not a transcript of one.
    """
    ap = argparse.ArgumentParser(
        prog='langaccess demo',
        description='Judge four invented sites bundled with the package, one per class. No browser '
                    'is started and no address is fetched. For a real address, run '
                    '`langaccess <url>`.')
    ap.add_argument('--json', action='store_true', help='one JSON object per site, to stdout')
    a = ap.parse_args(argv)

    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'demo_capture.jsonl.gz')
    if not os.path.exists(path):
        print('the demo capture is missing from this installation: %s' % path, file=sys.stderr)
        return EXIT_NOTHING
    shown = 0
    with gzip.open(path, 'rt', encoding='utf-8') as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            why = rec.pop('demo_why', '')
            rec.pop('demo_name', None)
            r = _rejudge_one(rec)
            shown += 1
            if a.json:
                print(json.dumps(r.to_dict(), ensure_ascii=False))
                continue
            _print_human(r)
            if why:
                for chunk in _wrap_demo(why):
                    print('  %s' % chunk)
    if not shown:
        print('the demo capture holds no sites', file=sys.stderr)
        return EXIT_NOTHING
    if not a.json:
        print()
        print('  These four sites are invented and are judged from pages stored inside the '
              'package.')
        print('  Nothing was fetched. Run `langaccess <url>` to read a real address.')
    return EXIT_OK


def _rejudge_one(rec):
    """One stored record judged again, which is what `--rejudge` does for one address."""
    from .core import rejudge as _rj
    return _rj(rec)


def _wrap_demo(text, width=86):
    """The one-line reason a demo site is in the set, wrapped for a terminal."""
    out, line = [], ''
    for word in text.split():
        if len(line) + len(word) + 1 > width:
            out.append(line)
            line = word
        else:
            line = (line + ' ' + word).strip()
    if line:
        out.append(line)
    return out


SUBCOMMANDS = {'calibrate': _main_calibrate,
               'diff': _main_diff, 'review': _main_review, 'ingest': _main_ingest,
               'report': _main_report, 'retry': _main_retry,
               'depth': _main_depth, 'demo': _main_demo}


def main(argv=None):
    # A quote in Khmer, Arabic or Amharic cannot be written to a cp949 console, and the
    # UnicodeEncodeError that follows kills a run that had already done the expensive part.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding='utf-8', errors='replace')
        except Exception:
            pass

    argv = sys.argv[1:] if argv is None else list(argv)
    if argv and argv[0] in SUBCOMMANDS:
        return SUBCOMMANDS[argv[0]](argv[1:])

    # The description says what the tool records, not what it approves of. An earlier wording,
    # "genuine (not machine-translated)", read as a judgement about the site and contradicted the
    # Scope section, which says the package describes what a site provides and scores nothing.
    p = argparse.ArgumentParser(
        prog='langaccess',
        description='Read a website and record, for each language it offers, whether the text was '
                    'written by the site, produced by a translation widget, or absent.',
        epilog='Subcommands: diff, review, ingest, report and depth read files and reach '
               'no site; retry reads exactly the sites a clean browser could not, and calibrate '
               'reads a sample of your own list to measure the settings this machine needs. Run '
               '"langaccess diff --help" for any of them.')
    p.add_argument('urls', nargs='*', help='one or more URLs to audit')
    p.add_argument('--json', action='store_true', help='print one JSON object per line instead of '
                                                        'the human-readable summary')
    p.add_argument('--concurrency', type=int, default=1,
                   help='how many URLs to audit at once (default 1)')
    p.add_argument('--deep', action='store_true',
                   help="also try the language's own word paths (/korean, /espanol) and look again "
                        'at a page that came back empty. Slower, and finds more')
    p.add_argument('--no-escalate', dest='escalate', action='store_false',
                   help='do not keep reading when a site is about to be called english_only on a '
                        'thin search. Escalation is ON by default; this turns it off, which is how '
                        'a study measures what it costs and what it finds')
    p.add_argument('--timeout', type=float, default=None,
                   help='seconds to spend on one site before giving up on it')
    p.add_argument('--from-file', dest='from_file', metavar='PATH',
                   help='read URLs from a file, one per line, blank lines and # comments skipped. '
                        'Use - for standard input')
    p.add_argument('--output', metavar='PATH',
                   help='with --json, append each JSON line to this file as it is produced, so a '
                        'run that is killed keeps what it finished')
    p.add_argument('--resume', metavar='PATH',
                   help='skip the addresses already in this file, which is a --output or --store '
                        'file from a run that was interrupted. The count skipped and the count '
                        'left are printed. An address that came back unreachable counts as done; '
                        'use the retry subcommand for those')
    p.add_argument('--shared-browser', dest='shared_browser', action='store_true',
                   help='launch one browser for the whole run instead of one per site. Each site '
                        'still gets a browser context of its own, which is what keeps its cookies '
                        'and widget state out of the next one')
    p.add_argument('--block-private-hosts', dest='block_private_hosts', action='store_true',
                   help='refuse every request whose host resolves off the public internet. Costs a '
                        'DNS lookup per host; for a list of addresses somebody else supplied')
    p.add_argument('--max-pages', dest='max_pages', type=int, default=None, metavar='N',
                   help='how many pages to read per site before stopping (default 6). '
                        'Escalation may still read past this on a site about to be called '
                        'english_only on a thin search')
    p.add_argument('--delay', dest='delay', type=float, default=None, metavar='SECONDS',
                   help='wait this long before every page fetch. Paid out of the per-site clock, so raise --timeout with it. Forced to at least %g with --ignore-robots'
                        % IGNORE_ROBOTS_MIN_DELAY)
    p.add_argument('--min-median-pages', dest='min_median_pages', type=int, default=None,
                   metavar='N',
                   help='the run-level acceptance floor: how many pages the median site has to '
                        'read before this run is comparable with another (default 4). Whatever it is set to, the result records it')
    p.add_argument('--max-thin-share', dest='max_thin_share', type=float, default=None,
                   metavar='SHARE',
                   help='the run-level acceptance ceiling: the share of readings allowed to rest '
                        'on a search too thin to support an absence claim (default 0.25)')
    p.add_argument('--ignore-robots', dest='ignore_robots', action='store_true',
                   help='OVERRIDE: fetch addresses the host disallows in robots.txt. robots.txt is '
                        'read and obeyed by default; use this only where you have the site '
                        "owner's permission")
    p.add_argument('--store', metavar='PATH',
                   help='append one JSON line per site, holding the verdict, the evidence and the '
                        'HTML of every page read, so a reading can be re-checked after the site '
                        'changes. A path ending .gz is written compressed')
    p.add_argument('--rejudge', metavar='PATH',
                   help='judge a store file written by --store again, over the pages it holds, '
                        'without touching the network. Any URLs given select which records; with '
                        'none, every record in the file is re-judged. What a stored capture cannot '
                        'reproduce is listed on each result')
    p.add_argument('--explain', action='store_true',
                   help='print the working behind each verdict instead of the summary: the rules '
                        'that fired in the order they are applied, the evidence each one rests on '
                        'with its address and quoted words, the two axes per language, and what '
                        'the search was worth. Combines with --rejudge to explain a stored capture, '
                        'and with --json for the same arrangement as one JSON object per site')
    p.add_argument('--version', action='store_true', help='print the version and exit')
    args = p.parse_args(argv)

    if args.version:
        print(__version__)
        return 0

    urls = list(args.urls)
    if args.from_file:
        try:
            urls += _urls_from_file(args.from_file)
        except InputFileUnusable as e:
            # `parser.error`, so a path that does not exist answers exactly as a file holding no
            # addresses already did: one sentence on stderr and EXIT_USAGE. It used to answer with a
            # traceback and 1, which is the code reserved for this tool having crashed.
            p.error(str(e))

    # Before the rejudge branch, because that branch returns and the message belongs to every form of
    # the command. A `--rejudge --output` run with no `--json` wrote nothing and said nothing about
    # writing nothing, which is the same defect one branch further along.
    if args.output and not args.json:
        print('--output writes JSON lines and the output here is the human-readable summary, so '
              '--output is ignored. Add --json to write the file.', file=sys.stderr)

    if args.rejudge:
        # No browser, no fetch, no event loop: the pages are already in hand. A run over a whole
        # stored census takes seconds. For the same reason, a crawl setting on this flag is a
        # misunderstanding to answer rather than ignore: eleven flags were silently dropped
        # here, --store among them, and a user who asked for a store got no store and no word.
        _ignored = [(name, flag) for name, flag in (
            ('--store', args.store), ('--resume', args.resume), ('--deep', args.deep),
            ('--shared-browser', args.shared_browser),
            ('--block-private-hosts', args.block_private_hosts),
            ('--no-escalate', not args.escalate), ('--delay', args.delay),
            ('--min-median-pages', args.min_median_pages is not None),
            ('--max-thin-share', args.max_thin_share is not None),
            ('--concurrency', args.concurrency != 1), ('--timeout', args.timeout is not None),
            ('--max-pages', args.max_pages is not None)) if flag]
        if _ignored:
            p.error('%s cannot be combined with --rejudge: a re-judge opens no browser and '
                    'reads no clock, so these settings would change nothing. Run them on the '
                    'crawl that writes the store.' % ', '.join(n for n, _ in _ignored))
        sink = None
        if args.output and args.json:
            sink = (gzip.open(args.output, 'at', encoding='utf-8')
                    if str(args.output).endswith('.gz')
                    else open(args.output, 'a', encoding='utf-8'))
        try:
            # A path that is not a capture answered with a traceback ending inside `read_store`,
            # which is the same defect `--from-file` had. The three ways to get here are a mistyped
            # path, a file that holds something other than one JSON record per line, and a name
            # ending .gz on bytes that are not gzip; each is named, and none is a bug report.
            try:
                judged = rejudge_store(args.rejudge, urls or None)
            except FileNotFoundError:
                p.error('%s does not exist. --rejudge wants a capture file written by an earlier '
                        'run with --store.' % args.rejudge)
            except IsADirectoryError:
                p.error('%s is a directory. --rejudge wants one capture file written by an earlier '
                        'run with --store.' % args.rejudge)
            except (ValueError, OSError, EOFError):
                p.error('%s is not a capture this can read, or was cut off before its first '
                        'whole record. --rejudge wants a file written by an earlier run with '
                        '--store: one JSON record per line, optionally gzipped under a name '
                        'ending .gz.' % args.rejudge)
            except (KeyError, TypeError, AttributeError):
                p.error('%s parses as JSON but its records are not captures this can judge. '
                        '--rejudge wants a file written by an earlier run with --store, whose '
                        'records carry the pages that were read.' % args.rejudge)
            # JSON lines from somewhere else judge without raising, and every one of them comes back
            # `unreachable` with an empty address, which in a table counts as a site that could not
            # be read. A capture names the site on every row, so a file where nothing does is not
            # one. Records with no stored pages are left alone: a real capture holds those, for the
            # sites a run failed to read.
            if judged and not any(r.url for r in judged):
                p.error('%s holds %d JSON records and not one of them names a site, so it is not a '
                        'capture. Re-judging it would return a page of unreachable rows for sites '
                        'that were never audited.' % (args.rejudge, len(judged)))
            for r in judged:
                _emit(r, args.json, sink, args.explain)
        finally:
            if sink is not None:
                sink.close()
        return 0

    if not urls:
        p.error('no URLs to audit. Give one or more addresses on the command line, or read them '
                'from a file with --from-file PATH (or --from-file - for standard input).')

    # Every address is checked before a browser starts, and what fails is not audited. See
    # `_reject_what_is_not_an_address` for why a rejected input is not allowed to become a verdict.
    urls, rejected = _reject_what_is_not_an_address(urls)
    if rejected and not urls:
        print('langaccess audited nothing: all %d of the strings given are not addresses. No '
              'browser was started and no result was written.' % len(rejected), file=sys.stderr)
        return EXIT_INPUT_REJECTED

    # What a previous run of this list already finished. After the address check and before the
    # browser, so a rejected string is still reported as rejected on a resumed run.
    if args.resume:
        try:
            done, lines, old = _addresses_already_done(args.resume)
        except FileNotFoundError:
            p.error('%s does not exist. --resume wants the --output or --store file of the run '
                    'being continued.' % args.resume)
        except (ValueError, OSError):
            p.error('%s could not be read as a run file. --resume wants the --output or --store '
                    'file of the run being continued.' % args.resume)
        keep = [u for u in urls if _resume_key(u) not in done]
        skipped = len(urls) - len(keep)
        print('--resume read %d rows from %s and skipped %d of the %d addresses given; %d left'
              % (lines, args.resume, skipped, len(urls), len(keep)), file=sys.stderr)
        if old:
            print('  %d of those rows predate the requested_url field and were matched on the '
                  'address the browser ended at, so a site that redirected may be read again'
                  % old, file=sys.stderr)
        if not keep:
            print('  every address given is already in that file, so there is nothing to do.',
                  file=sys.stderr)
            return EXIT_OK
        urls = keep

    # The pause between fetches, and the floor that applies when the run has been told to fetch what
    # a host disallows. Overriding robots.txt and hammering the host are separate acts; a study can
    # have a defence for the first and none for the second, so the second is not left to be forgotten.
    delay = args.delay
    if args.ignore_robots and (delay is None or delay < IGNORE_ROBOTS_MIN_DELAY):
        if args.delay is not None:
            print('--delay %g raised to %g: --ignore-robots sets a floor'
                  % (args.delay, IGNORE_ROBOTS_MIN_DELAY), file=sys.stderr)
        delay = IGNORE_ROBOTS_MIN_DELAY
    if delay:
        set_page_delay(delay)
        # The pause is paid out of the site's own clock. Said here rather than left to be found in
        # a run full of clock_exhausted readings, which is how a run comes back fast and wrong.
        if args.timeout is not None and args.timeout < delay * 20:
            print('--delay %g against --timeout %g: the pause is paid from the per-site clock, so '
                  'this run may exhaust it before the reading is deep enough to compare'
                  % (delay, args.timeout), file=sys.stderr)
    if args.min_median_pages is not None or args.max_thin_share is not None:
        was = set_acceptance(args.min_median_pages, args.max_thin_share)
        print('run acceptance thresholds moved from %s to (%s, %s); every result records the '
              'thresholds it was judged against' % (was, args.min_median_pages, args.max_thin_share),
              file=sys.stderr)

    broken, printed = asyncio.run(
        _run(urls, args.concurrency, args.json, args.deep, args.timeout, args.output,
             args.shared_browser, args.block_private_hosts, args.ignore_robots,
             args.store, args.escalate, args.explain, args.max_pages))
    if broken is None:
        if rejected:
            # The summary a person reads after a long run, carrying the denominator: a
            # run over 1,000 lines that audited 996 sites has to say so where the count can be seen,
            # not only in four lines that scrolled past an hour ago.
            print('\nlangaccess audited %d of the %d strings given; %d were not addresses, are named '
                  'above, and are in no output.'
                  % (len(urls), len(urls) + len(rejected), len(rejected)), file=sys.stderr)
            return EXIT_INPUT_REJECTED
        return EXIT_OK
    # Once, to stderr, so that it stays readable beside a thousand JSON lines on stdout and does not
    # land in the file `--output` is writing. What a reader has to know is not only that the browser
    # is missing but that the addresses below the failure were never opened and are not in the
    # output at all.
    left = len(urls) - printed
    print('\nlangaccess stopped: %s' % broken, file=sys.stderr)
    print('%d of %d addresses were read; the remaining %d were not opened and no result was written '
          'for them. Nothing here says anything about those sites.' % (printed, len(urls), left),
          file=sys.stderr)
    return EXIT_STORE_FAILED if isinstance(broken, StoreWriteFailed) else EXIT_NO_BROWSER


if __name__ == '__main__':
    sys.exit(main())
