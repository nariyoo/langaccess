# Usage

The full Python and command line reference. [README.md](../README.md) covers the short form:
installation, one call, one command. Section 19 is the field list of one output row and section 20
is one study from installation to a coded table, for a reader who wants the shape of the whole thing
before the parts.

## 1. Result

```python
from langaccess import audit

r = audit('https://example.org')
r.verdict            # 'english_only' | 'machine_translate' | 'machine_translate_error'
                     #  | 'true_multilingual' | 'unreachable'
r.languages          # ['Chinese', 'English', 'Spanish']
r.by_language        # {'Spanish': {'authorship': 'authored', 'sufficiency': 3}, ...}
r.switcher_languages # what the page's language menu lists
r.authorship         # 'authored' | 'server_plugin' | 'client_widget' | 'unknown_widget' | 'none'
r.sufficiency        # 0..4
r.evidence           # [Evidence(mechanism='inline_text', url='...', quote='...'), ...]
r.rules              # [3, 8, 10]
r.machine_translation # the translation vendor detected, if any
r.audited_at         # '2026-07-29T18:04:11Z', when the site was read
r.tool_version       # which version of the rules read it
r.tool_build         # 'd4c011b3a7f2', the bytes of core.py that read it
r.judged_build       # the bytes that applied the rules, equal to tool_build on a live audit
r.read_quality       # how much reading the result rests on
```

`audited_at`, `tool_version`, `tool_build` and `judged_build` appear on every result and in
`to_dict()`. The tool reads live sites, so a stored result describes one site at one moment under
one set of rules, and a table of results that does not carry these fields cannot be compared with a
table taken at another time.

`tool_build` and `judged_build` are the first twelve hex digits of the sha256 of `core.py` as
installed, which `build_id()` returns on its own for a caller writing the value into a document.
The version label names a release; on a working tree it names the last release the literal was set
to, and one organization census holds 334 records whose reading came from one `core.py` while the
label beside it said 0.1.0 for another. One label named two instruments and the rows could not say
so. The build is the file that holds the rules, the constants and the crawl, so it moves when the
readings can move and does not move when a renderer changes. It is `''` on a record written before
the field existed and on an installation whose own bytes cannot be read, which is what a package
running out of a zip archive can honestly report.

`authorship` and `sufficiency` are the two recorded scales from which the three non-`unreachable`
classes are derived. `class_for` is the one place that derivation lives, and
`tests/test_core.py` writes the table out cell by cell as `DERIVATION_TABLE`.

`machine_translate_error` says what this client could obtain and not what the site provides, so a
consumer needs to know how firm the observation is. It is written where a control naming a language
was clicked, the page did not change, and no route and no other control produced that language,
and only on a site where a vendor marker was found, since the class names a machine translation
failing and there is no machine translation to name otherwise. The class is firmer than it looks
from the row. Every row shows a spent page budget, because the control step runs on the home page
before the interior crawl reads anything, so the unread pages are what happened afterwards. Measured
on 2026-09-18: all 33 addresses a live re-read of the 2,000-site gold frame put in this class were
re-operated one site at a time on a 300-second clock, against concurrency 8 and 240 seconds in the
capture, and 27 of the 33 returned the class, 26 of those 27 with `clock_exhausted` false. The 6
that moved moved to `machine_translate`, each because the same control produced a language the
second time. Where the clock does end the control scan with a candidate unworked, the note says so
beside the sentence about the dead control; the class is unchanged on those rows, because nothing
had recorded the shape before and it has no count to change it on.

`sufficiency` is not a record of how much was read, and it has been read as one for a whole coding
round. It scores what a reader who does not read English can do with the non-English text the
result counted, so a result that counted none scores 0: every `unreachable` reading, where there is
no text and no axis at all, every `english_only` one, and a `machine_translate` one whose second
language is the widget's own output. How much of the site was read is `read_quality`, which holds
`pages_read`, `clock_exhausted`, `sufficient` and `unread` among the keys listed in section 19, and
a run is judged on the share of its crawls whose clock ran out and on the median of `pages_read`.

`languages` and `by_language` include **English**. English is detected by the same function-word
machinery as the other Latin-script languages, under the same paragraph rule, and it carries the
same two axes. It decides no outcome: `class_for`, `verdict_for`, `verdict_rules`,
`counted_evidence` and both site-level axes never receive a piece of English evidence, and no
threshold depends on it. The value of the entry lies in the case where English is absent, which
identifies a site written only in another language, a case a list restricted to non-English
languages cannot distinguish from a bilingual site. A consumer that requires a list without English
filters the entry out:

```python
non_english = [lg for lg in r.languages if lg != 'English']
```

`provenance` is a deprecated earlier name for `authorship`, and the two halves of the rename follow
different schedules. A capture stored under the key `provenance` is read under that key
permanently, by `rejudge`, `read_store` and the judgement functions taken on their own; no
conversion is required. The deprecated names in code (`provenance_of`, `provenance_summary`, the
`PROV_*` constants, and read-only `provenance` properties on `Result` and `Evidence`) remain
available for one release and are then removed, and no warning is emitted when one is used.

## 2. Evidence record

`r.evidence` is a list of `Evidence` records, each with these fields:

| field | meaning |
|---|---|
| `mechanism` | `inline_text` (non-English text on a page the visitor lands on), `translated_page` (a separate page, opened through an `hreflang` link, a language-named path, or a guessed path, whose content is not the English page repeated), `translation_plugin` (a server-side CMS plugin marker in the HTML), `language_control` (a control with no address behind it, found by clicking it), `testimonial` (a quotation, inside a container the page publishes testimonials or reviews in) |
| `url` | the exact address the browser was at when the result was made |
| `quote` | the words that decided it |
| `language` | the language named |
| `server_html` | was this language also in the document the server sent, with no JavaScript run |
| `server_plugin` | did that server document carry a CMS translation-plugin marker |
| `authorship`, `sufficiency` | the two axes for this piece of evidence |
| `rules` | the numbers of the classification rules that decided this finding |
| `reach` | whether this finding is on a page a reader arrives at, or behind a control |

`rules` appears on the `Result` as well, where it holds the rules that decided the site: the rules
on the evidence the classification counted, plus the site-level rules that fired. The numbers index
`RULES`, the registry the package ships, whose record for each rule carries a title and the objects
in `langaccess.core` that apply it, so every rule number a result names resolves inside the package.
`rule_titles(r.rules)` converts the numbers to titles, and the command line prints both.

`testimonial` is the one mechanism the classification never counts. It is written where non-English
text was found inside a container the page publishes quotations in, which is `<blockquote>`, `<q>`,
a `<figure>` carrying a `<cite>`, or an element whose `class` or `id` names a testimonial or a
review. The words are a visitor's and not the site's, so the row carries rung 1, the rung the
codebook gives a quoted testimonial, it carries no `authorship`, because that axis says who
produced the text and has no value for a visitor's words, and it names no codebook rule, because no
rule counts it. `counted_evidence` drops it, so no class, no language list and neither site-level
axis can move on it; a language seen only in a quotation appears in `by_language` at rung 0 and not
in `languages`, which is where a language found on an archive page has always been. It is on the
record so that a study that wants to count testimonials can, and so that a reader who is checking a
site by hand can see what the reading declined to use. What the container rule does and does not
reach is [LIMITATIONS.md](../LIMITATIONS.md) section 7.2.

`r.machine_translation` separately names the translation vendor detected, if any, whether or not
that vendor affected the class.

## 3. Audit options

The keyword arguments on `audit` and `audit_async` are `max_pages`, `deep`, `timeout`, `keep_pages`,
`block_private_hosts`, `respect_robots`, `store` and `escalate`.

`respect_robots` is enabled by default. Passing `False` is an override for a researcher who has the
site owner's permission, and not a configuration choice, because it causes this package to fetch
addresses a host has asked crawlers to avoid.

`block_private_hosts` resolves the host of every request the browser makes and refuses those that
resolve off the public internet. It costs a DNS lookup per host and is disabled by default; it is
worth enabling when the address list came from a source other than the person running the audit. It
is a defence in depth and not a guarantee: it resolves each host and then the fetch resolves it again
independently, so a name that answers with a public address for the guard and a private one for the
fetch (DNS rebinding) can still slip through. Where that is part of the threat model, run behind a
network egress policy that blocks the private ranges, which is the one control that can pin the
address the connection opens.

`store='run.jsonl'` appends one JSON line per audited site, holding the class, the evidence and the
HTML of every page read. A path ending `.gz` is written compressed.

An async version is available for auditing many sites without blocking on each one:

```python
import asyncio
from langaccess import audit_async

async def main():
    return await asyncio.gather(*(audit_async(u) for u in urls))

results = asyncio.run(main())
```

`asyncio.gather` must be called with a loop already running, so it is placed inside the coroutine
and not inside the `asyncio.run` call.

## 4. Many addresses

`audit_async` launches a browser instance per site and discards it, which costs one to two seconds
and a few hundred megabytes per site. `audit_many` launches one instance for the whole list:

```python
from langaccess import audit_many

results = audit_many(urls, concurrency=4, timeout=120, store='run.jsonl')
```

`audit_many_async` is the equivalent for code that already has an event loop, and takes an
`on_result` callback. Results are returned in the order the addresses were given, regardless of the
order in which the audits finished. Every site still receives a browser context of its own, which
keeps one site's cookies, cache, storage and translation-widget state out of the next site's
reading, so a batch applies the same per-site reading `audit` applies. A site that times out,
raises, or fails twice over is returned as a `Result` with the failure recorded in its `note`, and
the rest of the list continues. One `robots.txt` is fetched per origin and reused across the whole
batch. Both forms take `on_result`, `sectors` and `retain`.

