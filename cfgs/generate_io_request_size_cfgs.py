#!/usr/bin/env python3
"""Generate the power-of-two request-size histograms of the POSIX and ANSI C
read and write calls (io-<operation>-size-pow2-<statistic>.cfg).

Paraver has no logarithm function, so the interval index of a request of
size s is built as a sum of steps:

    index = sum over k = 0..31 of [s >= 2^k] = 1 + floor(log2(s))

Interval j holds the requests of size [2^(j-1), 2^j); interval 32 also holds
the requests of 2 GiB or more. Each step is a window with the function
Is In Range [2^k, inf), and the steps are added with a balanced tree of
derived windows.

BasicAnalysis does not run these cfgs: it computes the same intervals in
Python from the trace filtered with io-requests-filter.xml (rawdata.
parse_io_requests_trace), which is much faster. The cfgs are provided to
inspect the intervals in Paraver, preferably on the filtered trace (on the
full trace the 70 windows are slow).

Usage (from the cfgs folder):  python3 generate_io_request_size_cfgs.py
"""

import os

# Values of the I/O calls event (40000004) in Extrae.
FAMILIES = {
    'read': [1, 3, 5, 7, 9],     # read, fread, pread, readv, preadv
    'write': [2, 4, 6, 8, 10],   # write, fwrite, pwrite, writev, pwritev
}

STATISTICS = {
    'count': '# Bursts',
    'time': 'Time',
    'bytes': 'Sum bursts',
}

STEPS = 32
HUGE = '9223372036854775808.000000000000'
DBL_MAX = (
    '179769313486231570814527423731704356798070567525844996598917476803157'
    '260780028538760589558632766878171540458953514382464234321326889464182'
    '768467546703537516986049910576551282076245490090389328944075868508455'
    '133942304583236903222948165808559332123348274797826204144723168738177'
    '180919299881250404026184124858368.000000000000'
)

WINDOW_HEADER = """################################################################################
< NEW DISPLAYING WINDOW {name} >
################################################################################
window_name {name}
"""

WINDOW_COMMON = """window_position_x 0
window_position_y 0
window_width 600
window_height 134
window_comm_lines_enabled false
window_flags_enabled false
window_noncolor_mode true
window_color_mode window_in_null_gradient_mode
window_gradient_function gradient_function_linear
window_custom_color_enabled false
window_custom_background_as_zero true
window_semantic_scale_min_at_zero false
{filtered}window_units Microseconds
window_maximum_y 1.000000000000
window_minimum_y 0.000000000000
window_compute_y_max false
window_level thread
window_scale_relative 1.000000000000
window_end_time_relative 1.000000000000
window_object appl {{ 1, {{ All }} }}
window_begin_time_relative 0.000000000000
window_open false
window_drawmode draw_maximum
window_drawmode_rows draw_maximum
window_pixel_size 1
window_labels_to_draw 1
window_object_axis_position 0
"""

SINGLE_FILTERS = """window_logical_filtered true
window_physical_filtered false
window_intracomms_enabled true
window_intercomms_enabled true
window_comm_fromto true
window_comm_tagsize true
window_comm_typeval true
"""


def compose_functions(thread='As Is', top1='As Is', top2='As Is'):
    return (
        'window_compose_functions { 9, { {compose_cpu, As Is}, '
        '{compose_appl, As Is}, {compose_task, As Is}, '
        '{compose_thread, %s}, {compose_node, As Is}, '
        '{compose_system, As Is}, {compose_workload, As Is}, '
        '{topcompose1, %s}, {topcompose2, %s} } }\n' % (thread, top1, top2)
    )


def single_window(wid, name, event_type, label, value_function='All',
                  values=None, value_labels=None, thread='As Is',
                  top2='As Is'):
    """Thread-level window on the last value of one event type."""
    text = WINDOW_HEADER.format(name=name)
    text += 'window_type single\nwindow_id %d\n' % wid
    text += WINDOW_COMMON.format(filtered=SINGLE_FILTERS)
    text += (
        'window_selected_functions { 14, { {cpu, Active Thd}, '
        '{appl, Adding}, {task, Adding}, {thread, Last Evt Val}, '
        '{node, Adding}, {system, Adding}, {workload, Adding}, '
        '{from_obj, All}, {to_obj, All}, {tag_msg, All}, {size_msg, All}, '
        '{bw_msg, All}, {evt_type, =}, {evt_value, %s} } }\n'
        % value_function
    )
    text += compose_functions(thread=thread, top2=top2)
    text += 'window_filter_module evt_type 1 %d\n' % event_type
    text += 'window_filter_module evt_type_label 1 "%s"\n' % label

    if values:
        text += 'window_filter_module evt_value %d %s\n' % (
            len(values), ' '.join('%d.000000000000' % v for v in values))

    if value_labels:
        text += 'window_filter_module evt_value_label %d %s\n' % (
            len(value_labels),
            ' '.join('"%s"' % v for v in value_labels))

    return text


def derived_window(wid, name, operation, first, second, thread='As Is',
                   top2='As Is', module=''):
    """Window combining two windows with a derived operation."""
    text = WINDOW_HEADER.format(name=name)
    text += 'window_type composed\nwindow_id %d\n' % wid
    text += 'window_factors 1.000000000000 1.000000000000\n'
    text += 'window_shifts 0 0\n'
    text += 'window_operation %s\n' % operation
    text += 'window_identifiers %d %d\n' % (first, second)
    text += WINDOW_COMMON.format(filtered='')
    text += (
        'window_selected_functions { 5, { {appl, Adding}, {task, Adding}, '
        '{node, Adding}, {system, Adding}, {workload, Adding}, } }\n'
    )
    text += compose_functions(thread=thread, top2=top2)
    text += module
    return text


