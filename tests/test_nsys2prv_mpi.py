import importlib.util
import os
import shutil
import tempfile
import unittest

import nsys2prvevents
import nsys2prvmetrics
import reportdata
from configuration import configuration_model_key
from tracemetadata import (
    NSYS2PRV_MPI_MODE,
    is_host_gpu_mode,
    is_mpi_cuda_mode,
    is_mpi_gpu_mode,
    is_mpi_hybrid_mode,
    is_nsys2prv_mode,
    mpi_second_runtime,
    pcf_has_mpi_events,
)


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PCF = """DEFAULT_OPTIONS

EVENT_TYPE
0   63000000 CUDA library call
VALUES
0   End
1   cudaLaunchKernel


EVENT_TYPE
0   63000006 CUDA kernel
VALUES
0   End
1   gemm_kernel
{mpi}
"""

MPI_PCF = """
EVENT_TYPE
0 50000001 MPI Point-to-point
0 50000002 MPI Collective Comm
0 50000003 MPI Other
VALUES
0 End
31 MPI_Init
32 MPI_Finalize
"""


class ModeTest(unittest.TestCase):

    def test_modes(self):
        self.assertTrue(is_nsys2prv_mode(NSYS2PRV_MPI_MODE))
        self.assertTrue(is_mpi_gpu_mode(NSYS2PRV_MPI_MODE))
        self.assertTrue(is_mpi_cuda_mode(NSYS2PRV_MPI_MODE))
        self.assertTrue(is_mpi_hybrid_mode(NSYS2PRV_MPI_MODE))
        self.assertFalse(is_host_gpu_mode(NSYS2PRV_MPI_MODE))
        # nsys2prv traces without MPI keep the model without MPI.
        self.assertTrue(is_host_gpu_mode('nsys2prv+CUDA'))
        self.assertFalse(is_mpi_gpu_mode('nsys2prv+CUDA'))
        self.assertFalse(is_mpi_hybrid_mode('nsys2prv+CUDA'))
        # Extrae modes unchanged.
        self.assertTrue(is_mpi_hybrid_mode('Detailed+MPI+OpenMP'))
        self.assertFalse(is_mpi_hybrid_mode('Detailed+MPI'))
        self.assertTrue(is_mpi_cuda_mode('Detailed+MPI+CUDA'))
        self.assertFalse(is_mpi_cuda_mode('Detailed+MPI+HIP'))

    def test_second_runtime(self):
        self.assertEqual(mpi_second_runtime('Detailed+MPI+OpenMP'), 'OpenMP')
        self.assertEqual(mpi_second_runtime(NSYS2PRV_MPI_MODE), 'CUDA')

    def test_configuration_label(self):
        self.assertEqual(configuration_model_key(NSYS2PRV_MPI_MODE), 'mpi_gpu')
        self.assertEqual(configuration_model_key('nsys2prv+CUDA'), 'nsys2prv')

    def test_pcf_mpi_events(self):
        with tempfile.TemporaryDirectory() as folder:
            with_mpi = os.path.join(folder, 'a.pcf')
            without = os.path.join(folder, 'b.pcf')
            with open(with_mpi, 'w') as pcf:
                pcf.write(PCF.format(mpi=MPI_PCF))
            with open(without, 'w') as pcf:
                pcf.write(PCF.format(mpi=''))
            self.assertTrue(pcf_has_mpi_events(with_mpi))
            self.assertFalse(pcf_has_mpi_events(without))


class MpiTimesTest(unittest.TestCase):

    def test_useful_host_counts_cuda_in_mpi_once(self):
        threads = {'host': ['THREAD 1.1.1', 'THREAD 1.2.1', 'THREAD 1.2.2']}
        runtime = 100.0
        outside = {'THREAD 1.1.1': 80.0,      # 20 in MPI
                   'THREAD 1.2.1': 100.0,     # helper thread, no MPI
                   'THREAD 1.2.2': 70.0}      # 30 in MPI
        cuda = {'THREAD 1.1.1': 10.0, 'THREAD 1.2.1': 15.0, 'THREAD 1.2.2': 5.0}
        cuda_in_mpi = {'THREAD 1.1.1': 4.0}
        mpi = nsys2prvmetrics.nsys2prv_mpi_times(
            threads, ['THREAD 1.1.1', 'THREAD 1.2.1'], runtime, outside,
            cuda, cuda_in_mpi)
        # 100 - (10 + 20 - 4)
        self.assertAlmostEqual(mpi['useful_host']['THREAD 1.1.1'], 74.0)
        self.assertAlmostEqual(mpi['overlap_host']['THREAD 1.1.1'], 4.0)
        # The rank of TASK 2 is represented by the thread that calls MPI.
        self.assertEqual(mpi['mpi_thread'][2], 'THREAD 1.2.2')
        self.assertEqual(mpi['outside_by_task'], {1: 80.0, 2: 70.0})
        # Its Host unit has no MPI: only its CUDA calls are removed.
        self.assertAlmostEqual(mpi['useful_host']['THREAD 1.2.1'], 85.0)


