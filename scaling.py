#!/usr/bin/env python3

"""Scaling detection and selection utilities."""


import sys


# Execution domains of the Host/Device model with their own workload:
# (domain, option). The values of a workload option are sizes or ratios:
# the ratio of each trace is its value divided by that of the reference.
WORKLOAD_DOMAINS = (
    ("host", "--host-workload"),
    ("device", "--device-workload"),
)

DOMAINS = tuple(domain for domain, _option in WORKLOAD_DOMAINS)


def _option_attribute(option):
    return option.lstrip("-").replace("-", "_")


class ScalingInfo:
    """Stores information about the scaling model used in an analysis.

    Parameters
    ----------
    has_scaling_analysis : bool
        True when more than one execution trace is available and a scaling
        analysis can therefore be performed.

    detected : str or None
        Scaling type automatically detected from the execution measurements.
        Possible values are "strong", "weak", or None when scaling analysis
        is not applicable.

    selected : str
        Scaling type of the application level (the whole model in models
        with one execution domain; Speedup, Scaling Efficiency, and the
        application metrics in the Host/Device model). The value is
        "strong", "weak" or "workload". "workload" means that the
        scalability metrics are relative to the reference trace, scaled by
        the workload ratio of each trace instead of its resource ratio.

    selection_mode : str
        Indicates how the selected scaling type was obtained.
        Possible values are:
            - "auto": automatically detected.
            - "manual": explicitly selected by the user.
            - "workload": user-defined workload ratios.
            - "implicit": internal compatibility choice when scaling analysis
              is not applicable.

    overridden : bool
        True when the user explicitly selected a scaling type different from
        the automatically detected one.

    normalized_inst_ratio : float or None
        Average normalized useful-instruction ratio used by the detector.

    normalized_runtime_ratio : float or None
        Average normalized runtime ratio used by the detector.

    normalized_useful_avg_ratio : float or None
        Average normalized useful-computation ratio used by the detector.

    threshold : float
        Threshold used to classify each indicator as weak-scaling behavior.

    status_message : str or None
        Additional information describing the scaling-analysis status.

    workload_values : dict or None
        Workload value of each trace used at the application level, in
        workload mode: that of --workload or, in the Host/Device model
        without --workload, that of --device-workload.

    workload_ratios : dict or None
        Workload of each trace divided by the workload of the reference
        trace, for the application level.

    workload_option : str or None
        Option that gave the application workload.

    domain_workload_values, domain_workload_ratios, domain_workload_options
        : dict
        Per execution domain ("host", "device"), the workload values,
        ratios, and option given by the user with --host-workload or
        --device-workload.

    domain_modes : dict
        Scaling type of each execution domain of the Host/Device model when
        a workload is given: "workload" for a domain with its own workload
        or with the application workload (--workload), and otherwise the
        type forced with --scaling or detected from that domain only.

    domain_selection : dict
        How the scaling type of each domain was obtained: the workload
        option, "Manual (--scaling)", or "Automatic".

    domain_detection : dict
        Per domain detected from its own measurements, the detection
        (a ScalingInfo with the indicators).
    """

    def __init__(
        self,
        has_scaling_analysis,
        detected,
        selected,
        selection_mode,
        overridden,
        normalized_inst_ratio=None,
        normalized_runtime_ratio=None,
        normalized_useful_avg_ratio=None,
        threshold=0.9,
        status_message=None,
        workload_values=None,
        workload_ratios=None,
    ):
        self.has_scaling_analysis = has_scaling_analysis

        self.detected = detected
        self.selected = selected

        self.selection_mode = selection_mode
        self.overridden = overridden

        self.normalized_inst_ratio = normalized_inst_ratio
        self.normalized_runtime_ratio = normalized_runtime_ratio
        self.normalized_useful_avg_ratio = (
            normalized_useful_avg_ratio
        )

        self.threshold = threshold
        self.status_message = status_message

        self.workload_values = workload_values
        self.workload_ratios = workload_ratios
        self.workload_option = None
        self.domain_workload_values = {}
        self.domain_workload_ratios = {}
        self.domain_workload_options = {}
        self.domain_modes = {}
        self.domain_selection = {}
        self.domain_detection = {}

    def mode(self, domain=None):
        """Scaling type of an execution domain ("host" or "device"), or of
        the application level (domain None)."""
        return self.domain_modes.get(domain, self.selected)

    def work_ratio(self, trace, resource_ratio, domain=None):
        """Return the multiplier of the scalability formulas for a trace.

        It depends on the scaling type of the domain ("host", "device", or
        None for the application level):

            workload  the workload ratio of the domain when the user gave
                      one, and the application workload ratio otherwise;
            weak      the resource ratio of the metric (processes, host
                      threads, devices, ...);
            strong    1.
        """
        mode = self.mode(domain)

        if mode == "workload":
            ratios = self.domain_workload_ratios.get(domain)

            if ratios is not None:
                return ratios[trace]

            return self.workload_ratios[trace]

        if mode == "strong":
            return 1.0

        return resource_ratio

    def ratio_source(self, domain=None):
        """Text describing where the multiplier of a domain comes from."""
        mode = self.mode(domain)

        if mode == "workload":
            if domain in self.domain_workload_options:
                return self.domain_workload_options[domain]
            return self.workload_option

        if mode == "weak":
            return "weak scaling (resource ratio)"

        return "strong scaling (ratio 1)"


