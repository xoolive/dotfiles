-- Hyprland Lua config converted from ~/.config/hypr/hyprland.conf

------------------
---- COLORS ----
------------------

local rosewater = "rgb(f5e0dc)"
local flamingo = "rgb(f2cdcd)"
local pink = "rgb(f5c2e7)"
local mauve = "rgb(cba6f7)"
local red = "rgb(f38ba8)"
local maroon = "rgb(eba0ac)"
local peach = "rgb(fab387)"
local yellow = "rgb(f9e2af)"
local green = "rgb(a6e3a1)"
local teal = "rgb(94e2d5)"
local sky = "rgb(89dceb)"
local sapphire = "rgb(74c7ec)"
local blue = "rgb(89b4fa)"
local lavender = "rgb(b4befe)"
local text = "rgb(cdd6f4)"
local subtext1 = "rgb(bac2de)"
local subtext0 = "rgb(a6adc8)"
local overlay2 = "rgb(9399b2)"
local overlay1 = "rgb(7f849c)"
local overlay0 = "rgb(6c7086)"
local surface2 = "rgb(585b70)"
local surface1 = "rgb(45475a)"
local surface0 = "rgb(313244)"
local base = "rgb(1e1e2e)"
local mantle = "rgb(181825)"
local crust = "rgb(11111b)"

------------------
---- MONITORS ----
------------------

-- Left-to-right physical order: left Dell, laptop panel, right Dell.
-- Use Hyprland's `desc:` selector so the external monitor rules survive
-- connector renames such as DP-4 -> DP-6 after reconnecting docks/cables.
hl.monitor({ output = "desc:Dell Inc. DELL P2419H 9DPW893",       mode = "1920x1080", position = "0x0",    scale = 1 })
hl.monitor({ output = "desc:Sharp Corporation 0x149A",            mode = "1920x1080", position = "1920x0", scale = 1 })
hl.monitor({ output = "desc:Dell Inc. DELL P2417H CW6Y769A33LB",  mode = "1920x1080", position = "3840x0", scale = 1 })

---------------------
---- MY PROGRAMS ----
---------------------

local terminal = "ghostty"
local fileManager = "nautilus"
local menu = "rofi -show drun"

-------------------
---- AUTOSTART ----
-------------------

hl.on("hyprland.start", function()
    hl.exec_cmd("/usr/lib/polkit-gnome/polkit-gnome-authentication-agent-1")
    hl.exec_cmd("swaync")
    hl.exec_cmd("waybar")
    hl.exec_cmd("wl-paste --watch cliphist store")
    hl.exec_cmd("hyprshell run")
    hl.exec_cmd("hyprpaper & hypridle")
    hl.exec_cmd("hyprctl setcursor catppuccin-mocha-dark-cursors 28")
    hl.exec_cmd("nextcloud")
    hl.exec_cmd("dropbox")
end)

-------------------------------
---- ENVIRONMENT VARIABLES ----
-------------------------------

hl.env("XCURSOR_SIZE", "24")
hl.env("HYPRCURSOR_SIZE", "24")
hl.env("XDG_CURRENT_DESKTOP", "Hyprland")
hl.env("HTTP_PROXY", "http://localhost:8123")
hl.env("HTTPS_PROXY", "http://localhost:8123")
hl.env("http_proxy", "http://localhost:8123")
hl.env("https_proxy", "http://localhost:8123")
hl.env("NO_PROXY", "127.0.0.1")
hl.env("no_proxy", "127.0.0.1")

-----------------------
---- LOOK AND FEEL ----
-----------------------

hl.config({
    xwayland = {
        force_zero_scaling = true,
    },

    general = {
        gaps_in = 2,
        gaps_out = 3,
        border_size = 2,
        col = {
            active_border = { colors = { mauve, flamingo }, angle = 90 },
            inactive_border = subtext0,
        },
        resize_on_border = false,
        allow_tearing = false,
        layout = "dwindle",
    },

    decoration = {
        rounding = 4,
        rounding_power = 2,
        active_opacity = 1.0,
        inactive_opacity = 0.95,
        shadow = {
            enabled = true,
            range = 4,
            render_power = 3,
            color = "rgba(1a1a1aee)",
        },
        blur = {
            enabled = true,
            size = 3,
            passes = 1,
            vibrancy = 0.1696,
        },
    },

    animations = {
        enabled = true,
    },

    dwindle = {
        preserve_split = true,
    },

    master = {
        new_status = "master",
    },

    misc = {
        force_default_wallpaper = -1,
        disable_hyprland_logo = false,
    },

    input = {
        kb_layout = "fr",
        kb_variant = "dvorak",
        kb_model = "",
        kb_options = "caps:ctrl_modifier",
        kb_rules = "",
        follow_mouse = 1,
        sensitivity = 0,
        touchpad = {
            natural_scroll = false,
        },
    },
})

