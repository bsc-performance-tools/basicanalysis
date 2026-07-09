#!/usr/bin/env python3

"""Shared pipeline helpers for BasicAnalysis."""

from __future__ import print_function, division

import subprocess

import hybridmetrics
import plots
import reportdata

from simplemetrics import (
    compute_model_factors,
    print_efficiency_table,
    print_mod_factors_csv,
    print_mod_factors_table,
    print_other_metrics_csv,
    print_other_metrics_table,
    plots_efficiency_table_matplot,
    plots_modelfactors_matplot,
    plots_speedup_matplot,
)

# optional dependency flags
error_import_pandas = False
error_import_seaborn = False
error_import_matplotlib = False
error_import_scipy = False
error_import_numpy = False

error_import_plotly = False

error_import_interactiveplots = False

try:
    import interactiveplots
except ImportError:
    error_import_interactiveplots = True


try:
    import plotly.graph_objects as go
except ImportError:
    error_import_plotly = True

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


def count_hybrid_traces(trace_list, trace_mode):
    """Count traces that should use the hybrid metrics path."""
    trace_metrics = 0
    for trace in trace_list:
        if trace_mode[trace].startswith("Detailed+MPI+"):
            trace_metrics += 1
    return trace_metrics


def compute_metrics(analysis_result, trace_list, trace_processes, trace_tasks,
                    trace_threads, trace_mode, cmdl_args, trace_metrics):
    """Compute either hybrid or simple metrics."""
    raw_data = analysis_result["raw_data"]
    list_mpi_procs_count = analysis_result["list_mpi_procs_count"]

    if cmdl_args.metrics == 'hybrid' and trace_metrics > 0:
        (
            mod_factors,
            mod_factors_scale_plus_io,
            hybrid_factors,
            hyb_comm_omp_factors,
            other_metrics,
            device_factors,
            host_factors,
            hybrid_gpu_factors,
            omp_talp_factors,
        ) = hybridmetrics.compute_model_factors(
                raw_data,
                trace_list,
                trace_processes,
                trace_mode,
                list_mpi_procs_count,
                cmdl_args,
            )

        return {
            "kind": "hybrid",
            "mod_factors": mod_factors,
            "mod_factors_scale_plus_io": mod_factors_scale_plus_io,
            "hybrid_factors": hybrid_factors,
            "hyb_comm_omp_factors": hyb_comm_omp_factors,
            "other_metrics": other_metrics,
            "device_factors": device_factors,
            "host_factors": host_factors,
            "omp_talp_factors": omp_talp_factors,
        }

    mod_factors, mod_factors_scale_plus_io, other_metrics = compute_model_factors(
        raw_data,
        trace_list,
        trace_processes,
        trace_mode,
        list_mpi_procs_count,
        cmdl_args,
    )

    return {
        "kind": "simple",
        "mod_factors": mod_factors,
        "mod_factors_scale_plus_io": mod_factors_scale_plus_io,
        "other_metrics": other_metrics,
    }


