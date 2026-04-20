class CacheLine:

    def __init__(self, block_size: int):
        self.valid     = False
        self.dirty     = False
        self.tag       = None
        self.data      = [0] * block_size

    def copy(self) -> "CacheLine":
        snapshot       = CacheLine(len(self.data))
        snapshot.valid = self.valid
        snapshot.dirty = self.dirty
        snapshot.tag   = self.tag
        snapshot.data  = self.data[:]
        return snapshot

    def invalidate(self):
        self.valid = False
        self.dirty = False
        self.tag   = None

    def __repr__(self):
        return (f"CacheLine(valid={self.valid}, dirty={self.dirty}, "
                f"tag={self.tag})")
