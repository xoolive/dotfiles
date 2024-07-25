# magick convert

- Convert a SVG file and handle transparency

`convert -background none -density 1000 -resize 1000x file.svg file.png`

- Convert a batch of PDF files to PNG

  > You may need to edit the /etc/ImageMagick-6/policy.xml to allow the conversion
  > to PDF files. Find and edit to get the following line:
  >   <policy domain="coder" rights="read | write" pattern="PDF" />

`for i in *.pdf; do convert -density 300 -trim $i ${i:r}.png; done`

- Handle transparency

`convert input.png -fuzz 10% -transparent white output.png`

- Remove transparency

`convert input.png -flatten output.png`

