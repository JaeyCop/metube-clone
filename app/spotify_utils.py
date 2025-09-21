import re
import logging
import json
import asyncio
from typing import List, Dict, Optional, Tuple
import requests
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials

log = logging.getLogger('spotify_utils')

class SpotifyTrackInfo:
    def __init__(self, name: str, artists: List[str], duration_ms: int, album: str = "", track_number: int = 0):
        self.name = name
        self.artists = artists
        self.duration_ms = duration_ms
        self.album = album
        self.track_number = track_number
        
    def get_search_query(self) -> str:
        """Generate a search query for YouTube"""
        artists_str = " ".join(self.artists)
        return f"{artists_str} - {self.name}"
        
    def get_search_query_alternatives(self) -> List[str]:
        """Generate alternative search queries with enhanced strategies"""
        queries = []
        artists_str = " ".join(self.artists)
        main_artist = self.artists[0] if self.artists else ""
        
        # Clean track name (remove common problematic parts)
        clean_name = self.name
        # Remove feat./featuring parts for cleaner search
        clean_name = re.sub(r'\s*\(.*?feat\..*?\)', '', clean_name, flags=re.IGNORECASE)
        clean_name = re.sub(r'\s*feat\..*?$', '', clean_name, flags=re.IGNORECASE)
        clean_name = re.sub(r'\s*featuring.*?$', '', clean_name, flags=re.IGNORECASE)
        # Remove remix/version info for primary searches
        clean_name_no_remix = re.sub(r'\s*\(.*?(remix|mix|version|edit).*?\)', '', clean_name, flags=re.IGNORECASE)
        
        # Strategy 1: Standard format with clean name
        queries.append(f"{artists_str} - {clean_name_no_remix}")
        
        # Strategy 2: Main artist only (good for collaborations)
        queries.append(f"{main_artist} - {clean_name_no_remix}")
        
        # Strategy 3: Without dash, clean name
        queries.append(f"{main_artist} {clean_name_no_remix}")
        
        # Strategy 4: With "official" - prioritizes official uploads
        queries.append(f"{main_artist} {clean_name_no_remix} official")
        
        # Strategy 5: With "audio" - finds audio-only versions
        queries.append(f"{main_artist} {clean_name_no_remix} audio")
        
        # Strategy 6: With "music video" for popular tracks
        queries.append(f"{main_artist} {clean_name_no_remix} music video")
        
        # Strategy 7: Try original name if cleaning changed it significantly
        if clean_name != self.name:
            queries.append(f"{main_artist} - {self.name}")
            
        # Strategy 8: Album context if available
        if self.album and self.album.lower() not in clean_name.lower():
            queries.append(f"{main_artist} {clean_name_no_remix} {self.album}")
            
        # Strategy 9: Fallback - just the track name (for covers/versions)
        queries.append(clean_name_no_remix)
        
        # Strategy 10: Last resort - very specific search
        queries.append(f'"{main_artist}" "{clean_name_no_remix}"')
        
        return queries

