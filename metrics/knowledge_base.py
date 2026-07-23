"""Load and validate the BasicAnalysis metric knowledge base.

The YAML file contains methodological knowledge.  This module contains only
loading, validation, template expansion, and compatibility helpers.
"""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from string import Formatter
from typing import Any, Iterable, Mapping

import yaml


DEFAULT_PATH = Path(__file__).with_name("definitions.yaml")
_REQUIRED_FIELDS = {
    "analysis_level",
    "metric_type",
}
_TEMPLATE_CONTEXT_FIELDS = {"runtime", "runtime_family"}


class MetricKnowledgeError(ValueError):
    """Raised when the knowledge-base structure is invalid."""


class MetricKnowledgeBase:
    """Validated, read-only access to metric knowledge."""

    def __init__(self, path: str | Path = DEFAULT_PATH) -> None:
        self.path = Path(path)
        self._document = self._load_document()
        self.sources: dict[str, dict[str, Any]] = self._document["sources"]
        self.metrics: dict[str, dict[str, Any]] = self._document["metrics"]
        self.aliases = self._build_alias_map()
        self._validate()

    def _load_document(self) -> dict[str, Any]:
        if not self.path.exists():
            raise MetricKnowledgeError(
                f"Metric knowledge file does not exist: {self.path}"
            )

        with self.path.open("r", encoding="utf-8") as handle:
            document = yaml.safe_load(handle)

        if not isinstance(document, dict):
            raise MetricKnowledgeError("Knowledge-base root must be a mapping.")

        for field in ("sources", "metrics"):
            if not isinstance(document.get(field), dict):
                raise MetricKnowledgeError(
                    f"Top-level field '{field}' must be a mapping."
                )

        return document

    def _build_alias_map(self) -> dict[str, str]:
        aliases: dict[str, str] = {}
        for metric_id, entry in self.metrics.items():
            for alias in entry.get("aliases", []):
                if alias in aliases or alias in self.metrics:
                    raise MetricKnowledgeError(
                        f"Duplicate or conflicting metric alias: {alias}"
                    )
                aliases[alias] = metric_id
        return aliases

    def _validate(self) -> None:
        for metric_id, entry in self.metrics.items():
            if not isinstance(entry, dict):
                raise MetricKnowledgeError(
                    f"Metric '{metric_id}' must be a mapping."
                )

            missing = [field for field in _REQUIRED_FIELDS if field not in entry]
            if missing:
                raise MetricKnowledgeError(
                    f"Metric '{metric_id}' is missing required fields: {missing}"
                )

            if not ("name" in entry or "name_template" in entry):
                raise MetricKnowledgeError(
                    f"Metric '{metric_id}' requires 'name' or 'name_template'."
                )

            if not ("definition" in entry or "definition_template" in entry):
                raise MetricKnowledgeError(
                    f"Metric '{metric_id}' requires 'definition' or "
                    "'definition_template'."
                )

            for child in entry.get("children", []):
                if child not in self.metrics:
                    raise MetricKnowledgeError(
                        f"Metric '{metric_id}' references unknown child '{child}'."
                    )

            for source_id in entry.get("sources", []):
                if source_id not in self.sources:
                    raise MetricKnowledgeError(
                        f"Metric '{metric_id}' references unknown source "
                        f"'{source_id}'."
                    )

            placeholders = _collect_template_fields(entry)
            unsupported = placeholders - _TEMPLATE_CONTEXT_FIELDS
            if unsupported:
                raise MetricKnowledgeError(
                    f"Metric '{metric_id}' uses unsupported template fields: "
                    f"{sorted(unsupported)}"
                )

    def canonical_id(self, metric_id: str) -> str:
        """Return the canonical ID for a canonical ID or historical alias."""
        if metric_id in self.metrics:
            return metric_id
        if metric_id in self.aliases:
            return self.aliases[metric_id]
        raise KeyError(f"Unknown metric: {metric_id}")

    def get(
        self,
        metric_id: str,
        *,
        runtime: str | None = None,
        runtime_family: str | None = None,
    ) -> dict[str, Any]:
        """Return one resolved metric entry.

        Template-based entries require ``runtime``. ``runtime_family`` defaults
        to the lowercase runtime name.
        """
        canonical_id = self.canonical_id(metric_id)
        entry = deepcopy(self.metrics[canonical_id])

        context = {
            "runtime": runtime,
            "runtime_family": runtime_family or (
                runtime.lower() if runtime else None
            ),
        }

        required_context = _collect_template_fields(entry)
        missing_context = [name for name in required_context if not context.get(name)]
        if missing_context:
            raise MetricKnowledgeError(
                f"Metric '{canonical_id}' requires template context: "
                f"{missing_context}"
            )

        resolved = _resolve_templates(entry, context)
        resolved["id"] = canonical_id
        resolved["requested_id"] = metric_id
        resolved["source_details"] = [
            {"id": source_id, **deepcopy(self.sources[source_id])}
            for source_id in resolved.get("sources", [])
        ]
        return resolved

    def get_many(
        self,
        metric_ids: Iterable[str],
        *,
        runtime: str | None = None,
        runtime_family: str | None = None,
    ) -> dict[str, dict[str, Any]]:
        """Return multiple resolved entries, keyed by the requested IDs."""
        return {
            metric_id: self.get(
                metric_id,
                runtime=runtime,
                runtime_family=runtime_family,
            )
            for metric_id in metric_ids
        }

    def as_legacy_info(
        self,
        metric_id: str,
        *,
        runtime: str | None = None,
        runtime_family: str | None = None,
    ) -> dict[str, Any]:
        """Adapt one entry to the dictionaries currently used by reports.

        This compatibility layer lets BasicAnalysis migrate incrementally.
        """
        metric = self.get(
            metric_id,
            runtime=runtime,
            runtime_family=runtime_family,
        )
        interpretation = metric.get("interpretation", {})

        return {
            "label": metric["name"],
            "short_label": metric.get("short_name", metric["name"]),
            "type": _humanize(metric["analysis_level"]),
            "meaning": metric["definition"],
            "low": interpretation.get("low", ""),
            "high": interpretation.get("high", ""),
            "above100": interpretation.get("above_100", ""),
            "action": " ".join(metric.get("next_steps", [])),
            "formula": metric.get("formula", {}),
            "typical_causes": metric.get("typical_causes", []),
            "sources": metric.get("source_details", []),
        }


