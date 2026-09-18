# Limitations

What a reader must know to interpret a langaccess result. The measurements behind these limits, and
the validation record in full, accompany the paper and are not part of this distribution.

## 1. Accuracy

Classification agreement with a gold dataset is 93.2%, Cohen's kappa 0.8962, on n = 1,861
United States websites. The sample was drawn in two blocks, immigrant-serving nonprofit
organizations and local government units, the second made up of municipalities, counties and a
small number of state sites. Each block was drawn with unequal probability of selection and the
design weights are kept, so the unweighted columns describe the sites in hand and the weighted
columns estimate the populations the blocks were drawn from.

| block | n | agreement | kappa | weighted agreement | weighted kappa |
|---|---|---|---|---|---|
| government | 926 | 94.3% [92.6, 95.6] | 0.9043 [0.8800, 0.9286] | 96.4% [94.2, 97.8] | 0.9324 [0.8983, 0.9611] |
| nonprofit | 935 | 92.1% [90.2, 93.7] | 0.8788 [0.8513, 0.9048] | 93.7% [90.8, 95.8] | 0.8877 [0.8423, 0.9294] |
| pooled | 1,861 | 93.2% [91.9, 94.2] | 0.8962 [0.8785, 0.9129] | 94.7% [92.8, 96.1] | 0.9124 [0.8836, 0.9378] |

The table covers three classes and only three, `english_only`, `machine_translate` and
`true_multilingual`. A row where either side returned `unreachable` or `machine_translate_error` is
counted beside the table and never inside it, since neither class describes a form of access.
`unreachable` came back from the instrument on 111 sites and from the coders on 65, the same 62
sites in both; `machine_translate_error` came back from the instrument on 25 and, by construction,
from the coders on none.

Table note. Of 2,000 sites drawn and settled, 65 left the denominator on the gold-dataset class,
every one of them `unreachable`, and 74 more left it on the instrument class (`unreachable` 49,
`machine_translate_error` 25), which leaves the 1,861 reported, 93.0% of the draw; the government
block runs 1,019 to 926 and the nonprofit block 981 to 935. Agreement intervals are Wilson. The
weighted ones are Wilson on Kish's effective sample size, 713.4 pooled, 437.5 government and 368.5
nonprofit, because weights this unequal would otherwise claim a precision the weighted estimate does
not have. Kappa intervals are 2,000 bootstrap resamples.

Per class, over all 2,000 rows where each side returned a class, which is the only denominator on
which the two set-aside classes have a figure at all:

| class | gold dataset | instrument | recall | precision |
|---|---|---|---|---|
| `english_only` | 738 | 742 | 0.946 [0.927, 0.960] | 0.941 [0.921, 0.956] |
| `machine_translate` | 728 | 632 | 0.838 [0.809, 0.863] | 0.965 [0.948, 0.977] |
| `true_multilingual` | 469 | 490 | 0.908 [0.879, 0.931] | 0.869 [0.837, 0.896] |
| `unreachable` | 65 | 111 | 0.954 [0.873, 0.984] | 0.559 [0.466, 0.647] |

The weakest substantive cell is the recall of `machine_translate`: the instrument returns it 632
times against the gold dataset's 728, and of the 118 it misses, 51 land in `true_multilingual`, 24 in
`unreachable`, 23 in `machine_translate_error` and 20 in `english_only`. A study counting sites that
offer only a translation widget should read that shortfall as the direction of its own error. The
precision of `unreachable` is lower still, and section 4 is about it.

The gold dataset was coded by language models. Three coded each site independently and blind, and a
fourth settled the sites they split over, so the 93.2% is agreement between one automated coding
and another and not agreement with a human judgement.

No figure here covers `machine_translate_error`. The class can arise only from a control that was
operated, and re-judging a stored capture never operates one, so the coders could not exercise the
observation behind it, and the 25 sites the instrument put there are counted beside the table.

What the class is not, measured. A live re-read of the same frame in September 2026 put 33
addresses in it, every one of them with the page budget spent and 20 to 136 pages left unread,
which raises the question whether the class records a control that failed or a clock that ran out
before the control could be worked properly. All 33 were re-operated on 2026-09-18, one site at a
time on a 300-second clock, against concurrency 8 and 240 seconds in the capture. 27 of the 33 came
back `machine_translate_error` again, and 26 of those 27 finished with `clock_exhausted` false, so
the class is not being written for a starved clock. The 6 that moved all moved to
`machine_translate` because the same control produced a language on the second reading, and in 4 of
the 6 the capture had clicked the alphabetically first entry of a vendor's menu, which is what the
menu preference of this release replaced. The control step also runs on the home page before the
interior crawl spends the page budget, so the unread pages on those rows are what happened after
the control was worked. One shape is left and is not counted: a scan the clock stops with a control
still unworked now says so in the note, and until a run holds enough of them to count, the class is
unchanged on it.

