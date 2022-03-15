import sys, os, cv2, subprocess, unicodedata
import numpy as np

from pathlib import Path
from PIL import Image
from operator import itemgetter

from pymmax2.pyMMAX2 import * 
from tqdm import tqdm
PROGBARWIDTH    =   100

def extract_drawable_markup(png_files, mmax2_disc, min_markup_percentage):
    drawable_markup_per_page={}
    for page_idx, page_path in enumerate(png_files):                
        page_no = page_idx+1
        markup_bd_sequence=[]
        seq_count=0
        string_matches = {}
        # Go over all ocr_word markables
        for m in [m for m in mmax2_disc.get_level('ocr_words').get_markables() if int(m.get_attributes()['page_no'])==page_no]:
            # Extract markup intensity
            mku=float(m.get_attributes().get('markup','0'))
            if mku<int(min_markup_percentage):
                # Current m is not marked-up. Write existing sequence, if any.
                if markup_bd_sequence!=[]:
                    ocr_words_at_match_bds=[]
                    # single_match_elements is a list of bd ids that were matched.
                    # Go over all bd_elements in current match (mostly only one)
                    for bd_elem in markup_bd_sequence:
                        # Get ocr-word markable
                        ocr_word = mmax2_disc.get_level('ocr_words').get_markables_for_bd(bd_elem, with_attributes=None)[0]
                        if ocr_word not in ocr_words_at_match_bds:
                            ocr_words_at_match_bds.append(ocr_word)
                    lab_string="HL ("+str(seq_count)+"):::::"

                    frags, col=ocrwords_to_lines(ocr_words_at_match_bds)
                    for frag in frags:
                        lab_string+=(mmax2_disc.render_markables(frag)[0]+"\n")

                    string_matches[lab_string]=[markup_bd_sequence]
                    seq_count+=1
                    # Reset markup collector
                    markup_bd_sequence=[]
            else:
                # Current m is marked-up
                markup_bd_sequence.extend(flatten_spanlists(m.get_spanlists()))
        else:
            # Handle last one
            if markup_bd_sequence!=[]:
                ocr_words_at_match_bds=[]
                # single_match_elements is a list of bd ids that were matched.
                # Go over all bd_elements in current match (mostly only one)
                for bd_elem in markup_bd_sequence:
                    # Get ocr-word markable
                    ocr_word = mmax2_disc.get_level('ocr_words').get_markables_for_bd(bd_elem, with_attributes=None)[0]
                    if ocr_word not in ocr_words_at_match_bds:
                        ocr_words_at_match_bds.append(ocr_word)
                lab_string="HL ("+str(seq_count)+"):::::"

                frags, col = ocrwords_to_lines(ocr_words_at_match_bds)
                for frag in frags:
                    lab_string+=(mmax2_disc.render_markables(frag)[0]+"\n")
                string_matches[lab_string]=[markup_bd_sequence]
        drawable_markup_per_page[str(page_no)]=(string_matches, page_path)
    return drawable_markup_per_page


def ocrwords_to_lines(ocr_words_list):
    # Go over all markables in list, which might come from two or more lines.
    # Collect as long as l is increasing
    # Note: For marked-up sections, matches might even cross more than one line break!
    frag,frags=[],[]
    last_l = 0
    total_r, total_g, total_b = 0,0,0
    mk_words=0
    # Go over all ocr words
    for ocr_word in ocr_words_list:
        if float(ocr_word.get_attributes().get('markup','0'))>0:
            mk_words+=1
            r,g,b = map(int,ocr_word.get_attributes().get('markup_color','0:0:0').split(":"))
            total_r+=r
            total_g+=g
            total_b+=b
        # Get left pos of current ocr_word
        l,_,_,_ = map(int,ocr_word.get_attributes()['word_bbox'].split(" "))
        if len(frag)==0 or l > last_l:
            frag.append(ocr_word)
            last_l=l
        else:
            # l has decreased, which means we passed a line break / 'carriage return'
            frags.append(frag)
            frag=[ocr_word]
            last_l=0
    else:
        if len(frag)>0:
            frags.append(frag)
    return frags, ( int(total_r/mk_words), int(total_g/mk_words), int(total_b/mk_words))


