#!/usr/bin/env python3

"""Functions to compute the model metrics."""

from __future__ import print_function, division
import sys
import math

from rawdata import *
from collections import OrderedDict
from scaling import get_scaling_info
from configuration import (
    format_configuration_label,
    disambiguate_configuration_labels,
)

# error import variables
error_import_pandas = False
error_import_seaborn = False
error_import_matplotlib = False
error_import_numpy = False

try:
    import numpy as np
except ImportError:
    error_import_numpy = True


try:
    import pandas as pd
except ImportError:
    error_import_pandas = True

try:
    import seaborn as sns
except ImportError:
    error_import_seaborn = True


try:
    import matplotlib.pyplot as plt
except ImportError:
    error_import_matplotlib = True
    


# Contains all model factor entries with a printable name.
# This is used to generate and print all model factors, so, if an entry is added,
# it should be added here, too.

other_metrics_doc = OrderedDict([('elapsed_time', 'Elapsed time (sec)'),
                               ('efficiency', 'Efficiency'),
                               ('speedup', 'Speedup'),
                               ('ipc', 'Average IPC'),
                               ('freq', 'Average frequency (GHz)'),
                               ('flushing', 'Flushing (%)'),
                               ('io_mpiio', 'MPI I/O (%)'),
                               ('io_posix', 'POSIX I/O (%)'),
                               ('io_eff', 'I/O Efficiency (%)')])

mod_factors_doc = OrderedDict([('global_eff', 'Global efficiency'),
                               ('parallel_eff', '-- Parallel efficiency'),
                               ('load_balance', '   -- Load balance'),
                               ('comm_eff', '   -- Communication efficiency'),
                               ('serial_eff', '      -- Serialization efficiency'),
                               ('transfer_eff', '      -- Transfer efficiency'),
                               ('comp_scale', '-- Computation scalability'),
                               ('ipc_scale', '   -- IPC scalability'),
                               ('inst_scale', '   -- Instruction scalability'),
                               ('freq_scale', '   -- Frequency scalability')])

mod_factors_scale_plus_io_doc = OrderedDict([('comp_scale', '-- Computation scalability + I/O'),
                               ('ipc_scale', '   -- IPC scalability'),
                               ('inst_scale', '   -- Instruction scalability'),
                               ('freq_scale', '   -- Frequency scalability')])

mod_hybrid_factors_doc = OrderedDict([
                               ('hybrid_eff', '-- Hybrid Parallel efficiency'),
                               ('mpi_parallel_eff', '   -- MPI Parallel efficiency'),
                               ('mpi_load_balance', '      -- MPI Load balance'),
                               ('mpi_comm_eff', '      -- MPI Communication efficiency'),
                               ('serial_eff', '         -- MPI Serialization efficiency'),
                               ('transfer_eff', '         -- MPI Transfer efficiency'),
                               ('omp_parallel_eff', '   -- OpenMP Parallel efficiency'),
                               ('omp_load_balance', '      -- OpenMP Load balance'),
                               ('omp_comm_eff', '      -- OpenMP Communication efficiency')])

mod_hyb_comm_omp_factors_doc = OrderedDict([
                               ('omp_serial_eff', '         -- OpenMP Serialization efficiency'),
                               ('omp_transfer_eff', '         -- OpenMP Transfer efficiency'),])

mod_device_factors_doc = OrderedDict([
                               ('dev_global_eff', 'DEVICE Global efficiency'),
                               ('dev_parallel_eff', '-- Device Parallel efficiency'),
                               ('dev_load_balance', '   == Device Load balance'),
                               ('dev_comm_eff', '   == Device Communication efficiency'),
                               ('dev_orches_eff', '   == Device Orchestration efficiency'),
                               ('dev_comp_scale', '-- Device Computation scalability')])

mod_host_factors_doc = OrderedDict([
                               ('host_global_eff', 'HOST Global efficiency'),
                               ('host_parallel_eff', '-- Host Parallel efficiency'),
                               ('mpi_parallel_eff', '   == MPI Parallel efficiency'),
                               ('mpi_load_balance', '       -- MPI Load balance'),
                               ('mpi_comm_eff', '       -- MPI Communication efficiency'),
                               ('serial_eff', '          -- Serialization efficiency'),
                               ('transfer_eff', '          -- Transfer efficiency'),
                               ('dev_offload_eff', '   == Device Offload efficiency'),
                               ('host_comp_scale', '-- Host Computation scalability'),
                               ('host_ipc_scale', '   == IPC scalability'),
                               ('host_inst_scale', '   == Instruction scalability'),
                               ('host_freq_scale', '   == Frequency scalability')])


mod_omp_factors_doc = OrderedDict([
                                ('omp_talp_parallel_eff', '-- OpenMP Parallel Efficiency'),
                                ('omp_talp_serial_eff', '   -- OpenMP Serial Efficiency'),
                                ('omp_talp_load_balance', '   -- OpenMP Load Balance'),
                                ('omp_talp_scheduling_eff', '   -- OpenMP Scheduling Efficiency'),
                            ])


def safe_float_for_plot(value):
    """
    Convert metric values to float for plotting.

    Non-numeric values such as 'Warning!', 'Non-Avail',
    'N/A', or 'NaN' are represented as NaN so that
    heatmaps leave those cells empty.
    """
    try:
        return float(value)
    except (TypeError, ValueError):
        return np.nan

def create_mod_factors(trace_list):
    """Creates 2D dictionary of the model factors and initializes with an empty
    string. The mod_factors dictionary has the format: [mod factor key][trace].
    """
    global mod_factors_doc
    mod_factors = {}
    for key in mod_factors_doc:
        trace_dict = {}
        for trace_name in trace_list:
            trace_dict[trace_name] = 0.0
        mod_factors[key] = trace_dict

    return mod_factors


def create_mod_factors_scale_io(trace_list):
    """Creates 2D dictionary of the model factors and initializes with an empty
    string. The mod_factors dictionary has the format: [mod factor key][trace].
    """
    global mod_factors_scale_plus_io_doc
    mod_factors_scale_plus_io = {}
    for key in mod_factors_scale_plus_io_doc:
        trace_dict = {}
        for trace_name in trace_list:
            trace_dict[trace_name] = 0.0
        mod_factors_scale_plus_io[key] = trace_dict

    return mod_factors_scale_plus_io


def create_hybrid_mod_factors(trace_list):
    """Creates 2D dictionary of the hybrid model factors and initializes with an empty
    string. The hybrid_factors dictionary has the format: [factor key][trace].
    """
    global mod_hybrid_factors_doc
    hybrid_factors = {}
    for key in mod_hybrid_factors_doc:
        trace_dict = {}
        for trace_name in trace_list:
            trace_dict[trace_name] = 0.0
        hybrid_factors[key] = trace_dict

    return hybrid_factors

def create_hyb_comm_omp_factors(trace_list):
    """Creates 2D dictionary of the hybrid OpenMP communication submetrics factors and initializes with an empty
    string. The hyb_comm_omp_factors_doc dictionary has the format: [factor key][trace].
    """
    global mod_hyb_comm_omp_factors_doc
    hyb_comm_omp_factors = {}
    for key in mod_hyb_comm_omp_factors_doc:
        trace_dict = {}
        for trace_name in trace_list:
            trace_dict[trace_name] = 0.0
        hyb_comm_omp_factors[key] = trace_dict

    return hyb_comm_omp_factors

def create_mod_device_factors(trace_list):
    """Creates 2D dictionary of the device factors at device level and initializes with an empty
    string. The device_factors dictionary has the format: [factor key][trace].
    """
    global mod_device_factors_doc
    device_factors = {}
    for key in mod_device_factors_doc:
        trace_dict = {}
        for trace_name in trace_list:
            trace_dict[trace_name] = 0.0
        device_factors[key] = trace_dict

    return device_factors

def create_mod_host_factors(trace_list):
    """Creates 2D dictionary of the host factors at host level and initializes with an empty
    string. The host_factors dictionary has the format: [factor key][trace].
    """
    global mod_host_factors_doc
    host_factors = {}
    for key in mod_host_factors_doc:
        trace_dict = {}
        for trace_name in trace_list:
            trace_dict[trace_name] = 0.0
        host_factors[key] = trace_dict

    return host_factors


def create_other_metrics(trace_list):
    """Creates 2D dictionary of the other metrics and initializes with an empty
    string. The other_metrics dictionary has the format: [factor key][trace].
    """
    global other_metrics_doc
    other_metrics = {}
    for key in other_metrics_doc:
        trace_dict = {}
        for trace_name in trace_list:
            trace_dict[trace_name] = 0.0
        other_metrics[key] = trace_dict

    return other_metrics

def create_omp_talp_factors(trace_list):
    global mod_omp_factors_doc

    omp_talp_factors = {}
    for key in mod_omp_factors_doc:
        trace_dict = {}
        for trace_name in trace_list:
            trace_dict[trace_name] = 0.0
        omp_talp_factors[key] = trace_dict

    return omp_talp_factors

def is_mpi_gpu_mode(mode):
    return mode in (
    'Detailed+MPI+CUDA',
    'Detailed+MPI+HIP',
    )  

def _build_hybrid_configuration_labels(
        trace_list,
        trace_processes,
        trace_tasks,
        trace_threads,
        trace_mode,
        raw_data,
        separator='x'):
    """Build model-aware configuration labels for hybrid output."""

    labels = []

    for trace in trace_list:

        # --------------------------------------------------
        # MPI + GPU
        # --------------------------------------------------

        if is_mpi_gpu_mode(trace_mode[trace]):
            parallel_units = trace_processes[trace]
            mpi_ranks = trace_tasks[trace]
            devices = raw_data['count_devices'][trace]

            try:
                total_gpu_streams = (
                    int(parallel_units)
                    - int(mpi_ranks)
                )

                if int(mpi_ranks) > 0:
                    if total_gpu_streams % int(mpi_ranks) == 0:
                        streams_per_rank = (
                            total_gpu_streams
                            // int(mpi_ranks)
                        )
                    else:
                        streams_per_rank = -1
                else:
                    streams_per_rank = -1

            except (TypeError, ValueError):
                total_gpu_streams = None
                streams_per_rank = -1

            label = format_configuration_label(
                model_key="mpi_gpu",
                processes=parallel_units,
                mpi_ranks=mpi_ranks,
                gpu_streams=total_gpu_streams,
                streams_per_rank=streams_per_rank,
                devices=devices,
                separator=separator,
            )

        # --------------------------------------------------
        # MPI + other runtime
        # --------------------------------------------------

        elif trace_mode[trace].startswith(
                "Detailed+MPI+"):

            label = format_configuration_label(
                model_key="mpi_threads",
                processes=trace_processes[trace],
                mpi_ranks=trace_tasks[trace],
                inner_units=trace_threads[trace],
                separator=separator,
            )

        # --------------------------------------------------
        # Fallback
        # --------------------------------------------------

        else:
            label = format_configuration_label(
                model_key="generic",
                processes=trace_processes[trace],
                separator=separator,
            )

        labels.append(label)

    trace_ids = [
        index + 1
        for index in range(len(trace_list))
    ]

    return disambiguate_configuration_labels(
        labels,
        trace_ids=trace_ids,
    )


def _format_heatmap_metric_labels(labels, output_name):
    """
    Convert the textual hierarchy used by stdout (-- / ==)
    into clean metric names plus indentation levels for plots.
    """

    formatted_labels = []
    indent_levels = []

    is_hybrid_table = 'hybrid' in output_name

    for label in labels:
        raw_label = str(label)

        # Existing metric dictionaries encode hierarchy using
        # leading spaces plus '--' / '==' markers.
        leading_spaces = len(raw_label) - len(raw_label.lstrip())
        text = raw_label.strip()

        has_marker = False

        if text.startswith('=='):
            text = text[2:].strip()
            has_marker = True
        elif text.startswith('--'):
            text = text[2:].strip()
            has_marker = True

        if is_hybrid_table:
            # Hybrid Parallel efficiency is the root of this table.
            if text == 'Hybrid Parallel efficiency':
                level = 0
            else:
                level = int(round(leading_spaces / 3.0))

        else:
            # Global and HOST/DEVICE tables have unmarked root rows.
            if not has_marker:
                level = 0
            elif leading_spaces == 0:
                level = 1
            else:
                level = 1 + int(round(leading_spaces / 3.0))

        formatted_labels.append(text)
        indent_levels.append(level)

    return formatted_labels, indent_levels


