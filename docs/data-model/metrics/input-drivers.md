# Input Drivers — BNPL (Unsecured)

Metric tree decomposing GMV into actionable input drivers.

## Tree structure

```
Input Drivers
├── # Transactions
├── # AOV
│   ├── Credit Spent
│   │   ├── Spend Rate
│   │   └── Allocated credit
│   └── Debit Spent
├── # Buyers
│   ├── Active customer × purchase rate
│   ├── Dormant × purchase rate
│   ├── Soft churn × purchase rate
│   ├── Un-Activated × purchase rate
│   └── Fresh credit holder × Activation rate
│       ├── Applicant × Allocation rate
│       ├── Rejected × Second chance rate
│       └── Dead credit holder × Holder revenant rate
└── OPB (Orders Per Buyer)
```

## Formulas

### Buyers decomposition

```
buyers_count =
    active_customers × active_purchase_rate
  + dormant_customers × dormant_purchase_rate
  + soft_churn_customers × soft_churn_purchase_rate
  + unactivated_customers × unactivated_purchase_rate
  + fresh_credit_holders × activation_rate
```

### Fresh credit holder activation

```
fresh_credit_holders × activation_rate =
    applicants × allocation_rate
  + rejected × second_chance_rate
  + dead_credit_holders × holder_revenant_rate
```

### AOV decomposition

```
aov = credit_spent + debit_spent
```

```
credit_spent = f(spend_rate, allocated_credit)
```

> Exact functional form of `credit_spent` to be specified with analytics (e.g. spend rate applied to allocated credit per transaction).

## Driver registry

| Driver ID | Name | Parent | Formula / notes |
|-----------|------|--------|-----------------|
| `transactions` | # Transactions | GMV | `gmv / aov` |
| `aov` | # AOV | GMV | `gmv / transactions` |
| `credit_spent` | Credit Spent | AOV | Component of AOV |
| `spend_rate` | Spend Rate | Credit Spent | Input driver |
| `allocated_credit` | Allocated credit | Credit Spent | Input driver |
| `debit_spent` | Debit Spent | AOV | Component of AOV |
| `buyers` | # Buyers | GMV | `gmv / (opb × aov)` |
| `opb` | OPB | GMV | `transactions / buyers` |
| `active_purchase` | Active × purchase rate | Buyers | Segment driver |
| `dormant_purchase` | Dormant × purchase rate | Buyers | Segment driver |
| `soft_churn_purchase` | Soft churn × purchase rate | Buyers | Segment driver |
| `unactivated_purchase` | Un-Activated × purchase rate | Buyers | Segment driver |
| `fresh_activation` | Fresh credit holder × activation rate | Buyers | Funnel driver |
| `allocation` | Applicant × allocation rate | Fresh activation | Funnel sub-driver |
| `second_chance` | Rejected × second chance rate | Fresh activation | Funnel sub-driver |
| `revenant` | Dead credit holder × revenant rate | Fresh activation | Funnel sub-driver |