Two classification defects and one threshold were repaired against an earlier 1,000-site sample,
and all three were in the tree before this draw was scored. The dates are in the history of this
repository: the two repairs on 2026-08-07, the rule 17 threshold on 2026-08-10 in `fd4b844`, and
the build that scored the draw on 2026-08-11 in `351dd0f`. The held-out draw that would test the
threshold out of sample is captured and not yet coded. The cells differ enough that a prevalence
estimate corrected for classification error should use the per-class figures and never the pooled
one.

### 1.1 The 0.2.0 build, on a live re-read of the same frame

The table above belongs to 0.1.0 and to the frozen capture the coders read. 0.2.0 changes what is
read, and the frozen capture was not on the machine that built it, so 0.2.0 was measured on a live
re-read of the same frame: the 1,992 distinct addresses of the 2,000-site draw were captured once on
2026-09-17 and 2026-09-18 (the shared-browser batch runner, concurrency 8, a 240-second clock per
site, pages kept) by the tree the release was built from before its reading changed, build
`34c4bd0a980f`, and the stored pages were then judged twice, once by that build and once by 0.2.0 at
build `f84b423b85f1`. The released 0.2.0 is build `74a7f5df2b4b`, which differs from that one only
in the clock the end-of-batch retry pass gives a timed-out site, a step no re-judge runs; a re-judge
of the first 324 records of the capture under the released build returned the same 324 readings.
Both judgements are scored against the settled classes of August by the same script, so the
difference between the two rows of each block is the change in the rules and nothing else. The level
of either row carries the month between the pages the coders read and this capture, and a site whose
live reading disagrees with its settled class is first a question about the site.

| build | block | n | agreement | kappa |
|---|---|---|---|---|
| capture bytes | government | 901 | 93.0% [91.2%, 94.5%] | 0.8830 [0.8553, 0.9098] |
| capture bytes | nonprofit | 906 | 89.4% [87.2%, 91.2%] | 0.8379 [0.8047, 0.8663] |
| capture bytes | pooled | 1807 | 91.2% [89.8%, 92.4%] | 0.8662 [0.8462, 0.8864] |
| 0.2.0 | government | 901 | 92.9% [91.0%, 94.4%] | 0.8814 [0.8536, 0.9066] |
| 0.2.0 | nonprofit | 906 | 90.2% [88.1%, 91.9%] | 0.8499 [0.8178, 0.8781] |
| 0.2.0 | pooled | 1807 | 91.5% [90.2%, 92.7%] | 0.8712 [0.8520, 0.8903] |

Between the two judgements of the same pages, 37 sites moved. 19 changed class (7 from
`true_multilingual` to `machine_translate`, 5 from `machine_translate` to `true_multilingual`, 4
from `english_only` to `true_multilingual`, 3 from `true_multilingual` to `english_only`), 12 toward
the settled class, 6 away from it and 1 between two classes neither of which is the settled one. 18
changed only the languages named, on a class that did not move: a French reading that three words of
the old list had taken off English pages is gone from seven sites, Hindi is read as Nepali on Nepali
organizations, Punjabi, Nepali, Armenian, Turkish, Spanish or Portuguese notices are named on pages
that already read `true_multilingual`, and a quoted Russian testimonial and a quoted English tweet
are no longer counted. Of the six that moved away from the settled class, four rest on authored
Spanish or Portuguese the widened word lists admit and a coder could have missed (a city's Spanish
COVID notices, a Spanish news article, a Spanish assistance notice on a Google Translate site, a
Portuguese news item), one on six quoted member testimonials that the container rule now records
without counting, and one on a site-builder host whose locale pages hold the builder's own
placeholders and a Chinese skip link and nothing else. Of the 1,992 addresses, 144 came back
`unreachable` from the live read and are counted beside the table; the coders had settled 64
addresses `unreachable`, 60 of them among those 144; and 32 came back `machine_translate_error`.

