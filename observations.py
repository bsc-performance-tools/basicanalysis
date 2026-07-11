#!/usr/bin/env python3

"""Deterministic observations for BasicAnalysis reports."""

from __future__ import print_function, division

import math

# ---------------------------------------------------------------------
# Observation thresholds
# ---------------------------------------------------------------------

ATTENTION_THRESHOLD = 85.0
CRITICAL_THRESHOLD = 60.0


def _is_number(value):
    try:
        value = float(value)
        return not math.isnan(value)
    except Exception:
        return False


def _to_float(value):
    if _is_number(value):
        return float(value)
    return None


def _metric_series(metric_sources, metric_key, trace_list):
    """Return numeric values for one metric across traces."""
    source = metric_sources.get(metric_key, {})
    values = []

    for trace in trace_list:
        try:
            value = source[metric_key][trace]
        except Exception:
            value = None

        value = _to_float(value)
        if value is not None:
            values.append(value)

    return values


def _trend_type(values, stable_threshold=2.0):
    """
    Classify trend using first-last difference and monotonicity.

    Values are percentages.
    """
    if len(values) < 2:
        return "single"

    first = values[0]
    last = values[-1]
    delta = last - first

    decreasing = all(values[i] >= values[i + 1] for i in range(len(values) - 1))
    increasing = all(values[i] <= values[i + 1] for i in range(len(values) - 1))

    if abs(delta) < stable_threshold:
        return "stable"

    if delta < 0:
        if decreasing:
            return "decreasing"
        return "non_monotonic_decrease"

    if delta > 0:
        if increasing:
            return "increasing"
        return "non_monotonic_increase"

    return "stable"


def _trend_direction(values):
    """Return a simplified trend direction."""
    trend = _trend_type(values)

    if trend in ("decreasing", "non_monotonic_decrease"):
        return "decreasing"

    if trend in ("increasing", "non_monotonic_increase"):
        return "increasing"

    return "stable"


def _trend_delta(values):
    if len(values) < 2:
        return 0.0

    return values[-1] - values[0]

def _severity(delta):
    """Classify degradation magnitude."""
    if delta <= -15.0:
        return "significant"
    if delta <= -5.0:
        return "moderate"
    if delta < -2.0:
        return "small"
    return "none"


def _format_series(values):
    return " → ".join("{:.2f}%".format(v) for v in values)


def _metric_label(metric_info, metric_key):
    info = metric_info.get(metric_key, {})
    return info.get("label", metric_key).replace("-", "").replace("=", "").strip()


def _last_value(metric_sources, metric_key, trace_list):
    values = _metric_series(metric_sources, metric_key, trace_list)
    if not values:
        return None, []
    return values[-1], values


def _status_text(value):
    if value < CRITICAL_THRESHOLD:
        return "critical"
    if value < ATTENTION_THRESHOLD:
        return "below the acceptable threshold"
    return "acceptable"


def _metric_status(value):
    if value is None:
        return "unavailable"

    if value < CRITICAL_THRESHOLD:
        return "critical"

    if value < ATTENTION_THRESHOLD:
        return "attention"

    return "good"


def _metric_last_values(metric_sources, metric_key, trace_list):
    values = _metric_series(
        metric_sources,
        metric_key,
        trace_list,
    )

    if not values:
        return None, []

    return values[-1], values


def _clean_label(metric_info, metric_key):
    info = metric_info.get(metric_key, {})
    label = info.get("label", metric_key)

    return (
        label
        .replace("-", "")
        .replace("=", "")
        .replace("*", "")
        .strip()
    )

def _join_metric_names(names):
    if not names:
        return ""

    if len(names) == 1:
        return names[0]

    if len(names) == 2:
        return "{} and {}".format(
            names[0],
            names[1],
        )

    return "{}, and {}".format(
        ", ".join(names[:-1]),
        names[-1],
    )

