import socket
import os
import sys
import unittest

class TestEnvironmentReadiness(unittest.TestCase):
    def test_frontend_port_availability(self):
        """验证前端端口范围 (30517-30521) 是否有可用出口"""
        available = False
        for port in range(30517, 30522):
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.bind(('127.0.0.1', port))
                s.close()
                available = True
                print(f"  Frontend port check passed: {port}")
                break
            except:
                continue
        self.assertTrue(available, "No available frontend ports in range 30517-30521")

    def test_backend_port_availability(self):
        """验证后端端口范围 (38391-38395) 是否有可用出口"""
        available = False
        for port in range(38391, 38396):
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.bind(('127.0.0.1', port))
                s.close()
                available = True
                print(f"  Backend port check passed: {port}")
                break
            except:
                continue
        self.assertTrue(available, "No available backend ports in range 38391-38395")

if __name__ == "__main__":
    unittest.main()
