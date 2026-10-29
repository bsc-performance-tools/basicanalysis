#!/usr/bin/env python3

"""Work done by the devices, for the decomposition of the Device
Computation Scalability.

The Device Computation Scalability compares the useful device time U (the
kernel time of all devices) with the reference execution, as the
Computation Scalability compares the useful time on the CPU. It is split
exactly into factors that say where a change of U comes from. The factors
depend on the trace source, and are the same for all traces:

  - Issued instructions (nsys2prv traces with the GPU metrics), with the
    names of the CPU factors:

      Device Computation Scalability = Device IPC Scalability
                                       x Device Instruction Scalability
                                       x Device Frequency Scalability

      Device Instruction Scalability = W_ref * r / W
      Device IPC Scalability         = IPC / IPC_ref
      Device Frequency Scalability   = f / f_ref

    W = integral of SM Issue x GPC clock (the issued instructions, up to a
    constant of the GPU model), added over the devices;
    IPC = integral of SM Issue / U (mean SM Issue during kernels);
    f = integral of SM Issue x clock / integral of SM Issue (mean clock
    while issuing). U = W / (IPC x f).

  - GPU threads launched (all other traces), W = sum over the kernels of
    blocks per grid x threads per block:

      Device Computation Scalability = Device Work Scalability
                                       x Device Throughput Scalability

      Device Work Scalability       = W_ref * r / W
      Device Throughput Scalability = (W / U) / (W_ref / U_ref)

    The work is the number of GPU threads, and the throughput the threads
    completed per second of kernel time.

r is the work ratio of the scaling model (1 in strong scaling).

The kernels are also grouped by name, for the contribution of each kernel
to the change of the device time (see kernel_contributions).
"""

from __future__ import print_function, division

import gzip
import os
import re
import time
from collections import OrderedDict

from tracemetadata import (
    is_gpu_stream_label,
    parse_trace_header,
    _read_header_line,
)


# Kernel execution on a GPU stream (CUDA, HIP). In Extrae traces the blocks
# per grid and the threads per block of the kernel follow the same base
# (63000011, 63000012); nsys2prv writes the grid and block dimensions.
KERNEL_EXECUTION_EVENTS = (63000006, 63500006)
EXTRAE_BLOCKS_OFFSET = 5
EXTRAE_THREADS_OFFSET = 6
NSYS2PRV_GRID_EVENTS = (9101, 9102, 9103)
NSYS2PRV_BLOCK_EVENTS = (9104, 9105, 9106)

# nsys2prv stream label (CUDA-D0.S7), see nsys2prvmetrics.
NSYS2PRV_STREAM_LABEL_RE = re.compile(r"^(?:CUDA|HIP)-D\d+\.S\d+(?:-\S+)?\s*$")

# Libraries such as cuBLAS select a kernel for each problem size; its name
# ends with the tile configuration (nvjet_sm90_tst_192x192_64x4_2x1_v_bz_TNN).
# The family is the name without it.
KERNEL_TILE_SUFFIX_RE = re.compile(r"_\d+x\d+(?:_.*)?$")

_HEADER_TIME_RE = re.compile(r"^#Paraver \([^)]*\):(\d+)(?:_(ns|us))?:")

WORK_MEASURE_INSTRUCTIONS = 'issued_instructions'
WORK_MEASURE_THREADS = 'threads_launched'

WORK_MEASURE_LABELS = {
    WORK_MEASURE_INSTRUCTIONS: 'Issued instructions (SM Issue x GPC clock)',
    WORK_MEASURE_THREADS: 'GPU threads launched (blocks x threads per block)',
}

# Optional raw data: written to rawdata.csv only when a trace has it.
device_work_raw_data_doc = OrderedDict([
    ('device_kernels', 'Kernels executed on the devices'),
    ('device_threads', 'GPU threads launched (blocks x threads per block)'),
])

# Kernel time, count and threads of each kernel family, per trace. Not
# written to rawdata.csv.
DEVICE_KERNELS_KEY = 'device_kernel_families'

# Device Computation Scalability submetrics: IPC, Instruction and Frequency
# with issued instructions, Work and Throughput with GPU threads launched.
mod_device_work_factors_doc = OrderedDict([
    ('dev_ipc_scale', '   == Device IPC scalability'),
    ('dev_inst_scale', '   == Device Instruction scalability'),
    ('dev_freq_scale', '   == Device Frequency scalability'),
    ('dev_work_scale', '   == Device Work scalability'),
    ('dev_throughput_scale', '   == Device Throughput scalability'),
])

