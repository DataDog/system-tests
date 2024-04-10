using System;

namespace weblog.Models.ApiSecurity;

public class RequestBodyModel
{
    public KeyValueItem[]? main { get; set; }

    public string? nullable { get; set; }
}

public class KeyValueItem
{
    public string? key { get; set; }

    public double value { get; set; }
}
