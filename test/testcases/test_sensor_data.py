"""
传感器数据接口测试用例
覆盖 POST/GET/DELETE /api/sensor-data 系列接口

数据真实性验证策略（Round-trip Verification）：
    POST 已知数据 → GET 取回 → 逐字段比对
    确保 API 管道完整可靠：接收 → 存储 → 返回 无损。
"""
import pytest
from datetime import datetime, timezone


# ============================================================
#  固定的测试数据（用于 POST 正向测试和 Round-trip 验证）
# ============================================================
VALID_RECORD_A = {
    "temperature": 28.5,
    "humidity": 55.0,
    "soilMoisture": 40,
    "soilTemperature": 24.0,
    "rainDetected": False,
    "waterLevel": "Medium",
}

VALID_RECORD_B = {
    "temperature": 18.0,
    "humidity": 92.0,
    "soilMoisture": 85,
    "soilTemperature": 17.5,
    "rainDetected": True,
    "waterLevel": "High",
}

VALID_RECORD_NO_OPTIONAL = {
    "temperature": -5.0,
    "humidity": 15.0,
    "soilMoisture": 10,
    "rainDetected": False,
    "waterLevel": "Low",
}


# ============================================================
#  Helper
# ============================================================
def _assert_sensor_record_fields(record: dict, source: dict = None):
    """
    断言传感器数据记录包含所有必需字段。
    如果提供了 source（原始输入），则执行 Round-trip 比对。
    """
    required_fields = [
        "id", "temperature", "humidity", "soilMoisture",
        "rainDetected", "waterLevel", "createdAt",
    ]
    for field in required_fields:
        assert field in record, f"响应缺少必需字段: {field}"

    # id 应为字符串（BigInt 序列化）
    assert isinstance(record["id"], str), \
        f"id 应为字符串类型，实际为 {type(record['id']).__name__}"

    # createdAt 应为 ISO 8601 格式
    if record.get("createdAt"):
        ts = record["createdAt"]
        try:
            datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            pytest.fail(f"createdAt 格式无效: {ts}")

    # Round-trip 验证：逐字段比对（数值字段统一转 float 兼容 Decimal 序列化）
    if source:
        assert float(record["temperature"]) == float(source["temperature"]), \
            f"temperature 不一致: 发送 {source['temperature']}, 返回 {record['temperature']}"
        assert float(record["humidity"]) == float(source["humidity"]), \
            f"humidity 不一致: 发送 {source['humidity']}, 返回 {record['humidity']}"
        assert float(record["soilMoisture"]) == float(source["soilMoisture"]), \
            f"soilMoisture 不一致: 发送 {source['soilMoisture']}, 返回 {record['soilMoisture']}"
        assert record["rainDetected"] == source["rainDetected"], \
            f"rainDetected 不一致: 发送 {source['rainDetected']}, 返回 {record['rainDetected']}"
        assert record["waterLevel"] == source["waterLevel"], \
            f"waterLevel 不一致: 发送 {source['waterLevel']}, 返回 {record['waterLevel']}"

        # 可选字段 soilTemperature
        if "soilTemperature" in source and source["soilTemperature"] is not None:
            assert record.get("soilTemperature") is not None, \
                "发送了 soilTemperature 但返回为 null"
            assert float(record["soilTemperature"]) == float(source["soilTemperature"]), \
                f"soilTemperature 不一致: 发送 {source['soilTemperature']}, 返回 {record['soilTemperature']}"


def _assert_error_response(response, expected_status):
    """断言错误响应格式"""
    assert response.status_code == expected_status, \
        f"预期状态码 {expected_status}，实际 {response.status_code}"
    data = response.json()
    assert "error" in data, "错误响应缺少 error 字段"


