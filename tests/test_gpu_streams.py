import os
import tempfile
import unittest

from rawdata import count_gpu_streams_by_mpi_rank
from tracemetadata import (
    get_device_stream_id_mapping,
    is_gpu_stream_label,
)


# MPI+CUDA trace with legacy CUDA labels:
# 4 MPI ranks, one stream per rank, one device per rank.
LEGACY_CUDA_ROW = """\
LEVEL CPU SIZE 8
1.as06r4b08
2.as06r4b08
3.as06r4b08
4.as06r4b08
5.as06r4b08
6.as06r4b08
7.as06r4b08
8.as06r4b08

LEVEL NODE SIZE 1
as06r4b08

LEVEL THREAD SIZE 8
THREAD 1.1.1
CUDA-D1.S1-as06r4b08
THREAD 1.2.1
CUDA-D2.S1-as06r4b08
THREAD 1.3.1
CUDA-D3.S1-as06r4b08
THREAD 1.4.1
CUDA-D4.S1-as06r4b08
"""

# MPI+GPU trace with generic Extrae GPU labels:
# 2 MPI ranks, two streams per rank.
GENERIC_GPU_ROW = """\
LEVEL CPU SIZE 6
1.node1
2.node1
3.node1
4.node1
5.node1
6.node1

LEVEL NODE SIZE 1
node1

LEVEL THREAD SIZE 6
THREAD 1.1.1
GPU-D1.S1
GPU-D1.S2
THREAD 1.2.1
GPU-D2.S1
GPU-D2.S2
"""

# MPI+GPU trace with UUID-based labels:
# 2 MPI ranks, non-uniform number of streams per rank.
UUID_GPU_ROW = """\
LEVEL CPU SIZE 5
1.node1
2.node1
3.node1
4.node1
5.node1

LEVEL NODE SIZE 1
node1

LEVEL THREAD SIZE 5
THREAD 1.1.1
GPU_a2f80454.1
GPU_a2f80454.2
THREAD 1.2.1
GPU_b3e91565.1
"""


class GpuStreamCountTests(unittest.TestCase):

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self._tmpdir.cleanup()

    def _write_row(self, content):
        """Write a .row file and return the matching .prv path."""
        base = os.path.join(self._tmpdir.name, "trace")

        with open(base + ".row", "w") as f:
            f.write(content)

        return base + ".prv"

    def _assert_consistent(self, prv_file):
        """Devices and streams must be counted from the same labels."""
        devices = get_device_stream_id_mapping(prv_file)
        streams = count_gpu_streams_by_mpi_rank(prv_file[:-4] + ".row")

        streams_from_devices = sum(
            count for count, _ids in devices.values()
        )

        self.assertEqual(
            streams["total_streams"],
            streams_from_devices,
        )

        return devices, streams

    def test_legacy_cuda_labels(self):
        prv_file = self._write_row(LEGACY_CUDA_ROW)

        devices, streams = self._assert_consistent(prv_file)

        self.assertEqual(len(devices), 4)
        self.assertEqual(streams["total_streams"], 4)
        self.assertEqual(streams["streams_per_rank"], 1)
        self.assertEqual(
            streams["streams_by_rank"],
            {0: 1, 1: 1, 2: 1, 3: 1},
        )

    def test_generic_gpu_labels(self):
        prv_file = self._write_row(GENERIC_GPU_ROW)

        devices, streams = self._assert_consistent(prv_file)

        self.assertEqual(len(devices), 2)
        self.assertEqual(streams["total_streams"], 4)
        self.assertEqual(streams["streams_per_rank"], 2)

    def test_uuid_gpu_labels_non_uniform(self):
        prv_file = self._write_row(UUID_GPU_ROW)

        devices, streams = self._assert_consistent(prv_file)

        self.assertEqual(len(devices), 2)
        self.assertEqual(streams["total_streams"], 3)
        self.assertEqual(streams["streams_per_rank"], -1)

    def test_is_gpu_stream_label(self):
        for label in (
            "CUDA-D1.S1-as06r4b08",
            "GPU-D1.S2",
            "GPU_a2f80454.1",
        ):
            self.assertTrue(is_gpu_stream_label(label), label)

        for label in (
            "THREAD 1.1.1",
            "",
        ):
            self.assertFalse(is_gpu_stream_label(label), label)


if __name__ == "__main__":
    unittest.main()
