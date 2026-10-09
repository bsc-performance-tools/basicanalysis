import os
import tempfile
import unittest

from nsys2prvmetrics import (
    aggregate_nsys2prv_device_metrics,
    classify_nsys2prv_threads,
    parse_nsys2prv_timeline,
)
from tracemetadata import (
    count_nsys2prv_metrics_threads,
    is_host_gpu_mode,
    is_nsys2prv_mode,
    is_nsys2prv_pcf,
    parse_trace_header,
)


# nsys2prv header: 0 nodes, no CPU list, ':' before the task list.
# Task 1: 1 thread (idle process); task 2: host thread, 4 streams and the
# GPU metrics thread.
NSYS2PRV_HEADER = "#Paraver (11/08/2026 at 23:07):53664645850_ns:0:1:2:(1:1,6:1)\n"

NSYS2PRV_ROW = """\
LEVEL NODE SIZE 1
node1

LEVEL TASK SIZE 2
TASK 1.1
TASK 1.2

LEVEL THREAD SIZE 7
THREAD 1.1.1
THREAD 1.2.1
CUDA-D0.S7
CUDA-D0.S13
CUDA-D0.S21
CUDA-D0.S25
Metrics GPU0
"""

NSYS2PRV_PCF = """\
DEFAULT_OPTIONS

EVENT_TYPE
0   63000001 CUDA memcpy kernel
VALUES
0   End
3   CUDA memcpy Device-to-Device
6   CUDA memset

EVENT_TYPE
0   63000007 NCCL kernel
"""

EXTRAE_PCF = """\
DEFAULT_OPTIONS

STATES
0    Idle
1    Running
17   Memory transfer

EVENT_TYPE
0   63000001 CUDA memory transfer
"""


class TraceHeaderTests(unittest.TestCase):

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self._tmpdir.cleanup()

    def _write(self, name, content):
        path = os.path.join(self._tmpdir.name, name)
        with open(path, "w") as f:
            f.write(content)
        return path

    def test_extrae_header(self):
        prv = self._write(
            "extrae.prv",
            "#Paraver (16/05/2025 at 19:33):674177237_ns:2(4,4):1:"
            "4(2:1,2:1,1:2,1:2),5\n",
        )
        header = parse_trace_header(prv)
        self.assertEqual(header["nodes"], 2)
        self.assertEqual(header["cpus_per_node"], [4, 4])
        self.assertEqual(header["tasks"], 4)
        self.assertEqual(header["threads_per_task"], [2, 2, 1, 1])
        self.assertEqual(header["node_per_task"], [1, 1, 2, 2])

    def test_dimemas_header_with_trailing_comma(self):
        prv = self._write(
            "sim.prv",
            "#Paraver (10/05/22 at 04:07):2308018051_ns:2(1,1,):1:"
            "2(1:1,1:2),3\n",
        )
        header = parse_trace_header(prv)
        self.assertEqual(header["cpus_per_node"], [1, 1])
        self.assertEqual(header["tasks"], 2)

    def test_nsys2prv_header(self):
        prv = self._write("nsys.prv", NSYS2PRV_HEADER)
        header = parse_trace_header(prv)
        self.assertEqual(header["nodes"], 0)
        self.assertEqual(header["cpus_per_node"], [])
        self.assertEqual(header["tasks"], 2)
        self.assertEqual(header["threads_per_task"], [1, 6])
        self.assertEqual(header["node_per_task"], [1, 1])


class Nsys2prvDetectionTests(unittest.TestCase):

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self._tmpdir.cleanup()

    def _write(self, name, content):
        path = os.path.join(self._tmpdir.name, name)
        with open(path, "w") as f:
            f.write(content)
        return path

    def test_nsys2prv_pcf_is_detected(self):
        self.assertTrue(is_nsys2prv_pcf(self._write("n.pcf", NSYS2PRV_PCF)))

    def test_extrae_pcf_is_not_detected(self):
        self.assertFalse(is_nsys2prv_pcf(self._write("e.pcf", EXTRAE_PCF)))

    def test_pcf_without_states_or_nsys2prv_labels_is_not_detected(self):
        # e.g. some Dimemas-simulated traces have no STATES section.
        pcf = "DEFAULT_OPTIONS\n\nEVENT_TYPE\n0   50000001 MPI Point-to-point\n"
        self.assertFalse(is_nsys2prv_pcf(self._write("s.pcf", pcf)))

    def test_nsys2prv_mode_uses_the_host_gpu_model(self):
        self.assertTrue(is_nsys2prv_mode("nsys2prv+CUDA"))
        self.assertTrue(is_host_gpu_mode("nsys2prv+CUDA"))
        self.assertFalse(is_nsys2prv_mode("Detailed+CUDA"))

    def test_metrics_threads_are_counted(self):
        prv = self._write("t.prv", NSYS2PRV_HEADER)
        self._write("t.row", NSYS2PRV_ROW)
        self.assertEqual(count_nsys2prv_metrics_threads(prv), 1)


