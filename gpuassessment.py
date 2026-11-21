#!/usr/bin/env python3

"""GPU assessment metrics (doc/design/gpu_assessment_metrics.rst, step 1).

Metrics that the POP assessments of GPU applications compute by hand next
to the Device side of the Host/Device model:

Device work (with two or more traces): the kernel time, the Device
Computation Scalability without the workload or resource ratio, and the
scalability of the amount of work measured by the GPU hardware counters
(Tensor Core activity and DRAM data read and written), scaled as the Device
Computation Scalability. They are indicators next to the model, not
factors of it.

  Kernel time                    G (sum over devices)
  Comp. scalability not scaled   G_ref / G
  <counter> work scalability     I_ref / I x workload ratio

where I is the integral of the counter over the trace (all devices): the
Tensor Active integral is proportional to the Tensor Core work and the
DRAM bandwidth integrals to the bytes read and written. Above 100% the
trace does less of that work per unit of workload than the reference.

Host time split (nsys2prv traces): the time of the host units inside each
group of CUDA calls (kernel launches, synchronization, memory, CUDA graphs,
other), and outside CUDA calls (the framework: Python, the inference
engine, the application), in % of the host time.
"""

from __future__ import print_function, division

import math
import os
import re
from collections import OrderedDict


NS_PER_US = 1000.0

# Groups of CUDA runtime/driver calls, found by the call name (the value
# labels of the CUDA call event in the .pcf, which do not change between
# nsys2prv versions even when the values do). The first matching group is
# used: cudaGraphLaunch is a launch, cudaGraphInstantiate a graph call.
CUDA_CALL_GROUP_PATTERNS = (
    ('launch', re.compile(r'launch', re.IGNORECASE)),
    ('sync', re.compile(r'synchronize|query', re.IGNORECASE)),
    ('memory', re.compile(
        r'memcpy|memset|malloc|free|hostalloc|hostregister|memprefetch|memadvise',
        re.IGNORECASE)),
    ('graph', re.compile(r'graph|begincapture|endcapture', re.IGNORECASE)),
)

CUDA_CALL_GROUPS = ('launch', 'sync', 'memory', 'graph', 'other')

# Raw data of the host time split (only written when a trace has it).
host_calls_raw_data_doc = OrderedDict(
    [('host_calls_units', 'Host units of the CUDA call split')]
    + [('host_calls_' + group,
        'Time of the Host units in {} CUDA calls (total, us)'.format(group))
       for group in CUDA_CALL_GROUPS]
)

mod_host_calls_doc = OrderedDict([
    ('host_time_framework', 'Outside CUDA calls (framework)'),
    ('host_time_launch', 'Kernel launch calls'),
    ('host_time_sync', 'Synchronization calls'),
    ('host_time_memory', 'Memory calls'),
    ('host_time_graph', 'CUDA graph calls'),
    ('host_time_other', 'Other CUDA calls'),
])

mod_device_work_doc = OrderedDict([
    ('dev_kernel_time', 'Kernel time (sec)'),
    ('dev_comp_scale_unscaled', 'Device Computation scalability (not scaled)'),
    ('dev_tensor_work_scale', 'Tensor Core work scalability'),
    ('dev_dram_read_scale', 'DRAM read volume scalability'),
    ('dev_dram_write_scale', 'DRAM write volume scalability'),
])

# Counter integral (raw data key) of each work scalability.
DEVICE_WORK_INTEGRALS = OrderedDict([
    ('dev_tensor_work_scale', 'hwc_tensor_active_int'),
    ('dev_dram_read_scale', 'hwc_dram_read_unweighted_int'),
    ('dev_dram_write_scale', 'hwc_dram_write_unweighted_int'),
])

UNAVAILABLE = ('Non-Avail', 'NaN', 'N/A', None)


def classify_cuda_call(name):
    """Group of a CUDA call name: launch, sync, memory, graph or other."""
    for group, pattern in CUDA_CALL_GROUP_PATTERNS:
        if pattern.search(name):
            return group
    return 'other'