# Kernels listed in the contribution table; the rest are added up.
TOP_KERNELS = 10


def kernel_family(name):
    """Kernel name without the tile configuration of library kernels."""
    family = KERNEL_TILE_SUFFIX_RE.sub('', name)
    return family or name


def _time_unit_to_us(prv_file):
    """Factor from trace time to microseconds (traces without unit: us)."""
    try:
        match = _HEADER_TIME_RE.match(_read_header_line(prv_file))
    except (OSError, ValueError):
        return 1.0
    if match and match.group(2) == 'ns':
        return 1.0e-3
    return 1.0


def stream_rows(prv_file, row_path):
    """(task, thread) of the GPU stream threads, from the .row labels.

    The LEVEL THREAD labels are positional: the i-th label is the i-th
    thread of the header, task by task.
    """
    labels = []
    in_threads = False
    with open(row_path, errors='replace') as row_file:
        for raw_line in row_file:
            line = raw_line.strip()
            if line.startswith('LEVEL '):
                in_threads = line.startswith('LEVEL THREAD')
                continue
            if in_threads and line:
                labels.append(line)

    header = parse_trace_header(prv_file)
    rows = set()
    position = 0
    for task_id, n_threads in enumerate(header['threads_per_task'], start=1):
        for thread_id in range(1, n_threads + 1):
            if position < len(labels):
                label = labels[position]
                if (is_gpu_stream_label(label)
                        or NSYS2PRV_STREAM_LABEL_RE.match(label)):
                    rows.add((task_id, thread_id))
            position += 1
    return rows


def _kernel_threads(values, kernel_event):
    """GPU threads launched by a kernel, from the events of its start."""
    blocks = values.get(kernel_event + EXTRAE_BLOCKS_OFFSET)
    if blocks is not None:
        return blocks * values.get(kernel_event + EXTRAE_THREADS_OFFSET, 0)
    if NSYS2PRV_GRID_EVENTS[0] in values:
        threads = 1
        for event in NSYS2PRV_GRID_EVENTS + NSYS2PRV_BLOCK_EVENTS:
            threads *= max(values.get(event, 1), 1)
        return threads
    return None


def scan_device_kernels(prv_file, pcf_path, row_path):
    """Kernels executed on the GPU streams of a trace.

    A kernel is the interval between a non-zero value of the kernel
    execution event on a stream thread and the next zero on the same
    thread. Kernels still running at the end of the trace are ignored.

    Returns {'kernels': n, 'threads': sum of the threads launched (None if a
    kernel has no grid), 'families': {family: [kernels, time (us),
    threads]}}, or None when the trace has no kernels on its streams.
    """
    from rawdata import parse_pcf_event_values

    streams = stream_rows(prv_file, row_path)
    if not streams:
        return None

    to_us = _time_unit_to_us(prv_file)
    names = {}
    for event in KERNEL_EXECUTION_EVENTS:
        for value, label in parse_pcf_event_values(pcf_path, event).items():
            names[(event, value)] = label

    markers = tuple(':{}:'.format(event) for event in KERNEL_EXECUTION_EVENTS)
    running = {}
    families = {}
    total_kernels = 0
    total_threads = 0
    threads_known = True

    opener = gzip.open if prv_file.endswith('.gz') else open
    with opener(prv_file, 'rt', errors='replace') as trace:
        for line in trace:
            if line[0] != '2' or not any(m in line for m in markers):
                continue
            fields = line.rstrip('\n').split(':')
            row = (int(fields[3]), int(fields[4]))
            if row not in streams:
                continue
            values = {}
            for i in range(6, len(fields) - 1, 2):
                values[int(fields[i])] = int(fields[i + 1])
            for kernel_event in KERNEL_EXECUTION_EVENTS:
                if kernel_event in values:
                    break
            kernel = values[kernel_event]
            time = int(fields[5])
            started = running.pop(row, None)
            if started is not None:
                start, key, threads = started
                name = names.get(key, str(key[1]))
                family = families.setdefault(kernel_family(name), [0, 0.0, 0])
                family[0] += 1
                family[1] += (time - start) * to_us
                total_kernels += 1
                if threads is None:
                    threads_known = False
                else:
                    family[2] += threads
                    total_threads += threads
            if kernel != 0:
                running[row] = (time, (kernel_event, kernel),
                                _kernel_threads(values, kernel_event))

    if total_kernels == 0:
        return None

    return {
        'kernels': total_kernels,
        'threads': total_threads if threads_known else None,
        'families': families,
    }


