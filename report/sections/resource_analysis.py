"""Semantic builder for accelerator execution-domain analysis."""

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
# Host execution-domain metrics
# ---------------------------------------------------------------------------

# Most Host metrics are stored in ``host_factors``.
_HOST_FACTOR_METRICS = (
    (
        "host_global_eff",
        "Host Global efficiency",
        "host",
        0,
    ),
    (
        "host_parallel_eff",
        "Host Parallel efficiency",
        "host",
        1,
    ),
    (
        "mpi_parallel_eff",
        "MPI Parallel efficiency",
        "mpi",
        2,
    ),
    (
        "mpi_load_balance",
        "MPI Load balance",
        "mpi",
        3,
    ),
    (
        "mpi_comm_eff",
        "MPI Communication efficiency",
        "mpi",
        3,
    ),
    (
        "serial_eff",
        "MPI Serialization efficiency",
        "mpi",
        4,
    ),
    (
        "transfer_eff",
        "MPI Transfer efficiency",
        "mpi",
        4,
    ),
    (
        "dev_offload_eff",
        "Device Offload efficiency",
        "offload",
        2,
    ),
    (
        "host_comp_scale",
        "Host Computation scalability",
        "host",
        1,
    ),
)


# These metrics are stored in ``mod_factors`` but are interpreted as
# Host computation-scalability sub-metrics in this execution-domain view.
_HOST_CPU_SCALABILITY_METRICS = (
    (
        "ipc_scale",
        "IPC scalability",
        "host-scalability",
        2,
    ),
    (
        "inst_scale",
        "Instruction scalability",
        "host-scalability",
        2,
    ),
    (
        "freq_scale",
        "Frequency scalability",
        "host-scalability",
        2,
    ),
)


# ---------------------------------------------------------------------------
# Device execution-domain metrics
# ---------------------------------------------------------------------------

_DEVICE_METRICS = (
    (
        "dev_global_eff",
        "Device Global efficiency",
        "device",
        0,
    ),
    (
        "dev_parallel_eff",
        "Device Parallel efficiency",
        "device",
        1,
    ),
    (
        "dev_load_balance",
        "Device Load balance",
        "device",
        2,
    ),
    (
        "dev_comm_eff",
        "Device Communication efficiency",
        "device",
        2,
    ),
    (
        "dev_orches_eff",
        "Device Orchestration efficiency",
        "device",
        2,
    ),
    (
        "dev_comp_scale",
        "Device Computation scalability",
        "device",
        1,
    ),
)


@dataclass(frozen=True)
class ResourceAnalysisData:
    """Semantic information presented in Resource Analysis."""

    host: MetricAnalysisData
    device: MetricAnalysisData


