import unittest

from report.model_names import (
    HETEROGENEOUS_MODEL,
    hybrid_model_title,
    runtime_model_name,
    runtime_model_name_from_title,
)


class TestModelNames(unittest.TestCase):

    def test_runtime_model_name(self):
        self.assertEqual(runtime_model_name(True), "Hybrid Model")
        self.assertEqual(runtime_model_name(False), "Parallel Runtime Model")

    def test_titles(self):
        self.assertEqual(hybrid_model_title("CUDA"), "Hybrid Model: MPI + CUDA")
        self.assertEqual(runtime_model_name_from_title("Hybrid Model: MPI + HIP"),
                         "Hybrid Model")
        self.assertEqual(runtime_model_name_from_title("MPI Parallel Runtime Model"),
                         "Parallel Runtime Model")
        self.assertEqual(runtime_model_name_from_title(None),
                         "Parallel Runtime Model")

    def test_heterogeneous(self):
        self.assertEqual(HETEROGENEOUS_MODEL, "Heterogeneous Model")


if __name__ == "__main__":
    unittest.main()
