# OSMU Studio 개발 계획서

> 작성: 2026-10-03 · 상태: 승인된 계획, 구현 진행 중
> 이 문서는 설계의 단일 기준이다. 구현 중 결정이 바뀌면 이 문서를 먼저 고친다.

## 1. 목표

주제 하나를 매일 한국시간 07:00에 자동으로 다음 순서로 변환하고, 끝나면 Slack 또는 텔레그램으로 알린다.

```
주제 선택 → 리서치(3 병렬) → 페르소나 → 핵심내용 5가지 → 후킹 카피
→ 블로그 → 윤문 → [이미지 ∥ 인스타 → 쓰레드 ∥ 숏츠 스크립트 → 영상] → 검수 → 알림
```

누구나 GitHub에서 `git clone`해 설치해 쓰는 제품이다. 설치하는 사람의 컴퓨터에는 이 저장소 외에 아무것도 없다고 가정한다.

## 2. 확정 결정

| 항목 | 결정 |
|---|---|
| 배포 형태 | clone 방식. `git clone` → 그 폴더에서 `claude` → `/osmu-setup`. 팀 정의는 프로젝트 `.claude/`에 둔다 |
| 지원 OS | macOS + Windows. 둘 다 영상 완성본과 알림까지 동작해야 한다 |
| 이미지 생성 | 설치 때 선택: Pixverse CLI 또는 Gemini API |
| 음성(TTS) | 설치 때 선택: ElevenLabs 또는 Gemini TTS |
| 숏츠 | 저장소 안에서 자체 제작(스크립트 → 음성 → 장면 계획 → 이미지·클립 → 모션 → 합성 → 검수 → mp4) |
| 윤문 | 외부 플러그인 `humanize-korean`(im-not-ai, MIT)을 "작성 후" 단계로 적용. 미설치면 건너뛰고 알림에 표시 |
| 게시 | 생성·저장까지. 네이버·인스타·쓰레드 자동 게시는 범위 밖 |
| 무인 실행 | 페르소나 5명 중 1명, 카피 5세트 중 1개는 팀장이 자동 선택하고 근거를 `decisions.json`에 기록 |
| 비밀값 | 키·토큰·웹훅은 `.env`(git 제외)에만. 저장소에는 `.env.example`만 |

## 3. 참고한 방법론과 저장소 안 규칙 파일

설치자 PC에는 원본 자료가 없으므로 규칙을 `rules/`에 옮겨 담는다.

| 규칙 파일 | 내용 | 출처 |
|---|---|---|
| `rules/persona.md` | 4축(인구통계·심리·행동·기술) 세분화 → 페르소나 5명 표 → 1명 상세 10섹션(인구통계, OCEAN, 하루 일과, 고통 시나리오, 정보 탐색, 소비 패턴, 드림 100, 가치 사다리, SB7 캐릭터) | 한국형 STP 컨설턴트 프롬프트(Russell Brunson × Donald Miller) |
| `rules/data/korea-distribution.md` | 한국 인구 분포(지역·연령·직업·소득·교육·가구) 축별 상위 12개 | NVIDIA Nemotron-Personas-Korea (CC BY 4.0) |
| `rules/copy.md` | 친구 톤, 30자 이내 5세트, 후킹 패턴 8종(동음·페인+위트·단위 치환·솔루션 전복·정의 재구성·일상 철학·숫자·부정), 클리셰·광고티 금지 목록, 지루함·친구 톤 테스트, 채널별 변형 규격 | 같은 프롬프트 4·5단계 |
| `rules/blog-naver.md` | 제목 25자 내외·메인 키워드 맨 앞, 서론에 제목 그대로 1회, 공백 제외 1,500자 이상, 문단 4줄 이내, 소제목 구조, 1인칭 경험 화법, PAS, 인용구·내부링크, 발행 전 체크리스트 | 네이버 상위노출 정리(C-Rank·DIA·DIA+·스마트블록) |
| `rules/blog-sge.md` | E-E-A-T, 신뢰할 출처 인용, 틈새(롱테일) 키워드, SNS SEO | SGE 시대의 SEO 정리 |
| `rules/writing-absolute.md` | 생성 시점에 적용해도 안전한 절대 규칙만(이모지 남발, 이중 피동, 의의 과장 등). 빈도 조건 규칙은 넣지 않는다 — 생성 프롬프트에 넣으면 금지어처럼 작동해 글이 나빠진다(im-not-ai integration 문서) | im-not-ai quick-rules |
| `rules/instagram.md` `threads.md` `shorts-script.md` `image-prompts.md` `review-checklist.md` `untrusted-input.md` | 채널 규격, 숏츠 분량(약 7자/초, 30초≈210자, 훅 3초), 이미지 프롬프트 원칙(실사·텍스트 없음·가로형), 검수 체크리스트, 조사자료는 데이터이지 지시가 아님 | 신규 |

