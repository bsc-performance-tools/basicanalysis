"""Guided HTML navigation for the interactive performance report."""

from __future__ import annotations

import html

from typing import Dict, Optional, Sequence, Tuple

from .analysis_catalogue import (
    AnalysisCatalogue,
    AnalysisCatalogueView,
)


_PRIMARY_VIEW_IDS = (
    "overview",
    "parallel-runtime-model",
    "computation-scalability",
)

_DRILLDOWN_GROUPS = (
    "runtime",
    "domain",
)


def _safe_dom_id(value: str) -> str:
    """Return a stable HTML identifier."""

    characters = []

    for character in str(value):
        if character.isalnum():
            characters.append(character.lower())
        else:
            characters.append("-")

    result = "".join(characters).strip("-")

    while "--" in result:
        result = result.replace("--", "-")

    return result or "analysis-view"


def _validate_catalogue(
    catalogue: AnalysisCatalogue,
) -> None:
    """Validate the catalogue required by the guided navigation."""

    if not isinstance(catalogue, AnalysisCatalogue):
        raise TypeError(
            "The guided navigation requires an AnalysisCatalogue."
        )

    if not catalogue.has_view("overview"):
        raise ValueError(
            "The analysis catalogue must contain the Overview view."
        )

    if not catalogue.has_view("parallel-runtime-model"):
        raise ValueError(
            "The analysis catalogue must contain the "
            "Parallel Runtime Model view."
        )

    view_ids = [
        view.view_id
        for view in catalogue.views
    ]

    if len(view_ids) != len(set(view_ids)):
        raise ValueError(
            "Analysis catalogue identifiers must be unique."
        )


def _primary_views(
    catalogue: AnalysisCatalogue,
) -> Tuple[AnalysisCatalogueView, ...]:
    """Return available primary views in methodological order."""

    views = []

    for view_id in _PRIMARY_VIEW_IDS:
        view = catalogue.get_view(view_id)

        if view is not None:
            views.append(view)

    return tuple(views)


def _drilldown_views(
    catalogue: AnalysisCatalogue,
) -> Tuple[AnalysisCatalogueView, ...]:
    """Return runtime and execution-domain drill-down views."""

    return tuple(
        view
        for view in catalogue.views
        if view.group in _DRILLDOWN_GROUPS
    )


def _comparison_targets(
    catalogue: AnalysisCatalogue,
    source_view_id: str,
) -> Tuple[AnalysisCatalogueView, ...]:
    """Return meaningful comparison targets for one primary view."""

    permitted_ids = {
        "overview": (
            "parallel-runtime-model",
            "computation-scalability",
        ),
        "parallel-runtime-model": (
            "overview",
            "computation-scalability",
        ),
        "computation-scalability": (
            "overview",
            "parallel-runtime-model",
        ),
    }

    return tuple(
        view
        for view_id in permitted_ids.get(source_view_id, ())
        for view in (catalogue.get_view(view_id),)
        if view is not None
    )


def _render_primary_tabs(
    views: Sequence[AnalysisCatalogueView],
) -> str:
    """Render the primary analytical navigation."""

    lines = [
        (
            '<nav class="guided-primary-tabs" '
            'role="tablist" '
            'aria-label="Primary performance analyses">'
        )
    ]

    for index, view in enumerate(views):
        is_active = index == 0

        lines.append(
            """
            <button
                type="button"
                id="guided-tab-{safe_id}"
                class="guided-primary-tab{active_class}"
                role="tab"
                aria-selected="{selected}"
                aria-controls="guided-primary-stage"
                data-guided-primary-target="{view_id}"
            >
                {label}
            </button>
            """.format(
                safe_id=html.escape(
                    _safe_dom_id(view.view_id),
                    quote=True,
                ),
                active_class=" is-active" if is_active else "",
                selected="true" if is_active else "false",
                view_id=html.escape(view.view_id, quote=True),
                label=html.escape(view.label),
            )
        )

    lines.append("</nav>")

    return "\n".join(lines)


