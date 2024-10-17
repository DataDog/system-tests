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
 * Event field annotation, specifies that a value represents an amount of data (for example, bytes).
 * <p>
 * The following example shows how the {@code DataAmount} annotation can be used to
 * set the units {@code BITS} and {@code BYTES} to event fields.
 *
 * {@snippet class="Snippets" region="DataAmountOverview"}
 *
 * @since 9
 */
@MetadataDefinition
@ContentType
@Label("Data Amount")
@Description("Amount of data")
@Retention(RetentionPolicy.RUNTIME)
@Target({ ElementType.FIELD, ElementType.TYPE, ElementType.METHOD})
public @interface DataAmount {
    /**
     * Unit for bits
     */
    public static final String BITS = "BITS";
    /**
     * Unit for bytes
     */
    public static final String BYTES = "BYTES";

    /**
     * Returns the unit for the data amount, by default bytes.
     *
     * @return the data amount unit, default {@code BYTES}, not {@code null}
     */
    String value() default BYTES;
}
