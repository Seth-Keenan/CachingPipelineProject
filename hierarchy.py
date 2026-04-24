from enums import WritePolicy, ReplacementPolicy
from cache import Cache
from next_line_prefetcher import NextLinePrefetcher


def build_hierarchy(
    l1_size:          int              = 1024,
    l1_block_size:    int              = 64,
    l1_associativity: int              = 2,
    l1_write_policy:  WritePolicy      = WritePolicy.WRITE_BACK,
    l1_replacement:   ReplacementPolicy = ReplacementPolicy.LRU,
    l2_size:          int              = 8192,
    l2_block_size:    int              = 64,
    l2_associativity: int              = 4,
    l2_write_policy:  WritePolicy      = WritePolicy.WRITE_BACK,
    l2_replacement:   ReplacementPolicy = ReplacementPolicy.LRU,
) -> tuple[Cache, Cache]:

    
    l2 = Cache(
        name          = "L2",
        cache_size    = l2_size,
        block_size    = l2_block_size,
        associativity = l2_associativity,
        write_policy  = l2_write_policy,
        replacement   = l2_replacement,
        next_level    = None,
    )
    
    l1 = Cache(
        name          = "L1",
        cache_size    = l1_size,
        block_size    = l1_block_size,
        associativity = l1_associativity,
        write_policy  = l1_write_policy,
        replacement   = l1_replacement,
        next_level    = l2,
    )

    l1_prefetcher = NextLinePrefetcher(l1, l1_block_size)
    l1.prefetcher = l1_prefetcher
    return l1, l2