def _render_compare_control(
    catalogue: AnalysisCatalogue,
    source_view: AnalysisCatalogueView,
) -> str:
    """Render controlled comparison options for one primary view."""

    targets = _comparison_targets(
        catalogue=catalogue,
        source_view_id=source_view.view_id,
    )

    if not targets:
        return ""

    options = [
        '<option value="">Compare with…</option>'
    ]

    for target in targets:
        options.append(
            '<option value="{view_id}">{label}</option>'.format(
                view_id=html.escape(
                    target.view_id,
                    quote=True,
                ),
                label=html.escape(target.label),
            )
        )

    return """
    <div
        class="guided-comparison-control"
        data-guided-comparison-control="{source_view_id}"
        hidden
    >
        <label for="guided-compare-{safe_id}">
            Compare current analysis
        </label>

        <select
            id="guided-compare-{safe_id}"
            class="guided-comparison-selector"
            data-guided-comparison-selector
        >
            {options}
        </select>
    </div>
    """.format(
        source_view_id=html.escape(
            source_view.view_id,
            quote=True,
        ),
        safe_id=html.escape(
            _safe_dom_id(source_view.view_id),
            quote=True,
        ),
        options="\n".join(options),
    )


def _render_comparison_controls(
    catalogue: AnalysisCatalogue,
    primary_views: Sequence[AnalysisCatalogueView],
) -> str:
    """Render comparison controls for every primary analysis."""

    return "\n".join(
        _render_compare_control(
            catalogue=catalogue,
            source_view=view,
        )
        for view in primary_views
    )


def _render_drilldown_selector(
    views: Sequence[AnalysisCatalogueView],
) -> str:
    """Render runtime and execution-domain analysis buttons."""

    if not views:
        return """
        <aside class="guided-drilldown-selector is-empty">
            <p>
                No additional runtime-specific or execution-domain
                analysis is available.
            </p>
        </aside>
        """.strip()

    groups = (
        (
            "runtime",
            "Runtime analysis",
            "Inspect the behavior of an active parallel runtime.",
        ),
        (
            "domain",
            "Resource analysis",
            "Inspect where accelerator-related inefficiencies manifest.",
        ),
    )

    lines = [
        (
            '<aside class="guided-drilldown-selector" '
            'aria-label="Detailed runtime and resource analyses">'
        )
    ]

    for group_id, title, description in groups:
        group_views = [
            view
            for view in views
            if view.group == group_id
        ]

        if not group_views:
            continue

        lines.append(
            """
            <section
                class="guided-drilldown-group"
                data-guided-drilldown-group="{group_id}"
            >
                <h3>{title}</h3>
                <p>{description}</p>

                <div class="guided-drilldown-buttons">
            """.format(
                group_id=html.escape(group_id, quote=True),
                title=html.escape(title),
                description=html.escape(description),
            )
        )

        for view in group_views:
            lines.append(
                """
                <button
                    type="button"
                    class="guided-drilldown-button"
                    data-guided-drilldown-target="{view_id}"
                    aria-pressed="false"
                >
                    {label}
                </button>
                """.format(
                    view_id=html.escape(
                        view.view_id,
                        quote=True,
                    ),
                    label=html.escape(view.label),
                )
            )

        lines.append("</div>")
        lines.append("</section>")

    lines.append("</aside>")

    return "\n".join(lines)


def _render_view_store(
    catalogue: AnalysisCatalogue,
) -> str:
    """Render every analysis body exactly once.

    JavaScript moves these nodes into the active primary, comparison, or
    drill-down panel. Moving nodes instead of cloning them prevents duplicate
    HTML identifiers and preserves metric interaction state.
    """

    lines = [
        (
            '<div class="guided-view-store" '
            'data-guided-view-store '
            'hidden>'
        )
    ]

    for view in catalogue.views:
        body_html = view.body_html

        if not body_html:
            body_html = """
            <div class="guided-view-unavailable">
                <h3>Analysis content unavailable</h3>
                <p>
                    The semantic analysis is available, but no rendered
                    HTML body was provided.
                </p>
            </div>
            """.strip()

        lines.append(
            """
            <article
                id="guided-view-{safe_id}"
                class="guided-analysis-view"
                data-guided-view-id="{view_id}"
                data-guided-view-title="{title}"
                data-guided-view-description="{description}"
            >
                {body_html}
            </article>
            """.format(
                safe_id=html.escape(
                    _safe_dom_id(view.view_id),
                    quote=True,
                ),
                view_id=html.escape(
                    view.view_id,
                    quote=True,
                ),
                title=html.escape(
                    view.title,
                    quote=True,
                ),
                description=html.escape(
                    view.description,
                    quote=True,
                ),
                body_html=body_html,
            )
        )

    lines.append("</div>")

    return "\n".join(lines)


