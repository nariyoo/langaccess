# -*- coding: utf-8 -*-
"""`langaccess calibrate`: settings measured on the machine that will do the run.

The two pieces that decide anything are separated from the piece that opens a browser, so they are
tested here without one. What the command does with a browser is one thing (it reads a small sample
twice) and what it concludes is another, and only the second can be wrong quietly.
"""
import os
import subprocess
import sys

import pytest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_ROOT, 'src'))

from langaccess import core                                              # noqa: E402
from langaccess.cli import calibrate_plan, calibrate_reading             # noqa: E402


class _R:
    """A result carrying only what the calibration reads."""
    def __init__(self, pages, sufficient, clock=False, escalated=False):
        self.read_quality = {'pages_read': pages, 'sufficient': sufficient,
                             'clock_exhausted': clock, 'escalated': escalated}


# ------------------------------------------------------------------ the ladder
def test_the_ladder_raises_the_clock_before_anything_else():
    """An exhausted clock makes every other figure meaningless: a site that ran out of time read one
    page, so its depth describes the clock and not the machine, and its verdict describes neither."""
    plan = calibrate_plan([], 3)
    assert plan[0][0] < plan[1][0], 'the second rung does not give the site more clock'


def test_concurrency_never_goes_up_along_the_ladder():
    """Raising concurrency on a busy machine makes each site slower and can push readings back into
    clock_exhausted. A step that undoes itself is not one to take without somebody watching, so the
    ladder only ever lowers it and the person is told to raise it by hand."""
    concs = [c for _, c in calibrate_plan([], 3)]
    assert concs == sorted(concs, reverse=True), concs


def test_the_ladder_is_bounded_by_attempts():
    assert len(calibrate_plan([], 1)) == 1
    assert len(calibrate_plan([], 2)) == 2
    assert len(calibrate_plan([], 99)) == len(calibrate_plan([], 3)), 'attempts past the ladder'


def test_a_zero_attempt_still_tries_once():
    """Zero rungs would report "no setting works" without having tried one, which is a false
    statement about the machine."""
    assert len(calibrate_plan([], 0)) == 1


# ------------------------------------------------------------------ the reading
def test_shares_are_taken_over_the_sites_that_were_read():
    """A dead address has no search to judge. Counted as a thin reading, a list of dead addresses
    would read as a slow machine and the calibration would climb the ladder chasing nothing."""
    got = calibrate_reading([_R(0, False), _R(0, False), _R(9, True), _R(9, True)])
    assert got['sites'] == 4
    assert got['read'] == 2
    assert got['sufficient'] == 2
    assert got['median_pages'] == 9


def test_the_exhausted_clock_is_counted_and_reported():
    got = calibrate_reading([_R(1, False, clock=True) for _ in range(5)])
    assert got['clock_exhausted'] == 5
    assert got['accepted'] is False
    assert 'under the floor' in got['why']


def test_a_good_reading_is_accepted():
    got = calibrate_reading([_R(15, True) for _ in range(10)])
    assert got['accepted'] is True
    assert got['median_pages'] == 15


def test_the_reading_carries_the_thresholds_it_was_judged_against():
    """So a calibration run under a lowered gate cannot be quoted as though it cleared the shipped
    one. Same rule as the run itself."""
    got = calibrate_reading([_R(15, True) for _ in range(4)])
    assert got['min_median_pages'] == core.CAPTURE_MIN_MEDIAN_PAGES
    assert got['max_thin_share'] == core.CAPTURE_MAX_THIN_SHARE


def test_nothing_read_is_not_an_acceptance():
    """The one case where every share divides by zero."""
    got = calibrate_reading([_R(0, False), _R(0, False)])
    assert got['read'] == 0
    assert got['accepted'] is False
    assert got['median_pages'] == 0


# ------------------------------------------------------------------ the command
def test_calibrate_is_a_subcommand():
    from langaccess.cli import SUBCOMMANDS
    assert 'calibrate' in SUBCOMMANDS


def test_calibrate_refuses_an_empty_list_rather_than_opening_a_browser():
    """With no addresses there is nothing to measure, and a browser launched to read nothing would
    report a machine that cannot clear the floor."""
    p = subprocess.run([sys.executable, '-m', 'langaccess.cli', 'calibrate'],
                       capture_output=True, text=True, encoding='utf-8', errors='replace',
                       cwd=os.path.join(_ROOT, 'src'))
    assert p.returncode == 2, p.stdout[-400:]
    assert 'needs addresses' in p.stderr


def test_the_only_address_the_package_fetches_unasked_belongs_to_the_author():
    """A demo target baked into a published tool is fetched once per person who installs it. That
    load can only be spent on a site whose owner is in the room, so the constant is checked here
    rather than left to whoever edits it next."""
    from langaccess.cli import DEMO_URL
    assert DEMO_URL == 'https://nariyoo.com'


@pytest.mark.live
def test_demo_never_replaces_a_list_that_was_given():
    """--demo beside real addresses has to lose. A flag that silently swapped a thousand-address
    calibration for one site would report a setting measured on nothing."""
    p = subprocess.run([sys.executable, '-m', 'langaccess.cli', 'calibrate', '--demo',
                        'https://example.org', '--attempts', '0', '--json'],
                       capture_output=True, text=True, encoding='utf-8', errors='replace',
                       cwd=os.path.join(_ROOT, 'src'), timeout=600)
    assert '--demo ignored' in p.stderr, p.stderr[-400:]
    from langaccess.cli import DEMO_URL
    assert DEMO_URL not in p.stdout


@pytest.mark.parametrize('flag', ['--from-file', '--sample', '--for', '--attempts', '--quick',
                                  '--delay', '--ignore-robots', '--json', '--demo'])
def test_the_command_offers_its_settings(flag):
    p = subprocess.run([sys.executable, '-m', 'langaccess.cli', 'calibrate', '--help'],
                       capture_output=True, text=True, encoding='utf-8', errors='replace',
                       cwd=os.path.join(_ROOT, 'src'))
    assert p.returncode == 0, p.stderr[-400:]
    assert flag in p.stdout
