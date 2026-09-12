#!/usr/bin/env python3

"""Functions to compute the model metrics."""

from __future__ import print_function, division
import sys

from rawdata import *
from collections import OrderedDict
from scaling import get_scaling_info

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


# ----------------------------------------------------------------------
# Experimental metric extensions
# ----------------------------------------------------------------------

# I/O-aware scalability metrics are currently experimental and are not part
# of the documented BasicAnalysis 1.0 metric model.
#
# Raw I/O information is still collected and may be reported for diagnostic
# purposes, but it does not modify the standard efficiency metrics.
ENABLE_IO_AWARE_METRICS = False


# Contains all model factor entries with a printable name.
# This is used to generate and print all model factors, so, if an entry is added,
# it should be added here, too.

other_metrics_doc = OrderedDict([('elapsed_time', 'Elapsed time (sec)'),
                               ('efficiency', 'Efficiency'),
                               ('speedup', 'Speedup'),
                               ('ipc', 'Average IPC'),
                               ('freq', 'Average frequency (GHz)'),
                               ('flushing', 'Flushing (%)'),
                                # Complementary I/O efficiency metrics.
                                ('io_eff', 'I/O Efficiency (%)'),
                                ('mpi_io_eff', 'MPI I/O Efficiency (%)'),
                                ('mpi_io_load_balance', 'MPI I/O Load Balance (%)'),
                                ('posix_io_eff', 'POSIX I/O Efficiency (%)'),
                                ('posix_io_load_balance', 'POSIX I/O Load Balance (%)'),
                               ])

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


mod_omp_factors_doc = OrderedDict([('omp_talp_parallel_eff','-- OpenMP Parallel Efficiency'),
    ('omp_talp_serial_eff', '   -- OpenMP Serial Efficiency'),
    ('omp_talp_load_balance', '   -- OpenMP Load Balance'),
    ('omp_talp_scheduling_eff', '   -- OpenMP Scheduling Efficiency'),])


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


def create_other_metrics(trace_list):
    """Create general and complementary metric dictionaries."""
    global other_metrics_doc

    other_metrics = {}

    for key in other_metrics_doc:
        trace_dict = {}

        for trace_name in trace_list:
            trace_dict[trace_name] = 0.0

        other_metrics[key] = trace_dict

    # Internal I/O activity percentages.
    #
    # These values are used for diagnostics and for deriving the
    # efficiency-oriented I/O metrics, but are not exposed as
    # public BasicAnalysis metrics.
    for key in ('io_mpiio', 'io_posix'):
        other_metrics[key] = {
            trace_name: 0.0
            for trace_name in trace_list
        }

    return other_metrics


def create_omp_talp_factors(trace_list):
    """Create the isolated OpenMP metric dictionary.

    The dictionary has the format:
        omp_talp_factors[factor_key][trace]
    """
    global mod_omp_factors_doc

    omp_talp_factors = {}

    for key in mod_omp_factors_doc:
        trace_dict = {}

        for trace_name in trace_list:
            trace_dict[trace_name] = 0.0

        omp_talp_factors[key] = trace_dict

    return omp_talp_factors


