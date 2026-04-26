import csv
import os
import sys
import subprocess
from hierarchy import build_hierarchy
from enums import WritePolicy, ReplacementPolicy

L1_MISS_PENALTY = 10
L2_MISS_PENALTY = 100  

os.makedirs("results", exist_ok=True)


def get_total_misses(cache):
    return cache.stats["read_misses"] + cache.stats["write_misses"]


def calculate_penalty_and_do_access(l1, l2, address, is_write):
    l1_before = get_total_misses(l1)
    l2_before = get_total_misses(l2)

    if is_write:
        l1.write(address)
    else:
        l1.read(address)

    l1_missed = get_total_misses(l1) > l1_before
    l2_missed = get_total_misses(l2) > l2_before

    penalty = 0
    if l1_missed:
        penalty = L2_MISS_PENALTY if l2_missed else L1_MISS_PENALTY

    return penalty, l1_missed, l2_missed


def run_simulation(l1, l2, program_file, f, instruction_limit=2000):
    proc = subprocess.Popen(
        ["mu-riscv.exe", program_file],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )

    total_stalls    = 0
    l1_stall_cycles = 0
    l2_stall_cycles = 0
    mem_ops         = 0

    while True:
        if mem_ops > instruction_limit:
            print("\n[Bus] Instruction limit reached. Stopping.")
            proc.kill()
            break

        line = proc.stdout.readline()
        if not line:
            break
        line = line.strip()

        if line.startswith("READ ") or line.startswith("WRITE "):
            is_write  = line.startswith("WRITE ")
            addr_hex  = line.split(" ")[1]
            address   = int(addr_hex, 16)

            penalty, l1_missed, l2_missed = calculate_penalty_and_do_access(
                l1, l2, address, is_write
            )
            total_stalls += penalty
            if l1_missed and not l2_missed:
                l1_stall_cycles += L1_MISS_PENALTY
            elif l2_missed:
                l2_stall_cycles += L2_MISS_PENALTY

            proc.stdin.write(f"{penalty}\n")
            proc.stdin.flush()
            mem_ops += 1

    proc.wait()

    n = max(mem_ops, 1)
    cpi_l1 = l1_stall_cycles / n
    cpi_l2 = l2_stall_cycles / n
    cpi_total = 1.0 + cpi_l1 + cpi_l2

    l2_amat = 8 + l2.miss_rate * 100
    amat    = 1 + l1.miss_rate * l2_amat

    f.write("\n\n--- [Simulation Completed] ---\n")
    f.write(f"Memory Ops Processed : {mem_ops}\n")
    f.write(f"Total Stall Cycles   : {total_stalls}\n")
    f.write("\n--- CPI Decomposition ---\n")
    f.write(f"  CPI_ideal    : 1.0000\n")
    f.write(f"  CPI_L1_stall : {cpi_l1:.4f}  ({l1_stall_cycles} cycles from L1 misses)\n")
    f.write(f"  CPI_L2_stall : {cpi_l2:.4f}  ({l2_stall_cycles} cycles from L2 misses)\n")
    f.write(f"  CPI_total    : {cpi_total:.4f}\n")
    f.write(f"  AMAT         : {amat:.4f} cycles\n")
    f.write(l1.report())
    f.write(l2.report())

    return {
        "mem_ops": mem_ops,
        "l1_miss_rate": l1.miss_rate,
        "l2_miss_rate": l2.miss_rate,
        "amat": amat,
        "cpi_l1_stall": cpi_l1,
        "cpi_l2_stall": cpi_l2,
        "cpi_total": cpi_total,
        "mem_traffic": l1.stats["mem_traffic"],
        "dirty_evictions": l1.stats["dirty_evictions"],
        "compulsory_misses": l1.stats["compulsory_misses"],
        "non_compulsory_misses": (l1.stats["read_misses"] + l1.stats["write_misses"]
                                  - l1.stats["compulsory_misses"]),
    }


def write_csv(filename, fieldnames, rows):
    with open(os.path.join("results", filename), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)


