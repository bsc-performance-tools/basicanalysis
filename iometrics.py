"""File I/O performance model: Data Access and File Management.

The traced I/O calls (POSIX, ANSI C, and MPI-IO) are classified by their
meaning: calls that move or commit application data are Data Access, calls
that only manage the file (open, close, positioning, control) are File
Management. I/O Efficiency is decomposed as

    IOEff = DAEff x FMEff
    DAEff = U / (U + DA)
    FMEff = (U + DA) / (U + DA + FM)

where U is the useful time of the units that perform File I/O (the Host
processes and threads; the kernel time of the GPU streams is excluded)
and DA and FM the time in each component. When
the units synchronize after their I/O, the time paid is that of the slowest
unit; the I/O on the critical path, IO_cp, is the sum over the kinds of
operation (read, write, open, ...) of the maximum time of a unit:

    I/O Critical-Path Efficiency = U_avg / (U_avg + IO_cp)
                                 = IOEff x I/O Load Balance
    I/O Load Balance             = (U_avg + IO_avg) / (U_avg + IO_cp)

The diagnostics (time fractions, contributions, load balance, operation counts,
and mean durations) explain where the I/O time is spent. The request-size
distribution of the read and write calls of every API (power-of-two
intervals) shows which request sizes cost the time, and the files accessed
by the POSIX and ANSI C calls show whether the processes share files.

Times in the raw data are in microseconds.
"""

from __future__ import print_function, division

import os
import textwrap
from collections import OrderedDict


# POSIX and ANSI C calls recorded by Extrae (event 40000004).
POSIX_CALL_OPERATIONS = {
    'read': 'read',
    'fread': 'read',
    'pread': 'read',
    'readv': 'read',
    'preadv': 'read',
    'write': 'write',
    'fwrite': 'write',
    'pwrite': 'write',
    'writev': 'write',
    'pwritev': 'write',
    'open': 'open',
    'fopen': 'open',
    'close': 'close',
    'fclose': 'close',
    'lseek': 'seek',
    'fseek': 'seek',
    'ioctl': 'control',
}

DATA_ACCESS_OPERATIONS = ('read', 'write')

FILE_MANAGEMENT_OPERATIONS = ('open', 'close', 'seek', 'control', 'other')

OPERATIONS = DATA_ACCESS_OPERATIONS + FILE_MANAGEMENT_OPERATIONS

OPERATION_LABELS = {
    'read': 'Read',
    'write': 'Write',
    'open': 'Open',
    'close': 'Close',
    'seek': 'Seek',
    'control': 'Control (ioctl)',
    'other': 'Other calls',
}

APIS = ('posix', 'mpiio')

# Labels of the value 0 of the event, which is not a call.
NOT_A_CALL = {'', 'End', 'Outside MPI'}


def classify_call(api, call):
    """Return (operation, known) for a traced I/O call.

    The operation is one of OPERATIONS. Calls that the classification does
    not know are counted as File Management ('other') and reported as
    unknown, so that the classification can be extended.
    """
    if api == 'posix':
        operation = POSIX_CALL_OPERATIONS.get(call)

        if operation is not None:
            return operation, True

        return 'other', False

    name = call.lower()

    if name.startswith('mpi_file_read'):
        return 'read', True

    if name.startswith('mpi_file_write'):
        return 'write', True

    if name == 'mpi_file_open':
        return 'open', True

    if name == 'mpi_file_close':
        return 'close', True

    return 'other', False


# Factors of I/O Efficiency, reported with the other metrics
# (other_metrics.csv). I/O Efficiency itself is computed by the
# simple and hybrid metrics.
IO_FACTORS_DOC = OrderedDict([
    ('io_da_eff', '-- Data Access Efficiency (%)'),
    ('io_fm_eff', '-- File Management Efficiency (%)'),
    ('io_lb', 'I/O Load Balance (%)'),
    ('io_cp_eff', 'I/O Critical-Path Efficiency (%)'),
])

# Hierarchy of the I/O efficiencies, as printed and in io_metrics.csv.
IO_EFFICIENCY_TREE = [
    ('io_cp_eff', 'I/O Critical-Path Efficiency (%)'),
    ('io_eff', '-- I/O Efficiency (%)'),
    ('io_da_eff', '   -- Data Access Efficiency (%)'),
    ('io_fm_eff', '   -- File Management Efficiency (%)'),
    ('io_lb', '-- I/O Load Balance (%)'),
]

# Diagnostics: (label, unit). Reported in io_metrics.csv and in the
# standard output.
IO_DIAGNOSTICS_DOC = OrderedDict([
    ('io_fraction_avg', ('I/O time fraction, average (%)', '%')),
    ('io_fraction_max', ('I/O time fraction, maximum (%)', '%')),
    ('io_participation', ('I/O participation (%)', '%')),
    ('io_mpiio_contribution', ('MPI-IO contribution (%)', '%')),
    ('io_posix_contribution', ('POSIX and ANSI C contribution (%)', '%')),
    ('io_read_contribution', ('Read contribution to Data Access (%)', '%')),
    ('io_write_contribution', ('Write contribution to Data Access (%)', '%')),
    ('io_da_load_balance', ('Data Access Load Balance (%)', '%')),
    ('io_read_load_balance', ('Read Load Balance (%)', '%')),
    ('io_write_load_balance', ('Write Load Balance (%)', '%')),
    ('io_open_contribution', ('Open contribution to File Management (%)', '%')),
    ('io_close_contribution', ('Close contribution to File Management (%)', '%')),
    ('io_seek_contribution', ('Seek contribution to File Management (%)', '%')),
    ('io_control_contribution', ('Control contribution to File Management (%)', '%')),
    ('io_other_contribution', ('Other calls contribution to File Management (%)', '%')),
    ('io_fm_load_balance', ('File Management Load Balance (%)', '%')),
    ('io_open_load_balance', ('Open Load Balance (%)', '%')),
])

for _operation in OPERATIONS:
    _label = OPERATION_LABELS[_operation]
    IO_DIAGNOSTICS_DOC['io_{}_time'.format(_operation)] = (
        '{} time (s)'.format(_label), 's')
    IO_DIAGNOSTICS_DOC['io_{}_operations'.format(_operation)] = (
        '{} operations'.format(_label), 'count')
    IO_DIAGNOSTICS_DOC['io_{}_mean_duration'.format(_operation)] = (
        '{} mean duration (us)'.format(_label), 'us')

