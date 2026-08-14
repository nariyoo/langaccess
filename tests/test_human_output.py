# -*- coding: utf-8 -*-
"""What a person reads, held to the three things it kept getting wrong.

Every case here was found by reading the actual output rather than the code: a stage that answered
success over an empty file, a line that went missing when the only thing it had to say was a count,
and a document that told a stranger a site had no other language when nothing had been read at all.
"""
import io
import json
import os
import subprocess
import sys

import pytest

import langaccess as LA
from langaccess.cli import main


def _run(args, tmp_path):
    """The CLI in a subprocess, so the exit code is the real one a pipeline sees."""
    env = dict(os.environ, PYTHONPATH=os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), 'src'), PYTHONUTF8='1')
    return subprocess.run([sys.executable, '-m', 'langaccess'] + args,
                          capture_output=True, text=True, env=env, cwd=str(tmp_path))


def test_depth_on_a_run_holding_no_records_is_exit_nothing(tmp_path):
    """A --store path is opened for append before the first site is read, so a run that died early
    leaves a zero-byte file. This stage answered 0 over it, which is an empty result reported as a
    completed one, the failure this project has hit most often. Its siblings all answer 4."""
    p = tmp_path / 'empty.jsonl'
    p.write_text('', encoding='utf-8')
    got = _run(['depth', str(p)], tmp_path)
    assert got.returncode == 4, got.stdout + got.stderr
    assert 'holds no records' in got.stderr


def test_depth_does_not_promise_a_list_it_will_not_print(tmp_path):
    """`0 hold none and are named below` named nothing below."""
    p = tmp_path / 'empty.jsonl'
    p.write_text('', encoding='utf-8')
    got = _run(['depth', str(p)], tmp_path)
    assert 'are named below' not in got.stdout


def test_a_menu_this_tool_cannot_name_is_still_reported(capsys):
    """A page declaring hreflang alternates whose codes are outside the vocabulary has a language
    menu, and the human line was printed only when at least one name resolved, so the reader was
    told nothing while the JSON carried the count."""
    from langaccess.cli import _print_human
    r = LA.Result(url='https://x.org/', verdict='english_only', languages=['English'],
                  switcher_languages=[], switcher_unresolved=3)
    _print_human(r)
    out = capsys.readouterr().out
    assert 'switcher' in out and '3' in out
    assert 'none of which this tool can name' in out


def test_explain_says_the_same_of_a_menu_it_cannot_name():
    r = LA.Result(url='https://x.org/', verdict='english_only', languages=['English'],
                  switcher_languages=[], switcher_unresolved=2)
    assert 'none of which this tool can name' in LA.explain_text(r)


@pytest.mark.parametrize('form', ['text', 'html'])
def test_an_unreachable_report_makes_no_claim_about_the_site(form):
    """The document had two branches, an absence claim and `it rests on something that was found`,
    and `unreachable` fell into the second: nothing was read, so nothing was found either."""
    r = LA.Result(url='https://x.org/', verdict='unreachable', note='bot wall')
    doc = LA.report_text(r) if form == 'text' else LA.report_html(r)
    assert 'not a claim about the site at all' in doc
    assert 'it rests on something that was found' not in doc


@pytest.mark.parametrize('form', ['text', 'html'])
def test_a_reading_that_found_something_keeps_its_own_sentence(form):
    r = LA.Result(url='https://x.org/', verdict='machine_translate', machine_translation='Google Translate')
    doc = LA.report_text(r) if form == 'text' else LA.report_html(r)
    assert 'rests on something that was found' in doc
    assert 'not a claim about the site at all' not in doc


def test_a_quotation_in_the_review_sheet_says_it_was_cut():
    """The cell held a quote that stopped inside a word with nothing to say it had been cut."""
    from langaccess.review import _evidence_cell, QUOTE_CHARS
    long_quote = 'aviso ' * 200
    r = {'evidence': [{'mechanism': 'inline_text', 'url': 'https://x.org/es',
                       'quote': long_quote, 'language': 'Spanish'}]}
    cell = _evidence_cell(r)
    assert '..."' in cell or cell.endswith('...')
    assert 'avis"' not in cell, 'the cell still ends inside a word'

def test_the_demo_reads_four_invented_sites_with_no_browser(tmp_path):
    """A fresh install has nothing to read, and the only address this package would fetch unasked
    belongs to its author, so the first thing a new user saw was a real site and, in the printed
    evidence, that person's own writing. These four are invented and ship as a stored capture."""
    got = _run(['demo'], tmp_path)
    assert got.returncode == 0, got.stdout + got.stderr
    for verdict in ('english_only', 'machine_translate', 'true_multilingual', 'unreachable'):
        assert verdict in got.stdout, verdict
    assert 'Nothing was fetched' in got.stdout
    assert '.example/' in got.stdout, 'the demo addresses are reserved ones'


def test_the_demo_json_form_is_one_object_per_site(tmp_path):
    got = _run(['demo', '--json'], tmp_path)
    assert got.returncode == 0
    rows = [json.loads(x) for x in got.stdout.splitlines() if x.strip()]
    assert len(rows) == 4
    assert {r['verdict'] for r in rows} == {'english_only', 'machine_translate',
                                            'true_multilingual', 'unreachable'}
    assert all('demo_why' not in r for r in rows), 'the demo note is not a Result field'


def test_the_demo_capture_names_no_real_address():
    """Every page in it was written for this package; nothing here came off the web."""
    import gzip
    from urllib.parse import urlsplit
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        'src', 'langaccess', 'data', 'demo_capture.jsonl.gz')
    with gzip.open(path, 'rt', encoding='utf-8') as fh:
        recs = [json.loads(line) for line in fh if line.strip()]
    assert len(recs) == 4
    for r in recs:
        for u in [r.get('url'), r.get('requested_url')] + list((r.get('pages') or {})):
            host = urlsplit(u).hostname or ''
            assert host.endswith('.example'), u
