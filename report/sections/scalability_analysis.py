"""Semantic builder for Computation Scalability analysis."""

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
# Standard CPU computation-scalability metrics
# ---------------------------------------------------------------------------

_CPU_SCALABILITY_METRICS = (
    (
        "comp_scale",
        "Computation scalability",
        "scalability",
        0,
    ),
    (
        "ipc_scale",
        "IPC scalability",
        "scalability",
        1,
    ),
    (
        "inst_scale",
        "Instruction scalability",
        "scalability",
        1,
    ),
    (
        "freq_scale",
        "Frequency scalability",
        "scalability",
        1,
    ),
)


# ---------------------------------------------------------------------------
# Accelerator-aware computation-scalability metrics
# ---------------------------------------------------------------------------

# BasicAnalysis currently computes an application-level Computation
# Scalability metric for MPI+CUDA/HIP, but CPU IPC, instruction, and frequency
# factors are not presented as its multiplicative explanation. A GPU-inclusive
# computation-scalability decomposition must be defined before those factors
# can be exposed in this analytical view.


_ACCELERATOR_SCALABILITY_METRICS = (
    (
        "comp_scale",
        "Computation scalability",
        "scalability",
        0,
    ),
    (
        "ipc_scale",
        "IPC scalability",
        "scalability",
        1,
    ),
    (
        "inst_scale",
        "Instruction scalability",
        "scalability",
        1,
    ),
    (
        "freq_scale",
        "Frequency scalability",
        "scalability",
        1,
    ),
)


@dataclass(frozen=True)
class ScalingTrendValue:
    """
    Scaling information associated with one analyzed trace/configuration.
    """

    trace_id: int
    parallel_units: Any
    speedup: Any
    efficiency: Any


@dataclass(frozen=True)
class ScalabilityAnalysisData:
    """Semantic information presented in Computation Scalability."""

    analysis: MetricAnalysisData
    trace_count: int
    accelerator_limited_model: bool
    scaling_info: Any = None
    trend_values: Tuple[ScalingTrendValue, ...] = ()


