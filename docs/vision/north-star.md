# North Star Metric

**Product:** BNPL (Unsecured)  
**Version:** 1

## North Star

**GMV (Gross Merchandise Value)** — total value of transactions completed using BNPL (unsecured) credit on the marketplace.

## Growth Equation

The top-level decomposition of growth:

```
Growth GMV = # Buyers × # Transactions × # Sellers Listing Items × # Listed Items
```

This equation expands the marketplace supply and demand sides alongside buyer activity. In v1, the primary operational breakdown uses the input-driver tree (see `docs/data-model/metrics/input-drivers.md`).

## Equivalent GMV Formulas

GMV can be calculated in two equivalent ways:

### Formula 1 — Transaction lens

```
GMV = # Transactions × AOV
```

Where **AOV** = Average Order Value.

### Formula 2 — Buyer lens

```
GMV = # Buyers × OPB × AOV
```

Where **OPB** = Orders Per Buyer (average number of orders per buying customer in the period).

## Strategic intent

All product initiatives for BNPL (Unsecured) should ultimately move one or more input drivers that roll up to GMV. Discovery opportunities and roadmap bets should be traceable to a driver in the metric tree.
