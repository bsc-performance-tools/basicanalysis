import unittest

from configuration import format_gpu_configuration_label
from report.model_names import (
    HETEROGENEOUS_MODEL,
    RUNTIME_MODEL,
    hybrid_model_title,
    inner_level_name,
    is_hybrid_model_title,
    outer_level_name,
)


class TestModelNames(unittest.TestCase):

    def test_tabs(self):
        self.assertEqual(RUNTIME_MODEL, "Runtime Model")
        self.assertEqual(HETEROGENEOUS_MODEL, "Heterogeneous Model")

    def test_hybrid_and_levels(self):
        self.assertEqual(hybrid_model_title("CUDA"), "Hybrid (MPI+CUDA)")
        self.assertTrue(is_hybrid_model_title("Hybrid (MPI+HIP)"))
        self.assertFalse(is_hybrid_model_title("MPI"))
        self.assertFalse(is_hybrid_model_title(None))
        self.assertEqual(outer_level_name(), "Outer (MPI)")
        self.assertEqual(inner_level_name("OpenMP"), "Inner (OpenMP)")


class TestGpuConfigurationLabel(unittest.TestCase):

    def test_processes_times_gpus(self):
        self.assertEqual(format_gpu_configuration_label(4, 4), "4 × 1 GPU")
        self.assertEqual(format_gpu_configuration_label(2, 8), "2 × 4 GPUs")
        self.assertEqual(format_gpu_configuration_label("1", "1"), "1 × 1 GPU")

    def test_shared_gpus_and_unknown(self):
        self.assertEqual(format_gpu_configuration_label(8, 4), "8 (4 GPUs)")
        self.assertEqual(format_gpu_configuration_label(4, None), "4")
        self.assertEqual(format_gpu_configuration_label(None, None), "-")

    def test_trace_id(self):
        self.assertEqual(
            format_gpu_configuration_label(4, 4, trace_id="T2"),
            "4 × 1 GPU [T2]",
        )


if __name__ == "__main__":
    unittest.main()
