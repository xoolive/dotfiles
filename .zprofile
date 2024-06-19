export PATH=$HOME/.local/bin:$PATH

# -- homebrew --
if [[ $(uname -s) = "Darwin" ]]; then
    eval "$(/opt/homebrew/bin/brew shellenv)"
    export PATH="$(brew --prefix)/opt/coreutils/libexec/gnubin:$PATH"
fi

# -- cargo --
if [[ -d $HOME/.cargo ]]; then
    . "$HOME/.cargo/env"
fi

# -- opam (Ocaml) --
if command -v opam >/dev/null 2>&1; then
    eval "$(opam env --switch=default)"
fi


# atuin
# (among the possibilities to install atuin...)
if [[ -d $HOME/.atuin/bin ]]; then
    export PATH="$PATH:$HOME/.atuin/bin/"
fi

# -- rye (Python) --
# . "$HOME/.rye/env"

# -- volta (Js) --
export VOLTA_HOME="$HOME/.volta"
export PATH="$VOLTA_HOME/bin:$PATH"

# -- Go --
export GOPATH="$HOME/.gopath"
export PATH="$GOPATH/bin:$PATH"

# -- Ruby --
if [[ $(uname -s) = "Darwin" ]]; then
    source "$(brew --prefix)/opt/chruby/share/chruby/chruby.sh"
    source "$(brew --prefix)/opt/chruby/share/chruby/auto.sh"
    chruby ruby-3.1.3
fi
