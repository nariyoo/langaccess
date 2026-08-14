# -*- coding: utf-8 -*-
"""The queue of readings a person has to settle, and the three ways a queue lies.

A CEILING SHIPPED AS A VERDICT IS A CEILING NOBODY ACTS ON. `unreachable`, a thin `english_only` and
a translation control this package cannot name are all readings it cannot settle, and all three go
out today as numbers in a table beside readings it can. The tests here hold the predicate to the
record: it reads `verdict`, `read_quality` and `authorship` and nothing else, it flags the four
states the package itself calls unsettled, and it leaves alone the verdicts that rest on something
FOUND, whose thin search is not a doubt about what was found.

AN EMPTY STAGE REPORTED AS A FINISHED ONE. Six distinct instances of it in this project, and a work
queue is the shape that invites the seventh: "no site needs a person" and "the predicate never
fired" print the same way. So a run holding no records stops, a queue holding no rows refuses to
write a sheet, and an ingest that applied nothing says the sentence.

A HAND VERDICT THAT HIDES INSIDE A MACHINE ONE. Once a person's answer is written into the same
field the crawl writes, no later reader can ask what share of a figure came from a person. Every
hand coding lands as evidence of its own, carrying the verdict it replaced, and the mechanism it
carries is outside OWN_MECHANISMS, so `counted_evidence` can never count it back into a judgement.
"""
import json

import pytest

from langaccess import core as LA
from langaccess import (needs_human, unsettled_kind, unsettled_reason, review_queue, review_row,
                        review_text, write_review, read_review, ingest_review, ingest_text,
                        hand_coding, SheetRejected, HAND_CODING, REVIEW_COLUMNS)
from langaccess import cli as CLI
from langaccess.review import (DEAD_CONTROL, KIND_ORDER, KIND_TITLE, NO_CLASS, OFF_SITE_DECLARATION,
                               THIN_ABSENCE, UNNAMED_CONTROL, UNREAD)


def _quality(pages=9, sufficient=True, **kw):
    q = {'pages_read': pages, 'unread': 0, 'unread_locale_links': 0, 'shallow': pages < 3,
         'budget_exhausted': False, 'clock_exhausted': False, 'reads_timed_out': 0,
         'reads_failed': 0, 'escalated': False, 'sufficient': sufficient}
    q.update(kw)
    return q


def _rec(url, verdict='true_multilingual', languages=('English', 'Spanish'), **kw):
    rec = {'url': url, 'verdict': verdict, 'languages': list(languages), 'evidence': [],
           'audited_at': '2026-08-01T09:00:00Z', 'tool_version': '0.1.0', 'note': '',
           'machine_translation': '', 'pages_read': 9, 'switcher_languages': [],
           'switcher_unresolved': 0, 'read_quality': _quality()}
    rec.update(kw)
    return rec


def _unread(url='https://gone.org/', note='bot wall'):
    return _rec(url, 'unreachable', (), note=note, pages_read=0,
                read_quality=_quality(0, False, shallow=True))


def _thin(url='https://thin.org/'):
    return _rec(url, 'english_only', ('English',), pages_read=2,
                read_quality=_quality(2, False, shallow=True, unread=11, unread_locale_links=4))


def _write_run(tmp_path, name, records):
    path = tmp_path / name
    with open(path, 'w', encoding='utf-8') as fh:
        for r in records:
            fh.write(json.dumps(r, ensure_ascii=False) + '\n')
    return str(path)


def _fill(sheet, **cells):
    """Fill every row of a written sheet with the same cells, as a coder filling it in would."""
    rows = read_review(sheet)
    for row in rows:
        row.update(cells)
    return rows


# ------------------------------------------------------------ the predicate
def test_a_site_that_was_not_read_always_needs_a_person():
    """Nothing is established about its languages in either direction, so there is no reading to
    disagree with and only a person can make one."""
    r = _unread()
    assert needs_human(r) and unsettled_kind(r) == UNREAD


def test_an_absence_claim_on_a_search_too_thin_to_carry_it_needs_a_person():
    r = _thin()
    assert needs_human(r) and unsettled_kind(r) == THIN_ABSENCE


def test_a_record_holding_no_class_needs_a_person():
    """A blank read as a class is how a gap becomes a finding."""
    assert unsettled_kind(_rec('https://x.org/', '', ())) == NO_CLASS
    assert unsettled_kind(_rec('https://x.org/', 'maybe', ())) == NO_CLASS


def test_an_english_only_reading_with_no_read_quality_at_all_needs_a_person():
    """The absence claim is worth what the search was worth, and this record does not say what the
    search was."""
    r = _rec('https://old.org/', 'english_only', ('English',))
    r.pop('read_quality')
    assert needs_human(r) and unsettled_kind(r) == THIN_ABSENCE


def test_a_thin_search_that_found_something_is_not_in_the_queue():
    """The one boundary that decides the size of this queue. `true_multilingual` and
    `machine_translate` rest on something FOUND, and a thin search that found it is right for the
    same reason a thorough one is; putting them in the queue would put most of a run in it."""
    for verdict in ('true_multilingual', 'machine_translate'):
        r = _rec('https://found.org/', verdict, ('English', 'Spanish'), pages_read=1,
                 read_quality=_quality(1, False, shallow=True))
        assert not needs_human(r), verdict


def test_an_english_only_reading_on_a_sufficient_search_is_not_in_the_queue():
    assert not needs_human(_rec('https://ok.org/', 'english_only', ('English',)))


def test_a_language_menu_this_package_cannot_name_does_not_by_itself_queue_a_settled_site():
    """The menu is not the verdict. The count is on the record and the sheet prints it, so a coder
    queueing those sites by hand has the number; no reading enters the queue on it alone."""
    r = _rec('https://menu.org/', 'true_multilingual', ('English', 'Spanish'),
             switcher_languages=['Spanish'], switcher_unresolved=7)
    assert not needs_human(r)


