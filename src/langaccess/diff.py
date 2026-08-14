# -*- coding: utf-8 -*-
"""What moved between two runs of langaccess over one set of addresses.

    langaccess diff run_a.jsonl run_b.jsonl
    langaccess diff --json run_a.jsonl run_b.jsonl

    from langaccess import diff_runs
    d = diff_runs('run_a.jsonl', 'run_b.jsonl')
    d['moved']                      # every site that changed, as data
    d['unreachable']['toward']      # the sites that stopped being readable

Every measurement this package is used for compares two runs over the same addresses and reports
what moved: a rule change against the run before it, a deep pass against a shallow one, one week
against the next. That comparison had been written by hand each time, and two properties of it are
not a caller's business to remember.

MOVEMENT TOWARD `unreachable` IS REPORTED SEPARATELY AND FIRST, AND IS NEVER NETTED. A change that
makes sites unreadable and a change that finds more Spanish both show up as movement, and a total
that adds them reports the first as the second. So the sites that stopped being readable are their
own block, at the top, named one by one; the verdict, language and authorship tallies below are
computed over the sites READABLE IN BOTH runs and say so in their own denominator; and nothing here
ever emits a single net figure.
Recovery, a site unreachable in the first run and readable in the second, is held out of those
tallies for the same reason in the other direction: a site that was not read before has not gained
a language, and counting it as a gain would inflate exactly the number a favourable run wants.

A SITE IN ONE RUN AND NOT THE OTHER IS COUNTED AND NAMED. Comparing the intersection and calling it
a comparison is this project's single most frequent bug, six distinct instances of it, and it is
what turns "the new rules read 40 more sites as multilingual" into a sentence about a run that lost
200 addresses. `only_in_a` and `only_in_b` hold every such address, the human summary prints the
count before it prints anything else, and no code path here silently drops one.

WHAT A RUN FILE IS. One JSON object per line, as `--json --output` and `--store` both write. A path
ending `.gz` is read compressed. Both are read through `read_store`, so a capture and a plain result
file are the same input here. A site written twice in one file is the store appending, and the LAST
row wins, which is what `_stored_record` does for the same reason; how many rows collapsed that way
is reported rather than hidden.
"""
import collections

from .core import read_store


UNREACHABLE = 'unreachable'


def _key(url):
    """The comparable form of an address, which is what core compares two stored URLs on."""
    return str(url or '').rstrip('/').lower()


def _index(source):
    """One run as {key: record}, plus what the file held.

    `source` is a path to a JSON-lines file, or an iterable of records already in hand, so a caller
    that has read the run itself does not write it back out to compare it.
    """
    path = ''
    if isinstance(source, (str, bytes)) or hasattr(source, '__fspath__'):
        path, records = str(source), read_store(source)
    else:
        records = source
    sites, rows, blank = {}, 0, 0
    for rec in records:
        rows += 1
        k = _key(rec.get('url', ''))
        if not k:
            # a row with no address cannot be compared with anything, and it is counted here rather
            # than dropped, for the same reason the only_in_* lists exist
            blank += 1
            continue
        sites[k] = rec
    return {'path': path, 'rows': rows, 'sites': sites, 'blank_url_rows': blank,
            'duplicate_rows': rows - blank - len(sites)}


def _verdict(rec):
    return str(rec.get('verdict', '') or '')


def _languages(rec):
    """The languages a reading counted. English is among them, as the reading recorded it."""
    return [str(x) for x in (rec.get('languages') or [])]


def _movement(a, b):
    """What changed for one site read in both runs, or None when nothing did."""
    va, vb = _verdict(a), _verdict(b)
    la, lb = set(_languages(a)), set(_languages(b))
    # a capture written under the old top-level 'provenance' key is read here too; the alias
    # mirrors core._STORED_ALIAS, which until now covered only evidence-level reads
    pa = str(a.get('authorship', a.get('provenance', '')) or '')
    pb = str(b.get('authorship', b.get('provenance', '')) or '')
    gained, lost = sorted(lb - la), sorted(la - lb)
    if va == vb and not gained and not lost and pa == pb:
        return None
    return {
        'url': b.get('url') or a.get('url') or '',
        'verdict': {'a': va, 'b': vb},
        'languages_gained': gained,
        'languages_lost': lost,
        'authorship': {'a': pa, 'b': pb},
        'toward_unreachable': va != UNREACHABLE and vb == UNREACHABLE,
        'away_from_unreachable': va == UNREACHABLE and vb != UNREACHABLE,
    }


