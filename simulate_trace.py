# This will run experiments E1–E8 against the three synthetic workload traces
# and write CSV result files to the results directory.

import csv
import os
from math import log2

from enums import WritePolicy, ReplacementPolicy
from hierarchy import build_hierarchy
from trace_parser import parse_trace

os.makedirs("results", exist_ok=True)

L1_HIT_TIME = 1
L2_HIT_TIME = 8
DRAM_PENALTY = 100

TRACE_FILES = {
    "sequential": "traces/sequential.trace",
    "matrix": "traces/matrix.trace",
    "random": "traces/random.trace",
}

BASELINE_L1 = dict(l1_size=32768, l1_block_size=64, l1_associativity=4,
                   l1_write_policy=WritePolicy.WRITE_BACK,
                   l1_replacement=ReplacementPolicy.LRU)
BASELINE_L2 = dict(l2_size=262144, l2_block_size=64, l2_associativity=4,
                   l2_write_policy=WritePolicy.WRITE_BACK,
                   l2_replacement=ReplacementPolicy.LRU)

def run_experiment(trace, prefetch=False, **hierarchy_kwargs) -> dict:
    """
    Simulate one cache configuration against a trace list.
    Every trace record is treated as one memory instruction (ideal CPI = 1).
    Returns a stats dict suitable for writing to a CSV row.
    """
    l1, l2 = build_hierarchy(**hierarchy_kwargs, prefetcher_enabled=prefetch)

    l1_stalls = 0
    l2_stalls = 0

    for rec in trace:
        before_l1 = l1.stats["read_misses"] + l1.stats["write_misses"]
        before_l2 = l2.stats["read_misses"] + l2.stats["write_misses"]

        if rec["type"] == "S":
            l1.write(rec["address"])
        else:
            l1.read(rec["address"])

        l1_missed = (l1.stats["read_misses"] + l1.stats["write_misses"]) > before_l1
        l2_missed = (l2.stats["read_misses"] + l2.stats["write_misses"]) > before_l2

        if l1_missed and not l2_missed:
            l1_stalls += L2_HIT_TIME
        elif l2_missed:
            l2_stalls += DRAM_PENALTY

    n = len(trace)
    cpi_l1    = l1_stalls / n if n else 0.0
    cpi_l2    = l2_stalls / n if n else 0.0
    cpi_total = 1.0 + cpi_l1 + cpi_l2

    l2_amat = L2_HIT_TIME + l2.miss_rate * DRAM_PENALTY
    amat    = L1_HIT_TIME + l1.miss_rate * l2_amat

    pref = l1.prefetcher
    issued = pref.prefetches_issued  if (pref and prefetch) else 0
    useful = pref.prefetches_useful  if (pref and prefetch) else 0
    useless = pref.prefetches_useless if (pref and prefetch) else 0
    coverage = pref.coverage()         if (pref and prefetch) else 0.0
    useless_rate = (useless / issued) if issued > 0 else 0.0

    total_misses = l1.stats["read_misses"] + l1.stats["write_misses"]
    compulsory = l1.stats["compulsory_misses"]
    non_compulsory = total_misses - compulsory

    return {
        "instructions": n,
        "l1_miss_rate": round(l1.miss_rate, 6),
        "l2_miss_rate": round(l2.miss_rate, 6),
        "amat": round(amat, 4),
        "cpi_ideal": 1.0,
        "cpi_l1_stall": round(cpi_l1, 4),
        "cpi_l2_stall": round(cpi_l2, 4),
        "cpi_total": round(cpi_total, 4),
        "mem_traffic": l1.stats["mem_traffic"],
        "dirty_evictions": l1.stats["dirty_evictions"],
        "compulsory_misses": compulsory,
        "non_compulsory_misses": non_compulsory,
        "prefetch_coverage": round(coverage, 4),
        "prefetch_useless": useless,
        "prefetch_issued": issued,
        "useless_rate": round(useless_rate, 4),
    }


def load_traces() -> dict:
    traces = {}
    missing = []
    for name, path in TRACE_FILES.items():
        if not os.path.exists(path):
            missing.append(path)
        else:
            traces[name] = parse_trace(path)
    if missing:
        print("Missing trace files (run generate_traces.py first):")
        for p in missing:
            print(f"  {p}")
        raise SystemExit(1)
    return traces


def write_csv(filename, fieldnames, rows):
    path = os.path.join("results", filename)
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    print(f"  -> {path}")


