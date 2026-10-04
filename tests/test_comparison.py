import io
import unittest

from contextlib import redirect_stdout

from comparison import (
    NOT_APPLICABLE,
    build_comparison_device_rows,
    build_comparison_rows,
    check_comparison_support,
    clear_reference_metrics,
    get_comparison_scaling_info,
    get_programming_model,
    get_second_level_runtime,
    is_comparison_mode,
    is_gpu_model,
)


CUDA = "cuda.prv"
HIP = "hip.prv"
MPI = "mpi.prv"
OMP = "mpi_omp.prv"


def _factors(keys, values):
    """Create a [metric key][trace] dictionary."""
    return {
        key: dict(values)
        for key in keys
    }


class ProgrammingModelTests(unittest.TestCase):

    def test_get_programming_model(self):
        self.assertEqual(get_programming_model("Detailed+MPI+CUDA"), "MPI+CUDA")
        self.assertEqual(get_programming_model("Detailed+MPI"), "MPI")
        self.assertEqual(get_programming_model("Burst+MPI"), "MPI")
        self.assertEqual(get_programming_model("Sampling"), "Sampling")

    def test_gpu_and_second_level_runtime(self):
        self.assertTrue(is_gpu_model("Detailed+MPI+CUDA"))
        self.assertTrue(is_gpu_model("Detailed+MPI+HIP"))
        self.assertFalse(is_gpu_model("Detailed+MPI+OpenMP"))

        self.assertEqual(get_second_level_runtime("Detailed+MPI+OpenMP"), "OpenMP")
        self.assertIsNone(get_second_level_runtime("Detailed+MPI"))
        self.assertIsNone(get_second_level_runtime("Detailed+MPI+CUDA"))


class ComparisonModeTests(unittest.TestCase):

    def test_same_model_is_not_comparison(self):
        trace_mode = {"a": "Detailed+MPI", "b": "Detailed+MPI"}
        self.assertFalse(is_comparison_mode(["a", "b"], trace_mode))

    def test_single_trace_is_not_comparison(self):
        self.assertFalse(is_comparison_mode([CUDA], {CUDA: "Detailed+MPI+CUDA"}))

    def test_different_models_are_comparison(self):
        trace_mode = {CUDA: "Detailed+MPI+CUDA", MPI: "Detailed+MPI"}
        self.assertTrue(is_comparison_mode([CUDA, MPI], trace_mode))

    def test_cuda_vs_hip_is_comparison(self):
        trace_mode = {CUDA: "Detailed+MPI+CUDA", HIP: "Detailed+MPI+HIP"}
        self.assertTrue(is_comparison_mode([CUDA, HIP], trace_mode))

    def test_burst_vs_detailed_same_model_is_not_comparison(self):
        trace_mode = {"a": "Burst+MPI", "b": "Detailed+MPI"}
        self.assertFalse(is_comparison_mode(["a", "b"], trace_mode))

    def test_burst_trace_in_comparison_stops(self):
        trace_mode = {CUDA: "Detailed+MPI+CUDA", "burst.prv": "Burst+MPI"}

        output = io.StringIO()
        with redirect_stdout(output), self.assertRaises(SystemExit):
            check_comparison_support([CUDA, "burst.prv"], trace_mode)

        self.assertIn("burst.prv (Burst+MPI)", output.getvalue())

    def test_supported_comparison_does_not_stop(self):
        trace_mode = {CUDA: "Detailed+MPI+CUDA", MPI: "Detailed+MPI"}
        check_comparison_support([CUDA, MPI], trace_mode)

    def test_scaling_info_disables_scaling_analysis(self):
        scaling_info = get_comparison_scaling_info()
        self.assertFalse(scaling_info.has_scaling_analysis)
        self.assertEqual(scaling_info.selected, "strong")


