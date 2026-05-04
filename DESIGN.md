---
name: 작업대 (Jak-Eop-Dae)
colors:
  surface: "#13110E"
  surface-dim: "#0F0E0B"
  surface-bright: "#1F1C17"
  surface-container-lowest: "#0A0908"
  surface-container-low: "#16140F"
  surface-container: "#1A1813"
  surface-container-high: "#1F1D17"
  surface-container-highest: "#26241D"
  on-surface: "#F2EBDA"
  on-surface-variant: "#A39B85"
  outline: "#46423A"
  outline-variant: "#2C2922"
  surface-tint: "#F2EBDA"
  inverse-surface: "#F2EBDA"
  inverse-on-surface: "#13110E"
  inverse-primary: "#13110E"
  primary: "#E8B26A"
  on-primary: "#13110E"
  primary-container: "#3E2F18"
  on-primary-container: "#F2D7A8"
  primary-fixed: "#F2D7A8"
  primary-fixed-dim: "#C99752"
  on-primary-fixed: "#13110E"
  on-primary-fixed-variant: "#3E2F18"
  secondary: "#5BA8E5"
  on-secondary: "#001D33"
  secondary-container: "#0E2C46"
  on-secondary-container: "#CDE3F7"
  tertiary: "#86B889"
  on-tertiary: "#0A2A0D"
  tertiary-container: "#1F3A22"
  on-tertiary-container: "#D4E8D5"
  quaternary: "#D9847C"
  on-quaternary: "#3F0006"
  quaternary-container: "#4A211D"
  on-quaternary-container: "#F2D2CD"
  error: "#D9847C"
  on-error: "#3F0006"
  error-container: "#4A211D"
  on-error-container: "#F2D2CD"
  background: "#13110E"
  on-background: "#F2EBDA"
  surface-variant: "#26241D"
typography:
  display-lg:
    fontFamily: Space Grotesk
    fontSize: 48px
    fontWeight: "500"
    lineHeight: 52px
    letterSpacing: -0.02em
  display-md:
    fontFamily: Space Grotesk
    fontSize: 32px
    fontWeight: "500"
    lineHeight: 36px
    letterSpacing: -0.02em
  display-sm:
    fontFamily: Space Grotesk
    fontSize: 22px
    fontWeight: "500"
    lineHeight: 26px
    letterSpacing: -0.01em
  headline-lg:
    fontFamily: Pretendard Variable
    fontSize: 20px
    fontWeight: "600"
    lineHeight: 26px
    letterSpacing: -0.01em
  headline-md:
    fontFamily: Pretendard Variable
    fontSize: 16px
    fontWeight: "600"
    lineHeight: 22px
  headline-sm:
    fontFamily: Pretendard Variable
    fontSize: 14px
    fontWeight: "600"
    lineHeight: 20px
  body-lg:
    fontFamily: Pretendard Variable
    fontSize: 15px
    fontWeight: "400"
    lineHeight: 22px
  body-md:
    fontFamily: Pretendard Variable
    fontSize: 13px
    fontWeight: "400"
    lineHeight: 19px
  body-sm:
    fontFamily: Pretendard Variable
    fontSize: 11px
    fontWeight: "400"
    lineHeight: 15px
  label-lg:
    fontFamily: Pretendard Variable
    fontSize: 14px
    fontWeight: "600"
    lineHeight: 20px
    letterSpacing: 0.02em
  label-md:
    fontFamily: Pretendard Variable
    fontSize: 12px
    fontWeight: "600"
    lineHeight: 16px
    letterSpacing: 0.04em
  label-sm:
    fontFamily: Pretendard Variable
    fontSize: 10px
    fontWeight: "700"
    lineHeight: 14px
    letterSpacing: 0.08em
  data-lg:
    fontFamily: JetBrains Mono
    fontSize: 18px
    fontWeight: "500"
    lineHeight: 24px
    letterSpacing: 0
  data-md:
    fontFamily: JetBrains Mono
    fontSize: 13px
    fontWeight: "500"
    lineHeight: 19px
    letterSpacing: 0
  data-sm:
    fontFamily: JetBrains Mono
    fontSize: 11px
    fontWeight: "400"
    lineHeight: 14px
    letterSpacing: 0
rounded:
  none: 0
  sm: 4px
  DEFAULT: 8px
  md: 10px
  lg: 14px
  xl: 20px
  full: 9999px