def build_performance_interpretation(tree, metric_info, metric_sources,
                                     trace_list):
    """
    Build a hierarchy-aware interpretation of the efficiency metrics.

    The interpretation explains which direct child metrics are most likely
    to account for a low parent metric. It does not infer root causes.
    """

    interpretations = []

    def visit(node):
        metric_key = node["metric"]
        children = node.get("children", [])

        parent_value, _ = _metric_last_values(
            metric_sources,
            metric_key,
            trace_list,
        )

        if parent_value is None:
            return

        if parent_value < ATTENTION_THRESHOLD and children:
            child_data = []

            for child in children:
                child_key = child["metric"]

                child_value, _ = _metric_last_values(
                    metric_sources,
                    child_key,
                    trace_list,
                )

                if child_value is None:
                    continue

                child_data.append({
                    "metric": child_key,
                    "label": _clean_label(
                        metric_info,
                        child_key,
                    ),
                    "value": child_value,
                    "status": _metric_status(child_value),
                })

            if child_data:
                limiting_children = [
                    child
                    for child in child_data
                    if child["value"] < ATTENTION_THRESHOLD
                ]

                healthy_children = [
                    child
                    for child in child_data
                    if child["value"] >= ATTENTION_THRESHOLD
                ]

                limiting_children.sort(
                    key=lambda child: child["value"]
                )

                parent_label = _clean_label(
                    metric_info,
                    metric_key,
                )

                if limiting_children:
                    main_child = limiting_children[0]

                    text = (
                        "{} is mainly limited by {}"
                    ).format(
                        parent_label,
                        main_child["label"],
                    )

                    if healthy_children:
                        healthy_names = [
                            child["label"]
                            for child in healthy_children
                        ]

                        text += (
                            ", while {} remain{} at acceptable levels"
                        ).format(
                            _join_metric_names(healthy_names),
                            "" if len(healthy_names) > 1 else "s",
                        )

                    text += "."

                    interpretations.append({
                        "metric": metric_key,
                        "value": parent_value,
                        "text": text,
                    })

        for child in children:
            visit(child)

    for root in tree:
        visit(root)

    return interpretations


def build_performance_interpretation_html(interpretations):
    """Render hierarchy-aware metric interpretation."""

    if not interpretations:
        return (
            "<div class='performance-interpretation'>"
            "<h3>Performance interpretation</h3>"
            "<p>"
            "The analyzed metric hierarchy does not show a dominant "
            "efficiency factor below the attention threshold."
            "</p>"
            "</div>"
        )

    sentences = [
        item["text"]
        for item in interpretations
    ]

    return (
        "<div class='performance-interpretation'>"
        "<h3>Performance interpretation</h3>"
        "<p>{}</p>"
        "</div>"
    ).format(" ".join(sentences))


def build_scaling_trend_lines(metric_keys, metric_info, metric_sources,
                              trace_list, max_items=4):
    """
    Build trend notes for scaling analysis.

    Only used when more than one trace is available.
    """
    if len(trace_list) < 2:
        return []

    trend_lines = []

    for metric_key in metric_keys:
        values = _metric_series(metric_sources, metric_key, trace_list)
        if len(values) < 2:
            continue

        label = _metric_label(metric_info, metric_key)
        trend = _trend_type(values)
        final_value = values[-1]
        delta = final_value - values[0]

        if trend in ("decreasing", "non_monotonic_decrease"):
            if final_value < ATTENTION_THRESHOLD:
                text = (
                    "{} is below the acceptable threshold and decreases with scale ({})."
                ).format(label, _format_series(values))
            elif delta <= -5.0:
                text = (
                    "{} remains acceptable, but decreases with scale and may become relevant at larger scale ({})."
                ).format(label, _format_series(values))
            else:
                text = None

        elif trend in ("increasing", "non_monotonic_increase"):
            if final_value < ATTENTION_THRESHOLD:
                text = (
                    "{} remains below the acceptable threshold, although it improves with scale ({})."
                ).format(label, _format_series(values))
            else:
                text = None

        else:
            text = None

        if text:
            trend_lines.append({
                "metric": metric_key,
                "label": label,
                "values": values,
                "final_value": final_value,
                "delta": delta,
                "text": text,
            })

    trend_lines.sort(key=lambda obs: (obs["final_value"], obs["delta"]))
    return [obs["text"] for obs in trend_lines[:max_items]]


