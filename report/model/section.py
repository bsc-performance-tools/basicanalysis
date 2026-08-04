"""Semantic report-section hierarchy."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterator, List, Optional


@dataclass
class ReportSection:
    section_id: str
    title: str
    navigation_label: Optional[str] = None
    description: str = ""
    section_type: str = "analysis"
    visible: bool = True
    order: int = 0
    children: List["ReportSection"] = field(default_factory=list)
    payload: Any = None

    def __post_init__(self) -> None:
        if not self.navigation_label:
            self.navigation_label = self.title

    def add_child(self, child: "ReportSection") -> None:
        if child is self:
            raise ValueError("A section cannot be its own child.")

        if any(
            existing.section_id == child.section_id
            for existing in self.children
        ):
            raise ValueError(
                "Duplicate child section id {!r} under {!r}.".format(
                    child.section_id,
                    self.section_id,
                )
            )

        self.children.append(child)
        self.children.sort(
            key=lambda section: (section.order, section.section_id)
        )

    def iter_sections(self) -> Iterator["ReportSection"]:
        yield self
        for child in self.children:
            yield from child.iter_sections()
