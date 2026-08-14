# -*- coding: utf-8 -*-
"""The search behind an absence claim, and the crawl that keeps reading rather than asserting one.

`english_only` is the only one of the four classes that asserts an ABSENCE, and 45 per cent of the
error budget of the last validation round arrived there. An absence claim is worth exactly what the
search behind it was worth, and nothing in a `Result` recorded the search. The design note
is the reasoning; this file pins the two things it asked for.

`read_quality` on every Result, so a run degraded by machine load is visible in its own output.
Escalation: a shallow read is a reason to keep reading, not a reason to answer differently, so the
four classes are exactly the four classes and every verdict stays comparable with human coding.

The fifth-state test at the bottom is the one that would catch the design going wrong. A fifth class
cannot be scored against rules that give coders four, and every site carrying one would drop
out of the agreement calculation, which raises the measured figure by removing the hard cases.
"""
import asyncio
import warnings

import pytest

from langaccess import core as LA
from test_engineering import _MapBrowser, _page


_ENGLISH = ('The center offers legal advice, housing help and classes for adults who have recently '
            'arrived in the county. Our staff can be reached by phone during office hours and we '
            'welcome anyone who needs assistance with an application or a referral.')
_SPANISH = ('El centro ofrece asesoria legal, ayuda con la vivienda y clases para adultos que han '
            'llegado recientemente al condado. Nuestro personal esta disponible por telefono '
            'durante el horario de oficina y atendemos a cualquier persona que necesite ayuda con '
            'una solicitud o una referencia para otros servicios de la comunidad.')


# ------------------------------------------------------------------ the record of a search
def test_a_one_page_read_does_not_support_an_absence_claim():
    """Where the number comes from. On the two regression runs of the same 212 sites, contended and
    quiet, every one of the 27 sites the contended run called `english_only` and the quiet run
    called something else had read exactly one page; none of the 15 it called `english_only` on two
    pages or more moved."""
    assert LA.read_quality_of(1)['sufficient'] is False
    assert LA.read_quality_of(1)['shallow'] is True
    assert LA.read_quality_of(LA.READ_ENOUGH_PAGES)['sufficient'] is True
    assert LA.read_quality_of(LA.READ_ENOUGH_PAGES)['shallow'] is False


def test_a_search_the_clock_or_a_timeout_stopped_does_not_support_one_either():
    """The contended run's signature. Its pages came back at a median of 1 against 15 because every
    audit ran into its timeout, and the verdicts were reported with exactly the confidence of a
    quiet run's."""
    assert LA.read_quality_of(15, clock_exhausted=True)['sufficient'] is False
    assert LA.read_quality_of(15, reads_timed_out=1)['sufficient'] is False


def test_the_page_budget_running_out_is_not_a_thin_search():
    """A crawl that read fifteen pages and still had a queue stopped because that is how much
    reading the budget buys. If it counted, escalation would raise the budget, exhaust it again and
    have no stopping rule."""
    q = LA.read_quality_of(15, unread=40, budget_exhausted=True)
    assert q['budget_exhausted'] is True and q['sufficient'] is True


def test_a_playwright_timeout_counts_as_a_timeout():
    """Playwright raises its own TimeoutError, which does not inherit from the builtin, so a type
    test alone would have counted every navigation timeout as an ordinary failure."""
    class TimeoutError(Exception):        # noqa: A001  - the shape Playwright exports
        pass

    assert LA._is_timeout(TimeoutError('nav')) is True
    assert LA._is_timeout(asyncio.TimeoutError()) is True
    assert LA._is_timeout(ValueError('404')) is False


