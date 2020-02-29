#!/usr/bin/env python3

"""modelfactors.py Generates performance metrics from a set of Paraver traces."""

from __future__ import print_function, division
import os
import sys
import subprocess
import tempfile
import argparse
import math
import fnmatch
import re
import time
import resource
import mmap
import gzip
import shutil
from collections import OrderedDict

try:
    import scipy.optimize
except ImportError:
    print('==ERROR== Could not import SciPy. Please make sure to install a current version.')

try:
    import numpy
except ImportError:
    print('==ERROR== Could not import NumPy. Please make sure to install a current version.')

try:
    import sty
    from sty import fg, bg, ef, rs
except ImportError:
    print('sty module not available. Skipping color printing.')

__author__ = "Sandra Mendez"
__copyright__ = "Copyright 2019, Barcelona Supercomputing Center (BSC)"
__version_major__ = 0
__version_minor__ = 3
__version_micro__ = 7
__version__ = str(__version_major__) + "." + str(__version_minor__) + "." + str(__version_micro__)

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
                            ('flushing_avg', 'Flushing duration (average)'),
                            ('flushing_max', 'Flushing duration (maximum)'),
                            ('flushing_tot', 'Flushing duration (total)'),
                            ('io_tot', 'I/O duration (total)'),
                            ('io_max', 'I/O duration (maximum)'),
                            ('io_avg', 'I/O duration (avg)'),
                            ('mpiio_tot', 'MPI I/O duration (total)'),
                            ('mpiio_max', 'MPI I/O duration (maximum)'),
                            ('mpiio_avg', 'MPI I/O duration (avg)')])

# Contains all model factor entries with a printable name.
# This is used to generate and print all model factors, so, if an entry is added,
# it should be added here, too.
mod_factors_doc = OrderedDict([('speedup', 'Speedup'),
                               ('ipc', 'Average IPC'),
                               ('freq', 'Average frequency (GHz)'),
                               ('flushing', 'Flushing'),
                               ('io_mpiio', 'MPI I/O'),
                               ('io_posix', 'Other File I/O'),
                               ('global_eff', 'Global efficiency'),
                               ('parallel_eff', '-- Parallel efficiency'),
                               ('load_balance', '   -- Load balance'),
                               ('comm_eff', '   -- Communication efficiency'),
                               ('serial_eff', '      -- Serialization efficiency'),
                               ('transfer_eff', '      -- Transfer efficiency'),
                               ('comp_scale', '-- Computation scalability'),
                               ('ipc_scale', '   -- IPC scalability'),
                               ('inst_scale', '   -- Instruction scalability'),
                               ('freq_scale', '   -- Frequency scalability')])


def parse_arguments():
    """Parses the command line arguments.
    Currently the script only accepts one parameter list, which is the list of
    traces that are processed. This can be a regex and only valid trace files
    are kept at the end.
    """
    parser = argparse.ArgumentParser(description='Generates performance metrics from a set of Paraver traces.')
    parser.add_argument('trace_list', nargs='*',
                        help='list of traces to process. Accepts wild cards and automatically filters for '
                             'valid traces')
    parser.add_argument("-v", "--version", action='version', version='%(prog)s {version}'.format(version=__version__))
    parser.add_argument("-d", "--debug", help="increase output verbosity to debug level", action="store_true")
    parser.add_argument("-s", "--scaling",
                        help="define whether the measurements are weak or strong scaling (default: auto)",
                        choices=['weak', 'strong', 'auto'], default='auto')
    parser.add_argument("-p", "--project", metavar='<path-to-modelfactors.csv>',
                        help="run only the projection for the given modelfactors.csv (default: false)")
    parser.add_argument('--limit', help='limit number of cores for the projection (default: 10000)')
    parser.add_argument('--model', choices=['amdahl', 'pipe', 'linear'], default='amdahl',
                        help='select model for prediction (default: amdahl)')
    parser.add_argument('--bounds', choices=['yes', 'no'], default='yes',
                        help='set bounds for the prediction (default: yes)')
    parser.add_argument('--sigma', choices=['first', 'equal', 'decrease'], default='first',
                        help='set error restrains for prediction (default: first). first: prioritize smallest run; '
                             'equal: no priority; decrease: decreasing priority for larger runs')

    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(1)

    cmdl_args = parser.parse_args()

    if cmdl_args.debug:
        print('==DEBUG== Running in debug mode.')

    return cmdl_args