def add_device_kernels(trace_raw_data, trace, trace_name_control):
    """Scan the kernels of a GPU trace and store them in its raw data:
    device_kernels, device_threads and the kernel families."""
    row_path = trace_name_control + '.row'
    if not os.path.exists(row_path):
        return

    start = time.time()
    result = scan_device_kernels(trace, trace_name_control + '.pcf', row_path)
    if result is None:
        print('==WARNING== No kernels found on the GPU streams: the Device '
              'Work and Throughput Scalability and the kernel table are not '
              'available.')
        return

    trace_raw_data['device_kernels'] = result['kernels']
    if result['threads'] is not None:
        trace_raw_data['device_threads'] = result['threads']
    trace_raw_data[DEVICE_KERNELS_KEY] = result['families']
    print('Successfully scanned {} kernels in {:.1f} seconds.'.format(
        result['kernels'], time.time() - start))


def _number(value):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    return value


def device_work_measure(raw_data, trace_list):
    """Work measure used for all traces, or None when one is missing.

    Issued instructions when every trace has the integral of SM Issue x
    clock, GPU threads launched when every trace has them.
    """
    def all_positive(key):
        values = [_number(raw_data.get(key, {}).get(trace))
                  for trace in trace_list]
        return all(value is not None and value > 0 for value in values)

    if all_positive('hwc_sm_issue_clock_int') and all_positive('hwc_sm_issue_int'):
        return WORK_MEASURE_INSTRUCTIONS
    if all_positive('device_threads'):
        return WORK_MEASURE_THREADS
    return None


def device_work(raw_data, trace, measure):
    """Work W of the devices in a trace with the given measure."""
    if measure == WORK_MEASURE_INSTRUCTIONS:
        return _number(raw_data['hwc_sm_issue_clock_int'][trace])
    if measure == WORK_MEASURE_THREADS:
        return _number(raw_data['device_threads'][trace])
    return None


def compute_device_work_factors(raw_data, trace_list, comp_scale,
                                work_ratio):
    """Device Computation Scalability submetrics.

    comp_scale is {trace: Device Computation Scalability (%)}, and
    work_ratio(trace) the work ratio r of the scaling model.

    Returns ({metric key: {trace: value}}, work measure). The values are
    'Non-Avail' without a work measure or with a single trace; IPC,
    Instruction and Frequency Scalability are given with issued
    instructions, Work and Throughput Scalability with GPU threads launched.
    """
    factors = OrderedDict(
        (key, {trace: 'Non-Avail' for trace in trace_list})
        for key in mod_device_work_factors_doc
    )
    measure = device_work_measure(raw_data, trace_list)
    if measure is None or len(trace_list) < 2:
        return factors, measure

    reference = trace_list[0]
    work_ref = device_work(raw_data, reference, measure)
    if measure == WORK_MEASURE_INSTRUCTIONS:
        keys = ('dev_inst_scale', 'dev_ipc_scale', 'dev_freq_scale')
    else:
        keys = ('dev_work_scale', 'dev_throughput_scale')

    def rate(trace):
        """Mean SM Issue during the kernels and mean clock while issuing."""
        issue = _number(raw_data['hwc_sm_issue_int'][trace])
        issue_clock = _number(raw_data['hwc_sm_issue_clock_int'][trace])
        useful = _number(raw_data['useful_device'][trace])
        return issue / useful, issue_clock / issue

    for trace in trace_list:
        if _number(comp_scale.get(trace)) is None:
            continue
        try:
            work = device_work(raw_data, trace, measure)
            work_scale = work_ref * float(work_ratio(trace)) / work * 100.0
            if measure == WORK_MEASURE_INSTRUCTIONS:
                issue_ref, clock_ref = rate(reference)
                issue, clock = rate(trace)
                values = (work_scale, issue / issue_ref * 100.0,
                          clock / clock_ref * 100.0)
            else:
                values = (work_scale,
                          float(comp_scale[trace]) / work_scale * 100.0)
        except (TypeError, ValueError, ZeroDivisionError):
            values = ('NaN',) * len(keys)
        for key, value in zip(keys, values):
            factors[key][trace] = value

    return factors, measure


