#!/usr/bin/env python3

"""Functions to extract metadata information from each trace."""

from __future__ import print_function, division
import os
import sys
import math
import fnmatch
import mmap
import gzip


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
    row_file = True

    if prv_file[-4:] == ".prv":
        if os.path.exists(prv_file[:-4] + '.row'):
            tracefile = open(prv_file[:-4] + '.row')
        else:
            tracefile = prv_file[:-4]
            row_file = False
    elif prv_file[-7:] == ".prv.gz":
        if os.path.exists(prv_file[:-7] + '.row'):
            tracefile = open(prv_file[:-7] + '.row')
        else:
            tracefile = prv_file[:-7]
            row_file = False

    cpus = 0
    if row_file:
        for line in tracefile:
            if "LEVEL CPU SIZE" in line:
                cpus = line[15:]

        tracefile.close()
    else:
        if prv_file[-4:] == ".prv":
            tracefile = open(prv_file)
            for line in tracefile:
                header_trace = line.split('_')
                break
            tracefile.close()

        if prv_file[-7:] == ".prv.gz":
            with gzip.open(prv_file, 'rt') as f:
                for line in f:
                    if "#Paraver" in line:
                        header_trace = line.split('_')
                        break
            f.close()

        # tasks_temp = header_trace[3].split('(')[1].split(',')[0]

        list_tasks_node_temp = header_trace[1].split(':')[1].split('(')[1].replace(')','').split(',')
        list_tasks_node = [int(mapping) for mapping in list_tasks_node_temp]
        cpus = sum(list_tasks_node)

    return int(cpus)


def get_task_per_node(prv_file):
    """Gets the number of processes and nodes in a trace from the according .row file.
    """
    row_file = True

    if prv_file[-4:] == ".prv":
        if os.path.exists(prv_file[:-4] + '.row'):
            tracefile = open(prv_file[:-4] + '.row')
        else:
            tracefile = prv_file[:-4]
            row_file = False
    elif prv_file[-7:] == ".prv.gz":
        if os.path.exists(prv_file[:-7] + '.row'):
            tracefile = open(prv_file[:-7] + '.row')
        else:
            tracefile = prv_file[:-7]
            row_file = False

    tasks = 0
    nodes = 1
    if row_file:
        for line in tracefile:
            if "LEVEL CPU SIZE" in line:
                tasks = int(line[15:])
            if "LEVEL NODE SIZE" in line:
                nodes = int(line[15:])
        tracefile.close()
        task_nodes = math.ceil(int(tasks) / int(nodes))
    else:
        if prv_file[-4:] == ".prv":
            tracefile = open(prv_file)
            for line in tracefile:
                header_trace = line.split('_')
                break
            tracefile.close()

        if prv_file[-7:] == ".prv.gz":
            with gzip.open(prv_file, 'rt') as f:
                for line in f:
                    if "#Paraver" in line:
                        header_trace = line.split('_')
                        break
            f.close()
        task_nodes = int(header_trace[1].split(':')[1].split('(')[1].replace(')','').split(',')[0])

    return int(task_nodes)


def get_tasks_threads(prv_file):
    """Gets the tasks and threads from the .prv file.
      """
    if prv_file[-4:] == ".prv":
        tracefile = open(prv_file)
        for line in tracefile:
            header_trace = line.split('_')
            break
        tracefile.close()

    if prv_file[-7:] == ".prv.gz":
        with gzip.open(prv_file, 'rt') as f:
            for line in f:
                if "#Paraver" in line:
                    header_trace = line.split('_')
                    break
        f.close()
    header_to_print = header_trace[1].split(':')[3].split('(')
    tasks = header_to_print[0]
    threads = header_to_print[1]
    return int(tasks), int(threads)


