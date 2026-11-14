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

    def test_released_extrae_openmp_target(self):
        # GCC runtime traced by the released Extrae: ompitrace (60000034)
        # and newompitrace (60010)
        for code in ('60000034', '60010'):
            prv = self._pcf("EVENT_TYPE\n0    %s    OpenMP target\n" % code)
            self.assertEqual(tracemetadata.detect_offload_directives(prv),
                             tracemetadata.OFFLOAD_OPENMP_TARGET, code)

    def test_label(self):
        self.assertEqual(tracemetadata.offload_directives_label(3),
                         'OpenMP target + OpenACC')
        self.assertEqual(tracemetadata.offload_directives_label(0), '')


MPI_CUDA_PCF = ("EVENT_TYPE\n"
                "0    50000001    MPI Point-to-point\n"
                "0    63000000    CUDA library call\n")


class OpenMPOffloadModeTest(unittest.TestCase):
    """OpenMP target constructs alone are offloading, not CPU threading:
    the trace stays MPI+CUDA instead of the unsupported MPI+OpenMP+CUDA."""

    def _mode(self, extra):
        folder = tempfile.mkdtemp()
        path = os.path.join(folder, 'app.pcf')
        with open(path, 'w') as handle:
            handle.write(MPI_CUDA_PCF + extra)
        return tracemetadata._detect_mode_from_pcf(path, 'Detailed')

    def test_target_only_is_not_openmp(self):
        for extra in ("0    60000034    OpenMP target\n",
                      "0    60000    OpenMP call\n0    60010    OpenMP Target\n"):
            self.assertEqual(self._mode(extra), 'Detailed+MPI+CUDA', extra)

    def test_parallel_regions_are_openmp(self):
        for extra in ("0    60000001    Parallel (OMP)\n0    60000034    OpenMP target\n",
                      "0    60000    OpenMP call\n0    60002    OpenMP Parallel\n"
                      "0    60010    OpenMP Target\n",
                      "0    60000018    Parallel function\n"):
            self.assertEqual(self._mode(extra), 'Detailed+MPI+OpenMP+CUDA', extra)


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