def test_a_control_this_package_cannot_name_goes_to_a_person_and_moves_no_class():
    """The fourth kind, added 2026-08-05, and the decision it stands in for.

    A control labelled Translate, no vendor pattern that can name it, and no non-English text. The
    alternative on the table was to floor such a site at machine_translate, and over the county-gap
    draw that rule would have named 44 sites nothing else names and been wrong on three of them,
    all three in the class the instrument exists to separate. So the reading does not move and the
    site goes on the sheet: the verdict is the one the reading already reached, and what is
    unsettled is the control.
    """
    r = _rec('https://control.org/', 'english_only', ('English',),
             authorship=LA.AUTHOR_UNKNOWN_WIDGET)
    assert needs_human(r)
    assert unsettled_kind(r) == UNNAMED_CONTROL
    assert unsettled_reason(r) and 'Translate' in unsettled_reason(r)
    # the row a coder gets carries the verdict that still stands, unchanged
    assert review_row(r)['verdict'] == 'english_only'
    # and the value cannot arrive on a site where a vendor WAS named, so a named site is not queued
    named = _rec('https://named.org/', 'machine_translate', ('English',),
                 machine_translation='Google Translate')
    assert not needs_human(named)


def test_an_unnameable_control_on_a_thin_search_says_both_things():
    """A site can be in this state and resting its absence claim on too thin a search, and a coder
    who is told only one of the two has been told the wrong half. The control comes first because
    one click settles it; the search clause is carried along and not dropped."""
    r = _rec('https://both.org/', 'english_only', ('English',), pages_read=2,
             authorship=LA.AUTHOR_UNKNOWN_WIDGET,
             read_quality=_quality(2, False, shallow=True, unread=11))
    assert unsettled_kind(r) == UNNAMED_CONTROL
    reason = unsettled_reason(r)
    assert 'Translate' in reason and '2 pages read' in reason and 'too thin' in reason


def test_an_unnameable_control_beside_a_language_the_site_wrote_is_not_queued():
    """`unknown_widget` is only ever reached when nothing else is, so a site with a real finding
    keeps its authorship and its place outside the queue. The button is still there; it is no longer
    the only thing anybody saw."""
    r = _rec('https://both.org/', 'true_multilingual', ('English', 'Spanish'),
             authorship=LA.AUTHOR_AUTHORED)
    assert not needs_human(r)


def _off(url='https://lapsed.org/', alternates=1, off=('Turkish',), languages=('English',)):
    """A reading whose declaration points somewhere else, as a stored row."""
    return _rec(url, verdict='english_only', languages=list(languages),
                declared_off_site={'alternates': alternates, 'languages': list(off)})


def test_a_declaration_that_only_points_elsewhere_goes_to_a_person():
    """One county whose document declares Turkish and gives the address of a Turkish gambling
    domain, because the county's own domain has lapsed. `declared_languages` reports the language,
    which is true of the bytes; whether that other domain is the county's is what a person settles,
    and the alternative, taking the language away, was measured and was wrong on eleven of nineteen
    hand-read moves."""
    assert unsettled_kind(_off()) == OFF_SITE_DECLARATION
    assert needs_human(_off())


def test_the_reason_names_the_language_and_the_count_and_asks_the_question():
    reason = unsettled_reason(_off(alternates=3))
    assert 'Turkish' in reason and '3 alternates' in reason
    assert 'lapsed' in reason and 'second domain of its own' in reason, (
        'the coder has to be told what the two answers are, not just that there is a question')


def test_the_sheet_carries_where_the_declaration_pointed():
    row = review_row(_off())
    assert row['declared_off_site'] == (
        '1 alternate on another site: Turkish named there and nowhere on this one')
    assert 'declared_off_site' in REVIEW_COLUMNS


def test_an_alternate_that_left_but_named_nothing_new_is_not_a_question():
    """The observation is not the queue. A site can publish its Spanish on its own domain AND link a
    partner's Portuguese; the Spanish is on the record from an address here, so nothing is unsettled
    about what the site publishes."""
    assert unsettled_kind(_off(off=(), alternates=3)) == ''
    assert not needs_human(_off(off=(), alternates=3))


def test_a_language_the_crawl_read_for_itself_is_not_unsettled_by_a_second_domain():
    """Both halves are required. A site whose pages were read in Spanish has an answer already."""
    rec = _off(languages=('English', 'Spanish'))
    assert unsettled_kind(rec) == ''


def test_a_language_found_here_and_also_declared_elsewhere_is_settled():
    """One youth services organization publishes its Chinese and Korean at addresses on its own
    site, where the crawl read them, and declares alternates on its own second domain. An
    earlier form of this predicate asked whether the found languages were a SUBSET of the ones
    declared elsewhere and queued it; there is nothing for a coder to decide about a language the
    crawl read for itself."""
    rec = _off(languages=('Chinese', 'English', 'Korean'),
               off=('Chinese', 'Korean', 'Spanish'), alternates=3)
    assert unsettled_kind(rec) == ''


def test_a_site_whose_own_pages_carry_the_declared_language_is_settled_even_when_it_is_the_only_one():
    """The strict half, on the case that reads most like the queue and is not it: a lapsed address
    answering with a squatter's page in Indonesian, which the crawl READ. The language did not
    arrive from anywhere else, and what is wrong with that record is that the site is not the
    organization's, which is a different question and not this queue's."""
    rec = _off(languages=('English', 'Indonesian'), off=('Indonesian',), alternates=2)
    assert unsettled_kind(rec) == ''


def test_a_record_written_before_the_field_existed_asks_nothing():
    """`declared_off_site` is new, and a stored run from last week does not carry it. Absent has to
    mean nothing was observed, not that something was."""
    rec = _rec('https://old.org/', verdict='english_only', languages=['English'])
    rec.pop('declared_off_site', None)
    assert 'declared_off_site' not in rec
    assert unsettled_kind(rec) == ''
    assert review_row(rec)['declared_off_site'] == ''


