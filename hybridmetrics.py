#!/usr/bin/env python3

"""Functions to compute the model metrics."""

from __future__ import print_function, division
import sys
import subprocess
from os import system

from rawdata import *
from tracemetadata import get_trace_mode
from collections import OrderedDict
from utils import run_command

# Contains all model factor entries with a printable name.
# This is used to generate and print all model factors, so, if an entry is added,
# it should be added here, too.

other_metrics_doc = OrderedDict([('speedup', 'Speedup'),
                               ('ipc', 'Average IPC'),
                               ('freq', 'Average frequency (GHz)'),
                               ('flushing', 'Flushing'),
                               ('io_mpiio', 'MPI I/O'),
                               ('io_posix', 'Other File I/O'),
                               ('io_eff', 'I/O Efficiency')])

mod_factors_doc = OrderedDict([('global_eff', 'Global efficiency'),
                               ('parallel_eff', '-- Parallel efficiency'),
                               ('load_balance', '   -- Load balance'),
                               ('comm_eff', '   -- Communication efficiency'),
                               ('comp_scale', '-- Computation scalability'),
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
            other_metrics['io_mpiio'][trace] = (raw_data['mpiio_avg'][trace] + raw_data['mpiio_std'][trace])\
                                             / raw_data['runtime'][trace] * 100.0
        except:
            other_metrics['io_mpiio'][trace] = 0.0

        try:  # except NaN
            other_metrics['io_posix'][trace] = (raw_data['io_avg'][trace] + raw_data['io_std'][trace]) \
                                               / raw_data['runtime'][trace] * 100.0
        except:
            other_metrics['io_posix'][trace] = 0.0

        try:  # except NaN
            io_total = raw_data['mpiio_tot'][trace] + raw_data['flushing_tot'][trace] + raw_data['io_tot'][trace]
            other_metrics['io_eff'][trace] = (1 - io_total / (raw_data['useful_tot'][trace] + io_total)) * 100
        except:
            other_metrics['io_eff'][trace] = 0.0

        # Basic efficiency factors
        try:  # except NaN
            mod_factors['load_balance'][trace] = raw_data['useful_avg'][trace] \
                                                 / raw_data['useful_max'][trace] * 100.0
        except:
            mod_factors['load_balance'][trace] = 'NaN'

        try:  # except NaN
            # io_weight = other_metrics['io_mpiio'][trace] + other_metrics['io_posix'][trace]\
            #            + other_metrics['flushing'][trace]
            #if io_weight >= 10.0:
            #    mod_factors['comm_eff'][trace] = raw_data['useful_plus_io_max'][trace]\
            #                                      / raw_data['runtime'][trace] * 100.0
            #else:
            mod_factors['comm_eff'][trace] = raw_data['useful_max'][trace] \
                                                     / raw_data['runtime'][trace] * 100.0
        except:
            mod_factors['comm_eff'][trace] = 'NaN'

        try:  # except NaN
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
        try:  # except NaN
            if scaling == 'strong':
                mod_factors['inst_scale'][trace] = float(raw_data['useful_ins'][trace_list[0]]) \
                                                   / float(raw_data['useful_ins'][trace]) * 100.0
            else:
                mod_factors['inst_scale'][trace] = float(raw_data['useful_ins'][trace_list[0]]) \
                                                   / float(raw_data['useful_ins'][trace]) * proc_ratio * 100.0
        except:
            mod_factors['inst_scale'][trace] = 'NaN'
        try:  # except NaN
            if scaling == 'strong':
                other_metrics['speedup'][trace] = raw_data['runtime'][trace_list[0]] \
                                                / raw_data['runtime'][trace]
            else:
                other_metrics['speedup'][trace] = raw_data['runtime'][trace_list[0]] \
                                                / raw_data['runtime'][trace] * proc_ratio
        except:
            other_metrics['speedup'][trace] = 'NaN'

    return mod_factors, hybrid_factors, other_metrics


def print_mod_factors_table(mod_factors, hybrid_factors, trace_list, trace_processes):
    """Prints the model factors table in human readable form on stdout."""
    global mod_factors_doc, mod_hybrid_factors_doc

    # Update the hybrid parallelism mode
    trace_mode_doc = get_trace_mode(trace_list[0])
    if trace_mode_doc[0:len("Detailed+MPI+")] == "Detailed+MPI+":
        mod_hybrid_factors_doc['omp_parallel_eff'] = "   -- " + \
                                                     trace_mode_doc[len("Detailed+MPI+"):] + " Parallel efficiency"
        mod_hybrid_factors_doc['omp_load_balance'] = "      -- " + \
                                                     trace_mode_doc[len("Detailed+MPI+"):] + " Load Balance"
        mod_hybrid_factors_doc['omp_comm_eff'] = "      -- " + \
                                                 trace_mode_doc[len("Detailed+MPI+"):] + " Communication efficiency"
    
    print('')
    print('Overview of the Efficiency metrics:')

    longest_name = len(sorted(mod_hybrid_factors_doc.values(), key=len)[-1])

    line = ''.rjust(longest_name)
    for index, trace in enumerate(trace_list):
        line += ' | '
        line += (str(trace_processes[trace]) + '(' + str(index+1) + ')').rjust(10)
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

    print('Overview of the Speedup, IPC and Frequency:')

    longest_name = len(sorted(other_metrics_doc.values(), key=len)[-1])

    line = ''.rjust(longest_name)
    for index, trace in enumerate(trace_list):
        line += ' | '
        line += (str(trace_processes[trace]) + '(' + str(index+1) + ')').rjust(10)
    print(''.ljust(len(line), '-'))
    print(line)
    line_head = line
    print(''.ljust(len(line), '-'))

    for mod_key in other_metrics_doc:
        line = other_metrics_doc[mod_key].ljust(longest_name)
        if mod_key in ['speedup', 'ipc', 'freq']:
            for trace in trace_list:
                line += ' | '
                try:  # except NaN
                    line += ('{0:.2f}'.format(other_metrics[mod_key][trace])).rjust(10)
                except ValueError:
                    line += ('{}'.format(other_metrics[mod_key][trace])).rjust(10)
            print(line)
    print(''.ljust(len(line_head), '-'))
    print('')

    warning_io = []
    warning_flush = []
    for trace in trace_list:
        if other_metrics['flushing'][trace] >= 5.0:
            warning_flush.append(1)
        if (other_metrics['io_mpiio'][trace] + other_metrics['io_posix'][trace]) >= 5.0:
            warning_io.append(1)
    if len(warning_flush) > 0:
        message_warning_flush = "WARNING!!! --> Flushing > 5%.  "
    else:
        message_warning_flush = ""
    if len(warning_io) > 0:
        message_warning_io = "WARNING!!! --> File I/O > 5%."
    else:
        message_warning_io = ""
    print(message_warning_flush+message_warning_io)

    for mod_key in other_metrics_doc:
        line = other_metrics_doc[mod_key].ljust(longest_name)
        # Print empty line to separate values
        if mod_key in ['freq'] and len(warning_flush) > 0:
            print("Overview of tracer\'s flushing weight:")
            print(''.ljust(len(line_head), '-'))

        if mod_key not in ['speedup', 'ipc', 'freq']:
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
            elif mod_key in ['io_mpiio','io_posix', 'io_eff']:
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
        if mod_key in ['io_posix'] and len(warning_io) > 0:
            print(''.ljust(len(line), '-'))
            print('')


def print_efficiency_table(mod_factors, hybrid_factors, trace_list, trace_processes):
    """Prints the model factors table in human readable form on stdout."""
    global mod_factors_doc, mod_hybrid_factors_doc

    delimiter = ','
    file_path = os.path.join(os.getcwd(), 'efficiency_table-global.csv')
    with open(file_path, 'w') as output:
        line = '\"Number of processes\"'
        for index, trace in enumerate(trace_list):
            line += delimiter
            line += str(trace_processes[trace]) + '(' + str(index+1) + ')'
        output.write(line + '\n')

        for mod_key in mod_factors_doc:
            if mod_key not in ['speedup', 'ipc', 'freq', 'flushing', 'io_mpiio', 'io_posix']:
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

        limit_procs = 500 + len(trace_list) * 60
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
            line += str(trace_processes[trace])  + '(' + str(index+1) + ')'
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

        limit_procs = 510 + len(trace_list) * 60

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
        line = 'Number of processes'
        for trace in trace_list:
            line += delimiter
            line += str(trace_processes[trace])
        output.write(line + '\n')

        for mod_key in mod_factors_doc:
            line = mod_factors_doc[mod_key].replace('  ', '', 2)
            for trace in trace_list:
                line += delimiter
                try:  # except NaN
                    line += '{0:.6f}'.format(mod_factors[mod_key][trace])
                except ValueError:
                    line += '{}'.format(mod_factors[mod_key][trace])
            output.write(line + '\n')

        for mod_key in mod_hybrid_factors_doc:
            line = mod_hybrid_factors_doc[mod_key].replace('  ', '', 2)
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

    print('======== Output File: Other Metrics ========')
    print('Speedup, IPC, Frequency, I/O and Flushing written to ' + file_path)
    print('')
