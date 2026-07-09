#!/usr/bin/env python3

"""Interactive HTML reports for BasicAnalysis hybrid metrics."""

from __future__ import print_function, division

import os
import math
import json
import html
import observations

import plotly.graph_objects as go

SIMPLE_METRIC_INFO = {
    "global_eff": {
        "label": "Global efficiency",
        "short_label": "Global",
        "type": "Global metric",
        "meaning": "Overall efficiency including parallel efficiency and scalability.",
        "low": "Low values indicate relevant global inefficiency.",
        "above100": "Values above 100% may occur in some scaling cases and should be interpreted carefully.",
        "action": "Inspect parallel efficiency and computation scalability.",
    },
    "parallel_eff": {
        "label": "-- Parallel efficiency",
        "short_label": "PE",
        "type": "Parallel metric",
        "meaning": "Efficiency of the parallel execution at the measured scale.",
        "low": "Low values indicate parallel inefficiency.",
        "above100": "Values above 100% should be checked.",
        "action": "Inspect load balance and communication efficiency.",
    },
    "load_balance": {
        "label": "   -- Load balance",
        "short_label": "LB",
        "type": "Parallel sub-metric",
        "meaning": "Efficiency of work distribution across processes.",
        "low": "Low values indicate load imbalance.",
        "above100": "Values above 100% should be checked.",
        "action": "Inspect workload distribution.",
    },
    "comm_eff": {
        "label": "   -- Communication efficiency",
        "short_label": "Comm",
        "type": "Parallel sub-metric",
        "meaning": "Efficiency loss caused by communication.",
        "low": "Low values indicate communication overhead.",
        "above100": "Values above 100% should be checked.",
        "action": "Inspect serialization and transfer efficiency.",
    },
    "serial_eff": {
        "label": "      -- Serialization efficiency",
        "short_label": "Ser",
        "type": "Communication sub-metric",
        "meaning": "Efficiency loss caused by serialization.",
        "low": "Low values indicate serialization effects.",
        "above100": "Values above 100% may indicate simulation inconsistency.",
        "action": "Inspect simulated and original traces.",
    },
    "transfer_eff": {
        "label": "      -- Transfer efficiency",
        "short_label": "Trans",
        "type": "Communication sub-metric",
        "meaning": "Efficiency loss caused by data transfer overhead.",
        "low": "Low values indicate transfer overhead.",
        "above100": "Values above 100% may indicate simulation inconsistency.",
        "action": "Inspect communication volume and frequency.",
    },
    "comp_scale": {
        "label": "-- Computation scalability",
        "short_label": "Comp scale",
        "type": "Scalability metric",
        "meaning": "Scalability of useful computation.",
        "low": "Low values indicate computation scaling degradation.",
        "above100": "Values above 100% may occur depending on scaling behavior.",
        "action": "Inspect IPC, instruction, and frequency scalability.",
    },
    "ipc_scale": {
        "label": "   -- IPC scalability",
        "short_label": "IPC",
        "type": "Scalability sub-metric",
        "meaning": "Scalability of instructions per cycle.",
        "low": "Low values indicate IPC degradation.",
        "above100": "Values above 100% indicate higher IPC than reference.",
        "action": "Inspect microarchitectural behavior.",
    },
    "inst_scale": {
        "label": "   -- Instruction scalability",
        "short_label": "Inst",
        "type": "Scalability sub-metric",
        "meaning": "Scalability of executed instructions.",
        "low": "Low values indicate instruction-count growth or poor scaling.",
        "above100": "Values above 100% may occur depending on scaling mode.",
        "action": "Inspect algorithmic work and instrumentation effects.",
    },
    "freq_scale": {
        "label": "   -- Frequency scalability",
        "short_label": "Freq",
        "type": "Scalability sub-metric",
        "meaning": "Scalability of processor frequency.",
        "low": "Low values indicate frequency degradation.",
        "above100": "Values above 100% indicate higher frequency than reference.",
        "action": "Inspect CPU frequency, throttling, and power behavior.",
    },
}

