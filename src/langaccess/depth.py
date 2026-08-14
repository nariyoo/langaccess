# -*- coding: utf-8 -*-
"""How much of the site a language reaches, measured over a stored capture's own pages.

The classes answer whether a language is provided; this answers how far the provision goes, which
is the completeness question the Website Language Accessibility Checklist raises and no class can
carry. A site whose Spanish is one page of fifteen and a site whose Spanish mirrors the tree both
read `true_multilingual`.

    from langaccess import depth_of, depth_run
    d = depth_of(record)             # one stored capture, from read_store or a Result with pages
    d['pages_read']                  # the denominator, the pages this capture holds
    d['pages_by_language']           # {'English': 15, 'Spanish': 3, ...}, a page counted for a
                                     # language when its text carries that language's reading
    d['share']                       # {'Spanish': 0.2, ...}, against pages_read
    d['against_english']             # {'Spanish': 0.2, ...}, against the English page count,
                                     # absent when no page reads as English

Three properties, stated because each is a decision:

The measure is over the pages the capture HOLDS, so it inherits every bound of the crawl that
wrote it: a 15-page budget, the routes the crawl took, and the locale links it never fetched,
which `read_quality['unread_locale_links']` counts. A share of the read pages is not a share of
the site, and the field names say which denominator is meant.

A page counts for a language when `languages_in` finds that language in the page's text, the same
reading the classes rest on, so depth and class can never disagree about what a language is. A
page counted for two languages counts for both, since a bilingual page is one page of provision
in each.

No figure of this module has a validation measurement. No coder ever assigned a depth, so there
is no agreement number to state and none is claimed; the classes carry the validated claim and
this carries a description beside it. It moves no reading and writes no field: like `contested`,
it is a layer over a finished record, and a caller who ignores it holds exactly the reading they
held before.
"""
import collections

from .core import languages_in, read_store

ENGLISH = 'English'


def _pages(r):
    """The stored pages of one record, as {url: text}. Empty where the record kept none."""
    pages = r.get('pages') if isinstance(r, dict) else getattr(r, 'pages', None)
    if not isinstance(pages, dict):
        return {}
    out = {}
    for url, page in pages.items():
        if isinstance(page, str):
            out[url] = page
        elif isinstance(page, dict):
            text = page.get('text') or page.get('rendered') or ''
            if text:
                out[url] = text
    return out


def depth_of(record):
    """One capture's language depth, or None where the record holds no pages to measure.

    None rather than zeros, because a record without pages says nothing about depth and a zero
    would say the languages reach nothing, which is a different statement.

    Where the record carries a `languages` field, the count is RESTRICTED to those languages,
    and the restriction is rule 8 reaching into this module. The audit reads each
    page with the site's own name excluded, so an organization whose name is written in its
    community's language does not read as publishing in it; a raw re-read of the stored pages
    has no way to know that name, and without the restriction this module would report the name's
    language reaching every page of a site whose class says english_only. The verdict's language
    list already carries the exclusion, so counting within it keeps the two layers telling one
    story. A record with no `languages` field is counted unrestricted and says so.
    """
    pages = _pages(record)
    if not pages:
        return None
    counted = record.get('languages') if isinstance(record, dict) else \
        getattr(record, 'languages', None)
    allowed = set(counted) | {ENGLISH} if counted else None
    by_lang = collections.Counter()
    for url, text in pages.items():
        for lang in languages_in(text, script_words=True):
            if allowed is None or lang in allowed:
                by_lang[lang] += 1
    n = len(pages)
    out = {
        'pages_read': n,
        'pages_by_language': dict(by_lang),
        'share': {lang: k / n for lang, k in by_lang.items()},
    }
    if allowed is None:
        out['languages_unrestricted'] = True
    english = by_lang.get(ENGLISH, 0)
    if english:
        out['against_english'] = {lang: k / english for lang, k in by_lang.items()
                                  if lang != ENGLISH}
    return out


def depth_run(run):
    """Depth for every record of a run that holds pages, keyed by url, with the skipped counted.

    `run` is a path to a JSON-lines store or an iterable of records. Records without pages are
    counted and named rather than silently absent, this project's most frequent bug being an empty
    result reported as success.
    """
    records = list(read_store(run)) if isinstance(run, (str, bytes)) else list(run)
    out, skipped = {}, []
    for r in records:
        url = (r.get('url') if isinstance(r, dict) else getattr(r, 'url', '')) or ''
        d = depth_of(r)
        if d is None:
            skipped.append(url)
        else:
            out[url] = d
    return {'records': len(records), 'measured': out, 'no_pages': skipped}
