; kor_engine.asm - Wall Street Kid 한글 엔진 (UOROM 256KB, 8x16 동적 업로드, 대사창 BG 패턴테이블 분할)
; 어셈블: python asm/tools/asm65.py asm/kor_engine.asm <rom> --sym build/kor_engine.sym
; 전제: python asm/tools/expand.py <rom> --copy 4:12 --copy 6:13   (고정뱅크 15, 엔진 뱅크 7)
;       python asm/tools/kor_build.py tables  → build/kor_tables.asm (아래 .include)
; 설계: asm/DESIGN.md, 훅/빈공간: asm/CHANGES.md
;
; 16KB 뱅크 b 의 .bank 번호 = 2b ($8000-$9FFF) / 2b+1 ($A000-$BFFF).  고정뱅크 15 = .bank 30 ($C000) / 31 ($E000)

; ---------------------------------------------------------------- RAM ($0600 페이지, 원본 미사용 [정적+카나리])
KLO     = $0600          ; [107] 슬롯별 글리프 번호 lo
KHI     = $0670          ; [107] 슬롯별 글리프 번호 hi ($FF = 비어 있음)
KACT    = $06E0          ; 0 꺼짐 / 1,2 사본 업로드 중 / 3 활성(분할)
KFAIL   = $06E1          ; 연속 분할 실패 수
KNEXT   = $06E2          ; 다음 할당 슬롯(원형)
KPEND   = $06E3          ; 1 = KBUF 업로드 대기
KPT     = $06E4          ; 대기 글리프의 윗타일 번호
KTWO    = $06E5          ; 1 = 이번 플러시는 2행(8x16)
KGLO    = $06E6
KGHI    = $06E7
KC      = $06E8          ; 1바이트 코드 임시
KT      = $06E9          ; 현재 글자 윗타일
KSPL    = $06EA          ; 분할 스캔라인용 OAM Y (창 윗행*8-1)
KBUF    = $06F0          ; [16] 글리프 1bpp (위 8 + 아래 8)

; ---------------------------------------------------------------- 상수
NSLOT    = 107
REFRESH  = 40             ; asm/tools/kor_build.py 의 REFRESH 와 같게 (모의 검사)
ENGBANK  = 7
FONTBANK = 8              ; 글리프 n → 뱅크 8+(n>>10), $8000+(n&$3FF)*16
SPLITTOP = 16             ; 이 행 이상(y>=16)의 창만 한글 표시
OVSLOT   = $02DC          ; 오버플로 감지용 스프라이트 9개 = OAM 슬롯 55-63
OVTILE   = $40            ; $1000 타일 0x40 (빈 타일로 업로드)

BUS      = $FE90          ; 버스충돌 표 0..15 (원래 $F07E 0..6)

; ================================================================= 고정뱅크 훅
.bank 31
.org $F076                ; 뱅크 전환 $F066 의 STA $F07E,X
.expect 9D 7E F0
  STA BUS,X
.org $F8ED                ; NMI 큐 작업의 뱅크 전환
.expect 9D 7E F0
  STA BUS,X
.org $F970                ; NMI: OAM DMA 직후, $0B 작업 전
.expect A5 0C F0 0D
  JSR nmi_pre
  NOP
.org $F9BE                ; NMI 끝: LDA #0 / STA $05
.expect A9 00 85 05
  JSR nmi_post
  NOP
.org $F197                ; PPUMASK 갱신 공통 꼬리 (STA $02 / STA $2001 / RTS)
.expect 85 02 8D 01 20 60
  JMP kmask

.bank 30
.org $D7BC                ; $D7B6: 텍스트 뱅크 전환
.expect 30 09 AA A5 07 48 8A 20 66 F0 68
  JSR kbank
  JMP $D7C7
  NOP
  NOP
  NOP
  NOP
  NOP
.org $D7CB                ; $D7B6 끝: 뱅크 복원
.expect 68 30 03 20 66 F0
  PLA
  JSR fastsw              ; kbank 가 항상 복원할 뱅크(<$80)를 돌려줌
  NOP
  NOP
.org $D90E                ; $D8F8: 문자 판정
.expect 8A C9 FB 90 05
  JMP khook
  NOP
  NOP
.org $D948                ; $D936: 플러시 레코드 행 수
.expect 8C 25 03
  JSR krows
.org $D8A8                ; <PAGE>: 창 지우기
.expect 20 62 DA
  JSR kpage
