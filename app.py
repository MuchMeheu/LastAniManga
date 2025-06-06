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

STYLE_CONFIG = {
    "image_width_activity": 340,
    "image_height_activity": 110,
    "image_width_goal": 400,     
    "image_height_goal": 100,

    "fallback_background_color": (30, 33, 38),
    "text_color_title": (240, 240, 245),
    "text_color_details": (200, 205, 215),
    "accent_color": (100, 190, 255),
    
    "cover_image_size": (80, 115), 
    "cover_corner_radius": 6,
    
    "padding": 15,
    "font_title_name": "Montserrat-Bold.ttf",
    "font_details_name": "OpenSans-Regular.ttf",
    
    "font_size_title_activity": 18, 
    "font_size_details_activity": 13,

    "font_size_title_goal": 20,
    "font_size_details_goal": 16,

    "text_overlay_color": (20, 22, 25, 200),
    "text_overlay_padding": 10,
    "text_overlay_corner_radius": 5,

    "progress_bar_bg_color": (70, 75, 85),   
    "progress_bar_fill_color": (100, 190, 255),
    "progress_bar_height": 20,              
    "progress_bar_corner_radius": 8,         

    "line_spacing_title_details": 6,
    "line_spacing_details": 4,
    "request_timeout": 20,
    "anime_goal_total": 50 
}

try:
    FONT_TITLE_ACTIVITY = ImageFont.truetype(STYLE_CONFIG["font_title_name"], STYLE_CONFIG["font_size_title_activity"])
    FONT_DETAILS_ACTIVITY = ImageFont.truetype(STYLE_CONFIG["font_details_name"], STYLE_CONFIG["font_size_details_activity"])
    FONT_TITLE_GOAL = ImageFont.truetype(STYLE_CONFIG["font_title_name"], STYLE_CONFIG["font_size_title_goal"])
    FONT_DETAILS_GOAL = ImageFont.truetype(STYLE_CONFIG["font_details_name"], STYLE_CONFIG["font_size_details_goal"])
    print(f"Custom fonts ('{STYLE_CONFIG['font_title_name']}', '{STYLE_CONFIG['font_details_name']}') loaded successfully.")
except IOError:
    print(f"!!! CUSTOM FONTS NOT FOUND. Using fallback. Place '{STYLE_CONFIG['font_title_name']}' and '{STYLE_CONFIG['font_details_name']}' in the script directory. !!!")
    try:
        FONT_TITLE_ACTIVITY = ImageFont.truetype("arial.ttf", STYLE_CONFIG["font_size_title_activity"])
        FONT_DETAILS_ACTIVITY = ImageFont.truetype("arial.ttf", STYLE_CONFIG["font_size_details_activity"])
        FONT_TITLE_GOAL = ImageFont.truetype("arial.ttf", STYLE_CONFIG["font_size_title_goal"])
        FONT_DETAILS_GOAL = ImageFont.truetype("arial.ttf", STYLE_CONFIG["font_size_details_goal"])
        print("Fallback to system 'arial.ttf' successful.")
    except IOError:
        print("System 'arial.ttf' not found. Using most basic PIL default font (size will not be accurate).")
        FONT_TITLE_ACTIVITY = FONT_TITLE_GOAL = ImageFont.load_default()
        FONT_DETAILS_ACTIVITY = FONT_DETAILS_GOAL = ImageFont.load_default()

