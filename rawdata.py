#!/usr/bin/env python3

"""Functions to extract rawdata from each trace."""

from __future__ import print_function, division
import os
import time
import math
import gzip
import shutil
import json
from utils import which
from collections import OrderedDict, defaultdict
from tracemetadata import human_readable, get_tasks_threads, get_device_stream_id_mapping
from utils import run_command, move_files,remove_files, create_temp_folder


# Contains all raw data entries with a printable name.
# This is used to generate and print all raw data, so, if an entry is added, it
# should be added here, too.
raw_data_doc = OrderedDict([('runtime', 'Runtime (us)'),
                            ('runtime_dim', 'Runtime (ideal)'),
                            ('hybrid_runtime_dim', 'Hybrid Runtime (ideal)'),
                            ('useful_avg', 'Useful duration (average)'),
                            ('useful_max', 'Useful duration (maximum)'),
                            ('useful_tot', 'Useful duration (total)'),
                            ('useful_dim', 'Useful duration (ideal, max)'),
                            ('hybrid_useful_dim', 'Hybrid Useful duration (ideal, max)'),
                            ('useful_ins', 'Useful instructions (total)'),
                            ('useful_cyc', 'Useful cycles (total)'),
                            ('frequency', 'Frequency in Useful (avg)'),
                            ('outsidempi_avg', 'Outside MPI duration (average)'),
                            ('outsidempi_max', 'Outside MPI duration (maximum)'),
                            ('outsidempi_dim', 'Outside MPI duration (ideal,maximum)'),
                            ('hybrid_outsidempi_dim', 'Hybrid Outside MPI duration (ideal,maximum)'),
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
                            ('mpiio_ins', 'MPI I/O instructions (total)'),
                            ('burst_useful_tot', 'Burst Useful (total)'),
                            ('burst_useful_max', 'Burst Useful (max)'),
                            ('burst_useful_avg', 'Burst Useful (avg)'),
                            ('useful_not_0_avg', 'Useful duration not 0 inst (average)'),
                            ('useful_not_0_max', 'Useful duration not 0 inst (maximum)'),
                            ('useful_not_0_tot', 'Useful duration not 0 inst (total)'),
                            ('procs_ins', 'Procs with instructions (total)'),
                            ('useful_host', 'Useful Total duration on the Host'),
                            ('useful_host_max', 'Useful duration on the Host (maximum)'),
                            ('useful_hybrid_gpu_tot', 'Hybrid MPI+GPU useful duration (total)'),
                            ('useful_hybrid_gpu_avg', 'Hybrid MPI+GPU useful duration (average)'),
                            ('useful_hybrid_gpu_max', 'Hybrid MPI+GPU useful duration (maximum)'),
                            ('useful_device', 'Useful duration on the device'),
                            ('useful_device_max', 'Useful duration on the device (maximum)'),
                            ('useful_memtransf_device', 'Useful+MemoryTransfer on the device'),
                            ('useful_memtransf_device_max', 'Useful+MemoryTransfer on the device (maximum)'),
                            ('count_devices', 'Count of Devices'),
                            ('count_gpu_streams', 'Count of GPU streams'),
                            ('gpu_streams_per_rank', 'GPU streams per MPI rank'),
                            ('time_no_omp', 'Useful + MPI time.'),
                            ('time_omp_imbalance', 'Time lost due to load imbalance among OpenMP threads.'),
                            ('time_omp_schedule', 'Time spent in OpenMP scheduling and fork/join.'),
                            ('time_omp_serial', 'Serial OpenMP loss from inactive threads outside parallel regions.')
                            ])


SUMMARY_KEYS = {"Total", "Average", "Maximum", "Minimum", "StDev", "Num.", "Avg/Max", "Num. Cells"}

# ----------------------------------------------------------------------
# Helper functions to adding serialization for distributed analysis.
# ----------------------------------------------------------------------

def get_trace_output_dir(path_dest, trace):
    """Return a stable per-trace output directory."""
    base = os.path.basename(trace)
    if base.endswith(".prv.gz"):
        base = base[:-7]
    elif base.endswith(".prv"):
        base = base[:-4]
    return os.path.join(path_dest, base)

def save_trace_result(result, output_path):
    with open(output_path, 'w') as f:
        json.dump(result, f, indent=2, sort_keys=True)


def load_trace_result(input_path):
    with open(input_path) as f:
        return json.load(f)


def get_trace_result_path(output_dir, trace):
    base = os.path.basename(trace)
    if base.endswith('.prv.gz'):
        base = base[:-7]
    elif base.endswith('.prv'):
        base = base[:-4]
    return os.path.join(output_dir, base + '.rawdata.json')

# ----------------------------------------------------------------------
# Helper functions to parser data from paramedir outputs.
# ----------------------------------------------------------------------

def iter_stats_lines(path, skip_header=False):
    with open(path) as f:
        if skip_header:
            next(f, None)
        for line in f:
            yield line.rstrip('\n')


def get_parts(line, sep=None):
    parts = line.split(sep)
    return parts


def parse_total_average_max(path):
    total = None
    avg = None
    maximum = None

    for line in iter_stats_lines(path):
        parts = line.split()
        if not parts:
            continue
        key = parts[0]
        if key == 'Total':
            total = float(parts[1])
        elif key == 'Average':
            avg = float(parts[1])
        elif key == 'Maximum':
            maximum = float(parts[1])

    return total, avg, maximum


def parse_total_as_int(path):
    total = 0.0
    for line in iter_stats_lines(path):
        parts = line.split()
        if not parts:
            continue
        if parts[0] == 'Total':
            total = int(float(parts[1]))
            break
    return total


def parse_positive_value_sum(path, skip_header=True):
    total = 0.0
    for line in iter_stats_lines(path, skip_header=skip_header):
        parts = line.split()
        if not parts:
            continue
        if parts[0] in SUMMARY_KEYS:
            continue
        value = float(parts[-1])
        if value > 0.0:
            total += value
    return total


def parse_positive_value_sum_and_mask(path, skip_header=True):
    total = 0.0
    mask = []
    count_positive = 0

    for line in iter_stats_lines(path, skip_header=skip_header):
        parts = line.split()
        if not parts:
            continue
        if parts[0] in SUMMARY_KEYS:
            continue

        value = float(parts[-1])
        if value > 0.0:
            total += value
            count_positive += 1
            mask.append(1)
        else:
            mask.append(0)

    return total, count_positive, mask


def parse_tab_totals_row(path):
    """
    Reads files where 'Total' row contains one value per rank/process.
    Returns list of totals from the Total row.
    """
    with open(path) as f:
        for raw_line in f:
            line = raw_line.rstrip('\n')
            parts = line.split('\t')
            if not parts:
                continue
            if parts[0] == 'Total':
                values = [float(x) for x in parts[1:] if x != '']
                return values
    return []

def parse_tab_total_row_values(path):
    """
    Extract numeric values from the 'Total' row of a tab-separated stats file.
    """
    with open(path) as f:
        for raw_line in f:
            line = raw_line.rstrip('\n')
            parts = line.split('\t')
            if not parts:
                continue
            if parts[0] == 'Total':
                return [float(x) for x in parts[1:] if x != '']
    return []

def parse_timings_stats(path, instructions_mask=None, posixio_totals=None, has_pcf=False):
    """
    Parse timings.stats in one pass.

    Returns a dict with:
      useful_tot, useful_avg, useful_max,
      useful_not_0_tot, useful_not_0_avg, useful_not_0_max,
      io_state_tot, io_state_avg, io_state_max,
      useful_plus_io_avg, useful_plus_io_max
    """

    result = {
        'useful_tot': 'NaN',
        'useful_avg': 'NaN',
        'useful_max': 'NaN',
        'useful_not_0_tot': 'NaN',
        'useful_not_0_avg': 'NaN',
        'useful_not_0_max': 'NaN',
        'io_state_tot': 0.0,
        'io_state_avg': 0.0,
        'io_state_max': 0.0,
        'useful_plus_io_avg': 0.0,
        'useful_plus_io_max': 0.0,
    }

    useful_not_0_values = []
    useful_plus_io = []

    io_index = None
    data_row_index = 0

    with open(path) as f:
        for line_num, raw_line in enumerate(f):
            line = raw_line.rstrip('\n')
            line_list = line.split('\t')

            if not line_list or all(x == '' for x in line_list):
                continue

            # Header row: locate IO column once
            if line_num == 0:
                if has_pcf:
                    try:
                        io_index = line_list.index("I/O")
                    except ValueError:
                        io_index = None
                else:
                    try:
                        io_index = line_list.index("Unknown state 12")
                    except ValueError:
                        io_index = None
                continue

            key = line_list[0].strip()

            if key == 'Total':
                if len(line_list) > 1:
                    result['useful_tot'] = float(line_list[1])
                if io_index is not None and io_index < len(line_list) and line_list[io_index] != '':
                    result['io_state_tot'] = float(line_list[io_index])

            elif key == 'Average':
                if len(line_list) > 1:
                    result['useful_avg'] = float(line_list[1])
                if io_index is not None and io_index < len(line_list) and line_list[io_index] != '':
                    result['io_state_avg'] = float(line_list[io_index])

            elif key == 'Maximum':
                if len(line_list) > 1:
                    result['useful_max'] = float(line_list[1])
                if io_index is not None and io_index < len(line_list) and line_list[io_index] != '':
                    result['io_state_max'] = float(line_list[io_index])

            elif key in ('Minimum', 'StDev', 'Avg/Max', 'Num. Cells') or key.startswith('Num.'):
                continue

            else:
                # Per-rank / per-thread data row
                if len(line_list) <= 1 or line_list[1] == '':
                    continue

                useful_value = float(line_list[1])

                # useful_not_0_* based on instructions mask
                if instructions_mask is not None and data_row_index < len(instructions_mask):
                    if instructions_mask[data_row_index] == 1:
                        useful_not_0_values.append(useful_value)

                # useful_plus_io_* based on POSIX-IO totals
                if io_index is not None:
                    posixio_value = 0.0
                    if posixio_totals is not None and data_row_index < len(posixio_totals):
                        posixio_value = float(posixio_totals[data_row_index])
                    useful_plus_io.append(useful_value + posixio_value)

                data_row_index += 1

    # Final reductions
    if useful_not_0_values:
        result['useful_not_0_tot'] = float(sum(useful_not_0_values))
        result['useful_not_0_avg'] = float(sum(useful_not_0_values) / len(useful_not_0_values))
        result['useful_not_0_max'] = float(max(useful_not_0_values))

    if useful_plus_io:
        result['useful_plus_io_avg'] = float(sum(useful_plus_io) / len(useful_plus_io))
        result['useful_plus_io_max'] = float(max(useful_plus_io))

    return result


