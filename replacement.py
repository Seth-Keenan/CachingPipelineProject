from abc import ABC, abstractmethod
from collections import OrderedDict, deque

class ReplacementStrategy(ABC):

    @abstractmethod
    def on_access(self, way: int, tag: int):
        """Called on every cache hit to update internal state."""

    @abstractmethod
    def on_insert(self, way: int, tag: int):
        """Called when a new line is installed into a way."""

    @abstractmethod
    def evict_way(self) -> int:
        """Return the way index that should be evicted next."""

    @abstractmethod
    def remove(self, tag: int):
        """Remove a tag from tracking (called after eviction)."""

class LRUPolicy(ReplacementStrategy):
    def __init__(self):
        self._order: OrderedDict[int, int] = OrderedDict()

    def on_access(self, way: int, tag: int):
        if tag in self._order:
            self._order.move_to_end(tag)

    def on_insert(self, way: int, tag: int):
        self._order[tag] = way
        self._order.move_to_end(tag)

    def evict_way(self) -> int:
        if not self._order:
            raise RuntimeError("LRUPolicy: nothing to evict")
        _, way = next(iter(self._order.items()))
        return way

    def remove(self, tag: int):
        self._order.pop(tag, None)

class FIFOPolicy(ReplacementStrategy):
    def __init__(self):
        self._queue: deque[int] = deque()

    def on_access(self, way: int, tag: int):
        pass

    def on_insert(self, way: int, tag: int):
        self._queue.append(way)

    def evict_way(self) -> int:
        if not self._queue:
            raise RuntimeError("FIFOPolicy: nothing to evict")
        return self._queue[0]

    def remove(self, tag: int):
        if self._queue:
            self._queue.popleft()


def make_replacement_policy(policy_enum) -> ReplacementStrategy:
    from enums import ReplacementPolicy

    mapping = {
        ReplacementPolicy.LRU:  LRUPolicy,
        ReplacementPolicy.FIFO: FIFOPolicy,
    }
    cls = mapping.get(policy_enum)
    if cls is None:
        raise ValueError(f"Unknown replacement policy: {policy_enum}")
    return cls()
