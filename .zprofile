export PATH=$HOME/.local/bin:$PATH

# -- homebrew --
if [[ $(uname -s) = "Darwin" ]]; then
    eval "$(/opt/homebrew/bin/brew shellenv)"
    export PATH="$(brew --prefix)/opt/coreutils/libexec/gnubin:$PATH"
fi

# -- cargo --
. "$HOME/.cargo/env"

# -- opam (Ocaml) --
eval "$(opam env --switch=default)"

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