# Requests of the read and write calls of every API (POSIX, ANSI C, and
# MPI-IO).
REQUEST_SIZE_OPERATIONS = DATA_ACCESS_OPERATIONS

API_LABELS = {
    'posix': 'POSIX/ANSI C',
    'mpiio': 'MPI-IO',
}

for _operation in REQUEST_SIZE_OPERATIONS:
    _label = OPERATION_LABELS[_operation]
    IO_DIAGNOSTICS_DOC['io_{}_volume'.format(_operation)] = (
        '{} volume (bytes)'.format(_label), 'bytes')
    IO_DIAGNOSTICS_DOC['io_{}_mean_request_size'.format(_operation)] = (
        '{} mean request size (bytes)'.format(_label), 'bytes')
    IO_DIAGNOSTICS_DOC['io_{}_size_coverage'.format(_operation)] = (
        '{} request-size coverage (%)'.format(_label), '%')

# Files accessed by the POSIX and ANSI C calls (MPI-IO records no file).
# The main process of a file is the one that reads and writes most of its
# bytes: 100% of the volume moved by the main processes means one process
# per file; a file shared evenly by N processes gives 100/N %.
IO_DIAGNOSTICS_DOC['io_files'] = ('Files accessed', 'count')
IO_DIAGNOSTICS_DOC['io_max_processes_per_file'] = (
    'Processes per file, maximum', 'count')
IO_DIAGNOSTICS_DOC['io_main_process_volume'] = (
    'Volume moved by the main process of each file (%)', '%')
IO_DIAGNOSTICS_DOC['io_file_name_coverage'] = (
    'File-name coverage of the volume (%)', '%')

FILE_DIAGNOSTICS = [
    'io_files',
    'io_max_processes_per_file',
    'io_main_process_volume',
    'io_file_name_coverage',
]

# Access pattern of the POSIX and ANSI C reads and writes to regular files
# (see rawdata.parse_io_access_pattern_trace): each request is compared
# with the previous request of the same kind on the same descriptor.
ACCESS_PATTERN_CLASSES = OrderedDict([
    ('first', 'First'),
    ('consecutive', 'Consecutive'),
    ('strided', 'Strided'),
    ('forward', 'Forward'),
    ('backward', 'Backward'),
    ('unknown', 'Unknown offset'),
])

# Meaning of each class, for the report and the standard output.
ACCESS_PATTERN_DESCRIPTIONS = OrderedDict([
    ('first', 'The first read (write) on the descriptor after it is '
              'opened: there is no previous request to compare with.'),
    ('consecutive', 'Starts exactly where the previous read (write) '
                    'ended: the file is read (written) in order, without '
                    'gaps.'),
    ('strided', 'Leaves the same gap after the previous request as that '
                'request left after the one before it: a regular pattern, '
                'such as one record every N bytes.'),
    ('forward', 'Jumps ahead, skipping part of the file, by a gap '
                'different from the previous one.'),
    ('backward', 'Jumps back to an earlier offset, by a gap different from '
                 'the previous one; includes reading (writing) the same '
                 'region again.'),
    ('unknown', 'The offset cannot be rebuilt from the trace: '
                'pread/pwrite calls, descriptors without a traced open '
                '(until their first seek), and requests after a seek '
                'without a recorded offset (older Extrae versions).'),
])

# How the classes are obtained, for the report and the standard output.
ACCESS_PATTERN_METHOD = (
    'Each read (write) is compared with the previous read (write) of the '
    'same process on the same file descriptor. The offsets are rebuilt from '
    'the opens (offset 0), the seeks (taken as absolute), and the request '
    'sizes.'
)

for _operation in REQUEST_SIZE_OPERATIONS:
    _label = OPERATION_LABELS[_operation]
    IO_DIAGNOSTICS_DOC['io_{}_consecutive_volume'.format(_operation)] = (
        '{} volume in consecutive requests (%)'.format(_label), '%')
    IO_DIAGNOSTICS_DOC['io_{}_reaccessed_volume'.format(_operation)] = (
        '{} volume re-accessed (%)'.format(_label), '%')
    IO_DIAGNOSTICS_DOC['io_{}_offset_coverage'.format(_operation)] = (
        '{} offset coverage (%)'.format(_label), '%')

IO_DIAGNOSTICS_DOC['io_seek_to_current'] = (
    'Seeks to the current position (%)', '%')

# Diagnostics of the access pattern of each operation in
# REQUEST_SIZE_OPERATIONS (io_<operation>_<quantity>).
ACCESS_PATTERN_QUANTITIES = (
    'consecutive_volume', 'reaccessed_volume', 'offset_coverage')

# Name of the calls on descriptors without an open in the trace.
UNNAMED_FILE_LABEL = '(descriptors without a traced open)'

# Files shown in the standard output and in the report.
TOP_FILES = 10

NON_AVAIL = 'Non-Avail'

# Diagnostics of the distribution of the I/O time, in the groups shown in
# the report. The operations, the requests, and the files have their own
# tables in the report (OPERATION_QUANTITIES, REQUEST_QUANTITIES,
# FILE_DIAGNOSTICS).
IO_TIME_DIAGNOSTIC_GROUPS = [
    ('I/O time', [
        'io_fraction_avg',
        'io_fraction_max',
        'io_participation',
        'io_mpiio_contribution',
        'io_posix_contribution',
    ]),
    ('Data Access', [
        'io_read_contribution',
        'io_write_contribution',
        'io_da_load_balance',
        'io_read_load_balance',
        'io_write_load_balance',
    ]),
    ('File Management', [
        'io_open_contribution',
        'io_close_contribution',
        'io_seek_contribution',
        'io_control_contribution',
        'io_other_contribution',
        'io_fm_load_balance',
        'io_open_load_balance',
    ]),
]

# Diagnostics of each operation (io_<operation>_<quantity>).
OPERATION_QUANTITIES = ('time', 'operations', 'mean_duration')

# Diagnostics of the requests of each operation in REQUEST_SIZE_OPERATIONS.
REQUEST_QUANTITIES = ('volume', 'mean_request_size', 'size_coverage')

BINARY_UNITS = ('B', 'KiB', 'MiB', 'GiB', 'TiB', 'PiB')


def format_bytes(value):
    """Format a number of bytes with binary units (1 KiB = 1024 B)."""
    unit = 0

    while value >= 1024.0 and unit < len(BINARY_UNITS) - 1:
        value /= 1024.0
        unit += 1

    if unit == 0:
        return '{0:.0f} B'.format(value)

    return '{0:.2f} {1}'.format(value, BINARY_UNITS[unit])


