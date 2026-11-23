#!/usr/bin/env python3

"""Generate cfgs-report/useful_duration_nsys2prv.cfg, the Useful Duration
timeline of nsys2prv traces (they have no state records, so the Extrae
useful_duration.cfg, based on the Running state, shows nothing).

Value of each useful burst: its duration in microseconds.

  GPU streams:   CUDA kernels (event 63000006), with the nesting level as
                 kernels_streams.cfg (overlapping kernel events counted once).
  Host threads:  intervals outside CUDA runtime/driver calls (event
                 63000000), only on threads that call CUDA, as the useful
                 host time of BasicAnalysis (cuda_calls_host.cfg).

  duration = Int. Between Evt x mask, where the mask is
    kernels:  Sign(nesting level of the kernel event)
    host:     (1 - Sign(nesting level of the call event))
              x Sign(Sign(Next Evt Val) + Sign(Last Evt Type))
  The last factor is 1 on the threads with CUDA calls, from the start to the
  end of the trace, and 0 on the other threads.

BasicAnalysis rewrites the event codes for each trace (nsys2prvevents).

With --mask PATH, it also writes a 0/1 version of the useful timeline with
an analyzer of the time where it is 1, to check the cfg against the useful
times of BasicAnalysis with paramedir:

  paramedir trace.prv mask.cfg mask.csv
  (host threads = elapsed - time in CUDA calls; streams = kernel time)

Usage: generate_useful_duration_cfg.py [OUTPUT] [--mask PATH]
"""

import os
import sys

KERNEL, CALL = 63000006, 63000000
COMMON = """window_position_x 400
window_position_y 100
window_width 600
window_height 114
window_comm_lines_enabled false
window_flags_enabled false
window_noncolor_mode true
window_color_mode window_in_null_gradient_mode
window_custom_color_enabled false
window_custom_background_as_zero true
window_semantic_scale_min_at_zero false
window_logical_filtered true
window_physical_filtered false
window_intracomms_enabled true
window_intercomms_enabled true
window_comm_fromto true
window_comm_tagsize true
window_comm_typeval true
window_units Microseconds
window_maximum_y {maxy}
window_minimum_y 0.000000000000
window_compute_y_max {computey}
window_level thread
window_scale_relative 1.000000000000
window_end_time_relative 1.000000000000
window_object appl {{ 1, {{ All }} }}
window_begin_time_relative 0.000000000000
window_open {open}
window_drawmode draw_maximum
window_drawmode_rows draw_maximum
window_pixel_size 1
window_labels_to_draw 1
window_object_axis_position 0
"""

def single(wid, name, func, event, compose_thread='As Is', top2='As Is', top1='As Is'):
    return ("################################################################################\n"
            "< NEW DISPLAYING WINDOW {n} >\n"
            "################################################################################\n"
            "window_name {n}\nwindow_type single\nwindow_id {i}\n").format(n=name, i=wid) + \
        COMMON.format(maxy='1.000000000000', computey='false', open='false') + (
            "window_selected_functions { 14, { {cpu, Active Thd}, {appl, Adding}, {task, Adding}, "
            "{thread, %s}, {node, Adding}, {system, Adding}, {workload, Adding}, {from_obj, All}, "
            "{to_obj, All}, {tag_msg, All}, {size_msg, All}, {bw_msg, All}, {evt_type, =}, "
            "{evt_value, All} } }\n"
            "window_compose_functions { 9, { {compose_cpu, As Is}, {compose_appl, As Is}, "
            "{compose_task, As Is}, {compose_thread, %s}, {compose_node, As Is}, {compose_system, As Is}, "
            "{compose_workload, As Is}, {topcompose1, %s}, {topcompose2, %s} } }\n"
            "window_filter_module evt_type 1 %d\n\n") % (func, compose_thread, top1, top2, event)

def composed(wid, name, op, a, b, open_=False, maxy='1.000000000000', computey='false', top2='As Is'):
    return ("################################################################################\n"
            "< NEW DISPLAYING WINDOW {n} >\n"
            "################################################################################\n"
            "window_name {n}\nwindow_type composed\nwindow_id {i}\n"
            "window_factors 1.000000000000 1.000000000000\nwindow_shifts 0 0\n"
            "window_operation {op}\nwindow_identifiers {a} {b}\n").format(n=name, i=wid, op=op, a=a, b=b) + \
        COMMON.format(maxy=maxy, computey=computey, open='true' if open_ else 'false') + (
            "window_selected_functions { 5, { {appl, Adding}, {task, Adding}, {node, Adding}, "
            "{system, Adding}, {workload, Adding}, } }\n"
            "window_compose_functions { 9, { {compose_cpu, As Is}, {compose_appl, As Is}, "
            "{compose_task, As Is}, {compose_thread, As Is}, {compose_node, As Is}, {compose_system, As Is}, "
            "{compose_workload, As Is}, {topcompose1, As Is}, {topcompose2, %s} } }\n\n" % top2)

