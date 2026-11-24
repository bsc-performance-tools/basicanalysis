#!/usr/bin/env python3

"""Raw data of Paraver traces generated with nsys2prv.

nsys2prv converts NVIDIA Nsight Systems reports to Paraver traces. These
traces differ from Extrae traces in their content, not only in their format:

  - They contain no state records, only events.
  - The header declares 0 nodes and no CPUs, and the .row file has no
    LEVEL CPU section.
  - GPU stream labels do not include the node (CUDA-D0.S7), and each GPU has
    an additional thread with sampled hardware metrics (Metrics GPU0).
  - Some event types reuse Extrae numbers with a different meaning
    (e.g. 63000001 is a memory copy, 63000007 an NCCL kernel).

They are analyzed with their own configurations (cfgs/nsys2prv/) so that the
Extrae workflow is not affected. The results use the same raw data keys as
the Host/Device model of GPU applications without MPI.

Device activity on the GPU stream threads, following the TALP device
model (kernel computation, memory operations, idle):

  Useful time (U):     CUDA kernels (63000006).
  Communication (M):   memory operations, i.e. memory copies and memset
                       (63000001 = 3, 4, 5, 6), and NCCL kernels (63000007),
                       counted only when not overlapped with useful work on
                       the same device.

Host: the host threads are the non-stream threads of the processes with GPU
streams. Processes without GPU streams do not offload work and are not
considered. Without state records, the useful host time of each host thread
is estimated as the elapsed time minus its time inside CUDA runtime and
driver calls (63000000), which includes the time waiting for the GPU in
synchronization calls. In interpreted applications (e.g. Python), this
useful time also includes interpreter, waiting and I/O time.
"""

from __future__ import print_function, division

import os
import re
import time
from collections import OrderedDict, defaultdict

from tracemetadata import (
    NSYS2PRV_MPI_MODE,
    _read_header_line,
    parse_trace_header,
    NSYS2PRV_METRICS_LABEL_RE,
)
from utils import run_command, move_files
import nsys2prvevents


# Values of the CUDA memcpy event (63000001) in nsys2prv traces.
MEMCPY_D2D = 3.0
MEMCPY_D2H = 4.0
MEMCPY_H2D = 5.0
MEMSET = 6.0

# Memory operations: communication (M) in the TALP device model.
MEMORY_OPERATION_VALUES = (MEMCPY_D2D, MEMCPY_D2H, MEMCPY_H2D, MEMSET)

# The nsys2prv configurations export the timelines in nanoseconds, so that
# the sum of many short kernels is not affected by rounding.
NS_PER_US = 1000.0

# nsys2prv stream label: CUDA-D0.S7. A node suffix (CUDA-D0.S7-node) is
# also accepted.
NSYS2PRV_STREAM_LABEL_RE = re.compile(
    r"^(?:CUDA|HIP)-(D\d+)\.S(\d+)(?:-(\S+))?\s*$"
)

# GPU hardware counters sampled by Nsight Systems (--gpu-metrics-devices)
# on the Metrics GPU<n> thread of each device, every 100 us by default.
# Each cfg (cfgs/nsys2prv/hwc_<key>.cfg) integrates one counter over the
# whole trace (value x ns). The SM, warp and tensor counters are nested in
# GR Active and are integrated as they are; the DRAM and clock counters are
# integrated multiplied by GR Active, to obtain averages weighted by the
# GPU activity. The DRAM counters are also integrated as they are: these
# integrals are not used by the metrics, but are written to rawdata.csv as
# the amount of data read and written relative to the peak bandwidth.
HWC_COUNTERS = (
    # key, event, nsys2prv label
    ('gr_active', 9402, 'GR Active [Throughput %]'),
    ('sms_active', 9403, 'SMs Active [Throughput %]'),
    ('sm_issue', 9404, 'SM Issue [Throughput %]'),
    ('tensor_active', 9405, 'Tensor Active [Throughput %]'),
    ('warps_in_flight', 9412, 'Compute Warps in Flight [Throughput %]'),
    ('unallocated_warps', 9415, 'Unallocated Warps in Active SMs [Throughput %]'),
    ('dram_read', 9418, 'DRAM Read Bandwidth [Throughput %] x GR Active'),
    ('dram_write', 9419, 'DRAM Write Bandwidth [Throughput %] x GR Active'),
    ('gpc_clock', 9400, 'GPC Clock Frequency x GR Active'),
    ('dram_read_unweighted', 9418, 'DRAM Read Bandwidth [Throughput %]'),
    ('dram_write_unweighted', 9419, 'DRAM Write Bandwidth [Throughput %]'),
)

HWC_KEYS = tuple(key for key, _event, _label in HWC_COUNTERS)

# Integrals that are only written to rawdata.csv. The metrics do not need
# them, so results saved before they existed still give the metrics.
HWC_RAW_ONLY_KEYS = ('dram_read_unweighted', 'dram_write_unweighted')

# Raw data of the hardware counters. They are only printed in rawdata.csv
# when a trace has them, so that the raw data of Extrae traces is unchanged.
hwc_raw_data_doc = OrderedDict(
    [('hwc_devices', 'GPUs with sampled hardware counters'),
     ('hwc_elapsed', 'Elapsed time of the hardware counter integrals (us)')]
    + [('hwc_' + key + '_int', 'Integral of ' + label + ' (value x ns)')
       for key, _event, label in HWC_COUNTERS]
)

# Device hardware counter metrics (computed from hwc_raw_data_doc).
mod_device_hwc_factors_doc = OrderedDict([
    ('dev_hwc_gpu_active', 'GPU Active (HW counters)'),
    ('dev_hwc_sm_utilization', 'SM Utilization'),
    ('dev_hwc_sm_coverage', '-- SM Coverage'),
    ('dev_hwc_sm_issue_eff', '-- SM Issue Efficiency'),
    ('dev_hwc_achieved_occupancy', 'Achieved Occupancy (run average)'),
    ('dev_hwc_tensor_activity', 'Tensor Core Activity'),
    ('dev_hwc_dram_read', 'DRAM Read Bandwidth'),
    ('dev_hwc_dram_write', 'DRAM Write Bandwidth'),
    ('dev_hwc_gpc_clock', 'GPC Clock (MHz)'),
])

# nsys2prv records the GPC clock (9400) in Hz although its label says MHz.
# Averages above this value are taken as Hz.
HWC_CLOCK_HZ_THRESHOLD = 1.0e5



