# -*- coding: utf-8 -*-
"""Known-answer cases for the switcher reader, cut out of the validation capture of 2026-07-31.

Every fragment below is the exact bytes one site served on that day, taken out of that capture's
rendered documents and trimmed to its first few options so a person can read it. Nothing here was
written to make a test pass.

What the cases are for, in the order the failures happened while the reader was being built:

  The Google Translate combo was REJECTED by the first version, because Google's menu is about 250
  languages long and this package can name roughly eighty of them, so a share-of-labels test threw
  away the commonest switcher there is. `test_the_google_combo_is_read_however_many_it_cannot_name`
  is the gate on that.

  A COUNTRY dropdown was accepted by the second version. A country list's codes are `AF`, `AM` and
  `BG`, which are Afghanistan, Armenia and Bulgaria to the form and Afrikaans, Amharic and Bulgarian
  to a language table, so resolving the code first credited one county action committee with
  languages off a donation form. `test_a_country_dropdown_is_not_a_switcher` is the gate.

  A directory's PROVIDER-LANGUAGE facet is the opposite trap and no test on labels can catch it:
  every label in one statewide immigration coalition's provider filter really is a language. It is
  rejected on its values, which are search slugs, and on its container, which names no vendor.
  `test_a_provider_language_facet_is_not_a_switcher` is the gate, and it matters most of the four:
  reading it would have credited one site with sixty languages it does not publish in.
"""
import pytest

from langaccess import core as LA

# ------------------------------------------------------------------------------------------------
# One statewide immigration coalition's provider directory, read 2026-07-31. The Google Translate
# combo box, which JavaScript builds at runtime, and the provider-language facet that sits on the
# same page. First eight options of each.
GOOG_COMBO = (
    '<select class="goog-te-combo" aria-label="Language Translate Widget">'
    '<option value="">Select Language</option><option value="ab">Abkhaz</option>'
    '<option value="ace">Acehnese</option><option value="ach">Acholi</option>'
    '<option value="aa">Afar</option><option value="af">Afrikaans</option>'
    '<option value="sq">Albanian</option><option value="alz">Alur</option></select>')

PROVIDER_FACET = (
    '<select name="_sft_providers_language[]" class="sf-input-select" title="">'
    '<option class="sf-level-0 sf-item-0 sf-option-active" selected="selected" data-sf-count="0"'
    ' data-sf-depth="0" value="">All Provider Languages</option>'
    '<option class="sf-level-0 sf-item-181" data-sf-count="1" data-sf-depth="0"'
    ' value="200-languages">200 languages&nbsp;&nbsp;(1)</option>'
    '<option class="sf-level-0 sf-item-95" data-sf-count="1" data-sf-depth="0"'
    ' value="albanian">Albanian&nbsp;&nbsp;(1)</option>'
    '<option class="sf-level-0 sf-item-97" data-sf-count="3" data-sf-depth="0"'
    ' value="arabic">Arabic&nbsp;&nbsp;(3)</option>'
    '<option class="sf-level-0 sf-item-98" data-sf-count="1" data-sf-depth="0"'
    ' value="armenian">Armenian&nbsp;&nbsp;(1)</option>'
    '<option class="sf-level-0 sf-item-99" data-sf-count="1" data-sf-depth="0"'
    ' value="asl">ASL&nbsp;&nbsp;(1)</option></select>')

# One county action committee, read 2026-07-31. A Gravity Forms country field, and the
# GTranslate switcher that really is one, from the same document.
COUNTRY_DROPDOWN = (
    '<select name="input_6.6" id="input_23_6_6" aria-required="false">'
    '<option value="" selected=""></option><option value="Afghanistan">Afghanistan</option>'
    '<option value="Albania">Albania</option><option value="Algeria">Algeria</option>'
    '<option value="American Samoa">American Samoa</option>'
    '<option value="Andorra">Andorra</option><option value="Angola">Angola</option></select>')

# the same list written the way a form that stores ISO country codes writes it, which is the shape
# that made the first reader report Afrikaans, Armenian and Bulgarian off a country field
COUNTRY_DROPDOWN_CODED = (
    '<select name="country" id="country">'
    '<option value="AF">Afghanistan</option><option value="AL">Albania</option>'
    '<option value="AM">Armenia</option><option value="BG">Bulgaria</option>'
    '<option value="AR">Argentina</option><option value="SO">Somalia</option></select>')

GTRANSLATE_ANCHORS = (
    '<a href="#" class="nturl" data-gt-lang="af">'
    '<img data-gt-lazy-src="/wp-content/plugins/gtranslate/flags/svg/af.svg" alt="af">'
    ' Afrikaans</a>'
    '<a href="#" class="nturl" data-gt-lang="sq">'
    '<img data-gt-lazy-src="/wp-content/plugins/gtranslate/flags/svg/sq.svg" alt="sq">'
    ' Albanian</a>'
    '<a href="#" class="nturl" data-gt-lang="am">'
    '<img data-gt-lazy-src="/wp-content/plugins/gtranslate/flags/svg/am.svg" alt="am">'
    ' Amharic</a>'
    '<a href="#" class="nturl" data-gt-lang="ar">'
    '<img data-gt-lazy-src="/wp-content/plugins/gtranslate/flags/svg/ar.svg" alt="ar">'
    ' Arabic</a>')