class RegionTest(unittest.TestCase):

    def _prv(self, folder, lines):
        path = os.path.join(folder, 'trace.prv')
        with open(path, 'w') as prv:
            prv.write('#Paraver (24/11/2026 at 10:00):1000_ns:0:1:2:(1:1,1:1)\n')
            prv.write('\n'.join(lines) + '\n')
        return path

    def test_region_with_unsorted_records(self):
        with tempfile.TemporaryDirectory() as folder:
            # Merged nsys2prv traces are not sorted by time: the MPI
            # events of each rank come after its other events.
            path = self._prv(folder, [
                '2:0:1:1:1:500:63000000:1',
                '2:0:1:1:1:510:63000000:0',
                '2:0:1:1:1:950:50000003:32',
                '2:0:1:1:1:990:50000003:0',
                '2:0:1:1:1:10:50000003:31',
                '2:0:1:1:1:200:50000003:0',
                '2:0:1:2:1:20:50000003:31',
                '2:0:1:2:1:250:50000003:0',
                '2:0:1:2:1:900:50000003:32',
                '2:0:1:2:1:980:50000003:0',
            ])
            # The last rank leaves MPI_Init at 250; the first enters
            # MPI_Finalize at 900.
            self.assertEqual(nsys2prvmetrics.nsys2prv_mpi_region(path), (250, 900))

    def test_no_init_or_finalize(self):
        with tempfile.TemporaryDirectory() as folder:
            path = self._prv(folder, ['2:0:1:1:1:10:50000001:4',
                                      '2:0:1:1:1:20:50000001:0'])
            self.assertIsNone(nsys2prvmetrics.nsys2prv_mpi_region(path))
            path = self._prv(folder, ['2:0:1:1:1:10:50000003:31',
                                      '2:0:1:1:1:20:50000003:0'])
            self.assertEqual(nsys2prvmetrics.nsys2prv_mpi_region(path), (20, None))

    def test_time_window_in_cfg(self):
        text = ('window_end_time_relative 1.000000000000\n'
                'window_begin_time_relative 0.000000000000\n'
                'Analyzer2D.AnalysisLimits: Alltrace\n')
        out = nsys2prvmetrics.apply_time_window(text, 0.25, 0.9)
        self.assertIn('window_begin_time_relative 0.250000000000', out)
        self.assertIn('window_end_time_relative 0.900000000000', out)
        self.assertIn('Analyzer2D.AnalysisLimits: Allwindow', out)

    def test_timeline_clipped_to_region(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, 'kernels.csv')
            with open(path, 'w') as timeline:
                # start, duration, value in ns: one burst crosses the
                # beginning of the region (2 us), one is before it.
                timeline.write('1.2.1\t1000\t2000\t1\n')
                timeline.write('1.2.1\t100\t500\t1\n')
                timeline.write('1.2.1\t5000\t1000\t1\n')
            rows = nsys2prvmetrics.parse_nsys2prv_timeline(path, (2.0, 5.5))
            self.assertEqual([(start, end) for _t, start, end, _v in rows],
                             [(2.0, 3.0), (5.0, 5.5)])


class MpiUsefulCfgTest(unittest.TestCase):

    def _generator(self):
        path = os.path.join(ROOT, 'cfgs', 'nsys2prv', 'generate_useful_duration_cfg.py')
        spec = importlib.util.spec_from_file_location('generate_useful_duration_cfg', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_templates_match_the_generator(self):
        generator = self._generator()
        for name, mpi in ((reportdata.NSYS2PRV_USEFUL_CFG, False),
                          (reportdata.NSYS2PRV_MPI_USEFUL_CFG, True)):
            with open(os.path.join(ROOT, 'cfgs-report', name)) as cfg:
                self.assertEqual(cfg.read(), generator.build(mask=False, mpi=mpi), name)

    def test_mpi_template_codes(self):
        with open(os.path.join(ROOT, 'cfgs-report', reportdata.NSYS2PRV_MPI_USEFUL_CFG)) as cfg:
            codes = nsys2prvevents.cfg_reference_codes(cfg.read())
        self.assertEqual(codes, {63000000, 63000006, 50000001, 50000002,
                                 50000003, 50000004, 50000005})

    def test_report_uses_mpi_template(self):
        folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, folder)
        base = os.path.join(folder, 'ecsim')
        with open(base + '.pcf', 'w') as pcf:
            pcf.write(PCF.format(mpi=MPI_PCF))
        out = os.path.join(folder, 'out')
        os.makedirs(out)
        resources = reportdata._build_resources(
            [base + '.prv'], out, {base + '.prv': NSYS2PRV_MPI_MODE})
        with open(resources[0]['overview_cfg']) as cfg:
            text = cfg.read()
        self.assertIn('outside-mpi', text)
        self.assertIn('50000001', text)


if __name__ == '__main__':
    unittest.main()
