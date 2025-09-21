# Setting Up Spotify API for MeTube

This guide walks you through setting up Spotify API credentials to enhance MeTube's Spotify integration.

## Why Set Up Spotify API?

### With API Credentials:
- ✅ **Full playlist/album support** - Extract metadata from any public Spotify playlist or album
- ✅ **Better track information** - Get accurate artist names, track titles, durations, and album info
- ✅ **Reliable metadata** - No rate limiting or scraping issues
- ✅ **Large playlists** - Handle playlists with hundreds of tracks

### Without API Credentials:
- ⚠️ **Limited functionality** - Only basic track metadata via web scraping
- ⚠️ **No playlist/album support** - Cannot extract track lists from playlists/albums
- ⚠️ **Unreliable** - Web scraping may break or be rate limited

## Step-by-Step Setup

### 1. Create a Spotify Developer Account
1. Go to [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)
2. Log in with your Spotify account (create one if needed)
3. Accept the terms of service

### 2. Create a New App
1. Click **"Create an App"**
2. Fill in the details:
   - **App name**: `MeTube Integration` (or any name you prefer)
   - **App description**: `Spotify integration for MeTube music downloader`
   - **Website**: `http://localhost:8081` (or your MeTube URL)
   - **Redirect URI**: Leave blank (not needed for this use case)
3. Check the boxes to agree to terms
4. Click **"Create"**

### 3. Get Your Credentials
1. In your new app's dashboard, you'll see:
   - **Client ID** - Copy this value
   - **Client Secret** - Click "Show Client Secret" and copy this value

⚠️ **Important**: Keep your Client Secret private! Don't share it publicly.

### 4. Configure MeTube

#### Option A: Environment Variables (Recommended)
```bash
# Add to your docker run command
docker run -d -p 8081:8081 \
  -e SPOTIFY_CLIENT_ID="your_client_id_here" \
  -e SPOTIFY_CLIENT_SECRET="your_client_secret_here" \
  -v /path/to/downloads:/downloads \
  ghcr.io/alexta69/metube
```

#### Option B: Docker Compose
```yaml
services:
  metube:
    image: ghcr.io/alexta69/metube
    environment:
      - SPOTIFY_CLIENT_ID=your_client_id_here
      - SPOTIFY_CLIENT_SECRET=your_client_secret_here
    # ... other configuration
```

#### Option C: YTDL_OPTIONS
```bash
-e YTDL_OPTIONS='{"spotify_client_id": "your_id", "spotify_client_secret": "your_secret"}'
```

### 5. Test the Integration
1. Restart MeTube if it was already running
2. Try pasting a Spotify playlist URL like:
   ```
   https://open.spotify.com/playlist/37i9dQZF1DX0XUsuxWHRQd
   ```
3. You should see a message: "Spotify Playlist Detected: MeTube will search for all tracks in this playlist on YouTube and download them."
4. Click "Download" and watch the logs for track processing

## Troubleshooting

### "No tracks found in Spotify playlist"
- **Check credentials**: Make sure Client ID and Secret are correct
- **Check app status**: Ensure your Spotify app is not in "Development Mode" restrictions
- **Check URL**: Make sure the Spotify URL is public and accessible

### "Failed to extract Spotify metadata"
- **Rate limiting**: Wait a few minutes and try again
- **Invalid credentials**: Double-check your Client ID and Secret
- **Network issues**: Check your internet connection

### Logs showing authentication errors
- **Verify environment variables**: Check that the credentials are being loaded correctly
- **Restart container**: Environment changes require a restart
- **Check quotes**: Make sure credentials don't have extra quotes or spaces

## Security Best Practices

1. **Use environment variables**: Don't hardcode credentials in configuration files
2. **Restrict access**: If possible, limit your Spotify app to specific IP ranges
3. **Monitor usage**: Check your Spotify app dashboard for unusual activity
4. **Rotate secrets**: Periodically regenerate your Client Secret

## API Limits

Spotify's API has generous rate limits for this use case:
- **Rate limit**: 100 requests per minute (more than enough for playlist processing)
- **No cost**: The API is free for this type of usage
- **No user authorization**: MeTube only accesses public metadata, no user data

## Example Configuration Files

### Complete docker-compose.yml
```yaml
version: '3.8'
services:
  metube:
    image: ghcr.io/alexta69/metube
    container_name: metube
    restart: unless-stopped
    ports:
      - "8081:8081"
    volumes:
      - ./downloads:/downloads
    environment:
      - UID=1000
      - GID=1000
      - SPOTIFY_CLIENT_ID=${SPOTIFY_CLIENT_ID}
      - SPOTIFY_CLIENT_SECRET=${SPOTIFY_CLIENT_SECRET}
      - CUSTOM_DIRS=true
      - OUTPUT_TEMPLATE_PLAYLIST=%(playlist_title)s/%(playlist_index)s-%(title)s.%(ext)s
```

### .env file
```env
SPOTIFY_CLIENT_ID=your_actual_client_id_here
SPOTIFY_CLIENT_SECRET=your_actual_client_secret_here
```

## What's Next?

Once configured, you can:
- Paste any public Spotify playlist URL to download all tracks
- Download individual tracks or entire albums
- Enjoy organized downloads with proper naming
- Process large playlists efficiently

The integration will automatically search YouTube for each track and download the best matches!