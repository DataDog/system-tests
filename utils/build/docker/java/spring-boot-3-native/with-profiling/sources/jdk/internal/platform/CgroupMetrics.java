/*
 * Copyright (c) 2020, 2021, Red Hat Inc.
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

import java.util.Objects;

public class CgroupMetrics implements Metrics {

    private final CgroupSubsystem subsystem;

    CgroupMetrics(CgroupSubsystem subsystem) {
        this.subsystem = Objects.requireNonNull(subsystem);
    }

    @Override
    public String getProvider() {
        return subsystem.getProvider();
    }

    @Override
    public long getCpuUsage() {
        return subsystem.getCpuUsage();
    }

    @Override
    public long[] getPerCpuUsage() {
        return subsystem.getPerCpuUsage();
    }

    @Override
    public long getCpuUserUsage() {
        return subsystem.getCpuUserUsage();
    }

    @Override
    public long getCpuSystemUsage() {
        return subsystem.getCpuSystemUsage();
    }

    @Override
    public long getCpuPeriod() {
        return subsystem.getCpuPeriod();
    }

    @Override
    public long getCpuQuota() {
        return subsystem.getCpuQuota();
    }

    @Override
    public long getCpuShares() {
        return subsystem.getCpuShares();
    }

    @Override
    public long getCpuNumPeriods() {
        return subsystem.getCpuNumPeriods();
    }

    @Override
    public long getCpuNumThrottled() {
        return subsystem.getCpuNumThrottled();
    }

    @Override
    public long getCpuThrottledTime() {
        return subsystem.getCpuThrottledTime();
    }

    @Override
    public long getEffectiveCpuCount() {
        return subsystem.getEffectiveCpuCount();
    }

    @Override
    public int[] getCpuSetCpus() {
        return subsystem.getCpuSetCpus();
    }

    @Override
    public int[] getEffectiveCpuSetCpus() {
        return subsystem.getEffectiveCpuSetCpus();
    }

    @Override
    public int[] getCpuSetMems() {
        return subsystem.getCpuSetMems();
    }

    @Override
    public int[] getEffectiveCpuSetMems() {
        return subsystem.getEffectiveCpuSetMems();
    }

    public long getMemoryFailCount() {
        return subsystem.getMemoryFailCount();
    }

    @Override
    public long getMemoryLimit() {
        long subsMem = subsystem.getMemoryLimit();
        long systemTotal = getTotalMemorySize0();
        assert(systemTotal > 0);
        // Catch the cgroup memory limit exceeding host physical memory.
        // Treat this as unlimited.
        if (subsMem >= systemTotal) {
            return CgroupSubsystem.LONG_RETVAL_UNLIMITED;
        }
        return subsMem;
    }

    @Override
    public long getMemoryUsage() {
        return subsystem.getMemoryUsage();
    }

    @Override
    public long getTcpMemoryUsage() {
        return subsystem.getTcpMemoryUsage();
    }

    @Override
    public long getMemoryAndSwapLimit() {
        long totalSystemMemSwap = getTotalMemorySize0() + getTotalSwapSize0();
        assert(totalSystemMemSwap > 0);
        // Catch the cgroup memory and swap limit exceeding host physical swap
        // and memory. Treat this case as unlimited.
        long subsSwapMem = subsystem.getMemoryAndSwapLimit();
        if (subsSwapMem >= totalSystemMemSwap) {
            return CgroupSubsystem.LONG_RETVAL_UNLIMITED;
        }
        return subsSwapMem;
    }

    @Override
    public long getMemoryAndSwapUsage() {
        return subsystem.getMemoryAndSwapUsage();
    }

    @Override
    public long getMemorySoftLimit() {
        return subsystem.getMemorySoftLimit();
    }

    @Override
    public long getPidsMax() {
        return subsystem.getPidsMax();
    }

    @Override
    public long getPidsCurrent() {
        return subsystem.getPidsCurrent();
    }

    @Override
    public long getBlkIOServiceCount() {
        return subsystem.getBlkIOServiceCount();
    }

    @Override
    public long getBlkIOServiced() {
        return subsystem.getBlkIOServiced();
    }

    public static Metrics getInstance() {
        if (!isUseContainerSupport()) {
            // Return null on -XX:-UseContainerSupport
            return null;
        }
        return CgroupSubsystemFactory.create();
    }

    private static native boolean isUseContainerSupport();
    private static native long getTotalMemorySize0();
    private static native long getTotalSwapSize0();

}
