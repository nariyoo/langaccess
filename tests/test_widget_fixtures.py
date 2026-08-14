# -*- coding: utf-8 -*-
"""Known-answer cases for the widget patterns, taken from a measured corpus rather than from a list.

The cases in `fixtures/widget_fixtures.json` were cut out of a July 2026 website capture of a
national census of immigrant-serving organizations: 45,100 distinct organizations, 15.5 GB of
server and rendered documents. Each case carries the exact bytes a pattern matched and 100 characters of context either
side, so what is asserted here is what a real page really contained on a stated day, not a string
somebody wrote to make a regex pass.

The file is COPIED into the package on purpose. The capture lives outside this repository, on a
different drive, and a test that reads it there is a test that stops running when the drive is not
mounted.

A case carries the quoted bytes and no identifier of the organization they were cut from. The EIN
was taken out on 2026-08-05 and replaced by an opaque `case` handle, because a taxpayer number
identifies an organization as a legal entity and nothing here needs one, and the site's own ADDRESS
was taken out the same way on 2026-08-07: `url` holds that handle, and `page` holds the path a match
was found at under a placeholder host built from it, so a reading is still published with the
channel, the path and the bytes. `document` is the one field that was renamed with the EIN. It
says what a match's bytes ARE, `server` or `rendered`, which is what several of these cases turn on,
in place of the name a store on that other drive happens to be filed under. The excerpts are
verbatim except where a page quoted its own address or its own name, which read as that placeholder
host and as an invented name of the same shape and the same length; every vendor marker, asset path,
class name and count around them is the byte the capture held. `weglot_injected_client_side` also
carried that site's own Weglot key in its script address, and the key reads `REDACTED` here. It is
somebody else's credential and no pattern in this package looks at it.

What these cases are for, in the order the failures happened:

  Two patterns named a vendor that was not installed. `smartling` as a bare token matched the key
  "smartling" inside a shop platform's data-localized-strings JSON on 15 of the 18 organizations it
  matched at all, and `crowdin`, which was on nobody's list here and is on plenty of vendor lists,
  matches the English word "overcrowding" on all 131 of its static matches. Under rule 14 a
  widget that never renders is still a widget, so either of those moves a site to machine_translate
  on nothing. `smartling_false_positive` and `crowdin_substring_false_positive` are the gate, and
  `smartling_real` is the contrast: the vendor's own body class, which is what the pattern asks for.

  Four vendors had no pattern at all. MotionPoint, the Elfsight translator, Wix Multilingual and
  UserWay are each pinned by a case, and each is pinned to the list it belongs on: the first two
  name a machine translation, the second two only say machinery is present.

  MT_RX and MT_NAME disagreed about the same bytes. `google_loader_only_no_runtime` is the case
  that showed it, and `test_MT_RX_answers_for_every_marker_MT_NAME_can_name` is the invariant.
"""
import asyncio
import json
import os
import re

import pytest

from langaccess import core as LA
from test_engineering import _MapBrowser, _page


FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fixtures',
                        'widget_fixtures.json')
CASES = json.load(open(FIXTURES, encoding='utf-8'))
BY_ID = {c['id']: c for c in CASES}


