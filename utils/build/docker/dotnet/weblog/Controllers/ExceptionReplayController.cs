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
        public IActionResult ExceptionReplayRecursion(int depth)
        {
            if (depth > 0)
            {
                return ExceptionReplayRecursion(depth - 1);
            }
            else
            {
                throw new System.Exception("Recursion exception");
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
    }
}
