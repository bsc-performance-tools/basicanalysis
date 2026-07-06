#!/usr/bin/env python3

"""Common report data model for BasicAnalysis reports."""

from __future__ import print_function, division

import os
import shutil

def build_report(metrics_result,
                 analysis_result,
                 trace_list,
                 trace_processes,
                 trace_tasks,
                 trace_threads,
                 trace_mode,
                 cmdl_args):
    """
    Build a common report model to be consumed by HTML, PDF, and future
    report-generation backends.
    """
    
    output_dir = os.getcwd()

    report = {
        "general": _build_general(metrics_result, cmdl_args),
        "traces": _build_traces(
            trace_list,
            trace_processes,
            trace_tasks,
            trace_threads,
            trace_mode,
        ),
        "resources": _build_resources(trace_list, output_dir),
        "metrics": metrics_result,
        "diagnosis": [],
        "evidence": [],
    }

    return report


def _build_general(metrics_result, cmdl_args):
    return {
        "analysis_kind": metrics_result.get("kind", "unknown"),
        "pop_model": getattr(cmdl_args, "pop_model_to_apply", "unknown"),
    }


def _build_traces(trace_list,
                  trace_processes,
                  trace_tasks,
                  trace_threads,
                  trace_mode):
    traces = []

    for index, trace in enumerate(trace_list):
        traces.append({
            "id": index + 1,
            "name": os.path.basename(trace),
            "path": trace,
            "mode": trace_mode.get(trace, "unknown"),
            "processes": trace_processes.get(trace, "unknown"),
            "tasks": trace_tasks.get(trace, "unknown"),
            "threads": trace_threads.get(trace, "unknown"),
        })

    return traces


def _strip_trace_extension(trace):
    if trace.endswith(".prv.gz"):
        return trace[:-7]
    if trace.endswith(".prv"):
        return trace[:-4]
    return os.path.splitext(trace)[0]


def _cfgs_report_source_dir():
    return os.path.join(
        os.path.dirname(os.path.realpath(__file__)),
        "cfgs-report"
    )


def _ensure_report_cfg(output_dir, cfg_name):
    """
    Copy the report Paraver cfg into the output directory.

    Source:
        <basicanalysis>/cfgs-report/useful_duration.cfg

    Destination:
        <output_dir>/cfgs-report/useful_duration.cfg
    """
    src_dir = _cfgs_report_source_dir()
    src_path = os.path.join(src_dir, cfg_name)

    dst_dir = os.path.join(output_dir, "cfgs-report")
    dst_path = os.path.join(dst_dir, cfg_name)

    os.makedirs(dst_dir, exist_ok=True)

    if os.path.exists(src_path):
        shutil.copyfile(src_path, dst_path)
    else:
        # Keep report generation alive, but make the missing cfg explicit.
        with open(dst_path, "w") as f:
            f.write("# Missing source cfg: {}\n".format(src_path))

    return dst_path


def _build_resources(trace_list, output_dir):
    resources = []

    cfg_path = _ensure_report_cfg(output_dir, "useful_duration.cfg")

    for trace in trace_list:
        base = _strip_trace_extension(trace)

        resources.append({
            "trace": trace,
            "prv": trace,
            "pcf": base + ".pcf",
            "row": base + ".row",
            "overview_cfg": cfg_path,
            "cfgs": [],
            "images": [],
        })

    return resources