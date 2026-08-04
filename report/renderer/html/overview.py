"""HTML renderer for the semantic Overview section."""

from __future__ import annotations

import html
from typing import Iterable, Tuple

from ...model import ReportSection, TraceInfo


def _split_trace_mode(mode: str) -> Tuple[str, str]:
    """Split the trace collection mode and programming model.

    Examples
    --------
    ``Detailed+MPI`` becomes ``("Detailed", "MPI")``.

    ``Detailed+MPI+OpenMP`` becomes
    ``("Detailed", "MPI + OpenMP")``.
    """

    parts = str(mode).split("+")

    trace_mode = parts[0]

    if len(parts) > 1:
        programming_model = " + ".join(parts[1:])
    else:
        programming_model = "Unknown"

    return trace_mode, programming_model


def _programming_model_key(programming_model: str) -> str:
    """Return a normalized programming-model identifier."""

    normalized = (
        str(programming_model)
        .upper()
        .replace(" ", "")
    )

    if normalized == "MPI":
        return "mpi"

    if normalized in ("OPENMP", "OMP"):
        return "openmp"

    if normalized == "PTHREADS":
        return "pthreads"

    if normalized == "OMPSS":
        return "ompss"

    if normalized in ("CUDA", "HIP"):
        return "gpu"

    if normalized in (
        "MPI+OPENMP",
        "MPI+OMP",
        "MPI+PTHREADS",
    ):
        return "mpi_threads"

    if normalized == "MPI+OMPSS":
        return "mpi_ompss"

    if normalized in (
        "MPI+CUDA",
        "MPI+HIP",
    ):
        return "mpi_gpu"

    return "generic"


def _trace_resource_columns(
    model_key: str,
) -> Tuple[Tuple[str, str], ...]:
    """Return the resource columns required by one programming model."""

    columns = {
        "mpi": (
            ("tasks", "MPI ranks"),
        ),
        "openmp": (
            ("threads", "Threads"),
        ),
        "pthreads": (
            ("threads", "Threads"),
        ),
        "ompss": (
            ("threads", "Workers"),
        ),
        "gpu": (
            ("gpu_streams", "GPU streams"),
            ("devices", "Devices"),
        ),
        "mpi_threads": (
            ("processes", "Parallel units"),
            ("tasks", "MPI ranks"),
            ("threads", "Threads/rank"),
        ),
        "mpi_ompss": (
            ("processes", "Parallel units"),
            ("tasks", "MPI ranks"),
            ("threads", "Workers/rank"),
        ),
        "mpi_gpu": (
            ("processes", "Parallel units"),
            ("tasks", "MPI ranks"),
            ("gpu_streams_per_rank", "Streams/rank"),
            ("gpu_streams", "GPU streams"),
            ("devices", "Devices"),
        ),
        "generic": (
            ("processes", "Parallel units"),
        ),
    }

    return columns.get(
        model_key,
        columns["generic"],
    )


def _format_trace_id(trace: TraceInfo) -> str:
    """Return the user-facing trace identifier."""

    trace_id = trace.trace_id

    if trace_id is None:
        return "T-"

    return "T{}".format(trace_id)


def _format_resource_value(
    trace: TraceInfo,
    field_name: str,
) -> str:
    """Return a resource value suitable for the HTML table."""

    value = getattr(trace, field_name, "-")

    if (
        field_name == "gpu_streams_per_rank"
        and value == -1
    ):
        return "Non-uniform"

    if value is None:
        return "-"

    return str(value)


def _validate_trace_section(section: ReportSection) -> None:
    """Validate that a section can be rendered as trace configuration."""

    if section.section_id != "trace-configuration":
        raise ValueError(
            "Expected section 'trace-configuration', got {!r}.".format(
                section.section_id
            )
        )

    if section.section_type != "overview-traces":
        raise ValueError(
            "Section {!r} has unexpected type {!r}.".format(
                section.section_id,
                section.section_type,
            )
        )


def render_trace_configuration(
    section: ReportSection,
) -> str:
    """Render the semantic Trace Configuration section as HTML."""

    _validate_trace_section(section)

    traces = tuple(section.payload or ())

    if not traces:
        return (
            "<p>No trace configuration information available.</p>"
        )

    first_trace = traces[0]

    _, first_programming_model = _split_trace_mode(
        first_trace.mode
    )

    model_key = _programming_model_key(
        first_programming_model
    )

    resource_columns = _trace_resource_columns(
        model_key
    )

    lines = []

    lines.append("<table class='metric-table'>")
    lines.append("<thead>")
    lines.append("<tr>")

    lines.append("<th>ID</th>")
    lines.append("<th>Trace</th>")
    lines.append("<th>Trace mode</th>")
    lines.append("<th>Programming model</th>")

    for _, label in resource_columns:
        lines.append(
            "<th>{}</th>".format(
                html.escape(label)
            )
        )

    lines.append("</tr>")
    lines.append("</thead>")
    lines.append("<tbody>")

    for trace in traces:
        trace_collection_mode, programming_model = (
            _split_trace_mode(trace.mode)
        )

        lines.append("<tr>")

        lines.append(
            "<td><strong>{}</strong></td>".format(
                html.escape(_format_trace_id(trace))
            )
        )

        lines.append(
            "<td><code>{}</code></td>".format(
                html.escape(str(trace.name))
            )
        )

        lines.append(
            "<td>{}</td>".format(
                html.escape(trace_collection_mode)
            )
        )

        lines.append(
            "<td>{}</td>".format(
                html.escape(programming_model)
            )
        )

        for field_name, _ in resource_columns:
            value = _format_resource_value(
                trace,
                field_name,
            )

            lines.append(
                "<td>{}</td>".format(
                    html.escape(value)
                )
            )

        lines.append("</tr>")

    lines.append("</tbody>")
    lines.append("</table>")

    return "\n".join(lines)


def _get_child(
    section: ReportSection,
    child_id: str,
) -> ReportSection:
    """Return one direct child section."""

    for child in section.children:
        if child.section_id == child_id:
            return child

    raise ValueError(
        "Section {!r} does not contain child {!r}.".format(
            section.section_id,
            child_id,
        )
    )


def render_overview(
    section: ReportSection,
) -> str:
    """Render the semantic Overview section.

    Phase 3.2 initially renders only Trace Configuration. The remaining
    semantic Overview subsections will be added incrementally.
    """

    if section.section_id != "overview":
        raise ValueError(
            "Expected section 'overview', got {!r}.".format(
                section.section_id
            )
        )

    trace_section = _get_child(
        section,
        "trace-configuration",
    )

    trace_configuration_html = (
        render_trace_configuration(trace_section)
    )

    return """
    <section class="application-panel" aria-label="Application analysis">
        <div class="workspace-panel">
            <h2>{title}</h2>

            <section class="report-section">
                <h3>{trace_title}</h3>
                {trace_configuration_html}
            </section>
        </div>
    </section>
    """.format(
        title=html.escape(section.title),
        trace_title=html.escape(trace_section.title),
        trace_configuration_html=trace_configuration_html,
    )