#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
import os
import sys
from subprocess import Popen, PIPE
from multiprocessing import Process, Pipe
import argparse
import json
from datetime import datetime
from enum import Enum
from configparser import ConfigParser


class Dotfiles:
    __XDG_DATA_HOME = os.getenv('XDG_DATA_HOME') or [
        os.getenv('HOME'), '.local', 'share']

    STATE_FILE = os.path.join(*(__XDG_DATA_HOME + ['dotfiles.json']))

    def __init__(self):
        self.dots = {}
        self.out = Log()

    def manage(self, args):
        pargs, print_usage = self.__parse_args(args)

        if pargs.command:
            self.__load_state()

        if pargs.command == 'status':
            self.status()
        elif pargs.command == 'add':
            self.add(pargs.path, pargs.url)
        elif pargs.command == 'update':
            self.update()
        elif pargs.command == 'install':
            self.install()
        else:
            print_usage()

    def add(self, path, url):
        rpath = Dot.rpath(path)

        if os.path.isfile(rpath):
            sys.exit(path + ' is regular file')

        for dot in self.dots.values():
            if dot.path == rpath:
                sys.exit(path + ' already added')

        if url:
            if os.path.isdir(rpath):
                sys.exit(path + ' already exists, can not clone there')
        else:
            if os.path.isdir(rpath):
                if Dot.isrepo(rpath):
                    url = Dot.repourl(rpath)
                else:
                    sys.exit(path + ' is not a valid repo')
            else:
                sys.exit(path + ' does not exist')

        dot = Dot(rpath, url)
        dot.getrevision()
        name = os.path.basename(rpath)
        self.dots[name] = dot
        self.__update_state()
        self.out.info('added ' + name)

    def status(self):
        self.out.info('repos status:')
        self.out.info('')
        for name, dot in AsyncDo(self.dots, Dot.check):
            self.out.info(name + "\t" + dot.state.name + "\t" + dot.path)
            self.out.info(" " + dot.url + " " + dot.revision)

    def update(self):
        self.out.info('pulling from remotes...')
        self.out.info('')
        for _ in AsyncDo(self.dots, Dot.update):
            pass
        self.__update_state()
        self.status()

    def install(self, dot_name=None):
        if dot_name and dot_name in self.dots:
            self.dots[dot_name].install()
            return

        cwd = os.getcwd()
        for name, dot in self.dots.items():
            if dot.path == cwd:
                dot_name = name
                break
        if dot_name:
            self.dots[dot_name].install()
            return

        for dot in self.dots.values():
            dot.install()
        self.__update_state()

    def __parse_args(self, args):
        ap = argparse.ArgumentParser()
        sp = ap.add_subparsers(title='commands', dest='command', metavar=None)

        sp.add_parser('status', help='list known rc repos and their status')

        p_add = sp.add_parser('add', help='add rc repo')
        p_add.add_argument('path', type=str, help='rc repo path')
        p_add.add_argument(
            'url',
            type=str,
            help='rc repo (git) url',
            nargs='?',
            default=None)

        sp.add_parser('update', help='update dot files repos')

        p_install = sp.add_parser('install', help='install files')
        p_install.add_argument(
            'repo',
            type=str,
            help='repo name',
            nargs='?',
            default=None)

        return ap.parse_args(args), ap.print_usage

    def __load_state(self):
        state = {}
        if os.access(self.STATE_FILE, os.R_OK):
            with open(self.STATE_FILE, 'r', encoding='utf-8') as f:
                state = json.loads(f.read())

        for repo, details in state.items():
            self.dots[repo] = Dot.from_json(details)

    def __update_state(self):
        state = {}
        for name, dot in self.dots.items():
            state[name] = dot.as_json()
        data = json.dumps(
            state, indent=2, separators=(
                ',', ': '), sort_keys=True)
        with open(self.STATE_FILE, 'w', encoding='utf-8') as f:
            f.write(data)


DotState = Enum('DotState', 'UNKNOWN EXISTS BLANK')


