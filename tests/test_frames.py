# -*- coding: utf-8 -*-
"""A roster CSV in, a tidy table out: read_roster and to_frame."""
import pytest

import langaccess as LA


def test_read_roster_reads_url_and_sector_and_skips_blank_rows(tmp_path):
    p = tmp_path / 'roster.csv'
    p.write_text('url,sector,name\n'
                 'https://a.org,nonprofit,A\n'
                 ',government,a blank address is not audited\n'
                 'https://b.gov,government,B\n', encoding='utf-8')
    urls, sectors = LA.read_roster(str(p))
    assert urls == ['https://a.org', 'https://b.gov']
    assert sectors == ['nonprofit', 'government']


def test_read_roster_without_a_sector_column_leaves_it_empty(tmp_path):
    p = tmp_path / 'r.csv'
    p.write_text('url\nhttps://a.org\n', encoding='utf-8')
    urls, sectors = LA.read_roster(str(p))
    assert urls == ['https://a.org'] and sectors == ['']


def test_read_roster_needs_a_url_column(tmp_path):
    p = tmp_path / 'r.csv'
    p.write_text('site,sector\nhttps://a.org,x\n', encoding='utf-8')
    with pytest.raises(ValueError):
        LA.read_roster(str(p))


def test_to_frame_joins_on_requested_url_and_flags_the_weak_cell():
    pytest.importorskip('pandas')
    r1 = LA.Result(url='https://landed.gov/en', requested_url='https://a.gov',
                   verdict='true_multilingual', languages=['English', 'Spanish'],
                   sector='government')
    r2 = LA.Result(url='https://b.org', requested_url='https://b.org',
                   verdict='english_only', sector='nonprofit')
    df = LA.to_frame([r1, r2])
    assert list(df.columns) == list(LA.FRAME_COLUMNS)
    # the join key is the requested address, not where the browser landed
    assert list(df['requested_url']) == ['https://a.gov', 'https://b.org']
    assert df.loc[0, 'url'] == 'https://landed.gov/en'
    assert df.loc[0, 'languages'] == 'English; Spanish'
    # the one stratum caveat is carried into the table itself
    assert df.loc[0, 'sector_caveat'] and not df.loc[1, 'sector_caveat']


def test_to_frame_accepts_the_dicts_to_dict_returns():
    pytest.importorskip('pandas')
    r = LA.Result(url='https://a.org', requested_url='https://a.org', verdict='english_only')
    df = LA.to_frame([r.to_dict()])
    assert df.loc[0, 'verdict'] == 'english_only'
