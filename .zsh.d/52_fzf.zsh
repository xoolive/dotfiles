[ -f ~/.fzf.zsh ] && source ~/.fzf.zsh

TRAPWINCH() {
  zle && { zle reset-prompt; zle -R }
}

# Completions
fpath=(~/.zsh.d/ $fpath)
