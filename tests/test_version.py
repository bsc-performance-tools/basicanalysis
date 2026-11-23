import os
import re
import unittest

import utils


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class VersionFormatTest(unittest.TestCase):

    def test_format(self):
        # YY.MM, YY.MM.N or YY.MM.dev
        self.assertRegex(utils.__version__,
                         r'^\d{2}\.(0[1-9]|1[0-2])(\.([1-9]\d*|dev))?$')

    def test_version_file_and_user_guide_match(self):
        with open(os.path.join(ROOT, 'VERSION')) as version_file:
            self.assertEqual(version_file.read().strip(), utils.__version__)
        with open(os.path.join(ROOT, 'doc', 'source', 'conf.py')) as conf:
            release = re.search(r"^release = u?'([^']*)'", conf.read(), re.M)
        self.assertEqual(release.group(1), utils.__version__)

    def test_full_version_has_the_commit(self):
        if utils.__commit__:
            self.assertEqual(utils.__version_full__,
                             '{} ({})'.format(utils.__version__,
                                              utils.__commit__))
        else:
            self.assertEqual(utils.__version_full__, utils.__version__)

    def test_archive_placeholder(self):
        # git archive replaces it (export-subst in .gitattributes).
        with open(os.path.join(ROOT, '.gitattributes')) as attributes:
            self.assertIn('utils.py export-subst', attributes.read())


if __name__ == '__main__':
    unittest.main()
