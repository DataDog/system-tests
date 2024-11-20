using Microsoft.AspNetCore;
using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Hosting;
using Microsoft.AspNetCore.Http;

namespace MinimalWebApp
{
    public class Program
    {
        public static void Main(string[] args)
        {
            WebHost.CreateDefaultBuilder(args)
                .Configure(app =>
                {
                    app.Run(async context => await context.Response.WriteAsync("Hello World!"));
                })
                .Build()
                .Run();
        }
    }
}
