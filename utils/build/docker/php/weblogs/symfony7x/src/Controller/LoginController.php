<?php

namespace App\Controller;

use App\Entity\User;
use App\Security\AppAuthenticator;
use Doctrine\ORM\EntityManagerInterface;
use Symfony\Bundle\FrameworkBundle\Controller\AbstractController;
use Symfony\Bundle\SecurityBundle\Security;
use Symfony\Component\HttpFoundation\Request;
use Symfony\Component\HttpFoundation\Response;
use Symfony\Component\PasswordHasher\Hasher\UserPasswordHasherInterface;
use Symfony\Component\Routing\Attribute\Route;
use Symfony\Component\Security\Http\Authentication\AuthenticationUtils;

class LoginController extends AbstractController
{
    private static array $newUsers = [
        'testnew' => ['id' => 'new-user'],
    ];

    public function __construct(
        private UserPasswordHasherInterface $passwordHasher,
        private Security $security,
    ) {}

    #[Route('/login', name: 'login', methods: ['GET', 'POST'])]
    public function login(AuthenticationUtils $authenticationUtils): Response
    {
        // Authentication is handled by AppAuthenticator.
        // This method is reached only for GET requests or when the authenticator does not support the request.
        return new Response('', 200);
    }

    #[Route('/signup', name: 'signup', methods: ['POST'])]
    public function signup(Request $request, EntityManagerInterface $entityManager): Response
    {
        $username       = $request->request->get('username', '');
        $password       = $request->request->get('password', '');
        $id             = isset(self::$newUsers[$username]) ? self::$newUsers[$username]['id'] : hash('sha256', $username);
        $hashedPassword = $this->passwordHasher->hashPassword(new User($id, $username, '', $username), $password);

        $user = new User($id, $username, $hashedPassword, $username);
        $entityManager->persist($user);
        $entityManager->flush();

        $this->security->login($user, AppAuthenticator::class, 'main');

        return new Response('', 200);
    }
}
