# -*- coding: utf-8 -*-
"""Known-answer tests for the language detector, converted from the original
standalone script this package was extracted from into pytest. Every case from that script is
kept; none were dropped or weakened.

Two silent failures happened in one day of building this, and neither showed up in any output: the
function word lists were written without accents so no Latin-script language ever matched, and a
patch put a literal backspace byte where a word boundary was meant, which switched off all eighteen
of them at once. Both looked like sites having no non-English content. A detector whose failure
mode is silence needs cases with known answers more than it needs anything else.

These tests are pure functions (languages_in, _routes, precedence, regex health) and touch no
network and launch no browser. Browser-dependent tests live in tests/test_live.py, marked `live`
and skipped by default.
"""
import collections
import re
import time

import asyncio
import pytest

from langaccess import core as LA


LANGUAGE_CASES = [
    # --- a real sentence in the language proves the language
    ('es prose', 'Nuestros servicios para la comunidad son gratuitos. Recursos e información para familias.',
     ['Spanish']),
    ('hu prose', 'A szolgáltatásaink ingyenesek. Jelentkezés a magyar tanfolyamra. Oktatás gyerekeknek.',
     ['Hungarian']),
    ('ko prose', '본 기관은 이민자 가정을 위해 무료 법률 상담과 통역 서비스를 제공하고 있습니다. 문의해 주세요.',
     ['Korean']),
    # English is read the same way as every other Latin-script language since 2026-08-04, so this
    # names itself. The four cases below still name NOTHING, which is the half of the change worth
    # pinning: a name, a language menu, one greeting and an address do not reach four distinct
    # English function words inside one window any more than they reach four Spanish ones.
    ('en prose', 'Our services for the community are free. Resources and information for families.',
     ['English']),
    # --- the traps this project actually fell into
    ('org name only', 'Casa Buena Community Center, 123 Main Street, Suite 4', []),
    ('menu of languages', 'English 한국어 (Korean) ខ្មែរ (Khmer) ภาษาไทย (Thai) Tiếng Việt हिन्दी 中文', []),
    ('one greeting', 'Bienvenidos! Welcome to our organization. We serve families across the county.', []),
    ('address only', 'Oficina: 500 Main St. Tel 555-1234', []),
    # --- a script is named by its language, not by itself
    ('hindi prose', 'हमारी संस्था प्रवासी परिवारों को निःशुल्क कानूनी सहायता और अनुवाद सेवाएं प्रदान करती है।', ['Hindi']),
    ('russian prose', 'Наша организация предоставляет бесплатную юридическую помощь семьям иммигрантов.',
     ['Russian']),
]

LINK_CASES = [
    # a real organization's address stood here until 2026-08-05. The case is the SHAPE, a mailto
    # whose local part carries a language word, so the address it carries can be anybody's.
    ('mailto is not a route', 'href="mailto:russian-school@example.org"', False),
    ('path names a language', 'href="https://x.org/contact-chinese/"', True),
    ('file names a language', 'href="/forms/spanish-intake.pdf"', True),
    ('foreign domain is not a route', 'href="https://www.hungarianweekly.example/articles/x"', False),
]

VERDICT_CASES = [
    # (has widget, has own-language evidence) -> verdict
    ('widget alone', True, False, 'machine_translate'),
    # Was machine_translate from 2026-07-28 to 2026-07-30, under rule 10's count rule: one own
    # paragraph under a widget did not carry a site and a second was needed. The count rule was a
    # proxy for "is one passage worth anything", and the derivation now answers that question
    # directly on the sufficiency ladder: an authored notice is level 2, which is the rung at which
    # a reader who does not read English can act on what is there. See `LA.class_for`.
    ('widget and one own paragraph', True, True, 'true_multilingual'),
    ('own writing alone', False, True, 'true_multilingual'),
    ('neither', False, False, 'english_only'),
]


@pytest.mark.parametrize('name,text,want', LANGUAGE_CASES, ids=[c[0] for c in LANGUAGE_CASES])
def test_languages_in(name, text, want):
    assert LA.languages_in(text) == want


@pytest.mark.parametrize('name,html,want', LINK_CASES, ids=[c[0] for c in LINK_CASES])
def test_routes(name, html, want):
    # a language-named path or filename is a route worth trying; a mailto link or an unrelated
    # foreign-language domain name is not, even though it may contain a language word
    hit = bool([u for u in LA._routes(html, 'https://x.org/')
                if not u.endswith(('/es', '/es/', '/espanol', '/zh', '/zh-hans', '/ko', '/vi', '/ar',
                                   '/ru', '/fr', '/ht', '/pt'))])
    assert hit == want


@pytest.mark.parametrize('name,widget,own,want', VERDICT_CASES, ids=[c[0] for c in VERDICT_CASES])
def test_verdict_precedence(name, widget, own, want):
    # exercises the rule the tool applies, not a re-implementation of it in the test
    ev = [LA.Evidence('inline_text', 'u', 'q', 'Spanish')] if own else []
    assert LA.verdict_for(ev, 'Google Translate' if widget else '') == want


WIDGET_EVIDENCE_CASES = [
    # (mechanism, with a widget present, verdict) -- a widget manufactures routes and controls, so
    # under one they are not evidence that it is doing anything more than translating
    ('translated_page', True, 'machine_translate'),
    # a control clicked, the page swapped in place: the widget is working, so machine translation
    ('language_control', True, 'machine_translate'),
    # a single own-mechanism item under a widget no longer carries the site (2026-07-28)
    ('inline_text', True, 'machine_translate'),
    ('translation_plugin', True, 'machine_translate'),
    # with no widget in the page, every mechanism counts
    ('translated_page', False, 'true_multilingual'),
    ('language_control', False, 'true_multilingual'),
]


@pytest.mark.parametrize('mech,widget,want', WIDGET_EVIDENCE_CASES,
                         ids=[f'{m}-{"widget" if w else "no widget"}' for m, w, _ in WIDGET_EVIDENCE_CASES])
def test_widget_cannot_be_outvoted_by_what_it_makes(mech, widget, want):
    ev = [LA.Evidence(mech, 'https://x.org/es', 'texto', 'Spanish')]
    assert LA.verdict_for(ev, 'Google Translate' if widget else '') == want


ROUTE_HOST_CASES = [
    ('own path names a language', 'https://x.org/', '<a href="/programas-espanol">x</a>',
     'https://x.org/programas-espanol', True),
    ('another company on LinkedIn', 'https://x.org/',
     '<a href="https://www.linkedin.com/company/spanish-american-committee/">in</a>',
     'linkedin.com', False),
    ('www and bare host are one site', 'https://www.x.org/',
     '<a href="https://x.org/contact-spanish">x</a>', 'https://x.org/contact-spanish', True),
]


@pytest.mark.parametrize('name,base,html,needle,want', ROUTE_HOST_CASES,
                         ids=[c[0] for c in ROUTE_HOST_CASES])
def test_routes_stay_on_the_organizations_own_site(name, base, html, needle, want):
    # a page on someone else's domain is not evidence about this organization's website, however
    # its path reads
    assert any(needle in u for u in LA._routes(html, base)) is want


CYRILLIC_CASES = [
    # the Cyrillic range alone cannot name a language; calling all of it Russian reported a
    # Ukrainian weekend school and an association of Bulgarian schools as Russian sites
    ('ukrainian', 'Наша школа запрошує дітей на заняття з української мови. Ми працюємо щосуботи.',
     'Ukrainian'),
    ('bulgarian', 'Асоциацията на българските училища обединява училища, които преподават български език.',
     'Bulgarian'),
    ('russian', 'Наша организация предоставляет бесплатную юридическую помощь семьям иммигрантов.',
     'Russian'),
    ('serbian', 'Наша организација пружа бесплатну правну помоћ породицама сваки дан.', 'Serbian'),
]


@pytest.mark.parametrize('name,text,want', CYRILLIC_CASES, ids=[c[0] for c in CYRILLIC_CASES])
def test_cyrillic_is_named_by_its_own_language(name, text, want):
    assert LA.languages_in(text) == [want]


PARAGRAPH_CASES = [
    # the rules ask for a paragraph, not a label: one anti-violence organization was called
    # multilingual off a list of Spanish publication titles sitting on an English page
    ('titles scattered through an English page',
     'Annual Report 2025 Informe Anual de AVANCE 2025 Publications Declaracion sobre las Revelaciones '
     + ('english filler text here ' * 60) + ' Resources Guia para nuestros programas', False),
    ('one Spanish paragraph',
     'Nuestros servicios para la comunidad son gratuitos. Ofrecemos informacion y recursos para las '
     'familias que necesitan ayuda con este proceso, y todos pueden hacer una cita.', True),
]


@pytest.mark.parametrize('name,text,want', PARAGRAPH_CASES, ids=[c[0] for c in PARAGRAPH_CASES])
def test_a_paragraph_not_a_label(name, text, want):
    assert bool(LA.languages_in(text)) is want


LOCALE_CASES = [
    # under a widget, a page at a locale address is the widget's own output; a page at an ordinary
    # address is not something a widget produces
    ('https://x.org/es', 'machine_translate'),
    ('https://x.org/es/', 'machine_translate'),
    ('https://es.x.org/', 'machine_translate'),
    ('https://x.org/?lang=es', 'machine_translate'),
    ('https://x.org/know-your-rights-conozca-sus-derechos', 'true_multilingual'),
]


@pytest.mark.parametrize('url,want', LOCALE_CASES, ids=[c[0] for c in LOCALE_CASES])
def test_a_locale_mirror_is_not_the_organizations_own_page(url, want):
    ev = [LA.Evidence('translated_page', url, 'texto en espanol', 'Spanish')]
    assert LA.verdict_for(ev, 'Google Translate') == want


def test_interior_pages_are_same_site_and_not_documents():
    html = ('<a href="/about-us">About</a><a href="/teachers/anna">Anna</a>'
            '<a href="/flyer-espanol.pdf">Folleto</a>'
            '<a href="https://elsewhere.org/programs">Programs</a>')
    got = LA._interior(html, 'https://x.org/')
    assert 'https://x.org/about-us' in got and 'https://x.org/teachers/anna' in got
    assert not any('.pdf' in u for u in got)          # a document is not the website
    assert not any('elsewhere.org' in u for u in got)  # someone else's site is not this one


def test_the_widget_selector_names_the_common_widgets():
    for marker in ('google_translate_element', 'weglot', 'gtranslate', 'conveythis'):
        assert marker in LA.WIDGET_SEL


def test_deep_paths_are_only_tried_when_asked():
    """The default configuration is the one every published figure was produced under, so the
    deeper routes must not leak into it; asking for them must actually add them."""
    html = '<a href="/about">About</a>'
    shallow = LA._routes(html, 'https://x.org/')
    deep = LA._routes(html, 'https://x.org/', deep=True)
    assert 'https://x.org/korean' not in shallow
    assert 'https://x.org/korean' in deep
    assert 'https://x.org/espanol' in shallow          # a short list was always tried
    assert set(shallow) < set(deep)


def test_deep_paths_are_well_formed():
    assert len(LA.DEEP_PATHS) == len(set(LA.DEEP_PATHS))
    assert all(p.startswith('/') and ' ' not in p for p in LA.DEEP_PATHS)
    assert not set(LA.DEEP_PATHS) & set(LA.TRY_PATHS)   # no path fetched twice


def test_audit_takes_deep_and_timeout():
    """A run over more than a handful of sites has to be able to cap one site: before this existed,
    a single site held a batch of twelve for fifty-five minutes."""
    import inspect
    for fn in (LA.audit, LA.audit_async):
        params = inspect.signature(fn).parameters
        assert 'deep' in params and 'timeout' in params
        assert params['deep'].default is False and params['timeout'].default is None


def test_func_regexes_are_healthy():
    """Every language's regex must actually match the first word of its own function-word list.

    A known-answer guard against both silent failures described above: an unfolded
    (accented) word list that never matches a folded page, and a literal backspace byte (\\x08)
    swapped in for a word-boundary \\b that switches a regex off entirely.
    """
    bad = [k for k, r in LA.FUNC_RX.items()
           if '\x08' in r.pattern or not r.search(LA._fold(LA.FUNC[k].split()[0]))]
    assert bad == []


# A control is a language name and nothing else. A sentence that happens to contain one is not a switcher,
# and clicking every link whose text mentions Spanish would walk the whole site.
import pytest
from langaccess.core import LANGLABEL


@pytest.mark.parametrize('label,is_control', [
    ('Español', True), ('中文', True), ('한국어', True), ('Spanish', True), ('Tagalog', True),
    ('Home', False), ('EN', False), ('Read more in Spanish about our services', False),
    ('Español para familias inmigrantes', False),
])
def test_language_control_label(label, is_control):
    assert bool(LANGLABEL.match(label)) is is_control


AUX_CASES = [
    # langid fills only what the package's own lists cannot express. Lithuanian and Chin were both
    # on real sites in the validation set and were invisible before.
    ('a Lithuanian paragraph',   # this one the package's own list now covers
     'Musu mokykla kviecia vaikus i lietuviu kalbos pamokas. Mes dirbame kiekviena sestadieni ir '
     'visi vaikai yra bendruomenes dalis, todel labai svarbu dalyvauti kartu su seima.', True),
    # False in the sense this table is about: langid must not put a NAME on English prose. Since
    # 2026-08-04 English has a list of its own, so `languages_in` answers 'English' here, which is
    # the package's own reading and not the auxiliary's; the assertion below reads past it.
    ('an English paragraph',
     'Our services for the community are free. Resources and information for families. We help '
     'everyone who comes to our office each week of the year.', False),
    ('an organization name and an address', 'Casa Buena Community Center, 123 Main Street', False),
]


@pytest.mark.parametrize('name,text,want', AUX_CASES, ids=[c[0] for c in AUX_CASES])
def test_langid_fills_only_the_gaps(name, text, want):
    assert bool([n for n in LA.languages_in(text) if n != 'English']) is want


def test_the_auxiliary_never_overrides_a_language_the_lists_cover():
    """A language the lists already judge must not be re-judged by langid, or earlier readings stop
    being comparable and the case of one Spanish-named community organization (Spanish read off the
    organization's own name) comes back."""
    spanish = ('Nuestros servicios para la comunidad son gratuitos. Ofrecemos informacion y '
               'recursos para las familias que necesitan ayuda con este proceso.')
    assert LA.languages_in(spanish, aux=False) == LA.languages_in(spanish, aux=True)
    # whatever langid says, a name the lists already own is never taken from it
    assert not set(LA._aux_languages(spanish, LA.COVERED)) & LA.COVERED


WALL_CASES = [
    ('cloudflare', 'Just a moment... Checking your browser before accessing', True),
    ('site connection check',
     'example.org Checking the site connection security This page requires cookies to be '
     'enabled in your browser settings. Please check this setting and try again.', True),
    ('captcha', 'Please complete the captcha to continue', True),
    ('an ordinary page', 'Welcome to our organization. We serve immigrant families across the county '
                         'with legal help, English classes and case management.', False),
    ('a page that merely mentions cookies',
     'We use cookies on this site to improve your experience. Our services for the community are '
     'free and open to everyone.', False),
]


@pytest.mark.parametrize('name,text,want', WALL_CASES, ids=[c[0] for c in WALL_CASES])
def test_an_interstitial_is_not_the_site(name, text, want):
    """Reading an interstitial as the page reports english_only for a site that was never read,
    which is the confusion the unreachable class exists to prevent."""
    assert bool(LA.WALL_RX.search(text)) is want


def test_a_widget_that_translates_nothing_is_not_machine_translation():
    """One site renders an Espanol control whose page comes back word for word in
    English. Nothing was translated there, so nothing is claimed. But that has to be shown: a Google
    Translate widget publishes no route at all and rewrites the page in place, so finding no
    translated route says only that the tool never exercised it. Implementing the rule without that
    distinction moved 28 of 37 machine-translation sites to english_only in one run."""
    assert LA.verdict_for([], 'Weglot', route_was_english=True) == 'english_only'
    assert LA.verdict_for([], 'Google Translate') == 'machine_translate'
    produced = [LA.Evidence('translated_page', 'https://x.org/es', 'texto', 'Spanish')]
    assert LA.verdict_for(produced, 'Weglot') == 'machine_translate'


def test_a_plugin_marker_alone_is_not_content():
    """One immigrant services center carries WPML and not one word of non-English text."""
    marker_only = [LA.Evidence('translation_plugin', 'https://x.org/', 'wpml', '')]
    assert LA.verdict_for(marker_only, '') == 'english_only'
    with_text = marker_only + [LA.Evidence('inline_text', 'https://x.org/', 'texto', 'Spanish')]
    assert LA.verdict_for(with_text, '') == 'true_multilingual'


SCRIPT_PARAGRAPH_CASES = [
    ('a Khmer heading', 'ព័ត៌មានអំពីវ៉ាក់សាំង COVID-19 Video Collection', False),
    ('a Khmer sentence',
     'មជ្ឈមណ្ឌលវប្បធម៌កម្ពុជាផ្តល់ថ្នាក់រៀនភាសាខ្មែរ និងកម្មវិធីសម្រាប់យុវជននៅក្នុងសហគមន៍របស់យើង។', True),
    ('a Chinese nav row', '社区服务 志愿者 捐赠 联系我们', False),
    ('a Chinese sentence', 'ACSC致力于通过评估、导航和协助亚裔老年社区成员的社交需求，为他们提供全面的支持服务。', True),
]


@pytest.mark.parametrize('name,text,want', SCRIPT_PARAGRAPH_CASES,
                         ids=[c[0] for c in SCRIPT_PARAGRAPH_CASES])
def test_the_paragraph_standard_applies_to_every_script(name, text, want):
    """One Cambodian cultural center was reported multilingual off a few short Khmer titles for
    outside resources, because scripts needed only twelve characters where Latin needed a paragraph."""
    assert bool(LA.languages_in(text)) is want


# ------------------------------------------------------------------ Spanish against Portuguese
#
# The two thinnest unique-word lists in the package, and the pair the subtraction cannot separate on
# words alone. What is pinned here is the measurement, not the mechanism: `dos` was licensing a
# Portuguese reading off Spanish prose on 297 sites of the census render store, and the two
# orthographic marks are what let the word be made shared without taking Portuguese off the two
# sites in that store where the reading was true.

# a real Spanish paragraph whose every function word is one Portuguese also uses
SHARED_SPANISH = ('Este taller esta abierto para toda la familia y cada persona del barrio que '
                  'quiera venir a los ninos y a los mayores.')
# the same paragraph in Portuguese
SHARED_PORTUGUESE = ('Este encontro esta aberto para toda a familia e cada pessoa do bairro que '
                     'queira vir.')


def test_a_word_two_languages_share_licenses_neither():
    """`dos` is the Spanish numeral and it was in the Portuguese list alone, so the subtraction
    never saw it and it stayed unique to Portuguese. Measured over the census render store: 379 of
    the 673 Portuguese page findings rested on it and nothing else, on 297 sites; thirty were read
    by eye and every one was Spanish."""
    es = set(LA._fold(LA.FUNC['Spanish']).split())
    pt = set(LA._fold(LA.FUNC['Portuguese']).split())
    assert 'dos' in es and 'dos' in pt
    assert 'dos' in LA._SHARED
    assert not LA.FUNC_ONLY_RX['Portuguese'].search('dos')
    assert not LA.FUNC_ONLY_RX['Spanish'].search('dos')
    # the case it was doing damage on: a Spanish sentence counting to two
    spanish = ('No hay dos personas que experimenten el duelo de la misma manera, y cada familia '
               'puede pedir ayuda con este proceso cuando la necesite.')
    assert LA.languages_in(spanish, aux=False) == ['Spanish']


def test_english_shares_no_word_with_another_language():
    """The property the whole English addition rests on, and the one a later edit can break.

    `_SHARED` is counted over the other twenty lists and English is left out of the count, so that
    adding a twenty-first list could not thin any existing language's unique-word licence. That is
    safe only while the English list is disjoint from all twenty: a word in both English and German
    would be unique to German by the count and would still license English off German prose, which
    is the failure `dos` was for Spanish and Portuguese. Two words were dropped from the English
    list for exactly this reason, `once`, which is Turkish, and `take`, which is Ukrainian.
    """
    english = set(LA._fold(LA.FUNC['English']).split())
    others = set()
    for name, words in LA.FUNC.items():
        if name != 'English':
            others |= set(LA._fold(words).split())
    assert english & others == set(), (
        'these English words are also in another language list, so `_SHARED` no longer describes '
        'the language they were taken from: %s' % sorted(english & others))
    assert english & LA._SHARED == set()
    # and therefore English's own licence is its whole list and can never be the binding test
    assert set(LA._fold(LA.FUNC['English']).split()) - LA._SHARED == english


def test_adding_english_left_every_other_languages_licence_where_it_was():
    """`_SHARED` is the twenty-language set, and each language keeps every unique word it had.

    Recomputed here from the dict itself rather than compared with a recorded list, so the test
    states the rule instead of a snapshot of it: whatever the twenty lists hold, the subtraction
    set is what they share with EACH OTHER and English is not a party to it.
    """
    # Twenty-one since Oromo was added 2026-09-17. The number is not what this test holds; the
    # RULE is, which is that `_SHARED` is computed over the non-English lists and English is not a
    # party to it. The count is asserted so that a list arriving without anybody noticing fails
    # here, which is how Oromo's arrival was checked against every other language's licence.
    twenty = {k: v for k, v in LA.FUNC.items() if k != 'English'}
    assert len(twenty) == 21
    counted = collections.Counter(w for v in twenty.values()
                                  for w in set(LA._fold(v).split()))
    assert LA._SHARED == {w for w, c in counted.items() if c > 1}
    for name, words in twenty.items():
        own = set(LA._fold(words).split()) - LA._SHARED
        assert own, '%s has no word of its own' % name
        assert LA.FUNC_ONLY_RX[name].pattern == (
            r'\b(?:' + '|'.join(sorted(own)) + r')\b'), (
            '%s no longer licenses itself on the words it licensed itself on' % name)


def test_english_is_read_by_the_paragraph_rule_like_every_other_latin_language():
    """Four distinct function words inside one window, and a label or an address is not a page."""
    assert LA.languages_in('Our services for the community are free and open to all families '
                           'across the county every week of the year.', aux=False) == ['English']
    # below the four-distinct-words floor, which is what keeps a nav label out
    assert LA.languages_in('Home About Contact Donate', aux=False) == []
    assert LA.languages_in('Casa Buena Community Center, 123 Main Street, Suite 4',
                           aux=False) == []
    # a Spanish paragraph names Spanish and NOT English, which is the informative half
    assert LA.languages_in(
        'Nuestros servicios para la comunidad son gratuitos. Ofrecemos informacion y recursos '
        'para las familias que necesitan ayuda con este proceso.', aux=False) == ['Spanish']


def test_english_needs_no_orthographic_licence_and_is_not_in_the_pair_system():
    """ORTHO_ONLY is the Spanish-Portuguese pair machinery and English is not part of it.

    `languages_in` asks for an orthographic mark only when the unique-word test has already failed,
    and English's unique-word test cannot fail while its list is disjoint from the other twenty. So
    English reaches a reading on words alone and reaches it without a mark, which the second
    assertion pins on a page that carries none.
    """
    assert 'English' not in LA.ORTHO_ONLY
    plain = ('Our office provides free legal help to immigrant families across the county every '
             'day of the week and anyone can make an appointment with a caseworker.')
    assert not re.search(r'[^\x00-\x7f]', plain), 'the fixture has to be plain ASCII'
    assert LA.languages_in(plain, aux=False) == ['English']


def test_a_mark_one_of_the_pair_writes_licenses_the_reading_the_words_cannot():
    """The second licence, and both languages of the pair, on prose that carries no unique word."""
    assert LA.languages_in(SHARED_SPANISH, aux=False) == []
    assert LA.languages_in(SHARED_SPANISH.replace('ninos', 'niños'), aux=False) == ['Spanish']
    assert LA.languages_in(SHARED_PORTUGUESE, aux=False) == []
    assert LA.languages_in(SHARED_PORTUGUESE + ' Mais informação e apoio.',
                           aux=False) == ['Portuguese']


def test_the_mark_has_to_be_inside_the_window_that_fired():
    """Page-scoped, the mark adds 5 Portuguese sites and 29 Spanish ones to the census render store
    and the failures are all one shape: a mark somewhere else on a long multilingual page, a
    Brazilian organization's name in a Spanish donor list, an enye on four Portuguese pages.
    Window-scoped it adds 1 and 14 and every one of the fifteen is right."""
    far = SHARED_SPANISH + (' filler ' * 200) + ' niños'
    assert LA.languages_in(far, aux=False) == []
    assert LA.languages_in(SHARED_SPANISH + ' niños', aux=False) == ['Spanish']


def test_the_portuguese_mark_is_the_cedilla_form_and_not_the_bare_tilde():
    """Vietnamese writes ã and õ, and the wider form fired on a county page whose window held a
    Spanish notice next to a Vietnamese one. `São Tomé & Príncipe` in a country dropdown is the
    other shape it would have caught, on five sites of the census render store."""
    country_list = SHARED_PORTUGUESE + ' Samoa San Marino São Tomé & Príncipe Saudi Arabia'
    assert LA.languages_in(country_list, aux=False) == []
    assert LA.ORTHO_ONLY['Portuguese'].search('informação')
    assert LA.ORTHO_ONLY['Portuguese'].search('Percepções')
    assert not LA.ORTHO_ONLY['Portuguese'].search('São Paulo')
    assert not LA.ORTHO_ONLY['Portuguese'].search('CẢNH BÁO HÃY CẨN THẬN')


def test_only_the_measured_pair_has_a_mark_list():
    """A mark list for a language whose words are not shared would be a rule with nothing behind it,
    so the entries are the two the measurement covered and no others."""
    assert sorted(LA.ORTHO_ONLY) == ['Portuguese', 'Spanish']


def test_the_offset_map_reproduces_the_fold():
    """`_fold_offsets` is only correct if its text is `_fold`'s own, and the reason it exists at all
    is that NFKD is not length-preserving: the ligature expands, the decomposed letter contracts."""
    cases = ['ﬁne', '½ cup', '①', 'ﾊ', 'café', 'niño',
             'ação', '', ' ', 'क्ष', SHARED_SPANISH, SHARED_PORTUGUESE,
             SORANI_PROSE, KURMANJI_PROSE, PASHTO_PROSE]
    for t in cases:
        folded, idx = LA._fold_offsets(t)
        assert folded == LA._fold(t), repr(t)
        assert len(idx) == len(folded)
        assert all(0 <= i < len(t) for i in idx)
        assert idx == sorted(idx)
    # and the drift it protects against is real rather than theoretical
    drifty = 'oﬁcina ½ hora niños'
    assert len(LA._fold(drifty)) != len(drifty)


def test_the_spans_agree_with_the_yes_or_no():
    """`_paragraph_spans` is the same search as `_in_one_paragraph` reporting where it landed, and a
    reading now depends on the two agreeing, so the agreement is asserted rather than assumed."""
    for text in (SHARED_SPANISH, SHARED_PORTUGUESE, 'nothing here at all',
                 'para para para para', SHARED_SPANISH + ' ' * 900 + SHARED_SPANISH):
        folded = LA._fold(text)
        for name, rx in LA.FUNC_RX.items():
            hits = [(m.start(), m.group(0).lower()) for m in rx.finditer(folded)]
            assert bool(LA._paragraph_spans(hits)) is LA._in_one_paragraph(hits), (name, text[:40])


def test_a_verdict_of_multilingual_has_to_name_the_language():
    """239 organizations were published as true_multilingual with no language recorded, which is a
    claim a reader has no way to check."""
    unnamed = [LA.Evidence('translation_plugin', 'https://x.org/', 'wpml', '')]
    assert LA.verdict_for(unnamed, '') == 'english_only'
    named = [LA.Evidence('inline_text', 'https://x.org/', 'texto', 'Spanish')]
    assert LA.verdict_for(named, '') == 'true_multilingual'


NOT_A_WEBSITE_CASES = [
    ('a Facebook page', 'www.facebook.com', True),
    ('an Instagram page', 'instagram.com', True),
    ('a builder subdomain the org runs', 'someorg.wordpress.com', False),
    ('an ordinary domain', 'example.org', False),
]


@pytest.mark.parametrize('name,host,want', NOT_A_WEBSITE_CASES, ids=[c[0] for c in NOT_A_WEBSITE_CASES])
def test_a_social_page_is_not_the_organizations_website(name, host, want):
    """A social page's language handling belongs to the platform. A site-builder subdomain is the
    organization's own site; it has simply not bought a domain, and 185 in the census are like that."""
    assert bool(LA.SOCIAL_HOST.match(host)) is want


PARKED_CASES = [
    ('a registrar sales page', 'This domain is for sale. Inquire about this domain today.', True),
    ('a parking service', 'This webpage was generated by the domain owner using Sedoparking', True),
    ('an ordinary page', 'Welcome to our community center. We offer free legal help and ESL classes.',
     False),
    ('a page that mentions selling', 'Our thrift store sells donated clothing to fund our programs.',
     False),
]


@pytest.mark.parametrize('name,text,want', PARKED_CASES, ids=[c[0] for c in PARKED_CASES])
def test_a_parked_domain_is_not_the_site(name, text, want):
    """Reporting english_only for a registrar's sales page says something about an organization's
    website that was never checked, the same confusion a bot wall would cause."""
    assert bool(LA.PARKED_RX.search(text)) is want


JAPANESE_CASES = [
    # a Japanese sentence alternates kana and kanji. Reading the two ranges as separate scripts
    # meant neither ever formed a long enough run, and a Japanese weekend school and a Japanese
    # prefectural association were reported english_only.
    ('a Japanese sentence',
     'さくら日本語学校は、日本語を母語とする子どもたちのために国語教育を提供しています。', ['Japanese']),
    ('a Chinese sentence with no kana',
     'ACSC致力于通过评估、导航和协助亚裔老年社区成员的社交需求，为他们提供全面的支持服务。', ['Chinese']),
]


@pytest.mark.parametrize('name,text,want', JAPANESE_CASES, ids=[c[0] for c in JAPANESE_CASES])
def test_japanese_is_kana_and_kanji_together(name, text, want):
    assert LA.languages_in(text) == want


def test_rule_six_belongs_to_route_based_widgets_only():
    """Weglot and GTranslate serve a translated page at a real address, so one of their routes
    coming back in English shows the widget translates nothing. The Google Translate element
    publishes no address and rewrites the page in place, so a /es guess returning English shows
    only that there is no /es. Six sites moved to english_only before this distinction existed."""
    assert LA.ROUTE_WIDGET.search('<script src="cdn.weglot.com/weglot.min.js">')
    assert LA.ROUTE_WIDGET.search('gtranslate_wrapper')
    assert not LA.ROUTE_WIDGET.search('<div id="google_translate_element"></div>')


LABEL_CASES = [('中文版', True), ('中文', True), ('한국어 페이지', True), ('Español', True),
               ('Home', False), ('Read more in Spanish about our services', False)]


@pytest.mark.parametrize('label,want', LABEL_CASES, ids=[c[0] for c in LABEL_CASES])
def test_a_language_name_with_a_suffix_is_still_a_control(label, want):
    """One Chinese cultural institute keeps its Chinese site behind a nav item reading
    中文版, which an exact match on 中文 never recognised."""
    assert bool(LA.LANGLABEL.match(label)) is want


def test_the_audit_body_has_no_undefined_names():
    """A name that exists only on a branch taken by some sites fails there and nowhere else: a
    reference to `html` instead of `home_html` inside the route loop raised NameError on 13 of 115
    sites in one run, and each was recorded as unreachable rather than as a crash."""
    import ast, builtins, inspect, textwrap
    tree = ast.parse(textwrap.dedent(inspect.getsource(LA._audit_async)))
    bound, used = set(), set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            (bound if isinstance(node.ctx, ast.Store) else used).add(node.id)
        elif isinstance(node, ast.arg):
            bound.add(node.arg)
        elif isinstance(node, ast.ExceptHandler) and node.name:
            bound.add(node.name)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            bound.update((a.asname or a.name).split('.')[0] for a in node.names)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            bound.add(node.name)
    unknown = {n for n in used - bound if not hasattr(builtins, n) and not hasattr(LA, n)}
    assert not unknown, f'names used but never bound in _audit_async: {sorted(unknown)}'


def test_the_pages_are_handed_back_only_when_asked_for():
    """Reading a site with a real browser is the expensive part. A caller that wants to derive
    social links or contacts from the same read should not have to fetch it again, but a caller
    that only wants the verdict should not carry megabytes of HTML through a JSON line."""
    import inspect
    for fn in (LA.audit, LA.audit_async):
        p = inspect.signature(fn).parameters
        assert 'keep_pages' in p and p['keep_pages'].default is False
    r = LA.Result(url='https://x.org/')
    assert r.pages == {}
    r.pages['https://x.org/'] = '<html>...</html>'
    assert 'pages' not in r.to_dict()
    assert 'pages' in r.to_dict(with_pages=True)


# ---------------------------------------------------------------- guessed vs published locale route
def test_guessed_locale_routes_are_marked():
    """A route invented from TRY_PATHS is a guess; one the page links to is not.

    The difference decides what an English response means, and five sites were called english_only
    because a guessed /es came back in English on a widget that rewrites the page in place.
    """
    html = '<html><body><a href="/es/">Espanol</a></body></html>'
    guessed = set()
    urls = LA._routes(html, 'https://x.org/', guessed=guessed)
    assert 'https://x.org/es' in {u.rstrip('/').lower() for u in urls}
    assert 'https://x.org/es' not in guessed          # the page links to it
    assert 'https://x.org/ko' in guessed              # nothing links to this one


def test_a_page_with_no_language_links_guesses_everything():
    guessed = set()
    LA._routes('<html><body><a href="/about">About</a></body></html>', 'https://x.org/',
                 guessed=guessed)
    assert 'https://x.org/es' in guessed


# ---------------------------------------------------------------- langid needs corroboration
def test_aux_language_needs_two_blocks():
    """One block naming a language is langid noise; the reading has to repeat."""
    filler = 'x' * 10
    one = ('The organization serves families across the county and the surrounding region here. '
           + filler + '. ')
    # a block long enough to be classified, repeated so the same language lands twice
    sw = ('Shirika letu linatoa huduma za msaada kwa familia zote katika mkoa wetu na maeneo '
          'yanayozunguka kwa lugha ya Kiswahili kila siku ya wiki bila malipo yoyote kwa wale '
          'wanaohitaji msaada wa haraka. ')
    assert 'Swahili' not in LA._aux_languages(one + sw, covered=set())
    assert 'Swahili' in LA._aux_languages(one + sw + sw, covered=set())