-- Curves and animations
hl.curve("easeOutQuint",   { type = "bezier", points = { {0.23, 1},    {0.32, 1} } })
hl.curve("easeInOutCubic", { type = "bezier", points = { {0.65, 0.05}, {0.36, 1} } })
hl.curve("linear",         { type = "bezier", points = { {0, 0},       {1, 1} } })
hl.curve("almostLinear",   { type = "bezier", points = { {0.5, 0.5},   {0.75, 1} } })
hl.curve("quick",          { type = "bezier", points = { {0.15, 0},    {0.1, 1} } })

hl.animation({ leaf = "global",        enabled = true, speed = 10,   bezier = "default" })
hl.animation({ leaf = "border",        enabled = true, speed = 5.39, bezier = "easeOutQuint" })
hl.animation({ leaf = "windows",       enabled = true, speed = 4.79, bezier = "easeOutQuint" })
hl.animation({ leaf = "windowsIn",     enabled = true, speed = 4.1,  bezier = "easeOutQuint",   style = "popin 87%" })
hl.animation({ leaf = "windowsOut",    enabled = true, speed = 1.49, bezier = "linear",         style = "popin 87%" })
hl.animation({ leaf = "fadeIn",        enabled = true, speed = 1.73, bezier = "almostLinear" })
hl.animation({ leaf = "fadeOut",       enabled = true, speed = 1.46, bezier = "almostLinear" })
hl.animation({ leaf = "fade",          enabled = true, speed = 3.03, bezier = "quick" })
hl.animation({ leaf = "layers",        enabled = true, speed = 3.81, bezier = "easeOutQuint" })
hl.animation({ leaf = "layersIn",      enabled = true, speed = 4,    bezier = "easeOutQuint",   style = "fade" })
hl.animation({ leaf = "layersOut",     enabled = true, speed = 1.5,  bezier = "linear",         style = "fade" })
hl.animation({ leaf = "fadeLayersIn",  enabled = true, speed = 1.79, bezier = "almostLinear" })
hl.animation({ leaf = "fadeLayersOut", enabled = true, speed = 1.39, bezier = "almostLinear" })
hl.animation({ leaf = "workspaces",    enabled = true, speed = 1.94, bezier = "almostLinear",   style = "fade" })
hl.animation({ leaf = "workspacesIn",  enabled = true, speed = 1.21, bezier = "almostLinear",   style = "fade" })
hl.animation({ leaf = "workspacesOut", enabled = true, speed = 1.94, bezier = "almostLinear",   style = "fade" })
hl.animation({ leaf = "zoomFactor",    enabled = true, speed = 7,    bezier = "quick" })

---------------
---- INPUT ----
---------------

hl.gesture({ fingers = 3, direction = "horizontal", action = "workspace" })

hl.device({
    name = "epic-mouse-v1",
    sensitivity = -0.5,
})

---------------------
---- KEYBINDINGS ----
---------------------

local mainMod = "SUPER"

hl.bind(mainMod .. " + RETURN", hl.dsp.exec_cmd(terminal))
hl.bind(mainMod .. " + Q", hl.dsp.window.close())
hl.bind(mainMod .. " + L", hl.dsp.exec_cmd("hyprlock"))
hl.bind(mainMod .. " + M", hl.dsp.exec_cmd("command -v hyprshutdown >/dev/null 2>&1 && hyprshutdown || hyprctl dispatch exit"))
hl.bind(mainMod .. " + E", hl.dsp.exec_cmd(fileManager))
hl.bind(mainMod .. " + F", hl.dsp.window.float({ action = "toggle" }))
hl.bind(mainMod .. " + R", hl.dsp.exec_cmd(menu))
hl.bind(mainMod .. " + P", hl.dsp.window.pseudo())
hl.bind(mainMod .. " + J", hl.dsp.layout("togglesplit"))
hl.bind(mainMod .. " + V", hl.dsp.exec_cmd("cliphist list | rofi -dmenu | cliphist decode | wl-copy"))
hl.bind(mainMod .. " + X", hl.dsp.exit())

-- Move focus with mainMod + arrow keys
hl.bind(mainMod .. " + left",  hl.dsp.focus({ direction = "left" }))
hl.bind(mainMod .. " + right", hl.dsp.focus({ direction = "right" }))
hl.bind(mainMod .. " + up",    hl.dsp.focus({ direction = "up" }))
hl.bind(mainMod .. " + down",  hl.dsp.focus({ direction = "down" }))

