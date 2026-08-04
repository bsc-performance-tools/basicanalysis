"""Interactive HTML layout for the guided Performance Assessment view."""

from __future__ import annotations

import html

from dataclasses import dataclass
from typing import Mapping, Optional, Sequence, Tuple

from ...model import ReportSection
from ...sections import (
    ResourceAnalysisData,
    RuntimeAnalysisData,
)


@dataclass(frozen=True)
class AnalysisView:
    """One runtime or execution-domain analysis available for selection."""

    view_id: str
    label: str
    title: str
    group: str
    description: str
    body_html: str = ""


def _validate_section(
    section: ReportSection,
    expected_id: str,
    expected_type: str,
) -> None:
    """Validate a semantic report section before rendering."""

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


def _safe_dom_id(value: str) -> str:
    """Return a safe and stable HTML identifier."""

    normalized = []

    for character in str(value):
        if character.isalnum():
            normalized.append(
                character.lower()
            )
        else:
            normalized.append("-")

    result = "".join(
        normalized
    ).strip("-")

    while "--" in result:
        result = result.replace(
            "--",
            "-",
        )

    if not result:
        return "analysis-view"

    return result


def _group_title(group: str) -> str:
    """Return the visible title of one selector group."""

    titles = {
        "runtime": "Runtime components",
        "domain": "Execution domains",
    }

    return titles.get(
        group,
        "Analysis views",
    )


def _group_views(
    views: Sequence[AnalysisView],
) -> Tuple[Tuple[str, Tuple[AnalysisView, ...]], ...]:
    """Group views while preserving semantic display order."""

    groups = []

    for group_name in (
        "runtime",
        "domain",
    ):
        group_views = tuple(
            view
            for view in views
            if view.group == group_name
        )

        if group_views:
            groups.append(
                (
                    group_name,
                    group_views,
                )
            )

    return tuple(groups)


