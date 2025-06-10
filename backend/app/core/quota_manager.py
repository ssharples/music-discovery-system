"""
Advanced quota management system with caching and rate limiting
"""
import asyncio
import time
from typing import Dict, Any, Optional
from datetime import datetime, timedelta, timezone
import logging
from collections import defaultdict

from app.core.config import settings

logger = logging.getLogger(__name__)

class QuotaManager:
    """Advanced quota management with per-operation cost tracking and caching"""
    
    # API operation costs
    YOUTUBE_COSTS = {
        'search': 100,
        'videos': 1,
        'channels': 1,
        'captions': 50,
        'comments': 1,
        'channel_videos': 1,
        'video_details': 1
    }
    
    SPOTIFY_COSTS = {
        'search': 1,
        'artist_details': 1,
        'top_tracks': 1,
        'album_tracks': 1
    }
    
    
    def __init__(self):
        self._usage_cache = defaultdict(int)
        self._rate_limits = defaultdict(list)  # Track request timestamps
        self._last_reset = {}
        self._cache = {}  # Response cache
        self._cache_ttl = {}  # Cache TTL tracking
        
        # Daily limits
        self._daily_limits = {
            'youtube': settings.YOUTUBE_QUOTA_PER_DAY,
            'spotify': settings.SPOTIFY_RATE_LIMIT * 24,  # Daily based on hourly limit
            'firecrawl': 1000,  # Default limit
            'deepseek': 10000   # Default limit
        }
        
        # Rate limits (requests per minute)
        self._rate_limits_per_minute = {
            'youtube': 100,
            'spotify': 180,
            'firecrawl': 60,
            'deepseek': 60
        }
        
        logger.info("🎛️ QuotaManager initialized with comprehensive tracking")
    
    async def can_perform_operation(
        self,
        api: str,
        operation: str,
        count: int = 1
    ) -> bool:
        """Check if operation can be performed within quota and rate limits"""
        try:
            # Check daily quota
            if not await self._check_daily_quota(api, operation, count):
                logger.warning(f"❌ Daily quota exceeded for {api}:{operation}")
                return False
            
            # Check rate limits
            if not await self._check_rate_limit(api, count):
                logger.warning(f"⏱️ Rate limit exceeded for {api}")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Quota check error for {api}:{operation}: {e}")
            return True  # Allow operation if quota check fails
    
    async def record_operation(
        self,
        api: str,
        operation: str,
        count: int = 1,
        success: bool = True
    ):
        """Record an API operation for quota tracking"""
        try:
            cost_map = self._get_cost_map(api)
            cost = cost_map.get(operation, 1) * count
            
            if success:
                self._usage_cache[api] += cost
                self._rate_limits[api].append(time.time())
                
                # Clean old rate limit entries (older than 1 minute)
                cutoff = time.time() - 60
                self._rate_limits[api] = [
                    timestamp for timestamp in self._rate_limits[api] 
                    if timestamp > cutoff
                ]
                
                logger.debug(f"📊 Recorded {api}:{operation} cost={cost} (success={success})")
            
        except Exception as e:
            logger.error(f"Error recording operation {api}:{operation}: {e}")
    
    async def _check_daily_quota(self, api: str, operation: str, count: int) -> bool:
        """Check if daily quota allows the operation"""
        cost_map = self._get_cost_map(api)
        cost = cost_map.get(operation, 1) * count
        
        # Reset daily usage if needed
        await self._reset_daily_usage_if_needed(api)
        
        current_usage = self._usage_cache[api]
        daily_limit = self._daily_limits.get(api, 1000)
        
        return (current_usage + cost) <= daily_limit
    
    async def _check_rate_limit(self, api: str, count: int) -> bool:
        """Check if rate limit allows the operation"""
        rate_limit = self._rate_limits_per_minute.get(api, 60)
        
        # Count recent requests (last minute)
        cutoff = time.time() - 60
        recent_requests = [
            timestamp for timestamp in self._rate_limits[api] 
            if timestamp > cutoff
        ]
        
        return len(recent_requests) + count <= rate_limit
    
    async def _reset_daily_usage_if_needed(self, api: str):
        """Reset daily usage if a new day has started"""
        now = datetime.now(timezone.utc)
        last_reset = self._last_reset.get(api)
        
        if not last_reset or last_reset.date() < now.date():
            self._usage_cache[api] = 0
            self._last_reset[api] = now
            logger.info(f"🔄 Daily quota reset for {api}")
    
    def _get_cost_map(self, api: str) -> Dict[str, int]:
        """Get cost mapping for API"""
        if api == 'youtube':
            return self.YOUTUBE_COSTS
        elif api == 'spotify':
            return self.SPOTIFY_COSTS
        elif api == 'firecrawl':
            return self.FIRECRAWL_COSTS
        else:
            return {'default': 1}
    
    async def get_remaining_quota(self, api: str) -> int:
        """Get remaining quota for API"""
        await self._reset_daily_usage_if_needed(api)
        
        used = self._usage_cache[api]
        limit = self._daily_limits.get(api, 1000)
        
        return max(0, limit - used)
    
    async def get_quota_status(self) -> Dict[str, Any]:
        """Get comprehensive quota status for all APIs"""
        status = {}
        
        for api in ['youtube', 'spotify', 'firecrawl', 'deepseek']:
            remaining = await self.get_remaining_quota(api)
            limit = self._daily_limits.get(api, 1000)
            used = self._usage_cache[api]
            
            # Rate limit status
            cutoff = time.time() - 60
            recent_requests = len([
                t for t in self._rate_limits[api] if t > cutoff
            ])
            rate_limit = self._rate_limits_per_minute.get(api, 60)
            
            status[api] = {
                'daily_used': used,
                'daily_limit': limit,
                'daily_remaining': remaining,
                'daily_percentage': (used / limit * 100) if limit > 0 else 0,
                'rate_used_last_minute': recent_requests,
                'rate_limit_per_minute': rate_limit,
                'rate_remaining': max(0, rate_limit - recent_requests)
            }
        
        return status

