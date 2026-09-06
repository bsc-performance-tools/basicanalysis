"""Core semantic objects for BasicAnalysis reports."""

from .context import (
    AnalysisContext,
    ExecutionMappingInfo,
    GeneralInfo,
    ResourceInfo,
    TraceInfo,
)

from .metadata import ReportMetadata
from .navigation import NavigationItem, build_navigation
from .report import Report
from .section import ReportSection

__all__ = [
    "AnalysisContext",
    "ExecutionMappingInfo",
    "GeneralInfo",
    "NavigationItem",
    "Report",
    "ReportMetadata",
    "ReportSection",
    "ResourceInfo",
    "TraceInfo",
    "build_navigation",
]
