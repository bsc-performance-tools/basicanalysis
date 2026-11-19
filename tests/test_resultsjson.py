import json
import os
import tempfile
import unittest
from argparse import Namespace
from collections import OrderedDict

import resultsjson as rj


class ValueTests(unittest.TestCase):

    def test_values(self):
        self.assertEqual(rj._json_value(97.5), 97.5)
        self.assertEqual(rj._json_value('Non-Avail'), 'Non-Avail')
        self.assertEqual(rj._json_value(float('nan')), 'NaN')
        self.assertEqual(rj._json_value('Warning!'), 'Warning!')
        self.assertIsNone(rj._json_value(None))
        self.assertEqual(rj._count(8.0), 8)
        self.assertEqual(rj._count('48'), 48)

    def test_units(self):
        self.assertEqual(rj._unit('Elapsed time (sec)', None), 's')
        self.assertEqual(rj._unit('Average frequency (GHz)', None), 'GHz')
        self.assertEqual(rj._unit('GPU Active (HW counters)', '%'), '%')
        self.assertEqual(rj._unit('Global efficiency', '%'), '%')


class HierarchyTests(unittest.TestCase):

    def test_levels_and_parents(self):
        doc = OrderedDict([
            ('global_eff', 'Global efficiency'),
            ('parallel_eff', '-- Parallel efficiency'),
            ('load_balance', '   -- Load balance'),
            ('comm_eff', '   -- Communication efficiency'),
            ('serial_eff', '      -- Serialization efficiency'),
            ('comp_scale', '-- Computation scalability'),
        ])
        rows = {key: (level, parent) for key, _text, level, parent in rj._hierarchy(doc)}
        self.assertEqual(rows['global_eff'], (0, None))
        self.assertEqual(rows['parallel_eff'], (1, 'global_eff'))
        self.assertEqual(rows['load_balance'], (2, 'parallel_eff'))
        self.assertEqual(rows['serial_eff'], (3, 'comm_eff'))
        self.assertEqual(rows['comp_scale'], (1, 'global_eff'))

    def test_table_starting_with_a_marked_row(self):
        doc = OrderedDict([('hybrid_eff', '-- Hybrid Parallel efficiency'),
                           ('mpi_parallel_eff', '   -- MPI Parallel efficiency')])
        rows = {key: (level, parent) for key, _text, level, parent in rj._hierarchy(doc)}
        self.assertEqual(rows['hybrid_eff'], (0, None))
        self.assertEqual(rows['mpi_parallel_eff'], (1, 'hybrid_eff'))


class WriteTests(unittest.TestCase):

    def test_simple_mpi_results(self):
        traces = ['/x/a-4p.prv', '/x/a-8p.prv']
        values = lambda a, b: {traces[0]: a, traces[1]: b}
        metrics_result = {
            'kind': 'simple',
            'mod_factors': {'global_eff': values(97.8, 85.3),
                            'parallel_eff': values(97.8, 96.4)},
            'other_metrics': {'elapsed_time': values(25.0, 14.3)},
            'device_hwc_factors': {},
            'scaling_info': None,
        }
        analysis_result = {'raw_data': {'runtime': values(25e6, 14.3e6),
                                        'count_devices': values(0, 0)}}
        args = Namespace(metrics='hybrid', thresholds=None)
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, 'results.json')
            rj.write_results_json(
                metrics_result, analysis_result, traces,
                {traces[0]: 4, traces[1]: 8}, {traces[0]: 4, traces[1]: 8},
                {traces[0]: 1, traces[1]: 1},
                {traces[0]: 'Detailed+MPI', traces[1]: 'Detailed+MPI'},
                args, path=path)
            with open(path) as f:
                result = json.load(f)
        self.assertEqual(result['schema'], 'basicanalysis-results')
        self.assertEqual(result['schema_version'], rj.SCHEMA_VERSION)
        self.assertEqual(result['configuration_meaning'], 'MPI ranks')
        self.assertEqual([t['id'] for t in result['traces']], ['T1', 'T2'])
        self.assertEqual(result['traces'][1]['mpi_ranks'], 8)
        application = [m for m in result['models'] if m['id'] == 'application'][0]
        global_eff = application['metrics'][0]
        self.assertEqual(global_eff['key'], 'global_eff')
        self.assertEqual(global_eff['values'], {'T1': 97.8, 'T2': 85.3})
        self.assertEqual(application['metrics'][1]['parent'], 'global_eff')
        self.assertEqual(result['raw_data']['runtime']['T2'], 14.3e6)
        self.assertNotIn('host', [m['id'] for m in result['models']])


if __name__ == '__main__':
    unittest.main()