def parse_outside_mpi_stats(path, runtime_value):
    """
    Parse outside_mpi.stats for a real trace.

    Returns:
      {
        'outsidempi_tot_diff': ...,
        'outsidempi_tot': ...,
        'outsidempi_avg': ...,
        'outsidempi_max': ...,
        'mpicomm_tot': ...,
        'mpi_proc_count': ...,
      }
    """
    result = {
        'outsidempi_tot_diff': 'NaN',
        'outsidempi_tot': 'NaN',
        'outsidempi_avg': 'NaN',
        'outsidempi_max': 'NaN',
        'mpicomm_tot': 'NaN',
        'mpi_proc_count': 0,
    }
    
    # a list of outsidempi of MPI processes
    list_outside_mpi = []
    # a list of number of threads per MPI process
    list_thread_outside_mpi = []

    init_count_thread = False
    count_threads = 1

    total_row = None

    with open(path) as f:
        next(f, None)  # skip header

        for raw_line in f:
            line = raw_line.rstrip('\n')
            parts = line.split('\t')

            if not parts or parts[0] == '':
                continue

            key = parts[0]

            # Capture summary Total row for MPI communication totals
            if key == 'Total':
                total_row = parts
                continue

            # Skip summary/stat rows
            if key in SUMMARY_KEYS:
                continue

            if len(parts) < 2 or parts[1] == '':
                continue

            value = float(parts[1])

            # Original logic:
            # - values different from runtime_value are "outside MPI" representative rows
            # - values equal to runtime_value count extra threads of the current MPI task, because this means it is a thread.
            if value != runtime_value:
                list_outside_mpi.append(value)

                if len(list_outside_mpi) > 1:
                    list_thread_outside_mpi.append(count_threads)

                count_threads = 1
            else:
                if len(list_outside_mpi) == 1 and not init_count_thread:
                    count_threads = 2
                    init_count_thread = True
                else:
                    count_threads += 1

    if list_outside_mpi:
        list_thread_outside_mpi.append(count_threads)

        equal_threads = all(
            list_thread_outside_mpi[i] == list_thread_outside_mpi[i + 1]
            for i in range(len(list_thread_outside_mpi) - 1)
        )

        if not equal_threads:
            rescaled_outside_mpi = [
                list_outside_mpi[i] * list_thread_outside_mpi[i]
                for i in range(len(list_outside_mpi))
            ]

            result['outsidempi_tot_diff'] = sum(rescaled_outside_mpi)
            result['outsidempi_tot'] = sum(list_outside_mpi)

            total_threads = sum(list_thread_outside_mpi)
            
            if total_threads != 0:
                result['outsidempi_avg'] = sum(rescaled_outside_mpi) / total_threads
            else:
                result['outsidempi_avg'] = 'NaN'

            result['outsidempi_max'] = max(list_outside_mpi)
        else:
            result['outsidempi_tot_diff'] = sum(list_outside_mpi)
            result['outsidempi_tot'] = sum(list_outside_mpi)

            if len(list_outside_mpi) != 0:
                result['outsidempi_avg'] = sum(list_outside_mpi) / len(list_outside_mpi)
            else:
                result['outsidempi_avg'] = 'NaN'

            result['outsidempi_max'] = max(list_outside_mpi)
            result['mpi_proc_count'] = len(list_outside_mpi)
        
        
    # MPI communication total from Total row
    if total_row is not None and len(total_row) > 2:
        list_mpi_tot = [float(x) for x in total_row[2:] if x != '']
        result['mpicomm_tot'] = sum(list_mpi_tot)

    return result


def parse_tab_stats(path):
    """
    Parse stats files where rows are:
    Total / Average / Maximum and values are tab-separated per rank.
    """
    values = []

    result = {
        'tot': 0.0,
        'avg': 0.0,
        'max': 0.0,
        'std': 0.0
    }

    with open(path) as f:
        for raw_line in f:
            line = raw_line.rstrip('\n')
            parts = line.split('\t')

            if not parts:
                continue

            key = parts[0]

            if key == 'Total':
                values = [float(x) for x in parts[1:] if x != '']
                result['tot'] = sum(values)

            elif key == 'Average':
                if values:
                    result['avg'] = result['tot'] / len(values)

                    if len(values) > 1:
                        mean = result['avg']
                        variance = sum((x - mean) ** 2 for x in values) / len(values)
                        result['std'] = math.sqrt(variance)
                    else:
                        result['std'] = 0.0
                else:
                    result['avg'] = 0.0
                    result['std'] = 0.0

            elif key == 'Maximum':
                if values:
                    result['max'] = max(values)

    return result


def parse_outside_mpi_sim_stats(path):
    """
    Parse outside_mpi.stats for a simulated trace.

    Returns:
      {
        'outsidempi_dim': float
      }
    """
    result = {
        'outsidempi_dim': 0.0
    }

    list_outside_mpi = []
    max_time_outside_mpi = 0.0

    with open(path) as f:
        next(f, None)  # skip header

        for raw_line in f:
            line = raw_line.rstrip('\n')
            parts = line.split('\t')

            if not parts or parts[0] == '':
                continue

            key = parts[0]

            if key in SUMMARY_KEYS:
                continue

            if len(parts) < 2 or parts[1] == '':
                continue

            try:
                value = float(parts[1])
            except ValueError:
                continue

            # Keep original behavior:
            # representative MPI-task rows are THREAD x.y.1
            if key.startswith("THREAD "):
                thread_id = key.split()[1]
                thread_fields = thread_id.split(".")
                if len(thread_fields) >= 3 and thread_fields[2] == '1':
                    list_outside_mpi.append(value)

                if key == "THREAD 1.1.1":
                    max_time_outside_mpi = value

    if list_outside_mpi:
        result['outsidempi_dim'] = max(list_outside_mpi)
    else:
        result['outsidempi_dim'] = max_time_outside_mpi

    return result

def parse_burst_useful_stats(path):
    """
    Parse burst_useful.stats from the Total row.
    """
    result = {
        'tot': 'NaN',
        'avg': 'NaN',
        'max': 'NaN',
    }

    totals = parse_tab_total_row_values(path)

    if totals:
        result['tot'] = sum(totals)
        result['avg'] = sum(totals) / len(totals)
        result['max'] = max(totals)

    return result

def parse_tab_total_row_values_or_empty(path):
    if os.path.exists(path):
        return parse_tab_total_row_values(path)
    return []


def flushing_stats_has_data(path):
    with open(path) as f:
        for line in f:
            if '\tBegin\t' in line or '\tvalue 1\t' in line:
                return True
    return False

def create_raw_data(trace_list):
    """Creates 2D dictionary of the raw input data and initializes with zero.
    The raw_data dictionary has the format: [raw data key][trace].
    """
    global raw_data_doc
    raw_data = {}
    for key in raw_data_doc:
        trace_dict = {}
        for trace_name in trace_list:
            trace_dict[trace_name] = 0.0

        raw_data[key] = trace_dict

    return raw_data

# Functions to extract GPU IDs

def create_trace_raw_data():
    """Create flat raw-data dict for a single trace."""
    return {key: 0.0 for key in raw_data_doc}


def get_trace_names(trace, trace_process_count):
    """Return (trace_name_control, trace_name) for .prv / .prv.gz traces."""
    if trace.endswith(".prv.gz"):
        trace_name_control = trace[:-7]
        trace_name = trace[:-7] + '_' + str(trace_process_count) + 'P'
    elif trace.endswith(".prv"):
        trace_name_control = trace[:-4]
        trace_name = trace[:-4] + '_' + str(trace_process_count) + 'P'
    else:
        raise ValueError(f"Unsupported trace format: {trace}")

    return trace_name_control, trace_name


# ----------------------------------------------------------------------
# GPU stream parsing and row-based device mapping
# ----------------------------------------------------------------------
def mpi_rank_from_thread_object(thread_obj):
    """
    Extract MPI rank/task index from Paraver thread object:
        THREAD app.task.thread
    Returns zero-based rank index.
    """
    try:
        obj = thread_obj.split()[1]
        parts = obj.split(".")
        if len(parts) != 3:
            return None
        task_idx = int(parts[1])
        return task_idx - 1
    except Exception:
        return None

def normalize_thread_object(value):
    """
    Normalize Paraver thread ids to the canonical form:
        THREAD x.y.z

    Examples:
      "1.1.2"         -> "THREAD 1.1.2"
      "THREAD 1.1.2"  -> "THREAD 1.1.2"
    """
    s = str(value).strip()
    if not s.startswith("THREAD "):
        s = f"THREAD {s}"
    return s


def parse_row_thread_labels(row_path):
    """
    Parse the LEVEL THREAD section of a .row file.

    The interpretation is positional.

    Example:
        THREAD 1.1.1
        GPU_a2f80454.1
        GPU_a2f80454.2
        GPU_a2f80454.3

    becomes:
        {
            "THREAD 1.1.1": "THREAD 1.1.1",
            "THREAD 1.1.2": "GPU_a2f80454.1",
            "THREAD 1.1.3": "GPU_a2f80454.2",
            "THREAD 1.1.4": "GPU_a2f80454.3",
        }

    Returns:
        dict mapping Paraver thread object -> label_or_self
    """
    thread_to_label = {}

    in_thread_section = False
    current_prefix = None   # tuple like ("1", "1")
    current_index = None    # integer like 1

    with open(row_path) as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line:
                continue

            if line.startswith("LEVEL THREAD SIZE"):
                in_thread_section = True
                current_prefix = None
                current_index = None
                continue

            if in_thread_section and line.startswith("LEVEL "):
                break

            if not in_thread_section:
                continue

            if line.startswith("THREAD "):
                obj = line.split()[1]   # e.g. 1.2.1
                parts = obj.split('.')
                if len(parts) != 3:
                    continue

                a, b, c = parts
                current_prefix = (a, b)
                try:
                    current_index = int(c)
                except ValueError:
                    current_prefix = None
                    current_index = None
                    continue

                # Header object maps to itself
                thread_obj = f"THREAD {a}.{b}.{current_index}"
                thread_to_label[thread_obj] = thread_obj

            else:
                # This line defines the next thread object in the same block
                if current_prefix is None or current_index is None:
                    continue

                current_index += 1
                a, b = current_prefix
                thread_obj = f"THREAD {a}.{b}.{current_index}"
                thread_to_label[thread_obj] = line
    ## print("LABEL: ", thread_to_label)
    return thread_to_label


def count_gpu_streams_by_mpi_rank(row_path):
    """
    Count GPU streams associated with each MPI rank from the Paraver .row file.

    Returns:
        {
            "total_streams": int,
            "streams_per_rank": int,
            "streams_by_rank": dict,
        }

    streams_per_rank values:
        0  -> no GPU streams detected
        >0 -> homogeneous number of streams per MPI rank
        -1 -> non-uniform number of streams across MPI ranks
    """
    thread_to_label = parse_row_thread_labels(row_path)

    streams_by_rank = defaultdict(int)

    for thread_obj, label in thread_to_label.items():
        if not str(label).startswith("GPU_"):
            continue

        rank_id = mpi_rank_from_thread_object(thread_obj)
        if rank_id is None:
            continue

        streams_by_rank[rank_id] += 1

    total_streams = sum(streams_by_rank.values())

    counts = list(streams_by_rank.values())

    if not counts:
        streams_per_rank = 0
    elif len(set(counts)) == 1:
        streams_per_rank = counts[0]
    else:
        streams_per_rank = -1

    return {
        "total_streams": total_streams,
        "streams_per_rank": streams_per_rank,
        "streams_by_rank": dict(streams_by_rank),
    }


def parse_row_cpu_nodes(row_path):
    """
    Parse LEVEL CPU section of a .row file.

    Returns:
        dict mapping CPU index (1-based) -> node name
    """
    cpu_to_node = {}

    in_cpu_section = False
    cpu_index = 0

    with open(row_path) as f:
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

            if "." in line:
                _, node = line.split(".", 1)
                cpu_to_node[cpu_index] = node.strip()

    return cpu_to_node