def test_every_result_carries_the_field_whatever_its_class():
    """Including the sites that end before the crawl begins. A reader of a run should be able to see
    that nothing was read rather than infer it from a missing key."""
    # rule 1, decided on the landed address and before a single page is judged
    b = _MapBrowser({'https://www.facebook.com/thecenter': _page(_ENGLISH)})
    r = asyncio.run(LA._audit_async('https://www.facebook.com/thecenter', browser=b))
    assert r.verdict == 'unreachable' and r.rules == [1]
    assert r.read_quality['pages_read'] == 0 and r.read_quality['sufficient'] is False
    # and a site nothing answered for at all
    r = asyncio.run(LA._audit_async('https://x.org', browser=_MapBrowser({})))
    assert r.verdict == 'unreachable' and r.read_quality['pages_read'] == 0


# ------------------------------------------------------------------ escalation
_HIDDEN_SPANISH = {
    'https://x.org': _page(_ENGLISH),
    # `/spanish` is in DEEP_PATHS and not in TRY_PATHS, so a first pass never asks for it. Nothing
    # on the home page links to it, which is the shape the deep paths exist for: "a second language
    # often lives at the language's own WORD, not its code, and nothing links to it".
    'https://x.org/spanish': _page(_SPANISH),
}


def test_a_thin_english_only_keeps_reading_and_finds_the_page_a_first_pass_skips():
    b = _MapBrowser(_HIDDEN_SPANISH)
    r = asyncio.run(LA._audit_async('https://x.org', browser=b))
    assert r.read_quality['escalated'] is True
    assert r.verdict == 'true_multilingual' and r.languages == ['English', 'Spanish']


def test_the_same_site_stays_english_only_with_escalation_off():
    """The measurement arm. `escalate=False` changes no rule, only how much is read, which
    makes the difference between the two runs attributable to the reading."""
    b = _MapBrowser(_HIDDEN_SPANISH)
    r = asyncio.run(LA._audit_async('https://x.org', browser=b, escalate=False))
    assert r.read_quality['escalated'] is False
    assert r.verdict == 'english_only'
    assert 'https://x.org/spanish' not in b.reads


def test_escalation_does_not_fire_on_a_verdict_that_found_something():
    """Only an absence claim needs more reading. The other three classes rest on something that was
    found, and finding it on one page is finding it."""
    b = _MapBrowser({'https://x.org': _page(_SPANISH)})
    r = asyncio.run(LA._audit_async('https://x.org', browser=b))
    assert r.verdict == 'true_multilingual'
    assert r.read_quality['escalated'] is False
    assert r.read_quality['shallow'] is True, 'the read WAS thin; the verdict is not an absence'


def test_escalation_does_not_fire_on_a_site_carrying_a_widget():
    widget = ('<html><body><div id="google_translate_element"></div><script '
              'src="//translate.google.com/translate_a/element.js"></script><p>'
              + _ENGLISH + '</p></body></html>')
    b = _MapBrowser({'https://x.org': (widget, _ENGLISH, 200)})
    r = asyncio.run(LA._audit_async('https://x.org', browser=b))
    assert r.verdict == 'machine_translate' and r.read_quality['escalated'] is False


def test_escalation_happens_at_most_once():
    """A second escalation would be a third budget with nothing new to say about when to stop."""
    b = _MapBrowser({'https://x.org': _page(_ENGLISH)})
    r = asyncio.run(LA._audit_async('https://x.org', browser=b))
    assert r.verdict == 'english_only' and r.read_quality['escalated'] is True
    # the deep paths are asked for once each, not once per pass
    assert b.reads.count('https://x.org/spanish') == 1


def test_a_spent_clock_is_not_escalated_into():
    """Escalation costs reads, and beginning one there is no time to finish spends the reserve that
    gets the reading judged and written down, then returns the same verdict later."""
    b = _MapBrowser(_HIDDEN_SPANISH)
    r = asyncio.run(LA._audit_async('https://x.org', browser=b,
                                    deadline=LA._clock() - 1.0))
    assert r.read_quality['escalated'] is False
    assert r.verdict == 'english_only'


