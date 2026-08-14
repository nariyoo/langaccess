# -*- coding: utf-8 -*-
"""Comparing two runs over one frame, and the two ways a comparison lies.

Every measurement this package is used for is a comparison of two runs over the same addresses. The
arithmetic is easy and it has been rewritten by hand for each of them, which is how both of the
failures below got into this project's history more than once.

A RUN THAT MADE SITES UNREADABLE MUST NOT REPORT AS A RUN THAT FOUND MORE. A bot wall, a slower
machine, a shorter timeout and a rate limit all turn readings into `unreachable`, and a total that
adds those to the sites that genuinely moved reports an instrument failure as a finding. So the
movement toward `unreachable` is its own block, it is first, it is named site by site, and no count
below it includes those sites in either direction.

A COMPARISON OF THE INTERSECTION IS NOT A COMPARISON. Quietly dropping the addresses that are in one
run and not the other is this project's single most frequent bug, six distinct instances of it, and
it is what turns "the new rules read 40 more sites as multilingual" into a sentence about a run that
lost 200 addresses. Every such address is counted and named.
"""
import json

import pytest

from langaccess import diff_runs, diff_text
from langaccess import cli as CLI


def _row(url, verdict='english_only', languages=(), authorship='none'):
    return {'url': url, 'verdict': verdict, 'languages': list(languages),
            'authorship': authorship}


def _write(tmp_path, name, rows):
    path = tmp_path / name
    with open(path, 'w', encoding='utf-8') as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + '\n')
    return str(path)


# ------------------------------------------------------------ movement toward unreachable
def test_a_site_that_stopped_being_readable_is_reported_first_and_on_its_own():
    a = [_row('https://one.org/', 'true_multilingual', ['English', 'Spanish'], 'authored')]
    b = [_row('https://one.org/', 'unreachable', [], 'none')]
    d = diff_runs(a, b)
    assert [m['url'] for m in d['unreachable']['toward']] == ['https://one.org/']
    assert d['verdicts'] == {}, 'the transition is in the unreachable block and in no tally'
    assert d['languages']['lost'] == {}, 'a site nobody could read did not lose a language'
    assert d['compared'] == 0
    # and the summary prints that block before it prints any count
    text = diff_text(d)
    assert text.index('toward unreachable') < text.index('verdict changes')


def test_the_unreachable_movement_is_never_netted_against_an_improvement():
    """The failure this rule exists for. Two sites become unreadable and one gains a language; a
    single figure would report the run as one site better off."""
    a = [_row('https://gone1.org/', 'true_multilingual', ['English', 'Spanish'], 'authored'),
         _row('https://gone2.org/', 'true_multilingual', ['English', 'Korean'], 'authored'),
         _row('https://found.org/', 'english_only', ['English'])]
    b = [_row('https://gone1.org/', 'unreachable'),
         _row('https://gone2.org/', 'unreachable'),
         _row('https://found.org/', 'true_multilingual', ['English', 'Vietnamese'], 'authored')]
    d = diff_runs(a, b)
    assert len(d['unreachable']['toward']) == 2
    assert d['verdicts'] == {'english_only -> true_multilingual': 1}
    assert d['languages']['gained'] == {'Vietnamese': 1}
    assert d['languages']['lost'] == {}
    assert d['compared'] == 1, 'one site was read in both runs, and it is the only denominator'


def test_recovery_is_reported_and_is_not_counted_as_a_language_gained():
    """The same rule in the other direction. A site the first run could not read has not gained a
    language by being readable, and counting it as one inflates the favourable number."""
    a = [_row('https://one.org/', 'unreachable')]
    b = [_row('https://one.org/', 'true_multilingual', ['English', 'Spanish'], 'authored')]
    d = diff_runs(a, b)
    assert [m['url'] for m in d['unreachable']['away']] == ['https://one.org/']
    assert d['languages']['gained'] == {}
    assert d['verdicts'] == {}
    assert d['compared'] == 0


def test_a_site_unreadable_in_both_runs_is_counted_and_enters_no_tally():
    a = [_row('https://one.org/', 'unreachable')]
    b = [_row('https://one.org/', 'unreachable')]
    d = diff_runs(a, b)
    assert d['unreachable_in_both'] == 1
    assert d['compared'] == 0 and d['verdicts'] == {}
    assert d['unreachable']['toward'] == [] and d['unreachable']['away'] == []


