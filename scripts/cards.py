import json
import os
import sys
import urllib.request
from datetime import datetime, timezone
from html import escape
from pathlib import Path

USER = "onlyhvh"
HANDLE = "wakedev"

FETCH = [
    ("OS", "Windows 10"),
    ("Host", f"github.com/{USER}"),
    ("Uptime", None),
    ("Languages", "C++, Python, Java, C#, JavaScript"),
    ("Interests", "low-level, reverse engineering, VMs"),
    ("Tools", "Visual Studio, CMake, Ghidra, Git"),
    ("Mail", "wakedev@mail.ru"),
]

COLORS = {
    "C++": "#f34b7d", "C": "#555555", "C#": "#178600", "Python": "#3572A5", "Java": "#b07219",
    "JavaScript": "#f1e05a", "TypeScript": "#3178c6", "HTML": "#e34c26", "CSS": "#663399",
    "CMake": "#DA3434", "Shell": "#89e051", "Dockerfile": "#384d54", "Kotlin": "#A97BFF",
    "Rust": "#dea584", "Go": "#00ADD8", "Lua": "#000080", "PowerShell": "#012456", "Batchfile": "#C1F12E",
}

THEMES = {
    "dark": {"bg": "#0d1117", "chrome": "#161b22", "border": "#30363d", "text": "#e6edf3",
             "muted": "#7d8590", "user": "#3fb950", "path": "#58a6ff", "key": "#79c0ff", "track": "#21262d"},
    "light": {"bg": "#ffffff", "chrome": "#f6f8fa", "border": "#d0d7de", "text": "#1f2328",
              "muted": "#656d76", "user": "#1a7f37", "path": "#0969da", "key": "#0550ae", "track": "#eaeef2"},
}

FONT = "ui-monospace,SFMono-Regular,'SF Mono',Menlo,Consolas,'Liberation Mono',monospace"
W = 830
PAD = 28
LINE = 22
SIZE = 14
CHAR = SIZE * 0.6


def api(path, token=None, body=None):
    url = path if path.startswith("http") else f"https://api.github.com{path}"
    req = urllib.request.Request(url, data=json.dumps(body).encode() if body else None)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("User-Agent", f"{USER}-profile")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def collect(token):
    user = api(f"/users/{USER}", token)
    repos = [r for r in api(f"/users/{USER}/repos?per_page=100&type=owner", token) if not r["fork"]]

    languages = {}
    for r in repos:
        for lang, size in api(r["languages_url"], token).items():
            languages[lang] = languages.get(lang, 0) + size

    try:
        commits = api(f"/search/commits?q=author:{USER}&per_page=1", token)["total_count"]
    except Exception:
        commits = None

    contributions = None
    if token:
        query = "query($l:String!){user(login:$l){contributionsCollection{contributionCalendar{totalContributions}}}}"
        try:
            data = api("https://api.github.com/graphql", token, {"query": query, "variables": {"l": USER}})
            contributions = data["data"]["user"]["contributionsCollection"]["contributionCalendar"]["totalContributions"]
        except Exception:
            pass

    return {
        "created": datetime.fromisoformat(user["created_at"].replace("Z", "+00:00")),
        "followers": user["followers"],
        "repos": len(repos),
        "stars": sum(r["stargazers_count"] for r in repos),
        "commits": commits,
        "contributions": contributions,
        "languages": sorted(languages.items(), key=lambda kv: -kv[1]),
    }


