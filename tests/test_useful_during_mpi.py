import os
import tempfile
import unittest

from hybridmetrics import hybrid_work_factors
from rawdata import (
    aggregate_gpu_metrics_from_stream_stats,
    parse_first_thread_mpi_intervals,
    parse_timings_stats,
    useful_during_mpi_time,
)

# Paramedir timeline export: thread, start, duration, value.
# First thread of the process 1 in MPI from 100 to 200 and from 300 to 400. The
# second thread has an MPI event too, which the metrics ignore.
MPI_CALLS = """\
#paramedir timeline
1.1.1\t0\t100\t0
1.1.1\t100\t100\t3
1.1.1\t200\t100\t0
1.1.1\t300\t100\t10
1.1.2\t0\t50\t3
1.2.1\t0\t1000\t0
"""

CPU_ROW = """\
LEVEL THREAD SIZE 3
THREAD 1.1.1
THREAD 1.1.2
THREAD 1.2.1
"""

GPU_ROW = """\
LEVEL THREAD SIZE 3
THREAD 1.1.1
CUDA-D1.S1-node
CUDA-D1.S2-node
"""


def _write(folder, name, content):
    path = os.path.join(folder, name)

    with open(path, 'w') as f:
        f.write(content)

    return path


class UsefulDuringMpiTests(unittest.TestCase):

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.mpi = _write(self.folder.name, 'mpi.csv', MPI_CALLS)

    def test_only_the_calls_of_the_first_thread(self):
        intervals = parse_first_thread_mpi_intervals(self.mpi)

        self.assertEqual(sorted(intervals), [0])
        self.assertEqual([tuple(item) for item in intervals[0][1]],
                         [(100.0, 200.0), (300.0, 400.0)])

    def test_threads_during_the_calls_of_their_process(self):
        row = _write(self.folder.name, 'cpu.row', CPU_ROW)
        useful = _write(self.folder.name, 'useful.csv', (
            # Its own process: 50 and 100 during the MPI calls.
            "1.1.2\t150\t100\t1\n"
            "1.1.2\t250\t200\t1\n"
            # The first thread, and a zero value: not counted.
            "1.1.1\t100\t100\t1\n"
            "1.1.2\t500\t100\t0\n"
            # A process without MPI calls.
            "1.2.2\t100\t100\t1\n"
        ))

        self.assertEqual(useful_during_mpi_time(self.mpi, useful, row), 150.0)

    def test_no_overlap(self):
        row = _write(self.folder.name, 'cpu.row', CPU_ROW)
        useful = _write(self.folder.name, 'useful.csv', (
            "1.1.2\t0\t100\t1\n"
            "1.1.2\t200\t100\t1\n"
        ))

        self.assertEqual(useful_during_mpi_time(self.mpi, useful, row), 0.0)

    def test_streams_of_a_device_are_flattened(self):
        row = _write(self.folder.name, 'gpu.row', GPU_ROW)
        # Two streams overlap from 150 to 200: counted once.
        useful = _write(self.folder.name, 'useful.csv', (
            "1.1.1\t0\t50\t1\n"
            "1.1.2\t120\t80\t1\n"
            "1.1.3\t150\t100\t1\n"
        ))
        aggregate = aggregate_gpu_metrics_from_stream_stats(useful, None, row)

        self.assertEqual(
            useful_during_mpi_time(self.mpi, useful, row,
                                   per_device=aggregate['per_device']),
            80.0)


class HybridLevelsTests(unittest.TestCase):

    @staticmethod
    def _levels(useful_during_mpi, work_value='Non-Avail'):
        from interactiveplots import (
            HYBRID_INNER_WORK_ORDER,
            HYBRID_ORDER,
            HYBRID_OUTER_WORK_ORDER,
            _build_hybrid_levels_html,
            _build_hybrid_metric_info,
        )

        factors = {key: {'t': 50.0} for key in HYBRID_ORDER}
        factors['useful_during_mpi'] = {'t': useful_during_mpi}
        factors['omp_outside_mpi_eff'] = {'t': 43.01}
        for key in HYBRID_OUTER_WORK_ORDER + HYBRID_INNER_WORK_ORDER:
            factors.setdefault(key, {'t': work_value})

        return _build_hybrid_levels_html(
            _build_hybrid_metric_info('CUDA'),
            {key: factors for key in (HYBRID_ORDER
                                      + HYBRID_OUTER_WORK_ORDER
                                      + HYBRID_INNER_WORK_ORDER)},
            ['t'],
            ['4 [T1]'],
            '',
            'CUDA',
        )

    def test_outer_inner_and_other_tables(self):
        html = self._levels(114.27)

        self.assertIn('Outer level: MPI', html)
        self.assertIn('Inner level: CUDA', html)
        self.assertIn('Other: useful work during MPI', html)
        self.assertIn('114.27%', html)
        self.assertIn('43.01%', html)
        # Neither good nor bad, so no efficiency color.
        self.assertIn('background:#dbe4ee', html)

    def test_cpu_levels_use_the_distribution_of_useful_time(self):
        html = self._levels(100.0, work_value=88.0)

        self.assertIn('Outer level: between processes', html)
        self.assertIn('Inner level: inside the processes', html)
        self.assertIn('Process Load balance', html)
        self.assertIn('Thread Load balance', html)
        self.assertNotIn('Outer level: MPI', html)

    def test_other_is_omitted_without_values(self):
        html = self._levels('Non-Avail')

        self.assertIn('Inner level: CUDA', html)
        self.assertNotIn('Other: useful work during MPI', html)


class HybridWorkFactorsTests(unittest.TestCase):

    def test_timings_mean_useful_per_thread_of_each_process(self):
        with tempfile.TemporaryDirectory() as folder:
            path = _write(folder, 'timings.csv', (
                "\tRunning\n"
                "THREAD 1.1.1\t100\n"
                "THREAD 1.1.2\t20\n"
                "THREAD 1.2.1\t80\n"
                # Threads without useful time are not units of the model.
                "THREAD 1.2.2\t0\n"
                "Total\t200\n"
                "Average\t66.67\n"
                "Maximum\t100\n"
            ))
            result = parse_timings_stats(path, has_pcf=True)

        self.assertEqual(result['useful_process_mean_max'], 80.0)

    def test_product_is_hybrid_parallel_efficiency(self):
        useful_avg, useful_max, runtime = 60.0, 90.0, 100.0
        outside_max = 95.0
        factors = hybrid_work_factors(
            useful_avg, useful_max, 80.0,
            outside_max / runtime * 100.0,
            useful_max / outside_max * 100.0,
        )

        self.assertAlmostEqual(factors['process_load_balance'], 75.0)
        self.assertAlmostEqual(factors['thread_load_balance'], 80.0 / 90.0 * 100)
        self.assertAlmostEqual(
            factors['outer_parallel_eff'] * factors['inner_parallel_eff'] / 100.0,
            useful_avg / runtime * 100.0)
        self.assertAlmostEqual(
            factors['process_load_balance'] * factors['thread_load_balance'] / 100.0,
            useful_avg / useful_max * 100.0)

    def test_compensation_example_stays_bounded(self):
        # Process 1 is outside MPI for 100 and process 2 for 50, with the same
        # useful time: MPI LB is 75% and the ratio to Hybrid LB is 133%.
        factors = hybrid_work_factors(50.0, 50.0, 50.0, 100.0, 50.0)

        self.assertEqual(factors['process_load_balance'], 100.0)
        self.assertEqual(factors['thread_load_balance'], 100.0)
        self.assertEqual(factors['inner_parallel_eff'], 50.0)


if __name__ == '__main__':
    unittest.main()
