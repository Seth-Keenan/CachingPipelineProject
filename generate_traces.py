"""
Generate three synthetic RISC-V memory-access trace files:
  traces/sequential.trace  – stride-1 array copy
  traces/matrix.trace      – 32x32 matrix multiply
  traces/random.trace      – linked-list random walk

Each file follows the format:   <L|S> <hex_address>
Run once before simulate_trace.py:  python generate_traces.py
"""

import os
import random

os.makedirs("traces", exist_ok=True)


def write_trace(path: str, records: list[tuple[str, int]]):
    with open(path, "w") as fh:
        for op, addr in records:
            fh.write(f"{op} 0x{addr:08X}\n")
    print(f"  {path}: {len(records):,} accesses")


# Sequential Matrix
def gen_sequential():
    records = []
    base_src = 0x10000000
    base_dst = 0x10020000   
    N = 16384               
    for i in range(N):
        records.append(("L", base_src + i * 4))
        records.append(("S", base_dst + i * 4))
    return records


# Matrix Multiply
def gen_matrix():
    records = []
    base_A = 0x10100000
    base_B = 0x10101000
    base_C = 0x10102000
    N = 32
    for i in range(N):
        for j in range(N):
            for k in range(N):
                records.append(("L", base_A + (i * N + k) * 4))  # A[i][k]
                records.append(("L", base_B + (k * N + j) * 4))  # B[k][j]
            records.append(("S", base_C + (i * N + j) * 4))      # C[i][j]
    return records


# Random
def gen_random():
    rng = random.Random(42)           # fixed seed for reproducibility
    base   = 0x10200000
    stride = 64                       # one node per cache line
    n_nodes = 1024
    node_addrs = [base + i * stride for i in range(n_nodes)]
    order = list(range(n_nodes))
    rng.shuffle(order)                # random traversal order

    records = []
    traversals = 50                   # 50 × 1024 = 51 200 accesses
    for _ in range(traversals):
        for idx in order:
            records.append(("L", node_addrs[idx]))
    return records


if __name__ == "__main__":
    print("Generating trace files…")
    write_trace("traces/sequential.trace", gen_sequential())
    write_trace("traces/matrix.trace",     gen_matrix())
    write_trace("traces/random.trace",     gen_random())
    print("Done.")
