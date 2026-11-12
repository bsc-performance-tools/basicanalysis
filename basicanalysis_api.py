#!/usr/bin/env python3

"""Functions to use BasicAnalysis results from other programs (prototype).

Phase 2 of doc/design/ai_assistance.rst: the functions behind the MCP server
(basicanalysis_mcp.py). They read the folders written by modelfactors.py
(modelfactors.csv, talp_metrics.csv, other_metrics.csv, traces_metadata.txt)
and the metric knowledge of metrics/definitions.yaml, and can start an
analysis. They return plain data (dicts and lists), not HTML.

Access is limited to the folders given in BA_ROOTS (separated by ':'), or to
the current directory when it is not set.
"""

from __future__ import print_function, division

import csv
import os
import re
import subprocess
import sys
import time
import uuid

from metrics import get_default_provider

HERE = os.path.dirname(os.path.abspath(__file__))

# Tables written by modelfactors.py, by file name.
TABLES = {
    "application": ("modelfactors.csv", "Application and runtime model "
                    "(Global, Parallel, Hybrid, MPI, inner runtime, "
                    "Computation scalability)"),
    "heterogeneous": ("talp_metrics.csv", "Heterogeneous Model: Host and "
                      "Device metrics (GPU applications)"),
    "general": ("other_metrics.csv", "General metrics: elapsed time, "
                "Speedup, Efficiency, IPC, frequency, I/O"),
}

_JOBS = {}


# ----------------------------------------------------------------------
# Paths
# ----------------------------------------------------------------------

def roots():
    """Folders the functions may read and write."""
    value = os.environ.get("BA_ROOTS")
    paths = value.split(os.pathsep) if value else [os.getcwd()]
    return [os.path.realpath(os.path.expanduser(p)) for p in paths if p]


def checked_path(path):
    """Absolute path inside one of the roots, or ValueError."""
    real = os.path.realpath(os.path.expanduser(path))
    for root in roots():
        if real == root or real.startswith(root + os.sep):
            return real
    raise ValueError("Path outside the allowed folders ({}): {}".format(
        ", ".join(roots()), path))


# ----------------------------------------------------------------------
# Metric knowledge
# ----------------------------------------------------------------------

def _normalize(label):
    label = re.sub(r"^[\s\-=]+", "", str(label))
    return " ".join(label.lower().split())


def _knowledge_index():
    """Normalized metric names (and keys) -> metric key."""
    provider = get_default_provider()
    index = {}
    for key, entry in provider.knowledge_base.metrics.items():
        names = [key, entry.get("name", ""), entry.get("short_name", "")]
        for name in names:
            if name:
                index.setdefault(_normalize(name), key)
    # Labels of the standard output that differ from the names.
    index.setdefault("serialization efficiency", "serial_eff")
    index.setdefault("transfer efficiency", "transfer_eff")
    index.setdefault("hybrid parallel efficiency", "hybrid_eff")
    return index


# Contribution of the inner runtime of the Hybrid model, e.g. "CUDA Load
# balance": a template metric resolved with the runtime name.
_RUNTIME_METRIC = re.compile(
    r"^(openmp|cuda|hip|pthreads|ompss)\s+(parallel efficiency|load balance|"
    r"communication efficiency)$")
_RUNTIME_KEYS = {"parallel efficiency": "runtime_parallel_eff",
                 "load balance": "runtime_load_balance",
                 "communication efficiency": "runtime_comm_eff"}
_RUNTIME_NAMES = {"openmp": "OpenMP", "cuda": "CUDA", "hip": "HIP",
                  "pthreads": "Pthreads", "ompss": "OmpSs"}


def _resolve(label):
    """(metric key, runtime) of a table label or key; key None if unknown."""
    normalized = _normalize(label)
    match = _RUNTIME_METRIC.match(normalized)
    if match:
        return _RUNTIME_KEYS[match.group(2)], _RUNTIME_NAMES[match.group(1)]
    return _knowledge_index().get(normalized), None


def metric_key(label):
    """Metric key of a table label, or None."""
    return _resolve(label)[0]


