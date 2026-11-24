import contextlib
import io
import os
import tempfile
import unittest

import utils


class WorkingDirectoryTest(unittest.TestCase):

    def test_basicanalysis_folder_stops(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            with self.assertRaises(SystemExit) as stop:
                utils.check_working_directory(utils.basicanalysis_dir())
        self.assertEqual(stop.exception.code, 1)
        self.assertIn('The working directory is the BasicAnalysis folder',
                      out.getvalue())
        self.assertIn('cd <folder of the traces>', out.getvalue())

    def test_other_folder_continues(self):
        with tempfile.TemporaryDirectory() as folder:
            self.assertIsNone(utils.check_working_directory(folder))

    def test_subfolder_continues(self):
        # A folder inside the BasicAnalysis folder (for example a run folder)
        # has its own cfgs-report, so it does not touch the templates.
        self.assertIsNone(utils.check_working_directory(
            os.path.join(utils.basicanalysis_dir(), 'tests')))

    def test_link_to_basicanalysis_folder_stops(self):
        with tempfile.TemporaryDirectory() as folder:
            link = os.path.join(folder, 'ba')
            os.symlink(utils.basicanalysis_dir(), link)
            with contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaises(SystemExit):
                    utils.check_working_directory(link)


if __name__ == '__main__':
    unittest.main()