def get_traces_from_args(cmdl_args):
    """Filters the given list to extract traces, i.e. matching *.prv and sorts
    the traces in ascending order based on the number of processes in the trace.
    Excludes all files other than *.prv and ignores also simulated traces from
    this script, i.e. *.sim.prv
    Returns list of trace paths and dictionary with the number of processes.
    """
    trace_list = [x for x in cmdl_args.trace_list if (fnmatch.fnmatch(x, '*.prv') or fnmatch.fnmatch(x, '*.prv.gz'))
                  if not fnmatch.fnmatch(x, '*.sim.prv')]
    trace_list = sorted(trace_list, key=get_num_processes)

    if not trace_list:
        print('==Error== could not find any traces matching "', ' '.join(cmdl_args.trace_list))
        sys.exit(1)

    trace_processes = dict()
    trace_mode = dict()
    trace_task_per_node = dict()

    for trace in trace_list:
        trace_processes[trace] = get_num_processes(trace)
        trace_mode[trace] = get_trace_mode(trace)
        trace_task_per_node[trace] = get_task_per_node(trace)

    print_overview(trace_list, trace_processes, trace_mode, trace_task_per_node)
    return trace_list, trace_processes, trace_task_per_node, trace_mode


def get_num_processes(prv_file):
    """Gets the number of processes in a trace from the according .row file.
    Please note: return value needs to be integer because this function is also
    used as sorting key.
    """
    if prv_file[-4:] == ".prv":
        tracefile = open(prv_file[:-4] + '.row')
    elif prv_file[-7:] == ".prv.gz":
        tracefile = open(prv_file[:-7] + '.row')

    for line in tracefile:
        if "LEVEL CPU SIZE" in line:
            cpus = line[15:]

    tracefile.close()
    return int(cpus)


def get_task_per_node(prv_file):
    """Gets the number of processes and nodes in a trace from the according .row file.
    """

    if prv_file[-4:] == ".prv":
        tracefile = open(prv_file[:-4] + '.row')
    elif prv_file[-7:] == ".prv.gz":
        tracefile = open(prv_file[:-7] + '.row')

    for line in tracefile:
        if "LEVEL CPU SIZE" in line:
            tasks = int(line[15:])
        if "LEVEL NODE SIZE" in line:
            nodes = int(line[15:])

    tracefile.close()
    task_nodes = math.ceil(tasks / nodes)
    return (task_nodes)


def get_trace_mode(prv_file):
    """Gets the trace mode by detecting the event 40000018:2 in .prv file
    to detect the Burst mode trace in another case is Detailed mode.
    50000001 for MPI, 60000001 for OpenMP, 61000000 for pthreads, 63000001 for CUDA
    """
    mode_trace = ''
    burst = 0
    tracefile = open(prv_file)
    for line in tracefile:
        if "40000018:2" in line:
            burst = 1
            break
    tracefile.close()
    if burst == 1:
        mode_trace = 'Burst'
    else:
        mode_trace = 'Detailed'

    with open(prv_file[:-4] + '.pcf', 'rb', 0) as file, \
        mmap.mmap(file.fileno(), 0, access=mmap.ACCESS_READ) as s:
        if s.find(b'500000') != -1:
             mode_trace += '+MPI'
             if s.find(b'600000') != -1:
                mode_trace += '+OpenMP'
             if s.find(b'610000') != -1:
                mode_trace += '+Pthreads'
             if  s.find(b'630000') != -1 or s.find(b'631000') != -1 or s.find(b'632000') != -1:
                mode_trace += '+CUDA'
             if s.find(b'9200001') != -1:
                mode_trace += '+OmpSs'
             if s.find(b'642000') != -1 or s.find(b'6400001') != -1 or s.find(b'641000') != -1:
                 mode_trace += '+OpenCL'
        else:
             mode_trace += '+non-MPI'
             if s.find(b'600000') != -1:
                mode_trace += '+OpenMP'
             if s.find(b'610000') != -1:
                mode_trace += '+Pthreads'
             if  s.find(b'630000') != -1 or s.find(b'631000') != -1 or s.find(b'632000') != -1:
                mode_trace += '+CUDA'
             if s.find(b'9200001') != -1:
                mode_trace += '+OmpSs'
             if s.find(b'642000') != -1 or s.find(b'640000') != -1 or s.find(b'641000') != -1:
                 mode_trace += '+OpenCL'
    file.close()

    return (mode_trace)