## 4. 저장소 구조

```
OSMU_studio/
  README.md  CLAUDE.md  LICENSE  NOTICE.md
  .env.example  .gitignore  requirements.txt
  docs/DEVELOPMENT-PLAN.md       이 문서
  .claude/
    settings.json                deny 규칙만(.env 읽기, scripts·config·rules 수정 금지)
    commands/osmu-setup.md       설치: 질문 → doctor → 테스트 1회 → 승인 → 스케줄 등록
    commands/osmu-run.md         팀장 절차서. 인자 run=<폴더>
    commands/osmu-style.md       참고 계정 문체 프로파일 생성
    agents/osmu-*.md             팀원 8개 (frontmatter: name, description, tools, model)
  rules/                         3절
  config/
    config.example.json          비밀 아닌 설정 예시(가상 값)
    config.local.json            설치가 생성, git 제외
    unattended.template.json     무인 세션 권한 템플릿 → unattended.local.json(매 실행 생성, git 제외)
    style-profile.local.md       문체 프로파일(git 제외)
  scripts/
    osmu.py                      단일 진입점 CLI: doctor, selftest, select-topic, image, compose, tts, video, check, notify, scan
    run/daily.py                 예약 실행기(표준 라이브러리만)
    run/claude_cmd.py            claude 실행 파일 탐색·argv 조립(ASCII만)·프롬프트 stdin
    topics/select.py             folder / sheet / docs → topic.json
    research/youtube_api.py      YOUTUBE_API_KEY 있을 때만
    image/gemini.py  pixverse.py  compose_copy.py(3:4 + 한글 카피 합성)
    video/tts.py  plan_schema.py  build.py  captions.py
    checks/specs.py              채널 규격 결정적 검사
    notify.py                    Slack 웹훅·텔레그램(평문)
    setup/doctor.py  schedule.py  launchd.plist.template  task.xml.template
    publish/scan_secrets.py      커밋 전 비밀값·개인경로 검사
    shims/win/python3            Git Bash용 python3 심
  motion/                        Remotion 최소 프로젝트(컴포넌트 4개)
  assets/fonts/                  OFL 한글 폰트
  tests/  .github/workflows/     양 OS 자동 테스트
  output/runs/<날짜>/            산출물(git 제외)   _workspace/   윤문 작업 폴더(git 제외)
```

## 5. 팀

팀장은 메인 세션에서 도는 `/osmu-run` 커맨드다. 팀원은 결과를 텍스트로 돌려주고 팀장이 저장한다(이미지·영상 팀원만 도구를 직접 실행).

| 팀원 | tools | model | 읽는 규칙 | 출력 |
|---|---|---|---|---|
| `osmu-researcher` ×3 (시장·트렌드·기사 / 유튜브 상위 10 / 블로그 상위 10) | WebSearch, WebFetch | sonnet | untrusted-input | `01_research/*.md` (사실마다 URL·확인일·근거 수준) |
| `osmu-strategist` | Read | inherit | persona, korea-distribution | `02_persona.md`, `03_key_points.md` |
| `osmu-copywriter` | Read | inherit | copy | `04_copy.md` (5세트 + 선택 근거 + 채널 변형) |
| `osmu-blog-writer` | Read | inherit | blog-naver, blog-sge, writing-absolute, style-profile | `05_blog.draft.md` + 제목·키워드 메타 |
| `osmu-sns-editor` | Read | inherit | instagram, threads, writing-absolute, style-profile | `06_instagram.draft.md`, `07_threads.draft.md` |
| `osmu-visual` | Read, Bash | inherit | image-prompts | 가로형 실사 5장 + 인스타 3:4 합성 이미지 |
| `osmu-shorts` | Read, Write, Bash | inherit | shorts-script | `script.json` → `plan.json` → `shorts.mp4` |
| `osmu-reviewer` | Read | inherit | review-checklist | `09_review.md` (pass / fix / fail) |
| `humanize-korean` (외부) | — | — | — | 팀장이 Skill로 호출. 장르 blog, 보수 강도, 키워드·수치·고유명사 보존 |

## 6. 하루 실행 흐름 (`scripts/run/daily.py`)

