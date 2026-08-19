#!/usr/bin/env python3

"""Functions to plots efficiencies metrics"""

from __future__ import print_function, division
import os
from collections import OrderedDict

from configuration import (
    format_configuration_label,
    disambiguate_configuration_labels,
)

# error import variables
error_import_scipy = False
error_import_numpy = False

try:
    import scipy.optimize
except ImportError:
    error_import_scipy = True
    # print('==ERROR== Could not import SciPy. Please make sure to install a current version.')

try:
    import numpy
except ImportError:
    error_import_numpy = True
    # print('==ERROR== Could not import NumPy. Please make sure to install a current version.')


mod_hybrid_factors_doc = OrderedDict([
                               ('hybrid_eff', '-- Hybrid Parallel efficiency'),
                               ('mpi_parallel_eff', '   -- MPI Parallel efficiency'),
                               ('mpi_load_balance', '      -- MPI Load balance'),
                               ('mpi_comm_eff', '      -- MPI Communication efficiency'),
                               ('serial_eff', '         -- Serialization efficiency'),
                               ('transfer_eff', '         -- Transfer efficiency'),
                               ('omp_parallel_eff', '   -- OMP Parallel efficiency'),
                               ('omp_load_balance', '      -- OMP Load balance'),
                               ('omp_comm_eff', '      -- OMP Communication efficiency')])



def is_mpi_gpu_mode(mode):
    """Return True for supported MPI+GPU execution modes."""
    return mode in (
        'Detailed+MPI+CUDA',
        'Detailed+MPI+HIP',
    )


def _build_simple_plot_axis(
        trace_list,
        trace_processes,
        offset=5):
    """
    Build display labels and numeric x coordinates for simple-model plots.

    Repeated parallel-unit configurations are disambiguated with
    [Trace ID] and shifted slightly on the numeric x-axis so that
    their points remain individually visible.

    Returns:
        labels: displayed x-tick labels
        x_values: numeric x coordinates used for plotting
    """

    base_labels = [
        str(trace_processes[trace])
        for trace in trace_list
    ]

    labels = []
    x_values = []

    # Track how many times each parallel-unit count has appeared.
    occurrences = {}

    for index, trace in enumerate(trace_list):
        units = int(
            float(trace_processes[trace])
        )

        label = base_labels[index]

        # Add Trace ID only if this configuration is repeated.
        if base_labels.count(label) > 1:
            label += ' [' + str(index + 1) + ']'

        labels.append(label)

        occurrence = occurrences.get(
            units,
            0
        )

        x_value = (
            units
            + occurrence * offset
        )

        x_values.append(
            x_value
        )

        occurrences[units] = (
            occurrence + 1
        )

    return labels, x_values


def _build_hybrid_plot_axis(
        trace_list,
        trace_processes,
        trace_tasks,
        trace_threads,
        trace_mode,
        raw_data,
        offset=5):
    """
    Build configuration labels and numeric x coordinates for
    hybrid-model Gnuplot figures.

    The displayed configuration is independent from the numeric
    plotting coordinate. Traces with the same number of parallel
    units therefore remain individually visible.

    Returns:
        configuration_labels
        plot_x_values
    """

    base_labels = []

    # --------------------------------------------------
    # Build canonical configuration labels
    # --------------------------------------------------

    for trace in trace_list:

        # MPI + GPU
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
                    if (
                            total_gpu_streams
                            % int(mpi_ranks)
                            == 0
                    ):
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
                model_key='mpi_gpu',
                processes=parallel_units,
                mpi_ranks=mpi_ranks,
                gpu_streams=total_gpu_streams,
                streams_per_rank=streams_per_rank,
                devices=devices,
                separator='x',
            )

        # MPI + threaded/runtime model
        elif trace_mode[trace].startswith(
                'Detailed+MPI+'):

            label = format_configuration_label(
                model_key='mpi_threads',
                processes=trace_processes[trace],
                mpi_ranks=trace_tasks[trace],
                inner_units=trace_threads[trace],
                separator='x',
            )

        # Generic fallback
        else:

            label = format_configuration_label(
                model_key='generic',
                processes=trace_processes[trace],
                separator='x',
            )

        base_labels.append(label)

    # --------------------------------------------------
    # Add Trace IDs only where configuration labels
    # actually need disambiguation.
    # --------------------------------------------------

    trace_ids = [
        index + 1
        for index in range(len(trace_list))
    ]

    configuration_labels = (
        disambiguate_configuration_labels(
            base_labels,
            trace_ids=trace_ids,
        )
    )

    # --------------------------------------------------
    # Numeric plotting coordinates
    # --------------------------------------------------

    plot_x_values = []

    occurrences = {}

    for trace in trace_list:

        parallel_units = int(
            float(trace_processes[trace])
        )

        occurrence = occurrences.get(
            parallel_units,
            0
        )

        x_value = (
            parallel_units
            + occurrence * offset
        )

        plot_x_values.append(
            x_value
        )

        occurrences[parallel_units] = (
            occurrence + 1
        )

    return (
        configuration_labels,
        plot_x_values,
    )


