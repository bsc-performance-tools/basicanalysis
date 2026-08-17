#!/usr/bin/env python3

"""Interactive HTML reports for BasicAnalysis hybrid metrics."""

from __future__ import print_function, division

import os
import math
import json
import html
import observations

import plotly.graph_objects as go

from report.renderer.html import (
    build_analysis_catalogue,
    render_analysis_navigation,
    render_performance_assessment,
    render_trace_configuration,
)


from metrics import (
    get_default_knowledge_base,
    get_default_provider,
)

#
# Metric Knowledge Base
#
KB = get_default_knowledge_base()

#
# Typed semantic provider
#
KNOWLEDGE_PROVIDER = get_default_provider()


class MetricInfoProvider:
    """Presentation adapter for the metric knowledge base.

    The knowledge base remains the authoritative semantic source. This adapter
    provides the flattened dictionaries currently expected by the report
    builders and applies optional presentation overrides without mutating the
    knowledge-base data.

    Keeping this boundary explicit allows future report stages to expose richer
    fields such as formulas, derivations, dependencies, assumptions, and
    diagnostic causes without coupling the report code to the internal YAML
    representation.
    """

    def __init__(self, knowledge_base):
        self._knowledge_base = knowledge_base

    def get(self, metric_key, runtime=None, runtime_family=None,
            presentation=None, overrides=None):
        """Return one report-ready metric-information dictionary."""
        info = self._knowledge_base.as_legacy_info(
            metric_key,
            runtime=runtime,
            runtime_family=runtime_family,
        )
        info = dict(info)

        if presentation:
            info.update(presentation)

        if overrides:
            info.update(overrides)

        return info

    def build(self, presentation, runtime=None, runtime_family=None):
        """Build report-ready metadata for a presentation mapping."""
        metric_info = {}

        for metric_key, presentation_info in presentation.items():
            metric_info[metric_key] = self.get(
                metric_key,
                runtime=runtime,
                runtime_family=runtime_family,
                presentation=presentation_info,
            )

        return metric_info

    @staticmethod
    def clone(metric_info):
        """Return a safe shallow copy of a metric-information mapping."""
        return {
            metric_key: dict(info)
            for metric_key, info in metric_info.items()
        }


USE_GUIDED_ANALYSIS_NAVIGATION = True

METRIC_PROVIDER = MetricInfoProvider(KB)


EFFICIENCY_COLOR_SCALE = [
    (0.00, "#b2182b"),
    (0.20, "#ef6548"),
    (0.40, "#fdbb84"),
    (0.60, "#fee8a8"),
    (0.75, "#ffffbf"),
    (0.85, "#d9ef8b"),
    (0.92, "#b8e186"),
    (1.00, "#4dac26"),
]

def _format_unavailable_metric_value(raw_value):
    if raw_value == "Non-Avail":
        return "Non-Avail"

    if raw_value == "NaN":
        return "NaN"

    if raw_value == "N/A":
        return "N/A"

    return "Non-Avail"

def _build_simple_metric_info():
    """Build the standard POP metric metadata from the knowledge base.

    The knowledge base owns the methodological content.  This function adds
    only presentation details that are specific to the current report, such as
    hierarchy markers used by the legacy Plotly views.
    """

    presentation = {
        "global_eff": {
            "label": "Global efficiency",
            "short_label": "Global",
        },
        "parallel_eff": {
            "label": "-- Parallel efficiency",
            "short_label": "PE",
        },
        "load_balance": {
            "label": "   -- Load balance",
            "short_label": "LB",
        },
        "comm_eff": {
            "label": "   -- Communication efficiency",
            "short_label": "Comm",
        },
        "serial_eff": {
            "label": "      -- Serialization efficiency",
            "short_label": "Ser",
        },
        "transfer_eff": {
            "label": "      -- Transfer efficiency",
            "short_label": "Trans",
        },
        "comp_scale": {
            "label": "-- Computation scalability",
            "short_label": "Comp scale",
        },
        "ipc_scale": {
            "label": "   -- IPC scalability",
            "short_label": "IPC",
        },
        "inst_scale": {
            "label": "   -- Instruction scalability",
            "short_label": "Inst",
        },
        "freq_scale": {
            "label": "   -- Frequency scalability",
            "short_label": "Freq",
        },
    }

    return METRIC_PROVIDER.build(presentation)


# Standard application-level and single-runtime POP metrics are obtained
# through the shared presentation adapter.
SIMPLE_METRIC_INFO = _build_simple_metric_info()


def _build_hybrid_base_metric_info(inner_model):
    """Build the MPI+X metric metadata from the knowledge base.

    The internal ``omp_*`` identifiers are retained for compatibility with the
    current metric files.  Runtime-aware wording is requested from the
    knowledge base using the actual inner runtime (OpenMP, CUDA, HIP, etc.).
    Only report-specific hierarchy labels remain in this module.
    """

    inner_model = inner_model or "OpenMP"
    runtime_family = inner_model.lower()

    presentation = {
        "hybrid_eff": {
            "label": "Hybrid Parallel efficiency",
            "short_label": "Hybrid PE",
        },
        "mpi_parallel_eff": {
            "label": "  -- MPI Parallel efficiency",
            "short_label": " -- MPI PE",
        },
        "mpi_load_balance": {
            "label": "      -- MPI Load balance",
            "short_label": "  -- MPI LB",
        },
        "mpi_comm_eff": {
            "label": "      -- MPI Communication efficiency",
            "short_label": "  -- MPI Comm",
        },
        "serial_eff": {
            "label": "         -- MPI Serialization efficiency",
            "short_label": "    -- MPI Ser",
        },
        "transfer_eff": {
            "label": "         -- MPI Transfer efficiency",
            "short_label": "    -- MPI Trans",
        },
        "omp_parallel_eff": {
            "label": "  -- {} Parallel efficiency".format(inner_model),
            "short_label": "{} PE".format(inner_model),
        },
        "omp_load_balance": {
            "label": "      -- {} Load balance".format(inner_model),
            "short_label": "{} LB".format(inner_model),
        },
        "omp_comm_eff": {
            "label": "      -- {} Communication efficiency".format(inner_model),
            "short_label": "{} Comm".format(inner_model),
        },
        "omp_serial_eff": {
            "label": "         -- {} Serialization efficiency".format(inner_model),
            "short_label": "{} Ser".format(inner_model),
        },
        "omp_transfer_eff": {
            "label": "         -- {} Transfer efficiency".format(inner_model),
            "short_label": "{} Trans".format(inner_model),
        },
    }

    return METRIC_PROVIDER.build(
        presentation,
        runtime=inner_model,
        runtime_family=runtime_family,
    )


# Compatibility metadata for legacy helpers that do not yet receive the
# execution model explicitly. Runtime-aware report paths call
# _build_hybrid_base_metric_info() with the actual inner runtime.
METRIC_INFO = _build_hybrid_base_metric_info("OpenMP")



def _build_talp_metric_info():
    """Build Host/Device metric metadata from the knowledge base.

    Methodological content comes from the shared knowledge base.  Only
    report-specific labels and hierarchy markers remain in this module.
    """

    presentation = {
        "host_global_eff": {
            "label": "Host Global efficiency",
            "short_label": "Host global",
        },
        "host_parallel_eff": {
            "label": "-- Host Parallel efficiency",
            "short_label": "-- Host PE",
        },
        "mpi_parallel_eff": {
            "label": "   == MPI Parallel efficiency",
            "short_label": " -- MPI PE",
        },
        "mpi_load_balance": {
            "label": "       -- MPI Load balance",
            "short_label": " -- MPI LB",
        },
        "mpi_comm_eff": {
            "label": "       -- MPI Communication efficiency",
            "short_label": " -- MPI Comm",
        },
        "serial_eff": {
            "label": "          -- MPI Serialization efficiency",
            "short_label": "   -- MPI Ser",
        },
        "transfer_eff": {
            "label": "          -- MPI Transfer efficiency",
            "short_label": "   -- MPI Trans",
        },
        "dev_offload_eff": {
            "label": "   == Device Offload efficiency",
            "short_label": "   == Offload",
        },
        "host_comp_scale": {
            "label": "-- Host Computation scalability",
            "short_label": "-- Host scale",
        },
        "ipc_scale": {
            "label": "   -- IPC scalability",
            "short_label": "IPC",
        },
        "inst_scale": {
            "label": "   -- Instruction scalability",
            "short_label": "Inst",
        },
        "freq_scale": {
            "label": "   -- Frequency scalability",
            "short_label": "Freq",
        },
        "dev_global_eff": {
            "label": "Device Global efficiency",
            "short_label": "Dev global",
        },
        "dev_parallel_eff": {
            "label": "-- Device Parallel efficiency",
            "short_label": "-- Dev PE",
        },
        "dev_load_balance": {
            "label": "   == Device Load balance",
            "short_label": "   == Dev LB",
        },
        "dev_comm_eff": {
            "label": "   == Device Communication efficiency",
            "short_label": "   == Dev Comm",
        },
        "dev_orches_eff": {
            "label": "   == Device Orchestration efficiency",
            "short_label": "   == Dev Orch",
        },
        "dev_comp_scale": {
            "label": "-- Device Computation scalability",
            "short_label": "-- Dev scale",
        },
    }

    metric_info = METRIC_PROVIDER.build(presentation)

    # These canonical scalability metrics are interpreted specifically as
    # host-side sub-metrics in the Host execution-domain view.
    for metric_key in ("ipc_scale", "inst_scale", "freq_scale"):
        metric_info[metric_key]["type"] = "Host scalability sub-metric"

    return metric_info


TALP_METRIC_INFO = _build_talp_metric_info()



def _build_openmp_metric_info():
    """OpenMP runtime-specific metrics from the shared knowledge base."""

    presentation = {
        "omp_talp_parallel_eff": {"label": "OpenMP Parallel efficiency","short_label":"OMP Parallel"},
        "omp_talp_serial_eff": {"label": "   -- OpenMP Serial efficiency","short_label":"OMP Serial"},
        "omp_talp_load_balance": {"label": "   -- OpenMP Load balance","short_label":"OMP LB"},
        "omp_talp_scheduling_eff": {"label": "   -- OpenMP Scheduling efficiency","short_label":"OMP Sched"},
    }

    return METRIC_PROVIDER.build(presentation)

OPENMP_METRIC_INFO = _build_openmp_metric_info()


HYBRID_ORDER = [
    "hybrid_eff",
    "mpi_parallel_eff",
    "mpi_load_balance",
    "mpi_comm_eff",
    "serial_eff",
    "transfer_eff",
    "omp_parallel_eff",
    "omp_load_balance",
    "omp_comm_eff",
]

OMP_COMM_ORDER = [
    "omp_serial_eff",
    "omp_transfer_eff",
]


OVERVIEW_ORDER = [
    "elapsed_time",
    "efficiency",
    "speedup",
    "ipc",
    "freq",
]


OVERVIEW_LABELS = {
    "elapsed_time": "Elapsed time (s)",
    "efficiency": "Efficiency (-)",
    "speedup": "Speedup (×)",
    "ipc": "Average IPC (inst/cycle)",
    "freq": "Average frequency (GHz)",
}


OPENMP_ORDER = [
    "omp_talp_parallel_eff",
    "omp_talp_serial_eff",
    "omp_talp_load_balance",
    "omp_talp_scheduling_eff",
]


def _tree_node(metric_key, children=None):
    return {"metric": metric_key, "children": children or []}


# Application-level POP view.  Global Metrics intentionally stop at
# Communication Efficiency.  Serialization and Transfer are runtime-level
# explanations and are therefore shown only in the Parallel Runtime Model.
GLOBAL_TREE = [
    _tree_node("global_eff", [
        _tree_node("parallel_eff", [
            _tree_node("load_balance"),
            _tree_node("comm_eff"),
        ]),
        _tree_node("comp_scale", [
            _tree_node("ipc_scale"),
            _tree_node("inst_scale"),
            _tree_node("freq_scale"),
        ]),
    ])
]

# Runtime views are rooted at Parallel Efficiency.  The available depth is
# determined by the performance model: MPI can expose Serialization and
# Transfer through Dimemas, while other simple runtimes currently stop at
# Load Balance and Communication Efficiency.
GLOBAL_PARALLEL_TREE = [
    _tree_node("parallel_eff", [
        _tree_node("load_balance"),
        _tree_node("comm_eff", [
            _tree_node("serial_eff"),
            _tree_node("transfer_eff"),
        ]),
    ])
]

MPI_RUNTIME_TREE = [
    _tree_node("mpi_parallel_eff", [
        _tree_node("mpi_load_balance"),
        _tree_node("mpi_comm_eff", [
            _tree_node("serial_eff"),
            _tree_node("transfer_eff"),
        ]),
    ])
]

INNER_RUNTIME_TREE = [
    _tree_node("omp_parallel_eff", [
        _tree_node("omp_load_balance"),
        _tree_node("omp_comm_eff", [
            _tree_node("omp_serial_eff"),
            _tree_node("omp_transfer_eff"),
        ]),
    ])
]

HYBRID_TREE = [
    _tree_node("hybrid_eff", [
        _tree_node("mpi_parallel_eff", [
            _tree_node("mpi_load_balance"),
            _tree_node("mpi_comm_eff", [
                _tree_node("serial_eff"),
                _tree_node("transfer_eff"),
            ]),
        ]),
        _tree_node("omp_parallel_eff", [
            _tree_node("omp_load_balance"),
            _tree_node("omp_comm_eff", [
                _tree_node("omp_serial_eff"),
                _tree_node("omp_transfer_eff"),
            ]),
        ]),
    ])
]

TALP_TREE = [
    _tree_node("host_global_eff", [
        _tree_node("host_parallel_eff", [
            _tree_node("mpi_parallel_eff", [
                _tree_node("mpi_load_balance"),
                _tree_node("mpi_comm_eff", [
                    _tree_node("serial_eff"),
                    _tree_node("transfer_eff"),
                ]),
            ]),
            _tree_node("dev_offload_eff"),
        ]),
        _tree_node("host_comp_scale", [
            _tree_node("ipc_scale"),
            _tree_node("inst_scale"),
            _tree_node("freq_scale"),
        ]),
    ]),
    _tree_node("dev_global_eff", [
        _tree_node("dev_parallel_eff", [
            _tree_node("dev_load_balance"),
            _tree_node("dev_comm_eff"),
            _tree_node("dev_orches_eff"),
        ]),
        _tree_node("dev_comp_scale"),
    ]),
]

HOST_TREE = [
    _tree_node("host_global_eff", [
        _tree_node("host_parallel_eff", [
            _tree_node("mpi_parallel_eff", [
                _tree_node("mpi_load_balance"),
                _tree_node("mpi_comm_eff", [
                    _tree_node("serial_eff"),
                    _tree_node("transfer_eff"),
                ]),
            ]),
            _tree_node("dev_offload_eff"),
        ]),
        _tree_node("host_comp_scale", [
            _tree_node("ipc_scale"),
            _tree_node("inst_scale"),
            _tree_node("freq_scale"),
        ]),
    ])
]

DEVICE_TREE = [
    _tree_node("dev_global_eff", [
        _tree_node("dev_parallel_eff", [
            _tree_node("dev_load_balance"),
            _tree_node("dev_comm_eff"),
            _tree_node("dev_orches_eff"),
        ]),
        _tree_node("dev_comp_scale"),
    ])
]

DEVICE_RUNTIME_TREE = [
    _tree_node("dev_parallel_eff", [
        _tree_node("dev_load_balance"),
        _tree_node("dev_comm_eff"),
        _tree_node("dev_orches_eff"),
    ])
]

OPENMP_TREE = [
    _tree_node("omp_talp_parallel_eff", [
        _tree_node("omp_talp_serial_eff"),
        _tree_node("omp_talp_load_balance"),
        _tree_node("omp_talp_scheduling_eff"),
    ])
]


GLOBAL_GPU_TREE = [
    _tree_node("global_eff", [
        _tree_node("parallel_eff", [
            _tree_node("load_balance"),
            _tree_node("comm_eff"),
        ]),
        _tree_node("comp_scale"),
    ])
]


# Computation Scalability is an independent analytical view.
# The semantic ScalabilityAnalysisBuilder determines which nodes are
# available for the current execution model.
SCALABILITY_TREE = [
    _tree_node(
        "comp_scale",
        [
            _tree_node("ipc_scale"),
            _tree_node("inst_scale"),
            _tree_node("freq_scale"),
        ],
    )
]


def _metric_info(metric_key,
                 runtime=None,
                 runtime_family=None):
    """
    Return metric information using the knowledge base.

    This function currently provides a compatibility layer with the
    previous metric dictionaries.
    """

    return METRIC_PROVIDER.get(
        metric_key,
        runtime=runtime,
        runtime_family=runtime_family,
    )


def _default_metric_thresholds():
    """Return the provider-level fallback efficiency thresholds."""
    return KNOWLEDGE_PROVIDER.default_thresholds


def _build_metric_knowledge(
        metric_keys,
        runtime=None,
        runtime_family=None):
    """Resolve typed semantic knowledge for report metrics.

    Parameters
    ----------
    metric_keys
        Metric identifiers used by the report section.
    runtime
        Optional runtime used to resolve template-based metrics such as
        ``omp_parallel_eff``. Despite their historical names, these aliases may
        represent OpenMP, CUDA, HIP, or another inner runtime.
    runtime_family
        Optional normalized runtime family. When omitted, the provider derives
        it from ``runtime``.

    Returns
    -------
    dict
        Mapping from the report metric identifier to an immutable
        ``MetricKnowledge`` object.
    """

    metric_knowledge = {}

    for metric_key in metric_keys:
        metric_knowledge[metric_key] = KNOWLEDGE_PROVIDER.get(
            metric_key,
            runtime=runtime,
            runtime_family=runtime_family,
        )

    return metric_knowledge


def _format_overview_value(key, value):
    if value in ["Non-Avail", "N/A", "NaN", None]:
        return str(value)

    try:
        value = float(value)
    except Exception:
        return str(value)

    return "{:.2f}".format(value)


def _build_overview_table_html(other_metrics, trace_list, trace_labels): 

    headers = trace_labels

    html = []
    html.append("<table class='metric-table'>")

    html.append("<thead><tr>")
    html.append("<th>Metric</th>")
    for header in headers:
        html.append("<th>{}</th>".format(header))
    html.append("</tr></thead>")

    html.append("<tbody>")

    sections = [
        ("Runtime", ["elapsed_time"]),
        ("Performance", ["efficiency", "speedup"]),
        ("Microarchitecture", ["ipc", "freq"]),
    ]

    for section_name, keys in sections:
        # Section header row
        html.append(
            "<tr><td colspan='{}' style='font-weight:bold;background:#eee;text-align:left'>{}</td></tr>".format(
                len(headers) + 1, section_name
            )
        )

        # Metrics inside section
        for key in keys:
            html.append("<tr>")
            html.append("<td>{}</td>".format(OVERVIEW_LABELS[key]))

            for trace in trace_list:
                value = other_metrics.get(key, {}).get(trace, "Non-Avail")
                html.append("<td>{}</td>".format(_format_overview_value(key, value)))

            html.append("</tr>")

    html.append("</tbody>")



    html.append("</table>")
    return "\n".join(html)


def _is_number(value):
    try:
        value = float(value)
        return not math.isnan(value)
    except Exception:
        return False


def _clean_value(value):
    if _is_number(value):
        return float(value)
    return None


def _hover_text(metric_key, value, raw_value):
    info = METRIC_INFO.get(metric_key, {})
    label = info.get("label", metric_key)

    if value is None:
        return (
            "<b>{}</b><br>"
            "Value: {}<br><br>"
            "<b>Interpretation:</b> Metric is not available for this trace or configuration."
        ).format(label, raw_value)

    if value > 100.0:
        interpretation = info.get("above100", "Value above 100%. Interpret carefully.")
    elif value < 85.0:
        interpretation = info.get("low", "Low value. Potential optimization opportunity.")
    else:
        interpretation = "Value is relatively high. This component is probably not the dominant bottleneck."

    return (
        "<b>{}</b><br>"
        "Value: {:.2f}%<br><br>"
        "<b>Metric type:</b> {}<br>"
        "<b>Meaning:</b> {}<br>"
        "<b>Interpretation:</b> {}<br>"
        "<b>Next diagnostic step:</b> {}"
    ).format(
        label,
        value,
        info.get("type", "Metric"),
        info.get("meaning", ""),
        interpretation,
        info.get("action", ""),
    )


def _trace_label(trace, index, trace_processes, trace_tasks, trace_threads, trace_mode):
    tasks = trace_tasks[trace]
    threads = trace_threads[trace]

    if trace_mode[trace][0:len("Detailed+MPI+")] == "Detailed+MPI+":
        label = "{}({}x{})[{}]".format(
            trace_processes[trace], tasks, threads, index + 1
        )
    else:
        label = "{}[{}]".format(trace_processes[trace], index + 1)

    return label


def _read_metric(metrics_dict, metric_key, trace):
    try:
        return metrics_dict[metric_key][trace]
    except Exception:
        return "Non-Avail"


def _seaborn_rdylgn_center75_colorscale():
    return EFFICIENCY_COLOR_SCALE

def _plotly_label(label):
    """Preserve indentation using HTML non-breaking spaces."""
    n_spaces = len(label) - len(label.lstrip(" "))
    return ("&nbsp;" * n_spaces) + label.lstrip(" ")

def _cell_text_color(value):
    """Use white text on dark cells, black text on light cells."""
    if value is None:
        return "black"

    # Low red cells and very high green cells are dark.
    if value < 25.0 or value >= 95.0:
        return "white"

    return "#333333"

def _trace_summary(trace, index, trace_processes, trace_tasks, trace_threads, trace_mode):
    return (
        "Trace {}: mode={}, processes={}, tasks/rank={}, threads/task={}"
    ).format(
        index + 1,
        trace_mode[trace],
        trace_processes[trace],
        trace_tasks[trace],
        trace_threads[trace],
    )


def _hover_text_from_info(metric_info, metric_key, value, raw_value):
    info = metric_info.get(metric_key, {})
    label = info.get("label", metric_key)

    if value is None:
        return (
            "<b>{}</b><br>"
            "Value: {}<br><br>"
            "<b>Interpretation:</b> Metric is not available for this trace or configuration."
        ).format(label, raw_value)

    if value > 100.0:
        interpretation = info.get("above100", "Value above 100%. Interpret carefully.")
    elif value < 85.0:
        interpretation = info.get("low", "Low value. Potential optimization opportunity.")
    else:
        interpretation = "Value is relatively high. This component is probably not the dominant bottleneck."

    return (
        "<b>{}</b><br>"
        "Value: {:.2f}%<br><br>"
        "<b>Metric type:</b> {}<br>"
        "<b>Meaning:</b> {}<br>"
        "<b>Interpretation:</b> {}<br>"
        "<b>Next diagnostic step:</b> {}"
    ).format(
        label,
        value,
        info.get("type", "Metric"),
        info.get("meaning", ""),
        interpretation,
        info.get("action", ""),
    )


def _inner_model_name(trace_mode, trace_list):
    """Return X from Detailed+MPI+X."""
    for trace in trace_list:
        mode = trace_mode[trace]
        prefix = "Detailed+MPI+"
        if mode.startswith(prefix):
            return mode[len(prefix):]
    return "X"


def _build_scaling_model_html(scaling_model):
    """Build the scaling-model summary shown in Computation Scalability."""

    if scaling_model is None:
        return ""

    detected = (
        scaling_model.detected.capitalize()
        if scaling_model.detected
        else "Non-Avail"
    )

    selected = scaling_model.selected.capitalize()

    if scaling_model.selection_mode == "auto":
        selection = "Automatic"
    elif scaling_model.selection_mode == "manual":
        selection = "Manual"
    else:
        selection = "Implicit"

    warning_html = ""

    if scaling_model.overridden:
        warning_html = """
        <div class="scaling-model-warning">
            <strong>Manual override:</strong>
            the scaling model used to compute the metrics differs from
            the automatically detected scaling behavior.
        </div>
        """

    return """
    <section class="scaling-model-panel">
        <div class="scaling-model-header">
            <h3>Scaling model</h3>
            <p>
                Scaling behavior detected from the analyzed executions and
                the model used to compute the scalability metrics.
            </p>
        </div>

        <div class="scaling-model-grid">
            <div class="scaling-model-item">
                <span class="scaling-model-label">
                    Detected scaling
                </span>
                <strong>{detected}</strong>
            </div>

            <div class="scaling-model-item">
                <span class="scaling-model-label">
                    Scaling used
                </span>
                <strong>{selected}</strong>
            </div>

            <div class="scaling-model-item">
                <span class="scaling-model-label">
                    Selection
                </span>
                <strong>{selection}</strong>
            </div>
        </div>

        {warning_html}
    </section>
    """.format(
        detected=html.escape(detected),
        selected=html.escape(selected),
        selection=html.escape(selection),
        warning_html=warning_html,
    )

def _build_global_metric_info(is_hybrid):
    """Build application-level metric guidance for the execution model."""
    metric_info = METRIC_PROVIDER.clone(SIMPLE_METRIC_INFO)

    if not is_hybrid:
        return metric_info

    metric_info["parallel_eff"]["action"] = (
        "Inspect the Parallel Runtime Model and compare the Parallel Efficiency "
        "of each active runtime. Continue the diagnosis from the runtime "
        "exhibiting the lowest efficiency."
    )

    metric_info["load_balance"]["meaning"] = (
        "Overall efficiency of workload distribution after combining the "
        "contributions of all active parallel runtimes."
    )
    metric_info["load_balance"]["low"] = (
        "Low values indicate that one or more active runtimes contribute "
        "workload imbalance to the complete hybrid execution."
    )
    metric_info["load_balance"]["action"] = (
        "Inspect the Load Balance metric of each active runtime in the Parallel "
        "Runtime Model. Compare the runtime-specific values to identify which "
        "runtime contributes most to the overall imbalance, and continue the "
        "diagnosis from the runtime with the lowest value."
    )

    metric_info["comm_eff"]["meaning"] = (
        "Overall communication efficiency after combining communication and "
        "runtime-overhead effects from all active parallel runtimes."
    )
    metric_info["comm_eff"]["low"] = (
        "Low values indicate that one or more active runtimes contribute "
        "communication, synchronization, or runtime overhead."
    )
    metric_info["comm_eff"]["action"] = (
        "Inspect the Communication Efficiency metric of each active runtime in "
        "the Parallel Runtime Model. Continue the diagnosis within the runtime "
        "exhibiting the greatest efficiency loss and follow its child metrics."
    )

    return metric_info


def _build_hybrid_metric_info(inner_model):
    """Build runtime-aware metadata and diagnostic guidance for MPI+X."""
    metric_info = _build_hybrid_base_metric_info(inner_model)

    # The internal keys retain the historical omp_* names, but every
    # user-facing field must identify the actual inner runtime.
    metric_info["omp_parallel_eff"]["label"] = (
        "  -- {} Parallel efficiency".format(inner_model)
    )
    metric_info["omp_parallel_eff"]["short_label"] = (
        "{} PE".format(inner_model)
    )
    metric_info["omp_parallel_eff"]["type"] = (
        "{} contribution to the hybrid model".format(inner_model)
    )
    metric_info["omp_parallel_eff"]["meaning"] = (
        "{} Parallel Efficiency contribution derived from the MPI+{} "
        "multiplicative decomposition.".format(inner_model, inner_model)
    )
    metric_info["omp_parallel_eff"]["low"] = (
        "Low values indicate that {} contributes significant parallel "
        "inefficiency to the complete hybrid execution.".format(inner_model)
    )
    metric_info["omp_parallel_eff"]["above100"] = (
        "Values above 100% indicate that the {} contribution compensates "
        "for efficiency losses observed at the MPI level; this is not a "
        "conventional standalone efficiency.".format(inner_model)
    )

    metric_info["omp_load_balance"]["label"] = (
        "    -- {} Load balance".format(inner_model)
    )
    metric_info["omp_load_balance"]["short_label"] = (
        "{} LB".format(inner_model)
    )
    metric_info["omp_load_balance"]["type"] = (
        "{} contribution to the hybrid model".format(inner_model)
    )
    metric_info["omp_load_balance"]["meaning"] = (
        "{} Load Balance contribution derived from the MPI+{} "
        "multiplicative decomposition.".format(inner_model, inner_model)
    )
    metric_info["omp_load_balance"]["low"] = (
        "Low values indicate that workload distribution associated with {} "
        "contributes significantly to the overall hybrid load imbalance."
    ).format(inner_model)
    metric_info["omp_load_balance"]["above100"] = (
        "Values above 100% indicate that the {} contribution compensates "
        "for load imbalance observed at the MPI level.".format(inner_model)
    )

    metric_info["omp_comm_eff"]["label"] = (
        "    -- {} Communication efficiency".format(inner_model)
    )
    metric_info["omp_comm_eff"]["short_label"] = (
        "{} Comm".format(inner_model)
    )
    metric_info["omp_comm_eff"]["type"] = (
        "{} contribution to the hybrid model".format(inner_model)
    )
    metric_info["omp_comm_eff"]["meaning"] = (
        "{} contribution associated with synchronization, communication, "
        "and runtime-management overhead in the MPI+{} multiplicative "
        "decomposition.".format(inner_model, inner_model)
    )
    metric_info["omp_comm_eff"]["low"] = (
        "Low values indicate that synchronization, communication, or "
        "runtime-management overhead associated with {} significantly limits "
        "the hybrid execution.".format(inner_model)
    )
    metric_info["omp_comm_eff"]["above100"] = (
        "Values above 100% indicate that the {} contribution compensates for "
        "or amplifies communication-related effects observed at the MPI level."
    ).format(inner_model)

    metric_info["hybrid_eff"]["action"] = (
        "Compare MPI Parallel Efficiency with {} Parallel Efficiency and "
        "continue the diagnosis from the runtime exhibiting the lowest "
        "efficiency.".format(inner_model)
    )

    metric_info["mpi_parallel_eff"]["action"] = (
        "Continue the MPI diagnosis using MPI Load Balance and MPI "
        "Communication Efficiency. If MPI Communication Efficiency is low, "
        "inspect MPI Serialization and Transfer Efficiency."
    )
    metric_info["mpi_load_balance"]["action"] = (
        "Compare MPI Load Balance with {} Load Balance to determine the "
        "relative MPI contribution to the overall application imbalance."
    ).format(inner_model)
    metric_info["mpi_comm_eff"]["action"] = (
        "Compare MPI Communication Efficiency with {} Communication "
        "Efficiency. If MPI is lower, inspect MPI Serialization and Transfer "
        "Efficiency."
    ).format(inner_model)

    metric_info["omp_load_balance"]["action"] = (
        "Compare {0} Load Balance with MPI Load Balance to determine which "
        "runtime contributes most to the overall application imbalance. "
        "Continue the diagnosis within {0} if it has the lower value."
    ).format(inner_model)

    metric_info["omp_comm_eff"]["action"] = (
        "Compare {0} Communication Efficiency with MPI Communication "
        "Efficiency to determine which runtime contributes most to the "
        "overall communication or runtime-overhead loss."
    ).format(inner_model)

    if inner_model == "OpenMP":
        metric_info["omp_parallel_eff"]["meaning"] = (
            "OpenMP Parallel Efficiency contribution derived from the "
            "MPI+OpenMP multiplicative decomposition."
        )
        metric_info["omp_parallel_eff"]["low"] = (
            "Low values indicate that OpenMP contributes significant parallel "
            "inefficiency to the complete MPI+OpenMP execution."
        )
        metric_info["omp_parallel_eff"]["action"] = (
            "Continue the diagnosis in the Runtime-Specific Analysis section. "
            "Compare OpenMP Serial Efficiency, OpenMP Region Load Balance, and "
            "OpenMP Scheduling Efficiency to determine whether the OpenMP loss "
            "is caused by serial execution, workload imbalance inside parallel "
            "regions, or runtime scheduling and fork/join overhead."
        )

        metric_info["omp_load_balance"]["meaning"] = (
            "OpenMP Load Balance contribution derived from the MPI+OpenMP "
            "multiplicative decomposition."
        )
        metric_info["omp_load_balance"]["low"] = (
            "Low values indicate that workload distribution among OpenMP "
            "threads contributes significantly to the overall MPI+OpenMP "
            "load imbalance."
        )
        metric_info["omp_load_balance"]["action"] = (
            "Continue the diagnosis in the Runtime-Specific Analysis section. "
            "Inspect OpenMP Region Load Balance to determine whether the "
            "observed OpenMP imbalance originates inside OpenMP parallel "
            "regions. Compare useful computation per thread within those "
            "regions, and do not interpret this metric as identical to the "
            "application-level POP Load Balance."
        )

        metric_info["omp_comm_eff"]["meaning"] = (
            "OpenMP contribution associated with synchronization, scheduling, "
            "fork/join, and runtime-management overhead in the MPI+OpenMP "
            "multiplicative decomposition."
        )
        metric_info["omp_comm_eff"]["low"] = (
            "Low values indicate that OpenMP synchronization, scheduling, "
            "fork/join, or runtime-management overhead significantly limits "
            "the MPI+OpenMP execution."
        )
        metric_info["omp_comm_eff"]["action"] = (
            "Continue the diagnosis in the Runtime-Specific Analysis section. "
            "Inspect OpenMP Scheduling Efficiency and OpenMP Serial Efficiency "
            "to determine whether runtime management, synchronization, "
            "fork/join overhead, or time outside OpenMP parallel regions "
            "limits OpenMP efficiency."
        )

    elif inner_model in ("CUDA", "HIP"):
        metric_info["omp_parallel_eff"]["meaning"] = (
            "{} Parallel Efficiency contribution derived from the MPI+{} "
            "multiplicative decomposition.".format(inner_model, inner_model)
        )
        metric_info["omp_parallel_eff"]["low"] = (
            "Low values indicate that {} execution contributes significant "
            "parallel inefficiency to the complete MPI+{} execution."
        ).format(inner_model, inner_model)
        metric_info["omp_parallel_eff"]["action"] = (
            "Continue the diagnosis in the Execution Domain section. Compare "
            "Host Global Efficiency, Device Offload Efficiency, and Device "
            "Global Efficiency to determine whether the dominant loss "
            "originates in the host-side accelerator execution path, "
            "device-side execution, or both."
        )

        metric_info["omp_load_balance"]["meaning"] = (
            "{} Load Balance contribution derived from the MPI+{} "
            "multiplicative decomposition.".format(inner_model, inner_model)
        )
        metric_info["omp_load_balance"]["low"] = (
            "Low values indicate that workload distribution associated with "
            "{} contributes significantly to the overall MPI+{} load "
            "imbalance.".format(inner_model, inner_model)
        )

        metric_info["omp_load_balance"]["action"] = (
            "Compare {0} Load Balance with MPI Load Balance to identify the "
            "dominant contribution to the overall hybrid imbalance. If {0} is "
            "the main contributor, inspect the Host and Device execution domains "
            "and validate the behavior in the trace. Device Load Balance provides "
            "device-side evidence, but it is not a direct decomposition of this "
            "derived {0} Load Balance contribution."
        ).format(inner_model)

        metric_info["omp_comm_eff"]["meaning"] = (
            "{} contribution associated with synchronization, data movement, "
            "and accelerator runtime-management overhead in the MPI+{} "
            "multiplicative decomposition.".format(inner_model, inner_model)
        )
        metric_info["omp_comm_eff"]["low"] = (
            "Low values indicate that {} synchronization, data movement, or "
            "accelerator runtime-management overhead significantly limits the "
            "MPI+{} execution.".format(inner_model, inner_model)
        )
        metric_info["omp_comm_eff"]["action"] = (
            "Compare {0} Communication Efficiency with MPI Communication "
            "Efficiency to identify the dominant runtime contribution. If {0} "
            "is the main contributor, inspect the Host and Device execution "
            "domains and validate the behavior in the trace. The domain metrics "
            "provide supporting evidence, but they do not directly decompose "
            "this derived {0} Communication Efficiency contribution."
        ).format(inner_model)

    return metric_info


