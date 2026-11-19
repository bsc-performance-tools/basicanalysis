#!/usr/bin/env python3

"""results.json: all the results of a BasicAnalysis run in one file.

The file is the contract between the analysis, which runs on the cluster,
and the tools that explore the results elsewhere: the desktop application
(doc/design/desktop_app.rst), the MCP server, and user scripts. It contains
the run, the traces with their configuration labels, every metric of every
model per trace with its hierarchy, and the raw data. The CSV files and the
HTML report do not change.

The format is versioned with SCHEMA_VERSION: tools must check it, and new
fields can be added without changing the version; renamed or removed fields
change it.
"""

from __future__ import print_function

import datetime
import json
import math
import os
import re
import subprocess
import sys
from collections import OrderedDict

from configuration import configuration_description, split_trace_mode
from tracemetadata import NSYS2PRV_DISPLAY_MODE

SCHEMA = "basicanalysis-results"
SCHEMA_VERSION = 1
FILE_NAME = "results.json"

# Values that are not numbers: kept as strings (JSON has no NaN).
_NOT_AVAILABLE = ("Non-Avail", "N/A", "NaN", "Warning!", "")


def _basicanalysis_info():
    from utils import __version__
    info = OrderedDict([("version", __version__), ("commit", None)])
    source_dir = os.path.dirname(os.path.realpath(__file__))
    try:
        commit = subprocess.check_output(
            ["git", "-C", source_dir, "rev-parse", "--short", "HEAD"],
            stderr=subprocess.DEVNULL, timeout=5).decode().strip()
        info["commit"] = commit or None
    except (OSError, subprocess.SubprocessError):
        pass
    return info


def _count(value):
    """A count of the trace (processes, devices...) as an int when possible."""
    value = _json_value(value)
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


def _json_value(value):
    """A metric value as JSON: a number, or a string such as "Non-Avail"."""
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if math.isnan(number) or math.isinf(number):
        return "NaN"
    if isinstance(value, str) and value.strip() in _NOT_AVAILABLE:
        return value.strip()
    return int(number) if number.is_integer() and not isinstance(value, float) else number


def _options(cmdl_args):
    """Command-line options that change the results."""
    names = ("metrics", "scaling", "workload", "pop_model_to_apply",
             "skip_simulation", "simulation_openmp", "simulation_cuda",
             "ideal_omp", "hyb_mpiomp", "trace_mode_detection", "order_traces",
             "limit", "max_trace_size")
    options = OrderedDict()
    for name in names:
        if hasattr(cmdl_args, name):
            value = getattr(cmdl_args, name)
            options[name] = value if isinstance(value, (str, int, float, bool, type(None))) \
                else str(value)
    for name in vars(cmdl_args):
        if name.endswith("_workload") and getattr(cmdl_args, name) is not None:
            options[name] = str(getattr(cmdl_args, name))
    thresholds = getattr(cmdl_args, "thresholds", None)
    if thresholds is not None:
        options["thresholds"] = OrderedDict([
            ("critical", thresholds.critical), ("attention", thresholds.attention)])
    return options


def _display_mode(mode):
    collection_mode, programming_model = split_trace_mode(mode)
    if collection_mode == "nsys2prv":
        return NSYS2PRV_DISPLAY_MODE
    return programming_model.replace(" + ", "+") if programming_model != "Unknown" else mode


def _trace_label(trace_info):
    """Configuration label of the report (8 × 1 GPU, 56 (14×4), 16)."""
    try:
        from interactiveplots import _report_trace_label
        return _report_trace_label(trace_info, include_trace_id=False)
    except Exception:
        return str(trace_info.get("processes"))


def _traces(trace_list, trace_processes, trace_tasks, trace_threads, trace_mode,
            raw_data, cmdl_args):
    from reportdata import _build_traces
    infos = _build_traces(
        trace_list, trace_processes, trace_tasks, trace_threads, trace_mode,
        raw_data,
        getattr(cmdl_args, "simulated_traces", ()),
        getattr(cmdl_args, "inconsistent_simulations", ()),
    )
    traces = []
    for info in infos:
        traces.append(OrderedDict([
            ("id", "T{}".format(info["id"])),
            ("name", info["name"]),
            ("path", os.path.abspath(info["path"])),
            ("mode", info["mode"]),
            ("display_mode", _display_mode(info["mode"])),
            ("label", _trace_label(info)),
            ("processes", _count(info["processes"])),
            ("mpi_ranks", _count(info["tasks"])),
            ("threads", _count(info["threads"])),
            ("devices", _count(info["devices"])),
            ("gpu_streams", _count(info["gpu_streams"])),
            ("gpu_streams_per_rank", _count(info["gpu_streams_per_rank"])),
            ("simulated", bool(info["simulated"])),
            ("inconsistent_simulation", bool(info["inconsistent"])),
        ]))
    return traces


