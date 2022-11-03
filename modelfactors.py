#!/usr/bin/env python3

"""modelfactors.py Generates performance metrics from a set of Paraver traces."""

from __future__ import print_function, division
import subprocess
import plots
from utils import parse_arguments, check_installation
from tracemetadata import get_traces_from_args
from rawdata import gather_raw_data, print_raw_data_table, print_raw_data_csv
from simplemetrics import compute_model_factors, print_mod_factors_csv, print_efficiency_table, \
    print_mod_factors_table, read_mod_factors_csv, print_other_metrics_table, \
    print_other_metrics_csv, plots_efficiency_table_matplot, plots_modelfactors_matplot, plots_speedup_matplot

import hybridmetrics

# error import variables
error_import_pandas = False
error_import_seaborn = False
error_import_matplotlib = False
error_import_scipy = False
error_import_numpy = False

try:
    import pandas as pd
except ImportError:
    error_import_pandas = True

try:
    import seaborn as sns
except ImportError:
    error_import_seaborn = True

try:
    import matplotlib.pyplot as plt
except ImportError:
    error_import_matplotlib = True

try:
    import scipy.optimize
except ImportError:
    error_import_scipy = True


try:
    import numpy
except ImportError:
    error_import_numpy = True


__author__ = "Sandra Mendez"
__copyright__ = "Copyright 2019, Barcelona Supercomputing Center (BSC)"
__version_major__ = 0
__version_minor__ = 3
__version_micro__ = 7
__version__ = str(__version_major__) + "." + str(__version_minor__) + "." + str(__version_micro__)


