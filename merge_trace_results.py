#!/usr/bin/env python3

"""Merge serialized per-trace rawdata results."""

from __future__ import print_function, division

import argparse
import json
import os

from rawdata import (
    load_trace_result,
    merge_trace_results,
    reconstruct_trace_metadata,
)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Merge serialized per-trace rawdata results."
    )
    parser.add_argument(
        "inputs",
        nargs="+",
        metavar="JSON_FILE",
        help="Per-trace JSON files"
    )
    parser.add_argument(
        "--output",
        default="merged_rawdata.json",
        help="Output merged JSON file (default: merged_rawdata.json)"
    )
    parser.add_argument(
        "-ord", "--order_traces",
        choices=['yes', 'not'],
        default='yes',
        help='Order the trace list based on the numbers of processes'
    )
    return parser.parse_args()


def main():
    args = parse_args()

    results = [load_trace_result(path) for path in args.inputs]

    (
        trace_list,
        trace_processes,
        trace_tasks,
        trace_threads,
        trace_task_per_node,
        trace_mode,
    ) = reconstruct_trace_metadata(results, order_traces=args.order_traces)

    raw_data, list_mpi_procs_count = merge_trace_results(results, trace_list)

    merged = {
        "trace_list": trace_list,
        "trace_processes": trace_processes,
        "trace_tasks": trace_tasks,
        "trace_threads": trace_threads,
        "trace_task_per_node": trace_task_per_node,
        "trace_mode": trace_mode,
        "raw_data": raw_data,
        "list_mpi_procs_count": list_mpi_procs_count,
    }

    output_dir = os.path.dirname(os.path.abspath(args.output))
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    with open(args.output, "w") as f:
        json.dump(merged, f, indent=2, sort_keys=True)

    print("Merged rawdata result written to {}".format(args.output))


if __name__ == "__main__":
    main()