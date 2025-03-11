#!/usr/bin/env python3

"""Functions to extract metadata information from each trace."""

from __future__ import print_function, division
import os
import time
import sys
import math
import re
import fnmatch
import mmap
import gzip
import multiprocessing
import threading
from multiprocessing import Process


def get_traces_from_args(cmdl_args):
    """Filters the given list to extract traces, i.e. matching *.prv and sorts
    the traces in ascending order based on the number of processes in the trace.
    Excludes all files other than *.prv and ignores also simulated traces from
    this script, i.e. *.sim.prv
    Returns list of trace paths and dictionary with the number of processes.
    """

    def get_processes(prv_file):
        return trace_processes[prv_file], trace_tasks[prv_file], trace_threads[prv_file]

    trace_list = [x for x in cmdl_args.trace_list if (fnmatch.fnmatch(x, '*.prv') or fnmatch.fnmatch(x, '*.prv.gz'))
                  if not fnmatch.fnmatch(x, '*.sim.prv')]
    if not trace_list:
        print('==Error== could not find any traces matching "', ' '.join(cmdl_args.trace_list))
        sys.exit(1)

    trace_processes = dict()
    trace_tasks = dict()
    trace_threads = dict()
    trace_mode = dict()
    trace_task_per_node = dict()

    trace_list_temp = []
    trace_list_removed = []
    for trace in trace_list:
        if float(os.path.getsize(trace)/1024/1024) < float(cmdl_args.max_trace_size):
            trace_list_temp.append(trace)
        else:
            trace_list_removed.append(trace)

    if len(trace_list_temp) < 1:
        print('==Error== All traces exceed the maximum size (', cmdl_args.max_trace_size, 'MiB)')
        for trace_upper in trace_list_removed:
            print(trace_upper)
        sys.exit(1)

    print("Running modelfactors.py for the following traces list:")
    trace_list = trace_list_temp
    for trace in trace_list:
        print(trace)

    if len(trace_list_removed) > 0:
        print("\nFollowing traces were excluded to be analyzed (size >", cmdl_args.max_trace_size, "MiB): ")
        for trace in trace_list_removed:
            print(trace)

    print('\nExtracting metadata from the traces list.')
    # This part could be parallelized
    # t1 = time.perf_counter()

    for trace in trace_list:
        trace_processes[trace], trace_tasks[trace], trace_threads[trace] = get_num_processes(trace,cmdl_args)

    if cmdl_args.order_traces == 'yes':
        trace_list = sorted(trace_list, key=get_processes)

    t1 = time.perf_counter()
    jobs = []
    manager = multiprocessing.Manager()
    trace_mode = manager.dict()
    for trace in trace_list:
        p_act = Process(target=get_trace_mode, args=(trace, cmdl_args, trace_mode))
        jobs.append(p_act)
        p_act.start()

    for p in jobs:
        p.join()

    t2 = time.perf_counter()

    print('Successfully Metadata Extraction in {0:.1f} seconds.\n'.format(t2 - t1))

    #trace_list_wo_sampling = []
    #for trace in trace_list:
    #    if trace_mode[trace] != 'Sampling':
    #        trace_list_wo_sampling.append(trace)
    #    else:
    #        print("WARNING!!! Modelfactors does not compute metrics for Sampling tracing mode")
    #       print("Trace ", trace, " excluded from the analysis")

    #trace_list = trace_list_wo_sampling
    #if len(trace_list) == 0:
    #    print("All traces were excluded from the analysis")
    #    print("Finishing execution without metrics calculation")
    #    sys.exit(1)

    for trace in trace_list:
        trace_task_per_node[trace] = get_task_per_node(trace)
           
    print("Starting Analysis for the following sorted traces list:")
    print_overview(trace_list, trace_processes, trace_tasks, trace_threads, trace_mode, trace_task_per_node)
    return trace_list, trace_processes, trace_tasks, trace_threads, trace_task_per_node, trace_mode


