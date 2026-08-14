# -*- coding: utf-8 -*-
"""Browser-and-network tests for langaccess.

Everything here launches a real headless browser and makes real HTTP requests, unlike
tests/test_core.py, which is pure functions only. Marked `live` and skipped by default (see the
`addopts = -m "not live"` default in pyproject.toml). Run explicitly with:

    pytest -m live

Do not run this file as part of routine CI or local development unless you specifically want to
exercise the browser path; each case launches Chromium and fetches from the live internet.
"""
import pytest

from langaccess import audit, Result


pytestmark = pytest.mark.live


def test_audit_returns_a_result_for_a_real_site():
    r = audit('https://www.example.com')
    assert isinstance(r, Result)
    assert r.verdict in ('english_only', 'machine_translate', 'true_multilingual', 'unreachable')


def test_audit_reports_unreachable_for_a_nonexistent_domain():
    r = audit('https://this-domain-should-not-exist-langaccess-test.invalid')
    assert r.verdict == 'unreachable'


# ---------------------------------------------------------------- accuracy pass 3, 2026-07-30
# The chrome-removal step is JavaScript run against a real DOM, so the fakes in
# tests/test_engineering.py can only pin the wiring around it. `_CHROME_DOC` runs the script itself,
# on a document written to look like the case it exists for: a locale page whose whole text is a skip
# link, a navigation bar, a link list and a footer, with one paragraph of the site's own underneath.
_CHROME_DOC = '''<!doctype html><html><head><title>Centre</title></head><body>
<a class="skip-link" href="#main">Passer au contenu principal</a>
<header><div>ACCUEIL</div></header>
<nav><a href="/fr/a">NOS SERVICES POUR LES FAMILLES</a><a href="/fr/b">PRENDRE CONTACT</a></nav>
<ul><li><a href="/fr/1">Qui sommes nous</a></li><li><a href="/fr/2">Nos programmes</a></li>
<li><a href="/fr/3">Evenements</a></li></ul>
<main id="main"><p>KEEP THIS PARAGRAPH, which is the page itself and not its furniture.</p></main>
<footer><p>Tous droits reserves. Nos bureaux sont ouverts du lundi au vendredi.</p></footer>
</body></html>'''


def _chrome_free(doc):
    import asyncio

    from langaccess import core as LA

    async def go():
        async with LA._playwright() as pw:
            b = await LA._launch(pw)
            try:
                ctx = await b.new_context()
                page = await ctx.new_page()
                await page.set_content(doc)
                whole = await page.inner_text('body')
                main = await LA._main_text(page)
                after = await page.inner_text('body')
                return whole, main, after
            finally:
                await b.close()

    return asyncio.run(go())


def test_the_chrome_removal_script_takes_out_the_furniture_and_leaves_the_page():
    whole, main, after = _chrome_free(_CHROME_DOC)
    assert 'PRENDRE CONTACT' in whole                  # it was there to begin with
    assert 'KEEP THIS PARAGRAPH' in main
    for furniture in ('Passer au contenu principal', 'ACCUEIL', 'PRENDRE CONTACT',
                      'NOS SERVICES POUR LES FAMILLES', 'Qui sommes nous', 'Tous droits reserves'):
        assert furniture not in main, furniture
    # and the page is put back, because the language switcher lives in the header on most sites and
    # `_click_language_controls` reads the same DOM afterwards
    assert after == whole


def test_a_page_that_is_all_chrome_reads_as_nothing_rather_than_as_its_menu():
    from langaccess import core as LA

    doc = _CHROME_DOC.replace('<main id="main"><p>KEEP THIS PARAGRAPH, which is the page itself '
                              'and not its furniture.</p></main>', '')
    whole, main, _after = _chrome_free(doc)
    assert LA.languages_in(whole) == ['French'], 'the fixture has to be readable as French'
    assert LA.languages_in(main) == []