class Dot:
    @staticmethod
    def isrepo(rpath):
        return os.path.isdir(os.path.join(rpath, '.git'))

    @staticmethod
    def repourl(rpath):
        cmd = Cmd(Git.url(rpath)).invoke()
        return cmd.stdout.strip()

    @staticmethod
    def rpath(path):
        return os.path.abspath(os.path.expanduser(os.path.normpath(path)))

    @staticmethod
    def from_json(json_data):
        return Dot(
            url=json_data.get(
                'url',
                None),
            path=json_data['path'],
            revision=json_data.get(
                'revision',
                None),
            updated_on=json_data.get(
                'updated_on',
                None) and datetime.strptime(
                    json_data['updated_on'],
                    '%Y-%m-%dT%H:%M:%S.%f'),
            installed=json_data.get(
                'installed',
                {}),
            errors=json_data.get(
                'errors',
                {}),
        )

    def __init__(
            self,
            path,
            url,
            revision=None,
            updated_on=None,
            installed={},
            errors={}):
        self.state = DotState.UNKNOWN
        self.url = url
        self.path = path
        self.revision = revision
        self.updated_on = updated_on
        self.installed = {
            'links': installed.get(
                'links', {}), 'copies': installed.get(
                'copies', {})}
        self.vcs = Git(self.path)
        self.errors = {'install': errors.get('install', [])}
        self.last_error = None

    def as_json(self):
        return {
            'url': self.url,
            'path': self.path,
            'revision': self.revision,
            'updated_on': self.updated_on and self.updated_on.isoformat(),
            'installed': self.installed,
            'errors': self.errors,
        }

    def check(self):
        self.state = DotState.BLANK
        if self.vcs.exists() and os.system(
                ' '.join(self.vcs.status())) == 0:  # FIXME hardocde
            self.state = DotState.EXISTS

    def update(self):
        self.check()
        success = None
        if self.state == DotState.BLANK:
            if not os.path.exists(self.path):
                os.mkdir(self.path)
            success = self.__action(self.vcs.clone(self.url))
        else:
            success = self.__action(self.vcs.pull())

        if success:
            self.getrevision()
            self.state = DotState.EXISTS

    def getrevision(self):
        success, out = self.__action(self.vcs.revision())
        if success:
            self.revision = out.strip()

    def install(self):
        self.errors['install'] = []
        self.check()
        if self.state != DotState.EXISTS:
            return

        dotfiles_ini = os.path.join(self.path, 'dotfiles.ini')

        if not os.path.exists(dotfiles_ini):
            return

        config = ConfigParser()
        config.read(dotfiles_ini)

        # TODO: remove all previously installed symlinks/files

        self.__make_symlinks(config)

    def __make_symlinks(self, config):
        LINKS = 'links'
        if LINKS not in config.sections():
            self.errors['install'].append(
                'there is no links section in dotfiles.ini')
            return

        for src, dest in config.items(LINKS):
            dest = Dot.rpath(dest)
            src = os.path.join(self.path, src)
            if os.path.exists(dest):
                if os.path.islink(dest):
                    if os.readlink(dest) == src:
                        self.installed['links'][src] = dest
                    else:
                        self.errors['install'].append(
                            dest + ' already exists and is symlink to somewhere else')
                else:
                    self.errors['install'].append(
                        dest + ' already exists and is regular file')
            else:
                dest_dir = os.path.dirname(dest)
                if os.path.isdir(dest_dir):
                    os.symlink(src, dest)
                    self.installed['links'][src] = dest
                else:
                    try:
                        os.makedirs(dest_dir)
                        os.symlink(src, dest)
                        self.installed['links'][src] = dest
                    except os.error as e:
                        self.errors['install'].append(
                            'can not create directory for ' + dest + ' : ' + e)

    def __action(self, command):
        cmd = Cmd(command).invoke()
        if not cmd.success:
            self.last_error = cmd.stderr
        self.updated_on = datetime.utcnow()
        return cmd.success, cmd.stdout


class Cmd:
    def __init__(self, cmd):
        self.cmd = cmd
        self.stdout = None
        self.stderr = None
        self.exitcode = None

    def invoke(self):
        # TODO: use with
        process = Popen(
            self.cmd,
            stdout=PIPE,
            stderr=PIPE
        )
        stdout, stderr = process.communicate()
        self.stdout, self.stderr = self.__str(stdout), self.__str(stderr)
        self.exitcode = process.returncode
        return self

    def success(self):
        return self.exitcode == 0

    def __str(self, maybe_bytes):
        if isinstance(maybe_bytes, bytes):
            return maybe_bytes.decode('utf-8')
        return maybe_bytes


class AsyncDo:
    def __init__(self, items, func):
        self.items = items
        self.func = func
        self.workers = []
        self.i = None

    def __iter__(self):
        self.__start()
        self.i = iter(self.items)

        return self

    def __next__(self):
        n = next(self.i)
        return n, self.items[n]
    next = __next__

    def __start(self):
        if self.workers:
            return
        for name in self.items:
            p_conn, c_conn = Pipe()
            worker = Process(
                target=self.__func, args=(
                    c_conn, self.items[name],))
            self.workers.append((worker, p_conn, name))
            worker.start()
        for worker, _, _ in self.workers:
            worker.join()
        for _, conn, name in self.workers:
            self.items[name] = conn.recv()

    def __func(self, conn, data):
        self.func(data)
        conn.send(data)
        conn.close()


class Git:
    __CMD = ['git']

    @staticmethod
    def url(rpath):
        return Git.__CMD + \
            [f'--git-dir={rpath}/.git', 'config', 'remote.origin.url']

    def __init__(self, path):
        self.path = path

    def clone(self, url):
        return self.__CMD + ['clone', '--quiet',
                             '--recursive', '--', url, self.path]

    def exists(self):
        return os.access(os.path.join(self.path, '.git'), os.R_OK)

    def pull(self):
        return self.__base() + ['pull']

    def push(self):
        return self.__base() + ['push']

    def status(self):
        return self.__base() + ['status', '--porcelain']

    def revision(self):
        return self.__base() + ['rev-parse', 'HEAD']

    def __base(self):
        return self.__CMD + self.__path_settings()

    def __path_settings(self):
        return [t.format(self.path)
                for t in ['--git-dir={}/.git', '--work-tree={}']]


class Log:
    def info(self, text): sys.stdout.write(". " + text + "\n")
    def error(self, text): sys.stderr.write(". " + text + "\n")


if __name__ == '__main__':
    Dotfiles().manage(sys.argv[1:])