def create_html_document(drawable_data_per_page, save_as, mmax2_disc, margin_width=1000, highlight_recognized_words=True, scale_by=1, mark_words=False, color_labels=False):
    with open(save_as,"w") as html_out:
        print('<!DOCTYPE html>\n<html>\n<head>\n<style>\n'\
            ' .reco      { fill: green; opacity: 0.2; }\n'\
            ' .underline { stroke-width: 3; stroke: green; }\n'\
            ' .labelline { stroke-width: 3; stroke: black; }\n'\
            ' .text      { fill: black; font: normal 38px sans-serif; background: orange; }\n'\
            '  </style>\n</head>\n<body>\n<main>', file=html_out)
        # Go over all pages (some might not have anything to draw)
        for page_no in drawable_data_per_page:
            page_path = drawable_data_per_page[str(page_no)][1]
            # Get page shape from actual page image, for setting the svg viewbox size
            page_height, page_width,_ = cv2.imread(page_path).shape
            # One figure per page: <figure><svg><image></image><rect/>...<rect/><line/>...<line/><text>AB</text>...<text>XY</text></svg></figure>
            # This uses the org image that was also used for ocr
            vboxwidth   =(page_width*scale_by)+(2*margin_width)
            vboxheight  =page_height*scale_by
            #print('<figure id="page'+str(page_no)+'">\n<svg viewBox="0 0 '+str(vboxwidth)+' '+str(vboxheight)+'">\n\
            # <image transform="scale('+str(scale_by)+','+str(scale_by)+')"  x="'+str(margin_width)+'" xlink:href="'+page_path+'"></image>', file=html_out)
            print('<figure id="page'+str(page_no)+'">\n<svg width="'+str(vboxwidth)+'" height="'+str(vboxheight)+'">\n\
                <image width="'+str(page_width*scale_by)+'" height="'+str(page_height*scale_by)+'"  x="'+str(margin_width)+'" xlink:href="'+os.path.abspath(page_path)+'"></image>', file=html_out)

            if highlight_recognized_words:
                # Go over all ocr-words on current page
                for m in [m for m in mmax2_disc.get_level('ocr_words').get_markables() if m.get_attributes()['page_no']==page_no]:
                    l,t,r,b = map(int,m.get_attributes()['word_bbox'].split(" "))
                    x1=(l*scale_by)+margin_width
                    y1=b*scale_by
                    x2=(r*scale_by)+margin_width
                    y2=y1
                    print('<line x1="'+str(x1)+'" y1="'+str(y1)+'" x2="'+str(x2)+'" y2="'+str(y2)+'" class="underline"/>', file=html_out)

            matched_terms_on_page   = drawable_data_per_page[str(page_no)][0]
            matchspanstring2markables={}
            # Distribute all records to left and right side, based on the bboxes of their ocr-words
            # New: Repeat the same label on both sides if they have matches on both sides.
            matched_terms_on_right, matched_terms_on_left={}, {}
            # There is one match_dict per page! match_dict is a dict with the match_string as key 
            # and a list of lists of matching bd_elements as value
            for search_string in matched_terms_on_page:
                # Go over all matches for current search string. These can be actual matches or marked-up sections
                # Each match has a list of bd_ids which together are the match
                for single_match_elements in matched_terms_on_page[search_string]:
                    ocr_words_at_match_bds=[]
                    # single_match_elements is a list of bd ids that were matched.
                    # Go over all bd_elements in current match (mostly only one)
                    for bd_elem in single_match_elements:
                        # Get ocr-word markable
                        ocr_word = mmax2_disc.get_level('ocr_words').get_markables_for_bd(bd_elem, with_attributes=None)[0]
                        if ocr_word not in ocr_words_at_match_bds:
                            ocr_words_at_match_bds.append(ocr_word)
                    # ocr_words_at_match_bds is now the list of markables for the current single match
                    # Store mapping of bd_eleme id string to list of pertaining markables
                    matchspanstring2markables["".join(single_match_elements)]=ocr_words_at_match_bds

                    # Determine whether to draw the current match on the left or right margin
                    # Get bbox of first element in markable
                    l,_,r,_ = map(int,ocr_words_at_match_bds[0].get_attributes()['word_bbox'].split(" "))
                    if (l+((r-l)/2)<=page_width/2):  
                        # Draw on left
                        try:
                            matched_terms_on_left[search_string].append(ocr_words_at_match_bds)
                        except KeyError:
                            matched_terms_on_left[search_string]=[ocr_words_at_match_bds]
                    else:                            
                        try:                
                            matched_terms_on_right[search_string].append(ocr_words_at_match_bds)
                        except KeyError:    
                            matched_terms_on_right[search_string]=[ocr_words_at_match_bds]

            # This calculates the stepsize on the basis of the actual number of labels 
            try:                        
                stepsize_left   = 1 / (len(matched_terms_on_left)+1)
            except ZeroDivisionError:   
                stepsize_left   = 0
            try:                        
                stepsize_right  = 1 / (len(matched_terms_on_right)+1)
            except ZeroDivisionError:   
                stepsize_right  = 0

            # Start at 1 to prevent 0 y pos
            drawn_left, drawn_right=1,1
            # Determine drawing target on left or right side, and y position
            # y pos is based on static stepsize per side, which should be ok
            for (drawable_data, drawing) in [(matched_terms_on_left, 'left'), (matched_terms_on_right, 'right')]:
                for label_text in drawable_data:
                    if drawing == 'left':   
                        label_y = drawn_left  * stepsize_left * (page_height*scale_by)
                        label_x = 10
                    else:                   
                        label_y = drawn_right * stepsize_right * (page_height*scale_by)
                        label_x = margin_width + (page_width*scale_by) + 10

                    drawable_label_text=label_text if ":::::" not in label_text else label_text.split(":::::")[1]
                    blen=len(drawable_label_text.split("\n"))-1
                    fill_col="rgb(150,150,150)"
                    if color_labels:
                        _, col=ocrwords_to_lines(drawable_data[label_text][0])                    
                        fill_col="rgb"+str(col)
                    # Now set predom color here
                    print('<g><rect style="cursor:normal; stroke-width:3; fill:'+fill_col+'; fill-opacity:1" x="'+str(label_x)+'" y="'+str(label_y-38)+'" width="'+str(margin_width-10)+'" height="'+str(45*blen)+'"><title><html>'+drawable_label_text+'</html></title></rect>', file=html_out)
                    for fidx, f in enumerate(drawable_label_text.split("\n")):
                        # Draw label text. In case of ocr / syn, it contains the actually found string already.
                        if fidx == 0:
                            print('<text class="text" x="'+str(label_x)+'" y="'+str(label_y)+'">'+f, file=html_out)
                        else:
                            print('<tspan class="text" x="'+str(label_x)+'" dy="1.0cm">'+f+'</tspan>', file=html_out)
                    print('</text></g>', file=html_out)

                    padding=5
                    for m in drawable_data[label_text]:
                        # If a match or marked-up section crosses line boundaries, each frag will represent one matched line
                        line_frags, _=ocrwords_to_lines(m)
                        for fidx, frag in enumerate(line_frags):
                            l,t,_,_ = map(int,frag[0].get_attributes()['word_bbox'].split(" "))
                            _,_,r,b = map(int,frag[-1].get_attributes()['word_bbox'].split(" "))

                            # Draw box around marked-up text
                            box_x       = (l*scale_by) + margin_width - padding
                            box_y       = (t*scale_by)                - padding
                            box_width   = (r*scale_by  - l*scale_by)   + 2*padding
                            box_height  = (b*scale_by  - t*scale_by)   + 2*padding
                            if mark_words:
                                print('<rect style="cursor:normal; stroke-width:2; stroke:black; fill-opacity:0" x="'+str(box_x)+'" y="'+str(box_y)+'" width="'+str(box_width)+'" height="'+str(box_height)+'"/>', file=html_out)

                            if fidx==0:
                                # Attach line at top or bottom, depending on rel. pos. of label
                                if label_y < t*scale_by: 
                                    frag_y = t*scale_by
                                else:           
                                    frag_y = b*scale_by
                                if drawing=="right":                                
                                    print('<line x1="'+str(r*scale_by + margin_width)+'" y1="'+str(frag_y)+'" x2="'+str(label_x)+'" y2="'+str(label_y)+'" class="labelline" />', file=html_out)
                                else:
                                    print('<line x1="'+str(l*scale_by + margin_width)+'" y1="'+str(frag_y)+'" x2="'+str(margin_width)+'" y2="'+str(label_y)+'" class="labelline"/>', file=html_out)

                    if drawing=="left": drawn_left+=1
                    else:               drawn_right+=1

            print('</svg>\n</figure>', file=html_out)
        print('</main>\n</body>\n</html>', file=html_out)


