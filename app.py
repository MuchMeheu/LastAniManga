import os
import requests
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from io import BytesIO
from flask import Flask, send_file, abort
from dotenv import load_dotenv
import time

load_dotenv()

app = Flask(__name__)

ANILIST_USERNAME = os.getenv("ANILIST_USERNAME")
ANILIST_TOKEN = os.getenv("ANILIST_TOKEN")
ANILIST_API_URL = 'https://graphql.anilist.co'

STYLE_CONFIG = {
    "image_width": 450,
    "image_height": 125,
    "fallback_background_color": (30, 33, 38),
    "text_color_title": (240, 240, 245),
    "text_color_details": (200, 205, 215),
    "accent_color": (100, 190, 255),
    "cover_image_size": (80, 115),
    "cover_corner_radius": 6,
    "padding": 15,
    "font_title_name": "Montserrat-Bold.ttf",
    "font_details_name": "OpenSans-Regular.ttf",
    "font_size_title": 22,
    "font_size_details": 15,
    "text_overlay_color": (20, 22, 25, 200),
    "text_overlay_padding": 10,
    "text_overlay_corner_radius": 5,
    "line_spacing_title_details": 7,
    "line_spacing_details": 5,
    "request_timeout": 20
}

try:
    FONT_TITLE = ImageFont.truetype(STYLE_CONFIG["font_title_name"], STYLE_CONFIG["font_size_title"])
    FONT_DETAILS = ImageFont.truetype(STYLE_CONFIG["font_details_name"], STYLE_CONFIG["font_size_details"])
    print(f"Custom fonts ('{STYLE_CONFIG['font_title_name']}', '{STYLE_CONFIG['font_details_name']}') loaded successfully.")
except IOError:
    print(f"!!! CUSTOM FONTS NOT FOUND. Using default PIL font. Place '{STYLE_CONFIG['font_title_name']}' and '{STYLE_CONFIG['font_details_name']}' in the script directory. !!!")
    FONT_TITLE = ImageFont.truetype(None, STYLE_CONFIG["font_size_title"])
    FONT_DETAILS = ImageFont.truetype(None, STYLE_CONFIG["font_size_details"])


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

def get_last_updated_media(media_type="ANIME"):
    print(f"\n[{time.strftime('%H:%M:%S')}] [get_last_updated_media - {media_type}] Function called.")
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

    print(f"[{time.strftime('%H:%M:%S')}] [get_last_updated_media - {media_type}] Attempting to fetch data for {ANILIST_USERNAME}...")
    try:
        response = requests.post(ANILIST_API_URL, json={'query': query, 'variables': variables}, headers=headers, timeout=STYLE_CONFIG["request_timeout"])
        print(f"[{time.strftime('%H:%M:%S')}] [get_last_updated_media - {media_type}] Anilist API response status: {response.status_code}")
        content_type = response.headers.get('Content-Type', '')
        if 'application/json' not in content_type:
            print(f"[{time.strftime('%H:%M:%S')}] [get_last_updated_media - {media_type}] !!! Anilist API not JSON. CT: {content_type}. Text: {response.text[:200]}...")
            response.raise_for_status()
            return None
        response.raise_for_status()
        data = response.json()
        print(f"[{time.strftime('%H:%M:%S')}] [get_last_updated_media - {media_type}] Anilist API data received.")
    except requests.exceptions.Timeout:
        print(f"[{time.strftime('%H:%M:%S')}] [get_last_updated_media - {media_type}] !!! Timeout during Anilist API call.")
        return None
    except requests.exceptions.RequestException as e:
        print(f"[{time.strftime('%H:%M:%S')}] [get_last_updated_media - {media_type}] !!! RequestException: {e}")
        return None
    except Exception as e:
        print(f"[{time.strftime('%H:%M:%S')}] [get_last_updated_media - {media_type}] !!! General Exception during API/JSON: {e}")
        return None

    all_entries = []
    if data.get('data') and data['data'].get('MediaListCollection') and data['data']['MediaListCollection'].get('lists'):
        for media_list in data['data']['MediaListCollection']['lists']:
            if media_list and media_list.get('entries'):
                 all_entries.extend(media_list['entries'])
        print(f"[{time.strftime('%H:%M:%S')}] [get_last_updated_media - {media_type}] Processed {len(all_entries)} potential entries from lists.")
    else:
        print(f"[{time.strftime('%H:%M:%S')}] [get_last_updated_media - {media_type}] Anilist API response structure not as expected or no lists found. Data: {str(data)[:200]}...")
        return None

    if not all_entries:
        print(f"[{time.strftime('%H:%M:%S')}] [get_last_updated_media - {media_type}] No entries found after processing lists.")
        return None
    
    all_entries.sort(key=lambda x: x.get('updatedAt', 0), reverse=True)
    selected_entry = all_entries[0] if all_entries else None
    
    if selected_entry and selected_entry.get('media') and selected_entry['media'].get('title'):
        print(f"[{time.strftime('%H:%M:%S')}] [get_last_updated_media - {media_type}] Most recent entry found: {selected_entry['media']['title'].get('romaji', 'N/A')}")
    elif selected_entry:
        print(f"[{time.strftime('%H:%M:%S')}] [get_last_updated_media - {media_type}] Most recent entry found, but title missing in structure.")
    else:
         print(f"[{time.strftime('%H:%M:%S')}] [get_last_updated_media - {media_type}] No valid entries after sorting.")
    return selected_entry


