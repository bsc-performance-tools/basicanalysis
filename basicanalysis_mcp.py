#!/usr/bin/env python3

"""MCP server of BasicAnalysis (prototype).

Phase 2 of doc/design/ai_assistance.rst: lets an AI assistant that supports
the Model Context Protocol (Claude Code, Claude Desktop, other MCP clients)
read BasicAnalysis results, explain the metrics, and start analyses.

Requires the MCP Python SDK (pip install --user "mcp>=2"). Run with the
folders the assistant may use:

    BA_ROOTS=/path/to/results:/path/to/traces python3 basicanalysis_mcp.py

The server talks to the client over stdio; the client starts it. It only runs
modelfactors.py, with validated options, on traces inside BA_ROOTS.
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import functools  # noqa: E402

from mcp.server import MCPServer  # noqa: E402
from mcp.server.mcpserver.exceptions import ToolError  # noqa: E402

import basicanalysis_api as api  # noqa: E402

INSTRUCTIONS = """\
BasicAnalysis computes the POP efficiency metrics of parallel applications
from Paraver traces. Efficiencies are percentages (100% is ideal) organized as
a multiplicative tree: a parent is the product of its children. Scalability
metrics are relative to the first trace. Values are classified as Critical,
Attention, or Good with the thresholds of each metric (60% and 85% by default).

To diagnose an analysis: list_runs to find it, list_issues to see the metrics
below the thresholds, get_metrics for the full tables, and explain_metric for
the definition, causes, and next steps of a metric. Base the explanations on
those definitions and cite the values. analyze starts a new analysis of
traces; follow it with job_status.
"""

server = MCPServer(
    name="basicanalysis",
    title="BasicAnalysis",
    description="POP efficiency metrics of parallel applications from "
                "Paraver traces (BSC).",
    instructions=INSTRUCTIONS,
    version="prototype",
)


def expected_errors(function):
    """Report invalid arguments (paths outside BA_ROOTS, unknown metrics,
    bad options) to the assistant with their message."""
    @functools.wraps(function)
    def wrapper(*args, **kwargs):
        try:
            return function(*args, **kwargs)
        except (ValueError, OSError) as error:
            raise ToolError(str(error))
    return wrapper


@server.tool()
@expected_errors
def list_runs(folder: str = ".") -> list:
    """List the BasicAnalysis results (folders with modelfactors.csv) under
    a folder: their traces, trace mode, and available tables."""
    return api.list_runs(folder)


@server.tool()
@expected_errors
def get_metrics(run: str, table: str = "all") -> dict:
    """Metric tables of a BasicAnalysis result folder. table is application
    (Global, Parallel, Hybrid, MPI, inner runtime, Computation scalability),
    heterogeneous (Host and Device metrics of GPU applications), general
    (elapsed time, Speedup, IPC, frequency, I/O), or all. Each metric has its
    tree level, key, value per trace, and Critical/Attention/Good status."""
    return api.get_metrics(run, table)


@server.tool()
@expected_errors
def list_issues(run: str, include_attention: bool = True) -> dict:
    """Efficiency metrics below the thresholds in a BasicAnalysis result,
    ordered from the top of the tree and worst value first: the starting
    point of the diagnosis."""
    return api.list_issues(run, include_attention)


@server.tool()
@expected_errors
def explain_metric(metric: str) -> dict:
    """Definition, formula, interpretation, possible causes, next steps, and
    thresholds of a metric, by key (e.g. dev_orches_eff) or name (e.g.
    "Device Orchestration efficiency")."""
    return api.explain_metric(metric)


@server.tool()
@expected_errors
def analyze(traces: list, output: str, workload: str = "",
            host_workload: str = "", device_workload: str = "",
            scaling: str = "auto", simulate: bool = False,
            keep_order: bool = False) -> dict:
    """Start BasicAnalysis (modelfactors.py) on Paraver traces (.prv),
    writing the results into the folder output. Optional: workload,
    host_workload, device_workload (numbers separated by commas, one per
    trace), scaling (auto, weak, strong), simulate (Dimemas; slow),
    keep_order (keep the order of the traces; the first is the reference).
    Returns a job id: follow it with job_status."""
    return api.analyze(traces, output, workload or None, host_workload or None,
                       device_workload or None, scaling, simulate, keep_order)


@server.tool()
@expected_errors
def job_status(job: str) -> dict:
    """State of an analysis started with analyze (running, done, failed) and
    the end of its output. When done, use list_issues on its folder."""
    return api.status(job)


@server.resource("basicanalysis://definitions",
                 name="definitions",
                 description="Metric knowledge of BasicAnalysis "
                             "(metrics/definitions.yaml)",
                 mime_type="text/yaml")
def definitions() -> str:
    with open(os.path.join(HERE, "metrics", "definitions.yaml")) as handle:
        return handle.read()


if __name__ == "__main__":
    server.run("stdio")
