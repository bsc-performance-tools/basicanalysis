#!/usr/bin/env python3

"""Functions to extract rawdata from each trace."""

from __future__ import print_function, division
import os
import time
import math
import gzip
import shutil
from collections import OrderedDict
from tracemetadata import human_readable
from utils import run_command, move_files,remove_files, create_temp_folder


# Contains all raw data entries with a printable name.
# This is used to generate and print all raw data, so, if an entry is added, it
# should be added here, too.
raw_data_doc = OrderedDict([('runtime', 'Runtime (us)'),
                            ('runtime_dim', 'Runtime (ideal)'),
                            ('useful_avg', 'Useful duration (average)'),
                            ('useful_max', 'Useful duration (maximum)'),
                            ('useful_tot', 'Useful duration (total)'),
                            ('useful_dim', 'Useful duration (ideal, max)'),
                            ('useful_ins', 'Useful instructions (total)'),
                            ('useful_cyc', 'Useful cycles (total)'),
                            ('outsidempi_avg', 'Outside MPI duration (average)'),
                            ('outsidempi_max', 'Outside MPI duration (maximum)'),
                            ('outsidempi_dim', 'Outside MPI duration (ideal,maximum)'),
                            ('outsidempi_tot', 'Outside MPI duration (total)'),
                            ('mpicomm_tot', 'Communication MPI duration (total)'),
                            ('outsidempi_tot_diff', 'Outside MPI duration rescaled (total*threads)'),
                            ('flushing_avg', 'Flushing duration (average)'),
                            ('flushing_max', 'Flushing duration (maximum)'),
                            ('flushing_tot', 'Flushing duration (total)'),
                            ('flushing_cyc', 'Flushing cycles (total)'),
                            ('flushing_ins', 'Flushing instructions (total)'),
                            ('io_tot', 'Posix I/O duration (total)'),
                            ('io_max', 'Posix I/O duration (maximum)'),
                            ('io_avg', 'Posix I/O duration (avg)'),
                            ('io_std', 'Posix I/O duration (std)'),
                            ('io_cyc', 'Posix I/O cycles (total)'),
                            ('io_ins', 'Posix I/O instructions (total)'),
                            ('useful_plus_io_avg', 'Serial I/O plus useful duration (avg)'),
                            ('useful_plus_io_max', 'Serial I/O plus useful duration (max)'),
                            ('io_state_tot', 'state I/O duration (total)'),
                            ('io_state_avg', 'state I/O duration (avg)'),
                            ('io_state_max', 'state I/O duration (maximum)'),
                            ('mpiio_tot', 'MPI I/O duration (total)'),
                            ('mpiio_max', 'MPI I/O duration (maximum)'),
                            ('mpiio_avg', 'MPI I/O duration (avg)'),
                            ('mpiio_std', 'MPI I/O duration (std)'),
                            ('mpiio_cyc', 'MPI I/O cycles (total)'),
                            ('mpiio_ins', 'MPI I/O instructions (total)')])


def create_raw_data(trace_list):
    """Creates 2D dictionary of the raw input data and initializes with zero.
    The raw_data dictionary has the format: [raw data key][trace].
    """
    global raw_data_doc
    raw_data = {}
    for key in raw_data_doc:
        trace_dict = {}
        for trace_name in trace_list:
            trace_dict[trace_name] = 0

        raw_data[key] = trace_dict

    return raw_data


