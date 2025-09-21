import os
import yt_dlp
from collections import OrderedDict
import shelve
import time
import asyncio
import multiprocessing
import logging
import re

import yt_dlp.networking.impersonate
from dl_formats import get_format, get_opts, AUDIO_FORMATS
from datetime import datetime

log = logging.getLogger('ytdl')

class DownloadQueueNotifier:
    async def added(self, dl):
        raise NotImplementedError

    async def updated(self, dl):
        raise NotImplementedError

    async def completed(self, dl):
        raise NotImplementedError

    async def canceled(self, id):
        raise NotImplementedError

    async def cleared(self, id):
        raise NotImplementedError

class DownloadInfo:
    def __init__(self, id, title, url, quality, format, folder, custom_name_prefix, error):
        self.id = id if len(custom_name_prefix) == 0 else f'{custom_name_prefix}.{id}'
        self.title = title if len(custom_name_prefix) == 0 else f'{custom_name_prefix}.{title}'
        self.url = url
        self.quality = quality
        self.format = format
        self.folder = folder
        self.custom_name_prefix = custom_name_prefix
        self.msg = self.percent = self.speed = self.eta = None
        self.status = "pending"
        self.size = None
        self.timestamp = time.time_ns()
        self.error = error

class Download:
    manager = None

    def __init__(self, download_dir, temp_dir, output_template, output_template_chapter, quality, format, ytdl_opts, info):
        self.download_dir = download_dir
        self.temp_dir = temp_dir
        self.output_template = output_template
        self.output_template_chapter = output_template_chapter
        self.format = get_format(format, quality)
        self.ytdl_opts = get_opts(format, quality, ytdl_opts)
        if "impersonate" in self.ytdl_opts:
            self.ytdl_opts["impersonate"] = yt_dlp.networking.impersonate.ImpersonateTarget.from_str(self.ytdl_opts["impersonate"])
        self.info = info
        self.canceled = False
        self.tmpfilename = None
        self.status_queue = None
        self.proc = None
        self.loop = None
        self.notifier = None

    def _download(self):
        log.info(f"Starting download for: {self.info.title} ({self.info.url})")
        try:
            def put_status(st):
                self.status_queue.put({k: v for k, v in st.items() if k in (
                    'tmpfilename',
                    'filename',
                    'status',
                    'msg',
                    'total_bytes',
                    'total_bytes_estimate',
                    'downloaded_bytes',
                    'speed',
                    'eta',
                )})

            def put_status_postprocessor(d):
                if d['postprocessor'] == 'MoveFiles' and d['status'] == 'finished':
                    if '__finaldir' in d['info_dict']:
                        filename = os.path.join(d['info_dict']['__finaldir'], os.path.basename(d['info_dict']['filepath']))
                    else:
                        filename = d['info_dict']['filepath']
                    self.status_queue.put({'status': 'finished', 'filename': filename})

            ret = yt_dlp.YoutubeDL(params={
                'quiet': True,
                'no_color': True,
                'paths': {"home": self.download_dir, "temp": self.temp_dir},
                'outtmpl': { "default": self.output_template, "chapter": self.output_template_chapter },
                'format': self.format,
                'socket_timeout': 30,
                'ignore_no_formats_error': True,
                'progress_hooks': [put_status],
                'postprocessor_hooks': [put_status_postprocessor],
                **self.ytdl_opts,
            }).download([self.info.url])
            self.status_queue.put({'status': 'finished' if ret == 0 else 'error'})
            log.info(f"Finished download for: {self.info.title}")
        except yt_dlp.utils.YoutubeDLError as exc:
            log.error(f"Download error for {self.info.title}: {str(exc)}")
            self.status_queue.put({'status': 'error', 'msg': str(exc)})

    async def start(self, notifier):
        log.info(f"Preparing download for: {self.info.title}")
        if Download.manager is None:
            Download.manager = multiprocessing.Manager()
        self.status_queue = Download.manager.Queue()
        self.proc = multiprocessing.Process(target=self._download)
        self.proc.start()
        self.loop = asyncio.get_running_loop()
        self.notifier = notifier
        self.info.status = 'preparing'
        await self.notifier.updated(self.info)
        asyncio.create_task(self.update_status())
        return await self.loop.run_in_executor(None, self.proc.join)

    def cancel(self):
        log.info(f"Cancelling download: {self.info.title}")
        if self.running():
            try:
                self.proc.kill()
            except Exception as e:
                log.error(f"Error killing process for {self.info.title}: {e}")
        self.canceled = True
        if self.status_queue is not None:
            self.status_queue.put(None)

    def close(self):
        log.info(f"Closing download process for: {self.info.title}")
        if self.started():
            self.proc.close()
            if self.status_queue is not None:
                self.status_queue.put(None)

    def running(self):
        try:
            return self.proc is not None and self.proc.is_alive()
        except ValueError:
            return False

    def started(self):
        return self.proc is not None

    async def update_status(self):
        while True:
            status = await self.loop.run_in_executor(None, self.status_queue.get)
            if status is None:
                log.info(f"Status update finished for: {self.info.title}")
                return
            if self.canceled:
                log.info(f"Download {self.info.title} is canceled; stopping status updates.")
                return
            self.tmpfilename = status.get('tmpfilename')
            if 'filename' in status:
                fileName = status.get('filename')
                self.info.filename = os.path.relpath(fileName, self.download_dir)
                self.info.size = os.path.getsize(fileName) if os.path.exists(fileName) else None
                if self.info.format == 'thumbnail':
                    self.info.filename = re.sub(r'\.webm$', '.jpg', self.info.filename)
            self.info.status = status['status']
            self.info.msg = status.get('msg')
            if 'downloaded_bytes' in status:
                total = status.get('total_bytes') or status.get('total_bytes_estimate')
                if total:
                    self.info.percent = status['downloaded_bytes'] / total * 100
            self.info.speed = status.get('speed')
            self.info.eta = status.get('eta')
            log.info(f"Updating status for {self.info.title}: {status}")
            await self.notifier.updated(self.info)