def device_uuid_from_row_label(label):
    """
    Convert:
        GPU_a2f80454.1
    into:
        a2f80454

    Returns None for non-GPU labels such as 'THREAD 1.1.1'.
    """
    label = label.strip()

    if not label.startswith("GPU_"):
        return None

    body = label[len("GPU_"):]  # a2f80454.1

    if "." in body:
        gpu_uuid, _stream_id = body.split(".", 1)
    else:
        gpu_uuid = body

    gpu_uuid = gpu_uuid.strip()
    return gpu_uuid if gpu_uuid else None


def node_from_thread_object(thread_obj, cpu_to_node):
    """
    Infer node from Paraver thread object:
        THREAD 1.3.2
    """
    try:
        obj = thread_obj.split()[1]
        parts = obj.split(".")
        if len(parts) != 3:
            return None

        _app, task_idx, _thread_idx = parts
        task_idx = int(task_idx)
    except (IndexError, ValueError):
        return None

    return cpu_to_node.get(task_idx)

def build_thread_to_device_map_from_row(row_path):
    thread_to_label = parse_row_thread_labels(row_path)
    cpu_to_node = parse_row_cpu_nodes(row_path)

    thread_to_device = {}

    for thread_obj, label in thread_to_label.items():
        device_key = device_key_from_row_label(
            label,
            thread_obj=thread_obj,
            cpu_to_node=cpu_to_node
        )

        if device_key is not None:
            thread_to_device[thread_obj] = device_key

    return thread_to_device


def parse_gpu_stream_stats(path, active_values=None, value_tol=1e-9, positive_only=False):
    """
    Parse a paramedir stream stats/csv file with rows like:
        1.1.2,START,DURATION,VALUE
    or
        THREAD 1.1.2,START,DURATION,VALUE

    Args:
        active_values: iterable of accepted values, e.g. (3.0, 7.0)
        positive_only: if True, keep rows with value > 0

    Returns:
        list of (thread_obj, start, end)
    where thread_obj is normalized to:
        "THREAD x.y.z"
    """
    intervals = []

    with open(path) as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line:
                continue

            if '\t' in line:
                parts = line.split('\t')
            elif ';' in line:
                parts = line.split(';')
            else:
                parts = line.split(',')

            if len(parts) < 4:
                continue

            thread_obj = normalize_thread_object(parts[0].strip())

            try:
                start = float(parts[1])
                duration = float(parts[2])
                value = float(parts[3])
            except ValueError:
                continue

            if duration <= 0.0:
                continue

            if positive_only:
                if value <= 0.0:
                    continue
            elif active_values is not None:
                if not any(abs(value - v) <= value_tol for v in active_values):
                    continue

            end = start + duration
            intervals.append((thread_obj, start, end))

    return intervals


def merge_intervals(intervals):
    """
    intervals: list of (start, end)
    returns a merged list of non-overlapping intervals.
    """
    if not intervals:
        return []

    intervals = sorted(intervals, key=lambda x: (x[0], x[1]))
    merged = [list(intervals[0])]

    for start, end in intervals[1:]:
        last_start, last_end = merged[-1]

        if start <= last_end:
            if end > last_end:
                merged[-1][1] = end
        else:
            merged.append([start, end])

    return [(s, e) for s, e in merged]


def subtract_intervals(intervals, mask_intervals):
    """
    Subtract mask_intervals from intervals.

    Both inputs are lists of (start, end). They do not need to be merged,
    but this function assumes normal interval semantics with start < end.

    Returns:
        list of (start, end) pieces from intervals not covered by mask_intervals
    """
    if not intervals:
        return []

    if not mask_intervals:
        return list(intervals)

    intervals = merge_intervals(intervals)
    mask_intervals = merge_intervals(mask_intervals)

    result = []
    j = 0

    for start, end in intervals:
        current = start

        while j < len(mask_intervals) and mask_intervals[j][1] <= current:
            j += 1

        k = j
        while k < len(mask_intervals):
            mstart, mend = mask_intervals[k]

            if mstart >= end:
                break

            if mstart > current:
                result.append((current, min(mstart, end)))

            current = max(current, mend)
            if current >= end:
                break

            k += 1

        if current < end:
            result.append((current, end))

    return result


def interval_union_length(intervals_a, intervals_b):
    """
    Return the total length of the union of two interval lists.
    """
    return sum_intervals(merge_intervals(list(intervals_a) + list(intervals_b)))


def sum_intervals(intervals):
    return sum(end - start for start, end in intervals)


def device_key_from_row_label(label, thread_obj=None, cpu_to_node=None):
    """
    Support both legacy and UUID-based GPU labels.

    Legacy:
        CUDA-D1.S1-as07r1b02 -> as07r1b02:D1

    New:
        GPU_a2f80454.1 -> <node>:a2f80454
    """
    label = label.strip()

    # New UUID-based format
    if label.startswith("GPU_"):
        body = label[len("GPU_"):]
        gpu_uuid = body.split(".", 1)[0]

        node = None
        if thread_obj is not None and cpu_to_node is not None:
            node = node_from_thread_object(thread_obj, cpu_to_node)

        if node is None:
            return None

        return f"{node}:{gpu_uuid}"

    # Legacy CUDA-Dx format
    if label.startswith("CUDA-"):
        parts = label.split("-")
        if len(parts) < 3:
            return None

        ds_part = parts[1]                  # D1.S1
        node_part = "-".join(parts[2:])     # node
        device_part = ds_part.split(".")[0] # D1

        return f"{node_part}:{device_part}"

    return None


def aggregate_gpu_metrics_from_stream_stats(useful_stats_path, memtransfer_stats_path, row_path):
    """
    Aggregate GPU metrics per device using the .row file as the authoritative
    mapping from Paraver thread objects to CUDA device labels.

    Definitions implemented explicitly:

      useful_device:
          flattened useful computation per device
          = | union(useful intervals from all streams in the device) |

      useful_memtransf_device:
          useful + non-overlapped memtransfer per device
          = |useful_flat| + |memtransfer_flat minus useful_flat|

    This matches the interpretation:
      - overlapping useful across streams is counted once
      - transfer overlapping useful is considered computation
      - only transfer not already covered by useful adds extra duration
    """
    thread_to_device = build_thread_to_device_map_from_row(row_path)

    useful_rows = parse_gpu_stream_stats(useful_stats_path, positive_only=True)

    useful_by_rank = defaultdict(list)

    if memtransfer_stats_path and os.path.exists(memtransfer_stats_path):
        memtransfer_rows = parse_gpu_stream_stats(memtransfer_stats_path, active_values=(3.0, 7.0))
    else:
        memtransfer_rows = []

    useful_by_device = defaultdict(list)
    memtransfer_by_device = defaultdict(list)

    unknown_useful_threads = set()
    unknown_memtransfer_threads = set()

    for thread_obj, start, end in useful_rows:
        device_key = thread_to_device.get(thread_obj)
        if device_key is None:
            unknown_useful_threads.add(thread_obj)
            continue

        useful_by_device[device_key].append((start, end))

        rank_id = mpi_rank_from_thread_object(thread_obj)
        if rank_id is not None:
            useful_by_rank[rank_id].append((start, end))


    for thread_obj, start, end in memtransfer_rows:
        device_key = thread_to_device.get(thread_obj)
        if device_key is None:
            unknown_memtransfer_threads.add(thread_obj)
            continue
        memtransfer_by_device[device_key].append((start, end))

    all_devices = sorted(set(useful_by_device.keys()) | set(memtransfer_by_device.keys()))

    result = {
        'useful_device_total': 0.0,
        'useful_device_max': 0.0,
        'useful_memtransf_device_total': 0.0,
        'useful_memtransf_device_max': 0.0,
        'per_device': {},
        'useful_device_by_rank': {},
        'unknown_useful_threads': sorted(unknown_useful_threads),
        'unknown_memtransfer_threads': sorted(unknown_memtransfer_threads),
    }


    for device_key in all_devices:
        useful_raw = useful_by_device.get(device_key, [])
        memtransfer_raw = memtransfer_by_device.get(device_key, [])

        # 1) Flatten useful per device
        useful_flat = merge_intervals(useful_raw)
        useful_total = sum_intervals(useful_flat)

        # 2) Flatten memtransfer per device
        memtransfer_flat = merge_intervals(memtransfer_raw)
        memtransfer_total = sum_intervals(memtransfer_flat)

        # 3) Keep only transfer not already covered by useful
        memtransfer_only = subtract_intervals(memtransfer_flat, useful_flat)
        memtransfer_only_total = sum_intervals(memtransfer_only)

        # 4) Useful + memory transfer according to TALP explanation
        useful_memtransf_total = useful_total + memtransfer_only_total

        result['per_device'][device_key] = {
            'useful_total': useful_total,
            'memtransfer_total': memtransfer_total,
            'memtransfer_only_total': memtransfer_only_total,
            'useful_memtransf_total': useful_memtransf_total,
            'useful_intervals_merged': useful_flat,
            'memtransfer_intervals_merged': memtransfer_flat,
            'memtransfer_only_intervals': memtransfer_only,
        }

        result['useful_device_total'] += useful_total
        result['useful_memtransf_device_total'] += useful_memtransf_total

        if useful_total > result['useful_device_max']:
            result['useful_device_max'] = useful_total

        if useful_memtransf_total > result['useful_memtransf_device_max']:
            result['useful_memtransf_device_max'] = useful_memtransf_total

    # ------------------------------------------------------------
    # Rank-level GPU useful aggregation.
    # This is used by the classic MPI+GPU hybrid model:
    # Useful_hybrid_rank[i] = Useful_host_rank[i] + Useful_device_rank[i]
    # ------------------------------------------------------------
    for rank_id, intervals in useful_by_rank.items():
        useful_rank_flat = merge_intervals(intervals)
        result['useful_device_by_rank'][rank_id] = sum_intervals(useful_rank_flat)

    return result

# ----------------------------------------------------------------------
# JOBS setting depending on Memory and traces size.
# ----------------------------------------------------------------------

def get_available_memory_bytes():
    try:
        with open('/proc/meminfo') as f:
            for line in f:
                if line.startswith('MemAvailable:'):
                    return int(line.split()[1]) * 1024
    except OSError:
        return None
    return None

def estimate_mem_per_worker_bytes(trace_list, cmdl_args):
    if cmdl_args.mem_per_worker_gb is not None:
        return int(cmdl_args.mem_per_worker_gb * (1024 ** 3))

    estimates = []
    for trace in trace_list:
        size = os.path.getsize(trace)

        if trace.endswith('.prv.gz'):
            estimate = max(2 * 1024**3, 4 * size)
        else:
            estimate = max(1 * 1024**3, 2 * size)

        estimates.append(estimate)

    return max(estimates) if estimates else 1 * 1024**3

