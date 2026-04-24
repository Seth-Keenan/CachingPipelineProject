from math import log2

from enums import WritePolicy, ReplacementPolicy, Organization
from cache_set import CacheSet
from replacement import make_replacement_policy
from next_line_prefetcher import NextLinePrefetcher


class Cache:
    def __init__(
        self,
        name:           str,
        cache_size:     int,
        block_size:     int,
        associativity:  int,
        write_policy:   WritePolicy       = WritePolicy.WRITE_BACK,
        replacement:    ReplacementPolicy = ReplacementPolicy.LRU,
        next_level:     "Cache"           = None,
        next_line_prefetcher: NextLinePrefetcher = None,
    ):
        self._validate(cache_size, block_size)

        self.name          = name
        self.cache_size    = cache_size
        self.block_size    = block_size
        self.associativity = associativity
        self.write_policy  = write_policy
        self.replacement   = replacement
        self.next_level    = next_level
        self.prefetcher    = next_line_prefetcher

        self.num_blocks  = cache_size // block_size
        self.num_sets    = max(self.num_blocks // associativity, 1)
        self.offset_bits = int(log2(block_size))
        self.index_bits  = int(log2(self.num_sets)) if self.num_sets > 1 else 0

        if associativity == 1:
            self.organization = Organization.DIRECT_MAPPED
        elif associativity >= self.num_blocks:
            self.organization = Organization.FULLY_ASSOCIATIVE
        else:
            self.organization = Organization.SET_ASSOCIATIVE

        self.sets = [
            CacheSet(associativity, block_size, make_replacement_policy(replacement))
            for _ in range(self.num_sets)
        ]

        self._init_stats()

    def read(self, address: int) -> bool:
        self.stats["reads"] += 1
        tag, set_idx, _ = self._decompose(address)

        hit, way = self.sets[set_idx].lookup(tag)

        if hit:
            self.stats["read_hits"] += 1
            if self.prefetcher:
                hit_line = self.sets[set_idx].lines[way]
                self.prefetcher.hitPrefetch(hit_line)
            return True

        self.stats["read_misses"] += 1
        self._handle_miss(self.sets[set_idx], tag, address, is_write=False)

        if self.prefetcher:
            self.prefetcher.on_miss(address)

        return False

    def write(self, address: int) -> bool:
        self.stats["writes"] += 1
        tag, set_idx, _ = self._decompose(address)

        hit, way = self.sets[set_idx].lookup(tag)

        if hit:
            self.stats["write_hits"] += 1
            self._apply_write_policy_on_hit(self.sets[set_idx], way, address)
            return True

        self.stats["write_misses"] += 1
        self._apply_write_policy_on_miss(self.sets[set_idx], tag, address)
        return False

    def _apply_write_policy_on_hit(self, cache_set: CacheSet,
                                   way: int, address: int):
        if self.write_policy == WritePolicy.WRITE_BACK:
            cache_set.mark_dirty(way)
        else:
            self.stats["mem_traffic"] += 1
            if self.next_level:
                self.next_level.write(address)

    def _apply_write_policy_on_miss(self, cache_set: CacheSet,
                                    tag: int, address: int):
        if self.write_policy == WritePolicy.WRITE_BACK:
            self._handle_miss(cache_set, tag, address, is_write=True)
        else:
            self.stats["mem_traffic"] += 1
            if self.next_level:
                self.next_level.write(address)

    def _handle_miss(self, cache_set: CacheSet, tag: int,
                     address: int, is_write: bool):
        self.stats["mem_traffic"] += 1
        if self.next_level:
            self.next_level.read(address)

        evicted, way = cache_set.install(tag)

        if evicted and evicted.valid:
            self.stats["evictions"] += 1
            if evicted.dirty and self.write_policy == WritePolicy.WRITE_BACK:
                self._writeback(evicted.tag)
            if self.prefetcher and evicted.prefetched:
                self.prefetcher.evictPrefetch(evicted)

        if is_write and self.write_policy == WritePolicy.WRITE_BACK:
            cache_set.mark_dirty(way)

    def _writeback(self, evicted_tag: int):
        self.stats["dirty_evictions"] += 1
        self.stats["writebacks"]      += 1
        self.stats["mem_traffic"]     += 1
        if self.next_level:
            wb_address = evicted_tag << (self.offset_bits + self.index_bits)
            self.next_level.write(wb_address)

    def _decompose(self, address: int) -> tuple[int, int, int]:
        """Split address into (tag, set_index, block_offset)."""
        offset    = address & (self.block_size - 1)
        set_index = (address >> self.offset_bits) & (self.num_sets - 1) \
                    if self.num_sets > 1 else 0
        tag       = address >> (self.offset_bits + self.index_bits)
        return tag, set_index, offset

    @property
    def hit_rate(self) -> float:
        total = self.stats["reads"] + self.stats["writes"]
        hits  = self.stats["read_hits"] + self.stats["write_hits"]
        return hits / total if total > 0 else 0.0

    @property
    def miss_rate(self) -> float:
        return 1.0 - self.hit_rate

    def amat(self, hit_time: float, miss_penalty: float) -> float:
        return hit_time + self.miss_rate * miss_penalty

    def reset_stats(self):
        self._init_stats()

    def report(self) -> str:
        s = self.stats
        return (
            f"\n{'='*50}\n"
            f"Cache Report: {self.name}\n"
            f"{'='*50}\n"
            f"  Organization : {self.organization.value}\n"
            f"  Size         : {self.cache_size} B\n"
            f"  Block Size   : {self.block_size} B\n"
            f"  Associativity: {self.associativity}-way\n"
            f"  Write Policy : {self.write_policy.value}\n"
            f"  Replacement  : {self.replacement.value}\n"
            f"{'-'*50}\n"
            f"  Total Accesses : {s['reads'] + s['writes']}\n"
            f"  Reads          : {s['reads']}  "
            f"(hits: {s['read_hits']}, misses: {s['read_misses']})\n"
            f"  Writes         : {s['writes']} "
            f"(hits: {s['write_hits']}, misses: {s['write_misses']})\n"
            f"  Hit Rate       : {self.hit_rate:.4f}\n"
            f"  Miss Rate      : {self.miss_rate:.4f}\n"
            f"  Evictions      : {s['evictions']}\n"
            f"  Dirty Evictions: {s['dirty_evictions']}\n"
            f"  Writebacks     : {s['writebacks']}\n"
            f"  Memory Traffic : {s['mem_traffic']} block transfers\n"
            f"{'='*50}\n"
        )

    def __repr__(self):
        return (f"Cache(name={self.name!r}, size={self.cache_size}B, "
                f"block={self.block_size}B, ways={self.associativity}, "
                f"org={self.organization.value})")

    def _init_stats(self):
        self.stats = {
            "reads":           0,
            "writes":          0,
            "read_hits":       0,
            "write_hits":      0,
            "read_misses":     0,
            "write_misses":    0,
            "evictions":       0,
            "dirty_evictions": 0,
            "writebacks":      0,
            "mem_traffic":     0,
        }

    @staticmethod
    def _validate(cache_size: int, block_size: int):
        assert cache_size > 0 and (cache_size & (cache_size - 1)) == 0, \
            "cache_size must be a power of 2"
        assert block_size > 0 and (block_size & (block_size - 1)) == 0, \
            "block_size must be a power of 2"
