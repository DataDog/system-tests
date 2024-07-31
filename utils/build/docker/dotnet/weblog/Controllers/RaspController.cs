using Microsoft.AspNetCore.Mvc;
using Microsoft.AspNetCore.Routing;
using Microsoft.Data.Sqlite;
using System;
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
        [HttpGet("lfi")]
        public IActionResult lfiGet(string file)
        {
            var result = System.IO.File.ReadAllText(file);
            return Content(result);
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
			if (!string.IsNullOrEmpty(user_id))
			{
				return Content(SqlQuery(user_id));
			}
			else
			{
				return BadRequest("No params provided");
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
            var sb = new System.Text.StringBuilder();
            sb.AppendLine("Insecure SQL command executed:");
            using var conn = Sql.GetSqliteConnection();
            conn.Open();
            using var cmd = conn.CreateCommand();
            cmd.CommandText = "SELECT * FROM users WHERE id='" + user + "'";
            using var reader = cmd.ExecuteReader();

            while (reader.Read())
            {
                sb.AppendLine($"{reader["user"]}, {reader["pwd"]}");
            }

            return sb.ToString();
        }
    }
}
