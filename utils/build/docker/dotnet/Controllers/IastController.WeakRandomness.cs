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

namespace weblog;

public partial class IastController : Controller
{
    [HttpGet("weak_randomness/test_insecure")]
    public IActionResult test_insecure_weakRandomness(string user)
    {
        return Content("Weak random number: " + (new Random()).Next().ToString(), "text/html");
    }

    [HttpGet("weak_randomness/test_secure")]
    public IActionResult test_secure_weakRandomness(string user)
    {
        return Content("Secure random number: " + RandomNumberGenerator.GetInt32(100).ToString(), "text/html");
    }
}