def human_readable(size, precision=1):
    """Converts a given size in bytes to the value in human readable form."""
    suffixes = ['B', 'KB', 'MB', 'GB', 'TB']
    suffixIndex = 0
    while size > 1024 and suffixIndex < 4:
        suffixIndex += 1
        size = size / 1024.0
    return "%.*f%s" % (precision, size, suffixes[suffixIndex])


def print_overview(trace_list, trace_processes, trace_mode, trace_task_per_node):
    """Prints an overview of the traces that will be processed."""
    print('Running', os.path.basename(__file__), 'for the following traces:')

    for trace in trace_list:
        line = trace
        line += ', ' + str(trace_processes[trace]) + ' processes'
        line += ', ' + str(trace_task_per_node[trace]) + ' tasks per node'
        line += ', ' + human_readable(os.path.getsize(trace))
        line += ', ' + str(trace_mode[trace]) + ' mode'
        print(line)
    print('')


def which(cmd):
    """Returns path to cmd in path or None if not available."""
    for path in os.environ["PATH"].split(os.pathsep):
        path = path.strip('"')
        cmd_path = os.path.join(path, cmd)
        if os.path.isfile(cmd_path) and os.access(cmd_path, os.X_OK):
            return cmd_path

    return None


def check_installation(cmdl_args):
    """Check if Dimemas and paramedir are in the path."""

    if not which('Dimemas'):
        print('Could not find Dimemas. Please make sure Dimemas is correctly installed and in the path.')
        sys.exit(1)
    if not which('paramedir'):
        print('Could not find paramedir. Please make sure Paraver is correctly installed and in the path.')
        sys.exit(1)

    if cmdl_args.debug:
        print('==DEBUG== Using', __file__, __version__)
        print('==DEBUG== Using', sys.executable, ".".join(map(str, sys.version_info[:3])))

        try:
            print('==DEBUG== Using', 'SciPy', scipy.__version__)
        except NameError:
            print('==DEBUG== SciPy not installed.')

        try:
            print('==DEBUG== Using', 'NumPy', numpy.__version__)
        except NameError:
            print('==DEBUG== NumPy not installed.')

        print('==DEBUG== Using', which('Dimemas'))
        print('==DEBUG== Using', which('paramedir'))
        print('')

    return


def run_command(cmd):
    """Runs a command and forwards the return value."""
    if cmdl_args.debug:
        print('==DEBUG== Executing:', ' '.join(cmd))

    # In debug mode, keep the output. Otherwise, redirect it to devnull.
    if cmdl_args.debug:
        out = tempfile.NamedTemporaryFile(suffix='.out', prefix=cmd[0] + '_', dir='./', delete=False)
        err = tempfile.NamedTemporaryFile(suffix='.err', prefix=cmd[0] + '_', dir='./', delete=False)
    else:
        out = open(os.devnull, 'w')
        err = open(os.devnull, 'w')

    return_value = subprocess.call(cmd, stdout=out, stderr=err)

    out.close
    err.close

    if return_value == 0:
        if cmdl_args.debug:
            os.remove(out.name)
            os.remove(err.name)
    else:
        print('==ERROR== ' + ' '.join(cmd) + ' failed with return value ' + str(return_value) + '!')
        print('See ' + out.name + ' and ' + err.name + ' for more details.')

    return return_value


