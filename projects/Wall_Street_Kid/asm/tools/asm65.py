"""asm65 - 최소 2패스 6502 어셈블러 (py65 백엔드). asm6f/ca65 가 없는 환경용.
(Super_Express_Satsujin_Jiken/asm/tools/asm65.py 복사본 + `.include "파일"` 지원. UxROM 16KB 뱅크 b 는 .bank 2b/2b+1)

사용: python asm/tools/asm65.py <src.asm> <rom.nes> [--sym out.sym]
  롬 파일을 제자리 패치한다(롬은 expand.py 로 확장된 레이아웃이어야 함).

지원 문법 (asm6f 부분집합 + 2개 확장):
  NAME = expr            상수 (사용 전에 정의)
  label:                 전역 라벨,  @local: 직전 전역 라벨 범위의 지역 라벨
  .bank N[,M,..]         8KB PRG 뱅크 번호(확장 후 레이아웃). 파일 오프셋 = 0x10 + N*0x2000 + (pc & 0x1FFF)
                         여러 개면 같은 코드를 모든 뱅크에 복제(.expect 는 첫 뱅크 기준)
  .org $XXXX             CPU 주소
  .limit $XXXX           pc 가 이 주소를 넘으면 에러 (빈 공간 경계)
  .expect AA BB ..       현재 위치의 원본 바이트 검증(훅 지점 확인용, 바이트는 안 씀)
  .db x,y,..  .dw x,..   데이터
  니모닉은 py65 문법: LDA ($00),Y / STA $04CD / ASL A / JMP ($00BD) ...
  피연산자 식: 심볼, 심볼+N, 심볼-N, <expr (하위), >expr (상위), 10진/$16진/%2진
"""
import re
import sys

from py65.assembler import Assembler
from py65.devices.mpu6502 import MPU

NUM = r"(\$[0-9A-Fa-f]+|%[01]+|\d+)"


def parse_num(t):
    t = t.strip()
    if t.startswith("$"):
        return int(t[1:], 16)
    if t.startswith("%"):
        return int(t[1:], 2)
    return int(t)


class AsmError(Exception):
    pass


