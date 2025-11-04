import yaml
from semantic_version import Version

variants = {
    "agent": set(),
    "cpp_httpd": set(),
    "cpp_nginx": set(),
    "cpp": set(),
    "dd_apm_inject": set(),
    "dotnet": {"poc", "uds"},
    "golang": {
        "chi",
        "echo",
        "gin",
        "gqlgen",
        "graph-gophers",
        "graphql-go",
        "net-http-orchestrion",
        "net-http",
        "uds-echo",
    },
    "java": {
        "akka-http",
        "jersey-grizzly2",
        "play",
        "ratpack",
        "resteasy-netty3",
        "spring-boot-3-native",
        "spring-boot-jetty",
        "spring-boot-openliberty",
        "spring-boot-payara",
        "spring-boot-undertow",
        "spring-boot-wildfly",
        "spring-boot",
        "uds-spring-boot",
        "vertx3",
        "vertx4",
    },
    "k8s_cluster_agent": set(),
    "nodejs": {
        "express4-typescript",
        "express4",
        "express5",
        "fastify",
        "nextjs",
        "uds-express4",
    },
    "php": {
        "apache-mod-7.0-zts",
        "apache-mod-7.0",
        "apache-mod-7.1-zts",
        "apache-mod-7.1",
        "apache-mod-7.2-zts",
        "apache-mod-7.2",
        "apache-mod-7.3-zts",
        "apache-mod-7.3",
        "apache-mod-7.4-zts",
        "apache-mod-7.4",
        "apache-mod-8.0-zts",
        "apache-mod-8.0",
        "apache-mod-8.1-zts",
        "apache-mod-8.1",
        "apache-mod-8.2-zts",
        "apache-mod-8.2",
        "php-fpm-7.0",
        "php-fpm-7.1",
        "php-fpm-7.2",
        "php-fpm-7.3",
        "php-fpm-7.4",
        "php-fpm-8.0",
        "php-fpm-8.1",
        "php-fpm-8.2",
    },
    "python_lambda": {
        "alb-multi",
        "alb",
        "apigw-http",
        "apigw-rest",
        "function-url",
    },
    "python_otel": {
        "flask-poc-otel",
    },
    "python": {
        "django-poc",
        "fastapi",
        "flask-poc",
        "uds-flask",
        "uwsgi-poc",
        "django-py3.13",
        "python3.12",
    },
    "ruby": {
        "graphql23",
        "rack",
        "rails42",
        "rails52",
        "rails61",
        "rails72",
        "rails80",
        "sinatra14",
        "sinatra22",
        "sinatra32",
        "sinatra41",
        "uds-rails",
        "uds-sinatra",
    },
    "rust": set(),
}

output = ""


def count(node_id: str) -> int | float:
    if node_id.endswith(".py::"):
        count = 0
        scenario = False
        with open(node_id[:-2]) as f:
            for line in f:
                if line.startswith(("@scenarios", "@features")):
                    scenario = True
                if line.startswith("class ") and scenario:
                    count += 1
                    scenario = False
        return count
    # if node_id.endswith("::"):
    #     print(node_id)
    #     return 0
    return float("inf")


