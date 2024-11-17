wget -qO- "https://yihui.org/tinytex/install-bin-unix.sh" | sh

tlmgr update --self
tlmgr update --all

# for the slides
tlmgr install beamertheme-metropolis pgfopts soul caption
# for the whole tufte-latex series
tlmgr install tufte-latex hardwrap xtlxtra realscripts titlesec ragged2e textcase setspace fancyhdr
# for the French
tlmgr install babel-french hyphen-french
# useful without inkscape?
tlmgr install svg transparent
