#!/usr/bin/env python3

"""Functions to extract rawdata from each trace."""

from __future__ import print_function, division
import os
import time
from collections import OrderedDict

from tracemetadata import human_readable
from utils import run_command, save_remove


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
                            ('outsidempi_tot', 'Outside MPI duration (total)'),
                            ('flushing_avg', 'Flushing duration (average)'),
                            ('flushing_max', 'Flushing duration (maximum)'),
                            ('flushing_tot', 'Flushing duration (total)'),
                            ('io_tot', 'I/O duration (total)'),
                            ('io_max', 'I/O duration (maximum)'),
                            ('io_avg', 'I/O duration (avg)'),
                            ('mpiio_tot', 'MPI I/O duration (total)'),
                            ('mpiio_max', 'MPI I/O duration (maximum)'),
                            ('mpiio_avg', 'MPI I/O duration (avg)')])

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

    # Main loop over all traces
    # This can be parallelized: the loop iterations have no dependencies
    for trace in trace_list:
        time_tot = time.time()

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
           time_dim = time.time() - time_dim
           if not trace_sim == '':
             print('Successfully created simulated trace with Dimemas in {0:.1f} seconds.'.format(time_dim))
           else:
             print('Failed to create simulated trace with Dimemas.')

        # Run paramedir for the original and simulated trace
        time_pmd = time.time()
        cmd_normal = ['paramedir', trace]
        cmd_normal.extend([cfgs['timings'], trace[:-4] + '.timings.stats'])
        cmd_normal.extend([cfgs['runtime'], trace[:-4] + '.runtime.stats'])
        cmd_normal.extend([cfgs['cycles'], trace[:-4] + '.cycles.stats'])
        cmd_normal.extend([cfgs['instructions'], trace[:-4] + '.instructions.stats'])
        cmd_normal.extend([cfgs['flushing'], trace[:-4] + '.flushing.stats'])
        cmd_normal.extend([cfgs['mpi_io'], trace[:-4] + '.mpi_io.stats'])
        cmd_normal.extend([cfgs['outside_mpi'], trace[:-4] + '.outside_mpi.stats'])

        if trace_mode[trace] == 'Detailed+MPI' or trace_mode[trace] == 'Detailed+MPI+OpenMP':
           cmd_ideal = ['paramedir', trace_sim]
           cmd_ideal.extend([cfgs['timings'], trace_sim[:-4] + '.timings.stats'])
           cmd_ideal.extend([cfgs['runtime'], trace_sim[:-4] + '.runtime.stats'])

        run_command(cmd_normal,cmdl_args)
        if trace_mode[trace] == 'Detailed+MPI' or trace_mode[trace] == 'Detailed+MPI+OpenMP':
           if not trace_sim == '':
            run_command(cmd_ideal,cmdl_args)

        time_pmd = time.time() - time_pmd

        error_timing = 0
        error_counters = 0
        error_ideal = 0

        # Check if all files are created
        if not os.path.exists(trace[:-4] + '.timings.stats') or \
                not os.path.exists(trace[:-4] + '.runtime.stats'):
            print('==ERROR== Failed to compute timing information with paramedir.')
            error_timing = 1

        if not os.path.exists(trace[:-4] + '.cycles.stats') or \
                not os.path.exists(trace[:-4] + '.instructions.stats'):
            print('==ERROR== Failed to compute counter information with paramedir.')
            error_counters = 1

        if trace_mode[trace] == 'Detailed+MPI' or trace_mode[trace] == 'Detailed+MPI+OpenMP':
           if not os.path.exists(trace_sim[:-4] + '.timings.stats') or \
                   not os.path.exists(trace_sim[:-4] + '.runtime.stats'):
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
        if os.path.exists(trace[:-4] + '.timings.stats'):
            content = []
            with open(trace[:-4] + '.timings.stats') as f:
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
        # Get total IO, average IO, and maximum IO duration
        if os.path.exists(trace[:-4] + '.timings.stats'):
            content = []
            with open(trace[:-4] + '.timings.stats') as f:
                content = f.readlines()

                for line in content:
                    for field in line.split("\n"):
                        line_list = field.split("\t")
                        if "Running" in line_list:
                            try:
                                io_index = line_list.index("I/O")
                            except:
                                io_index = " "
                        elif io_index != " ":
                            if "Total" in field.split("\t"):
                                raw_data['io_tot'][trace] = float(line_list[io_index])
                            elif "Average" in field.split("\t"):
                                raw_data['io_avg'][trace] = float(line_list[io_index])
                            elif "Maximum" in field.split("\t"):
                                raw_data['io_max'][trace] = float(line_list[io_index])
                        else:
                            raw_data['io_tot'][trace] = 0.0
                            raw_data['io_avg'][trace] = 0.0
                            raw_data['io_max'][trace] = 0.0
        else:
            raw_data['io_tot'][trace] = 'NaN'
            raw_data['io_avg'][trace] = 'NaN'
            raw_data['io_max'][trace] = 'NaN'
        f.close()

        # Get total IO, average IO, and maximum IO duration for MPI-IO
        if os.path.exists(trace[:-4] + '.mpi_io.stats'):
            content = []
            with open(trace[:-4] + '.mpi_io.stats') as f:
                content = f.readlines()

                for line in content:
                    for field in line.split("\n"):
                        line_list = field.split("\t")
                        if "Total" in field.split("\t"):
                            count_procs = len(line_list[1:])
                            list_mpiio_tot = [ float(iotime) for iotime in line_list[1:count_procs]]
                            raw_data['mpiio_tot'][trace] = sum(list_mpiio_tot)
                        elif "Average" in field.split("\t"):
                            raw_data['mpiio_avg'][trace] = sum(list_mpiio_tot)/count_procs
                        elif "Maximum" in field.split("\t"):
                            raw_data['mpiio_max'][trace] = max(list_mpiio_tot)
        else:
            raw_data['mpiio_tot'][trace] = 0.0
            raw_data['mpiio_avg'][trace] = 0.0
            raw_data['mpiio_max'][trace] = 0.0
        f.close()

        # Get runtime
        if os.path.exists(trace[:-4] + '.runtime.stats'):
            content = []
            with open(trace[:-4] + '.runtime.stats') as f:
                content = f.readlines()

            for line in content:
                if line.split():
                    if line.split()[0] == 'Average':
                        raw_data['runtime'][trace] = float(line.split()[1])
        else:
            raw_data['runtime'][trace] = 'NaN'

        # Get total, average, and maximum outside MPI
        # list_mpi_procs_count = []
        if os.path.exists(trace[:-4] + '.outside_mpi.stats'):
            content = []
            with open(trace[:-4] + '.outside_mpi.stats') as f:
                content = f.readlines()
                list_outside_mpi = []
                for line1 in content[1:(len(content) - 8)]:
                    line = line1.split("\t")
                    # print(line)
                    if line:
                        if line[0] != 'Total' and line[0] != 'Average' \
                                and line[0] != 'Maximum' and line[0] != 'StDev' \
                                and line[0] != 'Avg/Max':
                            if float(line[1]) != raw_data['runtime'][trace]:
                                list_outside_mpi.append(float(line[1]))
                list_mpi_procs_count[trace] = len(list_outside_mpi)
                raw_data['outsidempi_tot'][trace] = sum(list_outside_mpi)
                raw_data['outsidempi_avg'][trace] = sum(list_outside_mpi) / len(list_outside_mpi)
                raw_data['outsidempi_max'][trace] = max(list_outside_mpi)

        else:
            raw_data['outsidempi_tot'][trace] = 'NaN'
            raw_data['outsidempi_avg'][trace] = 'NaN'
            raw_data['outsidempi_max'][trace] = 'NaN'
        f.close()
        # Get total, average, and maximum flushing duration
        if os.path.exists(trace[:-4] + '.flushing.stats'):
            content = []
            with open(trace[:-4] + '.flushing.stats') as f:
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

        # Get useful cycles
        if os.path.exists(trace[:-4] + '.cycles.stats'):
            content = []
            with open(trace[:-4] + '.cycles.stats') as f:
                content = f.readlines()

            for line in content:
                if line.split():
                    if line.split()[0] == 'Total':
                        raw_data['useful_cyc'][trace] = int(float(line.split()[1]))
        else:
            raw_data['useful_cyc'][trace] = 'NaN'

        # Get useful instructions
        if os.path.exists(trace[:-4] + '.instructions.stats'):
            content = []
            with open(trace[:-4] + '.instructions.stats') as f:
                content = f.readlines()

            for line in content:
                if line.split():
                    if line.split()[0] == 'Total':
                        raw_data['useful_ins'][trace] = int(float(line.split()[1]))
        else:
            raw_data['useful_ins'][trace] = 'NaN'

        # Get maximum useful duration for simulated trace
        if trace_mode[trace] == 'Detailed+MPI' or trace_mode[trace] == 'Detailed+MPI+OpenMP':
           if os.path.exists(trace_sim[:-4] + '.timings.stats'):
              content = []
              with open(trace_sim[:-4] + '.timings.stats') as f:
                content = f.readlines()

              for line in content:
                if line.split():
                    if line.split()[0] == 'Maximum':
                        raw_data['useful_dim'][trace] = float(line.split()[1])
           else:
            raw_data['useful_dim'][trace] = 'NaN'
        else:
            raw_data['useful_dim'][trace] = 'Non-Avail'

        # Get runtime for simulated trace
        if trace_mode[trace] == 'Detailed+MPI' or trace_mode[trace] == 'Detailed+MPI+OpenMP':
          if os.path.exists(trace_sim[:-4] + '.runtime.stats'):
            content = []
            with open(trace_sim[:-4] + '.runtime.stats') as f:
                content = f.readlines()

            for line in content:
                if line.split():
                    if line.split()[0] == 'Average':
                        raw_data['runtime_dim'][trace] = float(line.split()[1])
          else:
            raw_data['runtime_dim'][trace] = 'NaN'
        else:
            raw_data['runtime_dim'][trace] = 'Non-Avail'

        # Remove paramedir output files
        save_remove(trace[:-4] + '.timings.stats',cmdl_args)
        save_remove(trace[:-4] + '.runtime.stats',cmdl_args)
        save_remove(trace[:-4] + '.cycles.stats',cmdl_args)
        save_remove(trace[:-4] + '.instructions.stats',cmdl_args)
        save_remove(trace[:-4] + '.flushing.stats',cmdl_args)
        save_remove(trace[:-4] + '.mpi_io.stats',cmdl_args)

        if trace_mode[trace] == 'Detailed+MPI' or trace_mode[trace] == 'Detailed+MPI+OpenMP':
          save_remove(trace_sim[:-4] + '.timings.stats',cmdl_args)
          save_remove(trace_sim[:-4] + '.runtime.stats',cmdl_args)

        time_prs = time.time() - time_prs

        time_tot = time.time() - time_tot
        print('Finished successfully in {0:.1f} seconds.'.format(time_tot))
        print('')

    return raw_data,list_mpi_procs_count

