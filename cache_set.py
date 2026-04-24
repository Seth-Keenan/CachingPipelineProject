from cache_line import CacheLine
from replacement import ReplacementStrategy


class CacheSet:
    def __init__(self, associativity: int, block_size: int,
                 strategy: ReplacementStrategy):
        self.associativity = associativity
        self.strategy      = strategy
        self.lines         = [CacheLine(block_size) for _ in range(associativity)]

    def lookup(self, tag: int) -> tuple[bool, int | None]:
        for way, line in enumerate(self.lines):
            if line.valid and line.tag == tag:
                self.strategy.on_access(way, tag)
                return True, way
        return False, None

    def install(self, tag: int) -> tuple[CacheLine | None, int]:
        empty_way = self._find_empty_way()

        if empty_way is not None:
            way      = empty_way
            evicted  = None
        else:
            way      = self.strategy.evict_way()
            evicted  = self.lines[way].copy()
            self.strategy.remove(self.lines[way].tag)

        line       = self.lines[way]
        line.valid = True
        line.dirty = False
        line.tag   = tag
        line.prefetched = False

        self.strategy.on_insert(way, tag)
        return evicted, way

    def mark_dirty(self, way: int):
        self.lines[way].dirty = True

    def _find_empty_way(self) -> int | None:
        for way, line in enumerate(self.lines):
            if not line.valid:
                return way
        return None

    def __repr__(self):
        return (f"CacheSet(ways={self.associativity}, "
                f"valid={sum(l.valid for l in self.lines)})")
