import os
import re
import unittest


CFG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "cfgs")


def _analyzer_range(cfg_name):
    with open(os.path.join(CFG_DIR, cfg_name)) as f:
        text = f.read()

    def field(name):
        match = re.search(r"^Analyzer2D\.{}: (.*)$".format(name), text, re.M)
        return match.group(1).strip()

    return {
        "compute_y_scale": field("ComputeYScale"),
        "minimum": float(field("Minimum")),
        "maximum": float(field("Maximum")),
        "columns": int(field("NumColumns")),
    }


class CfgAnalyzerRangeTests(unittest.TestCase):
    """paramedir uses the saved analyzer range when ComputeYScale is False
    and silently drops the values outside it. These analyzers must cover
    every positive value with a single column (the parsers read one
    column), excluding only 0."""

    CFGS = (
        # cfg, minimum allowed (> 0, and small enough for every value)
        ("mpi-time.cfg", 1.0),                 # MPI call identifiers >= 1
        ("useful_outside_omp.cfg", 1e-3),      # burst durations (us)
        ("hist-read-bytes.cfg", 1e-3),         # bytes per call
        ("hist-write-bytes.cfg", 1e-3),
    )

    def test_single_column_covers_all_positive_values(self):
        for cfg_name, max_minimum in self.CFGS:
            with self.subTest(cfg=cfg_name):
                rng = _analyzer_range(cfg_name)
                self.assertEqual(rng["compute_y_scale"], "False")
                self.assertEqual(rng["columns"], 1)
                self.assertGreater(rng["minimum"], 0.0)
                self.assertLessEqual(rng["minimum"], max_minimum)
                self.assertGreaterEqual(rng["maximum"], 1e18)


if __name__ == "__main__":
    unittest.main()
