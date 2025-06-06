import os
import requests
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from io import BytesIO
from flask import Flask, send_file, abort, make_response
from dotenv import load_dotenv
import time
import traceback

load_dotenv()

app = Flask(__name__)

ANILIST_USERNAME = os.getenv("ANILIST_USERNAME")
ANILIST_TOKEN = os.getenv("ANILIST_TOKEN")
ANILIST_API_URL = 'https://graphql.anilist.co'

ORANGE_ACCENT = (252, 146, 46) 
DESCRIPTION_BOX_BG = (34, 39, 49) 
BRIGHT_TEXT = (235, 235, 240)
MEDIUM_GREY_TEXT = (180, 185, 190)
LIGHT_GREY_TEXT = (200, 205, 210)


STYLE_CONFIG = {
    "image_width_activity": 340,
    "image_height_activity": 100,
    "fallback_background_color": (30, 33, 38),
    "text_color_title_activity": BRIGHT_TEXT,
    "text_color_details_activity": MEDIUM_GREY_TEXT,
    "accent_color_activity": ORANGE_ACCENT, 
    "cover_image_size_activity": (70, 95), 
    "cover_corner_radius_activity": 5,
    "font_title_name": "Montserrat-Bold.ttf",
    "font_details_name": "OpenSans-Regular.ttf",
    "font_size_title_activity": 16,
    "font_size_details_activity": 12,
    "text_overlay_color_activity": (15, 17, 20, 235),
    "text_overlay_padding_activity": 8,
    "text_overlay_corner_radius_activity": 4,
    "banner_blur_radius": 1.5, 
    "banner_dim_color": (0, 0, 0, 120),
    "image_width_goal": 400,
    "image_height_goal": 90, 
    "background_color_goal": DESCRIPTION_BOX_BG, 
    "text_color_title_goal": BRIGHT_TEXT,
    "text_color_details_goal": LIGHT_GREY_TEXT,
    "font_size_title_goal": 18,
    "font_size_details_goal": 14,
    "progress_bar_bg_color": (60, 65, 75),
    "progress_bar_fill_color": ORANGE_ACCENT, 
    "progress_bar_height": 18,
    "progress_bar_corner_radius": 7,
    "anime_goal_total": 250,
    "image_width_completed": 420, 
    "image_height_completed": 110, 
    "background_completed_color": DESCRIPTION_BOX_BG,
    "background_dim_overlay_completed": (0, 0, 0, 35),
    "text_color_title_completed": BRIGHT_TEXT,
    "text_color_subtitle_completed": ORANGE_ACCENT, 
    "text_color_score_value_completed": BRIGHT_TEXT,
    "text_color_score_suffix_completed": LIGHT_GREY_TEXT,
    "cover_completed_size": (70, 100), 
    "cover_completed_corner_radius": 5,
    "font_size_title_completed": 17, 
    "font_size_subtitle_completed": 12,
    "font_size_score_value_completed": 26, 
    "font_size_score_suffix_completed": 13,
    "padding_completed": 12, 
    "padding_general": 15, 
    "line_spacing_title_details": 4, 
    "line_spacing_details": 2,
    "request_timeout": 20,
    "title_max_lines": 2,
}

pil_default_font = ImageFont.load_default()
FONT_TITLE_ACTIVITY, FONT_DETAILS_ACTIVITY = pil_default_font, pil_default_font
FONT_TITLE_GOAL, FONT_DETAILS_GOAL = pil_default_font, pil_default_font
FONT_TITLE_COMPLETED, FONT_SUBTITLE_COMPLETED = pil_default_font, pil_default_font
FONT_SCORE_VALUE_COMPLETED, FONT_SCORE_SUFFIX_COMPLETED = pil_default_font, pil_default_font

