"""
GoPRO Plus Cloud Downloader

Tool to download files from GoPro Plus Cloud as they don't offer such support,
and you have to manually scroll and click to download each file.

Login to the website and import cookies as JSON from browser using
the extension "Cookie-Editor" or similar.

Files will be downloaded in a folder named "downloads" as ZIP archives
grouped by date. Each archive contains the photos and videos from that day based
on the 'captured_at' field.

The script will keep track of the downloaded files in a TinyDB database to avoid
downloading the same files again.
"""
import argparse
import re
import json
import os.path
from itertools import groupby
from operator import itemgetter
from typing import Optional, Any
from argparse import ArgumentParser
from datetime import datetime

import requests
from tqdm import tqdm
from tinydb import TinyDB, Query


def is_valid_date(date_str: str) -> bool:
    try:
        # Attempt to parse the date
        datetime.strptime(date_str, '%Y-%m-%d')
        return True
    except ValueError:
        return False


def is_valid_date_range(date_range_str: str) -> bool:
    pattern = r'^\d{4}-\d{2}-\d{2},\d{4}-\d{2}-\d{2}$'
    if not re.match(pattern, date_range_str):
        return False

    start_date_str, end_date_str = date_range_str.split(',')

    # Validate dates
    if not (is_valid_date(start_date_str) and is_valid_date(end_date_str)):
        return False

    # Check if start date is before end date
    start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
    end_date = datetime.strptime(end_date_str, '%Y-%m-%d')

    if start_date > end_date:
        return False

    return True


def download_media(rsession: requests.Session, zip_name: str, data: list[dict]):
    data_size = sum([item['file_size'] for item in data])
    data_size_mb = round((data_size / 1024 / 1024), 2)
    print(f"Starting download of {zip_name} which has a total size of: {data_size_mb} MB")
    media_ids = [item['id'] for item in data]
    url = 'https://api.gopro.com/media/x/zip/source?ids=' + ','.join(media_ids)
    headers = {
        'Content-Type': 'application/octet-stream',
        'Accept': 'application/zip',
        'Accept-Encoding': 'gzip, deflate, br, zstd',
    }
    response = rsession.get(url, headers=headers, stream=True)
    # Check if response was successful
    if response.status_code == 200:
        # Write the response content to a file
        with (open(zip_name, 'wb') as f,
              tqdm(unit='B', unit_scale=True, unit_divisor=1024, total=data_size
                   ) as progress_bar):
            for chunk in response.iter_content(arguments.chunk_size):
                if chunk:
                    f.write(chunk)
                    progress_bar.update((len(chunk)))
        print(f"Downloaded successfully {zip_name}")
        # At this point we have to add to a database the zip name and the media ids
        insert_ids_by_date(data[0]['captured_day'], media_ids)
    else:
        print(f"Failed to download the ZIP file. Status code: {response.status_code}")
        print(f"Response: {response.text}")


def search_media(rsession: requests.Session,
                 date_range: str = None,
                 file_type: str = None,
                 page: int = 1,
                 per_page: int = 30
                 ) -> Optional[Any]:
    query_str_dict = {
        'processing_states': 'rendering, pretranscoding, transcoding, ready',
        'fields': 'camera_model, captured_at, content_title, content_type, created_at, gopro_user_id, gopro_media, filename, file_extension, file_size, height, fov, id, item_count, mce_type, moments_count, on_public_profile, orientation, play_as, ready_to_edit, ready_to_view, resolution, source_duration, token, type, width, submitted_at, thumbnail_available, captured_at_timezone, available_labels',
        'type': 'Burst, BurstVideo, Continuous, LoopedVideo, Photo, TimeLapse, TimeLapseVideo, Video',
        'page': f"{page}",
        'per_page': f"{per_page}"
    }
    if date_range:
        query_str_dict['range'] = date_range
    if file_type:
        query_str_dict['type'] = file_type

    query_string = '&'.join([f'{key}={value.replace(" ", "")}'
                             for key, value in query_str_dict.items()])
    url = f'https://api.gopro.com/media/search?{query_string}'
    headers = {
        'Accept': 'application/vnd.gopro.jk.media.search+json; version=2.0.0',
        'Accept-Language': 'en-US',
        }
    response = rsession.get(url, headers=headers)
    if response.status_code == 401:
        print(f"Failed to authenticate. Please check the cookies file")
        print(f"Response: {response.text}")
        return
    elif response.status_code == 200:
        response_json = response.json()
        return response_json
    else:
        print(f"Response failed with status code {response.status_code}")
        print(f"Response: {response.text}")
        return



def get_zip_filename(captured_day: str) -> str:
    counter = 1
    filename = os.path.join(download_dir, f"{captured_day}_{counter}_GoPro.zip")
    while os.path.exists(filename):
        counter += 1
        filename = os.path.join(download_dir, f"{captured_day}_{counter}_GoPro.zip")

    return filename