class ScalabilityAnalysisBuilder:
    """Build the Computation Scalability analysis when it is meaningful."""

    def build(
        self,
        context: AnalysisContext,
    ) -> Optional[ReportSection]:
        """Build Computation Scalability.

        The section is available only when:

        * more than one trace is present; and
        * at least one valid scalability metric is available.

        For CUDA/HIP executions, Computation Scalability is presented together
        with IPC, instruction, and frequency scalability. The three submetrics
        characterize host-side computation and must not be interpreted as a
        GPU-inclusive decomposition.
        """
        context.validate()

        if not self._has_scaling_experiment(
            context
        ):
            return None

        has_accelerator = self._has_accelerator(
            context
        )

        definitions = (
            _ACCELERATOR_SCALABILITY_METRICS
            if has_accelerator
            else _CPU_SCALABILITY_METRICS
        )

        mod_factors = self._get_metric_group(
            context=context,
            group_name="mod_factors",
        )

        other_metrics = self._get_metric_group(
            context=context,
            group_name="other_metrics",
        )

        metrics = self._build_available_metrics(
            context=context,
            source=mod_factors,
            definitions=definitions,
        )

        if not metrics:
            return None

        available_ids = {
            metric.metric_id
            for metric in metrics
        }

        # Computation Scalability is the root metric of this analysis.
        # Do not create the section when the root is unavailable, even if
        # one or more host-side scalability submetrics are present.
        if "comp_scale" not in available_ids:
            return None
        

        analysis = MetricAnalysisData(
            analysis_id="computation-scalability",
            title="Computation Scalability",
            description=self._build_description(
                has_accelerator
            ),
            metrics=metrics,
            tree=self._build_scalability_tree(
                available_ids=available_ids,
            ),
        )

        trend_values = self._build_scaling_trend_values(
            context=context,
            other_metrics=other_metrics,
        )

        payload = ScalabilityAnalysisData(
            analysis=analysis,
            trace_count=len(
                context.traces
            ),
            accelerator_limited_model=has_accelerator,
            scaling_info=context.scaling_info,
            trend_values=trend_values,
        )

        section = ReportSection(
            section_id="scalability-analysis",
            title="Scalability Analysis",
            navigation_label="Scalability Analysis",
            description=(
                "Analyze why useful computation does not scale across "
                "the evaluated execution configurations."
            ),
            section_type="scalability-analysis",
            order=50,
            payload=payload,
        )

        section.add_child(
            ReportSection(
                section_id="computation-scalability",
                title="Computation Scalability",
                navigation_label="Computation Scalability",
                description=analysis.description,
                section_type="computation-scalability",
                order=10,
                payload=analysis,
            )
        )

        return section


    def _build_scaling_trend_values(
        self,
        context: AnalysisContext,
        other_metrics: Mapping[str, Any],
    ) -> Tuple[ScalingTrendValue, ...]:
        """
        Build Speedup/Efficiency trend information in trace order.
        """

        speedup_values = other_metrics.get(
            "speedup",
            {},
        )

        efficiency_values = other_metrics.get(
            "efficiency",
            {},
        )

        trend_values = []

        for trace in context.traces:

            speedup = self._get_trace_metric_value(
                metric_values=speedup_values,
                trace=trace,
            )

            efficiency = self._get_trace_metric_value(
                metric_values=efficiency_values,
                trace=trace,
            )

            trend_values.append(
                ScalingTrendValue(
                    trace_id=trace.trace_id,
                    parallel_units=trace.processes,
                    speedup=(
                        float(speedup)
                        if self._is_number(speedup)
                        else None
                    ),
                    efficiency=(
                        float(efficiency)
                        if self._is_number(efficiency)
                        else None
                    ),
                )
            )

        return tuple(
            trend_values
        )

    # ------------------------------------------------------------------
    # Metric construction
    # ------------------------------------------------------------------

    def _build_available_metrics(
        self,
        context: AnalysisContext,
        source: Mapping[str, Any],
        definitions,
    ) -> Tuple[MetricAnalysisMetric, ...]:
        """Build available scalability metrics in semantic order."""

        metrics = []

        for (
            metric_id,
            label,
            family,
            depth,
        ) in definitions:
            if not self._metric_is_available(
                context=context,
                source=source,
                metric_id=metric_id,
            ):
                continue

            metrics.append(
                self._build_metric(
                    context=context,
                    source=source,
                    metric_id=metric_id,
                    label=label,
                    family=family,
                    depth=depth,
                )
            )

        return tuple(
            metrics
        )

    def _build_metric(
        self,
        context: AnalysisContext,
        source: Mapping[str, Any],
        metric_id: str,
        label: str,
        family: str,
        depth: int,
    ) -> MetricAnalysisMetric:
        """Build one scalability metric in trace order."""

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
        """Return whether at least one trace has a numeric value."""

        metric_values = source.get(
            metric_id,
            {},
        )

        for trace in context.traces:
            value = self._get_trace_metric_value(
                metric_values=metric_values,
                trace=trace,
            )

            if self._is_number(
                value
            ):
                return True

        return False

    # ------------------------------------------------------------------
    # Tree construction
    # ------------------------------------------------------------------

    def _build_scalability_tree(
        self,
        available_ids: Set[str],
    ) -> Tuple[MetricAnalysisTreeNode, ...]:
        """Build the computation-scalability hierarchy."""

        complete_tree = (
            MetricAnalysisTreeNode(
                metric_id="comp_scale",
                children=(
                    MetricAnalysisTreeNode(
                        metric_id="ipc_scale",
                    ),
                    MetricAnalysisTreeNode(
                        metric_id="inst_scale",
                    ),
                    MetricAnalysisTreeNode(
                        metric_id="freq_scale",
                    ),
                ),
            ),
        )

        return self._prune_tree(
            tree=complete_tree,
            available_ids=available_ids,
        )

    def _prune_tree(
        self,
        tree: Tuple[MetricAnalysisTreeNode, ...],
        available_ids: Set[str],
    ) -> Tuple[MetricAnalysisTreeNode, ...]:
        """Recursively remove unavailable metrics."""

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
        """Recursively prune one scalability-tree node."""

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
    # Availability and presentation
    # ------------------------------------------------------------------

    @staticmethod
    def _has_scaling_experiment(
        context: AnalysisContext,
    ) -> bool:
        """Return whether scaling analysis is applicable."""

        if context.scaling_info is not None:
            return bool(
                context.scaling_info.has_scaling_analysis
            )

        return len(
            context.traces
        ) > 1

    @staticmethod
    def _has_accelerator(
        context: AnalysisContext,
    ) -> bool:
        """Return whether CUDA or HIP appears in the execution model."""

        for trace in context.traces:
            mode = str(
                trace.mode
            ).upper()

            if (
                "CUDA" in mode
                or "HIP" in mode
            ):
                return True

        return False

    @staticmethod
    def _build_description(
        has_accelerator: bool,
    ) -> str:
        """Return analysis-scope guidance for the execution model."""

        if has_accelerator:
            return (
                "Computation Scalability across the evaluated configurations. "
                "For CUDA/HIP executions, IPC, Instruction, and Frequency "
                "Scalability are derived from host-side computation and hardware "
                "counter information. These submetrics therefore characterize "
                "host execution only and must not be interpreted as a GPU-inclusive "
                "decomposition of Computation Scalability. Device-side computation "
                "scalability is analyzed separately in the Execution Domains view."
            )

        return (
            "Decomposition of Computation Scalability into IPC, instruction, "
            "and frequency scalability across the evaluated configurations."
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