custom_font_title_path = STYLE_CONFIG["font_title_name"]
custom_font_details_path = STYLE_CONFIG["font_details_name"]
custom_fonts_loaded_successfully = False
try:
    FONT_TITLE_ACTIVITY = ImageFont.truetype(custom_font_title_path, STYLE_CONFIG["font_size_title_activity"])
    FONT_DETAILS_ACTIVITY = ImageFont.truetype(custom_font_details_path, STYLE_CONFIG["font_size_details_activity"])
    FONT_TITLE_GOAL = ImageFont.truetype(custom_font_title_path, STYLE_CONFIG["font_size_title_goal"])
    FONT_DETAILS_GOAL = ImageFont.truetype(custom_font_details_path, STYLE_CONFIG["font_size_details_goal"])
    FONT_TITLE_COMPLETED = ImageFont.truetype(custom_font_title_path, STYLE_CONFIG["font_size_title_completed"])
    FONT_SUBTITLE_COMPLETED = ImageFont.truetype(custom_font_details_path, STYLE_CONFIG["font_size_subtitle_completed"])
    FONT_SCORE_VALUE_COMPLETED = ImageFont.truetype(custom_font_title_path, STYLE_CONFIG["font_size_score_value_completed"])
    FONT_SCORE_SUFFIX_COMPLETED = ImageFont.truetype(custom_font_details_path, STYLE_CONFIG["font_size_score_suffix_completed"])
    custom_fonts_loaded_successfully = True
except IOError:
    pass
if not custom_fonts_loaded_successfully:
    try:
        def get_arial_font(size, is_bold=False):
            fn = "arialbd.ttf" if is_bold else "arial.ttf"; return ImageFont.truetype(fn, size)
        FONT_TITLE_ACTIVITY = get_arial_font(STYLE_CONFIG["font_size_title_activity"], True)
        FONT_DETAILS_ACTIVITY = get_arial_font(STYLE_CONFIG["font_size_details_activity"])
    except IOError: pass

def add_rounded_corners(im, rad):
    mask = Image.new('L', im.size, 0); draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle((0, 0) + im.size, radius=rad, fill=255); im.putalpha(mask); return im
def crop_to_aspect(image, aspect_w, aspect_h):
    img_w, img_h = image.size; target_aspect = aspect_w / aspect_h; img_aspect = img_w / img_h
    if img_aspect > target_aspect: new_w=int(target_aspect*img_h); off=(img_w-new_w)//2; image=image.crop((off,0,off+new_w,img_h))
    elif img_aspect < target_aspect: new_h=int(img_w/target_aspect); off=(img_h-new_h)//2; image=image.crop((0,off,img_w,off+new_h))
    return image
def get_anilist_data(query, variables, log_prefix="API_CALL"):
    headers = {'Authorization':f'Bearer {ANILIST_TOKEN}','Content-Type':'application/json','Accept':'application/json'}
    try:
        response = requests.post(ANILIST_API_URL,json={'query':query,'variables':variables},headers=headers,timeout=STYLE_CONFIG["request_timeout"])
        response.raise_for_status(); data=response.json(); return data
    except Exception as e: return None

def get_last_updated_media_for_activity(media_type="ANIME"):
    log_prefix = f"GLUM Activity - {media_type}"; query = '''query ($userName: String, $type: MediaType, $sort: [MediaListSort]) { MediaListCollection(userName: $userName, type: $type, sort: $sort, forceSingleCompletedList: true) { lists { name entries { updatedAt progress media { id title { romaji english } coverImage { large } bannerImage type format } } } } }'''
    variables = {'userName': ANILIST_USERNAME, 'type': media_type, 'sort': 'UPDATED_TIME_DESC'}
    data = get_anilist_data(query, variables, log_prefix);
    if not data: return None
    all_entries = []; collection = data.get('data', {}).get('MediaListCollection', {})
    if collection and collection.get('lists'):
        for lst in collection['lists']:
            if lst and lst.get('entries'): all_entries.extend(lst['entries'])
    if not all_entries: return None
    all_entries.sort(key=lambda x: x.get('updatedAt', 0), reverse=True)
    return all_entries[0]

