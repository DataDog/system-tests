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
    [Route("session")]
    public class SessionController : Controller
    {
	    [HttpGet("new")]
        public IActionResult New()
        {
            return Content($"Session created");
        }
		
        [HttpGet("user")]
        public IActionResult User(string sdk_user)
        {
            if (sdk_user != null)
            {
                var userDetails = new UserDetails()
                {
                    Id = sdk_user,
                };
                Tracer.Instance.ActiveScope?.Span.SetUser(userDetails);
            }

            return Content($"Hello, set the user to {sdk_user}");
        }
    }
}
#endif