.bank 31
.org $F03B                ; 리셋 초기화 끝 JMP ($FFDE)
.expect 6C DE FF
  JMP kinit

; ================================================================= 고정뱅크 본체 ($FE90-$FFBF)
.bank 31
.org $FE90
.limit $FFBF
  .db 0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15

; A = 뱅크 → $07 갱신 후 전환 (NMI 안전: $07 먼저)
fastsw:
  STA $07
  TAX
  STA BUS,X
  RTS

; ---- $D90E 대체: X = 읽은 바이트, 포인터는 이미 +1
khook:
  TXA
  CMP #$FB
  BCS @ctl
  CMP #$4F
  BCC @one
  CMP #$60
  BCS @one
  CMP #$50
  BCC @jmp
  SBC #$50
  STA KGHI
  LDY #0
  LDA ($81),Y
  STA KGLO
  INC $81
  BNE @k1
  INC $82
@k1:
  LDA $07
  PHA
  LDA #ENGBANK
  JSR fastsw
  JSR eng_kor
  PLA
  JMP fastsw
@ctl:
  STA $73
  RTS
@one:
  STA KC
  LDX KACT
  CPX #3
  BNE @orig
  LDA $07
  PHA
  LDA #ENGBANK
  JSR fastsw
  JSR eng_one
  PLA
  JSR fastsw
  BCC @ret
@orig:
  LDA KC
  CMP #$FB
  JMP $D918
@ret:
  RTS
@jmp:                     ; 4F bb ll hh : 뱅크 bb 의 $hhll 로 이어 읽기
  LDY #2
  LDA ($81),Y
  PHA
  DEY
  LDA ($81),Y
  PHA
  DEY
  LDA ($81),Y
  JSR fastsw
  PLA
  STA $81
  PLA
  STA $82
  JMP $D8F8

; ---- $D7BC: A = 요청 뱅크(FF=현재) → 4→12, 6→13 치환. 반환 A = 복원할 뱅크
kbank:
  CMP #$FF
  BNE @b1
  LDA $07
@b1:
  CMP #4
  BNE @b2
  LDA #12
@b2:
  CMP #6
  BNE @b3
  LDA #13
@b3:
  CMP $07
  BEQ @same
  TAX
  LDA $07
  PHA
  TXA
  JSR $F066
  PLA
  RTS
@same:
  LDA $07
  RTS

; ---- $D948: 8x16 글자가 있었으면 2행 플러시
krows:
  LDA KTWO
  BEQ @r
  LDY #2
@r:
  STY $0325
  LDA #0
  STA KTWO
  RTS

; ---- <PAGE> 창 지우기 전 슬롯 캐시 초기화
kpage:
  JSR kreset
  JMP $DA62
kreset:
  LDA #$FF
  LDX #NSLOT-1
@l:
  STA KHI,X
  DEX
  BPL @l
  LDA #0
  STA KNEXT
  RTS

; ---- PPUMASK: BG 또는 스프라이트가 꺼지면 분할 해제
kmask:
  STA $02
  STA $2001
  PHA
  AND #$18
  CMP #$18
  BEQ @m
  LDA KACT
  BEQ @m
  LDA #4                  ; NMI 가 감지 스프라이트를 숨기고 0 으로
  STA KACT
@m:
  PLA
  RTS

; ---- 리셋 초기화 ($F03B JMP ($FFDE) 대체)
kinit:
  LDA #0
  STA KACT
  STA KPEND
  STA KTWO
  JMP ($FFDE)

; ---- NMI 훅 (엔진 뱅크 호출, $07 은 건드리지 않음)
nmi_pre:
  LDA #ENGBANK
  TAX
  STA BUS,X
  JSR eng_nmipre
  LDX $07
  TXA
  STA BUS,X
  LDA $0C
  BNE @p
  PLA
  PLA
  JMP $F981
@p:
  RTS

nmi_post:
  LDA #ENGBANK
  TAX
  STA BUS,X
  JSR eng_split
  LDX $07
  TXA
  STA BUS,X
  LDA #0
  STA $05
  RTS

; ================================================================= 엔진 뱅크 7 ($8000-$BFFF)
.bank 14
.org $8000
.limit $9FFF
  JMP $C010               ; 다른 뱅크와 같은 머리(안전용)

; ---- 2바이트 한글 (KGLO/KGHI = 글리프 번호)
eng_kor:
  JSR glyph_emit
  RTS

