"""Strategy definitions for BNPL (Unsecured) — v1."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ProductLine:
    code: str
    name: str
    status: str
    active: bool


@dataclass(frozen=True)
class Equation:
    label: str
    formula: str
    description: str = ""


@dataclass(frozen=True)
class DriverNode:
    id: str
    name: str
    formula: str = ""
    children: list[DriverNode] = field(default_factory=list)


PRODUCT_LINES: list[ProductLine] = [
    ProductLine("bnpl-unsecure", "BNPL (Unsecured)", "Active — v1", True),
    ProductLine("bnpl-secure", "BNPL (Secured)", "Planned", False),
    ProductLine("c-credit", "C-Credit", "Planned", False),
]

NORTH_STAR = {
    "metric": "GMV",
    "full_name": "Gross Merchandise Value",
    "description": (
        "Total value of transactions completed using BNPL (unsecured) credit "
        "on the marketplace."
    ),
}

GROWTH_EQUATIONS: list[Equation] = [
    Equation(
        label="Growth Equation",
        formula="Growth GMV = # Buyers × # Transactions × # Sellers Listing Items × # Listed Items",
        description="Marketplace expansion framing for strategic growth.",
    ),
    Equation(
        label="GMV (Transaction lens)",
        formula="GMV = # Transactions × AOV",
        description="AOV = Average Order Value.",
    ),
    Equation(
        label="GMV (Buyer lens)",
        formula="GMV = # Buyers × OPB × AOV",
        description="OPB = Orders Per Buyer.",
    ),
]

INPUT_DRIVER_TREE = DriverNode(
    id="root",
    name="Input Drivers",
    children=[

        ##DriverNode(id="transactions", name="# Transactions = # purchase request × Purchase Conversion rate"),
        DriverNode(
            id="transaction",
            name="# Transaction",
            children=[
                DriverNode(
                    id="transaction",
                    name="Credit Spent",
                    children=[
                        DriverNode(id="spend_rate", name="Spend Rate"),
                        DriverNode(id="allocated_credit", name="Allocated credit"),
                    ],
                ),
                DriverNode(id="debit_spent", name="Debit Spent"),
            ],
        ),
        
        DriverNode(
            id="aov",
            name="# AOV",
            children=[
                DriverNode(
                    id="credit_spent",
                    name="Credit Spent",
                    children=[
                        DriverNode(id="spend_rate", name="Spend Rate"),
                        DriverNode(id="allocated_credit", name="Allocated credit"),
                    ],
                ),
                DriverNode(id="debit_spent", name="Debit Spent"),
            ],
        ),
        DriverNode(
            id="buyers",
            name="# Buyers",
            children=[
                DriverNode(
                    id="active",
                    name="# Active customer × Active customer purchase rate",
                ),
                DriverNode(id="dormant", name="# Dormant × Dormant purchase rate"),
                DriverNode(id="soft_churn", name="# Soft churn × Soft churn purchase rate"),
                DriverNode(id="unactivated", name="# Un-Activated × Un-Activated purchase rate"),
                DriverNode(
                    id="fresh",
                    name="# Fresh credit holder × Activation rate",
                    children=[
                        DriverNode(
                            id="allocation",
                            name="# Applicant × Allocation rate",
                        ),
                        DriverNode(
                            id="second_chance",
                            name="# Rejected × Second chance rate",
                        ),
                        DriverNode(
                            id="revenant",
                            name="# Dead credit holder × Holder revenant rate",
                        ),
                    ],
                ),
            ],
        ),
        DriverNode(id="opb", name="OPB (Orders Per Buyer)"),
    ],
)

BUYER_FORMULAS: list[Equation] = [
    Equation(
        label="Buyers decomposition",
        formula=(
            "# Buyers = (# Active × purchase rate) + (# Dormant × purchase rate) "
            "+ (# Soft churn × purchase rate) + (# Un-Activated × purchase rate) "
            "+ (# Fresh credit holder × Activation rate)"
        ),
    ),
    Equation(
        label="Fresh credit holder activation",
        formula=(
            "Fresh credit holder = "
            "(# Applicant × Allocation rate) + (# Rejected × Second chance rate) "
            "+ (# Dead credit holder × Holder revenant rate)"
        ),
    ),
    Equation(
        label="AOV decomposition",
        formula="AOV = Credit Spent + Debit Spent",
    ),
]

GLOSSARY: list[dict[str, str]] = [
    {"term": "GMV", "definition": "Gross Merchandise Value — total BNPL (unsecured) transaction value."},
    {"term": "AOV", "definition": "Average Order Value — GMV divided by number of transactions."},
    {"term": "OPB", "definition": "Orders Per Buyer — transactions divided by unique buyers."},
    {"term": "Spend Rate", "definition": "Share of allocated credit actually spent."},
    {"term": "Allocated credit", "definition": "Credit line assigned to the customer."},
    {"term": "Activation rate", "definition": "Share of fresh credit holders who complete a first purchase."},
    {"term": "Allocation rate", "definition": "Share of applicants who receive credit."},
    {"term": "Second chance rate", "definition": "Share of rejected applicants who convert via second-chance flow."},
    {"term": "Holder revenant rate", "definition": "Share of dead credit holders who return and transact."},
]
