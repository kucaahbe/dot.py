# -*- coding: UTF-8 -*-
import os
import sys
from subprocess import Popen, PIPE
from multiprocessing import Process, Pipe
import argparse
import json
from datetime import datetime
from enum import Enum
if sys.version_info > (3, 0):
  from urllib.request import urlopen
  from urllib.parse import urlparse
  from configparser import ConfigParser
else:
  from urllib2 import urlopen
  from urlparse import urlparse
  import ConfigParser

class Dotfiles:
  __XDG_DATA_HOME = os.getenv('XDG_DATA_HOME') or [os.getenv('HOME'), '.local', 'share']

  STATE_FILE   = os.path.join(*(__XDG_DATA_HOME + ['dotfiles.json']))

  def __init__(self):
    self.dots = {}
    self.out = Log()

  def manage(self, args):
    pargs, print_usage = self.__parse_args(args)

    if pargs.command == 'status':
      self.status()
    elif pargs.command == 'add':
      self.add(pargs.path, pargs.url)
    elif pargs.command == 'update':
      self.update()
    #elif pargs.command == 'upload':
    #  self.upload()
    #elif pargs.command == 'self-update':
    #  self.self_update()
    else:
      print_usage()

  def add(self, path, url):
    self.__load_state()
    rpath = os.path.abspath(os.path.expanduser(os.path.normpath(path)))

    if os.path.isfile(rpath):
      self.out.error(path + ' is regular file')
      exit(1)

    for dot in self.dots.values():
      if dot.path == rpath:
        self.out.error(path + ' already added')
        exit(1)

    if url:
      if os.path.isdir(rpath):
        self.out.error(path + ' already exists, can not clone there')
        exit(1)
    else:
      if os.path.isdir(rpath):
        if Dot.isrepo(rpath):
          url = Dot.repourl(rpath)
        else:
          self.out.error(path + ' is not a valid repo')
          exit(1)
      else:
        self.out.error(path + ' does not exist')
        exit(1)

    dot = Dot(rpath, url)
    dot.getrevision()
    name = os.path.basename(rpath)
    self.dots[name] = dot
    self.__update_state()
    self.out.info('added ' + name)

  def status(self):
    self.__load_state()

    self.out.info('repos status:')
    self.out.info('')
    for name, dot in AsyncDo(self.dots, Dot.check):
      self.out.info(name + "\t" + dot.state.name)

  def update(self):
    self.__load_state()

    self.out.info('pulling from remotes...')
    self.out.info('')
    for name, dot in AsyncDo(self.dots, Dot.update):
      self.out.info(name + "\t" + dot.state.name)

    self.__update_state()

  def upload(self):
    self._info('pushing to remotes...')
    job = lambda name,repo,url: Git(repo).push()
    for _,cmd,logfile in self._in_repos(job):
      if cmd.skipped():
        self._print_result('SKIPPED (seems does not cloned yet)')
      else:
        if cmd.exitcode == 0:
          self._print_result('ok')
        else:
          self._print_result('ERROR!',logfile)

  def __parse_args(self, args):
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(title='commands', dest='command', metavar=None)

    sp.add_parser('status', help='list known rc repos and their status')

    p_add = sp.add_parser('add', help='add rc repo')
    p_add.add_argument('path', type=str, help='rc repo path')
    p_add.add_argument('url', type=str, help='rc repo (git) url', nargs='?', default=None)

    sp.add_parser('update', help='update dot files repos')

    #parser_push = sp.add_parser('p',
    #    help='upload changes')
    #parser_push.set_defaults(action='upload')

    #parser_push = sp.add_parser('self-update',
    #    help='update self')
    #parser_push.set_defaults(action='self-update')

    return ap.parse_args(args), ap.print_usage

  def self_update(self):
    self_url = 'https://raw.githubusercontent.com/kucaahbe/dot.py/master/dot.py'
    self._info('downloading self from "{}"...'.format(self_url))
    self_code = urlopen(self_url).read()
    self_path = sys.argv[0]
    with open(self_path,'w') as f:
      f.write(self_code)
    self._info('successfully updated')

  def __load_state(self):
    state = {}
    if os.access(self.STATE_FILE, os.R_OK):
      with open(self.STATE_FILE, 'r') as f:
        state = json.loads(f.read())

    for repo, details in state.items():
      self.dots[repo] = Dot(
        url = details['url'],
        path = details['path'],
        revision = details['revision'],
        updated_on = details['updated_on'] and datetime.strptime(details['updated_on'], '%Y-%m-%dT%H:%M:%S.%f')
      )

  def __update_state(self):
    state = {}
    for name, dot in self.dots.items():
      state[name] = {
        'url': dot.url.decode('utf-8'),
        'path': dot.path,
        'revision': dot.revision and dot.revision.decode('utf-8'),
        'updated_on': dot.updated_on and dot.updated_on.isoformat()
      }
    data = json.dumps(state, indent=2, separators=(',', ': '), sort_keys=True)
    with open(self.STATE_FILE, 'w') as f: f.write(data)

  def _make_cloned(self,name):
    self._assign_metadata(name,'cloned',datetime.utcnow().isoformat())

