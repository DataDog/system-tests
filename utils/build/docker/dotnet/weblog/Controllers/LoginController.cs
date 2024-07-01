#if DDTRACE_2_23_0_OR_GREATER

#nullable enable
using System;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using Datadog.Trace.AppSec;
using Microsoft.AspNetCore.Identity;
using Microsoft.AspNetCore.Mvc;
using weblog.Models;

namespace weblog;

[Route("login")]
public class LoginController : Controller
{
    private readonly SignInManager<IdentityUser> _signInManager;
    private readonly UserManager<IdentityUser> _userManager;
    private readonly IUserStore<IdentityUser> _userStore;

    public LoginController(SignInManager<IdentityUser> signInManager, UserManager<IdentityUser> userManager,
        IUserStore<IdentityUser> userStore)
    {
        _signInManager = signInManager;
        _userManager = userManager;
        _userStore = userStore;
    }

    [HttpGet("")]
    public async Task<IActionResult> IndexGet([FromQuery] LoginModel? loginQuery)
    {
        if (loginQuery?.Auth == "basic")
        {
            if (loginQuery is { SdkEvent: "success" })
            {
                EventTrackingSdk.TrackUserLoginSuccessEvent(loginQuery.SdkUser);
            }
            else if (loginQuery is { SdkEvent: "failure" })
            {
                EventTrackingSdk.TrackUserLoginFailureEvent(loginQuery.SdkUser, loginQuery.SdkUserExists ?? false);
            }

            var authorizationHeader = this.Request.Headers["Authorization"][0];
            var authBase64Decoded = Encoding.UTF8.GetString(
                Convert.FromBase64String(authorizationHeader.Replace("Basic ", "",
                    StringComparison.OrdinalIgnoreCase)));
            var authSplit = authBase64Decoded.Split(new[] { ':' }, 2);
            var result = await _signInManager.PasswordSignInAsync(authSplit[0], authSplit[1], false, lockoutOnFailure: false);
            if (result.Succeeded)
            {
                return Content("Successfully login as " + authSplit[0]);
            }

            Response.StatusCode = 401;
            return Content("Invalid login attempt");
        }

        if (User.Identity.IsAuthenticated)
        {
            return Content($"Logged in as{User.Identity.Name}");
        }

        return Content("Logged in");
    }

    [HttpPost]
    public async Task<IActionResult> Index(LoginModel model)
    {
        if (ModelState.IsValid)
        {
            if (model is { SdkEvent: "success" })
            {
                EventTrackingSdk.TrackUserLoginSuccessEvent(model.SdkUser);
            }
            else if (model is { SdkEvent: "failure" })
            {
                EventTrackingSdk.TrackUserLoginFailureEvent(model.SdkUser, model.SdkUserExists ?? false);
            }

            // This doesn't count login failures towards account lockout
            // To enable password failures to trigger account lockout, set lockoutOnFailure: true
            var result = await _signInManager.PasswordSignInAsync(model.UserName, model.Password, false,
                lockoutOnFailure: false);
            if (result.Succeeded)
            {
                return Content("Successfully login as " + model.UserName);
            }

            Response.StatusCode = 401;
            return Content("Invalid login attempt");
        }

        // If we got this far, something failed, redisplay form
        return RedirectToAction(nameof(Index));
    }

    [HttpPost("logout")]
    public IActionResult LogOut()
    {
        _signInManager.SignOutAsync();
        return RedirectToAction(nameof(Index));
    }
}
#endif