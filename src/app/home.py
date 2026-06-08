"""App-wide navigation and home page content."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AppPage:
    id: str
    title: str
    description: str
    url: str
    group: str
    icon: str


APP_PAGES: list[AppPage] = [
    AppPage(
        id="strategy",
        title="Strategy",
        description=(
            "North star metric (GMV), growth equations, and the input-driver tree "
            "for BNPL (Unsecured)."
        ),
        url="/strategy",
        group="Strategy & metrics",
        icon="◎",
    ),
    AppPage(
        id="glossary",
        title="Glossary",
        description="Definitions for GMV, AOV, OPB, buyer segments, and transition rates.",
        url="/glossary",
        group="Strategy & metrics",
        icon="≡",
    ),
    AppPage(
        id="lifecycle",
        title="Lifecycle",
        description=(
            "Interactive canvas: drag stages, draw arrows, edit the BNPL user "
            "lifecycle diagram. Saves to project files."
        ),
        url="/lifecycle",
        group="User lifecycle",
        icon="↗",
    ),
    AppPage(
        id="data-gathering",
        title="Data gathering",
        description=(
            "Enter stage user counts and transition rates. Updates numbers shown "
            "on the lifecycle canvas."
        ),
        url="/data-gathering",
        group="User lifecycle",
        icon="▤",
    ),
    AppPage(
        id="present",
        title="Lifecycle presentation",
        description="Read-only fullscreen view of the lifecycle diagram for sharing.",
        url="/lifecycle/present",
        group="User lifecycle",
        icon="▶",
    ),
]

APP_GROUPS: list[str] = ["Strategy & metrics", "User lifecycle"]

ACTIVE_PRODUCT = "BNPL (Unsecured)"
