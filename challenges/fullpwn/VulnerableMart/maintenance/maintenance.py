import socket
import os

# Standalone "maintenance" service. Runs in its OWN container with NO database,
# NO source for the other challenges, and NO flags — so RCE here cannot be used
# to shortcut the web-app challenge chain. This box is the prize for the
# port-scan -> command-injection step only.


def start_maintenance():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(('0.0.0.0', 50050))
    server.listen(5)
    print("Maintenance interface listening on 50050")

    while True:
        client, addr = server.accept()
        try:
            client.send(b"Maintenance Interface. Enter IP: ")
            data = client.recv(1024).decode().strip()
            if data:
                # Intentional command-injection vulnerability.
                response = os.popen(f"ping -c 1 {data}").read()
                client.send(response.encode())
        except Exception:
            pass
        finally:
            client.close()


if __name__ == '__main__':
    start_maintenance()
