# -*- coding: utf-8 -*-
"""Tests for the command line, with the audit itself replaced by a stub.

Nothing here launches a browser or touches the network. What is being tested is the part of a batch
run that used to lose work: one site raising an exception took every result computed so far down
with it, and nothing was printed until the last site finished.
"""
import json

import pytest

from langaccess import cli as CLI
from langaccess import core as LA
from langaccess.core import BrowserUnavailable, Result


def _stub(**by_url):
    """An audit_async that answers from a table and raises for the URLs mapped to an exception."""
    async def fake(u, deep=False, timeout=None):
        answer = by_url.get(u, 'ok')
        if isinstance(answer, Exception):
            raise answer
        return Result(url=u, verdict='english_only', note=answer)
    return fake


def test_json_output_is_one_parseable_line_per_url(monkeypatch, capsys):
    monkeypatch.setattr(CLI, 'audit_async', _stub())
    assert CLI.main(['--json', 'x.org']) == 0
    lines = [l for l in capsys.readouterr().out.splitlines() if l.strip()]
    assert len(lines) == 1
    got = json.loads(lines[0])
    assert got['url'] == 'x.org' and got['verdict'] == 'english_only'
    assert 'audited_at' in got and 'tool_version' in got


def test_one_site_that_raises_does_not_take_the_batch_with_it(monkeypatch, capsys):
    """Before this, any exception other than a timeout went through gather and killed the run, so a
    thousand-site batch could lose nine hundred finished results to the last site's crash.

    The raised error is a page crash and not a missing browser, and that difference decides
    the handling: this one is a property of the site, so it is a Result and the run continues.
    The other is a property of the machine and stops the run, which the four cases below hold.
    """
    monkeypatch.setattr(CLI, 'audit_async', _stub(**{'bad.org': RuntimeError('the page crashed')}))
    assert CLI.main(['--json', 'good.org', 'bad.org', 'also-good.org']) == 0
    lines = [json.loads(l) for l in capsys.readouterr().out.splitlines() if l.strip()]
    assert [r['url'] for r in lines] == ['good.org', 'bad.org', 'also-good.org']
    assert lines[1]['verdict'] == 'unreachable'
    assert 'RuntimeError' in lines[1]['note'] and 'the page crashed' in lines[1]['note']


# ------------------------------------------------------------ a machine with no browser
#
# Found on 2026-08-03 by a clean-install verification, on a machine with neither a Playwright browser
# nor Chrome. `audit()` raised the right error and said the right thing; the command line caught it
# per site, printed it inside the result block, recorded `verdict unreachable`, and exited 0. On a
# `--from-file` run over a thousand addresses every row would have read `unreachable` and the process
# would have reported success over a thousand sites nobody had opened. Reporting an empty result as
# a completed one is this project's recurring shape, on its fifth appearance here.


def _no_browser(*urls):
    """An audit_async that fails the way a machine with no browser fails: on every address."""
    async def fake(u, deep=False, timeout=None):
        if not urls or u in urls:
            raise BrowserUnavailable(
                'langaccess needs a browser and Playwright has none installed. Run:\n'
                '    python -m playwright install chromium')
        return Result(url=u, verdict='english_only')
    return fake


def test_a_missing_browser_exits_nonzero_and_writes_no_result(monkeypatch, capsys):
    """The defect itself. No row may claim a site was checked when no browser was ever started."""
    monkeypatch.setattr(CLI, 'audit_async', _no_browser())
    assert CLI.main(['--json', 'a.org', 'b.org', 'c.org']) == CLI.EXIT_NO_BROWSER
    got = capsys.readouterr()
    assert [l for l in got.out.splitlines() if l.strip()] == [], (
        'a site that was never opened must not appear in the output at all')
    assert 'unreachable' not in got.out
    assert 'playwright install chromium' in got.err


def test_the_missing_browser_is_reported_once_and_not_once_per_address(monkeypatch, capsys):
    """The sentence a person acts on has to be findable. Printed once, on stderr, and the count of
    what was not opened printed with it."""
    monkeypatch.setattr(CLI, 'audit_async', _no_browser())
    urls = ['s%d.org' % i for i in range(40)]
    assert CLI.main(['--json', '--concurrency', '4'] + urls) == CLI.EXIT_NO_BROWSER
    err = capsys.readouterr().err
    assert err.count('playwright install chromium') == 1
    assert '0 of 40 addresses were read' in err