# Return left_col, right_col, or double_col
def get_line_type(line_markable, mmax2_disc, binary_mask, color_mask):
    _, page_width   = binary_mask.shape
    line_type='unk'
    # This box is the part of the line that is covered with text.
    # It has been handled already.
    l,t,r,b = map(int,line_markable.get_attributes().get('line_bbox').split(" "))
    # Default: double_col; find evidence for left or right
    # l            = distance from left margin to line start
    # page_width-r = distance from right margin to line end
    l_bin_area = binary_mask[t:b,0:l]
    l_col_area = color_mask[t:b,0:l]
    l_margin_highlight = 100 - ((np.sum(l_bin_area)*100)/((b-t)*(l)))
    #l_predom_rgb_tuple = get_predominant_color(l_col_area)

    r_bin_area = binary_mask[t:b,r:page_width]
    r_col_area = color_mask[t:b,r:page_width]
    r_margin_highlight = 100 - ((np.sum(r_bin_area)*100)/((b-t)*(page_width-r)))
    #r_predom_rgb_tuple = get_predominant_color(r_col_area)

    maxr,maxg,maxb = (0,0,0)
    margin_highlight=0
    if  l*100/page_width <= 40 and (page_width-r) > page_width/2:
        line_type='left_col'
        margin_highlight = l_margin_highlight
        if margin_highlight>0:# and get_predom_col:
            [[maxr,maxg,maxb]]=get_predominant_colors(l_col_area) if margin_highlight>0 else (0,0,0)
    elif l >= page_width/2:
        line_type='right_col'
        margin_highlight = r_margin_highlight
        if margin_highlight>0:# and get_predom_col:
            [[maxr,maxg,maxb]]=get_predominant_colors(r_col_area)
    else:
        line_type='double_col'
        if l_margin_highlight>r_margin_highlight:
            margin_highlight = l_margin_highlight
            if margin_highlight>0:# and get_predom_col:
                [[maxr,maxg,maxb]]=get_predominant_colors(l_col_area)
        else:
            margin_highlight = r_margin_highlight
            if margin_highlight>0:# and get_predom_col:
                [[maxr,maxg,maxb]]=get_predominant_colors(r_col_area)
    return line_type, l, t, r, b, margin_highlight, (maxr, maxg, maxb)


