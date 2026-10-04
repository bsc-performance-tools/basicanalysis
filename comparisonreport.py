#!/usr/bin/env python3

"""Interactive report for the comparison of programming models.

When the analyzed traces use different programming models, the interactive
report contains:

    - A "Programming Model Comparison" tab: the traces, their general
      metrics and the efficiency metrics of each trace's own programming
      model, with Metric Details for every value.
    - One tab per programming model: the standard BasicAnalysis report of
      the traces of that model, analyzed as an independent set.

Each per-model report is embedded as an isolated document (iframe), so the
standard report is reused unchanged.
"""

from __future__ import print_function, division

import html
import json
import os

import interactiveplots as ip

from comparison import (
    build_comparison_cells,
    build_comparison_device_cells,
    get_programming_model,
    get_programming_models,
)
from report.renderer.html import (
    render_execution_mapping,
    render_trace_configuration,
)


SECTION_ID = "programming-model-comparison"

# Metrics whose definition depends on the second-level runtime.
RUNTIME_SPECIFIC_METRICS = (
    "hybrid_eff",
    "omp_parallel_eff",
    "omp_load_balance",
    "omp_comm_eff",
)


# --------------------------------------------------
# Efficiency comparison table
# --------------------------------------------------

def _label_depth(label, device_row=False):
    """Hierarchy depth of a comparison-table label."""
    stripped = label.lstrip(' ')
    if not stripped.startswith('--'):
        return 0

    depth = (len(label) - len(stripped)) // 3 + 1

    # Device children are indented one extra level in the terminal table.
    if device_row:
        depth -= 1

    return depth


def _clean_label(label):
    return label.strip().lstrip('-').strip()


def _cell_info_key(model, cell):
    """Identify the definition shown by a cell (Metric Details)."""
    runtime = cell.runtime if cell.metric_key in RUNTIME_SPECIFIC_METRICS else None
    return "{}|{}|{}".format(model, cell.metric_key, runtime or "")


def _build_metric_info(rows, trace_list, trace_mode):
    """Build the Metric Details information of every comparison cell.

    A row can show a different metric for each programming model (e.g.
    Load Balance for MPI and MPI Load Balance for MPI+CUDA). Each cell
    therefore refers to the definition of its own trace's metric.
    """
    data = {}

    for _, cells, _ in rows:
        for trace in trace_list:
            cell = cells[trace]
            if cell is None:
                continue

            model = get_programming_model(trace_mode[trace])
            info_key = _cell_info_key(model, cell)
            if info_key in data:
                continue

            runtime = (
                cell.runtime
                if cell.metric_key in RUNTIME_SPECIFIC_METRICS
                else None
            )

            knowledge = ip.KNOWLEDGE_PROVIDER.get(
                cell.metric_key,
                runtime=runtime,
            )

            info_json = ip._metric_info_json(
                [cell.metric_key],
                {cell.metric_key: {"type": "{} metric".format(model)}},
                {cell.metric_key: knowledge},
            )

            data[info_key] = json.loads(info_json)[cell.metric_key]

    return data


def _comparison_rows(metrics_result, trace_list, trace_mode):
    """Return comparison rows as (label, cells, is_device_row)."""
    rows = [
        (label, cells, False)
        for label, cells in build_comparison_cells(
            trace_list,
            trace_mode,
            metrics_result["mod_factors"],
            metrics_result["hybrid_factors"],
            metrics_result["host_factors"],
        )
    ]

    rows += [
        (label, cells, True)
        for label, cells in build_comparison_device_cells(
            trace_list,
            trace_mode,
            metrics_result["device_factors"],
        )
    ]

    return rows


