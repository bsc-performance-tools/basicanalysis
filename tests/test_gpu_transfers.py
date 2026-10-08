import os
import tempfile
import unittest

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
# Useful (kernels): stream 1 from 0 to 100, stream 2 from 50 to 150.
USEFUL = """\
#paramedir timeline
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


class GpuTransferAggregationTests(unittest.TestCase):

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

    def test_host_transfer_intervals_are_not_reported(self):
        result = self._aggregate()
        self.assertEqual(result["unknown_memtransfer_threads"], [])
        self.assertEqual(result["unknown_useful_threads"], [])


if __name__ == "__main__":
    unittest.main()
