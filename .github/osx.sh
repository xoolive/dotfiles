sh <(curl -L https://nixos.org/nix/install)

# Screenshot folder
SCREENSHOT_FOLDER="${HOME}/Pictures/My Screenshots"
mkdir -p $SCREENSHOT_FOLDER
defaults write com.apple.screencapture location -string "${SCREENSHOTS_FOLDER}"

# Finder: show all filename extensions
defaults write NSGlobalDomain AppleShowAllExtensions -bool true

# No telemetry, thank you
defaults write com.microsoft.Word SendAllTelemetryEnabled -bool FALSE
defaults write com.microsoft.Excel SendAllTelemetryEnabled -bool FALSE
defaults write com.microsoft.Powerpoint SendAllTelemetryEnabled -bool FALSE