def get_num_processes(prv_file, cmdl_args):
    """Gets the number of processes in a trace from the according .row file.
    Please note: return value needs to be integer because this function is also
    used as sorting key.
    """
    file_trace_name = "not found"
    if prv_file[-4:] == ".prv":
        tracefile = open(prv_file)
        file_trace_name = prv_file[:-4]+".prv"
        for line in tracefile:
            header_trace = line.split('_')
            break
        tracefile.close()
    elif prv_file[-7:] == ".prv.gz":
        file_trace_name = prv_file[:-4] + ".prv.gz"
        with gzip.open(prv_file, 'rt') as f:
            for line in f:
                if "#Paraver" in line:
                    header_trace = line.split('_')
                    break
        f.close()

    if cmdl_args.debug:
        #if file_trace_name == "not found":
        print("Trace File ", prv_file)

    header_to_print = header_trace[1].split(':')[3].split('(')
    tasks = header_to_print[0]
    threads = header_to_print[1]
    list_procspernode = header_trace[1].split('(')[2].split(')')[0].split(',')

    total_procs = 0
    for proc_node in list_procspernode:
        total_procs += int(proc_node.split(':')[0])

    return int(total_procs), int(tasks), int(threads)


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


def get_trace_mode(prv_file, cmdl_args, trace_mode):
    """Gets the trace mode by detecting the event 40000018:2 in .prv file
    to detect the Burst mode trace in another case is Detailed mode.
    50000001 for MPI, 60000001 for OpenMP, 61000000 for pthreads, 63000001 for CUDA
    """
    mode_trace = ''
    burst = 0
    target_pair_burst = "40000018:2"
    pcf_file = True
    if prv_file[-4:] == ".prv":
        file_pcf = prv_file[:-4] + '.pcf'
        tracefile = open(prv_file)
        for line in tracefile:
            line_splitted = line.split(":")
            if (line_splitted[0] == "2") and (len(line_splitted) > 6):  # Ensure there are at least 6 elements
                values = line_splitted[6:]  # Get everything from the 6th value onward
                # Check in pairs (step = 2)
                for i in range(0, len(values) - 1, 2):
                    pair = f"{values[i]}:{values[i + 1]}"  # Form "key:value" pair
                    if pair == target_pair_burst:
                        burst = 1
                        break
                if burst == 1:
                   break
        tracefile.close()

    if prv_file[-7:] == ".prv.gz":
        file_pcf = prv_file[:-7] + '.pcf'
        with gzip.open(prv_file, 'rt') as f:
            for line in f:
                line_splitted = line.split(":")
                if (line_splitted[0] == "2") and (len(line_splitted) > 6):  # Ensure there are at least 6 elements
                    values = line_splitted[6:]  # Get everything from the 6th value onward
                    # Check in pairs (step = 2)
                    for i in range(0, len(values) - 1, 2):
                        pair = f"{values[i]}:{values[i + 1]}"  # Form "key:value" pair
                        if pair == target_pair_burst:
                            burst = 1
                            break
                    if burst == 1:
                        break
        f.close()

    if burst == 1:
        mode_trace = 'Burst'
    else:
        mode_trace = 'Detailed'

    if os.path.exists(file_pcf) and cmdl_args.trace_mode_detection == 'pcf':
        with open(file_pcf, 'rb', 0) as file, \
                mmap.mmap(file.fileno(), 0, access=mmap.ACCESS_READ) as s:
            #print(s.find(b'    30000'))
            if s.find(b'    30000') != -1:
                mode_trace = 'Sampling'
            elif s.find(b'   500000') != -1:
                mode_trace += '+MPI'
                if s.find(b'   610000') != -1:
                    mode_trace += '+Pthreads'
                elif s.find(b'   60000') != -1:
                    if not s.find(b'   60000019') == s.find(b'   60000'):
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
                    if not s.find(b'   60000019') == s.find(b'   60000'):
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
            with open(prv_file, 'rb', 0) as file, \
                    mmap.mmap(file.fileno(), 0, access=mmap.ACCESS_COPY) as s:
                # 2:cpu_id:appl_id:task_id:thread_id:time:event_type:event_value
                mpi = re.compile(rb'\n2:\w+:\w+:[1-4]:1:\w+:50000\w\w\w:')
                omp = re.compile(rb'\n2:\w+:\w+:[1-3]:[1-3]:\w+:60000018:')
                cuda = re.compile(rb'\n2:\w+:\w+:[1-3]:[1-3]:\w+:63\w\w\w\w\w\w:')
                pthreads = re.compile(rb'\n2:\w+:\w+:[1-3]:[1-3]:\w+:610000\w\w:')
                ompss = re.compile(rb'\n2:\w+:\w+:[1-3]:[1-3]:\w+:9200001:')
                opencl = re.compile(rb'\n2:\w+:\w+:[1-3]:[1-3]:\w+:64\w\w\w\w\w\w:')
                if mpi.search(s):
                    count_mpi = 1
                    mpi_trace = '+MPI'
                if omp.search(s):
                    count_omp = 1
                    omp_trace = '+OpenMP'
                elif cuda.search(s):
                    count_cuda = 1
                    cuda_trace = '+CUDA'
                elif pthreads.search(s):
                    count_pthreads = 1
                    pthreads_trace = '+Pthreads'
                elif ompss.search(s):
                    count_ompss = 1
                    ompss_trace = '+OmpSs'
                elif opencl.search(s):
                    count_opencl = 1
                    opencl_trace = '+OpenCL'
            file.close()
        elif prv_file[-7:] == ".prv.gz":
            handle = open(prv_file, "rb")
            mapped = mmap.mmap(handle.fileno(), 0, access=mmap.ACCESS_READ)
            gzfile = gzip.GzipFile(mode="r", fileobj=mapped)

            # 2:cpu_id:appl_id:task_id:thread_id:time:event_type:event_value
            mpi = re.compile(rb'\n2:\w+:\w+:[1-4]:1:\w+:50000\w\w\w:')
            omp = re.compile(rb'\n2:\w+:\w+:[1-3]:[1-3]:\w+:60000018:')
            cuda = re.compile(rb'\n2:\w+:\w+:[1-3]:[1-3]:\w+:63\w\w\w\w\w\w:')
            pthreads = re.compile(rb'\n2:\w+:\w+:[1-3]:[1-3]:\w+:610000\w\w:')
            ompss = re.compile(rb'\n2:\w+:\w+:[1-3]:[1-3]:\w+:9200001:')
            opencl = re.compile(rb'\n2:\w+:\w+:[1-3]:[1-3]:\w+:64\w\w\w\w\w\w:')
            s = gzfile.read()
            if mpi.search(s):
                count_mpi = 1
                mpi_trace = '+MPI'
            if omp.search(s):
                count_omp = 1
                omp_trace = '+OpenMP'
            elif cuda.search(s):
                count_cuda = 1
                cuda_trace = '+CUDA'
            elif pthreads.search(s):
                count_pthreads = 1
                pthreads_trace = '+Pthreads'
            elif ompss.search(s):
                count_ompss = 1
                ompss_trace = '+OmpSs'
            elif opencl.search(s):
                count_opencl = 1
                opencl_trace = '+OpenCL'

            handle.close()
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

    trace_mode[prv_file] = mode_trace
    #return mode_trace