def _plot_efficiency_heatmap(df, output_name, separator_row=None):
    """
    Render an efficiency table as a publication-quality heatmap.

    Layout:
        metric hierarchy | efficiency values | colorbar

    The metric-label area and data-column widths are computed from
    the actual text so that long metric names and configuration
    headers are not clipped or overlapped.
    """

    nrows, ncols = df.shape

    # --------------------------------------------------
    # Metric hierarchy
    # --------------------------------------------------

    formatted_labels, indent_levels = _format_heatmap_metric_labels(
        df.index,
        output_name,
    )

    # --------------------------------------------------
    # Figure dimensions
    # --------------------------------------------------

    # Estimate the width required by the metric-label column.
    #
    # Hierarchy indentation also consumes horizontal space, so add
    # a few equivalent characters for each indentation level.
    max_metric_chars = max(
        len(label) + level * 3
        for label, level in zip(
            formatted_labels,
            indent_levels,
        )
    )

    # Width reserved for metric names.
    #
    # The multiplication factor is intentionally conservative so
    # that long names such as "Device Communication efficiency"
    # are not clipped.
    label_width = max(
        3.4,
        max_metric_chars * 0.12
    )

    # --------------------------------------------------
    # Configuration/header width
    # --------------------------------------------------

    header_labels = [
        str(column)
        for column in df.columns
    ]

    max_header_chars = max(
        len(label)
        for label in header_labels
    )

    # Minimum width needed for numeric values.
    value_column_width = 1.25

    # Width required by the configuration header.
    #
    # Long labels such as:
    #
    #     36 (8xvar) [8D] [1]
    #
    # therefore produce wider columns than:
    #
    #     64 (8x8)
    #
    header_column_width = max(
        1.25,
        max_header_chars * 0.105
    )

    column_width = max(
        value_column_width,
        header_column_width
    )

    data_width = (
        ncols * column_width
    )

    # Independent narrow colorbar.
    colorbar_width = 0.28

    # Small extra spacing for figure boundaries.
    extra_width = 0.35

    figure_width = (
        label_width
        + data_width
        + colorbar_width
        + extra_width
    )

    figure_height = max(
        3.0,
        nrows * 0.54
    )

    # --------------------------------------------------
    # Three-column layout
    # --------------------------------------------------

    fig = plt.figure(
        figsize=(
            figure_width,
            figure_height
        )
    )

    grid = fig.add_gridspec(
        nrows=1,
        ncols=3,
        width_ratios=[
            label_width,
            data_width,
            colorbar_width,
        ],
        wspace=0.04
    )

    # Dedicated axis for metric names.
    label_ax = fig.add_subplot(
        grid[0, 0]
    )

    # Heatmap itself.
    ax = fig.add_subplot(
        grid[0, 1]
    )

    # Dedicated colorbar axis.
    cbar_ax = fig.add_subplot(
        grid[0, 2]
    )

    # --------------------------------------------------
    # Heatmap
    # --------------------------------------------------

    heatmap = sns.heatmap(
        df,
        ax=ax,
        cbar_ax=cbar_ax,
        cmap='RdYlGn',
        linewidths=0.6,
        linecolor='white',
        annot=True,
        vmin=0,
        vmax=100,
        center=75,
        fmt='.2f',
        annot_kws={
            'fontsize': 12
        }
    )

    # --------------------------------------------------
    # Configuration labels
    # --------------------------------------------------

    ax.xaxis.tick_top()
    ax.xaxis.set_label_position(
        'top'
    )

    # Adapt header font slightly when configuration names become long.
    if max_header_chars > 24:
        header_fontsize = 9
    elif max_header_chars > 18:
        header_fontsize = 10
    else:
        header_fontsize = 11

    ax.tick_params(
        axis='x',
        labelsize=header_fontsize,
        rotation=0,
        pad=6,
        length=0
    )

    ax.set_xlabel('')
    ax.set_ylabel('')

    # Metric names are rendered in label_ax, not as heatmap ticks.
    ax.set_yticklabels([])

    ax.tick_params(
        axis='y',
        length=0
    )

    # --------------------------------------------------
    # Metric-label column
    # --------------------------------------------------

    # Match seaborn's vertical coordinate system exactly.
    label_ax.set_ylim(
        nrows,
        0
    )

    label_ax.set_xlim(
        0,
        1
    )

    # No visible axis around the metric-label column.
    label_ax.axis('off')

    # Root metrics begin here.
    base_x = 0.01

    # Horizontal shift for each hierarchy level.
    #
    # Because label_ax has its own width, indentation is independent
    # from the width of the heatmap.
    indent_step = 0.07

    for row, (metric, level) in enumerate(
            zip(
                formatted_labels,
                indent_levels,
            )
    ):
        y = row + 0.5

        label_ax.text(
            base_x + level * indent_step,
            y,
            metric,
            fontsize=12,
            ha='left',
            va='center',
            clip_on=False
        )

    # --------------------------------------------------
    # Optional HOST / DEVICE separator
    # --------------------------------------------------

    if separator_row is not None:
        ax.hlines(
            separator_row,
            *ax.get_xlim(),
            colors='white',
            linewidth=5
        )

    # --------------------------------------------------
    # Colorbar
    # --------------------------------------------------

    cbar = heatmap.collections[0].colorbar

    cbar.ax.tick_params(
        labelsize=10
    )

    cbar.set_label(
        'Percentage (%)',
        fontsize=11,
        labelpad=8
    )

    # --------------------------------------------------
    # Output
    # --------------------------------------------------

    fig.savefig(
        output_name + '.png',
        dpi=400,
        bbox_inches='tight'
    )

    fig.savefig(
        output_name + '.pdf',
        bbox_inches='tight'
    )

    plt.close(fig)