When a batch has run to the end, the rows it produced whose failure says nothing about the site are
read once more, on a browser launched for them alone, at concurrency 2. A row whose failure was a
closed connection or a protocol error gets the same per-site `timeout` the run was given, since
neither of those spent it. A row that TIMED OUT gets twice that clock, capped at 600 seconds,
because the clock is what it ran out of and reading it back under the same bound asks a question
already answered. Measured on the 12 timed-out addresses of the 2026-09-18 re-read of the gold
frame's unreachable rows: under the run's own 240-second bound the pass recovered none of them, and
the same 12 read at 480 seconds with everything else identical answered on 11, at a median of 15
pages. Three failure kinds are in that pass, `connection_closed`,
`protocol_error` and `timeout`, and the reasoning for each is in section 19.1. The second reading
replaces the first only where it read at least one page, and either way the row's note ends
`(retried on a fresh browser)`, so a store shows which rows were offered the pass and what came of
it. One pass and no more, because a row that failed the same way on two browsers is a row about the
site. Only the rows in the pass are settled late; `store` and `on_result` still receive one row per
address and receive it once. `retry_pass=False`, or `--no-retry-pass` on the command line, turns it
off, which is how a study measures what it recovers.

A host that answered is not in the pass. `bot_wall`, the HTTP families, `robots_disallow`,
`no_dns`, `parked_domain` and `directory_profile` are all a site or a registry answering, and
reading them again would be this package fetching addresses that already said no. `retry
--your-browser`, in section 18, is the route for those.

`sectors` is one label per address, copied onto each `Result.sector` unchanged, for the join a
study always needs and the crawler cannot read. `sector_caveat(result)` reads it and returns a
one-line warning when a reading falls in the stratum the standard agrees with least,
`true_multilingual` on a government site, so a consumer can check or correct per stratum:

```python
results = audit_many(urls, sectors=sectors, store='run.jsonl')      # sectors parallels urls
for r in results:
    if sector_caveat(r):
        print(r.url, sector_caveat(r))
```

`retain=False` frees each reading the moment it has gone to `store` and `on_result`, so a run over
tens of thousands of addresses is bounded by one batch of memory rather than by the whole list. It
returns an empty list, so a run that turns retention off has to take its results through `store` or
`on_result`:

```python
audit_many(urls, store='big_run.jsonl', on_result=my_writer, retain=False)   # holds one batch
```

A run spread over several machines, or a CI job, downloads Chromium once per machine by default.
Point `PLAYWRIGHT_BROWSERS_PATH` at one shared directory before `python -m playwright install
chromium` and every run on that machine reads the one copy instead of its own; a read-only shared
mount lets a cluster share a single install. Leave it unset for the ordinary single-machine case.

## 5. Stored captures and re-judgement

A capture taken with `store=` can be judged again later without network access:

```python
from langaccess import rejudge, rejudge_store, read_store

r = rejudge('run.jsonl', 'https://example.org/')
r.verdict          # judged over the stored pages, with no network access
r.unreproducible   # the steps of a live audit a stored capture cannot carry
```

`rejudge` calls the same `languages_in`, `language_coverage`, `counted_evidence`, `verdict_for` and
`class_for` the live audit calls. The rules are not duplicated for re-judgement, so a stored
capture and a live audit cannot diverge in their judgement logic. Sharing those functions makes a
rule change checkable over a whole run in seconds instead of hours of live crawling, and allows a
validation sample to be coded twice against one stored capture.

From 0.2.0 they share the READER as well, which is a separate claim and was not true before.
`_page_text` turns a document into the text the rules are applied to, the live audit hands it
`page.content()`, which is byte for byte what `store=` writes, and `rejudge` hands it those same
bytes back. Until then the live audit read the browser's own rendered text and a re-judge read the
served document, so the same page could be judged two ways: over the 1,992 addresses of the
2026-09-17 gold-frame capture the two verdicts differ on 24 sites and the language lists on 13
more. Since every agreement figure this package publishes is computed by re-judging captures, the
reading a consumer gets live is now the reading those figures describe.

A store is other people's writing. Every record holds the full HTML of pages somebody else wrote
and holds the copyright to, and the capture exists so that a result can be re-checked and a rule
change re-scored, which is the use the quotation of evidence rests on. Publishing the store itself
is a different act: it redistributes entire websites, including any personal information their pages
carried, and neither this licence nor the package's own practice covers that. The validation work
behind this package kept its captures private and published results, counts and short quoted
passages with their addresses, which is the form to publish in. A store file is scraped data, and a
field's rules for scraped data apply to it.

Five steps of a live audit cannot be reproduced from stored HTML, and each is named on
`r.unreproducible` instead of being answered with a slightly different question: the
server-document confirmation that decides authorship, a clicked language control, the locale-route
probe behind rule 15, whether a page came from the sitemap or from a link, and the escalated pass,
which fetches addresses a first pass never queued. `REJUDGE_LIMITS` holds the full statement of
each, plus a sixth entry for a stored record that holds no HTML at all, which replaces the list
rather than joining it. There were six of them until 0.2.0, and the one that left is the browser's
own rendered text: it is not a step a capture cannot carry any more, because it is not a step the
live audit takes. A row written by an earlier release still carries `browser_rendered_text`, where
it is the truth about that row. `rejudge_store(path)` re-judges every record
in a file and `read_store(path)` yields the raw records.

A re-judged result names six things and not two. `audited_at`, `tool_version` and `tool_build` are
the capture's own and are carried forward: when the bytes were fetched, by which release, and by
which build. `judged_at`, `judged_version` and `judged_build` are this run's: when the rules were
applied to those bytes, and by which release and build.

```python
r = rejudge('run.jsonl', 'https://example.org/')
r.tool_version, r.judged_version    # ('0.1.0', '0.2.0') on a capture judged by later code
r.tool_build, r.judged_build        # ('d4c011b3a7f2', 'd103f9291c8e'), the two files
```

On a live audit both pairs are equal, because the capture and the judgement are one act, so a row
whose versions or whose builds differ is a re-judged row and says so without anybody having to
remember which file it came from. The builds are the pair that answers on a working tree, where two
re-judges months apart can carry one version label and different code. A capture written before
`tool_build` existed carries `''` forward, so a row with an empty `tool_build` and a filled
`judged_build` is a store taken under 0.1.0 judged by this one.

Judging a capture under a build it was not taken with is what `rejudge` is for, so a version
difference is recorded and never refused. What the store still does not record is the crawl
SETTINGS the capture was taken under, so a capture taken with `deep=True` and one taken with
`deep=False` are indistinguishable in a file, and nothing can compare them.

## 6. Explanation

`explain` arranges what a result already recorded into the working behind its classification, and
`explain_text` prints the same arrangement for a person:

```python
from langaccess import audit, explain, explain_text

r = audit('https://example.org')
print(explain_text(r))
x = explain(r)       # the same arrangement as a dict
```

The output holds the numbered rules that fired, grouped into the stages in which the package
applies them, since `Result.rules` is a set of numbers and rule order is not application order;
the evidence each rule rests on, with the address it was read at and the words that decided it;
which pieces of that evidence the classification counted; the two axes per language with the rung
named; and `read_quality`, which is what an `english_only` verdict rests on entirely, that verdict
being the only class that asserts an absence.

A rule number falls into one of five places. A rule
is `fired` when it is on `Result.rules`. It is `fired_on_uncounted_evidence` when it is on a piece of
evidence `counted_evidence` did not count, which is how an archive page's Spanish shows both that it
passed the paragraph gates and that rule 13 then set it aside. It is `tested_not_fired` for the rules
`verdict_rules` asks on every call, which is the only negative finding on the record. It is
`not_in_code` where a rule's own registry record says why nothing here can apply it, which no rule
says today. Everything else is `not_recorded`, meaning the result says nothing either way, and the explanation reports that
instead of converting silence into a rule that did not apply.

`explain` accepts a `Result` from `audit` or `rejudge`, and the dict a stored run holds, so a row
written years ago is explained without being re-judged. On a re-judged capture the explanation lists
`unreproducible` with the full statement of each limit, since what a capture could not carry is the
first thing a reader of one has to know. Nothing here judges anything: `counted_evidence` is the one
function it calls, and it is the same call the verdict made.

## 7. Run comparison

`diff_runs` compares two runs over the same addresses and reports what moved:

```python
from langaccess import diff_runs, diff_text

d = diff_runs('before.jsonl', 'after.jsonl')
print(diff_text(d))
d['unreachable']['toward']   # the sites that stopped being readable
d['sites']['only_in_a']      # addresses in the first run and not the second
d['moved']                   # every site that changed, with both results of each
```

Both arguments are paths to files holding one JSON object per line, as `--json --output` and
`--store` both write, or iterables of records already in hand. A path ending `.gz` is read
compressed. A site written twice in one file is the store appending, and the last row is the one
compared, which is what `rejudge` does with the same file; how many rows collapsed that way is
reported on the run.

Two rules of this project's measurement discipline are in the implementation rather than left to a
caller. Movement toward `unreachable` is reported separately and first, and is never netted against
anything: a bot wall, a slower machine and a shorter timeout all turn results into `unreachable`,
and a total that adds those to the sites that genuinely moved reports an instrument failure as a
finding. Recovery from `unreachable` is held out of the tallies for the same reason in the other
direction, since a site the earlier run could not read has not gained a language by becoming
readable. The verdict, language and authorship counts are therefore computed over `compared`, the
sites read in both runs, and the four counts account for every address in both:
`sites['both'] == compared + len(unreachable['toward']) + len(unreachable['away']) +
unreachable_in_both`.

The second rule is that an address present in one run and absent from the other is counted and
named, in `sites['only_in_a']` and `sites['only_in_b']`. A stage that compares an intersection and
calls it a comparison is what turns a run that lost two hundred addresses into a sentence about
forty sites that improved. The human summary prints those counts before it prints any tally, and
holds back only the names past twenty, with the remainder stated and the full list in the dict.

## 8. Hand-coding queue

Three states a class does not settle: A site recorded `unreachable` was not read at all, and
an `english_only` verdict whose `read_quality` reports `sufficient: False` is an absence claim
resting on a search the package itself will not stand behind. A third state is not a class at all: a
control labelled Translate that no vendor pattern here can name, which `authorship` records as
`unknown_widget`. A fourth is a control that was worked and did nothing, which the note records and
which reaches the queue whether or not the class could act on it. `needs_human` reads the verdict,
`read_quality`, `authorship`, `declared_off_site`, the note and `machine_translation`, and answers
whether one result needs a person:

```python
from langaccess import needs_human, unsettled_reason, review_queue, write_review

needs_human(r)        # True for a result this package could not settle
unsettled_reason(r)   # why, in a sentence, or '' where it is settled

q = review_queue('run.jsonl')
q['records'], q['unsettled']    # what was scanned, and what needs a person
write_review(q, 'review.csv')   # the sheet, one row per unsettled site
```

Seven states are flagged. `unreachable` always, since nothing is established about such a site's
languages in either direction. `english_only` where `read_quality['sufficient']` is false, or where
the record carries no `read_quality` at all, since `english_only` is the only class that asserts an
absence and the field is the record's own statement of what the search will carry. Any record whose
verdict is not one of the classes this package defines, the empty string included, since a blank taken for a class is
how a gap becomes a finding. And any record whose `authorship` is `unknown_widget`: a control
labelled Translate was drawn, no pattern here could name what runs it, and no non-English text was
found, so what a visitor gets from that control is unsettled. The verdict does not move for it. One
click settles it, and the sheet's reason column says so.

Two more are about a control that WAS worked. `machine_translate_error` always, under the kind
`dead_control`: a widget was named, a control on it was operated, the page did not change, and that
is what an automated browser could obtain rather than a finding about the site, since a widget can
work in one browser and not another. And, under `dead_control_no_vendor`, an `english_only` record
whose note says a clicked language control changed nothing and whose `machine_translation` is
empty. Rule 16 reads `a control of a named widget`, so where no vendor pattern matched there is no
widget for `machine_translate_error` to be about and the reading falls to `english_only`, which
leaves the one class that asserts an absence asserting it over a control a visitor can see. The
verdict does not move for either. The second is restricted to `english_only` deliberately: the same
observation beside `true_multilingual` or `machine_translate` settles nothing, because those
verdicts rest on something that was found. Measured over the 2,000-site gold frame on 2026-09-18,
88 readings record a dead control; 33 are `dead_control`, 14 are `dead_control_no_vendor`, and the
other 41 are left alone.

And any record whose every non-English language was named only by an alternate pointing at another
site, where the result's own findings name nothing else. The document does declare the language and
the package reports it; whether the address it gives belongs to this organization is a separate fact
no document settles, and the two shapes are indistinguishable in the markup. An organization
publishing its Spanish on a second domain of its own looks exactly like an address that has lapsed
and now serves a squatter whose alternates are the squatter's, which is what happened to one
county's domain. One look at the address settles it.

Each of the seven kinds keeps its own name on the sheet, and each carries the sentence a coder has
to act on. `review.KIND_ORDER` is the roll, and `KIND_TITLE` the line the summary prints for each;
a kind missing from either is a test failure rather than a queue that quietly hides one of its own.

A thin search behind `machine_translate` or `true_multilingual` is deliberately **not** flagged.
Those verdicts rest on something that was found, and a thin search that found it is right for the
same reason a thorough one is. Neither is an `english_only` verdict on a search the record calls
sufficient, whose bound is recorded rather than doubtful, and neither is a language menu carrying
entries the package cannot name, since the menu is not the verdict. The sheet prints that count
beside the menu, so a coder queueing such sites by hand has the number in front of them, but no
result enters the queue on it alone.

```
langaccess review run.jsonl -o review.csv
langaccess review run.jsonl -o review.csv --fail-on-empty
```

The sheet holds one row per unsettled site, in these columns:

| column | what it holds |
|---|---|
| `url` | the address |
| `verdict` | the class the package returned |
| `reason` | why the result is unsettled, as a sentence, carrying the note where the result left one |
| `audited_at` | when the site was read, since a coder opening it today may be looking at a different page |
| `pages_read` | how many pages the reading rests on |
| `crawl_stopped_by` | the stop reason, in words, with the count of locale-tree addresses the site advertises that were found and not read |
| `languages` | the languages the classification counted |
| `widget` | the translation vendor detected, if any |
| `switcher` | what the site's language menu offered, and how many of its entries this package cannot name |
| `declared_off_site` | how many of the page's declared alternates give an address on another site, and which languages no alternate on this one named |
| `evidence` | the words behind the first findings, each with the address it was read at |
| `human_verdict`, `human_languages`, `note`, `coder`, `coded_at` | blank, for the person |

Everything a coder needs in order to decide is in the row, because a coder who has to go and find
context will not. The file is written as UTF-8 with a byte order mark, so a quotation in Khmer,
Arabic or Amharic opens correctly in Excel.

### 8.1 Contested shapes

Whether the package can settle a result is one question. Whether a result it did settle is one
the model coders would have argued about is another, and `contested` answers that one. It flags a
result this package stands behind whose SHAPE is where the validation's blind coders disagreed with
each other. It never overlaps with `needs_human`: a result that is unsettled
returns an empty tuple, by construction.

```python
from langaccess import contested, contested_reason, CONTESTED_KINDS, CONTESTED_TITLE

contested(r)          # ('fragment_beside_widget',), and often ()
contested_reason(r)   # why, in a sentence, or '' where no shape holds
CONTESTED_KINDS       # the three names, in the order the summary prints them
CONTESTED_TITLE       # {name: the shape in words}
```

Three shapes are flagged, the third being a machine_translate reading in which rule 17's mirror
count set aside authored evidence the site already carried. `fragment_beside_widget` is a named widget on the site, a verdict of
`true_multilingual`, and authored evidence at the notice rung and no higher: the organization wrote
something in the language and a widget offers the rest, so the verdict turns on whether one authored
passage outweighs the widget. `one_language_notice` is one
non-English language on the record, at notice level, carrying the class by itself, with no second
language corroborating it and one passage standing for the whole verdict.

No figure is attached to the flag, and it moves no result: it writes no field and appends no
evidence, so a caller who ignores it holds exactly the result they held before. It is not the
queue either. A contested
result is counted as settled everywhere it appears, because summing the two hides the one number a
run is judged by, which is how much of it a person must do.

`review_queue` reports both counts and carries the contested rows at the end of the sheet:

```python
q = review_queue('run.jsonl')
q['unsettled']         # results a person MUST settle
q['contested']         # settled results carrying one of the three shapes
q['contested_kinds']   # {'fragment_beside_widget': 12, 'one_language_notice': 5,
                       #  'locale_mirrors_over_a_reading': 2}
q['rows']              # the unsettled rows first, the contested rows after them
```

A contested row is an ordinary review row whose `reason` column carries `contested_reason` instead
of `unsettled_reason`, so a coder reads a sentence in the column they already read and the sheet
needs no second format. A record carrying no `sufficiency` field carries neither shape, both of them
being statements about the rung, so a run written before that axis existed is not flagged wholesale.

One command-line behaviour follows from the counts being kept apart: `langaccess review` writes no
sheet at all when `unsettled` is zero, whatever `contested` holds, and prints the counts instead. A
study that wants the contested rows on their own writes them out of `q['rows']`, or filters the run
with `contested` directly, as the worked example in section 20 does.

## 9. Sheet ingest

```
langaccess ingest review.csv run.jsonl              # writes over run.jsonl
langaccess ingest review.csv run.jsonl -o settled.jsonl
langaccess ingest review.csv run.jsonl --dry-run    # report only
```

```python
from langaccess import ingest_review, write_records, hand_coding

records, report = ingest_review('review.csv', 'run.jsonl')
report['applied']            # the addresses a person settled
write_records(records, 'settled.jsonl')
```

A human verdict wins over the machine's **and is recorded as one**. The record keeps every field it
had, its `verdict` becomes the coder's, its `languages` become the coder's where the sheet names
any, and a piece of evidence is appended whose `mechanism` is `hand_coding`, carrying the verdict
and languages the machine returned, the coder's note as the words that decided it, and the coder and
date where the sheet supplies them. `hand_coding(record)` returns that entry, so the share of a
figure that came from a person is a count and not a guess:

```python
share = sum(1 for rec in read_store('settled.jsonl') if hand_coding(rec)) / n
```

The mechanism name is deliberately outside `OWN_MECHANISMS`, the tuple `counted_evidence` tests, so
a hand coding can never be counted back into a machine judgement however the record is later
re-read.

A blank `human_verdict` is a row nobody finished; it is counted and left alone, since a coder who
wrote nothing has not agreed with anything. A blank `human_languages` leaves the machine's list
standing for the same reason, and the word `none` in that cell clears it.

The sheet is rejected whole (the exception raised is `SheetRejected`), and nothing is written,
when any row cannot be applied: an address that
is not in the run, an address written twice, a row with no address, or a `human_verdict` outside the
classes this package defines. Every fault is named with its spreadsheet row number. A sheet carrying an address the
run does not hold is a sheet built against a different run, and applying the rows that happen to
match would put half a coding round into a file and report success.

The settled run is written over `RUN` unless `-o` names somewhere else, whole and then moved into
place, so a run being replaced by its own settled form is never left half written. Passing a run
through the sheet and back with nothing filled in returns the run unchanged, byte for byte.

Re-judging a settled run with `--rejudge` re-derives the machine classification from the stored pages and
does not carry the hand coding forward; a hand coding belongs to the run file, and a capture holds
what a site served.

## 10. Site report

`explain` answers a methodologist, `diff` answers a study comparing two runs, and `review` hands a
coder a spreadsheet. None of the three can be handed to the organization whose site was read.
`report` is the fourth part and the one addressed outside this project: it renders one site as one
document, for a city clerk or a hospital's language-access officer who has never used this package.

```python
from langaccess import report, report_text, report_html, write_report

print(report_text(r))
write_report(r, 'example.html')      # one HTML file, fetching nothing from anywhere
write_report(r, 'example.txt')       # the same document as plain text
d = report(r)                        # the same arrangement as a dict
d['sections']                        # the sections the rendered document holds, in order
```