# ---------------------------------------------------------------- the click step, 2026-08-01
#
# `_read` ends by deleting WIDGET_SEL, and on the Google Translate and GTranslate families WIDGET_SEL
# IS the switcher, so the read that positioned the throwaway context deleted the controls
# `_click_language_controls` then went looking for. Measured on a live page: two clickable Spanish
# candidates before the strip and none after.
#
# Skipping the strip there and doing nothing else would be worse than the defect. The click step
# reads the page it lands on and hands it to `languages_in` with nothing taken out, so the widget's
# own menu, which is a list of language autonyms, would be read as the organization writing in those
# languages, which is the reading the strip was added to stop.
#
# Both halves need a real DOM: the strip is JavaScript that removes nodes, the click is a click, and
# the fakes in tests/test_engineering.py can only pin the wiring around them. These two documents are
# served to a real browser through Playwright's own routing, so `base` is a real address the loop can
# navigate back to and no request leaves the machine.

_SPANISH = ('Ofrecemos clases de ingles y una despensa de alimentos para las familias de la '
            'comunidad. La oficina esta abierta de lunes a viernes y no es necesario pedir una '
            'cita para recibir ayuda con los formularios de inmigracion.')

# A Google Translate gadget with its language list open. The four controls are the nodes a visitor
# clicks and they sit inside `#google_translate_element`, which is the first selector in WIDGET_SEL.
_SWITCHER_DOC = (
    '<!doctype html><html><head><title>Community Center</title></head><body>'
    '<div id="google_translate_element" class="skiptranslate">'
    '<div class="goog-te-gadget"><span class="goog-te-menu-value">Select Language</span>'
    '<div class="goog-te-menu2">'
    '<a class="goog-te-menu2-item" style="display:block" id="es">Espanol</a>'
    '<a class="goog-te-menu2-item" style="display:block" id="fr">Francais</a>'
    '<a class="goog-te-menu2-item" style="display:block" id="vi">Tieng Viet</a>'
    '<a class="goog-te-menu2-item" style="display:block" id="ko">Korean</a>'
    '</div></div></div>'
    '<main><p id="b">We run English classes, legal clinics and a food pantry for families in the '
    'neighborhood, and the office is open on weekdays.</p></main>'
    '<script>document.getElementById("es").addEventListener("click",function(){'
    'document.getElementById("b").textContent="' + _SPANISH + '";});</script></body></html>')

# The other side. The widget's menu names languages in their own languages and carries the widget's
# own instruction line, and the page the control produces is English: the widget is installed and it
# translated nothing. The Cyrillic here is the widget speaking, so no language may be read off it.
_MENU_DOC = (
    '<!doctype html><html><head><title>Center</title></head><body>'
    '<div id="google_translate_element" class="skiptranslate">'
    '<a class="goog-te-menu2-item" id="pick">Russian</a>'
    '<div class="goog-te-menu2">'
    '<p>Выберите язык из '
    'списка, чтобы '
    'прочитать эту '
    'страницу.</p>'
    '<p>English Русский '
    'Українська '
    'Български Español Français Deutsch '
    '日本語 العربية</p>'
    '</div></div>'
    '<main><p id="b">We run English classes, legal clinics and a food pantry for families in the '
    'neighborhood, and the office is open on weekdays.</p></main>'
    '<script>document.getElementById("pick").addEventListener("click",function(){'
    'document.getElementById("b").textContent="Translation for this page is not available yet.";'
    '});</script></body></html>')

_FIXTURE_BASE = 'https://fixture.test/'


def _clicked(doc, strip_first):
    """The audit's click path over a real DOM. `strip_first` is the defect: True is the ordering
    that deleted the switcher before the click step looked for it, False is the fixed one.

    Returns what the click step found, the collapsed home text it was given to compare against, and
    whether the widget is back in the page after the loop, which is the claim that the navigation at
    the end of the loop restores it for the next candidate.
    """
    import asyncio

    from langaccess import core as LA

    async def go():
        async with LA._playwright() as pw:
            b = await LA._launch(pw)
            try:
                ctx = await b.new_context()

                async def serve(route):
                    await route.fulfill(status=200, content_type='text/html; charset=utf-8',
                                        body=doc)

                await ctx.route('**/*', serve)
                # the home read, stripped, exactly as the crawl takes it: this is where `home_text`
                # comes from and the guard inside the loop compares against it
                home = await ctx.new_page()
                home_text = (await LA._read(home, _FIXTURE_BASE))[2]
                await home.close()
                # and the throwaway context the controls are clicked in
                page = await ctx.new_page()
                await LA._read(page, _FIXTURE_BASE, strip=strip_first)
                out = (await LA._click_language_controls(page, home_text, _FIXTURE_BASE))[0]
                back = await page.query_selector('#google_translate_element')
                return out, home_text, back is not None
            finally:
                await b.close()

    return asyncio.run(go())


