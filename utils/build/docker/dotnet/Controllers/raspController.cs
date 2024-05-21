using Microsoft.AspNetCore.Mvc;
using Microsoft.AspNetCore.Routing;
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
    }
}