A re-judge of 0.2.0 over the frozen capture the coders read is owed and belongs on the machine that
holds that capture. Until it is taken, the 93.2% above is the figure of record for 0.1.0 and 0.2.0
has none; what this section states is the movement between two builds on one set of pages, which is
the quantity a rule change is answerable for.

## 2. Scope

A result describes what an automated browser obtained on the date recorded. A language control
that works for a person and not for this client is recorded as one that does nothing, and the
direction of that error is toward `machine_translate_error` and `english_only`. Whether a switcher
works is a property of the site and the client together, so a result records what this client could
reach and not what every visitor can.

The package describes what a site published. A classification is not a determination of compliance
with any federal or state law, with any regulation made under one, or with any professional guidance
on interpretation, and the package holds no threshold at which a site becomes adequate. It does not
assess translation quality, so fluent authored Spanish and clumsy authored Spanish are classified
alike.

Whether a person can obtain help turns on the telephone line, the intake desk, the interpreter
roster and the hours at which someone answers, none of which a website states and none of which a
crawler reads. An organization whose site reads `english_only` may serve people in six languages by
telephone.

## 3. Absence claims

`english_only` is the only outcome that asserts an absence, and the assertion is
bounded by the routes that were read, never by the site as a whole. Every result carries
`read_quality`, which records the pages read, the stop reason, and whether the search was deep
enough for an absence claim. A site whose second language is behind a control this package could not
work reads `machine_translate_error` where a vendor was named and the control was operated, and
`english_only` otherwise, however many pages were read.

## 4. Unreachable

`unreachable` means the instrument did not read the site, and it is the weakest cell in the
validation table. Recall is 0.954 [0.873, 0.984] on the 65 sites the gold dataset settled there, so a
site the coders could not read is nearly always a site the instrument could not read either.
Precision is 0.559 [0.466, 0.647] on the 111 sites the instrument put there, so about half of what
it calls unreachable was read by a coder working the same address. Of the 49 sites in that gap, the
coders read 24 that offer only a translation widget, 20 in English alone and 5 in more than one
language. The error runs almost entirely one way. The instrument withdraws from sites that can be
read, and the opposite error, a site the coders could not read and the instrument reported as
English only, happened on 3 of the 65. It is the one class that says nothing about the organization,
with one exception: a domain that does not resolve, which `failure_kind` names `no_dns`. The
organization had a website and the domain lapsed, and no better client recovers it; over an
organization census of 32,008 recorded websites, 27% of everything that could not be read had no
DNS record at all. Report that share apart from the rest. Section 19.1 of USAGE.md holds the
sixteen names and says which of them are doors this tool could not open.

What the rest of that cell is made of was read directly, on 30 of the 111 addresses, in September
2026. Almost all of it is one thing: a host that answers HTTP 403 with a body too short to be a
page, 27 of the 30, of which 9 carry a body of exactly 49 characters and 18 a body of 196 to 216
characters, which is one bot manager's refusal in two sizes. Two more failed twice over with an
error and one domain does not resolve. Two repairs were built and measured against those addresses
at concurrency 1 with a 240-second bound: offering the home address to a second browser engine after
Chromium had failed at every variant, measured on all 30, and entering the site at `/about`,
`/contact` or the first addresses of its sitemap, measured on the 20 of the 30 that were still
unreachable and whose host resolves. **Neither recovered a single site**, and neither shipped. A refusal keyed
on an automated client refuses every client this package can drive, so what this cell mostly
measures is not a crawler that gave up too early. The route that reads these sites is `retry
--your-browser`, which re-reads the unread rows through a browser a person is running, and section
18 of USAGE.md is how that is done. What it recovers on these addresses was not measured, since that
run needs a person at the machine.

**That cell was re-read with the 0.2.0 build, and it is much smaller than it was.** The frame is the
144 addresses a run over the gold frame recorded `unreachable` on 2026-09-08. Every one of them was
read again on 2026-09-18 at `--shared-browser --concurrency 2 --timeout 240`, a run of 113 minutes,
and **94 of the 144 now rest on at least one page**. By the class of the note the first run wrote:
58 of the 59 refused with HTTP 403, 11 of the 24 whose note was the bare word `Error`, 11 of the 12
that timed out, all 10 whose shared browser died under them, 3 of the 13 in the remaining shapes,
and 1 of the 26 refused by robots.txt. Of the 34 addresses that first run failed on infrastructure
grounds rather than on the site's own answer, 21 now read at least one page. Of the 94, 41 read
`english_only`, 29 `machine_translate`, 22 `true_multilingual` and 2 `machine_translate_error`.

