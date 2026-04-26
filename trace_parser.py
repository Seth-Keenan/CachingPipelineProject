def parse_trace(filepath: str) -> list[dict]:
    records = []
    with open(filepath) as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) < 2:
                continue
            op, addr_str = parts[0], parts[1]
            if op not in ("L", "S"):
                continue
            records.append({"type": op, "address": int(addr_str, 16)})
    return records