def build_analysis_views(
    runtime_section: ReportSection,
    resource_section: Optional[ReportSection],
    component_html: Optional[Mapping[str, str]] = None,
) -> Tuple[AnalysisView, ...]:
    """Build selector entries from Runtime and Resource Analysis."""

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

    rendered_components = component_html or {}

    views = []

    for component in runtime_data.runtime_components:
        views.append(
            AnalysisView(
                view_id=component.component_id,
                label=component.runtime_name,
                title=component.metrics.title,
                group="runtime",
                description=component.metrics.description,
                body_html=rendered_components.get(
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
                AnalysisView(
                    view_id="host-analysis",
                    label="Host",
                    title=resource_data.host.title,
                    group="domain",
                    description=resource_data.host.description,
                    body_html=rendered_components.get(
                        "host-analysis",
                        "",
                    ),
                ),
                AnalysisView(
                    view_id="device-analysis",
                    label="Device",
                    title=resource_data.device.title,
                    group="domain",
                    description=resource_data.device.description,
                    body_html=rendered_components.get(
                        "device-analysis",
                        "",
                    ),
                ),
            )
        )

    return tuple(views)


def render_analysis_selector(
    views: Sequence[AnalysisView],
) -> str:
    """Render the interactive vertical analysis selector."""

    if not views:
        return """
        <aside
            class="performance-analysis-selector is-empty"
            aria-label="Available analysis views"
        >
            <p>
                No additional runtime or execution-domain analysis is
                available for this execution model.
            </p>
        </aside>
        """.strip()

    lines = [
        (
            '<aside class="performance-analysis-selector" '
            'aria-label="Available analysis views">'
        )
    ]

    for group_name, group_views in _group_views(
        views
    ):
        lines.append(
            (
                '<section class="analysis-selector-group" '
                'data-analysis-group="{}">'
            ).format(
                html.escape(
                    group_name,
                    quote=True,
                )
            )
        )

        lines.append(
            "<h4>{}</h4>".format(
                html.escape(
                    _group_title(
                        group_name
                    )
                )
            )
        )

        lines.append(
            '<div class="analysis-selector-buttons">'
        )

        for view in group_views:
            safe_id = _safe_dom_id(
                view.view_id
            )

            lines.append(
                (
                    '<button '
                    'type="button" '
                    'class="analysis-selector-button" '
                    'data-analysis-target="{target}" '
                    'aria-controls="performance-analysis-view-{target}" '
                    'aria-selected="false">'
                    "{label}"
                    "</button>"
                ).format(
                    target=html.escape(
                        safe_id,
                        quote=True,
                    ),
                    label=html.escape(
                        view.label
                    ),
                )
            )

        lines.append("</div>")
        lines.append("</section>")

    lines.append("</aside>")

    return "\n".join(
        lines
    )


def render_secondary_panel(
    views: Sequence[AnalysisView],
) -> str:
    """Render the placeholder and all selectable analysis bodies."""

    if not views:
        return ""

    lines = [
        (
            '<section '
            'class="performance-secondary-panel" '
            'aria-label="Selected analysis" '
            'data-performance-secondary-panel>'
        ),
        (
            '<div '
            'class="performance-secondary-placeholder" '
            'data-performance-secondary-placeholder>'
        ),
        "<h3>Selected analysis</h3>",
        (
            "<p>"
            "Select a runtime component or execution domain to inspect "
            "its metrics while keeping the Parallel Runtime Model visible."
            "</p>"
        ),
        "</div>",
    ]

    for view in views:
        safe_id = _safe_dom_id(
            view.view_id
        )

        if view.body_html:
            body_html = view.body_html
        else:
            body_html = (
                '<p class="analysis-view-empty">'
                "No rendered metric content is available for this analysis."
                "</p>"
            )

        lines.extend(
            [
                (
                    '<article '
                    'id="performance-analysis-view-{target}" '
                    'class="performance-secondary-view" '
                    'data-performance-analysis-view="{target}" '
                    'hidden>'
                ).format(
                    target=html.escape(
                        safe_id,
                        quote=True,
                    )
                ),
                (
                    '<header '
                    'class="performance-secondary-view-header">'
                ),
                (
                    '<div class="performance-secondary-heading">'
                ),
                (
                    '<p class="performance-secondary-eyebrow">'
                    "Performance analysis"
                    "</p>"
                ),
                "<h3>{}</h3>".format(
                    html.escape(
                        view.title
                    )
                ),
                "<p>{}</p>".format(
                    html.escape(
                        view.description
                    )
                ),
                "</div>",
                (
                    '<button '
                    'type="button" '
                    'class="performance-secondary-close" '
                    'data-performance-secondary-close '
                    'aria-label="Close selected analysis">'
                    "×"
                    "</button>"
                ),
                "</header>",
                (
                    '<div class="performance-secondary-body">'
                    "{}"
                    "</div>"
                ).format(
                    body_html
                ),
                "</article>",
            ]
        )

    lines.append("</section>")

    return "\n".join(
        lines
    )


def _render_interaction_script() -> str:
    """Render selector interaction for one Performance Assessment view."""

    return """
    <script>
    (function () {
        "use strict";

        const roots = document.querySelectorAll(
            "[data-performance-assessment]"
        );

        roots.forEach(function (root) {
            const placeholder = root.querySelector(
                "[data-performance-secondary-placeholder]"
            );

            const selectorButtons = Array.from(
                root.querySelectorAll(
                    "[data-analysis-target]"
                )
            );

            const analysisViews = Array.from(
                root.querySelectorAll(
                    "[data-performance-analysis-view]"
                )
            );

            const closeButtons = Array.from(
                root.querySelectorAll(
                    "[data-performance-secondary-close]"
                )
            );

            let selectedTarget = null;

            function clearSelection() {
                selectedTarget = null;

                selectorButtons.forEach(function (button) {
                    button.classList.remove(
                        "is-selected"
                    );

                    button.setAttribute(
                        "aria-selected",
                        "false"
                    );
                });

                analysisViews.forEach(function (view) {
                    view.hidden = true;
                    view.classList.remove(
                        "is-active"
                    );
                });

                if (placeholder) {
                    placeholder.hidden = false;
                }
            }

            function selectView(target) {
                selectedTarget = target;

                selectorButtons.forEach(function (button) {
                    const isSelected =
                        button.dataset.analysisTarget === target;

                    button.classList.toggle(
                        "is-selected",
                        isSelected
                    );

                    button.setAttribute(
                        "aria-selected",
                        isSelected ? "true" : "false"
                    );
                });

                analysisViews.forEach(function (view) {
                    const isSelected =
                        view.dataset.performanceAnalysisView === target;

                    view.hidden = !isSelected;
                    view.classList.toggle(
                        "is-active",
                        isSelected
                    );
                });

                if (placeholder) {
                    placeholder.hidden = true;
                }

                const selectedView = root.querySelector(
                    '[data-performance-analysis-view="' +
                    target +
                    '"]'
                );

                if (selectedView) {
                    selectedView.scrollTop = 0;
                }
            }

            selectorButtons.forEach(function (button) {
                button.addEventListener(
                    "click",
                    function () {
                        const target =
                            button.dataset.analysisTarget;

                        if (selectedTarget === target) {
                            clearSelection();
                            return;
                        }

                        selectView(
                            target
                        );
                    }
                );
            });

            closeButtons.forEach(function (button) {
                button.addEventListener(
                    "click",
                    clearSelection
                );
            });

            clearSelection();
        });
    }());
    </script>
    """.strip()


def render_performance_assessment(
    assessment_section: ReportSection,
    runtime_section: ReportSection,
    resource_section: Optional[ReportSection],
    parallel_runtime_model_html: str,
    component_html: Optional[Mapping[str, str]] = None,
) -> str:
    """Render the interactive Performance Assessment layout."""

    _validate_section(
        section=assessment_section,
        expected_id="performance-assessment",
        expected_type="performance-assessment",
    )

    views = build_analysis_views(
        runtime_section=runtime_section,
        resource_section=resource_section,
        component_html=component_html,
    )

    selector_html = render_analysis_selector(
        views
    )

    secondary_panel_html = render_secondary_panel(
        views
    )

    if views:
        layout_class = "has-secondary-views"
    else:
        layout_class = "no-secondary-views"

    return """
    <section
        class="performance-assessment-view"
        aria-label="Performance Assessment"
        data-performance-assessment
    >
        <section class="performance-runtime-analysis">
            <header class="performance-section-header">
                <h2>Parallel Runtime Model</h2>

                <p>
                    Attribute the parallel-efficiency loss to the active
                    runtimes and inspect complementary runtime or
                    execution-domain analyses.
                </p>
            </header>

            <div class="performance-analysis-layout {layout_class}">
                <section
                    class="performance-primary-panel"
                    aria-label="Parallel Runtime Model"
                >
                    <div class="performance-primary-body">
                        {parallel_runtime_model_html}
                    </div>
                </section>

                {secondary_panel_html}

                {selector_html}
            </div>
        </section>
    </section>

    {interaction_script}
    """.format(
        layout_class=layout_class,
        parallel_runtime_model_html=(
            parallel_runtime_model_html
        ),
        secondary_panel_html=secondary_panel_html,
        selector_html=selector_html,
        interaction_script=_render_interaction_script(),
    )