def download_by_date(rsession: requests.Session, data: dict) -> None:
    needed_fields = ['captured_at', 'filename', 'file_extension', 'file_size',
                     'id', 'type']
    # This is the data from the first page
    needed_data = []
    for item in data['_embedded']['media']:
        item_data = {key: item[key] for key in needed_fields}
        item_data['captured_day'] = item['captured_at'].split('T')[0]
        needed_data.append(item_data)
    # Sort the data by 'captured_day'
    needed_data_sorted = sorted(needed_data, key=itemgetter('captured_day'))
    # Group the data by 'captured_day'
    grouped_data = {key: list(group) for key, group in
                    groupby(needed_data_sorted, key=itemgetter('captured_day'))}
    for captured_day, items in grouped_data.items():
        zip_name = get_zip_filename(captured_day)
        # Check if the media ids are already in the database
        db_ids = get_ids_by_date(captured_day)
        if len(db_ids) == 0 or len(db_ids) != len(items):
            # If the media ids are not in the database or the amount of media items is different
            # download the media
            download_media(rsession, zip_name, items)
        else:
            print(f"Skipping download of {zip_name} as it was already downloaded")


def insert_ids_by_date(captured_at: str, ids_list: list[str]) -> None:
    existing_record = db.search(MediaQuery.date == captured_at)
    if existing_record:
        # If the date already exists, update the media IDs
        current_ids = existing_record[0]['ids']
        new_ids = list(set(current_ids + ids_list)) # Merge and remove duplicates
        db.update({'ids': new_ids}, MediaQuery.date == captured_at)
    else:
        db.insert({'date': captured_at, 'ids': ids_list})


def search_id(media_id: str) -> bool:
    result = db.search(MediaQuery.ids.any([media_id]))
    if result:
        return True
    return False


def get_ids_by_date(captured_at: str) -> list[str]:
    result = db.search(MediaQuery.date == captured_at)
    if result:
        return result[0]['ids']
    return []


def main() -> None:
    # Authenticate to the GoPro Cloud with cookies
    with open(arguments.auth) as f:
        cookies_json = json.load(f)
    cookies = {cookie['name']: cookie['value'] for cookie in cookies_json}
    rsession = requests.Session()
    rsession.cookies = requests.cookies.cookiejar_from_dict(cookies)

    # 1st api call to search for media
    data = search_media(rsession, arguments.date_range, arguments.media_type,
                        per_page=arguments.per_page)
    if not data:
        print("No media was found")
        return
    _pages = data['_pages']

    download_by_date(rsession, data)

    # For each page  do next thing, put the name of the zip the date and download the data
    for page in range(2, _pages['total_pages']):
        data = search_media(rsession, arguments.date_range, arguments.media_type, page)
        if not data:
            print("No media was found")
            return
        download_by_date(rsession, data)


if __name__ == '__main__':
    parser = ArgumentParser(description=__doc__,
                            formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--auth', type=str,
                        help='Path to the authentication cookies JSON file',
                        required=True)
    parser.add_argument('--date-range', type=str,
                        help='Date range to search for media in format YYYY-MM-DD,YYYY-MM-DD')
    parser.add_argument('--media-type', type=str,
                        help='Type of media to search for Videos Photos or all (default: all)',
                        choices=['Videos', 'Photos', 'all'], default='all')
    parser.add_argument('--chunk-size', type=int,
                        help='The bytes to download in each chunk (default: 8192)', default=8192)
    parser.add_argument('--per-page', type=int,
                        help='Number of items to fetch per page (default: 30)', default=30)
    arguments = parser.parse_args()
    if arguments.date_range:
        if not is_valid_date_range(arguments.date_range):
            print("Invalid date range format. Expected format: YYYY-MM-DD,YYYY-MM-DD")
            exit(1)
    if not os.path.exists(arguments.auth):
        print("Invalid path to authentication cookies file")
        exit(1)
    if arguments.media_type == 'all':
        arguments.media_type = 'Burst, BurstVideo, Continuous, LoopedVideo, Photo, TimeLapse, TimeLapseVideo, Video'
    elif arguments.media_type == 'Videos':
        arguments.media_type = 'Video,BurstVideo,Timelapse,TimeLapseVideo,LoopedVideo'
    elif arguments.media_type == 'Photos':
        arguments.media_type = 'Photo,Burst'

    download_dir = 'downloads'
    if not os.path.exists(download_dir):
        os.makedirs(download_dir)

    db = TinyDB('gopro_media_db.json')
    MediaQuery = Query()
    try:
        main()
    except KeyboardInterrupt:
        print("Exiting...")
        exit(1)
