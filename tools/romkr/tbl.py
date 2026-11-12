"""Thingy 호환 테이블(.tbl) 파일.

문법
  XX=あ        일반 매핑 (XX는 1바이트 이상 hex, 예: 8140=가)
  /XX=<END>    문자열 종료 토큰 (텍스트 생략 시 <END>)
  *XX          줄바꿈 (텍스트 '\n')
  XX=<WAIT>    제어 코드는 <이름> 형식 권장
  # 또는 ; 로 시작하는 줄은 주석
인코딩 시 [XXYY] 는 원시 바이트로 그대로 출력된다.
"""
from __future__ import annotations

import re

RAW_RE = re.compile(r"\[([0-9A-Fa-f]{2})+\]")


class TableError(Exception):
    pass


class Table:
    def __init__(self):
        self.dec: dict[bytes, str] = {}
        self.enc: dict[str, bytes] = {}
        self.ends: set[bytes] = set()
        self.max_key = 1
        self.max_text = 1

    # ---------------------------------------------------------------- load
    @classmethod
    def load(cls, *paths) -> "Table":
        t = cls()
        for p in paths:
            with open(p, encoding="utf-8-sig") as f:
                for n, line in enumerate(f, 1):
                    t._parse_line(line.rstrip("\r\n"), p, n)
        return t

    def _parse_line(self, line, path, n):
        if not line.strip() or line.lstrip()[:1] in "#;":
            return
        end = newline = False
        if line[0] == "/":
            end, line = True, line[1:]
        elif line[0] == "*":
            newline, line = True, line[1:]
        key, _, text = line.partition("=")
        key = key.strip()
        try:
            kb = bytes.fromhex(key)
        except ValueError as e:
            raise TableError(f"{path}:{n}: 잘못된 hex '{key}'") from e
        if newline:
            text = text or "\n"
        elif end:
            text = text or "<END>"
        text = text.replace("\\n", "\n")
        if text == "":
            raise TableError(f"{path}:{n}: 텍스트가 비어 있음")
        self.add(kb, text, end)

    def add(self, key: bytes, text: str, end=False):
        self.dec.setdefault(key, text)
        self.enc.setdefault(text, key)
        if end:
            self.ends.add(key)
        self.max_key = max(self.max_key, len(key))
        self.max_text = max(self.max_text, len(text))

    # ---------------------------------------------------------------- decode
    def decode(self, data: bytes, start: int, limit: int = 4096, stop_at_end=True):
        """(텍스트, 소비 바이트 수) 반환. 미등록 바이트는 [XX]."""
        out, pos, stop = [], start, min(len(data), start + limit)
        while pos < stop:
            for L in range(self.max_key, 0, -1):
                k = bytes(data[pos:pos + L])
                if len(k) == L and k in self.dec:
                    out.append(self.dec[k])
                    pos += L
                    if stop_at_end and k in self.ends:
                        return "".join(out), pos - start
                    break
            else:
                out.append(f"[{data[pos]:02X}]")
                pos += 1
        return "".join(out), pos - start

    # ---------------------------------------------------------------- encode
    def encode(self, text: str) -> bytes:
        out, i, missing = bytearray(), 0, []
        while i < len(text):
            m = RAW_RE.match(text, i)
            if m:
                out += bytes.fromhex(m.group(0)[1:-1])
                i = m.end()
                continue
            for L in range(min(self.max_text, len(text) - i), 0, -1):
                s = text[i:i + L]
                if s in self.enc:
                    out += self.enc[s]
                    i += L
                    break
            else:
                missing.append((i, text[i]))
                i += 1
        if missing:
            chars = "".join(sorted({c for _, c in missing}))
            raise TableError(f"테이블에 없는 문자 {len(missing)}개: {chars!r}")
        return bytes(out)

    def missing_chars(self, text: str) -> set[str]:
        try:
            self.encode(text)
            return set()
        except TableError:
            miss = set()
            for ch in RAW_RE.sub("", text):
                if ch not in self.enc and not any(ch in k for k in self.enc if len(k) > 1):
                    miss.add(ch)
            return miss

    def ends_with_end(self, b: bytes) -> bool:
        return any(b.endswith(e) for e in self.ends)
