# zmv

- Rename file contents with its directory name as a prefix

`zmv -n '(*)/(*.txt)' '${1}_$2'`

- Add leading zeros to a filename (1.jpg -> 001.jpg, ...)  

`zmv -n '(<1->).jpg' '${(l:3::0:)1}.jpg'`

- Change the suffix from *.sh to *.pl

`zmv -n -W '*.sh' '*.pl'`