def diff_runs(a, b):
    """Compare two runs over one frame and report what moved.

    `a` and `b` are paths to JSON-lines run files, or iterables of records. The dict returned is the
    machine-readable form; `diff_text` renders the same dict for a person. See this module's
    docstring for the two rules the shape enforces: the movement toward `unreachable` is its own
    block and is never netted against the rest, and an address present in one run and absent from
    the other is counted and named.
    """
    ia, ib = _index(a), _index(b)
    keys_a, keys_b = set(ia['sites']), set(ib['sites'])
    both = keys_a & keys_b

    moved, toward, away = [], [], []
    verdicts = collections.Counter()
    gained_langs, lost_langs = collections.Counter(), collections.Counter()
    authorship = collections.Counter()
    compared = unchanged = unreachable_both = 0

    for k in sorted(both):
        ra, rb = ia['sites'][k], ib['sites'][k]
        va, vb = _verdict(ra), _verdict(rb)
        m = _movement(ra, rb)
        if m is not None:
            moved.append(m)
        # The three buckets that are not a comparison of provision. A site that stopped being
        # readable, a site that started being readable, and a site neither run could read: none of
        # the three can enter a verdict, language or authorship count without saying something the
        # readings do not support.
        if va != UNREACHABLE and vb == UNREACHABLE:
            toward.append(m)
            continue
        if va == UNREACHABLE and vb != UNREACHABLE:
            away.append(m)
            continue
        if va == UNREACHABLE and vb == UNREACHABLE:
            unreachable_both += 1
            continue
        compared += 1
        if m is None:
            unchanged += 1
            continue
        if va != vb:
            verdicts['%s -> %s' % (va, vb)] += 1
        for lg in m['languages_gained']:
            gained_langs[lg] += 1
        for lg in m['languages_lost']:
            lost_langs[lg] += 1
        if m['authorship']['a'] != m['authorship']['b']:
            authorship['%s -> %s' % (m['authorship']['a'], m['authorship']['b'])] += 1

    return {
        'runs': {'a': {k: v for k, v in ia.items() if k != 'sites'},
                 'b': {k: v for k, v in ib.items() if k != 'sites'}},
        'sites': {'a': len(keys_a), 'b': len(keys_b), 'both': len(both),
                  'only_in_a': sorted(ia['sites'][k].get('url') or k for k in keys_a - keys_b),
                  'only_in_b': sorted(ib['sites'][k].get('url') or k for k in keys_b - keys_a)},
        # first in the dict as it is first in the summary, and held out of every tally below
        'unreachable': {'toward': toward, 'away': away},
        # the denominator of everything under it: sites READ in both runs, so a site that stopped
        # being readable cannot enter a verdict count as an improvement or as anything else. The
        # four counts account for every address in both runs:
        # both == compared + toward + away + unreachable_in_both
        'compared': compared,
        'unreachable_in_both': unreachable_both,
        'verdicts': dict(verdicts),
        'languages': {'gained': dict(gained_langs), 'lost': dict(lost_langs)},
        'authorship': dict(authorship),
        'moved': moved,
        'unchanged': unchanged,
    }


def _sites(n):
    """`1 site`, `4 sites`. A count a person reads should not read as a template."""
    return '%d site%s' % (n, '' if n == 1 else 's')


def _names(urls, cap=20):
    """Every address, or the first `cap` of them and how many were not printed."""
    out = ['    %s' % u for u in urls[:cap]]
    if len(urls) > cap:
        out.append('    and %d more, all of them in the JSON form' % (len(urls) - cap))
    return out


def diff_text(d):
    """The comparison as lines a person reads, in the order the discipline requires."""
    out = []
    add = out.append
    add('langaccess diff')
    for side in ('a', 'b'):
        run = d['runs'][side]
        extra = ''
        if run['duplicate_rows']:
            extra += '   %d rows collapsed onto an address written twice' % run['duplicate_rows']
        if run['blank_url_rows']:
            extra += '   %d rows with no address' % run['blank_url_rows']
        add('  %s  %s   %s from %d rows%s'
            % (side, run['path'] or '(records)', _sites(d['sites'][side]), run['rows'], extra))
    add('  in both %d   only in a %d   only in b %d'
        % (d['sites']['both'], len(d['sites']['only_in_a']), len(d['sites']['only_in_b'])))

    # First, on its own, and never inside a total. A run that made 40 sites unreadable and found
    # Spanish on 12 has to say the first thing before the second.
    add('')
    add('toward unreachable   %s' % _sites(len(d['unreachable']['toward'])))
    for m in d['unreachable']['toward']:
        add('    %s   %s -> %s' % (m['url'], m['verdict']['a'], m['verdict']['b']))
    add('away from unreachable   %s' % _sites(len(d['unreachable']['away'])))
    for m in d['unreachable']['away']:
        add('    %s   %s -> %s' % (m['url'], m['verdict']['a'], m['verdict']['b']))
    add('  unreadable in both runs   %s' % _sites(d['unreachable_in_both']))
    add('  none of the three enters the counts below, in either direction')

    if d['sites']['only_in_a'] or d['sites']['only_in_b']:
        add('')
        add('only in a   %s' % _sites(len(d['sites']['only_in_a'])))
        out.extend(_names(d['sites']['only_in_a']))
        add('only in b   %s' % _sites(len(d['sites']['only_in_b'])))
        out.extend(_names(d['sites']['only_in_b']))
        add('  a comparison over the addresses in both runs says nothing about these')

    add('')
    add('over the %s read in both runs' % _sites(d['compared']))
    add('  verdict changes   %d' % sum(d['verdicts'].values()))
    for pair, n in sorted(d['verdicts'].items(), key=lambda kv: (-kv[1], kv[0])):
        add('    %-46s %d' % (pair, n))
    add('  languages gained  %s'
        % (', '.join('%s %d' % (k, v) for k, v in sorted(d['languages']['gained'].items(),
                                                         key=lambda kv: (-kv[1], kv[0]))) or '-'))
    add('  languages lost    %s'
        % (', '.join('%s %d' % (k, v) for k, v in sorted(d['languages']['lost'].items(),
                                                         key=lambda kv: (-kv[1], kv[0]))) or '-'))
    add('  authorship changes   %d' % sum(d['authorship'].values()))
    for pair, n in sorted(d['authorship'].items(), key=lambda kv: (-kv[1], kv[0])):
        add('    %-46s %d' % (pair, n))
    add('  unchanged on all three axes   %d' % d['unchanged'])
    return '\n'.join(out)
