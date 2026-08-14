# -*- coding: utf-8 -*-
"""What the command line does with input that is not what it was asked for.

Three defects found on 2026-08-08 by using the installed tool as a first-time user would, and one of
them is the class this project cares about most.

`langaccess "hello world"` and `langaccess htp://example.org` both printed `verdict unreachable`.
The tool put https:// in front of whatever it was handed, failed to open it, and recorded that
failure as a reading: in a study those rows are counted as sites that could not be reached, when the
truth is that nobody ever gave the tool a site. The second is the worse of the two, because a scheme
one letter out of true is a typo nobody notices in a thousand-row file and the row it produces looks
like every other unreachable row. A string that is not an address now gets no verdict at all.

`--from-file` on a path that does not exist raised a traceback ending inside `_urls_from_file` and
exited 1, the code reserved for this tool having crashed, while an EMPTY file already answered with
one clean sentence. The two are now the same answer.

`--output` without `--json` is documented as ignored and the sentence saying so was printed on one
of the two paths through the command line and not on the other.

Nothing here starts a browser. The audit is a stub that records which addresses reached it, which is
also how the first group of tests proves the rejected ones reached nothing.
"""
import json
import os

import pytest

from langaccess import cli as CLI
from langaccess.address import AddressRejected, auditable_url
from langaccess.core import Result


def _recording_stub(seen):
    """An audit_async that answers every address and records the ones it was asked for."""
    async def fake(u, deep=False, timeout=None):
        seen.append(u)
        return Result(url=u, verdict='english_only')
    return fake


# --------------------------------------------------------------- the rule itself, without the CLI


@pytest.mark.parametrize('raw', [
    'example.org', 'https://example.org', 'http://example.org/some/path?a=1',
    'https://sub.domain.example.org:8443/x', 'localhost', 'http://localhost:8000/',
    'https://93.184.216.34/', 'HTTPS://EXAMPLE.ORG',
])
def test_an_address_is_accepted(raw):
    # lowercased for the test only: the address comes back as it was typed, because what is returned
    # is what gets fetched and a host is not this function's to rewrite
    assert auditable_url(raw).lower().startswith(('http://', 'https://'))


@pytest.mark.parametrize('raw,in_reason', [
    ('hello world', 'space'),
    ('hello', 'dot'),
    ('htp://example.org', 'scheme'),
    ('ftp://example.org/file', 'scheme'),
    ('https://example.org/a b', 'space'),
    ('   ', 'empty'),
    ('', 'empty'),
    ('https://', 'no host'),
])
def test_what_is_not_an_address_is_rejected_with_a_reason(raw, in_reason):
    with pytest.raises(AddressRejected) as e:
        auditable_url(raw)
    assert in_reason in e.value.reason
    assert e.value.raw == raw, 'the rejected string has to come back, to be found in the input file'


def test_the_scheme_typo_is_not_swallowed_by_the_normalisation():
    """The defect underneath the defect. The old normalisation prepended https:// to anything that
    did not start with `http`, so `htp://example.org` became `https://htp://example.org`, whose
    scheme is https, and the scheme test never saw the typo it exists to catch."""
    with pytest.raises(AddressRejected) as e:
        auditable_url('htp://example.org')
    assert 'htp' in e.value.reason


def test_a_port_limit_applies_only_where_it_is_asked_for():
    """The web endpoint reads only the standard ports; the command line accepts `localhost`, and a
    site served on a development machine is rarely on 80."""
    assert auditable_url('http://localhost:8000/') == 'http://localhost:8000/'
    with pytest.raises(AddressRejected):
        auditable_url('http://localhost:8000/', ports=(80, 443))


# ------------------------------------------------------- a string that is not an address, in a run


@pytest.mark.parametrize('raw', ['hello world', 'htp://example.org', 'https://example.org/a b'])
def test_a_string_that_is_not_an_address_gets_no_verdict(raw, monkeypatch, capsys):
    """The defect. No browser is started, no result is printed, and the exit code is not 0."""
    seen = []
    monkeypatch.setattr(CLI, 'audit_async', _recording_stub(seen))
    assert CLI.main(['--json', raw]) == CLI.EXIT_INPUT_REJECTED
    got = capsys.readouterr()
    assert seen == [], 'a string that is not an address must never reach the audit'
    assert [l for l in got.out.splitlines() if l.strip()] == [], (
        'a rejected input must produce no result line at all, and above all no verdict')
    assert 'unreachable' not in got.out and 'unreachable' not in got.err
    assert repr(raw) in got.err or raw in got.err, 'the rejected string has to be named'


