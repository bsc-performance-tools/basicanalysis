"""Names of the performance models shown in the report.

Only the names shown to the user live here; the internal identifiers (view
ids such as ``parallel-runtime-model`` and ``execution-domains``, section
types, CSS classes) do not change.

Report structure::

    [Runtime Model]                      [Heterogeneous Model]
       one runtime:  MPI, OpenMP, CUDA...   Device, Host
       MPI + X:      Hybrid (MPI+X)
                       Outer (MPI), Inner (X)
"""

# Navigation tab of the runtime-level model of the parallel efficiency.
RUNTIME_MODEL = "Runtime Model"

# Host/Device execution-domain model of accelerator applications.
HETEROGENEOUS_MODEL = "Heterogeneous Model"

# Names of the tables of the Heterogeneous Model.
HOST_DOMAIN = "Host"
DEVICE_DOMAIN = "Device"

# Name of the application-level table (Global efficiency).
APPLICATION = "Application"

HYBRID_PREFIX = "Hybrid"


def hybrid_model_title(inner_runtime):
    """Name of the composed MPI+X model, e.g. Hybrid (MPI+CUDA)."""
    return "{} (MPI+{})".format(HYBRID_PREFIX, inner_runtime)


def is_hybrid_model_title(title):
    """Whether a runtime model name is the composed MPI+X model."""
    return str(title or "").startswith(HYBRID_PREFIX + " (")


def outer_level_name(runtime="MPI"):
    """Outer level of the Hybrid model, e.g. Outer (MPI)."""
    return "Outer ({})".format(runtime)


def inner_level_name(runtime):
    """Inner level of the Hybrid model, e.g. Inner (CUDA)."""
    return "Inner ({})".format(runtime)
