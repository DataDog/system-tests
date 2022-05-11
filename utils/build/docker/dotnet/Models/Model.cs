using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;

namespace weblog
{
    public class Model
    {
        public string Value { get; set; }
        public string Value2 { get; set; }

        public override string ToString() => $"value {Value}, value2 {Value2}";
    }
}
