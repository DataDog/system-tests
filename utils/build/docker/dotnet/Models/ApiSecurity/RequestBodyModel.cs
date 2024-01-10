#nullable enable
using System;

namespace weblog.Models.ApiSecurity;

public class RequestBodyModel
{
    public KeyValueItem[] main { get; set; }

    public object? nullable { get; set; }
}

public class KeyValueItem
{
    public string key { get; set; }

    public int value { get; set; }
}