def build_cfg(operation, statistic):
    windows = []

    # 1: 1 during a call of the family. The value 0 (call exit) is kept and
    # the other calls are filtered out, so the window is 0 between calls.
    windows.append(single_window(
        1, '%s calls' % operation, 40000004, 'I/O calls',
        value_function='=', values=[0] + FAMILIES[operation], top2='Sign'))

    # 2: last request size.
    windows.append(single_window(2, 'I/O size', 40000011, 'I/O size'))

    # 3, 4, 5: 1 when the last I/O call event carries a size (the size
    # event is in the same record), so that a call without size does not
    # take the size of a previous call.
    windows.append(single_window(
        3, 'time of last I/O call event', 40000004, 'I/O calls',
        value_function='!=', values=[11, 14, 16],
        value_labels=['open()', 'close()', 'lseek()'],
        thread='Begin Time'))
    windows.append(single_window(
        4, 'time of last I/O size event', 40000011, 'I/O size',
        thread='Begin Time'))
    windows.append(derived_window(
        5, 'I/O call with size', 'different', 3, 4, thread='1-Sign'))

    # 6: size of the current call; 7: size of the calls of the family.
    windows.append(derived_window(6, 'I/O call size', 'product', 2, 5))
    windows.append(derived_window(
        7, '%s request size' % operation, 'product', 1, 6))

    # Steps: 1 when the request size is 2^k or more.
    steps = []
    wid = 8

    for k in range(STEPS):
        windows.append(derived_window(
            wid, '%s size >= 2^%d' % (operation, k), 'product', 1, 6,
            top2='Is In Range',
            module=(
                'window_semantic_module topcompose2 Is In Range '
                '{ 2, { 1 %s, 1 %d.000000000000 } }\n' % (HUGE, 2 ** k))))
        steps.append(wid)
        wid += 1

    # Balanced sum of the steps: the interval index.
    level = steps

    while len(level) > 1:
        next_level = []

        for i in range(0, len(level) - 1, 2):
            windows.append(derived_window(
                wid, 'interval index %d' % wid, 'add',
                level[i], level[i + 1]))
            next_level.append(wid)
            wid += 1

        if len(level) % 2:
            next_level.append(level[-1])

        level = next_level

    index_window = level[0]

    text = (
        '#ParaverCFG\n'
        'ConfigFile.Version: 3.4\n'
        'ConfigFile.NumWindows: %d\n'
        'ConfigFile.BeginDescription\n'
        '%s of the POSIX and ANSI C %s calls per power-of-two request-size\n'
        'interval: column j holds the requests of size [2^(j-1), 2^j) bytes.\n'
        'Generated by generate_io_request_size_cfgs.py; for a faster\n'
        'computation, load it on the trace filtered with\n'
        'io-requests-filter.xml.\n'
        'ConfigFile.EndDescription\n'
        'ConfigFile.SyncGroups \n\n'
        % (len(windows),
           {'count': 'Number of requests', 'time': 'Time (us)',
            'bytes': 'Bytes'}[statistic],
           operation)
    )
    text += '\n'.join(windows)
    text += """
< NEW ANALYZER2D >
Analyzer2D.Type: single
Analyzer2D.Name: {operation}-size-pow2-{statistic}
Analyzer2D.X: 0
Analyzer2D.Y: 0
Analyzer2D.Width: 600
Analyzer2D.Height: 300
Analyzer2D.ControlWindow: {control}
Analyzer2D.DataWindow: 7
Analyzer2D.Accumulator: Semantic
Analyzer2D.Statistic: {paraver_statistic}
Analyzer2D.CalculateAll: True
Analyzer2D.HideCols: False
Analyzer2D.HorizVert: Horizontal
Analyzer2D.Color: True
Analyzer2D.SemanticColor: False
Analyzer2D.Zoom: Disabled
Analyzer2D.SortCols: False
Analyzer2D.SortCriteria: Total
Analyzer2D.SortReverse: False
Analyzer2D.Parameters: 4 -{dbl_max} {dbl_max}
Analyzer2D.AnalysisLimits: Alltrace
Analyzer2D.ComputeYScale: False
Analyzer2D.ComputeYScaleZero: False
Analyzer2D.Minimum: 1.000000000000
Analyzer2D.Maximum: {maximum}.000000000000
Analyzer2D.Delta: 1.000000000000
Analyzer2D.UseFixedDelta: True
Analyzer2D.NumColumns: {steps}
Analyzer2D.ComputeGradient: True
Analyzer2D.MinimumGradient: 0.000000000000
Analyzer2D.MaximumGradient: 1.000000000000
Analyzer2D.Object: appl {{ 1, {{ All }} }}
Analyzer2D.DrawModeObjects: draw_maximum
Analyzer2D.DrawModeColumns: draw_maximum
Analyzer2D.PixelSize: 1
Analyzer2D.ColorMode: window_in_gradient_mode
Analyzer2D.ShowOnlyTotals: False
Analyzer2D.ShortHeaderLabels: True
""".format(operation=operation, statistic=statistic, control=index_window,
           paraver_statistic=STATISTICS[statistic], dbl_max=DBL_MAX,
           maximum=STEPS + 1, steps=STEPS)
    return text


def main():
    folder = os.path.dirname(os.path.abspath(__file__))

    for operation in FAMILIES:
        for statistic in STATISTICS:
            name = 'io-{}-size-pow2-{}.cfg'.format(operation, statistic)

            with open(os.path.join(folder, name), 'w') as f:
                f.write(build_cfg(operation, statistic))

            print(name)


if __name__ == '__main__':
    main()
