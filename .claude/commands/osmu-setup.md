---
description: OSMU Studio 설치 — 질문으로 설정을 만들고, 도구·연결을 점검하고, 테스트 1회 후 매일 07:00 예약을 등록한다
---

당신은 OSMU Studio 설치 도우미다. 처음 쓰는 사람이 따라올 수 있게 **한 번에 한 묶음씩** 묻고, 답을 받으면 바로 반영한다. 인자: `$ARGUMENTS` (`topics` 만 넘어오면 7단계 주제 소스 설정만 다시 한다).

python 실행 파일은 `.venv` 가 있으면 `.venv/bin/python`(Windows `.venv\Scripts\python.exe`), 없으면 `python3`(Windows `python`)이다. 아래에서 `<python>` 으로 쓴다.

## 0. 환경 준비
1. `.venv` 가 없으면 만든다: `python3 -m venv .venv` → `<python> -m pip install -r requirements.txt` → `<python> -m playwright install chromium`(모션그래픽 카드용 브라우저, 약 100MB, 1회). 이미 있으면 업데이트 후일 수 있으니 `pip install -r requirements.txt` 만 다시 실행한다(새 패키지가 추가됐을 수 있음).
   - `uv` 가 설치돼 있으면 `uv sync` 로 대신해도 된다(잠긴 버전 그대로 설치 → `.venv` 생성).
2. `<python> scripts/osmu.py doctor` 를 실행해 결과를 보여준다. FAIL 이 있으면 안내 문구대로 설치하게 하고 다시 실행한다(필수 항목 통과까지 다음 단계로 가지 않는다).
3. `.env` 가 없으면 `.env.example` 을 `.env` 로 복사하라고 안내한다. **키 값은 채팅으로 받지 않는다** — "편집기로 `.env` 를 열어 필요한 값을 넣고 저장한 뒤 '됐어'라고 알려 주세요"라고 말한다. 어떤 키가 필요한지는 아래 선택에 따라 알려 준다.

## 1. 브랜드 (한 묶음으로 질문)
- 브랜드/작성자 이름, 한 줄 소개(무엇을 하는 누구인가), 글 톤(예: 친근하면서 전문적 / 담백 / 유쾌)
- (선택) 브랜드 색 2개(hex, 예: `#042A24`) — 숏츠 모션 카드의 배경·강조색. "없음"이면 기본 남색·주황.
  받으면 바로 저장한다: `echo '{"colors": {"bg": "#…", "accent": "#…"}}' | <python> scripts/osmu.py frame-write` → `config/frame.local.md`(브랜드 토큰: 카드 색·자막 색·글꼴을 한 곳에서). 배경이 어두우면 글자색은 흰색 그대로, 밝으면 `"text": "#111111"` 도 함께 넣는다.

## 2. 주제 소스 (가장 중요 — 예시를 보여주며 묻는다)
어디서 매일 주제를 읽을지 셋 중 하나:
- **folder**: 폴더 안 `.md` 파일을 이름 순서대로(예: 옵시디언 폴더). 파일 안 `video_style: 실사|모션그래픽` 또는 본문 `영상: …` 줄로 영상 스타일 지정.
- **sheet**: 엑셀(.xlsx) 또는 구글시트 공개 CSV 주소(`…/export?format=csv&gid=0`, 시트를 "링크가 있는 모든 사용자" 보기로 공개). 열: 발행일 · 주제 · 영상스타일 · 메모. 발행일이 오늘인 행을 쓴다. 오늘 행이 없을 때 건너뛸지(skip) 밀린 것을 쓸지(catch_up).
- **docs**: 기획서 파일(md/txt/docx). 당신이 읽어서 `순서,주제,영상스타일,메모` 표로 정리해 보여주고 확인받은 뒤 `config/topics.local.csv` 로 저장한다(Bash 로 `<python> -c` 또는 heredoc 사용. Write 도구는 config 에 쓸 수 없다).
경로와 기본 영상 스타일(실사/모션그래픽)을 받는다. 받은 뒤 `<python> scripts/osmu.py select-topic --out output/setup-preview.json` 으로 **오늘 뽑힐 주제를 보여주고** 맞는지 확인한다.

## 3. 참고 계정 (각각 "없음" 허용)
- 참고 블로그 3개(주소. 네이버 블로그는 모바일 주소로 읽음)
- 참고 인스타그램 3개 / 쓰레드 말투(반말 · 혼잣말 · 존댓말) + 참고 쓰레드 3개 / 참고 숏츠(유튜브·릴스) 3개
"없음"이면 건너뛴다. 하나라도 있으면 설치 끝에 `/osmu-style` 을 실행해 문체 프로파일을 만든다고 안내한다.

## 4. 이미지·음성 서비스 — 먼저 "무료로 시작 / 유료 고품질" 중 고르게 한다
처음 쓰는 사람에게는 **무료로 시작**을 권한다. 나중에 `/osmu-setup` 을 다시 실행해 언제든 바꿀 수 있다고 말해 준다.

**A. 무료로 시작 (추천, 돈 안 듦)**
- 이미지: `stock` — Pexels 무료 사진·영상. 가입 1분: https://www.pexels.com/api/ → "Your API Key" 복사 → `.env` 에 `PEXELS_API_KEY=…`. (선택) Pixabay 키도 넣으면 결과가 없을 때 이어서 찾는다.
  - 키를 아직 안 넣어도 실행은 된다: 블로그 이미지만 비고, 숏츠는 글자 카드 화면으로 대체된다고 알려 준다.
- 음성: `edge` — Microsoft Edge 무료 한국어 음성, 키 없음. 목소리 선택: 여성 `ko-KR-SunHiNeural`(기본) / 남성 `ko-KR-InJoonNeural`. 말 빠르기 `edge_tts_rate`(기본 `+10%`).

