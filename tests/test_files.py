# -*- coding: utf-8 -*-
"""Moving a finished file onto the path it replaces, when the machine will not let go of it.

Found on 2026-08-08 by running this package's own suite three times over: one run in three failed
inside `langaccess ingest` with PermissionError, WinError 5, out of `os.replace`. Nothing in the
code had changed between the runs. On Windows a replace is refused while any other process holds
the destination open, and a virus scanner or a search indexer reading a file the moment after it is
written is enough to do it.

The failure mattered because of which file it was. `ingest` is how a hand-coding round enters a run,
and what the person saw was a traceback and a coding round that appeared to be gone. It was never
gone: the settled run had already been written whole, beside the destination, under a temporary
name. So the move now waits the holder out, and where it still cannot be made the message names the
finished file and the command exits 7 instead of raising.

The first test here takes a real exclusive lock on Windows, so the defect is reproduced rather than
described. Everywhere else it is simulated, because POSIX permits the rename regardless.
"""
import json
import os
import sys

import pytest

from langaccess import cli as CLI
from langaccess.files import ReplaceBlocked, replace_atomically


def _run_file(tmp_path, name='run.jsonl'):
    p = tmp_path / name
    p.write_text(json.dumps({'url': 'https://a.org/', 'verdict': 'english_only',
                             'languages': ['English'], 'pages': []}) + '\n', encoding='utf-8')
    return str(p)


def test_a_replace_nothing_is_holding_just_happens(tmp_path):
    target = tmp_path / 'run.jsonl'
    target.write_text('old\n', encoding='utf-8')
    tmp = tmp_path / 'run.jsonl.tmp'
    tmp.write_text('new\n', encoding='utf-8')
    assert replace_atomically(str(tmp), str(target)) == str(target)
    assert target.read_text(encoding='utf-8') == 'new\n'
    assert not tmp.exists()


@pytest.mark.skipif(sys.platform != 'win32', reason='POSIX renames over an open file')
def test_a_destination_held_open_is_reported_and_not_lost(tmp_path):
    """The real defect, with a real lock: the finished file survives and is named."""
    target = tmp_path / 'run.jsonl'
    target.write_text('old\n', encoding='utf-8')
    tmp = tmp_path / 'run.jsonl.tmp'
    tmp.write_text('new\n', encoding='utf-8')
    holder = open(str(target), 'r', encoding='utf-8')
    try:
        with pytest.raises(ReplaceBlocked) as e:
            replace_atomically(str(tmp), str(target), tries=2, pause=0.01)
    finally:
        holder.close()
    assert e.value.finished == str(tmp) and e.value.target == str(target)
    assert str(tmp) in str(e.value), 'the message must name the file the work is in'
    assert tmp.read_text(encoding='utf-8') == 'new\n', 'the finished file must survive'


def test_a_holder_that_lets_go_is_waited_out(tmp_path, monkeypatch):
    """One refusal then success, which is the shape of a scanner reading a file just written."""
    target = tmp_path / 'run.jsonl'
    target.write_text('old\n', encoding='utf-8')
    tmp = tmp_path / 'run.jsonl.tmp'
    tmp.write_text('new\n', encoding='utf-8')
    real, calls = os.replace, []

    def flaky(a, b):
        calls.append(1)
        if len(calls) == 1:
            raise PermissionError(5, 'Access is denied')
        return real(a, b)

    monkeypatch.setattr(os, 'replace', flaky)
    assert replace_atomically(str(tmp), str(target), tries=4, pause=0.01) == str(target)
    assert len(calls) == 2
    assert target.read_text(encoding='utf-8') == 'new\n'


def test_a_failure_that_is_not_a_holder_is_raised(tmp_path, monkeypatch):
    """A missing source is a fault in the caller and must not be retried into a wrong message."""
    monkeypatch.setattr(os, 'replace', lambda a, b: (_ for _ in ()).throw(FileNotFoundError(a)))
    with pytest.raises(FileNotFoundError):
        replace_atomically(str(tmp_path / 'nope'), str(tmp_path / 'run.jsonl'), tries=3, pause=0.01)


def test_ingest_answers_a_blocked_write_with_a_sentence_and_code_seven(tmp_path, capsys,
                                                                      monkeypatch):
    """What the person running the coding round sees. Not a traceback, and not exit 1."""
    run = _run_file(tmp_path)
    sheet = str(tmp_path / 'review.csv')
    assert CLI.main(['review', run, '-o', sheet]) == CLI.EXIT_OK
    capsys.readouterr()
    monkeypatch.setattr(CLI, 'replace_atomically', lambda a, b: (_ for _ in ()).throw(
        ReplaceBlocked('%s could not be replaced. the finished file is %s' % (b, a), a, b)))
    assert CLI.main(['ingest', sheet, run]) == CLI.EXIT_WRITE_BLOCKED
    err = capsys.readouterr().err
    assert 'could not finish writing' in err and 'ingest-tmp' in err
    assert 'Traceback' not in err


def test_the_blocked_code_is_its_own(tmp_path):
    """7 is claimed by nothing else, so a caller can act on it."""
    codes = [CLI.EXIT_OK, CLI.EXIT_USAGE, CLI.EXIT_NO_BROWSER, CLI.EXIT_NOTHING,
             CLI.EXIT_SHEET_REJECTED, CLI.EXIT_INPUT_REJECTED, CLI.EXIT_WRITE_BLOCKED]
    assert CLI.EXIT_WRITE_BLOCKED == 7
    assert len(set(codes)) == len(codes)