def create_ideal_trace(trace, processes, task_per_node, cmdl_args):
    """Runs prv2dim and dimemas with ideal configuration for given trace."""
    if trace[-4:] == ".prv":
        trace_dim = trace[:-4] + '.dim'
        trace_sim = trace[:-4] + '.sim.prv'
    elif trace[-7:] == ".prv.gz":
        trace_dim = trace[:-7] + '.dim'
        trace_sim = trace[:-7] + '.sim.prv'

    cmd = ['prv2dim', trace, trace_dim]
    run_command(cmd,cmdl_args)

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

    with open(trace[:-4] + '.dimemas_ideal.cfg', 'w') as f:
        f.writelines(content)

    cmd = ['Dimemas', '-S', '32k', '--dim', trace_dim, '-p', trace_sim, trace[:-4] + '.dimemas_ideal.cfg']
    run_command(cmd,cmdl_args)
    # To remove simulation trace and ideal cfg
    os.remove(trace_dim)
    # os.remove(trace[:-4] + '.dimemas_ideal.cfg')

    if os.path.isfile(trace_sim):
        if cmdl_args.debug:
            print('==DEBUG== Created file ' + trace_sim)
        return trace_sim
    else:
        print('==Error== ' + trace_sim + ' could not be created.')
        return ''


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

    print('======== CSV File: TRACES RAW DATA ========')
    print('Raw data written to ' + file_path)
    print('')
    print('')