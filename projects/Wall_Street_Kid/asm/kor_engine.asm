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
KACT    = $06E0          ; 0 꺼짐 / 3 활성(분할) / 4 해제 요청(NMI 가 감지 스프라이트 숨김) / 5 해제+창 마지막 행 지우기
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
; ---- 8x8 UI 경로 (DESIGN §10). $0560-$05BF: 원본 정적 참조 없음(오탐만) [정적, 카나리 미확인]
UGLY    = $0560          ; [80] 풀 슬롯별 8x8 글리프 번호 ($FF = 비어 있음)
USTATE  = $05B0          ; 0 = 풀 없음(타이틀 등) / 1..19 = 장면 맵 t+1 의 CHR 이 BG $0000 에 있음
UNEXT   = $05B1          ; 다음 할당 슬롯(원형)
UCNT    = $05B2          ; 현재 풀 크기
UPLO    = $05B3          ; 현재 풀 표 주소
UPHI    = $05B4
UTMP    = $05B5
NTI     = $05B6          ; 이름표 변환 입력/출력 위치
NTO     = $05B7
KDCLR   = $05B8          ; [진단] 분할 건너뜀: NMI 가 사전렌더를 넘겨 오버플로 플래그가 이미 꺼짐 (DESIGN §12)
KDBUSY  = $05B9          ; [진단] 분할 건너뜀: 메인 스레드가 직접 PPU 쓰기 루틴 안(ppubusy)
KINVF   = $05BB          ; ≠0 = 8x8 캐시 무효화 예약($CD70 화면 지우기)
KTHI    = $05BA          ; 분할 행의 네임테이블 상위 바이트($20+행/8) — hkpre 가 분할 해제 판정
KMAG    = $05BC          ; [2] = $A5,$5A 이면 엔진 RAM 초기화됨. kinit(리셋·전원)이 깨고 첫 NMI 의 eng_nmipre 가 eng_init (fix3)
KPGF    = $05BE          ; ≠0 = <PAGE>(kpage) 뒤 8x16 슬롯 캐시 초기화 예약 (glyph_emit 이 처리, fix3: kreset 을 엔진 뱅크로)
KRDY    = $05BF          ; ≠0 = 감지 스프라이트가 이번 프레임 PPU OAM 에 있음(지난 NMI 가 써 두었고 이번 DMA 로 올라감) (fix3)
KINW    = $06EE          ; ≠0 = 분할 대기 중 (대기가 241 을 넘겨 들어온 중첩 NMI 는 eng_nmipre 가 바로 버림) (fix3)
KSND    = $06EF          ; ≠0 = NMI 사운드($DE67) 처리 중 (중첩 NMI 는 사운드 건너뜀) (fix3)
; ---- 종목 화면 상단 8x16 (DESIGN §19). 캐시 54칸 = T16CA[44](UGLY 뒤쪽, 맵0 8x8 풀은 UGLY[0..35]) + T16CB[10]
T16CA   = $0584          ; = UGLY+36, 캐시 0..43 (글자 번호 ii, $FF = 빈칸). uinval 이 UGLY 와 함께 비움
T16CB   = $05E0          ; 캐시 44..53 ($05E0-$05E9, 원본 정적 참조 없음)
T16NEXT = $06DB          ; 다음 할당 칸(원형)
T16I    = $06DC          ; 현재 글자 번호 ii
KLAY    = $06DD          ; 1 = 창 6 이 상단 8x16 배치([5F FF]) → $B37C 금액도 8x16·한 행 위로 / 0 = 8x8([5F FD], 수량 화면)
PFI     = $06DE          ; eng_pfnum 글자 위치

; ---------------------------------------------------------------- 상수
NSLOT    = 107
REFRESH  = 40             ; asm/tools/kor_build.py 의 REFRESH 와 같게 (모의 검사)
ENGBANK  = 7
FONTBANK = 8              ; 글리프 n → 뱅크 8+(n>>10), $8000+(n&$3FF)*16
SPLITTOP = 16             ; 이 행 이상(y>=16)의 창만 한글 표시
OVSLOT   = $02DC          ; 오버플로 감지용 스프라이트 9개 = OAM 슬롯 55-63
OVTILE   = $40            ; $1000 타일 0x40 (빈 타일로 업로드)
LABTILE  = $4A            ; 상태창 라벨 고정 타일 0x4A-0x4D (kor_build.py LABEL_TILE0)
NPOOLMAX = 80
T16N     = 54             ; 상단 8x16 캐시 칸 = 타일 쌍 수 (kor_build.py 가 T16TILE 54개 생성)
T16NA    = 44             ; 그중 T16CA 칸 수
T16BASE  = $37            ; [5F ii] 의 ii 시작 (kor_build.py T16_BASE). ii < $37 = 원본 1바이트 문자

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
.org $F98E                ; NMI: 사운드 $DE67 호출 → 재진입 방지 (fix3, DESIGN §18)
.expect 20 67 DE
  JSR ksnd

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
.bank 30
.org $C003                ; 고정뱅크 머리 JMP $C010 뒤 0 패딩(리셋 벡터 $C000 → $C010 으로 건너뜀, 미실행)
.limit $C00F
.expect 00 00 00 00 00 00 00 00 00 00 00 00 00
; ---- 리셋 초기화 ($F03B JMP ($FFDE) 대체)
;      전원 투입 시 RAM 은 무작위다(리셋은 보존). 여기서는 표식(KMAG)만 깨고, 첫 NMI 의 eng_nmipre 가
;      엔진 RAM 전부를 eng_init 로 초기화한다(고정 뱅크 여유가 없어 초기화 본체는 엔진 뱅크) (fix3)
kinit:
  LDA #0
  STA KMAG
  JMP ($FFDE)
