# GoPro Plus Cloud Downloader

This is a simple Python script that downloads all the media files from your 
GoPro Plus cloud account. It uses an unofficial API to list all the media files 
and download them to your local machine grouped by `capture_at` date.

The script will keep track of the downloaded files in a TinyDB database to avoid
downloading the same files again and to resume the download if it's interrupted.

## Requirements
Before running the script, you need to install the required dependencies:

* Python 3.12.5
* pip3
* pipenv
 

## Installation

1. Clone this repository
2. Install the required Python environment using `pipenv install`
3. Login to the website [https://gopro.com/login](https://gopro.com/login) and import cookies as JSON from browser using the extension "Cookie-Editor" or any similar.
4. Save the cookies as `.json` in the root directory of this repository.
5. Run the script using `pipenv run python main.py --help`

## Usage

```
usage: main.py [-h] --auth AUTH [--date-range DATE_RANGE] [--media-type {Videos,Photos,all}] [--chunk-size CHUNK_SIZE] [--per-page PER_PAGE]

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

options:
-h, --help            show this help message and exit
--auth AUTH           Path to the authentication cookies JSON file
--date-range DATE_RANGE
Date range to search for media in format YYYY-MM-DD,YYYY-MM-DD
--media-type {Videos,Photos,all}
Type of media to search for Videos Photos or all
--chunk-size CHUNK_SIZE
The bytes to download in each chunk (default: 8192)
--per-page PER_PAGE   Number of items to fetch per page (default: 30)
```

Whenever you want to restart the process and download all the files again, you can delete the `gopro_media_db.json` file.

### Example

To download all the media files from the cloud:
```bash
python main.py --auth cookies.json
```
To download all the files between 2019-01-01 and 2019-12-31:
```bash
python main.py --auth cookies.json --date-range 2019-01-01,2019-12-31
```
To download only the photos:
```bash
python main.py --auth cookies.json --media-type Photos
```