def _render_navigation_script() -> str:
    """Render guided navigation and controlled comparison behavior."""

    return """
    <script>
    (function () {
        "use strict";

        const roots = document.querySelectorAll(
            "[data-guided-analysis-navigation]"
        );

        roots.forEach(function (root) {
            const store = root.querySelector(
                "[data-guided-view-store]"
            );

            const primarySlot = root.querySelector(
                "[data-guided-primary-slot]"
            );

            const comparisonRegion = root.querySelector(
                "[data-guided-comparison-region]"
            );

            const comparisonSlot = root.querySelector(
                "[data-guided-comparison-slot]"
            );

            const comparisonTitle = root.querySelector(
                "[data-guided-comparison-title]"
            );

            const comparisonDescription = root.querySelector(
                "[data-guided-comparison-description]"
            );

            const closeComparisonButton = root.querySelector(
                "[data-guided-close-comparison]"
            );

            const runtimeLayout = root.querySelector(
                "[data-guided-runtime-layout]"
            );

            const drilldownSlot = root.querySelector(
                "[data-guided-drilldown-slot]"
            );

            const drilldownTitle = root.querySelector(
                "[data-guided-drilldown-title]"
            );

            const drilldownDescription = root.querySelector(
                "[data-guided-drilldown-description]"
            );

            const closeDrilldownButton = root.querySelector(
                "[data-guided-close-drilldown]"
            );

            const primaryTabs = Array.from(
                root.querySelectorAll(
                    "[data-guided-primary-target]"
                )
            );

            const comparisonControls = Array.from(
                root.querySelectorAll(
                    "[data-guided-comparison-control]"
                )
            );

            const comparisonSelectors = Array.from(
                root.querySelectorAll(
                    "[data-guided-comparison-selector]"
                )
            );

            const drilldownButtons = Array.from(
                root.querySelectorAll(
                    "[data-guided-drilldown-target]"
                )
            );

            let activePrimaryId = "overview";
            let activeComparisonId = null;
            let activeDrilldownId = null;

            function findView(viewId) {
                return root.querySelector(
                    '[data-guided-view-id="' + viewId + '"]'
                );
            }

            function resizeVisiblePlots(container) {
                if (
                    !container
                    || typeof window.Plotly === "undefined"
                ) {
                    return;
                }

                const plots = container.querySelectorAll(
                    ".js-plotly-plot"
                );

                plots.forEach(function (plot) {
                    try {
                        window.Plotly.Plots.resize(plot);
                    } catch (error) {
                        // Non-Plotly content remains usable.
                    }
                });
            }

            function returnViewToStore(viewId) {
                const view = findView(viewId);

                if (view && store) {
                    store.appendChild(view);
                }
            }

            function mountView(viewId, slot) {
                const view = findView(viewId);

                if (!view || !slot) {
                    return null;
                }

                slot.replaceChildren();
                slot.appendChild(view);

                window.requestAnimationFrame(function () {
                    resizeVisiblePlots(view);
                });

                return view;
            }

            function closeComparison() {
                if (activeComparisonId) {
                    returnViewToStore(activeComparisonId);
                }

                activeComparisonId = null;

                if (comparisonSlot) {
                    comparisonSlot.replaceChildren();
                }

                if (comparisonRegion) {
                    comparisonRegion.hidden = true;
                }

                comparisonSelectors.forEach(function (selector) {
                    selector.value = "";
                });
            }

            function closeDrilldown() {
                if (activeDrilldownId) {
                    returnViewToStore(activeDrilldownId);
                }

                activeDrilldownId = null;

                if (drilldownSlot) {
                    drilldownSlot.replaceChildren();
                }

                if (runtimeLayout) {
                    runtimeLayout.classList.remove(
                        "has-drilldown"
                    );
                }

                drilldownButtons.forEach(function (button) {
                    button.classList.remove("is-selected");
                    button.setAttribute("aria-pressed", "false");
                });
            }

            function updateComparisonControl() {
                comparisonControls.forEach(function (control) {
                    control.hidden =
                        control.dataset.guidedComparisonControl
                        !== activePrimaryId;
                });
            }

            function showPrimary(viewId) {
                if (viewId === activePrimaryId) {
                    return;
                }

                closeComparison();
                closeDrilldown();

                returnViewToStore(activePrimaryId);

                activePrimaryId = viewId;

                const selectedView = mountView(
                    activePrimaryId,
                    primarySlot
                );

                primaryTabs.forEach(function (button) {
                    const isSelected =
                        button.dataset.guidedPrimaryTarget
                        === activePrimaryId;

                    button.classList.toggle(
                        "is-active",
                        isSelected
                    );

                    button.setAttribute(
                        "aria-selected",
                        isSelected ? "true" : "false"
                    );
                });

                root.dataset.activePrimaryView = activePrimaryId;

                root.classList.toggle(
                    "is-runtime-primary",
                    activePrimaryId
                    === "parallel-runtime-model"
                );

                updateComparisonControl();

                if (selectedView && primarySlot) {
                    primarySlot.scrollTop = 0;
                }
            }

            function openComparison(viewId) {
                if (!viewId || viewId === activePrimaryId) {
                    closeComparison();
                    return;
                }

                closeDrilldown();

                if (activeComparisonId) {
                    returnViewToStore(activeComparisonId);
                }

                activeComparisonId = viewId;

                const selectedView = mountView(
                    activeComparisonId,
                    comparisonSlot
                );

                if (!selectedView) {
                    activeComparisonId = null;
                    return;
                }

                if (comparisonTitle) {
                    comparisonTitle.textContent =
                        selectedView.dataset.guidedViewTitle || "";
                }

                if (comparisonDescription) {
                    comparisonDescription.textContent =
                        selectedView.dataset.guidedViewDescription || "";
                }

                if (comparisonRegion) {
                    comparisonRegion.hidden = false;
                }

                window.requestAnimationFrame(function () {
                    resizeVisiblePlots(primarySlot);
                    resizeVisiblePlots(comparisonSlot);
                });
            }

            function openDrilldown(viewId, button) {
                if (activePrimaryId !== "parallel-runtime-model") {
                    return;
                }

                closeComparison();

                if (activeDrilldownId === viewId) {
                    closeDrilldown();
                    return;
                }

                if (activeDrilldownId) {
                    returnViewToStore(activeDrilldownId);
                }

                activeDrilldownId = viewId;

                const selectedView = mountView(
                    activeDrilldownId,
                    drilldownSlot
                );

                if (!selectedView) {
                    activeDrilldownId = null;
                    return;
                }

                if (drilldownTitle) {
                    drilldownTitle.textContent =
                        selectedView.dataset.guidedViewTitle || "";
                }

                if (drilldownDescription) {
                    drilldownDescription.textContent =
                        selectedView.dataset.guidedViewDescription || "";
                }

                if (runtimeLayout) {
                    runtimeLayout.classList.add(
                        "has-drilldown"
                    );
                }

                drilldownButtons.forEach(function (candidate) {
                    const selected =
                        candidate.dataset.guidedDrilldownTarget
                        === activeDrilldownId;

                    candidate.classList.toggle(
                        "is-selected",
                        selected
                    );

                    candidate.setAttribute(
                        "aria-pressed",
                        selected ? "true" : "false"
                    );
                });

                if (button) {
                    button.focus();
                }

                window.requestAnimationFrame(function () {
                    resizeVisiblePlots(primarySlot);
                    resizeVisiblePlots(drilldownSlot);
                });
            }

            primaryTabs.forEach(function (button) {
                button.addEventListener("click", function () {
                    showPrimary(
                        button.dataset.guidedPrimaryTarget
                    );
                });
            });

            comparisonSelectors.forEach(function (selector) {
                selector.addEventListener("change", function () {
                    openComparison(selector.value);
                });
            });

            drilldownButtons.forEach(function (button) {
                button.addEventListener("click", function () {
                    openDrilldown(
                        button.dataset.guidedDrilldownTarget,
                        button
                    );
                });
            });

            if (closeComparisonButton) {
                closeComparisonButton.addEventListener(
                    "click",
                    closeComparison
                );
            }

            if (closeDrilldownButton) {
                closeDrilldownButton.addEventListener(
                    "click",
                    closeDrilldown
                );
            }

            activePrimaryId =
                root.dataset.activePrimaryView || "overview";

            mountView(activePrimaryId, primarySlot);

            root.classList.toggle(
                "is-runtime-primary",
                activePrimaryId
                === "parallel-runtime-model"
            );

            updateComparisonControl();
        });
    }());
    </script>
    """.strip()


