package com.datadoghq.system_tests.springboot;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

class NestedObject {
    public int level;
    public NestedObject nested;

    public NestedObject(int level, NestedObject nested) {
        this.level = level;
        this.nested = nested;
    }
}

class ManyFieldsObject {
    // Class with 50 public fields to test maxFieldCount, we can't test generate these dynamically so we just always have 50 fields
    public Integer field0 = 0, field1 = 1, field2 = 2, field3 = 3, field4 = 4,
            field5 = 5, field6 = 6, field7 = 7, field8 = 8, field9 = 9,
            field10 = 10, field11 = 11, field12 = 12, field13 = 13, field14 = 14,
            field15 = 15, field16 = 16, field17 = 17, field18 = 18, field19 = 19,
            field20 = 20, field21 = 21, field22 = 22, field23 = 23, field24 = 24,
            field25 = 25, field26 = 26, field27 = 27, field28 = 28, field29 = 29,
            field30 = 30, field31 = 31, field32 = 32, field33 = 33, field34 = 34,
            field35 = 35, field36 = 36, field37 = 37, field38 = 38, field39 = 39,
            field40 = 40, field41 = 41, field42 = 42, field43 = 43, field44 = 44,
            field45 = 45, field46 = 46, field47 = 47, field48 = 48, field49 = 49;
}

public class DataGenerator {
    public static Map<String, Object> generateTestData(int depth, int collectionSize, int stringLength) {
        Map<String, Object> result = new HashMap<>();

        // Generate deeply nested object (tests maxReferenceDepth)
        result.put("deepObject", depth > 0 ? createNestedObject(depth, 1) : null);

        // Generate object with many fields (tests maxFieldCount)
        result.put("manyFields", new ManyFieldsObject());

        // Generate large collection (tests maxCollectionSize)
        List<Integer> largeCollection = new ArrayList<>();
        for (int i = 0; i < collectionSize; i++) {
            largeCollection.add(i);
        }
        result.put("largeCollection", largeCollection);

        // Generate long string (tests maxLength)
        result.put("longString", stringLength > 0 ? "A".repeat(stringLength) : "");

        return result;
    }

    private static NestedObject createNestedObject(int maxLevel, int level) {
        NestedObject nested = level < maxLevel ? createNestedObject(maxLevel, level + 1) : null;
        return new NestedObject(level, nested);
    }
}