def _overview_tables(trace_list, trace_processes, trace_tasks, trace_threads,
                     trace_mode, raw_data, cmdl_args):
    """The Trace configuration and Execution mapping tables of the report,
    with the columns that the report uses for the programming model."""
    from reportdata import _build_traces
    from report.renderer.html.overview import (
        _execution_mapping_columns, _overview_model_key, _split_trace_mode,
        _trace_resource_columns)
    infos = _build_traces(
        trace_list, trace_processes, trace_tasks, trace_threads, trace_mode,
        raw_data,
        getattr(cmdl_args, "simulated_traces", ()),
        getattr(cmdl_args, "inconsistent_simulations", ()),
    )
    if not infos:
        return None
    collection_mode, programming_model = _split_trace_mode(infos[0]["mode"])
    model_key = _overview_model_key(collection_mode, programming_model)
    resource_columns = _trace_resource_columns(model_key)
    mapping_columns = _execution_mapping_columns(model_key)

    def mapping_value(mapping, field):
        if isinstance(mapping, dict):
            value = mapping.get(field)
        else:
            value = getattr(mapping, field, None) if mapping is not None else None
        if value == -1:
            return "Non-uniform"
        return _count(value) if value is not None else None

    configuration = OrderedDict([
        ("columns", ["ID", "Trace", "Programming model"]
         + [label for _field, label in resource_columns]),
        ("rows", []),
    ])
    mapping = OrderedDict([
        ("columns", ["ID", "Trace"] + [label for _field, label in mapping_columns]),
        ("rows", []),
    ])
    for info in infos:
        trace_id = "T{}".format(info["id"])
        model = _split_trace_mode(info["mode"])[1].replace(" + ", "+")
        configuration["rows"].append(
            [trace_id, info["name"], model]
            + [_count(info.get(field)) for field, _label in resource_columns])
        mapping["rows"].append(
            [trace_id, info["name"]]
            + [mapping_value(info.get("mapping"), field) for field, _label in mapping_columns])
    return OrderedDict([("trace_configuration", configuration),
                        ("execution_mapping", mapping)])


def _hierarchy(doc):
    """Level and parent of each metric of a table, from the indentation and
    the '--' / '==' markers of its stdout labels."""
    rows = []
    parents = []  # stack of (level, key)
    for key, label in doc.items():
        raw = str(label)
        spaces = len(raw) - len(raw.lstrip())
        text = raw.strip()
        marker = text[:2] in ("--", "==")
        if marker:
            text = text[2:].strip()
        level = 0 if not marker else 1 + int(round(spaces / 3.0))
        while parents and parents[-1][0] >= level:
            parents.pop()
        parent = parents[-1][1] if parents else None
        parents.append((level, key))
        rows.append((key, text, level, parent))
    # The root of each table is level 0 (the Hybrid table starts with a
    # marked row).
    lowest = min((row[2] for row in rows), default=0)
    return [(key, text, level - lowest, parent) for key, text, level, parent in rows]


def _metric_name(key, label):
    try:
        from metrics import get_default_provider
        return get_default_provider().get(key).name
    except Exception:
        return label


# Units written at the end of the stdout labels: "Elapsed time (sec)".
_LABEL_UNITS = {"sec": "s", "s": "s", "us": "us", "ns": "ns", "%": "%",
                "GHz": "GHz", "MHz": "MHz", "B": "B", "KiB": "KiB",
                "MiB": "MiB", "GiB": "GiB", "MB/s": "MB/s", "GB/s": "GB/s"}


def _unit(label, default):
    match = re.search(r"\(([^()]*)\)\s*$", label)
    if match and match.group(1) in _LABEL_UNITS:
        return _LABEL_UNITS[match.group(1)]
    return default


def _model(model_id, name, values, doc, trace_ids, trace_list, unit="%"):
    metrics = []
    for key, label, level, parent in _hierarchy(doc):
        if key not in values:
            continue
        per_trace = values[key]
        metrics.append(OrderedDict([
            ("key", key),
            ("name", _metric_name(key, label)),
            ("label", label),
            ("level", level),
            ("parent", parent),
            ("unit", _unit(label, unit)),
            ("values", OrderedDict(
                (trace_id, _json_value(per_trace.get(trace)))
                for trace_id, trace in zip(trace_ids, trace_list))),
        ]))
    return OrderedDict([("id", model_id), ("name", name), ("metrics", metrics)])


