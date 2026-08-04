"""Tests for the semantic Performance Assessment section."""

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
    PerformanceAssessmentBuilder,
    PerformanceAssessmentData,
)


class PerformanceAssessmentBuilderTests(
    unittest.TestCase
):
    """Validate PerformanceAssessmentBuilder semantic output."""

    def _cpu_report_data(self):
        """Return representative CPU-only scalability data."""

        trace_1 = "/tmp/trace_1.prv"
        trace_2 = "/tmp/trace_2.prv"

        return {
            "general": {
                "analysis_kind": "simple",
                "pop_model": "classic",
            },
            "traces": [
                {
                    "id": 1,
                    "name": "trace_1.prv",
                    "path": trace_1,
                    "mode": "Detailed+MPI",
                    "processes": 4,
                    "tasks": 4,
                    "threads": 1,
                    "devices": 0,
                    "gpu_streams": 0,
                    "gpu_streams_per_rank": 0,
                },
                {
                    "id": 2,
                    "name": "trace_2.prv",
                    "path": trace_2,
                    "mode": "Detailed+MPI",
                    "processes": 8,
                    "tasks": 8,
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
                        trace_1: 100.0,
                        trace_2: 82.0,
                    },
                    "parallel_eff": {
                        trace_1: 100.0,
                        trace_2: 88.0,
                    },
                    "load_balance": {
                        trace_1: 100.0,
                        trace_2: 92.0,
                    },
                    "comm_eff": {
                        trace_1: 100.0,
                        trace_2: 95.65,
                    },
                    "comp_scale": {
                        trace_1: 100.0,
                        trace_2: 93.18,
                    },
                    "ipc_scale": {
                        trace_1: 100.0,
                        trace_2: 96.0,
                    },
                    "inst_scale": {
                        trace_1: 100.0,
                        trace_2: 98.0,
                    },
                    "freq_scale": {
                        trace_1: 100.0,
                        trace_2: 99.0,
                    },
                    # These runtime metrics must not become
                    # application-level Global Metrics.
                    "serial_eff": {
                        trace_1: 100.0,
                        trace_2: 91.0,
                    },
                    "transfer_eff": {
                        trace_1: 100.0,
                        trace_2: 97.0,
                    },
                },
                "other_metrics": {},
            },
            "diagnosis": [],
            "evidence": [],
        }

    def _gpu_report_data(self):
        """Return representative MPI+CUDA analysis data."""

        trace_1 = "/tmp/gpu_trace_1.prv"
        trace_2 = "/tmp/gpu_trace_2.prv"

        return {
            "general": {
                "analysis_kind": "hybrid",
                "pop_model": "classic",
            },
            "traces": [
                {
                    "id": 1,
                    "name": "gpu_trace_1.prv",
                    "path": trace_1,
                    "mode": "Detailed+MPI+CUDA",
                    "processes": 4,
                    "tasks": 4,
                    "threads": 1,
                    "devices": 4,
                    "gpu_streams": 4,
                    "gpu_streams_per_rank": 1,
                },
                {
                    "id": 2,
                    "name": "gpu_trace_2.prv",
                    "path": trace_2,
                    "mode": "Detailed+MPI+CUDA",
                    "processes": 8,
                    "tasks": 8,
                    "threads": 1,
                    "devices": 4,
                    "gpu_streams": 8,
                    "gpu_streams_per_rank": 1,
                },
            ],
            "resources": [],
            "metrics": {
                "kind": "hybrid",
                "mod_factors": {
                    "global_eff": {
                        trace_1: 100.0,
                        trace_2: 70.0,
                    },
                    "parallel_eff": {
                        trace_1: 100.0,
                        trace_2: 78.0,
                    },
                    "load_balance": {
                        trace_1: 100.0,
                        trace_2: 84.0,
                    },
                    "comm_eff": {
                        trace_1: 100.0,
                        trace_2: 92.86,
                    },
                    "comp_scale": {
                        trace_1: 100.0,
                        trace_2: 89.74,
                    },
                    # These values may exist internally, but must not be
                    # exposed in the application-level MPI+GPU view.
                    "ipc_scale": {
                        trace_1: 100.0,
                        trace_2: 90.0,
                    },
                    "inst_scale": {
                        trace_1: 100.0,
                        trace_2: 92.0,
                    },
                    "freq_scale": {
                        trace_1: 100.0,
                        trace_2: 97.0,
                    },
                },
                "hybrid_factors": {},
                "other_metrics": {},
            },
            "diagnosis": [],
            "evidence": [],
        }

    def _build_cpu_section(self):
        context = build_analysis_context(
            self._cpu_report_data()
        )

        return PerformanceAssessmentBuilder().build(
            context
        )

    @staticmethod
    def _metric_by_id(
        section,
        metric_id,
    ):
        for metric in (
            section.payload.global_metrics.metrics
        ):
            if metric.metric_id == metric_id:
                return metric

        raise AssertionError(
            "Metric {!r} was not created.".format(
                metric_id
            )
        )

    @staticmethod
    def _tree_node_by_id(
        nodes,
        metric_id,
    ):
        for node in nodes:
            if node.metric_id == metric_id:
                return node

            result = (
                PerformanceAssessmentBuilderTests
                ._tree_node_by_id(
                    node.children,
                    metric_id,
                )
            )

            if result is not None:
                return result

        return None

    def test_builds_performance_assessment_section(self):
        section = self._build_cpu_section()

        self.assertEqual(
            section.section_id,
            "performance-assessment",
        )

        self.assertEqual(
            section.title,
            "Performance Assessment",
        )

        self.assertEqual(
            section.section_type,
            "performance-assessment",
        )

        self.assertEqual(
            section.order,
            20,
        )

    def test_uses_typed_assessment_payload(self):
        section = self._build_cpu_section()

        self.assertIsInstance(
            section.payload,
            PerformanceAssessmentData,
        )

        self.assertIsInstance(
            section.payload.global_metrics,
            MetricAnalysisData,
        )

    def test_builds_global_metrics_child(self):
        section = self._build_cpu_section()

        self.assertEqual(
            len(section.children),
            1,
        )

        child = section.children[0]

        self.assertEqual(
            child.section_id,
            "global-metrics",
        )

        self.assertEqual(
            child.section_type,
            "metric-analysis",
        )

        self.assertEqual(
            child.payload,
            section.payload.global_metrics,
        )

    def test_builds_expected_cpu_metrics(self):
        section = self._build_cpu_section()

        metric_ids = [
            metric.metric_id
            for metric in (
                section.payload
                .global_metrics
                .metrics
            )
        ]

        self.assertEqual(
            metric_ids,
            [
                "global_eff",
                "parallel_eff",
                "load_balance",
                "comm_eff",
                "comp_scale",
                "ipc_scale",
                "inst_scale",
                "freq_scale",
            ],
        )

    def test_excludes_runtime_communication_submetrics(self):
        section = self._build_cpu_section()

        metric_ids = {
            metric.metric_id
            for metric in (
                section.payload
                .global_metrics
                .metrics
            )
        }

        self.assertNotIn(
            "serial_eff",
            metric_ids,
        )

        self.assertNotIn(
            "transfer_eff",
            metric_ids,
        )

    def test_metrics_use_typed_objects(self):
        section = self._build_cpu_section()

        for metric in (
            section.payload
            .global_metrics
            .metrics
        ):
            self.assertIsInstance(
                metric,
                MetricAnalysisMetric,
            )

            for value in metric.values:
                self.assertIsInstance(
                    value,
                    MetricAnalysisValue,
                )

    def test_metric_values_follow_trace_order(self):
        report_data = self._cpu_report_data()

        report_data[
            "metrics"
        ][
            "mod_factors"
        ][
            "global_eff"
        ] = {
            "/tmp/trace_2.prv": 82.0,
            "/tmp/trace_1.prv": 100.0,
        }

        context = build_analysis_context(
            report_data
        )

        section = (
            PerformanceAssessmentBuilder()
            .build(context)
        )

        global_efficiency = self._metric_by_id(
            section,
            "global_eff",
        )

        self.assertEqual(
            [
                value.trace_id
                for value
                in global_efficiency.values
            ],
            [1, 2],
        )

        self.assertEqual(
            [
                value.value
                for value
                in global_efficiency.values
            ],
            [100.0, 82.0],
        )

    def test_missing_value_is_preserved(self):
        report_data = self._cpu_report_data()

        del report_data[
            "metrics"
        ][
            "mod_factors"
        ][
            "load_balance"
        ][
            "/tmp/trace_2.prv"
        ]

        context = build_analysis_context(
            report_data
        )

        section = (
            PerformanceAssessmentBuilder()
            .build(context)
        )

        load_balance = self._metric_by_id(
            section,
            "load_balance",
        )

        self.assertEqual(
            load_balance.values[0].value,
            100.0,
        )

        self.assertIsNone(
            load_balance.values[1].value,
        )

    def test_completely_unavailable_metric_is_excluded(self):
        report_data = self._cpu_report_data()

        report_data[
            "metrics"
        ][
            "mod_factors"
        ][
            "freq_scale"
        ] = {
            "/tmp/trace_1.prv": "Non-Avail",
            "/tmp/trace_2.prv": None,
        }

        context = build_analysis_context(
            report_data
        )

        section = (
            PerformanceAssessmentBuilder()
            .build(context)
        )

        metric_ids = [
            metric.metric_id
            for metric in (
                section.payload
                .global_metrics
                .metrics
            )
        ]

        self.assertNotIn(
            "freq_scale",
            metric_ids,
        )

    def test_cpu_tree_matches_global_decomposition(self):
        section = self._build_cpu_section()

        tree = (
            section.payload
            .global_metrics
            .tree
        )

        self.assertEqual(
            len(tree),
            1,
        )

        root = tree[0]

        self.assertIsInstance(
            root,
            MetricAnalysisTreeNode,
        )

        self.assertEqual(
            root.metric_id,
            "global_eff",
        )

        self.assertEqual(
            [
                child.metric_id
                for child in root.children
            ],
            [
                "parallel_eff",
                "comp_scale",
            ],
        )

        parallel = self._tree_node_by_id(
            tree,
            "parallel_eff",
        )

        self.assertEqual(
            [
                child.metric_id
                for child in parallel.children
            ],
            [
                "load_balance",
                "comm_eff",
            ],
        )

        computation = self._tree_node_by_id(
            tree,
            "comp_scale",
        )

        self.assertEqual(
            [
                child.metric_id
                for child in computation.children
            ],
            [
                "ipc_scale",
                "inst_scale",
                "freq_scale",
            ],
        )

    def test_gpu_assessment_excludes_cpu_scalability_breakdown(self):
        context = build_analysis_context(
            self._gpu_report_data()
        )

        section = (
            PerformanceAssessmentBuilder()
            .build(context)
        )

        metric_ids = [
            metric.metric_id
            for metric in (
                section.payload
                .global_metrics
                .metrics
            )
        ]

        self.assertEqual(
            metric_ids,
            [
                "global_eff",
                "parallel_eff",
                "load_balance",
                "comm_eff",
                "comp_scale",
            ],
        )

    def test_gpu_tree_keeps_computation_scalability_leaf(self):
        context = build_analysis_context(
            self._gpu_report_data()
        )

        section = (
            PerformanceAssessmentBuilder()
            .build(context)
        )

        computation = self._tree_node_by_id(
            section.payload.global_metrics.tree,
            "comp_scale",
        )

        self.assertIsNotNone(
            computation
        )

        self.assertEqual(
            computation.children,
            (),
        )

    def test_report_builder_uses_populated_assessment(self):
        context = build_analysis_context(
            self._cpu_report_data()
        )

        report = build_report_model(
            context
        )

        assessment = report.get_section(
            "performance-assessment"
        )

        global_metrics = report.get_section(
            "global-metrics"
        )

        self.assertIsNotNone(
            assessment
        )

        self.assertIsNotNone(
            global_metrics
        )

        self.assertIsInstance(
            assessment.payload,
            PerformanceAssessmentData,
        )

        self.assertIsInstance(
            global_metrics.payload,
            MetricAnalysisData,
        )

        self.assertEqual(
            global_metrics.payload,
            assessment.payload.global_metrics,
        )

    def test_empty_mod_factors_produces_empty_analysis(self):
        report_data = self._cpu_report_data()

        report_data[
            "metrics"
        ][
            "mod_factors"
        ] = {}

        context = build_analysis_context(
            report_data
        )

        section = (
            PerformanceAssessmentBuilder()
            .build(context)
        )

        analysis = (
            section.payload.global_metrics
        )

        self.assertEqual(
            analysis.metrics,
            (),
        )

        self.assertEqual(
            analysis.tree,
            (),
        )


if __name__ == "__main__":
    unittest.main(
        verbosity=2
    )