```
langaccess report run.jsonl https://example.org -o example.html
langaccess report run.jsonl                       # the only record in the run, printed as text
langaccess report run.jsonl --all --dir reports/  # one document per address in the run
```

The document carries the classification with a sentence saying what that class means, since the
five words this package uses are its own vocabulary; the languages one at a time with both axes and
what each rung means, since one summary hides a site with Spanish its staff wrote beside Vietnamese
a widget produced; every quotation with the address it was read at, since the reason to hand
somebody a result is that they can open the address and check it; the numbered rules that decided
the class, and separately the rules that read a finding the class did not count; what the search
covered and what it did not; and the date and the version, since a result describes one address at
one moment under one rule set.

It states what it is not, in full, in both forms and at the foot where a reader arrives at it after
the finding. The package makes no determination of compliance with any federal or state law, with
any regulation made under one, or with any professional guidance on interpretation, and holds no
threshold at which a site becomes adequate. Beside that: the package does not judge how good a
translation is; a website is not a service, and whether a person can obtain help in a language
turns on the telephone line, the intake desk and the interpreter roster, none of which was read
here; an absence covers the pages the search read and nothing else; and a result is not carried
forward, since sites change and rules are revised. Those five statements are `langaccess.REPORT_LIMITS`, and
they are the part of the module to change most carefully.

The addresses under the search are described as the set they actually are. A capture written with
`store=` holds every page the crawl read, and the document names them and says so; a plain result
row holds no page list, so the only addresses on it are the ones its findings were quoted from, and
the document says that instead. Nothing is inferred either way.

`report` raises `NothingToReport` for a record that never held a result, meaning one with no
address, or one carrying no class, no evidence, no languages and no record of the search. A site
that was genuinely not read is a result and gets a document saying so; a row nobody filled in is
not, and rendering it would produce a page of headings indistinguishable from a finished audit. `--all`
names every such record on its own line and exits 4 when no record in the run held a result.

The HTML form is one file with no stylesheet, script, font or image fetched from anywhere, so it
opens the same from an attachment, from a shared drive and from a machine with no network. Every
`href` in it is one of the site's own addresses. Quotations are escaped and carry `dir="auto"`, so a
sentence in Arabic, Hebrew or Urdu reads in its own direction. `--format` chooses the form where the
output path does not; with neither, text is what is printed.

Nothing here judges a site. `counted_evidence` is the one deciding function it calls, which is the
same call the classification made, and the rule statuses come from `explain` rather than a second
copy of them.

## 11. Jupyter

A notebook already has an event loop running, so `await audit_async(url)` in a cell is the direct
call:

```python
from langaccess import audit_async

r = await audit_async('https://example.org')
```

`audit(url)` also works in a notebook. When it finds a loop already running it delegates the audit
to a helper thread with a loop of its own and waits for the result, avoiding the RuntimeError that
`asyncio.run` raises when it is asked for a second loop in one thread. `audit_many` behaves the
same way.

## 12. Command line

```
langaccess https://example.org https://other.org
langaccess --json https://example.org           # one JSON object per line
langaccess --concurrency 4 url1 url2 url3 ...    # audit several URLs at once
langaccess --deep --timeout 240 https://example.org   # slower routes, capped per site
langaccess --from-file sites.txt                 # one address per line, # comments skipped
langaccess --json --output out.jsonl --from-file sites.txt
langaccess --shared-browser --concurrency 8 --from-file sites.txt   # one browser for the run
langaccess --shared-browser --no-retry-pass --from-file sites.txt   # without the second reading
langaccess --block-private-hosts --from-file addresses-from-elsewhere.txt
langaccess --store run.jsonl.gz --from-file sites.txt      # keep every page read
langaccess --resume out.jsonl --json --output out.jsonl --from-file sites.txt  # carry on
langaccess --rejudge run.jsonl.gz                # judge the stored pages again, no network
langaccess --explain https://example.org         # the rules, evidence and axes behind one verdict
langaccess --explain --rejudge run.jsonl https://example.org    # the same, off a stored capture
langaccess --json --explain --from-file sites.txt          # one explanation object per site
langaccess calibrate --from-file sites.txt -n 20 # settings measured on this machine, before a run
langaccess calibrate --demo                      # one address, to see the tool work before a list
langaccess diff run_a.jsonl run_b.jsonl          # what moved between two runs of one frame
langaccess diff --json run_a.jsonl run_b.jsonl   # the same comparison as data
langaccess review run.jsonl -o review.csv        # the results that need a person, as a sheet
langaccess ingest review.csv run.jsonl           # the filled sheet, back into the run
langaccess report run.jsonl URL -o site.html     # one result, as a document about one site
langaccess report run.jsonl --all --dir reports/ # one document per address in the run
langaccess depth capture.jsonl                   # how far each language reaches into the pages read
langaccess retry run.jsonl --your-browser -o retried.jsonl   # the unreachable rows, again
langaccess --ignore-robots https://example.org   # override, with the owner's permission
langaccess --max-pages 12 --timeout 300 https://example.org   # a wider read, and clock to pay for it
langaccess --delay 1 --from-file sites.txt       # wait a second before every page fetch
langaccess --min-median-pages 2 --from-file sites.txt   # move the run-level acceptance floor
langaccess --max-thin-share 0.4 --from-file sites.txt   # move the run-level thin-reading ceiling
langaccess --strict --from-file sites.txt        # exit 9 if the finished run is a degraded one
langaccess --version
```

`--strict` changes the exit code and nothing else. The run is performed as it is performed without
the flag, every row it writes is written, and afterwards the process exits 9 when
`capture_acceptance` refuses the finished run or when any row carries the note a site gets after
answering nothing on every browser driver it was offered. Both conditions were already detected and
neither moved the exit code, so a run degraded by a driver that died part way through reached a
pipeline as a success.

Every string given as an address is checked before any browser starts, whether it came from the
command line or from `--from-file`. One that is not an address is not audited and is given no
verdict; it is named on stderr with the reason and the run exits 6. Section 13 has the rule and why
a rejected input may not become an `unreachable` row.

A string opening with a scheme token and a colon is an address only when what follows the colon is
a port number, so `example.org:8080/x` and `localhost:8000` are addresses and `mailto:`, `tel:`,
`sms:`, `javascript:`, `data:`, `file:`, `ftp:` and `about:` are not. Until 0.2.0 they were:
none of them carries `//`, the normalisation put `https://` on the front, and `https://mailto:a@b.c`
parses as a URL whose user name is `mailto:a` and whose host is `b.c`, so an email address in a
column of websites became a site and a verdict was recorded against whatever `b.c` was. An address
naming a user or a password before the host is refused for the same reason and on its own account,
since no public website address carries credentials.

`--from-file` reads a UTF-8 text file holding one address per line, skipping blank lines and lines
beginning with `#`, and `--from-file -` reads that list from standard input. A path that does not
exist, a directory, and a file that is not UTF-8 each produce one sentence on stderr naming the path
and exit 2, as a file holding no addresses already did.

`--output` writes the JSON lines a run produces and does nothing without `--json`. Given without it
the command line says so once on stderr and the run continues, on the audit path and on `--rejudge`
alike.

`--resume PATH` continues a run that was interrupted. PATH is the `--output` or `--store` file the
first attempt was writing, both of which are appended to as each site finishes and flushed per row,
so every site the run finished is on disk whether it ended or was killed. The addresses already in that
file are dropped from the list and the counts are printed: how many rows were read, how many
addresses were skipped, how many are left. Nothing is skipped silently.

The match is on `requested_url`, the address as the run was given it, since matching on `url` would
put back every site that redirected. A file written before that field existed is matched on `url`
instead, and the count of such rows is printed too, since a redirected site in that file can be read
twice.

A row that came back `unreachable` counts as done. Resume continues a run; re-reading the sites a
run could not reach is what `retry` is for, and doing it here would quietly change unreachable rows
every time a run was continued.

### 12.1 Run settings

Four settings govern how much reading a run does and how hard it leans on the hosts it reads.

`--max-pages N` is the base of the page budget per site, six by default, and the crawl spends
`N + 8` pages on an ordinary pass and `N + 16` with `--deep`, so the default reads fourteen pages
beyond the home page and fifteen in all. The figures elsewhere in this document, a median of
fifteen pages on a healthy run and four as the floor, are counts of pages read and are the numbers
to compare a run against; `N` is the dial that moves them. Escalation can still read past the
budget on a site about to be called `english_only` on a search too thin to support that claim,
because the budget is a cost control and the escalation is a correctness guard. Raising the budget
without raising `--timeout` buys nothing: the clock runs out first and the extra pages are never
read.

`--delay SECONDS` waits before every page fetch. It is taken immediately before the navigation, so
it paces requests and not batches; a delay applied per batch leaves the host seeing the same burst.
The pause is paid out of the site's own clock. A run with
`--delay 2` and the default `--timeout` will exhaust its clock on the pause and come back fast, thin
and wrong, so raise the timeout by roughly the delay times the page budget. The command line warns
when `--timeout` is under twenty times `--delay`.

`--ignore-robots` forces `--delay` to at least one second and says so if a smaller value was given.
Overriding a host's stated wish and hammering that host are separate acts, and a study can have a
defence for the first and none for the second.

`--min-median-pages N` and `--max-thin-share SHARE` move the run-level acceptance thresholds
described in section 12.2, four pages and 0.25 by default. Whatever they are set to, every result
records the thresholds it was judged against, in `min_median_pages` and `max_thin_share` on what
`capture_acceptance` returns, so a run that passed on a lowered gate carries the lowered gate with
it and a reader never has to reconstruct the command that produced it. The same two are reachable
from Python as `set_acceptance(min_median_pages, max_thin_share)`, and the pause as
`set_page_delay(seconds)`. Both are process-wide settings on the module that holds them rather than
arguments to a call, so they are imported from `langaccess.core` and not from the package root:

```python
from langaccess.core import set_acceptance, set_page_delay

set_page_delay(1.0)                                    # before every page fetch, for the process
was = set_acceptance(min_median_pages=2, max_thin_share=0.4)   # returns the pair it replaced
```