def generate_reports(metrics_result, analysis_result, trace_list, trace_processes,
                     trace_tasks, trace_threads, trace_mode, cmdl_args):
    """Generate tables and CSV files."""
    raw_data = analysis_result["raw_data"]

    if metrics_result["kind"] == "hybrid":
        mod_factors = metrics_result["mod_factors"]
        mod_factors_scale_plus_io = metrics_result["mod_factors_scale_plus_io"]
        hybrid_factors = metrics_result["hybrid_factors"]
        hyb_comm_omp_factors = metrics_result["hyb_comm_omp_factors"]
        other_metrics = metrics_result["other_metrics"]
        device_factors = metrics_result["device_factors"]
        host_factors = metrics_result["host_factors"]
        omp_talp_factors = metrics_result["omp_talp_factors"]

        hybridmetrics.print_other_metrics_table(
            other_metrics, trace_list, trace_processes, trace_tasks, trace_threads, trace_mode
        )
        hybridmetrics.print_other_metrics_csv(other_metrics, trace_list, trace_processes)

        if (cmdl_args.pop_model_to_apply == 'talp') and (trace_mode[trace_list[0]] == "Detailed+MPI+CUDA"):
            hybridmetrics.print_talp_metrics_csv(
                device_factors, host_factors, trace_list, trace_processes, raw_data
            )
            hybridmetrics.print_mod_factors_table_talp(
                mod_factors,
                other_metrics,
                mod_factors_scale_plus_io,
                hybrid_factors,
                device_factors,
                host_factors,
                trace_list,
                trace_processes,
                trace_tasks,
                trace_threads,
                trace_mode,
                raw_data,
            )
        else:
            hybridmetrics.print_mod_factors_table(
                mod_factors, other_metrics, mod_factors_scale_plus_io,
                hybrid_factors, hyb_comm_omp_factors, device_factors,
                trace_list, trace_processes, trace_tasks, trace_threads,
                trace_mode, raw_data, cmdl_args
            )
            hybridmetrics.print_efficiency_table(
                mod_factors, hybrid_factors, hyb_comm_omp_factors,
                trace_list, trace_processes, trace_tasks, trace_threads,
                trace_mode, cmdl_args
            )

        hybridmetrics.print_mod_factors_csv(mod_factors, hybrid_factors, trace_list, trace_processes)
        hybridmetrics.print_omp_talp_metrics_csv(omp_talp_factors, trace_list, trace_processes, trace_tasks,\
         trace_threads, trace_mode)
        
        return

    mod_factors = metrics_result["mod_factors"]
    mod_factors_scale_plus_io = metrics_result["mod_factors_scale_plus_io"]
    other_metrics = metrics_result["other_metrics"]

    print_other_metrics_table(other_metrics, trace_list, trace_processes)
    print_other_metrics_csv(other_metrics, trace_list, trace_processes)
    print_mod_factors_table(mod_factors, other_metrics, mod_factors_scale_plus_io, trace_list, trace_processes, trace_mode)
    print_mod_factors_csv(mod_factors, trace_list, trace_processes)
    print_efficiency_table(mod_factors, trace_list, trace_processes)


def can_plot_tables():
    """Check whether matplotlib-based table plotting is available."""
    return not (error_import_numpy or error_import_pandas or error_import_matplotlib or error_import_seaborn)


def can_plot_lineal():
    """Check whether line plotting is available."""
    return not (error_import_numpy or error_import_scipy)

def generate_hybrid_plots(metrics_result, analysis_result, report,
                          trace_list, trace_processes,
                          trace_tasks, trace_threads,
                          trace_mode, cmdl_args):
    """Generate plots for hybrid metrics."""
    raw_data = analysis_result["raw_data"]
    mod_factors = metrics_result["mod_factors"]
    hybrid_factors = metrics_result["hybrid_factors"]

    error_plot_table = False
    if not can_plot_tables():
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
                except Exception:
                    print(output_gnuplot_g)
                    print(output_gnuplot_h)
        error_plot_table = True

    if not error_plot_table:
        if (cmdl_args.pop_model_to_apply == 'talp') and (trace_mode[trace_list[0]] == "Detailed+MPI+CUDA"):
            hybridmetrics.plots_talp_efficiency_table_matplot(
                trace_list, trace_processes, trace_tasks, trace_threads, trace_mode, raw_data, cmdl_args
            )
        else:
            hybridmetrics.plots_efficiency_table_matplot(
                trace_list, trace_processes, trace_tasks, trace_threads, trace_mode, cmdl_args
            )

        if not error_import_interactiveplots:
            if (cmdl_args.pop_model_to_apply == 'talp') and (trace_mode[trace_list[0]] == "Detailed+MPI+CUDA"):
                interactiveplots.plot_talp_efficiency_interactive(
                    metrics_result,
                    analysis_result,
                    trace_list,
                    trace_processes,
                    trace_tasks,
                    trace_threads,
                    trace_mode,
                    cmdl_args,
                )
            else:
                interactiveplots.plot_hybrid_efficiency_interactive(
                    metrics_result,
                    trace_list,
                    trace_processes,
                    trace_tasks,
                    trace_threads,
                    trace_mode,
                    cmdl_args,
                )
            
            interactiveplots.plot_basicanalysis_interactive_report(
                metrics_result,
                analysis_result,
                report,
                trace_list,
                trace_processes,
                trace_tasks,
                trace_threads,
                trace_mode,
                cmdl_args,
            )

        else:
            print('Plotly/interactiveplots module not available. '
                 'Skipping interactive HTML report.')            

        if len(trace_list) > 1:
            if cmdl_args.pop_model_to_apply == 'classic':
                hybridmetrics.plots_modelfactors_matplot(
                    trace_list, trace_processes, trace_tasks, trace_threads, trace_mode, cmdl_args
                )
            hybridmetrics.plots_speedup_matplot(
                trace_list, trace_processes, trace_tasks, trace_threads, trace_mode, cmdl_args
            )

    error_plot_lineal = False
    if not can_plot_lineal():
        print('Scipy/NumPy module not available. Skipping lineal plotting.')
        error_plot_lineal = True

    if not error_plot_lineal:
        if len(trace_list) > 1 and (cmdl_args.pop_model_to_apply == 'classic'):
            plots.plot_hybrid_metrics(
                mod_factors,
                hybrid_factors,
                trace_list,
                trace_processes,
                trace_tasks,
                trace_threads,
                trace_mode,
                cmdl_args,
            )

    if len(trace_list) == 1 and (cmdl_args.pop_model_to_apply == 'classic'):
        subprocess.check_output(["rm", "efficiency_table_global.gp"])
        subprocess.check_output(["rm", "efficiency_table_hybrid.gp"])