# ============================================================
#  POST /api/sensor-data 测试
# ============================================================
@pytest.mark.sensor
class TestCreateSensorData:
    """POST /api/sensor-data 接口测试"""

    def test_create_sensor_data_success(self, api_client):
        """正向：完整数据创建成功，返回 201"""
        resp = api_client.post("/sensor-data", json_data=VALID_RECORD_A)
        assert resp.status_code == 201, f"预期 201，实际 {resp.status_code}"

    def test_create_sensor_data_response_fields(self, api_client):
        """正向：响应包含所有字段，且 Round-trip 比对通过"""
        resp = api_client.post("/sensor-data", json_data=VALID_RECORD_A)
        assert resp.status_code == 201
        data = resp.json()
        assert "data" in data, "响应缺少 data 字段"
        assert "message" in data, "响应缺少 message 字段"
        _assert_sensor_record_fields(data["data"], VALID_RECORD_A)

    def test_create_sensor_data_id_is_string(self, api_client):
        """正向：BigInt id 序列化为字符串"""
        resp = api_client.post("/sensor-data", json_data=VALID_RECORD_A)
        assert resp.status_code == 201
        record_id = resp.json()["data"]["id"]
        assert isinstance(record_id, str), \
            f"id 应为字符串，实际为 {type(record_id).__name__}"
        assert record_id.isdigit(), f"id 应为纯数字字符串，实际为 {record_id}"

    def test_create_sensor_data_without_optional_field(self, api_client):
        """正向：不传 soilTemperature 也能创建成功"""
        resp = api_client.post("/sensor-data", json_data=VALID_RECORD_NO_OPTIONAL)
        assert resp.status_code == 201
        data = resp.json()["data"]
        # soilTemperature 可以为 null
        assert data.get("soilTemperature") is None, \
            "未传 soilTemperature 时应为 null"

    def test_create_sensor_data_auto_created_at(self, api_client):
        """正向：createdAt 自动填充，格式为 ISO 8601"""
        resp = api_client.post("/sensor-data", json_data=VALID_RECORD_A)
        assert resp.status_code == 201
        created_at = resp.json()["data"]["createdAt"]
        assert created_at is not None, "createdAt 不应为 null"
        try:
            parsed = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            assert parsed is not None
        except (ValueError, AttributeError):
            pytest.fail(f"createdAt 格式无效: {created_at}")

    def test_create_sensor_data_message_field(self, api_client):
        """正向：成功消息内容正确"""
        resp = api_client.post("/sensor-data", json_data=VALID_RECORD_A)
        assert resp.status_code == 201
        assert resp.json()["message"] == "Sensor data created successfully"

    def test_create_sensor_data_roundtrip_record_b(self, api_client):
        """正向：雨天数据 Round-trip 验证"""
        resp = api_client.post("/sensor-data", json_data=VALID_RECORD_B)
        assert resp.status_code == 201
        _assert_sensor_record_fields(resp.json()["data"], VALID_RECORD_B)

    # --- 边界值测试 ---

    def test_create_sensor_data_boundary_temperature_min(self, api_client):
        """边界：temperature = -50（Zod 最小值）"""
        data = {**VALID_RECORD_A, "temperature": -50}
        resp = api_client.post("/sensor-data", json_data=data)
        assert resp.status_code == 201

    def test_create_sensor_data_boundary_temperature_max(self, api_client):
        """边界：temperature = 100（Zod 最大值）"""
        data = {**VALID_RECORD_A, "temperature": 100}
        resp = api_client.post("/sensor-data", json_data=data)
        assert resp.status_code == 201

    def test_create_sensor_data_boundary_humidity_min(self, api_client):
        """边界：humidity = 0（最小值）"""
        data = {**VALID_RECORD_A, "humidity": 0}
        resp = api_client.post("/sensor-data", json_data=data)
        assert resp.status_code == 201

    def test_create_sensor_data_boundary_humidity_max(self, api_client):
        """边界：humidity = 100（最大值）"""
        data = {**VALID_RECORD_A, "humidity": 100}
        resp = api_client.post("/sensor-data", json_data=data)
        assert resp.status_code == 201

    def test_create_sensor_data_boundary_soil_moisture_min(self, api_client):
        """边界：soilMoisture = 0"""
        data = {**VALID_RECORD_A, "soilMoisture": 0}
        resp = api_client.post("/sensor-data", json_data=data)
        assert resp.status_code == 201

    def test_create_sensor_data_boundary_soil_moisture_max(self, api_client):
        """边界：soilMoisture = 100"""
        data = {**VALID_RECORD_A, "soilMoisture": 100}
        resp = api_client.post("/sensor-data", json_data=data)
        assert resp.status_code == 201

    # --- 异常测试 ---

    def test_create_sensor_data_invalid_temperature_over(self, api_client):
        """异常：temperature = 200（超出范围）→ 400"""
        data = {**VALID_RECORD_A, "temperature": 200}
        resp = api_client.post("/sensor-data", json_data=data)
        _assert_error_response(resp, 400)

    def test_create_sensor_data_invalid_temperature_under(self, api_client):
        """异常：temperature = -100（超出范围）→ 400"""
        data = {**VALID_RECORD_A, "temperature": -100}
        resp = api_client.post("/sensor-data", json_data=data)
        _assert_error_response(resp, 400)

    def test_create_sensor_data_invalid_humidity_negative(self, api_client):
        """异常：humidity = -10（负数）→ 400"""
        data = {**VALID_RECORD_A, "humidity": -10}
        resp = api_client.post("/sensor-data", json_data=data)
        _assert_error_response(resp, 400)

    def test_create_sensor_data_invalid_humidity_over(self, api_client):
        """异常：humidity = 150（超过 100）→ 400"""
        data = {**VALID_RECORD_A, "humidity": 150}
        resp = api_client.post("/sensor-data", json_data=data)
        _assert_error_response(resp, 400)

    def test_create_sensor_data_missing_required_field(self, api_client):
        """异常：缺少必填字段 temperature → 400"""
        data = {**VALID_RECORD_A}
        del data["temperature"]
        resp = api_client.post("/sensor-data", json_data=data)
        _assert_error_response(resp, 400)

    def test_create_sensor_data_missing_rain_detected(self, api_client):
        """异常：缺少必填字段 rainDetected → 400"""
        data = {**VALID_RECORD_A}
        del data["rainDetected"]
        resp = api_client.post("/sensor-data", json_data=data)
        _assert_error_response(resp, 400)

    def test_create_sensor_data_invalid_type_temperature(self, api_client):
        """异常：temperature = "abc"（类型错误）→ 400"""
        data = {**VALID_RECORD_A, "temperature": "abc"}
        resp = api_client.post("/sensor-data", json_data=data)
        _assert_error_response(resp, 400)

    def test_create_sensor_data_invalid_type_soil_moisture(self, api_client):
        """异常：soilMoisture = 45.5（应为整数）→ 400"""
        data = {**VALID_RECORD_A, "soilMoisture": 45.5}
        resp = api_client.post("/sensor-data", json_data=data)
        _assert_error_response(resp, 400)

    def test_create_sensor_data_empty_body(self, api_client):
        """异常：空请求体 → 400"""
        resp = api_client.post("/sensor-data", json_data={})
        _assert_error_response(resp, 400)

    def test_create_sensor_data_validation_warning_rain_low_moisture(self, api_client):
        """业务：下雨但土壤湿度低 → 创建成功但有 validation warning"""
        data = {**VALID_RECORD_A, "rainDetected": True, "soilMoisture": 20}
        resp = api_client.post("/sensor-data", json_data=data)
        assert resp.status_code == 201
        result = resp.json()["data"]
        warnings = result.get("validation", {}).get("warnings", [])
        assert len(warnings) > 0, "下雨但土壤湿度低应触发 warning"


