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

package jdk.internal.platform.cgroupv2;

import java.nio.file.Paths;

import jdk.internal.platform.CgroupSubsystem;
import jdk.internal.platform.CgroupSubsystemController;

public class CgroupV2SubsystemController implements CgroupSubsystemController {

    private final String path;

    public CgroupV2SubsystemController(String mountPath, String cgroupPath) {
        this.path = Paths.get(mountPath, cgroupPath).toString();
    }

    @Override
    public String path() {
        return path;
    }

    public static long convertStringToLong(String strval) {
        return CgroupSubsystemController.convertStringToLong(strval,
                                                             CgroupSubsystem.LONG_RETVAL_UNLIMITED /* overflow retval */,
                                                             CgroupSubsystem.LONG_RETVAL_UNLIMITED /* default retval on error */);
    }

    public static long getLongEntry(CgroupSubsystemController controller, String param, String entryname) {
        return CgroupSubsystemController.getLongEntry(controller,
                                                      param,
                                                      entryname,
                                                      CgroupSubsystem.LONG_RETVAL_UNLIMITED /* retval on error */);
    }
}
