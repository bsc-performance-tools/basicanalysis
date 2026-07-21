#!/usr/bin/env python3

"""Interactive HTML reports for BasicAnalysis hybrid metrics."""

from __future__ import print_function, division

import os
import math
import json
import html
import observations

import plotly.graph_objects as go

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
         "action": (
            "Compare Host Global Efficiency with Device Global Efficiency. "
            "If the host value is substantially lower, inspect Host Parallel "
            "Efficiency, Device Offload Efficiency, and Host Computation "
            "Scalability to determine whether the dominant loss originates "
            "from MPI, the host-side accelerator execution path, or host computation."
        ),
    },
    "host_parallel_eff": {
        "label": "-- Host Parallel efficiency",
        "short_label": "-- Host PE",
        "type": "Host metric",
        "meaning": "Host-side parallel efficiency.",
        "low": "Low values indicate host-side parallel inefficiency.",
        "above100": "Values above 100% should be checked.",
         "action": (
            "Compare MPI Parallel Efficiency with Device Offload Efficiency. "
            "This separates MPI-related losses from losses in the host-side "
            "accelerator execution path."
        ),
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
         "meaning": (
            "Efficiency with which host-side time outside MPI is converted "
            "into effective device execution."
        ),
        "low": (
            "Low values indicate that a substantial fraction of host-side "
            "execution does not result in effective device work. Possible "
            "contributors include kernel-launch overhead, synchronization, "
            "runtime management, data movement, or insufficient accelerator use."
        ),
        "above100": "Values above 100% should be checked.",
        "action": (
            "Compare Device Offload Efficiency with MPI Parallel Efficiency "
            "and Device Global Efficiency. A low offload value together with "
            "healthy MPI metrics indicates that the dominant loss occurs in "
            "the host-side accelerator execution path. Then inspect the Device "
            "view to determine whether device-side execution adds another loss."
        ),
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
         "action": (
            "Inspect Device Parallel Efficiency and Device Computation "
            "Scalability. Within Device Parallel Efficiency, compare Device "
            "Load Balance, Communication Efficiency, and Orchestration Efficiency. "
            "Compare the result with Device Offload Efficiency to distinguish "
            "device-side inefficiency from host-side accelerator overhead."
        ),
    },
    "dev_parallel_eff": {
        "label": "-- Device Parallel efficiency",
        "short_label": "-- Dev PE",
        "type": "Device metric",
        "meaning": "Device-side parallel efficiency.",
        "low": "Low values indicate low useful device occupancy over runtime.",
        "above100": "Values above 100% should be checked.",
         "action": (
            "Compare Device Load Balance, Communication Efficiency, and "
            "Orchestration Efficiency. Then compare the device-side result "
            "with Device Offload Efficiency to determine whether the larger "
            "loss occurs during host-side offloading or device execution."
        ),
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
         "action": (
            "Inspect kernel-launch frequency, synchronization, stream dependencies, "
            "runtime scheduling, and overlap between device computation and data "
            "movement. Compare this loss with Device Offload Efficiency to distinguish "
            "device-side orchestration overhead from host-side accelerator overhead."
        ),
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

for key in ("ipc_scale", "inst_scale", "freq_scale"):
    TALP_METRIC_INFO[key] = dict(SIMPLE_METRIC_INFO[key])

TALP_METRIC_INFO["ipc_scale"]["type"] = "Host scalability sub-metric"
TALP_METRIC_INFO["inst_scale"]["type"] = "Host scalability sub-metric"
TALP_METRIC_INFO["freq_scale"]["type"] = "Host scalability sub-metric"


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
        "label": "  -- OpenMP Region Load balance",
        "short_label": "OMP Region LB",
        "type": "OpenMP runtime-specific sub-metric",
        "meaning": (
            "Efficiency of useful-computation distribution among OpenMP "
            "threads inside OpenMP parallel regions. Only useful computation "
            "performed inside those regions is considered."
        ),
        "low": (
            "Low values indicate that useful computation is unevenly "
            "distributed among OpenMP threads inside parallel regions."
        ),
        "above100": "Values above 100% are unexpected and should be checked.",
        "action": (
            "Inspect useful computation per OpenMP thread and per parallel "
            "region. Do not compare this metric directly with the classical "
            "application-level POP Load Balance."
        ),
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


def _build_global_metric_info(is_hybrid):
    """Build application-level metric guidance for the execution model."""
    metric_info = {
        key: dict(value)
        for key, value in SIMPLE_METRIC_INFO.items()
    }

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
    metric_info = {
        key: dict(value)
        for key, value in METRIC_INFO.items()
    }

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
            "First compare {0} Load Balance with MPI Load Balance. Then "
            "continue the diagnosis in the Execution Domain section: low "
            "Device Offload Efficiency indicates host-side accelerator "
            "overhead, whereas low Device Load Balance indicates imbalance "
            "during device execution."
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
            "First compare {0} Communication Efficiency with MPI "
            "Communication Efficiency. Then continue the diagnosis in the "
            "Execution Domain section to distinguish host-side offloading, "
            "data movement, and synchronization overhead from device-side "
            "communication or orchestration losses."
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


def _build_efficiency_scale_html():
    """Build the common efficiency interpretation scale."""

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

            <div class="efficiency-gradient-markers">
                <span style="left: 0%;">0%</span>
                <span style="left: 60%;">60%</span>
                <span style="left: 85%;">85%</span>
                <span style="left: 100%;">100%</span>
            </div>
        </div>

        <div class="efficiency-scale-ranges">
            <div class="scale-range scale-range-critical">
                <strong>Critical</strong>
                <span>&lt; 60%</span>
            </div>

            <div class="scale-range scale-range-attention">
                <strong>Attention</strong>
                <span>60% – 85%</span>
            </div>

            <div class="scale-range scale-range-good">
                <strong>Good</strong>
                <span>85% – 100%</span>
            </div>
        </div>

        <p class="efficiency-above-reference">
            <strong>Above reference (&gt; 100%):</strong>
            values are displayed using the upper end of the color scale and
            should be interpreted according to the selected metric.
        </p>

        <p class="efficiency-scale-guidance">
            <strong>Analysis guidance:</strong>
            Start with the lowest-efficiency metrics and follow their child
            metrics to identify the main factor contributing to the efficiency loss.
        </p>
    </div>
    """


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
    

def _build_trace_header_note(report):
    """Explain the model-aware trace column labels."""

    traces = report.get("traces", [])

    if not traces:
        return ""

    _, programming_model = _split_trace_mode(
        traces[0].get("mode", "unknown")
    )

    model_key = _programming_model_key(
        programming_model
    )

    notes = {
        "mpi": (
            "<b>Trace columns:</b> "
            "<code>MPI ranks [Trace ID]</code>"
        ),
        "openmp": (
            "<b>Trace columns:</b> "
            "<code>Threads [Trace ID]</code>"
        ),
        "pthreads": (
            "<b>Trace columns:</b> "
            "<code>Threads [Trace ID]</code>"
        ),
        "ompss": (
            "<b>Trace columns:</b> "
            "<code>Workers [Trace ID]</code>"
        ),
        "gpu": (
            "<b>Trace columns:</b> "
            "<code>GPU streams [Trace ID]</code>"
        ),
        "mpi_threads": (
            "<b>Trace columns:</b> "
            "<code>Parallel units (MPI ranks × threads/rank) [Trace ID]</code>"
        ),
        "mpi_ompss": (
            "<b>Trace columns:</b> "
            "<code>Parallel units (MPI ranks × workers/rank) [Trace ID]</code>"
        ),
        "mpi_gpu": (
            "<b>Trace columns:</b> "
            "<code>Parallel units (MPI ranks × streams/rank) "
            "[nD = devices] [Trace ID]</code>"
        ),

        "generic": (
            "<b>Trace columns:</b> "
            "<code>Parallel units [Trace ID]</code>"
        ),
    }

    return (
        "<p class='trace-header-note'>{}</p>"
    ).format(notes[model_key])


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

    html_lines.append("<table class='metric-table'>")
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
    else:
        tree = []

    return "\n".join(
        _render_tree_node(node, key_set, metric_info, section_id)
        for node in tree
    )


def _build_metric_tree_heatmap_section(metric_keys, metric_info, metric_sources,
                                        trace_list, trace_labels,
                                        title, section_id,
                                        tree_kind=None,
                                        trace_header_note=""):
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


    efficiency_table_html = _build_efficiency_table_html(
        metric_keys=metric_keys,
        metric_info=metric_info,
        metric_sources=metric_sources,
        trace_list=trace_list,
        trace_labels=trace_labels,
        section_id=section_id,
        tree=tree,
    )

    efficiency_scale_html = _build_efficiency_scale_html()

    info_json = _metric_info_json(metric_keys, metric_info)

    if tree:
        performance_interpretation = (
            observations.build_performance_interpretation(
                tree=tree,
                metric_info=metric_info,
                metric_sources=metric_sources,
                trace_list=trace_list,
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
        )

        observations_html = observations.build_threshold_observation_html(
            observation_groups,
            title="Analysis summary",
        )

    return """
    <script>
    window["metricInfo_{section_id}"] = {info_json};
    </script>
    {efficiency_scale_html}
    {trace_header_note}
    <div class="metric-table-card">
        {efficiency_table_html}
    </div>    

    <div class="metric-info-panel" id="{section_id}-info-panel">
        <h3 id="{section_id}-info-title">Select a metric</h3>
        <p id="{section_id}-info-type" class="metric-info-type"></p>
        <p id="{section_id}-info-meaning">Click a cell in the table to see its value, description, and diagnostic hints.</p>
        <p id="{section_id}-info-interpretation"></p>
        <p id="{section_id}-info-action"></p>
    </div>

    {observations_html}

    """.format(
        section_id=section_id,
        info_json=info_json,
        efficiency_scale_html=efficiency_scale_html,
        trace_header_note=trace_header_note,
        observations_html=observations_html,
        efficiency_table_html=efficiency_table_html,
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


def _metric_value_class(value):
    if value is None:
        return "metric-unavailable"

    if value > 100.0:
        return "metric-above-reference"

    if value < 60.0:
        return "metric-critical"

    if value < 85.0:
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


def _build_metric_definition_table_html(metric_keys, metric_info):
    """Build a static table with metric definitions."""

    if not metric_keys:
        return ""

    lines = []

    lines.append("<div class='metric-definition-section'>")
    lines.append("<h3>Metric definitions</h3>")

    lines.append("<table class='metric-definition-table'>")

    lines.append("<thead>")
    lines.append("<tr>")
    lines.append("<th>Metric</th>")
    lines.append("<th>Definition</th>")
    lines.append("</tr>")
    lines.append("</thead>")

    lines.append("<tbody>")

    for metric_key in metric_keys:
        info = metric_info.get(metric_key, {})

        label = _clean_metric_label(
            info.get("label", metric_key)
        )

        meaning = info.get(
            "meaning",
            "No definition available.",
        )

        lines.append("<tr>")

        lines.append(
            "<td><strong>{}</strong></td>".format(
                html.escape(label)
            )
        )

        lines.append(
            "<td>{}</td>".format(
                html.escape(meaning)
            )
        )

        lines.append("</tr>")

    lines.append("</tbody>")
    lines.append("</table>")
    lines.append("</div>")

    return "\n".join(lines)

def _build_printable_metric_section(
        metric_keys,
        metric_info,
        metric_sources,
        trace_list,
        trace_labels,
        title,
        tree,
        trace_header_note=""):
    """Build a static efficiency section for the printable report."""

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
        )
    )

    performance_html = (
        observations.build_performance_interpretation_html(
            performance_interpretation
        )
    )

    scaling_interpretation = (
        observations.build_scaling_interpretation(
            tree=tree,
            metric_info=metric_info,
            metric_sources=metric_sources,
            trace_list=trace_list,
        )
    )

    scaling_html = (
        observations.build_scaling_interpretation_html(
            scaling_interpretation
        )
    )

    analysis_html = observations.build_analysis_summary_html(
        performance_html=performance_html,
        scaling_html=scaling_html,
        title="Analysis summary",
    )

    definitions_html = _build_metric_definition_table_html(
        metric_keys=metric_keys,
        metric_info=metric_info,
    )

    return """
    <section class="print-metric-section">
        <h2>{title}</h2>

        {trace_header_note}

        <div class="metric-table-card">
            {efficiency_table_html}
        </div>

        {analysis_html}

        {definitions_html}
    </section>
    """.format(
        title=html.escape(title),
        trace_header_note=trace_header_note,
        efficiency_table_html=efficiency_table_html,
        analysis_html=analysis_html,
        definitions_html=definitions_html,
    )


def _build_efficiency_table_html(metric_keys, metric_info, metric_sources,
                                 trace_list, trace_labels, section_id,
                                 tree=None, printable=False):

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
                display_value = "N/A"
                js_value = "null"
            else:
                display_value = "{:.2f}%".format(value)
                js_value = "{:.10f}".format(value)

            value_class = _metric_value_class(value)
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
                    "class='metric-value' "
                    "style='background:{background}; color:{text_color};' "
                    "onclick=\"selectMetricCell("
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
                        display_value=display_value,
                    )
                )

        lines.append("</tr>")

    lines.append("</tbody>")
    lines.append("</table>")
    lines.append("</div>")

    return "\n".join(lines)




def _build_openmp_runtime_scope_note():
    """Explain the scope of the isolated OpenMP runtime metrics."""
    return """
    <div class="analysis-scope-note analysis-scope-warning">
        <h3>Metric scope</h3>
        <p>
            The metrics in this analysis are computed from the OpenMP
            execution independently of the derived hybrid multiplicative model.
        </p>
        <p>
            <strong>OpenMP Region Load Balance</strong> considers only useful
            computation performed inside OpenMP parallel regions. It is therefore
            not directly comparable with the application-level
            <strong>Load Balance</strong> shown in Global Metrics or with the
            derived OpenMP Load Balance shown in the Parallel Runtime Model.
        </p>
    </div>
    """


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


def _build_interactive_report_document(workspace_html):
    """Build the complete interactive HTML document."""
    document = """
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
            display: inline-block;
            min-width: 78px;
            padding: 6px 10px;

            border: 1px solid rgba(30, 50, 70, 0.14);
            border-radius: 999px;

            cursor: pointer;

            font-family: inherit;
            font-size: 13px;
            font-weight: 700;
            font-variant-numeric: tabular-nums;

            transition:
                transform 0.15s ease,
                box-shadow 0.15s ease,
                filter 0.15s ease;
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
            font-size: 14px;
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
            font-size: 13px;
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

        .metric-name-cell {
            position: sticky;
            left: 0;
            z-index: 3;

            min-width: 330px;
            color: #20344d;
            text-align: left;
            box-shadow: 7px 0 10px -10px rgba(20, 38, 63, 0.55);
        }

        .metric-value-cell {
            min-width: 120px;
            background: white;
            text-align: center;
            transition: background 0.15s ease;
        }

        .metric-value {
            display: inline-block;
            min-width: 78px;
            padding: 6px 10px;

            border-radius: 999px;

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
            margin: 24px 8px 30px;
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
            margin: 16px 0 10px;
            color: var(--primary);
            font-size: 17px;
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
        /* Analysis scope notes                                */
        /* -------------------------------------------------- */

        .analysis-scope-note {
            margin-bottom: 22px;
            padding: 18px 20px;
            border: 1px solid #d9c98c;
            border-left: 5px solid #c79a20;
            border-radius: var(--radius-md);
            background: #fffaf0;
            color: #4f452d;
        }

        .analysis-scope-note h3 {
            margin: 0 0 8px;
            color: #6f5617;
            font-size: 17px;
        }

        .analysis-scope-note p {
            margin: 7px 0;
            line-height: 1.65;
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

</style>

        <script>
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
                ".application-panel, .detail-panel"
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

        function initializeWorkspace() {
            initializeStickyHeader();

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

            document.getElementById(sectionId + "-info-title").innerText = info.title;
            document.getElementById(sectionId + "-info-type").innerText = info.type;
            document.getElementById(sectionId + "-info-meaning").innerText = info.meaning;
            document.getElementById(sectionId + "-info-interpretation").innerText =
                "Low values: " + info.low + " Above 100%: " + info.above100;
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

            if (value !== null && value !== undefined && value < 85.0) {
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
                "Next diagnostic step: " + info.action;


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

        <body onload="initializeWorkspace()">

        <header class="report-header">
            <div class="report-header-content">
                <div>
                    <div class="report-brand">BasicAnalysis</div>
                    <h1>Performance Report</h1>
                    <p class="subtitle">
                        Hierarchical efficiency analysis and guided performance diagnosis
                    </p>
                </div>

            </div>
        </header>

        <main class="report-container">""" + """

        {workspace_html}

    """ + """</main>
        </body>
        </html>
        """

    return document.replace('{workspace_html}', workspace_html)

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

    report_traces = report.get("traces", [])

    trace_labels = [
        _report_trace_label(trace_info)
        for trace_info in report_traces
    ]    

    trace_header_note = _build_trace_header_note(
        report
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
        )
    else:
        hybrid_html = "<p>Parallel programming model metrics are not available for simple traces.</p>"

    # ---- MPI+GPU execution-domain and device-runtime metrics
    host_html = "<p>Host execution-domain metrics are only available for MPI+GPU traces.</p>"
    device_html = "<p>Device execution-domain metrics are only available for MPI+GPU traces.</p>"

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
        )


    # ---- OpenMP runtime-specific efficiency metrics
    openmp_filtered_keys = []

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
            )
            openmp_html = (
                _build_openmp_runtime_scope_note()
                + openmp_metrics_html
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
        report
    )    
    
    resources_html = _build_resources_table_html(report)


    application_html = _build_application_summary_panel(
        trace_config_html=trace_config_html,
        trace_header_note=trace_header_note,
        overview_html=overview_html,
        resources_html=resources_html,
        global_html=global_html,
    )

    runtime_model_views = []
    runtime_analysis_views = []
    domain_views = []

    # --------------------------------------------------
    # Parallel Runtime Model
    # --------------------------------------------------
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

        # --------------------------------------------------
        # Runtime-Specific Analysis
        # --------------------------------------------------
        # The isolated OpenMP analysis is computed independently from the
        # derived MPI+OpenMP multiplicative decomposition.
        if model["has_omp"] and openmp_filtered_keys:
            runtime_analysis_views.append({
                "id": "runtime-analysis-openmp",
                "label": "OpenMP",
                "title": "OpenMP Runtime-Specific Analysis",
                "html": openmp_html,
            })

        # --------------------------------------------------
        # Execution Domain
        # --------------------------------------------------
        # Host and Device views are execution-domain analyses. They must not
        # be presented as CUDA runtime-specific analyses.
        if model["has_cuda"]:
            domain_views.extend([
                {
                    "id": "domain-host",
                    "label": "Host",
                    "title": "Host Execution Domain",
                    "html": host_html,
                },
                {
                    "id": "domain-device",
                    "label": "Device",
                    "title": "Device Execution Domain",
                    "html": device_html,
                },
            ])

    detail_html = _build_detail_panel(
        runtime_model_views=runtime_model_views,
        runtime_analysis_views=runtime_analysis_views,
        domain_views=domain_views,
    )

    workspace_html = _build_workspace_layout(
        application_html=application_html,
        detail_html=detail_html,
    )

    html_content = _build_interactive_report_document(
        workspace_html=workspace_html,
    )

    with open(output_html, "w") as output_file:
        output_file.write(html_content)

    print("Interactive report written to {}".format(output_html))

    return output_html


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
    """Generate printable BasicAnalysis HTML report."""

    output_html = os.path.join(
        os.getcwd(),
        "basicanalysis_printable_report.html",
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

    inner_model = _inner_model_name(
        trace_mode,
        trace_list,
    )

    hybrid_metric_info = _build_hybrid_metric_info(
        inner_model
    )
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

    global_filtered_keys = []

    for key in global_keys:
        if key not in mod_factors:
            continue

        for trace in trace_list:
            if _clean_value(
                _read_metric(mod_factors, key, trace)
            ) is not None:
                global_filtered_keys.append(key)
                break

    global_sources = {
        key: mod_factors
        for key in global_filtered_keys
    }

    global_html = _build_printable_metric_section(
        metric_keys=global_filtered_keys,
        metric_info=global_metric_info,
        metric_sources=global_sources,
        trace_list=trace_list,
        trace_labels=trace_labels,
        title="Global Efficiency Metrics",
        tree=global_tree,
        trace_header_note=trace_header_note,
    )


    hybrid_html = ""

    if metrics_result["kind"] == "hybrid":
        hybrid_keys = list(HYBRID_ORDER)

        if inner_model == "OpenMP" and cmdl_args.hyb_mpiomp:
            hybrid_keys += OMP_COMM_ORDER

        hybrid_sources = {}

        for key in HYBRID_ORDER:
            hybrid_sources[key] = hybrid_factors

        for key in OMP_COMM_ORDER:
            hybrid_sources[key] = hyb_comm_omp_factors

        hybrid_filtered_keys = []

        for key in hybrid_keys:
            source = hybrid_sources[key]

            for trace in trace_list:
                if _clean_value(
                    _read_metric(source, key, trace)
                ) is not None:
                    hybrid_filtered_keys.append(key)
                    break

        if hybrid_filtered_keys:
            hybrid_html = _build_printable_metric_section(
                metric_keys=hybrid_filtered_keys,
                metric_info=hybrid_metric_info,
                metric_sources=hybrid_sources,
                trace_list=trace_list,
                trace_labels=trace_labels,
                title="Parallel Programming Model: MPI + {}".format(
                    inner_model
                ),
                tree=HYBRID_TREE,
                trace_header_note=trace_header_note,
            )


    talp_html = ""

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

        talp_keys = host_keys + device_keys
        talp_sources = {}

        for key in host_keys:
            if key in (
                "ipc_scale",
                "inst_scale",
                "freq_scale",
            ):
                talp_sources[key] = mod_factors
            else:
                talp_sources[key] = host_factors

        for key in device_keys:
            talp_sources[key] = device_factors

        talp_filtered_keys = []

        for key in talp_keys:
            source = talp_sources[key]

            for trace in trace_list:
                if _clean_value(
                    _read_metric(source, key, trace)
                ) is not None:
                    talp_filtered_keys.append(key)
                    break

        if talp_filtered_keys:
            talp_html = _build_printable_metric_section(
                metric_keys=talp_filtered_keys,
                metric_info=TALP_METRIC_INFO,
                metric_sources=talp_sources,
                trace_list=trace_list,
                trace_labels=trace_labels,
                title="Host/Device Efficiency Metrics",
                tree=TALP_TREE,
                trace_header_note=trace_header_note,
            )

    openmp_html = ""

    if (
        metrics_result["kind"] == "hybrid"
        and "omp_talp_factors" in metrics_result
    ):
        omp_talp_factors = metrics_result[
            "omp_talp_factors"
        ]

        openmp_filtered_keys = []

        for key in OPENMP_ORDER:
            if key not in omp_talp_factors:
                continue

            for trace in trace_list:
                if _clean_value(
                    _read_metric(
                        omp_talp_factors,
                        key,
                        trace,
                    )
                ) is not None:
                    openmp_filtered_keys.append(key)
                    break

        if openmp_filtered_keys:
            openmp_sources = {
                key: omp_talp_factors
                for key in openmp_filtered_keys
            }

            openmp_metrics_html = _build_printable_metric_section(
                metric_keys=openmp_filtered_keys,
                metric_info=OPENMP_METRIC_INFO,
                metric_sources=openmp_sources,
                trace_list=trace_list,
                trace_labels=trace_labels,
                title="OpenMP Runtime-Specific Analysis",
                tree=OPENMP_TREE,
                trace_header_note=trace_header_note,
            )
            openmp_html = (
                _build_openmp_runtime_scope_note()
                + openmp_metrics_html
            )



    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>BasicAnalysis Performance Report</title>

        <style>
            @page {{
                size: A4 landscape;
                margin: 12mm;
            }}

            * {{
                box-sizing: border-box;
            }}

            body {{
                margin: 0;
                color: #172033;
                font-family:
                    -apple-system,
                    BlinkMacSystemFont,
                    "Segoe UI",
                    Roboto,
                    Helvetica,
                    Arial,
                    sans-serif;
                font-size: 10pt;
                line-height: 1.5;
            }}

            .print-header {{
                margin-bottom: 24px;
                padding: 18px 22px;
                background: #17365d;
                color: white;
            }}

            .print-header h1 {{
                margin: 0 0 5px;
                font-size: 22pt;
            }}

            .print-header p {{
                margin: 0;
                color: #d8e7f5;
            }}

            .print-section {{
                margin-bottom: 28px;
            }}

            .print-metric-section {{
                break-before: page;
            }}

            h2 {{
                margin: 0 0 14px;
                color: #17365d;
                font-size: 17pt;
            }}

            h3 {{
                color: #243b58;
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
                padding: 6px 8px;
                border: 1px solid #dce3ec;
            }}

            .metric-table th,
            .efficiency-table th,
            .metric-definition-table th {{
                background: #edf3f9;
                color: #29435f;
                text-align: left;
            }}

            .efficiency-table th:not(:first-child),
            .efficiency-table td:not(:first-child) {{
                text-align: center;
            }}

            .metric-name-cell {{
                padding-left: calc(
                    8px + (var(--metric-depth, 0) * 16px)
                ) !important;
            }}

            .metric-value {{
                display: inline-block;
                min-width: 60px;
                padding: 4px 7px;
                border-radius: 999px;
                font-size: 8.5pt;
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

            .observation-box {{
                margin: 18px 0;
                padding: 14px 16px;
                border: 1px solid #b7cbe3;
                border-left: 5px solid #4c83bd;
                background: #f4f8ff;
            }}

            .performance-interpretation p,
            .scaling-interpretation p {{
                color: #31465d;
                font-size: 10pt;
                line-height: 1.6;
            }}

            .metric-definition-section {{
                margin-top: 20px;
            }}

            .metric-definition-table {{
                font-size: 9pt;
            }}

            .metric-definition-table td:first-child {{
                width: 28%;
            }}

            .trace-header-note {{
                color: #5c677a;
                font-size: 9pt;
            }}

            table {{
                break-inside: auto;
            }}

            thead {{
                display: table-header-group;
            }}

            tr {{
                break-inside: avoid;
            }}

            .metric-table-card,
            .observation-box {{
                break-inside: avoid;
            }}

            .analysis-scope-note {{
                margin: 18px 0;
                padding: 14px 16px;
                border: 1px solid #d9c98c;
                border-left: 5px solid #c79a20;
                background: #fffaf0;
                color: #4f452d;
                break-inside: avoid;
            }}

            .analysis-scope-note h3 {{
                margin: 0 0 6px;
                color: #6f5617;
            }}

            .analysis-scope-note p {{
                margin: 6px 0;
            }}

            .efficiency-scale-panel {{
                margin: 0;
                padding: 18px 22px;
                border: 1px solid #d7e0ea;
                border-radius: 8px;
                background: #ffffff;
            }}

            .efficiency-scale-header h3 {{
                margin: 0 0 4px;
            }}

            .efficiency-scale-header p {{
                margin: 0 0 14px;
                color: #5c677a;
            }}

            .efficiency-gradient-container {{
                position: relative;
                margin: 12px 10px 28px;
            }}

            .efficiency-gradient {{
                height: 16px;
                border-radius: 8px;
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
            }}

            .efficiency-gradient-markers {{
                position: relative;
                height: 16px;
                margin-top: 5px;
                color: #5c677a;
                font-size: 8pt;
            }}

            .efficiency-gradient-markers span {{
                position: absolute;
                transform: translateX(-50%);
            }}

            .efficiency-gradient-markers span:first-child {{
                transform: none;
            }}

            .efficiency-gradient-markers span:last-child {{
                transform: translateX(-100%);
            }}

            .efficiency-scale-ranges {{
                display: grid;
                grid-template-columns: 60fr 25fr 15fr;
                border: 1px solid #d7e0ea;
            }}

            .scale-range {{
                display: flex;
                justify-content: space-between;
                padding: 8px 12px;
                border-top: 3px solid;
            }}

            .scale-range-critical {{
                border-top-color: #ef4444;
            }}

            .scale-range-attention {{
                border-top-color: #f4c76b;
            }}

            .scale-range-good {{
                border-top-color: #69b34c;
            }}

            .efficiency-above-reference,
            .efficiency-scale-guidance {{
                color: #4b5f78;
                font-size: 9pt;
            }}

            .efficiency-scale-guidance {{
                padding-top: 10px;
                border-top: 1px solid #d7e0ea;
            }}
        </style>
    </head>

    <body>

        <header class="print-header">
            <h1>BasicAnalysis Performance Report </h1>
            <p>
                Hierarchical efficiency analysis and guided performance diagnosis
            </p>
        </header>

        <section class="print-section">
            <h2>Execution Overview</h2>

            <h3>Trace configuration</h3>
            {trace_config_html}

            <h3>General metrics</h3>
            {trace_header_note}
            {overview_html}
        </section>

        <section class="print-section">
            {efficiency_scale_html}
        </section>

        {global_html}
        {hybrid_html}
        {talp_html}
        {openmp_html}


    </body>
    </html>
    """.format(
        trace_config_html=trace_config_html,
        trace_header_note=trace_header_note,
        overview_html=overview_html,
        efficiency_scale_html=efficiency_scale_html,
        global_html=global_html,
        hybrid_html=hybrid_html,
        talp_html=talp_html,
        openmp_html=openmp_html,
    )

    with open(output_html, "w") as output_file:
        output_file.write(html_content)

    print(
        "Printable report written to {}".format(
            output_html
        )
    )

    return output_html
    