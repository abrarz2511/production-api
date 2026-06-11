import hashlib
import time
from typing import Optional


class ResponseCache:

    def __init__(self, ttl_seconds: int = 300):
        self.ttl_seconds = ttl_seconds
        self._cache: dict[str, dict] = {}
        self._hits = 0
        self._misses = 0

    def _make_key(self, query: str) -> str:
        """create a hash key for the query to use in cache"""
        normalized = query.lower().strip()
        return hashlib.sha256(normalized.encode()).hexdigest()

    def get(self, query:str) -> Optional[str]:

        key = self._make_key(query)
        
        if key in self._cache:
            entry = self._cache[key]
            if time.time() - entry["timestamp"] < self.ttl_seconds:
                self._hits += 1
                return entry["response"]
            else:
                del self._cache[key]
        
        self._misses += 1

        return None

    def set(self, query:str, response:str) -> None:
        key = self._make_key(query)
        self._cache[key] = {"response": response, "timestamp": time.time(), "query": query}

    def stats(self) -> dict:
        self._remove_expired()
        total = self._hits + self._misses
        hit_rate = (self._hits / total) * 100 if total > 0 else 0.0
        return {
            "entries": len(self._cache),
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": round(hit_rate, 2),
            "ttl_seconds": self.ttl_seconds,
        }

    def _remove_expired(self) -> None:
        now = time.time()
        expired_keys = [
            key
            for key, entry in self._cache.items()
            if now - entry["timestamp"] >= self.ttl_seconds
        ]
        for key in expired_keys:
            del self._cache[key]

    