def test_aux_never_overrides_a_covered_language():
    sw = ('Shirika letu linatoa huduma za msaada kwa familia zote katika mkoa wetu na maeneo '
          'yanayozunguka kwa lugha ya Kiswahili kila siku ya wiki bila malipo yoyote kwa wale '
          'wanaohitaji msaada wa haraka. ')
    assert LA._aux_languages(sw + sw, covered={'Swahili'}) == []


def test_bosnian_greeting_is_read():
    """One ordinary sentence of Bosnian is a paragraph.

    One Bosnian Islamic community center opens with "Esselamu alejkum i dobro dosli na
    zvanicnu web stranicu dzemata", and the coders called the site multilingual on it; the list held
    two of its words, one short of the four a paragraph needs. The address block below carries the
    shape of the capture and none of its identifying detail.
    """
    t = ('NBICC bosanski dzemat 4187 North Clearbrook Avenue Ashford IN USA top of page Menu '
         'Donate Log In Esselamu alejkum i dobro dosli na zvanicnu web stranicu dzemata Northside '
         'Bosnian Islamic Community Center Ashford USA Join Us ') * 2
    assert 'Bosnian/Croatian/Serbian' in LA.languages_in(t)


def test_english_boilerplate_stays_english():
    """the guard on every word-list change: an ordinary English page names no language but English

    What this guards did not change when English got a list of its own on 2026-08-04: an English
    page must still name no OTHER language, and that is what a word-list change can break. It now
    also names English, which guards the same list in the other direction, since a list that could
    not read this page would be a list that reads nothing.
    """
    t = ('Welcome home. We provide free services to families in our community every day of the week '
         'and we do not charge anyone for help with housing, food, or legal questions. Contact us '
         'to make an appointment with a caseworker at any of our offices. ') * 3
    assert LA.languages_in(t) == ['English']


# ---------------------------------------------------------------- rules settled 2026-07-28
def test_under_a_widget_an_authored_page_and_an_authored_notice_both_count():
    """A whole page in the language at the organization's own address is a service; one pro bono
    legal project keeps /legal-assistance-spanish.

    Was `test_under_a_widget_a_page_counts_alone_and_a_fragment_needs_two`, and the second
    assertion was machine_translate from 2026-07-28 to 2026-07-30. One community house is the site
    behind it: one Spanish notice about DACA renewals inside an English services page, under a
    Google Translate widget. Rule 10's prose names that site as the negative example, and the
    project's own answer key codes it true_multilingual under rule 10: a whole Spanish notice about
    DACA renewals at the organization's own /services/immigration/, which rule 10 counts on its own
    even under a widget. The derivation follows the answer key: the notice is authored, because a widget that
    rewrites the page in the browser cannot put it in the server's response, and it is level 2,
    because it tells a reader one actionable thing. Counting to two was standing in for that."""
    page = [LA.Evidence('translated_page', 'https://x.org/legal-assistance-spanish', 'asistencia', 'Spanish')]
    frag = [LA.Evidence('inline_text', 'https://x.org/', 'Declaracion sobre', 'Spanish')]
    assert LA.verdict_for(page, 'Weglot') == 'true_multilingual'
    assert LA.verdict_for(frag, 'Google Translate') == 'true_multilingual'
    assert LA.verdict_for(frag * 2, 'Google Translate') == 'true_multilingual'


def test_a_locale_mirror_is_counted_at_the_front_door_only():
    """Five languages of one deep page is a platform translating what it was pointed at; five
    front doors is a platform. One Asian American legal advocacy organization has /ko/ and /vi/ and
    a Chinese hotline page beneath them, and it is a genuinely multilingual site. The count is what
    moved on 2026-08-10; what this pins is where it is taken."""
    front = [LA.Evidence('translated_page', f'https://x.org/{c}', 'texto', l)
             for c, l in (('es', 'Spanish'), ('fr', 'French'), ('pt', 'Portuguese'),
                          ('it', 'Italian'), ('nl', 'Dutch'))]
    deep = [LA.Evidence('translated_page', f'https://x.org/{c}/school/riverbend', 'texto', l)
            for c, l in (('es', 'Spanish'), ('fr', 'French'), ('de', 'German'),
                         ('it', 'Italian'), ('nl', 'Dutch'))]
    assert LA.verdict_for(front, '') == 'machine_translate'
    assert LA.verdict_for(deep, '') == 'true_multilingual'


def test_five_locale_mirrors_without_a_marker_are_machine_translation():
    """The threshold was three until 2026-08-10, when re-judging the validation capture at each
    value showed three overriding three sites that genuinely run a locale tree, and none the other
    way. Four and five score identically there, no site advertising exactly four, so the more
    conservative of the two was taken: this rule overrides the recorded axes outright."""
    ev = [LA.Evidence('translated_page', 'https://x.org/es', 'Iniciar sesion', 'Spanish'),
          LA.Evidence('translated_page', 'https://x.org/fr', 'Etre implique', 'French'),
          LA.Evidence('translated_page', 'https://x.org/pt', 'Se envolver', 'Portuguese'),
          LA.Evidence('translated_page', 'https://x.org/de', 'Mitmachen', 'German'),
          LA.Evidence('translated_page', 'https://x.org/it', 'Partecipa', 'Italian')]
    assert LA.verdict_for(ev, '') == 'machine_translate'
    assert LA.verdict_for(ev[:4], '') == 'true_multilingual'     # four is not a platform signature


def test_a_mirror_count_needs_locale_routes():
    """Three languages at ordinary addresses is an organization writing, not a platform mirroring."""
    ev = [LA.Evidence('translated_page', 'https://x.org/nuestros-programas', 'texto', 'Spanish'),
          LA.Evidence('translated_page', 'https://x.org/nos-programmes', 'texte', 'French'),
          LA.Evidence('translated_page', 'https://x.org/nossos-programas', 'texto', 'Portuguese')]
    assert LA.verdict_for(ev, '') == 'true_multilingual'


def test_an_archive_page_does_not_carry_the_reading():
    """One German heritage society keeps one German paragraph, a write-up of its 2016 Christmas
    party."""
    old = [LA.Evidence('translated_page', 'https://x.org/category/past_events/', 'Weihnachtsfeier', 'German')]
    live = [LA.Evidence('translated_page', 'https://x.org/services/legal/', 'Rechtsberatung', 'German')]
    assert LA.verdict_for(old, '') == 'english_only'
    assert LA.verdict_for(live, '') == 'true_multilingual'


def test_news_is_not_an_archive():
    """A current announcement often lives at /news/, so the path list stops short of it."""
    ev = [LA.Evidence('translated_page', 'https://x.org/news/nueva-clinica', 'texto', 'Spanish')]
    assert LA.verdict_for(ev, '') == 'true_multilingual'


def test_a_bare_label_is_not_a_paragraph():
    """"Board Interest Form / Formulario de Interes" is a noun phrase, not a sentence."""
    label = 'Board Interest Form / Formulario de Interes ' * 6
    assert LA.languages_in(label) == []


def test_the_sites_own_links_are_read_before_invented_ones():
    """A fixed page budget spent on guesses is a page of the organization's own not read.

    Deep mode queued 46 invented addresses ahead of the interior links and came back from one
    community house and one Cambodian cultural center with nothing, while default mode found the
    Spanish DACA notice and the Khmer contact line.
    """
    html = ('<a href="/es/">Espanol</a><a href="/services/immigration">Immigration</a>'
            '<a href="/youth-programs">Youth</a>')
    guessed = set()
    routes = LA._routes(html, 'https://x.org/', deep=True, guessed=guessed)
    published = [u for u in routes if u.rstrip('/').lower() not in guessed]
    interior = LA._interior(html, 'https://x.org/')
    invented = [u for u in routes if u.rstrip('/').lower() in guessed]
    order = published + interior + invented
    assert order.index('https://x.org/es/') < order.index('https://x.org/services/immigration')
    assert order.index('https://x.org/services/immigration') < order.index('https://x.org/korean')
    assert order.index('https://x.org/youth-programs') < order.index('https://x.org/spanish')


def test_a_lunar_date_line_is_not_a_chinese_paragraph():
    """One area Chinese association prints the lunar date over an English page. Twenty-odd
    CJK characters, and nothing a reader can take a service from."""
    t = ('7/29/2026 (丙午年[马] 农历二零二六年六月十六 星期三) Create an account Log In Web Mail Home '
         'HVCA Chinese School Chinese Cultural Resources Membership Contact Us ') * 2
    assert 'Chinese' not in LA.languages_in(t)


def test_real_chinese_prose_still_reads_even_with_a_date_in_it():
    t = ('本會成立於一九八二年，為華人移民家庭提供中文學校、法律諮詢轉介與社區服務。'
         '我們每週六上午開課，歡迎新生報名，詳情請洽辦公室。') * 2
    assert 'Chinese' in LA.languages_in(t)


def test_three_advertised_front_doors_settle_it_without_reading_them():
    """The same Cape Verdean community organization links /es, /fr and /pt. Reading only /es before
    the budget ran out flipped the site between two runs of identical code, so the rule counts the
    links."""
    ev = [LA.Evidence('translated_page', 'https://x.org/es', 'Iniciar sesion', 'Spanish')]
    assert LA.verdict_for(ev, '') == 'true_multilingual'
    assert LA.verdict_for(ev, '', advertised_roots=5) == 'machine_translate'


def test_a_wordpress_category_listing_is_an_archive():
    """The same German heritage society's German sits in /category/past_events/ and
    /category/members-news/, both listings of old posts. A single current post at /news/ is still
    read."""
    cat = [LA.Evidence('translated_page', 'https://x.org/category/members-news/', 'Sommerfest', 'German')]
    news = [LA.Evidence('translated_page', 'https://x.org/news/nueva-clinica', 'texto', 'Spanish')]
    letter = [LA.Evidence('translated_page', 'https://x.org/afab-may-newsletter/', 'INVITATION', 'French')]
    assert LA.verdict_for(cat, '') == 'english_only'
    assert LA.verdict_for(letter, 'Google Translate') == 'machine_translate'
    assert LA.verdict_for(news, '') == 'true_multilingual'


def test_hreflang_is_read_whichever_attribute_comes_first():
    """HTML does not fix attribute order, and /pt is a locale route with or without a trailing
    slash. The same Cape Verdean community organization declares three alternates and links all
    three; the tool saw none of them, so the rule that needs three front doors never fired.
    Asserted on the PUBLISHED set, because /fr and /pt are also in TRY_PATHS and a weaker assertion
    passed without the fix."""
    html = ('<link rel="alternate" hreflang="es-es" href="https://x.org/es"/>'
            '<link rel="alternate" href="https://x.org/fr" hreflang="fr-fr"/>'
            '<link rel="alternate" href="https://x.org/pt" hreflang="pt-cv"/>'
            '<link rel="alternate" href="https://x.org/en" hreflang="en-us"/>'
            '<link rel="alternate" href="https://x.org/" hreflang="x-default"/>')
    guessed = set()
    routes = LA._routes(html, 'https://x.org/', guessed=guessed)
    published = [u for u in routes if u.rstrip('/').lower() not in guessed]
    assert {u for u in published if LA.LOCALE_ROOT.search(u)} == {
        'https://x.org/es', 'https://x.org/fr', 'https://x.org/pt'}
    assert not any(u.rstrip('/').endswith('/en') for u in published)


def test_a_locale_code_can_end_the_path():
    guessed = set()
    got = LA._routes('<a href="https://x.org/pt">PT</a>', 'https://x.org/', guessed=guessed)
    assert 'https://x.org/pt' in got and 'https://x.org/pt' not in guessed


LOCALE_SHAPES = [
    ('https://x.org/es', True), ('https://x.org/es/', True), ('https://x.org/sw/', True),
    ('https://x.org/zh-hans/', True), ('https://x.org/fil/', True), ('https://es.x.org/', True),
    ('https://x.org/?lang=es', True),
    # a widget serving a deep page under its locale prefix is still the widget's output, so this
    # one IS a locale route; only rule 17's front-door count uses the narrower LOCALE_ROOT
    ('https://x.org/es/school/ai-hwa', True),
    ('https://x.org/services/', False),
    # three letters and not a language: reading /web/ as a locale route took an online Hungarian
    # school's own Hungarian pages away from it
    ('https://x.org/web/', False), ('https://x.org/web/oktatas/hungarian-classes', False),
    ('https://x.org/api/v2/', False), ('https://x.org/wp/', False),
    ('https://x.org/legal-assistance-spanish', False), ('https://x.org/', False),
]


@pytest.mark.parametrize('url,want', LOCALE_SHAPES, ids=[u for u, _ in LOCALE_SHAPES])
def test_a_bare_short_first_segment_is_a_locale_route(url, want):
    """A widget serves whatever it was configured for. One state poverty-law center runs
    Weglot at /es/, /vi/, /zh/ and /sw/, and Swahili was missing from the enumerated list, so that
    one page counted as the organization's own writing and carried the whole site."""
    assert bool(LA.LOCALE_ROUTE.search(url)) is want


def test_a_national_affiliate_at_a_locale_path_is_not_this_site_multilingual():
    """One international refugee agency keeps its national organizations at /de, /se and /kr. Two
    of those codes were missing from the front-door list, so three mirrors counted as one and the
    site was called multilingual on other organizations' pages."""
    ev = [LA.Evidence('translated_page', f'https://x.org/{c}', 'text', l)
          for c, l in (('de', 'German'), ('se', 'Swedish'), ('kr', 'Korean'),
                       ('it', 'Italian'), ('nl', 'Dutch'))]
    assert all(LA.LOCALE_ROOT.search(e.url) for e in ev)
    assert LA.verdict_for(ev, '') == 'machine_translate'


def test_a_language_needs_its_own_script():
    """langid answered Urdu for an English navigation bar in capitals, and one advocacy nonprofit was
    called multilingual on 'HOME ABOUT NEWS STAFF BOARD OF DIRECTORS'. Urdu is written in Arabic
    script; text with none of it cannot be Urdu, whatever a classifier says."""
    nav = ('HOME ABOUT ABOUT NEWS STAFF BOARD OF DIRECTORS JOURNEY OF HOPE AWARD WORK WITH US '
           'HISTORY ANNUAL REPORTS CONTACT DONATE VOLUNTEER ') * 4
    assert 'Urdu' not in LA.languages_in(nav)
    assert LA._script_allows('Urdu', 'یہ اردو میں ایک جملہ ہے') is True
    assert LA._script_allows('Urdu', 'this is english') is False
    assert LA._script_allows('Spanish', 'esto es espanol') is True     # no script requirement


def test_interior_falls_back_when_no_link_matches_a_keyword():
    """One design studio keeps its Spanish on /mirador and no keyword list has that word. A filter
    that matches nothing left the crawl with no interior pages at all."""
    html = ('<a href="/mirador">Mirador</a><a href="/colmena">Colmena</a>'
            '<a href="/almendra">Almendra</a>')
    got = LA._interior(html, 'https://x.org/')
    assert 'https://x.org/mirador' in got
    # and the keyword filter still leads when it does match
    html2 = html + '<a href="/services/immigration">Immigration Services</a>'
    assert LA._interior(html2, 'https://x.org/')[0] == 'https://x.org/services/immigration'


def test_the_keyword_free_fallback_stays_shallow():
    deep = '<a href="/a/b/c/d/e">Deep</a><a href="/about-x">Shallow</a>'
    got = LA._interior(deep, 'https://x.org/')
    assert 'https://x.org/a/b/c/d/e' not in got


# ---------------------------------------------------------------- accuracy pass, 2026-07-29
# Each case below was diagnosed by re-reading a failing site live, and each pins a CLASS of defect
# rather than the site that exposed it: no site name, domain or path appears in any of the rules.
import re as _re

FOUR_OH_THREE = ('Server Error 403 Forbidden You do not have permission to access this document. '
                 "That's what you can do Reload Page Back to Previous Page Home Page")


REFUSAL_CASES = [
    ('a bare 403 body', FOUR_OH_THREE, True),
    ('a 500 page', 'Server Error. Please try again later.', True),
    ('a permission refusal', 'You do not have permission to view this directory or page.', True),
    ('an authorization refusal', 'Not authorized. An API key is required.', True),
    ('a blocked request', 'Request blocked. Your request was identified as automated traffic.', True),
    ('a throttle', 'Rate limited: too many requests from this address.', True),
    ('an ordinary page mentioning permission',
     'We provide free legal help to immigrant families. You do not need permission to attend our '
     'weekly English classes, and every service is open to everyone in the community.', False),
]


@pytest.mark.parametrize('name,text,want', REFUSAL_CASES, ids=[c[0] for c in REFUSAL_CASES])
def test_a_refusal_is_not_an_english_page(name, text, want):
    """A server saying no is a site that was not read, which is unreachable and never english_only.
    A 145-character 403 body matched none of the wall patterns and was classed as English."""
    assert bool(LA.WALL_RX.search(text)) is want


def test_the_google_translate_loader_is_still_the_google_widget():
    """The element's own markers only exist after its script has run, and a consent gate means it
    never does. The loader that installs it is in the page either way, and rule 14 says a
    widget that never appears is still a widget."""
    consent_gated = ('<script>function googleTranslateElementInit2(){}</script>'
                     '<script src="https://translate.google.com/translate_a/element.js'
                     '?cb=googleTranslateElementInit2"></script>')
    assert 'goog-te' not in consent_gated and 'google_translate_element' not in consent_gated
    named = [nm for nm, pat in LA.MT_NAME if _re.search(pat, consent_gated, _re.I)]
    assert named[:1] == ['Google Translate']


def test_an_ordinary_translate_link_is_not_an_installed_widget():
    """A hyperlink offering Google Translate is not a widget in the page, and MT_RX read the proxy
    marker translate.goog as a substring of translate.google.com, so the two constants answered
    opposite things about the same page."""
    link = '<a href="https://translate.google.com/?sl=en&tl=es">Translate this page</a>'
    assert not LA.MT_RX.search(link)
    assert not [nm for nm, pat in LA.MT_NAME if _re.search(pat, link, _re.I)]
    assert LA.MT_RX.search('<a href="https://x-org.translate.goog/services">es</a>')


def test_a_verdict_does_not_ship_the_languages_it_rejected():
    """Three mirrored front doors make a site machine_translate under rule 17, and the languages on
    those mirrors belong to three other organizations. A row carrying them says the census found
    German, Korean and Swedish at an address whose verdict says it found none of them."""
    ev = [LA.Evidence('translated_page', 'https://x.org/de', 'text', 'German'),
          LA.Evidence('translated_page', 'https://x.org/se', 'text', 'Swedish'),
          LA.Evidence('translated_page', 'https://x.org/kr', 'text', 'Korean'),
          LA.Evidence('translated_page', 'https://x.org/it', 'text', 'Italian'),
          LA.Evidence('translated_page', 'https://x.org/nl', 'text', 'Dutch')]
    assert LA.verdict_for(ev, '') == 'machine_translate'
    # the no-widget branch counts them, so they are the verdict's own languages
    assert [e.language for e in LA.counted_evidence(ev, '')] == [
        'German', 'Swedish', 'Korean', 'Italian', 'Dutch']
    # under a widget the same three are the widget's own output and are rejected, so none is shipped
    assert LA.counted_evidence(ev, 'Google Translate') == []
    # an unnamed language is not shippable either, for the same reason rule 12 exists
    assert LA.counted_evidence([LA.Evidence('inline_text', 'https://x.org/', 'q', '')], '') == []


def test_counted_evidence_is_what_the_verdict_used():
    """The helper and the rule cannot disagree, because the rule is written on the helper."""
    archived = LA.Evidence('translated_page', 'https://x.org/category/past_events/', 'q', 'German')
    live = LA.Evidence('translated_page', 'https://x.org/services/legal/', 'q', 'German')
    assert LA.counted_evidence([archived], '') == []
    assert LA.counted_evidence([archived, live], '') == [live]


def test_an_interior_page_carries_sixteen_links_not_eight():
    """The site-wide nav is emitted first in every page's HTML, so a cap of eight returned the same
    eight links from every page and the second hop stopped happening. The page that mattered on one
    site was the twelfth keyword-matching link on its home page."""
    html = ''.join(f'<a href="/services/{i}">Service {i}</a>' for i in range(30))
    got = LA._interior(html, 'https://x.org/')
    assert len(got) == 16
    assert 'https://x.org/services/11' in got


def test_a_link_written_in_the_language_is_read_first():
    """PAGE_KW is an English vocabulary, so the link most likely to lead to non-English content is
    exactly the one it drops. Promotion is on a LETTER outside ASCII, not on another word list."""
    html = (''.join(f'<a href="/about-{i}">About {i}</a>' for i in range(20))
            + '<a href="/servicios-de-inmigracion-y-ciudadania">'
              'Servicios Legales de Inmigraci&oacute;n</a>')
    got = LA._interior(html, 'https://x.org/')
    assert got[0] == 'https://x.org/servicios-de-inmigracion-y-ciudadania'
    # a curly apostrophe and an en-dash are punctuation and promote nothing
    quiet = '<a href="/about-us">Who we are – our team’s story</a>'
    assert LA._interior(quiet, 'https://x.org/') == ['https://x.org/about-us']


def test_a_hash_router_site_has_interior_pages_after_all():
    """Every internal link on a single-page site is a fragment, and the crawler threw all of them
    away, so the whole budget went on guessed paths that 404."""
    html = ('<a href="#quienes-somos">Quienes somos</a><a href="#visitanos">Visitanos</a>'
            '<a href="#dar">Dar</a><a href="#english">English</a><a href="#top">Top</a>'
            '<a href="#quienes-somos">Quienes somos</a>')
    assert LA._interior(html, 'https://x.org/') == [
        'https://x.org/#quienes-somos', 'https://x.org/#visitanos',
        'https://x.org/#dar', 'https://x.org/#english']
    # a site with real interior links does not fall back to its fragments
    assert LA._interior(html + '<a href="/services">Services</a>',
                        'https://x.org/') == ['https://x.org/services']


def test_a_guessed_locale_route_follows_the_path_the_site_was_audited_at():
    """An organization audited at a subpath is not at the domain root, and every guess was aimed at
    the root, so a subpath site was asked for addresses belonging to whoever owns the domain."""
    got = LA._routes('<a href="/about">About</a>', 'https://x.org/someorg-erie/')
    assert 'https://x.org/someorg-erie/es' in got
    assert 'https://x.org/es' in got          # the root guesses are kept as well
    # a site audited at the root is guessed exactly as it was before
    assert all(u.count('/') == 3 for u in LA._routes('<a href="/about">About</a>', 'https://x.org/'))


def test_a_guess_cannot_walk_into_a_strangers_site_on_a_shared_host():
    """sites.google.com carries every Google Site in the world, so the host-only test let one
    organization's guess point at another's site. _same_site knows a builder host by its path."""
    base = 'https://sites.google.com/view/someorg/home'
    got = LA._routes('<a href="/view/someorg/about">About</a>', base)
    assert 'https://sites.google.com/es' not in got
    assert 'https://sites.google.com/view/someorg/home/es' in got


def test_language_coverage_at_known_ratios():
    """Script-aware on purpose. A Latin-script language is measured on the windows around its
    function words and a script on the share of characters, so the two are not one number, and a
    single measure would have downgraded real pages in one direction or the other."""
    es = ('Nuestros servicios para la comunidad son gratuitos. Ofrecemos informacion y recursos '
          'para las familias que necesitan ayuda con este proceso, y todos pueden hacer una cita. ')
    en = ('Our office provides free legal help to immigrant families across the county every day of '
          'the week. Call us to make an appointment with a caseworker today. ')
    zh = 'ACSC致力于通过评估导航和协助亚裔老年社区成员的社交需求，为他们提供全面的支持服务。'
    assert LA.language_coverage(es * 3, 'Spanish') > 0.9
    assert LA.language_coverage(en * 9 + es, 'Spanish') < 0.35
    assert LA.language_coverage(zh, 'Chinese') > 0.7
    assert LA.language_coverage(en * 5 + zh, 'Chinese') < 0.2
    assert 0.0 <= LA.language_coverage(en, 'Spanish') <= 1.0
    # a language with neither a word list nor a range here cannot be measured, and a coverage that
    # cannot be measured must never quietly downgrade a page
    assert LA.language_coverage(en, 'Chin') is None
    assert LA.language_coverage('', 'Spanish') is None


def test_a_low_coverage_interior_finding_is_a_notice_and_a_high_one_is_a_page():
    """The audit labelled every interior finding translated_page, so rule 10's page-versus-fragment
    distinction was standing in for "was this the home page", which is a different question. A
    single notice inside an otherwise English services page is a notice wherever the page sits, and
    the coverage cut is what tells the two apart.

    The first assertion was machine_translate from 2026-07-29 to 2026-07-30. The URL is one
    community house's own /services/immigration/, and the answer key codes that site
    true_multilingual under rule 10. What the coverage cut decides is the RUNG,
    2 against 3, and both rungs are on the counting side of the derivation."""
    frag = [LA.Evidence('inline_text', 'https://x.org/services/immigration/', 'aviso', 'Spanish')]
    page = [LA.Evidence('translated_page', 'https://x.org/legal-assistance-spanish', 'asis', 'Spanish')]
    assert LA.sufficiency_of(frag[0]) == LA.SUFF_NOTICE
    assert LA.sufficiency_of(page[0]) == LA.SUFF_PAGE
    assert LA.verdict_for(frag, 'Google Translate') == 'true_multilingual'
    assert LA.verdict_for(frag * 2, 'Google Translate') == 'true_multilingual'
    assert LA.verdict_for(page, 'Google Translate') == 'true_multilingual'
    # with no widget in the page the kind of finding changes nothing, which is rule 10's scope
    assert LA.verdict_for(frag, '') == 'true_multilingual'


def test_a_dated_post_address_is_told_from_a_page():
    """A sitemap of a site with a blog is mostly posts, and a post is not what this is looking for."""
    assert LA.DATED_POST.search('https://x.org/2019/07/our-summer-picnic/')
    assert LA.DATED_POST.search('https://x.org/blog/2026/12')
    assert not LA.DATED_POST.search('https://x.org/services/immigration/')
    assert not LA.DATED_POST.search('https://x.org/2019-annual-report')


# ---------------------------------------------------------------- accuracy pass 2, 2026-07-29
# The measurement behind this pass: on a seed-fixed random sample of 40 organizations whose own name
# implies a language, the published english_only reading is wrong on 31, and the leak is reach over
# detection by roughly four to one. Every widening below therefore ships with the narrowing that
# keeps it from firing on a site that is correctly english_only, and each case pins the CLASS of
# defect rather than the site that exposed it.

# ---- W1: the language's own half of a bilingual site is invisible to an English keyword list
def test_the_shallow_links_are_added_to_the_keyword_ones_not_swapped_for_them():
    """A bilingual site links its own half in its own language, at a path the builder invented.

    One association links its Chinese section as <a href="/blank-1">关于</a>: a builder default path
    under a Chinese label, so neither half can match an English keyword list. The non-keyword
    fallback only ran when the keyword branch was empty, and here it returned five English pages.
    """
    html = ('<a href="/about">About</a><a href="/services">Services</a><a href="/news">News</a>'
            '<a href="/contact">Contact</a><a href="/staff">Staff</a>'
            '<a href="/blank-1">关于</a><a href="/blank-2">Gallery</a>')
    got = LA._interior(html, 'https://x.org/')
    assert 'https://x.org/blank-1' in got, 'the non-keyword link is dropped when keywords matched'
    assert 'https://x.org/blank-2' in got
    assert got[0] == 'https://x.org/blank-1'      # the non-ASCII label still leads
    assert 'https://x.org/services' in got        # and the keyword pages are still read


# ---- W2: the site root is never fetched when the entry URL has a path
def test_a_site_recorded_at_a_path_still_has_its_front_door_read():
    """One organization is recorded at <host>/us/about/<name>/ and the root was never fetched,
    because "/" matches no keyword and nothing else queues it."""
    assert LA._site_root('https://x.org/us/about/someorg/') == 'https://x.org/'
    assert LA._site_root('https://x.org/') == ''            # already the front door
    assert LA._site_root('https://x.org') == ''
    # on a shared host the front door belongs to the platform, not to this organization
    assert LA._site_root('https://sites.google.com/view/someorg/home') == ''


# ---- W3: a locale mirror on a SUBDOMAIN is never probed
def test_a_locale_mirror_on_a_subdomain_is_probed():
    """One organization keeps a complete fourteen-page Spanish site at es.<host>, linked once from
    the home page and declared in no hreflang. TRY_PATHS only ever asks for <host>/es."""
    got = LA._subdomain_probes('https://www.example.org/')
    assert 'https://es.example.org/' in got and 'https://ko.example.org/' in got
    assert len(got) == len(LA.SUBDOMAIN_LOCALES)
    assert all(u.startswith('https://') and u.endswith('/') for u in got)
    assert LA._subdomain_probes('https://es.example.org/') == []       # already on the mirror
    # a builder host's subdomains belong to other organizations
    assert LA._subdomain_probes('https://sites.google.com/view/someorg/home') == []
    # these are guesses and not routes the SITE published, so _routes must not carry them
    assert not any('es.x.org' in u for u in LA._routes('<a href="/about">A</a>', 'https://x.org/'))


# ---- W4: LANGLABEL required the whole label to be the language name
LANGLABEL_RELAXED = [
    ('En Español', True),                 # the label on a link to a whole Spanish site
    ('View in Korean', True),
    ('Español', True),
    ('Read more in Spanish about our services', False),      # a sentence, not a switcher
    ('Español para familias inmigrantes', False),
    ('Home', False),
]


@pytest.mark.parametrize('label,want', LANGLABEL_RELAXED, ids=[c[0][:18] for c in LANGLABEL_RELAXED])
def test_a_language_name_inside_a_short_label_is_a_control(label, want):
    """The pattern was anchored at both ends, so `En Español` failed it. The length cap is what
    stops a sentence mentioning Spanish from being read as a switcher, and it is kept."""
    assert bool(LA.LANGLABEL.match(label)) is want
    assert len('Read more in Spanish about our services') > LA.LANGLABEL_MAX


# ---- W5: CJK sentences fail the run threshold by one character
CJK_RUN_CASES = [
    # rule 9: a line with a verb in it is a paragraph. Twenty-one characters, and the old
    # threshold of 22 threw it away
    ('a Japanese question with a verb', '日本と各国はどのような対策を取っているのか？', True),
    # the same eight sites gave the counter-example: the longest run on a correctly english_only
    # CJK site was a navigation row of 13 and an organization name in a header of 10
    ('a Chinese navigation row', '社区服务 志愿者 捐赠 联系我们 关于我们', False),
]


@pytest.mark.parametrize('name,text,want', CJK_RUN_CASES, ids=[c[0] for c in CJK_RUN_CASES])
def test_the_cjk_paragraph_threshold_sits_between_a_sentence_and_a_nav_row(name, text, want):
    assert bool(LA.languages_in(text)) is want
    assert LA.SCRIPT_RUN['Japanese'] == LA.SCRIPT_RUN['Chinese'] == 18


def test_a_middle_dot_does_not_break_a_cjk_phrase():
    """日本語上級者・ネイティブ向け交流会 is one phrase, and the separator class held no middle dot, so it
    split into runs of 6 and 10 and neither could ever reach a paragraph."""
    kanji = r'[぀-ヿ一-鿿]'
    assert LA._longest_run('日本語上級者・ネイティブ向け交流会', kanji) >= 16
    assert '・' in LA.SCRIPT_SEP and '（' in LA.SCRIPT_SEP and '）' in LA.SCRIPT_SEP


# ---- W6: a locale query parameter is recognized but never discovered
def test_a_locale_in_the_query_string_is_a_route():
    """LOCALE_ROUTE has always matched ?lang= and nothing ever collected one: the four collectors
    read a language-name label, an hreflang, a language word in the path and a code-shaped segment.
    Large institutional sites on Salesforce and ServiceNow route their languages this way."""
    html = ('<a href="/portal?language=es_MX">Apply</a>'
            '<a href="/help?foo=1&amp;locale=vi">Get help</a>'
            '<a href="/portal?language=en_US">Apply</a>'
            '<a href="/plain">Plain</a>')
    guessed = set()
    got = LA._routes(html, 'https://x.org/', guessed=guessed)
    assert 'https://x.org/portal?language=es_MX' in got
    assert 'https://x.org/help?foo=1&locale=vi' in got     # &amp; is the same character to a reader
    assert not any('en_US' in u for u in got)              # English is not another language
    assert 'https://x.org/portal?language=es_mx' not in guessed  # the page links it; it is no guess


# ---- W7: rank links instead of truncating in document order
def test_the_best_sixteen_links_are_read_and_not_the_first_sixteen():
    """On one state agency's home page the site's own Language Services page passes PAGE_KW on both
    its path and its label and is cut anyway, purely for sitting far down a document of 1,260
    links. Truncating in document order works on a small site and fails on every large one."""
    html = (''.join('<a href="/about-%d">About %d</a>' % (i, i) for i in range(40))
            + '<a href="/ogm/services/statewide-language-access">Language Services</a>')
    got = LA._interior(html, 'https://x.org/')
    assert got[0] == 'https://x.org/ogm/services/statewide-language-access'
    assert len(got) == LA.INTERIOR_LIMIT
    # document order is the tiebreak, so equal links are read in the order they always were
    plain = ''.join('<a href="/about-%d">About %d</a>' % (i, i) for i in range(20))
    assert LA._interior(plain, 'https://x.org/') == ['https://x.org/about-%d' % i for i in range(16)]


LINK_SCORE_ORDER = [
    ('a language name in the label', '<a href="/p1">Español</a>', 'https://x.org/p1'),
    ('a locale route', '<a href="/p2?lang=vi">Apply</a>', 'https://x.org/p2?lang=vi'),
    ('language-access vocabulary', '<a href="/p3">Interpretation</a>', 'https://x.org/p3'),
    ('a non-ASCII label', '<a href="/p4">Información</a>', 'https://x.org/p4'),
]


@pytest.mark.parametrize('name,link,want', LINK_SCORE_ORDER, ids=[c[0] for c in LINK_SCORE_ORDER])
def test_a_named_link_outranks_an_earlier_generic_one(name, link, want):
    """Every rank above the keyword one has to beat a keyword link that came first in the page."""
    html = ''.join('<a href="/about-%d">About %d</a>' % (i, i) for i in range(20)) + link
    assert LA._interior(html, 'https://x.org/')[0] == want