# One state immigration justice project, read 2026-07-31. WPML, whose labels are
# autonyms and whose codes are in hreflang. Six anchors, one of them English.
WPML_ANCHORS = (
    '<a href="https://www.example.org/immigration-justice-project/" hreflang="en" lang="en"'
    ' class="wpml-ls-link"><span class="wpml-ls-native">English</span></a>'
    '<a href="https://www.example.org/es/proyecto/" hreflang="es" lang="es"'
    ' class="wpml-ls-link"><span class="wpml-ls-native">Español</span></a>'
    '<a href="https://www.example.org/ko/x/" hreflang="ko" lang="ko"'
    ' class="wpml-ls-link"><span class="wpml-ls-native">한국어</span></a>'
    '<a href="https://www.example.org/ru/x/" hreflang="ru" lang="ru"'
    ' class="wpml-ls-link"><span class="wpml-ls-native">Русский</span></a>'
    '<a href="https://www.example.org/ar/x/" hreflang="ar" lang="ar"'
    ' class="wpml-ls-link"><span class="wpml-ls-native">العربية</span></a>'
    '<a href="https://www.example.org/fr/projet/" hreflang="fr" lang="fr"'
    ' class="wpml-ls-link"><span class="wpml-ls-native">Français</span></a>')

# One town government site, read 2026-07-31. A Google Translate skin that writes the language NAME
# into data-lang instead of a code, which is why a code is not required of a signalled group.
DATA_LANG_ANCHORS = (
    '<a href="#" class="Afrikaans" data-lang="Afrikaans">Afrikaans</a>'
    '<a href="#" class="Albanian" data-lang="Albanian">Albanian</a>'
    '<a href="#" class="Arabic" data-lang="Arabic">Arabic</a>'
    '<a href="#" class="Armenian" data-lang="Armenian">Armenian</a>')


def _page(*fragments):
    return '<html><body>' + ''.join(fragments) + '</body></html>'


# ------------------------------------------------------------------------------------------------
# the four cases the reader was built against


def test_the_google_combo_is_read_however_many_it_cannot_name():
    """Google's menu is longer than this package's vocabulary, and the answer is the part it can
    name plus a count of the part it cannot, never nothing at all."""
    langs, unresolved = LA.switcher_languages(_page(GOOG_COMBO))
    assert 'Afrikaans' in langs and 'Albanian' in langs
    # Abkhaz, Acehnese, Acholi, Afar and Alur are real offers this package has no name for, so they
    # are counted rather than dropped: eight names with sixty unknowns is not eight names.
    assert unresolved == 5
    # `Select Language` is the menu's own prompt and not an offer, so it is neither named nor counted
    assert 'Select Language' not in langs


def test_a_provider_language_facet_is_not_a_switcher():
    """Every label in it IS a language, so only the values and the container can reject it. Reading
    it would have credited one statewide immigration coalition with sixty languages it does not
    publish in."""
    langs, unresolved = LA.switcher_languages(_page(PROVIDER_FACET))
    assert langs == []
    assert unresolved == 0


def test_the_facet_does_not_contaminate_the_combo_on_the_same_page():
    """Both were on one document. The combo has to be read and the facet has to be refused, which is
    a statement about the two groups being judged separately."""
    langs, _ = LA.switcher_languages(_page(GOOG_COMBO, PROVIDER_FACET))
    assert 'Afrikaans' in langs
    # `ASL` and `200 languages` are the facet's, and neither is a language this tool would name
    assert 'Albanian' in langs      # the combo's, not the facet's: the combo carries `sq`
    assert len(langs) == 2


@pytest.mark.parametrize('markup', [COUNTRY_DROPDOWN, COUNTRY_DROPDOWN_CODED])
def test_a_country_dropdown_is_not_a_switcher(markup):
    """`AM` is Armenia to a form and Amharic to a language table. Resolving the code without
    requiring the label to name a language reported languages off a donation form."""
    assert LA.switcher_languages(_page(markup)) == ([], 0)


def test_the_country_dropdown_does_not_contaminate_the_real_switcher_beside_it():
    """One county action committee serves both out of one document."""
    langs, _ = LA.switcher_languages(_page(COUNTRY_DROPDOWN, GTRANSLATE_ANCHORS))
    assert langs == ['Afrikaans', 'Albanian', 'Amharic', 'Arabic']


# ------------------------------------------------------------------------------------------------
# what the reader answers


def test_a_code_names_a_language_whose_autonym_the_package_has_no_word_for():
    """WPML labels its options in the language itself. `Русский` and `العربية` are in the autonym
    list; a switcher writing one that is not still has hreflang, and hreflang names it."""
    langs, unresolved = LA.switcher_languages(_page(WPML_ANCHORS))
    assert langs == ['Arabic', 'French', 'Korean', 'Russian', 'Spanish']
    assert unresolved == 0


def test_a_signalled_group_does_not_need_a_code_at_all():
    """One town government's Google Translate skin writes the language NAME into data-lang. Requiring
    a code of every control would have thrown away a seventy-language switcher."""
    langs, _ = LA.switcher_languages(_page(DATA_LANG_ANCHORS))
    assert langs == ['Afrikaans', 'Albanian', 'Arabic', 'Armenian']