def save_remove(path):
    """Wraps os.remove with a try clause."""
    try:
        os.remove(path)
    except:
        if cmdl_args.debug:
            print('==DEBUG== Failed to remove ' + path + '!')


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
            if raw_data[data_key][trace] != "Non-Avail":
                line += str(round((raw_data[data_key][trace]),2)).rjust(15)
            else:
                line += str(raw_data[data_key][trace]).rjust(15)
        print(line)
    print(final_line_raw_data)
    print('')


def print_mod_factors_table(mod_factors, trace_list, trace_processes):
    """Prints the model factors table in human readable form on stdout."""
    global mod_factors_doc

    print('Overview of the Speedup, IPC and Frequency:')

    longest_name = len(sorted(mod_factors_doc.values(), key=len)[-1])

    line = ''.rjust(longest_name)
    for trace in trace_list:
        line += ' | '
        line += str(trace_processes[trace]).rjust(10)
    print(''.ljust(len(line), '-'))
    print(line)
    line_procs_factors = line

    print(''.ljust(len(line), '-'))

    for mod_key in mod_factors_doc:
        line = mod_factors_doc[mod_key].ljust(longest_name)
        if mod_key in ['speedup', 'ipc', 'freq']:
            for trace in trace_list:
                line += ' | '
                try:  # except NaN
                    line += ('{0:.2f}'.format(mod_factors[mod_key][trace])).rjust(10)
                except ValueError:
                    line += ('{}'.format(mod_factors[mod_key][trace])).rjust(10)
        elif mod_key in ['flushing']:
            for trace in trace_list:
                line += ' | '                                     
                try:  # except NaN
                    line += ('{0:.2f}%'.format(mod_factors[mod_key][trace])).rjust(10)
                except ValueError:
                    line += ('{}'.format(mod_factors[mod_key][trace])).rjust(10)
        else:
            for trace in trace_list:
                line += ' | '
                try:  # except NaN
                    line += ('{0:.2f}%'.format(mod_factors[mod_key][trace])).rjust(10)
                except ValueError:
                    line += ('{}'.format(mod_factors[mod_key][trace])).rjust(10)
        print(line)
        # Print empty line to separate values
        if mod_key in ['freq']:
            print(''.ljust(len(line), '-'))
            print(''.ljust(len(line), ' '))
            print("Overview of tracer\'s flushing weight:")
            print(''.ljust(len(line), '-'))

        # Print headers I/O
        if mod_key in ['flushing']:
            print(''.ljust(len(line), '-'))
            print(''.ljust(len(line), ' '))
            print('Overview of File I/O weight:')
            print(''.ljust(len(line), '-'))
        # Print headers model factors
        if mod_key in ['io_posix']:
            print(''.ljust(len(line), '-'))
            print(''.ljust(len(line), ' '))
            warning_io = []
            warning_flush = []
            for trace in trace_list:
                if mod_factors['flushing'][trace] >= 5.0:
                    warning_flush.append(1)
                if (mod_factors['io_mpiio'][trace] + mod_factors['io_posix'][trace]) >= 10.0:
                    warning_io.append(1)
            if len(warning_flush) > 0:
                message_warning_flush = "WARNING!!! --> Flushing > 5%.  "
            else:
                message_warning_flush = ""
            if len(warning_io) > 0:
                message_warning_io = "WARNING!!! --> File I/O > 10%."
            else:
                message_warning_io = ""

            print(message_warning_flush+message_warning_io)

            print(''.ljust(len(line), ' '))
            print('Overview of the Efficiency metrics:')
            print(''.ljust(len(line), '='))
            print(line_procs_factors)
            print(''.ljust(len(line), '='))
        if mod_key in ['freq_scale']:
            print(''.ljust(len(line), '='))

    print('')


