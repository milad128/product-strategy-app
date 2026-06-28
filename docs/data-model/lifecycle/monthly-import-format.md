# Monthly lifecycle counts — import format

**Product:** BNPL (Unsecured) and future product codes  
**Last updated:** 2026-06-28  
**Version:** 1

Update this document whenever import rules change. The parser in `src/app/lifecycle/monthly_import.py` must match.

## File layout

Wide table in **Sheet1** (Excel) or first CSV sheet:

| | A | B | C | … |
|--|---|---|---|---|
| **Row 1** | *(empty)* | month code | month code | … |
| **Row 2+** | stage label | count | count | … |

- **Column A:** stage name (see mapping below)
- **Row 1, columns B+:** Jalali month as **`YYYYMM`** (e.g. `140312`, `140401`)
- **Values:** non-negative integers (stage user counts only)
- **Transition rates:** not in this file (separate format TBD)

## Stage label → app stage ID

Matching is case-insensitive; spaces and underscores are equivalent.

| File label | Stage ID |
|------------|----------|
| applicant user | `applicant` |
| abandoned user | `abandoned` |
| active_customer | `activeCustomer` |
| dead_credit_holder | `deadCreditHolder` |
| dead closed customer | `creditClosed` |
| dormant_customer | `dormantCustomer` |
| fresh_credit_holder | `freshCreditHolder` |
| rejected user | `rejected` |
| soft_churn_customer | `softChurned` |
| unactivated_credit_holder | `unActivatedCreditHolder` |

`Applicant user` is also accepted (normalized to `applicant_user`).

## Defaults and validation

- **`blackList`:** set to `0` if not present in the file
- **`applicant`:** may be empty (stored as `0`) until filled manually or in a later import
- **Invalid cells:** non-integer or negative values reject that cell’s import with an error
- **Re-import:** same `(product_code, month)` **overwrites** existing counts

## Supported formats

- `.xlsx` (Excel)
- `.csv` (same column layout)

## Storage

SQLite table `lifecycle_counts_monthly`:

- `product_code` + `month` (Jalali `YYYYMM`) → JSON counts per stage