class Asm:
    def __init__(self):
        self.sym = {}
        self.asm = Assembler(MPU())

    def eval(self, expr, pc, scope, strict):
        e = expr.strip()
        lo = hi = False
        if e.startswith("<"):
            lo, e = True, e[1:]
        elif e.startswith(">"):
            hi, e = True, e[1:]
        total = 0
        for sign, tok in re.findall(r"([+-]?)\s*([@A-Za-z_][\w@]*|\$[0-9A-Fa-f]+|%[01]+|\d+)", e):
            if re.match(NUM + "$", tok):
                v = parse_num(tok)
            else:
                name = scope + tok if tok.startswith("@") else tok
                if name in self.sym:
                    v = self.sym[name]
                elif strict:
                    raise AsmError(f"정의 안 된 심볼: {tok}")
                else:
                    v = pc  # 1패스 자리표시(절대주소 크기로 계산됨)
            total += -v if sign == "-" else v
        if lo:
            total &= 0xFF
        if hi:
            total = (total >> 8) & 0xFF
        return total

    def subst(self, operand, pc, scope, strict):
        """피연산자 안의 식을 $hex 로 치환해 py65 가 읽을 수 있게 한다."""
        if not operand or operand.upper() == "A":
            return operand
        m = re.match(r"^(#?)(\(?)(.*?)(\)?,[XxYy]\)?|\),[Yy]|,[XxYy]|\))?$", operand.strip())
        imm, par, body, tail = m.group(1), m.group(2), m.group(3), m.group(4) or ""
        v = self.eval(body, pc, scope, strict)
        width = 2 if (imm or v < 0x100 and not re.search(r"[A-Za-z_]", body.lstrip("<>"))
                      and len(body.strip().lstrip("$")) <= 2) else 4
        if imm:
            width = 2
            v &= 0xFF
        return f"{imm}{par}${v:0{width}X}{tail}"

    def run(self, lines, rom=None, strict=False):
        pc, bank, scope, limit = 0, None, "", None
        banks = []
        out = []  # (file_offset, bytes, line_no)
        for no, raw in enumerate(lines, 1):
            line = raw.split(";", 1)[0].rstrip()
            if not line.strip():
                continue
            try:
                m = re.match(r"^\s*([A-Za-z_]\w*)\s*=\s*(.+)$", line)
                if m:
                    self.sym[m.group(1)] = self.eval(m.group(2), pc, scope, True)
                    continue
                m = re.match(r"^\s*(@?[A-Za-z_]\w*):(.*)$", line)
                if m:
                    name = m.group(1)
                    if not name.startswith("@"):
                        scope = name
                        full = name
                    else:
                        full = scope + name
                    if strict and self.sym.get(full) != pc:
                        raise AsmError(f"라벨 위치 불일치(2패스): {name}")
                    self.sym[full] = pc
                    line = m.group(2)
                    if not line.strip():
                        continue
                parts = line.strip().split(None, 1)
                op = parts[0]
                arg = parts[1].strip() if len(parts) > 1 else ""
                ol = op.lower()
                if ol == ".bank":
                    banks = [self.eval(x, pc, scope, True) for x in arg.split(",")]
                    bank = banks[0]
                    continue
                if ol == ".org":
                    pc = self.eval(arg, pc, scope, True)
                    limit = None
                    continue
                if ol == ".limit":
                    limit = self.eval(arg, pc, scope, True)
                    continue
                if bank is None:
                    raise AsmError(".bank 가 먼저 필요")
                fo = 0x10 + bank * 0x2000 + (pc & 0x1FFF)
                if rom is not None:      # .bank 과 .org 창 불일치 검사(UxROM: 마지막 2개 = $C000/$E000 고정)
                    nb8 = (len(rom) - 16) // 0x2000
                    for b_ in banks:
                        win = (0xC000 if b_ >= nb8 - 2 else 0x8000) + (b_ % 2) * 0x2000
                        if pc & 0xE000 != win:
                            raise AsmError(f".bank {b_} 의 창은 ${win:04X}-${win + 0x1FFF:04X} 인데 pc=${pc:04X}")
                if ol == ".expect":
                    exp = bytes(int(x, 16) for x in arg.split())
                    if strict and rom is not None and bytes(rom[fo:fo + len(exp)]) != exp:
                        raise AsmError(f".expect 불일치 @{pc:04X}: 롬={bytes(rom[fo:fo+len(exp)]).hex(' ')} 기대={exp.hex(' ')}")
                    continue
                if ol in (".db", ".byte"):
                    data = bytes(self.eval(x, pc, scope, strict) & 0xFF for x in arg.split(","))
                elif ol in (".dw", ".word"):
                    data = b"".join((self.eval(x, pc, scope, strict) & 0xFFFF).to_bytes(2, "little")
                                    for x in arg.split(","))
                else:
                    stmt = op.upper() + (" " + self.subst(arg, pc, scope, strict) if arg else "")
                    if op.upper() in ("BCC", "BCS", "BEQ", "BNE", "BMI", "BPL", "BVC", "BVS"):
                        tgt = self.eval(arg, pc, scope, strict)
                        if strict and not -128 <= tgt - (pc + 2) <= 127:
                            raise AsmError(f"분기 범위 초과 → {arg}")
                        if not strict:
                            tgt = pc
                        stmt = f"{op.upper()} ${tgt:04X}"
                    b = self.asm.assemble(stmt, pc)
                    if b is None:
                        raise AsmError(f"어셈블 실패: {stmt}")
                    data = bytes(b)
                if limit is not None and pc + len(data) - 1 > limit:
                    raise AsmError(f".limit ${limit:04X} 초과 (pc=${pc:04X}+{len(data)})")
                for b_ in banks:
                    out.append((0x10 + b_ * 0x2000 + (pc & 0x1FFF), data, no))
                pc += len(data)
            except AsmError as e:
                raise AsmError(f"{no}행: {raw.strip()}  → {e}")
        return out


def read_source(path, depth=0):
    """`.include "파일"` 을 펼친다(경로는 포함하는 파일 기준 → 없으면 현재 작업 디렉터리 기준)."""
    import os
    out = []
    for line in open(path, encoding="utf-8").read().splitlines():
        m = re.match(r'^\s*\.include\s+"([^"]+)"', line)
        if m:
            if depth > 8:
                raise AsmError(".include 너무 깊음")
            p = os.path.join(os.path.dirname(path), m.group(1))
            if not os.path.exists(p):
                p = m.group(1)
            out += read_source(p, depth + 1)
        else:
            out.append(line)
    return out


def assemble(src_path, rom):
    lines = read_source(src_path)
    a = Asm()
    a.run(lines, rom, strict=False)
    out = a.run(lines, rom, strict=True)
    return a, out


def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("src")
    p.add_argument("rom")
    p.add_argument("--sym")
    p.add_argument("--dry", action="store_true")
    a = p.parse_args()
    rom = bytearray(open(a.rom, "rb").read())
    try:
        asm, out = assemble(a.src, rom)
    except AsmError as e:
        sys.exit(f"asm65 오류: {e}")
    n = 0
    for fo, data, _ in out:
        rom[fo:fo + len(data)] = data
        n += len(data)
    if not a.dry:
        open(a.rom, "wb").write(rom)
    if a.sym:
        with open(a.sym, "w", encoding="utf-8") as f:
            for k, v in sorted(asm.sym.items(), key=lambda kv: kv[1]):
                f.write(f"{v:04X} {k}\n")
    print(f"asm65: {a.src} → {n} 바이트 패치 ({len(out)} 문)")


if __name__ == "__main__":
    main()