def _format_heatmap_metric_labels(labels, output_name=None):
    """
    Convert the textual hierarchy used by stdout (-- / ==)
    into clean metric names plus indentation levels for plots.
    """

    formatted_labels = []
    indent_levels = []

    for label in labels:
        raw_label = str(label)

        leading_spaces = len(raw_label) - len(raw_label.lstrip())
        text = raw_label.strip()

        has_marker = False

        if text.startswith('=='):
            text = text[2:].strip()
            has_marker = True
        elif text.startswith('--'):
            text = text[2:].strip()
            has_marker = True

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
    other_metrics = create_other_metrics(trace_list)
    mod_factors_scale_plus_io = create_mod_factors_scale_io(trace_list)
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

        # Flushing measurements
        try:  # except NaN
            other_metrics['flushing'][trace] = raw_data['flushing_tot'][trace] \
                                               / (raw_data['runtime'][trace] * trace_processes[trace]) * 100.0
        except:
            other_metrics['flushing'][trace] = 0.0

        # I/O measurements
        # --------------------------------------------------
        # File I/O metrics
        # --------------------------------------------------

        try:
            runtime = float(raw_data['runtime'][trace])
            parallel_units = float(trace_processes[trace])

            posix_io_tot = float(raw_data['io_tot'][trace])
            mpi_io_tot = float(raw_data['mpiio_tot'][trace])

            has_posix_io = posix_io_tot > 0.0
            has_mpi_io = mpi_io_tot > 0.0

        except (TypeError, ValueError):
            runtime = 0.0
            parallel_units = 0.0
            posix_io_tot = 0.0
            mpi_io_tot = 0.0
            has_posix_io = False
            has_mpi_io = False

        # --------------------------------------------------
        # Raw I/O activity percentages
        #
        # Kept internally for diagnostics and warning thresholds.
        # They are not part of the I/O efficiency metric set.
        # --------------------------------------------------

        if runtime > 0.0 and parallel_units > 0.0:

            other_metrics['io_mpiio'][trace] = (
                mpi_io_tot
                / (runtime * parallel_units)
                * 100.0
            )

            other_metrics['io_posix'][trace] = (
                posix_io_tot
                / (runtime * parallel_units)
                * 100.0
            )

        else:
            other_metrics['io_mpiio'][trace] = 0.0
            other_metrics['io_posix'][trace] = 0.0

        # --------------------------------------------------
        # MPI I/O Efficiency and Load Balance
        # --------------------------------------------------

        if has_mpi_io and runtime > 0.0 and parallel_units > 0.0:

            other_metrics['mpi_io_eff'][trace] = (
                100.0
                - other_metrics['io_mpiio'][trace]
            )

            try:
                mpi_io_avg = float(raw_data['mpiio_avg'][trace])
                mpi_io_max = float(raw_data['mpiio_max'][trace])

                if mpi_io_max > 0.0:
                    other_metrics['mpi_io_load_balance'][trace] = (
                        mpi_io_avg
                        / mpi_io_max
                        * 100.0
                    )
                else:
                    other_metrics['mpi_io_load_balance'][trace] = 'Non-Avail'

            except (TypeError, ValueError, ZeroDivisionError):
                other_metrics['mpi_io_load_balance'][trace] = 'NaN'

        else:
            other_metrics['mpi_io_eff'][trace] = 'Non-Avail'
            other_metrics['mpi_io_load_balance'][trace] = 'Non-Avail'

        # --------------------------------------------------
        # POSIX / ANSI C I/O Efficiency and Load Balance
        # --------------------------------------------------

        if has_posix_io and runtime > 0.0 and parallel_units > 0.0:

            other_metrics['posix_io_eff'][trace] = (
                100.0
                - other_metrics['io_posix'][trace]
            )

            try:
                posix_io_avg = float(raw_data['io_avg'][trace])
                posix_io_max = float(raw_data['io_max'][trace])

                if posix_io_max > 0.0:
                    other_metrics['posix_io_load_balance'][trace] = (
                        posix_io_avg
                        / posix_io_max
                        * 100.0
                    )
                else:
                    other_metrics['posix_io_load_balance'][trace] = 'Non-Avail'

            except (TypeError, ValueError, ZeroDivisionError):
                other_metrics['posix_io_load_balance'][trace] = 'NaN'

        else:
            other_metrics['posix_io_eff'][trace] = 'Non-Avail'
            other_metrics['posix_io_load_balance'][trace] = 'Non-Avail'

        # --------------------------------------------------
        # Overall I/O Efficiency
        #
        # Tracer flushing is intentionally excluded: it is instrumentation
        # overhead, not application File I/O.
        # --------------------------------------------------

        if has_posix_io or has_mpi_io:

            try:
                useful_tot = float(raw_data['useful_tot'][trace])

                io_total = (
                    posix_io_tot
                    + mpi_io_tot
                )

                denominator = (
                    useful_tot
                    + io_total
                )

                if denominator > 0.0:
                    other_metrics['io_eff'][trace] = (
                        useful_tot
                        / denominator
                        * 100.0
                    )
                else:
                    other_metrics['io_eff'][trace] = 'Non-Avail'

            except (TypeError, ValueError, ZeroDivisionError):
                other_metrics['io_eff'][trace] = 'NaN'

        else:
            other_metrics['io_eff'][trace] = 'Non-Avail'

        # Basic efficiency factors
        try:  # except NaN
            if trace_mode[trace] == 'Burst+MPI':
                mod_factors['load_balance'][trace] = float(raw_data['burst_useful_avg'][trace]) \
                                                     / float(raw_data['burst_useful_max'][trace]) * 100.0
            else:
                #if other_metrics['io_posix'][trace] > 0.0 or other_metrics['flushing'][trace] > 5.0:
                #    mod_factors['load_balance'][trace] = raw_data['useful_plus_io_avg'][trace] \
                #                                     / raw_data['useful_plus_io_max'][trace] * 100.0
                #else:
                mod_factors['load_balance'][trace] = raw_data['useful_avg'][trace] \
                                                 / raw_data['useful_max'][trace] * 100.0
        except:
            mod_factors['load_balance'][trace] = 'NaN'

        try:  # except NaN
            if trace_mode[trace] == 'Burst+MPI':
                mod_factors['comm_eff'][trace] = float(raw_data['burst_useful_max'][trace]) \
                / float(raw_data['runtime'][trace]) * 100.0
            else:
                #if other_metrics['io_posix'][trace] > 0.0 or other_metrics['flushing'][trace] > 5.0:
                #    mod_factors['comm_eff'][trace] = raw_data['useful_plus_io_max'][trace] \
                #                                 / raw_data['runtime'][trace] * 100.0
                #else:
                mod_factors['comm_eff'][trace] = raw_data['useful_max'][trace] / raw_data['runtime'][trace] * 100.0
        except:
            mod_factors['comm_eff'][trace] = 'NaN'

        
        if math.isnan(float(raw_data['outsidempi_avg'][trace])) or math.isnan(float(raw_data['outsidempi_max'][trace])):
            outmpi_measures = False
        else:
            outmpi_measures = True

        try:  # except NaN
            if (not outmpi_measures) or cmdl_args.skip_simulation:
                mod_factors['serial_eff'][trace] = 'Non-Avail'
            else: 
                mod_factors['serial_eff'][trace] = float(raw_data['useful_dim'][trace]) \
                                               / float(raw_data['runtime_dim'][trace]) * 100.0
                
                if round(mod_factors['serial_eff'][trace]) > 100:
                    mod_factors['serial_eff'][trace] = 'Warning!'
        except:
            mod_factors['serial_eff'][trace] = 'NaN'

        try:  # except NaN
            if (not outmpi_measures) or cmdl_args.skip_simulation:
                mod_factors['transfer_eff'][trace] = 'Non-Avail'
            else:
                if mod_factors['serial_eff'][trace] != 'Warning!':
                    mod_factors['transfer_eff'][trace] = mod_factors['comm_eff'][trace] \
                                                     / mod_factors['serial_eff'][trace] * 100.0
                else:
                    mod_factors['transfer_eff'][trace] = float(raw_data['runtime_dim'][trace]) \
                                                     / float(raw_data['runtime'][trace]) * 100.0
                
                if round(mod_factors['transfer_eff'][trace]) > 100:
                    print("Transfer Warning: ", mod_factors['transfer_eff'][trace])
                    mod_factors['transfer_eff'][trace] = 'Warning!'
        except:
            mod_factors['transfer_eff'][trace] = 'NaN'

        # Parallel Efficiency
        try:  # except NaN
            if trace_mode[trace] == 'Burst+MPI':
                mod_factors['parallel_eff'][trace] = float(raw_data['burst_useful_avg'][trace]) \
                                                     / float(raw_data['runtime'][trace]) * 100.0
            else:
                #if other_metrics['io_posix'][trace] > 0.0 or other_metrics['flushing'][trace] > 5.0:
                #    mod_factors['parallel_eff'][trace] = float(raw_data['useful_plus_io_avg'][trace]) \
                #                                     / float(raw_data['runtime'][trace]) * 100.0
                #else:
                mod_factors['parallel_eff'][trace] = mod_factors['load_balance'][trace] \
                                                     * mod_factors['comm_eff'][trace] / 100.0
        except:
            mod_factors['parallel_eff'][trace] = 'NaN'


        # Isolated OpenMP metrics:
        # TALP-style timing decomposition for OpenMP-only traces.
        try:
            if trace_mode[trace] == 'Detailed+OpenMP':
                t_no_omp = float(raw_data['time_no_omp'][trace])

                t_serial = float(raw_data['time_omp_serial'][trace])

                t_imbal = float(raw_data['time_omp_imbalance'][trace])

                t_sched = float(raw_data['time_omp_schedule'][trace])

                t_after_serial = (t_no_omp + t_serial)

                t_after_load_balance = (t_after_serial + t_imbal)

                t_total = (t_after_load_balance + t_sched)

                if t_total > 0.0:
                    omp_talp_factors['omp_talp_parallel_eff'][trace] = (t_no_omp / t_total * 100.0)
                else:
                    omp_talp_factors['omp_talp_parallel_eff'][trace] = 'NaN'

                if t_after_serial > 0.0:
                    omp_talp_factors['omp_talp_serial_eff'][trace] = (t_no_omp / t_after_serial * 100.0)
                else:
                    omp_talp_factors['omp_talp_serial_eff'][trace] = 'NaN'

                if t_after_load_balance > 0.0:
                    omp_talp_factors['omp_talp_load_balance'][trace] = (t_after_serial / t_after_load_balance * 100.0)
                else:
                    omp_talp_factors['omp_talp_load_balance'][trace] = 'NaN'

                if t_total > 0.0:
                    omp_talp_factors['omp_talp_scheduling_eff'][trace] = (t_after_load_balance / t_total * 100.0)
                else:
                    omp_talp_factors['omp_talp_scheduling_eff'][trace] = 'NaN'

            else:
                omp_talp_factors['omp_talp_parallel_eff'][trace] = 'Non-Avail'
                omp_talp_factors['omp_talp_serial_eff'][trace] = 'Non-Avail'
                omp_talp_factors['omp_talp_load_balance'][trace] = 'Non-Avail'
                omp_talp_factors['omp_talp_scheduling_eff'][trace] = 'Non-Avail'

        except (TypeError, ValueError, ZeroDivisionError):
            omp_talp_factors['omp_talp_parallel_eff'][trace] = 'NaN'
            omp_talp_factors['omp_talp_serial_eff'][trace] = 'NaN'
            omp_talp_factors['omp_talp_load_balance'][trace] = 'NaN'
            omp_talp_factors['omp_talp_scheduling_eff'][trace] = 'NaN'

        # Computation Scale only useful computation
        try:  # except NaN
            if len(trace_list) > 1:
                if trace_mode[trace] == 'Burst+MPI':
                    if scaling == 'strong':
                        mod_factors['comp_scale'][trace] = raw_data['burst_useful_tot'][trace_list[0]] \
                                                   / raw_data['burst_useful_tot'][trace] * 100.0
                    else:
                        mod_factors['comp_scale'][trace] = raw_data['burst_useful_tot'][trace_list[0]] \
                                                   / raw_data['burst_useful_tot'][trace] \
                                                   * proc_ratio * 100.0
                else:
                    if scaling == 'strong':
                        mod_factors['comp_scale'][trace] = raw_data['useful_tot'][trace_list[0]] \
                                                   / raw_data['useful_tot'][trace] * 100.0
                    else:
                        mod_factors['comp_scale'][trace] = raw_data['useful_tot'][trace_list[0]] \
                                                   / raw_data['useful_tot'][trace] \
                                                   * proc_ratio * 100.0
            else:
                mod_factors['comp_scale'][trace] = 'Non-Avail'
        except:
            mod_factors['comp_scale'][trace] = 'NaN'

        # Experimental Computation Scalability including serial I/O
        try:
            if not ENABLE_IO_AWARE_METRICS:
                mod_factors_scale_plus_io['comp_scale'][trace] = 'Non-Avail'

            elif len(trace_list) > 1:
                if (
                    other_metrics['io_posix'][trace] > 0.0
                    or other_metrics['flushing'][trace] > 0.0
                ):
                    io_serial_0 = (
                        raw_data['io_tot'][trace_list[0]]
                        + raw_data['flushing_tot'][trace_list[0]]
                    )

                    io_serial_n = (
                        raw_data['io_tot'][trace]
                        + raw_data['flushing_tot'][trace]
                    )

                    if scaling == 'strong':
                        mod_factors_scale_plus_io['comp_scale'][trace] = (
                            raw_data['useful_tot'][trace_list[0]]
                            + io_serial_0
                        ) / (
                            raw_data['useful_tot'][trace]
                            + io_serial_n
                        ) * 100.0

                    else:
                        mod_factors_scale_plus_io['comp_scale'][trace] = (
                            raw_data['useful_tot'][trace_list[0]]
                            + io_serial_0
                        ) / (
                            raw_data['useful_tot'][trace]
                            + io_serial_n
                        ) * proc_ratio * 100.0

                else:
                    mod_factors_scale_plus_io['comp_scale'][trace] = (
                        mod_factors['comp_scale'][trace]
                    )

            else:
                mod_factors_scale_plus_io['comp_scale'][trace] = 'Non-Avail'

        except:
            mod_factors_scale_plus_io['comp_scale'][trace] = 'NaN'

        try:  # except NaN
            if len(trace_list) > 1:
                mod_factors['global_eff'][trace] = mod_factors['parallel_eff'][trace] \
                                               * mod_factors['comp_scale'][trace] / 100.0
            else:
                mod_factors['global_eff'][trace] = mod_factors['parallel_eff'][trace] \
                                                   * 100.0 / 100.0
        except:
            mod_factors['global_eff'][trace] = 'NaN'

        # Basic scalability factors - Computational
        # IPC Scalability
        try:  # except NaN
            other_metrics['ipc'][trace] = float(raw_data['useful_ins'][trace]) \
                                        / float(raw_data['useful_cyc'][trace])
        except:
            if (raw_data['useful_ins'][trace] == 0) or (raw_data['useful_cyc'][trace] == 0):
                other_metrics['ipc'][trace] = 'Non-Avail'
            else:
                other_metrics['ipc'][trace] = 'NaN'
        try:  # except NaN
            if len(trace_list) > 1:
                if trace_mode[trace][:5] != 'Burst' and trace_mode[trace] != 'Sampling':
                    mod_factors['ipc_scale'][trace] = other_metrics['ipc'][trace] \
                                              / other_metrics['ipc'][trace_list[0]] * 100.0
                else:
                    mod_factors['ipc_scale'][trace] = 'Non-Avail'
            else:
                mod_factors['ipc_scale'][trace] = 'Non-Avail'
        except:
            mod_factors['ipc_scale'][trace] = 'NaN'

        # IPC scale + Serial I/O
        try:  # except NaN
            if not ENABLE_IO_AWARE_METRICS:
                mod_factors_scale_plus_io['ipc_scale'][trace] = 'Non-Avail'            
            elif len(trace_list) > 1:
                if other_metrics['io_posix'][trace] > 0.0 or other_metrics['flushing'][trace] > 0.0:
                    ipc_serial_io_0 = (raw_data['useful_ins'][trace_list[0]] + raw_data['io_ins'][trace_list[0]]
                               + raw_data['flushing_ins'][trace_list[0]]) \
                              / (raw_data['useful_cyc'][trace_list[0]] + raw_data['io_cyc'][trace_list[0]]
                                 + raw_data['flushing_cyc'][trace_list[0]])

                    ipc_serial_io_n = (raw_data['useful_ins'][trace] + raw_data['io_ins'][trace]
                               + raw_data['flushing_ins'][trace]) \
                              / (raw_data['useful_cyc'][trace] + raw_data['io_cyc'][trace]
                                 + raw_data['flushing_cyc'][trace])
                    mod_factors_scale_plus_io['ipc_scale'][trace] = ipc_serial_io_n / ipc_serial_io_0 * 100.0
                else:
                    mod_factors_scale_plus_io['ipc_scale'][trace] = 0.0
            else:
                mod_factors_scale_plus_io['ipc_scale'][trace] = 'Non-Avail'
        except:
            mod_factors_scale_plus_io['ipc_scale'][trace] = mod_factors['ipc_scale'][trace]

        # Average Frequency
        try:
            if raw_data['frequency'][trace] == 'Non-Avail':
                other_metrics['freq'][trace] = 'Non-Avail'
            else:
                other_metrics['freq'][trace] = (
                    float(raw_data['frequency'][trace]) / 1000.0
                )

        except (TypeError, ValueError):
            other_metrics['freq'][trace] = 'NaN'

        # Frequency Scalability
        try:
            if len(trace_list) > 1:

                reference = trace_list[0]

                if (
                    raw_data['useful_cyc'][trace] == 'Non-Avail'
                    or raw_data['useful_cyc'][reference] == 'Non-Avail'
                    or raw_data['useful_not_0_tot'][trace] == 'NaN'
                    or raw_data['useful_not_0_tot'][reference] == 'NaN'
                    or float(raw_data['useful_cyc'][trace]) <= 0.0
                    or float(raw_data['useful_cyc'][reference]) <= 0.0
                    or float(raw_data['useful_not_0_tot'][trace]) <= 0.0
                    or float(raw_data['useful_not_0_tot'][reference]) <= 0.0
                ):
                    mod_factors['freq_scale'][trace] = 'Non-Avail'

                elif (
                    trace_mode[trace][:5] != 'Burst'
                    and trace_mode[trace] != 'Sampling'
                ):
                    frequency_ref = (
                        float(raw_data['useful_cyc'][reference])
                        / float(raw_data['useful_not_0_tot'][reference])
                    )

                    frequency = (
                        float(raw_data['useful_cyc'][trace])
                        / float(raw_data['useful_not_0_tot'][trace])
                    )

                    mod_factors['freq_scale'][trace] = (
                        frequency
                        / frequency_ref
                        * 100.0
                    )

                else:
                    mod_factors['freq_scale'][trace] = 'Non-Avail'

            else:
                mod_factors['freq_scale'][trace] = 'Non-Avail'

        except (TypeError, ValueError, ZeroDivisionError):
            mod_factors['freq_scale'][trace] = 'NaN'
            
        # freq scale + Serial I/O
        try:  # except NaN
            if not ENABLE_IO_AWARE_METRICS:
                mod_factors_scale_plus_io['freq_scale'][trace] = 'Non-Avail'            
            
            elif len(trace_list) > 1:
                if other_metrics['io_posix'][trace] > 0.0 or other_metrics['flushing'][trace] > 0.0:
                    freq_serial_io_0 = (float(raw_data['useful_cyc'][trace_list[0]])
                                    + float(raw_data['io_cyc'][trace_list[0]])
                                    + float(raw_data['flushing_cyc'][trace_list[0]])) \
                                   / (float(raw_data['useful_not_0_tot'][trace_list[0]])
                                      + float(raw_data['io_tot'][trace_list[0]])
                                      + float(raw_data['flushing_tot'][trace_list[0]])) / 1000

                    freq_serial_io_n = (float(raw_data['useful_cyc'][trace]) + float(raw_data['io_cyc'][trace])
                                    + float(raw_data['flushing_cyc'][trace])) \
                                   / (float(raw_data['useful_not_0_tot'][trace])
                                      + float(raw_data['io_tot'][trace])
                                      + float(raw_data['flushing_tot'][trace])) / 1000
                    mod_factors_scale_plus_io['freq_scale'][trace] = freq_serial_io_n / freq_serial_io_0 * 100.0
                else:
                    mod_factors_scale_plus_io['freq_scale'][trace] = mod_factors['freq_scale'][trace]
            else:
                mod_factors_scale_plus_io['freq_scale'][trace] = 'Non-Avail'
        except:
            mod_factors_scale_plus_io['freq_scale'][trace] = 'NaN'

        # Instruction Scalability
        try:  # except NaN
            if len(trace_list) > 1:
                if trace_mode[trace][:5] != 'Burst' and trace_mode[trace] != 'Sampling':
                    if scaling == 'strong':
                        mod_factors['inst_scale'][trace] = float(raw_data['useful_ins'][trace_list[0]]) \
                                                   / float(raw_data['useful_ins'][trace]) * 100.0
                    else:
                        procs_ratio_ins = float(raw_data['procs_ins'][trace]) \
                                          / float(raw_data['procs_ins'][trace_list[0]])
                        mod_factors['inst_scale'][trace] = float(raw_data['useful_ins'][trace_list[0]]) \
                                                   / float(raw_data['useful_ins'][trace]) \
                                                       * procs_ratio_ins * 100.0
                else:
                    mod_factors['inst_scale'][trace] = 'Non-Avail'
            else:
                mod_factors['inst_scale'][trace] = 'Non-Avail'
        except:
            mod_factors['inst_scale'][trace] = 'NaN'

        # ins scale + Serial I/O
        try:  # except NaN
            if not ENABLE_IO_AWARE_METRICS:
                mod_factors_scale_plus_io['inst_scale'][trace] = 'Non-Avail'
            elif len(trace_list) > 1:
                if other_metrics['io_posix'][trace] > 0.0 or other_metrics['flushing'][trace] > 0.0:
                    useful_ins_plus_io_0 = float(raw_data['useful_ins'][trace_list[0]]) \
                                       + float(raw_data['io_ins'][trace_list[0]]) \
                                       + float(raw_data['flushing_ins'][trace_list[0]])
                    useful_ins_plus_io_n = float(raw_data['useful_ins'][trace]) \
                                       + float(raw_data['io_ins'][trace]) \
                                       + float(raw_data['flushing_ins'][trace])
                    if scaling == 'strong':
                        mod_factors_scale_plus_io['inst_scale'][trace] = useful_ins_plus_io_0 \
                                                                 / useful_ins_plus_io_n * 100.0
                    else:
                        procs_ratio_ins = float(raw_data['procs_ins'][trace]) \
                                          / float(raw_data['procs_ins'][trace_list[0]])
                        mod_factors_scale_plus_io['inst_scale'][trace] = useful_ins_plus_io_0 / useful_ins_plus_io_n \
                                                     * procs_ratio_ins * 100.0
                else:
                    mod_factors_scale_plus_io['inst_scale'][trace] = mod_factors['inst_scale'][trace]
            else:
                mod_factors_scale_plus_io['inst_scale'][trace] = 'Non-Avail'
        except:
            mod_factors_scale_plus_io['inst_scale'][trace] = 'NaN'

        # Speed-UP
        try:  # except NaN
            if len(trace_list) > 1:
                if scaling == 'strong':
                    other_metrics['speedup'][trace] = raw_data['runtime'][trace_list[0]] \
                                                / raw_data['runtime'][trace]
                else:
                    other_metrics['speedup'][trace] = raw_data['runtime'][trace_list[0]] \
                                                      / raw_data['runtime'][trace] * proc_ratio
            else:
                other_metrics['speedup'][trace] = 'Non-Avail'
        except:
            other_metrics['speedup'][trace] = 'NaN'

        try:  # except NaN
            other_metrics['elapsed_time'][trace] = raw_data['runtime'][trace] * 0.000001
        except:
            other_metrics['elapsed_time'][trace] = 'NaN'

        # Efficiency
        try:  # except NaN
            if len(trace_list) > 1:
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
        other_metrics, 
        omp_talp_factors,
        scaling_info,
    )