def init_nsys2prv_cfgs(root_dir):
    """Return the paths of the configurations used for nsys2prv traces."""
    nsys_dir = os.path.join(root_dir, 'nsys2prv')
    cfgs = {
        'runtime': os.path.join(root_dir, 'runtime_app.cfg'),
        'kernels_streams': os.path.join(nsys_dir, 'kernels_streams.cfg'),
        'memcpy_streams': os.path.join(nsys_dir, 'memcpy_streams.cfg'),
        'nccl_streams': os.path.join(nsys_dir, 'nccl_streams.cfg'),
        'cuda_calls_host': os.path.join(nsys_dir, 'cuda_calls_host.cfg'),
        # Traces with MPI events (nsys2prv -t mpi_event_trace).
        'mpi_outside_host': os.path.join(nsys_dir, 'mpi_outside_host.cfg'),
        'cuda_calls_in_mpi': os.path.join(nsys_dir, 'cuda_calls_in_mpi.cfg'),
    }
    for key in HWC_KEYS:
        cfgs['hwc_' + key] = os.path.join(nsys_dir, 'hwc_' + key + '.cfg')
    return cfgs


def _read_row_sections(row_path):
    """Return {level: [labels]} from a .row file."""
    sections = defaultdict(list)
    level = None

    with open(row_path) as row_file:
        for raw_line in row_file:
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith('LEVEL '):
                level = line.split()[1]
                continue
            if level is not None:
                sections[level].append(line)

    return sections


def classify_nsys2prv_threads(prv_file, row_path):
    """Classify the threads of an nsys2prv trace from its .row file.

    The LEVEL THREAD labels are positional: the i-th label is the i-th
    thread of the header, task by task.

    Returns:
      {
        'streams':  {thread_obj: device_key},
        'metrics':  [thread_obj, ...],
        'host':     [thread_obj, ...],
        'gpu_tasks': set of task ids with GPU streams,
        'gpu_host': [thread_obj, ...] host threads of the gpu_tasks,
        'streams_per_task': {task_id: number of streams},
        'labels':   [(thread_obj, .row label), ...] in thread order,
      }
    where thread_obj is 'THREAD appl.task.thread' and device_key is
    '<node>:<device>'.
    """
    header = parse_trace_header(prv_file)
    sections = _read_row_sections(row_path)
    thread_labels = sections.get('THREAD', [])
    node_names = sections.get('NODE', [])

    thread_objects = []
    thread_nodes = []
    for task_id, (n_threads, node_id) in enumerate(
            zip(header['threads_per_task'], header['node_per_task']), start=1):
        if 1 <= node_id <= len(node_names):
            node = node_names[node_id - 1]
        else:
            node = 'node' + str(node_id)
        for thread_id in range(1, n_threads + 1):
            thread_objects.append('THREAD 1.{}.{}'.format(task_id, thread_id))
            thread_nodes.append(node)

    result = {
        'streams': {},
        'metrics': [],
        'host': [],
        'gpu_tasks': set(),
        'gpu_host': [],
        'streams_per_task': defaultdict(int),
        'labels': [],
    }

    for thread_obj, node, label in zip(thread_objects, thread_nodes, thread_labels):
        result['labels'].append((thread_obj, label))
        match = NSYS2PRV_STREAM_LABEL_RE.match(label)
        if match:
            device = match.group(1)
            stream_node = match.group(3) or node
            result['streams'][thread_obj] = '{}:{}'.format(stream_node, device)
            task_id = _task_of(thread_obj)
            result['gpu_tasks'].add(task_id)
            result['streams_per_task'][task_id] += 1
        elif NSYS2PRV_METRICS_LABEL_RE.match(label):
            result['metrics'].append(thread_obj)
        else:
            result['host'].append(thread_obj)

    result['gpu_host'] = [
        thread_obj for thread_obj in result['host']
        if _task_of(thread_obj) in result['gpu_tasks']
    ]
    result['streams_per_task'] = dict(result['streams_per_task'])
    _resolve_gpu_identity(result)

    return result


def _resolve_gpu_identity(result):
    """Decide how the GPU streams are grouped into physical GPUs.

    By default a GPU is '<node>:<device>'. nsys2prv traces merged from
    several nodes may place every process on the same node, so GPUs with the
    same device number on different nodes would be merged. Each physical GPU
    is sampled by a single profiling session (only one tool can subscribe to
    the GPU counters), so more 'Metrics GPU<n>' threads than '<node>:<device>'
    GPUs means that the node information is missing: each process then has
    its own GPUs ('<node>:T<task>.<device>'), which assumes that processes do
    not share a GPU.

    Sets result['gpu_identity'] to 'node' or 'process', result['node_gpus']
    to the number of '<node>:<device>' GPUs, and
    result['gpu_shared_unverified'] to True when several processes use the
    same '<node>:<device>' and the trace has no GPU metrics threads to check
    whether they are the same GPU.
    """
    node_gpus = set(result['streams'].values())
    result['node_gpus'] = len(node_gpus)
    result['gpu_identity'] = 'node'
    result['gpu_shared_unverified'] = False

    if len(result['metrics']) > len(node_gpus):
        result['streams'] = {
            thread_obj: '{}:T{}.{}'.format(
                device_key.split(':', 1)[0],
                _task_of(thread_obj),
                device_key.split(':', 1)[1],
            )
            for thread_obj, device_key in result['streams'].items()
        }
        result['gpu_identity'] = 'process'
        return

    tasks_per_gpu = defaultdict(set)
    for thread_obj, device_key in result['streams'].items():
        tasks_per_gpu[device_key].add(_task_of(thread_obj))

    if not result['metrics'] and any(
            len(tasks) > 1 for tasks in tasks_per_gpu.values()):
        result['gpu_shared_unverified'] = True


_HEADER_END_RE = re.compile(r"^#Paraver \([^)]*\):(\d+)(?:_(ns|us))?:")


def trace_header_end_us(prv_file):
    """End time declared in the trace header, in microseconds.

    Returns None when the header has no time unit (the unit cannot be
    known) or cannot be read.
    """
    try:
        match = _HEADER_END_RE.match(_read_header_line(prv_file))
    except (OSError, ValueError):
        return None

    if not match or not match.group(2):
        return None

    value = float(match.group(1))
    return value / NS_PER_US if match.group(2) == 'ns' else value


def _task_of(thread_obj):
    """Return the task id of 'THREAD appl.task.thread'."""
    return int(thread_obj.split()[1].split('.')[1])


def streams_per_task_value(threads):
    """Streams per process with GPU streams: a number, or -1 if non-uniform."""
    values = set(threads['streams_per_task'].values())
    if not values:
        return 0
    return values.pop() if len(values) == 1 else -1


def select_host_units(threads, host_calls):
    """Host execution units of an nsys2prv trace: one per process with GPU
    streams.

    Nsight Systems records every thread of a process, most of them helper
    threads of the CUDA runtime, NCCL or the application that never call
    CUDA. Their time outside CUDA calls is not Host useful computation, so
    each process is represented by the thread that drives its GPUs: the
    host thread with the most time inside CUDA calls (host_calls, from
    parse_nsys2prv_host_calls). If no thread of a process calls CUDA, its
    first host thread is used.

    Returns the selected threads, in thread order.
    """
    by_task = defaultdict(list)
    for thread_obj in threads['gpu_host']:
        by_task[_task_of(thread_obj)].append(thread_obj)

    selected = []
    for task_id in sorted(by_task):
        # max() keeps the first thread on ties, so the choice is stable.
        selected.append(max(by_task[task_id],
                            key=lambda t: host_calls.get(t, 0.0)))
    return selected


