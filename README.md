# OSMU Studio

주제 하나를 **매일 아침 7시(한국시간)에 자동으로** 블로그 글 → 이미지 5장 → 인스타그램 피드 → 쓰레드 → 30초 숏츠 영상으로 바꿔 주고, 끝나면 Slack 또는 텔레그램으로 알려 주는 Claude Code 콘텐츠 팀입니다.

- 팀장 1명(메인 세션)과 팀원 8명(서브에이전트)이 리서치 → 페르소나 → 핵심내용 5가지 → 후킹 카피 → 블로그 → 윤문 → 이미지 · SNS · 숏츠 → 검수 순으로 일합니다.
- 글은 한국 시장 페르소나 방법론, 네이버 상위노출(C-Rank·DIA·스마트블록)과 SGE(E-E-A-T) 규칙, 친구 톤 카피 규칙을 따릅니다. 작성 뒤에는 [humanize-korean](https://github.com/epoko77-ai/im-not-ai) 플러그인으로 AI 티를 뺍니다.
- macOS와 Windows에서 동작합니다. 영상도 두 OS 모두에서 만들어집니다.
- 생성·저장까지만 합니다. 네이버·인스타·쓰레드에 자동 게시하지 않습니다.

## 필요한 것

| 필수 | 비고 |
|---|---|
| [Claude Code](https://code.claude.com/docs/en/setup) | 구독 또는 API 키 |
| Python 3.10 이상 | Windows는 설치 때 "Add to PATH" 체크 |
| FFmpeg | macOS `brew install ffmpeg` / Windows `winget install Gyan.FFmpeg` |
| git | Windows는 Git for Windows(Bash 도구에 필요) |

| 선택 | 용도 |
|---|---|
| Node.js 18+ | 모션그래픽 숏츠(Remotion). 없으면 정적 카드로 대체 |
| Pixverse 구독 **또는** Gemini API 키 | 이미지·영상 클립 생성 (설치 때 선택) |
| ElevenLabs 키 **또는** Gemini API 키 **또는** Pixverse | 숏츠 음성 |
| Slack Incoming Webhook **또는** 텔레그램 봇 | 완료 알림 |
| YouTube Data API 키 | 유튜브 리서치를 조회수 기준으로 (없으면 웹 검색) |

## 설치 (3단계)

```bash
git clone https://github.com/jkwon-startup/OSMU_studio.git
cd OSMU_studio
claude
```

Claude Code가 열리면:

```
/osmu-setup
```

설치 도우미가 순서대로 묻습니다 — 브랜드 소개 → 매일 주제를 읽을 위치(폴더 / 엑셀·구글시트 / 기획서) → 참고 계정(없으면 "없음") → 이미지·음성 서비스 → 알림 채널. 키 값은 채팅으로 묻지 않습니다. `.env` 파일을 직접 열어 넣습니다(`.env.example` 참고).
그다음 연결 검사(`selftest`) → 테스트 1회 실행 → 산출물 확인 → 승인하면 예약 등록까지 끝냅니다.

처음 열 때 Claude Code가 `humanize-korean` 플러그인 설치를 제안하면 수락하세요(윤문 단계에 필요. 거절해도 윤문만 건너뛰고 나머지는 동작합니다).

## 매일 무슨 일이 일어나나

1. 매시 정각에 실행기(`scripts/run/daily.py`)가 깨어나 한국시간 07:00~12:00 사이이고 오늘 아직 안 돌았으면 시작합니다. 07:00에 컴퓨터가 꺼져 있었으면 켜진 뒤 첫 정각에 따라잡습니다.
2. 주제 소스에서 오늘 주제(와 영상 스타일: 실사/모션그래픽)를 고릅니다.
3. **조사 세션**: 리서처 3명이 병렬로 시장·트렌드·기사 / 유튜브 상위 10 / 블로그 상위 10을 조사합니다. 이 세션은 웹 도구만 쓸 수 있습니다.
4. **제작 세션**: 팀장이 전략가 → 카피라이터 → 블로그 작가 → 윤문 → [비주얼 ∥ SNS 에디터 ∥ 숏폼 PD] → 검수를 조율합니다. 이 세션은 웹 도구가 없고, 저장소 읽기·`output/` 쓰기·정해진 스크립트 실행만 할 수 있습니다.
5. `output/runs/<날짜>/`에 저장하고 알림 1건을 보냅니다.

```
output/runs/2026-10-04/
  topic.json  01_research/  02_persona.md  03_key_points.md  04_copy.md
  05_blog.md  06_instagram.md  07_threads.md  images/(blog_1~5.jpg, instagram.jpg)
  08_shorts/(script.json, narration.mp3, shorts.mp4, frame_sheet.jpg)
  09_review.md  decisions.json  summary.json
```

알림 예: `[OSMU] 2026-10-04 완료 (6/6) 주제: … | 완료: 블로그 2,100자 · 인스타 · 쓰레드 · 이미지 6 · 숏츠 30초 | 선택: 페르소나 2번 … | 54분 · 추정 $18 | 폴더: …`

## 수동 실행과 점검

```bash
.venv/bin/python scripts/run/daily.py --now          # 지금 바로 1회 (Windows: .venv\Scripts\python)
.venv/bin/python scripts/osmu.py doctor               # 도구 점검
.venv/bin/python scripts/osmu.py selftest             # 외부 연결 검사 (소액 비용)
.venv/bin/python scripts/osmu.py schedule status      # 예약 상태 / install / uninstall
.venv/bin/python scripts/osmu.py check output/runs/<날짜>   # 산출물 규격 검사
```

Claude Code 안에서 `/osmu-run run=output/runs/<날짜>` 로 제작 세션만 다시 돌릴 수 있고(끝난 단계는 건너뜀), `/osmu-style` 로 참고 계정 문체 프로파일을 다시 만들 수 있습니다.

## 비용과 시간 (참고)

실측(2026-10): 조사 약 $1, 제작(글·검수) $10~15, 윤문 채널당 $1~3, 이미지·음성은 서비스 요금 별도. 한 번에 40~90분. `config.local.json` 의 `max_budget_usd` 로 상한을 겁니다. 비용을 줄이려면 윤문 채널을 줄이거나(`humanize_channels`) 팀원 모델을 조정하세요(`.claude/agents/*.md` 의 `model`).

## 설계 원칙

- **조사와 제작을 다른 세션으로 분리**합니다. 웹페이지에 숨은 지시문이 셸 명령으로 이어지지 않게 하기 위해서입니다. 조사 결과는 데이터로만 다룹니다(`rules/untrusted-input.md`).
- **무인 세션 권한은 최소**입니다(`config/unattended.template.json`). `.env` 읽기, 웹 도구, curl·git·rm, 스크립트·설정 수정은 막혀 있습니다. 설치 때 이 내용을 보여주고 동의를 받습니다.
- **키는 `.env`에만** 둡니다. 저장소에는 `.env.example`만 있고, 커밋 전 비밀값 검사가 돕니다.
- **글자는 코드로 얹습니다.** 이미지 모델에 한글을 맡기지 않습니다(인스타 카피·숏츠 자막은 Pillow + 동봉 OFL 폰트).
- **윤문은 쓴 뒤에**, 그리고 변경률(30% 경고·50% 롤백)과 키워드·수치 보존을 코드로 다시 확인합니다.

## 문서

- `docs/DEVELOPMENT-PLAN.md` — 설계와 결정 기록
- `rules/` — 팀원이 읽는 글쓰기·채널 규칙 (여기를 고치면 결과물이 바뀝니다)
- `NOTICE.md` — 제3자 자료·라이선스

## 알려진 제약

- 블로그 "조회수 상위 10"은 조회수가 공개되지 않아 검색 노출 순으로 대체합니다. 유튜브는 API 키가 없으면 조회수를 확인하지 못할 수 있습니다.
- 인스타그램·쓰레드 참고 계정은 로그인 벽으로 읽지 못할 수 있습니다. 그럴 때는 참고 글을 `config/references/`에 붙여넣어 주세요.
- Gemini 무료 등급은 분당 한도가 0인 프로젝트가 있습니다. 결제가 켜진 프로젝트의 키를 권장합니다.
- 예약 실행은 그 시각에 컴퓨터가 켜져 있어야 합니다(잠자기는 깨웁니다).
- Remotion은 개인·3인 이하 팀 무료, 그 이상 조직은 Company License가 필요합니다.
