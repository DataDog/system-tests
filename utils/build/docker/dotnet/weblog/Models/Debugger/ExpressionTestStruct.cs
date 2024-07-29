using System;
using System.Collections.Generic;
using System.Linq;

namespace weblog.Models.Debugger
{
    internal struct ExpressionTestStruct
    {
        public int IntValue = 1;
        public double DoubleValue = 1.1;
        public string StringValue = "one";
        public bool BoolValue = true;

        public List<string> Collection = new List<string>() {"one", "two", "three"};
        public Dictionary<string, int> Dictionary = new Dictionary<string, int>() { { "one", 1 }, { "two", 2 }, { "three", 3 }, { "four", 4 } };

        public ExpressionTestStruct(){}
    }
}