NOT_ANALYZED_REASONS = {
    'no_gpu_streams': (
        'its process has no GPU streams, so it does not offload work to the '
        'GPU (for example, a driver or front-end process that only queries '
        'or synchronizes the GPU)'),
    'not_host_unit': (
        'its process is represented by the thread with the most time in '
        'CUDA calls, the thread that drives its GPUs'),
}


# Host threads not analyzed with less than this share of the runtime in
# CUDA calls (helper threads that only initialize or query the GPU) are
# counted in one summary line instead of one line each.
NOT_ANALYZED_MIN_SHARE = 0.01


def host_threads_not_analyzed(threads, host_units, host_calls, runtime=None):
    """Host threads with CUDA calls that are not Host units, with the reason.

    Threads that never call CUDA are not listed. Returns a list of
    {'thread', 'label', 'cuda_calls_s', 'reason', 'minor'} in thread order,
    with the reason a key of NOT_ANALYZED_REASONS. 'minor' is True when the
    thread spends less than NOT_ANALYZED_MIN_SHARE of the runtime (us) in
    CUDA calls; without the runtime no thread is minor.
    """
    labels = dict(threads.get('labels', []))
    units = set(host_units)
    result = []
    for thread_obj in threads.get('host', []):
        calls = host_calls.get(thread_obj, 0.0)
        if thread_obj in units or calls <= 0.0:
            continue
        reason = ('not_host_unit' if _task_of(thread_obj) in threads['gpu_tasks']
                  else 'no_gpu_streams')
        result.append({'thread': thread_obj,
                       'label': labels.get(thread_obj, thread_obj),
                       'cuda_calls_s': calls / 1e6,
                       'reason': reason,
                       'minor': bool(runtime) and
                                calls < NOT_ANALYZED_MIN_SHARE * runtime})
    return result


def not_analyzed_summary(entries):
    """(listed entries, number of minor entries, their time in CUDA calls, s)."""
    listed = [e for e in entries if not e.get('minor')]
    minor = [e for e in entries if e.get('minor')]
    return listed, len(minor), sum(e.get('cuda_calls_s', 0.0) for e in minor)


def not_analyzed_minor_text(count, seconds):
    """Sentence for the threads not listed one by one."""
    return ('{} more host thread{} with less than {:g}% of the runtime each in '
            'CUDA calls ({:.3f} s in total) {} not listed.').format(
                count, '' if count == 1 else 's',
                NOT_ANALYZED_MIN_SHARE * 100, seconds,
                'is' if count == 1 else 'are')


def get_nsys2prv_resources(prv_file):
    """Execution units of an nsys2prv trace, as used in the configuration
    labels: (units, tasks, threads per task).

      units:  one host unit per process with GPU streams + GPU streams
      tasks:  processes with GPU streams
      threads per task: maximum host units + streams of those processes

    Each process with GPU streams has one host unit (select_host_units),
    whatever the number of helper threads recorded by Nsight Systems.

    Returns None if the .row file is not available.
    """
    if prv_file.endswith('.prv.gz'):
        row_path = prv_file[:-7] + '.row'
    else:
        row_path = prv_file[:-4] + '.row'

    if not os.path.exists(row_path):
        return None

    threads = classify_nsys2prv_threads(prv_file, row_path)
    units_per_task = defaultdict(int)
    for thread_obj in threads['streams']:
        units_per_task[_task_of(thread_obj)] += 1
    for task_id in {_task_of(t) for t in threads['gpu_host']}:
        units_per_task[task_id] += 1

    if not units_per_task:
        return None

    return (
        sum(units_per_task.values()),
        len(units_per_task),
        max(units_per_task.values()),
    )


def _execution_mapping_from_streams(stream_to_device):
    """Execution mapping of the GPU streams (same keys as
    tracemetadata.get_execution_mapping). -1 means non-uniform."""
    devices_by_node = defaultdict(int)
    streams_by_node = defaultdict(int)
    streams_by_device = defaultdict(int)
    for device_key in stream_to_device.values():
        streams_by_device[device_key] += 1
    for device_key, count in streams_by_device.items():
        node = device_key.split(':', 1)[0]
        devices_by_node[node] += 1
        streams_by_node[node] += count

    def uniform(values):
        values = set(values)
        if not values:
            return None
        return values.pop() if len(values) == 1 else -1

    return {
        "nodes": len(devices_by_node) or None,
        "mpi_ranks_per_node": None,
        "threads_per_rank": None,
        "threads_per_node": None,
        "gpus_per_node": uniform(devices_by_node.values()),
        "gpu_streams_per_node": uniform(streams_by_node.values()),
        "streams_per_gpu": uniform(streams_by_device.values()),
    }


def get_nsys2prv_execution_mapping(prv_file):
    """Execution mapping of an nsys2prv trace from its .row file."""
    row_path = (prv_file[:-7] if prv_file.endswith('.prv.gz')
                else prv_file[:-4]) + '.row'
    if not os.path.exists(row_path):
        return _execution_mapping_from_streams({})
    threads = classify_nsys2prv_threads(prv_file, row_path)
    return _execution_mapping_from_streams(threads['streams'])


def parse_nsys2prv_host_calls(path, threads):
    """Time inside CUDA calls per thread (microseconds) from the analyzer of
    cuda_calls_host.cfg (exported in nanoseconds).

    The rows are labelled with the .row labels, in thread order.
    Returns {thread_obj: time}.
    """
    values = {}
    if not path or not os.path.exists(path):
        return values

    rows = []
    with open(path) as stats_file:
        next(stats_file, None)  # column header
        for raw_line in stats_file:
            parts = raw_line.rstrip('\n').split('\t')
            if not parts[0].strip():
                break
            try:
                rows.append((parts[0].strip(), float(parts[1])))
            except (IndexError, ValueError):
                break

    labels = threads['labels']
    if len(rows) == len(labels):
        for (thread_obj, _label), (_row, value) in zip(labels, rows):
            values[thread_obj] = value / NS_PER_US
    else:
        # Fall back to the default thread labels (THREAD a.t.h).
        for row_label, value in rows:
            if row_label.startswith('THREAD '):
                values[row_label] = value / NS_PER_US

    return values


MPI_OTHER_TYPE = 50000003
MPI_INIT_VALUE = 31
MPI_FINALIZE_VALUE = 32


