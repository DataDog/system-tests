using System;
using System.Collections.Generic;

namespace weblog.Models.Debugger
{
    internal struct ExpressionTestStruct
    {
        public int IntValue;
        public double DoubleValue;
        public string StringValue;
        public bool BoolValue;

        public List<string> Collection;
        public Dictionary<string, int> Dictionary;

        public ExpressionTestStruct(int intValue, double doubleValue, string stringValue, bool boolValue, List<string> collection, Dictionary<string, int> dictionary)
        {
            IntValue = intValue;
            DoubleValue = doubleValue;
            StringValue = stringValue;
            BoolValue = boolValue;
            Collection = collection ?? new List<string> { "one", "two", "three" };
            Dictionary = dictionary ?? new Dictionary<string, int> { { "one", 1 }, { "two", 2 }, { "three", 3 }, { "four", 4 } };
        }

        public static ExpressionTestStruct CreateDefault()
        {
            return new ExpressionTestStruct(
                1, 
                1.1, 
                "one", 
                true, 
                new List<string> { "one", "two", "three" }, 
                new Dictionary<string, int> { { "one", 1 }, { "two", 2 }, { "three", 3 }, { "four", 4 } }
            );
        }
    }
}