"""Rows of the hybrid model without the hierarchical limitation."""

NON_HIERARCHICAL_PAIRS = (
    ('nh_mpi_parallel_eff', 'mpi_parallel_eff'),
    ('nh_mpi_load_balance', 'mpi_load_balance'),
    ('nh_mpi_comm_eff', 'mpi_comm_eff'),
    ('nh_omp_parallel_eff', 'omp_parallel_eff'),
    ('nh_omp_load_balance', 'omp_load_balance'),
    ('nh_omp_comm_eff', 'omp_comm_eff'),
)

NON_HIERARCHICAL_KEYS = tuple(pair[0] for pair in NON_HIERARCHICAL_PAIRS)

# Differences below this are the precision of the timelines (SOD2D: 0.003).
VISIBLE_DIFFERENCE = 0.05


def differs_from_classic(hybrid_factors):
    """True when a row of the model differs from its classic row in a trace.

    A hierarchical code gets the same values, so the report does not repeat
    them. They stay in the CSV files.
    """
    for new_key, classic_key in NON_HIERARCHICAL_PAIRS:
        new_values = hybrid_factors.get(new_key) or {}
        classic_values = hybrid_factors.get(classic_key) or {}

        for trace, value in new_values.items():
            try:
                difference = abs(float(value) - float(classic_values[trace]))
            except (KeyError, TypeError, ValueError):
                continue

            if difference >= VISIBLE_DIFFERENCE:
                return True

    return False
