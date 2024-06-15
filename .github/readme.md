The home command is defined in `.zsh.d/30_alias.zsh`

```zsh
alias home='git --git-dir=$HOME/.dotfiles/ --work-tree=$HOME'
```

Then we get the proper .gitignore

```zsh
home config core.excludesFile '.gitignore_dotfiles'
```