def compute_model_factors(raw_data, trace_list, trace_processes, trace_mode, list_mpi_procs_count, cmdl_args):
    """Computes the model factors from the gathered raw data and returns the
    according dictionary of model factors."""
    mod_factors = create_mod_factors(trace_list)
    hybrid_factors = create_hybrid_mod_factors(trace_list)
    hybrid_gpu_factors = create_hybrid_mod_factors(trace_list)
    other_metrics = create_other_metrics(trace_list)
    mod_factors_scale_plus_io = create_mod_factors_scale_io(trace_list)
    device_factors = create_mod_device_factors(trace_list)
    host_factors = create_mod_host_factors(trace_list)
    hyb_comm_omp_factors = create_hyb_comm_omp_factors(trace_list)
    omp_talp_factors = create_omp_talp_factors(trace_list)


    # Detect and select the scaling model.
    scaling_info = get_scaling_info(
        raw_data,
        trace_list,
        trace_processes,
        cmdl_args,
    )

    scaling = scaling_info.selected

    # Loop over all traces
    for trace in trace_list:

        proc_ratio = float(trace_processes[trace]) / float(trace_processes[trace_list[0]])
   
        total_procs = trace_processes[trace]

        is_mpi_gpu = trace_mode[trace] in ('Detailed+MPI+CUDA','Detailed+MPI+HIP',)        

        # Control OutMPI values no availables
        if math.isnan(float(raw_data['outsidempi_avg'][trace])) or math.isnan(float(raw_data['outsidempi_max'][trace])):
            outmpi_measures = False
        else:
            outmpi_measures = True

        # Flushing measurements
        try:  # except NaN
            if trace_mode[trace][0:len("Burst")] != 'Burst':
                other_metrics['flushing'][trace] = float(raw_data['flushing_tot'][trace]) \
                                                     / (raw_data['runtime'][trace] * total_procs) * 100.0
            else:
                other_metrics['flushing'][trace] = 0.0
        except:
            other_metrics['flushing'][trace] = 0.0

        # I/O measurements
        try:  # except NaN
            if trace_mode[trace][0:len("Burst")] != 'Burst':
                other_metrics['io_mpiio'][trace] = float(raw_data['mpiio_tot'][trace]) \
                                               / (raw_data['runtime'][trace] * total_procs) * 100.0
            else:
                other_metrics['io_mpiio'][trace] = 0.0
        except:
            other_metrics['io_mpiio'][trace] = 0.0

        try:  # except NaN
            if trace_mode[trace][0:len("Burst")] != 'Burst':
                other_metrics['io_posix'][trace] = float(raw_data['io_tot'][trace]) \
                                               / (raw_data['runtime'][trace] * total_procs) * 100.0
            else:
                other_metrics['io_posix'][trace] = 0.0
        except:
            other_metrics['io_posix'][trace] = 0.0
        try:  # except NaN

            io_total = float(raw_data['mpiio_tot'][trace] + raw_data['flushing_tot'][trace]
                             + raw_data['io_tot'][trace])
            other_metrics['io_eff'][trace] = float(raw_data['useful_tot'][trace]) \
                                             / (raw_data['useful_tot'][trace] + io_total) * 100.0
        except:
            other_metrics['io_eff'][trace] = 0.0

        # Basic efficiency factors
        try:  # except NaN
            #if other_metrics['io_posix'][trace] > 0.0 or other_metrics['flushing'][trace] > 5.0:
            #    mod_factors['load_balance'][trace] = float(raw_data['useful_plus_io_avg'][trace]) \
            #                                         / float(raw_data['useful_plus_io_max'][trace]) * 100.0
            #else:
            mod_factors['load_balance'][trace] = float(raw_data['useful_avg'][trace]) \
                                                 / float(raw_data['useful_max'][trace]) * 100.0
        except:
            mod_factors['load_balance'][trace] = 'NaN'

        try:  # except NaN
            #if other_metrics['io_posix'][trace] > 0.0 or other_metrics['flushing'][trace] > 5.0:
            #    mod_factors['comm_eff'][trace] = float(raw_data['useful_plus_io_max'][trace] \
            #                                     / raw_data['runtime'][trace] * 100.0)
            #else:
            mod_factors['comm_eff'][trace] = float(raw_data['useful_max'][trace] / raw_data['runtime'][trace] * 100.0)
        except:
            mod_factors['comm_eff'][trace] = 'NaN'

        try:  # except NaN
            if trace_mode[trace][0:len("Burst")] != 'Burst':
                #if other_metrics['io_posix'][trace] > 0.0 or other_metrics['flushing'][trace] > 5.0:
                #    mod_factors['parallel_eff'][trace] = float(raw_data['useful_plus_io_avg'][trace]) \
                #                                     / float(raw_data['runtime'][trace]) * 100.0
                #else:
                mod_factors['parallel_eff'][trace] = float(mod_factors['load_balance'][trace]) \
                                                     * float(mod_factors['comm_eff'][trace]) / 100.0
            elif trace_mode[trace] == 'Burst+MPI':
                mod_factors['parallel_eff'][trace] = float(raw_data['burst_useful_avg'][trace]) \
                                                     / float(raw_data['runtime'][trace]) * 100.0
        except:
            mod_factors['parallel_eff'][trace] = 'NaN'

        try:  # except NaN
            if len(trace_list) > 1:
                if trace_mode[trace][0:len("Burst")] == 'Burst':
                    if trace_mode[trace_list[0]][0:len("Burst")] == 'Burst':
                        if scaling == 'strong':
                            mod_factors['comp_scale'][trace] = raw_data['burst_useful_tot'][trace_list[0]] \
                                                   / raw_data['burst_useful_tot'][trace] * 100.0
                        else:
                            mod_factors['comp_scale'][trace] = raw_data['burst_useful_tot'][trace_list[0]] \
                                                   / raw_data['burst_useful_tot'][trace] \
                                                   * proc_ratio * 100.0
                    else:
                        mod_factors['comp_scale'][trace] = 100.0
                elif outmpi_measures and is_mpi_gpu:
                    if scaling == 'strong':
                        host_factors['host_comp_scale'][trace] = float(raw_data['useful_host'][trace_list[0]]) \
                                                    / float(raw_data['useful_host'][trace]) * 100.0
                    else:
                        host_factors['host_comp_scale'][trace] = float(raw_data['useful_host'][trace_list[0]]) \
                                                    / float(raw_data['useful_host'][trace]) * proc_ratio * 100.0

                    mod_factors['comp_scale'][trace] = host_factors['host_comp_scale'][trace]
                else:
                    if scaling == 'strong':
                        mod_factors['comp_scale'][trace] = float(raw_data['useful_tot'][trace_list[0]]) \
                                                   / float(raw_data['useful_tot'][trace]) * 100.0
                    else:
                        mod_factors['comp_scale'][trace] = float(raw_data['useful_tot'][trace_list[0]]) \
                                                   / float(raw_data['useful_tot'][trace]) * proc_ratio * 100.0
            else:
                mod_factors['comp_scale'][trace] = 'Non-Avail'
                host_factors['host_comp_scale'][trace] = 'Non-Avail'

        except:
            mod_factors['comp_scale'][trace] = 'NaN'
            host_factors['host_comp_scale'][trace] = 'NaN'

        # Computation Scale + Serial I/O
        try:  # except NaN
            if len(trace_list) > 1:
                if other_metrics['io_posix'][trace] > 0.0 or other_metrics['flushing'][trace] > 0.0:
                    io_serial_0 = float(raw_data['io_tot'][trace_list[0]] + raw_data['flushing_tot'][trace_list[0]])
                    io_serial_n = float(raw_data['io_tot'][trace] + raw_data['flushing_tot'][trace])
                    if scaling == 'strong':
                        mod_factors_scale_plus_io['comp_scale'][trace] = float((raw_data['useful_tot'][trace_list[0]]
                                                                      + io_serial_0) / (raw_data['useful_tot'][trace]
                                                                                        + io_serial_n) * 100.0)
                    else:
                        mod_factors_scale_plus_io['comp_scale'][trace] = (float(raw_data['useful_tot'][trace_list[0]])
                                                                          + io_serial_0) \
                                                                     / (float(raw_data['useful_tot'][trace])
                                                                        + io_serial_n) * proc_ratio * 100.0
                else:
                    mod_factors_scale_plus_io['comp_scale'][trace] = float(mod_factors['comp_scale'][trace])
            else:
                mod_factors_scale_plus_io['comp_scale'][trace] = 'Non-Avail'
        except:
            mod_factors_scale_plus_io['comp_scale'][trace] = 'NaN'


        try:  # except NaN
            if len(trace_list) > 1:
                mod_factors['global_eff'][trace] = float(mod_factors['parallel_eff'][trace]) \
                                                   * float(mod_factors['comp_scale'][trace]) / 100.0
            else:
                mod_factors['global_eff'][trace] = float(mod_factors['parallel_eff'][trace]) * 100.0 / 100.0
        except:
            mod_factors['global_eff'][trace] = 'NaN'

        # Hybrid metrics calculation
            # ------->  MPI metrics
        try:  # except NaN
            if not outmpi_measures:
                hybrid_factors['mpi_load_balance'][trace] = 'Non-Avail'
            elif trace_mode[trace][0:len("Detailed+MPI+")] == "Detailed+MPI+":
                hybrid_factors['mpi_load_balance'][trace] = float(raw_data['outsidempi_avg'][trace]) \
                                                        / float(raw_data['outsidempi_max'][trace]) * 100.0
            else:
                hybrid_factors['mpi_load_balance'][trace] = 'N/A'
        except:
                hybrid_factors['mpi_load_balance'][trace] = 'NaN'

        try:  # except NaN
            if not outmpi_measures:
                hybrid_factors['mpi_comm_eff'][trace] = 'Non-Avail'
            elif trace_mode[trace][0:len("Detailed+MPI+")] == "Detailed+MPI+":
                hybrid_factors['mpi_comm_eff'][trace] = float(raw_data['outsidempi_max'][trace]) \
                                                    / float(raw_data['runtime'][trace]) * 100.0
            else:
                hybrid_factors['mpi_comm_eff'][trace] = 'N/A'
        except:
            hybrid_factors['mpi_comm_eff'][trace] = 'NaN'

        # ------------> BEGIN MPI communication sub-metrics
        try:  # except NaN
            if (not outmpi_measures) or cmdl_args.skip_simulation:
                hybrid_factors['serial_eff'][trace] = 'Non-Avail'
            elif trace_mode[trace] == "Detailed+MPI+OpenMP" and cmdl_args.hyb_mpiomp:
                mod_factors['serial_eff'][trace] = float(raw_data['hybrid_useful_dim'][trace]) \
                                                   / float(raw_data['hybrid_runtime_dim'][trace]) * 100.0
                hybrid_factors['serial_eff'][trace] = float(raw_data['outsidempi_dim'][trace]) \
                / float(raw_data['runtime_dim'][trace]) * 100.0           
            elif trace_mode[trace] == "Detailed+MPI+OpenMP" \
                        or trace_mode[trace] == 'Detailed+MPI+CUDA':
                hybrid_factors['serial_eff'][trace] = float(raw_data['outsidempi_dim'][trace]) \
                                               / float(raw_data['runtime_dim'][trace]) * 100.0
                mod_factors['serial_eff'][trace] = 'N/A'
            elif trace_mode[trace] == "Detailed+MPI":
                mod_factors['serial_eff'][trace] = float(raw_data['useful_dim'][trace]) \
                                                   / float(raw_data['runtime_dim'][trace]) * 100.0
                hybrid_factors['serial_eff'][trace] = 'N/A'
            elif trace_mode[trace][0:len("Detailed+MPI+")] == "Detailed+MPI+":
                mod_factors['serial_eff'][trace] = 'N/A'
                hybrid_factors['serial_eff'][trace] = 'Non-Avail'
            else:
                mod_factors['serial_eff'][trace] = 'Non-Avail'
                hybrid_factors['serial_eff'][trace] = 'N/A'

            if round(hybrid_factors['serial_eff'][trace]) > 100:
                hybrid_factors['serial_eff'][trace] = 'Warning!'
        except:    
            if trace_mode[trace] == 'Detailed+MPI' or trace_mode[trace] == 'Detailed+MPI+OpenMP' \
                    or trace_mode[trace] == 'Detailed+MPI+CUDA':
                if hybrid_factors['serial_eff'][trace] != 'Non-Avail' and hybrid_factors['serial_eff'][trace] != 'N/A':
                    hybrid_factors['serial_eff'][trace] = 'NaN'

        try:  # except NaN
            if (not outmpi_measures) or cmdl_args.skip_simulation:
                hybrid_factors['transfer_eff'][trace] = 'Non-Avail'
            elif hybrid_factors['serial_eff'][trace] != 'Warning!':
                if trace_mode[trace] == "Detailed+MPI+OpenMP" and cmdl_args.hyb_mpiomp:
                    mod_factors['transfer_eff'][trace] = float(mod_factors['comm_eff'][trace]) \
                    / float(mod_factors['serial_eff'][trace]) * 100.0
                    hybrid_factors['transfer_eff'][trace] = float(hybrid_factors['mpi_comm_eff'][trace]) \
                    / float(hybrid_factors['serial_eff'][trace]) * 100.0                   
                elif trace_mode[trace] == "Detailed+MPI+OpenMP" \
                        or trace_mode[trace] == 'Detailed+MPI+CUDA':
                    hybrid_factors['transfer_eff'][trace] = float(hybrid_factors['mpi_comm_eff'][trace]) \
                                                        / float(hybrid_factors['serial_eff'][trace]) * 100.0
                    mod_factors['transfer_eff'][trace] = 'N/A'
                elif trace_mode[trace] == "Detailed+MPI":
                    mod_factors['transfer_eff'][trace] = float(mod_factors['comm_eff'][trace]) \
                                                         / float(mod_factors['serial_eff'][trace]) * 100.0
                    hybrid_factors['transfer_eff'][trace] = 'N/A'
                elif trace_mode[trace][0:len("Detailed+MPI+")] == "Detailed+MPI+":
                    hybrid_factors['transfer_eff'][trace] = 'Non-Avail'
                    mod_factors['transfer_eff'][trace] = 'N/A'
                else:
                    hybrid_factors['transfer_eff'][trace] = 'N/A'
                    mod_factors['transfer_eff'][trace] = 'Non-Avail'

                if not hybrid_factors['transfer_eff'][trace] == 'Non-Avail':
                    if round(hybrid_factors['transfer_eff'][trace]) > 100:
                        hybrid_factors['transfer_eff'][trace] = 'Warning!'
        except:
            if trace_mode[trace] == 'Detailed+MPI' or trace_mode[trace] == 'Detailed+MPI+OpenMP' \
                    or trace_mode[trace] == 'Detailed+MPI+CUDA':
                if hybrid_factors['transfer_eff'][trace] != 'N/A' and hybrid_factors['transfer_eff'][trace] != 'Non-Avail':
                    hybrid_factors['transfer_eff'][trace] = 'NaN'

        # submetrics communication openmp part in hybrid codes
        try:  # except NaN
            if (not outmpi_measures) or cmdl_args.skip_simulation:
                hyb_comm_omp_factors['omp_transfer_eff'][trace] = 'Non-Avail'
                hyb_comm_omp_factors['omp_serial_eff'][trace] = 'Non-Avail'
            elif trace_mode[trace] == "Detailed+MPI+OpenMP" and cmdl_args.hyb_mpiomp:
                hyb_comm_omp_factors['omp_serial_eff'][trace] = mod_factors['serial_eff'][trace]/hybrid_factors['serial_eff'][trace] * 100.0
                hyb_comm_omp_factors['omp_transfer_eff'][trace] = mod_factors['transfer_eff'][trace]/hybrid_factors['transfer_eff'][trace] * 100.0
            else:
                hyb_comm_omp_factors['omp_transfer_eff'][trace] = 'Non-Avail'
                hyb_comm_omp_factors['omp_serial_eff'][trace] = 'Non-Avail'            
        except:
            hyb_comm_omp_factors['omp_transfer_eff'][trace] = 'NaN'
            hyb_comm_omp_factors['omp_serial_eff'][trace] = 'NaN' 


        # --------------> END MPI communication sub-metrics
        try:  # except NaN
            if not outmpi_measures:
                hybrid_factors['mpi_parallel_eff'][trace] = 'Non-Avail'
            elif trace_mode[trace][0:len("Detailed+MPI+")] == "Detailed+MPI+":
                if raw_data['outsidempi_tot'][trace] == raw_data['outsidempi_tot_diff'][trace]:
                    hybrid_factors['mpi_parallel_eff'][trace] = float(raw_data['outsidempi_tot'][trace] /
                                                                  (raw_data['runtime'][trace]
                                                                   * list_mpi_procs_count[trace]) * 100.0)
                else:
                    hybrid_factors['mpi_parallel_eff'][trace] = float(raw_data['outsidempi_tot_diff'][trace]
                                                                  / (raw_data['runtime'][trace]
                                                                     * trace_processes[trace]) * 100.0)
            else:
                hybrid_factors['mpi_parallel_eff'][trace] = 'N/A'
        except:
            hybrid_factors['mpi_parallel_eff'][trace] = 'NaN'

        # ------->  Metrics for the second parallel paradigm
        try:  # except NaN
            if not outmpi_measures:
                hybrid_factors['omp_comm_eff'][trace] = 'Non-Avail'
            elif trace_mode[trace][0:len("Detailed+MPI+")] == "Detailed+MPI+":
                hybrid_factors['omp_comm_eff'][trace] = float(mod_factors['comm_eff'][trace]) \
                                                        / float(hybrid_factors['mpi_comm_eff'][trace]) * 100.0
            else:
                hybrid_factors['omp_comm_eff'][trace] = 'N/A'
        except:
            hybrid_factors['omp_comm_eff'][trace] = 'NaN'

        try:  # except NaN
            if not outmpi_measures:
                hybrid_factors['omp_load_balance'][trace] = 'Non-Avail'
            elif trace_mode[trace][0:len("Detailed+MPI+")] == "Detailed+MPI+":
                hybrid_factors['omp_load_balance'][trace] = float(mod_factors['load_balance'][trace]) \
                                                            / float(hybrid_factors['mpi_load_balance'][trace]) * 100.0
            else:
                hybrid_factors['omp_load_balance'][trace] = 'N/A'
        except:
            hybrid_factors['omp_load_balance'][trace] = 'NaN'

        try:  # except NaN
            if not outmpi_measures:
                hybrid_factors['omp_parallel_eff'][trace] = 'Non-Avail'
            elif trace_mode[trace][0:len("Detailed+MPI+")] == "Detailed+MPI+":
                hybrid_factors['omp_parallel_eff'][trace] = float(mod_factors['parallel_eff'][trace]) \
                                                            / float(hybrid_factors['mpi_parallel_eff'][trace]) * 100.0
            else:
                hybrid_factors['omp_parallel_eff'][trace] = 'N/A'
        except:
            hybrid_factors['omp_parallel_eff'][trace] = 'NaN'


        # -------> Isolated OpenMP metrics, TALP-style timing model
        try:
            if trace_mode[trace] == 'Detailed+MPI+OpenMP':
                t_no_omp = float(raw_data['time_no_omp'][trace])
                t_serial = float(raw_data['time_omp_serial'][trace])
                t_imbal = float(raw_data['time_omp_imbalance'][trace])
                t_sched = float(raw_data['time_omp_schedule'][trace])

                t_after_serial = t_no_omp + t_serial
                t_after_lb = t_after_serial + t_imbal
                t_total = t_after_lb + t_sched

                if t_total > 0.0:
                    omp_talp_factors['omp_talp_parallel_eff'][trace] = (
                        t_no_omp / t_total * 100.0
                    )
                else:
                    omp_talp_factors['omp_talp_parallel_eff'][trace] = 'NaN'

                if t_after_serial > 0.0:
                    omp_talp_factors['omp_talp_serial_eff'][trace] = (
                        t_no_omp / t_after_serial * 100.0
                    )
                else:
                    omp_talp_factors['omp_talp_serial_eff'][trace] = 'NaN'

                if t_after_lb > 0.0:
                    omp_talp_factors['omp_talp_load_balance'][trace] = (
                        t_after_serial / t_after_lb * 100.0
                    )
                else:
                    omp_talp_factors['omp_talp_load_balance'][trace] = 'NaN'

                if t_total > 0.0:
                    omp_talp_factors['omp_talp_scheduling_eff'][trace] = (
                        t_after_lb / t_total * 100.0
                    )
                else:
                    omp_talp_factors['omp_talp_scheduling_eff'][trace] = 'NaN'
            else:
                omp_talp_factors['omp_talp_parallel_eff'][trace] = 'Non-Avail'
                omp_talp_factors['omp_talp_serial_eff'][trace] = 'Non-Avail'
                omp_talp_factors['omp_talp_load_balance'][trace] = 'Non-Avail'
                omp_talp_factors['omp_talp_scheduling_eff'][trace] = 'Non-Avail'
        except:
            omp_talp_factors['omp_talp_parallel_eff'][trace] = 'NaN'
            omp_talp_factors['omp_talp_serial_eff'][trace] = 'NaN'
            omp_talp_factors['omp_talp_load_balance'][trace] = 'NaN'
            omp_talp_factors['omp_talp_scheduling_eff'][trace] = 'NaN'

        # -------> Classic MPI+GPU model using flattened devices
        if (outmpi_measures and is_mpi_gpu and cmdl_args.pop_model_to_apply == 'classic'):
            try:
                p = int(raw_data['count_host_threads'][trace])
                d = int(raw_data['count_devices'][trace])
                runtime = float(raw_data['runtime'][trace])

                useful_host = float(raw_data['useful_host'][trace])
                useful_host_max = float(raw_data['useful_host_max'][trace])

                useful_device = float(raw_data['useful_device'][trace])
                useful_device_max = float(raw_data['useful_device_max'][trace])

                parallel_units = p + d
                useful_total = useful_host + useful_device
                useful_max = max(useful_host_max, useful_device_max)

                hybrid_parallel_eff = (
                    useful_total / (parallel_units * runtime) * 100.0
                )

                hybrid_load_balance = (
                    (useful_total / parallel_units) / useful_max * 100.0
                )

                hybrid_comm_eff = (
                    useful_max / runtime * 100.0
                )

                hybrid_gpu_factors['hybrid_eff'][trace] = hybrid_parallel_eff

                hybrid_gpu_factors['mpi_parallel_eff'][trace] = hybrid_factors['mpi_parallel_eff'][trace]
                hybrid_gpu_factors['mpi_load_balance'][trace] = hybrid_factors['mpi_load_balance'][trace]
                hybrid_gpu_factors['mpi_comm_eff'][trace] = hybrid_factors['mpi_comm_eff'][trace]
                hybrid_gpu_factors['serial_eff'][trace] = hybrid_factors['serial_eff'][trace]
                hybrid_gpu_factors['transfer_eff'][trace] = hybrid_factors['transfer_eff'][trace]

                hybrid_gpu_factors['omp_parallel_eff'][trace] = (
                    hybrid_parallel_eff
                    / float(hybrid_factors['mpi_parallel_eff'][trace])
                    * 100.0
                )

                hybrid_gpu_factors['omp_load_balance'][trace] = (
                    hybrid_load_balance
                    / float(hybrid_factors['mpi_load_balance'][trace])
                    * 100.0
                )

                hybrid_gpu_factors['omp_comm_eff'][trace] = (
                    hybrid_comm_eff
                    / float(hybrid_factors['mpi_comm_eff'][trace])
                    * 100.0
                )
            except Exception:
                hybrid_gpu_factors['hybrid_eff'][trace] = 'NaN'
                hybrid_gpu_factors['omp_parallel_eff'][trace] = 'NaN'
                hybrid_gpu_factors['omp_load_balance'][trace] = 'NaN'
                hybrid_gpu_factors['omp_comm_eff'][trace] = 'NaN'



  # ------->  HOST metrics
        try:  # except NaN
            if outmpi_measures and is_mpi_gpu:
                host_factors['mpi_parallel_eff'][trace] = hybrid_factors['mpi_parallel_eff'][trace]
                host_factors['mpi_comm_eff'][trace] = hybrid_factors['mpi_comm_eff'][trace]
                host_factors['mpi_load_balance'][trace] = hybrid_factors['mpi_load_balance'][trace]
            else:
                host_factors['mpi_parallel_eff'][trace] = 'Non-Avail'
                host_factors['mpi_comm_eff'][trace] = 'Non-Avail'
                host_factors['mpi_load_balance'][trace] = 'Non-Avail'
        except:
            host_factors['mpi_parallel_eff'][trace] = 'NaN'
            host_factors['mpi_comm_eff'][trace] = 'NaN'
            host_factors['mpi_load_balance'][trace] = 'NaN'

    # ------------> BEGIN MPI communication sub-metrics HOST
        #### HOST Serialization
        try:
            if not outmpi_measures or cmdl_args.skip_simulation:
                host_factors['serial_eff'][trace] = 'Non-Avail'

            elif trace_mode[trace] == 'Detailed+MPI+CUDA':
                host_factors['serial_eff'][trace] = \
                    hybrid_factors['serial_eff'][trace]

            else:
                host_factors['serial_eff'][trace] = 'Non-Avail'

        except:
            host_factors['serial_eff'][trace] = 'NaN'

        #### HOST Transfer
        try:
            if not outmpi_measures or cmdl_args.skip_simulation:
                host_factors['transfer_eff'][trace] = 'Non-Avail'

            elif trace_mode[trace] == 'Detailed+MPI+CUDA':
                host_factors['transfer_eff'][trace] = \
                    hybrid_factors['transfer_eff'][trace]

            else:
                host_factors['transfer_eff'][trace] = 'Non-Avail'

        except:
            host_factors['transfer_eff'][trace] = 'NaN'

    # --------------> END MPI communication sub-metrics HOST
        
        ### Offloading
        try:  # except NaN
            if not outmpi_measures:
                host_factors['dev_offload_eff'][trace] = 'Non-Avail'
            elif is_mpi_gpu:
                host_factors['dev_offload_eff'][trace] = 100 * (float(raw_data['useful_host'][trace])\
                /float(raw_data['outsidempi_tot'][trace]) )
            else:
                host_factors['dev_offload_eff'][trace] = 'N/A'
        except:
            host_factors['dev_offload_eff'][trace] = 'NaN'
        
        ### Host Parallel Efficiency
        try:  # except NaN
            if not outmpi_measures:
                host_factors['host_parallel_eff'][trace] = 'Non-Avail'
            elif is_mpi_gpu:
                host_factors['host_parallel_eff'][trace] = (host_factors['mpi_parallel_eff'][trace]/100) \
                * (host_factors['dev_offload_eff'][trace]/100) * 100
            else:
                host_factors['host_parallel_eff'][trace] = 'N/A'
        except:
            host_factors['host_parallel_eff'][trace] = 'NaN'    

    # ------->  Devices metrics
        try:  # except NaN
            if not outmpi_measures:
                device_factors['dev_parallel_eff'][trace] = 'Non-Avail'
                device_factors['dev_load_balance'][trace] = 'Non-Avail'
                device_factors['dev_comm_eff'][trace] = 'Non-Avail'
                device_factors['dev_orches_eff'][trace] = 'Non-Avail'
                host_factors['dev_offload_eff'][trace] = 'Non-Avail'
            elif is_mpi_gpu:
                device_factors['dev_parallel_eff'][trace] = 100 * (float(raw_data['useful_device'][trace])\
                /(int(raw_data['count_devices'][trace])*float(raw_data['runtime'][trace])))

                device_factors['dev_load_balance'][trace] = 100 * ( (float(raw_data['useful_device'][trace])/int(raw_data['count_devices'][trace]))\
                /float(raw_data['useful_device_max'][trace]) )

                device_factors['dev_comm_eff'][trace] = 100 * ( float(raw_data['useful_device_max'][trace])\
                /float(raw_data['useful_memtransf_device_max'][trace]) )
                
                device_factors['dev_orches_eff'][trace] = 100 * ( float(raw_data['useful_memtransf_device_max'][trace]) \
                / float(raw_data['runtime'][trace]) )
            else:
                device_factors['dev_parallel_eff'][trace] = 'N/A'
                device_factors['dev_load_balance'][trace] = 'N/A'
                device_factors['dev_comm_eff'][trace] = 'N/A'
                device_factors['dev_orches_eff'][trace] = 'N/A'   
        except:
            if (raw_data['count_devices'][trace] <= 0 and raw_data['runtime'][trace] <= 0.0):
                device_factors['dev_parallel_eff'][trace] = 'NaN'
            if (raw_data['count_devices'][trace] <= 0):
                device_factors['dev_load_balance'][trace] = 'NaN'
            if (raw_data['useful_memtransf_device_max'][trace]<= 0.0):
                device_factors['dev_comm_eff'][trace] = 'NaN'
            if (raw_data['runtime'][trace] <= 0.0):
                device_factors['dev_orches_eff'][trace] = 'NaN'           
        
        # Device Computation Scalability
        try:  # except NaN
            if outmpi_measures and is_mpi_gpu and (len(trace_list) > 1):
                if scaling == 'strong':
                        device_factors['dev_comp_scale'][trace] = float(raw_data['useful_device'][trace_list[0]]) \
                                                   / float(raw_data['useful_device'][trace]) * 100.0
                else:
                    device_factors['dev_comp_scale'][trace] = float(raw_data['useful_device'][trace_list[0]]) \
                                                   / float(raw_data['useful_device'][trace]) * proc_ratio * 100.0
            else:
                device_factors['dev_comp_scale'][trace] = 'Non-Avail'
        except:
               device_factors['dev_comp_scale'][trace] = 'NaN'
        
        # Device Global Efficiency
        try:  # except NaN
            if outmpi_measures and is_mpi_gpu:
                if (len(trace_list) > 1):
                    device_factors['dev_global_eff'][trace] = (device_factors['dev_parallel_eff'][trace]/100) \
                    * (device_factors['dev_comp_scale'][trace]/100) * 100
                else:
                    device_factors['dev_global_eff'][trace] = device_factors['dev_parallel_eff'][trace]
        except:
            device_factors['dev_global_eff'][trace] = 'NaN'

    # ------->  Global Hybrid Metric
        try:  # except NaN
            if not outmpi_measures:
                hybrid_factors['hybrid_eff'][trace] = 'Non-Avail'

            elif (is_mpi_gpu and cmdl_args.pop_model_to_apply == 'classic'):
                hybrid_factors['hybrid_eff'][trace] = hybrid_gpu_factors['hybrid_eff'][trace]
                # Already computed directly from host useful time + flattened device useful time.
                pass
            elif trace_mode[trace][0:len("Detailed+MPI+")] == "Detailed+MPI+":
                hybrid_factors['hybrid_eff'][trace] = float(hybrid_factors['mpi_parallel_eff'][trace]) \
                                            * float(hybrid_factors['omp_parallel_eff'][trace]) / 100.0
            else:
                hybrid_factors['hybrid_eff'][trace] = 'N/A'
        except:
            hybrid_factors['hybrid_eff'][trace] = 'NaN'

    # Basic scalability factors - Computational
        # IPC   
        if (raw_data['useful_ins'][trace] == 'Non-Avail'
            or raw_data['useful_cyc'][trace] == 'Non-Avail'):
            other_metrics['ipc'][trace] = 'Non-Avail'
        else:
            try:
                if float(raw_data['useful_cyc'][trace]) > 0.0:
                    other_metrics['ipc'][trace] = (
                        float(raw_data['useful_ins'][trace])
                        / float(raw_data['useful_cyc'][trace])
                    )
                else:
                    other_metrics['ipc'][trace] = 'Non-Avail'
            except (TypeError, ValueError):
                other_metrics['ipc'][trace] = 'NaN'

        # IPC Scalability
        if len(trace_list) > 1:
            if (
                other_metrics['ipc'][trace] == 'Non-Avail'
                or other_metrics['ipc'][trace_list[0]] == 'Non-Avail'
            ):
                mod_factors['ipc_scale'][trace] = 'Non-Avail'

                if outmpi_measures and is_mpi_gpu:
                    host_factors['host_ipc_scale'][trace] = 'Non-Avail'

            elif trace_mode[trace][:5] != 'Burst' and trace_mode[trace] != 'Sampling':
                try:
                    mod_factors['ipc_scale'][trace] = (
                        float(other_metrics['ipc'][trace])
                        / float(other_metrics['ipc'][trace_list[0]])
                        * 100.0
                    )

                    if outmpi_measures and is_mpi_gpu:
                        host_factors['host_ipc_scale'][trace] = \
                            mod_factors['ipc_scale'][trace]
                    else:
                        host_factors['host_ipc_scale'][trace] = 'Non-Avail'

                except (TypeError, ValueError, ZeroDivisionError):
                    mod_factors['ipc_scale'][trace] = 'NaN'
                    host_factors['host_ipc_scale'][trace] = 'NaN'
        else:
            mod_factors['ipc_scale'][trace] = 'Non-Avail'
            host_factors['host_ipc_scale'][trace] = 'Non-Avail'


        # IPC scale + Serial I/O
        try:  # except NaN
            if len(trace_list) > 1:
                if other_metrics['io_posix'][trace] > 0.0 or other_metrics['flushing'][trace] > 0.0:
                    ipc_serial_io_0 = (raw_data['useful_ins'][trace_list[0]] + raw_data['io_ins'][trace_list[0]]
                                       + raw_data['flushing_ins'][trace_list[0]]) \
                                      / (raw_data['useful_cyc'][trace_list[0]] + raw_data['io_cyc'][trace_list[0]]
                                         + raw_data['flushing_cyc'][trace_list[0]])

                    ipc_serial_io_n = (raw_data['useful_ins'][trace] + raw_data['io_ins'][trace]
                                       + raw_data['flushing_ins'][trace])\
                                      / (raw_data['useful_cyc'][trace] + raw_data['io_cyc'][trace]
                                         + raw_data['flushing_cyc'][trace])
                    mod_factors_scale_plus_io['ipc_scale'][trace] = float(ipc_serial_io_n / ipc_serial_io_0 * 100.0)
                else:
                    mod_factors_scale_plus_io['ipc_scale'][trace] = float(mod_factors['ipc_scale'][trace])
            else:
                mod_factors_scale_plus_io['ipc_scale'][trace] = 'Non-Avail'
        except:
            mod_factors_scale_plus_io['ipc_scale'][trace] = 'NaN'

        # Frequency
        try:
            if (
                raw_data['useful_cyc'][trace] == 'Non-Avail'
                or raw_data['frequency'][trace] == 'Non-Avail'
                or raw_data['useful_cyc'][trace] == 0
            ):
                other_metrics['freq'][trace] = 'Non-Avail'
            else:
                other_metrics['freq'][trace] = (
                    float(raw_data['frequency'][trace]) / 1000
                )

        except (TypeError, ValueError):
            other_metrics['freq'][trace] = 'NaN'

        # Frequency Scalability
        try:
            if len(trace_list) > 1:

                if (
                    other_metrics['freq'][trace] == 'Non-Avail'
                    or other_metrics['freq'][trace_list[0]] == 'Non-Avail'
                ):
                    mod_factors['freq_scale'][trace] = 'Non-Avail'
                    host_factors['host_freq_scale'][trace] = 'Non-Avail'

                elif trace_mode[trace][:5] != 'Burst' and trace_mode[trace] != 'Sampling':

                    mod_factors['freq_scale'][trace] = (
                        float(other_metrics['freq'][trace])
                        / float(other_metrics['freq'][trace_list[0]])
                        * 100.0
                    )

                    if outmpi_measures and is_mpi_gpu:
                        host_factors['host_freq_scale'][trace] = \
                            mod_factors['freq_scale'][trace]
                    else:
                        host_factors['host_freq_scale'][trace] = 'Non-Avail'

                else:
                    mod_factors['freq_scale'][trace] = 'Non-Avail'
                    host_factors['host_freq_scale'][trace] = 'Non-Avail'

            else:
                mod_factors['freq_scale'][trace] = 'Non-Avail'
                host_factors['host_freq_scale'][trace] = 'Non-Avail'

        except (TypeError, ValueError, ZeroDivisionError):
            mod_factors['freq_scale'][trace] = 'NaN'
            host_factors['host_freq_scale'][trace] = 'NaN'


        # freq scale + Serial I/O
        try:  # except NaN
            if len(trace_list) > 1:
                if other_metrics['io_posix'][trace] > 0.0 or other_metrics['flushing'][trace] > 0.0:
                    freq_serial_io_0 = (float(raw_data['useful_cyc'][trace_list[0]])
                                        + float(raw_data['io_cyc'][trace_list[0]])
                                        + float(raw_data['flushing_cyc'][trace_list[0]]))\
                                       / (raw_data['useful_not_0_tot'][trace_list[0]]
                                          + float(raw_data['io_tot'][trace_list[0]])
                                          + float(raw_data['flushing_tot'][trace_list[0]])) / 1000

                    freq_serial_io_n = (float(raw_data['useful_cyc'][trace])
                                              + float(raw_data['io_cyc'][trace])
                                              + float(raw_data['flushing_cyc'][trace]))\
                                       / (float(raw_data['useful_not_0_tot'][trace])
                                          + float(raw_data['io_tot'][trace])
                                          + float(raw_data['flushing_tot'][trace])) / 1000
                    mod_factors_scale_plus_io['freq_scale'][trace] = float(freq_serial_io_n / freq_serial_io_0 * 100.0)
                else:
                    mod_factors_scale_plus_io['freq_scale'][trace] = float(mod_factors['freq_scale'][trace])
            else:
                mod_factors_scale_plus_io['freq_scale'][trace] = 'Non-Avail'
        except:
            mod_factors_scale_plus_io['freq_scale'][trace] = 'NaN'

    # Instruction Scalability
        try:
            if len(trace_list) > 1:

                # Hardware counter unavailable in current trace
                # or in the reference trace.
                if (
                    raw_data['useful_ins'][trace] == 'Non-Avail'
                    or raw_data['useful_ins'][trace_list[0]] == 'Non-Avail'
                ):
                    mod_factors['inst_scale'][trace] = 'Non-Avail'
                    host_factors['host_inst_scale'][trace] = 'Non-Avail'

                elif trace_mode[trace][:5] != 'Burst' and trace_mode[trace] != 'Sampling':

                    if scaling == 'strong':
                        mod_factors['inst_scale'][trace] = (
                            float(raw_data['useful_ins'][trace_list[0]])
                            / float(raw_data['useful_ins'][trace])
                            * 100.0
                        )

                    else:
                        procs_ratio_ins = (
                            float(raw_data['procs_ins'][trace])
                            / float(raw_data['procs_ins'][trace_list[0]])
                        )

                        mod_factors['inst_scale'][trace] = (
                            float(raw_data['useful_ins'][trace_list[0]])
                            / float(raw_data['useful_ins'][trace])
                            * procs_ratio_ins
                            * 100.0
                        )

                    if outmpi_measures and is_mpi_gpu:
                        host_factors['host_inst_scale'][trace] = \
                            mod_factors['inst_scale'][trace]
                    else:
                        host_factors['host_inst_scale'][trace] = 'Non-Avail'

                else:
                    mod_factors['inst_scale'][trace] = 'Non-Avail'
                    host_factors['host_inst_scale'][trace] = 'Non-Avail'

            else:
                mod_factors['inst_scale'][trace] = 'Non-Avail'
                host_factors['host_inst_scale'][trace] = 'Non-Avail'

        except (TypeError, ValueError, ZeroDivisionError):
            mod_factors['inst_scale'][trace] = 'NaN'
            host_factors['host_inst_scale'][trace] = 'NaN'


        # ins scale + Serial I/O
        try:  # except NaN
            if len(trace_list) > 1:
                if other_metrics['io_posix'][trace] > 0.0 or other_metrics['flushing'][trace] > 0.0:
                    useful_ins_plus_io_0 = float(raw_data['useful_ins'][trace_list[0]]) \
                                       + float(raw_data['io_ins'][trace_list[0]]) \
                                       + float(raw_data['flushing_ins'][trace_list[0]])
                    useful_ins_plus_io_n = float(raw_data['useful_ins'][trace]) \
                                       + float(raw_data['io_ins'][trace]) \
                                       + float(raw_data['flushing_ins'][trace])
                    if scaling == 'strong':
                        mod_factors_scale_plus_io['inst_scale'][trace] = float(useful_ins_plus_io_0) \
                                                                 / float(useful_ins_plus_io_n) * 100.0
                    else:
                        procs_ratio_ins = float(raw_data['procs_ins'][trace]) \
                                          / float(raw_data['procs_ins'][trace_list[0]])
                        mod_factors_scale_plus_io['inst_scale'][trace] = float(useful_ins_plus_io_0) \
                                                                         / float(useful_ins_plus_io_n)\
                                                                         * procs_ratio_ins * 100.0
                else:
                    mod_factors_scale_plus_io['inst_scale'][trace] = float(mod_factors['inst_scale'][trace])
            else:
                mod_factors_scale_plus_io['inst_scale'][trace] = 'Non-Avail'
        except:
            mod_factors_scale_plus_io['inst_scale'][trace] = 'NaN'

       
        try:  # except NaN
            if outmpi_measures and is_mpi_gpu:
                if len(trace_list) > 1:
                    host_factors['host_global_eff'][trace] = (host_factors['host_parallel_eff'][trace]/100) \
                * (host_factors['host_comp_scale'][trace]/100) * 100
                else:
                    host_factors['host_global_eff'][trace] = host_factors['host_parallel_eff'][trace]
            else:
                host_factors['host_global_eff'][trace] = 'Non-Avail'  
        except:
            host_factors['host_global_eff'][trace] = 'NaN'

        try:  # except NaN
            if len(trace_list) > 1:
                if scaling == 'strong':
                    other_metrics['speedup'][trace] = float(raw_data['runtime'][trace_list[0]]
                                                            / raw_data['runtime'][trace])
                else:
                    other_metrics['speedup'][trace] = float(raw_data['runtime'][trace_list[0]]
                                                            / raw_data['runtime'][trace] * proc_ratio)
            else:
                other_metrics['speedup'][trace] = 'Non-Avail'
        except:
            other_metrics['speedup'][trace] = 'NaN'

        try:  # except NaN
            other_metrics['elapsed_time'][trace] = float(raw_data['runtime'][trace] * 0.000001)
        except:
            other_metrics['elapsed_time'][trace] = 'NaN'

        try:  # except NaN
            if len(trace_list) > 1:
                #other_metrics['efficiency'][trace] = other_metrics['speedup'][trace] / proc_ratio
                if scaling == 'strong':
                    other_metrics['efficiency'][trace] = raw_data['runtime'][trace_list[0]] \
                                                        / (raw_data['runtime'][trace] * proc_ratio)
                else:
                    other_metrics['efficiency'][trace] = raw_data['runtime'][trace_list[0]] \
                                                        / raw_data['runtime'][trace]
            else:
                other_metrics['efficiency'][trace] = 'Non-Avail'
        except:
            other_metrics['efficiency'][trace] = 'NaN'

    return (
        mod_factors,
        mod_factors_scale_plus_io,
        hybrid_factors,
        hyb_comm_omp_factors,
        other_metrics,
        device_factors,
        host_factors,
        hybrid_gpu_factors,
        omp_talp_factors,
        scaling_info,
    )

