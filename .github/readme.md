## Version controlled .dotfiles

I synchronize this folder across several MacOS and Linux computers, even if there are different approaches to deal with installations:

- the [Homebrew](https://brew.sh) approach for MacOS;
- a more _compile what you need_ approach with Linux (mostly `cargo install` based).

Before starting:

- My principal shell is **zsh**, parametrized with [oh-my-zsh](https://ohmyz.sh/):
  - install the [Spaceship Prompt](https://github.com/spaceship-prompt/spaceship-prompt);
  - install [zsh-completions](https://github.com/zsh-users/zsh-completions);
  - install [zsh-syntax-highlighting](https://github.com/zsh-users/zsh-syntax-highlighting).

  ```zsh
  git clone https://github.com/zsh-users/zsh-completions ${ZSH_CUSTOM}/plugins/zsh-completions
  git clone https://github.com/zsh-users/zsh-syntax-highlighting ${ZSH_CUSTOM}/plugins/zsh-syntax-highlighting
  git clone https://github.com/spaceship-prompt/spaceship-prompt.git "$ZSH_CUSTOM/themes/spaceship-prompt" --depth=1
  ln -s "$ZSH_CUSTOM/themes/spaceship-prompt/spaceship.zsh-theme" "$ZSH_CUSTOM/themes/spaceship.zsh-theme"
  ```

- My principal terminal editor is **vim**, equipped with [Vundle](https://github.com/VundleVim/Vundle.vim) for plugin management:

  ```zsh
  git clone https://github.com/VundleVim/Vundle.vim.git ~/.vim/bundle/vundle
  vim +qPluginInstall +qall
  ```
  
A description of how to install environments for several programming languages are available in the `.github` folder:

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

Just clone this repository in the `~/.dotfiles/` folder, in a detached work tree approach.

The `home` command is defined in `.zsh.d/30_alias.zsh` and used as a replacement for `git`.

```zsh
alias home='git --git-dir=$HOME/.dotfiles/ --work-tree=$HOME'
```

It is preferable to have a `*` in the `.gitignore` for this repository, but it may conflict with the global `~/.gitignore`, hence the following setting:

```zsh
home config core.excludesFile '.gitignore_dotfiles'
```
