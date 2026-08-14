# -*- coding: utf-8 -*-
"""A roster CSV in, a tidy table out.

A study starts from a roster: a list of organizations with an address and, most often, the one
label the crawler cannot read off a page and every analysis needs, which population the address
belongs to. It ends wanting a table it can join back to that roster. These two functions are the ends
of that pipe. `read_roster` turns a CSV into the `urls` and `sectors` that `audit_many` takes, and
`to_frame` turns the results into a pandas DataFrame.

The join is on `requested_url`, the address as it was given, and never on `url`, where the browser
landed: a redirect moves `url` away from the roster, and on the 1,000-site round of 2026-08-07 it did
so for 209 of the 1,000. `to_frame` puts `requested_url` first for that reason, and falls back to
`url` only for a record written before that field existed.

pandas is an optional dependency, imported inside `to_frame` so that importing langaccess, and every
other part of it, does not require pandas. Install it with `pip install "langaccess[frame]"`.
"""
import csv

from .core import sector_caveat

# The columns `to_frame` emits, in order. The list fields are joined into one string each, so the
# frame is flat and writes to a CSV or a spreadsheet without a second pass; `to_dict()` on the
# Result keeps the structured form for a caller that wants it.
FRAME_COLUMNS = ('requested_url', 'url', 'sector', 'verdict', 'languages', 'machine_translation',
                 'authorship', 'sufficiency', 'pages_read', 'switcher_languages',
                 'audited_at', 'tool_version', 'note', 'sector_caveat')


def read_roster(path, url_col='url', sector_col='sector'):
    """Return `(urls, sectors)` from a roster CSV, ready to hand to `audit_many`.

    The file needs a column of addresses, named `url` by default, and may carry a column of sector
    labels, named `sector` by default. A row with a blank address is skipped rather than audited, so
    a trailing empty line or a gap in the sheet does not become an unreachable result. When there is
    no sector column every sector comes back empty, which is what `audit_many` treats as no label.
    """
    urls, sectors = [], []
    with open(path, newline='', encoding='utf-8-sig') as fh:
        reader = csv.DictReader(fh)
        cols = reader.fieldnames or []
        if url_col not in cols:
            raise ValueError('the roster has no %r column; its columns are %r' % (url_col, cols))
        has_sector = sector_col in cols
        for row in reader:
            u = (row.get(url_col) or '').strip()
            if not u:
                continue
            urls.append(u)
            sectors.append((row.get(sector_col) or '').strip() if has_sector else '')
    return urls, sectors


def to_frame(results):
    """A pandas DataFrame of the results, one row each, to join back to the roster on `requested_url`.

    Requires pandas. The list-valued fields (`languages`, `switcher_languages`) are joined with '; '
    so the frame is flat; `sector_caveat` is computed per row from the sector the result carries, so a
    government `true_multilingual` reading is flagged in the table itself. Accepts Results or the
    dicts `to_dict` returns.
    """
    try:
        import pandas as pd
    except ImportError as e:  # pragma: no cover - exercised only where pandas is absent
        raise ImportError('to_frame needs pandas; install it with pip install "langaccess[frame]"') \
            from e
    rows = []
    for r in results:
        d = r.to_dict() if hasattr(r, 'to_dict') else dict(r)
        rows.append({
            'requested_url': d.get('requested_url') or d.get('url', ''),
            'url': d.get('url', ''),
            'sector': d.get('sector', ''),
            'verdict': d.get('verdict', ''),
            'languages': '; '.join(d.get('languages') or []),
            'machine_translation': d.get('machine_translation', ''),
            'authorship': d.get('authorship', ''),
            'sufficiency': d.get('sufficiency', 0),
            'pages_read': d.get('pages_read', 0),
            'switcher_languages': '; '.join(d.get('switcher_languages') or []),
            'audited_at': d.get('audited_at', ''),
            'tool_version': d.get('tool_version', ''),
            'note': d.get('note', ''),
            'sector_caveat': sector_caveat(d),
        })
    return pd.DataFrame(rows, columns=list(FRAME_COLUMNS))