def generate_activity_image(media_entry, media_type_for_log="MEDIA"):
    cfg = STYLE_CONFIG; w, h = cfg["image_width_activity"], cfg["image_height_activity"]; FNT_T, FNT_D = FONT_TITLE_ACTIVITY, FONT_DETAILS_ACTIVITY
    base_img = None; media = media_entry.get('media') if media_entry else None; banner_url = media.get('bannerImage') if media else None
    if banner_url:
        try:
            banner_response = requests.get(banner_url, stream=True, timeout=cfg["request_timeout"]); banner_response.raise_for_status()
            banner_raw = Image.open(BytesIO(banner_response.content)).convert("RGBA")
            cropped_banner = crop_to_aspect(banner_raw, w, h)
            resized_banner = cropped_banner.resize((w, h), Image.Resampling.LANCZOS)
            banner_dim_color = cfg.get("banner_dim_color", (0,0,0,0))
            if banner_dim_color[3] > 0:
                dim_layer_for_banner = Image.new('RGBA', resized_banner.size, (0,0,0,0))
                draw_banner_dim = ImageDraw.Draw(dim_layer_for_banner)
                draw_banner_dim.rectangle([(0,0), resized_banner.size], fill=banner_dim_color)
                base_img = Image.alpha_composite(resized_banner, dim_layer_for_banner)
            else: base_img = resized_banner
            if cfg.get("banner_blur_radius", 0) > 0: base_img = base_img.filter(ImageFilter.GaussianBlur(radius=cfg["banner_blur_radius"]))
        except Exception as e: base_img = None
    if base_img is None: base_img = Image.new('RGBA', (w, h), cfg["fallback_background_color"] + (255,))
    final_img = base_img.copy(); draw = ImageDraw.Draw(final_img)
    scrim_x0 = cfg["padding_general"] + cfg["cover_image_size_activity"][0] + cfg["padding_general"] - cfg["text_overlay_padding_activity"]
    scrim_y0 = cfg["padding_general"] - cfg["text_overlay_padding_activity"]
    scrim_w = w - scrim_x0 - cfg["padding_general"] + cfg["text_overlay_padding_activity"]
    scrim_h = h - 2 * (cfg["padding_general"] - cfg["text_overlay_padding_activity"])
    overlay_img_draw = Image.new('RGBA', final_img.size, (0,0,0,0)); draw_overlay_rect = ImageDraw.Draw(overlay_img_draw)
    draw_overlay_rect.rounded_rectangle((scrim_x0, scrim_y0, scrim_x0 + scrim_w, scrim_y0 + scrim_h), radius=cfg["text_overlay_corner_radius_activity"], fill=cfg["text_overlay_color_activity"])
    final_img = Image.alpha_composite(final_img, overlay_img_draw); draw = ImageDraw.Draw(final_img)
    if not media:
        err_txt = f"No recent {media_type_for_log.lower()} data"; bb=draw.textbbox((0,0),err_txt,font=FNT_T); tw,th=bb[2]-bb[0],bb[3]-bb[1]
        draw.text(((w-tw)/2,(h-th)/2),err_txt,font=FNT_T,fill=cfg["text_color_title_activity"]); return final_img.convert("RGB")
    cover_url = media.get('coverImage', {}).get('large'); cx,cy = cfg["padding_general"],(h-cfg["cover_image_size_activity"][1])//2
    if cover_url:
        try:
            cover_resp=requests.get(cover_url,stream=True,timeout=cfg["request_timeout"]);cover_resp.raise_for_status()
            cover_img_data=BytesIO(cover_resp.content);cover_img=Image.open(cover_img_data).convert("RGBA").resize(cfg["cover_image_size_activity"],Image.Resampling.LANCZOS)
            final_img.paste(add_rounded_corners(cover_img,cfg["cover_corner_radius_activity"]),(cx,cy),cover_img)
        except Exception as e:draw.rectangle((cx,cy,cx+cfg["cover_image_size_activity"][0],cy+cfg["cover_image_size_activity"][1]),fill=(50,50,60,200))
    else:draw.rectangle((cx,cy,cx+cfg["cover_image_size_activity"][0],cy+cfg["cover_image_size_activity"][1]),fill=(50,50,60,200))
    title=media.get('title',{}).get('english') or media.get('title',{}).get('romaji') or "Untitled";prog=media_entry.get('progress',0)
    prog_lbl="Ep: " if media.get('type')=='ANIME' else "Ch: ";fmt=f"Format: {media.get('format','N/A')}"
    txt_x=scrim_x0+cfg["text_overlay_padding_activity"];cur_y=scrim_y0+cfg["text_overlay_padding_activity"]
    max_w_title=scrim_w-2*cfg["text_overlay_padding_activity"]
    disp_title=title;bbT=draw.textbbox((0,0),disp_title,font=FNT_T);tW=bbT[2]-bbT[0]
    while tW>max_w_title and len(disp_title)>15:disp_title=disp_title[:-4]+"...";bbT=draw.textbbox((0,0),disp_title,font=FNT_T);tW=bbT[2]-bbT[0]
    draw.text((txt_x,cur_y),disp_title,font=FNT_T,fill=cfg["text_color_title_activity"]);cur_y+=(bbT[3]-bbT[1])+cfg["line_spacing_title_details"]
    draw.text((txt_x,cur_y),prog_lbl,font=FNT_D,fill=cfg["text_color_details_activity"]);bbL=draw.textbbox((0,0),prog_lbl,font=FNT_D);lW=bbL[2]-bbL[0]
    draw.text((txt_x+lW,cur_y),str(prog),font=FNT_D,fill=cfg["accent_color_activity"]);bbP=draw.textbbox((0,0),prog_lbl+str(prog),font=FNT_D);cur_y+=(bbP[3]-bbP[1])+cfg["line_spacing_details"]
    fmt_bb=draw.textbbox((0,0),fmt,font=FNT_D);fmt_h=fmt_bb[3]-fmt_bb[1]
    if cur_y+fmt_h<=scrim_y0+scrim_h-cfg["text_overlay_padding_activity"]:
        draw.text((txt_x,cur_y),fmt,font=FNT_D,fill=cfg["text_color_details_activity"])
    return final_img.convert("RGB")

