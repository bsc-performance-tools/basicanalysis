#!/usr/bin/env python3

"""Analyze one Paraver trace and save the per-trace rawdata result."""

from __future__ import print_function, division

import argparse
import os

from rawdata import init_cfgs, process_one_trace, save_trace_result
from tracemetadata import get_traces_from_args
from utils import build_argument_parser, check_installation, create_temp_folder, which


def parse_single_trace_args():
    parser = build_argument_parser()
    parser.description = "Analyze one Paraver trace and save the per-trace rawdata result."

    parser.add_argument(
        "--output-dir",
        default=".",
        help="Directory where the per-trace JSON result will be written (default: current directory)"
    )

    args = parser.parse_args()

    if len(args.trace_list) != 1:
        parser.error("analyze_trace.py expects exactly one input trace.")

    return args


def get_default_result_filename(trace):
    """Build the default JSON filename from the trace name."""
    base = os.path.basename(trace)

    if base.endswith(".prv.gz"):
        base = base[:-7]
    elif base.endswith(".prv"):
        base = base[:-4]

    return base + ".rawdata.json"


def main():
    cmdl_args = parse_single_trace_args()

    check_installation(cmdl_args)

    trace_list, trace_processes, trace_tasks, trace_threads, trace_task_per_node, trace_mode = \
        get_traces_from_args(cmdl_args)

    if len(trace_list) != 1:
        raise RuntimeError(
            "Expected exactly one valid trace after filtering, but got {}".format(len(trace_list))
        )

    trace = trace_list[0]

    cfgs = init_cfgs()
    dimemas_available = which('Dimemas') is not None
    path_dest = create_temp_folder('scratch_out_basicanalysis', cmdl_args)

    result = process_one_trace(
        trace=trace,
        trace_process_count=trace_processes[trace],
        trace_task_per_node_value=trace_task_per_node[trace],
        trace_mode_value=trace_mode[trace],
        trace_tasks_value=trace_tasks[trace],
        trace_threads_value=trace_threads[trace],
        cmdl_args=cmdl_args,
        cfgs=cfgs,
        dimemas_available=dimemas_available,
        path_dest=path_dest,
    )

    os.makedirs(cmdl_args.output_dir, exist_ok=True)
    output_path = os.path.join(cmdl_args.output_dir, get_default_result_filename(trace))

    save_trace_result(result, output_path)

    print("Per-trace rawdata result written to {}".format(output_path))


if __name__ == "__main__":
    main()