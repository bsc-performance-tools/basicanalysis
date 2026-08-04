"""HTML renderer for the two-panel analysis comparison workspace."""

from __future__ import annotations

import html

from typing import Dict, Optional, Sequence, Tuple

from .analysis_catalogue import (
    AnalysisCatalogue,
    AnalysisCatalogueView,
)


_GROUP_ORDER = (
    "assessment",
    "runtime",
    "domain",
)


_GROUP_LABELS = {
    "assessment": "Performance assessment",
    "runtime": "Runtime analysis",
    "domain": "Execution domains",
}


def _safe_dom_id(value: str) -> str:
    """Return a stable HTML-safe identifier."""

    characters = []

    for character in str(value):
        if character.isalnum():
            characters.append(
                character.lower()
            )
        else:
            characters.append("-")

    normalized = "".join(
        characters
    ).strip("-")

    while "--" in normalized:
        normalized = normalized.replace(
            "--",
            "-",
        )

    return normalized or "analysis-view"


def _validate_catalogue(
    catalogue: AnalysisCatalogue,
) -> None:
    """Validate the minimum catalogue required by the workspace."""

    if not isinstance(
        catalogue,
        AnalysisCatalogue,
    ):
        raise TypeError(
            "The comparison workspace requires an AnalysisCatalogue."
        )

    if not catalogue.views:
        raise ValueError(
            "The comparison workspace requires at least one analysis view."
        )

    view_ids = [
        view.view_id
        for view in catalogue.views
    ]

    if len(view_ids) != len(set(view_ids)):
        raise ValueError(
            "Analysis catalogue view identifiers must be unique."
        )


def _group_views(
    views: Sequence[AnalysisCatalogueView],
) -> Tuple[
    Tuple[str, Tuple[AnalysisCatalogueView, ...]],
    ...,
]:
    """Group catalogue views in stable analytical order."""

    grouped = []

    known_groups = set()

    for group_name in _GROUP_ORDER:
        group_views = tuple(
            view
            for view in views
            if view.group == group_name
        )

        if group_views:
            grouped.append(
                (
                    group_name,
                    group_views,
                )
            )
            known_groups.add(
                group_name
            )

    extra_groups = []

    for view in views:
        if (
            view.group not in known_groups
            and view.group not in extra_groups
        ):
            extra_groups.append(
                view.group
            )

    for group_name in extra_groups:
        group_views = tuple(
            view
            for view in views
            if view.group == group_name
        )

        grouped.append(
            (
                group_name,
                group_views,
            )
        )

    return tuple(
        grouped
    )


def _select_default_view_id(
    catalogue: AnalysisCatalogue,
    preferred_id: str,
    excluded_id: Optional[str] = None,
) -> str:
    """Resolve one valid default view."""

    preferred = catalogue.get_view(
        preferred_id
    )

    if (
        preferred is not None
        and preferred.view_id != excluded_id
    ):
        return preferred.view_id

    for view in catalogue.views:
        if view.view_id != excluded_id:
            return view.view_id

    return catalogue.views[0].view_id


def _resolve_defaults(
    catalogue: AnalysisCatalogue,
    left_view_id: str,
    right_view_id: str,
) -> Tuple[str, str]:
    """Resolve valid initial views for both comparison panels."""

    left = _select_default_view_id(
        catalogue=catalogue,
        preferred_id=left_view_id,
    )

    right = _select_default_view_id(
        catalogue=catalogue,
        preferred_id=right_view_id,
        excluded_id=left,
    )

    return (
        left,
        right,
    )


def _render_selector_options(
    catalogue: AnalysisCatalogue,
    selected_view_id: str,
) -> str:
    """Render grouped options for one panel selector."""

    lines = []

    for group_name, group_views in _group_views(
        catalogue.views
    ):
        group_label = _GROUP_LABELS.get(
            group_name,
            group_name.replace(
                "-",
                " ",
            ).title(),
        )

        lines.append(
            '<optgroup label="{}">'.format(
                html.escape(
                    group_label,
                    quote=True,
                )
            )
        )

        for view in group_views:
            selected = (
                " selected"
                if view.view_id == selected_view_id
                else ""
            )

            lines.append(
                (
                    '<option value="{view_id}"{selected}>'
                    "{label}"
                    "</option>"
                ).format(
                    view_id=html.escape(
                        view.view_id,
                        quote=True,
                    ),
                    selected=selected,
                    label=html.escape(
                        view.label
                    ),
                )
            )

        lines.append("</optgroup>")

    return "\n".join(
        lines
    )