def test_the_results_taken_before_the_browser_died_are_kept(monkeypatch, capsys, tmp_path):
    """A driver that dies part way through must not cost the reading already taken, and must not
    turn the addresses after it into rows either."""
    out = tmp_path / 'out.jsonl'
    monkeypatch.setattr(CLI, 'audit_async', _no_browser('c.org', 'd.org'))
    code = CLI.main(['--json', '--output', str(out), '--concurrency', '1',
                     'a.org', 'b.org', 'c.org', 'd.org'])
    assert code == CLI.EXIT_NO_BROWSER
    lines = [json.loads(l) for l in capsys.readouterr().out.splitlines() if l.strip()]
    assert [r['url'] for r in lines] == ['a.org', 'b.org']
    written = [json.loads(l) for l in out.read_text(encoding='utf-8').splitlines() if l.strip()]
    assert [r['url'] for r in written] == ['a.org', 'b.org'], (
        'the file --output writes is what a killed run keeps, so a site never opened cannot be in it')


def test_the_shared_browser_path_reports_a_missing_browser_the_same_way(monkeypatch, capsys):
    """`audit_many_async` launches before it reads anything, so the failure arrives from there with
    nothing read. It has to answer with the same exit code and the same one sentence."""
    async def fake_many(urls, concurrency=4, deep=False, timeout=None, on_result=None, **kw):
        raise BrowserUnavailable('langaccess needs a browser and Playwright has none installed. '
                                 'Run: python -m playwright install chromium')

    monkeypatch.setattr(CLI, 'audit_many_async', fake_many)
    assert CLI.main(['--json', '--shared-browser', 'a.org', 'b.org']) == CLI.EXIT_NO_BROWSER
    got = capsys.readouterr()
    assert [l for l in got.out.splitlines() if l.strip()] == []
    assert got.err.count('playwright install chromium') == 1


def test_the_three_exit_codes_are_distinct_and_nothing_takes_argparse_s(monkeypatch):
    """A machine that cannot run a browser and a command typed wrong must not answer the same."""
    assert CLI.EXIT_OK == 0
    assert CLI.EXIT_USAGE == 2, 'argparse exits 2 on a bad command line and this names that'
    assert CLI.EXIT_NO_BROWSER not in (CLI.EXIT_OK, CLI.EXIT_USAGE, 1)


def test_results_are_printed_in_the_order_the_urls_were_given(monkeypatch, capsys):
    """The audits finish in whatever order they finish in; the output does not depend on that."""
    import asyncio

    async def fake(u, deep=False, timeout=None):
        await asyncio.sleep({'a.org': 0.05, 'b.org': 0.01, 'c.org': 0.03}[u])
        return Result(url=u, verdict='english_only')

    monkeypatch.setattr(CLI, 'audit_async', fake)
    CLI.main(['--json', '--concurrency', '3', 'a.org', 'b.org', 'c.org'])
    lines = [json.loads(l) for l in capsys.readouterr().out.splitlines() if l.strip()]
    assert [r['url'] for r in lines] == ['a.org', 'b.org', 'c.org']


def test_from_file_reads_the_urls(monkeypatch, capsys, tmp_path):
    f = tmp_path / 'sites.txt'
    f.write_text('# a comment\nfirst.org\n\n  second.org  \n', encoding='utf-8')
    monkeypatch.setattr(CLI, 'audit_async', _stub())
    assert CLI.main(['--json', '--from-file', str(f)]) == 0
    lines = [json.loads(l) for l in capsys.readouterr().out.splitlines() if l.strip()]
    assert [r['url'] for r in lines] == ['first.org', 'second.org']


def test_output_file_keeps_what_a_killed_run_finished(monkeypatch, capsys, tmp_path):
    out = tmp_path / 'out.jsonl'
    monkeypatch.setattr(CLI, 'audit_async', _stub())
    CLI.main(['--json', '--output', str(out), 'one.org', 'two.org'])
    written = [json.loads(l) for l in out.read_text(encoding='utf-8').splitlines() if l.strip()]
    assert [r['url'] for r in written] == ['one.org', 'two.org']


def test_version_prints_the_version(capsys):
    from langaccess import __version__
    assert CLI.main(['--version']) == 0
    assert capsys.readouterr().out.strip() == __version__


def test_no_urls_is_an_error(monkeypatch):
    monkeypatch.setattr(CLI, 'audit_async', _stub())
    with pytest.raises(SystemExit):
        CLI.main(['--json'])


