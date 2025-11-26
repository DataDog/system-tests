using System.Collections.Generic;

namespace weblog.Models.Debugger
{
    public class NestedObject
    {
        public int level { get; set; }
        public NestedObject nested { get; set; }
    }

    public class ManyFieldsObject
    {
        // Define 50 public properties to test maxFieldCount
        public int field0 { get; set; } = 0;
        public int field1 { get; set; } = 1;
        public int field2 { get; set; } = 2;
        public int field3 { get; set; } = 3;
        public int field4 { get; set; } = 4;
        public int field5 { get; set; } = 5;
        public int field6 { get; set; } = 6;
        public int field7 { get; set; } = 7;
        public int field8 { get; set; } = 8;
        public int field9 { get; set; } = 9;
        public int field10 { get; set; } = 10;
        public int field11 { get; set; } = 11;
        public int field12 { get; set; } = 12;
        public int field13 { get; set; } = 13;
        public int field14 { get; set; } = 14;
        public int field15 { get; set; } = 15;
        public int field16 { get; set; } = 16;
        public int field17 { get; set; } = 17;
        public int field18 { get; set; } = 18;
        public int field19 { get; set; } = 19;
        public int field20 { get; set; } = 20;
        public int field21 { get; set; } = 21;
        public int field22 { get; set; } = 22;
        public int field23 { get; set; } = 23;
        public int field24 { get; set; } = 24;
        public int field25 { get; set; } = 25;
        public int field26 { get; set; } = 26;
        public int field27 { get; set; } = 27;
        public int field28 { get; set; } = 28;
        public int field29 { get; set; } = 29;
        public int field30 { get; set; } = 30;
        public int field31 { get; set; } = 31;
        public int field32 { get; set; } = 32;
        public int field33 { get; set; } = 33;
        public int field34 { get; set; } = 34;
        public int field35 { get; set; } = 35;
        public int field36 { get; set; } = 36;
        public int field37 { get; set; } = 37;
        public int field38 { get; set; } = 38;
        public int field39 { get; set; } = 39;
        public int field40 { get; set; } = 40;
        public int field41 { get; set; } = 41;
        public int field42 { get; set; } = 42;
        public int field43 { get; set; } = 43;
        public int field44 { get; set; } = 44;
        public int field45 { get; set; } = 45;
        public int field46 { get; set; } = 46;
        public int field47 { get; set; } = 47;
        public int field48 { get; set; } = 48;
        public int field49 { get; set; } = 49;
    }

    public static class DataGenerator
    {
        public static Dictionary<string, object> GenerateTestData(int depth, int collectionSize, int stringLength)
        {
            var result = new Dictionary<string, object>();

            // Generate deeply nested object (tests maxReferenceDepth)
            result["deepObject"] = depth > 0 ? CreateNestedObject(depth) : null;

            // Generate object with many fields (tests maxFieldCount)
            result["manyFields"] = new ManyFieldsObject();

            // Generate large collection (tests maxCollectionSize)
            var largeCollection = new List<int>();
            for (int i = 0; i < collectionSize; i++)
            {
                largeCollection.Add(i);
            }
            result["largeCollection"] = largeCollection;

            // Generate long string (tests maxLength)
            result["longString"] = stringLength > 0 ? new string('A', stringLength) : "";

            return result;
        }

        private static NestedObject CreateNestedObject(int maxLevel, int level = 1)
        {
            var obj = new NestedObject
            {
                level = level,
                nested = level < maxLevel ? CreateNestedObject(maxLevel, level + 1) : null
            };

            return obj;
        }
    }
}