def kernel_contributions(raw_data, trace_list, work_ratio):
    """Contribution of each kernel family to the change of the device time.

    For each trace n other than the reference, with U_k the time of kernel
    family k and r the work ratio of the scaling model:

      Share_k(n) = (U_k(n) - U_k(ref) r) / (U(n) - U(ref) r)

    where U is the time of all families, so that the shares add up to
    100 %. The reference time is scaled by r, so the table explains the
    gap from the ideal of the scaling model.

    Returns {trace: {'ratio': r, 'gap': U(n) - U(ref) r (us),
    'rows': [row, ...]}} with the rows sorted
    by the absolute change, each row {'kernel', 'change', 'share',
    'count_ref', 'count', 'time_ref', 'time', 'threads_ref', 'threads'}
    (times in us). Empty without kernel data or with a single trace.
    """
    kernels = raw_data.get(DEVICE_KERNELS_KEY, {})
    if len(trace_list) < 2:
        return {}
    reference = trace_list[0]
    families_ref = kernels.get(reference)
    if not families_ref:
        return {}

    contributions = {}
    total_ref = sum(values[1] for values in families_ref.values())
    for trace in trace_list[1:]:
        families = kernels.get(trace)
        if not families:
            continue
        try:
            ratio = float(work_ratio(trace))
        except (TypeError, ValueError, ZeroDivisionError):
            continue
        total = sum(values[1] for values in families.values())
        gap = total - total_ref * ratio

        rows = []
        for name in set(families_ref) | set(families):
            count_ref, time_ref, threads_ref = families_ref.get(name, (0, 0.0, 0))
            count, time, threads = families.get(name, (0, 0.0, 0))
            change = time - time_ref * ratio
            rows.append({
                'kernel': name,
                'change': change,
                'share': change / gap * 100.0 if gap else 'NaN',
                'count_ref': count_ref,
                'count': count,
                'time_ref': time_ref,
                'time': time,
                'threads_ref': threads_ref,
                'threads': threads,
            })
        rows.sort(key=lambda row: -abs(row['change']))
        contributions[trace] = {'ratio': ratio, 'gap': gap, 'rows': rows}

    return contributions


def top_kernel_rows(rows, top=TOP_KERNELS):
    """The first rows and one 'Other kernels' row with the rest added."""
    if len(rows) <= top:
        return list(rows)
    rest = rows[top:]
    other = {
        'kernel': 'Other kernels ({})'.format(len(rest)),
        'change': sum(row['change'] for row in rest),
        'share': 'NaN',
        'count_ref': sum(row['count_ref'] for row in rest),
        'count': sum(row['count'] for row in rest),
        'time_ref': sum(row['time_ref'] for row in rest),
        'time': sum(row['time'] for row in rest),
        'threads_ref': sum(row['threads_ref'] for row in rest),
        'threads': sum(row['threads'] for row in rest),
    }
    shares = [row['share'] for row in rest]
    if all(share != 'NaN' for share in shares):
        other['share'] = sum(shares)
    return list(rows[:top]) + [other]


# Lambda kernels (Kokkos, RAJA, CUDA lambdas) have the same name; their
# signature names the function that defines the lambda: &(clover_pack_message_left(
_LAMBDA_FUNCTION_RE = re.compile(r"&\(([A-Za-z_][\w:]*)\(")


def kernel_display_names(names):
    """Short names for tables: {name: short name}.

    The short name is the name without the signature in brackets (Extrae
    labels are 'void name [signature]') and without 'void '. When several
    kernels have the same short name, the function that defines the lambda
    is added, or a number.
    """
    short = {}
    for name in names:
        base = name.split(' [', 1)[0]
        if base.startswith('void '):
            base = base[len('void '):]
        short[name] = base

    counts = {}
    for base in short.values():
        counts[base] = counts.get(base, 0) + 1

    display = {}
    for name in names:
        base = short[name]
        if counts[base] > 1:
            match = _LAMBDA_FUNCTION_RE.search(name)
            if match:
                base = '{} ({})'.format(base, match.group(1))
        display[name] = base

    groups = {}
    for name in sorted(names):
        groups.setdefault(display[name], []).append(name)
    for base, members in groups.items():
        if len(members) > 1:
            for number, name in enumerate(members, start=1):
                display[name] = '{} #{}'.format(base, number)
    return display