# ============================================================
#  GET /api/sensor-data 测试（分页查询）
# ============================================================
@pytest.mark.sensor
class TestGetSensorData:
    """GET /api/sensor-data 接口测试（需要先有数据，依赖 sensor_test_data fixture）"""

    def test_get_sensor_data_success(self, api_client, sensor_test_data):
        """正向：返回 200 和分页数据"""
        resp = api_client.get("/sensor-data")
        assert resp.status_code == 200
        body = resp.json()
        inner = body["data"]
        assert "data" in inner
        assert "message" in inner
        assert "meta" in inner
        assert isinstance(inner["data"], list)

    def test_get_sensor_data_pagination_meta(self, api_client, sensor_test_data):
        """正向：meta 包含所有分页字段"""
        resp = api_client.get("/sensor-data")
        assert resp.status_code == 200
        meta = resp.json()["data"]["meta"]
        for field in ["total", "limit", "offset", "hasNext", "hasPrev"]:
            assert field in meta, f"meta 缺少 {field} 字段"
        assert isinstance(meta["total"], int)
        assert isinstance(meta["hasNext"], bool)
        assert isinstance(meta["hasPrev"], bool)

    def test_get_sensor_data_default_pagination(self, api_client, sensor_test_data):
        """正向：默认 limit=10, offset=0"""
        resp = api_client.get("/sensor-data")
        assert resp.status_code == 200
        meta = resp.json()["data"]["meta"]
        assert meta["limit"] == 10
        assert meta["offset"] == 0

    def test_get_sensor_data_custom_pagination(self, api_client, sensor_test_data):
        """正向：自定义 limit=2, offset=0"""
        resp = api_client.get("/sensor-data", params={"limit": 2, "offset": 0})
        assert resp.status_code == 200
        inner = resp.json()["data"]
        assert len(inner["data"]) <= 2
        assert inner["meta"]["limit"] == 2

    def test_get_sensor_data_order_desc(self, api_client, sensor_test_data):
        """正向：数据按 createdAt 降序排列"""
        resp = api_client.get("/sensor-data", params={"limit": 100})
        assert resp.status_code == 200
        records = resp.json()["data"]["data"]
        if len(records) >= 2:
            for i in range(len(records) - 1):
                cur = records[i].get("createdAt", "")
                nxt = records[i + 1].get("createdAt", "")
                if cur and nxt:
                    assert cur >= nxt, "数据未按 createdAt 降序排列"

    def test_get_sensor_data_records_have_fields(self, api_client, sensor_test_data):
        """正向：返回的每条记录包含所有必需字段"""
        resp = api_client.get("/sensor-data")
        assert resp.status_code == 200
        for record in resp.json()["data"]["data"]:
            _assert_sensor_record_fields(record)

    def test_get_sensor_data_invalid_limit_zero(self, api_client):
        """异常：limit=0 → 400"""
        resp = api_client.get("/sensor-data", params={"limit": 0})
        _assert_error_response(resp, 400)

    def test_get_sensor_data_invalid_limit_over(self, api_client):
        """异常：limit=200（超过 100）→ 400"""
        resp = api_client.get("/sensor-data", params={"limit": 200})
        _assert_error_response(resp, 400)

    def test_get_sensor_data_invalid_offset_negative(self, api_client):
        """异常：offset=-1 → 400"""
        resp = api_client.get("/sensor-data", params={"offset": -1})
        _assert_error_response(resp, 400)


