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
    [Route("exceptionreplay")]
    public class ExceptionReplayController : Controller
    {
        [HttpGet("simple")]
        [Consumes("application/json", "application/xml")]
        public IActionResult ExceptionReplaySimple()
        {
            throw new System.Exception("Simple exception");
        }

        [HttpGet("recursion")]
        [Consumes("application/json", "application/xml")]
        [System.Runtime.CompilerServices.MethodImpl(System.Runtime.CompilerServices.MethodImplOptions.NoInlining)]
        public IActionResult exceptionReplayRecursion(int depth)
        {
            return exceptionReplayRecursionHelper(depth, depth);
        }

        [HttpGet("recursion_inline")]
        [Consumes("application/json", "application/xml")]
        public IActionResult exceptionReplayRecursion_inline(int depth)
        {
            return exceptionReplayRecursionHelper(depth, depth);
        }

        private IActionResult exceptionReplayRecursionHelper(int originalDepth, int currentDepth)
        {
            if (currentDepth > 0)
            {
                return exceptionReplayRecursionHelper(originalDepth, currentDepth - 1);
            }
            else
            {
                throw new System.Exception($"recursion exception depth {originalDepth}");
            }
        }

        [HttpGet("inner")]
        [Consumes("application/json", "application/xml")]
        public IActionResult ExceptionReplayInner()
        {
            try
            {
                throw new System.Exception("Inner exception");
            }
            catch (System.Exception ex)
            {
                throw new System.Exception("Outer exception", ex);
            }
        }

        [HttpGet("rps")]
        [Consumes("application/json", "application/xml")]
        public IActionResult ExceptionReplayRockPaperScissors(string shape)
        {
            if (shape == "rock")
            {
                throw new ExceptionReplayRock();
            }

            if (shape == "paper")
            {
                throw new ExceptionReplayPaper();
            }

            if (shape == "scissors")
            {
                throw new ExceptionReplayScissors();
            }

            return Content("No exception");
        }

        private void DeepFunctionC()
        {
            throw new System.Exception("Multiple stack frames exception");
        }

        private void DeepFunctionB()
        {
            DeepFunctionC();
        }

        private void DeepFunctionA()
        {
            DeepFunctionB();
        }

        [HttpGet("multiframe")]
        [Consumes("application/json", "application/xml")]
        public IActionResult ExceptionReplayMultiframe()
        {
            DeepFunctionA();
            return Content("Should not reach here");
        }

        private async Task<IActionResult> AsyncThrow()
        {
            throw new System.Exception("Async exception");
        }

        [HttpGet("async")]
        [Consumes("application/json", "application/xml")]
        public async Task<IActionResult> ExceptionReplayAsync()
        {
            return await AsyncThrow();
        }

        [HttpGet("outofmemory")]
        [Consumes("application/json", "application/xml")]
        public IActionResult ExceptionReplayOutOfMemory()
        {
            throw new System.OutOfMemoryException("outofmemory");
        }

        [HttpGet("stackoverflow")]
        [Consumes("application/json", "application/xml")]
        public IActionResult ExceptionReplayStackOverflow()
        {
            throw new System.StackOverflowException("stackoverflow");
        }

        [HttpGet("firsthit")]
        [Consumes("application/json", "application/xml")]
        public IActionResult ExceptionReplayFirstHit()
        {
            throw new System.InvalidOperationException("firsthit");
        }
    }
}
