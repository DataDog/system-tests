using System;
using System.Net.Http;
using System.Threading.Tasks;

namespace weblog
{
    public static class HttpClientWrapper
    {
        public static HttpClient HttpClient = new HttpClient();

        public static async Task<string> LocalGet(string path)
        {
            var baseUrl = Environment.GetEnvironmentVariable("WEBSITE_HOSTNAME") ?? "weblog:7777";
            var url = $"http://{baseUrl}";
            var simpleResponse = await HttpClient.GetStringAsync($"{url}{path}");
            return simpleResponse;
        }
    }
}
