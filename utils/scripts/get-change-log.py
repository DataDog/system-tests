import requests

page = 1

data = []

for page in range(1, 5):
    r = requests.get(
        "https://api.github.com/repos/DataDog/system-tests/pulls",
        params={"state": "closed", "per_page": 100, "page": page},
        timeout=10,
    )

    data += [pr for pr in r.json() if pr["merged_at"]]

data.sort(key=lambda pr: pr["merged_at"], reverse=True)

month = None

for pr in data:

    pr["merged_at"] = pr["merged_at"][:10]
    pr["author"] = pr["user"]["login"]

    if month != pr["merged_at"][:7]:
        month = pr["merged_at"][:7]
        print(f"\n\n### {month}\n")

    print("* {merged_at} [{title}]({html_url}) by @{author}".format(**pr))
