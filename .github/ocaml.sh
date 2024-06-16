bash -c "sh <(curl -fsSL https://raw.githubusercontent.com/ocaml/opam/master/shell/install.sh)"

opam init

eval $(opam env --switch=default)

opam install dune
opam install ocaml-lsp-server
opam install ocamlformat
