import os
import tempfile
import unittest

from rawdata import (
    parse_average_frequency_histogram,
    parse_host_total_as_int,
    parse_positive_value_sum,
    parse_positive_value_sum_and_mask,
)


# Useful cycles of an Extrae CUDA trace: the GPU stream rows carry the
# counter values that Extrae writes when it closes them, multiplied by every
# kernel of the stream (CloverLeaf, Extrae 5.1.3).
CYCLES_STATS = (
    "\t[0.00..1,000,000,000,000,000,000.00]\t\n"
    "THREAD 1.1.1\t100.00\t\n"
    "GPU-D1.S1\t85924309304774.00\t\n"
    "THREAD 1.2.1\t300.00\t\n"
    "GPU-D2.S1\t0.00\t\n"
    "\n"
    "Num. Cells\t4.00\t\n"
    "Total\t85924309305174.00\t\n"
    "Average\t21481077326293.50\t\n"
)

# Same rows without host labels (custom row labels).
CUSTOM_LABEL_STATS = (
    "\t[0.00..1,000.00]\t\n"
    "rank0\t100.00\t\n"
    "rank1\t300.00\t\n"
    "\n"
    "Total\t400.00\t\n"
)

# Time (us) of each thread in each frequency bin (cycles/us).
FREQUENCY_STATS = (
    "\t[1,000.00..2,000.00)\t[2,000.00..3,000.00)\t[3,000.00..4,000.00)\t\n"
    "THREAD 1.1.1\t10.00\t30.00\t0.00\t\n"
    "GPU-D1.S1\t0.00\t0.00\t1000.00\t\n"
    "THREAD 1.2.1\t0.00\t10.00\t0.00\t\n"
    "\n"
    "Num. Cells\t3.00\t2.00\t1.00\t\n"
    "Total\t10.00\t40.00\t1000.00\t\n"
)


class HostCountersTests(unittest.TestCase):

    def _write(self, content):
        handle, path = tempfile.mkstemp(suffix='.stats.csv')
        with os.fdopen(handle, 'w') as f:
            f.write(content)
        self.addCleanup(os.remove, path)
        return path

    def test_sum_counts_host_rows_only(self):
        path = self._write(CYCLES_STATS)

        self.assertEqual(parse_positive_value_sum(path), 400.0)

    def test_mask_keeps_one_entry_per_row(self):
        total, count, mask = parse_positive_value_sum_and_mask(
            self._write(CYCLES_STATS))

        self.assertEqual(total, 400.0)
        self.assertEqual(count, 2)
        # The GPU rows are not processes with instructions.
        self.assertEqual(mask, [1, 0, 1, 0])

    def test_no_host_counters(self):
        path = self._write(
            "\t[0..1]\t\nTHREAD 1.1.1\t0.00\t\nGPU-D1.S1\t5.00\t\n")

        self.assertIsNone(parse_positive_value_sum(path))
        self.assertEqual(parse_positive_value_sum_and_mask(path),
                         (None, 0, []))

    def test_total_of_host_rows(self):
        self.assertEqual(parse_host_total_as_int(self._write(CYCLES_STATS)),
                         400)

    def test_custom_labels_keep_all_rows(self):
        path = self._write(CUSTOM_LABEL_STATS)

        self.assertEqual(parse_positive_value_sum(path), 400.0)
        self.assertEqual(parse_host_total_as_int(path), 400)

    def test_average_frequency_of_host_rows(self):
        frequency = parse_average_frequency_histogram(
            self._write(FREQUENCY_STATS))

        # 10 us at 1500 and 40 us at 2500 cycles/us; the 1000 us of the GPU
        # row at 3500 cycles/us are not counted.
        self.assertAlmostEqual(frequency, (10 * 1500 + 40 * 2500) / 50.0)


if __name__ == '__main__':
    unittest.main()