def read_mod_factors_csv(cmdl_args):
    """Reads the model factors table from a csv file."""
    global mod_factors_doc

    delimiter = ';'
    file_path = cmdl_args.project

    # Read csv to list of lines
    if os.path.isfile(file_path) and file_path[-4:] == '.csv':
        with open(file_path, 'r') as f:
            lines = f.readlines()
        lines = [line.rstrip('\n') for line in lines]
    else:
        print('==ERROR==', file_path, 'is not a valid csv file.')
        sys.exit(1)

    # Get the number of processes of the traces
    processes = lines[0].split(delimiter)
    processes.pop(0)

    # Create artificial trace_list and trace_processes
    trace_list = []
    trace_processes = dict()
    for process in processes:
        trace_list.append(process)
        trace_processes[process] = int(process)

    # Create empty mod_factors handle
    mod_factors = create_mod_factors(trace_list)

    # Get mod_factor_doc keys
    mod_factors_keys = list(mod_factors_doc.items())

    # Iterate over the data lines
    for index, line in enumerate(lines[1:len(mod_factors_keys) + 1]):
        key = mod_factors_keys[index][0]
        line = line.split(delimiter)
        for index, trace in enumerate(trace_list):
            mod_factors[key][trace] = float(line[index + 1])

    if cmdl_args.debug:
        print_mod_factors_table(mod_factors, trace_list, trace_processes)

    return mod_factors, trace_list, trace_processes


