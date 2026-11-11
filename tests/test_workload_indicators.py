import unittest
from types import SimpleNamespace

import interactiveplots as ip
from scaling import build_workload_map, get_scaling_info


def _args(scaling="auto", workload=None, host_workload=None,
          device_workload=None):
    return SimpleNamespace(scaling=scaling, debug=False, workload=workload,
                           host_workload=host_workload,
                           device_workload=device_workload)


TRACES = ["b1.prv", "b4.prv", "b16.prv"]
RAW_DATA = {
    "useful_ins": {"b1.prv": 1000.0, "b4.prv": 3000.0, "b16.prv": 9000.0},
    "runtime": {"b1.prv": 100.0, "b4.prv": 150.0, "b16.prv": 300.0},
    "useful_avg": {"b1.prv": 90.0, "b4.prv": 140.0, "b16.prv": 290.0},
    "count_host_threads": {trace: 1 for trace in TRACES},
    "count_devices": {trace: 1 for trace in TRACES},
    "useful_host": {"b1.prv": 20.0, "b4.prv": 21.0, "b16.prv": 22.0},
    "useful_device": {"b1.prv": 60.0, "b4.prv": 110.0, "b16.prv": 260.0},
}


def _info(args, has_domains):
    build_workload_map(args, TRACES)
    return get_scaling_info(RAW_DATA, TRACES, {t: 1 for t in TRACES}, args,
                            has_domains=has_domains)


class WorkloadMarkTests(unittest.TestCase):

    def test_no_workload_no_marks(self):
        self.assertEqual(ip._workload_marks(_info(_args(), False), TRACES), {})

    def test_application_workload(self):
        marks = ip._workload_marks(_info(_args(workload="1,4,16"), False), TRACES)
        self.assertEqual(
            set(marks),
            {"comp_scale", "global_eff", "inst_scale", "speedup", "efficiency"})
        self.assertIn("--workload (ratios 1, 4, 16)", marks["comp_scale"])

    def test_device_workload_marks_only_device_and_application(self):
        marks = ip._workload_marks(
            _info(_args(device_workload="1,256,1024"), True), TRACES)
        for key in ("dev_comp_scale", "dev_global_eff", "comp_scale",
                    "global_eff", "speedup", "efficiency"):
            self.assertIn(key, marks)
        for key in ("host_comp_scale", "host_global_eff", "inst_scale"):
            self.assertNotIn(key, marks)
        self.assertIn("Device workload, --device-workload (ratios 1, 256, 1024)",
                      marks["dev_comp_scale"])
        self.assertNotIn("Host", marks["comp_scale"])

    def test_mark_html(self):
        ip._SCALING_CONTEXT["workload"] = {"comp_scale": "Computed with <x>."}
        try:
            mark = ip._workload_mark_html("comp_scale")
            self.assertIn("workload-mark", mark)
            self.assertIn("Computed with &lt;x&gt;.", mark)
            self.assertEqual(ip._workload_mark_html("ipc_scale"), "")
        finally:
            ip._SCALING_CONTEXT["workload"] = {}


class ScalingLevelsTests(unittest.TestCase):

    def _html(self, info):
        ip._SCALING_CONTEXT["raw_data"] = RAW_DATA
        try:
            return ip._build_scaling_model_html(info)
        finally:
            ip._SCALING_CONTEXT.pop("raw_data", None)

    def test_device_workload_names_the_source_of_each_level(self):
        text = self._html(_info(_args(device_workload="1,256,1024"), True))
        self.assertIn("Given with --device-workload", text)
        self.assertIn("Detected from the Host measurements", text)
        self.assertIn("1 · 256 · 1024", text)
        self.assertIn("marks the metrics computed with a user-defined workload",
                      text)
        self.assertNotIn("Not used (workload given)", text)

    def test_assumed_host_workload(self):
        text = self._html(_info(_args(workload="1,4,16"), True))
        self.assertIn("Assumed from --workload (no Host workload given)", text)

    def test_forced_scaling(self):
        text = self._html(_info(_args(scaling="strong",
                                      device_workload="1,256,1024"), True))
        self.assertIn("Forced with --scaling", text)
        self.assertIn("Strong scaling (ratio 1)", text)

    def test_without_workload_or_domains_keeps_the_summary(self):
        text = self._html(_info(_args(), False))
        self.assertIn("Detected scaling", text)
        self.assertNotIn("scaling-levels", text)


if __name__ == "__main__":
    unittest.main()
