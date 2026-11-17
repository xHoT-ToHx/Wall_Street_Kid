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
KACT    = $06E0          ; 0 꺼짐 / 3 활성(분할) / 4 해제 요청(NMI 가 감지 스프라이트 숨김)
KFAIL   = $06E1          ; 연속 분할 실패 수
KNEXT   = $06E2          ; 다음 할당 슬롯(원형)
KTWO    = $06E5          ; 1 = 이번 플러시는 2행(8x16)
KGLO    = $06E6
KGHI    = $06E7
KC      = $06E8          ; 1바이트 코드 임시
KT      = $06E9          ; 현재 글자 윗타일
KSPL    = $06EA          ; 분할 스캔라인용 OAM Y (창 윗행*8-1)
KCH     = $06EB          ; 사본 업로드 조각(0-4, 32B 단위)
KTMP    = $06ED
KSPON   = $06EC          ; ≠0 = 이번 프레임 BG=$1000 로 분할함
KREC    = $05F0          ; [8] 사본 업로드용 큐 레코드 (원본 미참조 영역)
KBUF    = $05C0          ; [32] 글리프 2bpp (위 타일 16 + 아래 타일 16, plane0=0 / plane1=글리프 → 색 2)

; ---------------------------------------------------------------- 상수
NSLOT    = 107
REFRESH  = 40             ; asm/tools/kor_build.py 의 REFRESH 와 같게 (모의 검사)
ENGBANK  = 7
FONTBANK = 8              ; 글리프 n → 뱅크 8+(n>>10), $8000+(n&$3FF)*16
SPLITTOP = 16             ; 이 행 이상(y>=16)의 창만 한글 표시
OVSLOT   = $02DC          ; 오버플로 감지용 스프라이트 9개 = OAM 슬롯 55-63
OVTILE   = $40            ; $1000 타일 0x40 (빈 타일로 업로드)

BUS      = $FE90          ; 버스충돌 표 0..15 (원래 $F07E 0..6)
BANKID   = $BFF9          ; 각 뱅크 0-14 의 이 주소에 자기 뱅크 번호 (원본은 0 패딩)

; ================================================================= 고정뱅크 훅
.bank 31
.org $F076                ; 뱅크 전환 $F066 의 STA $F07E,X
.expect 9D 7E F0
  STA BUS,X
.org $F8ED                ; NMI 큐 작업의 뱅크 전환
.expect 9D 7E F0
  STA BUS,X
.org $F962                ; NMI 시작: OAM DMA 앞에서 분할 BG 복귀
.expect A5 06 F0 0A A9 00 8D 03 20 A9 02 8D 14 40
  JSR kdma
  JMP $F970
.org $F981                ; NMI: 큐 작업 직후(아직 VBlank), $09 프레임 훅·사운드 전
.expect A5 0A F0 09
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
  JMP ($FFDE)

; ---- NMI 훅 (엔진 뱅크 호출, $07 은 건드리지 않음)
; ---- NMI 시작: 지난 프레임에 BG=$1000 로 분할했으면 즉시 $0000 로 (긴 NMI 에서도 화면 위쪽 보호), 원래 OAM DMA
kdma:
  LDA KSPON
  BEQ @d
  LDA $01
  STA $2000
  LDA #0
  STA KSPON
@d:
  LDA $06
  BEQ @x
  LDA #0
  STA $2003
  LDA #2
  STA $4014
@x:
  RTS

nmi_post:
  LDA BANKID              ; 지금 $8000 에 걸린 뱅크(메인 스레드가 $07 없이 바꿨을 수 있음)
  PHA
  LDA #ENGBANK
  TAX
  STA BUS,X
  JSR eng_nmipre          ; 게임 큐 작업이 끝난 뒤(VBlank 안): BG 복귀·감지 스프라이트
  JSR eng_split
  PLA
  TAX
  STA BUS,X
  LDA $0A                 ; 원래: LDA $0A / BEQ $F98E ($09 훅 없으면 건너뜀)
  BNE @h
  PLA
  PLA
  JMP $F98E