def print_mod_factors_table(mod_factors, other_metrics, mod_factors_scale_plus_io, trace_list, trace_processes, trace_mode):
    """Prints the model factors table in human readable form on stdout."""
    global mod_factors_doc
    global mod_factors_scale_plus_io_doc

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
        if mod_factors['serial_eff'][trace] == "Warning!" \
                or mod_factors['transfer_eff'][trace] == "Warning!":
            warning_simulation.append(1)
    if len(warning_flush_wrong) > 0:
        print("WARNING! Flushing in a trace is too high. Disabling standard output metrics...")
        print("         Flushing is an overhead due to the tracer, please review your trace.")
        print('')
        return

    print('Overview of the Efficiency metrics:')

    longest_name = len(sorted(mod_factors_doc.values(), key=len)[-1])

    # line = ''.rjust(longest_name)

    line = 'Processes [Trace Order]'.rjust(longest_name)
    line_trace_mode = 'Trace mode'.rjust(longest_name)

    if len(trace_list) == 1:
        limit_min = trace_processes[trace_list[0]]
        limit_max = trace_processes[trace_list[0]]
    else:
        limit_min = trace_processes[trace_list[0]]
        limit_max = trace_processes[trace_list[len(trace_list)-1]]

    # BEGIN To adjust header to big number of processes
    procs_header = []
    for index, trace in enumerate(trace_list):
        if limit_min == limit_max and len(trace_list) > 1:
            procs_header.append(str(trace_processes[trace]) + '[' + str(index+1) + ']')
        else:
            procs_header.append(str(trace_processes[trace]))

    max_len_header = 0
    for proc_h in procs_header:
        if max_len_header < len(proc_h):
            max_len_header = len(proc_h)

    value_to_adjust = 10
    if max_len_header > value_to_adjust:
        value_to_adjust = max_len_header + 1
    # END To adjust header to big number of processes
    label_trace_mode = []
    mode_string = ""
    for index, trace in enumerate(trace_list):
        line += ' | '
        line_trace_mode += ' | '
        #if limit_min == limit_max and len(trace_list) > 1:
        line += (str(trace_processes[trace]) + '[' + str(index+1) + ']').rjust(value_to_adjust)
        #else:
        #    line += (str(trace_processes[trace])).rjust(value_to_adjust)

        # For trace mode
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
            try:  # except NaN
                line += ('{0:.2f}%'.format(mod_factors[mod_key][trace])).rjust(value_to_adjust)
            except ValueError:
                line += ('{}'.format(mod_factors[mod_key][trace])).rjust(value_to_adjust)
        print(line)

    # print('')

    io_metrics = []
    io_metrics.append(0)
    for mod_key in mod_factors_scale_plus_io_doc:
        for trace in trace_list:
            if mod_factors_scale_plus_io[mod_key][trace] != 0:
                io_metrics.append(1)

    if (
        ENABLE_IO_AWARE_METRICS
        and (len(warning_flush) >= 1 or len(warning_io) >= 1)
        and len(trace_list) > 1
    ):
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

    if len(warning_simulation) > 0:
        print("===> Warning! Metrics obtained from simulated traces exceed 100%. "
              "Please review original and simulated traces.")
    print('')


