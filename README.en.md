# OSMU Studio

[한국어](README.md)

A Claude Code content team that turns one topic into a Korean blog post, five images, an Instagram feed post, a Threads post and a 30-second short video **every morning at 7:00 KST**, then notifies you on Slack or Telegram.

- One lead (main session) and eight teammates (subagents): research → persona → five key points → hook copy → blog → humanize → images · SNS · shorts → review.
- Writing rules target the Korean market (Naver search ranking, SGE/E-E-A-T, persona methodology). The output language is Korean.
- **You can start for free with only Claude Code.** Narration uses the free Microsoft Edge voice (no key); photos and B-roll come from Pexels (free key). Gemini, ElevenLabs and Pixverse are optional upgrades.
- Topics are read daily from a folder, a spreadsheet (Excel / Google Sheets) or a plan document; each short is made in a **live-action** or **motion-graphics** style.
- Runs on macOS and Windows (and on Linux servers via Docker). It generates and saves; it never auto-posts.

> **New in 1.1 (2026-10)**
> - **Start free**: free Edge voice (no key) + free Pexels stock by default; paid services fall back to free ones, and finally to a captions-only video
> - **Video quality**: background music with ducking, six transitions, 9:16 · 1:1 · 16:9, Korean-safe caption alignment
> - **HTML motion templates**: one scene = one HTML file, add designs with CSS; Remotion is optional
> - **Install & ops**: installer plugin, Docker, preflight checks before spending money, brand tokens, stronger review gates
>
> Details (Korean): [docs/UPDATE-1.1.md](docs/UPDATE-1.1.md)

## Requirements

Claude Code, Python 3.10+, FFmpeg, git. Optional: Node.js 18+ (Remotion engine / Pixverse CLI only), your own background music in `assets/bgm/`.

## Accounts and API keys

| Service | Needed? | Cost | Where to sign up | `.env` name | Used for |
|---|---|---|---|---|---|
| **Claude** (Anthropic) | **Required** | Pro/Max plan or API usage | [claude.ai](https://claude.ai), then log in to Claude Code | (none — login) | All writing, research, review |
| **Pexels** | **Recommended** | Free | [pexels.com/api](https://www.pexels.com/api/) | `PEXELS_API_KEY` | Blog photos, Instagram backgrounds, shorts scenes/B-roll |
| Pixabay | Optional | Free | [pixabay.com/api/docs](https://pixabay.com/api/docs/) | `PIXABAY_API_KEY` | Fallback stock search |
| Slack | One of two for notifications | Free | [api.slack.com/apps](https://api.slack.com/apps) → Incoming Webhooks | `SLACK_WEBHOOK_URL` | Done/failed notification |
| Telegram | One of two for notifications | Free | [@BotFather](https://t.me/BotFather) `/newbot` | `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` | Done/failed notification |
| Gemini | Optional (quality) | Paid | [aistudio.google.com/apikey](https://aistudio.google.com/apikey) | `GEMINI_API_KEY` | AI images, voice |
| ElevenLabs | Optional (quality) | Paid | [elevenlabs.io](https://elevenlabs.io) → API Keys | `ELEVENLABS_API_KEY` | Premium voice |
| Pixverse | Optional (quality) | Paid plan | [pixverse.ai](https://pixverse.ai) | (none — `pixverse auth login`) | AI images, image-to-video clips, voice |

No sign-up needed for the narration voice (Microsoft Edge), GitHub (public repo) or fonts (bundled).
**Free setup** = Claude + Pexels + Slack or Telegram. With Claude only, everything is produced except photos.

Copy `.env.example` to `.env`, fill in only the keys you have, and run `python scripts/osmu.py selftest`. Never paste keys into the Claude chat — the scripts read `.env`; Claude sessions don't. Step-by-step instructions for each key are in the [Korean README](README.md#가입api-키-안내).

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