# What this package should say about the QUOTED BYTES of each case, and nothing more. Three entries
# say '' where the case's own prose names a vendor, and those are the honest answers, not gaps in
# the table: the 100-character window holds the bytes the corpus scan matched, and on those three
# the scan matched an asset this package deliberately does not look at. They are marked.
#
#   id -> (vendor MT_NAME names, vendors AMBIGUOUS_NAME names, the CMS_RX marker, why)
EXPECTED = {
    'google_element_consent_gate': (
        'Google Translate', (), '',
        'the loader in the server document, with the widget node in neither document. Rule 14: a '
        'widget that never appears is still a widget, so the loader has to name it.'),
    'google_loader_only_no_runtime': (
        'Google Translate', (), '',
        'a loader and no content anywhere. This is also the case that caught MT_RX and MT_NAME '
        'disagreeing: the loader address was in one and not the other.'),
    'google_runtime_render_only': (
        'Google Translate', (), '',
        "NAMED off the widget's RUNTIME, which is a different marker from its loader and behaves "
        'the opposite way: translate.googleapis.com/_/translate_http/ is in 0 server documents in '
        'the whole capture and in 610 rendered ones, where the loader is in 549 server documents. '
        'Until 2026-08-01 no pattern here looked at it and this case pinned the non-detection. It '
        'names 11 organizations nothing else names, over a loader that covers 549 of the 606.'),
    'wpml_with_authored_content': (
        '', (), 'wpml',
        'a server-side plugin, not a widget. Rule 11 decides what the marker is worth.'),
    'wpml_chinese_both_documents': (
        '', (), 'polylang',
        'Polylang, Chinese in the server response. Same shape as the case above.'),
    'weglot_injected_client_side': (
        'Weglot', (), '',
        'Weglot in no server document at all, because another script injects it. 197 of the 405 '
        'rendered installs in the capture are like this, which is why Weglot is not in '
        'CLIENT_SIDE_WIDGET and why a server-only reader cannot settle it.'),
    'weglot_in_server_document': (
        'Weglot', (), '', 'the same vendor, this time in the server response.'),
    'proxy_and_bare_link': (
        '', (), '',
        'NOT NAMED OFF THE BYTES ALONE, which is what `_named` asks here and what this case has '
        'always pinned. The quoted bytes are a "Translate this site" hyperlink to '
        'translate.google.com, and on the document alone nothing says where it points. Given the '
        "site's own address it does: the target is the host serving the link, "
        'and `widget_name(bytes, url)` names Google Translate. '
        '`test_an_own_target_google_translate_link_is_a_control_and_a_bare_one_is_not` is that '
        'half, on these same bytes.'),
    'wix_locale_mirrors_no_marker': (
        '', (), '',
        'eight locale subdomains and no vendor marker anywhere. Nothing names this and nothing '
        'should: it is what rule 17 counts, and 312 organizations in the capture have '
        'this exact shape.'),
    'locale_mirrors_unknown_platform': (
        '', (), '',
        'fourteen locale paths on a platform the capture cannot identify. Rule 17 again.'),
    'widget_marker_no_nonenglish': (
        'Google Translate', (), '',
        'a widget marker with no non-English text behind it. Google Translate rather than '
        'GTranslate because MT_NAME is an ordered list and the Google alternative is first.'),
    'motionpoint_server_proxy': (
        'MotionPoint', (), '',
        'a SERVER-side proxy. Named as a machine translation, and kept out of CLIENT_SIDE_WIDGET, '
        'because its output IS the server response.'),
    'elfsight_website_translator': (
        'Elfsight Website Translator', (), '',
        'an ordinary commercial browser widget with no pattern anywhere before this.'),
    'smartling_false_positive': (
        '', (), '',
        'THE REGRESSION GATE. The word smartling here is a key inside a data-localized-strings '
        'JSON blob a shop platform emits on every page. The bare token named a vendor on 15 '
        'organizations that do not run it.'),
    'crowdin_substring_false_positive': (
        '', (), '',
        'THE OTHER GATE. The bytes are the English word "overcrowding". No constant here carries '
        'crowdin and this case is why none ever should.'),
    'smartling_real': (
        'Smartling', (), '',
        "the contrast case: the vendor's own smartling-es body class on the Spanish route."),
    'userway_live_translations': (
        '', ('UserWay',), '',
        'an accessibility widget that also ships a live translation module. Named, and named as '
        'ambiguous: the asset path says translations, the presence of the widget does not say the '
        'module was ever configured.'),
    'wix_multilingual_linguist': (
        '', ('Wix Multilingual',), '',
        'the largest single naming gap in the capture, 145 organizations named by nothing else. '
        'Ambiguous, because Wix serves an authored and a machine translation through the same '
        'selector.'),
    'squarespace_google_translate': (
        'Google Translate', (), '', 'the Google element behind a Squarespace styling helper.'),
    'adabundle_google_translate': (
        '', (), '',
        "NOT NAMED. The case is about a renamed callback, adabundleGoogleTranslateElementInit, "
        "which MT_NAME does match; the quoted 100-character window holds the plugin's stylesheet "
        'and script instead, and this package does not fingerprint the plugin itself.'),
    'gtranslate_tdn_proxy': (
        'GTranslate', (), '', 'the same vendor in its proxy deployment.'),
    'goog_te_marker_is_css': (
        'Google Translate', (), '',
        'the only goog-te bytes in the server response are stylesheet rules that hide the '
        "widget's own nodes. Still a widget under rule 14, and the case records that this is a "
        'weaker piece of evidence than it looks.'),
    'localize_real': (
        '', (), '',
        "NOT NAMED. The quoted bytes are Localize's own CSS class names, localize-powered-by and "
        'localize-dark. MT_NAME asks for `localizejs`, which is the vendor domain and the script, '
        'and the bare token `localize` is not usable: it is an ordinary English word.'),
    'widget_menu_read_as_language': (
        'Weglot', (), '',
        'a negative case for the language reader, kept here for the vendor it does carry.'),
}


def _named(text):
    """Everything this package can say about one document: vendor, ambiguous vendor, plugin."""
    return (LA.widget_name(text),
            tuple(nm for nm, pat in LA.AMBIGUOUS_NAME if re.search(pat, text, re.I)),
            (LA.CMS_RX.search(text).group(0).lower() if LA.CMS_RX.search(text) else ''))


def test_the_fixture_file_is_whole():
    """24 organizations and 66 quoted matches, which is what the corpus report states it wrote.

    A copied file can be truncated by the copy, and a data-driven suite whose data quietly shrank
    reports every remaining case passing.
    """
    assert len(CASES) == 24
    assert sum(len(c['matches']) for c in CASES) == 66
    assert set(BY_ID) == set(EXPECTED), 'every case has a recorded expected answer'
    for c in CASES:
        for m in c['matches']:
            assert m['matched_bytes'] in m['context'], (
                c['id'] + ': the quoted bytes have to be inside the quoted context, or the case '
                'is not evidence of anything')


@pytest.mark.parametrize('case_id', sorted(EXPECTED))
def test_each_corpus_case_is_read_the_way_the_corpus_says(case_id):
    """Every quoted match of a case, put through the constants, answers what the case pins."""
    vendor, ambiguous, cms, why = EXPECTED[case_id]
    case = BY_ID[case_id]
    got_v, got_a, got_c = set(), set(), set()
    for m in case['matches']:
        v, a, c = _named(m['context'])
        got_v.add(v)
        got_a.add(a)
        got_c.add(c)
    assert got_v == {vendor}, f'{case_id}: {why}'
    assert got_a == {tuple(ambiguous)}, f'{case_id}: {why}'
    assert got_c == {cms}, f'{case_id}: {why}'


@pytest.mark.parametrize('case_id', sorted(EXPECTED))
def test_the_kind_of_every_named_vendor_is_recorded(case_id):
    """Detecting a vendor is not the finding; what the marker ESTABLISHES is.

    A name in MT_NAME asserts that a machine produced the second language. A name in AMBIGUOUS_NAME
    asserts only that machinery is present. WIDGET_KIND is where that difference is written down,
    and this pins that no vendor can be named without it being written down.
    """
    vendor, ambiguous, _cms, why = EXPECTED[case_id]
    for nm in ([vendor] if vendor else []):
        assert LA.WIDGET_KIND[nm][0] == 'machine_translate', why
    for nm in ambiguous:
        assert LA.WIDGET_KIND[nm][0] == 'ambiguous', why