def print_other_metrics_table(
        other_metrics,
        trace_list,
        trace_processes):

    """Print general performance indicators and complementary metrics."""

    global other_metrics_doc

    print('Overview of the Speedup, IPC and Frequency:')

    longest_name = len(
        sorted(
            other_metrics_doc.values(),
            key=len
        )[-1]
    )

    line = ''.rjust(longest_name)

    if len(trace_list) == 1:
        limit_min = trace_processes[trace_list[0]]
        limit_max = trace_processes[trace_list[0]]
    else:
        limit_min = trace_processes[trace_list[0]]
        limit_max = trace_processes[trace_list[len(trace_list) - 1]]

    # --------------------------------------------------
    # Adjust header width to large process counts
    # --------------------------------------------------

    procs_header = []

    for index, trace in enumerate(trace_list):

        if limit_min == limit_max and len(trace_list) > 1:
            procs_header.append(
                str(trace_processes[trace])
                + '['
                + str(index + 1)
                + ']'
            )
        else:
            procs_header.append(
                str(trace_processes[trace])
            )

    max_len_header = 0

    for proc_h in procs_header:
        if max_len_header < len(proc_h):
            max_len_header = len(proc_h)

    value_to_adjust = 10

    if max_len_header > value_to_adjust:
        value_to_adjust = max_len_header + 1

    # --------------------------------------------------
    # Build execution-configuration header
    # --------------------------------------------------

    for index, trace in enumerate(trace_list):

        line += ' | '

        line += (
            str(trace_processes[trace])
            + '['
            + str(index + 1)
            + ']'
        ).rjust(value_to_adjust)

    print(''.ljust(len(line), '-'))
    print(line)

    line_head = line

    print(''.ljust(len(line), '-'))

    # --------------------------------------------------
    # General performance indicators
    # --------------------------------------------------

    for mod_key in other_metrics_doc:

        line = other_metrics_doc[mod_key].ljust(
            longest_name
        )

        if len(trace_list) > 1:

            if mod_key in [
                'speedup',
                'ipc',
                'freq',
                'elapsed_time',
                'efficiency',
            ]:

                for trace in trace_list:

                    line += ' | '

                    try:
                        line += (
                            '{0:.2f}'.format(
                                other_metrics[mod_key][trace]
                            )
                        ).rjust(value_to_adjust)

                    except (ValueError, TypeError):
                        line += (
                            '{}'.format(
                                other_metrics[mod_key][trace]
                            )
                        ).rjust(value_to_adjust)

                print(line)

        else:

            if mod_key in [
                'ipc',
                'freq',
                'elapsed_time',
            ]:

                for trace in trace_list:

                    line += ' | '

                    try:
                        line += (
                            '{0:.2f}'.format(
                                other_metrics[mod_key][trace]
                            )
                        ).rjust(value_to_adjust)

                    except (ValueError, TypeError):
                        line += (
                            '{}'.format(
                                other_metrics[mod_key][trace]
                            )
                        ).rjust(value_to_adjust)

                print(line)

    print(''.ljust(len(line_head), '-'))

    # --------------------------------------------------
    # Detect tracer flushing and File I/O activity
    # --------------------------------------------------

    warning_flush = []
    io_detected = False
    significant_io = False

    for trace in trace_list:

        if other_metrics['flushing'][trace] >= 10.0:
            warning_flush.append(1)

        # File I/O is considered available when at least one
        # API-specific efficiency metric is available.
        if (
            other_metrics['mpi_io_eff'][trace] != 'Non-Avail'
            or other_metrics['posix_io_eff'][trace] != 'Non-Avail'
        ):
            io_detected = True

        # Keep the previous 5% threshold as an informational
        # indication of significant I/O activity.
        if (
            other_metrics['io_mpiio'][trace] >= 5.0
            or other_metrics['io_posix'][trace] >= 5.0
        ):
            significant_io = True

    # --------------------------------------------------
    # Tracer flushing information
    # --------------------------------------------------

    if len(warning_flush) > 0:

        print("Overview of tracer's flushing weight:")
        print(''.ljust(len(line_head), '-'))

        line = other_metrics_doc['flushing'].ljust(
            longest_name
        )

        for trace in trace_list:

            line += ' | '

            value = other_metrics['flushing'][trace]

            try:
                line += (
                    '{0:.2f}%'.format(value)
                ).rjust(value_to_adjust)

            except (ValueError, TypeError):
                line += (
                    '{}'.format(value)
                ).rjust(value_to_adjust)

        print(line)

        print(''.ljust(len(line_head), '-'))

    # --------------------------------------------------
    # File I/O efficiency metrics
    # --------------------------------------------------

    if io_detected:

        print('Overview of File I/O Efficiency:')
        print(''.ljust(len(line_head), '-'))

        io_metric_keys = [
            'io_eff',
            'mpi_io_eff',
            'mpi_io_load_balance',
            'posix_io_eff',
            'posix_io_load_balance',
        ]

        for metric_key in io_metric_keys:

            line = other_metrics_doc[metric_key].ljust(
                longest_name
            )

            for trace in trace_list:

                line += ' | '

                value = other_metrics[metric_key][trace]

                try:
                    line += (
                        '{0:.2f}%'.format(value)
                    ).rjust(value_to_adjust)

                except (ValueError, TypeError):
                    line += (
                        '{}'.format(value)
                    ).rjust(value_to_adjust)

            print(line)

        print(''.ljust(len(line_head), '-'))

    # --------------------------------------------------
    # Informational messages
    # --------------------------------------------------

    if len(warning_flush) > 0:
        print(
            'WARNING! Tracer flushing is high and may affect '
            'the measured execution.'
        )

    if significant_io:
        print(
            'INFO: Significant File I/O activity was detected '
            'in the analyzed execution.'
        )

    print('')