# Use low marked_thresh here, filtering can be done later
def extract_markup(page_img_path, mmax2_disc, page_no, vertical=True, horizontal=True, grey_thresh=10, marked_thresh=10, verbose=False):
    # Extract highlighted regions
    page_img        = cv2.cvtColor(cv2.imread(page_img_path), cv2.COLOR_BGR2RGB)
    page_img_height, page_img_width, _ = page_img.shape
    binary_mask     = np.full((page_img_height, page_img_width   ),0, dtype=np.uint8)   # all-zeros
    color_mask      = np.empty((page_img_height, page_img_width, 3))                    # un-initialized, nan array must not have an int type!!
    color_mask.fill(np.nan)

    bar = tqdm(total=page_img_height*page_img_width, ncols=PROGBARWIDTH, desc="  Detecting non-grey image regions")
    # Binarize by detecting all non-greys
    for h in range(page_img_height):
        for w in range(page_img_width):
            [b,g,r]=map(int,page_img[h,w])
            # Grey = high degree of similarity between all three color components.
            # If the abs delta is below the threshold for all three components, mark pixel as grey=1
            # For clean bw printouts with clear, non-fluorescent markup, grey_threshold can be set to *very* low
            if (abs(b-g)<=grey_thresh and abs(g-r)<=grey_thresh and abs(b-r)<=grey_thresh):
                binary_mask[h,w] = 1 # set mask to grey = 1
            else:
                # Non-grey, leave binary_mask as 0, and preserve color
                # Non-colored pixels should remain nan
                color_mask[h,w,0]=b
                color_mask[h,w,1]=g
                color_mask[h,w,2]=r
            bar.update(1) 
    bar.close()

    if horizontal:
        # Go over all words in ocr level, on page page_no
        # This will only check *words* for highlighting (not the other way round)
        # Section-level highlighting in blank areas will be ignored.
        for wo in [a for a in mmax2_disc.get_level('ocr_words').get_markables() if a.get_attributes()['page_no'] == str(page_no)]:
            wo.update_attributes({'markup': '0'})
            # Get word bbox (0,0 is top-left)
            l,t,r,b = map(int,wo.get_attributes()['word_bbox'].split(" "))
            # Get corresponding area in binary_mask
            bm_area = binary_mask[t:b,l:r]
            # Compute percentage of colored pixels in binary_mask
            sc = 100 - ((np.sum(bm_area)*100)/((b-t)*(r-l)))
            if sc > marked_thresh:
                [[maxr,maxg,maxb]]=get_predominant_colors(color_mask[t:b,l:r])

                wo.update_attributes({'markup'          : str(round(sc,4))})
                wo.update_attributes({'markup_color'    : str(maxr)+":"+str(maxg)+":"+str(maxb)})
                wo.update_attributes({'markup_type'     : 'word'})
                
    if vertical:
        # Now handle vertical highlighting at the page or column margin
        for line_markable in [a for a in mmax2_disc.get_level('ocr_lines').get_markables() if a.get_attributes()['page_no']==str(page_no)]:
            # Get line position on page first
            line_type, l, t, r, b, hl_val, (maxr,maxg,maxb) = get_line_type(line_markable, mmax2_disc, binary_mask, color_mask)
            draw_line_types=True
            if draw_line_types:
                if line_type=='left_col':
                    cl=(255,0,0)  
                elif line_type=='right_col':
                    cl=(0,255,0)
                else:
                    cl=(0,0,255)

            # No line-level of any word level does exist already
            if len([m for m in line_markable.get_associated_markables('ocr_words') if m.get_attributes()['markup']!='0'])==0:
                # No need to distiguish between left or right here
                if hl_val > 0:
                    # Get all still unmarked ocr_words in current line (word-level highlighting has preference over line-level)
                    for aw in [m for m in line_markable.get_associated_markables('ocr_words') if m.get_attributes()['markup']=='0']:
                        aw.update_attributes({'markup': str(round(hl_val,4))})
                        aw.update_attributes({'markup_type': 'line'})
                        aw.update_attributes({'markup_color' : str(maxr)+":"+str(maxg)+":"+str(maxb)})
    


