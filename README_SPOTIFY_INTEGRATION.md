# Spotify Integration for MeTube

## Overview

This implementation adds intelligent Spotify support to MeTube by extracting playlist/album metadata and automatically searching for tracks on YouTube for download. Instead of blocking Spotify URLs, MeTube now processes them intelligently!

## How It Works

### For Users:
1. **Paste a Spotify URL** (track, album, or playlist)
2. **MeTube detects it** and shows an informative message
3. **Automatic processing** extracts track metadata from Spotify
4. **YouTube search** finds the best matches for each track
5. **Downloads begin** with proper naming and organization

### Example Workflow:
```
Spotify Playlist → Extract Track List → Search YouTube → Queue Downloads

"My Awesome Playlist" (50 tracks)
├── Track 1: "Artist - Song" → YouTube search → Download
├── Track 2: "Artist - Song" → YouTube search → Download
└── ... continues for all tracks
```

## Features

### ✅ What's New:
- **Spotify Track Support** - Single tracks found on YouTube
- **Spotify Album Support** - All album tracks downloaded in order
- **Spotify Playlist Support** - All playlist tracks downloaded
- **Smart Search** - Multiple search strategies for best YouTube matches
- **Progress Tracking** - See status as each track is processed
- **Organized Downloads** - Tracks numbered and named properly
- **Error Recovery** - Continues even if some tracks aren't found

### ⚙️ Technical Features:
- **Metadata Extraction** - Uses Spotify API (optional) or web scraping
- **Multiple Search Strategies** - Tries various query formats
- **Batch Processing** - Handles large playlists efficiently
- **Custom Naming** - Includes track numbers and artist info
- **Quality Options** - All existing MeTube quality settings work

## Installation & Setup

### 1. Install Dependencies
```bash
pip install spotipy requests
```

### 2. Optional: Spotify API Setup
For better metadata extraction, you can provide Spotify API credentials:

1. Go to [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)
2. Create a new app
3. Copy your Client ID and Client Secret
4. Add them to your MeTube configuration:

```bash
# Environment variables
export YTDL_OPTIONS='{"spotify_client_id": "your_client_id", "spotify_client_secret": "your_client_secret"}'

# Or in Docker
-e YTDL_OPTIONS='{"spotify_client_id": "your_client_id", "spotify_client_secret": "your_client_secret"}'
```

**Note:** The integration works without API credentials using web scraping fallbacks, but API access provides better metadata and supports playlists/albums.

## Usage Examples

### Supported URLs:
```
# Single tracks
https://open.spotify.com/track/4iV5W9uYEdYUVa79Axb7Rh

# Albums (downloads all tracks)
https://open.spotify.com/album/1DFixLWuPkv3KT3TnV35m3

# Playlists (downloads all tracks)
https://open.spotify.com/playlist/37i9dQZF1DX0XUsuxWHRQd

# Spotify URI format also works
spotify:track:4iV5W9uYEdYUVa79Axb7Rh
spotify:album:1DFixLWuPkv3KT3TnV35m3
```

### What Happens:

1. **Paste Spotify URL** → MeTube shows: "Spotify Playlist Detected: MeTube will search for all tracks in this playlist on YouTube and download them."

2. **Click Download** → Processing begins:
   ```
   Processing Spotify playlist: "Chill Vibes"
   Found 25 tracks in Spotify playlist
   Processing track 1/25: Billie Eilish - bad guy
   Found YouTube video: Billie Eilish - bad guy (Official Music Video)
   Successfully queued: Billie Eilish - bad guy
   Processing track 2/25: The Weeknd - Blinding Lights
   ...
   ```

3. **Downloads complete** with organized naming:
   ```
   01_Billie_Eilish_bad_guy.mp3
   02_The_Weeknd_Blinding_Lights.mp3
   03_Dua_Lipa_Don_t_Start_Now.mp3
   ...
   ```

## Configuration Options

### Search Behavior:
- **Playlist Item Limit** - Limit how many tracks to process
- **Custom Directories** - Organize downloads in folders
- **Quality Settings** - Audio/video quality as usual

### Search Strategies:
MeTube tries multiple search formats for each track:
1. `Artist - Track Name`
2. `Artist Track Name` 
3. `Primary Artist Track Name`
4. `Artist Track Name official`
5. `Artist Track Name audio`

## Limitations & Notes

### ⚠️ Important Considerations:
- **Search Accuracy** - YouTube matches may not always be exact
- **Availability** - Some tracks might not be available on YouTube
- **Quality Variation** - YouTube audio quality varies by video
- **Rate Limiting** - Large playlists process sequentially to avoid issues

### 🎯 Best Practices:
- **Verify Downloads** - Check that downloaded tracks match expectations
- **Use Audio Quality** - Set quality to "audio" for music-focused downloads
- **Monitor Progress** - Watch the progress for any failed tracks
- **Backup Playlists** - Keep your original Spotify playlists as reference

## Troubleshooting

### Common Issues:

**"No tracks found in Spotify playlist"**
- Solution: Add Spotify API credentials for better metadata access

**"Could not find YouTube video for track"**
- Some tracks may not be available on YouTube
- The search continues with remaining tracks

**"Failed to extract Spotify metadata"**
- Check your internet connection
- Verify the Spotify URL is correct and public

### Debug Mode:
Check the MeTube logs for detailed processing information:
```bash
docker logs your-metube-container
```

## Migration from Old Behavior

### Before (Blocking):
- Spotify URLs were blocked with error messages
- Users had to manually search for tracks

### After (Smart Integration):
- Spotify URLs are processed automatically
- Tracks are found and queued for download
- Users get organized, named downloads

No configuration changes needed - existing users will automatically get the new behavior!

## Technical Implementation

### Files Added/Modified:
- `app/spotify_utils.py` - New Spotify metadata extraction
- `app/ytdl.py` - Enhanced with Spotify processing
- `ui/src/app/app.component.ts` - Updated UI messages
- `ui/src/app/app.component.html` - New user feedback
- `Pipfile` - Added spotipy and requests dependencies

### Architecture:
```
Spotify URL → Metadata Extractor → Track List → YouTube Search → Download Queue
```

This implementation respects copyright and DRM by finding content on YouTube rather than attempting to download directly from Spotify.