def get_completed_anime_count_for_goal():
    log_prefix="GetGoalCount"; query = """query ($userName: String) { User(name: $userName) { statistics { anime { statuses { status count } } } } }"""
    variables = {'userName': ANILIST_USERNAME}; data = get_anilist_data(query, variables, log_prefix)
    if not data: return -1
    stats = data.get('data',{}).get('User',{}).get('statistics',{}).get('anime',{})
    if stats and stats.get('statuses'):
        for s_entry in stats['statuses']:
            if s_entry.get('status') == 'COMPLETED': return s_entry.get('count', 0)
    return 0
def draw_progress_bar_for_goal(draw_ctx,x,y,w,h,prog_pct,bg_c,fill_c,rad):
    prog_pct=max(0,min(1,prog_pct)); draw_ctx.rounded_rectangle((x,y,x+w,y+h),radius=rad,fill=bg_c)
    if prog_pct>0: fill_w=w*prog_pct; draw_ctx.rounded_rectangle((x,y,x+fill_w,y+h),radius=rad,fill=fill_c) if fill_w >= 2*rad else draw_ctx.rectangle((x,y, x+fill_w, y+h), fill=fill_c)
def generate_goal_progress_image_combined():
    cfg=STYLE_CONFIG; w,h=cfg["image_width_goal"],cfg["image_height_goal"]; FNT_T,FNT_D=FONT_TITLE_GOAL,FONT_DETAILS_GOAL
    img=Image.new('RGB',(w,h),color=cfg["background_color_goal"]); draw=ImageDraw.Draw(img)
    completed=get_completed_anime_count_for_goal(); goal_total=cfg["anime_goal_total"]
    if completed==-1: err_txt="Error fetching data"; bb=draw.textbbox((0,0),err_txt,font=FNT_T); tw,th=bb[2]-bb[0],bb[3]-bb[1]; draw.text(((w-tw)/2,(h-th)/2),err_txt,font=FNT_T,fill=cfg["text_color_title_goal"]); return img
    title_txt="Anime Completion Goal"; bbT=draw.textbbox((0,0),title_txt,font=FNT_T); tW=bbT[2]-bbT[0]; title_x,title_y=(w-tW)/2,cfg["padding_general"]
    draw.text((title_x,title_y),title_txt,font=FNT_T,fill=cfg["text_color_title_goal"]); cur_y=title_y+(bbT[3]-bbT[1])+cfg["padding_general"]/2
    bar_w=w-(2*cfg["padding_general"]); bar_x,bar_y=cfg["padding_general"],cur_y
    prog_pct=completed/goal_total if goal_total>0 else (1 if completed>0 else 0)
    draw_progress_bar_for_goal(draw,bar_x,bar_y,bar_w,cfg["progress_bar_height"],prog_pct,cfg["progress_bar_bg_color"],cfg["progress_bar_fill_color"],cfg["progress_bar_corner_radius"])
    cur_y+=cfg["progress_bar_height"]+cfg["padding_general"]/2
    prog_txt=f"{completed} / {goal_total} Completed";
    if completed>=goal_total and goal_total>0: prog_txt=f"Goal Achieved! ({completed}/{goal_total})"
    bbP=draw.textbbox((0,0),prog_txt,font=FNT_D); pW=bbP[2]-bbP[0]; prog_x,prog_y=(w-pW)/2,cur_y
    if prog_y+(bbP[3]-bbP[1]) > h-cfg["padding_general"]: prog_y = h-cfg["padding_general"]-(bbP[3]-bbP[1])
    draw.text((prog_x,prog_y),prog_txt,font=FNT_D,fill=cfg["text_color_details_goal"])
    return img