def gather_raw_data(trace_list, trace_processes, trace_task_per_node, trace_mode, cmdl_args):
    """Gathers all raw data needed to generate the model factors. Return raw
    data in a 2D dictionary <data type><list of values for each trace>"""
    raw_data = create_raw_data(trace_list)
    global list_mpi_procs_count
    list_mpi_procs_count = dict()

    cfgs = {}
    cfgs['root_dir'] = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'cfgs')
    cfgs['timings'] = os.path.join(cfgs['root_dir'], 'timings.cfg')
    cfgs['runtime'] = os.path.join(cfgs['root_dir'], 'runtime_app.cfg')
    cfgs['cycles'] = os.path.join(cfgs['root_dir'], 'cycles.cfg')
    cfgs['instructions'] = os.path.join(cfgs['root_dir'], 'instructions.cfg')
    cfgs['flushing'] = os.path.join(cfgs['root_dir'], 'flushing.cfg')
    cfgs['mpi_io'] = os.path.join(cfgs['root_dir'], 'mpi-io-reverse.cfg')
    cfgs['outside_mpi'] = os.path.join(cfgs['root_dir'], 'mpi-call-outside.cfg')
    cfgs['io_call'] = os.path.join(cfgs['root_dir'], 'io-call-reverse.cfg')
    cfgs['io_cycles'] = os.path.join(cfgs['root_dir'], 'io-call-cycles.cfg')
    cfgs['io_inst'] = os.path.join(cfgs['root_dir'], 'io-call-instructions.cfg')
    cfgs['mpiio_cycles'] = os.path.join(cfgs['root_dir'], 'mpi-io-cycles.cfg')
    cfgs['mpiio_inst'] = os.path.join(cfgs['root_dir'], 'mpi-io-instructions.cfg')
    cfgs['flushing_cycles'] = os.path.join(cfgs['root_dir'], 'flushing-cycles.cfg')
    cfgs['flushing_inst'] = os.path.join(cfgs['root_dir'], 'flushing-inst.cfg')

    # Main loop over all traces
    # This can be parallelized: the loop iterations have no dependencies
    path_dest = create_temp_folder('scratch_out_basicanalysis', cmdl_args)
    # path_dest_simul = create_temp_folder('output_simul_files', cmdl_args)

    for trace in trace_list:
        time_tot = time.time()
        if trace[-7:] == ".prv.gz":
            trace_name = trace[:-7] + '_' + str(trace_processes[trace]) + 'P'
        elif trace[-4:] == ".prv":
            trace_name = trace[:-4] + '_' + str(trace_processes[trace]) + 'P'

        line = 'Analyzing ' + os.path.basename(trace)
        line += ' (' + str(trace_processes[trace]) + ' processes'
        line += ', ' + str(trace_task_per_node[trace]) + ' tasks per node'
        line += ', ' + str(trace_mode[trace]) + ' mode'
        line += ', ' + human_readable(os.path.getsize(trace)) + ')'
        print(line)

        # Create simulated ideal trace with Dimemas
        if trace_mode[trace] == 'Detailed+MPI' or trace_mode[trace] == 'Detailed+MPI+OpenMP':
            time_dim = time.time()
            trace_sim = create_ideal_trace(trace, trace_processes[trace], trace_task_per_node[trace], cmdl_args)
            trace_name_sim = trace_sim[:-4]
            # print(trace_sim)
            time_dim = time.time() - time_dim
            if not trace_sim == '':
                print('Successfully created simulated trace with Dimemas in {0:.1f} seconds.'.format(time_dim))
            else:
                print('Failed to create simulated trace with Dimemas.')

        # Run paramedir for the original and simulated trace
        time_pmd = time.time()
        cmd_normal = ['paramedir', trace]

        cmd_normal.extend([cfgs['timings'], trace_name + '.timings.stats'])
        cmd_normal.extend([cfgs['runtime'], trace_name + '.runtime.stats'])
        cmd_normal.extend([cfgs['cycles'], trace_name + '.cycles.stats'])
        cmd_normal.extend([cfgs['instructions'], trace_name + '.instructions.stats'])
        cmd_normal.extend([cfgs['flushing'], trace_name + '.flushing.stats'])
        cmd_normal.extend([cfgs['io_call'], trace_name + '.io_call.stats'])
        cmd_normal.extend([cfgs['io_cycles'], trace_name + '.posixio-cycles.stats'])
        cmd_normal.extend([cfgs['io_inst'], trace_name + '.posixio-inst.stats'])
        cmd_normal.extend([cfgs['flushing_cycles'], trace_name + '.flushing-cycles.stats'])
        cmd_normal.extend([cfgs['flushing_inst'], trace_name + '.flushing-inst.stats'])

        if trace_mode[trace][:12] == 'Detailed+MPI':
            cmd_normal.extend([cfgs['mpi_io'], trace_name + '.mpi_io.stats'])
            cmd_normal.extend([cfgs['outside_mpi'], trace_name + '.outside_mpi.stats'])
            cmd_normal.extend([cfgs['mpiio_cycles'], trace_name + '.mpiio-cycles.stats'])
            cmd_normal.extend([cfgs['mpiio_inst'], trace_name + '.mpiio-inst.stats'])

        run_command(cmd_normal, cmdl_args)

        if trace_mode[trace] == 'Detailed+MPI' or trace_mode[trace] == 'Detailed+MPI+OpenMP':
            cmd_ideal = ['paramedir', trace_sim]
            cmd_ideal.extend([cfgs['timings'], trace_name_sim + '.timings.stats'])
            cmd_ideal.extend([cfgs['runtime'], trace_name_sim + '.runtime.stats'])
            cmd_ideal.extend([cfgs['outside_mpi'], trace_name_sim + '.outside_mpi.stats'])

        if trace_mode[trace] == 'Detailed+MPI' or trace_mode[trace] == 'Detailed+MPI+OpenMP':
            if not trace_sim == '':
                # print(cmd_ideal)
                run_command(cmd_ideal, cmdl_args)

        time_pmd = time.time() - time_pmd

        error_timing = 0
        error_counters = 0
        error_ideal = 0

        # Check if all files are created
        if not os.path.exists(trace_name + '.timings.stats') or \
                not os.path.exists(trace_name + '.runtime.stats') or \
                not os.path.exists(trace_name + '.outside_mpi.stats'):
            print('==ERROR== Failed to compute timing information with paramedir.')
            error_timing = 1

        if not os.path.exists(trace_name + '.cycles.stats') or \
                not os.path.exists(trace_name + '.instructions.stats'):
            print('==ERROR== Failed to compute counter information with paramedir.')
            error_counters = 1

        if trace_mode[trace] == 'Detailed+MPI' or trace_mode[trace] == 'Detailed+MPI+OpenMP':
            if not os.path.exists(trace_name_sim + '.timings.stats') or \
                   not os.path.exists(trace_name_sim + '.runtime.stats') or \
                   not os.path.exists(trace_name_sim + '.outside_mpi.stats'):
                print('==ERROR== Failed to compute timing information with paramedir.')
                error_ideal = 1
                trace_sim = ''

        if error_timing or error_counters or error_ideal:
            print('Failed to analyze trace with paramedir in {0:.1f} seconds.'.format(time_pmd))
        else:
            print('Successfully analyzed trace with paramedir in {0:.1f} seconds.'.format(time_pmd))

        # Parse the paramedir output files
        time_prs = time.time()

        # Get total, average, and maximum useful duration
        if os.path.exists(trace_name + '.timings.stats'):
            content = []
            with open(trace_name + '.timings.stats') as f:
                content = f.readlines()

            for line in content:
                if line.split():
                    if line.split()[0] == 'Total':
                        raw_data['useful_tot'][trace] = float(line.split()[1])
                    if line.split()[0] == 'Average':
                        raw_data['useful_avg'][trace] = float(line.split()[1])
                    if line.split()[0] == 'Maximum':
                        raw_data['useful_max'][trace] = float(line.split()[1])
        else:
            raw_data['useful_tot'][trace] = 'NaN'
            raw_data['useful_avg'][trace] = 'NaN'
            raw_data['useful_max'][trace] = 'NaN'
        f.close()

        # Get total File IO, average IO, and maximum IO duration
        if os.path.exists(trace_name + '.io_call.stats'):
            content = []
            with open(trace_name + '.io_call.stats') as f:
                content = f.readlines()

                for line in content:
                    for field in line.split("\n"):
                        line_list = field.split("\t")
                        if "Total" in field.split("\t"):
                            count_procs = len(line_list[1:])
                            list_io_tot = [float(iotime) for iotime in line_list[1:count_procs]]
                            # print(list_mpiio_tot)
                            raw_data['io_tot'][trace] = sum(list_io_tot)
                        elif "Average" in field.split("\t"):
                            raw_data['io_avg'][trace] = sum(list_io_tot)/count_procs
                            raw_data['io_std'][trace] = math.sqrt(sum([(number - raw_data['io_avg'][trace]) ** 2 \
                                                                       for number in list_io_tot]) / (len(list_io_tot) - 1))
                        elif "Maximum" in field.split("\t"):
                            raw_data['io_max'][trace] = max(list_io_tot)
        else:
            raw_data['io_tot'][trace] = 0.0
            raw_data['io_avg'][trace] = 0.0
            raw_data['io_max'][trace] = 0.0
            raw_data['io_std'][trace] = 0.0
        f.close()

        # Get total MPI IO, average IO, and maximum IO duration for MPI-IO
        dict_trace_mpiio={}
        if os.path.exists(trace_name + '.mpi_io.stats') and trace_mode[trace][:12] == 'Detailed+MPI':
            content = []
            with open(trace_name + '.mpi_io.stats') as f:
                content = f.readlines()

                for line in content:
                    for field in line.split("\n"):
                        line_list = field.split("\t")
                        if "Total" in field.split("\t"):
                            count_procs = len(line_list[1:])
                            list_mpiio_tot = [ float(iotime) for iotime in line_list[1:count_procs]]
                            dict_trace_mpiio[trace] = list_mpiio_tot
                            # print(list_mpiio_tot)
                            raw_data['mpiio_tot'][trace] = sum(list_mpiio_tot)
                        elif "Average" in field.split("\t"):
                            raw_data['mpiio_avg'][trace] = sum(list_mpiio_tot)/count_procs
                            raw_data['mpiio_std'][trace] = math.sqrt(sum([(number - raw_data['mpiio_avg'][trace]) ** 2
                                                                          for number in list_mpiio_tot])
                                                                     / (len(list_mpiio_tot) - 1))
                        elif "Maximum" in field.split("\t"):
                            raw_data['mpiio_max'][trace] = max(list_mpiio_tot)
        else:
            raw_data['mpiio_tot'][trace] = 0.0
            raw_data['mpiio_avg'][trace] = 0.0
            raw_data['mpiio_max'][trace] = 0.0
            raw_data['mpiio_std'][trace] = 0.0
        f.close()

        # Get total State IO, average IO, and maximum IO duration
        #print(dict_trace_mpiio)
        if os.path.exists(trace_name + '.timings.stats'):
            content = []
            with open(trace_name + '.timings.stats') as f:
                content = f.readlines()
                useful_plus_io = []
                useful_comp = []
                io_time = []
                for line in content:
                    for field in line.split("\n"):
                        line_list = field.split("\t")
                        #print(line)
                        if "Running" in line_list:
                            try:
                                io_index = line_list.index("I/O")
                            except:
                                io_index = " "
                        elif io_index != " ":
                            if "Total" in field.split("\t"):
                                raw_data['io_state_tot'][trace] = float(line_list[io_index])
                            elif "Average" in field.split("\t"):
                                raw_data['io_state_avg'][trace] = float(line_list[io_index])
                            elif "Maximum" in field.split("\t"):
                                raw_data['io_state_max'][trace] = float(line_list[io_index])
                            elif line_list[0].find("THREAD") != -1 and "Minimum" not in line_list \
                                and "StDev" not in line_list and "Avg/Max" not in line_list \
                                and len(line_list) > 1:
                                mpiio_index = len(useful_plus_io)
                                if len(dict_trace_mpiio) != 0:
                                    sum_aux = float(line_list[1]) + (float(line_list[io_index])
                                                                     - dict_trace_mpiio[trace][mpiio_index])
                                else:
                                    sum_aux = float(line_list[1]) + float(line_list[io_index])
                                #print("OutsideMP? ",sum_aux)
                                useful_plus_io.append(float(sum_aux))
                                useful_comp.append(float(line_list[1]))
                                io_time.append(float(line_list[io_index]))
                if io_index != " ":
                    useful_io_avg = float(sum(useful_plus_io)/len(useful_plus_io))
                    # mpiio is not included in useful + IO
                    raw_data['useful_plus_io_avg'][trace] = float(useful_io_avg)
                    raw_data['useful_plus_io_max'][trace] = float(max(useful_plus_io))
                else:
                    useful_io_avg = 0.0
                    raw_data['useful_plus_io_avg'][trace] = 0.0
                    raw_data['useful_plus_io_max'][trace] = 0.0
                    raw_data['io_state_tot'][trace] = 0.0
                    raw_data['io_state_avg'][trace] = 0.0
                    raw_data['io_state_max'][trace] = 0.0
        else:
            raw_data['useful_plus_io_avg'][trace] = 0.0
            raw_data['useful_plus_io_max'][trace] = 0.0
            raw_data['io_state_tot'][trace] = 0.0
            raw_data['io_state_avg'][trace] = 0.0
            raw_data['io_state_max'][trace] = 0.0
        f.close()


        # Get runtime
        if os.path.exists(trace_name + '.runtime.stats'):
            content = []
            with open(trace_name + '.runtime.stats') as f:
                content = f.readlines()

            for line in content:
                if line.split():
                    if line.split()[0] == 'Average':
                        raw_data['runtime'][trace] = float(line.split()[1])
        else:
            raw_data['runtime'][trace] = 'NaN'

        # Get total, average, and maximum outside MPI
        # list_mpi_procs_count = []
        if os.path.exists(trace_name + '.outside_mpi.stats') and trace_mode[trace][:12] == 'Detailed+MPI':
            content = []
            with open(trace_name + '.outside_mpi.stats') as f:
                content = f.readlines()
                list_outside_mpi = []

                list_thread_outside_mpi = []
                init_count_thread = False
                count_threads = 1
                for line1 in content[1:(len(content) - 8)]:
                    line = line1.split("\t")
                    # print(line)
                    if line:
                        if line[0] != 'Total' and line[0] != 'Average' \
                                and line[0] != 'Maximum' and line[0] != 'StDev' \
                                and line[0] != 'Avg/Max':
                            # To extract the count of MPI tasks
                            if float(line[1]) != raw_data['runtime'][trace]:
                                list_outside_mpi.append(float(line[1]))
                                # To extract the count of threads per MPI task
                                if len(list_outside_mpi) > 1:
                                    list_thread_outside_mpi.append(count_threads)
                                    count_threads = 1
                            else:
                                if len(list_outside_mpi) == 1 and not init_count_thread:
                                    count_threads = 2
                                    init_count_thread = True
                                else:
                                    count_threads += 1

                list_thread_outside_mpi.append(count_threads)

                count = 0
                equal_threads = True
                # Evaluate if the count of threads per MPI task are equal
                while count < (len(list_thread_outside_mpi) - 1) and equal_threads:
                    if list_thread_outside_mpi[count] != list_thread_outside_mpi[count+1]:
                        equal_threads = False
                    count += 1
                rescaled_outside_mpi = []
                # This is need to calculate the MPI_Par_Eff with the right #MPI_tasks and #threads
                if not equal_threads:
                    rescaled_outside_mpi.append(list_outside_mpi[0] * (list_thread_outside_mpi[0]))
                    # This is the sum of the outsidempi by the threads
                    sum_outside_mpi_threads = list_thread_outside_mpi[0]

                    for i in range(1,len(list_outside_mpi)):
                        rescaled_outside_mpi.append(list_outside_mpi[i] * (list_thread_outside_mpi[i]))
                        sum_outside_mpi_threads += list_thread_outside_mpi[i]
                    raw_data['outsidempi_tot_diff'][trace] = sum(rescaled_outside_mpi)
                    raw_data['outsidempi_tot'][trace] = sum(list_outside_mpi)
                    # Only the average is updated with the rescaled outsidempi
                    raw_data['outsidempi_avg'][trace] = sum(rescaled_outside_mpi) / sum(list_thread_outside_mpi)
                    # Maximum outsidempi is the same, although the count of threads is different
                    # because it waits that the MPI task has the max outsidempi.
                    raw_data['outsidempi_max'][trace] = max(list_outside_mpi)
                else:
                    raw_data['outsidempi_tot_diff'][trace] = sum(list_outside_mpi)
                    list_mpi_procs_count[trace] = len(list_outside_mpi)
                    raw_data['outsidempi_tot'][trace] = sum(list_outside_mpi)
                    raw_data['outsidempi_avg'][trace] = sum(list_outside_mpi) / len(list_outside_mpi)
                    raw_data['outsidempi_max'][trace] = max(list_outside_mpi)
                for line2 in content[(len(content) - 7):]:
                    line_aux = line2.split("\t")

                    if line_aux[0] == 'Total':
                        #print(line_aux)
                        count_mpiop = len(line_aux[1:])
                        list_mpi_tot = [float(mpitime) for mpitime in line_aux[2:count_mpiop]]
                        #print(list_mpi_tot)
                raw_data['mpicomm_tot'][trace] = sum(list_mpi_tot)
        else:
            raw_data['outsidempi_tot'][trace] = 'NaN'
            raw_data['outsidempi_avg'][trace] = 'NaN'
            raw_data['outsidempi_max'][trace] = 'NaN'
            raw_data['mpicomm_tot'][trace] = 'NaN'
        f.close()
        # Get total, average, and maximum flushing duration
        if os.path.exists(trace_name + '.flushing.stats'):
            content = []
            with open(trace_name + '.flushing.stats') as f:
                content = f.readlines()
                flushing_exist = '\tBegin\t\n' in content

            if flushing_exist:
                for line in content:
                    if line.split():
                        if line.split()[0] == 'Total':
                            raw_data['flushing_tot'][trace] = float(line.split()[1])
                        if line.split()[0] == 'Average':
                            raw_data['flushing_avg'][trace] = float(line.split()[1])
                        if line.split()[0] == 'Maximum':
                            raw_data['flushing_max'][trace] = float(line.split()[1])
            else:
                raw_data['flushing_tot'][trace] = 0.0
                raw_data['flushing_avg'][trace] = 0.0
                raw_data['flushing_max'][trace] = 0.0
        else:
            raw_data['flushing_tot'][trace] = 0.0
            raw_data['flushing_avg'][trace] = 0.0
            raw_data['flushing_max'][trace] = 0.0

        # Get total flushing cycles
        if os.path.exists(trace_name + '.flushing-cycles.stats'):
            content = []
            with open(trace_name + '.flushing-cycles.stats') as f:
                content = f.readlines()

            for line in content:
                if line.split():
                    if line.split()[0] == 'Total':
                        raw_data['flushing_cyc'][trace] = int(float(line.split()[1]))
        else:
            raw_data['flushing_cyc'][trace] = 0.0

        # Get total flushing instructions
        if os.path.exists(trace_name + '.flushing-inst.stats'):
            content = []
            with open(trace_name + '.flushing-inst.stats') as f:
                content = f.readlines()

            for line in content:
                if line.split():
                    if line.split()[0] == 'Total':
                        raw_data['flushing_ins'][trace] = int(float(line.split()[1]))
        else:
            raw_data['flushing_ins'][trace] = 0.0

        # Get total posixio cycles
        if os.path.exists(trace_name + '.posixio-cycles.stats'):
            content = []
            with open(trace_name + '.posixio-cycles.stats') as f:
                content = f.readlines()

            for line in content:
                if line.split():
                    if line.split()[0] == 'Total':
                        raw_data['io_cyc'][trace] = int(float(line.split()[1]))
        else:
            raw_data['io_cyc'][trace] = 0.0

        # Get total posixio instructions
        if os.path.exists(trace_name + '.posixio-inst.stats'):
            content = []
            with open(trace_name + '.posixio-inst.stats') as f:
                content = f.readlines()

            for line in content:
                if line.split():
                    if line.split()[0] == 'Total':
                        raw_data['io_ins'][trace] = int(float(line.split()[1]))
        else:
            raw_data['io_ins'][trace] = 0.0

        # Get total mpiio instructions
        if os.path.exists(trace_name + '.mpiio-cycles.stats') and trace_mode[trace][:12] == 'Detailed+MPI':
            content = []
            with open(trace_name + '.mpiio-cycles.stats') as f:
                content = f.readlines()

            for line in content:
                if line.split():
                    if line.split()[0] == 'Total':
                        raw_data['mpiio_cyc'][trace] = int(float(line.split()[1]))
        else:
            raw_data['mpiio_cyc'][trace] = 0.0

        # Get total mpiio instructions
        if os.path.exists(trace_name + '.mpiio-inst.stats') and trace_mode[trace][:12] == 'Detailed+MPI':
            content = []
            with open(trace_name + '.mpiio-inst.stats') as f:
                content = f.readlines()

            for line in content:
                if line.split():
                    if line.split()[0] == 'Total':
                        raw_data['mpiio_ins'][trace] = int(float(line.split()[1]))
        else:
            raw_data['mpiio_ins'][trace] = 0.0

        # Get useful cycles
        if os.path.exists(trace_name + '.cycles.stats'):
            content = []
            with open(trace_name + '.cycles.stats') as f:
                content = f.readlines()

            for line in content:
                if line.split():
                    if line.split()[0] == 'Total':
                        raw_data['useful_cyc'][trace] = int(float(line.split()[1]))
        else:
            raw_data['useful_cyc'][trace] = 'NaN'

        # Get useful instructions
        if os.path.exists(trace_name + '.instructions.stats'):
            content = []
            with open(trace_name + '.instructions.stats') as f:
                content = f.readlines()

            for line in content:
                if line.split():
                    if line.split()[0] == 'Total':
                        raw_data['useful_ins'][trace] = int(float(line.split()[1]))
        else:
            raw_data['useful_ins'][trace] = 'NaN'

        # Get timing for SIMULATED traces
        if trace_mode[trace] == 'Detailed+MPI' or trace_mode[trace] == 'Detailed+MPI+OpenMP':
            # Get maximum useful duration for simulated trace
            if os.path.exists(trace_name_sim + '.timings.stats'):
                content = []
                with open(trace_name_sim + '.timings.stats') as f:
                    content = f.readlines()

                for line in content:
                    if line.split():
                        if line.split()[0] == 'Maximum':
                            raw_data['useful_dim'][trace] = float(line.split()[1])
            else:
                raw_data['useful_dim'][trace] = 'NaN'

            # Get runtime for simulated trace
            if os.path.exists(trace_name_sim + '.runtime.stats'):
                content = []
                with open(trace_name_sim + '.runtime.stats') as f:
                    content = f.readlines()

                for line in content:
                    if line.split():
                        if line.split()[0] == 'Average':
                            raw_data['runtime_dim'][trace] = float(line.split()[1])
            else:
                raw_data['runtime_dim'][trace] = 'NaN'

            # Get outsideMPI max for simulated trace
            if os.path.exists(trace_name_sim + '.outside_mpi.stats'):
                    with open(trace_name_sim + '.outside_mpi.stats') as f:
                        content = f.readlines()
                        list_outside_mpi = []
                        list_thread_outside_mpi = []
                        init_count_thread = False
                        count_threads = 1
                        for line1 in content[1:(len(content) - 8)]:
                            line = line1.split("\t")
                        # print(line)
                            if line:
                                if line[0] != 'Total' and line[0] != 'Average' \
                                           and line[0] != 'Maximum' and line[0] != 'StDev' \
                                           and line[0] != 'Avg/Max':
                                    # To extract the count of MPI tasks
                                    if float(line[1]) != raw_data['runtime_dim'][trace]:
                                        list_outside_mpi.append(float(line[1]))
                                        # To extract the count of threads per MPI task
                                        if len(list_outside_mpi) > 1:
                                           list_thread_outside_mpi.append(count_threads)
                                        count_threads = 1
                                    else:
                                        if len(list_outside_mpi) == 1 and not init_count_thread:
                                            count_threads = 2
                                            init_count_thread = True
                                        else:
                                            count_threads += 1

                                    if line[0] == "THREAD 1.1.1":
                                        max_time_outside_mpi = float(line[1])

                        list_thread_outside_mpi.append(count_threads)
                        if len(list_outside_mpi) != 0:
                            raw_data['outsidempi_dim'][trace] = max(list_outside_mpi)
                        else:
                            raw_data['outsidempi_dim'][trace] = max_time_outside_mpi
            else:
                raw_data['outsidempi_dim'][trace] = 0.0
        else:
            raw_data['useful_dim'][trace] = 'Non-Avail'
            raw_data['runtime_dim'][trace] = 'Non-Avail'
            raw_data['outsidempi_dim'][trace] = 'Non-Avail'

        # Remove paramedir output files
        move_files(trace_name + '.timings.stats', path_dest, cmdl_args)
        move_files(trace_name + '.runtime.stats', path_dest, cmdl_args)
        move_files(trace_name + '.cycles.stats', path_dest, cmdl_args)
        move_files(trace_name + '.instructions.stats', path_dest, cmdl_args)
        move_files(trace_name + '.flushing.stats', path_dest, cmdl_args)
        move_files(trace_name + '.posixio-cycles.stats', path_dest, cmdl_args)
        move_files(trace_name + '.posixio-inst.stats', path_dest, cmdl_args)
        move_files(trace_name + '.flushing-cycles.stats', path_dest, cmdl_args)
        move_files(trace_name + '.flushing-inst.stats', path_dest, cmdl_args)

        if trace_mode[trace][:12] == 'Detailed+MPI':
            move_files(trace_name + '.mpi_io.stats', path_dest, cmdl_args)
            move_files(trace_name + '.io_call.stats', path_dest, cmdl_args)
            move_files(trace_name + '.outside_mpi.stats', path_dest, cmdl_args)
            move_files(trace_name + '.mpiio-cycles.stats', path_dest, cmdl_args)
            move_files(trace_name + '.mpiio-inst.stats', path_dest, cmdl_args)

        if trace_mode[trace] == 'Detailed+MPI' or trace_mode[trace] == 'Detailed+MPI+OpenMP':
            move_files(trace_name_sim + '.timings.stats', path_dest, cmdl_args)
            move_files(trace_name_sim + '.runtime.stats', path_dest, cmdl_args)
            move_files(trace_name_sim + '.outside_mpi.stats', path_dest, cmdl_args)
            move_files(trace_sim, path_dest, cmdl_args)
            move_files(trace_sim[:-4] + '.pcf', path_dest, cmdl_args)
            move_files(trace_sim[:-4] + '.row', path_dest, cmdl_args)
            # To move simulation trace and ideal cfg
            move_files(trace_sim[:-8] + '.dim', path_dest, cmdl_args)
            remove_files(trace_sim[:-8] + '.row', cmdl_args)
            remove_files(trace_sim[:-8] + '.pcf', cmdl_args)
            move_files(trace_sim[:-8] + '.dimemas_ideal.cfg', path_dest, cmdl_args)
            if trace[-7:] == ".prv.gz":
                remove_files(trace_name + '.prv', cmdl_args)
                # move_files(trace_name + '.prv', path_dest, cmdl_args)

        time_prs = time.time() - time_prs

        time_tot = time.time() - time_tot
        print('Finished successfully in {0:.1f} seconds.'.format(time_tot))
        print('')

    return raw_data,list_mpi_procs_count


