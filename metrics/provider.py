"""Typed semantic access to the BasicAnalysis metric knowledge base.

This module defines the application-facing semantic API for performance
metrics. It sits above :mod:`metrics.knowledge_base`:

* ``MetricKnowledgeBase`` loads, validates, and resolves YAML entries.
* ``PerformanceKnowledgeProvider`` converts resolved entries into immutable,
  typed domain objects and provides common semantic operations.
* Report and analysis modules consume the provider instead of depending on
  the YAML representation directly.

The provider preserves the current legacy-dictionary interface so existing
BasicAnalysis code can be migrated incrementally.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import math
from threading import RLock
from types import MappingProxyType
from typing import Any, Iterable, Mapping

from .knowledge_base import MetricKnowledgeBase, get_default_knowledge_base


DEFAULT_CRITICAL_THRESHOLD = 60.0
DEFAULT_ATTENTION_THRESHOLD = 85.0
DEFAULT_REFERENCE_VALUE = 100.0


class MetricStatus(str, Enum):
    """Semantic classification of a metric value."""

    UNAVAILABLE = "unavailable"
    CRITICAL = "critical"
    ATTENTION = "attention"
    ACCEPTABLE = "acceptable"
    ABOVE_REFERENCE = "above_reference"


@dataclass(frozen=True, slots=True)
class MetricThresholds:
    """Thresholds used to classify an efficiency metric."""

    critical: float = DEFAULT_CRITICAL_THRESHOLD
    attention: float = DEFAULT_ATTENTION_THRESHOLD
    reference: float = DEFAULT_REFERENCE_VALUE

    def __post_init__(self) -> None:
        values = {
            "critical": self.critical,
            "attention": self.attention,
            "reference": self.reference,
        }

        for name, value in values.items():
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise TypeError(
                    f"Metric threshold '{name}' must be numeric, got {value!r}."
                )

            if not math.isfinite(float(value)):
                raise ValueError(
                    f"Metric threshold '{name}' must be finite, got {value!r}."
                )

        if self.critical >= self.attention:
            raise ValueError(
                "The critical threshold must be lower than the attention "
                "threshold."
            )

        if self.attention > self.reference:
            raise ValueError(
                "The attention threshold must not exceed the reference value."
            )


@dataclass(frozen=True, slots=True)
class MetricKnowledge:
    """Immutable, resolved semantic description of one performance metric."""

    id: str
    requested_id: str
    name: str
    short_name: str
    family: str
    analysis_level: str
    metric_type: str
    definition: str

    interpretation_low: str
    interpretation_high: str
    interpretation_above_100: str

    formula: Mapping[str, Any]
    derivation: str
    depends_on: tuple[str, ...]
    assumptions: tuple[str, ...]
    typical_causes: tuple[str, ...]
    next_steps: tuple[str, ...]
    children: tuple[str, ...]
    sources: tuple[Mapping[str, Any], ...]

    thresholds: MetricThresholds

    @property
    def label(self) -> str:
        """Return the full user-facing label."""
        return self.name

    @property
    def clean_label(self) -> str:
        """Return the label without legacy presentation markers."""
        return _clean_label(self.name)

    @property
    def meaning(self) -> str:
        """Compatibility synonym for ``definition``."""
        return self.definition

    @property
    def dependencies(self) -> tuple[str, ...]:
        """Compatibility synonym for ``depends_on``."""
        return self.depends_on

    @property
    def causes(self) -> tuple[str, ...]:
        """Compatibility synonym for ``typical_causes``."""
        return self.typical_causes

    @property
    def source_details(self) -> tuple[Mapping[str, Any], ...]:
        """Return the expanded source descriptions."""
        return self.sources


class PerformanceKnowledgeProvider:
    """Semantic API for BasicAnalysis metric knowledge."""

    def __init__(
        self,
        knowledge_base: MetricKnowledgeBase,
        *,
        default_thresholds: MetricThresholds | None = None,
        enable_cache: bool = True,
    ) -> None:
        if not isinstance(knowledge_base, MetricKnowledgeBase):
            raise TypeError(
                "knowledge_base must be a MetricKnowledgeBase instance."
            )

        self._knowledge_base = knowledge_base
        self._default_thresholds = default_thresholds or MetricThresholds()
        self._enable_cache = bool(enable_cache)
        self._cache: dict[
            tuple[str, str | None, str | None],
            MetricKnowledge,
        ] = {}
        self._cache_lock = RLock()

    @property
    def knowledge_base(self) -> MetricKnowledgeBase:
        """Return the wrapped knowledge-base instance."""
        return self._knowledge_base

    @property
    def default_thresholds(self) -> MetricThresholds:
        """Return provider-level fallback thresholds."""
        return self._default_thresholds

    @property
    def cache_enabled(self) -> bool:
        """Return whether resolved metric caching is enabled."""
        return self._enable_cache

    @property
    def cache_size(self) -> int:
        """Return the number of cached resolved metrics."""
        with self._cache_lock:
            return len(self._cache)

    def clear_cache(self) -> None:
        """Remove all cached resolved metric objects."""
        with self._cache_lock:
            self._cache.clear()

    def canonical_id(self, metric_id: str) -> str:
        """Return the canonical identifier for a metric or historical alias."""
        return self._knowledge_base.canonical_id(metric_id)

    def get(
        self,
        metric_id: str,
        *,
        runtime: str | None = None,
        runtime_family: str | None = None,
    ) -> MetricKnowledge:
        """Return one resolved immutable metric object."""
        cache_key = self._cache_key(
            metric_id,
            runtime=runtime,
            runtime_family=runtime_family,
        )

        if self._enable_cache:
            with self._cache_lock:
                cached = self._cache.get(cache_key)
            if cached is not None:
                return cached

        entry = self._knowledge_base.get(
            metric_id,
            runtime=runtime,
            runtime_family=runtime_family,
        )
        metric = self._build_metric(entry)

        if self._enable_cache:
            with self._cache_lock:
                existing = self._cache.setdefault(cache_key, metric)
            return existing

        return metric

    def metric(
        self,
        metric_id: str,
        *,
        runtime: str | None = None,
        runtime_family: str | None = None,
    ) -> MetricKnowledge:
        """Alias for :meth:`get`."""
        return self.get(
            metric_id,
            runtime=runtime,
            runtime_family=runtime_family,
        )

    def get_many(
        self,
        metric_ids: Iterable[str],
        *,
        runtime: str | None = None,
        runtime_family: str | None = None,
    ) -> dict[str, MetricKnowledge]:
        """Return resolved metrics keyed by the requested identifiers."""
        return {
            metric_id: self.get(
                metric_id,
                runtime=runtime,
                runtime_family=runtime_family,
            )
            for metric_id in metric_ids
        }

    def metrics(
        self,
        metric_ids: Iterable[str],
        *,
        runtime: str | None = None,
        runtime_family: str | None = None,
    ) -> dict[str, MetricKnowledge]:
        """Alias for :meth:`get_many`."""
        return self.get_many(
            metric_ids,
            runtime=runtime,
            runtime_family=runtime_family,
        )

    def label(
        self,
        metric_id: str,
        *,
        runtime: str | None = None,
        runtime_family: str | None = None,
        short: bool = False,
    ) -> str:
        """Return the full or short resolved label for a metric."""
        metric = self.get(
            metric_id,
            runtime=runtime,
            runtime_family=runtime_family,
        )
        return metric.short_name if short else metric.name

    def clean_label(
        self,
        metric_id: str,
        *,
        runtime: str | None = None,
        runtime_family: str | None = None,
        short: bool = False,
    ) -> str:
        """Return a normalized full or short metric label."""
        return _clean_label(
            self.label(
                metric_id,
                runtime=runtime,
                runtime_family=runtime_family,
                short=short,
            )
        )

    def thresholds(
        self,
        metric_id: str,
        *,
        runtime: str | None = None,
        runtime_family: str | None = None,
    ) -> MetricThresholds:
        """Return resolved classification thresholds for a metric."""
        return self.get(
            metric_id,
            runtime=runtime,
            runtime_family=runtime_family,
        ).thresholds

    def status(
        self,
        metric_id: str,
        value: Any,
        *,
        runtime: str | None = None,
        runtime_family: str | None = None,
    ) -> MetricStatus:
        """Classify a metric value using its resolved thresholds."""
        numeric_value = _coerce_finite_float(value)

        if numeric_value is None:
            return MetricStatus.UNAVAILABLE

        thresholds = self.thresholds(
            metric_id,
            runtime=runtime,
            runtime_family=runtime_family,
        )

        if numeric_value > thresholds.reference:
            return MetricStatus.ABOVE_REFERENCE

        if numeric_value < thresholds.critical:
            return MetricStatus.CRITICAL

        if numeric_value < thresholds.attention:
            return MetricStatus.ATTENTION

        return MetricStatus.ACCEPTABLE

    def is_critical(
        self,
        metric_id: str,
        value: Any,
        *,
        runtime: str | None = None,
        runtime_family: str | None = None,
    ) -> bool:
        """Return whether a value belongs to the critical range."""
        return self.status(
            metric_id,
            value,
            runtime=runtime,
            runtime_family=runtime_family,
        ) is MetricStatus.CRITICAL

    def requires_attention(
        self,
        metric_id: str,
        value: Any,
        *,
        runtime: str | None = None,
        runtime_family: str | None = None,
    ) -> bool:
        """Return whether a value is below the attention threshold."""
        return self.status(
            metric_id,
            value,
            runtime=runtime,
            runtime_family=runtime_family,
        ) in {
            MetricStatus.CRITICAL,
            MetricStatus.ATTENTION,
        }

    def is_acceptable(
        self,
        metric_id: str,
        value: Any,
        *,
        runtime: str | None = None,
        runtime_family: str | None = None,
        include_above_reference: bool = True,
    ) -> bool:
        """Return whether a value is acceptable for threshold filtering."""
        status = self.status(
            metric_id,
            value,
            runtime=runtime,
            runtime_family=runtime_family,
        )

        if status is MetricStatus.ACCEPTABLE:
            return True

        return (
            include_above_reference
            and status is MetricStatus.ABOVE_REFERENCE
        )

    def is_above_reference(
        self,
        metric_id: str,
        value: Any,
        *,
        runtime: str | None = None,
        runtime_family: str | None = None,
    ) -> bool:
        """Return whether a value exceeds the metric reference value."""
        return self.status(
            metric_id,
            value,
            runtime=runtime,
            runtime_family=runtime_family,
        ) is MetricStatus.ABOVE_REFERENCE

    def to_legacy_info(
        self,
        metric_id: str,
        *,
        runtime: str | None = None,
        runtime_family: str | None = None,
    ) -> dict[str, Any]:
        """Return the legacy report dictionary for one metric."""
        return self._knowledge_base.as_legacy_info(
            metric_id,
            runtime=runtime,
            runtime_family=runtime_family,
        )

    def legacy_info(
        self,
        metric_id: str,
        *,
        runtime: str | None = None,
        runtime_family: str | None = None,
    ) -> dict[str, Any]:
        """Alias for :meth:`to_legacy_info`."""
        return self.to_legacy_info(
            metric_id,
            runtime=runtime,
            runtime_family=runtime_family,
        )

    def build(
        self,
        presentation: Mapping[str, Mapping[str, Any]],
        *,
        runtime: str | None = None,
        runtime_family: str | None = None,
    ) -> dict[str, dict[str, Any]]:
        """Build legacy report metadata with presentation-only overrides."""
        result: dict[str, dict[str, Any]] = {}

        for metric_id, overrides in presentation.items():
            if not isinstance(overrides, Mapping):
                raise TypeError(
                    f"Overrides for metric '{metric_id}' must be a mapping."
                )

            info = self.to_legacy_info(
                metric_id,
                runtime=runtime,
                runtime_family=runtime_family,
            )
            info.update(dict(overrides))
            result[metric_id] = info

        return result

    def build_legacy_info(
        self,
        presentation: Mapping[str, Mapping[str, Any]],
        *,
        runtime: str | None = None,
        runtime_family: str | None = None,
    ) -> dict[str, dict[str, Any]]:
        """Compatibility alias for :meth:`build`."""
        return self.build(
            presentation,
            runtime=runtime,
            runtime_family=runtime_family,
        )

    @staticmethod
    def clone_legacy_info(
        metric_info: Mapping[str, Mapping[str, Any]],
    ) -> dict[str, dict[str, Any]]:
        """Return safe shallow copies of legacy metric dictionaries."""
        return {
            metric_id: dict(info)
            for metric_id, info in metric_info.items()
        }

    def _cache_key(
        self,
        metric_id: str,
        *,
        runtime: str | None,
        runtime_family: str | None,
    ) -> tuple[str, str | None, str | None]:
        canonical_id = self.canonical_id(metric_id)
        normalized_runtime = _normalize_context_value(runtime)
        normalized_family = _normalize_context_value(
            runtime_family
            or (runtime.lower() if runtime else None)
        )
        return canonical_id, normalized_runtime, normalized_family

    def _build_metric(self, entry: Mapping[str, Any]) -> MetricKnowledge:
        interpretation = _as_mapping(entry.get("interpretation"))
        thresholds = self._resolve_thresholds(entry.get("thresholds"))

        name = _required_string(entry, "name")

        return MetricKnowledge(
            id=_required_string(entry, "id"),
            requested_id=_required_string(entry, "requested_id"),
            name=name,
            short_name=_optional_string(
                entry.get("short_name"),
                default=name,
            ),
            family=_optional_string(entry.get("family")),
            analysis_level=_required_string(entry, "analysis_level"),
            metric_type=_required_string(entry, "metric_type"),
            definition=_required_string(entry, "definition"),
            interpretation_low=_optional_string(
                interpretation.get("low")
            ),
            interpretation_high=_optional_string(
                interpretation.get("high")
            ),
            interpretation_above_100=_optional_string(
                interpretation.get("above_100")
            ),
            formula=_freeze_mapping(
                _as_mapping(entry.get("formula"))
            ),
            derivation=_optional_string(entry.get("derivation")),
            depends_on=_string_tuple(entry.get("depends_on")),
            assumptions=_string_tuple(entry.get("assumptions")),
            typical_causes=_string_tuple(entry.get("typical_causes")),
            next_steps=_string_tuple(entry.get("next_steps")),
            children=_string_tuple(entry.get("children")),
            sources=tuple(
                _freeze_mapping(source)
                for source in _mapping_sequence(
                    entry.get("source_details")
                )
            ),
            thresholds=thresholds,
        )

    def _resolve_thresholds(self, value: Any) -> MetricThresholds:
        if value is None:
            return self._default_thresholds

        mapping = _as_mapping(value)

        return MetricThresholds(
            critical=_threshold_value(
                mapping,
                "critical",
                self._default_thresholds.critical,
            ),
            attention=_threshold_value(
                mapping,
                "attention",
                self._default_thresholds.attention,
            ),
            reference=_threshold_value(
                mapping,
                "reference",
                self._default_thresholds.reference,
            ),
        )


def _required_string(mapping: Mapping[str, Any], key: str) -> str:
    value = mapping.get(key)

    if not isinstance(value, str) or not value.strip():
        raise ValueError(
            f"Resolved metric field '{key}' must be a non-empty string."
        )

    return value


def _optional_string(value: Any, default: str = "") -> str:
    if value is None:
        return default

    if not isinstance(value, str):
        raise TypeError(f"Expected a string value, got {value!r}.")

    return value


def _string_tuple(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()

    if isinstance(value, str):
        raise TypeError(
            "Expected a sequence of strings, got a single string."
        )

    try:
        items = tuple(value)
    except TypeError as error:
        raise TypeError(
            f"Expected a sequence of strings, got {value!r}."
        ) from error

    for item in items:
        if not isinstance(item, str):
            raise TypeError(
                f"Expected a sequence of strings, got item {item!r}."
            )

    return items


def _as_mapping(value: Any) -> Mapping[str, Any]:
    if value is None:
        return {}

    if not isinstance(value, Mapping):
        raise TypeError(f"Expected a mapping, got {value!r}.")

    return value


def _mapping_sequence(value: Any) -> tuple[Mapping[str, Any], ...]:
    if value is None:
        return ()

    if isinstance(value, (str, bytes, Mapping)):
        raise TypeError(
            f"Expected a sequence of mappings, got {value!r}."
        )

    try:
        items = tuple(value)
    except TypeError as error:
        raise TypeError(
            f"Expected a sequence of mappings, got {value!r}."
        ) from error

    for item in items:
        if not isinstance(item, Mapping):
            raise TypeError(
                f"Expected a sequence of mappings, got item {item!r}."
            )

    return items


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return _freeze_mapping(value)

    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)

    if isinstance(value, tuple):
        return tuple(_freeze(item) for item in value)

    if isinstance(value, set):
        return frozenset(_freeze(item) for item in value)

    return value


def _freeze_mapping(value: Mapping[str, Any]) -> Mapping[str, Any]:
    return MappingProxyType(
        {
            key: _freeze(item)
            for key, item in value.items()
        }
    )


def _threshold_value(
    mapping: Mapping[str, Any],
    key: str,
    default: float,
) -> float:
    value = mapping.get(key, default)

    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(
            f"Metric threshold '{key}' must be numeric, got {value!r}."
        )

    return float(value)


def _coerce_finite_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None

    try:
        numeric_value = float(value)
    except (TypeError, ValueError):
        return None

    if not math.isfinite(numeric_value):
        return None

    return numeric_value


def _normalize_context_value(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def _clean_label(label: str) -> str:
    return (
        label
        .replace("-", "")
        .replace("=", "")
        .replace("*", "")
        .strip()
    )


_default_provider: PerformanceKnowledgeProvider | None = None
_default_provider_lock = RLock()


def get_default_provider() -> PerformanceKnowledgeProvider:
    """Return a lazily created process-wide semantic provider."""
    global _default_provider

    if _default_provider is None:
        with _default_provider_lock:
            if _default_provider is None:
                _default_provider = PerformanceKnowledgeProvider(
                    get_default_knowledge_base()
                )

    return _default_provider
