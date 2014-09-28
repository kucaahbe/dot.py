#!/usr/bin/env python
# -*- coding: UTF-8 -*-

import os
import sys
import argparse
import urllib2
import ConfigParser
import threading

class AsyncExec(threading.Thread):
  def __init__(self,cmd,callback=None,args=None):
    threading.Thread.__init__(self)
    self.cmd      = cmd
    self.callback = callback
    self.args     = args
  def run(self):
    os.system(self.cmd)
    if self.callback: self.callback(*self.args)

class Async():
  def __init__(self):
    self.cmds=[]
  def add(self,cmd,callback=None,*args):
    self.cmds.append((cmd,callback,args))
  def run(self):
    threads = []
    for cmd in self.cmds:
      t = AsyncExec(*cmd)
      threads.append(t)
      t.start()
    for t in threads: t.join()

class Git():

  def __init__(self,path=None):
    self.repo_path = path

  def clone(self,url,repo):
    return 'git clone --recursive -- {} {}'.format(url,repo)

  def pull(self):
    return self._git() + 'pull'

  def push(self):
    return self._git() + 'push'

  def status(self):
    return self._git() + 'status --porcelain'

  def _git(self):
    return 'git --git-dir={0}/.git --work-tree={0} '.format(self.repo_path)

class Dot:

  CONFIG_PATH   = os.path.join(os.getenv('HOME'),'.dot')
  MANIFEST_PATH = os.path.join(CONFIG_PATH,'manifest.ini')

  def __init__(self):
    self.config_path = self.__class__.CONFIG_PATH
    self.manifest    = self.__class__.MANIFEST_PATH
    self.dots = []

  def parse_args(self,args):
    parser = argparse.ArgumentParser()

    subparsers = parser.add_subparsers()

    parser_install = subparsers.add_parser('i',
        help="install stuff")
    parser_install.set_defaults(action='install')
    parser_install.add_argument('manifest', type=str,
        help='path or url of manifest file')

    parser_status = subparsers.add_parser('s',
        help="get git status")
    parser_status.set_defaults(action='status')

    parser_pull = subparsers.add_parser('u',
        help="update configs")
    parser_pull.set_defaults(action='update')

    parser_push = subparsers.add_parser('p',
        help="upload changes")
    parser_push.set_defaults(action='upload')

    parser_cd = subparsers.add_parser('cd',
        help="cd into config directory")
    parser_cd.set_defaults(action='chdir')
    parser_cd.add_argument('dot', type=str)

    self.config = parser.parse_args(args)

  def install(self):
    manifest_url = self.config.manifest

    os.mkdir(self.config_path)

    if os.access(self.manifest,os.R_OK):
      self.log_error("sorry, manifest file already exists")
      exit(1)
    else:
      self.log_info('downloading manifest from "{}"...'.format(manifest_url))
      manifest = urllib2.urlopen(manifest_url).read()
      with open(self.manifest,'w') as f:
        f.write(manifest)

    self._parse_manifest()

    # clone stuff
    self.log_info("started cloning...")
    def job(name,repo,url,async):
      async.add(Git().clone(url,repo),
          lambda name: self.log_info('cloned {}'.format(name)),
          name)
    self._in_repos(job)

  def status(self):
    self._parse_manifest()
    self.log_info('repos status:')
    def job(name,repo,url,async):
      async.add(Git(repo).status())
    self._in_repos(job)

  def update(self):
    self._parse_manifest()
    self.log_info('pulling from remotes...')
    def job(name,repo,url,async):
      async.add(Git(repo).pull())
    self._in_repos(job)

  def upload(self):
    self._parse_manifest()
    self.log_info('pushing to remotes...')
    def job(name,repo,url,async):
      async.add(Git(repo).push())
    self._in_repos(job)

  def chdir(self):
    self._parse_manifest()
    for dot in self.dots:
      name, url = dot
      repo = os.path.join(self.config_path,name)
      if self.config.dot == name:
        #os.chdir(repo)
        print repo

  def do(self):
    if self.config.action == 'install':
      self.install()
    elif self.config.action == 'status':
      self.status()
    elif self.config.action == 'update':
      self.update()
    elif self.config.action == 'upload':
      self.upload()
    elif self.config.action == 'chdir':
      self.chdir()

  def log_info(self,text):
    sys.stdout.write(". "+text+"\n")

  def log_error(self,text):
    sys.stderr.write(". "+text+"\n")

  def _parse_manifest(self):
    manifest_data = ConfigParser.ConfigParser()
    manifest_data.read(self.manifest)
    self.dots = manifest_data.items('all')

  def _in_repos(self,job):
    async = Async()
    for dot in self.dots:
      name, url = dot
      repo = os.path.join(self.config_path,name)
      job(name,repo,url,async)
    async.run()

def main():
  dot = Dot()
  dot.parse_args(sys.argv[1:])
  dot.do()

if __name__ == "__main__":
  main()
