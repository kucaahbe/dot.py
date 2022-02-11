import unittest
import os
import asyncio

from fake_state import FakeState

import dotfiles

class TestWithStateFunction(unittest.TestCase, FakeState):
    TEST_STATE_FILE = os.path.join('test', 'state.json')
    TEST_STATE = '{}'

    def setUp(self):
        self.setup_test_state()

    def tearDown(self):
        self.stop_test_state()

    def test_regular_function(self):
        repos = None
        @dotfiles.with_state
        def regular_function(state=None):
            nonlocal repos
            repos = state.repos
        asyncio.run(regular_function())
        self.assertIsInstance(repos, list)

    def test_async_function(self):
        repos = None
        @dotfiles.with_state
        async def async_function(state=None):
            nonlocal repos
            repos = state.repos
        asyncio.run(async_function())
        self.assertIsInstance(repos, list)


if __name__ == '__main__':
    unittest.main()
