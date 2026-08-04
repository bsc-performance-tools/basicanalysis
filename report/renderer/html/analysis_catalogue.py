"""Build the HTML analysis-view catalogue used by comparison panels."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Optional, Tuple

from ...model import ReportSection
from ...sections import (
    ResourceAnalysisData,
    RuntimeAnalysisData,
    ScalabilityAnalysisData,
)


@dataclass(frozen=True)
class AnalysisCatalogueView:
    """One analysis view available to a comparison panel."""

    view_id: str
    label: str
    title: str
    group: str
    description: str
    body_html: str


@dataclass(frozen=True)
class AnalysisCatalogue:
    """Ordered collection of available comparison views."""

    views: Tuple[AnalysisCatalogueView, ...]

    def get_view(
        self,
        view_id: str,
    ) -> Optional[AnalysisCatalogueView]:
        """Return one view by semantic identifier."""

        for view in self.views:
            if view.view_id == view_id:
                return view

        return None

    def has_view(
        self,
        view_id: str,
    ) -> bool:
        """Return whether the catalogue contains a view."""

        return self.get_view(
            view_id
        ) is not None

    def views_by_group(
        self,
        group: str,
    ) -> Tuple[AnalysisCatalogueView, ...]:
        """Return all views belonging to one analytical group."""

        return tuple(
            view
            for view in self.views
            if view.group == group
        )


def _validate_section(
    section: ReportSection,
    expected_id: str,
    expected_type: str,
) -> None:
    """Validate a semantic report section."""

    if section.section_id != expected_id:
        raise ValueError(
            "Expected section {!r}, got {!r}.".format(
                expected_id,
                section.section_id,
            )
        )

    if section.section_type != expected_type:
        raise ValueError(
            "Section {!r} has type {!r}; expected {!r}.".format(
                section.section_id,
                section.section_type,
                expected_type,
            )
        )


def build_analysis_catalogue(
    overview_section: ReportSection,
    runtime_section: ReportSection,
    resource_section: Optional[ReportSection],
    scalability_section: Optional[ReportSection],
    rendered_html: Mapping[str, str],
) -> AnalysisCatalogue:
    """Build the ordered catalogue of available analysis views.

    Parameters
    ----------
    overview_section
        Semantic Overview section.

    runtime_section
        Semantic Runtime Analysis section.

    resource_section
        Optional Resource Analysis section for accelerator executions.

    scalability_section
        Optional Scalability Analysis section. It is absent for single-trace
        reports and when no valid scalability metric is available.

    rendered_html
        HTML bodies indexed by semantic view identifier.
    """

    _validate_section(
        section=overview_section,
        expected_id="overview",
        expected_type="overview",
    )

    _validate_section(
        section=runtime_section,
        expected_id="runtime-analysis",
        expected_type="runtime-analysis",
    )

    runtime_data = runtime_section.payload

    if not isinstance(
        runtime_data,
        RuntimeAnalysisData,
    ):
        raise TypeError(
            "Section 'runtime-analysis' requires RuntimeAnalysisData."
        )

    views = [
        AnalysisCatalogueView(
            view_id="overview",
            label="Overview",
            title=overview_section.title,
            group="assessment",
            description=overview_section.description,
            body_html=rendered_html.get(
                "overview",
                "",
            ),
        ),
        AnalysisCatalogueView(
            view_id="parallel-runtime-model",
            label="Parallel Runtime Model",
            title=runtime_data.parallel_runtime_model.title,
            group="assessment",
            description=(
                runtime_data.parallel_runtime_model.description
            ),
            body_html=rendered_html.get(
                "parallel-runtime-model",
                "",
            ),
        ),
    ]

    if scalability_section is not None:
        _validate_section(
            section=scalability_section,
            expected_id="scalability-analysis",
            expected_type="scalability-analysis",
        )

        scalability_data = scalability_section.payload

        if not isinstance(
            scalability_data,
            ScalabilityAnalysisData,
        ):
            raise TypeError(
                "Section 'scalability-analysis' requires "
                "ScalabilityAnalysisData."
            )

        views.append(
            AnalysisCatalogueView(
                view_id="computation-scalability",
                label="Computation Scalability",
                title=scalability_data.analysis.title,
                group="assessment",
                description=scalability_data.analysis.description,
                body_html=rendered_html.get(
                    "computation-scalability",
                    "",
                ),
            )
        )

    for component in runtime_data.runtime_components:
        views.append(
            AnalysisCatalogueView(
                view_id=component.component_id,
                label=component.runtime_name,
                title=component.metrics.title,
                group="runtime",
                description=component.metrics.description,
                body_html=rendered_html.get(
                    component.component_id,
                    "",
                ),
            )
        )

    if resource_section is not None:
        _validate_section(
            section=resource_section,
            expected_id="resource-analysis",
            expected_type="resource-analysis",
        )

        resource_data = resource_section.payload

        if not isinstance(
            resource_data,
            ResourceAnalysisData,
        ):
            raise TypeError(
                "Section 'resource-analysis' requires "
                "ResourceAnalysisData."
            )

        views.extend(
            (
                AnalysisCatalogueView(
                    view_id="host-analysis",
                    label="Host",
                    title=resource_data.host.title,
                    group="domain",
                    description=resource_data.host.description,
                    body_html=rendered_html.get(
                        "host-analysis",
                        "",
                    ),
                ),
                AnalysisCatalogueView(
                    view_id="device-analysis",
                    label="Device",
                    title=resource_data.device.title,
                    group="domain",
                    description=resource_data.device.description,
                    body_html=rendered_html.get(
                        "device-analysis",
                        "",
                    ),
                ),
            )
        )

    return AnalysisCatalogue(
        views=tuple(
            views
        )
    )