if __name__ == "__main__":
    """Main control flow.
    Currently the script only accepts one parameter, which is a list of traces
    that are processed. This can be a regex with wild cards and only valid trace
    files are kept at the end.
    """
    # Parse command line arguments
    cmdl_args = parse_arguments()

    # Check if paramedir and Dimemas are in the path
    check_installation(cmdl_args)

    # Process the trace list
    trace_list, trace_processes, trace_tasks, trace_threads, trace_task_per_node, trace_mode = \
        get_traces_from_args(cmdl_args)

    # To validate the metric type
    trace_metrics = 0
    # print(trace_mode)
    for trace in trace_list:
        if trace_mode[trace][0:len("Detailed+MPI+")] == "Detailed+MPI+":
            trace_metrics += 1

    # Analyze the traces and gather the raw input data
    raw_data, list_mpi_procs_count = gather_raw_data(trace_list, trace_processes, trace_task_per_node,
                                                     trace_mode, cmdl_args)
    print_raw_data_csv(raw_data, trace_list, trace_processes)

    # Compute the model factors and print them

    if cmdl_args.metrics == 'hybrid' and trace_metrics > 0:
        mod_factors, mod_factors_scale_plus_io, hybrid_factors, other_metrics = \
                hybridmetrics.compute_model_factors(raw_data, trace_list, trace_processes,
                                                    trace_mode, list_mpi_procs_count, cmdl_args)
        hybridmetrics.print_other_metrics_table(other_metrics, trace_list, trace_processes, trace_tasks,
                                                trace_threads, trace_mode)
        hybridmetrics.print_other_metrics_csv(other_metrics, trace_list, trace_processes)
        hybridmetrics.print_mod_factors_table(mod_factors, other_metrics, mod_factors_scale_plus_io, hybrid_factors,
                                              trace_list, trace_processes, trace_tasks, trace_threads, trace_mode)
        hybridmetrics.print_mod_factors_csv(mod_factors, hybrid_factors, trace_list, trace_processes)
        hybridmetrics.print_efficiency_table(mod_factors, hybrid_factors, trace_list, trace_processes, trace_tasks,
                                             trace_threads,trace_mode)
        # Plotting efficiency table with matplotlib
        error_plot_table = False
        if error_import_numpy or error_import_pandas or error_import_matplotlib or error_import_seaborn:
            print('Numpy/Pandas/Matplotlib/Seaborn modules not available. '
                  'Skipping efficiency table plotting with python.')
            if len(trace_list) > 1:
                out_ver_gnuplot = subprocess.check_output(["gnuplot", "--version"])
                if 'gnuplot 5.' not in str(out_ver_gnuplot):
                    print('It requires gnuplot version 5.0 or higher. '
                          'Skipping efficiency table and lineal plotting with gnuplot.')
                else:
                    try:
                        output_gnuplot_g = subprocess.check_output(["gnuplot", "efficiency_table_global.gp"])
                        output_gnuplot_h = subprocess.check_output(["gnuplot", "efficiency_table_hybrid.gp"])
                    except:
                        print(output_gnuplot_g)
                        print(output_gnuplot_h)

            error_plot_table = True

        if not error_plot_table:
            hybridmetrics.plots_efficiency_table_matplot(trace_list, trace_processes, trace_tasks,
                                                         trace_threads, trace_mode, cmdl_args)
            if len(trace_list) > 1:
                hybridmetrics.plots_modelfactors_matplot(trace_list, trace_processes, trace_tasks,
                                                         trace_threads, trace_mode, cmdl_args)
                hybridmetrics.plots_speedup_matplot(trace_list, trace_processes, trace_tasks,
                                                    trace_threads, trace_mode, cmdl_args)

        # Plotting if SciPy and NumPy are installed.
        error_plot_lineal = False
        if error_import_numpy or error_import_scipy:
            print('Scipy/NumPy module not available. Skipping lineal plotting.')
            error_plot_lineal = True

        if not error_plot_lineal:
            if len(trace_list) > 1:
                plots.plot_hybrid_metrics(mod_factors, hybrid_factors, trace_list, trace_processes,
                                          trace_tasks, trace_threads, trace_mode, cmdl_args)

        if len(trace_list) == 1:
            subprocess.check_output(["rm", "efficiency_table_global.gp"])
            subprocess.check_output(["rm", "efficiency_table_hybrid.gp"])

    elif cmdl_args.metrics == 'simple' or trace_metrics == 0:
        mod_factors, mod_factors_scale_plus_io, other_metrics = compute_model_factors(raw_data, trace_list,
                                                                                      trace_processes, trace_mode,
                                                                                      list_mpi_procs_count, cmdl_args)
        print_other_metrics_table(other_metrics, trace_list, trace_processes)
        print_other_metrics_csv(other_metrics, trace_list, trace_processes)
        print_mod_factors_table(mod_factors, other_metrics, mod_factors_scale_plus_io, trace_list, trace_processes, trace_mode)
        print_mod_factors_csv(mod_factors, trace_list, trace_processes)
        print_efficiency_table(mod_factors, trace_list, trace_processes)

        # Plotting efficiency table with matplotlib
        error_plot_table = False
        if error_import_numpy or error_import_pandas or error_import_matplotlib or error_import_seaborn:
            print('Numpy/Pandas/Matplotlib/Seaborn modules not available. '
                  'Skipping efficiency table plotting with python.')
            if len(trace_list) > 1:
                out_ver_gnuplot = subprocess.check_output(["gnuplot", "--version"])
                if 'gnuplot 5.' not in str(out_ver_gnuplot):
                    print('It requires gnuplot version 5.0 or higher. '
                          'Skipping efficiency table and lineal plotting with gnuplot.')
                else:
                    try:
                        output_gnuplot = subprocess.check_output(["gnuplot", "efficiency_table.gp"])
                    except:
                        print(output_gnuplot)
            error_plot_table = True

        if not error_plot_table:
            plots_efficiency_table_matplot(trace_list, trace_processes, trace_tasks, trace_threads, cmdl_args)
            if len(trace_list) > 1:
                plots_modelfactors_matplot(trace_list, trace_mode, trace_processes, trace_tasks, trace_threads,
                                           cmdl_args)

        # Plotting if SciPy and NumPy are installed.
        error_plot_lineal = False
        if error_import_numpy or error_import_scipy:
            print('Scipy/NumPy module not available. Skipping lineal plotting.')
            error_plot_lineal = True
        # sys.exit(1)
        if not error_plot_lineal:
            if len(trace_list) > 1:
                plots.plot_simple_metrics(mod_factors, trace_list, trace_processes, trace_mode, cmdl_args)
                plots_speedup_matplot(trace_list, trace_processes, trace_tasks, trace_threads, cmdl_args)
        if len(trace_list) == 1:
            subprocess.check_output(["rm", "efficiency_table.gp"])
