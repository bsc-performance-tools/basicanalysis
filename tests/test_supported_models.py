import io
import sys
import unittest
from unittest import mock

from tracemetadata import check_supported_models, unsupported_model


class TestSupportedModels(unittest.TestCase):

    def test_supported(self):
        for mode in ('Detailed+MPI', 'Detailed+OpenMP', 'Detailed+MPI+OpenMP',
                     'Detailed+MPI+Pthreads', 'Detailed+MPI+CUDA', 'Detailed+MPI+HIP',
                     'Detailed+CUDA', 'Detailed+HIP', 'nsys2prv+CUDA', 'Burst+MPI',
                     'Sampling', 'Detailed'):
            self.assertIsNone(unsupported_model(mode), mode)

    def test_gpu_with_host_threading(self):
        for mode in ('Detailed+MPI+OpenMP+CUDA', 'Detailed+MPI+Pthreads+CUDA',
                     'Detailed+OpenMP+CUDA', 'Detailed+MPI+OpenMP+HIP'):
            self.assertIsNotNone(unsupported_model(mode), mode)

    def test_check_stops_and_reports_the_mode(self):
        out = io.StringIO()
        trace_mode = {'a.prv': 'Detailed+MPI+CUDA',
                      'b.prv': 'Detailed+MPI+OpenMP+CUDA'}
        with mock.patch.object(sys, 'stdout', out), \
                self.assertRaises(SystemExit) as stop:
            check_supported_models(['a.prv', 'b.prv'], trace_mode)
        self.assertEqual(stop.exception.code, 1)
        text = out.getvalue()
        self.assertIn('b.prv', text)
        self.assertIn('Trace mode: Detailed+MPI+OpenMP+CUDA', text)
        self.assertNotIn('a.prv', text)

    def test_check_passes(self):
        check_supported_models(['a.prv'], {'a.prv': 'Detailed+MPI+CUDA'})


if __name__ == '__main__':
    unittest.main()