def _ratio(series, trace, reference, default):
    try:
        return float(series(trace)) / float(series(reference))
    except Exception:
        return default


def _detect(trace_list, instructions, units, runtime, useful_avg, eps):
    """Vote weak or strong scaling from per-trace measures.

    Each argument is a function trace -> value (instructions may be None).
    Returns (detected, normalized instruction, runtime, and useful-average
    ratios), averaged over the traces other than the reference.
    """
    normalized_inst_ratio = 0
    normalized_runtime_ratio = 0
    normalized_useful_avg_ratio = 0

    reference_trace = trace_list[0]

    for trace in trace_list:
        if instructions is None:
            inst_ratio = 0.0
        else:
            inst_ratio = _ratio(instructions, trace, reference_trace, 0.0)

        unit_ratio = _ratio(units, trace, reference_trace, float("nan"))
        runtime_ratio = _ratio(runtime, trace, reference_trace, float("nan"))
        # Not available (e.g. nsys2prv traces have no useful host time):
        # the indicator is NaN and does not vote.
        useful_avg_ratio = _ratio(
            useful_avg, trace, reference_trace, float("nan"))

        normalized_inst_ratio += inst_ratio / unit_ratio
        normalized_runtime_ratio += runtime_ratio
        normalized_useful_avg_ratio += useful_avg_ratio

    # Ignore the reference execution, whose normalized ratio is 1.0.
    others = len(trace_list) - 1
    normalized_inst_ratio = (normalized_inst_ratio - 1) / others
    normalized_runtime_ratio = (normalized_runtime_ratio - 1) / others
    normalized_useful_avg_ratio = (normalized_useful_avg_ratio - 1) / others

    weak_scaling_indicators = 0

    if normalized_inst_ratio > eps:
        weak_scaling_indicators += 1

    if normalized_runtime_ratio > eps:
        weak_scaling_indicators += 1

    if normalized_useful_avg_ratio > eps:
        weak_scaling_indicators += 1

    # At least two of the three indicators must identify weak scaling.
    detected = "weak" if weak_scaling_indicators > 1 else "strong"

    return (
        detected,
        normalized_inst_ratio,
        normalized_runtime_ratio,
        normalized_useful_avg_ratio,
    )


