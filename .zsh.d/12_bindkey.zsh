
# Functions together with their bindkeys

wan_ip_v4() {
  curl -f -s -m 2 -4 ifconfig.me
}

wan_ip_v6() {
  curl -f -s -m 2 -6 ifconfig.me
}

display_date () {
    echo;
    echo "\033[1m$(date -u)\033[0m";
    echo "\033[0;36m$(date)\033[0m";
    TZ="Asia/Tokyo" date;
    echo; echo; zle redisplay
}
zle -N display_date

weather () {
    echo
    # curl -f -s -m 2 'wttr.in/Toulouse?format=3' || printf '\n'
    curl 'wttr.in/Toulouse?format=Moon+phase:+%m'
    echo
    curl 'wttr.in/Toulouse?format=%l+%c%09+%t,+%w'
    echo
    curl 'wttr.in/Delft?format=%l%09+%c%09+%t,+%w'
    echo
    curl 'wttr.in/Kyoto?format=%l%09+%c%09+%t,+%w'
    echo; echo; zle redisplay
}
zle -N weather

xclip_qrcode() {
    if [[ $(uname -s) = "Darwin" ]]; then
        pbpaste | qrcode
    elif [[ $(uname -s) = "Linux" ]]; then
        xclip -o -s c | qrcode
    fi
}
zle -N xclip_qrcode

xclip_scan() {
    if [[ $(uname -s) = "Linux" ]]; then
        xclip -selection clipboard -t image/png -o | tesseract stdin stdout
    fi
}
zle -N xclip_scan

my_ip () {
    echo
    echo "Local IP"
    ifconfig | grep -Eo 'inet (addr:)?([0-9]*\.){3}[0-9]*' | grep -Eo '([0-9]*\.){3}[0-9]*' | grep -v '127.0.0.1'
    echo "External IP"; echo $(wan_ip_v4); echo $(wan_ip_v6)
    echo; echo; zle redisplay
}
zle -N my_ip

# Insert special character with ^V + char
bindkey "[15~" display_date  # F5
bindkey "[17~" my_ip # F6
bindkey "[18~" xclip_qrcode # F7
bindkey "[19~" xclip_scan # F8
bindkey "[20~" weather  # F9