class Nsys2prvThreadsTests(unittest.TestCase):

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.prv = os.path.join(self._tmpdir.name, "t.prv")
        self.row = os.path.join(self._tmpdir.name, "t.row")
        with open(self.prv, "w") as f:
            f.write(NSYS2PRV_HEADER)
        with open(self.row, "w") as f:
            f.write(NSYS2PRV_ROW)

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_classification(self):
        threads = classify_nsys2prv_threads(self.prv, self.row)

        self.assertEqual(threads["host"], ["THREAD 1.1.1", "THREAD 1.2.1"])
        self.assertEqual(threads["metrics"], ["THREAD 1.2.6"])
        self.assertEqual(
            threads["streams"],
            {
                "THREAD 1.2.2": "node1:D0",
                "THREAD 1.2.3": "node1:D0",
                "THREAD 1.2.4": "node1:D0",
                "THREAD 1.2.5": "node1:D0",
            },
        )
        self.assertEqual(threads["gpu_tasks"], {2})


class Nsys2prvAggregationTests(unittest.TestCase):

    STREAMS = {
        "THREAD 1.2.2": "node1:D0",
        "THREAD 1.2.3": "node1:D0",
        "THREAD 1.2.4": "node1:D1",
    }

    def test_device_metrics(self):
        kernels = [
            # Device D0: two streams overlapping, union 0-150.
            ("THREAD 1.2.2", 0.0, 100.0, 1.0),
            ("THREAD 1.2.3", 50.0, 150.0, 1.0),
            # Host thread: ignored.
            ("THREAD 1.2.1", 0.0, 500.0, 1.0),
            # Device D1.
            ("THREAD 1.2.4", 0.0, 40.0, 1.0),
        ]
        memcpy = [
            # D0: copy 140-200 overlaps the kernel until 150 -> 50 us.
            ("THREAD 1.2.2", 140.0, 200.0, 5.0),
            # D0: memset 300-310 -> memory operation, communication.
            ("THREAD 1.2.3", 300.0, 310.0, 6.0),
            # D1: Device-to-Host copy 100-120 -> 20 us.
            ("THREAD 1.2.4", 100.0, 120.0, 4.0),
        ]
        nccl = [
            # D1: NCCL kernel 200-230 -> communication, 30 us.
            ("THREAD 1.2.4", 200.0, 230.0, 1.0),
        ]

        result = aggregate_nsys2prv_device_metrics(
            kernels, memcpy, nccl, self.STREAMS)

        d0 = result["per_device"]["node1:D0"]
        d1 = result["per_device"]["node1:D1"]

        self.assertAlmostEqual(d0["useful_total"], 150.0)
        self.assertAlmostEqual(d0["memtransfer_only_total"], 60.0)
        self.assertAlmostEqual(d1["useful_total"], 40.0)
        self.assertAlmostEqual(d1["memtransfer_only_total"], 50.0)

        self.assertAlmostEqual(result["useful_device_total"], 190.0)
        self.assertAlmostEqual(result["useful_device_max"], 150.0)
        self.assertAlmostEqual(result["useful_memtransf_device_total"], 300.0)
        self.assertAlmostEqual(result["useful_memtransf_device_max"], 210.0)

    def test_timeline_in_nanoseconds(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "k.csv")
            with open(path, "w") as f:
                f.write("#paramedir:Nanoseconds\n")
                f.write("1.2.2\t0.00\t1000.00\t0.00\n")
                f.write("1.2.2\t1000.00\t1500.00\t1.00\n")

            rows = parse_nsys2prv_timeline(path)

        self.assertEqual(rows, [("THREAD 1.2.2", 1.0, 2.5, 1.0)])

    def test_missing_timeline(self):
        # paramedir writes no file when the events are not in the trace.
        self.assertEqual(parse_nsys2prv_timeline("/nonexistent.csv"), [])


if __name__ == "__main__":
    unittest.main()
