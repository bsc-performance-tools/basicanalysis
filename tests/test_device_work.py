import os
import tempfile
import unittest

from devicework import (
    DEVICE_KERNELS_KEY,
    WORK_MEASURE_INSTRUCTIONS,
    WORK_MEASURE_THREADS,
    compute_device_work_factors,
    device_work_measure,
    kernel_contributions,
    kernel_display_names,
    kernel_family,
    scan_device_kernels,
    top_kernel_rows,
)


EXTRAE_PRV = """#Paraver (08/10/2026 at 23:04):1000_ns:1(2):1:1(2:1),2
2:1:1:1:1:10:63000006:7:63000011:999
2:1:1:1:1:20:63000006:0
2:1:1:1:2:100:63000006:7:63000007:15:63000011:4:63000012:256
2:1:1:1:2:300:63000006:0:63000007:0
2:1:1:1:2:310:63000006:8:63000007:16:63000011:2:63000012:128
2:1:1:1:2:410:63000006:0:63000007:0
2:1:1:1:2:500:63000006:7:63000007:15:63000011:4:63000012:256
2:1:1:1:2:600:63000006:0:63000007:0
2:1:1:1:2:900:63000006:8:63000007:16:63000011:2:63000012:128
"""

EXTRAE_ROW = """LEVEL CPU SIZE 2
1.node
2.node

LEVEL NODE SIZE 1
node

LEVEL THREAD SIZE 2
THREAD 1.1.1
GPU-D1.S1
"""

EXTRAE_PCF = """EVENT_TYPE
0    63000006    CUDA kernel execution
VALUES
0      End
7      void stencil_kernel [void stencil_kernel<double>(int)]
8      void reduce_kernel [void reduce_kernel<double>(int)]

"""

NSYS_PRV = """#Paraver (11/08/2026 at 23:07):2000_ns:0:1:2:(1:1,2:1)
2:0:1:2:2:100:63000006:5:9101:2:9102:3:9103:1:9104:128:9105:1:9106:1
2:0:1:2:2:200:63000006:0:9101:0:9102:0:9103:0:9104:0:9105:0:9106:0
2:0:1:2:2:300:63000006:6:9101:10:9102:1:9103:1:9104:64:9105:2:9106:1
2:0:1:2:2:700:63000006:0
"""

NSYS_ROW = """LEVEL NODE SIZE 1
node1

LEVEL TASK SIZE 2
TASK 1.1
TASK 1.2

LEVEL THREAD SIZE 3
THREAD 1.1.1
THREAD 1.2.1
CUDA-D0.S7
"""

NSYS_PCF = """EVENT_TYPE
0   63000006 CUDA kernel
VALUES
5 nvjet_sm90_tst_256x8_64x6_4x1_v_bz_TNT
6 nvjet_sm90_tst_192x192_64x4_2x1_v_bz_coopB_TNN

"""


def _write_trace(directory, name, prv, row, pcf):
    base = os.path.join(directory, name)
    for extension, content in (('.prv', prv), ('.row', row), ('.pcf', pcf)):
        with open(base + extension, 'w') as output:
            output.write(content)
    return base


class KernelScanTests(unittest.TestCase):

    def test_extrae_kernels_on_streams_only(self):
        with tempfile.TemporaryDirectory() as directory:
            base = _write_trace(directory, 'extrae', EXTRAE_PRV, EXTRAE_ROW,
                                EXTRAE_PCF)
            result = scan_device_kernels(base + '.prv', base + '.pcf',
                                         base + '.row')

        # The kernel on the host thread (1.1.1) is ignored, and the kernel
        # still running at the end of the trace is not counted.
        self.assertEqual(result['kernels'], 3)
        self.assertEqual(result['threads'], 4 * 256 * 2 + 2 * 128)
        stencil = result['families']['void stencil_kernel [void stencil_kernel<double>(int)]']
        self.assertEqual(stencil[0], 2)
        self.assertAlmostEqual(stencil[1], 0.3)  # 200 + 100 ns in us
        self.assertEqual(stencil[2], 2 * 4 * 256)

    def test_nsys2prv_grid_and_families(self):
        with tempfile.TemporaryDirectory() as directory:
            base = _write_trace(directory, 'nsys', NSYS_PRV, NSYS_ROW, NSYS_PCF)
            result = scan_device_kernels(base + '.prv', base + '.pcf',
                                         base + '.row')

        self.assertEqual(result['kernels'], 2)
        self.assertEqual(result['threads'], 2 * 3 * 128 + 10 * 64 * 2)
        # Both cuBLAS tile variants are one family.
        self.assertEqual(list(result['families']), ['nvjet_sm90_tst'])
        self.assertEqual(result['families']['nvjet_sm90_tst'][0], 2)
        self.assertAlmostEqual(result['families']['nvjet_sm90_tst'][1], 0.5)


