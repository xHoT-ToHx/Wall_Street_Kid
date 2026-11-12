"""romkr - 레트로 게임 롬 한글화 공용 툴킷 (FC/SFC/MD/SMS/GB/GBC/PS)."""
__version__ = "0.1.0"


def parse_int(v):
    """'0x1F', '$1F', '31', 31 모두 정수로."""
    if isinstance(v, int):
        return v
    s = str(v).strip().replace("_", "")
    if s.startswith("$"):
        return int(s[1:], 16)
    return int(s, 0)
