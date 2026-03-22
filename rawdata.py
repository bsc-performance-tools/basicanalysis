#!/usr/bin/env python3

"""Functions to extract rawdata from each trace."""

from __future__ import print_function, division
import os
import time
import math
import gzip
import shutil
import re
from utils import which
from collections import OrderedDict, defaultdict
from tracemetadata import human_readable, get_tasks_threads, get_traces_from_args, get_device_count, get_device_stream_id_mapping
from utils import run_command, move_files,remove_files, create_temp_folder
from typing import Dict, Tuple, List


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

def format_mapping_for_cfg(
    device_tuple: Tuple[int, List[str]],
    decimals: int = 12,
    trim_trailing_zeros: bool = False
) -> str:
    """
    device_tuple: (count, ["002","003",...])
    returns: "40 2.000000000000 3.000000000000 ..." (or trimmed)
    """
    count, ids = device_tuple

    parts: List[str] = [str(count)]

    if trim_trailing_zeros:
        # Use general format to drop trailing zeros, but keep integer look (e.g., "2", "3")
        parts.extend(f"{int(x):g}" for x in ids)
    else:
        # Fixed decimals like "2.000000000000"
        fmt = f"{{:.{decimals}f}}"
        parts.extend(fmt.format(int(x)) for x in ids)

    return " ".join(parts)

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
    cfgs['useful_device'] = os.path.join(cfgs['root_dir'], 'kernels-x-Tasks-in-Device_app.cfg')
    cfgs['useful_memtransf_device'] = os.path.join(cfgs['root_dir'], 'kernelsPlusMemTransfer-x-Tasks-in-Device_app.cfg')
    return cfgs

def write_cfg_for_device(
    template_path: str,
    out_path: str,
    device_tuple: Tuple[int, List[str]],
    decimals: int = 12,
    trim_trailing_zeros: bool = False,
    placeholder: str = "REPLACE_BY_GPU_MAPPING"
):
    """
    Replace the placeholder in the template with the formatted mapping and write to out_path.
    """
    with open(template_path, "r", encoding="utf-8") as f:
        text = f.read()

    replacement = format_mapping_for_cfg(device_tuple, decimals, trim_trailing_zeros)

    # Replace just inside the specific line; safe even if there are spaces
    pattern = re.compile(rf"({re.escape(placeholder)})")
    new_text = pattern.sub(replacement, text, count=1)

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(new_text)

def write_all_device_cfgs_useful(
    cfgs: dict,
    mapping: Dict[str, Tuple[int, List[str]]],
    template_key: str = "useful_device",
    output_basename: str = "kernels-x-Tasks-in-Device_app"
):
    """
    Convenience wrapper:
    - cfgs[template_key] should point to your template cfg file (with REPLACE_BY_GPU_MAPPING).
    - Creates one cfg file per device: ...-D1.cfg, ...-D2.cfg, ...
    - Stores the file paths in cfgs as 'useful_device_D1', 'useful_device_D2', ...
    """
    template_path = cfgs[template_key]
    #root = cfgs["root_dir"]
    root = "scratch_out_basicanalysis"
    for dev, dev_tuple in mapping.items():
        safe_id = dev.replace(":", "_").replace("/", "_")
        out_path = os.path.join(root, f"{output_basename}-{safe_id}.cfg")
        # choose decimals vs trimming here:
        write_cfg_for_device(
            template_path,
            out_path,
            dev_tuple,
            decimals=12,                # exact 12-decimal output
            trim_trailing_zeros=False   # set True if you want "2 3 8 9 ..." instead
        )
        cfgs[f"useful_device_{safe_id}"] = out_path

