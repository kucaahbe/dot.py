#!/usr/bin/env python
# -*- coding: UTF-8 -*-
import os
import sys
import subprocess
import argparse
import urllib2
import ConfigParser
import json
from datetime import datetime

CONFIG_PATH   = os.path.join(os.getenv('HOME'),'.dot')
REPOS_PATH    = os.path.join(CONFIG_PATH,'data')
METADATA_PATH = os.path.join(CONFIG_PATH,'data.json')
MANIFEST_PATH = os.path.join(CONFIG_PATH,'manifest.ini')
LOG_PATH      = os.path.join(CONFIG_PATH,'log')

class Dot:

  def __init__(self,args):
    self.dots = []
    self._parse_args(args)

  def _parse_args(self,args):
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

    parsed = parser.parse_args(args)

    self.action   = parsed.action
    self.manifest = lambda: parsed.manifest

  def do(self):
    if self.action   == 'install':
      self.install(self.manifest())
    elif self.action == 'status':
      self.status()
    elif self.action == 'update':
      self.update()
    elif self.action == 'upload':
      self.upload()
    elif self.action == 'chdir':
      self.chdir()

  def install(self,manifest_url):
    os.mkdir(CONFIG_PATH)
    os.mkdir(LOG_PATH)

    if os.access(MANIFEST_PATH,os.R_OK):
      self._error("sorry, manifest file already exists")
      exit(1)
    else:
      self._info('downloading manifest from "{}"...'.format(manifest_url))
      manifest = urllib2.urlopen(manifest_url).read()
      with open(MANIFEST_PATH,'w') as f:
        f.write(manifest)

    self.clone()

  def clone(self):
    self._info("started cloning...")
    def job(name,repo,url):
      if self._has_metadata(name,'cloned'):
        return False
      else:
        return Git().clone(url,repo)
    for name,cmd,logfile in self._in_repos(job):
      if cmd.skipped():
        self._print_result('already cloned')
      else:
        if cmd.exitcode == 0:
          self._assign_metadata(name,'cloned',datetime.utcnow().isoformat())
          self._print_result('ok')
        else:
          self._print_result('ERROR!',logfile)

  def status(self):
    self._info('repos status:')
    job = lambda name,repo,url: Git(repo).status()
    for _,cmd,_ in self._in_repos(job):
      if len(cmd.stdout) > 0:
        self._print_result('DIRTY')
      else:
        self._print_result("clean")

  def update(self):
    self._info('pulling from remotes...')
    job = lambda name,repo,url: Git(repo).pull()
    for _,cmd,logfile in self._in_repos(job):
      if cmd.exitcode == 0:
        self._print_result('ok')
      else:
        self._print_result('ERROR!',logfile)

  def upload(self):
    self._info('pushing to remotes...')
    job = lambda name,repo,url: Git(repo).push()
    for _,cmd,logfile in self._in_repos(job):
      if cmd.exitcode == 0:
        self._print_result('ok')
      else:
        self._print_result('ERROR!',logfile)

  def chdir(self):
    for dot in self.dots:
      name, url = dot
      repo = os.path.join(CONFIG_PATH,name)
      if self.config.dot == name:
        #os.chdir(repo)
        print repo

  def _info(self,text):
    sys.stdout.write(". "+text+"\n")

  def _error(self,text):
    sys.stderr.write(". "+text+"\n")

  def _parse_manifest(self):
    manifest_data = ConfigParser.ConfigParser()
    manifest_data.read(MANIFEST_PATH)
    self.dots = manifest_data.items('all')

  def _load_metadata(self):
    if os.access(METADATA_PATH,os.R_OK):
      with open(METADATA_PATH,'r') as m:
        self.metadata = json.loads(m.read())
    else:
        self.metadata = {}

    for repo,_ in self.dots:
      if not repo in self.metadata: self.metadata[repo]={}

  def _assign_metadata(self,repo,key,value):
    self.metadata[repo][key]=value

  def _has_metadata(self,repo,key):
    return key in self.metadata[repo]

  def _dump_metadata(self):
    with open(METADATA_PATH,'w') as m:
      m.write(json.dumps(self.metadata,sort_keys=True,indent=2))

  def _in_repos(self,job):
    self._parse_manifest()
    self._load_metadata()

    async = Async()
    for dot in self.dots:
      name, url = dot
      path = os.path.join(REPOS_PATH,name)
      async.add(name,job(name,path,url))

    for name,executor in async.run():
      logfile = os.path.join(LOG_PATH,name+'.log')
      with open(logfile,'w') as log:
        cmd = ' '.join(str(i) for i in executor.cmd)
        msg = "command: {}\nreturn code: {}\n{}".format(cmd,executor.exitcode,executor.stderr)
        log.write(msg)

      sys.stdout.write(name+': ')
      yield name,executor,logfile

    self._dump_metadata()

  def _print_result(self,text,logfile=None):
    if logfile:
      text = text + ' check out logfile: {}'.format(logfile)
    sys.stdout.write(text+"\n")

class Executor():
  def __init__(self,cmd):
    self.cmd      = cmd
    self._process = None
    self.stdout   = None
    self.stderr   = None
    self.exitcode = None
  def start(self):
    if self.cmd:
      self._process = subprocess.Popen(self.cmd,
          stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    return self
  def skipped(self):
    return self.cmd == False
  def join(self):
    if self._process:
      self.stdout,self.stderr = self._process.communicate()
      self.exitcode = self._process.returncode

class Async():
  def __init__(self):
    self.cmds={}
  def add(self,name,cmd):
    self.cmds[name]=cmd
  def run(self):
    subprocesses = {}
    for name,cmd in self.cmds.iteritems():
      subprocesses[name]=Executor(cmd).start()
    for t in subprocesses.itervalues(): t.join()
    for name,executor in subprocesses.iteritems():
      yield name,executor

class Git():

  def __init__(self,path=None):
    self.repo_path = path

  def clone(self,url,repo):
    return ['git', 'clone', '-q', '--recursive', '--', url, repo]

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

if __name__ == "__main__":
  Dot(sys.argv[1:]).do()
