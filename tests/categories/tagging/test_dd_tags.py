# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from urllib.parse import urlparse

from utils import context, BaseTestCase, interfaces, bug, irrelevant


class Test_Meta(BaseTestCase):
    """meta object in spans respect all conventions"""


@bug(
    context.library in ("cpp", "python", "ruby"),
    reason="Inconsistent implementation across tracers; will need a dedicated testing scenario",
)
class Test_MetaDatadogTags(BaseTestCase):
    """Spans carry meta tags that were set in DD_TAGS tracer environment"""

    def test_meta_dd_tags(self):
        def validator(span):
            if span["meta"]["key1"] != "val1":
                raise Exception(f'keyTag tag in span\'s meta should be "test", not {span["meta"]["env"]}')

            if span["meta"]["key2"] != "val2":
                raise Exception(f'dKey tag in span\'s meta should be "key2:val2", not {span["meta"]["key2"]}')

            return True

        interfaces.library.add_span_validation(validator=validator)
