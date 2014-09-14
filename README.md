dot - personal command line config manager for developer
========================================================

sample manifest:

    [all]
    git=git://github.com/kucaahbe/gitrc.git
    zsh=git://github.com/kucaahbe/zshrc.git
    vim=git://github.com/kucaahbe/vimrc.git


Design goals
============

* could be installed via `wget` or similar
* no assumptions about user preferences, keep your dotfiles as you want them
* get out of you way, and let you do your job

Install
=======

```sh
wget https://raw.githubusercontent.com/kucaahbe/dot.py/master/dot.py -O ~/bin/dot && chmod +x ~/bin/dot
```

Usage
=====

dot i git://path.com/to/manifest.git - download and put manifest file into ~/.dotrc, create own data files, clones repositories, add self sync command into user's crontab,
installs everything and backup already existing files

dot u - clone/update all configs(also run install script for every config if clone, and write itself into a crontab in order to update configs)

dot s - see git status for each config

dot p - push updates if any(if fail to push to some repo tries to fix git url and repush again)