def print_efficiency_table(
        mod_factors,
        trace_list,
        trace_processes,
        trace_tasks,
        trace_threads):

    """Writes the efficiency metrics table and creates the Gnuplot file."""

    global mod_factors_doc

    delimiter = ','

    file_path = os.path.join(
        os.getcwd(),
        'efficiency_table.csv'
    )

    # --------------------------------------------------
    # Build canonical configuration labels
    # --------------------------------------------------

    configuration_labels = []

    base_labels = [
        str(trace_processes[trace])
        for trace in trace_list
    ]

    for index, label in enumerate(base_labels):
        if base_labels.count(label) > 1:
            label += ' [' + str(index + 1) + ']'

        configuration_labels.append(label)

    # --------------------------------------------------
    # Write efficiency-table CSV
    # --------------------------------------------------

    with open(file_path, 'w') as output:

        line = '"Metric"'

        for label in configuration_labels:
            line += delimiter
            line += label

        output.write(line + '\n')

        for mod_key in mod_factors_doc:

            # Preserve metric hierarchy.
            line = '"' + mod_factors_doc[mod_key] + '"'

            for trace in trace_list:
                line += delimiter

                value = mod_factors[mod_key][trace]

                if value in (
                        'Non-Avail',
                        'Warning!',
                        'N/A',
                        'NaN'):
                    line += str(value)
                else:
                    try:
                        line += '{0:.2f}'.format(value)
                    except (ValueError, TypeError):
                        line += '{}'.format(value)

            output.write(line + '\n')

    # --------------------------------------------------
    # Create Gnuplot file for efficiency plot
    # --------------------------------------------------

    gp_template = os.path.join(
        os.path.dirname(os.path.realpath(__file__)),
        'cfgs',
        'efficiency_table.gp'
    )

    content = []

    with open(gp_template) as f:
        content = f.readlines()

    limit_procs = 500 + len(trace_list) * 60

    content = [
        line.replace(
            '#REPLACE_BY_SIZE',
            ''.join([
                'set terminal pngcairo enhanced dashed crop size ',
                str(limit_procs),
                ',460 font "Latin Modern Roman,14"'
            ])
        )
        for line in content
    ]

    file_path = os.path.join(
        os.getcwd(),
        'efficiency_table.gp'
    )

    with open(file_path, 'w') as f:
        f.writelines(content)

    if len(trace_list) > 1:
        print(
            'Efficiency Table written to '
            + file_path[:len(file_path) - 3]
            + '.gp'
        )