def _detection_info(trace_list, instructions, units, runtime, useful_avg,
                    eps):
    detected, inst, rt, avg = _detect(
        trace_list, instructions, units, runtime, useful_avg, eps)

    return ScalingInfo(
        has_scaling_analysis=True,
        detected=detected,
        selected=detected,
        selection_mode="auto",
        overridden=False,
        normalized_inst_ratio=inst,
        normalized_runtime_ratio=rt,
        normalized_useful_avg_ratio=avg,
        threshold=eps,
    )


def _compute_scaling_detection(
    raw_data,
    trace_list,
    trace_processes,
    eps=0.9,
):
    """Detect weak or strong scaling from execution measurements.

    This function implements the automatic scaling-detection algorithm
    used by BasicAnalysis.

    Three indicators are evaluated:

        1. Useful-instruction growth normalized by process growth.
        2. Runtime evolution.
        3. Average useful-computation evolution.

    Each indicator whose normalized value is greater than ``eps`` votes for
    weak scaling. If at least two of the three indicators vote for weak
    scaling, the experiment is classified as weak scaling. Otherwise it is
    classified as strong scaling.

    This function performs only the automatic detection. It does not apply
    command-line scaling overrides.
    """

    # A single execution is not a scaling experiment.
    #
    # Historically BasicAnalysis used "strong" internally for this case.
    # We keep that compatibility choice in `selected`, while explicitly
    # marking that no scaling analysis can actually be performed.
    if len(trace_list) == 1:
        return ScalingInfo(
            has_scaling_analysis=False,
            detected=None,
            selected="strong",
            selection_mode="implicit",
            overridden=False,
            threshold=eps,
            status_message="Single execution",
        )

    return _detection_info(
        trace_list,
        instructions=lambda trace: raw_data["useful_ins"][trace],
        units=lambda trace: trace_processes[trace],
        runtime=lambda trace: raw_data["runtime"][trace],
        useful_avg=lambda trace: raw_data["useful_avg"][trace],
        eps=eps,
    )


def _per_unit(raw_data, total_key, count_key):
    def useful_avg(trace):
        return float(raw_data[total_key][trace]) / float(
            raw_data[count_key][trace])
    return useful_avg


def detect_domain_scaling(raw_data, trace_list, domain, eps=0.9):
    """Detect weak or strong scaling of one execution domain of the
    Host/Device model from its own measurements, with the same indicators
    and votes as the application detection:

        host    Host useful instructions per Host thread, runtime, and
                average useful time of the Host threads;
        device  runtime and average useful time of the devices (the
                devices have no instruction counters).
    """
    if domain == "host":
        return _detection_info(
            trace_list,
            instructions=lambda trace: raw_data["useful_ins"][trace],
            units=lambda trace: raw_data["count_host_threads"][trace],
            runtime=lambda trace: raw_data["runtime"][trace],
            useful_avg=_per_unit(raw_data, "useful_host", "count_host_threads"),
            eps=eps,
        )

    return _detection_info(
        trace_list,
        instructions=None,
        units=lambda trace: raw_data["count_devices"][trace],
        runtime=lambda trace: raw_data["runtime"][trace],
        useful_avg=_per_unit(raw_data, "useful_device", "count_devices"),
        eps=eps,
    )



def _apply_scaling_option(scaling_info, cmdl_args):
    """Apply --scaling (auto, weak, strong) to a detection."""

    if cmdl_args.scaling == "auto":
        scaling_info.selected = scaling_info.detected
        scaling_info.selection_mode = "auto"
        scaling_info.overridden = False

        if cmdl_args.debug:
            print(
                "==DEBUG== Detected "
                + scaling_info.detected
                + " scaling."
            )
            print("")

        return scaling_info

    if cmdl_args.scaling in ("weak", "strong"):
        forced = cmdl_args.scaling
        other = "strong" if forced == "weak" else "weak"
        scaling_info.selected = forced
        scaling_info.selection_mode = "manual"

        if scaling_info.detected == other:
            scaling_info.overridden = True

            print(
                "==Warning== Scaling set to {} scaling "
                "but detected {} scaling.".format(forced, other)
            )
            print("")
        else:
            scaling_info.overridden = False

        return scaling_info

    print(
        "==Error== reached undefined control flow state."
    )
    sys.exit(1)