spacing:
  unit: 4px
  page-margin: 24px
  card-padding: 20px
  card-gap: 12px
  section-margin: 28px
  transport-height: 88px
components:
  page-frame:
    backgroundColor: "{colors.background}"
    textColor: "{colors.on-background}"
    padding: 24px
  header-bar:
    backgroundColor: transparent
    textColor: "{colors.on-surface}"
    typography: "{typography.display-sm}"
    padding: 18px 0 14px 0
  header-name:
    typography: "{typography.display-sm}"
    textColor: "{colors.on-surface}"
  header-sub:
    typography: "{typography.label-md}"
    textColor: "{colors.on-surface-variant}"
  status-pill-idle:
    backgroundColor: transparent
    textColor: "{colors.on-surface}"
    rounded: "{rounded.full}"
    padding: 6px 14px
    border: "1px solid {colors.outline-variant}"
    typography: "{typography.label-md}"
  status-pill-running:
    backgroundColor: rgba(232, 178, 106, 0.10)
    textColor: "{colors.primary}"
    rounded: "{rounded.full}"
    padding: 6px 14px
    border: "1px solid {colors.primary}"
    typography: "{typography.label-md}"
  status-pill-paused:
    backgroundColor: rgba(91, 168, 229, 0.10)
    textColor: "{colors.secondary}"
    rounded: "{rounded.full}"
    padding: 6px 14px
    border: "1px solid {colors.secondary}"
    typography: "{typography.label-md}"
  status-dot-idle:
    backgroundColor: "{colors.outline-variant}"
    rounded: "{rounded.full}"
    width: 8px
    height: 8px
  status-dot-running:
    backgroundColor: "#D44A30"
    rounded: "{rounded.full}"
    width: 8px
    height: 8px
  step-card:
    backgroundColor: "{colors.surface-container}"
    textColor: "{colors.on-surface}"
    rounded: "{rounded.lg}"
    padding: 20px 20px 16px 20px
    border: "1px solid {colors.outline-variant}"
  step-card-active:
    backgroundColor: "{colors.surface-container-high}"
    border: "1px solid {colors.primary}"
  step-card-error:
    border: "1px solid {colors.quaternary}"
  step-card-stripe-image:
    backgroundColor: "{colors.secondary}"
    height: 3px
  step-card-stripe-time:
    backgroundColor: "{colors.tertiary}"
    height: 3px
  step-card-stripe-pixel:
    backgroundColor: "{colors.quaternary}"
    height: 3px
  step-number:
    typography: "{typography.data-lg}"
    textColor: "{colors.on-surface-variant}"
  step-trigger-line:
    typography: "{typography.headline-md}"
    textColor: "{colors.on-surface}"
  step-action-line:
    typography: "{typography.body-lg}"
    textColor: "{colors.on-surface-variant}"
  step-meta-tag:
    backgroundColor: "{colors.surface-container-highest}"
    textColor: "{colors.on-surface-variant}"
    typography: "{typography.label-sm}"
    rounded: "{rounded.sm}"
    padding: 3px 8px
  badge-trigger-image:
    backgroundColor: "{colors.secondary-container}"
    textColor: "{colors.on-secondary-container}"
    typography: "{typography.label-sm}"
    rounded: "{rounded.sm}"
    padding: 3px 8px
  badge-trigger-time:
    backgroundColor: "{colors.tertiary-container}"
    textColor: "{colors.on-tertiary-container}"
    typography: "{typography.label-sm}"
    rounded: "{rounded.sm}"
    padding: 3px 8px
  badge-trigger-pixel:
    backgroundColor: "{colors.quaternary-container}"
    textColor: "{colors.on-quaternary-container}"
    typography: "{typography.label-sm}"
    rounded: "{rounded.sm}"
    padding: 3px 8px
  divider-dotted:
    backgroundColor: transparent
    border: "1px dashed {colors.outline-variant}"
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.on-primary}"
    typography: "{typography.label-lg}"
    rounded: "{rounded.full}"
    height: 44px
    padding: 0 22px
  button-primary-pressed:
    backgroundColor: "{colors.primary-fixed-dim}"
  button-ghost:
    backgroundColor: transparent
    textColor: "{colors.on-surface}"
    typography: "{typography.label-lg}"
    rounded: "{rounded.full}"
    height: 40px
    padding: 0 18px
    border: "1px solid {colors.outline-variant}"
  button-danger-ghost:
    backgroundColor: transparent
    textColor: "{colors.error}"
    typography: "{typography.label-md}"
    rounded: "{rounded.full}"
    height: 32px
    padding: 0 14px
    border: "1px solid {colors.outline-variant}"
  transport-bar:
    backgroundColor: "{colors.surface-container-lowest}"
    border: "1px solid {colors.outline-variant}"
    rounded: "{rounded.xl}"
    padding: 16px 20px
  transport-play:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.on-primary}"
    typography: "{typography.label-lg}"
    rounded: "{rounded.full}"
    height: 56px
    minWidth: 132px
  transport-stop:
    backgroundColor: transparent
    textColor: "{colors.on-surface}"
    typography: "{typography.label-lg}"
    rounded: "{rounded.full}"
    height: 56px
    minWidth: 100px
    border: "1px solid {colors.outline-variant}"
  transport-pause:
    backgroundColor: transparent
    textColor: "{colors.on-surface}"
    typography: "{typography.label-lg}"
    rounded: "{rounded.full}"
    height: 56px
    minWidth: 100px
    border: "1px solid {colors.outline-variant}"
  match-gauge-track:
    backgroundColor: "{colors.surface-container-highest}"
    rounded: "{rounded.full}"
    height: 6px
  match-gauge-fill:
    backgroundColor: "{colors.primary}"
    rounded: "{rounded.full}"
  input-field:
    backgroundColor: "{colors.surface-container-low}"
    textColor: "{colors.on-surface}"
    typography: "{typography.body-lg}"
    rounded: "{rounded.md}"
    padding: 0 14px
    height: 40px
    border: "1px solid {colors.outline-variant}"
  input-field-focus:
    border: "1px solid {colors.primary}"
  input-label:
    typography: "{typography.label-md}"
    textColor: "{colors.on-surface-variant}"
  segmented-track:
    backgroundColor: "{colors.surface-container-low}"
    rounded: "{rounded.full}"
    padding: 4px
    border: "1px solid {colors.outline-variant}"
  segmented-thumb:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.on-primary}"
    rounded: "{rounded.full}"
    typography: "{typography.label-md}"
    padding: 6px 14px
  add-step-fab:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.on-primary}"
    typography: "{typography.label-lg}"
    rounded: "{rounded.full}"
    height: 52px
    padding: 0 26px
  type-picker-tile:
    backgroundColor: "{colors.surface-container-low}"
    textColor: "{colors.on-surface}"
    rounded: "{rounded.lg}"
    padding: 18px
    border: "1px solid {colors.outline-variant}"
  type-picker-tile-hover:
    backgroundColor: "{colors.surface-container-high}"
    border: "1px solid {colors.primary}"
  empty-state-rule:
    backgroundColor: transparent
    border: "1px dashed {colors.outline-variant}"
  empty-state-headline:
    typography: "{typography.headline-lg}"
    textColor: "{colors.on-surface}"
  empty-state-body:
    typography: "{typography.body-lg}"
    textColor: "{colors.on-surface-variant}"
  log-pre:
    backgroundColor: "{colors.surface-container-lowest}"
    textColor: "{colors.on-surface-variant}"
    typography: "{typography.data-sm}"
    rounded: "{rounded.md}"
    padding: 12px
    border: "1px solid {colors.outline-variant}"