def test_the_valid_addresses_of_a_mixed_list_are_still_audited(monkeypatch, capsys, tmp_path):
    """Two valid and two not. The valid ones are read, the others are named, nothing is dropped
    silently, the count is in the summary, and the file holds only what was read."""
    out = tmp_path / 'out.jsonl'
    seen = []
    monkeypatch.setattr(CLI, 'audit_async', _recording_stub(seen))
    code = CLI.main(['--json', '--output', str(out),
                     'first.org', 'hello world', 'second.org', 'htp://third.org'])
    assert code == CLI.EXIT_INPUT_REJECTED
    got = capsys.readouterr()
    assert seen == ['first.org', 'second.org']
    lines = [json.loads(l) for l in got.out.splitlines() if l.strip()]
    assert [r['url'] for r in lines] == ['first.org', 'second.org']
    written = [json.loads(l) for l in out.read_text(encoding='utf-8').splitlines() if l.strip()]
    assert [r['url'] for r in written] == ['first.org', 'second.org'], (
        'a row in an output file says a site was read, so a rejected input cannot be in one')
    assert 'hello world' in got.err and 'htp://third.org' in got.err
    assert 'audited 2 of the 4 strings given' in got.err
    assert '2 were not addresses' in got.err


def test_a_store_file_never_holds_a_rejected_input(monkeypatch, capsys, tmp_path):
    """`--store` is passed through to the audit, so the proof is that the audit was never called for
    the rejected string: a store row implies a page was read and kept."""
    seen = []
    monkeypatch.setattr(CLI, 'audit_async', _recording_stub(seen))
    store = tmp_path / 'store.jsonl'
    assert CLI.main(['--json', '--store', str(store), 'hello world']) == CLI.EXIT_INPUT_REJECTED
    assert seen == []
    assert not store.exists(), 'nothing was read, so no capture may exist'


def test_a_wholly_rejected_list_does_not_exit_zero(monkeypatch, capsys):
    seen = []
    monkeypatch.setattr(CLI, 'audit_async', _recording_stub(seen))
    assert CLI.main(['--json', 'hello world', 'htp://x.org']) == CLI.EXIT_INPUT_REJECTED
    assert seen == []
    assert 'audited nothing' in capsys.readouterr().err


def test_the_rejected_input_code_is_its_own(monkeypatch):
    """It is not 0, which claims the list was audited; not 2, which means the command line would not
    parse, when on a --from-file run the offending string is a line of somebody's spreadsheet; and
    not 4, which means a stage ran over its input and produced nothing."""
    assert CLI.EXIT_INPUT_REJECTED == 6
    assert CLI.EXIT_INPUT_REJECTED not in (CLI.EXIT_OK, CLI.EXIT_USAGE, CLI.EXIT_NO_BROWSER,
                                           CLI.EXIT_NOTHING, CLI.EXIT_SHEET_REJECTED, 1)


def test_a_missing_browser_still_outranks_a_rejected_input(monkeypatch, capsys):
    """Both wrong at once. The browser is the more serious statement, because it means nothing was
    read at all, so it is the one the exit code carries."""
    from langaccess.core import BrowserUnavailable

    async def fake(u, deep=False, timeout=None):
        raise BrowserUnavailable(
            'langaccess needs a browser: python -m playwright install chromium')

    monkeypatch.setattr(CLI, 'audit_async', fake)
    assert CLI.main(['--json', 'good.org', 'hello world']) == CLI.EXIT_NO_BROWSER
    err = capsys.readouterr().err
    assert 'hello world' in err and 'playwright install chromium' in err