class ResourceAnalysisBuilder:
    """Build Host and Device execution-domain analyses."""

    def build(
        self,
        context: AnalysisContext,
    ) -> Optional[ReportSection]:
        """Build Resource Analysis for accelerator executions.

        Returns ``None`` when the execution does not contain CUDA or HIP.
        """

        context.validate()

        if not self._has_accelerator(context):
            return None

        host_analysis = self._build_host_analysis(
            context
        )

        device_analysis = self._build_device_analysis(
            context
        )

        resource_data = ResourceAnalysisData(
            host=host_analysis,
            device=device_analysis,
        )

        section = ReportSection(
            section_id="resource-analysis",
            title="Resource Analysis",
            navigation_label="Resource Analysis",
            description=(
                "Execution-domain analysis used to determine whether "
                "accelerator-related inefficiency manifests on the host, "
                "the accelerator device, or both."
            ),
            section_type="resource-analysis",
            order=40,
            payload=resource_data,
        )

        section.add_child(
            ReportSection(
                section_id="host-analysis",
                title="Host Execution Domain",
                navigation_label="Host",
                description=host_analysis.description,
                section_type="execution-domain-analysis",
                order=10,
                payload=host_analysis,
            )
        )

        section.add_child(
            ReportSection(
                section_id="device-analysis",
                title="Device Execution Domain",
                navigation_label="Device",
                description=device_analysis.description,
                section_type="execution-domain-analysis",
                order=20,
                payload=device_analysis,
            )
        )

        return section

    # ------------------------------------------------------------------
    # Host analysis
    # ------------------------------------------------------------------

    def _build_host_analysis(
        self,
        context: AnalysisContext,
    ) -> MetricAnalysisData:
        """Build the Host execution-domain analysis."""

        host_factors = self._get_metric_group(
            context=context,
            group_name="host_factors",
        )

        mod_factors = self._get_metric_group(
            context=context,
            group_name="mod_factors",
        )

        metrics = list(
            self._build_available_metrics(
                context=context,
                source=host_factors,
                definitions=_HOST_FACTOR_METRICS,
            )
        )

        # Host CPU scalability metrics use the canonical global metric source.
        metrics.extend(
            self._build_available_metrics(
                context=context,
                source=mod_factors,
                definitions=_HOST_CPU_SCALABILITY_METRICS,
            )
        )

        metrics_tuple = tuple(metrics)

        available_ids = {
            metric.metric_id
            for metric in metrics_tuple
        }

        return MetricAnalysisData(
            analysis_id="host-analysis",
            title="Host Efficiency Metrics",
            description=(
                "Host-side MPI behavior, accelerator offload efficiency, "
                "and host computation scalability."
            ),
            metrics=metrics_tuple,
            tree=self._build_host_tree(
                available_ids
            ),
        )

    # ------------------------------------------------------------------
    # Device analysis
    # ------------------------------------------------------------------

    def _build_device_analysis(
        self,
        context: AnalysisContext,
    ) -> MetricAnalysisData:
        """Build the Device execution-domain analysis."""

        device_factors = self._get_metric_group(
            context=context,
            group_name="device_factors",
        )

        metrics = self._build_available_metrics(
            context=context,
            source=device_factors,
            definitions=_DEVICE_METRICS,
        )

        available_ids = {
            metric.metric_id
            for metric in metrics
        }

        return MetricAnalysisData(
            analysis_id="device-analysis",
            title="Device Efficiency Metrics",
            description=(
                "Device-side parallel efficiency, workload distribution, "
                "data movement, orchestration, and computation scalability."
            ),
            metrics=metrics,
            tree=self._build_device_tree(
                available_ids
            ),
        )

    # ------------------------------------------------------------------
    # Metric conversion
    # ------------------------------------------------------------------

    def _build_available_metrics(
        self,
        context: AnalysisContext,
        source: Mapping[str, Any],
        definitions,
    ) -> Tuple[MetricAnalysisMetric, ...]:
        """Build available metrics in their declared semantic order."""

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
        """Build one semantic execution-domain metric in trace order."""

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

    def _build_host_tree(
        self,
        available_ids: Set[str],
    ) -> Tuple[MetricAnalysisTreeNode, ...]:
        """Build the Host execution-domain metric hierarchy."""

        complete_tree = (
            MetricAnalysisTreeNode(
                metric_id="host_global_eff",
                children=(
                    MetricAnalysisTreeNode(
                        metric_id="host_parallel_eff",
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
                                metric_id="dev_offload_eff",
                            ),
                        ),
                    ),
                    MetricAnalysisTreeNode(
                        metric_id="host_comp_scale",
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
                ),
            ),
        )

        return self._prune_tree(
            tree=complete_tree,
            available_ids=available_ids,
        )

    def _build_device_tree(
        self,
        available_ids: Set[str],
    ) -> Tuple[MetricAnalysisTreeNode, ...]:
        """Build the Device execution-domain metric hierarchy."""

        complete_tree = (
            MetricAnalysisTreeNode(
                metric_id="dev_global_eff",
                children=(
                    MetricAnalysisTreeNode(
                        metric_id="dev_parallel_eff",
                        children=(
                            MetricAnalysisTreeNode(
                                metric_id="dev_load_balance",
                            ),
                            MetricAnalysisTreeNode(
                                metric_id="dev_comm_eff",
                            ),
                            MetricAnalysisTreeNode(
                                metric_id="dev_orches_eff",
                            ),
                        ),
                    ),
                    MetricAnalysisTreeNode(
                        metric_id="dev_comp_scale",
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
        """Recursively prune one execution-domain metric node."""

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
    def _has_accelerator(
        context: AnalysisContext,
    ) -> bool:
        """Return whether CUDA or HIP appears in any trace mode."""

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