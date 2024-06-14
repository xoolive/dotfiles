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