def resolve_job_count(trace_list, cmdl_args):
    core_count = os.cpu_count() or 1
    trace_cap = len(trace_list)

    available_mem = get_available_memory_bytes()
    if available_mem is not None:
        usable_mem = int(0.8 * available_mem)
        mem_per_worker = estimate_mem_per_worker_bytes(trace_list, cmdl_args)
        memory_cap = max(1, usable_mem // mem_per_worker)
    else:
        memory_cap = core_count

    hard_cap = min(trace_cap, core_count, memory_cap)

    if str(cmdl_args.jobs).lower() == 'auto':
        jobs = hard_cap
    else:
        requested_jobs = max(1, int(cmdl_args.jobs))
        jobs = min(requested_jobs, hard_cap)

    return max(1, jobs), {
        'trace_cap': trace_cap,
        'core_cap': core_count,
        'memory_cap': memory_cap,
        'available_mem': available_mem,
    }


# ----------------------------------------------------------------------
# Main functions to processes rawdata.
# ----------------------------------------------------------------------
def init_cfgs():
    """Build cfg dictionary once."""
    cfgs = {}
    cfgs['root_dir'] = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'cfgs')
    cfgs['timings'] = os.path.join(cfgs['root_dir'], 'timings.cfg')
    cfgs['runtime'] = os.path.join(cfgs['root_dir'], 'runtime_app.cfg')
    cfgs['cycles'] = os.path.join(cfgs['root_dir'], 'cycles.cfg')
    cfgs['instructions'] = os.path.join(cfgs['root_dir'], 'instructions.cfg')
    cfgs['frequency'] = os.path.join(cfgs['root_dir'], 'frequency.cfg')
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
    cfgs['burst_useful'] = os.path.join(cfgs['root_dir'], 'burst_useful.cfg')
    cfgs['useful_host'] = os.path.join(cfgs['root_dir'], 'useful_host.cfg')

    # New global GPU stream extractors
    cfgs['useful_streams'] = os.path.join(cfgs['root_dir'], 'useful_streams.cfg')
    cfgs['memtransfer_streams'] = os.path.join(cfgs['root_dir'], 'memtransfer_streams.cfg')

    # OpenMP TALP-style timing extractors
    cfgs['omp_useful_regions'] = os.path.join(cfgs['root_dir'], '2d-Useful-duration-in-parallelregion.cfg')
    cfgs['mpi_time'] = os.path.join(cfgs['root_dir'], 'mpi-time.cfg')
    cfgs['omp_sched_fork_join'] = os.path.join(cfgs['root_dir'], 'sched_fork_join.cfg')
    cfgs['useful_duration'] = os.path.join(cfgs['root_dir'], 'useful-duration.cfg')
    cfgs['useful_outside_omp'] = os.path.join(cfgs['root_dir'], 'useful_outside_omp.cfg')

    return cfgs

def parse_omp_region_imbalance(path):
    """
    Parse a table where:
      rows    = OpenMP threads
      columns = OpenMP parallel regions
      values  = useful time per thread in each region

    Returns:
      {
        'useful_in_regions': total useful time inside OpenMP regions,
        'imbalance': total imbalance time across regions,
      }
    """
    rows = []

    with open(path) as f:
        for raw_line in f:
            line = raw_line.rstrip('\n')
            parts = line.split('\t')

            if not parts:
                continue

            key = parts[0].strip()

            if key in SUMMARY_KEYS:
                continue

            if not key.startswith('THREAD '):
                continue

            values = []
            for value in parts[1:]:
                if value == '':
                    continue
                try:
                    values.append(float(value))
                except ValueError:
                    pass

            if values:
                rows.append(values)

    if not rows:
        return {
            'useful_in_regions': 0.0,
            'imbalance': 0.0,
        }

    ncols = max(len(row) for row in rows)

    useful_total = 0.0
    imbalance_total = 0.0

    for col in range(ncols):
        col_values = []
        for row in rows:
            if col < len(row):
                col_values.append(row[col])
            else:
                col_values.append(0.0)

        max_value = max(col_values)
        useful_total += sum(col_values)
        imbalance_total += sum(max_value - value for value in col_values)

    return {
        'useful_in_regions': useful_total,
        'imbalance': imbalance_total,
    }


def parse_master_thread_values(path, skip_header=True):
    """
    Parse per-thread stats and return values only for OpenMP master threads.

    Master thread convention:
        THREAD app.task.1

    Returns:
        dict mapping task id -> value
        example: {"1": 212540.69, "2": 90248.95}
    """
    values = {}

    with open(path) as f:
        if skip_header:
            next(f, None)

        for raw_line in f:
            line = raw_line.rstrip('\n')
            parts = line.split('\t')

            if not parts:
                continue

            key = parts[0].strip()

            if key in SUMMARY_KEYS:
                continue

            if not key.startswith("THREAD "):
                continue

            thread_id = key.split()[1]
            thread_parts = thread_id.split(".")

            if len(thread_parts) != 3:
                continue

            app_id, task_id, thread_idx = thread_parts

            if thread_idx != "1":
                continue

            value = 0.0
            for field in parts[1:]:
                if field == "":
                    continue
                try:
                    value += float(field)
                except ValueError:
                    pass

            values[task_id] = value

    return values


