# -*- coding: utf-8 -*-
"""The event-page half of codebook rule 13: a dated event page does not carry the reading alone.

Rule 13 says an archive page does not carry the reading. The event-page half says a dated event
or calendar page cannot be the SOLE carrier of a language's page-rung finding: when every
page-rung item for a language sits at an event address and no non-event item reaches the notice
rung, the event-page evidence is set aside at counting time, exactly as an archive address is.
Decided 2026-08-07 against the r2 settled standard (0 of 1,027 stored readings moved, and the 11
sites carrying event-page evidence all had corroborating non-event pages) and sized on a later
draw (1 of 720 moved).

The records here are synthetic store records judged through `langaccess.rejudge`, which is the
same judging entry the engineering tests use for stored captures: no browser, no network, the
same `counted_evidence` / `verdict_for` the live audit applies. Every address is under
`.example`, and every paragraph is invented.
"""
import pytest

from langaccess import core as LA

_GOOGLE = ('<script type="text/javascript" src="//translate.google.com/translate_a/'
           'element.js?cb=googleTranslateElementInit"></script>')

_EN = ('Welcome to our neighborhood center. We help families with legal questions and we offer '
       'free classes every week for anyone who wants to join us in the city.')
_ES_EVENT = ('Taller comunitario sobre la salud. Nuestros voluntarios ofrecen informacion y '
             'recursos para las familias que necesitan ayuda con este proceso. Todos pueden '
             'venir y hacer preguntas durante la reunion del jueves. ')
_ES_SERVICES = ('Nuestros servicios para la comunidad son gratuitos. Ofrecemos ayuda con las '
                'solicitudes y todos pueden hacer una cita con nosotros cualquier dia de la '
                'semana en nuestra oficina. ')
_ES_RESOURCES = ('Recursos para los inmigrantes de la region. Aqui encontrara guias sobre sus '
                 'derechos y sobre como pedir ayuda cuando la necesite en su propio idioma. ')


def _html(text, widget=False):
    return ('<html><head><title>Center</title></head><body>'
            + (_GOOGLE if widget else '')
            + '<p>' + text + '</p></body></html>')


def _record(url, pages):
    """A record in the shape `store=` writes, with pages only: rejudge derives the evidence."""
    return {'url': url, 'pages': pages, 'evidence': [], 'note': '', 'pages_read': len(pages),
            'verdict': '', 'rules': [], 'machine_translation': ''}


def _event_only_site(widget=False):
    """A site whose ONLY Spanish is one dated event page."""
    return _record('https://ev.example/', {
        'https://ev.example/': _html(_EN, widget=widget),
        'https://ev.example/event/taller-de-salud/': _html(_ES_EVENT * 3),
    })


def _event_beside_services_site():
    """A Spanish services page AND a Spanish event page."""
    return _record('https://ev.example/', {
        'https://ev.example/': _html(_EN),
        'https://ev.example/servicios/': _html(_ES_SERVICES * 3),
        'https://ev.example/event/taller-de-salud/': _html(_ES_EVENT * 3),
    })


def _two_ordinary_pages_site():
    """Two non-event Spanish pages and no event page at all."""
    return _record('https://ev.example/', {
        'https://ev.example/': _html(_EN),
        'https://ev.example/servicios/': _html(_ES_SERVICES * 3),
        'https://ev.example/recursos/': _html(_ES_RESOURCES * 3),
    })


# ------------------------------------------------- the sole event page does not carry the site
def test_the_sole_event_page_does_not_carry_the_page_rung():
    r = LA.rejudge(_event_only_site(widget=False))
    assert r.verdict == 'english_only'
    assert 'Spanish' not in r.languages
    assert 13 in r.rules, 'the event-page half reports under rule 13\'s own id'

    rw = LA.rejudge(_event_only_site(widget=True))
    assert rw.machine_translation, 'the widget fixture has to carry a named widget'
    assert rw.verdict == 'machine_translate'
    assert 'Spanish' not in rw.languages
    assert 13 in rw.rules


def test_the_set_aside_evidence_keeps_its_address_on_the_record():
    """Applied at counting time and not at reading time, exactly as the archive half is: the
    Spanish is still read, quoted and on the record with the address that disqualified it."""
    r = LA.rejudge(_event_only_site())
    aside = [e for e in r.evidence
             if LA._ev_lang(e) == 'Spanish' and LA._event_page_url(LA._ev_url(e))]
    assert aside, 'the event page was read and its evidence is still on the record'
    counted = LA.counted_evidence(r.evidence, r.machine_translation)
    assert not any(LA._ev_lang(e) == 'Spanish' for e in counted)


# ------------------------------------------------- a services page beside the event page
def test_a_services_page_beside_the_event_page_moves_nothing():
    r = LA.rejudge(_event_beside_services_site())
    assert r.verdict == 'true_multilingual'
    assert 'Spanish' in r.languages
    # and the event page itself is still counted, because the language has non-event support
    counted = LA.counted_evidence(r.evidence, r.machine_translation)
    assert any('/event/' in LA._ev_url(e) for e in counted), (
        'with non-event support at notice or above, the event evidence keeps counting')
    assert 13 not in r.rules


# ------------------------------------------------------------- two non-event Spanish pages
def test_two_ordinary_spanish_pages_move_nothing():
    r = LA.rejudge(_two_ordinary_pages_site())
    assert r.verdict == 'true_multilingual'
    assert 'Spanish' in r.languages
    assert 13 not in r.rules


# --------------------------------------------------------------------- the URL detector
@pytest.mark.parametrize('url, want', [
    ('https://x.example/event/foo-bar/', True),
    ('https://x.example/events/', True),
    ('https://x.example/events', True),
    ('https://x.example/2024/08/22/foo', True),
    ('https://x.example/tribe-events/taller/', True),
    ('https://x.example/calendar/', True),
    ('https://x.example/?post_type=tribe_events&p=12', True),
    ('https://x.example/services/immigration/', False),
    # a slug that merely CONTAINS the word is not an events path
    ('https://x.example/eventos-especiales-de-salud/', False),
    # a month archive without a day is DATED_POST's shape, not this rule's
    ('https://x.example/2024/08/', False),
    ('https://x.example/preventing-harm/', False),
])
def test_the_event_url_detector_decides_on_a_clear_url_signal_only(url, want):
    assert LA._event_page_url(url) is want
