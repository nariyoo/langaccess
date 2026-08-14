# Contribution guide

A change to a regex, a word list or a threshold changes what a website is recorded as providing, and
papers cite a version number as a statement about how their numbers were produced. Most of the
rules below are about saying what a change did.

## 1. Tests

```
python -m pip install -e ".[test]"
pytest -q
```

In continuous integration that command reports **1443 passed, 5 skipped, 15
deselected**. No browser is installed and none is needed, because the fifteen deselected tests are
the only ones that open one. They are marked `live` and `pyproject.toml` deselects them by default
with `addopts = -m "not live"`. Of the five skips, three are in the boundary gate and are the
alternatives a word boundary is not about, and two are vendor patterns that begin on a
non-word character. A count in this file that no longer matches is a bug in this file; run the
suite and correct it.

To run the fifteen that do open a browser and reach the network:

```
python -m playwright install chromium
pytest -m live
```

A `-m` given on the command line replaces the default, so that run collects the fifteen and deselects
the rest. Do not add a live test to the default suite. A test that depends on somebody else's
website fails on their redesign.

The suite is organised by what it guards. `tests/test_core.py` holds the detector's known-answer
cases and the derivation table. `tests/test_rules.py` is the rule registry gate.
`tests/test_widget_fixtures.py` is the corpus-backed vendor cases. `tests/test_engineering.py` holds
the constant freeze gate and everything that is not the detector. `tests/test_reading_freeze.py` is
the reading freeze gate. `tests/test_pattern_gates.py` holds the two gates over the wall,
placeholder and widget patterns, described below. `tests/test_cli.py`, `tests/test_rejudge.py` and
`tests/test_web.py` cover the command line, the stored-capture re-judge and the FastAPI service.

Continuous integration runs `pytest -v` on Python 3.10 through 3.13 on every push and every pull
request (`.github/workflows/test.yml`).

## 2. Freeze fingerprint

`tests/test_engineering.py` builds a single sha256 over every constant a result depends on.
The list of them is DERIVED: `_module_constants` reads every name `core.py` assigns
at module level off the module's own source, and the fingerprint covers all of them except the ten
in `_FINGERPRINT_EXCLUDE`, each of which carries a written reason. A constant added to `core.py` is
therefore covered by default and moves the hash by itself, and leaving one out is an edit to the
exclusion ledger that shows up in the diff.
`test_the_frozen_constants_have_not_moved` asserts the hash against the `FREEZE` literal beside it.
`test_every_constant_is_accounted_for` and the registry test beside it, which refuses to let the
gate exclude a constant `RULES` names as the place a rule is applied, make the derivation a gate
rather than a convenience.

The gate exists because a whole accuracy pass once moved results across a run without anything
noticing, because the vendor markers, the coverage cut and the two crawl limits were not in it and
each of them decides a verdict. A hand-written list goes on doing that: four constants once entered
the code without entering the list and were found only after results had moved. Deriving the list
covered 160 constants where the hand list had 102.

`LANGACCESS_FREEZE_DUMP=<path>` writes the exact listing the hash was taken over, so two
revisions can be diffed to see which constant moved.

## 3. Reading freeze

A constant fingerprint cannot see a change that moves a result without moving a constant, and there
has been one: scoping the unique-word test to the window the function words fired in, instead of to
the whole page, moved results on seven sites and changed no value anywhere. It changed WHERE
`PARA_WINDOW` is applied.

`tests/test_reading_freeze.py` audits a corpus of synthetic sites through the fake browser and freezes the
whole result of each one, evidence and quotes included, against `tests/fixtures/reading_expected.json`
and a single `READINGS` digest. The pages are invented, because the census capture is not
distributable; `test_every_address_in_the_corpus_is_a_reserved_one` keeps it that way.

**A move in `READINGS` is always a move in what the instrument reports**, unlike `FREEZE`, which can
move because the gate widened. Treat it as steps 2 to 4 below demand. Re-record by running the suite
once with `LANGACCESS_RECORD_READINGS=1` and reading the diff of the expected file first. What the
gate cannot catch is written at the top of that file; read it before trusting the gate.

**A constant may change; the change has to be recorded.** When the hash moves:

1. Re-record `FREEZE` with the new value.
2. Write, in the commit message, which constants moved and what the change does to a result. Name
   the shape of site whose class can change, not just the constant.
3. **Say which measured figure no longer applies.** A figure is measured against one set of these
   constants. If the change can move a class on any site, then every agreement number, kappa and
   published table produced under the old value describes an instrument that no longer exists, and
   the commit message has to say so in those words. LIMITATIONS.md binds the published figure to the
   released bytes for the same reason.