# Effectively a wrapper for tesseract.
def png_to_hocr(png_file="", tess_args=[], outfile_name='.'+os.path.sep+'tessout.tmp', 
    normalize_unicode=True, page_no=-1, decolor=False, grey_thresh=50, black_thresh=100, verbose=False):
    if verbose: 
        print("    png_to_hocr: "+str(os.path.basename(png_file))+" ...", file=sys.stderr)
    if decolor:
        # Name of decolorized page image file. File will be reused if possible
        pathlabel="decol_gt"+str(grey_thresh)+"_bt"+str(black_thresh)
        decol_png_file = str(Path(png_file).parent)+os.path.sep+pathlabel+os.path.sep+os.path.basename(png_file)
        if not os.path.exists(decol_png_file):
            png_file = decolor_image(png_file, grey_thresh=grey_thresh, black_thresh=black_thresh)
        else:
            if verbose: print("    Using existing image in /"+pathlabel+"/", file=sys.stderr)
            png_file=decol_png_file
    targs=['tesseract', png_file, outfile_name]
    targs.extend(tess_args)
    if verbose:
        print("     ## tesseract output ##", file=sys.stderr)
    res=subprocess.run(targs, capture_output=True).stderr.decode(sys.getfilesystemencoding()).strip()
    if verbose:
        for z in res.split("\n"):
            print("      "+z, file=sys.stderr)
        print("     ## tesseract output ##", file=sys.stderr)
    with open (outfile_name+".hocr", "r") as myfile:
        r="".join(myfile.readlines())
    if normalize_unicode:
        r=unicodedata.normalize('NFKD', r)
    return r

