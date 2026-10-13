"""Rebuild the contributions table in README.md from merged and open pull requests."""
import json
import os
import re
import urllib.parse
import urllib.request

USER = os.environ.get("GH_USER", "VanditGupta")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
API = "https://api.github.com"
VISIBLE = 10
START, END = "<!-- CONTRIBUTIONS:START -->", "<!-- CONTRIBUTIONS:END -->"


def get(path, params=None):
    url = API + path + ("?" + urllib.parse.urlencode(params) if params else "")
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "profile-contributions"}
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers)) as resp:
        return json.load(resp)


def pr_counts():
    """Count merged and open pull requests per repo (closed-unmerged ones are skipped)."""
    counts = {}
    for state in ("is:merged", "is:open"):
        page = 1
        while page <= 10:
            data = get("/search/issues", {
                "q": f"author:{USER} type:pr {state} -user:{USER}",
                "per_page": 100,
                "page": page,
            })
            for item in data["items"]:
                repo = item["repository_url"].split("/repos/", 1)[1]
                counts[repo] = counts.get(repo, 0) + 1
            if len(data["items"]) < 100:
                break
            page += 1
    return counts


def fmt_stars(n):
    return f"{n / 1000:.1f}k" if n >= 1000 else str(n)


def clean(text, limit=100):
    text = (text or "").replace("|", "/").replace("\n", " ").strip()
    return text if len(text) <= limit else text[: limit - 1] + "…"


def build_table(rows):
    lines = [
        "| Repository | Stars | Pull Requests | Language | Description |",
        "|:---|:---:|:---:|:---:|:---|",
    ]
    for r in rows:
        lines.append(
            f"| [**{r['full_name']}**]({r['html_url']}) | {fmt_stars(r['stargazers_count'])} "
            f"| {r['prs']} | {r['language'] or '-'} | {clean(r['description'])} |"
        )
    return "\n".join(lines)


def main():
    print(f"Fetching pull requests for {USER}...")
    counts = pr_counts()
    rows = []
    for full_name, prs in counts.items():
        try:
            info = get(f"/repos/{full_name}")
        except Exception as exc:  # repo deleted or private
            print(f"Skipping {full_name}: {exc}")
            continue
        if info.get("private"):
            continue  # never list private repositories on a public profile
        info["prs"] = prs
        rows.append(info)
    rows.sort(key=lambda r: (-r["stargazers_count"], -r["prs"]))
    print(f"Found {len(rows)} contributed repositories")

    if not rows:
        body = "_Open-source contributions will appear here._"
    else:
        body = build_table(rows[:VISIBLE])
        if len(rows) > VISIBLE:
            body += (
                f"\n\n<details>\n<summary>Show more ({len(rows) - VISIBLE} repositories)</summary>\n\n"
                + build_table(rows[VISIBLE:])
                + "\n\n</details>"
            )

    with open("README.md", encoding="utf-8", newline="") as fh:
        readme = fh.read()
    block = f"{START}\n{body}\n{END}"
    new, n = re.subn(re.escape(START) + r".*?" + re.escape(END), lambda _: block, readme, flags=re.S)
    if n != 1:
        raise SystemExit("Contribution markers not found in README.md")
    if new != readme:
        with open("README.md", "w", encoding="utf-8", newline="") as fh:
            fh.write(new)
        print("Updated README.md")
    else:
        print("README.md already up to date")


if __name__ == "__main__":
    main()
