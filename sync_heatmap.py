#!/usr/bin/env python3
"""Fetch GitLab contribution heatmap and push to this GitHub repo."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
CALENDAR_PATH = DATA_DIR / "calendar.json"
SVG_PATH = ROOT / "heatmap.svg"
README_PATH = ROOT / "README.md"
META_PATH = DATA_DIR / "meta.json"

GITLAB_URL = os.environ.get("GITLAB_URL", "http://192.168.10.174:9181").rstrip("/")
GITLAB_TOKEN = os.environ.get("GITLAB_TOKEN", "").strip()
GITLAB_USER_ID = os.environ.get("GITLAB_USER_ID", "15").strip()
GITLAB_USERNAME = os.environ.get("GITLAB_USERNAME", "jianjiale").strip()

# GitLab-ish blue levels (0 empty -> 4 high)
LEVEL_COLORS = ["#ebedf0", "#9be9a8", "#40c463", "#30a14e", "#216e39"]
# Prefer cool teal closer to GitLab profile blues if preferred later:
# LEVEL_COLORS = ["#ededed", "#acd5f2", "#7fa8c9", "#527ba0", "#254e77"]


def die(msg: str, code: int = 1) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)
    raise SystemExit(code)


def http_get_json(url: str) -> tuple[object, dict]:
    req = urllib.request.Request(url, headers={"PRIVATE-TOKEN": GITLAB_TOKEN})
    with urllib.request.urlopen(req, timeout=60) as resp:
        body = resp.read().decode("utf-8")
        headers = {k.lower(): v for k, v in resp.headers.items()}
        return json.loads(body), headers


def fetch_events(after: str) -> list[dict]:
    events: list[dict] = []
    page = 1
    while True:
        url = (
            f"{GITLAB_URL}/api/v4/users/{GITLAB_USER_ID}/events"
            f"?after={after}&per_page=100&page={page}&sort=asc"
        )
        batch, headers = http_get_json(url)
        if not isinstance(batch, list) or not batch:
            break
        events.extend(batch)
        total_pages = int(headers.get("x-total-pages") or "1")
        print(f"fetched page {page}/{total_pages} (+{len(batch)})")
        if page >= total_pages:
            break
        page += 1
    return events


def aggregate_calendar(events: list[dict]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for event in events:
        created = event.get("created_at") or ""
        if len(created) >= 10:
            counts[created[:10]] += 1
    return {day: counts[day] for day in sorted(counts)}


def level_for(count: int, max_count: int) -> int:
    if count <= 0:
        return 0
    if max_count <= 1:
        return 4
    # 4 non-empty buckets
    ratio = count / max_count
    if ratio > 0.75:
        return 4
    if ratio > 0.5:
        return 3
    if ratio > 0.25:
        return 2
    return 1


def render_svg(calendar: dict[str, int], end: date, days: int = 365) -> str:
    start = end - timedelta(days=days - 1)
    # Align columns to weeks starting Monday
    while start.weekday() != 0:
        start -= timedelta(days=1)

    max_count = max(calendar.values()) if calendar else 0
    cell = 12
    gap = 3
    left = 36
    top = 20
    weeks = ((end - start).days // 7) + 1
    width = left + weeks * (cell + gap) + 10
    height = top + 7 * (cell + gap) + 40

    rects: list[str] = []
    day = start
    week_i = 0
    while day <= end:
        dow = day.weekday()  # Mon=0 .. Sun=6
        key = day.isoformat()
        count = calendar.get(key, 0)
        lvl = level_for(count, max_count)
        x = left + week_i * (cell + gap)
        y = top + dow * (cell + gap)
        title = f"{key}: {count} contribution{'s' if count != 1 else ''}"
        rects.append(
            f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" rx="2" '
            f'fill="{LEVEL_COLORS[lvl]}" data-date="{key}" data-count="{count}">'
            f"<title>{title}</title></rect>"
        )
        day += timedelta(days=1)
        if day.weekday() == 0:
            week_i += 1

    labels = []
    for i, name in enumerate(["Mon", "", "Wed", "", "Fri", "", ""]):
        labels.append(
            f'<text x="0" y="{top + i * (cell + gap) + cell - 2}" '
            f'font-size="10" fill="#666">{name}</text>'
        )

    legend_x = left
    legend_y = top + 7 * (cell + gap) + 18
    legend = [
        f'<text x="{legend_x}" y="{legend_y}" font-size="10" fill="#666">Less</text>'
    ]
    lx = legend_x + 32
    for color in LEVEL_COLORS:
        legend.append(
            f'<rect x="{lx}" y="{legend_y - 10}" width="{cell}" height="{cell}" '
            f'rx="2" fill="{color}"/>'
        )
        lx += cell + gap
    legend.append(
        f'<text x="{lx + 4}" y="{legend_y}" font-size="10" fill="#666">More</text>'
    )

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'role="img" aria-label="GitLab contribution heatmap for {GITLAB_USERNAME}">\n'
        f'<rect width="100%" height="100%" fill="#ffffff"/>\n'
        + "\n".join(labels)
        + "\n"
        + "\n".join(rects)
        + "\n"
        + "\n".join(legend)
        + "\n</svg>\n"
    )


def write_readme(calendar: dict[str, int], synced_at: str, range_start: str, range_end: str) -> None:
    total = sum(calendar.values())
    active_days = len(calendar)
    peak_day = ""
    peak_count = 0
    if calendar:
        peak_day, peak_count = max(calendar.items(), key=lambda kv: kv[1])

    content = f"""# GitLab Contribution Heatmap