# Convert string in hocr format (producd ed by e.g. tesseract) into MMAX2 basedata, 
# creating ocr_words and ocr_lines on the respectove markable levels.
def hocr_to_mmax2(hocr_string, page_no, mmax2_disc, img_name, ignore_empty_chars=False, split_merged_chars=False, normalize_variants=False, separate_numbers=True, verbose=False, debug=False):
    if verbose: print("    hocr_to_mmax2, page "+str(page_no), file=sys.stderr)
    hocr_soup = bs(hocr_string, 'lxml')
    # Go over all spans of class 'ocr_line'. Each has the line words as its children.
    if debug: print(hocr_soup)

    line_spans = [s for s in hocr_soup.descendants if s.name == 'span' and 'ocr_line' in s['class']]
    for line_span in line_spans:
        line_string,stringindex2wordid,wordid2title,wordid2charconfs,wordid2worstcharconf,wordid2charbboxes=\
                analyse_hocr_line_span(line_span, ignore_empty_chars=ignore_empty_chars, split_merged_chars=split_merged_chars)
        if line_string.strip() == "":   continue

        if normalize_variants:
            for bf,af in dc_constants.char_mappings:
                line_string = line_string.replace(bf,af)

        # Line has been built up. Now create bd elements ...
        line_bd_ids = mmax2_disc.get_basedata().add_elements_from_string(line_string, isolate_numbers=separate_numbers)
        # ... and re-render line.
        rendered, _, _, mapping = mmax2_disc.get_basedata().render_string(for_ids=[line_bd_ids], mapping=True)
        last_id = None
        current_ocr_span=[] # Collect (index, id) tuples of spans mapped to the same ocr word
        current_bd_span=[]
        # Go over all positions in ocr string
        for i in sorted(stringindex2wordid.keys()):
            if last_id and stringindex2wordid[i] != last_id:
                # Current span ends. Collect bd_ids mapped to this ocr_word, in case an ocr token yielded more than one bd element.
                for (j,_) in current_ocr_span:
                    try:
                        # Store each bd_id only once
                        if mapping[j] not in current_bd_span:   current_bd_span.append(mapping[j])
                    except KeyError:    pass
                # Add ocr_word markable
                if debug: print(current_bd_span)
                was_added, m = mmax2_disc.get_level("ocr_words").add_markable([current_bd_span], allow_duplicate_spans=False)
                if debug: print(m.to_xml())
                assert was_added
                # Set attribute to ocr word. There is a 1-to-1 mapping between ocr_word markables and title attributes
                # bbox 588 827 622 837; x_wconf 96
                # Use attributes from last_id word
                bbox=wordid2title[last_id].split(";")[0][5:]
                conf=wordid2title[last_id].split(";")[1][9:]
                m.update_attributes({'word_bbox':bbox,
                                     'word_conf':str(conf),
                                     'char_confs':wordid2charconfs[last_id],
                                     'worst_char_conf':wordid2worstcharconf[last_id], 
                                     'char_bboxes':wordid2charbboxes[last_id],
                                     'image':img_name, 
                                     'page_no':str(page_no)})
                current_ocr_span=[]
                current_bd_span=[]
            # Collect in current ocr span
            current_ocr_span.append((i,stringindex2wordid[i]))
            last_id = stringindex2wordid[i]

        # All string positions in line_span have been processed
        # Create markable for last pending ocr_span
        for (j,_) in current_ocr_span:
            try:
                if mapping[j] not in current_bd_span:
                    current_bd_span.append(mapping[j])
            except KeyError:
                pass
        was_added, m = mmax2_disc.get_level("ocr_words").add_markable([current_bd_span], allow_duplicate_spans=False)
        assert was_added
        # Here, use atts from current id (last val of i)
        bbox=wordid2title[stringindex2wordid[i]].split(";")[0][5:]
        conf=wordid2title[stringindex2wordid[i]].split(";")[1][9:]            
        m.update_attributes({'word_bbox'        :bbox,
                             'word_conf'        :str(conf),
                             'char_confs'       :wordid2charconfs[stringindex2wordid[i]],
                             'worst_char_conf'  :wordid2worstcharconf[stringindex2wordid[i]], 
                             'char_bboxes'      :wordid2charbboxes[stringindex2wordid[i]], 
                             'image'            :img_name, 
                             'page_no'          :str(page_no)})

        was_added, m = mmax2_disc.get_level("ocr_lines").add_markable([line_bd_ids], allow_duplicate_spans=False)
        assert was_added
        bbox=line_span['title'].split(";")[0][5:]
        m.update_attributes({'line_bbox':bbox , 'image':img_name, 'page_no':str(page_no)})
    return