; ---- 1바이트 원본 문자: 활성·2행 피치·분할 아래면 8x16 ASCII 글리프로. C=0 처리함 / C=1 원래 경로
eng_one:
  LDA $75
  CMP #SPLITTOP
  BCC @no
  LDA $7A
  AND #1
  BEQ @no
  LDA KC
  AND #$7F
  CMP #$37
  BCS @no
  TAX
  LDA ASC_HI,X
  CMP #$FF
  BEQ @no
  STA KGHI
  LDA ASC_LO,X
  STA KGLO
  LDA KC
  BPL @n1
  INC $7B
@n1:
  JSR glyph_emit
  CLC
  RTS
@no:
  SEC
  RTS

; ---- 글리프 배치: 슬롯 찾기/할당, 버퍼에 윗/아래 타일 기록
glyph_emit:
  LDA $75
  CMP #SPLITTOP
  BCS @row
  LDA #$49                ; 분할 위쪽 창: 표시 불가 → 공백
  STA KT
  JMP @put1
@row:
  LDA KACT
  CMP #3
  BEQ @act
  ; ---- 활성화: 캐시 초기화, 분할 행 결정, 사본 업로드 대기
  JSR kreset
  LDA #0
  STA KFAIL
  LDA $77                 ; 창 윗행
  ASL A
  ASL A
  ASL A
  SEC
  SBC #1
  STA KSPL
@req:
  LDA #1
  STA KACT
@w:
  JSR $F03E
  LDA KACT
  CMP #3
  BEQ @act
  CMP #1
  BEQ @w
  CMP #2
  BEQ @w
  JMP @req                ; 대기 중 렌더링 꺼짐(0/4) → 다시 요청
@act:
  LDX #NSLOT-1
@find:
  LDA KLO,X
  CMP KGLO
  BNE @nx
  LDA KHI,X
  CMP KGHI
  BEQ @hit
@nx:
  DEX
  BPL @find
  ; ---- 미스: 원형 할당
@pw:
  LDA KPEND
  BEQ @np
  JSR $F03E
  JMP @pw
@np:
  JSR kcopy
  LDX KNEXT
  LDA KGLO
  STA KLO,X
  LDA KGHI
  STA KHI,X
  LDA SLOTTOP,X
  STA KPT
  INX
  CPX #NSLOT
  BCC @nn
  LDX #0
@nn:
  STX KNEXT
  LDA KPT
  STA KT
  LDA #1
  STA KPEND
  JMP @emit
@hit:                     ; 곧 덮일 슬롯(다음 할당 위치에서 REFRESH 안)이면 새 슬롯으로 옮김
  TXA
  SEC
  SBC KNEXT
  BCS @h1
  ADC #NSLOT
@h1:
  CMP #REFRESH
  BCS @use
  LDA #$FF
  STA KHI,X
  JMP @pw
@use:
  LDA SLOTTOP,X
  STA KT
@emit:
  LDY #0
  LDA KT
  STA ($89),Y
  LDA $7A
  BMI @line
  INY
  LDA KT
  CLC
  ADC #1
  STA ($89),Y
  JMP @fin
@line:                    ; 이어쓰기 모드: 아래 타일은 버퍼 + 폭
  LDA KTWO
  BNE @lf
  LDX $78                 ; 첫 8x16 글자 → 아래 행 버퍼를 공백으로
  LDY $78
  LDA #$49
@fl:
  STA $032B,Y
  INY
  DEX
  BNE @fl
@lf:
  LDA $89
  CLC
  ADC $78
  TAX
  LDA KT
  CLC
  ADC #1
  STA $0300,X
@fin:
  LDA #1
  STA KTWO
@put1x:
  LDA #0
  STA $73
  CLC
  LDA $89
  ADC $7B
  STA $89
  LDA $8A
  ADC #0
  STA $8A
  RTS
@put1:
  LDY #0
  LDA KT
  STA ($89),Y
  JMP @put1x

; ---- NMI 앞부분: BG=$0000 복귀, 사본/글리프 업로드, 오버플로 스프라이트 OAM
eng_nmipre:
  LDA $01
  STA $2000
  LDA KACT
  CMP #3
  BEQ @act
  CMP #1
  BEQ @c0
  CMP #2
  BEQ @c1
  CMP #4
  BNE @idle
  LDA #$F4                ; 비활성화: 감지 스프라이트 숨김
  LDX #32
