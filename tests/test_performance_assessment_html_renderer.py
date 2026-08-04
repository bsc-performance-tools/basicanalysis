"""Tests for the interactive Performance Assessment HTML renderer."""

import unittest

from report import build_analysis_context, build_report_model

from report.renderer.html import (
    AnalysisView,
    build_analysis_views,
    render_analysis_selector,
    render_performance_assessment,
    render_secondary_panel,
)


class PerformanceAssessmentHtmlRendererTests(unittest.TestCase):
    """Validate interactive Performance Assessment composition."""

    def _mpi_report_data(self):
        trace = "/tmp/mpi.prv"

        return {
            "general": {
                "analysis_kind": "simple",
                "pop_model": "classic",
            },
            "traces": [
                {
                    "id": 1,
                    "name": "mpi.prv",
                    "path": trace,
                    "mode": "Detailed+MPI",
                    "processes": 4,
                    "tasks": 4,
                    "threads": 1,
                    "devices": 0,
                    "gpu_streams": 0,
                    "gpu_streams_per_rank": 0,
                },
            ],
            "resources": [],
            "metrics": {
                "kind": "simple",
                "mod_factors": {
                    "global_eff": {
                        trace: 90.0,
                    },
                    "parallel_eff": {
                        trace: 90.0,
                    },
                    "load_balance": {
                        trace: 95.0,
                    },
                    "comm_eff": {
                        trace: 94.74,
                    },
                    "comp_scale": {
                        trace: 100.0,
                    },
                    "ipc_scale": {
                        trace: 100.0,
                    },
                    "inst_scale": {
                        trace: 100.0,
                    },
                    "freq_scale": {
                        trace: 100.0,
                    },
                    "serial_eff": {
                        trace: 97.0,
                    },
                    "transfer_eff": {
                        trace: 97.67,
                    },
                },
                "other_metrics": {},
            },
            "diagnosis": [],
            "evidence": [],
        }

    def _mpi_openmp_report_data(self):
        trace = "/tmp/mpi_openmp.prv"

        return {
            "general": {
                "analysis_kind": "hybrid",
                "pop_model": "classic",
            },
            "traces": [
                {
                    "id": 1,
                    "name": "mpi_openmp.prv",
                    "path": trace,
                    "mode": "Detailed+MPI+OpenMP",
                    "processes": 16,
                    "tasks": 4,
                    "threads": 4,
                    "devices": 0,
                    "gpu_streams": 0,
                    "gpu_streams_per_rank": 0,
                },
            ],
            "resources": [],
            "metrics": {
                "kind": "hybrid",
                "mod_factors": {
                    "global_eff": {
                        trace: 72.0,
                    },
                    "parallel_eff": {
                        trace: 72.0,
                    },
                    "load_balance": {
                        trace: 86.0,
                    },
                    "comm_eff": {
                        trace: 83.72,
                    },
                    "comp_scale": {
                        trace: 100.0,
                    },
                    "ipc_scale": {
                        trace: 100.0,
                    },
                    "inst_scale": {
                        trace: 100.0,
                    },
                    "freq_scale": {
                        trace: 100.0,
                    },
                },
                "hybrid_factors": {
                    "hybrid_eff": {
                        trace: 72.0,
                    },
                    "mpi_parallel_eff": {
                        trace: 80.0,
                    },
                    "mpi_load_balance": {
                        trace: 86.0,
                    },
                    "mpi_comm_eff": {
                        trace: 93.02,
                    },
                    "serial_eff": {
                        trace: 95.0,
                    },
                    "transfer_eff": {
                        trace: 97.92,
                    },
                    "omp_parallel_eff": {
                        trace: 90.0,
                    },
                    "omp_load_balance": {
                        trace: 94.0,
                    },
                    "omp_comm_eff": {
                        trace: 95.74,
                    },
                },
                "hyb_comm_omp_factors": {},
                "omp_talp_factors": {
                    "omp_talp_parallel_eff": {
                        trace: 78.0,
                    },
                    "omp_talp_serial_eff": {
                        trace: 92.0,
                    },
                    "omp_talp_load_balance": {
                        trace: 84.0,
                    },
                    "omp_talp_scheduling_eff": {
                        trace: 91.0,
                    },
                },
                "other_metrics": {},
            },
            "diagnosis": [],
            "evidence": [],
        }

    def _mpi_cuda_report_data(self):
        trace = "/tmp/mpi_cuda.prv"

        return {
            "general": {
                "analysis_kind": "hybrid",
                "pop_model": "classic",
            },
            "traces": [
                {
                    "id": 1,
                    "name": "mpi_cuda.prv",
                    "path": trace,
                    "mode": "Detailed+MPI+CUDA",
                    "processes": 4,
                    "tasks": 4,
                    "threads": 1,
                    "devices": 4,
                    "gpu_streams": 4,
                    "gpu_streams_per_rank": 1,
                },
            ],
            "resources": [],
            "metrics": {
                "kind": "hybrid",
                "mod_factors": {
                    "global_eff": {
                        trace: 65.0,
                    },
                    "parallel_eff": {
                        trace: 65.0,
                    },
                    "load_balance": {
                        trace: 80.0,
                    },
                    "comm_eff": {
                        trace: 81.25,
                    },
                    "comp_scale": {
                        trace: 100.0,
                    },
                    "ipc_scale": {
                        trace: 100.0,
                    },
                    "inst_scale": {
                        trace: 100.0,
                    },
                    "freq_scale": {
                        trace: 100.0,
                    },
                },
                "hybrid_factors": {
                    "hybrid_eff": {
                        trace: 65.0,
                    },
                    "mpi_parallel_eff": {
                        trace: 81.0,
                    },
                    "mpi_load_balance": {
                        trace: 87.0,
                    },
                    "mpi_comm_eff": {
                        trace: 93.10,
                    },
                    "serial_eff": {
                        trace: 95.0,
                    },
                    "transfer_eff": {
                        trace: 98.0,
                    },
                    "omp_parallel_eff": {
                        trace: 80.25,
                    },
                    "omp_load_balance": {
                        trace: 88.0,
                    },
                    "omp_comm_eff": {
                        trace: 91.19,
                    },
                },
                "hyb_comm_omp_factors": {},
                "omp_talp_factors": {},
                "host_factors": {
                    "host_global_eff": {
                        trace: 70.0,
                    },
                    "host_parallel_eff": {
                        trace: 78.0,
                    },
                    "mpi_parallel_eff": {
                        trace: 81.0,
                    },
                    "mpi_load_balance": {
                        trace: 87.0,
                    },
                    "mpi_comm_eff": {
                        trace: 93.10,
                    },
                    "serial_eff": {
                        trace: 95.0,
                    },
                    "transfer_eff": {
                        trace: 98.0,
                    },
                    "dev_offload_eff": {
                        trace: 89.74,
                    },
                    "host_comp_scale": {
                        trace: 100.0,
                    },
                },
                "device_factors": {
                    "dev_global_eff": {
                        trace: 62.0,
                    },
                    "dev_parallel_eff": {
                        trace: 70.0,
                    },
                    "dev_load_balance": {
                        trace: 80.0,
                    },
                    "dev_comm_eff": {
                        trace: 90.0,
                    },
                    "dev_orches_eff": {
                        trace: 97.22,
                    },
                    "dev_comp_scale": {
                        trace: 88.57,
                    },
                },
                "other_metrics": {},
            },
            "diagnosis": [],
            "evidence": [],
        }

    @staticmethod
    def _build_sections(report_data):
        context = build_analysis_context(report_data)
        report = build_report_model(context)

        return (
            report.get_section("performance-assessment"),
            report.get_section("runtime-analysis"),
            report.get_section("resource-analysis"),
        )

    def test_exports_analysis_view(self):
        view = AnalysisView(
            view_id="mpi-runtime",
            label="MPI",
            title="MPI Runtime Analysis",
            group="runtime",
            description="MPI details.",
        )

        self.assertEqual(
            view.view_id,
            "mpi-runtime",
        )

    def test_single_mpi_has_no_selector_views(self):
        _, runtime, resource = self._build_sections(
            self._mpi_report_data()
        )

        views = build_analysis_views(
            runtime_section=runtime,
            resource_section=resource,
        )

        self.assertEqual(
            views,
            (),
        )

    def test_mpi_openmp_builds_runtime_selector_views(self):
        _, runtime, resource = self._build_sections(
            self._mpi_openmp_report_data()
        )

        views = build_analysis_views(
            runtime_section=runtime,
            resource_section=resource,
        )

        self.assertEqual(
            [
                view.view_id
                for view in views
            ],
            [
                "mpi-runtime",
                "openmp-runtime",
            ],
        )

        self.assertEqual(
            [
                view.group
                for view in views
            ],
            [
                "runtime",
                "runtime",
            ],
        )

    def test_mpi_cuda_builds_runtime_and_domain_views(self):
        _, runtime, resource = self._build_sections(
            self._mpi_cuda_report_data()
        )

        views = build_analysis_views(
            runtime_section=runtime,
            resource_section=resource,
        )

        self.assertEqual(
            [
                view.view_id
                for view in views
            ],
            [
                "mpi-runtime",
                "accelerator-runtime",
                "host-analysis",
                "device-analysis",
            ],
        )

        self.assertEqual(
            [
                view.group
                for view in views
            ],
            [
                "runtime",
                "runtime",
                "domain",
                "domain",
            ],
        )

        self.assertEqual(
            [
                view.label
                for view in views
            ],
            [
                "MPI",
                "CUDA",
                "Host",
                "Device",
            ],
        )

    def test_component_html_is_attached_to_matching_view(self):
        _, runtime, resource = self._build_sections(
            self._mpi_cuda_report_data()
        )

        views = build_analysis_views(
            runtime_section=runtime,
            resource_section=resource,
            component_html={
                "mpi-runtime": "<p>MPI body</p>",
                "host-analysis": "<p>Host body</p>",
            },
        )

        bodies = {
            view.view_id: view.body_html
            for view in views
        }

        self.assertEqual(
            bodies["mpi-runtime"],
            "<p>MPI body</p>",
        )

        self.assertEqual(
            bodies["host-analysis"],
            "<p>Host body</p>",
        )

        self.assertEqual(
            bodies["device-analysis"],
            "",
        )

    def test_selector_renders_runtime_and_domain_groups(self):
        _, runtime, resource = self._build_sections(
            self._mpi_cuda_report_data()
        )

        views = build_analysis_views(
            runtime_section=runtime,
            resource_section=resource,
        )

        rendered = render_analysis_selector(
            views
        )

        self.assertIn(
            "Runtime components",
            rendered,
        )
        self.assertIn(
            "Execution domains",
            rendered,
        )
        self.assertIn(
            'data-analysis-target="mpi-runtime"',
            rendered,
        )
        self.assertIn(
            'data-analysis-target="accelerator-runtime"',
            rendered,
        )
        self.assertIn(
            'data-analysis-target="host-analysis"',
            rendered,
        )
        self.assertIn(
            'data-analysis-target="device-analysis"',
            rendered,
        )

        self.assertNotIn(
            "disabled",
            rendered,
        )

        self.assertIn(
            'aria-selected="false"',
            rendered,
        )

    def test_empty_selector_renders_explanation(self):
        rendered = render_analysis_selector(
            ()
        )

        self.assertIn(
            "No additional runtime or execution-domain analysis",
            rendered,
        )

    
    def test_complete_interactive_layout_contains_expected_sections(self):
        assessment, runtime, resource = self._build_sections(
            self._mpi_cuda_report_data()
        )

        rendered = render_performance_assessment(
            assessment_section=assessment,
            runtime_section=runtime,
            resource_section=resource,
            parallel_runtime_model_html=(
                "<div id='runtime-body'>Runtime</div>"
            ),
            component_html={
                "mpi-runtime": "<div id='mpi-body'>MPI</div>",
                "accelerator-runtime": (
                    "<div id='accelerator-body'>CUDA</div>"
                ),
                "host-analysis": "<div id='host-body'>Host</div>",
                "device-analysis": (
                    "<div id='device-body'>Device</div>"
                ),
            },
        )

        self.assertIn(
            'class="performance-assessment-view"',
            rendered,
        )

        self.assertNotIn(
            'class="performance-global-metrics"',
            rendered,
        )

        self.assertIn(
            'class="performance-runtime-analysis"',
            rendered,
        )

        self.assertIn(
            'class="performance-primary-panel"',
            rendered,
        )

        self.assertIn(
            'class="performance-secondary-panel"',
            rendered,
        )

        self.assertIn(
            'class="performance-analysis-selector"',
            rendered,
        )

        self.assertIn(
            "data-performance-assessment",
            rendered,
        )

        self.assertIn(
            "data-performance-secondary-placeholder",
            rendered,
        )

        self.assertIn(
            'data-performance-analysis-view="mpi-runtime"',
            rendered,
        )

        self.assertIn(
            'data-performance-analysis-view="accelerator-runtime"',
            rendered,
        )

        self.assertIn(
            'data-performance-analysis-view="host-analysis"',
            rendered,
        )

        self.assertIn(
            'data-performance-analysis-view="device-analysis"',
            rendered,
        )

        self.assertIn(
            "id='runtime-body'",
            rendered,
        )

        self.assertIn(
            "id='mpi-body'",
            rendered,
        )

        self.assertIn(
            "id='accelerator-body'",
            rendered,
        )

        self.assertIn(
            "id='host-body'",
            rendered,
        )

        self.assertIn(
            "id='device-body'",
            rendered,
        )

        self.assertIn(
            "addEventListener",
            rendered,
        )

        self.assertIn(
            "clearSelection",
            rendered,
        )

        self.assertIn(
            "selectView",
            rendered,
        )    


    def test_rejects_wrong_assessment_section(self):
        _, runtime, resource = self._build_sections(
            self._mpi_cuda_report_data()
        )

        with self.assertRaises(ValueError):
            render_performance_assessment(
                assessment_section=runtime,
                runtime_section=runtime,
                resource_section=resource,
                parallel_runtime_model_html="",
            )

    def test_secondary_panel_contains_placeholder_and_views(self):
        views = (
            AnalysisView(
                view_id="mpi-runtime",
                label="MPI",
                title="MPI Runtime Analysis",
                group="runtime",
                description="MPI details.",
                body_html="<p>MPI body</p>",
            ),
        )

        rendered = render_secondary_panel(
            views
        )

        self.assertIn(
            "Selected analysis",
            rendered,
        )

        self.assertIn(
            'data-performance-secondary-placeholder',
            rendered,
        )

        self.assertIn(
            'data-performance-analysis-view="mpi-runtime"',
            rendered,
        )

        self.assertIn(
            "<p>MPI body</p>",
            rendered,
        )

        self.assertIn(
            "data-performance-secondary-close",
            rendered,
        )


    def test_secondary_panel_is_empty_without_views(self):
        self.assertEqual(
            render_secondary_panel(()),
            "",
        )


if __name__ == "__main__":
    unittest.main(
        verbosity=2
    )