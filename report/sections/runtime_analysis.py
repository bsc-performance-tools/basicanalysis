"""Semantic builder for the Runtime Analysis report section."""

from __future__ import annotations

import math

from dataclasses import dataclass
from typing import Any, Mapping, Optional, Set, Tuple

from ..model import (
    AnalysisContext,
    ReportSection,
    TraceInfo,
)

from .metric_analysis import (
    MetricAnalysisData,
    MetricAnalysisMetric,
    MetricAnalysisTreeNode,
    MetricAnalysisValue,
)


# ---------------------------------------------------------------------------
# Single-runtime Parallel Runtime Model
# ---------------------------------------------------------------------------

_SIMPLE_RUNTIME_METRICS = (
    (
        "parallel_eff",
        "{runtime} Parallel efficiency",
        "runtime",
        0,
    ),
    (
        "load_balance",
        "{runtime} Load balance",
        "runtime",
        1,
    ),
    (
        "comm_eff",
        "{runtime} Communication efficiency",
        "runtime",
        1,
    ),
    (
        "serial_eff",
        "{runtime} Serialization efficiency",
        "runtime",
        2,
    ),
    (
        "transfer_eff",
        "{runtime} Transfer efficiency",
        "runtime",
        2,
    ),
)


# ---------------------------------------------------------------------------
# Composed MPI+X Parallel Runtime Model
# ---------------------------------------------------------------------------

_HYBRID_RUNTIME_METRICS = (
    (
        "hybrid_eff",
        "Hybrid Parallel efficiency",
        "hybrid",
        0,
    ),
    (
        "mpi_parallel_eff",
        "MPI Parallel efficiency",
        "mpi",
        1,
    ),
    (
        "mpi_load_balance",
        "MPI Load balance",
        "mpi",
        2,
    ),
    (
        "mpi_comm_eff",
        "MPI Communication efficiency",
        "mpi",
        2,
    ),
    (
        "serial_eff",
        "MPI Serialization efficiency",
        "mpi",
        3,
    ),
    (
        "transfer_eff",
        "MPI Transfer efficiency",
        "mpi",
        3,
    ),
    (
        "omp_parallel_eff",
        "{runtime} Parallel efficiency",
        "inner-runtime",
        1,
    ),
    (
        "omp_load_balance",
        "{runtime} Load balance",
        "inner-runtime",
        2,
    ),
    (
        "omp_comm_eff",
        "{runtime} Communication efficiency",
        "inner-runtime",
        2,
    ),
)


# Optional communication sub-metrics for the inner runtime.
#
# These metrics currently come from ``hyb_comm_omp_factors`` and are normally
# available for MPI+OpenMP analyses when the corresponding option is enabled.
_INNER_COMMUNICATION_METRICS = (
    (
        "omp_serial_eff",
        "{runtime} Serialization efficiency",
        "inner-runtime",
        3,
    ),
    (
        "omp_transfer_eff",
        "{runtime} Transfer efficiency",
        "inner-runtime",
        3,
    ),
)


# ---------------------------------------------------------------------------
# MPI runtime component in a hybrid execution
# ---------------------------------------------------------------------------

_MPI_HYBRID_COMPONENT_METRICS = (
    (
        "mpi_parallel_eff",
        "MPI Parallel efficiency",
        "mpi",
        0,
    ),
    (
        "mpi_load_balance",
        "MPI Load balance",
        "mpi",
        1,
    ),
    (
        "mpi_comm_eff",
        "MPI Communication efficiency",
        "mpi",
        1,
    ),
    (
        "serial_eff",
        "MPI Serialization efficiency",
        "mpi",
        2,
    ),
    (
        "transfer_eff",
        "MPI Transfer efficiency",
        "mpi",
        2,
    ),
)


# ---------------------------------------------------------------------------
# Isolated OpenMP runtime-specific model
# ---------------------------------------------------------------------------