def _knowledge(key, runtime=None):
    provider = get_default_provider()
    if runtime:
        return provider.get(key, runtime=runtime,
                            runtime_family=runtime.lower())
    return provider.get(key)


def explain_metric(metric):
    """Definition, formula, interpretation, causes, and next steps of a
    metric, given by key (e.g. "dev_orches_eff") or name."""
    key, runtime = _resolve(metric)
    try:
        knowledge = _knowledge(key or metric, runtime)
    except Exception:
        candidates = sorted(set(_knowledge_index().values()))
        raise ValueError("Unknown metric {!r}. Known metrics: {}".format(
            metric, ", ".join(candidates)))
    return {
        "key": knowledge.id,
        "name": knowledge.name,
        "definition": " ".join(knowledge.definition.split()),
        "formula": (knowledge.formula or {}).get("text", ""),
        "interpretation": {
            "low": knowledge.interpretation_low,
            "high": knowledge.interpretation_high,
            "above_100": knowledge.interpretation_above_100,
        },
        "possible_causes": list(knowledge.typical_causes),
        "next_steps": list(knowledge.next_steps),
        "children": list(knowledge.children),
        "thresholds": {
            "critical_below": knowledge.thresholds.critical,
            "good_from": knowledge.thresholds.attention,
        },
    }


def _thresholds(key, runtime=None):
    if key:
        try:
            return _knowledge(key, runtime).thresholds
        except Exception:
            pass
    return get_default_provider().default_thresholds


def _status(value, thresholds):
    if value > thresholds.reference:
        return "above reference"
    if value < thresholds.critical:
        return "Critical"
    if value < thresholds.attention:
        return "Attention"
    return "Good"


# ----------------------------------------------------------------------
# Results
# ----------------------------------------------------------------------

def _read_csv(path):
    with open(path, newline="") as handle:
        sample = handle.read(2048)
        handle.seek(0)
        delimiter = ";" if sample.count(";") > sample.count(",") else ","
        return [row for row in csv.reader(handle, delimiter=delimiter) if row]


def _number(text):
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def _traces(folder):
    """Trace names, processes and mode from traces_metadata.txt."""
    path = os.path.join(folder, "traces_metadata.txt")
    traces = []
    if os.path.exists(path):
        with open(path) as handle:
            lines = handle.readlines()
        for line in lines:
            match = re.match(r"\[(\d+)\] (.*?), (.*?) processes,.*, (\S+) mode",
                             line.strip())
            if match:
                traces.append({"id": "T" + match.group(1),
                               "trace": os.path.basename(match.group(2)),
                               "processes": match.group(3),
                               "mode": match.group(4)})
    return traces


def list_runs(folder="."):
    """BasicAnalysis results found in a folder and its subfolders (3 levels)."""
    base = checked_path(folder)
    runs = []
    for current, dirs, files in os.walk(base):
        depth = current[len(base):].count(os.sep)
        dirs[:] = [d for d in dirs if d != "scratch_out_basicanalysis"
                   and not d.startswith(".")]
        if depth >= 3:
            dirs[:] = []
        if "modelfactors.csv" in files:
            runs.append({
                "run": current,
                "traces": _traces(current),
                "tables": [name for name, (file_name, _) in TABLES.items()
                           if file_name in files],
                "report": "basicanalysis_interactive_report.html" in files,
            })
    return runs


def get_metrics(run, table="all"):
    """Metric tables of a run: per metric, its tree level, key, value per
    trace, and Critical/Attention/Good status. table: application,
    heterogeneous, general, or all."""
    folder = checked_path(run)
    names = list(TABLES) if table == "all" else [table]
    result = {"run": folder, "traces": _traces(folder), "tables": {}}
    for name in names:
        if name not in TABLES:
            raise ValueError("Unknown table {!r}: use one of {}".format(
                name, ", ".join(list(TABLES) + ["all"])))
        file_name, description = TABLES[name]
        path = os.path.join(folder, file_name)
        if not os.path.exists(path):
            continue
        rows = _read_csv(path)
        columns = [c.strip() for c in rows[0][1:]]
        metrics = []
        for row in rows[1:]:
            label = row[0]
            if not label.strip() or label.startswith("#") or len(row) < 2:
                continue
            level = len(label) - len(label.lstrip(" -=")) if label else 0
            key, runtime = _resolve(label)
            values = [_number(v) for v in row[1:]]
            entry = {"metric": label.strip(" -=\"").strip(),
                     "key": key,
                     "level": 0 if level == 0 else 1 + level // 4,
                     "values": [v if v is not None else c.strip()
                                for v, c in zip(values, row[1:])]}
            efficiency = name != "general" and key is not None
            if efficiency:
                thresholds = _thresholds(key, runtime)
                entry["status"] = [
                    _status(v, thresholds) if v is not None else None
                    for v in values]
            metrics.append(entry)
        result["tables"][name] = {"description": description,
                                  "columns": columns, "metrics": metrics}
    return result


