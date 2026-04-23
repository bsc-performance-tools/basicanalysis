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
import re
from collections import defaultdict, Counter
from typing import Dict, Tuple, List, Optional


TARGET_PAIR_BURST = "40000018:2"
# Byte markers used in PCF files
PCF_SAMPLING = b'    30000'
PCF_MPI = b'   500000'
PCF_PTHREADS = b'   610000'
PCF_OMP = b'   60000'
PCF_OMP_EXCLUDE = b'   60000019'
PCF_CUDA_1 = b'   630000'
PCF_CUDA_2 = b'   631000'
PCF_CUDA_3 = b'   632000'
PCF_OMPSS = b'   9200001'
PCF_OPENCL_1 = b'   642000'
PCF_OPENCL_2 = b'   6400001'
PCF_OPENCL_3 = b'   641000'

# Regex patterns for trace fallback detection
RX_MPI = re.compile(rb'\n2:\w+:\w+:[1-4]:1:\w+:50000\w\w\w:')
RX_OMP = re.compile(rb'\n2:\w+:\w+:[1-3]:[1-3]:\w+:60000018:')
RX_CUDA = re.compile(rb'\n2:\w+:\w+:[1-3]:[1-3]:\w+:630\w\w\w\w\w:')
RX_PTHREADS = re.compile(rb'\n2:\w+:\w+:[1-3]:[1-3]:\w+:610000\w\w:')
RX_OMPSS = re.compile(rb'\n2:\w+:\w+:[1-3]:[1-3]:\w+:9200001:')
RX_OPENCL = re.compile(rb'\n2:\w+:\w+:[1-3]:[1-3]:\w+:64\w\w\w\w\w\w:')
# RX_HIP = re.compile(rb'\n2:\w+:\w+:[1-3]:[1-3]:\w+:635\w\w\w\w\w:')


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
    #print("header_trace: ", header_trace[1].split('(')[2].split(')')[0].split(','))
    threads_per_task_per_node = header_trace[1].split('(')[2].split(')')[0].split(',')
    first_elements = [int(item.split(':')[0]) for item in threads_per_task_per_node]
    #print("first_elements: ",max(first_elements))
    header_to_print = header_trace[1].split(':')[3].split('(')
    #print("header_to_print: ", header_to_print)
    tasks = header_to_print[0]
    threads = max(first_elements)
    #threads = header_to_print[1]

    return int(tasks), int(threads)


def get_task_per_node(prv_file):
    """Gets the number of processes and nodes in a trace from the 
    corresponding .prv or .row file. If .row exists, tasks and nodes
     are taken from row; otherwise, they are taken from .prv.
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


def get_device_count(prv_file):
    """Gets the count of *node+device* from row files.
    Now we distinguish devices by node too:
      CUDA-D1.S1-as04r1b15  -> as04r1b15:D1
      CUDA-D1.S1-as04r1b16  -> as04r1b16:D1
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

    devices = set()
    if row_file:
        # NEW: capture both D# and node from lines like:
        #   CUDA-D1.S2-as04r1b15
        #        ^^^       ^^^^^
        #        D1        as04r1b15
        pattern = re.compile(r"CUDA-(D\d+)\.[^-]*-([^\s]+)")
        for line in tracefile:
            match = pattern.search(line)
            if match:
                dev  = match.group(1)   # e.g. "D1"
                node = match.group(2)   # e.g. "as04r1b15"
                key = f"{node}:{dev}"   # unique per node+device
                devices.add(key)
    else:
        print(".row file is needed to obtain the count of devices.")

    if row_file:
        tracefile.close()
    return len(devices)

def _iter_thread_section_lines(prv_file):
    """Yield stripped lines belonging to the LEVEL THREAD section."""
    in_threads = False

    if prv_file[-4:] == ".prv":
        tracefile = prv_file[:-4] + '.row'
    elif prv_file[-7:] == ".prv.gz":
        tracefile = prv_file[:-7] + '.row'
    
    with open(tracefile, "r", encoding="utf-8") as f:
        for raw in f:
            s = raw.strip()
            if s.startswith("LEVEL THREAD SIZE"):
                in_threads = True
                continue
            if not in_threads:
                continue
            if s.startswith("LEVEL "):  # next section (safety)
                break
            if s:  # skip empty
                yield s


