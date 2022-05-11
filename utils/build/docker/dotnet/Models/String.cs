using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using System.Xml.Serialization;

namespace weblog.Models
{
    [XmlType(TypeName = "string")]
    public class String
    {
        [XmlAttribute("attack")]
        public string Attack { get; set; }

        public override string ToString() => $"model Models.String with property attack {Attack}";
    }
}
