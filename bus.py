import sys
import subprocess
from hierarchy import build_hierarchy
from enums import WritePolicy, ReplacementPolicy, Organization

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

    f = open("cache_test_report.txt", "w")

    if len(sys.argv) < 2:
        print("Usage: python bus.py <riscv_program.mem>")
        return

    program_file = sys.argv[1]
    f.write("\n\n--- TESTING L1 Cache Size Variations ---\n\n")
    print("\n\n--- TESTING L1 Cache Size Variations ---\n\n")
    for cap in [4096, 8192, 16384, 32768, 65536]:
        f.write("\n--- Testing L1 Cache Size: {} KB ---\n".format(cap // 1024))
        print("--- [Bus IPC Started] ---")
        print("Building L1/L2 Cache Hierarchy...")
        l1, l2 = build_hierarchy(
            l1_size=cap, l1_block_size=64, l1_associativity=2,
            l2_size=262144, l2_block_size=64, l2_associativity=4,
        )
        
        run_simulation(l1, l2, program_file, f)

    f.write("\n\n--- TESTING Block Size Variations ---\n\n")
    print("\n\n--- TESTING Block Size Variations ---\n\n")
    for bs in [16, 32, 64, 128, 256]:
        f.write("\n--- Testing Block Size: {} B ---\n".format(bs))
        print("--- [Bus IPC Started] ---")
        print("Building L1/L2 Cache Hierarchy...")
        l1, l2 = build_hierarchy(
            l1_size=32768, l1_block_size=bs, l1_associativity=2,
            l2_size=262144, l2_block_size=bs, l2_associativity=4,
        )
        
        run_simulation(l1, l2, program_file, f)

    f.write("\n\n--- TESTING Associativity Variations ---\n\n")
    print("\n\n--- TESTING Associativity Variations ---\n\n")
    for ways in [1, 2, 4, 8, 16]:
        f.write("\n--- Testing Associativity: {}-way ---\n".format(ways))
        print("--- [Bus IPC Started] ---")
        print("Building L1/L2 Cache Hierarchy...")
        l1, l2 = build_hierarchy(
            l1_size=32768, l1_block_size=64, l1_associativity=ways,
            l2_size=262144, l2_block_size=64, l2_associativity=4,
        )

        run_simulation(l1, l2, program_file, f)

    f.write("\n\n--- TESTING Write Policy Variations ---\n\n")
    print("\n\n--- TESTING Write Policy Variations ---\n\n")
    for policy in [WritePolicy.WRITE_BACK, WritePolicy.WRITE_THROUGH]:
        f.write("\n--- Testing Write Policy: {} ---\n".format(policy.value))
        print("--- [Bus IPC Started] ---")
        print("Building L1/L2 Cache Hierarchy...")
        l1, l2 = build_hierarchy(
            l1_size=32768, l1_block_size=64, l1_associativity=2, l1_write_policy=policy,
            l2_size=262144, l2_block_size=64, l2_associativity=4, l2_write_policy=policy,
        )

        run_simulation(l1, l2, program_file, f)

    f.write("\n\n--- TESTING Replacement Policy Variations ---\n\n")
    print("\n\n--- TESTING Replacement Policy Variations ---\n\n")
    for policy in [ReplacementPolicy.LRU, ReplacementPolicy.FIFO]:
        f.write("\n--- Testing Replacement Policy: {} ---\n".format(policy.value))
        print("--- [Bus IPC Started] ---")
        print("Building L1/L2 Cache Hierarchy...")
        l1, l2 = build_hierarchy(
            l1_size=32768, l1_block_size=64, l1_associativity=2, l1_replacement=policy,
            l2_size=262144, l2_block_size=64, l2_associativity=4, l2_replacement=policy,
        )

        run_simulation(l1, l2, program_file, f)

    f.write("\n\n--- TESTING Prefetch ---\n\n")
    print("\n\n--- TESTING Prefetch ---\n\n")
    for should_prefetch in [False, True]:
        f.write("\n--- Testing Prefetch: {} ---\n".format("Enabled" if should_prefetch else "Disabled"))
        print("--- [Bus IPC Started] ---")
        print("Building L1/L2 Cache Hierarchy...")
        l1, l2 = build_hierarchy(
            l1_size=32768, l1_block_size=64, l1_associativity=2, prefetcher_enabled=should_prefetch,
            l2_size=262144, l2_block_size=64, l2_associativity=4,
        )

        run_simulation(l1, l2, program_file, f)
        p = l1.prefetcher
        f.write("\n[Prefetcher Performance]")
        f.write(f"\nPrefetches Issued: {p.prefetches_issued}")
        f.write(f"\nPrefetches Useful: {p.prefetches_useful}")
        f.write(f"\nPrefetches Useless: {p.prefetches_useless}")
        f.write(f"\nPrefetch Coverage: {p.coverage() * 100:.2f}%")

def run_simulation(l1, l2, program_file, f, instruction_limit=2000):
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
        if instructions_estimated > instruction_limit:
            print("\n[Bus] Instruction limit (2000) reached. Breaking infinite loop.")
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
            #if instructions_estimated % 100 == 0:
                #print(f"[Bus] Processed {instructions_estimated} fetches...", flush=True)
            
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
    
    f.write("\n\n--- [Simulation Completed] ---")
    f.write(f"Total Stalls Handled: {total_stalls} cycles")
    f.write("\n[Cache Performance Reports]")
    f.write(l1.report())
    f.write(l2.report())

    f.write("\n--- [CPI Analysis Approximation] ---")
    # Base in-order CPI is roughly 1.0 (excluding branches/flushes). 
    f.write(f"Stall CPI Component: {total_stalls} stalls / ~(Instruction Fetches) = {(total_stalls/instructions_estimated if instructions_estimated else 0):.4f}")

if __name__ == "__main__":
    main()