def _non_english(text, **kw):
    """`languages_in` with English dropped, for the cases that are about a different language.

    English is read by the same machinery as every other Latin-script language since 2026-08-04, so
    a fixture whose English sentence is only scaffolding for the question being asked now names
    English as well. Where a test is about what a Ukrainian name or a Spanish paragraph proves, that
    is noise and this is what reads past it. Where a test is about English itself, or about a page
    naming NOTHING, it asserts on `languages_in` directly and does not come through here.
    """
    return [n for n in LA.languages_in(text, **kw) if n != 'English']


# ---- N1: rule 8, a name is not content
# An invented organization name of the shape the case turns on: a Cyrillic run of 45 characters
# carrying no Cyrillic function word, with the one-letter preposition `у` inside it.
UKR_NAME = 'Український Громадський Освітній Центр у Гринвіллі'


def test_an_organizations_own_name_is_not_evidence_of_a_language():
    """On one site the deciding Cyrillic run is 45 characters and it is the organization's name,
    sitting as a subtitle under an English "About Us". It clears the 40-character threshold, and no
    character count can tell a name from prose, so raising the threshold is not the fix."""
    page = ('About Us ' + UKR_NAME + ' Our mission is to serve the community with classes and '
            'events every week of the year.')
    # The name carries no Cyrillic function word, so the script-word gate declines it on its own.
    # Before that gate this returned ['Ukrainian'], which is the reading the site was published on.
    # Read past English, which the page's own "Our mission is to serve the community" sentence now
    # names and which says nothing about what the Ukrainian NAME proves.
    assert _non_english(page, script_words=False) == ['Ukrainian']
    assert _non_english(page) == []
    assert _non_english(page, exclude=[UKR_NAME]) == []
    # the same name, read off the page's own markup rather than handed in
    html = ('<html><head><title>Home | ' + UKR_NAME + '</title>'
            '<meta property="og:site_name" content="' + UKR_NAME + '"></head>'
            '<body><h1>About Us</h1><img class="logo" alt="' + UKR_NAME + '" src="l.png">'
            '</body></html>')
    assert UKR_NAME in LA._site_names(html)
    assert _non_english(page, exclude=LA._site_names(html)) == []


def test_excluding_the_name_does_not_take_the_writing_with_it():
    """A page that carries the name AND a paragraph is still a page in the language."""
    prose = (UKR_NAME + ' Наш центр пропонує курси української мови для дітей та дорослих '
             'щосуботи вранці, і всі заняття безкоштовні для родин громади.')
    assert LA.languages_in(prose, exclude=[UKR_NAME]) == ['Ukrainian']


def test_a_name_buried_in_a_sentence_is_not_the_whole_sentence():
    """`_is_name` said yes to any run that CONTAINED a name, so when the exact-string strip missed a
    punctuation variant, a whole sentence carrying the organization's name in its own script read as
    just the name and its language was lost. The name has to be most of the run."""
    names = [LA._name_key('Casa de Colibri Azul')]
    assert LA._is_name('Casa de Colibri Azul', names) is True            # the name itself
    assert LA._is_name('Casa de Colibri Azul, Inc.', names) is True      # the name plus a small affix
    sentence = 'Casa de Colibri Azul ofrece servicios de salud y ayuda legal para las familias de aqui'
    assert LA._is_name(sentence, names) is False                      # the name plus a whole sentence


def test_the_sector_caveat_fires_only_on_a_government_true_multilingual():
    """The one stratum caveat the validation set supports, surfaced from the sector a caller stamped,
    and never a reclassification. It reads a Result or the dict `to_dict` returns."""
    gov_tm = LA.Result(url='https://x.gov/', verdict='true_multilingual', sector='government')
    assert LA.sector_caveat(gov_tm)
    assert LA.sector_caveat(gov_tm.to_dict()) == LA.sector_caveat(gov_tm)
    assert LA.sector_caveat(
        LA.Result(url='https://x.gov/', verdict='english_only', sector='government')) == ''
    assert LA.sector_caveat(
        LA.Result(url='https://x.org/', verdict='true_multilingual', sector='nonprofit')) == ''
    assert LA.sector_caveat(
        LA.Result(url='https://x.org/', verdict='true_multilingual')) == '', 'no sector, no caveat'
    # the government label a caller actually writes: variants of "government" and the census frame's
    # own level names (counties, places, state), not just the exact string
    for lab in ('Government', 'local government', 'Federal', 'counties', 'places', 'State', 'city'):
        assert LA.sector_caveat(
            LA.Result(url='https://x.gov/', verdict='true_multilingual', sector=lab)), lab


def test_the_result_repr_is_concise_and_does_not_flood_a_notebook():
    """The auto-generated repr printed every field, `pages` (whole documents) among them. This names
    the four a reader wants and leaves the record itself, `to_dict()`, untouched."""
    r = LA.Result(url='https://x.org/land', requested_url='https://x.org',
                  verdict='true_multilingual', languages=['English', 'Spanish'],
                  evidence=[{}, {}, {}], pages_read=7,
                  pages={'https://x.org/': '<html>' + 'x' * 100000 + '</html>'})
    text = repr(r)
    assert text == ("Result('https://x.org' verdict=true_multilingual "
                    "languages=[English, Spanish] evidence=3 pages_read=7)")
    assert 'html' not in text and len(text) < 200, 'the whole page leaked into the repr'
    assert 'pages' in r.to_dict(with_pages=True), 'the full record is unchanged'


def test_a_zero_width_joiner_inside_an_autonym_still_resolves():
    """'Espa‍nol' renders exactly as 'Espanol' and used to match nothing: not the label
    pattern, not the vocabulary. Format-category characters are stripped from LABELS before the
    comparison; page text keeps them, where SCRIPT_SEP has its own rule."""
    assert LA._langlabel('Espa‍nol') is not None
    assert LA._lookup_language(LA.LANG_TOKEN, 'espa‍nol') == 'Spanish'
    assert LA._lookup_language(LA.LANG_TOKEN, 'espanol') == 'Spanish', 'the plain form still works'


def test_a_three_letter_iso_declaration_is_a_declaration():
    """lang="spa" is a valid, conforming declaration; it resolved to nothing and a correctly
    declared page was reported undeclared. The 639-2/3 table serves `_declares` only, never the
    crawl, because `may` is Malay and `ben` is Bengali and every date archive would become a
    locale link."""
    assert LA._declares(['spa'], 'Spanish')
    assert LA._declares(['vie'], 'Vietnamese')
    assert LA._declares(['kor'], 'Korean')
    assert LA._declares(['zho-Hans'], 'Chinese'), 'a region subtag does not defeat it'
    assert not LA._declares(['spa'], 'Korean')
    assert 'may' not in LA.LANG_CODE and 'ben' not in LA.LANG_CODE, (
        'three-letter codes must stay out of the crawl-facing vocabulary')


def test_the_quote_comes_from_the_window_that_fired():
    """A page can carry one stray Spanish word in its header and its qualifying passage thousands
    of characters later; the quote used to show the header, which carries no tell, and on an
    injected page it showed the site's own words instead of the injection."""
    stray = 'Our services para the county. '                      # one Spanish word, no window
    filler = 'The center offers classes and legal help to families every week. ' * 40
    passage = ('Ofrecemos clases de ingles para las familias de la comunidad y toda la ayuda es '
               'gratuita para cada persona.')
    q = LA._quote(stray + filler + passage, 'Spanish')
    assert 'Ofrecemos' in q or 'familias de la comunidad' in q, q
    assert 'Our services' not in q


# codebook-F1 (_proper_name_token) was applied and then REVERTED 2026-08-10: the adversarial gate
# review measured it dropping every Title-cased function word, which erases a true reading on the
# Title-Case bilingual content US org sites use, and on the frozen capture it moved one verdict in the
# WRONG direction (true_multilingual -> machine_translate). The Vietnamese-name-roster false positive
# it targeted is real but rare, and this cure cost more than the disease; a smarter name filter is a
# measured decision owed to Nari before it ships. Nothing here now, on purpose.


def test_languages_in_is_unchanged_for_a_caller_that_passes_no_names():
    """The default has to be the reading every stored row was taken with."""
    for _n, text, want in LANGUAGE_CASES:
        assert LA.languages_in(text) == LA.languages_in(text, exclude=()) == want


def test_a_two_letter_name_cannot_silence_a_page():
    """A short key sits inside every run on the page, so anything shorter than NAME_KEY_MIN is not
    a name this can test against."""
    es = ('Nuestros servicios para la comunidad son gratuitos. Ofrecemos informacion y recursos '
          'para las familias que necesitan ayuda con este proceso.')
    assert LA.languages_in(es, exclude=['a', 'de', '.']) == ['Spanish']


# ---- N2: a navigation column reads as prose
UKR_NAV = 'Про нас Фестиваль Особливості Стати Спонсором Спонсори Паркінг Програма Контакти'


def test_a_navigation_column_repeated_across_pages_is_not_prose():
    """_longest_run joins whitespace-separated menu labels into one run, and the file's own design
    note assumed Latin text would break them up, which is false for a single-language nav bar. On
    one site the longest run in the whole audit was 226 characters of navigation column."""
    # The script-word gate does NOT catch this one: the label row carries a Cyrillic function word,
    # so it reads as Ukrainian on a single page whichever way that gate is set. Cross-page repetition
    # is what identifies it, which is why both guards exist and neither replaces the other.
    assert LA.languages_in(UKR_NAV) == ['Ukrainian']       # what one page on its own still says
    pages = [UKR_NAV + '\nWelcome to page %d of our festival, with the schedule and directions.' % i
             for i in range(4)]
    boiler = LA._boilerplate(pages)
    assert UKR_NAV in boiler
    assert _non_english(LA._drop_boilerplate(pages[0], boiler)) == []
    assert 'Welcome to page 0' in LA._drop_boilerplate(pages[0], boiler)


def test_boilerplate_needs_three_pages_before_it_can_be_measured():
    """A one-page or two-page audit has nothing to compare, so it is left exactly as it was."""
    pages = [UKR_NAV + '\nPage %d' % i for i in range(4)]
    assert LA._boilerplate(pages[:1]) == set()
    assert LA._boilerplate(pages[:2]) == set()
    assert LA._boilerplate(pages[:3])
    assert LA.BOILERPLATE_MIN_PAGES == 3


def test_a_segment_on_half_the_pages_is_not_boilerplate_yet():
    """More than half, so a paragraph two of four pages happen to share is still the site's own."""
    shared = 'Ofrecemos servicios legales gratuitos para las familias de nuestra comunidad.'
    pages = [shared + '\nOne', shared + '\nTwo', 'Three\nalone', 'Four\nalone']
    assert shared not in LA._boilerplate(pages)
    assert LA._drop_boilerplate(pages[0], LA._boilerplate(pages)).startswith('Ofrecemos')


def test_dropping_no_boilerplate_leaves_the_text_the_audit_always_read():
    raw = 'One line\n  Another  line \n\nThird'
    assert LA._drop_boilerplate(raw, set()) == ' '.join(raw.split())


# ---- N3: a platform's own content is not the organization's
PLATFORM_SITE_CASES = [
    ('the platform own help page', 'https://e-clubhouse.org/faq.php', False),
    ('another page of the same club', 'https://e-clubhouse.org/sites/someclub_ga/contact.php', True),
    ('another club on the platform', 'https://e-clubhouse.org/sites/somewhere_else/', False),
]


@pytest.mark.parametrize('name,url,want', PLATFORM_SITE_CASES,
                         ids=[c[0] for c in PLATFORM_SITE_CASES])
def test_a_club_platforms_own_pages_are_not_the_clubs(name, url, want):
    """Reading more pages walked onto a platform help page carrying a 318-character Chinese run
    that belongs to the international body, not to the local club whose address was audited. The
    platform serves clubs at /sites/<club> and its own pages at the root."""
    assert LA._same_site('https://e-clubhouse.org/sites/someclub_ga/', url) is want


PARENT_HOST_CASES = [
    # a portal the corpus shows carrying several organizations at several subdomains
    ('the state portal a county sits on', 'https://examplecounty.nebraska.gov/',
     'https://www.nebraska.gov/agencies/', False),
    ('the county own interior page', 'https://examplecounty.nebraska.gov/',
     'https://examplecounty.nebraska.gov/departments/', True),
    ('a state agency listing from another county', 'https://othercounty.wv.gov/',
     'https://www.wv.gov/policies', False),
    ('a site builder own pages', 'https://someorg.wordpress.com/',
     'https://wordpress.com/abuse/es', False),
    # an organization's own domain, which is the branch's reason for existing. The three hosts
    # below stand for a foundation, a county and a university whose parents the measurement leaves
    # OUT of SUFFIX_HOST, so each reads its own parent as its own site.
    ('the organization own parent domain', 'https://power.parentorg.example/',
     'https://parentorg.example/en/about', True),
    ('a Spanish mirror reaching its own site', 'https://es.countyseat.example/',
     'https://countyseat.example/', True),
    ('a university a centre belongs to', 'https://centre.university.example/',
     'https://www.university.example/events/', True),
    ('www is not a subdomain', 'https://www.example.org/', 'https://example.org/', True),
    ('a child of the site', 'https://example.org/', 'https://es.example.org/', True),
]


@pytest.mark.parametrize('name,base,url,want', PARENT_HOST_CASES,
                         ids=[c[0] for c in PARENT_HOST_CASES])
def test_a_portal_a_subdomain_hangs_off_is_not_the_site(name, base, url, want):
    """`_same_site` reads the parent of a subdomain as the same site, which is right on an
    organization's own domain and wrong on a host that carries many organizations. One county on a
    state portal was classed true_multilingual on Swedish read off `www.nebraska.gov/agencies/`,
    which is the state portal and not the county. SUFFIX_HOST holds the parents the corpus shows
    carrying three or more organizations at three or more subdomain labels."""
    assert LA._same_site(base, url) is want


# An explicit port in the host tests, found on 2026-08-03 by reading the fix above rather than the
# corpus and closed on 2026-08-04. `_same_site` compared netlocs, which carry the port, and SUFFIX_HOST,
# SHARED_HOST and SOCIAL_HOST all hold bare hosts, so the guard was matched against
# `nebraska.gov:443`, missed the set, and read the state portal as the county's own site again.
#
# Both directions are here, because the fix is a pair of claims and not one. A port the scheme
# already means is dropped, so a guard written for a host reaches every way of writing that host. A
# port the scheme does not mean is KEPT, because two services on two ports of one host are not one
# site and folding them together hands an organization's crawl whatever else the host is running.
PORT_CASES = [
    # the reproduced pair, in the four ways the two addresses can carry the port
    ('the portal with the port on both', 'https://examplecounty.nebraska.gov:443/',
     'https://www.nebraska.gov:443/agencies/', False),
    ('the portal with the port on the link', 'https://examplecounty.nebraska.gov/',
     'https://www.nebraska.gov:443/agencies/', False),
    ('the portal with the port on the base', 'https://examplecounty.nebraska.gov:443/',
     'https://www.nebraska.gov/agencies/', False),
    ('the portal with no port at all', 'https://examplecounty.nebraska.gov/',
     'https://www.nebraska.gov/agencies/', False),
    # a default port is the same address written twice, so the site still reads its own pages
    ('the site itself under an explicit 443', 'https://example.org:443/',
     'https://example.org:443/about', True),
    ('an explicit 443 against a bare address', 'https://example.org:443/',
     'https://example.org/about', True),
    ('an explicit 80 on http', 'http://example.org:80/', 'http://example.org/about', True),
    ('a subdomain reaching its own parent under a port', 'https://blog.example.org:443/',
     'https://example.org:443/about', True),
    ('http and https of one host', 'https://example.org:443/', 'http://example.org:80/about', True),
    # a port the scheme does not mean is a different service and stays on the host
    ('a nonstandard port is not the same site', 'https://example.org:8080/',
     'https://example.org/about', False),
    ('a nonstandard port against itself', 'https://example.org:8080/',
     'https://example.org:8080/about', True),
    ('443 on http is not http default', 'http://example.org:443/', 'http://example.org/about',
     False),
    ('80 on https is not https default', 'https://example.org:80/', 'https://example.org/about',
     False),
    # the shared-host branch, which searches inside the host and so was never blind to the port
    ('one builder site is not another under a port', 'https://sites.google.com:443/view/org/',
     'https://sites.google.com:443/view/other/', False),
    ('a builder site reaching its own pages under a port', 'https://sites.google.com:443/view/org/',
     'https://sites.google.com:443/view/org/about', True),
]


@pytest.mark.parametrize('name,base,url,want', PORT_CASES, ids=[c[0] for c in PORT_CASES])
def test_an_explicit_port_does_not_defeat_the_host_tests(name, base, url, want):
    assert LA._same_site(base, url) is want


def test_a_social_page_is_a_social_page_with_the_port_written_in():
    """SOCIAL_HOST is anchored at both ends and holds bare hosts, so `facebook.com:443` matched
    nothing and rule 1 let a platform page be read as the organization's website."""
    for netloc in ('www.facebook.com', 'www.facebook.com:443', 'instagram.com:443'):
        assert LA.SOCIAL_HOST.match(
            LA._bare_host(LA.urlsplit('https://%s/someorg' % netloc))), netloc
    assert not LA.SOCIAL_HOST.match(
        LA._bare_host(LA.urlsplit('https://www.facebook.com:8443/someorg'))), (
        'a nonstandard port is a different service and the anchored host test should not reach it')


def test_the_default_port_table_holds_only_what_the_scheme_means():
    assert LA.DEFAULT_PORT == {'http': '80', 'https': '443'}


def test_the_suffix_hosts_are_parents_and_not_whole_sites():
    """Every entry is a host a site can hang OFF, so none may swallow a site sitting at it.

    The set is applied to the linked host in the parent branch alone. A site audited at one of
    these addresses itself, which is what a state portal is when the state is the unit, still reads
    its own pages, because that comparison never reaches the branch.
    """
    assert LA._same_site('https://www.nebraska.gov/', 'https://www.nebraska.gov/agencies/') is True
    assert LA._same_site('https://www.nebraska.gov/',
                         'https://examplecounty.nebraska.gov/') is True
    assert all('.' in h and not h.startswith('.') for h in LA.SUFFIX_HOST)


def test_a_guess_cannot_walk_onto_a_club_platforms_root():
    got = LA._routes('<a href="/sites/someclub_ga/about.php">About</a>',
                     'https://e-clubhouse.org/sites/someclub_ga/')
    assert 'https://e-clubhouse.org/es' not in got
    assert 'https://e-clubhouse.org/sites/someclub_ga/es' in got


# ---- N4: a third-party directory profile is not the organization's website
DIRECTORY_CASES = [
    ('a profile on an arts directory',
     'https://www.creativeground.org/profile/riverbend-chinese-language-school', True),
    ('a member school on an association directory',
     'https://www.tcml-mandarin.org/school/riverbend-chinese-school-in-ashford', True),
    ('a funder-platform profile', 'https://app.candid.org/profile/0000000', True),
    # the digits were a real organization's EIN until 2026-08-05; what the rule reads is the
    # `/ein/` path segment the aggregator publishes every one of its rows under
    ('a 990 aggregator', 'https://getholdings.com/nonprofits/ein/000000000', True),
    # both halves are required, because a false exclusion loses a real site
    ('the directory host at its own front door', 'https://www.tcml-mandarin.org/', False),
    ('a profile path on an ordinary domain', 'https://x.org/profile/our-team', False),
    ('an ordinary organization', 'https://example.org/about', False),
]


@pytest.mark.parametrize('name,url,want', DIRECTORY_CASES, ids=[c[0] for c in DIRECTORY_CASES])
def test_a_directory_profile_is_not_the_organizations_website(name, url, want):
    """Rule 5. On one such address fourteen of the crawl's fifteen fetches went to the directory's
    own /about, /news, /team and /terms-use, and the row was scored on what they said."""
    assert LA._directory_profile(url) is want


# ---- N5: county addressing is not a language
#
# `LOCALE_ROUTE` read a two-letter first host label as a language whatever the two letters were.
# `co.<county>.<state>.us` and `ci.<city>.<state>.us` are the standard United States locality host
# forms, `co` is the ISO 639-1 code for Corsican, and `ci` is not a code at all. Measured over the
# 1,368 home pages of the county diagnosis: 213 links promoted into the crawl across 34 of 458
# counties, and every one of the 84 promoted addresses that was fetched holds no non-English text.
LOCALE_ROUTE_CASES = [
    ('a county host', 'https://co.riverbend.ne.us/', False),
    ('a county host with www', 'https://www.co.ashford.nh.us/departments/', False),
    ('a city host', 'https://ci.clearbrook.mn.us/public_works/airport.php', False),
    ('a .us host whose first label is not two letters', 'https://riverbendcountymo.us/', False),
    # a department subdomain outside .us: caught because the two letters are not a language code
    ('a public works subdomain', 'https://pw.examplecounty.example/', False),
    ('an environmental justice subdomain', 'https://ej.examplejustice.example/', False),
    ('a country code that is not a language code', 'https://cn.example.org/', False),
    # the department PATH, which is a code followed by three letters and never a locale
    ('a tax department path', 'https://www.examplecounty.example/tr-tax/', False),
    ('an information technology path', 'https://www.examplecounty-sc.example/it-gis', False),
    # everything a locale route actually looks like
    ('a locale subdomain', 'https://es.example.org/', True),
    ('a script subdomain', 'https://zh-hans.example.org/', True),
    ('a locale path', 'https://example.org/es/servicios', True),
    ('a region path', 'https://example.org/zh-cn/about', True),
    ('a script path', 'https://example.org/zh-hans/about', True),
    ('a locale parameter', 'https://example.org/?lang=es', True),
    ('the Google Translate proxy host', 'https://example-org.translate.goog/x', True),
]


@pytest.mark.parametrize('name,url,want', LOCALE_ROUTE_CASES, ids=[c[0] for c in LOCALE_ROUTE_CASES])
def test_a_two_letter_segment_needs_more_than_its_length(name, url, want):
    assert bool(LA.LOCALE_ROUTE.search(url)) is want


def test_the_host_branch_reads_only_the_two_letter_part_of_the_code_list():
    """`ISO639` itself is untouched: the host branch is its two-letter part and the path branch is
    all of it, so a three-letter code still routes on a path and never on a host."""
    assert set(LA.ISO639_HOST) == {c for c in LA.ISO639 if len(c) == 2}
    assert LA.LOCALE_ROUTE.search('https://example.org/spa/inicio')
    assert not LA.LOCALE_ROUTE.search('https://spa.example.org/')


# ---- W8: a 403 to the browser is not always a 403
def test_the_text_of_a_document_fetched_without_a_browser():
    """The plain-fetch rescue has no renderer, so it has to get text out of the markup itself."""
    html = ('<html><head><style>body{color:red}</style></head><body><nav>Home</nav>'
            '<script>var x = "not text";</script>'
            '<p>日本語のページです</p></body></html>')
    text = LA._text_from_html(html)
    assert 'not text' not in text and 'color:red' not in text
    assert '日本語のページです' in text
    assert 'Home' in text


# ---------------------------------------------------------------- accuracy pass 3, 2026-07-30
# F2: a script run must carry function words, the way Latin already does.
#
# The asymmetry these pin: a Latin-script language needs four distinct function words inside one
# window, which a name cannot satisfy, and a SCRIPTS language needed only a run of N characters, so
# an organization name, a navigation column and a lunar date line each had to be patched one at a
# time. `script_words=True` asks a script run the same question. It is off by default because two
# cases above pin the pre-existing reading of exactly these Ukrainian strings, and every stored row
# was taken with that reading.

SCRIPT_WORD_CASES = [
    # ---- must STOP firing: a name, a menu, a nav column, a date line
    ('a Ukrainian organization name under an English heading',
     'About Us ' + UKR_NAME + ' Our mission is to serve the community with classes and events '
     'every week of the year.', False),
    ('a Ukrainian navigation column with no particles',
     'Головна Фестиваль Особливості Спонсори Паркінг Програма Контакти Галерея Новини', False),
    ('a Korean navigation column', '홈 소개 프로그램 후원 문의 오시는길 자료실 공지사항 갤러리 회원가입 로그인', False),
    ('a Chinese navigation row', '社区服务 志愿者 捐赠 联系我们 关于我们 新闻动态 活动预告', False),
    ('a lunar date line over an English page',
     '7/29/2026 (丙午年[马] 农历二零二六年六月十六 星期三) Create an account Log In Web Mail Home '
     'OACA Chinese School Chinese Cultural Resources Membership Contact Us', False),
    ('a menu of language autonyms',
     'English 한국어 (Korean) ខ្មែរ (Khmer) ภาษาไทย (Thai) Tiếng Việt हिन्दी 中文', False),
    # ---- must STILL fire: the rules' own positive exemplars, one per script
    ('real Ukrainian prose',
     'Наша школа запрошує дітей на заняття з української мови. Ми працюємо щосуботи вранці.', True),
    ('real Russian prose',
     'Наша организация предоставляет бесплатную юридическую помощь семьям иммигрантов.', True),
    ('real Bulgarian prose',
     'Асоциацията на българските училища обединява училища, които преподават български език.', True),
    ('the Khmer sentence in rule 9',
     'នៅតែត្រូវការជំនួយ? ទាក់ទងមកយើងខ្ញុំតាមទំព័រហ្វេសប៊ុក', True),
    ('the Khmer contact sentence',
     'មជ្ឈមណ្ឌលវប្បធម៌កម្ពុជាផ្តល់ថ្នាក់រៀនភាសាខ្មែរ និងកម្មវិធីសម្រាប់យុវជននៅក្នុងសហគមន៍របស់យើង។', True),
    ('the Chinese prose case',
     'ACSC致力于通过评估、导航和协助亚裔老年社区成员的社交需求，为他们提供全面的支持服务。', True),
    ('Chinese prose in traditional characters',
     '本會成立於一九八二年，為華人移民家庭提供中文學校、法律諮詢轉介與社區服務。我們每週六上午開課，歡迎新生報名。', True),
    ('the Japanese school sentence',
     'さくら日本語学校は、日本語を母語とする子どもたちのために国語教育を提供しています。', True),
    ('the Japanese question in rule 9', '日本と各国はどのような対策を取っているのか？', True),
    ('Korean prose',
     '본 기관은 이민자 가정을 위해 무료 법률 상담과 통역 서비스를 제공하고 있습니다. 문의해 주세요.', True),
    ('Arabic prose',
     'نحن نقدم خدمات قانونية مجانية للعائلات المهاجرة في هذه المدينة كل يوم من أيام الأسبوع.', True),
    ('Hebrew prose',
     'הארגון שלנו מספק סיוע משפטי חינם למשפחות מהגרים בכל ימות השבוע וגם עוזר עם תרגום.', True),
    ('Hindi prose',
     'हमारी संस्था प्रवासी परिवारों को निःशुल्क कानूनी सहायता और अनुवाद सेवाएं प्रदान करती है।', True),
    ('Bengali prose',
     'আমাদের সংস্থা অভিবাসী পরিবারের জন্য বিনামূল্যে আইনি সহায়তা এবং অনুবাদ সেবা প্রদান করে থাকে।', True),
    ('Thai prose',
     'องค์กรของเราให้บริการช่วยเหลือทางกฎหมายฟรีแก่ครอบครัวผู้อพยพในเมืองนี้ทุกวัน', True),
    ('Amharic prose',
     'ድርጅታችን ለስደተኛ ቤተሰቦች ነፃ የሕግ ድጋፍ ይሰጣል እና በየሳምንቱ የቋንቋ ትምህርት ውስጥ ይሰጣል።', True),
    # Burmese, added 2026-08-01. A sentence from a global broadcaster's Burmese service, and
    # against it the two things in a real page that are a run of the Myanmar block and are not
    # anybody writing: the country name inside a telephone dialling-code list, which is what put
    # Myanmar characters on one church's site, and a row of Burmese navigation labels.
    ('Burmese prose',
     'ဒါဟာ တော်လှန်ရေးရဲ့ အရေးကြီးတဲ့ ခြေလှမ်းတရပ်၊ အရေးကြီးတဲ့အဆင့်တခုကို ကျော်ဖြတ်နိုင်တယ်လို့ပဲ ပြောချင်ပါတယ်။', True),
    ('a Burmese country name in a dialling-code list',
     'Mongolia + 976 Montenegro + 382 Myanmar (Burma) (မြန်မာ) + 95 Namibia + 264 Nepal + 977', False),
    ('a Burmese navigation row',
     'ပင်မစာမျက်နှာ အကြောင်း ဝန်ဆောင်မှုများ ဆက်သွယ်ရန် သတင်း ဓာတ်ပုံ လှူဒါန်းရန်', False),
    # The case this pinned down. Every one of these labels is an ordinary Burmese noun phrase, and
    # a case-marker word list matched three of them: များ inside ဝန်ဆောင်မှုများ, ရန် inside
    # ဆက်သွယ်ရန်, ကို inside ကိုရီးယား. A language MENU firing as prose is the misreading the
    # script-word test exists to stop, so it is here by name.
    ('a Burmese language menu',
     'ဘာသာစကား ရွေးချယ်ပါ မြန်မာ အင်္ဂလိပ် စပိန် တရုတ် ကိုရီးယား ဗီယက်နမ်', False),
]


@pytest.mark.parametrize('name,text,want', SCRIPT_WORD_CASES, ids=[c[0] for c in SCRIPT_WORD_CASES])
def test_a_script_run_has_to_carry_function_words_too(name, text, want):
    # Read past English: some of these fixtures carry an English sentence around the script run,
    # and the question here is what the RUN proves.
    assert bool(_non_english(text, script_words=True)) is want


def test_the_script_word_test_is_what_separates_the_name_from_the_prose():
    """The same page, the same threshold, the same 45-character run. What tells the organization's
    name from a sentence is that a sentence carries particles and a name does not."""
    page = 'About Us ' + UKR_NAME + ' Our mission is to serve the community every week.'
    prose = (UKR_NAME + ' Наш центр пропонує курси української мови для дітей та дорослих '
             'щосуботи вранці, і всі заняття безкоштовні для родин громади.')
    assert _non_english(page, script_words=False) == ['Ukrainian']   # the reading without it
    assert _non_english(page) == []                                  # the default carries it now
    assert _non_english(prose) == ['Ukrainian']                      # the name did not take it


# ------------------------------------------------------------------------------------------------
# THE FOUR LANGUAGES ADDED 2026-08-01
#
# Hmong, Pashto, Burmese and Kurdish were the four commonest labels a switcher offered that this
# package could not name. All four went into the switcher vocabulary, which is a reporting change.
# Three of them also got detectors and one did not, and what these tests hold is which is which,
# because the difference is invisible from the outside: `switcher_languages` says the same thing
# for all four and only `languages` tells them apart.
# ------------------------------------------------------------------------------------------------

# A state health department's COVID-19 service information in Hmong, which is the register this
# census reads: a US public agency writing service information for Hmong speakers.
HMONG_PROSE = ('COVID-19 yog ib hom kab mob tshwm sim los ntawm cov kab khauslauvnam vaislav uas '
               'sib kis tau yooj yim heev ntawm ib tug neeg mus rau ib tug neeg. Tus kab mob '
               'COVID-19 mob rau tib neeg lub qhov ntswg thiab lub qa thiab qee zaus kuj mob rau '
               'ob lub ntsws thiab, ua rau ua pa nyuaj heev.')

# A global broadcaster's Pashto service.
PASHTO_PROSE = ('وايي د ټولو هغو محدودیتونو سربېره چې ورسره مخامخ وه، د دغو عملیاتو په ترسره کولو '
                'ښه احساس لري. هغې ویلي، زه ډېره خوشحاله یم او داسې احساسوم لکه بېرته چې ځوانه '
                'شوې یم. کله کله انسان غواړي د خپل روحي وضعیت د ښه کېدو لپاره داسې څه وکړي.')

# A Kurdish news site's Sorani edition (Central Kurdish, Arabic script) and its Kurmanji edition
# (Northern Kurdish, Latin script). Neither is detected, and the tests below say so rather than
# skip it.
SORANI_PROSE = ('رووداو زانیویەتی، رۆژی شەممە ئەو باڵۆنەی لە ئاسمانی هەولێر دەبینرا، هێنراوەتە '
                'خوارەوە. ئەم باڵۆنانە دەتوانن ئامێرە ئەلیکترۆنییەکان بۆ بەرزیی چەند هەزار پێیەک '
                'لەسەر بنکە سەربازییەکان و کاروانەکان بەرز بکەنەوە.')
KURMANJI_PROSE = ('Şeva 3yê Tebaxa 2014an, telefona min zengil lê da û qet ranewestiya. Hevalên '
                  'min digiriyan û di telefonê de diqîriyan: Li vê derê tiştekî ku nayê vegotin '
                  'diqewime, em hemû dê bêne kuştin an jî bêne revandin.')


def test_burmese_is_reached_the_way_the_other_eleven_scripts_are():
    """The Myanmar block is its own proof, so the change was mechanical: one range in SCRIPTS, one
    particle list in SCRIPT_FUNC, and the default run threshold every non-CJK script uses."""
    assert ('Burmese', r'[က-႟]') in LA.SCRIPTS
    assert 'Burmese' in LA.SCRIPT_FUNC
    assert 'Burmese' not in LA.SCRIPT_RUN          # 40, like Khmer, Thai, Arabic and Cyrillic
    assert 'Burmese' not in LA.SCRIPT_FUNC_SPACED  # no spaces between words, so matched inside them
    assert 'Burmese' in LA.COVERED and 'Burmese' in LA.SCRIPT_LANGUAGES


def test_a_burmese_page_is_read_even_though_a_burmese_sentence_alone_may_not_be():
    """SCRIPT_FUNC_MIN is one particle within SCRIPT_FUNC_WINDOW of the run, so what has to carry a
    sentence-final marker is the NEIGHBOURHOOD, not every sentence. 42 of 61 sentences of the
    broadcaster's Burmese article fire read one at a time; the article read as a page fires on all
    of it."""
    para = ('သတင်းဌာန - ဖက်ဒရယ် အသွင်ကူးပြောင်းရေး ဆိုင်ရာအစီအမံ AFTA နဲ့ ပတ်သက်ပြီး Zero Draft '
            'မူကြမ်းထွက်လာပြီလို့ သိရတယ်။ ဒီ Draft က လက်ရှိတော်လှန်ရေးအပေါ်မှာ ဘယ်လိုအပြောင်း '
            'အလဲတွေ ဖြစ်လာစေမလဲ။ ဒါဟာ တော်လှန်ရေးရဲ့ အရေးကြီးတဲ့ ခြေလှမ်းတရပ်ဖြစ်ပါတယ်။')
    assert LA.languages_in(para, aux=False) == ['Burmese']


