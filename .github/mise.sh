
mise use -g node@latest
mise use -g pnpm@latest
mise use -g prettier@latest

mise upgrade --bump

pnpm add -g typescript typescript-language-server
pnpm add -g @vue/language-server

pnpm add -g @earendil-works/pi-coding-agent  # pi update
pnpm add -g hunkdiff

# npm install -g vscode-langservers-extracted
