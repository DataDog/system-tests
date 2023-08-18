#if DDTRACE_2_7_0_OR_GREATER
using Microsoft.AspNetCore.Mvc;
using Microsoft.AspNetCore.Mvc.Formatters;
using Microsoft.AspNetCore.Mvc.ModelBinding;
using Microsoft.AspNetCore.Mvc.ModelBinding.Binders;
using Microsoft.AspNetCore.Routing;
using System.Collections.Generic;
using System.Threading.Tasks;
using Datadog.Trace;

namespace weblog
{
    [ApiController]
    [Route("users")]
    public class UsersController : Controller
    {
        [HttpGet]
        public IActionResult Index(string user)
        {
            if (user != null)
            {
                var userDetails = new UserDetails()
                {
                    Id = user,
                };
                Tracer.Instance.ActiveScope?.Span.SetUser(userDetails);
            }

            return Content($"Hello, set the user to {user}");
        }
    }
}
#endif