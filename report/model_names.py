"""Names of the performance models shown in the report.

Only the names shown to the user live here; the internal identifiers (view
ids such as ``parallel-runtime-model`` and ``execution-domains``, section
types, CSS classes) do not change.
"""

# Host/Device execution-domain model of accelerator applications.
HETEROGENEOUS_MODEL = "Heterogeneous Model"

# Runtime-level model of the parallel efficiency: with one parallel runtime
# (MPI, OpenMP, CUDA without MPI, ...) it is the Parallel Runtime Model; with
# MPI plus a second runtime (MPI+OpenMP, MPI+CUDA, MPI+HIP) it is the Hybrid
# Model.
PARALLEL_RUNTIME_MODEL = "Parallel Runtime Model"
HYBRID_MODEL = "Hybrid Model"


def runtime_model_name(hybrid):
    """Name of the runtime model: Hybrid Model for MPI+X executions."""
    return HYBRID_MODEL if hybrid else PARALLEL_RUNTIME_MODEL


def hybrid_model_title(inner_runtime):
    """Title of the composed MPI+X model, e.g. Hybrid Model: MPI + CUDA."""
    return "{}: MPI + {}".format(HYBRID_MODEL, inner_runtime)


def runtime_model_name_from_title(title):
    """Name of the runtime model from the title of its view."""
    return runtime_model_name(str(title or "").startswith(HYBRID_MODEL))
