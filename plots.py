#!/usr/bin/env python3

"""Functions to plots efficiencies metrics"""

from __future__ import print_function, division
import os
from tracemetadata import get_trace_mode

try:
    import scipy.optimize
except ImportError:
    print('==ERROR== Could not import SciPy. Please make sure to install a current version.')

try:
    import numpy
except ImportError:
    print('==ERROR== Could not import NumPy. Please make sure to install a current version.')



def compute_projection(mod_factors, trace_list, trace_processes, cmdl_args):
    """Computes the projection from the gathered model factors and returns the
    according dictionary of fitted prediction functions."""

    if cmdl_args.debug:
        print('==DEBUG== Computing projection of model factors.')

    number_traces = len(trace_list)
    x_proc = numpy.zeros(number_traces)
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

    #Convert dictionaries to NumPy arrays
    for index, trace in enumerate(trace_list):
        x_proc[index] = trace_processes[trace]
        y_para[index] = mod_factors['parallel_eff'][trace]
        y_load[index] = mod_factors['load_balance'][trace]
        y_comm[index] = mod_factors['comm_eff'][trace]
        y_comp[index] = mod_factors['comp_scale'][trace]
        y_glob[index] = mod_factors['global_eff'][trace]
        y_ipc_scale[index] = mod_factors['ipc_scale'][trace]
        y_inst_scale[index] = mod_factors['inst_scale'][trace]
        y_freq_scale[index] = mod_factors['freq_scale'][trace]
        if get_trace_mode(trace) == 'Detailed+MPI':
            y_comm_serial[index] = mod_factors['serial_eff'][trace]
            y_comm_transfer[index] = mod_factors['transfer_eff'][trace]
        else:
            y_comm_serial[index] = 0.0
            y_comm_transfer[index] = 0.0
    def amdahl(x, x0, f):
        """#Projection function based on amdahl; 2 degrees of freedom: x0, f"""
        return x0 / (f + (1 - f) * x)

    def pipe(x, x0, f):
        """Projection function based on pipeline; 2 degrees of freedom: x0, f"""
        return x0 * x / ((1 - f) + f * (2 * x - 1) )

    def linear(x, x0, f):
        """Projection function linear; 2 degrees of freedom: x0, a"""
        return x0 + f * x

    #Select model function
    if cmdl_args.model == 'amdahl':
        model = amdahl
    elif cmdl_args.model == 'pipe':
        model = pipe
    elif cmdl_args.model == 'linear':
        model = linear

    #Set limit for projection
    if cmdl_args.limit:
        limit = cmdl_args.limit
    else:
        limit = str(trace_processes[trace] + 4)
        limit_min = str(int(x_proc[0]))

    #Create Gnuplot file for main plot
    gp_template = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'cfgs', 'modelfactors-onlydata.gp')
    content = []
    with open(gp_template) as f:
        content = f.readlines()

    #Replace xrange
    content = [line.replace('#REPLACE_BY_XRANGE', ''.join(['set xrange [',limit_min,':',limit,']']) ) for line in content]

    file_path = os.path.join(os.getcwd(), 'modelfactors.gp')
    with open(file_path, 'w') as f:
        f.writelines(content)

    #Add data points to gnuplot file
    with open(file_path, 'a') as f:
        for index in range(0, number_traces):
            line = ' '.join([str(x_proc[index]), str(y_para[index]), '\n'])
            f.write(line)
        f.write('e\n')

        for index in range(0, number_traces):
            line = ' '.join([str(x_proc[index]), str(y_load[index]), '\n'])
            f.write(line)
        f.write('e\n')

        for index in range(0, number_traces):
            line = ' '.join([str(x_proc[index]), str(y_comm[index]), '\n'])
            f.write(line)
        f.write('e\n')

        for index in range(0, number_traces):
            line = ' '.join([str(x_proc[index]), str(y_comp[index]), '\n'])
            f.write(line)
        f.write('e\n')

        for index in range(0, number_traces):
            line = ' '.join([str(x_proc[index]), str(y_glob[index]), '\n'])
            f.write(line)
        f.write('e\n')

        f.write('\n')
        f.write('pause -1\n')

    print('========= Plot (gnuplot File): EFFICIENCY METRICS ==========')
    print('Efficiency Plot written to ' + file_path)
    print('')

    # Create Gnuplot file for communication plot
    gp_template = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'cfgs', 'modelfactors-comm.gp')
    content = []
    with open(gp_template) as f:
        content = f.readlines()

    # Replace xrange
    content = [line.replace('#REPLACE_BY_XRANGE', ''.join(['set xrange [',limit_min,':',limit,']']) ) for line in content]

    file_path = os.path.join(os.getcwd(), 'modelfactors-comm.gp')
    with open(file_path, 'w') as f:
        f.writelines(content)

    # Add data points to gnuplot file
    with open(file_path, 'a') as f:
        for index in range(0, number_traces):
            line = ' '.join([str(x_proc[index]), str(y_comm[index]), '\n'])
            f.write(line)
        f.write('e\n')

        for index in range(0, number_traces):
            if str(y_comm_serial[index]) != 0.0:
                line = ' '.join([str(x_proc[index]), str(y_comm_serial[index]), '\n'])
                f.write(line)
        f.write('e\n')

        for index in range(0, number_traces):
            if str(y_comm_transfer[index]) != 0.0:
                line = ' '.join([str(x_proc[index]), str(y_comm_transfer[index]), '\n'])
                f.write(line)
        f.write('e\n')

        f.write('\n')
        f.write('pause -1\n')

    print('======= Plot (gnuplot File): COMMUNICATION METRICS ========')
    print('Communication Efficiency written to ' + file_path + '. Serialisation and Transfer'
                                                               ' Efficiency only have values'
                                                               ' for the Detailed+MPI trace type')
    print('')
    # Create Gnuplot file for scalability plot
    gp_template = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'cfgs', 'modelfactors-scale.gp')
    content = []
    with open(gp_template) as f:
        content = f.readlines()

    # Replace xrange
    content = [line.replace('#REPLACE_BY_XRANGE', ''.join(['set xrange [',limit_min,':',limit,']']) ) for line in content]

    file_path = os.path.join(os.getcwd(), 'modelfactors-scale.gp')
    with open(file_path, 'w') as f:
        f.writelines(content)

    # Add data points to gnuplot file
    with open(file_path, 'a') as f:
        for index in range(0, number_traces):
            line = ' '.join([str(x_proc[index]), str(y_comp[index]), '\n'])
            f.write(line)
        f.write('e\n')

        for index in range(0, number_traces):
            line = ' '.join([str(x_proc[index]), str(y_ipc_scale[index]), '\n'])
            f.write(line)
        f.write('e\n')

        for index in range(0, number_traces):
            line = ' '.join([str(x_proc[index]), str(y_inst_scale[index]), '\n'])
            f.write(line)
        f.write('e\n')

        for index in range(0, number_traces):
            line = ' '.join([str(x_proc[index]), str(y_freq_scale[index]), '\n'])
            f.write(line)
        f.write('e\n')

        f.write('\n')
        f.write('pause -1\n')

    print('========  Plot (gnuplot File): SCALABILITY METRICS ========')
    print('Scalability metrics written to ' + file_path)

    return