def main():
    if len(sys.argv) < 2:
        print("Usage: python bus.py <riscv_program.mem>")
        return

    program_file = sys.argv[1]

    with open("cache_test_report.txt", "w") as f:

        # E1
        f.write("\n\n--- E1: L1 Cache Size Variations ---\n")
        e1_rows = []
        for cap in [4096, 8192, 16384, 32768, 65536]:
            f.write(f"\n--- L1 Size: {cap // 1024} KB ---\n")
            l1, l2 = build_hierarchy(
                l1_size=cap, l1_block_size=64, l1_associativity=4,
                l2_size=262144, l2_block_size=64, l2_associativity=4,
            )
            r = run_simulation(l1, l2, program_file, f)
            e1_rows.append({"l1_size_kb": cap // 1024, **r})
        write_csv("e1_cache_size.csv",
                  ["l1_size_kb", "l1_miss_rate", "l2_miss_rate", "amat",
                   "cpi_l1_stall", "cpi_l2_stall", "cpi_total", "mem_traffic"],
                  e1_rows)

        # E2
        f.write("\n\n--- E2: Associativity Variations ---\n")
        e2_rows = []
        for ways in [1, 2, 4, 8]:
            f.write(f"\n--- Associativity: {ways}-way ---\n")
            l1, l2 = build_hierarchy(
                l1_size=32768, l1_block_size=64, l1_associativity=ways,
                l2_size=262144, l2_block_size=64, l2_associativity=4,
            )
            r = run_simulation(l1, l2, program_file, f)
            # area proxy: ways × (tag_bits + 2) bits per set
            from math import log2
            num_sets   = 32768 // (ways * 64)
            idx_bits   = int(log2(num_sets)) if num_sets > 1 else 0
            tag_bits   = 32 - 6 - idx_bits
            area_proxy = ways * (tag_bits + 2)
            e2_rows.append({"ways": ways, "area_proxy": area_proxy, **r})
        write_csv("e2_associativity.csv",
                  ["ways", "l1_miss_rate", "compulsory_misses",
                   "non_compulsory_misses", "area_proxy", "cpi_total"],
                  e2_rows)

        # E3
        f.write("\n\n--- E3: Block Size Variations ---\n")
        e3_rows = []
        for bs in [16, 32, 64, 128, 256]:
            f.write(f"\n--- Block Size: {bs} B ---\n")
            l1, l2 = build_hierarchy(
                l1_size=32768, l1_block_size=bs, l1_associativity=4,
                l2_size=262144, l2_block_size=bs, l2_associativity=4,
            )
            r = run_simulation(l1, l2, program_file, f)
            bandwidth = r["mem_traffic"] * bs
            e3_rows.append({"block_size_b": bs, "bandwidth_bytes": bandwidth, **r})
        write_csv("e3_block_size.csv",
                  ["block_size_b", "l1_miss_rate", "bandwidth_bytes", "amat", "cpi_total"],
                  e3_rows)

        # E4
        f.write("\n\n--- E4: Write Policy Variations ---\n")
        e4_rows = []
        for policy in [WritePolicy.WRITE_BACK, WritePolicy.WRITE_THROUGH]:
            f.write(f"\n--- Write Policy: {policy.value} ---\n")
            l1, l2 = build_hierarchy(
                l1_size=32768, l1_block_size=64, l1_associativity=4,
                l1_write_policy=policy,
                l2_size=262144, l2_block_size=64, l2_associativity=4,
                l2_write_policy=policy,
            )
            r = run_simulation(l1, l2, program_file, f)
            e4_rows.append({"write_policy": policy.value, **r})
        write_csv("e4_write_policy.csv",
                  ["write_policy", "mem_traffic", "dirty_evictions", "cpi_total"],
                  e4_rows)

        # E5
        f.write("\n\n--- E5: Replacement Policy Variations ---\n")
        e5_rows = []
        for policy in [ReplacementPolicy.LRU, ReplacementPolicy.FIFO]:
            f.write(f"\n--- Replacement: {policy.value} ---\n")
            l1, l2 = build_hierarchy(
                l1_size=32768, l1_block_size=64, l1_associativity=4,
                l1_replacement=policy,
                l2_size=262144, l2_block_size=64, l2_associativity=4,
                l2_replacement=policy,
            )
            r = run_simulation(l1, l2, program_file, f)
            e5_rows.append({"replacement": policy.value, **r})
        write_csv("e5_replacement.csv",
                  ["replacement", "l1_miss_rate", "l2_miss_rate", "cpi_total"],
                  e5_rows)

        # E6
        f.write("\n\n--- E6: Prefetching ---\n")
        e6_rows = []
        for enabled in [False, True]:
            label = "Enabled" if enabled else "Disabled"
            f.write(f"\n--- Prefetch: {label} ---\n")
            l1, l2 = build_hierarchy(
                l1_size=32768, l1_block_size=64, l1_associativity=4,
                l2_size=262144, l2_block_size=64, l2_associativity=4,
                prefetcher_enabled=enabled,
            )
            r = run_simulation(l1, l2, program_file, f)
            p = l1.prefetcher
            coverage    = p.coverage() if enabled else 0.0
            useless     = p.prefetches_useless if enabled else 0
            issued      = p.prefetches_issued if enabled else 0
            useless_rate = (useless / issued) if issued > 0 else 0.0
            f.write(f"\n[Prefetcher] issued={issued}  useful={p.prefetches_useful if enabled else 0}"
                    f"  useless={useless}  coverage={coverage:.2%}\n")
            e6_rows.append({
                "prefetch": label,
                "coverage": round(coverage, 4),
                "useless_rate": round(useless_rate, 4),
                "cpi_total": r["cpi_total"],
            })
        write_csv("e6_prefetch.csv",
                  ["prefetch", "coverage", "useless_rate", "cpi_total"],
                  e6_rows)

        # E8
        f.write("\n\n--- E8: L2 Cache Size Variations ---\n")
        e8_rows = []
        for l2_cap in [131072, 262144, 524288, 1048576, 2097152]:
            f.write(f"\n--- L2 Size: {l2_cap // 1024} KB ---\n")
            l1, l2 = build_hierarchy(
                l1_size=32768, l1_block_size=64, l1_associativity=4,
                l2_size=l2_cap, l2_block_size=64, l2_associativity=4,
            )
            r = run_simulation(l1, l2, program_file, f)
            e8_rows.append({"l2_size_kb": l2_cap // 1024, **r})
        write_csv("e8_l2_size.csv",
                  ["l2_size_kb", "l2_miss_rate", "amat", "cpi_total"],
                  e8_rows)

    print("Done. Results written to cache_test_report.txt and results/")


if __name__ == "__main__":
    main()
