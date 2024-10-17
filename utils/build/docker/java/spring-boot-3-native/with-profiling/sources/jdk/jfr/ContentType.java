/*
 * Copyright (c) 2016, 2018, Oracle and/or its affiliates. All rights reserved.
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
 * Meta annotation, specifies that an annotation represents a content type, such
 * as a time span or a frequency.
 * <p>
 * The following example shows how a temperature content type can be created and
 * used.
 * <p>
 * First declare a temperature annotation using the {@code ContentType}
 * annotation:
 *
 * {@snippet class="Snippets" region="ContentTypeDeclaration"}
 *
 * Then declare an event, annotate a field and commit the data:
 *
 * {@snippet class="Snippets" region="ContentTypeEvent"}
 *
 * Finally, inspect the annotation when displaying event data:
 *
 * {@snippet class="Snippets" region="ContentTypeConsumption"}
 *
 * @since 9
 */
@MetadataDefinition
@Label("Content Type")
@Description("Semantic meaning of a value")
@Target(ElementType.ANNOTATION_TYPE)
@Retention(RetentionPolicy.RUNTIME)
public @interface ContentType {
}
