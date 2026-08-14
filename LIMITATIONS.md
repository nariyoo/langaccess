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

The figure is in-sample. One classification repair and one threshold were both fitted to this
sample, and a held-out draw is the check that has not been made. The cells differ enough that a
prevalence estimate corrected for classification error should use the per-class figures and never
the pooled one.

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
English only, happened on 3 of the 65. It is the one class that says nothing about the organization.

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
run-level acceptance gate accepts.

## 6. Language coverage

The inventories name 83 languages besides English: 20 non-English function-word lists, 12 writing
systems, 9 further languages resolved from the Cyrillic and Arabic scripts by the letters that
distinguish them, and 43 more names the bundled lid.176 identifier supplies. A language in none of
these cannot be reported at all, and the scoring
standard counts such a language against the tool instead of dropping it from the denominator, so the
figure above already carries that cost. An identifier answer is corroborated before it is reported,
because an identifier names a language for any text it is handed. Corroboration has a cost in the
other direction: a genuine page in one of these languages written without the words on the gate's
short list goes unreported, which is a missed language and not a false finding.

## 7. Widget detection and injected advertising

Who produced the non-English text is decided by fetching the page a second time with no JavaScript
executed and testing whether that text is present in what the server sent. That test can miss a
working translator whose fingerprint is not in the package, and such a site reads `english_only`
with `unknown_widget` beside it.

Injected advertising is a live error class and it is not defended against. Two sites of the sample
read `true_multilingual` off online-casino text injected into their pages, and both verdicts are
wrong. A consumer counting languages should check by hand any single unexplained European language
on a small municipal site.

## 8. Build identity

Every figure in this document was measured on langaccess 0.1.0. A figure measured on one build does
not transfer to another and results produced by different builds are not comparable, so a study
records which build produced its own numbers.