def print_mod_factors_table(mod_factors, other_metrics, mod_factors_scale_plus_io,
                            hybrid_factors, hyb_comm_omp_factors, device_factors,
                            trace_list, trace_processes, trace_tasks, trace_threads,
                            trace_mode, raw_data, cmdl_args):
    """Prints the model factors table in human readable form on stdout."""
    global mod_factors_doc, mod_hybrid_factors_doc, mod_hyb_comm_omp_factors_doc, mod_device_factors_doc

    show_hyb_comm_omp = cmdl_args.hyb_mpiomp and any(
        trace_mode[trace] == "Detailed+MPI+OpenMP" for trace in trace_list
    )

    warning_io = []
    warning_flush = []
    warning_flush_wrong = []
    warning_simulation = []
    for trace in trace_list:
        if 10.0 <= other_metrics['flushing'][trace] < 15.0:
            warning_flush.append(1)
        elif other_metrics['flushing'][trace] >= 15.0:
            warning_flush_wrong.append(1)
        if other_metrics['io_posix'][trace] >= 5.0:
            warning_io.append(1)
        if hybrid_factors['serial_eff'][trace] == "Warning!" \
                or hybrid_factors['serial_eff'][trace] == "Warning!":
            warning_simulation.append(1)

    if len(warning_flush_wrong) > 0:
        print("WARNING! Flushing in a trace is too high. Disabling standard output metrics...")
        print("         Flushing is an overhead due to the tracer, please review your trace.")
        print('')
        return

    count_mode = 0
    for trace in trace_list:
        if trace_mode[trace][0:len("Detailed+MPI+")] == "Detailed+MPI+":
            count_mode += 1

    if count_mode == len(trace_list):
        del(mod_factors['serial_eff'])
        del(mod_factors['transfer_eff'])
        del(mod_factors_doc['serial_eff'])
        del(mod_factors_doc['transfer_eff'])

    # Update the hybrid parallelism mode
    trace_mode_doc = trace_mode[trace_list[0]]
    if trace_mode_doc[0:len("Detailed+MPI+")] == "Detailed+MPI+":
        mod_hybrid_factors_doc['omp_parallel_eff'] = "   -- " + \
                                                     trace_mode_doc[len("Detailed+MPI+"):] + " Parallel efficiency"
        mod_hybrid_factors_doc['omp_load_balance'] = "      -- " + \
                                                     trace_mode_doc[len("Detailed+MPI+"):] + " Load Balance"
        mod_hybrid_factors_doc['omp_comm_eff'] = "      -- " + \
                                                 trace_mode_doc[len("Detailed+MPI+"):] + " Communication efficiency"

    print('\n Overview of the Efficiency metrics:')

    longest_name = len(sorted(mod_hybrid_factors_doc.values(), key=len)[-1])
    if show_hyb_comm_omp:
        longest_name = max(longest_name, len(sorted(mod_hyb_comm_omp_factors_doc.values(), key=len)[-1]))

    line = 'Configuration'.rjust(longest_name)

    line_trace_mode = 'Trace mode'.rjust(longest_name)

    configuration_labels = _build_hybrid_configuration_labels(
        trace_list,
        trace_processes,
        trace_tasks,
        trace_threads,
        trace_mode,
        raw_data,
    )

    max_len_header = max(
        len(label)
        for label in configuration_labels
    )

    value_to_adjust = max(
        14,
        max_len_header + 1,
    )

    label_xtics = []
    label_trace_mode = []
    mode_string = ""

    for index, trace in enumerate(trace_list):
        line += ' | '
        line_trace_mode += ' | '

        s_xtics = configuration_labels[index]

        label_xtics.append(s_xtics)
        line += s_xtics.rjust(value_to_adjust)

        if trace_mode[trace][0:len("Detailed")] == "Detailed":
            mode_string = trace_mode[trace][len("Detailed+"):]
        elif trace_mode[trace][0:len("Burst")] == "Burst":
            mode_string = trace_mode[trace]
        elif trace_mode[trace] == "Sampling":
            mode_string = trace_mode[trace]

        line_trace_mode += mode_string.rjust(value_to_adjust)
        label_trace_mode.append(mode_string)

    print(''.ljust(len(line), '='))
    print(line_trace_mode)
    print(line)
    line_procs_factors = line

    print(''.ljust(len(line), '='))

    for mod_key in mod_factors_doc:
        line = mod_factors_doc[mod_key].ljust(longest_name)
        for trace in trace_list:
            line += ' | '
            try:
                line += ('{0:.2f}%'.format(mod_factors[mod_key][trace])).rjust(value_to_adjust)
            except ValueError:
                line += ('{}'.format(mod_factors[mod_key][trace])).rjust(value_to_adjust)
        print(line)

    io_metrics = []
    io_metrics.append(0)
    for mod_key in mod_factors_scale_plus_io_doc:
        for trace in trace_list:
            if mod_factors_scale_plus_io[mod_key][trace] != 0:
                io_metrics.append(1)

    if (len(warning_flush) >= 1 or len(warning_io) >= 1) and len(trace_list) > 1:
        print(''.ljust(len(line_procs_factors), '-'))
        for mod_key in mod_factors_scale_plus_io_doc:
            line = mod_factors_scale_plus_io_doc[mod_key].ljust(longest_name)
            for trace in trace_list:
                line += ' | '
                try:
                    line += ('{0:.2f}%'.format(mod_factors_scale_plus_io[mod_key][trace])).rjust(value_to_adjust)
                except ValueError:
                    line += ('{}'.format(mod_factors_scale_plus_io[mod_key][trace])).rjust(value_to_adjust)
            print(line)
        print(''.ljust(len(line_procs_factors), '='))
    else:
        print(''.ljust(len(line_procs_factors), '-'))

    for mod_key in mod_hybrid_factors_doc:
        line = mod_hybrid_factors_doc[mod_key].ljust(longest_name)
        for trace in trace_list:
            line += ' | '
            try:
                if str(hybrid_factors[mod_key][trace]) != 'nan':
                    line += ('{0:.2f}%'.format(hybrid_factors[mod_key][trace])).rjust(value_to_adjust)
                elif str(hybrid_factors[mod_key][trace]) == 'nan':
                    line += ('{}'.format('NaN')).rjust(value_to_adjust)
                else:
                    line += ('{}'.format(hybrid_factors[mod_key][trace])).rjust(value_to_adjust)
            except ValueError:
                line += ('{}'.format(hybrid_factors[mod_key][trace])).rjust(value_to_adjust)
        print(line)

    if show_hyb_comm_omp:
        #print(''.ljust(len(line_procs_factors), '-'))
        for mod_key in mod_hyb_comm_omp_factors_doc:
            line = mod_hyb_comm_omp_factors_doc[mod_key].ljust(longest_name)
            for trace in trace_list:
                line += ' | '
                try:
                    if str(hyb_comm_omp_factors[mod_key][trace]) != 'nan':
                        line += ('{0:.2f}%'.format(hyb_comm_omp_factors[mod_key][trace])).rjust(value_to_adjust)
                    elif str(hyb_comm_omp_factors[mod_key][trace]) == 'nan':
                        line += ('{}'.format('NaN')).rjust(value_to_adjust)
                    else:
                        line += ('{}'.format(hyb_comm_omp_factors[mod_key][trace])).rjust(value_to_adjust)
                except ValueError:
                    line += ('{}'.format(hyb_comm_omp_factors[mod_key][trace])).rjust(value_to_adjust)
            print(line)

    print(''.ljust(len(line_procs_factors), '='))
    if len(warning_simulation) > 0:
        print("===> Warning! Metrics obtained from simulated traces exceed 100%. "
              "Please review original and simulated traces.")
    print('')


