using Microsoft.AspNetCore.Mvc;
using System.Collections.Generic;
using Datadog.Trace.AppSec;
using Microsoft.AspNetCore.Mvc.RazorPages.Infrastructure;
using weblog.Models.ApiSecurity;

namespace weblog
{
    [ApiController]
    [Route("tag_value")]
    public class TagValueController : Controller
    {
        private void DoHeaders()
        {
            const string contentLangHeader = "content-language";

            string contentLang = HttpContext.Request.Query[contentLangHeader].ToString();

            if (!string.IsNullOrWhiteSpace(contentLang))
            {
                HttpContext.Response.Headers.Add(contentLangHeader, contentLang);
            }
        }

        [HttpPost("{tag}/{status}")]
        [Consumes("application/x-www-form-urlencoded")]
        public IActionResult IndexForm(string tag, string status, [FromForm] Model model)
        {
            DoHeaders();

            if (tag != null)
            {
                var details = new Dictionary<string, string>()
                {
                    { "value", tag }
                };
                EventTrackingSdk.TrackCustomEvent("system_tests_appsec_event", details);

                var statusCode = int.Parse(status);
                HttpContext.Response.StatusCode = statusCode;

                return Content($"Value tagged");
            }

            return Content("Hello, World!\\n");
        }

        [HttpGet("{tag}/{status}")]
        public IActionResult IndexForm(string? tag, string status)
        {
            DoHeaders();

            if (tag != null)
            {
                var details = new Dictionary<string, string?>
                {
                    { "value", tag }
                };
                EventTrackingSdk.TrackCustomEvent("system_tests_appsec_event", details);

                var statusCode = int.Parse(status);
                HttpContext.Response.StatusCode = statusCode;

                return Content($"Value tagged");
            }

            return Content("Hello, World!\\n");
        }

        [HttpGet("api_match_AS00{tag_value}/{status_code}")]
        // ReSharper disable once InconsistentNaming, system tests demand it
        public IActionResult ApiSecurity([FromRoute(Name = "tag_value")] int tagValue,
            [FromRoute(Name = "status_code")] int statusCode, [FromQuery(Name = "x-Option")] string? xOption)
        {
            HttpContext.Response.StatusCode = statusCode;
            Response.Headers["x-option"] = xOption;
            return Content("Ok");
        }

        [HttpPost("api_match_AS00{tag_value}/{status_code}")]
        // ReSharper disable once InconsistentNaming, system tests demand it
        public IActionResult ApiSecurityForm([FromRoute(Name = "tag_value")] int tagValue,
            [FromRoute(Name = "status_code")] int statusCode, [FromForm]RequestBodyModel bodyModel,
            [FromQuery(Name = "x-option")] string? xOption)
        {
            HttpContext.Response.StatusCode = statusCode;
            Response.Headers["x-option"] = xOption;
            return Content("Ok");
        }
        
        [HttpPost("api_match_AS00{tag_value}/{status_code}")]
        [Consumes("application/json")]
        // ReSharper disable once InconsistentNaming, system tests demand it
        public IActionResult ApiSecurityJson([FromRoute(Name = "tag_value")] int tagValue,
            [FromRoute(Name = "status_code")] int statusCode, [FromBody]RequestBodyModel bodyModel,
            [FromQuery(Name = "x-option")] string? xOption)
        {
            HttpContext.Response.StatusCode = statusCode;
            Response.Headers["x-option"] = xOption;
            return Content("Ok");
        }

        [HttpPost("payload_in_response_body_001/{status_code}")]
        [Consumes("application/x-www-form-urlencoded")]
        public IActionResult PayloadInResponseBody([FromRoute(Name = "status_code")] int statusCode,
            [FromForm] PayloadInResponseBodyModel payload)
        {
            HttpContext.Response.StatusCode = statusCode;
            return Json(new Dictionary<string, PayloadInResponseBodyModel> { { "payload", payload } });
        }
    }
}
