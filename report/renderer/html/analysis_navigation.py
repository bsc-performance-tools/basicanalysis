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


def _render_primary_tabs(views: Sequence[AnalysisCatalogueView],) -> str:
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
            "</div>",  # guided-split-menu
            "</div>",  # guided-split-control
        ]
    )

    lines.append(
        """
        <div
            class="guided-export-control"
            data-guided-export-control
        >
            <button
                type="button"
                class="guided-export-button"
                data-guided-export-button
                aria-label="Export report content"
                aria-haspopup="menu"
                aria-expanded="false"
                title="Export report content"
            >
                <svg
                    viewBox="0 0 24 24"
                    aria-hidden="true"
                    focusable="false"
                >
                    <path
                        d="M12 3v11"
                        fill="none"
                        stroke="currentColor"
                        stroke-width="1.8"
                        stroke-linecap="round"
                    ></path>

                    <path
                        d="M8 10l4 4 4-4"
                        fill="none"
                        stroke="currentColor"
                        stroke-width="1.8"
                        stroke-linecap="round"
                        stroke-linejoin="round"
                    ></path>

                    <path
                        d="M5 17v3h14v-3"
                        fill="none"
                        stroke="currentColor"
                        stroke-width="1.8"
                        stroke-linecap="round"
                        stroke-linejoin="round"
                    ></path>
                </svg>

                <span
                    class="guided-export-status"
                    data-guided-export-status
                    hidden
                ></span>
            </button>

            <div
                class="guided-export-menu"
                data-guided-export-menu
                role="menu"
                hidden
            >
                <div class="guided-export-menu-title">
                    Export
                </div>

                <div class="guided-export-menu-group">
                    <div class="guided-export-menu-group-title">
                        Images
                    </div>

                    <button
                        type="button"
                        class="guided-export-option"
                        data-guided-export-current-png
                        role="menuitem"
                    >
                        Current efficiency table (PNG)
                    </button>

                    <button
                        type="button"
                        class="guided-export-option"
                        data-guided-export-primary-png
                        role="menuitem"
                        hidden
                    >
                        Parallel Runtime Model table (PNG)
                    </button>

                    <button
                        type="button"
                        class="guided-export-option"
                        data-guided-export-application-png
                        role="menuitem"
                        hidden
                    >
                        Application Efficiency table (PNG)
                    </button>

                    <button
                        type="button"
                        class="guided-export-option"
                        data-guided-export-drilldown-png
                        role="menuitem"
                        hidden
                    >
                        Runtime Analysis table (PNG)
                    </button>

                    <button
                        type="button"
                        class="guided-export-option"
                        data-guided-export-visible-png
                        role="menuitem"
                        hidden
                    >
                        Both visible tables (PNG)
                    </button>


                    <button
                        type="button"
                        class="guided-export-option"
                        data-guided-export-all-png
                        role="menuitem"
                    >
                        All efficiency tables (ZIP)
                    </button>
                </div>

                <div class="guided-export-menu-group">
                    <div class="guided-export-menu-group-title">
                        Report
                    </div>

                    <button
                        type="button"
                        class="guided-export-option"
                        data-guided-export-pdf
                        role="menuitem"
                    >
                        Print / Save as PDF
                    </button>
                </div>
            </div>
        </div>
        """
    )

    lines.append("</div>")  # guided-primary-tabs

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

            const exportControl = root.querySelector(
                "[data-guided-export-control]"
            );

            const exportButton = root.querySelector(
                "[data-guided-export-button]"
            );

            const exportStatus = root.querySelector(
                "[data-guided-export-status]"
            );

            const exportMenu = root.querySelector(
                "[data-guided-export-menu]"
            );

            const exportCurrentPngButton = root.querySelector(
                "[data-guided-export-current-png]"
            );

            const exportApplicationPngButton = root.querySelector(
                "[data-guided-export-application-png]"
            );

            const exportPrimaryPngButton = root.querySelector(
                "[data-guided-export-primary-png]"
            );

            const exportDrilldownPngButton = root.querySelector(
                "[data-guided-export-drilldown-png]"
            );

            const exportVisiblePngButton = root.querySelector(
                "[data-guided-export-visible-png]"
            );

            const exportAllPngButton = root.querySelector(
                "[data-guided-export-all-png]"
            );

            const exportPdfButton = root.querySelector(
                "[data-guided-export-pdf]"
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

            function visibleEfficiencyTables() {
                return Array.from(
                    root.querySelectorAll(
                        "[data-efficiency-export]"
                    )
                ).filter(function (element) {
                    return (
                        element.offsetWidth > 0
                        && element.offsetHeight > 0
                        && !element.closest("[hidden]")
                    );
                });
            }           

            function activeDrilldownEfficiencyTable() {
                if (
                    activePrimaryId !== "parallel-runtime-model"
                    || !activeDrilldownId
                    || !drilldownSlot
                ) {
                    return null;
                }

                return drilldownSlot.querySelector(
                    "[data-efficiency-export]"
                );
            }

            function prmApplicationEfficiencyTable() {
                if (!primarySlot) {
                    return null;
                }

                const section = primarySlot.querySelector(
                    '[data-prm-export-role="application-efficiency"]'
                );

                if (!section) {
                    return null;
                }

                return section.querySelector(
                    "[data-efficiency-export]"
                );
            }


            function prmRuntimeModelTable() {
                if (!primarySlot) {
                    return null;
                }

                const section = primarySlot.querySelector(
                    '[data-prm-export-role="runtime-model"]'
                );

                if (!section) {
                    return null;
                }

                return section.querySelector(
                    "[data-efficiency-export]"
                );
            }


            function primaryEfficiencyTable() {
                if (
                    activePrimaryId
                    === "parallel-runtime-model"
                ) {
                    return prmRuntimeModelTable();
                }

                if (!primarySlot) {
                    return null;
                }

                return primarySlot.querySelector(
                    "[data-efficiency-export]"
                );
            }


            function activeRuntimeName() {
                if (!activeDrilldownId) {
                    return "";
                }

                const selectedButton = drilldownButtons.find(
                    function (button) {
                        return (
                            button.dataset.guidedDrilldownTarget
                            === activeDrilldownId
                        );
                    }
                );

                if (!selectedButton) {
                    return "";
                }

                return selectedButton.textContent.trim();
            }

            function allocateUniqueExportFilename(
                exportName,
                usedNames
            ) {
                const baseName =
                    safeExportFilename(
                        exportName || "efficiency-table"
                    );

                let filename =
                    baseName + ".png";

                let suffix = 2;

                while (usedNames.has(filename)) {
                    filename =
                        baseName
                        + "-"
                        + suffix
                        + ".png";

                    suffix += 1;
                }

                usedNames.add(filename);

                return filename;
            }

            function safeExportFilename(value) {
                return String(value || "efficiency-table")
                    .trim()
                    .toLowerCase()
                    .replace(/[^a-z0-9]+/g, "-")
                    .replace(/^-+|-+$/g, "");
            } 

            function downloadCanvasAsPng(canvas, filename) {
                const link = document.createElement("a");

                link.download = filename;
                link.href = canvas.toDataURL("image/png");

                document.body.appendChild(link);
                link.click();
                link.remove();
            }

            function downloadBlob(blob, filename) {
                const url = URL.createObjectURL(blob);

                const link = document.createElement("a");

                link.href = url;
                link.download = filename;

                document.body.appendChild(link);

                link.click();
                link.remove();

                window.setTimeout(function () {
                    URL.revokeObjectURL(url);
                }, 1000);
            }

            function canvasToPngBlob(canvas) {
                return new Promise(function (resolve, reject) {
                    canvas.toBlob(
                        function (blob) {
                            if (!blob) {
                                reject(
                                    new Error(
                                        "The PNG image could not be generated."
                                    )
                                );

                                return;
                            }

                            resolve(blob);
                        },
                        "image/png"
                    );
                });
            }

            function printEmbeddedReport() {
                const printableReport =
                    document.querySelector(
                        "[data-basicanalysis-printable-report]"
                    );

                if (!printableReport) {
                    window.alert(
                        "The printable report is not available."
                    );

                    return;
                }

                setExportMenuOpen(false);

                document.body.classList.add(
                    "basicanalysis-print-mode"
                );

                printableReport.hidden = false;

                preparePrintableEfficiencyTables(
                    printableReport
                );

                window.setTimeout(function () {
                    window.print();
                }, 50);
            }

            /*
            * Restore the interactive report after the browser
            * print dialog has been closed.
            */
            window.addEventListener(
                "afterprint",
                function () {
                    const printableReport =
                        document.querySelector(
                            "[data-basicanalysis-printable-report]"
                        );

                    document.body.classList.remove(
                        "basicanalysis-print-mode"
                    );

                    if (printableReport) {
                        printableReport.hidden = true;
                    }
                }
            );

            function preparePrintableEfficiencyTables(
                printableReport
            ) {
                if (!printableReport) {
                    return;
                }

                const tableCards = Array.from(
                    printableReport.querySelectorAll(
                        ".print-metric-results"
                    )
                );

                tableCards.forEach(function (card) {
                    const table =
                        card.querySelector(
                            ".efficiency-table"
                        );

                    if (!table) {
                        return;
                    }

                    /*
                    * Apply the same presentation rule used
                    * by PNG exports:
                    *
                    *   [T1], [T2], ... are useful in the
                    *   interactive report but are omitted
                    *   from publication-oriented output.
                    */
                    prepareTableForExport(
                        table
                    );

                    card.classList.add(
                        "print-export-style"
                    );
                });
            }


            async function renderEfficiencyTableToCanvas(
                tableCard,
                scale = null
            ) {
                if (!tableCard) {
                    return null;
                }

                if (
                    typeof window.html2canvas
                    === "undefined"
                ) {
                    throw new Error(
                        "PNG export is not available because "
                        + "html2canvas could not be loaded."
                    );
                }

                return window.html2canvas(
                    tableCard,
                    {
                        backgroundColor: "#ffffff",

                        scale:
                            scale !== null
                                ? scale
                                : Math.max(
                                    2,
                                    window.devicePixelRatio || 1
                                ),

                        useCORS: true,

                        logging: false
                    }
                );
            }


            async function renderEfficiencyTableToPngBlob(
                tableCard,
                scale = null
            ) {
                const canvas =
                    await renderEfficiencyTableToCanvas(
                        tableCard,
                        scale
                    );

                if (!canvas) {
                    return null;
                }

                return canvasToPngBlob(
                    canvas
                );
            }


            async function exportEfficiencyTableAsPng(tableCard) {
                if (!tableCard) {
                    return;
                }

                const exportName =
                    tableCard.dataset.exportName
                    || "efficiency-table";

                try {
                    const blob =
                        await renderEfficiencyTableToPngBlob(
                            tableCard
                        );

                    downloadBlob(
                        blob,
                        "basicanalysis-"
                            + safeExportFilename(exportName)
                            + ".png"
                    );

                } catch (error) {
                    console.error(
                        "BasicAnalysis PNG export failed:",
                        error
                    );

                    window.alert(
                        "The efficiency table could not "
                        + "be exported as PNG."
                    );
                }
            }

            async function exportCurrentEfficiencyTable() {
                /*
                * Execution Domains is presented interactively as
                * two tables but exported as one Host + Device table.
                */
                if (
                    activePrimaryId
                    === "execution-domains"
                ) {
                    setExportMenuOpen(false);
                    setExportBusy(true, "Preparing PNG...");

                    try {
                        await exportExecutionDomainsAsPng();
                    } finally {
                        setExportBusy(false);
                    }

                    return;
                }

                /*
                * When a Runtime Analysis drilldown is open, it is
                * the analyst's current detailed analysis. Export
                * that table rather than the Parallel Runtime Model
                * table that remains visible beside it.
                */
                const drilldownTable =
                    activeDrilldownEfficiencyTable();

                if (drilldownTable) {
                    setExportMenuOpen(false);
                    setExportBusy(true, "Preparing PNG...");

                    try {
                        await exportSingleEfficiencyTableAsPng(
                            drilldownTable,
                            runtimeAnalysisExportName()
                        );
                    } finally {
                        setExportBusy(false);
                    }

                    return;
                }

                /*
                * Normal primary views contain one exportable
                * efficiency table.
                */
                const tables =
                    visibleEfficiencyTables();

                if (tables.length === 0) {
                    window.alert(
                        "No efficiency table is currently visible."
                    );

                    return;
                }

                if (tables.length > 1) {
                    window.alert(
                        "More than one efficiency table is currently visible."
                    );

                    return;
                }

                setExportMenuOpen(false);
                setExportBusy(true, "Preparing PNG...");

                try {
                    await exportSingleEfficiencyTableAsPng(
                        tables[0]
                    );
                } finally {
                    setExportBusy(false);
                }
            }

            function prepareTableForExport(table) {
                if (!table) {
                    return;
                }

                const headerCells = table.querySelectorAll(
                    "thead th:not(.metric-column-header)"
                );

                headerCells.forEach(function (cell) {
                    cell.textContent =
                        cell.textContent.replace(
                            /\s*\[T\d+\]\s*$/,
                            ""
                        );
                });
            }

            function appendExportFooter(
                exportCard,
                columnDescription
            ) {
                if (
                    !exportCard
                    || !columnDescription
                ) {
                    return;
                }

                const footer =
                    document.createElement("div");

                footer.className =
                    "export-table-footer";

                footer.textContent =
                    "Columns: " + columnDescription;

                exportCard.appendChild(
                    footer
                );
            }

            function buildCombinedExecutionDomainsExport() {
                const hostCard = root.querySelector(
                    '[data-export-group="execution-domains"]'
                    + '[data-export-domain="host"]'
                );

                const deviceCard = root.querySelector(
                    '[data-export-group="execution-domains"]'
                    + '[data-export-domain="device"]'
                );

                if (!hostCard || !deviceCard) {
                    return null;
                }

                const hostTable = hostCard.querySelector(
                    ".efficiency-table"
                );

                const deviceTable = deviceCard.querySelector(
                    ".efficiency-table"
                );

                if (!hostTable || !deviceTable) {
                    return null;
                }

                const exportCard = document.createElement("div");

                exportCard.className =
                    "metric-table-card export-combined-efficiency-table";

                exportCard.dataset.exportName =
                    "execution-domains";

                const wrapper = document.createElement("div");

                wrapper.className =
                    "efficiency-table-wrapper";

                /*
                * Start from the Host table so we preserve exactly
                * the existing header and table styling.
                */
                const combinedTable =
                    hostTable.cloneNode(true);

                prepareTableForExport(
                    combinedTable
                );

                const combinedBody =
                    combinedTable.querySelector("tbody");

                const deviceBody =
                    deviceTable.querySelector("tbody");

                if (!combinedBody || !deviceBody) {
                    return null;
                }

                const deviceRows = Array.from(
                    deviceBody.children
                );

                deviceRows.forEach(function (row, index) {
                    const clonedRow =
                        row.cloneNode(true);

                    if (index === 0) {
                        clonedRow.classList.add(
                            "export-device-start"
                        );
                    }

                    combinedBody.appendChild(
                        clonedRow
                    );
                });

                wrapper.appendChild(combinedTable);
                exportCard.appendChild(wrapper);

                appendExportFooter(
                    exportCard,
                    hostCard.dataset.exportColumns || ""
                );

                return exportCard;
            }

            function buildTemporaryEfficiencyTableExport(sourceCard, exportName = null) {
                if (!sourceCard) {
                    return null;
                }

                const sourceTable = sourceCard.querySelector(
                    ".efficiency-table"
                );

                if (!sourceTable) {
                    return null;
                }

                const exportCard = document.createElement("div");

                exportCard.className =
                    "metric-table-card export-temporary-efficiency-table";

                exportCard.dataset.exportName =
                    exportName
                    || sourceCard.dataset.exportName
                    || "efficiency-table";

                const wrapper = document.createElement("div");

                wrapper.className =
                    "efficiency-table-wrapper";

                const clonedTable =
                    sourceTable.cloneNode(true);

                prepareTableForExport(
                    clonedTable
                );

                wrapper.appendChild(
                    clonedTable
                );

                exportCard.appendChild(
                    wrapper
                );

                appendExportFooter(
                    exportCard,
                    sourceCard.dataset.exportColumns || ""
                );

                return exportCard;
            }         

            async function exportTemporaryCardAsPng(exportCard) {
                if (!exportCard) {
                    return;
                }

                exportCard.style.position = "fixed";
                exportCard.style.left = "-100000px";
                exportCard.style.top = "0";
                exportCard.style.zIndex = "-1";

                /*
                * Let the temporary element use its intrinsic
                * table width instead of the report-panel width.
                */
                exportCard.style.width = "max-content";
                exportCard.style.maxWidth = "none";

                document.body.appendChild(
                    exportCard
                );

                try {
                    await exportEfficiencyTableAsPng(
                        exportCard
                    );
                } finally {
                    exportCard.remove();
                }
            }

            async function renderTemporaryCardToPngBlob(
                exportCard,
                scale = null
            ) {
                if (!exportCard) {
                    return null;
                }

                exportCard.style.position = "fixed";
                exportCard.style.left = "-100000px";
                exportCard.style.top = "0";
                exportCard.style.zIndex = "-1";

                exportCard.style.width = "max-content";
                exportCard.style.maxWidth = "none";

                document.body.appendChild(
                    exportCard
                );

                try {
                    return await renderEfficiencyTableToPngBlob(
                        exportCard,
                        scale
                    );
                } finally {
                    exportCard.remove();
                }
            }


            async function buildCombinedZipExportSurface(
                allCards,
                usedNames
            ) {
                if (!allCards || allCards.length === 0) {
                    return null;
                }

                const exportSurface =
                    document.createElement("div");

                exportSurface.className =
                    "zip-export-surface";

                exportSurface.style.position = "fixed";
                exportSurface.style.left = "-100000px";
                exportSurface.style.top = "0";
                exportSurface.style.zIndex = "-1";

                exportSurface.style.width = "max-content";
                exportSurface.style.maxWidth = "none";

                exportSurface.style.display = "flex";
                exportSurface.style.flexDirection = "column";
                exportSurface.style.alignItems = "flex-start";
                exportSurface.style.gap = "24px";

                const entries = [];

                /*
                * Add every normal logical efficiency table.
                *
                * Host and Device are excluded because Execution
                * Domains is exported separately as one combined table.
                */
                const normalCards =
                    allCards.filter(
                        function (card) {
                            return (
                                card.dataset.exportGroup
                                !== "execution-domains"
                            );
                        }
                    );

                normalCards.forEach(function (sourceCard) {
                    const exportCard =
                        buildTemporaryEfficiencyTableExport(
                            sourceCard
                        );

                    if (!exportCard) {
                        return;
                    }

                    exportCard.style.position = "static";
                    exportCard.style.width = "max-content";
                    exportCard.style.maxWidth = "none";

                    const filename =
                        allocateUniqueExportFilename(
                            sourceCard.dataset.exportName
                            || "efficiency-table",
                            usedNames
                        );

                    exportSurface.appendChild(
                        exportCard
                    );

                    entries.push({
                        card: exportCard,
                        filename: filename
                    });
                });

                /*
                * Add Execution Domains as its combined
                * Host + Device table.
                */
                const hasExecutionDomains =
                    allCards.some(
                        function (card) {
                            return (
                                card.dataset.exportGroup
                                === "execution-domains"
                            );
                        }
                    );

                if (hasExecutionDomains) {
                    const executionDomainsCard =
                        buildCombinedExecutionDomainsExport();

                    if (executionDomainsCard) {
                        executionDomainsCard.style.position =
                            "static";

                        executionDomainsCard.style.width =
                            "max-content";

                        executionDomainsCard.style.maxWidth =
                            "none";

                        const filename =
                            allocateUniqueExportFilename(
                                "execution-domains",
                                usedNames
                            );

                        exportSurface.appendChild(
                            executionDomainsCard
                        );

                        entries.push({
                            card: executionDomainsCard,
                            filename: filename
                        });
                    }
                }

                if (!entries.length) {
                    return null;
                }

                document.body.appendChild(
                    exportSurface
                );

                /*
                * Wait until the browser has computed the layout.
                */
                await new Promise(function (resolve) {
                    window.requestAnimationFrame(
                        function () {
                            resolve();
                        }
                    );
                });

                const surfaceBounds =
                    exportSurface.getBoundingClientRect();

                /*
                * Store each table location relative to the
                * complete export surface.
                */
                entries.forEach(function (entry) {
                    const bounds =
                        entry.card.getBoundingClientRect();

                    entry.x =
                        bounds.left - surfaceBounds.left;

                    entry.y =
                        bounds.top - surfaceBounds.top;

                    entry.width =
                        bounds.width;

                    entry.height =
                        bounds.height;
                });

                return {
                    surface: exportSurface,
                    entries: entries,
                    width: surfaceBounds.width,
                    height: surfaceBounds.height
                };
            }            

            async function cropCanvasRegionToPngBlob(
                sourceCanvas,
                entry,
                scaleX,
                scaleY
            ) {
                /*
                * Use floor/ceil rather than simple rounding so
                * table borders are not clipped at fractional
                * browser coordinates.
                */
                const sourceX =
                    Math.floor(
                        entry.x * scaleX
                    );

                const sourceY =
                    Math.floor(
                        entry.y * scaleY
                    );

                const sourceRight =
                    Math.ceil(
                        (entry.x + entry.width)
                        * scaleX
                    );

                const sourceBottom =
                    Math.ceil(
                        (entry.y + entry.height)
                        * scaleY
                    );

                const sourceWidth =
                    sourceRight - sourceX;

                const sourceHeight =
                    sourceBottom - sourceY;

                const cropCanvas =
                    document.createElement("canvas");

                cropCanvas.width =
                    sourceWidth;

                cropCanvas.height =
                    sourceHeight;

                const context =
                    cropCanvas.getContext("2d");

                if (!context) {
                    throw new Error(
                        "The PNG crop canvas could not be created."
                    );
                }

                context.drawImage(
                    sourceCanvas,

                    sourceX,
                    sourceY,
                    sourceWidth,
                    sourceHeight,

                    0,
                    0,
                    sourceWidth,
                    sourceHeight
                );

                return canvasToPngBlob(
                    cropCanvas
                );
            }

            async function addCombinedEfficiencyTablesToZip(
                zip,
                allCards,
                usedNames
            ) {
                const combinedExport =
                    await buildCombinedZipExportSurface(
                        allCards,
                        usedNames
                    );

                if (!combinedExport) {
                    return;
                }

                const exportSurface =
                    combinedExport.surface;

                try {
                    /*
                    * Render all logical tables with one
                    * html2canvas invocation.
                    */
                    const combinedCanvas =
                        await renderEfficiencyTableToCanvas(
                            exportSurface,
                            1.5
                        );

                    if (!combinedCanvas) {
                        return;
                    }

                    /*
                    * Derive the effective raster scale from the
                    * actual canvas instead of assuming that it
                    * is exactly 1.5.
                    */
                    const scaleX =
                        combinedCanvas.width
                        / combinedExport.width;

                    const scaleY =
                        combinedCanvas.height
                        / combinedExport.height;

                    /*
                    * Cropping is inexpensive compared with
                    * html2canvas, so process the regions
                    * sequentially for simple deterministic
                    * behavior.
                    */
                    for (const entry of combinedExport.entries) {
                        const blob =
                            await cropCanvasRegionToPngBlob(
                                combinedCanvas,
                                entry,
                                scaleX,
                                scaleY
                            );

                        if (!blob) {
                            continue;
                        }

                        zip.file(
                            entry.filename,
                            blob
                        );
                    }

                } finally {
                    exportSurface.remove();
                }
            }

            async function exportAllEfficiencyTablesAsZip() {
                setExportMenuOpen(false);

                if (
                    typeof window.JSZip
                    === "undefined"
                ) {
                    window.alert(
                        "ZIP export is not available because "
                        + "the ZIP library could not be loaded."
                    );

                    return;
                }

                const allCards = Array.from(
                    root.querySelectorAll(
                        "[data-efficiency-export]"
                    )
                );

                if (allCards.length === 0) {
                    window.alert(
                        "No efficiency tables are available "
                        + "for export."
                    );

                    return;
                }

                
                setExportBusy(true, "Preparing ZIP...");

                try {
                    /*
                    * Export every normal logical table.
                    *
                    * Host and Device are skipped here because
                    * Execution Domains is exported separately
                    * as one combined table.
                    */

                    const zip =
                        new window.JSZip();

                    const usedNames =
                        new Set();

                    await addCombinedEfficiencyTablesToZip(
                        zip,
                        allCards,
                        usedNames
                    );

                    /*
                    * Create one downloadable archive.
                    */

                    const zipBlob =
                        await zip.generateAsync({
                            type: "blob"
                        });

                    downloadBlob(
                        zipBlob,
                        "basicanalysis-efficiency-tables.zip"
                    );


                } catch (error) {
                    console.error(
                        "BasicAnalysis ZIP export failed:",
                        error
                    );

                    window.alert(
                        "The efficiency tables could not "
                        + "be exported as a ZIP file."
                    );
                } finally {
                    setExportBusy(false);
                }

            }

            async function exportExecutionDomainsAsPng() {
                const exportCard =
                    buildCombinedExecutionDomainsExport();

                if (!exportCard) {
                    window.alert(
                        "The Host and Device efficiency tables "
                        + "could not be prepared for export."
                    );

                    return;
                }

                await exportTemporaryCardAsPng(
                    exportCard
                );
            }

            async function exportSingleEfficiencyTableAsPng(
                sourceCard,
                exportName = null
            ) {
                const exportCard =
                    buildTemporaryEfficiencyTableExport(
                        sourceCard,
                        exportName
                    );

                if (!exportCard) {
                    window.alert(
                        "The efficiency table could not be "
                        + "prepared for export."
                    );

                    return;
                }

                await exportTemporaryCardAsPng(
                    exportCard
                );
            }

            function buildCombinedRuntimeAnalysisExport() {
                const primaryCard =
                    primaryEfficiencyTable();

                const drilldownCard =
                    activeDrilldownEfficiencyTable();

                if (!primaryCard || !drilldownCard) {
                    return null;
                }

                const primaryTable =
                    primaryCard.querySelector(
                        ".efficiency-table"
                    );

                const drilldownTable =
                    drilldownCard.querySelector(
                        ".efficiency-table"
                    );

                if (!primaryTable || !drilldownTable) {
                    return null;
                }

                const exportCard =
                    document.createElement("div");

                exportCard.className =
                    "export-runtime-combined";

                exportCard.dataset.exportName =
                    "parallel-runtime-model-"
                    + runtimeAnalysisExportName();

                /*
                * Parallel Runtime Model table.
                */
                const primaryWrapper =
                    document.createElement("div");

                primaryWrapper.className =
                    "metric-table-card "
                    + "export-temporary-efficiency-table";

                const primaryTableWrapper =
                    document.createElement("div");

                primaryTableWrapper.className =
                    "efficiency-table-wrapper";

                const clonedPrimaryTable =
                    primaryTable.cloneNode(true);

                prepareTableForExport(
                    clonedPrimaryTable
                );

                primaryTableWrapper.appendChild(
                    clonedPrimaryTable
                );

                primaryWrapper.appendChild(
                    primaryTableWrapper
                );

                exportCard.appendChild(
                    primaryWrapper
                );

                /*
                * Runtime Analysis table.
                */
                const drilldownWrapper =
                    document.createElement("div");

                drilldownWrapper.className =
                    "metric-table-card "
                    + "export-temporary-efficiency-table "
                    + "export-runtime-detail";

                const drilldownTableWrapper =
                    document.createElement("div");

                drilldownTableWrapper.className =
                    "efficiency-table-wrapper";

                const clonedDrilldownTable =
                    drilldownTable.cloneNode(true);

                prepareTableForExport(
                    clonedDrilldownTable
                );

                drilldownTableWrapper.appendChild(
                    clonedDrilldownTable
                );

                drilldownWrapper.appendChild(
                    drilldownTableWrapper
                );

                exportCard.appendChild(
                    drilldownWrapper
                );

                appendExportFooter(
                    exportCard,
                    primaryCard.dataset.exportColumns || ""
                );

                return exportCard;
            }

            async function exportVisibleRuntimeTablesAsPng() {
                const exportCard =
                    buildCombinedRuntimeAnalysisExport();

                if (!exportCard) {
                    window.alert(
                        "The Parallel Runtime Model and Runtime "
                        + "Analysis tables could not be prepared "
                        + "for export."
                    );

                    return;
                }

                setExportMenuOpen(false);
                setExportBusy(true, "Preparing PNG...");

                try {
                    await exportTemporaryCardAsPng(
                        exportCard
                    );
                } finally {
                    setExportBusy(false);
                }                
            }

            function runtimeAnalysisExportName() {
                if (!activeDrilldownId) {
                    return "runtime-analysis";
                }

                const selectedButton = drilldownButtons.find(
                    function (button) {
                        return (
                            button.dataset.guidedDrilldownTarget
                            === activeDrilldownId
                        );
                    }
                );

                if (!selectedButton) {
                    return activeDrilldownId;
                }

                const runtimeName =
                    selectedButton.textContent
                        .trim()
                        .toLowerCase();

                return runtimeName + "-runtime-analysis";
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

            function setExportMenuOpen(isOpen) {
                if (!exportMenu || !exportButton) {
                    return;
                }

                exportMenu.hidden = !isOpen;

                exportButton.setAttribute(
                    "aria-expanded",
                    isOpen ? "true" : "false"
                );

                exportControl.classList.toggle(
                    "is-open",
                    isOpen
                );
            }

            function setExportBusy(isBusy, message = "") {
                const exportOptions = root.querySelectorAll(
                    ".guided-export-option"
                );

                exportOptions.forEach(function (button) {
                    button.disabled = isBusy;
                });

                if (exportButton) {
                    exportButton.disabled = isBusy;

                    exportButton.setAttribute(
                        "aria-busy",
                        isBusy ? "true" : "false"
                    );
                }

                if (exportStatus) {
                    exportStatus.hidden = !isBusy;
                    exportStatus.textContent =
                        isBusy
                            ? message || "Preparing export..."
                            : "";
                }
            }

            function updateExportOptions() {
                const isParallelRuntimeModel =
                    activePrimaryId === "parallel-runtime-model";

                const hasRuntimeAnalysis =
                    (
                        isParallelRuntimeModel
                        && Boolean(activeDrilldownId)
                    );

                if (exportCurrentPngButton) {
                    exportCurrentPngButton.hidden =
                        isParallelRuntimeModel;
                }

                if (exportApplicationPngButton) {
                    exportApplicationPngButton.hidden =
                        !isParallelRuntimeModel;
                }

                if (exportPrimaryPngButton) {
                    exportPrimaryPngButton.hidden =
                        !isParallelRuntimeModel;
                }

                if (exportDrilldownPngButton) {
                    exportDrilldownPngButton.hidden =
                        !hasRuntimeAnalysis;

                    if (hasRuntimeAnalysis) {
                        const runtimeName =
                            activeRuntimeName();

                        exportDrilldownPngButton.textContent =
                            runtimeName
                                ? runtimeName
                                    + " Runtime Analysis table (PNG)"
                                : "Runtime Analysis table (PNG)";
                    }
                }

                if (exportVisiblePngButton) {
                    exportVisiblePngButton.hidden =
                        !hasRuntimeAnalysis;
                }
            }

            function toggleExportMenu() {
                if (!exportMenu) {
                    return;
                }

                setSplitMenuOpen(false);

                updateExportOptions();

                setExportMenuOpen(
                    exportMenu.hidden
                );
            }


            async function exportApplicationEfficiencyTable() {
                const table =
                    prmApplicationEfficiencyTable();

                if (!table) {
                    window.alert(
                        "The Application Efficiency table "
                        + "is not available."
                    );

                    return;
                }

                setExportMenuOpen(false);
                setExportBusy(true, "Preparing PNG...");

                try {
                    await exportSingleEfficiencyTableAsPng(
                        table,
                        "application-efficiency"
                    );
                } finally {
                    setExportBusy(false);
                }
            }

            async function exportPrimaryEfficiencyTable() {
                const table =
                    primaryEfficiencyTable();

                if (!table) {
                    window.alert(
                        "The Parallel Runtime Model efficiency "
                        + "table is not available."
                    );

                    return;
                }

                setExportMenuOpen(false);
                setExportBusy(true, "Preparing PNG...");

                try {
                    await exportSingleEfficiencyTableAsPng(
                        table,
                        "parallel-runtime-model"
                    );
                } finally {
                    setExportBusy(false);
                }                
            }

            async function exportDrilldownEfficiencyTable() {
                const table =
                    activeDrilldownEfficiencyTable();

                if (!table) {
                    window.alert(
                        "The selected Runtime Analysis efficiency "
                        + "table is not available."
                    );

                    return;
                }

                setExportMenuOpen(false);
                setExportBusy(true, "Preparing PNG...");

                try {
                    await exportSingleEfficiencyTableAsPng(
                        table,
                        runtimeAnalysisExportName()
                    );
                } finally {
                    setExportBusy(false);
                }                    
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

                setExportMenuOpen(false);

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

            if (exportButton) {
                exportButton.addEventListener(
                    "click",
                    function (event) {
                        event.stopPropagation();
                        toggleExportMenu();
                    }
                );
            }

            if (exportCurrentPngButton) {
                exportCurrentPngButton.addEventListener(
                    "click",
                    function (event) {
                        event.stopPropagation();

                        exportCurrentEfficiencyTable();
                    }
                );
            }

            if (exportApplicationPngButton) {
                exportApplicationPngButton.addEventListener(
                    "click",
                    function (event) {
                        event.stopPropagation();

                        exportApplicationEfficiencyTable();
                    }
                );
            }

            if (exportPrimaryPngButton) {
                exportPrimaryPngButton.addEventListener(
                    "click",
                    function (event) {
                        event.stopPropagation();

                        exportPrimaryEfficiencyTable();
                    }
                );
            }


            if (exportDrilldownPngButton) {
                exportDrilldownPngButton.addEventListener(
                    "click",
                    function (event) {
                        event.stopPropagation();

                        exportDrilldownEfficiencyTable();
                    }
                );
            }


            if (exportVisiblePngButton) {
                exportVisiblePngButton.addEventListener(
                    "click",
                    function (event) {
                        event.stopPropagation();

                        exportVisibleRuntimeTablesAsPng();
                    }
                );
            }

            if (exportAllPngButton) {
                exportAllPngButton.addEventListener(
                    "click",
                    function (event) {
                        event.stopPropagation();

                        exportAllEfficiencyTablesAsZip();
                    }
                );
            }

            if (exportPdfButton) {
                exportPdfButton.addEventListener(
                    "click",
                    function (event) {
                        event.stopPropagation();

                        printEmbeddedReport();
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

                    if (
                        exportControl
                        && !exportControl.contains(event.target)
                    ) {
                        setExportMenuOpen(false);
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