class ComparisonRowsTests(unittest.TestCase):

    def setUp(self):
        self.trace_mode = {
            CUDA: "Detailed+MPI+CUDA",
            MPI: "Detailed+MPI",
            OMP: "Detailed+MPI+OpenMP",
        }

        self.mod_factors = _factors(
            ("parallel_eff", "load_balance", "comm_eff",
             "serial_eff", "transfer_eff"),
            {CUDA: 1.0, MPI: 2.0, OMP: 3.0},
        )
        self.hybrid_factors = _factors(
            ("mpi_parallel_eff", "mpi_load_balance", "mpi_comm_eff",
             "serial_eff", "transfer_eff", "omp_parallel_eff",
             "omp_load_balance", "omp_comm_eff"),
            {CUDA: 10.0, MPI: 'N/A', OMP: 30.0},
        )
        self.host_factors = _factors(
            ("host_parallel_eff", "mpi_parallel_eff", "mpi_load_balance",
             "mpi_comm_eff", "serial_eff", "transfer_eff",
             "dev_offload_eff"),
            {CUDA: 100.0, MPI: 'Non-Avail', OMP: 'Non-Avail'},
        )
        self.device_factors = _factors(
            ("dev_parallel_eff", "dev_load_balance", "dev_comm_eff",
             "dev_orches_eff"),
            {CUDA: 50.0, MPI: 'N/A', OMP: 'N/A'},
        )

    def _rows(self, trace_list):
        return dict(build_comparison_rows(
            trace_list,
            self.trace_mode,
            self.mod_factors,
            self.hybrid_factors,
            self.host_factors,
        ))

    def test_each_trace_uses_its_own_model_metrics(self):
        rows = self._rows([CUDA, MPI, OMP])

        mpi_pe = rows['-- MPI Parallel efficiency']
        self.assertEqual(mpi_pe[CUDA], 100.0)  # host_factors
        self.assertEqual(mpi_pe[MPI], 2.0)     # mod_factors
        self.assertEqual(mpi_pe[OMP], 30.0)    # hybrid_factors

        top = rows['Host Parallel efficiency']
        self.assertEqual(top[CUDA], 100.0)
        self.assertEqual(top[MPI], 2.0)
        self.assertEqual(top[OMP], 3.0)

    def test_not_applicable_cells_are_empty(self):
        rows = self._rows([CUDA, MPI, OMP])

        omp_pe = rows['-- OpenMP Parallel efficiency']
        self.assertEqual(omp_pe[CUDA], NOT_APPLICABLE)
        self.assertEqual(omp_pe[MPI], NOT_APPLICABLE)
        self.assertEqual(omp_pe[OMP], 30.0)

        offload = rows['-- Device Offload efficiency']
        self.assertEqual(offload[CUDA], 100.0)
        self.assertEqual(offload[MPI], NOT_APPLICABLE)
        self.assertEqual(offload[OMP], NOT_APPLICABLE)

    def test_cpu_only_comparison_uses_parallel_efficiency_label(self):
        rows = self._rows([MPI, OMP])

        self.assertIn('Parallel efficiency', rows)
        self.assertNotIn('Host Parallel efficiency', rows)
        self.assertNotIn('-- Device Offload efficiency', rows)

        device_rows = build_comparison_device_rows(
            [MPI, OMP], self.trace_mode, self.device_factors
        )
        self.assertEqual(device_rows, [])

    def test_device_rows_only_filled_for_gpu_traces(self):
        device_rows = dict(build_comparison_device_rows(
            [CUDA, MPI], self.trace_mode, self.device_factors
        ))

        device_pe = device_rows['DEVICE Parallel efficiency']
        self.assertEqual(device_pe[CUDA], 50.0)
        self.assertEqual(device_pe[MPI], NOT_APPLICABLE)


class ClearReferenceMetricsTests(unittest.TestCase):

    def test_reference_metrics_become_not_applicable(self):
        trace_list = [CUDA, MPI]
        mod_factors = _factors(
            ("global_eff", "comp_scale", "parallel_eff"),
            {CUDA: 90.0, MPI: 0.0},
        )
        other_metrics = _factors(
            ("efficiency", "speedup"),
            {CUDA: 1.0, MPI: 0.5},
        )

        clear_reference_metrics(trace_list, {
            'mod_factors': mod_factors,
            'other_metrics': other_metrics,
        })

        self.assertEqual(mod_factors['comp_scale'][MPI], 'N/A')
        self.assertEqual(mod_factors['global_eff'][CUDA], 'N/A')
        self.assertEqual(other_metrics['efficiency'][MPI], 'N/A')

        # Per-trace metrics and runtime Speedup are kept.
        self.assertEqual(mod_factors['parallel_eff'][CUDA], 90.0)
        self.assertEqual(other_metrics['speedup'][MPI], 0.5)


if __name__ == "__main__":
    unittest.main()
