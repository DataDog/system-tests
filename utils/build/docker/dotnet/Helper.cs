using Datadog.Trace;
using System;
using System.Linq;
using System.Threading;


namespace weblog
{
    public class Helper
    {
        private static Random random = new Random();
        private const string chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789";

        public void GenerateSpan(int garbageTags)
        {
            using (var childScope = Tracer.Instance.StartActive("spans.child"))
            {
                childScope.Span.ResourceName = "span_" + System.Guid.NewGuid().ToString();
                for (int i = 0; i < garbageTags; i++)
                {
                    childScope.Span.SetTag("garbage" + i, RandomString(50));
                }

                // Send custom span tags
                string customSpanTags = Environment.GetEnvironmentVariable("DD_SPAN_CUSTOM_TAGS");
                if (!String.IsNullOrEmpty(customSpanTags)) {
                    string[] customSpanTagsArr = customSpanTags.Split(',');
                    foreach (var tag in customSpanTagsArr)
                    {
                        string[] arr = tag.Split(':');
                        childScope.Span.SetTag(arr[0], arr[1]);
                    }                    
                }
            }
        }

        private static string RandomString(int length)
        {
            return new string(
                Enumerable
                    .Range(1, length)
                    .Select(_ => chars[random.Next(chars.Length)])
                    .ToArray());
        }
    }
}
