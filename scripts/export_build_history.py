"""Export the Claude Code build conversation to readable Markdown for the submission.

    python scripts/export_build_history.py ~/.claude/projects/<project>/<session>.jsonl [more.jsonl …]

Keeps every message from the person and every reply in full; each tool call is one line with its input
shortened, each tool result its first lines. Harness bookkeeping, private reasoning and images are left out.
Secrets are removed before anything is written: values from .env and anything shaped like an API key or
token. The script prints only counts, never what it removed.
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "build-history"
TOOL_INPUT, TOOL_RESULT = 500, 300

KEY_SHAPES = re.compile(r"AIza[0-9A-Za-z_\-]{20,}|gh[pousr]_[0-9A-Za-z]{20,}|github_pat_[0-9A-Za-z_]{20,}"
                        r"|sk-[0-9A-Za-z\-_]{20,}|re_[0-9A-Za-z]{16,}|xox[abp]-[0-9A-Za-z\-]{10,}|EAA[0-9A-Za-z]{30,}"
                        r"|(?i:bearer)\s+[0-9A-Za-z\-_.]{20,}")
REMINDER = re.compile(r"<system-reminder>.*?</system-reminder>", re.S)


def env_values() -> list[str]:
    vals = []
    for f in (ROOT / ".env", ROOT.parent / ".env"):       # the project's, and one left in the folder above it
        if not f.exists():
            continue
        for line in f.read_text().splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                v = line.split("=", 1)[1].strip().strip("'\"")
                if len(v) >= 8:
                    vals.append(v)
    return vals


class Scrubber:
    def __init__(self):
        self.values, self.hits = env_values(), 0

    def __call__(self, s: str) -> str:
        for v in self.values:
            if v in s:
                self.hits += s.count(v)
                s = s.replace(v, "[REDACTED]")
        s, n = KEY_SHAPES.subn("[REDACTED]", s)
        self.hits += n
        return s


def short(s: str, n: int) -> str:
    s = s.strip()
    return s if len(s) <= n else s[:n].rstrip() + f" … [{len(s) - n:,} more characters]"


def tool_line(b: dict) -> str:
    name, inp = b.get("name", "tool"), b.get("input") or {}
    what = inp.get("description") or inp.get("file_path") or inp.get("pattern") or inp.get("query") or ""
    body = inp.get("command") or inp.get("content") or inp.get("new_string") or inp.get("prompt") or ""
    if not body and inp:
        body = json.dumps({k: v for k, v in inp.items() if k != "description"}, ensure_ascii=False)
    head = f"**{name}**" + (f": {what}" if what else "")
    return head + (f"\n\n```\n{short(str(body), TOOL_INPUT)}\n```" if body else "")


def result_text(b: dict) -> str:
    c = b.get("content")
    if isinstance(c, list):
        c = "\n".join(x.get("text", "[image]") if isinstance(x, dict) else str(x) for x in c)
    return short(str(c or ""), TOOL_RESULT)


def export(path: Path, scrub: Scrubber) -> tuple[str, int]:
    lines, msgs, day = [], 0, None
    for raw in path.open():
        r = json.loads(raw)
        kind, m = r.get("type"), r.get("message") or {}
        if kind not in ("user", "assistant") or r.get("isMeta"):
            continue
        ts = r.get("timestamp", "")
        if ts[:10] != day:
            day = ts[:10]
            lines.append(f"\n## {datetime.fromisoformat(ts[:10]).strftime('%A %-d %B %Y')}\n")
        content = m.get("content")
        blocks = [{"type": "text", "text": content}] if isinstance(content, str) else (content or [])
        for b in blocks:
            t = b.get("type")
            if kind == "user" and t == "text":
                text = REMINDER.sub("", b.get("text", "")).strip()
                if not text or text.startswith("<command-") or text.startswith("[Request interrupted"):
                    continue
                if text.startswith("This session is being continued"):
                    lines.append(f"<details><summary>Context summary (the conversation outgrew one window)</summary>\n\n"
                                 f"{scrub(text)}\n\n</details>\n")
                else:
                    lines.append(f"### Person\n\n{scrub(text)}\n")
                    msgs += 1
            elif kind == "user" and t == "document":
                lines.append("### Person\n\n*[attached a PDF document]*\n")
            elif kind == "user" and t == "tool_result":
                lines.append(f"<sub>result:</sub>\n\n```\n{scrub(result_text(b))}\n```\n")
            elif kind == "assistant" and t == "text" and b.get("text", "").strip():
                lines.append(f"### Claude\n\n{scrub(b['text'].strip())}\n")
            elif kind == "assistant" and t == "tool_use":
                lines.append(f"- {scrub(tool_line(b))}\n")
    return "\n".join(lines), msgs


def main() -> None:
    files = [Path(a).expanduser() for a in sys.argv[1:]]
    if not files:
        sys.exit("name the session .jsonl file(s)")
    OUT.mkdir(parents=True, exist_ok=True)
    scrub = Scrubber()
    for f in files:
        body, msgs = export(f, scrub)
        out = OUT / f"claude-code-{f.stem[:8]}.md"
        out.write_text("# FINN build conversation (Claude Code)\n\n"
                       "Exported with scripts/export_build_history.py. Messages and replies are complete; tool calls and "
                       "results are shortened; secrets are removed.\n" + body)
        print(f"{out.relative_to(ROOT)}: {msgs} messages from the person, {out.stat().st_size / 1e6:.1f} MB")
    print(f"secrets removed: {scrub.hits}")


if __name__ == "__main__":
    main()