def _build_resources_table_html(report):
    resources = report.get("resources", [])

    if not resources:
        return "<p>No trace resources available.</p>"

    html_lines = []
    html_lines.append("<table class='metric-table'>")
    html_lines.append("<thead><tr>")
    html_lines.append("<th>Trace</th>")
    html_lines.append("<th>Recommended view</th>")
    html_lines.append("<th>Action</th>")
    html_lines.append("</tr></thead>")
    html_lines.append("<tbody>")

    for item in resources:
        trace_path = item.get("prv", "")
        trace_name = os.path.basename(trace_path)
        cfg_path = item.get("overview_cfg", "")

        command = 'wxparaver "{}" "{}"'.format(trace_path, cfg_path)
        command_js = html.escape(command, quote=True)

        html_lines.append("<tr>")
        html_lines.append("<td><code>{}</code></td>".format(trace_name))
        html_lines.append("<td>Useful Duration timeline</td>")
        html_lines.append(
            "<td>"
            "<button class='copy-btn' onclick=\"copyCommand('{}')\">"
            "Copy Paraver command"
            "</button>"
            "</td>".format(command_js)
        )
        html_lines.append("</tr>")

    html_lines.append("</tbody>")
    html_lines.append("</table>")

    html_lines.append(
        "<p class='paraver-view-note'>"
        "<b>Default Paraver view:</b> Useful Duration timeline. "
        "Click the button to copy the command, then paste it in a terminal."
        "</p>"
    )


    return "\n".join(html_lines)


def _build_efficiency_scale_html(thresholds=None):
    """Build the common efficiency interpretation scale."""

    if thresholds is None:
        thresholds = _default_metric_thresholds()

    critical = float(thresholds.critical)
    attention = float(thresholds.attention)
    reference = float(thresholds.reference)

    critical_width = critical
    attention_width = attention - critical
    acceptable_width = reference - attention

    return """
    <div class="efficiency-scale-panel">
        <div class="efficiency-scale-header">
            <h3>Efficiency interpretation</h3>
            <p>
                Use the efficiency scale to identify the metrics requiring
                closer analysis.
            </p>
        </div>

        <div class="efficiency-gradient-container">
            <div class="efficiency-gradient"></div>

            <div
                class="efficiency-scale-compact-labels"
                style="grid-template-columns:
                    {critical_width}fr
                    {attention_width}fr
                    {acceptable_width}fr;"
            >
                <span>
                    <strong>Critical</strong>
                    &lt; {critical:g}%
                </span>

                <span>
                    <strong>Attention</strong>
                    {critical:g}% – {attention:g}%
                </span>

                <span>
                    <strong>Good</strong>
                    ≥ {attention:g}%
                </span>
            </div>
        </div>

        <p class="efficiency-above-reference">
            <strong>Above reference (&gt; {reference:g}%):</strong>
            values are displayed using the upper end of the color scale and
            should be interpreted according to the selected metric.
        </p>

        <p class="efficiency-scale-guidance">
            <strong>Analysis guidance:</strong>
            Start with the lowest-efficiency metrics and follow their child
            metrics to identify the main factor contributing to the efficiency loss.
        </p>
    </div>
    """.format(
        critical=critical,
        attention=attention,
        reference=reference,
        critical_width=critical_width,
        attention_width=attention_width,
        acceptable_width=acceptable_width,
    )


def _split_trace_mode(mode):
    """Split trace collection mode and programming model."""
    parts = str(mode).split("+")

    trace_mode = parts[0]

    if len(parts) > 1:
        programming_model = " + ".join(parts[1:])
    else:
        programming_model = "Unknown"

    return trace_mode, programming_model


def _programming_model_key(programming_model):
    """Return a normalized programming-model identifier."""

    model = str(programming_model).upper().replace(" ", "")

    if model == "MPI":
        return "mpi"

    if model in ("OPENMP", "OMP"):
        return "openmp"

    if model == "PTHREADS":
        return "pthreads"

    if model == "OMPSS":
        return "ompss"

    if model in ("CUDA", "HIP"):
        return "gpu"

    if model in (
        "MPI+OPENMP",
        "MPI+OMP",
        "MPI+PTHREADS",
    ):
        return "mpi_threads"

    if model == "MPI+OMPSS":
        return "mpi_ompss"

    if model in (
        "MPI+CUDA",
        "MPI+HIP",
    ):
        return "mpi_gpu"

    return "generic"

def _report_trace_label(trace_info):
    """Build a model-aware report column label."""

    trace_id = "T{}".format(
        trace_info.get("id", "-")
    )

    _, programming_model = _split_trace_mode(
        trace_info.get("mode", "unknown")
    )

    model_key = _programming_model_key(
        programming_model
    )

    # --------------------------------------------------
    # Single programming models
    # --------------------------------------------------

    if model_key == "mpi":
        return "{} [{}]".format(
            trace_info.get("tasks", "-"),
            trace_id,
        )

    if model_key in (
        "openmp",
        "pthreads",
        "ompss",
    ):
        return "{} [{}]".format(
            trace_info.get("threads", "-"),
            trace_id,
        )

    if model_key == "gpu":
        return "{} [{}]".format(
            trace_info.get("gpu_streams", "-"),
            trace_id,
        )

    # --------------------------------------------------
    # MPI + host threading
    # --------------------------------------------------

    if model_key in (
        "mpi_threads",
        "mpi_ompss",
    ):
        mpi_ranks = trace_info.get("tasks", 0)
        inner_units = trace_info.get("threads", 0)

        try:
            parallel_units = (
                int(mpi_ranks)
                * int(inner_units)
            )
        except (TypeError, ValueError):
            parallel_units = trace_info.get(
                "processes",
                "-",
            )

        return "{} ({}×{}) [{}]".format(
            parallel_units,
            mpi_ranks,
            inner_units,
            trace_id,
        )

    # --------------------------------------------------
    # MPI + GPU
    # --------------------------------------------------

    
    if model_key == "mpi_gpu":
        mpi_ranks = trace_info.get("tasks", 0)

        streams_per_rank = trace_info.get(
            "gpu_streams_per_rank",
            0,
        )

        devices = trace_info.get(
            "devices",
            0,
        )

        if streams_per_rank == -1:
            return "{} ({}×var) [{}D] [{}]".format(
                trace_info.get("gpu_streams", "-"),
                mpi_ranks,
                devices,
                trace_id,
            )

        try:
            parallel_units = (
                int(mpi_ranks)
                * int(streams_per_rank)
            )
        except (TypeError, ValueError):
            parallel_units = trace_info.get(
                "gpu_streams",
                "-",
            )

        return "{} ({}×{}) [{}D] [{}]".format(
            parallel_units,
            mpi_ranks,
            streams_per_rank,
            devices,
            trace_id,
        )


    # --------------------------------------------------
    # Fallback
    # --------------------------------------------------

    return "{} [{}]".format(
        trace_info.get("processes", "-"),
        trace_id,
    )
    

def _build_trace_column_description(report):
    """Return the model-aware meaning of efficiency-table columns."""

    traces = report.get("traces", [])

    if not traces:
        return ""

    _, programming_model = _split_trace_mode(
        traces[0].get("mode", "unknown")
    )

    model_key = _programming_model_key(
        programming_model
    )

    descriptions = {
        "mpi": (
            "MPI ranks"
        ),
        "openmp": (
            "Threads"
        ),
        "pthreads": (
            "Threads"
        ),
        "ompss": (
            "Workers"
        ),
        "gpu": (
            "GPU streams"
        ),
        "mpi_threads": (
            "Parallel units (MPI ranks × threads/rank)"
        ),
        "mpi_ompss": (
            "Parallel units (MPI ranks × workers/rank)"
        ),
        "mpi_gpu": (
            "Parallel units (MPI ranks × streams/rank) "
            "[nD = devices]"
        ),
        "generic": (
            "Parallel units"
        ),
    }

    return descriptions[model_key]


def _build_trace_header_note(report):
    """Explain the model-aware trace column labels."""

    description = _build_trace_column_description(
        report
    )

    if not description:
        return ""

    return (
        "<p class='trace-header-note'>"
        "<b>Trace columns:</b> "
        "<code>{} [Trace ID]</code>"
        "</p>"
    ).format(
        html.escape(description)
    )


def _trace_resource_columns(model_key):
    """Return resource columns for a programming model."""

    columns = {
        "mpi": [
            ("tasks", "MPI ranks"),
        ],

        "openmp": [
            ("threads", "Threads"),
        ],

        "pthreads": [
            ("threads", "Threads"),
        ],

        "ompss": [
            ("threads", "Workers"),
        ],

        "gpu": [
            ("gpu_streams", "GPU streams"),
            ("devices", "Devices"),
        ],

        "mpi_threads": [
            ("processes", "Parallel units"),
            ("tasks", "MPI ranks"),
            ("threads", "Threads/rank"),
        ],

        "mpi_ompss": [
            ("processes", "Parallel units"),
            ("tasks", "MPI ranks"),
            ("threads", "Workers/rank"),
        ],

        "mpi_gpu": [
            ("processes", "Parallel units"),
            ("tasks", "MPI ranks"),
            ("gpu_streams_per_rank", "Streams/rank"),
            ("gpu_streams", "GPU streams"),
            ("devices", "Devices"),
        ],

        "generic": [
            ("processes", "Parallel units"),
        ],
    }

    return columns[model_key]


def _build_trace_config_table_html(report):
    """Build a programming-model-aware trace configuration table."""

    traces = report.get("traces", [])

    if not traces:
        return "<p>No trace configuration information available.</p>"

    first_mode = traces[0].get("mode", "unknown")

    _, programming_model = _split_trace_mode(first_mode)

    model_key = _programming_model_key(programming_model)

    resource_columns = _trace_resource_columns(model_key)

    html_lines = []

    html_lines.append(
        "<table class='metric-table trace-config-table "
        "trace-config-{}'>".format(
            html.escape(model_key)
        )
    )
    html_lines.append("<thead><tr>")

    html_lines.append("<th>ID</th>")
    html_lines.append("<th>Trace</th>")
    html_lines.append("<th>Trace mode</th>")
    html_lines.append("<th>Programming model</th>")


    for _, label in resource_columns:
        html_lines.append(
            "<th>{}</th>".format(html.escape(label))
        )

    html_lines.append("</tr></thead>")
    html_lines.append("<tbody>")

    for trace in traces:
        trace_collection_mode, programming_model = _split_trace_mode(
            trace.get("mode", "unknown")
        )

        trace_id = "T{}".format(trace.get("id", "-"))

        html_lines.append("<tr>")

        html_lines.append(
            "<td><strong>{}</strong></td>".format(
                html.escape(trace_id)
            )
        )        

        html_lines.append(
            "<td><code>{}</code></td>".format(
                html.escape(str(trace.get("name", "unknown")))
            )
        )

        html_lines.append(
            "<td>{}</td>".format(
                html.escape(trace_collection_mode)
            )
        )

        html_lines.append(
            "<td>{}</td>".format(
                html.escape(programming_model)
            )
        )

        for field, _ in resource_columns:
            value = trace.get(field, "-")

            if field == "gpu_streams_per_rank" and value == -1:
                value = "Non-uniform"

            html_lines.append(
                "<td>{}</td>".format(
                    html.escape(str(value))
                )
            )

        html_lines.append("</tr>")

    html_lines.append("</tbody>")
    html_lines.append("</table>")

    return "\n".join(html_lines)
   


def _clean_metric_label(label):
    """Remove visual hierarchy markers from labels for the info panel."""
    return label.replace("-", "").replace("=", "").replace("*", "").strip()



def _metric_info_json(
        metric_keys,
        metric_info,
        metric_knowledge):
    """Serialize metric presentation and semantic knowledge for JavaScript.

    Presentation-specific fields, such as the report label and metric type,
    remain in ``metric_info``. Semantic fields are obtained exclusively from
    ``MetricKnowledge``.

    Legacy aliases are temporarily retained until the JavaScript consumers
    have been migrated to the structured semantic representation.
    """

    data = {}

    for metric_key in metric_keys:
        info = metric_info.get(metric_key, {})
        knowledge = metric_knowledge[metric_key]
        thresholds = knowledge.thresholds

        label = _clean_metric_label(
            info.get("label", knowledge.name)
        )

        definition = knowledge.definition
        interpretation_low = knowledge.interpretation_low
        interpretation_high = knowledge.interpretation_high
        interpretation_above_reference = (
            knowledge.interpretation_above_100
        )

        recommendations = list(knowledge.next_steps)

        # A report section may provide execution-model-specific diagnostic
        # routing. This does not replace the metric semantics; it specializes
        # the next diagnostic step for the current analysis context.
        contextual_action = info.get("action")

        if contextual_action:
            recommendations = [contextual_action]



        data[metric_key] = {
            # ----------------------------------------------
            # Presentation metadata
            # ----------------------------------------------
            "title": label,
            "type": info.get("type", "Metric"),

            # ----------------------------------------------
            # Structured semantic knowledge
            # ----------------------------------------------
            "definition": definition,
            "interpretation": {
                "low": interpretation_low,
                "high": interpretation_high,
                "above_reference": interpretation_above_reference,
            },
            "recommendations": recommendations,
            "thresholds": {
                "critical": thresholds.critical,
                "attention": thresholds.attention,
                "reference": thresholds.reference,
            },

            # ----------------------------------------------
            # Temporary compatibility aliases
            # Remove after migrating the JavaScript.
            # ----------------------------------------------
            "meaning": definition,
            "low": interpretation_low,
            "above100": interpretation_above_reference,
            "action": " ".join(recommendations),
        }

    return json.dumps(data)



def _metric_button(metric_key, metric_info, section_id):
    info = metric_info.get(metric_key, {})
    label = _clean_metric_label(info.get("label", metric_key))

    return (
        '<button class="metric-tree-button" '
        'data-metric-key="{metric_key}" '
        'onclick="selectMetric(\'{section_id}\', \'{metric_key}\')">'
        '{label}</button>'
    ).format(
        section_id=section_id,
        metric_key=metric_key,
        label=html.escape(label),
    )


def _metric_value_color(value):
    """Return interpolated color from the efficiency scale."""
    if value is None:
        return "#f0f2f5"

    normalized = max(0.0, min(float(value), 100.0)) / 100.0

    for index in range(len(EFFICIENCY_COLOR_SCALE) - 1):
        lower_position, lower_color = EFFICIENCY_COLOR_SCALE[index]
        upper_position, upper_color = EFFICIENCY_COLOR_SCALE[index + 1]

        if lower_position <= normalized <= upper_position:
            fraction = (
                (normalized - lower_position)
                / (upper_position - lower_position)
            )

            return _interpolate_color(
                lower_color,
                upper_color,
                fraction,
            )

    return EFFICIENCY_COLOR_SCALE[-1][1]

def _metric_value_text_color(value):
    if value is None:
        return "#7a8490"

    if value < 25.0 or value >= 95.0:
        return "#ffffff"

    return "#263238"    

def _render_tree_node(node, key_set, metric_info, section_id):
    metric_key = node["metric"]

    if metric_key not in key_set:
        return ""

    children = [
        _render_tree_node(child, key_set, metric_info, section_id)
        for child in node.get("children", [])
    ]
    children = [child for child in children if child]

    info = metric_info.get(metric_key, {})
    label = _clean_metric_label(info.get("label", metric_key))

    if children:
        return (
            "<details open>"
            "<summary class='metric-tree-summary' "
            "data-metric-key='{metric_key}' "
            "onclick=\"selectMetric('{section_id}', '{metric_key}')\">"
            "{label}</summary>"
            "<div class='metric-tree-children'>{children}</div>"
            "</details>"
        ).format(
            section_id=section_id,
            metric_key=metric_key,
            label=html.escape(label),
            children="\n".join(children),
        )

    return _metric_button(metric_key, metric_info, section_id)

def _build_metric_tree_html(metric_keys, metric_info, section_id, tree_kind):
    key_set = set(metric_keys)

    if tree_kind == "global":
        tree = GLOBAL_TREE
    elif tree_kind == "hybrid":
        tree = HYBRID_TREE
    elif tree_kind == "talp":
        tree = TALP_TREE
    elif tree_kind == "host":
        tree = HOST_TREE
    elif tree_kind == "device":
        tree = DEVICE_TREE
    elif tree_kind == "runtime_global":
        tree = GLOBAL_PARALLEL_TREE
    elif tree_kind == "runtime_mpi":
        tree = MPI_RUNTIME_TREE
    elif tree_kind == "runtime_inner":
        tree = INNER_RUNTIME_TREE
    elif tree_kind == "runtime_device":
        tree = DEVICE_RUNTIME_TREE
    elif tree_kind == "openmp":
        tree = OPENMP_TREE 
    elif tree_kind == "global_gpu":
        tree = GLOBAL_GPU_TREE
    elif tree_kind == "scalability":
        tree = SCALABILITY_TREE
    else:
        tree = []

    return "\n".join(
        _render_tree_node(node, key_set, metric_info, section_id)
        for node in tree
    )


def _build_execution_domains_section(host_metric_keys, device_metric_keys, host_sources, device_sources, trace_list, trace_labels, trace_header_note, trace_column_description="",):
    """Build the combined Host/Device Execution Domains analysis.

    The Execution Domains view presents Host and Device metrics as two
    complementary parts of the same analytical scope.

    Common information such as the efficiency scale, trace-column
    description, metric-details panel, and analysis summary is rendered
    only once.
    """

    all_metric_keys = (
        list(host_metric_keys)
        + list(device_metric_keys)
    )

    metric_knowledge = _build_metric_knowledge(
        metric_keys=all_metric_keys,
    )

    # --------------------------------------------------
    # Host table
    # --------------------------------------------------

    host_table_html = _build_efficiency_table_html(
        metric_keys=host_metric_keys,
        metric_info=TALP_METRIC_INFO,
        metric_sources=host_sources,
        trace_list=trace_list,
        trace_labels=trace_labels,
        section_id="execution-domains",
        tree=HOST_TREE,
        metric_knowledge=metric_knowledge,
    )

    # --------------------------------------------------
    # Device table
    # --------------------------------------------------

    device_table_html = _build_efficiency_table_html(
        metric_keys=device_metric_keys,
        metric_info=TALP_METRIC_INFO,
        metric_sources=device_sources,
        trace_list=trace_list,
        trace_labels=trace_labels,
        section_id="execution-domains",
        tree=DEVICE_TREE,
        metric_knowledge=metric_knowledge,
    )

    # --------------------------------------------------
    # Shared metric-information dictionary
    # --------------------------------------------------

    info_json = _metric_info_json(
        all_metric_keys,
        TALP_METRIC_INFO,
        metric_knowledge,
    )

    # --------------------------------------------------
    # Host observations
    # --------------------------------------------------

    host_performance = (
        observations.build_performance_interpretation(
            tree=HOST_TREE,
            metric_info=TALP_METRIC_INFO,
            metric_sources=host_sources,
            trace_list=trace_list,
            metric_knowledge=metric_knowledge,
        )
    )

    host_performance_html = (
        observations.build_performance_interpretation_html(
            host_performance
        )
    )

    host_scaling = (
        observations.build_scaling_interpretation(
            tree=HOST_TREE,
            metric_info=TALP_METRIC_INFO,
            metric_sources=host_sources,
            trace_list=trace_list,
            metric_knowledge=metric_knowledge,
        )
    )

    host_scaling_html = (
        observations.build_scaling_interpretation_html(
            host_scaling
        )
    )

    # --------------------------------------------------
    # Device observations
    # --------------------------------------------------

    device_performance = (
        observations.build_performance_interpretation(
            tree=DEVICE_TREE,
            metric_info=TALP_METRIC_INFO,
            metric_sources=device_sources,
            trace_list=trace_list,
            metric_knowledge=metric_knowledge,
        )
    )

    device_performance_html = (
        observations.build_performance_interpretation_html(
            device_performance
        )
    )

    device_scaling = (
        observations.build_scaling_interpretation(
            tree=DEVICE_TREE,
            metric_info=TALP_METRIC_INFO,
            metric_sources=device_sources,
            trace_list=trace_list,
            metric_knowledge=metric_knowledge,
        )
    )

    device_scaling_html = (
        observations.build_scaling_interpretation_html(
            device_scaling
        )
    )

    # --------------------------------------------------
    # Shared context
    # --------------------------------------------------

    efficiency_scale_html = _build_efficiency_scale_html()

    analysis_focus_html = """
    <div class="analysis-scope-note execution-domains-focus">
        <h3>Analysis focus</h3>

        <p>
            The Execution Domains view identifies where
            accelerator-related inefficiencies manifest across host
            execution, the accelerator offload path, and device execution.
        </p>

        <p>
            Host and Device metrics provide complementary evidence and
            should not be interpreted as direct decompositions of the
            runtime-specific metrics shown in the Parallel Runtime Model.
        </p>
    </div>
    """

    return """
    <section
        class="execution-domains-analysis"
        aria-label="Execution Domains"
    >
        <script>
        window["metricInfo_execution-domains"] = {info_json};
        </script>

        {trace_header_note}

        <section
            class="execution-domain-block execution-domain-host"
            aria-label="Host execution domain"
        >
            <div class="execution-domain-title">
                HOST
            </div>

            <div
                class="metric-table-card"
                data-efficiency-export
                data-export-name="execution-domains-host"
                data-export-group="execution-domains"
                data-export-domain="host"
                data-export-columns="{trace_column_description}"
            >
            {host_table_html}
            </div>

        </section>

        <section
            class="execution-domain-block execution-domain-device"
            aria-label="Device execution domain"
        >
            <div class="execution-domain-title">
                DEVICE
            </div>

            <div
                class="metric-table-card"
                data-efficiency-export
                data-export-name="execution-domains-device"
                data-export-group="execution-domains"
                data-export-domain="device"
                data-export-columns="{trace_column_description}"
            >
                {device_table_html}
            </div>

        </section>

        <div class="observation-box execution-domains-analysis-summary">
            <h3>Analysis</h3>

            <section class="execution-domain-analysis-group">
                <h4>HOST</h4>

                {host_performance_html}
                {host_scaling_html}
            </section>

            <section class="execution-domain-analysis-group">
                <h4>DEVICE</h4>

                {device_performance_html}
                {device_scaling_html}
            </section>
        </div>

        {efficiency_scale_html}

        {analysis_focus_html}
    </section>
    """.format(
        info_json=info_json,
        efficiency_scale_html=efficiency_scale_html,
        trace_header_note=trace_header_note,
        trace_column_description=html.escape(trace_column_description, quote=True,),        
        host_table_html=host_table_html,
        device_table_html=device_table_html,
        host_performance_html=host_performance_html,
        host_scaling_html=host_scaling_html,
        device_performance_html=device_performance_html,
        device_scaling_html=device_scaling_html,
        analysis_focus_html=analysis_focus_html,
    )


def _build_metric_tree_heatmap_section(metric_keys, metric_info, metric_sources,
        trace_list, trace_labels, title, section_id,
        tree_kind=None,
        trace_header_note="",
        trace_column_description="",
        runtime=None,
        runtime_family=None):
    # Global Metrics deliberately stop at Communication Efficiency. Keep this
    # invariant here even if a caller supplies runtime-level metrics.
    if tree_kind in ("global", "global_gpu") or section_id == "global":
        excluded_runtime_metrics = {"serial_eff", "transfer_eff"}
        metric_keys = [
            key for key in metric_keys
            if key not in excluded_runtime_metrics
        ]
        metric_sources = {
            key: source for key, source in metric_sources.items()
            if key not in excluded_runtime_metrics
        }

    metric_knowledge = _build_metric_knowledge(
        metric_keys=metric_keys,
        runtime=runtime,
        runtime_family=runtime_family,
    )

    tree = []

    if tree_kind == "global":
        tree = GLOBAL_TREE
    elif tree_kind == "global_gpu":
        tree = GLOBAL_GPU_TREE
    elif tree_kind == "hybrid":
        tree = HYBRID_TREE
    elif tree_kind == "talp":
        tree = TALP_TREE
    elif tree_kind == "host":
        tree = HOST_TREE
    elif tree_kind == "device":
        tree = DEVICE_TREE
    elif tree_kind == "runtime_global":
        tree = GLOBAL_PARALLEL_TREE
    elif tree_kind == "runtime_mpi":
        tree = MPI_RUNTIME_TREE
    elif tree_kind == "runtime_inner":
        tree = INNER_RUNTIME_TREE
    elif tree_kind == "runtime_device":
        tree = DEVICE_RUNTIME_TREE
    elif tree_kind == "openmp":
        tree = OPENMP_TREE
    elif tree_kind == "scalability":
        tree = SCALABILITY_TREE

    efficiency_table_html = _build_efficiency_table_html(
        metric_keys=metric_keys,
        metric_info=metric_info,
        metric_sources=metric_sources,
        trace_list=trace_list,
        trace_labels=trace_labels,
        section_id=section_id,
        tree=tree,
        metric_knowledge=metric_knowledge,
    )

    efficiency_scale_html = _build_efficiency_scale_html()

    info_json = _metric_info_json(
        metric_keys,
        metric_info,
        metric_knowledge,
    )

    if tree:
        performance_interpretation = (
            observations.build_performance_interpretation(
                tree=tree,
                metric_info=metric_info,
                metric_sources=metric_sources,
                trace_list=trace_list,
                metric_knowledge=metric_knowledge,
            )
        )

        performance_interpretation_html = (
            observations.build_performance_interpretation_html(
                performance_interpretation
            )
        )

        scaling_interpretation = observations.build_scaling_interpretation(
            tree=tree,
            metric_info=metric_info,
            metric_sources=metric_sources,
            trace_list=trace_list,
            metric_knowledge=metric_knowledge,
        )


        scaling_interpretation_html = (
            observations.build_scaling_interpretation_html(
                scaling_interpretation
            )
        )

        observations_html = observations.build_analysis_summary_html(
            performance_html=performance_interpretation_html,
            scaling_html=scaling_interpretation_html,
            title="Analysis summary",
        )
    else:
        observation_groups = observations.build_threshold_observations(
            metric_keys=metric_keys,
            metric_info=metric_info,
            metric_sources=metric_sources,
            trace_list=trace_list,
            max_attention=5,
            max_trends=4,
            metric_knowledge=metric_knowledge,
        )

        observations_html = observations.build_threshold_observation_html(
            observation_groups,
            title="Analysis summary",
        )

    return """
    <script>
    window["metricInfo_{section_id}"] = {info_json};
    </script>

    {trace_header_note}

    <div
        class="metric-table-card"
        data-efficiency-export
        data-export-name="{section_id}"
        data-export-columns="{trace_column_description}"
    >
        {efficiency_table_html}
    </div>

    {observations_html}

    {efficiency_scale_html}
    """.format(
        section_id=section_id,
        info_json=info_json,
        efficiency_scale_html=efficiency_scale_html,
        trace_header_note=trace_header_note,
        trace_column_description=html.escape(
            trace_column_description,
            quote=True,),        
        observations_html=observations_html,
        efficiency_table_html=efficiency_table_html,
    )


def _build_efficiency_heatmap_div(metric_keys, metric_info, metric_sources,
                                  trace_list, trace_processes, trace_tasks,
                                  trace_threads, trace_mode, title,
                                  section_id=None):
    """Build a Plotly heatmap div for embedding inside the unified HTML report."""

    y_values = list(range(len(metric_keys)))

    metric_labels = [metric_info[key]["label"] for key in metric_keys]

    x_labels = [
        _trace_label(trace, index, trace_processes, trace_tasks, trace_threads, trace_mode)
        for index, trace in enumerate(trace_list)
    ]

    z_values = []
    text_values = []
    hover_values = []
    custom_values = []

    for key in metric_keys:
        z_row = []
        text_row = []
        hover_row = []
        custom_row = []

        source = metric_sources[key]

        for index, trace in enumerate(trace_list):
            raw_value = _read_metric(source, key, trace)
            value = _clean_value(raw_value)

            z_row.append(value)
            text_row.append("" if value is None else "{:.2f}".format(value))
            hover_row.append(_hover_text_from_info(metric_info, key, value, raw_value))

            custom_row.append([
                key,
                metric_info[key]["label"],
                x_labels[index],
            ])

        z_values.append(z_row)
        text_values.append(text_row)
        hover_values.append(hover_row)
        custom_values.append(custom_row)

    fig = go.Figure(
        data=go.Heatmap(
            z=z_values,
            x=x_labels,
            y=y_values,
            text=hover_values,
            customdata=custom_values,
            hoverinfo="none",
            zmin=0,
            zmax=100,
            colorscale=_seaborn_rdylgn_center75_colorscale(),
            colorbar=dict(title="Percentage(%)"),
            xgap=1,
            ygap=1,
        )
    )

    desktop_domain_left = 0.52 if len(trace_list) > 1 else 0.45

    fig.update_layout(
        title=dict(
            text=title,
            x=0.02,
            xanchor="left",
        ),
        autosize=True,
        height=max(520, 42 * len(metric_keys)),
        margin=dict(l=40, r=80, t=80, b=40),
        clickmode="event",
    )

    fig.update_yaxes(
        autorange="reversed",
        title="",
        tickvals=y_values,
        ticktext=[""] * len(y_values),
        showticklabels=False,
    )

    fig.update_xaxes(
        side="top",
        title="",
        domain=[desktop_domain_left, 0.86],
    )

    # Left-side metric labels with family and hierarchy styling
    for i, key in enumerate(metric_keys):
        raw_label = metric_info[key]["label"]
        clean_label = _clean_metric_label(raw_label)

        family_style = _metric_family_style(key, raw_label)
        level = _metric_level(raw_label)

        if level == "main":
            display_label = "<b>{}</b>".format(clean_label)
            x_position = 0.02
            font_size = 13
        elif level == "child":
            display_label = "↳ {}".format(clean_label)
            x_position = 0.045
            font_size = 12
        else:
            display_label = "↳ {}".format(clean_label)
            x_position = 0.075
            font_size = 12

        fig.add_annotation(
            xref="paper",
            x=x_position,
            yref="y",
            y=i,
            text=display_label,
            showarrow=False,
            xanchor="left",
            yanchor="middle",
            align="left",
            font=dict(
                size=font_size,
                color="#20344d",
            ),
            bgcolor=family_style["background"],
            bordercolor=family_style["border"],
            borderwidth=1,
            borderpad=5,
            opacity=1.0,
        )

    # Cell values
    for i, row in enumerate(text_values):
        for j, text in enumerate(row):
            if text == "":
                continue

            value = z_values[i][j]

            fig.add_annotation(
                x=x_labels[j],
                y=y_values[i],
                text=text,
                showarrow=False,
                xanchor="center",
                yanchor="middle",
                font=dict(
                    size=13,
                    color=_cell_text_color(value),
                ),
            )

    plot_div_id = title.lower().replace(" ", "-").replace(":", "").replace("/", "-")

    click_script = """
    <script>
    document.getElementById("{plot_div_id}").on('plotly_click', function(data) {{
        var point = data.points[0];
        var metricKey = point.customdata[0];
        var metricLabel = point.customdata[1];
        var traceLabel = point.customdata[2];
        var value = point.z;

        selectMetricCell("{section_id}", metricKey, metricLabel, traceLabel, value);
    }});
    </script>
    """.format(
        plot_div_id=plot_div_id,
        section_id=section_id,
    )

    return fig.to_html(
        full_html=False,
        include_plotlyjs=False,
        div_id=plot_div_id,
        config={"responsive": True},
    ) + click_script


def _has_mode(trace_mode, trace_list, token):
    for trace in trace_list:
        if token in trace_mode[trace]:
            return True
    return False


def _report_execution_model(trace_mode, trace_list, metrics_result):
    is_hybrid = metrics_result.get("kind") == "hybrid"
    has_mpi = _has_mode(trace_mode, trace_list, "MPI")
    has_omp = _has_mode(trace_mode, trace_list, "OpenMP")
    has_cuda = _has_mode(trace_mode, trace_list, "CUDA")

    return {
        "is_hybrid": is_hybrid,
        "has_mpi": has_mpi,
        "has_omp": has_omp,
        "has_cuda": has_cuda,
    }


def _build_report_tabs(model):
    tabs = [
        ("overview", "Overview"),
        ("global", "Global metrics"),
    ]

    if model["is_hybrid"]:
        tabs.append(("hybrid", "Hybrid metrics"))

        if model["has_cuda"]:
            tabs.append(("talp", "Host/Device"))

        if model["has_omp"]:
            tabs.append(("openmp", "OpenMP"))

    else:
        if model["has_omp"]:
            tabs.append(("openmp", "OpenMP"))
        else:
            tabs.append(("simple", "Simple metrics"))

    return tabs