METRIC_INFO = {
    "hybrid_eff": {
        "label": "Hybrid Parallel efficiency",
        "short_label": "Hybrid PE",
        "type": "Global hybrid metric",
        "meaning": "Overall parallel efficiency of the complete hybrid execution.",
        "low": "Low values indicate that the complete hybrid execution is far from ideal.",
        "above100": "Values above 100% are unexpected for this metric and should be checked.",
        "action": "Inspect MPI and inner-level component metrics to identify the dominant source of inefficiency.",
    },
    "mpi_parallel_eff": {
        "label": "  -- MPI Parallel efficiency",
        "short_label": " -- MPI PE",
        "type": "Outer-level MPI metric",
        "meaning": "Parallel efficiency associated with the MPI level.",
        "low": "Low values indicate MPI-level inefficiency.",
        "above100": "Values above 100% are unexpected for this metric and should be checked.",
        "action": "Inspect MPI load balance and MPI communication efficiency.",
    },
    "mpi_load_balance": {
        "label": "      -- MPI Load balance",
        "short_label": "  -- MPI LB",
        "type": "Outer-level MPI metric",
        "meaning": "Work distribution efficiency across MPI ranks.",
        "low": "Low values indicate load imbalance between MPI ranks.",
        "above100": "Values above 100% are unexpected for this metric and should be checked.",
        "action": "Inspect the workload distribution across MPI ranks.",
    },
    "mpi_comm_eff": {
        "label": "      -- MPI Communication efficiency",
        "short_label": "  -- MPI Comm",
        "type": "Outer-level MPI metric",
        "meaning": "Efficiency loss associated with MPI communication.",
        "low": "Low values indicate significant MPI communication overhead.",
        "above100": "Values above 100% are unexpected for this metric and should be checked.",
        "action": "Inspect MPI serialization and MPI transfer efficiency.",
    },
    "serial_eff": {
        "label": "         -- MPI Serialization efficiency",
        "short_label": "    -- MPI Ser",
        "type": "Outer-level MPI sub-metric",
        "meaning": "Efficiency loss caused by serialization or limited overlap in MPI communication.",
        "low": "Low values indicate relevant MPI serialization effects.",
        "above100": "Values above 100% are usually caused by simulation or measurement inconsistency.",
        "action": "Compare original and simulated traces.",
    },
    "transfer_eff": {
        "label": "         -- MPI Transfer efficiency",
        "short_label": "    -- MPI Trans",
        "type": "Outer-level MPI sub-metric",
        "meaning": "Efficiency loss caused by MPI transfer overhead.",
        "low": "Low values indicate relevant MPI transfer overhead.",
        "above100": "Values above 100% are usually caused by simulation or measurement inconsistency.",
        "action": "Inspect message sizes, communication frequency, and network behavior.",
    },
    "omp_parallel_eff": {
        "label": "  -- OpenMP Parallel efficiency",
        "short_label": "-- OMP PE",
        "type": "Inner-level contribution",
        "meaning": "Inner-level contribution derived from the hybrid decomposition.",
        "low": "Low values indicate that the inner level contributes significant inefficiency.",
        "above100": "Values above 100% indicate a compensation effect, not a conventional efficiency.",
        "action": "Inspect inner-level load balance, communication, serialization, and transfer efficiency.",
    },
    "omp_load_balance": {
        "label": "      -- OpenMP Load balance",
        "short_label": "  -- OMP LB",
        "type": "Inner-level contribution",
        "meaning": "Inner-level load-balance contribution in the hybrid decomposition.",
        "low": "Low values may indicate thread-level imbalance, but interpretation depends on the hybrid decomposition.",
        "above100": "Values above 100% indicate that the inner level compensates load imbalance observed at the MPI level.",
        "action": "Use this as a compensation indicator. For inner level only diagnosis, use an isolated inner level view.",
    },
    "omp_comm_eff": {
        "label": "      -- OpenMP Communication efficiency",
        "short_label": "  -- OMP Comm",
        "type": "Inner-level contribution",
        "meaning": "Inner-level synchronization/runtime-overhead contribution in the hybrid decomposition.",
        "low": "Low values indicate relevant inner-level synchronization or runtime overhead.",
        "above100": "Values above 100% indicate a compensation or amplification effect in the hybrid decomposition.",
        "action": "Inspect inner level serialization and transfer efficiency.",
    },
    "omp_serial_eff": {
        "label": "         -- OpenMP Serialization efficiency",
        "short_label": "    -- OMP Ser",
        "type": "Inner-level sub-metric",
        "meaning": "Effect of limited parallelism, dependencies, or serialized OpenMP regions.",
        "low": "Low values indicate structural limitations in OpenMP parallelism.",
        "above100": "Values above 100% indicate a compensation effect in the hybrid decomposition.",
        "action": "Inspect dependencies, critical sections, barriers, and limited parallel regions.",
    },
    "omp_transfer_eff": {
        "label": "         -- OpenMP Transfer efficiency",
        "short_label": "    -- OMP Trans",
        "type": "Inner-level sub-metric",
        "meaning": "Effect of OpenMP runtime, scheduling, synchronization, or thread-management overhead.",
        "low": "Low values indicate significant OpenMP runtime overhead.",
        "above100": "Values above 100% indicate a compensation effect in the hybrid decomposition.",
        "action": "Inspect fork-join frequency, scheduling overhead, barriers, and synchronization events.",
    },
}