def generate_image(media_entry, media_type_for_log="MEDIA"):
    cfg = STYLE_CONFIG
    print(f"\n[{time.strftime('%H:%M:%S')}] [generate_image - {media_type_for_log}] Function called.")
    
    base_image = None
    media = media_entry.get('media') if media_entry else None
    banner_url = media.get('bannerImage') if media else None

    if banner_url:
        print(f"[{time.strftime('%H:%M:%S')}] [generate_image - {media_type_for_log}] Attempting to download banner: {banner_url}")
        try:
            banner_response = requests.get(banner_url, stream=True, timeout=cfg["request_timeout"])
            banner_response.raise_for_status()
            banner_img_data = BytesIO(banner_response.content)
            banner_image_raw = Image.open(banner_img_data).convert("RGBA")
            cropped_banner = crop_to_aspect(banner_image_raw, cfg["image_width"], cfg["image_height"])
            base_image = cropped_banner.resize((cfg["image_width"], cfg["image_height"]), Image.Resampling.LANCZOS)
            print(f"[{time.strftime('%H:%M:%S')}] [generate_image - {media_type_for_log}] Banner image processed.")
        except Exception as e:
            print(f"[{time.strftime('%H:%M:%S')}] [generate_image - {media_type_for_log}] !!! Error with banner: {e}. Falling back to solid color.")
            base_image = None

    if base_image is None:
        base_image = Image.new('RGBA', (cfg["image_width"], cfg["image_height"]), color=cfg["fallback_background_color"] + (255,))

    final_image = base_image.convert("RGBA")
    draw = ImageDraw.Draw(final_image)

    overlay_x0 = cfg["padding"]
    overlay_y0 = cfg["padding"]
    overlay_x1 = cfg["image_width"] - cfg["padding"]
    overlay_y1 = cfg["image_height"] - cfg["padding"]
    
    text_area_overlay_img = Image.new('RGBA', final_image.size, (0,0,0,0))
    draw_text_overlay = ImageDraw.Draw(text_area_overlay_img)
    
    text_scrim_x0 = cfg["padding"] + cfg["cover_image_size"][0] + cfg["padding"]
    text_scrim_y0 = cfg["padding"]
    text_scrim_width = cfg["image_width"] - text_scrim_x0 - cfg["padding"]
    text_scrim_height = cfg["image_height"] - 2 * cfg["padding"]
    
    if banner_url:
        draw_text_overlay.rounded_rectangle(
            (text_scrim_x0 - cfg["text_overlay_padding"], text_scrim_y0 - cfg["text_overlay_padding"], 
             text_scrim_x0 + text_scrim_width + cfg["text_overlay_padding"], text_scrim_y0 + text_scrim_height + cfg["text_overlay_padding"]),
            radius=cfg["text_overlay_corner_radius"],
            fill=cfg["text_overlay_color"]
        )
        final_image = Image.alpha_composite(final_image, text_area_overlay_img)
        draw = ImageDraw.Draw(final_image)

    if not media:
        print(f"[{time.strftime('%H:%M:%S')}] [generate_image - {media_type_for_log}] No valid media_entry, drawing fallback text.")
        error_text = f"No recent {media_type_for_log.lower()} activity."
        text_bbox = draw.textbbox((0,0), error_text, font=FONT_TITLE)
        text_width = text_bbox[2] - text_bbox[0]
        text_height = text_bbox[3] - text_bbox[1]
        draw.text(
            ((cfg["image_width"] - text_width) / 2, (cfg["image_height"] - text_height) / 2),
            error_text, font=FONT_TITLE, fill=cfg["text_color_title"]
        )
        return final_image

    cover_url = media.get('coverImage', {}).get('large')
    cover_x = cfg["padding"] + cfg["text_overlay_padding"]
    cover_y = (cfg["image_height"] - cfg["cover_image_size"][1]) // 2
    if cover_url:
        print(f"[{time.strftime('%H:%M:%S')}] [generate_image - {media_type_for_log}] Downloading cover: {cover_url}")
        try:
            cover_response = requests.get(cover_url, stream=True, timeout=cfg["request_timeout"])
            cover_response.raise_for_status()
            cover_img_data = BytesIO(cover_response.content)
            cover_img = Image.open(cover_img_data).convert("RGBA")
            cover_img = cover_img.resize(cfg["cover_image_size"], Image.Resampling.LANCZOS)
            cover_img = add_rounded_corners(cover_img, cfg["cover_corner_radius"])
            final_image.paste(cover_img, (cover_x, cover_y), cover_img)
            print(f"[{time.strftime('%H:%M:%S')}] [generate_image - {media_type_for_log}] Cover processed.")
        except Exception as e:
            print(f"[{time.strftime('%H:%M:%S')}] [generate_image - {media_type_for_log}] !!! Error with cover: {e}")
            draw.rectangle((cover_x, cover_y, cover_x + cfg["cover_image_size"][0], cover_y + cfg["cover_image_size"][1]), fill=(50,50,60,200))
    else:
        draw.rectangle((cover_x, cover_y, cover_x + cfg["cover_image_size"][0], cover_y + cfg["cover_image_size"][1]), fill=(50,50,60,200))

    title_obj = media.get('title', {})
    title = title_obj.get('english') or title_obj.get('romaji') or "Untitled"
    progress = media_entry.get('progress', 0)
    progress_text_val = str(progress)
    progress_label = "Ep: " if media.get('type') == 'ANIME' else "Ch: "
    media_format_text = f"Format: {media.get('format', 'N/A')}"
    
    print(f"[{time.strftime('%H:%M:%S')}] [generate_image - {media_type_for_log}] Title: {title}")

    text_x_start = text_scrim_x0
    current_y = text_scrim_y0 + cfg["text_overlay_padding"]

    display_title = title
    max_text_width_for_title = text_scrim_width - (2 * cfg["text_overlay_padding"])
    
    title_bbox = draw.textbbox((0,0), display_title, font=FONT_TITLE)
    title_width = title_bbox[2] - title_bbox[0]
    while title_width > max_text_width_for_title and len(display_title) > 15:
        display_title = display_title[:-4] + "..."
        title_bbox = draw.textbbox((0,0), display_title, font=FONT_TITLE)
        title_width = title_bbox[2] - title_bbox[0]
    draw.text((text_x_start, current_y), display_title, font=FONT_TITLE, fill=cfg["text_color_title"])
    current_y += (title_bbox[3] - title_bbox[1]) + cfg["line_spacing_title_details"]

    draw.text((text_x_start, current_y), progress_label, font=FONT_DETAILS, fill=cfg["text_color_details"])
    label_bbox = draw.textbbox((0,0), progress_label, font=FONT_DETAILS)
    label_width = label_bbox[2] - label_bbox[0]
    draw.text((text_x_start + label_width, current_y), progress_text_val, font=FONT_DETAILS, fill=cfg["accent_color"])
    
    progress_full_bbox = draw.textbbox((0,0), progress_label + progress_text_val, font=FONT_DETAILS)
    current_y += (progress_full_bbox[3] - progress_full_bbox[1]) + cfg["line_spacing_details"]

    draw.text((text_x_start, current_y), media_format_text, font=FONT_DETAILS, fill=cfg["text_color_details"])
    
    print(f"[{time.strftime('%H:%M:%S')}] [generate_image - {media_type_for_log}] Image generation complete.")
    return final_image