class ResponseCache:
    """Intelligent response caching to reduce API calls"""
    
    def __init__(self, default_ttl: int = 3600):  # 1 hour default TTL
        self._cache = {}
        self._cache_ttl = {}
        self._default_ttl = default_ttl
        self._hit_count = 0
        self._miss_count = 0
        
        logger.info("🗄️ ResponseCache initialized")
    
    def _generate_cache_key(self, api: str, operation: str, params: Dict[str, Any]) -> str:
        """Generate cache key from API call parameters"""
        # Sort params for consistent key generation
        sorted_params = sorted(params.items()) if params else []
        param_str = "&".join(f"{k}={v}" for k, v in sorted_params)
        return f"{api}:{operation}:{param_str}"
    
    async def get(
        self,
        api: str,
        operation: str,
        params: Dict[str, Any] = None
    ) -> Optional[Any]:
        """Get cached response if available and valid"""
        cache_key = self._generate_cache_key(api, operation, params or {})
        
        if cache_key in self._cache:
            # Check if cache entry is still valid
            if time.time() < self._cache_ttl.get(cache_key, 0):
                self._hit_count += 1
                logger.debug(f"📦 Cache HIT: {cache_key}")
                return self._cache[cache_key]
            else:
                # Remove expired entry
                self._remove_expired_entry(cache_key)
        
        self._miss_count += 1
        logger.debug(f"❌ Cache MISS: {cache_key}")
        return None
    
    async def set(
        self,
        api: str,
        operation: str,
        params: Dict[str, Any],
        response: Any,
        ttl: Optional[int] = None
    ):
        """Cache API response"""
        cache_key = self._generate_cache_key(api, operation, params or {})
        ttl = ttl or self._default_ttl
        
        self._cache[cache_key] = response
        self._cache_ttl[cache_key] = time.time() + ttl
        
        logger.debug(f"💾 Cached response: {cache_key} (TTL: {ttl}s)")
    
    def _remove_expired_entry(self, cache_key: str):
        """Remove expired cache entry"""
        if cache_key in self._cache:
            del self._cache[cache_key]
        if cache_key in self._cache_ttl:
            del self._cache_ttl[cache_key]
    
    async def cleanup_expired(self):
        """Remove all expired cache entries"""
        current_time = time.time()
        expired_keys = [
            key for key, expiry in self._cache_ttl.items()
            if current_time >= expiry
        ]
        
        for key in expired_keys:
            self._remove_expired_entry(key)
        
        if expired_keys:
            logger.info(f"🧹 Cleaned up {len(expired_keys)} expired cache entries")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        total_requests = self._hit_count + self._miss_count
        hit_rate = (self._hit_count / total_requests * 100) if total_requests > 0 else 0
        
        return {
            'cache_size': len(self._cache),
            'hit_count': self._hit_count,
            'miss_count': self._miss_count,
            'hit_rate_percentage': hit_rate,
            'total_requests': total_requests
        }

