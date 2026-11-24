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

    // Normalized route endpoints (RFC-1103, amended by RFC-1125). The handlers don't bind the route values: only the
    // route declarations matter.
    [HttpGet("api_security/multi-params-in-segment/{id}.{format}")]
    [HttpGet("api_security/three-params/{a}-{b}-{c}")]
    [HttpGet("api_security/optional-params/{id}.{format?}")]
    [HttpGet("api_security/static-text/user-{id}")]
    [HttpGet("api_security/version/v{version}/items")]
    [HttpGet("api_security/files/{name}.json")]
    [HttpGet("api_security/optional-segment/{id}/{tab?}")]
    [HttpGet("api_security/catch-all/{*path}")]
    // ASP.NET Core doesn't allow an optional parameter after static text in a segment, so declare two routes
    [HttpGet("api_security/search")]
    [HttpGet("api_security/search.{format}")]
    [HttpGet("api_security/optional-chain/{x?}/{y?}")]
    [HttpGet("api_security/encoded/café")]
    [HttpGet("api_security/param-names/{user-id}/{user_id}")]
    [HttpGet("api_security/drafts")]
    [HttpGet("api_security/drafts/preview")]
    public IActionResult NormalizedRoute()
    {
        return Content("ok");
    }
}