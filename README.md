# 작업대 (jakeopdae)

> 매크로 자동화 데스크탑 도구 — 따뜻한 흑연 + 황동 한 점.
> Python 패키지 이름: `keymacro`

KeyMacro 같은 픽셀 매크로의 직관성과 Playwright 같은 DOM 자동화의 안정성을
한 화면에 모았습니다. 비개발자도 *클릭으로 시연 → 매크로 자동 생성*이 가능하고,
필요할 때만 디버그 모드 Chrome에 attach해서 정확한 셀렉터를 잡습니다.

## 무엇을 할 수 있나

| | 트리거 / 액션 | 설명 |
|---|---|---|
| 🖼 | 이미지가 보이면 → 클릭 | OpenCV 멀티스케일 템플릿 매칭 + 절대/상대 좌표 클릭 |
| ⏱ | 일정 시간 뒤에 | sleep + 키/텍스트/드래그 |
| 🎯 | 특정 색이 보이면 | 한 점 RGB 매칭 |
| 🌐 | 웹 요소가 보이면 → 클릭 | Playwright + CDP attach. `role=button[name="..."]` 셀렉터 자동 추출 |
| 🔗 | URL이 일치하면 | regex/contains/exact |
| 🌗 | 이미지+URL **(디버그 모드 X)** | 일반 Chrome에서도 동작. UIA로 주소창 읽음 |
| 🔤 | 화면 텍스트가 보이면 | Tesseract OCR. 한+영 / 일 / 중 |
| 📝 | 텍스트 추출 → 변수 | OCR 결과를 `${var}` 로 저장. 다음 단계에서 참조 |
| 📅 | 예약 실행 | 평일 9시, 매일, HH:MM 단위 |
| ● | **녹화 모드** | 마우스/키보드 시연 → Step 자동 생성 (F8 정지) |

추가로:
- **요소 picker** — Chrome 페이지에서 마우스 호버 + 클릭 한 번이면 가장 안정적인
  셀렉터가 자동으로 입력됨 (`role+name > id > tag+text > CSS path` 우선순위).
- **매크로 라이브러리** 사이드바 — 핀 / 최근 / 폴더 섹션. Ctrl+B 토글.
- **실행 이력** SQLite — 매 실행 기록, 매크로별 성공률 / 평균 시간 통계.
- **`.kma` 묶음** — 매크로 + 템플릿 PNG들을 한 파일로 패키징 / 공유.

## 설치

```powershell
git clone https://github.com/yuangunn/jakeopdae.git
cd jakeopdae

py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev,gui,notify]"
```

선택 의존성:

