# vim

- Insert a Unicode character

`<ctrl-v>U<code>`

- Fix errors with invisible characters (`stray ‘\302’ in program`)

`:% s,\%o302,,g`

- When you forgot a sudo (a classic!)

`:w ! sudo tee %`

- Remove hidden ^M after a copy-paste

`:e ++ff=dos`
`:set ff=unix`