def get_recently_completed_anime_with_score():
    log_prefix = "GetRecentCompleted"; query = """
    query ($userName: String, $type: MediaType, $status: MediaListStatus, $sort: [MediaListSort]) {
      MediaListCollection(userName: $userName, type: $type, status: $status, sort: $sort, perChunk: 5, chunk: 1, forceSingleCompletedList: true) {
        lists { entries { score(format: POINT_100) updatedAt media { id title { romaji english } coverImage { large } type format } } } } }"""
    variables = {'userName': ANILIST_USERNAME, 'type': 'ANIME', 'status': 'COMPLETED', 'sort': 'UPDATED_TIME_DESC'}
    data = get_anilist_data(query, variables, log_prefix)
    if not data: return None
    all_entries = []; collection = data.get('data',{}).get('MediaListCollection',{})
    if collection and collection.get('lists'):
        for lst in collection['lists']:
            if lst and lst.get('entries'): all_entries.extend(lst['entries'])
    if not all_entries: return None
    all_entries.sort(key=lambda x: x.get('updatedAt',0), reverse=True) 
    if all_entries: return all_entries[0]
    else: return None

def generate_recently_completed_image(completed_entry):
    cfg = STYLE_CONFIG; w,h = cfg["image_width_completed"], cfg["image_height_completed"]
    FNT_T, FNT_SUB, FNT_SV, FNT_SS = FONT_TITLE_COMPLETED, FONT_SUBTITLE_COMPLETED, FONT_SCORE_VALUE_COMPLETED, FONT_SCORE_SUFFIX_COMPLETED
    final_img = Image.new('RGBA', (w,h), cfg["background_completed_color"]+(255,))
    draw = ImageDraw.Draw(final_img)
    if not completed_entry or not completed_entry.get('media'):
        err_txt = "No recently completed anime."; bb=draw.textbbox((0,0),err_txt,font=FNT_T); tw,th=bb[2]-bb[0],bb[3]-bb[1]; draw.text(((w-tw)/2,(h-th)/2),err_txt,font=FNT_T,fill=cfg["text_color_title_completed"]); return final_img.convert("RGB")
    media = completed_entry['media']; title_full = media.get('title',{}).get('english') or media.get('title',{}).get('romaji') or "Untitled"
    score_raw = completed_entry.get('score',0)
    score_disp_val = f"{score_raw}" if score_raw > 0 else "N/S"
    score_disp_suf = " /100" if score_raw > 0 else ""
    padding = cfg["padding_completed"]
    cx,cy = padding,(h-cfg["cover_completed_size"][1])//2
    if media.get('coverImage',{}).get('large'):
        try:
            cover_resp=requests.get(media['coverImage']['large'],stream=True,timeout=cfg["request_timeout"]);cover_resp.raise_for_status()
            cover_img_raw = Image.open(BytesIO(cover_resp.content)).convert("RGBA"); 
            cover_img = cover_img_raw.resize(cfg["cover_completed_size"],Image.Resampling.LANCZOS); 
            final_img.paste(add_rounded_corners(cover_img,cfg["cover_completed_corner_radius"]),(cx,cy),cover_img)
        except Exception as e: draw.rectangle((cx,cy,cx+cfg["cover_completed_size"][0],cy+cfg["cover_completed_size"][1]),fill=(50,50,60,200))
    else: draw.rectangle((cx,cy,cx+cfg["cover_completed_size"][0],cy+cfg["cover_completed_size"][1]),fill=(50,50,60,200))
    sval_bb = draw.textbbox((0,0), score_disp_val, font=FNT_SV); sval_w,sval_h = sval_bb[2]-sval_bb[0],sval_bb[3]-sval_bb[1]
    sval_ascent, _ = FNT_SV.getmetrics(); ssuf_w = 0
    if score_raw > 0: ssuf_bb = draw.textbbox((0,0), score_disp_suf, font=FNT_SS); ssuf_w = ssuf_bb[2]-ssuf_bb[0]; ssuf_ascent, _ = FNT_SS.getmetrics()
    score_total_w = sval_w + (ssuf_w + 3 if score_raw > 0 else 0); score_x_start = w - padding - score_total_w
    score_block_center_y = h / 2
    score_val_y = score_block_center_y - sval_ascent + (sval_ascent - sval_h) / 2 
    draw.text((score_x_start, score_val_y), score_disp_val, font=FNT_SV, fill=cfg["text_color_score_value_completed"])
    if score_raw > 0:
        score_suf_y = score_block_center_y - ssuf_ascent + (ssuf_ascent-(draw.textbbox((0,0),score_disp_suf,font=FNT_SS)[3]-draw.textbbox((0,0),score_disp_suf,font=FNT_SS)[1]))/2
        draw.text((score_x_start + sval_w + 3, score_suf_y), score_disp_suf, font=FNT_SS, fill=cfg["text_color_score_suffix_completed"])
    text_area_x_start = cx + cfg["cover_completed_size"][0] + padding
    text_area_max_width = score_x_start - text_area_x_start - padding
    lines = []; words = title_full.split(); current_line = ""
    for i, word in enumerate(words):
        test_line = current_line + (" " if current_line else "") + word
        line_bbox = draw.textbbox((0,0), test_line, font=FNT_T); line_width = line_bbox[2] - line_bbox[0]
        if line_width <= text_area_max_width: current_line = test_line
        else:
            if current_line: lines.append(current_line)
            current_line = word 
            word_bbox = draw.textbbox((0,0), current_line, font=FNT_T)
            if (word_bbox[2]-word_bbox[0]) > text_area_max_width and len(current_line.strip()) > 3:
                while (draw.textbbox((0,0), current_line + "...", font=FNT_T)[2]) > text_area_max_width and len(current_line) > 3: current_line = current_line[:-1]
                current_line = current_line + "..."; lines.append(current_line); current_line = "" ; break 
    if current_line: lines.append(current_line)
    if len(lines) > cfg["title_max_lines"]:
        lines = lines[:cfg["title_max_lines"]]
        if lines and len(lines[-1]) > 3 and not lines[-1].endswith("..."): lines[-1] = lines[-1][:-3] + "..."
    title_block_height = sum([(draw.textbbox((0,0),l,font=FNT_T)[3]-draw.textbbox((0,0),l,font=FNT_T)[1]) + (cfg["line_spacing_details"]/3 if idx < len(lines)-1 else 0) for idx,l in enumerate(lines)])
    subtitle_text = "Recently Completed"
    subtitle_bbox = draw.textbbox((0,0), subtitle_text, font=FNT_SUB); subtitle_height = subtitle_bbox[3] - subtitle_bbox[1]
    total_text_block_height = title_block_height + (cfg["line_spacing_title_details"] if lines else 0) + subtitle_height
    block_y_start = (h - total_text_block_height) / 2; 
    if block_y_start < padding: block_y_start = padding
    current_y_text = block_y_start 
    for line_idx, line_text in enumerate(lines):
        line_bbox = draw.textbbox((0,0), line_text, font=FNT_T); line_height_actual = line_bbox[3] - line_bbox[1]
        draw.text((text_area_x_start, current_y_text), line_text, font=FNT_T, fill=cfg["text_color_title_completed"])
        current_y_text += line_height_actual + (cfg["line_spacing_details"]/3 if line_idx < len(lines) -1 else 0)
    subtitle_y = current_y_text + (cfg["line_spacing_title_details"] if lines else 0)
    if subtitle_y + subtitle_height > h - padding: subtitle_y = h - padding - subtitle_height
    draw.text((text_area_x_start, subtitle_y), subtitle_text, font=FNT_SUB, fill=cfg["text_color_subtitle_completed"])
    return final_img.convert("RGB")