def test_hmong_is_read_off_its_function_words():
    """Latin script shared with everything else on the list, so the words are the only route."""
    assert 'Hmong' in LA.languages_in(HMONG_PROSE, aux=False)


def test_the_hmong_words_fire_on_no_other_language():
    """The check that matters. A false language reading moves a site to `true_multilingual`, so the
    list was built by requiring every word to be ABSENT from eighteen samples of the languages
    Hmong could be confused with, and this is that check in miniature."""
    for other in (PASHTO_PROSE, SORANI_PROSE, KURMANJI_PROSE,
                  'Nuestros servicios para la comunidad son gratuitos y cada familia puede pedir '
                  'ayuda con este proceso, porque todos tienen derecho a la informacion.',
                  'Our organization helps immigrant families with legal questions every week of '
                  'the year, and all of our services are free to anyone who needs them.',
                  'Kami menyediakan layanan bantuan hukum gratis untuk keluarga imigran di kota '
                  'ini, dan semua orang dapat meminta bantuan kami kapan saja.',
                  'Ang aming samahan ay nagbibigay ng libreng tulong legal para sa mga pamilyang '
                  'imigrante sa aming komunidad tuwing linggo ng taon.'):
        assert 'Hmong' not in LA.languages_in(other, aux=False), other[:40]


OROMO_PROSE = ('Dhaabbanni keenya torbee hunda maatii godaansaaf gorsa seeraa kaffaltii malee kenna. '
               'Gorsi kun bilisa yoo taʼe illee nuti haala godaansa keessan hin gaafannu, akkasumas '
               'waajjirri keenya guyyaa shan banaa dha.')
OROMO_NOTICE = ('Beeksisa: yoo gargaarsa barbaaddan, waaree dura bilbilaa. Abukaatoo waliin '
                'dubbachuuf hanga sa\'aatii kudha lamaatti eegaa, gorsi kun kaffaltii hin qabu.')


def test_oromo_is_read_off_its_function_words():
    """Latin script shared with every other language on the list and no identifier route either:
    lid.176 answers Finnish at 0.24 and 0.16 on the coverage paragraphs, under FT_MIN_CONF, so the
    words are the only way to this language."""
    assert LA.languages_in(OROMO_PROSE, aux=False) == ['Oromo']
    assert LA.languages_in(OROMO_NOTICE, aux=False) == ['Oromo']


def test_the_oromo_words_fire_on_no_other_language():
    """The check that matters for a new Latin-script list, because a false reading moves a site to
    true_multilingual. Held against the languages Oromo could be confused with by script, including
    the two that share a single word with it, `yoo` in Yoruba and `kun` in Uzbek: one word cannot
    reach the four distinct words a paragraph needs."""
    for other in (HMONG_PROSE,
                  'Ilé ìṣọ̀kan wa ń fúnni ní ìmọ̀ràn nípa òfin lọ́fẹ̀ẹ́ lórí àwọn ọ̀rọ̀ ìṣíkiri, '
                  'a sì ń kọ́ àwọn àgbàlagbà ní èdè Gẹ̀ẹ́sì ní alẹ́ ẹ̀ẹ̀mẹta ní ọ̀sẹ̀.',
                  'Markazimiz har hafta muhojir oilalarga bepul huquqiy maslahat beradi va biz '
                  'sizning immigratsiya holatingiz haqida soramaymiz.',
                  'Xarunta bulshada waxay talo sharci bilaash ah siisaa qoysaska socdaalka, '
                  'toddobaadkiina saddex habeen fasallo Ingiriisi ah ayaa la qabtaa.',
                  'Kituo chetu kinatoa ushauri wa kisheria bila malipo kwa familia za wahamiaji '
                  'kila wiki, na hatuulizi kuhusu hali yako ya uhamiaji.',
                  'Our organization helps immigrant families with legal questions every week of '
                  'the year, and all of our services are free to anyone who needs them.'):
        assert 'Oromo' not in LA.languages_in(other, aux=False), other[:40]


def test_a_lithuanian_help_notice_is_a_paragraph():
    """A help notice is the passage that most directly IS the provision this instrument measures,
    and it is the shape a thin word list loses. This notice carried two words of the list against a
    bar of four and read as nothing; the Bosnian entry was widened in August for the same shape.

    The neighbour is the thing to watch here, because Latvian and Lithuanian share vocabulary the
    way Spanish and Portuguese do. `jums` is ordinary Latvian, it is not in the Latvian list so it
    thins nothing, and what it does is give a Latvian page ONE Lithuanian word, which is three short
    of a reading.
    """
    notice = ('Pranešimas: jei jums reikia pagalbos lietuvių kalba, ateikite į registratūrą nuo '
              'pirmadienio iki penktadienio. Konsultacija nemokama ir mes neklausiame apie jūsų '
              'statusą. Norėdami pasikalbėti su advokatu, skambinkite iki vidudienio.')
    assert LA.languages_in(notice, aux=False) == ['Lithuanian']
    latvian = ('Paziņojums: ja jums vajadzīga palīdzība latviešu valodā, nāciet uz reģistratūru no '
               'pirmdienas līdz piektdienai. Konsultācija ir bezmaksas, un mēs neprasām par jūsu '
               'uzturēšanās statusu.')
    assert LA.languages_in(latvian, aux=False) == ['Latvian']
    # `kada` was the fifteenth candidate and is out, because the other list writes it too
    assert 'kada' not in LA._fold(LA.FUNC['Lithuanian']).split()
    assert 'kada' in LA._fold(LA.FUNC['Bosnian/Croatian/Serbian']).split()


# The two shapes the Spanish list was widened for on 2026-09-18, invented. Neither carries four
# words of the 48-word list the widening replaced, and both carry ten or eleven of the 122-word one.
SPANISH_EVENT = ('Aviso: ahora atendemos a quien llegó hace poco al condado, y siempre hay alguien '
                 'en la recepción. Aunque el trámite demora, cualquier familia consigue cita '
                 'después de las doce y nadie tiene que pagar.')
SPANISH_NOTICE = ('Ahora mismo hay alguien en la recepción que habla español. Si usted llegó hace '
                  'poco, cualquier consulta es sin costo, aunque siempre conviene pedir cita '
                  'después de las once.')


def test_a_spanish_paragraph_is_read_off_the_widened_list():
    """Spanish is the language this instrument meets most often and its list was the thinnest thing
    in front of it: 48 words, where a page of ordinary Spanish prose about an event or an opening
    hour can carry two or three of them and stop one short of FUNC_DISTINCT_MIN. Both passages here
    carry two words of the old list and ten or eleven of this one."""
    assert LA.languages_in(SPANISH_EVENT, aux=False) == ['Spanish']
    assert LA.languages_in(SPANISH_NOTICE, aux=False) == ['Spanish']


def test_the_widened_spanish_list_does_not_reach_its_latin_neighbours():
    """The check that matters for this pair, because Spanish and Portuguese share most of their
    everyday function vocabulary and a Spanish-only word inside Portuguese prose is a licence. The
    Portuguese passage carries three Spanish words and no Spanish licence, and each neighbour is
    still read as itself."""
    portuguese = ('Aviso: agora atendemos quem chegou há pouco ao condado, e há sempre alguém na '
                  'recepção. Embora o processo demore, qualquer família consegue marcação depois '
                  'do meio-dia. Todas as famílias podem pedir uma intérprete para as consultas, e '
                  'nós não perguntamos nada sobre a sua situação.')
    italian = ('Avviso: ora seguiamo chi è arrivato da poco nella contea, e c\'è sempre qualcuno '
               'alla reception. Anche se la pratica richiede tempo, qualsiasi famiglia ottiene un '
               'appuntamento dopo mezzogiorno. Tutte le famiglie possono chiedere un interprete e '
               'non chiediamo nulla sulla vostra situazione.')
    french = ('Avis: nous accueillons maintenant les personnes arrivées récemment dans le comté, '
              'et il y a toujours quelqu\'un à l\'accueil. Bien que la démarche prenne du temps, '
              'chaque famille obtient un rendez-vous après midi.')
    catalan = ('Avís: ara atenem qui ha arribat fa poc al comtat, i sempre hi ha algú a la '
               'recepció. Encara que el tràmit trigui, qualsevol família aconsegueix cita després '
               'del migdia.')
    assert LA.languages_in(portuguese, aux=False) == ['Portuguese']
    assert LA.languages_in(italian, aux=False) == ['Italian']
    assert LA.languages_in(french, aux=False) == ['French']
    assert 'Spanish' not in LA.languages_in(catalan, aux=False)


def test_an_english_page_of_spanish_names_is_not_spanish():
    """Rule 8 says a name is not content, and the widening's largest refusal is here: `los` and
    `las` are the definite plural articles and they match inside two of the commonest place names
    in the United States. They are not in the list, and this row is what would have carried them."""
    row = ('Our offices in Los Angeles and Las Cruces run the Mujeres Unidas and Casa de la '
           'Familia programs, and the Los Amigos food pantry opens on Saturday mornings at the '
           'community center.')
    assert LA.languages_in(row, aux=False) == []
    for w in ('los', 'las'):
        assert w not in LA._fold(LA.FUNC['Spanish']).split()


def test_the_words_the_spanish_screen_refused_are_not_in_the_list():
    """Each of these is an ordinary Spanish word and each is refused for a reason the corpus can
    name, so the ledger is a test rather than a paragraph nobody reads. Portuguese writes `podemos`
    and the two enclitic pronouns; Catalan writes `aquella`, `algun`, `alguna`, `seran` and `eres`;
    Dutch, German and Haitian Creole write `gratis`; `sin`, `hay` and `son` are English words."""
    spanish = set(LA._fold(LA.FUNC['Spanish']).split())
    for w in ('podemos', 'los', 'las', 'aquella', 'algun', 'alguna', 'seran', 'eres',
              'gratis', 'sin', 'hay', 'son', 'ese', 'esa', 'durante', 'mediante', 'todavia',
              'gratuito', 'oficina', 'recursos', 'familias', 'aqui', 'mas', 'solo', 'sido', 'ser'):
        assert w not in spanish, w
    # and the bar the Hmong entry set, which this widening did not lower
    assert all(len(w) >= 3 for w in spanish)


def test_the_spanish_widening_thins_no_other_languages_licence():
    """The same property the Oromo test states, asked of a list that grew rather than appeared. No
    word added on 2026-09-18 is in another language's list, so `_SHARED` is the set it was and no
    other language reads differently because Spanish got wider. The words Spanish already shared
    stay shared, which is what keeps `dos` doing the job the note above the list describes."""
    spanish = set(LA._fold(LA.FUNC['Spanish']).split())
    added = spanish - {
        'ademas', 'ayuda', 'cada', 'como', 'comunidad', 'cuando', 'del', 'desde', 'donde', 'dos',
        'entre', 'esta', 'estan', 'estas', 'este', 'estos', 'hacer', 'hasta', 'informacion', 'muy',
        'nosotros', 'nuestra', 'nuestras', 'nuestro', 'nuestros', 'otra', 'otro', 'para', 'pero',
        'por', 'porque', 'puede', 'pueden', 'que', 'servicios', 'sobre', 'sus', 'tambien', 'tiene',
        'tienen', 'toda', 'todas', 'todo', 'todos', 'una', 'unas', 'unos', 'usted'}
    assert len(added) == 74
    others = set()
    for name, words in LA.FUNC.items():
        if name not in ('Spanish', 'English'):
            others |= set(LA._fold(words).split())
    assert added & others == set(), sorted(added & others)
    assert added & LA._SHARED == set()
    # `dos` is the word that must stay shared, because it is what stops a Portuguese reading of
    # Spanish prose; see the note on the Spanish entry and ORTHO_ONLY
    assert 'dos' in LA._SHARED


def test_ilocano_and_cebuano_are_named_and_still_carry_tagalog():
    """What these two codes fix is a WRONG name and not a missing one. The identifier answers `ilo`
    and `ceb` correctly and the answer was discarded for want of an entry, so both languages came
    back reported as Tagalog, which is the only Philippine name the reader had. The second half is
    the honest one: the Tagalog stays, because the word list is what puts it there and no entry in
    that table can take it off, so a Cebuano page reports two names of which one is right."""
    assert LA.AUX_ISO['ilo'] == 'Ilocano' and LA.AUX_ISO['ceb'] == 'Cebuano'
    assert 'Ilocano' not in LA.COVERED and 'Cebuano' not in LA.COVERED
    # the three share their grammatical vocabulary, which is why the wrong name is there at all
    shared = set(LA._fold(LA.FUNC['Tagalog']).split())
    assert {'ang', 'mga'} <= shared
    # a Latin-script auxiliary language never qualifies on one block, so a help notice is unmoved
    assert LA.AUX_MIN_BLOCKS == 2
    assert LA.AUX_SCRIPT.get('Cebuano') is None and LA.AUX_SCRIPT.get('Ilocano') is None
    assert LA._aux_solo('Cebuano', 'a' * (LA.AUX_SOLO_RUN + 40)) is False


def test_the_turkish_list_carries_the_dotless_i():
    """Four entries of this list were written with a dotted i where Turkish writes the dotless one,
    so they could never match a page that spells the language properly. U+0131 is the third letter
    in these lists that NFKD leaves alone, after the Vietnamese `đ` and the Polish `ł`."""
    turkish = set(LA._fold(LA.FUNC['Turkish']).split())
    for dotted, dotless in (('arasinda', 'arasında'), ('ayrica', 'ayrıca'),
                            ('onlarin', 'onların'), ('yardim', 'yardım')):
        assert dotted in turkish and dotless in turkish, (dotted, dotless)
        assert LA._fold(dotless) == dotless
    notice = ('Duyuru: Türkçe yardıma ihtiyacınız varsa pazartesiden cumaya kadar resepsiyona '
              'gelin. Danışma ücretsizdir, ayrıca göçmenlik durumunuzu sormuyoruz ve bir avukatla '
              'birlikte görüşmek için şimdi telefon edin.')
    assert 'Turkish' in LA.languages_in(notice, aux=False)


def test_daca_is_not_a_romanian_word_on_this_frame():
    """The most useful refusal in the file. `dacă` is the Romanian word for `if` and it passes the
    frequency screen at 2,664; over the stored capture it matches on 19 pages and every one of them
    is the acronym DACA. On a frame of immigrant-serving organizations that string is everywhere,
    and a frequency list of Romanian prose cannot know it."""
    row = ('What is DACA? Deferred Action for Childhood Arrivals is a policy that lets people who '
           'came here as children apply. We also handle DACA Renewal and Green Card Renewal.')
    assert LA.languages_in(row, aux=False) == ['English']
    assert 'daca' not in LA._fold(LA.FUNC['Romanian']).split()


def test_both_spellings_of_a_german_umlaut_are_carried():
    """Neither spelling covers the other. `fuer` is what a page writes when it cannot set the
    diacritic and `fur` is what the fold produces from `für`, so a list holding one of them misses
    every page that writes the other. The second half is `die` and `der`, which are ordinary English
    words and an English surname particle: they are in the list and they cannot carry a reading,
    because four distinct words inside one window is the bar."""
    german = set(LA._fold(LA.FUNC['German']).split())
    for pair in (('fur', 'fuer'), ('uber', 'ueber'), ('konnen', 'koennen')):
        assert set(pair) <= german, pair
    assert LA._fold('für') == 'fur' and LA._fold('können') == 'konnen'
    english = ('The Fischer Foundation and the der Waal family fund our work, and nobody has to '
               'die waiting for an appointment at the office on Main Street.')
    assert LA.languages_in(english, aux=False) == ['English']


def test_an_italian_help_notice_is_a_paragraph():
    """Sixty-nine demonstratives, quantifiers and adverbs moved this notice from two distinct words
    to two. What a real Italian notice is built from is the second person and the articulated
    preposition, and `avete` and `servizio` are what take it over the bar. The commonest of those
    prepositions are refused by the screen, which is why `alla` is not here and `agli` is."""
    notice = ('Avviso: se avete bisogno di aiuto in italiano, rivolgetevi alla reception dal lunedì '
              'al venerdì. Il servizio è gratuito e non chiediamo la vostra situazione migratoria.')
    assert 'Italian' in LA.languages_in(notice, aux=False)
    italian = set(LA._fold(LA.FUNC['Italian']).split())
    assert 'avete' in italian and 'servizio' in italian
    # refused by the screen against Spanish, and refused twice over by being in the German list
    assert 'alla' not in italian and 'alle' not in italian
    assert 'alle' in LA._fold(LA.FUNC['German']).split()


def test_a_polish_help_notice_is_a_paragraph():
    """The one widening of this pass that moves the coverage table: this notice carried three words
    of the 37-word list against a bar of four and read as nothing. `ł` is the second letter in these
    lists that NFKD leaves alone, after the Vietnamese `đ`, so `był` folds to `był` and an entry
    written `byl` would match nothing."""
    notice = ('Uwaga: jeśli potrzebujesz pomocy po polsku, przyjdź do biura w godzinach pracy. '
              'Porada jest bezpłatna i nigdy nie pytamy o status pobytu. Możesz też zadzwonić '
              'wcześniej, jeżeli chcesz umówić tłumacza.')
    assert 'Polish' in LA.languages_in(notice, aux=False)
    assert LA._fold('był') == 'był' and 'był' in LA._fold(LA.FUNC['Polish']).split()
    assert 'byl' not in LA._fold(LA.FUNC['Polish']).split()


def test_a_vietnamese_help_notice_is_a_paragraph():
    """Vietnamese gives a short list because its grammatical vocabulary is short and most of it is
    two letters. The second assertion is the thing to know before editing that entry: `đ` is U+0111,
    NFKD leaves it alone, so `được` folds to `đuoc` and an entry written `duoc` would never match a
    page that spells the word properly."""
    notice = ('Thông báo: nếu quý vị cần được giúp đỡ bằng tiếng Việt, xin đến văn phòng của chúng '
              'tôi trong giờ làm việc. Dịch vụ thông dịch miễn phí và quý vị không phải trả tiền.')
    assert 'Vietnamese' in LA.languages_in(notice, aux=False)
    assert LA._fold('được') == 'đuoc' and LA._fold('đến') == 'đen'
    assert 'đuoc' in LA._fold(LA.FUNC['Vietnamese']).split()
    # the two the screen refuses to another list here, and the English word
    for w in ('nao', 'lai', 'them'):
        assert w not in LA._fold(LA.FUNC['Vietnamese']).split(), w
    assert 'nao' in LA._fold(LA.FUNC['Portuguese']).split()
    assert 'lai' in LA._fold(LA.FUNC['Latvian']).split()


def test_a_french_help_notice_is_a_paragraph():
    """French was already read from a long paragraph and this is about the notice, which is the
    shape a thin list loses. The second half is the removal. `les`, `par` and the English word
    `services` were French-only inside these inventories, because the Spanish list writes `los`,
    `por` and `servicios`, so each of them licensed a French reading by itself and a Spanish page
    could read French off three Spanish words and one English one. They are gone, and the Spanish
    passage here is what they fired on. `nos` stays and is the mechanism in one line: the Portuguese
    list writes it too, so `_SHARED` takes its licence away and it counts toward the four without
    ever licensing anything."""
    notice = ('Avis: nous accueillons maintenant toute personne arrivée récemment, et il y a '
              'toujours quelqu\'un à l\'accueil. Chacun peut demander un interprète, et aucune '
              'démarche n\'est payante.')
    assert LA.languages_in(notice, aux=False) == ['French']
    french = set(LA._fold(LA.FUNC['French']).split())
    for w in ('les', 'par', 'services'):
        assert w not in french, w
    assert 'nos' in french and 'nos' not in (french - LA._SHARED)
    assert 'nos' in LA._fold(LA.FUNC['Portuguese']).split()
    # the shape those three fired on: ordinary Spanish, with the English word `services` beside it
    spanish_page = ('Se les haga justicia a los que no pueden hablar por sí mismos. Nuestros '
                    'servicios y nuestro equipo están aquí para todos. Our services are free.')
    assert 'French' not in LA.languages_in(spanish_page, aux=False)
    # and the two the Vietnamese list refuses outright
    assert 'moi' not in french and 'toi' not in french
    assert {'moi', 'toi'} <= set(LA._fold(LA.FUNC['Vietnamese']).split())


def test_a_portuguese_enrolment_notice_is_a_paragraph():
    """The other half of the pair the ORTHO_ONLY note is about. Portuguese lost most of its everyday
    function words to `_SHARED` for the same reason Spanish did, so a short notice carried three of
    the 46-word list against a bar of four. The neighbour is what to watch: the Spanish passage here
    carries Portuguese words it shares and no Portuguese licence, and still reads Spanish alone."""
    notice = ('Aviso: agora atendemos quem chegou há pouco ao condado, e há sempre alguém na '
              'recepção. Qualquer família pode pedir uma intérprete, e ainda temos vagas nas aulas '
              'de inglês.')
    assert LA.languages_in(notice, aux=False) == ['Portuguese']
    assert LA.languages_in(SPANISH_EVENT, aux=False) == ['Spanish']
    # refused on its output rather than on the screen: see the note on the entry
    assert 'foram' not in LA._fold(LA.FUNC['Portuguese']).split()
    # and refused by the screen, because another list here already writes it
    assert 'vai' not in LA._fold(LA.FUNC['Portuguese']).split()
    assert 'vai' in LA._fold(LA.FUNC['Latvian']).split()


def test_the_oromo_list_thins_no_other_languages_licence():
    """`_SHARED` is counted over the non-English lists, so a word entering it takes that word out of
    some language's unique-word licence. Oromo shares nothing with any of the twenty, which is what
    lets it be added without any other language reading differently, and it is a property of the
    list rather than of the code."""
    om = set(LA._fold(LA.FUNC['Oromo']).split())
    others = set()
    for name, words in LA.FUNC.items():
        if name not in ('Oromo', 'English'):
            others |= set(LA._fold(words).split())
    assert om & others == set(), sorted(om & others)
    assert om & LA._SHARED == set()
    # so its whole list is its licence and the unique-word test can never be what refuses it
    assert set(LA._fold(LA.FUNC['Oromo']).split()) - LA._SHARED == om
    # two letters cannot separate a language from an abbreviation, so the commonest word is out
    assert 'fi' not in om and all(len(w) >= 3 for w in om)


def test_a_hmong_language_label_row_is_not_hmong():
    """`Kev Pab Rau Fab Kev Cai Lij Choj` is how one site writes `legal help` in a row of eight
    languages, and it is three of the list's words in a label. The four-distinct-words test is what
    rejects it, which is the same standard every other Latin-script language is held to."""
    row = ('Ayuda Legal Assistência Jurídica Èd Legal Юридическая Помощь Kev Pab Rau Fab Kev Cai '
           'Lij Choj Giúp Đỡ Pháp Lý المساعدة القانونية')
    assert 'Hmong' not in LA.languages_in(row, aux=False)


def test_pashto_needs_both_the_classifier_and_its_own_letters():
    """Pashto is Arabic script, which already carries Arabic, Persian and Urdu, so the range cannot
    name it. What names it is langid's `ps` model AND the letters Pashto adds to the Persian
    alphabet, and `_script_allows` is the conjunction."""
    assert LA._script_allows('Pashto', PASHTO_PROSE) is True
    # the four blocks in the stored captures where langid answered `ps` and was wrong were all
    # Arabic-script text with no Pashto letter in it, and this is what rejected them
    assert LA._script_allows('Pashto', 'نحن نقدم خدمات قانونية مجانية للعائلات المهاجرة') is False
    assert LA._script_allows('Pashto', SORANI_PROSE) is False
    assert LA._script_allows('Pashto', 'We serve immigrant families every day') is False


def test_the_pashto_letters_are_absent_from_its_neighbours():
    """The gate is only worth anything if the letters really do separate the four languages."""
    rx = LA.AUX_SCRIPT_RX['Pashto']
    assert rx.search(PASHTO_PROSE)
    for other in (SORANI_PROSE,
                  'نحن نقدم خدمات قانونية مجانية للعائلات المهاجرة في هذه المدينة كل يوم',   # Arabic
                  'ما خدمات حقوقی رایگان به خانواده‌های مهاجر در این شهر ارائه می‌دهیم',       # Persian
                  'ہم اس شہر میں تارکین وطن خاندانوں کو مفت قانونی خدمات فراہم کرتے ہیں'):    # Urdu
        assert not rx.search(other), other[:30]


def test_sorani_is_read_and_kurmanji_is_not_and_the_package_says_which():
    """One variety detected, one not, and the asymmetry stated rather than left to be inferred.

    Until 2026-08-02 a Sorani page was reported Persian and Urdu, because langid has no Sorani model
    and those are what it answers when it is shown Sorani. `_aux_name` overrules it on the letters
    Sorani writes and Persian and Urdu do not. Kurmanji is Latin script with nothing to gate it, and
    the one time `ku` fired in 133,183 blocks of the stored captures it was an English page about a
    Bengali festival, so it is still unread and `Kurdish` is still what a switcher offering either
    variety resolves to."""
    assert 'Kurdish' not in LA.SWITCHER_ONLY
    assert LA._aux_name('fa', SORANI_PROSE) == 'Kurdish'
    assert LA._aux_name('ur', SORANI_PROSE) == 'Kurdish'
    # Kurmanji in Latin script reaches none of it: there is no letter gate that can see it
    assert 'Kurdish' not in LA.languages_in(KURMANJI_PROSE)
    # and the switcher still reports what the menu offered, which is layer one
    assert LA._lookup_language(LA.LANG_TOKEN, 'Kurdish (Sorani)') == 'Kurdish'


def test_the_rename_takes_only_the_two_answers_it_was_measured_on():
    """A Persian page stays Persian, an Urdu page stays Urdu, and an answer outside the pair is left
    alone even when the block carries a Kurdish letter.

    `ug` is in the corpus: one Uyghur diaspora organization
    publishes in Uyghur, which shares ۆ with Sorani and is why ۆ is not in the gate. Uyghur is not
    an answer this rename may consume, so even a block that did carry ڕ would keep it."""
    persian = 'ما خدمات حقوقی رایگان به خانواده‌های مهاجر در این شهر ارائه می‌دهیم'
    urdu = 'ہم اس شہر میں تارکین وطن خاندانوں کو مفت قانونی خدمات فراہم کرتے ہیں'
    assert LA._aux_name('fa', persian) == 'Persian'
    assert LA._aux_name('ur', urdu) == 'Urdu'
    assert LA._aux_name('ug', SORANI_PROSE) is None            # not an answer the package names
    assert LA._aux_name('ps', PASHTO_PROSE) == 'Pashto'        # the other Arabic-script gate is intact
    assert LA.SORANI_HOSTS == ('Persian', 'Urdu')


def test_the_sorani_letters_are_absent_from_their_neighbours():
    """The gate is only worth anything if the letters really do separate the languages, and the one
    that does NOT is recorded here: ۆ is Uyghur as well, so it is not in the pattern."""
    rx = LA.AUX_SCRIPT_RX['Sorani']
    assert rx.search(SORANI_PROSE)
    for other in (PASHTO_PROSE,
                  'نحن نقدم خدمات قانونية مجانية للعائلات المهاجرة في هذه المدينة كل يوم',   # Arabic
                  'ما خدمات حقوقی رایگان به خانواده‌های مهاجر در این شهر ارائه می‌دهیم',       # Persian
                  'ہم اس شہر میں تارکین وطن خاندانوں کو مفت قانونی خدمات فراہم کرتے ہیں',    # Urdu
                  'بىز ئۇيغۇر تىلىدا ھۆججەت تەمىنلەيمىز',                                  # Uyghur
                  KURMANJI_PROSE):
        assert not rx.search(other), other[:30]
    assert 'ۆ' not in rx.pattern, 'the shared letter is back in the gate; Uyghur writes it too'


def test_every_script_with_a_threshold_of_its_own_has_a_word_list():
    """A script the run test judges and the word test does not is the asymmetry this closes, so the
    two lists have to cover the same scripts. Cyrillic is named by its language, so its entry is
    under the script name and `_script_prose` maps every Cyrillic language onto it."""
    named = {n for n, _ in LA.SCRIPTS}
    assert named - set(LA.SCRIPT_FUNC) == set()
    for lang in LA._CYR_LANGS:
        assert LA.SCRIPT_FUNC_RX.get('Cyrillic') is not None
        assert LA._script_prose('дуже добре', 0, 10, lang) is True
    # a one-letter Cyrillic word cannot separate a name from prose: "у" is a preposition and it is
    # also inside the name this rule exists for
    assert all(len(w) > 1 for w in LA.SCRIPT_FUNC['Cyrillic'].split())


def test_a_script_without_a_word_list_is_read_exactly_as_before():
    """`_script_prose` answers True for a script it has no list for, so turning the test on can
    never take away a reading it cannot judge."""
    assert LA._script_prose('whatever', 0, 8, 'Chin') is True


# ---- the Ethiopic script carries two languages, and until this it could say one
#
# The prose in these four strings is invented for this file: one invented community centre, invented
# services, and no organization or place that exists.
AMHARIC_PROSE = ('ማዕከላችን በየሳምንቱ ለስደተኛ ቤተሰቦች ነፃ የሕግ ምክር ይሰጣል። አገልግሎቱ ክፍያ የለውም እንዲሁም ስለ የመኖሪያ ሁኔታ '
                 'አንጠይቅም። ቢሮው ከሰኞ እስከ ዓርብ ክፍት ነው እና ሁሉ ሰው መምጣት ይችላል።')
# Tigrinya twice, because the resolution has two halves and a page can carry either. The first
# string carries none of the seven letters and is named on the WORDS; the second carries መቐበሊ,
# which is the ordinary word for a reception desk, and is named on the LETTER.
TIGRINYA_PROSE = ('ማእከልና ኣብ ነፍሲ ወከፍ ሰሙን ንስደተኛታት ስድራቤታት ነጻ ሕጋዊ ምኽሪ ይህብ። ኣገልግሎት ክፍሊት የብሉን ከምኡውን ብዛዕባ '
                  'ናይ መንበሪ ኩነታት ኣይንሓትትን። ቤት ጽሕፈት ካብ ሰኑይ ክሳብ ዓርቢ ክፉት እዩ ድማ ኩሉ ሰብ ክመጽእ ይኽእል።')
TIGRINYA_LETTERS = ('ናብ መቐበሊ ምጹ። ነርስ ጸቕጢ ደም ብነጻ ትዕቅን። ቤት ጽሕፈት ካብ ሰኑይ ክሳብ ዓርቢ ክፉት እዩ ድማ ኩሉ ሰብ '
                    'ክመጽእ ይኽእል።')


def test_tigrinya_is_told_from_amharic_inside_the_ethiopic_script():
    """Both are written in one range and the SCRIPTS entry is called `Amharic`, so before this a
    Tigrinya page carried no Amharic particle, `_script_prose` refused the run and the page read as
    carrying no language at all. Both halves of the resolution are exercised here, the words on the
    first string and the letters on the second."""
    assert LA.languages_in(TIGRINYA_PROSE, aux=False) == ['Tigrinya']
    assert LA.languages_in(TIGRINYA_LETTERS, aux=False) == ['Tigrinya']
    assert LA.languages_in(AMHARIC_PROSE, aux=False) == ['Amharic'], 'Amharic reads as it did'


def test_the_tigrinya_letters_are_absent_from_amharic():
    """The gate is worth something only if the seven letters really do separate the two.

    They are not in the Amharic alphabet at all, which is why one of them is evidence the way ў is
    evidence of Belarusian, and they are ordinary service vocabulary in Tigrinya rather than a rare
    sign: መቐበሊ is a reception desk and ጸቕጢ is pressure.
    """
    pat = dict(LA.ETHIOPIC)['Tigrinya']
    assert re.search(pat, TIGRINYA_LETTERS)
    assert not re.search(pat, TIGRINYA_PROSE), 'the word half of the test needs a string without them'
    assert not re.search(pat, AMHARIC_PROSE)
    assert not re.search(pat, 'ማስታወቂያ አገልግሎቱ ነፃ ነው ወደ መቀበያው ይምጡ')


def test_a_word_the_two_ethiopic_languages_share_names_neither():
    """Same subtraction CYR_RX makes: ግን is `but` in both, so it cannot carry a language."""
    assert 'ግን' in LA.ETH_FUNC['Amharic'] and 'ግን' in LA.ETH_FUNC['Tigrinya']
    assert not LA.ETH_RX['Amharic'].search('ግን')
    assert not LA.ETH_RX['Tigrinya'].search('ግን')
    # and it is still in the union, because naming is a different question from whether the run is
    # a sentence at all
    assert 'ግን' in LA.SCRIPT_FUNC['Amharic'].split()


# ---- two alphabets of one language each, which is a cleaner range than any of the four below
#
# Invented prose again. Armenian is on the reviewer's list; Georgian is beside it because the two
# ranges are the same kind of evidence and because a Georgian page had no route at all short of the
# identifier's two-sentence gate.
ARMENIAN_PROSE = ('Մեր կազմակերպությունը ամեն շաբաթ ներգաղթյալ ընտանիքների համար անվճար '
                  'իրավաբանական խորհրդատվություն է տրամադրում, և մենք ձեզ ձեր կարգավիճակի մասին '
                  'չենք հարցնում։')
GEORGIAN_PROSE = ('ჩვენი ორგანიზაცია ყოველ კვირას მიგრანტი ოჯახებისთვის უფასო იურიდიულ '
                  'კონსულტაციას სთავაზობს და ჩვენ არ გეკითხებით თქვენი სტატუსის შესახებ.')


@pytest.mark.parametrize('lang,text', [('Armenian', ARMENIAN_PROSE), ('Georgian', GEORGIAN_PROSE)])
def test_an_alphabet_of_one_language_names_that_language(lang, text):
    """Each of these two ranges is written by one nation's language and by nothing else, so it is
    cleaner evidence than the Brahmic four, which carry minority languages beside the majority one.
    Both were reachable before only through the identifier's two-sentence gate."""
    assert LA.languages_in(text, aux=False) == [lang]
    assert lang not in LA.SCRIPT_RUN, 'this script takes the table default, not a number of its own'


@pytest.mark.parametrize('lang,label', [('Armenian', 'Հայերեն'), ('Georgian', 'ქართული')])
def test_a_switcher_label_in_these_scripts_is_not_a_paragraph(lang, label):
    """Rule 7 again: the autonym on a control is a word, and a word is not writing."""
    assert LA.languages_in('English %s Home About Contact' % label, aux=False) == []
    # and the label does resolve as a control, which is the other half of the same page
    assert LA._lookup_language(LA.LANG_TOKEN, label) == lang