#### TALP metrics
def print_mod_factors_table_talp(mod_factors, other_metrics, mod_factors_scale_plus_io, hybrid_factors,device_factors, host_factors , trace_list,
                            trace_processes, trace_tasks, trace_threads, trace_mode, raw_data):
    """Prints the model factors table in human readable form on stdout."""  
    global mod_factors_doc, mod_hybrid_factors_doc, mod_device_factors_doc,mod_host_factors_doc

    warning_io = []
    warning_flush = []
    warning_flush_wrong = []
    warning_simulation = []
    for trace in trace_list:
        if 10.0 <= other_metrics['flushing'][trace] < 15.0:
            warning_flush.append(1)
        elif other_metrics['flushing'][trace] >= 15.0:
            warning_flush_wrong.append(1)
        if other_metrics['io_posix'][trace] >= 5.0:
            warning_io.append(1)
        if hybrid_factors['serial_eff'][trace] == "Warning!" \
                or hybrid_factors['serial_eff'][trace] == "Warning!":
            warning_simulation.append(1)

    if len(warning_flush_wrong) > 0:
        print("WARNING! Flushing in a trace is too high. Disabling standard output metrics...")
        print("         Flushing is an overhead due to the tracer, please review your trace.")
        print('')
        return

    count_mode = 0
    for trace in trace_list:
        if trace_mode[trace][0:len("Detailed+MPI+")] == "Detailed+MPI+":
            count_mode += 1

    if count_mode == len(trace_list):
        del(mod_factors['serial_eff'])
        del (mod_factors['transfer_eff'])
        del(mod_factors_doc['serial_eff'])
        del (mod_factors_doc['transfer_eff'])

    # Update the hybrid parallelism mode
    trace_mode_doc = trace_mode[trace_list[0]]
    if trace_mode_doc[0:len("Detailed+MPI+")] == "Detailed+MPI+":
        mod_hybrid_factors_doc['omp_parallel_eff'] = "   -- " + \
                                                     trace_mode_doc[len("Detailed+MPI+"):] + " Parallel efficiency"
        mod_hybrid_factors_doc['omp_load_balance'] = "      -- " + \
                                                     trace_mode_doc[len("Detailed+MPI+"):] + " Load Balance"
        mod_hybrid_factors_doc['omp_comm_eff'] = "      -- " + \
                                                 trace_mode_doc[len("Detailed+MPI+"):] + " Communication efficiency"
    
    # print('')
    print('\n Overview of the Efficiency metrics:')

    longest_name = len(sorted(mod_hybrid_factors_doc.values(), key=len)[-1])
    
    line = 'Configuration'.rjust(longest_name)
    line_trace_mode = 'Trace mode'.rjust(longest_name)

    configuration_labels = _build_hybrid_configuration_labels(
        trace_list,
        trace_processes,
        trace_tasks,
        trace_threads,
        trace_mode,
        raw_data,
    )

    max_len_header = max(
        len(label)
        for label in configuration_labels
    )

    value_to_adjust = max(
        14,
        max_len_header + 1,
    )

    label_xtics = []
    label_trace_mode = []
    mode_string = ""

    for index, trace in enumerate(trace_list):
        line += ' | '
        line_trace_mode += ' | '

        s_xtics = configuration_labels[index]

        label_xtics.append(s_xtics)
        line += s_xtics.rjust(value_to_adjust)

        if trace_mode[trace][0:len("Detailed")] == "Detailed":
            mode_string = trace_mode[trace][len("Detailed+"):]
        elif trace_mode[trace][0:len("Burst")] == "Burst":
            mode_string = trace_mode[trace]
        elif trace_mode[trace] == "Sampling":
            mode_string = trace_mode[trace]

        line_trace_mode += mode_string.rjust(value_to_adjust)
        label_trace_mode.append(mode_string)

    print(''.ljust(len(line), '='))
    print(line_trace_mode)
    print(line)
    line_procs_factors = line

    print(''.ljust(len(line), '='))

    io_metrics = []
    io_metrics.append(0)
    for mod_key in mod_factors_scale_plus_io_doc:
        for trace in trace_list:
            if mod_factors_scale_plus_io[mod_key][trace] != 0:
                io_metrics.append(1)

    if (len(warning_flush) >= 1 or len(warning_io) >= 1) and len(trace_list) > 1:
        print(''.ljust(len(line_procs_factors), '-'))
        for mod_key in mod_factors_scale_plus_io_doc:
            line = mod_factors_scale_plus_io_doc[mod_key].ljust(longest_name)
            for trace in trace_list:
                line += ' | '
                try:  # except NaN
                    line += ('{0:.2f}%'.format(mod_factors_scale_plus_io[mod_key][trace])).rjust(value_to_adjust)
                except ValueError:
                    line += ('{}'.format(mod_factors_scale_plus_io[mod_key][trace])).rjust(value_to_adjust)
            print(line)
        print(''.ljust(len(line_procs_factors), '='))
    else:
        print(''.ljust(len(line_procs_factors), '-'))
        
    for mod_key in mod_host_factors_doc:
        line = mod_host_factors_doc[mod_key].ljust(longest_name)
        for trace in trace_list:
            line += ' | '
            try:  # except NaN
                if str(host_factors[mod_key][trace]) != 'nan':
                    line += ('{0:.2f}%'.format(host_factors[mod_key][trace])).rjust(value_to_adjust)
                elif str(host_factors[mod_key][trace]) == 'nan':
                    line += ('{}'.format('NaN')).rjust(value_to_adjust)
                else:
                    line += ('{}'.format(host_factors[mod_key][trace])).rjust(value_to_adjust)
            except ValueError:
                line += ('{}'.format(host_factors[mod_key][trace])).rjust(value_to_adjust)
        print(line)