def _create_image_response(image_object):
    img_io=BytesIO(); image_object.save(img_io,'PNG'); img_io.seek(0)
    resp=make_response(send_file(img_io,mimetype='image/png'))
    resp.headers['Cache-Control']='no-cache,no-store,must-revalidate,public,max-age=0'; resp.headers['Pragma']='no-cache'; resp.headers['Expires']='0'
    return resp

@app.route('/')
def root_message():
    return "Anilist Image Generator. Endpoints: /last_anime.png, /last_manga.png, /anime_goal_progress.png, /recently_completed_anime.png"

@app.route('/last_anime.png')
def last_anime_image_route():
    try: latest=get_last_updated_media_for_activity("ANIME"); img=generate_activity_image(latest,"ANIME"); return _create_image_response(img)
    except Exception as e: abort(500)

@app.route('/last_manga.png')
def last_manga_image_route():
    try: latest=get_last_updated_media_for_activity("MANGA"); img=generate_activity_image(latest,"MANGA"); return _create_image_response(img)
    except Exception as e: abort(500)

@app.route('/anime_goal_progress.png')
def anime_goal_progress_image_route():
    try: img=generate_goal_progress_image_combined(); return _create_image_response(img)
    except Exception as e: abort(500)

@app.route('/recently_completed_anime.png')
def recently_completed_anime_route():
    try:
        entry = get_recently_completed_anime_with_score()
        img = generate_recently_completed_image(entry)
        return _create_image_response(img)
    except Exception as e:
        abort(500, description="Error generating recently completed anime image")

if __name__ == '__main__':
    if not ANILIST_USERNAME: pass
    if not ANILIST_TOKEN: pass
    if ANILIST_USERNAME and ANILIST_TOKEN: app.run(debug=True,port=5000, use_reloader=False)