def nsys2prv_mpi_region(prv_file):
    """Region of an nsys2prv trace with MPI events that Extrae would record:
    from the end of MPI_Init (the last rank to leave it) to the start of
    MPI_Finalize (the first rank to enter it), in nanoseconds.

    Nsight Systems records the whole process, MPI_Init included, while
    Extrae starts after MPI_Init. The records are not sorted by time in
    merged nsys2prv traces, so the events are sorted per thread.

    Returns (begin, end), with begin 0 when there is no MPI_Init and end
    None when there is no MPI_Finalize, or None when the trace has neither.
    """
    marker = ':{}:'.format(MPI_OTHER_TYPE)
    events = defaultdict(list)
    with open(prv_file) as trace_file:
        trace_file.readline()
        for line in trace_file:
            if line[0] != '2' or marker not in line:
                continue
            parts = line.rstrip('\n').split(':')
            values = parts[6:]
            for i in range(0, len(values) - 1, 2):
                if values[i] == str(MPI_OTHER_TYPE):
                    events[(parts[3], parts[4])].append(
                        (int(parts[5]), int(values[i + 1])))
    init_ends = []
    finalize_starts = []
    for thread_events in events.values():
        thread_events.sort()
        in_init = False
        for timestamp, value in thread_events:
            if value == MPI_INIT_VALUE:
                in_init = True
            elif value == 0 and in_init:
                init_ends.append(timestamp)
                in_init = False
            elif value == MPI_FINALIZE_VALUE:
                finalize_starts.append(timestamp)
    if not init_ends and not finalize_starts:
        return None
    begin = max(init_ends) if init_ends else 0
    end = min(finalize_starts) if finalize_starts else None
    if end is not None and end <= begin:
        return None
    return begin, end


def apply_time_window(text, begin_relative, end_relative):
    """Restrict a Paraver cfg to a time window (relative to the trace end):
    the windows start and end there, and the analyzers use the window
    (Allwindow) instead of the whole trace."""
    lines = []
    for line in text.splitlines(True):
        if line.startswith('window_begin_time_relative '):
            line = 'window_begin_time_relative {:.12f}\n'.format(begin_relative)
        elif line.startswith('window_end_time_relative '):
            line = 'window_end_time_relative {:.12f}\n'.format(end_relative)
        elif line.startswith('Analyzer2D.AnalysisLimits:'):
            line = 'Analyzer2D.AnalysisLimits: Allwindow\n'
        lines.append(line)
    return ''.join(lines)


def nsys2prv_mpi_times(threads, host_units, runtime, outside_mpi,
                       cuda_calls, cuda_in_mpi):
    """MPI time of the processes of an nsys2prv trace with MPI events, and
    the Host useful time of their Host units (microseconds).

    outside_mpi: {thread: time outside MPI calls} (mpi_outside_host.cfg);
    a thread without MPI events has the whole runtime. cuda_calls and
    cuda_in_mpi: {thread: time in CUDA calls} and {thread: time in CUDA
    calls inside MPI calls} (cuda_calls_in_mpi.cfg).

    The MPI rank of a process is represented by its thread with the most
    time in MPI calls (the thread that calls MPI), as the first thread of
    each rank in Extrae traces. The Host useful time of a Host unit is the
    runtime minus its time in CUDA calls or MPI calls, the CUDA calls inside
    MPI calls counted once.

    Returns {'outside_by_task': {task: time}, 'mpi_thread': {task: thread},
             'useful_host': {host unit: time},
             'mpi_host': {host unit: time in MPI}, 'overlap_host': {...}}.
    """
    host_tasks = {_task_of(unit) for unit in host_units}
    mpi_thread = {}
    for thread_obj in threads.get('host', []):
        task = _task_of(thread_obj)
        if task not in host_tasks or thread_obj not in outside_mpi:
            continue
        best = mpi_thread.get(task)
        if best is None or outside_mpi[thread_obj] < outside_mpi[best]:
            mpi_thread[task] = thread_obj
    outside_by_task = {task: outside_mpi[thread_obj]
                       for task, thread_obj in mpi_thread.items()}
    useful_host = {}
    mpi_host = {}
    overlap_host = {}
    for unit in host_units:
        in_mpi = max(runtime - outside_mpi.get(unit, runtime), 0.0)
        overlap = min(cuda_in_mpi.get(unit, 0.0), in_mpi)
        busy = cuda_calls.get(unit, 0.0) + in_mpi - overlap
        useful_host[unit] = max(runtime - busy, 0.0)
        mpi_host[unit] = in_mpi
        overlap_host[unit] = overlap
    return {'outside_by_task': outside_by_task, 'mpi_thread': mpi_thread,
            'useful_host': useful_host, 'mpi_host': mpi_host,
            'overlap_host': overlap_host}


def parse_nsys2prv_hwc_integral(path):
    """Integral of a hardware counter from the analyzer of an hwc_<key>.cfg.

    The rows are labelled with the .row labels; only the Metrics GPU<n>
    rows have values. The integrals of all devices are added.

    Returns (integral, number of devices), or None if the file is missing
    or has no Metrics GPU<n> row.
    """
    if not path or not os.path.exists(path):
        return None

    total = 0.0
    devices = 0
    with open(path) as stats_file:
        next(stats_file, None)  # column header
        for raw_line in stats_file:
            parts = raw_line.rstrip('\n').split('\t')
            if not parts[0].strip():
                break
            if not NSYS2PRV_METRICS_LABEL_RE.match(parts[0].strip()):
                continue
            try:
                total += float(parts[1])
            except (IndexError, ValueError):
                continue
            devices += 1

    if devices == 0:
        return None

    return total, devices