def get_trace_mode(prv_file):
    """Gets the trace mode by detecting the event 40000018:2 in .prv file
    to detect the Burst mode trace in another case is Detailed mode.
    50000001 for MPI, 60000001 for OpenMP, 61000000 for pthreads, 63000001 for CUDA
    """
    mode_trace = ''
    burst = 0
    pcf_file = True
    if prv_file[-4:] == ".prv":
        file_pcf = prv_file[:-4] + '.pcf'
        tracefile = open(prv_file)
        for line in tracefile:
            if "40000018:2" in line:
                burst = 1
                break
        tracefile.close()
    if prv_file[-7:] == ".prv.gz":
        file_pcf = prv_file[:-7] + '.pcf'
        with gzip.open(prv_file, 'rt') as f:
            for line in f:
                if "40000018:2" in line:
                    burst = 1
                    break
        f.close()

    if burst == 1:
        mode_trace = 'Burst'
    else:
        mode_trace = 'Detailed'

    if os.path.exists(file_pcf):
        with open(file_pcf, 'rb', 0) as file, \
                mmap.mmap(file.fileno(), 0, access=mmap.ACCESS_READ) as s:
            if s.find(b'   500000') != -1:
                mode_trace += '+MPI'
                if s.find(b'   610000') != -1:
                    mode_trace += '+Pthreads'
                elif s.find(b'   60000') != -1:
                    mode_trace += '+OpenMP'
                if s.find(b'   630000') != -1 or s.find(b'   631000') != -1 or s.find(b'   632000') != -1:
                    mode_trace += '+CUDA'
                if s.find(b'   9200001') != -1:
                    mode_trace += '+OmpSs'
                if s.find(b'   642000') != -1 or s.find(b'   6400001') != -1 or s.find(b'   641000') != -1:
                    mode_trace += '+OpenCL'
            else:
                if s.find(b'   610000') != -1:
                    mode_trace += '+Pthreads'
                elif s.find(b'   60000') != -1:
                    mode_trace += '+OpenMP'
                if s.find(b'   630000') != -1 or s.find(b'   631000') != -1 or s.find(b'   632000') != -1:
                    mode_trace += '+CUDA'
                if s.find(b'   9200001') != -1:
                    mode_trace += '+OmpSs'
                if s.find(b'   642000') != -1 or s.find(b'   6400001') != -1 or s.find(b'   641000') != -1:
                    mode_trace += '+OpenCL'
        file.close()
    else:
        count_mpi = 0
        count_omp = 0
        count_pthreads = 0
        count_cuda = 0
        count_ompss = 0
        count_opencl = 0
        if prv_file[-4:] == ".prv":
            tracefile = open(prv_file)
            for line in tracefile:
                line_event = line.split(':')
                if line_event[0] == '2':
                    if "500000" in line_event[6]:
                        count_mpi = 1
                        mpi_trace = '+MPI'
                    elif "60000" in line_event[6] and "60000020" not in line_event[6] \
                            and "60000120" not in line_event[6]:
                        count_omp = 1
                        omp_trace = '+OpenMP'
                    elif "610000" in line_event[6]:
                        count_pthreads = 1
                        pthreads_trace = '+Pthreads'
                    elif "630000" in line_event[6] or "631000" in line_event[6] or "632000" in line_event[6]:
                        count_cuda = 1
                        cuda_trace = '+CUDA'
                    elif "9200001" in line_event[6]:
                        count_ompss = 1
                        ompss_trace = '+OmpSs'
                    elif "642000" in line_event[6] or "6400001" in line_event[6] or "641000" in line_event[6]:
                        count_opencl = 1
                        opencl_trace = '+OpenCL'
            tracefile.close()
        elif prv_file[-7:] == ".prv.gz":
            with gzip.open(prv_file, 'rt') as f:
                for line in f:
                    line_event = line.split(':')
                    if line_event[0] == '2':
                        if "500000" in line_event[6]:
                            count_mpi = 1
                            mpi_trace = '+MPI'
                        elif "60000" in line_event[6] and "60000020" not in line_event[6] \
                                and "60000120" not in line_event[6]:
                            count_omp = 1
                            omp_trace = '+OpenMP'
                        elif "610000" in line_event[6]:
                            count_pthreads = 1
                            pthreads_trace = '+Pthreads'
                        elif "630000" in line_event[6] or "631000" in line_event[6] or "632000" in line_event[6]:
                            count_cuda = 1
                            cuda_trace = '+CUDA'
                        elif "9200001" in line_event[6]:
                            count_ompss = 1
                            ompss_trace = '+OmpSs'
                        elif "642000" in line_event[6] or "6400001" in line_event[6] or "641000" in line_event[6]:
                            count_opencl = 1
                            opencl_trace = '+OpenCL'
            f.close()
        if count_mpi > 0:
            mode_trace += mpi_trace
        if count_omp > 0:
            mode_trace += omp_trace
        if count_pthreads > 0:
            mode_trace += pthreads_trace
        if count_ompss > 0:
            mode_trace += ompss_trace
        if count_cuda > 0:
            mode_trace += cuda_trace
        if count_opencl > 0:
            mode_trace += opencl_trace

    return mode_trace


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
    print('Running modelfactors.py for the following traces:')
    # print('Running', os.path.basename(__file__), 'for the following traces:')

    file_path = os.path.join(os.getcwd(), 'traces_metadata.txt')
    with open(file_path, 'w') as output:
        for index, trace in enumerate(trace_list):
            line = '[' + str(index+1) + '] ' + trace

            tasks, threads = get_tasks_threads(trace)
            line += ', ' + str(trace_processes[trace]) \
                    + '(' + str(tasks) + 'x' + str(threads) + ')' + ' processes'
            line += ', ' + str(trace_task_per_node[trace]) + ' tasks per node'
            line += ', ' + human_readable(os.path.getsize(trace))
            line += ', ' + str(trace_mode[trace]) + ' mode'
            print(line)
            output.write(line + '\n')

    print('======== Output Files: Traces metadata ========')
    print('Traces metadata written to ' + file_path)
    print('')