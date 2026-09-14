"""
HTTP 请求封装工具类
提供统一的 API 请求方法和错误处理
"""
import requests
from test.config.settings import API_BASE_URL, REQUEST_TIMEOUT


class ApiClient:
    """API 请求客户端"""

    def __init__(self, base_url: str = API_BASE_URL, timeout: int = REQUEST_TIMEOUT):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json",
            "Accept": "application/json",
        })

    def get(self, path: str, params: dict = None) -> requests.Response:
        """发送 GET 请求"""
        url = f"{self.base_url}{path}"
        return self.session.get(url, params=params, timeout=self.timeout)

    def post(self, path: str, json_data: dict = None) -> requests.Response:
        """发送 POST 请求"""
        url = f"{self.base_url}{path}"
        return self.session.post(url, json=json_data, timeout=self.timeout)

    def put(self, path: str, json_data: dict = None) -> requests.Response:
        """发送 PUT 请求"""
        url = f"{self.base_url}{path}"
        return self.session.put(url, json=json_data, timeout=self.timeout)

    def delete(self, path: str, params: dict = None) -> requests.Response:
        """发送 DELETE 请求"""
        url = f"{self.base_url}{path}"
        return self.session.delete(url, params=params, timeout=self.timeout)

    def close(self):
        """关闭会话"""
        self.session.close()
