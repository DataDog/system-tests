class NestedObject:
    """Class to test maxReferenceDepth with real object attributes"""

    def __init__(self, level, nested=None):
        self.level = level
        self.nested = nested


class ManyFieldsObject:
    """Class to test maxFieldCount with real object attributes"""

    def __init__(self, field_count):
        for i in range(field_count):
            setattr(self, f"field{i}", i)


def generate_test_data(depth=0, fields=0, collection_size=0, string_length=0):
    """Generate test data for snapshot capture limits testing"""

    # Generate deeply nested object (tests maxReferenceDepth)
    deep_object = _create_nested_object(depth) if depth > 0 else None

    # Generate object with many fields (tests maxFieldCount)
    many_fields = ManyFieldsObject(fields)

    # Generate large collection (tests maxCollectionSize)
    large_collection = list(range(collection_size))

    # Generate long string (tests maxLength)
    long_string = "A" * string_length if string_length > 0 else ""

    return {
        "deepObject": deep_object,
        "manyFields": many_fields,
        "largeCollection": large_collection,
        "longString": long_string,
    }


def _create_nested_object(max_level, level=1):
    """Create a nested object up to max_level depth"""
    if level == max_level:
        return NestedObject(level)
    return NestedObject(level, _create_nested_object(max_level, level + 1))
