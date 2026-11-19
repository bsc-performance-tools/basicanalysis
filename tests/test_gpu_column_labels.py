import unittest

from configuration import add_plot_trace_ids, gpu_configuration_caption
from hybridmetrics import _build_hybrid_configuration_labels, _configuration_header


class GpuColumnLabelTests(unittest.TestCase):
    """The standard output, CSV files and plots label GPU configurations as
    the report: processes x GPUs per process."""

    def labels(self, modes, tasks, devices, processes=None):
        traces = ['t{}'.format(i) for i in range(len(modes))]
        return _build_hybrid_configuration_labels(
            traces,
            dict(zip(traces, processes or [0] * len(traces))),
            dict(zip(traces, tasks)),
            dict(zip(traces, [1] * len(traces))),
            dict(zip(traces, modes)),
            {'count_devices': dict(zip(traces, devices))},
        ), traces

    def test_nsys2prv_and_mpi_gpu(self):
        labels, _ = self.labels(['nsys2prv+CUDA', 'Detailed+MPI+CUDA'],
                                [8, 2], [8, 8], [48, 10])
        self.assertEqual(labels, ['8 × 1 GPU', '2 × 4 GPUs'])

    def test_same_label_gets_report_trace_id(self):
        labels, _ = self.labels(['nsys2prv+CUDA'] * 2, [8, 8], [8, 8], [48, 40])
        self.assertEqual(labels, ['8 × 1 GPU [T1]', '8 × 1 GPU [T2]'])
        self.assertEqual(add_plot_trace_ids(labels),
                         ['8 × 1 GPU [T1]', '8 × 1 GPU [T2]'])

    def test_header(self):
        _, traces = self.labels(['nsys2prv+CUDA'], [8], [8])
        self.assertEqual(_configuration_header(traces, {traces[0]: 'nsys2prv+CUDA'}),
                         'Processes × GPUs per process')
        self.assertEqual(_configuration_header(traces, {traces[0]: 'Detailed+MPI'}),
                         'Configuration')


class GpuCaptionTests(unittest.TestCase):

    def test_caption_says_what_the_label_means(self):
        self.assertEqual(
            gpu_configuration_caption(['8 × 1 GPU [T1]', '8 × 1 GPU [T2]']),
            'Configuration: processes × GPUs per process [Tn = trace ID]')
        self.assertEqual(gpu_configuration_caption(['2 × 4 GPUs']),
                         'Configuration: processes × GPUs per process')
        self.assertIsNotNone(gpu_configuration_caption(['8 (4 GPUs) [T1]']))

    def test_no_caption_without_gpus(self):
        self.assertIsNone(gpu_configuration_caption(['64 (8x8) [T1]', '128']))

if __name__ == '__main__':
    unittest.main()