def _models(metrics_result, trace_list, trace_ids, trace_mode):
    """The metric tables of the run, in the order of the report."""
    from report.model_names import APPLICATION, DEVICE_DOMAIN, HOST_DOMAIN
    if metrics_result.get("kind") == "hybrid":
        import hybridmetrics as metrics_module
    else:
        import simplemetrics as metrics_module
    from nsys2prvmetrics import mod_device_hwc_factors_doc

    tables = [
        ("general", "General", "other_metrics", "other_metrics_doc", None),
        ("application", APPLICATION, "mod_factors", "mod_factors_doc", "%"),
        ("scalability_io", "Computation scalability with I/O",
         "mod_factors_scale_plus_io", "mod_factors_scale_plus_io_doc", "%"),
        ("hybrid", "Hybrid", "hybrid_factors", "mod_hybrid_factors_doc", "%"),
        ("hybrid_inner_comm", "Hybrid inner communication",
         "hyb_comm_omp_factors", "mod_hyb_comm_omp_factors_doc", "%"),
        ("host", HOST_DOMAIN, "host_factors", "mod_host_factors_doc", "%"),
        ("device", DEVICE_DOMAIN, "device_factors", "mod_device_factors_doc", "%"),
        ("openmp_runtime", "OpenMP runtime", "omp_talp_factors", "mod_omp_factors_doc", "%"),
    ]
    gpu_traces = any(_is_gpu_mode(trace_mode[trace]) for trace in trace_list)
    models = []
    for model_id, name, result_key, doc_name, unit in tables:
        if model_id in ("host", "device") and not gpu_traces:
            continue
        values = metrics_result.get(result_key)
        doc = getattr(metrics_module, doc_name, None)
        if not values or doc is None or not _has_values(values, trace_list):
            continue
        models.append(_model(model_id, name, values, doc, trace_ids, trace_list, unit))

    hwc = metrics_result.get("device_hwc_factors")
    if hwc and _has_values(hwc, trace_list):
        models.append(_model("gpu_hardware_counters", "GPU Hardware Counters", hwc,
                             mod_device_hwc_factors_doc, trace_ids, trace_list, "%"))
    return models


def _is_gpu_mode(mode):
    from tracemetadata import is_host_gpu_mode, is_nsys2prv_mode
    from hybridmetrics import is_mpi_gpu_mode
    return is_mpi_gpu_mode(mode) or is_host_gpu_mode(mode) or is_nsys2prv_mode(mode)


def _has_values(values, trace_list):
    for per_trace in values.values():
        if not isinstance(per_trace, dict):
            continue
        for trace in trace_list:
            value = per_trace.get(trace)
            if _json_value(value) not in (None, "Non-Avail", "N/A", "NaN", ""):
                return True
    return False


def _raw_data(raw_data, trace_list, trace_ids):
    result = OrderedDict()
    for key, per_trace in raw_data.items():
        if not isinstance(per_trace, dict):
            continue
        result[key] = OrderedDict(
            (trace_id, _json_value(per_trace.get(trace)))
            for trace_id, trace in zip(trace_ids, trace_list))
    return result


def _scaling(scaling_info):
    """The scaling model (scaling.ScalingInfo) as JSON."""
    if scaling_info is None:
        return None
    data = scaling_info if isinstance(scaling_info, dict) else vars(scaling_info)
    return json.loads(json.dumps(data, default=_json_default))


def _json_default(value):
    if hasattr(value, "__dict__"):
        return vars(value)
    return str(value)


def build_results(metrics_result, analysis_result, trace_list, trace_processes,
                  trace_tasks, trace_threads, trace_mode, cmdl_args):
    """Build the content of results.json (a JSON-serializable dict)."""
    raw_data = analysis_result.get("raw_data", {})
    traces = _traces(trace_list, trace_processes, trace_tasks, trace_threads,
                     trace_mode, raw_data, cmdl_args)
    trace_ids = [trace["id"] for trace in traces]

    return OrderedDict([
        ("schema", SCHEMA),
        ("schema_version", SCHEMA_VERSION),
        ("basicanalysis", _basicanalysis_info()),
        ("run", OrderedDict([
            ("date", datetime.datetime.now().astimezone().isoformat(timespec="seconds")),
            ("command", " ".join(sys.argv)),
            ("directory", os.getcwd()),
            ("analysis_kind", metrics_result.get("kind")),
            ("options", _options(cmdl_args)),
            ("scaling", _scaling(metrics_result.get("scaling_info"))),
        ])),
        ("configuration_meaning",
         configuration_description([trace_mode[trace] for trace in trace_list])),
        ("traces", traces),
        ("overview", _overview_tables(trace_list, trace_processes, trace_tasks,
                                      trace_threads, trace_mode, raw_data, cmdl_args)),
        ("models", _models(metrics_result, trace_list, trace_ids, trace_mode)),
        ("raw_data", _raw_data(raw_data, trace_list, trace_ids)),
        ("files", OrderedDict([
            ("report", "basicanalysis_interactive_report.html"),
            ("cfgs_report", "cfgs-report"),
        ])),
    ])


def write_results_json(metrics_result, analysis_result, trace_list, trace_processes,
                       trace_tasks, trace_threads, trace_mode, cmdl_args,
                       path=FILE_NAME):
    """Write results.json in the current folder; never stops the analysis."""
    try:
        results = build_results(metrics_result, analysis_result, trace_list,
                                trace_processes, trace_tasks, trace_threads,
                                trace_mode, cmdl_args)
        with open(path, "w", encoding="utf-8") as output:
            json.dump(results, output, indent=1, ensure_ascii=False)
            output.write("\n")
    except Exception as error:  # the CSV files and the report are still valid
        print("==WARNING== results.json could not be written: {}".format(error))
        return None
    print("Results (machine-readable) written to " + os.path.abspath(path))
    return path
