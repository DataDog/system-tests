<?php

namespace App\Security;

use Symfony\Component\HttpFoundation\Request;
use Symfony\Component\HttpFoundation\Response;
use Symfony\Component\Security\Core\Authentication\Token\TokenInterface;
use Symfony\Component\Security\Core\Exception\AuthenticationException;
use Symfony\Component\Security\Core\Exception\CustomUserMessageAuthenticationException;
use Symfony\Component\Security\Http\Authenticator\AbstractAuthenticator;
use Symfony\Component\Security\Http\Authenticator\Passport\Badge\UserBadge;
use Symfony\Component\Security\Http\Authenticator\Passport\Credentials\PasswordCredentials;
use Symfony\Component\Security\Http\Authenticator\Passport\Passport;

class AppAuthenticator extends AbstractAuthenticator
{
    public function supports(Request $request): ?bool
    {
        if ($request->attributes->get('_route') !== 'login') {
            return false;
        }

        $auth = $request->query->get('auth', '');

        if ($auth === 'local' && $request->isMethod('POST')) {
            return true;
        }

        if ($auth === 'basic') {
            return true;
        }

        return false;
    }

    public function authenticate(Request $request): Passport
    {
        $sdkTrigger = $request->query->get('sdk_trigger', '');
        $sdkEvent   = $request->query->get('sdk_event', '');
        $sdkUser    = $request->query->get('sdk_user', '');
        $sdkExists  = filter_var($request->query->get('sdk_user_exists', 'false'), FILTER_VALIDATE_BOOLEAN);

        if ($sdkTrigger === 'before' && $sdkEvent !== '') {
            $this->callSdk($sdkEvent, $sdkUser, $sdkExists);
        }

        $auth = $request->query->get('auth', '');

        if ($auth === 'basic') {
            $authHeader = $request->headers->get('Authorization', '');
            if (!str_starts_with($authHeader, 'Basic ')) {
                throw new CustomUserMessageAuthenticationException('Missing or invalid Authorization header');
            }
            $decoded  = base64_decode(substr($authHeader, 6));
            $parts    = explode(':', $decoded, 2);
            $username = $parts[0] ?? '';
            $password = $parts[1] ?? '';
        } else {
            $username = $request->request->get('username', '');
            $password = $request->request->get('password', '');
        }

        // Store username in session so the tracer's handleAuthenticationFailure hook can extract it
        // via extractLoginFromAuthFailure Path C (_security.last_username) for wrong-password failures.
        if ($request->hasSession()) {
            $request->getSession()->set('_security.last_username', $username);
        }

        return new Passport(new UserBadge($username), new PasswordCredentials($password));
    }

    public function onAuthenticationSuccess(Request $request, TokenInterface $token, string $firewallName): ?Response
    {
        // Login success is tracked automatically by the tracer via
        // AuthenticatorManager::handleAuthenticationSuccess hook.
        $sdkTrigger = $request->query->get('sdk_trigger', '');
        $sdkEvent   = $request->query->get('sdk_event', '');
        $sdkUser    = $request->query->get('sdk_user', '');
        $sdkExists  = filter_var($request->query->get('sdk_user_exists', 'false'), FILTER_VALIDATE_BOOLEAN);

        if ($sdkTrigger === 'after' && $sdkEvent !== '') {
            $this->callSdk($sdkEvent, $sdkUser, $sdkExists);
        }

        return new Response('', 200);
    }

    public function onAuthenticationFailure(Request $request, AuthenticationException $exception): ?Response
    {
        // Login failure is tracked automatically by the tracer via
        // AuthenticatorManager::handleAuthenticationFailure hook.
        $sdkTrigger = $request->query->get('sdk_trigger', '');
        $sdkEvent   = $request->query->get('sdk_event', '');
        $sdkUser    = $request->query->get('sdk_user', '');
        $sdkExists  = filter_var($request->query->get('sdk_user_exists', 'false'), FILTER_VALIDATE_BOOLEAN);

        if ($sdkTrigger === 'after' && $sdkEvent !== '') {
            $this->callSdk($sdkEvent, $sdkUser, $sdkExists);
        }

        return new Response('', 401);
    }

    private function callSdk(string $event, string $user, bool $exists): void
    {
        if ($event === 'success') {
            \datadog\appsec\track_user_login_success_event($user, []);
        } else {
            \datadog\appsec\track_user_login_failure_event($user, $exists, []);
        }
    }
}
