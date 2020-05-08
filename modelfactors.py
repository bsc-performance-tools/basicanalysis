#!/usr/bin/env python3

"""modelfactors.py Generates performance metrics from a set of Paraver traces."""

from __future__ import print_function, division
import sys
import os
import subprocess
import plots
from utils import parse_arguments, check_installation
from tracemetadata import get_traces_from_args
from rawdata import gather_raw_data, print_raw_data_table, print_raw_data_csv
from simplemetrics import compute_model_factors, print_mod_factors_csv, print_efficiency_table, \
    print_mod_factors_table, read_mod_factors_csv, print_other_metrics_table, \
    print_other_metrics_csv, plots_efficiency_table_matplot, plots_modelfactors_matplot

import hybridmetrics

try:
    import pandas as pd
except ImportError:
    print('==ERROR== Could not import pandas. Please make sure to install a current version for plotting.')
try:
    import seaborn as sns
except ImportError:
    print('==ERROR== Could not import seaborn. Please make sure to install a current version for plotting.')

try:
    import matplotlib.pyplot as plt
except ImportError:
     print('==ERROR== Could not import matplotlib. Please make sure to install a current version for plotting.')



try:
    import scipy.optimize
except ImportError:
    print('==ERROR== Could not import SciPy. Please make sure to install a current version.')

try:
    import numpy
except ImportError:
    print('==ERROR== Could not import NumPy. Please make sure to install a current version.')


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

    # Check if projection-only mode is selected
    # If not: compute everything
    # Else: read the passed modelfactors.csv
    if not cmdl_args.project:
        trace_list, trace_processes, trace_task_per_node, trace_mode = get_traces_from_args(cmdl_args)

        # To validate the metric type
        trace_metrics = 0
        #print(trace_mode)
        for trace in trace_list:
            if trace_mode[trace] == 'Detailed+MPI' or \
                    trace_mode[trace][:16] == 'Detailed+non-MPI' or \
                    trace_mode[trace][:5] == 'Burst':

                trace_metrics += 1

        # Analyze the traces and gather the raw input data
        raw_data, list_mpi_procs_count = gather_raw_data(trace_list, trace_processes, trace_task_per_node,
                                                         trace_mode, cmdl_args)
        # print_raw_data_table(raw_data, trace_list, trace_processes)
        print_raw_data_csv(raw_data, trace_list, trace_processes)

        # Compute the model factors and print them

        if cmdl_args.metrics == 'hybrid' and trace_metrics == 0:
            mod_factors, mod_factors_scale_plus_io, hybrid_factors, other_metrics = hybridmetrics.compute_model_factors(raw_data, trace_list, \
                                                    trace_processes, trace_mode, list_mpi_procs_count, cmdl_args)
            hybridmetrics.print_other_metrics_table(other_metrics, trace_list, trace_processes)
            hybridmetrics.print_other_metrics_csv(other_metrics, trace_list, trace_processes)
            hybridmetrics.print_mod_factors_table(mod_factors, other_metrics, mod_factors_scale_plus_io, hybrid_factors, trace_list, trace_processes)
            hybridmetrics.print_mod_factors_csv(mod_factors, hybrid_factors, trace_list, trace_processes)
            # plot efficiency table
            hybridmetrics.print_efficiency_table(mod_factors, hybrid_factors, trace_list, trace_processes)
            subprocess.call(["gnuplot", "efficiency_table_global.gp"])
            subprocess.call(["gnuplot", "efficiency_table-hybrid.gp"])


            # Plotting if SciPy and NumPy are installed.
            try:
                numpy.__version__
                scipy.__version__
            except NameError:
                print('Scipy or NumPy module not available. Skipping plotting.')
                sys.exit(1)
            if len(trace_list) > 1:
                plots.plot_hybrid_metrics(mod_factors, hybrid_factors, trace_list, trace_processes, cmdl_args)
            # Plotting efficiency table with matplotlib
            try:
                pd.__version__
                plt.__file__
                sns.__version__
            except NameError:
                print('pandas or matplotlib or seaborn modules not available. Skipping plotting with matplotlib.')
                sys.exit(1)
            hybridmetrics.plots_efficiency_table_matplot(trace_list, trace_processes, cmdl_args)
            if len(trace_list) > 1:
                hybridmetrics.plots_modelfactors_matplot(trace_list, trace_processes, cmdl_args)
        elif cmdl_args.metrics == 'simple' or trace_metrics > 0:
            mod_factors, mod_factors_scale_plus_io, other_metrics = compute_model_factors(raw_data, trace_list, trace_processes
                                                                , trace_mode, list_mpi_procs_count, cmdl_args)
            print_other_metrics_table(other_metrics, trace_list, trace_processes)
            print_other_metrics_csv(other_metrics, trace_list, trace_processes)
            print_mod_factors_table(mod_factors, other_metrics, mod_factors_scale_plus_io, trace_list, trace_processes)
            print_mod_factors_csv(mod_factors, trace_list, trace_processes)
            # plot efficiency table
            print_efficiency_table(mod_factors, trace_list, trace_processes)
            subprocess.call(["gnuplot", "efficiency_table.gp"])

            # Plotting if SciPy and NumPy are installed.
            try:
                numpy.__version__
                scipy.__version__
            except NameError:
                print('Scipy or NumPy module not available. Skipping plotting.')
                sys.exit(1)
            if len(trace_list) > 1:
                plots.plot_simple_metrics(mod_factors, trace_list, trace_processes, cmdl_args)
            # Plotting efficiency table with matplotlib
            try:
                pd.__version__
                plt.__file__
                sns.__version__
            except NameError:
                print('pandas or matplotlib or seaborn modules not available. Skipping plotting with matplotlib.')
                sys.exit(1)
            plots_efficiency_table_matplot(trace_list, trace_processes, cmdl_args)
            if len(trace_list) > 1:
                plots_modelfactors_matplot(trace_list, trace_processes, cmdl_args)
    else:
        # Read the model factors from the csv file
        mod_factors, trace_list, trace_processes = read_mod_factors_csv(cmdl_args)