@pytest.mark.parametrize('case_id', sorted(EXPECTED))
def test_MT_RX_answers_for_every_marker_MT_NAME_can_name(case_id):
    """MT_RX is the public "is there any translation machinery here" test, and it used to answer
    the opposite of MT_NAME on a real page.

    MT_NAME names Google Translate off its loader and its callback; neither of those was in MT_RX,
    so a consent-gated install was a widget to the audit and no widget at all to a caller testing
    the same stored bytes. 67 organizations in the capture carry the loader or the callback and
    nothing else MT_RX knew. The invariant is both ways round on these cases: MT_RX matches exactly
    where some name was found.
    """
    vendor, ambiguous, _cms, why = EXPECTED[case_id]
    expected = bool(vendor or ambiguous)
    for m in BY_ID[case_id]['matches']:
        assert bool(LA.MT_RX.search(m['context'])) is expected, f'{case_id}: {why}'


def test_the_two_false_vendor_markers_stay_dead():
    """The narrowing, stated as the two exact byte strings that used to break it.

    Kept separate from the parametrised cases above so that the shape of the mistake is readable
    without opening a JSON file: a vendor name that is also an ordinary JSON key, and a vendor name
    that is also an ordinary English word.
    """
    shop_json = 'data-localized-strings="{&quot;smartling&quot;:{&quot;string_format&quot;'
    assert LA.widget_name(shop_json) == ''
    assert not LA.MT_RX.search(shop_json)
    assert not LA.ROUTE_WIDGET.search(shop_json)

    prose = 'subpar housing plagued with overcrowding and unsanitary conditions'
    assert LA.widget_name(prose) == ''
    assert not LA.MT_RX.search(prose)

    # and the real installs the narrowing has to keep, both alternatives, since neither finds both
    assert LA.widget_name('hellotools is_translated lang-es is_safari smartling-es"') == 'Smartling'
    assert LA.widget_name(
        '<script src="https://pinchjs-cdn.gdn.smartling.com/sl-tran-935b68372-es-LA.js">'
    ) == 'Smartling'


def test_the_vendor_lists_and_the_kind_table_agree():
    """One vendor cannot be a machine translation in one list and ambiguous in another.

    Three lists now, not two. MT_ADDRESS_NAME holds the vendors `widget_name` reaches off an
    ADDRESS rather than off a byte pattern, and it is a tuple of names because the freeze hashes
    every module-level assignment and a function object renders with its memory address. Every name
    in it carries a kind for the same reason every name in the other two does: detecting a vendor is
    not the finding, and what the marker ESTABLISHES is.
    """
    mt = [nm for nm, _ in LA.MT_NAME]
    amb = [nm for nm, _ in LA.AMBIGUOUS_NAME]
    addr = list(LA.MT_ADDRESS_NAME)
    assert len(set(mt)) == len(mt) and len(set(amb)) == len(amb), 'no vendor named twice'
    assert len(set(addr)) == len(addr), 'no vendor named twice by an address either'
    assert not set(mt) & set(amb), 'a vendor is on one list or the other'
    assert not set(addr) & set(amb), 'an address fingerprint cannot name an ambiguous vendor'
    assert set(mt) | set(amb) | set(addr) == set(LA.WIDGET_KIND), (
        'every named vendor has a recorded kind')
    for nm in mt + addr:
        assert LA.WIDGET_KIND[nm][0] == 'machine_translate'
    for nm in amb:
        assert LA.WIDGET_KIND[nm][0] == 'ambiguous'


def test_only_browser_side_widgets_let_the_server_document_settle_authorship():
    """CLIENT_SIDE_WIDGET is the list whose output provably cannot be in the server response.

    The mechanism is measured: Google Translate's runtime script, stylesheet and product logo are
    in 0 server documents of 23,997 paired organizations and in 610, 616 and 533 rendered ones. A
    vendor that serves an already-translated page from its own machines breaks that, so a server
    proxy must never be on this list, and neither must a vendor sold in both shapes.
    """
    for nm in LA.CLIENT_SIDE_WIDGET:
        assert LA.WIDGET_KIND[nm] == ('machine_translate', 'client_widget'), nm
    assert 'MotionPoint' not in LA.CLIENT_SIDE_WIDGET, 'a server proxy is not a browser widget'
    assert LA.WIDGET_KIND['MotionPoint'][1] == 'server_proxy'
    # 197 of 405 rendered Weglot installs are in no server document at all
    for sold_both_ways in ('Weglot', 'Localize', 'Bablic', 'Smartling'):
        assert sold_both_ways not in LA.CLIENT_SIDE_WIDGET
        assert LA.WIDGET_KIND[sold_both_ways][1] == 'ambiguous'