def get_scaling_info(
    raw_data,
    trace_list,
    trace_processes,
    cmdl_args,
    has_domains=False,
):
    """Return complete information about scaling detection and selection.

    The automatic detector first determines whether the analyzed executions
    resemble strong or weak scaling.

    Without workloads, the command-line scaling option is applied:

        auto
            Use the automatically detected scaling type.

        weak
            Force weak scaling.

        strong
            Force strong scaling.

    When the user-selected scaling differs from the automatically detected
    scaling, ``overridden`` is set to True and the same warning historically
    produced by BasicAnalysis is emitted.

    With workloads (--workload, --host-workload, --device-workload; see
    _set_workloads), the scalability metrics use the workload ratio of each
    trace relative to the reference trace. ``has_domains`` tells whether the
    execution model has Host and Device domains (Host/Device model); in
    other models the Host and Device workloads are ignored with a warning.

    For a single trace, scaling analysis is marked as not applicable.
    The selected value remains "strong" internally to preserve the historical
    behavior expected by the metric computation.
    """

    scaling_info = _compute_scaling_detection(
        raw_data=raw_data,
        trace_list=trace_list,
        trace_processes=trace_processes,
    )

    # Preserve historical single-trace behavior.
    #
    # The old get_scaling_type() immediately returned "strong" before
    # inspecting cmdl_args.scaling. Therefore no manual override is applied
    # for a single execution.
    if not scaling_info.has_scaling_analysis:
        return scaling_info

    workload_map = getattr(cmdl_args, "workload_map", None)
    domain_maps = dict(getattr(cmdl_args, "domain_workload_maps", None) or {})

    if domain_maps and not has_domains:
        print(
            "==Warning== {} ignored: the execution model has no Host/Device "
            "domains.".format(
                ", ".join(option for option, _ in domain_maps.values()))
        )
        print("")
        domain_maps = {}

    if not workload_map and not domain_maps:
        return _apply_scaling_option(scaling_info, cmdl_args)

    return _set_workloads(
        scaling_info, raw_data, trace_list, cmdl_args, workload_map,
        domain_maps, has_domains)


def _set_workloads(scaling_info, raw_data, trace_list, cmdl_args,
                   workload_map, domain_maps, has_domains):
    """Scaling of each level when the user gives workloads.

    Application level (Speedup, Scaling Efficiency, and every metric in
    models with one domain): the --workload ratio; without it, the
    --device-workload ratio; without both, the detected or forced scaling.

    Host and Device domains of the Host/Device model: their own workload;
    without it, the --workload ratio; without both, the scaling forced with
    --scaling, or detected from the measurements of that domain only.
    """
    for domain, (option, values) in domain_maps.items():
        (
            scaling_info.domain_workload_values[domain],
            scaling_info.domain_workload_ratios[domain],
        ) = _workload_ratios(values, trace_list)
        scaling_info.domain_workload_options[domain] = option

    if workload_map:
        app_option = cmdl_args.workload_option
        app_values, app_ratios = _workload_ratios(workload_map, trace_list)
    elif "device" in domain_maps:
        app_option = scaling_info.domain_workload_options["device"]
        app_values = scaling_info.domain_workload_values["device"]
        app_ratios = scaling_info.domain_workload_ratios["device"]
    else:
        app_option = None

    if app_option is not None:
        scaling_info.selected = "workload"
        scaling_info.selection_mode = "workload"
        scaling_info.overridden = False
        # The user gave the workload: the detection is not used.
        scaling_info.detected = None
        scaling_info.workload_values = app_values
        scaling_info.workload_ratios = app_ratios
        scaling_info.workload_option = app_option
    else:
        _apply_scaling_option(scaling_info, cmdl_args)

    if not has_domains:
        return scaling_info

    for domain in DOMAINS:
        if domain in domain_maps:
            mode = "workload"
            selection = "Manual, " + scaling_info.domain_workload_options[
                domain]
        elif workload_map:
            mode = "workload"
            selection = "Manual, " + cmdl_args.workload_option
        elif cmdl_args.scaling in ("weak", "strong"):
            mode = cmdl_args.scaling
            selection = "Manual, --scaling"
        else:
            detection = detect_domain_scaling(raw_data, trace_list, domain)
            scaling_info.domain_detection[domain] = detection
            mode = detection.detected
            selection = "Automatic, {} measurements only".format(
                domain.capitalize())

        scaling_info.domain_modes[domain] = mode
        scaling_info.domain_selection[domain] = selection

    return scaling_info