def _build_comparison_table_html(rows, trace_list, trace_labels,
                                 trace_mode, printable=False):
    """Build the efficiency comparison table (heatmap)."""
    lines = []

    lines.append("<div class='efficiency-table-wrapper'>")
    lines.append("<table class='efficiency-table pmc-efficiency-table'>")

    lines.append("<thead><tr>")
    lines.append("<th class='metric-column-header'>Metric</th>")
    for index, trace in enumerate(trace_list):
        lines.append(
            "<th>{label}<br><span class='pmc-column-model'>{model}</span></th>".format(
                label=html.escape(trace_labels[index]),
                model=html.escape(get_programming_model(trace_mode[trace])),
            )
        )
    lines.append("</tr></thead>")

    lines.append("<tbody>")

    previous_device_row = False

    for label, cells, device_row in rows:
        clean_label = _clean_label(label)
        depth = _label_depth(label, device_row)

        row_class = ""
        if device_row and not previous_device_row:
            row_class = " class='pmc-domain-start'"
        previous_device_row = device_row

        first_cell = next(
            (cell for cell in cells.values() if cell is not None),
            None,
        )
        family = ip._metric_family(
            first_cell.metric_key if first_cell else "",
            clean_label,
        )

        if depth == 0:
            display_label = "<strong>{}</strong>".format(html.escape(clean_label))
        else:
            display_label = "↳ {}".format(html.escape(clean_label))

        lines.append("<tr{}>".format(row_class))
        lines.append(
            "<td class='metric-name-cell metric-family-{family}' "
            "style='--metric-depth: {depth};'>{label}</td>".format(
                family=family,
                depth=depth,
                label=display_label,
            )
        )

        for index, trace in enumerate(trace_list):
            cell = cells[trace]
            model = get_programming_model(trace_mode[trace])

            if cell is None:
                lines.append(
                    "<td class='metric-value-cell pmc-not-applicable' "
                    "title='Not applicable to {model}'></td>".format(
                        model=html.escape(model, quote=True),
                    )
                )
                continue

            value = ip._clean_value(cell.value)

            if value is None:
                if cell.value == "Warning!":
                    display_value = "Warning!"
                else:
                    display_value = ip._format_unavailable_metric_value(cell.value)
                js_value = "null"
            else:
                display_value = "{:.2f}%".format(value)
                js_value = "{:.10f}".format(value)

            background_color = ip._metric_value_color(value)
            text_color = ip._cell_text_color(value)

            if printable:
                lines.append(
                    "<td class='metric-value-cell'>"
                    "<span class='metric-value metric-value-print' "
                    "style='background:{background}; color:{text_color};'>"
                    "{display_value}</span></td>".format(
                        background=background_color,
                        text_color=text_color,
                        display_value=display_value,
                    )
                )
                continue

            lines.append(
                "<td class='metric-value-cell'>"
                "<button type='button' class='metric-value' "
                "style='background:{background}; color:{text_color};' "
                "onclick=\"selectMetricCell(this, '{section_id}', "
                "'{info_key}', '{metric_label}', '{trace_label}', {value})\">"
                "{display_value}</button></td>".format(
                    background=background_color,
                    text_color=text_color,
                    section_id=SECTION_ID,
                    info_key=html.escape(_cell_info_key(model, cell), quote=True),
                    metric_label=html.escape(clean_label, quote=True),
                    trace_label=html.escape(trace_labels[index], quote=True),
                    value=js_value,
                    display_value=display_value,
                )
            )

        lines.append("</tr>")

    lines.append("</tbody>")
    lines.append("</table>")
    lines.append("</div>")

    return "\n".join(lines)


# --------------------------------------------------
# Comparison view content
# --------------------------------------------------

def _build_notice_html(trace_list, trace_mode, trace_labels):
    models = get_programming_models(trace_list, trace_mode)

    return """
    <div class="analysis-scope-note">
        <h3>Comparison of programming models</h3>
        <p>
            The analyzed traces use different programming models:
            <strong>{models}</strong>. Each trace is described with the
            efficiency metrics of its own programming model. Empty cells
            correspond to metrics that do not apply to a programming model.
        </p>
        <p>
            Scalability metrics are not computed across programming models,
            because the executions use different kinds of resources.
            Speedup is the runtime ratio relative to the first trace
            (<strong>{reference}</strong>, <code>{reference_trace}</code>).
        </p>
        <p>
            Use the programming-model tabs to open the complete analysis of
            the traces of each model.
        </p>
    </div>
    """.format(
        models=html.escape(", ".join(models)),
        reference=html.escape(trace_labels[0] if trace_labels else ""),
        reference_trace=html.escape(os.path.basename(trace_list[0])),
    )