def print_efficiency_table(mod_factors, trace_list, trace_processes):
    """Prints the model factors table in human readable form on stdout."""
    global mod_factors_doc

    ### print('Overview of the computed model factors:')

    longest_name = len(sorted(mod_factors_doc.values(), key=len)[-1])
    delimiter = ','
    file_path = os.path.join(os.getcwd(), 'efficiency_table.csv')
    with open(file_path, 'w') as output:
        line = '\"Number of processes\" '
        for trace in trace_list:
            line += delimiter
            line += str(trace_processes[trace])
        output.write(line + '\n')

        for mod_key in mod_factors_doc:
            if mod_key not in ['speedup', 'ipc', 'freq', 'flushing', 'io_mpiio', 'io_posix']:
                if mod_key in ['parallel_eff', 'comp_scale']:
                    line = "\"" + mod_factors_doc[mod_key].replace('  ', '', 2) + "\""
                elif mod_key in ['load_balance', 'comm_eff','ipc_scale', 'inst_scale','freq_scale']:
                    line = "\"" + mod_factors_doc[mod_key].replace('  ', '', 2) + "\""
                elif mod_key in ['serial_eff', 'transfer_eff']:
                    line = "\"    " + mod_factors_doc[mod_key].replace('  ', '', 4) + "\""
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
        print('')
        print('======== File: EFFICIENCY Table ========')
        print('Efficiency Table written to ' + file_path)
        shutil.copyfile(os.path.join(os.path.dirname(os.path.realpath(__file__)), 'cfgs', \
                                     'efficiency_table.gp'),
                        os.path.join(os.getcwd(), 'efficiency_table.gp'))


def print_mod_factors_csv(mod_factors, trace_list, trace_processes):
    """Prints the model factors table in a csv file."""
    global mod_factors_doc

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

        output.write('#\n')

        for raw_key in raw_data_doc:
            line = '#' + raw_data_doc[raw_key]
            for trace in trace_list:
                line += delimiter
                try:  # except NaN
                    line += '{0:.2f}'.format(raw_data[raw_key][trace])
                except ValueError:
                    line += '{}'.format(raw_data[raw_key][trace])
            output.write(line + '\n')

    print('======== File: METRICS AND EFFICIENCY ========')
    print('Model factors written to ' + file_path)


def gather_raw_data(trace_list, trace_processes, trace_task_per_node, trace_mode, cmdl_args):
    """Gathers all raw data needed to generate the model factors. Return raw
    data in a 2D dictionary <data type><list of values for each trace>"""
    raw_data = create_raw_data(trace_list)

    cfgs = {}
    cfgs['root_dir'] = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'cfgs')
    cfgs['timings'] = os.path.join(cfgs['root_dir'], 'timings.cfg')
    cfgs['runtime'] = os.path.join(cfgs['root_dir'], 'runtime_app.cfg')
    cfgs['cycles'] = os.path.join(cfgs['root_dir'], 'cycles.cfg')
    cfgs['instructions'] = os.path.join(cfgs['root_dir'], 'instructions.cfg')
    cfgs['flushing'] = os.path.join(cfgs['root_dir'], 'flushing.cfg')
    cfgs['mpi_io'] = os.path.join(cfgs['root_dir'], 'mpi-io-reverse.cfg')

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

        if trace_mode[trace] == 'Detailed+MPI' or trace_mode[trace] == 'Detailed+MPI+OpenMP':
           cmd_ideal = ['paramedir', trace_sim]
           cmd_ideal.extend([cfgs['timings'], trace_sim[:-4] + '.timings.stats'])
           cmd_ideal.extend([cfgs['runtime'], trace_sim[:-4] + '.runtime.stats'])

        run_command(cmd_normal)
        if trace_mode[trace] == 'Detailed+MPI' or trace_mode[trace] == 'Detailed+MPI+OpenMP':
           if not trace_sim == '':
            run_command(cmd_ideal)

        time_pmd = time.time() - time_pmd

        error_timing = 0;
        error_counters = 0;
        error_ideal = 0;

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
        save_remove(trace[:-4] + '.timings.stats')
        save_remove(trace[:-4] + '.runtime.stats')
        save_remove(trace[:-4] + '.cycles.stats')
        save_remove(trace[:-4] + '.instructions.stats')
        save_remove(trace[:-4] + '.flushing.stats')
        save_remove(trace[:-4] + '.mpi_io.stats')

        if trace_mode[trace] == 'Detailed+MPI' or trace_mode[trace] == 'Detailed+MPI+OpenMP':
          save_remove(trace_sim[:-4] + '.timings.stats')
          save_remove(trace_sim[:-4] + '.runtime.stats')

        time_prs = time.time() - time_prs

        time_tot = time.time() - time_tot
        print('Finished successfully in {0:.1f} seconds.'.format(time_tot))
        print('')

    return raw_data


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
        inst_ratio = float(raw_data['useful_ins'][trace]) / float(raw_data['useful_ins'][trace_list[0]])
        proc_ratio = float(trace_processes[trace]) / float(trace_processes[trace_list[0]])
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


