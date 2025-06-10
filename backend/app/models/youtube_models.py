"""
YouTube data models for the music discovery system
"""
from dataclasses import dataclass
from typing import List, Optional

@dataclass
class YouTubeVideo:
    """Represents a YouTube video result."""
    title: str
    url: str
    channel_name: str
    view_count: str
    duration: str
    upload_date: str
    video_id: Optional[str] = None
    thumbnail: Optional[str] = None
    description: Optional[str] = None

    def __post_init__(self):
        """Extract video ID from URL if not provided."""
        if not self.video_id and self.url:
            # Extract video ID from YouTube URL
            import re
            match = re.search(r'(?:v=|/)([a-zA-Z0-9_-]{11})', self.url)
            if match:
                self.video_id = match.group(1)

@dataclass
class YouTubeSearchResult:
    """Represents the result of a YouTube search operation."""
    query: str
    videos: List[YouTubeVideo]
    total_results: int
    success: bool
    error_message: Optional[str] = None

    def __post_init__(self):
        """Update total_results based on videos list if not provided."""
        if self.total_results == 0 and self.videos:
            self.total_results = len(self.videos) 