def list_issues(run, include_attention=True):
    """Efficiency metrics below the thresholds in any trace, from the top of
    the tree down, worst first: where to start the diagnosis."""
    data = get_metrics(run)
    issues = []
    for name, table in data["tables"].items():
        for metric in table["metrics"]:
            statuses = metric.get("status") or []
            bad = [i for i, s in enumerate(statuses)
                   if s == "Critical" or (include_attention and s == "Attention")]
            if not bad:
                continue
            worst = min(metric["values"][i] for i in bad)
            issues.append({
                "table": name,
                "metric": metric["metric"],
                "key": metric["key"],
                "level": metric["level"],
                "worst_value": worst,
                "per_trace": dict(zip(table["columns"],
                                      zip(metric["values"], statuses))),
            })
    issues.sort(key=lambda issue: (issue["level"], issue["worst_value"]))
    return {"run": data["run"], "traces": data["traces"], "issues": issues}


# ----------------------------------------------------------------------
# Running BasicAnalysis
# ----------------------------------------------------------------------

_LIST = re.compile(r"^[0-9.eE+-]+(,[0-9.eE+-]+)*$")


def analyze(traces, output, workload=None, host_workload=None,
            device_workload=None, scaling="auto", simulate=False,
            keep_order=False):
    """Start modelfactors.py on traces, writing into the folder output.
    Returns a job id; use status(job) to follow it."""
    if not traces:
        raise ValueError("No traces given.")
    trace_paths = [checked_path(t) for t in traces]
    for path in trace_paths:
        if not re.search(r"\.prv(\.gz)?$", path) or not os.path.exists(path):
            raise ValueError("Not a Paraver trace: {}".format(path))
    folder = checked_path(output)
    os.makedirs(folder, exist_ok=True)

    command = [sys.executable, os.path.join(HERE, "modelfactors.py")]
    for option, value in (("--workload", workload),
                          ("--host-workload", host_workload),
                          ("--device-workload", device_workload)):
        if value:
            if not _LIST.match(str(value)):
                raise ValueError("{} must be numbers separated by commas"
                                 .format(option))
            command += [option, str(value)]
    if scaling not in ("auto", "weak", "strong"):
        raise ValueError("scaling must be auto, weak, or strong")
    if scaling != "auto":
        command += ["-s", scaling]
    if not simulate:
        command.append("-skip-simul")
    if keep_order:
        command.append("--no-sort")
    command += trace_paths

    job = uuid.uuid4().hex[:8]
    log = open(os.path.join(folder, "mcp_job_{}.txt".format(job)), "w")
    process = subprocess.Popen(command, cwd=folder, stdout=log,
                               stderr=subprocess.STDOUT)
    _JOBS[job] = {"process": process, "folder": folder, "log": log.name,
                  "started": time.time(), "command": command}
    return {"job": job, "folder": folder}


def status(job):
    """State of an analysis started with analyze: running, done or failed,
    with the end of its output."""
    if job not in _JOBS:
        raise ValueError("Unknown job {!r}".format(job))
    entry = _JOBS[job]
    code = entry["process"].poll()
    state = "running" if code is None else ("done" if code == 0 else "failed")
    with open(entry["log"]) as handle:
        tail = handle.read()[-3000:]
    return {"job": job, "state": state, "exit_code": code,
            "folder": entry["folder"],
            "elapsed_s": round(time.time() - entry["started"], 1),
            "output_tail": tail}
