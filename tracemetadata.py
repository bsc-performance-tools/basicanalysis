#!/usr/bin/env python3

"""Functions to extract metadata information from each trace."""

from __future__ import print_function, division
import os
import sys
import math
import fnmatch
import re
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
        #if trace[-7:] == ".prv.gz":
        #    cmd_normal = ['gunzip', trace]
        #    run_command(cmd_normal)

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

def get_tasks_threads(prv_file):
    """Gets the app, tasks and threads from the .row file.
      """
    if prv_file[-4:] == ".prv":
        tracefile = open(prv_file[:-4] + '.row')
    elif prv_file[-7:] == ".prv.gz":
        tracefile = open(prv_file[:-7] + '.row')

    start_threads = False
    for line in tracefile:
        if "LEVEL THREAD SIZE" in line:
            start_threads = True
        elif start_threads:
            tasks_found = re.split(r'\.(.+?)\.', line)

    tracefile.close()

    app = re.split(r'\s', tasks_found[0])[1]
    tasks = tasks_found[1]
    threads = tasks_found[2]
    return int(app), int(tasks), int(threads)


def get_trace_mode(prv_file):
    """Gets the trace mode by detecting the event 40000018:2 in .prv file
    to detect the Burst mode trace in another case is Detailed mode.
    50000001 for MPI, 60000001 for OpenMP, 61000000 for pthreads, 63000001 for CUDA
    """
    mode_trace = ''
    burst = 0

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

    with open(file_pcf, 'rb', 0) as file, \
        mmap.mmap(file.fileno(), 0, access=mmap.ACCESS_READ) as s:
        if s.find(b'500000') != -1:
            mode_trace += '+MPI'
            if s.find(b'600000') != -1:
                mode_trace += '+OpenMP'
            if s.find(b'610000') != -1:
                mode_trace += '+Pthreads'
            if s.find(b'630000') != -1 or s.find(b'631000') != -1 or s.find(b'632000') != -1:
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
            if s.find(b'630000') != -1 or s.find(b'631000') != -1 or s.find(b'632000') != -1:
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
    print('Running modelfactors.py for the following traces:')
    # print('Running', os.path.basename(__file__), 'for the following traces:')

    for index, trace in enumerate(trace_list):
        line = '(' + str(index+1) + ') ' + trace
        line += ', ' + str(trace_processes[trace]) + ' processes'
        line += ', ' + str(trace_task_per_node[trace]) + ' tasks per node'
        line += ', ' + human_readable(os.path.getsize(trace))
        line += ', ' + str(trace_mode[trace]) + ' mode'
        print(line)
    print('')