def test_the_dead_alternatives_are_the_ones_that_were_measured_dead():
    """Three alternatives that fired on nothing, one kept and two removed, each on its own reason.

    `doGTranslate` is removed because removing it provably changes no match: the patterns compile
    case-insensitively and the string contains `GTranslate`. `sitepress` is kept: it was measured
    adding 0 organizations on 45,100, the removal is not provable from the pattern, and a folder
    name a plugin really uses is a recall question. `pll_` is the one that proves the exercise was
    worth doing, adding 207 organizations that never emit the word polylang.

    `qtranxf` WAS kept on the same reasoning as `sitepress` and that reasoning turned out to be
    wrong, which is why it is now the third case rather than the second. It was read as "a plugin
    that exists in the world and not in this capture". The leakage measurement of 2026-08-04 found
    qTranslate-X/XT running on 37 organizations of the census render store, every one of them
    emitting `qtranslate_lang` and not one emitting `qtranxf`: the plugin was in the corpus all
    along and the token was the wrong one. `qtranslate` names all 37 and subsumes anything `qtranxf`
    could have found, because the plugin serves itself out of a `qtranslate-x` folder.
    """
    assert 'doGTranslate'.lower() not in LA.MT_RX.pattern.lower()
    assert not any('dogtranslate' in pat.lower() for _nm, pat in LA.MT_NAME)
    assert 'dogtranslate' not in LA.ROUTE_WIDGET.pattern.lower()
    # and its removal really is a no-op, which is the whole argument for removing it
    assert LA.MT_RX.search('doGTranslate')
    assert LA.widget_name('<script>doGTranslate(this);</script>') == 'GTranslate'

    assert 'sitepress' in LA.CMS_RX.pattern
    assert 'pll_' in LA.CMS_RX.pattern
    assert LA.CMS_RX.search('var pll_data = {}')

    # the dead token, the live one, and the folder that makes the replacement a superset
    assert 'qtranxf' not in LA.CMS_RX.pattern
    assert not LA.CMS_RX.search('qtranxf_conf')
    assert LA.CMS_RX.search('<meta name="qtranslate_lang" content="es">').group(0) == 'qtranslate'
    assert LA.CMS_RX.search('/wp-content/plugins/qtranslate-xt/qtranslate.css')
    assert LA.CMS_RX.search('/wp-content/plugins/wpglobus/includes/js/wpglobus.js')


def test_the_new_vendors_are_named_off_the_patterns_the_corpus_measured():
    """The four gaps, each on the address the capture found it at.

    One site's own module folder was prefixed with that organization's initials, and the prefix
    reads `org_` here. The vendor token inside it is all of what the pattern reads.
    """
    assert LA.widget_name(
        'src="https://universe-static.elfsightcdn.com/app-releases/website-translator/stable/'
        'v1.13.1/0745e/widget/websiteTranslator.js"') == 'Elfsight Website Translator'
    assert LA.widget_name(
        'src="/modules/custom/org_international_motionpoint_language_toggle/js/mp_linkcode.js"'
    ) == 'MotionPoint'
    assert LA.widget_name(
        "<!--Processed by MotionPoint's TransMotion (r) translation engine v22.46.6-->"
    ) == 'MotionPoint'
    # the guard on the MotionPoint token, which is what keeps it out of ordinary prose. It cost
    # nothing on the capture: guarded and unguarded matched the same 52 organizations.
    assert LA.widget_name('id="promotionpoints" class="promotionpoint"') == ''

    wix = 'src="https://static.parastorage.com/services/linguist-flags/1.1005.0/assets/flags/'
    assert LA.widget_name(wix) == '', 'a platform selector is not a machine translation'
    assert ([nm for nm, pat in LA.AMBIGUOUS_NAME if re.search(pat, wix, re.I)]
            == ['Wix Multilingual'])
    assert LA.MT_RX.search(wix), 'it is still translation machinery, and MT_RX is that question'

    uw = 'src="https://cdn.userway.org/widgetapp/2026-07-07-10-43-48/translations/live_x.js"'
    assert LA.widget_name(uw) == ''
    assert [nm for nm, pat in LA.AMBIGUOUS_NAME if re.search(pat, uw, re.I)] == ['UserWay']
    # and the accessibility widget WITHOUT the translation module is not translation machinery
    assert not LA.MT_RX.search('src="https://cdn.userway.org/widget.js"')


