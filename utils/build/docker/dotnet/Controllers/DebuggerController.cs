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

        [HttpGet("metric/{id}")]
        [Consumes("application/json", "application/xml")]
        public IActionResult MetricProbe(int id)
        {
            id++;
            return Content($"Metric Probe {id}");
        }

        [HttpGet("span")]
        [Consumes("application/json", "application/xml")]
        public IActionResult SpanProbe()
        {
            return Content("Span probe");
        }

        private int intLocal = 0;
        [HttpGet("span-decoration/{arg}/{intArg}")]
        [Consumes("application/json", "application/xml")]
        public IActionResult SpanDecorationProbe(string arg, int intArg)
        {
            intLocal = intArg * arg.Length;
            return Content($"Span Decoration Probe {intLocal}");
        }

        private int intMixLocal = 0;
        [HttpGet("mix/{arg}/{intArg}")]
        [Consumes("application/json", "application/xml")]
        public IActionResult MixProbe(string arg, int intArg)
        {
            intMixLocal = intArg * arg.Length;
            return Content($"Mixed result {intMixLocal}");
        }
    }
}