def parse_cuda_calls_by_name(path, labels):
    """Time of each thread inside each CUDA call, from the analyzer of
    cuda_calls_by_name_host.cfg (one column per call, in nanoseconds).

    labels: [(thread_obj, .row label), ...] in thread order. The rows of the
    table are the threads in this order; if their number differs, only the
    rows labelled 'THREAD a.t.h' are used.

    Returns {thread_obj: {call name: time in us}}.
    """
    if not path or not os.path.exists(path):
        return {}

    with open(path) as stats_file:
        header = stats_file.readline().rstrip('\n').split('\t')
        calls = [column.strip() for column in header[1:]]
        rows = []
        for raw_line in stats_file:
            fields = raw_line.rstrip('\n').split('\t')
            if not fields[0].strip():
                break
            rows.append((fields[0].strip(), fields[1:]))

    def to_us(fields):
        times = {}
        for call, text in zip(calls, fields):
            if not call:
                continue
            try:
                value = float(text)
            except ValueError:
                continue
            if value:
                times[call] = value / NS_PER_US
        return times

    result = {}
    if len(rows) == len(labels):
        for (thread_obj, _label), (_row, fields) in zip(labels, rows):
            result[thread_obj] = to_us(fields)
    else:
        for row_label, fields in rows:
            if row_label.startswith('THREAD '):
                result[row_label] = to_us(fields)
    return result


def host_call_group_times(calls_by_thread, host_threads):
    """Time of the host units in each group of CUDA calls (total, us)."""
    totals = OrderedDict((group, 0.0) for group in CUDA_CALL_GROUPS)
    for thread_obj in host_threads:
        for call, time_us in calls_by_thread.get(thread_obj, {}).items():
            totals[classify_cuda_call(call)] += time_us
    return totals


def _number(value):
    if value in UNAVAILABLE:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(number) else number


def _raw(raw_data, key, trace):
    return raw_data.get(key, {}).get(trace, 'Non-Avail')


def create_device_work_factors(raw_data, trace_list, scaling_info):
    """Device work metrics: {metric key: {trace: value}}."""
    factors = OrderedDict(
        (key, {trace: 'Non-Avail' for trace in trace_list})
        for key in mod_device_work_doc
    )
    if not trace_list:
        return factors

    reference = trace_list[0]
    multi = len(trace_list) > 1
    device_mode = scaling_info.mode('device') if scaling_info else 'strong'

    for trace in trace_list:
        devices = _number(_raw(raw_data, 'count_devices', trace))
        kernel_time = _number(_raw(raw_data, 'useful_device', trace))
        if not devices or kernel_time is None:
            continue

        factors['dev_kernel_time'][trace] = kernel_time / 1.0e6
        if not multi:
            continue

        devices_ref = _number(_raw(raw_data, 'count_devices', reference))
        try:
            work_ratio = scaling_info.work_ratio(
                trace, devices / devices_ref, domain='device')
        except (AttributeError, TypeError, ZeroDivisionError, KeyError):
            work_ratio = 1.0

        kernel_ref = _number(_raw(raw_data, 'useful_device', reference))
        if device_mode == 'strong':
            factors['dev_comp_scale_unscaled'][trace] = 'N/A'
        elif kernel_ref is not None and kernel_time > 0:
            factors['dev_comp_scale_unscaled'][trace] = (
                100.0 * kernel_ref / kernel_time)
        else:
            factors['dev_comp_scale_unscaled'][trace] = 'NaN'

        for key, integral_key in DEVICE_WORK_INTEGRALS.items():
            integral = _number(_raw(raw_data, integral_key, trace))
            integral_ref = _number(_raw(raw_data, integral_key, reference))
            if integral is None or integral_ref is None:
                continue
            factors[key][trace] = (
                100.0 * integral_ref / integral * work_ratio
                if integral > 0 else 'NaN')

    return factors


def create_host_calls_factors(raw_data, trace_list):
    """Host time split: {metric key: {trace: % of the host time}}."""
    factors = OrderedDict(
        (key, {trace: 'Non-Avail' for trace in trace_list})
        for key in mod_host_calls_doc
    )
    for trace in trace_list:
        units = _number(_raw(raw_data, 'host_calls_units', trace))
        runtime = _number(_raw(raw_data, 'runtime', trace))
        groups = {group: _number(_raw(raw_data, 'host_calls_' + group, trace))
                  for group in CUDA_CALL_GROUPS}
        if not units or not runtime or any(v is None for v in groups.values()):
            continue
        host_time = units * runtime
        for group, time_us in groups.items():
            factors['host_time_' + group][trace] = 100.0 * time_us / host_time
        factors['host_time_framework'][trace] = max(
            0.0, 100.0 - 100.0 * sum(groups.values()) / host_time)
    return factors