# ============================================================
#  GET /api/sensor-data/latest 测试
# ============================================================
@pytest.mark.sensor
class TestGetLatestSensorData:
    """GET /api/sensor-data/latest 接口测试"""

    def test_get_latest_sensor_data_success(self, api_client, sensor_test_data):
        """正向：返回最新一条数据"""
        resp = api_client.get("/sensor-data/latest")
        assert resp.status_code == 200
        data = resp.json()
        assert "data" in data
        assert "message" in data

    def test_get_latest_sensor_data_fields(self, api_client, sensor_test_data):
        """正向：返回数据包含所有必需字段"""
        resp = api_client.get("/sensor-data/latest")
        assert resp.status_code == 200
        record = resp.json()["data"]
        if record is not None:
            _assert_sensor_record_fields(record)

    def test_get_latest_is_most_recent(self, api_client, sensor_test_data):
        """正向：返回的数据 createdAt 不早于列表中任何一条"""
        # 获取最新
        latest_resp = api_client.get("/sensor-data/latest")
        assert latest_resp.status_code == 200
        latest = latest_resp.json()["data"]

        # 获取列表
        list_resp = api_client.get("/sensor-data", params={"limit": 100})
        assert list_resp.status_code == 200
        records = list_resp.json()["data"]["data"]

        if latest and records:
            latest_time = latest["createdAt"]
            for r in records:
                assert latest_time >= r["createdAt"], \
                    "latest 数据的 createdAt 应 >= 列表中所有记录"

    def test_get_latest_sensor_data_message(self, api_client, sensor_test_data):
        """正向：成功消息内容正确（命中 TTL 缓存时后端会附加 "(from cache)"）"""
        resp = api_client.get("/sensor-data/latest")
        assert resp.status_code == 200
        assert "Latest sensor data retrieved successfully" in resp.json()["message"]