def test_a_google_translate_switcher_is_still_there_to_click_when_the_click_step_runs():
    """The defect and the fix on one document. With the widget deleted first there is nothing to
    click and the Spanish the control produces is never seen; with it left in place the control is
    reached, clicked, and the Spanish page behind it is read."""
    lost, _home, _back = _clicked(_SWITCHER_DOC, strip_first=True)
    assert lost == [], 'the fixture no longer reproduces the defect it was written for'

    found, home_text, back = _clicked(_SWITCHER_DOC, strip_first=False)
    assert [(lg, label) for lg, _u, label, _q in found] == [('Spanish', 'Espanol')]
    quote = found[0][3]
    assert quote and quote not in home_text, 'the quote has to come off the page the click produced'
    # the navigation at the end of the loop reloads `base`, so the widget is served again and the
    # next candidate has something to click. Confirmed rather than assumed.
    assert back, 'the return navigation left the page without its widget'
    # Known and not asserted as a requirement: `_strip_widget` REMOVES the widget's nodes, so every
    # element handle taken inside it before the loop is detached once the first candidate has been
    # tried, and the handles taken before the loop do not survive the navigation back either. One
    # control per call is what this recovers.


def test_no_language_is_read_off_the_widgets_own_menu_after_the_control_is_clicked():
    """The naive repair, skipping the strip and doing nothing else, reinstates the reading the strip
    exists to stop one step later: the click step reads the page it lands on with nothing taken out.
    The menu here is the widget's, the page the control produces is English, and the answer is that
    the site showed no language."""
    from langaccess import core as LA

    unstripped = ('Russian Выберите язык '
                  'из списка, чтобы '
                  'прочитать эту '
                  'страницу. English '
                  'Русский '
                  'Українська '
                  'Български '
                  'Translation for this page is not available yet.')
    assert LA.languages_in(unstripped, script_words=True) != [], \
        'the menu has to be readable as a language, or this asserts nothing'

    found, _home, back = _clicked(_MENU_DOC, strip_first=False)
    assert found == []
    assert back, 'the return navigation left the page without its widget'


# ---------------------------------------------------------------- reachability, 2026-08-01
#
# Everything below needs a real DOM. Visibility is layout, opening a collapsed container is a click
# that runs the page's own script, an <option> has no box of its own, and detaching an element
# handle is something only a real removal does; the fakes in tests/test_engineering.py can pin the
# wiring around all of them and none of them themselves.
#
# The documents are served to a real browser through Playwright's own routing, so `base` is an
# address the loop can navigate back to and no request leaves the machine.

# GTranslate's classic switcher, which is the shape 12 of the 14 all-hidden sites use:
# the items sit in a `display:none` box inside a switcher that is drawn, and clicking the drawn part
# opens the box. The items are `href="#"` links, exactly as `a.nturl` is on the live sites. Four of
# them, so that the box's own text runs past the label cap and the box is not itself a candidate.
_COLLAPSED_DOC = (
    '<!doctype html><html><head><title>Center</title></head><body>'
    '<div class="gtranslate_wrapper"><div class="gt_switcher">'
    '<div class="gt_selected">English</div>'
    '<div class="gt_option" style="display:none">'
    '<a href="#" class="nturl" id="es">Espanol</a>'
    '<a href="#" class="nturl" id="fr">Francais</a>'
    '<a href="#" class="nturl" id="pt">Portugues</a>'
    '<a href="#" class="nturl" id="ko">Korean</a>'
    '</div></div></div>'
    '<main><p id="b">We run English classes, legal clinics and a food pantry for families in the '
    'neighborhood, and the office is open on weekdays.</p></main>'
    '<script>'
    'document.querySelector(".gt_switcher").addEventListener("click",function(){'
    'var o=document.querySelector(".gt_option");'
    'o.style.display = o.style.display === "none" ? "block" : "none";});'
    'document.getElementById("es").addEventListener("click",function(e){e.stopPropagation();'
    'document.getElementById("b").textContent="' + _SPANISH + '";});'
    '</script></body></html>')

