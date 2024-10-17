/*
 * Copyright (c) 2016, 2020, Oracle and/or its affiliates. All rights reserved.
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
 * Meta annotation for defining new types of event metadata.
 * <p>
 * In the following example, a transaction event is defined with two
 * user-defined annotations, {@code @Severity} and {@code @TransactionId}.
 *
 * {@snippet class="Snippets" region="MetadataDefinitionOverview"}
 *
 * Adding {@code @MetadataDefinition} to the declaration of {@code @Severity} and {@code @TransactionId}
 * ensures the information is saved by Flight Recorder.
 *
 * @since 9
 */
@Retention(RetentionPolicy.RUNTIME)
@Target({ ElementType.TYPE })
public @interface MetadataDefinition {
}
