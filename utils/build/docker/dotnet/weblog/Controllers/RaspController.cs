using Microsoft.AspNetCore.Mvc;
using Microsoft.AspNetCore.Routing;
using Microsoft.Data.Sqlite;
using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Data.SqlClient;
using System.Diagnostics;
using System.Xml.Serialization;

#nullable disable

namespace weblog
{
    [ApiController]
    [Route("rasp")]
    public partial class RaspController : Controller
    {
        [HttpGet("shi")]
        public IActionResult shiGet(string list_dir)
        {
            return ExecuteCommandInternal("ls " + list_dir);
        }

        [XmlRoot("list_dir")]
        public class ShiModel
        {
            [XmlText]
            public string Value { get; set; }
        }

        [HttpPost("shi")]
        [Consumes("application/xml")]
        public IActionResult shiPostXml([FromBody] ShiModel data)
        {
            return ExecuteCommandInternal("ls " + data.Value);
        }

        [HttpPost("shi")]
        [Consumes("application/x-www-form-urlencoded")]
        public IActionResult shiPostForm([FromForm] Model data)
        {
            return ExecuteCommandInternal("ls " + data.List_dir);
        }

        [HttpPost("shi")]
        [Consumes("application/json")]
        public IActionResult shiPostJson([FromBody] Model data)
        {
            return ExecuteCommandInternal("ls " + data.List_dir);
        }

        [HttpGet("cmdi")]
        public IActionResult cmdiGet(string command)
        {
            return ExecuteCommandInternal(command, false);
        }

        [XmlRoot("command")]
        public class Command
        {
            [XmlElement("cmd")]
            public List<string> Cmd { get; set; }
        }

        [HttpPost("cmdi")]
        [Consumes("application/xml")]
        public IActionResult cmdiPostXml([FromBody] Command data)
        {
            List<string> arguments = null;
            if (data is not null && data.Cmd is not null && data.Cmd.Count > 1)
            {
                arguments = data.Cmd.GetRange(1, data.Cmd.Count - 1);
            }

            return ExecuteCommandInternal(data?.Cmd[0], false, arguments);
        }

        [HttpPost("cmdi")]
        [Consumes("application/x-www-form-urlencoded")]
        public IActionResult cmdiPostForm([FromForm] Model data)
        {
            return ExecuteCommandInternal(data.Command, false);
        }

        public class CmdiJsonModel
        {
            public List<string>? Command { get; set; }
        }

        [HttpPost("cmdi")]
        [Consumes("application/json")]
        public IActionResult cmdiPostJson([FromBody] CmdiJsonModel data)
        {
            List<string> arguments = null;
            if (data is not null && data.Command is not null && data.Command.Count > 1)
            {
                arguments = data.Command.GetRange(1, data.Command.Count - 1);
            }

            return ExecuteCommandInternal(data?.Command[0], false, arguments);
        }

        private IActionResult ExecuteCommandInternal(string commandLine, bool useShell = true, List<string>? argumentList = null)
        {
            try
            {
                if (!string.IsNullOrEmpty(commandLine))
                {
                    ProcessStartInfo startInfo = new ProcessStartInfo();
                    startInfo.FileName = commandLine;
                    startInfo.UseShellExecute = useShell;

                    if (argumentList is not null)
                    {
                        foreach (var argument in argumentList)
                        {
                            startInfo.ArgumentList.Add(argument);
                        }
                    }

                    var result = Process.Start(startInfo);
                    return Content($"Process launched.");
                }
                else
                {
                    return Content("No process name was provided");
                }
            }
            catch (Win32Exception)
            {
                return Content("Non existing file:" + commandLine);
            }
        }

        [HttpGet("lfi")]
        public IActionResult lfiGet(string file)
        {
            try
            {
                var result = System.IO.File.ReadAllText(file);
                return Content(result);
            }
            catch (System.IO.FileNotFoundException)
            {
                return Content("File not found");
            }
        }

        [XmlRoot("file")]
        public class FileModel
        {
            [XmlText]
            public string Value { get; set; }
        }

        [HttpPost("lfi")]
        [Consumes("application/xml")]
        public IActionResult lfiPostXml([FromBody] FileModel data)
        {
            var result = System.IO.File.ReadAllText(data.Value);
            return Content(result);
        }

        [HttpPost("lfi")]
        [Consumes("application/x-www-form-urlencoded")]
        public IActionResult lfiPostForm([FromForm] Model data)
        {
            var result = System.IO.File.ReadAllText(data.File);
            return Content(result);
        }

        [HttpPost("lfi")]
        [Consumes("application/json")]
        public IActionResult lfiPostJson([FromBody] Model data)
        {
            var result = System.IO.File.ReadAllText(data.File);
            return Content(result);
        }

        [HttpGet("ssrf")]
        public IActionResult SsrfGet(string domain)
        {
            var result = new System.Net.Http.HttpClient().GetStringAsync(("http://" + domain)).Result;
            return Content(result);
        }