.bank 30
.org $D242                ; 창 표 $D22F: 창 4 [x8 y24 w22 h4] 의 h — 데모 카드 지우기($85C6 → $D198)
.expect 04
  .db 5                   ; 8x16 설명 줄의 아래 타일 행(28)까지 지운다 (fix3: 다음 카드에 이전 설명 아래 반쪽이 남던 문제)
.org $D246                ; 창 5 [x8 y22 w22 h6] 의 h (엔딩 카드)
.expect 06
  .db 7
.org $D248                ; 창 6 [x2 y2 w28 h4] 의 y — 종목 화면 상단 창 지우기(bank5 $B33E/$B1AA 만 사용) (§19)
.expect 02
  .db 1                   ; 행 1-4 (8x16 안내 2줄). 열 제목(행 5-6)은 남김 → 수량 화면에서도 보임
.org $D250                ; 창 8 [x1 y2 w30 h5] — 정보 화면 진입 지우기(bank5 $ADF6 만 사용) → [x1 y1 w30 h6] (행 1 = 목록 안내 위 타일)
.expect 02 1E 05
  .db 1,$1E,6

; ---- bank5 종목 화면 창 모드 $80 → $85 (bit2 = 상단 8x16, bit0 = 2행 피치) (§19)
.bank 11
.org $AE28                ; 정보 화면 종목명 x3 y3 → 행 3-4
.expect 80
  .db $85
.org $AE4D                ; 정보 화면 틀 x2 y8 → 행 8-19 (주가/열 머리/종목 분류/기업 개요)
.expect 80
  .db $85
.org $AF07                ; 정보 화면 값 줄($038F) x2 y12 → 행 12-13
.expect 80
  .db $85
.org $AF37                ; 정보 화면 분류명 x3 y16 → 행 16-17
.expect 80
  .db $85