def request_size_interval_label(low, high, dash='-'):
    """Label of the request-size interval [low, high) bytes, in the unit of
    its lower bound: '1 B', '2-4 B', '512-1024 B', '1-2 KiB', '>= 2 GiB'.
    high is None for the last interval."""
    unit = 0
    scale = 1

    while low >= 1024 * scale and unit < len(BINARY_UNITS) - 1:
        scale *= 1024
        unit += 1

    if high is None:
        return '>= {0:g} {1}'.format(low / scale, BINARY_UNITS[unit])

    if high - low == 1:
        return '{0:g} {1}'.format(low / scale, BINARY_UNITS[unit])

    return '{0:g}{1}{2:g} {3}'.format(
        low / scale, dash, high / scale, BINARY_UNITS[unit])


def is_unused_diagnostic(values):
    """True when a diagnostic has no value or is zero for every trace (a call
    or API not used by any trace)."""
    return all(value in (NON_AVAIL, 0.0) for value in values)


def aggregate_io_calls(trace_io_data):
    """Aggregate the per-unit call tables of a trace by operation and API.

    Returns None when the trace has no call tables (e.g. raw data produced
    by a previous BasicAnalysis version). Otherwise returns:
        {
            'units': [unit labels],
            'time': {operation: [per unit]},
            'count': {operation: [per unit]},
            'api_time': {api: [per unit]},
            'unknown': [(api, call), ...],
        }
    """
    calls = (trace_io_data or {}).get('calls')

    if not calls:
        return None

    tables = [
        (api, stat, (calls.get(api) or {}).get(stat))
        for api in APIS
        for stat in ('time', 'count')
    ]

    if all(table is None for _, _, table in tables):
        return None

    units = []

    for _, _, table in tables:
        if table is None:
            continue

        for unit in table['units']:
            if unit not in units:
                units.append(unit)

    index = {unit: position for position, unit in enumerate(units)}

    aggregate = {
        'units': units,
        'time': {operation: [0.0] * len(units) for operation in OPERATIONS},
        'count': {operation: [0.0] * len(units) for operation in OPERATIONS},
        'api_time': {api: [0.0] * len(units) for api in APIS},
        'unknown': [],
    }

    for api, stat, table in tables:
        if table is None:
            continue

        for call, values in table['calls'].items():
            if call in NOT_A_CALL:
                continue

            operation, known = classify_call(api, call)

            if not known and (api, call) not in aggregate['unknown']:
                aggregate['unknown'].append((api, call))

            for unit, value in zip(table['units'], values):
                position = index[unit]
                aggregate[stat][operation][position] += value

                if stat == 'time':
                    aggregate['api_time'][api][position] += value

    return aggregate


def io_useful_time(raw_data, trace):
    """Useful time (us) of the units that perform File I/O.

    The I/O factors compare the I/O time with the useful time of the same
    units: the Host processes and threads (the THREAD rows of the timings
    table). In GPU traces useful_tot also holds the kernel time of the GPU
    streams, which perform no File I/O. useful_tot is used when the Host
    useful time is not available.
    """
    try:
        useful_io = float(raw_data['useful_io_tot'][trace])
    except (KeyError, TypeError, ValueError):
        useful_io = 0.0

    if useful_io > 0.0:
        return useful_io

    return float(raw_data['useful_tot'][trace])


def _request_call_count(trace_io_data, operation):
    """Number of calls of an operation that issue a request (call tables of
    every API). The *_end call of an MPI-IO split collective completes the
    request of its *_begin call and is not counted."""
    calls = (trace_io_data or {}).get('calls') or {}
    total = 0.0

    for api in APIS:
        table = (calls.get(api) or {}).get('count')

        if not table:
            continue

        for call, values in table['calls'].items():
            if call in NOT_A_CALL:
                continue

            if api == 'mpiio' and call.lower().endswith('_end'):
                continue

            if classify_call(api, call)[0] == operation:
                total += sum(values)

    return total


def io_request_size_distribution(trace_io_data):
    """Request-size distribution of the read and write calls of a trace
    (every API).

    Returns {operation: [bin, ...]} for the operations with requests, where
    every bin of the raw data (min, max, count, time, bytes) gets the
    'label' and the shares of the operation (count_pct, time_pct,
    bytes_pct).
    """
    distribution = OrderedDict()
    request_size = (trace_io_data or {}).get('request_size') or {}

    for operation in REQUEST_SIZE_OPERATIONS:
        bins = (request_size.get(operation) or {}).get('bins') or []

        totals = {
            key: sum(bin_[key] for bin_ in bins)
            for key in ('count', 'time', 'bytes')
        }

        if totals['count'] <= 0.0:
            continue

        rows = []

        for bin_ in bins:
            row = dict(bin_)
            row['label'] = request_size_interval_label(
                bin_['min'], bin_['max'])

            for key in ('count', 'time', 'bytes'):
                row[key + '_pct'] = _percentage(bin_[key], totals[key])

            rows.append(row)

        distribution[operation] = rows

    return distribution


def io_request_size_distribution_by_api(trace_io_data):
    """Request-size distribution of each API: {operation: {api: [bin]}}.
    The shares of every bin are relative to the totals of the operation in
    all the APIs, so that the bins of all the APIs add up to 100%."""
    distribution = OrderedDict()
    request_size = (trace_io_data or {}).get('request_size') or {}

    for operation in REQUEST_SIZE_OPERATIONS:
        by_api = (request_size.get(operation) or {}).get('bins_by_api') or {}
        bins = [bin_ for api in APIS for bin_ in by_api.get(api, [])]

        totals = {
            key: sum(bin_[key] for bin_ in bins)
            for key in ('count', 'time', 'bytes')
        }

        if totals['count'] <= 0.0:
            continue

        distribution[operation] = OrderedDict()

        for api in APIS:
            rows = []

            for bin_ in by_api.get(api, []):
                row = dict(bin_)
                row['label'] = request_size_interval_label(
                    bin_['min'], bin_['max'])

                for key in ('count', 'time', 'bytes'):
                    row[key + '_pct'] = _percentage(bin_[key], totals[key])

                rows.append(row)

            if rows:
                distribution[operation][api] = rows

    return distribution


