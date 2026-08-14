<picture>
  <source media="(prefers-color-scheme: dark)" srcset="figures/logo_lockup_dark.png">
  <img src="figures/logo_lockup.png" alt="langaccess" width="360">
</picture>

[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![Code](https://img.shields.io/badge/code-MIT-green.svg)](https://opensource.org/license/mit)
[![Bundled model](https://img.shields.io/badge/bundled%20model-CC--BY--SA--3.0-orange.svg)](LICENSES/lid.176.CC-BY-SA-3.0.txt)

langaccess audits the language accessibility of a website. Given a URL, the tool renders the site
in a headless browser and classifies, for each language present, the form of access provided:
English-only content, machine translation, or text authored by the site itself. The result is a
classification and a per-language breakdown, and each finding is returned with the URL and quoted
text that support it, so that any result can be verified without repeating the crawl. The tool
describes and classifies what a site provides; it does not score how well a site serves any
population.

![How a result is produced. A website address, with robots.txt respected, is read two ways: rendered in a headless Chromium, and fetched again as the plain server document. The difference between the two separates widget text from the site's own writing, the codebook rules judge each language on authorship and extent, and three things come out: a classification, an evidence record with the URL and quoted text, and a read-quality record.](https://raw.githubusercontent.com/nariyoo/langaccess/main/figures/system.png)

langaccess is a wrapper around two libraries.
[Playwright](https://github.com/microsoft/playwright-python) runs a Chromium that renders each
page and hands back its text, and [fastText](https://github.com/facebookresearch/fastText)'s
[`lid.176`](https://fasttext.cc/docs/en/language-identification.html) names the language of a passage
the package's own rules do not cover. There is no third-party HTML parser in the reading path: the
text comes from the rendered DOM rather than from source markup, since a translation widget rewrites
the DOM and leaves the markup alone.

The package supplies the crawl and the judgement: which pages to open and in what order,
the language controls to work on the page, the separation of translation-widget output from text the
site wrote, the length and script thresholds a finding has to clear, and the record of what the
search was worth, so that the absence of a language can be told apart from a failure to look for it.
`lid.176` is redistributed under CC BY-SA 3.0 and its licence text ships with the wheel.

## 1. Installation

```
pip install langaccess
python -m playwright install chromium
```

Python 3.10 or newer is required. The second command is required on a machine that has not
previously installed Playwright's browsers. The tool reads sites in a headless browser: an
installed Google Chrome is used where present, with the Chromium that Playwright manages as the
fallback. Where neither is present, `audit` raises `BrowserUnavailable` and the command line stops, prints
the reason once on stderr, and exits with code 3 rather than reporting every site as unreachable.
Three extras are available: `langaccess[web]` adds the FastAPI front end under `web/`,
`langaccess[frame]` adds pandas for `to_frame`, and `langaccess[test]` adds the test dependencies.

## 1.1 First run

A fresh install has no address list yet, so start with `langaccess demo`. It judges four invented
sites that ship inside the package, from pages stored with them: no browser starts and
no address is fetched, and what it prints is the instrument's own output rather than a transcript.
The four are one each of `english_only`, `machine_translate`, `true_multilingual` and
`unreachable`. The fifth class, `machine_translate_error`, needs a control to be clicked, which a
stored capture cannot carry, so no demo can show it.

```
langaccess demo
```

To check that a browser, the model and the crawl work on this machine, `calibrate --demo` reads one
real address, the author's own site. One address settles no setting.

The demo target carries a Google Translate widget offering eleven languages, and the author's own
Korean writing on its archive pages. The probe reports timing and depth and discards its results;
the same address read with the main command shows the fields a run produces.

```
langaccess calibrate --demo        # probe the demo address, print settings for this machine
langaccess https://nariyoo.com     # the same address, read for its verdict

https://nariyoo.com/
  verdict   machine_translate
  evidence  authorship authored   sufficiency 0 none
  languages English
    English          authored       4 section
    Korean           authored       0 none
  widget    Google Translate   pages read 15
  search    enough to rest an absence claim on  (budget_exhausted)
  switcher  offers 11: Arabic, Chinese, Hindi, Japanese, Korean, Nepali, Portuguese, Spanish, Tagalog, Thai, Vietnamese
  rules     12 a named language for true_multilingual; 13 archive and past-event pages; 14 an installed widget with no visible control
```

Under the rules, the command also prints each piece of evidence as its mechanism, its language and
the words that produced it. Section 2.4 shows that field on an address of your own.

The menu of eleven entries is recorded as the widget's offer, under the vendor's name, and widget
output is not text the site wrote; the Korean the site does carry is on archive pages, which rule 13
leaves outside the reading.

Before a long run, measure the settings on your own list with
`langaccess calibrate --from-file sites.txt -n 20`, and read the result against section 12.2 of
[docs/USAGE.md](https://github.com/nariyoo/langaccess/blob/main/docs/USAGE.md#122-calibration-before-a-long-run).

## 2. Quickstart

### 2.1 One address

```python
from langaccess import audit

r = audit('https://example.org')
r.verdict             # 'english_only' | 'machine_translate' | 'machine_translate_error'
                      #  | 'true_multilingual' | 'unreachable'
r.languages           # ['Chinese', 'English', 'Spanish']
r.by_language         # {'Spanish': {'authorship': 'authored', 'sufficiency': 3}, ...}
r.switcher_languages  # ['French', 'Spanish', 'Vietnamese']
r.read_quality        # {'pages_read': 15, 'sufficient': True, 'escalated': False, ...}
r.evidence            # [Evidence(mechanism='inline_text', url='...', quote='...'), ...]
```

`languages` lists the languages the classification counted, English among them. Where English is
absent, the site is written only in another language.

`by_language` reports each language separately, so a site with Spanish the organization published
and Vietnamese a widget produced shows one result of each.

`switcher_languages` lists what the page's language menu offers, a question separate from the
languages the site is written in. On a site carrying a widget the list is that widget's offer, and
`machine_translation` names the vendor, so a site offering two hundred machine-translated languages
and a site offering four are recorded distinctly.

`read_quality` reports how much reading the classification rests on: pages read, the stop reason,
and whether the search was deep enough for a claim that a language is absent.

`declared_off_site` reports where the page's declared alternates pointed: how many of them give an
address on another site, and which languages no alternate on this one named. An organization
publishing its Spanish on a second domain of its own and an address that has lapsed and now serves
somebody else look the same in a document, so the language is reported either way and `review` puts
the ambiguous results in front of a person.

### 2.2 Many addresses

`audit_many` reads a list of addresses through one browser instance and gives every site its own
browser context, so one site's cookies, cache and translation-widget state do not reach the next
site. Passing `store=` writes every page the crawl read to a capture file.

```python
from langaccess import audit_many

results = audit_many(urls, concurrency=4, timeout=120, store='run.jsonl')
```

Results come back in the order the addresses were given. A site that times out or fails is returned
as a `Result` carrying the failure in its `note`, and the rest of the list continues.

### 2.3 Stored captures

A capture taken with `store=` is judged again with no network access, which is how a rule change is
checked over a whole run in seconds and how a validation sample is coded twice against one capture
of each site.

```python
from langaccess import rejudge, rejudge_store

r = rejudge('run.jsonl', 'https://example.org/')
r.verdict          # judged over the stored pages
r.unreproducible   # the steps of a live audit a stored capture cannot carry

all_results = rejudge_store('run.jsonl')
```

Re-judgement calls the same functions the live audit calls, so a stored capture and a live audit
cannot diverge in their judgement logic.

A store holds the full HTML of pages other people wrote. It exists so a result can be re-checked;
publishing the file itself redistributes entire websites and is not covered by this package's
licence or practice. Publish results, counts and short quoted passages with their addresses, and
keep the store private.

### 2.4 Explanation

`explain` arranges what a result recorded into the working behind its classification: the numbered
rules that fired, in the stages the package applies them in, the evidence each one rests on with its
address and quoted words, the two axes per language, and how much reading the classification rests
on. It judges nothing itself.

```python
from langaccess import explain, explain_text

print(explain_text(r))
x = explain(r)     # the same arrangement as a dict
x['rules']['tested_not_fired']   # the one negative finding the record supports
```

A rule absent from a result has not been shown not to apply, so the rules are reported in five
states and only the rules `verdict_rules` asks on every call are reported as tested and not fired.
`explain` accepts a live `Result`, a re-judged one, and the dict a stored run holds.

### 2.5 Run comparison

`diff_runs` compares two runs over the same addresses and reports what moved per site: verdict
changes, languages gained and lost, and authorship changes.

```python
from langaccess import diff_runs, diff_text

d = diff_runs('before.jsonl', 'after.jsonl')
print(diff_text(d))
d['unreachable']['toward']   # the sites that stopped being readable, reported first and on their own
d['sites']['only_in_a']      # addresses in one run and not the other, counted and named
d['moved']                   # every site that changed, with both results of each
```

Movement toward `unreachable` is never netted against the rest, since a change that makes sites
unreadable would otherwise hide inside a favourable total, and an address present in one run and
absent from the other is never dropped.

### 2.6 Hand-coding queue

Three states a class does not settle: A site recorded `unreachable` was not read at all, and
an `english_only` verdict whose `read_quality` reports `sufficient: False` rests on a search the
package will not stand behind. `review` hands those results out as a work queue instead of
publishing them as verdicts, and `ingest` reads the finished sheet back. Each queued reading is
named by what is unsettled about it and carries the sentence a coder has to act on.

```
langaccess review run.jsonl -o review.csv     # one row per site a person has to decide
langaccess ingest review.csv run.jsonl        # the filled sheet, back into the run
```

```python
from langaccess import needs_human, contested, review_queue, ingest_review, hand_coding

needs_human(r)                  # unreachable, a thin absence claim, an unnameable translation
                                # control, or no class at all
contested(r)                    # settled, and shaped like the boundaries the model coders split over
q = review_queue('run.jsonl')
q['records'], q['unsettled']    # what was scanned, beside what needs a person
q['contested']                  # settled results a second look is worth, counted apart
records, report = ingest_review('review.csv', 'run.jsonl')
```

`contested` flags settled results shaped like the boundaries the model coders split over. No figure
is attached to the flag: what it offers a study is a place to spend a coder's time and not a
measured correction, and it moves no result.

Each row carries what a coder needs in order to decide without leaving the sheet: the address, the
class reached, why it is unsettled as a sentence, when it was read, how many pages the reading rests
on and the stop reason, the languages found, the language menu with the count of entries this
package cannot name, and the quoted words behind each finding.

A human verdict wins over the machine's and is recorded as one, as a piece of evidence whose
mechanism is `hand_coding`, carrying the verdict it replaced and the coder and date where the sheet
supplies them, so a later reader can ask what share of a figure came from a person. A sheet naming
an address the run does not hold is rejected whole and every fault is named. A queue that finds
nothing says so, and exits non-zero on request.

### 2.7 Site report

`report` renders one result as one document for the organization whose site was read, the only
output of this package addressed outside the project. It carries the classification with a sentence
saying what that class means, the languages one at a time, every quotation with the address it was
read at, the numbered rules that decided it, what the search covered and what it did not, and the
date and the version.

```
langaccess report run.jsonl https://example.org -o example.html
langaccess report run.jsonl --all --dir reports/
```

```python
from langaccess import report, report_text, write_report

print(report_text(r))
write_report(r, 'example.html')   # one HTML file, fetching nothing from anywhere
```

The document states what it is not, in full and in both forms: the package makes no determination
of compliance with any federal or state law, with any regulation made under one, or with any
professional guidance on interpretation, and holds no threshold at which a site becomes adequate.
It does not judge translation quality, a website is not a service, an absence covers the pages the
search read and nothing else, and a result is not carried forward. A record that never held a
result raises `NothingToReport` rather than rendering a page of headings over blanks.

### 2.8 Command line

```
langaccess https://example.org
langaccess --deep --timeout 240 https://example.org
langaccess --json --output out.jsonl --from-file sites.txt
langaccess --explain https://example.org
langaccess calibrate --from-file sites.txt -n 20
langaccess diff run_a.jsonl run_b.jsonl
langaccess review run.jsonl -o review.csv
langaccess ingest review.csv run.jsonl
langaccess report run.jsonl https://example.org -o example.html
langaccess depth capture.jsonl
langaccess retry run.jsonl --your-browser -o retried.jsonl
```

`depth` reports how far each language extends into the pages a capture holds and `retry` re-opens
the `unreachable` rows through a browser you are driving yourself; both are in
[docs/USAGE.md](https://github.com/nariyoo/langaccess/blob/main/docs/USAGE.md), sections 17 and 18.

## 3. Classes

`english_only`. No non-English text was found on the routes the crawl follows. The claim is bounded
by those routes, and the bound is recorded in `read_quality` on every result.

`machine_translate`. The site offers a translation widget and no non-English text was found outside
the widget's output. Widget output is not the site's own text and is unavailable whenever the widget
does not load, so it is reported apart from the class below.

`machine_translate_error`. The site offers a translation widget, a control on it was operated, and
the page did not change. What that establishes is that this automated browser could not obtain a
translation through the widget on that date. It is held apart from `english_only` because
`english_only` asserts that no other language was found, which was not established here;
a widget can work in one browser and not another, and one site in this class translated for a
visitor on a phone. Treat it as a site to open by hand: `review`
puts every one of them in the hand-coding queue. No accuracy figure covers this class, for the
reason given in [LIMITATIONS.md](https://github.com/nariyoo/langaccess/blob/main/LIMITATIONS.md).

`true_multilingual`. Non-English text is present in the document the server sent, so no browser-side
widget produced it. The text may be the site's own or a server-side translation plugin's, and the
`authorship` field on each piece of evidence records which was observed.

`unreachable` is a read outcome; it does not describe a form of access. The site was not read at
all, because of a bot wall, a timeout, a parked domain, or an empty response, so nothing is
established about its languages in either direction.

The five names are nominal. They are printed in a fixed order so that tables from different runs
line up, and that order is not a ranking: no class is better than another, none is a step toward
another, and a table sorted by class is not sorted by anything about the organizations. Scoring them
0 to 4 and entering that in a model is a misuse: `english_only` and `machine_translate` are on
the same rung of the sufficiency axis and differ only on whether a widget was found, and
`unreachable` is not a level of anything. The `authorship` values ARE ordered, by how directly the organization produced
the text, which says nothing about how well anyone is served.

## 3.1 Codebook

Every result names the numbered rules that decided it, in `Result.rules`. `RULES` is the registry
those numbers index, and each entry carries the rule's heading, the test it applies, and the objects
in `langaccess.core` that apply it, so a number printed in a table of results can be resolved without
the coding document this distribution does not carry. The paper gives the argument for each rule.

The numbers run 1 to 17 in the order the pipeline applies them, so the table can be read down the
page in the order a crawl asks each question. The stage column carries that order for reading and
can be renamed. The numbers cannot: a stored result and the coded standard both hold them as
integers.

<!-- codebook: generated from RULES, do not edit by hand -->
| # | stage | rule | criterion |
|---|---|---|---|
| 1 | Site identity | social media profiles | a Facebook, Instagram, LinkedIn, X/Twitter, YouTube, TikTok or Threads address is excluded; a site-builder address is not |
| 2 | Site identity | registrar parking pages | a registrar sales page, an expired-domain notice or an under-construction placeholder is unreachable, as a bot wall is |
| 3 | Pages in the reading | rendered pages as the unit | a downloadable document or an off-site form is not the site; what a visitor reads in the browser is |
| 4 | Pages in the reading | two clicks from the home page | the home page, a page linked from it, and a page linked from one of those |
| 5 | Pages in the reading | pages still in service, whatever their date | a page still served counts whatever its date; the archive shapes of rule 13 are the exception |
| 6 | Text against label | a paragraph of connected prose | four distinct function words inside one 500-character window of connected prose, so a tagline, a menu label or a list of titles does not clear it |
| 7 | Text against label | the paragraph standard in every script | rule 6 in any writing system, with the character count set per script |
| 8 | Text against label | names of organizations, places and people | an organization, place or personal name is evidence of no language, in either direction |
| 9 | Text against label | a bilingual line with a verb | a bilingual line with a verb meets the paragraph standard, and a verbless label does not |
| 10 | Evidence and its rung | authored text beside a widget | text a widget could not have produced counts against it, at the rung the page it sits on earns |
| 11 | Evidence and its rung | a plugin marker without content | a plugin marker counts only beside non-English content, never alone |
| 12 | Evidence and its rung | a named language for true_multilingual | true_multilingual only where the language can be named |
| 13 | Evidence and its rung | archive and past-event pages | a past-event write-up, a newsletter, a gallery caption or an index of old posts carries no reading |
| 14 | Site class | an installed widget with no visible control | a widget installed with no control rendering still classes the site machine_translate |
| 15 | Site class | an advertised locale route in English | a locale route the site itself advertises that returns the English page classes the site english_only; the server answered, whatever the browser |
| 16 | Site class | a worked control without effect | a control of a named widget that was operated and changed nothing classes the site machine_translate_error: the client failed to obtain a translation, and no absence is asserted. With no vendor named there is no widget to have failed, and the reading stands on what else was found |
| 17 | Site class | five locale mirrors without a vendor marker | five or more mirrored locale routes with no vendor marker read as machine translation; four do not |
<!-- end codebook -->

`rule_titles(r.rules)` turns the numbers into these titles, and the command line prints both. Rule
12 is a scoring rule with no object behind it: a language the instrument cannot name counts against
it rather than leaving the denominator.

## 4. Scope

langaccess classifies the form of language access a website presents. For each language it finds,
the tool records whether the text was authored by the site, produced by a translation widget, or
absent, and returns the URL and the quoted words behind that finding.

The tool does not evaluate whether a service meets a legal or professional standard. A
classification is not a determination of compliance with any federal or state law, with any
regulation made under one, or with any professional guidance on interpretation, and the package
holds no threshold at which a site becomes adequate. It does not assess translation quality, so
fluent authored Spanish and clumsy authored Spanish are classified alike. It does not measure
whether a person can obtain help, which turns on the telephone line, the intake desk, the
interpreter roster and the hours at which someone answers, none of which a website states and none
of which a crawler reads.

Questions about who receives service in which language are answered with survey, administrative and
interview data. A website classification is one observable in that work: what an organization
published, at the address where it published it, on the day it was read.

The baseline is English. Every classification rule asks what a site offers in addition to English,
the rules were written and their agreement measured on United States websites, and the language word
lists cover the languages spoken by immigrant populations in the United States. Carrying the package
into a setting with a different default language, such as Welsh and English or Finnish and Swedish,
means rebuilding the English entry in the languages list, the direction of the `machine_translate`
class and the word lists, and the agreement figure below would not carry across. The limits of a
classification produced within this scope are in LIMITATIONS.md, and the measurement behind each
limit accompanies the paper.

## 5. Accuracy

Classification agreement with a gold dataset coded blind by language models is 93.2% (Cohen's kappa
0.8962) on 1,861 United States websites, 94.3% (0.9043) over the 926 local government sites and
92.1% (0.8788) over the 935 nonprofit organization sites. Carrying the design weights the sites were
drawn under, the pooled figure is 94.7% [92.8, 96.1] with a kappa of 0.9124.

The figure covers three classes, `english_only`, `machine_translate` and `true_multilingual`.
`unreachable` and `machine_translate_error` are counted beside it and never inside it, which is why
the 1,861 is smaller than the 2,000 sites drawn. [LIMITATIONS.md](https://github.com/nariyoo/langaccess/blob/main/LIMITATIONS.md) carries that
ladder, the per-class recall and precision, and the build the table belongs to.

## 6. Limitations

[LIMITATIONS.md](https://github.com/nariyoo/langaccess/blob/main/LIMITATIONS.md) states what a reader must know to interpret a result, including
what the figures above do and do not cover. The measurement behind each limit accompanies the paper
and is not part of this distribution.

## 7. Documentation

These files travel with the source distribution and are not in the wheel, so a reader who installed
the wheel alone can retrieve them with `pip download --no-binary :all: langaccess`.

- [docs/USAGE.md](https://github.com/nariyoo/langaccess/blob/main/docs/USAGE.md), the full Python and command line reference, including crawler conduct
- [LIMITATIONS.md](https://github.com/nariyoo/langaccess/blob/main/LIMITATIONS.md), the limits of the instrument
- [CONTRIBUTING.md](https://github.com/nariyoo/langaccess/blob/main/CONTRIBUTING.md), the procedure for reporting a misclassified site

## 8. Citation

Cite the software. [CITATION.cff](https://github.com/nariyoo/langaccess/blob/main/CITATION.cff) holds the record, and the version belongs in the
citation, because a classification is the output of one rule set. The accompanying paper this
document refers to is not published yet.

### Methods wording

A verdict in a table is the output of a rule set, a crawl budget and a date, and a reader who has
only the tool's name cannot tell which of those produced the number. Adapt this, filling in the
four values from your own run:

> Website language access was classified with langaccess 0.1.0 (Yoo, 2026), which renders each site
> in a headless browser, reads up to N pages per site, and assigns one of five classes from the
> text it finds and the translation machinery it detects. Sites were audited between DATE and DATE.
> Of the N sites, N could not be read and are reported as `unreachable` and not as English-only.
> The package reports 93.2% agreement with a gold dataset coded by language models on 1,861 sites.

Four clauses get left out most often, and each changes what the numbers mean.

**Report `unreachable` as its own row.** A site behind a bot wall, a domain that has lapsed and a
server that timed out all land here, and folding them into any substantive class puts a measurement
error inside a finding. The unreachable class in LIMITATIONS.md has the reasoning.

**Name the crawl budget.** The class depends on how much of the site was read. A Spanish page four
clicks deep is found by a run that reads twenty pages and missed by a run that reads
five, and both runs are correct about what they read. `Result.read_quality` carries the number for
each site, and `capture_acceptance` says whether the search was thin enough that an absence claim
should not be made from it.

**Give the dates.** Sites are rebuilt, translation plugins are added and removed, and a domain
lapses. A verdict is a statement about a site on a day.

**Name the build that produced the classes.** Two builds can classify one stored capture
differently, in either direction, so two tables produced from the same addresses by different builds
are not comparable. A released version names one rule set, and 0.1.0 is the version every figure in
`LIMITATIONS.md` was measured on. A working copy taken from the repository between releases names
none, so a study running from source records the revision it ran.

If a reviewer asks which rules produced a class, every result carries them: `Result.rules` is the
list of numbered codebook rules that fired, and each piece of evidence carries the URL and the
quoted text that decided it. Those fields are what a reviewer should receive, in place of a summary
of them.

## 9. Related work

**Web accessibility auditors.** Auditors such as [axe-core](https://github.com/dequelabs/axe-core)
check the language DECLARATION:
WCAG success criterion 3.1.1 asks that the language of a page be programmatically determinable, and
the axe-core rules for it test whether a `lang` attribute is present and syntactically valid, so a
widget that rewrites `lang="en"` to `lang="es"` passes while adding no authored Spanish. One rule
in the wider family does compare the declared tag against the language of the text,
[ACT rule ucwvc8](https://www.w3.org/WAI/standards-guidelines/act/rules/ucwvc8/proposed/), and it is
absent from axe-core; the implementation that carries it furthest asks a caller-supplied oracle what
the language is, ships no oracle, and marks itself experimental. The models also do not fit. Every
axe finding is a property of a node in the rendered tree, and the difference between the served
document and the rendered one is a property of no node. The context axe accepts is an element, a
NodeList, a selector, an include and exclude pair, frames or shadow roots, never an address, so the
second fetch, the crawl and the sitemap read have nowhere to go in it.

**Federal positions on machine translation.** The line between authored and widget text is a live
disagreement. The Department of Justice said in 2011 that "The use of machine or automatic
translations is strongly discouraged even if a disclaimer is added"
([archived](https://web.archive.org/web/20250714055740id_/https://www.lep.gov/sites/lep/files/resources/081511_Language_Access_CAQ_TA_Guidance.pdf),
because lep.gov is
[suspended](https://www.justice.gov/crt/limited-english-proficiency)), and the Attorney General's
[memorandum of 14 July 2025](https://www.justice.gov/ag/media/1407776/dl?inline=) encourages
"responsible use of artificial intelligence and machine translation" instead. Executive Order 14224
revoked EO 13166 ([90 FR 11363](https://www.federalregister.gov/documents/full_text/text/2025/03/06/2025-03694.txt))
and the 2002 LEP Guidance was rescinded
([90 FR 15721](https://www.federalregister.gov/documents/full_text/text/2025/04/15/2025-06366.txt)),
while Title VI stands. This package holds no view on whether machine translation satisfies any
obligation.

**Language identification.** Which language a passage is written in is decided by fastText's
`lid.176`, on the languages the package's own word lists do not cover, behind a confidence floor and
the orthographic gates. The model ships inside the package under CC BY-SA 3.0; see section 10.

The prior audits of organizational websites, the work on detecting machine-translated text, and the
full reference list are in the paper.

## 10. Licence

MIT. See LICENSE. Every line of code in this package is under those terms.

One shipped file is not code and is not MIT. `src/langaccess/data/lid.176.ftz` is fastText's
lid.176 language identification model, distributed by its authors under CC-BY-SA 3.0 and
redistributed here byte for byte, so it stays under the licence it came with.
`LICENSES/lid.176.CC-BY-SA-3.0.txt` holds the attribution line, where the model came from, the sha256
of the shipped bytes and the full text of the licence. A built wheel carries it next to the MIT
LICENSE at `langaccess-<version>.dist-info/licenses/LICENSES/lid.176.CC-BY-SA-3.0.txt`, and both
files are named as `License-File` in the metadata, so an installed copy answers the licence
question without the repository.