def test_a_list_read_from_a_file_is_checked_the_same_way(monkeypatch, capsys, tmp_path):
    """The case the defect matters in. A thousand-line file with four typos in it."""
    f = tmp_path / 'sites.txt'
    f.write_text('first.org\nhtp://second.org\n# a comment\nthird.org\n', encoding='utf-8')
    seen = []
    monkeypatch.setattr(CLI, 'audit_async', _recording_stub(seen))
    assert CLI.main(['--json', '--from-file', str(f)]) == CLI.EXIT_INPUT_REJECTED
    assert seen == ['first.org', 'third.org']
    assert 'htp://second.org' in capsys.readouterr().err


# ---------------------------------------------------------------- --from-file that cannot be read


def test_a_from_file_path_that_does_not_exist_is_one_line_and_not_a_traceback(capsys, tmp_path):
    """It exited 1 through a traceback ending in `_urls_from_file`. 1 is the code reserved for this
    tool having crashed, and the path the user mistyped was not in the message at all."""
    missing = tmp_path / 'nope.txt'
    with pytest.raises(SystemExit) as e:
        CLI.main(['--json', '--from-file', str(missing)])
    assert e.value.code == CLI.EXIT_USAGE
    err = capsys.readouterr().err
    assert str(missing) in err and 'does not exist' in err
    assert 'Traceback' not in err and '_urls_from_file' not in err


def test_a_directory_given_to_from_file_is_named_as_one(capsys, tmp_path):
    """A directory raises IsADirectoryError on POSIX and PermissionError on Windows, and the second
    would be reported as a file this account may not read."""
    with pytest.raises(SystemExit) as e:
        CLI.main(['--json', '--from-file', str(tmp_path)])
    assert e.value.code == CLI.EXIT_USAGE
    err = capsys.readouterr().err
    assert 'is a directory' in err and 'Traceback' not in err


def test_a_from_file_that_is_not_utf8_is_named_as_that(capsys, tmp_path):
    """A spreadsheet, a gzipped run file or a UTF-16 export, handed to --from-file."""
    f = tmp_path / 'utf16.txt'
    f.write_bytes('first.org\nsecond.org\n'.encode('utf-16'))
    with pytest.raises(SystemExit) as e:
        CLI.main(['--json', '--from-file', str(f)])
    assert e.value.code == CLI.EXIT_USAGE
    err = capsys.readouterr().err
    assert 'not UTF-8' in err and 'Traceback' not in err


def test_an_empty_from_file_answers_the_way_it_always_did(capsys, tmp_path):
    """The behaviour the three above were made consistent with: one sentence, and EXIT_USAGE."""
    f = tmp_path / 'empty.txt'
    f.write_text('', encoding='utf-8')
    with pytest.raises(SystemExit) as e:
        CLI.main(['--json', '--from-file', str(f)])
    assert e.value.code == CLI.EXIT_USAGE
    assert 'no URLs to audit' in capsys.readouterr().err


def test_calibrate_answers_a_missing_list_the_same_way(capsys, tmp_path):
    """`calibrate --from-file` reads the list through the same function and used to raise the same
    traceback."""
    with pytest.raises(SystemExit) as e:
        CLI.main(['calibrate', '--from-file', str(tmp_path / 'nope.txt')])
    assert e.value.code == CLI.EXIT_USAGE
    assert 'does not exist' in capsys.readouterr().err


# ---------------------------------------------------------------------- --output without --json


def test_output_without_json_says_it_is_being_ignored(monkeypatch, capsys, tmp_path):
    out = tmp_path / 'out.jsonl'
    seen = []
    monkeypatch.setattr(CLI, 'audit_async', _recording_stub(seen))
    assert CLI.main(['--output', str(out), 'first.org']) == CLI.EXIT_OK
    err = capsys.readouterr().err
    assert err.count('--output is ignored') == 1, 'said once, not once per address'
    assert 'Add --json' in err
    assert seen == ['first.org'], 'the combination is a warning and the run continues'
    assert not out.exists()


def test_output_without_json_is_said_once_on_a_long_run(monkeypatch, capsys, tmp_path):
    seen = []
    monkeypatch.setattr(CLI, 'audit_async', _recording_stub(seen))
    urls = ['s%d.org' % i for i in range(12)]
    assert CLI.main(['--output', str(tmp_path / 'out.jsonl')] + urls) == CLI.EXIT_OK
    assert capsys.readouterr().err.count('--output is ignored') == 1