def _metric_family(metric_key, label=""):
    label_lower = label.lower()
    key = metric_key.lower()

    if "cuda" in label_lower:
        return "cuda"

    if "openmp" in label_lower:
        return "openmp"

    if key == "dev_offload_eff":
        return "host"

    if "mpi " in label_lower or key.startswith("mpi_"):
        return "mpi"

    if "host " in label_lower or key.startswith("host_"):
        return "host"

    if "device " in label_lower or key.startswith("dev_"):
        return "device"

    return "global"

def _metric_family_style(metric_key, label):
    """Return Plotly annotation styling for a metric family."""
    family = _metric_family(metric_key, label)

    styles = {
        "global": {
            "background": "#eef2f7",
            "border": "#66788a",
        },
        "mpi": {
            "background": "#eaf3ff",
            "border": "#4f86c6",
        },
        "openmp": {
            "background": "#ecf8ef",
            "border": "#4f9d69",
        },
        "cuda": {
            "background": "#fff1e7",
            "border": "#d9823b",
        },
        "host": {
            "background": "#f2edff",
            "border": "#8066bf",
        },
        "device": {
            "background": "#e9f7f5",
            "border": "#318c82",
        },
    }

    return styles.get(family, styles["global"])


def _metric_level(label):
    stripped = label.lstrip()
    indentation = len(label) - len(stripped)

    if indentation >= 6:
        return "grandchild"

    if indentation >= 2:
        return "child"

    return "main"


def _hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip("#")
    return tuple(
        int(hex_color[i:i + 2], 16)
        for i in (0, 2, 4)
    )


def _rgb_to_hex(rgb):
    return "#{:02x}{:02x}{:02x}".format(
        int(round(rgb[0])),
        int(round(rgb[1])),
        int(round(rgb[2])),
    )


def _interpolate_color(color_a, color_b, fraction):
    fraction = max(0.0, min(1.0, fraction))

    rgb_a = _hex_to_rgb(color_a)
    rgb_b = _hex_to_rgb(color_b)

    rgb = tuple(
        a + (b - a) * fraction
        for a, b in zip(rgb_a, rgb_b)
    )

    return _rgb_to_hex(rgb)


def _metric_value_class(value, thresholds=None):
    if thresholds is None:
        thresholds = _default_metric_thresholds()

    if value is None:
        return "metric-unavailable"

    if value > thresholds.reference:
        return "metric-above-reference"

    if value < thresholds.critical:
        return "metric-critical"

    if value < thresholds.attention:
        return "metric-warning"

    return "metric-good"


def _metric_value_html(value):
    if value is None:
        return (
            "<span class='metric-value metric-unavailable'>"
            "N/A"
            "</span>"
        )

    css_class = _metric_value_class(value)

    return (
        "<span class='metric-value {}'>{:.2f}%</span>"
    ).format(css_class, value)


def _metric_name_html(metric_key, metric_info, depth=0):
    info = metric_info.get(metric_key, {})
    raw_label = info.get("label", metric_key)

    family = _metric_family(metric_key, raw_label)
    clean_label = _clean_metric_label(raw_label)

    if depth == 0:
        display_label = "<strong>{}</strong>".format(
            html.escape(clean_label)
        )
    else:
        display_label = "↳ {}".format(
            html.escape(clean_label)
        )

    return (
        "<td class='metric-name-cell metric-family-{family}' "
        "style='--metric-depth: {depth};'>"
        "{label}"
        "</td>"
    ).format(
        family=family,
        depth=depth,
        label=display_label,
    )


def _build_metric_depth_map(tree):
    """Return metric hierarchy depth from a metric tree."""
    depth_map = {}

    def visit(node, depth):
        metric = node["metric"]
        depth_map[metric] = depth

        for child in node.get("children", []):
            visit(child, depth + 1)

    for root in tree:
        visit(root, 0)

    return depth_map


def _collect_metric_reference(
        reference_registry,
        metric_keys,
        metric_info,
        runtime=None,
        runtime_family=None):
    """
    Collect semantic metric information used by the printable
    Metric Reference appendix.

    Semantic information comes from definitions.yaml through the
    PerformanceKnowledgeProvider. metric_info is used only for the
    presentation label shown in the report.
    """

    for metric_key in metric_keys:
        info = metric_info.get(
            metric_key,
            {}
        )

        try:
            knowledge = KNOWLEDGE_PROVIDER.get(
                metric_key,
                runtime=runtime,
                runtime_family=runtime_family,
            )
        except (KeyError, ValueError):
            continue

        label = _clean_metric_label(
            info.get(
                "label",
                knowledge.name,
            )
        )

        normalized_label = " ".join(
            label.lower().split()
        )

        if normalized_label in reference_registry:
            continue

        reference_registry[
            normalized_label
        ] = {
            "label": label,

            # Temporary compatibility with current PDF renderer.
            "meaning": knowledge.definition,

            "definition": knowledge.definition,
            "formula": knowledge.formula.get(
                "text",
                "",
            ),
            "typical_causes": list(
                knowledge.typical_causes
            ),
        }


def _build_metric_reference_appendix_html(metric_reference):
    """Build the printable metric-reference appendix."""

    if not metric_reference:
        return ""

    lines = [
        '<section class="print-appendix print-page-section">',
        '<header class="print-section-header">',
        '<h2>Appendix A — Metric Reference</h2>',
        '<p class="print-section-description">',
        'Metrics are listed once, in the order in which they first appear '
        'in the report. Each entry summarizes the metric definition, '
        'formulation, and typical sources of performance inefficiency.',
        '</p>',
        '</header>',
        '<div class="metric-reference-list">',
    ]

    for item in metric_reference.values():

        lines.append(
            '<article class="metric-reference-card">'
        )

        lines.append(
            '<h3 class="metric-reference-name">{}</h3>'.format(
                html.escape(item["label"])
            )
        )

        # --------------------------------------------------
        # Definition
        # --------------------------------------------------

        lines.append(
            '<div class="metric-reference-field">'
            '<div class="metric-reference-label">'
            'Definition'
            '</div>'
            '<div class="metric-reference-value">{}</div>'
            '</div>'.format(
                html.escape(
                    item["definition"]
                )
            )
        )

        # --------------------------------------------------
        # Formula
        # --------------------------------------------------

        formula = item.get(
            "formula",
            "",
        )

        if formula:
            lines.append(
                '<div class="metric-reference-field">'
                '<div class="metric-reference-label">'
                'Formula'
                '</div>'
                '<div class="metric-reference-value '
                'metric-reference-formula">'
                '{}</div>'
                '</div>'.format(
                    html.escape(formula)
                )
            )

        # --------------------------------------------------
        # Typical causes
        # --------------------------------------------------

        typical_causes = item.get(
            "typical_causes",
            [],
        )

        if typical_causes:
            lines.append(
                '<div class="metric-reference-field">'
                '<div class="metric-reference-label">'
                'Typical performance issues'
                '</div>'
                '<ul class="metric-reference-causes">'
            )

            for cause in typical_causes:
                lines.append(
                    '<li>{}</li>'.format(
                        html.escape(cause)
                    )
                )

            lines.append(
                '</ul>'
                '</div>'
            )

        lines.append(
            '</article>'
        )

    lines.extend([
        '</div>',
        '</section>',
    ])

    return "\n".join(lines)

def _build_printable_execution_domains_section(
        host_metric_keys,
        device_metric_keys,
        host_sources,
        device_sources,
        trace_list,
        trace_labels,
        trace_column_description):
    """Build one combined Host + Device printable analysis."""

    all_metric_keys = (
        list(host_metric_keys)
        + list(device_metric_keys)
    )

    metric_knowledge = _build_metric_knowledge(
        metric_keys=all_metric_keys,
    )

    # --------------------------------------------------
    # Host table
    # --------------------------------------------------

    host_table_html = _build_efficiency_table_html(
        metric_keys=host_metric_keys,
        metric_info=TALP_METRIC_INFO,
        metric_sources=host_sources,
        trace_list=trace_list,
        trace_labels=trace_labels,
        section_id="print-execution-domains",
        tree=HOST_TREE,
        printable=True,
        metric_knowledge=metric_knowledge,
    )

    # --------------------------------------------------
    # Device table
    # --------------------------------------------------

    device_table_html = _build_efficiency_table_html(
        metric_keys=device_metric_keys,
        metric_info=TALP_METRIC_INFO,
        metric_sources=device_sources,
        trace_list=trace_list,
        trace_labels=trace_labels,
        section_id="print-execution-domains",
        tree=DEVICE_TREE,
        printable=True,
        metric_knowledge=metric_knowledge,
    )

    # --------------------------------------------------
    # Host diagnosis
    # --------------------------------------------------

    host_performance = (
        observations.build_performance_interpretation(
            tree=HOST_TREE,
            metric_info=TALP_METRIC_INFO,
            metric_sources=host_sources,
            trace_list=trace_list,
            metric_knowledge=metric_knowledge,
        )
    )

    host_performance_html = (
        observations.build_performance_interpretation_html(
            host_performance
        )
    )

    host_scaling = (
        observations.build_scaling_interpretation(
            tree=HOST_TREE,
            metric_info=TALP_METRIC_INFO,
            metric_sources=host_sources,
            trace_list=trace_list,
            metric_knowledge=metric_knowledge,
        )
    )

    host_scaling_html = (
        observations.build_scaling_interpretation_html(
            host_scaling
        )
    )

    # --------------------------------------------------
    # Device diagnosis
    # --------------------------------------------------

    device_performance = (
        observations.build_performance_interpretation(
            tree=DEVICE_TREE,
            metric_info=TALP_METRIC_INFO,
            metric_sources=device_sources,
            trace_list=trace_list,
            metric_knowledge=metric_knowledge,
        )
    )

    device_performance_html = (
        observations.build_performance_interpretation_html(
            device_performance
        )
    )

    device_scaling = (
        observations.build_scaling_interpretation(
            tree=DEVICE_TREE,
            metric_info=TALP_METRIC_INFO,
            metric_sources=device_sources,
            trace_list=trace_list,
            metric_knowledge=metric_knowledge,
        )
    )

    device_scaling_html = (
        observations.build_scaling_interpretation_html(
            device_scaling
        )
    )

    return """
    <section
        class="print-metric-section
               print-page-section
               print-execution-domains"
    >
        <header class="print-section-header">

            <h2>5 Execution Domains</h2>

            <p class="print-section-description">
                Complementary Host and Device evidence used to identify
                where accelerator-related inefficiencies manifest.
            </p>
        </header>

        <div class="print-execution-domain-label">
            HOST
        </div>

        <p class="trace-header-note">
            <b>Trace columns:</b>
            <code>{trace_column_description}</code>
        </p>

        <div class="print-metric-results metric-table-card">
            {host_table_html}
        </div>

        <div class="print-execution-domain-label">
            DEVICE
        </div>

        <div class="print-metric-results metric-table-card">
            {device_table_html}
        </div>

        <div class="print-analysis-summary">
            <div class="execution-domain-analysis-group">
                <h3>HOST</h3>
                {host_performance_html}
                {host_scaling_html}
            </div>

            <div class="execution-domain-analysis-group">
                <h3>DEVICE</h3>
                {device_performance_html}
                {device_scaling_html}
            </div>
        </div>
    </section>
    """.format(
        host_table_html=host_table_html,
        device_table_html=device_table_html,
        trace_column_description=html.escape(
            trace_column_description
        ),
        host_performance_html=host_performance_html,
        host_scaling_html=host_scaling_html,
        device_performance_html=device_performance_html,
        device_scaling_html=device_scaling_html,
    )

def _build_printable_metric_section(
        metric_keys,
        metric_info,
        metric_sources,
        trace_list,
        trace_labels,
        title,
        tree,
        trace_header_note="",
        trace_column_description="",
        scope_note_html="",
        section_kicker="Performance analysis",
        section_description=""):
    """Build one analytical section for the printable report.

    Metric definitions are intentionally excluded.  They are collected by the
    caller and rendered once in Appendix A.
    """

    # Keep Serialization and Transfer exclusively in runtime-model sections.
    if tree in (GLOBAL_TREE, GLOBAL_GPU_TREE):
        excluded_runtime_metrics = {"serial_eff", "transfer_eff"}
        metric_keys = [
            key for key in metric_keys
            if key not in excluded_runtime_metrics
        ]
        metric_sources = {
            key: source for key, source in metric_sources.items()
            if key not in excluded_runtime_metrics
        }

    efficiency_table_html = _build_efficiency_table_html(
        metric_keys=metric_keys,
        metric_info=metric_info,
        metric_sources=metric_sources,
        trace_list=trace_list,
        trace_labels=trace_labels,
        section_id="print",
        tree=tree,
        printable=True,
    )

    performance_interpretation = (
        observations.build_performance_interpretation(
            tree=tree,
            metric_info=metric_info,
            metric_sources=metric_sources,
            trace_list=trace_list,
            #metric_knowledge=metric_knowledge,
        )
    )

    performance_html = observations.build_performance_interpretation_html(
        performance_interpretation
    )

    scaling_interpretation = observations.build_scaling_interpretation(
        tree=tree,
        metric_info=metric_info,
        metric_sources=metric_sources,
        trace_list=trace_list,
        #metric_knowledge=metric_knowledge,
    )

    scaling_html = observations.build_scaling_interpretation_html(
        scaling_interpretation
    )

    analysis_html = observations.build_analysis_summary_html(
        performance_html=performance_html,
        scaling_html=scaling_html,
        title="Automatic diagnosis",
    )

    description_html = ""
    if section_description:
        description_html = (
            '<p class="print-section-description">{}</p>'.format(
                html.escape(section_description)
            )
        )

    return """
    <section class="print-metric-section print-page-section">
        <header class="print-section-header">
            <h2>{title}</h2>
            {description_html}
        </header>

        {scope_note_html}

        <p class="trace-header-note">
            <b>Trace columns:</b>
            <code>{trace_column_description}</code>
        </p>

        <div class="print-metric-results metric-table-card">
            {efficiency_table_html}
        </div>
        
        <div class="print-analysis-summary">
            {analysis_html}
        </div>
    </section>
    """.format(
        section_kicker=html.escape(section_kicker),
        title=html.escape(title),
        description_html=description_html,
        trace_header_note=trace_header_note,
        trace_column_description=html.escape(
            trace_column_description
        ),
        scope_note_html=scope_note_html,
        efficiency_table_html=efficiency_table_html,
        analysis_html=analysis_html,
    )


def _build_efficiency_table_html( metric_keys, metric_info, metric_sources,
                                trace_list, trace_labels, section_id,
                                tree=None, printable=False,
                                metric_knowledge=None):

    """Build an interactive HTML efficiency metrics table."""

    depth_map = _build_metric_depth_map(tree or [])
    headers = trace_labels

    lines = []

    lines.append("<div class='efficiency-table-wrapper'>")
    lines.append("<table class='efficiency-table'>")

    # --------------------------------------------------
    # Header
    # --------------------------------------------------

    lines.append("<thead>")
    lines.append("<tr>")
    lines.append("<th class='metric-column-header'>Metric</th>")

    for header in headers:
        lines.append(
            "<th>{}</th>".format(html.escape(header))
        )

    lines.append("</tr>")
    lines.append("</thead>")

    # --------------------------------------------------
    # Body
    # --------------------------------------------------

    lines.append("<tbody>")

    for metric_key in metric_keys:
        info = metric_info.get(metric_key, {})
        raw_label = info.get("label", metric_key)
        clean_label = _clean_metric_label(raw_label)

        source = metric_sources.get(metric_key, {})

        # Resolve the thresholds for this metric.
        knowledge = (
            metric_knowledge.get(metric_key)
            if metric_knowledge
            else None
        )

        thresholds = (
            knowledge.thresholds
            if knowledge is not None
            else _default_metric_thresholds()
        )

        lines.append("<tr>")

        # Metric name
        depth = depth_map.get(metric_key, 0)

        lines.append(
            _metric_name_html(
                metric_key,
                metric_info,
                depth=depth,
            )
        )

        # Values per trace
        for index, trace in enumerate(trace_list):
            raw_value = _read_metric(
                source,
                metric_key,
                trace,
            )

            value = _clean_value(raw_value)
            trace_label = headers[index]

            if value is None:
                display_value = _format_unavailable_metric_value(raw_value)
                js_value = "null"
            else:
                display_value = "{:.2f}%".format(value)
                js_value = "{:.10f}".format(value)

            value_class = _metric_value_class(
                value,
                thresholds,
            )

            background_color = _metric_value_color(value)
            text_color = _cell_text_color(value)

            if printable:
                lines.append(
                    "<td class='metric-value-cell'>"
                    "<span "
                    "class='metric-value metric-value-print' "
                    "style='background:{background}; color:{text_color};'>"
                    "{display_value}"
                    "</span>"
                    "</td>".format(
                        background=background_color,
                        text_color=text_color,
                        display_value=display_value,
                    )
                )
            else:
                lines.append(
                    "<td class='metric-value-cell'>"
                    "<button "
                    "type='button' "
                    "class='metric-value {value_class}' "
                    "style='background:{background}; color:{text_color};' "
                    "onclick=\"selectMetricCell("
                    "this, "
                    "'{section_id}', "
                    "'{metric_key}', "
                    "'{metric_label}', "
                    "'{trace_label}', "
                    "{value}"
                    ")\">"
                    "{display_value}"
                    "</button>"
                    "</td>".format(
                        background=background_color,
                        text_color=text_color,
                        section_id=html.escape(section_id, quote=True),
                        metric_key=html.escape(metric_key, quote=True),
                        metric_label=html.escape(clean_label, quote=True),
                        trace_label=html.escape(trace_label, quote=True),
                        value=js_value,
                        value_class=value_class,
                        display_value=display_value,
                    )
                )

        lines.append("</tr>")

    lines.append("</tbody>")
    lines.append("</table>")
    lines.append("</div>")

    return "\n".join(lines)


def _build_openmp_runtime_scope_note(is_hybrid):
    """Explain the scope of the isolated OpenMP runtime metrics."""

    if is_hybrid:
        comparison_text = """
        <p>
            <strong>OpenMP Region Load Balance</strong> considers only useful
            computation performed inside OpenMP parallel regions. It is therefore
            not directly comparable with the application-level
            <strong>Load Balance</strong> shown in Global Metrics or with the
            derived OpenMP Load Balance contribution shown in the
            Parallel Runtime Model.
        </p>
        """
    else:
        comparison_text = """
        <p>
            <strong>OpenMP Region Load Balance</strong> considers only useful
            computation performed inside OpenMP parallel regions. It is therefore
            not directly comparable with the application-level
            <strong>Load Balance</strong> shown in Global Metrics, which describes
            the distribution of useful computation across the complete execution.
        </p>
        """

    return """
    <div class="analysis-scope-note analysis-scope-warning">
        <h3>Metric scope</h3>
        <p>
            The metrics in this analysis are computed directly from the
            OpenMP execution and quantify serial execution, workload imbalance
            inside parallel regions, and OpenMP scheduling and fork/join overhead.
        </p>
        {comparison_text}
    </div>
    """.format(
        comparison_text=comparison_text,
    )


def _build_execution_domains_view(
    host_html,
    device_html,
):
    """Build the combined Host and Device execution-domain view.

    Host and Device remain independent analytical domains, but they are
    presented together in the primary Execution Domains view because they
    provide complementary evidence for accelerator-oriented executions.

    This function does not compute or reinterpret any metric. It only
    composes the already-rendered Host and Device analyses.
    """

    if not host_html and not device_html:
        return ""

    sections = []

    if host_html:
        sections.append(
            """
            <section
                class="execution-domain-section execution-domain-host"
                aria-label="Host execution domain"
            >
                {host_html}
            </section>
            """.format(
                host_html=host_html,
            )
        )

    if device_html:
        sections.append(
            """
            <section
                class="execution-domain-section execution-domain-device"
                aria-label="Device execution domain"
            >
                {device_html}
            </section>
            """.format(
                device_html=device_html,
            )
        )

    focus_note = """
    <div class="analysis-scope-note execution-domains-focus">
        <h3>Analysis focus</h3>

        <p>
            The Execution Domains view identifies where accelerator-related
            inefficiencies manifest across host execution, the accelerator
            offload path, and device execution.
        </p>

        <p>
            These metrics complement the Parallel Runtime Model but represent
            a different analytical scope. Runtime-specific efficiency factors
            should therefore not be interpreted as direct equivalents of the
            Host or Device metrics shown here.
        </p>
    </div>
    """

    return """
    <div class="execution-domains-view">
        {sections}

        {focus_note}
    </div>
    """.format(
        sections="\n".join(sections),
        focus_note=focus_note,
    )



def _build_overview_view(trace_config_html, trace_header_note,
                         overview_html, resources_html, global_html):
    """Build the Overview view without changing its current presentation.

    This semantic wrapper is the first layout-refactoring step. It groups all
    application-level information in a single view while preserving the
    existing HTML structure and visual appearance.
    """
    return _build_application_summary_panel(
        trace_config_html=trace_config_html,
        trace_header_note=trace_header_note,
        overview_html=overview_html,
        resources_html=resources_html,
        global_html=global_html,
    )


def _build_parallel_runtime_model_views(model, mod_factors, trace_list, 
                                        trace_labels, trace_header_note,
                                        trace_column_description,
                                        hybrid_html, inner_model):
    """Build the semantic Parallel Runtime Model view definitions.

    The function only reorganizes the existing report-generation logic. It
    deliberately keeps the same identifiers, titles, metric trees, and HTML
    content so that Step 1 introduces no visual or behavioral changes.
    """
    runtime_model_views = []

    # Simple traces expose the general POP Parallel Efficiency subtree.
    # Hybrid traces expose the complete derived MPI+X multiplicative model.
    if not model["is_hybrid"]:
        simple_runtime_keys = [
            "parallel_eff",
            "load_balance",
            "comm_eff",
            "serial_eff",
            "transfer_eff",
        ]
        simple_runtime_filtered_keys = [
            key for key in simple_runtime_keys
            if key in mod_factors and any(
                _clean_value(_read_metric(mod_factors, key, trace)) is not None
                for trace in trace_list
            )
        ]
        simple_runtime_sources = {
            key: mod_factors for key in simple_runtime_filtered_keys
        }

        if model["has_mpi"]:
            runtime_label = "MPI"
        elif model["has_omp"]:
            runtime_label = "OpenMP"
        elif model["has_cuda"]:
            runtime_label = "CUDA"
        else:
            runtime_label = "Parallel runtime"

        simple_runtime_html = _build_metric_tree_heatmap_section(
            metric_keys=simple_runtime_filtered_keys,
            metric_info=SIMPLE_METRIC_INFO,
            metric_sources=simple_runtime_sources,
            trace_list=trace_list,
            trace_labels=trace_labels,
            title="{} Parallel Efficiency".format(runtime_label),
            section_id="runtime-model-simple-metrics",
            tree_kind="runtime_global",
            trace_header_note=trace_header_note,
            trace_column_description=trace_column_description,
        )

        runtime_model_views.append({
            "id": "runtime-model-simple",
            "label": runtime_label,
            "title": "{} Parallel Runtime Model".format(runtime_label),
            "html": simple_runtime_html,
        })
    else:
        runtime_model_views.append({
            "id": "runtime-model-hybrid",
            "label": "MPI + {}".format(inner_model),
            "title": "Parallel Runtime Model: MPI + {}".format(inner_model),
            "html": hybrid_html,
        })

    if runtime_model_views:
        parallel_runtime_model_html = runtime_model_views[0]["html"]
    else:
        parallel_runtime_model_html = (
            "<p>No Parallel Runtime Model is available.</p>"
        )

    return runtime_model_views


def _build_component_views(model, inner_model, mpi_html,
                           accelerator_html,
                           openmp_filtered_keys, openmp_html,
                           host_html, device_html):
    """Build the independent analysis views exposed by the navigator.

    Runtime components and execution domains are intentionally represented as
    two separate analysis groups.  Host and Device are therefore not rendered
    as children of the accelerator runtime component.
    """
    analysis_views = []

    if mpi_html:
        analysis_views.append({
            "id": "analysis-runtime-mpi",
            "label": "MPI",
            "description": "Runtime analysis",
            "title": "MPI Runtime-Specific Analysis",
            "group": "runtime",
            "html": mpi_html,
        })

    if model["has_omp"] and openmp_filtered_keys:
        analysis_views.append({
            "id": "analysis-runtime-openmp",
            "label": "OpenMP",
            "description": "Runtime analysis",
            "title": "OpenMP Runtime-Specific Analysis",
            "group": "runtime",
            "html": openmp_html,
        })

    if model["is_hybrid"] and model["has_cuda"] and accelerator_html:
        analysis_views.append({
            "id": "analysis-runtime-accelerator",
            "label": inner_model,
            "description": "Hybrid contribution",
            "title": "{} Runtime Contribution".format(inner_model),
            "group": "runtime",
            "html": accelerator_html,
        })

        analysis_views.extend([
            {
                "id": "analysis-domain-host",
                "label": "Host",
                "description": "CPU side",
                "title": "Host Execution Domain",
                "group": "domain",
                "html": host_html,
            },
            {
                "id": "analysis-domain-device",
                "label": "Device",
                "description": "Accelerator side",
                "title": "Device Execution Domain",
                "group": "domain",
                "html": device_html,
            },
        ])

    # Preserve selection of other hybrid runtimes even when an isolated model
    # is not yet available.
    if (
        model["is_hybrid"]
        and not model["has_omp"]
        and not model["has_cuda"]
        and inner_model
    ):
        analysis_views.append({
            "id": "analysis-runtime-inner",
            "label": inner_model,
            "description": "Analysis availability",
            "title": "{} Runtime Analysis".format(inner_model),
            "group": "runtime",
            "html": (
                "<div class='analysis-scope-note'>"
                "<h3>Analysis availability</h3>"
                "<p>The Parallel Runtime Model quantifies the {0} contribution, "
                "but an isolated {0} runtime-specific analysis is not currently "
                "available.</p></div>"
            ).format(html.escape(inner_model)),
        })

    return analysis_views


def _build_analysis_navigator_html(analysis_views):
    """Build grouped selectors for runtime and execution-domain analyses."""
    runtime_views = [
        view for view in analysis_views
        if view.get("group") == "runtime"
    ]
    domain_views = [
        view for view in analysis_views
        if view.get("group") == "domain"
    ]

    def build_group(title, description, views, aria_label):
        if not views:
            return ""

        buttons = []
        for view in views:
            buttons.append(
                '<button type="button" class="runtime-component-button analysis-nav-button" '
                'data-analysis-target="{target}" '
                'aria-pressed="false" '
                'onclick="selectAnalysisView(\'{target}\', this)">'
                '<span class="runtime-component-name">{label}</span>'
                '<span class="runtime-component-kind">{description}</span>'
                '</button>'.format(
                    target=html.escape(view["id"], quote=True),
                    label=html.escape(view["label"]),
                    description=html.escape(view.get("description", "Analysis")),
                )
            )

        return (
            '<section class="analysis-navigator-group" aria-label="{aria_label}">'
            '<div class="runtime-component-selector-header">'
            '<h3>{title}</h3><p>{description}</p>'
            '</div>'
            '<div class="runtime-component-list">{buttons}</div>'
            '</section>'
        ).format(
            aria_label=html.escape(aria_label, quote=True),
            title=html.escape(title),
            description=html.escape(description),
            buttons="".join(buttons),
        )

    groups = [
        build_group(
            "Select a runtime component",
            "Inspect the contribution or runtime-specific behavior of an active parallel runtime.",
            runtime_views,
            "Runtime components",
        ),
        build_group(
            "Select an execution domain",
            "Inspect whether the efficiency loss occurs on the host or during device execution.",
            domain_views,
            "Execution domains",
        ),
    ]

    groups = [group for group in groups if group]
    if not groups:
        return (
            '<div class="runtime-component-selector empty">'
            '<p>No selectable analyses are available.</p>'
            '</div>'
        )

    return (
        '<section class="runtime-component-selector analysis-navigator" '
        'aria-label="Performance analysis navigator">{}</section>'
    ).format("".join(groups))


def _build_sidebar_runtime_model_html(runtime_model_views, analysis_views):
    """Render the Parallel Runtime Model and the grouped analysis navigator."""
    if not runtime_model_views:
        return (
            '<section class="workspace-panel">'
            '<h2>Parallel Runtime Model</h2>'
            '<p>No parallel runtime model is available.</p>'
            '</section>'
        )

    selector_html = _build_analysis_navigator_html(analysis_views)
    model_html = "\n".join(
        _build_detail_view(view["id"], view["title"], view["html"])
        .replace('class="detail-view"', 'class="runtime-model-static-view"')
        for view in runtime_model_views
    )

    # Present the composed MPI+X model first.  Compact jump controls preserve
    # this diagnostic order while allowing direct navigation to the component
    # selectors and back to the composed model without repeated manual scrolling.
    return (
        '<div id="runtime-model-composed-start" class="runtime-model-composed-start">'
        '<button type="button" class="analysis-jump-link" '
        'onclick="scrollSidebarToElement(\'runtime-model-component-selectors\')">'
        '<span>Component-level diagnosis</span><span aria-hidden="true">↓</span>'
        '</button>'
        + model_html
        + '</div>'
        + '<div id="runtime-model-component-selectors" '
          'class="analysis-drilldown-separator">'
          '<span>Continue with component-level diagnosis</span>'
          '<button type="button" class="analysis-jump-link analysis-jump-link-back" '
          'onclick="scrollSidebarToElement(\'runtime-model-composed-start\')">'
          '<span aria-hidden="true">↑</span><span>Back to composed runtime model</span>'
          '</button>'
          '</div>'
        + selector_html
    )


def _build_component_panel_html(analysis_views):
    """Pre-render all selectable analyses for the right panel."""
    panels = []
    for view in analysis_views:
        panels.append(
            '<section id="{id}" class="component-analysis-view" hidden '
            'aria-label="{title}">'
            '<div class="workspace-panel component-analysis-workspace">'
            '<div class="component-analysis-header">'
            '<p class="component-analysis-eyebrow">Performance analysis</p>'
            '<h1>{title}</h1>'
            '</div>'
            '{content}'
            '</div>'
            '</section>'.format(
                id=html.escape(view["id"], quote=True),
                title=html.escape(view["title"]),
                content=view.get("html", ""),
            )
        )

    return "\n".join(panels)


def _build_step4_workspace(overview_view_html, runtime_model_views,
                           analysis_views):
    """Build the Step 4 context/detail workspace with hide and maximize controls."""
    runtime_model_html = _build_sidebar_runtime_model_html(
        runtime_model_views,
        analysis_views,
    )
    component_panels_html = _build_component_panel_html(analysis_views)

    return """
    <div class="workspace-shell">
        <div class="analysis-layout">
        <aside class="analysis-sidebar" aria-label="Report navigation">
            <div class="sidebar-header">
                <div class="sidebar-header-row">
                    <span class="sidebar-title">Global Performance Overview</span>
                    <div class="sidebar-header-actions">
                        <button
                            type="button"
                            id="sidebar-maximize-button"
                            class="sidebar-control-button sidebar-maximize-button"
                            aria-label="Maximize global performance overview"
                            aria-pressed="false"
                            title="Maximize global performance overview"
                            onclick="toggleContextMaximized()">
                            <span class="sidebar-maximize-icon" aria-hidden="true">⛶</span>
                        </button>
                        <button
                            type="button"
                            id="sidebar-collapse-button"
                            class="sidebar-control-button sidebar-collapse-button"
                            aria-label="Hide global performance overview"
                            aria-expanded="true"
                            title="Hide global performance overview"
                            onclick="toggleAnalysisSidebar()">
                            <span class="sidebar-collapse-icon" aria-hidden="true">‹</span>
                        </button>
                    </div>
                </div>
                <div class="sidebar-tabs" role="tablist" aria-label="Primary report views">
                    <button
                        type="button"
                        id="overview-sidebar-tab"
                        class="sidebar-tab active"
                        role="tab"
                        aria-selected="true"
                        aria-controls="overview-sidebar-view"
                        onclick="showSidebarView('overview-sidebar-view', this)">
                        <span class="sidebar-tab-label">Overview</span>
                    </button>
                    <button
                        type="button"
                        id="runtime-model-sidebar-tab"
                        class="sidebar-tab"
                        role="tab"
                        aria-selected="false"
                        aria-controls="runtime-model-sidebar-view"
                        onclick="showSidebarView('runtime-model-sidebar-view', this)">
                        <span class="sidebar-tab-label">Parallel Runtime Model</span>
                    </button>
                </div>
            </div>

            <div class="sidebar-view-container">
                <section
                    id="overview-sidebar-view"
                    class="sidebar-view active"
                    role="tabpanel"
                    aria-labelledby="overview-sidebar-tab"
                    aria-label="Overview">
                    {overview_view_html}
                </section>

                <section
                    id="runtime-model-sidebar-view"
                    class="sidebar-view"
                    role="tabpanel"
                    aria-labelledby="runtime-model-sidebar-tab"
                    aria-label="Parallel Runtime Model">
                    {runtime_model_html}
                </section>
            </div>
        </aside>

        <main class="component-panel" aria-label="Performance analysis">
            <div id="component-placeholder" class="workspace-panel component-placeholder">
                <div class="component-placeholder-icon" aria-hidden="true">◎</div>
                <p class="component-placeholder-eyebrow">Performance analysis</p>
                <h2>Select an analysis view</h2>
                <p>
                    Open the Parallel Runtime Model tab and choose either a runtime
                    component or an execution domain.
                </p>
            </div>
            {component_panels_html}
        </main>
        </div>
    </div>
    """.format(
        overview_view_html=overview_view_html,
        runtime_model_html=runtime_model_html,
        component_panels_html=component_panels_html,
    )

def _assemble_interactive_report(overview_view_html, runtime_model_views,
                                 analysis_views):
    """Assemble the Step 4 report with persistent context-panel sizing."""
    workspace_html = _build_step4_workspace(
        overview_view_html=overview_view_html,
        runtime_model_views=runtime_model_views,
        analysis_views=analysis_views,
    )

    return _build_interactive_report_document(
        workspace_html=workspace_html, printable_report_html=printable_report_body,
    )