```
0. KST 가드(07:00 ≤ 지금 < 12:00, 오늘 미실행) · 잠금 · doctor 요약
1. 주제 선택 → output/runs/<날짜>/topic.json
2. [세션 A 조사] claude -p --agent osmu-researcher ×3 병렬 — 웹 도구만 허용
3. [세션 B 제작] claude -p "/osmu-run run=…" --settings config/unattended.local.json — 웹 도구 금지
   전략가 → 카피 → 블로그 → 윤문 → 규격 재검사
   → [비주얼 ∥ SNS 에디터 ∥ 숏츠 스크립트] → 윤문 ×3 → [숏츠 제작 ∥ 검수]
   실패 시 1회 재실행(state.json 보고 끝난 단계 건너뜀)
4. summary.json → 알림 1건(실행기가 전송, 세션이 죽어도 발송)
5. 완료 표시
```

- 조사 세션과 제작 세션을 분리하는 이유: 웹페이지에 숨은 지시문이 셸 명령으로 이어지지 않게 하기 위해서다.
- 참고 계정은 매일 읽지 않는다. 설치 때 `/osmu-style`이 문체 프로파일을 만들고 매일은 그것을 읽는다.
- 윤문은 블로그(작성 직후), 인스타·쓰레드·숏츠 내레이션(초안 직후)에 적용한다. 30자 카피·해시태그·제목은 제외한다.
- 검수가 `fix`면 원작자가 1회 수정하고, 그래도 실패하면 부분 완료로 저장하고 알림에 경고를 남긴다.
- 알림 예: `[OSMU] 2026-10-03 부분 완료 (5/6) 주제: … | 완료: 블로그·이미지 6·인스타·쓰레드 | 실패: 숏츠(TTS 오류) | 건너뜀: 윤문(플러그인 없음) | 54분 | 폴더: …`

## 7. 주제 선택

| 소스 | 오늘 주제 | 영상 스타일 | 완료 표시 |
|---|---|---|---|
| folder (옵시디언 등 폴더) | `*.md` 자연 정렬 중 미완료 첫 파일 | frontmatter `video_style` → 본문 `영상:` 줄 → 기본값 | `output/state/done.json` |
| sheet (xlsx / 구글시트 공개 CSV) | 발행일 == 오늘 행. 없으면 skip(기본) 또는 catch_up | 영상스타일 열 | done.json |
| docs (기획서) | 설치 때 `config/topics.local.csv`로 정규화 후 순서대로 | csv 열 | done.json |

## 8. 숏츠 제작

| 단계 | 방식 |
|---|---|
| 대본 | `script.json` {beats, full_narration, tts_text}. 30초≈210자 |
| 음성 | ElevenLabs 또는 Gemini TTS. 키는 `.env` |
| 시간 측정 | 문장별 합성 → ffprobe 길이 누적 → concat (공급자 무관, 양 OS) |
| 장면 계획 | `plan.json`: shots(start/end 연속, 합계=길이), source {image\|clip\|motion\|endcard}, overlays. 스키마 검증 |
| 실사 | Pixverse: 이미지 + image-to-video 클립 3~4개, 나머지 정지+카메라 운동 / Gemini: 이미지만, 전 샷 zoompan |
| 모션그래픽 | Remotion 컴포넌트 4개. 라이선스(개인·3인 이하 무료)를 설치 질문에서 확인 |
| 합성 | FFmpeg: 세그먼트 → PNG 자막 overlay → concat → 음성·효과음 → loudnorm -16 LUFS → 1080×1920 30fps mp4 + 프레임시트 |
| 자동 검수 | freezedetect, 길이, ebur128, 프레임시트(검수 팀원이 이미지로 점검) |

## 9. 스케줄과 무인 권한

- OS 스케줄러는 매시 정각에 `daily.py`를 깨우고 KST(UTC+9 고정) 판단은 Python이 한다. 07:00~12:00 사이 첫 가동에서 실행하므로 07:00에 꺼져 있었으면 켜진 뒤 따라잡는다.
- macOS: `~/Library/LaunchAgents/com.osmu-studio.daily.plist` (매시, PATH 고정, `launchctl bootstrap`)
- Windows: `schtasks /Create /XML` (매시 반복, StartWhenAvailable, WakeToRun, IgnoreNew, pythonw.exe)
- 무인 권한은 프로젝트 `settings.json`이 아니라 `--settings` 파일로 전달한다(폴더 신뢰 전에는 프로젝트 allow가 적용되지 않음). allow는 이 저장소의 `osmu.py`, 윤문 플러그인 스크립트, output·_workspace 편집, Skill, Agent만. deny에 웹 도구, `.env` 읽기, scripts·config·rules·.claude 수정, curl·git·rm을 둔다. 설치 때 이 내용을 보여주고 동의를 받는다.

## 10. 배포 안전

