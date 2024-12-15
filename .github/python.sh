# install uv from https://astral.sh
# install pixi from https://github.com/prefix-dev/pixi

uv tool install cartes
uv tool install fr24
uv tool install maturin
uv tool install poetry
uv tool install posting
uv tool install "glances[all]"  # https://github.com/nicolargo/glances

uv tool install 'python-lsp-server[all]' --with pylsp-mypy
uv tool install pyright
