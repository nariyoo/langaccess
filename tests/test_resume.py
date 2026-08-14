# -*- coding: utf-8 -*-
"""The address as it was given, and the resume that needs it.

WHY THE FIELD EXISTS, measured rather than supposed. `Result.url` is where the browser ended up,
which is the address to quote beside a finding and the wrong one to join a table on. On the
1,000-site round of 2026-08-07, 209 of the 1,000 results came back under an address that is not in
the frame they were drawn from, and the strata analysis of that run joined 791 rows and gave up on
the rest. A run whose output cannot be matched to its own input list has lost the link between a
verdict and everything else known about that organization, and no amount of care downstream puts it
back.

So every `Result` now carries `requested_url`, the string the caller handed over, before a scheme
was added and before any redirect. The tests below hold three things to that: the live path records
it, a re-judge carries it rather than re-deriving it, and a record written before the field existed
still reads.

`--resume` is what the field makes possible. It skips the addresses a previous run finished, and the
one thing it must never do is skip them quietly: the counts go to stderr every time, including the
count of rows too old to carry the field, because those are matched on the redirected address and a
site that moved will be read twice.
"""
import gzip
import json

import pytest

from langaccess import cli as CLI
from langaccess.core import Result, rejudge


# ------------------------------------------------------------------ the address as it was given


def test_the_result_carries_the_address_as_given():
    r = Result(url='https://www.example.org/', requested_url='example.org')
    d = r.to_dict()
    assert d['requested_url'] == 'example.org'
    assert d['url'] == 'https://www.example.org/'


def test_the_field_sits_beside_the_url_and_not_at_the_end():
    """A consumer selecting the first columns of a run file should get both addresses."""
    assert list(Result(url='x').to_dict())[:2] == ['url', 'requested_url']


def test_a_record_written_before_the_field_still_reads():
    old = {'url': 'https://a.org/', 'verdict': 'english_only', 'languages': ['English'],
           'pages': {}}
    r = rejudge(old)
    assert r.requested_url == ''
    assert r.url == 'https://a.org/'


def test_a_rejudge_carries_the_address_rather_than_re_deriving_it():
    rec = {'url': 'https://www.moved.org/', 'requested_url': 'moved.org',
           'verdict': 'english_only', 'languages': ['English'], 'pages': {}}
    assert rejudge(rec).requested_url == 'moved.org'


def test_a_site_that_could_not_be_audited_still_names_the_address_it_was_given():
    from langaccess.core import _failed
    r = _failed('https://gone.org', 'bot wall')
    assert r.requested_url == 'https://gone.org'


# ------------------------------------------------------------------------------ the resume key


@pytest.mark.parametrize('a,b', [
    ('example.org', 'https://example.org/'),
    ('HTTP://Example.ORG', 'example.org'),
    ('https://example.org/', 'http://example.org'),
])
def test_the_forms_of_one_address_compare_equal(a, b):
    assert CLI._resume_key(a) == CLI._resume_key(b)


def test_two_different_hosts_do_not_compare_equal():
    assert CLI._resume_key('example.org') != CLI._resume_key('www.example.org')


# ---------------------------------------------------------------------------------- the resume


def _run_file(tmp_path, rows, name='out.jsonl'):
    p = tmp_path / name
    p.write_text(''.join(json.dumps(r) + '\n' for r in rows), encoding='utf-8')
    return str(p)


def test_the_addresses_already_done_are_read_off_the_requested_address(tmp_path):
    path = _run_file(tmp_path, [
        {'requested_url': 'a.org', 'url': 'https://www.a.org/'},
        {'requested_url': 'b.org', 'url': 'https://b.org/'}])
    done, lines, old = CLI._addresses_already_done(path)
    assert done == {'a.org', 'b.org'} and lines == 2 and old == 0


def test_a_row_with_no_requested_address_falls_back_and_is_counted(tmp_path):
    path = _run_file(tmp_path, [{'url': 'https://www.c.org/'}])
    done, lines, old = CLI._addresses_already_done(path)
    assert done == {'www.c.org'} and old == 1, 'the fallback must be counted, not hidden'


def test_a_gzipped_store_is_read(tmp_path):
    p = tmp_path / 'run.jsonl.gz'
    with gzip.open(str(p), 'wt', encoding='utf-8') as fh:
        fh.write(json.dumps({'requested_url': 'd.org', 'url': 'https://d.org/'}) + '\n')
    done, lines, old = CLI._addresses_already_done(str(p))
    assert done == {'d.org'} and lines == 1


