<?php

namespace App\Controller;

use App\Entity\User;
use App\Security\AppAuthenticator;
use App\Security\UserProvider;
use Symfony\Bundle\FrameworkBundle\Controller\AbstractController;
use Symfony\Bundle\SecurityBundle\Security;
use Symfony\Component\HttpFoundation\Request;
use Symfony\Component\HttpFoundation\Response;
use Symfony\Component\PasswordHasher\Hasher\UserPasswordHasherInterface;
use Symfony\Component\Routing\Attribute\Route;
use Symfony\Component\Security\Core\Exception\UserNotFoundException;

class LoginController extends AbstractController
{
    private static array $newUsers = [
        'testnew' => ['id' => 'new-user'],
    ];

    public function __construct(
        private UserProvider $userProvider,
        private UserPasswordHasherInterface $passwordHasher,
        private Security $security,
    ) {}

    #[Route('/login', name: 'login', methods: ['GET', 'POST'])]
    public function login(Request $request): Response
    {
        $auth = $request->query->get('auth', '');

        if ($auth === 'local') {
            return $this->handleLocalLogin($request);
        }

        if ($auth === 'basic') {
            return $this->handleBasicLogin($request);
        }

        return new Response('', 200);
    }

    #[Route('/signup', name: 'signup', methods: ['POST'])]
    public function signup(Request $request): Response
    {
        $username       = $request->request->get('username', '');
        $password       = $request->request->get('password', '');
        $id             = isset(self::$newUsers[$username]) ? self::$newUsers[$username]['id'] : hash('sha256', $username);
        $hashedPassword = $this->passwordHasher->hashPassword(new User($id, $username, '', $username), $password);

        $user = $this->userProvider->createUser($id, $username, $hashedPassword, $username);
        $this->security->login($user, AppAuthenticator::class, 'main');

        return new Response('', 200);
    }

    private function handleLocalLogin(Request $request): Response
    {
        if (!$request->isMethod('POST')) {
            return new Response('', 200);
        }

        $username   = $request->request->get('username', '');
        $password   = $request->request->get('password', '');
        $sdkEvent   = $request->query->get('sdk_event', '');
        $sdkTrigger = $request->query->get('sdk_trigger', '');
        $sdkUser    = $request->query->get('sdk_user', '');
        $sdkExists  = filter_var($request->query->get('sdk_user_exists', 'false'), FILTER_VALIDATE_BOOLEAN);

        if ($sdkTrigger === 'before' && $sdkEvent !== '') {
            $this->callSdk($sdkEvent, $sdkUser, $sdkExists);
        }

        $success = $this->attemptLogin($username, $password);

        if ($sdkTrigger === 'after' && $sdkEvent !== '') {
            $this->callSdk($sdkEvent, $sdkUser, $sdkExists);
        }

        if ($success) {
            return new Response('', 200);
        }

        return new Response('', 401);
    }

    private function handleBasicLogin(Request $request): Response
    {
        $authHeader = $request->headers->get('Authorization', '');
        if (!str_starts_with($authHeader, 'Basic ')) {
            return new Response('', 401);
        }

        $decoded  = base64_decode(substr($authHeader, 6));
        $parts    = explode(':', $decoded, 2);
        $username = $parts[0] ?? '';
        $password = $parts[1] ?? '';

        $sdkEvent   = $request->query->get('sdk_event', '');
        $sdkTrigger = $request->query->get('sdk_trigger', '');
        $sdkUser    = $request->query->get('sdk_user', '');
        $sdkExists  = filter_var($request->query->get('sdk_user_exists', 'false'), FILTER_VALIDATE_BOOLEAN);

        if ($sdkTrigger === 'before' && $sdkEvent !== '') {
            $this->callSdk($sdkEvent, $sdkUser, $sdkExists);
        }

        $success = $this->attemptLogin($username, $password);

        if ($sdkTrigger === 'after' && $sdkEvent !== '') {
            $this->callSdk($sdkEvent, $sdkUser, $sdkExists);
        }

        return new Response('', $success ? 200 : 401);
    }

    private function attemptLogin(string $username, string $password): bool
    {
        try {
            $user = $this->userProvider->loadUserByIdentifier($username);
        } catch (UserNotFoundException) {
            return false;
        }

        if (!$this->passwordHasher->isPasswordValid($user, $password)) {
            return false;
        }

        $this->security->login($user, AppAuthenticator::class, 'main');

        return true;
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
