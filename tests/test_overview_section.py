"""Tests for the semantic Overview report section."""

import unittest

from report import build_analysis_context
from report.sections import (
    OverviewBuilder,
    OverviewData,
    OverviewMetric,
    OverviewMetricValue,
)


class OverviewBuilderTests(unittest.TestCase):
    """Validate the semantic structure produced by OverviewBuilder."""

    def _report_data(self):
        """Return representative report data containing two traces."""

        return {
            "general": {
                "analysis_kind": "hybrid",
                "pop_model": "classic",
            },
            "traces": [
                {
                    "id": 1,
                    "name": "trace_1.prv",
                    "path": "/tmp/trace_1.prv",
                    "mode": "Detailed+MPI+OpenMP",
                    "processes": 8,
                    "tasks": 4,
                    "threads": 2,
                    "devices": 0,
                    "gpu_streams": 0,
                    "gpu_streams_per_rank": 0,
                },
                {
                    "id": 2,
                    "name": "trace_2.prv",
                    "path": "/tmp/trace_2.prv",
                    "mode": "Detailed+MPI+OpenMP",
                    "processes": 16,
                    "tasks": 8,
                    "threads": 2,
                    "devices": 0,
                    "gpu_streams": 0,
                    "gpu_streams_per_rank": 0,
                },
            ],
            "resources": [
                {
                    "trace": "/tmp/trace_1.prv",
                    "prv": "/tmp/trace_1.prv",
                    "pcf": "/tmp/trace_1.pcf",
                    "row": "/tmp/trace_1.row",
                    "overview_cfg": "/tmp/useful_duration.cfg",
                    "cfgs": [],
                    "images": [],
                },
                {
                    "trace": "/tmp/trace_2.prv",
                    "prv": "/tmp/trace_2.prv",
                    "pcf": "/tmp/trace_2.pcf",
                    "row": "/tmp/trace_2.row",
                    "overview_cfg": "/tmp/useful_duration.cfg",
                    "cfgs": [],
                    "images": [],
                },
            ],
            "metrics": {
                "other_metrics": {
                    "elapsed_time": {
                        "/tmp/trace_1.prv": 100.0,
                        "/tmp/trace_2.prv": 60.0,
                    },
                    "efficiency": {
                        "/tmp/trace_1.prv": 1.0,
                        "/tmp/trace_2.prv": 0.83,
                    },
                    "speedup": {
                        "/tmp/trace_1.prv": 1.0,
                        "/tmp/trace_2.prv": 1.67,
                    },
                    "ipc": {
                        "/tmp/trace_1.prv": 1.50,
                        "/tmp/trace_2.prv": 1.70,
                    },
                    "freq": {
                        "/tmp/trace_1.prv": 2.40,
                        "/tmp/trace_2.prv": 2.30,
                    },
                }
            },
            "diagnosis": [],
            "evidence": [],
        }

    def _build_section(self):
        """Build the Overview section used by most tests."""

        context = build_analysis_context(self._report_data())
        return OverviewBuilder().build(context)

    @staticmethod
    def _metric_by_id(section, metric_id):
        """Return one Overview metric by its semantic identifier."""

        for metric in section.payload.general_metrics:
            if metric.metric_id == metric_id:
                return metric

        raise AssertionError(
            f"Overview metric {metric_id!r} was not created"
        )

    def test_builds_overview_section(self):
        section = self._build_section()

        self.assertEqual(section.section_id, "overview")
        self.assertEqual(section.title, "Overview")
        self.assertEqual(section.section_type, "overview")
        self.assertEqual(section.order, 10)

    def test_uses_typed_overview_payload(self):
        section = self._build_section()

        self.assertIsInstance(
            section.payload,
            OverviewData,
        )

        self.assertEqual(
            section.payload.general.analysis_kind,
            "hybrid",
        )

        self.assertEqual(
            section.payload.general.pop_model,
            "classic",
        )

        self.assertEqual(
            len(section.payload.traces),
            2,
        )

        self.assertEqual(
            len(section.payload.resources),
            2,
        )

        self.assertEqual(
            len(section.payload.general_metrics),
            5,
        )

    def test_builds_expected_children(self):
        section = self._build_section()

        child_ids = [
            child.section_id
            for child in section.children
        ]

        self.assertEqual(
            child_ids,
            [
                "trace-configuration",
                "general-information",
                "general-metrics",
                "paraver-validation",
            ],
        )

    def test_builds_children_in_expected_order(self):
        section = self._build_section()

        child_orders = [
            child.order
            for child in section.children
        ]

        self.assertEqual(
            child_orders,
            [10, 20, 30, 40],
        )

    def test_child_payloads_reference_overview_data(self):
        section = self._build_section()

        trace_section = section.children[0]
        general_section = section.children[1]
        metrics_section = section.children[2]
        resource_section = section.children[3]

        self.assertEqual(
            trace_section.payload,
            section.payload.traces,
        )

        self.assertEqual(
            general_section.payload,
            section.payload.general,
        )

        self.assertEqual(
            metrics_section.payload,
            section.payload.general_metrics,
        )

        self.assertEqual(
            resource_section.payload,
            section.payload.resources,
        )

    def test_builds_expected_general_metrics(self):
        section = self._build_section()

        metric_ids = [
            metric.metric_id
            for metric in section.payload.general_metrics
        ]

        self.assertEqual(
            metric_ids,
            [
                "elapsed_time",
                "efficiency",
                "speedup",
                "ipc",
                "freq",
            ],
        )

    def test_general_metrics_use_typed_objects(self):
        section = self._build_section()

        for metric in section.payload.general_metrics:
            self.assertIsInstance(
                metric,
                OverviewMetric,
            )

            self.assertIsInstance(
                metric.values,
                tuple,
            )

            for metric_value in metric.values:
                self.assertIsInstance(
                    metric_value,
                    OverviewMetricValue,
                )

    def test_general_metric_metadata(self):
        section = self._build_section()

        elapsed_time = self._metric_by_id(
            section,
            "elapsed_time",
        )

        efficiency = self._metric_by_id(
            section,
            "efficiency",
        )

        ipc = self._metric_by_id(
            section,
            "ipc",
        )

        self.assertEqual(
            elapsed_time.label,
            "Elapsed time (s)",
        )
        self.assertEqual(
            elapsed_time.group,
            "Runtime",
        )

        self.assertEqual(
            efficiency.label,
            "Efficiency",
        )
        self.assertEqual(
            efficiency.group,
            "Performance",
        )

        self.assertEqual(
            ipc.label,
            "Average IPC (inst/cycle)",
        )
        self.assertEqual(
            ipc.group,
            "Microarchitecture",
        )

    def test_general_metric_values_are_extracted(self):
        section = self._build_section()

        elapsed_time = self._metric_by_id(
            section,
            "elapsed_time",
        )

        efficiency = self._metric_by_id(
            section,
            "efficiency",
        )

        ipc = self._metric_by_id(
            section,
            "ipc",
        )

        self.assertEqual(
            [value.value for value in elapsed_time.values],
            [100.0, 60.0],
        )

        self.assertEqual(
            [value.value for value in efficiency.values],
            [1.0, 0.83],
        )

        self.assertEqual(
            [value.value for value in ipc.values],
            [1.50, 1.70],
        )

    def test_general_metric_values_reference_trace_ids(self):
        section = self._build_section()

        elapsed_time = self._metric_by_id(
            section,
            "elapsed_time",
        )

        self.assertEqual(
            [value.trace_id for value in elapsed_time.values],
            [1, 2],
        )

    def test_general_metrics_follow_context_trace_order(self):
        report_data = self._report_data()

        # Reverse the order in the source metric mapping. The semantic
        # output must still follow the order of report_data["traces"].
        report_data["metrics"]["other_metrics"]["elapsed_time"] = {
            "/tmp/trace_2.prv": 60.0,
            "/tmp/trace_1.prv": 100.0,
        }

        context = build_analysis_context(report_data)
        section = OverviewBuilder().build(context)

        elapsed_time = self._metric_by_id(
            section,
            "elapsed_time",
        )

        self.assertEqual(
            [value.trace_id for value in elapsed_time.values],
            [1, 2],
        )

        self.assertEqual(
            [value.value for value in elapsed_time.values],
            [100.0, 60.0],
        )

    def test_missing_metric_value_is_none(self):
        report_data = self._report_data()

        del report_data[
            "metrics"
        ][
            "other_metrics"
        ][
            "ipc"
        ][
            "/tmp/trace_2.prv"
        ]

        context = build_analysis_context(report_data)
        section = OverviewBuilder().build(context)

        ipc = self._metric_by_id(
            section,
            "ipc",
        )

        self.assertEqual(
            ipc.values[0].value,
            1.50,
        )

        self.assertIsNone(
            ipc.values[1].value,
        )

    def test_missing_complete_metric_is_represented(self):
        report_data = self._report_data()

        del report_data[
            "metrics"
        ][
            "other_metrics"
        ][
            "freq"
        ]

        context = build_analysis_context(report_data)
        section = OverviewBuilder().build(context)

        frequency = self._metric_by_id(
            section,
            "freq",
        )

        self.assertEqual(
            len(frequency.values),
            2,
        )

        self.assertEqual(
            [value.value for value in frequency.values],
            [None, None],
        )

    def test_empty_metrics_do_not_break_overview(self):
        report_data = self._report_data()
        report_data["metrics"] = {}

        context = build_analysis_context(report_data)
        section = OverviewBuilder().build(context)

        self.assertEqual(
            len(section.payload.general_metrics),
            5,
        )

        for metric in section.payload.general_metrics:
            self.assertEqual(
                len(metric.values),
                2,
            )

            self.assertTrue(
                all(
                    value.value is None
                    for value in metric.values
                )
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)