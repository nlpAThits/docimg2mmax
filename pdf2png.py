import argparse, os, subprocess
from PyPDF2 import PdfFileReader
from glob import glob
import regex as re
from ntpath import basename
from operator import itemgetter

if __name__ == '__main__':  
    parser = argparse.ArgumentParser()
    parser.add_argument('--pdf_folder',   default=None, required=True)
    parser.add_argument('--out_path',     default=None, required=True)
    parser.add_argument('--out_prefix',   default="",   required=False)
    parser.add_argument('--dpi',          default="300", required=False)
    # If set, input pdf files are processed in sort order, determined by the numerical value of the file name part up to the first position of this char. Non-numerical
    # chars in the sort string are removed.
    # If file name dioes not contain a particular separator, use . to use the full name w/o extension.
    # Ff not set, input files will be sorted alphabetically by file name.
    parser.add_argument('--num_sort_split_char',     default="", required=False)
    ns = parser.parse_args()
    if ns.num_sort_split_char != "":
        pdf_files = sorted([(f, int(re.sub('[^0-9]+','',basename(f)[0:basename(f).find(ns.num_sort_split_char)]))   ) for f in glob(ns.pdf_folder+os.path.sep+"*.*")], key=itemgetter(1))    
    else:
        pdf_files = sorted([(f, basename(f)[0:basename(f).rfind('.')]   ) for f in glob(ns.pdf_folder+os.path.sep+"*.*")], key=itemgetter(1))    
    for f in [f[0] for f in pdf_files if f[0].lower().endswith('.pdf')]:
        print(f)
        namebase=ns.out_prefix+basename(f)[0:basename(f).rfind('.')]+"@"+ns.dpi+"dpi"
        target_folder=ns.out_path+os.path.sep+namebase
        if not os.path.exists(target_folder):
            os.makedirs(target_folder)
        else:
            print(target_folder+" exists, skipping")
            continue
        numps       = [a+1 for a in range(0,PdfFileReader(open(f,'rb')).getNumPages())]
        for n in numps:
            print("Converting page", n)
            subprocess.check_output(["pdftocairo", "-r", ns.dpi, "-png", "-f", str(n) , "-l", str(n) , f, target_folder+os.path.sep+namebase])
