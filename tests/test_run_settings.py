# -*- coding: utf-8 -*-
"""The settings a run can be given: the page budget, the pause between fetches, the gate.

All three were reachable only by editing the source until 2026-08-07. The pause did not exist at
all, which mattered because `--ignore-robots` did: the tool could be told to fetch what a host asks
it not to fetch, at whatever rate the machine managed, and offered no way to slow down.

The gate opened at Nari's decision, against the argument that a movable gate is not a gate. The
answer is the last test in this file: whatever the thresholds are set to, the result carries them,
so a run that passed on a lowered gate cannot be quoted as though it had passed on the shipped one.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'src'))

from langaccess import core                                            # noqa: E402


@pytest.fixture(autouse=True)
def _restore():
    """Every test here moves module state. Put it back, or the next test reads this one's setting."""
    delay = core.PAGE_DELAY
    gate = (core.CAPTURE_MIN_MEDIAN_PAGES, core.CAPTURE_MAX_THIN_SHARE)
    yield
    core.set_page_delay(delay)
    core.set_acceptance(gate[0], gate[1])
    assert core.PAGE_DELAY == delay
    assert (core.CAPTURE_MIN_MEDIAN_PAGES, core.CAPTURE_MAX_THIN_SHARE) == gate


# --------------------------------------------------------------------------- the pause
def test_the_pause_defaults_to_nothing():
    """A single audit of a single site does not need pacing, and paying for it silently would make
    every default run slower for no reason the user asked for."""
    assert core.PAGE_DELAY == 0.0


def test_the_pause_is_set_and_returns_what_it_was():
    was = core.set_page_delay(2.5)
    assert was == 0.0
    assert core.PAGE_DELAY == 2.5
    assert core.set_page_delay(0) == 2.5
    assert core.PAGE_DELAY == 0.0


def test_a_negative_pause_is_not_a_negative_pause():
    """A negative sleep is a TypeError deep inside asyncio, an hour into a run."""
    core.set_page_delay(-5)
    assert core.PAGE_DELAY == 0.0


def test_the_pause_is_applied_where_a_page_is_opened():
    """The delay has to sit at the navigation itself. Placed anywhere else it paces batches rather
    than requests, and a host sees the same burst."""
    import inspect
    src = inspect.getsource(core)
    i = src.find("resp = await page.goto(url, wait_until='domcontentloaded'")
    assert i > 0, 'the navigation moved; this test is now looking at the wrong place'
    before = src[max(0, i - 200):i]
    assert 'PAGE_DELAY' in before and 'asyncio.sleep' in before, (
        'the pause is not taken immediately before the page is opened:\n%s' % before[-200:])


# --------------------------------------------------------------------------- the CLI surface
# The parser is built inside main() rather than by a factory, so the user-facing surface is checked
# by running the program. Slower than parsing in process and it tests the thing the user touches.
@pytest.mark.parametrize('flag', ['--max-pages', '--delay', '--min-median-pages',
                                  '--max-thin-share'])
def test_each_setting_is_offered_on_the_command_line(flag):
    import subprocess
    p = subprocess.run([sys.executable, '-m', 'langaccess.cli', '--help'],
                       capture_output=True, text=True, encoding='utf-8', errors='replace',
                       cwd=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                        'src'))
    assert p.returncode == 0, p.stderr[-800:]
    assert flag in p.stdout, '%s is not offered; the help lists %r' % (flag, p.stdout[:400])


def test_the_page_budget_reaches_the_engine():
    """The flag existing is not the flag working. The wiring is what was missing: the same value had
    been reachable from Python and not from the command line."""
    import inspect
    from langaccess import cli
    assert 'max_pages' in inspect.signature(cli._run).parameters
    assert inspect.signature(cli._run).parameters['max_pages'].default is None, (
        'the default has to be None so the engine keeps its own budget when nobody asked')
    assert "extra['max_pages'] = max_pages" in inspect.getsource(cli._run)
    assert 'args.max_pages' in inspect.getsource(cli.main), 'main does not hand the value down'


# --------------------------------------------------------------------------- the gate
def _fake(pages, sufficient):
    return {'read_quality': {'pages_read': pages, 'sufficient': sufficient}}


def test_the_shipped_gate_refuses_a_thin_run():
    """The run that started this: sixteen readings, every one a single page with the clock gone."""
    got = core.capture_acceptance([_fake(1, False) for _ in range(16)])
    assert got['accepted'] is False
    assert 'under the floor of 4' in got['why']


def test_the_gate_moves_when_it_is_told_to():
    thin = [_fake(1, False) for _ in range(16)]
    assert core.capture_acceptance(thin)['accepted'] is False
    core.set_acceptance(min_median_pages=1, max_thin_share=1.0)
    assert core.capture_acceptance(thin)['accepted'] is True


def test_a_moved_gate_is_recorded_in_the_result():
    """The whole defence of a movable gate.

    A run that passed because the thresholds were lowered has to say so in the artifact, so the
    reader of a result never has to reconstruct how it was invoked to know what it cleared.
    """
    shipped = core.capture_acceptance([_fake(9, True) for _ in range(10)])
    assert shipped['min_median_pages'] == 4 and shipped['max_thin_share'] == 0.25

    # 1.0 and not 0.99: the ceiling is a strict comparison, so a run where every reading is thin
    # needs the ceiling at 1.0 to pass. 0.99 reads like "allow anything" and is the one value that
    # does not.
    core.set_acceptance(min_median_pages=1, max_thin_share=1.0)
    relaxed = core.capture_acceptance([_fake(1, False) for _ in range(10)])
    assert relaxed['accepted'] is True
    assert relaxed['min_median_pages'] == 1, 'a run that passed on a lowered floor does not say so'
    assert relaxed['max_thin_share'] == 1.0


def test_the_empty_run_also_records_the_thresholds():
    """The early return had its own dict and would have been the one branch with nothing on it."""
    got = core.capture_acceptance([_fake(0, False)])
    assert got['accepted'] is False
    assert 'min_median_pages' in got and 'max_thin_share' in got


def test_set_acceptance_returns_what_it_replaced():
    was = core.set_acceptance(min_median_pages=7)
    assert was == (4, 0.25)
    assert core.CAPTURE_MIN_MEDIAN_PAGES == 7
    assert core.CAPTURE_MAX_THIN_SHARE == 0.25, 'a partial call moved a threshold it was not given'


# --------------------------------------------------------------------------- robots.txt
def test_ignoring_robots_carries_a_floor_on_the_pause():
    """Overriding a host's stated wish and hammering it are separate acts. The first can have a
    defence; the second does not, so the code does not let the first happen without the second
    being considered."""
    assert core.IGNORE_ROBOTS_MIN_DELAY > 0
    import inspect
    from langaccess import cli
    src = inspect.getsource(cli.main)
    assert 'IGNORE_ROBOTS_MIN_DELAY' in src
    assert 'args.ignore_robots' in src
