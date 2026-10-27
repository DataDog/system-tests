# Thread context sharing (CWS)

The `THREAD_CONTEXT_SHARING` scenario checks that a tracer shares the trace_id/span_id of the span active on a thread with system-probe, so that a CWS (Cloud Workload Security) security event triggered on that thread carries them as `dd.trace_id`/`dd.span_id`. The weblog side of the contract is [`GET /security/thread_context_sharing`](../weblogs/end-to-end_weblog.md#get-securitythread_context_sharing).

It is an [end-to-end scenario](README.md) whose agent runs the CWS runtime security module. Like the [documented CWS Docker setup](https://docs.datadoghq.com/security/workload_protection/setup/agent/docker/), the agent container gets the host PID and cgroup namespaces, extra capabilities, and binds of the docker host's `/sys/kernel/debug` and `/sys/kernel/security`. The weblog is only started once the agent's CWS self test has succeeded (90 seconds at most): a weblog started before CWS is live has been observed to produce security events without trace context.

```bash
./build.sh php
./run.sh THREAD_CONTEXT_SHARING
```

## ebpfless: `THREAD_CONTEXT_SHARING_EBPFLESS`

`THREAD_CONTEXT_SHARING_EBPFLESS` runs the same tests, on the same weblogs, with the ebpfless (ptrace-based) CWS probe instead of the eBPF one. The weblog runs under `cws-instrumentation trace --probe-addr=agent:5678 -- ./app.sh`: cws-instrumentation ptraces it, reads the span context of the thread doing each syscall, and sends it to system-probe with the event. system-probe listens on `0.0.0.0:5678` (`DD_RUNTIME_SECURITY_CONFIG_EBPFLESS_SOCKET`), and the agent container gets no extra privilege, so this scenario runs on any docker host.

Startup is ordered: the weblog only starts once system-probe listens on port 5678 (cws-instrumentation exits otherwise), and the scenario then waits for the CWS self test (90 seconds at most), which in ebpfless mode passes on the weblog's own startup exec.

The weblog gets cws-instrumentation as a read-only bind on `/opt/datadog/cws-instrumentation`, from the first of:

1. `binaries/cws-instrumentation`: a static linux binary for the docker host's architecture, e.g. built from a datadog-agent branch with `dda inv cws-instrumentation.build --static`.
2. the `/cws-instrumentation` binary of the image named in `binaries/cws-instrumentation-image`, like `datadog/cws-instrumentation-dev:my-branch`.
3. the `/cws-instrumentation` binary of `datadog/cws-instrumentation:latest`.

The agent image must be one whose ebpfless probe forwards the span context (see [binaries](../../execute/binaries.md#agent) for `binaries/agent-image`).

```bash
echo datadog/cws-instrumentation-dev:my-branch > binaries/cws-instrumentation-image
./build.sh <library>
./run.sh THREAD_CONTEXT_SHARING_EBPFLESS
```

Both scenarios run the same test class, so a library's manifest entries apply to both.

## Kata docker-in-docker: `/vm-host`

The default setup needs the docker daemon to run on the machine whose kernel CWS instruments. That is not the case when system-tests runs in a docker-in-docker (DIND) service of a Kubernetes pod using a Kata VM runtime, as in some tracer CI pipelines: the docker daemon's "host" is itself a container of the VM, so `--pid=host` only gives the DIND PID namespace, and the VM's kernel filesystems are not available.

For that environment, the CI runner mounts the VM's kernel filesystems under `/vm-host`. When `/vm-host` exists, system-tests detects it and makes the agent take them from there:

| DIND source                    | Agent target                         | Mode |
|--------------------------------|--------------------------------------|------|
| `/vm-host/proc`                | `/host/proc`                         | ro   |
| `/vm-host/sys/fs/cgroup`       | `/host/sys/fs/cgroup`                | ro   |
| `/vm-host/sys/kernel/debug`    | `/sys/kernel/debug`                  | rw   |
| `/vm-host/sys/kernel/tracing`  | `/sys/kernel/tracing`                | rw   |
| `/vm-host/sys/kernel/security` | `/sys/kernel/security`               | rw   |

In this mode, system-tests also disables CWS enforcement (`DD_RUNTIME_SECURITY_CONFIG_ENFORCEMENT_ENABLED=false`): cgroup files read by the agent are relative to the VM's namespaces rather than its own, so it can't reliably identify its own cgroup.

Without `/vm-host`, the default setup is used. A `/vm-host` lacking any of the sources above is an error.

### Prerequisites

The `/vm-host` mounts are not created by system-tests. The CI runner adds them to the job pod as hostPath volumes:

| Host path              | Mount path in the job's containers | Mode |
|------------------------|------------------------------------|------|
| `/proc`                | `/vm-host/proc`                    | ro   |
| `/sys/fs/cgroup`       | `/vm-host/sys/fs/cgroup`           | ro   |
| `/sys/kernel/debug`    | `/vm-host/sys/kernel/debug`        | rw   |
| `/sys/kernel/tracing`  | `/vm-host/sys/kernel/tracing`      | rw   |
| `/sys/kernel/security` | `/vm-host/sys/kernel/security`     | rw   |

On a Kata runtime, host paths under `/proc` and `/sys` are not shared from the Kubernetes node: the Kata agent mounts the VM's own ones instead. So these volumes give the DIND container the VM's procfs, numbered in the VM's top-level PID namespace like the PIDs in CWS events, and the VM's kernel filesystems. At Datadog, the `micro-vms-cws` GitLab runner pool is configured this way.

Never use such a runner configuration outside Kata: on a regular container runtime, the same host paths are the node's own `/proc` and kernel filesystems.

system-tests checks for `/vm-host` in its own container, while the agent's binds are resolved by the docker daemon. This works because the GitLab Kubernetes executor mounts these volumes into every container of the job pod, the DIND service included. All sources are docker bind mounts rather than volumes, so should the daemon not see `/vm-host`, the agent container fails to be created instead of starting with empty directories.