        [XmlRoot("domain")]
        public class SSrfModel
        {
            [XmlText]
            public string Value { get; set; }
        }

        [HttpPost("ssrf")]
        [Consumes("application/xml")]
        public IActionResult SsrfPostXml([FromBody] SSrfModel data)
        {
            var result = new System.Net.Http.HttpClient().GetStringAsync(("http://" + data.Value)).Result;
            return Content(result);
        }

        [HttpPost("ssrf")]
        [Consumes("application/x-www-form-urlencoded")]
        public IActionResult SsrfPostForm([FromForm] Model data)
        {
            var result = new System.Net.Http.HttpClient().GetStringAsync(("http://" + data.Domain)).Result;
            return Content(result);
        }

        [HttpPost("ssrf")]
        [Consumes("application/json")]
        public IActionResult SsrfPostJson([FromBody] Model data)
        {
            var result = new System.Net.Http.HttpClient().GetStringAsync(("http://" + data.Domain)).Result;
            return Content(result);
        }

        [HttpGet("sqli")]
        public IActionResult SqliGet(string user_id)
        {
            // [DIAG do-not-merge] timing in SqliGet to localize the 5s stall on Test_SqlServiceNameSource.
            var t0 = System.DateTime.UtcNow;
            System.Console.WriteLine($"[DIAG-CTRL ] {t0:HH:mm:ss.fffffff} SqliGet ENTER user_id={user_id}");
            try
            {
                if (!string.IsNullOrEmpty(user_id))
                {
                    var sw = System.Diagnostics.Stopwatch.StartNew();
                    var result = SqlQuery(user_id);
                    System.Console.WriteLine($"[DIAG-CTRL ] {System.DateTime.UtcNow:HH:mm:ss.fffffff} SqliGet SqlQuery done in {sw.Elapsed.TotalMilliseconds:F2}ms");
                    return Content(result);
                }
                else
                {
                    return BadRequest("No params provided");
                }
            }
            finally
            {
                System.Console.WriteLine($"[DIAG-CTRL ] {System.DateTime.UtcNow:HH:mm:ss.fffffff} SqliGet EXIT elapsed_ms={(System.DateTime.UtcNow - t0).TotalMilliseconds:F2}");
            }
        }

        [XmlRoot("user_id")]
        public class SqliModel
        {
            [XmlText]
            public string Value { get; set; }
        }

        [HttpPost("sqli")]
        [Consumes("application/xml")]
        public IActionResult SqliPostXml([FromBody] SqliModel data)
        {
            if (!string.IsNullOrEmpty(data.Value))
            {
                return Content(SqlQuery(data.Value));
            }
            else
            {
                return BadRequest("No params provided");
            }
        }

        [HttpPost("sqli")]
        [Consumes("application/x-www-form-urlencoded")]
        public IActionResult SqliPostForm([FromForm] Model data)
        {
            if (!string.IsNullOrEmpty(data.User_id))
            {
                return Content(SqlQuery(data.User_id));
            }
            else
            {
                return BadRequest("No params provided");
            }
        }


        [HttpPost("sqli")]
        [Consumes("application/json")]
        public IActionResult SqliPostJson([FromBody] Model data)
        {
            if (!string.IsNullOrEmpty(data.User_id))
            {
                return Content(SqlQuery(data.User_id));
            }
            else
            {
                return BadRequest("No params provided");
            }
        }

        private string SqlQuery(string user)
        {
            // [DIAG do-not-merge] sub-step timing inside the SQLite path.
            var swTotal = System.Diagnostics.Stopwatch.StartNew();
            var sb = new System.Text.StringBuilder();
            sb.AppendLine("Insecure SQL command executed:");

            var sw = System.Diagnostics.Stopwatch.StartNew();
            using var conn = Sql.GetSqliteConnection();
            var tCreate = sw.Elapsed.TotalMilliseconds;

            sw.Restart();
            conn.Open();
            var tOpen = sw.Elapsed.TotalMilliseconds;

            sw.Restart();
            using var cmd = conn.CreateCommand();
            cmd.CommandText = "SELECT * FROM users WHERE id='" + user + "'";
            var tCmd = sw.Elapsed.TotalMilliseconds;

            sw.Restart();
            using var reader = cmd.ExecuteReader();
            var tExec = sw.Elapsed.TotalMilliseconds;

            sw.Restart();
            while (reader.Read())
            {
                sb.AppendLine($"{reader["user"]}, {reader["pwd"]}");
            }
            var tRead = sw.Elapsed.TotalMilliseconds;

            System.Console.WriteLine($"[DIAG-SQL  ] {System.DateTime.UtcNow:HH:mm:ss.fffffff} SqlQuery user='{user}' total={swTotal.Elapsed.TotalMilliseconds:F2}ms create={tCreate:F2} open={tOpen:F2} cmd={tCmd:F2} exec={tExec:F2} read={tRead:F2}");
            return sb.ToString();
        }
    }
}