def test_these_two_scripts_take_the_ordinary_word_boundary():
    """They write no combining vowel signs, so \\b means what it says here and SCRIPT_FUNC_EDGE is
    not needed; the Brahmic four are the entries that need it."""
    for lang in ('Armenian', 'Georgian'):
        assert lang in LA.SCRIPT_FUNC_SPACED and lang not in LA.SCRIPT_FUNC_EDGE
    # both spellings of the Armenian `and`, because a page may write either
    assert 'և' in LA.SCRIPT_FUNC['Armenian'].split()
    assert 'եւ' in LA.SCRIPT_FUNC['Armenian'].split()


# ---- codebook rule 9 inside a script: a conjunction stands in for no verb
#
# The regression this closes. Re-judging a 300-site prefix of the gold frame moved exactly one site,
# an Armenian cultural organization whose settled class is english_only, to true_multilingual on
# Armenian. What carried it was its event subtitles: an Armenian noun phrase beside its English
# twin, 55 to 70 characters, no verb, joined by the conjunction. The run cleared the length
# threshold and the conjunction cleared SCRIPT_FUNC_MIN, and nothing else on the page was Armenian.
# The subtitles below are invented and have the shape; the real ones are not in this repository.
ARMENIAN_SUBTITLES = (
    'Events at the centre. '
    'Graphic Novels from Two Cities  հայկական գրաֆիկական վեպեր Բեյրութից եւ Ստամբուլից  '
    'Board Games Evening  նարդի, թղթախաղ եւ շախմատի պատմությունը Հայաստանում  '
    'Writing Workshop  գրելու աշխատանոց Աննա Գալաչյանի եւ Ալեքսիա Հաթունի ուղեկցութեամբ  '
    'All events are free and open to the public. Doors open at six in the evening.')


def test_a_verbless_bilingual_subtitle_joined_by_a_conjunction_is_not_a_paragraph():
    """Rule 9's own distinction, in a script. The run is 57 characters against a threshold of 40,
    so the length test passes; the only Armenian particle on the page is the conjunction, and a
    conjunction is what a label is built from."""
    assert LA.languages_in(ARMENIAN_SUBTITLES, aux=False) == ['English']
    pat = dict(LA.SCRIPTS)['Armenian']
    assert LA._longest_run(ARMENIAN_SUBTITLES, pat) >= LA.SCRIPT_RUN_DEFAULT, (
        'the length test has to PASS, or this fixture is testing the wrong gate')
    assert LA._longest_run(ARMENIAN_SUBTITLES, pat, (), 'Armenian') == 0


def test_the_same_line_with_a_verb_in_it_still_counts():
    """The other half of rule 9, and the passage this instrument most wants to read: a help notice
    is one clause, and one clause carries a copula."""
    notice = ('Հայտարարություն. եթե ձեզ օգնություն է պետք հայերենով, եկեք ընդունարան '
              'երկուշաբթիից ուրբաթ։ Խորհրդատվությունը անվճար է և մենք չենք հարցնում ձեր '
              'ներգաղթի կարգավիճակի մասին։')
    assert LA.languages_in(notice, aux=False) == ['Armenian']
    # and the conjunction is still IN the list, because beside a copula it is evidence of prose
    assert 'և' in LA.SCRIPT_FUNC['Armenian'].split()


@pytest.mark.parametrize('script', sorted(LA.SCRIPT_CONNECTIVE))
def test_a_coordinator_alone_never_clears_the_script_paragraph_test(script):
    """Uniform over every script that has a coordinator in its list, so this is a rule and not a
    patch for one language. A window carrying one coordinator and nothing else fails; the same
    window with one qualifying particle added passes.
    """
    conj = LA.SCRIPT_CONNECTIVE[script].split()[0]
    qualifying = sorted(set(LA.SCRIPT_FUNC[script].split())
                        - set(LA.SCRIPT_CONNECTIVE[script].split()))
    assert qualifying, '%s has no qualifying particle left, so the class is too wide' % script
    alone = ' %s ' % conj
    assert LA._script_prose(alone, 0, len(alone), script) is False, script
    with_one = ' %s %s ' % (conj, qualifying[0])
    assert LA._script_prose(with_one, 0, len(with_one), script) is True, script


def test_every_coordinator_is_a_word_of_the_list_it_is_subtracted_from():
    """The set is a partition of the lists and not a second vocabulary. A word here that is not in
    its own SCRIPT_FUNC entry is a typo that would silently subtract nothing, and a conjunction
    added to a list later without being classified here is the way this rule quietly stops
    holding."""
    for script, words in LA.SCRIPT_CONNECTIVE.items():
        have = set(LA.SCRIPT_FUNC[script].split())
        missing = [w for w in words.split() if w not in have]
        assert missing == [], (script, missing)


def test_the_class_is_coordinators_and_not_the_whole_grammar():
    """Where the judgement is, asserted so that widening the class has to be deliberate.

    A complementizer stays qualifying, because a word meaning `that` introduces a subordinate clause
    and so is evidence of the verb rule 9 asks for; the causal subordinators stay qualifying for the
    same reason. Burmese is the one entry with no coordinator at all, which is why it needs no
    exclusion: its list is the sentence-final verb markers and was built that way.
    """
    assert 'Burmese' not in LA.SCRIPT_CONNECTIVE
    for w in ('因为', '因為'):
        assert w in LA.SCRIPT_FUNC['Chinese'].split()
        assert w not in LA.SCRIPT_CONNECTIVE['Chinese'].split()
    for w in ('和', '或'):
        assert w in LA.SCRIPT_CONNECTIVE['Chinese'].split()
    # a copula, a pronoun and a case marker are qualifying in the scripts added with this work
    assert 'է' not in LA.SCRIPT_CONNECTIVE['Armenian'].split()
    assert 'არის' not in LA.SCRIPT_CONNECTIVE['Georgian'].split()
    assert 'ኣብ' not in LA.SCRIPT_CONNECTIVE['Amharic'].split()


# ---- four Brahmic ranges that are their own proof, the way Khmer and Thai already were
#
# Invented prose, one invented community centre, in the two shapes the coverage work uses: a
# paragraph and a help notice.
BRAHMIC = {
    'Punjabi': ('ਸਾਡੀ ਸੰਸਥਾ ਹਰ ਹਫ਼ਤੇ ਪਰਵਾਸੀ ਪਰਿਵਾਰਾਂ ਨੂੰ ਮੁਫ਼ਤ ਕਾਨੂੰਨੀ ਸਲਾਹ ਦਿੰਦੀ ਹੈ ਅਤੇ ਅਸੀਂ ਤੁਹਾਨੂੰ '
                'ਕਿਸੇ ਵੀ ਹਾਲਤ ਬਾਰੇ ਨਹੀਂ ਪੁੱਛਦੇ।',
                'ਜੇ ਤੁਹਾਨੂੰ ਮਦਦ ਦੀ ਲੋੜ ਹੈ ਤਾਂ ਸੋਮਵਾਰ ਤੋਂ ਸ਼ੁੱਕਰਵਾਰ ਤੱਕ ਆਓ ਅਤੇ ਅਸੀਂ ਕੋਈ ਫ਼ੀਸ ਨਹੀਂ ਲੈਂਦੇ।'),
    'Gujarati': ('અમારી સંસ્થા દર અઠવાડિયે સ્થળાંતરિત પરિવારો માટે મફત કાનૂની સલાહ આપે છે અને અમે તમને '
                 'કોઈ પણ સ્થિતિ વિશે પૂછતા નથી।',
                 'જો તમને મદદની જરૂર હોય તો સોમવારથી શુક્રવાર સુધી આવો અને અમે કોઈ ફી લેતા નથી।'),
    'Tamil': ('எங்கள் அமைப்பு ஒவ்வொரு வாரமும் குடிபெயர்ந்த குடும்பங்களுக்கு இலவச சட்ட ஆலோசனை '
              'வழங்குகிறது மற்றும் உங்கள் நிலை பற்றி நாங்கள் கேட்பதில்லை.',
              'உங்களுக்கு உதவி தேவைப்பட்டால் திங்கள் முதல் வெள்ளி வரை வாருங்கள், இந்த ஆலோசனை இலவசம்.'),
    'Telugu': ('మా సంస్థ ప్రతి వారం వలస కుటుంబాల కోసం ఉచిత న్యాయ సలహా ఇస్తుంది మరియు మీ స్థితి గురించి '
               'మేము అడగము.',
               'మీకు సహాయం అవసరమైతే సోమవారం నుండి శుక్రవారం వరకు రండి, ఈ సలహా ఉచితం కానీ సమయం కావాలి.'),
}


@pytest.mark.parametrize('lang', sorted(BRAHMIC))
def test_a_brahmic_range_is_its_own_proof_of_the_language(lang):
    """Each of the four is written by one language of this vocabulary and by nothing else, so the
    range is evidence the way the Khmer and Thai ranges already are. Both shapes are held, because
    the notice is the one these four could not reach: the identifier wants two sentences of 140
    characters each and a help notice has none."""
    para, notice = BRAHMIC[lang]
    assert LA.languages_in(para, aux=False) == [lang]
    assert LA.languages_in(notice, aux=False) == [lang]


@pytest.mark.parametrize('lang', sorted(BRAHMIC))
def test_the_new_brahmic_scripts_are_held_to_the_paragraph_standard(lang):
    """Rule 7 in a new script, and the threshold is the table's own default rather than a number
    chosen for these four. A label row is under it and a sentence is over it."""
    assert lang not in LA.SCRIPT_RUN, 'this script must take the default, not a number of its own'
    para = BRAHMIC[lang][0]
    pat = dict(LA.SCRIPTS)[lang]
    assert LA._longest_run(para, pat, (), lang) >= LA.SCRIPT_RUN_DEFAULT
    # the label a language menu writes, which is a word and not a sentence
    label = {'Punjabi': 'ਪੰਜਾਬੀ', 'Gujarati': 'ગુજરાતી', 'Tamil': 'தமிழ்', 'Telugu': 'తెలుగు'}[lang]
    assert LA.languages_in('English %s Home About Contact' % label, aux=False) == []


def test_the_four_new_scripts_carry_a_word_list_matched_on_their_own_edge():
    """Every script with a run threshold needs a word list, and these four write combining vowel
    signs, so the list has to be matched on the script's range rather than on \\b."""
    for lang in BRAHMIC:
        assert lang in LA.SCRIPT_FUNC and lang in LA.SCRIPT_FUNC_EDGE
        para = BRAHMIC[lang][0]
        assert LA.SCRIPT_FUNC_RX[lang].search(para), lang


# ---- the Bengali script carries two languages, and the letter that separates them is the r
#
# Invented prose again: one invented community centre and no organization or place that exists.
BENGALI_PROSE = ('আমাদের সংস্থা প্রতি সপ্তাহে অভিবাসী পরিবারের জন্য বিনামূল্যে আইনি পরামর্শ দেয়। '
                 'পরামর্শ বিনামূল্যে এবং আমরা আপনার অবস্থা সম্পর্কে কিছু জিজ্ঞাসা করি না।')
ASSAMESE_PROSE = ('আমাৰ সংস্থাই প্ৰতি সপ্তাহত প্ৰব্ৰজনকাৰী পৰিয়ালৰ বাবে বিনামূলীয়া আইনী পৰামৰ্শ দিয়ে। '
                  'পৰামৰ্শ বিনামূলীয়া আৰু আমি আপোনাক অৱস্থাৰ বিষয়ে একো নুসুধোঁ।')


def test_assamese_is_told_from_bengali_inside_the_bengali_script():
    """Assamese was reachable only through the identifier, which wants two sentences of 140
    characters each, so an Assamese page of ordinary length read as Bengali."""
    assert LA.languages_in(BENGALI_PROSE, aux=False) == ['Bengali'], 'Bengali reads as it did'
    assert LA.languages_in(ASSAMESE_PROSE, aux=False) == ['Assamese']


def test_the_assamese_letter_is_the_r_and_not_the_w():
    """ৰ is the consonant r, so it is in almost every Assamese sentence rather than being a rare
    sign, and Bengali writes র instead. ৱ is the letter usually named beside it and it is out for
    the reason ۆ is out of the Sorani gate: Bengali writes it too, in transliterated names, so it
    would put Assamese on a Bengali page that mentions a person. Dropping it costs nothing, because
    no Assamese passage carries ৱ without carrying ৰ."""
    pat = dict(LA.BENGALI)['Assamese']
    assert pat == 'ৰ' and 'ৱ' not in pat
    assert len(re.findall(pat, ASSAMESE_PROSE)) >= 5, 'the letter has to be frequent, not rare'
    assert not re.search(pat, BENGALI_PROSE)


def test_the_words_the_two_bengali_script_languages_share_name_neither():
    """These two share most of their grammatical vocabulary, so the subtraction does more work here
    than in the Cyrillic or Ethiopic tables."""
    shared = sorted(w for w, n in LA._BEN_ALL.items() if n > 1)
    assert len(shared) >= 4, shared
    for w in shared:
        assert not LA.BEN_RX['Bengali'].search(w) and not LA.BEN_RX['Assamese'].search(w), w
        assert w in LA.SCRIPT_FUNC['Bengali'].split(), w


def test_the_bengali_entry_keeps_every_word_it_held():
    """The same union the Devanagari entry became, and the same reason for checking it."""
    held = 'এবং এর করে থেকে জন্য আমরা আমাদের এই তার না যে হয় আছে সঙ্গে সব'.split()
    now = set(LA.SCRIPT_FUNC['Bengali'].split())
    assert [w for w in held if w not in now] == []


def test_bengali_falls_back_to_the_reading_it_had_before():
    assert LA._bengali_language('নমস্কার কেন্দ্র') == 'Bengali'
    assert LA._bengali_language('') == 'Bengali'


# ---- Devanagari carries three languages, and until this it could say one
#
# Invented prose again: one invented community centre and no organization or place that exists.
HINDI_PROSE = ('हमारी संस्था हर सप्ताह प्रवासी परिवारों को निःशुल्क कानूनी सलाह देती है। यह सेवा नहीं '
               'बदलती और हम किसी से उसकी स्थिति के बारे में नहीं पूछते हैं।')
NEPALI_PROSE = ('हाम्रो संस्थाले हरेक हप्ता आप्रवासी परिवारहरूलाई निःशुल्क कानुनी सल्लाह दिन्छ। सल्लाह '
                'निःशुल्क छ र हामी तपाईंलाई अवस्थाबारे सोध्दैनौं, कार्यालय बिहानदेखि साँझसम्म खुला छ।')
MARATHI_PROSE = ('आमच्या संस्थेत दर आठवड्याला स्थलांतरित कुटुंबांना मोफत कायदेशीर सल्ला दिला जातो. सल्ला '
                 'मोफत आहे आणि आम्ही तुम्हाला तुमच्या स्थितीबद्दल विचारत नाही, कार्यालय सदैव उघडे असते.')


def test_nepali_and_marathi_are_told_from_hindi_inside_devanagari():
    """One alphabet, three languages, and one name for all of them until now. A Nepali page was not
    missed, it was reported as Hindi, which is one community's name on another's page and is the
    failure CYRILLIC was built for in the other shared script."""
    assert LA.languages_in(HINDI_PROSE, aux=False) == ['Hindi'], 'Hindi reads as it did'
    assert LA.languages_in(NEPALI_PROSE, aux=False) == ['Nepali']
    assert LA.languages_in(MARATHI_PROSE, aux=False) == ['Marathi']


def test_the_devanagari_words_separate_the_three_with_room():
    """The scoring bar is CYR_RX's, two distinct words and strictly more than any other, so the
    margins are worth pinning rather than the verdict alone."""
    for text, want in ((HINDI_PROSE, 'Hindi'), (NEPALI_PROSE, 'Nepali'), (MARATHI_PROSE, 'Marathi')):
        score = {k: len({m.group(0) for m in rx.finditer(text)}) for k, rx in LA.DEV_RX.items()}
        best = max(score, key=score.get)
        assert best == want and score[best] >= 2, (want, score)
        assert score[best] > sorted(score.values())[-2], (want, score)


def test_devanagari_falls_back_to_the_reading_it_had_before():
    """Below the bar the answer is Hindi, which every Devanagari page read before this existed, so
    the resolution can move a page off Hindi and can never move one to nothing."""
    assert LA._devanagari_language('नमस्ते केंद्र') == 'Hindi'
    assert LA._devanagari_language('') == 'Hindi'


def test_a_devanagari_word_test_is_not_a_fragment_test():
    """The boundary defect this closes, asserted on both sides.

    `\\b` is defined against `\\w`, a Devanagari vowel sign is a combining mark and so is not `\\w`,
    and the effect was not that such a word matched less often. `\\bका\\b` could not match `का`
    standing alone and COULD match the first two characters of `कार्यक्रम`, so the entry tested for
    fragments. Both directions are held here, because fixing only the first would leave a name
    clearing rule 7 on a fragment.
    """
    assert LA.SCRIPT_FUNC_RX['Hindi'].search(' का '), 'the word standing alone has to match'
    assert not LA.SCRIPT_FUNC_RX['Hindi'].search('कार्यक्रम कार्यालय'), 'and a fragment must not'
    # the words that could never match under the old boundary, all of them ordinary Hindi
    for w in ('है', 'हैं', 'के', 'की', 'में', 'से', 'नहीं'):
        assert LA.SCRIPT_FUNC_RX['Hindi'].search(' %s ' % w), w
        assert not re.search(r'\b(?:%s)\b' % re.escape(w), ' %s ' % w), (
            '%s is matchable under \\b after all, so the note above SCRIPT_FUNC_EDGE is wrong' % w)


def test_the_devanagari_entry_keeps_every_word_it_held():
    """The entry became the union of DEV_FUNC plus the shared connectives, and a union that dropped
    one of the twenty it had would be a silent narrowing of rule 7 in this script."""
    held = 'है हैं के की का को में से और पर यह वह हम आप नहीं कि लिए हुए था थे'.split()
    now = set(LA.SCRIPT_FUNC['Hindi'].split())
    assert [w for w in held if w not in now] == []


def test_ethiopic_falls_back_to_the_reading_it_had_before():
    """`_cyrillic_language` can answer with the script name and this cannot, because `Amharic` is
    the SCRIPTS entry. So the fallback is Amharic, which is what every Ethiopic page read before."""
    assert LA._ethiopic_language('ሰላም ማዕከል') == 'Amharic'
    assert LA._ethiopic_language('') == 'Amharic'


# ---- F1: the document the server sent settles authored against widget
def test_a_locale_address_under_a_widget_is_the_widgets_even_server_confirmed():
    """A locale address is where a translation system puts its output, and text in the server's
    document at one proves server-side DELIVERY rather than authorship. Granicus runs Google
    Translate on the server and serves the output at ?lang_update=<ticks>; GTranslate's paid tier
    serves it at language subdomains; ConveyThis at ?locale=. The earlier order let server
    confirmation win here, and six unanimous rows of the validation sample were credited, in up
    to eleven languages each, with text Google wrote. At an ORDINARY address the confirmation
    still counts, which is what keeps one regional legal aid organization's Spanish and Somali
    Know Your Rights post its own."""
    widget_made = [LA.Evidence('translated_page', 'https://x.org/es', 'texto', 'Spanish')]
    server_sent = [LA.Evidence('translated_page', 'https://x.org/es', 'texto', 'Spanish',
                               server_html=True)]
    granicus = [LA.Evidence('translated_page',
                            'https://x.org/home?lang_update=639212242815969751',
                            'texto', 'Spanish', server_html=True)]
    own_page = [LA.Evidence('translated_page', 'https://x.org/servicios', 'texto', 'Spanish',
                            server_html=True)]
    assert LA.verdict_for(widget_made, 'Google Translate') == 'machine_translate'
    assert LA.verdict_for(server_sent, 'Google Translate') == 'machine_translate'
    assert LA.verdict_for(granicus, 'Google Translate') == 'machine_translate'
    assert LA.verdict_for(own_page, 'Google Translate') == 'true_multilingual'
    assert LA.counted_evidence(server_sent, 'Google Translate') == []
    assert LA.counted_evidence(own_page, 'Google Translate') == own_page


def test_no_vendors_server_document_proves_authorship_at_a_locale_address():
    """Weglot, Localize, Bablic and Smartling can each be deployed as a proxy that translates
    before the response leaves the host, and the browser-side three each have a server-side
    deployment too: Granicus for Google Translate, the paid subdomain tier for GTranslate, the
    ?locale= routes for ConveyThis. The vendor's name says the vendor is installed, not which
    deployment was bought, so at a locale address the server document settles nothing for ANY of
    them. Crediting the organization with it would be the overstatement this package exists to
    prevent."""
    server_sent = [LA.Evidence('translated_page', 'https://x.org/es', 'texto', 'Spanish',
                               server_html=True)]
    for vendor in tuple(LA.CLIENT_SIDE_WIDGET) + ('Weglot', 'Localize', 'Bablic', 'Smartling'):
        assert LA.verdict_for(server_sent, vendor) == 'machine_translate'


def test_server_confirmation_is_what_makes_a_notice_under_a_widget_authored():
    """Was `test_server_confirmation_changes_nothing_where_the_address_was_never_the_objection`,
    and the first assertion was machine_translate on 2026-07-30, under rule 10's count rule. This
    is that community house's exact shape: a Spanish notice in the server's own response, on an
    ordinary address, under a Google Translate widget. Server confirmation makes it
    `authored`, the coverage cut makes it level 2, and the derivation counts an authored notice.
    The answer key agrees, under rule 10."""
    frag = [LA.Evidence('inline_text', 'https://x.org/', 'aviso', 'Spanish', server_html=True)]
    assert LA.authorship_of(frag[0], 'Google Translate') == LA.AUTHOR_AUTHORED
    assert LA.sufficiency_of(frag[0]) == LA.SUFF_NOTICE
    assert LA.verdict_for(frag, 'Google Translate') == 'true_multilingual'
    assert LA.verdict_for(frag * 2, 'Google Translate') == 'true_multilingual'
    assert LA.verdict_for(frag, '') == 'true_multilingual'
    # an archive page is still an archive page, whoever wrote it: rule 13 drops it from the
    # counted evidence before the widget question is reached
    old = [LA.Evidence('translated_page', 'https://x.org/category/past_events/', 'q', 'German',
                       server_html=True)]
    assert LA.counted_evidence(old, 'Google Translate') == []
    assert LA.verdict_for(old, '') == 'english_only'


def test_a_stored_row_written_before_this_field_existed_still_reads():
    """Evidence arrives as a dict once it has been through JSON, and a row written by an earlier
    version has no server_html key at all."""
    old_row = {'mechanism': 'translated_page', 'url': 'https://x.org/es', 'quote': 'texto',
               'language': 'Spanish'}
    assert LA._ev_server(old_row) is False
    assert LA.verdict_for([old_row], 'Google Translate') == 'machine_translate'
    assert LA._ev_server(dict(old_row, server_html=True)) is True
    # the field still reads off a dict; what it can no longer do is prove authorship at a locale
    # address, where server text is server-side delivery of the translation system's output
    assert (LA.verdict_for([dict(old_row, server_html=True)], 'Google Translate')
            == 'machine_translate')
    own = dict(old_row, url='https://x.org/servicios', server_html=True)
    assert LA.verdict_for([own], 'Google Translate') == 'true_multilingual'


def test_a_cyrillic_finding_is_quoted_from_the_cyrillic():
    """A Cyrillic reading is reported under its LANGUAGE and SCRIPTS holds only the script, so the
    quote matched nothing and fell back to the opening words of the page, which on a long page are
    English. Nothing about the verdict changes; what changes is what a person checking one is shown,
    and a coder about to check a sample of these readings is exactly who the quote is for."""
    page = ('Event name: Event Date: Sun, Jun 14th, 2026 Event Details: Children Day, a round '
            'robin of activities for the whole family at the hall. '
            + 'Наша громада запрошує дітей та батьків на святкування, і всі заняття безкоштовні.')
    q = LA._quote(page, 'Ukrainian')
    assert 'Наша громада' in q
    assert not q.startswith('Event name')
    # the scripts that were already right stay right, and the same way: the quote is taken at the
    # run, not at the top of the page
    english = 'Welcome to our center. We hold classes for the whole family every week of the year. '
    zh = LA._quote(english * 2 + '我们是一个非营利社区组织，为社区服务。' * 2, 'Chinese')
    assert '我们是一个非营利社区组织' in zh and not zh.startswith('Welcome to our center')


# ------------------------------------------------- the two-axis model, settled 2026-07-30
# Three classes were carrying two independent questions, which is why the boundary rules
# kept contradicting each other. The questions are recorded separately now and the class is derived
# from them, so what follows are known-answer cases for each axis, for the table that joins them,
# and for the two sites that forced it.


def test_authorship_names_who_produced_the_text():
    """The four values, and the two boundaries the earlier code could only answer by proxy."""
    # nothing client-side is present, so nothing but the site can have written it
    own = LA.Evidence('inline_text', 'https://x.org/servicios', 'aviso', 'Spanish')
    assert LA.authorship_of(own, '') == LA.AUTHOR_AUTHORED
    # server-confirmed AT A LOCALE ADDRESS is server-side delivery of the translation system's
    # output, because the vendor a widget names also sells server deployments: Granicus serves
    # Google's output at ?lang_update=. The route outranks the confirmation.
    confirmed = LA.Evidence('translated_page', 'https://x.org/es', 'texto', 'Spanish',
                            server_html=True)
    assert LA.authorship_of(confirmed, 'Google Translate') == LA.AUTHOR_CLIENT_WIDGET
    # at an ordinary address the confirmation still decides, and nothing else could have
    ordinary = LA.Evidence('translated_page', 'https://x.org/servicios', 'texto', 'Spanish',
                           server_html=True)
    assert LA.authorship_of(ordinary, 'Google Translate') == LA.AUTHOR_AUTHORED
    # the same response settles nothing under a vendor that can be deployed as a proxy
    assert LA.authorship_of(confirmed, 'Weglot') == LA.AUTHOR_CLIENT_WIDGET
    # a CMS marker in the server document: the text is real and in the response, and WPML may have
    # produced it, which is rule 11's question and not the widget's
    plugin = LA.Evidence('translated_page', 'https://x.org/es', 'texto', 'Spanish',
                         server_plugin=True)
    assert LA.authorship_of(plugin, 'ConveyThis') == LA.AUTHOR_SERVER_PLUGIN
    assert LA.authorship_of(plugin, '') == LA.AUTHOR_SERVER_PLUGIN
    # a translation proxy is Google Translate's own output, served from Google's host rather than
    # written in the visitor's browser. Calling it a plugin would credit an organization with a
    # machine translation, which is the one thing this package exists to prevent.
    for u in ('https://x-org.translate.goog/services', 'https://x.org/page?_x_tr_sl=en'):
        proxy = LA.Evidence('translated_page', u, 'texto', 'Spanish')
        assert LA.authorship_of(proxy, 'Google Translate') == LA.AUTHOR_CLIENT_WIDGET
        assert LA.authorship_of(proxy, '') == LA.AUTHOR_CLIENT_WIDGET
    # a locale address under a widget, with no server confirmation, is where a widget puts its output
    mirror = LA.Evidence('translated_page', 'https://x.org/es', 'texto', 'Spanish')
    assert LA.authorship_of(mirror, 'Google Translate') == LA.AUTHOR_CLIENT_WIDGET
    # a control the widget rendered, clicked, shows the widget working and nothing else
    ctrl = LA.Evidence('language_control', 'https://x.org/', 'texto', 'Spanish')
    assert LA.authorship_of(ctrl, 'Google Translate') == LA.AUTHOR_CLIENT_WIDGET
    assert LA.authorship_of(ctrl, '') == LA.AUTHOR_AUTHORED
    # no language named is no text to have a authorship at all
    marker = LA.Evidence('translation_plugin', 'https://x.org/', 'wpml', '')
    assert LA.authorship_of(marker, '') == LA.AUTHOR_NONE
    assert LA.authorship_of(marker, 'Google Translate') == LA.AUTHOR_NONE


def test_a_recorded_authorship_is_not_derived_again():
    """The audit answers the question once and writes the answer down. Deriving it a second time
    from a page that has since changed would let a stored reading move under a reader."""
    e = LA.Evidence('translated_page', 'https://x.org/es', 'texto', 'Spanish',
                    authorship=LA.AUTHOR_AUTHORED, sufficiency=LA.SUFF_PAGE)
    assert LA.authorship_of(e, 'Google Translate') == LA.AUTHOR_AUTHORED
    assert LA.sufficiency_of(e) == LA.SUFF_PAGE
    # and a row written before the fields existed still reads, by derivation
    old_row = {'mechanism': 'translated_page', 'url': 'https://x.org/es', 'quote': 'texto',
               'language': 'Spanish'}
    assert LA.authorship_of(old_row, 'Google Translate') == LA.AUTHOR_CLIENT_WIDGET
    assert LA.sufficiency_of(old_row) == LA.SUFF_PAGE


def test_the_ladder_is_ordered_the_way_its_names_say():
    assert LA.SUFF_NONE < LA.SUFF_TOKEN < LA.SUFF_NOTICE < LA.SUFF_PAGE < LA.SUFF_SECTION
    assert LA.SUFFICIENCY_COUNTS == LA.SUFF_NOTICE
    assert set(LA.SUFFICIENCY_NAMES) == {0, 1, 2, 3, 4}


def test_each_rung_of_the_ladder_from_synthetic_text_at_known_coverage():
    """The rung is read off the same coverage cut the crawl labels its findings with, so the two
    cannot drift apart: `translated_page` is what the crawl calls a page at or above PAGE_COVERAGE
    and `inline_text` a passage below it."""
    es = ('Nuestros servicios para la comunidad son gratuitos. Ofrecemos informacion y recursos '
          'para las familias que necesitan ayuda con este proceso, y todos pueden hacer una cita. ')
    en = ('Our office provides free legal help to immigrant families across the county every day of '
          'the week. Call us to make an appointment with a caseworker today. ')

    # level 3, a page: the page is substantially written in the language
    assert LA.language_coverage(es * 3, 'Spanish') >= LA.PAGE_COVERAGE
    page = LA.Evidence('translated_page', 'https://x.org/servicios', es[:60], 'Spanish')
    assert LA.sufficiency_of(page) == LA.SUFF_PAGE

    # level 2, a notice: a grammatical passage inside a page that is otherwise English
    assert LA.language_coverage(en * 9 + es, 'Spanish') < LA.PAGE_COVERAGE
    assert _non_english(en * 9 + es) == ['Spanish']          # and it still passes detection
    notice = LA.Evidence('inline_text', 'https://x.org/services/', es[:60], 'Spanish')
    assert LA.sufficiency_of(notice) == LA.SUFF_NOTICE

    # level 1, a token: a name, a slogan or a title in a list. It fails the function-word gate, so
    # the crawl never turns one into evidence, and the rung is where the excluded thing sits
    assert LA.languages_in('Taller de Arte') == []
    assert LA.languages_in('Bienvenidos! Welcome to our center.') == []
    token = LA.Evidence('inline_text', 'https://x.org/programs/', 'Taller de Arte', 'Spanish',
                        sufficiency=LA.SUFF_TOKEN)
    assert LA.sufficiency_of(token) == LA.SUFF_TOKEN

    # level 0, none: a plugin marker names no language, so there is nothing to do with it
    assert LA.sufficiency_of(LA.Evidence('translation_plugin', 'https://x.org/', 'wpml', '')) \
        == LA.SUFF_NONE

    # level 4, a section: two pages in ONE language, or a locale tree the site advertises
    two = [LA.Evidence('translated_page', f'https://x.org/{p}', es[:60], 'Spanish')
           for p in ('servicios', 'recursos')]
    assert LA.sufficiency_summary(two) == LA.SUFF_SECTION
    assert LA.sufficiency_summary(two[:1]) == LA.SUFF_PAGE
    mixed = [two[0], LA.Evidence('translated_page', 'https://x.org/nos-services', 'texte', 'French')]
    assert LA.sufficiency_summary(mixed) == LA.SUFF_PAGE  # one page each is a section in neither
    assert LA.sufficiency_summary(two[:1], advertised_roots=2) == LA.SUFF_SECTION
    # a declaration with nothing found behind it cannot lift the reading on its own
    assert LA.sufficiency_summary([notice], advertised_roots=2) == LA.SUFF_NOTICE