def test_a_site_that_was_never_read_is_reported_as_unread_and_not_as_a_declaration():
    """Order matters between the kinds. `unreachable` is the stronger fact: nothing was established
    about the site in either direction, and a declaration on a page nobody read is not the thing to
    put in front of the coder."""
    rec = _off()
    rec['verdict'] = 'unreachable'
    assert unsettled_kind(rec) == UNREAD


def test_the_off_site_question_is_asked_before_the_thin_search_and_carries_it():
    """Ordering, on the precedent the unnamed-control kind set. A site whose record names a language
    only from another site is nearly always ALSO resting an absence on too little reading, because a
    crawl that found no non-English text is what puts it there. Of the two sentences, the address is
    the one a coder acts on in a single look, so it is the kind; the thin-search clause is carried
    along in the reason rather than dropped."""
    rec = _off()
    rec['read_quality'] = _quality(pages=1, sufficient=False)
    assert unsettled_kind(rec) == OFF_SITE_DECLARATION
    reason = unsettled_reason(rec)
    assert 'Open the address' in reason
    assert 'too thin to rest it on' in reason, (
        'the thin search is a second fact the coder needs and it was dropped'
    )


def test_a_site_that_was_read_enough_and_declares_only_elsewhere_is_still_asked_about():
    """And the kind does not depend on the search being thin: a site read to its budget that found
    only English, and names Turkish on the word of another domain, is the same question."""
    rec = _off()
    rec['read_quality'] = _quality(pages=15, sufficient=True)
    assert unsettled_kind(rec) == OFF_SITE_DECLARATION


def test_every_queue_kind_is_printed_and_titled():
    """A kind the summary does not iterate is a kind nobody is told about.

    `review_text` held a hand-written tuple of four when a fifth was added on 2026-08-05: the site
    went into the sheet, the sheet was right, and the line a person reads did not mention it. That
    is this project's most frequent bug, a stage producing something and reporting nothing, in the
    one module written to prevent it.
    """
    assert set(KIND_ORDER) == set(KIND_TITLE), (
        'a queue kind is missing from the printed order or from the titles: %s'
        % sorted(set(KIND_ORDER) ^ set(KIND_TITLE)))
    assert len(KIND_ORDER) == len(set(KIND_ORDER))
    for kind, title in KIND_TITLE.items():
        assert len(title.strip()) > 15, 'the title for %s says nothing a coder can act on' % kind


def test_the_summary_names_the_kind_of_every_site_it_counted():
    """The count and the breakdown are taken from the same queue, so they cannot disagree."""
    q = review_queue([_unread(), _thin(), _off()])
    assert q['unsettled'] == 3
    text = review_text(q)
    for kind in q['kinds']:
        assert KIND_TITLE[kind] in text, (
            '%d sites are in the queue as %s and the summary does not say so'
            % (q['kinds'][kind], kind))
    assert sum(q['kinds'].values()) == q['unsettled']


def test_the_predicate_reads_a_result_object_and_a_stored_row_alike():
    r = LA.Result(url='https://x.org/', verdict='unreachable', note='bot wall')
    assert needs_human(r) and needs_human(r.to_dict())


def test_the_reason_is_a_sentence_a_person_can_act_on_and_not_a_code():
    reasons = [unsettled_reason(_unread()), unsettled_reason(_thin()),
               unsettled_reason(_rec('https://x.org/', '', ()))]
    for kind, reason in zip((UNREAD, THIN_ABSENCE, NO_CLASS), reasons):
        assert kind not in reason, 'the sheet carries the sentence, not the code'
        assert len(reason.split()) > 8 and reason.endswith('.')
    assert 'bot wall' in reasons[0], 'the note is what separates an address worth opening by hand'
    assert '2 pages read' in reasons[1] and 'locale tree' in reasons[1]
    assert 'fewer than 3 pages' not in reasons[1], 'one fact should not charge a reader twice'
    assert 'no verdict' in reasons[2]


def test_a_site_no_page_answered_for_says_that_and_not_that_it_read_too_few():
    assert review_row(_unread())['crawl_stopped_by'] == 'no page answered'


def test_a_settled_reading_has_no_reason():
    assert unsettled_reason(_rec('https://ok.org/')) == ''


# ------------------------------------------------------------ the row a coder decides from
def test_the_row_carries_everything_a_coder_needs_without_leaving_the_sheet():
    r = _thin()
    r['evidence'] = [{'mechanism': 'inline_text', 'url': 'https://thin.org/servicios',
                      'quote': 'Nuestros servicios son gratuitos', 'language': 'Spanish'}]
    r['switcher_languages'] = ['Spanish', 'Vietnamese']
    r['switcher_unresolved'] = 3
    r['machine_translation'] = 'Google Translate'
    row = review_row(r)
    assert row['url'] == 'https://thin.org/' and row['verdict'] == 'english_only'
    assert row['audited_at'] == '2026-08-01T09:00:00Z'
    assert row['pages_read'] == 2
    assert '11 addresses were found and not read' in row['crawl_stopped_by']
    assert row['languages'] == 'English'
    assert row['widget'] == 'Google Translate'
    assert 'Spanish, Vietnamese' in row['switcher']
    assert '+3 this tool cannot name' in row['switcher']
    assert 'https://thin.org/servicios' in row['evidence'] and 'servicios' in row['evidence']
    assert list(row) == list(REVIEW_COLUMNS), 'the row is the sheet, in the sheet order'


def test_the_columns_a_person_fills_in_come_out_blank():
    row = review_row(_thin())
    for col in ('human_verdict', 'human_languages', 'note', 'coder', 'coded_at'):
        assert row[col] == ''


def test_a_crawl_that_simply_finished_says_so_rather_than_leaving_the_cell_empty():
    r = _rec('https://x.org/', 'english_only', ('English',),
             read_quality=_quality(4, False))
    assert 'ran out of addresses' in review_row(r)['crawl_stopped_by']