def compute_model_factors(raw_data, trace_list, trace_processes, trace_mode, cmdl_args):
    """Computes the model factors from the gathered raw data and returns the
    according dictionary of model factors."""
    mod_factors = create_mod_factors(trace_list)
    # Guess the weak or strong scaling
    scaling = get_scaling_type(raw_data, trace_list, trace_processes, cmdl_args)

    # Loop over all traces
    for trace in trace_list:
        proc_ratio = float(trace_processes[trace]) / float(trace_processes[trace_list[0]])

        # Basic efficiency factors
        try:  # except NaN
            mod_factors['load_balance'][trace] = raw_data['useful_avg'][trace] \
                                                 / raw_data['useful_max'][trace] * 100.0
        except:
            mod_factors['load_balance'][trace] = 'NaN'

        try:  # except NaN
            mod_factors['comm_eff'][trace] = raw_data['useful_max'][trace] \
                                                     / raw_data['runtime'][trace] * 100.0
        except:
            mod_factors['comm_eff'][trace] = 'NaN'

        try:  # except NaN
            mod_factors['serial_eff'][trace] = raw_data['useful_dim'][trace] \
                                               / raw_data['runtime_dim'][trace] * 100.0
        except:
            if trace_mode[trace] == 'Detailed+MPI' or trace_mode[trace] == 'Detailed+MPI+OpenMP':
                mod_factors['serial_eff'][trace] = 'NaN'
            else:
                mod_factors['serial_eff'][trace] = 'Non-Avail'

        try:  # except NaN
            mod_factors['transfer_eff'][trace] = mod_factors['comm_eff'][trace] / mod_factors['serial_eff'][trace] * 100.0

        except:
            if trace_mode[trace] == 'Detailed+MPI' or trace_mode[trace] == 'Detailed+MPI+OpenMP':
              mod_factors['transfer_eff'][trace] = 'NaN'
            else:
              mod_factors['transfer_eff'][trace] = 'Non-Avail'
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

        # Basic scalability factors
        try:  # except NaN
            mod_factors['ipc'][trace] = float(raw_data['useful_ins'][trace]) \
                                        / float(raw_data['useful_cyc'][trace])
        except:
            mod_factors['ipc'][trace] = 'NaN'
        try:  # except NaN
            mod_factors['ipc_scale'][trace] = mod_factors['ipc'][trace] \
                                              / mod_factors['ipc'][trace_list[0]] * 100.0
        except:
            mod_factors['ipc_scale'][trace] = 'NaN'
        try:  # except NaN
            mod_factors['freq'][trace] = float(raw_data['useful_cyc'][trace]) \
                                         / float(raw_data['useful_tot'][trace]) / 1000
        except:
            mod_factors['freq'][trace] = 'NaN'
        try:  # except NaN
            mod_factors['freq_scale'][trace] = mod_factors['freq'][trace] \
                                               / mod_factors['freq'][trace_list[0]] * 100.0
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
                mod_factors['speedup'][trace] = raw_data['runtime'][trace_list[0]] \
                                                / raw_data['runtime'][trace]
            else:
                mod_factors['speedup'][trace] = raw_data['runtime'][trace_list[0]] \
                                                / raw_data['runtime'][trace] * proc_ratio
        except:
            mod_factors['speedup'][trace] = 'NaN'

        # Flushing measurements
        try:  # except NaN
            mod_factors['flushing'][trace] = raw_data['flushing_tot'][trace] \
                                                 / (raw_data['runtime'][trace] * trace_processes[trace]) * 100.0
        except:
            mod_factors['flushing'][trace] = 0.0

        # I/O measurements
        try:  # except NaN
            mod_factors['io_mpiio'][trace] = raw_data['mpiio_tot'][trace]\
                                             / (raw_data['runtime'][trace] * trace_processes[trace]) * 100.0
        except:
            mod_factors['io_mpiio'][trace] = 0.0

        try:  # except NaN
            mod_factors['io_posix'][trace] = (raw_data['io_tot'][trace] - raw_data['mpiio_tot'][trace])\
                                             /(raw_data['runtime'][trace] * trace_processes[trace]) * 100.0
        except:
            mod_factors['io_posix'][trace] = 0.0
    return mod_factors


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


