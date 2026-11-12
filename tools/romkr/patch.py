"""IPS / BPS 패치 생성·적용. (PS 디스크 이미지는 xdelta3 사용 권장)"""
from __future__ import annotations

import zlib


class PatchError(Exception):
    pass


def crc(b):
    return zlib.crc32(b) & 0xFFFFFFFF


# ---------------------------------------------------------------- IPS
def ips_create(src: bytes, dst: bytes) -> bytes:
    if len(dst) > 0x1000000:
        raise PatchError("IPS는 16MB 초과 불가 - BPS 사용")
    out = bytearray(b"PATCH")
    n, i = len(dst), 0
    while i < n:
        if i < len(src) and src[i] == dst[i]:
            i += 1
            continue
        start = i
        if start == 0x454F46:          # 'EOF' 오프셋 회피
            start -= 1
        j = i
        while j < n and j - start < 0xFFFF and (j >= len(src) or src[j] != dst[j]):
            j += 1
        rec = dst[start:j]
        out += start.to_bytes(3, "big") + len(rec).to_bytes(2, "big") + rec
        i = j
    out += b"EOF"
    if len(dst) < len(src):
        out += len(dst).to_bytes(3, "big")
    return bytes(out)


def ips_apply(src: bytes, patch: bytes) -> bytes:
    if patch[:5] != b"PATCH":
        raise PatchError("IPS 아님")
    out, p = bytearray(src), 5
    while patch[p:p + 3] != b"EOF":
        off = int.from_bytes(patch[p:p + 3], "big")
        size = int.from_bytes(patch[p + 3:p + 5], "big")
        p += 5
        if size == 0:                  # RLE
            rl = int.from_bytes(patch[p:p + 2], "big")
            data = patch[p + 2:p + 3] * rl
            p += 3
        else:
            data = patch[p:p + size]
            p += size
        if off + len(data) > len(out):
            out.extend(b"\0" * (off + len(data) - len(out)))
        out[off:off + len(data)] = data
    p += 3
    if len(patch) - p == 3:
        del out[int.from_bytes(patch[p:p + 3], "big"):]
    return bytes(out)


# ---------------------------------------------------------------- BPS
def _enc(n):
    out = bytearray()
    while True:
        x, n = n & 0x7F, n >> 7
        if n == 0:
            out.append(0x80 | x)
            return bytes(out)
        out.append(x)
        n -= 1


def bps_create(src: bytes, dst: bytes, metadata: bytes = b"") -> bytes:
    out = bytearray(b"BPS1") + _enc(len(src)) + _enc(len(dst)) + _enc(len(metadata)) + metadata
    n, ls, i = len(dst), len(src), 0
    while i < n:
        j = i
        if i < ls and src[i] == dst[i]:
            while j < n and j < ls and src[j] == dst[j]:
                j += 1
            out += _enc(((j - i - 1) << 2) | 0)
        else:
            while j < n and not (j < ls and src[j] == dst[j]):
                j += 1
            out += _enc(((j - i - 1) << 2) | 1) + dst[i:j]
        i = j
    out += crc(src).to_bytes(4, "little") + crc(dst).to_bytes(4, "little")
    out += crc(out).to_bytes(4, "little")
    return bytes(out)


def bps_apply(src: bytes, patch: bytes) -> bytes:
    if patch[:4] != b"BPS1":
        raise PatchError("BPS 아님")
    if crc(patch[:-4]) != int.from_bytes(patch[-4:], "little"):
        raise PatchError("패치 CRC 불일치")
    pos = 4

    def dec():
        nonlocal pos
        data, shift = 0, 1
        while True:
            x = patch[pos]
            pos += 1
            data += (x & 0x7F) * shift
            if x & 0x80:
                return data
            shift <<= 7
            data += shift

    ssize, tsize, msize = dec(), dec(), dec()
    pos += msize
    if ssize != len(src) or crc(src) != int.from_bytes(patch[-12:-8], "little"):
        raise PatchError("원본 롬이 패치 대상과 다름 (CRC/크기 불일치)")
    out = bytearray(tsize)
    op = srel = trel = 0
    end = len(patch) - 12
    while pos < end:
        d = dec()
        mode, length = d & 3, (d >> 2) + 1
        if mode == 0:
            out[op:op + length] = src[op:op + length]
        elif mode == 1:
            out[op:op + length] = patch[pos:pos + length]
            pos += length
        else:
            d2 = dec()
            off = -(d2 >> 1) if d2 & 1 else (d2 >> 1)
            if mode == 2:
                srel += off
                out[op:op + length] = src[srel:srel + length]
                srel += length
            else:
                trel += off
                for k in range(length):
                    out[op + k] = out[trel + k]
                trel += length
        op += length
    if crc(out) != int.from_bytes(patch[-8:-4], "little"):
        raise PatchError("결과 CRC 불일치")
    return bytes(out)


def create(src, dst, kind):
    return ips_create(src, dst) if kind == "ips" else bps_create(src, dst)


def apply(src, patch):
    return ips_apply(src, patch) if patch[:5] == b"PATCH" else bps_apply(src, patch)
