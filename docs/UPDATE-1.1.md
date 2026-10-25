# OSMU Studio 1.1 업데이트 (2026-10-25)

공개 저장소를 받아 설치하는 사람을 기준으로 다시 손본 판입니다. MoneyPrinterTurbo(MIT)·Pixelle-Video(Apache-2.0)·HyperFrames(Apache-2.0)를 분석해 OSMU 에 없던 것만 골라 **방식만 참고해 새로 구현**했습니다(코드 복사 없음, 출처는 `NOTICE.md`). 설계 결정 요약은 `DEVELOPMENT-PLAN.md` 14절.

## 한 줄 요약

**Claude Code + Pexels 무료 키만 있으면** 블로그·이미지·인스타·쓰레드·숏츠(음성·자막·모션·배경음악)까지 매일 자동으로 나옵니다. 유료 서비스는 품질을 올리고 싶을 때만 고르면 되고, 실패해도 무료 쪽으로 내려가 끝까지 완성합니다.

## OSMU 로 할 수 있는 것

- 주제 하나 → **블로그 글**(네이버 상위노출·SGE 규칙, 1,500자 이상) + **이미지 5장** + **인스타 피드**(3:4 카피 합성) + **쓰레드** + **30초 숏츠**
- 매일 아침 7시(한국시간) 자동 실행, 끝나면 **Slack·텔레그램 알림**(실패 시 멈춘 단계와 해결 방법)
- 주제는 폴더 / 엑셀·구글시트 / 기획서에서 읽음, 숏츠는 **실사** 또는 **모션그래픽** 스타일
- 리서치(시장·유튜브·블로그 상위) → 페르소나 → 핵심내용 5가지 → 후킹 카피 → 글 → 윤문(AI 티 제거) → 검수까지 팀원 8명이 분업
- 브랜드 색·자막 색·글꼴, 숏츠 비율·전환·목소리·배경음악을 설정 한 줄로 변경
- 생성·저장까지만 하며 자동 게시는 하지 않음

## 무엇이 바뀌었나

### A. 무료로 바로 시작

| 전 | 후 |
|---|---|
| 유료 키 2~3개(Gemini·ElevenLabs·Pixverse)가 있어야 숏츠 완성 | 기본값이 무료: 음성 **Microsoft Edge 음성(키 없음)**, 사진·영상 **Pexels/Pixabay(무료 키)** |
| 음성이 실패하면 영상이 안 나옴 | 설정한 음성 → Edge 음성 → **음성 없이 자막만** 순으로 내려가 반드시 완성, `timing.json`·알림에 기록 |
| AI 이미지 실패 시 이미지 없음 | 스톡 키가 있으면 스톡 사진으로 대체, 출처는 `images/credits.json` |
| 옛 설정 파일이면 업데이트 후 깨질 수 있음 | 기본값 위에 내 설정을 덮어씀(빠진 값 자동 채움, 잘못된 값은 경고 후 기본값), `config-show` 로 실제 값 확인 |
| 오류 로그·알림에 키가 섞일 위험 | 로그·알림·실행 기록에서 키 자동 가림 |

### B. 영상 품질

- **배경음악**: `assets/bgm/` 에 넣은 곡을 날마다 하나 골라 작게 깔고, 내레이션이 나오면 자동으로 더 작아짐(덕킹), 끝은 페이드아웃. 폴더가 비면 음악 없이.
- **장면 전환**: fade·dissolve·slide_left·slide_up·zoom·cut. 전환을 넣어도 전체 길이와 자막 타이밍이 그대로.
- **비율**: 9:16(쇼츠·릴스) / 1:1(인스타 피드) / 16:9(유튜브).
- **한글 자막 정렬**: 화면 글자 "3가지"와 읽는 말 "세 가지"가 달라도 발화 시점에 맞춤. 긴 문장은 여러 장으로 나눔.
- **인코더 자동 선택**: libx264 가 없는 FFmpeg 에서도 사용 가능한 인코더로 대체.

### C. 모션그래픽 엔진

- 모션 카드 = `templates/motion/*.html` 파일 하나. **CSS 만 알면 새 디자인 추가**.
- 기본 템플릿 4종: `kinetic_full`(큰 글자), `bullet_card`(핵심 카드), `data_bars`(막대 그래프), `endcard`.
- Playwright(Chromium)로 프레임마다 애니메이션 시점을 고정해 찍어 **같은 입력이면 같은 영상**. 움직임 없는 구간은 프레임 재사용으로 빠르게(4초 장면 약 2초).
- Remotion 은 선택 사항으로 내려감(4인 이상 조직 라이선스 부담 없음). Chromium 이 없으면 같은 내용의 정적 카드로.
- `motion-preview <템플릿>` 으로 미리 보기.

### D. 배포·설치·검수

