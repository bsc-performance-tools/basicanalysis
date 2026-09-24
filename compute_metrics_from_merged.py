#!/usr/bin/env python3

"""Compute metrics from merged rawdata JSON."""

from __future__ import print_function, division

import json

from pipeline import count_hybrid_traces, compute_metrics, generate_reports, generate_plots
from utils import build_argument_parser
from argparse import SUPPRESS

def parse_args():
    parser = build_argument_parser()
    parser.description = "Compute metrics from merged rawdata JSON."

    parser.add_argument(
        "--merged-input",
        required=True,
        help="Merged rawdata JSON file"
    )

    hidden_options = [
        "--jobs",
        "--mem-per-worker-gb",
        "--simulation_openmp",
        "--simulation_cuda",
        "--ideal-omp",
        "--max_trace_size",
    ]

    for action in parser._actions:
        if any(opt in hidden_options for opt in action.option_strings):
            action.help = SUPPRESS

    args = parser.parse_args()

    if len(args.trace_list) != 0:
        parser.error(
            "compute_metrics_from_merged.py does not accept trace arguments. "
            "Use --merged-input <file> instead."
        )

    return args


def main():
    cmdl_args = parse_args()

    with open(cmdl_args.merged_input) as f:
        merged = json.load(f)

    trace_list = merged["trace_list"]
    trace_processes = merged["trace_processes"]
    trace_tasks = merged["trace_tasks"]
    trace_threads = merged["trace_threads"]
    trace_task_per_node = merged["trace_task_per_node"]
    trace_mode = merged["trace_mode"]
    raw_data = merged["raw_data"]
    io_data = merged["io_data"]
    list_mpi_procs_count = merged["list_mpi_procs_count"]

    analysis_result = {
        "raw_data": raw_data,
        "io_data": io_data,
        "list_mpi_procs_count": list_mpi_procs_count,
    }

    trace_metrics = count_hybrid_traces(trace_list, trace_mode)

    metrics_result = compute_metrics(
        analysis_result,
        trace_list,
        trace_processes,
        trace_tasks,
        trace_threads,
        trace_mode,
        cmdl_args,
        trace_metrics,
    )

    generate_reports(
        metrics_result,
        analysis_result,
        trace_list,
        trace_processes,
        trace_tasks,
        trace_threads,
        trace_mode,
        cmdl_args,
    )

    generate_plots(
        metrics_result,
        analysis_result,
        trace_list,
        trace_processes,
        trace_tasks,
        trace_threads,
        trace_mode,
        cmdl_args,
    )


if __name__ == "__main__":
    main()