_OPENMP_RUNTIME_METRICS = (
    (
        "omp_talp_parallel_eff",
        "OpenMP Parallel efficiency",
        "openmp",
        0,
    ),
    (
        "omp_talp_serial_eff",
        "OpenMP Serial efficiency",
        "openmp",
        1,
    ),
    (
        "omp_talp_load_balance",
        "OpenMP Region Load balance",
        "openmp",
        1,
    ),
    (
        "omp_talp_scheduling_eff",
        "OpenMP Scheduling efficiency",
        "openmp",
        1,
    ),
)


# ---------------------------------------------------------------------------
# Accelerator contribution inside the composed MPI+accelerator model
# ---------------------------------------------------------------------------

_ACCELERATOR_CONTRIBUTION_METRICS = (
    (
        "omp_parallel_eff",
        "{runtime} Parallel efficiency contribution",
        "accelerator",
        0,
    ),
    (
        "omp_load_balance",
        "{runtime} Load balance contribution",
        "accelerator",
        1,
    ),
    (
        "omp_comm_eff",
        "{runtime} Communication efficiency contribution",
        "accelerator",
        1,
    ),
)


@dataclass(frozen=True)
class RuntimeComponentAnalysis:
    """One selectable runtime component analysis.

    ``analysis_kind`` distinguishes an isolated runtime-specific model from a
    runtime contribution derived from a composed hybrid model.
    """

    component_id: str
    runtime_name: str
    analysis_kind: str
    metrics: MetricAnalysisData


@dataclass(frozen=True)
class RuntimeAnalysisData:
    """Semantic information presented in Runtime Analysis."""

    parallel_runtime_model: MetricAnalysisData
    runtime_components: Tuple[RuntimeComponentAnalysis, ...]


