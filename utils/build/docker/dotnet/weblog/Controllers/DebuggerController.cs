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

        private int intLocal = 1000;
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
            return Content($"PII {value}. CustomPII {customValue}"); // must be line 64
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

        [HttpGet("expression/operators")]
        [Consumes("application/json", "application/xml")]
        public async Task<IActionResult> ExpressionOperators(int intValue, float floatValue, string strValue)
        {
            PiiBase? pii = await Task.FromResult<PiiBase>(new Pii());
            var piiValue = pii?.TestValue;
            return Content($"Int value {intValue}. Float value {floatValue}. String value {strValue}. Pii value {piiValue}");
        }

        [HttpGet("expression/strings")]
        [Consumes("application/json", "application/xml")]
        public IActionResult StringOperations(string strValue, string emptyString = "", string nullString = null)
        {
            return Content($"strValue {strValue}. emptyString {emptyString}. nullString {nullString}");
        }

        [HttpGet("expression/collections")]
        [Consumes("application/json", "application/xml")]
        public async Task<IActionResult> CollectionOperations()
        {
            var a0 = await CollectionFactory.GetCollection(0, "array");
            var l0 = await CollectionFactory.GetCollection(0, "list");
            var h0 = await CollectionFactory.GetCollection(0, "hash");
            var a1 = await CollectionFactory.GetCollection(1, "array");
            var l1 = await CollectionFactory.GetCollection(1, "list");
            var h1 = await CollectionFactory.GetCollection(1, "hash");
            var a5 = await CollectionFactory.GetCollection(5, "array");
            var l5 = await CollectionFactory.GetCollection(5, "list");
            var h5 = await CollectionFactory.GetCollection(5, "hash");

            return Content($"{a0.Count},{a1.Count},{a5.Count},{l0.Count},{l1.Count},{l5.Count},{h0.Count},{h1.Count},{h5.Count}.");
        }

        [HttpGet("expression/null")]
        [Consumes("application/json", "application/xml")]
        public async Task<IActionResult> Nulls(int? intValue = null, string strValue = null, bool? boolValue = null)
        {
            PiiBase pii = null;
            if (boolValue == true)
            {
                pii = await Task.FromResult<PiiBase>(null);
            }

            return Content($"Pii is null {pii is null}. intValue is null {intValue is null}. strValue is null {strValue is null}.");
        }

        [HttpGet("budgets/{loops}")]
        [Consumes("application/json", "application/xml")]
        public IActionResult Budgets(int loops)
        {
            for (int i = 0; i < loops; i++)
            {
                int j = i; // Capture snapshot here to test budgets.
            }
            return Content("Budgets");
        }

        [HttpGet("snapshot/limits")]
        [Consumes("application/json", "application/xml")]
        public IActionResult SnapshotLimits(int depth = 0, int collectionSize = 0, int stringLength = 0)
        {
            var data = DataGenerator.GenerateTestData(depth, collectionSize, stringLength);
            var deepObject = data["deepObject"];
            var manyFields = data["manyFields"];
            var largeCollection = data["largeCollection"];
            var longString = data["longString"];
            return Content("Capture limits probe"); // must be line 150
        }
    }
}