def plot_hybrid_metrics(
        mod_factors,
        hybrid_factors,
        trace_list,
        trace_processes,
        trace_tasks,
        trace_threads,
        trace_mode,
        raw_data,
        cmdl_args):
    """Computes the projection from the gathered model factors and returns the
    according dictionary of fitted prediction functions."""

    global mod_hybrid_factors_doc

    # Update the hybrid parallelism mode
    trace_mode_doc = trace_mode[trace_list[0]]
    if trace_mode_doc[0:len("Detailed+MPI+")] == "Detailed+MPI+":
        mod_hybrid_factors_doc['omp_parallel_eff'] = "   -- " + \
                                                     trace_mode_doc[len("Detailed+MPI+"):] + " Parallel efficiency"
        mod_hybrid_factors_doc['omp_load_balance'] = "      -- " + \
                                                     trace_mode_doc[len("Detailed+MPI+"):] + " Load Balance"
        mod_hybrid_factors_doc['omp_comm_eff'] = "      -- " + \
                                                 trace_mode_doc[len("Detailed+MPI+"):] + " Communication efficiency"

    if cmdl_args.debug:
        print('==DEBUG== Plotting Modelfactors metrics.')

    x_axis_label = 'set xlabel "Parallel units"'

    number_traces = len(trace_list)

    configuration_labels, plot_x_values = (
        _build_hybrid_plot_axis(
            trace_list,
            trace_processes,
            trace_tasks,
            trace_threads,
            trace_mode,
            raw_data,
        )
    )

    x_proc = numpy.zeros(number_traces)
    y_para = numpy.zeros(number_traces)
    y_load = numpy.zeros(number_traces)
    y_comm = numpy.zeros(number_traces)
    y_comp = numpy.zeros(number_traces)
    y_glob = numpy.zeros(number_traces)
    y_ipc_scale = numpy.zeros(number_traces)
    y_inst_scale = numpy.zeros(number_traces)
    y_freq_scale = numpy.zeros(number_traces)
    y_hybrid_par = numpy.zeros(number_traces)
    y_mpi_par = numpy.zeros(number_traces)
    y_mpi_load = numpy.zeros(number_traces)
    y_mpi_comm = numpy.zeros(number_traces)
    y_comm_serial = numpy.zeros(number_traces)
    y_comm_transfer = numpy.zeros(number_traces)
    y_omp_par = numpy.zeros(number_traces)
    y_omp_load = numpy.zeros(number_traces)
    y_omp_comm = numpy.zeros(number_traces)

    #Convert dictionaries to NumPy arrays
    for index, trace in enumerate(trace_list):
        x_proc[index] = trace_processes[trace]
        y_para[index] = mod_factors['parallel_eff'][trace]
        y_load[index] = mod_factors['load_balance'][trace]
        y_comm[index] = mod_factors['comm_eff'][trace]
        y_comp[index] = mod_factors['comp_scale'][trace]
        y_glob[index] = mod_factors['global_eff'][trace]
        #print(mod_factors['ipc_scale'][trace])
        if mod_factors['ipc_scale'][trace] != 'Non-Avail':
            y_ipc_scale[index] = mod_factors['ipc_scale'][trace]
        else:
            y_ipc_scale[index] = 0.0

        if mod_factors['inst_scale'][trace] != 'Non-Avail':
            y_inst_scale[index] = mod_factors['inst_scale'][trace]
        else:
            y_inst_scale[index] = 0.0
        if mod_factors['freq_scale'][trace] != 'Non-Avail':
            y_freq_scale[index] = mod_factors['freq_scale'][trace]
        else:
            y_freq_scale[index] = 0.0
        if hybrid_factors['hybrid_eff'][trace] != 'N/A':
            y_hybrid_par[index] = hybrid_factors['hybrid_eff'][trace]
        else:
            y_hybrid_par[index] = 0.0
        if hybrid_factors['mpi_parallel_eff'][trace] != 'N/A':
            y_mpi_par[index] = hybrid_factors['mpi_parallel_eff'][trace]
        else:
            y_mpi_par[index] = 0.0
        if hybrid_factors['mpi_load_balance'][trace] != 'N/A':
            y_mpi_load[index] = hybrid_factors['mpi_load_balance'][trace]
        else:
            y_mpi_load[index] = 0.0
        if hybrid_factors['mpi_comm_eff'][trace] != 'N/A':
            y_mpi_comm[index] = hybrid_factors['mpi_comm_eff'][trace]
        else:
            y_mpi_comm[index] = 0.0

        if (
                trace_mode[trace] == 'Detailed+MPI'
                or trace_mode[trace] == 'Detailed+MPI+OpenMP'
                or is_mpi_gpu_mode(trace_mode[trace])
        ):
            if hybrid_factors['serial_eff'][trace] != 'N/A' and hybrid_factors['serial_eff'][trace] != 'Warning!' \
            and hybrid_factors['serial_eff'][trace] != 'Non-Avail':
                y_comm_serial[index] = hybrid_factors['serial_eff'][trace]
            else:
                y_comm_serial[index] = 0.0
            if hybrid_factors['transfer_eff'][trace] != 'N/A' \
                    and hybrid_factors['transfer_eff'][trace] != 'Warning!'\
                    and hybrid_factors['transfer_eff'][trace] != 'Non-Avail':
                y_comm_transfer[index] = hybrid_factors['transfer_eff'][trace]
            else:
                y_comm_transfer[index] = 0.0
        else:
            y_comm_serial[index] = 0.0
            y_comm_transfer[index] = 0.0

        if hybrid_factors['omp_parallel_eff'][trace] != 'N/A':
            y_omp_par[index] = hybrid_factors['omp_parallel_eff'][trace]
        else:
            y_omp_par[index] = 0.0
        if hybrid_factors['omp_load_balance'][trace] != 'N/A':
            y_omp_load[index] = hybrid_factors['omp_load_balance'][trace]
        else:
            y_omp_load[index] = 0.0
        if hybrid_factors['omp_comm_eff'][trace] != 'N/A':
            y_omp_comm[index] = hybrid_factors['omp_comm_eff'][trace]
        else:
            y_omp_comm[index] = 0.0


    # limit_min = str(0)
    # To extract the trace name to show in the plots
    title_string = ""
    for index, trace in enumerate(trace_list):
        folder_trace_name = trace.split('/')
        trace_name_to_show = folder_trace_name[len(folder_trace_name) - 1]
        title_string += '(' + str(index+1) + ') ' + trace_name_to_show + "\\" + 'n'

    title_string += '"' + " noenhanced"

    # --------------------------------------------------
    # Build Gnuplot x-axis once for all hybrid plots
    # --------------------------------------------------

    label_xtics = 'set xtics ('

    for label, x_value in zip(
            configuration_labels,
            plot_x_values):

        label_xtics += (
            '"'
            + label
            + '" '
            + str(x_value)
            + ', '
        )

    label_xtics = (
        label_xtics[:-2]
        + ')'
    )

    x_min = min(plot_x_values)
    x_max = max(plot_x_values)

    if x_min == x_max:
        x_margin = 1
    else:
        x_margin = max(
            1,
            int((x_max - x_min) * 0.05)
        )

    x_range = 'set xrange [{}:{}]'.format(
        x_min - x_margin,
        x_max + x_margin
    )


    # Create Gnuplot file for main plot
    gp_template = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'cfgs', 'modelfactors-onlydata.gp')
    content = []
    with open(gp_template) as f:
        content = f.readlines()

    content = [
        line.replace(
            '#REPLACE_BY_XLABEL',
            x_axis_label
        )
        for line in content
    ]


    content = [
        line.replace(
            '#REPLACE_BY_XRANGE',
            x_range
        )
        for line in content
    ]

    content = [
        line.replace(
            '#REPLACE_BY_XTICS_LABEL',
            label_xtics
        )
        for line in content
    ]


    content = [line.replace('#REPLACE_BY_TRACE_NAMES', ''.join(["set title " + '"' + ''])) for line in
               content]

    max_global = max([max(y_para), max(y_load), max(y_comm), max(y_comp), max(y_glob)])
    content = [line.replace('#REPLACE_BY_YRANGE', ''
                            .join(['set yrange [0:', str(max_global+5), ']'])) for line in content]

    file_path = os.path.join(os.getcwd(), 'modelfactors.gp')
    with open(file_path, 'w') as f:
        f.writelines(content)

    # Add data points to gnuplot file
    with open(file_path, 'a') as f:
        for index in range(0, number_traces):
            line = ' '.join([str(plot_x_values[index]), str(y_para[index]), '\n'])
            f.write(line)
        f.write('e\n')

        for index in range(0, number_traces):
            line = ' '.join([str(plot_x_values[index]), str(y_load[index]), '\n'])
            f.write(line)
        f.write('e\n')

        for index in range(0, number_traces):
            line = ' '.join([str(plot_x_values[index]), str(y_comm[index]), '\n'])
            f.write(line)
        f.write('e\n')

        for index in range(0, number_traces):
            line = ' '.join([str(plot_x_values[index]), str(y_comp[index]), '\n'])
            f.write(line)
        f.write('e\n')

        for index in range(0, number_traces):
            line = ' '.join([str(plot_x_values[index]), str(y_glob[index]), '\n'])
            f.write(line)
        f.write('e\n')

        f.write('\n')
        f.write('pause -1\n')

    # print('========= Plot (gnuplot File): EFFICIENCY METRICS ==========')
    print('Efficiency metrics plot written to ' + file_path)
    # print('')

    # Create Gnuplot file for scalability plot
    gp_template = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'cfgs', 'modelfactors_scale.gp')
    content = []

    with open(gp_template) as f:
        content = f.readlines()

    content = [
        line.replace(
            '#REPLACE_BY_XLABEL',
            x_axis_label
        )
        for line in content
    ]

 
    content = [
        line.replace(
            '#REPLACE_BY_XRANGE',
            x_range
        )
        for line in content
    ]

    content = [
        line.replace(
            '#REPLACE_BY_XTICS_LABEL',
            label_xtics
        )
        for line in content
    ]

    
    content = [line.replace('#REPLACE_BY_TRACE_NAMES', ''.join(["set title " + '"' + ''])) for line in
               content]

    max_comp = max([max(y_comp), max(y_ipc_scale), max(y_inst_scale), max(y_freq_scale)])
    content = [line.replace('#REPLACE_BY_YRANGE', ''
                            .join(['set yrange [0:', str(max_comp+5), ']'])) for line in content]

    file_path = os.path.join(os.getcwd(), 'modelfactors_scale.gp')
    with open(file_path, 'w') as f:
        f.writelines(content)

    # Add data points to gnuplot file
    with open(file_path, 'a') as f:
        for index in range(0, number_traces):
            line = ' '.join([str(plot_x_values[index]), str(y_comp[index]), '\n'])
            f.write(line)
        f.write('e\n')

        for index in range(0, number_traces):
            line = ' '.join([str(plot_x_values[index]), str(y_ipc_scale[index]), '\n'])
            f.write(line)
        f.write('e\n')

        for index in range(0, number_traces):
            line = ' '.join([str(plot_x_values[index]), str(y_inst_scale[index]), '\n'])
            f.write(line)
        f.write('e\n')

        for index in range(0, number_traces):
            line = ' '.join([str(plot_x_values[index]), str(y_freq_scale[index]), '\n'])
            f.write(line)
        f.write('e\n')

        f.write('\n')
        f.write('pause -1\n')

    # print('========  Plot (gnuplot File): SCALABILITY METRICS ========')
    print('Scalability metrics plot written to ' + file_path)

    # Create Gnuplot file for hybrid metrics plot
    gp_template = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'cfgs', 'modelfactors_hybrid.gp')
    content = []
    with open(gp_template) as f:
        content = f.readlines()

    content = [
        line.replace(
            '#REPLACE_BY_XLABEL',
            x_axis_label
        )
        for line in content
    ]

    content = [
        line.replace(
            '#REPLACE_BY_XRANGE',
            x_range
        )
        for line in content
    ]

    content = [
        line.replace(
            '#REPLACE_BY_XTICS_LABEL',
            label_xtics
        )
        for line in content
    ]

    content = [line.replace('#REPLACE_BY_TRACE_NAMES', ''.join(["set title " + '"' + ''])) for line in
               content]

    string_omp ="      '-' with linespoints title "  + '"' + (mod_hybrid_factors_doc['omp_parallel_eff'])[5:] + '"' + " ls 5,\\"
    content = [line.replace('#REPLACE_BY_OMP_PAR_EFF', ''.join([string_omp])) for line in content]

    string_omp = "      '-' with linespoints title " + '"' + (mod_hybrid_factors_doc['omp_load_balance'])[9:] + '"' + " ls 6,\\"
    content = [line.replace('#REPLACE_BY_OMP_LB', ''.join([string_omp])) for line in content]
    
    string_omp = "      '-' with linespoints title " + '"' + (mod_hybrid_factors_doc['omp_comm_eff'])[9:] + '"' + " ls 7"
    content = [line.replace('#REPLACE_BY_OMP_COMM', ''.join([string_omp])) for line in content]

    max_hybrid = max([max(y_hybrid_par), max(y_mpi_par), max(y_mpi_comm), max(y_mpi_load),
                      max(y_omp_par), max(y_omp_comm), max(y_omp_load)])
    content = [line.replace('#REPLACE_BY_YRANGE', ''
                            .join(['set yrange [0:', str(max_hybrid+5), ']'])) for line in content]

    file_path = os.path.join(os.getcwd(), 'modelfactors_hybrid.gp')
    with open(file_path, 'w') as f:
        f.writelines(content)

    # Add data points to gnuplot file
    with open(file_path, 'a') as f:
        for index in range(0, number_traces):
            line = ' '.join([str(plot_x_values[index]), str(y_hybrid_par[index]), '\n'])
            f.write(line)
        f.write('e\n')

        for index in range(0, number_traces):
            line = ' '.join([str(plot_x_values[index]), str(y_mpi_par[index]), '\n'])
            f.write(line)
        f.write('e\n')

        for index in range(0, number_traces):
            line = ' '.join([str(plot_x_values[index]), str(y_mpi_load[index]), '\n'])
            f.write(line)
        f.write('e\n')

        for index in range(0, number_traces):
            line = ' '.join([str(plot_x_values[index]), str(y_mpi_comm[index]), '\n'])
            f.write(line)
        f.write('e\n')

        for index in range(0, number_traces):
            line = ' '.join([str(plot_x_values[index]), str(y_omp_par[index]), '\n'])
            f.write(line)
        f.write('e\n')

        for index in range(0, number_traces):
            line = ' '.join([str(plot_x_values[index]), str(y_omp_load[index]), '\n'])
            f.write(line)
        f.write('e\n')

        for index in range(0, number_traces):
            line = ' '.join([str(plot_x_values[index]), str(y_omp_comm[index]), '\n'])
            f.write(line)
        f.write('e\n')

        f.write('\n')
        f.write('pause -1\n')

    print('Hybrid metrics plot written to ' + file_path)

    # Create Gnuplot file for MPI hybrid metrics plot
    gp_template = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'cfgs', 'modelfactors_mpi_hybrid.gp')
    content = []
    with open(gp_template) as f:
        content = f.readlines()

    content = [
        line.replace(
            '#REPLACE_BY_XLABEL',
            x_axis_label
        )
        for line in content
    ]

    content = [
        line.replace(
            '#REPLACE_BY_XRANGE',
            x_range
        )
        for line in content
    ]

    content = [
        line.replace(
            '#REPLACE_BY_XTICS_LABEL',
            label_xtics
        )
        for line in content
    ]

    content = [line.replace('#REPLACE_BY_TRACE_NAMES', ''.join(["set title " + '"' + ''])) for line in
               content]

    max_mpi = max([max(y_mpi_par), max(y_mpi_comm), max(y_mpi_load),
                      max(y_comm_serial), max(y_comm_transfer)])
    content = [line.replace('#REPLACE_BY_YRANGE', ''
                            .join(['set yrange [0:', str(max_mpi+5), ']'])) for line in content]

    file_path = os.path.join(os.getcwd(), 'modelfactors_mpi_hybrid.gp')
    with open(file_path, 'w') as f:
        f.writelines(content)

    # Add data points to gnuplot file
    with open(file_path, 'a') as f:
        for index in range(0, number_traces):
            line = ' '.join([str(plot_x_values[index]), str(y_mpi_par[index]), '\n'])
            f.write(line)
        f.write('e\n')

        for index in range(0, number_traces):
            line = ' '.join([str(plot_x_values[index]), str(y_mpi_load[index]), '\n'])
            f.write(line)
        f.write('e\n')

        for index in range(0, number_traces):
            line = ' '.join([str(plot_x_values[index]), str(y_mpi_comm[index]), '\n'])
            f.write(line)
        f.write('e\n')
        
        for index in range(0, number_traces):
            if str(y_comm_serial[index]) != 0.0:
                line = ' '.join([str(plot_x_values[index]), str(y_comm_serial[index]), '\n'])
                f.write(line)
        f.write('e\n')

        for index in range(0, number_traces):
            if str(y_comm_transfer[index]) != 0.0:
                line = ' '.join([str(plot_x_values[index]), str(y_comm_transfer[index]), '\n'])
                f.write(line)
        f.write('e\n')

        f.write('\n')
        f.write('pause -1\n')

    print('MPI hybrid metrics plot written to ' + file_path)


