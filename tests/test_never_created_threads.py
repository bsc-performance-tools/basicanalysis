"""Host threads that the application never created, and the fixed range of
the frequency histogram (Laplace mpi-openmp-offload, MN5-ACC, job 49051561:
4 ranks with OMP_NUM_THREADS=20, one CPU thread used per rank)."""
import os
import re
import tempfile
import unittest

import hybridmetrics
from rawdata import count_never_created_host_threads


# timings.stats of the trace, shortened: per rank one working thread, empty
# threads (Not created, plus the flush of Extrae at the end) and the GPU row.
TIMINGS_STATS = (
    "\tRunning\tNot created\tSynchronization\tI/O\tMemory transfer\t\n"
    "THREAD 1.1.1\t2467265.18\t0.00\t635305.47\t2016.89\t1224910.03\t\n"
    "THREAD 1.1.2\t0.00\t4549628.09\t0.00\t0.24\t0.00\t\n"
    "THREAD 1.1.3\t0.00\t4549628.15\t0.00\t0.17\t0.00\t\n"
    "GPU-D1.S1\t629135.10\t2824884.54\t0.00\t175.41\t33745.07\t\n"
    "THREAD 1.2.1\t2257679.13\t210096.35\t636455.61\t3286.54\t1231933.50\t\n"
    "THREAD 1.2.2\t0.00\t4549628.10\t0.00\t0.22\t0.00\t\n"
    "GPU-D2.S1\t629000.00\t2824884.54\t0.00\t175.41\t33745.07\t\n"
    "\n"
    "Total\t0\t0\t0\t0\t0\t\n"
    "Average\t0\t0\t0\t0\t0\t\n"
)


class NeverCreatedHostThreadsTest(unittest.TestCase):
    def _write(self, text):
        handle = tempfile.NamedTemporaryFile(
            'w', suffix='.csv', delete=False)
        handle.write(text)
        handle.close()
        self.addCleanup(os.remove, handle.name)
        return handle.name

    def test_empty_threads_counted(self):
        # 1.1.2, 1.1.3 and 1.2.2; not the working threads (rank 2 starts
        # 0.2 s late: Not created for 5% of its time), nor the GPU rows.
        self.assertEqual(
            count_never_created_host_threads(self._write(TIMINGS_STATS)), 3)

    def test_without_pcf_labels(self):
        text = TIMINGS_STATS.replace('Not created', 'Unknown state 2')
        self.assertEqual(
            count_never_created_host_threads(self._write(text)), 3)

    def test_no_not_created_column(self):
        text = ("\tRunning\tI/O\t\n"
                "THREAD 1.1.1\t100.00\t1.00\t\n")
        self.assertEqual(
            count_never_created_host_threads(self._write(text)), 0)


class MpiGpuConfigurationLabelTest(unittest.TestCase):
    """84 rows (4 ranks x 20 threads + 4 GPU streams) with 76 empty threads:
    8 (4x1) [4D], not 84 (4x20) [4D]."""

    def _label(self, processes, host_threads, streams):
        trace = 't.prv'
        raw_data = {
            'count_devices': {trace: 4},
            'count_gpu_streams': {trace: streams},
            'gpu_streams_per_rank': {trace: 1},
            'count_host_threads': {trace: host_threads},
        }
        labels = hybridmetrics._build_hybrid_configuration_labels(
            [trace], {trace: processes}, {trace: 4}, {trace: 21},
            {trace: 'Detailed+MPI+CUDA'}, raw_data)
        return labels[0]

    def test_empty_threads(self):
        self.assertEqual(self._label(84, 4, 4), '8 (4x1) [4D]')

    def test_one_thread_per_rank(self):
        self.assertEqual(self._label(8, 4, 4), '8 (4x1) [4D]')


class FrequencyCfgRangeTest(unittest.TestCase):
    """The frequency histogram has a fixed range of 1..10001 cycles/us
    (up to 10 GHz). With a range computed from the data, one counter value
    of an empty thread (4.8e6 cycles/us) made bins 25,000 cycles/us wide and
    gave an Average frequency of 72.91 GHz. Values outside the range (no
    cycles, or impossible frequencies) are dropped by paramedir."""

    def test_fixed_range(self):
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            '..', 'cfgs', 'frequency_avg_value.cfg')
        with open(path) as handle:
            text = handle.read()

        def field(name):
            return re.search(r'^Analyzer2D\.{}: (.*)$'.format(name),
                             text, re.M).group(1).strip()

        self.assertEqual(field('ComputeYScale'), 'False')
        self.assertGreater(float(field('Minimum')), 0.0)
        self.assertLessEqual(float(field('Minimum')), 1.0)
        self.assertGreaterEqual(float(field('Maximum')), 10000.0)
        width = ((float(field('Maximum')) - float(field('Minimum')))
                 / int(field('NumColumns')))
        self.assertLessEqual(width, 10.0)


if __name__ == '__main__':
    unittest.main()