def _build_general_metrics_html(other_metrics, trace_list, trace_labels,
                                trace_mode):
    """Elapsed time, Speedup, IPC and frequency of each trace."""
    rows = [
        ("Elapsed time (s)", "elapsed_time"),
        ("Speedup (relative to the first trace)", "speedup"),
        ("Average IPC", "ipc"),
        ("Average frequency (GHz)", "freq"),
    ]

    lines = ["<table class='metric-table'>", "<thead><tr>", "<th>Metric</th>"]
    for index, trace in enumerate(trace_list):
        lines.append(
            "<th>{label}<br><span class='pmc-column-model'>{model}</span></th>".format(
                label=html.escape(trace_labels[index]),
                model=html.escape(get_programming_model(trace_mode[trace])),
            )
        )
    lines.append("</tr></thead><tbody>")

    for label, key in rows:
        lines.append("<tr><td>{}</td>".format(label))
        for trace in trace_list:
            value = other_metrics.get(key, {}).get(trace, "Non-Avail")
            lines.append(
                "<td>{}</td>".format(ip._format_overview_value(key, value))
            )
        lines.append("</tr>")

    lines.append("</tbody></table>")

    return "\n".join(lines)


def _build_trace_sections_html(report_model):
    """Trace configuration and execution mapping of all traces."""
    trace_configuration_section = report_model.get_section(
        "trace-configuration"
    )
    execution_mapping_section = report_model.get_section(
        "execution-mapping"
    )

    trace_config_html = ""
    execution_mapping_html = ""

    if trace_configuration_section is not None:
        trace_config_html = render_trace_configuration(
            trace_configuration_section
        )

        if execution_mapping_section is not None:
            execution_mapping_html = render_execution_mapping(
                execution_mapping_section,
                trace_configuration_section.payload,
            )

    return trace_config_html, execution_mapping_html


def _build_comparison_view_html(metrics_result, report, report_model,
                                trace_list, trace_mode, printable=False):
    """Build the content of the Programming Model Comparison tab."""
    other_metrics = metrics_result["other_metrics"]

    trace_labels = ip._build_report_trace_labels(report.get("traces", []))

    rows = _comparison_rows(metrics_result, trace_list, trace_mode)

    trace_config_html, execution_mapping_html = (
        _build_trace_sections_html(report_model)
    )

    table_html = _build_comparison_table_html(
        rows,
        trace_list,
        trace_labels,
        trace_mode,
        printable=printable,
    )

    if printable:
        # Same wrapper as the standard printable report, so the print
        # styles fit the table to the page width.
        table_html = (
            "<div class='print-metric-results metric-table-card "
            "print-export-style'>{}</div>".format(table_html)
        )

    column_note = (
        "<p class='section-description'>Columns: execution configuration "
        "and programming model of each trace.</p>"
    )

    io_html = ""
    if not printable and ip._has_io_metrics(other_metrics, trace_list):
        io_html = """
        <section class="report-section">
            {io_section}
        </section>
        """.format(
            io_section=ip._build_io_metrics_section(
                other_metrics=other_metrics,
                trace_list=trace_list,
                trace_labels=trace_labels,
                trace_header_note=column_note,
                trace_column_description="",
            ),
        )

    metric_info_script = ""
    interaction_hint = ""
    if not printable:
        metric_info_script = (
            "<script>window[\"metricInfo_{section_id}\"] = {info};</script>"
        ).format(
            section_id=SECTION_ID,
            info=json.dumps(_build_metric_info(rows, trace_list, trace_mode)),
        )
        interaction_hint = ip._build_metric_interaction_hint_html()

    return """
    <section class="application-panel" aria-label="Programming model comparison">
        <div class="workspace-panel">
            <h2>Programming Model Comparison</h2>

            {notice_html}

            <section class="report-section">
                <h3>Trace configuration</h3>
                {trace_config_html}
            </section>

            <section class="report-section">
                <h3>Execution mapping</h3>
                {execution_mapping_html}
            </section>

            <section class="report-section">
                <h3>General metrics</h3>
                {column_note}
                {general_html}
            </section>

            <section class="report-section">
                <h3>Efficiency metrics</h3>
                {column_note}
                {interaction_hint}
                {metric_info_script}
                {table_html}
                {efficiency_scale_html}
            </section>

            {io_html}
        </div>
    </section>
    """.format(
        notice_html=_build_notice_html(trace_list, trace_mode, trace_labels),
        trace_config_html=trace_config_html,
        execution_mapping_html=execution_mapping_html,
        column_note=column_note,
        general_html=_build_general_metrics_html(
            other_metrics, trace_list, trace_labels, trace_mode,
        ),
        interaction_hint=interaction_hint,
        metric_info_script=metric_info_script,
        table_html=table_html,
        efficiency_scale_html=ip._build_efficiency_scale_html(),
        io_html=io_html,
    )