class PersistentQueue:
    def __init__(self, path):
        pdir = os.path.dirname(path)
        if not os.path.isdir(pdir):
            os.mkdir(pdir)
        with shelve.open(path, 'c'):
            pass
        self.path = path
        self.dict = OrderedDict()

    def load(self):
        for k, v in self.saved_items():
            self.dict[k] = Download(None, None, None, None, None, None, {}, v)

    def exists(self, key):
        return key in self.dict

    def get(self, key):
        return self.dict[key]

    def items(self):
        return self.dict.items()

    def saved_items(self):
        with shelve.open(self.path, 'r') as shelf:
            return sorted(shelf.items(), key=lambda item: item[1].timestamp)

    def put(self, value):
        key = value.info.url
        self.dict[key] = value
        with shelve.open(self.path, 'w') as shelf:
            shelf[key] = value.info

    def delete(self, key):
        if key in self.dict:
            del self.dict[key]
            with shelve.open(self.path, 'w') as shelf:
                shelf.pop(key, None)

    def next(self):
        k, v = next(iter(self.dict.items()))
        return k, v

    def empty(self):
        return not bool(self.dict)

class DownloadQueue:
    def __init__(self, config, notifier):
        self.config = config
        self.notifier = notifier
        self.queue = PersistentQueue(self.config.STATE_DIR + '/queue')
        self.done = PersistentQueue(self.config.STATE_DIR + '/completed')
        self.pending = PersistentQueue(self.config.STATE_DIR + '/pending')
        self.active_downloads = set()
        self.semaphore = None
        # For sequential mode, use an asyncio lock to ensure one-at-a-time execution.
        if self.config.DOWNLOAD_MODE == 'sequential':
            self.seq_lock = asyncio.Lock()
        elif self.config.DOWNLOAD_MODE == 'limited':
            self.semaphore = asyncio.Semaphore(int(self.config.MAX_CONCURRENT_DOWNLOADS))
        
        self.done.load()

    async def __import_queue(self):
        for k, v in self.queue.saved_items():
            await self.add(v.url, v.quality, v.format, v.folder, v.custom_name_prefix, getattr(v, 'playlist_strict_mode', False), getattr(v, 'playlist_item_limit', 0))

    async def initialize(self):
        log.info("Initializing DownloadQueue")
        asyncio.create_task(self.__import_queue())

    async def __start_download(self, download):
        if download.canceled:
            log.info(f"Download {download.info.title} was canceled, skipping start.")
            return
        if self.config.DOWNLOAD_MODE == 'sequential':
            async with self.seq_lock:
                log.info("Starting sequential download.")
                await download.start(self.notifier)
                self._post_download_cleanup(download)
        elif self.config.DOWNLOAD_MODE == 'limited' and self.semaphore is not None:
            await self.__limited_concurrent_download(download)
        else:
            await self.__concurrent_download(download)

    async def __concurrent_download(self, download):
        log.info("Starting concurrent download without limits.")
        asyncio.create_task(self._run_download(download))

    async def __limited_concurrent_download(self, download):
        log.info("Starting limited concurrent download.")
        async with self.semaphore:
            await self._run_download(download)

    async def _run_download(self, download):
        if download.canceled:
            log.info(f"Download {download.info.title} is canceled; skipping start.")
            return
        await download.start(self.notifier)
        self._post_download_cleanup(download)

    def _post_download_cleanup(self, download):
        if download.info.status != 'finished':
            if download.tmpfilename and os.path.isfile(download.tmpfilename):
                try:
                    os.remove(download.tmpfilename)
                except:
                    pass
            download.info.status = 'error'
        download.close()
        if self.queue.exists(download.info.url):
            self.queue.delete(download.info.url)
            if download.canceled:
                asyncio.create_task(self.notifier.canceled(download.info.url))
            else:
                self.done.put(download)
                asyncio.create_task(self.notifier.completed(download.info))

    def __extract_info(self, url, playlist_strict_mode):
        return yt_dlp.YoutubeDL(params={
            'quiet': True,
            'no_color': True,
            'extract_flat': True,
            'ignore_no_formats_error': True,
            'noplaylist': playlist_strict_mode,
            'paths': {"home": self.config.DOWNLOAD_DIR, "temp": self.config.TEMP_DIR},
            **self.config.YTDL_OPTIONS,
            **({'impersonate': yt_dlp.networking.impersonate.ImpersonateTarget.from_str(self.config.YTDL_OPTIONS['impersonate'])} if 'impersonate' in self.config.YTDL_OPTIONS else {}),
        }).extract_info(url, download=False)

    def __calc_download_path(self, quality, format, folder):
        base_directory = self.config.DOWNLOAD_DIR if (quality != 'audio' and format not in AUDIO_FORMATS) else self.config.AUDIO_DOWNLOAD_DIR
        if folder:
            if not self.config.CUSTOM_DIRS:
                return None, {'status': 'error', 'msg': f'A folder for the download was specified but CUSTOM_DIRS is not true in the configuration.'}
            dldirectory = os.path.realpath(os.path.join(base_directory, folder))
            real_base_directory = os.path.realpath(base_directory)
            if not dldirectory.startswith(real_base_directory):
                return None, {'status': 'error', 'msg': f'Folder "{folder}" must resolve inside the base download directory "{real_base_directory}"'}
            if not os.path.isdir(dldirectory):
                if not self.config.CREATE_CUSTOM_DIRS:
                    return None, {'status': 'error', 'msg': f'Folder "{folder}" for download does not exist inside base directory "{real_base_directory}", and CREATE_CUSTOM_DIRS is not true in the configuration.'}
                os.makedirs(dldirectory, exist_ok=True)
        else:
            dldirectory = base_directory
        return dldirectory, None

    async def __add_entry(self, entry, quality, format, folder, custom_name_prefix, playlist_strict_mode, playlist_item_limit, auto_start, already):
        if not entry:
            return {'status': 'error', 'msg': "Invalid/empty data was given."}

        error = None
        if "live_status" in entry and "release_timestamp" in entry and entry.get("live_status") == "is_upcoming":
            dt_ts = datetime.fromtimestamp(entry.get("release_timestamp")).strftime('%Y-%m-%d %H:%M:%S %z')
            error = f"Live stream is scheduled to start at {dt_ts}"
        else:
            if "msg" in entry:
                error = entry["msg"]

        etype = entry.get('_type') or 'video'

        if etype.startswith('url'):
            log.debug('Processing as an url')
            return await self.add(entry['url'], quality, format, folder, custom_name_prefix, playlist_strict_mode, playlist_item_limit, auto_start, already)
        elif etype == 'playlist':
            log.debug('Processing as a playlist')
            entries = entry['entries']
            log.info(f'playlist detected with {len(entries)} entries')
            playlist_index_digits = len(str(len(entries)))
            results = []
            if playlist_item_limit > 0:
                log.info(f'Playlist item limit is set. Processing only first {playlist_item_limit} entries')
                entries = entries[:playlist_item_limit]
            for index, etr in enumerate(entries, start=1):
                etr["_type"] = "video"
                etr["playlist"] = entry["id"]
                etr["playlist_index"] = '{{0:0{0:d}d}}'.format(playlist_index_digits).format(index)
                for property in ("id", "title", "uploader", "uploader_id"):
                    if property in entry:
                        etr[f"playlist_{property}"] = entry[property]
                results.append(await self.__add_entry(etr, quality, format, folder, custom_name_prefix, playlist_strict_mode, playlist_item_limit, auto_start, already))
            if any(res['status'] == 'error' for res in results):
                return {'status': 'error', 'msg': ', '.join(res['msg'] for res in results if res['status'] == 'error' and 'msg' in res)}
            return {'status': 'ok'}
        elif etype == 'video' or (etype.startswith('url') and 'id' in entry and 'title' in entry):
            log.debug('Processing as a video')
            key = entry.get('webpage_url') or entry['url']
            if not self.queue.exists(key):
                dl = DownloadInfo(entry['id'], entry.get('title') or entry['id'], key, quality, format, folder, custom_name_prefix, error)
                dldirectory, error_message = self.__calc_download_path(quality, format, folder)
                if error_message is not None:
                    return error_message
                output = self.config.OUTPUT_TEMPLATE if len(custom_name_prefix) == 0 else f'{custom_name_prefix}.{self.config.OUTPUT_TEMPLATE}'
                output_chapter = self.config.OUTPUT_TEMPLATE_CHAPTER
                if 'playlist' in entry and entry['playlist'] is not None:
                    if len(self.config.OUTPUT_TEMPLATE_PLAYLIST):
                        output = self.config.OUTPUT_TEMPLATE_PLAYLIST
                    for property, value in entry.items():
                        if property.startswith("playlist"):
                            output = output.replace(f"%({property})s", str(value))
                ytdl_options = dict(self.config.YTDL_OPTIONS)
                if playlist_item_limit > 0:
                    log.info(f'playlist limit is set. Processing only first {playlist_item_limit} entries')
                    ytdl_options['playlistend'] = playlist_item_limit
                if auto_start is True:
                    download = Download(dldirectory, self.config.TEMP_DIR, output, output_chapter, quality, format, ytdl_options, dl)
                    self.queue.put(download)
                    asyncio.create_task(self.__start_download(download))
                else:
                    self.pending.put(Download(dldirectory, self.config.TEMP_DIR, output, output_chapter, quality, format, ytdl_options, dl))
                await self.notifier.added(dl)
            return {'status': 'ok'}
        return {'status': 'error', 'msg': f'Unsupported resource "{etype}"'}

    def __is_spotify_url(self, url):
        """Check if the URL is a Spotify URL"""
        from spotify_utils import get_spotify_extractor
        extractor = get_spotify_extractor()
        return extractor.is_spotify_url(url)

    def __get_spotify_content_type(self, url):
        """Determine the type of Spotify content"""
        from spotify_utils import get_spotify_extractor
        extractor = get_spotify_extractor()
        return extractor.get_content_type(url)
        
    async def __search_youtube_for_track(self, track_info, max_attempts=5):
        """Search YouTube for a track using multiple search strategies with quality filtering"""
        from spotify_utils import SpotifyTrackInfo
        
        if not isinstance(track_info, SpotifyTrackInfo):
            return None
            
        search_queries = track_info.get_search_query_alternatives()
        
        for attempt, query in enumerate(search_queries[:max_attempts]):
            try:
                log.info(f"Searching YouTube for: {query} (attempt {attempt + 1}/{max_attempts})")
                
                # Search for multiple results to find best match
                search_url = f"ytsearch5:{query}"
                search_result = await asyncio.get_running_loop().run_in_executor(
                    None, self.__extract_info, search_url, True
                )
                
                if search_result and 'entries' in search_result and search_result['entries']:
                    best_video = self.__select_best_video(search_result['entries'], track_info)
                    if best_video:
                        log.info(f"Found YouTube video: {best_video.get('title', 'Unknown')} - {best_video.get('webpage_url', '')}")
                        return best_video.get('webpage_url')
                    
            except Exception as e:
                log.warning(f"YouTube search attempt {attempt + 1} failed for '{query}': {e}")
                continue
                
        log.warning(f"Could not find YouTube video for track: {track_info.get_search_query()}")
        return None
        
    def __select_best_video(self, videos, track_info):
        """Select the best video from search results based on quality indicators"""
        from spotify_utils import SpotifyTrackInfo
        
        if not videos:
            return None
            
        # If only one result, return it
        if len(videos) == 1:
            return videos[0]
            
        scored_videos = []
        track_duration = track_info.duration_ms / 1000.0 if track_info.duration_ms > 0 else None
        
        for video in videos:
            score = 0
            title = video.get('title', '').lower()
            duration = video.get('duration', 0)
            view_count = video.get('view_count', 0)
            uploader = video.get('uploader', '').lower()
            
            # Prefer official uploads and verified channels
            if any(indicator in uploader for indicator in ['official', 'records', 'music', 'vevo']):
                score += 30
            if any(indicator in title for indicator in ['official', 'music video', 'audio']):
                score += 20
                
            # Prefer videos with reasonable view counts (but not too low or suspiciously high)
            if view_count > 1000:
                score += 10
            if view_count > 100000:
                score += 10
            if view_count > 1000000:
                score += 5
                
            # Duration matching (if we have Spotify duration)
            if track_duration and duration:
                duration_diff = abs(duration - track_duration)
                if duration_diff < 10:  # Within 10 seconds
                    score += 25
                elif duration_diff < 30:  # Within 30 seconds
                    score += 15
                elif duration_diff < 60:  # Within 1 minute
                    score += 5
                elif duration_diff > 300:  # More than 5 minutes off
                    score -= 15
                    
            # Penalize very short or very long videos (likely not the track)
            if duration:
                if duration < 30:  # Too short
                    score -= 20
                elif duration > 600:  # Over 10 minutes, likely not a single track
                    score -= 10
                    
            # Prefer videos that don't have live/remix/cover indicators (unless original is remix)
            original_is_remix = any(term in track_info.name.lower() for term in ['remix', 'mix', 'edit'])
            if not original_is_remix:
                if any(term in title for term in ['live', 'cover', 'remix', 'karaoke', 'instrumental']):
                    score -= 15
                    
            # Prefer audio-only or music videos over other content
            if any(term in title for term in ['audio', 'lyrics', 'music video']):
                score += 10
                
            scored_videos.append((score, video))
            
        # Sort by score (highest first) and return best match
        scored_videos.sort(key=lambda x: x[0], reverse=True)
        
        best_video = scored_videos[0][1]
        log.info(f"Selected video with score {scored_videos[0][0]}: {best_video.get('title', 'Unknown')}")
        
        return best_video
        
    async def __process_spotify_content(self, url, quality, format, folder, custom_name_prefix, playlist_strict_mode, playlist_item_limit, auto_start, already):
        """Process Spotify URLs by extracting metadata and searching YouTube"""
        from spotify_utils import get_spotify_extractor
        
        extractor = get_spotify_extractor(
            client_id=self.config.SPOTIFY_CLIENT_ID or self.config.YTDL_OPTIONS.get('spotify_client_id'),
            client_secret=self.config.SPOTIFY_CLIENT_SECRET or self.config.YTDL_OPTIONS.get('spotify_client_secret')
        )
        
        content_type = extractor.get_content_type(url)
        log.info(f"Processing Spotify {content_type}: {url}")
        
        tracks = []
        
        try:
            if content_type == 'track':
                track = await extractor.extract_track_metadata(url)
                if track:
                    tracks = [track]
                    
            elif content_type == 'album':
                tracks = await extractor.extract_album_metadata(url)
                
            elif content_type == 'playlist':
                tracks = await extractor.extract_playlist_metadata(url)
                
            else:
                # For podcasts and other content, let the original handler deal with it
                return None
                
        except Exception as e:
            log.error(f"Failed to extract Spotify metadata: {e}")
            return {'status': 'error', 'msg': f'Failed to extract Spotify metadata: {str(e)}'}
            
        if not tracks:
            if content_type in ['track', 'album', 'playlist']:
                return {'status': 'error', 'msg': f'No tracks found in Spotify {content_type}. This might require Spotify API credentials (SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET).'}
            else:
                return None  # Let original handler process podcasts/episodes
                
        log.info(f"Found {len(tracks)} tracks in Spotify {content_type}")
        
        # Apply playlist item limit if specified
        if playlist_item_limit > 0 and len(tracks) > playlist_item_limit:
            log.info(f"Limiting to first {playlist_item_limit} tracks")
            tracks = tracks[:playlist_item_limit]
            
        successful_downloads = 0
        failed_downloads = 0
        
        for i, track in enumerate(tracks, 1):
            try:
                log.info(f"Processing track {i}/{len(tracks)}: {track.get_search_query()}")
                
                # Search for the track on YouTube
                youtube_url = await self.__search_youtube_for_track(track)
                
                if youtube_url:
                    # Create a custom name prefix that includes track info
                    track_prefix = custom_name_prefix
                    if content_type in ['album', 'playlist']:
                        if track_prefix:
                            track_prefix += f".{i:02d}_{track.artists[0]}_{track.name}"
                        else:
                            track_prefix = f"{i:02d}_{track.artists[0]}_{track.name}"
                        # Clean the prefix (remove invalid filename characters)
                        track_prefix = re.sub(r'[<>:"/\\|?*]', '_', track_prefix)
                    
                    # Add the YouTube video to the download queue
                    result = await self.add(
                        youtube_url, quality, format, folder, track_prefix,
                        True,  # playlist_strict_mode = True for individual videos
                        0,     # playlist_item_limit = 0 for individual videos  
                        auto_start, already
                    )
                    
                    if result.get('status') == 'ok':
                        successful_downloads += 1
                        log.info(f"Successfully queued: {track.get_search_query()}")
                    else:
                        failed_downloads += 1
                        log.warning(f"Failed to queue: {track.get_search_query()} - {result.get('msg', 'Unknown error')}")
                else:
                    failed_downloads += 1
                    log.warning(f"Could not find YouTube video for: {track.get_search_query()}")
                    
            except Exception as e:
                failed_downloads += 1
                log.error(f"Error processing track {track.get_search_query()}: {e}")
                
        # Return summary result
        if successful_downloads > 0:
            msg = f"Successfully queued {successful_downloads} tracks from Spotify {content_type}"
            if failed_downloads > 0:
                msg += f" ({failed_downloads} tracks could not be found on YouTube)"
            return {'status': 'ok', 'msg': msg}
        else:
            return {'status': 'error', 'msg': f'Could not find any tracks from Spotify {content_type} on YouTube'}

    async def add(self, url, quality, format, folder, custom_name_prefix, playlist_strict_mode, playlist_item_limit, auto_start=True, already=None):
        log.info(f'adding {url}: {quality=} {format=} {already=} {folder=} {custom_name_prefix=} {playlist_strict_mode=} {playlist_item_limit=}')
        already = set() if already is None else already
        if url in already:
            log.info('recursion detected, skipping')
            return {'status': 'ok'}
        else:
            already.add(url)

        # Special handling for Spotify URLs
        if self.__is_spotify_url(url):
            content_type = self.__get_spotify_content_type(url)
            log.info(f'Spotify {content_type} URL detected: {url}')
            
            # Try to process Spotify music content by searching YouTube
            if content_type in ['track', 'album', 'playlist']:
                log.info(f'Processing Spotify {content_type} by searching for tracks on YouTube')
                spotify_result = await self.__process_spotify_content(
                    url, quality, format, folder, custom_name_prefix, 
                    playlist_strict_mode, playlist_item_limit, auto_start, already
                )
                if spotify_result is not None:
                    return spotify_result
                # If spotify_result is None, fall through to try direct download (for podcasts)
            elif content_type in ['podcast', 'episode']:
                log.info(f'Attempting to process Spotify {content_type} content - this may or may not work due to DRM restrictions')

        try:
            entry = await asyncio.get_running_loop().run_in_executor(None, self.__extract_info, url, playlist_strict_mode)
        except yt_dlp.utils.YoutubeDLError as exc:
            error_msg = str(exc)
            if self.__is_spotify_url(url):
                # Enhance error message for Spotify URLs
                if 'DRM' in error_msg:
                    error_msg += ' Most Spotify content is DRM-protected and cannot be downloaded. Only some podcast content may be accessible.'
                elif 'blocked' in error_msg.lower() or '403' in error_msg:
                    error_msg += ' Spotify has blocked access to this content. Try using official Spotify features instead.'
                log.error(f'Spotify extraction failed: {error_msg}')
            else:
                log.error(f'Extraction failed: {error_msg}')
            return {'status': 'error', 'msg': error_msg}
        return await self.__add_entry(entry, quality, format, folder, custom_name_prefix, playlist_strict_mode, playlist_item_limit, auto_start, already)

    async def start_pending(self, ids):
        for id in ids:
            if not self.pending.exists(id):
                log.warn(f'requested start for non-existent download {id}')
                continue
            dl = self.pending.get(id)
            self.queue.put(dl)
            self.pending.delete(id)
            asyncio.create_task(self.__start_download(dl))
        return {'status': 'ok'}

    async def cancel(self, ids):
        for id in ids:
            if self.pending.exists(id):
                self.pending.delete(id)
                await self.notifier.canceled(id)
                continue
            if not self.queue.exists(id):
                log.warn(f'requested cancel for non-existent download {id}')
                continue
            if self.queue.get(id).started():
                self.queue.get(id).cancel()
            else:
                self.queue.delete(id)
                await self.notifier.canceled(id)
        return {'status': 'ok'}

    async def clear(self, ids):
        for id in ids:
            if not self.done.exists(id):
                log.warn(f'requested delete for non-existent download {id}')
                continue
            if self.config.DELETE_FILE_ON_TRASHCAN:
                dl = self.done.get(id)
                try:
                    dldirectory, _ = self.__calc_download_path(dl.info.quality, dl.info.format, dl.info.folder)
                    os.remove(os.path.join(dldirectory, dl.info.filename))
                except Exception as e:
                    log.warn(f'deleting file for download {id} failed with error message {e!r}')
            self.done.delete(id)
            await self.notifier.cleared(id)
        return {'status': 'ok'}

    def get(self):
        return (list((k, v.info) for k, v in self.queue.items()) +
                list((k, v.info) for k, v in self.pending.items()),
                list((k, v.info) for k, v in self.done.items()))
