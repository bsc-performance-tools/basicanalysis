#!/usr/bin/env python3

"""Shared pipeline helpers for BasicAnalysis."""

from __future__ import print_function, division

import io
import subprocess
from collections import OrderedDict
from contextlib import redirect_stdout

import hybridmetrics
import plots
import reportdata
from report import build_analysis_context, build_report_model
import html_to_pdf
import os
from comparison import (
    get_programming_model,
    is_comparison_mode,
    print_comparison_info,
)

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
    print_omp_talp_metrics_csv,
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
    import comparisonreport
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

    # Traces with different programming models are always compared
    # with the hybrid metrics, which cover every MPI-based model.
    comparison = is_comparison_mode(trace_list, trace_mode)

    if comparison and cmdl_args.metrics != 'hybrid':
        print("==INFO== Traces use different programming models: "
              "hybrid metrics are used for the comparison.")

    if (cmdl_args.metrics == 'hybrid' and trace_metrics > 0) or comparison:
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
            scaling_info,
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
            "scaling_info": scaling_info,
        }


    (mod_factors, 
    mod_factors_scale_plus_io, 
    other_metrics, 
    omp_talp_factors,
    scaling_info,
    ) = compute_model_factors(
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
        "omp_talp_factors": omp_talp_factors,
        "scaling_info": scaling_info,
    }

def print_scaling_info(scaling_info):
    """Print the scaling model used by the analysis."""

    if (
        scaling_info is None
        or not scaling_info.has_scaling_analysis
    ):
        return

    detected = (
        scaling_info.detected.capitalize()
        if scaling_info.detected
        else "Non-Avail"
    )

    selected = scaling_info.selected.capitalize()

    if scaling_info.selection_mode == "auto":
        selection = "Automatic"
    elif scaling_info.selection_mode == "manual":
        selection = "Manual"
    else:
        selection = "Implicit"

    ##print("")
    print("Scaling model:")
    print("  Detected scaling : {}".format(detected))
    print("  Scaling used     : {}".format(selected))
    print("  Selection        : {}".format(selection))
    print("")