def compute_device_hwc_factors(raw_data, trace):
    """Device hardware counter metrics of one trace.

    With the integrals I_x of the counters over the whole trace (added
    over devices), T the runtime and N the number of devices:

      GPU Active            = I_GR / (N T)
      SM Utilization        = I_SMIssue / I_GR
        SM Coverage         = I_SMsActive / I_GR
        SM Issue Efficiency = I_SMIssue / I_SMsActive
      Achieved Occupancy    = I_WarpsInFlight / I_SMsActive
      Tensor Core Activity  = I_Tensor / I_GR
      DRAM Read/Write       = I_(DRAM x GR) / I_GR
      GPC Clock             = I_(Clock x GR) / I_GR

    SM Utilization = SM Coverage x SM Issue Efficiency. The GR-weighted
    ratios do not need to attribute the samples to kernels: GR Active is
    about 0 while the GPU is idle.

    Returns {metric key: value}, with 'Non-Avail' when the trace has no
    hardware counters and 'NaN' when a ratio cannot be computed.
    """
    factors = OrderedDict((key, 'Non-Avail') for key in mod_device_hwc_factors_doc)

    def raw(key):
        return raw_data.get(key, {}).get(trace, 'Non-Avail')

    integrals = {key: raw('hwc_' + key + '_int') for key in HWC_KEYS
                 if key not in HWC_RAW_ONLY_KEYS}
    if any(value in ('Non-Avail', 'NaN', None) for value in integrals.values()):
        return factors

    def ratio(numerator, denominator, scale=100.0):
        try:
            return scale * float(numerator) / float(denominator)
        except (TypeError, ValueError, ZeroDivisionError):
            return 'NaN'

    gr = integrals['gr_active']

    # The integrals cover the whole trace as loaded by Paraver, which can be
    # longer than the end declared in the header (see hwc_elapsed).
    elapsed = raw('hwc_elapsed')
    if elapsed in ('Non-Avail', 'NaN', None):
        elapsed = raw('runtime')
    try:
        elapsed_ns = float(elapsed) * NS_PER_US * float(raw('hwc_devices'))
    except (TypeError, ValueError):
        elapsed_ns = 0.0
    factors['dev_hwc_gpu_active'] = ratio(gr, elapsed_ns, scale=1.0)

    factors['dev_hwc_sm_utilization'] = ratio(integrals['sm_issue'], gr)
    factors['dev_hwc_sm_coverage'] = ratio(integrals['sms_active'], gr)
    factors['dev_hwc_sm_issue_eff'] = ratio(integrals['sm_issue'], integrals['sms_active'])
    factors['dev_hwc_achieved_occupancy'] = ratio(integrals['warps_in_flight'], integrals['sms_active'])
    factors['dev_hwc_tensor_activity'] = ratio(integrals['tensor_active'], gr)
    factors['dev_hwc_dram_read'] = ratio(integrals['dram_read'], gr, scale=1.0)
    factors['dev_hwc_dram_write'] = ratio(integrals['dram_write'], gr, scale=1.0)

    clock = ratio(integrals['gpc_clock'], gr, scale=1.0)
    if clock != 'NaN' and clock > HWC_CLOCK_HZ_THRESHOLD:
        clock /= 1.0e6
    factors['dev_hwc_gpc_clock'] = clock

    return factors


def create_device_hwc_factors(raw_data, trace_list):
    """Device hardware counter metrics: {metric key: {trace: value}}."""
    device_hwc_factors = OrderedDict(
        (key, {}) for key in mod_device_hwc_factors_doc
    )
    for trace in trace_list:
        for key, value in compute_device_hwc_factors(raw_data, trace).items():
            device_hwc_factors[key][trace] = value
    return device_hwc_factors


def aggregate_nsys2prv_device_metrics(kernel_rows, memcpy_rows, nccl_rows,
                                      stream_to_device,
                                      memory_values=MEMORY_OPERATION_VALUES):
    """Aggregate the Device activity per device.

    Each *_rows argument is a list of (thread_obj, start, end, value) in
    microseconds. Rows of threads that are not GPU streams are ignored.

    Per device:
      useful        = | union(kernels) |
      communication = | union(copies, memset, NCCL) minus useful |

    Per stream (for the Parallel Runtime Model, as the Running state of each
    stream in Extrae traces):
      useful        = | union(kernels of the stream) |

    memory_values: values of the memcpy event that are memory operations
    (found in the .pcf of the trace, nsys2prvevents.resolve_memory_values).
    """
    memory_values = {float(value) for value in memory_values}
    from rawdata import merge_intervals, subtract_intervals, sum_intervals

    useful_by_device = defaultdict(list)
    useful_by_stream = defaultdict(list)
    comm_by_device = defaultdict(list)

    for thread_obj, start, end, value in kernel_rows:
        device_key = stream_to_device.get(thread_obj)
        if device_key is not None and value > 0.0:
            useful_by_device[device_key].append((start, end))
            useful_by_stream[thread_obj].append((start, end))

    for thread_obj, start, end, value in memcpy_rows:
        device_key = stream_to_device.get(thread_obj)
        if device_key is not None and value in memory_values:
            comm_by_device[device_key].append((start, end))

    for thread_obj, start, end, value in nccl_rows:
        device_key = stream_to_device.get(thread_obj)
        if device_key is not None and value > 0.0:
            comm_by_device[device_key].append((start, end))

    result = {
        'useful_device_total': 0.0,
        'useful_device_max': 0.0,
        'useful_memtransf_device_total': 0.0,
        'useful_memtransf_device_max': 0.0,
        'per_device': {},
        'useful_by_stream': {
            thread_obj: sum_intervals(merge_intervals(useful_by_stream.get(thread_obj, [])))
            for thread_obj in stream_to_device
        },
    }

    for device_key in sorted(set(stream_to_device.values())):
        useful_flat = merge_intervals(useful_by_device.get(device_key, []))
        comm_flat = merge_intervals(comm_by_device.get(device_key, []))
        comm_only = subtract_intervals(comm_flat, useful_flat)

        useful_total = sum_intervals(useful_flat)
        comm_total = sum_intervals(comm_flat)
        comm_only_total = sum_intervals(comm_only)
        useful_comm_total = useful_total + comm_only_total

        result['per_device'][device_key] = {
            'useful_total': useful_total,
            'memtransfer_total': comm_total,
            'memtransfer_only_total': comm_only_total,
            'useful_memtransf_total': useful_comm_total,
        }

        result['useful_device_total'] += useful_total
        result['useful_memtransf_device_total'] += useful_comm_total
        result['useful_device_max'] = max(result['useful_device_max'], useful_total)
        result['useful_memtransf_device_max'] = max(
            result['useful_memtransf_device_max'], useful_comm_total)

    return result


def parse_nsys2prv_timeline(path, window=None):
    """Parse a paramedir timeline exported in nanoseconds.

    window: (begin, end) in microseconds; the bursts are clipped to it (the
    export of a window starts with the burst that contains its beginning).
    Returns a list of (thread_obj, start, end, value) in microseconds.
    A missing file (e.g. no NCCL events in the trace) returns [].
    """
    from rawdata import normalize_thread_object

    rows = []
    if not path or not os.path.exists(path):
        return rows

    with open(path) as stats_file:
        for raw_line in stats_file:
            if raw_line.startswith('#'):
                continue
            parts = raw_line.strip().split('\t')
            if len(parts) < 4:
                continue
            try:
                start = float(parts[1])
                duration = float(parts[2])
                value = float(parts[3])
            except ValueError:
                continue
            if duration <= 0.0 or value == 0.0:
                continue
            begin_us = start / NS_PER_US
            end_us = (start + duration) / NS_PER_US
            if window is not None:
                begin_us = max(begin_us, window[0])
                end_us = min(end_us, window[1])
                if end_us <= begin_us:
                    continue
            rows.append((
                normalize_thread_object(parts[0].strip()),
                begin_us,
                end_us,
                value,
            ))

    return rows