## TO Devices metrics
    print(''.ljust(len(line_procs_factors), '-'))
    for mod_key in mod_device_factors_doc:
        line = mod_device_factors_doc[mod_key].ljust(longest_name)
        for trace in trace_list:
            line += ' | '
            try:  # except NaN
                if str(device_factors[mod_key][trace]) != 'nan':
                    line += ('{0:.2f}%'.format(device_factors[mod_key][trace])).rjust(value_to_adjust)
                elif str(device_factors[mod_key][trace]) == 'nan':
                    line += ('{}'.format('NaN')).rjust(value_to_adjust)
                else:
                    line += ('{}'.format(device_factors[mod_key][trace])).rjust(value_to_adjust)
            except ValueError:
                line += ('{}'.format(device_factors[mod_key][trace])).rjust(value_to_adjust)
        print(line)    

#####
    print(''.ljust(len(line_procs_factors), '='))
    if len(warning_simulation) > 0:
        print("===> Warning! Metrics obtained from simulated traces exceed 100%. "
              "Please review original and simulated traces.")
    print('')


def print_other_metrics_table(
        other_metrics,
        trace_list,
        trace_processes,
        trace_tasks,
        trace_threads,
        trace_mode,
        raw_data):    
    """Prints the other metrics table in human readable form on stdout."""
    global other_metrics_doc

    print('Overview of the Efficiency, Speedup, IPC and Frequency:')

    longest_name = len(sorted(other_metrics_doc.values(), key=len)[-1])

    line = 'Configuration'.rjust(longest_name)

    configuration_labels = _build_hybrid_configuration_labels(
        trace_list,
        trace_processes,
        trace_tasks,
        trace_threads,
        trace_mode,
        raw_data,
    )

    max_len_header = max(
        len(label)
        for label in configuration_labels
    )

    value_to_adjust = max(
        10,
        max_len_header + 1,
    )

    for label in configuration_labels:
        line += ' | '
        line += label.rjust(value_to_adjust)

    print(''.ljust(len(line), '-'))
    print(line)
    line_head = line
    print(''.ljust(len(line), '-'))

    for mod_key in other_metrics_doc:
        line = other_metrics_doc[mod_key].ljust(longest_name)
        if len(trace_list) > 1:
            if mod_key in ['speedup', 'ipc', 'freq', 'elapsed_time', 'efficiency']:
                for trace in trace_list:
                    line += ' | '
                    try:  # except NaN
                        line += ('{0:.2f}'.format(other_metrics[mod_key][trace])).rjust(value_to_adjust)
                    except ValueError:
                        line += ('{}'.format(other_metrics[mod_key][trace])).rjust(value_to_adjust)
                print(line)
        else:
            if mod_key in ['ipc', 'freq', 'elapsed_time']:
                for trace in trace_list:
                    line += ' | '
                    try:  # except NaN
                        line += ('{0:.2f}'.format(other_metrics[mod_key][trace])).rjust(value_to_adjust)
                    except ValueError:
                        line += ('{}'.format(other_metrics[mod_key][trace])).rjust(value_to_adjust)
                print(line)
    print(''.ljust(len(line_head), '-'))
    # print('')

    warning_io = []
    warning_flush = []
    for trace in trace_list:
        if other_metrics['flushing'][trace] >= 10.0:
            warning_flush.append(1)
        if other_metrics['io_mpiio'][trace] >= 5.0 or other_metrics['io_posix'][trace] >= 5.0:
            warning_io.append(1)

    for mod_key in other_metrics_doc:
        line = other_metrics_doc[mod_key].ljust(longest_name)
        # Print empty line to separate values
        if mod_key in ['freq'] and len(warning_flush) > 0:
            print('')
            print("Overview of tracer\'s flushing weight:")
            print(''.ljust(len(line_head), '-'))

        if mod_key not in ['speedup', 'ipc', 'freq', 'elapsed_time', 'efficiency']:
            if mod_key in ['flushing']:
                for trace in trace_list:
                    line += ' | '
                    try:  # except NaN
                        line += ('{0:.2f}%'.format(other_metrics[mod_key][trace])).rjust(value_to_adjust)
                    except ValueError:
                        line += ('{}'.format(other_metrics[mod_key][trace])).rjust(value_to_adjust)
                if len(warning_flush) > 0:
                    print(line)
                    print(''.ljust(len(line_head), '-'))
            elif mod_key in ['io_mpiio','io_posix','io_eff']:
                for trace in trace_list:
                    line += ' | '
                    try:  # except NaN
                        line += ('{0:.2f}%'.format(other_metrics[mod_key][trace])).rjust(value_to_adjust)
                    except ValueError:
                        line += ('{}'.format(other_metrics[mod_key][trace])).rjust(value_to_adjust)
                if len(warning_io) > 0:
                    print(line)

        # Print headers I/O
        if mod_key in ['flushing'] and len(warning_io) > 0:
            print(''.ljust(len(line), ' '))
            print('Overview of File I/O weight:')
            print(''.ljust(len(line), '-'))
        if mod_key in ['io_eff'] and len(warning_io) > 0:
            print(''.ljust(len(line), '-'))
            # print('')

    if len(warning_flush) > 0:
        message_warning_flush = "WARNING! %Flushing is high and affects computation of efficiency metrics."
    else:
        message_warning_flush = ""
    if len(warning_io) > 0:
        message_warning_io = "WARNING! % File I/O is high and affects computation of efficiency metrics."
    else:
        message_warning_io = ""
    print(message_warning_flush+message_warning_io)
    # print('')


def print_efficiency_table(mod_factors, hybrid_factors, hyb_comm_omp_factors,
                           trace_list, trace_processes, trace_tasks, trace_threads,
                           trace_mode, raw_data, cmdl_args):
    """Prints the model factors table in a csv file for the efficiency heatmaps."""
    global mod_factors_doc, mod_hybrid_factors_doc, mod_hyb_comm_omp_factors_doc

    show_hyb_comm_omp = cmdl_args.hyb_mpiomp and any(
        trace_mode[trace] == "Detailed+MPI+OpenMP" for trace in trace_list
    )

    delimiter = ','

    configuration_labels = _build_hybrid_configuration_labels(
        trace_list,
        trace_processes,
        trace_tasks,
        trace_threads,
        trace_mode,
        raw_data,
    )


    file_path = os.path.join(os.getcwd(), 'efficiency_table_global.csv')
    with open(file_path, 'w') as output:

        line = '"Metric"'

        for label in configuration_labels:
            line += delimiter
            line += label        

        output.write(line + '\n')

        for mod_key in mod_factors_doc:
            if mod_key not in ['speedup', 
                                'ipc', 'freq', 'elapsed_time', 
                                'efficiency', 'flushing', 
                                'io_mpiio', 'io_posix']:

                line = "\"" + mod_factors_doc[mod_key] + "\""

                for trace in trace_list:
                    line += delimiter
                    try:
                        if mod_factors[mod_key][trace] in (
                                "Non-Avail",
                                "Warning!",
                                "N/A",
                                "NaN",
                        ):
                            line += str(mod_factors[mod_key][trace])
                        else:
                            line += '{0:.2f}'.format(
                                mod_factors[mod_key][trace]
                            )
                    except ValueError:
                        line += '{}'.format(mod_factors[mod_key][trace])
                output.write(line + '\n')

        # Create Gnuplot file for efficiency plot
        gp_template = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'cfgs', 'efficiency_table_global.gp')
        content = []

        with open(gp_template) as f:
            content = f.readlines()

        limit_procs = 500 + len(trace_list) * 65

        content = [line.replace('#REPLACE_BY_SIZE', ''.join(['set terminal pngcairo enhanced dashed crop size ',
                                                             str(limit_procs), ',460 font "Latin Modern Roman,14"']))
                   for line in content]

        file_path = os.path.join(os.getcwd(), 'efficiency_table_global.gp')
        with open(file_path, 'w') as f:
            f.writelines(content)

        if len(trace_list) > 1:
            print('Global Efficiency Table written to ' + file_path[:len(file_path) - 3] + '.gp')

    file_path = os.path.join(os.getcwd(), 'efficiency_table_hybrid.csv')
    with open(file_path, 'w') as output:

        line = '"Metric"'

        for label in configuration_labels:
            line += delimiter
            line += label
        output.write(line + '\n')

        for mod_key in mod_hybrid_factors_doc:

        # Preserve the complete hierarchy encoded in the
        # metric description. Do not strip leading spaces.
            line = "\"" + mod_hybrid_factors_doc[mod_key] + "\""

            for trace in trace_list:
                line += delimiter
                try:
                    if hybrid_factors[mod_key][trace] in (
                            "Non-Avail",
                            "Warning!",
                            "N/A",
                            "NaN",
                    ):
                        line += str(hybrid_factors[mod_key][trace])
                    else:
                        line += '{0:.2f}'.format(
                            hybrid_factors[mod_key][trace]
                        )
                except ValueError:
                    line += '{}'.format(hybrid_factors[mod_key][trace])

            output.write(line + '\n')

        if show_hyb_comm_omp:
            for mod_key in mod_hyb_comm_omp_factors_doc:
                line = "\"" + mod_hyb_comm_omp_factors_doc[mod_key] + "\""
                for trace in trace_list:
                    line += delimiter
                    try:
                        if hyb_comm_omp_factors[mod_key][trace] == "Non-Avail" or \
                           hyb_comm_omp_factors[mod_key][trace] == "Warning!":
                            line += '0.00'
                        else:
                            line += '{0:.2f}'.format(hyb_comm_omp_factors[mod_key][trace])
                    except ValueError:
                        line += '{}'.format(hyb_comm_omp_factors[mod_key][trace])
                output.write(line + '\n')

        # Create Gnuplot file for efficiency plot
        gp_template = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'cfgs', 'efficiency_table_hybrid.gp')
        content = []

        with open(gp_template) as f:
            content = f.readlines()

        limit_procs = 510 + len(trace_list) * 80

        content = [line.replace('#REPLACE_BY_SIZE', ''.join(['set terminal pngcairo enhanced dashed crop size ',
                                                             str(limit_procs), ',460 font "Latin Modern Roman,14"']))
                   for line in content]

        file_path = os.path.join(os.getcwd(), 'efficiency_table_hybrid.gp')
        with open(file_path, 'w') as f:
            f.writelines(content)

        if len(trace_list) > 1:
            print('Hybrid Efficiency Table written to ' + file_path[:len(file_path) - 3] + '.gp')


