#!/usr/bin/env python3

"""modelfactors.py Generates performance metrics from a set of Paraver traces."""

from __future__ import print_function, division

from pipeline import count_hybrid_traces, compute_metrics, generate_reports, generate_plots
from rawdata import gather_raw_data, print_raw_data_csv
from tracemetadata import get_traces_from_args
from utils import parse_arguments, check_installation


def analyze_traces(trace_list, trace_processes, trace_task_per_node,
                   trace_mode, trace_tasks, trace_threads, cmdl_args):
    raw_data, io_data, list_mpi_procs_count = gather_raw_data(
        trace_list,
        trace_processes,
        trace_task_per_node,
        trace_mode,
        trace_tasks,
        trace_threads,
        cmdl_args,
    )
    print_raw_data_csv(raw_data, trace_list, trace_processes)

    return {
        "raw_data": raw_data,
        "io_data": io_data,
        "list_mpi_procs_count": list_mpi_procs_count,
    }


def main():
    cmdl_args = parse_arguments()

    check_installation(cmdl_args)

    trace_list, trace_processes, trace_tasks, trace_threads, trace_task_per_node, trace_mode = \
        get_traces_from_args(cmdl_args)

    trace_metrics = count_hybrid_traces(trace_list, trace_mode)

    analysis_result = analyze_traces(
        trace_list,
        trace_processes,
        trace_task_per_node,
        trace_mode,
        trace_tasks,
        trace_threads,
        cmdl_args,
    )

    print("\nI/O DATA:")
    print(analysis_result["io_data"])

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
