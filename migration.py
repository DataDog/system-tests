import ruamel.yaml

weblogs = {
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


def quotes(string: str) -> str:
    if ">" in string or ":" in string:
        return f'"{string}"'
    return string


def get_comment(commented_obj: dict, key: str) -> str:
    """Extract EOL comment from ruamel.yaml CommentedMap for a given key."""
    if not hasattr(commented_obj, "ca"):
        return ""
    ca = commented_obj.ca
    if not ca or not hasattr(ca, "items"):
        return ""
    items = ca.items
    if key not in items or len(items[key]) < 3:  # noqa: PLR2004
        return ""
    comment_token = items[key][2]  # EOL comment is at index 2
    if comment_token:
        comment_str = comment_token.value.strip()
        return f"  {comment_str}" if comment_str else ""
    return ""


def flatten(
    data: dict | str,
    lib: str,
    refs: dict,
    root: str = "tests/",
    end: bool = False,  # noqa: FBT001, FBT002
    _leaves: set | None = None,
    commented_data: dict | None = None,
    current_key: str | None = None,
) -> set | None:
    global output  # noqa: PLW0603

    if isinstance(data, str):
        comment = ""
        if commented_data and current_key and hasattr(commented_data, "ca"):
            comment = get_comment(commented_data, current_key)
        if refs and data in refs:
            data_str = f"*{refs[data]}"
            line = f"\n{root}: {data_str}"
            if comment:
                line += comment
            output += line
        else:
            line = f"\n{root}: {quotes(data)}"
            if comment:
                line += comment
            output += line
    elif end:
        output += f"\n{root}:"
        # For variant declarations, data itself is the CommentedMap containing the variants
        variant_commented = data if isinstance(data, dict) and hasattr(data, "ca") else commented_data
        for var in data.items():
            var_name = var[0]
            if var[0] == "*":
                var_name = f'"{var[0]}"'
            data_str = f"*{refs[var[1]]}" if refs and var[1] in refs else f"{quotes(var[1])}"
            comment = ""
            if variant_commented and hasattr(variant_commented, "ca"):
                comment = get_comment(variant_commented, var[0])
            line = f"\n    {var_name}: {data_str}"
            if comment:
                line += comment
            output += line

    else:
        if root.endswith(".py"):
            root += "::"
            end = True

        for item in data.items():
            key = item[0]
            # Pass the current level's CommentedMap as parent, and current key
            sub_commented = data if isinstance(data, dict) and hasattr(data, "ca") else commented_data
            flatten(item[1], lib, refs, root + key, end, commented_data=sub_commented, current_key=key)


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
            if entry[1]:
                f.write("    - weblog_declaration:\n")
            for line in entry[1]:
                f.write("    " + line + "\n")


def add_refs(file_path: str, output_file: str) -> None:
    global output  # noqa: PLW0602
    with open(file_path) as f:
        data = f.readlines()
    with open(output_file, "w") as f:
        for line in data:
            if line.startswith("tests/:"):
                f.write("manifest:")
                return
            f.write(line)


def get_refs(file_path: str) -> None:
    if "nodejs" not in file_path:
        return None
    with open(file_path, "r") as f:
        lines = f.readlines()

    refs = {}
    for _iline, line in enumerate(lines):
        if line.startswith("tests"):
            break
        if "refs:" in line or "---" in line:
            continue

        semver_range = line[line.find("'") + 1 : line.rfind("'")]
        ref = line[line.find("&") + 1 : line.find(" '")]
        refs[semver_range] = ref

    return refs


def main() -> None:
    global output  # noqa: PLW0603
    for lib in weblogs:
        output = ""
        file_path = f"./manifests/{lib}.yml"
        output_file = f"./new.manifests/{lib}.yml"

        refs = get_refs(file_path)

        add_refs(file_path, output_file)
        with open(file_path) as file:
            yaml = ruamel.yaml.YAML()
            yaml.preserve_quotes = True
            data = yaml.load(file)
            tests_data = data.get("tests/") or data.get("manifest")
            if tests_data:
                flatten(tests_data, lib, refs, commented_data=tests_data)

        yml_sort(output_file)


if __name__ == "__main__":
    main()
