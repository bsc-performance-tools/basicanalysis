import unittest

from configuration import (
    add_plot_trace_ids,
    configuration_caption,
    configuration_description,
)
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
                         'MPI ranks')
        self.assertEqual(_configuration_header(traces, {}), 'Configuration')


class ConfigurationDescriptionTests(unittest.TestCase):
    """The stdout headers and the plot captions say what the configuration
    labels mean, with the text of the report."""

    def test_descriptions(self):
        cases = {
            'Detailed+MPI': 'MPI ranks',
            'Burst+MPI': 'MPI ranks',
            'Detailed+OpenMP': 'Threads',
            'Detailed+MPI+OpenMP': 'Parallel units (MPI ranks × threads/rank)',
            'Detailed+MPI+CUDA': 'MPI ranks × GPUs per rank',
            'Detailed+CUDA': 'Processes × GPUs per process',
            'nsys2prv+CUDA': 'Processes × GPUs per process',
        }
        for mode, text in cases.items():
            self.assertEqual(configuration_description([mode, mode]), text, mode)

    def test_different_models_have_no_common_description(self):
        self.assertIsNone(configuration_description(['Detailed+MPI', 'Detailed+MPI+OpenMP']))

    def test_caption(self):
        self.assertEqual(configuration_caption(['Detailed+MPI+OpenMP']),
                         'Configuration: Parallel units (MPI ranks × threads/rank)'
                         ' [Tn = trace ID]')
        self.assertEqual(configuration_caption(['Detailed+MPI'], trace_ids=False),
                         'Configuration: MPI ranks')

if __name__ == '__main__':
    unittest.main()
