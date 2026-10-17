# Thread context sharing (CWS)

The `THREAD_CONTEXT_SHARING` scenario checks that a tracer shares the trace_id/span_id of the span active on a thread with system-probe, so that a CWS (Cloud Workload Security) security event triggered on that thread carries them as `dd.trace_id`/`dd.span_id`. The weblog side of the contract is [`GET /security/thread_context_sharing`](../weblogs/end-to-end_weblog.md#get-securitythread_context_sharing).

It is an [end-to-end scenario](README.md) whose agent runs the CWS runtime security module. Like the [documented CWS Docker setup](https://docs.datadoghq.com/security/workload_protection/setup/agent/docker/), the agent container gets the host PID and cgroup namespaces, extra capabilities, and binds of the docker host's `/sys/kernel/debug` and `/sys/kernel/security`. The weblog is only started once the agent's CWS self test has succeeded (90 seconds at most): a weblog started before CWS is live has been observed to produce security events without trace context.

```bash
./build.sh php
./run.sh THREAD_CONTEXT_SHARING
```

## Kata docker-in-docker: `SYSTEM_TESTS_CWS_GUEST_KERNEL_MOUNTS`

The default setup needs the docker daemon to run on the machine whose kernel CWS instruments. That is not the case when system-tests runs in a docker-in-docker (DIND) service of a Kubernetes pod using a Kata VM runtime, as in some tracer CI pipelines: the docker daemon's "host" is itself a container of the VM, so `--pid=host` only gives the DIND PID namespace, and the VM's kernel filesystems are not available.

For that environment, setting `SYSTEM_TESTS_CWS_GUEST_KERNEL_MOUNTS=v1` makes the agent take the VM's kernel filesystems from `/vm-host` in the DIND container:

| DIND source                    | Agent target                         | Mode |
|--------------------------------|--------------------------------------|------|
| `/vm-host/proc`                | `/host/proc`                         | ro   |
| `/vm-host/sys/fs/cgroup`       | `/host/sys/fs/cgroup`                | ro   |
| `/vm-host/sys/kernel/debug`    | `/sys/kernel/debug`                  | rw   |
| `/vm-host/sys/kernel/tracing`  | `/sys/kernel/tracing`                | rw   |
| `/vm-host/sys/kernel/security` | `/sys/kernel/security`               | rw   |

In this mode, system-tests also disables CWS enforcement (`DD_RUNTIME_SECURITY_CONFIG_ENFORCEMENT_ENABLED=false`): cgroup files read by the agent are relative to the VM's namespaces rather than its own, so it can't reliably identify its own cgroup.

Leaving the variable unset (or empty) keeps the default setup. Any other value is an error, so that a future version of the layout can't be silently misinterpreted.

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

All sources are docker bind mounts rather than volumes, so on a runner without the `/vm-host` mounts, the agent container fails to be created instead of starting with empty directories.
