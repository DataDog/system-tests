using Microsoft.AspNetCore.Mvc;

namespace weblog;

[ApiController]
public class ApiSecController : Controller
{
    [HttpGet]
    [Route("api_security/sampling/{status:int}")]
    public IActionResult ApiSecuritySamplingStatus(int status)
    {
        HttpContext.Response.StatusCode = status;
        return Content("Hello!");
    }

    [HttpGet]
    [Route("api_security_sampling/{i:int}")]
    public IActionResult ApiSecuritySampling(int i)
    {
        return Content("Ok");
    }
}