def test_output_without_json_is_said_on_the_rejudge_path_too(capsys, tmp_path):
    """The half of the defect that was still silent. `--rejudge` returns before the sentence used to
    be printed, so a re-judgement asked to write a file wrote nothing and said nothing."""
    store = tmp_path / 'store.jsonl'
    store.write_text(json.dumps({'url': 'https://first.org', 'verdict': 'english_only',
                                 'pages': []}) + '\n', encoding='utf-8')
    out = tmp_path / 'out.jsonl'
    CLI.main(['--rejudge', str(store), '--output', str(out)])
    err = capsys.readouterr().err
    assert err.count('--output is ignored') == 1
    assert not os.path.exists(str(out))


# ------------------------------------------------------------------- --rejudge that cannot be read


def _rejudge_refusal(argv, capsys):
    """`--rejudge` on the given path, returning what a person was told. Never a traceback."""
    with pytest.raises(SystemExit) as e:
        CLI.main(argv)
    assert e.value.code == CLI.EXIT_USAGE
    return capsys.readouterr().err


def test_a_rejudge_path_that_does_not_exist_is_one_line_and_not_a_traceback(capsys, tmp_path):
    """Found on 2026-08-08 the same way `--from-file` was: the tool exited 1, the code reserved for
    having crashed, with a traceback ending inside `read_store`."""
    err = _rejudge_refusal(['--rejudge', str(tmp_path / 'nope.jsonl')], capsys)
    assert 'does not exist' in err and '--store' in err
    assert 'Traceback' not in err


def test_a_rejudge_file_that_is_not_json_is_named_as_that(capsys, tmp_path):
    bad = tmp_path / 'notastore.jsonl'
    bad.write_text('this is not json\n', encoding='utf-8')
    err = _rejudge_refusal(['--rejudge', str(bad)], capsys)
    assert 'not a capture this can read' in err
    assert 'Traceback' not in err


def test_a_rejudge_name_ending_gz_on_bytes_that_are_not_gzip(capsys, tmp_path):
    """A store is written compressed when its name ends .gz, so the name is read as a promise about
    the bytes. A file renamed by hand breaks that promise inside the gzip module."""
    bad = tmp_path / 'store.jsonl.gz'
    bad.write_bytes(b'{"url": "https://first.org"}\n')
    err = _rejudge_refusal(['--rejudge', str(bad)], capsys)
    assert 'not a capture this can read' in err
    assert 'Traceback' not in err


def test_a_rejudge_file_of_json_that_is_not_captures(capsys, tmp_path):
    """Valid JSON, one object per line, and nothing in it a judgement can be made from. This one
    raised nothing at all: every line came back `unreachable` with an empty address, which is the
    address defect wearing a different flag, so it is refused by the count of rows naming a site."""
    bad = tmp_path / 'other.jsonl'
    bad.write_text(''.join(json.dumps({'a': i}) + '\n' for i in range(3)), encoding='utf-8')
    err = _rejudge_refusal(['--rejudge', str(bad)], capsys)
    assert 'not a capture' in err and 'unreachable' in err
    assert 'Traceback' not in err
    assert 'verdict' not in capsys.readouterr().out


def test_a_capture_whose_sites_failed_is_still_judged(capsys, tmp_path):
    """The guard above must not refuse a real capture. A run that could not read a site stores the
    row with no pages, and a store of nothing but those rows is a legitimate thing to re-judge."""
    store = tmp_path / 'store.jsonl'
    store.write_text(''.join(json.dumps({'url': 'https://s%d.org' % i, 'pages': []}) + '\n'
                             for i in range(3)), encoding='utf-8')
    assert CLI.main(['--rejudge', str(store)]) == CLI.EXIT_OK
    out = capsys.readouterr().out
    assert out.count('unreachable') == 3 and 'https://s2.org' in out


def test_a_directory_given_to_rejudge_is_named_as_one(capsys, tmp_path):
    d = tmp_path / 'adir'
    d.mkdir()
    err = _rejudge_refusal(['--rejudge', str(d)], capsys)
    assert str(d) in err
    assert 'Traceback' not in err
