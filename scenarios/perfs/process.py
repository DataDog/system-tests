import json
from collections import defaultdict
from statistics import mean, stdev
from os import environ


LOG_FOLDER = environ["LOG_FOLDER"] if "LOG_FOLDER" in environ else "logs"


def get_bucket(size):
    if size < 10000:
        return "Requests < 10ko"
    elif size < 1000000:
        return "Requests < 1Mo"
    else:
        return "Requests > 1Mo"


def compute_file(filename):
    buckets = defaultdict(list)
    results = {}
    data = json.load(open(filename))
    for _, time, _, size in data["durations"]:
        buckets[get_bucket(size)].append(time)

    for b in buckets:
        items = sorted(buckets[b])
        item_count = len(items)
        t = int(item_count / 10)
        items = items[t:-t]

        results[b] = {"mean": mean(items) * 1000, "stdev": stdev(items) * 1000, "count": len(items)}

    return results


def report(bucket, without, with_, diff):
    print(f"{bucket: <16} | {without: <24} | {with_: <24} | {diff}")


def compute(lib):
    try:
        without_appsec = compute_file(f"{LOG_FOLDER}/stats_{lib}_without_appsec.json")
        with_appsec = compute_file(f"{LOG_FOLDER}/stats_{lib}_with_appsec.json")
    except FileNotFoundError:
        return

    print()
    report(f"** {lib} **", "Without Appsec", "With Appsec", "Overhead")
    print("-" * 81)
    for b in without_appsec:
        mean_without_appsec = without_appsec[b]["mean"]
        mean_with_appsec = with_appsec[b]["mean"]

        diff = mean_with_appsec - mean_without_appsec

        report(
            b,
            f"{without_appsec[b]['mean']:.2f} ±{without_appsec[b]['stdev']:.2f}",  # ({without_appsec[b]['count']})",
            f"{with_appsec[b]['mean']:.2f} ±{with_appsec[b]['stdev']:.2f}",  # ({with_appsec[b]['count']})",
            f"{diff:.2f}",
        )

    print()


def main():
    for lib in ("golang", "dotnet", "java", "nodejs", "php", "ruby"):
        compute(lib)


main()