def process_one_trace(
    trace,
    trace_process_count,
    trace_task_per_node_value,
    trace_mode_value,
    trace_tasks_value,
    trace_threads_value,
    cmdl_args,
    cfgs,
    dimemas_available,
    path_dest,
):
    """
    Analyze one trace and return isolated per-trace results.

    Returns:
      {
        "trace": trace,
        "trace_mode": trace_mode_value,
        "trace_process_count": trace_process_count,
        "trace_task_per_node": trace_task_per_node_value,
        "trace_tasks": trace_tasks_value,
        "trace_threads": trace_threads_value,
        "raw_data": trace_raw_data,
        "mpi_proc_count": int or None,
      }
    """
    trace_raw_data = create_trace_raw_data()
    mpi_proc_count = None

    # Create process-specific scratch directory
    base_name = os.path.basename(trace)
    if base_name.endswith(".prv.gz"):
        base_name = base_name[:-7]
    elif base_name.endswith(".prv"):
        base_name = base_name[:-4]

    local_path_dest = os.path.join(path_dest, base_name)
    os.makedirs(local_path_dest, exist_ok=True)

    trace_name_control, trace_name = get_trace_names(trace, trace_process_count)
    row_path = trace_name_control + '.row'

    time_tot = time.time()

    line = 'Analyzing ' + os.path.basename(trace)
    line += ' (' + str(trace_process_count) + ' processes'
    line += ', ' + str(trace_task_per_node_value) + ' tasks per node'
    line += ', ' + str(trace_mode_value) + ' mode'
    line += ', ' + human_readable(os.path.getsize(trace)) + ')'
    print(line)

    is_detailed_mpi = trace_mode_value[:12] == 'Detailed+MPI'
    is_burst_mpi = trace_mode_value[:9] == 'Burst+MPI'
    is_detailed_mpi_family = trace_mode_value in (
        'Detailed+MPI',
        'Detailed+MPI+OpenMP',
        'Detailed+MPI+CUDA',
    )
    is_mpi_omp = (trace_mode_value == 'Detailed+MPI+OpenMP')    

    is_talp_cuda = (trace_mode_value == 'Detailed+MPI+CUDA' and cmdl_args.pop_model_to_apply == 'talp')
    is_mpi_gpu = (trace_mode_value == 'Detailed+MPI+CUDA')

    mapping_devices = None
    trace_sim = ''
    trace_name_sim = ''
    
    gpu_useful_stats = None
    gpu_memtransfer_stats = None
    time_pmd_sim = 0.0
    # ------------------------------------------------------------
    # 1) Run paramedir on original trace
    # ------------------------------------------------------------
    cmd_base = ['paramedir', trace]

    cmd_base.extend([cfgs['timings'], trace_name + '.timings.stats.csv'])
    cmd_base.extend([cfgs['runtime'], trace_name + '.runtime.stats.csv'])
    cmd_base.extend([cfgs['cycles'], trace_name + '.cycles.stats.csv'])
    cmd_base.extend([cfgs['instructions'], trace_name + '.instructions.stats.csv'])
    cmd_base.extend([cfgs['flushing'], trace_name + '.flushing.stats.csv'])
    cmd_base.extend([cfgs['io_call'], trace_name + '.posixio_call.stats.csv'])
    cmd_base.extend([cfgs['io_cycles'], trace_name + '.posixio-cycles.stats.csv'])
    cmd_base.extend([cfgs['io_inst'], trace_name + '.posixio-inst.stats.csv'])
    cmd_base.extend([cfgs['flushing_cycles'], trace_name + '.flushing-cycles.stats.csv'])
    cmd_base.extend([cfgs['flushing_inst'], trace_name + '.flushing-inst.stats.csv'])
    cmd_base.extend([cfgs['frequency'], trace_name + '.frequency.stats.csv'])

    if is_detailed_mpi:
        cmd_base.extend([cfgs['mpi_io'], trace_name + '.mpi_io.stats.csv'])
        cmd_base.extend([cfgs['outside_mpi'], trace_name + '.outside_mpi.stats.csv'])
        cmd_base.extend([cfgs['mpiio_cycles'], trace_name + '.mpiio-cycles.stats.csv'])
        cmd_base.extend([cfgs['mpiio_inst'], trace_name + '.mpiio-inst.stats.csv'])

    if is_burst_mpi:
        cmd_base.extend([cfgs['burst_useful'], trace_name + '.burst_useful.stats.csv'])

    if is_talp_cuda or is_mpi_gpu:
        cmd_base.extend([
            cfgs['useful_host'],
            trace_name + '.useful_host.stats.csv'
        ])

        # Count GPU devices
        mapping_devices = get_device_stream_id_mapping(trace)
        gpu_devices = len(mapping_devices)

        trace_raw_data['count_devices'] = gpu_devices

        print("==> Count of devices: ", gpu_devices)

        # Count GPU streams from the Paraver .row hierarchy
        if os.path.exists(row_path):
            gpu_stream_info = count_gpu_streams_by_mpi_rank(row_path)

            trace_raw_data['count_gpu_streams'] = (
                gpu_stream_info['total_streams']
            )

            trace_raw_data['gpu_streams_per_rank'] = (
                gpu_stream_info['streams_per_rank']
            )

            print(
                "==> Count of GPU streams: ",
                gpu_stream_info['total_streams']
            )

            if gpu_stream_info['streams_per_rank'] == -1:
                print(
                    "==> GPU streams per MPI rank: non-uniform"
                )
            else:
                print(
                    "==> GPU streams per MPI rank: ",
                    gpu_stream_info['streams_per_rank']
                )

            if cmdl_args.debug:
                print(
                    "==DEBUG== GPU streams by MPI rank: ",
                    gpu_stream_info['streams_by_rank']
                )

        else:
            trace_raw_data['count_gpu_streams'] = 0
            trace_raw_data['gpu_streams_per_rank'] = 0

            print(
                "==WARNING== Cannot count GPU streams: "
                "{} not found.".format(row_path)
            )

        gpu_useful_stats = (
            trace_name + '.useful_streams.stats.csv'
        )

        gpu_memtransfer_stats = (
            trace_name + '.memtransfer_streams.stats.csv'
        )

        cmd_base.extend([
            cfgs['useful_streams'],
            gpu_useful_stats
        ])

        cmd_base.extend([
            cfgs['memtransfer_streams'],
            gpu_memtransfer_stats
        ])

  
    if is_mpi_omp:
        cmd_base.extend([cfgs['omp_useful_regions'],trace_name + '.omp_useful_regions.stats.csv'])
        cmd_base.extend([
            cfgs['mpi_time'],
            trace_name + '.mpi_time.stats.csv'
        ])
        cmd_base.extend([
            cfgs['omp_sched_fork_join'],
            trace_name + '.omp_sched_fork_join.stats.csv'
        ])
        cmd_base.extend([
            cfgs['useful_duration'],
            trace_name + '.useful_duration.stats.csv'
        ])
        cmd_base.extend([
            cfgs['useful_outside_omp'],
            trace_name + '.useful_outside_omp.stats.csv'
        ])


    time_base = time.time()
    run_command(cmd_base, cmdl_args)
    time_base = time.time() - time_base

    # ------------------------------------------------------------
    # 2) Optional Dimemas simulation
    # ------------------------------------------------------------
    if dimemas_available and not cmdl_args.skip_simulation:
        if is_detailed_mpi_family and os.path.exists(trace_name + '.outside_mpi.stats.csv'):
            time_dim = time.time()

            trace_sim = create_ideal_trace(
                trace,
                trace_process_count,
                trace_task_per_node_value,
                trace_mode_value,
                trace_tasks_value,
                trace_threads_value,
                cmdl_args
            )

            if trace_sim:
                trace_name_sim = trace_sim[:-4]

            time_dim = time.time() - time_dim
            if trace_sim != '':
                print('Successfully created simulated trace with Dimemas in {0:.1f} seconds.'.format(time_dim))
            else:
                print('Failed to create simulated trace with Dimemas.')
            
            if cmdl_args.hyb_mpiomp and trace_mode_value == 'Detailed+MPI+OpenMP':
                time_dim = time.time()
                cmdl_args.ideal_omp = True
                cmdl_args.simulation_openmp = True
                hybrid_trace_sim = create_ideal_trace(
                    trace,
                    trace_process_count,
                    trace_task_per_node_value,
                    trace_mode_value,
                    trace_tasks_value,
                    trace_threads_value,
                    cmdl_args,
                    "_hybrid"
                )

                if hybrid_trace_sim:
                    hybrid_trace_name_sim = hybrid_trace_sim[:-4]
                else:
                    hybrid_trace_name_sim = ""

                time_dim = time.time() - time_dim
                if hybrid_trace_sim != '':
                    print('Successfully created Hybrid simulated trace with Dimemas in {0:.1f} seconds.'.format(time_dim))
                else:
                    print('Failed to create Hybrid simulated trace with Dimemas.')

    if dimemas_available and os.path.exists(trace_name + '.outside_mpi.stats.csv') and not cmdl_args.skip_simulation:
        if is_detailed_mpi_family and trace_sim != '':
            cmd_ideal = ['paramedir', trace_sim]
            cmd_ideal.extend([cfgs['timings'], trace_name_sim + '.timings.stats.csv'])
            cmd_ideal.extend([cfgs['runtime'], trace_name_sim + '.runtime.stats.csv'])
            cmd_ideal.extend([cfgs['outside_mpi'], trace_name_sim + '.outside_mpi.stats.csv'])

            time_pmd_sim = time.time()
            run_command(cmd_ideal, cmdl_args)
            time_pmd_sim = time.time() - time_pmd_sim
            #print(f'Simulated trace analyzed with paramedir in: {time_pmd_sim:.1f} s')
        
        if cmdl_args.hyb_mpiomp and trace_mode_value == 'Detailed+MPI+OpenMP':
            if is_detailed_mpi_family and hybrid_trace_sim != '':
                cmd_ideal = ['paramedir', hybrid_trace_sim]
                cmd_ideal.extend([cfgs['timings'], hybrid_trace_name_sim + '.timings.stats.csv'])
                cmd_ideal.extend([cfgs['runtime'], hybrid_trace_name_sim + '.runtime.stats.csv'])
                cmd_ideal.extend([cfgs['outside_mpi'], hybrid_trace_name_sim + '.outside_mpi.stats.csv'])

                time_pmd_sim_hybrid = time.time()
                run_command(cmd_ideal, cmdl_args)
                time_pmd_sim = time_pmd_sim + (time.time() - time_pmd_sim_hybrid)

                    
    # ------------------------------------------------------------
    # 3) Validate generated files
    # ------------------------------------------------------------
    error_timing = 0
    error_counters = 0
    error_ideal = 0
    error_ideal_hybrid = 0

    if not os.path.exists(trace_name + '.timings.stats.csv') or \
            not os.path.exists(trace_name + '.runtime.stats.csv'):
        print('==ERROR== Failed to compute timing information with paramedir.')
        error_timing = 1

    if not os.path.exists(trace_name + '.outside_mpi.stats.csv') and trace_mode_value[:5] != 'Burst' \
            and 'MPI' in trace_mode_value:
        print('==ERROR== Failed to compute outside MPI timing information with paramedir.')
        error_timing = 1

    if not os.path.exists(trace_name + '.cycles.stats.csv') or \
            not os.path.exists(trace_name + '.instructions.stats.csv'):
        print('==ERROR== Failed to compute counter information with paramedir.')
        error_counters = 1

    if dimemas_available and not cmdl_args.skip_simulation:
        if is_detailed_mpi_family and os.path.exists(trace_name + '.outside_mpi.stats.csv'):
            if trace_sim == '' or \
                    not os.path.exists(trace_name_sim + '.timings.stats.csv') or \
                    not os.path.exists(trace_name_sim + '.runtime.stats.csv') or \
                    not os.path.exists(trace_name_sim + '.outside_mpi.stats.csv'):
                print('==ERROR== Failed to compute simulated timing information with paramedir.')
                error_ideal = 1
                trace_sim = ''
            
            if cmdl_args.hyb_mpiomp and trace_mode_value == 'Detailed+MPI+OpenMP':
                if hybrid_trace_sim == '' or \
                        not os.path.exists(hybrid_trace_name_sim + '.timings.stats.csv') or \
                        not os.path.exists(hybrid_trace_name_sim + '.runtime.stats.csv') or \
                        not os.path.exists(hybrid_trace_name_sim + '.outside_mpi.stats.csv'):
                    print('==ERROR== Failed to compute simulated timing information with paramedir.')
                    error_ideal_hybrid = 1
                    hybrid_trace_sim = ''
    else:
        error_ideal = 0
        error_ideal_hybrid = 0

    if error_timing or error_counters or error_ideal or error_ideal_hybrid:
        print('Failed to analyze trace with paramedir')
    else:
        print('Successfully analyzed trace with paramedir in {0:.1f} seconds.'.format(time_base + time_pmd_sim))

    # ------------------------------------------------------------
    # 4) Parse output files
    # ------------------------------------------------------------
    time_prs = time.time()

    # useful_cyc
    if os.path.exists(trace_name + '.cycles.stats.csv'):
        trace_raw_data['useful_cyc'] = parse_positive_value_sum(trace_name + '.cycles.stats.csv', skip_header=True)
    else:
        trace_raw_data['useful_cyc'] = 'NaN'

    # runtime
    if os.path.exists(trace_name + '.frequency.stats.csv'):
        _, frequency_avg, _ = parse_total_average_max(trace_name + '.frequency.stats.csv')
        trace_raw_data['frequency'] = frequency_avg
    else:
        trace_raw_data['frequency'] = 'NaN'


    # useful_ins + procs_ins + instructions mask
    procs_ins = 0
    content_insttructions = []
    if os.path.exists(trace_name + '.instructions.stats.csv'):
        useful_ins, procs_ins, content_insttructions = parse_positive_value_sum_and_mask(
            trace_name + '.instructions.stats.csv',
            skip_header=True
        )
        trace_raw_data['procs_ins'] = procs_ins
        trace_raw_data['useful_ins'] = float(useful_ins)
    else:
        trace_raw_data['useful_ins'] = 'NaN'

    # POSIX-IO aggregates
    posixio_totals = None
    if os.path.exists(trace_name + '.posixio_call.stats.csv'):
        posixio_totals = parse_tab_total_row_values(trace_name + '.posixio_call.stats.csv')
        posix_stats = parse_tab_stats(trace_name + '.posixio_call.stats.csv')
        trace_raw_data['io_tot'] = posix_stats['tot']
        trace_raw_data['io_avg'] = posix_stats['avg']
        trace_raw_data['io_max'] = posix_stats['max']
        trace_raw_data['io_std'] = posix_stats['std']
    else:
        trace_raw_data['io_tot'] = 0.0
        trace_raw_data['io_avg'] = 0.0
        trace_raw_data['io_max'] = 0.0
        trace_raw_data['io_std'] = 0.0

    # timings.stats
    if os.path.exists(trace_name + '.timings.stats.csv'):
        timings_data = parse_timings_stats(
            trace_name + '.timings.stats.csv',
            instructions_mask=content_insttructions if procs_ins != 0 else None,
            posixio_totals=posixio_totals,
            has_pcf=os.path.exists(trace_name_control + '.pcf')
        )

        trace_raw_data['useful_tot'] = timings_data['useful_tot']
        trace_raw_data['useful_avg'] = timings_data['useful_avg']
        trace_raw_data['useful_max'] = timings_data['useful_max']
        trace_raw_data['useful_not_0_tot'] = timings_data['useful_not_0_tot']
        trace_raw_data['useful_not_0_avg'] = timings_data['useful_not_0_avg']
        trace_raw_data['useful_not_0_max'] = timings_data['useful_not_0_max']
        trace_raw_data['io_state_tot'] = timings_data['io_state_tot']
        trace_raw_data['io_state_avg'] = timings_data['io_state_avg']
        trace_raw_data['io_state_max'] = timings_data['io_state_max']
        trace_raw_data['useful_plus_io_avg'] = timings_data['useful_plus_io_avg']
        trace_raw_data['useful_plus_io_max'] = timings_data['useful_plus_io_max']
    else:
        trace_raw_data['useful_tot'] = 'NaN'
        trace_raw_data['useful_avg'] = 'NaN'
        trace_raw_data['useful_max'] = 'NaN'
        trace_raw_data['useful_not_0_tot'] = 'NaN'
        trace_raw_data['useful_not_0_avg'] = 'NaN'
        trace_raw_data['useful_not_0_max'] = 'NaN'
        trace_raw_data['io_state_tot'] = 'NaN'
        trace_raw_data['io_state_avg'] = 'NaN'
        trace_raw_data['io_state_max'] = 'NaN'
        trace_raw_data['useful_plus_io_avg'] = 'NaN'
        trace_raw_data['useful_plus_io_max'] = 'NaN'

    # runtime
    if os.path.exists(trace_name + '.runtime.stats.csv'):
        _, runtime_avg, _ = parse_total_average_max(trace_name + '.runtime.stats.csv')
        trace_raw_data['runtime'] = runtime_avg
    else:
        trace_raw_data['runtime'] = 'NaN'

    # outside_mpi
    if os.path.exists(trace_name + '.outside_mpi.stats.csv') and is_detailed_mpi:
        outside_data = parse_outside_mpi_stats(
            trace_name + '.outside_mpi.stats.csv',
            trace_raw_data['runtime']
        )
        trace_raw_data['outsidempi_tot_diff'] = outside_data['outsidempi_tot_diff']
        trace_raw_data['outsidempi_tot'] = outside_data['outsidempi_tot']
        trace_raw_data['outsidempi_avg'] = outside_data['outsidempi_avg']
        trace_raw_data['outsidempi_max'] = outside_data['outsidempi_max']
        trace_raw_data['mpicomm_tot'] = outside_data['mpicomm_tot']
        if outside_data['mpi_proc_count'] > 0:
            mpi_proc_count = outside_data['mpi_proc_count']
    else:
        trace_raw_data['outsidempi_tot_diff'] = 'NaN'
        trace_raw_data['outsidempi_tot'] = 'NaN'
        trace_raw_data['outsidempi_avg'] = 'NaN'
        trace_raw_data['outsidempi_max'] = 'NaN'
        trace_raw_data['mpicomm_tot'] = 'NaN'

    # flushing
    if os.path.exists(trace_name + '.flushing.stats.csv'):
        with open(trace_name + '.flushing.stats.csv') as f:
            content = f.readlines()
            flushing_exist = ('\tBegin\t\n' in content) or ('\tvalue 1\t\n' in content)

        if flushing_exist:
            flushing_tot, flushing_avg, flushing_max = parse_total_average_max(trace_name + '.flushing.stats.csv')
            trace_raw_data['flushing_tot'] = float(flushing_tot)
            trace_raw_data['flushing_avg'] = float(flushing_avg)
            trace_raw_data['flushing_max'] = float(flushing_max)
        else:
            trace_raw_data['flushing_tot'] = 0.0
            trace_raw_data['flushing_avg'] = 0.0
            trace_raw_data['flushing_max'] = 0.0
    else:
        trace_raw_data['flushing_tot'] = 0.0
        trace_raw_data['flushing_avg'] = 0.0
        trace_raw_data['flushing_max'] = 0.0

    # total-only counters
    trace_raw_data['flushing_cyc'] = parse_total_as_int(trace_name + '.flushing-cycles.stats.csv') \
        if os.path.exists(trace_name + '.flushing-cycles.stats.csv') else 0.0
    trace_raw_data['flushing_ins'] = parse_total_as_int(trace_name + '.flushing-inst.stats.csv') \
        if os.path.exists(trace_name + '.flushing-inst.stats.csv') else 0.0
    trace_raw_data['io_cyc'] = parse_total_as_int(trace_name + '.posixio-cycles.stats.csv') \
        if os.path.exists(trace_name + '.posixio-cycles.stats.csv') else 0.0
    trace_raw_data['io_ins'] = parse_total_as_int(trace_name + '.posixio-inst.stats.csv') \
        if os.path.exists(trace_name + '.posixio-inst.stats.csv') else 0.0
    trace_raw_data['mpiio_cyc'] = parse_total_as_int(trace_name + '.mpiio-cycles.stats.csv') \
        if os.path.exists(trace_name + '.mpiio-cycles.stats.csv') and is_detailed_mpi else 0.0
    trace_raw_data['mpiio_ins'] = parse_total_as_int(trace_name + '.mpiio-inst.stats.csv') \
        if os.path.exists(trace_name + '.mpiio-inst.stats.csv') and is_detailed_mpi else 0.0

    # mpi_io aggregates
    if os.path.exists(trace_name + '.mpi_io.stats.csv') and is_detailed_mpi:
        mpiio_stats = parse_tab_stats(trace_name + '.mpi_io.stats.csv')
        trace_raw_data['mpiio_tot'] = mpiio_stats['tot']
        trace_raw_data['mpiio_avg'] = mpiio_stats['avg']
        trace_raw_data['mpiio_max'] = mpiio_stats['max']
        trace_raw_data['mpiio_std'] = mpiio_stats['std']
    else:
        trace_raw_data['mpiio_tot'] = 0.0
        trace_raw_data['mpiio_avg'] = 0.0
        trace_raw_data['mpiio_max'] = 0.0
        trace_raw_data['mpiio_std'] = 0.0

    # GPU metrics
    time_gpu_agg = 0.0
    if (is_mpi_gpu and os.path.exists(row_path)):
        trace_raw_data['useful_device'] = 0.0
        trace_raw_data['useful_device_max'] = 0.0
        trace_raw_data['useful_memtransf_device'] = 0.0
        trace_raw_data['useful_memtransf_device_max'] = 0.0
        gpu_agg = {}
        
        if gpu_useful_stats and os.path.exists(gpu_useful_stats):
            time_gpu_agg = time.time()
            gpu_agg = aggregate_gpu_metrics_from_stream_stats(
                gpu_useful_stats,
                gpu_memtransfer_stats,
                row_path
            )
            time_gpu_agg = time.time() - time_gpu_agg
            print('Successfully aggregated GPU time in {0:.1f} seconds.'.format(time_gpu_agg))    
            
            if cmdl_args.debug:
                for dev, vals in gpu_agg['per_device'].items():
                    print(
                        f'==DEBUG== {dev}: '
                        f'useful={vals["useful_total"]:.2f}, '
                        f'memtransfer={vals["memtransfer_total"]:.2f}, '
                        f'memtransfer_only={vals["memtransfer_only_total"]:.2f}, '
                        f'useful_plus_memtransfer={vals["useful_memtransf_total"]:.2f}')

            trace_raw_data['useful_device'] = gpu_agg['useful_device_total']
            trace_raw_data['useful_device_max'] = gpu_agg['useful_device_max']
            trace_raw_data['useful_memtransf_device'] = gpu_agg['useful_memtransf_device_total']
            trace_raw_data['useful_memtransf_device_max'] = gpu_agg['useful_memtransf_device_max']

            if gpu_agg['unknown_useful_threads']:
                print('==WARNING== Unknown useful thread ids: ' +
                      ', '.join(gpu_agg['unknown_useful_threads'][:10]))

            if gpu_agg['unknown_memtransfer_threads']:
                print('==WARNING== Unknown memtransfer thread ids: ' +
                      ', '.join(gpu_agg['unknown_memtransfer_threads'][:10]))


        ## host_useful_values = []

        if os.path.exists(trace_name + '.useful_host.stats.csv'):
            useful_host_total, _, useful_host_max = parse_total_average_max(
                trace_name + '.useful_host.stats.csv'
            )

            if useful_host_total is not None and useful_host_max is not None:
                trace_raw_data['useful_host'] = float(useful_host_total)
                trace_raw_data['useful_host_max'] = float(useful_host_max)
            else:
                trace_raw_data['useful_host'] = 0.0
                trace_raw_data['useful_host_max'] = 0.0
        else:
            trace_raw_data['useful_host'] = 0.0
            trace_raw_data['useful_host_max'] = 0.0
          
    # OpenMP TALP-style raw timings
    if is_mpi_omp:      
        # Useful inside OpenMP parallel regions + imbalance
        if os.path.exists(trace_name + '.omp_useful_regions.stats.csv'):
            omp_region_data = parse_omp_region_imbalance(
                trace_name + '.omp_useful_regions.stats.csv'
            )
            trace_raw_data['time_omp_imbalance'] = omp_region_data['imbalance']
        else:
            trace_raw_data['time_omp_imbalance'] = 'NaN'

        # OpenMP scheduling/fork-join overhead
        if os.path.exists(trace_name + '.omp_sched_fork_join.stats.csv'):
            sched_stats = parse_tab_stats(trace_name + '.omp_sched_fork_join.stats.csv')
            trace_raw_data['time_omp_schedule'] = sched_stats['tot']
        else:
            trace_raw_data['time_omp_schedule'] = 'NaN'

        # Useful outside OpenMP parallel regions
        if os.path.exists(trace_name + '.useful_outside_omp.stats.csv'):
            useful_outside_stats = parse_tab_stats(
                trace_name + '.useful_outside_omp.stats.csv'
            )
            useful_outside_omp = useful_outside_stats['tot']
        else:
            useful_outside_omp = 0.0

        # MPI time
        if os.path.exists(trace_name + '.mpi_time.stats.csv'):
            mpi_time_stats = parse_tab_stats(trace_name + '.mpi_time.stats.csv')
            mpi_time = mpi_time_stats['tot']
        else:
            mpi_time = 0.0

        # T_no_OMP = all useful computation + MPI time
        useful_total = float(trace_raw_data['useful_tot'])
        trace_raw_data['time_no_omp'] = useful_total + mpi_time

        # Serial OpenMP loss:
        # for each MPI rank, useful/MPI time executed by the master thread
        # outside OpenMP parallel regions is projected to inactive worker threads.

        useful_outside_by_master = {}
        if os.path.exists(trace_name + '.useful_outside_omp.stats.csv'):
            useful_outside_by_master = parse_master_thread_values(
                trace_name + '.useful_outside_omp.stats.csv'
            )

        mpi_by_master = {}
        if os.path.exists(trace_name + '.mpi_time.stats.csv'):
            mpi_by_master = parse_master_thread_values(
                trace_name + '.mpi_time.stats.csv'
            )

        threads_per_rank = max(int(trace_threads_value), 1)

        time_omp_serial = 0.0
        all_task_ids = set(useful_outside_by_master.keys()) | set(mpi_by_master.keys())

        for task_id in all_task_ids:
            useful_outside_value = useful_outside_by_master.get(task_id, 0.0)
            mpi_value = mpi_by_master.get(task_id, 0.0)

            serial_active = useful_outside_value + mpi_value
            time_omp_serial += serial_active * max(threads_per_rank - 1, 0)

        trace_raw_data['time_omp_serial'] = time_omp_serial
    else:
        trace_raw_data['time_no_omp'] = 'Non-Avail'
        trace_raw_data['time_omp_imbalance'] = 'Non-Avail'
        trace_raw_data['time_omp_schedule'] = 'Non-Avail'
        trace_raw_data['time_omp_serial'] = 'Non-Avail'

    # burst mode
    if trace_mode_value == 'Burst+MPI':
        if os.path.exists(trace_name + '.burst_useful.stats.csv'):
            totals = parse_tab_total_row_values(trace_name + '.burst_useful.stats.csv')
            if totals:
                trace_raw_data['burst_useful_tot'] = sum(totals)
                trace_raw_data['burst_useful_avg'] = sum(totals) / len(totals)
                trace_raw_data['burst_useful_max'] = max(totals)
            else:
                trace_raw_data['burst_useful_avg'] = 'NaN'
                trace_raw_data['burst_useful_max'] = 'NaN'
                trace_raw_data['burst_useful_tot'] = 'NaN'
        else:
            trace_raw_data['burst_useful_avg'] = 'NaN'
            trace_raw_data['burst_useful_max'] = 'NaN'
            trace_raw_data['burst_useful_tot'] = 'NaN'
    else:
        trace_raw_data['burst_useful_avg'] = 0.0
        trace_raw_data['burst_useful_max'] = 0.0
        trace_raw_data['burst_useful_tot'] = 0.0

    # simulated trace metrics
    if is_detailed_mpi_family and (dimemas_available and os.path.exists(trace_name + '.outside_mpi.stats.csv') and not cmdl_args.skip_simulation):
        if os.path.exists(trace_name_sim + '.timings.stats.csv'):
            _, _, useful_dim_max = parse_total_average_max(trace_name_sim + '.timings.stats.csv')
            trace_raw_data['useful_dim'] = float(useful_dim_max)
        else:
            trace_raw_data['useful_dim'] = 'NaN'

        if os.path.exists(trace_name_sim + '.runtime.stats.csv'):
            _, runtime_sim_avg, _ = parse_total_average_max(trace_name_sim + '.runtime.stats.csv')
            trace_raw_data['runtime_dim'] = float(runtime_sim_avg)
        else:
            trace_raw_data['runtime_dim'] = 'NaN'

        if os.path.exists(trace_name_sim + '.outside_mpi.stats.csv'):
            # keep current logic for now; refactor later if desired
            with open(trace_name_sim + '.outside_mpi.stats.csv') as f:
                content = f.readlines()
                list_outside_mpi = []
                init_count_thread = False
                count_threads = 1
                max_time_outside_mpi = 0.0

                for line1 in content[1:(len(content) - 8)]:
                    line_parts = line1.split("\t")
                    if line_parts:
                        if line_parts[0] != 'Num. Cells' and line_parts[0] != 'Total' and line_parts[0] != 'Average' \
                                and line_parts[0] != 'Maximum' and line_parts[0] != 'StDev' \
                                and line_parts[0] != 'Avg/Max' and line_parts[0] != '\n':
                            if line_parts[0].split(".")[2] == '1':
                                list_outside_mpi.append(float(line_parts[1]))
                                if len(list_outside_mpi) > 1:
                                    pass
                                count_threads = 1
                            else:
                                if len(list_outside_mpi) == 1 and not init_count_thread:
                                    count_threads = 2
                                    init_count_thread = True
                                else:
                                    count_threads += 1

                            if line_parts[0] == "THREAD 1.1.1":
                                max_time_outside_mpi = float(line_parts[1])

                if len(list_outside_mpi) != 0:
                    trace_raw_data['outsidempi_dim'] = max(list_outside_mpi)
                else:
                    trace_raw_data['outsidempi_dim'] = max_time_outside_mpi
        else:
            trace_raw_data['outsidempi_dim'] = 0.0
    else:
        trace_raw_data['useful_dim'] = 'Non-Avail'
        trace_raw_data['runtime_dim'] = 'Non-Avail'
        trace_raw_data['outsidempi_dim'] = 'Non-Avail'


    # HYBRID Simulated trace metrics 
    if is_detailed_mpi_family and (dimemas_available and os.path.exists(trace_name + '.outside_mpi.stats.csv') and not cmdl_args.skip_simulation):
        if cmdl_args.hyb_mpiomp and trace_mode_value == 'Detailed+MPI+OpenMP':        
            if os.path.exists(hybrid_trace_name_sim + '.timings.stats.csv'):
                _, _, useful_dim_max = parse_total_average_max(hybrid_trace_name_sim + '.timings.stats.csv')
                trace_raw_data['hybrid_useful_dim'] = float(useful_dim_max)
            else:
                trace_raw_data['hybrid_useful_dim'] = 'NaN'

            if os.path.exists(hybrid_trace_name_sim + '.runtime.stats.csv'):
                _, runtime_sim_avg, _ = parse_total_average_max(hybrid_trace_name_sim + '.runtime.stats.csv')
                trace_raw_data['hybrid_runtime_dim'] = float(runtime_sim_avg)
            else:
                trace_raw_data['hybrid_runtime_dim'] = 'NaN'

            if os.path.exists(hybrid_trace_name_sim + '.outside_mpi.stats.csv'):
                # keep current logic for now; refactor later if desired
                with open(hybrid_trace_name_sim + '.outside_mpi.stats.csv') as f:
                    content = f.readlines()
                    list_outside_mpi = []
                    init_count_thread = False
                    count_threads = 1
                    max_time_outside_mpi = 0.0

                    for line1 in content[1:(len(content) - 8)]:
                        line_parts = line1.split("\t")
                        if line_parts:
                            if line_parts[0] != 'Num. Cells' and line_parts[0] != 'Total' and line_parts[0] != 'Average' \
                                    and line_parts[0] != 'Maximum' and line_parts[0] != 'StDev' \
                                    and line_parts[0] != 'Avg/Max' and line_parts[0] != '\n':
                                if line_parts[0].split(".")[2] == '1':
                                    list_outside_mpi.append(float(line_parts[1]))
                                    if len(list_outside_mpi) > 1:
                                        pass
                                    count_threads = 1
                                else:
                                    if len(list_outside_mpi) == 1 and not init_count_thread:
                                        count_threads = 2
                                        init_count_thread = True
                                    else:
                                        count_threads += 1

                                if line_parts[0] == "THREAD 1.1.1":
                                    max_time_outside_mpi = float(line_parts[1])

                    if len(list_outside_mpi) != 0:
                        trace_raw_data['hybrid_outsidempi_dim'] = max(list_outside_mpi)
                    else:
                        trace_raw_data['hybrid_outsidempi_dim'] = max_time_outside_mpi
            else:
                trace_raw_data['hybrid_outsidempi_dim'] = 0.0
    else:
        trace_raw_data['hybrid_useful_dim'] = 'Non-Avail'
        trace_raw_data['hybrid_runtime_dim'] = 'Non-Avail'
        trace_raw_data['hybrid_outsidempi_dim'] = 'Non-Avail'


    # ------------------------------------------------------------
    # 5) Move generated files
    # ------------------------------------------------------------
    if is_detailed_mpi_family and (dimemas_available and os.path.exists(trace_name + '.outside_mpi.stats.csv')) and not cmdl_args.skip_simulation:
        move_files(trace_name + '.dimemas_ideal.cfg', local_path_dest, cmdl_args)
        move_files(trace_name + '.dim', local_path_dest, cmdl_args)
        if trace_sim != '':
            move_files(trace_name_sim + '.timings.stats.csv', local_path_dest, cmdl_args)
            move_files(trace_name_sim + '.runtime.stats.csv', local_path_dest, cmdl_args)
            move_files(trace_name_sim + '.outside_mpi.stats.csv', local_path_dest, cmdl_args)
            move_files(trace_sim, local_path_dest, cmdl_args)
            move_files(trace_sim[:-4] + '.pcf', local_path_dest, cmdl_args)
            move_files(trace_sim[:-4] + '.row', local_path_dest, cmdl_args)

            if trace.endswith(".prv.gz"):
                remove_files(trace_name_control + '.prv', cmdl_args)
        if cmdl_args.hyb_mpiomp and trace_mode_value == 'Detailed+MPI+OpenMP':
            if hybrid_trace_sim != '':
                move_files(hybrid_trace_name_sim + '.timings.stats.csv', local_path_dest, cmdl_args)
                move_files(hybrid_trace_name_sim + '.runtime.stats.csv', local_path_dest, cmdl_args)
                move_files(hybrid_trace_name_sim + '.outside_mpi.stats.csv', local_path_dest, cmdl_args)
                move_files(hybrid_trace_sim, local_path_dest, cmdl_args)
                move_files(hybrid_trace_sim[:-4] + '.pcf', local_path_dest, cmdl_args)
                move_files(hybrid_trace_sim[:-4] + '.row', local_path_dest, cmdl_args)          

                if trace.endswith(".prv.gz"):
                    remove_files(trace_name_control + '.prv', cmdl_args)            
    
    remove_files(trace_name + '.row', cmdl_args)
    remove_files(trace_name + '.pcf', cmdl_args)
    move_files(trace_name + '.timings.stats.csv', local_path_dest, cmdl_args)
    move_files(trace_name + '.runtime.stats.csv', local_path_dest, cmdl_args)
    move_files(trace_name + '.cycles.stats.csv', local_path_dest, cmdl_args)
    move_files(trace_name + '.instructions.stats.csv', local_path_dest, cmdl_args)
    move_files(trace_name + '.flushing.stats.csv', local_path_dest, cmdl_args)
    move_files(trace_name + '.posixio-cycles.stats.csv', local_path_dest, cmdl_args)
    move_files(trace_name + '.posixio-inst.stats.csv', local_path_dest, cmdl_args)
    move_files(trace_name + '.flushing-cycles.stats.csv', local_path_dest, cmdl_args)
    move_files(trace_name + '.flushing-inst.stats.csv', local_path_dest, cmdl_args)
    move_files(trace_name + '.frequency.stats.csv', local_path_dest, cmdl_args)

    if is_detailed_mpi:
        move_files(trace_name + '.mpi_io.stats.csv', local_path_dest, cmdl_args)
        move_files(trace_name + '.posixio_call.stats.csv', local_path_dest, cmdl_args)
        move_files(trace_name + '.outside_mpi.stats.csv', local_path_dest, cmdl_args)
        move_files(trace_name + '.mpiio-cycles.stats.csv', local_path_dest, cmdl_args)
        move_files(trace_name + '.mpiio-inst.stats.csv', local_path_dest, cmdl_args)

    if is_burst_mpi:
        move_files(trace_name + '.2dh_BurstEff.stats.csv', local_path_dest, cmdl_args)
        move_files(trace_name + '.burst_useful.stats.csv', local_path_dest, cmdl_args)

    if is_mpi_gpu:
        if os.path.exists(trace_name + '.useful_host.stats.csv'):
            move_files(trace_name + '.useful_host.stats.csv', local_path_dest, cmdl_args)
        if os.path.exists(trace_name + '.useful_streams.stats.csv'):
            move_files(trace_name + '.useful_streams.stats.csv', local_path_dest, cmdl_args)
        if os.path.exists(trace_name + '.useful_streams.stats.legend.csv'):
            move_files(trace_name + '.useful_streams.stats.legend.csv', local_path_dest, cmdl_args)
        if os.path.exists(trace_name + '.memtransfer_streams.stats.csv'):
            move_files(trace_name + '.memtransfer_streams.stats.csv', local_path_dest, cmdl_args)
        if os.path.exists(trace_name + '.memtransfer_streams.stats.legend.csv'):
            move_files(trace_name + '.memtransfer_streams.stats.legend.csv', local_path_dest, cmdl_args)

    if is_mpi_omp:
        if os.path.exists(trace_name + '.omp_useful_regions.stats.csv'):
            move_files(trace_name + '.omp_useful_regions.stats.csv', local_path_dest, cmdl_args)
        if os.path.exists(trace_name + '.mpi_time.stats.csv'):
            move_files(trace_name + '.mpi_time.stats.csv', local_path_dest, cmdl_args)
        if os.path.exists(trace_name + '.omp_sched_fork_join.stats.csv'):
            move_files(trace_name + '.omp_sched_fork_join.stats.csv', local_path_dest, cmdl_args)
        if os.path.exists(trace_name + '.useful_duration.stats.csv'):
            move_files(trace_name + '.useful_duration.stats.csv', local_path_dest, cmdl_args)
        if os.path.exists(trace_name + '.useful_outside_omp.stats.csv'):
            move_files(trace_name + '.useful_outside_omp.stats.csv', local_path_dest, cmdl_args)


    time_prs = time.time() - time_prs
    time_tot = time.time() - time_tot

    print('Finished successfully in {0:.1f} seconds.'.format(time_tot+time_gpu_agg))
    print('')

    return {
        "trace": trace,
        "trace_mode": trace_mode_value,
        "trace_process_count": trace_process_count,
        "trace_task_per_node": trace_task_per_node_value,
        "trace_tasks": trace_tasks_value,
        "trace_threads": trace_threads_value,
        "raw_data": trace_raw_data,
        "mpi_proc_count": mpi_proc_count,
    }



