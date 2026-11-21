import unittest

from nsys2prvmetrics import NOT_ANALYZED_REASONS, host_threads_not_analyzed
from interactiveplots import _build_not_analyzed_threads_html


THREADS = {
    # TASK 1: driver process without GPU streams; TASK 2: GPU process with
    # a driving thread and a helper thread.
    'host': ['THREAD 1.1.1', 'THREAD 1.2.1', 'THREAD 1.2.2', 'THREAD 1.2.3'],
    'gpu_tasks': {2},
    'labels': [('THREAD 1.1.1', 'THREAD 1.1.1'),
               ('THREAD 1.2.1', 'THREAD 1.2.1'),
               ('THREAD 1.2.2', 'pt_autograd_0'),
               ('THREAD 1.2.3', 'THREAD 1.2.3')],
}


class HostThreadsNotAnalyzedTest(unittest.TestCase):

    def test_reasons(self):
        calls = {'THREAD 1.1.1': 194650.0, 'THREAD 1.2.1': 1708400.0,
                 'THREAD 1.2.2': 500.0}
        result = host_threads_not_analyzed(THREADS, ['THREAD 1.2.1'], calls)
        self.assertEqual([e['thread'] for e in result],
                         ['THREAD 1.1.1', 'THREAD 1.2.2'])
        self.assertEqual(result[0]['reason'], 'no_gpu_streams')
        self.assertAlmostEqual(result[0]['cuda_calls_s'], 0.19465)
        self.assertEqual(result[1]['reason'], 'not_host_unit')
        self.assertEqual(result[1]['label'], 'pt_autograd_0')
        for entry in result:
            self.assertIn(entry['reason'], NOT_ANALYZED_REASONS)

    def test_threads_without_calls_are_not_listed(self):
        self.assertEqual(
            host_threads_not_analyzed(THREADS, ['THREAD 1.2.1'],
                                      {'THREAD 1.2.1': 10.0}), [])


class NotAnalyzedNoteTest(unittest.TestCase):

    def test_note(self):
        not_analyzed = {'b1': [{'thread': 'THREAD 1.1.1', 'label': 'THREAD 1.1.1',
                                'cuda_calls_s': 0.19465,
                                'reason': 'no_gpu_streams'}],
                        'b256': []}
        out = _build_not_analyzed_threads_html(
            not_analyzed, ['b1', 'b256'], ['1 × 1 GPU [T1]', '1 × 1 GPU [T2]'])
        self.assertIn('Host threads not analyzed', out)
        self.assertIn('1 × 1 GPU [T1]', out)
        self.assertNotIn('[T2]', out)
        self.assertIn('0.195', out)
        self.assertIn('no GPU streams', out)

    def test_no_note_without_threads(self):
        self.assertEqual(_build_not_analyzed_threads_html({}, ['a'], ['A']), '')
        self.assertEqual(_build_not_analyzed_threads_html(None, ['a'], ['A']), '')


if __name__ == '__main__':
    unittest.main()
