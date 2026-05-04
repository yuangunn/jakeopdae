# 데모 GIF 녹화 가이드

README 상단에 짧은 GIF 두 어개 박아두면 *기능 설명문 다섯 줄*보다 효과가 좋습니다.
이 문서는 30초짜리 GIF를 만드는 가장 빠른 경로입니다.

## 준비

1. **screen-to-gif** (https://www.screentogif.com) — 무료, 한국어 UI, 6 MB 정도. 30초 영상 → ~1 MB GIF
2. 또는 **LICEcap** (https://www.cockos.com/licecap/) — 더 가벼움 (1 MB 미만)
3. 두 도구 모두: 윈도우 영역을 드래그로 선택 → 녹화 → 시작/정지 → GIF로 저장

## 권장 시나리오 (3개)

### 1. `01-recorder-flow.gif` — 녹화 모드
**약 20초.** 사용자가 *시연만 했는데 매크로가 자동 생성되는* 핵심 가치를 보여줌.

녹화 시퀀스:
1. keymacro GUI 떠 있는 상태 (빈 매크로)
2. 우상단 [● 녹화] 클릭 → 빨간 점 + "녹화 중" 상태바 표시
3. 메모장으로 가서 클릭 → "안녕하세요" 타이핑 → Enter → Ctrl+S
4. F8 누름
5. 다이얼로그 "이벤트 14개 → 단계 6개로 변환" → [Yes]
6. GUI에 단계 카드 6개 자동으로 채워짐

→ 1 MB 미만, 15~25 fps

### 2. `02-element-picker.gif` — 요소 picker
**약 15초.** *셀렉터를 손으로 안 친다* 는 두 번째 핵심 가치.

녹화 시퀀스:
1. 웹 단계가 선택된 상태 (셀렉터 입력란 비어 있음)
2. [🎯 화면에서 요소 고르기] 클릭
3. Chrome 페이지로 자동 포커스 이동, 마우스 따라 황동 박스가 요소 위에 떠다님
4. 상단 패널에 *지금 호버한 요소의 셀렉터*가 라이브 표시
5. [학습하기] 버튼에 마우스 올림 → `role=button[name="학습하기"]` 보임
6. 클릭 → 셀렉터 자동 입력됨

→ Chrome 화면도 같이 잡혀야 함, 큰 영역 (1.5~2 MB 정도)

### 3. `03-hybrid-no-debug.gif` — 디버그 모드 없는 일반 Chrome 자동화
**약 25초.** *디버그 모드 안 켜도 됨* 이 KeyMacro 대비 차별점.

녹화 시퀀스:
1. 일반 Chrome (사용자 평소 프로필) 띄움 — 학교 사이트 로그인된 상태
2. keymacro GUI에서 [+ 단계 추가] → 🌗 [이미지+URL (디버그 모드 X)] 선택
3. 단계 카드 추가됨, 우측 폼에 URL 패턴 / 이미지 영역 입력
4. F9 시작 → URL이 매칭되는 일반 Chrome 페이지에서 매크로 발사

→ 최대 2 MB, 핵심은 "디버그 Chrome이 따로 안 떠 있다"는 점

## 저장 + 추가

저장 경로:
```
docs/screenshots/01-recorder-flow.gif
docs/screenshots/02-element-picker.gif
docs/screenshots/03-hybrid-no-debug.gif
```

README 상단에 마크다운으로 박기:
```markdown
![녹화 모드](docs/screenshots/01-recorder-flow.gif)
![요소 picker](docs/screenshots/02-element-picker.gif)
![하이브리드 트리거](docs/screenshots/03-hybrid-no-debug.gif)
```

또는 표 형태:
```markdown
| 녹화 모드 | 요소 picker |
|---|---|
| ![녹화](docs/screenshots/01-recorder-flow.gif) | ![picker](docs/screenshots/02-element-picker.gif) |
```

## 팁

- **15 fps로 녹화**: 25 fps는 GIF 사이즈가 1.5배 커짐, 시각적 차이는 작음
- **마우스 커서를 천천히** 움직이세요 — GIF는 연속 프레임을 인접 프레임끼리 비교 압축하므로 빠른 움직임은 사이즈를 키움
- **3 MB 넘으면 줄여보기**: 영역 더 좁게 잡거나 fps 낮추거나 색상 팔레트 줄이기
- **Loop**: 무한 반복으로 저장 — README에서 끊김 없이 보임
- **타이틀 카드**: 영상 첫 프레임에 "녹화 모드 — 시연만 하면 매크로가 만들어짐" 같은 한 줄을 1초 정도 박으면 무엇을 보여주는지 즉시 전달됨

## 자동화 (선택)

녹화는 사람 손으로 해야 자연스럽지만, 동일 매크로의 *재생 결과*는 자동화 가능:

```yaml
# examples/demo-recording.yaml — 데모용 매크로
name: demo-recording
steps:
  - id: open_notepad
    trigger: { type: time, delay_s: 1 }
    action: { type: key, keys: "win+r" }
  - id: type_notepad
    trigger: { type: time, delay_s: 0.5 }
    action: { type: type, text: "notepad" }
  ...
```

이걸 ``keymacro run examples/demo-recording.yaml``로 돌리면서 동시에 화면 녹화하면
*매크로가 직접 데모를 시연하는* 메타-데모 GIF가 됩니다 — 마케팅 효과 ↑.
