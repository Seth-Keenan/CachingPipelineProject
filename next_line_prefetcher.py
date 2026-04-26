class NextLinePrefetcher:
	def __init__(self, cache, block_size: int):
		self.cache = cache
		self.block_size = block_size
		self.prefetches_issued = 0
		self.prefetches_useful = 0 # updated when prefetched line is hit
		self.prefetches_useless = 0 # updated when prefetched line is evicted
	def on_miss(self, missed_address: int):
		"""
		When L1 misses address A, prefetch block A+1 into L1.
		"""
		next_block_addr = (missed_address // self.block_size + 1) * self.block_size
		if self.cache.probe(next_block_addr):
			return
		self.prefetches_issued += 1
		tag, set_idx, _ = self.cache._decompose(next_block_addr)
		evicted, way = self.cache.sets[set_idx].install(tag)
		self.cache.sets[set_idx].lines[way].prefetched = True
		if evicted and evicted.valid and evicted.prefetched:
			self.evictPrefetch(evicted)

	def hitPrefetch(self, line):
		if line.prefetched:
			self.prefetches_useful += 1
			line.prefetched = False

	def evictPrefetch(self, line):
		if line.prefetched:
			self.prefetches_useless += 1
			line.prefetched = False

	def coverage(self):
		return (self.prefetches_useful / self.prefetches_issued if self.prefetches_issued > 0 else 0.0)