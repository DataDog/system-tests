/*
 * Copyright (c) 2022, Oracle and/or its affiliates. All rights reserved.
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

package jdk.jfr.events;

import jdk.jfr.Category;
import jdk.jfr.Description;
import jdk.jfr.Label;
import jdk.jfr.Name;
import jdk.jfr.internal.MirrorEvent;

@Category({"Java Development Kit", "Security"})
@Label("Security Provider Instance Request")
@Name("jdk.SecurityProviderService")
@Description("Details of Provider.getInstance(String type, String algorithm) calls")
@MirrorEvent(className = "jdk.internal.event.SecurityProviderServiceEvent")
public final class SecurityProviderServiceEvent extends AbstractJDKEvent {
    @Label("Type of Service")
    public String type;

    @Label("Algorithm Name")
    public String algorithm;

    @Label("Security Provider")
    public String provider;
}