---

# 작업대 — keymacro 데스크톱 편집기

목수의 작업대 위에 펼쳐놓은 작업 지시서. 각 단계는 번호가 매겨진 카드이고, 아래쪽에는 운전반(transport)이 항상 떠 있어 시작/일시정지/정지를 한 번에 누른다. 사용자는 매크로를 *짜는* 사람이 아니라 *조작하는* 사람이라는 전제 — 현장 작업자가 매뉴얼을 읽고 손으로 누르는 그 결을 따라간다.

## Brand & Style

**Concept**: 공방의 작업대 위에 펼쳐놓은 단계 지시서와 운전반. 따뜻한 흑연 위에 황동(brass) 한 점이 놓인 풍경. 화이트 배경의 사무 SaaS도 아니고, 게이밍 RGB도 아닌 — 좋은 도구가 잘 정리된 워크벤치의 차분한 톤.

**Personality**: 친근한 실용주의. 미니멀리즘의 차가움이 아니라, 잘 정돈된 공구함의 너그러움. 라벨이 한국어 능동태로 쓰여 있고("이미지가 보이면 / 이 위치를 클릭한다"), 큰 버튼은 손가락 끝으로 정확히 누를 수 있게 크다. 실패는 빨간 경고가 아니라 따뜻한 장미빛 표시로 알려준다 — 사용자를 혼내지 않는다.