def create_ideal_trace(trace, processes, task_per_node, cmdl_args):
    """Runs prv2dim and dimemas with ideal configuration for given trace."""
    if trace[-4:] == ".prv":
        trace_dim = trace[:-4] + '_' + str(processes) + 'P' + '.dim'
        trace_sim = trace[:-4] + '_' + str(processes) + 'P' + '.sim.prv'
        trace_name = trace[:-4]
        cmd = ['prv2dim', trace, trace_dim]
    elif trace[-7:] == ".prv.gz":
        with gzip.open(trace, 'rb') as f_in:
            with open(trace[:-7] + '.prv', 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
        trace_dim = trace[:-7] + '_' + str(processes) + 'P' + '.dim'
        trace_sim = trace[:-7] + '_' + str(processes) + 'P' + '.sim.prv'
        trace_name = trace[:-7]
        trace_unzip = trace[:-3]
        cmd = ['prv2dim', trace_unzip, trace_dim]

    run_command(cmd, cmdl_args)

    if os.path.isfile(trace_dim):
        if cmdl_args.debug:
            print('==DEBUG== Created file ' + trace_dim)
    else:
        print('==Error== ' + trace_dim + 'could not be creaeted.')
        return

    # Create Dimemas configuration
    cfg_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'cfgs')

    content = []
    with open(os.path.join(cfg_dir, 'dimemas_ideal.cfg')) as f:
        content = f.readlines()

    content = [line.replace('REPLACE_BY_NTASKS_PER_NODE', str(task_per_node)) for line in content]
    content = [line.replace('REPLACE_BY_NTASKS', str(processes)) for line in content]
    content = [line.replace('REPLACE_BY_COLLECTIVES_PATH', os.path.join(cfg_dir, 'dimemas.collectives')) for line in
               content]

    with open(trace_name + '_' + str(processes) + 'P' + '.dimemas_ideal.cfg', 'w') as f:
        f.writelines(content)

    cmd = ['Dimemas', '-S', '32k', '--dim', trace_dim, '-p', trace_sim, trace_name + '_' + str(processes)
           + 'P' + '.dimemas_ideal.cfg']
    run_command(cmd, cmdl_args)


    if os.path.isfile(trace_sim):
        if cmdl_args.debug:
            print('==DEBUG== Created file ' + trace_sim)
        return trace_sim
    else:
        print('==Error== ' + trace_sim + ' could not be created.')
        return ''


