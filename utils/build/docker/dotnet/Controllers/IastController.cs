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
    public class RequestData
    {
        public string user{get; set;}
        public string cmd{get; set;}
        public string table{get; set;}
        public string path{get; set;}
        public string url{get; set;}
    };
    
    public class BodyForIast
    {
        public string name { get; set; }
        public string value { get; set; }
    }

    [ApiController]
    [Route("iast")]
    public partial class IastController : Controller
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
            catch
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
            catch
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
            catch
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
            catch
            {
                return StatusCode(500, "NotOk");
            }
        }

        [HttpGet("insecure_cipher/test_insecure_algorithm")]
        public IActionResult test_insecure_weakCipher()
        {
            DES.Create();
            return StatusCode(200);
        }
        
        [HttpGet("insecure_cipher/test_secure_algorithm")]
        public IActionResult test_secure_weakCipher()
        {
            Aes.Create();
            return StatusCode(200);
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
        
        [HttpGet("no-httponly-cookie/test_empty_cookie")]
        [HttpGet("no-samesite-cookie/test_empty_cookie")]
        [HttpGet("insecure-cookie/test_empty_cookie")]
        public IActionResult test_EmptyCookie()
        {
            Response.Headers.Append("Set-Cookie", string.Empty);
            return StatusCode(200);
        }

        [HttpGet("no-httponly-cookie/test_insecure")]
        public IActionResult test_insecure_noHttpOnly()
        {
            Response.Headers.Append("Set-Cookie", "user-id=7;Secure;SameSite=Strict");
            return StatusCode(200);
        }
        
        [HttpGet("no-httponly-cookie/test_secure")]
        public IActionResult test_secure_noHttpOnly()
        {
            Response.Headers.Append("Set-Cookie", "user-id=7;Secure;HttpOnly;SameSite=Strict");
            return StatusCode(200);
        }        
        
        [HttpPost("path_traversal/test_insecure")]
        public IActionResult TestInsecurePathTraversal([FromForm] RequestData data)
        {
            try
            {
                var result = System.IO.File.ReadAllText(data.path);
                return Content($"File content: " + result);
            }
            catch
            {
                return StatusCode(500, "Error reading file.");
            }
        }

        [HttpPost("path_traversal/test_secure")]
        public IActionResult TestSecurePathTraversal([FromForm] RequestData data)
        {
            try
            {
                var result = System.IO.File.ReadAllText("file.txt");
                return Content($"File content: " + result);
            }
            catch
            {
                return StatusCode(500, "Error reading file.");
            }
        }
        
        [HttpPost("ssrf/test_insecure")]
        public IActionResult TestInsecureSSRF([FromForm] RequestData data)
        {
            return MakeRequest(data.url);
        }
        
        [HttpPost("ssrf/test_secure")]
        public IActionResult TestSecureSSRF([FromForm] RequestData data)
        {
            return MakeRequest("notAUrl");
        }
        
        private IActionResult MakeRequest(string url)
        {
            try
            {
                var result = new System.Net.Http.HttpClient().GetStringAsync(url).Result;
                return Content($"Reponse: " + result);
            }
            catch
            {
                return StatusCode(500, "Error in request.");
            }
        }
        
        [HttpPost("ldapi/test_insecure")]
        public IActionResult TestInsecureLdap([FromForm] string username, [FromForm] string password)
        {
            try
            {
                string ldapPath = "LDAP://" + username + ":" + password + "@ldap.example.com/OU=Users,DC=example,DC=com";
                _ = new System.DirectoryServices.DirectoryEntry(ldapPath);
                return Content($"Conection created");
            }
            catch
            {
                return Content($"Error creating connection");
            }
        }
        
        [HttpPost("ldapi/test_secure")]
        public IActionResult TestSecureLdap([FromForm] string username, [FromForm] string password)
        {
            try
            {        
                _ = new System.DirectoryServices.DirectoryEntry("LDAP://ldap.example.com/OU=Users,DC=example,DC=com", username, password);
                return Content($"Conection created");
            }
            catch
            {
                return Content($"Error creating connection");
            }                
        }
        
        [HttpPost("sqli/test_insecure")]
        public IActionResult test_insecure_sqlI([FromForm] string username, [FromForm] string password)
        {
            try
            {
                if (!string.IsNullOrEmpty(username))
                {
                    var sb = new System.Text.StringBuilder();
                    sb.AppendLine("Insecure SQL command executed:");
                    using var conn = Sql.GetSqliteConnection();
                    conn.Open();
                    using var cmd = conn.CreateCommand();
                    cmd.CommandText = "SELECT * FROM users WHERE user = '" + username + "'";
                    using var reader = cmd.ExecuteReader();

                    while (reader.Read())
                    {
                        sb.AppendLine(reader["user"]?.ToString() + ", " + reader["pwd"]?.ToString());
                    }

                    return Content(sb.ToString());
                }
                else
                {
                    return BadRequest($"No params provided");
                }
            }
            catch
            {
                return StatusCode(500, "Error executing query.");
            }        
        }
        
        [HttpPost("sqli/test_secure")]
        public IActionResult test_secure_sqlI([FromForm] string username, [FromForm] string password)
        {
            try
            {
                if (!string.IsNullOrEmpty(username))
                {
                    var sb = new System.Text.StringBuilder();
                    sb.AppendLine("Secure SQL command executed:");
                    using var conn = Sql.GetSqliteConnection();
                    conn.Open();
                    using var cmd = conn.CreateCommand();
                    cmd.CommandText = "SELECT * FROM data WHERE value = $user";
                    cmd.Parameters.Add("$user");
                    cmd.Parameters["$user"].Value = username;
                    using var reader = cmd.ExecuteReader();
                    while (reader.Read())
                    {
                        sb.AppendLine(reader["value"]?.ToString());
                    }

                    return Content(sb.ToString());
                }
                else
                {
                    return BadRequest($"No params provided");
                }
            }
            catch
            {
                return StatusCode(500, "Error executing query.");
            }
        }

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
        
        [HttpGet("source/cookievalue/test")]
        public IActionResult test_cookie_value()
        {
            var process = Request.Cookies["table"];
            try
            {
                System.Diagnostics.Process.Start(process);                
                return Content("Ok");
            }
            catch
            {
                return StatusCode(500, "NotOk");
            }
        }
        
        [HttpGet("source/cookiename/test")]
        public IActionResult test_cookie_name()
        {
            var process = Request.Cookies.Keys.First();
            try
            {
                System.Diagnostics.Process.Start(process);                
                return Content("Ok");
            }
            catch
            {
                return StatusCode(500, "NotOk");
            }
        }                

        [HttpPost("source/body/test")]
        public IActionResult test_source_body([FromBody]BodyForIast body)
        {
            try
            {
                var result = System.IO.File.ReadAllText(body.value);
                return Content($"Executed injection");
            }
            catch
            {
                return StatusCode(500, "Error executing query.");
            }               
        }
        
        [HttpGet("source/header/test")]
        public IActionResult test_headerValue()
        {
            var headerValue = Request.Headers["table"].ToString();
            try
            {
                var result = System.IO.File.ReadAllText(headerValue);
                return Content($"Executed injection");
            }
            catch
            {
                return StatusCode(500, "Error executing query.");
            }               
        }
    }
}
