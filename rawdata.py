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
                            ('mpiio_ins', 'MPI I/O instructions (total)'),
                            ('burst_useful_tot', 'Burst Useful (total)'),
                            ('burst_useful_max', 'Burst Useful (max)'),
                            ('burst_useful_avg', 'Burst Useful (avg)'),
                            ('useful_not_0_avg', 'Useful duration not 0 inst (average)'),
                            ('useful_not_0_max', 'Useful duration not 0 inst (maximum)'),
                            ('useful_not_0_tot', 'Useful duration not 0 inst (total)'),
                            ('procs_ins', 'Procs with instructions (total)'),
                            ('useful_host', 'Useful Total duration on the Host'),
                            ('useful_device', 'Useful duration on the device'),
                            ('useful_device_max', 'Useful duration on the device (maximum)'),
                            ('useful_memtransf_device', 'Useful+MemoryTransfer on the device'),
                            ('useful_memtransf_device_max', 'Useful+MemoryTransfer on the device (maximum)'),
                            ('count_devices', 'Count of Devices')
                            ])


SUMMARY_KEYS = {"Total", "Average", "Maximum", "Minimum", "StDev", "Num.", "Avg/Max", "Num. Cells"}

# ----------------------------------------------------------------------
# Helper functions to adding serialization for distributed analysis.
# ----------------------------------------------------------------------

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

    list_outside_mpi = []
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
            # - values equal to runtime_value count extra threads of the current MPI task
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
        CUDA-D1.S1-node
        CUDA-D1.S2-node

    becomes:
        {
            "THREAD 1.1.1": "THREAD 1.1.1",
            "THREAD 1.1.2": "CUDA-D1.S1-node",
            "THREAD 1.1.3": "CUDA-D1.S2-node",
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


def device_key_from_row_label(label):
    """
    Convert:
        CUDA-D1.S1-as02r2b20
    into:
        as02r2b20:D1

    Returns None for non-CUDA labels such as 'THREAD 1.1.1'.
    """
    if not label.startswith("CUDA-"):
        return None

    parts = label.split('-')
    if len(parts) < 3:
        return None

    ds_part = parts[1]                  # D1.S1
    node_part = '-'.join(parts[2:])     # as02r2b20
    device_part = ds_part.split('.')[0] # D1

    return f"{node_part}:{device_part}"


def build_thread_to_device_map_from_row(row_path):
    """
    Build mapping:
        "THREAD 1.1.2" -> "as02r2b20:D1"
    using the .row file.
    """
    thread_to_label = parse_row_thread_labels(row_path)

    thread_to_device = {}
    for thread_obj, label in thread_to_label.items():
        device_key = device_key_from_row_label(label)
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
    memtransfer_rows = parse_gpu_stream_stats(memtransfer_stats_path, active_values=(3.0, 7.0))

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

    return cfgs

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
    local_path_dest = os.path.join(path_dest, f"trace_{os.getpid()}")
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
    is_talp_cuda = (trace_mode_value == 'Detailed+MPI+CUDA' and cmdl_args.pop_model_to_apply == 'talp')

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

    cmd_base.extend([cfgs['timings'], trace_name + '.timings.stats'])
    cmd_base.extend([cfgs['runtime'], trace_name + '.runtime.stats'])
    cmd_base.extend([cfgs['cycles'], trace_name + '.cycles.stats'])
    cmd_base.extend([cfgs['instructions'], trace_name + '.instructions.stats'])
    cmd_base.extend([cfgs['flushing'], trace_name + '.flushing.stats'])
    cmd_base.extend([cfgs['io_call'], trace_name + '.posixio_call.stats'])
    cmd_base.extend([cfgs['io_cycles'], trace_name + '.posixio-cycles.stats'])
    cmd_base.extend([cfgs['io_inst'], trace_name + '.posixio-inst.stats'])
    cmd_base.extend([cfgs['flushing_cycles'], trace_name + '.flushing-cycles.stats'])
    cmd_base.extend([cfgs['flushing_inst'], trace_name + '.flushing-inst.stats'])

    if is_detailed_mpi:
        cmd_base.extend([cfgs['mpi_io'], trace_name + '.mpi_io.stats'])
        cmd_base.extend([cfgs['outside_mpi'], trace_name + '.outside_mpi.stats'])
        cmd_base.extend([cfgs['mpiio_cycles'], trace_name + '.mpiio-cycles.stats'])
        cmd_base.extend([cfgs['mpiio_inst'], trace_name + '.mpiio-inst.stats'])

    if is_burst_mpi:
        cmd_base.extend([cfgs['burst_useful'], trace_name + '.burst_useful.stats'])

    if is_talp_cuda:
        cmd_base.extend([cfgs['useful_host'], trace_name + '.useful_host.stats'])

        mapping_devices = get_device_stream_id_mapping(trace)
        gpu_devices = len(mapping_devices)
        trace_raw_data['count_devices'] = gpu_devices
        print("==> Count of devices: ", gpu_devices)

        gpu_useful_stats = trace_name + '.useful_streams.stats.csv'
        gpu_memtransfer_stats = trace_name + '.memtransfer_streams.stats.csv'

        cmd_base.extend([cfgs['useful_streams'], gpu_useful_stats])
        cmd_base.extend([cfgs['memtransfer_streams'], gpu_memtransfer_stats])

    time_base = time.time()
    run_command(cmd_base, cmdl_args)
    time_base = time.time() - time_base

    # ------------------------------------------------------------
    # 2) Optional Dimemas simulation
    # ------------------------------------------------------------
    if dimemas_available and not cmdl_args.skip_simulation:
        if is_detailed_mpi_family and os.path.exists(trace_name + '.outside_mpi.stats'):
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

    if dimemas_available and os.path.exists(trace_name + '.outside_mpi.stats') and not cmdl_args.skip_simulation:
        if is_detailed_mpi_family and trace_sim != '':
            cmd_ideal = ['paramedir', trace_sim]
            cmd_ideal.extend([cfgs['timings'], trace_name_sim + '.timings.stats'])
            cmd_ideal.extend([cfgs['runtime'], trace_name_sim + '.runtime.stats'])
            cmd_ideal.extend([cfgs['outside_mpi'], trace_name_sim + '.outside_mpi.stats'])

            time_pmd_sim = time.time()
            run_command(cmd_ideal, cmdl_args)
            time_pmd_sim = time.time() - time_pmd_sim
            #print(f'Simulated trace analyzed with paramedir in: {time_pmd_sim:.1f} s')
                    
 
    # ------------------------------------------------------------
    # 3) Validate generated files
    # ------------------------------------------------------------
    error_timing = 0
    error_counters = 0
    error_ideal = 0

    if not os.path.exists(trace_name + '.timings.stats') or \
            not os.path.exists(trace_name + '.runtime.stats'):
        print('==ERROR== Failed to compute timing information with paramedir.')
        error_timing = 1

    if not os.path.exists(trace_name + '.outside_mpi.stats') and trace_mode_value[:5] != 'Burst' \
            and 'MPI' in trace_mode_value:
        print('==ERROR== Failed to compute outside MPI timing information with paramedir.')
        error_timing = 1

    if not os.path.exists(trace_name + '.cycles.stats') or \
            not os.path.exists(trace_name + '.instructions.stats'):
        print('==ERROR== Failed to compute counter information with paramedir.')
        error_counters = 1

    if dimemas_available and not cmdl_args.skip_simulation:
        if is_detailed_mpi_family and os.path.exists(trace_name + '.outside_mpi.stats'):
            if trace_sim == '' or \
                    not os.path.exists(trace_name_sim + '.timings.stats') or \
                    not os.path.exists(trace_name_sim + '.runtime.stats') or \
                    not os.path.exists(trace_name_sim + '.outside_mpi.stats'):
                print('==ERROR== Failed to compute simulated timing information with paramedir.')
                error_ideal = 1
                trace_sim = ''
    else:
        error_ideal = 0

    if error_timing or error_counters or error_ideal:
        print('Failed to analyze trace with paramedir')
    else:
        print('Successfully analyzed trace with paramedir in {0:.1f} seconds.'.format(time_base + time_pmd_sim))

    # ------------------------------------------------------------
    # 4) Parse output files
    # ------------------------------------------------------------
    time_prs = time.time()

    # useful_cyc
    if os.path.exists(trace_name + '.cycles.stats'):
        trace_raw_data['useful_cyc'] = parse_positive_value_sum(trace_name + '.cycles.stats', skip_header=True)
    else:
        trace_raw_data['useful_cyc'] = 'NaN'

    # useful_ins + procs_ins + instructions mask
    procs_ins = 0
    content_insttructions = []
    if os.path.exists(trace_name + '.instructions.stats'):
        useful_ins, procs_ins, content_insttructions = parse_positive_value_sum_and_mask(
            trace_name + '.instructions.stats',
            skip_header=True
        )
        trace_raw_data['procs_ins'] = procs_ins
        trace_raw_data['useful_ins'] = float(useful_ins)
    else:
        trace_raw_data['useful_ins'] = 'NaN'

    # POSIX-IO aggregates
    posixio_totals = None
    if os.path.exists(trace_name + '.posixio_call.stats'):
        posixio_totals = parse_tab_total_row_values(trace_name + '.posixio_call.stats')
        posix_stats = parse_tab_stats(trace_name + '.posixio_call.stats')
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
    if os.path.exists(trace_name + '.timings.stats'):
        timings_data = parse_timings_stats(
            trace_name + '.timings.stats',
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
    if os.path.exists(trace_name + '.runtime.stats'):
        _, runtime_avg, _ = parse_total_average_max(trace_name + '.runtime.stats')
        trace_raw_data['runtime'] = runtime_avg
    else:
        trace_raw_data['runtime'] = 'NaN'

    # outside_mpi
    if os.path.exists(trace_name + '.outside_mpi.stats') and is_detailed_mpi:
        outside_data = parse_outside_mpi_stats(
            trace_name + '.outside_mpi.stats',
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
    if os.path.exists(trace_name + '.flushing.stats'):
        with open(trace_name + '.flushing.stats') as f:
            content = f.readlines()
            flushing_exist = ('\tBegin\t\n' in content) or ('\tvalue 1\t\n' in content)

        if flushing_exist:
            flushing_tot, flushing_avg, flushing_max = parse_total_average_max(trace_name + '.flushing.stats')
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
    trace_raw_data['flushing_cyc'] = parse_total_as_int(trace_name + '.flushing-cycles.stats') \
        if os.path.exists(trace_name + '.flushing-cycles.stats') else 0.0
    trace_raw_data['flushing_ins'] = parse_total_as_int(trace_name + '.flushing-inst.stats') \
        if os.path.exists(trace_name + '.flushing-inst.stats') else 0.0
    trace_raw_data['io_cyc'] = parse_total_as_int(trace_name + '.posixio-cycles.stats') \
        if os.path.exists(trace_name + '.posixio-cycles.stats') else 0.0
    trace_raw_data['io_ins'] = parse_total_as_int(trace_name + '.posixio-inst.stats') \
        if os.path.exists(trace_name + '.posixio-inst.stats') else 0.0
    trace_raw_data['mpiio_cyc'] = parse_total_as_int(trace_name + '.mpiio-cycles.stats') \
        if os.path.exists(trace_name + '.mpiio-cycles.stats') and is_detailed_mpi else 0.0
    trace_raw_data['mpiio_ins'] = parse_total_as_int(trace_name + '.mpiio-inst.stats') \
        if os.path.exists(trace_name + '.mpiio-inst.stats') and is_detailed_mpi else 0.0

    # mpi_io aggregates
    if os.path.exists(trace_name + '.mpi_io.stats') and is_detailed_mpi:
        mpiio_stats = parse_tab_stats(trace_name + '.mpi_io.stats')
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
    if is_talp_cuda and os.path.exists(row_path):
        trace_raw_data['useful_device'] = 0.0
        trace_raw_data['useful_device_max'] = 0.0
        trace_raw_data['useful_memtransf_device'] = 0.0
        trace_raw_data['useful_memtransf_device_max'] = 0.0

        if gpu_useful_stats and gpu_memtransfer_stats and \
           os.path.exists(gpu_useful_stats) and os.path.exists(gpu_memtransfer_stats):
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

        if os.path.exists(trace_name + '.useful_host.stats'):
            useful_host_tot, _, _ = parse_total_average_max(trace_name + '.useful_host.stats')
            trace_raw_data['useful_host'] = float(useful_host_tot)
        else:
            trace_raw_data['useful_host'] = 0.0

    # burst mode
    if trace_mode_value == 'Burst+MPI':
        if os.path.exists(trace_name + '.burst_useful.stats'):
            totals = parse_tab_total_row_values(trace_name + '.burst_useful.stats')
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
    if is_detailed_mpi_family and (dimemas_available and os.path.exists(trace_name + '.outside_mpi.stats') and not cmdl_args.skip_simulation):
        if os.path.exists(trace_name_sim + '.timings.stats'):
            _, _, useful_dim_max = parse_total_average_max(trace_name_sim + '.timings.stats')
            trace_raw_data['useful_dim'] = float(useful_dim_max)
        else:
            trace_raw_data['useful_dim'] = 'NaN'

        if os.path.exists(trace_name_sim + '.runtime.stats'):
            _, runtime_sim_avg, _ = parse_total_average_max(trace_name_sim + '.runtime.stats')
            trace_raw_data['runtime_dim'] = float(runtime_sim_avg)
        else:
            trace_raw_data['runtime_dim'] = 'NaN'

        if os.path.exists(trace_name_sim + '.outside_mpi.stats'):
            # keep current logic for now; refactor later if desired
            with open(trace_name_sim + '.outside_mpi.stats') as f:
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

    # ------------------------------------------------------------
    # 5) Move generated files
    # ------------------------------------------------------------
    if is_detailed_mpi_family and (dimemas_available and os.path.exists(trace_name + '.outside_mpi.stats')) and not cmdl_args.skip_simulation:
        if trace_sim != '':
            move_files(trace_name_sim + '.timings.stats', local_path_dest, cmdl_args)
            move_files(trace_name_sim + '.runtime.stats', local_path_dest, cmdl_args)
            move_files(trace_name_sim + '.outside_mpi.stats', local_path_dest, cmdl_args)
            move_files(trace_sim, local_path_dest, cmdl_args)
            move_files(trace_sim[:-4] + '.pcf', local_path_dest, cmdl_args)
            move_files(trace_sim[:-4] + '.row', local_path_dest, cmdl_args)
            move_files(trace_sim[:-8] + '.dim', local_path_dest, cmdl_args)
            remove_files(trace_sim[:-8] + '.row', cmdl_args)
            remove_files(trace_sim[:-8] + '.pcf', cmdl_args)
            move_files(trace_sim[:-8] + '.dimemas_ideal.cfg', local_path_dest, cmdl_args)

            if trace.endswith(".prv.gz"):
                remove_files(trace_name_control + '.prv', cmdl_args)

    move_files(trace_name + '.timings.stats', local_path_dest, cmdl_args)
    move_files(trace_name + '.runtime.stats', local_path_dest, cmdl_args)
    move_files(trace_name + '.cycles.stats', local_path_dest, cmdl_args)
    move_files(trace_name + '.instructions.stats', local_path_dest, cmdl_args)
    move_files(trace_name + '.flushing.stats', local_path_dest, cmdl_args)
    move_files(trace_name + '.posixio-cycles.stats', local_path_dest, cmdl_args)
    move_files(trace_name + '.posixio-inst.stats', local_path_dest, cmdl_args)
    move_files(trace_name + '.flushing-cycles.stats', local_path_dest, cmdl_args)
    move_files(trace_name + '.flushing-inst.stats', local_path_dest, cmdl_args)

    if is_detailed_mpi:
        move_files(trace_name + '.mpi_io.stats', local_path_dest, cmdl_args)
        move_files(trace_name + '.posixio_call.stats', local_path_dest, cmdl_args)
        move_files(trace_name + '.outside_mpi.stats', local_path_dest, cmdl_args)
        move_files(trace_name + '.mpiio-cycles.stats', local_path_dest, cmdl_args)
        move_files(trace_name + '.mpiio-inst.stats', local_path_dest, cmdl_args)

    if is_burst_mpi:
        move_files(trace_name + '.2dh_BurstEff.stats', local_path_dest, cmdl_args)
        move_files(trace_name + '.burst_useful.stats', local_path_dest, cmdl_args)

    if is_talp_cuda and os.path.exists(row_path):
        move_files(trace_name + '.useful_host.stats', local_path_dest, cmdl_args)
        move_files(trace_name + '.useful_streams.stats.csv', local_path_dest, cmdl_args)
        move_files(trace_name + '.memtransfer_streams.stats.csv', local_path_dest, cmdl_args)

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

def create_ideal_trace(trace, processes, task_per_node, trace_mode,trace_tasks, trace_threads, cmdl_args):
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
        if cmdl_args.simulation_openmp:
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
            if cmdl_args.simulation_openmp:
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