**The robots.txt refusals are unchanged, and unchanged by policy.** 25 of the 26 are still refused,
and the one that is not is a host whose own robots.txt changed in the ten days between the runs. A
host that asks a crawler to stay away is obeyed, and no figure moves that.

What the re-read cannot do is apportion the 94. Three changes are in it, a user agent with no
contact comment, a failed read that names its cause, and a batch that reads its own transport
failures again, and so are ten days of the web moving; the probe behind the first of those found 41
of the 144 answering the old string on the same day, so a large part of this is time and not code.
It is a reach figure, and nothing in it was scored against a settled class. The two reach repairs
refused in the CHANGELOG, a second browser engine and other entry pages, were measured on 30 of
these 144 under the tagged User-Agent string, so their refusal is a statement about that string as
much as about the engine, and neither was re-measured after the tag was dropped. One thing it does
separate: **the end-of-batch second reading was offered 12 rows and recovered none of them**. All 12
were timeouts, and no row in this run failed with a closed connection or a protocol error at all, so
the family that pass was built for did not arise at concurrency 2 and remains untested here.

Report its count as its own row in every table, and report the denominator of every rate as the
sites that were read. Do not fold `unreachable` into `english_only`. The two are opposite kinds of
statement: `english_only` is an absence claim the instrument makes after reading pages, and
`unreachable` is the instrument saying it read none. A study that merges them reports an
English-only rate biased upward by however many of its sites were behind a bot wall.

## 5. Run settings

The settings a run is given decide what it reads, and a run given too little clock does not fail
loudly. It finishes early, returns a full set of verdicts, and the verdicts are wrong in one
direction, out of `true_multilingual` and towards `english_only` and `machine_translate` on
languages the site had written itself. `langaccess calibrate` measures a machine before a long run:
it walks a ladder of settings over a sample of the caller's own list and stops at the first one the
run-level acceptance gate accepts. That sample is twenty addresses by default, so the setting it
prints is the least one twenty sites accepted and a hundred sites of the real list can refuse it;
section 12.2 of USAGE.md has the pilot that did.

What records how much was read is `read_quality`, in the share of crawls whose clock ran out and the
median pages read, and never `sufficiency`, which scores the non-English text a reading found and is
0 wherever it found none.

## 6. Language coverage

The inventories name 89 languages besides English: 21 non-English function-word lists, 18 writing
systems, 13 further languages resolved inside a script whose entry carries another name, by the
letters or the grammatical words that distinguish them, and 37 more names the bundled lid.176
identifier supplies. The four parts are disjoint in that order, so they sum to the total and no
language is counted twice; Persian, Urdu, Kurdish and Pashto are the names this matters for, since
each is both resolved inside the Arabic script and has a code in the identifier's table. The counts
are computed from the tables in `langaccess.core` rather than kept by hand, and one of them is a
correction: the figures here read 83 before 2026-09-17, where the same decomposition over the same
code gave 84.

A language in none of the inventories cannot be reported at all, and the scoring
standard counts such a language against the tool instead of dropping it from the denominator, so the
figure above already carries that cost. Seven such languages are named here, because a reader is
better served by a list than by the statement that a list exists. Igbo, S'gaw Karen, Marshallese,
Chuukese, Samoan, Tongan and Hawaiian have no function-word list here, no script of their own that
another language does not already claim, and no label in lid.176, which was checked by reading all
176 of the model's labels rather than by assuming. A page written in any of them is unreportable,
and for S'gaw Karen the failure has a particular shape worth knowing: it is written in the Myanmar
range, so the script test sees a run and the Burmese particle list correctly declines it, and the
page comes back carrying no language rather than carrying Burmese. None of the seven is reachable
by the arithmetic that widened twelve of the word lists in this release, because that screen needs a
frequency list of the language and there is none for any of them; each would need a corpus built by
hand against real prose in the way the Hmong entry records, which is two documents from unrelated
publishers and a count of every candidate word against eighteen neighbouring languages.

Nine of the Latin-script lists are in the same position for the same reason, and it is worth
separating from the sentence above, because these languages ARE reported and it is only their word
lists that could not be widened. Haitian Creole, Tagalog, Somali, Albanian, Bosnian, Croatian,
Serbian, Hmong and Oromo have no frequency list in the package the screen draws candidates from, so
their lists stand where they stood. Ukrainian is a tenth case and a different one: a frequency list
exists for it and it is Cyrillic, while the entry here is a romanization, so no candidate that list
offers can be compared with what this one holds. Hmong and Oromo were each built word by word
against real prose, in August and September, and carry that record at their own entries; the other
eight have had no such pass, and a reader should take their lists to be thinner than the twelve that
were screened rather than equally measured.

