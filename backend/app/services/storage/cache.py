"""
Image & raster caching service to optimize FITS rendering latency.
"""
from typing import Dict, Any, Optional
from collections import OrderedDict
from threading import RLock

class MemoryCache:
    def __init__(self):
        self._store = OrderedDict()
        self._lock = RLock()

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            if key in self._store:
                self._store.move_to_end(key)
            return self._store.get(key)

    def set(self, key: str, value: Any):
        with self._lock:
            self._store[key] = value
            self._store.move_to_end(key)
            while len(self._store) > 64:
                self._store.popitem(last=False)

    def clear(self):
        with self._lock:
            self._store.clear()

cache = MemoryCache()
