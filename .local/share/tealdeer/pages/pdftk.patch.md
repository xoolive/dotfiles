- Crop a pdf file to hide/reveal part of it

`pdfcrop --margins '0 0 0 -620' --clip private_information.pdf`

- Uncompress a pdf file

`pdftk book.pdf output uncompressed.pdf uncompress`

- Compress a pdf file

`pdftk uncompressed.pdf output clean.pdf compress`