def generate_reports(metrics_result, analysis_result, trace_list, trace_processes,
                     trace_tasks, trace_threads, trace_mode, cmdl_args):
    """Generate tables and CSV files."""
    raw_data = analysis_result["raw_data"]

    scaling_info = metrics_result.get("scaling_info")
    print_scaling_info(scaling_info)    

    comparison = is_comparison_mode(trace_list, trace_mode)
    if comparison:
        print_comparison_info(trace_list, trace_mode)

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
            other_metrics,
            trace_list,
            trace_processes,
            trace_tasks,
            trace_threads,
            trace_mode,
            raw_data,
        )

        hybridmetrics.print_other_metrics_csv(other_metrics, trace_list, trace_processes)
        
        is_mpi_gpu = trace_mode[trace_list[0]] in (
            "Detailed+MPI+CUDA",
            "Detailed+MPI+HIP",
        )

        if comparison:
            hybridmetrics.print_comparison_table(
                mod_factors,
                hybrid_factors,
                device_factors,
                host_factors,
                other_metrics,
                trace_list,
                trace_processes,
                trace_tasks,
                trace_threads,
                trace_mode,
                raw_data,
            )
        elif (cmdl_args.pop_model_to_apply == 'talp') and is_mpi_gpu:
            hybridmetrics.print_talp_metrics_csv(
                device_factors,
                host_factors,
                trace_list,
                trace_processes,
                trace_tasks,
                trace_threads,
                trace_mode,
                raw_data,
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
                mod_factors,
                hybrid_factors,
                hyb_comm_omp_factors,
                trace_list,
                trace_processes,
                trace_tasks,
                trace_threads,
                trace_mode,
                raw_data,
                cmdl_args,
            )

        hybridmetrics.print_mod_factors_csv(mod_factors, hybrid_factors, trace_list, trace_processes,trace_mode)

        if comparison:
            hybridmetrics.print_comparison_csv(
                mod_factors,
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

        if any(
            trace_mode[trace] == "Detailed+MPI+OpenMP"
            for trace in trace_list
        ):
            hybridmetrics.print_omp_talp_metrics_csv(
                omp_talp_factors,
                trace_list,
                trace_processes,
                trace_tasks,
                trace_threads,
                trace_mode
            )
        
        return

    mod_factors = metrics_result["mod_factors"]
    mod_factors_scale_plus_io = metrics_result["mod_factors_scale_plus_io"]
    other_metrics = metrics_result["other_metrics"]
    omp_talp_factors = metrics_result["omp_talp_factors"]


    print_other_metrics_table(other_metrics, trace_list, trace_processes)
    print_other_metrics_csv(other_metrics, trace_list, trace_processes)
    print_mod_factors_table(mod_factors, other_metrics, mod_factors_scale_plus_io, trace_list, trace_processes, trace_mode)
    print_mod_factors_csv(mod_factors, trace_list, trace_processes)

    if any(
        trace_mode[trace] == "Detailed+OpenMP"
        for trace in trace_list
    ):
        print_omp_talp_metrics_csv(
            omp_talp_factors,
            trace_list,
            trace_processes
        )
    
    print_efficiency_table(mod_factors, trace_list, trace_processes, trace_tasks,trace_threads)


def can_plot_tables():
    """Check whether matplotlib-based table plotting is available."""
    return not (error_import_numpy or error_import_pandas or error_import_matplotlib or error_import_seaborn)


def can_plot_lineal():
    """Check whether line plotting is available."""
    return not (error_import_numpy or error_import_scipy)


def generate_hybrid_plots(metrics_result, analysis_result, report,
                            report_model, trace_list, trace_processes,
                            trace_tasks, trace_threads,trace_mode,
                            cmdl_args):
    """Generate plots for hybrid metrics."""
    raw_data = analysis_result["raw_data"]
    mod_factors = metrics_result["mod_factors"]
    hybrid_factors = metrics_result["hybrid_factors"]

    # Efficiency-table, model-factor and speedup plots assume a single
    # programming model. They are not produced when comparing models.
    comparison = is_comparison_mode(trace_list, trace_mode)
    if comparison:
        print('Comparison of programming models: efficiency-table and '
              'scaling plots are not generated.')

    error_plot_table = False
    if not can_plot_tables():
        print('Numpy/Pandas/Matplotlib/Seaborn modules not available. '
              'Skipping efficiency table plotting with python.')
        if len(trace_list) > 1 and not comparison:
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

    is_mpi_gpu = trace_mode[trace_list[0]] in (
        "Detailed+MPI+CUDA",
        "Detailed+MPI+HIP",
    )    

    if not error_plot_table:
        if comparison:
            pass  # Efficiency-table plots assume a single programming model.
        elif (cmdl_args.pop_model_to_apply == 'talp') and is_mpi_gpu:
            hybridmetrics.plots_talp_efficiency_table_matplot(
                trace_list, trace_processes, trace_tasks, trace_threads, trace_mode, raw_data, cmdl_args
            )
        else:
            hybridmetrics.plots_efficiency_table_matplot(
                trace_list, trace_processes, trace_tasks, trace_threads, trace_mode, cmdl_args
            )

        if not error_import_interactiveplots and comparison:
            comparisonreport.plot_comparison_interactive_report(
                metrics_result,
                report,
                report_model,
                trace_list,
                trace_mode,
                build_model_group_reports(
                    analysis_result,
                    trace_list,
                    trace_processes,
                    trace_tasks,
                    trace_threads,
                    trace_mode,
                    cmdl_args,
                ),
            )
        elif not error_import_interactiveplots:           
            interactiveplots.plot_basicanalysis_interactive_report(
                metrics_result,
                analysis_result,
                report,
                report_model,
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

        if len(trace_list) > 1 and not comparison:
            if cmdl_args.pop_model_to_apply == 'classic':
                hybridmetrics.plots_modelfactors_matplot(
                    trace_list, trace_processes, trace_tasks, trace_threads, trace_mode, cmdl_args
                )
            hybridmetrics.plots_speedup_matplot(
                trace_list, trace_processes, trace_tasks, trace_threads, trace_mode, raw_data, cmdl_args
            )

    error_plot_lineal = False
    if not can_plot_lineal():
        print('Scipy/NumPy module not available. Skipping lineal plotting.')
        error_plot_lineal = True

    if not error_plot_lineal:
        if (len(trace_list) > 1 and not comparison
                and cmdl_args.pop_model_to_apply == 'classic'):
            plots.plot_hybrid_metrics(
                mod_factors,
                hybrid_factors,
                trace_list,
                trace_processes,
                trace_tasks,
                trace_threads,
                trace_mode,
                raw_data,
                cmdl_args,
            )
    if len(trace_list) == 1 and (cmdl_args.pop_model_to_apply == 'classic'):
        subprocess.check_output(["rm", "efficiency_table_global.gp"])
        subprocess.check_output(["rm", "efficiency_table_hybrid.gp"])


def generate_simple_plots(metrics_result, analysis_result, report,
                            report_model, trace_list, trace_processes,
                            trace_tasks, trace_threads, trace_mode,
                            cmdl_args):
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
            interactiveplots.plot_basicanalysis_interactive_report(
                metrics_result,
                analysis_result,
                report,
                report_model,
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


def build_report_models(metrics_result, analysis_result, trace_list,
                        trace_processes, trace_tasks, trace_threads,
                        trace_mode, cmdl_args):
    """Build the report data, analysis context and semantic report model."""

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

    # Phase 2: build and validate the new semantic report model in parallel.
    # The existing report dictionary continues to feed interactiveplots.py, so
    # report output and behavior remain unchanged during this integration step.
    analysis_context = build_analysis_context(
        report,
        raw_data=analysis_result.get("raw_data", {}),
        scaling_info=metrics_result.get("scaling_info"),
    )

    report_model = build_report_model(analysis_context)
    report_model.validate()

    return report, analysis_context, report_model


def build_model_group_reports(analysis_result, trace_list, trace_processes,
                              trace_tasks, trace_threads, trace_mode,
                              cmdl_args):
    """Build the standard interactive report of each programming model.

    Used when comparing programming models. The traces of each model are
    analyzed as an independent set: metrics (including scaling between
    traces of the same model) are recomputed for the group, so each report
    matches a standalone analysis of those traces.

    Returns:
        list of {"model", "traces", "html"}, in trace order.
    """
    groups = OrderedDict()
    for trace in trace_list:
        groups.setdefault(
            get_programming_model(trace_mode[trace]), []
        ).append(trace)

    model_reports = []

    for model, group in groups.items():
        # Group metrics are not printed: the terminal and CSV outputs
        # describe the comparison of all traces.
        with redirect_stdout(io.StringIO()):
            group_metrics = compute_metrics(
                analysis_result,
                group,
                trace_processes,
                trace_tasks,
                trace_threads,
                trace_mode,
                cmdl_args,
                count_hybrid_traces(group, trace_mode),
            )

            group_report, _, group_report_model = build_report_models(
                group_metrics,
                analysis_result,
                group,
                trace_processes,
                trace_tasks,
                trace_threads,
                trace_mode,
                cmdl_args,
            )

            group_html = interactiveplots.build_basicanalysis_interactive_report_html(
                group_metrics,
                analysis_result,
                group_report,
                group_report_model,
                group,
                trace_processes,
                trace_tasks,
                trace_threads,
                trace_mode,
                cmdl_args,
            )

        model_reports.append({
            "model": model,
            "traces": group,
            "html": group_html,
        })

    return model_reports


def generate_plots(
    metrics_result,
    analysis_result,
    trace_list,
    trace_processes,
    trace_tasks,
    trace_threads,
    trace_mode,
    cmdl_args,
):
    """Generate all plots."""

    report, analysis_context, report_model = build_report_models(
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

        for trace_info in analysis_context.traces:
            print(
                "==DEBUG== Semantic mapping:",
                trace_info.trace_id,
                trace_info.mapping,
            )

        for trace_info in report["traces"]:
            print(
                "==DEBUG== Report mapping:",
                trace_info["id"],
                trace_info.get("mapping"),
            )

        print("==DEBUG== Report resources:", len(report["resources"]))
        print(
            "==DEBUG== Semantic report sections:",
            len(list(report_model.iter_sections())),
        )

        # Temporary Phase 3.1 integration validation
        overview = report_model.get_section("overview")

        mapping_section = report_model.get_section(
            "execution-mapping"
        )

        if mapping_section is not None:
            print("==DEBUG== Execution Mapping section:")

            for item in mapping_section.payload:
                print(
                    "==DEBUG== ",
                    item.trace_id,
                    item.mapping,
                )

        print("\n==DEBUG== Overview section")
        print("==DEBUG== Section ID:", overview.section_id)
        print("==DEBUG== Section type:", overview.section_type)

        print("==DEBUG== Overview children:")
        for child in overview.children:
            print(
                "==DEBUG==  ",
                child.section_id,
                child.section_type,
            )

        print("==DEBUG== General metrics:")
        for metric in overview.payload.general_metrics:
            print(
                "==DEBUG==  ",
                metric.metric_id,
                [
                    (value.trace_id, value.value)
                    for value in metric.values
                ],
            )

        scalability = report_model.get_section(
            "scalability-analysis"
        )

        if scalability is not None:
            scaling_info = scalability.payload.scaling_info

            print("==DEBUG== Scaling detected:", scaling_info.detected)
            print("==DEBUG== Scaling selected:", scaling_info.selected)
            print(
                "==DEBUG== Scaling selection mode:",
                scaling_info.selection_mode,
            )
            print(
                "==DEBUG== Scaling overridden:",
                scaling_info.overridden,
            )


    if metrics_result["kind"] == "hybrid":
        generate_hybrid_plots(
            metrics_result,
            analysis_result,
            report,
            report_model,
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
            report_model,
            trace_list,
            trace_processes,
            trace_tasks,
            trace_threads,
            trace_mode,
            cmdl_args,
        )
    

