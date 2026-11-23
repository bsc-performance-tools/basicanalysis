import os
import shutil
import tempfile
import unittest

import nsys2prvevents
import reportdata

PCF = """DEFAULT_OPTIONS

EVENT_TYPE
0   {call} CUDA library call
VALUES
0   End
1   cudaLaunchKernel


EVENT_TYPE
0   {kernel} CUDA kernel execution
VALUES
0   End
1   gemm_kernel

"""


class Nsys2prvUsefulCfgTest(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        self.out = os.path.join(self.tmp, 'out')
        os.makedirs(self.out)

    def _trace(self, name, call, kernel):
        base = os.path.join(self.tmp, name)
        with open(base + '.pcf', 'w') as pcf:
            pcf.write(PCF.format(call=call, kernel=kernel))
        return base + '.prv'

    def _filter_codes(self, path):
        with open(path) as cfg:
            return nsys2prvevents.cfg_reference_codes(cfg.read())

    def test_template_uses_reference_codes(self):
        template = os.path.join(reportdata._cfgs_report_source_dir(),
                                reportdata.NSYS2PRV_USEFUL_CFG)
        self.assertEqual(self._filter_codes(template), {63000000, 63000006})

    def test_codes_of_the_trace(self):
        trace = self._trace('vllm', 63000000, 63000006)
        path = reportdata._nsys2prv_useful_cfg(trace, self.out)
        self.assertEqual(os.path.basename(path), 'vllm.useful_duration.cfg')
        self.assertEqual(self._filter_codes(path), {63000000, 63000006})

    def test_codes_changed_by_nsys2prv(self):
        # Another nsys2prv version: same labels, other codes.
        trace = self._trace('other', 63100000, 63100006)
        path = reportdata._nsys2prv_useful_cfg(trace, self.out)
        self.assertEqual(self._filter_codes(path), {63100000, 63100006})
        with open(path) as cfg:
            self.assertNotIn('evt_type_label', cfg.read())

    def test_resources_per_trace(self):
        nsys = self._trace('nsys', 63000000, 63000006)
        extrae = os.path.join(self.tmp, 'extrae.prv')
        resources = reportdata._build_resources(
            [nsys, extrae], self.out,
            {nsys: 'nsys2prv+CUDA', extrae: 'Detailed+MPI'})
        self.assertTrue(resources[0]['overview_cfg'].endswith('nsys.useful_duration.cfg'))
        self.assertTrue(resources[1]['overview_cfg'].endswith(
            os.path.join('cfgs-report', 'useful_duration.cfg')))

    def test_without_pcf_uses_generic_cfg(self):
        trace = os.path.join(self.tmp, 'missing.prv')
        resources = reportdata._build_resources(
            [trace], self.out, {trace: 'nsys2prv+CUDA'})
        self.assertTrue(resources[0]['overview_cfg'].endswith('useful_duration.cfg'))
        self.assertFalse(resources[0]['overview_cfg'].endswith('.useful_duration.cfg'))


if __name__ == '__main__':
    unittest.main()