class DeduplicationManager:
    """Manage artist deduplication across discovery sessions"""
    
    def __init__(self):
        self._processed_artists = set()
        self._artist_fingerprints = {}
        
        logger.info("🔍 DeduplicationManager initialized")
    
    def generate_artist_fingerprint(self, artist_data: Dict[str, Any]) -> str:
        """Generate unique fingerprint for artist"""
        # Use multiple identifiers to create robust fingerprint
        identifiers = []
        
        # Primary identifiers
        if artist_data.get('youtube_channel_id'):
            identifiers.append(f"yt:{artist_data['youtube_channel_id']}")
        
        if artist_data.get('spotify_id'):
            identifiers.append(f"sp:{artist_data['spotify_id']}")
        
        # Secondary identifiers (name-based)
        name = artist_data.get('name', '').lower().strip()
        if name:
            # Normalize name
            normalized_name = ''.join(c for c in name if c.isalnum())
            identifiers.append(f"name:{normalized_name}")
        
        # Create fingerprint
        fingerprint = "|".join(sorted(identifiers))
        return fingerprint if fingerprint else f"unknown:{hash(str(artist_data))}"
    
    def is_duplicate(self, artist_data: Dict[str, Any]) -> bool:
        """Check if artist is a duplicate"""
        fingerprint = self.generate_artist_fingerprint(artist_data)
        
        if fingerprint in self._processed_artists:
            logger.info(f"🔍 Duplicate detected: {artist_data.get('name', 'Unknown')}")
            return True
        
        return False
    
    def mark_as_processed(self, artist_data: Dict[str, Any]):
        """Mark artist as processed"""
        fingerprint = self.generate_artist_fingerprint(artist_data)
        self._processed_artists.add(fingerprint)
        self._artist_fingerprints[fingerprint] = {
            'name': artist_data.get('name', 'Unknown'),
            'processed_at': datetime.now(timezone.utc).isoformat(),
            'youtube_channel_id': artist_data.get('youtube_channel_id'),
            'spotify_id': artist_data.get('spotify_id')
        }
        
        logger.debug(f"✅ Marked as processed: {artist_data.get('name', 'Unknown')}")
    
    def get_processed_count(self) -> int:
        """Get count of processed artists"""
        return len(self._processed_artists)
    
    def clear_session_data(self):
        """Clear session-specific data (keep long-term duplicates)"""
        # Keep a subset of recent artists to prevent immediate duplicates
        # while allowing rediscovery after some time
        if len(self._processed_artists) > 1000:
            # Keep most recent 500
            recent_artists = list(self._processed_artists)[-500:]
            self._processed_artists = set(recent_artists)
            logger.info("🧹 Cleared old deduplication data, kept recent 500 artists")

# Global instances
quota_manager = QuotaManager()
response_cache = ResponseCache()
deduplication_manager = DeduplicationManager()

# Cleanup task (run periodically)
async def cleanup_caches():
    """Periodic cleanup of caches and expired data"""
    await response_cache.cleanup_expired()
    
    # Clean old deduplication data periodically
    if deduplication_manager.get_processed_count() > 2000:
        deduplication_manager.clear_session_data() 