def _add_file_access_pattern(row, pattern):
    """Add to a file row the access pattern of its reads and writes:
    for each operation and class, the shares of the requests and of the
    bytes ('<operation>_<class>_requests_pct', '..._bytes_pct'), and the
    share of the bytes in consecutive requests
    ('<operation>_consecutive_volume'). NON_AVAIL when the file has no
    classified request of the operation (no requests to a regular file, or
    no access-pattern data)."""
    for operation in REQUEST_SIZE_OPERATIONS:
        classes = (pattern or {}).get(operation) or {}
        totals = {
            key: sum(stats[key] for stats in classes.values())
            for key in ('requests', 'bytes')
        }

        for name in ACCESS_PATTERN_CLASSES:
            stats = classes.get(name) or {'requests': 0.0, 'bytes': 0.0}

            for key in ('requests', 'bytes'):
                row['{}_{}_{}_pct'.format(operation, name, key)] = (
                    _percentage(stats[key], totals[key])
                    if totals['requests'] > 0.0 else NON_AVAIL)

        row['{}_consecutive_volume'.format(operation)] = row[
            '{}_consecutive_bytes_pct'.format(operation)]


def _file_row(name, stats, unnamed=False):
    row = OrderedDict([
        ('name', name),
        ('unnamed', unnamed),
        ('processes', len(stats['processes'])),
        ('opens', stats['opens']),
        ('time', stats['time']),
    ])

    for operation in REQUEST_SIZE_OPERATIONS:
        for key in ('requests', 'bytes', 'time'):
            row['{}_{}'.format(operation, key)] = stats[operation][key]

        row['{}_processes'.format(operation)] = len(
            stats[operation]['processes'])

    row['bytes'] = sum(
        row['{}_bytes'.format(operation)]
        for operation in REQUEST_SIZE_OPERATIONS
    )
    row['main_process_bytes'] = max(
        [entry[-1] for entry in stats.get('bytes_by_process', [])] or [0.0])
    row['main_process_pct'] = _percentage(
        row['main_process_bytes'], row['bytes'])

    return row


def io_file_access_rows(trace_io_data):
    """Files accessed by the POSIX and ANSI C calls of a trace, in
    decreasing I/O time, followed by the calls on descriptors without an
    open in the trace (when there are any).

    Each row has the file name, the processes that call on the file, the
    opens, the I/O time (all the calls on the file, us), the requests,
    bytes, time, and processes of the read and write calls, the bytes read
    and written, the bytes of the process that moves the most
    (main_process_bytes, and its share main_process_pct), and the shares of
    the time and of the bytes of all the rows (time_pct, bytes_pct).
    Returns [] when the trace has no file data.
    """
    file_access = (trace_io_data or {}).get('file_access')

    if not file_access:
        return []

    pattern = (trace_io_data or {}).get('access_pattern') or {}
    file_patterns = pattern.get('files') or {}

    rows = []

    for name, stats in file_access['files'].items():
        row = _file_row(name, stats)
        _add_file_access_pattern(row, file_patterns.get(name))
        rows.append(row)

    rows.sort(key=lambda row: (-row['time'], row['name']))

    unnamed = file_access['unnamed']

    if unnamed['processes']:
        row = _file_row(UNNAMED_FILE_LABEL, unnamed, unnamed=True)
        # Several descriptors of each process: no main process.
        row['main_process_bytes'] = NON_AVAIL
        row['main_process_pct'] = NON_AVAIL
        _add_file_access_pattern(row, pattern.get('unnamed'))
        rows.append(row)

    total_time = sum(row['time'] for row in rows)
    total_bytes = sum(row['bytes'] for row in rows)

    for row in rows:
        row['time_pct'] = _percentage(row['time'], total_time)
        row['bytes_pct'] = _percentage(row['bytes'], total_bytes)

    return rows


def io_access_pattern(trace_io_data):
    """Access pattern of the reads and writes of a trace.

    Returns {operation: [row, ...]} for the operations with requests to
    regular files, one row per class of ACCESS_PATTERN_CLASSES with the
    'class', its 'label', the 'requests', 'bytes', and 'time' (us), and
    their shares of the operation (requests_pct, bytes_pct, time_pct).
    """
    distribution = OrderedDict()
    pattern = (trace_io_data or {}).get('access_pattern') or {}

    for operation in REQUEST_SIZE_OPERATIONS:
        classes = pattern.get(operation) or {}
        totals = {
            key: sum(stats[key] for stats in classes.values())
            for key in ('requests', 'bytes', 'time')
        }

        if totals['requests'] <= 0.0:
            continue

        rows = []

        for name, label in ACCESS_PATTERN_CLASSES.items():
            stats = classes.get(
                name, {'requests': 0.0, 'bytes': 0.0, 'time': 0.0})
            row = OrderedDict([('class', name), ('label', label)])

            for key in ('requests', 'bytes', 'time'):
                row[key] = stats[key]
                row[key + '_pct'] = _percentage(stats[key], totals[key])

            rows.append(row)

        distribution[operation] = rows

    return distribution


def access_pattern_diagnostics(trace_io_data):
    """Diagnostics of the access pattern: per operation, the share of the
    volume in consecutive requests, the share of the volume re-accessed by
    the same process in the same file, and the share of the requests to
    regular files with a known offset; and the share of the seeks (with an
    offset) that go to the current position."""
    keys = [
        'io_{}_{}'.format(operation, quantity)
        for operation in REQUEST_SIZE_OPERATIONS
        for quantity in ACCESS_PATTERN_QUANTITIES
    ] + ['io_seek_to_current']
    metrics = OrderedDict((key, NON_AVAIL) for key in keys)
    pattern = (trace_io_data or {}).get('access_pattern') or {}

    if not pattern:
        return metrics

    for operation, rows in io_access_pattern(trace_io_data).items():
        by_class = {row['class']: row for row in rows}
        requests = sum(row['requests'] for row in rows)

        metrics['io_{}_consecutive_volume'.format(operation)] = (
            by_class['consecutive']['bytes_pct'])
        metrics['io_{}_offset_coverage'.format(operation)] = _percentage(
            requests - by_class['unknown']['requests'], requests)

        reaccess = (pattern.get('reaccess') or {}).get(operation) or {}

        if reaccess.get('bytes', 0.0) > 0.0:
            metrics['io_{}_reaccessed_volume'.format(operation)] = (
                _percentage(reaccess['bytes'] - reaccess['distinct'],
                            reaccess['bytes']))

    seeks = pattern.get('seeks') or {}
    metrics['io_seek_to_current'] = _percentage(
        seeks.get('to_current', 0.0), seeks.get('with_offset', 0.0))

    return metrics