# ------------------------------------------------------------ the queue and the sheet
def test_the_queue_reports_the_count_it_was_drawn_from_beside_the_count_it_found():
    q = review_queue([_unread(), _thin(), _rec('https://ok.org/'), _rec('https://x.org/', '', ())])
    assert q['records'] == 4 and q['unsettled'] == 3 and q['settled'] == 1
    assert q['kinds'] == {UNREAD: 1, THIN_ABSENCE: 1, NO_CLASS: 1}
    text = review_text(q)
    assert '4 records read' in text and 'need a person   3 sites of 4' in text


def test_a_run_where_nothing_needs_a_person_writes_no_sheet_and_says_so(tmp_path):
    q = review_queue([_rec('https://ok.org/'), _rec('https://fine.org/')])
    assert q['unsettled'] == 0
    with pytest.raises(ValueError) as e:
        write_review(q, str(tmp_path / 'review.csv'))
    assert 'nothing to review' in str(e.value)
    assert 'no sheet was written' in str(e.value)
    assert not (tmp_path / 'review.csv').exists()
    assert 'nothing to review' in review_text(q)


def test_the_sheet_is_written_with_one_row_per_unsettled_site(tmp_path):
    path = str(tmp_path / 'review.csv')
    assert write_review(review_queue([_unread(), _thin(), _rec('https://ok.org/')]), path) == 2
    rows = read_review(path)
    assert [row['url'] for row in rows] == ['https://gone.org/', 'https://thin.org/']
    assert list(rows[0]) == list(REVIEW_COLUMNS)


def test_a_quote_in_another_script_survives_the_sheet(tmp_path):
    """The sheet is opened in a spreadsheet on the coder's own machine, and the evidence column is
    where a language the reading found is quoted in its own script."""
    r = _thin()
    r['evidence'] = [{'mechanism': 'inline_text', 'url': 'https://thin.org/ko',
                      'quote': '우리 기관은 무료 상담을 제공합니다', 'language': 'Korean'}]
    path = str(tmp_path / 'review.csv')
    write_review(review_queue([r]), path)
    assert '무료 상담' in read_review(path)[0]['evidence']


def test_a_file_that_is_not_a_review_sheet_is_refused_as_one(tmp_path):
    path = tmp_path / 'other.csv'
    path.write_text('url,verdict\nhttps://a.org/,english_only\n', encoding='utf-8')
    with pytest.raises(SheetRejected) as e:
        read_review(str(path))
    assert 'human_verdict' in str(e.value)


# ------------------------------------------------------------ reading the answers home
def test_a_human_verdict_wins_over_the_machine_and_is_recorded_as_one(tmp_path):
    run = _write_run(tmp_path, 'run.jsonl', [_thin(), _rec('https://ok.org/')])
    sheet = str(tmp_path / 'review.csv')
    write_review(review_queue(run), sheet)
    rows = _fill(sheet, human_verdict='true_multilingual', human_languages='English, Korean',
                 note='the Korean pages are at /kr/, which the crawl never reached',
                 coder='NY', coded_at='2026-08-05')

    records, report = ingest_review(rows, run)
    settled = records[0]
    assert settled['verdict'] == 'true_multilingual'
    assert settled['languages'] == ['English', 'Korean']
    assert report['applied'] == ['https://thin.org/']
    assert report['verdicts'] == {'english_only -> true_multilingual': 1}

    ev = hand_coding(settled)
    assert ev is not None and ev['mechanism'] == HAND_CODING
    assert ev['machine_verdict'] == 'english_only', 'the reading it replaced is kept beside it'
    assert ev['machine_languages'] == ['English']
    assert ev['human_verdict'] == 'true_multilingual'
    assert ev['coder'] == 'NY' and ev['coded_at'] == '2026-08-05'
    assert 'the Korean pages' in ev['quote'], 'the coder\'s words are what decided it'
    assert ev['ingested_at'], 'when the answer came home is known even when the sheet is silent'
    # the site nobody was asked about is untouched, object for object
    assert records[1] == _rec('https://ok.org/')


def test_a_hand_coding_cannot_move_a_machine_judgement(tmp_path):
    """The mechanism is outside OWN_MECHANISMS on purpose. Whatever later re-reads the record, a
    hand coding sits beside the reading and cannot be counted back into one."""
    rec = _thin()
    rec['evidence'] = [{'mechanism': 'inline_text', 'url': 'https://thin.org/es',
                        'quote': 'hola', 'language': 'Spanish', 'authorship': 'authored'}]
    before = LA.counted_evidence(rec['evidence'], '')
    records, _ = ingest_review([{'url': 'https://thin.org/', 'human_verdict': 'true_multilingual',
                                 'human_languages': 'English, Spanish'}], [rec])
    after = LA.counted_evidence(records[0]['evidence'], '')
    assert HAND_CODING not in LA.OWN_MECHANISMS
    assert [e['url'] for e in after] == [e['url'] for e in before]
    assert hand_coding(records[0]) not in after


def test_a_row_nobody_finished_is_counted_and_changes_nothing(tmp_path):
    run = _write_run(tmp_path, 'run.jsonl', [_thin(), _unread()])
    sheet = str(tmp_path / 'review.csv')
    write_review(review_queue(run), sheet)
    rows = read_review(sheet)
    rows[0]['human_verdict'] = 'true_multilingual'
    records, report = ingest_review(rows, run)
    assert report['applied'] == ['https://thin.org/'] and report['blank'] == 1
    assert records[1] == _unread(), 'a coder who wrote nothing has not agreed with anything'
    assert hand_coding(records[1]) is None


def test_a_blank_language_cell_leaves_the_machine_list_and_the_word_none_clears_it():
    rows = [{'url': 'https://thin.org/', 'human_verdict': 'english_only', 'human_languages': ''}]
    records, _ = ingest_review(rows, [_thin()])
    assert records[0]['languages'] == ['English'], 'a blank cell is a coder saying nothing'

    rows[0]['human_languages'] = 'none'
    records, _ = ingest_review(rows, [_thin()])
    assert records[0]['languages'] == []
    assert hand_coding(records[0])['human_languages'] == []


