import unittest
from unittest.mock import patch
import os
import dotfiles

TEST_STATE_FILE = os.path.join('test', 'state.json')
TEST_STATE = '{ "repo1": {} }'

class TestStateWhenStateFileIsBlank(unittest.TestCase):
    def setUp(self):
        self.patcher = patch('dotfiles.STATE_FILE', os.path.join('some', 'location'))
        self.patcher.start()
        self.state = dotfiles.State()

    def tearDown(self):
        self.patcher.stop()

    def test___load__(self):
        self.state.__load__()
        self.assertEqual(self.state.repos, [])

class TestStateWhenStateFileIsPresent(unittest.TestCase):
    def setUp(self):
        self.patcher = patch("dotfiles.STATE_FILE", TEST_STATE_FILE)
        self.patcher.start()
        with open(TEST_STATE_FILE, 'w', encoding='utf-8') as state_f:
            state_f.write(TEST_STATE)
        self.state = dotfiles.State()

    def tearDown(self):
        self.patcher.stop()
        os.remove(TEST_STATE_FILE)

    def test___load__(self):
        self.state.__load__()
        self.assertEqual(len(self.state.repos), 1)

if __name__ == '__main__':
    unittest.main()