def test_shared_browser_routes_to_the_batch_function(monkeypatch, capsys):
    """With the flag the run goes through audit_many_async, and the output is still one line per
    address in the order the addresses were given."""
    seen = {}

    async def fake_many(urls, concurrency=4, deep=False, timeout=None, on_result=None, **kw):
        seen.update(urls=list(urls), concurrency=concurrency, deep=deep, timeout=timeout, kw=kw)
        out = [Result(url=u, verdict='english_only') for u in seen['urls']]
        for i, r in enumerate(out):
            if on_result is not None:
                on_result(i, r)
        return out

    def never(*a, **k):
        raise AssertionError('the per-site path should not run with --shared-browser')

    monkeypatch.setattr(CLI, 'audit_many_async', fake_many)
    monkeypatch.setattr(CLI, 'audit_async', never)
    assert CLI.main(['--json', '--shared-browser', '--concurrency', '3', '--deep',
                     'a.org', 'b.org']) == 0
    lines = [json.loads(l) for l in capsys.readouterr().out.splitlines() if l.strip()]
    assert [r['url'] for r in lines] == ['a.org', 'b.org']
    assert seen['urls'] == ['a.org', 'b.org']
    assert seen['concurrency'] == 3 and seen['deep'] is True
    assert 'block_private_hosts' not in seen['kw']


def test_shared_browser_passes_the_private_host_guard_on(monkeypatch, capsys):
    seen = {}

    async def fake_many(urls, concurrency=4, deep=False, timeout=None, on_result=None, **kw):
        seen.update(kw)
        return [Result(url=u, verdict='english_only') for u in urls]

    monkeypatch.setattr(CLI, 'audit_many_async', fake_many)
    assert CLI.main(['--json', '--shared-browser', '--block-private-hosts', 'a.org']) == 0
    assert seen == {'block_private_hosts': True}


def test_block_private_hosts_reaches_the_audit(monkeypatch, capsys):
    seen = {}

    async def fake(u, deep=False, timeout=None, block_private_hosts=False):
        seen[u] = block_private_hosts
        return Result(url=u, verdict='english_only')

    monkeypatch.setattr(CLI, 'audit_async', fake)
    assert CLI.main(['--json', '--block-private-hosts', 'x.org']) == 0
    assert seen == {'x.org': True}


def test_the_private_host_guard_is_not_passed_when_it_was_not_asked_for(monkeypatch, capsys):
    """An ordinary research run calls audit_async with exactly the arguments it always did, which
    is why this stub takes no block_private_hosts at all."""
    monkeypatch.setattr(CLI, 'audit_async', _stub())
    assert CLI.main(['--json', 'x.org']) == 0
    lines = [json.loads(l) for l in capsys.readouterr().out.splitlines() if l.strip()]
    assert lines[0]['verdict'] == 'english_only'


def test_the_human_summary_prints_a_note_on_a_site_that_was_read(capsys):
    """'locale route returned English' is the sentence behind the verdict on a site with a widget
    that translates nothing, and it was written to the JSON and nowhere a person could see it."""
    CLI._print_human(Result(url='https://x.org/', verdict='english_only',
                            note='locale route returned English'))
    out = capsys.readouterr().out
    assert 'locale route returned English' in out and 'english_only' in out


def test_the_human_summary_prints_the_two_axes_the_verdict_was_read_off(capsys):
    """A verdict on its own is a conclusion with its working thrown away, and the per-language rows
    are where a site with authored Spanish and a widget-produced Vietnamese shows both."""
    CLI._print_human(Result(
        url='https://x.org/', verdict='true_multilingual', languages=['Spanish'],
        machine_translation='Google Translate', authorship='authored', sufficiency=2,
        by_language={'Spanish': {'authorship': 'authored', 'sufficiency': 2},
                     'Vietnamese': {'authorship': 'client_widget', 'sufficiency': 0}}))
    out = capsys.readouterr().out
    assert 'authorship authored' in out
    assert 'sufficiency 2 notice' in out
    assert 'Vietnamese' in out and 'client_widget' in out