def test_an_address_written_twice_in_a_run_is_settled_on_its_last_row():
    """The store appends, so the most recent reading is written last, and a hand coding of the
    address means that row. `diff_runs` and `_stored_record` read the same row."""
    early = _rec('https://one.org/', 'english_only', ('English',))
    late = _thin('https://one.org/')
    records, report = ingest_review(
        [{'url': 'https://one.org/', 'human_verdict': 'true_multilingual'}], [early, late])
    assert hand_coding(records[0]) is None
    assert records[1]['verdict'] == 'true_multilingual'
    assert report['applied'] == ['https://one.org/']


def test_an_address_written_with_and_without_its_trailing_slash_is_one_site():
    records, report = ingest_review(
        [{'url': 'HTTPS://THIN.ORG', 'human_verdict': 'unreachable'}], [_thin()])
    assert report['applied'] == ['https://thin.org/'] and records[0]['verdict'] == 'unreachable'


# ------------------------------------------------------------ the sheet that does not fit the run
def test_a_sheet_naming_an_address_the_run_does_not_hold_is_refused_whole():
    """A sheet with a wrong address in it is a sheet built against a different run, and applying the
    rows that happen to match would put half a coding round into a file and report success."""
    rows = [{'url': 'https://thin.org/', 'human_verdict': 'true_multilingual'},
            {'url': 'https://elsewhere.org/', 'human_verdict': 'english_only'}]
    with pytest.raises(SheetRejected) as e:
        ingest_review(rows, [_thin()])
    assert len(e.value.problems) == 1
    assert 'https://elsewhere.org/' in e.value.problems[0] and 'row 3' in e.value.problems[0]
    assert 'https://thin.org/' not in e.value.problems[0]


def test_every_address_that_does_not_fit_is_named_and_not_only_the_first():
    rows = [{'url': 'https://one.org/', 'human_verdict': 'english_only'},
            {'url': 'https://two.org/', 'human_verdict': 'english_only'}]
    with pytest.raises(SheetRejected) as e:
        ingest_review(rows, [_thin()])
    assert len(e.value.problems) == 2


def test_an_address_written_twice_in_a_sheet_is_refused_and_says_where():
    rows = [{'url': 'https://thin.org/', 'human_verdict': 'english_only'},
            {'url': 'https://thin.org/', 'human_verdict': 'true_multilingual'}]
    with pytest.raises(SheetRejected) as e:
        ingest_review(rows, [_thin()])
    assert 'row 3' in e.value.problems[0] and 'also on row 2' in e.value.problems[0]


def test_a_verdict_outside_the_four_classes_is_refused():
    rows = [{'url': 'https://thin.org/', 'human_verdict': 'english only'}]
    with pytest.raises(SheetRejected) as e:
        ingest_review(rows, [_thin()])
    assert "'english only'" in e.value.problems[0] and 'true_multilingual' in e.value.problems[0]


def test_a_row_with_no_address_is_refused_rather_than_skipped():
    with pytest.raises(SheetRejected) as e:
        ingest_review([{'url': '', 'human_verdict': 'english_only'}], [_thin()])
    assert 'row 2 has no address' in e.value.problems[0]


# ------------------------------------------------------------ the round trip
def test_a_run_written_to_a_sheet_and_ingested_unedited_is_the_run_it_started_as(tmp_path):
    """The property the whole feature rests on. If passing a run through the queue changes it, then
    every figure computed after a coding round differs from the one computed before it for reasons
    nobody chose."""
    run = _write_run(tmp_path, 'run.jsonl', [
        _unread(), _thin(), _rec('https://ok.org/'), _rec('https://none.org/', '', ()),
        _rec('https://widget.org/', 'machine_translate', ('English',),
             machine_translation='Google Translate', switcher_languages=['Spanish'],
             switcher_unresolved=2,
             evidence=[{'mechanism': 'inline_text', 'url': 'https://widget.org/es',
                        'quote': 'servicios gratuitos', 'language': 'Spanish'}])])
    sheet = str(tmp_path / 'review.csv')
    assert write_review(review_queue(run), sheet) == 3

    out = str(tmp_path / 'out.jsonl')
    assert CLI.main(['ingest', sheet, run, '-o', out]) == CLI.EXIT_OK

    before = [json.loads(line) for line in open(run, encoding='utf-8')]
    after = [json.loads(line) for line in open(out, encoding='utf-8')]
    assert after == before
    assert len(after) == 5
    assert all(hand_coding(rec) is None for rec in after)


# ------------------------------------------------------------ the command line
def test_the_review_subcommand_writes_the_sheet_and_prints_the_two_counts(tmp_path, capsys):
    run = _write_run(tmp_path, 'run.jsonl', [_unread(), _thin(), _rec('https://ok.org/')])
    sheet = str(tmp_path / 'review.csv')
    assert CLI.main(['review', run, '-o', sheet]) == CLI.EXIT_OK
    out = capsys.readouterr().out
    assert '3 records read' in out and 'need a person   2 sites of 3' in out
    assert 'langaccess ingest' in out, 'the sheet says what to type next'
    assert len(read_review(sheet)) == 2


def test_a_review_that_finds_nothing_says_so_and_exits_non_zero_on_request(tmp_path, capsys):
    run = _write_run(tmp_path, 'run.jsonl', [_rec('https://ok.org/')])
    sheet = str(tmp_path / 'review.csv')
    assert CLI.main(['review', run, '-o', sheet]) == CLI.EXIT_OK
    assert 'nothing to review' in capsys.readouterr().out
    assert not (tmp_path / 'review.csv').exists()
    assert CLI.main(['review', run, '-o', sheet, '--fail-on-empty']) == CLI.EXIT_NOTHING


def test_a_run_holding_no_records_fails_whether_or_not_it_was_asked_to(tmp_path, capsys):
    """An empty INPUT is a broken stage and not an empty result, so this one does not wait to be
    asked."""
    run = _write_run(tmp_path, 'run.jsonl', [])
    assert CLI.main(['review', run, '-o', str(tmp_path / 'review.csv')]) == CLI.EXIT_NOTHING
    assert 'holds no records' in capsys.readouterr().err