# Every cell of the derivation, written out rather than computed, so that the table here and the
# table in `class_for` have to be compared by a person and cannot agree by construction.
# (authorship, sufficiency, widget present) -> class
DERIVATION_TABLE = [
    (LA.AUTHOR_AUTHORED, 0, False, 'english_only'),
    (LA.AUTHOR_AUTHORED, 0, True, 'machine_translate'),
    (LA.AUTHOR_AUTHORED, 1, False, 'english_only'),
    (LA.AUTHOR_AUTHORED, 1, True, 'machine_translate'),
    (LA.AUTHOR_AUTHORED, 2, False, 'true_multilingual'),
    (LA.AUTHOR_AUTHORED, 2, True, 'true_multilingual'),
    (LA.AUTHOR_AUTHORED, 3, False, 'true_multilingual'),
    (LA.AUTHOR_AUTHORED, 3, True, 'true_multilingual'),
    (LA.AUTHOR_AUTHORED, 4, False, 'true_multilingual'),
    (LA.AUTHOR_AUTHORED, 4, True, 'true_multilingual'),
    (LA.AUTHOR_SERVER_PLUGIN, 0, False, 'english_only'),
    (LA.AUTHOR_SERVER_PLUGIN, 0, True, 'machine_translate'),
    (LA.AUTHOR_SERVER_PLUGIN, 1, False, 'english_only'),
    (LA.AUTHOR_SERVER_PLUGIN, 1, True, 'machine_translate'),
    (LA.AUTHOR_SERVER_PLUGIN, 2, False, 'true_multilingual'),
    (LA.AUTHOR_SERVER_PLUGIN, 2, True, 'true_multilingual'),
    (LA.AUTHOR_SERVER_PLUGIN, 3, False, 'true_multilingual'),
    (LA.AUTHOR_SERVER_PLUGIN, 3, True, 'true_multilingual'),
    (LA.AUTHOR_SERVER_PLUGIN, 4, False, 'true_multilingual'),
    (LA.AUTHOR_SERVER_PLUGIN, 4, True, 'true_multilingual'),
    # client_widget with no widget present cannot occur, since the value names one; the cell is
    # defined anyway, because a rule with an undefined cell is a rule with a hole in it
    (LA.AUTHOR_CLIENT_WIDGET, 0, False, 'english_only'),
    (LA.AUTHOR_CLIENT_WIDGET, 0, True, 'machine_translate'),
    (LA.AUTHOR_CLIENT_WIDGET, 1, False, 'english_only'),
    (LA.AUTHOR_CLIENT_WIDGET, 1, True, 'machine_translate'),
    (LA.AUTHOR_CLIENT_WIDGET, 2, False, 'english_only'),
    (LA.AUTHOR_CLIENT_WIDGET, 2, True, 'machine_translate'),
    (LA.AUTHOR_CLIENT_WIDGET, 3, False, 'english_only'),
    (LA.AUTHOR_CLIENT_WIDGET, 3, True, 'machine_translate'),
    (LA.AUTHOR_CLIENT_WIDGET, 4, False, 'english_only'),
    (LA.AUTHOR_CLIENT_WIDGET, 4, True, 'machine_translate'),
    # `unknown_widget`: a control was drawn, nothing could name it, and no non-English text was
    # found. Every cell is the cell `none` already had, deliberately.
    # The value says the CONTROL was not settled, not that a second language was found,
    # so it may not move a class; a rule reading "a control I cannot name means machine
    # translation" would assert on this axis the one thing the instrument exists to measure. The
    # ten cells are here because the table is the whole space and a cell nobody wrote down is a
    # cell nobody decided. The five `widget=True` cells cannot arise from a reading:
    # `authorship_summary` refuses the value whenever a vendor was named.
    (LA.AUTHOR_UNKNOWN_WIDGET, 0, False, 'english_only'),
    (LA.AUTHOR_UNKNOWN_WIDGET, 0, True, 'machine_translate'),
    (LA.AUTHOR_UNKNOWN_WIDGET, 1, False, 'english_only'),
    (LA.AUTHOR_UNKNOWN_WIDGET, 1, True, 'machine_translate'),
    (LA.AUTHOR_UNKNOWN_WIDGET, 2, False, 'english_only'),
    (LA.AUTHOR_UNKNOWN_WIDGET, 2, True, 'machine_translate'),
    (LA.AUTHOR_UNKNOWN_WIDGET, 3, False, 'english_only'),
    (LA.AUTHOR_UNKNOWN_WIDGET, 3, True, 'machine_translate'),
    (LA.AUTHOR_UNKNOWN_WIDGET, 4, False, 'english_only'),
    (LA.AUTHOR_UNKNOWN_WIDGET, 4, True, 'machine_translate'),
    (LA.AUTHOR_NONE, 0, False, 'english_only'),
    (LA.AUTHOR_NONE, 0, True, 'machine_translate'),
    (LA.AUTHOR_NONE, 1, False, 'english_only'),
    (LA.AUTHOR_NONE, 1, True, 'machine_translate'),
    (LA.AUTHOR_NONE, 2, False, 'english_only'),
    (LA.AUTHOR_NONE, 2, True, 'machine_translate'),
    (LA.AUTHOR_NONE, 3, False, 'english_only'),
    (LA.AUTHOR_NONE, 3, True, 'machine_translate'),
    (LA.AUTHOR_NONE, 4, False, 'english_only'),
    (LA.AUTHOR_NONE, 4, True, 'machine_translate'),
]


@pytest.mark.parametrize('authorship,sufficiency,widget,want', DERIVATION_TABLE,
                         ids=[f'{p}-{s}-{"widget" if w else "no widget"}'
                              for p, s, w, _ in DERIVATION_TABLE])
def test_the_derivation_table_exhaustively(authorship, sufficiency, widget, want):
    assert LA.class_for(authorship, sufficiency, widget=widget) == want


def test_the_derivation_covers_every_value_of_both_axes():
    """A cell nobody wrote down is a cell nobody decided, so the table has to be the whole space."""
    assert {(p, s, w) for p, s, w, _ in DERIVATION_TABLE} == {
        (p, s, w) for p in LA.AUTHORSHIP_ORDER for s in LA.SUFFICIENCY_NAMES for w in (False, True)}


def test_rule_six_is_the_one_thing_outside_the_two_axes():
    """A widget whose advertised route comes back in English has given a visitor nothing, so the
    site is english_only rather than machine_translate. It sits beside the table because it is a
    fact about a route and not about a piece of evidence."""
    assert LA.class_for(LA.AUTHOR_NONE, LA.SUFF_NONE, widget=True,
                        route_was_english=True) == 'english_only'
    assert LA.class_for(LA.AUTHOR_NONE, LA.SUFF_NONE, widget=True) == 'machine_translate'
    # it cannot take a reading away: a site that counted is still true_multilingual
    assert LA.class_for(LA.AUTHOR_AUTHORED, LA.SUFF_NOTICE, widget=True,
                        route_was_english=True) == 'true_multilingual'


def test_the_per_language_breakdown_keeps_two_languages_apart():
    """A site with authored Spanish and a widget-produced Vietnamese is a real and common shape,
    and one summary value hides it. `languages` lists what the verdict counted, so the Vietnamese
    is correctly absent from it; the breakdown is where a reader can still see it was there."""
    ev = [LA.Evidence('inline_text', 'https://x.org/services/immigration/', 'aviso', 'Spanish',
                      server_html=True),
          LA.Evidence('translated_page', 'https://x.org/vi', 'noi dung', 'Vietnamese')]
    assert LA.language_summary(ev, 'Google Translate') == {
        'Spanish': {'authorship': LA.AUTHOR_AUTHORED, 'sufficiency': LA.SUFF_NOTICE},
        'Vietnamese': {'authorship': LA.AUTHOR_CLIENT_WIDGET, 'sufficiency': LA.SUFF_NONE}}
    assert LA.authorship_summary(ev, 'Google Translate') == LA.AUTHOR_AUTHORED
    assert [e.language for e in LA.counted_evidence(ev, 'Google Translate')] == ['Spanish']
    assert LA.verdict_for(ev, 'Google Translate') == 'true_multilingual'
    # with no widget in the page both are the site's own, and both are counted
    assert LA.language_summary(ev, '') == {
        'Spanish': {'authorship': LA.AUTHOR_AUTHORED, 'sufficiency': LA.SUFF_NOTICE},
        'Vietnamese': {'authorship': LA.AUTHOR_AUTHORED, 'sufficiency': LA.SUFF_PAGE}}


def test_a_community_house_notice_is_authored_under_a_widget():
    """The site the rules argued with themselves about. Rule 10's prose names it as the case a
    fragment does not carry, and the project's own answer key codes it true_multilingual under that
    same rule: a whole Spanish notice about DACA renewals at the organization's own
    /services/immigration/, which rule 10 counts on its own even under a widget. On the two axes
    there is nothing left to argue about. The notice is in the
    server's response, which a Google Translate widget cannot reach, so it is authored; it is a
    grammatical passage inside an otherwise English page, so it is level 2; and level 2 is the rung
    at which a reader who does not read English can act on what is there.

    It was machine_translate until 2026-07-30, under the count rule this replaces."""
    ev = [LA.Evidence('inline_text', 'https://example.org/services/immigration/',
                      'Si su DACA vence pronto, comuniquese con nuestra oficina para renovarlo',
                      'Spanish', server_html=True)]
    assert LA.authorship_of(ev[0], 'Google Translate') == LA.AUTHOR_AUTHORED
    assert LA.sufficiency_of(ev[0]) == LA.SUFF_NOTICE
    assert LA.counted_evidence(ev, 'Google Translate') == ev
    assert LA.verdict_for(ev, 'Google Translate') == 'true_multilingual'


def test_an_arts_centres_workshop_title_is_a_token_and_carries_nothing():
    """The other side of the same boundary, and the reason the ladder has a rung below `notice`.
    One arts centre's Spanish is a past workshop's title inside a card list. It is the
    organization's own words, so it is authored; it enables nothing, so it is level 1; and the site
    stays machine_translate. Two rules already take it out before it can become evidence at all: a
    list of short linked labels is chrome whatever element it sits in, and a title with no verb in
    it fails the function-word gate."""
    ev = [LA.Evidence('inline_text', 'https://x.org/programs/', 'Taller de Arte para Jovenes',
                      'Spanish', server_html=True, sufficiency=LA.SUFF_TOKEN)]
    assert LA.authorship_of(ev[0], 'Google Translate') == LA.AUTHOR_AUTHORED
    assert LA.sufficiency_of(ev[0]) == LA.SUFF_TOKEN
    assert LA.verdict_for(ev, 'Google Translate') == 'machine_translate'
    # the gates that keep it off the evidence list in the first place
    assert LA.languages_in('Taller de Arte para Jovenes') == []
    assert LA.CHROME_LIST_MIN_ITEMS == 3 and LA.CHROME_LIST_SHARE == 0.8


# ------------------------------------------------------ wall and placeholder pass, 2026-08-01
# Measured over the census render store, 44,284 capture rows carrying home text over 41,473
# distinct sites. No validation file was
# opened. Each case below pins a CLASS: the two shipped patterns converting a live site into
# unreachable, the length gate that separates a placeholder from a page, and the three candidates
# the measurement rejected.


def _padded(head, body, want=1700):
    """A home read that opens with `head` and continues into a real page.

    The body is repeated to the length of an ordinary home read. Length is what these
    cases test and the assertions state it, so the padding is not doing any silent work.
    """
    out = head + body
    while len(out) < want:
        out += ' ' + body
    return out


# Two community organizations, the only two pages the alternative
# `parked (?:free )?(?:courtesy of|by)` matched in the whole corpus, both live organization sites of
# about 3,000 characters whose history paragraph opens with these two words.
SPARKED = ('Our journey began in 2004, sparked by a simple yet powerful desire to welcome our '
           'neighbours. We run free legal clinics, English classes and a food pantry, and every '
           'programme is open to anyone in the county who needs it. Our staff speak with families '
           'every week about housing, schools and work, and we accompany them to appointments.')


def test_sparked_by_is_not_a_parked_domain():
    """One missing word boundary, a 100 percent false-positive rate. The alternative matched inside
    `sparked by` and its only two matches in 44,284 pages were live organization websites, both
    reported unreachable, which hides them from the measure entirely."""
    assert LA.PARKED_RX.search(SPARKED) is None
    assert LA.is_parked(SPARKED) is False
    # the wording the alternative is for still matches
    assert LA.PARKED_RX.search('This page is parked free courtesy of the registrar.') is not None
    assert LA.is_parked('Parked by the registrar. This domain has no website.') is True


PARKED_PAGE_CASES = [
    # the shipped wordings
    ('a registrar sales page', 'This domain is for sale. Inquire about this domain today.', True),
    ('a parking service', 'This webpage was generated by the domain owner using Sedoparking', True),
    # P3: `domain (?:is )?parked` never reached `This domain is currently parked`
    ('a domain parked at a registrar',
     'This domain is currently parked at gkg.net The domain EXAMPLEORG.ORG has been registered '
     'but currently does not have a website.', True),
    # P2
    ('a domain bound to no site',
     "Create a Website This domain isn't connected to a site If this domain is yours, head to the "
     'Domains page in your Wix dashboard.', True),
    # P1
    ('a builder placeholder',
     'example.org is coming soon This domain is managed at', True),
    ('an ordinary page', 'Welcome to our community center. We offer free legal help and ESL classes.',
     False),
]


@pytest.mark.parametrize('name,text,want', PARKED_PAGE_CASES, ids=[c[0] for c in PARKED_PAGE_CASES])
def test_a_placeholder_is_not_the_site(name, text, want):
    assert LA.is_parked(text) is want


def test_a_captcha_on_a_contact_form_is_not_a_wall():
    """Three live organization sites, a global health charity, a science museum and a cultural
    association, were reported unreachable because their contact form is protected by reCAPTCHA.
    `captcha` accounts for 9 of the 37 readable pages the shipped pattern converted."""
    live = _padded('Contact us. ',
                   'Send us a message and a caseworker will call you back within two working days. '
                   'This form is protected by reCAPTCHA and the Google Privacy Policy and Terms of '
                   'Service apply. Our office is open Monday to Friday, and walk-in hours for '
                   'immigration questions are on Wednesday afternoons.')
    assert len(live) >= LA.PAGE_IS_SUBSTANTIAL
    assert LA.is_wall(live) is False
    # the wording still decides on a page that carries nothing else
    assert LA.is_wall('Please complete the captcha to continue') is True


def test_a_challenge_interstitial_is_still_a_wall():
    """Both the vendor wording the pattern shipped with and the newer wording of the same vendors,
    which is the largest single addition at 239 rows over 221 sites."""
    assert LA.is_wall('Just a moment... Checking your browser before accessing') is True
    assert LA.is_wall(
        'philanthropy.org Performing security verification This website uses a security service to '
        'protect against malicious bots. This page is displayed while the website verifies you are '
        'not a bot. Ray ID: a1f914a53cf5e826') is True
    assert LA.is_wall('Before we continue... Press & Hold to confirm you are a human (and not a '
                      'bot). Reference ID 735deeaa-8668-11f1-a050-e4d3376c8350') is True
    # a challenge that resolved in the same read and left the real page behind it
    resolved = _padded('Checking the site connection security. This page requires cookies to be '
                       'enabled in your browser settings. ',
                       'Welcome to our organization. We serve immigrant families across the county '
                       'with legal help, English classes and case management, and our staff answer '
                       'the phone in four languages.')
    assert len(resolved) >= LA.PAGE_IS_SUBSTANTIAL
    assert LA.is_wall(resolved) is False


# Four immigrant-serving organizations each answer with a stale
# `403 - Forbidden` banner and then the organization's own site. A screen built from English
# site-furniture words called all four not-an-organization, which is precisely backwards for a
# package whose job is finding the non-English ones. The gate is on length so that it reads the
# same in every language.
BANNER = '403 - Forbidden Access to this page is forbidden. '
BEHIND_THE_BANNER = [
    ('Spanish',
     'Ofrecemos servicios gratuitos de asesoria legal para familias inmigrantes en todo el '
     'condado. Nuestro personal habla espanol y puede acompanarle a sus citas con el abogado. '
     'Las clases de ingles son gratuitas y se ofrecen por la manana y por la tarde.'),
    ('Korean',
     '저희 단체는 이민 가정을 위한 무료 '
     '법률 상담과 통역 서비스를 제공합'
     '니다. 상담은 예약 없이도 가능하며 '
     '한국어를 사용하는 상담원이 매주 '
     '화요일과 목요일에 사무실에 있습'
     '니다. 영어 수업은 무료로 운영됩니다.'),
    ('Portuguese',
     'Oferecemos apoio juridico gratuito para familias imigrantes e refugiadas em toda a regiao. '
     'A nossa equipa fala portugues e pode acompanhar as familias as consultas e as audiencias. '
     'As aulas de ingles sao gratuitas e acontecem de manha e ao final da tarde.'),
]


@pytest.mark.parametrize('lang,body', BEHIND_THE_BANNER, ids=[c[0] for c in BEHIND_THE_BANNER])
def test_a_stale_banner_over_a_whole_site_is_read_not_called_unreachable(lang, body):
    page = _padded(BANNER, body)
    assert len(page) >= LA.PAGE_IS_SUBSTANTIAL
    assert LA.is_wall(page) is False
    # the same banner with nothing behind it is a refusal, which is what W7 is for: the corpus says
    # `403 - Forbidden` and `don't`, neither of which the shipped `403 forbidden` reaches
    assert LA.is_wall(BANNER) is True
    assert LA.is_wall("Forbidden You don't have permission to access this resource.") is True


def test_the_gate_needs_the_whole_home_text_and_not_the_window():
    """Where the gate belongs, pinned. The search window is 600 characters and always has been; the
    gate is on the length of the whole read. A window of 600 characters can never reach 1,500, so a
    call site that sliced before calling would leave every gated alternative permanently open and
    put all 37 false positives back."""
    page = _padded(BANNER, BEHIND_THE_BANNER[0][1])
    assert LA.is_wall(page) is False
    assert LA.is_wall(page[:LA.WALL_WINDOW]) is True
    assert LA.WALL_WINDOW == 600 and LA.PARKED_WINDOW == 1200


REJECTED_CASES = [
    # a bare `404` token catches 163 sites and is wrong on 41: a live page printing the number in a
    # street address, a suite number, a footer or a help note. The adopted form needs not-found or
    # error wording next to the number AND a page under 300 characters, and neither of these two
    # gives it both.
    ('a live page whose street address holds the number',
     'Casa Buena. 404 East Main Street, Suite 12. Free English classes on Tuesday and Thursday '
     'evenings, and a legal clinic on the first Saturday of the month.', False),
    ('a live page mentioning a 404 error',
     'Resources for families. If a link on this page returns a 404 error, please tell us and we '
     'will fix it. Our legal clinic runs every Thursday, our English classes are free and open to '
     'anyone in the county, and our caseworkers can help with housing, school enrolment and work '
     'authorization paperwork. Call the office or come to the front desk during opening hours.',
     False),
    # a bare `forbidden` catches 113 and is wrong on 8
    ('an organization with forbidden in its name',
     'Forbidden Gate Chinese Cultural Center. Weekend language school, lion dance troupe and a '
     'senior lunch programme.', False),
    # ungated `coming soon` or `under construction` catches 390 and is wrong on 227, because 58
    # percent of what it reaches is a live page announcing something
    ('a live page announcing something coming soon',
     'We are bringing them back. Our trail programme is coming soon. Sign up to get priority '
     'access when registration opens, and see below for the classes running this month, the legal '
     'clinic hours and the volunteer rota for the food pantry.', False),
]


@pytest.mark.parametrize('name,text,want', REJECTED_CASES, ids=[c[0] for c in REJECTED_CASES])
def test_the_three_rejected_candidates_stay_rejected(name, text, want):
    assert (LA.is_wall(text) or LA.is_parked(text)) is want


def test_a_whole_page_placeholder_is_still_caught_under_its_gate():
    """The one surviving form of the under-construction family, at 200 characters."""
    assert LA.is_parked('Coming Soon') is True
    assert LA.is_parked('Site en construction. Website im Aufbau. Sito in costruzione. Website '
                        'Under Construction. Pagina web en construccion.') is True
    assert LA.PARKED_SOON_MAX == 200


def test_a_status_page_with_nothing_behind_it_is_unreachable():
    """The families the shipped pattern missed, each on the short page it is measured on."""
    assert LA.is_wall('502 Bad Gateway') is True
    assert LA.is_wall('Error establishing a database connection') is True
    assert LA.is_wall('Account Suspended This Account has been suspended. Contact your hosting '
                      'provider for more information.') is True
    assert LA.is_wall('Site not found This site is not published or does not have a domain '
                      'assigned to it.') is True
    assert LA.is_wall('Welcome to nginx! If you see this page, the nginx web server is '
                      'successfully installed and working.') is True
    assert LA.is_wall('404 Not Found') is True
    assert LA.is_wall('Sign in to continue to Gmail Email or phone Forgot email?') is True
    assert LA.is_parked('This domain has expired. If you owned this name, contact your '
                        'registration provider for assistance.') is True


# --------------------------------------------------------------------------------------------
# The reCAPTCHA boundary and the five alternatives that moved behind the length gate, 2026-08-01.
# Every count below is over the census render store, 44,284 capture rows carrying home text over
# 41,473 distinct sites, measured on the first ' || ' segment of the store's text column.
# --------------------------------------------------------------------------------------------

# The footer sentence every GoDaddy, Wix and Squarespace contact page prints. 67 rows of the corpus
# carry it in their first 600 characters and 63 of them were being called unreachable.
RECAPTCHA_FOOTER = ('This site is protected by reCAPTCHA and the Google Privacy Policy and Terms '
                    'of Service apply.')
FOOTER_ONLY_PAGES = [
    # a Bulgarian cultural center's contact page, 312 characters, the shortest of the 64
    ('a contact page of 312 characters',
     'Home Riverbend Cultural Center Bulgarian School More Contact Us DROP US A LINE! Name Email* '
     'Send ' + RECAPTCHA_FOOTER + ' Social Copyright 2026 Riverbend Bulgarian Cultural and Language '
     'Center Detelina - All Rights Reserved. Powered by Home'),
    # an Ethiopian mutual-aid association, 575 characters, whose home page names itself in Amharic.
    # The reading this page was losing is exactly the reading the package exists for.
    ('a home page in Amharic behind the same footer',
     'HIGHLAND ETHIOPIAN ASSOCIATION Contact Us Drop us a line! Name Email* SEND ' + RECAPTCHA_FOOTER
     + ' Copyright 2025 Highland Ethiopian Association - All Rights Reserved.'),
    # an education charity's contact page, 535 characters
    ('a contact page of 535 characters',
     'HOME ABOUT US WHERE WE SERVE PROJECTS DONATE NOW CONTACT GET IN TOUCH WITH US SEND US A '
     'MESSAGE Name* Email* Phone* SEND ' + RECAPTCHA_FOOTER + ' FRIENDS OF LEARNING, HONDURAS '
     'P.O. Box 341, Ashford, MO 64512, USA'),
]


@pytest.mark.parametrize('name,text', FOOTER_ONLY_PAGES, ids=[c[0] for c in FOOTER_ONLY_PAGES])
def test_a_recaptcha_footer_is_not_a_wall(name, text):
    """`captcha` with no word boundary matches inside `reCAPTCHA`, and the footer sentence above is
    boilerplate on an enormous number of ordinary contact pages. 87 corpus rows match `captcha`,
    18 match `\\bcaptcha`, and of the 69 that differ the 1,500-character gate released 5 and left 64
    rows over 64 sites unreachable at a median home read of 627 characters. Every one read by hand
    was a live organization page and none carried any other wall wording, so all 64 are released.
    These three are short on purpose: the gate cannot save a 312-character page."""
    assert len(text) < LA.PAGE_IS_SUBSTANTIAL
    assert LA.is_wall(text) is False
    assert LA.is_parked(text) is False


def test_a_captcha_field_on_a_contact_form_is_not_a_wall():
    """The bare word survives the boundary and is still furniture. Of the 18 rows that carry
    `captcha` as a word, ten are HugeDomains sales pages that `security check` already catches, one
    is a real bot wall, and three are live organization contact pages whose spam field is labelled
    CAPTCHA: one Spanish-language victim services agency twice and one faith-based ministry. The
    wall is the demand to solve one, not the word. The postal block below is invented and keeps the
    shape the capture carries, a box number, a city, a state and a five-digit ZIP."""
    contact_page = ('CasaVerde Donate P.O. Box 240718 Fairhaven, Missouri 65219 Office Hours '
                    'Monday - Friday 8am - 4pm Please call to schedule an appointment. No '
                    'walk-ins. Send a Message: Name* First Last Email* Phone Message* Privacy '
                    'Consent I accept the privacy policy CAPTCHA')
    assert len(contact_page) < LA.PAGE_IS_SUBSTANTIAL
    assert LA.CONTACT_POSTAL.search(contact_page), 'the invented block is still a postal address'
    assert LA.is_wall(contact_page) is False


def test_a_page_that_demands_a_captcha_is_still_a_wall():
    """A hospital system's site, the one genuine captcha wall in 44,284 pages, and the wording the
    shipped tests already used. The alternative that replaces the bare word catches this page and
    nothing else in the corpus."""
    real_wall = ('We apologize for the inconvenience... but your activity and behavior on this '
                 'site made us think that you are a bot. Please solve this CAPTCHA to request '
                 'unblock to the website.')
    assert len(real_wall) < LA.PAGE_IS_SUBSTANTIAL
    assert LA.is_wall(real_wall) is True
    assert LA.is_wall('Please complete the captcha to continue') is True


# The pages the five moved alternatives were converting. Each is a real capture; the Spanish two are
# the whole reason the gate exists, since a marker screen built from English site furniture cannot
# see either of them.
SURVIVORS = [
    # one legal advocacy site's /immigration, 4,000 characters: a wp.com challenge line, then a
    # faith-based charity's Spanish mission statement
    ('checking your browser over a Spanish site',
     'Checking your browser This will only take a few seconds... ',
     'Quienes somos Programas Ubicaciones Vision y Mision Caridades Buenaventura esta comprometida '
     'a poner de manifiesto el espiritu de Cristo, por medio de la colaboracion con comunidades '
     'diversas, la prestacion de servicios a personas de bajos recursos y que se encuentran en '
     'estados vulnerables, la fomentacion de la dignidad humana y la lucha por la justicia '
     'social. Ayuda para inmigrantes y refugiados.'),
    # one family services site, 2,761 characters: a stale 403 banner, then the organization's own
    # Spanish
    ('a 403 banner over a Spanish site',
     'Forbidden You do not have permission to access this document. Web Server at '
     'gdmig-example-org.example ',
     'Servicios Nuestra historia Noticias y Eventos Contactenos Apoyanos Centro Buenaventura '
     'Advocacy Services. Brindar servicios que empoderan y apoyan a familias e individuos en '
     'nuestra comunidad culturalmente diversa. Como agencia reconocida por la Oficina de '
     'Programas de Acceso Legal, brindamos servicios de inmigracion de bajo costo.'),
    # one Ukrainian scholarship organization, 4,000 characters: an ASP.NET stack trace from an
    # embedded login control, then the organization's site in Ukrainian
    ('a stack trace over a Ukrainian site',
     "Server Error in '/' Application. Object reference not set to an instance of an object. ",
     'Nasha orhanizatsiia dopomohla 350 ukrainskym talanovytym uchniam iz nezamozhnykh rodyn '
     'zdobuty stypendii do naykrashchykh shkil-pansioniv ta koledzhiv svitu. Zi svoho boku '
     'studenty zoboviazuiutsia povernutysia do Ukrainy na piat rokiv.'),
    # one community health center, 1,781 characters: the only row in the whole corpus that
    # `attention required` matches, and it is ordinary English prose
    ('attention required in a sentence',
     'Our providers focus on a smaller number of patients so they can give the time and '
     'attention required to build that trust. ',
     'Neighbourhood primary care, pediatric care, urgent visits, community health and telehealth. '
     'Because of the generosity of our donors, we are able to offer care to ALL families, '
     'regardless of their ability to pay.'),
    # one Ukraine relief foundation's /contact, 1,890 characters: a form plugin's notice below a
    # whole site
    ('a form asking for JavaScript',
     'Contact Us Now! Please enable JavaScript in your browser to complete this form. ',
     'The Buenaventura Foundation delivers medical aid, housing, education and hope to thousands '
     'affected by the conflict in Ukraine. The foundation is a registered fundraising '
     'organization in California. Every contribution directly impacts the lives of Ukrainian '
     'children.'),
]


@pytest.mark.parametrize('name,head,body', SURVIVORS, ids=[c[0] for c in SURVIVORS])
def test_a_banner_over_a_whole_site_is_read_after_the_five_moves(name, head, body):
    """`checking your browser`, `you do not have permission`, `server error`, `attention required`
    and `enable javascript` decided on their own until 2026-08-01. Each one's only catch above
    1,500 characters was a live organization page, so all five moved behind the gate. The moves
    release six rows over six sites and leave 1,004 catches in place."""
    page = _padded(head, body)
    assert len(page) >= LA.PAGE_IS_SUBSTANTIAL
    assert LA.is_wall(page) is False
    # the same wording with nothing behind it is still a wall
    assert LA.is_wall(head) is True


def test_the_moved_alternatives_are_still_waited_out_by_read():
    """WALL_RX is every alternative of both lists, ungated, and it is what `_read`'s challenge loop
    tests: a Cloudflare or wp.com interstitial is a wait of four times four seconds before the site
    is called unreadable, `_read_home` moves to the next candidate address on a hit, and
    `_plain_fetch` discards the body. Moving an alternative from the ungated list to the gated one
    must not change any of that, because only `is_wall` reads the gate. Pinned so a later move
    cannot quietly stop a challenge being waited out."""
    for wording in ('Checking your browser This will only take a few seconds...',
                    'Please enable JavaScript in your browser to complete this form.',
                    'Attention Required! Cloudflare',
                    "Server Error in '/' Application.",
                    'Forbidden You do not have permission to access this document.'):
        assert LA.WALL_RX.search(wording.lower()), wording
    # and each is out of the ungated list and in the gated one, which is where the gate reaches it
    for alt in ('checking your browser', 'enable javascript', 'attention required', 'server error',
                'you do not have permission'):
        assert alt not in LA.WALL_UNGATED_RX.pattern
        assert alt in LA.WALL_GATED_RX.pattern


def test_a_refusal_at_the_recorded_address_stays_unreachable():
    """`access denied` and `not authorized` did NOT move. One law school's immigration clinic page
    is the one page in the corpus either word reaches above 1,500 characters, and it is the
    university's own chrome around `Access denied. You are not authorized to access this page.` The
    clinic page was refused, like the refused legal-services site the rules
    settle as unreachable, so the two words keep their 72 and 3 rows. The name and the address below
    are invented and carry the shape of the chrome."""
    page = _padded('Riverbend College of Law Access denied Access denied You are not authorized to '
                   'access this page. ',
                   'CONTACT US Address 1420 North 18th Street Ashford IN 46512. About the College, '
                   'Prospective Student, Academics and Community, Clinics, Alumni, Career '
                   'Development. We prepare lawyers for public service.')
    assert len(page) >= LA.PAGE_IS_SUBSTANTIAL
    assert LA.is_wall(page) is True


# ------------------------------------------------------------------------------------------------
# The reader defects of the class-(c) review, 2026-08-04. Each is a real site's shape reduced to the
# smallest text that carries it; the sites are named beside the constants in core.py and the corpus
# counts are in measurement/studies/reader_fixes_20260804/.


def test_a_page_written_in_urdu_is_more_than_one_block():
    """The auxiliary reader counts blocks and split them on Latin punctuation alone.

    Urdu ends a sentence with U+06D4 and never with a full stop, so a whole Urdu page was ONE block
    however long it was and AUX_MIN_BLOCKS could never be met from it. The `/ur` pages of two South
    Asian family service organizations both read as nothing while their Gujarati, Tamil and Telugu
    siblings on the identical locale tree read correctly.
    """
    urdu = ('یہاں ہمارے ریفیوجی ریلیف سینٹر میں، ہم جانتے ہیں کہ بعض اوقات دنیا کو بدلنے کے لیے '
            'صرف ایک چھوٹی سی مدد کی ضرورت ہوتی ہے اور اسی یقین کے ساتھ ہم ہر روز کام کرتے ہیں۔ '
            'ہم ایک غیر منفعتی تنظیم ہیں جو پناہ گزینوں کو امریکہ میں آباد ہونے میں مدد دیتی ہے اور '
            'ان کے خاندانوں کے لیے تعلیم، رہائش اور صحت کی خدمات تک رسائی فراہم کرتی ہے۔ '
            'ہمارے رضاکار ہر ہفتے نئے آنے والوں سے ملتے ہیں اور ان کی اپنی زبان میں ان کی رہنمائی '
            'کرتے ہیں تاکہ وہ اپنے حقوق اور دستیاب خدمات کو بہتر طور پر سمجھ سکیں۔ ')
    old = re.split(r'\s+\|\|\s+|(?<=[.!?。？！])\s+', urdu)
    assert len(old) == 1, 'the old splitter saw one block in a page of Urdu sentences'
    blocks = [b for b in LA.AUX_SPLIT.split(urdu) if len(b) >= LA.AUX_MIN_BLOCK]
    assert len(blocks) >= LA.AUX_MIN_BLOCKS
    assert 'Urdu' in LA.languages_in(urdu, script_words=True)
    # neither floor moved; what changed is where a block ends
    assert (LA.AUX_MIN_BLOCK, LA.AUX_MIN_BLOCKS) == (140, 2)


def test_the_latin_sentence_rule_still_needs_whitespace_after_the_stop():
    """A decimal and a host name are not sentence ends, and splitting there would shorten real
    blocks under AUX_MIN_BLOCK. The script marks do not need the space, because none of them is
    written inside a number or a host name."""
    assert LA.AUX_SPLIT.split('Version 3.5 of the guide is at example.org and is free.') == [
        'Version 3.5 of the guide is at example.org and is free.']
    assert len(LA.AUX_SPLIT.split('Serve. Support.')) == 2
    assert len(LA.AUX_SPLIT.split('یہ پہلا جملہ ہے۔دوسرا جملہ')) == 2
    # and the Arabic QUESTION mark is deliberately not here: Persian asks with it too, and it split
    # one Iranian cultural association's Persian finely enough for two of langid's Urdu answers to
    # reach the floor
    assert len(LA.AUX_SPLIT.split('نظر شما چیست؟ما اینجا هستیم')) == 1


def test_the_arabic_script_is_named_when_the_letters_settle_it():
    """SCRIPT_FUNC's Arabic particles include ما and من, which are ordinary Persian words, so
    Persian prose fired the Arabic test and the page was reported Arabic. One Iranian cultural
    association publishes its mission at /fa and the reading dropped Persian and added Arabic on
    exactly that."""
    persian = ('انجمن فرهنگی ما (ICS) یک سازمان غیرانتفاعی، غیرسیاسی و غیر مذهبی است که به حفظ و '
               'ترویج میراث فرهنگی ما اختصاص دارد. ماموریت ما این است که مردم با پیشینه های مختلف '
               'را از طریق تجلیل از فرهنگ، موسیقی و هنر ایرانی متحد کنیم.')
    assert LA._arabic_language(persian) == 'Persian'
    assert 'Persian' in LA.languages_in(persian, script_words=True)
    assert 'Arabic' not in LA.languages_in(persian, script_words=True)

    arabic = 'نحن منظمة غير ربحية تقدم المساعدة القانونية للاجئين في هذه المدينة ومع كل العائلات.'
    assert LA._arabic_language(arabic) == 'Arabic'

    # ONE CANDIDATE OR NONE. One refugee translation service offers the same sentence in Pashto,
    # Persian, Sorani Kurdish and Arabic; naming any one of them takes the other three away, so
    # the script name is what the letters prove and is what the reading keeps.
    four = ('ژباړې لپاره د مرستې غوښتنه وکړئ تقاضای کمک برای ترجمه طلب مساعدة على الترجمة '
            'داوای یارمەتی وەرگێری بکە')
    assert LA._arabic_language(four) == 'Arabic'

    # and the language the letters cannot reach, excluded rather than guessed at
    uyghur = 'ئۇيغۇر مەدەنىيەت جەمئىيىتى ھۆججەت ۋە تەرجىمە مۇلازىمىتى تەمىنلەپ كېلىۋاتىدۇ.'
    assert LA._arabic_language(uyghur) == 'Arabic'


