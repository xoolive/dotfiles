setopt incappendhistory   # appendhistory, incappendhistory, sharehistory
setopt auto_pushd         # "cd" met le répertoire d'où on vient sur la pile
setopt auto_remove_slash  # Enleve les / inutiles en completion
setopt chase_links        # Traite les liens symboliques comme il faut
setopt correct
setopt correct_all
setopt glob_complete      # Completion avec RegEx
setopt hist_verify        # completion historique (!) intelligente
setopt print_exit_value   # Affiche le code de sortie si différent de '0'
setopt printeightbit
setopt pushd_ignore_dups  # Ignore les doublons dans la pile
setopt pushd_silent       # N'affiche pas la pile après un "pushd" ou "popd"
setopt pushd_to_home      # "pushd" sans argument = "pushd $HOME"

unsetopt bg_nice          # nice(bg_job) = 0
unsetopt clobber          # >| doit etre utilise
unsetopt hup              # Garde les jobs ouvert si le terminal ferme
unsetopt ignore_eof       # Ctrl+D est équivalent à 'logout'
unsetopt list_ambiguous
unsetopt rm_star_silent   # Demande confirmation pour 'rm *'


