from hierarchy import build_hierarchy


def run_smoke_test():
    print("Building L1 / L2 cache hierarchy...")
    l1, l2 = build_hierarchy(
        l1_size=1024, l1_block_size=64, l1_associativity=2,
        l2_size=8192, l2_block_size=64, l2_associativity=4,
    )
    print(f"  {l1}")
    print(f"  {l2}")

    print("\n[1] Sequential reads  (0x0000 -> 0x03FF, step 4)")
    for addr in range(0x0000, 0x0400, 4):
        l1.read(addr)

    print("[2] Repeat reads      (expecting high hit rate)")
    for addr in range(0x0000, 0x0400, 4):
        l1.read(addr)

    print("[3] Writes            (0x0000 -> 0x003F, step 4)")
    for addr in range(0x0000, 0x0040, 4):
        l1.write(addr)

    print(l1.report())
    print(l2.report())

    l1_amat = l1.amat(hit_time=1, miss_penalty=10)
    print(f"L1 AMAT (hit=1 cycle, miss penalty=10 cycles): {l1_amat:.4f} cycles\n")


if __name__ == "__main__":
    run_smoke_test()
