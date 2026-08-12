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
    "execution-domains",
    "computation-scalability",
)


_DRILLDOWN_GROUPS = (
    "runtime",
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
    """Return runtime-specific drill-down views."""

    return tuple(
        view
        for view in catalogue.views
        if view.group in _DRILLDOWN_GROUPS
    )


def _render_primary_tabs(
    views: Sequence[AnalysisCatalogueView],
) -> str:
    """Render primary navigation and the split-view control."""

    lines = [
        '<div class="guided-primary-tabs">',
        (
            '<nav class="guided-primary-tab-list" '
            'role="tablist" '
            'aria-label="Primary performance analyses">'
        ),
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

    lines.append(
        """
        <div
            class="guided-split-control"
            data-guided-split-control
        >
            <button
                type="button"
                class="guided-split-button"
                data-guided-split-button
                aria-label="Open complementary analysis view"
                aria-haspopup="menu"
                aria-expanded="false"
                title="Open complementary analysis view"
            >
                <svg
                    viewBox="0 0 24 24"
                    aria-hidden="true"
                    focusable="false"
                >
                    <rect
                        x="3"
                        y="4"
                        width="18"
                        height="16"
                        rx="2"
                        fill="none"
                        stroke="currentColor"
                        stroke-width="1.8"
                    ></rect>

                    <line
                        x1="12"
                        y1="4"
                        x2="12"
                        y2="20"
                        stroke="currentColor"
                        stroke-width="1.8"
                    ></line>
                </svg>
            </button>

            <div
                class="guided-split-menu"
                data-guided-split-menu
                role="menu"
                hidden
            >
                <div class="guided-split-menu-title">
                    Open second view
                </div>
        """
    )

    for view in views:
        lines.append(
            """
            <button
                type="button"
                class="guided-split-option"
                data-guided-split-target="{view_id}"
                role="menuitem"
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

    lines.extend(
        [
            "</div>",
            "</div>",
            "</div>",
        ]
    )

    return "\n".join(lines)


def _render_drilldown_selector(
    views: Sequence[AnalysisCatalogueView],
) -> str:
    """Render the compact runtime-analysis selector."""

    if not views:
        return ""

    lines = [
        (
            '<nav class="guided-drilldown-selector" '
            'aria-label="Runtime analysis">'
        ),
        '<span class="guided-runtime-selector-label">Runtime Analysis</span>',
        '<div class="guided-drilldown-buttons">',
    ]

    for view in views:
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

    lines.extend([
        "</div>",
        "</nav>",
    ])

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

            const comparisonDivider = root.querySelector(
                "[data-guided-comparison-divider]"
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

            const panelDivider = root.querySelector(
                "[data-guided-panel-divider]"
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

            const splitControl = root.querySelector(
                "[data-guided-split-control]"
            );

            const splitButton = root.querySelector(
                "[data-guided-split-button]"
            );

            const splitMenu = root.querySelector(
                "[data-guided-split-menu]"
            );

            const splitOptions = Array.from(
                root.querySelectorAll(
                    "[data-guided-split-target]"
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

            function initializePanelResize() {
                if (!panelDivider || !runtimeLayout) {
                    return;
                }

                let dragging = false;

                function updatePanelWidth(clientX) {
                    if (
                        !runtimeLayout.classList.contains(
                            "has-drilldown"
                        )
                    ) {
                        return;
                    }

                    const bounds =
                        runtimeLayout.getBoundingClientRect();

                    const selectorWidth = 155;
                    const dividerWidth = 8;
                    const gapsWidth = 24;

                    const usableWidth =
                        bounds.width
                        - selectorWidth
                        - dividerWidth
                        - gapsWidth;

                    if (usableWidth <= 0) {
                        return;
                    }

                    const pointerOffset =
                        clientX - bounds.left;

                    const minimumPanelWidth = 360;

                    const minimumPercentage =
                        minimumPanelWidth
                        / usableWidth
                        * 100;

                    let percentage =
                        pointerOffset
                        / usableWidth
                        * 100;

                    percentage = Math.max(
                        minimumPercentage,
                        Math.min(
                            100 - minimumPercentage,
                            percentage
                        )
                    );

                    runtimeLayout.style.setProperty(
                        "--primary-panel-width",
                        percentage.toFixed(2) + "%"
                    );

                    window.requestAnimationFrame(function () {
                        resizeVisiblePlots(primarySlot);
                        resizeVisiblePlots(drilldownSlot);
                    });
                }

                panelDivider.addEventListener(
                    "pointerdown",
                    function (event) {
                        dragging = true;

                        panelDivider.classList.add(
                            "is-dragging"
                        );

                        panelDivider.setPointerCapture(
                            event.pointerId
                        );

                        event.preventDefault();
                    }
                );

                panelDivider.addEventListener(
                    "pointermove",
                    function (event) {
                        if (!dragging) {
                            return;
                        }

                        updatePanelWidth(
                            event.clientX
                        );
                    }
                );

                panelDivider.addEventListener(
                    "pointerup",
                    function (event) {
                        dragging = false;

                        panelDivider.classList.remove(
                            "is-dragging"
                        );

                        if (
                            panelDivider.hasPointerCapture(
                                event.pointerId
                            )
                        ) {
                            panelDivider.releasePointerCapture(
                                event.pointerId
                            );
                        }
                    }
                );

                panelDivider.addEventListener(
                    "pointercancel",
                    function () {
                        dragging = false;

                        panelDivider.classList.remove(
                            "is-dragging"
                        );
                    }
                );

                panelDivider.addEventListener(
                    "keydown",
                    function (event) {
                        if (
                            event.key !== "ArrowLeft"
                            && event.key !== "ArrowRight"
                        ) {
                            return;
                        }

                        const currentValue =
                            parseFloat(
                                getComputedStyle(
                                    runtimeLayout
                                ).getPropertyValue(
                                    "--primary-panel-width"
                                )
                            )
                            || 52;

                        const adjustment =
                            event.key === "ArrowLeft"
                                ? -3
                                : 3;

                        const newValue = Math.max(
                            30,
                            Math.min(
                                70,
                                currentValue + adjustment
                            )
                        );

                        runtimeLayout.style.setProperty(
                            "--primary-panel-width",
                            newValue + "%"
                        );

                        window.requestAnimationFrame(function () {
                            resizeVisiblePlots(primarySlot);
                            resizeVisiblePlots(drilldownSlot);
                        });

                        event.preventDefault();
                    }
                );
            }

            function initializeComparisonResize() {
                if (!comparisonDivider || !comparisonRegion) {
                    return;
                }

                const analysisStage = root.querySelector(
                    ".guided-analysis-stage"
                );

                if (!analysisStage) {
                    return;
                }

                let dragging = false;

                function updateComparisonWidth(clientX) {
                    if (comparisonRegion.hidden) {
                        return;
                    }

                    const bounds =
                        analysisStage.getBoundingClientRect();

                    if (bounds.width <= 0) {
                        return;
                    }

                    const pointerOffset =
                        clientX - bounds.left;

                    let primaryPercentage =
                        pointerOffset
                        / bounds.width
                        * 100;

                    /*
                    * Keep both analysis views usable.
                    */
                    primaryPercentage = Math.max(
                        30,
                        Math.min(
                            70,
                            primaryPercentage
                        )
                    );

                    const comparisonPercentage =
                        100 - primaryPercentage;

                    analysisStage.style.setProperty(
                        "--comparison-panel-width",
                        comparisonPercentage.toFixed(2) + "%"
                    );

                    window.requestAnimationFrame(function () {
                        resizeVisiblePlots(primarySlot);
                        resizeVisiblePlots(comparisonSlot);
                    });
                }

                comparisonDivider.addEventListener(
                    "pointerdown",
                    function (event) {
                        dragging = true;

                        comparisonDivider.classList.add(
                            "is-dragging"
                        );

                        comparisonDivider.setPointerCapture(
                            event.pointerId
                        );

                        event.preventDefault();
                    }
                );

                comparisonDivider.addEventListener(
                    "pointermove",
                    function (event) {
                        if (!dragging) {
                            return;
                        }

                        updateComparisonWidth(
                            event.clientX
                        );
                    }
                );

                comparisonDivider.addEventListener(
                    "pointerup",
                    function (event) {
                        dragging = false;

                        comparisonDivider.classList.remove(
                            "is-dragging"
                        );

                        if (
                            comparisonDivider.hasPointerCapture(
                                event.pointerId
                            )
                        ) {
                            comparisonDivider.releasePointerCapture(
                                event.pointerId
                            );
                        }
                    }
                );

                comparisonDivider.addEventListener(
                    "pointercancel",
                    function () {
                        dragging = false;

                        comparisonDivider.classList.remove(
                            "is-dragging"
                        );
                    }
                );

                comparisonDivider.addEventListener(
                    "keydown",
                    function (event) {
                        if (
                            event.key !== "ArrowLeft"
                            && event.key !== "ArrowRight"
                        ) {
                            return;
                        }

                        const currentValue =
                            parseFloat(
                                getComputedStyle(
                                    analysisStage
                                ).getPropertyValue(
                                    "--comparison-panel-width"
                                )
                            )
                            || 48;

                        /*
                        * Arrow right makes the second panel smaller.
                        * Arrow left makes the second panel larger.
                        */
                        const adjustment =
                            event.key === "ArrowLeft"
                                ? 3
                                : -3;

                        const newValue = Math.max(
                            30,
                            Math.min(
                                70,
                                currentValue + adjustment
                            )
                        );

                        analysisStage.style.setProperty(
                            "--comparison-panel-width",
                            newValue + "%"
                        );

                        window.requestAnimationFrame(function () {
                            resizeVisiblePlots(primarySlot);
                            resizeVisiblePlots(comparisonSlot);
                        });

                        event.preventDefault();
                    }
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

                if (comparisonDivider) {
                    comparisonDivider.hidden = true;
                }

                updateSplitControl();
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

            function setSplitMenuOpen(isOpen) {
                if (!splitMenu || !splitButton) {
                    return;
                }

                splitMenu.hidden = !isOpen;

                splitButton.setAttribute(
                    "aria-expanded",
                    isOpen ? "true" : "false"
                );

                splitControl.classList.toggle(
                    "is-open",
                    isOpen
                );
            }


            function updateSplitControl() {
                splitOptions.forEach(function (option) {
                    const viewId =
                        option.dataset.guidedSplitTarget;

                    const isPrimary =
                        viewId === activePrimaryId;

                    option.hidden = isPrimary;

                    option.classList.toggle(
                        "is-selected",
                        viewId === activeComparisonId
                    );
                });

                if (splitControl) {
                    splitControl.classList.toggle(
                        "has-secondary-view",
                        Boolean(activeComparisonId)
                    );
                }

                if (splitButton) {
                    splitButton.setAttribute(
                        "aria-label",
                        activeComparisonId
                            ? "Change complementary analysis view"
                            : "Open complementary analysis view"
                    );

                    splitButton.title =
                        activeComparisonId
                            ? "Change complementary analysis view"
                            : "Open complementary analysis view";
                }
            }


            function toggleSplitMenu() {
                if (!splitMenu) {
                    return;
                }

                updateSplitControl();

                setSplitMenuOpen(
                    splitMenu.hidden
                );
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

                updateSplitControl();
                setSplitMenuOpen(false);

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

                if (comparisonDivider) {
                    comparisonDivider.hidden = false;
                }

                updateSplitControl();
                setSplitMenuOpen(false);

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

            if (splitButton) {
                splitButton.addEventListener(
                    "click",
                    function (event) {
                        event.stopPropagation();
                        toggleSplitMenu();
                    }
                );
            }

            splitOptions.forEach(function (option) {
                option.addEventListener(
                    "click",
                    function () {
                        openComparison(
                            option.dataset.guidedSplitTarget
                        );
                    }
                );
            });

            document.addEventListener(
                "click",
                function (event) {
                    if (
                        splitControl
                        && !splitControl.contains(event.target)
                    ) {
                        setSplitMenuOpen(false);
                    }
                }
            );

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
            
            initializePanelResize();
            initializeComparisonResize();

            mountView(activePrimaryId, primarySlot);

            root.classList.toggle(
                "is-runtime-primary",
                activePrimaryId
                === "parallel-runtime-model"
            );

            updateSplitControl();
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

                <div
                    class="guided-panel-divider"
                    data-guided-panel-divider
                    role="separator"
                    aria-orientation="vertical"
                    aria-label="Resize analysis panels"
                    tabindex="0"
                ></div>

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

                {drilldown_selector_region}

            </div>

            <div
                class="guided-comparison-divider"
                data-guided-comparison-divider
                role="separator"
                aria-orientation="vertical"
                aria-label="Resize analysis views"
                tabindex="0"
                hidden
            ></div>

            <section
                class="guided-comparison-region"
                data-guided-comparison-region
                hidden
                aria-label="Complementary analysis view"
            >
                <header class="guided-secondary-header">
                    <div>
                        <p class="guided-secondary-eyebrow">
                            Complementary view
                        </p>

                        <h2 data-guided-comparison-title>
                            Second analysis
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
        primary_tabs=_render_primary_tabs(primary_views),
        drilldown_selector_region=(
            """
            <div class="guided-runtime-selector-region">
                {selector}
            </div>
            """.format(
                selector=_render_drilldown_selector(
                    drilldown_views
                )
            )
            if drilldown_views
            else ""
        ),
        view_store=_render_view_store(catalogue),
        navigation_script=_render_navigation_script(),
    )