def file_diagnostics(rows):
    """Diagnostics of the files accessed (FILE_DIAGNOSTICS) from the rows of
    io_file_access_rows."""
    metrics = OrderedDict((key, NON_AVAIL) for key in FILE_DIAGNOSTICS)
    files = [row for row in rows if not row['unnamed']]

    if not rows:
        return metrics

    total_bytes = sum(row['bytes'] for row in rows)
    file_bytes = sum(row['bytes'] for row in files)

    metrics['io_files'] = float(len(files))

    if files:
        metrics['io_max_processes_per_file'] = float(
            max(row['processes'] for row in files))

    metrics['io_main_process_volume'] = _percentage(
        sum(row['main_process_bytes'] for row in files), file_bytes)
    metrics['io_file_name_coverage'] = _percentage(file_bytes, total_bytes)

    return metrics


def _percentage(numerator, denominator):
    if denominator > 0.0:
        return numerator / denominator * 100.0

    return NON_AVAIL


def _participant_load_balance(values):
    """Average over the participating units divided by the maximum."""
    participants = [value for value in values if value > 0.0]

    if not participants:
        return NON_AVAIL

    return (
        sum(participants) / len(participants)
        / max(participants) * 100.0
    )


def _sum_units(*series):
    return [sum(values) for values in zip(*series)]


def compute_trace_io_metrics(useful_tot, runtime, io_units, trace_io_data):
    """Compute the I/O factors and diagnostics of one trace.

    useful_tot: total useful time of the units that perform File I/O (us),
        as returned by io_useful_time.
    runtime: execution time (us).
    io_units: number of execution units that can perform File I/O (Host
        units), used for the average time fraction and the participation.

    Returns (metrics, aggregate), where metrics maps every key of
    IO_FACTORS_DOC and IO_DIAGNOSTICS_DOC to a value or 'Non-Avail'.
    """
    metrics = OrderedDict(
        (key, NON_AVAIL)
        for key in list(IO_FACTORS_DOC) + list(IO_DIAGNOSTICS_DOC)
    )

    aggregate = aggregate_io_calls(trace_io_data)

    if aggregate is None:
        return metrics, None

    time = aggregate['time']
    count = aggregate['count']

    read_units = time['read']
    write_units = time['write']
    da_units = _sum_units(read_units, write_units)
    fm_units = _sum_units(*[time[op] for op in FILE_MANAGEMENT_OPERATIONS])
    io_units_time = _sum_units(da_units, fm_units)

    da_tot = sum(da_units)
    fm_tot = sum(fm_units)
    io_tot = da_tot + fm_tot

    if io_tot <= 0.0:
        return metrics, aggregate

    # Factors of I/O Efficiency.
    metrics['io_da_eff'] = _percentage(useful_tot, useful_tot + da_tot)
    metrics['io_fm_eff'] = _percentage(
        useful_tot + da_tot,
        useful_tot + da_tot + fm_tot,
    )

    # Load balance on the critical path: each kind of operation costs the
    # time of the slowest unit (units synchronized after each kind).
    if io_units > 0:
        useful_avg = useful_tot / io_units
        io_avg = io_tot / io_units
        io_cp = sum(max(time[operation]) for operation in OPERATIONS)

        metrics['io_lb'] = _percentage(
            useful_avg + io_avg, useful_avg + io_cp)
        metrics['io_cp_eff'] = _percentage(useful_avg, useful_avg + io_cp)

    # I/O time.
    if io_units > 0:
        metrics['io_fraction_avg'] = _percentage(io_tot, io_units * runtime)

        participants = sum(1 for value in io_units_time if value > 0.0)
        metrics['io_participation'] = participants / io_units * 100.0

    metrics['io_fraction_max'] = _percentage(max(io_units_time), runtime)

    metrics['io_mpiio_contribution'] = _percentage(
        sum(aggregate['api_time']['mpiio']), io_tot)
    metrics['io_posix_contribution'] = _percentage(
        sum(aggregate['api_time']['posix']), io_tot)

    # Data Access.
    metrics['io_read_contribution'] = _percentage(sum(read_units), da_tot)
    metrics['io_write_contribution'] = _percentage(sum(write_units), da_tot)
    metrics['io_da_load_balance'] = _participant_load_balance(da_units)
    metrics['io_read_load_balance'] = _participant_load_balance(read_units)
    metrics['io_write_load_balance'] = _participant_load_balance(write_units)

    # File Management.
    for operation in FILE_MANAGEMENT_OPERATIONS:
        metrics['io_{}_contribution'.format(operation)] = _percentage(
            sum(time[operation]), fm_tot)

    metrics['io_fm_load_balance'] = _participant_load_balance(fm_units)
    metrics['io_open_load_balance'] = _participant_load_balance(time['open'])

    # Per operation.
    for operation in OPERATIONS:
        operation_time = sum(time[operation])
        operation_count = sum(count[operation])

        if operation_time <= 0.0 and operation_count <= 0.0:
            continue

        metrics['io_{}_time'.format(operation)] = operation_time / 1e6
        metrics['io_{}_operations'.format(operation)] = operation_count

        if operation_count > 0.0:
            metrics['io_{}_mean_duration'.format(operation)] = (
                operation_time / operation_count
            )

    # Requests (every API).
    for operation, bins in io_request_size_distribution(
            trace_io_data).items():
        requests = sum(bin_['count'] for bin_ in bins)
        volume = sum(bin_['bytes'] for bin_ in bins)

        metrics['io_{}_volume'.format(operation)] = volume
        metrics['io_{}_mean_request_size'.format(operation)] = (
            volume / requests)

        calls = _request_call_count(trace_io_data, operation)

        if calls > 0.0:
            metrics['io_{}_size_coverage'.format(operation)] = (
                requests / calls * 100.0)

    # Files (POSIX and ANSI C).
    metrics.update(file_diagnostics(io_file_access_rows(trace_io_data)))

    # Access pattern (POSIX and ANSI C).
    metrics.update(access_pattern_diagnostics(trace_io_data))

    return metrics, aggregate