@app.route('/')
def root_message():
    print(f"\n[{time.strftime('%H:%M:%S')}] Root path '/' accessed.")
    return "Image generator is running. Use /last_anime.png or /last_manga.png"

@app.route('/last_anime.png')
def last_anime_image():
    print(f"\n[{time.strftime('%H:%M:%S')}] Route /last_anime.png accessed.")
    try:
        latest_anime = get_last_updated_media(media_type="ANIME")
        img = generate_image(latest_anime, media_type_for_log="ANIME")
        img_io = BytesIO()
        img.save(img_io, 'PNG')
        img_io.seek(0)
        print(f"[{time.strftime('%H:%M:%S')}] Sending ANIME image.")
        return send_file(img_io, mimetype='image/png')
    except Exception as e:
        print(f"[{time.strftime('%H:%M:%S')}] !!! Unhandled error in /last_anime.png: {e}")
        import traceback
        print(traceback.format_exc())
        abort(500, description="Error generating anime image")

@app.route('/last_manga.png')
def last_manga_image():
    print(f"\n[{time.strftime('%H:%M:%S')}] Route /last_manga.png accessed.")
    try:
        latest_manga = get_last_updated_media(media_type="MANGA")
        img = generate_image(latest_manga, media_type_for_log="MANGA")
        img_io = BytesIO()
        img.save(img_io, 'PNG')
        img_io.seek(0)
        print(f"[{time.strftime('%H:%M:%S')}] Sending MANGA image.")
        return send_file(img_io, mimetype='image/png')
    except Exception as e:
        print(f"[{time.strftime('%H:%M:%S')}] !!! Unhandled error in /last_manga.png: {e}")
        import traceback
        print(traceback.format_exc())
        abort(500, description="Error generating manga image")

if __name__ == '__main__':
    if not ANILIST_USERNAME: print("Error: ANILIST_USERNAME not set in .env.")
    if not ANILIST_TOKEN: print("Error: ANILIST_TOKEN not set in .env.")
    
    if ANILIST_USERNAME and ANILIST_TOKEN:
        print(f"[{time.strftime('%H:%M:%S')}] Starting Flask server for user: {ANILIST_USERNAME}")
        app.run(debug=True, port=5000)
    else:
        print(f"[{time.strftime('%H:%M:%S')}] Flask server NOT started due to missing .env variables.")