def test_escalation_never_produces_a_class_outside_the_published_set():
    """The design that does not work, pinned so it cannot arrive later.

    An instrument that emits a fifth state has no counterpart in rules that give human coders
    four, so every site carrying it drops out of the agreement calculation, and dropping the sites
    an instrument is least sure about raises the measured figure by removing the hard cases from the
    denominator. The retired scoring rule (12 of the development numbering) already forbids the
    same move in the other direction.
    """
    four = {'english_only', 'machine_translate', 'true_multilingual', 'unreachable'}
    for site in (_HIDDEN_SPANISH, {'https://x.org': _page(_ENGLISH)},
                 {'https://x.org': _page(_SPANISH)}, {}):
        r = asyncio.run(LA._audit_async('https://x.org', browser=_MapBrowser(site)))
        assert r.verdict in four, r.verdict


# ------------------------------------------------------------------ the acceptance condition
def _run(pages_each, cut=0):
    out = []
    for i, p in enumerate(pages_each):
        r = LA.Result(url='https://s%d.example' % i, pages_read=p)
        r.read_quality = LA.read_quality_of(p, clock_exhausted=i < cut)
        out.append(r)
    return out


def test_a_run_that_read_the_sites_is_accepted():
    """The quiet regression runs: a median of 15 pages and under six per cent thin."""
    got = LA.capture_acceptance(_run([15] * 100 + [1] * 5))
    assert got['accepted'] is True and got['median_pages'] >= LA.CAPTURE_MIN_MEDIAN_PAGES


def test_a_run_the_machine_could_not_do_the_reading_for_is_refused():
    """The contended run: a median of 1 page where the same code gives 15, and no line of code
    changed between them."""
    got = LA.capture_acceptance(_run([1] * 100 + [15] * 5))
    assert got['accepted'] is False and 'median' in got['why']


def test_a_run_degraded_only_in_part_is_refused_too():
    """What the median alone cannot catch. The `pass3` development run kept its median of 15 while
    a third of its sites were cut short by the clock."""
    got = LA.capture_acceptance(_run([15] * 100, cut=31))
    assert got['median_pages'] == 15
    assert got['accepted'] is False and 'absence claim' in got['why']


def test_a_frame_of_dead_addresses_is_not_a_reading_at_all():
    got = LA.capture_acceptance(_run([0] * 20))
    assert got['read'] == 0 and got['accepted'] is False


def test_a_batch_says_so_in_its_own_output_when_it_did_not_do_the_reading():
    """The check the contended run needed and did not have. It was something a person had to
    remember; the batch now makes the check itself."""
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        LA._warn_if_thin(_run([1] * 40))
    assert any('not deep enough' in str(w.message) for w in caught)


# ------------------------------------------------------------------ a stored capture
def test_a_stored_capture_cannot_escalate_and_says_so():
    """The pages escalation would fetch are not in a capture, because the crawl that wrote it did
    not fetch them. A re-judged `english_only` therefore rests on the search the original run made
    and on no more, and `read_quality` is carried rather than re-derived."""
    rec = {'url': 'https://x.org/', 'verdict': 'english_only', 'pages_read': 1,
           'note': 'crawl cut short by the time budget after 1 pages',
           'pages': {'https://x.org/': _page(_ENGLISH)[0]}, 'evidence': []}
    r = LA.rejudge(rec)
    assert LA.REJUDGE_ESCALATION in r.unreproducible
    assert LA.REJUDGE_LIMITS[LA.REJUDGE_ESCALATION]
    assert r.read_quality['clock_exhausted'] is True
    assert r.read_quality['sufficient'] is False


def test_a_record_written_with_the_field_keeps_it_word_for_word():
    q = LA.read_quality_of(7, unread=3, budget_exhausted=True, escalated=True)
    rec = {'url': 'https://x.org/', 'verdict': 'english_only', 'pages_read': 7,
           'read_quality': q, 'note': '', 'pages': {'https://x.org/': _page(_ENGLISH)[0]},
           'evidence': []}
    assert LA.rejudge(rec).read_quality == q


@pytest.mark.parametrize('field', ['pages_read', 'sufficient', 'escalated', 'clock_exhausted',
                                   'budget_exhausted', 'reads_timed_out', 'shallow', 'unread',
                                   'reads_failed', 'unread_locale_links'])