def _parse_row_cpu_nodes(prv_file: str) -> Dict[int, str]:
    """
    Parse LEVEL CPU section from the .row file associated with prv_file.

    Returns:
        { cpu_index: node_name }
    """
    row_file = prv_file[:-4] + ".row" if prv_file.endswith(".prv") else prv_file[:-7] + ".row"

    cpu_to_node: Dict[int, str] = {}
    in_cpu_section = False
    cpu_index = 0

    with open(row_file) as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line:
                continue

            if line.startswith("LEVEL CPU SIZE"):
                in_cpu_section = True
                cpu_index = 0
                continue

            if in_cpu_section and line.startswith("LEVEL "):
                break

            if not in_cpu_section:
                continue

            cpu_index += 1

            # Examples:
            #   1.as07r1b02
            #   01.as07r4b27
            if "." in line:
                _, node = line.split(".", 1)
                cpu_to_node[cpu_index] = node.strip()

    return cpu_to_node


def _node_from_thread_label(thread_label: str, cpu_to_node: Dict[int, str]) -> Optional[str]:
    """
    From:
        THREAD 1.3.1
    infer:
        task_idx = 3
    and return the node for that task.
    """
    m = re.match(r"^THREAD\s+(\d+)\.(\d+)\.(\d+)\s*$", thread_label)
    if not m:
        return None

    task_idx = int(m.group(2))
    return cpu_to_node.get(task_idx)


def get_device_stream_id_mapping(
    prv_file,
    start_id: int = 1,
    pad: int = 3
) -> Dict[str, Tuple[int, List[str]]]:
    """
    Number entries in the THREAD section sequentially:
      - THREAD line -> consumes an ID (ignored for per-device counts)
      - each GPU line -> consumes an ID and is counted for its (node,gpu_uuid)

    Returns:
        { "node:gpu_uuid": (count, [id_str...]) }
      where id_str are zero-padded IDs (e.g., '002').
    """

    THREAD_RE = re.compile(r"^THREAD\s+\d+\.\d+\.\d+\s*$")
    GPU_RE = re.compile(r"^GPU_([^.]+)(?:\.(\d+))?\s*$")

    dev_to_ids: Dict[str, List[str]] = defaultdict(list)
    next_id = start_id

    cpu_to_node = _parse_row_cpu_nodes(prv_file)
    current_thread = None

    def fmt(n: int) -> str:
        return str(n).zfill(pad)

    for s in _iter_thread_section_lines(prv_file):
        s = s.strip()

        if THREAD_RE.match(s):
            current_thread = s
            _ = fmt(next_id)   # THREAD line consumes an ID
            next_id += 1
            continue

        m = GPU_RE.match(s)
        if m:
            gpu_uuid = m.group(1)

            node = _node_from_thread_label(current_thread, cpu_to_node) if current_thread else None
            if node is not None:
                key = f"{node}:{gpu_uuid}"
                dev_to_ids[key].append(fmt(next_id))

            next_id += 1

    out: Dict[str, Tuple[int, List[str]]] = {}

    def dev_sort_key(k: str):
        # k example: "as07r4b27:a2f80454"
        node, gpu_uuid = k.split(":", 1)
        return (node, gpu_uuid)

    for key in sorted(dev_to_ids.keys(), key=dev_sort_key):
        ids_sorted = sorted(dev_to_ids[key], key=lambda x: int(x))
        out[key] = (len(ids_sorted), ids_sorted)

    return out

def _open_trace_text(prv_file):
    """Open .prv or .prv.gz as text."""
    if prv_file.endswith(".prv"):
        return open(prv_file, "rt")
    if prv_file.endswith(".prv.gz"):
        return gzip.open(prv_file, "rt")
    raise ValueError(f"Unsupported trace format: {prv_file}")


def _open_trace_binary(prv_file):
    """Open .prv or .prv.gz as binary stream."""
    if prv_file.endswith(".prv"):
        return open(prv_file, "rb")
    if prv_file.endswith(".prv.gz"):
        return gzip.open(prv_file, "rb")
    raise ValueError(f"Unsupported trace format: {prv_file}")


def _detect_burst_mode(prv_file):
    """
    Detect Burst mode by scanning event pairs in the trace.
    Returns 'Burst' or 'Detailed'.
    """
    with _open_trace_text(prv_file) as tracefile:
        for line in tracefile:
            line_splitted = line.split(":")
            if line_splitted[0] != "2" or len(line_splitted) <= 6:
                continue

            values = line_splitted[6:]
            for i in range(0, len(values) - 1, 2):
                if values[i] == "40000018" and values[i + 1].strip() == "2":
                    return "Burst"

    return "Detailed"


