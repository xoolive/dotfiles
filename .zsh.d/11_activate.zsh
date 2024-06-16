# find folders where virtualenvs are located and source them

POETRY_PATH=$(poetry config virtualenvs.path || "")
PIPX_PATH=$(pipx list | grep venvs | sed "s/ /\n/g" | tail -n 1 || "")

function activate {
    if [[ -z $1 ]]; then
        echo "Usage: activate [environment]"
        return
    fi
    if [[ -d $PIPX_PATH/$1 ]]; then
        source $PIPX_PATH/$1/bin/activate
    elif [[ -d $POETRY_PATH/$1 ]]; then
        source $POETRY_PATH/$1/bin/activate
    else
        echo "$1 not found"
    fi
}

local envdirs
envdirs=($PIPX_PATH $POETRY_PATH)
compdef '_files -W envdirs' activate

deactivate () {
    unset -f pydoc > /dev/null 2>&1 || true
    if ! [ -z "${_OLD_VIRTUAL_PATH:+_}" ]
    then
        PATH="$_OLD_VIRTUAL_PATH"
        export PATH
        unset _OLD_VIRTUAL_PATH
    fi
    if ! [ -z "${_OLD_VIRTUAL_PYTHONHOME+_}" ]
    then
        PYTHONHOME="$_OLD_VIRTUAL_PYTHONHOME"
        export PYTHONHOME
        unset _OLD_VIRTUAL_PYTHONHOME
    fi
    hash -r 2> /dev/null
    if ! [ -z "${_OLD_VIRTUAL_PS1+_}" ]
    then
        PS1="$_OLD_VIRTUAL_PS1"
        export PS1
        unset _OLD_VIRTUAL_PS1
    fi
    unset VIRTUAL_ENV
    unset VIRTUAL_ENV_PROMPT
    if [ ! "${1-}" = "nondestructive" ]
    then
        unset -f deactivate
    fi
}