def test_the_ingest_subcommand_writes_over_the_run_and_reports_what_a_person_decided(tmp_path,
                                                                                    capsys):
    run = _write_run(tmp_path, 'run.jsonl', [_thin(), _rec('https://ok.org/')])
    sheet = str(tmp_path / 'review.csv')
    assert CLI.main(['review', run, '-o', sheet]) == CLI.EXIT_OK
    capsys.readouterr()

    rows = _fill(sheet, human_verdict='true_multilingual', human_languages='English, Korean')
    with open(sheet, 'w', encoding='utf-8-sig', newline='') as fh:
        import csv as _csv
        w = _csv.DictWriter(fh, fieldnames=list(REVIEW_COLUMNS))
        w.writeheader()
        w.writerows(rows)

    assert CLI.main(['ingest', sheet, run]) == CLI.EXIT_OK
    out = capsys.readouterr().out
    assert 'hand verdicts applied   1' in out
    assert 'english_only -> true_multilingual' in out
    assert 'written to %s' % run in out
    settled = [json.loads(line) for line in open(run, encoding='utf-8')]
    assert settled[0]['verdict'] == 'true_multilingual'
    assert hand_coding(settled[0])['machine_verdict'] == 'english_only'
    assert len(settled) == 2, 'the run keeps every record it had, settled or not'


def test_an_ingest_that_applies_nothing_says_so_and_exits_non_zero_on_request(tmp_path, capsys):
    run = _write_run(tmp_path, 'run.jsonl', [_thin()])
    sheet = str(tmp_path / 'review.csv')
    assert CLI.main(['review', run, '-o', sheet]) == CLI.EXIT_OK
    capsys.readouterr()
    assert CLI.main(['ingest', sheet, run]) == CLI.EXIT_OK
    assert 'nothing was applied' in capsys.readouterr().out.lower()
    assert CLI.main(['ingest', sheet, run, '--fail-on-empty']) == CLI.EXIT_NOTHING


def test_a_refused_sheet_names_every_fault_and_writes_nothing(tmp_path, capsys):
    run = _write_run(tmp_path, 'run.jsonl', [_thin()])
    sheet = tmp_path / 'review.csv'
    sheet.write_text('url,human_verdict,human_languages,note\n'
                     'https://elsewhere.org/,true_multilingual,,\n', encoding='utf-8')
    before = open(run, encoding='utf-8').read()
    assert CLI.main(['ingest', str(sheet), run]) == CLI.EXIT_SHEET_REJECTED
    err = capsys.readouterr().err
    assert 'applied nothing' in err and 'https://elsewhere.org/' in err
    assert open(run, encoding='utf-8').read() == before


def test_a_dry_run_reports_and_writes_nothing(tmp_path, capsys):
    run = _write_run(tmp_path, 'run.jsonl', [_thin()])
    sheet = tmp_path / 'review.csv'
    sheet.write_text('url,human_verdict,human_languages,note\n'
                     'https://thin.org/,true_multilingual,"English, Korean",found it\n',
                     encoding='utf-8')
    before = open(run, encoding='utf-8').read()
    assert CLI.main(['ingest', str(sheet), run, '--dry-run']) == CLI.EXIT_OK
    out = capsys.readouterr().out
    assert 'hand verdicts applied   1' in out and 'written to' not in out
    assert open(run, encoding='utf-8').read() == before


def test_a_missing_file_is_named(tmp_path, capsys):
    run = _write_run(tmp_path, 'run.jsonl', [_thin()])
    with pytest.raises(SystemExit):
        CLI.main(['review', str(tmp_path / 'nothing.jsonl'), '-o', str(tmp_path / 'r.csv')])
    assert 'does not exist' in capsys.readouterr().err
    with pytest.raises(SystemExit):
        CLI.main(['ingest', str(tmp_path / 'nothing.csv'), run])
    assert 'does not exist' in capsys.readouterr().err


def test_the_new_words_do_not_disturb_the_audit_command_line(monkeypatch, capsys):
    """The rest of the tool keeps the flat command line it has always had."""
    async def fake(u, deep=False, timeout=None):
        return LA.Result(url=u, verdict='english_only')

    monkeypatch.setattr(CLI, 'audit_async', fake)
    assert CLI.main(['--json', 'https://review.org/', 'https://ingest.org/']) == 0
    lines = [json.loads(line) for line in capsys.readouterr().out.splitlines() if line.strip()]
    assert [r['url'] for r in lines] == ['https://review.org/', 'https://ingest.org/']


def test_the_share_of_a_figure_that_came_from_a_person_is_answerable(tmp_path):
    """The question the evidence entry exists for. A table of mixed readings has to be able to say
    how much of it a person decided."""
    records, _ = ingest_review([{'url': 'https://thin.org/', 'human_verdict': 'true_multilingual'}],
                               [_thin(), _unread(), _rec('https://ok.org/')])
    assert sum(1 for rec in records if hand_coding(rec)) == 1
    assert len(records) == 3


def test_the_ingest_summary_names_the_denominators():
    _records, report = ingest_review(
        [{'url': 'https://thin.org/', 'human_verdict': 'true_multilingual'}], [_thin(), _unread()])
    text = ingest_text(report, written='run.jsonl')
    assert '2 records' in text and 'hand verdicts applied   1' in text
    assert 'records the machine reading still stands on   1' in text


# ---------------------------------------------------------------- the contested layer

from langaccess import review as R  # noqa: E402


def _settled_tm(widget='Google Translate', sufficiency=2, languages=('English', 'Spanish'),
                verdict='true_multilingual'):
    """A reading the package stands behind, shaped like the boundary the coders split over."""
    return {'url': 'https://x.org/', 'verdict': verdict, 'machine_translation': widget,
            'sufficiency': sufficiency, 'languages': list(languages),
            'read_quality': {'sufficient': True, 'pages_read': 15}, 'evidence': []}