### 12.2 Calibration before a long run

The numbers below are this machine's numbers. Another machine's will differ: a setting that reads
properly on a fast connection with spare cores will exhaust its clock on a laptop, and the run comes
back sooner, looking finished, with `english_only` where a language was. **Do not copy a timeout out
of this document. Measure one on the machine that will do the run.** Twenty addresses cost a few
minutes and settle it.

`langaccess calibrate` performs that measurement and prints the command for the full run:

```
langaccess calibrate --from-file sites.txt -n 20      # the head of your own list
langaccess calibrate --from-file sites.txt --for 4000 # project the hours over a list this long
langaccess calibrate --demo                           # one address, before you have a list
langaccess calibrate --from-file sites.txt --json     # the whole calibration as data
```

It takes the sample from the head of the list it was given, for two reasons and the second is the
stronger: a calibration is worth something only if it meets the hosts, page weights and redirects
the real run will meet, and a set of demo addresses shipped inside a published tool is a handful of
sites fetched once per person who ever installs it, which is a load those owners never agreed to.
The one address the package will fetch without being given one is `--demo`, which reads the
author's own site.

It walks a ladder of settings and stops at the first rung `capture_acceptance` accepts. The rungs
are `--timeout 120 --concurrency 4`, then `--timeout 240 --concurrency 4`, then `--timeout 480
--concurrency 2`, and `--quick` shortens the ladder to two. The clock rises before anything else,
because an exhausted clock makes every other figure meaningless, and concurrency only ever comes
down: raising it makes each site slower on a machine that is already busy, so that step is left to
a person watching the result. `--attempts N` stops the walk after N rungs, `--delay SECONDS` probes
with the pause the real run will take so the projection includes it, and `--ignore-robots` probes
the addresses a host disallows and forces the same one-second delay floor the main command does.

**The rung it stops on is a floor.** The walk ends at the first setting the gate accepts, and the
gate is measured on the probe, twenty addresses unless `-n` says otherwise, so what the command
prints is the least setting that passed on twenty sites and not the setting a long run wants.
Confirm it on a hundred sites of the real list before committing days of clock to it.

Measured on an organization frame of 10,136 sites, `calibrate` proposed `--timeout 240` off 20
addresses, and two pilots over the same 100 sites of that frame read a median of 21.5 pages a site
at 240 against 31.0 at 480. The clock cut 51% of the crawls short at 240 against 10% at 480, and 3
of the 100 verdicts differed between the two settings, each of the three toward `true_multilingual`,
one from `english_only`, one from `unreachable` and one from `machine_translate`. The direction is
what makes the hundred-site confirmation worth its hours. Reading too little turns an organization
that serves other languages into an organization that appears not to, and in a directory built from
these verdicts that error takes out the listing a person searching in their own language was looking
for, while the opposite error leaves a wrong entry a reader can check. Raising `--concurrency` past
what the machine can do costs reading in the same direction: at 24 an earlier run read a median of
one page per site and reported its verdicts in the ordinary way.

Each rung prints on stderr as it is measured: seconds per site, how many addresses produced a
result, how many exhausted the clock, how many searches were sufficient against the ceiling in
force, and the median pages against the floor in force. What lands on stdout is the chosen setting,
the projection in hours over `--for` addresses or over the list, and the command to run. Probe
results are discarded, because what the command produces is a setting and not a result: the
addresses are read again by the real run, all of them under the one setting, so that no two sites
in a run were measured under different conditions. It exits 0 when a rung was accepted and 1 when
none was.

The same four figures can be read by hand off an ordinary run, which is what the command automates
and what a person who would rather see the working does instead.

```
head -20 sites.txt > calibrate.txt

langaccess --from-file calibrate.txt --json --output cal_a.jsonl \
    --shared-browser --concurrency 4 --timeout 180
```

Read four things off the run, in this order. The first three come from `read_quality` on each
result and the fourth from the clock.

1. **How many results exhausted the clock.** `clock_exhausted` true on most of the sites that were
   read means the timeout is too short for this machine and everything else is noise.
2. **How many searches were sufficient.** `sufficient` has to hold on more than 75% of the sites that
   produced a result, which is what the run-level gate checks.
3. **The median of `pages_read`**, over the sites that produced a result. Four is the floor.
4. **Seconds per site**, which is the wall clock divided by the number of addresses, and which
   projects the full run.

```python
import json
rows = [json.loads(l) for l in open('cal_a.jsonl', encoding='utf-8')]
read = [r for r in rows if (r['read_quality'].get('pages_read') or 0) > 0]
print('read           ', len(read), 'of', len(rows))
print('clock ran out  ', sum(1 for r in read if r['read_quality'].get('clock_exhausted')))
print('sufficient     ', sum(1 for r in read if r['read_quality'].get('sufficient')), 'of', len(read))
print('median pages   ', sorted(r['read_quality']['pages_read'] for r in read)[len(read) // 2])
```

If the run printed no warning about the result being too shallow to compare, the settings hold and
the run is ready to scale. If it printed one, change one thing and measure again:

| what the calibration showed | what to change |
|---|---|
| most results exhausted the clock | raise `--timeout`, and lower `--concurrency` if the machine is loaded |
| clock survived, median pages still under four | raise `--max-pages`, and raise `--timeout` with it |
| clock survived, gate accepted, too slow to finish | raise `--concurrency` a step at a time, re-measuring each step |
| `--delay` set and clocks exhausting | raise `--timeout` by about the delay times the page budget |

Raising `--concurrency` is the one change that can undo itself. More sites at once makes each site
slower on a machine that is already busy, so a step that looks free on paper can push results back
into `clock_exhausted`. Re-measure after every step rather than at the end.

Two configurations over the same twenty addresses answer this in about ten minutes, and that is
cheap against a run of a thousand: at 20 seconds a site a thousand addresses take about six hours.

### 12.3 Cost of the wrong setting

What these settings are for is visible in one measurement over twenty addresses. At `--timeout 45 --concurrency 8` the run finished in 53 seconds; every one of the
sixteen sites that produced a result had exhausted its clock, the median site had read one page,
escalation had never fired, and the run-level gate refused the result. At `--timeout 180
--concurrency 4` the same twenty took 470 seconds, the clock survived on fourteen of sixteen, the
median site read fifteen pages, and the gate accepted it. Six of the twenty verdicts differed
between the two, and all six moved the same way: `english_only` and `machine_translate` under the
short clock became `true_multilingual` under the long one, with Spanish, Korean and Chinese found on
sites the fast run had called English-only. The fast configuration was failing to read these sites.

`--from-file -` reads the list from standard input. `--output PATH` appends each JSON line to a file
as the result is produced, so a long run that is terminated retains everything it had finished; it
applies with `--json` and is ignored otherwise. Results print as soon as the results before them are
ready, in the order the addresses were given, and a site that raises an error is reported as
`unreachable` with the error in its `note` while the rest of the batch continues. A browser that
cannot be started is the one exception and is not treated as a site error; see the exit codes
below. The human-readable output prints the two axes, the per-language breakdown, the rules by
number and title, and the note.

`--shared-browser` runs the batch through `audit_many_async`, so the whole run holds one browser
instead of one per site, and the output still arrives in the order the addresses were given.

`--explain` replaces the summary with the working behind each verdict, described above. It applies
to a live address and, with `--rejudge`, to a stored capture, which is how a result is normally
debugged. With `--json` each site is one explanation object; the file `--output` names still
receives the result row, because that file is what a census reads and an explanation is for a
person.

`calibrate`, `diff`, `review`, `ingest`, `report`, `depth` and `retry` are the seven
subcommands. Five of them read files, reach no site and judge nothing; the two exceptions both reach
sites, `retry` exactly the ones a clean browser could not and `calibrate` a sample of the caller's
own list, whose results it throws away. `diff` prints the comparison described above, or the
same comparison as one JSON object with `--json`; `calibrate` is described in section 12.2 and
`review`, `ingest`, `report`, `depth`
and `retry` are described in the sections above and in sections 17 and 18. `depth` takes
a capture, since it reads pages.

## 13. Exit codes

| code | meaning |
|---|---|
| 0 | the run was performed. The code states nothing about the classes: a file of addresses that all returned `unreachable` because the sites refused the crawler exits 0, because that is a result |
| 1 | `calibrate` only: the ladder ran out with no rung the run-level gate accepted, so the command has no setting to recommend and says what the last attempt refused on |
| 2 | argparse could not parse the command line; `calibrate` was given no addresses at all; or `--from-file` was given a path that does not exist, a directory, or a file that is not UTF-8 text. The path and what is wrong with it are named in one sentence on stderr |
| 3 | no browser could be started, so nothing was read. The run stops where it stands, the addresses below that point produce no result at all, and the sentence stating what to install is printed once on stderr. `retry` answers with the same code when no browser is listening where `--cdp` points, and prints the three start commands |
| 4 | a stage produced nothing: a run file holding no records, a `review --fail-on-empty` that found nothing to review, an `ingest --fail-on-empty` whose sheet applied nothing, a `report` over a record that never held a result, a `report --all` in which no record did, a `retry` over a run file holding no records |
| 5 | a review sheet that cannot be applied to the run it was given with. Nothing was written and every fault is named on stderr |
| 6 | at least one of the strings given as an address is not one. Each is named on stderr with the reason, none of them was audited, and none appears in `--json` output or in a `--store` file. The addresses that are addresses were audited as usual, and the summary line carries both counts |
| 7 | a finished file could not replace its target, because another program held it open. The new run is complete beside the target under a temporary name, the message gives that path, and renaming it over the target finishes the job |
| 8 | the run's own store stopped taking writes (disk full, path revoked); the run stops where it stands, what was appended is safe, and no site after the failure gets a row |
| 9 | `--strict` only: the run finished and wrote everything it writes, and the reading it produced is one `capture_acceptance` refuses or one in which a site answered nothing on every browser driver it was offered. The reason is printed on stderr with the counts behind it. Without `--strict` the same run exits 0, because a run full of sites that refuse a crawler is a result |

