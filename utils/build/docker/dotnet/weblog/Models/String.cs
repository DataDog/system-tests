using System;
using System.Collections.Generic;
using System.Linq;
using System.Runtime.Serialization;
using System.Text;
using System.Threading.Tasks;
using System.Xml.Serialization;

namespace weblog.Models
{
    [XmlType(TypeName = "string")]
    public class String : IValidable
    {
        [XmlAttribute("attack")]
        public string? Attack { get; set; }

        public bool IsValid() => !string.IsNullOrEmpty(Attack);

        public override string ToString() => $"model Models.String with property attack {Attack}";
    }
}
