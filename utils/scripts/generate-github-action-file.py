from copy import deepcopy
import yaml

scenarios_sets = (
    (
        "DEFAULT",
        "PROFILING",
        "CGROUP",
        "TRACE_PROPAGATION_STYLE_W3C",
        "INTEGRATIONS",
        "LIBRARY_CONF_CUSTOM_HEADERS_SHORT",
        "LIBRARY_CONF_CUSTOM_HEADERS_LONG",
        "REMOTE_CONFIG_MOCKED_BACKEND_ASM_FEATURES",
        "REMOTE_CONFIG_MOCKED_BACKEND_LIVE_DEBUGGING",
        "REMOTE_CONFIG_MOCKED_BACKEND_ASM_DD",
        "REMOTE_CONFIG_MOCKED_BACKEND_ASM_FEATURES_NOCACHE",
        "REMOTE_CONFIG_MOCKED_BACKEND_LIVE_DEBUGGING_NOCACHE",
        "REMOTE_CONFIG_MOCKED_BACKEND_ASM_DD_NOCACHE",
    ),
    (
        "APPSEC_MISSING_RULES",
        "APPSEC_CORRUPTED_RULES",
        "APPSEC_CUSTOM_RULES",
        "APPSEC_RULES_MONITORING_WITH_ERRORS",
        "APPSEC_BLOCKING",
        "APPSEC_DISABLED",
        "APPSEC_LOW_WAF_TIMEOUT",
        "APPSEC_CUSTOM_OBFUSCATION",
        "APPSEC_RATE_LIMITER",
        "APPSEC_IP_BLOCKING",
        "APPSEC_RUNTIME_ACTIVATION",
        "SAMPLING",
        # "APPSEC_UNSUPPORTED",
    ),
)

php_versions = ("7.0", "7.1", "7.2", "7.3", "7.4", "8.0", "8.1", "8.2")
rails_versions = ("32", "40", "41", "42", "50", "51", "52", "60", "61", "70")


def build_variant_array(lang, weblogs):
    return [{"library": lang, "weblog": weblog} for weblog in weblogs]


variants = (
    build_variant_array("cpp", ["nginx"])
    + build_variant_array("dotnet", ["poc", "uds"])
    + build_variant_array("golang", ["chi", "echo", "gin", "gorilla", "net-http", "uds-echo"])
    + build_variant_array(
        "java",
        [
            "jersey-grizzly2",
            "ratpack",
            "resteasy-netty3",
            "vertx3",
            "spring-boot-jetty",
            "spring-boot",
            "uds-spring-boot",
            "spring-boot-openliberty",
            "spring-boot-wildfly",
            "spring-boot-undertow",
        ],
    )
    + build_variant_array("nodejs", ["express4", "uds-express4", "express4-typescript"])
    + build_variant_array("php", [f"apache-mod-{v}" for v in php_versions])
    + build_variant_array("php", [f"apache-mod-{v}-zts" for v in php_versions])
    + build_variant_array("php", [f"php-fpm-{v}" for v in php_versions])
    + build_variant_array("python", ["flask-poc", "django-poc", "uwsgi-poc", "uds-flask"])  # TODO pylons
    + build_variant_array("ruby", ["rack", "sinatra14", "sinatra20", "sinatra21", "uds-sinatra"])
    + build_variant_array("ruby", [f"rails{v}" for v in rails_versions])
)
variants_graalvm = build_variant_array("java", ["spring-boot-native", "spring-boot-3-native"])


class Job:
    def __init__(self, name, needs=None, env=None, large_runner=False):
        self.name = name
        self.data = {}
        if large_runner:
            self.data["runs-on"] = {"labels": "ubuntu-latest-16-cores", "group": "APM Larger Runners"}
        else:
            self.data["runs-on"] = "ubuntu-latest"
        if needs is not None:
            self.data["needs"] = needs
        if env is not None:
            self.data["env"] = env

    @property
    def steps(self) -> list:
        if "steps" not in self.data:
            self.data["steps"] = []
        return self.data["steps"]

    def add_checkout(self):
        self.steps.append({"name": "Checkout", "uses": "actions/checkout@v3"})

    def add_setup_buildx(self):
        self.steps.append(
            {
                "name": "Set up Docker Buildx",
                "uses": "docker/setup-buildx-action@dc7b9719a96d48369863986a06765841d7ea23f6",
                "with": {"install": "false"},
            }
        )  # 2.0.0

    def add_docker_login(self):
        self.steps.append(
            {
                "name": "Log in to the Container registry",
                "uses": "docker/login-action@49ed152c8eca782a232dede0303416e8f356c37b",
                "with": {
                    "registry": "ghcr.io",
                    "username": "${{ github.actor }}",
                    "password": "${{ secrets.GITHUB_TOKEN }}",
                },
            }
        )  # 2.0.0

    def add_upload_artifact(self, name, path, if_condition=None):
        step = self.add_step(
            "Upload artifact",
            uses="actions/upload-artifact@v3",
            with_statement={"name": name, "path": path},
            if_condition=if_condition,
        )

        return step

    def add_step(
        self, name=None, run=None, uses=None, if_condition=None, env=None, with_statement=None, add_gh_token=False
    ):
        result = {}

        if name:
            result["name"] = name

        if if_condition is not None:
            result["if"] = if_condition

        if run is not None:
            result["run"] = run

        if uses is not None:
            result["uses"] = uses

        if with_statement is not None:
            result["with"] = with_statement

        if env is None:
            env = {}

        if add_gh_token:
            env = {"GH_TOKEN": "${{ secrets.GITHUB_TOKEN }}"}

        if len(env) != 0:
            result["env"] = env

        self.steps.append(result)

        return result