Code 9 judges the run as it finished. With `--shared-browser` a batch reads its own transport
failures once more at the end of itself, described in section 4, and what `--strict` reads is the
state after that pass: a row the pass recovered is a reading and counts as one, and a row it did not
recover keeps the note the batch wrote, with `(retried on a fresh browser)` after it, and counts
against the run exactly as it did before. A timed-out row is read back on twice the run's clock,
capped at 600 seconds, so a run whose own bound was too short for a slow site can exit 0 where the
rows the batch first wrote would have exited 9; what changed is that the site was read. The same list run with `--no-retry-pass` can
therefore exit 9 where the default run exits 0, and the difference is the pass and not the
sites.

Code 3 outranks code 6 where both apply, since a missing browser means nothing was read at all.
Codes 3 and 8 outrank code 9 for the same reason: a run that stopped where it stood is a fraction
of a list rather than a degraded reading of the whole of one. Code 9 outranks code 6, and the line
naming the rejected strings is printed either way; code 6 says the output does not cover the list it
was given, and code 9 says the rows that are in the output cannot be compared with another run's,
which is the stronger statement about what the caller has in hand.

A run whose list holds both addresses and strings that are not addresses audits the first and
rejects the second, and ends with a line carrying the denominator, `langaccess audited 996 of the
1000 strings given; 4 were not addresses`. Read that line if you are counting `unreachable` rows: a
rejected string is not one, and it is in no output file.

On code 7 nothing is lost and nothing is half written.

`depth` answers 4 on a run file holding no records, as `review`, `ingest`, `report` and `retry` do,
and 0 on any run it could read, including one in which no record held pages. Its own output
carries the denominator: how many records were read, how many held pages, and how many held none,
with every record of the last kind named on its own line. A caller wiring it into a pipeline tests
`len(depth_run(path)['measured'])`.

## 14. Deep pass

A default pass follows what a site declares: `hreflang` tags, links whose path names a language, a
short list of guessed codes such as `/es`. Passing `deep=True` (or `--deep`) additionally requests
the language's own word as a path, where a second language often resides and to which nothing links
(`/korean` as well as `/ko`), reads more interior pages, and re-examines a page whose body returned
empty instead of recording it unreadable.

```python
audit('https://example.org', deep=True, timeout=240)
```

Interior pages are read in either mode, because a second language is usually absent from the home
page. Links whose path or visible text matches a keyword list (services, programs, contact, staff,
classes and similar) are followed first, and when nothing on the page matches any of them the crawl
falls back to the ordinary shallow same-site links, so a site whose own vocabulary this package
does not recognize still yields interior pages. A page opened that way is read one hop further,
taking up to sixteen interior links from it (`INTERIOR_LIMIT`). A cap of eight returned the same
eight links from every page, and the second hop the two-click rule depends on stopped
occurring.

`timeout` caps the whole audit of one site, in seconds. Any run over more than a handful of sites
should set it: a single site with many language controls, each of them clicked and returned from,
can otherwise run for most of an hour. Within the cap the crawl stops queueing pages before the
time expires and judges what it read, so a site that runs long returns as a result with a note and
not as `unreachable`.

## 15. Sitemap

The crawl also reads the site's own list of its pages. `/sitemap.xml`, `/sitemap_index.xml` and
`/wp-sitemap.xml` are tried in that order, the first one that answers is used, and up to forty of
its addresses join the queue behind the routes the page links to and the interior pages a visitor
would click. One organization keeps its Spanish at a path no keyword list holds and nothing on the
home page links to it by such a word, and it is the second entry in `sitemap.xml`. A sitemap index
points at further sitemaps, which are followed one level down and only when they are on the same
site, since a nested entry pointing at another host is an address this tool has no reason to fetch.
Documents are skipped by extension, and an address on another site is skipped by the same rule the
rest of the crawl applies.

## 16. Crawler conduct

The crawler reads public pages one at a time within a site, with a real browser, waiting for each
page to render before proceeding to the next. It is not built for high-volume crawling. Runs over
many sites should keep the concurrency low, below the level the package technically allows.

**robots.txt is read and obeyed by default.** A disallowed address is skipped and the audit
continues, because robots.txt is a statement about addresses and not about the site; only a
disallowed home page ends the audit, which then ends as a site that was not read and not as a site
with no language access. `respect_robots=False` and `--ignore-robots` are overrides for a
researcher who has the owner's permission.