TALP_METRIC_INFO = {
    "host_global_eff": {
        "label": "HOST Global efficiency",
        "short_label": "Host global",
        "type": "Host metric",
        "meaning": "Overall host efficiency.",
        "low": "Low values indicate host-side inefficiency.",
        "above100": "Values above 100% should be checked.",
        "action": "Inspect host parallel efficiency and host computation scalability.",
    },
    "host_parallel_eff": {
        "label": "-- Host Parallel efficiency",
        "short_label": "-- Host PE",
        "type": "Host metric",
        "meaning": "Host-side parallel efficiency.",
        "low": "Low values indicate host-side parallel inefficiency.",
        "above100": "Values above 100% should be checked.",
        "action": "Inspect MPI and offload efficiency.",
    },
    "mpi_parallel_eff": {
        "label": "   == MPI Parallel efficiency",
        "short_label": " -- MPI PE",
        "type": "MPI host metric",
        "meaning": "MPI efficiency on the host side.",
        "low": "Low values indicate MPI-level inefficiency.",
        "above100": "Values above 100% should be checked.",
        "action": "Inspect MPI load balance and communication efficiency.",
    },
    "mpi_load_balance": {
        "label": "       -- MPI Load balance",
        "short_label": " -- MPI LB",
        "type": "MPI host metric",
        "meaning": "MPI rank load balance.",
        "low": "Low values indicate MPI rank imbalance.",
        "above100": "Values above 100% should be checked.",
        "action": "Inspect MPI workload distribution.",
    },
    "mpi_comm_eff": {
        "label": "       -- MPI Communication efficiency",
        "short_label": " -- MPI Comm",
        "type": "MPI host metric",
        "meaning": "MPI communication efficiency.",
        "low": "Low values indicate MPI communication overhead.",
        "above100": "Values above 100% should be checked.",
        "action": "Inspect MPI serialization and transfer.",
    },
    "serial_eff": {
        "label": "          -- MPI Serialization efficiency",
        "short_label": "   -- MPI Ser",
        "type": "MPI sub-metric",
        "meaning": "MPI serialization efficiency.",
        "low": "Low values indicate MPI serialization effects.",
        "above100": "Values above 100% may indicate simulation inconsistency.",
        "action": "Inspect original and simulated traces.",
    },
    "transfer_eff": {
        "label": "          -- MPI Transfer efficiency",
        "short_label": "   -- MPI Trans",
        "type": "MPI sub-metric",
        "meaning": "MPI transfer efficiency.",
        "low": "Low values indicate MPI transfer overhead.",
        "above100": "Values above 100% may indicate simulation inconsistency.",
        "action": "Inspect message volume and frequency.",
    },
    "dev_offload_eff": {
        "label": "   == Device Offload efficiency",
        "short_label": "   == Offload",
        "type": "Host/device metric",
        "meaning": "Fraction of outside-MPI time effectively offloaded to the device.",
        "low": "Low values indicate low device offload efficiency.",
        "above100": "Values above 100% should be checked.",
        "action": "Inspect host/device work distribution.",
    },
    "host_comp_scale": {
        "label": "-- Host Computation scalability",
        "short_label": "-- Host scale",
        "type": "Host scalability metric",
        "meaning": "Host computation scalability.",
        "low": "Low values indicate host-side computation scaling loss.",
        "above100": "Values above 100% may occur depending on scaling behavior.",
        "action": "Inspect host IPC, instruction, and frequency scalability.",
    },
    "dev_global_eff": {
        "label": "DEVICE Global efficiency",
        "short_label": "Dev global",
        "type": "Device metric",
        "meaning": "Overall device-side efficiency.",
        "low": "Low values indicate GPU/device inefficiency.",
        "above100": "Values above 100% should be checked.",
        "action": "Inspect device parallel efficiency and computation scalability.",
    },
    "dev_parallel_eff": {
        "label": "-- Device Parallel efficiency",
        "short_label": "-- Dev PE",
        "type": "Device metric",
        "meaning": "Device-side parallel efficiency.",
        "low": "Low values indicate low useful device occupancy over runtime.",
        "above100": "Values above 100% should be checked.",
        "action": "Inspect device load balance, communication, and orchestration.",
    },
    "dev_load_balance": {
        "label": "   == Device Load balance",
        "short_label": "   == Dev LB",
        "type": "Device sub-metric",
        "meaning": "Load balance across devices.",
        "low": "Low values indicate imbalance across devices.",
        "above100": "Values above 100% should be checked.",
        "action": "Inspect per-device useful time.",
    },
    "dev_comm_eff": {
        "label": "   == Device Communication efficiency",
        "short_label": "   == Dev Comm",
        "type": "Device sub-metric",
        "meaning": "Efficiency related to device memory transfer overhead.",
        "low": "Low values indicate relevant device transfer overhead.",
        "above100": "Values above 100% should be checked.",
        "action": "Inspect host-device/device memory transfers.",
    },
    "dev_orches_eff": {
        "label": "   == Device Orchestration efficiency",
        "short_label": "   == Dev Orch",
        "type": "Device sub-metric",
        "meaning": "Efficiency of device orchestration over runtime.",
        "low": "Low values indicate relevant orchestration overhead.",
        "above100": "Values above 100% should be checked.",
        "action": "Inspect kernel launch, synchronization, and orchestration overhead.",
    },
    "dev_comp_scale": {
        "label": "-- Device Computation scalability",
        "short_label": "-- Dev scale",
        "type": "Device scalability metric",
        "meaning": "Device computation scalability.",
        "low": "Low values indicate GPU/device computation scaling loss.",
        "above100": "Values above 100% may occur depending on scaling behavior.",
        "action": "Inspect device useful time scaling.",
    },
}

OPENMP_METRIC_INFO = {
    "omp_talp_parallel_eff": {
        "label": "OpenMP Parallel efficiency",
        "short_label": "OMP PE",
        "type": "OpenMP metric",
        "meaning": "Efficiency of the OpenMP execution considering idle OpenMP-thread time as loss.",
        "low": "Low values indicate relevant OpenMP inefficiency.",
        "above100": "Values above 100% are unexpected and should be checked.",
        "action": "Inspect OpenMP Serial, Load Balance, and Scheduling efficiencies.",
    },
    "omp_talp_serial_eff": {
        "label": "  -- OpenMP Serial efficiency",
        "short_label": "OMP Serial",
        "type": "OpenMP sub-metric",
        "meaning": "Efficiency loss caused by time outside OpenMP parallel regions.",
        "low": "Low values indicate that a relevant part of the execution is not parallelized with OpenMP.",
        "above100": "Values above 100% are unexpected and should be checked.",
        "action": "Inspect useful computation and MPI time outside OpenMP parallel regions.",
    },
    "omp_talp_load_balance": {
        "label": "  -- OpenMP Load balance",
        "short_label": "OMP LB",
        "type": "OpenMP sub-metric",
        "meaning": "Efficiency loss caused by imbalance among OpenMP threads inside parallel regions.",
        "low": "Low values indicate that some OpenMP threads wait while others continue useful computation.",
        "above100": "Values above 100% are unexpected and should be checked.",
        "action": "Inspect useful duration per OpenMP thread and per parallel region.",
    },
    "omp_talp_scheduling_eff": {
        "label": "  -- OpenMP Scheduling efficiency",
        "short_label": "OMP Sched",
        "type": "OpenMP sub-metric",
        "meaning": "Efficiency loss caused by OpenMP scheduling and fork/join overhead.",
        "low": "Low values indicate relevant OpenMP runtime overhead.",
        "above100": "Values above 100% are unexpected and should be checked.",
        "action": "Inspect scheduling and fork/join states in the OpenMP regions.",
    },
}

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