def test_a_block_carrying_pashto_letters_counts_for_pashto_as_well():
    """One refugee relief organization's `/ps` page is 798 characters of Pashto in two blocks, and
    langid answers `ps` on one and `fa` on the other, so Pashto stood at one block below
    AUX_MIN_BLOCKS and the page read as nothing. AUX_SCRIPT already requires one of the ten Pashto
    letters before a `ps` answer is believed, so a block carrying one is Pashto by the gate's own
    standard.

    It ADDS rather than renames. One Jewish family services agency runs a Persian helpline line and
    a Pashto one in the same block, and a rename took Persian off a page that publishes in it.
    """
    pashto = 'زموږ کلتوري ټولنې ته ډالۍ د مالیې څخه معاف دي او زموږ د سلنه رضاکار ټیم لخوا'
    assert LA._aux_names('ps', pashto) == ['Pashto']
    assert LA._aux_names('fa', pashto) == ['Persian', 'Pashto']
    assert LA._aux_names('ur', pashto) == ['Urdu', 'Pashto']
    # a Persian block with no Pashto letter in it is Persian and only Persian
    assert LA._aux_names('fa', 'ما یک سازمان غیرانتفاعی هستیم که به خانواده ها کمک می کنیم') == \
        ['Persian']
    # and the Sorani rename still consumes its host, because langid has no Sorani model at all
    assert LA._aux_names('fa', 'ئێمە ڕێکخراوێکی ناحکومی بێ قازانجین') == ['Kurdish']


def test_a_skip_link_selector_only_reaches_a_link():
    """WordPress block themes put `id="wp--skip-link--target"` on the `<main>` element that wraps
    the whole page, because that is where the skip link jumps TO. Written without the `a`,
    `[id*="skip-link"]` matched it, `_main_text` hid the entire document and returned the empty
    string, and every page of such a site read as nothing at all. Six of the 353 stored captures of
    the 2026-08-03 re-read carry the id and all six reported no language whatever, English included;
    one Burmese community organization publishes a fundraising notice in Burmese and Malay and read
    `english_only`.
    """
    skip = [s.strip() for s in LA.CHROME_SEL.split(',') if 'skip' in s]
    assert len(skip) == 4
    for sel in skip:
        assert sel.startswith('a['), (
            '%s reaches any element carrying the word, and a skip-link TARGET is the element that '
            'wraps the page' % sel)
    assert 'a[class*="skip-link"]' in LA.CHROME_SEL
    assert 'a[id*="skip-to"]' in LA.CHROME_SEL


def test_an_unterminated_style_element_is_not_prose():
    """`<style>` opens a raw-text element, so a document that never closes it has no more text in
    it. The paired substitution needs the closing tag to remove anything, so the stylesheet came out
    as prose and langid called it Zulu on ten captures of the census render store, all of them near
    97,000 characters. Two of them are a high school and a foundation whose browser
    text is empty, so the plain-HTTP rescue is the only reading they have."""
    page = ('<html><head><title>Riverbend School</title></head><body><p>Welcome to our school.</p>'
            '<style>@charset "UTF-8"; @import url("https://fonts.googleapis.com/css2?family=Rob");'
            ' .site-header{-webkit-transition:all .3s ease;color:#222}')
    got = LA._text_from_html(page)
    assert 'Welcome to our school.' in got
    assert 'webkit-transition' not in got and '@import' not in got
    # a terminated one is removed as it always was, and the text after it survives
    closed = '<html><body><p>One</p><style>.a{color:red}</style><p>Two</p></body></html>'
    assert LA._text_from_html(closed).split() == ['One', 'Two']


# ---------------------------------------------------------------- the tag stripper, 2026-08-05
#
# `<[^>]+>` stops at the first `>` in the document, and HTML says a `>` inside a QUOTED attribute
# value is an ordinary character, so the rest of that element's own start tag came out of the reader
# as text. It fired on 50 of 1,365 live sites. Every case below is a known answer taken from the
# HTML5 tokenizer's tag-consumption states rather than from what this implementation happens to do.


def test_a_greater_than_inside_a_quoted_attribute_does_not_end_the_tag():
    """The defect, in the shape Squarespace writes it: section JSON in `data-current-styles`, one of
    whose values is a CSS selector with a child combinator in it."""
    leak = '<div data-styles="{ &quot;w&quot;: &quot;a>b&quot; }" class="x">hello</div>'
    assert LA._text_from_html(leak) == 'hello'
    single = ("<section data-current-styles='{\"selector\":\".bg > img\"}' class=y>"
              'Casa Buena</section>')
    assert LA._text_from_html(single) == 'Casa Buena'
    # the same character in a value the tag never quoted still ends the tag, as it does in a browser
    assert LA._text_from_html('<a href=/x?a=b>go</a>') == 'go'
    assert LA._text_from_html('<a href = "a>b" title=c>d</a>') == 'd'
    # a quote that opens no value is part of an attribute NAME, and the `>` after it ends the tag
    assert LA._text_from_html('<a "b>c" d>e</a>') == 'c" d>e'


def test_a_less_than_that_opens_no_tag_is_text():
    """`<[^>]+>` ate `< 18 and staff >` out of a sentence. A `<` an ASCII letter, `/`, `!` or `?`
    does not follow opens nothing, which is what a browser does with it."""
    assert LA._text_from_html('<p>3 < 5 > 1 yes</p>') == '3 < 5 > 1 yes'
    assert LA._text_from_html('<p>ages &lt; 18</p>') == 'ages < 18'


def test_the_pieces_of_a_document_that_are_not_elements():
    """A comment, a doctype and a processing instruction are removed and take nothing with them."""
    assert LA._text_from_html('<!-- <script> --><p>Kept</p>') == 'Kept'
    assert LA._text_from_html('<!DOCTYPE html><p>Doc</p>') == 'Doc'
    assert LA._text_from_html('<p>u</p><?xml version="1.0"?><p>v</p>') == 'u\nv'
    assert LA._text_from_html('<p>x</p><!--never closed') == 'x'


def test_a_raw_text_element_ends_where_a_browser_ends_it():
    """`</style >` and `</style/>` close the element, which the pattern this replaces did not
    accept, so everything after one was read as stylesheet. `<scriptural>` is not `<script>`."""
    assert LA._text_from_html('<p>A</p><style >.a{b}</style ><p>B</p>').split() == ['A', 'B']
    assert LA._text_from_html('<script>a</script >after') == 'after'
    assert LA._text_from_html('<script src="a>b.js"></script><p>ok</p>') == 'ok'
    assert LA._text_from_html('<p>keep</p><scriptural>notraw</scriptural>').split() == \
        ['keep', 'notraw']


def test_a_line_break_is_a_line_break_whatever_the_tag_carries():
    """`<br class="x">` is the same break as `<br>`. The pattern this replaces required the tag to
    end right after the name, so an attribute on it turned the break into a space and joined two
    lines the reader sees apart."""
    assert LA._text_from_html('<p>a<br>b</p>') == 'a\nb'
    assert LA._text_from_html('<p>a<br class="x">b</p>') == 'a\nb'
    assert LA._text_from_html('<p>a<br />b</p>') == 'a\nb'


def _timed(fn, arg):
    t = time.perf_counter()
    fn(arg)
    return time.perf_counter() - t + 1e-9


def test_the_stripper_is_linear_in_the_document():
    """This runs on every page of every site, so a stripper that backtracks is a stripper that
    stalls on one pathological capture. Not a wall-clock assertion, which would be flaky on a
    contended machine: the shape being held is that ten times the document is about ten times the
    work and not a hundred times it."""
    unit = ('<section data-current-styles="{&quot;selector&quot;:&quot;.bg > img&quot;}" '
            'class="page-section"><p>Casa Buena acompana a las familias.</p></section>')

    def cost(n):
        doc = '<html><body>' + unit * n + '</body></html>'
        return min(_timed(LA._text_from_html, doc) for _ in range(3))

    small, large = cost(200), cost(2000)
    assert large < small * 30, (
        'ten times the document cost %.1f times the work, which is not linear' % (large / small))


# ---------------------------------------------------------------- somebody else's feed, removed
#
# The prose below is invented and no real account's posts are reproduced. What the tests assert is
# which ELEMENT goes, which is the whole of what the rule looks at.
_FEED_SPANISH = ('Gracias a todos los que vinieron a nuestra fiesta en el parque; fue una tarde '
                 'muy bonita para cada familia de nuestra comunidad y para todos los que nos '
                 'ayudaron desde temprano hasta el final de la jornada.')
_FEED_ENGLISH = ('Our centre helps families with school enrolment, housing questions and legal '
                 'appointments every weekday morning at the front desk.')


def _wrapped(open_tag, tag):
    return ('<html><body><p>' + _FEED_ENGLISH + '</p>' + open_tag + '<p>' + _FEED_SPANISH
            + '</p></' + tag + '></body></html>')


@pytest.mark.parametrize('open_tag,tag', [
    ('<div id="sb_instagram">', 'div'),
    ('<div class="sbi_item">', 'div'),
    ('<li class="cff-item">', 'li'),
    ('<div id="cff">', 'div'),
    ('<div class="powr-social-feed">', 'div'),
    ('<div class="juicer-feed">', 'div'),
    ('<div class="elfsight-app-3f2a1b4c">', 'div'),
    ('<div class="widget sk-ww-instagram-feed">', 'div'),
    ('<blockquote class="instagram-media">', 'blockquote'),
    ('<iframe src="https://www.facebook.com/plugins/page.php?href=x">', 'iframe'),
    ('<iframe src="https://www.instagram.com/p/AbCd/embed">', 'iframe'),
])
def test_a_feed_container_leaves_before_the_text_is_read(open_tag, tag):
    """Every container in the five lists, each holding a member's post in another language."""
    doc = _wrapped(open_tag, tag)
    assert 'Spanish' in LA.languages_in(LA._text_from_html(doc)), (
        'this case would pass on a document with no Spanish in it at all')
    assert 'Spanish' not in LA.languages_in(LA._page_text(doc))
    assert 'English' in LA.languages_in(LA._page_text(doc)), 'the page itself survived'


def test_a_feed_container_that_is_never_closed_leaves_the_document_alone():
    """The failure this refuses is the one `_main_text` already met from the other direction: an
    element with no end tag would otherwise take every byte after it and the page reads as nothing."""
    doc = ('<html><body><div class="sbi_item"><p>' + _FEED_SPANISH + '</p><p>' + _FEED_ENGLISH
           + '</p></body></html>')
    assert LA._without_feeds(doc) == doc
    assert 'English' in LA.languages_in(LA._page_text(doc))


def test_a_feed_container_closes_at_its_own_end_tag_and_not_the_first_one():
    """A container holds elements of its own name, and a scanner that stopped at the first `</div>`
    would leave half the feed in the text and take half the page out with the other half."""
    doc = ('<html><body><div id="sb_instagram"><div class="post"><p>' + _FEED_SPANISH
           + '</p></div></div><p>' + _FEED_ENGLISH + '</p></body></html>')
    out = LA._page_text(doc)
    assert _FEED_SPANISH.split()[0] not in out
    assert _FEED_ENGLISH.split()[0] in out


def test_a_document_with_no_feed_marker_is_read_exactly_as_it_was():
    """The cheap refusal, and the promise that this changes nothing on the pages it is not about."""
    doc = '<html><body><p>' + _FEED_ENGLISH + '</p><p>' + _FEED_SPANISH + '</p></body></html>'
    assert LA._without_feeds(doc) == doc
    assert LA._page_text(doc) == LA._text_from_html(doc)


def test_a_feed_container_is_found_through_an_attribute_that_carries_a_greater_than():
    """The shape the tag stripper was rewritten for, asked of the container scan as well."""
    doc = ('<html><body><p>' + _FEED_ENGLISH + '</p>'
           '<div data-styles="{&quot;sel&quot;:&quot;.a > b&quot;}" class="sbi_item"><p>'
           + _FEED_SPANISH + '</p></div></body></html>')
    assert 'Spanish' not in LA.languages_in(LA._page_text(doc))


def test_the_feed_scan_is_linear_in_a_document_that_never_closes_one():
    """The shape that made the first version quadratic, held so it cannot come back.

    A container the document never closes used to be searched for to the end of the document, and
    the next one searched the same tail again: 0.02 seconds for 200 of them against 2.10 for 2,000,
    ten times the document for a hundred times the work. Not a wall-clock assertion, which would be
    flaky on a contended machine; the shape held is that ten times the document is about ten times
    the work.
    """
    unit = '<div class="sbi_item"><p>A member post of ordinary length sits here.</p>'

    def cost(n):
        doc = '<html><body>' + unit * n + '</body></html>'
        return min(_timed(LA._without_feeds, doc) for _ in range(3))

    small, large = cost(200), cost(2000)
    assert large < small * 30, (
        'ten times the document cost %.1f times the work, which is not linear' % (large / small))
    # and the document is still whole, because none of those containers was ever closed
    doc = '<html><body>' + unit * 3 + '</body></html>'
    assert LA._without_feeds(doc) == doc


def test_a_feed_container_an_ancestor_closes_first_is_left_alone():
    """Malformed the other way: the container is still open when its parent's end tag arrives. It
    is popped with no end of its own, so no cut is recorded and the page keeps its bytes."""
    doc = ('<html><body><section><div class="sbi_item"><p>' + _FEED_SPANISH
           + '</p></section><p>' + _FEED_ENGLISH + '</p></body></html>')
    assert LA._without_feeds(doc) == doc


# The site builder's own furniture, invented in the shape the platform renders. The prose inside
# the containers is written for this file and names no organization; the five sentences in
# PLACEHOLDER_TEXT are the platform's own interface strings and are quoted from the constant rather
# than retyped, so a change to that tuple cannot leave this test passing against the old wording.
_OWN_SPANISH = ('Nuestro centro comunitario ofrece asesoria legal gratuita a las familias que '
                'llegaron hace poco al condado, y nadie tiene que pagar por la consulta.')
_PAGE_ENGLISH = ('Welcome to our office on Maple Street, where we help families with legal '
                 'questions every day of the week and nobody has to pay for a first visit.')


def _builder_page(open_tag, body):
    """One builder container, opened with `open_tag` and properly closed, inside an English page."""
    return ('<html><body><p>' + _PAGE_ENGLISH + '</p>' + open_tag + '<div>' + body
            + '</div></div></body></html>')


def test_a_site_builders_empty_state_is_not_the_organizations_writing():
    """A builder ships its interface in every language it supports, so a locale page renders the
    builder's strings whether or not the organization has written anything. The container is what
    is matched, never the content, so this works in every language the builder ships."""
    doc = _builder_page('<div data-hook="empty-state-container">', _OWN_SPANISH)
    out = LA._page_text(doc)
    assert _OWN_SPANISH.split()[0] not in out
    assert _PAGE_ENGLISH.split()[0] in out
    assert LA.languages_in(out, aux=False) == ['English']


def test_the_members_dialog_container_goes_the_same_way():
    """The second hook, on the sign-up dialog a members page renders when nobody is signed in. On
    one organization of the design set the whole of two pages was this dialog."""
    doc = _builder_page('<div data-testid="siteMembersDialogLayout">', _OWN_SPANISH)
    assert _OWN_SPANISH.split()[0] not in LA._page_text(doc)


def test_the_sentence_list_is_the_second_line_when_the_hook_is_absent():
    """A server document rendered without the attribute, or a builder that renames it. The sentence
    list is applied to the TEXT and carries only the wording a stored page attests."""
    sentences = ' '.join(LA.PLACEHOLDER_TEXT)
    doc = '<html><body><p>' + _PAGE_ENGLISH + '</p><p>' + sentences + '</p></body></html>'
    out = LA._page_text(doc)
    for t in LA.PLACEHOLDER_TEXT:
        assert t not in out, t
    assert _PAGE_ENGLISH.split()[0] in out
    assert LA.languages_in(out, aux=False) == ['English']
    # and a line break where the browser puts one does not save it
    broken = LA.PLACEHOLDER_TEXT[0].replace(' ', chr(10) + '   ')
    assert LA._without_placeholder_text(broken).strip() == ''


def test_the_organizations_own_spanish_survives_the_strip():
    """The direction that costs a reading if it is got wrong. The page of the design set this was
    written for publishes in Spanish on its front door and renders the builder's empty state on its
    blog, and only the second goes."""
    doc = ('<html><body><div data-hook="empty-state-container"><div>' + LA.PLACEHOLDER_TEXT[0]
           + '</div></div><p>' + _OWN_SPANISH + '</p></body></html>')
    out = LA._page_text(doc)
    assert LA.PLACEHOLDER_TEXT[0] not in out
    assert _OWN_SPANISH.split()[0] in out
    assert LA.languages_in(out, aux=False) == ['Spanish']


def test_the_two_readers_remove_the_same_placeholder_containers():
    """The property the feed pair states and the only thing that keeps a live reading and a
    re-judge of the stored bytes comparable: one list, two readers."""
    for h in LA.PLACEHOLDER_HOOK:
        assert '[data-hook="%s"]' % h in LA.PLACEHOLDER_SEL
        assert LA._is_placeholder_element('div', 'data-hook="%s"' % h)
        assert LA._is_placeholder_element('div', 'DATA-HOOK="%s"' % h.upper())
    for t in LA.PLACEHOLDER_TESTID:
        assert '[data-testid="%s"]' % t in LA.PLACEHOLDER_SEL
        assert LA._is_placeholder_element('div', 'data-testid="%s"' % t)
    assert not LA._is_placeholder_element('div', 'class="empty-state-container"')
    doc = '<html><body><div data-hook="empty-state-container">x</div></body></html>'
    assert LA._without_placeholders(doc) != doc
    assert LA._without_feeds(doc) == doc          # the two families are separate lists


def test_a_document_with_no_placeholder_marker_is_read_exactly_as_it_was():
    doc = '<html><body><div class="ordinary"><p>' + _OWN_SPANISH + '</p></div></body></html>'
    assert LA._without_placeholders(doc) == doc


def test_every_placeholder_sentence_is_attested_and_none_is_translated():
    """The capture holds one organization's Spanish locale pages and no other locale of the same
    site, so Spanish is the only wording this package can quote. The English and French forms the
    builder also ships are deliberately absent rather than guessed, and the container strip above is
    what carries them."""
    assert len(LA.PLACEHOLDER_TEXT) == 5
    for t in LA.PLACEHOLDER_TEXT:
        assert LA.languages_in(t * 4, aux=False) in ([], ['Spanish']), t


def test_a_script_inside_a_feed_container_does_not_close_it():
    """`</div>` inside a script is a string. A scanner that read it as an end tag would cut the
    container short and leave the posts after it in the text."""
    doc = ('<html><body><div class="sbi_item"><script>var t = "</div>";</script><p>'
           + _FEED_SPANISH + '</p></div><p>' + _FEED_ENGLISH + '</p></body></html>')
    out = LA._page_text(doc)
    assert _FEED_SPANISH.split()[0] not in out
    assert _FEED_ENGLISH.split()[0] in out


def test_the_browser_selector_and_the_byte_reader_name_the_same_containers():
    """One list and two readers. A container named to the browser and not to the stored bytes would
    be removed from the text the class is read off and left in the document the authorship test
    re-reads, which puts one finding on two sides of one question."""
    for marker in (LA.FEED_ID + LA.FEED_CLASS + LA.FEED_CLASS_PREFIX + LA.FEED_IFRAME_SRC
                   + LA.FEED_BLOCKQUOTE_CLASS):
        assert marker in LA.FEED_SEL, '%s is not in the selector the browser is handed' % marker
        assert LA._FEED_HINT.search(marker), '%s is not in the prefilter' % marker
    assert LA._is_feed_element('div', ' id="sb_instagram"')
    assert LA._is_feed_element('div', ' class="foo sbi_item bar"')
    assert not LA._is_feed_element('div', ' class="sbi_items"'), 'a class token is a whole token'
    assert not LA._is_feed_element('div', ' src="https://www.instagram.com/p/x/embed"'), (
        'the iframe source names a container only on an iframe')


def test_a_re_judged_capture_reads_the_feed_out_too():
    """The capture keeps the feed, because `page.content()` is taken before the DOM strip. A
    re-judge that did not take it out again would read a language off the stored bytes that the
    live audit never saw, and the two would disagree on a site neither had changed."""
    doc = _wrapped('<div id="sb_instagram">', 'div')
    record = {'url': 'https://feed.example/', 'verdict': 'english_only', 'languages': ['English'],
              'evidence': [], 'pages': {'https://feed.example/': doc}}
    r = LA.rejudge(record)
    assert r.verdict == 'english_only'
    assert 'Spanish' not in r.languages


# ---------------------------------------------- the translation widget, on both sides of one line
#
# WIDGET_SEL has always been handed to the browser and the widget's furniture has always come out of
# the DOM before the browser text was read. What did not happen until 0.2.0 is the same removal on
# the BYTES, and `_page_text` is now the reading on both sides of the live/stored line, so the
# omission was a disagreement between two readers of one page: the store keeps `page.content()`
# taken before the strip, a Google Translate menu of language autonyms is in that document, and a
# re-judge read it as the site's own content.
_WIDGET_EN = ('Our centre helps families with legal questions, housing and school enrolment every '
              'day of the week, and the first appointment is free of charge.')
_WIDGET_RU = ('Наша организация каждую неделю предоставляет бесплатную юридическую помощь семьям '
              'иммигрантов, и мы не спрашиваем вас о вашем статусе в этой стране.')


def _widget_wrapped(open_tag, tag):
    return ('<html><body><p>' + _WIDGET_EN + '</p>' + open_tag + '<p>' + _WIDGET_RU
            + '</p></' + tag + '></body></html>')


@pytest.mark.parametrize('open_tag,tag', [
    ('<div id="google_translate_element">', 'div'),
    ('<div class="goog-te-menu-frame">', 'div'),
    ('<div class="goog-te-menu2">', 'div'),
    ('<div class="skiptranslate">', 'div'),
    ('<div class="gtranslate_wrapper">', 'div'),
    ('<div class="gt_switcher">', 'div'),
    ('<div class="country-selector weglot_here">', 'div'),
    ('<div id="weglot-container">', 'div'),
    ('<div class="conveythis-widget">', 'div'),
    ('<div id="conveythis-1">', 'div'),
])
def test_the_widgets_own_furniture_leaves_the_bytes_as_well_as_the_dom(open_tag, tag):
    """Every clause of WIDGET_SEL, each holding a menu's worth of another language."""
    doc = _widget_wrapped(open_tag, tag)
    assert 'Russian' in LA.languages_in(LA._text_from_html(doc)), (
        'this case would pass on a document with no Russian in it at all')
    assert 'Russian' not in LA.languages_in(LA._page_text(doc))
    assert 'English' in LA.languages_in(LA._page_text(doc)), 'the page itself survived'


def test_the_widget_selector_and_the_byte_reader_name_the_same_furniture():
    """One list and two readers, the way the feed containers are one list. A vendor named to the
    browser and not to the bytes is a menu the live audit removes and a re-judge of the same
    capture reads."""
    for marker in LA.WIDGET_ID + LA.WIDGET_CLASS + LA.WIDGET_SUBSTRING:
        assert marker in LA.WIDGET_SEL, '%s is not in the selector the browser is handed' % marker
        assert LA._WIDGET_HINT.search(marker), '%s is not in the prefilter' % marker
    assert LA._is_widget_element('div', ' id="google_translate_element"')
    assert LA._is_widget_element('div', ' class="foo skiptranslate bar"')
    assert not LA._is_widget_element('div', ' class="skiptranslated"'), (
        'a class in WIDGET_CLASS is a whole token, which is what `.skiptranslate` means')
    # and the two substring vendors are substrings on purpose, in either attribute
    assert LA._is_widget_element('div', ' class="weglot-container"')
    assert LA._is_widget_element('aside', ' id="conveythis-widget-1"')


def test_a_re_judged_capture_reads_the_widget_furniture_out_too():
    """The capture keeps the menu, because `page.content()` is taken before the DOM strip. This is
    the disagreement 0.2.0 removes: the same bytes now read the same way live and re-judged."""
    doc = _widget_wrapped('<div id="google_translate_element">', 'div')
    record = {'url': 'https://widget.example/', 'verdict': 'english_only',
              'languages': ['English'], 'evidence': [],
              'pages': {'https://widget.example/': doc}}
    r = LA.rejudge(record)
    assert 'Russian' not in r.languages


# ------------------------------------------- a quoted testimonial, out of the count and on the record
#
# The prose below is invented and no real testimonial is reproduced. What the tests assert is which
# ELEMENT the text was in, which is the whole of what the rule looks at. Every container named here
# is one the stored markup of the two captures shows; the block above `TESTIMONIAL_RX` in core.py
# says which site each came from and why three proposed words are not in the list.
_QUOTED_SPANISH = ('Gracias a todas las personas de este centro por la ayuda que nos dieron '
                   'cuando llegamos a la ciudad sin conocer a nadie; nos acompanaron a la '
                   'escuela de los ninos y no nos dejaron solos en ningun momento.')
_QUOTED_ENGLISH = ('Our centre helps families with school enrolment, housing questions and legal '
                   'appointments every weekday morning at the front desk.')


def _quoted(open_tag, tag):
    return ('<html><body><p>' + _QUOTED_ENGLISH + '</p>' + open_tag + '<p>' + _QUOTED_SPANISH
            + '</p><p>- Yolanda</p></' + tag + '></body></html>')


@pytest.mark.parametrize('open_tag,tag', [
    ('<blockquote>', 'blockquote'),
    ('<q>', 'q'),
    ('<div class="testimonial-card">', 'div'),
    ('<div class="testimonials-grid">', 'div'),
    ('<section id="testimonials">', 'section'),
    ('<div class="elementor-testimonial__text">', 'div'),
    ('<div class="et_pb_testimonial_description">', 'div'),
    ('<div class="ui-e-testimonial-text">', 'div'),
    ('<div class="board-vol-testimonial animate-in">', 'div'),
    ('<div class="testimonial-marquee-wrap">', 'div'),
    ('<div class="type-testimonial">', 'div'),
    ('<div class="avia-grid-testimonials">', 'div'),
    ('<aside class="widget widget-reviews">', 'aside'),
    ('<div class="cff-all-reviews">', 'div'),
])
def test_a_quoted_container_leaves_the_counted_text(open_tag, tag):
    """Every shape the two captures show, each holding a visitor's testimonial in another
    language. The page's own English paragraph survives every one of them."""
    doc = _quoted(open_tag, tag)
    assert 'Spanish' in LA.languages_in(LA._text_from_html(doc)), (
        'this case would pass on a document with no Spanish in it at all')
    assert 'Spanish' not in LA.languages_in(LA._page_text(doc))
    assert 'English' in LA.languages_in(LA._page_text(doc)), 'the page itself survived'


@pytest.mark.parametrize('open_tag,tag', [
    ('<blockquote>', 'blockquote'),
    ('<div class="testimonial-card">', 'div'),
    ('<aside class="widget widget-reviews">', 'aside'),
])
def test_a_quoted_container_is_recorded_at_rung_one_and_attributed_to_nobody(open_tag, tag):
    """Taken out of the count is not taken off the record. The row names the language and the
    address, carries the rung the codebook gives a quoted testimonial, and carries no authorship,
    because that axis says who produced the text and has no value for a visitor's words."""
    doc = _quoted(open_tag, tag)
    ev = LA.testimonial_evidence('https://quoted.example/', doc)
    assert [(e.mechanism, e.language, e.sufficiency, e.authorship) for e in ev] == [
        (LA.MECH_TESTIMONIAL, 'Spanish', LA.SUFF_TOKEN, LA.AUTHOR_NONE)]
    assert _QUOTED_SPANISH.split()[0] in ev[0].quote
    assert ev[0].url == 'https://quoted.example/'
    assert ev[0].rules == [], 'no classification rule counts it, so it names none'


def test_the_english_inside_a_quoted_container_is_not_recorded_either():
    """`Result.evidence` never receives a piece of English evidence and a quotation is not the
    exception: an English testimonial is out of the counted text and carries no row."""
    doc = ('<html><body><p>' + _QUOTED_ENGLISH + '</p><div class="testimonial-card"><p>'
           + _QUOTED_ENGLISH + ' It changed everything for our family.</p></div></body></html>')
    assert LA.testimonial_evidence('https://quoted.example/', doc) == []


def test_a_quotation_cannot_count_towards_a_verdict():
    """Three constructions hold it out of the count and this asserts all three, because a rule
    that suppresses a reading has to be unable to create one."""
    assert LA.MECH_TESTIMONIAL not in LA.OWN_MECHANISMS
    assert LA.MECH_SUFFICIENCY[LA.MECH_TESTIMONIAL] == LA.SUFF_TOKEN
    assert LA.SUFF_TOKEN < LA.SUFFICIENCY_COUNTS
    row = LA.Evidence(LA.MECH_TESTIMONIAL, 'https://quoted.example/', _QUOTED_SPANISH, 'Spanish',
                      authorship=LA.AUTHOR_NONE, sufficiency=LA.SUFF_TOKEN)
    assert LA.counted_evidence([row], '') == []
    assert LA.sufficiency_of(row) == LA.SUFF_TOKEN
    assert LA.authorship_of(row, '') == LA.AUTHOR_NONE, (
        'a recorded authorship wins, so the row cannot lift a site up the axis')
    assert LA.verdict_for([row], '') == 'english_only'


def test_a_word_inside_a_longer_word_is_not_a_container():
    """`preview` is not a review, and that is why the rule is a pattern and not a CSS selector:
    ten class tokens of the 72-site capture carry `preview` and none of them is a testimonial."""
    for cls in ('ios-preview-native-scroll', 'wplinkpreview-description', 'audio-preview',
                'fw-preview-button', 'preview_content', 'big-preview', 'reviewer-photo',
                'tweak-quote-block-alignment-center', 'modern-quote', 'icon-quote-right'):
        assert not LA._is_quoted_element('div', ' class="%s"' % cls), (
            '%s is not a container a testimonial is published in' % cls)
    for cls in ('testimonial-card', 'elementor-testimonial__text', 'et_pb_testimonial_1',
                'insurancehome_section5_testimonial', 'testimonials', 'widget-reviews',
                'TESTIMONIAL-CARD'):
        assert LA._is_quoted_element('div', ' class="%s"' % cls), (
            '%s is a container the corpus shows' % cls)


def test_the_document_itself_is_never_a_quotation():
    """The guard that keeps a theme's style setting from taking the whole page. Squarespace writes
    its site-wide settings onto the body element, and without this the word rule took the entire
    document off every Squarespace site of the 72-site capture, one of them an organization
    publishing help pages in eight languages."""
    attrs = ' class="tweak-testimonial-alignment-center"'
    for tag in LA.QUOTED_NEVER:
        assert not LA._is_quoted_element(tag, attrs), '%s is the document, not a part of it' % tag
    assert LA._is_quoted_element('div', attrs), 'the same class on a div is still a container'


def test_a_link_to_a_page_of_testimonials_is_not_a_container():
    """The attribute is read from `class` and `id` and from nowhere else. An anchor pointing at a
    page of reviews is navigation, and a wrapper naming a record in a data attribute is drawing
    the quotation rather than being it."""
    assert not LA._is_quoted_element('a', ' href="/reviews/"')
    assert not LA._is_quoted_element('div', ' data-testimonial-id="4182"')


def test_a_figure_is_a_quotation_only_when_it_names_who_is_quoted():
    """A `<figure>` is equally how a photograph and a code listing are published, so the `<cite>`
    inside it is what makes this one a quotation."""
    with_cite = ('<html><body><p>' + _QUOTED_ENGLISH + '</p><figure><p>' + _QUOTED_SPANISH
                 + '</p><figcaption><cite>Yolanda P.</cite></figcaption></figure></body></html>')
    without = ('<html><body><p>' + _QUOTED_ENGLISH + '</p><figure><p>' + _QUOTED_SPANISH
               + '</p><figcaption>A summer afternoon in the park</figcaption>'
                 '</figure></body></html>')
    assert 'Spanish' not in LA.languages_in(LA._page_text(with_cite))
    assert 'Spanish' in LA.languages_in(LA._page_text(without))


def test_a_cite_names_the_nearest_figure_and_not_every_one():
    """The inner figure's cite is the inner figure's, which is what the stack answers and what a
    search for the outermost ancestor would get wrong."""
    doc = ('<html><body><figure><p>' + _QUOTED_ENGLISH + '</p><figure><p>' + _QUOTED_SPANISH
           + '</p><cite>Yolanda P.</cite></figure></figure></body></html>')
    out = LA._page_text(doc)
    assert _QUOTED_SPANISH.split()[0] not in out
    assert _QUOTED_ENGLISH.split()[0] in out


def test_a_quoted_container_that_is_never_closed_leaves_the_document_alone():
    """The same refusal `_without_feeds` makes: a container with no end tag would otherwise take
    every byte after it and the page would read as nothing."""
    doc = ('<html><body><div class="testimonial-card"><p>' + _QUOTED_SPANISH + '</p><p>'
           + _QUOTED_ENGLISH + '</p></body></html>')
    assert LA._without_testimonials(doc) == doc
    assert 'English' in LA.languages_in(LA._page_text(doc))


def test_a_document_with_no_quotation_marker_is_read_exactly_as_it_was():
    doc = '<html><body><p>' + _QUOTED_ENGLISH + '</p></body></html>'
    assert LA._without_testimonials(doc) == doc
    assert LA._testimonial_blocks(doc) == []


def test_a_container_inside_a_container_is_recorded_once():
    """A wrapper holding two quotations is one quotation region. Overlapping rows would say the
    page carried several findings where it carries one shape."""
    doc = ('<html><body><section id="testimonials"><blockquote><p>' + _QUOTED_SPANISH
           + '</p></blockquote><blockquote><p>' + _QUOTED_SPANISH
           + '</p></blockquote></section><p>' + _QUOTED_ENGLISH + '</p></body></html>')
    assert len(LA._testimonial_blocks(doc)) == 1
    assert _QUOTED_ENGLISH.split()[0] in LA._page_text(doc)


def test_a_quotation_inside_somebody_elses_feed_is_read_as_the_feed():
    """The feed containers go first, so a testimonial slider rendered inside an embedded feed is
    not recorded twice under two mechanisms."""
    doc = ('<html><body><p>' + _QUOTED_ENGLISH + '</p><div id="sb_instagram">'
           '<div class="testimonial-card"><p>' + _QUOTED_SPANISH
           + '</p></div></div></body></html>')
    assert LA._testimonial_blocks(doc) == []
    assert 'Spanish' not in LA.languages_in(LA._page_text(doc))