def print_mod_factors_csv(mod_factors, hybrid_factors, trace_list, trace_processes):
    """Prints the model factors table in a csv file."""
    global mod_factors_doc, mod_hybrid_factors_doc

    delimiter = ';'
    # File is stored in the trace directory
    # file_path = os.path.join(os.path.dirname(os.path.realpath(trace_list[0])), 'modelfactors.csv')
    # File is stored in the execution directory
    file_path = os.path.join(os.getcwd(), 'modelfactors.csv')

    with open(file_path, 'w') as output:
        line = "\"Number of processes\""
        for trace in trace_list:
            line += delimiter
            line += str(trace_processes[trace])
        output.write(line + '\n')

        for mod_key in mod_factors_doc:
            line = "\"" + mod_factors_doc[mod_key].replace('  ', '', 2) + "\""
            for trace in trace_list:
                line += delimiter
                try:  # except NaN
                    line += '{0:.6f}'.format(mod_factors[mod_key][trace])
                except ValueError:
                    line += '{}'.format(mod_factors[mod_key][trace])
            output.write(line + '\n')

        for mod_key in mod_hybrid_factors_doc:
            line = "\"" + mod_hybrid_factors_doc[mod_key].replace('  ', '', 2) + "\""
            for trace in trace_list:
                line += delimiter
                try:  # except NaN
                    line += '{0:.6f}'.format(hybrid_factors[mod_key][trace])
                except ValueError:
                    line += '{}'.format(hybrid_factors[mod_key][trace])
            output.write(line + '\n')

        output.write('#\n')

    print('======== Output Files: Metrics and Plots  ========')
    print('Model factors written to ' + file_path)


def print_other_metrics_csv(other_metrics, trace_list, trace_processes):
    """Prints the model factors table in a csv file."""
    global other_metrics_doc

    delimiter = ';'
    # File is stored in the trace directory
    # file_path = os.path.join(os.path.dirname(os.path.realpath(trace_list[0])), 'modelfactors.csv')
    # File is stored in the execution directory
    file_path = os.path.join(os.getcwd(), 'other_metrics.csv')

    with open(file_path, 'w') as output:
        line = 'Number of processes'
        for trace in trace_list:
            line += delimiter
            line += str(trace_processes[trace])
        output.write(line + '\n')

        for mod_key in other_metrics_doc:
            line = other_metrics_doc[mod_key].replace('  ', '', 2)
            for trace in trace_list:
                line += delimiter
                try:  # except NaN
                    line += '{0:.6f}'.format(other_metrics[mod_key][trace])
                except ValueError:
                    line += '{}'.format(other_metrics[mod_key][trace])
            output.write(line + '\n')

        output.write('#\n')

    print('')
    print('======== Output File: Other Metrics ========')
    print('Speedup, IPC, Frequency, I/O and Flushing written to ' + file_path)


def plots_efficiency_table_matplot(trace_list, trace_processes, trace_tasks, trace_threads, trace_mode, cmdl_args):
    # Plotting using python
    # For plotting using python, read the csv file

    file_path = os.path.join(os.getcwd(), 'efficiency_table_hybrid.csv')
    df = pd.read_csv(file_path)
    metrics = df['Metric'].tolist()

    ## remove complete nan columns and put to DF1
    df1 = df.dropna(axis='columns', how='all')

    traces_procs = list(df.keys())[1:]

    

    list_data = []

    for index, rows in df1.iterrows():
        list_temp = []             
        for value in list(rows)[1:]:
            if pd.isna(value):
                list_temp.append(np.nan)
            else:
                numeric_value = safe_float_for_plot(value)

                if pd.isna(numeric_value):
                    list_temp.append(np.nan)
                elif numeric_value == 0.0:
                    list_temp.append(np.nan)
                else:
                    list_temp.append(numeric_value)

        list_data.append(list_temp)

    list_np = np.array(list_data)

    idx = metrics
    cols = traces_procs

    df = pd.DataFrame(
        list_np,
        index=idx,
        columns=cols
    )

    _plot_efficiency_heatmap(df, 'efficiency_table_hybrid_matplot')


    # General Metrics plot

    file_path = os.path.join(os.getcwd(), 'efficiency_table_global.csv')
    df = pd.read_csv(file_path)

    metrics = df['Metric'].tolist()

    traces_procs = list(df.keys())[1:]

    list_data = []
    for index, rows in df.iterrows():
        list_temp = []
        for value in list(rows)[1:]:
            if pd.isna(value):
                list_temp.append(np.nan)
            else:
                numeric_value = safe_float_for_plot(value)

                if pd.isna(numeric_value):
                    list_temp.append(np.nan)
                elif numeric_value == 0.0:
                    list_temp.append(np.nan)
                else:
                    list_temp.append(numeric_value)

        # print(list_temp)
        list_data.append(list_temp)

    list_np = np.array(list_data)

    idx = metrics
    cols = traces_procs

    df = pd.DataFrame(
        list_np,
        index=idx,
        columns=cols
    )

    _plot_efficiency_heatmap(df, 'efficiency_table_global_matplot')

def plots_modelfactors_matplot(trace_list, trace_processes,trace_tasks, trace_threads, trace_mode, cmdl_args):
    # Plotting using python
    # For plotting using python, read the csv file
    count_mode = 0
    for trace in trace_list:
        if trace_mode[trace][0:len("Detailed+MPI+")] == "Detailed+MPI+":
            count_mode += 1

    file_path = os.path.join(os.getcwd(), 'modelfactors.csv')
    df = pd.read_csv(file_path, sep=';')

    traces_procs = list(df.keys())[1:]

    if count_mode != len(trace_list):
        df_hybrid = df[10:19].dropna(axis='columns', how='all')
    else:
        df_hybrid = df[8:17].dropna(axis='columns', how='all')

    traces_procs_hybrid = list(df_hybrid.keys())[1:]

    #put all data in a list of list
    list_data = []
    for index, rows in df.iterrows():
        list_temp = []
        for value in list(rows)[1:]:
            if value != 'Non-Avail' and value != 'Warning!' and not pd.isna(value):
                list_temp.append(float(value))
            else:
                list_temp.append(0.0)

        list_data.append(list_temp)

    #put hybrid data in a list of list
    list_data_hybrid = []
    for index, rows in df_hybrid.iterrows():
        list_temp = []
        for value in list(rows)[1:]:
            if value != 'Non-Avail' and value != 'Warning!' and not pd.isna(value):
                list_temp.append(float(value))
            else:
                list_temp.append(0.0)

        list_data_hybrid.append(list_temp)

    # To control same number of processes for the header on plots and table
    same_procs = True
    procs_trace_prev = trace_processes[trace_list[0]]
    tasks_trace_prev = trace_tasks[trace_list[0]]
    threads_trace_prev = trace_threads[trace_list[0]]
    for index, trace in enumerate(trace_list):
        tasks = trace_tasks[trace]
        threads = trace_threads[trace]
        if procs_trace_prev == trace_processes[trace] and tasks_trace_prev == tasks \
                and threads_trace_prev == threads:
            same_procs *= True
        else:
            same_procs *= False

    # Set limit for projection
    if cmdl_args.limit:
        limit = cmdl_args.limit
    else:
        limit = str(trace_processes[trace_list[len(trace_list)-1]])

    limit_min = trace_processes[trace_list[0]]

    # To xticks label
    label_xtics = []
    label_xtics_hybrid = []
    for index, trace in enumerate(trace_list):
        tasks = trace_tasks[trace]
        threads = trace_threads[trace]
        if int(limit) == int(limit_min) and same_procs:
            s_xtics = str(trace_processes[trace]) + '[' + str(index + 1) + ']'
        else:
            if trace_mode[trace][0:len("Detailed+MPI+")] == "Detailed+MPI+":
                s_xtics = str(trace_processes[trace]) + '(' + str(tasks) + 'x' + str(threads) + ')'
                label_xtics_hybrid.append(s_xtics+'[' + str(index + 1) + ']')
            else:
                s_xtics = str(trace_processes[trace])
        #if s_xtics in label_xtics:
        s_xtics += '[' + str(index + 1) + ']'
        label_xtics.append(s_xtics)

    ## Global Metrics
    plt.figure()

    if count_mode == len(trace_list):
        max_global = max([max(list_data[0]), max(list_data[1]), max(list_data[2]),
                      max(list_data[3]), max(list_data[4])])
        plt.plot(traces_procs, list_data[0], 'o-', color='black', label='Global Efficiency')
        plt.plot(traces_procs, list_data[1], 's--', color='magenta', label='Parallel Efficiency')
        plt.plot(traces_procs, list_data[2], '*:', color='red', label='Load Balance')
        plt.plot(traces_procs, list_data[3], 'x-.', color='green', label='Communication efficiency')
        plt.plot(traces_procs, list_data[4], 'v--', color='blue', label='Computation scalability')
    else:
        max_global = max([max(list_data[0]), max(list_data[1]), max(list_data[2]),
                          max(list_data[3]), max(list_data[6])])
        plt.plot(traces_procs, list_data[0], 'o-', color='black', label='Global Efficiency')
        plt.plot(traces_procs, list_data[1], 's--', color='magenta', label='Parallel Efficiency')
        plt.plot(traces_procs, list_data[2], '*:', color='red', label='Load Balance')
        plt.plot(traces_procs, list_data[3], 'x-.', color='green', label='Communication efficiency')
        plt.plot(traces_procs, list_data[6], 'v--', color='blue', label='Computation scalability')

    plt.xlabel("Number of Processes")
    plt.ylabel("Efficiency (%)")
    plt.xticks(tuple(traces_procs), tuple(label_xtics))
    # print(max_global)
    if float(max_global) < 100:
        max_global = 100

    plt.ylim(0, max_global+5)
    plt.legend()
    plt.savefig('modelfactors_global_matplot.png', bbox_inches='tight')

    ## Scale Metrics
    plt.figure()

    if count_mode == len(trace_list):
        max_scale = max([max(list_data[4]), max(list_data[5]), max(list_data[6]), max(list_data[7])])
        plt.plot(traces_procs, list_data[4], 'v-', color='blue', markerfacecolor='blue', label='Computation scalability')
        plt.plot(traces_procs, list_data[5], 'v--', color='skyblue', label='IPC scalability')
        plt.plot(traces_procs, list_data[6], 'v:', color='gray', label='Instruction scalability')
        plt.plot(traces_procs, list_data[7], 'v-.', color='darkviolet', label='Frequency scalability')
    else:
        max_scale = max([max(list_data[6]), max(list_data[7]), max(list_data[8]), max(list_data[9])])
        plt.plot(traces_procs, list_data[6], 'v-', color='blue', markerfacecolor='blue', label='Computation scalability')
        plt.plot(traces_procs, list_data[7], 'v--', color='skyblue', label='IPC scalability')
        plt.plot(traces_procs, list_data[8], 'v:', color='gray', label='Instruction scalability')
        plt.plot(traces_procs, list_data[9], 'v-.', color='darkviolet', label='Frequency scalability')

    plt.xlabel("Number of Processes")
    plt.ylabel("Efficiency (%)")
    plt.xticks(tuple(traces_procs), tuple(label_xtics))
    if float(max_scale) < 100:
        max_scale = 100

    plt.ylim(0, max_scale+5)
    plt.legend()
    plt.savefig('modelfactors_scale_matplot.png', bbox_inches='tight')

    ## Hybrid Metrics

    plt.figure()

    if count_mode == len(trace_list):
        max_hybrid = max([max(list_data[8]), max(list_data[9]), max(list_data[10]), max(list_data[11]),
                     max(list_data[14]), max(list_data[15]), max(list_data[16])])
        plt.plot(traces_procs, list_data[8], 's-', color='purple', label='Hybrid Parallel efficiency')
        plt.plot(traces_procs, list_data[9], 'o--', color='green', label='MPI Parallel efficiency')
        plt.plot(traces_procs, list_data[10], 'x-.', color='lime', label='MPI Load balance')
        plt.plot(traces_procs, list_data[11], '*:', color='lightseagreen', label='MPI Communication efficiency')
        plt.plot(traces_procs, list_data[14], 'h--', color='red', label='OpenMP Parallel efficiency')
        plt.plot(traces_procs, list_data[15], 'v-.', color='orange', label='OpenMP Load Balance')
        plt.plot(traces_procs, list_data[16], 'X:', color='salmon', label='OpenMP Communication efficiency')
    else:
        max_hybrid = max([max(list_data_hybrid[0]), max(list_data_hybrid[1]), max(list_data_hybrid[2]),
                          max(list_data_hybrid[3]), max(list_data_hybrid[4]), max(list_data_hybrid[5]),
                          max(list_data_hybrid[6])])
        plt.plot(traces_procs_hybrid, list_data_hybrid[0], 's-', color='purple', label='Hybrid Parallel efficiency')
        plt.plot(traces_procs_hybrid, list_data_hybrid[1], 'o--', color='green', label='MPI Parallel efficiency')
        plt.plot(traces_procs_hybrid, list_data_hybrid[2], 'x-.', color='lime', label='MPI Load balance')
        plt.plot(traces_procs_hybrid, list_data_hybrid[3], '*:', color='lightseagreen', label='MPI Communication efficiency')
        plt.plot(traces_procs_hybrid, list_data_hybrid[4], 'h--', color='red', label='OpenMP Parallel efficiency')
        plt.plot(traces_procs_hybrid, list_data_hybrid[5], 'v-.', color='orange', label='OpenMP Load Balance')
        plt.plot(traces_procs_hybrid, list_data_hybrid[6], 'X:', color='salmon', label='OpenMP Communication efficiency')

    plt.xlabel("Number of Processes")
    plt.ylabel("Efficiency (%)")
    plt.xticks(tuple(traces_procs_hybrid), tuple(label_xtics_hybrid))
    if float(max_hybrid) < 100:
        max_hybrid = 100

    plt.ylim(0, max_hybrid+5)
    plt.legend()
    plt.savefig('modelfactors_hybrid_matplot.png', bbox_inches='tight')

    ## MPI Metrics
    plt.figure()

    if count_mode == len(trace_list):
        if max(list_data[12]) != 'NaN' and max(list_data[13]) != 'NaN':
            max_mpi = max([max(list_data[9]), max(list_data[10]), max(list_data[11]),
                       max(list_data[12]), max(list_data[13])])
            plt.plot(traces_procs, list_data[9], 's-', color='green', label='MPI Parallel efficiency')
            plt.plot(traces_procs, list_data[10], 'v:', color='lime', label='MPI Load balance')
            plt.plot(traces_procs, list_data[11], 'o-.', color='lightseagreen', label='MPI Communication efficiency')
            plt.plot(traces_procs, list_data[12], linestyle=(0, (3, 10, 1, 10)), marker='s', color='gold',
                 label='Serialization efficiency')
            plt.plot(traces_procs, list_data[13], linestyle=(0, (3, 5, 1, 5)), marker='x', color='tomato',
                     label='Transfer efficiency')
        elif max(list_data[12]) == 'NaN' and max(list_data[13]) == 'NaN':
            max_mpi = max([max(list_data[9]), max(list_data[10]), max(list_data[11])])
            plt.plot(traces_procs, list_data[9], 's-', color='green', label='MPI Parallel efficiency')
            plt.plot(traces_procs, list_data[10], 'v:', color='lime', label='MPI Load balance')
            plt.plot(traces_procs, list_data[11], 'o-.', color='lightseagreen', label='MPI Communication efficiency')
        elif max(list_data[12]) != 'NaN' and max(list_data[13]) == 'NaN':
            max_mpi = max([max(list_data[9]), max(list_data[10]), max(list_data[11]),
                       max(list_data[12])])
            plt.plot(traces_procs, list_data[9], 's-', color='green', label='MPI Parallel efficiency')
            plt.plot(traces_procs, list_data[10], 'v:', color='lime', label='MPI Load balance')
            plt.plot(traces_procs, list_data[11], 'o-.', color='lightseagreen', label='MPI Communication efficiency')
            plt.plot(traces_procs, list_data[12], linestyle=(0, (3, 10, 1, 10)), marker='s', color='gold',
                     label='Serialization efficiency')
        else:
            max_mpi = max([max(list_data[9]), max(list_data[10]), max(list_data[11]),max(list_data[13])])
            plt.plot(traces_procs, list_data[9], 's-', color='green', label='MPI Parallel efficiency')
            plt.plot(traces_procs, list_data[10], 'v:', color='lime', label='MPI Load balance')
            plt.plot(traces_procs, list_data[11], 'o-.', color='lightseagreen', label='MPI Communication efficiency')
            plt.plot(traces_procs, list_data[13], linestyle=(0, (3, 5, 1, 5)), marker='x', color='tomato',
                     label='Transfer efficiency')
    else:
        if max(list_data_hybrid[4]) != 'NaN' and max(list_data_hybrid[5]) != 'NaN':
            max_mpi = max([max(list_data_hybrid[1]), max(list_data_hybrid[2]), max(list_data_hybrid[3]),
                       max(list_data_hybrid[4]), max(list_data_hybrid[5])])
            plt.plot(traces_procs_hybrid, list_data_hybrid[1], 's-', color='green', label='MPI Parallel efficiency')
            plt.plot(traces_procs_hybrid, list_data_hybrid[2], 'v:', color='lime', label='MPI Load balance')
            plt.plot(traces_procs_hybrid, list_data_hybrid[3], 'o-.', color='lightseagreen', label='MPI Communication efficiency')
            plt.plot(traces_procs_hybrid, list_data_hybrid[4], linestyle=(0, (3, 10, 1, 10)), marker='s', color='gold',
                 label='Serialization efficiency')
            plt.plot(traces_procs_hybrid, list_data_hybrid[5], linestyle=(0, (3, 5, 1, 5)), marker='x', color='tomato',
                     label='Transfer efficiency')
        elif max(list_data_hybrid[4]) == 'NaN' and max(list_data_hybrid[5]) == 'NaN':
            max_mpi = max([max(list_data_hybrid[1]), max(list_data_hybrid[2]), max(list_data_hybrid[3])])
            plt.plot(traces_procs_hybrid, list_data_hybrid[1], 's-', color='green', label='MPI Parallel efficiency')
            plt.plot(traces_procs_hybrid, list_data_hybrid[2], 'v:', color='lime', label='MPI Load balance')
            plt.plot(traces_procs_hybrid, list_data_hybrid[3], 'o-.', color='lightseagreen', label='MPI Communication efficiency')
        elif max(list_data_hybrid[4]) != 'NaN' and max(list_data_hybrid[5]) == 'NaN':
            max_mpi = max([max(list_data_hybrid[1]), max(list_data_hybrid[2]), max(list_data_hybrid[3]),
                       max(list_data_hybrid[4])])
            plt.plot(traces_procs_hybrid, list_data_hybrid[1], 's-', color='green', label='MPI Parallel efficiency')
            plt.plot(traces_procs_hybrid, list_data_hybrid[2], 'v:', color='lime', label='MPI Load balance')
            plt.plot(traces_procs_hybrid, list_data_hybrid[3], 'o-.', color='lightseagreen', label='MPI Communication efficiency')
            plt.plot(traces_procs_hybrid, list_data_hybrid[4], linestyle=(0, (3, 10, 1, 10)), marker='s', color='gold',
                     label='Serialization efficiency')
        else:
            max_mpi = max([max(list_data_hybrid[1]), max(list_data_hybrid[2]), max(list_data_hybrid[3]),
                           max(list_data_hybrid[5])])
            plt.plot(traces_procs_hybrid, list_data_hybrid[1], 's-', color='green', label='MPI Parallel efficiency')
            plt.plot(traces_procs_hybrid, list_data_hybrid[2], 'v:', color='lime', label='MPI Load balance')
            plt.plot(traces_procs_hybrid, list_data_hybrid[3], 'o-.', color='lightseagreen', label='MPI Communication efficiency')
            plt.plot(traces_procs_hybrid, list_data_hybrid[5], linestyle=(0, (3, 5, 1, 5)), marker='x', color='tomato',
                     label='Transfer efficiency')

    plt.xlabel("Number of Processes")
    plt.ylabel("Efficiency (%)")
    plt.xticks(tuple(traces_procs_hybrid), tuple(label_xtics_hybrid))
    if float(max_mpi) < 100:
        max_mpi = 100

    plt.ylim(0, max_mpi+5)
    plt.legend()
    plt.savefig('modelfactors_mpi_matplot.png', bbox_inches='tight')


