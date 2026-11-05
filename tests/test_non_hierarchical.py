import os
import tempfile
import unittest

from hybridmetrics import non_hierarchical_factors
from rawdata import non_hierarchical_outside_mpi

CPU_ROW = """\
LEVEL THREAD SIZE 4
THREAD 1.1.1
THREAD 1.1.2
THREAD 1.2.1
THREAD 1.2.2
"""


def _write(folder, name, content):
    path = os.path.join(folder, name)

    with open(path, 'w') as f:
        f.write(content)

    return path


def _timeline(rows, threads=()):
    """Paramedir timeline: thread, start, duration, value."""
    lines = ['#paramedir timeline']

    for thread, start, end in rows:
        lines.append('{}\t{}\t{}\t1'.format(thread, start, end - start))

    # Paramedir writes the threads without values too.
    for thread in threads:
        lines.append('{}\t0\t100\t0'.format(thread))

    return '\n'.join(lines) + '\n'


class NonHierarchicalOutsideMpiTests(unittest.TestCase):
    def _measure(self, mpi_rows, useful_rows, row=CPU_ROW, runtime=100.0,
                 per_device=None, threads=('1.1.1', '1.1.2', '1.2.1', '1.2.2')):
        with tempfile.TemporaryDirectory() as folder:
            return non_hierarchical_outside_mpi(
                _write(folder, 'mpi.csv', _timeline(mpi_rows, threads)),
                _write(folder, 'useful.csv', _timeline(useful_rows)),
                _write(folder, 'trace.row', row),
                runtime,
                per_device=per_device)

    def test_hierarchical_code_is_outside_mpi_of_the_first_thread(self):
        # O = 70, 50: the threads are idle during MPI.
        result = self._measure(
            [('1.1.1', 70, 100), ('1.2.1', 50, 100)],
            [('1.1.1', 0, 70), ('1.1.2', 0, 50),
             ('1.2.1', 0, 50), ('1.2.2', 0, 40)])

        self.assertAlmostEqual(result['avg'], 60.0)
        self.assertAlmostEqual(result['max'], 70.0)

    def test_useful_work_during_mpi_is_not_blamed_on_mpi(self):
        # Rank 1: O = 60, and the second thread works 20 during MPI, so
        # O' = 60 + 20 / 2 = 70.
        result = self._measure(
            [('1.1.1', 60, 100)],
            [('1.1.1', 0, 60), ('1.1.2', 60, 80),
             ('1.2.1', 0, 50), ('1.2.2', 0, 50)])

        self.assertAlmostEqual(result['max'], 100.0)   # rank 2 has no MPI
        self.assertAlmostEqual(result['avg'], (70.0 + 100.0) / 2)

    def test_mpi_called_from_any_thread(self):
        # Rank 1: t1 in MPI 40-60, t2 in MPI 50-80, so M = 40-80 and O = 60.
        # During M, t1 works 60-80 and t2 works 40-50: 30 / 2 = 15.
        result = self._measure(
            [('1.1.1', 40, 60), ('1.1.2', 50, 80)],
            [('1.1.1', 0, 40), ('1.1.1', 60, 100),
             ('1.1.2', 0, 50), ('1.1.2', 80, 100)])

        self.assertAlmostEqual(result['max'], 100.0)
        self.assertAlmostEqual(result['avg'], (75.0 + 100.0) / 2)

    def test_device_of_the_example_in_the_slides(self):
        # One rank, one Host thread and one device: O = 60, device works 20
        # during MPI, so O' = 60 + 20 / 2 = 70.
        row = "LEVEL THREAD SIZE 2\nTHREAD 1.1.1\nCUDA-D1.S1-node\n"
        per_device = {
            'node:1': {'useful_intervals_merged': [(20.0, 80.0)]}
        }

        with tempfile.TemporaryDirectory() as folder:
            row_path = _write(folder, 'trace.row', row)

            from rawdata import build_thread_to_device_map_from_row
            device_key = list(
                build_thread_to_device_map_from_row(row_path).values())[0]
            per_device = {device_key: per_device['node:1']}

            result = non_hierarchical_outside_mpi(
                _write(folder, 'mpi.csv', _timeline([('1.1.1', 60, 100)], ('1.1.1',))),
                _write(folder, 'useful.csv', _timeline(
                    [('1.1.1', 0, 20), ('1.1.2', 20, 80)])),
                row_path,
                100.0,
                per_device=per_device)

        self.assertAlmostEqual(result['avg'], 70.0)
        self.assertAlmostEqual(result['max'], 70.0)

    def test_unequal_threads_are_weighted_in_cpu_codes(self):
        row = ("LEVEL THREAD SIZE 3\nTHREAD 1.1.1\nTHREAD 1.1.2\n"
               "THREAD 1.2.1\n")
        result = self._measure(
            [('1.1.1', 70, 100), ('1.2.1', 40, 100)],
            [('1.1.1', 0, 70), ('1.1.2', 0, 50), ('1.2.1', 0, 40)],
            row=row, threads=('1.1.1', '1.1.2', '1.2.1'))

        self.assertAlmostEqual(result['avg'], (70.0 * 2 + 40.0) / 3)

    def test_row_file_of_another_execution_adds_no_process(self):
        row = CPU_ROW + "THREAD 1.3.1\nTHREAD 1.3.2\n"
        result = self._measure(
            [('1.1.1', 70, 100), ('1.2.1', 50, 100)],
            [('1.1.1', 0, 70), ('1.2.1', 0, 50)], row=row)

        self.assertAlmostEqual(result['avg'], 60.0)
        self.assertAlmostEqual(result['max'], 70.0)


class NonHierarchicalFactorsTests(unittest.TestCase):
    def test_the_model_still_multiplies(self):
        factors = non_hierarchical_factors(70.0, 70.0, 100.0, 40.0, 57.0, 70.2)

        self.assertAlmostEqual(factors['nh_mpi_parallel_eff'], 70.0)
        self.assertAlmostEqual(
            factors['nh_mpi_load_balance'] * factors['nh_mpi_comm_eff'] / 100.0,
            factors['nh_mpi_parallel_eff'])
        self.assertAlmostEqual(
            factors['nh_mpi_parallel_eff'] * factors['nh_omp_parallel_eff'] / 100.0,
            40.0)


if __name__ == '__main__':
    unittest.main()