def _workload_ratios(workload_map, trace_list):
    """Workload values and ratios to the reference (first) trace."""
    reference_value = workload_map[trace_list[0]]

    values = {trace: workload_map[trace] for trace in trace_list}
    ratios = {
        trace: workload_map[trace] / reference_value
        for trace in trace_list
    }

    return values, ratios


def describe_detected(scaling_info):
    """Return the label of the detected scaling shown to the user."""

    if scaling_info.selected == "workload":
        return "Not used (workload given)"

    if scaling_info.detected:
        return scaling_info.detected.capitalize()

    return "Non-Avail"


def _describe_mode(mode):
    if mode == "workload":
        return "User-defined workload"
    return mode.capitalize()


def describe_scaling(scaling_info):
    """Return the (scaling used, selection) labels shown to the user."""

    if scaling_info.selected == "workload":
        return (
            "User-defined workload",
            "Manual ({})".format(scaling_info.workload_option),
        )

    selected = scaling_info.selected.capitalize()

    if scaling_info.selection_mode == "auto":
        selection = "Automatic"
    elif scaling_info.selection_mode == "manual":
        selection = "Manual"
    else:
        selection = "Implicit"

    return selected, selection


def describe_domains(scaling_info):
    """Scaling of the Host and Device domains, when they have their own:
    a list of (domain label, scaling used, selection)."""

    return [
        (
            domain.capitalize(),
            _describe_mode(scaling_info.domain_modes[domain]),
            scaling_info.domain_selection[domain],
        )
        for domain in DOMAINS
        if domain in scaling_info.domain_modes
    ]


# Resource counted by the weak-scaling ratio of each domain.
RESOURCE_COUNTS = {
    "host": ("count_host_threads", "Host threads"),
    "device": ("count_devices", "devices"),
}


def resource_ratio(raw_data, trace_list, trace, domain):
    """Weak-scaling ratio of a domain (Host threads or devices) for a trace,
    or None when it cannot be computed."""
    if raw_data is None or domain not in RESOURCE_COUNTS:
        return None

    key = RESOURCE_COUNTS[domain][0]

    try:
        return float(raw_data[key][trace]) / float(raw_data[key][trace_list[0]])
    except (KeyError, TypeError, ValueError, ZeroDivisionError):
        return None


def workload_table(scaling_info, trace_list=None, raw_data=None):
    """Workload and ratio of each trace, per level, for the outputs.

    Returns (columns, rows): columns is a list of level labels
    ("Application", "Host", "Device"), and each row is
    (trace, [(value or None, ratio, source) per column]). The ratio of a
    domain in weak scaling is its resource ratio when raw_data is given,
    and None otherwise.
    """
    levels = [(None, "Application")]
    if scaling_info.domain_modes:
        levels += [(domain, domain.capitalize()) for domain in DOMAINS]

    if trace_list is None:
        trace_list = list(scaling_info.workload_ratios or {})
        if not trace_list:
            for ratios in scaling_info.domain_workload_ratios.values():
                trace_list = list(ratios)
                break

    rows = []
    for trace in trace_list:
        cells = []
        for domain, _label in levels:
            mode = scaling_info.mode(domain)
            source = scaling_info.ratio_source(domain)
            value = None
            if mode == "workload":
                if domain in scaling_info.domain_workload_values:
                    value = scaling_info.domain_workload_values[domain][trace]
                else:
                    value = scaling_info.workload_values[trace]
                ratio = scaling_info.work_ratio(trace, None, domain)
            elif mode == "strong":
                ratio = 1.0
            else:
                ratio = resource_ratio(raw_data, trace_list, trace, domain)
                if domain in RESOURCE_COUNTS:
                    source = "weak scaling (ratio of {})".format(
                        RESOURCE_COUNTS[domain][1])
            cells.append((value, ratio, source))
        rows.append((trace, cells))

    return [label for _domain, label in levels], rows



