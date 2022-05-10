using Microsoft.AspNetCore.Mvc;

namespace weblog
{
    [ApiController]
    [Route("waf")]
    public class WafController : Controller
    {
        [HttpPost]
        [Consumes("application/json", "application/xml", "text/plain")]
        public IActionResult Index([FromBody]Model model)
        {
            return Content($"Hello post world, value was {model.Value}");
        }

        [HttpPost]
        [Consumes("application/x-www-form-urlencoded")]
        public IActionResult IndexForm([FromForm]Model model)
        {
            return Content($"Hello post world, value was {model.Value}");
        }

        [HttpPost]
        public IActionResult IndexAll(Model model)
        {
            return Content($"Hello post world, value was {model.Value}");
        }
    }
}
