# BasicAnalysis metric knowledge schema

## Purpose

`definitions.yaml` is the methodological source of truth for metric names,
definitions, formulations, interpretation guidance, causes, diagnostic steps,
hierarchy, and provenance. Report code should render this knowledge; it should
not redefine it.

## Top-level fields

- `version`: schema/content version.
- `sources`: source registry keyed by stable source ID.
- `metrics`: metric registry keyed by stable canonical metric ID.

## Required metric fields

- `name` or `name_template`
- `analysis_level`
- `metric_type`
- `definition` or `definition_template`

## Recommended metric fields

- `short_name`
- `family`
- `formula`
- `interpretation`
- `typical_causes`
- `next_steps`
- `children`
- `sources`
- `aliases`

## Templates

Template entries are used when one conceptual metric is instantiated for
multiple runtimes. Supported placeholders are:

- `{runtime}`: display name, for example `CUDA` or `OpenMP`.
- `{runtime_family}`: normalized CSS/report family, for example `cuda`.

A field whose key ends in `_template` is exposed without that suffix after
resolution. Example:

```yaml
name_template: "{runtime} Parallel Efficiency"
```

becomes:

```python
{"name": "CUDA Parallel Efficiency"}
```

## Formula schema

```yaml
formula:
  text: Human-readable formula
  latex: LaTeX formula
  variables:
    Symbol: Meaning
  status: stable | model_specific | provisional
```

An empty LaTeX formula is permitted for a metric whose exact formulation still
needs methodological consolidation. Such entries should use
`status: model_specific` or `status: provisional`.

## Interpretation schema

```yaml
interpretation:
  low: Meaning of a low value
  high: Meaning of a high value
  above_100: Meaning of a value above 100 percent
```

## Analysis levels

- `application`
- `composed_runtime`
- `runtime_contribution`
- `runtime_specific`
- `execution_domain`
- `scalability`

These levels prevent a derived runtime contribution from being presented as an
isolated runtime-specific metric.

## Extension checklist

When adding a metric:

1. Select a stable canonical ID.
2. Classify its analysis level and family.
3. Define what it measures before writing the formula.
4. Add text and LaTeX formulations.
5. Define low/high/above-reference interpretation.
6. Add likely causes and concrete next diagnostic steps.
7. Link child metrics, if any.
8. Register methodological sources.
9. Run `python3 tests/test_knowledge_base.py`.