def test_the_json_line_carries_the_two_axes(monkeypatch, capsys):
    """The JSON is what a census run reads, so the axes have to be in it and not only on screen."""
    async def fake(u, deep=False, timeout=None):
        return Result(url=u, verdict='true_multilingual', languages=['Spanish'],
                      authorship='authored', sufficiency=3,
                      by_language={'Spanish': {'authorship': 'authored', 'sufficiency': 3}})

    monkeypatch.setattr(CLI, 'audit_async', fake)
    assert CLI.main(['--json', 'x.org']) == 0
    got = json.loads([l for l in capsys.readouterr().out.splitlines() if l.strip()][0])
    assert got['authorship'] == 'authored' and got['sufficiency'] == 3
    assert got['by_language'] == {'Spanish': {'authorship': 'authored', 'sufficiency': 3}}


def test_the_module_form_reaches_the_same_entry_point():
    """python -m langaccess and the langaccess script are one command line, not two.

    The console script lands in a virtual environment's Scripts directory, which on Windows is not
    on PATH unless the environment is activated, so a first run there fails on a missing command
    rather than on anything about the package. This asserts the module form exists and dispatches
    to cli.main, and it runs the real interpreter because importing __main__ in-process would
    not test the thing that breaks.
    """
    import subprocess
    import sys

    from conftest import cli_argv, cli_env

    env = cli_env()
    out = subprocess.run(cli_argv() + ['--version'],
                         capture_output=True, text=True, env=env)
    assert out.returncode == 0, out.stderr
    direct = subprocess.run([sys.executable, '-c',
                             'import sys; from langaccess.cli import main;'
                             " sys.argv=['langaccess','--version'];"
                             ' sys.exit(main())'], capture_output=True, text=True, env=env)
    assert out.stdout == direct.stdout
    assert '0.2.0' in out.stdout


# ------------------------------------------------------------ --strict, the degraded run
#
# A dead driver part way through a batch writes honest rows saying the sites were not read, and the
# process exits 0. `capture_acceptance` already answers whether a finished run is deep enough to be
# compared with another and already warns when it is not, and a warning on stderr is what a
# scheduled job's log buries. `--strict` is the exit code for both, asked for explicitly, with the
# run itself unchanged: everything it writes is still written and only the code moves.


def _reading_stub(quality, note=''):
    """An audit_async that answers every address with one read_quality and one note."""
    async def fake(u, deep=False, timeout=None):
        return Result(url=u, requested_url=u, verdict='english_only', note=note,
                      pages_read=int(quality.get('pages_read') or 0),
                      read_quality=dict(quality))
    return fake


_DEEP = {'pages_read': 6, 'sufficient': True}
_THIN = {'pages_read': 1, 'sufficient': False}


def test_a_run_deep_enough_to_compare_exits_zero_under_strict(monkeypatch, capsys):
    """The flag is not a way of failing every run. A run `capture_acceptance` accepts exits 0 with
    the flag and without it."""
    monkeypatch.setattr(CLI, 'audit_async', _reading_stub(_DEEP))
    urls = ['s%d.org' % i for i in range(5)]
    assert CLI.main(['--json', '--strict'] + urls) == CLI.EXIT_OK
    capsys.readouterr()
    assert CLI.main(['--json'] + urls) == CLI.EXIT_OK


def test_a_run_capture_acceptance_refuses_exits_nine_only_when_strict_was_asked_for(
        monkeypatch, capsys):
    """The defect. The same five sites, read one page each on a search too thin to support an
    absence claim, exit 0 by default, which is what put a degraded reading into a pipeline as a
    success."""
    monkeypatch.setattr(CLI, 'audit_async', _reading_stub(_THIN))
    urls = ['s%d.org' % i for i in range(5)]
    assert CLI.main(['--json'] + urls) == CLI.EXIT_OK, 'the default may not move'
    capsys.readouterr()
    assert CLI.main(['--json', '--strict'] + urls) == CLI.EXIT_DEGRADED
    err = capsys.readouterr().err
    assert '--strict' in err and 'compared with another run' in err


def test_a_driver_that_died_part_way_through_exits_nine_under_strict(monkeypatch, capsys):
    """The second fault, and the one the exit code was asked for. The rows say the sites answered
    nothing on every driver they were offered, which is what the batch looks like after its browser
    has gone, and a run of them is a census of dead websites that is really a dead machine."""
    from langaccess.core import DEAD_DRIVER_NOTE
    note = 'no page, and back in under 2s, on 3 %s: a site that answers nothing and a dead driver '
    monkeypatch.setattr(CLI, 'audit_async',
                        _reading_stub(_DEEP, note=(note % DEAD_DRIVER_NOTE) + 'look the same'))
    urls = ['s%d.org' % i for i in range(5)]
    assert CLI.main(['--json'] + urls) == CLI.EXIT_OK
    capsys.readouterr()
    assert CLI.main(['--json', '--strict'] + urls) == CLI.EXIT_DEGRADED
    err = capsys.readouterr().err
    assert 'every browser driver' in err and '5 of 5' in err


