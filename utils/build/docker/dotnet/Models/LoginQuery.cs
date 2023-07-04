#nullable enable
using Microsoft.AspNetCore.Mvc;

namespace weblog.Models;

public class LoginQuery
{
    public string? Auth { get; set; }
    [FromQuery(Name = "sdk_event")] 
    public string? SdkEvent { get; set; }
    
    [FromQuery(Name = "sdk_user")] 
    public string? SdkUser { get; set; }
    
    [FromQuery(Name = "sdk_user_exists")] 
    public bool? SdkUserExists { get; set; }
}