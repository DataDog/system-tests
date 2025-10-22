import yaml
from collections import OrderedDict

variants = {
        "django-poc",
        "fastapi",
        "flask-poc",
        "uds-flask",
        "uwsgi-poc",
        "django-py3.13",
        "python3.12",
        }

output = ""

def count(node_id: str):
    # if node_id == "tests/serverless/span_pointers/aws/test_s3_span_pointers.py::":
    #     breakpoint()
    if node_id.endswith(".py::"):
        count = 0
        scenario = False
        with open(node_id[:-2]) as f:
            for line in f.readlines():
                if line.startswith("@scenarios") or line.startswith("@features"):
                    scenario = True
                if line.startswith("class ") and scenario:
                    count += 1
                    scenario = False
        return count
    # if node_id.endswith("::"):
    #     print(node_id)
    #     return 0
    else:
        return float("inf")



def flatten(data, root = "", end = False, leaves = None):
    global output
    if not leaves: leaves = set()
    if isinstance(data, str):
        # print(f"{root}: {data}")
        output += f"{root}: {data}\n"
        pass
    elif end:
        root = f"{root}:"
        vars = set()
        for var in data.items():
            if var[0] != "*":
                vars.add(var[0])
        for var in data.items():
            leaf = f"    - "
            if var[0] == "*":
                if len(vars) == 0:
                    leaves.add(f" {var[1]}")
                    continue
                elif len(vars) > len(variants) // 2:
                    leaf += f"variant: {variants - vars}\n      "
                    leaf = leaf.replace("{", "[").replace("}", "]").replace("'", "")
                else:
                    leaf += f"excluded_variant: {vars}\n      "
                    leaf = leaf.replace("{", "[").replace("}", "]").replace("'", "")
            else:
                leaf += f"variant: {var[0]}\n      "
            if var[1].startswith("v"):
                leaf += f"library_version: <{var[1][1:]}"
                leaf += f"\n      declaration: missing_feature"
            else:
                leaf += f"declaration: {var[1]}"
            leaves.add(leaf)

    else:
        branch_leaves = {}
        if root.endswith(".py"):
            root += "::"
            end = True

        for next in data.items():
            res = flatten(next[1], root + next[0], end)
            if res:
                branch_leaves[root+next[0]] = res

        leaves_count = {}
        for branch in branch_leaves.values():
            for leave in branch:
                if leave not in leaves_count:
                    leaves_count[leave] = 0
                leaves_count[leave] += 1

        for leaf in leaves_count.items():
            if leaf[1] >= count(root):
                leaves.add(leaf[0])
                pass

        for branch, bleaves in branch_leaves.items():
            # if "test_s3_span_pointers.py" in branch:
            #     breakpoint()
            p_branch = True
            bleaves = sorted(list(bleaves))
            for leaf in bleaves:
                if leaf not in leaves:
                    if p_branch:
                        # print(branch + ":")
                        output += branch + ":"
                        if len(bleaves) > 1 or len(leaf.splitlines()) > 1:
                            output += "\n"
                        p_branch = False
                    output += leaf + "\n"
                    # print(leaf)

    return leaves

def yml_sort():
    global output
    data = []
    for line in output.splitlines():
        if line.startswith(" "):
            data[-1][1].append(line)
        else:
            data.append((line, []))
    data.sort()
    # return

    for entry in data:
        print(entry[0])
        for line in entry[1]:
            print(line)



def main():
    with open("./manifests/python.yml") as f:
        data = yaml.safe_load(f)
        flatten(data)

    yml_sort()

if __name__ == "__main__":
    main()