def get_scaling_type(
    raw_data,
    trace_list,
    trace_processes,
    cmdl_args,
):
    """Return the scaling type used for metric computation.

    This function preserves the historical BasicAnalysis interface.

    Existing callers in simplemetrics.py and hybridmetrics.py expect this
    function to return only:

        "strong"
        "weak"

    The richer scaling information required by the semantic report is
    available through get_scaling_info().
    """

    scaling_info = get_scaling_info(
        raw_data=raw_data,
        trace_list=trace_list,
        trace_processes=trace_processes,
        cmdl_args=cmdl_args,
    )

    return scaling_info.selected


def parse_workload_values(text, option):
    """Parse a comma-separated list of positive workload values."""

    values = []

    for item in text.split(","):
        item = item.strip()

        try:
            value = float(item)
        except ValueError:
            print(
                "==Error== {} expects comma-separated numbers, "
                "got '{}'.".format(option, item)
            )
            sys.exit(1)

        if not value > 0.0:
            print(
                "==Error== {} values must be greater than zero, "
                "got '{}'.".format(option, item)
            )
            sys.exit(1)

        values.append(value)

    return values


def has_workload(cmdl_args):
    """True when the user gave any workload option."""
    return bool(
        getattr(cmdl_args, "workload", None)
        or any(getattr(cmdl_args, _option_attribute(option), None)
               for _domain, option in WORKLOAD_DOMAINS)
    )


def _matched_values(text, option, trace_list):
    values = parse_workload_values(text, option)

    if len(values) != len(trace_list):
        print(
            "==Error== {} has {} values but {} traces were given.".format(
                option, len(values), len(trace_list)
            )
        )
        sys.exit(1)

    return dict(zip(trace_list, values))


def build_workload_map(cmdl_args, trace_list):
    """Store on cmdl_args the workload value of each trace, if given.

    The values of --workload are matched, in order, with ``trace_list``:
    the traces as given on the command line, before any size filtering.
    In workload mode the traces are not sorted, so the first trace is the
    reference. The values are sizes or ratios: the ratio of each trace is
    its value divided by the value of the reference. The result is stored
    as ``cmdl_args.workload_map`` (trace -> value), or None without
    --workload. The workloads of the execution domains (--host-workload,
    --device-workload) are matched in the same way and stored as
    ``cmdl_args.domain_workload_maps`` (domain -> (option, map)).

    --scaling cannot be combined with --workload. With only Host or Device
    workloads it sets the scaling of the other domain.
    """

    cmdl_args.workload_map = None
    cmdl_args.workload_option = None
    cmdl_args.domain_workload_maps = {}

    for domain, option in WORKLOAD_DOMAINS:
        text = getattr(cmdl_args, _option_attribute(option), None)

        if text:
            cmdl_args.domain_workload_maps[domain] = (
                option, _matched_values(text, option, trace_list))

    text = getattr(cmdl_args, "workload", None)

    if not text:
        return None

    if getattr(cmdl_args, "scaling", "auto") != "auto":
        print(
            "==Error== --workload cannot be combined with --scaling {}.".format(
                cmdl_args.scaling
            )
        )
        sys.exit(1)

    cmdl_args.workload_map = _matched_values(text, "--workload", trace_list)
    cmdl_args.workload_option = "--workload"

    return cmdl_args.workload_map
