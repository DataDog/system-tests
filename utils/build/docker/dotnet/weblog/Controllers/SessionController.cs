#if DDTRACE_2_7_0_OR_GREATER
using System;
using Microsoft.AspNetCore.Mvc;
using Microsoft.AspNetCore.Mvc.Formatters;
using Microsoft.AspNetCore.Mvc.ModelBinding;
using Microsoft.AspNetCore.Mvc.ModelBinding.Binders;
using Microsoft.AspNetCore.Routing;
using System.Collections.Generic;
using System.Threading.Tasks;
using Datadog.Trace.AppSec;

namespace weblog
{
    [ApiController]
    [Route("session")]
    public class SessionController : Controller
    {
	    [HttpGet("new")]
        public IActionResult New()
        {
            HttpContext.Session.Set(Guid.NewGuid().ToString(), [1, 2, 3, 4, 5]);
            return Content(HttpContext.Session.Id);
        }
		
        [HttpGet("user")]
        public IActionResult User(string sdk_user)
        {
            if (sdk_user != null)
            {
                EventTrackingSdk.TrackUserLoginSuccessEvent(sdk_user);
            }

            return Content($"Hello, set the user to {sdk_user}");
        }
    }
}
#endif