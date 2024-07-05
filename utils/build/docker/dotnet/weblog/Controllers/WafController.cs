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
    [Route("waf")]
    public class WafController : Controller
    {
        [HttpPost]
        [Consumes("application/json", "application/xml")]
        public IActionResult Index([FromBody] object obj)
        {
            return Content($"Hello post world, value was {obj}");
        }

        [HttpPost]
        [Consumes("application/x-www-form-urlencoded")]
        public IActionResult IndexForm([FromForm] Model model)
        {
            return Content($"Hello post world, value was {model.Value}");
        }

        [HttpPost]
        [Consumes("application/octet-stream", "text/plain")]
        public IActionResult IndexRaw()
        {
            return Content($"Hello post world");
        }


        //dont remove, some system tests queries dont have a content type and we get an AmbiguousRouteException
        [HttpPost]
        public IActionResult IndexAll(Model model)
        {
            return Content($"Hello post world, value was {model.Value}");
        }

    }
}