def test_the_six_vendors_of_the_leakage_measurement_are_named():
    """One address per vendor, each taken verbatim off the organization the corpus found it on.

    `true_multilingual` is defined by exclusion, so every machine translator the instrument cannot
    name inflates the class it exists to find. These six were measured on 2026-08-04 over the census
    render store, about 21 organizations between them, and each byte string below was re-read in
    context on the site named beside it.
    """
    assert LA.widget_name(
        'src="/wp-content/plugins/transposh-translation-filter-for-wordpress/js/'
        'transposh-js-extra.js"') == 'Transposh'
    assert LA.widget_name(
        'id="widget_prisna-google-website-translator-2" class="widget prisna-wp-translate"'
    ) == 'Prisna Website Translator'
    assert LA.widget_name(
        'href="/wp-content/plugins/linguise/assets/css/front.bundle.css?ver=2.2.23"') == 'Linguise'
    assert LA.widget_name('<div id="linguise_popup_container"></div>') == 'Linguise'
    assert LA.widget_name(
        'src="//app.easyling.com/client/asl38rvv/0/stub.js?disableSelector=true"') == 'Easyling'
    assert LA.widget_name(
        'src="https://ssl.microsofttranslator.com/ajax/v3/WidgetV3.ashx?siteData=ueOIGRSKkd9"'
    ) == 'Microsoft Translator'
    assert LA.widget_name('<div id="MicrosoftTranslatorWidget"></div>') == 'Microsoft Translator'
    assert LA.widget_name(
        'src="https://translate.yandex.net/website-widget/v1/widget.js?widgetId=ytWidget"'
    ) == 'Yandex Translate'
    # every one of them is also translation machinery to a caller testing the bytes, which is the
    # invariant MT_NAME and MT_RX broke on the Google loader once already
    for asset in ('/plugins/transposh-translation-filter-for-wordpress/',
                  'widget_prisna-google-website-translator-2', 'linguise_popup_container',
                  '//app.easyling.com/client/x/0/stub.js',
                  'ssl.microsofttranslator.com/ajax/v3/WidgetV3.ashx',
                  'translate.yandex.net/website-widget/v1/widget.js'):
        assert LA.MT_RX.search(asset), asset

    # THE THREE THAT ROUTE. Transposh, Linguise and Easyling each serve their translation at an
    # address of its own, so rule 15 can ask whether that address came back in English. The Microsoft
    # and Yandex widgets rewrite the page in place and publish no address, and neither does Prisna,
    # which wraps the Google element.
    assert LA.ROUTE_WIDGET.search('/plugins/transposh-translation-filter-for-wordpress/')
    assert LA.ROUTE_WIDGET.search('/wp-content/plugins/linguise/assets/js/front.bundle.js')
    assert LA.ROUTE_WIDGET.search('//app.easyling.com/client/asl38rvv/0/stub.js')
    assert not LA.ROUTE_WIDGET.search('ssl.microsofttranslator.com/ajax/v3/WidgetV3.ashx')
    assert not LA.ROUTE_WIDGET.search('translate.yandex.net/website-widget/v1/widget.js')
    assert not LA.ROUTE_WIDGET.search('widget_prisna-google-website-translator-2')

    # THE SECOND WIX MARKER, beside the flag assets and answering the same limited question. 731
    # organizations of the render store carry it and 145 of the flag-asset installs were named by
    # nothing else, so this is a recall addition to a name the package deliberately does not act on.
    sel = ('static.parastorage.com/services/editor-elements-library/dist/thunderbolt/'
           'rb_wixui.thunderbolt[LanguageSelector].abc123.bundle.min.js')
    assert LA.widget_name(sel) == '', 'a platform selector is not a machine translation'
    assert [nm for nm, pat in LA.AMBIGUOUS_NAME if re.search(pat, sel, re.I)] == ['Wix Multilingual']
    assert LA.MT_RX.search(sel)

    # THE THREE FALSE FINGERPRINTS, confirmed in context by the same measurement and named here so
    # that a later vendor list cannot put them back without this test going red.
    for prose, why in (
            ('<a href="/donate">Give through MillionBridges</a>', 'lionbridge inside MillionBridges'),
            ('href="https://catalog.smartcatalogiq.com/en/2024-2025/Catalog"', 'smartcat inside '
             'smartcatalogiq'),
            ('<div class="smartcat_our_team">Our team</div>', 'smartcat as a staff plugin'),
            ('families living in overcrowding and unsanitary conditions', 'crowdin inside '
             'overcrowding')):
        assert LA.widget_name(prose) == '', why
        assert not LA.MT_RX.search(prose), why


def test_the_google_widget_is_named_off_its_runtime_as_well_as_its_loader():
    """The two halves of one widget, and the line between the runtime and an ordinary hyperlink.

    The loader is the INSTALL and is usually in the bytes the server sent; the runtime is the widget
    RUNNING and can only be in a rendered document. Measured on the 23,997 paired organizations of
    the July 2026 capture: script 0 server / 610 rendered, stylesheet 0 / 616, logo 0 / 533, against
    a loader at 549 / 606. Each address here is the one the capture found, anchored to the asset
    path, because the host on its own is not this widget.
    """
    assert LA.widget_name(
        'src="https://translate.googleapis.com/_/translate_http/_/js/'
        'k=translate_http.tr.en_US.Qm6zfyAGhvw.O/am=BIAABw/d=1/rs=AN8SPfolnSA1iF5EK06x/m=el_main"'
    ) == 'Google Translate'
    assert LA.widget_name(
        'href="https://www.gstatic.com/_/translate_http/_/ss/'
        'k=translate_http.tr.1RvRdG4PDmq889IXXRnXixFQ/m=el_main_css"') == 'Google Translate'
    assert LA.widget_name(
        'src="https://fonts.gstatic.com/s/i/productlogos/translate/v14/24px.svg"'
    ) == 'Google Translate'
    # and MT_RX answers the same, which is the invariant the loader broke once already
    for asset in ('https://translate.googleapis.com/_/translate_http/_/js/k=x',
                  'https://www.gstatic.com/_/translate_http/_/ss/k=x',
                  'https://fonts.gstatic.com/s/i/productlogos/translate/v14/24px.svg'):
        assert LA.MT_RX.search(asset), asset

    # THE NEGATIVE, and what it now says. 80 organizations in the capture carry a "Translate this
    # site" hyperlink, and on the bytes alone nothing says whose page is behind it, so the answer
    # off the bytes alone is still no name at all. What decides it is the site's own address, and
    # that is the next test.
    link = ('<p><strong>Translate this site:</strong> <a href="http://translate.google.com/'
            'translate?u=www.wf-08.example/&amp;hl=en&amp;ie=UTF-8&amp;sl=en&amp;tl=es">'
            'Español</a></p>')
    assert LA.widget_name(link) == ''
    assert not LA.MT_RX.search(link)
    # nor does the pattern reach Google's translation API called from a server, which is a different
    # product on the same host and is why the host alone could not be the marker
    assert LA.widget_name(
        'https://translate.googleapis.com/language/translate/v2?key=AIza&q=hello') == ''


def test_a_wix_isMultilingualEnabled_flag_is_not_a_marker():
    """3,852 organizations in the capture carry this global, and it is present on Wix pages with
    the feature switched OFF. Only the VALUE distinguishes them, and no document read here carries
    a value this package parses, so the token names nothing."""
    assert not LA.MT_RX.search('window.isMultilingualEnabled = false;')
    assert LA.widget_name('window.isMultilingualEnabled = true;') == ''