def test_contested_names_the_two_shapes_and_only_on_settled_readings():
    """The two measured shapes fire, their absence is quiet, and an unsettled reading is never
    contested, because the queue and the second look answer different questions and a row in both
    would be counted twice."""
    r = _settled_tm()
    assert R.contested(r) == (R.CONTESTED_FRAGMENT, R.CONTESTED_ONE_LANGUAGE)
    assert 'coders split over' in R.contested_reason(r)
    # page-level authored text beside the widget: the boundary is passed, nothing to flag
    assert R.contested(_settled_tm(sufficiency=3)) == ()
    # no widget, one language at notice level: the one-language shape alone
    assert R.contested(_settled_tm(widget='', sufficiency=2)) == (R.CONTESTED_ONE_LANGUAGE,)
    # two non-English languages corroborate each other
    assert R.contested(_settled_tm(widget='', languages=('English', 'Spanish', 'Korean'))) == ()
    # machine_translate with one language at notice level carries the one-language shape
    assert R.contested(_settled_tm(widget='Weglot', verdict='machine_translate')) == \
        (R.CONTESTED_ONE_LANGUAGE,)
    # english_only carries neither shape however thin the page count
    assert R.contested(_settled_tm(widget='', verdict='english_only')) == ()
    # unreachable is the queue's, not this layer's
    assert R.contested({'url': 'https://x.org/', 'verdict': 'unreachable'}) == ()
    assert R.contested_reason({'url': 'https://x.org/', 'verdict': 'unreachable'}) == ''


def test_the_queue_counts_contested_apart_and_prints_it():
    """A run with one unsettled and one contested reading: the queue keeps the two counts apart,
    the sheet carries both rows with the contested one last, and the printed summary names the
    shape, because a kind the sheet holds and the summary hides is this project's most frequent
    bug wearing a different coat."""
    unread = {'url': 'https://a.org/', 'verdict': 'unreachable', 'note': 'bot wall'}
    disputed = _settled_tm(sufficiency=2, languages=('English', 'Spanish'))
    clean = _settled_tm(widget='', sufficiency=4, languages=('English', 'Spanish', 'Korean'),
                        verdict='true_multilingual')
    q = R.review_queue([unread, disputed, clean])
    assert q['records'] == 3 and q['unsettled'] == 1 and q['contested'] == 1
    assert q['settled'] == 2, 'a contested reading is settled and counted as settled'
    assert q['contested_kinds'] == {R.CONTESTED_FRAGMENT: 1, R.CONTESTED_ONE_LANGUAGE: 1}
    assert len(q['rows']) == 2 and q['rows'][0]['url'] == 'https://a.org/'
    assert 'coders split over' in q['rows'][1]['reason']
    text = R.review_text(q, output='review.csv')
    assert 'settled, in a shape the model coders split over   1 site' in text
    for kind in R.CONTESTED_KINDS:
        if q['contested_kinds'].get(kind):
            assert R.CONTESTED_TITLE[kind] in text
    assert '2 sites' in text.split('written to')[1]


def test_a_run_with_only_contested_rows_still_writes_a_sheet():
    """unsettled == 0 is not nothing-to-review when contested rows exist: the sheet is written
    and the summary says so, rather than reporting an empty queue over a sheet with rows in it."""
    q = R.review_queue([_settled_tm()])
    assert q['unsettled'] == 0 and q['contested'] == 1 and len(q['rows']) == 1
    assert 'nothing to review' not in R.review_text(q, output='review.csv')


# ---------------------------------------------------------------- depth and retry, the two layers

def test_depth_counts_pages_per_language_and_refuses_a_pageless_record():
    """A page counts for a language when the reading finds it, a bilingual page counts once for
    each, and a record without pages answers None rather than zeros, because zero says the
    languages reach nothing and no-pages says nothing was kept to measure."""
    from langaccess import depth_of, depth_run
    es = ('Ofrecemos clases gratuitas para todas las familias de la comunidad y la oficina '
          'esta abierta de lunes a viernes sin necesidad de cita previa para los vecinos.')
    en = ('We run free classes for every family in the neighborhood and the office is open '
          'weekdays with no appointment needed for any resident who walks in the door.')
    rec = {'url': 'https://x.org/', 'pages': {
        'https://x.org/': en + ' ' + en,
        'https://x.org/es': es + ' ' + es,
        'https://x.org/both': en + ' ' + es,
    }}
    d = depth_of(rec)
    assert d['pages_read'] == 3
    assert d['pages_by_language']['English'] == 2
    assert d['pages_by_language']['Spanish'] == 2
    assert abs(d['share']['Spanish'] - 2 / 3) < 1e-9
    assert abs(d['against_english']['Spanish'] - 1.0) < 1e-9
    assert depth_of({'url': 'https://x.org/', 'pages': {}}) is None
    # rule 8 reaches this module through the record's own language list: a language the
    # verdict excluded (an organization's name in its community's language) does not count here
    restricted = dict(rec, languages=['English'])
    dr = depth_of(restricted)
    assert 'Spanish' not in dr['pages_by_language'] and dr['pages_by_language']['English'] == 2
    assert 'languages_unrestricted' not in dr
    assert depth_of(rec).get('languages_unrestricted') is True
    q = depth_run([rec, {'url': 'https://empty.org/'}])
    assert q['records'] == 2 and list(q['measured']) == ['https://x.org/']
    assert q['no_pages'] == ['https://empty.org/'], 'the pageless record is named, never dropped'