## Colors

세 줄로 정리하면: **따뜻한 흑연 캔버스 + 황동 주조연(主助演) + 트리거 종류별 도장(stamp) 세 가지 + 실행 중 한순간만 쓰는 적색 펄스**.

- **Canvas** `surface` `#13110E` — 흑연인데 푸른 KTX와 다르게 **갈색 언더톤** (작업대 나무의 그림자). 모든 표면은 이 위에서 `surface-container-*` 사다리로 떠오른다. 그림자는 거의 안 쓴다.
- **Text** `on-surface` `#F2EBDA` (따뜻한 골편색) — 순백은 작업등 아래에서 눈을 찌른다. 보조 텍스트는 `on-surface-variant` `#A39B85` (담배재 회색).
- **Brass** `primary` `#E8B26A` — 황동 손잡이. 시작 버튼, 활성 단계 카드 테두리, 매칭 게이지 채움. 면적이 작은 곳에만 쓴다 — 큰 패널 배경으로 절대 깔지 않는다.
- **Trigger stamps** — 각 트리거 종류는 카드 상단 3px 띠 + 작은 배지로 식별된다. 배경 패널이나 텍스트에는 안 쓴다.
  - **이미지** `secondary` `#5BA8E5` (코발트 파랑) — 화면을 *보고* 있다는 의미.
  - **시간** `tertiary` `#86B889` (세이지 초록) — 시계가 흐르는 의미.
  - **픽셀** `quaternary` `#D9847C` (장미빛) — 색을 *집어내는* 의미. 에러 색과 같은 계열로 쓰지만 컨텍스트가 다르다.
- **Ember** `#D44A30` (Boston Clay) — 매크로가 *지금 실행 중*임을 알리는 헤더 펄스 점에만 쓴다. 다른 데서 쓰면 무게가 빠진다. `status-dot-running`에 하드코딩.
- **금지**: 그라디언트, 보라/네온/형광, 위 5개 외의 컬러.

## Typography

세 패밀리, 각자 분명한 역할.

- **Space Grotesk** (display 22–48px) — 헤더(`작업대`), 단계 번호, 매크로 이름. 기하학적 그로테스크. KTX의 Bricolage가 신문 헤드라인 톤이라면, Space Grotesk는 산업 사이니지 톤 — 공방 메타포에 더 어울린다.
- **Noto Sans KR** (body, headline, label) — 한국어 우선. 본문/단계 설명/폼 라벨/버튼은 전부 여기로. Adobe/Google 합작의 한글 디자인 표준 — 모든 OS에서 동일하게 렌더링되도록 4개 weight (Regular/Medium/SemiBold/Bold)를 패키지에 번들링하고 ``QFontDatabase.addApplicationFont``로 시작 시 등록한다. 시스템에 Pretendard가 깔린 환경에서는 둘 사이가 거의 호환되니 fallback 체인이 어긋날 일 없다.
- **JetBrains Mono** (data 11–18px) — 좌표 (x, y, w, h), 신뢰도 (0.92), 시간 (1.50s), 단계 ID. 정렬되는 모든 숫자.

위계는 색이 아니라 *크기와 굵기*로만 표현. Display는 -0.01~-0.02em으로 트래킹을 좁혀 무게를 잡고, Mono는 트래킹 0. 한국어 라벨은 트래킹을 절대 늘리지 않는다 — 한글이 깨져 보인다.

## Layout & Spacing

4px 베이스 유닛. 페이지 여백은 24px (KTX의 20px보다 살짝 넓음 — 데스크톱 윈도우라 마진이 더 필요).

화면 구성은 **세 층**:
1. **상단 헤더** (66px 정도) — 좌측에 매크로 이름, 우측에 상태 알약 (idle / 실행 중 / 일시정지).
2. **본문** (가용 영역 전부) — 좌측 단계 카드 리스트 (40~45%) + 우측 단계 편집 패널 (55~60%). 분할은 사용자가 드래그해서 바꿀 수 있다.
3. **하단 운전반** (88px sticky) — 큰 시작 알약 + 일시정지 + 정지 + 실시간 매칭 게이지. **항상 보인다** — 어디서 무엇을 편집하든 손이 닿는 곳에 운전 컨트롤이 있어야 한다.

리스트가 곧 레이아웃이다. 단계는 세로로 12px 간격으로 쌓인다. 가로 그리드 절대 안 만든다 — 시퀀스의 *순서*가 가장 중요한 정보이므로 세로 리듬이 모든 것을 이긴다.

