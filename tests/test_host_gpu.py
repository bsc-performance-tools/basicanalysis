import os
import tempfile
import unittest

from configuration import format_configuration_label
from rawdata import compute_host_outside_runtime
from tracemetadata import host_runtime_of_mode, is_host_gpu_mode


class HostGpuModeTests(unittest.TestCase):

    def test_gpu_without_mpi(self):
        self.assertTrue(is_host_gpu_mode("Detailed+CUDA"))
        self.assertTrue(is_host_gpu_mode("Detailed+HIP"))

    def test_threaded_host_gpu(self):
        self.assertTrue(is_host_gpu_mode("Detailed+OpenMP+CUDA"))
        self.assertTrue(is_host_gpu_mode("Detailed+Pthreads+HIP"))

    def test_mpi_gpu_is_not_host_gpu(self):
        self.assertFalse(is_host_gpu_mode("Detailed+MPI+CUDA"))
        self.assertFalse(is_host_gpu_mode("Detailed+MPI+HIP"))

    def test_other_modes(self):
        for mode in ("Detailed+MPI", "Detailed+OpenMP", "Burst+MPI",
                     "Burst+CUDA", "Sampling"):
            self.assertFalse(is_host_gpu_mode(mode), mode)

    def test_host_runtime_of_mode(self):
        self.assertIsNone(host_runtime_of_mode("Detailed+CUDA"))
        self.assertEqual(host_runtime_of_mode("Detailed+OpenMP+CUDA"), "OpenMP")
        self.assertEqual(host_runtime_of_mode("Detailed+Pthreads+HIP"), "Pthreads")


class HostOutsideRuntimeTests(unittest.TestCase):
    """Host time outside the host runtime = useful + GPU runtime calls."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self._tmpdir.cleanup()

    def _write(self, name, rows):
        path = os.path.join(self._tmpdir.name, name)
        with open(path, "w") as f:
            f.write("\tvalue\t\n")
            for label, value in rows:
                f.write("{}\t{}\t\n".format(label, value))
            f.write("\nTotal\t0\t\n")
        return path

    def test_sum_per_host_thread(self):
        useful = self._write("useful.csv", [
            ("THREAD 1.1.1", 60.0),
            ("THREAD 1.1.2", 20.0),
            ("CUDA-D1.S1-node", 5.0),   # GPU rows are ignored
        ])
        gpu_calls = self._write("calls.csv", [
            ("THREAD 1.1.1", 30.0),
            ("THREAD 1.1.2", 10.0),
            ("CUDA-D1.S1-node", 0.0),
        ])

        total, average, maximum = compute_host_outside_runtime(
            useful, gpu_calls
        )

        self.assertEqual(total, 120.0)
        self.assertEqual(average, 60.0)
        self.assertEqual(maximum, 90.0)

    def test_missing_stats(self):
        self.assertIsNone(compute_host_outside_runtime(
            os.path.join(self._tmpdir.name, "missing.csv"),
            os.path.join(self._tmpdir.name, "missing2.csv"),
        ))


class GpuConfigurationLabelTests(unittest.TestCase):

    def test_host_threads_streams_devices(self):
        self.assertEqual(
            format_configuration_label(
                "gpu", processes=6, gpu_streams=5, devices=1,
            ),
            "6 (1+5) [1D]",
        )
        self.assertEqual(
            format_configuration_label(
                "gpu", processes=20, gpu_streams=16, devices=2,
            ),
            "20 (4+16) [2D]",
        )

    def test_fallback_without_streams_or_devices(self):
        self.assertEqual(
            format_configuration_label("gpu", processes=6, gpu_streams=5),
            "6",
        )
        # Classic model: streams and devices are not counted.
        self.assertEqual(
            format_configuration_label(
                "gpu", processes=6, gpu_streams=0.0, devices=0.0,
            ),
            "6",
        )


if __name__ == "__main__":
    unittest.main()
