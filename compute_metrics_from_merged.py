#!/usr/bin/env python3

"""Compute metrics from merged rawdata JSON."""

from __future__ import print_function, division

import json

from pipeline import count_hybrid_traces, compute_metrics, generate_reports, generate_plots
from utils import build_argument_parser



def parse_args():
    """
    Reuse the main BasicAnalysis parser and add one extra argument for the
    merged rawdata JSON file.
    """
    parser = build_argument_parser()
    parser.description = "Compute metrics from merged rawdata JSON."

    parser.add_argument(
        "--merged-input",
        required=True,
        help="Merged rawdata JSON file"
    )

    args = parser.parse_args()

    # This script does not consume trace files directly.
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
    list_mpi_procs_count = merged["list_mpi_procs_count"]

    analysis_result = {
        "raw_data": raw_data,
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