def build_tree_diagnosis_observations(tree, metric_info, metric_sources,
                                      trace_list):
    """
    Build hierarchical observations following the metric tree.

    The diagnosis starts from root metrics and recursively expands only
    branches whose last-trace value is below ATTENTION_THRESHOLD.
    """
    lines = []

    def visit(node, depth=0):
        metric_key = node["metric"]
        children = node.get("children", [])

        value, values = _last_value(metric_sources, metric_key, trace_list)
        if value is None:
            return

        if value >= ATTENTION_THRESHOLD and depth > 0:
            return

        label = _metric_label(metric_info, metric_key)
        status = _status_text(value)
        indent = "&nbsp;" * (depth * 4)

        if depth == 0:
            if value >= ATTENTION_THRESHOLD:
                lines.append(
                    "{}{} remains acceptable ({:.2f}%).".format(
                        indent, label, value
                    )
                )
                return
            else:
                lines.append(
                    "{}{} is {} ({:.2f}%).".format(
                        indent, label, status, value
                    )
                )
        else:
            lines.append(
                "{}↳ {} is {} ({:.2f}%).".format(
                    indent, label, status, value
                )
            )

        bad_children = []
        good_children = []

        for child in children:
            child_key = child["metric"]
            child_value, _ = _last_value(metric_sources, child_key, trace_list)

            if child_value is None:
                continue

            if child_value < ATTENTION_THRESHOLD:
                bad_children.append((child_value, child))
            else:
                good_children.append((child_value, child))

        bad_children.sort(key=lambda item: item[0])

        for _, child in bad_children:
            visit(child, depth + 1)

        if depth == 0 and good_children and bad_children:
            good_names = [
                _metric_label(metric_info, child["metric"])
                for _, child in good_children
            ]

            lines.append(
                "{}{} remain acceptable and are less likely to explain the main loss.".format(
                    "&nbsp;" * ((depth + 1) * 4),
                    ", ".join(good_names),
                )
            )

    for root in tree:
        visit(root, depth=0)

    if not lines:
        lines.append(
            "All analyzed metrics remain above {:.0f}%, so no significant efficiency loss is highlighted.".format(
                ATTENTION_THRESHOLD
            )
        )

    return lines


def build_tree_diagnosis_html(diagnosis_lines, trend_lines=None,
                              title="Analysis summary"):
    trend_lines = trend_lines or []

    html = []
    html.append("<div class='observation-box'>")
    html.append("<h3>{}</h3>".format(title))

    html.append("<p><b>Diagnosis</b></p>")
    html.append("<div class='tree-diagnosis'>")
    for line in diagnosis_lines:
        html.append("<div>{}</div>".format(line))
    html.append("</div>")

    if trend_lines:
        html.append("<p><b>Scaling trends</b></p>")
        html.append("<ul>")
        for line in trend_lines:
            html.append("<li>{}</li>".format(line))
        html.append("</ul>")

    html.append("</div>")
    return "\n".join(html)


def build_threshold_observations(metric_keys, metric_info, metric_sources,
                                 trace_list, max_attention=5, max_trends=4):
    """
    Build observations using threshold-first logic.

    1. Report metrics below ATTENTION_THRESHOLD in the last trace.
    2. If several traces are available, report trend notes.
    """
    attention = []
    trends = []

    for metric_key in metric_keys:
        values = _metric_series(metric_sources, metric_key, trace_list)
        if not values:
            continue

        info = metric_info.get(metric_key, {})
        label = info.get("label", metric_key).replace("-", "").replace("=", "").strip()

        final_value = values[-1]

        if final_value < CRITICAL_THRESHOLD:
            level = "critical"
        elif final_value < ATTENTION_THRESHOLD:
            level = "requires attention"
        else:
            level = "acceptable"

        if final_value < ATTENTION_THRESHOLD:
            attention.append({
                "metric": metric_key,
                "label": label,
                "values": values,
                "final_value": final_value,
                "level": level,
                "text": "{} is {} in the last trace ({:.2f}%).".format(
                    label,
                    level,
                    final_value,
                ),
            })

        if len(values) >= 2:
            trend = _trend_type(values)
            delta = values[-1] - values[0]

            if trend in ("decreasing", "non_monotonic_decrease"):
                if final_value < ATTENTION_THRESHOLD:
                    text = (
                        "{} is below the acceptable threshold and decreases with scale "
                        "({})."
                    ).format(label, _format_series(values))
                elif delta <= -5.0:
                    text = (
                        "{} remains acceptable but decreases with scale; "
                        "it may become relevant at larger scale ({})."
                    ).format(label, _format_series(values))
                else:
                    text = None

            elif trend in ("increasing", "non_monotonic_increase"):
                if final_value < ATTENTION_THRESHOLD:
                    text = (
                        "{} remains below the acceptable threshold, although it improves "
                        "with scale ({})."
                    ).format(label, _format_series(values))
                else:
                    text = None
            else:
                text = None

            if text:
                trends.append({
                    "metric": metric_key,
                    "label": label,
                    "values": values,
                    "delta": delta,
                    "trend": trend,
                    "final_value": final_value,
                    "text": text,
                })

    attention.sort(key=lambda obs: obs["final_value"])

    # Prioritize low values first, then stronger degradation.
    trends.sort(key=lambda obs: (obs["final_value"], obs.get("delta", 0.0)))

    return {
        "attention": attention[:max_attention],
        "trends": trends[:max_trends],
    }