def _detect_mode_from_pcf(file_pcf, base_mode):
    """
    Detect trace programming model from .pcf file.
    Returns a mode string like:
    'Sampling'
    'Detailed+MPI+CUDA'
    'Burst+MPI+OpenMP'
    """
    mode_trace = base_mode

    with open(file_pcf, 'rb', 0) as file_obj, \
            mmap.mmap(file_obj.fileno(), 0, access=mmap.ACCESS_READ) as mm:

        if mm.find(PCF_SAMPLING) != -1:
            return 'Sampling'

        has_mpi = mm.find(PCF_MPI) != -1
        has_pthreads = mm.find(PCF_PTHREADS) != -1
        has_omp = (mm.find(PCF_OMP) != -1 and
                   mm.find(PCF_OMP_EXCLUDE) != mm.find(PCF_OMP))
        has_cuda = (mm.find(PCF_CUDA_1) != -1 or
                    mm.find(PCF_CUDA_2) != -1 or
                    mm.find(PCF_CUDA_3) != -1)
        has_ompss = mm.find(PCF_OMPSS) != -1
        has_opencl = (mm.find(PCF_OPENCL_1) != -1 or
                      mm.find(PCF_OPENCL_2) != -1 or
                      mm.find(PCF_OPENCL_3) != -1)

    if has_mpi:
        mode_trace += '+MPI'
    if has_pthreads:
        mode_trace += '+Pthreads'
    elif has_omp:
        mode_trace += '+OpenMP'

    if has_cuda:
        mode_trace += '+CUDA'
    if has_ompss:
        mode_trace += '+OmpSs'
    if has_opencl:
        mode_trace += '+OpenCL'
    # if has_hip:
    #     mode_trace += '+HIP'

    return mode_trace


def _detect_mode_from_trace_streaming(prv_file, base_mode, chunk_size=8 * 1024 * 1024, overlap=1024):
    """
    Fallback detection from the trace itself.
    Reads .prv/.prv.gz in chunks instead of loading the whole file.
    """
    mode_trace = base_mode

    found_mpi = False
    found_omp = False
    found_cuda = False
    found_pthreads = False
    found_ompss = False
    found_opencl = False
    # found_hip = False

    tail = b''

    with _open_trace_binary(prv_file) as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break

            data = tail + chunk

            if not found_mpi and RX_MPI.search(data):
                found_mpi = True
            if not found_omp and RX_OMP.search(data):
                found_omp = True
            if not found_cuda and RX_CUDA.search(data):
                found_cuda = True
            if not found_pthreads and RX_PTHREADS.search(data):
                found_pthreads = True
            if not found_ompss and RX_OMPSS.search(data):
                found_ompss = True
            if not found_opencl and RX_OPENCL.search(data):
                found_opencl = True
            # if not found_hip and RX_HIP.search(data):
            #     found_hip = True

            if (found_mpi and found_omp and found_cuda and found_pthreads and
                    found_ompss and found_opencl):
                break

            tail = data[-overlap:]

    if found_mpi:
        mode_trace += '+MPI'
    if found_pthreads:
        mode_trace += '+Pthreads'
    elif found_omp:
        mode_trace += '+OpenMP'

    if found_cuda:
        mode_trace += '+CUDA'
    if found_ompss:
        mode_trace += '+OmpSs'
    if found_opencl:
        mode_trace += '+OpenCL'
    # if found_hip:
    #     mode_trace += '+HIP'

    return mode_trace


def get_trace_mode(prv_file, cmdl_args, trace_mode):
    """
    Gets the trace mode by detecting:
      - Burst vs Detailed from trace events
      - Programming model from .pcf if available and requested
      - Otherwise fallback to trace-content detection
    """
    if prv_file.endswith(".prv"):
        file_pcf = prv_file[:-4] + '.pcf'
    elif prv_file.endswith(".prv.gz"):
        file_pcf = prv_file[:-7] + '.pcf'
    else:
        raise ValueError(f"Unsupported trace format: {prv_file}")

    base_mode = _detect_burst_mode(prv_file)

    if os.path.exists(file_pcf) and cmdl_args.trace_mode_detection == 'pcf':
        mode_trace = _detect_mode_from_pcf(file_pcf, base_mode)
    else:
        mode_trace = _detect_mode_from_trace_streaming(prv_file, base_mode)

    trace_mode[prv_file] = mode_trace