@hide:
  STA OVSLOT,X
  DEX
  DEX
  DEX
  DEX
  BPL @hide
  LDA #0
  STA KACT
@idle:
  RTS
@c0:
  LDA $2002
  LDA #$14
  STA $2006
  LDA #$00
  STA $2006
  LDY #0
  LDX #80
@u0:
  LDA COPYIMG,Y
  STA $2007
  INY
  DEX
  BNE @u0
  LDA #2
  STA KACT
  JMP @scr
@c1:
  LDA $2002
  LDA #$14
  STA $2006
  LDA #$50
  STA $2006
  LDY #80
  LDX #80
@u1:
  LDA COPYIMG,Y
  STA $2007
  INY
  DEX
  BNE @u1
  LDA #3
  STA KACT
  JMP @scr
@act:
  LDX #32                 ; 감지 스프라이트 9개: Y=KSPL, 타일 0x40(빈), 뒤
@ov:
  LDA KSPL
  STA OVSLOT,X
  LDA #OVTILE
  STA OVSLOT+1,X
  LDA #$20
  STA OVSLOT+2,X
  LDA #0
  STA OVSLOT+3,X
  DEX
  DEX
  DEX
  DEX
  BPL @ov
  LDA KPEND
  BEQ @done
  LDA $2002
  LDA KPT
  LSR A
  LSR A
  LSR A
  LSR A
  ORA #$10
  STA $2006
  LDA KPT
  ASL A
  ASL A
  ASL A
  ASL A
  STA $2006
  LDX #0
@g0:
  LDA KBUF,X
  STA $2007
  INX
  CPX #8
  BNE @g0
  LDA #0
  LDX #8
@z0:
  STA $2007
  DEX
  BNE @z0
  LDX #8
@g1:
  LDA KBUF,X
  STA $2007
  INX
  CPX #16
  BNE @g1
  LDA #0
  LDX #8
@z1:
  STA $2007
  DEX
  BNE @z1
  STA KPEND
@scr:
  LDA $2002
  LDA $03
  STA $2005
  LDA $04
  STA $2005
  LDA $01
  STA $2000
@done:
  RTS

; ---- NMI 끝: 스프라이트 오버플로 플래그를 기다렸다가 BG=$1000
eng_split:
  LDA KACT
  CMP #3
  BNE @out
  LDA KFAIL
  CMP #3
  BCS @out
  LDA $02
  AND #$18
  CMP #$18
  BNE @out
  LDX #0
@w1:                      ; 이전 프레임 플래그가 지워질 때(사전렌더)까지
  LDA $2002
  AND #$20
  BEQ @w2s
  DEX
  BNE @w1
  JMP @fail
@w2s:
  LDY #6
  LDX #0
@w2:
  LDA $2002
  AND #$20
  BNE @hit
  DEX
  BNE @w2
  DEY
  BNE @w2
@fail:
  INC KFAIL
  RTS
@hit:
  LDA $01
  ORA #$10
  STA $2000
  LDA #0
  STA KFAIL
@out:
  RTS

.include "../build/kor_tables.asm"

; ================================================================= 공유 코드 (뱅크 7,8,9,10 의 $BFB0-$BFF9)
.bank 15,17,19,21
.org $BFB0
.limit $BFF9
; ---- 글리프 n(KGLO/KGHI) 1bpp 16B → KBUF (메인 스레드, $10/$11 임시)
; 엔진 뱅크 7 과 폰트 뱅크 8-10 의 같은 주소($BFB0)에 복제: 뱅크를 바꿔도 다음 명령이 이어진다
kcopy:
  LDA $10
  PHA
  LDA $11
  PHA
  LDA $07
  PHA
  LDA KGLO
  STA $10
  LDA KGHI
  AND #3
  ASL $10
  ROL A
  ASL $10
  ROL A
  ASL $10
  ROL A
  ASL $10
  ROL A
  ORA #$80
  STA $11
  LDA KGHI
  LSR A
  LSR A
  CLC
  ADC #FONTBANK            ; 글리프 번호 g: 뱅크 8+(g>>10), 뱅크당 1019자(끝 5칸은 이 코드)
  JSR fastsw
  LDY #15
@c:
  LDA ($10),Y
  STA KBUF,Y
  DEY
  BPL @c
  PLA
  JSR fastsw
  PLA
  STA $11
  PLA
  STA $10
  RTS


