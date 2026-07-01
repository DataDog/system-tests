<?php

namespace App\Controller;

use App\Entity\User;
use Doctrine\ORM\EntityManagerInterface;
use Symfony\Bundle\FrameworkBundle\Controller\AbstractController;
use Symfony\Bundle\SecurityBundle\Security;
use Symfony\Component\HttpFoundation\Request;
use Symfony\Component\HttpFoundation\Response;
use Symfony\Component\PasswordHasher\Hasher\UserPasswordHasherInterface;
use Symfony\Component\Routing\Attribute\Route;

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
    public function login(): Response
    {
        return new Response('', Response::HTTP_OK);
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

        // Signup event is tracked automatically by the tracer via Doctrine\ORM\UnitOfWork::executeInserts hook.
        $entityManager->flush();

        $this->security->login($user);

        return new Response('', 200);
    }
}
