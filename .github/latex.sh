wget -qO- "https://yihui.org/tinytex/install-bin-unix.sh" | sh

# for the slides
tlmgr install beamertheme-metropolis pgfopts soul caption
# for the whole tufte-latex series
tlmgr install tufte-latex hardwrap xtlxtra realscripts titlesec ragged2e textcase setspace fancyhdr
