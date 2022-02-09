#!/usr/bin/env python3
import os
import sys
import logging
import asyncio
import functools
import shutil
import shlex
import argparse
import json
from datetime import datetime
import configparser
from itertools import chain

XDG_DATA_HOME = os.getenv('XDG_DATA_HOME') or os.path.join(os.getenv('HOME'), '.local', 'share')
STATE_FILE = os.path.join(XDG_DATA_HOME, 'dotfiles.state')
CONFIG_NAME = 'dotfiles.ini'

logger = logging.getLogger(__name__)

async def main(args):
    logger.setLevel(logging.DEBUG)
    log_file = logging.FileHandler(os.path.join(XDG_DATA_HOME, 'dotfiles.log'))
    log_file.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s %(name)s %(levelname)s: %(message)s')
    log_file.setFormatter(formatter)
    logger.addHandler(log_file)

    pargs, print_usage = parse_args(args)

    if not pargs.command or pargs.command == 'status':
        await status()
    elif pargs.command == 'add':
        await add(pargs.path, pargs.url)
    elif pargs.command == 'rm':
        await remove(pargs.path)
    elif pargs.command == 'update':
        await update()
    elif pargs.command == 'install':
        await install()
    else:
        print_usage()

def parse_args(args):
    parser = argparse.ArgumentParser()

    commands_parser = parser.add_subparsers(title='commands', dest='command', metavar=None)
    commands_parser.add_parser('status', help='list known directories and their status')

    p_add = commands_parser.add_parser('add', help='add rc repo')
    p_add.add_argument('path', type=str, help='rc repo path')
    p_add.add_argument('url', type=str, help='rc repo (git) url', nargs='?', default=None)

    p_remove = commands_parser.add_parser('rm', help='remove repo')
    p_remove.add_argument('path', type=str, help='repo path')

    commands_parser.add_parser('update', help='update dot files repos')

    p_install = commands_parser.add_parser('install', help='install files')
    p_install.add_argument('repo', type=str, help='repo name', nargs='?', default=None)

    return parser.parse_args(args), parser.print_usage

class State:
    def __init__(self):
        self.repos = None

    def __load__(self):
        raw_state = {}
        if os.access(STATE_FILE, os.R_OK):
            with open(STATE_FILE, 'r', encoding='utf-8') as state_f:
                raw_state = json.loads(state_f.read())

        self.repos = [Dot(path).load(raw_state[path]) for path in sorted(raw_state)]

    def __save__(self):
        state = {repo.path:repo.as_json() for repo in self.repos}
        data = json.dumps(state, indent=2, separators=(',', ': '), sort_keys=True)
        with open(STATE_FILE, 'w', encoding='utf-8') as state_f:
            state_f.write(data)

    def __enter__(self):
        self.__load__()

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.__save__()

        if exc_type == SystemExit:
            return False

        if exc_type:
            logger.error('exception while managing state:', exc_info=(exc_type, exc_val, exc_tb))
            return True

        return False

def with_state(func):
    @functools.wraps(func)
    async def state_managed(*args, **kwargs):
        with State() as state:
            kwargs['state'] = state
            if asyncio.iscoroutinefunction(func):
                await func(*args, **kwargs)
            else:
                func(*args, **kwargs)
    return state_managed

@with_state
async def status(state=None):
    await asyncio.gather(*[repo.check() for repo in state.repos])

    print('repos status:\n')
    for repo in state.repos:
        print_repo_status(repo)

def print_repo_status(repo):
    path_output = PP(Dot.nice_path(repo.path))
    if not repo.exists:
        path_output.decorate(9)
        print(f'{path_output}:')
        print('  repo does not exist')
        return

    path_output.decorate(1)
    print(f'{path_output}', end='')
    if repo.vcs:
        vcs = repo.vcs
        print(f' {vcs.name}:{vcs.branch}@{vcs.commit}', end='')
    print()

    if repo.files:
        for file in repo.files:
            if file.is_link():
                print(f'  {file.src} -> {Dot.nice_path(file.dest)}')
    else:
        print(f'  {CONFIG_NAME} not found')

@with_state
async def add(path, url, state=None):
    path = Dot.normalized_path(path)

    for repo in state.repos:
        if repo.path == path:
            sys.exit(f'"{path}" is already added')

    if os.path.isfile(path):
        sys.exit(f'"{path}" is a regular file')

    if url:
        if os.path.isdir(path):
            sys.exit(path + ' already exists, can not clone there')
        print('TODO')
    else:
        if not os.path.isdir(path):
            sys.exit(f'"{path}" does not exist')
        repo = Dot(path)
        await repo.check()
        state.repos.append(repo)
        print(f'"{repo.path}" added')

@with_state
def remove(path, state=None):
    try:
        path = Dot.normalized_path(path)
        idx = [repo.path for repo in state.repos].index(path)
        repo = state.repos[idx]
        del state.repos[idx]
        print(f'repo at {repo.path} was excluded from configuration')
    except ValueError:
        sys.exit(f'"{path}" is unknown repo folder')

@with_state
async def update(state=None):
    print('pulling from remotes...\n')

    await asyncio.gather(*[repo.update() for repo in state.repos])
    await status()

@with_state
async def install(state=None):
    await asyncio.gather(*[repo.install() for repo in state.repos])


