# mdfind

> mdfind is the MacOS interface to the Spotlight search engine.
> MacOS runs a daemon to index all files on the system.
> mdfind searches for patterns inside files

- the five latest modified files (limited to the past 5 days)

`mdfind -onlyin ~/Pictures 'kMDItemPixelCount > 15000000'`

- real-time mode

`mdfind -live 'kMDItemContentModificationDate >= $time.now'`

