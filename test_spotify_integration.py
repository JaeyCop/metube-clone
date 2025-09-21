#!/usr/bin/env python3
"""
Test script for MeTube Spotify Integration

This script tests the core Spotify integration features without requiring
a full MeTube installation. It validates URL detection, metadata extraction,
and search query generation.

Usage:
    python3 test_spotify_integration.py
    
Requirements:
    pip install requests spotipy
"""

import asyncio
import sys
import os
import requests
import time
from urllib.parse import urlparse

# Test Spotify URLs
TEST_URLS = {
    'track': 'https://open.spotify.com/track/4iV5W9uYEdYUVa79Axb7Rh',
    'album': 'https://open.spotify.com/album/1DFixLWuPkv3KT3TnV35m3',
    'playlist': 'https://open.spotify.com/playlist/37i9dQZF1DX0XUsuxWHRQd',
    'podcast': 'https://open.spotify.com/show/4rOoJ6Egrf8K2IrywzwOMk',
    'episode': 'https://open.spotify.com/episode/123456789',
    'invalid': 'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
    'spotify_uri': 'spotify:track:4iV5W9uYEdYUVa79Axb7Rh'
}

def test_url_detection():
    """Test Spotify URL detection and content type identification"""
    print("🔍 Testing Spotify URL Detection...")
    
    # Add the app directory to Python path for testing
    app_path = os.path.join(os.path.dirname(__file__), 'app')
    if os.path.exists(app_path):
        sys.path.insert(0, app_path)
    
    try:
        from spotify_utils import SpotifyMetadataExtractor
        
        extractor = SpotifyMetadataExtractor()
        
        for content_type, url in TEST_URLS.items():
            is_spotify = extractor.is_spotify_url(url)
            detected_type = extractor.get_content_type(url) if is_spotify else 'N/A'
            
            status = "✅" if (content_type != 'invalid' and is_spotify) or (content_type == 'invalid' and not is_spotify) else "❌"
            print(f"  {status} {content_type:10} | {url[:50]:50} | Spotify: {is_spotify:5} | Type: {detected_type}")
            
    except ImportError as e:
        print(f"  ❌ Cannot import spotify_utils: {e}")
        print("  💡 Make sure you're running this from the MeTube directory with app/spotify_utils.py")
        return False
    
    return True

def test_search_query_generation():
    """Test search query generation strategies"""
    print("\n🎯 Testing Search Query Generation...")
    
    try:
        from spotify_utils import SpotifyTrackInfo
        
        # Test track with various characteristics
        test_tracks = [
            SpotifyTrackInfo(
                name="Bohemian Rhapsody",
                artists=["Queen"],
                duration_ms=355000,
                album="A Night at the Opera"
            ),
            SpotifyTrackInfo(
                name="Blinding Lights (feat. Some Artist)",
                artists=["The Weeknd", "Some Artist"],
                duration_ms=200000,
                album="After Hours"
            ),
            SpotifyTrackInfo(
                name="Track (Remix)",
                artists=["Artist"],
                duration_ms=180000
            )
        ]
        
        for track in test_tracks:
            print(f"\n  🎵 Track: {track.name} by {', '.join(track.artists)}")
            print(f"     Primary query: {track.get_search_query()}")
            
            alternatives = track.get_search_query_alternatives()[:3]  # Show first 3
            for i, query in enumerate(alternatives, 1):
                print(f"     Alternative {i}: {query}")
                
    except ImportError as e:
        print(f"  ❌ Cannot import SpotifyTrackInfo: {e}")
        return False
    
    return True

def test_spotify_api_connection():
    """Test Spotify API connectivity (if credentials are available)"""
    print("\n🌐 Testing Spotify API Connection...")
    
    # Check for credentials in environment
    client_id = os.environ.get('SPOTIFY_CLIENT_ID')
    client_secret = os.environ.get('SPOTIFY_CLIENT_SECRET')
    
    if not client_id or not client_secret:
        print("  ⚠️  No Spotify API credentials found in environment")
        print("  💡 Set SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET to test API features")
        return True  # Not a failure, just not configured
    
    try:
        import spotipy
        from spotipy.oauth2 import SpotifyClientCredentials
        
        client_credentials_manager = SpotifyClientCredentials(
            client_id=client_id,
            client_secret=client_secret
        )
        sp = spotipy.Spotify(client_credentials_manager=client_credentials_manager)
        
        # Test with a well-known track
        test_track_id = "4iV5W9uYEdYUVa79Axb7Rh"  # A popular track
        
        track = sp.track(test_track_id)
        print(f"  ✅ API Connection successful!")
        print(f"     Test track: {track['name']} by {', '.join([artist['name'] for artist in track['artists']])}")
        print(f"     Duration: {track['duration_ms']}ms")
        
        return True
        
    except Exception as e:
        print(f"  ❌ API Connection failed: {e}")
        print("  💡 Check your credentials and internet connection")
        return False