@h:
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
  ; 사본(타일 0x40-0x49, 160B)을 게임 큐 작업으로 32B x5 업로드 (메인 스레드 PPU 쓰기와 충돌 없음)
  LDA #0
  STA KCH
@cpy:
  LDA #$02                ; 쓰기, +1
  STA KREC
  LDA #0
  STA KREC+1              ; 256B 페이지 수
  LDA #32
  STA KREC+2              ; 나머지 바이트
  LDA #ENGBANK
  STA KREC+3
  LDA KCH
  ASL A
  ASL A
  ASL A
  ASL A
  ASL A
  PHA
  CLC
  ADC #<COPYIMG
  STA KREC+4
  LDA #>COPYIMG
  ADC #0
  STA KREC+5
  PLA
  STA KREC+6
  LDA #$14
  STA KREC+7
  LDX #<KREC
  LDY #>KREC
  JSR $F302
  JSR $F03E
  INC KCH
  LDA KCH
  CMP #5
  BCC @cpy
  LDA #3
  STA KACT
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
  LDA #0                  ; KBUF 의 plane0(+0..7, +16..23) = 0 (원본 폰트처럼 plane1 만 사용 = 색 2)
  LDX #7
@z:
  STA KBUF,X
  STA KBUF+16,X
  DEX
  BPL @z
  JSR kcopy               ; plane0 채움 (폰트 뱅크)
  LDX KNEXT
  LDA KGLO
  STA KLO,X
  LDA KGHI
  STA KHI,X
  LDA SLOTTOP,X
  STA KT
  INX
  CPX #NSLOT
  BCC @nn
  LDX #0
@nn:
  STX KNEXT
  ; 글리프 32B 를 게임 큐 작업으로 업로드: [02][00][20][FF][KBUF][$1000+T*16]
  LDA #$02
  STA KREC
  LDA #0
  STA KREC+1
  LDA #32
  STA KREC+2
  LDA #$FF
  STA KREC+3
  LDA #<KBUF
  STA KREC+4
  LDA #>KBUF
  STA KREC+5
  LDA KT
  ASL A
  ASL A
  ASL A
  ASL A
  STA KREC+6
  LDA KT
  LSR A
  LSR A
  LSR A
  LSR A
  ORA #$10
  STA KREC+7
  LDX #<KREC
  LDY #>KREC
  JSR $F302
  JSR $F03E
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

; ---- NMI 뒷부분(작업·사운드 뒤, VBlank 안): BG=$0000 복귀, 오버플로 감지 스프라이트 OAM(다음 프레임 DMA 용)
eng_nmipre:
  LDA KACT
  CMP #3
  BEQ @act
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
@done:
  RTS

; ---- NMI 가 끊은 메인 스레드 위치 검사. C=1 = 직접 PPU 쓰기 루틴 안($CB79-$CBFF CHR 로더, $F086-$F0BE 스크롤)
; 스택: S+1,2 nmi_post 복귀 / S+3,4 $F9C0 / S+5 Y S+6 X S+7 A S+8 P / S+9 P S+10 PCL S+11 PCH (NMI)
;       NMI 가 $F03E 대기 루프($F03E-$F048)를 끊었으면 S+12 A, S+13/14 = 호출자 복귀 주소
ppubusy:
  TSX                     ; (이 루틴 JSR 로 2 더 깊음 → +2)
  LDA $010D,X
  LDY $010C,X
  CMP #$F0
  BNE @c
  CPY #$3E
  BCC @c
  CPY #$49
  BCS @c
  LDA $0110,X
  LDY $010F,X
@c:
  CMP #$CB
  BNE @c2
  CPY #$79
  BCS @busy
@c2:
  CMP #$F0
  BNE @free
  CPY #$86
  BCC @free
  CPY #$BF
  BCC @busy