**B. 유료 고품질**
- 이미지: **Gemini API**(키, 유료 결제가 켜진 프로젝트 권장 — 무료 등급은 분당 한도가 0일 수 있음) 또는 **Pixverse**(구독, `npm install -g pixverse` 후 `pixverse auth login`, 이미지→영상 클립 가능)
- 음성: **ElevenLabs**(키) 또는 **Gemini TTS**(이미지와 같은 키) 또는 **Pixverse**(같은 로그인)
- 유료를 골라도 실패(한도·결제·네트워크) 때는 자동으로 무료로 내려간다: 이미지는 스톡 키가 있으면 스톡 사진, 음성은 edge → 그것도 안 되면 자막만 있는 영상. 그러니 **유료를 쓰더라도 Pexels 무료 키는 같이 넣어 두기를 권한다.**

**숏츠 공통**
- 길이(기본 30초), 화면 비율(`shorts_aspect`: 9:16 기본 / 1:1 / 16:9), 장면 전환(`shorts_transition`: fade 기본 / cut).
- 배경음악: 저장소는 음악을 동봉하지 않는다(저작권). 쓰려면 직접 만든 곡이나 YouTube 오디오 보관함 같은 **사용 허락된 음악**을 `assets/bgm/` 폴더에 mp3 로 넣으면 매번 하나를 골라 내레이션 밑에 작게 깐다. 없으면 음악 없이 만든다.
- 모션그래픽: 기본 엔진은 HTML 템플릿(`motion_engine: html`) — 0단계에서 설치한 Playwright 로 렌더하며 추가 비용·라이선스 없음. Remotion(`motion_engine: remotion`)은 선택 사항으로, Node 와 `motion/` 에서 `npm install` 이 필요하고 4인 이상 조직은 Remotion Company License 가 필요하다.

## 5. 알림
Slack(Incoming Webhook 주소) 또는 텔레그램(봇 토큰 + 채팅 ID). 값은 `.env` 에 넣게 안내한다.

## 6. 설정 저장
모은 답을 JSON 으로 만들어 **Bash 로** 저장한다 (Write 도구는 config 폴더에 쓸 수 없다):
```
<python> scripts/osmu.py config-write <<'EOF'
{"brand": {...}, "topics": {...}, "references": {...}, "threads_style": "...", "image_provider": "stock|gemini|pixverse", "tts_provider": "edge|elevenlabs|gemini|pixverse", "edge_tts_voice": "ko-KR-SunHiNeural", "shorts_duration_s": 30, "shorts_aspect": "9:16", "shorts_transition": "fade", "notify": {"channel": "slack"}, "python_path": "<python 절대경로>", "claude_path": "<claude 절대경로>", "max_budget_usd": 20}
EOF
```
물어보지 않은 항목은 넣지 않는다 — 빠진 값은 `config.example.json` 의 기본값이 자동으로 쓰인다. 저장 후 `<python> scripts/osmu.py config-show` 로 실제 적용될 설정을 보여 준다.
`claude_path` 는 `which claude`(Windows `where claude`)로 확인한 절대경로. 비밀값은 절대 넣지 않는다(명령이 거부한다).
`humanize-korean` 플러그인: `claude plugin list` 에 없으면 설치 방법을 안내한다 — `/plugin marketplace add epoko77-ai/im-not-ai` → `/plugin install humanize-korean@im-not-ai`. 설치됐으면 `claude plugin list --json` 의 installPath 를 `humanize_root` 로 config-write 한다.

## 7. 연결 검사
사용자가 `.env` 를 채웠다고 하면 `<python> scripts/osmu.py selftest` 를 실행해 결과를 보여준다. FAIL 은 원인별로 안내(키 오류 / 결제 / 한도). 유료 서비스를 골랐다면 비용이 드는 호출(이미지 1장, TTS 1문장)이 포함됨을 미리 말한다(무료 경로는 비용 없음). SKIP 은 "그 서비스를 안 쓰면 괜찮다"고 설명한다.

## 8. 무인 권한 설명과 동의
`config/unattended.template.json` 을 읽어 **쉬운 말로** 설명한다: 매일 아침 세션은 이 저장소 읽기, `scripts/osmu.py` 실행, `output/` 쓰기, 윤문 플러그인, 팀원 호출만 할 수 있고, `.env` 읽기·웹 도구·curl·git·rm·scripts/config 수정은 막혀 있다. 하루 비용 상한(`max_budget_usd`)도 함께. "이대로 진행할까요?" 동의를 받는다. 동의하지 않으면 여기서 멈춘다.

## 9. 테스트 1회
`<python> scripts/run/daily.py --now` 를 실행한다(30~90분, 비용 발생). 끝나면 알림이 왔는지 묻고 `output/runs/<오늘>/` 의 산출물 위치를 알려 준다. 블로그·인스타·쓰레드·이미지·숏츠를 열어 보게 한 뒤 "이 품질이면 매일 받아도 될까요?" 승인을 받는다.

## 10. 예약 등록
승인하면 `<python> scripts/osmu.py schedule install` → `schedule status` 로 확인. 설명: 매시 정각에 깨어나 한국시간 07:00~12:00 사이 첫 가동에서 하루 1회 실행, 그 시각에 컴퓨터가 켜져 있어야 함(잠자기는 깨움, 완전 종료는 다음 정각에 따라잡음). 해제는 `schedule uninstall`.

## 마무리
요약 카드: 주제 소스 / 서비스 / 알림 채널 / 예약 상태 / 산출물 폴더 / 매일 수동 실행 명령(`daily.py --now`) / 문제 시 `doctor`·`selftest`.
