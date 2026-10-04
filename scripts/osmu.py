#!/usr/bin/env python3
"""OSMU Studio 단일 진입점 CLI.

  python3 scripts/osmu.py doctor                 도구 점검 (네트워크 없음)
  python3 scripts/osmu.py selftest [--only a,b]  외부 연결 검사 (비용 발생 가능)
  python3 scripts/osmu.py select-topic [--out F] 오늘 주제 선택 → topic.json
  python3 scripts/osmu.py mark-done REF [--retry] 주제 완료/재시도 표시
  python3 scripts/osmu.py notify "메시지"         알림 전송 (config.notify.channel)
  python3 scripts/osmu.py scan [--staged]        비밀값 검사

무인 세션의 권한 규칙이 `Bash(<python> scripts/osmu.py *)` 한 줄로 끝나도록 모든 기능을 이 파일로 모은다.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from common import OUTPUT_DIR, ensure_utf8_stdout, kst_now, load_config, load_env, read_json, write_json  # noqa: E402


def cmd_doctor(_):
    from setup import doctor
    return 0 if doctor.print_report(doctor.check_all()) else 1


def cmd_selftest(a):
    from setup import selftest
    only = set(a.only.split(",")) if a.only else None
    return 0 if selftest.run(only) else 1


def cmd_select_topic(a):
    from topics import select
    topic = select.select_topic(load_config())
    if not topic:
        print("오늘 주제 없음")
        return 2
    out = Path(a.out) if a.out else OUTPUT_DIR / "runs" / kst_now().strftime("%Y-%m-%d") / "topic.json"
    write_json(out, topic)
    print(json.dumps(topic, ensure_ascii=False, indent=2))
    print(f"→ {out}")
    return 0


def cmd_mark_done(a):
    from topics import select
    select.mark(a.ref, "retry" if a.retry else "done")
    print("표시 완료")
    return 0


def cmd_notify(a):
    import notify
    cfg = load_config()
    channel = a.channel or (cfg.get("notify") or {}).get("channel", "slack")
    ok, detail = notify.send(channel, load_env(), a.message)
    print(f"{'전송됨' if ok else '실패'} ({channel}): {detail}")
    return 0 if ok else 1


def cmd_research(a):
    """세션 A 만 실행 (테스트·재조사용)."""
    from run import daily
    from run.claude_cmd import find_claude
    from topics import select
    cfg = load_config()
    run_dir = Path(a.run) if a.run else OUTPUT_DIR / "runs" / kst_now().strftime("%Y-%m-%d")
    topic = read_json(run_dir / "topic.json")
    if not topic:
        topic = select.select_topic(cfg)
        if not topic:
            print("주제 없음"); return 2
        write_json(run_dir / "topic.json", topic)
    claude_path = find_claude(cfg.get("claude_path"))
    print(f"주제: {topic['title']} → 리서처 3명 병렬 (최대 15분)")
    res = daily.run_research(topic, run_dir, cfg, claude_path)
    print(res)
    return 0 if all(res.values()) else 1


def cmd_produce(a):
    """세션 B 만 실행 (테스트용). scope=text 면 이미지·영상 제외."""
    from run.claude_cmd import ClaudeCall, find_claude, run_claude
    from run import daily
    cfg = load_config()
    run_dir = Path(a.run)
    settings = daily.write_unattended_settings(cfg)
    rel = run_dir.resolve().relative_to(Path.cwd().resolve()).as_posix() if run_dir.is_absolute() else run_dir.as_posix()
    call = ClaudeCall(prompt=f"/osmu-run run={rel} scope={a.scope}", settings=settings,
                      disallowed_tools=["WebSearch", "WebFetch"], max_budget_usd=float(cfg.get("max_budget_usd", 15)))
    print("제작 세션 시작 (최대 2시간) …")
    res = run_claude(call, find_claude(cfg.get("claude_path")), daily.PRODUCE_TIMEOUT_S, run_dir / "produce_manual.log")
    data = res.json() or {}
    print(f"exit={res.returncode} {res.seconds/60:.1f}분 cost=${data.get('total_cost_usd', 0):.2f} turns={data.get('num_turns')}")
    print((data.get("result") or res.stderr)[-1500:])
    return 0 if res.ok else 1


def cmd_image(a):
    from image import generate
    cfg = load_config()
    run_dir = Path(a.run)
    if a.prompts_stdin:
        items = json.loads(sys.stdin.read())
    else:
        items = json.loads(Path(a.prompts or (run_dir / "images" / "prompts.json")).read_text(encoding="utf-8"))
    provider = a.provider or cfg.get("image_provider", "gemini")
    print(f"이미지 {len(items)}장 생성 — provider={provider}")
    results = generate.generate_all(run_dir, items, provider, cfg)
    return 0 if all(r["ok"] for r in results) else 1


def cmd_compose(a):
    from image import compose_copy
    run_dir = Path(a.run)
    bg = Path(a.bg) if a.bg else run_dir / "images" / "instagram_bg.jpg"
    out = Path(a.out) if a.out else run_dir / "images" / "instagram.jpg"
    res = compose_copy.compose(bg, a.text, out, a.position)
    print(json.dumps(res, ensure_ascii=False))
    return 0


def cmd_tts(a):
    from video import tts
    timing = tts.run(Path(a.run), load_config(), a.provider)
    return 0 if timing["units"] else 1


def cmd_video(a):
    from video import build, plan_schema
    cfg = load_config()
    run_dir = Path(a.run)
    sdir = run_dir / "08_shorts"
    if a.action in ("auto-plan", "all"):
        script = json.loads((sdir / "script.json").read_text(encoding="utf-8"))
        timing = json.loads((sdir / "timing.json").read_text(encoding="utf-8"))
        style = a.style or script.get("style") or "photoreal"
        plan = plan_schema.auto_plan(script, timing, style, cfg.get("image_provider", "gemini"))
        write_json(sdir / "plan.json", plan)
        print(f"plan.json: {len(plan['shots'])} shots, {len(plan['captions'])} captions, {plan['duration_s']}s, style={style}")
    if a.action in ("plan-check", "auto-plan", "assets", "build", "all"):
        errs = plan_schema.validate_file(sdir / "plan.json")
        if errs:
            print("plan.json 오류:\n  " + "\n  ".join(errs))
            return 1
        print("plan-check: OK")
        if a.action == "plan-check":
            return 0
    plan = json.loads((sdir / "plan.json").read_text(encoding="utf-8"))
    if a.action in ("assets", "all") and plan.get("style") != "motion":
        res = build.make_assets(run_dir, plan, cfg)
        fails = [r for r in res if not r["ok"]]
        print(f"assets: {len(res) - len(fails)} OK / {len(fails)} FAIL")
    if a.action in ("build", "all"):
        review = build.build(run_dir, cfg)
        print(json.dumps(review, ensure_ascii=False, indent=2))
        return 0 if review["duration_ok"] else 1
    return 0


def cmd_schedule(a):
    from setup import schedule
    label = a.label or schedule.DEFAULT_LABEL
    if a.action == "render":
        text = schedule.render_task_xml() if a.windows or os.name == "nt" else schedule.render_launchd(label)
        if a.out:
            Path(a.out).write_text(text, encoding="utf-16" if (a.windows or os.name == "nt") else "utf-8")
            print(f"→ {a.out}")
        else:
            print(text)
        return 0
    fn = {"install": schedule.install, "uninstall": schedule.uninstall, "status": schedule.status, "run-now": schedule.run_now}[a.action]
    print(fn(label))
    return 0


def cmd_config_write(a):
    """설치 커맨드가 config.local.json 을 쓸 때 사용 (stdin 으로 JSON). 비밀값은 받지 않는다."""
    data = json.loads(sys.stdin.read())
    for k in list(data):
        if any(s in k.upper() for s in ("KEY", "TOKEN", "SECRET", "WEBHOOK", "PASSWORD")):
            print(f"거부: '{k}' 는 비밀값으로 보임 — .env 에 직접 넣으세요")
            return 1
    path = Path("config/config.local.json")
    cur = read_json(path, {}) or {}
    cur.update(data)
    write_json(path, cur)
    print(f"config.local.json 갱신: {', '.join(data.keys())}")
    return 0


def cmd_check(a):
    from checks import specs
    run_dir = Path(a.run_dir)
    only = set(a.only.split(",")) if a.only else None
    r = specs.run_checks(run_dir, only)
    specs.print_report(r)
    return 1 if r.failed else 0


def cmd_humanize_gate(a):
    from checks import humanize_gate
    argv = [a.original, a.rewritten]
    if a.keywords:
        argv += ["--keywords", a.keywords]
    if a.title:
        argv += ["--title", a.title]
    if a.out:
        argv += ["--out", a.out]
    return humanize_gate.main(argv)


def cmd_scan(a):
    from publish import scan_secrets
    sys.argv = ["scan_secrets.py"] + (["--staged"] if a.staged else [])
    return scan_secrets.main()


def main(argv=None) -> int:
    ensure_utf8_stdout()
    ap = argparse.ArgumentParser(prog="osmu")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("doctor").set_defaults(fn=cmd_doctor)
    p = sub.add_parser("selftest"); p.add_argument("--only"); p.set_defaults(fn=cmd_selftest)
    p = sub.add_parser("select-topic"); p.add_argument("--out"); p.set_defaults(fn=cmd_select_topic)
    p = sub.add_parser("mark-done"); p.add_argument("ref"); p.add_argument("--retry", action="store_true"); p.set_defaults(fn=cmd_mark_done)
    p = sub.add_parser("notify"); p.add_argument("message"); p.add_argument("--channel"); p.set_defaults(fn=cmd_notify)
    p = sub.add_parser("research"); p.add_argument("--run"); p.set_defaults(fn=cmd_research)
    p = sub.add_parser("produce"); p.add_argument("--run", required=True); p.add_argument("--scope", default="full"); p.set_defaults(fn=cmd_produce)
    p = sub.add_parser("image"); p.add_argument("--run", required=True); p.add_argument("--prompts"); p.add_argument("--prompts-stdin", action="store_true"); p.add_argument("--provider"); p.set_defaults(fn=cmd_image)
    p = sub.add_parser("compose"); p.add_argument("--run", required=True); p.add_argument("--text", required=True); p.add_argument("--bg"); p.add_argument("--out"); p.add_argument("--position", default="top"); p.set_defaults(fn=cmd_compose)
    p = sub.add_parser("tts"); p.add_argument("--run", required=True); p.add_argument("--provider"); p.set_defaults(fn=cmd_tts)
    p = sub.add_parser("video"); p.add_argument("action", choices=["plan-check", "auto-plan", "assets", "build", "all"]); p.add_argument("--run", required=True); p.add_argument("--style"); p.set_defaults(fn=cmd_video)
    p = sub.add_parser("schedule"); p.add_argument("action", choices=["install", "uninstall", "status", "run-now", "render"]); p.add_argument("--label"); p.add_argument("--out"); p.add_argument("--windows", action="store_true"); p.set_defaults(fn=cmd_schedule)
    p = sub.add_parser("config-write"); p.set_defaults(fn=cmd_config_write)
    p = sub.add_parser("check"); p.add_argument("run_dir"); p.add_argument("--only"); p.set_defaults(fn=cmd_check)
    p = sub.add_parser("humanize-gate"); p.add_argument("original"); p.add_argument("rewritten")
    p.add_argument("--keywords"); p.add_argument("--title"); p.add_argument("--out"); p.set_defaults(fn=cmd_humanize_gate)
    p = sub.add_parser("scan"); p.add_argument("--staged", action="store_true"); p.set_defaults(fn=cmd_scan)
    a = ap.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
