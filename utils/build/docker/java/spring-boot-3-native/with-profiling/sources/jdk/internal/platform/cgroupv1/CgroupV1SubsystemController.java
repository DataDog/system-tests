/*
 * Copyright (c) 2018, 2022, Oracle and/or its affiliates. All rights reserved.
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

import jdk.internal.platform.CgroupSubsystem;
import jdk.internal.platform.CgroupSubsystemController;

public class CgroupV1SubsystemController implements CgroupSubsystemController {

    private static final double DOUBLE_RETVAL_UNLIMITED = CgroupSubsystem.LONG_RETVAL_UNLIMITED;
    // Values returned larger than this number are unlimited.
    static long UNLIMITED_MIN = 0x7FFFFFFFFF000000L;
    String root;
    String mountPoint;
    String path;

    public CgroupV1SubsystemController(String root, String mountPoint) {
        this.root = root;
        this.mountPoint = mountPoint;
    }

    public void setPath(String cgroupPath) {
        if (root != null && cgroupPath != null) {
            if (root.equals("/")) {
                if (!cgroupPath.equals("/")) {
                    path = mountPoint + cgroupPath;
                }
                else {
                    path = mountPoint;
                }
            }
            else {
                if (root.equals(cgroupPath)) {
                    path = mountPoint;
                }
                else {
                    if (cgroupPath.startsWith(root)) {
                        if (cgroupPath.length() > root.length()) {
                            String cgroupSubstr = cgroupPath.substring(root.length());
                            path = mountPoint + cgroupSubstr;
                        }
                    }
                }
            }
        }
    }

    @Override
    public String path() {
        return path;
    }

    public static long getLongEntry(CgroupSubsystemController controller, String param, String entryname) {
        return CgroupSubsystemController.getLongEntry(controller,
                                                      param,
                                                      entryname,
                                                      CgroupSubsystem.LONG_RETVAL_UNLIMITED /* retval on error */);
    }

    public static double getDoubleValue(CgroupSubsystemController controller, String param) {
        return CgroupSubsystemController.getDoubleValue(controller,
                                                        param,
                                                        DOUBLE_RETVAL_UNLIMITED /* retval on error */);
    }

    public static long convertStringToLong(String strval) {
        return CgroupSubsystemController.convertStringToLong(strval,
                                                             Long.MAX_VALUE /* overflow value */,
                                                             CgroupSubsystem.LONG_RETVAL_UNLIMITED /* retval on error */);
    }

    public static long longValOrUnlimited(long value) {
        return value > UNLIMITED_MIN ? CgroupSubsystem.LONG_RETVAL_UNLIMITED : value;
    }

    public static long getLongValueMatchingLine(CgroupSubsystemController controller,
                                                String param,
                                                String match) {
        return CgroupSubsystemController.getLongValueMatchingLine(controller,
                                                                  param,
                                                                  match,
                                                                  CgroupV1SubsystemController::convertHierachicalLimitLine,
                                                                  CgroupSubsystem.LONG_RETVAL_UNLIMITED);
    }

    public static long convertHierachicalLimitLine(String line) {
        String[] tokens = line.split(" ");
        if (tokens.length == 2) {
            String strVal = tokens[1];
            return CgroupV1SubsystemController.convertStringToLong(strVal);
        }
        return CgroupV1SubsystemController.UNLIMITED_MIN + 1; // unlimited
    }

}
