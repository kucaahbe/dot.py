import unittest
from unittest.mock import patch
import os
import dotfiles

class TestStateWhenStateFileIsBlank(unittest.TestCase):
    TEST_STATE_FILE = os.path.join('test', 'nonexistent.json')

    def setUp(self):
        self.patcher = patch('dotfiles.STATE_FILE', self.TEST_STATE_FILE)
        self.patcher.start()
        self.state = dotfiles.State()

    def tearDown(self):
        self.patcher.stop()
        os.remove(self.TEST_STATE_FILE)

    def test_loads_blank_repos(self):
        repos = None
        with dotfiles.State() as state:
            repos = state.repos
        self.assertEqual(repos, [])

    def test_saves_state_file(self):
        with dotfiles.State() as state:
            pass
        self.assertTrue(os.access(self.TEST_STATE_FILE, os.R_OK))

    def test_state_file_contains_blank(self):
        with dotfiles.State() as state:
            pass
        file_content = None
        with open(self.TEST_STATE_FILE, 'r', encoding='utf-8') as f:
            file_content = f.read()
        self.assertEqual(file_content, '{}')

class TestStateWhenStateFileIsPresent(unittest.TestCase):
    TEST_STATE_FILE = os.path.join('test', 'state.json')
    TEST_STATE = '{ "/repo2": {}, "/repo1": {} }'

    def setUp(self):
        self.patcher = patch("dotfiles.STATE_FILE", self.TEST_STATE_FILE)
        self.patcher.start()
        with open(self.TEST_STATE_FILE, 'w', encoding='utf-8') as state_f:
            state_f.write(self.TEST_STATE)
        self.state = dotfiles.State()

    def tearDown(self):
        self.patcher.stop()
        os.remove(self.TEST_STATE_FILE)

    def test_loads_repos(self):
        repos = None
        with dotfiles.State() as state:
            repos = state.repos
        self.assertEqual(len(repos), 2)

    def test_each_repo_is_dot(self):
        repos = None
        with dotfiles.State() as state:
            repos = state.repos
        repo = repos[0]
        self.assertIsInstance(repo, dotfiles.Dot)
        self.assertEqual(repo.path, '/repo1')

    def test_repos_sorted(self):
        repos = None
        with dotfiles.State() as state:
            repos = state.repos
        paths = [repo.path for repo in repos]
        self.assertEqual(paths, ['/repo1', '/repo2'])

    def test_persists_state_file(self):
        with dotfiles.State() as state:
            pass
        file_content = None
        with open(self.TEST_STATE_FILE, 'r', encoding='utf-8') as f:
            file_content = f.read()
        expected_content = '''{
  "/repo1": {
    "revision": null,
    "updated_on": null
  },
  "/repo2": {
    "revision": null,
    "updated_on": null
  }
}'''
        self.assertEqual(file_content, expected_content)

if __name__ == '__main__':
    unittest.main()
