import sys
import subprocess
from hierarchy import build_hierarchy

L1_MISS_PENALTY = 10
L2_MISS_PENALTY = 100

def get_total_misses(cache):
    return cache.stats["read_misses"] + cache.stats["write_misses"]

def calculate_penalty_and_do_access(l1, l2, address, is_write):
    # Snapshot missed before operation
    l1_misses_before = get_total_misses(l1)
    l2_misses_before = get_total_misses(l2)

    # Perform the access operations
    if is_write:
        l1.write(address)
    else:
        l1.read(address)

    # Calculate difference
    l1_misses_after = get_total_misses(l1)
    l2_misses_after = get_total_misses(l2)

    l1_missed = (l1_misses_after > l1_misses_before)
    l2_missed = (l2_misses_after > l2_misses_before)

    penalty = 0
    if l1_missed:
        if l2_missed:
            penalty = L2_MISS_PENALTY
        else:
            penalty = L1_MISS_PENALTY

    return penalty

def main():
    if len(sys.argv) < 2:
        print("Usage: python bus.py <riscv_program.mem>")
        return

    program_file = sys.argv[1]

    print("--- [Bus IPC Started] ---")
    print("Building L1/L2 Cache Hierarchy...")
    l1, l2 = build_hierarchy(
        l1_size=1024, l1_block_size=64, l1_associativity=2,
        l2_size=8192, l2_block_size=64, l2_associativity=4,
    )
    
    print("Spawning mu-riscv.exe Process...")
    # Using bufsize 1 (line buffered) and universal_newlines (text mode)
    proc = subprocess.Popen(
        ["mu-riscv.exe", program_file],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1
    )

    total_stalls = 0
    instructions_estimated = 0  # VERY rough estimation based on fetching

    print("Bus is listening...")
    sys.stdout.flush()

    # Consume the stdout lines
    while True:
        if instructions_estimated > 1000:
            print("\n[Bus] Instruction limit (1000) reached. Breaking infinite loop.")
            proc.kill()
            break

        line = proc.stdout.readline()
        if not line:
            break
        line = line.strip()

        if line.startswith("READ "):
            addr_hex = line.split(" ")[1]
            address = int(addr_hex, 16)
            penalty = calculate_penalty_and_do_access(l1, l2, address, is_write=False)
            total_stalls += penalty
            proc.stdin.write(f"{penalty}\n")
            proc.stdin.flush()
            instructions_estimated += 1
            if instructions_estimated % 100 == 0:
                print(f"[Bus] Processed {instructions_estimated} fetches...", flush=True)
            
        elif line.startswith("WRITE "):
            addr_hex = line.split(" ")[1]
            address = int(addr_hex, 16)
            penalty = calculate_penalty_and_do_access(l1, l2, address, is_write=True)
            total_stalls += penalty
            proc.stdin.write(f"{penalty}\n")
            proc.stdin.flush()
        else:
            # We can log or print other simulator text
            pass

    proc.wait()
    
    print("\n\n--- [Simulation Completed] ---")
    print(f"Total Stalls Handled: {total_stalls} cycles")
    print("\n[Cache Performance Reports]")
    print(l1.report())
    print(l2.report())

    p = l1.prefetcher
    print("\n[Prefetcher Performance]")
    print(f"Prefetches Issued: {p.prefetches_issued}")
    print(f"Prefetches Useful: {p.prefetches_useful}")
    print(f"Prefetches Useless: {p.prefetches_useless}")
    print(f"Prefetch Coverage: {p.coverage() * 100:.2f}%")

    print("\n--- [CPI Analysis Approximation] ---")
    # Base in-order CPI is roughly 1.0 (excluding branches/flushes). 
    print(f"Stall CPI Component: {total_stalls} stalls / ~(Instruction Fetches) = {(total_stalls/instructions_estimated if instructions_estimated else 0):.4f}")

if __name__ == "__main__":
    main()