def _ratio_text(numerator, denominator):
    if not denominator:
        return 'new' if numerator else '-'
    return '{:.2f}'.format(numerator / denominator)


def _time_per_thread_ratio(row):
    if not (row['threads'] and row['threads_ref'] and row['time_ref']):
        return '-'
    return '{:.2f}'.format((row['time'] / row['threads'])
                           / (row['time_ref'] / row['threads_ref']))


def print_device_kernel_tables(contributions, trace_list):
    """Kernel contribution tables on the standard output, one per trace."""
    if not contributions:
        return

    reference = os.path.basename(trace_list[0])
    name_width = 60
    print('======== Device kernels: contribution to the change of the device time ========')
    print('Share = (U_k - U_k,ref x r) / (U - U_ref x r), with U the kernel time and r')
    print('the work ratio of the scaling model. Kernels of libraries are grouped by family.')
    for trace in trace_list[1:]:
        result = contributions.get(trace)
        if not result:
            continue
        print('')
        print('{} (reference: {}, r = {:.4g})'.format(
            os.path.basename(trace), reference, result['ratio']))
        print('Change from the ideal of the scaling model: {:+.3f} s ({})'.format(
            result['gap'] / 1.0e6,
            'slower' if result['gap'] > 0 else 'faster'))
        header = ('{:<' + str(name_width) + '} | {:>8} | {:>17} | {:>10} | '
                  '{:>10} | {:>7} | {:>9} | {:>13}').format(
            'Kernel', 'Share', 'Calls ref -> n', 'Time ref s', 'Time s',
            'Time x', 'Threads x', 'Time/thread x')
        print(header)
        print('-' * len(header))
        display = kernel_display_names([row['kernel'] for row in result['rows']])
        for row in top_kernel_rows(result['rows']):
            name = display.get(row['kernel'], row['kernel'])
            if len(name) > name_width:
                name = name[:name_width - 3] + '...'
            share = ('{:.2f}%'.format(row['share'])
                     if row['share'] != 'NaN' else 'NaN')
            calls = '{} -> {}'.format(row['count_ref'], row['count'])
            print(('{:<' + str(name_width) + '} | {:>8} | {:>17} | {:>10.3f} | '
                   '{:>10.3f} | {:>7} | {:>9} | {:>13}').format(
                name, share, calls, row['time_ref'] / 1.0e6,
                row['time'] / 1.0e6, _ratio_text(row['time'], row['time_ref']),
                _ratio_text(row['threads'], row['threads_ref']),
                _time_per_thread_ratio(row)))
    print('')


def print_device_kernels_csv(contributions, trace_list):
    """device_kernels.csv: all kernel families of every trace compared with
    the reference."""
    if not contributions:
        return

    file_path = os.path.join(os.getcwd(), 'device_kernels.csv')
    delimiter = ','
    columns = ['Trace', 'Reference', 'Work ratio', 'Kernel', 'Share (%)',
               'Calls ref', 'Calls', 'Time ref (us)', 'Time (us)',
               'Threads ref', 'Threads']
    with open(file_path, 'w') as output:
        output.write(delimiter.join(columns) + '\n')
        for trace in trace_list[1:]:
            result = contributions.get(trace)
            if not result:
                continue
            for row in result['rows']:
                share = ('{:.6f}'.format(row['share'])
                         if row['share'] != 'NaN' else 'NaN')
                values = [
                    os.path.basename(trace), os.path.basename(trace_list[0]),
                    '{:.6g}'.format(result['ratio']),
                    '"' + row['kernel'].replace('"', '""') + '"',
                    share, str(row['count_ref']), str(row['count']),
                    '{:.3f}'.format(row['time_ref']),
                    '{:.3f}'.format(row['time']),
                    str(row['threads_ref']), str(row['threads']),
                ]
                output.write(delimiter.join(values) + '\n')

    print('======== Output File: Device kernels ========')
    print('Kernel contributions written to ' + file_path)
    print('')
