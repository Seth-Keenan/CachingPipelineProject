
# 1. Generate the three workload trace files (run once)
python generate_traces.py

# 2. Run all experiments — outputs CSVs to results/
python simulate_trace.py

# 3. Generate all figures — outputs PDFs and PNGs to results/figures/
python visualize.py

`simulate_trace.py` runs all 8 required experiments against all three workloads
and writes one CSV per experiment to `results/`:

| Experiment | Variable | Output CSV |
|---|---|---|
| E1 | L1 cache size (4–64 KB) | `e1_cache_size.csv` |
| E2 | Associativity (1, 2, 4, 8-way) | `e2_associativity.csv` |
| E3 | Block size (16–256 B) | `e3_block_size.csv` |
| E4 | Write policy (WB vs WT) | `e4_write_policy.csv` |
| E5 | Replacement policy (LRU vs FIFO) | `e5_replacement.csv` |
| E6 | Prefetching on vs off | `e6_prefetch.csv` |
| E7 | Workload sensitivity | `e7_workload.csv` |
| E8 | L2 cache size (128 KB–2 MB) | `e8_l2_size.csv` |

## Figures

`visualize.py` reads the CSVs and saves both PDF and PNG to `results/figures/`:

| Figure | Description |
|---|---|
| Fig 2 | Miss rate vs. L1 cache size (log-x), one curve per workload |
| Fig 3 | AMAT vs. block size, one curve per associativity level |
| Fig 4 | CPI decomposition stacked bar chart (ideal + L1 stall + L2 stall) |
| Fig 5 | Write-through vs. write-back memory traffic (normalized) |
| Fig 6 | Prefetch coverage and useless-prefetch rate vs. block size |
---

## Cache Configuration

All parameters are set when constructing a `Cache` object or via `build_hierarchy()`:

| Parameter | Options | Default |
|---|---|---|
| `cache_size` | Any power-of-2 bytes | — |
| `block_size` | Any power-of-2 bytes | 64 |
| `associativity` | 1 (direct-mapped), N, or `num_blocks` (fully associative) | 4 |
| `write_policy` | `WritePolicy.WRITE_BACK`, `WritePolicy.WRITE_THROUGH` | `WRITE_BACK` |
| `replacement` | `ReplacementPolicy.LRU`, `ReplacementPolicy.FIFO` | `LRU` |

Example:
```python
from hierarchy import build_hierarchy
from enums import WritePolicy, ReplacementPolicy

l1, l2 = build_hierarchy(
    l1_size=32768, l1_block_size=64, l1_associativity=4,
    l1_write_policy=WritePolicy.WRITE_BACK,
    l1_replacement=ReplacementPolicy.LRU,
    l2_size=262144, l2_block_size=64, l2_associativity=4,
    prefetcher_enabled=True,
)

l1.read(0x10004000)
l1.write(0x10004008)
print(l1.report())
```
