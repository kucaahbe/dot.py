from unittest.mock import patch
import os

class FakeState:
    TEST_STATE_FILE = None
    TEST_STATE = None
    patcher = None

    def setup_test_state(self):
        if self.TEST_STATE:
            with open(self.TEST_STATE_FILE, 'w', encoding='utf-8') as test_f:
                test_f.write(self.TEST_STATE)
        self.patcher = patch('dotfiles.STATE_FILE', self.TEST_STATE_FILE)
        self.patcher.start()

    def stop_test_state(self):
        self.patcher.stop()
        os.remove(self.TEST_STATE_FILE)
