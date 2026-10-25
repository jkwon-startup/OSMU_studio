# OSMU Studio

[English](README.en.md)

주제 하나를 **매일 아침 7시(한국시간)에 자동으로** 블로그 글 → 이미지 5장 → 인스타그램 피드 → 쓰레드 → 30초 숏츠 영상으로 바꿔 주고, 끝나면 Slack 또는 텔레그램으로 알려 주는 Claude Code 콘텐츠 팀입니다.

- 팀장 1명(메인 세션)과 팀원 8명(서브에이전트)이 리서치 → 페르소나 → 핵심내용 5가지 → 후킹 카피 → 블로그 → 윤문 → 이미지 · SNS · 숏츠 → 검수 순으로 일합니다.
- 글은 한국 시장 페르소나 방법론, 네이버 상위노출(C-Rank·DIA·스마트블록)과 SGE(E-E-A-T) 규칙, 친구 톤 카피 규칙을 따릅니다. 작성 뒤에는 [humanize-korean](https://github.com/epoko77-ai/im-not-ai) 플러그인으로 AI 티를 뺍니다.
- **Claude Code 만 있으면 무료로 시작할 수 있습니다.** 음성은 무료(키 없음), 사진·영상은 Pexels 무료 키 하나면 됩니다. 유료 서비스(Gemini·ElevenLabs·Pixverse)는 선택입니다.
- 주제는 폴더 / 엑셀·구글시트 / 기획서에서 매일 하나씩 읽고, 숏츠는 주제마다 **실사** 또는 **모션그래픽** 스타일로 만듭니다.
- macOS·Windows(그리고 Docker 로 리눅스 서버)에서 동작합니다.
- 생성·저장까지만 합니다. 네이버·인스타·쓰레드에 자동 게시하지 않습니다.

> **1.1 새 기능 (2026-10)**
> - **무료로 시작**: Edge 음성(키 없음) + Pexels 무료 스톡이 기본값. 유료 서비스가 실패해도 무료 쪽으로, 끝내는 자막 영상으로라도 완성
> - **영상 품질**: 배경음악(내레이션 때 자동으로 작아짐), 장면 전환 6종, 9:16·1:1·16:9, 한글 자막 정렬("3가지" ↔ "세 가지")
> - **HTML 모션 템플릿**: 장면 하나 = HTML 파일 하나, CSS 로 디자인 추가. Remotion 은 선택 사항
> - **설치·운영**: 설치 도우미 플러그인, Docker, 비용 쓰기 전 사전 점검, 브랜드 토큰, 검수 강화
>
> 자세히: [docs/UPDATE-1.1.md](docs/UPDATE-1.1.md)

## 필요한 것

| 필수 | 비고 |
|---|---|
| [Claude Code](https://code.claude.com/docs/en/setup) | 구독 또는 API 키 |
| Python 3.10 이상 | Windows는 설치 때 "Add to PATH" 체크 |
| FFmpeg | macOS `brew install ffmpeg` / Windows `winget install Gyan.FFmpeg` |
| git | Windows는 Git for Windows(Bash 도구에 필요) |

| 선택 프로그램 | 언제 |
|---|---|
| Node.js 18+ | Remotion 엔진(선택)·Pixverse CLI 를 쓸 때만 |
| 배경음악 파일 | `assets/bgm/` 에 사용 허락된 mp3 를 넣으면 숏츠에 작게 깔림 |

## 가입·API 키 안내

### 어디에 가입해야 하나 (한눈에)

| 서비스 | 꼭 필요? | 비용 | 가입·키 받는 곳 | `.env` 에 넣을 이름 | 쓰는 곳 |
|---|---|---|---|---|---|
| **Claude** (Anthropic) | **필수** | Pro·Max 구독 또는 API 사용량 | [claude.ai](https://claude.ai) 구독 후 Claude Code 로그인 | (없음 — 로그인으로 인증) | 모든 글쓰기·조사·검수 |
| **Pexels** | **추천** (무료 경로) | 무료 | [pexels.com/api](https://www.pexels.com/api/) | `PEXELS_API_KEY` | 블로그 사진·인스타 배경·숏츠 장면/영상 |
| Pixabay | 선택 | 무료 | [pixabay.com/api/docs](https://pixabay.com/api/docs/) | `PIXABAY_API_KEY` | Pexels 에서 못 찾을 때 이어서 검색 |
| Slack | 알림 둘 중 하나 | 무료 | [api.slack.com/apps](https://api.slack.com/apps) | `SLACK_WEBHOOK_URL` | 완료·실패 알림 |
| 텔레그램 | 알림 둘 중 하나 | 무료 | 텔레그램 앱에서 [@BotFather](https://t.me/BotFather) | `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` | 완료·실패 알림 |
| Gemini (Google) | 선택 (고품질) | 유료 | [aistudio.google.com/apikey](https://aistudio.google.com/apikey) | `GEMINI_API_KEY` | AI 이미지, 음성 |
| ElevenLabs | 선택 (고품질) | 유료 | [elevenlabs.io](https://elevenlabs.io) | `ELEVENLABS_API_KEY` | 고품질 음성 |
| Pixverse | 선택 (고품질) | 유료 구독 | [pixverse.ai](https://pixverse.ai) | (없음 — `pixverse auth login`) | AI 이미지, 이미지→영상 클립, 음성 |

**가입이 필요 없는 것**: 숏츠 음성(Microsoft Edge 무료 음성), GitHub(공개 저장소라 계정 없이 내려받기 가능), 폰트(저장소에 동봉).

### 어떻게 조합하나

| 조합 | 가입할 곳 | 결과 |
|---|---|---|
| 최소 | Claude | 글·인스타·쓰레드·숏츠(음성 + 글자 카드)는 나오지만 **사진이 빠집니다** |
| **무료 추천** | Claude + Pexels + (Slack 또는 텔레그램) | 전부 나옵니다. 이미지·음성 비용 0원 |
| 고품질 | 무료 추천 + Gemini 또는 Pixverse(+ ElevenLabs) | AI 이미지·영상 클립·고품질 음성. 유료 서비스가 실패하면 무료 쪽으로 자동 대체 |

### 키 받는 법

<details>
<summary><b>Claude</b> — 필수</summary>

1. [claude.ai](https://claude.ai) 에서 Pro 또는 Max 구독 (매일 실행하려면 Max 권장)
2. [Claude Code 설치](https://code.claude.com/docs/en/setup) 후 터미널에서 `claude` 실행 → 브라우저로 로그인
3. 구독 대신 API 로 쓰려면 [console.anthropic.com](https://console.anthropic.com) 에서 크레딧을 충전하고 Claude Code 로그인 때 API 키를 고릅니다.
4. Docker 로 돌릴 때만 `.env` 에 `ANTHROPIC_API_KEY` 또는 `CLAUDE_CODE_OAUTH_TOKEN`(`claude setup-token` 으로 발급)을 넣습니다.
</details>

<details>
<summary><b>Pexels</b> — 무료, 1분</summary>

1. [pexels.com](https://www.pexels.com/ko-kr/) 오른쪽 위 **가입** (사진 사이트와 같은 계정)
2. [pexels.com/api](https://www.pexels.com/api/) → **Get Started** / **Your API Key**
3. 용도 설명(예: `Personal content automation for blog and short videos`)과 웹사이트(블로그 또는 GitHub 주소)를 적고 약관 동의
4. 바로 나오는 키를 복사 → `.env` 의 `PEXELS_API_KEY=` 뒤에 붙여 넣기

기본 한도는 시간당 200회·월 2만 회로, 하루 한 편에 충분합니다. 쓴 사진의 출처는 `images/credits.json` 에 자동으로 기록됩니다.
</details>

<details>
<summary><b>Pixabay</b> — 무료, 선택</summary>

[pixabay.com](https://pixabay.com) 가입·로그인 → [pixabay.com/api/docs](https://pixabay.com/api/docs/) 본문 중간 **Parameters** 의 `key` 항목에 내 키가 보입니다 → `PIXABAY_API_KEY=`
</details>

<details>
<summary><b>Slack 알림</b> — 무료</summary>

1. [api.slack.com/apps](https://api.slack.com/apps) → **Create New App** → **From scratch** → 앱 이름·워크스페이스 선택
2. 왼쪽 **Incoming Webhooks** → 켜기(On) → **Add New Webhook to Workspace** → 알림 받을 채널 선택
3. 생성된 **Webhook URL**(`https://hooks.slack.com` 으로 시작) 을 복사 → `SLACK_WEBHOOK_URL=`
</details>

<details>
<summary><b>텔레그램 알림</b> — 무료</summary>

1. 텔레그램에서 [@BotFather](https://t.me/BotFather) 에게 `/newbot` → 봇 이름 정하기 → 받은 토큰 → `TELEGRAM_BOT_TOKEN=`
2. 방금 만든 봇과 대화를 열어 아무 말이나 한 번 보냅니다.
3. 브라우저에서 `https://api.telegram.org/bot<토큰>/getUpdates` 를 열어 `"chat":{"id":` 뒤 숫자 → `TELEGRAM_CHAT_ID=`
</details>

<details>
<summary><b>Gemini</b> — 유료, 선택</summary>

[aistudio.google.com/apikey](https://aistudio.google.com/apikey) → **Create API key** → `GEMINI_API_KEY=`
무료 등급은 이미지 분당 한도가 0인 경우가 있어, Google Cloud 에서 **결제가 켜진 프로젝트**의 키를 권장합니다.
</details>

<details>
<summary><b>ElevenLabs</b> — 유료, 선택</summary>

[elevenlabs.io](https://elevenlabs.io) 가입 → 왼쪽 아래 프로필 또는 **Developers** → **API Keys** → **Create API key** → `ELEVENLABS_API_KEY=`
</details>

<details>
<summary><b>Pixverse</b> — 유료 구독, 선택</summary>

[pixverse.ai](https://pixverse.ai) 에서 구독 → 터미널에서 `npm install -g pixverse` → `pixverse auth login`(브라우저 로그인). `.env` 에 넣을 키는 없습니다.
</details>

### `.env` 에 넣기

```bash
cp .env.example .env      # Windows: copy .env.example .env
```

`.env` 를 메모장·에디터로 열어 받은 값만 채웁니다. 안 쓰는 줄은 비워 두면 됩니다.

```
PEXELS_API_KEY=
PIXABAY_API_KEY=
SLACK_WEBHOOK_URL=
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
GEMINI_API_KEY=
ELEVENLABS_API_KEY=
```

- 키를 **Claude 채팅창에 붙여 넣지 마세요.** `.env` 에만 넣으면 스크립트가 알아서 읽고, Claude 세션은 이 파일을 열지 않습니다.
- `.env` 는 git 에 올라가지 않습니다(`.gitignore`).
- 넣은 뒤 `python scripts/osmu.py selftest` 로 실제 연결을 확인합니다(무료 항목은 비용 없음). `--only stock` 처럼 하나만 검사할 수도 있습니다.

## 설치

### 방법 1 — Claude Code 안에서 (가장 쉬움)

아무 폴더에서 Claude Code 를 열고:

```
/plugin install osmu-studio --marketplace jkwon-startup/OSMU_studio
/osmu-studio:install
```

설치 도우미가 저장소 내려받기 → 파이썬 환경 → 도구 점검까지 해 주고, 다음에 할 일(`/osmu-setup`)을 알려 줍니다.
(Claude Code 가 오래된 버전이면 `/plugin marketplace add jkwon-startup/OSMU_studio` → `/plugin install osmu-studio@osmu-studio` 로 나눠 입력하세요.)

### 방법 2 — 터미널에서

```bash
git clone https://github.com/jkwon-startup/OSMU_studio.git
cd OSMU_studio
claude
```

Claude Code가 열리면:

```
/osmu-setup
```

설치 도우미가 순서대로 묻습니다 — 브랜드 소개(+브랜드 색) → 매일 주제를 읽을 위치(폴더 / 엑셀·구글시트 / 기획서) → 참고 계정(없으면 "없음") → **무료로 시작 / 유료 고품질** → 알림 채널. 키 값은 채팅으로 묻지 않습니다. `.env` 파일을 직접 열어 넣습니다(`.env.example` 참고).
그다음 연결 검사(`selftest`) → 테스트 1회 실행 → 산출물 확인 → 승인하면 예약 등록까지 끝냅니다.

처음 열 때 Claude Code가 `humanize-korean` 플러그인 설치를 제안하면 수락하세요(윤문 단계에 필요. 거절해도 윤문만 건너뛰고 나머지는 동작합니다).

> `uv` 를 쓰는 분은 `uv sync` 로 고정된 버전을 그대로 설치할 수 있습니다(`uv.lock`). 일반 설치는 `/osmu-setup` 이 `.venv` + `pip install -r requirements.txt` 로 알아서 합니다.

키 받는 법은 위 [가입·API 키 안내](#가입api-키-안내)를 보세요.

## 매일 무슨 일이 일어나나

1. 매시 정각에 실행기(`scripts/run/daily.py`)가 깨어나 한국시간 07:00~12:00 사이이고 오늘 아직 안 돌았으면 시작합니다. 07:00에 컴퓨터가 꺼져 있었으면 켜진 뒤 첫 정각에 따라잡습니다.
2. **사전 점검**: FFmpeg·글꼴·디스크 공간을 먼저 확인합니다. 문제가 있으면 비용을 쓰기 전에 멈추고 해결 방법을 알림으로 보냅니다.
3. 주제 소스에서 오늘 주제(와 영상 스타일: 실사/모션그래픽)를 고릅니다.
4. **조사 세션**: 리서처 3명이 병렬로 시장·트렌드·기사 / 유튜브 상위 10 / 블로그 상위 10을 조사합니다. 이 세션은 웹 도구만 쓸 수 있습니다.
5. **제작 세션**: 팀장이 전략가 → 카피라이터 → 블로그 작가 → 윤문 → [비주얼 ∥ SNS 에디터 ∥ 숏폼 PD] → 검수를 조율합니다. 이 세션은 웹 도구가 없고, 저장소 읽기·`output/` 쓰기·정해진 스크립트 실행만 할 수 있습니다.
6. `output/runs/<날짜>/`에 저장하고 알림 1건을 보냅니다. 실패하면 **어느 단계에서** 멈췄는지 함께 알려 줍니다.

```
output/runs/2026-10-25/
  topic.json  01_research/  02_persona.md  03_key_points.md  04_copy.md
  05_blog.md  06_instagram.md  07_threads.md
  images/(blog_1~5.jpg, instagram.jpg, credits.json)
  08_shorts/(script.json, narration.mp3, timing.json, plan.json, shorts.mp4, frame_sheet.jpg, seams.jpg, review.json)
  09_review.md  decisions.json  summary.json
```

알림 예: `[OSMU] 2026-10-25 완료 (6/6) 주제: … | 완료: 블로그 2,100자 · 인스타 · 쓰레드 · 이미지 6 · 숏츠 30초 | 선택: 페르소나 2번 … | 54분 · 추정 $18 | 폴더: …`

## 안 될 때 자동으로 대신하는 것

무인 실행이 중간에 멈추지 않도록, 서비스가 안 되면 더 단순한 방법으로 내려가고 그 사실을 알림·`summary.json` 에 남깁니다.

| 무엇이 안 되면 | 대신 |
|---|---|
| 설정한 음성(ElevenLabs·Gemini 등) — 키 없음·한도·결제 | 무료 Edge 음성 → 그것도 안 되면 음성 없이 자막만 있는 숏츠 |
| AI 이미지(Gemini·Pixverse) | 스톡 키가 있으면 Pexels/Pixabay 사진 |
| 숏츠 장면 이미지·클립 | 정지 이미지 → 글자 카드 |
| 모션그래픽 렌더(Chromium) | 같은 내용의 정적 카드 |
| 배경음악 파일 | 음악 없이 |
| 윤문 플러그인 | 윤문 없이 초안 사용 |

## 숏츠 꾸미기

- **비율**: `config/config.local.json` 의 `"shorts_aspect"` — `9:16`(기본, 쇼츠·릴스) / `1:1`(인스타 피드) / `16:9`(유튜브)
- **장면 전환**: `"shorts_transition"` — `fade`(기본) / `dissolve` / `slide_left` / `slide_up` / `zoom` / `cut`
- **배경음악**: `assets/bgm/` 에 사용 허락된 mp3 를 넣으면 날마다 한 곡을 골라 작게 깝니다. 내레이션이 나올 때 자동으로 더 작아집니다. 자세히: `assets/bgm/README.md`
- **목소리**: `"edge_tts_voice"` — 여성 `ko-KR-SunHiNeural`(기본) / 남성 `ko-KR-InJoonNeural`, 빠르기 `"edge_tts_rate": "+10%"`
- **브랜드 색·자막 색·글꼴**: `config/frame.local.md` 한 파일(`/osmu-setup` 이 만들어 줌, 예시는 `config/frame.example.md`)
- **모션그래픽 디자인 추가**: `templates/motion/` 에 HTML 파일 하나 = 장면 하나. CSS 만 알면 됩니다. `python scripts/osmu.py motion-preview <이름>` 으로 미리 보기. 자세히: `templates/motion/README.md`

설정을 바꾼 뒤 `python scripts/osmu.py config-show` 로 실제 적용되는 값을 확인할 수 있습니다(빠진 값은 기본값, 잘못된 값은 경고 후 기본값).

## 수동 실행과 점검

```bash
.venv/bin/python scripts/run/daily.py --now          # 지금 바로 1회 (Windows: .venv\Scripts\python)
.venv/bin/python scripts/osmu.py doctor               # 도구 점검 (업데이트 알림 포함)
.venv/bin/python scripts/osmu.py selftest             # 외부 연결 검사 (무료 항목은 비용 없음)
.venv/bin/python scripts/osmu.py config-show          # 실제 적용 설정 보기
.venv/bin/python scripts/osmu.py schedule status      # 예약 상태 / install / uninstall
.venv/bin/python scripts/osmu.py check output/runs/<날짜>   # 산출물 규격 검사
```

Claude Code 안에서 `/osmu-run run=output/runs/<날짜>` 로 제작 세션만 다시 돌릴 수 있고(끝난 단계는 건너뜀), `/osmu-style` 로 참고 계정 문체 프로파일을 다시 만들 수 있습니다.

문제가 생기면 [`docs/TROUBLESHOOTING.md`](docs/TROUBLESHOOTING.md) 를 먼저 보세요.

## 업데이트

```bash
git pull
.venv/bin/python -m pip install -r requirements.txt   # 새 패키지가 추가됐을 수 있음
.venv/bin/python scripts/osmu.py doctor
```

`doctor` 가 "새 버전" 을 알려 주면 위 순서로 업데이트하세요. 내 설정(`config/*.local.*`, `.env`)은 git 이 건드리지 않고, 새로 생긴 설정은 기본값으로 자동 채워집니다.

## Docker (리눅스 서버, 선택)

데스크톱 없이 서버에서 돌리고 싶을 때만 필요합니다. `.env` 와 `config/config.local.json` 을 준비한 뒤:

```bash
docker compose build
docker compose run --rm osmu doctor
docker compose run --rm --entrypoint python osmu scripts/run/daily.py --now
```

컨테이너 안 Claude Code 인증은 `.env` 에 `ANTHROPIC_API_KEY` 또는 `CLAUDE_CODE_OAUTH_TOKEN`(`claude setup-token` 으로 발급)을 넣습니다. 매일 실행은 서버 cron 에 등록합니다(`docker-compose.yml` 주석 참고). 윤문 플러그인은 컨테이너 안에 없으므로 윤문 단계는 건너뜁니다.

## 비용과 시간 (참고)

실측(2026-10): 조사 약 $1, 제작(글·검수) $10~15, 윤문 채널당 $1~3. **무료 경로(Edge 음성 + Pexels)는 이미지·음성 비용 0원**, 유료 서비스를 고르면 해당 요금이 추가됩니다. 한 번에 40~90분. `config.local.json` 의 `max_budget_usd` 로 Claude 비용 상한을 겁니다. 비용을 줄이려면 윤문 채널을 줄이거나(`humanize_channels`) 팀원 모델을 조정하세요(`.claude/agents/*.md` 의 `model`).

## 설계 원칙

- **조사와 제작을 다른 세션으로 분리**합니다. 웹페이지에 숨은 지시문이 셸 명령으로 이어지지 않게 하기 위해서입니다. 조사 결과는 데이터로만 다룹니다(`rules/untrusted-input.md`).
- **무인 세션 권한은 최소**입니다(`config/unattended.template.json`). `.env` 읽기, 웹 도구, curl·git·rm, 스크립트·설정·템플릿 수정은 막혀 있습니다. 설치 때 이 내용을 보여주고 동의를 받습니다.
- **키는 `.env`에만** 둡니다. 저장소에는 `.env.example`만 있고, 커밋 전 비밀값 검사가 돌며, 로그·알림에 섞인 키는 자동으로 가려집니다.
- **글자는 코드로 얹습니다.** 이미지 모델에 한글을 맡기지 않습니다(인스타 카피·숏츠 자막은 Pillow, 모션 카드는 HTML + 동봉 OFL 폰트).
- **같은 입력이면 같은 영상**: 모션 카드는 애니메이션 시점을 프레임마다 고정해 찍습니다.
- **윤문은 쓴 뒤에**, 그리고 변경률(30% 경고·50% 롤백)과 키워드·수치 보존을 코드로 다시 확인합니다.

## 문서

- `docs/UPDATE-1.1.md` — 1.1 업데이트 내용(무료 경로·영상 품질·HTML 모션·설치 도우미)과 기존 사용자 업데이트 방법
- `docs/TROUBLESHOOTING.md` — 자주 막히는 곳과 해결
- `docs/DEVELOPMENT-PLAN.md` — 설계와 결정 기록
- `rules/` — 팀원이 읽는 글쓰기·채널 규칙 (여기를 고치면 결과물이 바뀝니다)
- `templates/motion/README.md` — 모션 템플릿 만들기
- `NOTICE.md` — 제3자 자료·라이선스·참고한 오픈소스

## 알려진 제약

- 블로그 "조회수 상위 10"은 조회수가 공개되지 않아 검색 노출 순으로 대체합니다. 유튜브는 API 키가 없으면 조회수를 확인하지 못할 수 있습니다.
- 인스타그램·쓰레드 참고 계정은 로그인 벽으로 읽지 못할 수 있습니다. 그럴 때는 참고 글을 `config/references/`에 붙여넣어 주세요.
- 스톡 사진은 한국 공간이 아닐 수 있습니다. 검수 팀원이 엉뚱한 장면을 잡아내 검색어를 바꾸게 합니다.
- 무료 Edge 음성은 비공식 경로라 서비스 쪽 변경으로 멈출 수 있습니다(그때는 자막만 있는 영상으로 대체되고 알림에 표시). 상업적 이용 전 약관을 확인하세요.
- Gemini 무료 등급은 분당 한도가 0인 프로젝트가 있습니다. 결제가 켜진 프로젝트의 키를 권장합니다.
- 예약 실행은 그 시각에 컴퓨터가 켜져 있어야 합니다(잠자기는 깨웁니다).
- Remotion 엔진(선택)을 켜면 4인 이상 조직은 Remotion Company License 가 필요합니다. 기본 HTML 엔진은 제약이 없습니다.
