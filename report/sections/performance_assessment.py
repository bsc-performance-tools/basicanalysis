"""Semantic builder for the Performance Assessment report section."""

from __future__ import annotations

import math

from dataclasses import dataclass
from typing import Any, Mapping, Set, Tuple

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


# Application-level Global Metrics shown for every execution model.
#
# Each tuple contains:
#   metric identifier
#   user-facing label
#   metric family
#   hierarchy depth
_GLOBAL_METRICS = (
    (
        "global_eff",
        "Global efficiency",
        "global",
        0,
    ),
    (
        "parallel_eff",
        "Parallel efficiency",
        "global",
        1,
    ),
    (
        "load_balance",
        "Load balance",
        "global",
        2,
    ),
    (
        "comm_eff",
        "Communication efficiency",
        "global",
        2,
    ),
    (
        "comp_scale",
        "Computation scalability",
        "global",
        1,
    ),
)


# CPU computation-scalability sub-metrics.
#
# These are intentionally omitted from application-level MPI+GPU reports
# until a GPU-inclusive computation-scalability methodology is available.
_CPU_SCALABILITY_METRICS = (
    (
        "ipc_scale",
        "IPC scalability",
        "global",
        2,
    ),
    (
        "inst_scale",
        "Instruction scalability",
        "global",
        2,
    ),
    (
        "freq_scale",
        "Frequency scalability",
        "global",
        2,
    ),
)


@dataclass(frozen=True)
class PerformanceAssessmentData:
    """Semantic information presented in Performance Assessment."""

    global_metrics: MetricAnalysisData


class PerformanceAssessmentBuilder:
    """Build the application-level Performance Assessment section."""

    def build(
        self,
        context: AnalysisContext,
    ) -> ReportSection:
        """Build and return the Performance Assessment section."""

        context.validate()

        global_metrics = self._build_global_metrics(
            context
        )

        assessment_data = PerformanceAssessmentData(
            global_metrics=global_metrics,
        )

        section = ReportSection(
            section_id="performance-assessment",
            title="Performance Assessment",
            navigation_label="Performance Assessment",
            description=(
                "Application-level efficiency decomposition used to "
                "identify the dominant performance loss."
            ),
            section_type="performance-assessment",
            order=20,
            payload=assessment_data,
        )

        section.add_child(
            ReportSection(
                section_id="global-metrics",
                title="Global Metrics",
                navigation_label="Global Metrics",
                description=(
                    "Overall efficiency decomposition of the complete "
                    "parallel application."
                ),
                section_type="metric-analysis",
                order=10,
                payload=global_metrics,
            )
        )

        return section

    def _build_global_metrics(
        self,
        context: AnalysisContext,
    ) -> MetricAnalysisData:
        """Build the application-level Global Metrics analysis."""

        mod_factors = self._get_metric_group(
            context=context,
            group_name="mod_factors",
        )

        include_cpu_scalability = (
            not self._has_accelerator(context)
        )

        metric_definitions = list(
            _GLOBAL_METRICS
        )

        if include_cpu_scalability:
            metric_definitions.extend(
                _CPU_SCALABILITY_METRICS
            )

        metrics = []

        for (
            metric_id,
            label,
            family,
            depth,
        ) in metric_definitions:

            if not self._metric_is_available(
                context=context,
                source=mod_factors,
                metric_id=metric_id,
            ):
                continue

            metrics.append(
                self._build_metric(
                    context=context,
                    source=mod_factors,
                    metric_id=metric_id,
                    label=label,
                    family=family,
                    depth=depth,
                )
            )

        metrics_tuple = tuple(metrics)

        available_ids = {
            metric.metric_id
            for metric in metrics_tuple
        }

        tree = self._build_global_tree(
            available_ids=available_ids,
            include_cpu_scalability=(
                include_cpu_scalability
            ),
        )

        return MetricAnalysisData(
            analysis_id="global-metrics",
            title="Global Efficiency Metrics",
            description=(
                "Application-level decomposition of Global Efficiency "
                "into parallel-efficiency and computation-scalability "
                "factors."
            ),
            metrics=metrics_tuple,
            tree=tree,
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
        """Build one semantic metric in trace order."""

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

    @staticmethod
    def _get_metric_group(
        context: AnalysisContext,
        group_name: str,
    ) -> Mapping[str, Any]:
        """Return one metric group from the analysis context."""

        metrics = context.metrics

        if not isinstance(metrics, Mapping):
            return {}

        group = metrics.get(
            group_name,
            {},
        )

        if not isinstance(group, Mapping):
            return {}

        return group

    def _metric_is_available(
        self,
        context: AnalysisContext,
        source: Mapping[str, Any],
        metric_id: str,
    ) -> bool:
        """Return True when a metric has a numeric value in any trace."""

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

    @staticmethod
    def _get_trace_metric_value(
        metric_values: Any,
        trace: TraceInfo,
    ) -> Any:
        """Return one metric value associated with a trace.

        The current metric dictionaries normally use the trace path as
        the key. Trace-ID fallbacks are supported for future normalized
        representations.
        """

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
            numeric_value = float(value)
        except (TypeError, ValueError):
            return False

        return not math.isnan(
            numeric_value
        )

    @staticmethod
    def _has_accelerator(
        context: AnalysisContext,
    ) -> bool:
        """Return whether an accelerator runtime is active."""

        for trace in context.traces:
            mode = str(trace.mode).upper()

            if (
                "CUDA" in mode
                or "HIP" in mode
            ):
                return True

        return False

    @classmethod
    def _build_global_tree(
        cls,
        available_ids: Set[str],
        include_cpu_scalability: bool,
    ) -> Tuple[MetricAnalysisTreeNode, ...]:
        """Build and prune the Global Efficiency decomposition tree."""

        parallel_efficiency = (
            MetricAnalysisTreeNode(
                metric_id="parallel_eff",
                children=(
                    MetricAnalysisTreeNode(
                        metric_id="load_balance",
                    ),
                    MetricAnalysisTreeNode(
                        metric_id="comm_eff",
                    ),
                ),
            )
        )

        scalability_children = ()

        if include_cpu_scalability:
            scalability_children = (
                MetricAnalysisTreeNode(
                    metric_id="ipc_scale",
                ),
                MetricAnalysisTreeNode(
                    metric_id="inst_scale",
                ),
                MetricAnalysisTreeNode(
                    metric_id="freq_scale",
                ),
            )

        computation_scalability = (
            MetricAnalysisTreeNode(
                metric_id="comp_scale",
                children=scalability_children,
            )
        )

        complete_tree = (
            MetricAnalysisTreeNode(
                metric_id="global_eff",
                children=(
                    parallel_efficiency,
                    computation_scalability,
                ),
            ),
        )

        return tuple(
            node
            for node in (
                cls._prune_tree_node(
                    node=node,
                    available_ids=available_ids,
                )
                for node in complete_tree
            )
            if node is not None
        )

    @classmethod
    def _prune_tree_node(
        cls,
        node: MetricAnalysisTreeNode,
        available_ids: Set[str],
    ):
        """Remove unavailable nodes recursively from a metric tree."""

        if node.metric_id not in available_ids:
            return None

        children = tuple(
            child
            for child in (
                cls._prune_tree_node(
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