class SpotifyMetadataExtractor:
    def __init__(self, client_id: Optional[str] = None, client_secret: Optional[str] = None):
        self.client_id = client_id
        self.client_secret = client_secret
        self.sp = None
        self._initialize_client()
        
    def _initialize_client(self):
        """Initialize Spotify client with credentials if available"""
        if self.client_id and self.client_secret:
            try:
                client_credentials_manager = SpotifyClientCredentials(
                    client_id=self.client_id,
                    client_secret=self.client_secret
                )
                self.sp = spotipy.Spotify(client_credentials_manager=client_credentials_manager)
                log.info("Spotify API client initialized successfully")
            except Exception as e:
                log.warning(f"Failed to initialize Spotify API client: {e}")
                self.sp = None
        else:
            log.info("No Spotify API credentials provided, using web scraping fallback")
            
    def _extract_id_from_url(self, url: str) -> Tuple[Optional[str], str]:
        """Extract Spotify ID and content type from URL"""
        patterns = {
            'track': r'(?:open\.spotify\.com/track/|spotify:track:)([a-zA-Z0-9]+)',
            'album': r'(?:open\.spotify\.com/album/|spotify:album:)([a-zA-Z0-9]+)',
            'playlist': r'(?:open\.spotify\.com/playlist/|spotify:playlist:)([a-zA-Z0-9]+)',
            'show': r'(?:open\.spotify\.com/show/|spotify:show:)([a-zA-Z0-9]+)',
            'episode': r'(?:open\.spotify\.com/episode/|spotify:episode:)([a-zA-Z0-9]+)',
        }
        
        for content_type, pattern in patterns.items():
            match = re.search(pattern, url)
            if match:
                return match.group(1), content_type
                
        return None, 'unknown'
        
    def _scrape_track_metadata(self, track_id: str) -> Optional[SpotifyTrackInfo]:
        """Fallback web scraping for track metadata"""
        try:
            # Use Spotify's oEmbed API which doesn't require authentication
            oembed_url = f"https://open.spotify.com/oembed?url=https://open.spotify.com/track/{track_id}"
            response = requests.get(oembed_url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                title = data.get('title', '')
                
                # Try to parse "Artist - Track" format
                if ' - ' in title:
                    artist_part, track_part = title.split(' - ', 1)
                    return SpotifyTrackInfo(
                        name=track_part,
                        artists=[artist_part],
                        duration_ms=0  # Duration not available from oEmbed
                    )
                else:
                    return SpotifyTrackInfo(
                        name=title,
                        artists=['Unknown Artist'],
                        duration_ms=0
                    )
        except Exception as e:
            log.error(f"Failed to scrape track metadata: {e}")
            
        return None
        
    def _scrape_playlist_metadata(self, playlist_id: str) -> List[SpotifyTrackInfo]:
        """Fallback web scraping for playlist metadata"""
        try:
            # Unfortunately, there's no reliable way to scrape playlist contents
            # without the API, so we'll return an empty list
            log.warning("Playlist scraping requires Spotify API credentials")
            return []
        except Exception as e:
            log.error(f"Failed to scrape playlist metadata: {e}")
            return []
            
    async def extract_track_metadata(self, url: str) -> Optional[SpotifyTrackInfo]:
        """Extract metadata for a single track"""
        track_id, content_type = self._extract_id_from_url(url)
        
        if not track_id or content_type != 'track':
            return None
            
        if self.sp:
            try:
                track = self.sp.track(track_id)
                return SpotifyTrackInfo(
                    name=track['name'],
                    artists=[artist['name'] for artist in track['artists']],
                    duration_ms=track['duration_ms'],
                    album=track['album']['name']
                )
            except Exception as e:
                log.error(f"Spotify API error: {e}")
                
        # Fallback to web scraping
        return self._scrape_track_metadata(track_id)
        
    async def extract_album_metadata(self, url: str) -> List[SpotifyTrackInfo]:
        """Extract metadata for all tracks in an album"""
        album_id, content_type = self._extract_id_from_url(url)
        
        if not album_id or content_type != 'album':
            return []
            
        if self.sp:
            try:
                album = self.sp.album(album_id)
                tracks = []
                
                for track in album['tracks']['items']:
                    tracks.append(SpotifyTrackInfo(
                        name=track['name'],
                        artists=[artist['name'] for artist in track['artists']],
                        duration_ms=track['duration_ms'],
                        album=album['name'],
                        track_number=track['track_number']
                    ))
                    
                return tracks
            except Exception as e:
                log.error(f"Spotify API error: {e}")
                
        # No fallback for albums without API
        return []
        
    async def extract_playlist_metadata(self, url: str) -> List[SpotifyTrackInfo]:
        """Extract metadata for all tracks in a playlist"""
        playlist_id, content_type = self._extract_id_from_url(url)
        
        if not playlist_id or content_type != 'playlist':
            return []
            
        if self.sp:
            try:
                playlist = self.sp.playlist(playlist_id)
                tracks = []
                
                for item in playlist['tracks']['items']:
                    if item['track'] and item['track']['type'] == 'track':
                        track = item['track']
                        tracks.append(SpotifyTrackInfo(
                            name=track['name'],
                            artists=[artist['name'] for artist in track['artists']],
                            duration_ms=track['duration_ms'],
                            album=track['album']['name'] if track['album'] else ""
                        ))
                        
                return tracks
            except Exception as e:
                log.error(f"Spotify API error: {e}")
                
        # Fallback to web scraping (limited)
        return self._scrape_playlist_metadata(playlist_id)
        
    def get_content_type(self, url: str) -> str:
        """Get the type of Spotify content"""
        _, content_type = self._extract_id_from_url(url)
        return content_type
        
    def is_spotify_url(self, url: str) -> bool:
        """Check if URL is a Spotify URL"""
        spotify_patterns = [
            r'https?://open\.spotify\.com/',
            r'spotify:',
        ]
        return any(re.match(pattern, url, re.IGNORECASE) for pattern in spotify_patterns)

# Global instance
spotify_extractor = None

def get_spotify_extractor(client_id: Optional[str] = None, client_secret: Optional[str] = None) -> SpotifyMetadataExtractor:
    """Get or create global Spotify extractor instance"""
    global spotify_extractor
    if spotify_extractor is None:
        spotify_extractor = SpotifyMetadataExtractor(client_id, client_secret)
    return spotify_extractor