def uptime(since):
    now = datetime.now(timezone.utc)
    months = (now.year - since.year) * 12 + now.month - since.month - (now.day < since.day)
    years, months = divmod(months, 12)
    total = since.month - 1 + years * 12 + months
    anchor = since.replace(year=since.year + total // 12, month=total % 12 + 1)
    days = (now - anchor).days

    def unit(n, word):
        return f"{n} {word}{'' if n == 1 else 's'}"

    return ", ".join(([unit(years, "year")] if years else []) + [unit(months, "month"), unit(days, "day")])


def text(x, y, spans, t):
    parts = []
    for s, color, bold in spans:
        weight = ' font-weight="600"' if bold else ""
        parts.append(f'<tspan fill="{t[color]}"{weight}>{escape(s)}</tspan>')
    return f'<text x="{x}" y="{y:.0f}" xml:space="preserve">{"".join(parts)}</text>'


def prompt(command):
    return [(f"{HANDLE}@github", "user", True), (":", "text", False), ("~", "path", True),
            ("$ ", "text", False), (command, "text", False)]


def terminal(stats, t):
    body, y = [], 44 + PAD + 4

    body.append(text(PAD, y, prompt("fetch"), t))
    y += LINE * 1.4
    body.append(text(PAD, y, [(HANDLE, "user", True), ("@", "text", False), ("github", "user", True)], t))
    y += LINE * 0.9
    body.append(text(PAD, y, [("-" * len(f"{HANDLE}@github"), "muted", False)], t))
    for key, value in FETCH:
        y += LINE
        body.append(text(PAD, y, [(f"{key}:", "key", True), (" " * (11 - len(key)), "text", False),
                                  (value or uptime(stats["created"]), "text", False)], t))

    y += LINE * 1.6
    body.append(text(PAD, y, prompt(f"gh api users/{USER}"), t))
    y += LINE * 1.4
    cells = [("repos", stats["repos"]), ("stars", stats["stars"]), ("commits", stats["commits"]),
             ("followers", stats["followers"])]
    if stats["contributions"] is not None:
        cells.append(("contributions this year", stats["contributions"]))
    spans = []
    for name, value in cells:
        spans += [(name, "muted", False), (" ", "text", False),
                  ("-" if value is None else f"{value:,}", "text", True), ("    ", "text", False)]
    body.append(text(PAD, y, spans, t))

    langs = stats["languages"][:6]
    total = sum(size for _, size in langs) or 1
    y += LINE * 0.9
    bar_w = W - PAD * 2
    body.append(f'<clipPath id="bar"><rect x="{PAD}" y="{y:.0f}" width="{bar_w}" height="8" rx="4"/></clipPath>')
    body.append(f'<g clip-path="url(#bar)"><rect x="{PAD}" y="{y:.0f}" width="{bar_w}" height="8" fill="{t["track"]}"/>')
    x = PAD
    for lang, size in langs:
        seg = bar_w * size / total
        body.append(f'<rect x="{x:.1f}" y="{y:.0f}" width="{max(seg - 2, 1):.1f}" height="8" fill="{COLORS.get(lang, t["muted"])}"/>')
        x += seg
    body.append("</g>")

    y += 8 + LINE
    x = PAD
    for lang, size in langs:
        pct = f" {size * 100 / total:.1f}%"
        body.append(f'<circle cx="{x + 4:.1f}" cy="{y - 4.5:.1f}" r="4" fill="{COLORS.get(lang, t["muted"])}"/>')
        body.append(f'<text x="{x + 13:.1f}" y="{y:.0f}" font-size="12" xml:space="preserve">'
                    f'<tspan fill="{t["text"]}" font-weight="600">{escape(lang)}</tspan><tspan fill="{t["muted"]}">{pct}</tspan></text>')
        x += 13 + (len(lang) + len(pct)) * 12 * 0.6 + 20

    y += LINE * 1.6
    cursor_x = PAD + len(f"{HANDLE}@github:~$ ") * CHAR
    body.append(text(PAD, y, prompt(""), t))
    body.append(f'<rect class="cursor" x="{cursor_x:.1f}" y="{y - SIZE + 2:.0f}" width="{CHAR:.1f}" height="{SIZE + 2}" fill="{t["text"]}"/>')

    h = int(y + PAD)
    head = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{h}" viewBox="0 0 {W} {h}" font-family="{FONT}" font-size="{SIZE}">',
        "<style>.cursor{animation:blink 1.1s steps(1) infinite}@keyframes blink{50%{opacity:0}}"
        "@media (prefers-reduced-motion:reduce){.cursor{animation:none}}</style>",
        f'<rect x=".5" y=".5" width="{W - 1}" height="{h - 1}" rx="8" fill="{t["bg"]}" stroke="{t["border"]}"/>',
        f'<path d="M1 44V9a8 8 0 0 1 8-8h{W - 18}a8 8 0 0 1 8 8v35Z" fill="{t["chrome"]}"/>',
        f'<line x1="1" y1="44.5" x2="{W - 1}" y2="44.5" stroke="{t["border"]}"/>',
    ]
    for i, color in enumerate(("#ff5f57", "#febc2e", "#28c840")):
        head.append(f'<circle cx="{22 + i * 20}" cy="22.5" r="6" fill="{color}"/>')
    head.append(f'<text x="{W / 2}" y="27" text-anchor="middle" font-size="12" fill="{t["muted"]}">{HANDLE}@github: ~</text>')
    return "\n".join(head + body + ["</svg>"])


def main():
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "dist")
    out.mkdir(parents=True, exist_ok=True)
    stats = collect(os.environ.get("GITHUB_TOKEN"))
    for name, theme in THEMES.items():
        (out / f"terminal-{name}.svg").write_text(terminal(stats, theme), encoding="utf-8")
    print(f"repos={stats['repos']} stars={stats['stars']} commits={stats['commits']} "
          f"contributions={stats['contributions']} languages={[l for l, _ in stats['languages'][:6]]}")


if __name__ == "__main__":
    main()
