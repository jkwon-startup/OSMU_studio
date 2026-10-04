# Windows 확인 체크리스트

macOS에서 전체 통과한 뒤, Windows 컴퓨터 한 대에서 아래 순서로 확인한다. 각 항목의 결과(통과/실패와 메시지)를 적어 두면 수정에 바로 쓸 수 있다.

## 0. 준비 (PowerShell, 관리자 권한 불필요)

```powershell
winget install Git.Git Gyan.FFmpeg OpenJS.NodeJS.LTS Python.Python.3.12
# Claude Code: https://code.claude.com/docs/en/setup 의 Windows 안내대로 설치 후 로그인
git clone https://github.com/jkwon-startup/OSMU_studio.git
cd OSMU_studio
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
copy .env.example .env     # 편집기로 열어 키 입력
```

- [ ] `where claude` 가 경로를 출력한다 (`%USERPROFILE%\.local\bin\claude.exe` 권장. `claude.cmd` 면 메모)
- [ ] `where bash` 가 Git Bash 경로를 출력한다

## 1. 도구 점검

```powershell
.venv\Scripts\python scripts\osmu.py doctor
```
- [ ] 필수 항목 모두 OK (Python, Claude Code, FFmpeg + 필터·인코더, ffprobe, git, Pillow)
- [ ] 한글이 깨지지 않고 출력된다 (깨지면 `chcp 65001` 후 재시도하고 그 사실을 메모)

## 2. 외부 연결

```powershell
.venv\Scripts\python scripts\osmu.py selftest
```
- [ ] Slack 또는 텔레그램 PASS (실제 메시지 수신)
- [ ] 선택한 이미지 서비스 PASS (Pixverse: `npm install -g pixverse` → `pixverse auth login` 후)
- [ ] 선택한 음성 서비스 PASS
- [ ] FFmpeg 합성 PASS

## 3. 설치 커맨드

```powershell
claude
```
`/osmu-setup` 을 끝까지 진행한다.
- [ ] 주제 소스 미리보기(`select-topic`)가 오늘 주제를 올바르게 보여준다
- [ ] `config\config.local.json` 이 생성되고 `python_path`·`claude_path` 가 절대경로다
- [ ] humanize-korean 플러그인 설치 제안을 수락했다 (또는 건너뛴 사실을 메모)
- [ ] 무인 권한 설명 후 동의 단계가 나온다

## 4. 수동 실행 1회

```powershell
.venv\Scripts\python scripts\run\daily.py --now
```
- [ ] 조사 세션 3개가 끝나고 `output\runs\<날짜>\01_research\*.md` 3개가 생긴다
- [ ] 제작 세션이 끝나고 `05_blog.md`, `06_instagram.md`, `07_threads.md`, `images\`, `08_shorts\shorts.mp4`, `summary.json` 이 생긴다
- [ ] 알림이 왔다 (내용에 "완료" 또는 "부분 완료")
- [ ] `shorts.mp4` 가 재생되고 자막 한글이 깨지지 않는다
- [ ] `images\instagram.jpg` 의 한글 카피가 정상이다
- [ ] (모션그래픽 주제라면) `08_shorts\review.json` 의 notes 에 "Remotion 없음" 이 없다 — 있으면 `cd motion; npm install` 후 재실행

```powershell
.venv\Scripts\python scripts\osmu.py check output\runs\<날짜>
```
- [ ] 실패 0

## 5. 예약 등록

```powershell
.venv\Scripts\python scripts\osmu.py schedule install
.venv\Scripts\python scripts\osmu.py schedule status
```
- [ ] 작업 스케줄러에 "OSMU Studio" 가 보인다 (taskschd.msc)
- [ ] `schedule run-now` 로 즉시 실행했을 때 창 밖 시각이면 1초 안에 조용히 끝난다(정상). 창 안이면 실행이 시작된다
- [ ] 다음 날 07:00~12:00 사이 자동 실행 후 알림 수신 (컴퓨터 켜 둔 상태로 1회)
- [ ] 잠자기 상태에서 WakeToRun 으로 깨어나 실행되는지 (선택)

## 6. 정리

- [ ] 테스트용 예약을 둘지 해제할지 결정 (`schedule uninstall`)
- [ ] 발견한 문제를 `docs/DEVELOPMENT-PLAN.md` 14절 또는 이슈로 기록