Auto-synced from [{GITLAB_USERNAME}]({GITLAB_URL}/{GITLAB_USERNAME}) on weekdays at 10:00 (local).

![heatmap](./heatmap.svg)

| | |
|---|---|
| Synced at | `{synced_at}` |
| Range | `{range_start}` → `{range_end}` |
| Contributions | **{total}** |
| Active days | **{active_days}** |
| Peak day | `{peak_day}` (**{peak_count}**) |

Source: GitLab Events API → daily aggregation (same idea as profile `calendar.json`).
"""
    README_PATH.write_text(content, encoding="utf-8")


def git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def commit_and_push(synced_at: str) -> None:
    status = git("status", "--porcelain")
    if status.returncode != 0:
        die(status.stderr or "git status failed")
    if not status.stdout.strip():
        print("no file changes; skip commit/push")
        return

    add = git("add", "data/calendar.json", "data/meta.json", "heatmap.svg", "README.md")
    if add.returncode != 0:
        die(add.stderr or "git add failed")

    msg = f"chore: sync GitLab heatmap ({synced_at[:10]})"
    commit = git("commit", "-m", msg)
    if commit.returncode != 0:
        die(commit.stderr or commit.stdout or "git commit failed")
    print(commit.stdout.strip() or "committed")

    push = git("push", "origin", "HEAD")
    if push.returncode != 0:
        die(push.stderr or push.stdout or "git push failed")
    print(push.stdout.strip() or push.stderr.strip() or "pushed")


def main() -> None:
    if not GITLAB_TOKEN:
        die("GITLAB_TOKEN is not set")

    end = date.today()
    start = end - timedelta(days=364)
    after = (start - timedelta(days=1)).isoformat()

    print(f"syncing {GITLAB_USERNAME} from {GITLAB_URL} after={after}")
    try:
        events = fetch_events(after)
    except urllib.error.HTTPError as e:
        die(f"GitLab HTTP {e.code}: {e.read().decode('utf-8', errors='replace')[:300]}")
    except urllib.error.URLError as e:
        die(f"GitLab unreachable: {e}")

    calendar = aggregate_calendar(events)
    # Keep only last ~365 days of keys that fall in window
    calendar = {
        day: count
        for day, count in calendar.items()
        if start.isoformat() <= day <= end.isoformat()
    }

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    CALENDAR_PATH.write_text(
        json.dumps(calendar, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    synced_at = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    meta = {
        "source": f"{GITLAB_URL}/api/v4/users/{GITLAB_USER_ID}/events",
        "username": GITLAB_USERNAME,
        "user_id": GITLAB_USER_ID,
        "synced_at": synced_at,
        "range_start": start.isoformat(),
        "range_end": end.isoformat(),
        "events": len(events),
        "contributions": sum(calendar.values()),
        "active_days": len(calendar),
    }
    META_PATH.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    SVG_PATH.write_text(render_svg(calendar, end), encoding="utf-8")
    write_readme(calendar, synced_at, start.isoformat(), end.isoformat())

    print(
        f"wrote calendar days={len(calendar)} contributions={sum(calendar.values())} "
        f"events={len(events)}"
    )

    skip_push = "--no-push" in sys.argv
    if skip_push:
        print("skip push (--no-push)")
        return
    commit_and_push(synced_at)


if __name__ == "__main__":
    main()