def add_job(workflow, job):
    if "jobs" not in workflow:
        workflow["jobs"] = {}

    workflow["jobs"][job.name] = job.data

    return job


def add_lint_job(workflow):
    job = Job("lint_and_test")
    job.add_checkout()
    job.add_step(uses="actions/setup-python@v4", with_statement={"python-version": "3.9"})
    job.add_step(run="pip install -r requirements.txt")
    job.add_step(run="black --check --diff .")
    job.add_step(
        run='echo "Lint fails, please have a look on https://github.com/DataDog/system-tests/blob/main/docs/edit/lint.md"\nexit 1\n',
        if_condition="${{ failure() }}",
    )
    job.add_step(run="mkdir -p logs/docker/weblog/logs/")
    job.add_step(run='PYTHONPATH="$PWD" pytest utils/test_the_test')

    return add_job(workflow, job)


def add_main_job(i, workflow, needs, scenarios, variants, use_cache=False, large_runner=False):

    name = f"test-the-tests-{i}"
    job = Job(name, needs=[job.name for job in needs], large_runner=large_runner)

    job.data["strategy"] = {
        "matrix": {"variant": variants, "version": ["prod", "dev"]},
        "fail-fast": False,
    }

    job.data["env"] = {
        "TEST_LIBRARY": "${{ matrix.variant.library }}",
        "WEBLOG_VARIANT": "${{ matrix.variant.weblog }}",
    }

    if use_cache:
        job.add_setup_buildx()
        job.add_docker_login()

    job.add_checkout()
    job.add_step(run="mkdir logs && touch logs/.weblog.env")
    job.add_step("Pull mongo image", run="docker pull mongo:latest")
    job.add_step("Pull cassandra image", run="docker pull cassandra:latest")
    job.add_step("Pull postgres image", run="docker pull postgres:latest")
    job.add_step(
        "Load WAF rules",
        "./utils/scripts/load-binary.sh waf_rule_set",
        add_gh_token=True,
        if_condition="${{ matrix.version == 'dev' }}",
    )

    job.add_step(
        "Load library binary",
        "./utils/scripts/load-binary.sh ${{ matrix.variant.library }}",
        if_condition="${{ matrix.version == 'dev' && (matrix.variant.library != 'php' && matrix.variant.library != 'java')}}",
    )

    # PHP script that loads prod tracer is very flaky
    # we also use it for dev, as dev artifact is on circle CI, requiring a token.
    job.add_step(
        "Load PHP prod library binary",
        "./utils/scripts/load-binary.sh php prod",
        add_gh_token=True,
        if_condition="${{ matrix.variant.library == 'php' }}",
    )

    job.add_step(
        "Load library PHP appsec binary",
        "./utils/scripts/load-binary.sh php_appsec ${{matrix.version}}",
        add_gh_token=True,
        if_condition="${{ matrix.variant.library == 'php' }}",
    )

    job.add_step(
        "Load library dotNet prod binary",
        "./utils/scripts/load-binary.sh ${{ matrix.variant.library }} prod",
        add_gh_token=True,
        if_condition="${{ matrix.variant.library == 'dotNet' && matrix.version == 'prod' }}",
    )

    job.add_step(
        "Load agent binary", "./utils/scripts/load-binary.sh agent", if_condition="${{ matrix.version == 'dev' }}"
    )

    job.add_step(
        "Log in to the Container registry",
        "echo ${{ secrets.GITHUB_TOKEN }} | docker login ${{ env.REGISTRY }} -u ${{ github.actor }} --password-stdin",
        if_condition="${{ matrix.variant.library == 'ruby' }}",
    )

    if use_cache:
        job.add_step(
            "Building with cache read-write mode",
            "SYSTEM_TEST_BUILD_ATTEMPTS=3 ./build.sh --cache-mode RW",
            if_condition="${{ github.ref == 'refs/heads/main'}}",
        )
        job.add_step(
            "Building with cache read only mode",
            "SYSTEM_TEST_BUILD_ATTEMPTS=3 ./build.sh --cache-mode R",
            if_condition="${{ github.ref != 'refs/heads/main'}}",
        )

    else:
        job.add_step("Build", "SYSTEM_TEST_BUILD_ATTEMPTS=3 ./build.sh")

    for scenario in scenarios:
        step = job.add_step(
            f"Run {scenario} scenario", f"./run.sh {scenario}", env={"DD_API_KEY": "${{ secrets.DD_API_KEY }}"}
        )

        if scenario == "TRACE_PROPAGATION_STYLE_W3C":  # TODO: fix weblog to allow this value for old tracer
            step["if"] = "${{ matrix.variant.library != 'python' }}"  # TODO

    job.add_step("Compress logs", "tar -czvf artifact.tar.gz $(ls | grep logs)", if_condition="${{ always() }}")
    job.add_upload_artifact(
        name="logs_${{ matrix.variant.library }}_${{ matrix.variant.weblog }}_${{ matrix.version }}_" + str(i),
        path="artifact.tar.gz",
        if_condition="${{ always() }}",
    )

    job.add_step(
        "Upload results CI Visibility",
        run=(
            "./utils/scripts/upload_results_CI_visibility.sh ${{ matrix.version }} "
            "system-tests ${{ github.run_id }}-${{ github.run_attempt }}"
        ),
        if_condition="${{ always() }}",
        env={"DD_API_KEY": "${{ secrets.DD_CI_API_KEY }}"},
    )

    job.add_step(
        "Print fancy log report",
        run="python utils/scripts/markdown_logs.py >> $GITHUB_STEP_SUMMARY",
        if_condition="${{ always() }}",
    )

    return add_job(workflow, job)


