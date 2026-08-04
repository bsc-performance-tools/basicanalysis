"""Shared semantic objects for hierarchical metric analyses."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Tuple


@dataclass(frozen=True)
class MetricAnalysisValue:
    """Value of one performance metric for one trace."""

    trace_id: int
    value: Any


@dataclass(frozen=True)
class MetricAnalysisMetric:
    """One metric presented in a hierarchical analysis."""

    metric_id: str
    label: str
    family: str
    depth: int
    values: Tuple[MetricAnalysisValue, ...]


@dataclass(frozen=True)
class MetricAnalysisTreeNode:
    """One node in a metric decomposition tree."""

    metric_id: str
    children: Tuple["MetricAnalysisTreeNode", ...] = ()


@dataclass(frozen=True)
class MetricAnalysisData:
    """Semantic payload shared by hierarchical metric analyses."""

    analysis_id: str
    title: str
    description: str
    metrics: Tuple[MetricAnalysisMetric, ...]
    tree: Tuple[MetricAnalysisTreeNode, ...]