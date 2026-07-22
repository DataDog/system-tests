<?php

namespace App\Security;

use Symfony\Component\HttpFoundation\Request;
use Symfony\Component\HttpFoundation\Response;
use Symfony\Component\HttpKernel\HttpKernelInterface;
use Symfony\Component\Security\Core\Authentication\Token\TokenInterface;
use Symfony\Component\Security\Http\Authentication\AuthenticationSuccessHandlerInterface;

class LoginSuccessHandler implements AuthenticationSuccessHandlerInterface
{
    public function __construct(
        private HttpKernelInterface $httpKernel,
    ) {}

    public function onAuthenticationSuccess(Request $request, TokenInterface $token): Response
    {
        $sdkTrigger = $request->query->get('sdk_trigger', '');
        $sdkUser    = $request->query->get('sdk_user', '');

        if ($sdkTrigger === 'before' && $sdkUser !== '') {
            \datadog\appsec\track_user_login_success_event($sdkUser, []);
        }

        if ($sdkTrigger === 'after' && $sdkUser !== '') {
            \datadog\appsec\track_user_login_success_event($sdkUser, []);
        }

        $subRequest = $request->duplicate();
        $subRequest->setMethod('GET');
        $subRequest->request->replace([]);

        return $this->httpKernel->handle($subRequest, HttpKernelInterface::SUB_REQUEST);
    }
}
