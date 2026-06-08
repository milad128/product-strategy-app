# Growth Equation — Data Model

**Product:** `bnpl-unsecure`  
**North star:** `gmv`

## Entity: ProductMetricTree

Root metric with two calculation paths.

### Path A — Transactions × AOV

```
gmv = transactions_count × aov
```

### Path B — Buyers × OPB × AOV

```
gmv = buyers_count × opb × aov
```

### Identity

```
transactions_count = buyers_count × opb
```

Therefore Path A and Path B are equivalent when definitions are consistent.

## Entity: GrowthExpansion

Top-level marketplace growth decomposition:

```
growth_gmv = buyers_count × transactions_count × sellers_listing_count × listed_items_count
```

> **Note:** This is a strategic expansion framing. Operational monitoring in v1 emphasizes the input-driver tree under GMV.

## Relationships

```
gmv
├── transactions_count
├── aov
│   ├── credit_spent
│   │   ├── spend_rate
│   │   └── allocated_credit
│   └── debit_spent
├── buyers_count
│   └── (see input-drivers.md)
└── opb
```

## Future products

| Product code | Status |
|--------------|--------|
| `bnpl-unsecure` | Defined |
| `bnpl-secure` | Not defined |
| `c-credit` | Not defined |