4. Note the version the change ships in. A rule change takes a MAJOR
   version, a change to crawler reach that alters which pages are read takes at least a MINOR
   version and invalidates any figure measured before it, and PATCH is reserved for changes that
   cannot move a verdict.

An instrument freeze can also be in force for a validation run, in which case the run's manifest
records the sha256 of the source files themselves and the answer is simply no: the change waits for
the release after the run.

## 4. Wall and placeholder patterns

`tests/test_pattern_gates.py` holds two gates neither of the freezes above can be. Both are about
the family of patterns that decides, on the home read, that a site was not read at all.

**The boundary gate** compares every alternative of the eight patterns with the same alternative
behind a left word boundary, over `tests/fixtures/pattern_boundary.json`. An alternative that
matches inside a longer word either gets the boundary or gets an entry in `INTENDED_DIFFERENCE` with
the reason and a `covered` flag saying whether the pattern as a whole would lose a match, which the
gate checks. Two defects of that shape have shipped: `parked (?:courtesy of|by)` matching inside
`sparked by`, and the bare word `captcha` matching inside `reCAPTCHA`. Adding an alternative to any
of the eight patterns also requires a string in that corpus which the alternative matches, or
`test_every_alternative_is_exercised_by_the_corpus` fails and names it.

**The unreachable ward** freezes what `is_wall` and `is_parked` catch over 31 synthetic pages,
against a `WARD` digest, and reports the two direction counts when it fires. A pattern change is
allowed and it is a decision:

1. Count both directions over real sites. The 31 synthetic pages this gate holds are its corpus and
   never the measurement. A capture store written with `langaccess --store` serves: judge it once
   under the current patterns and once under the changed ones, and count how many pages become
   unreachable and how many become readable.
2. Write both numbers into the freeze note, and keep them as two numbers. A net figure hides the
   toward-unreachable count, which is the one that costs an organization its language access on
   the record, and it is the number to lead with.
3. Re-record with `LANGACCESS_RECORD_WARD=1`, read the diff of `tests/fixtures/ward_expected.json`,
   and paste the digest the gate reports.

## 5. Classification rules and registry

The rules are not this package's own. They were written for the Immigrant Support Map
organization census, and the human and model coders code from the same set. The release
numbering runs 1 to 17 in pipeline order, assigned 2026-08-09 before the first release; the
development numbering, under which the validation records were written, has a one-for-one
correspondence table in the freeze note in `tests/test_engineering.py`.
`RULES` in `langaccess/core.py` holds one record per rule, with its number, a short
title, the rule's heading verbatim, and `enforced_in`, the names of the objects in that
module where the rule is applied.

**A rule must have a record, and a record must resolve.** `tests/test_rules.py` enforces
four things and each of them has caught something:

- the registry covers exactly the numbers 1 to 17, so a rule 18 nobody wrote and a rule 7
  somebody deleted both fail;
- every rule either names at least one enforcement site or says in words why it cannot be in code;
- every name in `enforced_in` resolves to a real object in the module;
- every record carries the rule's heading verbatim, so a retitling or a renumbering shows up as a
  test failure rather than as silent drift.

Every record names at least one enforcement site. In the development numbering, rule 12 was the
one that named nothing, a scoring rule about how a disagreement between a coder and the instrument is counted, and it came
off the published set on 2026-08-08 with the validation table it scored. Development rule 5 came
off in the same pass, for the same reason: it excluded an address against a list of nonprofit directories
built for one census frame. Its behaviour stayed and its number went, so a directory profile
still answers unreachable with a note and claims no rule. Those two development numbers stay retired in that
numbering, because stored development-era records carry them; the release numbering reuses both
digits for different rules. A future rule that no code can
apply takes the old treatment: `not_in_code` with the reason written out, never an empty
`enforced_in` on its own.

Before the registry existed, a mechanical count over `src/`, under the development numbering,
found ten of the eighteen rules then defined named
somewhere in the source and eight named nowhere, several of which were in fact implemented. Nothing
could tell an unimplemented rule from an unnamed one, and the names rule was written and had no
implementation at all for weeks on that account.

## 6. New widget fingerprint

A vendor pattern says that a site is running translation machinery, and under rule 14 a
widget that never renders is still a widget, so a pattern that fires on the wrong bytes can move a
site to `machine_translate` on a JSON key. Two patterns did that before the corpus pass:
`smartling` as a bare token matched 18 organizations and 15 of them carried it only as a key inside a
shop platform's `data-localized-strings` JSON, and `crowdin` matched the English word
"overcrowding" on all 131 of its static matches.

