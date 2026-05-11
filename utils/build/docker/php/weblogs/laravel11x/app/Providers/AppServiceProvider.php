<?php

namespace App\Providers;

use Illuminate\Support\ServiceProvider;

class AppServiceProvider extends ServiceProvider
{
    public function register(): void {}

    public function boot(): void
    {
        // DDTrace 1.19.x hardcodes usr.exists=false and omits usr.id for failed logins.
        // We register a PHP post-hook that runs after the tracer's own hook and calls
        // the automated SDK function again with the correct values when the user is found.
        // Signature follows DDTrace 1.x convention: ($This, $scope, $args, $retval).
        // Guard: DDTrace extension is absent during artisan migrate at image build time.
        if (!function_exists('DDTrace\hook_method')) {
            return;
        }
        \DDTrace\hook_method(
            'Illuminate\Auth\SessionGuard',
            'attempt',
            null,
            function ($This, $scope, $args, $retval): void {
                if ($retval !== false) {
                    return;
                }
                if (!function_exists('\datadog\appsec\track_user_login_failure_event_automated')) {
                    return;
                }
                $credentials = $args[0] ?? [];
                $login       = $credentials['username'] ?? ($credentials['email'] ?? '');
                if ($login === '') {
                    return;
                }
                $user = \App\Models\User::where('username', $login)->first();
                if ($user === null) {
                    return;
                }
                \datadog\appsec\track_user_login_failure_event_automated(
                    $login,
                    (string) $user->getAuthIdentifier(),
                    true,
                    []
                );
            }
        );
    }
}
