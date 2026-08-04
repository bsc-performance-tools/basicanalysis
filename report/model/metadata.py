"""Metadata describing a generated report document."""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class ReportMetadata:
    title: str
    subtitle: str = ""
    tool_name: str = "BasicAnalysis"
    tool_version: Optional[str] = None
    analysis_kind: Optional[str] = None
    programming_model: Optional[str] = None
