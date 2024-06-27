#nullable enable

using System.Threading.Tasks;
using Microsoft.AspNetCore.Mvc;
using Datadog.Trace;

namespace weblog
{
    public class CreateExtraServiceController: Controller
    {
        [HttpGet]
        public IActionResult Index(string? serviceName)
        {
            using var scope = Tracer.Instance.StartActive("create-extra-service");
            scope.Span.ServiceName = serviceName;

            return Content("Created: " + serviceName);
        }
    }
}