# --------------------------------------------------
# Tabs and document
# --------------------------------------------------

COMPARISON_STYLE = """
<style>
    /*
     * The report page does not scroll (body overflow is hidden): the
     * workspace fills the available height and each panel scrolls.
     */
    .pmc-workspace {
        display: flex;
        flex-direction: column;
        height: 100%;
        min-height: 0;
    }

    .pmc-toolbar {
        flex: 0 0 auto;
        display: flex;
        align-items: flex-end;
        justify-content: space-between;
        gap: 12px;
        border-bottom: 1px solid var(--border);
        margin-bottom: 16px;
        flex-wrap: wrap;
    }

    .pmc-tabs {
        display: flex;
        gap: 4px;
        flex-wrap: wrap;
    }

    .pmc-tab {
        border: 1px solid var(--border);
        border-bottom: none;
        border-radius: var(--radius-sm) var(--radius-sm) 0 0;
        background: var(--surface-soft);
        color: var(--text-secondary);
        padding: 10px 16px;
        font: inherit;
        font-weight: 600;
        cursor: pointer;
    }

    .pmc-tab:hover {
        color: var(--primary);
        background: var(--primary-light);
    }

    .pmc-tab[aria-selected="true"] {
        background: var(--surface);
        color: var(--primary);
        box-shadow: inset 0 3px 0 var(--primary);
    }

    .pmc-tab-detail {
        display: block;
        font-size: 0.8em;
        font-weight: 400;
    }

    .pmc-print-button {
        margin-bottom: 8px;
        border: 1px solid var(--border);
        border-radius: var(--radius-sm);
        background: var(--surface);
        color: var(--primary);
        padding: 8px 14px;
        font: inherit;
        cursor: pointer;
    }

    .pmc-print-button:hover {
        background: var(--primary-light);
    }

    .pmc-panel {
        flex: 1 1 auto;
        min-height: 0;
        overflow-y: auto;
    }

    .pmc-panel[hidden] {
        display: none;
    }

    .pmc-model-panel {
        display: flex;
        flex-direction: column;
        overflow: hidden;
    }

    .pmc-column-model {
        font-weight: 400;
        font-size: 0.85em;
        opacity: 0.8;
    }

    .pmc-not-applicable {
        background: repeating-linear-gradient(
            -45deg,
            transparent,
            transparent 6px,
            rgba(92, 103, 122, 0.06) 6px,
            rgba(92, 103, 122, 0.06) 12px
        );
    }

    .pmc-domain-start td {
        border-top: 2px solid var(--border);
    }

    .pmc-model-note {
        flex: 0 0 auto;
        color: var(--text-secondary);
        margin: 0 0 8px 0;
    }

    .pmc-model-frame {
        flex: 1 1 auto;
        width: 100%;
        min-height: 0;
        border: 1px solid var(--border);
        border-radius: var(--radius-md);
        background: var(--surface);
    }
</style>
"""

COMPARISON_SCRIPT = """
<script>
    function showComparisonTab(button) {
        const tabs = document.querySelectorAll(".pmc-tab");

        for (let i = 0; i < tabs.length; i++) {
            const selected = tabs[i] === button;
            tabs[i].setAttribute("aria-selected", selected ? "true" : "false");

            const panel = document.getElementById(
                tabs[i].getAttribute("aria-controls")
            );

            if (panel) {
                panel.hidden = !selected;
            }
        }

        const printButton = document.querySelector(".pmc-print-button");
        if (printButton) {
            printButton.hidden = button.getAttribute("aria-controls")
                !== "pmc-comparison";
        }
    }

    function printComparisonReport() {
        const printableReport = document.querySelector(
            "[data-basicanalysis-printable-report]"
        );

        if (!printableReport) {
            return;
        }

        document.body.classList.add("basicanalysis-print-mode");
        printableReport.hidden = false;

        window.setTimeout(function () {
            window.print();
        }, 50);
    }

    window.addEventListener("afterprint", function () {
        const printableReport = document.querySelector(
            "[data-basicanalysis-printable-report]"
        );

        document.body.classList.remove("basicanalysis-print-mode");

        if (printableReport) {
            printableReport.hidden = true;
        }
    });
</script>
"""