# Function use in Multiprocessing Pool (Parallel traces processing)
def _process_one_trace_wrapper(args):
    return process_one_trace(*args)

# Helper to distributed analysis
def merge_trace_results(results, trace_list):
    raw_data = create_raw_data(trace_list)
    list_mpi_procs_count = {}

    for result in results:
        trace = result["trace"]
        trace_raw_data = result["raw_data"]

        for key in raw_data_doc:
            raw_data[key][trace] = trace_raw_data[key]

        if result["mpi_proc_count"] is not None:
            list_mpi_procs_count[trace] = result["mpi_proc_count"]

    return raw_data, list_mpi_procs_count



def run_trace_analyses_locally(trace_list, trace_processes, trace_task_per_node,
                               trace_mode, trace_tasks, trace_threads, cmdl_args):
    dimemas_available = which('Dimemas') is not None
    cfgs = init_cfgs()
    path_dest = create_temp_folder('scratch_out_basicanalysis', cmdl_args)

    results = []

    jobs, jobs_info = resolve_job_count(trace_list, cmdl_args)

    print(
        f"Using {jobs} worker(s) "
        f"(traces={jobs_info['trace_cap']}, "
        f"cores={jobs_info['core_cap']}, "
        f"memory_cap={jobs_info['memory_cap']})"
    )

    if jobs == 1:
        for trace in trace_list:
            result = process_one_trace(
                trace=trace,
                trace_process_count=trace_processes[trace],
                trace_task_per_node_value=trace_task_per_node[trace],
                trace_mode_value=trace_mode[trace],
                trace_tasks_value=trace_tasks[trace],
                trace_threads_value=trace_threads[trace],
                cmdl_args=cmdl_args,
                cfgs=cfgs,
                dimemas_available=dimemas_available,
                path_dest=path_dest
            )
            results.append(result)
    else:
        from multiprocessing import Pool

        print(f"Running with {jobs} parallel workers")

        args_list = []
        for trace in trace_list:
            args_list.append((
                trace,
                trace_processes[trace],
                trace_task_per_node[trace],
                trace_mode[trace],
                trace_tasks[trace],
                trace_threads[trace],
                cmdl_args,
                cfgs,
                dimemas_available,
                path_dest
            ))

        with Pool(processes=jobs) as pool:
            results = pool.map(_process_one_trace_wrapper, args_list)

    return results

