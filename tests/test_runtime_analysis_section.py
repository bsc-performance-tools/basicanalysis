"""Tests for the semantic Runtime Analysis section."""

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
    RuntimeAnalysisBuilder,
    RuntimeAnalysisData,
    RuntimeComponentAnalysis,
)


class RuntimeAnalysisBuilderTests(unittest.TestCase):
    """Validate the semantic Runtime Analysis model."""

    # ------------------------------------------------------------------
    # Test data
    # ------------------------------------------------------------------

    def _mpi_report_data(self):
        """Return representative single-runtime MPI data."""

        trace_1 = "/tmp/mpi_1.prv"
        trace_2 = "/tmp/mpi_2.prv"

        return {
            "general": {
                "analysis_kind": "simple",
                "pop_model": "classic",
            },
            "traces": [
                {
                    "id": 1,
                    "name": "mpi_1.prv",
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
                    "name": "mpi_2.prv",
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
                    "parallel_eff": {
                        trace_1: 100.0,
                        trace_2: 82.0,
                    },
                    "load_balance": {
                        trace_1: 100.0,
                        trace_2: 88.0,
                    },
                    "comm_eff": {
                        trace_1: 100.0,
                        trace_2: 93.18,
                    },
                    "serial_eff": {
                        trace_1: 100.0,
                        trace_2: 95.0,
                    },
                    "transfer_eff": {
                        trace_1: 100.0,
                        trace_2: 98.08,
                    },
                },
                "other_metrics": {},
            },
            "diagnosis": [],
            "evidence": [],
        }

    def _openmp_report_data(self):
        """Return representative single-runtime OpenMP data."""

        trace_1 = "/tmp/openmp_1.prv"
        trace_2 = "/tmp/openmp_2.prv"

        return {
            "general": {
                "analysis_kind": "simple",
                "pop_model": "classic",
            },
            "traces": [
                {
                    "id": 1,
                    "name": "openmp_1.prv",
                    "path": trace_1,
                    "mode": "Detailed+OpenMP",
                    "processes": 4,
                    "tasks": 1,
                    "threads": 4,
                    "devices": 0,
                    "gpu_streams": 0,
                    "gpu_streams_per_rank": 0,
                },
                {
                    "id": 2,
                    "name": "openmp_2.prv",
                    "path": trace_2,
                    "mode": "Detailed+OpenMP",
                    "processes": 8,
                    "tasks": 1,
                    "threads": 8,
                    "devices": 0,
                    "gpu_streams": 0,
                    "gpu_streams_per_rank": 0,
                },
            ],
            "resources": [],
            "metrics": {
                "kind": "simple",
                "mod_factors": {
                    "parallel_eff": {
                        trace_1: 100.0,
                        trace_2: 79.0,
                    },
                    "load_balance": {
                        trace_1: 100.0,
                        trace_2: 86.0,
                    },
                    "comm_eff": {
                        trace_1: 100.0,
                        trace_2: 91.86,
                    },
                },
                "omp_talp_factors": {
                    "omp_talp_parallel_eff": {
                        trace_1: 94.0,
                        trace_2: 76.0,
                    },
                    "omp_talp_serial_eff": {
                        trace_1: 98.0,
                        trace_2: 91.0,
                    },
                    "omp_talp_load_balance": {
                        trace_1: 96.0,
                        trace_2: 83.0,
                    },
                    "omp_talp_scheduling_eff": {
                        trace_1: 99.0,
                        trace_2: 92.0,
                    },
                },
                "other_metrics": {},
            },
            "diagnosis": [],
            "evidence": [],
        }

    def _mpi_openmp_report_data(self):
        """Return representative MPI+OpenMP data."""

        trace_1 = "/tmp/mpi_openmp_1.prv"
        trace_2 = "/tmp/mpi_openmp_2.prv"

        return {
            "general": {
                "analysis_kind": "hybrid",
                "pop_model": "classic",
            },
            "traces": [
                {
                    "id": 1,
                    "name": "mpi_openmp_1.prv",
                    "path": trace_1,
                    "mode": "Detailed+MPI+OpenMP",
                    "processes": 16,
                    "tasks": 4,
                    "threads": 4,
                    "devices": 0,
                    "gpu_streams": 0,
                    "gpu_streams_per_rank": 0,
                },
                {
                    "id": 2,
                    "name": "mpi_openmp_2.prv",
                    "path": trace_2,
                    "mode": "Detailed+MPI+OpenMP",
                    "processes": 32,
                    "tasks": 8,
                    "threads": 4,
                    "devices": 0,
                    "gpu_streams": 0,
                    "gpu_streams_per_rank": 0,
                },
            ],
            "resources": [],
            "metrics": {
                "kind": "hybrid",
                "mod_factors": {},
                "hybrid_factors": {
                    "hybrid_eff": {
                        trace_1: 100.0,
                        trace_2: 72.0,
                    },
                    "mpi_parallel_eff": {
                        trace_1: 100.0,
                        trace_2: 80.0,
                    },
                    "mpi_load_balance": {
                        trace_1: 100.0,
                        trace_2: 86.0,
                    },
                    "mpi_comm_eff": {
                        trace_1: 100.0,
                        trace_2: 93.02,
                    },
                    "serial_eff": {
                        trace_1: 100.0,
                        trace_2: 95.0,
                    },
                    "transfer_eff": {
                        trace_1: 100.0,
                        trace_2: 97.92,
                    },
                    "omp_parallel_eff": {
                        trace_1: 100.0,
                        trace_2: 90.0,
                    },
                    "omp_load_balance": {
                        trace_1: 100.0,
                        trace_2: 94.0,
                    },
                    "omp_comm_eff": {
                        trace_1: 100.0,
                        trace_2: 95.74,
                    },
                },
                "hyb_comm_omp_factors": {
                    "omp_serial_eff": {
                        trace_1: 100.0,
                        trace_2: 97.0,
                    },
                    "omp_transfer_eff": {
                        trace_1: 100.0,
                        trace_2: 98.7,
                    },
                },
                "omp_talp_factors": {
                    "omp_talp_parallel_eff": {
                        trace_1: 93.0,
                        trace_2: 78.0,
                    },
                    "omp_talp_serial_eff": {
                        trace_1: 98.0,
                        trace_2: 92.0,
                    },
                    "omp_talp_load_balance": {
                        trace_1: 95.0,
                        trace_2: 84.0,
                    },
                    "omp_talp_scheduling_eff": {
                        trace_1: 99.0,
                        trace_2: 91.0,
                    },
                },
                "other_metrics": {},
            },
            "diagnosis": [],
            "evidence": [],
        }

    def _mpi_cuda_report_data(self):
        """Return representative MPI+CUDA data."""

        trace_1 = "/tmp/mpi_cuda_1.prv"
        trace_2 = "/tmp/mpi_cuda_2.prv"

        return {
            "general": {
                "analysis_kind": "hybrid",
                "pop_model": "classic",
            },
            "traces": [
                {
                    "id": 1,
                    "name": "mpi_cuda_1.prv",
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
                    "name": "mpi_cuda_2.prv",
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
                "mod_factors": {},
                "hybrid_factors": {
                    "hybrid_eff": {
                        trace_1: 100.0,
                        trace_2: 65.0,
                    },
                    "mpi_parallel_eff": {
                        trace_1: 100.0,
                        trace_2: 81.0,
                    },
                    "mpi_load_balance": {
                        trace_1: 100.0,
                        trace_2: 87.0,
                    },
                    "mpi_comm_eff": {
                        trace_1: 100.0,
                        trace_2: 93.10,
                    },
                    "serial_eff": {
                        trace_1: 100.0,
                        trace_2: 95.0,
                    },
                    "transfer_eff": {
                        trace_1: 100.0,
                        trace_2: 98.0,
                    },
                    "omp_parallel_eff": {
                        trace_1: 100.0,
                        trace_2: 80.25,
                    },
                    "omp_load_balance": {
                        trace_1: 100.0,
                        trace_2: 88.0,
                    },
                    "omp_comm_eff": {
                        trace_1: 100.0,
                        trace_2: 91.19,
                    },
                },
                "hyb_comm_omp_factors": {},
                "omp_talp_factors": {},
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
        context = build_analysis_context(report_data)
        return RuntimeAnalysisBuilder().build(context)

    @staticmethod
    def _metric_ids(analysis):
        return [
            metric.metric_id
            for metric in analysis.metrics
        ]

    @staticmethod
    def _component_by_id(section, component_id):
        for component in section.payload.runtime_components:
            if component.component_id == component_id:
                return component

        raise AssertionError(
            "Runtime component {!r} was not created.".format(
                component_id
            )
        )

    @staticmethod
    def _metric_by_id(analysis, metric_id):
        for metric in analysis.metrics:
            if metric.metric_id == metric_id:
                return metric

        raise AssertionError(
            "Metric {!r} was not created.".format(
                metric_id
            )
        )

    @staticmethod
    def _tree_node_by_id(nodes, metric_id):
        for node in nodes:
            if node.metric_id == metric_id:
                return node

            result = RuntimeAnalysisBuilderTests._tree_node_by_id(
                node.children,
                metric_id,
            )

            if result is not None:
                return result

        return None

    # ------------------------------------------------------------------
    # Generic section tests
    # ------------------------------------------------------------------

    def test_builds_runtime_analysis_section(self):
        section = self._build_section(
            self._mpi_report_data()
        )

        self.assertEqual(
            section.section_id,
            "runtime-analysis",
        )
        self.assertEqual(
            section.title,
            "Runtime Analysis",
        )
        self.assertEqual(
            section.section_type,
            "runtime-analysis",
        )
        self.assertEqual(
            section.order,
            30,
        )

    def test_uses_typed_runtime_payload(self):
        section = self._build_section(
            self._mpi_report_data()
        )

        self.assertIsInstance(
            section.payload,
            RuntimeAnalysisData,
        )
        self.assertIsInstance(
            section.payload.parallel_runtime_model,
            MetricAnalysisData,
        )
        self.assertIsInstance(
            section.payload.runtime_components,
            tuple,
        )

    def test_builds_parallel_runtime_model_child(self):
        section = self._build_section(
            self._mpi_report_data()
        )

        child = section.children[0]

        self.assertEqual(
            child.section_id,
            "parallel-runtime-model",
        )
        self.assertEqual(
            child.section_type,
            "parallel-runtime-model",
        )
        self.assertEqual(
            child.payload,
            section.payload.parallel_runtime_model,
        )

    # ------------------------------------------------------------------
    # Single-runtime MPI
    # ------------------------------------------------------------------

    def test_builds_single_mpi_runtime_model(self):
        section = self._build_section(
            self._mpi_report_data()
        )

        analysis = section.payload.parallel_runtime_model

        self.assertEqual(
            analysis.title,
            "MPI Parallel Runtime Model",
        )

        self.assertEqual(
            self._metric_ids(analysis),
            [
                "parallel_eff",
                "load_balance",
                "comm_eff",
                "serial_eff",
                "transfer_eff",
            ],
        )

        self.assertEqual(
            analysis.tree[0].metric_id,
            "parallel_eff",
        )

    def test_single_mpi_tree_has_communication_children(self):
        section = self._build_section(
            self._mpi_report_data()
        )

        tree = section.payload.parallel_runtime_model.tree

        communication = self._tree_node_by_id(
            tree,
            "comm_eff",
        )

        self.assertIsNotNone(
            communication
        )

        self.assertEqual(
            [
                child.metric_id
                for child in communication.children
            ],
            [
                "serial_eff",
                "transfer_eff",
            ],
        )

    def test_single_mpi_does_not_duplicate_runtime_component(self):
        section = self._build_section(
            self._mpi_report_data()
        )

        self.assertEqual(
            section.payload.runtime_components,
            (),
        )

        child_ids = [
            child.section_id
            for child in section.children
        ]

        self.assertEqual(
            child_ids,
            [
                "parallel-runtime-model",
            ],
        )



    # ------------------------------------------------------------------
    # OpenMP
    # ------------------------------------------------------------------

    def test_openmp_builds_isolated_runtime_component(self):
        section = self._build_section(
            self._openmp_report_data()
        )

        openmp_component = self._component_by_id(
            section,
            "openmp-runtime",
        )

        self.assertEqual(
            openmp_component.runtime_name,
            "OpenMP",
        )
        self.assertEqual(
            openmp_component.analysis_kind,
            "runtime-specific-analysis",
        )

        self.assertEqual(
            self._metric_ids(openmp_component.metrics),
            [
                "omp_talp_parallel_eff",
                "omp_talp_serial_eff",
                "omp_talp_load_balance",
                "omp_talp_scheduling_eff",
            ],
        )

    def test_openmp_tree_represents_runtime_specific_metrics(self):
        section = self._build_section(
            self._openmp_report_data()
        )

        openmp_component = self._component_by_id(
            section,
            "openmp-runtime",
        )

        root = openmp_component.metrics.tree[0]

        self.assertEqual(
            root.metric_id,
            "omp_talp_parallel_eff",
        )

        self.assertEqual(
            [
                child.metric_id
                for child in root.children
            ],
            [
                "omp_talp_serial_eff",
                "omp_talp_load_balance",
                "omp_talp_scheduling_eff",
            ],
        )

    # ------------------------------------------------------------------
    # MPI+OpenMP
    # ------------------------------------------------------------------

    def test_builds_mpi_openmp_composed_model(self):
        section = self._build_section(
            self._mpi_openmp_report_data()
        )

        analysis = section.payload.parallel_runtime_model

        self.assertEqual(
            analysis.title,
            "Parallel Runtime Model: MPI + OpenMP",
        )

        self.assertEqual(
            self._metric_ids(analysis),
            [
                "hybrid_eff",
                "mpi_parallel_eff",
                "mpi_load_balance",
                "mpi_comm_eff",
                "serial_eff",
                "transfer_eff",
                "omp_parallel_eff",
                "omp_load_balance",
                "omp_comm_eff",
                "omp_serial_eff",
                "omp_transfer_eff",
            ],
        )

    def test_mpi_openmp_builds_two_runtime_components(self):
        section = self._build_section(
            self._mpi_openmp_report_data()
        )

        component_ids = [
            component.component_id
            for component in section.payload.runtime_components
        ]

        self.assertEqual(
            component_ids,
            [
                "mpi-runtime",
                "openmp-runtime",
            ],
        )

    def test_mpi_openmp_composed_tree_has_two_runtime_branches(self):
        section = self._build_section(
            self._mpi_openmp_report_data()
        )

        root = section.payload.parallel_runtime_model.tree[0]

        self.assertEqual(
            root.metric_id,
            "hybrid_eff",
        )

        self.assertEqual(
            [
                child.metric_id
                for child in root.children
            ],
            [
                "mpi_parallel_eff",
                "omp_parallel_eff",
            ],
        )

        openmp_communication = self._tree_node_by_id(
            root.children,
            "omp_comm_eff",
        )

        self.assertEqual(
            [
                child.metric_id
                for child in openmp_communication.children
            ],
            [
                "omp_serial_eff",
                "omp_transfer_eff",
            ],
        )

    # ------------------------------------------------------------------
    # MPI+CUDA
    # ------------------------------------------------------------------

    def test_builds_mpi_cuda_composed_model(self):
        section = self._build_section(
            self._mpi_cuda_report_data()
        )

        analysis = section.payload.parallel_runtime_model

        self.assertEqual(
            analysis.title,
            "Parallel Runtime Model: MPI + CUDA",
        )

        self.assertEqual(
            self._metric_ids(analysis),
            [
                "hybrid_eff",
                "mpi_parallel_eff",
                "mpi_load_balance",
                "mpi_comm_eff",
                "serial_eff",
                "transfer_eff",
                "omp_parallel_eff",
                "omp_load_balance",
                "omp_comm_eff",
            ],
        )

    def test_mpi_cuda_builds_mpi_and_accelerator_components(self):
        section = self._build_section(
            self._mpi_cuda_report_data()
        )

        component_ids = [
            component.component_id
            for component in section.payload.runtime_components
        ]

        self.assertEqual(
            component_ids,
            [
                "mpi-runtime",
                "accelerator-runtime",
            ],
        )

        accelerator = self._component_by_id(
            section,
            "accelerator-runtime",
        )

        self.assertEqual(
            accelerator.runtime_name,
            "CUDA",
        )
        self.assertEqual(
            accelerator.analysis_kind,
            "runtime-contribution-analysis",
        )

    def test_accelerator_component_is_a_contribution_model(self):
        section = self._build_section(
            self._mpi_cuda_report_data()
        )

        accelerator = self._component_by_id(
            section,
            "accelerator-runtime",
        )

        self.assertEqual(
            self._metric_ids(accelerator.metrics),
            [
                "omp_parallel_eff",
                "omp_load_balance",
                "omp_comm_eff",
            ],
        )

        self.assertIn(
            "not an isolated",
            accelerator.metrics.description,
        )

        self.assertEqual(
            accelerator.metrics.tree[0].metric_id,
            "omp_parallel_eff",
        )

    # ------------------------------------------------------------------
    # Metric extraction and filtering
    # ------------------------------------------------------------------

    def test_metric_values_follow_context_trace_order(self):
        report_data = self._mpi_report_data()

        report_data[
            "metrics"
        ][
            "mod_factors"
        ][
            "parallel_eff"
        ] = {
            "/tmp/mpi_2.prv": 82.0,
            "/tmp/mpi_1.prv": 100.0,
        }

        section = self._build_section(
            report_data
        )

        analysis = section.payload.parallel_runtime_model

        parallel_efficiency = self._metric_by_id(
            analysis,
            "parallel_eff",
        )

        self.assertEqual(
            [
                value.trace_id
                for value in parallel_efficiency.values
            ],
            [1, 2],
        )

        self.assertEqual(
            [
                value.value
                for value in parallel_efficiency.values
            ],
            [100.0, 82.0],
        )

    def test_missing_trace_value_is_none(self):
        report_data = self._mpi_report_data()

        del report_data[
            "metrics"
        ][
            "mod_factors"
        ][
            "load_balance"
        ][
            "/tmp/mpi_2.prv"
        ]

        section = self._build_section(
            report_data
        )

        load_balance = self._metric_by_id(
            section.payload.parallel_runtime_model,
            "load_balance",
        )

        self.assertEqual(
            load_balance.values[0].value,
            100.0,
        )
        self.assertIsNone(
            load_balance.values[1].value,
        )

    def test_completely_unavailable_metric_is_excluded_and_pruned(self):
        report_data = self._mpi_report_data()

        report_data[
            "metrics"
        ][
            "mod_factors"
        ][
            "transfer_eff"
        ] = {
            "/tmp/mpi_1.prv": "Non-Avail",
            "/tmp/mpi_2.prv": None,
        }

        section = self._build_section(
            report_data
        )

        analysis = section.payload.parallel_runtime_model

        self.assertNotIn(
            "transfer_eff",
            self._metric_ids(analysis),
        )

        communication = self._tree_node_by_id(
            analysis.tree,
            "comm_eff",
        )

        self.assertEqual(
            [
                child.metric_id
                for child in communication.children
            ],
            ["serial_eff"],
        )

    def test_typed_metric_objects_are_used(self):
        section = self._build_section(
            self._mpi_openmp_report_data()
        )

        analysis = section.payload.parallel_runtime_model

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

    def test_report_builder_uses_populated_runtime_analysis(self):
        context = build_analysis_context(
            self._mpi_cuda_report_data()
        )

        report = build_report_model(
            context
        )

        runtime = report.get_section(
            "runtime-analysis"
        )
        runtime_model = report.get_section(
            "parallel-runtime-model"
        )
        mpi = report.get_section(
            "mpi-runtime"
        )
        accelerator = report.get_section(
            "accelerator-runtime"
        )

        self.assertIsNotNone(runtime)
        self.assertIsNotNone(runtime_model)
        self.assertIsNotNone(mpi)
        self.assertIsNotNone(accelerator)

        self.assertIsInstance(
            runtime.payload,
            RuntimeAnalysisData,
        )

        self.assertEqual(
            runtime_model.payload,
            runtime.payload.parallel_runtime_model,
        )

        self.assertIsInstance(
            mpi.payload,
            RuntimeComponentAnalysis,
        )
        self.assertIsInstance(
            accelerator.payload,
            RuntimeComponentAnalysis,
        )

    def test_empty_metrics_produce_empty_runtime_model(self):
        report_data = self._mpi_report_data()

        report_data[
            "metrics"
        ][
            "mod_factors"
        ] = {}

        section = self._build_section(
            report_data
        )

        analysis = section.payload.parallel_runtime_model

        self.assertEqual(
            analysis.metrics,
            (),
        )
        self.assertEqual(
            analysis.tree,
            (),
        )
        self.assertEqual(
            section.payload.runtime_components,
            (),
        )


if __name__ == "__main__":
    unittest.main(
        verbosity=2
    )