def test_the_field_survives_into_a_stored_row(field):
    """A census row is the Result serialised, and a field that does not reach it cannot be audited
    afterwards, which is the whole reason this exists."""
    r = LA.Result(url='https://x.org/')
    r.read_quality = LA.read_quality_of(2)
    assert field in r.to_dict()['read_quality']


# ------------------------------------------------- the locale tree a site advertises and nothing read
#
# One Portuguese cultural centre, 2026-08-04. The crawl read fifteen pages: the English
# home, /pt, and thirteen English interior pages. /pt itself is chrome, a menu and nothing else, and
# the twenty `/pt/` subpages it links carry the site's only Portuguese. None of the twenty was read.
# `read_quality` called the search sufficient, because sufficiency counts pages and fifteen is not a
# thin read, so escalation was never asked for, and the site was reported `english_only`.
#
# Two things were wrong and both are exercised below. The queue is FIFO and a second hop was
# appended to its tail, so twenty locale-tree links found on page two could not compete with sixteen
# ordinary English links found on page one, whatever `_link_score` says about the two kinds. And an
# absence claim with an advertised locale tree left unread is not a sufficient search however many
# pages were read.
#
# Every page below is invented. The shape is the site's; none of the bytes are.
_PORTUGUESE = ('Estamos sempre a procura de voluntarios para os nossos programas. A nossa '
               'comunidade oferece aulas e ajuda com documentos para quem chegou ha pouco tempo, '
               'e voce pode falar com a nossa equipa sem marcacao. Tambem temos servicos de apoio '
               'para todas as familias que precisam.')
_EN_PAGES = ['about-us', 'contact', 'events', 'event-list', 'amenities', 'board', 'employment',
             'restaurant', 'menu', 'bar', 'esplanada', 'get-involved', 'membership', 'donate']
_PT_PAGES = ['about-us', 'contact', 'amenities', 'board', 'employment', 'restaurant', 'menu',
             'bar', 'esplanada', 'get-involved', 'membership', 'donate', 'field-sponsors',
             'events', 'event-list', 'voluntarios']


def _locale_tree_site(pt_pages):
    """An English home, a /pt that is a menu and nothing else, and a /pt tree whose LAST page is the
    only Portuguese on the site. `pt_pages` is how wide the tree is."""
    site = {'https://x.org': _page(
        _ENGLISH,
        '<html><body><a href="/pt">PT</a>'
        + ''.join('<a href="/%s">%s</a>' % (p, p) for p in _EN_PAGES)
        + '<p>' + _ENGLISH + '</p></body></html>')}
    site['https://x.org/pt'] = (
        '<html><body>' + ''.join('<a href="/pt/%s">%s</a>' % (p, p) for p in pt_pages)
        + '</body></html>', 'PCC', 200)
    for p in _EN_PAGES:
        site['https://x.org/' + p] = _page('The %s page of the center, with contact details.' % p)
    for p in pt_pages[:-1]:
        site['https://x.org/pt/' + p] = _page('The %s page.' % p)
    site['https://x.org/pt/' + pt_pages[-1]] = _page(_PORTUGUESE)
    return site


def test_an_absence_claim_with_an_unread_locale_tree_keeps_reading():
    """The site as it stands: the tree is wider than one budget, so the first pass ends on an
    absence claim with part of the tree still queued, which escalation now handles."""
    b = _MapBrowser(_locale_tree_site(_PT_PAGES))
    r = asyncio.run(LA._audit_async('https://x.org', browser=b))
    assert r.verdict == 'true_multilingual' and r.languages == ['English', 'Portuguese']
    assert r.read_quality['escalated'] is True
    assert r.read_quality['unread_locale_links'] == 0, 'the tree was read to the end'


