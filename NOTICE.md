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

## 사용하는 외부 서비스 (설치자가 직접 계약·키 발급)

- Anthropic Claude Code — 팀원 실행
- Google Gemini API 또는 Pixverse — 이미지·영상 생성
- ElevenLabs 또는 Google Gemini TTS — 음성
- Slack Incoming Webhook 또는 Telegram Bot API — 알림
- (선택) YouTube Data API v3 — 유튜브 리서치
- Remotion — 모션그래픽 렌더. 개인·3인 이하 팀은 무료, 그 이상 조직은 Company License 가 필요합니다. https://www.remotion.dev/license

각 서비스의 생성물에는 해당 서비스 약관이 적용됩니다.