def e1_cache_size(traces):
    print("E1: Cache size sensitivity…")
    rows = []
    for cap in [4096, 8192, 16384, 32768, 65536]:
        for wl, trace in traces.items():
            r = run_experiment(trace,
                               l1_size=cap, l1_block_size=64, l1_associativity=4,
                               l1_write_policy=WritePolicy.WRITE_BACK,
                               l1_replacement=ReplacementPolicy.LRU,
                               **BASELINE_L2)
            rows.append({"workload": wl, "l1_size_kb": cap // 1024, **r})
    write_csv("e1_cache_size.csv",
              ["workload", "l1_size_kb", "l1_miss_rate", "l2_miss_rate",
               "amat", "cpi_l1_stall", "cpi_l2_stall", "cpi_total"],
              rows)
    return rows


def e2_associativity(traces):
    print("E2: Associativity study…")
    rows = []
    for ways in [1, 2, 4, 8]:
        num_sets  = 32768 // (ways * 64)
        idx_bits  = int(log2(num_sets)) if num_sets > 1 else 0
        tag_bits  = 32 - 6 - idx_bits
        area_proxy = ways * (tag_bits + 2)
        for wl, trace in traces.items():
            r = run_experiment(trace,
                               l1_size=32768, l1_block_size=64,
                               l1_associativity=ways,
                               l1_write_policy=WritePolicy.WRITE_BACK,
                               l1_replacement=ReplacementPolicy.LRU,
                               **BASELINE_L2)
            rows.append({"workload": wl, "ways": ways,
                         "area_proxy": area_proxy, **r})
    write_csv("e2_associativity.csv",
              ["workload", "ways", "l1_miss_rate",
               "compulsory_misses", "non_compulsory_misses", "area_proxy", "cpi_total"],
              rows)


def e3_block_size(traces):
    print("E3: Block size impact…")
    rows = []
    for bs in [16, 32, 64, 128, 256]:
        for wl, trace in traces.items():
            r = run_experiment(trace,
                               l1_size=32768, l1_block_size=bs, l1_associativity=4,
                               l1_write_policy=WritePolicy.WRITE_BACK,
                               l1_replacement=ReplacementPolicy.LRU,
                               l2_size=262144, l2_block_size=bs, l2_associativity=4,
                               l2_write_policy=WritePolicy.WRITE_BACK,
                               l2_replacement=ReplacementPolicy.LRU)
            bandwidth = r["mem_traffic"] * bs
            rows.append({"workload": wl, "block_size_b": bs,
                         "bandwidth_bytes": bandwidth, **r})
    write_csv("e3_block_size.csv",
              ["workload", "block_size_b", "l1_miss_rate", "bandwidth_bytes", "amat", "cpi_total"],
              rows)


def e4_write_policy(traces):
    print("E4: Write policy comparison…")
    rows = []
    for policy in [WritePolicy.WRITE_BACK, WritePolicy.WRITE_THROUGH]:
        for wl, trace in traces.items():
            r = run_experiment(trace,
                               l1_size=32768, l1_block_size=64, l1_associativity=4,
                               l1_write_policy=policy,
                               l1_replacement=ReplacementPolicy.LRU,
                               l2_size=262144, l2_block_size=64, l2_associativity=4,
                               l2_write_policy=policy,
                               l2_replacement=ReplacementPolicy.LRU)
            rows.append({"workload": wl, "write_policy": policy.value, **r})
    write_csv("e4_write_policy.csv",
              ["workload", "write_policy", "mem_traffic", "dirty_evictions", "cpi_total"],
              rows)


def e5_replacement(traces):
    print("E5: Replacement policy…")
    rows = []
    for policy in [ReplacementPolicy.LRU, ReplacementPolicy.FIFO]:
        for wl, trace in traces.items():
            r = run_experiment(trace,
                               l1_size=32768, l1_block_size=64, l1_associativity=4,
                               l1_write_policy=WritePolicy.WRITE_BACK,
                               l1_replacement=policy,
                               l2_size=262144, l2_block_size=64, l2_associativity=4,
                               l2_write_policy=WritePolicy.WRITE_BACK,
                               l2_replacement=policy)
            rows.append({"workload": wl, "replacement": policy.value, **r})
    write_csv("e5_replacement.csv",
              ["workload", "replacement", "l1_miss_rate", "l2_miss_rate", "cpi_total"],
              rows)


def e6_prefetch(traces):
    print("E6: Prefetching effect (also sweeps block size for Figure 6)…")
    # ON vs OFF at baseline
    rows_onoff = []
    for enabled in [False, True]:
        for wl, trace in traces.items():
            r = run_experiment(trace, prefetch=enabled, **BASELINE_L1, **BASELINE_L2)
            rows_onoff.append({"workload": wl,
                                "prefetch": "on" if enabled else "off", **r})
    write_csv("e6_prefetch.csv",
              ["workload", "prefetch", "prefetch_coverage", "prefetch_issued",
               "prefetch_useless", "useless_rate", "cpi_total"],
              rows_onoff)

    # Block-size sweep with prefetch ON (data for Figure 6)
    rows_bs = []
    for bs in [16, 32, 64, 128, 256]:
        for wl, trace in traces.items():
            r = run_experiment(trace, prefetch=True,
                               l1_size=32768, l1_block_size=bs, l1_associativity=4,
                               l1_write_policy=WritePolicy.WRITE_BACK,
                               l1_replacement=ReplacementPolicy.LRU,
                               l2_size=262144, l2_block_size=bs, l2_associativity=4,
                               l2_write_policy=WritePolicy.WRITE_BACK,
                               l2_replacement=ReplacementPolicy.LRU)
            rows_bs.append({"workload": wl, "block_size_b": bs, **r})
    write_csv("e6_prefetch_vs_blocksize.csv",
              ["workload", "block_size_b", "prefetch_coverage", "useless_rate", "cpi_total"],
              rows_bs)


def e7_workload(traces):
    print("E7: Workload sensitivity…")
    rows = []
    for wl, trace in traces.items():
        r = run_experiment(trace, **BASELINE_L1, **BASELINE_L2)
        total_misses = r["l1_miss_rate"]
        loads  = sum(1 for rec in trace if rec["type"] == "L")
        stores = sum(1 for rec in trace if rec["type"] == "S")
        rows.append({
            "workload":       wl,
            "total_accesses": len(trace),
            "load_fraction":  round(loads  / len(trace), 4),
            "store_fraction": round(stores / len(trace), 4),
            **r,
        })
    write_csv("e7_workload.csv",
              ["workload", "total_accesses", "load_fraction", "store_fraction",
               "l1_miss_rate", "l2_miss_rate",
               "cpi_ideal", "cpi_l1_stall", "cpi_l2_stall", "cpi_total", "amat"],
              rows)


def e8_l2_size(traces):
    print("E8: L2 size sweep…")
    rows = []
    for l2_cap in [131072, 262144, 524288, 1048576, 2097152]:
        for wl, trace in traces.items():
            r = run_experiment(trace,
                               l1_size=32768, l1_block_size=64, l1_associativity=4,
                               l1_write_policy=WritePolicy.WRITE_BACK,
                               l1_replacement=ReplacementPolicy.LRU,
                               l2_size=l2_cap, l2_block_size=64, l2_associativity=4,
                               l2_write_policy=WritePolicy.WRITE_BACK,
                               l2_replacement=ReplacementPolicy.LRU)
            rows.append({"workload": wl, "l2_size_kb": l2_cap // 1024, **r})
    write_csv("e8_l2_size.csv",
              ["workload", "l2_size_kb", "l2_miss_rate", "amat", "cpi_total"],
              rows)


def fig3_amat_block_assoc(traces):
    """Extra sweep for Figure 3: AMAT vs block size × associativity."""
    print("Figure 3 data: AMAT vs block-size by associativity…")
    rows = []
    for bs in [16, 32, 64, 128, 256]:
        for ways in [1, 2, 4, 8]:
            for wl, trace in traces.items():
                r = run_experiment(trace,
                                   l1_size=32768, l1_block_size=bs,
                                   l1_associativity=ways,
                                   l1_write_policy=WritePolicy.WRITE_BACK,
                                   l1_replacement=ReplacementPolicy.LRU,
                                   l2_size=262144, l2_block_size=bs, l2_associativity=4,
                                   l2_write_policy=WritePolicy.WRITE_BACK,
                                   l2_replacement=ReplacementPolicy.LRU)
                rows.append({"workload": wl, "block_size_b": bs,
                             "ways": ways, "amat": r["amat"]})
    write_csv("fig3_amat_block_assoc.csv",
              ["workload", "block_size_b", "ways", "amat"],
              rows)


if __name__ == "__main__":
    print("Loading traces…")
    traces = load_traces()
    for name, t in traces.items():
        print(f"  {name}: {len(t):,} accesses")

    e1_cache_size(traces)
    e2_associativity(traces)
    e3_block_size(traces)
    e4_write_policy(traces)
    e5_replacement(traces)
    e6_prefetch(traces)
    e7_workload(traces)
    e8_l2_size(traces)
    fig3_amat_block_assoc(traces)

    print("\nAll experiments complete. CSV files in results/")