- **설치 도우미 플러그인**: Claude Code 에서 `/plugin install osmu-studio --marketplace jkwon-startup/OSMU_studio` → `/osmu-studio:install`
- **Docker**(리눅스 서버용, CI 에서 이미지 빌드·점검), **`uv.lock`** 으로 같은 버전 설치
- **사전 점검**: 매일 실행 전 FFmpeg·글꼴·디스크·쓰기 권한 확인 → 문제면 비용 쓰기 전에 멈추고 알림. 실패 시 멈춘 단계 기록
- **doctor**: Edge 음성·Chromium·스톡 키·글꼴·배경음악 폴더 점검, 새 버전 알림
- **브랜드 토큰**: `config/frame.local.md` 하나로 브랜드 색·자막 색·글꼴(모션 카드·자막·인스타 합성이 공통으로 읽음)
- **검수 강화**: 첫 화면 빈 화면, 자막 읽기 시간 부족, 장면 경계 시트(`seams.jpg`), 폰 크기 미리보기 시트, 검수 의견 P0/P1/P2·`t=초` 형식
- **문서**: README 재작성(가입·API 키 안내 포함), 영문 README, `docs/TROUBLESHOOTING.md`

## 새로 생긴 명령

| 명령 | 하는 일 |
|---|---|
| `python scripts/osmu.py config-show` | 실제 적용되는 설정(기본값 + 내 설정) 보기 |
| `python scripts/osmu.py frame-write` | 브랜드 토큰 저장(설치 커맨드가 사용, 색 형식 검사) |
| `python scripts/osmu.py motion-preview <템플릿> [--props JSON] [--seconds 3] [--aspect 9:16]` | 모션 템플릿 미리 보기, 받는 값 안내 |
| `python scripts/osmu.py selftest --only stock,edge_tts` | 무료 스톡·음성 연결 검사 |
| `/osmu-studio:install` | 플러그인 사용자용 설치 도우미 |

## 새 설정 (`config/config.local.json`)

| 키 | 기본값 | 선택지 |
|---|---|---|
| `image_provider` | `stock` | `stock` / `gemini` / `pixverse` |
| `tts_provider` | `edge` | `edge` / `elevenlabs` / `gemini` / `pixverse` |
| `tts_fallback` | `["edge", "silent"]` | 실패 시 내려갈 순서 |
| `edge_tts_voice` / `edge_tts_rate` | `ko-KR-SunHiNeural` / `+10%` | 남성 `ko-KR-InJoonNeural` |
| `shorts_aspect` | `9:16` | `9:16` / `1:1` / `16:9` |
| `shorts_transition` | `fade` | `fade` / `dissolve` / `slide_left` / `slide_up` / `zoom` / `cut` |
| `motion_engine` | `html` | `html` / `remotion` |
| `bgm` | `{"enabled": true, "volume": 0.15}` | `file` 로 특정 곡 지정 |

새 비밀값(`.env`): `PEXELS_API_KEY`, `PIXABAY_API_KEY`(선택).

## 기존 사용자 업데이트 방법

```bash
git pull
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m playwright install chromium     # 모션 카드용 (한 번)
.venv/bin/python scripts/osmu.py doctor
.venv/bin/python scripts/osmu.py config-show
```

- 내 설정(`config/*.local.*`, `.env`)은 그대로 유지되고, 새 설정은 기본값으로 채워집니다.
- 이미 유료 서비스를 쓰고 있었다면 그대로 동작합니다. 실패할 때만 무료 쪽으로 내려갑니다.
- 무료 스톡을 쓰려면 `.env` 에 `PEXELS_API_KEY` 를 넣고 `image_provider` 를 `stock` 으로.

## 검증

| 항목 | 결과 |
|---|---|
| 단위 테스트 | 61개 통과 (무료 경로·폴백·설정 병합·키 가림·자막 정렬·템플릿·배경음악·브랜드 토큰·전환 합성·배포) |
| 무료 경로 실제 실행 | Edge 음성 → 모션 카드 6장 → 전환 → 합성 → 규격 검사 통과(정지 구간·첫 화면·자막·음량 -15.9 LUFS) |
| 새 폴더에 처음 설치 | venv·설치·doctor 정상, 무료 기본값 적용 |
| 플러그인 | `claude plugin validate` 통과 |
| 미확인 | Pexels 실제 연결(키 필요), Docker 로컬 빌드(CI 로 확인), 매일 실행 전체(Claude 팀원 포함, 약 $15) |

## 알려진 제약

- 무료 Edge 음성은 비공식 경로라 서비스 쪽 변경으로 멈출 수 있음(자막만 있는 영상으로 대체, 알림 표시). 상업적 이용 전 약관 확인.
- 스톡 사진은 한국 공간이 아닐 수 있음(검수 팀원이 엉뚱한 장면을 잡아 검색어를 바꾸게 함).
- 배경음악은 동봉하지 않음(저작권). 사용 허락된 곡만 직접 넣기.

## 다음 후보 (이번에 하지 않음)

웹 UI·API 서버, HyperFrames 엔진 자체 도입, 자동 게시, 한 번에 숏츠 변형 여러 개(훅 A/B), 바뀐 장면만 다시 렌더, Whisper 기반 단어 타이밍(유료 음성용), 유튜브 API 결과를 리서치에 연결(현재 키는 연결 검사에서만 사용).
