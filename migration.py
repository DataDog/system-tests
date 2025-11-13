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


def flatten(
    data: dict | str,
    lib: str,
    refs: dict,
    root: str = "tests/",
    end: bool = False,  # noqa: FBT001, FBT002
    leaves: set | None = None,
) -> set | None:

    global output  # noqa: PLW0603

    if isinstance(data, str):
        if refs and data in refs:
            data_str = f"*{refs[data]}"
            output += f"\n{root}: {data_str}"
        else:
            output += f'\n{root}: "{data}"'
    elif end:
        output += f"\n{root}:"
        for var in data.items():
            if refs and var[1] in refs:
                data_str = f"*{refs[var[1]]}"
            else:
                data_str = f'"{var[1]}"'
            output += f"\n    {var[0]}: {data_str}"

    else:
        if root.endswith(".py"):
            root += "::"
            end = True

        for item in data.items():
            flatten(item[1], lib, refs, root + item[0], end)



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
                f.write("    - variant_declaration:\n")
            for line in entry[1]:
                f.write("    " + line + "\n")


def add_refs(file_path: str, output_file: str) -> None:
    global output  # noqa: PLW0602
    with open(file_path) as f:
        data = f.readlines()
    with open(output_file, "w") as f:
        for line in data:
            if line.startswith("tests/:"):
                f.write("manifest:" + "\n")
                return
            f.write(line)


def get_refs(file_path: str) -> None:
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

        semver_range = line[line.find("'") + 1 : line.rfind("'")]
        ref = line[line.find("&") + 1 : line.find(" '")]
        refs[semver_range] = ref

    return refs


def main() -> None:
    global output  # noqa: PLW0603
    for lib in variants:
        output = ""
        file_path = f"./manifests/{lib}.yml"
        output_file = f"./new.manifests/{lib}.yml"

        refs = get_refs(file_path)

        add_refs(file_path, output_file)
        with open(file_path) as f:
            data = yaml.safe_load(f)
            flatten(data["tests/"], lib, refs)

        yml_sort(output_file)


if __name__ == "__main__":
    main()