def run_trace_analyses_to_files(trace_list, trace_processes, trace_task_per_node,
                                trace_mode, trace_tasks, trace_threads, cmdl_args,
                                output_dir):
    results = run_trace_analyses_locally(
        trace_list,
        trace_processes,
        trace_task_per_node,
        trace_mode,
        trace_tasks,
        trace_threads,
        cmdl_args,
    )

    os.makedirs(output_dir, exist_ok=True)

    paths = []
    for result in results:
        path = get_trace_result_path(output_dir, result["trace"])
        save_trace_result(result, path)
        paths.append(path)

    return paths


def merge_trace_result_files(result_paths, trace_list):
    results = [load_trace_result(path) for path in result_paths]
    return merge_trace_results(results, trace_list)


def reconstruct_trace_metadata(results, order_traces='yes'):
    """Rebuild trace metadata dictionaries from serialized per-trace results."""
    if order_traces == 'yes':
        results = sorted(results, key=lambda r: r["trace_process_count"])

    trace_list = []
    trace_processes = {}
    trace_tasks = {}
    trace_threads = {}
    trace_task_per_node = {}
    trace_mode = {}

    for result in results:
        trace = result["trace"]
        trace_list.append(trace)
        trace_processes[trace] = result["trace_process_count"]
        trace_tasks[trace] = result["trace_tasks"]
        trace_threads[trace] = result["trace_threads"]
        trace_task_per_node[trace] = result["trace_task_per_node"]
        trace_mode[trace] = result["trace_mode"]

    return (
        trace_list,
        trace_processes,
        trace_tasks,
        trace_threads,
        trace_task_per_node,
        trace_mode,
    )