# ------------------------------------------------------ the five vendors named off an ADDRESS
#
# Known-answer cases for the fingerprints added 2026-08-05. Every positive string below is bytes a
# site in the county-gap draw really served, quoted from the stored capture and de-named as the
# paragraph below describes; every negative is the shape the fingerprint has to refuse. The counts
# in each docstring are that draw, 1,370 sites with a readable document, and they were measured
# with these functions and not with a scan written beside them.
#
# The draw is a government-heavy sample and no site in it can be named here, so every address in
# this block is a placeholder of the same shape as the one the capture held, and the surrounding
# prose is not reproduced. Both sides of every ownership test moved together, which is the only way
# the test still asks a question. The single exception is the state portal of the directory
# stop's case below:
# `SUFFIX_HOST` is a frozen list of hosts, and a portal that is not on it makes that case pass for
# the wrong reason. The hand coding that says what each of these sites really offers is at
# `unnamed_control_coding/` beside the draw, outside this repository, and it was taken blind: every
# code was written down before any verdict of this package's was looked at.

_COUNTY_SELECT = ('<option value="https://translate.google.com/translate?hl=en&amp;sl=en&amp;'
                  'tl=ar&amp;u=https://www.co.alpha.example/default.aspx">Arabic</option>')
_CIVICPLUS = ("""onclick="Core.Layout.dynamicJavascript('window.open(\\&#39;https://translate."""
              """google.com/translate?js=n&amp;sl=auto&amp;tl=es&amp;u=\\&#39; + document."""
              """location.href, \\&quot;TranslateWindow\\&quot;);'); return false;\"""")
_APPTEGY = ('<script src="https://cmsv2-static-cdn-prod.apptegy.net/app.js"></script>'
            '<script>window.__DATA__="{\\"clientId\\":4469,\\"translation\\":{\\"languages\\":'
            '[{\\"language\\":\\"English\\",\\"code\\":\\"en\\"},{\\"language\\":\\"Spanish\\",'
            '\\"code\\":\\"es\\"}],\\"language\\":\\"English\\",\\"locale\\":\\"en\\"}"</script>')


def test_an_own_target_google_translate_link_is_a_control_and_a_bare_one_is_not():
    """G1, and the reversal it carries. 13 sites of the draw, 10 of them named by nothing else, and
    on the 9 where the truth is known all 9 are working machine translators.

    The package recorded until now that a translate.google.com hyperlink is not an installed widget,
    and on the document alone that is right, because nothing in the bytes says whose page is behind
    the link. The address is what settles it, and `_same_site` is what reads it, so the same code
    that keeps a state portal off a county's reading under the directory stop keeps a stranger's
    page out of
    this one.
    """
    assert LA.widget_name(_COUNTY_SELECT, 'https://www.co.alpha.example/') == 'Google Translate'
    assert LA.widget_name(_COUNTY_SELECT, 'https://www.example.org/') == ''
    assert LA.widget_name(_COUNTY_SELECT) == '', 'no address given, so the question has no answer'

    # the same bytes `proxy_and_bare_link` holds, read with and without the address
    link = ('<a href="http://translate.google.com/translate?u=www.wf-08.example/&amp;hl=en&amp;'
            'sl=en&amp;tl=es">Espanol</a>')
    assert LA.widget_name(link, 'https://www.wf-08.example/') == 'Google Translate'
    assert LA.widget_name(link, 'https://example.net/') == ''

    # THE FALSE POSITIVE THE OWNERSHIP CLAUSE EXISTS FOR, and the only known error of the whole
    # family: a newsletter archive entry saved as a Google Translate address of a Mailchimp
    # campaign, which is CONTENT on the page and not a control of the page.
    mailchimp = ('<a href="https://translate.google.com/website?sl=en&amp;tl=es&amp;'
                 'u=http://eepurl.com/jzYSGo">translate</a>')
    assert LA.widget_name(mailchimp, 'https://example.net/') == ''

    # the directory stop's shape, which is where an ownership test written on string similarity
# would fail. The
    # state portal is a real host because `SUFFIX_HOST` is the frozen list this clause reads, and a
    # portal that is not on it would make the case pass on the wrong branch; the county subdomain
    # in front of it is a placeholder.
    portal = 'href="https://translate.google.com/translate?tl=es&u=https://www.nebraska.gov/"'
    assert LA.widget_name(portal, 'https://examplecounty.nebraska.gov/') == ''
    # and a co-tenant under the same parent host, which is the address-key collision this project
    # has already been bitten by once
    cotenant = 'href="https://translate.google.com/translate?tl=es&u=https://co.beta.example/"'
    assert LA.widget_name(cotenant, 'https://www.co.alpha.example/') == ''
    # the site's own subdomain is the site
    own = 'href="https://translate.google.com/translate?tl=es&u=https://es.example.org/"'
    assert LA.widget_name(own, 'https://www.example.org/') == 'Google Translate'


def test_a_target_built_from_the_address_bar_needs_no_address_at_all():
    """G2. 16 sites of the draw, 6 of them named by nothing else, 0 known errors.

    The target of such a link is the page the reader is standing on by construction, so this one
    cannot be pointed at a third party and needs no ownership clause. It is also why no rule here
    names a content manager: one ASP.NET county CMS and CivicPlus Site Tools both write this shape,
    and an asset filename would go stale at the next reskin and teach the instrument nothing.
    """
    assert LA.widget_name(_CIVICPLUS) == 'Google Translate'
    assert LA.widget_name(_CIVICPLUS, '') == 'Google Translate'
    # the vendor script the county CMS loads, which writes the same address the same way
    ez = ('var currentURL = encodeURIComponent(window.location.href);\n'
          'var url = "https://translate.google.com/translate?hl=en&sl=auto&tl=es&u=" + currentURL;')
    assert LA.widget_name(ez) == 'Google Translate'
    # and a literal address with no concatenation anywhere near it is not this fingerprint
    assert LA.widget_name(
        '<a href="https://translate.google.com/translate?tl=es&u=http://eepurl.com/x">go</a>') == ''