def add_io_metrics(other_metrics, raw_data, io_data, trace_list):
    """Add the I/O factors and diagnostics of every trace to other_metrics.

    other_metrics must contain the internal key 'io_units' (Host execution
    units of each trace) set by the simple or hybrid metrics. The I/O
    Efficiency already in other_metrics is not modified; a warning is
    printed when the classified call time differs from the I/O time used by
    I/O Efficiency, because the factors would then not multiply to it.
    """
    for key in list(IO_FACTORS_DOC) + list(IO_DIAGNOSTICS_DOC):
        other_metrics[key] = {trace: NON_AVAIL for trace in trace_list}

    # Internal key: request-size distribution of each trace (see
    # io_request_size_distribution), for the report and io_request_sizes.csv.
    other_metrics['io_request_sizes'] = {
        trace: io_request_size_distribution((io_data or {}).get(trace))
        for trace in trace_list
    }
    other_metrics['io_request_sizes_by_api'] = {
        trace: io_request_size_distribution_by_api(
            (io_data or {}).get(trace))
        for trace in trace_list
    }
    # Internal key: files accessed by each trace (see io_file_access_rows),
    # for the report and io_files.csv.
    other_metrics['io_file_access'] = {
        trace: io_file_access_rows((io_data or {}).get(trace))
        for trace in trace_list
    }
    # Internal key: access pattern of each trace (see io_access_pattern),
    # for the report and io_access_pattern.csv.
    other_metrics['io_access_pattern'] = {
        trace: io_access_pattern((io_data or {}).get(trace))
        for trace in trace_list
    }

    unknown_calls = []

    for trace in trace_list:
        try:
            useful_tot = io_useful_time(raw_data, trace)
            runtime = float(raw_data['runtime'][trace])
            reference_io = (
                float(raw_data['io_tot'][trace])
                + float(raw_data['mpiio_tot'][trace])
            )
        except (KeyError, TypeError, ValueError):
            continue

        io_units = other_metrics.get('io_units', {}).get(trace, 0)

        metrics, aggregate = compute_trace_io_metrics(
            useful_tot,
            runtime,
            io_units,
            (io_data or {}).get(trace),
        )

        for key, value in metrics.items():
            other_metrics[key][trace] = value

        if aggregate is None:
            continue

        for call in aggregate['unknown']:
            if call not in unknown_calls:
                unknown_calls.append(call)

        classified_io = sum(
            sum(values) for values in aggregate['time'].values()
        )

        if (
            reference_io > 0.0
            and abs(classified_io - reference_io) / reference_io > 0.01
        ):
            print(
                '==WARNING== The time of the classified I/O calls '
                '({0:.3f} s) differs by more than 1% from the I/O time '
                '({1:.3f} s) in {2}. Data Access and File Management '
                'Efficiency do not multiply exactly to I/O Efficiency.'
                .format(classified_io / 1e6, reference_io / 1e6, trace)
            )

    if unknown_calls:
        print(
            '==WARNING== I/O calls not known to the Data Access / File '
            'Management classification were counted as File Management: '
            + ', '.join(
                '{} ({})'.format(call, 'MPI-IO' if api == 'mpiio'
                                 else 'POSIX/ANSI C')
                for api, call in unknown_calls
            )
        )


def has_io_metrics(other_metrics, trace_list):
    """Return whether any trace has the I/O factors."""
    return any(
        other_metrics.get('io_da_eff', {}).get(trace, NON_AVAIL) != NON_AVAIL
        for trace in trace_list
    )


def format_io_value(value, unit):
    """Format an I/O metric value for the standard output."""
    if not isinstance(value, (int, float)):
        return '{}'.format(value)

    if unit == '%':
        return '{0:.2f}%'.format(value)

    if unit == 's':
        return '{0:.3f}'.format(value)

    if unit == 'count':
        return '{0:.0f}'.format(value)

    if unit == 'bytes':
        return format_bytes(value)

    return '{0:.1f}'.format(value)


def print_io_diagnostics_table(other_metrics, trace_list, column_labels,
                               longest_name, value_to_adjust):
    """Print the I/O diagnostics that have a value for some trace."""
    line_head = 'I/O diagnostics'.ljust(longest_name)

    for label in column_labels:
        line_head += ' | ' + label.rjust(value_to_adjust)

    print('Overview of File I/O diagnostics:')
    print(''.ljust(len(line_head), '-'))

    for key, (label, unit) in IO_DIAGNOSTICS_DOC.items():
        values = [other_metrics[key][trace] for trace in trace_list]

        # Calls or APIs not used by any trace (io_metrics.csv keeps them).
        if is_unused_diagnostic(values):
            continue

        line = label.ljust(longest_name)

        for value in values:
            line += ' | ' + format_io_value(value, unit).rjust(value_to_adjust)

        print(line)

    print(''.ljust(len(line_head), '-'))


def io_diagnostics_label_width():
    """Width of the longest diagnostic label."""
    return max(len(label) for label, _ in IO_DIAGNOSTICS_DOC.values())


def print_io_tables(other_metrics, trace_list, column_labels,
                    value_to_adjust):
    """Print the I/O efficiencies, and the I/O diagnostics."""
    rows = IO_EFFICIENCY_TREE

    longest_name = io_diagnostics_label_width()

    line_head = ''.ljust(longest_name)

    for label in column_labels:
        line_head += ' | ' + label.rjust(value_to_adjust)

    print('Overview of File I/O Efficiency:')
    print(''.ljust(len(line_head), '-'))

    for key, label in rows:
        line = label.ljust(longest_name)

        for trace in trace_list:
            value = other_metrics.get(key, {}).get(trace, NON_AVAIL)
            line += ' | ' + format_io_value(value, '%').rjust(value_to_adjust)

        print(line)

    print(''.ljust(len(line_head), '-'))

    if has_io_metrics(other_metrics, trace_list):
        print_io_diagnostics_table(
            other_metrics,
            trace_list,
            column_labels,
            longest_name,
            value_to_adjust,
        )
        print_io_request_size_tables(
            other_metrics,
            trace_list,
            column_labels,
            longest_name,
            value_to_adjust,
        )
        print_io_access_pattern_tables(
            other_metrics,
            trace_list,
            column_labels,
            longest_name,
        )
        print_io_file_tables(other_metrics, trace_list, column_labels)


def _request_size_rows(other_metrics, trace_list, operation):
    """Intervals with requests in some trace, in increasing size, and the
    bin of each trace in each interval ({trace: bin})."""
    intervals = OrderedDict()

    for trace in trace_list:
        distribution = (
            other_metrics.get('io_request_sizes', {}).get(trace) or {})

        for bin_ in distribution.get(operation, []):
            intervals.setdefault(bin_['min'], {})[trace] = bin_

    return [
        (low, intervals[low]) for low in sorted(intervals)
    ]


