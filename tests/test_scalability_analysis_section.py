"""Tests for the semantic Scalability Analysis section."""

import unittest

from report import (
    build_analysis_context,
    build_report_model,
)

from report.sections import (
    MetricAnalysisData,
    MetricAnalysisMetric,
    MetricAnalysisTreeNode,
    MetricAnalysisValue,
    ScalabilityAnalysisBuilder,
    ScalabilityAnalysisData,
)


class ScalabilityAnalysisBuilderTests(unittest.TestCase):
    """Validate Computation Scalability availability and structure."""

    # ------------------------------------------------------------------
    # Test data
    # ------------------------------------------------------------------

    def _cpu_report_data(
        self,
        trace_count=2,
    ):
        """Return representative multi-trace CPU scalability data."""

        trace_paths = [
            "/tmp/mpi_4.prv",
            "/tmp/mpi_8.prv",
            "/tmp/mpi_16.prv",
        ]

        traces = []

        for index in range(trace_count):
            parallel_units = 4 * (2 ** index)

            traces.append(
                {
                    "id": index + 1,
                    "name": "mpi_{}.prv".format(
                        parallel_units
                    ),
                    "path": trace_paths[index],
                    "mode": "Detailed+MPI",
                    "processes": parallel_units,
                    "tasks": parallel_units,
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
                    "comp_scale": {
                        trace_paths[0]: 100.0,
                        trace_paths[1]: 82.0,
                        trace_paths[2]: 73.0,
                    },
                    "ipc_scale": {
                        trace_paths[0]: 100.0,
                        trace_paths[1]: 91.0,
                        trace_paths[2]: 85.0,
                    },
                    "inst_scale": {
                        trace_paths[0]: 100.0,
                        trace_paths[1]: 90.11,
                        trace_paths[2]: 85.88,
                    },
                    "freq_scale": {
                        trace_paths[0]: 100.0,
                        trace_paths[1]: 100.0,
                        trace_paths[2]: 99.95,
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
        """Return representative MPI+CUDA scalability data."""

        trace_paths = [
            "/tmp/mpi_cuda_4.prv",
            "/tmp/mpi_cuda_8.prv",
            "/tmp/mpi_cuda_16.prv",
        ]

        traces = []

        for index in range(trace_count):
            mpi_ranks = 4 * (2 ** index)

            traces.append(
                {
                    "id": index + 1,
                    "name": "mpi_cuda_{}.prv".format(
                        mpi_ranks
                    ),
                    "path": trace_paths[index],
                    "mode": "Detailed+MPI+CUDA",
                    "processes": mpi_ranks,
                    "tasks": mpi_ranks,
                    "threads": 1,
                    "devices": 4,
                    "gpu_streams": mpi_ranks,
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
                    "comp_scale": {
                        trace_paths[0]: 100.0,
                        trace_paths[1]: 74.0,
                        trace_paths[2]: 61.0,
                    },

                    # These legacy values may exist, but the semantic
                    # Scalability Analysis must not expose them as the
                    # decomposition of MPI+CUDA Computation Scalability.
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
                "hybrid_factors": {},
                "host_factors": {},
                "device_factors": {},
                "other_metrics": {},
            },
            "diagnosis": [],
            "evidence": [],
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_section(report_data):
        context = build_analysis_context(
            report_data
        )

        return ScalabilityAnalysisBuilder().build(
            context
        )

    @staticmethod
    def _metric_ids(analysis):
        return [
            metric.metric_id
            for metric in analysis.metrics
        ]

    @staticmethod
    def _metric_by_id(
        analysis,
        metric_id,
    ):
        for metric in analysis.metrics:
            if metric.metric_id == metric_id:
                return metric

        raise AssertionError(
            "Metric {!r} was not created.".format(
                metric_id
            )
        )

    # ------------------------------------------------------------------
    # Availability
    # ------------------------------------------------------------------

    def test_single_trace_does_not_create_scalability_section(self):
        section = self._build_section(
            self._cpu_report_data(
                trace_count=1
            )
        )

        self.assertIsNone(
            section
        )

    def test_multiple_traces_create_scalability_section(self):
        section = self._build_section(
            self._cpu_report_data(
                trace_count=2
            )
        )

        self.assertIsNotNone(
            section
        )

        self.assertEqual(
            section.section_id,
            "scalability-analysis",
        )

        self.assertEqual(
            section.section_type,
            "scalability-analysis",
        )

        self.assertEqual(
            section.order,
            50,
        )

    def test_multiple_traces_without_metrics_do_not_create_section(self):
        report_data = self._cpu_report_data(
            trace_count=2
        )

        report_data[
            "metrics"
        ][
            "mod_factors"
        ] = {}

        section = self._build_section(
            report_data
        )

        self.assertIsNone(
            section
        )

    def test_non_numeric_scalability_metrics_do_not_create_section(self):
        report_data = self._cpu_report_data(
            trace_count=2
        )

        report_data[
            "metrics"
        ][
            "mod_factors"
        ] = {
            "comp_scale": {
                "/tmp/mpi_4.prv": "Non-Avail",
                "/tmp/mpi_8.prv": None,
            },
            "ipc_scale": {
                "/tmp/mpi_4.prv": "NaN",
                "/tmp/mpi_8.prv": "Non-Avail",
            },
        }

        section = self._build_section(
            report_data
        )

        self.assertIsNone(
            section
        )

    # ------------------------------------------------------------------
    # CPU model
    # ------------------------------------------------------------------

    def test_cpu_scalability_uses_typed_payload(self):
        section = self._build_section(
            self._cpu_report_data(
                trace_count=2
            )
        )

        self.assertIsInstance(
            section.payload,
            ScalabilityAnalysisData,
        )

        self.assertIsInstance(
            section.payload.analysis,
            MetricAnalysisData,
        )

        self.assertEqual(
            section.payload.trace_count,
            2,
        )

        self.assertFalse(
            section.payload.accelerator_limited_model
        )

    def test_cpu_scalability_contains_expected_metrics(self):
        section = self._build_section(
            self._cpu_report_data(
                trace_count=2
            )
        )

        analysis = section.payload.analysis

        self.assertEqual(
            self._metric_ids(
                analysis
            ),
            [
                "comp_scale",
                "ipc_scale",
                "inst_scale",
                "freq_scale",
            ],
        )

    def test_cpu_scalability_builds_expected_tree(self):
        section = self._build_section(
            self._cpu_report_data(
                trace_count=2
            )
        )

        tree = section.payload.analysis.tree

        self.assertEqual(
            len(tree),
            1,
        )

        root = tree[0]

        self.assertEqual(
            root.metric_id,
            "comp_scale",
        )

        self.assertEqual(
            [
                child.metric_id
                for child in root.children
            ],
            [
                "ipc_scale",
                "inst_scale",
                "freq_scale",
            ],
        )

    def test_partial_cpu_metrics_are_pruned_from_tree(self):
        report_data = self._cpu_report_data(
            trace_count=2
        )

        del report_data[
            "metrics"
        ][
            "mod_factors"
        ][
            "inst_scale"
        ]

        report_data[
            "metrics"
        ][
            "mod_factors"
        ][
            "freq_scale"
        ] = {
            "/tmp/mpi_4.prv": "Non-Avail",
            "/tmp/mpi_8.prv": None,
        }

        section = self._build_section(
            report_data
        )

        analysis = section.payload.analysis

        self.assertEqual(
            self._metric_ids(
                analysis
            ),
            [
                "comp_scale",
                "ipc_scale",
            ],
        )

        self.assertEqual(
            [
                child.metric_id
                for child in analysis.tree[0].children
            ],
            [
                "ipc_scale",
            ],
        )

    def test_metric_values_follow_trace_order(self):
        report_data = self._cpu_report_data(
            trace_count=2
        )

        report_data[
            "metrics"
        ][
            "mod_factors"
        ][
            "comp_scale"
        ] = {
            "/tmp/mpi_8.prv": 82.0,
            "/tmp/mpi_4.prv": 100.0,
        }

        section = self._build_section(
            report_data
        )

        comp_scale = self._metric_by_id(
            section.payload.analysis,
            "comp_scale",
        )

        self.assertEqual(
            [
                value.trace_id
                for value in comp_scale.values
            ],
            [
                1,
                2,
            ],
        )

        self.assertEqual(
            [
                value.value
                for value in comp_scale.values
            ],
            [
                100.0,
                82.0,
            ],
        )

    def test_missing_trace_value_is_preserved_as_none(self):
        report_data = self._cpu_report_data(
            trace_count=2
        )

        del report_data[
            "metrics"
        ][
            "mod_factors"
        ][
            "ipc_scale"
        ][
            "/tmp/mpi_8.prv"
        ]

        section = self._build_section(
            report_data
        )

        ipc_scale = self._metric_by_id(
            section.payload.analysis,
            "ipc_scale",
        )

        self.assertEqual(
            ipc_scale.values[0].value,
            100.0,
        )

        self.assertIsNone(
            ipc_scale.values[1].value
        )

    # ------------------------------------------------------------------
    # Accelerator model
    # ------------------------------------------------------------------

    def test_mpi_cuda_exposes_only_computation_scalability(self):
        section = self._build_section(
            self._mpi_cuda_report_data(
                trace_count=2
            )
        )

        analysis = section.payload.analysis

        self.assertEqual(
            self._metric_ids(
                analysis
            ),
            [
                "comp_scale",
            ],
        )

        self.assertEqual(
            analysis.tree[0].metric_id,
            "comp_scale",
        )

        self.assertEqual(
            analysis.tree[0].children,
            (),
        )

    def test_mpi_cuda_payload_marks_limited_model(self):
        section = self._build_section(
            self._mpi_cuda_report_data(
                trace_count=2
            )
        )

        self.assertTrue(
            section.payload.accelerator_limited_model
        )

        self.assertIn(
            "GPU-inclusive",
            section.payload.analysis.description,
        )

    def test_mpi_cuda_without_comp_scale_does_not_create_section(self):
        report_data = self._mpi_cuda_report_data(
            trace_count=2
        )

        del report_data[
            "metrics"
        ][
            "mod_factors"
        ][
            "comp_scale"
        ]

        section = self._build_section(
            report_data
        )

        self.assertIsNone(
            section
        )

    # ------------------------------------------------------------------
    # Section hierarchy and typed objects
    # ------------------------------------------------------------------

    def test_builds_computation_scalability_child_section(self):
        section = self._build_section(
            self._cpu_report_data(
                trace_count=2
            )
        )

        self.assertEqual(
            len(section.children),
            1,
        )

        child = section.children[0]

        self.assertEqual(
            child.section_id,
            "computation-scalability",
        )

        self.assertEqual(
            child.section_type,
            "computation-scalability",
        )

        self.assertEqual(
            child.payload,
            section.payload.analysis,
        )

    def test_uses_typed_metric_objects(self):
        section = self._build_section(
            self._cpu_report_data(
                trace_count=2
            )
        )

        analysis = section.payload.analysis

        for metric in analysis.metrics:
            self.assertIsInstance(
                metric,
                MetricAnalysisMetric,
            )

            for value in metric.values:
                self.assertIsInstance(
                    value,
                    MetricAnalysisValue,
                )

        for node in analysis.tree:
            self.assertIsInstance(
                node,
                MetricAnalysisTreeNode,
            )

    # ------------------------------------------------------------------
    # Report integration
    # ------------------------------------------------------------------

    def test_report_builder_adds_scalability_for_multiple_traces(self):
        context = build_analysis_context(
            self._cpu_report_data(
                trace_count=2
            )
        )

        report = build_report_model(
            context
        )

        scalability = report.get_section(
            "scalability-analysis"
        )

        computation = report.get_section(
            "computation-scalability"
        )

        self.assertIsNotNone(
            scalability
        )

        self.assertIsNotNone(
            computation
        )

        self.assertIsInstance(
            scalability.payload,
            ScalabilityAnalysisData,
        )

        self.assertEqual(
            computation.payload,
            scalability.payload.analysis,
        )

    def test_report_builder_omits_scalability_for_single_trace(self):
        context = build_analysis_context(
            self._cpu_report_data(
                trace_count=1
            )
        )

        report = build_report_model(
            context
        )

        self.assertIsNone(
            report.get_section(
                "scalability-analysis"
            )
        )

        self.assertIsNone(
            report.get_section(
                "computation-scalability"
            )
        )


if __name__ == "__main__":
    unittest.main(
        verbosity=2
    )