def print_mod_factors_csv(mod_factors, trace_list, trace_processes):
    """Prints the model factors table in a csv file."""
    global mod_factors_doc

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

        output.write('#\n')

    print('======== Output Files: Metrics and Plots ========')
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
        line = "\"Number of processes\""
        for trace in trace_list:
            line += delimiter
            line += str(trace_processes[trace])
        output.write(line + '\n')

        for mod_key in other_metrics_doc:
            line = "\"" + other_metrics_doc[mod_key].replace('  ', '', 2) +"\""
            for trace in trace_list:
                line += delimiter
                try:  # except NaN
                    line += '{0:.6f}'.format(other_metrics[mod_key][trace])
                except ValueError:
                    line += '{}'.format(other_metrics[mod_key][trace])
            output.write(line + '\n')

        output.write('#\n')

    print('======== Output File: Other Metrics ========')
    print('Speedup, IPC, Frequency, I/O and Flushing written to ' + file_path)
    print('')


def plots_efficiency_table_matplot(
        trace_list,
        trace_processes,
        trace_tasks,
        trace_threads,
        cmdl_args):
    """Render the simple-model efficiency table using Matplotlib."""

    file_path = os.path.join(
        os.getcwd(),
        'efficiency_table.csv'
    )

    df = pd.read_csv(file_path)

    # First CSV column contains metric names.
    metrics = df['Metric'].tolist()

    # Remaining CSV columns already contain the canonical
    # execution-configuration labels.
    configuration_labels = list(df.columns)[1:]

    list_data = []

    for _, rows in df.iterrows():
        list_temp = []

        for value in list(rows)[1:]:

            if pd.isna(value):
                list_temp.append(np.nan)
                continue

            try:
                numeric_value = float(value)
            except (TypeError, ValueError):
                # Non-Avail, Warning!, N/A, NaN, ...
                numeric_value = np.nan

            list_temp.append(numeric_value)

        list_data.append(list_temp)

    list_np = np.array(list_data)

    df_plot = pd.DataFrame(
        list_np,
        index=metrics,
        columns=configuration_labels
    )

    _plot_efficiency_heatmap(
        df_plot,
        'efficiency_table-matplot'
    )


def plots_modelfactors_matplot(trace_list, trace_mode, trace_processes, trace_tasks, trace_threads, cmdl_args):
    # Plotting using python
    # For plotting using python, read the csv file
    file_path = os.path.join(os.getcwd(), 'modelfactors.csv')
    df = pd.read_csv(file_path, sep=';')

    # metrics = df['Number of processes'].tolist()

    traces_procs = list(df.keys())[1:]

    list_data = []
    for index, rows in df.iterrows():
        list_temp = []
        for value in list(rows)[1:]:
            if value != 'Non-Avail' and value != "Warning!":
                list_temp.append(float(value))
            elif value == 'Non-Avail' or value == "Warning!":
                list_temp.append(float('nan'))
        #print(list_temp)
        list_data.append(list_temp)

    # To control same number of processes for the header on plots and table
    same_procs = True
    procs_trace_prev = trace_processes[trace_list[0]]
    tasks_trace_prev = trace_tasks[trace_list[0]]
    threads_trace_prev = trace_threads[trace_list[0]]
    for index, trace in enumerate(trace_list):
        tasks = trace_tasks[trace]
        threads = trace_tasks[trace]
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
    for index, trace in enumerate(trace_list):
        tasks = trace_tasks[trace]
        threads = trace_tasks[trace]
        if int(limit) == int(limit_min) and same_procs:
            s_xtics = str(trace_processes[trace]) + '[' + str(index + 1) + ']'
        elif int(limit) == int(limit_min) and not same_procs:
            s_xtics = str(trace_processes[trace]) + '(' + str(tasks) + 'x' \
                           + str(threads) + ')'
        else:
            s_xtics = str(trace_processes[trace])
        label_xtics.append(s_xtics)

    ### Plot: Global Metrics
    # print(list_data)
    plt.figure()
    max_global = max([max(list_data[0]), max(list_data[1]), max(list_data[2]), max(list_data[3]), max(list_data[6])])
    plt.plot(traces_procs, list_data[0], 'o-', color='black', label='Global Efficiency')
    plt.plot(traces_procs, list_data[1], 's--', color='magenta', label='Parallel Efficiency')
    plt.plot(traces_procs, list_data[2], 'X:', color='red', linewidth=2, label='Load Balance')
    plt.plot(traces_procs, list_data[3], 'x-.', color='green', label='Communication efficiency')
    plt.plot(traces_procs, list_data[6], 'v--', color='blue', label='Computation scalability')
    plt.xlabel("Number of Processes")
    plt.ylabel("Efficiency (%)")
    plt.xticks(tuple(traces_procs), tuple(label_xtics))
    # print(max_global)
    if float(max_global) < 100:
        max_global = 100

    plt.ylim(0, float(max_global)+5)
    plt.legend()
    plt.savefig('modelfactors-matplot.png', bbox_inches='tight')

    # Plot: Comm Metrics
    if trace_mode[trace] == 'Detailed+MPI':
        plt.figure()
        if max(list_data[3]) != 'NaN' and max(list_data[4]) != 'NaN' and max(list_data[5]) != 'NaN':
            max_comm = max([max(list_data[3]), max(list_data[4]), max(list_data[5])])
            plt.plot(traces_procs, list_data[3], 's-', color='green', label='Communication efficiency')
            plt.plot(traces_procs, list_data[4], 'h--', color='gold', label='Serialization efficiency')
            plt.plot(traces_procs, list_data[5], 'x:', color='tomato', label='Transfer efficiency')
            plt.xlabel("Number of Processes")
            plt.ylabel("Efficiency (%)")
            plt.xticks(tuple(traces_procs), tuple(label_xtics))
        
            if float(max_comm) < 100:
                max_comm = 100

            plt.ylim(0, float(max_comm)+5)
            plt.legend()
            plt.savefig('modelfactors-comm-matplot.png', bbox_inches='tight')

    ### Plot: Scale Metrics
    if trace_mode[trace][:5] != 'Burst':
        plt.figure()
        max_scale = max([max(list_data[6]), max(list_data[7]), max(list_data[8]), max(list_data[9])])
        plt.plot(traces_procs, list_data[6], 'v-', color='blue', label='Computation scalability')
        plt.plot(traces_procs, list_data[7], 'v--', color='skyblue', label='IPC scalability')
        plt.plot(traces_procs, list_data[8], 'v:', color='gray', label='Instruction scalability')
        plt.plot(traces_procs, list_data[9], 'v-.', color='darkviolet', label='Frequency scalability')
        plt.xlabel("Number of Processes")
        plt.ylabel("Efficiency (%)")
        plt.xticks(tuple(traces_procs), tuple(label_xtics))
        if float(max_scale) < 100:
            max_scale = 100

        plt.ylim(0, float(max_scale)+5)
        plt.legend()
        plt.savefig('modelfactors-scale-matplot.png', bbox_inches='tight')


