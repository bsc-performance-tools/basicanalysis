"""Standalone tests for the typed metric knowledge provider.

Run from the BasicAnalysis repository root with:

    python3 tests/test_provider.py

This test script intentionally uses only the Python standard library.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from pathlib import Path
from types import MappingProxyType
from typing import Any, Callable
import sys


ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from metrics import (
    MetricKnowledge,
    MetricKnowledgeBase,
    MetricStatus,
    MetricThresholds,
    PerformanceKnowledgeProvider,
    get_default_provider,
)


DEFINITIONS = ROOT / "metrics" / "definitions.yaml"


def assert_raises(
    expected_exception: type[BaseException],
    function: Callable[..., Any],
    *args: Any,
    contains: str | None = None,
    **kwargs: Any,
) -> BaseException:
    """Assert that a callable raises the expected exception."""

    try:
        function(*args, **kwargs)

    except expected_exception as error:
        if contains is not None:
            message = str(error)

            assert contains in message, (
                f"Expected exception message to contain {contains!r}, "
                f"but got {message!r}."
            )

        return error

    except Exception as error:
        raise AssertionError(
            f"Expected {expected_exception.__name__}, "
            f"but {type(error).__name__} was raised: {error}"
        ) from error

    raise AssertionError(
        f"Expected {expected_exception.__name__}, "
        "but no exception was raised."
    )


def run_test(
    name: str,
    function: Callable[[], None],
) -> None:
    """Run one logical test group and print its result."""

    print(f"[TEST] {name:<46}", end="", flush=True)

    try:
        function()

    except Exception:
        print("FAILED")
        raise

    print("OK")


def make_knowledge_base() -> MetricKnowledgeBase:
    """Create a fresh metric knowledge base."""

    assert DEFINITIONS.exists(), (
        f"Metric definitions file not found: {DEFINITIONS}"
    )

    return MetricKnowledgeBase(DEFINITIONS)


def make_provider(
    *,
    enable_cache: bool = True,
    thresholds: MetricThresholds | None = None,
) -> PerformanceKnowledgeProvider:
    """Create a fresh provider for one logical test group."""

    return PerformanceKnowledgeProvider(
        make_knowledge_base(),
        default_thresholds=thresholds,
        enable_cache=enable_cache,
    )


def test_provider_construction() -> None:
    """Validate provider construction and public configuration."""

    knowledge_base = make_knowledge_base()

    provider = PerformanceKnowledgeProvider(
        knowledge_base,
    )

    assert provider.knowledge_base is knowledge_base

    assert provider.default_thresholds == MetricThresholds()

    assert provider.default_thresholds.critical == 60.0
    assert provider.default_thresholds.attention == 85.0
    assert provider.default_thresholds.reference == 100.0

    assert provider.cache_enabled is True
    assert provider.cache_size == 0

    uncached_provider = PerformanceKnowledgeProvider(
        knowledge_base,
        enable_cache=False,
    )

    assert uncached_provider.cache_enabled is False
    assert uncached_provider.cache_size == 0

    assert_raises(
        TypeError,
        PerformanceKnowledgeProvider,
        object(),
        contains="MetricKnowledgeBase",
    )

    custom_thresholds = MetricThresholds(
        critical=50.0,
        attention=80.0,
        reference=100.0,
    )

    custom_provider = PerformanceKnowledgeProvider(
        knowledge_base,
        default_thresholds=custom_thresholds,
    )

    assert custom_provider.default_thresholds is custom_thresholds

    assert (
        custom_provider.thresholds("global_eff")
        is custom_thresholds
    )


def test_threshold_validation() -> None:
    """Validate threshold values, ordering, and immutability."""

    valid_cases = (
        (0.0, 85.0, 100.0),
        (50.0, 80.0, 100.0),
        (-10.0, 0.0, 100.0),
        (60.0, 100.0, 100.0),
    )

    for critical, attention, reference in valid_cases:
        thresholds = MetricThresholds(
            critical=critical,
            attention=attention,
            reference=reference,
        )

        assert thresholds.critical == critical
        assert thresholds.attention == attention
        assert thresholds.reference == reference

    invalid_types = (
        ("critical", True),
        ("attention", False),
        ("reference", "100"),
        ("critical", None),
    )

    for field, value in invalid_types:
        arguments: dict[str, Any] = {
            "critical": 60.0,
            "attention": 85.0,
            "reference": 100.0,
        }

        arguments[field] = value

        assert_raises(
            TypeError,
            MetricThresholds,
            **arguments,
            contains="must be numeric",
        )

    invalid_finite_values = (
        ("critical", float("nan")),
        ("attention", float("inf")),
        ("reference", float("-inf")),
    )

    for field, value in invalid_finite_values:
        arguments = {
            "critical": 60.0,
            "attention": 85.0,
            "reference": 100.0,
        }

        arguments[field] = value

        assert_raises(
            ValueError,
            MetricThresholds,
            **arguments,
            contains="must be finite",
        )

    assert_raises(
        ValueError,
        MetricThresholds,
        critical=85.0,
        attention=85.0,
        reference=100.0,
        contains="critical threshold must be lower",
    )

    assert_raises(
        ValueError,
        MetricThresholds,
        critical=60.0,
        attention=101.0,
        reference=100.0,
        contains="must not exceed the reference",
    )

    thresholds = MetricThresholds()

    def mutate_thresholds() -> None:
        thresholds.critical = 50.0  # type: ignore[misc]

    assert_raises(
        FrozenInstanceError,
        mutate_thresholds,
    )


def test_metric_resolution() -> None:
    """Validate canonical typed metric resolution."""

    provider = make_provider()

    metric = provider.get("global_eff")

    assert isinstance(metric, MetricKnowledge)

    assert metric.id == "global_eff"
    assert metric.requested_id == "global_eff"

    assert metric.name == "Global Efficiency"
    assert metric.short_name == "Global"

    assert metric.family == "global"
    assert metric.analysis_level == "application"
    assert metric.metric_type == "compound_efficiency"

    assert metric.definition

    assert (
        metric.formula["text"]
        == "GE = PE × CompScale"
    )

    assert metric.children == (
        "parallel_eff",
        "comp_scale",
    )

    assert metric.typical_causes
    assert metric.next_steps
    assert metric.sources

    assert metric.label == metric.name
    assert metric.meaning == metric.definition

    assert metric.dependencies == metric.depends_on
    assert metric.causes == metric.typical_causes
    assert metric.source_details == metric.sources

    assert metric.clean_label == "Global Efficiency"

    assert provider.metric("global_eff") is metric

    metrics = provider.get_many(
        [
            "global_eff",
            "parallel_eff",
            "load_balance",
        ]
    )

    assert list(metrics) == [
        "global_eff",
        "parallel_eff",
        "load_balance",
    ]

    assert metrics["global_eff"].id == "global_eff"
    assert metrics["parallel_eff"].id == "parallel_eff"
    assert metrics["load_balance"].id == "load_balance"

    alias_result = provider.metrics(
        [
            "global_eff",
            "parallel_eff",
        ]
    )

    assert alias_result["global_eff"] is metric

    assert (
        alias_result["parallel_eff"]
        is provider.get("parallel_eff")
    )

    assert_raises(
        KeyError,
        provider.get,
        "not_a_metric",
        contains="Unknown metric",
    )


def test_runtime_templates_and_aliases() -> None:
    """Validate runtime template expansion and alias resolution."""

    provider = make_provider()

    metric = provider.get(
        "omp_parallel_eff",
        runtime="CUDA",
        runtime_family="cuda",
    )

    assert metric.id == "runtime_parallel_eff"
    assert metric.requested_id == "omp_parallel_eff"

    assert metric.name == "CUDA Parallel Efficiency"
    assert metric.short_name == "CUDA PE"

    assert metric.family == "cuda"

    assert (
        metric.formula["text"]
        == "CUDA_PE = HybridPE / MPI_PE"
    )

    assert "CUDA" in metric.definition

    assert all(
        "CUDA" in cause
        for cause in metric.typical_causes
    )

    assert all(
        "CUDA" in step
        for step in metric.next_steps
    )

    implicit_family = provider.get(
        "runtime_parallel_eff",
        runtime="CUDA",
    )

    assert implicit_family.family == "cuda"

    explicit_family = provider.get(
        "runtime_parallel_eff",
        runtime="OpenMP",
        runtime_family="thread_runtime",
    )

    assert explicit_family.name == "OpenMP Parallel Efficiency"
    assert explicit_family.family == "thread_runtime"

    assert (
        provider.label(
            "omp_parallel_eff",
            runtime="CUDA",
            short=True,
        )
        == "CUDA PE"
    )

    assert_raises(
        ValueError,
        provider.get,
        "runtime_parallel_eff",
        contains="requires template context",
    )


def test_labels_and_thresholds() -> None:
    """Validate label helpers and threshold resolution."""

    provider = make_provider()

    assert (
        provider.label("global_eff")
        == "Global Efficiency"
    )

    assert (
        provider.label(
            "global_eff",
            short=True,
        )
        == "Global"
    )

    assert (
        provider.clean_label("global_eff")
        == "Global Efficiency"
    )

    assert (
        provider.thresholds("global_eff")
        is provider.default_thresholds
    )


def test_status_classification() -> None:
    """Validate status classification and threshold boundaries."""

    provider = make_provider()

    cases = (
        (None, MetricStatus.UNAVAILABLE),
        ("not-a-number", MetricStatus.UNAVAILABLE),
        (True, MetricStatus.UNAVAILABLE),
        (float("nan"), MetricStatus.UNAVAILABLE),
        (float("inf"), MetricStatus.UNAVAILABLE),
        (0.0, MetricStatus.CRITICAL),
        (59.999, MetricStatus.CRITICAL),
        (60.0, MetricStatus.ATTENTION),
        (84.999, MetricStatus.ATTENTION),
        (85.0, MetricStatus.ACCEPTABLE),
        (100.0, MetricStatus.ACCEPTABLE),
        (100.001, MetricStatus.ABOVE_REFERENCE),
        ("90.0", MetricStatus.ACCEPTABLE),
    )

    for value, expected in cases:
        actual = provider.status(
            "global_eff",
            value,
        )

        assert actual is expected, (
            f"Unexpected status for {value!r}: "
            f"expected {expected}, got {actual}."
        )

    critical_cases = (
        (59.0, True),
        (60.0, False),
        (90.0, False),
        (None, False),
    )

    for value, expected in critical_cases:
        assert (
            provider.is_critical(
                "global_eff",
                value,
            )
            is expected
        )

    attention_cases = (
        (59.0, True),
        (60.0, True),
        (84.999, True),
        (85.0, False),
        (101.0, False),
        (None, False),
    )

    for value, expected in attention_cases:
        assert (
            provider.requires_attention(
                "global_eff",
                value,
            )
            is expected
        )

    acceptable_cases = (
        (59.0, False),
        (84.0, False),
        (85.0, True),
        (100.0, True),
        (101.0, True),
        (None, False),
    )

    for value, expected in acceptable_cases:
        assert (
            provider.is_acceptable(
                "global_eff",
                value,
            )
            is expected
        )

    assert (
        provider.is_acceptable(
            "global_eff",
            101.0,
            include_above_reference=False,
        )
        is False
    )

    above_reference_cases = (
        (100.0, False),
        (100.001, True),
        (150.0, True),
        (None, False),
    )

    for value, expected in above_reference_cases:
        assert (
            provider.is_above_reference(
                "global_eff",
                value,
            )
            is expected
        )

    custom_provider = make_provider(
        thresholds=MetricThresholds(
            critical=50.0,
            attention=75.0,
            reference=100.0,
        )
    )

    assert (
        custom_provider.status(
            "global_eff",
            49.9,
        )
        is MetricStatus.CRITICAL
    )

    assert (
        custom_provider.status(
            "global_eff",
            50.0,
        )
        is MetricStatus.ATTENTION
    )

    assert (
        custom_provider.status(
            "global_eff",
            75.0,
        )
        is MetricStatus.ACCEPTABLE
    )


def test_cache_behavior() -> None:
    """Validate provider cache semantics."""

    provider = make_provider()

    first = provider.get("global_eff")
    second = provider.get("global_eff")

    assert first is second
    assert provider.cache_size == 1

    provider.get("parallel_eff")

    assert provider.cache_size == 2

    provider.clear_cache()

    assert provider.cache_size == 0

    third = provider.get("global_eff")

    assert third == first
    assert third is not first

    uncached = make_provider(enable_cache=False)

    first = uncached.get("global_eff")
    second = uncached.get("global_eff")

    assert first == second
    assert first is not second
    assert uncached.cache_size == 0

    runtime_provider = make_provider()

    cuda = runtime_provider.get(
        "runtime_parallel_eff",
        runtime="CUDA",
        runtime_family="cuda",
    )

    openmp = runtime_provider.get(
        "runtime_parallel_eff",
        runtime="OpenMP",
        runtime_family="thread_runtime",
    )

    assert cuda is not openmp
    assert cuda.name == "CUDA Parallel Efficiency"
    assert openmp.name == "OpenMP Parallel Efficiency"

    normalized = make_provider()

    implicit = normalized.get(
        "runtime_parallel_eff",
        runtime="CUDA",
    )

    explicit = normalized.get(
        "runtime_parallel_eff",
        runtime="CUDA",
        runtime_family="cuda",
    )

    assert implicit is explicit


def test_immutability() -> None:
    """Validate immutable provider objects."""

    provider = make_provider()

    metric = provider.get("parallel_eff")

    def mutate_metric():
        metric.name = "Changed"

    assert_raises(
        FrozenInstanceError,
        mutate_metric,
    )

    assert isinstance(
        metric.formula,
        MappingProxyType,
    )

    def mutate_formula():
        metric.formula["text"] = "Changed"

    assert_raises(
        TypeError,
        mutate_formula,
    )

    variables = metric.formula["variables"]

    assert isinstance(
        variables,
        MappingProxyType,
    )

    def mutate_variables():
        variables["LB"] = "Changed"

    assert_raises(
        TypeError,
        mutate_variables,
    )

    global_metric = provider.get("global_eff")

    assert isinstance(global_metric.depends_on, tuple)
    assert isinstance(global_metric.assumptions, tuple)
    assert isinstance(global_metric.children, tuple)
    assert isinstance(global_metric.typical_causes, tuple)
    assert isinstance(global_metric.next_steps, tuple)
    assert isinstance(global_metric.sources, tuple)

    source = global_metric.sources[0]

    assert isinstance(
        source,
        MappingProxyType,
    )

    def mutate_source():
        source["title"] = "Changed"

    assert_raises(
        TypeError,
        mutate_source,
    )


def test_legacy_compatibility() -> None:
    """Validate compatibility with the old API."""

    kb = make_knowledge_base()

    provider = PerformanceKnowledgeProvider(kb)

    expected = kb.as_legacy_info("global_eff")
    actual = provider.to_legacy_info("global_eff")

    assert expected == actual

    runtime_args = dict(
        runtime="CUDA",
        runtime_family="cuda",
    )

    expected = kb.as_legacy_info(
        "omp_parallel_eff",
        **runtime_args,
    )

    actual = provider.to_legacy_info(
        "omp_parallel_eff",
        **runtime_args,
    )

    assert expected == actual

    assert actual["label"] == "CUDA Parallel Efficiency"
    assert actual["short_label"] == "CUDA PE"


def test_build_helpers() -> None:
    """Validate legacy report generation."""

    provider = make_provider()

    presentation = {
        "global_eff": {
            "label": "== Global Efficiency",
            "plot_order": 0,
        },
        "parallel_eff": {
            "label": "-- Parallel Efficiency",
            "plot_order": 1,
        },
    }

    result = provider.build(presentation)

    assert (
        result["global_eff"]["label"]
        == "== Global Efficiency"
    )

    assert (
        result["parallel_eff"]["plot_order"]
        == 1
    )

    assert result["global_eff"]["meaning"]

    alias = provider.build_legacy_info(
        presentation
    )

    assert alias == result

    runtime_result = provider.build(
        {
            "omp_parallel_eff": {
                "label": "-- CUDA Parallel Efficiency",
            }
        },
        runtime="CUDA",
        runtime_family="cuda",
    )

    info = runtime_result["omp_parallel_eff"]

    assert (
        info["label"]
        == "-- CUDA Parallel Efficiency"
    )

    assert info["short_label"] == "CUDA PE"

    assert "CUDA" in info["meaning"]

    assert_raises(
        TypeError,
        provider.build,
        {"global_eff": "invalid"},
        contains="must be a mapping",
    )

    original = {
        "global_eff": {
            "label": "Global Efficiency",
            "plot_order": 0,
        }
    }

    cloned = PerformanceKnowledgeProvider.clone_legacy_info(
        original
    )

    assert cloned == original
    assert cloned is not original
    assert cloned["global_eff"] is not original["global_eff"]

    cloned["global_eff"]["label"] = "Changed"

    assert (
        original["global_eff"]["label"]
        == "Global Efficiency"
    )


def test_default_provider() -> None:
    """Validate singleton provider."""

    first = get_default_provider()
    second = get_default_provider()

    assert isinstance(
        first,
        PerformanceKnowledgeProvider,
    )

    assert first is second


def main() -> None:

    print()
    print("=" * 72)
    print("BasicAnalysis Provider Tests")
    print("=" * 72)

    tests = (
        ("Provider construction", test_provider_construction),
        ("Threshold validation", test_threshold_validation),
        ("Metric resolution", test_metric_resolution),
        ("Runtime templates", test_runtime_templates_and_aliases),
        ("Labels", test_labels_and_thresholds),
        ("Status classification", test_status_classification),
        ("Cache", test_cache_behavior),
        ("Immutability", test_immutability),
        ("Legacy compatibility", test_legacy_compatibility),
        ("Build helpers", test_build_helpers),
        ("Default provider", test_default_provider),
    )

    passed = 0

    for name, test in tests:
        run_test(name, test)
        passed += 1

    print("=" * 72)
    print(f"All {passed} provider test groups passed.")
    print("=" * 72)
    print()


if __name__ == "__main__":
    main()
