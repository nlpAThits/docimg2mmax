# docimg2mmax

## Installation
```
$ git clone https://github.com/nlpAThits/docimg2mmax.git
$ cd docimg2mmax
$ conda create --name docimg2mmax python=3.8 --file reqs.txt
$ source activate docimg2mmax
$ pip install pypdf2 opencv-python
$ wget https://github.com/nlpAThits/pyMMAX2/archive/refs/tags/v0.65.zip
$ unzip v0.65.zip
$ pip install pyMMAX2-0.65/.
```
## Prepare PDF documents
```
$ python pdf2png.py --pdf_file_path ./data/in/pdf/PMC6742607_w_markup_300dpi.pdf --out_path ./data/in/png/ --num_sort_split_char . --decolor
```

## Extract text and markup