def add_rounded_corners(im, rad):
    mask = Image.new('L', im.size, 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle((0, 0) + im.size, radius=rad, fill=255)
    im.putalpha(mask)
    return im

def crop_to_aspect(image, aspect_w, aspect_h):
    img_w, img_h = image.size
    target_aspect = aspect_w / aspect_h
    img_aspect = img_w / img_h
    if img_aspect > target_aspect:
        new_w = int(target_aspect * img_h)
        offset = (img_w - new_w) // 2
        image = image.crop((offset, 0, offset + new_w, img_h))
    elif img_aspect < target_aspect:
        new_h = int(img_w / target_aspect)
        offset = (img_h - new_h) // 2
        image = image.crop((0, offset, img_w, offset + new_h))
    return image

def get_last_updated_media_for_activity(media_type="ANIME"):
    print(f"\n[{time.strftime('%H:%M:%S')}] [get_last_updated_media_for_activity - {media_type}] Function called.")
    query = '''
    query ($userName: String, $type: MediaType, $sort: [MediaListSort]) {
        MediaListCollection(userName: $userName, type: $type, sort: $sort, forceSingleCompletedList: true) {
            lists {
                name
                entries {
                    updatedAt
                    progress
                    media {
                        id
                        title { romaji english }
                        coverImage { large }
                        bannerImage
                        type format
                    }
                }
            }
        }
    }
    '''
    variables = {'userName': ANILIST_USERNAME, 'type': media_type, 'sort': 'UPDATED_TIME_DESC'}
    headers = {'Authorization': f'Bearer {ANILIST_TOKEN}', 'Content-Type': 'application/json', 'Accept': 'application/json'}
    print(f"[{time.strftime('%H:%M:%S')}] [get_last_updated_media_for_activity - {media_type}] Attempting to fetch data for {ANILIST_USERNAME}...")
    try:
        response = requests.post(ANILIST_API_URL, json={'query': query, 'variables': variables}, headers=headers, timeout=STYLE_CONFIG["request_timeout"])
        print(f"[{time.strftime('%H:%M:%S')}] [get_last_updated_media_for_activity - {media_type}] Anilist API response status: {response.status_code}")
        content_type = response.headers.get('Content-Type', '')
        if 'application/json' not in content_type:
            print(f"[{time.strftime('%H:%M:%S')}] [get_last_updated_media_for_activity - {media_type}] !!! Anilist API not JSON. CT: {content_type}. Text: {response.text[:200]}...")
            response.raise_for_status(); return None
        response.raise_for_status()
        data = response.json()
        print(f"[{time.strftime('%H:%M:%S')}] [get_last_updated_media_for_activity - {media_type}] Anilist API data received.")
    except Exception as e:
        print(f"[{time.strftime('%H:%M:%S')}] [get_last_updated_media_for_activity - {media_type}] !!! Exception during API/JSON: {e}"); return None

    all_entries = []
    if data.get('data') and data['data'].get('MediaListCollection') and data['data']['MediaListCollection'].get('lists'):
        for media_list in data['data']['MediaListCollection']['lists']:
            if media_list and media_list.get('entries'): all_entries.extend(media_list['entries'])
        print(f"[{time.strftime('%H:%M:%S')}] [get_last_updated_media_for_activity - {media_type}] Processed {len(all_entries)} potential entries.")
    else: print(f"[{time.strftime('%H:%M:%S')}] [get_last_updated_media_for_activity - {media_type}] Anilist API response structure not as expected or no lists. Data: {str(data)[:200]}"); return None
    if not all_entries: print(f"[{time.strftime('%H:%M:%S')}] [get_last_updated_media_for_activity - {media_type}] No entries found."); return None
    all_entries.sort(key=lambda x: x.get('updatedAt', 0), reverse=True)
    selected_entry = all_entries[0]
    if selected_entry.get('media') and selected_entry['media'].get('title'): print(f"[{time.strftime('%H:%M:%S')}] [get_last_updated_media_for_activity - {media_type}] Most recent: {selected_entry['media']['title'].get('romaji', 'N/A')}")
    return selected_entry

def generate_activity_image(media_entry, media_type_for_log="MEDIA"):
    cfg = STYLE_CONFIG
    print(f"\n[{time.strftime('%H:%M:%S')}] [generate_activity_image - {media_type_for_log}] Function called.")
    
    img_width = cfg["image_width_activity"]
    img_height = cfg["image_height_activity"]

    base_image = None
    media = media_entry.get('media') if media_entry else None
    banner_url = media.get('bannerImage') if media else None

    if banner_url:
        print(f"[{time.strftime('%H:%M:%S')}] [generate_activity_image - {media_type_for_log}] Attempting to download banner: {banner_url}")
        try:
            banner_response = requests.get(banner_url, stream=True, timeout=cfg["request_timeout"])
            banner_response.raise_for_status()
            banner_img_data = BytesIO(banner_response.content)
            banner_image_raw = Image.open(banner_img_data).convert("RGBA")
            cropped_banner = crop_to_aspect(banner_image_raw, img_width, img_height)
            base_image = cropped_banner.resize((img_width, img_height), Image.Resampling.LANCZOS)
        except Exception as e: print(f"[{time.strftime('%H:%M:%S')}] [generate_activity_image - {media_type_for_log}] !!! Error with banner: {e}. Falling back."); base_image = None
    if base_image is None: base_image = Image.new('RGBA', (img_width, img_height), color=cfg["fallback_background_color"] + (255,))
    
    final_image = base_image.convert("RGBA")
    draw = ImageDraw.Draw(final_image)
    
    text_area_overlay_img = Image.new('RGBA', final_image.size, (0,0,0,0))
    draw_text_overlay = ImageDraw.Draw(text_area_overlay_img)
    text_scrim_x0 = cfg["padding"] + cfg["cover_image_size"][0] + cfg["padding"]
    text_scrim_y0 = cfg["padding"]
    text_scrim_width = img_width - text_scrim_x0 - cfg["padding"]
    text_scrim_height = img_height - 2 * cfg["padding"]
    
    if banner_url:
        draw_text_overlay.rounded_rectangle(
            (text_scrim_x0 - cfg["text_overlay_padding"], text_scrim_y0 - cfg["text_overlay_padding"], 
             text_scrim_x0 + text_scrim_width + cfg["text_overlay_padding"], text_scrim_y0 + text_scrim_height + cfg["text_overlay_padding"]),
            radius=cfg["text_overlay_corner_radius"], fill=cfg["text_overlay_color"])
        final_image = Image.alpha_composite(final_image, text_area_overlay_img)
        draw = ImageDraw.Draw(final_image)

    if not media:
        error_text = f"No recent {media_type_for_log.lower()} activity."
        text_bbox = draw.textbbox((0,0), error_text, font=FONT_TITLE_ACTIVITY)
        text_width = text_bbox[2] - text_bbox[0]; text_height = text_bbox[3] - text_bbox[1]
        draw.text(((img_width - text_width) / 2, (img_height - text_height) / 2), error_text, font=FONT_TITLE_ACTIVITY, fill=cfg["text_color_title"])
        return final_image

    cover_url = media.get('coverImage', {}).get('large')
    cover_x = cfg["padding"] + cfg["text_overlay_padding"] 
    cover_y = (img_height - cfg["cover_image_size"][1]) // 2
    if cover_url:
        try:
            cover_response = requests.get(cover_url, stream=True, timeout=cfg["request_timeout"])
            cover_response.raise_for_status()
            cover_img_data = BytesIO(cover_response.content)
            cover_img = Image.open(cover_img_data).convert("RGBA")
            cover_img = cover_img.resize(cfg["cover_image_size"], Image.Resampling.LANCZOS)
            cover_img = add_rounded_corners(cover_img, cfg["cover_corner_radius"])
            final_image.paste(cover_img, (cover_x, cover_y), cover_img)
        except Exception as e: print(f"!!! Error with cover: {e}"); draw.rectangle((cover_x, cover_y, cover_x + cfg["cover_image_size"][0], cover_y + cfg["cover_image_size"][1]), fill=(50,50,60,200))
    else: draw.rectangle((cover_x, cover_y, cover_x + cfg["cover_image_size"][0], cover_y + cfg["cover_image_size"][1]), fill=(50,50,60,200))
    title_obj = media.get('title', {}); title = title_obj.get('english') or title_obj.get('romaji') or "Untitled"
    progress = media_entry.get('progress', 0); progress_text_val = str(progress)
    progress_label = "Ep: " if media.get('type') == 'ANIME' else "Ch: "
    media_format_text = f"Format: {media.get('format', 'N/A')}"
    text_x_start = text_scrim_x0; current_y = text_scrim_y0 + cfg["text_overlay_padding"]
    display_title = title; max_text_width_for_title = text_scrim_width - (2 * cfg["text_overlay_padding"])
    title_bbox = draw.textbbox((0,0), display_title, font=FONT_TITLE_ACTIVITY); title_width = title_bbox[2] - title_bbox[0]
    while title_width > max_text_width_for_title and len(display_title) > 15:
        display_title = display_title[:-4] + "..."; title_bbox = draw.textbbox((0,0), display_title, font=FONT_TITLE_ACTIVITY); title_width = title_bbox[2] - title_bbox[0]
    draw.text((text_x_start, current_y), display_title, font=FONT_TITLE_ACTIVITY, fill=cfg["text_color_title"])
    current_y += (title_bbox[3] - title_bbox[1]) + cfg["line_spacing_title_details"]
    draw.text((text_x_start, current_y), progress_label, font=FONT_DETAILS_ACTIVITY, fill=cfg["text_color_details"])
    label_bbox = draw.textbbox((0,0), progress_label, font=FONT_DETAILS_ACTIVITY); label_width = label_bbox[2] - label_bbox[0]
    draw.text((text_x_start + label_width, current_y), progress_text_val, font=FONT_DETAILS_ACTIVITY, fill=cfg["accent_color"])
    progress_full_bbox = draw.textbbox((0,0), progress_label + progress_text_val, font=FONT_DETAILS_ACTIVITY)
    current_y += (progress_full_bbox[3] - progress_full_bbox[1]) + cfg["line_spacing_details"]
    draw.text((text_x_start, current_y), media_format_text, font=FONT_DETAILS_ACTIVITY, fill=cfg["text_color_details"])
    
    print(f"[{time.strftime('%H:%M:%S')}] [generate_activity_image - {media_type_for_log}] Image generation complete.")
    return final_image

def get_completed_anime_count_for_goal():
    print(f"\n[{time.strftime('%H:%M:%S')}] [get_completed_anime_count_for_goal] Fetching completed anime count for {ANILIST_USERNAME}...")
    query = """query ($userName: String) { User(name: $userName) { statistics { anime { statuses { status count } } } } }"""
    variables = {'userName': ANILIST_USERNAME}
    headers = {'Authorization': f'Bearer {ANILIST_TOKEN}', 'Content-Type': 'application/json', 'Accept': 'application/json'}
    try:
        response = requests.post(ANILIST_API_URL, json={'query': query, 'variables': variables}, headers=headers, timeout=STYLE_CONFIG["request_timeout"])
        response.raise_for_status(); data = response.json()
        if data.get('data') and data['data'].get('User') and data['data']['User'].get('statistics') and \
           data['data']['User']['statistics'].get('anime') and data['data']['User']['statistics']['anime'].get('statuses'):
            statuses = data['data']['User']['statistics']['anime']['statuses']
            for status_entry in statuses:
                if status_entry.get('status') == 'COMPLETED': return status_entry.get('count', 0)
            return 0 
        else: print(f"Unexpected API structure. Data: {str(data)[:200]}"); return 0
    except Exception as e: print(f"!!! Error fetching completed count: {e}"); print(traceback.format_exc()); return -1

def draw_progress_bar_for_goal(draw_context, x, y, width, height, progress_percentage, bg_color, fill_color, corner_radius):
    progress_percentage = max(0, min(1, progress_percentage))
    draw_context.rounded_rectangle((x, y, x + width, y + height), radius=corner_radius, fill=bg_color)
    if progress_percentage > 0:
        fill_width = width * progress_percentage
        draw_context.rounded_rectangle((x, y, x + fill_width, y + height), radius=corner_radius, fill=fill_color)

def generate_goal_progress_image_combined():
    cfg = STYLE_CONFIG
    print(f"[{time.strftime('%H:%M:%S')}] [generate_goal_progress_image_combined] Starting image generation...")
    img_width = cfg["image_width_goal"]
    img_height = cfg["image_height_goal"]
    img = Image.new('RGB', (img_width, img_height), color=cfg["fallback_background_color"])
    draw = ImageDraw.Draw(img)
    completed_count = get_completed_anime_count_for_goal()
    goal_total = cfg["anime_goal_total"]
    if completed_count == -1:
        error_text = "Error fetching data"
        text_bbox = draw.textbbox((0,0), error_text, font=FONT_TITLE_GOAL); text_width = text_bbox[2]-text_bbox[0]; text_height=text_bbox[3]-text_bbox[1]
        draw.text(((img_width - text_width) / 2, (img_height - text_height) / 2), error_text, font=FONT_TITLE_GOAL, fill=cfg["text_color_title"])
        return img
    title_text = "Anime Completion Goal"; title_bbox = draw.textbbox((0,0), title_text, font=FONT_TITLE_GOAL); title_width=title_bbox[2]-title_bbox[0]
    title_x = (img_width - title_width) / 2; title_y = cfg["padding"]
    draw.text((title_x, title_y), title_text, font=FONT_TITLE_GOAL, fill=cfg["text_color_title"])
    current_y = title_y + (title_bbox[3] - title_bbox[1]) + cfg["padding"] / 2
    bar_width = img_width - (2 * cfg["padding"]); bar_x = cfg["padding"]; bar_y = current_y
    progress_percent = completed_count / goal_total if goal_total > 0 else (1 if completed_count > 0 else 0)
    draw_progress_bar_for_goal(draw, bar_x, bar_y, bar_width, cfg["progress_bar_height"], progress_percent, cfg["progress_bar_bg_color"], cfg["progress_bar_fill_color"], cfg["progress_bar_corner_radius"])
    current_y += cfg["progress_bar_height"] + cfg["padding"] / 2
    progress_text_str = f"{completed_count} / {goal_total} Completed"
    if completed_count >= goal_total and goal_total > 0: progress_text_str = f"Goal Achieved! ({completed_count}/{goal_total})"
    progress_text_bbox = draw.textbbox((0,0), progress_text_str, font=FONT_DETAILS_GOAL); progress_text_width = progress_text_bbox[2]-progress_text_bbox[0]
    progress_text_x = (img_width - progress_text_width) / 2; progress_text_y = current_y
    if progress_text_y + (progress_text_bbox[3] - progress_text_bbox[1]) > img_height - cfg["padding"]: progress_text_y = img_height - cfg["padding"] - (progress_text_bbox[3] - progress_text_bbox[1])
    draw.text((progress_text_x, progress_text_y), progress_text_str, font=FONT_DETAILS_GOAL, fill=cfg["text_color_details"])
    print(f"[{time.strftime('%H:%M:%S')}] [generate_goal_progress_image_combined] Image generation complete.")
    return img

def _create_image_response(image_object):
    img_io = BytesIO()
    image_object.save(img_io, 'PNG')
    img_io.seek(0)
    
    response = make_response(send_file(img_io, mimetype='image/png'))
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate, public, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

@app.route('/')
def root_message():
    print(f"\n[{time.strftime('%H:%M:%S')}] Root path '/' accessed.")
    return "Anilist Image Generator is running. Endpoints: /last_anime.png, /last_manga.png, /anime_goal_progress.png"

@app.route('/last_anime.png')
def last_anime_image_route():
    print(f"\n[{time.strftime('%H:%M:%S')}] Route /last_anime.png accessed.")
    try:
        latest_anime = get_last_updated_media_for_activity(media_type="ANIME")
        img = generate_activity_image(latest_anime, media_type_for_log="ANIME")
        print(f"[{time.strftime('%H:%M:%S')}] Sending ANIME image with no-cache headers.")
        return _create_image_response(img)
    except Exception as e:
        print(f"[{time.strftime('%H:%M:%S')}] !!! Unhandled error in /last_anime.png: {e}")
        print(traceback.format_exc())
        abort(500, description="Error generating anime image")

@app.route('/last_manga.png')
def last_manga_image_route():
    print(f"\n[{time.strftime('%H:%M:%S')}] Route /last_manga.png accessed.")
    try:
        latest_manga = get_last_updated_media_for_activity(media_type="MANGA")
        img = generate_activity_image(latest_manga, media_type_for_log="MANGA")
        print(f"[{time.strftime('%H:%M:%S')}] Sending MANGA image with no-cache headers.")
        return _create_image_response(img)
    except Exception as e:
        print(f"[{time.strftime('%H:%M:%S')}] !!! Unhandled error in /last_manga.png: {e}")
        print(traceback.format_exc())
        abort(500, description="Error generating manga image")

@app.route('/anime_goal_progress.png')
def anime_goal_progress_image_route():
    print(f"\n[{time.strftime('%H:%M:%S')}] Route /anime_goal_progress.png accessed.")
    try:
        img = generate_goal_progress_image_combined()
        print(f"[{time.strftime('%H:%M:%S')}] Sending GOAL PROGRESS image with no-cache headers.")
        return _create_image_response(img)
    except Exception as e:
        print(f"[{time.strftime('%H:%M:%S')}] !!! Unhandled error in /anime_goal_progress.png: {e}")
        print(traceback.format_exc())
        abort(500, description="Error generating goal progress image")


if __name__ == '__main__':
    if not ANILIST_USERNAME: print("CRITICAL Error: ANILIST_USERNAME not set in .env.")
    if not ANILIST_TOKEN: print("CRITICAL Error: ANILIST_TOKEN not set in .env.")
    
    if ANILIST_USERNAME and ANILIST_TOKEN:
        print(f"[{time.strftime('%H:%M:%S')}] Starting Flask server for user: {ANILIST_USERNAME}")
        app.run(debug=True, port=5000)
    else:
        print(f"[{time.strftime('%H:%M:%S')}] Flask server NOT started due to missing .env variables.")