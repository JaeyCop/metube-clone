# Spotify Support in MeTube

MeTube now includes intelligent Spotify integration that extracts playlist/album metadata and searches for tracks on YouTube for download.

## What's Supported

### ✅ Music Content via YouTube Search
- **Spotify Tracks** - Extracts track metadata and searches YouTube for the best match
- **Spotify Albums** - Downloads all tracks in an album by searching YouTube
- **Spotify Playlists** - Downloads all tracks in a playlist by searching YouTube
- **Smart Search** - Uses multiple search strategies and fallbacks for better accuracy

### ✅ Advanced Features
- **Metadata Preservation** - Track names, artists, and album info are used for searches
- **Sequential Processing** - Tracks are processed one by one with progress feedback
- **Error Handling** - Continues processing even if some tracks can't be found
- **Custom Naming** - Downloaded files include track numbers and artist information

### ⚠️ Podcast Content (Limited)
- **Spotify Podcasts** - Some podcast content may be downloadable directly
- **Podcast Episodes** - Individual episodes may be accessible in some cases

## How It Works

### The Process
1. **URL Detection** - MeTube recognizes Spotify URLs and identifies content type
2. **Metadata Extraction** - Track information is extracted from Spotify (artist, title, album)
3. **YouTube Search** - Each track is searched on YouTube using intelligent queries
4. **Download Processing** - Found YouTube videos are added to the download queue
5. **Progress Tracking** - Users see progress as each track is processed

### Search Strategies
MeTube uses multiple search approaches to find the best YouTube matches:
- `Artist - Track Name`
- `Artist Track Name` (without dash)
- `Artist Track Name official`
- `Artist Track Name audio`
- Primary artist only (for collaborations)

### Configuration Options
- **Spotify API Credentials** - Optional Spotify Client ID/Secret for better metadata
- **Playlist Limits** - Respect existing playlist item limits
- **Custom Directories** - Albums/playlists can be organized in folders
- **Quality Settings** - All existing quality/format options work with Spotify content

## Usage Examples

### Supported URLs (Music Content via YouTube)
```
# Single tracks - searches YouTube and downloads best match
https://open.spotify.com/track/4iV5W9uYEdYUVa79Axb7Rh

# Albums - downloads all tracks by searching YouTube
https://open.spotify.com/album/1DFixLWuPkv3KT3TnV35m3

# Playlists - downloads all tracks by searching YouTube  
https://open.spotify.com/playlist/37i9dQZF1DX0XUsuxWHRQd

# Spotify URI format also works
spotify:track:4iV5W9uYEdYUVa79Axb7Rh
spotify:album:1DFixLWuPkv3KT3TnV35m3
```

### Podcast URLs (Direct Download Attempt)
```
# Podcasts (may work with DRM limitations)
https://open.spotify.com/show/4rOoJ6Egrf8K2IrywzwOMk
https://open.spotify.com/episode/1234567890
```

## User Experience

### When entering a Spotify URL:

1. **Music Content** - You'll see an immediate warning explaining that the content is DRM-protected and cannot be downloaded, with suggestions to use Spotify's official features instead.

2. **Podcast Content** - You'll see a notice that podcast content may be supported, and MeTube will attempt to process it.

3. **Download Attempt** - If you try to download DRM-protected music, you'll get a clear error message explaining the limitations and suggesting alternatives.

## Technical Implementation

### Spotify URL Detection
- Recognizes `https://open.spotify.com/*` URLs
- Supports `spotify:*` URI format
- Identifies content types: track, album, playlist, show/podcast, episode

### Content Handling
- **Music content**: Blocked at both frontend and backend levels
- **Podcast content**: Allowed to attempt download with appropriate warnings
- **Unknown content**: Treated as potentially DRM-protected with warnings

### Error Messages
- Context-aware messages based on content type
- Suggestions for alternatives (official Spotify features, YouTube search)
- Clear explanations of DRM limitations

## Limitations

1. **DRM Protection** - Most Spotify content is protected and cannot be downloaded
2. **API Restrictions** - Spotify blocks most programmatic access to their content
3. **Podcast Availability** - Even podcast content may be restricted depending on licensing
4. **No Workarounds** - This implementation respects DRM and does not attempt to bypass protections

## Future Enhancements

Potential improvements that could be added:

1. **YouTube Search Integration** - Automatic search for Spotify tracks on YouTube
2. **Playlist Export** - Extract track lists from Spotify playlists for manual searching
3. **Alternative Source Suggestions** - Recommend other platforms where content might be available
4. **Batch Processing** - Handle multiple Spotify URLs with bulk feedback

## Why This Approach?

This implementation prioritizes:
- **User Education** - Clear communication about what's possible and what isn't
- **Respectful Handling** - No attempts to bypass DRM or terms of service
- **Good UX** - Immediate feedback rather than failed download attempts
- **Transparency** - Honest about limitations while exploring what's possible

The goal is to provide the best possible experience within legal and technical constraints, while educating users about the realities of content protection in modern streaming services.