비대칭은 의도적: 카드 상단의 트리거 색 띠가 페이지 좌측 바깥으로 살짝 나간 느낌(시각적으로는 padding 0), 단계 번호는 카드 좌상단에서 mono로 굵게, 트리거 설명은 헤드라인으로, 액션 설명은 한 단 작은 본문체로. 눈이 두 채널을 학습한다.

## Elevation & Depth

깊이는 `surface-container-*` 사다리와 1px `outline-variant` 보더로만 표현. 박스 섀도는 운전반과 (선택) 시스템 트레이 아이콘 외에는 쓰지 않는다.

활성 단계 카드는 한 단 위 사다리(`surface-container-high`) + `primary` 보더 + 좌측 트리거 색 띠가 굵어지면서(3→4px) "지금 이 단계가 실행되고 있다"를 시각화. 펄스 애니메이션 안 한다 — 정적이지만 명백하게.

## Shapes

- **단계 카드 / 운전반**: 14px (`rounded.lg`) — 여기보다 둥글면 캐주얼해지고 모지면 폼 같다.
- **버튼 / 알약**: 풀필(`rounded.full`).
- **인풋**: 10px (`rounded.md`).
- **트리거 띠 / 배지**: 4px (`rounded.sm`) — 도장 찍은 느낌.

## Components

### 상단 헤더

- 좌측: `display-sm` "작업대" + `label-md` 부제 (현재 매크로 파일 이름, 또는 `(저장 안 됨)`).
- 우측: 상태 알약. 세 상태 — `idle` (테두리만, 회색 점) / `running` (`primary` 보더, ember 점, "실행 중 · 단계 2/4") / `paused` (`secondary` 보더, "일시정지").

### 단계 카드

각 단계는 카드 한 장. 위에서 아래로:
1. **트리거 띠** — 3px 컬러 바, 카드 상단 모서리에 직각으로. 활성 시 4px.
2. **머리줄** — 좌측에 단계 번호 (`STEP 01` mono 굵게) + 트리거 종류 배지 + (있다면) 매크로 이름. 우측 상단에 작은 [수정] / [복제] / [삭제] 아이콘은 hover 시에만 등장.
3. **트리거 줄** — `headline-md` 한국어 능동태 한 줄: "이미지 `templates/login.png`이(가) 영역 (100, 200) ~ (900, 800)에 보이면". 폼 필드를 그대로 노출하지 않고 **문장으로 풀어서** 보여준다.
4. **액션 줄** — `body-lg` 한 단 작게: "→ 매칭 위치를 더블클릭한다 (오프셋 +5, -3)".
5. **메타 태그 줄** — 작은 칩들로 "반복 4회", "실패 시 건너뜀", "재시도 2회". 기본값(반복 1회/실패 시 중단/재시도 0회)인 항목은 표시하지 않는다 — 노이즈.

비활성 단계는 한 단 어두운 사다리에 텍스트 색 한 단 떨어뜨려 *읽을 수는 있되 demoted* 상태로 표시.

### 단계 편집 패널 (우측)

선택된 단계의 폼이 우측에 항상 떠 있다. KeyMacro의 모달과 다르게 **상시 표시 + 즉시 반영**. 라벨은 한국어 능동태:
- "이 단계 이름" (id가 아니라 name 위주로 노출)
- "언제 실행할까요?" (트리거 타입 segmented control)
- "어떻게 동작할까요?" (액션 타입 segmented control)
- 트리거가 image일 때: "어떤 이미지를 찾을까요?" + [영역 그리기] [화면에서 캡처] 버튼이 큼직한 primary 색
- "실패하면?" (계속 / 건너뛰기 / 재시도 segmented)
- "이 단계를 몇 번 반복할까요?" (정수 입력 + 옆에 큰 +/- 버튼)

### 운전반 (하단 sticky)

좌측: 56px 높이의 [▶ 시작 (F9)] **brass 알약**, 같은 높이의 [⏸ 일시정지 (F11)] / [■ 정지 (F10)] 고스트.
우측: 매칭 게이지 — `match-gauge-track`(6px 높이) 위에 `match-gauge-fill`이 0~100% 채워지고, 그 위에 mono로 "단계 2/4 · 신뢰도 0.873"이 한 줄 표시. 실행 중이 아니면 게이지는 빈 트랙만 보인다.