def human_readable(size, precision=1):
    """Converts a given size in bytes to the value in human readable form."""
    suffixes = ['B', 'KB', 'MB', 'GB', 'TB']
    suffixIndex = 0
    while size > 1024 and suffixIndex < 4:
        suffixIndex += 1
        size = size / 1024.0
    return "%.*f%s" % (precision, size, suffixes[suffixIndex])


def print_overview(trace_list, trace_processes, trace_tasks, trace_threads, trace_mode, trace_task_per_node):
    """Prints an overview of the traces that will be processed."""
    #print('Running', os.path.basename(__file__), 'for the following traces:')

    file_path = os.path.join(os.getcwd(), 'traces_metadata.txt')
    with open(file_path, 'w') as output:
        for index, trace in enumerate(trace_list):
            line = '[' + str(index+1) + '] ' + trace

            line += ', ' + str(trace_processes[trace]) \
                    + '(' + str(trace_tasks[trace]) + 'x' + str(trace_threads[trace]) + ')' + ' processes'
            line += ', ' + str(trace_task_per_node[trace]) + ' tasks per node'
            line += ', ' + human_readable(os.path.getsize(trace))
            line += ', ' + str(trace_mode[trace]) + ' mode'
            print(line)
            output.write(line + '\n')

    print('======== Output Files: Traces metadata ========')
    print('Traces metadata written to ' + file_path)
    print('')