#!/usr/bin/env python3

"""Functions to plots efficiencies metrics"""

from __future__ import print_function, division
import os
from collections import OrderedDict

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


def plot_hybrid_metrics(mod_factors, hybrid_factors, trace_list, trace_processes, trace_tasks, trace_threads, trace_mode, cmdl_args):
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
        print('==DEBUG== Computing projection of model factors.')

    number_traces = len(trace_list)
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
        if trace_mode[trace] == 'Detailed+MPI' \
                or trace_mode[trace] == 'Detailed+MPI+OpenMP' \
                or trace_mode[trace] == 'Detailed+MPI+CUDA':
            if hybrid_factors['serial_eff'][trace] != 'N/A' and hybrid_factors['serial_eff'][trace] != 'Warning!':
                y_comm_serial[index] = hybrid_factors['serial_eff'][trace]
            else:
                y_comm_serial[index] = 0.0
            if hybrid_factors['transfer_eff'][trace] != 'N/A' \
                    and hybrid_factors['transfer_eff'][trace] != 'Warning!':
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


            # Set limit for projection
    if cmdl_args.limit:
        limit = cmdl_args.limit
    else:
        limit = str(trace_processes[trace_list[len(trace_list)-1]])

    limit_min = str(int(x_proc[0]))
    # limit_min = str(0)
    # To extract the trace name to show in the plots
    title_string = ""
    for index, trace in enumerate(trace_list):
        folder_trace_name = trace.split('/')
        trace_name_to_show = folder_trace_name[len(folder_trace_name) - 1]
        title_string += '(' + str(index+1) + ') ' + trace_name_to_show + "\\" + 'n'

    title_string += '"' + " noenhanced"

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

    # Create Gnuplot file for main plot
    gp_template = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'cfgs', 'modelfactors-onlydata.gp')
    content = []
    with open(gp_template) as f:
        content = f.readlines()

    # Replace xrange
    if int(limit) == int(limit_min):
        limit_plot = int(limit_min) + 5 * (len(trace_list) - 1)
    else:
        limit_plot = int(limit)

    # To xticks label
    label_xtics = 'set xtics ('
    glabel_xtics = []
    temp_procs = []
    list_real_procs = []
    for index, trace in enumerate(trace_list):
        tasks = trace_tasks[trace]
        threads = trace_threads[trace]
        s_xtics = str(trace_processes[trace]) + '(' + str(tasks) + 'x' + str(threads) + ')'
        if int(limit) == int(limit_min) and same_procs:
            proc_xtics = str(trace_processes[trace]) + '(' + str(tasks) + 'x' + str(threads) + ')' \
                         + '[' + str(index + 1) + ']'
            real_procs = str(trace_processes[trace] + index * 5)
        elif int(limit) == int(limit_min) and not same_procs:
            proc_xtics = str(trace_processes[trace]) + '(' + str(tasks) + 'x' + str(threads) + ')'
            real_procs = str(trace_processes[trace] + index * 5)
            if s_xtics in glabel_xtics:
                proc_xtics += '[' + str(index + 1) + ']'
            glabel_xtics.append(s_xtics)
        else:
            proc_xtics = str(trace_processes[trace]) + '(' + str(tasks) + 'x' + str(threads) + ')'
            real_procs = str(trace_processes[trace])
            if s_xtics in glabel_xtics:
                proc_xtics += '[' + str(index + 1) + ']'
            glabel_xtics.append(s_xtics)
        temp_procs.append(real_procs)

        count_real_procs = 0
        for procs in temp_procs:
            if real_procs == procs:
                count_real_procs += 1

        real_procs_before_string = int(real_procs) + (count_real_procs-1) * 5
        list_real_procs.append(real_procs_before_string)
        label_xtics += '"' + proc_xtics + '" ' + str(real_procs_before_string) + ', '

    content = [line.replace('#REPLACE_BY_XRANGE', ''
                            .join(['set xrange [', str(min(list_real_procs)), ':',
                                   str(max(list_real_procs)), ']'])) for line in content]
    content = [line.replace('#REPLACE_BY_XTICS_LABEL', ''.join([label_xtics[:-2] + ') '])) for
               line in content]
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
            line = ' '.join([str(list_real_procs[index]), str(y_para[index]), '\n'])
            f.write(line)
        f.write('e\n')

        for index in range(0, number_traces):
            line = ' '.join([str(list_real_procs[index]), str(y_load[index]), '\n'])
            f.write(line)
        f.write('e\n')

        for index in range(0, number_traces):
            line = ' '.join([str(list_real_procs[index]), str(y_comm[index]), '\n'])
            f.write(line)
        f.write('e\n')

        for index in range(0, number_traces):
            line = ' '.join([str(list_real_procs[index]), str(y_comp[index]), '\n'])
            f.write(line)
        f.write('e\n')

        for index in range(0, number_traces):
            line = ' '.join([str(list_real_procs[index]), str(y_glob[index]), '\n'])
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

    # Replace xrange
    content = [line.replace('#REPLACE_BY_XRANGE', ''.join(['set xrange [', str(min(list_real_procs)), ':',
                                                           str(max(list_real_procs)),']']) ) for line in content]
    content = [line.replace('#REPLACE_BY_XTICS_LABEL', ''.join([label_xtics[:-2]+') '])) for
               line in content]
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
            line = ' '.join([str(list_real_procs[index]), str(y_comp[index]), '\n'])
            f.write(line)
        f.write('e\n')

        for index in range(0, number_traces):
            line = ' '.join([str(list_real_procs[index]), str(y_ipc_scale[index]), '\n'])
            f.write(line)
        f.write('e\n')

        for index in range(0, number_traces):
            line = ' '.join([str(list_real_procs[index]), str(y_inst_scale[index]), '\n'])
            f.write(line)
        f.write('e\n')

        for index in range(0, number_traces):
            line = ' '.join([str(list_real_procs[index]), str(y_freq_scale[index]), '\n'])
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

    # Replace xrange
    content = [line.replace('#REPLACE_BY_XRANGE', ''.join(['set xrange [',str(min(list_real_procs)), ':',
                                                           str(max(list_real_procs)),']']) ) for line in content]
    content = [line.replace('#REPLACE_BY_XTICS_LABEL', ''.join([label_xtics[:-2]+') '])) for
               line in content]
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
            line = ' '.join([str(list_real_procs[index]), str(y_hybrid_par[index]), '\n'])
            f.write(line)
        f.write('e\n')

        for index in range(0, number_traces):
            line = ' '.join([str(list_real_procs[index]), str(y_mpi_par[index]), '\n'])
            f.write(line)
        f.write('e\n')

        for index in range(0, number_traces):
            line = ' '.join([str(list_real_procs[index]), str(y_mpi_load[index]), '\n'])
            f.write(line)
        f.write('e\n')

        for index in range(0, number_traces):
            line = ' '.join([str(list_real_procs[index]), str(y_mpi_comm[index]), '\n'])
            f.write(line)
        f.write('e\n')

        for index in range(0, number_traces):
            line = ' '.join([str(list_real_procs[index]), str(y_omp_par[index]), '\n'])
            f.write(line)
        f.write('e\n')

        for index in range(0, number_traces):
            line = ' '.join([str(list_real_procs[index]), str(y_omp_load[index]), '\n'])
            f.write(line)
        f.write('e\n')

        for index in range(0, number_traces):
            line = ' '.join([str(list_real_procs[index]), str(y_omp_comm[index]), '\n'])
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

    # Replace xrange
    content = [line.replace('#REPLACE_BY_XRANGE', ''.join(['set xrange [',str(min(list_real_procs)), ':',
                                                           str(max(list_real_procs)),']'])) for line in content]
    content = [line.replace('#REPLACE_BY_XTICS_LABEL', ''.join([label_xtics[:-2]+') '])) for
               line in content]
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
            line = ' '.join([str(list_real_procs[index]), str(y_mpi_par[index]), '\n'])
            f.write(line)
        f.write('e\n')

        for index in range(0, number_traces):
            line = ' '.join([str(list_real_procs[index]), str(y_mpi_load[index]), '\n'])
            f.write(line)
        f.write('e\n')

        for index in range(0, number_traces):
            line = ' '.join([str(list_real_procs[index]), str(y_mpi_comm[index]), '\n'])
            f.write(line)
        f.write('e\n')
        
        for index in range(0, number_traces):
            if str(y_comm_serial[index]) != 0.0:
                line = ' '.join([str(list_real_procs[index]), str(y_comm_serial[index]), '\n'])
                f.write(line)
        f.write('e\n')

        for index in range(0, number_traces):
            if str(y_comm_transfer[index]) != 0.0:
                line = ' '.join([str(list_real_procs[index]), str(y_comm_transfer[index]), '\n'])
                f.write(line)
        f.write('e\n')

        f.write('\n')
        f.write('pause -1\n')

    print('MPI hybrid metrics plot written to ' + file_path)