Two further shapes are not unreportable and are not what they look like either. Dari is read and
reported as Persian, because the two share the script and most of the grammatical vocabulary and
lid.176 has no separate label; a Dari page is therefore named, under a name its publishers may not
use. Bosnian, Croatian and Serbian in Latin script are reported under one joint label, which is a
decision recorded at the word list rather than a limit of it.

A reading taken from a script rests on two tests and the second is codebook rule 9. A run of the
script has to be long enough, and it has to carry one of that script's grammatical particles, which
is what stands in for the verb rule 9 asks a bilingual line for. One particle is enough, so the
weight of the rule falls on which particle, and a coordinating conjunction is excluded from
carrying it alone: `X and Y` is how a verbless bilingual subtitle is written, and an events page
repeats that shape down the page. One organization in the gold frame is read `english_only` for
exactly this reason, in agreement with its coders, where its event subtitles would otherwise have
made it multilingual. The cost runs the other way too, and it is the honest half: a page whose only
non-English text is a list of names or titles joined by a conjunction is a page this instrument
reports nothing for, even where a reader of that language would recognise the language at a glance.

An identifier answer is corroborated before it is reported,
because an identifier names a language for any text it is handed. Corroboration has a cost in the
other direction: a genuine page in one of these languages written without the words on the gate's
short list goes unreported, which is a missed language and not a false finding.

Measured on 152 paragraphs of invented organizational prose in 76 languages, two per language, one
of about 600 characters and one of about 250 in the shape of a help notice: the corroboration word
lists are almost never what refuses such a page. What refuses it is the length regime in front of
them. The identifier is asked only about a block of at least 140 characters and will not name a
language found in fewer than two such blocks, and a block is one sentence, so a language is reported
only where two sentences each run past 140 characters. Ordinary organizational prose has sentences
of 90 to 130 characters, and a help notice is one sentence. Twelve languages that lid.176 names
correctly on both paragraphs go unreported for that reason alone: Dutch, Finnish, Estonian, Czech,
Slovak, Slovenian, Swahili, Malay, Yoruba, Uzbek, Pashto and Sorani Kurdish. The regime is not
changed here, because the measurement behind it was taken on real captures and says that relaxing
it admits injected advertising and menu rows; what is stated is which gate the cost falls on, so
that it is not mistaken for a gap in the word lists.

The same accounting from the other side, on real organizations rather than on invented prose. A
reviewer read 98 organizations this instrument had published as `english_only`, 72 of them carried
an address a capture could reach, and 19 of those 72 still read `english_only` after the reader
changes of this release. Read one at a time, they divide as follows. Two were a Spanish paragraph
the word list was three words short of, and both are read after the Spanish list was widened, which
leaves 17. Eight are a name, a tagline, a menu label, a liturgical term or a motto placed beside its
own English twin, which codebook rule 6 is right to leave outside every class, and the reviewer
agreed with the instrument on all eight. Three carry no non-English text at all on the flagged
block, which was an English footer of an address, opening hours and a telephone number that the
screening identifier behind the reviewer's list had named Esperanto. On one of the three the
identifier still answers Esperanto at 0.99 and the floor on how much of a block is written the way
an address and a telephone number are written, added in this release, refuses it at 0.320 against a
ceiling of 0.29; on the other two the identifier returns Esperanto on no block of the capture at
all. `english_only` was right about all three. Three are text the organization
did not write, two of them injected online advertising and one a community member's testimonial
printed under its own English version, which section 7 is about. Two are text the reading never
saw. On one the reviewer's passage is not in the September capture at all: the crawl read the whole
of that site's navigation, six pages of six, and where the reviewer had quoted a paragraph of
Spanish appointment instructions the capture carries a notice of 118 characters, so the site
changed between the two readings. On the other the whole navigation is a link element carrying a
client-side route and no address, so the crawl had nothing to follow and read one page, and the
French mission statement the reviewer quoted is one level below the front door. One is a reader gap
that is still open, and it is the length regime again rather than the word lists: a Spanish
invitation of 132 characters carrying two words of the list, where the paragraph standard asks for
four distinct words inside one window.

## 7. Widget detection and injected advertising

