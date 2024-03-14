using Microsoft.AspNetCore.Mvc;
using Microsoft.AspNetCore.Mvc.Formatters;
using Microsoft.AspNetCore.Mvc.ModelBinding;
using Microsoft.AspNetCore.Mvc.ModelBinding.Binders;
using Microsoft.AspNetCore.Routing;
using System.Collections.Generic;
using System.Threading.Tasks;
using weblog.Models.Debugger;

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

        [HttpGet("log/pii/{arg}")]
        [Consumes("application/json", "application/xml")]
        public async Task<IActionResult> Pii(int arg)
        {
            PiiBase pii = null;

            switch (arg)
            {
                case 1:
                    pii = await Task.FromResult<PiiBase>(new Pii1());
                    break;
                case 2:
                    pii = await Task.FromResult<PiiBase>(new Pii2());
                    break;
                case 3:
                    pii = await Task.FromResult<PiiBase>(new Pii3());
                    break;
                case 4:
                    pii = await Task.FromResult<PiiBase>(new Pii4());
                    break;
                case 5:
                    pii = await Task.FromResult<PiiBase>(new Pii5());
                    break;
                case 6:
                    pii = await Task.FromResult<PiiBase>(new Pii6());
                    break;
                default:
                    pii = await Task.FromResult<PiiBase>(null);
                    break;
            }

            var value = pii?.TestValue;
            return Content($"PII {value}");
        }
    }
}