def render_analysis_navigation(
    catalogue: AnalysisCatalogue,
) -> str:
    """Render the complete guided interactive-report navigation."""

    _validate_catalogue(catalogue)

    primary_views = _primary_views(catalogue)
    drilldown_views = _drilldown_views(catalogue)

    return """
    <section
        class="guided-analysis-navigation"
        data-guided-analysis-navigation
        data-active-primary-view="overview"
        aria-label="Guided performance analysis"
    >
        <header class="guided-navigation-header">
            <div>
                <p class="guided-navigation-eyebrow">
                    Performance-analysis workflow
                </p>

                <h1>Interactive Report</h1>

                <p>
                    Start from the execution overview, continue with runtime
                    attribution, and inspect computation scalability when a
                    scaling experiment is available.
                </p>
            </div>

            <div class="guided-navigation-actions">
                {comparison_controls}
            </div>
        </header>

        {primary_tabs}

        <div class="guided-analysis-stage">
            <div
                class="guided-primary-region"
                data-guided-runtime-layout
            >
                <main
                    class="guided-primary-panel"
                    data-guided-primary-slot
                    aria-label="Primary analysis"
                ></main>

                <section
                    class="guided-drilldown-panel"
                    aria-label="Selected detailed analysis"
                >
                    <header class="guided-secondary-header">
                        <div>
                            <p class="guided-secondary-eyebrow">
                                Detailed analysis
                            </p>

                            <h2 data-guided-drilldown-title>
                                Selected analysis
                            </h2>

                            <p data-guided-drilldown-description></p>
                        </div>

                        <button
                            type="button"
                            class="guided-secondary-close"
                            data-guided-close-drilldown
                            aria-label="Close detailed analysis"
                        >
                            ×
                        </button>
                    </header>

                    <div
                        class="guided-secondary-content"
                        data-guided-drilldown-slot
                    ></div>
                </section>

                <div class="guided-runtime-selector-region">
                    {drilldown_selector}
                </div>
            </div>

            <section
                class="guided-comparison-region"
                data-guided-comparison-region
                hidden
                aria-label="Comparison analysis"
            >
                <header class="guided-secondary-header">
                    <div>
                        <p class="guided-secondary-eyebrow">
                            Comparative analysis
                        </p>

                        <h2 data-guided-comparison-title>
                            Comparison
                        </h2>

                        <p data-guided-comparison-description></p>
                    </div>

                    <button
                        type="button"
                        class="guided-secondary-close"
                        data-guided-close-comparison
                        aria-label="Close comparison"
                    >
                        ×
                    </button>
                </header>

                <div
                    class="guided-secondary-content"
                    data-guided-comparison-slot
                ></div>
            </section>
        </div>

        {view_store}
    </section>

    {navigation_script}
    """.format(
        comparison_controls=_render_comparison_controls(
            catalogue=catalogue,
            primary_views=primary_views,
        ),
        primary_tabs=_render_primary_tabs(primary_views),
        drilldown_selector=_render_drilldown_selector(
            drilldown_views
        ),
        view_store=_render_view_store(catalogue),
        navigation_script=_render_navigation_script(),
    )