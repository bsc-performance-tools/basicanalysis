#!/usr/bin/env python3

"""Utilities for BasicAnalysis execution-configuration labels."""


def format_configuration_label(
        model_key,
        processes=None,
        mpi_ranks=None,
        inner_units=None,
        gpu_streams=None,
        streams_per_rank=None,
        devices=None,
        trace_id=None,
        separator='x'):
    """Build a model-aware BasicAnalysis configuration label."""

    # --------------------------------------------------
    # MPI
    # --------------------------------------------------

    if model_key == "mpi":
        label = str(
            mpi_ranks
            if mpi_ranks is not None
            else processes
        )

    # --------------------------------------------------
    # Host-threading runtime
    # --------------------------------------------------

    elif model_key in (
        "openmp",
        "pthreads",
        "ompss",
    ):
        label = str(
            inner_units
            if inner_units is not None
            else processes
        )

    # --------------------------------------------------
    # MPI + host threading
    # --------------------------------------------------

    elif model_key in (
        "mpi_threads",
        "mpi_ompss",
    ):
        try:
            parallel_units = (
                int(mpi_ranks)
                * int(inner_units)
            )
        except (TypeError, ValueError):
            parallel_units = processes

        label = "{} ({}{}{})".format(
            parallel_units,
            mpi_ranks,
            separator,
            inner_units,
        )

    # --------------------------------------------------
    # GPU-only
    # --------------------------------------------------

    elif model_key == "gpu":
        label = str(
            gpu_streams
            if gpu_streams is not None
            else processes
        )

    # --------------------------------------------------
    # MPI + GPU
    # --------------------------------------------------

    elif model_key == "mpi_gpu":

        if streams_per_rank == -1 or streams_per_rank == "var":

            try:
                parallel_units = (
                    int(mpi_ranks)
                    + int(gpu_streams)
                )
            except (TypeError, ValueError):
                parallel_units = processes

            label = "{} ({}{}var) [{}D]".format(
                parallel_units,
                mpi_ranks,
                separator,
                devices,
            )

        else:
            try:
                total_gpu_streams = (
                    int(mpi_ranks)
                    * int(streams_per_rank)
                )

                parallel_units = (
                    int(mpi_ranks)
                    + total_gpu_streams
                )

            except (TypeError, ValueError):
                try:
                    parallel_units = (
                        int(mpi_ranks)
                        + int(gpu_streams)
                    )
                except (TypeError, ValueError):
                    parallel_units = processes

            label = "{} ({}{}{}) [{}D]".format(
                parallel_units,
                mpi_ranks,
                separator,
                streams_per_rank,
                devices,
            )

    # --------------------------------------------------
    # Fallback
    # --------------------------------------------------

    else:
        label = str(processes)

    if trace_id is not None:
        label += " [{}]".format(trace_id)

    return label


def disambiguate_configuration_labels(
        labels,
        trace_ids=None):
    """Append a trace ID only to duplicated configuration labels."""

    counts = {}

    for label in labels:
        counts[label] = counts.get(label, 0) + 1

    result = []

    for index, label in enumerate(labels):

        if counts[label] > 1:

            if trace_ids is not None:
                trace_id = trace_ids[index]
            else:
                trace_id = index + 1

            label = "{} [{}]".format(
                label,
                trace_id,
            )

        result.append(label)

    return result