운전반 자체는 카드처럼 떠 있는 컨테이너 — `surface-container-lowest` 배경 + `outline-variant` 보더 + `rounded.xl` 코너.

### 단계 추가 — 타입 픽커

KeyMacro의 `[추가]` UX를 그대로 차용. `+ 단계 추가` brass 알약(`add-step-fab`)을 누르면 **모달 시트**가 떠서 6개 타일 그리드를 보여준다:

| 타일 | 라벨 | 설명 |
|---|---|---|
| 🖼 | 이미지가 보이면 | 화면 영역에서 등록한 이미지를 찾아 클릭/조작 |
| ⏱ | 일정 시간 뒤에 | 지정한 시간만큼 기다렸다가 다음 동작 |
| 🎯 | 특정 색 픽셀이 보이면 | 한 점의 RGB가 특정 값이 될 때까지 기다림 |
| ⌨ | 키 입력 | 단축키 / 키 조합을 보냄 |
| ✏ | 텍스트 입력 | 문자열을 타이핑 |
| ⏸ | 잠시 멈춤 | 다음 단계 전에 멈추기 |

타일은 `type-picker-tile` (회색 배경 + 점선 호버), 호버 시 `type-picker-tile-hover` (밝은 배경 + brass 보더). 클릭하면 그 타입으로 새 단계 카드가 리스트에 추가되고 우측 편집 패널에 자동 포커스.

### 빈 상태 (no steps)

화면 정중앙 위아래로 점선 가로줄 두 가닥(64px 간격). 사이에 `headline-lg` "아직 단계가 없습니다", `body-lg` "위의 [+ 단계 추가]를 눌러 첫 단계를 만들어 보세요". 그 아래 `button-primary` `+ 단계 추가`. KTX의 빈 상태(가상의 레일)와 결을 맞추되, 메타포는 *작업 노트의 빈 페이지*.

### 영역 그리기 오버레이

이미 PySide6 구현체가 있음 (`region_picker.py`). 토큰 적용 — 반투명 흑연 (`rgba(8,9,12,0.65)`) 배경 + 점선 brass(`primary`) 셀렉션 사각형. 모서리 마커는 안 그린다 — 점선 자체로 충분.

## Don'ts

- **`trigger.type=image` 같은 스키마 라벨을 화면에 노출하지 않는다.** 한국어 능동태로 풀어 쓴다 ("이미지가 보이면").
- **버튼 라벨에 "OK / Cancel" 쓰지 않는다.** 동사를 명시 — "저장", "취소", "삭제", "추가".
- **그라디언트 배경 안 쓴다.** 작업대의 단단한 무광택을 유지.
- **활성 brass(`primary`)를 큰 패널 배경으로 깔지 않는다.** 버튼 / 카드 보더 / 게이지 채움에만.
- **에러를 모달 다이얼로그로 띄우지 않는다.** 해당 인풋 아래에 인라인 `quaternary`(장미)로 표시.
- **아이콘만 있는 버튼 안 만든다.** 항상 한국어 라벨이 같이 붙는다 (운전반 시작 버튼은 `▶ 시작` 식).
- **ember(`#D44A30`)를 `status-dot-running` 외에서 쓰지 않는다.** 한 점에만 살아 있는 색.
- **단계 리스트에 가로 그리드를 넣지 않는다.** 항상 세로 한 줄 — 시퀀스의 순서를 시각적으로 보존.

## Do's

- **단계 번호를 항상 표시.** `STEP 01` mono로 카드 좌상단. 사람은 순서가 있는 일을 *번호*로 가장 잘 읽는다.
- **트리거/액션을 한국어 능동태 문장으로 노출.** 폼 필드는 편집 패널에만, 카드에는 *완성된 문장*만.
- **운전반은 항상 보인다.** 단계를 편집하든 영역을 그리든 시작/정지가 손에 닿는 위치에.
- **실행 중 활성 단계는 한 단 밝은 사다리 + brass 보더로 시각화.** 펄스 안 한다 — 정적 표현.
- **기본값과 다른 메타만 칩으로 노출.** 반복 1회 / 실패 시 중단 / 재시도 0회는 카드에 표시 안 함.
- **숫자/시간/좌표는 무조건 mono.** `(100, 200)`, `0.92`, `1.50s` 모두 JetBrains Mono.
- **타입 픽커 시트의 타일은 6개 고정.** 더 추가하지 않는다 — 6개가 한 화면에 안 흩어지고 들어가는 최댓값.
