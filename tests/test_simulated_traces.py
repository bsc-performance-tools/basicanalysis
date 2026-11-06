"""Dimemas simulated traces given as input (simulatedtraces)."""

import os
import tempfile
import unittest

from simulatedtraces import (NOT_AVAILABLE, clear_simulated_metrics,
                             find_inconsistent_simulations,
                             find_overwritten_inputs, header_end_time_us,
                             is_simulated_trace, simulated_trace_note_html,
                             simulated_trace_warnings)


DIMEMAS_ROW = "LEVEL SYSTEM SIZE 1\nunnamed_1 ()\n\nLEVEL NODE SIZE 2\n"
EXTRAE_ROW = "LEVEL CPU SIZE 4\n01.s09r1b63\n02.s09r1b63\n"
NSYS2PRV_ROW = "LEVEL NODE SIZE 1\nnode1\n"


class DetectionTests(unittest.TestCase):

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.dir = self._tmpdir.name

    def tearDown(self):
        self._tmpdir.cleanup()

    def _trace(self, name, row=None):
        path = os.path.join(self.dir, name)
        with open(path, "w") as f:
            f.write("#Paraver (10/04/26 at 17:34):100_ns:1(1):1:1(1:1),1\n")
        if row is not None:
            base = path[:-7] if name.endswith(".prv.gz") else path[:-4]
            with open(base + ".row", "w") as f:
                f.write(row)
        return path

    def test_renamed_dimemas_trace_is_detected_by_its_row(self):
        self.assertTrue(is_simulated_trace(self._trace("fastcpu.prv", DIMEMAS_ROW)))

    def test_extrae_and_nsys2prv_traces_are_not_simulated(self):
        self.assertFalse(is_simulated_trace(self._trace("app.prv", EXTRAE_ROW)))
        self.assertFalse(is_simulated_trace(self._trace("nsys.prv", NSYS2PRV_ROW)))

    def test_the_row_wins_over_the_name(self):
        self.assertFalse(is_simulated_trace(self._trace("app.sim.prv", EXTRAE_ROW)))

    def test_without_row_the_name_decides(self):
        self.assertTrue(is_simulated_trace(self._trace("x_8P.sim.prv")))
        self.assertTrue(is_simulated_trace(self._trace("x_8P.sim.prv.gz")))
        self.assertFalse(is_simulated_trace(self._trace("x.prv")))


class OverwriteTests(unittest.TestCase):

    def test_ideal_simulation_would_overwrite_a_simulated_input(self):
        traces = ["run/x.prv", "run/x_24P.sim.prv"]
        processes = {"run/x.prv": 24, "run/x_24P.sim.prv": 24}
        clashes = find_overwritten_inputs(traces, processes, {"run/x_24P.sim.prv"})
        self.assertEqual(clashes, [("run/x_24P.sim.prv", "run/x.prv")])

    def test_other_names_or_folders_do_not_clash(self):
        traces = ["run/x.prv", "other/x_24P.sim.prv", "run/x_8P.sim.prv"]
        processes = dict.fromkeys(traces, 24)
        simulated = {"other/x_24P.sim.prv", "run/x_8P.sim.prv"}
        self.assertEqual(find_overwritten_inputs(traces, processes, simulated), [])


def _factors(keys, traces, value=90.0):
    return {key: {trace: value for trace in traces} for key in keys}


class ClearMetricsTests(unittest.TestCase):

    def test_pure_mpi_simulation_keeps_all_but_the_ideal_metrics(self):
        traces = ["real.prv", "sim.prv"]
        result = {
            "mod_factors": _factors(
                ["parallel_eff", "load_balance", "comm_eff", "serial_eff",
                 "transfer_eff", "comp_scale", "ipc_scale"], traces),
            "other_metrics": _factors(["elapsed_time", "ipc"], traces),
        }
        clear_simulated_metrics(result, traces, dict.fromkeys(traces, "Detailed+MPI"),
                                {"sim.prv"})
        mod = result["mod_factors"]
        self.assertEqual(mod["serial_eff"]["sim.prv"], NOT_AVAILABLE)
        self.assertEqual(mod["transfer_eff"]["sim.prv"], NOT_AVAILABLE)
        for key in ("parallel_eff", "load_balance", "comm_eff", "comp_scale", "ipc_scale"):
            self.assertEqual(mod[key]["sim.prv"], 90.0)
        self.assertEqual(mod["serial_eff"]["real.prv"], 90.0)
        self.assertEqual(result["other_metrics"]["ipc"]["sim.prv"], 90.0)

    def test_hybrid_simulation_keeps_only_the_mpi_level(self):
        traces = ["sim.prv"]
        result = {
            "mod_factors": _factors(["global_eff", "parallel_eff", "comp_scale"], traces),
            "hybrid_factors": _factors(
                ["hybrid_eff", "mpi_parallel_eff", "mpi_load_balance", "mpi_comm_eff",
                 "serial_eff", "transfer_eff", "omp_parallel_eff",
                 "omp_load_balance"], traces),
            "host_factors": _factors(
                ["host_parallel_eff", "mpi_parallel_eff", "dev_offload_eff"], traces),
            "device_factors": _factors(["dev_comp_scale"], traces),
            "other_metrics": _factors(["elapsed_time", "ipc", "freq"], traces),
            "scaling_info": None,
        }
        clear_simulated_metrics(result, traces, {"sim.prv": "Detailed+MPI+OpenMP"},
                                {"sim.prv"})
        hybrid = result["hybrid_factors"]
        for key in ("mpi_parallel_eff", "mpi_load_balance", "mpi_comm_eff"):
            self.assertEqual(hybrid[key]["sim.prv"], 90.0)
        for key in ("hybrid_eff", "serial_eff", "transfer_eff", "omp_parallel_eff",
                    "omp_load_balance"):
            self.assertEqual(hybrid[key]["sim.prv"], NOT_AVAILABLE)
        for key in ("global_eff", "parallel_eff", "comp_scale"):
            self.assertEqual(result["mod_factors"][key]["sim.prv"], NOT_AVAILABLE)
        self.assertEqual(result["host_factors"]["mpi_parallel_eff"]["sim.prv"], 90.0)
        self.assertEqual(result["host_factors"]["dev_offload_eff"]["sim.prv"], NOT_AVAILABLE)
        self.assertEqual(result["device_factors"]["dev_comp_scale"]["sim.prv"], NOT_AVAILABLE)
        # Elapsed time and the counters stay, with the warning.
        self.assertEqual(result["other_metrics"]["ipc"]["sim.prv"], 90.0)


