# OSMU Studio — 헤드리스 리눅스 서버용 이미지 (macOS·Windows 데스크톱은 README 의 기본 설치가 더 간단합니다)
#
#   docker compose build
#   docker compose run --rm osmu doctor
#   docker compose run --rm osmu selftest --only ffmpeg_compose,edge_tts,stock
#   docker compose run --rm --entrypoint python osmu scripts/run/daily.py --now
#
# 키·설정·산출물은 이미지에 넣지 않고 docker-compose.yml 의 볼륨으로 연결한다.
FROM python:3.12-slim

ENV PYTHONUTF8=1 \
    PYTHONIOENCODING=utf-8 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    TZ=Asia/Seoul

# FFmpeg(합성), git(업데이트 확인), Node(Claude Code CLI)
RUN apt-get update \
 && apt-get install -y --no-install-recommends ffmpeg git ca-certificates tzdata nodejs npm \
 && apt-get clean

# Claude Code — 컨테이너 안 인증은 .env 의 ANTHROPIC_API_KEY 또는 CLAUDE_CODE_OAUTH_TOKEN(`claude setup-token` 으로 발급)
RUN npm install -g @anthropic-ai/claude-code && npm cache clean --force

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt \
 && python -m playwright install --with-deps chromium

COPY . .
RUN useradd --create-home osmu \
 && mkdir -p /app/output /app/config \
 && chown -R osmu:osmu /app /ms-playwright
USER osmu

ENTRYPOINT ["python", "scripts/osmu.py"]
CMD ["doctor"]