class KernelNameTests(unittest.TestCase):

    def test_family_removes_the_tile_suffix(self):
        self.assertEqual(
            kernel_family('nvjet_sm90_tst_192x192_64x4_2x1_v_bz_coopB_TNN'),
            'nvjet_sm90_tst')
        self.assertEqual(kernel_family('act_and_mul_kernel'),
                         'act_and_mul_kernel')

    def test_display_names_of_lambda_kernels(self):
        left = ('void clover::par_ranged1d_kernel [void clover::par_ranged1d_kernel'
                '<tag<&(clover_pack_message_left(global_variables&)), 1u>>]')
        right = left.replace('left', 'right')
        names = kernel_display_names([left, right, 'void other [x]', 'void other [y]'])

        self.assertEqual(names[left],
                         'clover::par_ranged1d_kernel (clover_pack_message_left)')
        self.assertEqual(names[right],
                         'clover::par_ranged1d_kernel (clover_pack_message_right)')
        self.assertEqual(sorted([names['void other [x]'], names['void other [y]']]),
                         ['other #1', 'other #2'])


def _raw_data(**values):
    raw_data = {
        'useful_device': {'a': 100.0, 'b': 150.0},
        'count_devices': {'a': 1, 'b': 1},
        'device_threads': {'a': 1000.0, 'b': 1000.0},
        'hwc_sm_issue_int': {'a': 'Non-Avail', 'b': 'Non-Avail'},
        'hwc_sm_issue_clock_int': {'a': 'Non-Avail', 'b': 'Non-Avail'},
    }
    raw_data.update(values)
    return raw_data


class DecompositionTests(unittest.TestCase):

    def test_threads_measure_strong_scaling(self):
        raw_data = _raw_data()
        comp_scale = {'a': 100.0, 'b': 100.0 * 100.0 / 150.0}

        factors, measure = compute_device_work_factors(
            raw_data, ['a', 'b'], comp_scale, lambda trace: 1.0)

        self.assertEqual(measure, WORK_MEASURE_THREADS)
        self.assertAlmostEqual(factors['dev_work_scale']['b'], 100.0)
        self.assertAlmostEqual(factors['dev_throughput_scale']['b'],
                               comp_scale['b'])
        for key in ('dev_ipc_scale', 'dev_inst_scale', 'dev_freq_scale'):
            self.assertEqual(factors[key]['b'], 'Non-Avail')

    def test_product_is_the_computation_scalability(self):
        raw_data = _raw_data(
            device_threads={'a': 1000.0, 'b': 3000.0},
            hwc_sm_issue_int={'a': 10.0, 'b': 60.0},
            hwc_sm_issue_clock_int={'a': 10.0 * 2000.0, 'b': 60.0 * 1800.0},
        )
        ratio = {'a': 1.0, 'b': 4.0}
        comp_scale = {trace: 100.0 * 100.0 * ratio[trace]
                      / raw_data['useful_device'][trace] for trace in ratio}

        factors, measure = compute_device_work_factors(
            raw_data, ['a', 'b'], comp_scale, ratio.get)

        self.assertEqual(measure, WORK_MEASURE_INSTRUCTIONS)
        instructions = factors['dev_inst_scale']['b']
        ipc = factors['dev_ipc_scale']['b']
        frequency = factors['dev_freq_scale']['b']
        self.assertAlmostEqual(ipc * instructions * frequency / 100.0 ** 2,
                               comp_scale['b'])
        # W = 108000 vs 20000 (x5.4) with r = 4.
        self.assertAlmostEqual(instructions, 100.0 * 4.0 / 5.4)
        self.assertAlmostEqual(ipc, 100.0 * (60.0 / 150.0) / (10.0 / 100.0))
        self.assertAlmostEqual(frequency, 90.0)
        self.assertEqual(factors['dev_work_scale']['b'], 'Non-Avail')
        self.assertEqual(factors['dev_throughput_scale']['b'], 'Non-Avail')

    def test_ipc_is_coverage_times_active_issue_rate(self):
        raw_data = _raw_data(
            hwc_sm_issue_int={'a': 10.0, 'b': 60.0},
            hwc_sm_issue_clock_int={'a': 10.0 * 2000.0, 'b': 60.0 * 1800.0},
            hwc_sms_active_int={'a': 50.0, 'b': 120.0},
        )
        comp_scale = {'a': 100.0, 'b': 50.0}

        factors, _measure = compute_device_work_factors(
            raw_data, ['a', 'b'], comp_scale, lambda trace: 1.0)

        coverage = factors['dev_cov_scale']['b']
        active_issue = factors['dev_active_issue_scale']['b']
        # SMs Active during kernels 0.5 -> 0.8; issue of active SMs 0.2 -> 0.5.
        self.assertAlmostEqual(coverage, 160.0)
        self.assertAlmostEqual(active_issue, 250.0)
        self.assertAlmostEqual(coverage * active_issue / 100.0,
                               factors['dev_ipc_scale']['b'])

    def test_coverage_needs_sms_active(self):
        raw_data = _raw_data(
            hwc_sm_issue_int={'a': 10.0, 'b': 60.0},
            hwc_sm_issue_clock_int={'a': 20.0, 'b': 108.0},
        )
        factors, _measure = compute_device_work_factors(
            raw_data, ['a', 'b'], {'a': 100.0, 'b': 50.0}, lambda trace: 1.0)
        self.assertNotEqual(factors['dev_ipc_scale']['b'], 'Non-Avail')
        self.assertEqual(factors['dev_cov_scale']['b'], 'Non-Avail')
        self.assertEqual(factors['dev_active_issue_scale']['b'], 'Non-Avail')

    def test_instructions_need_every_trace(self):
        raw_data = _raw_data(
            hwc_sm_issue_int={'a': 10.0, 'b': 'Non-Avail'},
            hwc_sm_issue_clock_int={'a': 20.0, 'b': 'Non-Avail'},
        )
        self.assertEqual(device_work_measure(raw_data, ['a', 'b']),
                         WORK_MEASURE_THREADS)

    def test_without_work_or_with_one_trace(self):
        raw_data = _raw_data(device_threads={'a': 'Non-Avail', 'b': 1.0})
        factors, measure = compute_device_work_factors(
            raw_data, ['a', 'b'], {'a': 100.0, 'b': 50.0}, lambda trace: 1.0)
        self.assertIsNone(measure)
        self.assertEqual(factors['dev_work_scale']['b'], 'Non-Avail')

        factors, _measure = compute_device_work_factors(
            _raw_data(), ['a'], {'a': 100.0}, lambda trace: 1.0)
        self.assertEqual(factors['dev_work_scale']['a'], 'Non-Avail')