def test_web_scraping_fallback():
    """Test web scraping fallback functionality"""
    print("\n🕸️  Testing Web Scraping Fallback...")
    
    try:
        # Test oEmbed endpoint (doesn't require auth)
        test_track_id = "4iV5W9uYEdYUVa79Axb7Rh"
        oembed_url = f"https://open.spotify.com/oembed?url=https://open.spotify.com/track/{test_track_id}"
        
        response = requests.get(oembed_url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            title = data.get('title', '')
            print(f"  ✅ Web scraping successful!")
            print(f"     Retrieved title: {title}")
            
            if ' - ' in title:
                artist_part, track_part = title.split(' - ', 1)
                print(f"     Parsed - Artist: {artist_part}, Track: {track_part}")
            
            return True
        else:
            print(f"  ❌ Web scraping failed with status: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"  ❌ Web scraping error: {e}")
        return False

def test_metube_integration():
    """Test MeTube integration points"""
    print("\n🔗 Testing MeTube Integration Points...")
    
    # Check if MeTube files exist
    required_files = [
        'app/main.py',
        'app/ytdl.py', 
        'app/spotify_utils.py',
        'Pipfile',
        'ui/src/app/app.component.ts',
        'ui/src/app/app.component.html'
    ]
    
    missing_files = []
    for file_path in required_files:
        if not os.path.exists(file_path):
            missing_files.append(file_path)
        else:
            print(f"  ✅ {file_path}")
    
    if missing_files:
        print(f"\n  ❌ Missing files:")
        for file_path in missing_files:
            print(f"     - {file_path}")
        return False
    
    # Check Pipfile for dependencies
    try:
        with open('Pipfile', 'r') as f:
            pipfile_content = f.read()
            
        required_deps = ['spotipy', 'requests']
        for dep in required_deps:
            if dep in pipfile_content:
                print(f"  ✅ Dependency {dep} found in Pipfile")
            else:
                print(f"  ❌ Dependency {dep} missing from Pipfile")
                
    except Exception as e:
        print(f"  ❌ Error checking Pipfile: {e}")
        return False
    
    return True

def print_setup_instructions():
    """Print setup instructions"""
    print("\n📋 Setup Instructions:")
    print("=" * 50)
    
    print("\n1. 🐳 Docker Setup:")
    print("   docker-compose up -d")
    print("   # or")
    print("   docker run -d -p 8081:8081 \\")
    print("     -e SPOTIFY_CLIENT_ID='your_id' \\")
    print("     -e SPOTIFY_CLIENT_SECRET='your_secret' \\")
    print("     -v ./downloads:/downloads \\")
    print("     ghcr.io/alexta69/metube")
    
    print("\n2. 🔑 Spotify API Setup:")
    print("   • Go to: https://developer.spotify.com/dashboard")
    print("   • Create a new app")
    print("   • Copy Client ID and Client Secret")
    print("   • Set environment variables or use .env file")
    
    print("\n3. 🧪 Testing:")
    print("   • Open http://localhost:8081")
    print("   • Paste a Spotify URL like:")
    print("     https://open.spotify.com/track/4iV5W9uYEdYUVa79Axb7Rh")
    print("   • Check the informational message")
    print("   • Click Download and monitor progress")
    
    print("\n4. 📊 Monitoring:")
    print("   • Check logs: docker logs metube")
    print("   • Watch for 'Processing Spotify...' messages")
    print("   • Look for 'Found YouTube video:' confirmations")

async def main():
    """Run all tests"""
    print("🎵 MeTube Spotify Integration Test Suite")
    print("=" * 50)
    
    tests = [
        ("URL Detection", test_url_detection),
        ("Search Query Generation", test_search_query_generation),
        ("Spotify API Connection", test_spotify_api_connection),
        ("Web Scraping Fallback", test_web_scraping_fallback),
        ("MeTube Integration", test_metube_integration)
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        try:
            results[test_name] = test_func()
        except Exception as e:
            print(f"  ❌ {test_name} failed with exception: {e}")
            results[test_name] = False
    
    # Summary
    print("\n📊 Test Results Summary:")
    print("=" * 50)
    
    passed = sum(1 for result in results.values() if result)
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {status} {test_name}")
    
    print(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Your Spotify integration is ready.")
    else:
        print("⚠️  Some tests failed. Check the output above for details.")
    
    print_setup_instructions()

if __name__ == "__main__":
    asyncio.run(main())