def plot_simple_metrics(mod_factors, trace_list, trace_processes, trace_mode, cmdl_args):
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
        if trace_mode[trace][:5] != 'Burst' and trace_mode[trace]!= 'Sampling':
            y_ipc_scale[index] = mod_factors['ipc_scale'][trace]
            y_inst_scale[index] = mod_factors['inst_scale'][trace]
            y_freq_scale[index] = mod_factors['freq_scale'][trace]
        else:
            y_ipc_scale[index] = 0.0
            y_inst_scale[index] = 0.0
            y_freq_scale[index] = 0.0
        if trace_mode[trace] == 'Detailed+MPI':
            if mod_factors['serial_eff'][trace] != 'Warning!':
                y_comm_serial[index] = mod_factors['serial_eff'][trace]
            else:
                y_comm_serial[index] = 0.0
            if mod_factors['transfer_eff'][trace] != 'Warning!':
                y_comm_transfer[index] = mod_factors['transfer_eff'][trace]
            else:
                y_comm_transfer[index] = 0.0
        else:
            y_comm_serial[index] = 0.0
            y_comm_transfer[index] = 0.0

    #Set limit for projection
    if cmdl_args.limit:
        limit = cmdl_args.limit
    else:
        limit = str(trace_processes[trace_list[len(trace_list) - 1]])

    limit_min = str(int(x_proc[0]))
    # limit_min = str(0)
    # To extract the trace name to show in the plots
    title_string = ""
    for index, trace in enumerate(trace_list):
        folder_trace_name = trace.split('/')
        trace_name_to_show = folder_trace_name[len(folder_trace_name) - 1]
        title_string += '(' + str(index+1) + ') ' + trace_name_to_show + "\\" + 'n'
    title_string += '"' + " noenhanced"

    #Create Gnuplot file for main plot
    gp_template = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'cfgs', 'modelfactors-onlydata.gp')
    content = []
    with open(gp_template) as f:
        content = f.readlines()

    #Replace xrange
    if int(limit) == int(limit_min):
        limit_plot = int(limit_min) + 5 * (len(trace_list) - 1)
    else:
        limit_plot = int(limit)

    # To xticks label
    label_xtics = 'set xtics ('
    for index, trace in enumerate(trace_list):

        if int(limit) == int(limit_min):
            label_xtics += '"' + str(trace_processes[trace]) + '[' + str(index + 1) + ']' + '" ' \
                           + str(trace_processes[trace] + index * 5) + ', '
        else:
            label_xtics += '"' + str(trace_processes[trace]) + '" ' + str(trace_processes[trace]) + ', '

    content = [line.replace('#REPLACE_BY_XRANGE', ''
                            .join(['set xrange [',limit_min,':', str(limit_plot),']'])) for line in content]
    content = [line.replace('#REPLACE_BY_XTICS_LABEL', ''.join([label_xtics[:-2] + ') '])) for
               line in content]

    content = [line.replace('#REPLACE_BY_TRACE_NAMES', ''.join(["set title " + '"' + ''])) for line in
               content]

    max_global = max([max(y_para), max(y_load), max(y_comm), max(y_comp), max(y_glob)])
    content = [line.replace('#REPLACE_BY_YRANGE', ''
                            .join(['set yrange [0:', str(max_global+5), ']'])) for line in content]

    file_path = os.path.join(os.getcwd(), 'modelfactors.gp')
    with open(file_path, 'w') as f:
        f.writelines(content)

    #Add data points to gnuplot file
    with open(file_path, 'a') as f:
        for index in range(0, number_traces):
            if int(limit) == int(limit_min):
                line = ' '.join([str(x_proc[index]+index*5), str(y_para[index]), '\n'])
            else:
                line = ' '.join([str(x_proc[index]), str(y_para[index]), '\n'])
            f.write(line)
        f.write('e\n')

        for index in range(0, number_traces):
            if int(limit) == int(limit_min):
                line = ' '.join([str(x_proc[index]+index*5), str(y_load[index]), '\n'])
            else:
                line = ' '.join([str(x_proc[index]), str(y_load[index]), '\n'])
            f.write(line)
        f.write('e\n')

        for index in range(0, number_traces):
            if int(limit) == int(limit_min):
                line = ' '.join([str(x_proc[index]+index*5), str(y_comm[index]), '\n'])
            else:
                line = ' '.join([str(x_proc[index]), str(y_comm[index]), '\n'])
            f.write(line)
        f.write('e\n')

        for index in range(0, number_traces):
            if int(limit) == int(limit_min):
                line = ' '.join([str(x_proc[index]+index*5), str(y_comp[index]), '\n'])
            else:
                line = ' '.join([str(x_proc[index]), str(y_comp[index]), '\n'])
            f.write(line)
        f.write('e\n')

        for index in range(0, number_traces):
            if int(limit) == int(limit_min):
                line = ' '.join([str(x_proc[index]+index*5), str(y_glob[index]), '\n'])
            else:
                line = ' '.join([str(x_proc[index]), str(y_glob[index]), '\n'])
            f.write(line)
        f.write('e\n')

        f.write('\n')
        f.write('pause -1\n')

    # print('========= Plot (gnuplot File): EFFICIENCY METRICS ==========')
    print('Efficiency metrics plot written to ' + file_path)
    # print('')

    # Create Gnuplot file for communication plot
    gp_template = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'cfgs', 'modelfactors_comm.gp')
    content = []
    with open(gp_template) as f:
        content = f.readlines()

    # Replace xrange
    content = [line.replace('#REPLACE_BY_XRANGE', ''.join(['set xrange [',limit_min,':',str(limit_plot),']']) ) for line in content]
    content = [line.replace('#REPLACE_BY_XTICS_LABEL', ''.join([label_xtics[:-2]+') '])) for
               line in content]

    content = [line.replace('#REPLACE_BY_TRACE_NAMES', ''.join(["set title " + '"' + ''])) for line in
               content]

    max_comm = max([max(y_comm), max(y_comm_serial), max(y_comm_transfer)])
    content = [line.replace('#REPLACE_BY_YRANGE', ''
                            .join(['set yrange [0:', str(max_comm+5), ']'])) for line in content]

    file_path = os.path.join(os.getcwd(), 'modelfactors_comm.gp')
    with open(file_path, 'w') as f:
        f.writelines(content)

    # Add data points to gnuplot file
    with open(file_path, 'a') as f:
        for index in range(0, number_traces):
            if int(limit) == int(limit_min):
                line = ' '.join([str(x_proc[index]+index*5), str(y_comm[index]), '\n'])
            else:
                line = ' '.join([str(x_proc[index]), str(y_comm[index]), '\n'])
            f.write(line)
        f.write('e\n')

        for index in range(0, number_traces):
            if str(y_comm_serial[index]) != 0.0:
                if int(limit) == int(limit_min):
                    line = ' '.join([str(x_proc[index]+index*5), str(y_comm_serial[index]), '\n'])
                else:
                    line = ' '.join([str(x_proc[index]), str(y_comm_serial[index]), '\n'])
                f.write(line)
        f.write('e\n')

        for index in range(0, number_traces):
            if str(y_comm_transfer[index]) != 0.0:
                if int(limit) == int(limit_min):
                    line = ' '.join([str(x_proc[index]+index*5), str(y_comm_transfer[index]), '\n'])
                else:
                    line = ' '.join([str(x_proc[index]), str(y_comm_transfer[index]), '\n'])
                f.write(line)
        f.write('e\n')

        f.write('\n')
        f.write('pause -1\n')

    # print('======= Plot (gnuplot File): COMMUNICATION METRICS ========')
    print('Communication Efficiency plot written to ' + file_path)
    # print('')

    # Create Gnuplot file for scalability plot
    gp_template = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'cfgs', 'modelfactors_scale.gp')
    content = []
    with open(gp_template) as f:
        content = f.readlines()

    # Replace xrange
    content = [line.replace('#REPLACE_BY_XRANGE', ''.join(['set xrange [',limit_min,':',str(limit_plot),']']) ) for line in content]
    content = [line.replace('#REPLACE_BY_XTICS_LABEL', ''.join([label_xtics[:-2]+') '])) for
               line in content]
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
            if int(limit) == int(limit_min):
                line = ' '.join([str(x_proc[index]+index*5), str(y_comp[index]), '\n'])
            else:
                line = ' '.join([str(x_proc[index]), str(y_comp[index]), '\n'])
            f.write(line)
        f.write('e\n')

        for index in range(0, number_traces):
            if int(limit) == int(limit_min):
                line = ' '.join([str(x_proc[index]+index*5), str(y_ipc_scale[index]), '\n'])
            else:
                line = ' '.join([str(x_proc[index]), str(y_ipc_scale[index]), '\n'])
            f.write(line)
        f.write('e\n')

        for index in range(0, number_traces):
            if int(limit) == int(limit_min):
                line = ' '.join([str(x_proc[index]+index*5), str(y_inst_scale[index]), '\n'])
            else:
                line = ' '.join([str(x_proc[index]), str(y_inst_scale[index]), '\n'])
            f.write(line)
        f.write('e\n')

        for index in range(0, number_traces):
            if int(limit) == int(limit_min):
                line = ' '.join([str(x_proc[index]+index*5), str(y_freq_scale[index]), '\n'])
            else:
                line = ' '.join([str(x_proc[index]), str(y_freq_scale[index]), '\n'])
            f.write(line)
        f.write('e\n')

        f.write('\n')
        f.write('pause -1\n')

    # print('========  Plot (gnuplot File): SCALABILITY METRICS ========')
    print('Scalability metrics plot written to ' + file_path)