@free:
  CLC
  RTS
@busy:
  SEC
  RTS

; ---- NMI 끝: 스프라이트 오버플로 플래그를 기다렸다가 BG=$1000
eng_split:
  LDA KACT
  CMP #3
  BNE @out
  LDA $02
  AND #$18
  CMP #$18
  BNE @out
  JSR ppubusy             ; 메인 스레드가 VBlank 직후 PPU 를 직접 쓰는 중이면 이번 프레임 분할 안 함
  BCS @out
  LDY #1                   ; 대기 한도 보정(아래)
  LDA $2002                ; 이전 프레임의 오버플로가 아직 켜져 있으면 사전렌더(261)에서 꺼지는 순간으로 동기
  AND #$20
  BEQ @out                 ; 이미 꺼짐: NMI 가 길어 사전렌더를 지났거나 지난 프레임 미발생 → 시점 불명, 이번 프레임은 분할 안 함
  LDX #0
@w1:                      ; 사전렌더 줄에서 플래그가 지워질 때까지 (최대 ~29줄)
  LDA $2002
  AND #$20
  BEQ @w2s
  DEX
  BNE @w1
  JMP @fail
@w2s:
  INY
@late:                    ; 최대 (KSPL/32 + 1 또는 2) x ~29줄 → 다음 NMI(241) 전에 반드시 끝남(중첩 NMI 방지)
  STY KTMP
  LDA KSPL
  LSR A
  LSR A
  LSR A
  LSR A
  LSR A
  CLC
  ADC KTMP
  TAY
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
  STA KSPON
  LDA #0
  STA KFAIL
@out:
  RTS

.include "../build/kor_tables.asm"

; ================================================================= 공유 코드 (뱅크 7,8,9,10 의 $BFA0-$BFF8)
.bank 15,17,19,21
.org $BFA0
.limit $BFF8
; ---- 글리프 n(KGLO/KGHI) 1bpp 16B → KBUF (메인 스레드, $10/$11 임시)
; 엔진 뱅크 7 과 폰트 뱅크 8-10 의 같은 주소($BFA0)에 복제: 뱅크를 바꿔도 다음 명령이 이어진다
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
  ADC #FONTBANK            ; 글리프 번호 g: 뱅크 8+(g>>10), 뱅크당 1018자(끝 6칸은 이 코드·뱅크표식)
  JSR fastsw
  LDY #15
@c1:                      ; 아래 타일 → KBUF+24..31 (plane1: 원본 폰트와 같은 색 2)
  LDA ($10),Y
  STA KBUF+16,Y
  DEY
  CPY #7
  BNE @c1
@c0:                      ; 위 타일 → KBUF+8..15 (plane1)
  LDA ($10),Y
  STA KBUF+8,Y
  DEY
  BPL @c0
  PLA
  JSR fastsw
  PLA
  STA $11
  PLA
  STA $10
  RTS

; ================================================================= 뱅크 번호 표식 ($BFF9)
.bank 1
.org $BFF9
.expect 00
  .db 0
.bank 3
.org $BFF9
.expect 00
  .db 1
.bank 5
.org $BFF9
.expect 00
  .db 2
.bank 7
.org $BFF9
.expect 00
  .db 3
.bank 9
.org $BFF9
.expect 00
  .db 4
.bank 11
.org $BFF9
.expect 00
  .db 5
.bank 13
.org $BFF9
.expect 00
  .db 6
.bank 15
.org $BFF9
  .db 7
.bank 17
.org $BFF9
  .db 8
.bank 19
.org $BFF9
  .db 9
.bank 21
.org $BFF9
  .db 10
.bank 23
.org $BFF9
  .db 11
.bank 25
.org $BFF9
.expect 00
  .db 12
.bank 27
.org $BFF9
.expect 00
  .db 13
.bank 29
.org $BFF9
  .db 14