class ContributionTests(unittest.TestCase):

    def test_shares_add_up_to_100(self):
        raw_data = {DEVICE_KERNELS_KEY: {
            'a': {'k1': [10, 50.0, 100], 'k2': [10, 50.0, 100]},
            'b': {'k1': [20, 120.0, 200], 'k2': [10, 60.0, 100],
                  'k3': [1, 20.0, 10]},
        }}

        result = kernel_contributions(raw_data, ['a', 'b'], lambda trace: 1.0)['b']

        self.assertAlmostEqual(result['gap'], 100.0)
        rows = {row['kernel']: row for row in result['rows']}
        self.assertAlmostEqual(rows['k1']['share'], 70.0)
        self.assertAlmostEqual(rows['k2']['share'], 10.0)
        self.assertAlmostEqual(rows['k3']['share'], 20.0)
        self.assertEqual([row['kernel'] for row in result['rows']],
                         ['k1', 'k3', 'k2'])

    def test_reference_scaled_by_the_work_ratio(self):
        raw_data = {DEVICE_KERNELS_KEY: {
            'a': {'k1': [1, 10.0, 1]},
            'b': {'k1': [4, 30.0, 4]},
        }}
        result = kernel_contributions(raw_data, ['a', 'b'], lambda trace: 4.0)['b']

        # 30 - 10 x 4 = -10: faster than the ideal.
        self.assertAlmostEqual(result['gap'], -10.0)
        self.assertAlmostEqual(result['rows'][0]['share'], 100.0)

    def test_top_rows_add_the_rest(self):
        rows = [{'kernel': str(i), 'change': 1.0, 'share': 10.0, 'count_ref': 1,
                 'count': 1, 'time_ref': 1.0, 'time': 2.0, 'threads_ref': 1,
                 'threads': 1} for i in range(12)]
        top = top_kernel_rows(rows, top=10)

        self.assertEqual(len(top), 11)
        self.assertEqual(top[-1]['kernel'], 'Other kernels (2)')
        self.assertAlmostEqual(top[-1]['share'], 20.0)


if __name__ == '__main__':
    unittest.main()