.org $B3C7                ; $B37C 금액 2줄 PPU 레코드 제출(LDX #$2B / LDY #$03 / JSR $C0EB) → 보유 주식 화면이면 8x16 으로
.expect A2 2B A0 03 20 EB C0
  JSR stub5
  NOP
  NOP
  NOP
  NOP
; ---- bank5·bank7 같은 주소 공유 스텁 (stock_desc_b5 영역 끝 32B, kor_build.py STUB5_RESERVE): 뱅크를 바꿔도 다음 명령이 이어진다
.bank 11,15
.org $BC26
.limit $BC45
stub5:
  LDA $07
  PHA
  LDA #ENGBANK
  JSR fastsw              ; → 뱅크 7 의 같은 주소에서 계속
  JSR eng_pfnum
  PLA
  JSR fastsw              ; → 뱅크 5
  LDX #$2B
  LDY #$03
  JMP $C0EB
.bank 30
.org $CBEB                ; CHR 로더($CB33, 1bpp/2bpp 직접 쓰기) 끝: JMP $CE03 (PLA / 뱅크 복원 / RTS)
.expect 4C 03 CE
  JMP ulab
.org $CCAA                ; CHR 로더($CBF2, 큐 $F20F) 끝
.expect 4C 03 CE
  JMP ulab
.bank 31
.org $F210                ; $F20F: JSR $F489 → 분할 해제 판정 후 같은 곳으로
.expect 20 89 F4
  JSR kq
.bank 30
.org $CD73                ; $CD70 화면 지우기: STA $40 / TYA → kcls
.expect 85 40 98
  JSR kcls
.org $C463                ; 날짜 상자 요일 복사 루프(LDY #1 .. BNE) → kwdbox
.expect A0 01 BD 07 C4 99 2B 03 E8 C8 C6 91 D0 F4
  JSR kwdbox
  JMP $C471
.org $DC82                ; 이름표($DC67): 문자열 → $032E 복사 루프 (LDY #0 .. BNE) 
.expect A0 00 B1 8F C9 FF F0 06 99 2E 03 C8 D0 F4
  JSR ntag
  JMP $DC90
.org $DDB9                ; 이름표 2($DD9E): 같은 루프
.expect A0 00 B1 8F C9 FF F0 06 99 2E 03 C8 D0 F4
  JSR ntag
  JMP $DDC7

; ================================================================= 고정뱅크 본체 ($FE90-$FFBF)
; ================================================================= 고정뱅크 본체 2 ($E0F2-$E121: menu_b7 영역 끝 96B, kor_build.py MENU_CODE_RESERVE)
.bank 31
.org $E0C2
.limit $E120              ; $E121 은 원본 코드(LDX $AF, 점프표 $C13F 의 대상) — 포함하면 안 됨 (fix3 에서 확인)
; ---- 1바이트 문자 원래 경로. 4E = NOP(그리지 않고 전진 0: 고정 길이 요일 채움)
korig:
  LDA KC
  CMP #$4E
  BEQ @nop
  CMP #$FB                ; 원래 $D90F 와 같은 플래그(N)로 $D918 진입
  JMP $D918
@nop:
  LDA #0
  STA $7B
  STA $73
  RTS

; ---- NMI(nmi_post 첫머리, 큐 작업 직후 VBlank 안): $09 훅이 $D2A3($D27F 의 PPU 레코드 목록 직접 기록)이면 지금 실행하고
;      $0A=0($F051) 으로 원래 자리(분할 대기 뒤 = 화면 중간)에서 다시 돌지 않게 한다. 레코드 목록이 전환 뱅크($8000-)에
;      있을 수 있으므로(타이틀 bank5 $847A 등) 엔진 뱅크로 바꾸기 전에 호출해야 한다. $0A 상위 $D2 인 훅은 $D2A3 뿐.
;      첫 레코드의 기록 행이 분할 구간(KTHI = $20+분할행/8 이상의 네임테이블 상위 바이트)이면 그 창이 다른 그림으로
;      덮이는 것이므로(타이틀 데모 카드 → 메뉴·저작권) 분할을 끈다(KACT=4). 상태창·이름표(행 2-12)는 유지.
; ---- $F20F(원시 바이트 큐 기록) 첫머리: 분할 중 분할 행 이하 네임테이블($2000-$23FF)에 쓰면 창이 다른 그림으로
;      바뀌는 것(타이틀 데모 카드 → 메뉴·저작권 $C055)이므로 분할을 끈다. A/X/Y 보존.
kq:
  PHA
  LDA KACT
  CMP #3
  BNE @p
  CPY KTHI
  BCC @p
  CPY #$24
  BCS @p
  LDA #5                  ; 5 = 해제 + 마지막 행 지우기(eng_nmipre)
  STA KACT
@p:
  PLA
  JMP $F489

; ---- 날짜 상자($C41C): 요일 3B 원시 복사($C463-$C470) 대체. X = 요일*3. 엔진 뱅크에서 8x8 풀 타일로 바꿔 $032C-$032E 에
kwdbox:
  STX KTMP
  LDA $07
  PHA
  LDA #ENGBANK
  JSR fastsw
  JSR eng_wdbox
  PLA
  JMP fastsw

hkpre:
  LDA $0A
  CMP #$D2
  BNE @r
  LDY #1
  LDA ($40),Y
  CMP KTHI
  BCC @h
  LDA #4
  STA KACT
@h:
  JSR $D2A3
  JSR $F051
@r:
  RTS

.bank 31
.org $FE90
.limit $FFDD              ; $FFDE = 리셋 연속 벡터(JMP ($FFDE))
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
  CMP #$61                ; 50-5F = 8x16 글리프, 60 = 8x8 UI 글리프(KGHI=$10 으로 구분)
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
@one:                     ; 1바이트 문자는 모두 eng_one 이 판정(분할 창 8x16 / 상단 8x16 창 / 그 밖 C=1 원래 경로) (§19: 고정 8B 절약)
  STA KC
  LDA $07
  PHA
  LDA #ENGBANK
  JSR fastsw
  JSR eng_one
  PLA
  JSR fastsw
  BCC @ret
@orig:
  JMP korig
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

; ---- <PAGE> 창 지우기 전 슬롯 캐시 초기화 → 예약만(다음 글리프에서 glyph_emit 가 kreset). 본체는 엔진 뱅크 (fix3: 고정 공간)
kpage:
  DEC KPGF
  JMP $DA62

; ---- $CD70(네임테이블 전체 지우기) 첫머리: 화면이 통째로 바뀌므로 8x8 풀 캐시 무효화 예약(u8tile 이 처리)
kcls:
  STA $40
  DEC KINVF
  TYA
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


; ---- CHR 로더 끝($CBEB/$CCAA 의 JMP $CE03 대체): 엔진 뱅크에서 8x8 풀 상태 갱신·라벨 타일 업로드
ulab:
  LDA $07
  PHA
  LDA #ENGBANK
  JSR fastsw
  JSR eng_chr
  PLA
  JSR fastsw
  JMP $CE03

; ---- 이름표 복사 루프 대체 ($DC82/$DDB9): 반환 A=$FF, Y=길이 (원래 루프 종료 상태)
ntag:
  LDA $07
  PHA
  LDA #ENGBANK
  JSR fastsw
  JSR eng_ntag
  PLA
  JSR fastsw
  LDA #$FF
  RTS

; ---- NMI 훅 (엔진 뱅크 호출, $07 은 건드리지 않음)
; ---- NMI 시작: 지난 프레임에 BG=$1000 로 분할했으면 즉시 $0000 로 (긴 NMI 에서도 화면 위쪽 보호), 원래 OAM DMA
kdma:
  LDA $01                 ; (X 는 NMI 진입부에서 이미 저장됨)
  LDX KSPON
  BEQ @d
  STA $2000
@d:
  LDA #0
  STA KSPON
  LDX $06
  BEQ @x
  STA $2003
  LDA #2
  STA $4014
@x:
  RTS

nmi_post:
  JSR hkpre               ; PPU 직접 쓰기 훅($D2A3)은 분할 대기 전에, 메인 스레드 뱅크 그대로 (DESIGN §14)
  LDA BANKID              ; 지금 $8000 에 걸린 뱅크(메인 스레드가 $07 없이 바꿨을 수 있음)
  PHA
  LDA #ENGBANK
  TAX
  STA BUS,X
  JSR eng_nmipre          ; 게임 큐 작업이 끝난 뒤(VBlank 안): BG 복귀·감지 스프라이트
  JSR eng_splitw          ; 분할 대기 (KINW 로 감쌈)
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

; ---- NMI 의 사운드($F98E JSR $DE67 대체): 사운드 엔진 재진입 방지 (fix3, DESIGN §18)
;      분할 대기가 NMI 안에서 분할 줄(타이틀 카드 = 199줄)까지 이어지므로 그 뒤의 $09 훅·사운드가 241 을 넘기면 다음 NMI 가
;      사운드 처리 중간에 끼어든다(원래 게임은 $09 훅 $E121 이 NMI 안에서 $F03E 로 다음 NMI 를 일부러 기다림 = 중첩 NMI 전제).
;      안쪽 NMI 가 사운드를 끝까지 돌리면 바깥 사운드의 채널 루프 변수 $0521 이 3 이 되어 $0543,X 배열을 한 칸 밀어 쓰고
;      $0546 → 점프표 $9CC3 범위 밖 → $025D(RAM) 실행 → 화면이 $1000 타일로 바뀐 채 정지 [검증: 트레이스·쓰기 BP].
;      → 사운드 중이면 안쪽 NMI 는 이번 사운드 틱을 건너뛴다.
ksnd:
  LDA KSND
  BNE @s
  INC KSND
  JSR $DE67
  DEC KSND
@s:
  RTS

; ================================================================= 엔진 뱅크 7 ($8000-$BFFF)
.bank 14
.org $8000
.limit $9FFF
  JMP $C010               ; 다른 뱅크와 같은 머리(안전용)

; ---- 2바이트 한글 (KGLO/KGHI = 글리프 번호, KGHI=$10 이면 8x8 UI 글리프 KGLO)
eng_kor:
  LDA KGHI
  CMP #$10
  BEQ eng_ui8
  CMP #$0F                ; [5F ii] = 상단 8x16 글자/표식 (§19)
  BNE @g
  JMP eng_t16
@g:
  JMP glyph_emit

; ---- 8x8 UI 글리프 (DESIGN §10)
; 분할 아래(행>=16)·2행 피치 창이면 같은 글자의 8x16 글리프로(대사창 <VAR> 의 요일 등).
; 그 밖에는 BG $0000 의 현재 장면 빈 타일 풀에 동적 배치(캐시 적중이면 재사용).
eng_ui8:
  LDA $75
  CMP #SPLITTOP
  BCC @u8
  LDA $7A
  AND #1
  BEQ @u8
  LDX KGLO
  LDA UI8G_HI,X
  CMP #$FF
  BEQ @u8
  STA KGHI
  LDA UI8G_LO,X
  STA KGLO
  JMP glyph_emit
@u8:
  JSR u8tile
@put:
  LDY #0
  LDA KT
  STA ($89),Y
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

; KGLO(8x8 글리프) → KT(BG $0000 타일). 풀 없음이면 KT=$49(공백). 미스면 원형 할당 후 업로드(NMI 1회)
u8tile:
  LDA KINVF               ; 화면 지우기 뒤 첫 글자: 캐시 비움(보이던 글자가 없으므로 처음부터 할당)
  BEQ @v
  JSR uinval
  LDA #0
  STA KINVF
@v:
  LDA #$49
  STA KT
  LDA USTATE
  BEQ @r
  LDX UCNT
  BEQ @r
  DEX
@find:
  LDA UGLY,X
  CMP KGLO
  BEQ @hit
  DEX
  BPL @find
  LDX UNEXT
  LDA KGLO
  STA UGLY,X
  TXA
  TAY
  INX
  CPX UCNT
  BCC @nn
  LDX #0
@nn:
  STX UNEXT
  JSR upool
  STA KT
  JMP u8up
@hit:
  TXA
  TAY
  JSR upool
  STA KT
@r:
  RTS

; ---- 이름표($DC67/$DD9E): 문자열을 PPU 레코드 버퍼 $032E 로 그대로 복사하던 루프 대체.
;      [60 ii] 는 풀 타일 번호로 바꿔 쓴다. 반환 Y = 출력 길이 (원래 루프와 같음)
eng_ntag:
  LDA #0
  STA NTI
  STA NTO
@l:
  LDY NTI
  LDA ($8F),Y
  CMP #$FF
  BEQ @end
  INY
  CMP #$60
  BNE @raw
  LDA ($8F),Y
  INY
  STY NTI
  STA KGLO
  JSR u8tile
  LDA KT
  JMP @out
@raw:
  STY NTI
@out:
  LDY NTO
  STA $032E,Y
  INC NTO
  JMP @l
@end:
  LDY NTO
  RTS

; ---- 날짜 상자 요일: 표 $C407 의 [60 ii 4E] 에서 ii → 풀 타일, 오른쪽 맞춤(" 　월,4/03")
eng_wdbox:
  LDX KTMP
  LDA $C408,X
  STA KGLO
  JSR u8tile
  LDA #$49
  STA $032C
  STA $032D
  LDA KT
  STA $032E
  RTS

; Y = 슬롯 → A = 타일 번호 (현재 풀 표)
upool:
  LDA $10
  PHA
  LDA $11
  PHA
  LDA UPLO
  STA $10
  LDA UPHI
  STA $11
  LDA ($10),Y
  STA UTMP
  PLA
  STA $11
  PLA
  STA $10
  LDA UTMP
  RTS

; KGLO 의 8x8 글리프(1bpp 8B) → KBUF 2bpp(plane0=0, plane1=글리프) → 타일 KT 로 큐 업로드
u8up:
  LDA $10
  PHA
  LDA $11
  PHA
  LDA KGLO
  STA $10
  LDA #0
  ASL $10
  ROL A
  ASL $10
  ROL A
  ASL $10
  ROL A
  STA $11
  CLC
  LDA $10
  ADC #<UI8FONT
  STA $10
  LDA $11
  ADC #>UI8FONT
  STA $11
  LDY #7
@c:
  LDA ($10),Y
  STA KBUF+8,Y
  LDA #0
  STA KBUF,Y
  DEY
  BPL @c
  PLA
  STA $11
  PLA
  STA $10
  LDA #$02                ; [02][00][10][FF][KBUF][$0000+KT*16]
  STA KREC
  LDA #0
  STA KREC+1
  LDA #16
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
  STA KREC+7
  LDX #<KREC
  LDY #>KREC
  JSR $F302
  JMP $F03E

; ---- CHR 로더 끝 ($40 = 로드 항목 번호, 표 bank0-3 $8010). 장면 그림(항목 8-$19 = 맵 0-$11, $29 = 큰 맵)이면
;      풀을 그 맵의 빈 타일로 바꾸고 캐시를 비운 뒤 라벨 4타일을 올린다. 타이틀/전면 그림(1,2,$2A-$2C)이면 풀 없음.
eng_chr:
  LDA $40
  SEC
  SBC #8
  CMP #$12
  BCC @map
  LDA $40
  CMP #$29
  BNE @other
  LDA #$12
@map:
  TAX
  INX
  STX USTATE
  DEX
  LDA POOLCNT,X
  STA UCNT
  LDA POOLLO,X
  STA UPLO
  LDA POOLHI,X
  STA UPHI
  JSR uinval
  LDA USTATE
  CMP #$13                ; 큰 맵(장면 $13): 0x4C- 를 얼굴 애니메이션이 씀 → 라벨 안 올림(QA V2)
  BEQ @rts
  LDA #$02                ; 라벨 2bpp 64B → $04A0 (타일 0x4A-0x4D)
  STA KREC
  LDA #0
  STA KREC+1
  LDA #64
  STA KREC+2
  LDA #ENGBANK
  STA KREC+3
  LDA #<LABIMG
  STA KREC+4
  LDA #>LABIMG
  STA KREC+5
  LDA #$A0                ; <(LABTILE*16)
  STA KREC+6
  LDA #$04                ; >(LABTILE*16)
  STA KREC+7
  LDX #<KREC
  LDY #>KREC
  JSR $F302
  JMP $F03E
@other:
  CMP #1                  ; 항목 1 = 타일 0x24-0x40(패스워드 기호), 2 = 0x00-0x2B(엔딩 로고)만 올림 [검증: 로더 표 bank0 $8010].
  BEQ @free               ;  둘 다 화면을 통째로 지운 패스워드 표시 화면 앞에서 쓰이므로 0x50-0x9F 를 풀로 (fix3:
  CMP #2                  ;  예전엔 '풀 없음'으로 둬 "당신의 패스워드" 가 공백으로 나옴). 일반 장면은 뒤이어 맵 항목이 덮어씀
  BEQ @free
  CMP #$2A
  BCC @rts
  CMP #$2D
  BCS @rts
@none:
  LDA #0
  STA USTATE
  STA UCNT
  JMP uinval
@free:
  LDA #$14                ; 1..$13 = 맵 풀, $14 = 지운 화면용 고정 풀
  STA USTATE
  LDA #NPOOLMAX
  STA UCNT
  LDA #<POOLFREE
  STA UPLO
  LDA #>POOLFREE
  STA UPHI
  JMP uinval
@rts:
  RTS
uinval:                   ; 8x8 풀 캐시 + 상단 8x16 캐시(T16CA 는 UGLY 뒤쪽, T16CB) 비움
  LDA #$FF
  LDX #NPOOLMAX-1
@i:
  STA UGLY,X
  DEX
  BPL @i
  LDX #T16N-T16NA-1
@j:
  STA T16CB,X
  DEX
  BPL @j
  LDA #0
  STA UNEXT
  STA T16NEXT
  RTS

; 상단 8x16 캐시만 비움(8x8 풀은 화면에 남아 있을 수 있어 건드리지 않음)
t16inval:
  LDA #$FF
  LDX #T16NA-1
@a:
  STA T16CA,X
  DEX
  BPL @a
  LDX #T16N-T16NA-1
@b:
  STA T16CB,X
  DEX
  BPL @b
  LDA #0
  STA T16NEXT
  RTS

; ================================================================= 종목 화면 상단 8x16 (DESIGN §19)
; 목록·보유 주식·정보 화면은 그림이 없고 BG $0000 에 홈 그림(맵0, CHR 항목 8)이 남아 있다. 맵0 이 참조하는 인접 타일 쌍
; 54개(T16TILE, 8x8 풀과 겹치지 않음)에 8x16 글리프를 올린다. 화면을 떠나 홈으로 가면 CHR 항목 8 이 다시 로드된다[검증].
; C=0 = 지금 창이 상단 8x16 창(모드 & 6 = 4)이고 홈 CHR(USTATE=1) 이 있음
t16ok:
  LDA $7A
  AND #$06
  CMP #$04
  BNE @no
  LDA USTATE
  CMP #1
  BNE @no
  CLC
  RTS
@no:
  SEC
  RTS

; X = 글자 번호 ii → KGLO/KGHI (8x16 글리프). ii < $37 = 원본 1바이트 문자(ASC 표)
t16g:
  CPX #T16BASE
  BCS @k
  LDA ASC_LO,X
  STA KGLO
  LDA ASC_HI,X
  STA KGHI
  RTS
@k:
  LDA T16LO-T16BASE,X
  STA KGLO
  LDA T16HI-T16BASE,X
  STA KGHI
  RTS

; X = 글자 번호 ii → KT = 위 타일(아래 = KT+1). 캐시 미스면 원형 할당 후 32B 를 큐로 업로드(NMI 1회)
t16tile:
  STX T16I
  LDA KINVF               ; 화면 지우기($CD70) 뒤 첫 글자: 캐시 비움
  BEQ @v
  JSR uinval
  LDA #0
  STA KINVF
@v:
  LDX #T16N-1
@f:
  CPX #T16NA
  BCS @f2
  LDA T16CA,X
  JMP @c
@f2:
  LDA T16CB-T16NA,X
@c:
  CMP T16I
  BEQ @hit
  DEX
  BPL @f
  LDX T16NEXT             ; 미스
  LDA T16I
  CPX #T16NA
  BCS @s2
  STA T16CA,X
  JMP @s3
@s2:
  STA T16CB-T16NA,X
@s3:
  LDA T16TILE,X
  STA KT
  INX
  CPX #T16N
  BCC @nn
  LDX #0
@nn:
  STX T16NEXT
  LDX T16I
  JSR t16g
  LDA #0
  LDX #7
@z:
  STA KBUF,X
  STA KBUF+16,X
  DEX
  BPL @z
  JSR kcopy
  LDA #$02                ; [02][00][20][FF][KBUF][$0000+KT*16] (타일 KT, KT+1)
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
  STA KREC+7
  LDX #<KREC
  LDY #>KREC
  JSR $F302
  JMP $F03E
@hit:
  LDA T16TILE,X
  STA KT
  RTS

; [5F ii]: ii = 글자 → 상단 8x16 (창이 아니거나 홈 CHR 이 아니면 8x8 대체 T16U8, 없으면 공백)
;          FF = 창 6 을 상단 8x16 배치로(2행 피치 + 상단 8x16 모드, 한 행 위로, KLAY=1) / FD = KLAY=0. 표식은 그리지 않고 전진 0
eng_t16:
  LDX KGLO
  CPX #$FC
  BEQ @fc
  CPX #$FD
  BEQ @fd
  CPX #$FF
  BEQ @ff
  JSR t16ok
  BCS @fb
  JSR t16tile
  JMP glyph_emit@emit
@fb:
  LDA T16U8-T16BASE,X
  CMP #$FF
  BEQ @sp
  STA KGLO
  JMP eng_ui8@u8
@sp:
  LDA #$49
  STA KT
  JMP glyph_emit@put1
@fc:                      ; 정보 화면 첫 글자 앞: 앞 화면의 8x16 캐시를 비움(v0.2.6)
  JSR t16inval
  JMP @nop
@ff:
  JSR t16inval            ; 목록·보유 주식 화면 시작
  LDA #1
  STA KLAY
  LDA $7A
  ORA #$05
  STA $7A
  DEC $75
  DEC $77
  JMP @nop
@fd:
  LDA #0
  STA KLAY
@nop:
  LDA #0
  STA $7B
  STA $73
  RTS

; ---- 보유 주식 화면 금액(bank5 $B37C): PPU 레코드 $032B = [lo][hi][len][타일 x len][FF] 를 제출 직전에 바꾼다 (stub5 에서 호출)
;      KLAY=1(보유 주식 [5F FF]) 이면 행을 짝수→한 행 위(행 2→1, 3 은 그대로 = 현금/주식 8x16 줄과 맞춤),
;      홈 CHR 이면 숫자·$·, 를 8x16 위 타일로 바꾸고 아래 타일 레코드를 이어 붙인다(최대 len 12 → $0349 까지).
eng_pfnum:
  LDA KLAY
  BEQ @r
  LDA $032B
  AND #$20
  BNE @odd
  LDA $032B
  SEC
  SBC #$20
  STA $032B
  BCS @odd
  DEC $032C
@odd:
  LDA USTATE
  CMP #1
  BNE @r
  CLC
  LDA $032B
  ADC #$20
  STA $033A
  LDA $032C
  ADC #0
  STA $033B
  LDA $032D
  STA $033C
  LDA #0
  STA PFI
@l:
  LDX PFI
  LDA #$49
  STA $033D,X
  LDA $032E,X
  CMP #$49
  BEQ @n
  AND #$7F
  CMP #$37
  BCS @n
  TAX
  LDA ASC_HI,X
  CMP #$FF
  BEQ @n
  JSR t16tile
  LDX PFI
  LDA KT
  STA $032E,X
  CLC
  ADC #1
  STA $033D,X
@n:
  INC PFI
  LDA PFI
  CMP $032D
  BCC @l
  TAX
  LDA #$FF                ; 목록 끝 = 다음 레코드의 hi 자리($D2A3 이 [lo][hi] 의 hi=FF 로 판정) → $033D+len+1
  STA $033D,X
  STA $033E,X
@r:
  RTS

; ---- 1바이트 원본 문자: 활성·2행 피치·분할 아래면 8x16 ASCII 글리프로. C=0 처리함 / C=1 원래 경로
eng_one:
  JSR t16ok               ; 상단 8x16 창(모드 bit2, 홈 CHR): ASCII 8x16 을 BG $0000 타일 쌍에 (§19)
  BCS @spl
  LDA KC
  AND #$7F
  CMP #$37
  BCS @no
  TAX
  LDA ASC_HI,X
  CMP #$FF
  BEQ @no
  LDA KC
  BPL @t1
  INC $7B                 ; 80|c = 문자+공백
@t1:
  JSR t16tile
  JSR glyph_emit@emit
  CLC
  RTS
@spl:
  LDA KACT                ; (khook 이 이제 모든 1바이트 문자를 넘김) 분할 활성일 때만
  CMP #3
  BNE @no
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
  LDA KPGF                ; <PAGE> 뒤 첫 글리프: 슬롯 캐시 초기화 (kpage 가 예약)
  BEQ @np
  JSR kreset
@np:
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
  LDA $77
  LSR A
  LSR A
  LSR A
  ORA #$20
  STA KTHI
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

; ---- 8x16 슬롯 캐시 초기화 (활성화·<PAGE>). 고정 뱅크에서 옮김 (fix3)
kreset:
  LDA #$FF
  LDX #NSLOT-1
@l:
  STA KHI,X
  DEX
  BPL @l
  LDA #0
  STA KNEXT
  STA KPGF
  RTS

; ---- NMI(큐 작업 직후, VBlank 안): BG=$0000 복귀, 오버플로 감지 스프라이트 OAM(다음 프레임 DMA 용)
eng_nmipre:
  LDA KMAG                ; 리셋·전원 투입 뒤 첫 NMI: 엔진 RAM 전부 초기화 (kinit 가 KMAG 를 깸)
  CMP #$A5
  BNE @init
  LDA KMAG+1
  CMP #$5A
  BEQ @ok
@init:
  JMP eng_init
@ok:
  LDA KINW                ; 분할 대기(엔진 뱅크) 중에 다음 VBlank 의 NMI 가 들어옴(NMI 작업이 길어 대기가 241 을 넘김):
  BEQ @nn                 ; 이 NMI 를 끝까지 돌리면 사운드($DE67)가 $07 뱅크로 바꿔 놓고 RTI 해 대기 루프가 엉뚱한 뱅크에서
  PLA                     ; 이어지므로(정지) 여기서 버린다. 스택: eng_nmipre 복귀 2 / 뱅크 1 / nmi_post 복귀 2 / Y X A P → RTI
  PLA                     ; (이 NMI 앞부분 kdma·큐·hkpre 는 이미 돎: 큐·$0A 는 바깥 NMI 가 비웠고 메인 스레드는 멈춰 있어 새 작업 없음)
  PLA
  PLA
  PLA
  PLA
  TAY
  PLA
  TAX
  PLA
  PLP
  RTI
@nn:
  LDA KACT
  CMP #3
  BEQ @act
  CMP #5
  BNE @n5
  JSR wclr                ; kq 가 창 교체로 분할을 끈 경우: 마지막 줄 아래 타일 행 지우기
  JMP @off
@n5:
  CMP #4
  BNE @idle
@off:
  LDA #0
  STA KRDY
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
  LDX #0                  ; 지난 NMI 가 써 둔 감지 스프라이트가 그대로면 이번 NMI 첫머리 DMA 로 PPU 에 올라갔음 → 이번 프레임 분할 가능
  LDA OVSLOT+32
  CMP KSPL
  BNE @rdy
  LDA OVSLOT+33
  CMP #OVTILE
  BNE @rdy
  INX
@rdy:
  STX KRDY
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

; ---- (NMI, VBlank) 직전 텍스트 창의 마지막 행(y+h-1, 8x16 마지막 줄의 아래 타일)을 공백으로. 창 지우기($D198)는
;      창 높이(1행 피치 기준)만 지워 이 행이 남는다(타이틀 데모 카드 → 메뉴 전환 때 28행 잔상). 끝에서 스크롤 복원.
wclr:
  LDA $2002
  LDA $77
  CLC
  ADC $79
  SEC
  SBC #1
  STA KTMP                ; 행
  LSR A
  LSR A
  LSR A
  ORA #$20
  STA $2006
  LDA KTMP
  ASL A
  ASL A
  ASL A
  ASL A
  ASL A
  CLC
  ADC $76
  STA $2006
  LDX $78
  BEQ @e
  LDA #$49
@l:
  STA $2007
  DEX
  BNE @l
@e:
  LDA #$FF
  JMP $F086

; ---- NMI 가 끊은 메인 스레드 위치 검사. C=1 = 직접 PPU 쓰기 루틴 안($CB79-$CBFF CHR 로더, $F086-$F0BE 스크롤)
; 스택: S+1,2 nmi_post 복귀 / S+3,4 $F9C0 / S+5 Y S+6 X S+7 A S+8 P / S+9 P S+10 PCL S+11 PCH (NMI)
;       NMI 가 $F03E 대기 루프($F03E-$F048)를 끊었으면 S+12 A, S+13/14 = 호출자 복귀 주소
; [fix3 메모, 미수정] 지금 경로(nmi_post 의 뱅크 PHA, eng_splitw)에서는 위 오프셋이 맞지 않아 PCL/P 근처를 읽는다 → 사실상
;   항상 '아님'(QA 의 KDBUSY 0 과 일치). 고치면 스크롤 중 분할을 건너뛰는 프레임이 생길 수 있어 동작을 바꾸지 않았다.
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

; ---- nmi_post: 분할 대기를 KINW 로 감쌈 (대기 중 중첩 NMI 는 eng_nmipre 가 버린다: 그 NMI 가 끝까지 돌면 사운드가
;      $07 뱅크로 바꿔 놓고 RTI 해 이 대기 루프가 엉뚱한 뱅크에서 이어짐)
eng_splitw:
  LDA #1
  STA KINW
  JSR eng_split
  LDA #0
  STA KINW
  RTS

; ---- 스프라이트 오버플로 플래그를 기다렸다가 BG=$1000
eng_split:
  LDA KACT
  CMP #3
  BNE @out
  LDA $02
  AND #$18
  CMP #$18
  BNE @out
  LDA KRDY                 ; 감지 스프라이트가 아직 PPU OAM 에 없으면(활성화 직후 1프레임 등) 오버플로가 안 나 대기만 길어짐 → 건너뜀
  BEQ @out
  JSR ppubusy             ; 메인 스레드가 VBlank 직후 PPU 를 직접 쓰는 중이면 이번 프레임 분할 안 함
  BCS @busy
  LDY #1                   ; 대기 한도 보정(아래)
  LDA $2002                ; 이전 프레임의 오버플로가 아직 켜져 있으면 사전렌더(261)에서 꺼지는 순간으로 동기
  AND #$20
  BEQ @clr                 ; 이미 꺼짐: NMI 가 길어 사전렌더를 지남(또는 지난 프레임 미발생) → @clr 에서 분할 줄 대기
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
@busy:
  INC KDBUSY
  RTS
@clr:                     ; NMI 가 길어(스크롤·큰 큐 작업) 이미 사전렌더를 지남 = 이번 프레임 렌더링 중(분할 줄 전) [QA A3]
  INC KDCLR               ; → 건너뛰지 않고 분할 줄의 오버플로 켜짐을 바로 기다린다(대기 한도는 241 전에 끝남)
  JMP @w2s

; ---- 리셋·전원 투입 뒤 첫 NMI(eng_nmipre): 엔진 RAM 전부를 빈 상태로. 전원 투입 직후 RAM 은 무작위(FCEUmm 기본 $FF)라
;      KTWO≠0 이면 첫 8x16 글자의 '아래 행 버퍼 공백 채움'을 건너뛰어 버퍼 쓰레기(팔레트 자료 등)가 아래 행에 찍혔다
;      (첫 카드 '월스트리트 키드' 오른쪽 잔상, fix3 [검증: Mesen 에서 RAM $FF 채움 + 리셋으로 재현]).
eng_init:
  JSR uinval              ; UGLY·T16 캐시, UNEXT·T16NEXT (A=0 으로 돌아옴)
  STA KLAY
  STA PFI
  STA T16I
  LDA #$FF
  LDX #NSLOT-1
@k:
  STA KHI,X
  DEX
  BPL @k
  STA KTHI                ; $FF = 어떤 행도 분할 구간이 아님(hkpre/kq 의 CMP KTHI → BCC)
  LDA #0
  STA KACT
  STA KFAIL
  STA KNEXT
  STA KTWO
  STA KCH
  STA KSPON
  STA KINVF
  STA KDCLR
  STA KDBUSY
  STA USTATE
  STA UNEXT
  STA UCNT
  STA KPGF
  STA KRDY
  STA KINW
  STA KSND
  LDA #$A5
  STA KMAG
  LDA #$5A
  STA KMAG+1
  RTS

; ---- 지운 화면(패스워드 표시) 용 8x8 풀: 0x50-0x9F
POOLFREE:
  .db $50,$51,$52,$53,$54,$55,$56,$57,$58,$59,$5A,$5B,$5C,$5D,$5E,$5F
  .db $60,$61,$62,$63,$64,$65,$66,$67,$68,$69,$6A,$6B,$6C,$6D,$6E,$6F
  .db $70,$71,$72,$73,$74,$75,$76,$77,$78,$79,$7A,$7B,$7C,$7D,$7E,$7F
  .db $80,$81,$82,$83,$84,$85,$86,$87,$88,$89,$8A,$8B,$8C,$8D,$8E,$8F
  .db $90,$91,$92,$93,$94,$95,$96,$97,$98,$99,$9A,$9B,$9C,$9D,$9E,$9F

.include "../build/kor_tables.asm"
.include "../build/kor_ui_tables.asm"

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