def _build_application_summary_panel(trace_config_html, trace_header_note,
                                     overview_html, resources_html,
                                     global_html):
    """Build the persistent application-analysis pane."""
    return """
    <section class="application-panel" aria-label="Application analysis">
        <div class="workspace-panel">
            <h2>Overview</h2>

            <section class="report-section">
                <h3>Trace configuration</h3>
                {trace_config_html}
            </section>

            <section class="report-section">
                <h3>General metrics</h3>
                {trace_header_note}
                {overview_html}
            </section>

        </div>

        <div class="workspace-panel">
            <h2>Global Metrics</h2>
            {global_html}
        </div>

        <div class="workspace-panel validation-panel">
            <h2>Validate the analysis in Paraver</h2>
            <p class="section-description">
                Use the recommended view to inspect the execution and validate
                the findings identified by BasicAnalysis.
            </p>
            {resources_html}
        </div>
    </section>
    """.format(
        trace_config_html=trace_config_html,
        trace_header_note=trace_header_note,
        overview_html=overview_html,
        resources_html=resources_html,
        global_html=global_html,
    )


def _build_detail_navigation(runtime_model_views,
                             runtime_analysis_views,
                             domain_views):
    """Build selectors for the analysis families that are available."""
    groups = []

    def add_group(group_label, views, button_class):
        if not views:
            return

        buttons = []
        for view in views:
            buttons.append(
                '<button id="{id}-button" '
                'class="detail-tab-button {button_class}" '
                'data-target="{id}" '
                'onclick="showDetailView(&quot;{id}&quot;, this)">'
                '{label}</button>'.format(
                    id=html.escape(view["id"], quote=True),
                    button_class=html.escape(button_class, quote=True),
                    label=html.escape(view["label"]),
                )
            )

        groups.append(
            '<div class="detail-nav-group">'
            '<span class="detail-nav-label">{group_label}</span>'
            '<div class="detail-tab-list">{buttons}</div>'
            '</div>'.format(
                group_label=html.escape(group_label),
                buttons="".join(buttons),
            )
        )

    add_group(
        "Parallel Runtime Model",
        runtime_model_views,
        "runtime-model-tab",
    )
    add_group(
        "Runtime-Specific Analysis",
        runtime_analysis_views,
        "runtime-analysis-tab",
    )
    add_group(
        "Execution Domain",
        domain_views,
        "domain-tab",
    )

    return (
        '<nav class="detail-navigation" '
        'aria-label="Detailed analysis selector">{}</nav>'
    ).format("".join(groups))


def _build_detail_view(view_id, title, content_html):
    """Build one selectable detailed-analysis view."""
    return """
    <section id="{view_id}" class="detail-view">
        <h2>{title}</h2>
        {content_html}
    </section>
    """.format(
        view_id=html.escape(view_id, quote=True),
        title=html.escape(title),
        content_html=content_html,
    )


def _build_detail_panel(runtime_model_views,
                        runtime_analysis_views,
                        domain_views):
    """Build the selectable analysis pane from explicit semantic views."""
    all_views = (
        list(runtime_model_views)
        + list(runtime_analysis_views)
        + list(domain_views)
    )

    if all_views:
        views_html = "\n".join(
            _build_detail_view(view["id"], view["title"], view["html"])
            for view in all_views
        )
    else:
        views_html = _build_detail_view(
            "analysis-unavailable",
            "Detailed Analysis",
            "<p>No additional analysis models are available.</p>",
        )

    return """
    <section class="detail-panel" aria-label="Detailed performance analysis">
        <div class="workspace-panel detail-workspace">
            {navigation_html}
            <div class="detail-view-container">
                {views_html}
            </div>
        </div>
    </section>
    """.format(
        navigation_html=_build_detail_navigation(
            runtime_model_views,
            runtime_analysis_views,
            domain_views,
        ),
        views_html=views_html,
    )


def _build_workspace_layout(application_html, detail_html):
    """Arrange the persistent application pane and selectable detail pane."""
    return """
    <div class="report-workspace">
        {application_html}
        {detail_html}
    </div>
    """.format(
        application_html=application_html,
        detail_html=detail_html,
    )


def _build_primary_report_navigation(
    overview_html,
    performance_assessment_html,
):
    """Build the top-level Overview and Performance Assessment views."""

    return """
    <div class="primary-report-navigation">
        <div
            class="primary-report-tabs"
            role="tablist"
            aria-label="Report analysis stages"
        >
            <button
                type="button"
                id="primary-overview-tab"
                class="primary-report-tab active"
                role="tab"
                aria-selected="true"
                aria-controls="primary-overview-view"
                onclick="showPrimaryReportView(
                    'primary-overview-view',
                    this
                )"
            >
                Overview
            </button>

            <button
                type="button"
                id="primary-assessment-tab"
                class="primary-report-tab"
                role="tab"
                aria-selected="false"
                aria-controls="primary-assessment-view"
                onclick="showPrimaryReportView(
                    'primary-assessment-view',
                    this
                )"
            >
                Performance Assessment
            </button>
        </div>

        <section
            id="primary-overview-view"
            class="primary-report-view active"
            role="tabpanel"
            aria-labelledby="primary-overview-tab"
        >
            {overview_html}
        </section>

        <section
            id="primary-assessment-view"
            class="primary-report-view"
            role="tabpanel"
            aria-labelledby="primary-assessment-tab"
            hidden
        >
            {performance_assessment_html}
        </section>
    </div>
    """.format(
        overview_html=overview_html,
        performance_assessment_html=performance_assessment_html,
    )