class InconsistentSimulationTests(unittest.TestCase):

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.dir = self._tmpdir.name

    def tearDown(self):
        self._tmpdir.cleanup()

    def _trace(self, name, header):
        path = os.path.join(self.dir, name)
        with open(path, "w") as f:
            f.write(header + "\n")
        return path

    def test_header_end_time_units(self):
        ns = self._trace("ns.prv", "#Paraver (28/07/25 at 15:38):31079205_ns:1(1):1:1(1:1),1")
        us = self._trace("us.prv", "#Paraver (10/05/22 at 04:07):2308018:1(1):1:1(1:1),1")
        self.assertAlmostEqual(header_end_time_us(ns), 31079.205)
        self.assertAlmostEqual(header_end_time_us(us), 2308018.0)

    def test_runtime_after_the_header_end_is_inconsistent(self):
        good = self._trace("good.prv", "#Paraver (x):6274099633_ns:1(1):1:1(1:1),1")
        bad = self._trace("bad.prv", "#Paraver (x):31079205_ns:1(1):1:1(1:1),1")
        raw_data = {"runtime": {good: 6274099.6, bad: 10000000.0, "real.prv": 99.0}}
        found = find_inconsistent_simulations([good, bad, "real.prv"], {good, bad}, raw_data)
        self.assertEqual(list(found), [bad])

    def test_no_metric_is_kept_for_an_inconsistent_trace(self):
        traces = ["sim.prv"]
        result = {
            "hybrid_factors": _factors(["mpi_parallel_eff", "omp_parallel_eff"], traces),
            "other_metrics": _factors(["elapsed_time", "ipc"], traces),
        }
        clear_simulated_metrics(result, traces, {"sim.prv": "Detailed+MPI+CUDA"},
                                {"sim.prv"}, {"sim.prv"})
        for group in result.values():
            for values in group.values():
                self.assertEqual(values["sim.prv"], NOT_AVAILABLE)

    def test_numeric_other_metrics_become_nan(self):
        result = {"other_metrics": _factors(["flushing", "io_posix", "io_eff"], ["sim.prv"])}
        clear_simulated_metrics(result, ["sim.prv"], {"sim.prv": "Detailed+MPI"},
                                {"sim.prv"}, {"sim.prv"})
        other = result["other_metrics"]
        self.assertNotEqual(other["flushing"]["sim.prv"], other["flushing"]["sim.prv"])
        self.assertNotEqual(other["io_posix"]["sim.prv"], other["io_posix"]["sim.prv"])
        self.assertEqual(other["io_eff"]["sim.prv"], NOT_AVAILABLE)

    def test_structured_io_data_is_kept(self):
        sizes = {"read": {"posix": [1, 2]}}
        result = {"other_metrics": {"io_request_sizes": {"sim.prv": sizes}}}
        clear_simulated_metrics(result, ["sim.prv"], {"sim.prv": "Detailed+MPI"},
                                {"sim.prv"}, {"sim.prv"})
        self.assertIs(result["other_metrics"]["io_request_sizes"]["sim.prv"], sizes)


class WarningTests(unittest.TestCase):

    def test_no_warning_without_simulated_traces(self):
        self.assertEqual(simulated_trace_warnings(["a.prv"], {"a.prv": "Detailed+MPI"}, set()), [])
        self.assertEqual(simulated_trace_note_html([{"name": "a.prv", "simulated": False}]), "")

    def test_warning_explains_what_dimemas_simulates(self):
        modes = {"a.prv": "Detailed+MPI", "b.prv": "Detailed+MPI+CUDA"}
        text = "\n".join(simulated_trace_warnings(["a.prv", "b.prv"], modes,
                                                  {"a.prv", "b.prv"}))
        self.assertIn("Serialization and Transfer", text)
        self.assertIn("CPU ratio 1", text)
        self.assertIn("b.prv (Detailed+MPI+CUDA)", text)
        self.assertIn("only cover the main", text)
        self.assertNotIn("a.prv (Detailed+MPI)", text)

    def test_report_note_escapes_names(self):
        note = simulated_trace_note_html(
            [{"name": "<x>.prv", "simulated": True, "mode": "Detailed+MPI+OpenMP"}])
        self.assertIn("&lt;x&gt;.prv", note)
        self.assertIn("MPI level only", note)


if __name__ == "__main__":
    unittest.main()
