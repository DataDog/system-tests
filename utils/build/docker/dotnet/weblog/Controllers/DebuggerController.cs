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

        [HttpGet("pii")]
        [Consumes("application/json", "application/xml")]
        public async Task<IActionResult> Pii()
        {
            PiiBase? pii = await Task.FromResult<PiiBase>(new Pii());
            PiiBase? customPii = await Task.FromResult<PiiBase>(new CustomPii());
            var value = pii?.TestValue;
            var customValue = customPii?.TestValue;
            return Content($"PII {value}. CustomPII {customValue}");
        }

        [HttpGet("expression")]
        [Consumes("application/json", "application/xml")]
        public async Task<IActionResult> Expression(string inputValue)
        {
            var testStruct = await Task.FromResult<ExpressionTestStruct>(new ExpressionTestStruct());
            var localValue = inputValue.Length;

            return Content($"Great success number {localValue}");
        }

        [HttpGet("expression/exception")]
        [Consumes("application/json", "application/xml")]
        public IActionResult ExpressionException()
        {
            throw new System.Exception("Hello from exception");
        }

        [HttpGet("expression/comparison-operators")]
        [Consumes("application/json", "application/xml")]
        public IActionResult ExpressionComparisonOperators(int intValue, float floatValue, string strValue)
        {
            return Content($"Int value {intValue}. Float value {floatValue}. String value {strValue}");
        }
    }
}