def test_english_is_resolved_and_then_left_out():
    """A switcher lists English like anything else. It has to RESOLVE, or every English entry would
    be counted as a label that failed; and it has to be left out of the answer, because `languages`
    leaves it out and the two fields would otherwise not be comparable."""
    two = _page('<a hreflang="en" href="/">English</a><a hreflang="es" href="/es/">Español</a>')
    langs, unresolved = LA.switcher_languages(two)
    assert langs == ['Spanish']
    assert unresolved == 0
    # and English counted towards the two that make a list, which is why one language comes back
    assert LA.SWITCHER_MIN == 2


def test_one_language_link_is_not_a_switcher():
    """A single Español link is a link to a Spanish page, which `_routes` already collects and the
    verdict already reads. A LIST is two or more."""
    one = _page('<a hreflang="es" href="/es/">Español</a>')
    assert LA.switcher_languages(one) == ([], 0)


def test_a_document_with_no_switcher_answers_nothing():
    assert LA.switcher_languages('<html><body><p>We serve immigrants.</p></body></html>') == ([], 0)
    assert LA.switcher_languages('') == ([], 0)
    assert LA.switcher_languages(None) == ([], 0)


def test_a_name_appears_once_however_many_controls_carry_it():
    """A page renders the same switcher in its header and its footer, and one site served the same
    thirteen anchors three times over."""
    langs, _ = LA.switcher_languages(_page(GTRANSLATE_ANCHORS, GTRANSLATE_ANCHORS))
    assert langs == ['Afrikaans', 'Albanian', 'Amharic', 'Arabic']


def test_the_unresolved_count_is_of_distinct_entries_too():
    """The same reasoning as the line above, on the other side of the answer. Two copies of one
    menu offer what one copy offers, so a site serving its switcher twice must not be reported as
    having twice as many languages this tool cannot name."""
    once = LA.switcher_languages(_page(GOOG_COMBO))
    twice = LA.switcher_languages(_page(GOOG_COMBO, GOOG_COMBO))
    assert once == twice == (['Afrikaans', 'Albanian'], 5)


def test_the_vocabulary_only_names_languages_the_package_already_knows():
    """The switcher vocabulary is the package's own lists, plus a SET THAT HAS TO BE DECLARED.

    A menu offering a language this tool cannot name has to COUNT as unresolved
    rather than be given a new name here, because the unresolved figure is what tells a reader how
    much of a menu the field is showing them. A name added to the vocabulary and absent from the
    detector is a language `switcher_languages` can report and `languages` can never report, which
    is a real asymmetry: it is not wrong, but a reader comparing the two fields has to be told which
    silence is an instrument limit rather than a fact about the site.

    Nepali entered that state by accident. LANGNAME matched नेपाली and `nepali` as a switcher label
    from the first version, and nothing ever read a Nepali page. It was pinned here by name so that
    a second such addition had to be somebody's decision rather than a side effect.

    On 2026-08-01 it became somebody's decision. Pashto, Burmese, Kurdish and Hmong were the four
    commonest unresolved labels in the validation capture, and all four were added to the vocabulary
    because the owner asked for them. Three of the four got detectors in the same pass and were not
    in this set: Burmese through SCRIPTS, Hmong through FUNC, Pashto through AUX_ISO. Kurdish was
    the second member, and on 2026-08-02 it left, because Sorani got one too.

    THE MEMBERSHIP TEST IS AUX_NAMES AND NOT `AUX_ISO.values()`. The Sorani change has that shape:
    a name the auxiliary reader returns that langid has no code for, so the values of
    the code table are no longer the names the reader can produce. A test written against the code
    table would have reported Kurdish as unreadable while the reader was reading it.

    What this pins is the DECLARATION, not the number. Adding a switcher-only name is still allowed
    and still has to be deliberate: it fails here until it is also written into SWITCHER_ONLY, where
    the reason for it has to be given.
    """
    known = LA.COVERED | set(LA.AUX_NAMES) | {LA.SWITCHER_ENGLISH}
    assert set(LA.LANG_CODE.values()) - known == set(LA.SWITCHER_ONLY)
    assert set(LA.LANG_TOKEN.values()) - known == set(LA.SWITCHER_ONLY)
    assert LA.SWITCHER_ONLY == {'Nepali'}
    # every alias points at a name the package can either read or has declared it cannot
    assert set(LA.SWITCHER_ALIAS.values()) <= known | set(LA.SWITCHER_ONLY)
    # and the four that DID get detectors are not quietly sitting in the declared set
    for name in ('Burmese', 'Hmong', 'Pashto', 'Kurdish'):
        assert name not in LA.SWITCHER_ONLY
        assert name in known