Who produced the non-English text is decided by fetching the page a second time with no JavaScript
executed and testing whether that text is present in what the server sent. That test can miss a
working translator whose fingerprint is not in the package, and such a site reads `english_only`
with `unknown_widget` beside it.

A site builder's own interface is a third kind of text this page carries and this organization did
not write, and it is defended against by container the way a feed embed is. A locale page of a Wix
site renders the builder's strings in that locale whether or not the organization has published
anything, so a blog with no posts announced in Spanish that it had none and was read as Spanish;
`PLACEHOLDER_HOOK`, `PLACEHOLDER_TESTID` and the five sentences of `PLACEHOLDER_TEXT` take the empty
state and the members dialog out before the text is read. Measured over 936 stored pages, three lose
a language and none gains one, all three on one organization, whose own Spanish pages still read
Spanish. The container test is language-independent; the sentence list carries only the Spanish
wording a stored page attests, because no other locale of that site was captured, and the English
and French forms the builder also ships are absent rather than guessed.

Injected advertising is a live error class and it is not defended against. Two sites of the sample
read `true_multilingual` off online-casino text injected into their pages, and both verdicts are
wrong. A consumer counting languages should check by hand any single unexplained European language
on a small municipal site.

### 7.1 A plugin that is either a translator or a translation

`CMS_RX` names the content managers that run a second language the organization itself wrote, and a
match sets `authorship` to `server_plugin` rather than to `client_widget`. **TranslatePress belongs
to that list only in its manual mode.** Attach DeepL or Google to it and it mirrors the whole site
automatically, and in that mode the server document is the vendor's output - the reasoning that
places Transposh and Linguise on the machine-translation side of the same file.

The two modes cannot be told apart from the page. Measured over 252 organizations running the plugin,
out of 30,022 whose markup was stored (the second commonest marker in `CMS_RX`, after `wpml`):

| signal | automatic sites | sites with no localised URLs |
|---|---|---|
| `trp_machine_translated` | 0 of 5 | 0 of 16 |
| a DeepL or Google reference | 3 of 5 | 2 of 16 |
| the language switcher | 5 of 5 | 16 of 16 |
| `hreflang` naming a non-English language | 5 of 5 | 14 of 16 |

The one signal that does separate them is the site's own sitemap: an automatic mirror lists one
localised URL per English URL, so the localised share sits at or above half. Five sampled sites read
83%, 67%, 50%, 50% and 50%; twenty-six read 0%. That is a fetch the crawl does not make, and nine of
forty sampled sites served no readable sitemap at all, so it is not a rule this package applies.

**What this means for a count.** `server_plugin` is not `authored`, and rule 11 requires content
beside the marker, so no verdict rests on the marker alone. But a study counting `true_multilingual`
on sites running TranslatePress should expect some share of them to be automatic mirrors, and the
share is not known. Demoting all of them would move organizations that did write their own second
language into `machine_translate`, which is the more expensive error in an audit whose subject is
language access.

### 7.2 Feed embeds and testimonials

An embedded social feed is somebody else's writing rendered inside this page, and the container the
vendor's script renders into is what says so. `FEED_SEL` and `_without_feeds` remove those
containers before the text is read, on the browser side and on the stored bytes, so a Spanish
Instagram caption or a Facebook post shared from a news outlet is no longer read as the
organization publishing in that language. The list is by vendor and never by content: nothing in it
looks at what the feed says or which language it is in.

A testimonial is the same question and the answer is now partial. The codebook already places one:
`SUFF_TOKEN` is defined as "a name, slogan, nav label, menu item, a title in a list, a quoted
testimonial", which puts a quoted testimonial at rung 1, below `SUFFICIENCY_COUNTS`, and therefore
outside every class. Until 2026-09-18 no code found one, so a testimonial was read at the rung its
length and coverage earned it, which is 2 or 3, and it decided a class.

**The refusal of 2026-09-17 was about the TEXT and it stands.** A feed embed is a container a named
vendor owns, documents and puts one class on. The words of a testimonial are not distinguishable
from the organization's own words by reading them: a quotation mark with an attribution beneath it
is also how an organization quotes its own director, and a block printed beside its own English
version is also exactly what a bilingual notice is, which codebook rule 9 counts.