def has_metrics(factors, trace_list):
    """True if any trace has a value (not Non-Avail/N/A) in the factors."""
    return bool(factors) and any(
        factors[key].get(trace, 'Non-Avail') not in ('Non-Avail', 'N/A')
        for key in factors for trace in trace_list)


def _shown_keys(factors, doc, trace_list):
    """Keys with a value in some trace (the others are not printed)."""
    return [key for key in doc
            if any(factors[key].get(trace, 'Non-Avail') not in ('Non-Avail', 'N/A')
                   for trace in trace_list)]


def format_value(key, value):
    """Text of a value: seconds for the kernel time, % otherwise."""
    number = _number(value)
    if number is None:
        return '{}'.format(value)
    if key == 'dev_kernel_time':
        return '{0:.3f}'.format(number)
    return '{0:.2f}%'.format(number)


TABLES = {
    'device_work': {
        'doc': mod_device_work_doc,
        'title': (' Device work: kernel time and scalability of the work measured by the '
                  'GPU hardware counters\n (indicators next to the Device Computation '
                  'scalability; not factors of the model):'),
        'csv': 'device_work_metrics.csv',
        'csv_title': 'Device Work Metrics',
    },
    'host_calls': {
        'doc': mod_host_calls_doc,
        'title': (' Host time split: time of the Host units outside CUDA calls '
                  '(framework) and in each group\n of CUDA calls, in % of the '
                  'Host time:'),
        'csv': 'host_cuda_calls.csv',
        'csv_title': 'Host Time Split',
    },
}


def print_table(name, factors, trace_list, trace_processes, trace_tasks,
                trace_threads, trace_mode, raw_data):
    """Print a GPU assessment table (TABLES[name]) on stdout."""
    import hybridmetrics

    doc = TABLES[name]['doc']
    keys = _shown_keys(factors, doc, trace_list)
    if not keys:
        return

    labels = hybridmetrics._build_hybrid_configuration_labels(
        trace_list, trace_processes, trace_tasks, trace_threads, trace_mode,
        raw_data)
    header = hybridmetrics._configuration_header(trace_list, trace_mode)
    longest = max([len(doc[key]) for key in keys] + [len(header)])
    width = max(14, max(len(label) for label in labels) + 1)

    line = header.rjust(longest) + ''.join(' | ' + l.rjust(width) for l in labels)
    print('\n' + TABLES[name]['title'])
    print(''.ljust(len(line), '='))
    print(line)
    print(''.ljust(len(line), '='))
    for key in keys:
        row = doc[key].ljust(longest)
        for trace in trace_list:
            row += ' | ' + format_value(key, factors[key][trace]).rjust(width)
        print(row)
        if key in ('dev_comp_scale_unscaled', 'host_time_framework'):
            print(''.ljust(len(line), '-'))
    print(''.ljust(len(line), '='))
    print('')


def print_csv(name, factors, trace_list, trace_processes, trace_tasks,
              trace_threads, trace_mode, raw_data):
    """Write a GPU assessment table (TABLES[name]) to its CSV file.

    The kernel time is written in seconds; the other metrics in %.
    """
    import hybridmetrics

    doc = TABLES[name]['doc']
    keys = _shown_keys(factors, doc, trace_list)
    if not keys:
        return

    labels = hybridmetrics._build_hybrid_configuration_labels(
        trace_list, trace_processes, trace_tasks, trace_threads, trace_mode,
        raw_data)
    file_path = os.path.join(os.getcwd(), TABLES[name]['csv'])
    with open(file_path, 'w') as output:
        output.write('"Metric"' + ''.join(',' + label for label in labels) + '\n')
        for key in keys:
            line = '"' + doc[key] + '"'
            for trace in trace_list:
                value = factors[key][trace]
                number = _number(value)
                line += ',' + ('{0:.6f}'.format(number) if number is not None
                               else '{}'.format(value))
            output.write(line + '\n')

    print('======== Output File: {} ========'.format(TABLES[name]['csv_title']))
    print('{} written to {}'.format(TABLES[name]['csv_title'], file_path))
    print('')
