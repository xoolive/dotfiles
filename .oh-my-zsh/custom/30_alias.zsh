# reset the terminal when things seem wrong
alias fix='reset; stty sane; tput rs1; clear; echo -e "\033c"'

alias psu="ps -U $USER"

if [[ $(uname -s) = "Linux" ]]; then
  alias pupdatedb="updatedb -l 0 -U $HOME --output=$HOME/.mydb.db"
  alias plocate="locate -d $HOME/.mydb.db"
fi

alias home='git --git-dir=$HOME/.dotfiles/ --work-tree=$HOME'

alias lt="ls --tree --sort type --level 2"
alias lty="ls --sort type"