# A switcher built as a <select>, which is what 20 of the 53 sites measured have and what the
# element query never asked for. The change event is what swaps the page; a click on an <option>
# is not a thing Chromium does.
_SELECT_DOC = (
    '<!doctype html><html><head><title>Center</title></head><body>'
    '<div id="google_translate_element" class="skiptranslate">'
    '<select class="goog-te-combo"><option value="">Select Language</option>'
    '<option value="en">English</option><option value="es">Espanol</option></select>'
    '</div>'
    '<main><p id="b">We run English classes, legal clinics and a food pantry for families in the '
    'neighborhood, and the office is open on weekdays.</p></main>'
    '<script>document.querySelector("select").addEventListener("change",function(){'
    'if(this.value==="es") document.getElementById("b").textContent="' + _SPANISH + '";});'
    '</script></body></html>')

# Two controls that swap nothing, which is the path that leaves the document standing. The page
# counts the clicks it received in an attribute, because innerText is what the loop compares and a
# counter that showed up in the text would make every control look like a control that worked. The
# instruction line is there so that the box holding the two links is too wordy to be a candidate
# itself, which keeps the count a count of the two controls.
_TWO_DEAD_DOC = (
    '<!doctype html><html><head><title>Center</title></head><body data-clicks="">'
    '<div id="google_translate_element" class="skiptranslate">'
    'Choose the language you would like to read this site in: '
    '<a href="#" id="fr">Francais</a> <a href="#" id="es">Espanol</a>'
    '</div>'
    '<main><p>We run English classes, legal clinics and a food pantry for families in the '
    'neighborhood, and the office is open on weekdays.</p></main>'
    '<script>["fr","es"].forEach(function(id){'
    'document.getElementById(id).addEventListener("click",function(){'
    'document.body.dataset.clicks=document.body.dataset.clicks+id+" ";});});'
    '</script></body></html>')


def _click_step(doc, after=None, whole=False):
    """The audit's click path over a real DOM, with the positioning read taken the way the crawl
    takes it. `after` is JavaScript evaluated on the page once the loop has finished, and
    `whole` asks for the loop's three lists instead of only the controls that worked."""
    import asyncio

    from langaccess import core as LA

    async def go():
        async with LA._playwright() as pw:
            b = await LA._launch(pw)
            try:
                ctx = await b.new_context()

                async def serve(route):
                    await route.fulfill(status=200, content_type='text/html; charset=utf-8',
                                        body=doc)

                await ctx.route('**/*', serve)
                home = await ctx.new_page()
                home_text = (await LA._read(home, _FIXTURE_BASE))[2]
                await home.close()
                page = await ctx.new_page()
                await LA._read(page, _FIXTURE_BASE, strip=False)
                out = await LA._click_language_controls(page, home_text, _FIXTURE_BASE)
                extra = None if after is None else await page.evaluate(after)
                return (out if whole else out[0]), home_text, extra
            finally:
                await b.close()

    return asyncio.run(go())


def test_a_collapsed_candidate_is_not_visible_before_the_control_is_opened():
    """The fixture has to reproduce the state it exists for, or the test after it asserts nothing
    about opening: a language a visitor cannot see, still answering inner_text with its name."""
    import asyncio

    from langaccess import core as LA

    async def go():
        async with LA._playwright() as pw:
            b = await LA._launch(pw)
            try:
                page = await (await b.new_context()).new_page()
                await page.set_content(_COLLAPSED_DOC)
                el = await page.query_selector('#es')
                return await el.is_visible(), await el.bounding_box(), await el.inner_text()
            finally:
                await b.close()

    visible, box, label = asyncio.run(go())
    assert not visible and box is None
    assert label == 'Espanol', 'a collapsed item still answers inner_text, which is the whole trap'


