#!/usr/bin/env python3

"""Utilities for BasicAnalysis execution-configuration labels."""

import re


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
    # Processes + GPU without MPI (nsys2prv traces)
    #
    # Same format as MPI+GPU, e.g. 5 (1x4) [1D]: execution units
    # (processes x streams per process) [devices]. The units are given,
    # since a process may have several host threads.
    # --------------------------------------------------

    elif model_key == "tasks_gpu":
        if streams_per_rank == -1 or streams_per_rank == "var":
            streams_per_rank = "var"

        label = "{} ({}{}{}) [{}D]".format(
            processes,
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


def add_plot_trace_ids(labels):
    """Add the trace ID of the interactive report ([T1], [T2], ...) to the
    configuration labels of the static plots.

    The labels are in trace order. The numeric ID that
    disambiguate_configuration_labels adds to duplicated labels is
    replaced, so that every column can be referenced as in the report
    (e.g. in a paper or in slides), even with the same parallel units.
    """

    result = []

    for index, label in enumerate(labels):
        label = str(label)

        for suffix in (" [{}]".format(index + 1), " [T{}]".format(index + 1)):
            if label.endswith(suffix):
                label = label[:-len(suffix)]

        result.append("{} [T{}]".format(label, index + 1))

    return result


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

def format_gpu_configuration_label(
        processes,
        devices,
        trace_id=None,
        separator='×'):
    """Build the report label of a GPU configuration: processes × GPUs.

    The same label is used in every table (Runtime Model, Host, Device), so
    that it describes the configuration and not the units of one domain:
    ``4 × 1 GPU`` (4 processes, 1 GPU each), ``2 × 4 GPUs``. When the GPUs
    are shared by the processes, or the counts are unknown, it gives both
    totals: ``8 (4 GPUs)``. The GPU streams are shown in the Execution
    Overview.
    """

    def _count(value):
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    processes = _count(processes)
    devices = _count(devices)

    if not processes or not devices:
        label = str(processes) if processes else "-"
    elif devices % processes == 0:
        per_process = devices // processes
        label = "{} {} {} GPU{}".format(
            processes,
            separator,
            per_process,
            "" if per_process == 1 else "s",
        )
    else:
        label = "{} ({} GPU{})".format(
            processes,
            devices,
            "" if devices == 1 else "s",
        )

    if trace_id is not None:
        label += " [{}]".format(trace_id)

    return label


# Meaning of the configuration labels (the trace columns), per programming
# model. The same text is used by the report ("Trace columns: ..."), the
# standard output tables, and the captions of the static plots.
CONFIGURATION_DESCRIPTIONS = {
    "mpi": "MPI ranks",
    "openmp": "Threads",
    "pthreads": "Threads",
    "ompss": "Workers",
    "gpu": "Processes × GPUs per process",
    "mpi_threads": "Parallel units (MPI ranks × threads/rank)",
    "mpi_ompss": "Parallel units (MPI ranks × workers/rank)",
    "mpi_gpu": "MPI ranks × GPUs per rank",
    "nsys2prv": "Processes × GPUs per process",
    "generic": "Parallel units",
}

# Font size of the caption of the static plots, smaller than the plot text.
CONFIGURATION_CAPTION_FONTSIZE = 9


def split_trace_mode(mode):
    """Split a trace mode (Detailed+MPI+OpenMP) into the collection mode and
    the programming model (Detailed, MPI + OpenMP)."""
    parts = str(mode).split("+")
    collection_mode = parts[0]
    if len(parts) > 1:
        programming_model = " + ".join(parts[1:])
    else:
        programming_model = "Unknown"
    return collection_mode, programming_model


def programming_model_key(programming_model):
    """Normalized identifier of a programming model (mpi, mpi_threads...)."""
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
    if model in ("MPI+OPENMP", "MPI+OMP", "MPI+PTHREADS"):
        return "mpi_threads"
    if model == "MPI+OMPSS":
        return "mpi_ompss"
    if model in ("MPI+CUDA", "MPI+HIP"):
        return "mpi_gpu"
    return "generic"


def configuration_model_key(mode):
    """Key of CONFIGURATION_DESCRIPTIONS for a trace mode."""
    collection_mode, programming_model = split_trace_mode(mode)
    if collection_mode == "nsys2prv":
        return "nsys2prv"
    if collection_mode in ("Burst", "Sampling"):
        # Burst+MPI traces are MPI traces.
        return programming_model_key(
            programming_model if programming_model != "Unknown" else "MPI")
    return programming_model_key(programming_model)


def configuration_description(trace_modes):
    """Meaning of the configuration labels of traces with these modes, e.g.
    "MPI ranks" or "Parallel units (MPI ranks × threads/rank)".

    Returns None when the traces have different programming models (each
    column then has its own meaning).
    """
    keys = {configuration_model_key(mode) for mode in trace_modes}
    if len(keys) != 1:
        return None
    return CONFIGURATION_DESCRIPTIONS[keys.pop()]


def configuration_caption(trace_modes, trace_ids=True):
    """Caption of a static plot: "Configuration: MPI ranks [Tn = trace ID]".

    Returns None when the traces have different programming models.
    """
    description = configuration_description(trace_modes)
    if description is None:
        return None
    return "Configuration: {}{}".format(
        description, " [Tn = trace ID]" if trace_ids else "")