def print_io_request_size_tables(other_metrics, trace_list, column_labels,
                                 longest_name, value_to_adjust):
    """Print the share of the requests and of the time of each
    power-of-two request-size interval."""
    for operation in REQUEST_SIZE_OPERATIONS:
        rows = _request_size_rows(other_metrics, trace_list, operation)

        if not rows:
            continue

        # Cells hold two shares ('100.0 / 100.0').
        width = max(value_to_adjust, 13)
        line_head = 'Request size'.ljust(longest_name)

        for label in column_labels:
            line_head += ' | ' + label.rjust(width)

        print('{} requests per size interval '
              '(% of requests / % of time):'.format(
                  OPERATION_LABELS[operation]))
        print(''.ljust(len(line_head), '-'))
        print(line_head)
        print(''.ljust(len(line_head), '-'))

        for _, bins in rows:
            any_bin = next(iter(bins.values()))
            line = any_bin['label'].ljust(longest_name)

            for trace in trace_list:
                bin_ = bins.get(trace)

                if bin_ is None:
                    cell = '-'
                else:
                    cell = '{0:.1f} / {1:.1f}'.format(
                        bin_['count_pct'], bin_['time_pct'])

                line += ' | ' + cell.rjust(width)

            print(line)

        print(''.ljust(len(line_head), '-'))


def print_io_access_pattern_tables(other_metrics, trace_list, column_labels,
                                   longest_name):
    """Print the share of the requests, of the bytes, and of the time of
    each access-pattern class of the reads and writes."""
    patterns = other_metrics.get('io_access_pattern', {})
    printed = False

    for operation in REQUEST_SIZE_OPERATIONS:
        if not any((patterns.get(trace) or {}).get(operation)
                   for trace in trace_list):
            continue

        # Cells hold three shares ('100.0 / 100.0 / 100.0').
        width = 21
        line_head = 'Access pattern'.ljust(longest_name)

        for label in column_labels:
            line_head += ' | ' + label.strip().rjust(width)

        print('{} access pattern, POSIX and ANSI C on regular files '
              '(% of requests / % of bytes / % of time):'.format(
                  OPERATION_LABELS[operation]))
        print(''.ljust(len(line_head), '-'))
        print(line_head)
        print(''.ljust(len(line_head), '-'))

        for name, label in ACCESS_PATTERN_CLASSES.items():
            line = label.ljust(longest_name)

            for trace in trace_list:
                rows = {
                    row['class']: row
                    for row in (patterns.get(trace) or {}).get(operation, [])
                }
                row = rows.get(name)

                if row is None:
                    cell = '-'
                else:
                    cell = ' / '.join(
                        '-' if row[key] == NON_AVAIL
                        else '{0:.1f}'.format(row[key])
                        for key in ('requests_pct', 'bytes_pct', 'time_pct'))

                line += ' | ' + cell.rjust(width)

            print(line)

        print(''.ljust(len(line_head), '-'))
        printed = True

    if printed:
        print_access_pattern_legend()


def print_access_pattern_legend(width=79):
    """Print the meaning of the access-pattern classes."""
    print('Access pattern classes:')

    for line in textwrap.wrap(ACCESS_PATTERN_METHOD, width - 2):
        print('  ' + line)

    for name, label in ACCESS_PATTERN_CLASSES.items():
        lines = textwrap.wrap(
            '{}: {}'.format(label, ACCESS_PATTERN_DESCRIPTIONS[name]),
            width - 4)

        print('  - ' + lines[0])

        for line in lines[1:]:
            print('    ' + line)

    print('')


def shorten_file_name(name, width):
    """Keep the end of a long file name ('...part2.vtkhdf')."""
    if len(name) <= width:
        return name

    return '...' + name[-(width - 3):]


def _file_percentage_cell(value):
    if value == NON_AVAIL:
        return '-'

    return format_io_value(value, '%')


def print_io_file_tables(other_metrics, trace_list, column_labels,
                         name_width=48):
    """Print, for every trace, the files with the most I/O time. The
    consecutive columns are the shares of the bytes read and written in
    consecutive requests (see the access pattern)."""
    columns = [
        ('Processes', lambda row: '{0:d}'.format(row['processes'])),
        ('Read', lambda row: format_bytes(row['read_bytes'])),
        ('Written', lambda row: format_bytes(row['write_bytes'])),
        ('Main process', lambda row: (
            '-' if row['main_process_pct'] == NON_AVAIL
            else format_io_value(row['main_process_pct'], '%'))),
        ('I/O time (s)', lambda row: '{0:.3f}'.format(row['time'] / 1e6)),
        ('I/O time (%)', lambda row: format_io_value(row['time_pct'], '%')),
        ('Consec. read', lambda row: _file_percentage_cell(
            row.get('read_consecutive_volume', NON_AVAIL))),
        ('Consec. write', lambda row: _file_percentage_cell(
            row.get('write_consecutive_volume', NON_AVAIL))),
    ]
    width = max(len(title) for title, _ in columns)

    for trace, label in zip(trace_list, column_labels):
        rows = other_metrics.get('io_file_access', {}).get(trace) or []

        if not rows:
            continue

        files = [row for row in rows if not row['unnamed']]
        shown = files[:TOP_FILES] + [row for row in rows if row['unnamed']]

        line_head = 'File'.ljust(name_width)

        for title, _ in columns:
            line_head += ' | ' + title.rjust(width)

        print('Files with the most I/O time, POSIX and ANSI C ({0}, {1} of '
              '{2} files):'.format(label.strip(), min(len(files), TOP_FILES),
                                    len(files)))
        print(''.ljust(len(line_head), '-'))
        print(line_head)
        print(''.ljust(len(line_head), '-'))

        for row in shown:
            line = shorten_file_name(row['name'], name_width).ljust(
                name_width)

            for _, cell in columns:
                line += ' | ' + cell(row).rjust(width)

            print(line)

        print(''.ljust(len(line_head), '-'))
        print('Consec. read / write: share of the bytes read / written in '
              'consecutive requests (access pattern, regular files).')
        print('')