def test_the_browser_reader_and_the_byte_reader_are_built_from_one_pattern():
    """One list and two readers, and the browser is handed this pattern's own source rather than a
    selector, because `[class*="review"]` cannot refuse `preview` and `[class$="review"]` cannot
    refuse `audio-preview`. The pattern that reaches the browser is applied here to the class
    values the corpus shows, and it has to decide every one of them the way the byte reader does.
    What the browser DOES with it is JavaScript and is exercised on a real page in
    tests/test_live.py, exactly as `_CHROME_JS` is."""
    calls = []

    class _Page(object):
        async def evaluate(self, js, arg=None):
            calls.append((js, arg))
            return 0

    asyncio.run(LA._lift_testimonials(_Page()))
    assert len(calls) == 1
    js, arg = calls[0]
    assert js is LA._QUOTED_JS
    assert arg == [LA.TESTIMONIAL_RX.pattern, list(LA.QUOTED_TAGS), LA.QUOTED_FIGURE_CHILD,
                   list(LA.QUOTED_NEVER)]
    for word in LA.TESTIMONIAL_WORDS:
        assert word in LA.TESTIMONIAL_RX.pattern, '%s is not in the pattern' % word
        assert LA._QUOTED_HINT.search(word), '%s is not in the prefilter' % word
        assert word not in js, (
            'the browser reads the word list off the pattern it is handed and never holds a copy '
            'of its own')
    browser_rx = re.compile(arg[0])
    for cls in ('testimonial-card', 'ios-preview-native-scroll', 'et_pb_testimonial_1',
                'audio-preview', 'widget-reviews', 'reviewer-photo', 'modern-quote',
                'avia-grid-testimonials'):
        assert bool(browser_rx.search(cls)) == LA._is_quoted_element('div', ' class="%s"' % cls), (
            'the two readers disagree about %s' % cls)
    for tag in LA.QUOTED_TAGS:
        assert LA._QUOTED_HINT.search('<' + tag + '>'), '%s is not in the prefilter' % tag
    assert LA._QUOTED_HINT.search('<' + LA.QUOTED_FIGURE_CHILD + '>')


def test_a_re_judged_capture_reads_the_quotation_out_too_and_puts_it_on_the_record():
    """The capture keeps the container, because `page.content()` is taken before the DOM strip. A
    re-judge has to take it out of the same text and record the same row, or the live audit and a
    re-judge of its own capture answer differently about a site neither of them has changed."""
    doc = _quoted('<div class="testimonial-card">', 'div')
    record = {'url': 'https://quoted.example/', 'verdict': 'true_multilingual',
              'languages': ['English', 'Spanish'], 'evidence': [],
              'pages': {'https://quoted.example/': doc}}
    r = LA.rejudge(record)
    assert r.verdict == 'english_only'
    assert 'Spanish' not in r.languages
    quoted = [e for e in r.evidence if e.mechanism == LA.MECH_TESTIMONIAL]
    assert [(e.language, e.sufficiency) for e in quoted] == [('Spanish', LA.SUFF_TOKEN)]
    assert LA.counted_evidence(r.evidence, r.machine_translation) == []
    assert r.by_language['Spanish'] == {'authorship': LA.AUTHOR_NONE,
                                        'sufficiency': LA.SUFF_NONE}, (
        'a language seen only in a quotation is on by_language and off languages, which is where '
        'a language on an archive page has always been')


def test_one_sitewide_slider_is_recorded_once_and_not_once_per_page():
    """A testimonial slider in a footer is on every page. Thirty copies of one quotation would
    bury the findings that decided the site under the one the verdict declined to count."""
    doc = _quoted('<div class="testimonial-card">', 'div')
    pages = {'https://quoted.example/': doc,
             'https://quoted.example/services': doc,
             'https://quoted.example/contact': doc}
    r = LA.rejudge({'url': 'https://quoted.example/', 'verdict': 'english_only',
                    'languages': ['English'], 'evidence': [], 'pages': pages})
    assert len([e for e in r.evidence if e.mechanism == LA.MECH_TESTIMONIAL]) == 1


def test_the_quoted_rows_come_last_on_the_evidence_list():
    """The hand-coding queue prints the first three rows of the list, so a quotation the verdict
    declined to count must not displace the finding the verdict rests on."""
    doc = ('<html><body><p>' + _QUOTED_ENGLISH + '</p><p>Ofrecemos ayuda con la escuela de los '
           'ninos, con la vivienda y con las citas legales todas las mananas de la semana en '
           'nuestra oficina del centro, y no hay que pagar nada por este servicio.</p>'
           '<div class="testimonial-card"><p>' + _QUOTED_SPANISH + '</p></div></body></html>')
    r = LA.rejudge({'url': 'https://quoted.example/', 'verdict': 'english_only',
                    'languages': ['English'], 'evidence': [],
                    'pages': {'https://quoted.example/': doc}})
    assert r.verdict == 'true_multilingual'
    assert [e.mechanism for e in r.evidence][-1] == LA.MECH_TESTIMONIAL
    assert r.evidence[0].mechanism == 'inline_text'


# --------------------------------------- a block of contact details is not prose in any language
#
# The five blocks below are shapes, not quotations: the two from docs/KNOWN_ISSUES.md are rewritten
# with invented street names and invented numbers, because a real address belongs in a measurement
# report and not in a test.
_CONTACT_PANEL = ('Riverbend Centre 4821 Marlow Rd, Suite 210, Fairhaven, NY 14022 '
                  'Main 555-217-4480 Espanol 555-217-4488 Fax 555-217-4499 '
                  'Monday 9am - 2pm Tuesday 9am - 2pm Wednesday 9am - 2pm Thursday 9am - 4pm')
_LISTING_RESIDUE = ('Fairhaven NY,14022 Save $310,000 House just listed Save 1 2 3 4 5 '
                    '820 Marlow Rd, Riverbend, NY 14031 $340,000 820 Marlow Rd, Riverbend, '
                    'NY 14031 Save 1 2 3 4 5 $268,000 17 Calder Ln, Fairhaven, NY 14022')
_DIRECTORY = ('Box 95086 Fairhaven, NY 14022 555-471-2522 Riverbend State Athletic Commission '
              '(RSAC) 1313 Marlow Street Riverbend, NY 14031 Box 94907 Fairhaven, NY 14022 '
              '555-471-4545 Riverbend State Patrol (RSP) Troop A')
_PROSE = ('Shirika letu la jamii linatoa msaada wa sheria na makazi kwa familia zote katika mji '
          'wetu kila wiki bila malipo yoyote na wafanyakazi wetu wanazungumza lugha yako.')
_PROSE_WITH_DETAILS = ('Tafadhali wasiliana nasi kwa simu 555-217-4480 au barua pepe ili kupanga '
                       'miadi na mshauri wetu kuhusu huduma za makazi elimu na afya kwa wakazi '
                       'wote wapya katika eneo letu kabla ya tarehe 14 Machi 2026.')


@pytest.mark.parametrize('block', [_CONTACT_PANEL, _LISTING_RESIDUE, _DIRECTORY])
def test_a_block_of_contact_details_is_not_offered_to_the_identifier(block):
    """A street address, a telephone number and a table of opening hours are not prose, and the
    identifier answers a language for any text it is handed. These are the three shapes it was
    measured answering a language on: Esperanto on an English footer, Slovenian on a property
    listing, Swedish on a state agency directory."""
    assert len(block) >= LA.AUX_MIN_BLOCK, 'a block this short never reached the identifier anyway'
    assert LA.listing_share(block) > LA.AUX_LISTING_SHARE
    assert not LA._aux_asked(block)


@pytest.mark.parametrize('block', [_PROSE, _PROSE_WITH_DETAILS])
def test_prose_is_offered_to_the_identifier_even_when_it_carries_a_number(block):
    """The half that costs recall if it is wrong. A paragraph that names a telephone number and a
    date is still a paragraph, and the ceiling is set where the genuine blocks of a measured
    capture run to 0.250 rather than where the shapes above begin at 0.320."""
    assert LA.listing_share(block) <= LA.AUX_LISTING_SHARE
    assert LA._aux_asked(block)


def test_the_listing_test_reads_an_address_the_way_an_address_is_written():
    """Case is the rule and not a convenience. `de`, `la`, `in`, `or` and `me` are ordinary words
    in the languages this reader exists to find and are also state codes in upper case, and
    matching them either way pushed a Spanish and an Estonian block over the ceiling."""
    spanish = ('Nuestra oficina de la comunidad ayuda a las familias con la escuela y la vivienda '
               'en el barrio, y nosotros podemos buscar un interprete para usted cuando lo pida.')
    assert LA.listing_share(spanish) == 0.0
    assert LA.listing_share('VA NE PA TX') == 1.0
    assert LA.listing_share('Rd St Ave Blvd') == 1.0
    assert LA.listing_share('$40 EUR 20 3pm') == pytest.approx(0.75)


def test_the_floor_is_asked_in_every_place_the_auxiliary_reader_splits_blocks():
    """AUX_SPLIT's own note says a reader that counted blocks one way and quoted them another would
    quote a passage it had not counted. The three places are `_aux_languages`, `language_coverage`
    and `_aux_quote`, and all three ask `_aux_asked`."""
    import inspect
    for fn in (LA._aux_languages, LA.language_coverage, LA._aux_quote):
        assert '_aux_asked' in inspect.getsource(fn), (
            '%s splits blocks without asking the floor' % fn.__name__)


def test_the_coverage_denominator_is_not_narrowed_by_the_floor():
    """Taking a refused block out of the denominator would RAISE the coverage of a page that is
    mostly contact panels, which is the opposite of what the floor is for."""
    import inspect
    src = inspect.getsource(LA.language_coverage)
    assert 'if len(b) >= AUX_MIN_BLOCK]' in src, 'the denominator stopped being every long block'


def test_a_latin_langid_answer_needs_corroboration():
    """AUX_SCRIPT has always refused langid's Pashto without a Pashto letter on the page. A
    Latin-script answer had no gate to meet, and langid names a language for any text it is
    handed: one South Asian cultural association's board roster, a run of Latin-script personal
    names, classified as Maltese, and twelve rows of the validation sample named such a language
    with the settled standard against every one. These pin THE GATES, with langid out of the loop.
    The roster below is invented and the real one is not reproduced here, so this does not
    reproduce the misfire itself, which depends on langid's n-grams over the names it actually
    saw; what it holds is that a roster of Latin-script names meets no letter gate and no word
    gate, which is what stops the misfire from reaching a reading."""
    roster = ('BOARD OF DIRECTORS YEAR 2026 RAJESH MANNAKKARA PRESIDENT PRIYA VADAKKEDATH '
              'VICE PRESIDENT SANTHOSHKUMAR ILLIKKAL TREASURER MEERA THAZHEKKARA SECRETARY')
    ada = ('The county will provide reasonable accommodations for persons attending public '
           'meetings, and all meetings of the council are open to every resident of the county.')
    # letter gates: the language's own orthography, absent from English prose
    for lang in ('Maltese', 'Danish', 'Afrikaans', 'Slovenian', 'Finnish'):
        assert LA._script_allows(lang, roster) is False
        assert LA._script_allows(lang, ada) is False
    assert LA._script_allows('Danish', 'Vi tilbyder gratis rådgivning på dit sprog højt og tæt') is True
    assert LA._script_allows('Maltese', 'Aħna noffru għajnuna bćara lill-familji kollha') is True
    # word gates: two distinct closed-class items, which no English block carries
    sw = ('Shirika letu linatoa msaada kwa familia zote katika mji wetu kila wiki bila malipo')
    assert LA._script_allows('Swahili', sw) is True
    assert LA._script_allows('Swahili', roster) is False
    assert LA._script_allows('Swahili', ada) is False
    assert LA._script_allows('Javanese', roster) is False
    assert LA._script_allows('Malay', ada) is False
    # Malay is the one gate here whose neighbour has a word list of its own, so it is pinned in both
    # directions. The Malaysian sentence carries four forms Indonesian does not write; the
    # Indonesian sentence beside it is the SAME sentence with the four Indonesian forms, and it must
    # not pass. Until 2026-08-07 the positive case was `Kami menyediakan bantuan untuk keluarga
    # dengan maklumat tentang perumahan dan pendidikan`, which is Indonesian in every word but
    # `maklumat`, and it passed on `untuk` and `dengan`, which Indonesian writes too.
    assert LA._script_allows('Malay', 'Perkhidmatan kami adalah percuma kerana kami menerima '
                                      'bantuan daripada kerajaan negeri') is True
    assert LA._script_allows('Malay', 'Layanan kami gratis karena kami menerima bantuan dari '
                                      'pemerintah provinsi') is False
    assert LA._script_allows('Malay', 'Kami menyediakan bantuan untuk keluarga dengan informasi '
                                      'tentang perumahan dan pendidikan') is False
    # one item alone is a name or a fragment, not a paragraph
    assert LA._script_allows('Swahili', 'The kwa center is open') is False


# ---------------------------------------------------------------------------------------------
# The four-script gate. A switcher row is a passage to the identifier, and the identifiers
# benchmarked against this corpus each answer something different about one: on one social services
# council's sixteen-script row, lid.176 says Hindi at 0.479, GlotLID says English, OpenLID says
# Ilocano.
# There is no right answer, because the block is not written in a language.


def test_a_row_of_language_names_is_not_a_passage():
    """The shape the gate exists for, taken from the capture. This is a switcher rendered as text,
    and every identifier asked about it invents an answer."""
    row = ('\u09ac\u09be\u0982\u09b2\u09be \u7b80\u4f53\u4e2d\u6587 \ud55c\uad6d\uc5b4 '
           '\u0420\u0443\u0441\u0441\u043a\u0438\u0439 \u0939\u093f\u0928\u094d\u0926\u0940 '
           '\u0c95\u0ca8\u0ccd\u0ca8\u0ca1 \u0ba4\u0bae\u0bbf\u0bb4\u0bcd '
           '\u0627\u0631\u062f\u0648 Espa\u00f1ol Ti\u1ebfng Vi\u1ec7t Kreyol Somali')
    assert LA._script_count(row) >= LA.MENU_SCRIPTS
    assert LA._aux_languages(row * 3, set()) == []


def test_japanese_prose_with_an_english_word_is_not_a_menu():
    """The gate's own worst failure mode, pinned so it cannot come back. Han, hiragana and katakana
    are three Unicode scripts and one writing system, and an ordinary Japanese sentence uses all
    three. Counted separately, every Japanese page carrying one English word would be four scripts
    and the gate would throw away the language it was built to protect."""
    ja = ('\u5f53\u30bb\u30f3\u30bf\u30fc\u306f\u3001\u5730\u57df\u306e\u3054\u5bb6\u65cf'
          '\u306b\u7121\u6599\u306eCOVID-19\u691c\u67fb\u3068\u901a\u8a33\u30b5\u30fc\u30d3'
          '\u30b9\u3092\u63d0\u4f9b\u3057\u3066\u3044\u307e\u3059\u3002')
    assert LA._script_count(ja) < LA.MENU_SCRIPTS, LA._script_count(ja)


def test_a_korean_page_naming_itself_in_english_is_not_a_menu():
    """Hangul beside occasional Han and Latin is three, and three is under the threshold. Korean is
    deliberately NOT collapsed into the Japanese entry."""
    ko = ('\ud55c\uad6d\uc778 \ubbf8\uad6d \ud611\ud68c(\u97d3\u56fd\u4eba\u5354\u4f1a)'
          '\ub294 \uc9c0\uc5ed \uac00\uc871\uc744 \uc704\ud574 \ubb34\ub8cc English '
          '\uc218\uc5c5\uc744 \uc81c\uacf5\ud569\ub2c8\ub2e4.')
    assert LA._script_count(ko) < LA.MENU_SCRIPTS, LA._script_count(ko)


def test_a_persian_page_with_an_english_footer_is_not_a_menu():
    """Two scripts. The threshold is four so that a page can name itself, carry an address and quote
    a policy link without any of that counting against it."""
    fa = ('\u062f\u0631\u0628\u0627\u0631\u0647 \u062a\u062f\u0631\u06cc\u0633 '
          '\u062e\u0635\u0648\u0635\u06cc \u0628\u06cc\u0634\u062a\u0631 '
          '\u0628\u062f\u0627\u0646\u06cc\u062f Privacy Policy 260 Larkspur Avenue Ashford, IN')
    assert LA._script_count(fa) == 2, LA._script_count(fa)


def test_the_script_counter_reads_a_fullwidth_letter_as_latin():
    """The counter matches the script word anywhere in the character's name and not as its first
    word, because a CJK page writes fullwidth Latin and `FULLWIDTH LATIN CAPITAL LETTER A` would
    otherwise be a writing system of its own."""
    assert LA._script_of('\uff21') == 'LATIN'
    assert LA._script_of('A') == 'LATIN'
    assert LA._script_of('\u4e2d') == 'CJK'
    assert LA._script_of('\u3042') == 'CJK'
    assert LA._script_of('\u30a2') == 'CJK'
    assert LA._script_of('\ud55c') == 'HANGUL'
    assert LA._script_of('1') == ''


# ---------------------------------------------------------------------------------------------
# The two codes added 2026-08-07, and the one deliberately left out. LIMITATIONS described these as
# an inventory limit when they were a choice: the identifier names them and the name was being
# discarded, because the code was not in the table.

_TIBETAN = ('\u0f56\u0f7c\u0f51\u0f0b\u0f66\u0f90\u0f51\u0f0b\u0f51\u0f44\u0f0b'
            '\u0f51\u0f42\u0f7a\u0f0b\u0f56\u0f0b\u0f62\u0f92\u0fb1\u0f0b'
            '\u0f58\u0f5a\u0fb2\u0f0d ') * 12


def test_the_tibetan_gate_is_the_tibetan_range_and_nothing_else():
    """Tibetan script is claimed by no other language in these inventories, so the range IS the
    gate and there is nothing finer to ask for, unlike Pashto against Persian."""
    english = ('The center offers classes and legal help to families in the county every week of '
               'the year. ') * 3
    assert LA._script_allows('Tibetan', _TIBETAN) is True
    assert LA._script_allows('Tibetan', english) is False


def test_tibetan_and_sorani_are_in_the_auxiliary_table():
    """`bo` and `ckb`. Sorani is the inversion worth naming: SORANI_HOSTS renames a Persian answer
    to Sorani because the PREVIOUS identifier had no Sorani model, and lid.176 has one, so a page
    it called Sorani correctly was thrown away while a page it called Persian was renamed."""
    assert LA.AUX_ISO.get('bo') == 'Tibetan'
    assert LA.AUX_ISO.get('ckb') == 'Kurdish'
    assert 'Tibetan' not in LA.COVERED, 'a covered name is filtered out of the auxiliary reading'


def test_nepali_is_left_out_of_the_identifier_and_read_by_the_script_instead():
    """This test said, until the Devanagari resolution landed, that Nepali was not missed but
    misnamed, that adding `ne` would put two names on one text, and that separating Nepali from
    Hindi was a measurement nobody had taken. The measurement has been taken and the pin did its
    work: it is what made the separation a decision rather than a gap nobody could see.

    Both halves hold now for a stronger reason than before. `ne` is still out, because Nepali is in
    COVERED and `_aux_languages` filters a covered name, so an entry could never fire. And the name
    has left SWITCHER_ONLY, which is what that set is for: the asymmetry it records is that a
    switcher can offer what the reader cannot read, and the reader can read this one.
    """
    assert 'ne' not in LA.AUX_ISO
    assert 'Nepali' in LA.COVERED
    assert 'Nepali' not in LA.SWITCHER_ONLY
    assert LA.SWITCHER_ONLY == frozenset(), (
        'a name in this set is a name the switcher reports and the reader cannot: %s'
        % sorted(LA.SWITCHER_ONLY))


def test_the_tibetan_entry_is_wired_and_the_solo_run_is_what_releases_it():
    """End to end, and it records which limit is doing the work.

    This test said the opposite until the solo-run rule landed, and the change records a decision
    and not a repair. The identifier answers `bo` at full confidence and the script gate passes, so the
    reading was available as soon as the code was in the table; what refused it was AUX_MIN_BLOCKS,
    because the site that motivated the entry carries exactly one passage over the length floor.
    Counting blocks was a proxy for whether one stray finding should decide a class, and
    `AUX_SOLO_RUN` replaces the proxy with the quantity that actually separates the cases: 1,105
    characters of Tibetan in one block is a passage, and a thirty-character proper name is not.
    """
    pytest.importorskip('fasttext')
    if LA._ft() is None:
        pytest.skip('the identifier could not load in this environment')
    code, conf = LA._lid(_TIBETAN)
    assert code == 'bo' and conf > 0.9, (code, conf)
    assert LA._aux_names(code, _TIBETAN) == ['Tibetan']
    # one block, and it is named, because the run is long
    assert LA._aux_languages(_TIBETAN, set()) == ['Tibetan']
    assert LA._aux_solo('Tibetan', _TIBETAN) is True
    # and with the solo rule out of the way the old behaviour returns, which is what says the rule
    # and not something else is what releases it
    saved = LA.AUX_SOLO_RUN
    try:
        LA.AUX_SOLO_RUN = 10 ** 9
        assert LA._aux_languages(_TIBETAN, set()) == []
    finally:
        LA.AUX_SOLO_RUN = saved


# ---------------------------------------------------------------------------------------------
# `failure_kind`. Every note below is one the 1,000-site validation capture actually carries, and
# the counts in the ids are how many of its 73 unread rows carry that shape.

_FAILURE_NOTES = [
    ('HTTP 403 on the home page, 214-character body (home read retried once)', 'http_403'),
    ('HTTP 403 on the home page, 49-character body (home read retried once)', 'http_403'),
    ('HTTP 404 on the home page, 62-character body (home read retried once)', 'http_404'),
    ('robots.txt disallowed the home page, so the site was not read', 'robots_disallow'),
    ("a third-party directory profile, not the organization's own website", 'directory_profile'),
    ('empty body (HTTP 200) (home read retried once)', 'empty_body'),
    ('bot wall', 'bot_wall'),
    ('TimeoutError (home read retried once)', 'timeout'),
    ('ValueError: Invalid IPv6 URL', 'malformed_address'),
    ('Error (home read retried once)', 'unspecified_error'),
    ("a parked or expired domain, not the organization's own website", 'parked_domain'),
]

# The transport failures, whose notes come from a different measurement and are marked as such. The
# 1,000-site capture could not carry one of these, because until 2026-09-18 the note on a failed
# read was the exception's CLASS and every one of them arrived as the bare word `Error`. These are
# the strings `_error_note` now writes, and the causes behind them were read off a probe of the 144
# addresses the gold-frame run of 2026-09-08 recorded unreachable, taken on 2026-09-18.
_TRANSPORT_NOTES = [
    ('Error: net::ERR_HTTP2_PROTOCOL_ERROR (home read retried once)', 'protocol_error'),
    ('Error: net::ERR_EMPTY_RESPONSE (home read retried once)', 'protocol_error'),
    ('Error: net::ERR_CONNECTION_CLOSED (home read retried once)', 'connection_closed'),
    ('Exception: Connection closed while reading from the driver', 'connection_closed'),
    ('Error: net::ERR_CONNECTION_TIMED_OUT (home read retried once)', 'timeout'),
]
_FAILURE_NOTES += _TRANSPORT_NOTES


@pytest.mark.parametrize('note,want', _FAILURE_NOTES,
                         ids=[w for _n, w in _FAILURE_NOTES])
def test_failure_kind_names_the_mechanism(note, want):
    """`HTTP 403 on the home page` appears as 17 DISTINCT strings
    across 25 sites of that capture, because the note interpolates the body length, so an analyst
    who counts notes counts seventeen failures where there is one."""
    assert LA.failure_kind(note) == want


def test_failure_kind_is_empty_for_a_site_that_was_read():
    """A site that was read has no failure to name. Returning a kind for it would put every row in
    a table into a failure family."""
    r = LA.Result(url='https://x.example/', verdict='english_only', note='read 15 pages')
    assert LA.failure_kind(r) == ''
    assert LA.failure_kind({'verdict': 'true_multilingual', 'note': 'anything'}) == ''


@pytest.mark.parametrize('label,ch,want', [
    ('base block',                  'م', True),
    ('Arabic Supplement',           'ݖ', True),
    ('Arabic Extended-B',           'ࡲ', True),
    ('Arabic Extended-A',           'ࢠ', True),
    ('Presentation Forms-A',        'ﭐ', True),
    ('Presentation Forms-B, first', 'ﹰ', True),
    ('Presentation Forms-B, last',  'ﻼ', True),
    ('the byte order mark',         '﻿', False),
    ('Hebrew',                      'א', False),
    ('Syriac',                      'ܐ', False),
    ('Thaana',                      'ހ', False),
])
def test_the_arabic_class_covers_the_script_and_stops_at_the_byte_order_mark(label, ch, want):
    """The class names a script, so it has to cover the script's blocks and nothing else.

    The last case is the one that matters. Presentation Forms-B ends at U+FEFF and U+FEFF is the
    byte order mark, not a letter, so a range written to the block boundary makes a plain English
    page that merely opens with a BOM read as Arabic. Every corpus here has such pages.
    """
    import re
    pat = dict(LA.SCRIPTS)['Arabic']
    assert bool(re.search(pat, ch)) is want, label


def test_a_bom_does_not_put_a_page_into_a_script():
    """The same thing said on a page rather than a character, since that is how it would have shipped."""
    import re
    pat = dict(LA.SCRIPTS)['Arabic']
    assert not re.search(pat, '﻿Welcome to our clinic. Office hours are nine to five.')
    assert re.search(pat, '﻿مرحبا بكم')


class _FakeControl:
    """The two evaluate() probes `_accessible_label` makes, and nothing else."""

    def __init__(self, aria=None, title=None, alt=None, raise_on=()):
        self.aria, self.title, self.alt, self.raise_on = aria, title, alt, raise_on

    async def evaluate(self, how):
        for key, val in (('aria-label', self.aria), ('title', self.title), ('img', self.alt)):
            if key in how:
                if key.split('-')[0] in self.raise_on:
                    raise RuntimeError('element detached')
                return val
        return None


@pytest.mark.parametrize('label,aria,title,alt,want', [
    ('aria-label first',        'Espanol', 'x', 'y', 'Espanol'),
    ('title when aria is gone',  None, 'Kreyol', 'y', 'Kreyol'),
    ('the alt of a flag image',  None, None, 'Tieng Viet', 'Tieng Viet'),
    ('nothing at all',           None, None, None, ''),
    ('whitespace is nothing',    '  ', ' ', '', ''),
])
def test_a_control_with_no_text_is_read_from_its_accessible_name(label, aria, title, alt, want):
    """An anchor holding only a flag image returns nothing from inner_text, so the language-name
    test never sees a label and the control is never worked. The accessible name is what a screen
    reader announces, which makes it the right fallback for a language-access instrument."""
    el = _FakeControl(aria=aria, title=title, alt=alt)
    assert asyncio.run(LA._accessible_label(el)) == want, label


def test_reading_the_accessible_name_never_raises():
    """A control can go away between the query and the read, and one that does must not take the
    page's whole click step with it."""
    el = _FakeControl(aria='Espanol', raise_on=('aria', 'title', 'img'))
    assert asyncio.run(LA._accessible_label(el)) == ''


@pytest.mark.parametrize('text', ['Menu', 'Search', 'Close', 'Home', 'Language', 'Select language',
                                  'Open navigation', 'Facebook', 'Translate', 'flag of Mexico',
                                  'Spanish version of this page', 'en', 'es'])
def test_an_accessible_name_admits_nothing_the_visible_text_would_not(text):
    """The fallback finds a label; it does not lower the bar the label then has to clear. These are
    the accessible names a switcher-shaped element commonly carries, and none of them is a language
    control. Checked because a change that fires correctly can still admit the wrong thing, which is
    the standing rule here."""
    assert not (len(text) <= LA.LANGLABEL_MAX and LA._langlabel(text))


@pytest.mark.parametrize('text', ['Espanol', 'Kreyol Ayisyen', 'Tieng Viet'])
def test_the_autonyms_it_is_meant_to_find_do_clear_the_gates(text):
    assert len(text) <= LA.LANGLABEL_MAX and LA._langlabel(text)


def _written_off_note(attempts=3, last=''):
    """The note `written_off` builds, rebuilt from the same constants it uses.

    Not a copied string: if the wording moves and the pattern does not, this fails here instead of
    silently reclassifying every dead-driver row in a published store.
    """
    note = (f'no page, and back in under {LA.DEAD_SECONDS:g}s, on {attempts} '
            f'{LA.DEAD_DRIVER_NOTE}: a site that answers nothing and a dead driver look the '
            f'same from here')
    return note + (f'. last attempt: {last}' if last else '')


@pytest.mark.parametrize('last', [
    '',
    'HTTP 403 on the home page, 214-character body (home read retried once)',
    'Error (home read retried once)',
    'robots.txt disallowed the home page, so the site was not read',
    'TimeoutError (home read retried once)',
    'Error: net::ERR_HTTP2_PROTOCOL_ERROR (home read retried once)',
])
def test_a_site_that_answered_nothing_on_every_driver_has_its_own_kind(last):
    """A site that came back empty and instantly on every driver it was offered is not a finding
    about the site. `written_off` says so in the note, and this is the family that lets a study set
    those rows aside instead of counting them as the site's own behaviour.

    The last attempt's words are carried on the same note so that nothing diagnostic is lost, and
    they are exactly what used to classify the row: a run whose drivers died on 2026-08-11 wrote
    rows whose last attempt read `HTTP 403`, and `failure_kind` called them http_403, which is a
    statement about the site that nothing established. So the pattern is tested FIRST.
    """
    assert LA.failure_kind(_written_off_note(last=last)) == 'no_page_any_driver'


def test_the_dead_driver_kind_does_not_swallow_an_ordinary_failure():
    """It has to be narrow: every other note in the capture keeps the family it had."""
    for note, want in _FAILURE_NOTES:
        assert LA.failure_kind(note) == want


def test_failure_kind_takes_a_result_a_dict_or_a_note():
    """Those three are what a caller has in hand at different points and none is more correct."""
    note = 'robots.txt disallowed the home page, so the site was not read'
    r = LA.Result(url='https://x.example/', verdict='unreachable', note=note)
    assert LA.failure_kind(r) == 'robots_disallow'
    assert LA.failure_kind({'verdict': 'unreachable', 'note': note}) == 'robots_disallow'
    assert LA.failure_kind(note) == 'robots_disallow'


def test_every_kind_it_returns_is_in_the_published_vocabulary():
    """Otherwise the closed list is not closed and a consumer cannot enumerate it."""
    for note, want in _FAILURE_NOTES:
        assert want in LA.FAILURE_KINDS
    assert LA.failure_kind('something nobody has seen before') == 'other'
    assert 'other' in LA.FAILURE_KINDS


def test_the_specific_patterns_are_tested_before_the_catch_all():
    """Order is all of the parsing. `Error (home read retried once)` is what the crawl writes
    when it has nothing more specific, and an unordered table would let it swallow every named
    mechanism that mentions an error."""
    assert LA.failure_kind('TimeoutError (home read retried once)') == 'timeout'
    assert LA.failure_kind('ValueError: Invalid IPv6 URL') == 'malformed_address'
    kinds = [k for k, _rx in LA._FAILURE_PATTERNS]
    assert kinds[-1] == 'unspecified_error', kinds


# ---------------------------------------------------------------------------------------------
# The solo-run rule. AUX_MIN_BLOCKS counts blocks, which is a proxy, and the capture shows the proxy
# failing in both directions at once. Both cases below are real sites and both are pinned.

_SOLO_TIBETAN = ('\u0f56\u0f7c\u0f51\u0f0b\u0f66\u0f90\u0f51\u0f0b\u0f51\u0f44\u0f0b'
                 '\u0f51\u0f42\u0f7a\u0f0b\u0f56\u0f0b\u0f62\u0f92\u0fb1\u0f0b'
                 '\u0f58\u0f5a\u0fb2\u0f0d') * 20
_SOLO_TAMIL_TITLE = ('Events - RCAA 01 Nov \u0baf\u0bbe\u0bb4\u0bcd\u0baa\u0bcd\u0baa'
                     '\u0bbe\u0ba3 \u0ba8\u0bbe\u0ba4 (Yazhpana Nada Samarpanam) 18:00 - '
                     '00:00 Riverbend School of Music and Dance, Ashford, NY')


def test_a_long_run_lets_one_block_name_a_language():
    """One Tibetan Buddhist temple publishes 1,105 characters of Tibetan and the identifier answers
    at 1.000.
    It sits in ONE block, so the block count refused it and the site read english_only while the
    settled standard reads true_multilingual."""
    assert LA._aux_solo('Tibetan', _SOLO_TIBETAN) is True
    assert LA._longest_run(_SOLO_TIBETAN,
                           LA.AUX_SCRIPT_RX['Tibetan'].pattern) >= LA.AUX_SOLO_RUN


def test_a_proper_name_in_another_script_does_not():
    """The other direction, and it is why the block count existed. This is one South Asian
    association's events page: the proper name of a concert in Tamil script with its romanization in
    brackets, inside an otherwise English listing, on a site the standard settles english_only."""
    assert LA._aux_solo('Tamil', _SOLO_TAMIL_TITLE) is False


def test_a_latin_script_auxiliary_language_can_never_qualify_alone():
    """Deliberate, and it is what keeps this rule away from the injected-advertising class. AUX_SCRIPT
    has no entry for Finnish, Czech, Dutch or Swedish because their script does not separate them
    from English, so there is no run to measure and two blocks are still required. The casino spam
    on two municipal sites is written in exactly those languages."""
    for lang in ('Finnish', 'Czech', 'Dutch', 'Swedish', 'Greek'):
        long_latin = 'kasino ja bonus ja ilmaiskierroksia netissa ' * 20
        if lang == 'Greek':
            continue
        assert LA.AUX_SCRIPT.get(lang) is None, lang
        assert LA._aux_solo(lang, long_latin) is False, lang


def test_the_threshold_is_the_block_length_and_not_a_new_number():
    """AUX_MIN_BLOCK is already this file's statement of how much text the identifier needs to be
    right about, so a run of a language as long as a whole qualifying block is a passage in that
    language by the file's own standard. Of the 15 (site, language) pairs the auxiliary reader can
    name across the capture, three rest on a single block and their runs are 964, 32 and 26
    characters, so every threshold between 40 and 800 admits exactly one of them."""
    assert LA.AUX_SOLO_RUN == LA.AUX_MIN_BLOCK
    assert 32 < LA.AUX_SOLO_RUN < 964


def test_one_block_of_tibetan_now_names_it_and_a_tamil_title_does_not():
    """End to end through `_aux_languages`, which is where the block count is applied."""
    pytest.importorskip('fasttext')
    if LA._ft() is None:
        pytest.skip('the identifier could not load in this environment')
    assert LA._aux_languages(_SOLO_TIBETAN, set()) == ['Tibetan']
    assert LA._aux_languages(_SOLO_TAMIL_TITLE, set()) == []