def plots_speedup_matplot(trace_list, trace_processes, trace_tasks, trace_threads, trace_mode, cmdl_args):
    # Plotting using python
    # For plotting using python, read the csv file
    file_path = os.path.join(os.getcwd(), 'other_metrics.csv')
    df = pd.read_csv(file_path, sep=';')

    traces_procs = list(df.keys())[1:]

    list_data = []
    for index, rows in df.iterrows():
        list_temp = []
        for value in list(rows)[1:]:
            if value != 'Non-Avail':
                list_temp.append(float(value))
            elif value == 'Non-Avail':
                list_temp.append('NaN')
        # print(list_temp)
        list_data.append(list_temp)

    # To control same number of processes for the header on plots and table
    same_procs = True
    procs_trace_prev = trace_processes[trace_list[0]]
    tasks_trace_prev = trace_tasks[trace_list[0]]
    threads_trace_prev = trace_threads[trace_list[0]]
    for index, trace in enumerate(trace_list):
        tasks = trace_tasks[trace]
        threads = trace_threads[trace]
        if procs_trace_prev == trace_processes[trace] and tasks_trace_prev == tasks \
                and threads_trace_prev == threads:
            same_procs *= True
        else:
            same_procs *= False

    # Set limit for projection
    if cmdl_args.limit:
        limit = cmdl_args.limit
    else:
        limit = str(trace_processes[trace_list[len(trace_list) - 1]])

    limit_min = trace_processes[trace_list[0]]

    # proc_ratio to ideal speedup
    proc_ratio = []
    for index, trace in enumerate(trace_list):
        proc_ratio.append(trace_processes[trace]/trace_processes[trace_list[0]])
    # print(proc_ratio)

    # To xticks label
    label_xtics = []
    for index, trace in enumerate(trace_list):
        tasks = trace_tasks[trace]
        threads = trace_threads[trace]
        if int(limit) == int(limit_min) and same_procs:
            s_xtics = str(trace_processes[trace]) + '[' + str(index + 1) + ']'
        elif int(limit) == int(limit_min) and not same_procs:
            if trace_mode[trace][0:len("Detailed+MPI+")] == "Detailed+MPI+":
                s_xtics = str(trace_processes[trace]) + '(' + str(tasks) + 'x' \
                          + str(threads) + ')'
        else:
            s_xtics = str(trace_processes[trace])
        s_xtics += '[' + str(index + 1) + ']'
        label_xtics.append(s_xtics)

    int_traces_procs = []
    prev_procs = int(float(traces_procs[0]))
    int_traces_procs.append(int(float(traces_procs[0])))
    count_rep = 0
    for procs in traces_procs[1:]:
        if prev_procs == int(float(procs)):
            count_rep += 1
            int_traces_procs.append(int(float(procs)) + (6*count_rep))
            prev_procs = int(float(procs))
        else:
            int_traces_procs.append(int(float(procs)))
            prev_procs = int(float(procs))
            count_rep = 0

    ### Plot: Global Metrics
    plt.figure()
    for x, y in zip(int_traces_procs, list_data[2]):
        label = "{:.2f}".format(y)
        plt.annotate(label, (x, y), textcoords="offset points", xytext=(0, 10), ha='center')

    plt.plot(int_traces_procs, list_data[2], 'o-', color='blue', label='measured')
    plt.plot(int_traces_procs, proc_ratio, 'o-', color='black', label='ideal')
    plt.xlabel("Number of Processes")
    plt.ylabel("SpeedUp")
    plt.xticks(tuple(int_traces_procs), tuple(label_xtics))
    #plt.yscale('log')
    plt.legend()
    #plt.xlim(0, )
    plt.ylim(0, )
    plt.savefig('speedup_matplot.png', bbox_inches='tight')

    ### Plot: Efficiency
    # print(list_data)
    plt.figure()
    for x, y in zip(int_traces_procs, list_data[1]):
        label = "{:.2f}".format(y)
        plt.annotate(label, (x, y), textcoords="offset points", xytext=(0, 10), ha='center')

    plt.plot(int_traces_procs, list_data[1], 'o-', color='blue', label='measured')
    plt.axhline(y=1, color='black', linestyle='-', label='ideal')
    plt.xlabel("Number of Processes")
    plt.ylabel("Efficiency")
    plt.xticks(tuple(int_traces_procs), tuple(label_xtics))
    # plt.yscale('log')
    max_y = max(list_data[1])
    if max_y < 1.1:
        max_y = 1.0
    #plt.xlim(0, )
    plt.ylim(0,max_y+0.1)
    plt.legend()
    plt.savefig('efficiency_matplot.png', bbox_inches='tight')

def print_talp_metrics_csv(
        device_factors,
        host_factors,
        trace_list,
        trace_processes,
        trace_tasks,
        trace_threads,
        trace_mode,
        raw_data):
    """Prints the model factors table in a csv file."""
    global mod_device_factors_doc, mod_host_factors_doc

    delimiter = ','
    file_path = os.path.join(os.getcwd(), 'talp_metrics.csv')

    configuration_labels = _build_hybrid_configuration_labels(
        trace_list,
        trace_processes,
        trace_tasks,
        trace_threads,
        trace_mode,
        raw_data,
    )


    with open(file_path, 'w') as output:
        line = '"Metric"'

        for label in configuration_labels:
            line += delimiter
            line += label

        output.write(line + '\n')

        # HOST metrics
        for mod_key in mod_host_factors_doc:
            line = "\"" + mod_host_factors_doc[mod_key] + "\""
            for trace in trace_list:
                line += delimiter
                try:
                    if host_factors[mod_key][trace] == "Non-Avail":
                        line += 'Non-Avail'
                    else:
                        line += '{0:.6f}'.format(host_factors[mod_key][trace])

                except ValueError:
                    line += '{}'.format(host_factors[mod_key][trace])
            output.write(line + '\n')


        # DEVICE metrics
        for mod_key in mod_device_factors_doc:
            line = "\"" + mod_device_factors_doc[mod_key] + "\""
            for trace in trace_list:
                line += delimiter
                try:
                    if device_factors[mod_key][trace] == "Non-Avail":
                        line += 'Non-Avail'
                    else:
                        line += '{0:.6f}'.format(device_factors[mod_key][trace])
                except ValueError:
                    line += '{}'.format(device_factors[mod_key][trace])
            output.write(line + '\n')

    print('')
    print('======== Output File: Device Metrics ========')
    print('Device Metrics written to ' + file_path)


def plots_talp_efficiency_table_matplot(
        trace_list,
        trace_processes,
        trace_tasks,
        trace_threads,
        trace_mode,
        raw_data,
        cmdl_args):

    global mod_host_factors_doc

    file_path = os.path.join(
        os.getcwd(),
        'talp_metrics.csv'
    )

    df = pd.read_csv(file_path)

    metrics = df['Metric'].tolist()

    # Remove completely empty columns.
    df1 = df.dropna(
        axis='columns',
        how='all'
    )

    # Canonical configuration labels are already stored
    # in the CSV column names.
    traces_procs = list(df.keys())[1:]

    list_data = []

    for index, rows in df1.iterrows():
        list_temp = []

        for value in list(rows)[1:]:
            if pd.isna(value) or value == 0.0:
                list_temp.append(np.nan)
            else:
                list_temp.append(
                    safe_float_for_plot(value)
                )

        list_data.append(list_temp)

    list_np = np.array(list_data)

    idx = metrics
    cols = traces_procs

    df_plot = pd.DataFrame(
        list_np,
        index=idx,
        columns=cols
    )

    host_rows = len(mod_host_factors_doc)

    _plot_efficiency_heatmap(
        df_plot,
        'efficiency_table_talp_matplot',
        separator_row=host_rows
    )


def print_omp_talp_metrics_csv(omp_talp_factors, trace_list, trace_processes,
                               trace_tasks, trace_threads, trace_mode):
    """Print isolated OpenMP TALP-style metrics for validation."""
    global mod_omp_factors_doc

    delimiter = ';'
    file_path = os.path.join(os.getcwd(), 'omp_talp_metrics.csv')

    with open(file_path, 'w') as output:
        line = '"Number of processes"'
        for trace in trace_list:
            if trace_mode[trace] == "Detailed+MPI+OpenMP":
                label = "{}({}x{})".format(
                    trace_processes[trace],
                    trace_tasks[trace],
                    trace_threads[trace],
                )
            else:
                label = str(trace_processes[trace])

            line += delimiter + label

        output.write(line + '\n')

        for mod_key in mod_omp_factors_doc:
            line = '"' + mod_omp_factors_doc[mod_key] + '"'

            for trace in trace_list:
                line += delimiter
                value = omp_talp_factors[mod_key][trace]

                try:
                    line += '{0:.6f}'.format(value)
                except (ValueError, TypeError):
                    line += '{}'.format(value)

            output.write(line + '\n')

        output.write('#\n')

    print('')
    print('======== Output File: Isolated OpenMP Metrics ========')
    print('OpenMP TALP-style metrics written to ' + file_path)