def _build_interactive_report_document(workspace_html,
        printable_report_html=""):
    """Build the complete interactive HTML document."""
    document = """
        <!DOCTYPE html>
        <html>
        <head>
        <meta charset="utf-8">
        <meta
            name="viewport"
            content="width=device-width, initial-scale=1.0, minimum-scale=0.5, maximum-scale=5.0, user-scalable=yes"
        >
        <title>BasicAnalysis Interactive Report</title>
        <script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
        <script src="https://cdn.jsdelivr.net/npm/html2canvas@1.4.1/dist/html2canvas.min.js"></script>        
        <script src="https://cdn.jsdelivr.net/npm/jszip@3.10.1/dist/jszip.min.js"></script>
        <style>
        .metric-tree-children {
            margin-left: 14px;
        }

        .metric-tree-summary {
            cursor: pointer;
            font-weight: bold;
            padding: 6px 8px;
            background: #f4f4f4;
        }

        .metric-tree-summary:hover {
            background: #eef4ff;
        }

        .metric-info-panel {
            border: 1px solid #ccc;
            background: #f8f8f8;
            padding: 14px 18px;
            margin-bottom: 18px;
            max-width: 1100px;
        }

        .metric-info-panel h3 {
            margin-top: 0;
            margin-bottom: 6px;
        }

        .metric-info-type {
            font-weight: bold;
            color: #555;
        }

        .metric-layout {
            display: grid;
            grid-template-columns: 260px minmax(500px, 1fr);
            gap: 20px;
            align-items: start;
        }

        .metric-tree {
            border: 1px solid #ddd;
            background: #fafafa;
            padding: 12px;
            font-size: 14px;
        }

        .metric-tree details {
            margin-bottom: 8px;
        }

        .metric-tree summary {
            cursor: pointer;
            font-weight: bold;
            margin-bottom: 6px;
            height: 39px;
        line-height: 39px;
        }

        .metric-tree-button {
            display: block;
            width: 100%;
            text-align: left;
            border: none;
            background: white;
            border-left: 3px solid transparent;
            cursor: pointer;
            color: #123;
            height: 39px;
            line-height: 27px;
            padding: 6px 8px;
            margin: 0;
        }

        .metric-tree-button:hover {
            background: #eef4ff;
        }

        .metric-tree-button.active {
            border-left-color: #123;
            background: #e6eef8;
            font-weight: bold;
        }

        .metric-heatmap {
            min-width: 0;
        }

        .metric-table {
            border-collapse: collapse;
            margin-top: 16px;
            font-size: 14px;
        }

        .metric-table th,
        .metric-table td {
            border: 1px solid #ccc;
            padding: 8px 12px;
            text-align: right;
        }

        .metric-table th:first-child,
        .metric-table td:first-child {
            text-align: left;
            font-weight: bold;
        }

        .metric-table thead {
            background: #f2f2f2;
        }

        body {
            font-family: Arial, sans-serif;
            margin: 24px;
            color: #123;
        }

        h1 {
            margin-bottom: 4px;
        }

        .subtitle {
            color: #555;
            margin-bottom: 24px;
        }

        .tab-bar {
            display: flex;
            gap: 8px;
            border-bottom: 1px solid #ccc;
            margin-bottom: 20px;
        }

        .tab-button {
            padding: 10px 14px;
            border: 1px solid #ccc;
            border-bottom: none;
            background: #f5f5f5;
            cursor: pointer;
            font-size: 14px;
        }

        .tab-button.active {
            background: white;
            font-weight: bold;
        }

        .tab-content {
            display: none;
        }

        .tab-content.active {
            display: block;
        }

        .copy-btn {
            padding: 6px 10px;
            border: 1px solid #999;
            background: #f5f5f5;
            cursor: pointer;
            border-radius: 4px;
        }

        .copy-btn:hover {
            background: #e8eef8;
        }

        .observation-box {
            border: 1px solid #c8d6e5;
            background: #f4f8fc;
            padding: 14px 18px;
            margin-bottom: 18px;
            max-width: 1100px;
        }

        .observation-box h3 {
            margin-top: 0;
        }

        .observation-box ul {
            margin-bottom: 8px;
        }

        .tree-diagnosis {
            line-height: 1.5;
            font-size: 14px;
        }

        .tree-diagnosis div {
            margin-bottom: 3px;
        }


        :root {
            --background: #f4f7fb;
            --surface: #ffffff;
            --surface-soft: #f8fafc;

            --primary: #17365d;
            --primary-light: #e8f0fa;
            --primary-hover: #244d7e;

            --text: #172033;
            --text-secondary: #5c677a;
            --border: #dce3ec;

            --info-bg: #eef6ff;
            --info-border: #8bb8e8;

            --summary-bg: #f4f8ff;
            --summary-border: #b7cbe3;

            --shadow-sm: 0 2px 8px rgba(20, 38, 63, 0.06);
            --shadow-md: 0 8px 24px rgba(20, 38, 63, 0.09);

            --radius-sm: 8px;
            --radius-md: 12px;
            --radius-lg: 16px;
        }

        /* -------------------------------------------------- */
        /* Page                                                */
        /* -------------------------------------------------- */

        * {
            box-sizing: border-box;
        }

        html,
        body {
            height: 100%;
        }

        body {
            display: flex;
            flex-direction: column;
            margin: 0;
            overflow: hidden;
            background: var(--background);
            color: var(--text);
            font-family:
                Inter,
                -apple-system,
                BlinkMacSystemFont,
                "Segoe UI",
                Roboto,
                Helvetica,
                Arial,
                sans-serif;
            line-height: 1.55;
        }

        .report-header {
            position: relative;
            z-index: 1000;
            flex: 0 0 auto;
            background: linear-gradient(135deg, #122a49 0%, #1e4b78 100%);
            color: white;
            padding: 30px 24px;
            box-shadow: none;
            transition: box-shadow 0.18s ease;
        }

        .report-header.is-scrolled {
            box-shadow: var(--shadow-md);
        }

        .report-header-content {
            max-width: 1440px;
            margin: 0 auto;
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 24px;
        }

        .report-brand {
            margin-bottom: 4px;
            color: #a9c9ea;
            font-size: 13px;
            font-weight: 700;
            letter-spacing: 0.12em;
            text-transform: uppercase;
        }

        .report-header h1 {
            margin: 0;
            color: white;
            font-size: 30px;
            line-height: 1.2;
        }

        .subtitle {
            margin: 8px 0 0;
            color: #d8e7f5;
            font-size: 15px;
        }

        .report-badge {
            flex: 0 0 auto;
            padding: 8px 13px;
            border: 1px solid rgba(255, 255, 255, 0.35);
            border-radius: 999px;
            background: rgba(255, 255, 255, 0.10);
            font-size: 13px;
            font-weight: 600;
            white-space: nowrap;
        }

        .report-container {
            width: min(1440px, calc(100% - 40px));
            margin: 28px auto 48px;
        }

        h2 {
            margin: 0 0 22px;
            color: var(--primary);
            font-size: 25px;
        }

        h3 {
            margin-top: 28px;
            margin-bottom: 12px;
            color: #243b58;
            font-size: 18px;
        }

        /* -------------------------------------------------- */
        /* Navigation                                          */
        /* -------------------------------------------------- */

        .tab-bar {
            position: sticky;
            top: 0;
            z-index: 20;

            display: flex;
            flex-wrap: wrap;
            gap: 7px;

            margin-bottom: 24px;
            padding: 8px;

            border: 1px solid var(--border);
            border-radius: var(--radius-md);
            background: rgba(255, 255, 255, 0.96);
            box-shadow: var(--shadow-sm);
            backdrop-filter: blur(8px);
        }

        .tab-button {
            padding: 10px 16px;
            border: 0;
            border-radius: var(--radius-sm);
            background: transparent;
            color: var(--text-secondary);

            cursor: pointer;
            font-size: 14px;
            font-weight: 600;

            transition:
                background 0.18s ease,
                color 0.18s ease,
                transform 0.18s ease;
        }

        .tab-button:hover {
            background: var(--primary-light);
            color: var(--primary);
        }

        .tab-button.active {
            background: var(--primary);
            color: white;
            box-shadow: 0 3px 10px rgba(23, 54, 93, 0.22);
        }

        .tab-content {
            display: none;
            padding: 26px;

            border: 1px solid var(--border);
            border-radius: var(--radius-lg);
            background: var(--surface);
            box-shadow: var(--shadow-sm);
        }

        .tab-content.active {
            display: block;
        }

        /* -------------------------------------------------- */
        /* Tables                                              */
        /* -------------------------------------------------- */

        .metric-table {
            width: 100%;
            margin-top: 12px;
            overflow: hidden;

            border-collapse: separate;
            border-spacing: 0;

            border: 1px solid var(--border);
            border-radius: var(--radius-md);
            background: white;

            font-size: 14px;
        }

        .metric-table th,
        .metric-table td {
            padding: 11px 14px;
            border: 0;
            border-bottom: 1px solid var(--border);
            text-align: right;
        }

        .metric-table th {
            background: #edf3f9;
            color: #29435f;
            font-size: 13px;
            font-weight: 700;
        }

        .metric-table td:first-child,
        .metric-table th:first-child {
            text-align: left;
        }

        .metric-table tbody tr:last-child td {
            border-bottom: 0;
        }

        .metric-table tbody tr:hover td {
            background: #f8fbff;
        }

        .metric-table td[colspan] {
            background: #f0f4f8 !important;
            color: var(--primary);
            font-weight: 700 !important;
            letter-spacing: 0.01em;
        }

        /* -------------------------------------------------- */
        /* Analysis summary                                    */
        /* -------------------------------------------------- */

        .observation-box {
            max-width: none;
            margin-bottom: 22px;
            padding: 20px 22px;

            border: 1px solid var(--summary-border);
            border-left: 5px solid #4c83bd;
            border-radius: var(--radius-md);
            background: linear-gradient(135deg, #f7faff 0%, #eef5fc 100%);
            box-shadow: var(--shadow-sm);
        }

        .observation-box h3 {
            margin: 0 0 14px;
            color: var(--primary);
            font-size: 18px;
        }

        .observation-box p {
            margin: 10px 0;
        }

        .observation-box ul {
            margin: 8px 0 0;
            padding-left: 22px;
        }

        .observation-box li {
            margin-bottom: 7px;
        }

        .tree-diagnosis {
            padding: 12px 14px;
            border-radius: var(--radius-sm);
            background: rgba(255, 255, 255, 0.75);
            font-size: 14px;
            line-height: 1.7;
        }

        .tree-diagnosis div {
            margin-bottom: 4px;
        }

        /* -------------------------------------------------- */
        /* Metric details                                      */
        /* -------------------------------------------------- */

        .metric-info-panel {
            position: relative;
            max-width: none;
            min-height: 145px;
            margin-bottom: 22px;
            padding: 20px 22px;

            border: 1px solid var(--info-border);
            border-left: 5px solid #2374b8;
            border-radius: var(--radius-md);
            background: var(--info-bg);
            box-shadow: var(--shadow-sm);
        }

        .metric-info-panel::before {
            content: "Metric details";
            display: block;
            margin-bottom: 8px;

            color: #527397;
            font-size: 12px;
            font-weight: 700;
            letter-spacing: 0.08em;
            text-transform: uppercase;
        }

        .metric-info-panel h3 {
            margin: 0 0 8px;
            color: var(--primary);
            font-size: 19px;
        }

        .metric-info-panel p {
            margin: 7px 0;
            color: #31465d;
            font-size: 14px;
            line-height: 1.7;
        }        

        .metric-info-type {
            display: inline-block;
            padding: 4px 9px;

            border-radius: 999px;
            background: #dcecff;
            color: #245a8d;

            font-size: 12px;
            font-weight: 700;
        }


        /* -------------------------------------------------- */
        /* Metric details modal                                */
        /* -------------------------------------------------- */

        body.metric-details-open {
            overflow: hidden !important;
        }

        html:has(body.metric-details-open) {
            overflow: hidden !important;
        }

        .metric-details-modal {
            position: fixed;
            inset: 0;
            z-index: 3000;

            display: grid;
            place-items: center;

            padding: 24px;
        }

        .metric-details-modal[hidden] {
            display: none;
        }

        .metric-details-backdrop {
            position: absolute;
            inset: 0;

            background: rgba(12, 25, 42, 0.50);
            backdrop-filter: blur(2px);
        }

        .metric-details-dialog {
            position: relative;
            z-index: 1;

            width: min(620px, calc(100vw - 32px));
            max-height: min(720px, calc(100vh - 48px));
            overflow-y: auto;

            padding: 22px 24px;

            border: 1px solid var(--border);
            border-radius: var(--radius-lg);

            background: var(--surface);
            box-shadow: 0 18px 50px rgba(20, 38, 63, 0.28);
        }

        .metric-details-close {
            position: absolute;
            top: 12px;
            right: 12px;

            display: grid;
            width: 34px;
            height: 34px;

            place-items: center;

            border: 1px solid #aabed2;
            border-radius: 8px;

            background: #fff;
            color: var(--primary);

            cursor: pointer;
            font: inherit;
            font-size: 22px;
            line-height: 1;
        }

        .metric-details-close:hover {
            border-color: var(--primary);
            background: var(--primary-light);
        }

        .metric-details-eyebrow {
            margin-bottom: 4px;

            color: #527397;
            font-size: 10px;
            font-weight: 750;
            letter-spacing: .08em;
            text-transform: uppercase;
        }

        .metric-details-dialog h2 {
            margin: 0 44px 10px 0;
            font-size: 21px;
        }

        .metric-details-context {
            display: flex;
            flex-wrap: wrap;
            gap: 7px;

            margin-bottom: 18px;
        }

        .metric-details-context span {
            padding: 4px 9px;

            border-radius: 999px;
            background: #eef4fa;
            color: #36536f;

            font-size: 11px;
            font-weight: 700;
        }

        .metric-details-section {
            padding: 13px 0;

            border-top: 1px solid var(--border);
        }

        .metric-details-section h3 {
            margin: 0 0 5px;

            color: var(--primary);
            font-size: 14px;
        }

        .metric-details-section p {
            margin: 0;

            color: #31465d;
            font-size: 13px;
            line-height: 1.55;
        }

        .metric-details-next-step {
            margin-top: 2px;
        }

        @media (max-width: 620px) {
            .metric-details-modal {
                padding: 12px;
            }

            .metric-details-dialog {
                width: 100%;
                max-height: calc(100vh - 24px);
                padding: 18px;
            }
        }

        /* -------------------------------------------------- */
        /* Heatmap                                             */
        /* -------------------------------------------------- */

        .metric-heatmap {
            min-width: 0;
            overflow: hidden;

            border: 1px solid var(--border);
            border-radius: var(--radius-md);
            background: white;
            box-shadow: var(--shadow-sm);
        }

        /* -------------------------------------------------- */
        /* Buttons                                             */
        /* -------------------------------------------------- */

        .copy-btn {
            padding: 8px 12px;
            border: 1px solid #2d669d;
            border-radius: 7px;
            background: #2d669d;
            color: white;

            cursor: pointer;
            font-size: 13px;
            font-weight: 600;

            transition:
                background 0.18s ease,
                transform 0.18s ease,
                box-shadow 0.18s ease;
        }

        .copy-btn:hover {
            background: #214f7b;
            box-shadow: 0 4px 10px rgba(33, 79, 123, 0.20);
            transform: translateY(-1px);
        }

        code {
            padding: 3px 6px;
            border-radius: 5px;
            background: #eef2f6;
            color: #33465c;
            font-family: "SFMono-Regular", Consolas, "Liberation Mono", monospace;
            font-size: 12px;
        }

        /* -------------------------------------------------- */
        /* Responsive                                          */
        /* -------------------------------------------------- */

        @media (max-width: 800px) {
            .report-header-content {
                align-items: flex-start;
                flex-direction: column;
            }

            .report-badge {
                display: none;
            }

            .report-container {
                width: min(100% - 20px, 1440px);
                margin-top: 16px;
            }

            .tab-content {
                padding: 18px 14px;
            }

            .tab-bar {
                position: static;
            }

            .metric-table {
                display: block;
                overflow-x: auto;
                white-space: nowrap;
            }

            .report-header h1 {
                font-size: 24px;
            }
        }

        .report-section {
            margin-bottom: 34px;
        }

        .report-section:last-child {
            margin-bottom: 0;
        }

        .section-description {
            max-width: 850px;
            margin-top: -4px;
            color: var(--text-secondary);
            font-size: 14px;
        }

        .tab-content.active {
            display: block;
            animation: tabFadeIn 0.22s ease;
        }

        @keyframes tabFadeIn {
            from {
                opacity: 0;
                transform: translateY(4px);
            }

            to {
                opacity: 1;
                transform: translateY(0);
            }
        }

        /* Metric-family styling */

        .metric-family-global {
            background: #eef2f7;
            border-left: 4px solid #66788a;
        }

        .metric-family-mpi {
            background: #eaf3ff;
            border-left: 4px solid #4f86c6;
        }

        .metric-family-openmp {
            background: #ecf8ef;
            border-left: 4px solid #4f9d69;
        }

        .metric-family-cuda {
            background: #fff1e7;
            border-left: 4px solid #d9823b;
        }

        .metric-family-host {
            background: #f2edff;
            border-left: 4px solid #8066bf;
        }

        .metric-family-device {
            background: #e9f7f5;
            border-left: 4px solid #318c82;
        }

        .metric-main {
            font-weight: 700;
        }

        .metric-child {
            padding-left: 28px !important;
        }

        .metric-grandchild {
            padding-left: 48px !important;
        }


        /* Severity badges */

        .metric-value {
            display: inline-flex;

            width: 96px;
            min-width: 96px;
            height: 30px;
            padding: 0 8px;

            align-items: center;
            justify-content: center;

            border: 1px solid rgba(30, 50, 70, 0.10);
            border-radius: 3px;

            cursor: pointer;

            font-family: inherit;
            font-size: 13px;
            font-weight: 700;
            font-variant-numeric: tabular-nums;

            transition:
                transform 0.15s ease,
                box-shadow 0.15s ease;
        }

        .metric-value:hover {
            transform: translateY(-1px);
            box-shadow: 0 3px 9px rgba(20, 38, 63, 0.16);
            filter: brightness(0.97);
        }

        .metric-above-reference {
            background: #e7f0fb;
            color: #245887;
            border: 1px solid #abc7e4;
        }

        .metric-unavailable {
            background: #f0f2f5;
            color: #7a8490;
            border: 1px solid #d7dce2;
        }

        /* -------------------------------------------------- */
        /* Efficiency metrics table                            */
        /* -------------------------------------------------- */

        .metric-table-card {
            overflow: hidden;
            border: 1px solid var(--border);
            border-radius: var(--radius-md);
            background: white;
            box-shadow: var(--shadow-sm);
        }

        .efficiency-table-wrapper {
            position: relative;
            width: 100%;
            overflow-x: auto;
            overflow-y: visible;
        }

        .efficiency-table {
            width: 100%;
            border-collapse: separate;
            border-spacing: 0;
            background: white;
            font-size: clamp(15px, 0.9vw, 18px);
        }

        .efficiency-table th,
        .efficiency-table td {
            padding: 11px 14px;
            border-bottom: 1px solid var(--border);
        }

        .efficiency-table thead th {
            position: sticky;
            top: 0;
            z-index: 4;

            background: #edf3f9;
            color: #29435f;
            font-size: clamp(14px, 0.82vw, 16px);
            font-weight: 700;
            text-align: center;
        }

        .efficiency-table .metric-column-header {
            position: sticky;
            top: 0;
            left: 0;
            z-index: 7;

            min-width: 330px;
            text-align: left;
            background: #edf3f9;
            box-shadow: 7px 0 10px -10px rgba(20, 38, 63, 0.55);
        }

        .efficiency-table tbody tr:last-child td {
            border-bottom: 0;
        }

        .efficiency-table tbody tr:hover .metric-value-cell {
            background: #f8fbff;
        }

        .efficiency-table tbody tr:hover .metric-name-cell {
            filter: brightness(0.985);
        }

        /* -------------------------------------------------- */
        /* PNG export                                         */
        /* -------------------------------------------------- */

        .export-combined-efficiency-table {
            background: #fff;
        }

        .export-combined-efficiency-table
        .export-device-start
        td {
            border-top: 2px solid #66788a !important;
        }

        .export-temporary-efficiency-table,
        .export-combined-efficiency-table {
            width: max-content !important;
            max-width: none !important;

            background: #fff;
        }

        .export-temporary-efficiency-table
        .efficiency-table-wrapper,
        .export-combined-efficiency-table
        .efficiency-table-wrapper {
            width: max-content;
            overflow: visible;
        }

        .export-temporary-efficiency-table
        .efficiency-table,
        .export-combined-efficiency-table
        .efficiency-table {
            width: max-content !important;
            min-width: 0 !important;
        }

        .export-runtime-combined {
            display: flex;
            flex-direction: column;

            width: max-content;
            max-width: none;

            gap: 12px;

            background: white;
        }

        .export-runtime-combined
        .export-runtime-detail {
            border-top: 2px solid #66788a;
        }

        /*
        * Let the metric-name column use the width required
        * by its longest metric instead of the fixed 330px
        * width used by the interactive report.
        */

        .export-temporary-efficiency-table
        .metric-name-cell,
        .export-temporary-efficiency-table
        .metric-column-header,
        .export-combined-efficiency-table
        .metric-name-cell,
        .export-combined-efficiency-table
        .metric-column-header {
            width: auto !important;
            min-width: 0 !important;
            white-space: nowrap;
        }

        .export-combined-efficiency-table
        .export-device-start
        td {
            border-top: 2px solid #66788a !important;
        }

        .export-table-footer {
            margin-top: 6px;
            padding: 6px 4px 2px;

            border-top: 1px solid #d7dde5;

            color: #66788a;

            font-size: 11px;
            font-style: italic;
            line-height: 1.35;
        }

        /* -------------------------------------------------- */
        /* END PNG export                                     */
        /* -------------------------------------------------- */

        .metric-name-cell {
            position: sticky;
            left: 0;
            z-index: 3;

            min-width: 330px;
            color: #20344d;
            text-align: left;

            font-size: clamp(15px, 0.9vw, 18px);
            line-height: 1.35;

            box-shadow: 7px 0 10px -10px rgba(20, 38, 63, 0.55);
        }

        .metric-value-cell {
            min-width: 112px;
            padding-left: 6px !important;
            padding-right: 6px !important;

            background: white;
            text-align: center;

            transition: background 0.15s ease;
        }

        .metric-value {
            display: inline-flex;

            width: 104px;
            min-width: 104px;
            height: 34px;
            padding: 0 8px;

            align-items: center;
            justify-content: center;

            border: 1px solid rgba(30, 50, 70, 0.10);
            border-radius: 3px;

            cursor: pointer;

            font-family: inherit;
            font-size: clamp(14px, 0.85vw, 17px);
            font-weight: 700;
            font-variant-numeric: tabular-nums;

            transition:
                transform 0.15s ease,
                box-shadow 0.15s ease;
        }

        .metric-value:hover {
            transform: translateY(-1px);
            box-shadow: 0 3px 9px rgba(20, 38, 63, 0.16);
        }

        .metric-value:focus {
            outline: 2px solid #4f86c6;
            outline-offset: 2px;
        }

        .metric-name-cell {
            padding-left: calc(
                16px + (var(--metric-depth, 0) * 22px)
            ) !important;
        }

        /* -------------------------------------------------- */
        /* Efficiency interpretation scale                     */
        /* -------------------------------------------------- */

        .efficiency-scale-panel {
            margin-bottom: 22px;
            padding: 20px 22px;

            border: 1px solid var(--border);
            border-radius: var(--radius-md);
            background: #ffffff;
            box-shadow: var(--shadow-sm);
        }

        .efficiency-scale-header h3 {
            margin: 0 0 4px;
            color: var(--primary);
            font-size: 18px;
        }

        .efficiency-scale-header p {
            margin: 0;
            color: var(--text-secondary);
            font-size: 14px;
        }

        /* Gradient */

        .efficiency-gradient-container {
            position: relative;
            margin: 18px 8px 14px;
        }

        .efficiency-gradient {
            width: 100%;
            height: 18px;

            border: 1px solid rgba(30, 50, 70, 0.14);
            border-radius: 999px;

            background: linear-gradient(
                to right,
                #b2182b 0%,
                #ef6548 20%,
                #fdbb84 40%,
                #fee8a8 60%,
                #ffffbf 75%,
                #d9ef8b 85%,
                #b8e186 92%,
                #4dac26 100%
            );
        }

        .efficiency-gradient-markers {
            position: relative;
            height: 18px;
            margin-top: 6px;

            color: var(--text-secondary);
            font-size: 12px;
            font-weight: 600;
        }

        .efficiency-gradient-markers span {
            position: absolute;
            transform: translateX(-50%);
        }

        .efficiency-gradient-markers span:first-child {
            transform: none;
        }

        .efficiency-gradient-markers span:last-child {
            transform: translateX(-100%);
        }

        .efficiency-scale-compact-labels {
            display: grid;
            align-items: start;

            margin-top: 7px;

            color: var(--text-secondary);
            font-size: 11px;
            line-height: 1.3;
        }

        .efficiency-scale-compact-labels span {
            padding: 0 5px;
            text-align: center;
        }

        .efficiency-scale-compact-labels span:first-child {
            padding-left: 0;
            text-align: left;
        }

        .efficiency-scale-compact-labels span:last-child {
            padding-right: 0;
            text-align: right;
        }

        .efficiency-scale-compact-labels strong {
            color: #243b58;
        }

        /* Semantic ranges */

        .efficiency-scale-ranges {
            display: grid;
            grid-template-columns: 60fr 25fr 15fr;

            overflow: hidden;

            border: 1px solid var(--border);
            border-radius: var(--radius-sm);

            background: var(--surface-soft);
        }

        .scale-range {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 8px;

            padding: 10px 14px;

            border-right: 1px solid var(--border);

            font-size: 13px;
        }

        .scale-range:last-child {
            border-right: 0;
        }

        .scale-range strong {
            color: #243b58;
        }

        .scale-range span {
            color: var(--text-secondary);
            font-size: 12px;
        }

        .scale-range-critical {
            border-top: 3px solid #d94841;
        }

        .scale-range-attention {
            border-top: 3px solid #fee08b;
        }

        .scale-range-good {
            border-top: 3px solid #6dbb4f;
        }

        .efficiency-above-reference {
            margin: 14px 0 0;
            color: var(--text-secondary);
            font-size: 13px;
        }

        .efficiency-scale-guidance {
            margin: 16px 0 0;
            padding-top: 14px;

            border-top: 1px solid var(--border);

            color: #40546b;
            font-size: 14px;
        }

        /* Responsive */

        @media (max-width: 700px) {
            .efficiency-scale-ranges {
                display: block;
            }

            .scale-range {
                border-right: 0;
                border-bottom: 1px solid var(--border);
            }

            .scale-range:last-child {
                border-bottom: 0;
            }

            .scale-range-critical,
            .scale-range-attention,
            .scale-range-good {
                border-top: 0;
                border-left-width: 4px;
                border-left-style: solid;
            }

            .scale-range-critical {
                border-left-color: #d94841;
            }

            .scale-range-attention {
                border-left-color: #fee08b;
            }

            .scale-range-good {
                border-left-color: #6dbb4f;
            }
        }

        /* -------------------------------------------------- */
        /* END Efficiency interpretation scale                */
        /* -------------------------------------------------- */

        .metric-table-card {
            margin-bottom: 22px;
        }

        /* -------------------------------------------------- */
        /* Performance and scaling interpretation              */
        /* -------------------------------------------------- */

        .performance-interpretation h3,
        .scaling-interpretation h3 {
            font-size: 17px;
        }

        .execution-domains-analysis-summary h4 {
            font-size: 13px;
        }

        .performance-interpretation h3 {
            margin-top: 0;
        }

        .scaling-interpretation {
            margin-top: 22px;
        }

        .performance-interpretation p,
        .scaling-interpretation p {
            margin: 0;
            color: #31465d;
            font-size: 14px;
            line-height: 1.7;
        }

        /* -------------------------------------------------- */
        /* Header trace notes                                 */
        /* -------------------------------------------------- */

        .trace-header-note {
            margin: 8px 0 12px;
            color: var(--text-secondary);
            font-size: 13px;
        }

        .trace-header-note code {
            color: #29435f;
            font-weight: 600;
        }

        /* -------------------------------------------------- */
        /* Parave view notes                                  */
        /* -------------------------------------------------- */

        .paraver-view-note {
            margin: 14px 0 0;
            color: #31465d;
            font-size: 14px;
            line-height: 1.7;
        }
      
        /* -------------------------------------------------- */
        /* Execution Domains                                  */
        /* -------------------------------------------------- */

        .execution-domains-analysis {
            min-width: 0;
        }

        .execution-domain-block {
            margin-bottom: 10px;
        }

        .execution-domain-title {
            margin: 4px 0;
            padding: 4px 8px;

            border-left: 4px solid var(--primary);

            background: #f3f7fb;
            color: var(--primary);

            font-size: 12px;
            font-weight: 800;
            letter-spacing: .09em;
        }

        .execution-domain-host .execution-domain-title {
            border-left-color: #8066bf;
        }

        .execution-domain-device .execution-domain-title {
            border-left-color: #318c82;
        }

        .execution-domains-analysis-summary h4 {
            margin: 12px 0 6px;

            color: var(--primary);
            font-size: 12px;
            font-weight: 800;
            letter-spacing: .08em;
        }

        .execution-domain-analysis-group
        + .execution-domain-analysis-group {
            margin-top: 18px;
            padding-top: 14px;

            border-top: 1px solid var(--border);
        }


        /* -------------------------------------------------- */
        /* Additional Execution Domains                       */
        /* -------------------------------------------------- */
        .execution-domains-analysis .efficiency-table th,
        .execution-domains-analysis .efficiency-table td {
            padding: 5px 8px;
        }

        .execution-domains-analysis .metric-name-cell,
        .execution-domains-analysis
        .efficiency-table
        .metric-column-header {
            min-width: 220px;
        }

        .execution-domains-analysis .metric-name-cell {
            padding-left: calc(
                9px + (var(--metric-depth, 0) * 14px)
            ) !important;
        }

        .execution-domains-analysis .metric-value-cell {
            min-width: 88px;
        }

        .execution-domains-analysis .metric-value {
            min-width: 66px;
            padding: 4px 6px;
            font-size: 12px;
        }

        .execution-domains-analysis .metric-table-card {
            margin-bottom: 8px;
        }



        /* -------------------------------------------------- */
        /* Analysis scope notes                                */
        /* -------------------------------------------------- */

        .analysis-scope-note {
            margin-bottom: 12px;
            padding: 10px 14px;

            border: 1px solid #d9c98c;
            border-left: 4px solid #c79a20;
            border-radius: var(--radius-md);

            background: #fffaf0;
            color: #4f452d;

            font-size: 13px;
        }

        .analysis-scope-note h3 {
            margin: 0 0 4px;

            color: #6f5617;
            font-size: 14px;
            line-height: 1.3;
        }

        .analysis-scope-note p {
            margin: 4px 0;
            line-height: 1.45;
        }

        /* -------------------------------------------------- */
        /* Two-pane analysis workspace                         */
        /* -------------------------------------------------- */

        .report-container {
            flex: 1 1 auto;
            min-height: 0;
            width: min(1680px, calc(100% - 32px));
            margin: 24px auto;
        }

        .report-workspace {
            display: grid;
            grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
            gap: 20px;
            align-items: stretch;
            height: 100%;
            min-height: 0;
        }

        .application-panel,
        .detail-panel {
            min-width: 0;
            min-height: 0;
            overflow-y: auto;
            overscroll-behavior: contain;
            scrollbar-gutter: stable;
        }

        .application-panel {
            padding-right: 8px;
        }

        .detail-panel {
            height: 100%;
            max-height: 100%;
            padding-right: 8px;
        }

        .application-panel {
            display: flex;
            flex-direction: column;
            gap: 20px;
            height: 100%;
            max-height: 100%;
        }

        /* Keep the application cards at their natural height. Without this,
           flexbox may shrink them to fit the column, clipping their contents
           instead of creating vertical overflow for the panel scrollbar. */
        .application-panel > .workspace-panel {
            flex: 0 0 auto;
        }

        .workspace-panel {
            min-width: 0;
            padding: 22px;
            border: 1px solid var(--border);
            border-radius: var(--radius-lg);
            background: var(--surface);
            box-shadow: var(--shadow-sm);
            overflow: hidden;
        }

        .detail-workspace {
            overflow: visible;
        }

        .workspace-panel > h2 {
            margin-top: 0;
        }

        .detail-navigation {
            position: sticky;
            top: 0;
            z-index: 30;

            display: flex;
            flex-direction: column;
            gap: 14px;

            margin: 0 0 24px;
            padding: 0 0 18px;

            border-bottom: 1px solid var(--border);
            background: var(--surface);
            box-shadow: 0 6px 12px -10px rgba(20, 38, 63, 0.35);
        }

        .detail-nav-group {
            display: grid;
            grid-template-columns: minmax(130px, auto) minmax(0, 1fr);
            gap: 12px;
            align-items: center;
        }

        .detail-nav-label {
            color: var(--text-secondary);
            font-size: 12px;
            font-weight: 700;
            letter-spacing: .05em;
            text-transform: uppercase;
        }

        .detail-tab-list {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
        }

        .detail-tab-button {
            min-height: 36px;
            padding: 7px 16px;
            border: 1px solid #b8c7d8;
            border-radius: 999px;
            background: #fff;
            color: #40546b;
            cursor: pointer;
            font: inherit;
            font-size: 13px;
            font-weight: 650;
        }

        .detail-tab-button:hover {
            border-color: #6f96bd;
            background: #f2f7fc;
            color: var(--primary);
        }

        .detail-tab-button.active {
            border-color: var(--primary);
            background: var(--primary);
            color: #fff;
        }

        .detail-view {
            display: none;
        }

        .detail-view.active {
            display: block;
            animation: tabFadeIn .22s ease;
        }

        .application-panel .metric-table,
        .application-panel .efficiency-table,
        .detail-panel .efficiency-table {
            width: max-content;
            min-width: 100%;
        }

        .application-panel .report-section,
        .efficiency-table-wrapper {
            overflow-x: auto;
        }

        @media (max-width: 980px) {
            html,
            body {
                height: auto;
                min-height: 100%;
            }

            body {
                display: block;
                overflow: auto;
            }

            .report-header {
                position: sticky;
                top: 0;
            }

            .report-container {
                width: min(100% - 24px, 1680px);
                margin: 16px auto 28px;
            }

            .report-workspace {
                grid-template-columns: 1fr;
                height: auto;
            }

            .application-panel,
            .detail-panel {
                overflow: visible;
                padding-right: 0;
            }

            .detail-nav-group {
                grid-template-columns: 1fr;
            }
        }


        /* -------------------------------------------------- */
        /* Step 4: persistent, collapsible analysis workspace  */
        /* -------------------------------------------------- */

        .workspace-shell {
            display: flex;
            flex-direction: column;
            gap: 12px;
            height: 100%;
            min-height: 0;
        }

        .analysis-layout {
            display: grid;
            grid-template-columns: minmax(420px, 46%) minmax(0, 54%);
            gap: 20px;
            align-items: stretch;
            height: 100%;
            min-height: 0;
            transition: grid-template-columns .24s ease;
        }

        .analysis-layout.sidebar-collapsed {
            grid-template-columns: 54px minmax(0, 1fr);
        }

        .analysis-layout.context-maximized {
            grid-template-columns: minmax(0, 1fr);
        }

        .analysis-layout.context-maximized .analysis-sidebar {
            width: 100%;
        }

        .analysis-layout.context-maximized .component-panel {
            display: none;
        }

        .analysis-layout.context-maximized .sidebar-maximize-button {
            border-color: var(--primary);
            background: var(--primary);
            color: #fff;
        }

        .analysis-layout.sidebar-collapsed .sidebar-view-container,
        .analysis-layout.sidebar-collapsed .sidebar-tabs,
        .analysis-layout.sidebar-collapsed .sidebar-title {
            display: none;
        }

        .analysis-layout.sidebar-collapsed .analysis-sidebar {
            overflow: hidden;
        }

        .analysis-layout.sidebar-collapsed .sidebar-header {
            height: 100%;
            padding: 10px 8px;
            border-bottom: 0;
        }

        .analysis-layout.sidebar-collapsed .sidebar-header-row {
            justify-content: center;
            margin-bottom: 0;
        }

        .analysis-layout.sidebar-collapsed .sidebar-header-actions {
            width: 100%;
            justify-content: center;
        }

        .analysis-layout.sidebar-collapsed .sidebar-maximize-button {
            display: none;
        }

        .analysis-layout.sidebar-collapsed .sidebar-collapse-icon {
            transform: rotate(180deg);
        }

        .analysis-sidebar,
        .component-panel {
            min-width: 0;
            min-height: 0;
            overflow-y: auto;
            overscroll-behavior: contain;
            scrollbar-gutter: stable;
        }

        .analysis-sidebar {
            display: flex;
            flex-direction: column;
            border: 1px solid var(--border);
            border-radius: var(--radius-lg);
            background: var(--surface);
            box-shadow: var(--shadow-sm);
        }

        .sidebar-header {
            position: sticky;
            top: 0;
            z-index: 40;
            flex: 0 0 auto;
            padding: 12px;
            border-bottom: 1px solid var(--border);
            background: rgba(255, 255, 255, 0.97);
            backdrop-filter: blur(8px);
        }

        .sidebar-header-row {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 10px;
            margin-bottom: 10px;
        }

        .sidebar-title {
            color: var(--primary);
            font-size: 12px;
            font-weight: 800;
            letter-spacing: .07em;
            text-transform: uppercase;
        }

        .sidebar-header-actions {
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .sidebar-control-button {
            display: grid;
            width: 34px;
            height: 34px;
            flex: 0 0 34px;
            place-items: center;
            border: 1px solid #b8c7d8;
            border-radius: 9px;
            background: #fff;
            color: var(--primary);
            cursor: pointer;
            font: inherit;
        }

        .sidebar-control-button:hover {
            border-color: #6f96bd;
            background: #f2f7fc;
        }

        .sidebar-control-button:focus-visible {
            outline: 2px solid #4f86c6;
            outline-offset: 2px;
        }

        .sidebar-maximize-icon {
            display: inline-block;
            font-size: 18px;
            line-height: 1;
        }

        .sidebar-collapse-icon {
            display: inline-block;
            font-size: 25px;
            line-height: 1;
            transition: transform .24s ease;
        }

        .sidebar-tabs {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 8px;
        }

        .sidebar-tab {
            min-height: 42px;
            padding: 9px 12px;
            border: 1px solid #b8c7d8;
            border-radius: var(--radius-sm);
            background: #fff;
            color: #40546b;
            cursor: pointer;
            font: inherit;
            font-size: 13px;
            font-weight: 700;
        }

        .sidebar-tab:hover {
            border-color: #6f96bd;
            background: #f2f7fc;
            color: var(--primary);
        }

        .sidebar-tab:focus-visible {
            outline: 2px solid #4f86c6;
            outline-offset: 2px;
        }

        .sidebar-tab.active {
            border-color: var(--primary);
            background: var(--primary);
            color: #fff;
            box-shadow: 0 3px 10px rgba(23, 54, 93, 0.18);
        }

        .sidebar-view-container {
            flex: 1 1 auto;
            min-height: 0;
            padding: 16px;
        }

        .sidebar-view {
            display: none;
        }

        .sidebar-view.active {
            display: block;
            animation: workspaceFadeIn .20s ease;
        }

        .sidebar-view .application-panel {
            display: flex;
            height: auto;
            max-height: none;
            overflow: visible;
            padding-right: 0;
        }

        .sidebar-view .workspace-panel {
            box-shadow: none;
        }

        .runtime-model-static-view {
            display: block;
        }

        .runtime-model-static-view + .runtime-model-static-view {
            margin-top: 18px;
        }

        .component-panel {
            display: flex;
            align-items: stretch;
            padding-right: 8px;
        }

        .component-placeholder {
            display: flex;
            width: 100%;
            min-height: 100%;
            align-items: center;
            justify-content: center;
            flex-direction: column;
            text-align: center;
            color: var(--text-secondary);
        }

        .component-placeholder-icon {
            display: grid;
            width: 62px;
            height: 62px;
            margin-bottom: 16px;
            place-items: center;
            border: 1px solid #b8c7d8;
            border-radius: 50%;
            background: #f3f7fb;
            color: var(--primary);
            font-size: 30px;
        }

        .component-placeholder-eyebrow {
            margin: 0 0 6px;
            color: #527397;
            font-size: 12px;
            font-weight: 700;
            letter-spacing: 0.08em;
            text-transform: uppercase;
        }

        .component-placeholder h2 {
            margin-bottom: 10px;
        }

        .component-placeholder p {
            max-width: 560px;
            margin: 5px auto;
        }

        .component-placeholder-note {
            padding-top: 12px;
            border-top: 1px solid var(--border);
            font-size: 13px;
        }

        .component-view-storage {
            display: none !important;
        }

        .runtime-model-composed-start {
            scroll-margin-top: 84px;
        }

        .analysis-jump-link {
            display: inline-flex;
            align-items: center;
            gap: 7px;
            margin: 0 0 14px;
            padding: 7px 11px;
            border: 1px solid #9fb6cf;
            border-radius: 999px;
            background: #f7faff;
            color: var(--primary);
            cursor: pointer;
            font: inherit;
            font-size: 12px;
            font-weight: 750;
            line-height: 1.2;
        }

        .analysis-jump-link:hover {
            border-color: var(--primary);
            background: #eaf3ff;
        }

        .analysis-jump-link:focus-visible {
            outline: 2px solid #4f86c6;
            outline-offset: 2px;
        }

        .analysis-jump-link-back {
            margin: 0;
            background: #fff;
            font-size: 11px;
        }

        #runtime-model-component-selectors {
            scroll-margin-top: 84px;
        }

        .analysis-drilldown-separator {
            display: flex;
            align-items: center;
            gap: 12px;
            margin: 24px 0 14px;
            color: #527397;
            font-size: 11px;
            font-weight: 800;
            letter-spacing: .07em;
            text-transform: uppercase;
        }

        .analysis-drilldown-separator::before,
        .analysis-drilldown-separator::after {
            content: "";
            flex: 1 1 auto;
            height: 1px;
            background: var(--border);
        }

        .runtime-component-selector {
            margin-bottom: 12px;
            padding: 12px;
            border: 1px solid #cbd8e6;
            border-radius: var(--radius-md);
            background: #f7faff;
        }

        .runtime-component-selector-header h3 {
            margin: 0 0 2px;
            color: var(--primary);
            font-size: 15px;
        }

        .runtime-component-selector-header p {
            margin: 0 0 8px;
            color: var(--text-secondary);
            font-size: 12px;
            line-height: 1.4;
        }

        .analysis-navigator {
            display: flex;
            flex-direction: column;
            gap: 12px;
        }

        .analysis-navigator-group + .analysis-navigator-group {
            padding-top: 12px;
            border-top: 1px solid var(--border);
        }

        .runtime-component-list {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
            gap: 8px;
        }

        .runtime-component-button {
            display: flex;
            min-height: 50px;
            flex-direction: column;
            align-items: flex-start;
            justify-content: center;
            gap: 1px;
            padding: 8px 11px;
            border: 1px solid #9fb6cf;
            border-radius: 9px;
            background: #fff;
            color: var(--primary);
            cursor: pointer;
            text-align: left;
        }

        .runtime-component-button:hover {
            border-color: var(--primary);
            background: #edf5fd;
        }

        .runtime-component-button.active {
            border-color: var(--primary);
            background: var(--primary);
            color: #fff;
            box-shadow: 0 4px 12px rgba(23, 54, 93, 0.20);
        }

        .runtime-component-name {
            font-size: 14px;
            font-weight: 750;
            line-height: 1.2;
        }

        .runtime-component-kind {
            color: #66788a;
            font-size: 10px;
            font-weight: 650;
            line-height: 1.2;
        }

        .runtime-component-button.active .runtime-component-kind {
            color: #d8e7f5;
        }

        .component-analysis-view {
            display: none;
            width: 100%;
        }

        .component-analysis-view.active {
            display: block;
            animation: workspaceFadeIn .22s ease;
        }

        @keyframes workspaceFadeIn {
            from { opacity: 0; transform: translateY(5px); }
            to { opacity: 1; transform: translateY(0); }
        }

        .component-analysis-workspace {
            width: 100%;
            min-height: 100%;
            overflow: visible;
        }

        .component-analysis-header {
            margin-bottom: 18px;
            padding-bottom: 14px;
            border-bottom: 1px solid var(--border);
        }

        .component-analysis-header h1 {
            margin: 0;
            color: var(--primary);
            font-size: 25px;
        }

        .component-analysis-eyebrow {
            margin: 0 0 5px;
            color: #527397;
            font-size: 12px;
            font-weight: 700;
            letter-spacing: .08em;
            text-transform: uppercase;
        }

        .domain-selector {
            position: sticky;
            top: 0;
            z-index: 25;
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 14px;
            margin-bottom: 20px;
            padding: 12px 0 14px;
            border-bottom: 1px solid var(--border);
            background: var(--surface);
        }

        .domain-selector-label {
            color: var(--text-secondary);
            font-size: 12px;
            font-weight: 700;
            letter-spacing: .05em;
            text-transform: uppercase;
        }

        .domain-selector-buttons {
            display: flex;
            gap: 8px;
        }

        .domain-selector-button {
            padding: 8px 18px;
            border: 1px solid #aabed2;
            border-radius: 999px;
            background: #fff;
            color: #40546b;
            cursor: pointer;
            font: inherit;
            font-size: 13px;
            font-weight: 700;
        }

        .domain-selector-button.active {
            border-color: var(--primary);
            background: var(--primary);
            color: #fff;
        }

        .execution-domain-view {
            display: none;
        }

        .execution-domain-view.active {
            display: block;
        }

        @media (max-width: 1100px) {
            .analysis-layout {
                grid-template-columns: minmax(360px, 48%) minmax(0, 52%);
            }
        }

        @media (max-width: 980px) {
            .analysis-layout,
            .analysis-layout.sidebar-collapsed,
            .analysis-layout.context-maximized {
                grid-template-columns: 1fr;
                height: auto;
            }

            .analysis-layout.context-maximized .component-panel {
                display: flex;
            }

            .analysis-layout.sidebar-collapsed .sidebar-view-container,
            .analysis-layout.sidebar-collapsed .sidebar-tabs,
            .analysis-layout.sidebar-collapsed .sidebar-title {
                display: initial;
            }

            .analysis-layout.sidebar-collapsed .sidebar-tabs {
                display: grid;
            }

            .analysis-layout.sidebar-collapsed .sidebar-header {
                height: auto;
                padding: 12px;
                border-bottom: 1px solid var(--border);
            }

            .analysis-layout.sidebar-collapsed .sidebar-header-row {
                justify-content: space-between;
                margin-bottom: 10px;
            }

            .analysis-layout.sidebar-collapsed .sidebar-collapse-icon {
                transform: none;
            }

            .analysis-sidebar,
            .component-panel {
                overflow: visible;
                padding-right: 0;
            }

            .component-placeholder {
                min-height: 340px;
            }
        }

        @media (max-width: 620px) {
            .sidebar-tabs {
                grid-template-columns: 1fr;
            }
        }


        /* -------------------------------------------------- */
        /* Performance Assessment layout                */
        /* -------------------------------------------------- */

        .performance-assessment-view {
            display: flex;
            flex-direction: column;
            gap: 24px;
            height: 100%;
            min-height: 0;
            overflow-y: auto;
            padding-right: 8px;
        }

        .performance-global-metrics,
        .performance-runtime-analysis {
            padding: 22px;
            border: 1px solid var(--border);
            border-radius: var(--radius-lg);
            background: var(--surface);
            box-shadow: var(--shadow-sm);
        }

        .performance-section-header {
            margin-bottom: 20px;
            padding-bottom: 14px;
            border-bottom: 1px solid var(--border);
        }

        .performance-section-header h2 {
            margin-bottom: 6px;
        }

        .performance-section-header p {
            max-width: 900px;
            margin: 0;
            color: var(--text-secondary);
            font-size: 14px;
        }

        .performance-analysis-layout {
            display: grid;
            grid-template-columns:
                minmax(0, 1fr)
                minmax(300px, 0.75fr)
                170px;
            gap: 16px;
            align-items: stretch;
        }

        .performance-primary-panel,
        .performance-secondary-panel {
            min-width: 0;
            min-height: 420px;
            padding: 18px;

            border: 1px solid var(--border);
            border-radius: var(--radius-md);

            background: var(--surface-soft);
            overflow: hidden;
        }

        .performance-secondary-panel {
            position: relative;
        }

        .performance-secondary-placeholder {
            display: flex;
            min-height: 380px;
            max-width: 430px;
            margin: 0 auto;

            align-items: center;
            justify-content: center;
            flex-direction: column;

            color: var(--text-secondary);
            text-align: center;
        }

        .performance-secondary-placeholder[hidden] {
            display: none;
        }

        .performance-secondary-placeholder h3 {
            margin-top: 0;
            color: var(--primary);
        }

        .performance-secondary-view {
            display: none;
            min-width: 0;
        }

        .performance-secondary-view.is-active {
            display: block;
            animation: tabFadeIn 0.22s ease;
        }

        .performance-secondary-view-header {
            display: flex;
            align-items: flex-start;
            justify-content: space-between;
            gap: 16px;

            margin-bottom: 18px;
            padding-bottom: 14px;

            border-bottom: 1px solid var(--border);
        }

        .performance-secondary-heading {
            min-width: 0;
        }

        .performance-secondary-heading h3 {
            margin: 0 0 7px;
            color: var(--primary);
            font-size: 20px;
        }

        .performance-secondary-heading > p:last-child {
            margin: 0;
            color: var(--text-secondary);
            font-size: 13px;
            line-height: 1.55;
        }

        .performance-secondary-eyebrow {
            margin: 0 0 4px;

            color: #527397;
            font-size: 11px;
            font-weight: 750;
            letter-spacing: 0.08em;
            text-transform: uppercase;
        }

        .performance-secondary-close {
            display: grid;
            width: 34px;
            height: 34px;
            flex: 0 0 34px;

            place-items: center;

            border: 1px solid #aabed2;
            border-radius: 8px;

            background: white;
            color: var(--primary);

            cursor: pointer;
            font: inherit;
            font-size: 22px;
            line-height: 1;
        }

        .performance-secondary-close:hover {
            border-color: var(--primary);
            background: var(--primary-light);
        }

        .performance-secondary-close:focus-visible {
            outline: 2px solid #4f86c6;
            outline-offset: 2px;
        }

        .performance-secondary-body {
            min-width: 0;
        }

        .performance-secondary-body .metric-table-card,
        .performance-secondary-body .efficiency-table-wrapper {
            max-width: 100%;
        }

        .performance-secondary-body .efficiency-table {
            width: max-content;
            min-width: 100%;
        }

        .performance-secondary-body .metric-name-cell,
        .performance-secondary-body
        .efficiency-table
        .metric-column-header {
            min-width: 250px;
        }

        .performance-analysis-selector {
            display: flex;
            flex-direction: column;
            gap: 16px;
            min-width: 0;
        }

        .performance-analysis-selector.is-empty {
            padding: 14px;
            border: 1px dashed var(--border);
            border-radius: var(--radius-md);
            color: var(--text-secondary);
            background: var(--surface-soft);
        }

        .analysis-selector-group {
            padding: 12px;
            border: 1px solid var(--border);
            border-radius: var(--radius-md);
            background: #f7faff;
        }

        .analysis-selector-group h4 {
            margin: 0 0 10px;
            color: var(--primary);
            font-size: 13px;
        }

        .analysis-selector-buttons {
            display: flex;
            flex-direction: column;
            gap: 8px;
        }


        .analysis-selector-button {
            width: 100%;
            min-height: 42px;
            padding: 9px 11px;

            border: 1px solid #9fb6cf;
            border-radius: 8px;

            background: white;
            color: var(--primary);

            cursor: pointer;
            text-align: left;

            font: inherit;
            font-size: 13px;
            font-weight: 700;

            transition:
                border-color 0.16s ease,
                background 0.16s ease,
                color 0.16s ease,
                box-shadow 0.16s ease;
        }

        .analysis-selector-button:hover {
            border-color: var(--primary);
            background: #edf5fd;
        }

        .analysis-selector-button.is-selected {
            border-color: var(--primary);
            background: var(--primary);
            color: white;
            box-shadow: 0 4px 12px rgba(23, 54, 93, 0.20);
        }

        .analysis-selector-button:focus-visible {
            outline: 2px solid #4f86c6;
            outline-offset: 2px;
        }

        .performance-primary-panel .efficiency-table,
        .performance-secondary-panel .efficiency-table {
            width: max-content;
            min-width: 100%;
        }

        @media (max-width: 1100px) {
            .performance-analysis-layout {
                grid-template-columns:
                    minmax(0, 1fr)
                    minmax(260px, 0.75fr);
            }

            .performance-analysis-selector {
                grid-column: 1 / -1;
                display: grid;
                grid-template-columns: repeat(
                    auto-fit,
                    minmax(220px, 1fr)
                );
            }
        }

        @media (max-width: 780px) {
            html,
            body {
                height: auto;
                overflow: auto;
            }

            .report-container {
                height: auto;
            }

            .performance-assessment-view {
                overflow: visible;
            }

            .performance-analysis-layout {
                grid-template-columns: 1fr;
            }

            .performance-analysis-selector {
                grid-column: auto;
                display: flex;
            }
        }


        /* -------------------------------------------------- */
        /* Primary report navigation                           */
        /* -------------------------------------------------- */

        .primary-report-navigation {
            display: flex;
            flex-direction: column;
            height: 100%;
            min-height: 0;
        }

        .primary-report-tabs {
            display: flex;
            flex: 0 0 auto;
            gap: 8px;
            margin-bottom: 16px;
            padding: 8px;

            border: 1px solid var(--border);
            border-radius: var(--radius-md);
            background: var(--surface);
            box-shadow: var(--shadow-sm);
        }

        .primary-report-tab {
            min-height: 42px;
            padding: 9px 18px;

            border: 1px solid transparent;
            border-radius: var(--radius-sm);

            background: transparent;
            color: var(--text-secondary);

            cursor: pointer;
            font: inherit;
            font-size: 14px;
            font-weight: 700;
        }

        .primary-report-tab:hover {
            background: var(--primary-light);
            color: var(--primary);
        }

        .primary-report-tab.active {
            border-color: var(--primary);
            background: var(--primary);
            color: white;
        }

        .primary-report-tab:focus-visible {
            outline: 2px solid #4f86c6;
            outline-offset: 2px;
        }

        .primary-report-view {
            display: none;
            flex: 1 1 auto;
            min-height: 0;
            overflow-y: auto;
            padding-right: 8px;
        }

        .primary-report-view.active {
            display: block;
            animation: tabFadeIn 0.22s ease;
        }

        .primary-report-view .application-panel {
            height: auto;
            max-height: none;
            overflow: visible;
            padding-right: 0;
        }

        @media (max-width: 780px) {
            .primary-report-navigation {
                height: auto;
            }

            .primary-report-tabs {
                flex-direction: column;
            }

            .primary-report-view {
                overflow: visible;
            }
        }

        /* -------------------------------------------------- */
        /* Analysis comparison workspace                       */
        /* -------------------------------------------------- */

        .comparison-workspace {
            display: flex;
            height: 100%;
            min-height: 0;
            flex-direction: column;
            gap: 16px;
        }

        .comparison-workspace-header {
            flex: 0 0 auto;
            padding: 18px 22px;

            border: 1px solid var(--border);
            border-radius: var(--radius-lg);

            background: var(--surface);
            box-shadow: var(--shadow-sm);
        }

        .comparison-workspace-header h1 {
            margin: 0 0 5px;
            color: var(--primary);
            font-size: 24px;
        }

        .comparison-workspace-header > div > p:last-child {
            margin: 0;
            color: var(--text-secondary);
            font-size: 14px;
        }

        .comparison-workspace-eyebrow {
            margin: 0 0 4px;

            color: #527397;
            font-size: 11px;
            font-weight: 750;
            letter-spacing: 0.08em;
            text-transform: uppercase;
        }

        .comparison-panels {
            display: grid;
            flex: 1 1 auto;
            min-height: 0;

            grid-template-columns:
                minmax(0, 1fr)
                1px
                minmax(0, 1fr);

            gap: 16px;
        }

        .comparison-divider {
            width: 1px;
            min-height: 100%;
            background: var(--border);
        }

        .comparison-panel {
            display: flex;
            min-width: 0;
            min-height: 0;
            flex-direction: column;

            border: 1px solid var(--border);
            border-radius: var(--radius-lg);

            background: var(--surface);
            box-shadow: var(--shadow-sm);

            overflow: hidden;
        }

        .comparison-panel-header {
            display: flex;
            flex: 0 0 auto;
            align-items: flex-start;
            justify-content: space-between;
            gap: 18px;

            padding: 16px 18px;

            border-bottom: 1px solid var(--border);
            background: #f8fbff;
        }

        .comparison-panel-heading {
            min-width: 0;
            flex: 1 1 auto;
        }

        .comparison-panel-heading h2 {
            margin: 0 0 5px;
            font-size: 20px;
        }

        .comparison-panel-heading > p:last-child {
            max-width: 620px;
            margin: 0;

            color: var(--text-secondary);
            font-size: 12px;
            line-height: 1.45;
        }

        .comparison-panel-eyebrow {
            margin: 0 0 3px;

            color: #527397;
            font-size: 10px;
            font-weight: 750;
            letter-spacing: 0.08em;
            text-transform: uppercase;
        }

        .comparison-panel-controls {
            display: grid;
            min-width: 210px;

            grid-template-columns: minmax(150px, 1fr) 36px;
            gap: 6px;
            align-items: end;
        }

        .comparison-selector-label {
            grid-column: 1 / -1;

            color: var(--text-secondary);
            font-size: 10px;
            font-weight: 700;
            letter-spacing: 0.05em;
            text-transform: uppercase;
        }

        .comparison-view-selector {
            width: 100%;
            min-height: 36px;
            padding: 6px 9px;

            border: 1px solid #aabed2;
            border-radius: 8px;

            background: white;
            color: var(--primary);

            font: inherit;
            font-size: 12px;
            font-weight: 650;
        }

        .comparison-view-selector:focus-visible {
            outline: 2px solid #4f86c6;
            outline-offset: 2px;
        }

        .comparison-panel-control {
            display: grid;
            width: 36px;
            height: 36px;

            place-items: center;

            border: 1px solid #aabed2;
            border-radius: 8px;

            background: white;
            color: var(--primary);

            cursor: pointer;
            font: inherit;
        }

        .comparison-panel-control:hover {
            border-color: var(--primary);
            background: var(--primary-light);
        }

        .comparison-panel-control:focus-visible {
            outline: 2px solid #4f86c6;
            outline-offset: 2px;
        }

        .comparison-panel-content {
            flex: 1 1 auto;
            min-width: 0;
            min-height: 0;

            padding: 16px;

            overflow: auto;
            overscroll-behavior: contain;
            scrollbar-gutter: stable;
        }

        .comparison-analysis-view {
            display: none;
            min-width: 0;
        }

        .comparison-analysis-view.is-active {
            display: block;
            animation: tabFadeIn 0.22s ease;
        }

        .comparison-analysis-body {
            min-width: 0;
        }

        .comparison-analysis-body .application-panel {
            display: flex;
            height: auto;
            max-height: none;

            overflow: visible;
            padding-right: 0;
        }

        .comparison-analysis-body .workspace-panel {
            box-shadow: none;
        }

        .comparison-analysis-body .efficiency-table {
            width: max-content;
            min-width: 100%;
        }

        .comparison-analysis-body .metric-name-cell,
        .comparison-analysis-body
        .efficiency-table
        .metric-column-header {
            min-width: 255px;
        }

        .comparison-view-unavailable {
            padding: 24px;

            border: 1px dashed var(--border);
            border-radius: var(--radius-md);

            background: var(--surface-soft);
            color: var(--text-secondary);
            text-align: center;
        }

        .comparison-view-unavailable h3 {
            margin-top: 0;
        }

        /* Maximize/restore */

        .comparison-workspace[data-maximized-panel]
        .comparison-panels {
            grid-template-columns: minmax(0, 1fr);
        }

        .comparison-workspace[data-maximized-panel]
        .comparison-divider {
            display: none;
        }

        .comparison-panel.is-hidden-by-maximize {
            display: none;
        }

        .comparison-panel.is-maximized {
            width: 100%;
        }

        .comparison-panel.is-maximized
        .comparison-panel-control {
            border-color: var(--primary);
            background: var(--primary);
            color: white;
        }

        @media (max-width: 1050px) {
            .comparison-panels {
                grid-template-columns: 1fr;
                height: auto;
            }

            .comparison-divider {
                width: 100%;
                min-height: 1px;
                height: 1px;
            }

            .comparison-panel {
                min-height: 620px;
            }
        }

        @media (max-width: 720px) {
            html,
            body {
                height: auto;
                overflow: auto;
            }

            .report-container {
                height: auto;
            }

            .comparison-workspace {
                height: auto;
            }

            .comparison-panel-header {
                flex-direction: column;
            }

            .comparison-panel-controls {
                width: 100%;
                min-width: 0;
            }

            .comparison-panel-content {
                overflow: visible;
            }
        } 

        /* -------------------------------------------------- */
        /* Guided analysis navigation                          */
        /* -------------------------------------------------- */

        .guided-analysis-navigation {
            display: flex;
            height: 100%;
            min-height: 0;
            flex-direction: column;
            gap: 14px;
        }

        .guided-navigation-header {
            display: flex;
            flex: 0 0 auto;
            align-items: flex-end;
            justify-content: space-between;
            gap: 24px;
            padding: 17px 21px;

            border: 1px solid var(--border);
            border-radius: var(--radius-lg);

            background: var(--surface);
            box-shadow: var(--shadow-sm);
        }

        .guided-navigation-header h1 {
            margin: 0 0 5px;
            color: var(--primary);
            font-size: 24px;
        }

        .guided-navigation-header > div:first-child > p:last-child {
            margin: 0;
            color: var(--text-secondary);
            font-size: 13px;
        }

        .guided-navigation-eyebrow,
        .guided-secondary-eyebrow {
            margin: 0 0 3px;

            color: #527397;
            font-size: 10px;
            font-weight: 750;
            letter-spacing: .08em;
            text-transform: uppercase;
        }

        .guided-primary-tabs {
            position: relative;

            display: flex;
            flex: 0 0 auto;
            align-items: center;
            gap: 8px;

            padding: 5px 6px;

            border: 1px solid var(--border);
            border-radius: var(--radius-md);

            background: var(--surface);
            box-shadow: var(--shadow-sm);
        }

        .guided-primary-tab-list {
            display: flex;
            flex: 1 1 auto;
            flex-wrap: wrap;
            align-items: center;
            gap: 4px;

            min-width: 0;
        }

        .guided-primary-tab {
            min-height: 42px;
            padding: 8px 17px;

            border: 1px solid transparent;
            border-radius: 8px;

            background: transparent;
            color: var(--text-secondary);

            cursor: pointer;
            font: inherit;
            font-size: 13px;
            font-weight: 700;
        }

        .guided-primary-tab:hover {
            background: var(--primary-light);
            color: var(--primary);
        }

        .guided-primary-tab.is-active {
            border-color: var(--primary);
            background: var(--primary);
            color: white;
        }


        /* -------------------------------------------------- */
        /* Split analysis view                                 */
        /* -------------------------------------------------- */

        .guided-split-control {
            position: relative;

            flex: 0 0 auto;

            margin-left: auto;
        }

        .guided-split-button {
            display: grid;

            width: 34px;
            height: 34px;

            place-items: center;

            padding: 0;

            border: 1px solid #aabed2;
            border-radius: 7px;

            background: white;
            color: var(--primary);

            cursor: pointer;

            transition:
                border-color .15s ease,
                background .15s ease,
                color .15s ease,
                box-shadow .15s ease;
        }

        .guided-split-button svg {
            width: 19px;
            height: 19px;
        }

        .guided-split-button:hover {
            border-color: var(--primary);
            background: var(--primary-light);
        }

        .guided-split-button:focus-visible {
            outline: 2px solid #4f86c6;
            outline-offset: 2px;
        }

        .guided-split-control.has-secondary-view
        .guided-split-button {
            border-color: var(--primary);
            background: var(--primary);
            color: white;
        }

        .guided-split-menu {
            position: absolute;
            top: calc(100% + 7px);
            right: 0;
            z-index: 1200;

            width: 245px;

            padding: 6px;

            border: 1px solid var(--border);
            border-radius: 10px;

            background: white;
            box-shadow: 0 12px 30px rgba(20, 38, 63, .18);
        }

        .guided-split-menu[hidden] {
            display: none;
        }

        .guided-split-menu-title {
            padding: 5px 8px 7px;

            color: var(--text-secondary);

            font-size: 10px;
            font-weight: 750;
            letter-spacing: .06em;
            text-transform: uppercase;
        }

        /* -------------------------------------------------- */
        /* Export menu                                        */
        /* -------------------------------------------------- */

        .guided-export-control {
            position: relative;
            flex: 0 0 auto;
        }

        .guided-export-button {
            display: grid;

            width: 34px;
            height: 34px;

            place-items: center;

            padding: 0;

            border: 1px solid #aabed2;
            border-radius: 7px;

            background: white;
            color: var(--primary);

            cursor: pointer;

            transition:
                border-color .15s ease,
                background .15s ease,
                color .15s ease,
                box-shadow .15s ease;
        }

        .guided-export-button svg {
            width: 19px;
            height: 19px;
        }

        .guided-export-button:hover {
            border-color: var(--primary);
            background: var(--primary-light);
        }

        .guided-export-button:focus-visible {
            outline: 2px solid #4f86c6;
            outline-offset: 2px;
        }

        .guided-export-control.is-open
        .guided-export-button {
            border-color: var(--primary);
            background: var(--primary);
            color: white;
        }

        .guided-export-menu {
            position: absolute;
            top: calc(100% + 7px);
            right: 0;
            z-index: 1200;

            width: 280px;

            padding: 6px;

            border: 1px solid var(--border);
            border-radius: 10px;

            background: white;
            box-shadow: 0 12px 30px rgba(20, 38, 63, .18);
        }

        .guided-export-menu[hidden] {
            display: none;
        }

        .guided-export-menu-title {
            padding: 5px 8px 7px;

            color: var(--primary);
            font-size: 12px;
            font-weight: 800;
        }

        .guided-export-menu-group {
            padding: 5px 0;
        }

        .guided-export-menu-group
        + .guided-export-menu-group {
            margin-top: 4px;
            padding-top: 9px;

            border-top: 1px solid var(--border);
        }

        .guided-export-menu-group-title {
            padding: 3px 8px 5px;

            color: var(--text-secondary);
            font-size: 10px;
            font-weight: 750;
            letter-spacing: .07em;
            text-transform: uppercase;
        }

        .guided-export-option {
            display: block;

            width: 100%;
            padding: 8px 10px;

            border: 0;
            border-radius: 7px;

            background: transparent;
            color: #31465d;

            cursor: pointer;
            text-align: left;

            font: inherit;
            font-size: 12px;
            font-weight: 650;
        }

        .guided-export-option[hidden] {
            display: none;
        }

        .guided-export-option:hover {
            background: var(--primary-light);
            color: var(--primary);
        }

        .guided-export-option:focus-visible {
            outline: 2px solid #4f86c6;
            outline-offset: -2px;
        }

        /* -------------------------------------------------- */
        /* END Export menu                                    */
        /* -------------------------------------------------- */


        .guided-split-option {
            display: block;

            width: 100%;

            padding: 8px 10px;

            border: 0;
            border-radius: 6px;

            background: transparent;
            color: #31465d;

            cursor: pointer;

            font: inherit;
            font-size: 12px;
            font-weight: 650;
            text-align: left;
        }

        .guided-split-option:hover {
            background: var(--primary-light);
            color: var(--primary);
        }

        .guided-split-option.is-selected {
            background: #edf4fb;
            color: var(--primary);
            font-weight: 750;
        }

        .guided-split-option[hidden] {
            display: none;
        }

        /* -------------------------------------------------- */
        /* END Split analysis view                            */
        /* -------------------------------------------------- */

        .guided-analysis-stage {
            --comparison-panel-width: 48%;

            display: flex;
            flex: 1 1 auto;
            min-height: 0;
            gap: 8px;
        }

        .guided-primary-region {
            display: grid;
            flex: 1 1 auto;
            min-width: 0;
            min-height: 0;

            grid-template-columns:
                minmax(0, 1fr)
                180px;

            gap: 16px;
        }

        .guided-primary-region.has-drilldown {
            grid-template-columns:
                minmax(0, 1fr)
                minmax(320px, .85fr)
                180px;
        }

        .guided-primary-panel,
        .guided-drilldown-panel,
        .guided-comparison-region {
            min-width: 0;
            min-height: 0;

            border: 1px solid var(--border);
            border-radius: var(--radius-lg);

            background: var(--surface);
            box-shadow: var(--shadow-sm);

            overflow: auto;
            overscroll-behavior: contain;
            scrollbar-gutter: stable;
        }

        .guided-primary-panel {
            padding: 18px;
        }

        .guided-analysis-navigation:not(.is-runtime-primary)
        .guided-runtime-selector-region {
            display: none;
        }

        .guided-analysis-navigation:not(.is-runtime-primary)
        .guided-primary-region {
            grid-template-columns: minmax(0, 1fr);
        }

        .guided-drilldown-panel {
            display: none;
        }

        .guided-primary-region.has-drilldown
        .guided-drilldown-panel {
            display: flex;
            flex-direction: column;
        }

        .guided-secondary-header {
            display: flex;
            flex: 0 0 auto;
            align-items: flex-start;
            justify-content: space-between;
            gap: 15px;

            padding: 15px 17px;

            border-bottom: 1px solid var(--border);
            background: #f8fbff;
        }

        .guided-secondary-header h2 {
            margin: 0 0 4px;
            font-size: 19px;
        }

        .guided-secondary-header > div > p:last-child {
            margin: 0;
            color: var(--text-secondary);
            font-size: 11px;
        }

        .guided-secondary-close {
            display: grid;
            width: 33px;
            height: 33px;
            flex: 0 0 33px;

            place-items: center;

            border: 1px solid #aabed2;
            border-radius: 8px;

            background: white;
            color: var(--primary);

            cursor: pointer;
            font: inherit;
            font-size: 21px;
        }

        .guided-secondary-content {
            min-width: 0;
            min-height: 0;
            padding: 16px;
            overflow: auto;
        }

        .guided-comparison-region {
            display: flex;

            flex: 0 0 var(--comparison-panel-width);

            min-width: 0;
            flex-direction: column;
        }

        .guided-comparison-region[hidden] {
            display: none;
        }

        .guided-analysis-view {
            min-width: 0;
        }

        .guided-analysis-view .application-panel {
            display: flex;
            height: auto;
            max-height: none;
            overflow: visible;
            padding-right: 0;
        }

        .guided-analysis-view .workspace-panel {
            box-shadow: none;
        }

        .guided-analysis-view .efficiency-table {
            width: max-content;
            min-width: 100%;
        }

        .guided-analysis-view .metric-name-cell,
        .guided-analysis-view
        .efficiency-table
        .metric-column-header {
            width: clamp(190px, 30%, 275px);
            min-width: 190px;
        }

        .guided-primary-panel,
        .guided-secondary-content {
            overflow: auto;
        }

        .guided-analysis-view {
            width: 100%;
            min-width: 0;
        }

        .guided-analysis-view .metric-table-card {
            width: 100%;
            max-width: 100%;
            overflow-x: auto;
        }

        .guided-analysis-view .efficiency-table {
            width: max-content;
            min-width: 100%;
        }


        .guided-view-unavailable {
            padding: 24px;

            border: 1px dashed var(--border);
            border-radius: var(--radius-md);

            background: var(--surface-soft);
            color: var(--text-secondary);
            text-align: center;
        }

        @media (max-width: 850px) {
            html {
                height: auto;
                overflow-x: hidden;
                overflow-y: auto;
            }

            body {
                min-height: 100%;
                height: auto;
                overflow-x: hidden;
                overflow-y: visible;
            }

            .report-container,
            .guided-analysis-navigation {
                height: auto;
            }

            .guided-navigation-header {
                align-items: stretch;
                flex-direction: column;
            }

            .guided-primary-tabs {
                flex-direction: column;
            }

            .guided-analysis-stage {
                flex-direction: column;
            }

            .guided-primary-region,
            .guided-primary-region.has-drilldown {
                grid-template-columns: minmax(0, 1fr);
            }

            .guided-primary-region.has-drilldown
            .guided-primary-panel,
            .guided-primary-region.has-drilldown
            .guided-panel-divider,
            .guided-primary-region.has-drilldown
            .guided-drilldown-panel,
            .guided-primary-region.has-drilldown
            .guided-runtime-selector-region {
                grid-column: 1;
                grid-row: auto;
            }

            .guided-primary-region.has-drilldown
            .guided-panel-divider {
                display: none;
            }            

            .guided-drilldown-selector {
                display: grid;
                grid-template-columns:
                    repeat(auto-fit, minmax(180px, 1fr));
            }

            .guided-primary-panel,
            .guided-drilldown-panel,
            .guided-comparison-region {
                overflow: visible;
            }

            .guided-comparison-region {
                flex-basis: auto;
            }
        }

        @media (max-width: 1450px) {
            .guided-analysis-view .metric-name-cell,
            .guided-analysis-view
            .efficiency-table
            .metric-column-header {
                width: 185px;
                min-width: 185px;
            }

            .guided-analysis-view
            .efficiency-table th,
            .guided-analysis-view
            .efficiency-table td {
                padding-left: 8px;
                padding-right: 8px;
            }
        }


        /* -------------------------------------------------- */
        /* Compact layout for analysis-focused use             */
        /* -------------------------------------------------- */

        /* Main report header */

        .report-header {
            padding: 9px 20px;
        }

        .report-header-content {
            max-width: 1760px;
        }

        .report-header h1 {
            margin: 0;
            font-size: 22px;
            line-height: 1.15;
        }

        .report-brand {
            margin-bottom: 1px;
            font-size: 10px;
            line-height: 1.2;
        }

        .subtitle {
            margin-top: 2px;
            font-size: 12px;
            line-height: 1.25;
        }

        /* Compact Overview */
        .guided-analysis-view
        .application-panel
        > .workspace-panel:first-child
        > h2 {
            display: none;
        }

        .guided-analysis-view
        .application-panel
        > .workspace-panel:first-child {
            padding: 12px 14px;
        }

        .guided-analysis-view
        .application-panel
        > .workspace-panel:first-child
        .report-section {
            margin-bottom: 16px;
        }

        .guided-analysis-view
        .application-panel
        > .workspace-panel:first-child
        .report-section:last-child {
            margin-bottom: 0;
        }

        .guided-analysis-view
        .application-panel
        .report-section h3,
        .guided-analysis-view
        .application-panel
        > .workspace-panel
        > h2 {
            margin: 4px 0 10px;
            color: var(--primary);
            font-size: 18px;
            line-height: 1.25;
            font-weight: 700;
        }

        .guided-analysis-view
        .application-panel
        > .workspace-panel:first-child
        .metric-table {
            margin-top: 6px;
        }

        .guided-analysis-view
        .application-panel
        > .workspace-panel:first-child
        .metric-table th,
        .guided-analysis-view
        .application-panel
        > .workspace-panel:first-child
        .metric-table td {
            padding: 7px 10px;
        }


        /* Main report area */

        .report-container {
            width: min(1760px, calc(100% - 20px));
            margin: 12px auto 18px;
        }


        /* Guided-workflow header */

        .guided-analysis-navigation {
            gap: 8px;
        }

        .guided-navigation-header {
            min-height: 0;
            padding: 7px 12px;
            gap: 12px;
        }

        .guided-navigation-header h1 {
            margin: 0 0 1px;
            font-size: 17px;
            line-height: 1.2;
        }

        .guided-navigation-header > div:first-child > p:last-child {
            margin: 0;
            font-size: 11px;
            line-height: 1.25;
        }

        .guided-navigation-eyebrow {
            display: none;
        }

        /* Primary navigation tabs */

        .guided-primary-tabs {
            gap: 3px;
            padding: 3px 5px;
        }

        .guided-primary-tab-list {
            gap: 3px;
        }

        .guided-primary-tab {
            min-height: 34px;
            padding: 6px 14px;
            font-size: 13px;
            line-height: 1.2;
        }

        .guided-split-button {
            width: 34px;
            height: 34px;
        }

        .guided-split-button svg {
            width: 18px;
            height: 18px;
        }

        /* Analysis regions */

        .guided-analysis-stage {
            gap: 10px;
        }

        .guided-primary-region {
            display: grid;

            grid-template-columns: minmax(0, 1fr);
            grid-template-rows:
                auto
                minmax(0, 1fr);

            grid-template-areas:
                "selector"
                "primary";

            gap: 6px;

            min-width: 0;
            min-height: 0;
        }

        .guided-primary-region.has-drilldown {
            --primary-panel-width: 52%;

            grid-template-columns:
                minmax(360px, var(--primary-panel-width))
                8px
                minmax(360px, 1fr);

            grid-template-rows:
                auto
                minmax(0, 1fr);

            grid-template-areas:
                "selector divider detail"
                "primary  divider detail";

            gap: 6px 8px;
        }

        /***********************************/
        /*     Assign the grid areas       */    
        /***********************************/
        .guided-runtime-selector-region {
            grid-area: selector;

            min-width: 0;
        }

        .guided-primary-panel {
            grid-area: primary;
        }

        .guided-primary-region.has-drilldown
        .guided-panel-divider {
            grid-area: divider;
        }

        .guided-primary-region.has-drilldown
        .guided-drilldown-panel {
            grid-area: detail;
        }

        /***********************************/
        /*   END Assign the grid areas     */    
        /***********************************/

        .guided-panel-divider {
            display: none;
        }

        .guided-primary-region.has-drilldown
        .guided-panel-divider {
            display: block;
        }

        .guided-panel-divider {
            position: relative;

            width: 8px;
            min-width: 8px;

            border-radius: 5px;
            background: #d9e3ee;

            cursor: col-resize;
            touch-action: none;
        }

        .guided-panel-divider::after {
            position: absolute;
            top: 50%;
            left: 50%;

            width: 3px;
            height: 42px;

            border-radius: 3px;
            background: #7893ae;

            content: "";
            transform: translate(-50%, -50%);
        }

        .guided-panel-divider:hover,
        .guided-panel-divider.is-dragging {
            background: #bdd1e5;
        }

        .guided-panel-divider:focus-visible {
            outline: 2px solid #4f86c6;
            outline-offset: 2px;
        }

        .guided-comparison-divider {
            position: relative;

            display: block;

            width: 8px;
            min-width: 8px;

            border-radius: 5px;

            background: #d9e3ee;

            cursor: col-resize;
            touch-action: none;
        }

        .guided-comparison-divider[hidden] {
            display: none;
        }

        .guided-comparison-divider::after {
            position: absolute;

            top: 50%;
            left: 50%;

            width: 3px;
            height: 42px;

            border-radius: 3px;

            background: #7893ae;

            content: "";

            transform: translate(-50%, -50%);
        }

        .guided-comparison-divider:hover,
        .guided-comparison-divider.is-dragging {
            background: #bdd1e5;
        }

        .guided-comparison-divider:focus-visible {
            outline: 2px solid #4f86c6;
            outline-offset: 2px;
        }

        .guided-primary-panel {
            padding: 10px;
        }


        /* Runtime and resource selector */

        /* -------------------------------------------------- */
        /* Runtime analysis selector                          */
        /* -------------------------------------------------- */

        .guided-runtime-selector-region {
            display: flex;
            align-items: center;
            justify-content: flex-start;

            width: 100%;
            min-width: 0;

            padding: 4px 8px;

            border-left: 4px solid #4f86c6;
            border-radius: 6px;

            background: #edf5fd;

            overflow: visible;
        }

        .guided-drilldown-selector {
            display: inline-flex;
            flex-direction: row;
            flex-wrap: nowrap;
            align-items: center;

            gap: 10px;

            width: auto;
            min-height: 34px;

            padding: 4px 7px;

            border: 1px solid #b8cde2;
            border-radius: 7px;

            background: #eaf3fc;
        }

        .guided-runtime-selector-label {
            flex: 0 0 auto;

            padding: 0 3px;

            color: #315b85;

            font-size: 12px;
            font-weight: 750;

            white-space: nowrap;
        }

        .guided-drilldown-buttons {
            display: inline-flex;
            flex-direction: row;
            flex-wrap: nowrap;
            align-items: center;

            gap: 0;

            overflow: hidden;

            border: 1px solid #8faccc;
            border-radius: 6px;

            background: white;
        }

        .guided-drilldown-button {
            flex: 0 0 auto;

            min-height: 28px;
            padding: 4px 12px;

            border: 0;
            border-right: 1px solid #b8cde2;
            border-radius: 0;

            background: white;
            color: #244d78;

            cursor: pointer;

            font: inherit;
            font-size: 11px;
            font-weight: 700;

            white-space: nowrap;
        }

        .guided-drilldown-button:last-child {
            border-right: 0;
        }

        .guided-drilldown-button:hover {
            background: #dcecf9;
        }

        .guided-drilldown-button.is-selected {
            background: #315f8d;
            color: white;
        }


        /* Detailed-analysis header */

        .guided-secondary-header {
            padding: 9px 12px;
            gap: 10px;
        }

        .guided-secondary-eyebrow {
            display: none;
        }

        .guided-secondary-header h2 {
            margin-bottom: 2px;
            font-size: 17px;
        }

        .guided-secondary-header > div > p:last-child {
            font-size: 10px;
            line-height: 1.35;
        }

        .guided-secondary-close {
            width: 29px;
            height: 29px;
            flex-basis: 29px;
            font-size: 18px;
        }

        .guided-secondary-content {
            padding: 10px;
        }


        /* Efficiency interpretation: compact reference panel */

        .efficiency-scale-panel {
            margin-bottom: 12px;
            padding: 11px 14px;
        }

        .efficiency-scale-header h3 {
            margin-bottom: 1px;
            font-size: 15px;
        }

        .efficiency-scale-header p {
            font-size: 11px;
        }

        .efficiency-gradient-container {
            margin: 12px 6px 17px;
        }

        .efficiency-gradient {
            height: 10px;
        }

        .efficiency-gradient-markers {
            height: 13px;
            margin-top: 3px;
            font-size: 10px;
        }

        .scale-range {
            padding: 6px 10px;
            font-size: 11px;
        }

        .scale-range span {
            font-size: 10px;
        }

        .efficiency-above-reference {
            margin-top: 8px;
            font-size: 10px;
            line-height: 1.35;
        }

        .efficiency-scale-guidance {
            margin-top: 8px;
            padding-top: 7px;
            font-size: 11px;
            line-height: 1.4;
        }


        /* Give more visual priority to tables and analysis */

        .metric-table-card {
            margin-bottom: 12px;
        }

        .efficiency-table th,
        .efficiency-table td {
            padding-top: 4px;
            padding-bottom: 4px;
        }

        .metric-info-panel {
            min-height: 0;
            margin-bottom: 12px;
            padding: 13px 16px;
        }

        .metric-info-panel::before {
            margin-bottom: 4px;
            font-size: 10px;
        }

        .metric-info-panel h3 {
            margin-bottom: 4px;
            font-size: 16px;
        }

        .metric-info-panel p {
            margin: 4px 0;
            font-size: 12px;
            line-height: 1.5;
        }

        .observation-box {
            margin-bottom: 12px;
            padding: 13px 16px;
        }

        .observation-box h3 {
            margin-bottom: 7px;
            font-size: 16px;
        }

        .performance-interpretation p,
        .scaling-interpretation p {
            font-size: 14px;
            line-height: 1.55;
        }

        /* -------------------------------------------------- */
        /* Final responsive guided-layout overrides            */
        /* Must remain after the compact desktop rules.         */
        /* -------------------------------------------------- */

        /* Medium width:
        primary analysis above detailed analysis;
        selector remains on the right. */
        @media (max-width: 1250px) {
            .guided-primary-region.has-drilldown {
                grid-template-columns: minmax(0, 1fr);

                grid-template-areas:
                    "selector"
                    "primary"
                    "detail";

                gap: 8px;
            }

            .guided-primary-region.has-drilldown
            .guided-runtime-selector-region {
                grid-area: selector;

                width: 100%;
                min-width: 0;
            }

            .guided-primary-region.has-drilldown
            .guided-primary-panel {
                grid-area: primary;

                width: 100%;
                min-width: 0;
            }

            .guided-primary-region.has-drilldown
            .guided-drilldown-panel {
                grid-area: detail;

                width: 100%;
                min-width: 0;
                min-height: 520px;
            }

            .guided-primary-region.has-drilldown
            .guided-panel-divider {
                display: none;
            }
        }


        /* -------------------------------------------------- */
        /* Final responsive guided-layout overrides            */
        /* Must remain after the compact desktop rules.        */
        /* -------------------------------------------------- */

        /* Narrow width:
        selector, primary analysis and detailed analysis are stacked. */
        @media (max-width: 850px) {
            .guided-primary-region,
            .guided-primary-region.has-drilldown {
                grid-template-columns: minmax(0, 1fr);

                grid-template-areas:
                    "selector"
                    "primary"
                    "detail";

                gap: 10px;
            }

            .guided-primary-region
            .guided-primary-panel,
            .guided-primary-region.has-drilldown
            .guided-primary-panel {
                grid-area: primary;
                width: 100%;
                min-width: 0;
            }

            .guided-primary-region.has-drilldown
            .guided-drilldown-panel {
                grid-area: detail;
                width: 100%;
                min-width: 0;
                min-height: 520px;
            }

            .guided-primary-region
            .guided-runtime-selector-region,
            .guided-primary-region.has-drilldown
            .guided-runtime-selector-region {
                grid-area: selector;
                width: 100%;
                min-width: 0;
                order: initial;
            }

            .guided-primary-region.has-drilldown
            .guided-panel-divider {
                display: none;
            }

            .guided-drilldown-selector {
                display: inline-flex;
                flex-direction: row;
                flex-wrap: nowrap;
                align-items: center;
                gap: 8px;

                width: auto;
                max-width: 100%;
            }

            .guided-drilldown-buttons {
                display: inline-flex;
                flex-direction: row;
                flex-wrap: nowrap;
            }

            .guided-primary-tabs {
                flex-direction: row;
                flex-wrap: nowrap;
                align-items: flex-start;
            }

            .guided-primary-tab-list {
                display: grid;

                flex: 1 1 auto;

                grid-template-columns:
                    repeat(auto-fit, minmax(170px, 1fr));

                gap: 5px;
            }

            .guided-primary-tab {
                width: 100%;
                min-height: 38px;

                padding: 7px 10px;

                font-size: 13px;
            }

            .guided-split-control {
                flex: 0 0 auto;
            }

            .guided-export-control {
                flex: 0 0 auto;
            }

            .guided-split-button {
                width: 38px;
                height: 38px;
            }

            .guided-split-button svg {
                width: 20px;
                height: 20px;
            }

            .guided-export-button {
                width: 38px;
                height: 38px;
            }

            .guided-export-button svg {
                width: 20px;
                height: 20px;
            }

            .guided-split-menu {
                position: fixed;

                top: auto;
                right: 12px;
                bottom: 12px;
                left: 12px;

                width: auto;

                max-height: min(420px, calc(100vh - 24px));
                overflow-y: auto;
            }

            .guided-export-menu {
                position: fixed;

                top: auto;
                right: 12px;
                bottom: 12px;
                left: 12px;

                width: auto;

                max-height: min(420px, calc(100vh - 24px));
                overflow-y: auto;
            }

            .guided-comparison-divider {
                display: none !important;
            }

            /* Mobile readability */

            .report-header {
                padding: 11px 14px;
            }

            .report-header h1 {
                font-size: 21px;
            }

            .report-brand {
                font-size: 10px;
            }

            .subtitle {
                font-size: 12px;
            }

            .guided-navigation-header h1 {
                font-size: 19px;
            }

            .guided-navigation-header > div:first-child > p:last-child {
                font-size: 13px;
                line-height: 1.4;
            }

            .guided-primary-tab {
                min-height: 38px;
                padding: 7px 10px;
                font-size: 13px;
            }

            .trace-header-note {
                font-size: 13px;
            }

            .efficiency-table {
                font-size: 15px;
            }

            .efficiency-table thead th {
                font-size: 14px;
            }

            .metric-name-cell {
                font-size: 15px;
                line-height: 1.35;
            }

            .metric-value {
                width: 96px;
                min-width: 96px;
                height: 31px;
                font-size: 14px;
            }

            .execution-domain-title {
                font-size: 13px;
            }

            .performance-interpretation p,
            .scaling-interpretation p {
                font-size: 13px;
                line-height: 1.5;
            }

            .observation-box {
                font-size: 14px;
            }

            .analysis-scope-note {
                font-size: 13px;
            }

            /* Mobile table scrolling */

            .efficiency-table-wrapper,
            .metric-table-card {
                overflow-x: auto;
                overflow-y: visible;

                -webkit-overflow-scrolling: touch;
                touch-action: pan-x pan-y pinch-zoom;
            }

            /* Let the page handle vertical scrolling */

            .guided-primary-panel,
            .guided-secondary-content,
            .guided-drilldown-panel,
            .guided-comparison-region {
                overflow: visible;
            }


        }

        @page {
            size: A4;
            margin: 16mm 18mm 16mm 18mm;
        }

        @media print {

            body.basicanalysis-print-mode {
                display: block !important;
                overflow: visible !important;
                background: white !important;
            }
        
            body.basicanalysis-print-mode
            .print-analysis-summary
            .analysis-summary-title {
                display: none !important;
            }

            body.basicanalysis-print-mode {
                font-size: 11pt;
                line-height: 1.45;
            }

            body.basicanalysis-print-mode p,
            body.basicanalysis-print-mode li,
            body.basicanalysis-print-mode
            .print-section-description,
            body.basicanalysis-print-mode
            .print-analysis-summary,
            body.basicanalysis-print-mode
            .metric-reference-value,
            body.basicanalysis-print-mode
            .metric-reference-causes {
                font-size: 11pt !important;
                line-height: 1.45 !important;
            }

            body.basicanalysis-print-mode h1 {
                font-size: 20pt !important;
                line-height: 1.2;
            }

            body.basicanalysis-print-mode h2 {
                font-size: 16pt !important;
                line-height: 1.25;
            }

            body.basicanalysis-print-mode h3 {
                font-size: 12pt !important;
                line-height: 1.3;
            }

            body.basicanalysis-print-mode
            > *:not(.basicanalysis-printable-report) {
                display: none !important;
            }

            body.basicanalysis-print-mode
            .basicanalysis-printable-report {
                display: block !important;
            }

            .basicanalysis-printable-report[hidden] {
                display: none;
            }

            body.basicanalysis-print-mode
            .print-export-style {
                width: max-content;
                max-width: 100%;
                overflow: visible;
            }

            body.basicanalysis-print-mode
            .print-export-style
            .efficiency-table-wrapper {
                width: max-content;
                max-width: 100%;
                overflow: visible;
            }

            body.basicanalysis-print-mode
            .print-export-style
            .efficiency-table {
                width: max-content !important;
                min-width: 0 !important;
            }

            body.basicanalysis-print-mode
            .print-export-style
            .metric-name-cell,
            body.basicanalysis-print-mode
            .print-export-style
            .metric-column-header {
                width: auto !important;
                min-width: 0 !important;
                white-space: nowrap;
            }

            body.basicanalysis-print-mode,
            body.basicanalysis-print-mode * {
                -webkit-print-color-adjust: exact !important;
                print-color-adjust: exact !important;
            }


            /* -------------------------------------------------- */
            /* Printable diagnosis as report prose                */
            /* -------------------------------------------------- */

            body.basicanalysis-print-mode
            .print-analysis-summary {
                margin: 14px 0 20px !important;
                padding: 0 !important;

                border: 0 !important;
                background: transparent !important;
                box-shadow: none !important;
            }


            /*
            * build_analysis_summary_html() creates its own
            * observation-box inside print-analysis-summary.
            */
            body.basicanalysis-print-mode
            .print-analysis-summary
            .observation-box {
                margin: 0 !important;
                padding: 0 !important;

                max-width: none !important;

                border: 0 !important;
                border-left: 0 !important;
                border-radius: 0 !important;

                background: transparent !important;
                background-image: none !important;

                box-shadow: none !important;
            }


            /*
            * Do not show the UI-oriented "Automatic diagnosis"
            * heading in the printable report.
            */
            body.basicanalysis-print-mode
            .print-analysis-summary
            .observation-box > h3:first-child {
                display: none !important;
            }


            body.basicanalysis-print-mode
            .print-analysis-summary h3,
            body.basicanalysis-print-mode
            .print-analysis-summary h4 {
                margin: 12px 0 5px !important;

                color: #17365d;

                font-size: 12pt !important;
                font-weight: 700;
                line-height: 1.3;
            }


            body.basicanalysis-print-mode
            .print-analysis-summary p {
                margin: 0 0 10px !important;

                color: #26394d;

                font-size: 11pt !important;
                line-height: 1.45 !important;
            }

            /* -------------------------------------------------- */
            /* END Printable diagnosis as report prose            */
            /* -------------------------------------------------- */


            body.basicanalysis-print-mode
            .print-analysis-summary h3,
            body.basicanalysis-print-mode
            .print-analysis-summary h4 {
                margin: 12px 0 5px !important;

                color: #17365d;

                font-size: 12pt !important;
                font-weight: 700;
                line-height: 1.3;
            }

            body.basicanalysis-print-mode
            .print-analysis-summary h3:first-of-type,
            body.basicanalysis-print-mode
            .print-analysis-summary h4:first-of-type {
                margin-top: 0 !important;
            }


            body.basicanalysis-print-mode
            .print-analysis-summary p {
                margin: 0 0 10px !important;

                font-size: 11pt !important;
                line-height: 1.45 !important;

                color: #26394d;
            }

            body.basicanalysis-print-mode
            .execution-domain-analysis-group {
                margin-top: 14px;
                padding: 0 !important;

                border: 0 !important;
                background: transparent !important;
            }

            .print-execution-domain-label {
                margin: 10px 0 4px;
                padding: 4px 8px;

                color: #17365d;
                font-size: 12px;
                font-weight: 800;
                letter-spacing: .08em;
            }

            .print-execution-domains
            .print-analysis-summary
            .execution-domain-analysis-group
            + .execution-domain-analysis-group {
                margin-top: 16px;
                padding-top: 12px;
                border-top: 1px solid #dce3ec;
            }


            body.basicanalysis-print-mode
            .trace-table th,
            body.basicanalysis-print-mode
            .trace-table td {
                white-space: normal !important;

                overflow-wrap: anywhere;
                word-break: normal;

                font-size: 10px;
                padding: 6px 7px;
            }


            body.basicanalysis-print-mode
            .print-overview-block
            .metric-table {
                width: max-content !important;
                max-width: 100% !important;

                min-width: 0 !important;

                display: table !important;

                overflow: visible !important;
            }

            body.basicanalysis-print-mode
            .trace-header-note
            + .metric-table {
                width: max-content !important;
                max-width: 100% !important;

                min-width: 0 !important;

                display: table !important;
                overflow: visible !important;
            }

            body.basicanalysis-print-mode
            .trace-header-note
            + .metric-table {
                border-radius: 0 !important;
                border-left: 0 !important;
                border-right: 0 !important;

                box-shadow: none !important;
            }

            body.basicanalysis-print-mode
            .trace-header-note {
                font-size: 10pt !important;
                line-height: 1.35;
            }

            body.basicanalysis-print-mode
            .efficiency-scale-panel p,
            body.basicanalysis-print-mode
            .efficiency-scale-compact-labels {
                font-size: 10pt !important;
                line-height: 1.35;
            }

            /* -------------------------------------------------- */
            /* Only for GPU traces                                */
            /* -------------------------------------------------- */

            body.basicanalysis-print-mode
            .trace-config-mpi_gpu {
                width: 100% !important;
            }

            body.basicanalysis-print-mode
            .trace-config-mpi_gpu {
                width: 100% !important;
            }

            /* -------------------------------------------------- */
            /* Only for second column Trace config table          */
            /* -------------------------------------------------- */

            body.basicanalysis-print-mode
            .trace-config-table th:nth-child(2),
            body.basicanalysis-print-mode
            .trace-config-table td:nth-child(2) {
                width: 180px !important;
                min-width: 180px !important;
                max-width: 180px !important;

                white-space: normal !important;

                overflow-wrap: anywhere;
                word-break: break-word;
            }

            body.basicanalysis-print-mode
            .trace-config-table td:nth-child(2) code {
                white-space: normal !important;

                overflow-wrap: anywhere;
                word-break: break-word;

                font-size: 9.5pt !important;
            }

            /* -------------------------------------------------- */
            /* Printable Trace Configuration                      */
            /* -------------------------------------------------- */

            body.basicanalysis-print-mode
            .trace-config-table {
                display: table !important;

                width: max-content !important;
                max-width: 100% !important;
                min-width: 0 !important;

                table-layout: auto !important;

                overflow: visible !important;
                white-space: normal !important;

                font-size: 10pt !important;
            }


            body.basicanalysis-print-mode
            .trace-config-table th,
            body.basicanalysis-print-mode
            .trace-config-table td {
                width: auto !important;

                padding: 5px 8px !important;

                white-space: nowrap !important;

                font-size: 10pt !important;
                line-height: 1.3;
            }


            /* -------------------------------------------------- */
            /* Compact printable efficiency tables                */
            /* -------------------------------------------------- */

            body.basicanalysis-print-mode
            .print-metric-results {
                margin-bottom: 12px !important;

                border: 1px solid #dce3ec !important;
                border-radius: 4px !important;

                box-shadow: none !important;
            }


            body.basicanalysis-print-mode
            .print-metric-results
            .efficiency-table-wrapper {
                width: 100%;
                overflow: visible !important;
            }


            body.basicanalysis-print-mode
            .print-metric-results
            .efficiency-table {
                width: 100% !important;

                font-size: 10pt !important;

                border-collapse: separate;
                border-spacing: 0;
            }


            /*
            * Reduce row height.
            */
            body.basicanalysis-print-mode
            .print-metric-results
            .efficiency-table th,
            body.basicanalysis-print-mode
            .print-metric-results
            .efficiency-table td {
                padding-top: 4px !important;
                padding-bottom: 4px !important;

                padding-left: 7px !important;
                padding-right: 7px !important;

                border-bottom: 1px solid #e2e7ed !important;
            }

            /*
            * Preserve metric hierarchy in the first column.
            * This must override the generic printable TD padding above.
            */
            body.basicanalysis-print-mode
            .print-metric-results
            .efficiency-table
            td.metric-name-cell {
                padding-left: calc(
                    8px + (var(--metric-depth, 0) * 14px)
                ) !important;
            }

            /*
            * Column headers.
            */
            body.basicanalysis-print-mode
            .print-metric-results
            .efficiency-table thead th {
                position: static !important;

                font-size: 9.5pt !important;
                line-height: 1.25;

                background: #edf3f9;
            }


            /*
            * Metric names.
            */
            body.basicanalysis-print-mode
            .print-metric-results
            .metric-name-cell {
                position: static !important;

                min-width: 0 !important;

                font-size: 10pt !important;
                line-height: 1.3;

                box-shadow: none !important;
            }

            /*
            * Value columns should not reserve the large
            * interactive-report width.
            */
            body.basicanalysis-print-mode
            .print-metric-results
            .metric-value-cell {
                min-width: 0 !important;

                padding-left: 5px !important;
                padding-right: 5px !important;
            }


            /*
            * Compact colored efficiency cells.
            */
            body.basicanalysis-print-mode
            .print-metric-results
            .metric-value {
                width: auto !important;
                min-width: 62px !important;
                height: 25px !important;

                padding: 2px 6px !important;

                border-radius: 2px !important;

                font-size: 9.5pt !important;
                line-height: 1.15;

                box-shadow: none !important;
            }

            /* -------------------------------------------------- */
            /* Justify the report prose                           */
            /* -------------------------------------------------- */

            body.basicanalysis-print-mode
            .print-section-description,

            body.basicanalysis-print-mode
            .print-analysis-summary p,

            body.basicanalysis-print-mode
            .metric-reference-value,

            body.basicanalysis-print-mode
            .metric-reference-causes li,

            body.basicanalysis-print-mode
            .analysis-scope-note p {

                text-align: justify;
                text-justify: inter-word;
            }

            /* -------------------------------------------------- */
            /* Add space before every new analytical section      */
            /* -------------------------------------------------- */
            
            body.basicanalysis-print-mode
            .print-metric-section {
                margin-top: 30px;
            }

            body.basicanalysis-print-mode
            .print-metric-section:first-of-type {
                margin-top: 0;
            }

            body.basicanalysis-print-mode
            .print-section-header {
                margin-bottom: 14px;
            }

            /*
            * Compact colored efficiency cells.
            */
            body.basicanalysis-print-mode
            .efficiency-scale-panel {
                margin-top: 24px !important;
                margin-bottom: 30px !important;
            }

            /* -------------------------------------------------- */
            /* Metric Scope ordinary report text      */
            /* -------------------------------------------------- */
            body.basicanalysis-print-mode
            .analysis-scope-note {
                margin: 16px 0 20px !important;
                padding: 0 !important;

                border: 0 !important;
                border-left: 0 !important;
                border-radius: 0 !important;

                background: transparent !important;
                box-shadow: none !important;

                color: #26394d !important;
            }

            body.basicanalysis-print-mode
            .analysis-scope-note h3 {
                margin: 0 0 6px !important;

                color: #17365d !important;

                font-size: 12pt !important;
                font-weight: 700;
                letter-spacing: normal !important;
            }

            body.basicanalysis-print-mode
            .analysis-scope-note p {
                margin: 0 0 8px !important;

                color: #26394d !important;

                font-size: 11pt !important;
                line-height: 1.45 !important;

                text-align: justify;
            }

            /* -------------------------------------------------- */
            /* Appendix                                           */
            /* -------------------------------------------------- */

            body.basicanalysis-print-mode
            .print-appendix {
                break-before: page;
                page-break-before: always;
            }    


        }        

        /* -------------------------------------------------- */
        /* Printable metric reference                         */
        /* -------------------------------------------------- */

        .metric-reference-list {
            display: block;
        }

        .metric-reference-card {
            margin: 0 0 14px;
            padding: 11px 13px;

            border: 1px solid #d7e0ea;
            border-radius: 8px;

            background: #ffffff;

            break-inside: avoid;
            page-break-inside: avoid;
        }

        .metric-reference-name {
            margin: 0 0 9px;

            color: #17365d;

            font-size: 15px;
            font-weight: 750;
        }

        .metric-reference-field {
            margin-top: 8px;
        }

        .metric-reference-field:first-of-type {
            margin-top: 0;
        }

        .metric-reference-label {
            margin-bottom: 3px;

            color: #53697f;

            font-size: 10px;
            font-weight: 750;

            letter-spacing: .04em;
            text-transform: uppercase;
        }

        .metric-reference-value {
            color: #26394d;

            font-size: 11px;
            line-height: 1.45;
        }

        .metric-reference-formula {
            padding: 6px 8px;

            border-radius: 5px;

            background: #f3f6f9;

            font-family:
                "SFMono-Regular",
                Consolas,
                "Liberation Mono",
                monospace;

            font-size: 10.5px;
        }

        .metric-reference-causes {
            margin: 4px 0 0;
            padding-left: 20px;

            color: #26394d;

            font-size: 11px;
            line-height: 1.4;
        }

        .metric-reference-causes li {
            margin-bottom: 2px;
        }

        body.basicanalysis-print-mode
        .metric-reference-name {
            font-size: 12pt !important;
            line-height: 1.3;
        }

        body.basicanalysis-print-mode
        .metric-reference-label {
            font-size: 9pt !important;
            line-height: 1.25;
        }

        body.basicanalysis-print-mode
        .metric-reference-value,
        body.basicanalysis-print-mode
        .metric-reference-causes {
            font-size: 11pt !important;
            line-height: 1.45;
        }

        body.basicanalysis-print-mode
        .metric-reference-formula {
            font-size: 10.5pt !important;
            line-height: 1.35;

            font-family:
                "SFMono-Regular",
                Consolas,
                "Liberation Mono",
                monospace;
        }

        /* -------------------------------------------------- */
        /* Scaling model                                      */
        /* -------------------------------------------------- */

        .scaling-model-panel {
            margin-bottom: 16px;
            padding: 14px 16px;

            border: 1px solid var(--border);
            border-radius: var(--radius-md);

            background: #f8fbff;
            box-shadow: var(--shadow-sm);
        }

        .scaling-model-header h3 {
            margin: 0 0 3px;
            color: var(--primary);
            font-size: 16px;
        }

        .scaling-model-header p {
            margin: 0 0 12px;
            color: var(--text-secondary);
            font-size: 12px;
        }

        .scaling-model-grid {
            display: grid;
            grid-template-columns: repeat(3, minmax(140px, 1fr));
            gap: 10px;
        }

        .scaling-model-item {
            padding: 9px 11px;

            border: 1px solid var(--border);
            border-radius: 8px;

            background: white;
        }

        .scaling-model-label {
            display: block;
            margin-bottom: 2px;

            color: var(--text-secondary);
            font-size: 10px;
            font-weight: 700;
            letter-spacing: .05em;
            text-transform: uppercase;
        }

        .scaling-model-item strong {
            color: var(--primary);
            font-size: 14px;
        }

        .scaling-model-warning {
            margin-top: 12px;
            padding: 9px 11px;

            border-left: 4px solid #c79a20;
            border-radius: 6px;

            background: #fff8e7;
            color: #5c4b1c;

            font-size: 12px;
        }

        @media (max-width: 700px) {
            .scaling-model-grid {
                grid-template-columns: 1fr;
            }
        }

</style>

        <script>
        const WORKSPACE_STATE_KEY = "basicAnalysis.workspace.v1";

        function readWorkspaceState() {
            try {
                return JSON.parse(localStorage.getItem(WORKSPACE_STATE_KEY)) || {};
            } catch (error) {
                return {};
            }
        }

        function writeWorkspaceState(update) {
            const state = Object.assign({}, readWorkspaceState(), update);
            try {
                localStorage.setItem(WORKSPACE_STATE_KEY, JSON.stringify(state));
            } catch (error) {
                // The report remains fully usable when storage is unavailable.
            }
        }

        function updateContextControls() {
            const layout = document.querySelector(".analysis-layout");
            const collapseButton = document.getElementById("sidebar-collapse-button");
            const maximizeButton = document.getElementById("sidebar-maximize-button");
            if (!layout) return;

            const collapsed = layout.classList.contains("sidebar-collapsed");
            const maximized = layout.classList.contains("context-maximized");

            if (collapseButton) {
                collapseButton.setAttribute("aria-expanded", collapsed ? "false" : "true");
                collapseButton.setAttribute(
                    "aria-label",
                    collapsed
                        ? "Show global performance overview"
                        : "Hide global performance overview"
                );
                collapseButton.title = collapsed
                    ? "Show global performance overview"
                    : "Hide global performance overview";
            }

            if (maximizeButton) {
                maximizeButton.setAttribute("aria-pressed", maximized ? "true" : "false");
                maximizeButton.setAttribute(
                    "aria-label",
                    maximized
                        ? "Restore split view"
                        : "Maximize global performance overview"
                );
                maximizeButton.title = maximized
                    ? "Restore split view"
                    : "Maximize global performance overview";
                const icon = maximizeButton.querySelector(".sidebar-maximize-icon");
                if (icon) icon.textContent = maximized ? "🗗" : "⛶";
            }
        }

        function toggleAnalysisSidebar(forceCollapsed, persist = true) {
            const layout = document.querySelector(".analysis-layout");
            if (!layout) return;

            const collapsed = typeof forceCollapsed === "boolean"
                ? forceCollapsed
                : !layout.classList.contains("sidebar-collapsed");

            if (collapsed) {
                layout.classList.remove("context-maximized");
            }
            layout.classList.toggle("sidebar-collapsed", collapsed);
            updateContextControls();

            if (persist) {
                writeWorkspaceState({
                    sidebarCollapsed: collapsed,
                    contextMaximized: false
                });
            }
        }

        function toggleContextMaximized(forceMaximized, persist = true) {
            const layout = document.querySelector(".analysis-layout");
            if (!layout || window.innerWidth <= 980) return;

            const maximized = typeof forceMaximized === "boolean"
                ? forceMaximized
                : !layout.classList.contains("context-maximized");

            if (maximized) {
                layout.classList.remove("sidebar-collapsed");
            }
            layout.classList.toggle("context-maximized", maximized);
            updateContextControls();

            const sidebar = document.querySelector(".analysis-sidebar");
            if (sidebar) sidebar.scrollTop = 0;

            if (persist) {
                writeWorkspaceState({
                    contextMaximized: maximized,
                    sidebarCollapsed: false
                });
            }
        }

        function showSidebarView(viewId, button, persist = true) {
            const views = document.getElementsByClassName("sidebar-view");
            for (let i = 0; i < views.length; i++) {
                views[i].classList.remove("active");
                views[i].setAttribute("hidden", "hidden");
            }

            const buttons = document.getElementsByClassName("sidebar-tab");
            for (let i = 0; i < buttons.length; i++) {
                buttons[i].classList.remove("active");
                buttons[i].setAttribute("aria-selected", "false");
                buttons[i].setAttribute("tabindex", "-1");
            }

            const view = document.getElementById(viewId);
            if (view) {
                view.classList.add("active");
                view.removeAttribute("hidden");
            }

            if (button) {
                button.classList.add("active");
                button.setAttribute("aria-selected", "true");
                button.setAttribute("tabindex", "0");
            }

            const sidebar = document.querySelector(".analysis-sidebar");
            if (sidebar) sidebar.scrollTop = 0;

            if (persist) writeWorkspaceState({ sidebarView: viewId });
        }

        function initializeSidebarTabs(savedViewId) {
            let activeButton = null;
            if (savedViewId) {
                activeButton = document.querySelector(
                    '.sidebar-tab[aria-controls="' + savedViewId + '"]'
                );
            }
            if (!activeButton) {
                activeButton = document.querySelector(".sidebar-tab.active");
            }
            if (activeButton) {
                showSidebarView(
                    activeButton.getAttribute("aria-controls"),
                    activeButton,
                    false
                );
            }

            const tabList = document.querySelector(".sidebar-tabs");
            if (!tabList) return;

            tabList.addEventListener("keydown", function(event) {
                if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") {
                    return;
                }

                const tabs = Array.from(
                    tabList.querySelectorAll(".sidebar-tab")
                );
                const currentIndex = tabs.indexOf(document.activeElement);
                if (currentIndex < 0) return;

                event.preventDefault();
                const direction = event.key === "ArrowRight" ? 1 : -1;
                const nextIndex = (currentIndex + direction + tabs.length) % tabs.length;
                const nextTab = tabs[nextIndex];

                nextTab.focus();
                showSidebarView(nextTab.getAttribute("aria-controls"), nextTab);
            });
        }

        function scrollSidebarToElement(elementId) {
            const sidebar = document.querySelector(".analysis-sidebar");
            const target = document.getElementById(elementId);
            if (!sidebar || !target) return;

            const sidebarRect = sidebar.getBoundingClientRect();
            const targetRect = target.getBoundingClientRect();
            const stickyHeader = sidebar.querySelector(".sidebar-header");
            const headerHeight = stickyHeader ? stickyHeader.offsetHeight : 0;
            const destination = sidebar.scrollTop
                + (targetRect.top - sidebarRect.top)
                - headerHeight
                - 12;

            sidebar.scrollTo({
                top: Math.max(0, destination),
                behavior: "smooth"
            });
        }

        function selectAnalysisView(viewId, button, persist = true) {
            const layout = document.querySelector(".analysis-layout");

            // A runtime component or execution domain opens a detailed analysis
            // in the right panel. If the global context is maximized, restore
            // the split layout automatically before showing the selected view.
            const sidebar = document.querySelector(".analysis-sidebar");
            const preservedSidebarScroll = sidebar ? sidebar.scrollTop : 0;

            if (layout && layout.classList.contains("context-maximized")) {
                toggleContextMaximized(false, false);
                if (sidebar) {
                    // Restoring split view changes the panel width but should not
                    // send the user back to the beginning of the runtime model.
                    window.requestAnimationFrame(function() {
                        sidebar.scrollTop = preservedSidebarScroll;
                    });
                }
            }

            const placeholder = document.getElementById("component-placeholder");
            if (placeholder) placeholder.style.display = "none";

            const views = document.getElementsByClassName("component-analysis-view");
            for (let i = 0; i < views.length; i++) {
                views[i].classList.remove("active");
                views[i].setAttribute("hidden", "hidden");
            }

            const buttons = document.getElementsByClassName("analysis-nav-button");
            for (let i = 0; i < buttons.length; i++) {
                buttons[i].classList.remove("active");
                buttons[i].setAttribute("aria-pressed", "false");
            }

            const view = document.getElementById(viewId);
            if (view) {
                view.classList.add("active");
                view.removeAttribute("hidden");
            }

            if (button) {
                button.classList.add("active");
                button.setAttribute("aria-pressed", "true");
            }

            const panel = document.querySelector(".component-panel");
            if (panel) panel.scrollTop = 0;

            if (persist) {
                writeWorkspaceState({
                    analysisView: viewId,
                    contextMaximized: false,
                    sidebarCollapsed: false
                });
            }
        }

        function showDetailView(viewId, button) {
            const views = document.getElementsByClassName("detail-view");
            for (let i = 0; i < views.length; i++) {
                views[i].classList.remove("active");
            }

            const buttons = document.getElementsByClassName("detail-tab-button");
            for (let i = 0; i < buttons.length; i++) {
                buttons[i].classList.remove("active");
            }

            const view = document.getElementById(viewId);
            if (view) view.classList.add("active");
            if (button) button.classList.add("active");
        }

        function initializeStickyHeader() {
            const header = document.querySelector(".report-header");
            if (!header) return;

            const scrollPanels = document.querySelectorAll(
                ".analysis-sidebar, .component-panel"
            );

            function updateHeaderShadow() {
                let isScrolled = window.scrollY > 0;

                for (let i = 0; i < scrollPanels.length; i++) {
                    if (scrollPanels[i].scrollTop > 0) {
                        isScrolled = true;
                        break;
                    }
                }

                header.classList.toggle("is-scrolled", isScrolled);
            }

            updateHeaderShadow();
            window.addEventListener("scroll", updateHeaderShadow, { passive: true });

            for (let i = 0; i < scrollPanels.length; i++) {
                scrollPanels[i].addEventListener(
                    "scroll",
                    updateHeaderShadow,
                    { passive: true }
                );
            }
        }

        function showPrimaryReportView(viewId, button) {
            const views = document.getElementsByClassName(
                "primary-report-view"
            );

            for (let index = 0; index < views.length; index++) {
                views[index].classList.remove("active");
                views[index].setAttribute("hidden", "hidden");
            }

            const buttons = document.getElementsByClassName(
                "primary-report-tab"
            );

            for (let index = 0; index < buttons.length; index++) {
                buttons[index].classList.remove("active");
                buttons[index].setAttribute(
                    "aria-selected",
                    "false"
                );
            }

            const selectedView = document.getElementById(
                viewId
            );

            if (selectedView) {
                selectedView.classList.add("active");
                selectedView.removeAttribute("hidden");
                selectedView.scrollTop = 0;
            }

            if (button) {
                button.classList.add("active");
                button.setAttribute(
                    "aria-selected",
                    "true"
                );
            }
        }

        function initializeWorkspace() {
            initializeStickyHeader();

            window.addEventListener("resize", function() {
                const layout = document.querySelector(".analysis-layout");
                if (!layout) return;
                if (window.innerWidth <= 980) {
                    layout.classList.remove("sidebar-collapsed");
                    layout.classList.remove("context-maximized");
                }
                updateContextControls();
            });

            const state = readWorkspaceState();
            initializeSidebarTabs(state.sidebarView);

            if (window.innerWidth > 980) {
                if (state.contextMaximized === true) {
                    toggleContextMaximized(true, false);
                } else if (state.sidebarCollapsed === true) {
                    toggleAnalysisSidebar(true, false);
                } else {
                    updateContextControls();
                }
            } else {
                updateContextControls();
            }

            if (state.analysisView) {
                const savedView = document.getElementById(state.analysisView);
                const savedButton = document.querySelector(
                    '.analysis-nav-button[data-analysis-target="' +
                    state.analysisView + '"]'
                );
                if (savedView && savedButton) {
                    selectAnalysisView(state.analysisView, savedButton, false);
                }
            }

            const firstButton = document.querySelector(".detail-tab-button");
            if (firstButton) {
                showDetailView(firstButton.dataset.target, firstButton);
                return;
            }

            const firstView = document.querySelector(".detail-view");
            if (firstView) firstView.classList.add("active");
        }

        function selectMetric(sectionId, metricKey) {
            const infoDict = window["metricInfo_" + sectionId];
            if (!infoDict || !infoDict[metricKey]) {
                return;
            }

            const info = infoDict[metricKey];
            const thresholds = info.thresholds;

            document.getElementById(sectionId + "-info-title").innerText = info.title;
            document.getElementById(sectionId + "-info-type").innerText = info.type;
            document.getElementById(sectionId + "-info-meaning").innerText = info.meaning;
            document.getElementById(sectionId + "-info-interpretation").innerText =
                "Values below " + thresholds.attention + "%: "
                + info.low
                + " Values above " + thresholds.reference + "%: "
                + info.above100;

            document.getElementById(sectionId + "-info-action").innerText =
                "Next diagnostic step: " + info.action;

            const buttons = document.querySelectorAll(
                "#" + sectionId + " .metric-tree-button"
            );

            for (let i = 0; i < buttons.length; i++) {
                buttons[i].classList.remove("active");
            }

            if (event && event.target) {
                event.target.classList.add("active");
            }
        }

        
        function selectMetricCell(
            trigger,
            sectionId,
            metricKey,
            metricLabel,
            traceLabel,
            value
        ) {
            const infoDict = window[
                "metricInfo_" + sectionId
            ];

            if (!infoDict || !infoDict[metricKey]) {
                return;
            }

            const info = infoDict[metricKey];
            const thresholds = info.thresholds;

            const valueText =
                value === null || value === undefined
                    ? "Non-Avail"
                    : value.toFixed(2) + "%";

            let interpretation = "";

            if (
                value === null
                || value === undefined
            ) {
                interpretation =
                    "Metric is not available for this trace or configuration.";
            } else if (
                value > thresholds.reference
            ) {
                interpretation =
                    info.above100;
            } else if (
                value < thresholds.critical
            ) {
                interpretation =
                    "Critical value. " + info.low;
            } else if (
                value < thresholds.attention
            ) {
                interpretation =
                    "Requires attention. " + info.low;
            } else {
                interpretation =
                    "This component is probably not the dominant bottleneck.";
            }

            document.getElementById(
                "metric-details-title"
            ).innerText = info.title;

            document.getElementById(
                "metric-details-type"
            ).innerText = info.type;

            document.getElementById(
                "metric-details-trace"
            ).innerText = traceLabel;

            document.getElementById(
                "metric-details-value"
            ).innerText = valueText;

            document.getElementById(
                "metric-details-definition"
            ).innerText = info.meaning;

            document.getElementById(
                "metric-details-interpretation"
            ).innerText = interpretation;

            document.getElementById(
                "metric-details-action"
            ).innerText = info.action;

            const modal = document.getElementById(
                "metric-details-modal"
            );

            if (!modal) {
                return;
            }

            modal.hidden = false;
            modal.setAttribute(
                "aria-hidden",
                "false"
            );

            document.body.classList.add(
                "metric-details-open"
            );

            const closeButton = modal.querySelector(
                ".metric-details-close"
            );

            if (closeButton) {
                closeButton.focus();
            }
        }        

        function closeMetricDetails() {
            const modal = document.getElementById(
                "metric-details-modal"
            );

            if (!modal) {
                return;
            }

            modal.hidden = true;
            modal.setAttribute(
                "aria-hidden",
                "true"
            );

            document.body.classList.remove(
                "metric-details-open"
            );
        }

        /* Close the dialog with ESC */
        document.addEventListener(
            "keydown",
            function(event) {
                if (event.key === "Escape") {
                    closeMetricDetails();
                }
            }
        );


        function copyCommand(cmd) {
            navigator.clipboard.writeText(cmd).then(function() {
                alert("Paraver command copied to clipboard.");
            });
        }

        </script>
        </head>

        <body onload="initializeWorkspace()">

        <header class="report-header">
            <div class="report-header-content">
                <div>
                    <div class="report-brand">BasicAnalysis</div>
                    <h1>Performance Report</h1>
                </div>

            </div>
        </header>

        <main class="report-container">""" + """

        {workspace_html}

    """ + """</main>

        <div
            id="metric-details-modal"
            class="metric-details-modal"
            hidden
            aria-hidden="true"
        >
            <div
                class="metric-details-backdrop"
                onclick="closeMetricDetails()"
            ></div>

            <section
                class="metric-details-dialog"
                role="dialog"
                aria-modal="true"
                aria-labelledby="metric-details-title"
            >
                <button
                    type="button"
                    class="metric-details-close"
                    aria-label="Close metric details"
                    onclick="closeMetricDetails()"
                >
                    ×
                </button>

                <div class="metric-details-eyebrow">
                    Metric details
                </div>

                <h2 id="metric-details-title">
                    Metric details
                </h2>

                <div class="metric-details-context">
                    <span id="metric-details-type"></span>
                    <span id="metric-details-trace"></span>
                    <span id="metric-details-value"></span>
                </div>

                <div class="metric-details-section">
                    <h3>Definition</h3>
                    <p id="metric-details-definition"></p>
                </div>

                <div class="metric-details-section">
                    <h3>Interpretation</h3>
                    <p id="metric-details-interpretation"></p>
                </div>

                <div class="metric-details-section metric-details-next-step">
                    <h3>Next diagnostic step</h3>
                    <p id="metric-details-action"></p>
                </div>
            </section>
        </div>

        <section
            class="basicanalysis-printable-report"
            data-basicanalysis-printable-report
            hidden
        >
            {printable_report_html}
        </section>

        </body>
        </html>
        """

    return(document.replace('{workspace_html}', workspace_html,)
         .replace('{printable_report_html}',printable_report_html,)
      )