def resolve_nsys2prv_events(pcf_path, event_map=None):
    """Find the nsys2prv events in the .pcf of a trace and print them.

    Returns {'resolution': {name: Resolution}, 'codes': {reference code:
    code in the trace, or None}, 'memory_values': values of the memcpy
    event that are memory operations}.
    """
    from rawdata import parse_pcf_event_values

    resolution = nsys2prvevents.resolve_events(pcf_path, event_map)
    memcpy_code = resolution['memcpy'].code
    if memcpy_code is not None:
        memory, memory_how = nsys2prvevents.resolve_memory_values(
            parse_pcf_event_values(pcf_path, memcpy_code))
    else:
        memory, memory_how = (nsys2prvevents.DEFAULT_MEMORY_VALUES,
                              'reference values')

    print('==> nsys2prv events found in the .pcf:')
    for line in nsys2prvevents.format_resolution(resolution, memory, memory_how):
        print(line)
    missing = [name for name, found in resolution.items()
               if found.code is None and name in nsys2prvevents.FIXED_EVENTS]
    if missing:
        print('==WARNING== nsys2prv events not found in the .pcf: {}. Give '
              'their codes with --nsys2prv-events.'.format(', '.join(missing)))
    shared = nsys2prvevents.ambiguous_codes(pcf_path, resolution)
    if shared:
        print('==WARNING== The .pcf uses the event code(s) {} for more than one '
              'event: their values may be mixed.'.format(
                  ', '.join(str(code) for code in shared)))

    codes = {nsys2prvevents.ALL_EVENTS[name].code: found.code
             for name, found in resolution.items()}
    return {'resolution': resolution, 'codes': codes,
            'memory_values': tuple(memory.values())}


def write_trace_cfgs(cfgs, keys, codes, dest_dir, window=None):
    """Write the cfgs of one trace with the event codes of the trace.

    codes: {reference code: code in the trace, or None}. A cfg that needs an
    event that the trace does not have is not written. window: (begin, end)
    relative to the trace end, to restrict the cfgs to a region.

    Returns ({key: path of the written cfg}, [keys not written]).
    """
    written = {}
    missing = []
    os.makedirs(dest_dir, exist_ok=True)
    for key in keys:
        with open(cfgs[key]) as cfg_file:
            text = cfg_file.read()
        needed = nsys2prvevents.cfg_reference_codes(text)
        if any(codes.get(code, code) is None for code in needed):
            missing.append(key)
            continue
        path = os.path.join(dest_dir, os.path.basename(cfgs[key]))
        text = nsys2prvevents.rewrite_cfg(text, codes)
        if window is not None:
            text = apply_time_window(text, window[0], window[1])
        with open(path, 'w') as out:
            out.write(text)
        written[key] = path
    return written, missing