def test_the_four_buckets_account_for_every_address_in_both_runs():
    """The arithmetic a reader has to be able to do. Nothing falls between the buckets."""
    a = [_row('https://move.org/', 'english_only', ['English']),
         _row('https://same.org/', 'english_only', ['English']),
         _row('https://lost.org/', 'english_only', ['English']),
         _row('https://back.org/', 'unreachable'),
         _row('https://dark.org/', 'unreachable')]
    b = [_row('https://move.org/', 'true_multilingual', ['English', 'Spanish'], 'authored'),
         _row('https://same.org/', 'english_only', ['English']),
         _row('https://lost.org/', 'unreachable'),
         _row('https://back.org/', 'english_only', ['English']),
         _row('https://dark.org/', 'unreachable')]
    d = diff_runs(a, b)
    assert d['sites']['both'] == (d['compared'] + len(d['unreachable']['toward'])
                                  + len(d['unreachable']['away']) + d['unreachable_in_both'])
    assert d['compared'] == 2 and d['unchanged'] == 1


# ------------------------------------------------------------ an address in one run only
def test_an_address_in_one_run_and_not_the_other_is_counted_and_named():
    """The most frequent bug in this project's history is a stage that compares an intersection and
    calls it a comparison."""
    a = [_row('https://both.org/'), _row('https://only-a.org/'), _row('https://also-a.org/')]
    b = [_row('https://both.org/'), _row('https://only-b.org/')]
    d = diff_runs(a, b)
    assert d['sites']['only_in_a'] == ['https://also-a.org/', 'https://only-a.org/']
    assert d['sites']['only_in_b'] == ['https://only-b.org/']
    assert d['sites']['a'] == 3 and d['sites']['b'] == 2 and d['sites']['both'] == 1
    text = diff_text(d)
    assert 'only in a   2 sites' in text and 'https://only-a.org/' in text
    assert 'only in b   1 site' in text


def test_a_long_only_in_list_is_still_counted_in_full():
    """The names are held back past a point and the count never is, so nothing is dropped by being
    inconvenient to print."""
    a = [_row('https://s%d.org/' % i) for i in range(60)]
    d = diff_runs(a, [])
    assert len(d['sites']['only_in_a']) == 60
    text = diff_text(d)
    assert 'only in a   60 sites' in text
    assert 'and 40 more' in text


def test_two_runs_with_no_address_in_common_report_that_rather_than_nothing():
    d = diff_runs([_row('https://a.org/')], [_row('https://b.org/')])
    assert d['sites']['both'] == 0
    assert d['sites']['only_in_a'] == ['https://a.org/']
    assert d['sites']['only_in_b'] == ['https://b.org/']
    assert d['compared'] == 0


# ------------------------------------------------------------ what moved, per site
def test_a_site_reports_its_verdict_change_and_the_languages_either_side():
    a = [_row('https://one.org/', 'machine_translate', ['English'], 'client_widget')]
    b = [_row('https://one.org/', 'true_multilingual', ['English', 'Spanish'], 'authored')]
    d = diff_runs(a, b)
    m = d['moved'][0]
    assert m['verdict'] == {'a': 'machine_translate', 'b': 'true_multilingual'}
    assert m['languages_gained'] == ['Spanish'] and m['languages_lost'] == []
    assert m['authorship'] == {'a': 'client_widget', 'b': 'authored'}
    assert d['authorship'] == {'client_widget -> authored': 1}


def test_a_language_lost_on_a_site_that_stayed_readable_is_reported_as_a_loss():
    """The tallies are not one-sided. What they exclude is the sites nobody could read."""
    a = [_row('https://one.org/', 'true_multilingual', ['English', 'Korean'], 'authored')]
    b = [_row('https://one.org/', 'english_only', ['English'], 'none')]
    d = diff_runs(a, b)
    assert d['languages']['lost'] == {'Korean': 1}
    assert d['verdicts'] == {'true_multilingual -> english_only': 1}


def test_a_site_that_did_not_move_is_not_in_the_moved_list():
    same = [_row('https://one.org/', 'true_multilingual', ['English', 'Spanish'], 'authored')]
    d = diff_runs(same, [dict(r) for r in same])
    assert d['moved'] == [] and d['unchanged'] == 1 and d['compared'] == 1


def test_an_address_written_with_and_without_its_trailing_slash_is_one_site():
    """The two runs are compared on the key core compares two stored addresses on."""
    d = diff_runs([_row('https://one.org/')], [_row('HTTPS://ONE.ORG')])
    assert d['sites']['both'] == 1 and d['sites']['only_in_a'] == []


