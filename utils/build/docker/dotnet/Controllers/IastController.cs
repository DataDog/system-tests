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

namespace weblog
{
    public class RequestData
    {
        public string user{get; set;}
        public string cmd{get; set;}
        public string table{get; set;}
    };
    
    [ApiController]
    [Route("iast")]
    public class IastController : Controller
    {
        [HttpGet("insecure_hashing/test_md5_algorithm")]
        public IActionResult test_md5_algorithm(string user)
        {
            var byteArg = new byte[] { 3, 5, 6 };
            var result = MD5.Create().ComputeHash(byteArg);
            return Content(result.ToString());
        }

        [HttpGet("insecure_hashing/test_secure_algorithm")]
        public IActionResult test_secure_algorithm(string user)
        {
            var byteArg = new byte[] { 3, 5, 6 };
            var result = SHA256.Create().ComputeHash(byteArg);
            return Content(result.ToString());
        }


        [HttpGet("insecure_hashing/multiple_hash")]
        public IActionResult multiple_hash(string user)
        {
            var byteArg = new byte[] { 3, 5, 6 };
            var result = MD5.Create().ComputeHash(byteArg);
            _ = GetSHA1(byteArg);
            return Content(result.ToString());
        }
        
        private byte[] GetSHA1(byte[] array)
        {
            return SHA1.Create().ComputeHash(array);
        }
        
        [HttpGet("insecure_hashing/deduplicate")]
        public IActionResult deduplicate(string user)
        {
            var byteArg = new byte[] { 3, 5, 6 };
            
            byte[] result = null;
            for (int i = 0; i < 10; i++)
            {
                result = MD5.Create().ComputeHash(byteArg);
            }
            
            return Content(result.ToString());
        }
        
        [HttpPost("source/parameter/test")]
        public IActionResult parameterTestPost([FromForm] RequestData data)
        {
            try
            {
                System.Diagnostics.Process.Start(data.table);
                
                return Content("Ok");
            }
            catch(Exception ex)
            {
                return StatusCode(500, "NotOk");
            }
        }

        [HttpGet("source/parameter/test")]
        public IActionResult parameterTest(string table)
        {
            try
            {
                System.Diagnostics.Process.Start(table);
                
                return Content("Ok");
            }
            catch(Exception ex)
            {
                return StatusCode(500, "NotOk");
            }
        }
        
        [HttpPost("source/parametername/test")]
        public IActionResult parameterNameTestPost([FromForm] RequestData data)
        {
            try
            {
                System.Diagnostics.Process.Start(data.user);
                
                return Content("Ok");
            }
            catch(Exception ex)
            {
                return StatusCode(500, "NotOk");
            }
        }

        [HttpGet("source/parametername/test")]
        public IActionResult parameterNameTest(string user)
        {
            try
            {
                System.Diagnostics.Process.Start(Request.Query.First().Key);
                
                return Content("Ok");
            }
            catch(Exception ex)
            {
                return StatusCode(500, "NotOk");
            }
        }

        [HttpPost("cmdi/test_insecure")]
        public IActionResult test_insecure_cmdI([FromForm] RequestData data)
        {
            try
            {            
                if (!string.IsNullOrEmpty(data.cmd))
                {
                    var result = Process.Start(data.cmd);
                    return Content($"Process launched: " + result.ProcessName);
                }
                else
                {
                    return BadRequest($"No file was provided");
                }
            }
            catch
            {
                return StatusCode(500, "Error launching process.");
            }
        }
        
        [HttpPost("cmdi/test_secure")]
        public IActionResult test_secure_cmdI([FromForm] RequestData data)
        {
            try
            {
                    var result = Process.Start("ls");
                    return Content($"Process launched: " + result.ProcessName);
            }
            catch
            {
                return StatusCode(500, "Error launching process.");
            }
        }

        [HttpGet("insecure-cookie/test_insecure")]
        public IActionResult test_insecure_insecureCookie()
        {
            Response.Headers.Append("Set-Cookie", "user-id=7;HttpOnly;SameSite=Strict");
            return StatusCode(200);
        }

        [HttpGet("insecure-cookie/test_secure")]
        public IActionResult test_secure_insecureCookie()
        {
            Response.Headers.Append("Set-Cookie", "user-id=7;Secure;HttpOnly;SameSite=Strict");
            return StatusCode(200);
        }

        
        [HttpGet("no-samesite-cookie/test_insecure")]
        public IActionResult test_insecure_noSameSiteCookie()
        {
            Response.Headers.Append("Set-Cookie", "user-id=7;HttpOnly;Secure");
            return StatusCode(200);
        }
        
        [HttpGet("no-samesite-cookie/test_secure")]
        public IActionResult test_secure_noSameSiteCookie()
        {
            Response.Headers.Append("Set-Cookie", "user-id=7;Secure;HttpOnly;SameSite=Strict");
            return StatusCode(200);
        }
    }
}
