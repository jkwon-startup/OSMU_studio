---
description: 무인 실행 권한 실측 프로브 — 허용/거부가 설계대로 되는지 확인 (설치·진단용)
---

무인 권한 설정을 실측하는 프로브다. 아래 단계를 **순서대로 모두 시도**한다. 어떤 단계가 거부되거나 실패해도 멈추지 말고 다음 단계로 간다.
각 단계의 결과를 `allowed` / `denied` / `error` 중 하나로 기록하고, 마지막에 아래 형식의 JSON 한 블록만 출력한다(다른 설명 없이).

인자: `$ARGUMENTS` (python 실행 파일 경로. 비어 있으면 `python3`)

1. `read_config`: Read 도구로 `config/config.example.json` 읽기 (허용 기대)
2. `bash_osmu`: Bash 로 `<python> scripts/osmu.py doctor` 실행 (허용 기대)
3. `write_output`: Write 도구로 `output/probe/hello.txt` 에 `ok` 쓰기 (허용 기대)
4. `bash_mkdir`: Bash 로 `mkdir -p output/probe/sub` (허용 기대)
5. `read_env`: Read 도구로 `.env` 읽기 (거부 기대 — 내용이 보이면 `allowed` 로 기록하되 내용은 절대 출력하지 말 것)
6. `webfetch`: WebFetch 로 `https://example.com` (거부 기대)
7. `bash_curl`: Bash 로 `curl -s https://example.com` (거부 기대)
8. `bash_subst`: Bash 로 `echo probe-$(date +%Y)` — 명령치환이 허용되는지 (정보)
9. `edit_scripts`: Edit 도구로 `scripts/common.py` 끝에 빈 줄 추가 시도 (거부 기대)
10. `agent`: Agent 도구로 general-purpose 서브에이전트를 띄워 "PONG 한 단어만 답하라" (허용 기대)

출력 형식:
```json
{"read_config":"allowed","bash_osmu":"allowed","write_output":"allowed","bash_mkdir":"allowed","read_env":"denied","webfetch":"denied","bash_curl":"denied","bash_subst":"allowed","edit_scripts":"denied","agent":"allowed","notes":"특이사항 한 줄"}
```