DESC = """Useful Duration for nsys2prv traces (no state records): duration of each
useful burst, in microseconds. On the GPU streams, the CUDA kernels (event
63000006). On the host threads that call CUDA, the intervals outside CUDA
runtime/driver calls (event 63000000), as the useful host time of
BasicAnalysis; threads without CUDA calls show 0. The event codes are
rewritten for each trace with the codes found in its .pcf.
"""

def build(mask=False):
    w = []
    if mask:
        # 0/1 mask: 1 in a kernel (streams) or outside CUDA calls (host threads that call CUDA).
        w.append(single(1, 'in-kernel', 'Last Evt Val', KERNEL, compose_thread='Nesting level', top1='Join Bursts', top2='Sign'))
        w.append(single(2, 'outside-call', 'Last Evt Val', CALL, compose_thread='Nesting level', top1='Join Bursts', top2='1-Sign'))
        w.append(single(3, 'call-follows', 'Next Evt Val', CALL, top2='Sign'))
        w.append(single(4, 'call-seen', 'Last Evt Type', CALL, top2='Sign'))
        w.append(composed(5, 'calls-thread', 'add', 3, 4, top2='Sign'))
        w.append(composed(6, 'host-useful', 'product', 2, 5))
        w.append(composed(7, 'useful-mask', 'add', 1, 6, open_=True))
        n, final = 7, 7
    else:
        w.append(single(1, 'kernel-interval', 'Int. Between Evt', KERNEL))
        w.append(single(2, 'in-kernel', 'Last Evt Val', KERNEL, compose_thread='Nesting level', top1='Join Bursts', top2='Sign'))
        w.append(composed(3, 'kernel-duration', 'product', 1, 2))
        w.append(single(4, 'call-interval', 'Int. Between Evt', CALL))
        w.append(single(5, 'outside-call', 'Last Evt Val', CALL, compose_thread='Nesting level', top1='Join Bursts', top2='1-Sign'))
        w.append(single(6, 'call-follows', 'Next Evt Val', CALL, top2='Sign'))
        w.append(single(7, 'call-seen', 'Last Evt Type', CALL, top2='Sign'))
        w.append(composed(8, 'calls-thread', 'add', 6, 7, top2='Sign'))
        w.append(composed(9, 'host-useful', 'product', 5, 8))
        w.append(composed(10, 'host-useful-duration', 'product', 4, 9))
        w.append(composed(11, 'Useful Duration (nsys2prv)', 'add', 3, 10, open_=True,
                          maxy='1000.000000000000', computey='true'))
        n, final = 11, 11
    text = ("#ParaverCFG\nConfigFile.Version: 3.4\nConfigFile.NumWindows: %d\n"
            "ConfigFile.BeginDescription\n%sConfigFile.EndDescription\nConfigFile.SyncGroups \n\n") % (n, DESC)
    text += ''.join(w)
    if mask:
        text += ANALYZER.format(final=final)
    return text

ANALYZER = """< NEW ANALYZER2D >
Analyzer2D.Name: useful-mask-time
Analyzer2D.X: 400
Analyzer2D.Y: 100
Analyzer2D.Width: 600
Analyzer2D.Height: 400
Analyzer2D.ControlWindow: {final}
Analyzer2D.DataWindow: {final}
Analyzer2D.Accumulator: Semantic
Analyzer2D.Statistic: Time
Analyzer2D.CalculateAll: True
Analyzer2D.HideCols: False
Analyzer2D.HorizVert: Horizontal
Analyzer2D.Color: True
Analyzer2D.SemanticColor: False
Analyzer2D.Zoom: Disabled
Analyzer2D.SortCols: False
Analyzer2D.SortCriteria: Total
Analyzer2D.SortReverse: False
Analyzer2D.AnalysisLimits: Alltrace
Analyzer2D.ComputeYScale: False
Analyzer2D.ComputeYScaleZero: False
Analyzer2D.Minimum: 1.000000000000
Analyzer2D.Maximum: 1.000000000000
Analyzer2D.Delta: 1.000000000000
Analyzer2D.UseFixedDelta: True
Analyzer2D.NumColumns: 1
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
"""


def main(argv):
    here = os.path.dirname(os.path.realpath(__file__))
    output = os.path.join(here, '..', '..', 'cfgs-report', 'useful_duration_nsys2prv.cfg')
    mask_path = None
    args = list(argv)
    if '--mask' in args:
        index = args.index('--mask')
        mask_path = args[index + 1]
        del args[index:index + 2]
    if args:
        output = args[0]
    with open(output, 'w') as out:
        out.write(build(mask=False))
    if mask_path:
        with open(mask_path, 'w') as out:
            out.write(build(mask=True))


if __name__ == '__main__':
    main(sys.argv[1:])
