# 제3자 자료 고지

이 저장소에는 다음 외부 자료와 도구가 포함되거나 사용됩니다.

## 포함된 데이터

- **NVIDIA Nemotron-Personas-Korea** — `rules/data/distribution.json`, `rules/data/korea-distribution.md`
  합성 페르소나 데이터셋의 인구 분포 집계. 라이선스 CC BY 4.0. https://huggingface.co/datasets/nvidia/Nemotron-Personas-Korea
  원본 페르소나 텍스트는 포함하지 않으며, 축별 비율 집계만 담았습니다.

## 포함된 폰트

- `assets/fonts/` — SIL Open Font License 1.1 로 배포되는 한글 폰트. 각 폰트의 라이선스 전문은 같은 폴더의 `OFL.txt` 를 참고하세요.

## 참고한 방법론

- 페르소나·카피 규칙(`rules/persona.md`, `rules/copy.md`)은 Russell Brunson(드림 100, 가치 사다리)과 Donald Miller(SB7) 의 공개된 프레임워크를 바탕으로 저자가 정리한 것입니다.
- 글쓰기 절대 규칙(`rules/writing-absolute.md`)은 **im-not-ai / humanize-korean** (MIT, https://github.com/epoko77-ai/im-not-ai) 의 룰북에서 일부 규칙을 골라 요약했습니다. 윤문 단계는 이 플러그인을 별도로 설치해 사용합니다.
- 숏츠 제작 흐름(대본 → 음성 → 장면 계획 → 합성 → 검수)은 **short_studio** (MIT, https://github.com/jkwon-startup/short_studio) 의 구조를 참고해 양 OS용으로 다시 구현했습니다. 코드를 복사하지 않았습니다.

- 2026-10 업그레이드에서 아래 오픈소스의 **방식**을 참고해 OSMU 구조에 맞게 새로 구현했습니다(코드 복사 없음).
  - **MoneyPrinterTurbo** (MIT, https://github.com/harry0703/MoneyPrinterTurbo) — 무료 음성(edge-tts) 기본값·무음 폴백, Pexels/Pixabay 스톡 영상, 배경음악 믹스, 장면 전환, 키 가림, 관대한 설정 로딩
  - **Pixelle-Video** (Apache-2.0, https://github.com/ATH-MaaS/Pixelle-Video) — HTML 프레임 템플릿과 `{{이름:타입=기본값}}` 자리표시자 규칙, 배경음악 폴더 방식
  - **HyperFrames** (Apache-2.0, https://github.com/heygen-com/hyperframes) — 애니메이션 시점을 고정하는 결정적 HTML→영상 렌더, 표시 자막↔발화 정렬(한글 대응으로 다시 작성), frame.md 브랜드 토큰, 검수 시트(장면 경계·폰 크기)와 P0/P1/P2 노트 형식

## 사용하는 오픈소스 패키지 (pip 로 설치, 저장소에 포함하지 않음)

- **edge-tts** (LGPL-3.0, https://github.com/rany2/edge-tts) — 무료 음성. Microsoft Edge 의 읽어주기 기능을 쓰는 비공식 경로라 서비스 쪽 변경으로 동작이 멈출 수 있습니다(그때는 자동으로 무음 자막 영상으로 대체). 상업적 이용 전에는 Microsoft 약관을 직접 확인하세요.
- **Playwright** (Apache-2.0, https://playwright.dev) — HTML 모션 템플릿 렌더(Chromium)
- **Pillow** (MIT-CMU), **openpyxl** (MIT)

## 사용하는 외부 서비스 (설치자가 직접 계약·키 발급)

- Anthropic Claude Code — 팀원 실행
- Pexels API / Pixabay API (무료 키) — 스톡 사진·영상. 두 서비스 모두 상업적 이용 무료·출처 표기 권장(`images/credits.json` 에 자동 기록). https://www.pexels.com/license/ · https://pixabay.com/service/license-summary/
- Google Gemini API 또는 Pixverse — 이미지·영상 생성(선택, 유료)
- ElevenLabs 또는 Google Gemini TTS — 음성(선택, 유료)
- Slack Incoming Webhook 또는 Telegram Bot API — 알림
- (선택) YouTube Data API v3 — 유튜브 리서치
- Remotion — (선택) 모션그래픽 렌더 대체 엔진. 기본 엔진(HTML 템플릿)은 라이선스 제약이 없습니다. Remotion 을 켜면(`motion_engine: remotion`) 개인·3인 이하 팀은 무료, 그 이상 조직은 Company License 가 필요합니다. https://www.remotion.dev/license

각 서비스의 생성물에는 해당 서비스 약관이 적용됩니다. 배경음악은 저장소에 포함하지 않으며, 설치자가 `assets/bgm/` 에 넣은 음악의 권리는 설치자 책임입니다.