**What is read instead is the container, and this is what it reaches.** `TESTIMONIAL_WORDS` holds
`testimonial`, `testimonials`, `review` and `reviews`, matched against the `class` and the `id` of
an element as a word with a non-letter on each side of it, and `QUOTED_TAGS` adds the elements that
are a quotation in HTML rather than in a theme's convention: `<blockquote>`, `<q>`, and a
`<figure>` that carries the `<cite>` naming who is quoted. `QUOTED_NEVER` refuses `<html>`,
`<head>`, `<body>` and `<main>`, because a class on the document is a setting for the document.
One pattern feeds both readers, the browser's `_lift_testimonials` and the stored bytes'
`_without_testimonials`, so a live audit and a re-judge of its own capture count the same words.

**A testimonial is not removed; it is moved off the count and onto the record.** Where a quoted
container carries a non-English reading, `testimonial_evidence` writes an evidence row whose
mechanism is `testimonial`, at rung 1, naming the language and the address, with no authorship,
because that axis says who produced the text and has no value for a visitor's words. The mechanism
is outside `OWN_MECHANISMS`, so `counted_evidence` cannot count it and no class, language list or
site-level axis can move on it; a language seen only in a quotation is in `by_language` at rung 0
and not in `languages`. A reader checking a site by hand sees the block the reading declined to
use, which a removed feed does not leave behind.

**What it moved, measured on two stored captures.** On the 72 reviewer-read sites of the
2026-09-17 capture, 4 sites carry a `testimonial` row and 3 sites move: one leaves
`true_multilingual` for `english_only` on a Spanish client testimonial the reviewer had refuted,
one keeps `english_only` and now says on the record why, and one drops a rung on the
`<blockquote>` shape described below. On the gold capture of the same frame, 1,997 records over
1,986 distinct addresses, re-judged under this tree and under the tree before it: 39 records carry
a row, 5 differ on the verdict or the language list, none differs on a site-level axis alone, and
one more gains a `by_language` row. `true_multilingual` falls from 475 to 472 and
`machine_translate` rises from 630 to 633, with `english_only`, `machine_translate_error` and
`unreachable` unchanged at 716, 32 and 144. Four of the five are a participant or client
testimonial, on two sites in a bare `<blockquote>`, on one inside an Elementor testimonial widget,
and on one a Russian quotation on a page of five testimonials whose Ukrainian help pages keep the
class. The fifth drops ENGLISH from its language list, because the only English that site's
verdict counted was a quoted tweet inside `blockquote.twitter-tweet`, the Twitter form of the
embed `FEED_BLOCKQUOTE_CLASS` already names for Instagram.

**Two of those five leave no trace, and the reason is the paragraph standard.** A row is written
only where the container carries a reading, and a reading is what codebook rule 6 says it is. One
business association publishes six member quotations of 30 to 188 characters; none of them clears
rule 6 standing alone, the Spanish the page carried as one stream is gone from the count, and no
row records that anything was there. English is never recorded on any mechanism, so the site that
lost English from its list has no row either. A consumer reading `evidence` for testimonials will
therefore find the long ones and not the short ones, and the honest reading of a site that moved
with no row is that the container took text the page had been counting.

**What the container does not reach.** A testimonial published as ordinary paragraphs with no
container of its own is still counted, and that is the commonest of the three refuted shapes rather
than an edge of it: of the three organizations the reviewer refuted for reading a class off a
client testimonial, the one whose capture this was measured on publishes its Spanish testimonial
as three sibling HTML blocks of a site builder's layout, each a curly-quoted paragraph followed by
a line holding a first name after a dash, with no class anywhere that says what the block is.
Nothing in that markup distinguishes it from a paragraph of the organization's own prose, and the
2026-09-17 refusal covers it exactly. A section
wrapper is the boundary from the other side: where an organization writes its own paragraph INSIDE
a testimonial container, that paragraph leaves the counted stream with the quotations, and the
reading is lost. The one organization of the reviewed sample with that shape does not have it in
its markup, so the case is argued rather than measured.

**Three proposed words are not in the list and one is refused on a measurement.**
`what-people-say`, `client-stories` and `success-stories` were proposed and no page of either
capture carries any of the three. `quote` and `quotes` were proposed and are refused: over the
first 200 sites of the gold capture the commonest matching token of the whole tally is Enfold's
`modern-quote`, 65 occurrences, which the theme writes onto a HEADING element, and the second is
`icon-quote-right`, an SVG symbol with no text; on the 72-site capture the same word takes five
containers off one organization's pages and every one of them holds that organization's own
Persian announcement, which would have gone on the record as five testimonials it did not write.
A class holding `quote` names a style more often than it names somebody's words, and the tags
above already catch a quotation the markup marks as one, `wp-block-quote` among them.