def test_the_pages_that_were_never_read_are_counted_when_escalation_is_off():
    """The measurement arm, and the field the whole change turns on. `sufficient` is True here: the
    crawl read fifteen pages, which is not a thin read, and three addresses in the locale tree the
    site advertises were found and never fetched. Nothing in the record said so before."""
    b = _MapBrowser(_locale_tree_site(_PT_PAGES))
    r = asyncio.run(LA._audit_async('https://x.org', browser=b, escalate=False))
    assert r.verdict == 'english_only'
    assert r.read_quality['sufficient'] is True, 'page count alone calls this search enough'
    assert r.read_quality['unread_locale_links'] == 3
    assert 'https://x.org/pt/voluntarios' not in b.reads


def test_a_locale_tree_found_on_page_two_outranks_the_english_links_found_on_page_one():
    """The queue mechanism, on a tree narrow enough to fit inside the ordinary budget, so what is
    being tested is the ORDER and not the escalation. Before this, twenty `/pt/` links entered the
    queue behind sixteen English interior links, forty sitemap addresses and twenty guesses."""
    b = _MapBrowser(_locale_tree_site(['about-us', 'contact', 'events', 'voluntarios']))
    r = asyncio.run(LA._audit_async('https://x.org', browser=b))
    assert r.verdict == 'true_multilingual' and r.languages == ['English', 'Portuguese']
    assert r.read_quality['escalated'] is False, 'the ordinary budget was enough once ordered'
    first_locale = min(i for i, u in enumerate(b.reads) if u.startswith('https://x.org/pt/'))
    first_english = min(i for i, u in enumerate(b.reads) if u.rstrip('/') in
                        ['https://x.org/' + p for p in _EN_PAGES])
    assert first_locale < first_english


def test_a_guessed_locale_path_is_not_an_advertised_tree():
    """The guard on the trigger. Every site is asked for /es, /zh, /ko and nine more, and if an
    unread guess counted as an advertised tree then every site on earth would escalate and
    escalation would be DEEP_PATHS under another name."""
    b = _MapBrowser({'https://x.org': _page(_ENGLISH)})
    r = asyncio.run(LA._audit_async('https://x.org', browser=b, escalate=False))
    assert r.verdict == 'english_only'
    assert r.read_quality['unread_locale_links'] == 0


# ------------------------------------------ a tree wider than one page's worth of links, 2026-08-05
#
# Every case above holds a tree of sixteen, which is exactly INTERIOR_LIMIT, so every address on it
# reached the queue and the queue could stand in for the record. Real trees are not sixteen wide.
# Measured over two stored captures with no page fetched: of the 22,769 declared locale addresses
# that the census re-crawl's 1,711 sites link from pages the crawl READ and never fetched, 41.0 per
# cent were in the queue, 46.8 per cent had been cut by `_interior`'s sixteen-link slice and 12.2
# per cent sat behind the two-hop gate; one community clinic links 57 `/es-la/` addresses of which
# 13 were queued, one legal aid organization 61 of which 32, one county 43 of which 18.
#
# The two tests below are the two halves of what that costs, on a tree of twenty. The first is the
# record: `unread_locale_links` said the tree had been read to the end when nine addresses of it
# had never been fetched. The second is the reading: escalation reorders the queue, a queue can only
# be reordered by what is in it, and the addresses the slice dropped were not in it, so escalation
# spent its sixteen pages on DEEP_PATHS guesses while the site's own tree sat outside.
_WIDE_TREE = ['p%02d' % i for i in range(19)] + ['voluntarios']


def test_the_record_counts_the_tree_the_slice_dropped():
    """With escalation off, so what is measured is the RECORD and not the crawl. The site publishes
    twenty `/pt/` addresses, the crawl reads thirteen of them, and seven are left: three that were
    queued and four that `_interior` cut. Before this the answer was three."""
    b = _MapBrowser(_locale_tree_site(_WIDE_TREE))
    r = asyncio.run(LA._audit_async('https://x.org', browser=b, escalate=False))
    assert r.verdict == 'english_only'
    assert r.read_quality['sufficient'] is True, 'page count alone calls this search enough'
    assert r.read_quality['unread_locale_links'] == 7