def test_an_own_host_google_proxy_address_is_a_name_and_a_stranger_s_is_not():
    """G3. 4 sites of the draw carry an own-host proxy address, 3 of them named by nothing else; 2
    more carry one whose host is not theirs, which is where this fingerprint's false positive comes
    from and why the host clause is not optional.

    MT_RX has matched `translate.goog` since the widget corpus and MT_NAME deliberately did not name
    it, on the reasoning that a proxy address is a marker and is nobody's vendor name. It is a
    vendor's name once the host is read.
    """
    proxy = '<a href="https://www-example-org.translate.goog/es/">Espanol</a>'
    assert LA.widget_name(proxy, 'https://www.example.org/') == 'Google Translate'
    assert LA.widget_name(proxy, 'https://www.example.net/') == ''
    assert LA.widget_name(proxy) == ''
    # a real hyphen in the host is written doubled, so it has to come out first
    assert LA.widget_name('https://www-a--b-example.translate.goog/',
                          'https://www.a-b.example/') == 'Google Translate'


def test_the_google_element_runtime_needs_both_halves_of_its_conjunction():
    """G4, and the conjunction IS the rule. Over the draw, `googtrans` alone matches 14 sites and
    `skiptranslate` alone 38, because sites copy that class into their own stylesheets to stop a
    region being translated. Requiring both collapses 52 loose matches to 2, one of them named by
    nothing else, with 0 known errors."""
    assert LA.widget_name('document.cookie="googtrans=/en/es"; <iframe class="skiptranslate">'
                          ) == 'Google Translate'
    assert LA.widget_name('document.cookie="googtrans=/en/es";') == ''
    assert LA.widget_name('.skiptranslate{display:none}') == ''


def test_a_content_manager_declaring_its_own_translation_languages_is_named():
    """G5. 7 sites of the draw, all 7 named by nothing else, 0 known errors.

    Three clauses and each is load-bearing. The vendor's own asset host makes this a
    vendor's name rather than a JSON key anybody could emit. The payload key separates the feature
    from the content manager. A SECOND declared language separates a configured feature from one
    serving English alone.

    What it establishes is narrower than the four above, and the kind table says so: the feature is
    installed and these are the languages it declares. On one city of the draw the declaration lists
    fourteen languages and the city ALSO publishes its own Spanish, and that site is
    true_multilingual by the ordinary evidence path with this name on it. Naming the widget and
    classing the site stay separate.
    """
    assert LA.widget_name(_APPTEGY) == 'Apptegy'
    assert LA.WIDGET_KIND['Apptegy'] == ('machine_translate', 'server_plugin')
    assert 'Apptegy' not in LA.CLIENT_SIDE_WIDGET, (
        'the payload carries the content manager\'s own locale, so the translation is chosen on '
        'the server and a server document is that vendor\'s output')
    english_only = _APPTEGY.replace(',{\\"language\\":\\"Spanish\\",\\"code\\":\\"es\\"}', '')
    assert LA.widget_name(english_only) == '', 'a feature declaring English alone offers nothing'
    assert LA.widget_name('<script src="https://cmsv2-static-cdn-prod.apptegy.net/app.js">'
                          '</script>') == '', 'the content manager is not the feature'
    assert LA.widget_name('"translation":{"languages":[{"language":"English"},'
                          '{"language":"Spanish"}]}') == '', 'the key alone is anybody\'s JSON'


def test_a_bare_element_labelled_translate_names_nothing_and_is_still_recorded():
    """The one that was refused, and the reason the five are five.

    Over the draw a bare element labelled Translate is on 171 sites and would newly name 44. On the
    44 where the truth is known it is wrong three times, and all three are in the class the
    instrument exists to separate: a county whose Translate button opens an English page about using
    the browser's own translator, and two cities that publish their own languages. It is recorded as
    an observation and it settles nothing.
    """
    assert LA.widget_name('<button>Translate</button>', 'https://www.example.org/') == ''
    assert LA.unnamed_control('<button>Translate</button>')
    assert LA.unnamed_control('<button aria-label="Translate">x</button>')
    # anchored on both sides: a sentence the site wrote is not a control's whole label
    assert not LA.unnamed_control('<h2>Translation Services</h2>')
    assert not LA.unnamed_control('<button aria-label="Translate Site">x</button>')
    assert not LA.unnamed_control('')


def test_MT_RX_cannot_answer_for_a_vendor_named_off_an_address():
    """The invariant `test_MT_RX_answers_for_every_marker_MT_NAME_can_name` states, and its edge.

    MT_RX is the public "is there any translation machinery in these bytes" test, and it is a byte
    test: a caller hands it a document and nothing else. Three of the five address fingerprints
    cannot be written that way, because the question they answer is about the SITE and not about the
    bytes. The invariant therefore holds over MT_NAME and AMBIGUOUS_NAME, which is what that test
    exercises, and it does not extend to these. Written down here rather than left to be discovered,
    because the two constants answering opposite things about one page is a defect this package has
    already shipped once.
    """
    assert LA.widget_name(_COUNTY_SELECT, 'https://www.co.alpha.example/') == 'Google Translate'
    assert not LA.MT_RX.search(_COUNTY_SELECT), (
        'a hyperlink is not a marker, and MT_RX reads markers')
    # the two that ARE byte tests do reach MT_RX, because their bytes are the vendor's own
    assert LA.MT_RX.search('https://www-example-org.translate.goog/es/')
    for nm in LA.MT_ADDRESS_NAME:
        assert nm in LA.WIDGET_KIND
    # and the names `widget_name` actually returns this way are that tuple and nothing else, so the
    # constant cannot drift away from the two string literals in the function
    reached = {LA.widget_name(_COUNTY_SELECT, 'https://www.co.alpha.example/'),
               LA.widget_name(_CIVICPLUS), LA.widget_name(_APPTEGY),
               LA.widget_name('https://www-example-org.translate.goog/',
                              'https://www.example.org/'),
               LA.widget_name('googtrans <iframe class="skiptranslate">')}
    assert reached == set(LA.MT_ADDRESS_NAME)


