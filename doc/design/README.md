# BasicAnalysis Design Documents (Work in Progress)

This directory contains the design documents of BasicAnalysis features that
are being defined or validated. They are **not** part of the User Guide: the
Sphinx sources are in `doc/source/`, so these documents are not included in
the HTML or PDF documentation. They are for internal use only: the packages
made with `git archive`, such as the release archives, leave this directory
out (`export-ignore` in `.gitattributes`).

Each document records the proposed metrics and definitions, the open
questions, and the validation performed with real traces. Formulas and
thresholds in these documents may change and must not be taken as the
behaviour of the released tool.

## Life cycle

1. **Design**: the document is created here and discussed.
2. **Implementation**: the feature is developed on its own branch, and the
   document is updated with the decisions and validation results.
3. **Validated**: the definitions that are implemented and validated are
   moved to the User Guide (mainly `06_metrics.rst`, and `09_limitations.rst`
   for the assumptions), and the release notes are updated. The design
   document is then removed or marked as implemented, with a reference to
   the User Guide section.

## Documents

| Document | Status | Branch |
|----------|--------|--------|
| [I/O Performance Model and Diagnostic Metrics](io_performance_model.rst) | Implementation in progress (factors, time diagnostics, request sizes, and files done) | `feature/io-metrics` |
| [GPU Metrics: States, Events, and the `.row` File](gpu_states_events_row.rst) | Decision recorded; future work proposed (Paraver views, fallback without `.row`) | — |
| [GPU Assessment Metrics from the vLLM POP Assessment](gpu_assessment_metrics.rst) | Proposal, for review by the team (metrics and Paraver views in five steps) | `feature/gpu-assessment-metrics` |