def test_every_label_the_capture_carries_for_the_four_added_languages_resolves():
    """The labels are the ones the stored documents actually write, not invented spellings.

    `Myanmar (Burmese)` and `Kurdish (Kurmanji)` are how Google's own menu writes them, and
    SWITCHER_TRIM has to drop the bracket before the lookup can work. `Kurdish (Sorani)` resolves to
    the same name as `Kurdish (Kurmanji)`, which is correct and is the reason the two Kurdish
    options a Google menu offers count once rather than twice.
    """
    seen = {
        'Hmong': 'Hmong', 'Hmoob': 'Hmong',
        'Pashto': 'Pashto', 'پښتو': 'Pashto',
        'Myanmar (Burmese)': 'Burmese', 'Myanmar': 'Burmese', 'မြန်မာ': 'Burmese',
        'Kurdish (Kurmanji)': 'Kurdish', 'Kurdish (Sorani)': 'Kurdish', 'Kurdish': 'Kurdish',
        'Kurdî (KU)': 'Kurdish',
    }
    for label, want in seen.items():
        assert LA._lookup_language(LA.LANG_TOKEN, label) == want, label
    for code, want in {'my': 'Burmese', 'hmn': 'Hmong', 'ps': 'Pashto',
                       'ku': 'Kurdish', 'ckb': 'Kurdish', 'kmr': 'Kurdish'}.items():
        assert LA._lookup_language(LA.LANG_CODE, code) == want, code


def test_a_switcher_only_language_is_reportable_and_undetectable():
    """The asymmetry itself, asserted rather than described.

    The SWITCHER_ONLY declaration says exactly this much: the menu can be read, the page
    cannot. It has already fired once in the direction it was built to fire: Kurdish got a detector
    on 2026-08-02 and had to come out of the set.
    """
    for name in LA.SWITCHER_ONLY:
        assert name in set(LA.LANG_TOKEN.values())          # a switcher offering it is reported
        assert name not in LA.COVERED                        # no word list and no script names it
        assert name not in LA.AUX_NAMES                      # and the auxiliary reader cannot say it


# ------------------------------------------------------------------------------------------------
# what it must NOT do


def test_the_switcher_moves_no_verdict():
    """The field is descriptive. Nothing in it is evidence, nothing in it is counted, and the two
    functions that decide a class never see it."""
    ev = [LA.Evidence('inline_text', 'https://x.org/', 'Nuestros servicios', 'Spanish')]
    before = LA.verdict_for(ev, 'Google Translate')
    r = LA.Result(url='https://x.org/')
    r.evidence = ev
    r.switcher_languages = ['Korean', 'Somali', 'Vietnamese']
    r.switcher_unresolved = 60
    # the verdict is read off the evidence and the widget, and neither of those is the menu
    assert LA.verdict_for(r.evidence, 'Google Translate') == before
    assert [LA._ev_lang(e) for e in LA.counted_evidence(r.evidence, 'Google Translate')] == \
        [LA._ev_lang(e) for e in LA.counted_evidence(ev, 'Google Translate')]


def test_the_switcher_is_not_the_organizations_own_writing():
    """A widget offering eighty languages says nothing about what the organization wrote, and
    `languages` must not pick any of them up."""
    html = _page(GOOG_COMBO)
    langs, _ = LA.switcher_languages(html)
    assert len(langs) >= 2
    ev = []                                     # the crawl found no non-English text anywhere
    assert LA.counted_evidence(ev, 'Google Translate') == []
    assert LA.verdict_for(ev, 'Google Translate') == 'machine_translate'


def test_the_fields_survive_the_round_trip_to_json():
    r = LA.Result(url='https://x.org/')
    r.switcher_languages = ['Somali', 'Spanish']
    r.switcher_unresolved = 12
    d = r.to_dict()
    assert d['switcher_languages'] == ['Somali', 'Spanish']
    assert d['switcher_unresolved'] == 12


def test_a_result_that_was_never_asked_has_the_unrecorded_default():
    """Every stored row written before this field existed reads as a site whose switcher was not
    looked at, which is what an empty list and a zero say."""
    r = LA.Result(url='https://x.org/')
    assert r.switcher_languages == []
    assert r.switcher_unresolved == 0


# ------------------------------------------------------------------------------------------------
# the stored capture


def test_rejudge_reads_the_switcher_off_the_stored_document():
    """A stored page is `page.content()`, which is the document the menu is rendered in, so this
    reproduces exactly and is deliberately NOT one of the things a re-judge cannot do."""
    rec = {'url': 'https://z.org/', 'verdict': 'machine_translate', 'note': '', 'pages_read': 1,
           'audited_at': '2026-07-30T00:00:00Z', 'tool_version': '0.2.0', 'evidence': [],
           'pages': {'https://z.org/': _page(
               '<div id="google_translate_element"></div>', GOOG_COMBO,
               '<p>We serve immigrants and refugees in the county.</p>')}}
    r = LA.rejudge(rec)
    assert r.switcher_languages == ['Afrikaans', 'Albanian']
    assert r.switcher_unresolved == 5
    # the field is reproducible, unlike the clicked controls beside it
    assert LA.REJUDGE_CLICKED_CONTROLS in r.unreproducible
    assert not any('switcher' in reason for reason in r.unreproducible)


def test_rejudge_of_a_record_with_no_switcher_answers_empty():
    rec = {'url': 'https://z.org/', 'verdict': 'english_only', 'note': '', 'pages_read': 1,
           'audited_at': '2026-07-30T00:00:00Z', 'tool_version': '0.2.0', 'evidence': [],
           'pages': {'https://z.org/': _page('<p>We serve immigrants and refugees.</p>')}}
    r = LA.rejudge(rec)
    assert r.switcher_languages == []
    assert r.switcher_unresolved == 0