def write_all_device_cfgs_useful_plus_memtransfer(
    cfgs: dict,
    mapping: Dict[str, Tuple[int, List[str]]],
    template_key: str = "useful_memtransf_device",
    output_basename: str = "kernelsPlusMemTransfer-x-Tasks-in-Device_app"
):
    """
    Convenience wrapper:
    - cfgs[template_key] should point to your template cfg file (with REPLACE_BY_GPU_MAPPING).
    - Creates one cfg file per device: ...-D1.cfg, ...-D2.cfg, ...
    - Stores the file paths in cfgs as 'useful_device_D1', 'useful_device_D2', ...
    """
    template_path = cfgs[template_key]
    #root = cfgs["root_dir"]
    root = "scratch_out_basicanalysis"

    for dev, dev_tuple in mapping.items():
        safe_id = dev.replace(":", "_").replace("/", "_")
        out_path = os.path.join(root, f"{output_basename}-{safe_id}.cfg")
        # choose decimals vs trimming here:
        write_cfg_for_device(
            template_path,
            out_path,
            dev_tuple,
            decimals=12,                # exact 12-decimal output
            trim_trailing_zeros=False   # set True if you want "2 3 8 9 ..." instead
        )
        cfgs[f"useful_memtransf_device_{safe_id}"] = out_path


###############################

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

    # ------------------------------------------------------------
    # 1) Run paramedir on original trace
    # ------------------------------------------------------------
    time_pmd = time.time()

    cmd_normal = ['paramedir', trace]
    cmd_normal.extend([cfgs['timings'], trace_name + '.timings.stats'])
    cmd_normal.extend([cfgs['runtime'], trace_name + '.runtime.stats'])
    cmd_normal.extend([cfgs['cycles'], trace_name + '.cycles.stats'])
    cmd_normal.extend([cfgs['instructions'], trace_name + '.instructions.stats'])
    cmd_normal.extend([cfgs['flushing'], trace_name + '.flushing.stats'])
    cmd_normal.extend([cfgs['io_call'], trace_name + '.posixio_call.stats'])
    cmd_normal.extend([cfgs['io_cycles'], trace_name + '.posixio-cycles.stats'])
    cmd_normal.extend([cfgs['io_inst'], trace_name + '.posixio-inst.stats'])
    cmd_normal.extend([cfgs['flushing_cycles'], trace_name + '.flushing-cycles.stats'])
    cmd_normal.extend([cfgs['flushing_inst'], trace_name + '.flushing-inst.stats'])

    if is_detailed_mpi:
        cmd_normal.extend([cfgs['mpi_io'], trace_name + '.mpi_io.stats'])
        cmd_normal.extend([cfgs['outside_mpi'], trace_name + '.outside_mpi.stats'])
        cmd_normal.extend([cfgs['mpiio_cycles'], trace_name + '.mpiio-cycles.stats'])
        cmd_normal.extend([cfgs['mpiio_inst'], trace_name + '.mpiio-inst.stats'])

    if is_burst_mpi:
        cmd_normal.extend([cfgs['burst_useful'], trace_name + '.burst_useful.stats'])

    if is_talp_cuda:
        cmd_normal.extend([cfgs['useful_host'], trace_name + '.useful_host.stats'])

        mapping_devices = get_device_stream_id_mapping(trace)
        gpu_devices = len(mapping_devices)
        trace_raw_data['count_devices'] = gpu_devices
        print("==> Count of devices: ", gpu_devices)

        write_all_device_cfgs_useful(cfgs, mapping_devices)
        for device_id in mapping_devices:
            safe_id = device_id.replace(":", "_").replace("/", "_")
            key_device_to_replace = "useful_device_" + str(safe_id)
            cmd_normal.extend([cfgs[key_device_to_replace], trace_name + "." + str(key_device_to_replace) + '.stats'])

        write_all_device_cfgs_useful_plus_memtransfer(cfgs, mapping_devices)
        for device_id in mapping_devices:
            safe_id = device_id.replace(":", "_").replace("/", "_")
            key_device_to_replace = "useful_memtransf_device_" + str(safe_id)
            cmd_normal.extend([cfgs[key_device_to_replace], trace_name + "." + str(key_device_to_replace) + '.stats'])

    run_command(cmd_normal, cmdl_args)

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
            run_command(cmd_ideal, cmdl_args)

    time_pmd = time.time() - time_pmd

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
        print('Successfully analyzed trace with paramedir in {0:.1f} seconds.'.format(time_pmd))

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
    if is_talp_cuda and mapping_devices is not None:
        trace_raw_data['useful_device'] = 0.0
        trace_raw_data['useful_device_max'] = 0.0
        trace_raw_data['useful_memtransf_device'] = 0.0
        trace_raw_data['useful_memtransf_device_max'] = 0.0

        for device_id in mapping_devices:
            safe_id = device_id.replace(":", "_").replace("/", "_")

            key_device_to_replace = "useful_device_" + str(safe_id)
            device_stats_path = trace_name + "." + str(key_device_to_replace) + '.stats'
            if os.path.exists(device_stats_path):
                useful_dev_tot, _, useful_dev_max = parse_total_average_max(device_stats_path)
                trace_raw_data['useful_device'] += float(useful_dev_tot)
                if float(useful_dev_max) > trace_raw_data['useful_device_max']:
                    trace_raw_data['useful_device_max'] = float(useful_dev_max)

            key_device_to_replace = "useful_memtransf_device_" + str(safe_id)
            device_mem_stats_path = trace_name + "." + str(key_device_to_replace) + '.stats'
            if os.path.exists(device_mem_stats_path):
                useful_memtransf_dev_tot, _, useful_memtransf_dev_max = parse_total_average_max(device_mem_stats_path)
                trace_raw_data['useful_memtransf_device'] += float(useful_memtransf_dev_tot)
                if float(useful_memtransf_dev_max) > trace_raw_data['useful_memtransf_device_max']:
                    trace_raw_data['useful_memtransf_device_max'] = float(useful_memtransf_dev_max)

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

    if is_talp_cuda and mapping_devices is not None:
        move_files(trace_name + '.useful_host.stats', local_path_dest, cmdl_args)
        for device_id in mapping_devices:
            safe_id = device_id.replace(":", "_").replace("/", "_")
            key_device_to_replace = "useful_device_" + str(safe_id)
            move_files(trace_name + "." + str(key_device_to_replace) + '.stats', local_path_dest, cmdl_args)

            key_device_to_replace = "useful_memtransf_device_" + str(safe_id)
            move_files(trace_name + "." + str(key_device_to_replace) + '.stats', local_path_dest, cmdl_args)

    time_prs = time.time() - time_prs
    time_tot = time.time() - time_tot

    print('Finished successfully in {0:.1f} seconds.'.format(time_tot))
    print('')

    return {
        "trace": trace,
        "raw_data": trace_raw_data,
        "mpi_proc_count": mpi_proc_count,
    }



