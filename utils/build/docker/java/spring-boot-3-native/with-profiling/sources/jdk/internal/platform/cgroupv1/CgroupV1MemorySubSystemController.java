/*
 * Copyright (c) 2020, Red Hat Inc.
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

package jdk.internal.platform.cgroupv1;

public class CgroupV1MemorySubSystemController extends CgroupV1SubsystemController {

    private boolean hierarchical;
    private boolean swapenabled;

    public CgroupV1MemorySubSystemController(String root, String mountPoint) {
        super(root, mountPoint);
    }

    boolean isHierarchical() {
        return hierarchical;
    }

    void setHierarchical(boolean hierarchical) {
        this.hierarchical = hierarchical;
    }

    boolean isSwapEnabled() {
        return swapenabled;
    }

    void setSwapEnabled(boolean swapenabled) {
        this.swapenabled = swapenabled;
    }
}
