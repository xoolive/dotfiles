# Install homebrew
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
eval "$(/opt/homebrew/bin/brew shellenv)"

# Install GNU core utilities (those that come with OS X are outdated)
brew install coreutils
echo "Don’t forget to add $(brew --prefix coreutils)/libexec/gnubin to \$PATH."

# Cask installations

brew install --cask calibre
brew install --cask font-fira-mono-for-powerline
brew install --cask font-iosevka
brew install --cask font-menlo-for-powerline
brew install --cask font-monaspace
brew install --cask macvim
brew install --cask mongodb-compass
brew install --cask ollama
brew install --cask transmission
brew install --cask wezterm
brew install --cask zoom
brew install --cask zotero

# Standard installations

brew install autossh
brew install bat  # https://github.com/sharkdp/bat (replace cat)
brew install broot  # https://github.com/Canop/broot (replace tree)
brew install chruby ruby-install xz
brew install dua-cli  # https://github.com/Byron/dua-cli (replace ncdu)
brew install duckdb
brew install eza  # https://github.com/eza-community/eza (replace ls)
brew install fdupes
brew install fzf  # https://github.com/sharkdp/fd (replace find)
brew install gh
brew install git-delta  # https://github.com/dandavison/delta  (replace diff)
brew install git-lfs
brew install go
brew install htop  # (replace top)
brew install jet1090
brew install jless
brew install jq
brew install just
brew install libarchive
brew install links
brew install neofetch
brew install nushell
brew install pandoc
brew install pdftk-java
brew install pipx
brew install pkg-config
brew install podman
brew install socat
brew install tesseract
brew install tealdeer  # tldr
brew install tmux
brew install the_silver_searcher  # ag: https://github.com/ggreer/the_silver_searcher
brew install transmission-cli
brew install tree
brew install uv
brew install wget
brew install xh  # http requests
brew install xoolive/homebrew/jet1090
brew install yt-dlp
brew install zoxide
