#!/usr/bin/env python
# -*- coding: UTF-8 -*-

import os
import sys
import subprocess
import argparse
import urllib2
import ConfigParser

class AsyncExec():
  def __init__(self,cmd):
    self.cmd      = cmd
    self._process = None
    self.stdout   = None
    self.stderr   = None
    self.returncode = None
  def start(self):
    self._process = subprocess.Popen(self.cmd,
        stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    return self
  def ok(self):
    return self.returncode == 0
  def join(self):
    self.stdout,self.stderr = self._process.communicate()
    self.returncode = self._process.returncode

class Async():
  def __init__(self):
    self.cmds={}
  def add(self,cmd,index):
    self.cmds[index]=cmd
  def run(self):
    subprocesses = {}
    for index,cmd in self.cmds.iteritems():
      subprocesses[index]=AsyncExec(cmd).start()
    for t in subprocesses.itervalues(): t.join()
    for index,executor in subprocesses.iteritems():
      yield index,executor

class Git():

  def __init__(self,path=None):
    self.repo_path = path

  def clone(self,url,repo):
    return ['git', 'clone', '--recursive', '--', url, repo]

  def pull(self):
    return self._git() + ['pull']

  def push(self):
    return self._git() + ['push']

  def status(self):
    return self._git() + ['status', '--porcelain']

  def _git(self):
    return ['git'] + self._git_path_opts()

  def _git_path_opts(self):
    tmpl = ['--git-dir={}/.git', '--work-tree={}']
    return map(lambda s: s.format(self.repo_path),tmpl)

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
      async.add(Git().clone(url,repo),name)
    for result in self._in_repos(job):
      print 'ok'

  def status(self):
    self._parse_manifest()
    self.log_info('repos status:')
    def job(name,repo,url,async):
      async.add(Git(repo).status(),name)
    for result in self._in_repos(job):
      if len(result)>0:
        print "DIRTY"
      else:
        print "clean"

  def update(self):
    self._parse_manifest()
    self.log_info('pulling from remotes...')
    def job(name,repo,url,async):
      async.add(Git(repo).pull(),name)
    for result in self._in_repos(job):
      print 'ok'

  def upload(self):
    self._parse_manifest()
    self.log_info('pushing to remotes...')
    def job(name,repo,url,async):
      async.add(Git(repo).push())
    for result in self._in_repos(job):
      print 'ok'

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

    results = async.run()
    for data in results:
      repo,executor = data

      logfile = os.path.join(self.config_path,repo+'.log')
      with open(logfile,'w') as log:
        log.write("command: {}\n".format(' '.join(str(i) for i in executor.cmd)))
        log.write("return code: {}\n".format(executor.returncode))
        log.write(executor.stderr+"\n")

      sys.stdout.write(repo+': ')
      if executor.ok():
        yield executor.stdout
      else:
        sys.stdout.write("ERROR! check out logfile: {}".format(logfile)+"\n")

def main():
  dot = Dot()
  dot.parse_args(sys.argv[1:])
  dot.do()

if __name__ == "__main__":
  main()
