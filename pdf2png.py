import argparse, os, sys, subprocess
from PyPDF2 import PdfFileReader
from glob import glob
import regex as re
from operator import itemgetter
from docimg2mmax_lib import decolor_image

if __name__ == '__main__':  
    parser = argparse.ArgumentParser()
    parser.add_argument('--pdf_file_path',          default=None,   required=True)
    parser.add_argument('--out_path',               default=None,   required=True)
    parser.add_argument('--out_prefix',             default="",     required=False)
    parser.add_argument('--dpi',                    default="300",  required=False)
    parser.add_argument('--decolor_grey_thresh',    default="50",   required=False)
    parser.add_argument('--decolor_black_thresh',   default="100",  required=False)    
    parser.add_argument('--decolor',                default=False,  dest='decolor', action='store_true')

    # If set, input pdf files are processed in sort order, determined by the numerical value of the file name part up to the first position of this char. 
    # Non-numerical chars in the sort string are removed first.
    # If file name does not contain a particular separator, use . to use the full name w/o extension.
    # If not set, input files will be sorted alphabetically by file name.
    parser.add_argument('--num_sort_split_char',    default="",     required=False)
    ns = parser.parse_args()
    if ns.num_sort_split_char != "":
        pdf_files = sorted([(f, int(re.sub('[^0-9]+','',os.path.basename(f)[0:os.path.basename(f).find(ns.num_sort_split_char)]))   ) for f in glob(ns.pdf_file_path)], key=itemgetter(1)) 
    else:
        pdf_files = sorted([(f, os.path.basename(f)[0:os.path.basename(f).rfind('.')]   ) for f in glob(ns.pdf_file_path)], key=itemgetter(1))    
    for f in [f[0] for f in pdf_files if f[0].lower().endswith('.pdf')]:
        print("Doc "+str(os.path.abspath(f)), file=sys.stderr)
        namebase=ns.out_prefix+os.path.basename(f)[0:os.path.basename(f).rfind('.')]+"@"+ns.dpi+"dpi"
        target_folder=ns.out_path+os.path.sep+namebase
        if not os.path.exists(target_folder):
            os.makedirs(target_folder, exist_ok=True)
        else:
            print(target_folder+" exists, skipping", file=sys.stderr)
            continue
        for n in [a+1 for a in range(0,PdfFileReader(open(f,'rb')).getNumPages())]:
            print(" Converting page "+str(n), file=sys.stderr)
            subprocess.check_output(["pdftocairo", "-r", ns.dpi, "-png", "-f", str(n) , "-l", str(n) , f, target_folder+os.path.sep+namebase])
        if ns.decolor:
            for i in glob(target_folder+os.path.sep+namebase+"*.png"):
                print(" Decoloring page "+str(os.path.basename(i)), file=sys.stderr)
                decolor_image(i, grey_thresh=int(ns.decolor_grey_thresh), black_thresh=int(ns.decolor_black_thresh))
