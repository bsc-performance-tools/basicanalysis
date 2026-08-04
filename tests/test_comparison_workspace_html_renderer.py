"""Tests for the two-panel comparison workspace HTML renderer."""

import unittest

from report.renderer.html import (
    AnalysisCatalogue,
    AnalysisCatalogueView,
    render_comparison_workspace,
)


class ComparisonWorkspaceHtmlRendererTests(unittest.TestCase):
    """Validate comparison workspace structure and interaction."""

    # ------------------------------------------------------------------
    # Test data
    # ------------------------------------------------------------------

    @staticmethod
    def _view(
        view_id,
        label,
        title,
        group,
        description,
        body_html,
    ):
        return AnalysisCatalogueView(
            view_id=view_id,
            label=label,
            title=title,
            group=group,
            description=description,
            body_html=body_html,
        )

    def _full_catalogue(self):
        return AnalysisCatalogue(
            views=(
                self._view(
                    view_id="overview",
                    label="Overview",
                    title="Overview",
                    group="assessment",
                    description="Execution context and global metrics.",
                    body_html="<div id='overview-body'>Overview</div>",
                ),
                self._view(
                    view_id="parallel-runtime-model",
                    label="Parallel Runtime Model",
                    title="Parallel Runtime Model",
                    group="assessment",
                    description="Runtime contribution analysis.",
                    body_html="<div id='runtime-model-body'>Runtime</div>",
                ),
                self._view(
                    view_id="computation-scalability",
                    label="Computation Scalability",
                    title="Computation Scalability",
                    group="assessment",
                    description="Computation scaling analysis.",
                    body_html="<div id='scalability-body'>Scalability</div>",
                ),
                self._view(
                    view_id="mpi-runtime",
                    label="MPI",
                    title="MPI Runtime Analysis",
                    group="runtime",
                    description="MPI-specific analysis.",
                    body_html="<div id='mpi-body'>MPI</div>",
                ),
                self._view(
                    view_id="openmp-runtime",
                    label="OpenMP",
                    title="OpenMP Runtime Analysis",
                    group="runtime",
                    description="OpenMP-specific analysis.",
                    body_html="<div id='openmp-body'>OpenMP</div>",
                ),
                self._view(
                    view_id="accelerator-runtime",
                    label="CUDA",
                    title="CUDA Runtime Contribution",
                    group="runtime",
                    description="CUDA runtime contribution.",
                    body_html="<div id='cuda-body'>CUDA</div>",
                ),
                self._view(
                    view_id="host-analysis",
                    label="Host",
                    title="Host Execution Domain",
                    group="domain",
                    description="Host-side analysis.",
                    body_html="<div id='host-body'>Host</div>",
                ),
                self._view(
                    view_id="device-analysis",
                    label="Device",
                    title="Device Execution Domain",
                    group="domain",
                    description="Device-side analysis.",
                    body_html="<div id='device-body'>Device</div>",
                ),
            )
        )

    def _single_trace_catalogue(self):
        return AnalysisCatalogue(
            views=(
                self._view(
                    view_id="overview",
                    label="Overview",
                    title="Overview",
                    group="assessment",
                    description="Execution context and global metrics.",
                    body_html="<div id='overview-body'>Overview</div>",
                ),
                self._view(
                    view_id="parallel-runtime-model",
                    label="Parallel Runtime Model",
                    title="Parallel Runtime Model",
                    group="assessment",
                    description="Runtime contribution analysis.",
                    body_html="<div id='runtime-model-body'>Runtime</div>",
                ),
                self._view(
                    view_id="mpi-runtime",
                    label="MPI",
                    title="MPI Runtime Analysis",
                    group="runtime",
                    description="MPI-specific analysis.",
                    body_html="<div id='mpi-body'>MPI</div>",
                ),
            )
        )

    # ------------------------------------------------------------------
    # Basic structure
    # ------------------------------------------------------------------

    def test_renders_two_comparison_panels(self):
        rendered = render_comparison_workspace(
            self._full_catalogue()
        )

        self.assertIn(
            'data-comparison-panel="comparison-left"',
            rendered,
        )

        self.assertIn(
            'data-comparison-panel="comparison-right"',
            rendered,
        )

        self.assertEqual(
            rendered.count(
                'class="comparison-panel"'
            ),
            2,
        )

    def test_renders_workspace_header(self):
        rendered = render_comparison_workspace(
            self._full_catalogue()
        )

        self.assertIn(
            "Compare analytical views",
            rendered,
        )

        self.assertIn(
            "Inspect complementary analyses side by side",
            rendered,
        )

    def test_renders_divider_between_panels(self):
        rendered = render_comparison_workspace(
            self._full_catalogue()
        )

        self.assertIn(
            'class="comparison-divider"',
            rendered,
        )

    # ------------------------------------------------------------------
    # Default selections
    # ------------------------------------------------------------------

    def test_default_left_panel_is_overview(self):
        rendered = render_comparison_workspace(
            self._full_catalogue()
        )

        self.assertIn(
            '<option value="overview" selected>',
            rendered,
        )

        self.assertIn(
            'data-comparison-view-id="overview"',
            rendered,
        )

        self.assertIn(
            'class="comparison-analysis-view is-active"',
            rendered,
        )

    def test_default_right_panel_is_parallel_runtime_model(self):
        rendered = render_comparison_workspace(
            self._full_catalogue()
        )

        self.assertIn(
            '<option value="parallel-runtime-model" selected>',
            rendered,
        )

        self.assertIn(
            'data-comparison-view-id="parallel-runtime-model"',
            rendered,
        )

    def test_custom_defaults_are_respected(self):
        rendered = render_comparison_workspace(
            self._full_catalogue(),
            left_view_id="parallel-runtime-model",
            right_view_id="computation-scalability",
        )

        self.assertIn(
            '<option value="parallel-runtime-model" selected>',
            rendered,
        )

        self.assertIn(
            '<option value="computation-scalability" selected>',
            rendered,
        )

    def test_invalid_defaults_fall_back_to_available_views(self):
        rendered = render_comparison_workspace(
            self._single_trace_catalogue(),
            left_view_id="missing-left",
            right_view_id="missing-right",
        )

        self.assertIn(
            '<option value="overview" selected>',
            rendered,
        )

        self.assertIn(
            '<option value="parallel-runtime-model" selected>',
            rendered,
        )

    def test_default_panels_prefer_different_views(self):
        catalogue = AnalysisCatalogue(
            views=(
                self._view(
                    view_id="overview",
                    label="Overview",
                    title="Overview",
                    group="assessment",
                    description="Overview.",
                    body_html="<div>Overview</div>",
                ),
                self._view(
                    view_id="mpi-runtime",
                    label="MPI",
                    title="MPI",
                    group="runtime",
                    description="MPI.",
                    body_html="<div>MPI</div>",
                ),
            )
        )

        rendered = render_comparison_workspace(
            catalogue,
            left_view_id="overview",
            right_view_id="overview",
        )

        self.assertIn(
            '<option value="overview" selected>',
            rendered,
        )

        self.assertIn(
            '<option value="mpi-runtime" selected>',
            rendered,
        )

    # ------------------------------------------------------------------
    # Selector catalogue
    # ------------------------------------------------------------------

    def test_each_panel_contains_all_catalogue_views(self):
        rendered = render_comparison_workspace(
            self._full_catalogue()
        )

        for view_id in (
            "overview",
            "parallel-runtime-model",
            "computation-scalability",
            "mpi-runtime",
            "openmp-runtime",
            "accelerator-runtime",
            "host-analysis",
            "device-analysis",
        ):
            self.assertEqual(
                rendered.count(
                    'value="{}"'.format(
                        view_id
                    )
                ),
                2,
            )

    def test_selector_groups_are_rendered(self):
        rendered = render_comparison_workspace(
            self._full_catalogue()
        )

        self.assertEqual(
            rendered.count(
                '<optgroup label="Performance assessment">'
            ),
            2,
        )

        self.assertEqual(
            rendered.count(
                '<optgroup label="Runtime analysis">'
            ),
            2,
        )

        self.assertEqual(
            rendered.count(
                '<optgroup label="Execution domains">'
            ),
            2,
        )

    def test_single_trace_catalogue_omits_computation_scalability(self):
        rendered = render_comparison_workspace(
            self._single_trace_catalogue()
        )

        self.assertNotIn(
            'value="computation-scalability"',
            rendered,
        )

        self.assertNotIn(
            'data-comparison-view-id="computation-scalability"',
            rendered,
        )

    # ------------------------------------------------------------------
    # Pre-rendered content
    # ------------------------------------------------------------------

    def test_each_panel_prerenders_all_view_bodies(self):
        rendered = render_comparison_workspace(
            self._full_catalogue()
        )

        for body_id in (
            "overview-body",
            "runtime-model-body",
            "scalability-body",
            "mpi-body",
            "openmp-body",
            "cuda-body",
            "host-body",
            "device-body",
        ):
            self.assertEqual(
                rendered.count(
                    body_id
                ),
                2,
            )

    def test_missing_body_renders_unavailable_message(self):
        catalogue = AnalysisCatalogue(
            views=(
                self._view(
                    view_id="overview",
                    label="Overview",
                    title="Overview",
                    group="assessment",
                    description="Overview.",
                    body_html="",
                ),
            )
        )

        rendered = render_comparison_workspace(
            catalogue
        )

        self.assertEqual(
            rendered.count(
                "Analysis content unavailable"
            ),
            2,
        )

    def test_titles_and_descriptions_are_escaped(self):
        catalogue = AnalysisCatalogue(
            views=(
                self._view(
                    view_id="overview",
                    label="Overview",
                    title="<Unsafe title>",
                    group="assessment",
                    description='Description "with" <markup>.',
                    body_html="<div>Trusted rendered body</div>",
                ),
            )
        )

        rendered = render_comparison_workspace(
            catalogue
        )

        self.assertIn(
            "&lt;Unsafe title&gt;",
            rendered,
        )

        self.assertIn(
            "&lt;markup&gt;",
            rendered,
        )

        self.assertNotIn(
            'data-comparison-view-title="<Unsafe title>"',
            rendered,
        )

    # ------------------------------------------------------------------
    # Interaction
    # ------------------------------------------------------------------

    def test_renders_independent_selectors(self):
        rendered = render_comparison_workspace(
            self._full_catalogue()
        )

        self.assertIn(
            'id="comparison-left-selector"',
            rendered,
        )

        self.assertIn(
            'id="comparison-right-selector"',
            rendered,
        )

        self.assertEqual(
            rendered.count(
                'class="comparison-view-selector"'
            ),
            2,
        )

    def test_renders_maximize_control_for_each_panel(self):
        rendered = render_comparison_workspace(
            self._full_catalogue()
        )

        self.assertEqual(
            rendered.count(
                'class="comparison-panel-control"'
            ),
            2,
        )

        self.assertEqual(
            rendered.count(
                'aria-pressed="false"'
            ),
            2,
        )

        self.assertIn(
            "data-comparison-maximize",
            rendered,
        )

    def test_script_switches_panel_views_independently(self):
        rendered = render_comparison_workspace(
            self._full_catalogue()
        )

        self.assertIn(
            "function updatePanel(panel, viewId)",
            rendered,
        )

        self.assertIn(
            'selector.addEventListener(',
            rendered,
        )

        self.assertIn(
            '"change"',
            rendered,
        )

        self.assertIn(
            "updatePanel(",
            rendered,
        )

    def test_script_updates_title_and_description(self):
        rendered = render_comparison_workspace(
            self._full_catalogue()
        )

        self.assertIn(
            "data-comparison-panel-title",
            rendered,
        )

        self.assertIn(
            "data-comparison-panel-description",
            rendered,
        )

        self.assertIn(
            "selectedView.dataset.comparisonViewTitle",
            rendered,
        )

        self.assertIn(
            "selectedView.dataset.comparisonViewDescription",
            rendered,
        )

    def test_script_resizes_visible_plotly_content(self):
        rendered = render_comparison_workspace(
            self._full_catalogue()
        )

        self.assertIn(
            "function resizeVisiblePlots(panel)",
            rendered,
        )

        self.assertIn(
            "window.Plotly.Plots.resize",
            rendered,
        )

        self.assertIn(
            ".js-plotly-plot",
            rendered,
        )

    def test_script_supports_maximize_and_restore(self):
        rendered = render_comparison_workspace(
            self._full_catalogue()
        )

        self.assertIn(
            "workspace.dataset.maximizedPanel",
            rendered,
        )

        self.assertIn(
            "is-maximized",
            rendered,
        )

        self.assertIn(
            "is-hidden-by-maximize",
            rendered,
        )

        self.assertIn(
            "Restore comparison",
            rendered,
        )

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def test_rejects_non_catalogue_argument(self):
        with self.assertRaises(TypeError):
            render_comparison_workspace(
                []
            )

    def test_rejects_empty_catalogue(self):
        with self.assertRaises(ValueError):
            render_comparison_workspace(
                AnalysisCatalogue(
                    views=()
                )
            )

    def test_rejects_duplicate_view_ids(self):
        duplicate_view = self._view(
            view_id="overview",
            label="Overview",
            title="Overview",
            group="assessment",
            description="Overview.",
            body_html="<div>Overview</div>",
        )

        catalogue = AnalysisCatalogue(
            views=(
                duplicate_view,
                duplicate_view,
            )
        )

        with self.assertRaises(ValueError):
            render_comparison_workspace(
                catalogue
            )


if __name__ == "__main__":
    unittest.main(
        verbosity=2
    )