def _build_workspace_html(comparison_html, model_reports):
    """Tab bar, comparison panel and one embedded report per model."""
    tabs = [
        "<button type='button' role='tab' class='pmc-tab' "
        "id='pmc-tab-comparison' aria-controls='pmc-comparison' "
        "aria-selected='true' onclick='showComparisonTab(this)'>"
        "Programming Model Comparison"
        "<span class='pmc-tab-detail'>All traces</span>"
        "</button>"
    ]

    panels = [
        "<div id='pmc-comparison' class='pmc-panel' role='tabpanel' "
        "aria-labelledby='pmc-tab-comparison'>{}</div>".format(comparison_html)
    ]

    for index, model_report in enumerate(model_reports, start=1):
        model = model_report["model"]
        traces = model_report["traces"]

        count = len(traces)
        detail = "{} trace{}".format(count, "" if count == 1 else "s")

        tabs.append(
            "<button type='button' role='tab' class='pmc-tab' "
            "id='pmc-tab-model-{index}' aria-controls='pmc-model-{index}' "
            "aria-selected='false' onclick='showComparisonTab(this)'>"
            "{model}<span class='pmc-tab-detail'>{detail}</span>"
            "</button>".format(
                index=index,
                model=html.escape(model),
                detail=detail,
            )
        )

        trace_names = ", ".join(
            html.escape(os.path.basename(trace)) for trace in traces
        )

        panels.append(
            "<div id='pmc-model-{index}' class='pmc-panel pmc-model-panel' "
            "role='tabpanel' "
            "aria-labelledby='pmc-tab-model-{index}' hidden>"
            "<p class='pmc-model-note'>Complete analysis of the "
            "<strong>{model}</strong> traces, analyzed as an independent "
            "set: {trace_names}</p>"
            "<iframe class='pmc-model-frame' title='{model} analysis' "
            "loading='lazy' srcdoc=\"{srcdoc}\"></iframe>"
            "</div>".format(
                index=index,
                model=html.escape(model),
                trace_names=trace_names,
                srcdoc=html.escape(model_report["html"], quote=True),
            )
        )

    return """
    {style}
    <div class="pmc-workspace">
    <div class="pmc-toolbar">
        <div class="pmc-tabs" role="tablist" aria-label="Programming models">
            {tabs}
        </div>
        <button type="button" class="pmc-print-button"
                onclick="printComparisonReport()">
            Print comparison
        </button>
    </div>
    {panels}
    </div>
    {script}
    """.format(
        style=COMPARISON_STYLE,
        tabs="\n".join(tabs),
        panels="\n".join(panels),
        script=COMPARISON_SCRIPT,
    )


def build_comparison_report_html(metrics_result, report, report_model,
                                 trace_list, trace_mode, model_reports):
    """Build the interactive comparison report and return it."""
    comparison_html = _build_comparison_view_html(
        metrics_result,
        report,
        report_model,
        trace_list,
        trace_mode,
    )

    printable_html = _build_comparison_view_html(
        metrics_result,
        report,
        report_model,
        trace_list,
        trace_mode,
        printable=True,
    )

    return ip._build_interactive_report_document(
        workspace_html=_build_workspace_html(comparison_html, model_reports),
        printable_report_html=printable_html,
    )


def plot_comparison_interactive_report(metrics_result, report,
                                       report_model, trace_list,
                                       trace_mode, model_reports):
    """Write the interactive comparison report."""
    output_html = os.path.join(
        os.getcwd(),
        "basicanalysis_interactive_report.html",
    )

    html_content = build_comparison_report_html(
        metrics_result,
        report,
        report_model,
        trace_list,
        trace_mode,
        model_reports,
    )

    with open(output_html, "w") as output_file:
        output_file.write(html_content)

    print("Interactive report written to {}".format(output_html))

    return output_html