# ============================================================
#  GET /api/sensor-data/stats 测试
# ============================================================
@pytest.mark.sensor
class TestGetSensorDataStats:
    """GET /api/sensor-data/stats 接口测试"""

    def test_get_stats_success(self, api_client, sensor_test_data):
        """正向：返回统计数据"""
        resp = api_client.get("/sensor-data/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert "data" in data

    def test_get_stats_structure(self, api_client, sensor_test_data):
        """正向：统计结构包含 average/minimum/maximum/totalReadings/rainDetectionCount"""
        resp = api_client.get("/sensor-data/stats")
        assert resp.status_code == 200
        stats = resp.json()["data"]

        assert "average" in stats, "缺少 average 字段"
        assert "minimum" in stats, "缺少 minimum 字段"
        assert "maximum" in stats, "缺少 maximum 字段"
        assert "totalReadings" in stats, "缺少 totalReadings 字段"
        assert "rainDetectionCount" in stats, "缺少 rainDetectionCount 字段"
        assert "periodHours" in stats, "缺少 periodHours 字段"

        # average/minimum/max 应包含传感器字段
        for group_name in ["average", "minimum", "maximum"]:
            group = stats[group_name]
            for field in ["temperature", "humidity", "soilMoisture"]:
                assert field in group, f"{group_name} 缺少 {field}"

    def test_get_stats_default_hours(self, api_client, sensor_test_data):
        """正向：默认 periodHours=24"""
        resp = api_client.get("/sensor-data/stats")
        assert resp.status_code == 200
        assert resp.json()["data"]["periodHours"] == 24

    def test_get_stats_custom_hours(self, api_client, sensor_test_data):
        """正向：自定义 hours=48"""
        resp = api_client.get("/sensor-data/stats", params={"hours": 48})
        assert resp.status_code == 200
        assert resp.json()["data"]["periodHours"] == 48

    def test_get_stats_avg_in_range(self, api_client, sensor_test_data):
        """正向：average 值在 min 和 max 之间"""
        resp = api_client.get("/sensor-data/stats")
        assert resp.status_code == 200
        stats = resp.json()["data"]

        if stats["totalReadings"] > 0:
            for field in ["temperature", "humidity", "soilMoisture"]:
                avg = float(stats["average"][field])
                mn = float(stats["minimum"][field])
                mx = float(stats["maximum"][field])
                if avg is not None and mn is not None and mx is not None:
                    assert mn <= avg <= mx, \
                        f"{field}: avg({avg}) 不在 min({mn}) 和 max({mx}) 之间"

    def test_get_stats_total_readings_positive(self, api_client, sensor_test_data):
        """正向：totalReadings 为正整数"""
        resp = api_client.get("/sensor-data/stats")
        assert resp.status_code == 200
        total = resp.json()["data"]["totalReadings"]
        assert isinstance(total, int)
        assert total > 0, "totalReadings 应大于 0"

    def test_get_stats_rain_count_non_negative(self, api_client, sensor_test_data):
        """正向：rainDetectionCount 为非负整数"""
        resp = api_client.get("/sensor-data/stats")
        assert resp.status_code == 200
        rain = resp.json()["data"]["rainDetectionCount"]
        assert isinstance(rain, int)
        assert rain >= 0, "rainDetectionCount 不应为负数"

    def test_get_stats_invalid_hours_zero(self, api_client):
        """异常：hours=0 → 400"""
        resp = api_client.get("/sensor-data/stats", params={"hours": 0})
        _assert_error_response(resp, 400)

    def test_get_stats_invalid_hours_negative(self, api_client):
        """异常：hours=-5 → 400"""
        resp = api_client.get("/sensor-data/stats", params={"hours": -5})
        _assert_error_response(resp, 400)

    def test_get_stats_invalid_hours_exceed(self, api_client):
        """异常：hours=200（超过 168）→ 400"""
        resp = api_client.get("/sensor-data/stats", params={"hours": 200})
        _assert_error_response(resp, 400)


# ============================================================
#  GET /api/sensor-data/health 测试
# ============================================================
@pytest.mark.sensor
class TestSensorDataHealth:
    """GET /api/sensor-data/health 接口测试"""

    def test_sensor_health_success(self, api_client, sensor_test_data):
        """正向：返回健康状态"""
        resp = api_client.get("/sensor-data/health")
        assert resp.status_code == 200

    def test_sensor_health_has_data(self, api_client, sensor_test_data):
        """正向：有数据时 status 为 healthy"""
        resp = api_client.get("/sensor-data/health")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["status"] == "healthy"
        assert data["hasData"] is True

    def test_sensor_health_structure(self, api_client, sensor_test_data):
        """正向：响应包含 status/hasData/lastDataAgeMinutes/message"""
        resp = api_client.get("/sensor-data/health")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "status" in data, "缺少 status 字段"
        assert "hasData" in data, "缺少 hasData 字段"
        assert "lastDataAgeMinutes" in data, "缺少 lastDataAgeMinutes 字段"
        assert "message" in data, "缺少 message 字段"

    def test_sensor_health_last_data_age(self, api_client, sensor_test_data):
        """正向：lastDataAgeMinutes 为非负整数"""
        resp = api_client.get("/sensor-data/health")
        assert resp.status_code == 200
        age = resp.json()["data"]["lastDataAgeMinutes"]
        assert isinstance(age, int)
        assert age >= 0, "lastDataAgeMinutes 不应为负数"


# ============================================================
#  GET /api/sensor-data/:id 测试
# ============================================================
@pytest.mark.sensor
class TestGetSensorDataById:
    """GET /api/sensor-data/:id 接口测试"""

    def test_get_sensor_data_by_id_success(self, api_client, sensor_test_data):
        """正向：通过有效 ID 获取数据"""
        ids = sensor_test_data["ids"]
        assert len(ids) > 0, "没有可用的测试数据 ID"
        resp = api_client.get(f"/sensor-data/{ids[0]}")
        assert resp.status_code == 200
        data = resp.json()
        assert "data" in data
        assert data["data"] is not None

    def test_get_sensor_data_by_id_roundtrip(self, api_client, sensor_test_data):
        """正向：Round-trip 验证 —— 返回数据与创建时一致"""
        records = sensor_test_data["records"]
        ids = sensor_test_data["ids"]
        assert len(ids) > 0, "没有可用的测试数据 ID"

        resp = api_client.get(f"/sensor-data/{ids[0]}")
        assert resp.status_code == 200
        returned = resp.json()["data"]
        source = records[0]
        _assert_sensor_record_fields(returned, source)

    def test_get_sensor_data_by_id_fields(self, api_client, sensor_test_data):
        """正向：返回数据包含所有必需字段"""
        ids = sensor_test_data["ids"]
        assert len(ids) > 0
        resp = api_client.get(f"/sensor-data/{ids[0]}")
        assert resp.status_code == 200
        _assert_sensor_record_fields(resp.json()["data"])

    def test_get_sensor_data_by_id_not_found(self, api_client):
        """异常：不存在的 ID → 404"""
        resp = api_client.get("/sensor-data/999999999")
        assert resp.status_code == 404

    def test_get_sensor_data_by_id_invalid_format(self, api_client):
        """异常：ID="abc"（非数字）→ 400"""
        resp = api_client.get("/sensor-data/abc")
        _assert_error_response(resp, 400)

    def test_get_sensor_data_by_id_negative(self, api_client):
        """异常：ID="-1" → 404"""
        resp = api_client.get("/sensor-data/-1")
        # 负数 ID 转为 BigInt 后查询不到
        assert resp.status_code in [400, 404]


# ============================================================
#  DELETE /api/sensor-data/cleanup 测试
# ============================================================
@pytest.mark.sensor
class TestCleanupSensorData:
    """DELETE /api/sensor-data/cleanup 接口测试"""

    def test_cleanup_success(self, api_client):
        """正向：默认清理 30 天前数据"""
        resp = api_client.delete("/sensor-data/cleanup")
        assert resp.status_code == 200

    def test_cleanup_custom_days(self, api_client):
        """正向：自定义 days=7"""
        resp = api_client.delete("/sensor-data/cleanup?days=7")
        assert resp.status_code == 200

    def test_cleanup_response_structure(self, api_client):
        """正向：响应包含 deletedCount 和 daysKept"""
        resp = api_client.delete("/sensor-data/cleanup")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "deletedCount" in data, "缺少 deletedCount 字段"
        assert "daysKept" in data, "缺少 daysKept 字段"
        assert isinstance(data["deletedCount"], int)
        assert isinstance(data["daysKept"], int)

    def test_cleanup_message(self, api_client):
        """正向：消息包含清理结果"""
        resp = api_client.delete("/sensor-data/cleanup")
        assert resp.status_code == 200
        msg = resp.json()["message"]
        assert "Cleanup completed" in msg
        assert "old records deleted" in msg

    def test_cleanup_minimum_days(self, api_client):
        """异常：days=5（小于 7）→ 400"""
        resp = api_client.delete("/sensor-data/cleanup?days=5")
        _assert_error_response(resp, 400)

    def test_cleanup_invalid_days_zero(self, api_client):
        """异常：days=0 → 400"""
        resp = api_client.delete("/sensor-data/cleanup?days=0")
        _assert_error_response(resp, 400)

    def test_cleanup_response_time(self, api_client):
        """性能：响应时间 < 5 秒"""
        resp = api_client.delete("/sensor-data/cleanup")
        assert resp.elapsed.total_seconds() < 5, \
            f"清理响应时间过长: {resp.elapsed.total_seconds()}秒"