def test_strict_changes_the_exit_code_and_nothing_else(monkeypatch, capsys, tmp_path):
    """The run completes and writes exactly what it writes now. The same thin run with and without
    the flag produces byte-identical output files and the same lines on stdout."""
    monkeypatch.setattr(CLI, 'audit_async', _reading_stub(_THIN))
    urls = ['s%d.org' % i for i in range(5)]
    plain, strict = tmp_path / 'plain.jsonl', tmp_path / 'strict.jsonl'
    assert CLI.main(['--json', '--output', str(plain)] + urls) == CLI.EXIT_OK
    out_plain = capsys.readouterr().out
    assert CLI.main(['--json', '--strict', '--output', str(strict)] + urls) == CLI.EXIT_DEGRADED
    out_strict = capsys.readouterr().out

    def _rows(path):
        return [{k: v for k, v in json.loads(l).items()
                 if k not in ('audited_at', 'judged_at')}
                for l in path.read_text(encoding='utf-8').splitlines() if l.strip()]

    assert len(_rows(plain)) == 5 and _rows(plain) == _rows(strict)
    assert out_plain.count('\n') == out_strict.count('\n')


def test_a_missing_browser_outranks_strict(monkeypatch, capsys):
    """Code 3 stays code 3. A run that stopped where it stood is not a degraded reading of a whole
    list, it is a fraction of a list, and the more specific code says so."""
    monkeypatch.setattr(CLI, 'audit_async', _no_browser())
    assert CLI.main(['--json', '--strict', 'a.org', 'b.org']) == CLI.EXIT_NO_BROWSER


def test_strict_outranks_a_rejected_input(monkeypatch, capsys):
    """Both are true and one code has to be returned. Code 6 says the output does not cover the
    list it was given; code 9 says the rows that are in the output cannot be compared with another
    run's, which is the stronger statement about what the caller has in hand. The line naming the
    rejected strings is printed either way."""
    monkeypatch.setattr(CLI, 'audit_async', _reading_stub(_THIN))
    assert CLI.main(['--json', '--strict', 'good.org', 'hello world']) == CLI.EXIT_DEGRADED
    err = capsys.readouterr().err
    assert 'were not addresses' in err and '--strict' in err


def test_the_exit_codes_are_distinct():
    """Nine names one condition and nothing else does."""
    codes = [CLI.EXIT_OK, CLI.EXIT_USAGE, CLI.EXIT_NO_BROWSER, CLI.EXIT_NOTHING,
             CLI.EXIT_SHEET_REJECTED, CLI.EXIT_INPUT_REJECTED, CLI.EXIT_WRITE_BLOCKED,
             CLI.EXIT_STORE_FAILED, CLI.EXIT_DEGRADED]
    assert len(set(codes)) == len(codes)
    assert CLI.EXIT_DEGRADED == 9


# --------------------------------------------------- the end-of-batch pass, through the command line
#
# A shared-browser run reads its own transport failures once more at the end of each batch, on a
# browser launched for them alone. What the command line has to show is that the run still prints one
# line per address, in the order the addresses were given, carrying the reading that was kept; that
# `--no-retry-pass` turns the pass off; and that `--strict` judges the run as it finished rather than
# as the batch first left it.


class _DeadDriver:
    """A browser that is alive as far as the batch can tell. What it is standing in for is the pipe
    to the Playwright driver, which dies without saying so."""

    def __init__(self):
        self.closed = False

    def is_connected(self):
        return not self.closed

    async def close(self):
        self.closed = True


class _FakePW:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


_CLOSED_NOTE = 'RuntimeError: Connection closed while reading from the driver'


