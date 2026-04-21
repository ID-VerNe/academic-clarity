import socket
import os
import sys
import unittest

class TestEnvironmentReadiness(unittest.TestCase):
    def test_frontend_port_availability(self):
        """验证前端端口 30517 是否可用"""
        port = 30517
        host = '127.0.0.1'
        try:
            # 尝试建立一个监听 socket，模拟 Vite 的绑定动作
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind((host, port))
            s.close()
        except PermissionError:
            self.fail(f"Port {port} is locked by system/firewall (EACCES). Cannot start dev server.")
        except OSError as e:
            if e.errno == 10048: # WSAEADDRINUSE
                # 已被占用属于正常错误，但 EACCES (Permission Denied) 是异常的
                pass
            else:
                self.fail(f"Unknown OS error on port {port}: {e}")

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