def test_a_site_written_twice_in_one_run_is_the_last_row_and_the_collapse_is_reported():
    """A store appends, so a site audited twice has its most recent reading written last, which is
    what `_stored_record` reads. How many rows collapsed is said rather than hidden."""
    a = [_row('https://one.org/', 'english_only', ['English']),
         _row('https://one.org/', 'true_multilingual', ['English', 'Spanish'], 'authored')]
    b = [_row('https://one.org/', 'true_multilingual', ['English', 'Spanish'], 'authored')]
    d = diff_runs(a, b)
    assert d['runs']['a']['rows'] == 2 and d['runs']['a']['duplicate_rows'] == 1
    assert d['moved'] == [], 'the last row of a is the one compared'
    assert 'rows collapsed' in diff_text(d)


# ------------------------------------------------------------ the files and the command line
def test_a_run_file_written_by_the_command_line_is_read_back(tmp_path):
    """`--json --output` and `--store` write the same one-object-per-line form, so a diff reads
    either without being told which it was given."""
    pa = _write(tmp_path, 'a.jsonl', [_row('https://one.org/', 'english_only', ['English'])])
    pb = _write(tmp_path, 'b.jsonl',
                [_row('https://one.org/', 'true_multilingual', ['English', 'Spanish'], 'authored')])
    d = diff_runs(pa, pb)
    assert d['runs']['a']['path'] == pa
    assert d['verdicts'] == {'english_only -> true_multilingual': 1}


def test_the_subcommand_prints_a_summary(tmp_path, capsys):
    pa = _write(tmp_path, 'a.jsonl', [_row('https://one.org/', 'english_only', ['English']),
                                      _row('https://two.org/', 'english_only', ['English'])])
    pb = _write(tmp_path, 'b.jsonl',
                [_row('https://one.org/', 'true_multilingual', ['English', 'Spanish'], 'authored'),
                 _row('https://two.org/', 'unreachable')])
    assert CLI.main(['diff', pa, pb]) == CLI.EXIT_OK
    out = capsys.readouterr().out
    assert 'toward unreachable   1 site' in out
    assert 'english_only -> true_multilingual' in out
    assert out.index('toward unreachable') < out.index('english_only -> true_multilingual')


def test_the_subcommand_gives_the_moved_sites_as_data(tmp_path, capsys):
    pa = _write(tmp_path, 'a.jsonl', [_row('https://one.org/', 'english_only', ['English'])])
    pb = _write(tmp_path, 'b.jsonl',
                [_row('https://one.org/', 'true_multilingual', ['English', 'Spanish'], 'authored')])
    assert CLI.main(['diff', '--json', pa, pb]) == CLI.EXIT_OK
    got = json.loads(capsys.readouterr().out)
    assert got['moved'][0]['url'] == 'https://one.org/'
    assert got['moved'][0]['languages_gained'] == ['Spanish']


def test_the_subcommand_says_which_file_is_missing(tmp_path, capsys):
    pa = _write(tmp_path, 'a.jsonl', [_row('https://one.org/')])
    with pytest.raises(SystemExit):
        CLI.main(['diff', pa, str(tmp_path / 'nothing.jsonl')])
    assert 'does not exist' in capsys.readouterr().err


def test_the_word_diff_does_not_disturb_the_audit_command_line(monkeypatch, capsys):
    """The rest of the tool keeps the flat command line it has always had."""
    from langaccess.core import Result

    async def fake(u, deep=False, timeout=None):
        return Result(url=u, verdict='english_only')

    monkeypatch.setattr(CLI, 'audit_async', fake)
    assert CLI.main(['--json', 'https://diff.org/']) == 0
    lines = [json.loads(l) for l in capsys.readouterr().out.splitlines() if l.strip()]
    assert [r['url'] for r in lines] == ['https://diff.org/']


def test_a_row_with_no_address_is_counted_rather_than_dropped():
    """It cannot be compared with anything, which is a reason to say so and not a reason to be
    quiet about it."""
    d = diff_runs([_row('https://one.org/'), {'verdict': 'english_only'}],
                  [_row('https://one.org/')])
    assert d['runs']['a']['blank_url_rows'] == 1
    assert d['sites']['a'] == 1
    assert 'rows with no address' in diff_text(d)
