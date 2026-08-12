"""Build the HTML analysis-view catalogue used by the interactive report."""

from __future__ import annotations

from typing import Mapping, Optional

from ...model import ReportSection
from ...sections import (
    ResourceAnalysisData,
    RuntimeAnalysisData,
    ScalabilityAnalysisData,
)


class AnalysisCatalogueView:
    """One analysis view available to the interactive report."""

    def __init__(
        self,
        view_id,
        label,
        title,
        group,
        description,
        body_html,
    ):
        self.view_id = view_id
        self.label = label
        self.title = title
        self.group = group
        self.description = description
        self.body_html = body_html


class AnalysisCatalogue:
    """Ordered collection of available analysis views."""

    def __init__(
        self,
        views,
    ):
        self.views = tuple(views)

    def get_view(
        self,
        view_id,
    ):
        """Return one view by semantic identifier."""

        for view in self.views:
            if view.view_id == view_id:
                return view

        return None

    def has_view(
        self,
        view_id,
    ):
        """Return whether the catalogue contains a view."""

        return self.get_view(
            view_id
        ) is not None

    def views_by_group(
        self,
        group,
    ):
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


def _build_execution_domains_html(
    rendered_html: Mapping[str, str],
) -> str:
    """Build the combined Host/Device execution-domain view.

    Prefer a dedicated Execution Domains renderer when available.

    During the transition to the new navigation architecture, fall back
    to composing the existing Host and Device HTML bodies. This keeps
    the new primary view functional without duplicating metric logic.
    """

    execution_domains_html = rendered_html.get(
        "execution-domains",
        "",
    )

    if execution_domains_html:
        return execution_domains_html

    host_html = rendered_html.get(
        "host-analysis",
        "",
    )

    device_html = rendered_html.get(
        "device-analysis",
        "",
    )

    return "\n".join(
        html_body
        for html_body in (
            host_html,
            device_html,
        )
        if html_body
    )


def build_analysis_catalogue(
    overview_section: ReportSection,
    runtime_section: ReportSection,
    resource_section: Optional[ReportSection],
    scalability_section: Optional[ReportSection],
    rendered_html: Mapping[str, str],
) -> AnalysisCatalogue:
    """Build the ordered catalogue of available analysis views.

    Primary analytical views are organized according to the
    performance-analysis workflow:

        Overview
            Application and execution context together with the
            application-level performance assessment.

        Parallel Runtime Model
            Attributes parallel-efficiency losses to the active
            parallel runtimes.

        Execution Domains
            For accelerator executions, identifies where inefficiencies
            manifest across host execution, the offload path, and
            device execution.

        Computation Scalability
            Evaluates how useful computation changes across multiple
            execution configurations.

    Runtime-specific and execution-domain-specific views are also kept
    in the catalogue as secondary views so they can later be used for
    detailed analysis, correlation, and export operations.

    Parameters
    ----------
    overview_section
        Semantic Overview section.

    runtime_section
        Semantic Runtime Analysis section.

    resource_section
        Optional Resource Analysis section for accelerator executions.
        When present, the catalogue exposes an Execution Domains primary
        view composed of the Host and Device analyses.

    scalability_section
        Optional Scalability Analysis section. It is absent for
        single-trace reports and when no valid scalability metric is
        available.

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
            group="primary",
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
            group="primary",
            description=(
                runtime_data.parallel_runtime_model.description
            ),
            body_html=rendered_html.get(
                "parallel-runtime-model",
                "",
            ),
        ),
    ]

    resource_data = None

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

        views.append(
            AnalysisCatalogueView(
                view_id="execution-domains",
                label="Execution Domains",
                title="Execution Domains",
                group="primary",
                description=(
                    "Analyze where accelerator-related inefficiencies "
                    "manifest across host execution, the offload path, "
                    "and device execution."
                ),
                body_html=_build_execution_domains_html(
                    rendered_html
                ),
            )
        )

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
                group="primary",
                description=scalability_data.analysis.description,
                body_html=rendered_html.get(
                    "computation-scalability",
                    "",
                ),
            )
        )

    # Runtime-specific views remain available as secondary analyses.
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

    # Keep Host and Device as separate secondary views.
    #
    # The primary Execution Domains view presents both together, while
    # these entries remain useful for future detailed inspection,
    # correlation, and export functionality.
    if resource_data is not None:
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