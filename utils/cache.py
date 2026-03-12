import time
import os

class Cache:
    def __init__(self, ttl: int= 300): # 300s = 5 minutes
        self._store: dict = {}
        self.ttl = ttl

    def _key(self, user_id: str, resource: str) -> str:
        return f"{user_id}:{resource}"
    
    def get(self, user_id: str, resource: str):
        key = self._key(user_id, resource)
        entry = self._store.get(key)
        if not entry:
            return None
        if time.time() > entry["expires_at"]:
            del self._store[key]
            return None
        return entry["data"]
    
    def set(self, user_id: str, resource: str, data):
        key = self._key(user_id, resource)
        self._store[key] = {
            "data": data,
            "expires_at": time.time() + self.ttl
        }
    
    def invalidate(self, user_id: str, resource: str):
        key = self._key(user_id, resource)
        self._store.pop(key, None)

    def invalidate_all(self, user_id: str):
        keys = [k for k in self._store if k.startswith(f"{user_id}:")]
        for k in keys:
            del self._store[k]

cache = Cache(ttl=int(os.environ.get("CACHE_TIME", 300)))