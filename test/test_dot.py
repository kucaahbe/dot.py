import unittest
import os

import dotfiles

class TestDot(unittest.TestCase):
    HOME = os.path.expanduser('~')
    CWD = os.getcwd()

    def test_normalized_path(self):
        raw_path = '~/some//folder/'
        normalized_path = dotfiles.Dot.normalized_path(raw_path)
        self.assertEqual(normalized_path, f'{self.HOME}/some/folder')

        raw_path = 'some/folder/'
        normalized_path = dotfiles.Dot.normalized_path(raw_path)
        self.assertEqual(normalized_path, f'{self.CWD}/some/folder')

        raw_path = './some/folder/'
        normalized_path = dotfiles.Dot.normalized_path(raw_path)
        self.assertEqual(normalized_path, f'{self.CWD}/some/folder')

    def test_nice_path(self):
        raw_path = f'{self.HOME}/some/folder'
        nice_path = dotfiles.Dot.nice_path(raw_path)
        self.assertEqual(nice_path, '~/some/folder')

        raw_path = '~/some//folder'
        nice_path = dotfiles.Dot.nice_path(raw_path)
        self.assertEqual(nice_path, '~/some/folder')

        raw_path = '/some/folder'
        nice_path = dotfiles.Dot.nice_path(raw_path)
        self.assertEqual(nice_path, '/some/folder')
