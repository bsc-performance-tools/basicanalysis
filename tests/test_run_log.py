import argparse
import atexit
import io
import os
import sys
import tempfile
import unittest
from unittest import mock

import utils


class TestRunLog(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.stdout, self.stderr = sys.stdout, sys.stderr

    def tearDown(self):
        sys.stdout, sys.stderr = self.stdout, self.stderr
        self.tmp.cleanup()

    def _start(self, **kwargs):
        args = argparse.Namespace(log=kwargs.pop('log', None), no_log=kwargs.pop('no_log', False))
        console = io.StringIO()
        sys.stdout = console
        sys.stderr = console
        hooks = []
        argv = ['modelfactors.py', '--workload', '1,2', 'my trace.prv']
        with mock.patch.object(sys, 'argv', argv), \
                mock.patch.object(atexit, 'register', hooks.append):
            path = utils.start_run_log(args, **kwargs)
        return path, console, hooks

    def test_log_has_command_and_output(self):
        log = os.path.join(self.tmp.name, 'run.log')
        path, console, hooks = self._start(log=log)
        self.assertEqual(path, log)
        print('analysis output')
        sys.stderr.write('a warning\n')
        for hook in hooks:
            hook()
        sys.stdout, sys.stderr = self.stdout, self.stderr
        with open(log) as f:
            text = f.read()
        self.assertIn("Command:   modelfactors.py --workload 1,2 'my trace.prv'", text)
        self.assertIn('BasicAnalysis ' + utils.__version__, text)
        self.assertIn('analysis output', text)
        self.assertIn('a warning', text)
        self.assertIn('Finished:', text)
        self.assertIn('analysis output', console.getvalue())

    def test_no_log(self):
        path, _, hooks = self._start(log=os.path.join(self.tmp.name, 'x.log'), no_log=True)
        self.assertIsNone(path)
        self.assertEqual(hooks, [])
        self.assertFalse(os.path.exists(os.path.join(self.tmp.name, 'x.log')))

    def test_no_default_file(self):
        path, _, hooks = self._start(default_file=None)
        self.assertIsNone(path)
        self.assertEqual(hooks, [])

    def test_parser_options(self):
        args = utils.build_argument_parser().parse_args(['--log', 'a.log', 't.prv'])
        self.assertEqual(args.log, 'a.log')
        self.assertFalse(args.no_log)


if __name__ == '__main__':
    unittest.main()