def _render_panel_views(
    catalogue: AnalysisCatalogue,
    panel_id: str,
    selected_view_id: str,
) -> str:
    """Pre-render all catalogue views for one comparison panel."""

    lines = []

    for view in catalogue.views:
        safe_view_id = _safe_dom_id(
            view.view_id
        )

        is_selected = (
            view.view_id == selected_view_id
        )

        active_class = (
            " is-active"
            if is_selected
            else ""
        )

        hidden = (
            ""
            if is_selected
            else " hidden"
        )

        if view.body_html:
            body_html = view.body_html
        else:
            body_html = """
            <div class="comparison-view-unavailable">
                <h3>Analysis content unavailable</h3>
                <p>
                    The semantic analysis view is available, but no rendered
                    HTML body was provided.
                </p>
            </div>
            """.strip()

        lines.append(
            """
            <article
                id="{panel_id}-view-{safe_view_id}"
                class="comparison-analysis-view{active_class}"
                data-comparison-view-id="{view_id}"
                data-comparison-view-title="{title}"
                data-comparison-view-description="{description}"
                {hidden}
            >
                <div class="comparison-analysis-body">
                    {body_html}
                </div>
            </article>
            """.format(
                panel_id=html.escape(
                    panel_id,
                    quote=True,
                ),
                safe_view_id=html.escape(
                    safe_view_id,
                    quote=True,
                ),
                active_class=active_class,
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
                hidden=hidden,
                body_html=body_html,
            )
        )

    return "\n".join(
        lines
    )


def _render_panel(
    catalogue: AnalysisCatalogue,
    panel_id: str,
    panel_label: str,
    selected_view_id: str,
) -> str:
    """Render one independently selectable analysis panel."""

    selected_view = catalogue.get_view(
        selected_view_id
    )

    if selected_view is None:
        raise ValueError(
            "Unknown selected view {!r}.".format(
                selected_view_id
            )
        )

    return """
    <section
        class="comparison-panel"
        data-comparison-panel="{panel_id}"
        aria-label="{panel_label}"
    >
        <header class="comparison-panel-header">
            <div class="comparison-panel-heading">
                <p class="comparison-panel-eyebrow">
                    {panel_label}
                </p>

                <h2 data-comparison-panel-title>
                    {title}
                </h2>

                <p data-comparison-panel-description>
                    {description}
                </p>
            </div>

            <div class="comparison-panel-controls">
                <label
                    class="comparison-selector-label"
                    for="{panel_id}-selector"
                >
                    Analysis view
                </label>

                <select
                    id="{panel_id}-selector"
                    class="comparison-view-selector"
                    data-comparison-selector
                    aria-label="Select analysis for {panel_label}"
                >
                    {selector_options}
                </select>

                <button
                    type="button"
                    class="comparison-panel-control"
                    data-comparison-maximize
                    aria-pressed="false"
                    aria-label="Maximize {panel_label}"
                    title="Maximize panel"
                >
                    <span aria-hidden="true">⛶</span>
                </button>
            </div>
        </header>

        <div
            class="comparison-panel-content"
            data-comparison-panel-content
        >
            {panel_views}
        </div>
    </section>
    """.format(
        panel_id=html.escape(
            panel_id,
            quote=True,
        ),
        panel_label=html.escape(
            panel_label
        ),
        title=html.escape(
            selected_view.title
        ),
        description=html.escape(
            selected_view.description
        ),
        selector_options=_render_selector_options(
            catalogue=catalogue,
            selected_view_id=selected_view_id,
        ),
        panel_views=_render_panel_views(
            catalogue=catalogue,
            panel_id=panel_id,
            selected_view_id=selected_view_id,
        ),
    )


