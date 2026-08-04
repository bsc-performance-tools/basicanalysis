"""Adapters and builders for the BasicAnalysis report model."""

from typing import Any, Mapping, Optional


from .sections import (
    OverviewBuilder,
    PerformanceAssessmentBuilder,
    ResourceAnalysisBuilder,
    RuntimeAnalysisBuilder,
    ScalabilityAnalysisBuilder,
)


from .model import (
    AnalysisContext,
    GeneralInfo,
    Report,
    ReportMetadata,
    ResourceInfo,
    TraceInfo,
)

def build_analysis_context(
    report_data: Mapping[str, Any],
    raw_data: Optional[Mapping[str, Any]] = None,
) -> AnalysisContext:
    """Adapt the current ``reportdata`` dictionary to typed objects."""

    general_data = report_data.get(
        "general",
        {},
    )

    general = GeneralInfo(
        analysis_kind=general_data.get(
            "analysis_kind",
            "unknown",
        ),
        pop_model=general_data.get(
            "pop_model",
            "unknown",
        ),
    )

    traces = [
        TraceInfo(
            trace_id=item.get("id"),
            name=item.get(
                "name",
                "unknown",
            ),
            path=item.get(
                "path",
                "",
            ),
            mode=item.get(
                "mode",
                "unknown",
            ),
            processes=item.get(
                "processes",
                "unknown",
            ),
            tasks=item.get(
                "tasks",
                "unknown",
            ),
            threads=item.get(
                "threads",
                "unknown",
            ),
            devices=item.get(
                "devices",
                0,
            ),
            gpu_streams=item.get(
                "gpu_streams",
                0,
            ),
            gpu_streams_per_rank=item.get(
                "gpu_streams_per_rank",
                0,
            ),
        )
        for item in report_data.get(
            "traces",
            [],
        )
    ]

    resources = [
        ResourceInfo(
            trace=item.get(
                "trace",
                "",
            ),
            prv=item.get(
                "prv",
                "",
            ),
            pcf=item.get(
                "pcf",
                "",
            ),
            row=item.get(
                "row",
                "",
            ),
            overview_cfg=item.get(
                "overview_cfg",
                "",
            ),
            cfgs=tuple(
                item.get(
                    "cfgs",
                    [],
                )
            ),
            images=tuple(
                item.get(
                    "images",
                    [],
                )
            ),
        )
        for item in report_data.get(
            "resources",
            [],
        )
    ]

    context = AnalysisContext(
        general=general,
        traces=traces,
        resources=resources,
        metrics=report_data.get(
            "metrics",
            {},
        ),
        raw_data=raw_data or {},
        diagnosis=list(
            report_data.get(
                "diagnosis",
                [],
            )
        ),
        evidence=list(
            report_data.get(
                "evidence",
                [],
            )
        ),
    )

    context.validate()

    return context



def build_report_model(
    context: AnalysisContext,
    tool_version: Optional[str] = None,
) -> Report:
    """Build and validate the semantic report hierarchy."""

    programming_model = None

    if context.traces:
        mode_parts = str(
            context.traces[0].mode
        ).split("+")

        if len(mode_parts) > 1:
            programming_model = " + ".join(
                mode_parts[1:]
            )

    report = Report(
        metadata=ReportMetadata(
            title="BasicAnalysis Performance Report",
            subtitle=(
                "Interactive guide for performance analysis"
            ),
            tool_version=tool_version,
            analysis_kind=(
                context.general.analysis_kind
            ),
            programming_model=programming_model,
        )
    )

    # --------------------------------------------------
    # Overview
    # --------------------------------------------------

    report.add_section(
        OverviewBuilder().build(
            context
        )
    )

    # --------------------------------------------------
    # Performance Assessment
    # --------------------------------------------------

    report.add_section(
        PerformanceAssessmentBuilder().build(
            context
        )
    )

    # --------------------------------------------------
    # Runtime Analysis
    # --------------------------------------------------

    report.add_section(
        RuntimeAnalysisBuilder().build(
            context
        )
    )

    # --------------------------------------------------
    # Resource Analysis
    #
    # Host and Device remain structural placeholders until
    # ResourceAnalysisBuilder is implemented.
    # --------------------------------------------------


    resource_analysis = ResourceAnalysisBuilder().build(
        context
    )

    if resource_analysis is not None:
        report.add_section(
            resource_analysis
        )


    scalability_analysis = ScalabilityAnalysisBuilder().build(
        context
    )

    if scalability_analysis is not None:
        report.add_section(
            scalability_analysis
        )


    report.validate()

    return report
