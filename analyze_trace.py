#!/usr/bin/env python3

"""Analyze Paraver traces and save independent per-trace rawdata results."""

from __future__ import print_function, division

from rawdata import run_trace_analyses_to_files
from tracemetadata import get_traces_from_args
from utils import build_argument_parser, check_installation


def parse_args():
    parser = build_argument_parser()
    parser.description = (
        "Analyze Paraver traces and save independent per-trace rawdata results."
    )

    parser.add_argument(
        "--output-dir",
        default=".",
        help=(
            "Directory where the per-trace JSON results will be written "
            "(default: current directory)"
        )
    )

    return parser.parse_args()


def main():
    cmdl_args = parse_args()

    check_installation(cmdl_args)

    (
        trace_list,
        trace_processes,
        trace_tasks,
        trace_threads,
        trace_task_per_node,
        trace_mode,
    ) = get_traces_from_args(cmdl_args)

    if not trace_list:
        raise RuntimeError("No valid traces available for analysis.")

    result_paths = run_trace_analyses_to_files(
        trace_list,
        trace_processes,
        trace_task_per_node,
        trace_mode,
        trace_tasks,
        trace_threads,
        cmdl_args,
        cmdl_args.output_dir,
    )

    for path in result_paths:
        print("Per-trace rawdata result written to {}".format(path))


if __name__ == "__main__":
    main()