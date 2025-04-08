<?php
require __DIR__ . '/vendor/autoload.php';

use Monolog\Logger;
use Monolog\Handler\StreamHandler;

// Create the logger
$logger = new Logger('webapp');

// Add handler to write to stderr (which is where error_log writes to by default)
$logger->pushHandler(new StreamHandler('php://stderr', Logger::DEBUG));

// Log the message from GET parameter
if (isset($_GET['msg'])) {
    $logger->info('Received message', ['message' => $_GET['msg']]);
} else {
    $logger->warning('No message provided in GET parameters');
}
?>