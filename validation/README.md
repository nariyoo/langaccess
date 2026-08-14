# Validation table

`gold2000_deidentified.csv` is the de-identified scoring table behind the accuracy figures in
`LIMITATIONS.md` and in the paper: one row per site of the 2,000-site two-block draw, with every
identifying field removed. Organization names, addresses and web addresses are withheld because the
gold dataset scores named organizations and local governments; the full table is available from the
author on reasonable request.

## Columns

| column | meaning |
|---|---|
| `row_id` | an arbitrary row label carrying no identity |
| `block` | `government` or `nonprofit`, the reporting block |
| `stratum` | the sampling stratum the site was drawn from |
| `pool_size` | the number of frame units in that stratum |
| `take_merged` | the number the sample drew from it |
| `weight_merged` | the design weight, `pool_size / take_merged` |
| `coderA_class`, `coderB_class`, `coderC_class` | the three blind coders' classes |
| `settled_class` | the gold-dataset class after adjudication of splits |
| `instrument_class` | the class langaccess 0.1.0 returned |

## Reproduction

Restrict both class columns to `english_only`, `machine_translate` and `true_multilingual`;
agreement is the share of the remaining 1,861 rows where they match (93.2%, Cohen's kappa 0.8962),
and the weighted figures apply `weight_merged` to the same rows (94.7%, 0.9124). `unreachable` and
`machine_translate_error` are reported beside the figure as counts, never inside it. The full
interval methods are stated beneath the table in `LIMITATIONS.md`.
