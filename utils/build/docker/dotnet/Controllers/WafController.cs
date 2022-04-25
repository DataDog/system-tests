using Microsoft.AspNetCore.Mvc;

namespace weblog
{
    public class WafController : Controller
    {
        [HttpPost]
        public IActionResult Index(Model model)
        {
            return Content("Hello post world\n");
        }
    }
}
