from collections import defaultdict
import requests

page = 1

data = defaultdict(list)

for page in range(1, 7):
    r = requests.get(
        "https://api.github.com/repos/DataDog/system-tests/pulls",
        params={"state": "closed", "per_page": "100", "page": str(page)},
        timeout=10,
    )

    for pr in r.json():
        if pr["merged_at"]:
            data[pr["merged_at"][:7]].append(pr)

for month in sorted(data, reverse=True):
    prs = data[month]

    print(f"\n\n### {month} ({len(prs)} PR merged)\n")
    for pr in prs:
        pr["merged_at"] = pr["merged_at"][:10]
        pr["author"] = pr["user"]["login"]
        print("* {merged_at} [{title}]({html_url}) by @{author}".format(**pr))
