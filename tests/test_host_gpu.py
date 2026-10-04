import unittest

from tracemetadata import is_host_gpu_mode


class HostGpuModeTests(unittest.TestCase):

    def test_gpu_without_mpi(self):
        self.assertTrue(is_host_gpu_mode("Detailed+CUDA"))
        self.assertTrue(is_host_gpu_mode("Detailed+HIP"))

    def test_mpi_gpu_is_not_host_gpu(self):
        self.assertFalse(is_host_gpu_mode("Detailed+MPI+CUDA"))
        self.assertFalse(is_host_gpu_mode("Detailed+MPI+HIP"))

    def test_other_modes(self):
        for mode in ("Detailed+MPI", "Detailed+OpenMP", "Burst+MPI", "Sampling"):
            self.assertFalse(is_host_gpu_mode(mode), mode)


if __name__ == "__main__":
    unittest.main()
