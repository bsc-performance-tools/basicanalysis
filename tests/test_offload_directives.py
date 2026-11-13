"""Offloading directives: detection and Offloading LB / CommE (case 1 of
doc/design/three_runtime_hybrid.rst)."""
import os
import tempfile
import unittest

import hybridmetrics
import tracemetadata


class DetectOffloadDirectivesTest(unittest.TestCase):
    def _pcf(self, text):
        folder = tempfile.mkdtemp()
        with open(os.path.join(folder, 'app.pcf'), 'w') as handle:
            handle.write(text)
        return os.path.join(folder, 'app.prv')

    def test_openmp_target(self):
        prv = self._pcf("EVENT_TYPE\n0    70008    Target Offloading\n")
        self.assertEqual(tracemetadata.detect_offload_directives(prv),
                         tracemetadata.OFFLOAD_OPENMP_TARGET)

    def test_openacc_and_gz_name(self):
        prv = self._pcf("EVENT_TYPE\n0    66000000    OpenACC\n")
        self.assertEqual(
            tracemetadata.detect_offload_directives(prv + '.gz'),
            tracemetadata.OFFLOAD_OPENACC)

    def test_none_and_missing(self):
        prv = self._pcf("EVENT_TYPE\n0    63500006    HIP kernel\n"
                        "0    700080    other\n")
        self.assertEqual(tracemetadata.detect_offload_directives(prv), 0)
        self.assertEqual(
            tracemetadata.detect_offload_directives('/nonexistent/x.prv'), 0)

    def test_label(self):
        self.assertEqual(tracemetadata.offload_directives_label(3),
                         'OpenMP target + OpenACC')
        self.assertEqual(tracemetadata.offload_directives_label(0), '')


class OffloadContributionsTest(unittest.TestCase):
    # TLAB worked example of the design note (4 ranks, T = 89.04 s).
    useful = [8.01, 7.90, 7.99, 8.02]

    def _raw(self, directives=1, threads=4):
        return {
            'offload_directives': {'t': directives},
            'count_host_threads': {'t': threads},
            'useful_host': {'t': sum(self.useful)},
            'useful_host_max': {'t': max(self.useful)},
            'runtime': {'t': 89.04},
        }

    host = {'mpi_load_balance': {'t': 97.90}, 'mpi_comm_eff': {'t': 97.18}}

    def test_tlab_values(self):
        lb, comm = hybridmetrics._offload_contributions(
            self._raw(), self.host, 't', True, True, {'t': 4})
        self.assertAlmostEqual(lb, 101.68, delta=0.05)
        self.assertAlmostEqual(comm, 9.27, delta=0.02)

    def test_not_applicable(self):
        cases = [
            (self._raw(directives=0), True, {'t': 4}),   # no directives
            (self._raw(), False, {'t': 4}),              # not MPI+GPU
            (self._raw(threads=8), True, {'t': 4}),      # CPU threads compute
        ]
        for raw, is_mpi_gpu, ranks in cases:
            self.assertEqual(
                hybridmetrics._offload_contributions(
                    raw, self.host, 't', is_mpi_gpu, True, ranks),
                ('N/A', 'N/A'))

    def test_without_outside_mpi(self):
        self.assertEqual(
            hybridmetrics._offload_contributions(
                self._raw(), self.host, 't', True, False, {'t': 4}),
            ('Non-Avail', 'Non-Avail'))


if __name__ == '__main__':
    unittest.main()
