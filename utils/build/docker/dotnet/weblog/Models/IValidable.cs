using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;

namespace weblog.Models
{
    public interface IValidable
    {
        bool IsValid();
    }
}