GLOBAL_TREE = [
    _tree_node("global_eff", [
        _tree_node("parallel_eff", [
            _tree_node("load_balance"),
            _tree_node("comm_eff", [
                _tree_node("serial_eff"),
                _tree_node("transfer_eff"),
            ]),
        ]),
        _tree_node("comp_scale", [
            _tree_node("ipc_scale"),
            _tree_node("inst_scale"),
            _tree_node("freq_scale"),
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
        _tree_node("host_comp_scale"),
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

OPENMP_TREE = [
    _tree_node("omp_talp_parallel_eff", [
        _tree_node("omp_talp_serial_eff"),
        _tree_node("omp_talp_load_balance"),
        _tree_node("omp_talp_scheduling_eff"),
    ])
]



def _format_overview_value(key, value):
    if value in ["Non-Avail", "N/A", "NaN", None]:
        return str(value)

    try:
        value = float(value)
    except Exception:
        return str(value)

    return "{:.2f}".format(value)


def _build_overview_table_html(other_metrics, trace_list, trace_processes,
                               trace_tasks, trace_threads, trace_mode):
    headers = [
        _trace_label(trace, index, trace_processes, trace_tasks, trace_threads, trace_mode)
        for index, trace in enumerate(trace_list)
    ]

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
    elif value < 80.0:
        interpretation = info.get("low", "Low value. Potential optimization opportunity.")
    else:
        interpretation = "Value is relatively high. This component is probably not the dominant bottleneck."

    return (
        "<b>{}</b><br>"
        "Value: {:.2f}%<br><br>"
        "<b>Metric type:</b> {}<br>"
        "<b>Meaning:</b> {}<br>"
        "<b>Interpretation:</b> {}<br>"
        "<b>Actionability:</b> {}"
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
    """Softer RdYlGn-like scale, centered around 75%."""
    return [
        [0.00, "#b2182b"],
        [0.20, "#ef6548"],
        [0.40, "#fdbb84"],
        [0.60, "#fee8a8"],
        [0.75, "#ffffbf"],
        [0.85, "#d9ef8b"],
        [0.92, "#b8e186"],
        [1.00, "#4dac26"],
    ]

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
    elif value < 80.0:
        interpretation = info.get("low", "Low value. Potential optimization opportunity.")
    else:
        interpretation = "Value is relatively high. This component is probably not the dominant bottleneck."

    return (
        "<b>{}</b><br>"
        "Value: {:.2f}%<br><br>"
        "<b>Metric type:</b> {}<br>"
        "<b>Meaning:</b> {}<br>"
        "<b>Interpretation:</b> {}<br>"
        "<b>Actionability:</b> {}"
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


def _build_hybrid_metric_info(inner_model):
    """Build metric metadata for MPI+X hybrid metrics."""
    metric_info = dict(METRIC_INFO)

    metric_info["omp_parallel_eff"] = dict(metric_info["omp_parallel_eff"])
    metric_info["omp_load_balance"] = dict(metric_info["omp_load_balance"])
    metric_info["omp_comm_eff"] = dict(metric_info["omp_comm_eff"])

    metric_info["omp_parallel_eff"]["label"] = "  -- {} Parallel efficiency".format(inner_model)
    metric_info["omp_parallel_eff"]["short_label"] = "{} PE".format(inner_model)

    metric_info["omp_load_balance"]["label"] = "    -- {} Load balance".format(inner_model)
    metric_info["omp_load_balance"]["short_label"] = "{} LB".format(inner_model)

    metric_info["omp_comm_eff"]["label"] = "    -- {} Communication efficiency".format(inner_model)
    metric_info["omp_comm_eff"]["short_label"] = "{} Comm".format(inner_model)

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
        "<p><b>Default Paraver view:</b> Useful Duration timeline. "
        "Click the button to copy the command, then paste it in a terminal.</p>"
    )

    return "\n".join(html_lines)


def _build_trace_config_table_html(analysis_result, trace_list, trace_processes,
                                   trace_tasks, trace_threads, trace_mode):
    raw_data = analysis_result.get("raw_data", {})

    html = []
    html.append("<table class='metric-table'>")
    html.append("<thead><tr>")
    html.append("<th>Trace</th>")
    html.append("<th>Mode</th>")
    html.append("<th>Processes</th>")
    html.append("<th>Tasks/rank</th>")
    html.append("<th>Threads/task</th>")
    html.append("<th>Devices</th>")
    html.append("</tr></thead>")

    html.append("<tbody>")
    for index, trace in enumerate(trace_list):
        devices = raw_data.get("count_devices", {}).get(trace, None)

        if devices in [None, 0, 0.0]:
            devices = "-"

        html.append("<tr>")
        html.append("<td>{}</td>".format(index + 1))
        html.append("<td>{}</td>".format(trace_mode[trace]))
        html.append("<td>{}</td>".format(trace_processes[trace]))
        html.append("<td>{}</td>".format(trace_tasks[trace]))
        html.append("<td>{}</td>".format(trace_threads[trace]))
        html.append("<td>{}</td>".format(devices))
        html.append("</tr>")
    html.append("</tbody>")
    html.append("</table>")

    return "\n".join(html)


def _clean_metric_label(label):
    """Remove visual hierarchy markers from labels for the info panel."""
    return label.replace("-", "").replace("=", "").replace("*", "").strip()


def _metric_info_json(metric_keys, metric_info):
    """Build JSON metadata used by the clickable metric tree."""
    data = {}

    for key in metric_keys:
        info = metric_info.get(key, {})
        label = _clean_metric_label(info.get("label", key))

        data[key] = {
            "title": label,
            "type": info.get("type", "Metric"),
            "meaning": info.get("meaning", ""),
            "low": info.get("low", ""),
            "above100": info.get("above100", ""),
            "action": info.get("action", ""),
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
    elif tree_kind == "openmp":
        tree = OPENMP_TREE      
    else:
        tree = []

    return "\n".join(
        _render_tree_node(node, key_set, metric_info, section_id)
        for node in tree
    )


def _build_metric_tree_heatmap_section(metric_keys, metric_info, metric_sources,
                                       trace_list, trace_processes, trace_tasks,
                                       trace_threads, trace_mode, title,
                                       section_id, tree_kind=None):
    heatmap_html = _build_efficiency_heatmap_div(
        metric_keys=metric_keys,
        metric_info=metric_info,
        metric_sources=metric_sources,
        trace_list=trace_list,
        trace_processes=trace_processes,
        trace_tasks=trace_tasks,
        trace_threads=trace_threads,
        trace_mode=trace_mode,
        title=title,
        section_id=section_id,
    )

    info_json = _metric_info_json(metric_keys, metric_info)

    tree = []
    if tree_kind == "global":
        tree = GLOBAL_TREE
    elif tree_kind == "hybrid":
        tree = HYBRID_TREE
    elif tree_kind == "talp":
        tree = TALP_TREE
    elif tree_kind == "openmp":
        tree = OPENMP_TREE

    if tree:
        diagnosis_lines = observations.build_tree_diagnosis_observations(
            tree=tree,
            metric_info=metric_info,
            metric_sources=metric_sources,
            trace_list=trace_list,
        )

        trend_lines = observations.build_scaling_trend_lines(
            metric_keys=metric_keys,
            metric_info=metric_info,
            metric_sources=metric_sources,
            trace_list=trace_list,
            max_items=4,
        )

        observations_html = observations.build_tree_diagnosis_html(
            diagnosis_lines,
            trend_lines=trend_lines,
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
        )

        observations_html = observations.build_threshold_observation_html(
            observation_groups,
            title="Analysis summary",
        )

    return """
    <script>
    window.metricInfo_{section_id} = {info_json};
    </script>

    {observations_html}

    <div class="metric-info-panel" id="{section_id}-info-panel">
        <h3 id="{section_id}-info-title">Select a metric</h3>
        <p id="{section_id}-info-type" class="metric-info-type"></p>
        <p id="{section_id}-info-meaning">Click a cell in the table to see its value, description, and diagnostic hints.</p>
        <p id="{section_id}-info-interpretation"></p>
        <p id="{section_id}-info-action"></p>
    </div>

    <div class="metric-heatmap">
        {heatmap_html}
    </div>
    """.format(
        section_id=section_id,
        info_json=info_json,
        observations_html=observations_html,
        heatmap_html=heatmap_html,
    )


def _plot_efficiency_heatmap_interactive(metric_keys, metric_info, metric_sources,
                                         trace_list, trace_processes, trace_tasks,
                                         trace_threads, trace_mode, cmdl_args,
                                         output_html, title, trace_summary=None,
                                         split_index=None):
    """Generic interactive efficiency heatmap renderer."""

    y_values = list(range(len(metric_keys)))

    metric_labels = [metric_info[key]["label"] for key in metric_keys]
    metric_short_labels = [
        metric_info[key].get("short_label", metric_info[key]["label"])
        for key in metric_keys
    ]

    x_labels = [
        _trace_label(trace, index, trace_processes, trace_tasks, trace_threads, trace_mode)
        for index, trace in enumerate(trace_list)
    ]

    if trace_summary is None:
        trace_summary = "<br>".join([
            _trace_summary(trace, index, trace_processes, trace_tasks, trace_threads, trace_mode)
            for index, trace in enumerate(trace_list)
        ])

    z_values = []
    text_values = []
    hover_values = []

    for key in metric_keys:
        z_row = []
        text_row = []
        hover_row = []

        source = metric_sources[key]

        for trace in trace_list:
            raw_value = _read_metric(source, key, trace)
            value = _clean_value(raw_value)

            z_row.append(value)
            text_row.append("" if value is None else "{:.2f}".format(value))
            hover_row.append(_hover_text_from_info(metric_info, key, value, raw_value))

        z_values.append(z_row)
        text_values.append(text_row)
        hover_values.append(hover_row)

    fig = go.Figure(
        data=go.Heatmap(
            z=z_values,
            x=x_labels,
            y=y_values,
            text=hover_values,
            hoverinfo="text",
            zmin=0,
            zmax=100,
            colorscale=_seaborn_rdylgn_center75_colorscale(),
            colorbar=dict(title="Percentage(%)"),
            xgap=1,
            ygap=1,
            hoverlabel=dict(
                bgcolor="white",
                bordercolor="#aaa",
                font=dict(color="#222", size=12),
                align="left",
            ),
        )
    )

    desktop_domain_left = 0.52 if len(trace_list) > 1 else 0.45
    
    top_margin = 170 + 22 * max(0, len(trace_list) - 1)


    fig.update_layout(
        title=dict(
            text=title + "<br><span style='font-size:12px'>{}</span>".format(trace_summary),
            x=0.02,
            xanchor="left",
        ),
        autosize=True,
        height=max(620, 42 * len(metric_keys) + top_margin - 120),
        margin=dict(l=40, r=80, t=top_margin, b=40),
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

    if split_index is not None:
        fig.add_shape(
            type="line",
            xref="paper",
            x0=desktop_domain_left,
            x1=0.86,
            yref="y",
            y0=split_index - 0.5,
            y1=split_index - 0.5,
            line=dict(color="black", width=2),
        )

    # Left-aligned metric labels
    for i, label in enumerate(metric_labels):
        fig.add_annotation(
            xref="paper",
            x=0.02,
            yref="y",
            y=i,
            text=label,
            showarrow=False,
            xanchor="left",
            yanchor="middle",
            align="left",
            font=dict(size=13),
        )

    # Centered values
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

    post_script = """
    var fullLabels = %s;
    var shortLabels = %s;
    var nMetricLabels = fullLabels.length;

    function updateResponsiveLayout() {
        var w = window.innerWidth;
        var shortMode = w < 750;
        var mobileMode = w < 520;

        var labels = shortMode ? shortLabels : fullLabels;

        var updates = {};
        for (var i = 0; i < nMetricLabels; i++) {
            updates["annotations[" + i + "].text"] = labels[i];
            updates["annotations[" + i + "].font.size"] = mobileMode ? 11 : 13;
        }

        if (mobileMode) {
            updates["xaxis.domain"] = [0.30, 0.82];
            updates["margin.l"] = 20;
            updates["margin.r"] = 50;
        } else if (shortMode) {
            updates["xaxis.domain"] = [0.34, 0.84];
            updates["margin.l"] = 30;
            updates["margin.r"] = 60;
        } else {
            updates["xaxis.domain"] = [%s, 0.86];
            updates["margin.l"] = 40;
            updates["margin.r"] = 80;
        }

        Plotly.relayout("{plot_id}", updates);
    }

    window.addEventListener("resize", updateResponsiveLayout);
    updateResponsiveLayout();
    """ % (
        metric_labels,
        metric_short_labels,
        desktop_domain_left,
    )

    fig.write_html(
        output_html,
        include_plotlyjs="cdn",
        config={"responsive": True},
        post_script=post_script,
    )

    print("Interactive Efficiency Table written to {}".format(output_html))


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

    # Left-side metric labels
    for i, label in enumerate(metric_labels):
        fig.add_annotation(
            xref="paper",
            x=0.02,
            yref="y",
            y=i,
            text=label,
            showarrow=False,
            xanchor="left",
            yanchor="middle",
            align="left",
            font=dict(size=13),
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


def plot_hybrid_efficiency_interactive(metrics_result, trace_list, trace_processes,
                                       trace_tasks, trace_threads, trace_mode,
                                       cmdl_args):
    """Generate interactive HTML heatmap for hybrid MPI+X metrics, including global metrics."""

    mod_factors = metrics_result["mod_factors"]
    hybrid_factors = metrics_result["hybrid_factors"]
    hyb_comm_omp_factors = metrics_result["hyb_comm_omp_factors"]

    inner_model = _inner_model_name(trace_mode, trace_list)

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

    metric_info = dict(SIMPLE_METRIC_INFO)
    metric_info.update(_build_hybrid_metric_info(inner_model))

    show_hyb_comm_omp = (
        inner_model == "OpenMP"
        and cmdl_args.hyb_mpiomp
        and any(trace_mode[trace] == "Detailed+MPI+OpenMP" for trace in trace_list)
    )

    metric_keys = list(global_keys) + list(HYBRID_ORDER)
    if show_hyb_comm_omp:
        metric_keys += OMP_COMM_ORDER

    metric_sources = {}

    for key in global_keys:
        metric_sources[key] = mod_factors

    for key in HYBRID_ORDER:
        metric_sources[key] = hybrid_factors

    for key in OMP_COMM_ORDER:
        metric_sources[key] = hyb_comm_omp_factors

    filtered_keys = []
    for key in metric_keys:
        source = metric_sources[key]
        for trace in trace_list:
            if _clean_value(_read_metric(source, key, trace)) is not None:
                filtered_keys.append(key)
                break

    output_html = os.path.join(os.getcwd(), "efficiency_table_hybrid_interactive.html")

    _plot_efficiency_heatmap_interactive(
        metric_keys=filtered_keys,
        metric_info=metric_info,
        metric_sources=metric_sources,
        trace_list=trace_list,
        trace_processes=trace_processes,
        trace_tasks=trace_tasks,
        trace_threads=trace_threads,
        trace_mode=trace_mode,
        cmdl_args=cmdl_args,
        output_html=output_html,
        title="BasicAnalysis interactive hybrid efficiency table",
        split_index=len(global_keys),
    )


def plot_simple_efficiency_interactive(metrics_result, trace_list, trace_processes,
                                       trace_tasks, trace_threads, trace_mode,
                                       cmdl_args):
    """Generate interactive HTML heatmap for simple metrics."""

    mod_factors = metrics_result["mod_factors"]

    metric_keys = [
        "global_eff",
        "parallel_eff",
        "load_balance",
        "comm_eff",
        "serial_eff",
        "transfer_eff",
        "comp_scale",
        "ipc_scale",
        "inst_scale",
        "freq_scale",
    ]

    # Remove communication submetrics if they are not available in all traces
    filtered_keys = []
    for key in metric_keys:
        keep = False
        for trace in trace_list:
            if _clean_value(_read_metric(mod_factors, key, trace)) is not None:
                keep = True
        if keep:
            filtered_keys.append(key)

    metric_sources = {key: mod_factors for key in filtered_keys}

    output_html = os.path.join(os.getcwd(), "efficiency_table_simple_interactive.html")

    _plot_efficiency_heatmap_interactive(
        metric_keys=filtered_keys,
        metric_info=SIMPLE_METRIC_INFO,
        metric_sources=metric_sources,
        trace_list=trace_list,
        trace_processes=trace_processes,
        trace_tasks=trace_tasks,
        trace_threads=trace_threads,
        trace_mode=trace_mode,
        cmdl_args=cmdl_args,
        output_html=output_html,
        title="BasicAnalysis interactive efficiency table",
    )


def plot_talp_efficiency_interactive(metrics_result, analysis_result, trace_list,
                                     trace_processes, trace_tasks, trace_threads,
                                     trace_mode, cmdl_args):
    """Generate interactive HTML heatmap for TALP MPI+GPU metrics."""

    raw_data = analysis_result["raw_data"]
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
    ]

    device_keys = [
        "dev_global_eff",
        "dev_parallel_eff",
        "dev_load_balance",
        "dev_comm_eff",
        "dev_orches_eff",
        "dev_comp_scale",
    ]

    metric_keys = host_keys + device_keys

    filtered_keys = []
    for key in metric_keys:
        source = device_factors if key.startswith("dev_") and key != "dev_offload_eff" else host_factors
        for trace in trace_list:
            if _clean_value(_read_metric(source, key, trace)) is not None:
                filtered_keys.append(key)
                break

    metric_sources = {}
    for key in filtered_keys:
        if key.startswith("dev_") and key != "dev_offload_eff":
            metric_sources[key] = device_factors
        else:
            metric_sources[key] = host_factors

    trace_summary = "<br>".join([
        "Trace {}: mode={}, processes={}, tasks/rank={}, threads/task={}, devices={}".format(
            index + 1,
            trace_mode[trace],
            trace_processes[trace],
            trace_tasks[trace],
            trace_threads[trace],
            raw_data["count_devices"][trace],
        )
        for index, trace in enumerate(trace_list)
    ])

    output_html = os.path.join(os.getcwd(), "efficiency_table_talp_interactive.html")

    _plot_efficiency_heatmap_interactive(
        metric_keys=filtered_keys,
        metric_info=TALP_METRIC_INFO,
        metric_sources=metric_sources,
        trace_list=trace_list,
        trace_processes=trace_processes,
        trace_tasks=trace_tasks,
        trace_threads=trace_threads,
        trace_mode=trace_mode,
        cmdl_args=cmdl_args,
        output_html=output_html,
        title="BasicAnalysis interactive TALP efficiency table",
        trace_summary=trace_summary,
    )


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


def plot_basicanalysis_interactive_report(metrics_result, analysis_result,
                                          report,
                                          trace_list, trace_processes,
                                          trace_tasks, trace_threads,
                                          trace_mode, cmdl_args):
    """Generate unified interactive HTML report."""

    output_html = os.path.join(os.getcwd(), "basicanalysis_interactive_report.html")

    other_metrics = metrics_result["other_metrics"]

    model = _report_execution_model(trace_mode, trace_list, metrics_result)
    tabs = _build_report_tabs(model)

    overview_html = _build_overview_table_html(
        other_metrics,
        trace_list,
        trace_processes,
        trace_tasks,
        trace_threads,
        trace_mode,
    )

    mod_factors = metrics_result.get("mod_factors", {})
    hybrid_factors = metrics_result.get("hybrid_factors", {})
    hyb_comm_omp_factors = metrics_result.get("hyb_comm_omp_factors", {})

    inner_model = _inner_model_name(trace_mode, trace_list)
    hybrid_metric_info = _build_hybrid_metric_info(inner_model)

    global_keys = [
        "global_eff",
        "parallel_eff",
        "load_balance",
        "comm_eff",
        "serial_eff",
        "transfer_eff",
        "comp_scale",
        "ipc_scale",
        "inst_scale",
        "freq_scale",
    ]


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
        metric_info=SIMPLE_METRIC_INFO,
        metric_sources=global_sources,
        trace_list=trace_list,
        trace_processes=trace_processes,
        trace_tasks=trace_tasks,
        trace_threads=trace_threads,
        trace_mode=trace_mode,
        title="Global metrics",
        section_id="global",
        tree_kind="global",
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
            trace_processes=trace_processes,
            trace_tasks=trace_tasks,
            trace_threads=trace_threads,
            trace_mode=trace_mode,
            title="Parallel Programming Model: MPI + {}".format(inner_model),
            section_id="hybrid",
            tree_kind="hybrid",
        )
    else:
        hybrid_html = "<p>Parallel programming model metrics are not available for simple traces.</p>"

    # ---- TALP model tab

    if (
    metrics_result["kind"] == "hybrid"
    and trace_mode[trace_list[0]] == "Detailed+MPI+CUDA"
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
        ]

        device_keys = [
            "dev_global_eff",
            "dev_parallel_eff",
            "dev_load_balance",
            "dev_comm_eff",
            "dev_orches_eff",
            "dev_comp_scale",
        ]

        talp_keys = host_keys + device_keys

        talp_sources = {}
        for key in host_keys:
            talp_sources[key] = host_factors
        for key in device_keys:
            talp_sources[key] = device_factors

        # Remove rows that are unavailable for all traces
        talp_filtered_keys = []
        for key in talp_keys:
            source = talp_sources[key]
            for trace in trace_list:
                if _clean_value(_read_metric(source, key, trace)) is not None:
                    talp_filtered_keys.append(key)
                    break
        talp_html = _build_metric_tree_heatmap_section(
            metric_keys=talp_filtered_keys,
            metric_info=TALP_METRIC_INFO,
            metric_sources=talp_sources,
            trace_list=trace_list,
            trace_processes=trace_processes,
            trace_tasks=trace_tasks,
            trace_threads=trace_threads,
            trace_mode=trace_mode,
            title="Host/Device Efficiency Metrics",
            section_id="talp",
            tree_kind="talp",
        )
    else:
        talp_html = ("<p>Host/Device metrics are only available for MPI+GPU traces.</p>")


    # ---- OpenMP Efficiency Metrics tab
    if (
        metrics_result["kind"] == "hybrid"
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

            openmp_html = _build_metric_tree_heatmap_section(
                metric_keys=openmp_filtered_keys,
                metric_info=OPENMP_METRIC_INFO,
                metric_sources=openmp_sources,
                trace_list=trace_list,
                trace_processes=trace_processes,
                trace_tasks=trace_tasks,
                trace_threads=trace_threads,
                trace_mode=trace_mode,
                title="OpenMP Efficiency Metrics",
                section_id="openmp",
                tree_kind="openmp",
            )
        else:
            openmp_html = (
                "<p>OpenMP efficiency metrics are not available for this trace configuration.</p>"
            )
    else:
        openmp_html = (
            "<p>OpenMP efficiency metrics are only available for MPI+OpenMP traces.</p>"
        )


    trace_config_html = _build_trace_config_table_html(
        analysis_result,
        trace_list,
        trace_processes,
        trace_tasks,
        trace_threads,
        trace_mode,
    )
    
    resources_html = _build_resources_table_html(report)


    show_simple = (
        not model["is_hybrid"]
        and model["has_mpi"]
        and not model["has_omp"]
        and not model["has_cuda"]
    )

    show_hybrid = model["is_hybrid"]

    show_hostdevice = model["has_cuda"]

    show_openmp = model["has_omp"]


    html_content = """
        <!DOCTYPE html>
        <html>
        <head>
        <meta charset="utf-8">
        <title>BasicAnalysis Interactive Report</title>
        <script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
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


        </style>

        <script>
        function showTab(tabId) {
            const contents = document.getElementsByClassName("tab-content");
            for (let i = 0; i < contents.length; i++) {
                contents[i].classList.remove("active");
            }

            const buttons = document.getElementsByClassName("tab-button");
            for (let i = 0; i < buttons.length; i++) {
                buttons[i].classList.remove("active");
            }

            document.getElementById(tabId).classList.add("active");
            document.getElementById(tabId + "-button").classList.add("active");
        }

        function selectMetric(sectionId, metricKey) {
            const infoDict = window["metricInfo_" + sectionId];
            if (!infoDict || !infoDict[metricKey]) {
                return;
            }

            const info = infoDict[metricKey];

            document.getElementById(sectionId + "-info-title").innerText = info.title;
            document.getElementById(sectionId + "-info-type").innerText = info.type;
            document.getElementById(sectionId + "-info-meaning").innerText = info.meaning;
            document.getElementById(sectionId + "-info-interpretation").innerText =
                "Low values: " + info.low + " Above 100%: " + info.above100;
            document.getElementById(sectionId + "-info-action").innerText =
                "Suggested action: " + info.action;

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

        function selectMetricCell(sectionId, metricKey, metricLabel, traceLabel, value) {
            const infoDict = window["metricInfo_" + sectionId];
            if (!infoDict || !infoDict[metricKey]) {
                return;
            }

            const info = infoDict[metricKey];
            const valueText = value === null || value === undefined ? "Non-Avail" : value.toFixed(2) + "%";

            document.getElementById(sectionId + "-info-title").innerText =
                info.title + " — " + traceLabel;

            document.getElementById(sectionId + "-info-type").innerText =
                info.type + " | Value: " + valueText;

            document.getElementById(sectionId + "-info-meaning").innerText =
                info.meaning;

            if (value !== null && value !== undefined && value < 80.0) {
                document.getElementById(sectionId + "-info-interpretation").innerText =
                    "Interpretation: " + info.low;
            } else if (value !== null && value !== undefined && value > 100.0) {
                document.getElementById(sectionId + "-info-interpretation").innerText =
                    "Interpretation: " + info.above100;
            } else {
                document.getElementById(sectionId + "-info-interpretation").innerText =
                    "Interpretation: This component is probably not the dominant bottleneck.";
            }

            document.getElementById(sectionId + "-info-action").innerText =
                "Suggested action: " + info.action;


            const buttons = document.querySelectorAll(
                "#" + sectionId + " .metric-tree-button"
            );

            for (let i = 0; i < buttons.length; i++) {
                buttons[i].classList.remove("active");

                if (buttons[i].getAttribute("data-metric-key") === metricKey) {
                    buttons[i].classList.add("active");
                }
            }
        }

        function copyCommand(cmd) {
            navigator.clipboard.writeText(cmd).then(function() {
                alert("Paraver command copied to clipboard.");
            });
        }

        </script>
        </head>

        <body onload="showTab('overview')">

        <h1>BasicAnalysis Interactive Report</h1>
        <div class="subtitle">Performance diagnosis organized by metric level.</div>

        <div class="tab-bar">
            <button id="overview-button" class="tab-button" onclick="showTab('overview')">Overview</button>
            <button id="global-button" class="tab-button" onclick="showTab('global')">Global metrics</button>
            <button id="hybrid-button" class="tab-button" onclick="showTab('hybrid')">Programming Model</button>
            <button id="talp-button" class="tab-button" onclick="showTab('talp')">Host/Device</button>
            <button id="isolated-inner-button" class="tab-button" onclick="showTab('isolated-inner')">OpenMP</button>
        </div>

        <div id="overview" class="tab-content">
            <h2>Overview</h2>

            <h3>Trace configuration</h3>
            {trace_config_html}

            <h3>Open traces in Paraver</h3>
            {resources_html}

            <h3>General metrics</h3>
            {overview_html}
        </div>

        <div id="global" class="tab-content">
            <h2>Global metrics</h2>
            {global_html}
        </div>

        <div id="hybrid" class="tab-content">
            <h2>Parallel Programming Model Efficiency Metrics</h2>
            {hybrid_html}
        </div>
    
        <div id="talp" class="tab-content">
            <h2>Host/Device Efficiency Metrics</h2>
            {talp_html}
        </div>

        <div id="isolated-inner" class="tab-content">
            <h2>OpenMP Efficiency Metrics</h2>
            {openmp_html}
        </div>        

        </body>
        </html>
        """
    
   
    if not show_hybrid:
        html_content = html_content.replace(
            '<button id="hybrid-button" class="tab-button" onclick="showTab(\'hybrid\')">Programming Model</button>',
            ""
        )

        html_content = html_content.replace(
            '<div id="hybrid" class="tab-content">',
            '<div id="hybrid" class="tab-content" style="display:none;">'
        )   


    if not show_hostdevice:
        html_content = html_content.replace(
            '<button id="talp-button" class="tab-button" onclick="showTab(\'talp\')">Host/Device</button>',
            ""
        )

        html_content = html_content.replace(
            '<div id="talp" class="tab-content">',
            '<div id="talp" class="tab-content" style="display:none;">'
        )

    if not show_openmp:
        html_content = html_content.replace(
            '<button id="isolated-inner-button" class="tab-button" onclick="showTab(\'isolated-inner\')">OpenMP</button>',
            ""
        )
        html_content = html_content.replace(
            '<div id="isolated-inner" class="tab-content">',
            '<div id="isolated-inner" class="tab-content" style="display:none;">'
        )
 
    html_content = html_content.replace("{trace_config_html}", trace_config_html)
    html_content = html_content.replace("{overview_html}", overview_html)
    html_content = html_content.replace("{global_html}", global_html)
    html_content = html_content.replace("{hybrid_html}", hybrid_html)
    html_content = html_content.replace("{talp_html}", talp_html)
    html_content = html_content.replace("{openmp_html}", openmp_html)
    html_content = html_content.replace("{resources_html}", resources_html)

    with open(output_html, "w") as f:
        f.write(html_content)

    print("Interactive report written to {}".format(output_html))