def build_threshold_observation_html(observation_groups,
                                     title="Analysis summary"):
    attention = observation_groups.get("attention", [])
    trends = observation_groups.get("trends", [])

    html = []
    html.append("<div class='observation-box'>")
    html.append("<h3>{}</h3>".format(title))

    if attention:
        html.append("<p><b>Metrics requiring attention</b></p>")
        html.append("<ul>")
        for obs in attention:
            html.append("<li>{}</li>".format(obs["text"]))
        html.append("</ul>")
    else:
        html.append(
            "<p>All analyzed metrics remain above {:.0f}% in the last trace.</p>".format(
                ATTENTION_THRESHOLD
            )
        )

    if trends:
        html.append("<p><b>Trend notes</b></p>")
        html.append("<ul>")
        for obs in trends:
            html.append("<li>{}</li>".format(obs["text"]))
        html.append("</ul>")

    html.append("</div>")

    return "\n".join(html)


def build_hierarchy_observations(metric_keys, metric_info, metric_sources,
                                 trace_list, tree, max_items=4):
    observations = build_trend_observations(
        metric_keys,
        metric_info,
        metric_sources,
        trace_list,
        max_items=50,
    )

    obs_by_metric = {obs["metric"]: obs for obs in observations}

    hierarchy_obs = []

    def visit(node, depth=0):
        metric = node["metric"]
        children = node.get("children", [])

        parent_obs = obs_by_metric.get(metric)
        child_obs = [
            obs_by_metric.get(child["metric"])
            for child in children
            if obs_by_metric.get(child["metric"]) is not None
        ]

        if parent_obs and child_obs:
            # For diagnosis, select the child with the lowest final efficiency.
            # This is the main limiting component, even if another child has
            # a slightly larger degradation trend.
            def _ratio_loss(obs):
                # For efficiency metrics in [0,100], the child with the lowest final value
                # usually contributes the largest multiplicative loss.
                return obs["values"][-1]

            child_obs.sort(key=_ratio_loss)
            main_child = child_obs[0]

            if parent_obs["trend"] in ("decreasing", "non_monotonic_decrease"):
                trend_text = "decreases as resources increase"
            elif parent_obs["trend"] in ("increasing", "non_monotonic_increase"):
                trend_text = "improves as resources increase"
            else:
                trend_text = "changes across traces"

            text = (
                "{} {}. The main limiting child metric is {}."
            ).format(
                parent_obs["label"],
                trend_text,
                main_child["label"],
            )

            hierarchy_obs.append({
                "metric": metric,
                "label": parent_obs["label"],
                "values": parent_obs["values"],
                "delta": parent_obs["delta"],
                "trend": parent_obs["trend"],
                "severity": parent_obs["severity"],
                "text": text,
                "action": main_child.get("action", parent_obs.get("action", "")),
            })

        for child in children:
            visit(child, depth + 1)

    for root in tree:
        visit(root)


    if hierarchy_obs:

        # Only report metrics that deserve attention
        attention_obs = [
            obs for obs in hierarchy_obs
            if obs["values"] and obs["values"][-1] < ATTENTION_THRESHOLD
        ]

        # If all metrics are good, simply report that.
        if not attention_obs:
            return [{
                "metric": None,
                "label": "All metrics",
                "values": [],
                "delta": 0.0,
                "trend": "stable",
                "severity": "none",
                "text": (
                    "All efficiency metrics remain above {:.0f}%, "
                    "so no significant efficiency loss is highlighted."
                ).format(ATTENTION_THRESHOLD),
                "action": "",
            }]

        # Lowest efficiency first
        attention_obs.sort(key=lambda obs: obs["values"][-1])

        return attention_obs[:max_items]

    return observations[:max_items]

