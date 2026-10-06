# Thread context sharing (CWS)

The `THREAD_CONTEXT_SHARING` scenario checks that a tracer shares the trace_id/span_id of the span active on a thread with system-probe, so that a CWS (Cloud Workload Security) security event triggered on that thread carries them as `dd.trace_id`/`dd.span_id`. The weblog side of the contract is [`GET /security/thread_context_sharing`](../weblogs/end-to-end_weblog.md#get-securitythread_context_sharing).

It is an [end-to-end scenario](README.md) whose agent runs the CWS runtime security module. Like the [documented CWS Docker setup](https://docs.datadoghq.com/security/workload_protection/setup/agent/docker/), the agent container gets the host PID namespace, extra capabilities, and binds of the docker host's `/sys/kernel/debug` and `/sys/kernel/security`. Tests wait for the agent's CWS self test to succeed before sending requests.

```bash
./build.sh php
./run.sh THREAD_CONTEXT_SHARING
```

## Kata docker-in-docker: `SYSTEM_TESTS_CWS_GUEST_KERNEL_MOUNTS`

The default setup needs the docker daemon to run on the machine whose kernel CWS instruments. That is not the case when system-tests runs in a docker-in-docker (DIND) service of a Kubernetes pod using a Kata VM runtime, as in some tracer CI pipelines: the docker daemon's "host" is itself a container of the VM, so `--pid=host` only gives the DIND PID namespace, and the VM's kernel filesystems are not available.

For that environment, setting `SYSTEM_TESTS_CWS_GUEST_KERNEL_MOUNTS=v1` makes the agent take the VM's kernel filesystems from `/vm-host`, where a Kata guest hook exposes them in the DIND container:

| DIND source                    | Agent target                         | Mode |
|--------------------------------|--------------------------------------|------|
| `/vm-host/proc`                | `/host/proc`                         | ro   |
| `/vm-host/sys/fs/cgroup`       | `/host/sys/fs/cgroup`                | ro   |
| `/vm-host/sys/kernel/debug`    | `/sys/kernel/debug`                  | rw   |
| `/vm-host/sys/kernel/tracing`  | `/sys/kernel/tracing`                | rw   |
| `/vm-host/sys/kernel/security` | `/sys/kernel/security`               | rw   |
| `/vm-host/.ready-v1`           | `/opt/system-tests/vm-host-ready-v1` | ro   |

In this mode, system-tests also:

* runs the agent in the docker daemon's cgroup namespace (`--cgroupns host`);
* disables CWS enforcement (`DD_RUNTIME_SECURITY_CONFIG_ENFORCEMENT_ENABLED=false`): cgroup files read by the agent are relative to the VM's namespaces rather than its own, so it can't reliably identify its own cgroup;
* starts the weblog only once the agent's CWS self test has succeeded (90 seconds at most). A weblog started before CWS is live has been observed to produce security events without trace context.

Leaving the variable unset (or empty) keeps the default setup. Any other value is an error, so that a future version of the layout can't be silently misinterpreted.

### Prerequisites

The `/vm-host` mounts are not created by system-tests. They require:

* a Kata runtime whose guest image has the guest kernel mounts prestart hook, enabled with `guest_hook_path`;
* the `io.katacontainers.datadog.guest-kernel-mounts=v1` annotation on the pod. In GitLab, set the job variable `KUBERNETES_POD_ANNOTATIONS_CWS_GUEST_KERNEL_MOUNTS: "io.katacontainers.datadog.guest-kernel-mounts=v1"`. The runner must allow this annotation.
* the DIND service container to be named `docker`. The hook only acts on that container.

The hook writes `/vm-host/.ready-v1` after all the other mounts. All sources are docker bind mounts rather than volumes, so if the hook did not run or did not finish, the agent container fails to be created instead of starting with empty directories. Kata only logs hook failures. To find them, run this in the VM:

```bash
dmesg | grep 'kata-agent: hook failed'
```
