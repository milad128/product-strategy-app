# Buyer Segments — BNPL (Unsecured)

Segments used to decompose **# Buyers** in the input-driver model.

## Transactional segments

Each segment contributes to total buyers as: `segment population × purchase rate`.

| Segment | Description |
|---------|-------------|
| **Active customer** | Customers with recent BNPL activity who remain engaged |
| **Dormant** | Customers with allocated credit but no recent purchase activity |
| **Soft churn** | Customers showing declining engagement or at risk of leaving |
| **Un-Activated** | Credit holders who have never completed a first purchase |

## Fresh credit holder

New or recently allocated customers. Decomposed by activation funnel:

```
Fresh credit holder × Activation rate =
    (Applicant × Allocation rate)
  + (Rejected × Second chance rate)
  + (Dead credit holder × Holder revenant rate)
```

| Sub-segment | Description |
|-------------|-------------|
| **Applicant** | New applicants who may receive credit allocation |
| **Rejected** | Applicants denied credit who may enter a second-chance path |
| **Dead credit holder** | Former holders whose credit lapsed or was closed, eligible for reactivation |

## Notes

- Segment definitions and thresholds (e.g. days since last purchase) should be finalized with data/analytics teams.
- v1 documents the structural model; operational cutoffs are TBD.