def analyse_hocr_line_span(line_span, ignore_empty_chars=False, split_merged_chars=False):
    line_string = ""        
    stringindex2wordid, wordid2title, wordid2charconfs, wordid2charbboxes, wordid2worstcharconf = {}, {}, {}, {}, {}
    for word_span in [s for s in line_span.descendants if s.name == 'span' and 'ocrx_word' in s['class']]:
        word_text, char_confs, char_bboxes="","",""
        worst_char_conf = 100
        for c in [d for d in word_span.descendants if d.name=='span' and 'ocrx_cinfo' in d['class']]:
            # Build up word from single chars
            if ignore_empty_chars and len(c.text.strip())==0:
                continue
            if split_merged_chars:
                if len(c.text)==1:
                    # Nothing to split
                    word_text=word_text+c.text
                    # Collect char level confs normally
                    char_conf       =   int(c['title'].split(" ")[-1].split(".")[0])
                    if char_conf < worst_char_conf:
                        worst_char_conf=char_conf
                    char_confs      =   char_confs  + str(char_conf)+","
                    char_bboxes     =   char_bboxes + c['title'].split(";")[0][9:]+","

                elif len(c.text)==2:
                    # Collect both chars for final string
                    word_text=word_text+c.text
                    # Get conf of merged char, which will be used for both after splitting
                    char_conf       =   int(c['title'].split(" ")[-1].split(".")[0])
                    if char_conf < worst_char_conf:
                        worst_char_conf=char_conf
                    # Add twice to char_conf xml string
                    char_confs      =   char_confs + str(char_conf) + "," + str(char_conf) + ","

                    # Get bbox containing both chars
                    box_l, box_t, box_r, box_b = map(int,c['title'].split(";")[0][9:].split(' '))
                    box_width = box_r-box_l
                    # left_box_l = box_l
                    left_box_r = box_l + int(box_width/2)
                    right_box_l = left_box_r+1
                    # Add left box
                    char_bboxes = char_bboxes + str(box_l)      +" "+str(box_t) + " "+ str(left_box_r) + " " + str(box_b) + ","
                    char_bboxes = char_bboxes + str(right_box_l)+" "+str(box_t) + " "+ str(box_r)      + " " + str(box_b) + ","
                else:
                    print(c.text, "is more than **two** chars, cannot split ...", file=sys.stderr)
            else:
                # No special treatment for ligatures, this will produce recall errors for certain oem modes
                try:
                    assert len(c.text)==1
                    word_text=word_text+c.text                
                except AssertionError:
                    # print(c.text, "is more than one char, trimming ...")
                    word_text=word_text+c.text[0]

                # Collect char level confs
                char_conf       =   int(c['title'].split(" ")[-1].split(".")[0])
                if char_conf < worst_char_conf:
                    worst_char_conf=char_conf
                char_confs      =   char_confs  + str(char_conf)+","
                char_bboxes     =   char_bboxes + c['title'].split(";")[0][9:]+","

        # word has been built up
        wordid2charconfs[word_span['id']]               = char_confs[0:-1]  # Cut off last comma
        wordid2charbboxes[word_span['id']]              = char_bboxes[0:-1]  # Cut off last comma
        wordid2worstcharconf[word_span['id']]           = str(worst_char_conf)
        for i in range(len(word_text)):
            # Map org string pos to word_id
            stringindex2wordid[len(line_string)+i+1]    = word_span['id']  # Add one for leading space
            wordid2title[word_span['id']]               = word_span['title']
        # Build line rep with standard space-based separators, to be used as input to add_elements_from_string method
        line_string=line_string+" "+word_text
    return line_string, stringindex2wordid, wordid2title, wordid2charconfs, wordid2worstcharconf, wordid2charbboxes

