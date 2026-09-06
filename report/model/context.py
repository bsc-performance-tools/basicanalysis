"""Typed execution context consumed by diagnosis and report builders."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Mapping, Optional


@dataclass(frozen=True)
class GeneralInfo:
    analysis_kind: str = "unknown"
    pop_model: str = "unknown"


@dataclass(frozen=True)
class ExecutionMappingInfo:
    """Representative execution-resource mapping for one trace."""

    nodes: Any = None
    mpi_ranks_per_node: Any = None
    threads_per_rank: Any = None
    threads_per_node: Any = None
    gpus_per_node: Any = None
    gpu_streams_per_node: Any = None
    streams_per_gpu: Any = None


@dataclass(frozen=True)
class TraceInfo:
    trace_id: int
    name: str
    path: str
    mode: str
    processes: Any
    tasks: Any
    threads: Any
    devices: Any = 0
    gpu_streams: Any = 0
    gpu_streams_per_rank: Any = 0
    mapping: Optional[ExecutionMappingInfo] = None


@dataclass(frozen=True)
class ResourceInfo:
    trace: str
    prv: str
    pcf: str
    row: str
    overview_cfg: str
    cfgs: tuple = ()
    images: tuple = ()


@dataclass
class AnalysisContext:
    """Information produced by the analysis, independent of rendering."""

    general: GeneralInfo
    traces: List[TraceInfo]
    resources: List[ResourceInfo]
    metrics: Mapping[str, Any]
    scaling_info: Optional[Any] = None
    raw_data: Mapping[str, Any] = field(default_factory=dict)
    diagnosis: List[Any] = field(default_factory=list)
    evidence: List[Any] = field(default_factory=list)

    def validate(self) -> None:
        trace_ids = [trace.trace_id for trace in self.traces]
        if len(trace_ids) != len(set(trace_ids)):
            raise ValueError("Trace identifiers must be unique.")

        trace_paths = {trace.path for trace in self.traces}
        for resource in self.resources:
            if resource.trace not in trace_paths:
                raise ValueError(
                    "Resource refers to an unknown trace: {!r}".format(
                        resource.trace
                    )
                )

        if not isinstance(self.metrics, Mapping):
            raise TypeError("metrics must be a mapping.")
