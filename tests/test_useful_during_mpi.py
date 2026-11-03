import os
import tempfile
import unittest

from hybridmetrics import hybrid_lb_split
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


class HybridTreeTests(unittest.TestCase):

    def test_new_metrics_are_children_of_existing_metrics(self):
        from interactiveplots import GLOBAL_TREE, HYBRID_TREE

        def children(tree, key):
            for node in tree:
                if node['metric'] == key:
                    return [child['metric'] for child in node['children']]
                found = children(node['children'], key)
                if found is not None:
                    return found
            return None

        self.assertEqual(children(GLOBAL_TREE, 'load_balance'),
                         ['lb_between_processes', 'lb_inside_processes'])
        self.assertEqual(children(HYBRID_TREE, 'hybrid_eff'),
                         ['mpi_parallel_eff', 'omp_parallel_eff'])
        self.assertIn('useful_during_mpi',
                      children(HYBRID_TREE, 'omp_parallel_eff'))

    def test_split_is_only_for_cpu_based_hybrid_executions(self):
        from hybridmetrics import get_application_factor_keys

        for mode, expected in (('Detailed+MPI+OpenMP', True),
                               ('Detailed+MPI+CUDA', False),
                               ('Detailed+MPI', False)):
            keys = get_application_factor_keys(['t'], {'t': mode})
            self.assertEqual('lb_between_processes' in keys, expected, mode)

    def test_useful_during_mpi_has_a_neutral_color(self):
        from interactiveplots import (
            NEUTRAL_VALUE_COLOR, _build_efficiency_table_html,
            _build_hybrid_metric_info)

        html = _build_efficiency_table_html(
            metric_keys=['useful_during_mpi'],
            metric_info=_build_hybrid_metric_info('CUDA'),
            metric_sources={'useful_during_mpi': {
                'useful_during_mpi': {'t': 114.27}}},
            trace_list=['t'],
            trace_labels=['4 [T1]'],
            section_id='test',
            tree=[],
            metric_knowledge={},
        )

        self.assertIn('background:' + NEUTRAL_VALUE_COLOR, html)


class HybridLbSplitTests(unittest.TestCase):

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

    def test_product_is_hybrid_load_balance(self):
        split = hybrid_lb_split(60.0, 90.0, 80.0)

        self.assertAlmostEqual(split['lb_between_processes'], 75.0)
        self.assertAlmostEqual(split['lb_inside_processes'], 80.0 / 90.0 * 100)
        self.assertAlmostEqual(
            split['lb_between_processes'] * split['lb_inside_processes'] / 100.0,
            60.0 / 90.0 * 100.0)

    def test_equal_useful_time_is_balanced(self):
        # Process 1 is outside MPI for 100 and process 2 for 50, with the same
        # useful time: MPI LB is 75% and the ratio to Hybrid LB is 133%.
        split = hybrid_lb_split(50.0, 50.0, 50.0)

        self.assertEqual(split['lb_between_processes'], 100.0)
        self.assertEqual(split['lb_inside_processes'], 100.0)


if __name__ == '__main__':
    unittest.main()