###############################

def gather_raw_data(trace_list, trace_processes, trace_task_per_node,
                    trace_mode, trace_tasks, trace_threads, cmdl_args):
    results = run_trace_analyses_locally(
        trace_list,
        trace_processes,
        trace_task_per_node,
        trace_mode,
        trace_tasks,
        trace_threads,
        cmdl_args,
    )
    return merge_trace_results(results, trace_list)

def create_ideal_trace(trace, processes, task_per_node, trace_mode,trace_tasks, trace_threads, cmdl_args, suffix=''):
    """Runs prv2dim and dimemas with ideal configuration for given trace."""
    if trace[-4:] == ".prv":
        base = trace[:-4] + '_' + str(processes) + 'P' + suffix
        trace_dim = trace[:-4] + '_' + str(processes) + 'P' + '.dim'
        trace_sim = base + '.sim.prv'       
        trace_name = trace[:-4]
        cmd = ['prv2dim', trace, trace_dim]
    elif trace[-7:] == ".prv.gz":
        with gzip.open(trace, 'rb') as f_in:
            with open(trace[:-7] + '.prv', 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
        base = trace[:-7] + '_' + str(processes) + 'P' + suffix
        trace_dim = trace[:-7] + '_' + str(processes) + 'P' + '.dim'
        trace_sim = base + '.sim.prv'
        trace_name = trace[:-7]
        trace_unzip = trace[:-3]
        cmd = ['prv2dim', trace_unzip, trace_dim]

    run_command(cmd, cmdl_args)

    if os.path.isfile(trace_dim):
        if cmdl_args.debug:
            print('==DEBUG== Created file ' + trace_dim)
    else:
        print('==Error== ' + trace_dim + 'could not be created.')
        return

    # Create Dimemas configuration
    cfg_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'cfgs')

    content = []
    if (trace_mode != 'Detailed+MPI+CUDA'):
        with open(os.path.join(cfg_dir, 'dimemas_ideal.cfg')) as f:
            content = f.readlines()
    else:
        with open(os.path.join(cfg_dir, 'dimemas_ideal_gpu.cfg')) as f:
            content = f.readlines()

    #print("Procs: ", processes, "Task Per Node: ", task_per_node, "Trace Tasks: " ,trace_tasks, "Trace Threads: ", trace_threads, "\n")

    if trace_mode != 'Detailed+MPI+CUDA':
        content = [line.replace('REPLACE_BY_CPUS_PER_NODE', str(trace_threads)) for line in content]
        content = [line.replace('REPLACE_BY_NTASKS', str(trace_tasks)) for line in content]
    content = [line.replace('REPLACE_BY_COLLECTIVES_PATH', os.path.join(cfg_dir, 'dimemas.collectives')) for line in
               content]
    # MPI+CUDA needs a different Dimemas configuration file
    if trace_mode == 'Detailed+MPI+CUDA':
        task_mpi, threads_2nd = get_tasks_threads(trace)
        #print("Task MPI: ", task_mpi, "Threads: ",threads_2nd, "\n")

        content = [line.replace('REPLACE_BY_CPUS_PER_NODE', str(task_mpi)) for line in content]
        content = [line.replace('REPLACE_BY_NTASKS', str(task_mpi)) for line in content]
        line_accelerator = ''
        # Create a line per each CUDA Thread
        for i in range(int(task_mpi)):
            line_accelerator += '"accelerator node information" {' + str(i) + ', ' + str(threads_2nd) \
                                + ', 0.0, 0.0, 0.0, 0, 1.0};;\n'
        content = [line.replace('REPLACE_ACCELERATORS', line_accelerator) for line in content]

    with open(trace_name + '_' + str(processes) + 'P' + '.dimemas_ideal.cfg', 'w') as f:
        f.writelines(content)

    if trace_mode == 'Detailed+MPI+CUDA':
        if cmdl_args.simulation_cuda:
            cmd = ['Dimemas', '-S', '32k', '--dim', trace_dim, '-p', trace_sim, trace_name + '_' + str(processes) \
               + 'P' + '.dimemas_ideal.cfg']
        else:
            cmd = ['Dimemas', '-S', '32k', '--disable-cuda', '--dim', trace_dim, '-p', trace_sim, trace_name + '_' + str(processes) \
               + 'P' + '.dimemas_ideal.cfg']
    elif trace_mode == 'Detailed+MPI+OpenMP':
        if cmdl_args.simulation_openmp and cmdl_args.ideal_omp :
            cmd = ['Dimemas', '-S', '32k', '--ideal-openmp', '--dim', trace_dim, '-p', trace_sim, trace_name + '_' + str(processes) \
               + 'P' + '.dimemas_ideal.cfg']
        elif cmdl_args.simulation_openmp:
            cmd = ['Dimemas', '-S', '32k', '--dim', trace_dim, '-p', trace_sim, trace_name + '_' + str(processes) \
               + 'P' + '.dimemas_ideal.cfg']
        else:
            cmd = ['Dimemas', '-S', '32k', '--disable-openmp', '--dim', trace_dim, '-p', trace_sim, trace_name + '_' + str(processes) \
               + 'P' + '.dimemas_ideal.cfg']
    else:
        cmd = ['Dimemas', '-S', '32k', '--dim', trace_dim, '-p', trace_sim, trace_name + '_' + str(processes) \
           + 'P' + '.dimemas_ideal.cfg']

    #run_command(cmd, cmdl_args)
    result_exit_code_command = run_command(cmd, cmdl_args)

    if result_exit_code_command == 1001:
        if trace_mode == 'Detailed+MPI+CUDA':
            if cmdl_args.simulation_cuda:
                cmd = ['Dimemas', '-S', '256k', '--dim', trace_dim, '-p', trace_sim, trace_name + '_' + str(processes) \
                + 'P' + '.dimemas_ideal.cfg']
            else:
                cmd = ['Dimemas', '-S', '256k', '--disable-cuda', '--dim', trace_dim, '-p', trace_sim, trace_name + '_' + str(processes) \
                + 'P' + '.dimemas_ideal.cfg']
        elif trace_mode == 'Detailed+MPI+OpenMP':
            if cmdl_args.simulation_openmp and cmdl_args.ideal_omp :
                cmd = ['Dimemas', '-S', '256k', '--ideal-openmp', '--dim', trace_dim, '-p', trace_sim, trace_name + '_' + str(processes) \
               + 'P' + '.dimemas_ideal.cfg']
            elif cmdl_args.simulation_openmp:
                cmd = ['Dimemas', '-S', '256k', '--dim', trace_dim, '-p', trace_sim, trace_name + '_' + str(processes) \
                + 'P' + '.dimemas_ideal.cfg']
            else:
                cmd = ['Dimemas', '-S', '256k', '--disable-openmp', '--dim', trace_dim, '-p', trace_sim, trace_name + '_' + str(processes) \
                + 'P' + '.dimemas_ideal.cfg']
        else:
            cmd = ['Dimemas', '-S', '256k', '--dim', trace_dim, '-p', trace_sim, trace_name + '_' + str(processes) \
            + 'P' + '.dimemas_ideal.cfg']

        result_exit_code_command = run_command(cmd, cmdl_args)


    if os.path.isfile(trace_sim) and (result_exit_code_command == 0):
        if cmdl_args.debug:
            print('==DEBUG== Created file ' + trace_sim)
        return trace_sim
    else:
        if (result_exit_code_command == 1001):
            print('==ERROR== ' + trace_sim + ' is incomplete.')
            remove_files(trace_sim, cmdl_args)
            remove_files(trace_sim[:-4] + '.pcf', cmdl_args)
            remove_files(trace_sim[:-4] + '.row', cmdl_args)          
        else:
            print('==ERROR== ' + trace_sim + ' could not be created.')
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