def _collect_template_fields(value: Any, template_active: bool = False) -> set[str]:
    """Collect placeholders only from fields explicitly marked as templates."""
    fields: set[str] = set()

    if isinstance(value, str):
        if template_active:
            for _, field_name, _, _ in Formatter().parse(value):
                if field_name:
                    fields.add(field_name)
        return fields

    if isinstance(value, list):
        for child in value:
            fields.update(_collect_template_fields(child, template_active))
        return fields

    if isinstance(value, Mapping):
        for key, child in value.items():
            child_is_template = template_active or key.endswith("_template")
            fields.update(_collect_template_fields(child, child_is_template))
        return fields

    return fields


def _resolve_templates(
    value: Any,
    context: Mapping[str, str | None],
    template_active: bool = False,
) -> Any:
    """Resolve only fields explicitly marked with a ``_template`` suffix."""
    if isinstance(value, str):
        return value.format(**context) if template_active else value

    if isinstance(value, list):
        return [
            _resolve_templates(child, context, template_active)
            for child in value
        ]

    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, child in value.items():
            child_is_template = template_active or key.endswith("_template")
            resolved_key = (
                key[: -len("_template")]
                if key.endswith("_template")
                else key
            )
            result[resolved_key] = _resolve_templates(
                child,
                context,
                child_is_template,
            )
        return result

    return value


def _humanize(value: str) -> str:
    return value.replace("_", " ").strip().title()


_default_kb: MetricKnowledgeBase | None = None


def get_default_knowledge_base() -> MetricKnowledgeBase:
    """Return a lazily created process-wide knowledge-base instance."""
    global _default_kb
    if _default_kb is None:
        _default_kb = MetricKnowledgeBase()
    return _default_kb