- `.gitignore`: `.env*`(예외 `.env.example`), `config/*.local.*`, `output/`, `_workspace/`, `.venv/`, 미디어 파일 등
- `scripts/publish/scan_secrets.py`: 키·토큰·웹훅·시트 ID·개인 절대경로·이메일 패턴 검사. pre-commit 훅과 CI에서 실행. 첫 커밋 전에 훅부터 설치
- 저장소에 넣지 않는 것: 비밀값, 개인 경로·계정·브랜드 문구, 테스트 산출물, 로컬 설정, 라이선스 불명 자산

## 11. 구현 순서 (테스트 우선)

| 단계 | 만드는 것 | 검증 |
|---|---|---|
| 0 | git init, .gitignore, pre-commit 훅, doctor, selftest | 외부 연결(알림·이미지·TTS) PASS/FAIL, 샘플 3종 → topic.json, 무인 권한 실측 |
| 1 | config·.env 로더, KST 가드, 잠금, notify, select-topic, claude_cmd | 단위 테스트 + 양 OS CI |
| 2 | rules/* 이식, 분포 md 생성, NOTICE | 필수 섹션·금지어 파싱 테스트 |
| 3 | 에이전트 8개, /osmu-run(숏츠 제외), 규격 검사, 윤문 연동 | 샘플 주제 1건 → 규격 통과, 윤문 변경률 기록 |
| 4 | 이미지(gemini, pixverse, 카피 합성) | 5장 가로·텍스트 없음, 3:4 한글 깨짐 없음 |
| 5 | 숏츠(tts, plan, build, captions, review) | CI: 합성음+단색 이미지 30초 mp4(양 OS). 로컬: 실제 1편 |
| 6 | 모션(Remotion) | CI: 1초 렌더(양 OS). 로컬: 1편 |
| 7 | 예약·설치(daily, schedule, /osmu-setup) | launchd 테스트 가동 → 알림. CI windows: schtasks 등록·실행·삭제 |
| 8 | Windows 전체 실행 | Windows 컴퓨터에서 clone → 설치 → 1회 실행 체크리스트 |
| 9 | 배포 | scan_secrets 통과, README, 확인 후 push |

## 12. 위험

| 위험 | 대응 |
|---|---|
| 윤문 플러그인 스크립트가 무인 권한에서 거부되면 변경률 게이트가 사라짐 | 0단계 실측, 정확 경로 allow |
| 유튜브·블로그 "상위 10" 데이터 | 유튜브는 API 키 있으면 조회수순, 없으면 웹 검색(조회수 미확인 표기). 블로그는 조회수 비공개라 검색 노출 순으로 대체 |
| 인스타·쓰레드 계정 읽기 실패(로그인 벽) | "없음" 또는 참고 글 붙여넣기 대안 |
| 07:00에 꺼진 컴퓨터 | 매시 가드 + 12:00 마감, WakeToRun. 완전 종료는 README에 명시 |
| 하루 비용·시간 | 60~90분, API 기준 $5~15/일 추정. 예산 상한, 비용을 알림에 표기 |
| 설치자의 전역 Claude 설정 간섭 | `--strict-mcp-config`, MCP 도구 금지. 나머지는 README에 명시 |

## 13. 미확인 항목과 실측 결과

| # | 항목 | 결과 (2026-10-03 0단계) |
|---|---|---|
| 1 | 윤문 플러그인 SKILL의 명령치환(`$(…)`)이 dontAsk 모드에서 허용되는지 | **거부됨**(프로브 `bash_subst: denied`). → 변경률·키워드 보존 게이트는 플러그인 스크립트에 기대지 않고 `osmu.py humanize-gate`로 직접 구현한다(문자 바이그램 변경률 30% 경고·50% 롤백, 수치·키워드 보존 검사) |
| 2 | `--settings` 파일의 allow가 적용되는지 | **적용됨**. 프로브 10항목 중 9항목이 설계대로(Read·osmu.py·output 쓰기·mkdir·Agent 허용 / .env·curl·scripts 수정 거부). `--disallowedTools`로 뺀 WebFetch는 도구 자체가 세션에 없음 |
| 3 | 구독 로그인이 Windows 예약 작업에서 유지되는지 | 미확인 — 8단계 Windows 실행에서 확인 |
| 4 | ElevenLabs with-timestamps 응답 형식 | **확인**: `audio_base64` + `alignment{characters, character_start_times_seconds, character_end_times_seconds}` |
| 5 | Gemini 이미지 모델 ID와 3:4 지원 | 미확인 — GEMINI_API_KEY 확보 후 selftest |
| 6 | Pixverse CLI Windows 동작 | 미확인 — 8단계. macOS에서는 로그인·계정 조회 통과 |
| 7 | 네이버 모바일 페이지 WebFetch 가능 여부 | 미확인 — 3단계 리서처 테스트에서 확인 |

0단계 실측 비용: 프로브 1회 약 $1.5(12턴). 하루 실행 비용 추정에 반영한다.