# ------------------------------------------------------------------------------------------------
# the platform DECLARATION
#
# Every fragment below is synthetic, unlike the four capture cases above. A declaration is a
# structure and not a page: what has to be pinned is which structures are read and which are
# refused, and a captured page would carry one shape of the first and none of the second.
#
# The case that made this necessary is one Portuguese cultural centre, whose Wix menu is
# drawn by JavaScript, so the served document holds no code-carrying anchor and no labelled
# <select>, and whose same document names Portuguese and the address of its Portuguese tree in
# plain text. The audit read fifteen pages of that site and reported an empty switcher.

_WIX_ENTRY = ('{"languageCode":"%s","locale":"%s","countryCode":"%s","resolutionMethod":'
              '"Subdirectory","url":"%s","visitorPrimary":%s,"name":"%s","seoLang":"%s",'
              '"localizedName":"%s","isPrimaryLanguage":%s,"status":"%s"}')
_WIX_PT = _WIX_ENTRY % ('pt', 'pt-pt', 'PRT', 'https://x.example/pt', 'false', 'Portuguese',
                        'pt-pt', 'Portugues', 'false', 'Active')
_WIX_EN = _WIX_ENTRY % ('en', 'en-us', 'USA', 'https://x.example/', 'true', 'English',
                        'en-us', 'English', 'true', 'Active')


def _wix(*entries):
    return _page('<script>window.__cfg={"siteLanguages":[' + ','.join(entries) + ']};</script>'
                 '<p>The center offers classes and legal help to families in the county.</p>')


def test_a_wix_declaration_names_the_language_no_control_names():
    """The shape the whole change is for: a document with no switcher a reader can click and a
    declaration that says the site is published in Portuguese as well."""
    assert LA.switcher_languages(_wix(_WIX_PT, _WIX_EN)) == (['Portuguese'], 0)


def test_a_declaration_gives_the_address_of_the_tree_it_names():
    langs, unresolved, roots, off = LA.declared_languages(_wix(_WIX_PT, _WIX_EN),
                                                          'https://x.example/')
    assert langs == ['Portuguese'] and unresolved == []
    assert roots == ['https://x.example/pt'], 'the crawl reads this, and reads the page it reaches'
    assert off == {'alternates': 0, 'languages': []}, 'nothing left the site, so nothing is noted'


def test_a_language_the_owner_switched_off_is_not_on_offer():
    off = _WIX_ENTRY % ('pt', 'pt-pt', 'PRT', 'https://x.example/pt', 'false', 'Portuguese',
                        'pt-pt', 'Portugues', 'false', 'Inactive')
    assert LA.switcher_languages(_wix(off, _WIX_EN)) == ([], 0)


def test_a_declaration_off_another_site_keeps_its_language_and_says_the_address_left():
    """The observation, and not a refusal. An entry naming another host keeps its language, because
    the document does declare it, and the address it gave is recorded as having left the site."""
    other = _WIX_ENTRY % ('pt', 'pt-pt', 'PRT', 'https://elsewhere.example/pt', 'false',
                          'Portuguese', 'pt-pt', 'Portugues', 'false', 'Active')
    langs, unresolved, roots, off = LA.declared_languages(_wix(other, _WIX_EN),
                                                          'https://x.example/')
    assert langs == ['Portuguese'] and unresolved == []
    assert roots == [], "the crawl still does not fetch somebody else's page"
    assert off == {'alternates': 1, 'languages': ['Portuguese']}


def test_the_county_that_lapsed_declares_turkish_and_says_the_address_left():
    """One county let its domain lapse, and the address now answers with a
    Turkish gambling page whose single alternate is
    `hreflang="tr" href="https://tr.gambling-mirror11.example/"`.

    Refusing the language was written and measured on 2026-08-05: over the census render store it
    reached 153 organizations, and eleven of the nineteen hand-read moves took a language away from
    an organization that does publish it, on a second domain of its own. The document really does
    declare Turkish; what is wrong is that the address serves somebody else's site, and no document
    settles that. So the language is named and the observation is carried beside it.
    """
    head = '<link rel="alternate" hreflang="tr" href="https://tr.gambling-mirror11.example/"/>'
    langs, unresolved, roots, off = LA.declared_languages(_page(head), 'https://lapsed.example/')
    assert langs == ['Turkish'] and unresolved == [] and roots == []
    assert off == {'alternates': 1, 'languages': ['Turkish']}
    assert LA.switcher_languages(_page(head)) == (['Turkish'], 0), (
        'the menu is what a visitor is offered, and a visitor clicking it is offered Turkish')


def test_a_locale_subdomain_did_not_leave_the_site():
    """The observation is `_same_site`, the test the reading already uses, so an organization
    publishing its Spanish on `es.` of its own domain has nothing noted against it."""
    head = '<link rel="alternate" hreflang="es" href="https://es.x.example/"/>'
    langs, _un, roots, off = LA.declared_languages(_page(head), 'https://x.example/')
    assert langs == ['Spanish'] and roots == ['https://es.x.example/']
    assert off == {'alternates': 0, 'languages': []}