def add_ci_dashboard_job(workflow, needs):
    job = Job("post_test-the-tests", needs=[job.name for job in needs])

    job.data["if"] = "always() && github.ref == 'refs/heads/main'"
    job.add_checkout()
    job.add_step(
        "Update CI Dashboard",
        run=(
            "./utils/scripts/update_dashboard_CI_visibility.sh system-tests "
            "${{ github.run_id }}-${{ github.run_attempt }}"
        ),
        env={"DD_API_KEY": "${{ secrets.DD_CI_API_KEY }}", "DD_APP_KEY": "${{ secrets.DD_CI_APP_KEY }}",},
    )

    return add_job(workflow, job)


def add_perf_job(workflow, needs):
    job = Job("peformances", needs=[job.name for job in needs], env={"DD_API_KEY": "${{ secrets.DD_API_KEY }}"})

    job.add_checkout()
    job.add_step("Run", "./scenarios/perfs/run.sh golang")
    job.add_step("Display", "python scenarios/perfs/process.py")

    add_job(workflow, job)

    return job


def add_fuzzer_job(workflow, needs):
    job = Job("fuzzer", needs=[job.name for job in needs], env={"DD_API_KEY": "${{ secrets.DD_API_KEY }}"})

    job.add_checkout()
    job.add_step("Build", "./build.sh golang")
    job.add_step("Run", "./run.sh scenarios/fuzzer/main.py -t 60", env={"RUNNER_CMD": "python"})

    add_job(workflow, job)

    return job


def add_parametric_job(workflow, needs):
    job = Job("parametric", needs=[job.name for job in needs])

    job.data["strategy"] = {"matrix": {"client": ["python", "dotnet", "golang", "nodejs"]}, "fail-fast": False}

    job.add_checkout()
    job.add_step(uses="actions/setup-python@v4", with_statement={"python-version": "3.9"})
    job.add_step("Install", "cd parametric && pip install wheel && pip install -r requirements.txt")
    job.add_step("Run", "cd parametric && CLIENTS_ENABLED=${{ matrix.client }} ./run.sh")

    add_job(workflow, job)

    return job


def line_prepender(filename, line):
    with open(filename, "r+") as f:
        content = f.read()
        f.seek(0, 0)
        f.write(line.rstrip("\r\n") + "\n" + content)


def main():

    result = {"name": "Testing the test"}

    result["on"] = {
        "workflow_dispatch": {},
        "schedule": [{"cron": "00 02 * * 2-6"}],
        "pull_request": {"branches": ["**"]},
        "push": {"branches": ["main"]},
    }
    result["env"] = {"REGISTRY": "ghcr.io"}

    lint_job = add_lint_job(result)

    main_jobs = []

    for i, scenarios in enumerate(scenarios_sets):
        main_jobs.append(add_main_job(i, result, needs=[lint_job], scenarios=scenarios, variants=deepcopy(variants)))

    main_jobs.append(
        add_main_job(
            "graalvm",
            result,
            needs=[lint_job],
            scenarios=scenarios_sets[0],
            variants=deepcopy(variants_graalvm),
            use_cache=True,
            large_runner=True,
        )
    )
    add_ci_dashboard_job(result, main_jobs)

    add_perf_job(result, needs=[lint_job])
    add_fuzzer_job(result, needs=[lint_job])
    add_parametric_job(result, needs=[lint_job])
    YML_FILE = ".github/workflows/ci.yml"
    yaml.dump(result, open(YML_FILE, "w", encoding="utf-8"), sort_keys=False, width=160)
    line_prepender(YML_FILE, "#DON'T EDIT THIS FILE. Autogenerated by utils/scripts/generate-github-action-file.py")


if __name__ == "__main__":
    main()
