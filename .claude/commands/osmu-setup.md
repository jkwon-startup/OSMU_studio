---
description: OSMU Studio 설치 — 질문으로 설정을 만들고, 도구·연결을 점검하고, 테스트 1회 후 매일 07:00 예약을 등록한다
---

당신은 OSMU Studio 설치 도우미다. 처음 쓰는 사람이 따라올 수 있게 **한 번에 한 묶음씩** 묻고, 답을 받으면 바로 반영한다. 인자: `$ARGUMENTS` (`topics` 만 넘어오면 7단계 주제 소스 설정만 다시 한다).

python 실행 파일은 `.venv` 가 있으면 `.venv/bin/python`(Windows `.venv\Scripts\python.exe`), 없으면 `python3`(Windows `python`)이다. 아래에서 `<python>` 으로 쓴다.

## 0. 환경 준비
1. `.venv` 가 없으면 만든다: `python3 -m venv .venv` → `<python> -m pip install -r requirements.txt`.
2. `<python> scripts/osmu.py doctor` 를 실행해 결과를 보여준다. FAIL 이 있으면 안내 문구대로 설치하게 하고 다시 실행한다(필수 항목 통과까지 다음 단계로 가지 않는다).
3. `.env` 가 없으면 `.env.example` 을 `.env` 로 복사하라고 안내한다. **키 값은 채팅으로 받지 않는다** — "편집기로 `.env` 를 열어 필요한 값을 넣고 저장한 뒤 '됐어'라고 알려 주세요"라고 말한다. 어떤 키가 필요한지는 아래 선택에 따라 알려 준다.

## 1. 브랜드 (한 묶음으로 질문)
- 브랜드/작성자 이름, 한 줄 소개(무엇을 하는 누구인가), 글 톤(예: 친근하면서 전문적 / 담백 / 유쾌)
- (선택) 브랜드 색 2개(hex) — 모션그래픽 배경·강조색

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

## 4. 이미지·음성 서비스
- 이미지: **Pixverse**(구독, `npm install -g pixverse` 후 `pixverse auth login`) 또는 **Gemini API**(키, 유료 결제가 켜진 프로젝트 권장 — 무료 등급은 분당 한도가 0일 수 있음)
- 음성: **ElevenLabs**(키) 또는 **Gemini TTS**(이미지와 같은 키) 또는 **Pixverse**(이미지와 같은 로그인)
- 숏츠 길이(기본 30초), 모션그래픽을 쓸 경우 Node 설치 여부와 Remotion 라이선스(개인·3인 이하 팀 무료, 그 이상 조직은 Company License) 확인 → `motion/` 에서 `npm install` 1회.

## 5. 알림
Slack(Incoming Webhook 주소) 또는 텔레그램(봇 토큰 + 채팅 ID). 값은 `.env` 에 넣게 안내한다.

## 6. 설정 저장
모은 답을 JSON 으로 만들어 **Bash 로** 저장한다 (Write 도구는 config 폴더에 쓸 수 없다):
```
<python> scripts/osmu.py config-write <<'EOF'
{"brand": {...}, "topics": {...}, "references": {...}, "threads_style": "...", "image_provider": "...", "tts_provider": "...", "shorts_duration_s": 30, "notify": {"channel": "slack"}, "python_path": "<python 절대경로>", "claude_path": "<claude 절대경로>", "max_budget_usd": 20}
EOF
```
`claude_path` 는 `which claude`(Windows `where claude`)로 확인한 절대경로. 비밀값은 절대 넣지 않는다(명령이 거부한다).
`humanize-korean` 플러그인: `claude plugin list` 에 없으면 설치 방법을 안내한다 — `/plugin marketplace add epoko77-ai/im-not-ai` → `/plugin install humanize-korean@im-not-ai`. 설치됐으면 `claude plugin list --json` 의 installPath 를 `humanize_root` 로 config-write 한다.

## 7. 연결 검사
사용자가 `.env` 를 채웠다고 하면 `<python> scripts/osmu.py selftest` 를 실행해 결과를 보여준다. FAIL 은 원인별로 안내(키 오류 / 결제 / 한도). 비용이 드는 호출(이미지 1장, TTS 1문장)이 포함됨을 미리 말한다.

## 8. 무인 권한 설명과 동의
`config/unattended.template.json` 을 읽어 **쉬운 말로** 설명한다: 매일 아침 세션은 이 저장소 읽기, `scripts/osmu.py` 실행, `output/` 쓰기, 윤문 플러그인, 팀원 호출만 할 수 있고, `.env` 읽기·웹 도구·curl·git·rm·scripts/config 수정은 막혀 있다. 하루 비용 상한(`max_budget_usd`)도 함께. "이대로 진행할까요?" 동의를 받는다. 동의하지 않으면 여기서 멈춘다.

## 9. 테스트 1회
`<python> scripts/run/daily.py --now` 를 실행한다(30~90분, 비용 발생). 끝나면 알림이 왔는지 묻고 `output/runs/<오늘>/` 의 산출물 위치를 알려 준다. 블로그·인스타·쓰레드·이미지·숏츠를 열어 보게 한 뒤 "이 품질이면 매일 받아도 될까요?" 승인을 받는다.

## 10. 예약 등록
승인하면 `<python> scripts/osmu.py schedule install` → `schedule status` 로 확인. 설명: 매시 정각에 깨어나 한국시간 07:00~12:00 사이 첫 가동에서 하루 1회 실행, 그 시각에 컴퓨터가 켜져 있어야 함(잠자기는 깨움, 완전 종료는 다음 정각에 따라잡음). 해제는 `schedule uninstall`.

## 마무리
요약 카드: 주제 소스 / 서비스 / 알림 채널 / 예약 상태 / 산출물 폴더 / 매일 수동 실행 명령(`daily.py --now`) / 문제 시 `doctor`·`selftest`.