def _build_metric_observation(metric_key, metric_info, values):
    if len(values) < 2:
        return None

    first = values[0]
    last = values[-1]
    delta = last - first

    trend = _trend_type(values)
    sev = _severity(delta)

    if sev == "none" and trend not in ("increasing", "non_monotonic_increase"):
        return None

    info = metric_info.get(metric_key, {})
    label = info.get("label", metric_key).replace("-", "").replace("=", "").strip()

    if trend == "decreasing":
        if sev == "significant":
            text = "{} decreases significantly across traces ({}).".format(
                label, _format_series(values)
            )
        elif sev == "moderate":
            text = "{} shows a moderate degradation across traces ({}).".format(
                label, _format_series(values)
            )
        else:
            text = "{} shows a small degradation across traces ({}).".format(
                label, _format_series(values)
            )

    elif trend == "non_monotonic_decrease":
        text = "{} has a non-monotonic degradation trend ({}).".format(
            label, _format_series(values)
        )

    elif trend == "increasing":
        text = "{} improves across traces ({}).".format(
            label, _format_series(values)
        )

    elif trend == "non_monotonic_increase":
        text = "{} has a non-monotonic improvement trend ({}).".format(
            label, _format_series(values)
        )

    else:
        return None

    return {
        "metric": metric_key,
        "label": label,
        "values": values,
        "delta": delta,
        "trend": trend,
        "severity": sev,
        "text": text,
        "action": info.get("action", ""),
    }


def build_trend_observations(metric_keys, metric_info, metric_sources,
                             trace_list, max_items=4):
    """
    Build deterministic observations for a metric page.

    Parameters
    ----------
    metric_keys : list[str]
        Metrics to inspect.
    metric_info : dict
        Metadata for labels, meaning, and suggested action.
    metric_sources : dict
        Maps each metric key to the factor dictionary containing values.
    trace_list : list
        Ordered list of traces.
    max_items : int
        Maximum number of observations to return.
    """
    observations = []

    if len(trace_list) < 2:
        return [{
            "metric": None,
            "label": "Single trace",
            "values": [],
            "delta": 0.0,
            "trend": "single",
            "severity": "none",
            "text": "Only one trace is available, so scalability trends cannot be evaluated.",
            "action": "Use multiple traces to analyze scalability trends.",
        }]

    for metric_key in metric_keys:
        values = _metric_series(metric_sources, metric_key, trace_list)

        if len(values) < 2:
            continue

        obs = _build_metric_observation(metric_key, metric_info, values)
        if obs is not None:
            observations.append(obs)

    # Prioritize strongest degradations first, then improvements.
    observations.sort(key=lambda item: item["delta"])

    return observations[:max_items]


def build_observation_html(observations, title="Analysis summary"):
    """Render observations as HTML."""
    if not observations:
        return (
            "<div class='observation-box'>"
            "<h3>{}</h3>"
            "<p>No relevant trend was detected across the selected traces.</p>"
            "</div>"
        ).format(title)

    html = []
    html.append("<div class='observation-box'>")
    html.append("<h3>{}</h3>".format(title))
    html.append("<ul>")

    for obs in observations:
        html.append("<li>{}</li>".format(obs["text"]))

    html.append("</ul>")

    html.append("</div>")

    return "\n".join(html)

def build_analysis_summary_html(performance_html,
                                scaling_html="",
                                title="Analysis summary"):
    html = []

    html.append("<div class='observation-box'>")
    html.append("<h3>{}</h3>".format(title))

    html.append(performance_html)

    if scaling_html:
        html.append(scaling_html)

    html.append("</div>")

    return "\n".join(html)


def _metric_trend_data(metric_key, metric_info, metric_sources, trace_list):
    values = _metric_series(
        metric_sources,
        metric_key,
        trace_list,
    )

    if len(values) < 2:
        return None

    return {
        "metric": metric_key,
        "label": _clean_label(metric_info, metric_key),
        "values": values,
        "first": values[0],
        "final": values[-1],
        "delta": _trend_delta(values),
        "direction": _trend_direction(values),
        "status": _metric_status(values[-1]),
    }


