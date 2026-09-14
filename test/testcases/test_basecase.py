"""
基础接口测试用例
覆盖 GET /api/health、GET /api/info、GET /api/db-test 等基础接口
"""
import pytest
from datetime import datetime, timezone


@pytest.mark.smoke
@pytest.mark.health
class TestHealthEndpoint:
    """GET /api/health 接口测试"""

    def test_health_check_success(self, api_client):
        """测试健康检查接口返回成功状态"""
        response = api_client.get("/health")
        assert response.status_code == 200

    def test_health_response_structure(self, api_client):
        """验证健康检查响应包含所有必需字段"""
        response = api_client.get("/health")
        data = response.json()

        assert "success" in data, "响应缺少 success 字段"
        assert "message" in data, "响应缺少 message 字段"
        assert "timestamp" in data, "响应缺少 timestamp 字段"
        assert "services" in data, "响应缺少 services 字段"

    def test_health_success_field(self, api_client):
        """验证 success 字段为 true"""
        response = api_client.get("/health")
        data = response.json()
        assert data["success"] is True

    def test_health_message_field(self, api_client):
        """验证 message 字段内容"""
        response = api_client.get("/health")
        data = response.json()
        assert data["message"] == "API is healthy"

    def test_health_services_structure(self, api_client):
        """验证 services 字段包含 database 和 api 子字段"""
        response = api_client.get("/health")
        data = response.json()
        services = data["services"]

        assert "database" in services, "services 缺少 database 字段"
        assert "api" in services, "services 缺少 api 字段"

    def test_health_database_connected(self, api_client):
        """验证数据库状态为 connected"""
        response = api_client.get("/health")
        data = response.json()
        assert data["services"]["database"] == "connected"

    def test_health_api_operational(self, api_client):
        """验证 API 状态为 operational"""
        response = api_client.get("/health")
        data = response.json()
        assert data["services"]["api"] == "operational"

    def test_health_timestamp_format(self, api_client):
        """验证 timestamp 字段为有效的 ISO 8601 格式"""
        response = api_client.get("/health")
        data = response.json()
        timestamp = data["timestamp"]

        # 验证可以解析 ISO 8601 格式
        try:
            parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            assert parsed.tzinfo is not None, "timestamp 应包含时区信息"
        except ValueError:
            pytest.fail(f"timestamp 格式无效: {timestamp}")

    def test_health_response_time(self, api_client):
        """验证响应时间在合理范围内（< 2秒）"""
        response = api_client.get("/health")
        assert response.elapsed.total_seconds() < 2, \
            f"响应时间过长: {response.elapsed.total_seconds()}秒"

    def test_health_content_type(self, api_client):
        """验证响应 Content-Type 为 application/json"""
        response = api_client.get("/health")
        assert "application/json" in response.headers.get("Content-Type", "")


@pytest.mark.smoke
class TestInfoEndpoint:
    """GET /api/info 接口测试"""

    def test_info_endpoint_success(self, api_client):
        """测试 API 信息接口返回成功"""
        response = api_client.get("/info")
        assert response.status_code == 200

    def test_info_response_structure(self, api_client):
        """验证 API 信息响应结构"""
        response = api_client.get("/info")
        data = response.json()

        assert "name" in data, "响应缺少 name 字段"
        assert "version" in data, "响应缺少 version 字段"
        assert "description" in data, "响应缺少 description 字段"
        assert "endpoints" in data, "响应缺少 endpoints 字段"

    def test_info_name_field(self, api_client):
        """验证 API 名称"""
        response = api_client.get("/info")
        data = response.json()
        assert data["name"] == "Smart Farming IoT Backend API"

    def test_info_version_field(self, api_client):
        """验证版本号格式"""
        response = api_client.get("/info")
        data = response.json()
        version = data["version"]
        # 验证语义化版本格式 (x.y.z)
        parts = version.split(".")
        assert len(parts) == 3, f"版本号格式不正确: {version}"
        for part in parts:
            assert part.isdigit(), f"版本号应为数字: {version}"


@pytest.mark.smoke
class TestDbTestEndpoint:
    """GET /api/db-test 接口测试"""

    def test_db_test_success(self, api_client):
        """测试数据库连接测试接口返回成功"""
        response = api_client.get("/db-test")
        assert response.status_code == 200

    def test_db_test_response_structure(self, api_client):
        """验证数据库测试响应结构"""
        response = api_client.get("/db-test")
        data = response.json()

        assert "success" in data, "响应缺少 success 字段"
        assert "message" in data, "响应缺少 message 字段"
        assert "timestamp" in data, "响应缺少 timestamp 字段"

    def test_db_test_success_field(self, api_client):
        """验证数据库连接成功"""
        response = api_client.get("/db-test")
        data = response.json()
        assert data["success"] is True
        assert data["message"] == "Database connection successful"