def plot_basicanalysis_interactive_report(metrics_result, analysis_result,
                                            report, report_model,
                                            trace_list, trace_processes,
                                            trace_tasks, trace_threads,
                                            trace_mode, cmdl_args):
    """Generate unified interactive HTML report."""

    output_html = os.path.join(os.getcwd(), "basicanalysis_interactive_report.html")

    other_metrics = metrics_result["other_metrics"]

    model = _report_execution_model(trace_mode, trace_list, metrics_result)
    report_traces = report.get("traces", [])

    trace_labels = [
        _report_trace_label(trace_info)
        for trace_info in report_traces
    ]    

    trace_header_note = _build_trace_header_note(
        report
    )

    trace_column_description = (
        _build_trace_column_description(
            report
        )
    )

    overview_html = _build_overview_table_html(
        other_metrics,
        trace_list,
        trace_labels,
    )    

    mod_factors = metrics_result.get("mod_factors", {})
    hybrid_factors = metrics_result.get("hybrid_factors", {})
    hyb_comm_omp_factors = metrics_result.get("hyb_comm_omp_factors", {})

    inner_model = _inner_model_name(trace_mode, trace_list)
    hybrid_metric_info = _build_hybrid_metric_info(inner_model)
    global_metric_info = _build_global_metric_info(
        is_hybrid=model["is_hybrid"]
    )


    if model["has_cuda"]:
        global_keys = [
            "global_eff",
            "parallel_eff",
            "load_balance",
            "comm_eff",
            "comp_scale",
        ]

        global_tree_kind = "global_gpu"

    else:
        global_keys = [
            "global_eff",
            "parallel_eff",
            "load_balance",
            "comm_eff",
            "comp_scale",
            "ipc_scale",
            "inst_scale",
            "freq_scale",
        ]

        global_tree_kind = "global"


    global_filtered_keys = []
    for key in global_keys:
        if key not in mod_factors:
            continue

        for trace in trace_list:
            if _clean_value(_read_metric(mod_factors, key, trace)) is not None:
                global_filtered_keys.append(key)
                break

    global_sources = {key: mod_factors for key in global_filtered_keys}

    global_html = _build_metric_tree_heatmap_section(
        metric_keys=global_filtered_keys,
        metric_info=global_metric_info,
        metric_sources=global_sources,
        trace_list=trace_list,
        trace_labels=trace_labels,
        title="Global Efficiency Metrics",
        section_id="global",
        tree_kind=global_tree_kind,
        trace_header_note=trace_header_note,
        trace_column_description=trace_column_description,
    )


    # ---- Hybrid model tab
    if metrics_result["kind"] == "hybrid":
        hybrid_keys = list(HYBRID_ORDER)

        if inner_model == "OpenMP" and cmdl_args.hyb_mpiomp:
            hybrid_keys += OMP_COMM_ORDER

        hybrid_sources = {}
        for key in HYBRID_ORDER:
            hybrid_sources[key] = hybrid_factors
        for key in OMP_COMM_ORDER:
            hybrid_sources[key] = hyb_comm_omp_factors
        hybrid_html = _build_metric_tree_heatmap_section(
            metric_keys=hybrid_keys,
            metric_info=hybrid_metric_info,
            metric_sources=hybrid_sources,
            trace_list=trace_list,
            trace_labels=trace_labels,
            title="Parallel Programming Model: MPI + {}".format(inner_model),
            section_id="hybrid",
            tree_kind="hybrid",
            trace_header_note=trace_header_note,
            trace_column_description=trace_column_description,
            runtime=inner_model,
            runtime_family=inner_model.lower(),
        )
    else:
        hybrid_html = "<p>Parallel programming model metrics are not available for simple traces.</p>"

    # ---- MPI+GPU execution-domain and device-runtime metrics
    host_html = "<p>Host execution-domain metrics are only available for MPI+GPU traces.</p>"
    device_html = "<p>Device execution-domain metrics are only available for MPI+GPU traces.</p>"

    execution_domains_html = ""

    if (
        metrics_result["kind"] == "hybrid"
        and trace_mode[trace_list[0]] in ("Detailed+MPI+CUDA","Detailed+MPI+HIP")
    ):
        host_factors = metrics_result["host_factors"]
        device_factors = metrics_result["device_factors"]

        host_keys = [
            "host_global_eff",
            "host_parallel_eff",
            "mpi_parallel_eff",
            "mpi_load_balance",
            "mpi_comm_eff",
            "serial_eff",
            "transfer_eff",
            "dev_offload_eff",
            "host_comp_scale",
            "ipc_scale",
            "inst_scale",
            "freq_scale",
        ]
        device_keys = [
            "dev_global_eff",
            "dev_parallel_eff",
            "dev_load_balance",
            "dev_comm_eff",
            "dev_orches_eff",
            "dev_comp_scale",
        ]

        host_sources = {}
        for key in host_keys:
            if key in ("ipc_scale", "inst_scale", "freq_scale"):
                host_sources[key] = mod_factors
            else:
                host_sources[key] = host_factors

        device_sources = {key: device_factors for key in device_keys}

        host_filtered_keys = []
        for key in host_keys:
            source = host_sources[key]
            if any(
                _clean_value(_read_metric(source, key, trace)) is not None
                for trace in trace_list
            ):
                host_filtered_keys.append(key)

        device_filtered_keys = []
        for key in device_keys:
            source = device_sources[key]
            if any(
                _clean_value(_read_metric(source, key, trace)) is not None
                for trace in trace_list
            ):
                device_filtered_keys.append(key)

        host_html = _build_metric_tree_heatmap_section(
            metric_keys=host_filtered_keys,
            metric_info=TALP_METRIC_INFO,
            metric_sources=host_sources,
            trace_list=trace_list,
            trace_labels=trace_labels,
            title="Host Efficiency Metrics",
            section_id="host",
            tree_kind="host",
            trace_header_note=trace_header_note,
            trace_column_description=trace_column_description,
        )

        device_html = _build_metric_tree_heatmap_section(
            metric_keys=device_filtered_keys,
            metric_info=TALP_METRIC_INFO,
            metric_sources=device_sources,
            trace_list=trace_list,
            trace_labels=trace_labels,
            title="Device Efficiency Metrics",
            section_id="device",
            tree_kind="device",
            trace_header_note=trace_header_note,
            trace_column_description=trace_column_description,
        )

        execution_domains_html = _build_execution_domains_section(
            host_metric_keys=host_filtered_keys,
            device_metric_keys=device_filtered_keys,
            host_sources=host_sources,
            device_sources=device_sources,
            trace_list=trace_list,
            trace_labels=trace_labels,
            trace_header_note=trace_header_note,
            trace_column_description=trace_column_description,
        )        

    # ---- OpenMP runtime-specific efficiency metrics
    openmp_filtered_keys = []

    if (
        model["has_omp"]
        and "omp_talp_factors" in metrics_result
    ):
        omp_talp_factors = metrics_result["omp_talp_factors"]

        openmp_filtered_keys = []
        for key in OPENMP_ORDER:
            if key not in omp_talp_factors:
                continue

            for trace in trace_list:
                if _clean_value(_read_metric(omp_talp_factors, key, trace)) is not None:
                    openmp_filtered_keys.append(key)
                    break

        if openmp_filtered_keys:
            openmp_sources = {
                key: omp_talp_factors for key in openmp_filtered_keys
            }

            openmp_metrics_html = _build_metric_tree_heatmap_section(
                metric_keys=openmp_filtered_keys,
                metric_info=OPENMP_METRIC_INFO,
                metric_sources=openmp_sources,
                trace_list=trace_list,
                trace_labels=trace_labels,
                title="OpenMP Efficiency Metrics",
                section_id="openmp",
                tree_kind="openmp",
                trace_header_note=trace_header_note,
                trace_column_description=trace_column_description,
            )
            openmp_html = (
                openmp_metrics_html
                + _build_openmp_runtime_scope_note(
                    is_hybrid=model["is_hybrid"]
                )
            )
        else:
            openmp_html = (
                "<p>OpenMP efficiency metrics are not available for this trace configuration.</p>"
            )
            
    else:
        openmp_html = (
            "<p>OpenMP runtime-specific efficiency metrics are not available "
            "for this trace configuration.</p>"
        )

   
    trace_configuration_section = report_model.get_section(
        "trace-configuration"
    )

    if trace_configuration_section is None:
        raise ValueError(
            "The semantic report does not contain the "
            "'trace-configuration' section."
        )

    trace_config_html = render_trace_configuration(
        trace_configuration_section
    )


    overview_section = report_model.get_section(
        "overview"
    )

    assessment_section = report_model.get_section(
        "performance-assessment"
    )

    runtime_section = report_model.get_section(
        "runtime-analysis"
    )

    resource_section = report_model.get_section(
        "resource-analysis"
    )

    scalability_section = report_model.get_section(
        "scalability-analysis"
    )


    if overview_section is None:
        raise ValueError(
            "The semantic report does not contain the "
            "'overview' section."
        )

    if assessment_section is None:
        raise ValueError(
            "The semantic report does not contain the "
            "'performance-assessment' section."
        )

    if runtime_section is None:
        raise ValueError(
            "The semantic report does not contain the "
            "'runtime-analysis' section."
        )

    resources_html = _build_resources_table_html(report)


    # --------------------------------------------------
    # Computation Scalability analysis
    # --------------------------------------------------

    computation_scalability_html = ""

    if scalability_section is not None:
        scalability_data = scalability_section.payload
        scalability_analysis = scalability_data.analysis

        scaling_model_html = _build_scaling_model_html(
            scalability_data.scaling_info
        )

        scalability_keys = [
            metric.metric_id
            for metric in scalability_analysis.metrics
        ]

        scalability_sources = {
            metric_key: mod_factors
            for metric_key in scalability_keys
        }

        if scalability_keys:
            scalability_metrics_html = (
                _build_metric_tree_heatmap_section(
                    metric_keys=scalability_keys,
                    metric_info=SIMPLE_METRIC_INFO,
                    metric_sources=scalability_sources,
                    trace_list=trace_list,
                    trace_labels=trace_labels,
                    title=scalability_analysis.title,
                    section_id="computation-scalability",
                    tree_kind="scalability",
                    trace_header_note=trace_header_note,
                    trace_column_description=trace_column_description,
                )
            )

            scalability_scope_html = """
            <div class="analysis-scope-note">
                <h3>Analysis scope</h3>
                <p>{description}</p>
            </div>
            """.format(
                description=html.escape(
                    scalability_analysis.description
                )
            )

            computation_scalability_html = (
                scaling_model_html
                + scalability_metrics_html
                + scalability_scope_html
            )



    # --------------------------------------------------
    # Step 1: build semantic report views
    # --------------------------------------------------

    overview_view_html = _build_overview_view(
        trace_config_html=trace_config_html,
        trace_header_note=trace_header_note,
        overview_html=overview_html,
        resources_html=resources_html,
        global_html=global_html,
    )

    runtime_model_views = _build_parallel_runtime_model_views(
        model=model,
        mod_factors=mod_factors,
        trace_list=trace_list,
        trace_labels=trace_labels,
        trace_header_note=trace_header_note,
        trace_column_description=trace_column_description,
        hybrid_html=hybrid_html,
        inner_model=inner_model,
    )

    # --------------------------------------------------
    # Step 3: build MPI runtime-specific component analysis
    # --------------------------------------------------
    mpi_html = ""

    if model["has_mpi"]:
        if model["is_hybrid"]:
            mpi_keys = [
                "mpi_parallel_eff",
                "mpi_load_balance",
                "mpi_comm_eff",
                "serial_eff",
                "transfer_eff",
            ]
            mpi_metric_info = hybrid_metric_info
            mpi_sources = {
                key: hybrid_factors for key in mpi_keys
            }
            mpi_tree_kind = "runtime_mpi"
        else:
            mpi_keys = [
                "parallel_eff",
                "load_balance",
                "comm_eff",
                "serial_eff",
                "transfer_eff",
            ]
            mpi_metric_info = SIMPLE_METRIC_INFO
            mpi_sources = {
                key: mod_factors for key in mpi_keys
            }
            mpi_tree_kind = "runtime_global"

        mpi_filtered_keys = []
        for key in mpi_keys:
            source = mpi_sources[key]
            if any(
                _clean_value(_read_metric(source, key, trace)) is not None
                for trace in trace_list
            ):
                mpi_filtered_keys.append(key)

        if mpi_filtered_keys:
            mpi_html = _build_metric_tree_heatmap_section(
                metric_keys=mpi_filtered_keys,
                metric_info=mpi_metric_info,
                metric_sources=mpi_sources,
                trace_list=trace_list,
                trace_labels=trace_labels,
                title="MPI Efficiency Metrics",
                section_id="mpi-runtime",
                tree_kind=mpi_tree_kind,
                trace_header_note=trace_header_note,
                trace_column_description=trace_column_description,
            )

    # --------------------------------------------------
    # Step 3 revision: accelerator runtime contribution
    # --------------------------------------------------
    accelerator_html = ""

    if model["is_hybrid"] and model["has_cuda"]:
        accelerator_keys = [
            "omp_parallel_eff",
            "omp_load_balance",
            "omp_comm_eff",
        ]
        accelerator_sources = {
            key: hybrid_factors for key in accelerator_keys
        }
        accelerator_filtered_keys = [
            key for key in accelerator_keys
            if any(
                _clean_value(
                    _read_metric(accelerator_sources[key], key, trace)
                ) is not None
                for trace in trace_list
            )
        ]

        if accelerator_filtered_keys:
            accelerator_scope_note = (
                "<div class='analysis-scope-note'>"
                "<h3>Metric scope</h3>"
                "<p>These metrics quantify the {0} contribution within the "
                "MPI+{0} multiplicative runtime model. Use the Execution "
                "Domains view to inspect complementary Host and Device "
                "evidence and determine where the accelerator-related "
                "inefficiency manifests.</p></div>"
            ).format(
                html.escape(inner_model)
            )

            accelerator_metrics_html = _build_metric_tree_heatmap_section(
                metric_keys=accelerator_filtered_keys,
                metric_info=hybrid_metric_info,
                metric_sources=accelerator_sources,
                trace_list=trace_list,
                trace_labels=trace_labels,
                title="{} Runtime Contribution Metrics".format(inner_model),
                section_id="accelerator-runtime",
                tree_kind="runtime_inner",
                trace_header_note=trace_header_note,
                trace_column_description=trace_column_description,
                runtime=inner_model,
                runtime_family=inner_model.lower(),
            )

            accelerator_html = (
                accelerator_metrics_html + accelerator_scope_note
            )

    analysis_views = _build_component_views(
        model=model,
        inner_model=inner_model,
        mpi_html=mpi_html,
        accelerator_html=accelerator_html,
        openmp_filtered_keys=openmp_filtered_keys,
        openmp_html=openmp_html,
        host_html=host_html,
        device_html=device_html,
    )

    component_html = {
        "mpi-runtime": mpi_html,
        "openmp-runtime": openmp_html,
        "accelerator-runtime": accelerator_html,
        "host-analysis": host_html,
        "device-analysis": device_html,
    }

    if runtime_model_views:
        parallel_runtime_model_html = runtime_model_views[0]["html"]
    else:
        parallel_runtime_model_html = (
            "<p>No Parallel Runtime Model is available.</p>"
        )

    rendered_analysis_html = {
        "overview": overview_view_html,

        "parallel-runtime-model": (
            parallel_runtime_model_html
        ),

        "execution-domains": (
            execution_domains_html
        ),

        "computation-scalability": (
            computation_scalability_html
        ),

        "mpi-runtime": mpi_html,
        "openmp-runtime": openmp_html,
        "accelerator-runtime": accelerator_html,

        "host-analysis": host_html,
        "device-analysis": device_html,
    }

    analysis_catalogue = build_analysis_catalogue(
        overview_section=overview_section,
        runtime_section=runtime_section,
        resource_section=resource_section,
        scalability_section=scalability_section,
        rendered_html=rendered_analysis_html,
    )

    if USE_GUIDED_ANALYSIS_NAVIGATION:
        workspace_html = render_analysis_navigation(
            catalogue=analysis_catalogue,
        )
    else:
        performance_assessment_html = (
            render_performance_assessment(
                assessment_section=assessment_section,
                runtime_section=runtime_section,
                resource_section=resource_section,
                parallel_runtime_model_html=(
                    parallel_runtime_model_html
                ),
                component_html=component_html,
            )
        )

        workspace_html = _build_primary_report_navigation(
            overview_html=overview_view_html,
            performance_assessment_html=(
                performance_assessment_html
            ),
        )

    printable_report_body = (
        _build_basicanalysis_printable_report_html(
            metrics_result=metrics_result,
            analysis_result=analysis_result,
            report=report,
            trace_list=trace_list,
            trace_processes=trace_processes,
            trace_tasks=trace_tasks,
            trace_threads=trace_threads,
            trace_mode=trace_mode,
            cmdl_args=cmdl_args,
            standalone=False,
        )
    )

    html_content = _build_interactive_report_document(
        workspace_html=workspace_html, printable_report_html=printable_report_body,
    )

    with open(output_html, "w") as output_file:
        output_file.write(html_content)

    print("Interactive report written to {}".format(output_html))

    return output_html