def test_a_language_declared_both_here_and_elsewhere_is_not_named_as_off_site():
    """`languages` in the observation is what NO alternate on this site named. A site that gives
    Spanish twice, once at home and once on a partner domain, has said where its Spanish is."""
    head = ('<link rel="alternate" hreflang="es" href="/es/"/>'
            '<link rel="alternate" hreflang="es-mx" href="https://partner.example/es/"/>'
            '<link rel="alternate" hreflang="vi" href="https://partner.example/vi/"/>')
    langs, _un, _roots, off = LA.declared_languages(_page(head), 'https://x.example/')
    assert langs == ['Spanish', 'Vietnamese']
    assert off == {'alternates': 2, 'languages': ['Vietnamese']}


def test_with_no_base_nothing_is_observed_because_no_site_was_named():
    """An observation has to be of something observed. With no address given there is no site for
    an alternate to leave, so the field is empty rather than false."""
    head = '<link rel="alternate" hreflang="tr" href="https://tr.gambling-mirror11.example/"/>'
    langs, _un, _roots, off = LA.declared_languages(_page(head))
    assert langs == ['Turkish']
    assert off == {'alternates': 0, 'languages': []}


def test_an_ordinary_json_array_of_language_codes_is_not_a_declaration():
    """The gate. A form's country list, a caption track list and an analytics payload all carry
    language codes, and reading any JSON that holds one would turn every such list into an offer of
    service. Only the named key of the named platform is read."""
    for js in ('<script>var opts={"countries":[{"languageCode":"pt","url":"/pt"}]};</script>',
               '<script>var t={"captionTracks":[{"languageCode":"vi","url":"/v.vtt"}]};</script>',
               '<script>var a={"languages":[{"languageCode":"ko","url":"/ko"}]};</script>'):
        assert LA.declared_languages(_page(js)) == ([], [], [], dict(LA.NO_OFF_SITE))


def test_an_entry_without_the_fields_of_the_structure_is_refused():
    """Named right and shaped wrong. `siteLanguages` on some other object is not Wix's."""
    js = '<script>var x={"siteLanguages":["pt","en"]};</script>'
    assert LA.declared_languages(_page(js)) == ([], [], [], dict(LA.NO_OFF_SITE))
    js = '<script>var x={"siteLanguages":[{"languageCode":"pt"}]};</script>'
    assert LA.declared_languages(_page(js)) == ([], [], [], dict(LA.NO_OFF_SITE))


def test_an_hreflang_alternate_is_a_declaration_too():
    """The standard form, which `_routes` has always read for its ADDRESS and which nothing read
    for its LANGUAGE, so a site declaring its alternates only in the head reported no switcher."""
    head = ('<link rel="alternate" hreflang="es" href="/es/"/>'
            '<link rel="alternate" hreflang="vi" href="/vi/"/>'
            '<link rel="alternate" hreflang="en" href="/"/>'
            '<link rel="alternate" hreflang="x-default" href="/"/>')
    assert LA.switcher_languages(_page(head)) == (['Spanish', 'Vietnamese'], 0)
    langs, _un, roots, off = LA.declared_languages(_page(head), 'https://x.example/')
    assert roots == ['https://x.example/es/', 'https://x.example/vi/']
    assert off == {'alternates': 0, 'languages': []}


def test_a_declared_language_this_package_cannot_name_is_counted_not_dropped():
    """The same honesty the menu reader keeps: a list of names with unknowns beside it is a
    different fact from a list of names alone."""
    head = '<link rel="alternate" hreflang="es" href="/es/"/><link hreflang="ab" href="/ab/"/>'
    assert LA.switcher_languages(_page(head)) == (['Spanish'], 1)


def test_a_declaration_moves_no_class():
    """`switcher_languages` is a statement about a MENU and the verdict is a statement about the
    writing. A site that declares Portuguese and serves nothing at the address it names is
    english_only, and rule 17's count of advertised roots is not fed from here either."""
    import asyncio

    from test_engineering import _MapBrowser
    home = _wix(_WIX_PT, _WIX_EN)
    r = asyncio.run(LA._audit_async('https://x.example/',
                                    browser=_MapBrowser({'https://x.example/': (home, 'The center '
                                                         'offers classes and legal help to '
                                                         'families in the county.', 200)})))
    assert r.verdict == 'english_only' and r.languages == []
    assert r.switcher_languages == ['Portuguese']
    assert 17 not in r.rules


# ---------------------------------------------------------------------------------------------
# The vocabulary's own invariants. Each case below is a string a real switcher writes, and each was
# read wrongly by the shipped instrument until 2026-08-07.


def test_no_name_for_english_already_meant_another_language():
    """The collision the English list could have introduced, asserted rather than hoped for.

    `ENGLISH_EXONYM` is looked up in the same table as every other switcher label, so an entry that
    already meant something else would silently retire that language. This checks each token
    against the vocabulary as it stands WITHOUT the English list, which is the only way to ask the
    question: with the list in, every token resolves to English by construction.

    It found one. `af-ingiriisi`, which is Somali for the English language, resolved to AFRIKAANS,
    because the lookup took the part before the hyphen and `af` is the Afrikaans code. The same
    fault hit `af-soomaali`, which is how a Somali switcher writes Somali itself, so the language
    was read as Afrikaans on the sites most likely to offer it.
    """
    clean = dict(LA.LANG_TOKEN)
    for tok in LA.ENGLISH_EXONYM:
        clean.pop(LA._nfc(tok), None)
    wrong = {tok: LA._lookup_language(clean, tok) for tok in LA.ENGLISH_EXONYM}
    wrong = {k: v for k, v in wrong.items() if v and v != LA.SWITCHER_ENGLISH}
    assert wrong == {}, 'these already meant another language: %r' % wrong


