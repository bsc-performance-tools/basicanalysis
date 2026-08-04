"""Top-level semantic report model."""

from dataclasses import dataclass, field
from typing import Iterator, List, Optional, Set

from .metadata import ReportMetadata
from .navigation import build_navigation
from .section import ReportSection


@dataclass
class Report:
    metadata: ReportMetadata
    sections: List[ReportSection] = field(default_factory=list)

    def add_section(self, section: ReportSection) -> None:
        if self.get_section(section.section_id) is not None:
            raise ValueError(
                "Duplicate section id {!r}.".format(section.section_id)
            )

        self.sections.append(section)
        self.sections.sort(
            key=lambda item: (item.order, item.section_id)
        )

    def iter_sections(self) -> Iterator[ReportSection]:
        for section in self.sections:
            yield from section.iter_sections()

    def get_section(self, section_id: str) -> Optional[ReportSection]:
        for section in self.iter_sections():
            if section.section_id == section_id:
                return section
        return None

    @property
    def navigation(self):
        return build_navigation(self.sections)

    def validate(self) -> None:
        seen_ids: Set[str] = set()
        active_objects: Set[int] = set()

        def visit(section: ReportSection) -> None:
            object_id = id(section)

            if object_id in active_objects:
                raise ValueError(
                    "Cycle detected at section {!r}.".format(
                        section.section_id
                    )
                )

            if not section.section_id.strip():
                raise ValueError(
                    "Every section requires a non-empty section_id."
                )

            if not section.title.strip():
                raise ValueError(
                    "Section {!r} requires a title.".format(
                        section.section_id
                    )
                )

            if section.section_id in seen_ids:
                raise ValueError(
                    "Duplicate section id {!r}.".format(
                        section.section_id
                    )
                )

            seen_ids.add(section.section_id)
            active_objects.add(object_id)

            for child in section.children:
                visit(child)

            active_objects.remove(object_id)

        for section in self.sections:
            visit(section)