def test_escalation_reads_the_addresses_the_slice_dropped():
    """The verdict this moves. The only Portuguese is on the twentieth `/pt/` page, which
    `_interior` never kept, so no reordering could reach it and the site was reported `english_only`
    with `unread_locale_links` of ZERO, which reads as a tree that was followed to its end.

    The page count settles the cost argument: 31 either way. Escalation reads the same
    sixteen pages it always read; what changed is which sixteen."""
    b = _MapBrowser(_locale_tree_site(_WIDE_TREE))
    r = asyncio.run(LA._audit_async('https://x.org', browser=b))
    assert r.verdict == 'true_multilingual' and r.languages == ['English', 'Portuguese']
    assert r.read_quality['escalated'] is True
    assert r.read_quality['unread_locale_links'] == 0
    assert r.pages_read == 31


def test_no_more_addresses_jump_the_queue_than_an_escalated_pass_can_read():
    """The cap, on a tree far wider than any budget. One county publishes 1,281 locale addresses
    and an uncapped tree would put a thousand fetches in front of the crawl; a page that comes back
    empty costs a fetch and does not count against the page budget, so the clock would pay, and the
    clock is the one resource whose exhaustion can end in `unreachable`."""
    wide = ['q%03d' % i for i in range(199)] + ['voluntarios']
    b = _MapBrowser(_locale_tree_site(wide))
    r = asyncio.run(LA._audit_async('https://x.org', browser=b))
    assert r.pages_read <= 31, 'the page budget is what it was'
    tree = [u for u in b.reads if u.startswith('https://x.org/pt/')]
    assert len(tree) <= 16 + LA.LOCALE_ESCALATE_LIMIT
    assert r.read_quality['unread_locale_links'] >= 150, 'and the rest is on the record'


def test_a_platform_s_own_language_switcher_is_not_this_site_s_tree():
    """The directory principle, applied to the record. One association's site is a blog on
    wordpress.com, the crawl
    stored a wordpress.com footer page, and WordPress.com's own switcher offered Greek, Hebrew,
    Hindi, Romanian, Swedish, Thai and Turkish. Read against the page they were found on those are
    same-site; read against the HOME PAGE, which is what an organization's website means here, they
    are somebody else's."""
    site = {'https://org.example.com/': _page(
        _ENGLISH, '<html><body><a href="https://example.com/?ref=footer">Blog at Example</a><p>'
                  + _ENGLISH + '</p></body></html>')}
    site['https://example.com/?ref=footer'] = _page(
        'A page of the hosting platform, with its own footer and its own language switcher.',
        '<html><body><a href="/el/">Ellinika</a><a href="/he/">Ivrit</a>'
        '<a href="/th/">Thai</a></body></html>')
    b = _MapBrowser(site)
    r = asyncio.run(LA._audit_async('https://org.example.com/', browser=b, escalate=False))
    assert r.read_quality['unread_locale_links'] == 0


def _noisy_tree_site(head='', extra_links=''):
    """The wide-tree site with something added to the home document, so a test can ask what the
    addition did to the record and nothing else."""
    site = _locale_tree_site(_WIDE_TREE)
    html, text, status = site['https://x.org']
    site['https://x.org'] = (html.replace('<html><body>',
                                          '<html><head>' + head + '</head><body>' + extra_links),
                             text, status)
    return site


def _unread_locale_count(site):
    return asyncio.run(LA._audit_async(
        'https://x.org', browser=_MapBrowser(site), escalate=False)).read_quality[
            'unread_locale_links']