class Dot:
    TIME_FMT = '%Y-%m-%dT%H:%M:%S.%f'

    @staticmethod
    def normalized_path(path):
        return os.path.abspath(os.path.expanduser(os.path.normpath(path)))

    @staticmethod
    def nice_path(path):
        part_path = os.path.relpath(path, start=os.path.expanduser('~'))
        if part_path == path:
            return path

        return os.path.join('~', part_path)

    def __init__(self, path):
        self.path = self.__class__.normalized_path(path)
        self.exists = False
        self.updated_on = None
        self.revision = None
        self.files = []
        self.vcs = None

    def load(self, data):
        raw_updated_on = data.get('updated_on', None)
        self.updated_on = raw_updated_on and datetime.strptime(raw_updated_on, self.TIME_FMT)

        return self

    def as_json(self):
        return {
            'revision': self.revision,
            'updated_on': self.updated_on and self.updated_on.isoformat(),
        }

    async def check(self):
        if not os.access(self.path, os.R_OK):
            return

        self.exists = True
        self.__load_config__()

        if Git.exists(self.path):
            self.vcs = Git(self.path)

        if self.vcs:
            await self.vcs.load()

    async def update(self):
        await self.check()
        if self.vcs:
            await self.vcs.update()

    async def install(self):
        await self.check()
        self.__symlink_files__()

    def __load_config__(self):
        config_file = os.path.join(self.path, CONFIG_NAME)

        if not os.path.exists(config_file):
            return

        config = configparser.ConfigParser(allow_no_value = True)
        with open(config_file, 'r', encoding='utf-8') as file:
            config.read_file(chain([f'[{configparser.DEFAULTSECT}]'], file), source=config_file)

        for src, dest in sorted(config.defaults().items()):
            self.files.append(File(src, dest, 'link'))

    def __symlink_files__(self):
        # TODO: remove all previously installed symlinks/files

        for file in [f for f in self.files if f.is_link()]:
            src = os.path.join(self.path, file.src)
            dest = Dot.normalized_path(file.dest)

            print(src, dest)
            if os.path.exists(dest):
                if os.path.islink(dest):
                    real_link = os.readlink(dest)
                    if real_link == src:
                        logger.debug('link OK: %s -> %s', dest, src)
                    else:
                        logger.error('link NOT OK: %s -> %s', dest, real_link)
                else:
                    logger.error('link is file: %s', dest)
            else:
                dest_dir = os.path.dirname(dest)
                if os.path.isdir(dest_dir):
                    os.symlink(src, dest)
                    # self.installed['links'][src] = dest
                else:
                    try:
                        os.makedirs(dest_dir)
                        os.symlink(src, dest)
                        # self.installed['links'][src] = dest
                    except os.error as error:
                        logger.error('can not create symlink %s -> %s:', dest, src)
                        logger.exception(error)


class File:
    def __init__(self, src, dest, itype):
        self.src = src
        self._dest = dest
        self._type = itype

    def is_link(self):
        return self._type == 'link'

    @property
    def dest(self):
        if not self._dest:
            return os.path.join(os.path.expanduser('~'), f'.{self.src}')

        if self._dest.startswith(('~', '/')):
            return os.path.expanduser(self._dest)

        return os.path.join(os.path.expanduser('~'), self._dest)


class Cmd:
    def __init__(self, *cmd):
        self.cmd = ' '.join([shlex.quote(c) for c in cmd])
        self.stdout = None
        self.stderr = None
        self.exitcode = None

    async def run(self):
        proc = await asyncio.create_subprocess_shell(self.cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE)

        logger.debug('invoking cmd: %s', self.cmd)
        self.stdout, self.stderr = await proc.communicate()
        self.exitcode = proc.returncode

    def success(self):
        return self.exitcode == 0

    def stdout_if_success(self):
        if self.success():
            return self.stdout.decode('utf-8').rstrip('\n')

        logger.error('command %s failed with %i: %s', self.cmd, self.exitcode, self.stderr)
        return None


class Git:
    @staticmethod
    def exists(path):
        return os.access(os.path.join(path, '.git'), os.R_OK)

    def __init__(self, path):
        self.path = path
        self.name = 'git'
        self.branch = None
        self.commit = None

        self._cmd = [shutil.which('git'), f'--git-dir={self.path}/.git', f'--work-tree={self.path}']

    async def load(self):
        branch = Cmd(*self._cmd, 'branch', '--show-current')
        commit = Cmd(*self._cmd, 'rev-parse', '--short', 'HEAD')

        await asyncio.gather(*[c.run() for c in [branch, commit]])

        self.branch = branch.stdout_if_success()
        self.commit = commit.stdout_if_success()

    # def clone(self, url):
    #     return self.__CMD + ['clone', '--quiet', '--recursive', '--', url, self.path]

    async def update(self):
        await Cmd(*self._cmd, 'pull', '--quiet').run()
        await Cmd(*self._cmd, 'submodule', '--quiet', 'update').run()
        await self.load()

    # async def push(self):
    #     await Cmd(*self._cmd, 'push', '--quiet').run()
    #     await self.load()

    # async def status(self):
    #     await Cmd(*self._cmd, 'status', '--porcelain').run()
    #     await self.load()

class PP:
    def __init__(self, string, *modes):
        self.string = string
        self.modes = set(modes)

    def decorate(self, *modes):
        for mode in modes:
            self.modes.add(mode)

    def __str__(self):
        return f'{self.ansi(*self.modes)}{self.string}{self.ansi(0)}'

    @staticmethod
    def ansi(*codes):
        code = ','.join(map(str, codes))
        return f'\033[{code}m'

if __name__ == '__main__':
    asyncio.run(main(sys.argv[1:]))