def build_scaling_interpretation(tree, metric_info, metric_sources,
                                 trace_list):
    """
    Build hierarchy-aware scaling interpretation.

    The analysis compares the trend of each parent metric with the trends
    of its direct children.
    """

    if len(trace_list) < 2:
        return []

    interpretations = []

    def visit(node):
        metric_key = node["metric"]
        children = node.get("children", [])

        parent = _metric_trend_data(
            metric_key,
            metric_info,
            metric_sources,
            trace_list,
        )

        if parent is None:
            return

        child_data = []

        for child in children:
            data = _metric_trend_data(
                child["metric"],
                metric_info,
                metric_sources,
                trace_list,
            )

            if data is not None:
                child_data.append(data)

        if children and child_data:
            text = _build_parent_child_scaling_text(
                parent,
                child_data,
            )

            if text:
                interpretations.append({
                    "metric": metric_key,
                    "text": text,
                    "final": parent["final"],
                    "delta": parent["delta"],
                })

        for child in children:
            visit(child)

    for root in tree:
        visit(root)

    return interpretations


def _build_parent_child_scaling_text(parent, children):
    parent_label = parent["label"]
    parent_direction = parent["direction"]

    degrading_children = [
        child
        for child in children
        if child["direction"] == "decreasing"
    ]

    improving_low_children = [
        child
        for child in children
        if (
            child["direction"] == "increasing"
            and child["final"] < ATTENTION_THRESHOLD
        )
    ]

    healthy_children = [
        child
        for child in children
        if child["final"] >= ATTENTION_THRESHOLD
    ]

    # Acceptable but degrading
    if (
        parent_direction == "decreasing"
        and parent["final"] >= ATTENTION_THRESHOLD
    ):
        return (
            "{} remains acceptable but decreases with scale and may become "
            "relevant at larger scale."
        ).format(parent_label)

    # Parent degradation
    if parent_direction == "decreasing":
        text = "{} decreases with scale".format(parent_label)

        if degrading_children:
            degrading_children.sort(
                key=lambda child: child["delta"]
            )

            main_child = degrading_children[0]

            text += (
                ", following the degradation of {}"
            ).format(main_child["label"])

            other_degrading = [
                child["label"]
                for child in degrading_children[1:]
                if child["delta"] <= -5.0
            ]

            if other_degrading:
                text += (
                    "; {} also degrade{} with scale"
                ).format(
                    _join_metric_names(other_degrading),
                    "" if len(other_degrading) > 1 else "s",
                )

        elif improving_low_children:
            improving_low_children.sort(
                key=lambda child: child["final"]
            )

            main_child = improving_low_children[0]

            text += (
                ". Although {} improves with scale, it remains below the "
                "acceptable threshold and continues to limit the parent metric"
            ).format(main_child["label"])

        text += "."

        healthy_names = [
            child["label"]
            for child in healthy_children
            if (
                child["direction"] != "decreasing"
                or child["delta"] > -5.0
            )
        ]

        if healthy_names:
            text += (
                " {} remain{} at acceptable levels and are unlikely "
                "to explain the observed scaling loss."
            ).format(
                _join_metric_names(healthy_names),
                "" if len(healthy_names) > 1 else "s",
            )

        return text

    # Improving but still low
    if (
        parent_direction == "increasing"
        and parent["final"] < ATTENTION_THRESHOLD
    ):
        text = (
            "{} improves with scale but remains below the acceptable threshold"
        ).format(parent_label)

        low_children = [
            child
            for child in children
            if child["final"] < ATTENTION_THRESHOLD
        ]

        if low_children:
            low_children.sort(
                key=lambda child: child["final"]
            )

            text += (
                ", with {} remaining the main limiting child metric"
            ).format(low_children[0]["label"])

        return text + "."

    return None


def build_scaling_interpretation_html(interpretations):
    """Render hierarchy-aware scaling interpretation."""

    if not interpretations:
        return ""

    paragraphs = [
        item["text"]
        for item in interpretations
    ]

    return (
        "<div class='scaling-interpretation'>"
        "<h3>Scaling trends</h3>"
        "<p>{}</p>"
        "</div>"
    ).format(
        " ".join(paragraphs)
    )