@pytest.mark.parametrize('label', ['Ingl\u00e9s', 'Ingles', '\u82f1\u8a9e', '\u82f1\u8bed',
                                   '\uc601\uc5b4', 'Anglais',
                                   '\u0410\u043d\u0433\u043b\u0438\u0439\u0441\u043a\u0438\u0439',
                                   'Ti\u1ebfng Anh', 'Englisch', 'Af-Ingiriisi'])
def test_english_is_recognised_when_the_menu_is_not_written_in_english(label):
    """A menu rendered in the visitor's language writes its English option in that language. Read
    as anything else, the option is a language control that produced no language, which is the
    dead-control observation, which is `control_dead`, which is machine_translate_error under
    rule 16."""
    assert LA._lookup_language(LA.LANG_TOKEN, label) == LA.SWITCHER_ENGLISH


@pytest.mark.parametrize('label,want', [
    ('Af-Soomaali', 'Somali'), ('af soomaali', 'Somali'), ('AfSoomaali', 'Somali'),
    ('zh-Hans', 'Chinese'), ('pt-BR', 'Portuguese'), ('es-MX', 'Spanish'), ('fr-CA', 'French'),
])
def test_the_hyphen_split_reads_a_region_tag_and_not_an_ordinary_word(label, want):
    """Taking the part before a hyphen is for `zh-Hans` and `pt-BR`. Applied to any hyphenated
    word it reads the head as a code, and two-letter codes are dense enough that most heads hit
    one. `BCP47_SHAPE` is what licenses the split."""
    assert LA._lookup_language(LA.LANG_TOKEN, label) == want


@pytest.mark.parametrize('label', ['Espa\u00f1ol', 'Ti\u1ebfng Vi\u1ec7t', 'Fran\u00e7ais',
                                   'Portugu\u00eas', 'Krey\u00f2l', 'T\u00fcrk\u00e7e',
                                   'Rom\u00e2n\u0103', 'Latvie\u0161u'])
def test_a_decomposed_autonym_resolves_like_a_composed_one(label):
    """Both spellings render identically and nothing on the page says which one it used, so a
    vocabulary holding only the composed form has entries a decomposed page can never reach.
    WordPress and Drupal both emit decomposed text on some paths."""
    import unicodedata
    nfd = unicodedata.normalize('NFD', label)
    assert nfd != label, 'this case is not testing anything: %r has no decomposed form' % label
    assert LA._lookup_language(LA.LANG_TOKEN, nfd) == LA._lookup_language(LA.LANG_TOKEN, label)
    assert LA._lookup_language(LA.LANG_TOKEN, nfd) != ''


@pytest.mark.parametrize('label', ['Somalia', 'Russian Federation', 'French Guiana',
                                   'French Polynesia', 'Germany', 'Thailand', 'Cambodia'])
def test_a_country_option_is_not_a_language_control(label):
    """A form's country list carries language names inside it, and a control that is worked and
    changes nothing is RECORDED as dead, which returns machine_translate_error under rule 16.
    So a country
    entry reaching the click vocabulary is a wrong verdict and not a wasted click."""
    assert LA._langlabel(label) is None
    assert LA._lookup_language(LA.LANG_TOKEN, label) == ''


@pytest.mark.parametrize('label', ['Espa\u00f1ol', 'En Espa\u00f1ol', '\u4e2d\u6587',
                                   '\u4e2d\u6587\u7248', '\ud55c\uad6d\uc5b4', 'Deutsch',
                                   'T\u00fcrk\u00e7e', 'Hmoob', 'Shqip', 'Magyar',
                                   'Krey\u00f2l Ayisyen', 'Soomaali',
                                   '\u067e\u069a\u062a\u0648'])
def test_a_label_the_package_can_name_a_language_for_is_a_label_it_will_work(label):
    """The invariant `_click_vocabulary` exists to make true. Before it the click vocabulary was a
    hand-written thirty beside a switcher vocabulary of 153, and seven of these thirteen could be
    resolved once a switcher was found and never clicked."""
    assert LA._langlabel(label) is not None


def test_english_is_not_a_click_candidate():
    """It reached the generated vocabulary through COVERED, which has listed English since the
    reader began naming it. Measured over the 927 stored documents of the validation capture, the
    label `English` occurs 3,600 times under the label cap, more than any other token the
    generation admits, and every one is a control whose click produces English on a page that is
    already English. `limit` counts controls WORKED, so each is a click-settle-read-navigate cycle
    a real second language then does not get."""
    for label in ('English', 'en', 'Ingl\u00e9s', '\u82f1\u8a9e', '\uc601\uc5b4'):
        assert LA._langlabel(label) is None, label
    # and the languages either side of it in the same vocabulary are still candidates
    for label in ('Espa\u00f1ol', 'Deutsch', '\u4e2d\u6587', 'Hmoob'):
        assert LA._langlabel(label) is not None, label


