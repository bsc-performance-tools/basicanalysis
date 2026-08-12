#!/usr/bin/env python3

"""Scaling detection and selection utilities."""


import sys


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
        Scaling type finally used by BasicAnalysis for metric computation.
        The value is always "strong" or "weak".

    selection_mode : str
        Indicates how the selected scaling type was obtained.
        Possible values are:
            - "auto": automatically detected.
            - "manual": explicitly selected by the user.
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


def _compute_scaling_detection(
    raw_data,
    trace_list,
    trace_processes,
    eps=0.9,
):
    """Detect weak or strong scaling from execution measurements.

    This function implements the automatic scaling-detection algorithm
    historically used by BasicAnalysis.

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

    normalized_inst_ratio = 0
    normalized_runtime_ratio = 0
    normalized_useful_avg_ratio = 0

    reference_trace = trace_list[0]

    for trace in trace_list:
        try:
            inst_ratio = (
                float(raw_data["useful_ins"][trace])
                / float(raw_data["useful_ins"][reference_trace])
            )
        except Exception:
            inst_ratio = 0.0

        try:
            proc_ratio = (
                float(trace_processes[trace])
                / float(trace_processes[reference_trace])
            )
        except Exception:
            proc_ratio = "NaN"

        try:
            runtime_ratio = (
                float(raw_data["runtime"][trace])
                / float(raw_data["runtime"][reference_trace])
            )
        except Exception:
            runtime_ratio = "NaN"

        try:
            useful_avg_ratio = (
                float(raw_data["useful_avg"][trace])
                / float(raw_data["useful_avg"][reference_trace])
            )
        except Exception:
            useful_avg_ratio = "NaN"

        normalized_inst_ratio += (
            inst_ratio / proc_ratio
        )

        normalized_runtime_ratio += (
            runtime_ratio
        )

        normalized_useful_avg_ratio += (
            useful_avg_ratio
        )

    # Ignore the reference execution, whose normalized ratio is 1.0.
    normalized_inst_ratio = (
        normalized_inst_ratio - 1
    ) / (len(trace_list) - 1)

    normalized_runtime_ratio = (
        normalized_runtime_ratio - 1
    ) / (len(trace_list) - 1)

    normalized_useful_avg_ratio = (
        normalized_useful_avg_ratio - 1
    ) / (len(trace_list) - 1)

    weak_scaling_indicators = 0

    if normalized_inst_ratio > eps:
        weak_scaling_indicators += 1

    if normalized_runtime_ratio > eps:
        weak_scaling_indicators += 1

    if normalized_useful_avg_ratio > eps:
        weak_scaling_indicators += 1

    # At least two of the three indicators must identify weak scaling.
    if weak_scaling_indicators > 1:
        detected = "weak"
    else:
        detected = "strong"

    return ScalingInfo(
        has_scaling_analysis=True,
        detected=detected,
        selected=detected,
        selection_mode="auto",
        overridden=False,
        normalized_inst_ratio=normalized_inst_ratio,
        normalized_runtime_ratio=normalized_runtime_ratio,
        normalized_useful_avg_ratio=normalized_useful_avg_ratio,
        threshold=eps,
    )


def get_scaling_info(
    raw_data,
    trace_list,
    trace_processes,
    cmdl_args,
):
    """Return complete information about scaling detection and selection.

    The automatic detector first determines whether the analyzed executions
    resemble strong or weak scaling.

    The command-line scaling option is then applied:

        auto
            Use the automatically detected scaling type.

        weak
            Force weak scaling.

        strong
            Force strong scaling.

    When the user-selected scaling differs from the automatically detected
    scaling, ``overridden`` is set to True and the same warning historically
    produced by BasicAnalysis is emitted.

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

    if cmdl_args.scaling == "weak":
        scaling_info.selected = "weak"
        scaling_info.selection_mode = "manual"

        if scaling_info.detected == "strong":
            scaling_info.overridden = True

            print(
                "==Warning== Scaling set to weak scaling "
                "but detected strong scaling."
            )
            print("")
        else:
            scaling_info.overridden = False

        return scaling_info

    if cmdl_args.scaling == "strong":
        scaling_info.selected = "strong"
        scaling_info.selection_mode = "manual"

        if scaling_info.detected == "weak":
            scaling_info.overridden = True

            print(
                "==Warning== Scaling set to strong scaling "
                "but detected weak scaling."
            )
            print("")
        else:
            scaling_info.overridden = False

        return scaling_info

    print(
        "==Error== reached undefined control flow state."
    )
    sys.exit(1)


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