**The `<blockquote>` tag reaches a shape the argument above does not settle.** An organization that
prints its mission statement as a blockquote, in English and then in its second language, has
written both lines itself, and codebook rule 9 counts exactly that shape. One site of the 72 does
this in Lithuanian: its Lithuanian rung falls from 3 to 2 because 163 bytes of its own writing left
the counted stream, and the class holds only because the same language is on the page outside the
quotation. A site whose only second language is a bilingual mission statement inside a blockquote
would now read `english_only`, which would be wrong. Nothing in the two captures is that site, and
the shape is named here because it is the cost the tag buys its testimonials with.

**What this means for a count.** A site whose only non-English text is a testimonial inside a
container the theme names reads `english_only` and carries the quotation in `evidence`. A site that
publishes the same testimonial as bare paragraphs still reads `true_multilingual`. Neither the
1,992-site gold agreement figures of section 1 nor the 89.2% of 0.1.0 is recomputed for this
change: the gold standard is not coded in this tree, and what is measured is movement rather than
accuracy. A study that needs the distinction reads `evidence` for the `testimonial` rows, and for
the sites without a container it still decides by hand.

### 7.3 Five refused defences against injected advertising

Two sites of the original sample read `true_multilingual` off online-casino text injected into
their pages, and the class is still not defended against. Five defences have now been measured and
each is refused, recorded here so the work is not repeated.

Three were measured in August 2026. A gambling vocabulary misses Finnish compounds and flags a real
charity casino night, and in an audit of immigrant service organizations the vocabulary is part of
the subject matter, since addiction services write about gambling. Hidden-text detection answers
nothing, because the injected text is visible. A foreign commercial domain inside the same block
does not fire, because the domain sits in another block.

Two more were measured on 2026-09-17, on a live capture of the 72 addresses of a sample of 98
organizations a reviewer had read by hand, judged over 48 site-and-language findings.

**A language whose every block also carries three or more outbound anchors to hosts unrelated to
the site fires on nothing at all: 0 of 48.** It does not fire on the one injected case the capture
still holds, because the injection is a blog post on the site's own domain and the anchor beside
the German casino text is that post's own permalink. A test that never fires cannot be calibrated
and cannot be scored.

**A language on exactly one page, named by neither the declaration nor the switcher, fires on 23 of
48, and 18 of the 23 are organizations the reviewer confirmed do publish in that language.** One
page in one language with no switcher is the ordinary shape of a small organization's second
language, not the shape of an injection. It would also not repair the case it was written for: the
Russian on that site is on two pages, so the site would still read `true_multilingual` after the
German was struck. Eighteen real readings lost, no verdict corrected.

**The frame for this question has also shrunk, which is itself a finding.** Of the three injected
sites in that sample, two no longer carry the text and read `english_only` on the September capture:
the injections were cleaned up between the two readings. One remains. A rule written against one
site is a rule fitted to one site, and this package does not ship those.

What holds for a consumer is what LIMITATIONS said before: check by hand any single unexplained
European language on a site whose subject has nothing to do with it. The evidence record carries
the quoted block, which is what makes that check possible in a table rather than in a browser.

## 8. Build identity

The figures in this document were not all measured on one build. The agreement table in section 1
was measured on langaccess 0.1.0, on a frozen capture of the gold frame. The measurements in
sections 4, 6, 7.2 and 7.3 were taken in September 2026, during the development of 0.2.0 and on the
tree that became it. A figure measured on one build does not transfer to another and results
produced by different builds are not comparable, so a study records which build produced its own
numbers.

Every result names its own build, so the record no longer depends on the label. `tool_build` is the
first twelve hex digits of the sha256 of `core.py` as installed when the bytes were fetched, and
`judged_build` is the same twelve digits for the `core.py` that applied the rules; the two are equal
on a live audit and differ on a re-judge, and `build_id()` returns the value on its own for a
document that has to quote it. Two results are comparable on a class only where their `judged_build`
agree. The file is the one that holds the rules, the constants and the crawl, so it moves when a
reading can move.

A version label did not distinguish builds on its own, which is why these fields exist. One
organization census holds 334 records whose reading came from one `core.py` while the package label
beside it read 0.1.0 for another, and nothing on the row said so; the two files were separated months
later by hashing them by hand. The value is `''` on a record written before the fields existed, so an
empty `tool_build` beside a filled `judged_build` is an earlier store judged by this code.