def test_the_site_s_own_english_is_not_an_unread_other_language():
    """`en` is in ISO639, so LOCALE_ROUTE matches /en/ as it matches /es/. For an absence claim that
    is the wrong answer twice over: the English tree is not the language the claim says the site
    does not have, and the crawl is reading it. `_routes` already refuses an hreflang of `en`.

    Asked as a difference, so what is measured is the addition and not the tree:
    one immigrant service network's `/en/directory/research/` and 21 of the 35 addresses counted on
    one youth ministry were the site's own English."""
    plain = _unread_locale_count(_noisy_tree_site())
    assert plain > 0, 'the tree has to be counted before an addition to it can be measured'
    noisy = _unread_locale_count(_noisy_tree_site(
        extra_links='<a href="/en/directory/">Directory</a>'
                    '<a href="/en-us/team/">Team</a>'))
    assert noisy == plain, 'the English tree entered the record'
    assert LA._ENGLISH_ROUTE.search('https://z.org/en/directory/')
    assert LA._ENGLISH_ROUTE.search('https://z.org/en-us/team/')
    assert not LA._ENGLISH_ROUTE.search('https://z.org/es/directorio/')
    # and the guard is written for a host and a query as well as for a path
    assert LA._ENGLISH_ROUTE.search('https://en.z.org/about')
    assert LA._ENGLISH_ROUTE.search('https://z.org/page?lang=en')
    assert not LA._ENGLISH_ROUTE.search('https://z.org/energia/')


def test_the_record_holds_a_page_and_not_a_json_endpoint():
    """`_routes` is not the source, and this is why. Three of its five rules match a bare `href=`
    anywhere in a document, `<link>` included, so a WordPress site under /es declared
    `/es/wp-json/`,
    an oembed endpoint, a shortlink and an RSS feed as pages of its Spanish tree. Eighty-four of 278
    addresses read by hand were that, and none of them is a page a reader sees."""
    plain = _unread_locale_count(_noisy_tree_site())
    assert plain > 0
    noisy = _unread_locale_count(_noisy_tree_site(
        head='<link rel="https://api.w.org/" href="/pt/wp-json/">'
             '<link rel="alternate" type="application/json+oembed" href="/pt/wp-json/oembed/1.0/e">'
             '<link rel="shortlink" href="/pt/?p=1315">'
             '<link rel="alternate" type="application/rss+xml" href="/pt/feed/">'))
    assert noisy == plain, 'a link tag that is not an hreflang entered the record'


def test_the_record_reaches_deeper_than_the_crawl_may_read():
    """Recording and reading are separated. Rule 4 bounds a reading at two clicks from the
    home page, so a locale address linked from a page three clicks in is not queued; it is still an
    address this site published in another language and an absence claim still answers for it."""
    # Each body differs, because a page whose text is the home page's word for word is not a page
    # read and would not reach the recorder at all.
    site = {'https://y.org': _page(_ENGLISH, '<html><body><a href="/about">About</a><p>'
                                             + _ENGLISH + '</p></body></html>')}
    site['https://y.org/about'] = _page(
        'The about page of the center, with the history of the association and its founders.',
        '<html><body><a href="/team">Team</a></body></html>')
    site['https://y.org/team'] = _page(
        'The staff page of the center, with a photograph and a telephone number for each member.',
        '<html><body><a href="/pt/apoio">PT</a></body></html>')
    site['https://y.org/pt/apoio'] = _page(_PORTUGUESE)
    b = _MapBrowser(site)
    r = asyncio.run(LA._audit_async('https://y.org', browser=b, escalate=False))
    assert r.verdict == 'english_only'
    assert r.read_quality['unread_locale_links'] == 1
    assert 'https://y.org/pt/apoio' not in b.reads

    # the same address declared as an hreflang alternate instead of as an anchor, which is the one
    # `<link>` tag `_note_locale_links` reads and the reason it parses them at all
    site['https://y.org/team'] = _page(
        'The staff page of the center, with a photograph and a telephone number for each member.',
        '<html><head><link rel="alternate" hreflang="pt" href="/pt/apoio"></head>'
        '<body>Staff</body></html>')
    b2 = _MapBrowser(site)
    r2 = asyncio.run(LA._audit_async('https://y.org', browser=b2, escalate=False))
    assert r2.read_quality['unread_locale_links'] == 1
    assert 'https://y.org/pt/apoio' not in b2.reads