def print_raw_data_table(raw_data, trace_list, trace_processes):
    """Prints the raw data table in human readable form on stdout."""
    global raw_data_doc

    print('Overview of the collected raw data:')

    longest_name = len(sorted(raw_data_doc.values(), key=len)[-1])

    line = ''.rjust(longest_name)
    for trace in trace_list:
        line += ' | '
        line += str(trace_processes[trace]).rjust(15)
    print(''.ljust(len(line), '-'))
    print(line)

    print(''.ljust(len(line), '-'))
    final_line_raw_data = ''.ljust(len(line), '-')

    for data_key in raw_data_doc:
        line = raw_data_doc[data_key].ljust(longest_name)
        for trace in trace_list:
            line += ' | '
            if raw_data[data_key][trace] != "Non-Avail" and raw_data[data_key][trace] != 'NaN':
                line += str(round((raw_data[data_key][trace]),2)).rjust(15)
            else:
                line += str(raw_data[data_key][trace]).rjust(15)
        print(line)
    print(final_line_raw_data)
    print('')


def print_raw_data_csv(raw_data, trace_list, trace_processes):
    """Prints the model factors table in a csv file."""
    global raw_data_doc

    delimiter = ';'
    # File is stored in the trace directory
    # file_path = os.path.join(os.path.dirname(os.path.realpath(trace_list[0])), 'modelfactors.csv')
    # File is stored in the execution directory
    file_path = os.path.join(os.getcwd(), 'rawdata.csv')

    with open(file_path, 'w') as output:
        line = 'Number of processes'
        for trace in trace_list:
            line += delimiter
            line += str(trace_processes[trace])
        output.write(line + '\n')

        for raw_key in raw_data_doc:
            line = '#' + raw_data_doc[raw_key]
            for trace in trace_list:
                line += delimiter
                try:  # except NaN
                    line += '{0:.2f}'.format(raw_data[raw_key][trace])
                except ValueError:
                    line += '{}'.format(raw_data[raw_key][trace])
            output.write(line + '\n')

    print('======== Output Files: Traces raw data and intermediate data ========')
    print('Raw data written to ' + file_path)
    file_path_intermediate = os.path.join(os.getcwd(), 'scratch_out_basicanalysis')
    print('Intermediate file written to ' + file_path_intermediate)
    print('')