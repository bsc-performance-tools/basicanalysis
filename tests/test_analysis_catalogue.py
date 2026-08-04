"""Tests for the HTML analysis-view catalogue."""

import unittest

from report import (
    build_analysis_context,
    build_report_model,
)

from report.renderer.html import (
    AnalysisCatalogue,
    AnalysisCatalogueView,
    build_analysis_catalogue,
)


class AnalysisCatalogueTests(unittest.TestCase):
    """Validate catalogue composition for the main execution models."""

    # ------------------------------------------------------------------
    # Test data
    # ------------------------------------------------------------------

    def _mpi_report_data(
        self,
        trace_count=1,
    ):
        trace_paths = [
            "/tmp/mpi_4.prv",
            "/tmp/mpi_8.prv",
            "/tmp/mpi_16.prv",
        ]

        traces = []

        for index in range(trace_count):
            processes = 4 * (2 ** index)

            traces.append(
                {
                    "id": index + 1,
                    "name": "mpi_{}.prv".format(
                        processes
                    ),
                    "path": trace_paths[index],
                    "mode": "Detailed+MPI",
                    "processes": processes,
                    "tasks": processes,
                    "threads": 1,
                    "devices": 0,
                    "gpu_streams": 0,
                    "gpu_streams_per_rank": 0,
                }
            )

        return {
            "general": {
                "analysis_kind": "simple",
                "pop_model": "classic",
            },
            "traces": traces,
            "resources": [],
            "metrics": {
                "kind": "simple",
                "mod_factors": {
                    "global_eff": {
                        trace_paths[0]: 100.0,
                        trace_paths[1]: 82.0,
                        trace_paths[2]: 73.0,
                    },
                    "parallel_eff": {
                        trace_paths[0]: 100.0,
                        trace_paths[1]: 84.0,
                        trace_paths[2]: 76.0,
                    },
                    "load_balance": {
                        trace_paths[0]: 100.0,
                        trace_paths[1]: 90.0,
                        trace_paths[2]: 86.0,
                    },
                    "comm_eff": {
                        trace_paths[0]: 100.0,
                        trace_paths[1]: 93.33,
                        trace_paths[2]: 88.37,
                    },
                    "serial_eff": {
                        trace_paths[0]: 100.0,
                        trace_paths[1]: 96.0,
                        trace_paths[2]: 92.0,
                    },
                    "transfer_eff": {
                        trace_paths[0]: 100.0,
                        trace_paths[1]: 97.22,
                        trace_paths[2]: 96.05,
                    },
                    "comp_scale": {
                        trace_paths[0]: 100.0,
                        trace_paths[1]: 97.62,
                        trace_paths[2]: 96.05,
                    },
                    "ipc_scale": {
                        trace_paths[0]: 100.0,
                        trace_paths[1]: 93.0,
                        trace_paths[2]: 89.0,
                    },
                    "inst_scale": {
                        trace_paths[0]: 100.0,
                        trace_paths[1]: 95.0,
                        trace_paths[2]: 92.0,
                    },
                    "freq_scale": {
                        trace_paths[0]: 100.0,
                        trace_paths[1]: 99.9,
                        trace_paths[2]: 98.7,
                    },
                },
                "other_metrics": {},
            },
            "diagnosis": [],
            "evidence": [],
        }

    def _mpi_openmp_report_data(
        self,
        trace_count=2,
    ):
        trace_paths = [
            "/tmp/mpi_openmp_1.prv",
            "/tmp/mpi_openmp_2.prv",
            "/tmp/mpi_openmp_3.prv",
        ]

        traces = []

        for index in range(trace_count):
            tasks = 4 * (2 ** index)
            threads = 4

            traces.append(
                {
                    "id": index + 1,
                    "name": "mpi_openmp_{}.prv".format(
                        index + 1
                    ),
                    "path": trace_paths[index],
                    "mode": "Detailed+MPI+OpenMP",
                    "processes": tasks * threads,
                    "tasks": tasks,
                    "threads": threads,
                    "devices": 0,
                    "gpu_streams": 0,
                    "gpu_streams_per_rank": 0,
                }
            )

        return {
            "general": {
                "analysis_kind": "hybrid",
                "pop_model": "classic",
            },
            "traces": traces,
            "resources": [],
            "metrics": {
                "kind": "hybrid",
                "mod_factors": {
                    "global_eff": {
                        trace_paths[0]: 100.0,
                        trace_paths[1]: 72.0,
                        trace_paths[2]: 63.0,
                    },
                    "parallel_eff": {
                        trace_paths[0]: 100.0,
                        trace_paths[1]: 72.0,
                        trace_paths[2]: 66.0,
                    },
                    "load_balance": {
                        trace_paths[0]: 100.0,
                        trace_paths[1]: 86.0,
                        trace_paths[2]: 83.0,
                    },
                    "comm_eff": {
                        trace_paths[0]: 100.0,
                        trace_paths[1]: 83.72,
                        trace_paths[2]: 79.52,
                    },
                    "comp_scale": {
                        trace_paths[0]: 100.0,
                        trace_paths[1]: 100.0,
                        trace_paths[2]: 95.45,
                    },
                    "ipc_scale": {
                        trace_paths[0]: 100.0,
                        trace_paths[1]: 96.0,
                        trace_paths[2]: 91.0,
                    },
                    "inst_scale": {
                        trace_paths[0]: 100.0,
                        trace_paths[1]: 97.0,
                        trace_paths[2]: 94.0,
                    },
                    "freq_scale": {
                        trace_paths[0]: 100.0,
                        trace_paths[1]: 100.0,
                        trace_paths[2]: 99.2,
                    },
                },
                "hybrid_factors": {
                    "hybrid_eff": {
                        trace_paths[0]: 100.0,
                        trace_paths[1]: 72.0,
                        trace_paths[2]: 66.0,
                    },
                    "mpi_parallel_eff": {
                        trace_paths[0]: 100.0,
                        trace_paths[1]: 80.0,
                        trace_paths[2]: 75.0,
                    },
                    "mpi_load_balance": {
                        trace_paths[0]: 100.0,
                        trace_paths[1]: 86.0,
                        trace_paths[2]: 82.0,
                    },
                    "mpi_comm_eff": {
                        trace_paths[0]: 100.0,
                        trace_paths[1]: 93.02,
                        trace_paths[2]: 91.46,
                    },
                    "serial_eff": {
                        trace_paths[0]: 100.0,
                        trace_paths[1]: 95.0,
                        trace_paths[2]: 92.0,
                    },
                    "transfer_eff": {
                        trace_paths[0]: 100.0,
                        trace_paths[1]: 97.92,
                        trace_paths[2]: 99.41,
                    },
                    "omp_parallel_eff": {
                        trace_paths[0]: 100.0,
                        trace_paths[1]: 90.0,
                        trace_paths[2]: 88.0,
                    },
                    "omp_load_balance": {
                        trace_paths[0]: 100.0,
                        trace_paths[1]: 94.0,
                        trace_paths[2]: 91.0,
                    },
                    "omp_comm_eff": {
                        trace_paths[0]: 100.0,
                        trace_paths[1]: 95.74,
                        trace_paths[2]: 96.70,
                    },
                },
                "hyb_comm_omp_factors": {},
                "omp_talp_factors": {
                    "omp_talp_parallel_eff": {
                        trace_paths[0]: 93.0,
                        trace_paths[1]: 78.0,
                        trace_paths[2]: 72.0,
                    },
                    "omp_talp_serial_eff": {
                        trace_paths[0]: 98.0,
                        trace_paths[1]: 92.0,
                        trace_paths[2]: 89.0,
                    },
                    "omp_talp_load_balance": {
                        trace_paths[0]: 95.0,
                        trace_paths[1]: 84.0,
                        trace_paths[2]: 80.0,
                    },
                    "omp_talp_scheduling_eff": {
                        trace_paths[0]: 99.0,
                        trace_paths[1]: 91.0,
                        trace_paths[2]: 90.0,
                    },
                },
                "other_metrics": {},
            },
            "diagnosis": [],
            "evidence": [],
        }

    def _mpi_cuda_report_data(
        self,
        trace_count=2,
    ):
        trace_paths = [
            "/tmp/mpi_cuda_1.prv",
            "/tmp/mpi_cuda_2.prv",
            "/tmp/mpi_cuda_3.prv",
        ]

        traces = []

        for index in range(trace_count):
            ranks = 4 * (2 ** index)

            traces.append(
                {
                    "id": index + 1,
                    "name": "mpi_cuda_{}.prv".format(
                        index + 1
                    ),
                    "path": trace_paths[index],
                    "mode": "Detailed+MPI+CUDA",
                    "processes": ranks,
                    "tasks": ranks,
                    "threads": 1,
                    "devices": 4,
                    "gpu_streams": ranks,
                    "gpu_streams_per_rank": 1,
                }
            )

        return {
            "general": {
                "analysis_kind": "hybrid",
                "pop_model": "talp",
            },
            "traces": traces,
            "resources": [],
            "metrics": {
                "kind": "hybrid",
                "mod_factors": {
                    "global_eff": {
                        trace_paths[0]: 100.0,
                        trace_paths[1]: 65.0,
                        trace_paths[2]: 57.0,
                    },
                    "parallel_eff": {
                        trace_paths[0]: 100.0,
                        trace_paths[1]: 65.0,
                        trace_paths[2]: 60.0,
                    },
                    "load_balance": {
                        trace_paths[0]: 100.0,
                        trace_paths[1]: 80.0,
                        trace_paths[2]: 77.0,
                    },
                    "comm_eff": {
                        trace_paths[0]: 100.0,
                        trace_paths[1]: 81.25,
                        trace_paths[2]: 77.92,
                    },
                    "comp_scale": {
                        trace_paths[0]: 100.0,
                        trace_paths[1]: 87.69,
                        trace_paths[2]: 95.0,
                    },
                    "ipc_scale": {
                        trace_paths[0]: 100.0,
                        trace_paths[1]: 93.0,
                        trace_paths[2]: 88.0,
                    },
                    "inst_scale": {
                        trace_paths[0]: 100.0,
                        trace_paths[1]: 84.0,
                        trace_paths[2]: 76.0,
                    },
                    "freq_scale": {
                        trace_paths[0]: 100.0,
                        trace_paths[1]: 97.0,
                        trace_paths[2]: 94.0,
                    },
                },
                "hybrid_factors": {
                    "hybrid_eff": {
                        trace_paths[0]: 100.0,
                        trace_paths[1]: 65.0,
                        trace_paths[2]: 60.0,
                    },
                    "mpi_parallel_eff": {
                        trace_paths[0]: 100.0,
                        trace_paths[1]: 81.0,
                        trace_paths[2]: 78.0,
                    },
                    "mpi_load_balance": {
                        trace_paths[0]: 100.0,
                        trace_paths[1]: 87.0,
                        trace_paths[2]: 83.0,
                    },
                    "mpi_comm_eff": {
                        trace_paths[0]: 100.0,
                        trace_paths[1]: 93.10,
                        trace_paths[2]: 93.98,
                    },
                    "serial_eff": {
                        trace_paths[0]: 100.0,
                        trace_paths[1]: 95.0,
                        trace_paths[2]: 93.0,
                    },
                    "transfer_eff": {
                        trace_paths[0]: 100.0,
                        trace_paths[1]: 98.0,
                        trace_paths[2]: 98.9,
                    },
                    "omp_parallel_eff": {
                        trace_paths[0]: 100.0,
                        trace_paths[1]: 80.25,
                        trace_paths[2]: 76.92,
                    },
                    "omp_load_balance": {
                        trace_paths[0]: 100.0,
                        trace_paths[1]: 88.0,
                        trace_paths[2]: 84.0,
                    },
                    "omp_comm_eff": {
                        trace_paths[0]: 100.0,
                        trace_paths[1]: 91.19,
                        trace_paths[2]: 91.57,
                    },
                },
                "hyb_comm_omp_factors": {},
                "omp_talp_factors": {},
                "host_factors": {
                    "host_global_eff": {
                        trace_paths[0]: 100.0,
                        trace_paths[1]: 70.0,
                        trace_paths[2]: 63.0,
                    },
                    "host_parallel_eff": {
                        trace_paths[0]: 100.0,
                        trace_paths[1]: 78.0,
                        trace_paths[2]: 75.0,
                    },
                    "mpi_parallel_eff": {
                        trace_paths[0]: 100.0,
                        trace_paths[1]: 81.0,
                        trace_paths[2]: 78.0,
                    },
                    "mpi_load_balance": {
                        trace_paths[0]: 100.0,
                        trace_paths[1]: 87.0,
                        trace_paths[2]: 83.0,
                    },
                    "mpi_comm_eff": {
                        trace_paths[0]: 100.0,
                        trace_paths[1]: 93.10,
                        trace_paths[2]: 93.98,
                    },
                    "serial_eff": {
                        trace_paths[0]: 100.0,
                        trace_paths[1]: 95.0,
                        trace_paths[2]: 93.0,
                    },
                    "transfer_eff": {
                        trace_paths[0]: 100.0,
                        trace_paths[1]: 98.0,
                        trace_paths[2]: 98.9,
                    },
                    "dev_offload_eff": {
                        trace_paths[0]: 100.0,
                        trace_paths[1]: 89.74,
                        trace_paths[2]: 85.0,
                    },
                    "host_comp_scale": {
                        trace_paths[0]: 100.0,
                        trace_paths[1]: 100.0,
                        trace_paths[2]: 98.0,
                    },
                },
                "device_factors": {
                    "dev_global_eff": {
                        trace_paths[0]: 100.0,
                        trace_paths[1]: 62.0,
                        trace_paths[2]: 58.0,
                    },
                    "dev_parallel_eff": {
                        trace_paths[0]: 100.0,
                        trace_paths[1]: 70.0,
                        trace_paths[2]: 67.0,
                    },
                    "dev_load_balance": {
                        trace_paths[0]: 100.0,
                        trace_paths[1]: 80.0,
                        trace_paths[2]: 77.0,
                    },
                    "dev_comm_eff": {
                        trace_paths[0]: 100.0,
                        trace_paths[1]: 90.0,
                        trace_paths[2]: 88.0,
                    },
                    "dev_orches_eff": {
                        trace_paths[0]: 100.0,
                        trace_paths[1]: 97.22,
                        trace_paths[2]: 98.9,
                    },
                    "dev_comp_scale": {
                        trace_paths[0]: 100.0,
                        trace_paths[1]: 88.57,
                        trace_paths[2]: 86.57,
                    },
                },
                "other_metrics": {},
            },
            "diagnosis": [],
            "evidence": [],
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_sections(report_data):
        context = build_analysis_context(
            report_data
        )

        report = build_report_model(
            context
        )

        return (
            report.get_section("overview"),
            report.get_section("runtime-analysis"),
            report.get_section("resource-analysis"),
            report.get_section("scalability-analysis"),
        )

    @staticmethod
    def _build_catalogue(
        report_data,
        rendered_html=None,
    ):
        (
            overview,
            runtime,
            resource,
            scalability,
        ) = AnalysisCatalogueTests._build_sections(
            report_data
        )

        return build_analysis_catalogue(
            overview_section=overview,
            runtime_section=runtime,
            resource_section=resource,
            scalability_section=scalability,
            rendered_html=rendered_html or {},
        )

    @staticmethod
    def _view_ids(catalogue):
        return [
            view.view_id
            for view in catalogue.views
        ]

    # ------------------------------------------------------------------
    # Catalogue API
    # ------------------------------------------------------------------

    def test_returns_typed_catalogue(self):
        catalogue = self._build_catalogue(
            self._mpi_report_data(
                trace_count=1
            )
        )

        self.assertIsInstance(
            catalogue,
            AnalysisCatalogue,
        )

        for view in catalogue.views:
            self.assertIsInstance(
                view,
                AnalysisCatalogueView,
            )

    def test_get_view_returns_matching_entry(self):
        catalogue = self._build_catalogue(
            self._mpi_report_data(
                trace_count=1
            )
        )

        view = catalogue.get_view(
            "parallel-runtime-model"
        )

        self.assertIsNotNone(
            view
        )

        self.assertEqual(
            view.view_id,
            "parallel-runtime-model",
        )

    def test_get_view_returns_none_for_unknown_id(self):
        catalogue = self._build_catalogue(
            self._mpi_report_data(
                trace_count=1
            )
        )

        self.assertIsNone(
            catalogue.get_view(
                "unknown-view"
            )
        )

    def test_has_view_reports_availability(self):
        catalogue = self._build_catalogue(
            self._mpi_report_data(
                trace_count=1
            )
        )

        self.assertTrue(
            catalogue.has_view(
                "overview"
            )
        )

        self.assertFalse(
            catalogue.has_view(
                "computation-scalability"
            )
        )

    def test_views_by_group_filters_views(self):
        catalogue = self._build_catalogue(
            self._mpi_cuda_report_data(
                trace_count=2
            )
        )

        runtime_views = catalogue.views_by_group(
            "runtime"
        )

        self.assertEqual(
            [
                view.view_id
                for view in runtime_views
            ],
            [
                "mpi-runtime",
                "accelerator-runtime",
            ],
        )

        domain_views = catalogue.views_by_group(
            "domain"
        )

        self.assertEqual(
            [
                view.view_id
                for view in domain_views
            ],
            [
                "host-analysis",
                "device-analysis",
            ],
        )

    # ------------------------------------------------------------------
    # Single-runtime MPI
    # ------------------------------------------------------------------

    def test_single_trace_mpi_contains_only_overview_and_runtime_model(self):
        catalogue = self._build_catalogue(
            self._mpi_report_data(
                trace_count=1
            )
        )

        self.assertEqual(
            self._view_ids(
                catalogue
            ),
            [
                "overview",
                "parallel-runtime-model",
            ],
        )

    def test_multi_trace_mpi_adds_computation_scalability(self):
        catalogue = self._build_catalogue(
            self._mpi_report_data(
                trace_count=2
            )
        )

        self.assertEqual(
            self._view_ids(
                catalogue
            ),
            [
                "overview",
                "parallel-runtime-model",
                "computation-scalability",
            ],
        )

    def test_single_runtime_mpi_does_not_duplicate_mpi_component(self):
        catalogue = self._build_catalogue(
            self._mpi_report_data(
                trace_count=2
            )
        )

        self.assertFalse(
            catalogue.has_view(
                "mpi-runtime"
            )
        )

    # ------------------------------------------------------------------
    # MPI+OpenMP
    # ------------------------------------------------------------------

    def test_mpi_openmp_contains_assessment_and_runtime_views(self):
        catalogue = self._build_catalogue(
            self._mpi_openmp_report_data(
                trace_count=2
            )
        )

        self.assertEqual(
            self._view_ids(
                catalogue
            ),
            [
                "overview",
                "parallel-runtime-model",
                "computation-scalability",
                "mpi-runtime",
                "openmp-runtime",
            ],
        )

    def test_mpi_openmp_has_no_execution_domain_views(self):
        catalogue = self._build_catalogue(
            self._mpi_openmp_report_data(
                trace_count=2
            )
        )

        self.assertEqual(
            catalogue.views_by_group(
                "domain"
            ),
            (),
        )

    # ------------------------------------------------------------------
    # MPI+CUDA
    # ------------------------------------------------------------------

    def test_multi_trace_mpi_cuda_contains_all_available_views(self):
        catalogue = self._build_catalogue(
            self._mpi_cuda_report_data(
                trace_count=2
            )
        )

        self.assertEqual(
            self._view_ids(
                catalogue
            ),
            [
                "overview",
                "parallel-runtime-model",
                "computation-scalability",
                "mpi-runtime",
                "accelerator-runtime",
                "host-analysis",
                "device-analysis",
            ],
        )

    def test_single_trace_mpi_cuda_omits_computation_scalability(self):
        catalogue = self._build_catalogue(
            self._mpi_cuda_report_data(
                trace_count=1
            )
        )

        self.assertEqual(
            self._view_ids(
                catalogue
            ),
            [
                "overview",
                "parallel-runtime-model",
                "mpi-runtime",
                "accelerator-runtime",
                "host-analysis",
                "device-analysis",
            ],
        )

    def test_mpi_cuda_labels_are_user_facing(self):
        catalogue = self._build_catalogue(
            self._mpi_cuda_report_data(
                trace_count=2
            )
        )

        labels = {
            view.view_id: view.label
            for view in catalogue.views
        }

        self.assertEqual(
            labels["overview"],
            "Overview",
        )

        self.assertEqual(
            labels["parallel-runtime-model"],
            "Parallel Runtime Model",
        )

        self.assertEqual(
            labels["computation-scalability"],
            "Computation Scalability",
        )

        self.assertEqual(
            labels["mpi-runtime"],
            "MPI",
        )

        self.assertEqual(
            labels["accelerator-runtime"],
            "CUDA",
        )

        self.assertEqual(
            labels["host-analysis"],
            "Host",
        )

        self.assertEqual(
            labels["device-analysis"],
            "Device",
        )

    # ------------------------------------------------------------------
    # HTML mapping
    # ------------------------------------------------------------------

    def test_rendered_html_is_attached_by_semantic_id(self):
        catalogue = self._build_catalogue(
            self._mpi_cuda_report_data(
                trace_count=2
            ),
            rendered_html={
                "overview": "<div id='overview-body'></div>",
                "parallel-runtime-model": (
                    "<div id='runtime-model-body'></div>"
                ),
                "computation-scalability": (
                    "<div id='scalability-body'></div>"
                ),
                "mpi-runtime": "<div id='mpi-body'></div>",
                "accelerator-runtime": (
                    "<div id='accelerator-body'></div>"
                ),
                "host-analysis": "<div id='host-body'></div>",
                "device-analysis": (
                    "<div id='device-body'></div>"
                ),
            },
        )

        expected_ids = {
            "overview": "overview-body",
            "parallel-runtime-model": "runtime-model-body",
            "computation-scalability": "scalability-body",
            "mpi-runtime": "mpi-body",
            "accelerator-runtime": "accelerator-body",
            "host-analysis": "host-body",
            "device-analysis": "device-body",
        }

        for view_id, html_id in expected_ids.items():
            view = catalogue.get_view(
                view_id
            )

            self.assertIsNotNone(
                view
            )

            self.assertIn(
                html_id,
                view.body_html,
            )

    def test_missing_rendered_html_uses_empty_body(self):
        catalogue = self._build_catalogue(
            self._mpi_report_data(
                trace_count=1
            ),
            rendered_html={},
        )

        for view in catalogue.views:
            self.assertEqual(
                view.body_html,
                "",
            )

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def test_rejects_wrong_overview_section(self):
        (
            overview,
            runtime,
            resource,
            scalability,
        ) = self._build_sections(
            self._mpi_report_data(
                trace_count=2
            )
        )

        with self.assertRaises(ValueError):
            build_analysis_catalogue(
                overview_section=runtime,
                runtime_section=runtime,
                resource_section=resource,
                scalability_section=scalability,
                rendered_html={},
            )

    def test_rejects_wrong_runtime_section(self):
        (
            overview,
            runtime,
            resource,
            scalability,
        ) = self._build_sections(
            self._mpi_report_data(
                trace_count=2
            )
        )

        with self.assertRaises(ValueError):
            build_analysis_catalogue(
                overview_section=overview,
                runtime_section=overview,
                resource_section=resource,
                scalability_section=scalability,
                rendered_html={},
            )


if __name__ == "__main__":
    unittest.main(
        verbosity=2
    )