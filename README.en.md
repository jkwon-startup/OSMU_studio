# OSMU Studio

[한국어](README.md)

A Claude Code content team that turns one topic into a Korean blog post, five images, an Instagram feed post, a Threads post and a 30-second short video **every morning at 7:00 KST**, then notifies you on Slack or Telegram.

- One lead (main session) and eight teammates (subagents): research → persona → five key points → hook copy → blog → humanize → images · SNS · shorts → review.
- Writing rules target the Korean market (Naver search ranking, SGE/E-E-A-T, persona methodology). The output language is Korean.
- **You can start for free with only Claude Code.** Narration uses the free Microsoft Edge voice (no key); photos and B-roll come from Pexels (free key). Gemini, ElevenLabs and Pixverse are optional upgrades.
- Runs on macOS and Windows (and on Linux servers via Docker). It generates and saves; it never auto-posts.

## Requirements

Claude Code, Python 3.10+, FFmpeg, git. Optional: a free Pexels/Pixabay API key, Slack webhook or Telegram bot, paid image/voice services, your own background music in `assets/bgm/`.

## Install

Inside Claude Code (any folder):

```
/plugin install osmu-studio --marketplace jkwon-startup/OSMU_studio
/osmu-studio:install
```

Or from a terminal:

```bash
git clone https://github.com/jkwon-startup/OSMU_studio.git
cd OSMU_studio
claude        # then type /osmu-setup
```

`/osmu-setup` asks about your brand, where daily topics live (folder / spreadsheet / plan document), reference accounts, **free vs. paid services**, and notifications. Keys go into `.env` yourself (never into the chat). It then runs a connection test, one full trial run, and registers the daily schedule after you approve the result.

## Graceful fallbacks

Unattended runs never stop halfway because one service failed:

| If this fails | It uses |
|---|---|
| Configured voice (key, quota, billing) | Free Edge voice → captions-only video |
| AI images | Pexels/Pixabay photos (if a stock key exists) |
| Scene image / clip | Still image → text card |
| Motion graphics (Chromium) | Static card with the same content |
| Background music | No music |

Every fallback is recorded in `summary.json` and the notification.

## Customising shorts

`config/config.local.json`: `shorts_aspect` (`9:16` / `1:1` / `16:9`), `shorts_transition` (`fade`, `dissolve`, `slide_left`, `slide_up`, `zoom`, `cut`), `edge_tts_voice`, `bgm`. Brand colours, caption colours and fonts live in `config/frame.local.md`. Motion-graphic scenes are plain HTML/CSS files in `templates/motion/` — see its README; preview with `python scripts/osmu.py motion-preview <name>`.

## Useful commands

```bash
.venv/bin/python scripts/run/daily.py --now        # run once now
.venv/bin/python scripts/osmu.py doctor             # check tools (and updates)
.venv/bin/python scripts/osmu.py selftest           # check connections
.venv/bin/python scripts/osmu.py config-show        # effective settings
```

Troubleshooting (Korean): `docs/TROUBLESHOOTING.md`. Licences and the open-source projects this borrows ideas from (MoneyPrinterTurbo, Pixelle-Video, HyperFrames): `NOTICE.md`.

## License

MIT. Bundled fonts: SIL OFL 1.1. No music is bundled.