def plots_speedup_matplot(
        trace_list,
        trace_processes,
        trace_tasks,
        trace_threads,
        cmdl_args):
    """
    Plot measured Speedup and Efficiency against their ideal values.

    The numeric x coordinates are kept separate from the displayed
    configuration labels so that traces with the same number of
    parallel units can still be represented individually.
    """

    file_path = os.path.join(
        os.getcwd(),
        'other_metrics.csv'
    )

    df = pd.read_csv(
        file_path,
        sep=';'
    )

    # --------------------------------------------------
    # Read metric values
    # --------------------------------------------------

    list_data = []

    for _, rows in df.iterrows():
        list_temp = []

        for value in list(rows)[1:]:

            if pd.isna(value):
                list_temp.append(np.nan)
                continue

            try:
                list_temp.append(float(value))
            except (TypeError, ValueError):
                # Non-Avail, NaN, ...
                list_temp.append(np.nan)

        list_data.append(list_temp)

    # Current other_metrics.csv ordering:
    #
    # 0 elapsed_time
    # 1 efficiency
    # 2 speedup
    # 3 ipc
    # 4 freq
    # ...
    efficiency_values = list_data[1]
    speedup_values = list_data[2]

    # --------------------------------------------------
    # Configuration labels
    # --------------------------------------------------

    # Simple metrics use only the number of parallel units.
    #
    # MPI    -> ranks
    # OpenMP -> threads
    # OmpSs  -> workers
    #
    # Repeated configurations are distinguished with [Trace ID].
    base_labels = [
        str(trace_processes[trace])
        for trace in trace_list
    ]

    configuration_labels = []

    for index, label in enumerate(base_labels):
        if base_labels.count(label) > 1:
            label += ' [' + str(index + 1) + ']'

        configuration_labels.append(label)

    # --------------------------------------------------
    # Numeric x coordinates
    # --------------------------------------------------

    # Preserve the previous BasicAnalysis behavior:
    # repeated configurations receive slightly different numeric
    # positions so that individual points and connecting lines remain
    # visible.
    x_values = []

    previous_procs = None
    repeated_count = 0

    for trace in trace_list:

        procs = int(trace_processes[trace])

        if previous_procs == procs:
            repeated_count += 1
            x = procs + (2 * repeated_count)
        else:
            repeated_count = 0
            x = procs

        x_values.append(x)
        previous_procs = procs

    # --------------------------------------------------
    # Ideal values
    # --------------------------------------------------

    reference_units = float(
        trace_processes[trace_list[0]]
    )

    ideal_speedup = [
        float(trace_processes[trace]) / reference_units
        for trace in trace_list
    ]

    ideal_efficiency = [
        1.0
        for _ in trace_list
    ]

    # --------------------------------------------------
    # SPEEDUP
    # --------------------------------------------------

    fig, ax = plt.subplots(
        figsize=(7.2, 4.8),
        constrained_layout=True
    )

    ax.plot(
        x_values,
        speedup_values,
        marker='o',
        linewidth=2.0,
        markersize=7,
        label='Measured'
    )

    ax.plot(
        x_values,
        ideal_speedup,
        marker='o',
        linewidth=1.6,
        markersize=6,
        linestyle='--',
        label='Ideal'
    )

    # Numeric annotations for measured values.
    for x, y in zip(
            x_values,
            speedup_values):

        if np.isnan(y):
            continue

        ax.annotate(
            '{:.2f}'.format(y),
            (x, y),
            textcoords='offset points',
            xytext=(0, 9),
            ha='center',
            fontsize=10
        )

    ax.set_xticks(
        x_values
    )

    ax.set_xticklabels(
        configuration_labels,
        fontsize=11
    )

    ax.set_xlabel(
        'Parallel units',
        fontsize=12
    )

    ax.set_ylabel(
        'Speedup',
        fontsize=12
    )

    ax.tick_params(
        axis='y',
        labelsize=11
    )

    ax.set_ylim(
        bottom=0
    )

    ax.grid(
        axis='y',
        linewidth=0.5,
        alpha=0.35
    )

    ax.legend(
        fontsize=10,
        frameon=True
    )

    fig.savefig(
        'speedup-matplot.png',
        dpi=400,
        bbox_inches='tight'
    )

    fig.savefig(
        'speedup-matplot.pdf',
        bbox_inches='tight'
    )

    plt.close(fig)

    # --------------------------------------------------
    # EFFICIENCY
    # --------------------------------------------------

    fig, ax = plt.subplots(
        figsize=(7.2, 4.8),
        constrained_layout=True
    )

    ax.plot(
        x_values,
        efficiency_values,
        marker='o',
        linewidth=2.0,
        markersize=7,
        label='Measured'
    )

    ax.plot(
        x_values,
        ideal_efficiency,
        linewidth=1.6,
        linestyle='--',
        label='Ideal'
    )

    # Numeric annotations for measured values.
    for x, y in zip(
            x_values,
            efficiency_values):

        if np.isnan(y):
            continue

        ax.annotate(
            '{:.2f}'.format(y),
            (x, y),
            textcoords='offset points',
            xytext=(0, 9),
            ha='center',
            fontsize=10
        )

    ax.set_xticks(
        x_values
    )

    ax.set_xticklabels(
        configuration_labels,
        fontsize=11
    )

    ax.set_xlabel(
        'Parallel units',
        fontsize=12
    )

    ax.set_ylabel(
        'Efficiency',
        fontsize=12
    )

    ax.tick_params(
        axis='y',
        labelsize=11
    )

    # Leave a little room above the ideal-efficiency line.
    finite_efficiency = [
        value
        for value in efficiency_values
        if not np.isnan(value)
    ]

    max_efficiency = (
        max(finite_efficiency)
        if finite_efficiency
        else 1.0
    )

    upper_limit = max(
        1.10,
        max_efficiency + 0.10
    )

    ax.set_ylim(
        0,
        upper_limit
    )

    ax.grid(
        axis='y',
        linewidth=0.5,
        alpha=0.35
    )

    ax.legend(
        fontsize=10,
        frameon=True
    )

    fig.savefig(
        'efficiency-matplot.png',
        dpi=400,
        bbox_inches='tight'
    )

    fig.savefig(
        'efficiency-matplot.pdf',
        bbox_inches='tight'
    )

    plt.close(fig)


def print_omp_talp_metrics_csv(omp_talp_factors, trace_list, trace_processes):
    """Print isolated OpenMP TALP-style metrics for validation."""
    global mod_omp_factors_doc

    delimiter = ';'
    file_path = os.path.join(os.getcwd(), 'omp_talp_metrics.csv')

    with open(file_path, 'w') as output:
        line = '"Number of processes"'
        for trace in trace_list:
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