def get_chunks(l, n):
    for i in range(0, n):
        yield l[i::n]

def decolor_image(page_img_path, grey_thresh=50, black_thresh=100):
    page_img_path = os.path.realpath(page_img_path)
    page_img = cv2.cvtColor(cv2.imread(page_img_path), cv2.COLOR_BGR2RGB)
    page_img_height, page_img_width, _ = page_img.shape    
    for h in range(page_img_height):
        for w in range(page_img_width):
            [b,g,r]=map(int,page_img[h,w])
            # Set colored (non-grey) pixels to white
            if (abs(b-g)>grey_thresh or abs(g-r)>grey_thresh or abs(b-r)>grey_thresh):
                if (b+g+r)/3 > black_thresh:# Color must have a minimum "lightness", to prevent black from being blotted out
                    page_img[h,w,]=255
    pathlabel="decol_gt"+str(grey_thresh)+"_bt"+str(black_thresh)
    if not os.path.exists(str(Path(page_img_path).parent)+os.path.sep+pathlabel+os.path.sep):
        os.mkdir(str(Path(page_img_path).parent)+os.path.sep+pathlabel+os.path.sep)
    decol_png_file = str(Path(page_img_path).parent)+os.path.sep+pathlabel+os.path.sep+os.path.basename(page_img_path)
    cv2.imwrite(decol_png_file, cv2.cvtColor(page_img,cv2.COLOR_BGR2GRAY))
    return decol_png_file

def get_predominant_colors(rgb_img, ignore_black=True, verbose=False):
    rgb_img_height, rgb_img_width, _ = rgb_img.shape
    cols = sorted(Image.fromarray(np.uint8(rgb_img)).convert('RGB').getcolors(maxcolors=rgb_img_height*rgb_img_width), key=itemgetter(0), reverse=True)
    for idx in range(10):
        if not ignore_black or cols[idx][1]!=(0,0,0):
            return [list(cols[idx][1])]
    return None
