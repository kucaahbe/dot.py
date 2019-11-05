# dotfiles - manage dotfiles

### Install

```sh
curl https://raw.githubusercontent.com/kucaahbe/dot.py/master/dotfiles -o /usr/local/bin/dotfiles && chmod +x /usr/local/bin/dotfiles
# or
wget https://raw.githubusercontent.com/kucaahbe/dot.py/master/dotfiles -O /usr/local/bin/dotfiles && chmod +x /usr/local/bin/dotfiles
```

### Use

1. add dotfiles repository (there maybe few, add each one as needed, existing repositories also work):

```sh
dotfiles add ~/mydotfiles/dotfiles1 git://githosting.io/username/dotfiles1
```

2. check what's added:

```sh
dotfiles status
```

3. download updates:

```sh
dotfiles update
```

4. symlink/copy needed files, if target dotfiles repository(ies) contains [dotfiles.ini](#dotfilesini)
```sh
dotfiles install {specific repo name}
```

##### dotfiles.ini:

```ini
# dotfiles.ini
[links]
bashrc = ~/.bashrc
ls.bashrc = ~/.bashrc.d/ls.bashrc
```