def _process_one_trace_wrapper(args):
    return process_one_trace(*args)


def get_available_memory_bytes():
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("MemAvailable:"):
                    return int(line.split()[1]) * 1024
    except OSError:
        return None
    return None


def estimate_mem_per_worker(trace_path):
    size = os.path.getsize(trace_path)

    if trace_path.endswith(".prv.gz"):
        return max(2 * 1024**3, 4 * size)
    return max(1 * 1024**3, 2 * size)


def gather_raw_data(trace_list, trace_processes, trace_task_per_node, trace_mode, trace_tasks, trace_threads, cmdl_args):
    """Gathers all raw data needed to generate the model factors."""
    raw_data = create_raw_data(trace_list)
    global list_mpi_procs_count
    list_mpi_procs_count = dict()

    dimemas_available = which('Dimemas') is not None
    cfgs = init_cfgs()

    path_dest = create_temp_folder('scratch_out_basicanalysis', cmdl_args)

    results = []
    #jobs = max(1, cmdl_args.jobs)

    requested_jobs = max(1, cmdl_args.jobs)
    core_count = os.cpu_count() or 1

    available_mem = get_available_memory_bytes()
    if available_mem is not None:
        usable_mem = int(0.8 * available_mem)
        estimated_per_worker = max(estimate_mem_per_worker(t) for t in trace_list)
        memory_based_cap = max(1, usable_mem // estimated_per_worker)
    else:
        memory_based_cap = core_count

    jobs = min(requested_jobs, len(trace_list), core_count, memory_based_cap)

    if jobs < requested_jobs:
        print(
            f"Requested {requested_jobs} workers, using {jobs} "
            f"(trace/core/memory limits applied)"
        )

    if jobs == 1:
        # --- SERIAL (debug-safe)
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

    # --- MERGE RESULTS (common for both modes)
    for result in results:
        trace = result["trace"]
        trace_raw_data = result["raw_data"]

        for key in raw_data_doc:
            raw_data[key][trace] = trace_raw_data[key]

        if result["mpi_proc_count"] is not None:
            list_mpi_procs_count[trace] = result["mpi_proc_count"]
    

    return raw_data, list_mpi_procs_count


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