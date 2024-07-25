# RTL-SDR

- Pipe [softfm](https://github.com/jorisvr/SoftFM) to sox

`softfm  -f 98.3M -g 20.7 -b 0.1 -R - | play -t raw -esigned-integer -b16 -r 48000 -c 2 -`

- Pipe rtl_fm to sox

`rtl_fm -M wbfm -f 103.5M -F 0 -g 37.5 -s 250k | play -r 32k -t raw -e s -b 16 -c 1 -V1 -`