def flatten(
    data: dict | str,
    lib: str,
    refs: dict,
    root: str = "tests/",
    end: bool = False,  # noqa: FBT001, FBT002
    leaves: set | None = None,
) -> set | None:
    global output  # noqa: PLW0603
    if not leaves:
        leaves = set()
    if isinstance(data, str):
        # print(f"{root}: {data}")
        if refs and data in refs:
            data_str = f"*{refs[data]}"
            if "||" in data:
                output += f"{root}:\n    - library_version: {data_str}\n      declaration: missing_feature\n"
            else:
                output += f"{root}: {data_str}\n"
        else:
            output += f'{root}: "{data}"\n'
    elif end:
        root = f"{root}:"
        variants_set = set()
        for var in data.items():
            if var[0] != "*":
                variants_set.add(var[0])
        for var in data.items():
            leaf = "  - "
            if var[0] == "*":
                if len(variants_set) == 0:
                    leaves.add(f' "{var[1]}"')
                    continue
                if len(variants_set) > len(variants[lib]) // 2:
                    leaf += f"variant: {variants[lib] - variants_set}\n    "
                    leaf = leaf.replace("{", "[").replace("}", "]").replace("'", "")
                else:
                    leaf += f"excluded_variant: {variants_set}\n    "
                    leaf = leaf.replace("{", "[").replace("}", "]").replace("'", "")
            else:
                leaf += f"variant: {var[0]}\n    "
            if var[1].startswith(("v", "<", ">")):
                if refs and var[1] in refs and "||" in var[1]:
                    data_str = f"*{refs[var[1]]}"
                else:
                    data_str = f'"<{var[1][1:].strip('=')}"'
                leaf += f"library_version: {data_str}"
                leaf += "\n    declaration: missing_feature"
            else:
                leaf += f"declaration: {var[1]}"
            leaves.add(leaf)

    else:
        branch_leaves = {}
        if root.endswith(".py"):
            root += "::"
            end = True

        for item in data.items():
            res = flatten(item[1], lib, refs, root + item[0], end)
            if res:
                branch_leaves[root + item[0]] = res

        leaves_count = {}
        for branch in branch_leaves.values():
            for leave in branch:
                if leave not in leaves_count:
                    leaves_count[leave] = 0
                leaves_count[leave] += 1

        for leaf in leaves_count.items():
            if leaf[1] >= count(root):
                leaves.add(leaf[0])

        for branch, bleaves in branch_leaves.items():
            p_branch = True
            bleaves = sorted(bleaves)  # noqa: PLW2901
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


def yml_sort(output_file: str) -> None:
    global output  # noqa: PLW0602
    data = []
    for line in output.splitlines():
        if line.startswith(" "):
            data[-1][1].append(line)
        else:
            data.append((line, []))
    data.sort(key=lambda x: x[0][: x[0].rfind(":")])

    with open(output_file, "a") as f:
        for entry in data:
            f.write("  " + entry[0] + "\n")
            for line in entry[1]:
                f.write("  " + line + "\n")


def add_refs(file_path: str, output_file: str) -> None:
    global output  # noqa: PLW0602
    with open(file_path) as f:
        data = f.readlines()
    with open(output_file, "w") as f:
        for line in data:
            if line.startswith("tests/:"):
                # print("manifest:")
                f.write("manifest:" + "\n")
                return
            # print(line, end="")
            f.write(line)


def update_refs(file_path: str) -> None:
    if "nodejs" not in file_path:
        return None
    with open(file_path, "r") as f:
        lines = f.readlines()

    refs = {}
    for iline, line in enumerate(lines):
        if line.startswith("tests"):
            break
        if "refs:" in line or "---" in line:
            continue
        # print(line)

        semver_range = line[line.find("'") + 1 : line.rfind("'")]
        ref = line[line.find("&") + 1 : line.find(" '")]
        refs[semver_range] = ref

        if "||" not in line:
            continue

        elements = semver_range.split(" || ")
        if " - " in elements[0]:
            mrel = elements[0].split(" - ")
            main_range = f">{mrel[1]} || <{mrel[0]}"
        else:
            main_range = f"<{elements[0][2:]}"

        new_ranges = []
        for element in elements[1:]:
            version = Version(element[1:])
            new_ranges.append(f">={version.next_major()} || <{version}")
        new_line = line[: line.find("'") + 1] + main_range
        for new_range in new_ranges:
            new_line += f" {new_range}"
        new_line += line[line.rfind("'") :]
        # print(new_line)
        semver_range = new_line[new_line.find("'") + 1 : new_line.rfind("'")]
        refs[semver_range] = ref
        lines[iline] = new_line

    with open(file_path, "w") as file:
        file.writelines(lines)

    return refs


def main() -> None:
    global output  # noqa: PLW0603
    for lib in variants:
        output = ""
        file_path = f"./manifests/{lib}.yml"
        output_file = f"./new.manifests/{lib}.yml"

        refs = update_refs(file_path)

        add_refs(file_path, output_file)
        with open(file_path) as f:
            data = yaml.safe_load(f)
            # print(refs)
            flatten(data["tests/"], lib, refs)

        yml_sort(output_file)


if __name__ == "__main__":
    main()