def print_io_files_csv(other_metrics, trace_list):
    """Write the files accessed by the POSIX and ANSI C calls to
    io_files.csv, one row per trace and file, in decreasing I/O time."""
    files = other_metrics.get('io_file_access', {})

    if not any(files.get(trace) for trace in trace_list):
        return

    delimiter = ';'
    file_path = os.path.join(os.getcwd(), 'io_files.csv')

    columns = [
        ('Trace', None),
        ('File', None),
        ('Processes', 'processes'),
        ('Opens', 'opens'),
        ('I/O time (us)', 'time'),
        ('Read requests', 'read_requests'),
        ('Read bytes', 'read_bytes'),
        ('Read time (us)', 'read_time'),
        ('Reading processes', 'read_processes'),
        ('Write requests', 'write_requests'),
        ('Write bytes', 'write_bytes'),
        ('Write time (us)', 'write_time'),
        ('Writing processes', 'write_processes'),
        ('Main process bytes', 'main_process_bytes'),
        ('Main process bytes (%)', 'main_process_pct'),
        ('I/O time (%)', 'time_pct'),
        ('Bytes (%)', 'bytes_pct'),
    ]
    columns += [
        ('{} {} {} (%)'.format(
            OPERATION_LABELS[operation], label.lower(), key),
         '{}_{}_{}_pct'.format(operation, name, key))
        for operation in REQUEST_SIZE_OPERATIONS
        for name, label in ACCESS_PATTERN_CLASSES.items()
        for key in ('requests', 'bytes')
    ]

    with open(file_path, 'w') as output:
        output.write(
            delimiter.join('"' + c + '"' for c, _ in columns) + '\n')

        for trace in trace_list:
            for row in files.get(trace) or []:
                values = [
                    '"' + trace + '"',
                    '"' + row['name'].replace('"', '""') + '"',
                ]

                for _, key in columns[2:]:
                    value = row.get(key, NON_AVAIL)

                    if not isinstance(value, (int, float)):
                        values.append(str(value))
                    elif key.endswith('_pct') or key.endswith('time'):
                        values.append('{0:.6f}'.format(value))
                    else:
                        values.append('{0:.0f}'.format(value))

                output.write(delimiter.join(values) + '\n')

    print('======== Output File: I/O Files ========')
    print('Files accessed written to ' + file_path)
    print('')


def print_io_access_pattern_csv(other_metrics, trace_list):
    """Write the access pattern of the reads and writes to
    io_access_pattern.csv, one row per trace, operation, and class."""
    patterns = other_metrics.get('io_access_pattern', {})

    if not any(patterns.get(trace) for trace in trace_list):
        return

    delimiter = ';'
    file_path = os.path.join(os.getcwd(), 'io_access_pattern.csv')

    columns = [
        'Trace', 'Operation', 'Class', 'Requests', 'Bytes', 'Time (us)',
        'Requests (%)', 'Bytes (%)', 'Time (%)',
    ]

    with open(file_path, 'w') as output:
        output.write(delimiter.join('"' + c + '"' for c in columns) + '\n')

        for trace in trace_list:
            for operation, rows in (patterns.get(trace) or {}).items():
                for row in rows:
                    values = [
                        '"' + trace + '"',
                        '"' + operation + '"',
                        '"' + row['label'] + '"',
                        '{0:.0f}'.format(row['requests']),
                        '{0:.0f}'.format(row['bytes']),
                        '{0:.3f}'.format(row['time']),
                    ]

                    for key in ('requests_pct', 'bytes_pct', 'time_pct'):
                        value = row[key]
                        values.append(
                            '{0:.6f}'.format(value)
                            if isinstance(value, float) else str(value))

                    output.write(delimiter.join(values) + '\n')

    print('======== Output File: I/O Access Pattern ========')
    print('Access pattern written to ' + file_path)
    print('')


def print_io_request_sizes_csv(other_metrics, trace_list):
    """Write the request-size distribution to io_request_sizes.csv, one row
    per trace, operation, API, and non-empty interval. The shares are
    relative to the operation in all the APIs."""
    distributions = other_metrics.get('io_request_sizes_by_api', {})

    if not any(distributions.get(trace) for trace in trace_list):
        return

    delimiter = ';'
    file_path = os.path.join(os.getcwd(), 'io_request_sizes.csv')

    columns = [
        'Trace', 'API', 'Operation', 'Interval', 'Minimum size (bytes)',
        'Maximum size (bytes, excluded)', 'Requests', 'Time (us)', 'Bytes',
        'Requests (%)', 'Time (%)', 'Bytes (%)',
    ]

    with open(file_path, 'w') as output:
        output.write(delimiter.join('"' + c + '"' for c in columns) + '\n')

        for trace in trace_list:
            for operation, by_api in (distributions.get(trace) or {}).items():
                for api, bin_ in [(api, bin_) for api, bins in by_api.items()
                                  for bin_ in bins]:
                    values = [
                        '"' + trace + '"',
                        '"' + API_LABELS[api] + '"',
                        '"' + operation + '"',
                        '"' + bin_['label'] + '"',
                        '{:d}'.format(int(bin_['min'])),
                        '' if bin_['max'] is None
                        else '{:d}'.format(int(bin_['max'])),
                        '{0:.0f}'.format(bin_['count']),
                        '{0:.3f}'.format(bin_['time']),
                        '{0:.0f}'.format(bin_['bytes']),
                    ]

                    for key in ('count_pct', 'time_pct', 'bytes_pct'):
                        value = bin_[key]
                        values.append(
                            '{0:.6f}'.format(value)
                            if isinstance(value, float) else str(value))

                    output.write(delimiter.join(values) + '\n')

    print('======== Output File: I/O Request Sizes ========')
    print('Request-size distribution written to ' + file_path)
    print('')


def print_io_metrics_csv(other_metrics, trace_list, trace_processes):
    """Write the I/O factors and diagnostics to io_metrics.csv."""
    if not has_io_metrics(other_metrics, trace_list):
        return

    delimiter = ';'
    file_path = os.path.join(os.getcwd(), 'io_metrics.csv')

    rows = [
        (key, label.replace('-- ', '').strip())
        for key, label in IO_EFFICIENCY_TREE
    ]
    rows += [
        (key, label)
        for key, (label, _) in IO_DIAGNOSTICS_DOC.items()
    ]

    with open(file_path, 'w') as output:
        line = '"Number of processes"'

        for trace in trace_list:
            line += delimiter + str(trace_processes[trace])

        output.write(line + '\n')

        for key, label in rows:
            line = '"' + label + '"'

            for trace in trace_list:
                value = other_metrics.get(key, {}).get(trace, NON_AVAIL)
                line += delimiter

                try:
                    line += '{0:.6f}'.format(value)
                except (TypeError, ValueError):
                    line += '{}'.format(value)

            output.write(line + '\n')

        output.write('#\n')

    print('======== Output File: I/O Metrics ========')
    print('I/O factors and diagnostics written to ' + file_path)
    print('')
