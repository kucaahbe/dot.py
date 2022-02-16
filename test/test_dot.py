import unittest
import os
import asyncio
from fake_repo import FakeRepo

import dotfiles

class TestDotClassMethods(unittest.TestCase):
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

class TestDotCheckGeneral(unittest.TestCase):
    def setUp(self):
        self.dot = dotfiles.Dot('not/exist')

    def test_no_folder(self):
        asyncio.run(self.dot.check())
        self.assertFalse(self.dot.exists)

class TestDotCheckParseConfig(unittest.TestCase):
    HOME = os.path.expanduser('~')

    def setUp(self):
        self.fake_repo = FakeRepo('repo1')
        self.fake_repo.create()

        self.dot = dotfiles.Dot(self.fake_repo.full_path)

    def tearDown(self):
        self.fake_repo.destroy()

    def __write_config__(self, data):
        config = os.path.join(self.fake_repo.full_path, 'dotfiles.ini')
        with open(config, 'w', encoding='utf-8') as file:
            file.write(data)

    def test_no_config(self):
        asyncio.run(self.dot.check())
        self.assertEqual(self.dot.files, [])

    def test_no_default_section(self):
        config = '''
a = b
'''
        self.__write_config__(config)
        asyncio.run(self.dot.check())
        self.assertEqual(len(self.dot.files), 1)

    def test_with_default_section(self):
        config = '''
[DEFAULT]
a = b
'''
        self.__write_config__(config)
        asyncio.run(self.dot.check())
        self.assertEqual(len(self.dot.files), 1)

    def test_config_links(self):
        config = '''
src1 = dest1
src2
src3 = ~/dest3
'''
        self.__write_config__(config)
        asyncio.run(self.dot.check())

        file1 = self.dot.files[0]
        self.assertEqual(file1.src, 'src1')
        self.assertEqual(file1.dest, os.path.join(self.HOME, 'dest1'))
        self.assertTrue(file1.is_link())

        file2 = self.dot.files[1]
        self.assertEqual(file2.src, 'src2')
        self.assertEqual(file2.dest, os.path.join(self.HOME, '.src2'))
        self.assertTrue(file2.is_link())

        file3 = self.dot.files[2]
        self.assertEqual(file3.src, 'src3')
        self.assertEqual(file3.dest, os.path.join(self.HOME, 'dest3'))
        self.assertTrue(file3.is_link())

class TestDotInstall(unittest.TestCase):
    ORIG_HOME = os.getenv('HOME')
    FAKE_HOME = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fake_home')

    def setUp(self):
        self.fake_repo = FakeRepo('repo1')
        self.fake_repo.create()
        self.fake_repo.put_file('src1', '')

        self.fake_home = FakeRepo('fake_home')
        self.fake_home.create()

        os.environ['HOME'] = self.FAKE_HOME

        self.dot = dotfiles.Dot(self.fake_repo.full_path)
        self.link1 = dotfiles.File('src1', 'dest1', 'link')
        self.dot.files.append(self.link1)

    def tearDown(self):
        self.fake_repo.destroy()
        self.fake_home.destroy()
        os.environ['HOME'] = self.ORIG_HOME

    def test_installs_symlink(self):
        asyncio.run(self.dot.install())

        self.assertTrue(os.path.exists(self.link1.dest))

    def test_symlink_exists_and_is_correct(self):
        os.symlink(os.path.join(self.fake_repo.full_path, self.link1.src), self.link1.dest)
        asyncio.run(self.dot.install())

        self.assertTrue(os.path.exists(self.link1.dest))

    def test_symlink_exists_and_incorrect(self):
        self.fake_home.put_file('existing-file', 'content\n')
        os.symlink(os.path.join(self.fake_home.full_path, 'existing-file'), self.link1.dest)
        asyncio.run(self.dot.install())

        self.assertTrue(os.path.exists(self.link1.dest))
        self.assertTrue(os.readlink(self.link1.dest) == os.path.join(self.fake_repo.full_path, self.link1.src))
        # TODO: test renamed file

    def test_file_exists_at_symlinks_place(self):
        self.fake_home.put_file(self.link1.dest, 'content\n')
        #import pdb; pdb.set_trace()
        #os.symlink(os.path.join(self.fake_home.full_path, 'existing-file'), self.link1.dest)
        asyncio.run(self.dot.install())

        self.assertTrue(os.path.exists(self.link1.dest))
        self.assertTrue(os.readlink(self.link1.dest) == os.path.join(self.fake_repo.full_path, self.link1.src))
        # TODO: test renamed file