**A new or widened pattern needs corpus evidence, not a vendor list.** What a proposal has to carry:

1. **A count of distinct organizations the pattern adds**, measured over a real capture, not a count
   of pages and not a hit count. The reference measurement is a July 2026 capture of 45,100 distinct
   organizations' websites. A pattern that adds zero
   organizations over a pattern already present does not ship, and the measured zero belongs in the
   comment so that nobody adds it again off a vendor list.
2. **A count of what it names wrongly.** Take the matches and read the context. If the pattern
   matches an English word, a product key, or an ordinary hyperlink to a translation service, say how
   many of the matches are of that kind. A bare "Translate this site" link to translate.google.com is
   carried by 80 organizations in the capture and is not an installed widget.
3. **The right list.** `MT_NAME` names a machine translation. `AMBIGUOUS_NAME` says only that
   translation machinery is present, where Wix Multilingual and UserWay belong, because neither
   marker establishes that a machine wrote the second language. `CLIENT_SIDE_WIDGET` is narrower
   still and means the vendor's output cannot be in the server response, which the authorship
   axis rests on; a vendor that can be deployed as a server-side proxy does not go on it, and Weglot
   is the measured case, with 197 of its 405 rendered installs appearing in no server document at
   all. `WIDGET_KIND` records what each marker establishes, because detecting a vendor and
   classifying it are different claims.
4. **A fixture case, from the capture.** `tests/fixtures/widget_fixtures.json` holds 24 cases, each
   with an `id`, an opaque `case` handle, the `url`, the `why` in prose, the `languages` found per
   document and channel, and `matches`, which carries the exact matched bytes with 100 characters of
   context either side, per document and page. A case names the organization by its address and by
   nothing else: no EIN, no registry number and no contact details, because a result is published
   with an address and a quote and those are the only two identifiers this package puts in front of
   anybody. `document` says what the bytes are rather than where they were kept, `server` or
   `rendered`, since which of the two a marker is in is the whole argument of several cases. The
   file is copied into the package on purpose, so the test does not depend on the capture being
   reachable. Add the expected answer to the
   `EXPECTED` table in `tests/test_widget_fixtures.py`, including the cases where the honest
   expected answer is that nothing is named.
5. The freeze note above, because every one of these lists is in the fingerprint.

## 7. Misclassified sites

A misclassified site is the most useful thing to report, and the one report that needs nothing but
an address.

Open an issue with the address and, optionally, what you expected to find or where you saw the
second language. Issues are not checked automatically; run the check locally, which takes one
command.

A report is much stronger with three things: the address, what a visitor who does not read English
can actually do on that site and where, and the verdict this package gave. Run
`langaccess --json <url>` and paste the output, or `langaccess --store run.jsonl <url>` and keep the
capture, which holds every page that was read. The evidence records name the URL and the quoted words
behind each finding, and `rules` names by number the rules that decided it. `rule_titles(r.rules)`
turns those numbers into the titles `RULES` carries, so a report can quote the rule it disagrees
with rather than an impression of the site.

Two answers are common and are not defects. A site behind a bot wall comes back `unreachable`, which
is not a claim that it has no language access. And a widget's output is deliberately not counted as
the organization's own provision; if you think a second language was written by the organization and
this tool called it machine translation, say where the text is and whether it survives with
JavaScript disabled, since the verdict turns on that test.

`LIMITATIONS.md` states what the instrument cannot do, and carries the measurement behind those
statements in summary. Check it first: a report of something already known
to be outside the reading is still useful, but it is a different report from a defect.

## 8. Pull requests

Keep them small and separable. A change to the judgement and a change to packaging do not belong in
one commit, because one of them invalidates a figure and the other cannot.

Every pull request should say which of these it is, since the review is different for each: a change
that cannot move any verdict, a change to crawler reach that alters which pages are read, or a change
to a coding rule. The second and third require the freeze note described above. The third also requires the written rules themselves to have been changed first, since this
package applies rules it does not define.

The house style is plain prose in comments, with the reason a thing is the way it is and the site or
the measurement that settled it. Most of the constants in this package were set by a named case, and
the comment naming that case stops the next person from undoing it.

## 9. Support

For a question about a result, use the issue form above. For anything else, open an issue on
`https://github.com/nariyoo/langaccess`, or write to Nari Yoo at `nariyoo@umich.edu`.

If you are a site owner and you want this crawler to stay off your site, robots.txt is read and
obeyed by default, and an email to the address above is enough.
