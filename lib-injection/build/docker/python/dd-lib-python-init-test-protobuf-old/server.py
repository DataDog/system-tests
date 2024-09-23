import socket
import signal
import sys

import addressbook_pb2

def handle_sigterm(signo, sf):
    print("Received SIGTERM")
    sys.exit(0)


def request_loop():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(("0.0.0.0", 18080))

    print("Listening on port 18080")
    server.listen()

    while True:
        conn, addr = server.accept()
        print(f"Accepted connection from {addr}")

        # Drain the request from the fixture
        data = conn.recv(4096)

        print("Received request")

        # Do some stuff with the protobuf
        person = addressbook_pb2.Person()
        person.id = 1234
        person.name = "John Doe"
        person.email = "john@ibm.com"

        print(person)

        print("Sending response")

        # Send a standard response back to the fixture and teardown
        conn.send(b"HTTP/1.1 200 OK\r\nContent-Length: 0\r\n\r\n")
        conn.close()


signal.signal(signal.SIGTERM, handle_sigterm)
request_loop()