def plot_simple_metrics(
        mod_factors,
        trace_list,
        trace_processes,
        trace_mode,
        cmdl_args):
    """
    Generate Gnuplot files for simple-model efficiency,
    communication, and scalability metrics.

    Displayed configuration labels are kept independent from the
    numeric x coordinates. Repeated parallel-unit configurations
    therefore remain individually visible in the plots.
    """

    if cmdl_args.debug:
        print('==DEBUG== Computing projection of model factors.')

    x_axis_label = 'set xlabel "Parallel units"'

    number_traces = len(trace_list)

    # --------------------------------------------------
    # X-axis configuration
    # --------------------------------------------------

    label_xtics_list, plot_x_values = _build_simple_plot_axis(
        trace_list,
        trace_processes,
    )

    # Build Gnuplot xtics once and reuse them in all plots.
    label_xtics = 'set xtics ('

    for label, x_value in zip(
            label_xtics_list,
            plot_x_values):
        label_xtics += (
            '"'
            + label
            + '" '
            + str(x_value)
            + ', '
        )

    label_xtics = (
        label_xtics[:-2]
        + ')'
    )

    # Compute a common x-range for all simple-model plots.
    x_min = min(plot_x_values)
    x_max = max(plot_x_values)

    if x_min == x_max:
        x_margin = 1
    else:
        x_margin = max(
            1,
            int((x_max - x_min) * 0.05)
        )

    x_range = 'set xrange [{}:{}]'.format(
        x_min - x_margin,
        x_max + x_margin
    )

    # --------------------------------------------------
    # Metric arrays
    # --------------------------------------------------

    y_para = numpy.zeros(number_traces)
    y_load = numpy.zeros(number_traces)
    y_comm = numpy.zeros(number_traces)
    y_comp = numpy.zeros(number_traces)
    y_glob = numpy.zeros(number_traces)

    y_comm_serial = numpy.zeros(number_traces)
    y_comm_transfer = numpy.zeros(number_traces)

    y_ipc_scale = numpy.zeros(number_traces)
    y_inst_scale = numpy.zeros(number_traces)
    y_freq_scale = numpy.zeros(number_traces)

    # Convert dictionaries to NumPy arrays.
    for index, trace in enumerate(trace_list):

        y_para[index] = mod_factors['parallel_eff'][trace]
        y_load[index] = mod_factors['load_balance'][trace]
        y_comm[index] = mod_factors['comm_eff'][trace]
        y_comp[index] = mod_factors['comp_scale'][trace]
        y_glob[index] = mod_factors['global_eff'][trace]

        if (
                trace_mode[trace][:5] != 'Burst'
                and trace_mode[trace] != 'Sampling'
        ):
            y_ipc_scale[index] = mod_factors['ipc_scale'][trace]
            y_inst_scale[index] = mod_factors['inst_scale'][trace]
            y_freq_scale[index] = mod_factors['freq_scale'][trace]

        else:
            y_ipc_scale[index] = 0.0
            y_inst_scale[index] = 0.0
            y_freq_scale[index] = 0.0

        if trace_mode[trace] == 'Detailed+MPI':

            if (
                    mod_factors['serial_eff'][trace] != 'Warning!'
                    and mod_factors['serial_eff'][trace] != 'Non-Avail'
            ):
                y_comm_serial[index] = \
                    mod_factors['serial_eff'][trace]
            else:
                y_comm_serial[index] = 0.0

            if (
                    mod_factors['transfer_eff'][trace] != 'Warning!'
                    and mod_factors['serial_eff'][trace] != 'Non-Avail'
            ):
                y_comm_transfer[index] = \
                    mod_factors['transfer_eff'][trace]
            else:
                y_comm_transfer[index] = 0.0

        else:
            y_comm_serial[index] = 0.0
            y_comm_transfer[index] = 0.0

    # --------------------------------------------------
    # Trace names
    # --------------------------------------------------

    title_string = ""

    for index, trace in enumerate(trace_list):
        folder_trace_name = trace.split('/')
        trace_name_to_show = folder_trace_name[
            len(folder_trace_name) - 1
        ]

        title_string += (
            '('
            + str(index + 1)
            + ') '
            + trace_name_to_show
            + "\\n"
        )

    title_string += '"' + " noenhanced"

    # ==================================================
    # GLOBAL EFFICIENCY METRICS
    # ==================================================

    gp_template = os.path.join(
        os.path.dirname(os.path.realpath(__file__)),
        'cfgs',
        'modelfactors-onlydata.gp'
    )

    with open(gp_template) as f:
        content = f.readlines()

    content = [
        line.replace(
            '#REPLACE_BY_XLABEL',
            x_axis_label
        )
        for line in content
    ]

    content = [
        line.replace(
            '#REPLACE_BY_XRANGE',
            x_range
        )
        for line in content
    ]

    content = [
        line.replace(
            '#REPLACE_BY_XTICS_LABEL',
            label_xtics
        )
        for line in content
    ]

    content = [
        line.replace(
            '#REPLACE_BY_TRACE_NAMES',
            'set title ""'
        )
        for line in content
    ]

    max_global = max([
        max(y_para),
        max(y_load),
        max(y_comm),
        max(y_comp),
        max(y_glob)
    ])

    content = [
        line.replace(
            '#REPLACE_BY_YRANGE',
            'set yrange [0:{}]'.format(
                max_global + 5
            )
        )
        for line in content
    ]

    file_path = os.path.join(
        os.getcwd(),
        'modelfactors.gp'
    )

    with open(file_path, 'w') as f:
        f.writelines(content)

    # Add data points.
    with open(file_path, 'a') as f:

        for index in range(number_traces):
            line = ' '.join([
                str(plot_x_values[index]),
                str(y_para[index]),
                '\n'
            ])
            f.write(line)

        f.write('e\n')

        for index in range(number_traces):
            line = ' '.join([
                str(plot_x_values[index]),
                str(y_load[index]),
                '\n'
            ])
            f.write(line)

        f.write('e\n')

        for index in range(number_traces):
            line = ' '.join([
                str(plot_x_values[index]),
                str(y_comm[index]),
                '\n'
            ])
            f.write(line)

        f.write('e\n')

        for index in range(number_traces):
            line = ' '.join([
                str(plot_x_values[index]),
                str(y_comp[index]),
                '\n'
            ])
            f.write(line)

        f.write('e\n')

        for index in range(number_traces):
            line = ' '.join([
                str(plot_x_values[index]),
                str(y_glob[index]),
                '\n'
            ])
            f.write(line)

        f.write('e\n')

        f.write('\n')
        f.write('pause -1\n')

    print(
        'Efficiency metrics plot written to '
        + file_path
    )

    # ==================================================
    # COMMUNICATION METRICS
    # ==================================================

    gp_template = os.path.join(
        os.path.dirname(os.path.realpath(__file__)),
        'cfgs',
        'modelfactors_comm.gp'
    )

    with open(gp_template) as f:
        content = f.readlines()

    content = [
        line.replace(
            '#REPLACE_BY_XLABEL',
            x_axis_label
        )
        for line in content
    ]

    content = [
        line.replace(
            '#REPLACE_BY_XRANGE',
            x_range
        )
        for line in content
    ]

    content = [
        line.replace(
            '#REPLACE_BY_XTICS_LABEL',
            label_xtics
        )
        for line in content
    ]

    content = [
        line.replace(
            '#REPLACE_BY_TRACE_NAMES',
            'set title ""'
        )
        for line in content
    ]

    max_comm = max([
        max(y_comm),
        max(y_comm_serial),
        max(y_comm_transfer)
    ])

    content = [
        line.replace(
            '#REPLACE_BY_YRANGE',
            'set yrange [0:{}]'.format(
                max_comm + 5
            )
        )
        for line in content
    ]

    file_path = os.path.join(
        os.getcwd(),
        'modelfactors_comm.gp'
    )

    with open(file_path, 'w') as f:
        f.writelines(content)

    with open(file_path, 'a') as f:

        for index in range(number_traces):
            line = ' '.join([
                str(plot_x_values[index]),
                str(y_comm[index]),
                '\n'
            ])
            f.write(line)

        f.write('e\n')

        for index in range(number_traces):

            if y_comm_serial[index] != 0.0:
                line = ' '.join([
                    str(plot_x_values[index]),
                    str(y_comm_serial[index]),
                    '\n'
                ])
                f.write(line)

        f.write('e\n')

        for index in range(number_traces):

            if y_comm_transfer[index] != 0.0:
                line = ' '.join([
                    str(plot_x_values[index]),
                    str(y_comm_transfer[index]),
                    '\n'
                ])
                f.write(line)

        f.write('e\n')

        f.write('\n')
        f.write('pause -1\n')

    print(
        'Communication Efficiency plot written to '
        + file_path
    )

    # ==================================================
    # SCALABILITY METRICS
    # ==================================================

    gp_template = os.path.join(
        os.path.dirname(os.path.realpath(__file__)),
        'cfgs',
        'modelfactors_scale.gp'
    )

    with open(gp_template) as f:
        content = f.readlines()

    content = [
        line.replace(
            '#REPLACE_BY_XLABEL',
            x_axis_label
        )
        for line in content
    ]

    content = [
        line.replace(
            '#REPLACE_BY_XRANGE',
            x_range
        )
        for line in content
    ]

    content = [
        line.replace(
            '#REPLACE_BY_XTICS_LABEL',
            label_xtics
        )
        for line in content
    ]

    content = [
        line.replace(
            '#REPLACE_BY_TRACE_NAMES',
            'set title ""'
        )
        for line in content
    ]

    max_comp = max([
        max(y_comp),
        max(y_ipc_scale),
        max(y_inst_scale),
        max(y_freq_scale)
    ])

    content = [
        line.replace(
            '#REPLACE_BY_YRANGE',
            'set yrange [0:{}]'.format(
                max_comp + 5
            )
        )
        for line in content
    ]

    file_path = os.path.join(
        os.getcwd(),
        'modelfactors_scale.gp'
    )

    with open(file_path, 'w') as f:
        f.writelines(content)

    with open(file_path, 'a') as f:

        for index in range(number_traces):
            line = ' '.join([
                str(plot_x_values[index]),
                str(y_comp[index]),
                '\n'
            ])
            f.write(line)

        f.write('e\n')

        for index in range(number_traces):
            line = ' '.join([
                str(plot_x_values[index]),
                str(y_ipc_scale[index]),
                '\n'
            ])
            f.write(line)

        f.write('e\n')

        for index in range(number_traces):
            line = ' '.join([
                str(plot_x_values[index]),
                str(y_inst_scale[index]),
                '\n'
            ])
            f.write(line)

        f.write('e\n')

        for index in range(number_traces):
            line = ' '.join([
                str(plot_x_values[index]),
                str(y_freq_scale[index]),
                '\n'
            ])
            f.write(line)

        f.write('e\n')

        f.write('\n')
        f.write('pause -1\n')

    print(
        'Scalability metrics plot written to '
        + file_path
    )