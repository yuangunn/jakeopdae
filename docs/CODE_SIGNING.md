# 코드 사이닝 가이드

`jakeopdae.exe` 를 사용자에게 보낼 때 Windows Defender SmartScreen이 경고를
띄우는 건 **인증서가 없기 때문**입니다. 미서명 exe는 Microsoft의 평판
시스템에 등록될 수 없어서 매번 사용자가 *"추가 정보 → 실행"*을 눌러야 해요.

이 문서는 *진짜* 코드 사이닝 인증서를 발급받아 빌드 파이프라인에 붙이는
절차입니다. 인증서 없이는 self-signed로도 SmartScreen이 안 풀려서, 차라리
지금처럼 README에 "추가 정보 → 실행" 안내를 두는 게 깔끔합니다.

## 인증서 발급 (연 비용 발생)

| 발급기관 | 종류 | 연 비용 (대략) | SmartScreen 효과 |
|---|---|---|---|
| Sectigo, DigiCert, GlobalSign | **OV** (Organization Validation) | $80–$200 | 평판 *축적* 후 풀림 (다운로드 200~500건) |
| 동일 발급기관 | **EV** (Extended Validation) | $300–$500 | **즉시** 풀림 |
| Sectigo Cloud Signing, SignPath | EV (HSM-backed) | 월 $25~ | 즉시 풀림, USB 토큰 불필요 |

개인 개발자에게는:
- **트래픽 적음 + 출시 빠르게**: EV 클라우드 사이닝 (Sectigo + SignPath 조합)
- **트래픽 많을 예정**: OV로 시작 (다운로드 쌓이면서 자연 평판)

## 발급 후 사인 절차

1. 인증서 발급기관에서 ``jakeopdae.pfx`` (PKCS#12 형식) 또는 USB 토큰을 받음
2. 빌드 머신에 인증서 임포트 또는 토큰 연결
3. ``signtool sign`` 으로 빌드 산출물 서명
4. ``signtool verify /pa /v dist/jakeopdae.exe`` 로 검증
5. 평소대로 GitHub Release에 첨부

### signtool 명령

```powershell
# 인증서 파일 방식 (PFX)
signtool sign `
  /f path\to\jakeopdae.pfx `
  /p $env:KEYMACRO_PFX_PASSWORD `
  /tr http://timestamp.sectigo.com `
  /td sha256 `
  /fd sha256 `
  dist\jakeopdae.exe

# USB 토큰 방식 (cert thumbprint로 매칭)
signtool sign `
  /sha1 0123456789ABCDEF... `
  /tr http://timestamp.sectigo.com `
  /td sha256 `
  /fd sha256 `
  dist\jakeopdae.exe
```

`-tr` (RFC3161 timestamp) 는 인증서 만료 후에도 서명을 유지시켜 주므로
**필수**.

## 우리 빌드 파이프라인에 끼우기

`packaging/keymacro.spec` 마지막에 다음 블록을 추가하면 PyInstaller가
EXE를 만든 직후에 자동으로 사인합니다:

```python
# --- optional code signing -------------------------------------------------
import os, subprocess, sys

if "KEYMACRO_PFX_PATH" in os.environ:
    pfx = os.environ["KEYMACRO_PFX_PATH"]
    pwd = os.environ.get("KEYMACRO_PFX_PASSWORD", "")
    target = "dist/jakeopdae.exe"
    cmd = [
        "signtool", "sign",
        "/f", pfx,
        "/p", pwd,
        "/tr", "http://timestamp.sectigo.com",
        "/td", "sha256",
        "/fd", "sha256",
        target,
    ]
    print(f"[codesign] running: {' '.join(cmd[:4] + ['/p', '***'] + cmd[6:])}")
    subprocess.run(cmd, check=True)
```

GitHub Actions에서는 `secrets.KEYMACRO_PFX_BASE64` 와
`secrets.KEYMACRO_PFX_PASSWORD` 를 등록해두고 `release.yml` 에 다음을
추가하면 됩니다:

```yaml
- name: Decode signing certificate
  shell: pwsh
  if: env.KEYMACRO_PFX_BASE64 != ''
  env:
    KEYMACRO_PFX_BASE64: ${{ secrets.KEYMACRO_PFX_BASE64 }}
  run: |
    $bytes = [System.Convert]::FromBase64String($env:KEYMACRO_PFX_BASE64)
    [System.IO.File]::WriteAllBytes("$env:RUNNER_TEMP\sign.pfx", $bytes)
    echo "KEYMACRO_PFX_PATH=$env:RUNNER_TEMP\sign.pfx" | Out-File -Append $env:GITHUB_ENV

- name: Build (signed if cert available)
  env:
    KEYMACRO_PFX_PASSWORD: ${{ secrets.KEYMACRO_PFX_PASSWORD }}
  run: pyinstaller packaging/keymacro.spec --clean --noconfirm
```

## 현재 상태 (v0.1.0)

- ❌ 코드 사이닝 인증서 없음 → exe는 미서명
- ✅ spec과 CI에 hook은 *준비*되어 있음 — 인증서 받으면 환경변수 / Secret 두 개만
  추가하면 자동 서명 시작
- ✅ README에 "추가 정보 → 실행" 안내 명시

## 참고

- [Microsoft signtool 문서](https://learn.microsoft.com/en-us/dotnet/framework/tools/signtool-exe)
- [GitHub Actions에서 signtool 호출](https://github.com/microsoft/setup-msbuild)
- SmartScreen 평판 빌딩: 다운로드 횟수 + 시간 + 사용자 신고 없음 → 자연스럽게 풀림
- EV 인증서가 없어도 트래픽이 쌓이면 OV로도 결국 SmartScreen은 사라집니다 (몇 주~몇 달 소요)