def test_a_language_inside_a_collapsed_switcher_is_reached_by_opening_it():
    """The candidate is in the page and a click cannot land on it. Before this the click waited its
    three seconds and gave up; 128 of the 157 candidates on the 53 widget sites of the two
    development regression frames are in exactly this state."""
    found, home_text, _ = _click_step(_COLLAPSED_DOC)
    assert [(lg, label) for lg, _u, label, _q in found] == [('Spanish', 'Espanol')]
    quote = found[0][3]
    assert quote and quote not in home_text, 'the quote has to come off the page the click produced'


def test_a_switcher_built_as_a_select_is_driven_and_reports_its_language():
    """An <option> is not rendered and has no box, so it cannot be clicked; the change event is what
    swaps the page. Twenty of the 53 sites measured carry one, and eighteen of those carry nothing
    else."""
    found, _home, _ = _click_step(_SELECT_DOC)
    assert [(lg, label) for lg, _u, label, _q in found] == [('Spanish', 'Espanol')]


def test_a_second_control_in_the_same_switcher_is_still_there_to_work():
    """`_strip_widget` REMOVES the widget's nodes, so once one candidate inside it had been tried,
    every remaining candidate answered `Element is not attached to the DOM`. That only bites on the
    path that leaves the document standing, which is a control that changed nothing, and exactly
    there the next control is the one that might work."""
    found, _home, clicks = _click_step(_TWO_DEAD_DOC, after='() => document.body.dataset.clicks')
    assert found == [], 'neither control changes this page, so neither may report a language'
    assert clicks == 'fr es ', 'the second control was never worked: %r' % clicks


# A switcher a visitor can see the shape of and this package cannot work: the language links are
# hidden and nothing on the page opens them, so `_open_collapsed` has nothing to click and
# `_click_can_land` keeps answering False. Before 2026-08-08 the loop dropped each one with a bare
# `continue`: no evidence, no note, no count, and the reading went on to call the site english_only
# on a search that had skipped the one route most likely to carry the answer.
_STUCK_DOC = (
    '<!doctype html><html><head><title>Center</title></head><body>'
    '<div class="lang" style="display:none">'
    '<a href="/es" id="es">Espanol</a> <a href="/ko" id="ko">Korean</a>'
    '</div>'
    '<main><p>We run English classes, legal clinics and a food pantry for families in the '
    'neighborhood, and the office is open on weekdays.</p></main>'
    '</body></html>')


def test_a_control_that_cannot_be_worked_is_recorded_instead_of_dropped():
    """The count is what matters. A control that was clicked and did nothing has been rule 16's
    observation since 2026-08-06; a control that could not be clicked at all was silence, and the
    two failures are the same fact about the reading."""
    (worked, dead, stuck), _home, _ = _click_step(_STUCK_DOC, whole=True)
    assert worked == [], 'nothing here can be worked, so nothing may report a language'
    assert dead == [], 'nothing was clicked, so nothing can have been clicked and done nothing'
    labels = [lbl for lbl, _u in stuck]
    assert 'Espanol' in labels and 'Korean' in labels, labels
    # the wrapper element resolves as a candidate too, on the text of both links; what the record
    # owes is that the abandoned routes are on it, not that the DOM query is tidy
    assert all(_u == _FIXTURE_BASE for _lbl, _u in stuck)


def test_an_unworkable_control_reaches_the_record_without_moving_the_class():
    """It travels as an evidence entry with no language, which `counted_evidence` cannot count, so
    a reader of the record sees the abandoned route and no verdict moves on account of it."""
    import asyncio

    from langaccess import core as LA

    class _Routed:
        """The real browser, with every context it hands out serving the fixture. `_audit_async`
        makes its own contexts, so routing one built here would never reach the crawl."""

        def __init__(self, b):
            self._b = b

        async def new_context(self, **kw):
            ctx = await self._b.new_context(**kw)

            async def serve(route):
                await route.fulfill(status=200, content_type='text/html; charset=utf-8',
                                    body=_STUCK_DOC)

            await ctx.route('**/*', serve)
            return ctx

        def __getattr__(self, name):
            return getattr(self._b, name)

    async def go():
        async with LA._playwright() as pw:
            b = await LA._launch(pw)
            try:
                return await LA._audit_async(_FIXTURE_BASE, browser=_Routed(b))
            finally:
                await b.close()

    r = asyncio.run(go())
    say = [e for e in r.evidence if 'could not be operated' in LA._ev_quote(e)]
    assert say, 'the abandoned controls left no trace on the record'
    assert all(not LA._ev_lang(e) and not LA._ev_recorded(e, 'rules') for e in say), (
        'an entry with a language or a rule number would be counted or would resolve against a '
        'rule that does not cover this')
    assert r.verdict == 'english_only', 'recording the control may not move the class'