def _render_workspace_script() -> str:
    """Render comparison-panel interaction."""

    return """
    <script>
    (function () {
        "use strict";

        const workspaces = document.querySelectorAll(
            "[data-comparison-workspace]"
        );

        workspaces.forEach(function (workspace) {
            const panels = Array.from(
                workspace.querySelectorAll(
                    "[data-comparison-panel]"
                )
            );

            function resizeVisiblePlots(panel) {
                if (
                    typeof window.Plotly === "undefined"
                    || !panel
                ) {
                    return;
                }

                const plots = panel.querySelectorAll(
                    ".js-plotly-plot"
                );

                plots.forEach(function (plot) {
                    try {
                        window.Plotly.Plots.resize(
                            plot
                        );
                    } catch (error) {
                        // Non-Plotly views remain fully usable.
                    }
                });
            }

            function updatePanel(panel, viewId) {
                const views = Array.from(
                    panel.querySelectorAll(
                        "[data-comparison-view-id]"
                    )
                );

                let selectedView = null;

                views.forEach(function (view) {
                    const isSelected =
                        view.dataset.comparisonViewId === viewId;

                    view.hidden = !isSelected;

                    view.classList.toggle(
                        "is-active",
                        isSelected
                    );

                    if (isSelected) {
                        selectedView = view;
                    }
                });

                if (!selectedView) {
                    return;
                }

                const title = panel.querySelector(
                    "[data-comparison-panel-title]"
                );

                const description = panel.querySelector(
                    "[data-comparison-panel-description]"
                );

                if (title) {
                    title.textContent =
                        selectedView.dataset.comparisonViewTitle || "";
                }

                if (description) {
                    description.textContent =
                        selectedView.dataset.comparisonViewDescription || "";
                }

                const content = panel.querySelector(
                    "[data-comparison-panel-content]"
                );

                if (content) {
                    content.scrollTop = 0;
                    content.scrollLeft = 0;
                }

                window.requestAnimationFrame(function () {
                    resizeVisiblePlots(
                        selectedView
                    );
                });
            }

            panels.forEach(function (panel) {
                const selector = panel.querySelector(
                    "[data-comparison-selector]"
                );

                if (selector) {
                    selector.addEventListener(
                        "change",
                        function () {
                            updatePanel(
                                panel,
                                selector.value
                            );
                        }
                    );
                }

                const maximizeButton = panel.querySelector(
                    "[data-comparison-maximize]"
                );

                if (maximizeButton) {
                    maximizeButton.addEventListener(
                        "click",
                        function () {
                            const panelId =
                                panel.dataset.comparisonPanel;

                            const isMaximized =
                                workspace.dataset.maximizedPanel === panelId;

                            panels.forEach(function (candidate) {
                                candidate.classList.remove(
                                    "is-maximized"
                                );

                                candidate.classList.remove(
                                    "is-hidden-by-maximize"
                                );
                            });

                            if (isMaximized) {
                                delete workspace.dataset.maximizedPanel;

                                maximizeButton.setAttribute(
                                    "aria-pressed",
                                    "false"
                                );

                                maximizeButton.title =
                                    "Maximize panel";

                                maximizeButton.querySelector(
                                    "span"
                                ).textContent = "⛶";
                            } else {
                                workspace.dataset.maximizedPanel =
                                    panelId;

                                panels.forEach(function (candidate) {
                                    if (candidate === panel) {
                                        candidate.classList.add(
                                            "is-maximized"
                                        );
                                    } else {
                                        candidate.classList.add(
                                            "is-hidden-by-maximize"
                                        );
                                    }

                                    const button = candidate.querySelector(
                                        "[data-comparison-maximize]"
                                    );

                                    if (button) {
                                        const selected =
                                            candidate === panel;

                                        button.setAttribute(
                                            "aria-pressed",
                                            selected ? "true" : "false"
                                        );

                                        button.title = selected
                                            ? "Restore comparison"
                                            : "Maximize panel";

                                        button.querySelector(
                                            "span"
                                        ).textContent = selected
                                            ? "🗗"
                                            : "⛶";
                                    }
                                });
                            }

                            window.requestAnimationFrame(function () {
                                panels.forEach(function (candidate) {
                                    if (
                                        !candidate.classList.contains(
                                            "is-hidden-by-maximize"
                                        )
                                    ) {
                                        resizeVisiblePlots(
                                            candidate
                                        );
                                    }
                                });
                            });
                        }
                    );
                }
            });
        });
    }());
    </script>
    """.strip()


def render_comparison_workspace(
    catalogue: AnalysisCatalogue,
    left_view_id: str = "overview",
    right_view_id: str = "parallel-runtime-model",
) -> str:
    """Render two independently selectable analysis panels."""

    _validate_catalogue(
        catalogue
    )

    left_default, right_default = _resolve_defaults(
        catalogue=catalogue,
        left_view_id=left_view_id,
        right_view_id=right_view_id,
    )

    return """
    <section
        class="comparison-workspace"
        data-comparison-workspace
        aria-label="Performance analysis comparison"
    >
        <header class="comparison-workspace-header">
            <div>
                <p class="comparison-workspace-eyebrow">
                    Performance analysis
                </p>

                <h1>Compare analytical views</h1>

                <p>
                    Inspect complementary analyses side by side and correlate
                    their findings without losing the execution context.
                </p>
            </div>
        </header>

        <div class="comparison-panels">
            {left_panel}

            <div
                class="comparison-divider"
                aria-hidden="true"
            ></div>

            {right_panel}
        </div>
    </section>

    {workspace_script}
    """.format(
        left_panel=_render_panel(
            catalogue=catalogue,
            panel_id="comparison-left",
            panel_label="Analysis panel A",
            selected_view_id=left_default,
        ),
        right_panel=_render_panel(
            catalogue=catalogue,
            panel_id="comparison-right",
            panel_label="Analysis panel B",
            selected_view_id=right_default,
        ),
        workspace_script=_render_workspace_script(),
    )