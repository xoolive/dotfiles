# Install homebrew
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
eval "$(/opt/homebrew/bin/brew shellenv)"

# Install GNU core utilities (those that come with OS X are outdated)
brew install coreutils
echo "Don’t forget to add $(brew --prefix coreutils)/libexec/gnubin to \$PATH."

# Cask installations

brew install --cask calibre
brew install --cask cyberduck
brew install --cask drawio
brew install --cask font-fira-mono-for-powerline
brew install --cask font-iosevka
brew install --cask font-menlo-for-powerline
brew install --cask font-monaspace
brew install --cask font-monaspace-nerd-font  # https://github.com/ryanoasis/nerd-fonts
brew install --cask font-caskaydia-cove-nerd-font
brew install --cask ghostty
brew install --cask gimp
brew install --cask macvim
brew install --cask mongodb-compass
brew install --cask ollama
brew install --cask transmission
brew install --cask vlc
brew install --cask wezterm
brew install --cask zoom
brew install --cask zotero

# Standard installations

brew install autossh
brew install bat  # https://github.com/sharkdp/bat (replace cat)
brew install broot  # https://github.com/Canop/broot (replace tree)
brew install chruby ruby-install xz
brew install cmake
brew install ctags
brew install dua-cli  # https://github.com/Byron/dua-cli (replace ncdu)
brew install duckdb
brew install eza  # https://github.com/eza-community/eza (replace ls)
brew install fdupes
brew install ffmpeg
brew install fzf  # https://github.com/sharkdp/fd (replace find)
brew install gh
brew install git-delta  # https://github.com/dandavison/delta  (replace diff)
brew install git-lfs
brew install go
brew install helix
brew install htop  # (replace top)
brew install imagemagick
brew install jet1090
brew install jless
brew install jordanbaird-ice  # https://github.com/jordanbaird/Ice
brew install jnv  # jq-based interactive tool
brew install jq
brew install juliaup
brew install just
brew install libarchive
brew install links
brew install ltex-ls
brew install marksman  # lsp for Markdown
brew install neofetch
brew install nushell
brew install nvim
brew install pandoc
brew install pdftk-java
brew install pkg-config
brew install podman
brew install podman-desktop
brew install protobuf
brew install quarto
brew install socat
brew install sox
brew install taplo  # linter for toml
brew install telnet
brew install tesseract
# brew install tealdeer  # outdated release, clone and compile
brew install tmux
brew install the_silver_searcher  # ag
brew install transmission-cli
brew install tree
brew install uv
brew install watchexec
brew install websocat
brew install wget
brew install xh  # http requests
brew install yazi ripgrep poppler  # with useful dependencies
brew install yt-dlp
brew install zig
brew install zls
brew install zoxide
brew install 7zip

brew install xoolive/homebrew/jet1090
brew install xoolive/homebrew/decode1090
brew install axodotdev/tap/cargo-dist
brew install f1bonacc1/tap/process-compose
