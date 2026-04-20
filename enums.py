from enum import Enum


class WritePolicy(Enum):
    WRITE_THROUGH = "write-through"
    WRITE_BACK    = "write-back"


class ReplacementPolicy(Enum):
    LRU  = "lru"
    FIFO = "fifo"


class Organization(Enum):
    DIRECT_MAPPED     = "direct-mapped"
    SET_ASSOCIATIVE   = "set-associative"
    FULLY_ASSOCIATIVE = "fully-associative"
