#!/usr/bin/env python3

"""Functions to compute the model metrics."""

from __future__ import print_function, division
import sys

from rawdata import *
from collections import OrderedDict

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
    """Creates 2D dictionary of the model factors and initializes with an empty
    string. The mod_factors dictionary has the format: [mod factor key][trace].
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
    normalized_runtime_ratio = 0
    normalized_useful_avg_ratio = 0

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
        try:  # except NaN
            runtime_ratio = float(raw_data['runtime'][trace]) / float(raw_data['runtime'][trace_list[0]])
        except:
            runtime_ratio = 'NaN'
        try:  # except NaN
            useful_avg_ratio = float(raw_data['useful_avg'][trace]) / float(raw_data['useful_avg'][trace_list[0]])
        except:
            useful_avg_ratio = 'NaN'
           
        normalized_inst_ratio += inst_ratio / proc_ratio
        normalized_runtime_ratio += runtime_ratio
        normalized_useful_avg_ratio += useful_avg_ratio
    # Get the average inst increase. Ignore ratio of first trace 1.0)
    normalized_inst_ratio = (normalized_inst_ratio - 1) / (len(trace_list) - 1)
    normalized_runtime_ratio = (normalized_runtime_ratio - 1) / (len(trace_list) - 1)
    normalized_useful_avg_ratio = (normalized_useful_avg_ratio - 1) / (len(trace_list) - 1)
    
    scaling_computed = ''
    scale_type = 0

    if normalized_inst_ratio > eps:
        scale_type += 1
    if normalized_runtime_ratio > eps:
        scale_type += 1
    if normalized_useful_avg_ratio > eps:
        scale_type += 1

    # scale_type greater than 1 means weak scaling.
    if scale_type > 1:
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


def compute_model_factors(raw_data, trace_list, trace_processes, trace_mode, list_mpi_procs_count, cmdl_args):
    """Computes the model factors from the gathered raw data and returns the
    according dictionary of model factors."""
    mod_factors = create_mod_factors(trace_list)
    other_metrics = create_other_metrics(trace_list)
    mod_factors_scale_plus_io = create_mod_factors_scale_io(trace_list)
    omp_talp_factors = create_omp_talp_factors(trace_list)

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

        # Computation Scale + Serial I/O
        try:  # except NaN
            if len(trace_list) > 1:
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
            if len(trace_list) > 1:
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

        # Frequency Scalability
        try:  # except NaN
            if (raw_data['useful_cyc'][trace] == 0):
                other_metrics['freq'][trace] = 'Non-Avail'
            else:
                other_metrics['freq'][trace] = float(raw_data['frequency'][trace]) / 1000
        except:
            other_metrics['freq'][trace] = 'NaN'

        try:  # except NaN
            if len(trace_list) > 1:
                if trace_mode[trace][:5] != 'Burst' and trace_mode[trace] != 'Sampling':
                    mod_factors['freq_scale'][trace] = other_metrics['freq'][trace] \
                                               / other_metrics['freq'][trace_list[0]] * 100.0
                else:
                    mod_factors['freq_scale'][trace] = 'Non-Avail'
            else:
                mod_factors['freq_scale'][trace] = 'Non-Avail'
        except:
            mod_factors['freq_scale'][trace] = 'NaN'
            
        # freq scale + Serial I/O
        try:  # except NaN
            if len(trace_list) > 1:
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
            if len(trace_list) > 1:
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

    return (mod_factors, mod_factors_scale_plus_io, other_metrics, omp_talp_factors)


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

    if len(warning_simulation) > 0:
        print("===> Warning! Metrics obtained from simulated traces exceed 100%. "
              "Please review original and simulated traces.")
    print('')


def print_other_metrics_table(other_metrics, trace_list, trace_processes):
    """Prints the model factors table in human readable form on stdout."""
    global other_metrics_doc

    print('Overview of the Speedup, IPC and Frequency:')

    longest_name = len(sorted(other_metrics_doc.values(), key=len)[-1])

    line = ''.rjust(longest_name)
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

    for index, trace in enumerate(trace_list):
        line += ' | '
        #if limit_min == limit_max and len(trace_list) > 1:
        line += (str(trace_processes[trace]) + '[' + str(index+1) + ']').rjust(value_to_adjust)
        #else:
        #    line += (str(trace_processes[trace])).rjust(value_to_adjust)

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
            print("Overview of tracer\'s flushing weight:")
            print(''.ljust(len(line_head), '-'))

        if mod_key not in ['speedup', 'ipc', 'freq', 'elapsed_time','efficiency']:
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
            elif mod_key in ['io_mpiio','io_posix']:
                for trace in trace_list:
                    line += ' | '
                    try:  # except NaN
                        line += ('{0:.2f}%'.format(other_metrics[mod_key][trace])).rjust(value_to_adjust)
                    except ValueError:
                        line += ('{}'.format(other_metrics[mod_key][trace])).rjust(value_to_adjust)
                if len(warning_io) > 0:
                    print(line)
            elif mod_key in ['io_eff']:
                for trace in trace_list:
                    line += ' | '
                    try:  # except NaN
                        line += ('{0:.2f}%'.format(other_metrics[mod_key][trace])).rjust(value_to_adjust)
                    except ValueError:
                        line += ('{}'.format(other_metrics[mod_key][trace])).rjust(value_to_adjust)
                if len(warning_io) > 0 or len(warning_flush) > 0:
                    print(line)

        # Print headers I/O
        if mod_key in ['flushing'] and len(warning_io) > 0:
            print(''.ljust(len(line), ' '))
            print('Overview of File I/O weight:')
            print(''.ljust(len(line), '-'))
        if mod_key in ['io_eff'] and len(warning_io) > 0:
            print(''.ljust(len(line), '-'))
        #    print('')

    if len(warning_flush) > 0:
        message_warning_flush = "WARNING! %Flushing is high and affects computation of efficiency metrics."
    else:
        message_warning_flush = ""
    if len(warning_io) > 0:
        message_warning_io = "WARNING! % File I/O is high and affects computation of efficiency metrics."
    else:
        message_warning_io = ""
    print(message_warning_flush + message_warning_io)
    print('')


def print_efficiency_table(mod_factors, trace_list, trace_processes):
    """Prints the model factors table in human readable form on stdout."""
    global mod_factors_doc

    longest_name = len(sorted(mod_factors_doc.values(), key=len)[-1])
    delimiter = ','
    file_path = os.path.join(os.getcwd(), 'efficiency_table.csv')
    with open(file_path, 'w') as output:
        line = '\"Number of processes\"'
        if len(trace_list) == 1:
            limit_min = trace_processes[trace_list[0]]
            limit_max = trace_processes[trace_list[0]]
        else:
            limit_min = trace_processes[trace_list[0]]
            limit_max = trace_processes[trace_list[len(trace_list)-1]]

        for index, trace in enumerate(trace_list):
            line += delimiter
            if limit_min == limit_max and len(trace_list) > 1:
                line += str(trace_processes[trace]) + '[' + str(index+1) + ']'
            else:
                line += str(trace_processes[trace])
        output.write(line + '\n')

        for mod_key in mod_factors_doc:
            if mod_key not in ['speedup', 'ipc', 'freq', 'elapsed_time', 'efficiency', 'flushing', 'io_mpiio', 'io_posix']:
                if mod_key in ['parallel_eff', 'comp_scale']:
                    line = "\"" + mod_factors_doc[mod_key].replace('  ', '', 2) + "\""
                elif mod_key in ['load_balance', 'comm_eff','ipc_scale', 'inst_scale','freq_scale']:
                    line = "\"" + mod_factors_doc[mod_key].replace('  ', '  ', 2) + "\""
                elif mod_key in ['serial_eff', 'transfer_eff']:
                    line = "\"    " + mod_factors_doc[mod_key].replace('  ', ' ', 4) + "\""
                else:
                    line = "\"" + mod_factors_doc[mod_key] + "\""
                for trace in trace_list:
                    line += delimiter
                    try:  # except NaN
                        if mod_factors[mod_key][trace] == "Non-Avail" or mod_factors[mod_key][trace] == "Warning!":
                            line += '0.00'
                        else:
                            line += '{0:.2f}'.format(mod_factors[mod_key][trace])
                    except ValueError:
                        line += '{}'.format(mod_factors[mod_key][trace])
                output.write(line + '\n')
        # print('')

        # Create Gnuplot file for efficiency plot
        gp_template = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'cfgs', 'efficiency_table.gp')
        content = []

        with open(gp_template) as f:
            content = f.readlines()

        limit_procs = 500 + len(trace_list) * 60

        # Replace xrange
        content = [line.replace('#REPLACE_BY_SIZE', ''.join(['set terminal pngcairo enhanced dashed crop size ',
                                                             str(limit_procs), ',460 font "Latin Modern Roman,14"']))
                   for line in content]

        file_path = os.path.join(os.getcwd(), 'efficiency_table.gp')
        with open(file_path, 'w') as f:
            f.writelines(content)

        # print('======== Plot (gnuplot File): EFFICIENCY Table ========')
        if len(trace_list) > 1:
            print('Efficiency Table written to ' + file_path[:len(file_path) - 3] + '.gp')
        # print('')


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


def plots_efficiency_table_matplot(trace_list, trace_processes, trace_tasks, trace_threads, cmdl_args):
    # Plotting using python
    # For plotting using python, read the csv file

    file_path = os.path.join(os.getcwd(), 'efficiency_table.csv')
    df = pd.read_csv(file_path)
    metrics = df['Number of processes'].tolist()
    traces_procs = list(df.keys())[1:]

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
    for index, trace in enumerate(trace_list):
        tasks = trace_tasks[trace]
        threads = trace_threads[trace]
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

    # BEGIN To adjust header to big number of processes
    max_len_header = 7
    for labelx in label_xtics:
        if len(labelx) > max_len_header:
            max_len_header = len(labelx)
    # END To adjust header to big number of processes

    list_data = []
    for index, rows in df.iterrows():
        list_temp = []
        for value in list(rows)[1:]:
            if float(value) == 0.0:
                list_temp.append(np.nan)
            else:
                list_temp.append(float(value))
        # print(list_temp)
        list_data.append(list_temp)

    list_np = np.array(list_data)

    idx = metrics
    cols = label_xtics
    #cols = traces_procs
    df = pd.DataFrame(list_np, index=idx, columns=cols)

    # min for 1 traces is x=3 for the (x,y) in figsize
    size_figure_y = len(idx) * 0.40
    size_figure_x = len(cols) * 0.16 * max_len_header
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

    ax.yaxis.set_tick_params(pad=len_pad + 120)
    plt.savefig('efficiency_table-matplot.png', bbox_inches='tight')


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


def plots_speedup_matplot(trace_list, trace_processes, trace_tasks, trace_threads, cmdl_args):
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
                list_temp.append(float('nan'))
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
            s_xtics = str(trace_processes[trace]) + '(' + str(tasks) + 'x' \
                          + str(threads) + ')'
        else:
            s_xtics = str(trace_processes[trace])
        label_xtics.append(s_xtics)

    ### Plot: SpeedUp
    # print(list_data)

    int_traces_procs = []
    prev_procs = int(float(traces_procs[0]))
    int_traces_procs.append(int(float(traces_procs[0])))
    count_rep = 0
    for procs in traces_procs[1:]:
        if prev_procs == int(float(procs)):
            count_rep += 1
            int_traces_procs.append(int(float(procs)) + (2 * count_rep))
            prev_procs = int(float(procs))
        else:
            int_traces_procs.append(int(float(procs)))
            prev_procs = int(float(procs))
            count_rep = 0


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
    # plt.xlim(0, )
    plt.ylim(0, )
    plt.savefig('speedup-matplot.png', bbox_inches='tight')

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
        max_y = 1.1
    plt.ylim(0,max_y+0.1)
    # plt.xlim(0, )
    plt.legend()
    plt.savefig('efficiency-matplot.png', bbox_inches='tight')


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