def test_the_menu_threshold_sits_in_the_gap_between_the_two_populations():
    """MENU_SIZE is read off the capture and not chosen: distinct language-named labels per page
    run 0, then 1 to 28 for authored switchers, then nothing at all until 39, then 2,007 documents
    at 73 to 97 which are one vendor menu. A threshold on either population's edge would move with
    the next capture; one in the empty gap does not."""
    assert 28 < LA.MENU_SIZE < 39, LA.MENU_SIZE
    assert LA.SELECT_OPTION_CANDIDATES < LA.MENU_SIZE


class _StubEl:
    """One clickable thing. Records that it was worked and reports the page it swaps to."""

    def __init__(self, page, tag, label, href='#', produces=None):
        self.page, self.tag, self.label, self.href = page, tag, label, href
        self.produces = produces          # the body text a click swaps in, or None for no change

    async def inner_text(self):
        return self.label

    async def evaluate(self, js, *a):
        if 'tagName' in js:
            return self.tag.upper()
        if 'closest' in js:               # the per-select tally
            return -1
        return None

    async def get_attribute(self, name):
        return self.href if name == 'href' else None

    async def is_visible(self):
        return True

    async def bounding_box(self):
        return {'x': 0, 'y': 0, 'width': 40, 'height': 20}

    async def click(self, timeout=None):
        self.page.worked.append(self.label)
        if self.produces is not None:
            self.page.body = self.produces


class _StubPage:
    """Enough of a page for `_click_language_controls`, and nothing else."""

    def __init__(self, els, body='Welcome to the center. We help families every day of the week.'):
        self.url = 'https://x.example/'
        self.body = body
        self.worked = []
        self._els = els
        for e in els:
            e.page = self

    async def query_selector_all(self, sel):
        return list(self._els)

    async def evaluate(self, js, *a):
        return None

    async def inner_text(self, sel):
        return self.body

    async def wait_for_timeout(self, ms):
        return None

    async def goto(self, url, **kw):
        return None

    async def query_selector(self, sel):
        return None


NAMES = ['Afrikaans', 'Albanian', 'Amharic', 'Arabic', 'Armenian', 'Assamese', 'Azerbaijani',
         'Basque', 'Bengali', 'Bosnian', 'Bulgarian', 'Catalan', 'Chinese', 'Croatian', 'Czech',
         'Danish', 'Dutch', 'Estonian', 'Filipino', 'Finnish', 'French', 'Galician', 'Georgian',
         'German', 'Greek', 'Gujarati', 'Hebrew', 'Hindi', 'Hungarian', 'Icelandic', 'Indonesian',
         'Irish', 'Italian', 'Japanese', 'Kannada', 'Kazakh', 'Khmer', 'Korean', 'Lao', 'Latvian']


def _work(els, limit=8):
    import asyncio
    page = _StubPage(els)
    out, dead, _stuck = asyncio.run(LA._click_language_controls(
        page, page.body, 'https://x.example/', limit=limit))
    return page.worked, out, dead


def test_a_vendor_menu_does_not_spend_the_control_budget():
    """A hundred-language menu is presented in alphabetical order, so working controls in document
    order works Afrikaans, Albanian and Amharic and never reaches the language the organization
    publishes in. The page is counted before anything is worked, and a page over MENU_SIZE gets
    SELECT_OPTION_CANDIDATES controls rather than `limit` of them.

    Driven against a stub rather than through `_audit_async`, because the first version of this
    test went through the map browser and passed with MENU_SIZE set to 9999.
    """
    assert len(NAMES) > LA.MENU_SIZE, 'the fixture is not a menu under this threshold'
    worked, _out, _dead = _work([_StubEl(None, 'a', n) for n in NAMES], limit=8)
    assert len(worked) == LA.SELECT_OPTION_CANDIDATES, worked
    assert worked == NAMES[:LA.SELECT_OPTION_CANDIDATES], worked


def test_an_authored_switcher_still_gets_the_whole_budget():
    """The negative side, and the one that says the threshold is not simply a cap on everything.
    A page under MENU_SIZE is a set of controls worth working one by one, and it gets `limit`."""
    six = ['Espa\u00f1ol', '\u4e2d\u6587', 'Ti\u1ebfng Vi\u1ec7t', '\ud55c\uad6d\uc5b4',
           'Soomaali', 'Krey\u00f2l']
    assert len(six) < LA.MENU_SIZE
    worked, _out, _dead = _work([_StubEl(None, 'a', n) for n in six], limit=8)
    assert worked == six, worked


def test_the_menu_rule_is_what_produces_that_difference():
    """The known-answer check on the rule itself: the same forty controls, with the threshold
    lifted above them, are worked to the limit. Without this the first test would pass on a build
    where MENU_SIZE did nothing, which is how it was written the first time."""
    saved = LA.MENU_SIZE
    try:
        LA.MENU_SIZE = 9999
        worked, _out, _dead = _work([_StubEl(None, 'a', n) for n in NAMES], limit=8)
        assert len(worked) == 8, worked
    finally:
        LA.MENU_SIZE = saved
