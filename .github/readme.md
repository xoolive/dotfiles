## Version controlled .dotfiles

I synchronize this folder across several MacOS and Linux computers, even if there are different approaches to deal with installations:

- the [Homebrew](https://brew.sh) approach for MacOS;
- a more _compile what you need_ approach with Linux (mostly `cargo install` based).

A description of how to install several environments are available in the `.github` folder:

- `brew.sh` for the installed Homebrew packages (MacOS)
- `go.sh` for the Golang environment (installed through brew)
- `javascript.sh` for the Volta environment
- `latex.sh` for a lightweight LaTeX installation (MacOS)
- `ocaml.sh` for the opam environment
- `python.sh` for Python and pipx tools
- `rust.sh` for the Rust tool suite (Linux)

## Miscellaneous

- Use TouchID for sudo (MacOS)

  ```sh
  # in /etc/pam.d/sudo, after pam_smartcard.so
  auth       sufficient     pam_tid.so
  ```

- Keyboard layout

  I use a specific French variant of the Dvorak keyboard layout (no, not bépo), and like to use Caps Lock as an extra Ctrl key. All the settings are described in [xoolive/dvorak-fr](https://github.com/xoolive/dvorak-fr).

  Read more about it in the [Dvorak zine](https://www.dvzine.org/)

## Setup

Just clone this repository in the `~/.dotfiles/` folder:

```zsh
git clone --bare git@github.com:xoolive/dotfiles ~/.dotfiles
```

The `home` command is defined in `.zsh.d/30_alias.zsh` and used as a replacement for `git`.

```zsh
alias home='git --git-dir=$HOME/.dotfiles/ --work-tree=$HOME'
```

It is preferable to have a `*` in the `.gitignore` for this repository, but it may conflict with the global `~/.gitignore`, hence the following setting:

```zsh
home config core.excludesFile '.gitignore_dotfiles'
```

To start with:
- run `echo '*' > ~/.gitignore_dotfiles`
- run `home status` and compare files, proceed cautiously

The settings are based for my environment with:

- **zsh** as a default shell  
  [oh-my-zsh](https://github.com/ohmyzsh/ohmyzsh) as a configuration framework

  Optional plugins: [spaceship](https://github.com/spaceship-prompt/spaceship-prompt) (prompt), [zsh-completions](https://github.com/zsh-users/zsh-completions) and [zsh-syntax-highlighting](https://github.com/zsh-users/zsh-syntax-highlighting).

- **vim** as a principal terminal editor  
  [vim-plug](https://github.com/junegunn/vim-plug) for plugin management

Useful for copy-pasting:

```zsh
git clone https://github.com/zsh-users/zsh-completions ${ZSH_CUSTOM}/plugins/zsh-completions
git clone https://github.com/zsh-users/zsh-syntax-highlighting ${ZSH_CUSTOM}/plugins/zsh-syntax-highlighting
git clone https://github.com/spaceship-prompt/spaceship-prompt.git "$ZSH_CUSTOM/themes/spaceship-prompt" --depth=1
ln -s "$ZSH_CUSTOM/themes/spaceship-prompt/spaceship.zsh-theme" "$ZSH_CUSTOM/themes/spaceship.zsh-theme"
```


