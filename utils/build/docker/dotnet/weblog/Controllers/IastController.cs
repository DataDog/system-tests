using Microsoft.AspNetCore.Http;
using Microsoft.AspNetCore.Mvc;
using Microsoft.AspNetCore.Routing;
using System;
using System.Collections.Generic;
using System.Data.SqlClient;
using System.Diagnostics;
using System.Linq;
using System.Net.Mail;
using System.Web;
using System.Xml;
using System.Security.Cryptography;
using System.Threading.Tasks;
using Microsoft.Data.Sqlite;

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
        public string expression{get; set;}
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

        [HttpGet("/iast/source/path/test")]
        public IActionResult pathTest()
        {
            try
            {
                System.Diagnostics.Process.Start(Request.Path);

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
            return ExecuteCommandInternal(data.cmd, false);
        }

        [HttpPost("cmdi/test_secure")]
        public IActionResult test_secure_cmdI([FromForm] RequestData data)
        {
            return ExecuteCommandInternal("ls", false);
        }

        private IActionResult ExecuteCommandInternal(string commandLine, bool useShell = true)
        {
            try
            {
                if (!string.IsNullOrEmpty(commandLine))
                {
                    ProcessStartInfo startInfo = new ProcessStartInfo();
                    startInfo.FileName = commandLine;
                    startInfo.UseShellExecute = useShell;
                    var result = Process.Start(startInfo);
                    return Content($"Process launched.");
                }
                else
                {
                    return Content("No process name was provided");
                }
            }
            catch (Exception)
            {
                return Content("Non existing file.");
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

        [HttpGet("hstsmissing/test_insecure")]
        public IActionResult test_insecure_hstsmissing()
        {
            Response.Headers["Strict-Transport-Security"] = "max-age=-3153";
            Response.Headers.Append("X-Forwarded-Proto", "https");
            return Content("Ok", "text/html");
        }

        [HttpGet("hstsmissing/test_secure")]
        public IActionResult test_secure_hstsmissing()
        {
            Response.Headers.Append("Strict-Transport-Security", "max-age=31536000");
            Response.Headers.Append("X-Forwarded-Proto", "https");
            return Content("Ok", "text/html");
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
                return Content("File content: " + result);
            }
            catch (UnauthorizedAccessException)
            {
                // Normal Exception caught: The file in the test "/var/log" is not accessible
                return StatusCode(200);
            }
            catch (Exception e)
            {
                Console.WriteLine(e);
                return StatusCode(500, "Error reading file.");
            }
        }

        [HttpPost("path_traversal/test_secure")]
        public IActionResult TestSecurePathTraversal([FromForm] RequestData data)
        {
            try
            {
                var result = System.IO.File.ReadAllText("file.txt");
                return Content("File content: " + result);
            }
            catch (System.IO.FileNotFoundException)
            {
                // Normal Exception caught: The file "file.txt" hardcoded for the test does not exist
                return StatusCode(200);
            }
            catch (Exception e)
            {
                Console.WriteLine(e);
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
            return MakeRequest("https://www.datadoghq.com");
        }

        private IActionResult MakeRequest(string url)
        {
            try
            {
                var result = new System.Net.Http.HttpClient().GetStringAsync(url).Result;
                return Content("Response: " + result);
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
                return Content("Connection created");
            }
            catch
            {
                return Content("Error creating connection");
            }
        }

        [HttpPost("ldapi/test_secure")]
        public IActionResult TestSecureLdap([FromForm] string username, [FromForm] string password)
        {
            try
            {
                _ = new System.DirectoryServices.DirectoryEntry("LDAP://ldap.example.com/OU=Users,DC=example,DC=com", username, password);
                return Content("Connection created");
            }
            catch
            {
                return Content("Error creating connection");
            }
        }

        [HttpPost("header_injection/test_insecure")]
        public IActionResult test_insecure_header_injection([FromForm] string test)
        {
            Response.Headers["returnedHeaderKey"] = test;
            return Content("Ok");
        }

        [HttpPost("header_injection/test_secure")]
        public IActionResult test_secure_header_injection([FromForm] string test)
        {
            Response.Headers["returnedHeaderKey"] = "notTainted";
            return Content("Ok");
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
                        sb.AppendLine($"{reader["user"]}, {reader["pwd"]}");
                    }

                    return Content(sb.ToString());
                }
                else
                {
                    return BadRequest("No params provided");
                }
            }
            catch (Exception e)
            {
                Console.WriteLine(e);
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
                    cmd.CommandText = "SELECT * FROM users WHERE user = $user";
                    cmd.Parameters.Add(new SqliteParameter("$user", username));

                    using var reader = cmd.ExecuteReader();
                    while (reader.Read())
                    {
                        sb.AppendLine(reader["user"]?.ToString() + ", " + reader["pwd"]?.ToString());
                    }

                    return Content(sb.ToString());
                }
                else
                {
                    return BadRequest("No params provided");
                }
            }
            catch (Exception e)
            {
                Console.WriteLine(e);
                return StatusCode(500, "Error executing query.");
            }
        }

        [HttpGet("weak_randomness/test_insecure")]
        public IActionResult test_insecure_weakRandomness()
        {
            return Content("Weak random number: " + (new Random()).Next().ToString(), "text/html");
        }

        [HttpGet("weak_randomness/test_secure")]
        public IActionResult test_secure_weakRandomness()
        {
            return Content("Secure random number: " + RandomNumberGenerator.GetInt32(100).ToString(), "text/html");
        }

        [HttpGet("trust-boundary-violation/test_insecure")]
        public IActionResult test_insecure_trustBoundaryViolation([FromQuery] string username, [FromQuery] string password)
        {
            HttpContext.Session.SetString("UserData", username);
            return Content("Parameter added to session. User : " + HttpContext.Session.GetString("UserData"));
        }

        [HttpGet("trust-boundary-violation/test_secure")]
        public IActionResult test_secure_trustBoundaryViolation([FromQuery] string username, [FromQuery] string password)
        {
            return Content("Nothing added to session");
        }

        [HttpPost("unvalidated_redirect/test_insecure_header")]
        public IActionResult test_insecure_redirect_header([FromForm] string location)
        {
            Response.Headers["location"] = location;
            return Content("Redirected to " + location);
        }

        [HttpPost("unvalidated_redirect/test_secure_header")]
        public IActionResult test_secure_redirect_header()
        {
            var location = "http://dummy.location.com";
            Response.Headers["location"] = location;
            return Content("Redirected to " + location);
        }

        [HttpPost("unvalidated_redirect/test_insecure_redirect")]
        public IActionResult test_insecure_redirect([FromForm] string location)
        {
            Response.Redirect(location);
            return Content("Redirected to " + location);
        }

        [HttpPost("unvalidated_redirect/test_secure_redirect")]
        public IActionResult test_secure_redirect()
        {
            var location = "http://dummy.location.com";
            Response.Redirect(location);
            return Content("Redirected to " + location);
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
        public IActionResult test_source_body([FromBody] BodyForIast body)
        {
            try
            {
                var result = System.IO.File.ReadAllText(body.value);
                return Content("Executed injection");
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
                return Content("Executed injection");
            }
            catch
            {
                return StatusCode(500, "Error executing query.");
            }
        }

        [HttpPost("mongodb-nosql-injection/test_insecure")]
        public IActionResult test_insecure_mongodb_injection([FromForm] string key)
        {
            try
            {
                var mongoDbHelper = new MongoDbHelper("mongodb://mongodb:27017", "test-db");
                var filter = "{ \"user\": \"" + key + "\" }";
                mongoDbHelper.Find("users", filter);

                return Content("Executed injection");
            }
            catch (Exception e)
            {
                Console.WriteLine(e);
                return StatusCode(500, "Error executing query.");
            }
        }

        [HttpPost("mongodb-nosql-injection/test_secure")]
        public IActionResult test_secure_mongodb_injection([FromForm] string key)
        {
            try
            {
                var mongoDbHelper = new MongoDbHelper("mongodb://mongodb:27017", "test-db");
                var filter = MongoDbHelper.CreateSimpleDocument("user", key);
                mongoDbHelper.Find("users", filter);

                return Content("Executed secure injection");
            }
            catch (Exception e)
            {
                Console.WriteLine(e);
                return StatusCode(500, "Error executing query.");
            }
        }

        private class ReflectionInjection { } // Class name passed as parameter in the reflection injection test

        [HttpPost("reflection_injection/test_insecure")]
        public IActionResult test_insecure_reflection_injection([FromForm] string param)
        {

            try
            {
                var type = Type.GetType(param);
                Activator.CreateInstance(type!);
            }
            catch
            {
                return StatusCode(500, "Error executing reflection.");
            }

            return Content("Executed reflection injection");
        }

        [HttpPost("reflection_injection/test_secure")]
        public IActionResult test_secure_reflection_injection([FromForm] string param)
        {
            try
            {
                var type = Type.GetType("System.Text.StringBuilder")!;
                Activator.CreateInstance(type);
                return Content("Executed secure injection");
            }
            catch (Exception e)
            {
                Console.WriteLine(e);
                return StatusCode(500, "Error executing safe reflection.");
            }
        }

        [HttpGet("insecure-auth-protocol/test")]
        public IActionResult test_insecure_auth_protocol()
        {
            // Reset the deduplication of vulnerabilities using reflection
            var type = Type.GetType("Datadog.Trace.Iast.HashBasedDeduplication, Datadog.Trace")!;
            var instance = type.GetProperty("Instance")!.GetValue(null);
            var field = type.GetField("_vulnerabilityHashes", System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance);
            field!.SetValue(instance, new HashSet<int>());

            return StatusCode(200);
        }

        private readonly string xmlContent = @"<?xml version=""1.0"" encoding=""ISO-8859-1""?>
		<data><user><name>jaime</name><password>1234</password><account>administrative_account</account></user>
		<user><name>tom</name><password>12345</password><account>toms_acccount</account></user>
		<user><name>guest</name><password>anonymous1234</password><account>guest_account</account></user>
		</data>";

        [HttpPost("xpathi/test_insecure")]
        public IActionResult test_insecure_xpath_injection([FromForm] RequestData data)
        {

            var findUserXPath = "/data/user[name/text()='" + data.expression + "' and password/text()='" + data.expression + "}']";
            var doc = new XmlDocument();
            doc.LoadXml(xmlContent);
            var result = doc.SelectSingleNode(findUserXPath);
            return result is null ?
                Content($"Invalid user/password") :
                Content($"User " + result.ChildNodes[0].InnerText + " successfully logged.");
        }

        [HttpPost("xpathi/test_secure")]
        public IActionResult test_secure_xpath_injection([FromForm] RequestData data)
        {
            var findUserXPath = "/data/user[name/text()='user' and password/text()='value']";
            var doc = new XmlDocument();
            doc.LoadXml(xmlContent);
            var result = doc.SelectSingleNode(findUserXPath);
            return result is null ?
                Content($"Invalid user/password") :
                Content($"User " + result.ChildNodes[0].InnerText + " successfully logged.");
        }

        [HttpPost("email_html_injection/test_insecure")]
        public IActionResult TestInsecureEmailHtmlInjection([FromForm] string username, [FromForm] string email)
        {
            try
            {
                var mailMessage = BuildMailMessage(username);

                using (var client = new SmtpClient())
                {
                    client.Send(mailMessage);
                }

                return Content("Email sent");
            }
            catch
            {
                return Content("Error sending email");
            }
        }

        [HttpPost("email_html_injection/test_secure")]
        public IActionResult TestSecureEmailHtmlInjection([FromForm] string username, [FromForm] string email)
        {
            try
            {
                var mailMessage = BuildMailMessage(HttpUtility.HtmlEncode(username));

                using (var client = new SmtpClient())
                {
                    client.Send(mailMessage);
                }

                return Content("Email sent");
            }
            catch
            {
                return Content("Error sending email");
            }
        }

        private MailMessage BuildMailMessage(string name)
        {
            var contentHtml = "Hi " + name + "!";
            var subject = "Welcome!";

            var mailMessage = new MailMessage();
            // Not setting the MailMessage To/From properties will throw an exception when sending without going further
            mailMessage.Subject = subject;
            mailMessage.Body = contentHtml;
            mailMessage.IsBodyHtml = true;
            return mailMessage;
        }


        [HttpGet("sampling-by-route-method-count/{count}")]
        public IActionResult TestSecureEmailHtmlInjection(int count)
        {
            GetSHA1_1();
            GetSHA1_2();
            GetSHA1_3();
            GetSHA1_4();
            GetSHA1_5();
            GetSHA1_6();
            GetSHA1_7();
            GetSHA1_8();
            GetSHA1_9();
            GetSHA1_10();
            GetSHA1_11();
            GetSHA1_12();
            GetSHA1_13();
            GetSHA1_14();
            GetSHA1_15();

            return Content("OK");

            static byte[] GetSHA1_1() { return SHA1.Create().ComputeHash([0, 1, 2, 3]); }
            static byte[] GetSHA1_2() { return SHA1.Create().ComputeHash([0, 1, 2, 3]); }
            static byte[] GetSHA1_3() { return SHA1.Create().ComputeHash([0, 1, 2, 3]); }
            static byte[] GetSHA1_4() { return SHA1.Create().ComputeHash([0, 1, 2, 3]); }
            static byte[] GetSHA1_5() { return SHA1.Create().ComputeHash([0, 1, 2, 3]); }
            static byte[] GetSHA1_6() { return SHA1.Create().ComputeHash([0, 1, 2, 3]); }
            static byte[] GetSHA1_7() { return SHA1.Create().ComputeHash([0, 1, 2, 3]); }
            static byte[] GetSHA1_8() { return SHA1.Create().ComputeHash([0, 1, 2, 3]); }
            static byte[] GetSHA1_9() { return SHA1.Create().ComputeHash([0, 1, 2, 3]); }
            static byte[] GetSHA1_10() { return SHA1.Create().ComputeHash([0, 1, 2, 3]); }
            static byte[] GetSHA1_11() { return SHA1.Create().ComputeHash([0, 1, 2, 3]); }
            static byte[] GetSHA1_12() { return SHA1.Create().ComputeHash([0, 1, 2, 3]); }
            static byte[] GetSHA1_13() { return SHA1.Create().ComputeHash([0, 1, 2, 3]); }
            static byte[] GetSHA1_14() { return SHA1.Create().ComputeHash([0, 1, 2, 3]); }
            static byte[] GetSHA1_15() { return SHA1.Create().ComputeHash([0, 1, 2, 3]); }
        }

        [HttpGet("sampling-by-route-method-count-2/{count}")]
        public IActionResult TestSecureEmailHtmlInjection_2(int count)
        {
            GetSHA1_1();
            GetSHA1_2();
            GetSHA1_3();
            GetSHA1_4();
            GetSHA1_5();
            GetSHA1_6();
            GetSHA1_7();
            GetSHA1_8();
            GetSHA1_9();
            GetSHA1_10();
            GetSHA1_11();
            GetSHA1_12();
            GetSHA1_13();
            GetSHA1_14();
            GetSHA1_15();

            return Content("OK");

            static byte[] GetSHA1_1() { return SHA1.Create().ComputeHash([0, 1, 2, 3]); }
            static byte[] GetSHA1_2() { return SHA1.Create().ComputeHash([0, 1, 2, 3]); }
            static byte[] GetSHA1_3() { return SHA1.Create().ComputeHash([0, 1, 2, 3]); }
            static byte[] GetSHA1_4() { return SHA1.Create().ComputeHash([0, 1, 2, 3]); }
            static byte[] GetSHA1_5() { return SHA1.Create().ComputeHash([0, 1, 2, 3]); }
            static byte[] GetSHA1_6() { return SHA1.Create().ComputeHash([0, 1, 2, 3]); }
            static byte[] GetSHA1_7() { return SHA1.Create().ComputeHash([0, 1, 2, 3]); }
            static byte[] GetSHA1_8() { return SHA1.Create().ComputeHash([0, 1, 2, 3]); }
            static byte[] GetSHA1_9() { return SHA1.Create().ComputeHash([0, 1, 2, 3]); }
            static byte[] GetSHA1_10() { return SHA1.Create().ComputeHash([0, 1, 2, 3]); }
            static byte[] GetSHA1_11() { return SHA1.Create().ComputeHash([0, 1, 2, 3]); }
            static byte[] GetSHA1_12() { return SHA1.Create().ComputeHash([0, 1, 2, 3]); }
            static byte[] GetSHA1_13() { return SHA1.Create().ComputeHash([0, 1, 2, 3]); }
            static byte[] GetSHA1_14() { return SHA1.Create().ComputeHash([0, 1, 2, 3]); }
            static byte[] GetSHA1_15() { return SHA1.Create().ComputeHash([0, 1, 2, 3]); }
        }

        [HttpPost("sampling-by-route-method-count/{count}")]
        public IActionResult TestSecureEmailHtmlInjection_Post([FromForm] int count)
        {
            GetSHA1_1();
            GetSHA1_2();
            GetSHA1_3();
            GetSHA1_4();
            GetSHA1_5();
            GetSHA1_6();
            GetSHA1_7();
            GetSHA1_8();
            GetSHA1_9();
            GetSHA1_10();
            GetSHA1_11();
            GetSHA1_12();
            GetSHA1_13();
            GetSHA1_14();
            GetSHA1_15();

            return Content("OK");

            static byte[] GetSHA1_1() { return SHA1.Create().ComputeHash([0, 1, 2, 3]); }
            static byte[] GetSHA1_2() { return SHA1.Create().ComputeHash([0, 1, 2, 3]); }
            static byte[] GetSHA1_3() { return SHA1.Create().ComputeHash([0, 1, 2, 3]); }
            static byte[] GetSHA1_4() { return SHA1.Create().ComputeHash([0, 1, 2, 3]); }
            static byte[] GetSHA1_5() { return SHA1.Create().ComputeHash([0, 1, 2, 3]); }
            static byte[] GetSHA1_6() { return SHA1.Create().ComputeHash([0, 1, 2, 3]); }
            static byte[] GetSHA1_7() { return SHA1.Create().ComputeHash([0, 1, 2, 3]); }
            static byte[] GetSHA1_8() { return SHA1.Create().ComputeHash([0, 1, 2, 3]); }
            static byte[] GetSHA1_9() { return SHA1.Create().ComputeHash([0, 1, 2, 3]); }
            static byte[] GetSHA1_10() { return SHA1.Create().ComputeHash([0, 1, 2, 3]); }
            static byte[] GetSHA1_11() { return SHA1.Create().ComputeHash([0, 1, 2, 3]); }
            static byte[] GetSHA1_12() { return SHA1.Create().ComputeHash([0, 1, 2, 3]); }
            static byte[] GetSHA1_13() { return SHA1.Create().ComputeHash([0, 1, 2, 3]); }
            static byte[] GetSHA1_14() { return SHA1.Create().ComputeHash([0, 1, 2, 3]); }
            static byte[] GetSHA1_15() { return SHA1.Create().ComputeHash([0, 1, 2, 3]); }
        }
    }
}
