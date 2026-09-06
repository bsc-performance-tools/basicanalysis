"""Semantic builder for the Overview report section."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Tuple

from ..model import (
    AnalysisContext,
    ExecutionMappingInfo,
    GeneralInfo,
    ReportSection,
    ResourceInfo,
    TraceInfo,
)


# Metrics currently presented in the General Metrics table of the
# interactive Overview.
#
# Each tuple contains:
#   metric identifier used in metrics["other_metrics"]
#   user-facing label
#   semantic group
_OVERVIEW_METRICS = (
    ("elapsed_time", "Elapsed time (s)", "Runtime"),
    ("efficiency", "Efficiency", "Performance"),
    ("speedup", "Speedup", "Performance"),
    ("ipc", "Average IPC (inst/cycle)", "Microarchitecture"),
    ("freq", "Average frequency (GHz)", "Microarchitecture"),
)


@dataclass(frozen=True)
class OverviewMetricValue:
    """Value of an Overview metric for one trace."""

    trace_id: int
    value: Any


@dataclass(frozen=True)
class OverviewMetric:
    """Metric displayed in the General Metrics part of the Overview."""

    metric_id: str
    label: str
    group: str
    values: Tuple[OverviewMetricValue, ...]


@dataclass(frozen=True)
class OverviewExecutionMapping:
    """Execution-resource mapping associated with one trace."""

    trace_id: int
    mapping: ExecutionMappingInfo


@dataclass(frozen=True)
class OverviewData:
    """Semantic information presented in the Overview section."""

    general: GeneralInfo
    traces: Tuple[TraceInfo, ...]
    execution_mappings: Tuple[OverviewExecutionMapping, ...]
    general_metrics: Tuple[OverviewMetric, ...]
    resources: Tuple[ResourceInfo, ...]


class OverviewBuilder:
    """Build the Overview section from an AnalysisContext."""

    def build(self, context: AnalysisContext) -> ReportSection:
        """Build and return the complete semantic Overview section."""

        context.validate()

        overview_data = OverviewData(
            general=context.general,
            traces=tuple(context.traces),
            execution_mappings=self._build_execution_mappings(
                context
            ),
            general_metrics=self._build_general_metrics(
                context
            ),
            resources=tuple(context.resources),
        )

        section = ReportSection(
            section_id="overview",
            title="Overview",
            navigation_label="Overview",
            description=(
                "Execution configuration, general metrics, and validation "
                "information about the analyzed traces."
            ),
            section_type="overview",
            order=10,
            payload=overview_data,
        )

        section.add_child(
            ReportSection(
                section_id="trace-configuration",
                title="Trace configuration",
                navigation_label="Trace configuration",
                section_type="overview-traces",
                order=10,
                payload=overview_data.traces,
            )
        )

        section.add_child(
            ReportSection(
                section_id="execution-mapping",
                title="Execution mapping",
                navigation_label="Execution mapping",
                section_type="overview-mapping",
                order=20,
                payload=overview_data.execution_mappings,
            )
        )

        section.add_child(
            ReportSection(
                section_id="general-information",
                title="General information",
                navigation_label="General information",
                section_type="overview-general",
                order=30,
                payload=overview_data.general,
            )
        )

        section.add_child(
            ReportSection(
                section_id="general-metrics",
                title="General metrics",
                navigation_label="General metrics",
                section_type="overview-metrics",
                order=40,
                payload=overview_data.general_metrics,
            )
        )

        section.add_child(
            ReportSection(
                section_id="paraver-validation",
                title="Paraver validation",
                navigation_label="Paraver validation",
                section_type="overview-resources",
                order=50,
                payload=overview_data.resources,
            )
        )

        return section

    def _build_general_metrics(
        self,
        context: AnalysisContext,
    ) -> Tuple[OverviewMetric, ...]:
        """Extract the General Metrics values in trace order.

        The legacy metric result stores each metric as a mapping whose keys
        normally correspond to trace paths. This method converts that
        representation into an explicitly ordered semantic representation.

        Missing metrics or missing values are represented by ``None``.
        The HTML renderer will later decide how missing values are displayed.
        """

        other_metrics = self._get_other_metrics(context)
        overview_metrics = []

        for metric_id, label, group in _OVERVIEW_METRICS:
            metric_values = other_metrics.get(metric_id, {})

            values = tuple(
                OverviewMetricValue(
                    trace_id=trace.trace_id,
                    value=self._get_trace_metric_value(
                        metric_values=metric_values,
                        trace=trace,
                    ),
                )
                for trace in context.traces
            )

            overview_metrics.append(
                OverviewMetric(
                    metric_id=metric_id,
                    label=label,
                    group=group,
                    values=values,
                )
            )

        return tuple(overview_metrics)

    @staticmethod
    def _get_other_metrics(
        context: AnalysisContext,
    ) -> Mapping[str, Any]:
        """Return the legacy ``other_metrics`` mapping safely."""

        metrics = context.metrics

        if not isinstance(metrics, Mapping):
            return {}

        other_metrics = metrics.get("other_metrics", {})

        if not isinstance(other_metrics, Mapping):
            return {}

        return other_metrics

    @staticmethod
    def _get_trace_metric_value(
        metric_values: Any,
        trace: TraceInfo,
    ) -> Any:
        """Return a metric value associated with one trace.

        The normal legacy representation is:

            metric_values[trace.path]

        A fallback using ``trace_id`` is included to make the semantic builder
        tolerant of metrics that have already been converted to trace IDs.
        """

        if not isinstance(metric_values, Mapping):
            return None

        trace_path = getattr(trace, "path", None)

        if trace_path is not None and trace_path in metric_values:
            return metric_values[trace_path]

        if trace.trace_id in metric_values:
            return metric_values[trace.trace_id]

        trace_id_as_string = str(trace.trace_id)

        if trace_id_as_string in metric_values:
            return metric_values[trace_id_as_string]

        return None

    def _build_execution_mappings(
        self,
        context: AnalysisContext,
    ) -> Tuple[OverviewExecutionMapping, ...]:
        """Build the execution mapping associated with each trace."""

        mappings = []

        for trace in context.traces:

            if trace.mapping is None:
                continue

            mappings.append(
                OverviewExecutionMapping(
                    trace_id=trace.trace_id,
                    mapping=trace.mapping,
                )
            )

        return tuple(mappings)