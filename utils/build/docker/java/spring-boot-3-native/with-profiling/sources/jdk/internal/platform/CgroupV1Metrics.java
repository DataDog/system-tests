/*
 * Copyright (c) 2018, 2020, Oracle and/or its affiliates. All rights reserved.
 * ORACLE PROPRIETARY/CONFIDENTIAL. Use is subject to license terms.
 *
 *
 *
 *
 *
 *
 *
 *
 *
 *
 *
 *
 *
 *
 *
 *
 *
 *
 *
 *
 */

package jdk.internal.platform;

/**
 *
 * Cgroup v1 extensions to the Metrics interface. Linux, only.
 *
 */
public interface CgroupV1Metrics extends Metrics {

    /**
     * Returns the largest amount of physical memory, in bytes, that
     * have been allocated in the Isolation Group.
     *
     * @return The largest amount of memory in bytes or -1 if this
     *         metric is not available. Returns -2 if this metric is not
     *         supported.
     *
     */
    public long getMemoryMaxUsage();

    /**
     * Returns the number of times that kernel memory requests in the
     * Isolation Group have exceeded the kernel memory limit.
     *
     * @return The number of exceeded requests or -1 if metric
     *         is not available.
     *
     */
    public long getKernelMemoryFailCount();

    /**
     * Returns the largest amount of kernel physical memory, in bytes, that
     * have been allocated in the Isolation Group.
     *
     * @return The largest amount of memory in bytes or -1 if this
     *         metric is not available.
     *
     */
    public long getKernelMemoryMaxUsage();

    /**
     * Returns the amount of kernel physical memory, in bytes, that
     * is currently allocated in the current Isolation Group.
     *
     * @return The amount of memory in bytes allocated or -1 if this
     *         metric is not available.
     *
     */
    public long getKernelMemoryUsage();

    /**
     * Returns the number of times that networking memory requests in the
     * Isolation Group have exceeded the kernel memory limit.
     *
     * @return The number of exceeded requests or -1 if the metric
     *         is not available.
     *
     */
    public long getTcpMemoryFailCount();

    /**
     * Returns the largest amount of networking physical memory, in bytes,
     * that have been allocated in the Isolation Group.
     *
     * @return The largest amount of memory in bytes or -1 if this
     *         metric is not available.
     *
     */
    public long getTcpMemoryMaxUsage();

    /**
     * Returns the number of times that user memory requests in the
     * Isolation Group have exceeded the memory + swap limit.
     *
     * @return The number of exceeded requests or -1 if the metric
     *         is not available.
     *
     */
    public long getMemoryAndSwapFailCount();

    /**
     * Returns the largest amount of physical memory and swap space,
     * in bytes, that have been allocated in the Isolation Group.
     *
     * @return The largest amount of memory in bytes or -1 if this
     *         metric is not available.
     *
     */
    public long getMemoryAndSwapMaxUsage();

    /**
     * Returns the state of the Operating System Out of Memory termination
     * policy.
     *
     * @return Returns true if operating system will terminate processes
     *         in the Isolation Group that exceed the amount of available
     *         memory, otherwise false. null will be returned if this
     *         capability is not available on the current operating system.
     *
     */
    public Boolean isMemoryOOMKillEnabled();

    /**
     * Returns the (attempts per second * 1000), if enabled, that the
     * operating system tries to satisfy a memory request for any
     * process in the current Isolation Group when no free memory is
     * readily available.  Use {@link #isCpuSetMemoryPressureEnabled()} to
     * determine if this support is enabled.
     *
     * @return Memory pressure or 0 if not enabled or -1 if metric is not
     *         available.
     *
     */
    public double getCpuSetMemoryPressure();

    /**
     * Returns the state of the memory pressure detection support.
     *
     * @return true if support is available and enabled. false otherwise.
     *
     */
    public Boolean isCpuSetMemoryPressureEnabled();
}