def test_a_widget_whose_control_does_nothing_is_reported_as_an_error_not_an_absence():
    """End to end over a real browser, on the fixture where both controls are clicked and neither
    changes the page. Before 2026-08-09 this site came back english_only, which asserts that no
    other language was found; what the reading establishes is that a widget was there and this
    client could not get a translation out of it, which is rule 16's class."""
    import asyncio

    from langaccess import core as LA

    class _Routed:
        def __init__(self, b):
            self._b = b

        async def new_context(self, **kw):
            ctx = await self._b.new_context(**kw)

            async def serve(route):
                await route.fulfill(status=200, content_type='text/html; charset=utf-8',
                                    body=_TWO_DEAD_DOC)

            await ctx.route('**/*', serve)
            return ctx

        def __getattr__(self, name):
            return getattr(self._b, name)

    async def go():
        async with LA._playwright() as pw:
            b = await LA._launch(pw)
            try:
                return await LA._audit_async(_FIXTURE_BASE, browser=_Routed(b))
            finally:
                await b.close()

    r = asyncio.run(go())
    assert r.machine_translation, 'the fixture has to name a vendor or there is no widget to fail'
    assert r.verdict == LA.MT_ERROR, r.verdict
    assert 16 in r.rules and 15 not in r.rules
    assert LA.CONTROL_DEAD_NOTE in r.note


def _widget_texts():
    import asyncio

    from langaccess import core as LA

    async def go():
        async with LA._playwright() as pw:
            b = await LA._launch(pw)
            try:
                ctx = await b.new_context()

                async def serve(route):
                    await route.fulfill(status=200, content_type='text/html; charset=utf-8',
                                        body=_MENU_DOC)

                await ctx.route('**/*', serve)
                p1 = await ctx.new_page()
                await LA._read(p1, _FIXTURE_BASE, strip=False)
                whole = await p1.inner_text('body')
                await LA._strip_widget(p1)
                removed = await p1.inner_text('body')
                p2 = await ctx.new_page()
                await LA._read(p2, _FIXTURE_BASE, strip=False)
                await LA._hide_widget(p2)
                hidden = await p2.inner_text('body')
                main = await LA._main_text(p2)
                await LA._show_widget(p2)
                back = await p2.inner_text('body')
                p3 = await ctx.new_page()
                read_text = (await LA._read(p3, _FIXTURE_BASE))[2]
                return whole, removed, hidden, back, read_text, main
            finally:
                await b.close()

    return asyncio.run(go())


def test_hiding_the_widget_reads_the_same_as_removing_it():
    """What the click loop does to the widget changed from a removal to a hide, and `_read` still
    removes. The two have to produce the same TEXT or the reading moved, and they do, because
    inner_text is what the browser lays out and a `display:none` subtree is not laid out.

    `_read`'s own answer is taken here as well, on the same document, so the claim that it is
    unaffected is measured and not asserted.
    """
    whole, removed, hidden, back, read_text, main = _widget_texts()
    assert 'Выберите' in whole, 'the fixture has to carry the widget menu, or this asserts nothing'
    assert removed != whole
    assert hidden == removed
    assert ' '.join(read_text.split()) == ' '.join(removed.split()), \
        "_read's text moved, which is the one thing this change may not do"
    assert 'Выберите' not in main, 'the chrome read has to see the widget out as well'
    assert back == whole, 'the widget was not put back, so the next control would be gone'
