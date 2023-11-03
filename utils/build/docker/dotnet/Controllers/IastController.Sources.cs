using Microsoft.AspNetCore.Http;
using Microsoft.AspNetCore.Mvc;
using Microsoft.AspNetCore.Routing;
using System;
using System.Collections.Generic;
using System.Data.SqlClient;
using System.Diagnostics;
using System.Linq;
using System.Security.Cryptography;
using System.Threading.Tasks;
#nullable disable

namespace weblog
{
    public partial class IastController : Controller
    {
        [HttpPost("source/body/test")]
        public IActionResult test_source_body(string value)
        {
            return MakeRequest(value);
        }
    }
}