class RuntimeAnalysisBuilder:
    """Build the Parallel Runtime Model and runtime component analyses."""

    def build(
        self,
        context: AnalysisContext,
    ) -> ReportSection:
        """Build and return the complete Runtime Analysis section."""

        context.validate()

        parallel_runtime_model = self._build_parallel_runtime_model(
            context
        )

        runtime_components = self._build_runtime_components(
            context
        )

        runtime_data = RuntimeAnalysisData(
            parallel_runtime_model=parallel_runtime_model,
            runtime_components=runtime_components,
        )

        section = ReportSection(
            section_id="runtime-analysis",
            title="Runtime Analysis",
            navigation_label="Runtime Analysis",
            description=(
                "Attribute parallel-efficiency losses to the active runtimes "
                "and inspect runtime-specific behavior."
            ),
            section_type="runtime-analysis",
            order=30,
            payload=runtime_data,
        )

        section.add_child(
            ReportSection(
                section_id="parallel-runtime-model",
                title="Parallel Runtime Model",
                navigation_label="Parallel Runtime Model",
                description=(
                    "Runtime-level decomposition of Parallel Efficiency "
                    "across the active parallel runtimes."
                ),
                section_type="parallel-runtime-model",
                order=10,
                payload=parallel_runtime_model,
            )
        )

        component_order = 20

        for component in runtime_components:
            section.add_child(
                ReportSection(
                    section_id=component.component_id,
                    title=component.metrics.title,
                    navigation_label=component.runtime_name,
                    description=component.metrics.description,
                    section_type=component.analysis_kind,
                    order=component_order,
                    payload=component,
                )
            )

            component_order += 10

        return section

    # ------------------------------------------------------------------
    # Parallel Runtime Model construction
    # ------------------------------------------------------------------

    def _build_parallel_runtime_model(
        self,
        context: AnalysisContext,
    ) -> MetricAnalysisData:
        """Build the single-runtime or composed hybrid runtime model."""

        if self._is_hybrid(context):
            return self._build_hybrid_runtime_model(
                context
            )

        return self._build_single_runtime_model(
            context
        )

    def _build_single_runtime_model(
        self,
        context: AnalysisContext,
    ) -> MetricAnalysisData:
        """Build the Parallel Runtime Model for a single runtime."""

        runtime_name = self._single_runtime_name(
            context
        )

        mod_factors = self._get_metric_group(
            context=context,
            group_name="mod_factors",
        )

        metrics = self._build_available_metrics(
            context=context,
            source=mod_factors,
            definitions=_SIMPLE_RUNTIME_METRICS,
            runtime_name=runtime_name,
        )

        available_ids = {
            metric.metric_id
            for metric in metrics
        }

        tree = self._build_simple_runtime_tree(
            available_ids
        )

        return MetricAnalysisData(
            analysis_id="parallel-runtime-model",
            title="{} Parallel Runtime Model".format(
                runtime_name
            ),
            description=(
                "Runtime-level decomposition of Parallel Efficiency into "
                "load-balance and communication effects."
            ),
            metrics=metrics,
            tree=tree,
        )

    def _build_hybrid_runtime_model(
        self,
        context: AnalysisContext,
    ) -> MetricAnalysisData:
        """Build the composed MPI+X Parallel Runtime Model."""

        inner_runtime = self._inner_runtime_name(
            context
        )

        hybrid_factors = self._get_metric_group(
            context=context,
            group_name="hybrid_factors",
        )

        inner_communication_factors = self._get_metric_group(
            context=context,
            group_name="hyb_comm_omp_factors",
        )

        metrics = list(
            self._build_available_metrics(
                context=context,
                source=hybrid_factors,
                definitions=_HYBRID_RUNTIME_METRICS,
                runtime_name=inner_runtime,
            )
        )

        # The optional inner-runtime Serialization and Transfer metrics are
        # stored separately from the main hybrid-factor dictionary.
        metrics.extend(
            self._build_available_metrics(
                context=context,
                source=inner_communication_factors,
                definitions=_INNER_COMMUNICATION_METRICS,
                runtime_name=inner_runtime,
            )
        )

        metrics_tuple = tuple(metrics)

        available_ids = {
            metric.metric_id
            for metric in metrics_tuple
        }

        tree = self._build_hybrid_runtime_tree(
            available_ids
        )

        return MetricAnalysisData(
            analysis_id="parallel-runtime-model",
            title="Parallel Runtime Model: MPI + {}".format(
                inner_runtime
            ),
            description=(
                "Multiplicative decomposition of Parallel Efficiency across "
                "the active MPI and {} runtimes.".format(
                    inner_runtime
                )
            ),
            metrics=metrics_tuple,
            tree=tree,
        )

    # ------------------------------------------------------------------
    # Runtime component construction
    # ------------------------------------------------------------------

    def _build_runtime_components(
        self,
        context: AnalysisContext,
    ) -> Tuple[RuntimeComponentAnalysis, ...]:
        """Build the analyses exposed by the runtime component selector.

        A single-runtime MPI execution does not expose an MPI component because
        its Parallel Runtime Model already represents the complete MPI runtime
        analysis.
        """
        components = []

        if (
            self._is_hybrid(context)
            and self._has_runtime(
                context,
                "MPI",
            )
        ):
            mpi_component = self._build_mpi_component(
                context
            )

            if mpi_component is not None:
                components.append(
                    mpi_component
                )
    
        if self._has_runtime(
            context,
            "OPENMP",
        ):
            openmp_component = self._build_openmp_component(
                context
            )

            if openmp_component is not None:
                components.append(
                    openmp_component
                )

        if (
            self._is_hybrid(context)
            and self._has_accelerator(context)
        ):
            accelerator_component = (
                self._build_accelerator_component(
                    context
                )
            )

            if accelerator_component is not None:
                components.append(
                    accelerator_component
                )

        return tuple(components)

    def _build_mpi_component(
        self,
        context: AnalysisContext,
    ) -> Optional[RuntimeComponentAnalysis]:
        """Build the selectable MPI runtime analysis."""

        if self._is_hybrid(context):
            source = self._get_metric_group(
                context=context,
                group_name="hybrid_factors",
            )

            definitions = _MPI_HYBRID_COMPONENT_METRICS
            title = "MPI Runtime-Specific Analysis"
            description = (
                "MPI-specific diagnosis of load imbalance, serialization, "
                "and data-transfer overhead."
            )

            metrics = self._build_available_metrics(
                context=context,
                source=source,
                definitions=definitions,
                runtime_name="MPI",
            )

            available_ids = {
                metric.metric_id
                for metric in metrics
            }

            tree = self._build_mpi_hybrid_tree(
                available_ids
            )

        else:
            source = self._get_metric_group(
                context=context,
                group_name="mod_factors",
            )

            definitions = _SIMPLE_RUNTIME_METRICS
            title = "MPI Runtime Analysis"
            description = (
                "MPI runtime decomposition of Parallel Efficiency."
            )

            metrics = self._build_available_metrics(
                context=context,
                source=source,
                definitions=definitions,
                runtime_name="MPI",
            )

            available_ids = {
                metric.metric_id
                for metric in metrics
            }

            tree = self._build_simple_runtime_tree(
                available_ids
            )

        if not metrics:
            return None

        analysis = MetricAnalysisData(
            analysis_id="mpi-runtime",
            title=title,
            description=description,
            metrics=metrics,
            tree=tree,
        )

        return RuntimeComponentAnalysis(
            component_id="mpi-runtime",
            runtime_name="MPI",
            analysis_kind="runtime-specific-analysis",
            metrics=analysis,
        )

    def _build_openmp_component(
        self,
        context: AnalysisContext,
    ) -> Optional[RuntimeComponentAnalysis]:
        """Build the isolated OpenMP runtime-specific analysis."""

        source = self._get_metric_group(
            context=context,
            group_name="omp_talp_factors",
        )

        metrics = self._build_available_metrics(
            context=context,
            source=source,
            definitions=_OPENMP_RUNTIME_METRICS,
            runtime_name="OpenMP",
        )

        if not metrics:
            return None

        available_ids = {
            metric.metric_id
            for metric in metrics
        }

        analysis = MetricAnalysisData(
            analysis_id="openmp-runtime",
            title="OpenMP Runtime-Specific Analysis",
            description=(
                "Direct OpenMP execution metrics used to distinguish serial "
                "execution, workload imbalance inside parallel regions, and "
                "scheduling or fork/join overhead."
            ),
            metrics=metrics,
            tree=self._build_openmp_runtime_tree(
                available_ids
            ),
        )

        return RuntimeComponentAnalysis(
            component_id="openmp-runtime",
            runtime_name="OpenMP",
            analysis_kind="runtime-specific-analysis",
            metrics=analysis,
        )

    def _build_accelerator_component(
        self,
        context: AnalysisContext,
    ) -> Optional[RuntimeComponentAnalysis]:
        """Build the accelerator contribution derived from MPI+X metrics."""

        runtime_name = self._inner_runtime_name(
            context
        )

        source = self._get_metric_group(
            context=context,
            group_name="hybrid_factors",
        )

        metrics = self._build_available_metrics(
            context=context,
            source=source,
            definitions=_ACCELERATOR_CONTRIBUTION_METRICS,
            runtime_name=runtime_name,
        )

        if not metrics:
            return None

        available_ids = {
            metric.metric_id
            for metric in metrics
        }

        analysis = MetricAnalysisData(
            analysis_id="accelerator-runtime",
            title="{} Runtime Contribution".format(
                runtime_name
            ),
            description=(
                "{} contribution derived from the composed MPI+{} "
                "multiplicative runtime model. This is not an isolated "
                "{} runtime-specific model.".format(
                    runtime_name,
                    runtime_name,
                    runtime_name,
                )
            ),
            metrics=metrics,
            tree=self._build_accelerator_tree(
                available_ids
            ),
        )

        return RuntimeComponentAnalysis(
            component_id="accelerator-runtime",
            runtime_name=runtime_name,
            analysis_kind="runtime-contribution-analysis",
            metrics=analysis,
        )

    # ------------------------------------------------------------------
    # Metric conversion
    # ------------------------------------------------------------------

    def _build_available_metrics(
        self,
        context: AnalysisContext,
        source: Mapping[str, Any],
        definitions,
        runtime_name: str,
    ) -> Tuple[MetricAnalysisMetric, ...]:
        """Build available metrics in their declared semantic order."""

        metrics = []

        for (
            metric_id,
            label_template,
            family,
            depth,
        ) in definitions:
            if not self._metric_is_available(
                context=context,
                source=source,
                metric_id=metric_id,
            ):
                continue

            label = label_template.format(
                runtime=runtime_name
            )

            resolved_family = family

            if family == "inner-runtime":
                resolved_family = self._runtime_family(
                    runtime_name
                )

            metrics.append(
                self._build_metric(
                    context=context,
                    source=source,
                    metric_id=metric_id,
                    label=label,
                    family=resolved_family,
                    depth=depth,
                )
            )

        return tuple(metrics)

    def _build_metric(
        self,
        context: AnalysisContext,
        source: Mapping[str, Any],
        metric_id: str,
        label: str,
        family: str,
        depth: int,
    ) -> MetricAnalysisMetric:
        """Build one semantic runtime metric in trace order."""

        metric_values = source.get(
            metric_id,
            {},
        )

        values = tuple(
            MetricAnalysisValue(
                trace_id=trace.trace_id,
                value=self._get_trace_metric_value(
                    metric_values=metric_values,
                    trace=trace,
                ),
            )
            for trace in context.traces
        )

        return MetricAnalysisMetric(
            metric_id=metric_id,
            label=label,
            family=family,
            depth=depth,
            values=values,
        )

    def _metric_is_available(
        self,
        context: AnalysisContext,
        source: Mapping[str, Any],
        metric_id: str,
    ) -> bool:
        """Return whether at least one trace has a numeric metric value."""

        metric_values = source.get(
            metric_id,
            {},
        )

        for trace in context.traces:
            value = self._get_trace_metric_value(
                metric_values=metric_values,
                trace=trace,
            )

            if self._is_number(value):
                return True

        return False

    # ------------------------------------------------------------------
    # Tree construction
    # ------------------------------------------------------------------

    def _build_simple_runtime_tree(
        self,
        available_ids: Set[str],
    ) -> Tuple[MetricAnalysisTreeNode, ...]:
        """Build the single-runtime Parallel Efficiency tree."""

        complete_tree = (
            MetricAnalysisTreeNode(
                metric_id="parallel_eff",
                children=(
                    MetricAnalysisTreeNode(
                        metric_id="load_balance",
                    ),
                    MetricAnalysisTreeNode(
                        metric_id="comm_eff",
                        children=(
                            MetricAnalysisTreeNode(
                                metric_id="serial_eff",
                            ),
                            MetricAnalysisTreeNode(
                                metric_id="transfer_eff",
                            ),
                        ),
                    ),
                ),
            ),
        )

        return self._prune_tree(
            complete_tree,
            available_ids,
        )

    def _build_hybrid_runtime_tree(
        self,
        available_ids: Set[str],
    ) -> Tuple[MetricAnalysisTreeNode, ...]:
        """Build the composed MPI+X runtime tree."""

        complete_tree = (
            MetricAnalysisTreeNode(
                metric_id="hybrid_eff",
                children=(
                    MetricAnalysisTreeNode(
                        metric_id="mpi_parallel_eff",
                        children=(
                            MetricAnalysisTreeNode(
                                metric_id="mpi_load_balance",
                            ),
                            MetricAnalysisTreeNode(
                                metric_id="mpi_comm_eff",
                                children=(
                                    MetricAnalysisTreeNode(
                                        metric_id="serial_eff",
                                    ),
                                    MetricAnalysisTreeNode(
                                        metric_id="transfer_eff",
                                    ),
                                ),
                            ),
                        ),
                    ),
                    MetricAnalysisTreeNode(
                        metric_id="omp_parallel_eff",
                        children=(
                            MetricAnalysisTreeNode(
                                metric_id="omp_load_balance",
                            ),
                            MetricAnalysisTreeNode(
                                metric_id="omp_comm_eff",
                                children=(
                                    MetricAnalysisTreeNode(
                                        metric_id="omp_serial_eff",
                                    ),
                                    MetricAnalysisTreeNode(
                                        metric_id="omp_transfer_eff",
                                    ),
                                ),
                            ),
                        ),
                    ),
                ),
            ),
        )

        return self._prune_tree(
            complete_tree,
            available_ids,
        )

    def _build_mpi_hybrid_tree(
        self,
        available_ids: Set[str],
    ) -> Tuple[MetricAnalysisTreeNode, ...]:
        """Build the MPI subtree of a composed hybrid model."""

        complete_tree = (
            MetricAnalysisTreeNode(
                metric_id="mpi_parallel_eff",
                children=(
                    MetricAnalysisTreeNode(
                        metric_id="mpi_load_balance",
                    ),
                    MetricAnalysisTreeNode(
                        metric_id="mpi_comm_eff",
                        children=(
                            MetricAnalysisTreeNode(
                                metric_id="serial_eff",
                            ),
                            MetricAnalysisTreeNode(
                                metric_id="transfer_eff",
                            ),
                        ),
                    ),
                ),
            ),
        )

        return self._prune_tree(
            complete_tree,
            available_ids,
        )

    def _build_openmp_runtime_tree(
        self,
        available_ids: Set[str],
    ) -> Tuple[MetricAnalysisTreeNode, ...]:
        """Build the isolated OpenMP runtime-specific tree."""

        complete_tree = (
            MetricAnalysisTreeNode(
                metric_id="omp_talp_parallel_eff",
                children=(
                    MetricAnalysisTreeNode(
                        metric_id="omp_talp_serial_eff",
                    ),
                    MetricAnalysisTreeNode(
                        metric_id="omp_talp_load_balance",
                    ),
                    MetricAnalysisTreeNode(
                        metric_id="omp_talp_scheduling_eff",
                    ),
                ),
            ),
        )

        return self._prune_tree(
            complete_tree,
            available_ids,
        )

    def _build_accelerator_tree(
        self,
        available_ids: Set[str],
    ) -> Tuple[MetricAnalysisTreeNode, ...]:
        """Build the accelerator-contribution tree."""

        complete_tree = (
            MetricAnalysisTreeNode(
                metric_id="omp_parallel_eff",
                children=(
                    MetricAnalysisTreeNode(
                        metric_id="omp_load_balance",
                    ),
                    MetricAnalysisTreeNode(
                        metric_id="omp_comm_eff",
                    ),
                ),
            ),
        )

        return self._prune_tree(
            complete_tree,
            available_ids,
        )

    def _prune_tree(
        self,
        tree: Tuple[MetricAnalysisTreeNode, ...],
        available_ids: Set[str],
    ) -> Tuple[MetricAnalysisTreeNode, ...]:
        """Recursively remove unavailable metrics from a tree."""

        return tuple(
            node
            for node in (
                self._prune_tree_node(
                    node=node,
                    available_ids=available_ids,
                )
                for node in tree
            )
            if node is not None
        )

    def _prune_tree_node(
        self,
        node: MetricAnalysisTreeNode,
        available_ids: Set[str],
    ) -> Optional[MetricAnalysisTreeNode]:
        """Recursively prune one metric-tree node."""

        if node.metric_id not in available_ids:
            return None

        children = tuple(
            child
            for child in (
                self._prune_tree_node(
                    node=child,
                    available_ids=available_ids,
                )
                for child in node.children
            )
            if child is not None
        )

        return MetricAnalysisTreeNode(
            metric_id=node.metric_id,
            children=children,
        )

    # ------------------------------------------------------------------
    # Independent helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _get_metric_group(
        context: AnalysisContext,
        group_name: str,
    ) -> Mapping[str, Any]:
        """Return one metric dictionary from the analysis context."""

        metrics = context.metrics

        if not isinstance(
            metrics,
            Mapping,
        ):
            return {}

        group = metrics.get(
            group_name,
            {},
        )

        if not isinstance(
            group,
            Mapping,
        ):
            return {}

        return group

    @staticmethod
    def _get_trace_metric_value(
        metric_values: Any,
        trace: TraceInfo,
    ) -> Any:
        """Return one trace value from a legacy or normalized mapping."""

        if not isinstance(
            metric_values,
            Mapping,
        ):
            return None

        if trace.path in metric_values:
            return metric_values[
                trace.path
            ]

        if trace.trace_id in metric_values:
            return metric_values[
                trace.trace_id
            ]

        trace_id_as_string = str(
            trace.trace_id
        )

        if trace_id_as_string in metric_values:
            return metric_values[
                trace_id_as_string
            ]

        return None

    @staticmethod
    def _is_number(
        value: Any,
    ) -> bool:
        """Return True for usable numeric metric values."""

        try:
            numeric_value = float(
                value
            )
        except (TypeError, ValueError):
            return False

        return not math.isnan(
            numeric_value
        )

    @staticmethod
    def _has_runtime(
        context: AnalysisContext,
        runtime_name: str,
    ) -> bool:
        """Return whether a runtime appears in any trace mode."""

        expected_runtime = runtime_name.upper()

        return any(
            expected_runtime in str(
                trace.mode
            ).upper()
            for trace in context.traces
        )

    def _has_accelerator(
        self,
        context: AnalysisContext,
    ) -> bool:
        """Return whether CUDA or HIP appears in the trace modes."""

        return (
            self._has_runtime(
                context,
                "CUDA",
            )
            or self._has_runtime(
                context,
                "HIP",
            )
        )

    @staticmethod
    def _is_hybrid(
        context: AnalysisContext,
    ) -> bool:
        """Return whether the computed metric model is hybrid."""

        metrics = context.metrics

        if not isinstance(
            metrics,
            Mapping,
        ):
            return False

        return (
            metrics.get("kind")
            == "hybrid"
        )

    @staticmethod
    def _single_runtime_name(
        context: AnalysisContext,
    ) -> str:
        """Return the active runtime for a simple execution model."""

        if not context.traces:
            return "Parallel Runtime"

        parts = str(
            context.traces[0].mode
        ).split("+")

        if len(parts) <= 1:
            return "Parallel Runtime"

        runtimes = parts[1:]

        if len(runtimes) == 1:
            return runtimes[0]

        return " + ".join(
            runtimes
        )

    @staticmethod
    def _inner_runtime_name(
        context: AnalysisContext,
    ) -> str:
        """Return X from an MPI+X trace mode."""

        for trace in context.traces:
            parts = str(
                trace.mode
            ).split("+")

            upper_parts = [
                part.upper()
                for part in parts
            ]

            if (
                "MPI" in upper_parts
                and len(parts) >= 3
            ):
                mpi_index = upper_parts.index(
                    "MPI"
                )

                if mpi_index + 1 < len(parts):
                    return parts[
                        mpi_index + 1
                    ]

        return "X"

    @staticmethod
    def _runtime_family(
        runtime_name: str,
    ) -> str:
        """Return the normalized presentation family of a runtime."""

        normalized = str(
            runtime_name
        ).strip().lower()

        if normalized in (
            "cuda",
            "hip",
        ):
            return "accelerator"

        if normalized == "openmp":
            return "openmp"

        if normalized == "mpi":
            return "mpi"

        return "runtime"