/*
 * Copyright (c) 2016, 2022, Oracle and/or its affiliates. All rights reserved.
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



package sun.text.spi;

import java.time.DateTimeException;
import java.util.Locale;
import java.util.spi.LocaleServiceProvider;

/**
 * Service Provider Interface for retrieving DateTime patterns from
 * specified Locale provider for java.time.
 */

public abstract class JavaTimeDateTimePatternProvider extends LocaleServiceProvider {

    protected JavaTimeDateTimePatternProvider() {
    }

    /**
     * Returns the formatting pattern for a timeStyle
     * dateStyle, calendarType and locale.
     * Concrete implementation of this method will retrieve
     * a java.time specific dateTime Pattern from the selected Locale Provider.
     *
     * @param timeStyle an {@code int} value, representing FormatStyle constant, -1
     * for date-only pattern
     * @param dateStyle an {@code int} value, representing FormatStyle constant, -1
     * for time-only pattern
     * @param locale {@code locale}, non-null
     * @param calType a {@code String}, non-null representing CalendarType such as "japanese",
     * "iso8601"
     * @return  formatting pattern {@code String}
     * @see java.time.format.DateTimeFormatterBuilder#convertStyle(java.time.format.FormatStyle)
     * @since 9
     */
    public abstract String getJavaTimeDateTimePattern(int timeStyle, int dateStyle, String calType, Locale locale);

    /**
     * Returns the formatting pattern for the requested template, calendarType, and locale.
     * Concrete implementation of this method will retrieve
     * a java.time specific pattern from selected Locale Provider.
     *
     * @param requestedTemplate the requested template, not null
     * @param calType a {@code String}, non-null representing CalendarType such as "japanese",
     * "iso8601"
     * @param locale {@code locale}, non-null
     * @throws IllegalArgumentException if {@code requestedTemplate} does not match
     *      the regular expression syntax described in
     *      {@link java.time.format.DateTimeFormatterBuilder#appendLocalized(String)}.
     * @throws DateTimeException if a match for the formatting pattern for
     *      {@code requestedTemplate} is not available
     * @return  formatting pattern {@code String}
     * @since 19
     */
    public String getJavaTimeDateTimePattern(String requestedTemplate, String calType, Locale locale) {
        // default implementation throws exception
        throw new DateTimeException("Formatting pattern is not available for the requested template: " + requestedTemplate);
    }
}
