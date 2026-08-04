"""Navigation derived from the report section hierarchy."""

from dataclasses import dataclass
from typing import List, Tuple

from .section import ReportSection


@dataclass(frozen=True)
class NavigationItem:
    section_id: str
    label: str
    children: Tuple["NavigationItem", ...] = ()


def _from_section(section: ReportSection) -> NavigationItem:
    children = [child for child in section.children if child.visible]
    children.sort(key=lambda child: (child.order, child.section_id))

    return NavigationItem(
        section_id=section.section_id,
        label=section.navigation_label or section.title,
        children=tuple(_from_section(child) for child in children),
    )


def build_navigation(
    sections: List[ReportSection],
) -> Tuple[NavigationItem, ...]:
    visible = [section for section in sections if section.visible]
    visible.sort(key=lambda section: (section.order, section.section_id))
    return tuple(_from_section(section) for section in visible)