def _stub(monkeypatch, seen):
    async def fake(u, deep=False, timeout=None, **kw):
        seen.append(u)
        return Result(url=u, requested_url=u, verdict='english_only')
    monkeypatch.setattr(CLI, 'audit_async', fake)


def test_resume_audits_only_what_is_left_and_says_how_many(tmp_path, capsys, monkeypatch):
    prev = _run_file(tmp_path, [{'requested_url': 'a.org', 'url': 'https://www.a.org/'}])
    lst = tmp_path / 'sites.txt'
    lst.write_text('a.org\nb.org\nc.org\n', encoding='utf-8')
    seen = []
    _stub(monkeypatch, seen)
    assert CLI.main(['--from-file', str(lst), '--resume', prev]) == CLI.EXIT_OK
    err = capsys.readouterr().err
    assert 'skipped 1 of the 3 addresses given; 2 left' in err
    assert seen == ['b.org', 'c.org'], 'the address is passed on as the caller wrote it'


def test_a_redirected_address_is_not_read_twice(tmp_path, capsys, monkeypatch):
    """The defect the field exists for. The previous run recorded a different `url`, and matching on
    that would put this address back on the list every time the run is resumed."""
    prev = _run_file(tmp_path, [{'requested_url': 'moved.org', 'url': 'https://www.newname.org/'}])
    lst = tmp_path / 'sites.txt'
    lst.write_text('moved.org\nstill.org\n', encoding='utf-8')
    seen = []
    _stub(monkeypatch, seen)
    CLI.main(['--from-file', str(lst), '--resume', prev])
    assert seen == ['still.org'], 'the redirected address was read again'


def test_a_finished_list_does_nothing_and_says_so(tmp_path, capsys, monkeypatch):
    prev = _run_file(tmp_path, [{'requested_url': 'a.org'}, {'requested_url': 'b.org'}])
    lst = tmp_path / 'sites.txt'
    lst.write_text('a.org\nb.org\n', encoding='utf-8')
    seen = []
    _stub(monkeypatch, seen)
    assert CLI.main(['--from-file', str(lst), '--resume', prev]) == CLI.EXIT_OK
    assert 'nothing to do' in capsys.readouterr().err
    assert seen == [], 'a finished list must start no browser'


def test_an_unreachable_row_counts_as_done(tmp_path, monkeypatch):
    """Resume is resume. Re-reading the sites a run could not reach is what `retry` is for, and
    doing it here would change unreachable rows every time a run was continued."""
    prev = _run_file(tmp_path, [{'requested_url': 'wall.org', 'url': 'https://wall.org/',
                                 'verdict': 'unreachable'}])
    lst = tmp_path / 'sites.txt'
    lst.write_text('wall.org\nok.org\n', encoding='utf-8')
    seen = []
    _stub(monkeypatch, seen)
    CLI.main(['--from-file', str(lst), '--resume', prev])
    assert seen == ['ok.org']


def test_a_resume_file_that_is_not_there_is_one_sentence(tmp_path, capsys):
    lst = tmp_path / 'sites.txt'
    lst.write_text('a.org\n', encoding='utf-8')
    with pytest.raises(SystemExit) as e:
        CLI.main(['--from-file', str(lst), '--resume', str(tmp_path / 'nope.jsonl')])
    assert e.value.code == CLI.EXIT_USAGE
    err = capsys.readouterr().err
    assert 'does not exist' in err and 'Traceback' not in err


def test_a_rejected_address_is_still_rejected_on_a_resumed_run(tmp_path, capsys, monkeypatch):
    """The resume filter runs after the address check, so a typo on line 3 is still reported."""
    prev = _run_file(tmp_path, [{'requested_url': 'a.org'}])
    lst = tmp_path / 'sites.txt'
    lst.write_text('a.org\nb.org\nhtp://c.org\n', encoding='utf-8')
    seen = []
    _stub(monkeypatch, seen)
    code = CLI.main(['--from-file', str(lst), '--resume', prev])
    err = capsys.readouterr().err
    assert 'its scheme is' in err
    assert code == CLI.EXIT_INPUT_REJECTED
    assert seen == ['b.org']