def create_ideal_trace(trace, processes, task_per_node, cmdl_args):
    """Runs prv2dim and dimemas with ideal configuration for given trace."""
    if trace[-4:] == ".prv":
        trace_dim = trace[:-4] + '.dim'
        trace_sim = trace[:-4] + '.sim.prv'
    elif trace[-7:] == ".prv.gz":
        trace_dim = trace[:-7] + '.dim'
        trace_sim = trace[:-7] + '.sim.prv'

    cmd = ['prv2dim', trace, trace_dim]
    run_command(cmd)

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
    run_command(cmd)
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

    print('========= Plots: EFFICIENCY METRICS ==========')
    print('Efficiency Plot written to ' + file_path)

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

    print('======= Plots: COMMUNICATION METRICS ========')
    print('Communication Efficiency written to ' + file_path + '. Serialisation and Transfer'
                                                               ' Efficiency only have values'
                                                               ' for the Detailed+MPI trace type')

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

    print('========  Plots: SCALABILITY METRICS ========')
    print('Scalability metrics written to ' + file_path)

    return


if __name__ == "__main__":
    """Main control flow.
    Currently the script only accepts one parameter, which is a list of traces
    that are processed. This can be a regex with wild cards and only valid trace
    files are kept at the end.
    """
    # Parse command line arguments
    cmdl_args = parse_arguments()

    # Check if paramedir and Dimemas are in the path
    check_installation(cmdl_args)

    # Check if projection-only mode is selected
    # If not: compute everything
    # Else: read the passed modelfactors.csv
    if not cmdl_args.project:
        trace_list, trace_processes, trace_task_per_node, trace_mode = get_traces_from_args(cmdl_args)

        # Analyze the traces and gather the raw input data
        raw_data= gather_raw_data(trace_list, trace_processes, trace_task_per_node, trace_mode, cmdl_args)
        print_raw_data_table(raw_data, trace_list, trace_processes)

        # Compute the model factors andl print them
        mod_factors = compute_model_factors(raw_data, trace_list, trace_processes, trace_mode, cmdl_args)
        print_mod_factors_table(mod_factors, trace_list, trace_processes)
        print_efficiency_table(mod_factors, trace_list, trace_processes)
        print_mod_factors_csv(mod_factors, trace_list, trace_processes)
    else:
        # Read the model factors from the csv file
        mod_factors, trace_list, trace_processes = read_mod_factors_csv(cmdl_args)

    # Compute projection if SciPy and NumPy are installed.
    try:
        numpy.__version__
        scipy.__version__
    except NameError:
        print('Scipy or NumPy module not available. Skipping projection.')
        sys.exit(1)

    compute_projection(mod_factors, trace_list, trace_processes, cmdl_args)