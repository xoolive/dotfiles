export PYTHONSTARTUP=$HOME/.pythonstartup

export EDITOR=vi

# Larger history (allow 32³ entries; default is 500)
export HISTSIZE=32768
export HISTFILESIZE=$HISTSIZE
export HISTFILE=$HOME/.history
export HISTCONTROL=ignoredups

# Make some commands not show up in history
export HISTIGNORE="ls:cd:cd -:pwd:[bf]g:clear:exit:date:* --help"

# replacement for cd
eval "$(zoxide init zsh)"

# nice Ctrl-R
# configuration in ~/.config/atuin/config.toml
eval "$(atuin init zsh --disable-up-arrow)"

# -- pixi (replacement for conda) --
export PATH="$HOME/.pixi/bin:$PATH"
eval "$(pixi completion --shell zsh)"

eval "$(just --completions zsh)"

# -- jet1090 (completion) --
eval "$(jet1090 --completion zsh)"
