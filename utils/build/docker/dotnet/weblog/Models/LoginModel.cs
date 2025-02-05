using System.ComponentModel.DataAnnotations;
using Microsoft.AspNetCore.Mvc;

namespace weblog.Models;

public class LoginModel
{
    [Required]
    [Display(Name = "Username")]
    public string? UserName { get; set; }

    [Required]
    [DataType(DataType.Password)]
    public string? Password { get; set; }

    public string? Auth { get; set; }

    [FromQuery(Name = "sdk_event")]public string? SdkEvent { get; set; }

    [FromQuery(Name = "sdk_user")] public string? SdkUser { get; set; }

    [FromQuery(Name = "sdk_user_exists")] public bool? SdkUserExists { get; set; }

    [FromQuery(Name = "sdk_trigger")] public string? SdkTrigger { get; set; }
}
