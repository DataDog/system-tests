<?php

namespace App\Security;

use Symfony\Component\HttpFoundation\Request;
use Symfony\Component\HttpFoundation\Response;
use Symfony\Component\Security\Core\Exception\AuthenticationException;
use Symfony\Component\Security\Http\Authentication\AuthenticationFailureHandlerInterface;

class LoginFailureHandler implements AuthenticationFailureHandlerInterface
{
    public function onAuthenticationFailure(Request $request, AuthenticationException $exception): Response
    {
        $sdkTrigger = $request->query->get('sdk_trigger', '');
        $sdkUser    = $request->query->get('sdk_user', '');
        $sdkExists  = filter_var($request->query->get('sdk_user_exists', 'false'), FILTER_VALIDATE_BOOLEAN);

        if ($sdkTrigger === 'before' && $sdkUser !== '') {
            \datadog\appsec\track_user_login_failure_event($sdkUser, $sdkExists, []);
        }

        if ($sdkTrigger === 'after' && $sdkUser !== '') {
            \datadog\appsec\track_user_login_failure_event($sdkUser, $sdkExists, []);
        }

        return new Response('', 401);
    }
}
