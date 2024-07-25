- List dependencies of a package

`brew deps <package>`
`brew deps --installed <package>`

- Switch to a different version of a package

`brew switch <package> <version>`

- Clean old versions of installed packages (remove -n when ok).

`brew cleanup -ns`

- Delete all archives in cache

`rm -rf $(brew --cache)`