-- Send active window to the back
hl.bind(mainMod .. " + bracketleft", hl.dsp.window.alter_zorder({ mode = "bottom" }))

-- Hyprshell owns Alt+Tab now; the old rofi Alt+Tab bind was intentionally omitted.

-- Switch workspaces with physical number row keycodes, preserving the original dvorak-friendly binds.
for code = 10, 19 do
    local workspace = code - 9
    hl.bind(mainMod .. " + code:" .. code, hl.dsp.focus({ workspace = workspace }))
    hl.bind(mainMod .. " + SHIFT + code:" .. code, hl.dsp.window.move({ workspace = workspace }))
end

-- Special workspace / scratchpad
hl.bind(mainMod .. " + S", hl.dsp.workspace.toggle_special("magic"))
hl.bind(mainMod .. " + SHIFT + S", hl.dsp.window.move({ workspace = "special:magic" }))

-- Scroll through existing workspaces with mainMod + scroll
hl.bind(mainMod .. " + mouse_down", hl.dsp.focus({ workspace = "e+1" }))
hl.bind(mainMod .. " + mouse_up", hl.dsp.focus({ workspace = "e-1" }))

-- Move/resize windows with mainMod + LMB/RMB and dragging
hl.bind(mainMod .. " + mouse:272", hl.dsp.window.drag(), { mouse = true })
hl.bind(mainMod .. " + mouse:273", hl.dsp.window.resize(), { mouse = true })

-- Laptop multimedia keys for volume and LCD brightness
hl.bind("XF86AudioRaiseVolume", hl.dsp.exec_cmd("wpctl set-volume -l 1 @DEFAULT_AUDIO_SINK@ 5%+"), { locked = true, repeating = true })
hl.bind("XF86AudioLowerVolume", hl.dsp.exec_cmd("wpctl set-volume @DEFAULT_AUDIO_SINK@ 5%-"), { locked = true, repeating = true })
hl.bind("XF86AudioMute", hl.dsp.exec_cmd("wpctl set-mute @DEFAULT_AUDIO_SINK@ toggle"), { locked = true, repeating = true })
hl.bind("XF86AudioMicMute", hl.dsp.exec_cmd("wpctl set-mute @DEFAULT_AUDIO_SOURCE@ toggle"), { locked = true, repeating = true })
hl.bind("XF86MonBrightnessUp", hl.dsp.exec_cmd("brightnessctl -e4 -n2 set 5%+"), { locked = true, repeating = true })
hl.bind("XF86MonBrightnessDown", hl.dsp.exec_cmd("brightnessctl -e4 -n2 set 5%-"), { locked = true, repeating = true })

-- Requires playerctl
hl.bind("XF86AudioNext", hl.dsp.exec_cmd("playerctl next"), { locked = true })
hl.bind("XF86AudioPause", hl.dsp.exec_cmd("playerctl play-pause"), { locked = true })
hl.bind("XF86AudioPlay", hl.dsp.exec_cmd("playerctl play-pause"), { locked = true })
hl.bind("XF86AudioPrev", hl.dsp.exec_cmd("playerctl previous"), { locked = true })

hl.bind("PRINT", hl.dsp.exec_cmd("hyprshot -m region"))
hl.bind(mainMod .. " + SHIFT + PRINT", hl.dsp.exec_cmd("hyprshot -m window"))

--------------------------------
---- WINDOWS AND WORKSPACES ----
--------------------------------

hl.window_rule({
    name = "suppress-maximize-events",
    match = { class = ".*" },
    suppress_event = "maximize",
})

hl.window_rule({
    name = "fix-xwayland-drags",
    match = {
        class = "^$",
        title = "^$",
        xwayland = true,
        float = true,
        fullscreen = false,
        pin = false,
    },
    no_focus = true,
})

hl.window_rule({
    name = "move-hyprland-run",
    match = { class = "hyprland-run" },
    move = "20 monitor_h-120",
    float = true,
})

hl.window_rule({
    name = "float-whatsapp",
    match = { class = "whatsapp-electron" },
    float = true,
})

hl.window_rule({
    name = "float-nautilus",
    match = { class = "org.gnome.Nautilus" },
    float = true,
})

hl.window_rule({
    name = "float-firefox-extension",
    match = { class = "firefox", title = "^Extension.*$" },
    float = true,
})

hl.window_rule({
    name = "float-mail-all",
    match = { class = "org.mozilla.Thunderbird", initial_title = "^$" },
    float = true,
})

hl.window_rule({
    name = "float-mail-compose",
    match = { title = "^Rédaction.*$" },
    float = true,
    size = "980 600",
})
