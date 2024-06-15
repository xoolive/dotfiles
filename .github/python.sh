# install rye, uv from https://astral.sh
#
# rye fetch cpython@3.12
# PATH=~/.rye/py/cpython@3.12.2/bin/:$PATH poetry env use 3.12

# install pixi from https://github.com/prefix-dev/pixi
#


pipx install maturin
pipx install poetry
pipx install "glances[all]"  # https://github.com/nicolargo/glances