def process_one_nsys2prv_trace(trace, trace_process_count, trace_task_per_node_value,
                               trace_mode_value, trace_tasks_value, trace_threads_value,
                               cmdl_args, cfgs, path_dest):
    """Analyze one nsys2prv trace.

    Returns the same per-trace result structure as
    rawdata.process_one_trace().
    """
    from rawdata import (create_trace_raw_data, create_io_raw_data,
                         get_trace_names, parse_total_average_max,
                         human_readable)

    nsys_cfgs = init_nsys2prv_cfgs(cfgs['root_dir'])
    trace_raw_data = create_trace_raw_data()
    trace_io_data = create_io_raw_data()

    base_name = os.path.basename(trace)
    if base_name.endswith(".prv.gz"):
        base_name = base_name[:-7]
    elif base_name.endswith(".prv"):
        base_name = base_name[:-4]

    local_path_dest = os.path.join(path_dest, base_name)
    os.makedirs(local_path_dest, exist_ok=True)

    trace_name_control, trace_name = get_trace_names(trace, trace_process_count)
    row_path = trace_name_control + '.row'

    line = 'Analyzing ' + os.path.basename(trace)
    line += ' (' + str(trace_process_count) + ' processes'
    line += ', ' + str(trace_mode_value) + ' mode'
    line += ', ' + human_readable(os.path.getsize(trace)) + ')'
    print(line)

    time_tot = time.time()
    # MPI events (nsys2prv -t mpi_event_trace): MPI+CUDA model.
    has_mpi = trace_mode_value == NSYS2PRV_MPI_MODE

    # Metrics that need state records, hardware counters or MPI are not
    # available in nsys2prv traces (the outside-MPI times are replaced
    # below for traces with MPI events).
    for key in ('useful_tot', 'useful_avg', 'useful_max',
                'useful_not_0_tot', 'useful_not_0_avg', 'useful_not_0_max',
                'useful_cyc', 'useful_ins', 'frequency',
                'runtime_dim', 'hybrid_runtime_dim', 'useful_dim',
                'hybrid_useful_dim', 'outsidempi_dim', 'hybrid_outsidempi_dim',
                'useful_host', 'useful_host_max'):
        # useful_host is replaced below when the .row file is available.
        trace_raw_data[key] = 'Non-Avail'
    for key in ('outsidempi_avg', 'outsidempi_max', 'outsidempi_tot',
                'mpicomm_tot', 'outsidempi_tot_diff'):
        trace_raw_data[key] = 'NaN'

    # ------------------------------------------------------------
    # 1) Thread classification from the .row file
    # ------------------------------------------------------------
    if os.path.exists(row_path):
        threads = classify_nsys2prv_threads(trace, row_path)
    else:
        print('==WARNING== {} not found: the GPU streams cannot be '
              'identified.'.format(row_path))
        threads = {'streams': {}, 'metrics': [], 'host': [], 'gpu_tasks': set(),
                   'gpu_host': [], 'streams_per_task': {}, 'labels': []}

    stream_to_device = threads['streams']
    devices = sorted(set(stream_to_device.values()))

    host_threads = threads['gpu_host']
    streams_per_task = streams_per_task_value(threads)

    trace_raw_data['count_devices'] = len(devices)
    trace_raw_data['count_gpu_streams'] = len(stream_to_device)
    # One host unit per process with GPU streams (select_host_units).
    host_units_tasks = {_task_of(t) for t in host_threads}
    trace_raw_data['count_host_threads'] = len(host_units_tasks)
    trace_raw_data['gpu_streams_per_rank'] = streams_per_task

    other_tasks = sorted({_task_of(t) for t in threads['host']} - threads['gpu_tasks'])

    print("==> nsys2prv trace: Device metrics from kernel and memory operation events,")
    if has_mpi:
        print("    MPI metrics from the MPI events, Host metrics from the time outside")
        print("    CUDA and MPI calls.")
    else:
        print("    Host metrics from the time outside CUDA calls.")
    print("==> Count of devices: ", len(devices))
    if threads.get('gpu_identity') == 'process':
        print("==INFO== The trace has more GPU metrics threads ({}) than GPUs "
              "identified by node and device number ({}): the node of each "
              "process is missing. Each process is assumed to use its own "
              "GPUs.".format(len(threads['metrics']), threads['node_gpus']))
    elif threads.get('gpu_shared_unverified'):
        print("==WARNING== Several processes use GPUs with the same node and "
              "device number, and the trace has no GPU metrics to check "
              "whether they are the same GPU: they are analyzed as shared "
              "GPUs. If the processes ran on different nodes, the Device "
              "metrics are not valid.")
    print("==> Count of GPU streams: ", len(stream_to_device))
    if streams_per_task == -1:
        print("==> GPU streams per process: non-uniform")
    else:
        print("==> GPU streams per process: ", streams_per_task)
    print("==> Count of host threads: ", len(host_threads))
    if len(host_threads) > len(host_units_tasks):
        print("==> Host units: one per process with GPU streams, the thread "
              "with the most time in CUDA calls")
    if other_tasks:
        print("==> Processes without GPU streams (not analyzed): " +
              ', '.join(str(t) for t in other_tasks))

    # ------------------------------------------------------------
    # 2) Run paramedir
    # ------------------------------------------------------------
    stats = {
        'runtime': trace_name + '.runtime.stats.csv',
        'kernels_streams': trace_name + '.kernels_streams.stats.csv',
        'memcpy_streams': trace_name + '.memcpy_streams.stats.csv',
        'nccl_streams': trace_name + '.nccl_streams.stats.csv',
        'cuda_calls_host': trace_name + '.cuda_calls_host.stats.csv',
    }
    mpi_keys = ()
    if has_mpi:
        mpi_keys = ('mpi_outside_host', 'cuda_calls_in_mpi')
        stats['mpi_outside_host'] = trace_name + '.mpi_outside_host.stats.csv'
        stats['cuda_calls_in_mpi'] = trace_name + '.cuda_calls_in_mpi.stats.csv'

    # GPU hardware counters, only when the trace has Metrics GPU<n> threads.
    hwc_stats = {}
    if threads['metrics']:
        for key in HWC_KEYS:
            hwc_stats['hwc_' + key] = trace_name + '.hwc_' + key + '.stats.csv'
    stats.update(hwc_stats)

    # Region analyzed of traces with MPI events: from the end of MPI_Init to
    # the start of MPI_Finalize, as Extrae records it (nsys2prv_mpi_region).
    region = None          # (begin, end) in microseconds
    window = None          # (begin, end) relative to the trace end
    header_end = trace_header_end_us(trace)
    if has_mpi and header_end and not getattr(cmdl_args, 'nsys2prv_whole_trace', False):
        mpi_region = nsys2prv_mpi_region(trace)
        if mpi_region is not None:
            begin_us = mpi_region[0] / NS_PER_US
            end_us = (mpi_region[1] / NS_PER_US if mpi_region[1] is not None
                      else header_end)
            region = (begin_us, min(end_us, header_end))
            window = (region[0] / header_end, region[1] / header_end)
            print('==> Region analyzed: from the end of MPI_Init ({:.3f} s) to the '
                  'start of MPI_Finalize ({:.3f} s), {:.3f} s of {:.3f} s ({:.1f} %), '
                  'as Extrae records it. Use --nsys2prv-whole-trace to analyze the '
                  'whole trace.'.format(
                      region[0] / 1e6, region[1] / 1e6,
                      (region[1] - region[0]) / 1e6, header_end / 1e6,
                      100.0 * (region[1] - region[0]) / header_end))

    # The codes of the events change between nsys2prv versions: find them
    # in the .pcf of the trace and rewrite the cfgs with them.
    events = resolve_nsys2prv_events(
        trace_name_control + '.pcf',
        getattr(cmdl_args, 'nsys2prv_events', None))
    trace_cfgs, missing_cfgs = write_trace_cfgs(
        nsys_cfgs, ('kernels_streams', 'memcpy_streams', 'nccl_streams',
                    'cuda_calls_host') + mpi_keys + tuple(hwc_stats),
        events['codes'], os.path.join(local_path_dest, 'cfgs-nsys2prv'),
        window=window)
    trace_cfgs['runtime'] = nsys_cfgs['runtime']

    cmd = ['paramedir', trace]
    for key in ('runtime', 'kernels_streams', 'memcpy_streams', 'nccl_streams',
                'cuda_calls_host') + mpi_keys + tuple(hwc_stats):
        if key in trace_cfgs:
            cmd.extend([trace_cfgs[key], stats[key]])

    time_pmd = time.time()
    run_command(cmd, cmdl_args)
    time_pmd = time.time() - time_pmd

    if not os.path.exists(stats['runtime']):
        print('==ERROR== Failed to compute timing information with paramedir.')
        print('Failed to analyze trace with paramedir')
    else:
        print('Successfully analyzed trace with paramedir in {0:.1f} seconds.'.format(time_pmd))

    # ------------------------------------------------------------
    # 3) Parse
    # ------------------------------------------------------------
    paraver_runtime = 'NaN'
    if os.path.exists(stats['runtime']):
        _, paraver_runtime, _ = parse_total_average_max(stats['runtime'])

    # nsys2prv can write events (GPU metric samples) after the end declared
    # in the header; Paraver then extends the trace to the last event. The
    # metrics use the declared end, which covers the application activity.
    trace_raw_data['runtime'] = (
        header_end if header_end is not None else paraver_runtime)
    if region is not None:
        trace_raw_data['runtime'] = region[1] - region[0]
    elif (header_end is not None and paraver_runtime != 'NaN'
            and paraver_runtime > header_end * 1.001):
        print('==INFO== The trace has events after the end declared in its '
              'header ({0:.3f} s); Paraver extends it to {1:.3f} s. The '
              'metrics use the declared end; the GPU hardware counters '
              'include the samples after it.'.format(
                  header_end / 1e6, paraver_runtime / 1e6))

    # Host useful time: elapsed time minus time inside CUDA calls.
    # One host unit per process: the thread that drives its GPUs.
    host_calls = parse_nsys2prv_host_calls(stats['cuda_calls_host'], threads)
    if len(host_threads) > len(host_units_tasks):
        host_threads = select_host_units(threads, host_calls)
        print("==> Host unit of each process: " + ', '.join(host_threads))
    trace_raw_data['host_threads_not_analyzed'] = host_threads_not_analyzed(
        threads, host_threads, host_calls,
        runtime=(float(trace_raw_data['runtime'])
                 if trace_raw_data['runtime'] != 'NaN' else None))
    listed, minor_count, minor_s = not_analyzed_summary(
        trace_raw_data['host_threads_not_analyzed'])
    for entry in listed:
        print("==> Not analyzed: {} ({:.3f} s in CUDA calls): {}".format(
            entry['thread'], entry['cuda_calls_s'],
            NOT_ANALYZED_REASONS[entry['reason']]))
    if minor_count:
        print("==> Not analyzed: " + not_analyzed_minor_text(minor_count, minor_s))
    mpi_proc_count = None
    if host_threads and trace_raw_data['runtime'] != 'NaN' and host_calls:
        runtime = float(trace_raw_data['runtime'])
        useful_host = [
            max(runtime - host_calls.get(thread_obj, 0.0), 0.0)
            for thread_obj in host_threads
        ]
        outside_mpi = (parse_nsys2prv_host_calls(stats['mpi_outside_host'], threads)
                       if has_mpi else {})
        if has_mpi and not outside_mpi:
            print('==WARNING== The time outside MPI calls could not be computed: '
                  'the MPI metrics are not available, and the Host useful time '
                  'includes the time in MPI calls.')
        if outside_mpi:
            mpi = nsys2prv_mpi_times(
                threads, host_threads, runtime, outside_mpi, host_calls,
                parse_nsys2prv_host_calls(stats['cuda_calls_in_mpi'], threads))
            useful_host = [mpi['useful_host'][unit] for unit in host_threads]
            outside = [mpi['outside_by_task'][task]
                       for task in sorted(mpi['outside_by_task'])]
            if outside:
                mpi_proc_count = len(outside)
                trace_raw_data['outsidempi_tot'] = sum(outside)
                trace_raw_data['outsidempi_tot_diff'] = sum(outside)
                trace_raw_data['outsidempi_avg'] = sum(outside) / len(outside)
                trace_raw_data['outsidempi_max'] = max(outside)
                trace_raw_data['mpicomm_tot'] = sum(runtime - value for value in outside)
            for unit in host_threads:
                task = _task_of(unit)
                note = ''
                if mpi['mpi_thread'].get(task, unit) != unit:
                    note = ' (MPI called from {})'.format(mpi['mpi_thread'][task])
                print('==> MPI: {} {:.3f} s in MPI calls, {:.3f} s of CUDA calls '
                      'inside MPI calls{}'.format(
                          unit, mpi['mpi_host'][unit] / 1e6,
                          mpi['overlap_host'][unit] / 1e6, note))
        trace_raw_data['useful_host'] = sum(useful_host)
        trace_raw_data['useful_host_max'] = max(useful_host)

        if cmdl_args.debug:
            for thread_obj in host_threads:
                print('==DEBUG== {}: CUDA calls={:.2f}, useful={:.2f}'.format(
                    thread_obj, host_calls.get(thread_obj, 0.0),
                    runtime - host_calls.get(thread_obj, 0.0)))

    # paramedir writes no file when none of the events of a filter is in the
    # trace. Without the kernel timeline the Device useful time is 0, and the
    # Device metrics are 0 or NaN: say why.
    if 'kernels_streams' in missing_cfgs:
        print('==WARNING== The GPU kernel event was not found in the .pcf: '
              'the Device useful time is 0 and the Device metrics are not '
              'meaningful. Give its code with --nsys2prv-events.')
    elif os.path.exists(stats['runtime']) and not os.path.exists(
            stats['kernels_streams']):
        print('==WARNING== paramedir found no GPU kernel events ({}) '
              'on the GPU streams: the Device useful time is 0 and the '
              'Device metrics are not meaningful.'.format(
                  events['resolution']['kernel'].code))

    time_agg = time.time()
    gpu_agg = aggregate_nsys2prv_device_metrics(
        parse_nsys2prv_timeline(stats['kernels_streams'], region),
        parse_nsys2prv_timeline(stats['memcpy_streams'], region),
        parse_nsys2prv_timeline(stats['nccl_streams'], region),
        stream_to_device,
        memory_values=events['memory_values'],
    )
    time_agg = time.time() - time_agg
    print('Successfully aggregated GPU time in {0:.1f} seconds.'.format(time_agg))

    if cmdl_args.debug:
        for dev, vals in gpu_agg['per_device'].items():
            print(
                f'==DEBUG== {dev}: '
                f'useful={vals["useful_total"]:.2f}, '
                f'communication={vals["memtransfer_total"]:.2f}, '
                f'communication_only={vals["memtransfer_only_total"]:.2f}, '
                f'useful_plus_communication={vals["useful_memtransf_total"]:.2f}')

    # Parallel Runtime Model (flattened host threads + GPU streams, as for
    # GPU applications without MPI in Extrae traces): useful time of each
    # execution unit.
    if trace_raw_data['useful_host'] != 'Non-Avail':
        unit_useful = list(useful_host) + list(gpu_agg['useful_by_stream'].values())
        trace_raw_data['useful_tot'] = sum(unit_useful)
        trace_raw_data['useful_avg'] = sum(unit_useful) / len(unit_useful)
        trace_raw_data['useful_max'] = max(unit_useful)

    # GPU hardware counters: integrals added over the Metrics GPU<n> threads.
    # The devices of all counters must match; otherwise they are not used.
    hwc_values = {
        key: parse_nsys2prv_hwc_integral(hwc_stats.get('hwc_' + key))
        for key in HWC_KEYS
    }
    hwc_devices = {value[1] for value in hwc_values.values() if value}
    if all(hwc_values.values()) and len(hwc_devices) == 1:
        trace_raw_data['hwc_devices'] = hwc_devices.pop()
        trace_raw_data['hwc_elapsed'] = (
            region[1] - region[0] if region is not None else paraver_runtime)
        for key, (integral, _devices) in hwc_values.items():
            trace_raw_data['hwc_' + key + '_int'] = integral
        print("==> GPU hardware counters: {} device(s) with sampled metrics".format(
            trace_raw_data['hwc_devices']))
    elif threads['metrics']:
        missing_hwc = sorted(name for name in nsys2prvevents.HWC_EVENTS
                             if events['resolution'][name].code is None)
        print('==WARNING== The GPU hardware counters of the Metrics GPU threads '
              'could not be computed{}.'.format(
                  ': counters not found in the .pcf: ' + ', '.join(missing_hwc)
                  + ' (give their codes with --nsys2prv-events)'
                  if missing_hwc else ''))

    trace_raw_data['useful_device'] = gpu_agg['useful_device_total']
    trace_raw_data['useful_device_max'] = gpu_agg['useful_device_max']
    trace_raw_data['useful_memtransf_device'] = gpu_agg['useful_memtransf_device_total']
    trace_raw_data['useful_memtransf_device_max'] = gpu_agg['useful_memtransf_device_max']

    for path in stats.values():
        move_files(path, local_path_dest, cmdl_args)
        move_files(path[:-4] + '.legend.csv', local_path_dest, cmdl_args)

    execution_mapping = _execution_mapping_from_streams(stream_to_device)

    time_tot = time.time() - time_tot
    print('Finished successfully in {0:.1f} seconds.'.format(time_tot))
    print('')

    return {
        "trace": trace,
        "trace_mode": trace_mode_value,
        "trace_process_count": trace_process_count,
        "trace_task_per_node": trace_task_per_node_value,
        "trace_tasks": trace_tasks_value,
        "trace_threads": trace_threads_value,
        "execution_mapping": execution_mapping,
        "raw_data": trace_raw_data,
        "io_data": trace_io_data,
        "mpi_proc_count": mpi_proc_count,
    }
