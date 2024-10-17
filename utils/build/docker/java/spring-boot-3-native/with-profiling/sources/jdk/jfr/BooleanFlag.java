/*
 * Copyright (c) 2016, 2023, Oracle and/or its affiliates. All rights reserved.
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

package jdk.jfr;

import java.lang.annotation.ElementType;
import java.lang.annotation.Retention;
import java.lang.annotation.RetentionPolicy;
import java.lang.annotation.Target;

/**
 * Event field annotation, specifies that the value is a boolean flag, a
 * {@code true} or {@code false} value.
 * <p>
 * The following example shows how the {@code BooleanFlag} annotation can be
 * used to describe that a setting is a boolean value. This information can be
 * used by a graphical user interface to display the setting as a checkbox.
 *
 * {@snippet class = "Snippets" region = "BooleanFlagOverview"}
 *
 * @since 9
 */
@MetadataDefinition
@ContentType
@Label("Flag")
@Retention(RetentionPolicy.RUNTIME)
@Target({ ElementType.FIELD, ElementType.TYPE, ElementType.METHOD})
public @interface BooleanFlag {
}
