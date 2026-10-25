# 문제 해결

먼저 이 두 명령으로 상태를 보세요(Windows 는 `.venv\Scripts\python`).

```bash
.venv/bin/python scripts/osmu.py doctor      # 설치된 도구 — FAIL 옆 → 줄이 해결 방법
.venv/bin/python scripts/osmu.py selftest    # 실제 연결 — 무료 항목(edge_tts, stock)은 비용 없음
```

그래도 모르겠으면 그날 폴더의 기록을 보세요: `output/runs/<날짜>/summary.json`(무엇이 실패·대체됐는지), `08_shorts/review.json`(영상 검사), `images/image_results.json`(이미지 오류), `produce_attempt1.log`(제작 세션 기록 — 키는 자동으로 가려져 있어 이슈에 붙여도 됩니다).

## 설치

**`python` / `python3` 를 찾을 수 없다고 나와요 (Windows)**
Python 을 다시 설치하면서 첫 화면의 "Add python.exe to PATH" 를 체크하세요. 설치 후 터미널을 새로 여세요.

**`pip install` 이 실패해요**
- 회사·학교 네트워크라면 프록시 때문일 수 있습니다. 집 네트워크나 휴대폰 테더링으로 한 번 시도해 보세요.
- `uv` 가 있으면 `uv sync` 가 더 안정적입니다.

**`playwright install chromium` 이 실패하거나 doctor 에 "Chromium 미설치"**
`.venv/bin/python -m playwright install chromium` 을 다시 실행하세요(약 100MB). 안 되면 모션그래픽 장면만 정적 카드로 대체되고 나머지는 정상 동작합니다.

**FFmpeg 필터·인코더가 없다고 나와요**
일부 최소 빌드에는 필요한 기능이 빠져 있습니다. macOS `brew reinstall ffmpeg`, Windows `winget install Gyan.FFmpeg`(전체 빌드)로 바꾸세요. libx264 가 없어도 OS 내장 인코더로 자동 대체되지만, 화질은 libx264 가 가장 좋습니다.

## 이미지

**블로그 이미지가 하나도 없어요**
`images/image_results.json` 의 오류를 보세요.
- "스톡 키가 없습니다" → https://www.pexels.com/api/ 에서 무료 키를 받아 `.env` 에 `PEXELS_API_KEY=…`.
- "HTTP 401/403" → 키를 잘못 붙여넣었습니다(앞뒤 공백·따옴표 확인).
- "HTTP 429" → 한도 초과. Pexels 는 시간당 200회라 보통 다음 날 풀립니다. `PIXABAY_API_KEY` 를 추가하면 이어서 찾습니다.
- Gemini 를 쓰는데 429 → 무료 등급 한도일 가능성. 결제가 켜진 프로젝트의 키를 쓰거나, 스톡 키를 넣어 두면 실패한 장만 스톡 사진으로 대체됩니다.

**스톡 사진이 주제와 안 어울려요**
검수 팀원이 엉뚱한 사진을 잡아 검색어를 바꾸라고 지시합니다. 계속 어색하면 `rules/image-prompts.md` 의 "스톡 검색어" 규칙을 브랜드에 맞게 고치세요(예: "사람보다 사물 위주"). 출처는 `images/credits.json` 에 있습니다.

## 숏츠

**영상에 목소리가 없어요 (자막만 나와요)**
음성 서비스가 모두 실패해 무음으로 대체된 것입니다. `08_shorts/timing.json` 의 `fallback` 에 이유가 있습니다.
- edge 실패 → 인터넷 연결 확인, `osmu.py selftest --only edge_tts`. 회사 방화벽이 Microsoft 음성 서버를 막는 경우가 있습니다.
- ElevenLabs/Gemini 실패 → 키·결제·한도 확인. 그동안은 무료 음성으로 자동 대체됩니다.

**모션그래픽이 움직이지 않는 정적 카드로 나와요**
`review.json` 의 `motion` 에 `card` 가 있고 notes 에 이유가 적혀 있습니다. 대부분 Chromium 미설치 → 위 "playwright install" 참고.

**배경음악이 안 들어가요**
`review.json` 의 `bgm_note` 를 보세요. `assets/bgm/` 에 mp3·m4a·wav·ogg 파일이 있어야 합니다(하위 폴더는 보지 않음). 끄려면 `config.local.json` 에 `"bgm": {"enabled": false}`.

**자막이 너무 빨리 지나가요**
`osmu.py check output/runs/<날짜>` 의 `caption_reading_time` 경고에 해당 자막이 나옵니다. 대본 문장을 더 짧게 쓰도록 `rules/shorts-script.md` 를 조정하거나, `edge_tts_rate` 를 `+0%` 로 낮추세요.

**영상이 세로가 아니에요 / 정사각형으로 만들고 싶어요**
`config.local.json` 의 `"shorts_aspect"`: `9:16` · `1:1` · `16:9`.

## 예약 실행

**아침에 알림이 안 왔어요**
1. `osmu.py schedule status` — 등록돼 있는지.
2. 그 시각에 컴퓨터가 켜져 있었는지(완전 종료면 켜진 뒤 첫 정각에 따라잡음, 12:00 이후면 그날은 건너뜀).
3. `output/state/runs.json` 의 오늘 항목 — `stage` 에 멈춘 단계, `error` 에 이유.
4. 알림 자체 문제면 `osmu.py selftest --only slack` (또는 `telegram`).

**"시작 전 점검 실패 — 비용은 쓰지 않았습니다" 알림**
알림에 적힌 항목(FFmpeg·글꼴·디스크 공간)을 해결하고 `daily.py --now` 로 다시 돌리세요.

## 설정

**설정을 고쳤는데 반영이 안 돼요**
`osmu.py config-show` 로 실제 값을 보세요. 잘못된 값(예: `"image_provider": "midjourney"`)은 경고와 함께 기본값으로 바뀝니다. JSON 문법 오류(쉼표·따옴표)가 있으면 파일 전체가 무시되고 경고가 나옵니다.

**업데이트 후 이상해요**
`git pull` 다음에 `pip install -r requirements.txt` 를 꼭 다시 실행하세요(새 패키지). 그래도 안 되면 `doctor` 결과와 함께 GitHub 이슈를 올려 주세요.
