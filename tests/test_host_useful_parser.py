"""parse_host_useful_stats reads only the Running column of the useful
Host profile; a profile without it (no Host thread is ever Running, e.g.
a badly cut trace) gives no useful Host time instead of the Idle time."""
import os
import tempfile
import unittest

import rawdata


def _profile(header, rows):
    folder = tempfile.mkdtemp()
    path = os.path.join(folder, 'app.useful_host.stats.csv')
    with open(path, 'w') as handle:
        handle.write('\t' + header + '\t\n')
        for label, value in rows:
            handle.write('{}\t{:.2f}\t\n'.format(label, value))
        handle.write('\nNum. Cells\t2.00\t\nTotal\t30.00\t\n')
    return path


class HostUsefulParserTest(unittest.TestCase):
    rows = [('THREAD 1.1.1', 10.0), ('GPU-D1.S1', 0.0),
            ('THREAD 1.2.1', 20.0), ('GPU-D2.S1', 0.0)]

    def test_running_column(self):
        self.assertEqual(
            rawdata.parse_host_useful_stats(_profile('Running', self.rows)),
            (30.0, 20.0))

    def test_without_pcf_state_names(self):
        self.assertEqual(
            rawdata.parse_host_useful_stats(
                _profile('Unknown state 1', self.rows)),
            (30.0, 20.0))

    def test_only_idle_column(self):
        self.assertEqual(
            rawdata.parse_host_useful_stats(_profile('Idle', self.rows)),
            (None, None))


if __name__ == '__main__':
    unittest.main()