def _build_single_runtime_metric_info(runtime_name):
    """Build runtime-labelled metadata for a single-runtime POP model.

    The underlying metric identifiers remain the standard simple-model keys,
    but the printable report explicitly identifies the active runtime so that
    pure MPI, OpenMP, CUDA, and other single-runtime reports use the same
    analytical vocabulary as composed-runtime reports.
    """
    metric_info = METRIC_PROVIDER.clone(SIMPLE_METRIC_INFO)

    runtime_name = runtime_name or "Parallel runtime"

    metric_info["parallel_eff"]["label"] = (
        "{} Parallel efficiency".format(runtime_name)
    )
    metric_info["parallel_eff"]["short_label"] = (
        "{} PE".format(runtime_name)
    )
    metric_info["parallel_eff"]["type"] = (
        "{} runtime metric".format(runtime_name)
    )

    metric_info["load_balance"]["label"] = (
        "  -- {} Load balance".format(runtime_name)
    )
    metric_info["load_balance"]["short_label"] = (
        "{} LB".format(runtime_name)
    )
    metric_info["load_balance"]["type"] = (
        "{} runtime sub-metric".format(runtime_name)
    )

    metric_info["comm_eff"]["label"] = (
        "  -- {} Communication efficiency".format(runtime_name)
    )
    metric_info["comm_eff"]["short_label"] = (
        "{} Comm".format(runtime_name)
    )
    metric_info["comm_eff"]["type"] = (
        "{} runtime sub-metric".format(runtime_name)
    )

    metric_info["serial_eff"]["label"] = (
        "     -- {} Serialization efficiency".format(runtime_name)
    )
    metric_info["serial_eff"]["short_label"] = (
        "{} Ser".format(runtime_name)
    )
    metric_info["serial_eff"]["type"] = (
        "{} communication sub-metric".format(runtime_name)
    )

    metric_info["transfer_eff"]["label"] = (
        "     -- {} Transfer efficiency".format(runtime_name)
    )
    metric_info["transfer_eff"]["short_label"] = (
        "{} Trans".format(runtime_name)
    )
    metric_info["transfer_eff"]["type"] = (
        "{} communication sub-metric".format(runtime_name)
    )

    if runtime_name == "MPI":
        metric_info["parallel_eff"]["meaning"] = (
            "Parallel efficiency of the MPI execution."
        )
        metric_info["load_balance"]["meaning"] = (
            "Efficiency of useful-work distribution across MPI ranks."
        )
        metric_info["comm_eff"]["meaning"] = (
            "Efficiency loss associated with MPI communication."
        )
        metric_info["serial_eff"]["meaning"] = (
            "Efficiency loss caused by MPI serialization or limited overlap."
        )
        metric_info["transfer_eff"]["meaning"] = (
            "Efficiency loss caused by MPI data-transfer overhead."
        )

    return metric_info


