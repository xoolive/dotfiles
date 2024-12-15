# Install Rustup
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh

rustup upgrade
rustup component add rust-analyzer

cargo install cargo-release

# Install tools (Linux)
# Most of these tools have installers for already compiled versions

# Useful for .zprofile
#
# atuin: check https://atuin.sh
# eza: check https://github.com/eza-community/eza
# zoxide: https://github.com/ajeetdsouza/zoxide

# Check the github for detailed instructions

cargo install atuin  # (replace history)
cargo install bat
cargo install broot
cargo install dua  # (replace ncdu)
cargo install eza  # (replace ls)
cargo install jless
cargo install just  # (replace make)
cargo install procs  # (replace ps)
# cargo install tealdeer  # outdated release, clone and compile
cargo install xh  # http requests
cargo install zoxide  # (replace cd)
