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

  def __init__(self):
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

    os.mkdir(CONFIG_PATH)
    os.mkdir(LOG_PATH)

    if os.access(MANIFEST_PATH,os.R_OK):
      self.log_error("sorry, manifest file already exists")
      exit(1)
    else:
      self.log_info('downloading manifest from "{}"...'.format(manifest_url))
      manifest = urllib2.urlopen(manifest_url).read()
      with open(MANIFEST_PATH,'w') as f:
        f.write(manifest)

    self.log_info("started cloning...")
    job = lambda repo,url: Git().clone(url,repo)
    for output in self._in_repos(job):
      print 'ok'

  def status(self):
    self.log_info('repos status:')
    job = lambda repo,url: Git(repo).status()
    for output in self._in_repos(job):
      if len(output)>0:
        print "DIRTY"
      else:
        print "clean"

  def update(self):
    self.log_info('pulling from remotes...')
    job = lambda repo,url: Git(repo).pull()
    for output in self._in_repos(job):
      print 'ok'

  def upload(self):
    self.log_info('pushing to remotes...')
    job = lambda repo,url: Git(repo).push()
    for output in self._in_repos(job):
      print 'ok'

  def chdir(self):
    for dot in self.dots:
      name, url = dot
      repo = os.path.join(CONFIG_PATH,name)
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

  def _dump_metadata(self):
    with open(METADATA_PATH,'w') as m:
      m.write(json.dumps(self.metadata,sort_keys=True,indent=2))

  def _in_repos(self,job):
    self._parse_manifest()
    self._load_metadata()

    async = Async()
    for dot in self.dots:
      name, url = dot
      repo = os.path.join(REPOS_PATH,name)
      async.add(job(repo,url),name)

    for repo,executor in async.run():
      logfile = os.path.join(LOG_PATH,repo+'.log')
      with open(logfile,'w') as log:
        cmd = ' '.join(str(i) for i in executor.cmd)
        msg = "command: {}\nreturn code: {}\n{}".format(cmd,executor.returncode,executor.stderr)
        log.write(msg)

      sys.stdout.write(repo+': ')
      if executor.ok():
        if not 'cloned' in self.metadata[repo]:
          self.metadata[repo]['cloned']=datetime.utcnow().isoformat()
        yield executor.stdout
      else:
        sys.stdout.write("ERROR! check out logfile: {}".format(logfile)+"\n")

    self._dump_metadata()

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
  dot = Dot()
  dot.parse_args(sys.argv[1:])
  dot.do()