def _filter_available_metric_keys(metric_keys, metric_sources,
                                  trace_list):
    """Return only metrics with at least one numeric value."""
    filtered = []

    for key in metric_keys:
        source = metric_sources.get(key, {})
        if any(
            _clean_value(_read_metric(source, key, trace)) is not None
            for trace in trace_list
        ):
            filtered.append(key)

    return filtered


def _build_basicanalysis_printable_report_html(
        metrics_result,
        analysis_result,
        report,
        trace_list,
        trace_processes,
        trace_tasks,
        trace_threads,
        trace_mode,
        cmdl_args,
        standalone=True):
    """Generate the printable BasicAnalysis HTML report.

    The printable report follows the same analytical architecture as the
    interactive report:

      1. Execution Overview
      2. Application Efficiency Analysis
      3. Runtime Analysis
         - single-runtime model for pure applications
         - composed runtime model for hybrid applications
      4. Runtime-Specific Analysis, when available
      5. Execution-Domain Analysis, when available
      Appendix A. Metric Definitions

    Runtime contributions, isolated runtime diagnoses, and Host/Device
    execution domains are intentionally represented as different layers.
    """

    trace_column_description = (
        _build_trace_column_description(
            report
        )
    )

    model = _report_execution_model(
        trace_mode,
        trace_list,
        metrics_result,
    )

    report_traces = report.get("traces", [])
    trace_labels = [
        _report_trace_label(trace_info)
        for trace_info in report_traces
    ]

    trace_header_note = _build_trace_header_note(report)
    trace_config_html = _build_trace_config_table_html(report)

    other_metrics = metrics_result["other_metrics"]
    overview_html = _build_overview_table_html(
        other_metrics,
        trace_list,
        trace_labels,
    )
    efficiency_scale_html = _build_efficiency_scale_html()

    mod_factors = metrics_result.get("mod_factors", {})
    hybrid_factors = metrics_result.get("hybrid_factors", {})
    hyb_comm_omp_factors = metrics_result.get(
        "hyb_comm_omp_factors",
        {},
    )

    inner_model = _inner_model_name(trace_mode, trace_list)
    hybrid_metric_info = _build_hybrid_metric_info(inner_model)
    global_metric_info = _build_global_metric_info(
        is_hybrid=model["is_hybrid"]
    )

    metric_reference = {}

    # --------------------------------------------------
    # 2. Application efficiency analysis
    # --------------------------------------------------
    if model["has_cuda"]:
        global_keys = [
            "global_eff",
            "parallel_eff",
            "load_balance",
            "comm_eff",
            "comp_scale",
        ]
        global_tree = GLOBAL_GPU_TREE
    else:
        global_keys = [
            "global_eff",
            "parallel_eff",
            "load_balance",
            "comm_eff",
            "comp_scale",
            "ipc_scale",
            "inst_scale",
            "freq_scale",
        ]
        global_tree = GLOBAL_TREE

    global_sources = {
        key: mod_factors
        for key in global_keys
    }
    global_filtered_keys = _filter_available_metric_keys(
        global_keys,
        global_sources,
        trace_list,
    )

    _collect_metric_reference(
        metric_reference,
        global_filtered_keys,
        global_metric_info,
    )

    global_html = _build_printable_metric_section(
        metric_keys=global_filtered_keys,
        metric_info=global_metric_info,
        metric_sources=global_sources,
        trace_list=trace_list,
        trace_labels=trace_labels,
        title="2 Application Efficiency Analysis",
        tree=global_tree,
        trace_header_note=trace_header_note,
        trace_column_description=trace_column_description,
        section_kicker="Application-level model",
        section_description=(
            "Overall efficiency decomposition and scaling behavior of the "
            "complete application."
        ),
    )

    # --------------------------------------------------
    # 3. Runtime analysis
    # --------------------------------------------------
    runtime_model_html = ""

    if model["is_hybrid"]:
        hybrid_keys = list(HYBRID_ORDER)
        if inner_model == "OpenMP" and cmdl_args.hyb_mpiomp:
            hybrid_keys += OMP_COMM_ORDER

        hybrid_sources = {
            key: hybrid_factors
            for key in HYBRID_ORDER
        }
        for key in OMP_COMM_ORDER:
            hybrid_sources[key] = hyb_comm_omp_factors

        hybrid_filtered_keys = _filter_available_metric_keys(
            hybrid_keys,
            hybrid_sources,
            trace_list,
        )

        if hybrid_filtered_keys:
            _collect_metric_reference(
                metric_reference,
                hybrid_filtered_keys,
                hybrid_metric_info,
            )
            runtime_model_html = _build_printable_metric_section(
                metric_keys=hybrid_filtered_keys,
                metric_info=hybrid_metric_info,
                metric_sources=hybrid_sources,
                trace_list=trace_list,
                trace_labels=trace_labels,
                title="3 Composed Runtime Analysis — MPI + {}".format(
                    inner_model
                ),
                tree=HYBRID_TREE,
                trace_header_note=trace_header_note,
                trace_column_description=trace_column_description,
                section_kicker="Composed runtime model",
                section_description=(
                    "Multiplicative decomposition of Parallel Efficiency "
                    "across the active runtimes."
                ),
            )
    else:
        if model["has_mpi"]:
            runtime_name = "MPI"
        elif model["has_omp"]:
            runtime_name = "OpenMP"
        elif model["has_cuda"]:
            runtime_name = "CUDA"
        else:
            runtime_name = "Parallel Runtime"

        single_runtime_keys = [
            "parallel_eff",
            "load_balance",
            "comm_eff",
            "serial_eff",
            "transfer_eff",
        ]
        single_runtime_sources = {
            key: mod_factors
            for key in single_runtime_keys
        }
        single_runtime_filtered_keys = _filter_available_metric_keys(
            single_runtime_keys,
            single_runtime_sources,
            trace_list,
        )

        if single_runtime_filtered_keys:
            single_runtime_info = _build_single_runtime_metric_info(
                runtime_name
            )
            _collect_metric_reference(
                metric_reference,
                single_runtime_filtered_keys,
                single_runtime_info,
            )
            runtime_model_html = _build_printable_metric_section(
                metric_keys=single_runtime_filtered_keys,
                metric_info=single_runtime_info,
                metric_sources=single_runtime_sources,
                trace_list=trace_list,
                trace_labels=trace_labels,
                title="3 {} Runtime Analysis".format(runtime_name),
                tree=GLOBAL_PARALLEL_TREE,
                trace_header_note=trace_header_note,
                trace_column_description=trace_column_description,
                section_kicker="Runtime model",
                section_description=(
                    "Runtime-level decomposition of Parallel Efficiency, "
                    "including load balance and communication losses."
                ),
            )

    # --------------------------------------------------
    # 4. Runtime-specific analysis
    # --------------------------------------------------
    runtime_specific_sections = []
    runtime_specific_index = 1

    # For hybrid executions, expose MPI separately from the composed model.
    if model["is_hybrid"] and model["has_mpi"]:
        mpi_keys = [
            "mpi_parallel_eff",
            "mpi_load_balance",
            "mpi_comm_eff",
            "serial_eff",
            "transfer_eff",
        ]
        mpi_sources = {
            key: hybrid_factors
            for key in mpi_keys
        }
        mpi_filtered_keys = _filter_available_metric_keys(
            mpi_keys,
            mpi_sources,
            trace_list,
        )

        if mpi_filtered_keys:
            _collect_metric_reference(
                metric_reference,
                mpi_filtered_keys,
                hybrid_metric_info,
            )
            runtime_specific_sections.append(
                _build_printable_metric_section(
                    metric_keys=mpi_filtered_keys,
                    metric_info=hybrid_metric_info,
                    metric_sources=mpi_sources,
                    trace_list=trace_list,
                    trace_labels=trace_labels,
                    title="4.{} MPI Runtime-Specific Analysis".format(
                        runtime_specific_index
                    ),
                    tree=MPI_RUNTIME_TREE,
                    trace_header_note=trace_header_note,
                    trace_column_description=trace_column_description,
                    section_kicker="Runtime-specific diagnosis",
                    section_description=(
                        "Isolated diagnosis of MPI load balance, "
                        "serialization, and transfer overhead."
                    ),
                )
            )
            runtime_specific_index += 1

    # OpenMP exposes a true isolated runtime-specific model.
    if model["has_omp"] and "omp_talp_factors" in metrics_result:
        omp_talp_factors = metrics_result["omp_talp_factors"]
        openmp_sources = {
            key: omp_talp_factors
            for key in OPENMP_ORDER
        }
        openmp_filtered_keys = _filter_available_metric_keys(
            OPENMP_ORDER,
            openmp_sources,
            trace_list,
        )

        if openmp_filtered_keys:
            _collect_metric_reference(
                metric_reference,
                openmp_filtered_keys,
                OPENMP_METRIC_INFO,
                runtime="OpenMP",
                runtime_family="openmp",
            )
            runtime_specific_sections.append(
                _build_printable_metric_section(
                    metric_keys=openmp_filtered_keys,
                    metric_info=OPENMP_METRIC_INFO,
                    metric_sources=openmp_sources,
                    trace_list=trace_list,
                    trace_labels=trace_labels,
                    title="4.{} OpenMP Runtime-Specific Analysis".format(
                        runtime_specific_index
                    ),
                    tree=OPENMP_TREE,
                    trace_header_note=trace_header_note,
                    trace_column_description=trace_column_description,
                    scope_note_html=_build_openmp_runtime_scope_note(
                        is_hybrid=model["is_hybrid"]
                    ),
                    section_kicker="Runtime-specific diagnosis",
                    section_description=(
                        "Direct diagnosis of serial execution, region load "
                        "balance, and OpenMP scheduling overhead."
                    ),
                )
            )
            runtime_specific_index += 1

    # CUDA/HIP currently expose their contribution from the composed model.
    # This is kept separate from Host and Device execution-domain analysis.
    if (
        model["is_hybrid"]
        and model["has_cuda"]
        and inner_model in ("CUDA", "HIP")
    ):
        accelerator_keys = [
            "omp_parallel_eff",
            "omp_load_balance",
            "omp_comm_eff",
        ]
        accelerator_sources = {
            key: hybrid_factors
            for key in accelerator_keys
        }
        accelerator_filtered_keys = _filter_available_metric_keys(
            accelerator_keys,
            accelerator_sources,
            trace_list,
        )

        if accelerator_filtered_keys:
            _collect_metric_reference(
                metric_reference,
                accelerator_filtered_keys,
                hybrid_metric_info,
            )
            runtime_specific_sections.append(
                _build_printable_metric_section(
                    metric_keys=accelerator_filtered_keys,
                    metric_info=hybrid_metric_info,
                    metric_sources=accelerator_sources,
                    trace_list=trace_list,
                    trace_labels=trace_labels,
                    title="4.{} {} Runtime Contribution".format(
                        runtime_specific_index,
                        inner_model,
                    ),
                    tree=INNER_RUNTIME_TREE,
                    trace_header_note=trace_header_note,
                    trace_column_description=trace_column_description,
                    section_kicker="Runtime contribution",
                    section_description=(
                        "Isolated view of the {} contribution derived from "
                        "the composed MPI+{} runtime model. A dedicated "
                        "runtime-specific model can be added here when its "
                        "metrics are defined."
                    ).format(inner_model, inner_model),
                )
            )
            runtime_specific_index += 1

    runtime_specific_html = "\n".join(runtime_specific_sections)

    # --------------------------------------------------
    # 5. Execution-domain analysis
    # --------------------------------------------------
    execution_domains_html = ""

    if metrics_result.get("kind") == "hybrid" and model["has_cuda"]:
        host_factors = metrics_result.get("host_factors", {})
        device_factors = metrics_result.get("device_factors", {})

        host_keys = [
            "host_global_eff",
            "host_parallel_eff",
            "mpi_parallel_eff",
            "mpi_load_balance",
            "mpi_comm_eff",
            "serial_eff",
            "transfer_eff",
            "dev_offload_eff",
            "host_comp_scale",
            "ipc_scale",
            "inst_scale",
            "freq_scale",
        ]
        device_keys = [
            "dev_global_eff",
            "dev_parallel_eff",
            "dev_load_balance",
            "dev_comm_eff",
            "dev_orches_eff",
            "dev_comp_scale",
        ]

        host_sources = {}
        for key in host_keys:
            if key in ("ipc_scale", "inst_scale", "freq_scale"):
                host_sources[key] = mod_factors
            else:
                host_sources[key] = host_factors

        device_sources = {
            key: device_factors
            for key in device_keys
        }

        host_filtered_keys = _filter_available_metric_keys(
            host_keys,
            host_sources,
            trace_list,
        )
        device_filtered_keys = _filter_available_metric_keys(
            device_keys,
            device_sources,
            trace_list,
        )

        if host_filtered_keys:
            _collect_metric_reference(
                metric_reference,
                host_filtered_keys,
                TALP_METRIC_INFO,
            )


        if device_filtered_keys:
            _collect_metric_reference(
                metric_reference,
                device_filtered_keys,
                TALP_METRIC_INFO,
            )

        if host_filtered_keys or device_filtered_keys:
            execution_domains_html = (
                _build_printable_execution_domains_section(
                    host_metric_keys=host_filtered_keys,
                    device_metric_keys=device_filtered_keys,
                    host_sources=host_sources,
                    device_sources=device_sources,
                    trace_list=trace_list,
                    trace_labels=trace_labels,
                    trace_column_description=trace_column_description,
                )
            )

    appendix_html = _build_metric_reference_appendix_html(
        metric_reference
    )


    body_html = """
        <header class="print-header">
            <h1>BasicAnalysis Performance Report</h1>
            <p>Hierarchical efficiency analysis and guided performance diagnosis</p>
        </header>

        <section class="print-overview">
            <header class="print-section-header">
                <h2>1 Execution Overview</h2>
                <p class="print-section-description">
                    Execution configuration, general performance indicators, and
                    the efficiency scale used throughout the report.
                </p>
            </header>

            <div class="print-overview-grid">
                <div class="print-overview-block">
                    <h3>Trace configuration</h3>
                    {trace_config_html}
                </div>

                <div class="print-overview-block">
                    <h3>General metrics</h3>
                    {trace_header_note}
                    {overview_html}
                </div>

                <div class="print-overview-block">
                    {efficiency_scale_html}
                </div>
            </div>
        </section>

        {global_html}
        {runtime_model_html}
        {runtime_specific_html}
        {execution_domains_html}
        {appendix_html}
    """.format(
        trace_config_html=trace_config_html,
        trace_header_note=trace_header_note,
        overview_html=overview_html,
        efficiency_scale_html=efficiency_scale_html,
        global_html=global_html,
        runtime_model_html=runtime_model_html,
        runtime_specific_html=runtime_specific_html,
        execution_domains_html=execution_domains_html,
        appendix_html=appendix_html,
    )

    if not standalone:
        return body_html

    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>BasicAnalysis Performance Report</title>

        <style>
            @page {{
                size: A4 landscape;
                margin: 10mm;
            }}

            @media print {{
                html,
                body {{
                    -webkit-print-color-adjust: exact;
                    print-color-adjust: exact;
                }}
            }}

            * {{ box-sizing: border-box; }}

            body {{
                margin: 0;
                color: #172033;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI",
                    Roboto, Helvetica, Arial, sans-serif;
                font-size: 9.4pt;
                line-height: 1.42;
            }}

            .print-header {{
                margin-bottom: 16px;
                padding: 13px 18px;
                background: #17365d;
                color: white;
            }}

            .print-header h1 {{
                margin: 0 0 3px;
                font-size: 20pt;
            }}

            .print-header p {{
                margin: 0;
                color: #d8e7f5;
            }}

            .print-page-section {{
                break-before: page;
                page-break-before: always;
            }}

            .print-overview {{
                break-before: auto;
                page-break-before: auto;
            }}

            .print-section-header {{
                break-after: avoid-page;
                page-break-after: avoid;
                margin-bottom: 10px;
            }}

            .print-section-kicker {{
                margin: 0 0 2px;
                color: #527397;
                font-size: 8pt;
                font-weight: 700;
                letter-spacing: .08em;
                text-transform: uppercase;
            }}

            .print-section-description {{
                margin: -4px 0 7px;
                color: #5c677a;
                font-size: 8.8pt;
            }}

            h2 {{
                margin: 0 0 8px;
                color: #17365d;
                font-size: 16pt;
            }}

            h3 {{
                margin: 12px 0 6px;
                color: #243b58;
                break-after: avoid-page;
                page-break-after: avoid;
            }}

            .print-overview-grid {{
                display: grid;
                grid-template-columns: 1fr;
                gap: 12px;
            }}

            .print-overview-block {{
                break-inside: avoid-page;
                page-break-inside: avoid;
            }}

            .metric-table,
            .efficiency-table,
            .metric-definition-table {{
                width: 100%;
                border-collapse: collapse;
            }}

            .metric-table th,
            .metric-table td,
            .efficiency-table th,
            .efficiency-table td,
            .metric-definition-table th,
            .metric-definition-table td {{
                padding: 4px 6px;
                border: 1px solid #dce3ec;
                vertical-align: top;
            }}

            .metric-table th,
            .efficiency-table th,
            .metric-definition-table th {{
                background: #edf3f9;
                color: #29435f;
                text-align: left;
            }}

            thead {{ display: table-header-group; }}
            tr {{
                break-inside: avoid-page;
                page-break-inside: avoid;
            }}

            .efficiency-table th:not(:first-child),
            .efficiency-table td:not(:first-child) {{
                text-align: center;
            }}

            .metric-name-cell {{
                padding-left: calc(6px + (var(--metric-depth, 0) * 14px)) !important;
            }}

            .metric-value {{
                display: inline-block;
                min-width: 54px;
                padding: 3px 6px;
                border-radius: 999px;
                font-size: 8pt;
                font-weight: 700;
            }}

            .metric-family-global {{
                background: #eef2f7;
                border-left: 4px solid #66788a !important;
            }}
            .metric-family-mpi {{
                background: #eaf3ff;
                border-left: 4px solid #4f86c6 !important;
            }}
            .metric-family-openmp {{
                background: #ecf8ef;
                border-left: 4px solid #4f9d69 !important;
            }}
            .metric-family-cuda {{
                background: #fff1e7;
                border-left: 4px solid #d9823b !important;
            }}
            .metric-family-host {{
                background: #f2edff;
                border-left: 4px solid #8066bf !important;
            }}
            .metric-family-device {{
                background: #e9f7f5;
                border-left: 4px solid #318c82 !important;
            }}

            .metric-table-card {{
                break-inside: auto;
                page-break-inside: auto;
            }}

            .print-analysis-summary {{
                margin-top: 12px;
            }}

            .observation-box {{
                margin: 0;
                padding: 10px 12px;
                border: 1px solid #b7cbe3;
                border-left: 5px solid #4c83bd;
                background: #f4f8ff;
                break-inside: avoid-page;
                page-break-inside: avoid;
            }}

            .observation-box h3 {{ margin-top: 0; }}

            .performance-interpretation p,
            .scaling-interpretation p {{
                margin: 4px 0;
                color: #31465d;
                font-size: 8.8pt;
                line-height: 1.45;
            }}

            .trace-header-note {{
                margin: 0 0 7px;
                color: #5c677a;
                font-size: 8.2pt;
            }}

            .analysis-scope-note {{
                margin: 8px 0 10px;
                padding: 10px 12px;
                border: 1px solid #d9c98c;
                border-left: 5px solid #c79a20;
                background: #fffaf0;
                color: #4f452d;
                break-inside: avoid-page;
                page-break-inside: avoid;
            }}

            .analysis-scope-note h3 {{
                margin: 0 0 4px;
                color: #6f5617;
            }}

            .analysis-scope-note p {{ margin: 4px 0; }}

            .efficiency-scale-panel {{
                margin: 0;
                padding: 12px 15px;
                border: 1px solid #d7e0ea;
                border-radius: 8px;
                background: #ffffff;
                break-inside: avoid-page;
                page-break-inside: avoid;
            }}

            .efficiency-scale-header h3 {{ margin: 0 0 2px; }}
            .efficiency-scale-header p {{
                margin: 0 0 8px;
                color: #5c677a;
            }}

            .efficiency-gradient-container {{
                position: relative;
                margin: 8px 8px 20px;
            }}

            .efficiency-gradient {{
                height: 12px;
                border-radius: 8px;
                background: linear-gradient(
                    to right,
                    #b2182b 0%, #ef6548 20%, #fdbb84 40%,
                    #fee8a8 60%, #ffffbf 75%, #d9ef8b 85%,
                    #b8e186 92%, #4dac26 100%
                );
            }}

            .efficiency-gradient-markers {{
                position: relative;
                height: 12px;
                margin-top: 3px;
                color: #5c677a;
                font-size: 7.5pt;
            }}

            .efficiency-gradient-markers span {{
                position: absolute;
                transform: translateX(-50%);
            }}
            .efficiency-gradient-markers span:first-child {{ transform: none; }}
            .efficiency-gradient-markers span:last-child {{ transform: translateX(-100%); }}

            .efficiency-scale-ranges {{
                display: grid;
                grid-template-columns: 60fr 25fr 15fr;
                border: 1px solid #d7e0ea;
            }}

            .scale-range {{
                display: flex;
                justify-content: space-between;
                padding: 5px 8px;
                border-top: 3px solid;
            }}
            .scale-range-critical {{ border-top-color: #ef4444; }}
            .scale-range-attention {{ border-top-color: #f4c76b; }}
            .scale-range-good {{ border-top-color: #69b34c; }}

            .efficiency-above-reference,
            .efficiency-scale-guidance {{
                margin: 7px 0 0;
                color: #4b5f78;
                font-size: 8pt;
            }}

            .efficiency-scale-guidance {{
                padding-top: 6px;
                border-top: 1px solid #d7e0ea;
            }}

            .metric-definition-table {{
                font-size: 8.3pt;
            }}

            .metric-definition-table td:first-child {{
                width: 27%;
                white-space: nowrap;
            }}

            .print-appendix .metric-definition-table td {{
                padding-top: 3px;
                padding-bottom: 3px;
            }}
        </style>
    </head>

    <body>
       {body_html}
    </body>
    </html>
    """.format(
    body_html=body_html
    )

    return html_content

def generate_basicanalysis_printable_report(
        metrics_result,
        analysis_result,
        report,
        trace_list,
        trace_processes,
        trace_tasks,
        trace_threads,
        trace_mode,
        cmdl_args):
    """Write the standalone printable BasicAnalysis HTML report."""

    html_content = _build_basicanalysis_printable_report_html(
        metrics_result=metrics_result,
        analysis_result=analysis_result,
        report=report,
        trace_list=trace_list,
        trace_processes=trace_processes,
        trace_tasks=trace_tasks,
        trace_threads=trace_threads,
        trace_mode=trace_mode,
        cmdl_args=cmdl_args,
    )

    output_html = os.path.join(
        os.getcwd(),
        "basicanalysis_printable_report.html",
    )

    with open(output_html, "w") as output_file:
        output_file.write(html_content)

    print(
        "Printable report written to {}".format(
            output_html
        )
    )

    return output_html
