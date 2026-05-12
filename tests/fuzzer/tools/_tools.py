# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.


class cached_property:  # noqa: N801 (used as a decorator)
    """Descriptor (non-data) for building an attribute on-demand on first use."""

    def __init__(self, factory):  # noqa: ANN001
        """<factory> is called such: factory(instance) to build the attribute."""
        self._attr_name = factory.__name__
        self._factory = factory

    def __get__(self, instance: object, owner):  # noqa: ANN001
        # Build the attribute.
        attr = self._factory(instance)

        # Cache the value; hide ourselves.
        setattr(instance, self._attr_name, attr)

        return attr
