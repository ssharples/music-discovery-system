"""
Enhanced Data Extractors
Fixed extraction methods for YouTube, Spotify, and Musixmatch
"""

import json
import re
import logging
from typing import Dict, Any, List, Optional, Tuple
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

class EnhancedYouTubeExtractor:
    """Enhanced YouTube data extraction with ytInitialData parsing"""
    
    @staticmethod
    def extract_video_data(html: str) -> Dict[str, Any]:
        """Extract video data from YouTube video page"""
        data = {
            "title": "",
            "channel_name": "",
            "channel_url": "",
            "channel_id": "",
            "description": "",
            "view_count": "",
            "duration": "",
            "upload_date": "",
            "subscriber_count": ""
        }
        
        try:
            # First try to extract from ytInitialData JavaScript
            yt_data = EnhancedYouTubeExtractor._extract_yt_initial_data(html)
            if yt_data:
                video_data = EnhancedYouTubeExtractor._parse_video_details(yt_data)
                data.update(video_data)
            
            # Fallback to HTML parsing if JavaScript extraction fails
            if not data["title"]:
                html_data = EnhancedYouTubeExtractor._extract_from_html(html)
                data.update(html_data)
                
        except Exception as e:
            logger.error(f"Error extracting YouTube video data: {e}")
        
        return data
    
    @staticmethod
    def extract_search_videos(html: str, max_results: int = 50) -> List[Dict[str, Any]]:
        """Extract videos from YouTube search results"""
        videos = []
        
        try:
            # Extract from ytInitialData first
            yt_data = EnhancedYouTubeExtractor._extract_yt_initial_data(html)
            if yt_data:
                videos = EnhancedYouTubeExtractor._parse_search_results(yt_data, max_results)
            
            # Fallback to HTML parsing
            if len(videos) < 5:  # If we got very few results, try HTML parsing
                html_videos = EnhancedYouTubeExtractor._extract_videos_from_html(html, max_results)
                videos.extend(html_videos)
                
                # Remove duplicates by video ID
                seen_ids = set()
                unique_videos = []
                for video in videos:
                    video_id = EnhancedYouTubeExtractor._extract_video_id(video.get("url", ""))
                    if video_id and video_id not in seen_ids:
                        seen_ids.add(video_id)
                        unique_videos.append(video)
                
                videos = unique_videos[:max_results]
                
        except Exception as e:
            logger.error(f"Error extracting YouTube search videos: {e}")
        
        return videos
    
    @staticmethod
    def _extract_yt_initial_data(html: str) -> Optional[Dict[str, Any]]:
        """Extract ytInitialData from HTML"""
        patterns = [
            r'var ytInitialData = ({.*?});',
            r'window\["ytInitialData"\] = ({.*?});',
            r'ytInitialData":\s*({.*?})(?:,|\s*</script>)',
            r'ytInitialData = ({.*?});'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, html, re.DOTALL)
            if match:
                try:
                    data = json.loads(match.group(1))
                    logger.info(f"✅ Successfully parsed ytInitialData ({len(str(data)):,} chars)")
                    return data
                except json.JSONDecodeError as e:
                    logger.warning(f"Failed to parse ytInitialData: {e}")
                    continue
        
        logger.warning("❌ No ytInitialData found in HTML")
        return None
    
    @staticmethod
    def _parse_video_details(yt_data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse video details from ytInitialData"""
        data = {}
        
        try:
            # Navigate to video details
            contents = yt_data.get("contents", {})
            two_column = contents.get("twoColumnWatchNextResults", {})
            results = two_column.get("results", {}).get("results", {})
            contents_list = results.get("contents", [])
            
            for content in contents_list:
                # Primary video info (title, views)
                if "videoPrimaryInfoRenderer" in content:
                    primary = content["videoPrimaryInfoRenderer"]
                    
                    # Extract title
                    title_info = primary.get("title", {})
                    if "runs" in title_info and title_info["runs"]:
                        data["title"] = title_info["runs"][0].get("text", "")
                    
                    # Extract view count
                    view_info = primary.get("viewCount", {})
                    if "videoViewCountRenderer" in view_info:
                        view_count = view_info["videoViewCountRenderer"].get("viewCount", {})
                        if "simpleText" in view_count:
                            data["view_count"] = view_count["simpleText"]
                        elif "runs" in view_count and view_count["runs"]:
                            data["view_count"] = view_count["runs"][0].get("text", "")
                
                # Secondary video info (channel, description)
                elif "videoSecondaryInfoRenderer" in content:
                    secondary = content["videoSecondaryInfoRenderer"]
                    
                    # Extract channel info
                    owner = secondary.get("owner", {}).get("videoOwnerRenderer", {})
                    if owner:
                        # Channel name
                        title = owner.get("title", {})
                        if "runs" in title and title["runs"]:
                            data["channel_name"] = title["runs"][0].get("text", "")
                            
                            # Channel URL
                            nav_endpoint = title["runs"][0].get("navigationEndpoint", {})
                            if "commandMetadata" in nav_endpoint:
                                channel_url = nav_endpoint["commandMetadata"].get("webCommandMetadata", {}).get("url", "")
                                if channel_url:
                                    data["channel_url"] = f"https://www.youtube.com{channel_url}"
                        
                        # Subscriber count
                        subscriber_info = owner.get("subscriberCountText", {})
                        if "simpleText" in subscriber_info:
                            data["subscriber_count"] = subscriber_info["simpleText"]
                    
                    # Extract description
                    description = secondary.get("description", {})
                    if "runs" in description:
                        desc_parts = []
                        for run in description["runs"]:
                            if "text" in run:
                                desc_parts.append(run["text"])
                        data["description"] = "".join(desc_parts)
            
            # Try to extract from sidebar as well
            sidebar = two_column.get("secondaryResults", {})
            # Could extract related videos here if needed
            
        except Exception as e:
            logger.error(f"Error parsing video details from ytInitialData: {e}")
        
        return data
    
    @staticmethod
    def _parse_search_results(yt_data: Dict[str, Any], max_results: int) -> List[Dict[str, Any]]:
        """Parse search results from ytInitialData"""
        videos = []
        
        try:
            # Navigate to search results
            contents = yt_data.get("contents", {})
            two_column = contents.get("twoColumnSearchResultsRenderer", {})
            primary_contents = two_column.get("primaryContents", {})
            section_list = primary_contents.get("sectionListRenderer", {})
            contents_list = section_list.get("contents", [])
            
            for section in contents_list:
                if "itemSectionRenderer" in section:
                    items = section["itemSectionRenderer"].get("contents", [])
                    
                    for item in items:
                        if "videoRenderer" in item:
                            video_data = EnhancedYouTubeExtractor._parse_video_renderer(item["videoRenderer"])
                            if video_data:
                                videos.append(video_data)
                                if len(videos) >= max_results:
                                    break
                    
                    if len(videos) >= max_results:
                        break
        
        except Exception as e:
            logger.error(f"Error parsing search results from ytInitialData: {e}")
        
        return videos[:max_results]
    
    @staticmethod
    def _parse_video_renderer(renderer: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Parse individual video renderer from search results"""
        try:
            video_data = {}
            
            # Video ID and URL
            video_id = renderer.get("videoId", "")
            if video_id:
                video_data["url"] = f"https://www.youtube.com/watch?v={video_id}"
                video_data["video_id"] = video_id
            
            # Title
            title = renderer.get("title", {})
            if "runs" in title and title["runs"]:
                video_data["title"] = title["runs"][0].get("text", "")
            elif "simpleText" in title:
                video_data["title"] = title["simpleText"]
            
            # Channel name
            owner_text = renderer.get("ownerText", {})
            if "runs" in owner_text and owner_text["runs"]:
                video_data["channel_name"] = owner_text["runs"][0].get("text", "")
            
            # View count
            view_count = renderer.get("viewCountText", {})
            if "simpleText" in view_count:
                video_data["view_count"] = view_count["simpleText"]
            elif "runs" in view_count and view_count["runs"]:
                video_data["view_count"] = view_count["runs"][0].get("text", "")
            
            # Duration
            duration = renderer.get("lengthText", {})
            if "simpleText" in duration:
                video_data["duration"] = duration["simpleText"]
            
            # Published time
            published_time = renderer.get("publishedTimeText", {})
            if "simpleText" in published_time:
                video_data["upload_date"] = published_time["simpleText"]
            
            # Description snippet
            description_snippet = renderer.get("descriptionSnippet", {})
            if "runs" in description_snippet:
                desc_parts = []
                for run in description_snippet["runs"]:
                    if "text" in run:
                        desc_parts.append(run["text"])
                video_data["description"] = "".join(desc_parts)
            
            # Only return if we have essential data
            if video_data.get("title") and video_data.get("url"):
                return video_data
                
        except Exception as e:
            logger.error(f"Error parsing video renderer: {e}")
        
        return None
    
    @staticmethod
    def _extract_from_html(html: str) -> Dict[str, Any]:
        """Fallback HTML extraction"""
        data = {}
        
        try:
            soup = BeautifulSoup(html, 'html.parser')
            
            # Title from meta tags
            title_tag = soup.find('meta', property='og:title')
            if title_tag:
                data["title"] = title_tag.get('content', '').replace(' - YouTube', '')
            
            # Description from meta tags
            desc_tag = soup.find('meta', property='og:description')
            if desc_tag:
                data["description"] = desc_tag.get('content', '')
            
            # Try to extract from JSON-LD structured data
            scripts = soup.find_all('script', type='application/ld+json')
            for script in scripts:
                try:
                    json_data = json.loads(script.string)
                    if isinstance(json_data, list):
                        json_data = json_data[0]
                    
                    if json_data.get('@type') == 'VideoObject':
                        data["title"] = json_data.get("name", data.get("title", ""))
                        data["description"] = json_data.get("description", data.get("description", ""))
                        
                        # Channel info
                        author = json_data.get("author", {})
                        if isinstance(author, dict):
                            data["channel_name"] = author.get("name", "")
                        
                except json.JSONDecodeError:
                    continue
            
        except Exception as e:
            logger.error(f"Error in HTML fallback extraction: {e}")
        
        return data
    
    @staticmethod
    def _extract_videos_from_html(html: str, max_results: int) -> List[Dict[str, Any]]:
        """Fallback HTML extraction for search results"""
        videos = []
        
        try:
            soup = BeautifulSoup(html, 'html.parser')
            
            # Look for video links
            video_links = soup.find_all('a', href=re.compile(r'/watch\?v='))
            
            for link in video_links[:max_results]:
                video_data = {}
                
                # URL and video ID
                href = link.get('href')
                if href:
                    if href.startswith('/'):
                        video_data["url"] = f"https://www.youtube.com{href}"
                    else:
                        video_data["url"] = href
                    
                    video_data["video_id"] = EnhancedYouTubeExtractor._extract_video_id(video_data["url"])
                
                # Title
                title = link.get('title') or link.get_text(strip=True)
                if title:
                    video_data["title"] = title
                
                if video_data.get("title") and video_data.get("url"):
                    videos.append(video_data)
        
        except Exception as e:
            logger.error(f"Error in HTML video extraction: {e}")
        
        return videos
    
    @staticmethod
    def _extract_video_id(url: str) -> str:
        """Extract video ID from YouTube URL"""
        patterns = [
            r'[?&]v=([a-zA-Z0-9_-]{11})',
            r'/watch/([a-zA-Z0-9_-]{11})',
            r'/embed/([a-zA-Z0-9_-]{11})',
            r'youtu\.be/([a-zA-Z0-9_-]{11})'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        
        return ""


class EnhancedSpotifyExtractor:
    """Enhanced Spotify data extraction"""
    
    @staticmethod
    def extract_artist_data(html: str) -> Dict[str, Any]:
        """Extract artist data from Spotify artist page"""
        data = {
            "artist_name": "",
            "monthly_listeners": "",
            "followers": "",
            "biography": "",
            "top_tracks": [],
            "genres": [],
            "images": []
        }
        
        try:
            # Extract from page title
            title_match = re.search(r'<title>([^|]+) \| Spotify</title>', html)
            if title_match:
                data["artist_name"] = title_match.group(1).strip()
            
            # Extract monthly listeners - multiple patterns
            listener_patterns = [
                r'(\d{1,3}(?:,\d{3})*)\s+monthly listeners',
                r'(\d{1,3}(?:\.\d+)?K)\s+monthly listeners',
                r'(\d{1,3}(?:\.\d+)?M)\s+monthly listeners',
                r'"monthlyListeners":(\d+)',
                r'monthly listeners.*?(\d{1,3}(?:,\d{3})*)',
                r'listeners.*?(\d{1,3}(?:\.\d+)?[KM]?)'
            ]
            
            for pattern in listener_patterns:
                match = re.search(pattern, html, re.IGNORECASE)
                if match:
                    data["monthly_listeners"] = match.group(1)
                    break
            
            # Extract followers
            follower_patterns = [
                r'(\d{1,3}(?:,\d{3})*)\s+followers',
                r'(\d{1,3}(?:\.\d+)?K)\s+followers',
                r'(\d{1,3}(?:\.\d+)?M)\s+followers',
                r'"followers":{"total":(\d+)'
            ]
            
            for pattern in follower_patterns:
                match = re.search(pattern, html, re.IGNORECASE)
                if match:
                    data["followers"] = match.group(1)
                    break
            
            # Extract biography from meta description
            bio_patterns = [
                r'<meta name="description" content="Listen to ([^"]+) on Spotify',
                r'<meta property="og:description" content="([^"]+)"',
                r'"biography":"([^"]+)"'
            ]
            
            for pattern in bio_patterns:
                match = re.search(pattern, html)
                if match:
                    data["biography"] = match.group(1)
                    break
            
            # Extract top tracks - look for track names in various formats
            track_patterns = [
                r'"name":"([^"]+)"[^}]*"type":"track"',
                r'data-testid="track-name"[^>]*>([^<]+)',
                r'"title":"([^"]+)"[^}]*"uri":"spotify:track:',
                r'<div[^>]*track[^>]*>([^<]+)</div>',
                r'"track":\s*{\s*"name":\s*"([^"]+)"'
            ]
            
            tracks = set()  # Use set to avoid duplicates
            for pattern in track_patterns:
                matches = re.findall(pattern, html)
                for match in matches:
                    track_name = match.strip()
                    if len(track_name) > 1 and track_name not in ['', ' ', 'undefined']:
                        tracks.add(track_name)
            
            data["top_tracks"] = list(tracks)[:10]  # Top 10 tracks
            
            # Extract genres
            genre_pattern = r'"genres":\[([^\]]+)\]'
            genre_match = re.search(genre_pattern, html)
            if genre_match:
                genre_str = genre_match.group(1)
                genres = [g.strip().strip('"') for g in genre_str.split(',')]
                data["genres"] = genres
            
        except Exception as e:
            logger.error(f"Error extracting Spotify data: {e}")
        
        return data


class EnhancedMusixmatchExtractor:
    """Enhanced Musixmatch lyrics extraction"""
    
    @staticmethod
    def extract_lyrics_data(html: str) -> Dict[str, Any]:
        """Extract lyrics data from Musixmatch page"""
        data = {
            "song_title": "",
            "artist_name": "",
            "lyrics": "",
            "album": "",
            "year": ""
        }
        
        try:
            # Extract from page title
            title_match = re.search(r'<title>([^-]+) - ([^-]+) lyrics.*?</title>', html)
            if title_match:
                data["artist_name"] = title_match.group(1).strip()
                data["song_title"] = title_match.group(2).strip()
            
            # Extract song title from various sources
            title_patterns = [
                r'<h1[^>]*class="[^"]*mxm-track-title[^"]*"[^>]*>([^<]+)</h1>',
                r'"track_name":"([^"]+)"',
                r'<meta property="og:title" content="([^"]*)"',
                r'data-track-name="([^"]*)"'
            ]
            
            for pattern in title_patterns:
                match = re.search(pattern, html)
                if match:
                    title = match.group(1).strip()
                    if title and not data["song_title"]:
                        data["song_title"] = title
                    break
            
            # Extract artist name
            artist_patterns = [
                r'<h2[^>]*class="[^"]*mxm-track-artist[^"]*"[^>]*>([^<]+)</h2>',
                r'"artist_name":"([^"]+)"',
                r'<a[^>]*href="/artist/[^"]*"[^>]*>([^<]+)</a>',
                r'data-artist-name="([^"]*)"'
            ]
            
            for pattern in artist_patterns:
                match = re.search(pattern, html)
                if match:
                    artist = match.group(1).strip()
                    if artist and not data["artist_name"]:
                        data["artist_name"] = artist
                    break
            
            # Extract lyrics - multiple strategies
            lyrics_patterns = [
                # Standard lyrics container
                r'<div[^>]*class="[^"]*mxm-lyrics__content[^"]*"[^>]*>(.*?)</div>',
                # Lyrics span elements
                r'<span[^>]*class="[^"]*lyrics__content__ok[^"]*"[^>]*>(.*?)</span>',
                # JSON lyrics
                r'"lyrics_body":"([^"]+)"',
                # P tag lyrics
                r'<p[^>]*class="[^"]*lyrics[^"]*"[^>]*>(.*?)</p>',
                # Alternative lyrics containers
                r'<div[^>]*data-lyrics[^>]*>(.*?)</div>',
                r'class="lyrics"[^>]*>(.*?)</(?:div|span)>'
            ]
            
            for pattern in lyrics_patterns:
                match = re.search(pattern, html, re.DOTALL | re.IGNORECASE)
                if match:
                    lyrics_html = match.group(1)
                    
                    # Clean HTML tags and extract text
                    soup = BeautifulSoup(lyrics_html, 'html.parser')
                    
                    # Replace <br> tags with newlines
                    for br in soup.find_all("br"):
                        br.replace_with("\n")
                    
                    lyrics_text = soup.get_text()
                    
                    # Clean up whitespace
                    lyrics_text = re.sub(r'\n\s*\n', '\n\n', lyrics_text)
                    lyrics_text = lyrics_text.strip()
                    
                    if len(lyrics_text) > 20:  # Ensure we have substantial lyrics
                        data["lyrics"] = lyrics_text
                        break
            
            # If no lyrics found, try to extract from page text
            if not data["lyrics"]:
                # Look for structured data or JSON containing lyrics
                json_patterns = [
                    r'"lyrics":\s*"([^"]+)"',
                    r'"body":\s*"([^"]+)"',
                    r'"text":\s*"([^"]+)"'
                ]
                
                for pattern in json_patterns:
                    match = re.search(pattern, html)
                    if match:
                        lyrics = match.group(1)
                        # Decode escaped characters
                        lyrics = lyrics.replace('\\n', '\n').replace('\\"', '"').replace('\\\\', '\\')
                        if len(lyrics) > 20:
                            data["lyrics"] = lyrics
                            break
            
        except Exception as e:
            logger.error(f"Error extracting Musixmatch data: {e}")
        
        return data


# Export classes for easy import
__all__ = ['EnhancedYouTubeExtractor', 'EnhancedSpotifyExtractor', 'EnhancedMusixmatchExtractor']