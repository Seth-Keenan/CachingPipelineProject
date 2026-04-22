# Caching Pipeline Simulation Project

This project is a Python-based computer architecture simulation of a multi-level CPU caching hierarchy. It models the behavior of CPU caches, tracking hits, misses, evictions, and memory traffic, as well as calculating structural statistics like Average Memory Access Time (AMAT). 

## Overview

The simulator decomposes memory addresses into `Tag`, `Set Index`, and `Block Offset` to route access requests. It fully supports N-way set associative caches, direct-mapped, and fully associative structures.

### Key Features
* **Multi-Level Hierarchy:** Configurable support for L1 and L2 caching (and beyond, simply by linking the `next_level` property).
* **Write Policies:** Supports `Write-Back` and `Write-Through` operations.
* **Replacement Policies:** Ships with `LRU` (Least Recently Used) and `FIFO` algorithms for cache line eviction.
* **Statistics & Reporting:** Automatically measures read/write hits and misses, cache line evictions, writebacks, and computes properties like AMAT and Hit/Miss Rates.

## Architecture & Code Structure

* **`cache.py` (`Cache`):** The core module that orchestrates read/write requests. It handles address decomposition, drives hits/misses, applies write policies, and links to lower-level caches (e.g. L1 falling back to L2).
* **`cache_set.py` (`CacheSet`):** Models an individual set within the cache. Given a set associativity, it manages `N` cache lines and utilizes the specified replacement strategy to handle installation and eviction.
* **`cache_line.py` (`CacheLine`):** Represents exactly one cache block, storing state flags (valid/dirty), the tag, and simulated data.
* **`replacement.py`:** Defines the `ReplacementStrategy` abstract base class and implements `LRUPolicy` and `FIFOPolicy`. Provides a factory `make_replacement_policy()` for instantiation.
* **`hierarchy.py`:** A builder helper to quickly instantiate and wire together an L1 and L2 cache.
* **`enums.py`:** Contains enumerations for Write Policies, Replacement Policies, and Organizaton Types to ensure type-safe configurations.
* **`main.py`:** A smoke test driver that instantiates an L1/L2 hierarchy, runs sequential accesses, repeat reads, and writes, then prints a performance report.

## Usage

To run the smoke test and see the caching simulator in action, run:

```bash
python main.py
```

This will run simulated memory traces on a 1024B 2-way L1 cache and 8192B 4-way L2 cache, printing a detailed hit/miss breakdown for both levels and calculating the overall AMAT.