DotState = Enum('DotState', 'UNKNOWN EXISTS BLANK')
class Dot:
  @staticmethod
  def isrepo(rpath):
    return os.path.isdir(os.path.join(rpath, '.git'))

  @staticmethod
  def repourl(rpath):
    cmd = Cmd(Git.url(rpath)).invoke()
    return cmd.stdout.strip()

  def __init__(self, path, url, revision=None, updated_on=None):
    self.state = DotState.UNKNOWN
    self.url = url
    self.path = path
    self.revision = revision
    self.updated_on = updated_on
    self.vcs = Git(self.path)

  def check(self):
    self.state = DotState.BLANK
    if self.vcs.exists() and os.system(' '.join(self.vcs.status())) == 0: # FIXME hardocde
      self.state = DotState.EXISTS

  def update(self):
    self.check()
    success = None
    if self.state == DotState.BLANK:
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

  def __action(self, command):
    cmd = Cmd(command).invoke()
    if not cmd.success:
      self.last_error = cmd.stderr
    self.updated_on = datetime.utcnow()
    return cmd.success, cmd.stdout

class Cmd:
  def __init__(self, cmd):
    self.cmd = cmd
    self.stdout   = None
    self.stderr   = None
    self.exitcode = None

  def invoke(self):
    process = Popen(
      self.cmd,
      stdout=PIPE,
      stderr=PIPE
    )
    self.stdout, self.stderr = process.communicate()
    self.exitcode = process.returncode
    return self

  def success(self): return self.exitcode == 0

class AsyncDo:
  def __init__(self, items, func):
    self.items = items
    self.func = func
    self.threads = []

  def __iter__(self):
    self.__start()
    self.i = iter(self.items)

    return self

  def __next__(self):
    n = next(self.i)
    return n, self.items[n]
  next = __next__

  def __start(self):
    if self.threads: return
    for name in self.items:
      p_conn, c_conn = Pipe()
      t = Process(target=self.__func, args=(c_conn, self.items[name],))
      self.threads.append((t, p_conn, name))
      t.start()
    for thread in self.threads: thread[0].join()
    for thread in self.threads:
        name = thread[2]
        conn = thread[1]
        self.items[name] = conn.recv()

  def __func(self, conn, data):
      self.func(data)
      conn.send(data)
      conn.close()

class Git:
  __CMD = ['git']

  @staticmethod
  def url(rpath): return Git.__CMD + ['--git-dir={}/.git'.format(rpath), 'config', 'remote.origin.url']

  def __init__(self, path): self.path = path

  def clone(self, url): return self.__CMD + ['clone', '--quiet', '--recursive', '--', url, self.path]

  def exists(self): return os.access(os.path.join(self.path, '.git'), os.R_OK)

  def pull(self): return self.__base() + ['pull']

  def push(self): return self.__base() + ['push']

  def status(self): return self.__base() + ['status', '--porcelain']

  def revision(self): return self.__base() + ['rev-parse', 'HEAD']

  def __base(self):
    return self.__CMD + self.__path_settings()

  def __path_settings(self):
    tmpl = ['--git-dir={}/.git', '--work-tree={}']
    return [t.format(self.path) for t in tmpl]

class Log:
  def info(self, text): sys.stdout.write(". "+text+"\n")
  def error(self, text): sys.stderr.write(". "+text+"\n")

if __name__ == '__main__': Dotfiles().manage(sys.argv[1:])
