import socket
import os
import sys
import unittest

class TestEnvironmentReadiness(unittest.TestCase):
    def test_frontend_port_availability(self):
        """验证前端端口 30517 或备用端口是否可用 (Vite strictPort=false)"""
        base_port = 30517
        host = '127.0.0.1'
        found_available = False
        errors = []

        for port in range(base_port, base_port + 5):
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s.bind((host, port))
                s.close()
                found_available = True
                break
            except PermissionError:
                errors.append(f"Port {port}: Permission Denied (EACCES)")
                continue
            except OSError as e:
                if e.errno == 10048: # WSAEADDRINUSE
                    errors.append(f"Port {port}: In Use")
                    continue
                else:
                    errors.append(f"Port {port}: OS Error {e.errno}")
                    continue

        if not found_available:
            self.fail(f"Could not find an available port in range {base_port}-{base_port+4}. Errors: {errors}")
        else:
            print(f"  Frontend port check passed (found available port in range)")

    def test_backend_port_availability(self):
        """验证后端端口 38391 是否可用"""
        port = 38391
        host = '127.0.0.1'
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind((host, port))
            s.close()
        except Exception as e:
            self.fail(f"Backend port {port} is blocked: {e}")

if __name__ == "__main__":
    unittest.main()