def _driver_dies_then_answers(monkeypatch):
    """The first browser of the run answers every site with a closed connection; the second reads.

    The browser object is the seam, as it is in the batch's own tests: `_launch` hands out a new one
    per driver, the batch opens one and the end-of-batch pass opens another, and the audit answers on
    which of the two it was given. This is the shape 10 of the 144 unreachable addresses of the
    gold-frame run carried, `Browser.new_context: Connection closed`, of which 9 answered a probe.
    """
    launched = []

    async def fake_launch(pw):
        b = _DeadDriver()
        launched.append(b)
        return b

    async def stub(url, max_pages=6, deep=False, keep_pages=False, block_private_hosts=False,
                   browser=None):
        if browser is launched[0]:
            return LA._failed(url, _CLOSED_NOTE)
        return Result(url=url, requested_url=url, verdict='english_only', pages_read=6,
                      read_quality={'pages_read': 6, 'sufficient': True})

    monkeypatch.setattr(LA, '_playwright', lambda: _FakePW())
    monkeypatch.setattr(LA, '_launch', fake_launch)
    monkeypatch.setattr(LA, '_audit_async', stub)
    return launched


def test_the_retry_pass_reaches_the_run_and_prints_one_line_per_address(monkeypatch, capsys):
    launched = _driver_dies_then_answers(monkeypatch)
    urls = ['a.org', 'b.org', 'c.org']
    assert CLI.main(['--json', '--shared-browser', '--concurrency', '2'] + urls) == CLI.EXIT_OK
    rows = [json.loads(l) for l in capsys.readouterr().out.splitlines() if l.strip()]
    assert [r['requested_url'] for r in rows] == urls, 'one row per address, in the order given'
    assert all(r['verdict'] == 'english_only' for r in rows)
    assert all(LA.RETRY_PASS_NOTE in r['note'] for r in rows)
    assert len(launched) == 2, 'the batch had one browser and the pass had one of its own'


def test_no_retry_pass_leaves_the_batch_s_own_answer(monkeypatch, capsys):
    """The flag is how a study measures what the pass recovers: the same list, one flag apart."""
    launched = _driver_dies_then_answers(monkeypatch)
    urls = ['a.org', 'b.org', 'c.org']
    assert CLI.main(['--json', '--shared-browser', '--no-retry-pass'] + urls) == CLI.EXIT_OK
    rows = [json.loads(l) for l in capsys.readouterr().out.splitlines() if l.strip()]
    assert [r['requested_url'] for r in rows] == urls
    assert all(r['verdict'] == 'unreachable' for r in rows)
    assert all(LA.RETRY_PASS_NOTE not in r['note'] for r in rows)
    assert len(launched) == 1, 'no second browser was opened'


def test_the_output_file_holds_the_reading_that_was_kept(monkeypatch, capsys, tmp_path):
    """A row held back for the pass reaches `--output` once, carrying the reading that was kept.
    Two rows for one address would be a run that read more addresses than it was given."""
    _driver_dies_then_answers(monkeypatch)
    out = tmp_path / 'run.jsonl'
    assert CLI.main(['--json', '--shared-browser', '--output', str(out),
                     'a.org', 'b.org']) == CLI.EXIT_OK
    capsys.readouterr()
    rows = [json.loads(l) for l in out.read_text(encoding='utf-8').splitlines() if l.strip()]
    assert [r['requested_url'] for r in rows] == ['a.org', 'b.org']
    assert all(r['pages_read'] == 6 for r in rows)


def test_strict_judges_the_run_as_the_pass_left_it(monkeypatch, capsys):
    """`--strict` refuses a run whose reading cannot be compared with another run's. The same three
    addresses are a refused run when the pass is off and an accepted one when it is on, which is
    what it means for the exit code to see the final state and not the batch's first answer."""
    _driver_dies_then_answers(monkeypatch)
    urls = ['a.org', 'b.org', 'c.org']
    assert CLI.main(['--json', '--shared-browser', '--strict', '--no-retry-pass']
                    + urls) == CLI.EXIT_DEGRADED
    assert '--strict' in capsys.readouterr().err
    _driver_dies_then_answers(monkeypatch)
    assert CLI.main(['--json', '--shared-browser', '--strict'] + urls) == CLI.EXIT_OK


def test_no_retry_pass_is_refused_with_rejudge(monkeypatch, tmp_path, capsys):
    """A re-judge opens no browser, so a crawl setting on it is a misunderstanding to answer rather
    than ignore. Eleven flags were once dropped here in silence."""
    run = tmp_path / 'run.jsonl'
    run.write_text('{"url": "https://x.org/", "verdict": "english_only"}\n', encoding='utf-8')
    with pytest.raises(SystemExit):
        CLI.main(['--json', '--rejudge', str(run), '--no-retry-pass'])
    assert '--no-retry-pass' in capsys.readouterr().err
