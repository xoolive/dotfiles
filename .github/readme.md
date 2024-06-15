## Version controlled .dotfiles

I synchronize this folder across several MacOS and Linux computers, even if there are different approaches to deal with installations:

- the [Homebrew](https://brew.sh) approach for MacOS;
- a more _compile what you need_ approach with Linux (mostly `cargo install` based).

My principal shell is zsh, parametrized with [oh-my-zsh](https://ohmyz.sh/) and the [Spaceship Prompt](https://github.com/spaceship-prompt/spaceship-prompt)

A description of how to install environments for several programming languages are available in the `.github` folder:

- `brew.sh` for the installed Homebrew packages (MacOS)
- `go.sh` for the Golang environment (installed through brew)
- `javascript.sh` for the Volta environment
- `latex.sh` for a lightweight LaTeX installation (MacOS)
- `python.sh` for Python and pipx tools
- `rust.sh` for the Rust tool suite (Linux)

## Miscellaneous

- MacOS: use TouchID for sudo

  ```sh
  # in /etc/pam.d/sudo, after pam_smartcard.so
  auth       sufficient     pam_tid.so
  ```

- Keyboard layout: I use a specific French variant of the Dvorak keyboard layout (no, not bépo), and like to use Caps Lock as an extra Ctrl key. All described in another repo [xoolive/dvorak-fr](https://github.com/xoolive/dvorak-fr).


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
