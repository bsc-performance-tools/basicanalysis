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

Host metrics are not available: without state records the useful host time
cannot be measured.
"""

from __future__ import print_function, division

import os
import re
import time
from collections import defaultdict

from tracemetadata import parse_trace_header, NSYS2PRV_METRICS_LABEL_RE
from utils import run_command, move_files


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



def init_nsys2prv_cfgs(root_dir):
    """Return the paths of the configurations used for nsys2prv traces."""
    nsys_dir = os.path.join(root_dir, 'nsys2prv')
    return {
        'runtime': os.path.join(root_dir, 'runtime_app.cfg'),
        'kernels_streams': os.path.join(nsys_dir, 'kernels_streams.cfg'),
        'memcpy_streams': os.path.join(nsys_dir, 'memcpy_streams.cfg'),
        'nccl_streams': os.path.join(nsys_dir, 'nccl_streams.cfg'),
    }


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
    }

    for thread_obj, node, label in zip(thread_objects, thread_nodes, thread_labels):
        match = NSYS2PRV_STREAM_LABEL_RE.match(label)
        if match:
            device = match.group(1)
            stream_node = match.group(3) or node
            result['streams'][thread_obj] = '{}:{}'.format(stream_node, device)
            result['gpu_tasks'].add(int(thread_obj.split()[1].split('.')[1]))
        elif NSYS2PRV_METRICS_LABEL_RE.match(label):
            result['metrics'].append(thread_obj)
        else:
            result['host'].append(thread_obj)

    return result


def aggregate_nsys2prv_device_metrics(kernel_rows, memcpy_rows, nccl_rows,
                                      stream_to_device):
    """Aggregate the Device activity per device.

    Each *_rows argument is a list of (thread_obj, start, end, value) in
    microseconds. Rows of threads that are not GPU streams are ignored.

    Per device:
      useful        = | union(kernels) |
      communication = | union(copies, memset, NCCL) minus useful |
    """
    from rawdata import merge_intervals, subtract_intervals, sum_intervals

    useful_by_device = defaultdict(list)
    comm_by_device = defaultdict(list)

    for thread_obj, start, end, value in kernel_rows:
        device_key = stream_to_device.get(thread_obj)
        if device_key is not None and value > 0.0:
            useful_by_device[device_key].append((start, end))

    for thread_obj, start, end, value in memcpy_rows:
        device_key = stream_to_device.get(thread_obj)
        if device_key is not None and value in MEMORY_OPERATION_VALUES:
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


def parse_nsys2prv_timeline(path):
    """Parse a paramedir timeline exported in nanoseconds.

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
            rows.append((
                normalize_thread_object(parts[0].strip()),
                start / NS_PER_US,
                (start + duration) / NS_PER_US,
                value,
            ))

    return rows


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

    # Metrics that need state records, hardware counters or MPI are not
    # available in nsys2prv traces.
    for key in ('useful_tot', 'useful_avg', 'useful_max',
                'useful_not_0_tot', 'useful_not_0_avg', 'useful_not_0_max',
                'useful_cyc', 'useful_ins', 'frequency',
                'runtime_dim', 'hybrid_runtime_dim', 'useful_dim',
                'hybrid_useful_dim', 'outsidempi_dim', 'hybrid_outsidempi_dim',
                'useful_host', 'useful_host_max'):
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
        threads = {'streams': {}, 'metrics': [], 'host': [], 'gpu_tasks': set()}

    stream_to_device = threads['streams']
    devices = sorted(set(stream_to_device.values()))

    trace_raw_data['count_devices'] = len(devices)
    trace_raw_data['count_gpu_streams'] = len(stream_to_device)
    trace_raw_data['count_host_threads'] = len(threads['host'])
    trace_raw_data['gpu_streams_per_rank'] = 0

    print("==> nsys2prv trace: Device metrics from kernel and memory copy events.")
    print("==> Count of devices: ", len(devices))
    print("==> Count of GPU streams: ", len(stream_to_device))
    print("==> Host threads: ", len(threads['host']),
          "(processes with GPU streams: {})".format(
              ', '.join(str(t) for t in sorted(threads['gpu_tasks'])) or 'none'))

    # ------------------------------------------------------------
    # 2) Run paramedir
    # ------------------------------------------------------------
    stats = {
        'runtime': trace_name + '.runtime.stats.csv',
        'kernels_streams': trace_name + '.kernels_streams.stats.csv',
        'memcpy_streams': trace_name + '.memcpy_streams.stats.csv',
        'nccl_streams': trace_name + '.nccl_streams.stats.csv',
    }

    cmd = ['paramedir', trace]
    for key in ('runtime', 'kernels_streams', 'memcpy_streams', 'nccl_streams'):
        cmd.extend([nsys_cfgs[key], stats[key]])

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
    if os.path.exists(stats['runtime']):
        _, runtime_avg, _ = parse_total_average_max(stats['runtime'])
        trace_raw_data['runtime'] = runtime_avg
    else:
        trace_raw_data['runtime'] = 'NaN'

    time_agg = time.time()
    gpu_agg = aggregate_nsys2prv_device_metrics(
        parse_nsys2prv_timeline(stats['kernels_streams']),
        parse_nsys2prv_timeline(stats['memcpy_streams']),
        parse_nsys2prv_timeline(stats['nccl_streams']),
        stream_to_device,
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

    trace_raw_data['useful_device'] = gpu_agg['useful_device_total']
    trace_raw_data['useful_device_max'] = gpu_agg['useful_device_max']
    trace_raw_data['useful_memtransf_device'] = gpu_agg['useful_memtransf_device_total']
    trace_raw_data['useful_memtransf_device_max'] = gpu_agg['useful_memtransf_device_max']

    for path in stats.values():
        move_files(path, local_path_dest, cmdl_args)
        move_files(path[:-4] + '.legend.csv', local_path_dest, cmdl_args)

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

    execution_mapping = {
        "nodes": len(devices_by_node) or None,
        "mpi_ranks_per_node": None,
        "threads_per_rank": None,
        "threads_per_node": None,
        "gpus_per_node": uniform(devices_by_node.values()),
        "gpu_streams_per_node": uniform(streams_by_node.values()),
        "streams_per_gpu": uniform(streams_by_device.values()),
    }

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
        "mpi_proc_count": None,
    }
