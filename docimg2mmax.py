import sys, argparse, shutil, os, subprocess
from glob import glob
from pymmax2.pyMMAX2 import * 
from multiprocessing import Process
from pathlib import Path
from docimg2mmax_lib import decolor_image, get_predominant_colors, get_chunks, get_line_type, ocrwords_to_lines
from docimg2mmax_lib import png_to_hocr, hocr_to_mmax2, analyse_hocr_line_span, extract_markup, create_html_document
from docimg2mmax_lib import extract_drawable_markup

# This will be called in parallel for chunks of image folders.
# Images of the same document will not be split across chunks.
def docimg2mmax_worker(args, folder_chunk, mmax2_target_folder, proc_namespace):
    for img_folder_name in folder_chunk:
        if args.verbose: 
            print("\nProcessing images in folder "+os.path.abspath(img_folder_name), file=sys.stderr)
        # Use name of folder with images as base for MMAX2 project name
        # If .mmax file exists, it will not be re-created.
        mmax2_proj_name   = create_mmax2_stub(os.path.basename(img_folder_name), mmax2_target_folder, 
                                              clear_basedata=True, clear_levels=['ocr_words', 'ocr_lines'], verbose=False)
        mmax2_disc = MMAX2Discourse(mmax2_proj_name, verbose=False)
        mmax2_disc.load_markables(verbose=False)
        if args.verbose: 
            print("  Creating "+os.path.abspath(mmax2_proj_name), file=sys.stderr)
        pages=None
        # pages is 1-based,so 0 means all
        if args.pages != "0":
            pages=map(int,args.pages.split(","))
        # Sort numerically by page number in order to keep correct import order.
        # This will only find *original* files in the image folder, not those in the /decol**/ sub-folder
        # Choice of decol images is controlled in the png_to_hocr method
        png_files = [a[0] for a in 
                sorted([(f, int( os.path.basename(f)[os.path.basename(f).rfind('-')+1:os.path.basename(f).rfind('.')] )) 
                for f in glob(img_folder_name+os.path.sep+"*.*") if f.lower().endswith('.png')], key=itemgetter(1))]
        for page_idx, png_file in enumerate(png_files):
            page_no = page_idx+1
            if pages and page_no not in pages:
                print("Skipping page no "+str(page_no), file=sys.stderr)
                continue
            hocr = png_to_hocr(png_file, 
                              ['--oem',args.oem,'--psm',args.psm,'--dpi',args.dpi,'-c','tessedit_create_hocr=1','-c','hocr_char_boxes=1','--tessdata-dir',args.tessdata_dir],
                              args.tmp_path+os.path.sep+proc_namespace+"_tessout.tmp", 
                              normalize_unicode=True, decolor=args.decolor_for_ocr, grey_thresh=50, black_thresh=100, verbose=args.verbose)

            hocr_to_mmax2(hocr, page_no, mmax2_disc, os.path.basename(png_file), 
                ignore_empty_chars=True, split_merged_chars=True, normalize_variants=False, separate_numbers=args.separate_numbers, verbose=args.verbose)

            if args.detect_markup:
                extract_markup(png_file, mmax2_disc, page_no, vertical=True, horizontal=True,
                        grey_thresh=int(args.markup_grey_threshold), marked_thresh=int(args.markup_marked_threshold), verbose=args.verbose)

        if not args.detect_markup:
            # Set markup default 
            for wo in [a for a in mmax2_disc.get_level('ocr_words').get_markables()]:
                wo.update_attributes({'markup': '0'})
        else:
            # Create HTML page
            drawable_markup_per_page=extract_drawable_markup(png_files, mmax2_disc, args.min_markup_percentage)
            create_html_document(drawable_markup_per_page, args.html_target_folder+os.path.sep+os.path.basename(mmax2_proj_name)+".html", mmax2_disc, margin_width=1500, scale_by=2)

        mmax2_disc.get_basedata().write(dtd_base_path='"', overwrite=True)
        mmax2_disc.get_level('ocr_words').write(to_path=mmax2_disc.get_mmax2_path()+mmax2_disc.get_markable_path(),  overwrite=True, no_backup=True)
        mmax2_disc.get_level('ocr_lines').write(to_path=mmax2_disc.get_mmax2_path()+mmax2_disc.get_markable_path(),  overwrite=True, no_backup=True)
        mmax2_disc.get_level('text_words').write(to_path=mmax2_disc.get_mmax2_path()+mmax2_disc.get_markable_path(), overwrite=True, no_backup=True)
        print(mmax2_disc.info(), file=sys.stderr)

def docimg2mmax(args):
    # Create folders, if neccessary
    if not os.path.exists(args.tmp_path):
        os.mkdir(args.tmp_path)
    if not os.path.exists(args.html_target_folder):
        os.makedirs(args.html_target_folder)

    # Create target data template, if neccessary
    mmax2_stub_path = "./data/stub/"
    if not os.path.exists(args.mmax2_target_folder+os.path.sep+"MMAX2"+os.path.sep):
        # The *complete* folder does not exist yet
        if not os.path.exists(args.mmax2_target_folder):
            os.makedirs(args.mmax2_target_folder)
        shutil.copytree(mmax2_stub_path, args.mmax2_target_folder, dirs_exist_ok=True)
    mmax2_target_folder = args.mmax2_target_folder+os.path.sep+"MMAX2"+os.path.sep

    # Start processing
    procs=[]
    for folder_chunk in get_chunks(sorted([os.path.dirname(f) for f in glob(args.img_folders)]), int(args.workers)):
        p = Process(target=docimg2mmax_worker, args=(args, folder_chunk, mmax2_target_folder, str(os.getpid())+"_"+str(len(procs))))
        p.start()
        procs.append(p)
    for p in procs: p.join()

#############################################
if __name__ == '__main__': 
#############################################    
    parser = argparse.ArgumentParser()
    # Folders of PNG files to be imported. Use quotation marks if argument contains a wildcard: "./imagefile/*/"
    # We expect one folder per document with the individual page file names to *end with* -01.png, 
    # so that we can extract the page number. This is the format produced by the pdf2png tool.
    parser.add_argument('--img_folders',                default=None, required=True)
    # This is the path to the folder *containing* the MMAX2 folder!
    parser.add_argument('--mmax2_target_folder',        default=None, required=True)
    parser.add_argument('--html_target_folder',         default ="."+os.path.sep+"html"+os.path.sep)
    # For parallelization
    parser.add_argument('--workers',                    default="1")
    parser.add_argument('--pages',                      default="0")
    parser.add_argument('--verbose',                    default=False, dest='verbose', action='store_true')
    parser.add_argument('--tmp_path',                   default="."+os.path.sep+"tmp"+os.path.sep)
    parser.add_argument('--no_decolor_for_ocr',         default=True, dest='decolor_for_ocr', action='store_false')

    parser.add_argument('--detect_markup',              default=False, dest='detect_markup', action='store_true')
    parser.add_argument('--markup_grey_threshold',      default="10")
    parser.add_argument('--markup_marked_threshold',    default="10")
    parser.add_argument('--min_markup_percentage',      default="40")
    # For tokenization
    parser.add_argument('--no_separate_numbers',        default=True, dest='separate_numbers', action='store_false')
    # tesseract parameters. Stick to actual parameter names (except _ for -)
    parser.add_argument('--tessdata_dir',               default=None, required=True)
    parser.add_argument('--oem',                        default=None, required=True)
    parser.add_argument('--psm',                        default=None, required=True)
    parser.add_argument('--dpi',                        default=None, required=True)

    docimg2mmax(parser.parse_args())
