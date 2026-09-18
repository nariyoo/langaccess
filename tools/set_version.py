# -*- coding: utf-8 -*-
"""Move the version everywhere it is written down, or say where it is out of step.

`pyproject.toml` reads the version from one place - `__version__` in `src/langaccess/__init__.py` -
so an installed copy and the source tree can never disagree about which build produced a reading.
But the number is also QUOTED in eight other files, as a statement about which instrument a figure
belongs to, and those do not follow automatically:

    CITATION.cff          the version a citation names
    README.md             the suggested methods sentence, and the comparability note
    LIMITATIONS.md        the build every figure in it was measured on
    CONTRIBUTING.md       the CI test counts, which go stale on any test change
    tests/test_cli.py     asserts the version the CLI prints
    tests/test_review.py  a fixture's tool_version

Run with no argument to REPORT what each file says. Run with a version to rewrite them. Nothing is
written unless every file is found and every occurrence is unambiguous, so a partial rewrite - the
state where the package says one version and the citation says another - cannot happen.

    python tools/set_version.py            # report
    python tools/set_version.py 0.2.0      # rewrite
"""
import io, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)

SOURCE = 'src/langaccess/__init__.py'
SOURCE_RX = re.compile(r'^(__version__\s*=\s*)"([^"]+)"', re.M)

# file -> (pattern, what it is for). Group 1 is kept, group 2 is the version.
QUOTED = [
    ('CITATION.cff', re.compile(r'^(version:\s*)(\S+)', re.M), 'the version a citation names'),
    ('tests/test_cli.py', re.compile(r"(assert ')(\d+\.\d+\.\d+)(?=' in out\.stdout)"),
     'the version the CLI prints'),
    ('tests/test_review.py', re.compile(r"('tool_version':\s*')(\d+\.\d+\.\d+)"),
     "a fixture's tool_version"),
]

# Files where the version appears in prose, several times, and a blind rewrite would be wrong:
# reported, never rewritten.
PROSE = ['README.md', 'LIMITATIONS.md', 'docs/USAGE.md', 'pyproject.toml']


def current():
    s = io.open(SOURCE, encoding='utf-8').read()
    m = SOURCE_RX.search(s)
    if not m:
        raise SystemExit('no __version__ in %s' % SOURCE)
    return m.group(2)


def report(now):
    print('the package says: %s   (%s)' % (now, SOURCE))
    print()
    print('%-24s %-10s %s' % ('file', 'says', 'what it is for'))
    for path, rx, why in QUOTED:
        s = io.open(path, encoding='utf-8').read()
        found = [m.group(2) for m in rx.finditer(s)]
        mark = '' if all(v == now for v in found) else '   <- out of step'
        print('%-24s %-10s %s%s' % (path, ','.join(found) or '(none)', why, mark))
    print()
    print('mentioned in prose, rewritten by hand:')
    for path in PROSE:
        s = io.open(path, encoding='utf-8').read()
        n = len(re.findall(re.escape(now), s))
        print('   %-22s %d occurrence(s) of %s' % (path, n, now))
    print()
    print('and one count that is not a version:')
    c = io.open('CONTRIBUTING.md', encoding='utf-8').read()
    m = re.search(r'\*\*(\d+) passed, (\d+) skipped, (\d+)\s*\n?deselected\*\*', c)
    print('   CONTRIBUTING.md claims %s' % (', '.join(m.groups()) if m else '(not found)'))
    print('   run `pytest -q` and correct it: the file says a count that no longer matches is a '
          'bug in the file')


def rewrite(now, new):
    edits = []
    s = io.open(SOURCE, encoding='utf-8').read()
    if SOURCE_RX.search(s).group(2) != new:
        edits.append((SOURCE, SOURCE_RX.sub(lambda m: '%s"%s"' % (m.group(1), new), s, count=1)))
    for path, rx, _why in QUOTED:
        s = io.open(path, encoding='utf-8').read()
        if not rx.search(s):
            raise SystemExit('%s: the version pattern found nothing; check it by hand' % path)
        edits.append((path, rx.sub(lambda m: '%s%s' % (m.group(1), new), s)))
    for path, body in edits:
        io.open(path, 'w', encoding='utf-8').write(body)
        print('   %s -> %s' % (path, new))
    print()
    print('rewritten: %s -> %s' % (now, new))
    print('BY HAND, because the version is prose in these:')
    for path in PROSE:
        print('   %s' % path)
    print('and re-record the CI counts in CONTRIBUTING.md from a real run.')


if __name__ == '__main__':
    now = current()
    if len(sys.argv) < 2:
        report(now)
    else:
        rewrite(now, sys.argv[1])
