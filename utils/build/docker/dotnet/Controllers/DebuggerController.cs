using Microsoft.AspNetCore.Mvc;
using Microsoft.AspNetCore.Mvc.Formatters;
using Microsoft.AspNetCore.Mvc.ModelBinding;
using Microsoft.AspNetCore.Mvc.ModelBinding.Binders;
using Microsoft.AspNetCore.Routing;
using System.Collections.Generic;
using System.Threading.Tasks;

namespace weblog
{
    [ApiController]
    [Route("debugger")]
    public class DebuggerController : Controller
    {
        [HttpGet("log")]
        [Consumes("application/json", "application/xml")]
        public IActionResult LogProbe()
        {
            return Content($"Log probe");
        }

        [HttpGet("metric")]
        [Consumes("application/json", "application/xml")]
        public IActionResult MetricProbe()
        {
            int id = 0;
            return Content($"Metric Probe {id}");
        }

        [HttpGet("span")]
        [Consumes("application/json", "application/xml")]
        public IActionResult SpanProbe()
        {
            string span = "some";
            return Content($"Span Probe {span}");
        }

        [HttpGet("span-decoration")]
        [Consumes("application/json", "application/xml")]
        public IActionResult SpanDecorationProbe(string arg, int intArg)
        {
            var intLocal = arg.Length * 2;
            return Content($"Span Decoration Probe {intLocal}");
        }
    }
}