def generate_simple_plots(metrics_result, analysis_result, report,
                          trace_list, trace_processes,
                          trace_tasks, trace_threads, trace_mode, cmdl_args):
    """Generate plots for simple metrics."""
    mod_factors = metrics_result["mod_factors"]

    error_plot_table = False
    if not can_plot_tables():
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
                except Exception:
                    print(output_gnuplot)
        error_plot_table = True

    if not error_plot_table:
        plots_efficiency_table_matplot(trace_list, trace_processes, trace_tasks, trace_threads, cmdl_args)
        if not error_import_interactiveplots:
            interactiveplots.plot_simple_efficiency_interactive(
                metrics_result,
                trace_list,
                trace_processes,
                trace_tasks,
                trace_threads,
                trace_mode,
                cmdl_args,
            )

            interactiveplots.plot_basicanalysis_interactive_report(
                metrics_result,
                analysis_result,
                report,
                trace_list,
                trace_processes,
                trace_tasks,
                trace_threads,
                trace_mode,
                cmdl_args,
            )


        else:
            print('Plotly/interactiveplots module not available. '
                      'Skipping interactive HTML report.')

        if len(trace_list) > 1:
            plots_modelfactors_matplot(
                trace_list, trace_mode, trace_processes, trace_tasks, trace_threads, cmdl_args
            )

    error_plot_lineal = False
    if not can_plot_lineal():
        print('Scipy/NumPy module not available. Skipping lineal plotting.')
        error_plot_lineal = True

    if not error_plot_lineal:
        if len(trace_list) > 1:
            plots.plot_simple_metrics(mod_factors, trace_list, trace_processes, trace_mode, cmdl_args)
            plots_speedup_matplot(trace_list, trace_processes, trace_tasks, trace_threads, cmdl_args)

    if len(trace_list) == 1:
        subprocess.check_output(["rm", "efficiency_table.gp"])


def generate_plots(metrics_result, analysis_result, trace_list, trace_processes,
                   trace_tasks, trace_threads, trace_mode, cmdl_args):
    """Generate all plots."""

    report = reportdata.build_report(
        metrics_result,
        analysis_result,
        trace_list,
        trace_processes,
        trace_tasks,
        trace_threads,
        trace_mode,
        cmdl_args,
    )

    if cmdl_args.debug:
        print("==DEBUG== Report data model created")
        print("==DEBUG== Report traces:", len(report["traces"]))
        print("==DEBUG== Report resources:", len(report["resources"]))

    if metrics_result["kind"] == "hybrid":
        generate_hybrid_plots(
            metrics_result,
            analysis_result,
            report,
            trace_list,
            trace_processes,
            trace_tasks,
            trace_threads,
            trace_mode,
            cmdl_args,
        )
    else:
        generate_simple_plots(
            metrics_result,
            analysis_result,
            report,
            trace_list,
            trace_processes,
            trace_tasks,
            trace_threads,
            trace_mode,
            cmdl_args,
        )

