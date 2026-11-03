import os
import tempfile
import unittest

from hybridmetrics import mpi_gpu_useful_per_device
from rawdata import aggregate_gpu_metrics_from_stream_stats


# 1 MPI rank with 1 host thread and 2 streams of the same device.
ROW = """\
LEVEL CPU SIZE 3
1.node1
2.node1
3.node1

LEVEL NODE SIZE 1
node1

LEVEL THREAD SIZE 3
THREAD 1.1.1
CUDA-D1.S1-node1
CUDA-D1.S2-node1
"""

# Paramedir timeline export: thread, start, duration, value.
# Useful (Running state):
#  - stream 1 from 0 to 100, stream 2 from 50 to 150 (kernels);
#  - host thread from 0 to 500: host computation, ignored.
USEFUL = """\
#paramedir timeline
1.1.1\t0\t500\t1
1.1.2\t0\t100\t1
1.1.2\t100\t100\t0
1.1.3\t50\t100\t1
"""

# Memory transfer (state 17, value 1):
#  - stream 1 from 140 to 200: 140-150 overlaps the kernel on stream 2,
#    so only 150-200 (50 us) is a non-overlapped transfer;
#  - host thread from 300 to 400: host side of a synchronous copy, ignored.
MEMTRANSFER = """\
#paramedir timeline
1.1.1\t300\t100\t1
1.1.2\t140\t60\t1
1.1.2\t200\t100\t0
"""


class GpuDeviceAggregationTests(unittest.TestCase):

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self._tmpdir.cleanup()

    def _write(self, name, content):
        path = os.path.join(self._tmpdir.name, name)
        with open(path, "w") as f:
            f.write(content)
        return path

    def _aggregate(self):
        return aggregate_gpu_metrics_from_stream_stats(
            self._write("useful.csv", USEFUL),
            self._write("memtransfer.csv", MEMTRANSFER),
            self._write("trace.row", ROW),
        )

    def test_useful_is_union_of_streams(self):
        result = self._aggregate()
        self.assertAlmostEqual(result["useful_device_total"], 150.0)

    def test_only_non_overlapped_stream_transfers_count(self):
        result = self._aggregate()
        # useful 150 + non-overlapped transfer 50; host interval ignored.
        self.assertAlmostEqual(result["useful_memtransf_device_total"], 200.0)

    def test_host_intervals_are_not_reported(self):
        result = self._aggregate()
        self.assertEqual(result["unknown_memtransfer_threads"], [])
        self.assertEqual(result["unknown_useful_threads"], [])


class MpiGpuUsefulPerDeviceTests(unittest.TestCase):

    @staticmethod
    def _raw_data(**changes):
        # XSHELLS, 32 processes and 32 GPUs with several streams each.
        values = {
            'useful_host': 25432.40,
            'useful_host_max': 895.03,
            'useful_device': 1053165.80,
            'useful_device_max': 33117.99,
            'count_host_threads': 32,
            'count_devices': 32,
        }
        values.update(changes)
        return {key: {'t': value} for key, value in values.items()}

    def test_units_are_host_threads_and_physical_devices(self):
        useful_avg, useful_max = mpi_gpu_useful_per_device(
            self._raw_data(), 't')
        runtime = 51477.827

        self.assertAlmostEqual(useful_avg, 1078598.20 / 64)
        self.assertEqual(useful_max, 33117.99)
        load_balance = useful_avg / useful_max
        comm_eff = useful_max / runtime
        self.assertAlmostEqual(load_balance * 100.0, 50.89, places=2)
        self.assertAlmostEqual(comm_eff * 100.0, 64.33, places=2)
        # The product is the Hybrid Parallel Efficiency of H + D units.
        self.assertAlmostEqual(load_balance * comm_eff,
                               1078598.20 / (64 * runtime))

    def test_maximum_can_be_on_the_host(self):
        _, useful_max = mpi_gpu_useful_per_device(
            self._raw_data(useful_host_max=40000.0), 't')

        self.assertEqual(useful_max, 40000.0)

    def test_not_available(self):
        for changes in ({'useful_host': 'Non-Avail'},
                        {'useful_device_max': 'Non-Avail'},
                        {'count_devices': 0},
                        {'useful_host_max': 0.0, 'useful_device_max': 0.0}):
            self.assertIsNone(
                mpi_gpu_useful_per_device(self._raw_data(**changes), 't'))

        self.assertIsNone(mpi_gpu_useful_per_device({}, 't'))



if __name__ == "__main__":
    unittest.main()