def test_retry_reaudits_only_the_unread_and_stamps_how_it_read():
    """Only the rows a person would have to open are retried, the settled rows pass through
    untouched, and a retried record says it was read with the user's browser and keeps the
    clean-room verdict beside the new one, so the two observations stay separable."""
    import asyncio
    from langaccess.retry import retry_unreachable_async
    from test_engineering import _MapBrowser, _page
    page_text = ('We provide services for families across the county and '
                 'the office is open weekdays for every resident. ' * 4)
    browser = _MapBrowser({'https://gone.org/': _page(page_text)})
    run = [
        {'url': 'https://gone.org/', 'verdict': 'unreachable', 'note': 'bot wall'},
        {'url': 'https://fine.org/', 'verdict': 'english_only', 'languages': ['English'],
         'read_quality': {'sufficient': True, 'pages_read': 15}},
    ]
    records, report = asyncio.run(retry_unreachable_async(run, browser=browser))
    assert report['unread'] == 1 and report['retried'] == 1
    assert records[1] == run[1], 'the settled record passed through byte-identical'
    got = records[0]
    assert got['read_with_user_browser'] is True
    assert got['clean_room_verdict'] == 'unreachable'
    assert got['verdict'] == 'english_only'
    assert report['now_read'] == 1 and report['moved'] == [('https://gone.org/', 'english_only')]


def test_retry_refuses_the_addresses_a_run_file_could_aim_at_your_own_network():
    """The addresses come out of a FILE, and pointed at a person's own browser on their own
    network an address is an instruction: a cloud metadata service, a router's admin page, the
    debugging port itself. The retry opens http and https on 80 and 443 and nothing else, refuses
    private and loopback hosts by literal as well as by the guard inside the audit, and counts
    what it refused rather than passing over it in silence."""
    import asyncio
    from langaccess.retry import retry_unreachable_async, refused
    for bad in ('http://169.254.169.254/latest/meta-data/', 'http://192.168.1.1/admin',
                'http://127.0.0.1:9222/json/new', 'http://localhost:9222/',
                'file:///etc/passwd', 'javascript:alert(1)', 'http://example.org:8080/'):
        assert refused(bad), bad
    for ok in ('https://example.org/', 'http://example.org/', 'https://example.org:443/x'):
        assert refused(ok) == '', ok
    run = [{'url': 'http://169.254.169.254/latest/meta-data/', 'verdict': 'unreachable'}]
    records, report = asyncio.run(retry_unreachable_async(run, browser=object()))
    assert report['retried'] == 0 and len(report['refused']) == 1
    assert records[0] == run[0], 'a refused record is left exactly as it was'

def test_a_widget_that_was_worked_and_did_nothing_goes_to_a_person():
    """`machine_translate_error` says what THIS client could obtain, and only a person opening the
    address can turn that into a finding about the site. It is reported ahead of `unnamed_control`
    because a site can be in both and this is the narrower observation: the control was named,
    worked, and did nothing, which one look settles."""
    r = LA.Result(url='https://x.org/', verdict=LA.MT_ERROR,
                  machine_translation='Google Translate',
                  note=LA.CONTROL_DEAD_NOTE, rules=[12, 14, 16],
                  read_quality={'sufficient': True, 'pages_read': 15})
    assert unsettled_kind(r) == DEAD_CONTROL
    assert needs_human(r)
    why = unsettled_reason(r)
    assert 'did not change' in why and 'Open the address' in why
    assert 'one browser and not another' in why, (
        "the sentence has to say the failure may be this client's")


def test_the_queue_kinds_all_have_a_title_and_a_place_in_the_order():
    """A kind with no title prints a code at a coder, and a kind outside the order is a kind the
    summary silently drops."""
    for kind in KIND_ORDER:
        assert kind in KIND_TITLE, kind
    assert set(KIND_ORDER) == set(KIND_TITLE)

def test_the_locale_mirror_contested_shape_fires_on_the_release_number():
    from langaccess import contested as LA_contested
    """The renumbering left `15` in this predicate's third branch, and the shape went silent: rule
    17 is the mirror rule in the release numbering and 15 is the advertised route, which never
    co-occurs with machine_translate. Found by a read-only review on 2026-08-09, confirmed by
    running the predicate, and pinned here so a future renumber fails a test instead of a reader."""
    r = LA.Result(url='https://x.org/', verdict='machine_translate', rules=[12, 17],
                  sufficiency=4, authorship=LA.AUTHOR_CLIENT_WIDGET)
    assert 'locale_mirrors_over_a_reading' in LA_contested(r)
    # and the route rule, which shares the development ancestor, does not trip it
    r2 = LA.Result(url='https://x.org/', verdict='english_only', rules=[12, 14, 15],
                   sufficiency=0, authorship=LA.AUTHOR_NONE,
                   read_quality={'sufficient': True, 'pages_read': 15})
    assert not needs_human(r2), 'the premise: this reading is SETTLED, or contested is moot'
    assert 'locale_mirrors_over_a_reading' not in LA_contested(r2)

def test_the_summary_prints_every_kind_the_queue_defines():
    """The test written to catch a queue hiding one of its kinds was itself fed a fixture holding
    three of the six, so the three newest kinds were never checked to reach the printed summary."""
    rows = [
        LA.Result(url='https://a.org/', verdict='unreachable', note='bot wall'),
        LA.Result(url='https://b.org/', verdict=LA.MT_ERROR,
                  machine_translation='Google Translate', note=LA.CONTROL_DEAD_NOTE,
                  rules=[12, 14, 16], read_quality={'sufficient': True, 'pages_read': 15}),
        LA.Result(url='https://c.org/', verdict='english_only',
                  read_quality={'sufficient': False, 'pages_read': 2}),
        LA.Result(url='https://d.org/', verdict='no_such_class'),
        LA.Result(url='https://e.org/', verdict='english_only',
                  authorship=LA.AUTHOR_UNKNOWN_WIDGET,
                  read_quality={'sufficient': True, 'pages_read': 15}),
        LA.Result(url='https://f.org/', verdict='english_only',
                  declared_off_site={'alternates': 2, 'languages': ['Spanish']},
                  read_quality={'sufficient': True, 'pages_read': 15}),
    ]
    q = review_queue(rows)
    text = review_text(q)
    for kind in KIND_ORDER:
        assert KIND_TITLE[kind] in text, 'the summary does not print %r' % kind