| extras | 무엇 |
|---|---|
| `[gui]` | PySide6 (GUI 편집기) |
| `[notify]` | requests (텔레그램 알림) |
| `[web]` | playwright (DOM 자동화 — `playwright install chromium` 필요) |
| `[browser-uia]` | uiautomation (하이브리드 트리거의 주소창 읽기, Windows) |
| `[ocr]` | pytesseract — [Tesseract 본체](https://github.com/UB-Mannheim/tesseract/wiki) 별도 설치 필요 |

## 빠른 시작

```powershell
# GUI 편집기
keymacro gui

# 매크로를 미리 열어둠
keymacro gui examples\web-training.yaml

# CLI 즉시 실행
keymacro run examples\simple-click.yaml

# 핫키 상주 모드 (F9 시작 / F10 정지 / F11 일시정지)
keymacro watch my-macro.yaml

# 디버그 모드 Chrome 띄우기 (웹 매크로 / 요소 picker용)
keymacro chrome-launch
```

## 매크로 한 장 예시

```yaml
name: 필수교육-자동화
description: 평일 아침 강의 자동 진행
variables:
  course_id: NSC0001305

steps:
  - id: wait_morning
    name: 평일 9시까지 대기
    trigger: { type: schedule, at: "09:00", weekdays: [0, 1, 2, 3, 4] }
    action: { type: wait, duration_s: 0 }

  - id: click_next
    name: '[다음으로] 버튼이 활성화되면 클릭'
    trigger:
      type: web_element
      selector: 'role=button[name="다음으로"]'
      url_contains: "/lec/"
      timeout_s: 1800
    action:
      type: web_click
      selector: 'role=button[name="다음으로"]'
    on_success_goto: click_next   # 강의 끝까지 무한 루프
```

## 디자인

`DESIGN.md` 참고. 컨셉은 *공방 작업대 위에 펼쳐놓은 작업 지시서와 운전반*:

- **Canvas**: 따뜻한 흑연 `#13110E`
- **Brass primary** `#E8B26A` — 시작 버튼 / 활성 카드 보더
- **Trigger 도장**:
  코발트(`#5BA8E5`, 이미지) /
  세이지(`#86B889`, 시간·예약) /
  장미(`#D9847C`, 픽셀) /
  보라(`#A98FD9`, 웹) /
  카키(`#C9B96A`, OCR)
- **Typography**: Space Grotesk (display) + Noto Sans KR (body, 4 weight 번들) +
  JetBrains Mono (좌표/시간/셀렉터)
- **Don'ts**: 그라디언트 / 큰 면적 채도 / `currentText()` 한국어 라벨로 모델 검증

## 아키텍처

```
keymacro/
├── core/        # capture · matcher · input · runner · web · web_picker · ocr
├── models/      # Pydantic v2 — Trigger / Action / Step / Macro
├── ui/          # PySide6 — main_window · step_form · type_picker · transport_bar
│   └── assets/fonts/  # NotoSansKR 4 weights (Regular/Medium/SemiBold/Bold)
├── storage/     # YAML 매크로 저장 + library.json + .kma 묶음
├── history/     # SQLite 실행 이력
├── hotkey/      # 글로벌 핫키 (pynput)
└── notify/      # 텔레그램
```

테스트: `pytest`. 현재 169 케이스 / 100% 통과.

## 한국 사용자 시나리오

이 도구가 가장 빛나는 곳:

1. **필수교육 사이트 자동 진행** — `[다음으로]` 버튼 활성화 감지 + 클릭 +
   다음 강의로 이동 무한 루프
2. **반복 폼 입력** — 예약 / 신청 / 설문 등 같은 정보를 매번 채워야 하는 페이지
3. **OTP 자동 입력** — OCR로 화면의 6자리 숫자 추출 → `${otp}` 변수에 저장 → 폼에 입력
4. **티켓팅 / 수강신청** — 시간 트리거 + 픽셀 트리거로 정확한 순간에 클릭
5. **KeyMacro에서 못 하는 DOM 동작** — 웹 요소가 *활성화*된 시점에 클릭
   (KeyMacro는 픽셀 모양만 봐서 disabled/enabled 구분 못 함)

## 단일 파일 배포 (.exe)

비개발자 친구한테 더블클릭 한 번으로 쓰게 하고 싶으면 PyInstaller로 단일
``jakeopdae.exe`` 만들 수 있습니다. NotoSansKR 폰트 + Qt + OpenCV가 다
들어가서 약 270 MB.

```powershell
.\.venv\Scripts\Activate.ps1
pip install pyinstaller
pyinstaller packaging\keymacro.spec --clean --noconfirm
# → dist\jakeopdae.exe
```

빌드 후 사용자에게 보낼 것:

| 필수 | 옵션 |
|---|---|
| ``jakeopdae.exe`` (270 MB) | Tesseract (OCR을 쓸 때만) |
| | ``playwright install chromium`` (웹 매크로 + 요소 picker를 쓸 때) |

**디버그 빌드** — 콘솔 창이 뜨고 stderr가 보이는 진단용 ``jakeopdae-debug.exe``:

```powershell
pyinstaller packaging\keymacro-console.spec --clean --noconfirm
```

크래시 / 누락된 hidden import를 추적할 때만 쓰세요.

## 사용자 가이드 (exe 받은 사람용)

1. ``jakeopdae.exe`` 더블클릭 → 5 ~ 10초 뒤 GUI 뜸 (one-file이라 첫 실행시
   임시 폴더로 압축 해제)
2. 우상단 [○ Chrome 시작] 누름 → keymacro 전용 Chrome 창이 뜸 → 학교 사이트
   로그인 (한 번만)
3. [+ 단계 추가] → 원하는 단계 종류 선택 → 영역/셀렉터 지정
4. 좌하단 [▶ 시작 (F9)] 또는 F9 핫키
5. 정지: F10 / 일시정지: F11

자주 묻는 것:

- **Windows Defender가 막아요** → "추가 정보" → "실행" 클릭. PyInstaller로 만든
  서명 안 된 exe라 SmartScreen이 처음 한 번 경고함. 안전한 코드.
- **느려요 / 첫 실행이 오래 걸려요** → one-file 압축 해제 때문. 두 번째부터는
  ``%LOCALAPPDATA%\Temp\_MEI…`` 캐시가 있어서 빠릅니다.
- **OCR이 "Tesseract을 찾을 수 없어요"라고 떠요** →
  https://github.com/UB-Mannheim/tesseract/wiki 에서 Windows installer 받아서
  설치. 설치 시 "Korean" 언어팩 체크.

## 라이선스

MIT. 자유롭게 fork / 수정 / 배포.

## Credits

이름: 작업대 (work-bench).
디자인 컨셉: getdesign.md 의 Warp / Linear 시스템에서 영감 — 따뜻한 흑연 +
한 점의 황동 + 도장 색.