Two divergences from [RFC 9309](https://www.rfc-editor.org/rfc/rfc9309.html) are deliberate and are
documented here instead of left in the source. A robots.txt that cannot be fetched, or that answers
with any status other than 200, is treated as imposing no restrictions; the RFC states that a crawler
MUST assume complete disallow when robots.txt is unreachable through a server or network error. The
strict rule converts a momentary server error into a site recorded as unreadable, and the
divergence trades that strictness for coverage. The cache holds one robots.txt per origin for the
life of the process with no expiry, whereas the RFC states a crawler SHOULD NOT use a cached copy
for more than 24 hours; a run over thousands of sites can exceed a day. A host's `Crawl-delay` is
not honoured. The parse limit is 512,000 bytes, which is the 500 kibibytes RFC 9309 section 2.5
requires, interpreted as binary kibibytes, and the fetch timeout is five seconds.

**The crawler sends a plain browser string and nothing else.** The user agent is an ordinary Chrome
string, sent by the rendered read, the plain fetch and the robots.txt fetch alike so that the two
ways a home page can be read are the same client to the server. Until 0.2.0 a contact comment was
appended to it, `(+mailto:...; langaccess research crawler)`, so that a site administrator reading a
server log had somewhere to write. It was removed on 2026-09-18 after a measurement: the 144
addresses a run over the gold frame had recorded unreachable were probed once under each string at
concurrency 2, counting an answer as HTTP 200 with a body over 200 characters, and 54 answered the
plain string against 41 that answered the string with the comment. Every address that answered the
comment answered the plain string too, and of the 13 that answered only the plain string, 7 refused
the comment with `net::ERR_HTTP2_PROTOCOL_ERROR`, 4 with HTTP 403 and 2 with a destroyed execution
context. A contact token cost 13 of 144 addresses, which is coverage a study pays for in
`unreachable` rows.

What is left in its place is the conduct that decides what gets fetched rather than a name in a log:
robots.txt is read and obeyed, one page is read at a time within a site, and the address in section
10 of [CONTRIBUTING.md](../CONTRIBUTING.md) is where a site owner asks this crawler to stay away.
The string is set rather than left to the browser's own default, because a headless Chromium's
default names itself `HeadlessChrome`, which is an identification of a different kind and one no
measurement here covers.

## 17. Language depth

A class answers whether a language is provided. How far that provision extends into the site is a
different question, and no class carries it: a site whose Spanish is one page of fifteen and a site
whose Spanish mirrors the whole tree both read `true_multilingual`. `depth_of` measures the
difference over the pages a stored capture already holds.

```python
from langaccess import depth_of, depth_run, read_store

for record in read_store('capture.jsonl.gz'):
    d = depth_of(record)
    if d is None:
        continue                   # this record kept no pages, so depth is unmeasurable for it
    d['pages_read']                # the denominator, the pages this capture holds
    d['pages_by_language']         # {'English': 15, 'Spanish': 3}
    d['share']                     # {'English': 1.0, 'Spanish': 0.2}, against pages_read
    d['against_english']           # {'Spanish': 0.2}, against the English page count

run = depth_run('capture.jsonl.gz')
run['records'], run['measured'], run['no_pages']
```

```
langaccess depth capture.jsonl.gz
langaccess depth capture.jsonl.gz --json
```

The input is a capture, which is what `--store` and `retry --keep-pages` wrote. A run written by
`--json --output` holds no page markup, so every record in one is returned in `no_pages` and nothing
is measured. `depth_of` answers `None` for such a record rather than a dict of zeros, because a
record without pages says nothing about depth and zeros would say the languages reach nothing, which
is a different statement. `depth_run` counts those records and names them instead of leaving them
out of the total, and the command line prints the three counts on one line before it prints any
per-site figure.

`against_english` is absent where no page carries English, so a consumer takes it with `.get`.
`languages_unrestricted` is present, and `True`, only where the record carried no `languages` field
at all.

The measure has three properties, each of them a decision. It is taken over the pages the capture
HOLDS, so it inherits every bound of the crawl that wrote it: the page budget, the routes that crawl
took, and the locale addresses it never fetched, which `read_quality['unread_locale_links']` counts.
A share of the read pages is not a share of the site, and the field names say which denominator is
meant. A page counts for a language when `languages_in` finds that language in the page's text, the
same reading the classes rest on, so depth and class cannot disagree about what a language is, and a
bilingual page counts once in each of its two languages. The count is restricted to the record's own
`languages`, plus English, which is rule 8 applied in this module and not a convenience: the audit
reads each page with the site's own name excluded, a raw re-read of stored pages has no way to know
that name, and without the restriction an organization whose name is written in its community's
language would show that language on every page of a site whose class says `english_only`.

No figure here is validated. No coder ever assigned a depth to a site, so there is no agreement
number to state and none is claimed; the classes carry the validated claim and this carries a
description beside it. It moves no result, writes no field on a record, and changes the shape of no
stored row.

**Which language a full vendor menu is driven to.** A `language_control` row says a control was
worked and names what came back, and on a site whose only switcher is a vendor menu of eighty
languages that row used to name whichever language the widget listed first. The menu is
alphabetical, the budget for worked controls on such a page is two, and the two were spent in page
order, so the row read as a claim about Amharic on seven of the seventeen sites of a development
round that were recovered this way. A switcher of `MENU_SIZE` labelled options or more is now driven
in a fixed order, Spanish, Chinese, Vietnamese, Korean, Arabic, Tagalog, Russian, French, Haitian
Creole and Portuguese, then whatever else the menu offers in the order the page presents it. A
label is resolved through the switcher vocabulary, so a menu written in its own languages is
ordered the same way, and a label the vocabulary cannot resolve whole keeps its place behind the
ones it can. A curated switcher, which is any switcher below that size, keeps page order throughout,
because the order of a list an organization wrote is a decision somebody made. Only which control is
worked first changes: the same evidence is recorded for whatever the click produces, no rule reads
the order, and a menu whose controls do nothing is the dead control it was. The order is
`MENU_PREFERENCE` and it was not measured live, so no figure here rests on it.

## 18. Retry of unreachable rows

`unreachable` is the instrument's weakest outcome on every scoring run, and the cause is mostly how
a site answers a strange browser: a bot wall that challenges a fresh headless browser seldom
challenges the browser a person actually uses, with its own profile, its own history and its own
network. `retry`
attaches to that browser over the DevTools protocol and re-reads exactly the rows a clean browser
could not read.

This is not the end-of-batch second reading of section 4, and the two answer different rows. The
end-of-batch pass is automatic, runs inside a shared-browser run, and reads only the rows whose
failure was a closed connection, a protocol error or a timeout, which are failures of the crawl.
`retry --your-browser` needs a person at the machine and is for the rows where the site answered and
refused, which is most of them.

Two things follow from the browser being a person's. The page is brought to the front before the
challenge poll, because a background tab is throttled by the browser it sits in and a challenge that
has to run JavaScript may not finish in one. And a challenge that clears NAVIGATES the page, which
destroys the execution context the poll is holding, so the error that says so is read as the
challenge clearing and the poll continues instead of the read failing. Measured in a government
session: of five walled sites that had refused a 420-second wait, four came back with a page under
those two lines.

**Start a separate Chrome profile with `--user-data-dir`, and leave it open.** One of these, on the
platform you are on:

```
Windows  chrome.exe --user-data-dir=%TEMP%\la-retry --remote-debugging-port=9222
macOS    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
             --user-data-dir=/tmp/la-retry --remote-debugging-port=9222
Linux    google-chrome --user-data-dir=/tmp/la-retry --remote-debugging-port=9222
```

A debugging port on your everyday profile lets any local process, and any page able to reach
127.0.0.1, read the cookies and sessions of every site you are signed in to, for as long as that
window is open. `--user-data-dir` gives the retry a profile of its own: it still carries a real
browser's fingerprint, which is the reason for borrowing a browser, and it carries none of
your logins. Nothing in the package can enforce this, which is why the instruction is repeated in
every place the command is written, including the command's own `--help`.

```
langaccess retry run.jsonl --your-browser -o retried.jsonl
langaccess retry run.jsonl --your-browser -o retried.jsonl --timeout 180 --keep-pages
langaccess retry run.jsonl --your-browser -o retried.jsonl --cdp http://localhost:9333
```

`--your-browser` is required and takes no value, so that borrowing the browser is always said out
loud on the command line. `-o/--output` is required and is where the updated run is written.
`--timeout` bounds each site and defaults to 120 seconds: without a deadline every clock guard
inside the audit is inert, and one page with a long language menu can hold a borrowed browser for
the better part of an hour. A site that exceeds it is left as the `unreachable` result it already
was, with the timeout in its note, and it is counted in `timed_out`. `--cdp` is where the browser is
listening, `http://localhost:9222` by default, which is also the value of `RETRY_DEFAULT_CDP`.
`--keep-pages` stores the pages of the retried reads, as `--store` does for an audit.

**What the retry refuses to open.** The addresses come out of a file, and a file arrives from a
collaborator, a shared drive, or an earlier run nobody has read since. Pointed at your own browser,
on your own network, an address is an instruction: `http://169.254.169.254/` is a cloud metadata
service and `http://192.168.1.1/admin` is a router, and `--keep-pages` would write whatever came
back into the output. So the retry admits `http` and `https` and no other scheme, ports 80 and 443
and no other port, and refuses a private, loopback, link-local or reserved host both by literal
address and by handing `block_private_hosts=True` to every read it performs. The scheme, the port
and the shape of the string are `auditable_url`'s answer and not a second copy of it, so this door
and the command line cannot disagree about what an address is; each of the eight non-web schemes
that module names is refused with a reason that says which scheme was typed, the seven tried by
hand against 0.1.0 among them. A refused address is
never opened, and it is counted rather than passed over: `report['refused']` holds one `(url,
reason)` pair for each, and the printed summary carries them under `refused, never opened` with the
reason beside each address. The clean-room audit makes the host guard optional, since a study may
deliberately audit an intranet; borrowing somebody's browser is not that case.

**What a retried record says about itself.** Only the records `needs_human` already queues as unread
are retried, and everything else in the run is carried through unchanged. Every retried record
carries `read_with_user_browser` set to `True`, because a capture taken with a person's own
fingerprint is a different observation from the clean-room one and a study has to be able to separate
the two, and it keeps the result it replaced beside it under `clean_room_verdict`, so nothing is
overwritten silently. A `site_id` already on the record is carried forward.

```python
import asyncio
from langaccess import retry_unreachable_async, retry_text, write_retry

records, report = asyncio.run(
    retry_unreachable_async('run.jsonl', timeout=180, output='retried.jsonl'))
write_retry(records, 'retried.jsonl')
print(retry_text(report, output='retried.jsonl'))
```

| key of `report` | what it holds |
|---|---|
| `records` | how many records the run held |
| `unread` | how many of them a clean browser could not read |
| `retried` | how many were opened through your browser |
| `now_read` | how many came back as something other than `unreachable` |
| `still_unreachable` | how many did not |
| `timed_out` | how many of those hit `--timeout`, counted inside `still_unreachable` |
| `refused` | `(url, reason)` for every address never opened |
| `moved` | `(url, verdict)` for every site that stopped being unreachable |

`retry_unreachable_async` takes the run as a path or as records already in hand, and a `browser`
argument that a test hands a fake to. The attached browser is never closed, because it is yours: the
Playwright connection is stopped and every context the audit opened is closed in its own `finally`.
When `output` is given, each retried record is appended to `<output>.part` as it lands, so a run
interrupted after an hour of browser reads keeps what it read; `write_retry` then writes the whole
file to a temporary beside the destination and renames it, and removes the crash copy. A browser
that is not listening raises `BrowserNotAttached`, which is `langaccess.retry.BrowserNotAttached`
and is not among the package's top-level exports; the command line answers it with exit code 3 and
prints the three start commands above.

## 19. Output fields

**Join on `requested_url`, not on `url`.** `url` is where the browser ended at, so a site that
redirects comes back under a name that is not in the list the run was given. `requested_url` is the
string the caller handed over.

One audited site is one JSON object. Its fields are `Result.to_dict()`,
which is what `--json`, `--json --output`, `--store` and `write_records` all write and what
`read_store` reads back. Every field below is present on every row the current build writes, whatever
the verdict, so a consumer selects columns without testing for their existence; the exception is
`pages`, which is written only when pages were asked for. Rows written by earlier builds can lack
the later fields, which is why `read_store` consumers take a value with `.get` when the build that
wrote the file is unknown.

| field | what it holds | always present |
|---|---|---|
| `url` | the address that was read, which is where the browser ended up | yes |
| `requested_url` | the address as it was given, before a scheme was added and before any redirect | yes on this build, `''` on a row written before it existed |
| `verdict` | `english_only`, `machine_translate`, `machine_translate_error`, `true_multilingual` or `unreachable` | yes |
| `languages` | the languages the classification counted, English included | yes, and empty on an unread site |
| `evidence` | the findings, each an `Evidence` record as a dict; the fields are in section 2 | yes, and empty where nothing was found |
| `machine_translation` | the translation vendor detected, if any, whether or not it moved the class | yes, and `''` where none was |
| `pages_read` | how many pages the reading rests on | yes |
| `note` | what happened, in words, where anything did: a timeout, an error, a crawl that stopped early. Section 19.1 reduces it to one name | yes, and `''` on an ordinary reading |
| `audited_at` | when the bytes were fetched, as `2026-07-29T18:04:11Z` | yes |
| `tool_version` | which release fetched them | yes |
| `tool_build` | the first twelve hex digits of the sha256 of the `core.py` that fetched them, from `build_id()` | yes on this build, `''` on a row written before it existed |
| `judged_at` | when the rules were applied to those bytes | yes |
| `judged_version` | which release applied them. Equal to `tool_version` on a live audit, different on a re-judge, which is how a re-judged row says so | yes |
| `judged_build` | the same twelve digits for the `core.py` that applied the rules. Equal to `tool_build` on a live audit; the pair that separates two builds carrying one version label | yes on this build, `''` on a row written before it existed |
| `authorship` | the site-level axis: `authored`, `server_plugin`, `client_widget`, `unknown_widget` or `none`, the strongest present over all the evidence | yes |
| `sufficiency` | the site-level axis, 0 to 4, the highest rung the counted evidence carries | yes |
| `by_language` | `{language: {'authorship': str, 'sufficiency': int}}`, the same two axes one language at a time. It names every language the reading FOUND, which is a wider set than `languages`, and the two are not a pair to join on: `languages` holds the languages the classification counted, so a language a widget produced is in `by_language` at `client_widget` and rung 0 and is not in `languages` at all. Over the 2,000-site gold frame, `languages` is a subset of `by_language` on all 1,993 rows and 127 rows hold a language `by_language` names and `languages` does not, Spanish and Arabic most often | yes, and empty where no language was found |
| `switcher_languages` | what the page's language MENU lists, which is a different question from what the site is written in. Counted by nothing | yes, and empty where no menu was found |
| `switcher_unresolved` | how many menu entries this package has no name for | yes, and 0 where there were none |
| `declared_off_site` | `{'alternates': int, 'languages': list}`: how many declared alternates resolve to another site, and which languages only an off-site alternate named | yes |
| `rules` | the numbered rules that decided this site, resolvable through `RULES` and `rule_titles` | yes |
| `unreproducible` | the steps a re-judge could not reproduce, by reason code; see `REJUDGE_LIMITS` | yes, and empty on a live audit |
| `read_quality` | what the search was worth, as the eleven keys below | yes |
| `pages` | `{url: html}`, every page the crawl read | only with `--store`, `keep_pages=True` or `to_dict(with_pages=True)` |

`read_quality` holds `pages_read`, `unread`, `unread_locale_links`, `shallow`, `budget_exhausted`,
`clock_exhausted`, `reads_timed_out`, `reads_failed`, `escalated`, `sufficient` and
`lid_absent`. `lid_absent` is whether the bundled language identifier failed to load in the
run's environment; a reading taken without it is not comparable with one taken with it, and
before this field that fact was a single warning on stderr. `sufficient` is
the one judgement among them and it answers one question, whether the search is enough to rest an
ABSENCE claim on, which is why `needs_human` reads it on an `english_only` verdict and on no other.
`read_quality_of(pages_read, ...)` is the function that assembles the block, exported so that a
consumer building the same record from counts of its own applies the package's rule for
`sufficient` instead of a second copy of it.

`sufficiency` in the table above answers a different question and belongs to no part of this block.
It is the rung the counted evidence reached, which is what a reader who does not read English can
do with the non-English text that was found, and it says nothing about how many pages were read or
how the crawl ended. A reading that counted no non-English text scores 0, and `unreachable` scores
0 by construction, since a site that was not read has neither axis. An `english_only` reading admits
rung 1 as well as 0, and the crawl writes no rung-1 finding, for the reason `sufficiency_of` gives.
The one shape where a class other than `true_multilingual` carries a high rung is rule 17: five
advertised locale mirrors with no vendor marker class the site `machine_translate` whatever rung
those mirrored pages earned. Over the 42 readings of `tests/fixtures/reading_expected.json`,
`sufficiency` is 0 on all 9 `english_only` readings, on all 5 `unreachable` ones and on 4 of the 5
`machine_translate` ones, and the fifth is that rule 17 case at rung 4. Judge a run by
`read_quality` and never by a distribution of `sufficiency`.

### 19.1 Failure kinds

`note` says why in words, which no two rows write the same way. `failure_kind` reduces the sentence
to one member of a closed vocabulary, so a table of unread sites can be grouped and counted:

```python
from langaccess import failure_kind, FAILURE_KINDS

failure_kind(r)          # 'robots_disallow'
FAILURE_KINDS            # the sixteen names, in the order the patterns are tested
```

The names are `no_dns`, `robots_disallow`, `directory_profile`, `parked_domain`, `bot_wall`,
`http_403`, `http_404`, `http_status`, `timeout`, `protocol_error`, `connection_closed`,
`empty_body`, `malformed_address`, `no_page_any_driver`, `unspecified_error` and `other`. A site
that WAS read answers `''`, which is not one of the sixteen, because a site with no failure to name
would otherwise put every row of a table into a failure family.

`protocol_error` and `connection_closed` are the two transport failures, and they became countable
in 0.2.0 because the note became able to say them. Until then a failed read wrote the exception's
CLASS and nothing else, so every network condition Playwright reports, which is one class for all of
them, arrived as the bare word `Error` and fell into `unspecified_error`. A note now names the
cause: `Error: net::ERR_HTTP2_PROTOCOL_ERROR (home read retried once)` where the row used to read
`Error (home read retried once)`, with the API call in front of the message and the address behind
it both dropped, since `Page.goto` is the same for every cause and the address is already in `url`.
`protocol_error` reads `net::ERR_HTTP2_PROTOCOL_ERROR` and `net::ERR_EMPTY_RESPONSE`, and
`connection_closed` reads `net::ERR_CONNECTION_CLOSED` and the `Connection closed` a dying
Playwright driver writes. Both mean that nothing was refused and nothing was served, which is why
neither is `bot_wall` and neither is `empty_body`, and both are in the end-of-batch second reading
described in section 4 along with `timeout`. Only codes this project has observed on its own frames
are mapped; `net::ERR_NAME_NOT_RESOLVED` in particular is NOT read as `no_dns`, because that name is
a claim about the organization and the only evidence accepted for it is the resolver answering
outright that the host does not exist.

Reading a distribution over these names across builds takes one caution. A run taken before 0.2.0
puts its transport failures in `unspecified_error`, so the two new names are 0 in any older store
and the older store's `unspecified_error` is larger by however many of them it held. Group the three
together when comparing an old run with a new one.

`parked_domain` sits beside `directory_profile` because the two say the same thing about the frame:
the address on file was never a website the organization runs. Rule 2 has written the note this
name reads since the release and the name did not exist, so the family a study most wants to set
aside was the one it could not count. Two tests reach it. The first reads the page, and
`PARKED_RX`, `PARKED_EXPIRED_RX` and `PARKED_SOON_RX` are what it reads with. The second reads
where the address LANDED: a domain that has gone to a registrar's marketplace forwards to that
marketplace's host, and `PARKED_HOST` holds those hosts, so the finding no longer depends on which
sentence the marketplace's page happens to carry. `PARKED_HOST` is sale and parking hosts only and
is matched on the bare host and its `www.` form, never on a suffix; no site builder is in it,
because `sites.google.com` and its kind are addresses real organizations run their websites on and
rule 1 says a builder address is included.

`no_dns` is the one name here that is a fact about the ORGANIZATION rather than about the crawl.
The resolver was asked and answered that the host does not exist: the domain has lapsed, and no
better client recovers it. Every other kind is a door this tool could not open. A study reporting
`unreachable` as a single figure is reporting two different things at once, and the size of the
difference is not small - over an organization census of 32,008 recorded websites, **27% of
everything that could not be read had no DNS record at all**, and nonprofit domains lapse where the
government domains of the sibling audit do not. Report the two apart.

It is asked only where the read has already failed and only where nothing in the note already
proves the host answered: an HTTP status, a bot wall or a robots.txt response each require a
connection, so the resolver cannot be asked to contradict them. A resolver that times out or errs
leaves the note alone, because not knowing whether a domain is gone is not the same as knowing that
it is.

`no_page_any_driver` is the one name that describes neither the site nor this crawler's conduct.
It is a site that came back with no page, faster than a read can be taken, on every browser driver
it was offered, and a site that refuses and a driver that has died look the same from there. The
note carries what the last attempt said, so nothing diagnostic is lost, and the family is tested
before the others so that those words do not classify the row: a run whose drivers died wrote rows
whose last attempt read `HTTP 403`, and counting them as `http_403` would report a property of the
site that nothing established. Set these rows aside before reading a distribution over the rest. The argument is a `Result`, a
stored record as a dict, or the note as a string, since those are what a caller has in hand at
different points. The first matching pattern wins, so a note naming two causes is filed under the
more specific one. The unreachable class in [LIMITATIONS.md](../LIMITATIONS.md) is what a distribution over
these names means for a study, and the short answer is that none of the sixteen is a property of
the site's language access.

Two commands add a key of their own, and both are absent from an ordinary row. `retry` writes
`read_with_user_browser` and `clean_room_verdict` on every record it re-read, described in section
18. `ingest` adds no field at all: a hand coding is appended to `evidence` with the mechanism
`hand_coding`, and `hand_coding(record)` is how it is read back.

## 20. Worked example

A study has 50 organization websites in a text file, one address per line, and wants a table of what
each site offers, a coding round over the results the package will not settle by itself, and a
statement of how much of the final table a person decided.

The audit, with one browser for the whole run, a cap per site, and both files: the row file that
becomes the table, and the capture that keeps every page read.

```
pip install langaccess
python -m playwright install chromium
langaccess --json --output run.jsonl --store capture.jsonl.gz \
    --shared-browser --concurrency 4 --timeout 180 --from-file orgs.txt
```

The table, the queue and the second-look sheet:

```python
import pandas as pd
from langaccess import contested, hand_coding, read_store, review_queue, write_review

rows = list(read_store('run.jsonl'))
assert rows, 'run.jsonl holds no records'
df = pd.DataFrame(rows)

df['non_english'] = df['languages'].apply(lambda xs: [x for x in xs if x != 'English'])
df['n_languages'] = df['non_english'].str.len()
counts = df['verdict'].value_counts().rename_axis('verdict').reset_index(name='sites')
counts['share'] = counts['sites'] / len(df)
counts.to_csv('verdicts.csv', index=False)
print(counts)
print(pd.crosstab(df['verdict'], df['authorship']))

q = review_queue(rows)
print('%d records, %d need a person, %d settled in a shape the coders split over'
      % (q['records'], q['unsettled'], q['contested']))
if q['rows']:
    write_review(q, 'review.csv')

df['contested'] = df.apply(lambda r: ', '.join(contested(r.to_dict())), axis=1)
df.loc[df['contested'] != '', ['url', 'verdict', 'languages', 'contested']].to_csv(
    'second_look.csv', index=False)
```

`review.csv` holds the results a coder must settle, and the contested rows after them, each row
carrying its reason. `second_look.csv` is the contested rows on their own, for a study that wants
them coded separately or reported as a stratum of its own. The `if q['rows']` guard is there because
`write_review` raises on an empty queue instead of writing a header and reporting success.

The coders fill `human_verdict`, `human_languages` and `note`, and the sheet goes back into the run:

```
langaccess ingest review.csv run.jsonl -o settled.jsonl
```

Then the share of the table a person decided, as a count:

```python
settled = list(read_store('settled.jsonl'))
coded = [r for r in settled if hand_coding(r)]
print('hand coded: %d of %d results, %.1f%%'
      % (len(coded), len(settled), 100.0 * len(coded) / len(settled)))
```

`settled.jsonl` is the file every later stage reads, and `run.jsonl` is left as the machine classification
it was, so the two can be compared with `langaccess diff run.jsonl settled.jsonl`. The capture is
what `langaccess depth capture.jsonl.gz` reads, and it is
also what a re-judge under a later build needs, so it is worth keeping beside the table it produced.

One field of every row is absent from the table above because it is a nested record rather
than a column: `lang_declared` records, for each page read, the language its markup declared
(`html`, its `parts`, and the text direction). It is present on every row.
