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
and mean durations) explain where the I/O time is spent.

Times in the raw data are in microseconds.
"""

from __future__ import print_function, division

import os
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

NON_AVAIL = 'Non-Avail'

# Groups of diagnostics shown in the report.
IO_DIAGNOSTIC_GROUPS = [
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
    ('Operations', [
        'io_{}_{}'.format(operation, quantity)
        for operation in OPERATIONS
        for quantity in ('time', 'operations', 'mean_duration')
    ]),
]


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
