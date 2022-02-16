import os
import shutil

class FakeRepo:
    TEST_DIR = os.path.dirname(os.path.abspath(__file__))

    def __init__(self, path):
        self.path = path
        self.full_path = os.path.join(self.TEST_DIR, self.path)

    def create(self):
        if os.path.exists(self.full_path):
            self.destroy()
        os.mkdir(self.full_path)

    def put_file(self, name, content):
        file_path = os.path.join(self.full_path, name)
        with open(file_path, 'w', encoding='utf-8') as test_f:
            test_f.write(content)

    def destroy(self):
        shutil.rmtree(self.full_path)
