using System.Collections.Generic;

namespace weblog.Models.ApiSecurity;

public class ResponseBodyModel
{
    public IDictionary<string, object> Main { get; set; }
    public object? Nullable { get; set; }
}

public class PayloadInResponseBodyModel
{
    public string? test_str { get; set; }

    public int test_int { get; set; }

    public double test_float { get; set; }

    public bool test_bool { get; set; }
}
