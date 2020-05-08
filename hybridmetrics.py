#!/usr/bin/env python3

"""Functions to compute the model metrics."""

from __future__ import print_function, division
import sys


from rawdata import *
from tracemetadata import get_trace_mode
from collections import OrderedDict
from tracemetadata import get_tasks_threads

try:
    import numpy as np
except ImportError:
    print('==ERROR== Could not import NumPy. Please make sure to install a current version.')


try:
    import pandas as pd
except ImportError:
    print('==ERROR== Could not import pandas. Please make sure to install a current version for plotting.')
try:
    import seaborn as sns
except ImportError:
    print('==ERROR== Could not import seaborn. Please make sure to install a current version for plotting.')

try:
    import matplotlib.pyplot as plt
except ImportError:
     print('==ERROR== Could not import matplotlib. Please make sure to install a current version for plotting.')


# Contains all model factor entries with a printable name.
# This is used to generate and print all model factors, so, if an entry is added,
# it should be added here, too.

other_metrics_doc = OrderedDict([('elapsed_time', 'Elapsed time (sec)'),
                               ('efficiency', 'Efficiency (%)'),
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
                               ('serial_eff', '         -- Serialization efficiency'),
                               ('transfer_eff', '         -- Transfer efficiency'),
                               ('omp_parallel_eff', '   -- OMP Parallel efficiency'),
                               ('omp_load_balance', '      -- OMP Load balance'),
                               ('omp_comm_eff', '      -- OMP Communication efficiency')])


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
    string. The hybrid_factors dictionary has the format: [mod factor key][trace].
    """
    global mod_hybrid_factors_doc
    hybrid_factors = {}
    for key in mod_hybrid_factors_doc:
        trace_dict = {}
        for trace_name in trace_list:
            trace_dict[trace_name] = 0.0
        hybrid_factors[key] = trace_dict

    return hybrid_factors


def create_other_metrics(trace_list):
    """Creates 2D dictionary of the other metrics and initializes with an empty
    string. The other_metrics dictionary has the format: [mod factor key][trace].
    """
    global other_metrics_doc
    other_metrics = {}
    for key in other_metrics_doc:
        trace_dict = {}
        for trace_name in trace_list:
            trace_dict[trace_name] = 0.0
        other_metrics[key] = trace_dict

    return other_metrics


def get_scaling_type(raw_data, trace_list, trace_processes, cmdl_args):
    """Guess the scaling type (weak/strong) based on the useful instructions.
    Computes the normalized instruction ratio for all measurements, whereas the
    normalized instruction ratio is (instructions ratio / process ratio) with
    the smallest run as reference. For exact weak scaling the normalized ratio
    should be exactly 1 and for exact strong scaling it should be close to zero
    with an upper bound of 0.5. The eps value defines the threshold to be
    considered weak scaling and should give enough buffer to safely handle
    non-ideal scaling.
    """
    eps = 0.9
    normalized_inst_ratio = 0

    # Check if there is only one trace.
    if len(trace_list) == 1:
        return 'strong'

    for trace in trace_list:
        try:  # except NaN
            inst_ratio = float(raw_data['useful_ins'][trace]) / float(raw_data['useful_ins'][trace_list[0]])
        except:
            inst_ratio = 0.0
        try:  # except NaN
            proc_ratio = float(trace_processes[trace]) / float(trace_processes[trace_list[0]])
        except:
            proc_ratio = 'NaN'

        normalized_inst_ratio += inst_ratio / proc_ratio

    # Get the average inst increase. Ignore ratio of first trace 1.0)
    normalized_inst_ratio = (normalized_inst_ratio - 1) / (len(trace_list) - 1)

    scaling_computed = ''

    if normalized_inst_ratio > eps:
        scaling_computed = 'weak'
    else:
        scaling_computed = 'strong'

    if cmdl_args.scaling == 'auto':
        if cmdl_args.debug:
            print('==DEBUG== Detected ' + scaling_computed + ' scaling.')
            print('')
        return scaling_computed

    if cmdl_args.scaling == 'weak':
        if scaling_computed == 'strong':
            print('==Warning== Scaling set to weak scaling but detected strong scaling.')
            print('')
        return 'weak'

    if cmdl_args.scaling == 'strong':
        if scaling_computed == 'weak':
            print('==Warning== Scaling set to strong scaling but detected weak scaling.')
            print('')
        return 'strong'

    print('==Error== reached undefined control flow state.')
    sys.exit(1)


def compute_model_factors(raw_data, trace_list, trace_processes, trace_mode,list_mpi_procs_count, cmdl_args):
    """Computes the model factors from the gathered raw data and returns the
    according dictionary of model factors."""
    mod_factors = create_mod_factors(trace_list)
    hybrid_factors = create_hybrid_mod_factors(trace_list)
    other_metrics = create_other_metrics(trace_list)
    mod_factors_scale_plus_io = create_mod_factors_scale_io(trace_list)

    # Guess the weak or strong scaling
    scaling = get_scaling_type(raw_data, trace_list, trace_processes, cmdl_args)

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
        try:  # except NaN
            other_metrics['io_mpiio'][trace] = raw_data['mpiio_tot'][trace] \
                                               / (raw_data['runtime'][trace] * trace_processes[trace]) * 100.0
        except:
            other_metrics['io_mpiio'][trace] = 0.0

        try:  # except NaN
            other_metrics['io_posix'][trace] = raw_data['io_tot'][trace] \
                                               / (raw_data['runtime'][trace] * trace_processes[trace]) * 100.0
        except:
            other_metrics['io_posix'][trace] = 0.0
        try:  # except NaN
            io_total = raw_data['mpiio_tot'][trace] + raw_data['flushing_tot'][trace] + raw_data['io_tot'][trace]
            other_metrics['io_eff'][trace] = raw_data['useful_tot'][trace] \
                                             / (raw_data['useful_tot'][trace] + io_total) * 100.0
        except:
            other_metrics['io_eff'][trace] = 0.0

        # Basic efficiency factors
        try:  # except NaN
            if other_metrics['io_posix'][trace] >= 5.0 or other_metrics['flushing'][trace] >= 10.0:
                mod_factors['load_balance'][trace] = raw_data['useful_plus_io_avg'][trace] \
                                                     / raw_data['useful_plus_io_max'][trace] * 100.0
            else:
                mod_factors['load_balance'][trace] = raw_data['useful_avg'][trace] \
                                                 / raw_data['useful_max'][trace] * 100.0
        except:
            mod_factors['load_balance'][trace] = 'NaN'

        try:  # except NaN
            if other_metrics['io_posix'][trace] >= 5.0 or other_metrics['flushing'][trace] >= 10.0:
                mod_factors['comm_eff'][trace] = raw_data['useful_plus_io_max'][trace] \
                                                 / raw_data['runtime'][trace] * 100.0
            else:
                mod_factors['comm_eff'][trace] = raw_data['useful_max'][trace] \
                                                     / raw_data['runtime'][trace] * 100.0
        except:
            mod_factors['comm_eff'][trace] = 'NaN'

        try:  # except NaN
            if other_metrics['io_posix'][trace] >= 5.0 or other_metrics['flushing'][trace] >= 10.0:
                mod_factors['parallel_eff'][trace] = raw_data['useful_plus_io_avg'][trace] \
                                                     / raw_data['runtime'][trace] * 100.0
            else:
                mod_factors['parallel_eff'][trace] = mod_factors['load_balance'][trace] \
                                                     * mod_factors['comm_eff'][trace] / 100.0
        except:
            mod_factors['parallel_eff'][trace] = 'NaN'

        try:  # except NaN
            if scaling == 'strong':
                mod_factors['comp_scale'][trace] = raw_data['useful_tot'][trace_list[0]] \
                                                   / raw_data['useful_tot'][trace] * 100.0
            else:
                mod_factors['comp_scale'][trace] = raw_data['useful_tot'][trace_list[0]] \
                                                   / raw_data['useful_tot'][trace] * proc_ratio * 100.0
        except:
            mod_factors['comp_scale'][trace] = 'NaN'

        # Computation Scale + Serial I/O
        try:  # except NaN
            if other_metrics['io_posix'][trace] > 0.0 or other_metrics['flushing'][trace] > 0.0:
                io_serial_0 = raw_data['io_tot'][trace_list[0]] + raw_data['flushing_tot'][trace_list[0]]
                io_serial_n = raw_data['io_tot'][trace] + raw_data['flushing_tot'][trace]
                if scaling == 'strong':
                    mod_factors_scale_plus_io['comp_scale'][trace] = (raw_data['useful_tot'][trace_list[0]]
                                                                      + io_serial_0) / (raw_data['useful_tot'][trace]
                                                                                        + io_serial_n) * 100.0
                else:
                    mod_factors_scale_plus_io['comp_scale'][trace] = (raw_data['useful_tot'][trace_list[0]]
                                                                      + io_serial_0) \
                                                                     / (raw_data['useful_tot'][trace] + io_serial_n) \
                                                                     * proc_ratio * 100.0
            else:
                mod_factors_scale_plus_io['comp_scale'][trace] = mod_factors['comp_scale'][trace]
        except:
            mod_factors_scale_plus_io['comp_scale'][trace] = 'NaN'


        try:  # except NaN
            mod_factors['global_eff'][trace] = mod_factors['parallel_eff'][trace] \
                                               * mod_factors['comp_scale'][trace] / 100.0
        except:
            mod_factors['global_eff'][trace] = 'NaN'

        # Hybrid metrics calculation
        # ------->  MPI metrics
        try:  # except NaN
            hybrid_factors['mpi_load_balance'][trace] = raw_data['outsidempi_avg'][trace] \
                                                 / raw_data['outsidempi_max'][trace] * 100.0
        except:
            hybrid_factors['mpi_load_balance'][trace] = 'NaN'

        try:  # except NaN
            hybrid_factors['mpi_comm_eff'][trace] = raw_data['outsidempi_max'][trace] \
                                                     / raw_data['runtime'][trace] * 100.0
        except:
            hybrid_factors['mpi_comm_eff'][trace] = 'NaN'

        # ------------> BEGIN MPI communication sub-metrics
        try:  # except NaN
            hybrid_factors['serial_eff'][trace] = raw_data['outsidempi_dim'][trace] \
                                               / raw_data['runtime_dim'][trace] * 100.0
        except:
            if trace_mode[trace] == 'Detailed+MPI' or trace_mode[trace] == 'Detailed+MPI+OpenMP':
                hybrid_factors['serial_eff'][trace] = 'NaN'
            else:
                hybrid_factors['serial_eff'][trace] = 'Non-Avail'

        try:  # except NaN
            hybrid_factors['transfer_eff'][trace] = hybrid_factors['mpi_comm_eff'][trace] \
                                                    / hybrid_factors['serial_eff'][trace] * 100.0

        except:
            if trace_mode[trace] == 'Detailed+MPI' or trace_mode[trace] == 'Detailed+MPI+OpenMP':
                hybrid_factors['transfer_eff'][trace] = 'NaN'
            else:
                hybrid_factors['transfer_eff'][trace] = 'Non-Avail'
        # --------------> END MPI communication sub-metrics
        try:  # except NaN
            if raw_data['outsidempi_tot'][trace] == raw_data['outsidempi_tot_diff'][trace]:
                hybrid_factors['mpi_parallel_eff'][trace] = raw_data['outsidempi_tot'][trace] \
                                                    / (raw_data['runtime'][trace] * list_mpi_procs_count[trace]) * 100.0
            else:
                hybrid_factors['mpi_parallel_eff'][trace] = raw_data['outsidempi_tot_diff'][trace] \
                                                          / (raw_data['runtime'][trace] * trace_processes[trace] ) * 100.0
        except:
            hybrid_factors['mpi_parallel_eff'][trace] = 'NaN'

        # ------->  Metrics for the second parallel paradigm
        try:  # except NaN
            hybrid_factors['omp_comm_eff'][trace] = mod_factors['comm_eff'][trace] \
                                                     / hybrid_factors['mpi_comm_eff'][trace] * 100.0
        except:
            hybrid_factors['omp_comm_eff'][trace] = 'NaN'

        try:  # except NaN
            hybrid_factors['omp_load_balance'][trace] = mod_factors['load_balance'][trace] \
                                                 / hybrid_factors['mpi_load_balance'][trace] * 100.0
        except:
            hybrid_factors['omp_load_balance'][trace] = 'NaN'

        try:  # except NaN
            hybrid_factors['omp_parallel_eff'][trace] = mod_factors['parallel_eff'][trace] \
                                                     / hybrid_factors['mpi_parallel_eff'][trace] * 100.0
        except:
            hybrid_factors['omp_parallel_eff'][trace] = 'NaN'

        # ------->  Global Hybrid Metric
        try:  # except NaN
            hybrid_factors['hybrid_eff'][trace] = hybrid_factors['mpi_parallel_eff'][trace] \
                                               * hybrid_factors['omp_parallel_eff'][trace] / 100.0
        except:
            hybrid_factors['hybrid_eff'][trace] = 'NaN'

        # Basic scalability factors
        try:  # except NaN
            other_metrics['ipc'][trace] = float(raw_data['useful_ins'][trace]) \
                                        / float(raw_data['useful_cyc'][trace])
        except:
            other_metrics['ipc'][trace] = 'NaN'
        try:  # except NaN
            mod_factors['ipc_scale'][trace] = other_metrics['ipc'][trace] \
                                              / other_metrics['ipc'][trace_list[0]] * 100.0
        except:
            mod_factors['ipc_scale'][trace] = 'NaN'

        # IPC scale + Serial I/O
        try:  # except NaN
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
                mod_factors_scale_plus_io['ipc_scale'][trace] = mod_factors['ipc_scale'][trace]
        except:
            mod_factors_scale_plus_io['ipc_scale'][trace] = 'NaN'

        try:  # except NaN
            other_metrics['freq'][trace] = float(raw_data['useful_cyc'][trace]) \
                                         / float(raw_data['useful_tot'][trace]) / 1000
        except:
            other_metrics['freq'][trace] = 'NaN'
        try:  # except NaN
            mod_factors['freq_scale'][trace] = other_metrics['freq'][trace] \
                                               / other_metrics['freq'][trace_list[0]] * 100.0
        except:
            mod_factors['freq_scale'][trace] = 'NaN'

        # freq scale + Serial I/O
        try:  # except NaN
            if other_metrics['io_posix'][trace] > 0.0 or other_metrics['flushing'][trace] > 0.0:
                freq_serial_io_0 = (float(raw_data['useful_cyc'][trace_list[0]])
                                    + float(raw_data['io_cyc'][trace_list[0]])
                                    + float(raw_data['flushing_cyc'][trace_list[0]])) \
                                   / (float(raw_data['useful_tot'][trace_list[0]])
                                      + float(raw_data['io_tot'][trace_list[0]])
                                      + float(raw_data['flushing_tot'][trace_list[0]])) / 1000

                freq_serial_io_n = (float(raw_data['useful_cyc'][trace]) + float(raw_data['io_cyc'][trace])
                                    + float(raw_data['flushing_cyc'][trace])) \
                                   / (float(raw_data['useful_tot'][trace])
                                      + float(raw_data['io_tot'][trace])
                                      + float(raw_data['flushing_tot'][trace])) / 1000
                mod_factors_scale_plus_io['freq_scale'][trace] = freq_serial_io_n / freq_serial_io_0 * 100.0
            else:
                mod_factors_scale_plus_io['freq_scale'][trace] = mod_factors['freq_scale'][trace]
        except:
            mod_factors_scale_plus_io['freq_scale'][trace] = 'NaN'

        try:  # except NaN
            if scaling == 'strong':
                mod_factors['inst_scale'][trace] = float(raw_data['useful_ins'][trace_list[0]]) \
                                                   / float(raw_data['useful_ins'][trace]) * 100.0
            else:
                mod_factors['inst_scale'][trace] = float(raw_data['useful_ins'][trace_list[0]]) \
                                                   / float(raw_data['useful_ins'][trace]) * proc_ratio * 100.0
        except:
            mod_factors['inst_scale'][trace] = 'NaN'

        # ins scale + Serial I/O
        try:  # except NaN
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
                    mod_factors_scale_plus_io['inst_scale'][trace] = useful_ins_plus_io_0 / useful_ins_plus_io_n \
                                                     * proc_ratio * 100.0
            else:
                mod_factors_scale_plus_io['inst_scale'][trace] = mod_factors['inst_scale'][trace]
        except:
            mod_factors_scale_plus_io['inst_scale'][trace] = 'NaN'

        try:  # except NaN
            if scaling == 'strong':
                other_metrics['speedup'][trace] = raw_data['runtime'][trace_list[0]] \
                                                / raw_data['runtime'][trace]
            else:
                other_metrics['speedup'][trace] = raw_data['runtime'][trace_list[0]] \
                                                / raw_data['runtime'][trace] * proc_ratio
        except:
            other_metrics['speedup'][trace] = 'NaN'

        try:  # except NaN
            other_metrics['elapsed_time'][trace] = raw_data['runtime'][trace] * 0.000001
        except:
            other_metrics['elapsed_time'][trace] = 'NaN'

        try:  # except NaN
            other_metrics['efficiency'][trace] = mod_factors['global_eff'][trace]
        except:
            other_metrics['efficiency'][trace] = 'NaN'

    return mod_factors, mod_factors_scale_plus_io, hybrid_factors, other_metrics


def print_mod_factors_table(mod_factors, other_metrics, mod_factors_scale_plus_io, hybrid_factors, trace_list, trace_processes):
    """Prints the model factors table in human readable form on stdout."""
    global mod_factors_doc, mod_hybrid_factors_doc

    warning_io = []
    warning_flush = []
    warning_flush_wrong = []
    for trace in trace_list:
        if 10.0 <= other_metrics['flushing'][trace] < 15.0:
            warning_flush.append(1)
        elif other_metrics['flushing'][trace] >= 15.0:
            warning_flush_wrong.append(1)
        if other_metrics['io_posix'][trace] >= 5.0:
            warning_io.append(1)
    if len(warning_flush_wrong) > 0:
        print("WARNING! Flushing in a trace is too high. Disabling standard output metrics...")
        print("         Flushing is an overhead due to the tracer, please review your trace.")
        print('')
        return

    # Update the hybrid parallelism mode
    trace_mode_doc = get_trace_mode(trace_list[0])
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

    line = ''.rjust(longest_name)
    if len(trace_list) == 1:
        limit_min = trace_processes[trace_list[0]]
        limit_max = trace_processes[trace_list[0]]
    else:
        limit_min = trace_processes[trace_list[0]]
        limit_max = trace_processes[trace_list[len(trace_list)-1]]

    # To control same number of processes for the header on plots and table
    same_procs = True
    procs_trace_prev = trace_processes[trace_list[0]]
    tasks_trace_prev, threads_trace_prev = get_tasks_threads(trace_list[0])
    for index, trace in enumerate(trace_list):
        tasks, threads = get_tasks_threads(trace)
        if procs_trace_prev == trace_processes[trace] and tasks_trace_prev == tasks \
                and threads_trace_prev == threads:
            same_procs *= True
        else:
            same_procs *= False

    for index, trace in enumerate(trace_list):
        line += ' | '
        tasks, threads = get_tasks_threads(trace)
        if limit_min == limit_max and same_procs and len(trace_list) > 1:
            line += (str(trace_processes[trace]) + '[' + str(index+1) + ']').rjust(10)
        else:
            line += (str(trace_processes[trace]) + '(' + str(tasks) + 'x' + str(threads) + ')').rjust(10)

    print(''.ljust(len(line), '='))
    print(line)
    line_procs_factors = line

    print(''.ljust(len(line), '='))

    for mod_key in mod_factors_doc:
        line = mod_factors_doc[mod_key].ljust(longest_name)
        for trace in trace_list:
            line += ' | '
            try:  # except NaN
                line += ('{0:.2f}%'.format(mod_factors[mod_key][trace])).rjust(10)
            except ValueError:
                line += ('{}'.format(mod_factors[mod_key][trace])).rjust(10)
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
                try:  # except NaN
                    line += ('{0:.2f}%'.format(mod_factors_scale_plus_io[mod_key][trace])).rjust(10)
                except ValueError:
                    line += ('{}'.format(mod_factors_scale_plus_io[mod_key][trace])).rjust(10)
            print(line)
        print(''.ljust(len(line_procs_factors), '='))
    else:
        print(''.ljust(len(line_procs_factors), '-'))
        
    for mod_key in mod_hybrid_factors_doc:
        line = mod_hybrid_factors_doc[mod_key].ljust(longest_name)
        for trace in trace_list:
            line += ' | '
            try:  # except NaN
                line += ('{0:.2f}%'.format(hybrid_factors[mod_key][trace])).rjust(10)
            except ValueError:
                line += ('{}'.format(hybrid_factors[mod_key][trace])).rjust(10)
        print(line)

    print(''.ljust(len(line_procs_factors), '='))
    print('')


def print_other_metrics_table(other_metrics, trace_list, trace_processes):
    """Prints the other metrics table in human readable form on stdout."""
    global other_metrics_doc

    print('Overview of the Efficiency, Speedup, IPC and Frequency:')

    longest_name = len(sorted(other_metrics_doc.values(), key=len)[-1])

    line = ''.rjust(longest_name)
    if len(trace_list) == 1:
        limit_min = trace_processes[trace_list[0]]
        limit_max = trace_processes[trace_list[0]]
    else:
        limit_min = trace_processes[trace_list[0]]
        limit_max = trace_processes[trace_list[len(trace_list)-1]]

    # To control same number of processes for the header on plots and table
    same_procs = True
    procs_trace_prev = trace_processes[trace_list[0]]
    tasks_trace_prev, threads_trace_prev = get_tasks_threads(trace_list[0])
    for index, trace in enumerate(trace_list):
        tasks, threads = get_tasks_threads(trace)
        if procs_trace_prev == trace_processes[trace] and tasks_trace_prev == tasks \
                and threads_trace_prev == threads:
            same_procs *= True
        else:
            same_procs *= False

    for index, trace in enumerate(trace_list):
        line += ' | '
        tasks, threads = get_tasks_threads(trace)
        if limit_min == limit_max and same_procs and len(trace_list) > 1:
            line += (str(trace_processes[trace]) + '[' + str(index+1) + ']').rjust(10)
        else:
            line += (str(trace_processes[trace]) + '(' + str(tasks) + 'x' + str(threads) + ')').rjust(10)

    print(''.ljust(len(line), '-'))
    print(line)
    line_head = line
    print(''.ljust(len(line), '-'))

    for mod_key in other_metrics_doc:
        line = other_metrics_doc[mod_key].ljust(longest_name)
        if mod_key in ['speedup', 'ipc', 'freq', 'elapsed_time', 'efficiency']:
            for trace in trace_list:
                line += ' | '
                try:  # except NaN
                    line += ('{0:.2f}'.format(other_metrics[mod_key][trace])).rjust(10)
                except ValueError:
                    line += ('{}'.format(other_metrics[mod_key][trace])).rjust(10)
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
                        line += ('{0:.2f}%'.format(other_metrics[mod_key][trace])).rjust(10)
                    except ValueError:
                        line += ('{}'.format(other_metrics[mod_key][trace])).rjust(10)
                if len(warning_flush) > 0:
                    print(line)
                    print(''.ljust(len(line_head), '-'))
            elif mod_key in ['io_mpiio','io_posix','io_eff']:
                for trace in trace_list:
                    line += ' | '
                    try:  # except NaN
                        line += ('{0:.2f}%'.format(other_metrics[mod_key][trace])).rjust(10)
                    except ValueError:
                        line += ('{}'.format(other_metrics[mod_key][trace])).rjust(10)
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


def print_efficiency_table(mod_factors, hybrid_factors, trace_list, trace_processes):
    """Prints the model factors table in human readable form on stdout."""
    global mod_factors_doc, mod_hybrid_factors_doc

    delimiter = ','
    # To control same number of processes for the header on plots and table
    same_procs = True
    procs_trace_prev = trace_processes[trace_list[0]]
    tasks_trace_prev, threads_trace_prev = get_tasks_threads(trace_list[0])
    for index, trace in enumerate(trace_list):
        tasks, threads = get_tasks_threads(trace)
        if procs_trace_prev == trace_processes[trace] and tasks_trace_prev == tasks \
                and threads_trace_prev == threads:
            same_procs *= True
        else:
            same_procs *= False

    if len(trace_list) == 1:
        limit_min = trace_processes[trace_list[0]]
        limit_max = trace_processes[trace_list[0]]
    else:
        limit_min = trace_processes[trace_list[0]]
        limit_max = trace_processes[trace_list[len(trace_list) - 1]]

    file_path = os.path.join(os.getcwd(), 'efficiency_table-global.csv')
    with open(file_path, 'w') as output:
        line = '\"Number of processes\"'
        for index, trace in enumerate(trace_list):
            line += delimiter
            tasks, threads = get_tasks_threads(trace)
            if limit_min == limit_max and same_procs and len(trace_list) > 1:
                line += str(trace_processes[trace]) + '[' + str(index+1) + ']'
            else:
                line += str(trace_processes[trace]) + '(' + str(tasks) + 'x' + str(threads) + ')'
        output.write(line + '\n')

        for mod_key in mod_factors_doc:
            if mod_key not in ['speedup', 'ipc', 'freq', 'elapsed_time', 'efficiency', 'flushing', 'io_mpiio', 'io_posix']:
                if mod_key in ['parallel_eff', 'comp_scale']:
                    line = "\"" + mod_factors_doc[mod_key].replace('  ', '', 2) + "\""
                elif mod_key in ['load_balance', 'comm_eff','ipc_scale', 'inst_scale','freq_scale']:
                    line = "\"" + mod_factors_doc[mod_key].replace('     ', '', 2) + "\""
                else:
                    line = "\"" + mod_factors_doc[mod_key] + "\""
                for trace in trace_list:
                    line += delimiter
                    try:  # except NaN
                        if mod_factors[mod_key][trace] == "Non-Avail":
                            line += '0.00'
                        else:
                            line += '{0:.2f}'.format(mod_factors[mod_key][trace])
                    except ValueError:
                        line += '{}'.format(mod_factors[mod_key][trace])
                output.write(line + '\n')

        # Create Gnuplot file for efficiency plot
        gp_template = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'cfgs', 'efficiency_table-global.gp')
        content = []

        with open(gp_template) as f:
            content = f.readlines()

        limit_procs = 500 + len(trace_list) * 65
        ## print(limit_procs)

        # Replace xrange
        content = [line.replace('#REPLACE_BY_SIZE', ''.join(['set terminal pngcairo enhanced dashed crop size ',
                                                             str(limit_procs), ',460 font "Latin Modern Roman,14"']))
                   for line in content]

        file_path = os.path.join(os.getcwd(), 'efficiency_table_global.gp')
        with open(file_path, 'w') as f:
            f.writelines(content)
        # print('======== Plot (gnuplot File): EFFICIENCY Table ========')
        print('Global Efficiency Table written to ' + file_path[:len(file_path) - 3] + '.png')
        # print('')

    delimiter = ','
    file_path = os.path.join(os.getcwd(), 'efficiency_table-hybrid.csv')
    with open(file_path, 'w') as output:
        line = '\"Number of processes\"'
        for index, trace in enumerate(trace_list):
            line += delimiter
            tasks, threads = get_tasks_threads(trace)
            if limit_min == limit_max and same_procs and len(trace_list) > 1:
                line += str(trace_processes[trace]) + '[' + str(index+1) + ']'
            else:
                line += str(trace_processes[trace]) + '(' + str(tasks) + 'x' + str(threads) + ')'
        output.write(line + '\n')

        for mod_key in mod_hybrid_factors_doc:
            if mod_key in ['mpi_parallel_eff', 'omp_parallel_eff']:
                line = "\"" + mod_hybrid_factors_doc[mod_key].replace('     ', '', 2) + "\""
            elif mod_key in ['mpi_load_balance', 'mpi_comm_eff','omp_load_balance', 'omp_comm_eff']:
                line = "\"" + mod_hybrid_factors_doc[mod_key].replace('       ', '', 2) + "\""
            elif mod_key in ['serial_eff', 'transfer_eff']:
                line = "\"" + mod_hybrid_factors_doc[mod_key].replace('         ', '          ', 2) + "\""
            else:
                line = "\"" + mod_hybrid_factors_doc[mod_key] + "\""
            for trace in trace_list:
                line += delimiter
                try:  # except NaN
                    if hybrid_factors[mod_key][trace] == "Non-Avail":
                        line += '0.00'
                    else:
                        line += '{0:.2f}'.format(hybrid_factors[mod_key][trace])
                except ValueError:
                    line += '{}'.format(hybrid_factors[mod_key][trace])
            output.write(line + '\n')

        # Create Gnuplot file for efficiency plot
        gp_template = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'cfgs', 'efficiency_table-hybrid.gp')
        content = []

        with open(gp_template) as f:
            content = f.readlines()

        limit_procs = 510 + len(trace_list) * 80

        # Replace xrange
        content = [line.replace('#REPLACE_BY_SIZE', ''.join(['set terminal pngcairo enhanced dashed crop size ',
                                                             str(limit_procs), ',460 font "Latin Modern Roman,14"']))
                   for line in content]

        file_path = os.path.join(os.getcwd(), 'efficiency_table-hybrid.gp')
        with open(file_path, 'w') as f:
            f.writelines(content)
        # print('======== Plot (gnuplot File): EFFICIENCY Table ========')
        print('Hybrid Efficiency Table written to ' + file_path[:len(file_path) - 3] + '.png')
        #print('')


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


def plots_efficiency_table_matplot(trace_list, trace_processes, cmdl_args):
    # Plotting using python
    # For plotting using python, read the csv file

    file_path = os.path.join(os.getcwd(), 'efficiency_table-hybrid.csv')
    df = pd.read_csv(file_path)
    metrics = df['Number of processes'].tolist()

    traces_procs = list(df.keys())[1:]

    # To control same number of processes for the header on plots and table
    same_procs = True
    procs_trace_prev = trace_processes[trace_list[0]]
    tasks_trace_prev, threads_trace_prev = get_tasks_threads(trace_list[0])
    for index, trace in enumerate(trace_list):
        tasks, threads = get_tasks_threads(trace)
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
        tasks, threads = get_tasks_threads(trace)
        if int(limit) == int(limit_min) and same_procs:
            s_xtics = str(trace_processes[trace]) + '[' + str(index + 1) + ']'
        elif int(limit) == int(limit_min) and not same_procs:
            s_xtics = str(trace_processes[trace]) + '(' + str(tasks) + 'x' + str(threads) + ')'
        else:
            s_xtics = str(trace_processes[trace])
        if s_xtics in label_xtics:
            s_xtics += '[' + str(index + 1) + ']'
        label_xtics.append(s_xtics)
    ##### End xticks

    list_data = []
    for index, rows in df.iterrows():
        list_data.append(list(rows)[1:])

    list_np = np.array(list_data)

    idx = metrics
    cols = label_xtics
    # cols = traces_procs
    df = pd.DataFrame(list_np, index=idx, columns=cols)

    # min for 1 trace is x=3 for the (x,y) in figsize
    size_figure_y = len(idx) * 0.40
    size_figure_x = len(cols) * 1.35
    plt.figure(figsize=(size_figure_x, size_figure_y))

    ax = sns.heatmap(df, cmap='RdYlGn', linewidths=0.05, annot=True, vmin=0, vmax=100, center=75, \
                     fmt='.2f', annot_kws={"size": 10}, cbar_kws={'label': 'Percentage(%)'})
    ## to align ylabels to left
    plt.yticks(rotation=0, ha='left')

    ax.xaxis.tick_top()
    # to adjust metrics
    len_pad = 0
    for metric in metrics:
        if len(metric) > len_pad:
            len_pad = len(metric)

    ax.yaxis.set_tick_params(pad=len_pad + 164)

    plt.savefig('efficiency_table-hybrid-matplot.png', bbox_inches='tight')

    # General Metrics plot

    file_path = os.path.join(os.getcwd(), 'efficiency_table-global.csv')
    df = pd.read_csv(file_path)
    metrics = df['Number of processes'].tolist()

    traces_procs = list(df.keys())[1:]

    list_data = []
    for index, rows in df.iterrows():
        list_data.append(list(rows)[1:])

    list_np = np.array(list_data)

    idx = metrics
    cols = label_xtics
    # cols = traces_procs
    df = pd.DataFrame(list_np, index=idx, columns=cols)

    # min for 1 traces is x=3 for the (x,y) in figsize
    size_figure_y = len(idx) * 0.40
    size_figure_x = len(cols) * 1.35
    plt.figure(figsize=(size_figure_x, size_figure_y))

    ax = sns.heatmap(df, cmap='RdYlGn', linewidths=0.05, annot=True, vmin=0, vmax=100, center=75, \
                     fmt='.2f', annot_kws={"size": 10}, cbar_kws={'label': 'Percentage(%)'})
    ## to align ylabels to left
    plt.yticks(rotation=0, ha='left')
    ax.xaxis.tick_top()
    # to adjust metrics
    len_pad = 0
    for metric in metrics:
        if len(metric) > len_pad:
            len_pad = len(metric)

    ax.yaxis.set_tick_params(pad=len_pad + 140)

    plt.savefig('efficiency_table-global-matplot.png', bbox_inches='tight')


def plots_modelfactors_matplot(trace_list, trace_processes, cmdl_args):
    # Plotting using python
    # For plotting using python, read the csv file
    file_path = os.path.join(os.getcwd(), 'modelfactors.csv')
    df = pd.read_csv(file_path, sep=';')

    traces_procs = list(df.keys())[1:]

    list_data = []
    for index, rows in df.iterrows():
        list_data.append(list(rows)[1:])

    # To control same number of processes for the header on plots and table
    same_procs = True
    procs_trace_prev = trace_processes[trace_list[0]]
    tasks_trace_prev, threads_trace_prev = get_tasks_threads(trace_list[0])
    for index, trace in enumerate(trace_list):
        tasks, threads = get_tasks_threads(trace)
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
        tasks, threads = get_tasks_threads(trace)
        if int(limit) == int(limit_min) and same_procs:
            s_xtics = str(trace_processes[trace]) + '[' + str(index + 1) + ']'
        elif int(limit) == int(limit_min) and not same_procs:
            s_xtics = str(trace_processes[trace]) + '(' + str(tasks) + 'x' + str(threads) + ')'
        else:
            s_xtics = str(trace_processes[trace])
        if s_xtics in label_xtics:
            s_xtics += '[' + str(index + 1) + ']'
        label_xtics.append(s_xtics)

    ## Global Metrics
    plt.figure()
    max_global = max([max(list_data[0]), max(list_data[1]), max(list_data[2]),
                      max(list_data[3]), max(list_data[4])])
    plt.plot(traces_procs, list_data[0], 'o-', color='black', label='Global Efficiency')
    plt.plot(traces_procs, list_data[1], 's-.', color='magenta', label='Parallel Efficiency')
    plt.plot(traces_procs, list_data[2], 's-.', color='red', label='Load Balance')
    plt.plot(traces_procs, list_data[3], 's-.', color='green', label='Communication efficiency')
    plt.plot(traces_procs, list_data[4], 'v--', color='blue', label='Computation scalability')
    plt.xlabel("Number of Processes")
    plt.ylabel("Efficiency (%)")
    plt.xticks(tuple(traces_procs), tuple(label_xtics))
    if max_global < 100:
        max_global = 100

    plt.ylim(0, max_global+5)
    plt.legend()
    plt.savefig('modelfactors-global-matplot.png', bbox_inches='tight')

    ## Scale Metrics
    plt.figure()
    max_scale = max([max(list_data[4]), max(list_data[5]), max(list_data[6]), max(list_data[7])])
    plt.plot(traces_procs, list_data[4], label='Computation scalability',
             color='blue', linestyle='dashed', marker='v', markerfacecolor='blue')
    plt.plot(traces_procs, list_data[5], 'v--', color='skyblue', label='IPC scalability')
    plt.plot(traces_procs, list_data[6], 'v--', color='gray', label='Instruction scalability')
    plt.plot(traces_procs, list_data[7], 'v--', color='darkviolet', label='Frequency scalability')
    plt.xlabel("Number of Processes")
    plt.ylabel("Efficiency (%)")
    plt.xticks(tuple(traces_procs), tuple(label_xtics))
    if max_scale < 100:
        max_scale = 100

    plt.ylim(0, max_scale+5)
    plt.legend()
    plt.savefig('modelfactors-scale-matplot.png', bbox_inches='tight')

    ## Hybrid Metrics
    plt.figure()
    max_hybrid = max([max(list_data[8]), max(list_data[9]), max(list_data[10]), max(list_data[11]),
                     max(list_data[14]), max(list_data[15]), max(list_data[16])])
    plt.plot(traces_procs, list_data[8], 's-.', color='purple', label='Hybrid Parallel efficiency')
    plt.plot(traces_procs, list_data[9], 's-.', color='green', label='MPI Parallel efficiency')
    plt.plot(traces_procs, list_data[10], 's-.', color='lime', label='MPI Load balance')
    plt.plot(traces_procs, list_data[11], 's-.', color='lightseagreen', label='MPI Communication efficiency')
    plt.plot(traces_procs, list_data[14], 's-.', color='red', label='OpenMP Parallel efficiency')
    plt.plot(traces_procs, list_data[15], 's-.', color='orange', label='OpenMP Load Balance')
    plt.plot(traces_procs, list_data[16], 's-.', color='salmon', label='OpenMP Communication efficiency')
    plt.xlabel("Number of Processes")
    plt.ylabel("Efficiency (%)")
    plt.xticks(tuple(traces_procs), tuple(label_xtics))
    if max_hybrid < 100:
        max_hybrid = 100

    plt.ylim(0, max_hybrid+5)
    plt.legend()
    plt.savefig('modelfactors-hybrid-matplot.png', bbox_inches='tight')

    ## MPI Metrics
    plt.figure()
    max_mpi = max([max(list_data[9]), max(list_data[10]), max(list_data[11]),
                     max(list_data[12]), max(list_data[13])])
    plt.plot(traces_procs, list_data[9], 's-.', color='green', label='MPI Parallel efficiency')
    plt.plot(traces_procs, list_data[10], 's-.', color='lime', label='MPI Load balance')
    plt.plot(traces_procs, list_data[11], 's-.', color='lightseagreen', label='MPI Communication efficiency')
    plt.plot(traces_procs, list_data[12], 's-.', color='gold', label='Serialization efficiency')
    plt.plot(traces_procs, list_data[13], 's-.', color='tomato', label='Transfer efficiency')
    plt.xlabel("Number of Processes")
    plt.ylabel("Efficiency (%)")
    plt.xticks(tuple(traces_procs), tuple(label_xtics))
    if max_mpi < 100:
        max_mpi = 100

    plt.ylim(0, max_mpi+5)
    plt.legend()
    plt.savefig('modelfactors-mpi-matplot.png', bbox_inches='tight')

    # END Plotting using python