# --------------------------------------------------------------- the marker on an interior page
#
# A home-page-only widget scan is close to sufficient and is not sufficient, and the corpus puts a
# number on the gap. In the SERVER documents of the capture, a home-page-only check finds 1,768 of
# the 1,844 organizations carrying an MT_NAME marker and misses 76 of them, 4.1 per cent; and 1,162
# of the 1,230 carrying a CMS_RX marker, missing 68, 5.5 per cent. That is roughly a hundred
# organizations in one census whose widget or plugin sits behind the front door.
#
# The crawl was already reading those pages. It read them for their language and never looked at
# them for a marker, so the fix is not a new fetch, and these cases are what stop the scan being
# narrowed back to the home document by somebody optimising the loop.
_EN_HOME = ('Welcome to our community center. We help families with legal questions, housing and '
            'school enrolment every day of the week.')
_EN_INSIDE = ('Our services include intake appointments, referrals to legal counsel and help with '
              'benefit applications for families across the county.')


def _site(interior_html):
    return {
        'https://x.org/': _page(_EN_HOME,
                                '<html><body><a href="/services">Services</a><p>'
                                + _EN_HOME + '</p></body></html>'),
        'https://x.org/services': (interior_html, _EN_INSIDE, 200),
    }


def _inside(extra):
    return '<html><body>' + extra + '<p>' + _EN_INSIDE + '</p></body></html>'


def test_a_widget_on_an_interior_page_is_still_the_site_s_widget():
    """4.1 per cent of the capture's MT_NAME organizations are exactly this site."""
    b = _MapBrowser(_site(_inside(
        '<script src="//translate.google.com/translate_a/element.js?cb=x"></script>')))
    r = asyncio.run(LA._audit_async('https://x.org/', browser=b))
    assert r.pages_read >= 2, 'the interior page has to have been read for the scan to see it'
    assert r.machine_translation == 'Google Translate'


def test_a_cms_plugin_marker_on_an_interior_page_is_still_evidence():
    """5.5 per cent of the capture's CMS_RX organizations are exactly this site. Rule 11's marker,
    recorded at the address it was found at rather than at the home page's."""
    b = _MapBrowser(_site(_inside('<link rel="stylesheet" href="/wp-content/plugins/sitepress-'
                                  'multilingual-cms/wpml.css">')))
    r = asyncio.run(LA._audit_async('https://x.org/', browser=b))
    plugin = [e for e in r.evidence if e.mechanism == 'translation_plugin']
    assert len(plugin) == 1, 'one marker for the site, not one per page'
    assert plugin[0].url == 'https://x.org/services'
    assert 11 in plugin[0].rules


def test_the_home_page_still_answers_first_when_both_pages_carry_a_marker():
    """The front door is the page a visitor lands on, so it names the widget and the interior pages
    only fill in for a site that has nothing on it."""
    site = _site(_inside('<script src="//cdn.weglot.com/weglot.min.js"></script>'))
    home_html, home_text, st = site['https://x.org/']
    site['https://x.org/'] = (home_html.replace(
        '<body>', '<body><script src="//translate.google.com/translate_a/element.js"></script>'),
        home_text, st)
    r = asyncio.run(LA._audit_async('https://x.org/', browser=_MapBrowser(site)))
    assert r.machine_translation == 'Google Translate'


def test_a_site_with_no_marker_anywhere_still_names_no_widget():
    """The scan reads more pages, which is more chances to be wrong, so this test is the control."""
    b = _MapBrowser(_site(_inside('<div class="translateY-hero">')))
    r = asyncio.run(LA._audit_async('https://x.org/', browser=b))
    assert r.machine_translation == ''
    assert not [e for e in r.evidence if e.mechanism == 'translation_plugin']


def test_a_re_judge_finds_the_interior_marker_the_live_crawl_found(tmp_path):
    """The two readers have to scan the same pages or they are two different instruments.

    `rejudge` reads a stored capture and applies the same judgement without going back to the web.
    It scanned the home document alone, so a site whose widget or plugin is one click in would have
    been re-judged to a different answer from the audit that wrote the record, on exactly the four
    to six per cent of marker-carrying organizations this change is about.
    """
    path = tmp_path / 'run.jsonl'
    site = _site(_inside('<script src="//cdn.weglot.com/weglot.min.js"></script>'
                         '<link href="/wp-content/plugins/polylang/style.css">'))
    live = asyncio.run(LA._audit_async('https://x.org/', browser=_MapBrowser(site),
                                       keep_pages=True))
    LA._store_result(str(path), live)
    assert live.machine_translation == 'Weglot', 'the fixture has to have an interior marker'

    again = LA.rejudge(str(path), 'https://x.org/')
    assert again.machine_translation == live.machine_translation
    assert ([(e.mechanism, e.url) for e in again.evidence if e.mechanism == 'translation_plugin']
            == [(e.mechanism, e.url) for e in live.evidence if e.mechanism == 'translation_plugin'])
    assert again.verdict == live.verdict
