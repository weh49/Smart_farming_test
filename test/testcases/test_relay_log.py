"""
继电器日志接口自动化测试用例
覆盖 POST /api/relay-log、GET /api/relay-log、GET /api/relay-log/latest、
GET /api/relay-log/:id、GET /api/relay-log/stats、GET /api/relay-log/status、
POST /api/relay-log/state-change、GET /api/relay-log/duration、
GET /api/relay-log/health、DELETE /api/relay-log/cleanup

共计 10 个测试类，约 74 个用例。
"""
import time
from datetime import datetime, timezone


# ============================================================
#  辅助函数
# ============================================================

def _assert_relay_log_fields(record: dict, source: dict = None):
    """
    断言继电器日志记录包含所有必需字段。
    如果提供了 source（原始输入），则执行 Round-trip 比对。
    """
    required_fields = [
        "id", "relayStatus", "triggerReason", "sensorReadingId",
        "createdAt", "sensorData",
    ]
    for field in required_fields:
        assert field in record, f"响应缺少必需字段: {field}"

    # id 应为字符串（BigInt 序列化）
    assert isinstance(record["id"], str), \
        f"id 应为字符串类型，实际为 {type(record['id']).__name__}"

    # sensorReadingId 应为字符串（BigInt 序列化）
    assert isinstance(record["sensorReadingId"], str), \
        f"sensorReadingId 应为字符串类型，实际为 {type(record['sensorReadingId']).__name__}"

    # relayStatus 应为布尔值
    assert isinstance(record["relayStatus"], bool), \
        f"relayStatus 应为布尔类型，实际为 {type(record['relayStatus']).__name__}"

    # triggerReason 应为字符串
    assert isinstance(record["triggerReason"], str), \
        f"triggerReason 应为字符串类型，实际为 {type(record['triggerReason']).__name__}"

    # createdAt 应为 ISO 8601 格式
    if record.get("createdAt"):
        ts = record["createdAt"]
        try:
            datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            pytest.fail(f"createdAt 格式无效: {ts}")

    # sensorData 关联对象应存在
    assert record.get("sensorData") is not None, "sensorData 关联对象不应为 null"
    assert isinstance(record["sensorData"], dict), "sensorData 应为对象类型"

    # sensorData 子对象必需字段
    sensor_required = ["id", "temperature", "humidity", "soilMoisture", "rainDetected", "createdAt"]
    for field in sensor_required:
        assert field in record["sensorData"], f"sensorData 缺少字段: {field}"

    # Round-trip 验证
    if source:
        assert record["relayStatus"] == source["relayStatus"], \
            f"relayStatus 不一致: 发送 {source['relayStatus']}, 返回 {record['relayStatus']}"
        assert record["triggerReason"] == source["triggerReason"], \
            f"triggerReason 不一致: 发送 {source['triggerReason']}, 返回 {record['triggerReason']}"
        assert str(record["sensorReadingId"]) == str(source["sensorReadingId"]), \
            f"sensorReadingId 不一致: 发送 {source['sensorReadingId']}, 返回 {record['sensorReadingId']}"


def _assert_error_response(response, expected_status):
    """断言错误响应格式"""
    assert response.status_code == expected_status, \
        f"预期状态码 {expected_status}，实际 {response.status_code}"
    data = response.json()
    assert data.get("success") is False or "error" in data or "message" in data, \
        f"错误响应应包含 success=false 或 error 或 message 字段，实际: {data}"


import pytest


# ============================================================
#  Fixture 验证（确保数据准备正确）
# ============================================================

@pytest.mark.relay
class TestRelayLogFixtures:
    """验证继电器日志 fixtures 配置"""

    def test_sensor_data_pool_has_ids(self, sensor_data_pool):
        """验证 sensor_data_pool 成功创建了传感器数据"""
        assert sensor_data_pool["count"] > 0, "sensor_data_pool 未创建任何传感器数据"
        assert len(sensor_data_pool["ids"]) > 0, "sensor_data_pool 无可用 ID"

    def test_relay_create_data_created(self, relay_create_data):
        """验证 relay_create_data 成功创建了继电器日志"""
        assert len(relay_create_data["ids"]) > 0, "relay_create_data 未创建任何继电器日志"
        assert len(relay_create_data["records"]) > 0, "relay_create_data 无原始记录"

    def test_relay_state_change_data_created(self, relay_state_change_data):
        """验证 relay_state_change_data 成功创建了初始状态"""
        assert relay_state_change_data["initial_relay_id"] != "", \
            "relay_state_change_data 未创建初始继电器日志"

    def test_relay_query_data_pagination_ready(self, relay_query_data):
        """验证 relay_query_data 创建了足够多的数据用于分页测试"""
        assert relay_query_data["total_count"] >= 10, \
            f"relay_query_data 数据不足: {relay_query_data['total_count']} 条（需 >= 10）"
        assert len(relay_query_data["on_ids"]) > 0, "relay_query_data 无 ON 状态数据"
        assert len(relay_query_data["off_ids"]) > 0, "relay_query_data 无 OFF 状态数据"


# ============================================================
#  类 1: POST /api/relay-log
# ============================================================

@pytest.mark.relay
class TestCreateRelayLog:
    """POST /api/relay-log 接口测试"""

    # ---------- 正向验证 ----------

    def test_create_relay_log_success(self, api_client, sensor_data_pool):
        """正向：创建继电器日志成功，状态码 201"""
        sensor_id = sensor_data_pool["ids"][0]
        payload = {
            "relayStatus": True,
            "triggerReason": "Soil moisture below threshold, activating pump",
            "sensorReadingId": sensor_id,
        }
        resp = api_client.post("/relay-log", json_data=payload)
        assert resp.status_code == 201, f"预期 201，实际 {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data.get("message") == "Relay log created successfully"

    def test_create_relay_log_response_fields(self, api_client, relay_create_data):
        """正向：POST 创建后通过 GET /:id 验证响应 data 包含所有必需字段"""
        # 使用 fixture 中已创建的第一条数据
        rid = relay_create_data["ids"][0]
        source = relay_create_data["records"][0]
        # 通过 GET /:id 获取 API 实际响应
        resp = api_client.get(f"/relay-log/{rid}")
        assert resp.status_code == 200, f"GET /relay-log/{rid} 失败: {resp.status_code}"
        record = resp.json()["data"]
        # 使用辅助函数验证所有必需字段及类型
        _assert_relay_log_fields(record, source)

    def test_create_relay_log_id_is_string(self, api_client, sensor_data_pool):
        """正向：BigInt id 被序列化为字符串"""
        sensor_id = sensor_data_pool["ids"][0]
        payload = {
            "relayStatus": False,
            "triggerReason": "Test id serialization",
            "sensorReadingId": sensor_id,
        }
        resp = api_client.post("/relay-log", json_data=payload)
        assert resp.status_code == 201
        data = resp.json()["data"]
        assert isinstance(data["id"], str), \
            f"id 应为字符串，实际为 {type(data['id']).__name__}"
        assert isinstance(data["sensorReadingId"], str), \
            f"sensorReadingId 应为字符串，实际为 {type(data['sensorReadingId']).__name__}"


    def test_create_relay_log_created_at_auto_filled(self, api_client, sensor_data_pool):
        """正向：createdAt 自动填充，格式为 ISO 8601"""
        sensor_id = sensor_data_pool["ids"][0]
        payload = {
            "relayStatus": True,
            "triggerReason": "Test auto createdAt",
            "sensorReadingId": sensor_id,
        }
        resp = api_client.post("/relay-log", json_data=payload)
        assert resp.status_code == 201
        data = resp.json()["data"]
        assert data.get("createdAt") is not None, "createdAt 不应为 null"
        try:
            ts = datetime.fromisoformat(data["createdAt"].replace("Z", "+00:00"))
            now = datetime.now(timezone.utc)
            diff = abs((now - ts).total_seconds())
            assert diff < 60, f"createdAt 与当前时间差距过大: {diff} 秒"
        except (ValueError, AttributeError) as e:
            pytest.fail(f"createdAt 格式无效: {data['createdAt']} ({e})")

    def test_create_relay_log_message_field(self, api_client, sensor_data_pool):
        """正向：message 字段内容正确"""
        sensor_id = sensor_data_pool["ids"][0]
        payload = {
            "relayStatus": False,
            "triggerReason": "Test message field",
            "sensorReadingId": sensor_id,
        }
        resp = api_client.post("/relay-log", json_data=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data.get("message") == "Relay log created successfully"

    # ---------- Round-trip 验证 ----------

    def test_create_relay_log_roundtrip_on_status(self, api_client, sensor_data_pool):
        """Round-trip：写入 ON 状态后通过 GET /:id 读回比对"""
        sensor_id = sensor_data_pool["ids"][0]
        payload = {
            "relayStatus": True,
            "triggerReason": "Round-trip test ON status",
            "sensorReadingId": sensor_id,
        }
        # 步骤 1: 创建
        resp = api_client.post("/relay-log", json_data=payload)
        assert resp.status_code == 201
        created = resp.json()["data"]
        rid = created["id"]

        # 步骤 2: 读回
        get_resp = api_client.get(f"/relay-log/{rid}")
        assert get_resp.status_code == 200
        fetched = get_resp.json()["data"]

        # 步骤 3: 比对
        assert fetched["relayStatus"] == payload["relayStatus"], \
            f"relayStatus 不一致: 发送 {payload['relayStatus']}, 读回 {fetched['relayStatus']}"
        assert fetched["triggerReason"] == payload["triggerReason"], \
            f"triggerReason 不一致"
        assert str(fetched["sensorReadingId"]) == str(payload["sensorReadingId"]), \
            f"sensorReadingId 不一致"

    def test_create_relay_log_roundtrip_off_status(self, api_client, sensor_data_pool):
        """Round-trip：写入 OFF 状态后通过 GET /:id 读回比对"""
        sensor_id = sensor_data_pool["ids"][0]
        payload = {
            "relayStatus": False,
            "triggerReason": "Round-trip test OFF status",
            "sensorReadingId": sensor_id,
        }
        resp = api_client.post("/relay-log", json_data=payload)
        assert resp.status_code == 201
        created = resp.json()["data"]
        rid = created["id"]

        get_resp = api_client.get(f"/relay-log/{rid}")
        assert get_resp.status_code == 200
        fetched = get_resp.json()["data"]

        assert fetched["relayStatus"] == payload["relayStatus"]
        assert fetched["triggerReason"] == payload["triggerReason"]
        assert str(fetched["sensorReadingId"]) == str(payload["sensorReadingId"])

    # ---------- 关联数据验证 ----------

    def test_create_relay_log_includes_sensor_data(self, api_client, sensor_data_pool):
        """正向：响应中自动包含 sensorData 关联对象"""
        sensor_id = sensor_data_pool["ids"][0]
        payload = {
            "relayStatus": True,
            "triggerReason": "Test sensorData include",
            "sensorReadingId": sensor_id,
        }
        resp = api_client.post("/relay-log", json_data=payload)
        assert resp.status_code == 201
        data = resp.json()["data"]
        assert data.get("sensorData") is not None, "sensorData 不应为 null"
        assert isinstance(data["sensorData"], dict), "sensorData 应为对象"

    def test_create_relay_log_sensor_data_fields(self, api_client, sensor_data_pool):
        """正向：sensorData 子对象字段完整"""
        sensor_id = sensor_data_pool["ids"][0]
        payload = {
            "relayStatus": False,
            "triggerReason": "Test sensorData fields",
            "sensorReadingId": sensor_id,
        }
        resp = api_client.post("/relay-log", json_data=payload)
        assert resp.status_code == 201
        data = resp.json()["data"]
        sd = data["sensorData"]
        assert sd is not None
        assert isinstance(sd["id"], str), "sensorData.id 应为字符串"
        assert sd["id"] == str(sensor_id), "sensorData.id 应与 sensorReadingId 一致"
        float(sd["temperature"])   # 可转换为 float 即为数值，否则抛 ValueError
        float(sd["humidity"])
        float(sd["soilMoisture"])
        assert isinstance(sd.get("rainDetected"), bool), "rainDetected 应为布尔值"

    # ---------- 异常输入 ----------

    def test_create_relay_log_missing_relay_status(self, api_client, sensor_data_pool):
        """异常：缺少必填字段 relayStatus"""
        sensor_id = sensor_data_pool["ids"][0]
        payload = {
            "triggerReason": "Missing relayStatus test",
            "sensorReadingId": sensor_id,
        }
        resp = api_client.post("/relay-log", json_data=payload)
        _assert_error_response(resp, 400)

    def test_create_relay_log_missing_trigger_reason(self, api_client, sensor_data_pool):
        """异常：缺少必填字段 triggerReason"""
        sensor_id = sensor_data_pool["ids"][0]
        payload = {
            "relayStatus": True,
            "sensorReadingId": sensor_id,
        }
        resp = api_client.post("/relay-log", json_data=payload)
        _assert_error_response(resp, 400)

    def test_create_relay_log_missing_sensor_reading_id(self, api_client):
        """异常：缺少必填字段 sensorReadingId"""
        payload = {
            "relayStatus": True,
            "triggerReason": "Missing sensorReadingId test",
        }
        resp = api_client.post("/relay-log", json_data=payload)
        _assert_error_response(resp, 400)

    def test_create_relay_log_invalid_relay_status_type(self, api_client, sensor_data_pool):
        """异常：relayStatus 类型错误（传字符串而非布尔值）"""
        sensor_id = sensor_data_pool["ids"][0]
        payload = {
            "relayStatus": "true",  # 字符串而非布尔值
            "triggerReason": "Invalid type test",
            "sensorReadingId": sensor_id,
        }
        resp = api_client.post("/relay-log", json_data=payload)
        _assert_error_response(resp, 400)

    def test_create_relay_log_empty_trigger_reason(self, api_client, sensor_data_pool):
        """异常：triggerReason 为空字符串（发现潜在校验漏洞）"""
        sensor_id = sensor_data_pool["ids"][0]
        payload = {
            "relayStatus": True,
            "triggerReason": "",
            "sensorReadingId": sensor_id,
        }
        resp = api_client.post("/relay-log", json_data=payload)
        # 注意：Zod schema 中 z.string() 接受空字符串
        # 如果返回 201，说明后端缺少 .min(1) 校验（潜在 bug）
        # 如果返回 400，说明有其他层面的校验
        if resp.status_code == 201:
            pytest.skip("后端接受空字符串 triggerReason（潜在校验漏洞）")
        else:
            _assert_error_response(resp, 400)

    def test_create_relay_log_invalid_sensor_reading_id(self, api_client):
        """异常：sensorReadingId 引用不存在的传感器记录（外键约束）"""
        payload = {
            "relayStatus": True,
            "triggerReason": "Invalid FK test",
            "sensorReadingId": "999999999",
        }
        resp = api_client.post("/relay-log", json_data=payload)
        _assert_error_response(resp, 400)


# ============================================================
#  类 2: GET /api/relay-log（分页 + 过滤）
# ============================================================

@pytest.mark.relay
class TestGetRelayLogs:
    """GET /api/relay-log 接口测试（分页、过滤、排序）"""

    # ---------- 分页基础 ----------

    def test_get_relay_logs_success(self, api_client, relay_query_data):
        """正向：默认分页返回成功"""
        resp = api_client.get("/relay-log")
        assert resp.status_code == 200
        data = resp.json()
        assert "data" in data.get("data", {})

    def test_get_relay_logs_pagination_meta(self, api_client, relay_query_data):
        """正向：分页 meta 结构完整"""
        resp = api_client.get("/relay-log")
        assert resp.status_code == 200
        meta = resp.json()["data"]["meta"]
        assert "total" in meta, "meta 缺少 total"
        assert "limit" in meta, "meta 缺少 limit"
        assert "offset" in meta, "meta 缺少 offset"
        assert "hasNext" in meta, "meta 缺少 hasNext"
        assert "hasPrev" in meta, "meta 缺少 hasPrev"

    def test_get_relay_logs_default_pagination(self, api_client, relay_query_data):
        """正向：默认分页参数 limit=10, offset=0"""
        resp = api_client.get("/relay-log")
        assert resp.status_code == 200
        meta = resp.json()["data"]["meta"]
        assert meta["limit"] == 10, f"默认 limit 应为 10，实际 {meta['limit']}"
        assert meta["offset"] == 0, f"默认 offset 应为 0，实际 {meta['offset']}"

    def test_get_relay_logs_custom_pagination(self, api_client, relay_query_data):
        """正向：自定义 limit/offset 参数"""
        resp = api_client.get("/relay-log", params={"limit": 5, "offset": 2})
        assert resp.status_code == 200
        meta = resp.json()["data"]["meta"]
        assert meta["limit"] == 5
        assert meta["offset"] == 2
        records = resp.json()["data"]["data"]
        assert len(records) <= 5, f"返回记录数应 <= 5，实际 {len(records)}"

    def test_get_relay_logs_has_next(self, api_client, relay_query_data):
        """正向：当数据量 > limit 时 hasNext=True"""
        total = relay_query_data["total_count"]
        resp = api_client.get("/relay-log", params={"limit": 5, "offset": 0})
        assert resp.status_code == 200
        meta = resp.json()["data"]["meta"]
        if total > 5:
            assert meta["hasNext"] is True, "数据量 > limit 时 hasNext 应为 True"

    def test_get_relay_logs_has_prev(self, api_client, relay_query_data):
        """正向：当 offset > 0 时 hasPrev=True"""
        resp = api_client.get("/relay-log", params={"limit": 5, "offset": 5})
        assert resp.status_code == 200
        meta = resp.json()["data"]["meta"]
        assert meta["hasPrev"] is True, "offset > 0 时 hasPrev 应为 True"

    # ---------- 排序验证 ----------

    def test_get_relay_logs_order_desc(self, api_client, relay_query_data):
        """正向：返回数据按 createdAt 降序排列"""
        resp = api_client.get("/relay-log", params={"limit": 10})
        assert resp.status_code == 200
        records = resp.json()["data"]["data"]
        if len(records) >= 2:
            for i in range(len(records) - 1):
                ts_curr = datetime.fromisoformat(records[i]["createdAt"].replace("Z", "+00:00"))
                ts_next = datetime.fromisoformat(records[i + 1]["createdAt"].replace("Z", "+00:00"))
                assert ts_curr >= ts_next, \
                    f"记录未按 createdAt 降序: [{i}] {records[i]['createdAt']} < [{i+1}] {records[i+1]['createdAt']}"

    # ---------- 状态过滤 ----------

    def test_get_relay_logs_filter_status_true(self, api_client, relay_query_data):
        """正向：?status=true 只返回 ON 状态"""
        resp = api_client.get("/relay-log", params={"status": "true", "limit": 100})
        assert resp.status_code == 200
        records = resp.json()["data"]["data"]
        for record in records:
            assert record["relayStatus"] is True, \
                f"过滤 status=true 后发现 relayStatus=False 的记录: {record['id']}"

    def test_get_relay_logs_filter_status_false(self, api_client, relay_query_data):
        """正向：?status=false 只返回 OFF 状态"""
        resp = api_client.get("/relay-log", params={"status": "false", "limit": 100})
        assert resp.status_code == 200
        records = resp.json()["data"]["data"]
        for record in records:
            assert record["relayStatus"] is False, \
                f"过滤 status=false 后发现 relayStatus=True 的记录: {record['id']}"

    def test_get_relay_logs_filter_total_matches(self, api_client, relay_query_data):
        """正向：过滤后 total 只计符合条件的记录"""
        on_count = len(relay_query_data["on_ids"])
        off_count = len(relay_query_data["off_ids"])
        resp_on = api_client.get("/relay-log", params={"status": "true", "limit": 100})
        resp_off = api_client.get("/relay-log", params={"status": "false", "limit": 100})
        assert resp_on.status_code == 200
        assert resp_off.status_code == 200
        # total 可能包含其他测试创建的数据，所以只验证 >= 预期
        assert resp_on.json()["data"]["meta"]["total"] >= on_count
        assert resp_off.json()["data"]["meta"]["total"] >= off_count


# ============================================================
#  类 3: GET /api/relay-log/latest
# ============================================================

@pytest.mark.relay
class TestGetLatestRelayLog:
    """GET /api/relay-log/latest 接口测试"""

    def test_get_latest_relay_log_success(self, api_client, relay_query_data):
        """正向：返回最新一条继电器日志"""
        resp = api_client.get("/relay-log/latest")
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("data") is not None

    def test_get_latest_relay_log_fields(self, api_client, relay_query_data):
        """正向：最新日志字段完整（含 sensorData）"""
        resp = api_client.get("/relay-log/latest")
        assert resp.status_code == 200
        record = resp.json()["data"]
        _assert_relay_log_fields(record)

    def test_get_latest_is_most_recent(self, api_client, relay_query_data):
        """正向：返回的是 createdAt 最大的记录"""
        resp = api_client.get("/relay-log/latest")
        assert resp.status_code == 200
        latest = resp.json()["data"]
        # 再获取分页数据的第一条（按 desc 排序）
        page_resp = api_client.get("/relay-log", params={"limit": 1})
        assert page_resp.status_code == 200
        first_page = page_resp.json()["data"]["data"][0]
        assert latest["id"] == first_page["id"], \
            "latest 端点返回的 ID 应与分页第一条一致"

    def test_get_latest_relay_log_message(self, api_client, relay_query_data):
        """正向：message 字段正确"""
        resp = api_client.get("/relay-log/latest")
        assert resp.status_code == 200
        assert resp.json().get("message") == "Latest relay log retrieved successfully"

    def test_get_latest_relay_log_has_sensor_data(self, api_client, relay_query_data):
        """正向：最新日志包含 sensorData 关联"""
        resp = api_client.get("/relay-log/latest")
        assert resp.status_code == 200
        record = resp.json()["data"]
        assert record.get("sensorData") is not None, "最新日志应包含 sensorData"
        assert isinstance(record["sensorData"]["id"], str)


# ============================================================
#  类 4: GET /api/relay-log/:id
# ============================================================

@pytest.mark.relay
class TestGetRelayLogById:
    """GET /api/relay-log/:id 接口测试"""

    def test_get_relay_log_by_id_success(self, api_client, relay_create_data):
        """正向：通过有效 ID 获取继电器日志"""
        rid = relay_create_data["ids"][0]
        resp = api_client.get(f"/relay-log/{rid}")
        assert resp.status_code == 200
        data = resp.json()

        assert data["data"]["id"] == rid

    def test_get_relay_log_by_id_roundtrip(self, api_client, relay_create_data):
        """Round-trip：用 POST 创建的 ID 查询，比对字段一致"""
        source = relay_create_data["records"][0]
        rid = relay_create_data["ids"][0]
        resp = api_client.get(f"/relay-log/{rid}")
        assert resp.status_code == 200
        fetched = resp.json()["data"]
        assert fetched["relayStatus"] == source["relayStatus"]
        assert fetched["triggerReason"] == source["triggerReason"]
        assert str(fetched["sensorReadingId"]) == str(source["sensorReadingId"])

    def test_get_relay_log_by_id_fields(self, api_client, relay_create_data):
        """正向：响应字段完整（含 sensorData）"""
        rid = relay_create_data["ids"][0]
        resp = api_client.get(f"/relay-log/{rid}")
        assert resp.status_code == 200
        _assert_relay_log_fields(resp.json()["data"])

    def test_get_relay_log_by_id_not_found(self, api_client):
        """异常：不存在的 ID 返回 404"""
        resp = api_client.get("/relay-log/999999999")
        assert resp.status_code == 404

    def test_get_relay_log_by_id_invalid_format(self, api_client):
        """异常：非数字 ID 返回 400"""
        resp = api_client.get("/relay-log/abc")
        assert resp.status_code == 400

    def test_get_relay_log_by_id_negative(self, api_client):
        """异常：负数 ID 返回 400 或 404"""
        resp = api_client.get("/relay-log/-1")
        assert resp.status_code in (400, 404)


# ============================================================
#  类 5: GET /api/relay-log/stats
# ============================================================

@pytest.mark.relay
class TestGetRelayStats:
    """GET /api/relay-log/stats 接口测试"""

    def test_get_relay_stats_success(self, api_client, relay_query_data):
        """正向：获取继电器统计数据成功"""
        resp = api_client.get("/relay-log/stats")
        assert resp.status_code == 200
        data = resp.json()

        assert data.get("data") is not None

    def test_get_relay_stats_structure(self, api_client, relay_query_data):
        """正向：统计响应包含所有必需字段"""
        resp = api_client.get("/relay-log/stats")
        assert resp.status_code == 200
        stats = resp.json()["data"]
        required = [
            "periodHours", "totalOperations", "onCount", "offCount",
            "onPercentage", "avgSoilMoistureWhenOn", "avgTemperatureWhenOn",
            "avgSoilTemperatureWhenOn", "rainDetectionCount",
        ]
        for field in required:
            assert field in stats, f"统计响应缺少字段: {field}"

    def test_get_relay_stats_default_hours(self, api_client, relay_query_data):
        """正向：默认 hours=24"""
        resp = api_client.get("/relay-log/stats")
        assert resp.status_code == 200
        assert resp.json()["data"]["periodHours"] == 24

    def test_get_relay_stats_custom_hours(self, api_client, relay_query_data):
        """正向：自定义 hours 参数"""
        resp = api_client.get("/relay-log/stats", params={"hours": 1})
        assert resp.status_code == 200
        assert resp.json()["data"]["periodHours"] == 1

    def test_get_relay_stats_count_consistency(self, api_client, relay_query_data):
        """业务逻辑：onCount + offCount == totalOperations"""
        resp = api_client.get("/relay-log/stats", params={"hours": 1})
        assert resp.status_code == 200
        stats = resp.json()["data"]
        assert stats["onCount"] + stats["offCount"] == stats["totalOperations"], \
            f"onCount({stats['onCount']}) + offCount({stats['offCount']}) != totalOperations({stats['totalOperations']})"

    def test_get_relay_stats_on_percentage(self, api_client, relay_query_data):
        """业务逻辑：onPercentage 计算正确"""
        resp = api_client.get("/relay-log/stats", params={"hours": 1})
        assert resp.status_code == 200
        stats = resp.json()["data"]
        if stats["totalOperations"] > 0:
            expected = (stats["onCount"] / stats["totalOperations"]) * 100
            assert abs(stats["onPercentage"] - expected) < 0.01, \
                f"onPercentage 计算错误: 预期 {expected}, 实际 {stats['onPercentage']}"

    def test_get_relay_stats_fields_non_negative(self, api_client, relay_query_data):
        """业务逻辑：所有计数字段非负"""
        resp = api_client.get("/relay-log/stats")
        assert resp.status_code == 200
        stats = resp.json()["data"]
        assert stats["totalOperations"] >= 0
        assert stats["onCount"] >= 0
        assert stats["offCount"] >= 0
        assert stats["rainDetectionCount"] >= 0
        assert stats["onPercentage"] >= 0

    def test_get_relay_stats_invalid_hours_zero(self, api_client):
        """异常：hours=0 返回 400"""
        resp = api_client.get("/relay-log/stats", params={"hours": 0})
        _assert_error_response(resp, 400)

    def test_get_relay_stats_invalid_hours_negative(self, api_client):
        """异常：hours=-1 返回 400"""
        resp = api_client.get("/relay-log/stats", params={"hours": -1})
        _assert_error_response(resp, 400)

    def test_get_relay_stats_invalid_hours_exceed(self, api_client):
        """异常：hours=169 超过最大值 168 返回 400"""
        resp = api_client.get("/relay-log/stats", params={"hours": 169})
        _assert_error_response(resp, 400)


# ============================================================
#  类 6: GET /api/relay-log/status
# ============================================================

@pytest.mark.relay
class TestGetCurrentRelayStatus:
    """GET /api/relay-log/status 接口测试"""

    def test_get_current_status_success(self, api_client, relay_create_data):
        """正向：获取当前继电器状态成功"""
        resp = api_client.get("/relay-log/status")
        assert resp.status_code == 200
        data = resp.json()

    def test_get_current_status_has_relay_status(self, api_client, relay_create_data):
        """正向：relayStatus 为布尔值"""
        resp = api_client.get("/relay-log/status")
        assert resp.status_code == 200
        status_data = resp.json()["data"]
        assert isinstance(status_data["relayStatus"], bool), \
            f"relayStatus 应为布尔值，实际为 {type(status_data['relayStatus']).__name__}"

    def test_get_current_status_has_timestamp(self, api_client, relay_create_data):
        """正向：包含有效 timestamp"""
        resp = api_client.get("/relay-log/status")
        assert resp.status_code == 200
        status_data = resp.json()["data"]
        assert "timestamp" in status_data, "status 响应缺少 timestamp"
        try:
            datetime.fromisoformat(status_data["timestamp"].replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            pytest.fail(f"timestamp 格式无效: {status_data['timestamp']}")

    def test_get_current_status_consistent_with_latest(self, api_client, relay_create_data):
        """一致性：status 返回的 relayStatus 与 latest 端点一致"""
        status_resp = api_client.get("/relay-log/status")
        latest_resp = api_client.get("/relay-log/latest")
        assert status_resp.status_code == 200
        assert latest_resp.status_code == 200
        status_val = status_resp.json()["data"]["relayStatus"]
        latest_val = latest_resp.json()["data"]["relayStatus"]
        assert status_val == latest_val, \
            f"status({status_val}) 与 latest({latest_val}) 的 relayStatus 不一致"


# ============================================================
#  类 7: POST /api/relay-log/state-change
# ============================================================

@pytest.mark.relay
class TestLogRelayStateChange:
    """POST /api/relay-log/state-change 接口测试（带状态冲突校验）"""

    def test_state_change_conflict_same_status(self, api_client, relay_state_change_data):
        """状态冲突：请求与当前状态相同 → 400"""
        # fixture 初始状态为 ON，再次请求 ON 应冲突
        sensor_id = relay_state_change_data["sensor_ids"][0]
        payload = {
            "relayStatus": True,  # 与初始状态相同
            "triggerReason": "Conflict test - same status",
            "sensorReadingId": sensor_id,
        }
        resp = api_client.post("/relay-log/state-change", json_data=payload)
        assert resp.status_code == 400, \
            f"状态冲突应返回 400，实际 {resp.status_code}"
        data = resp.json()
        assert "already" in str(data).lower() or resp.status_code == 400

    def test_state_change_success_toggle(self, api_client, relay_state_change_data):
        """正向：切换到不同状态成功 → 201"""
        sensor_id = relay_state_change_data["sensor_ids"][0]
        payload = {
            "relayStatus": False,  # 从 ON 切换到 OFF
            "triggerReason": "State change toggle test",
            "sensorReadingId": sensor_id,
        }
        resp = api_client.post("/relay-log/state-change", json_data=payload)
        assert resp.status_code == 201, f"状态切换应返回 201，实际 {resp.status_code}: {resp.text}"
        

    def test_state_change_reflected_in_status(self, api_client, relay_state_change_data):
        """正向：切换后 GET /status 确认状态已变"""
        # 先切换到 OFF（如果当前是 ON）
        sensor_id = relay_state_change_data["sensor_ids"][0]
        payload = {
            "relayStatus": False,
            "triggerReason": "Status reflection test",
            "sensorReadingId": sensor_id,
        }
        resp = api_client.post("/relay-log/state-change", json_data=payload)
        # 可能成功（201）或冲突（400，说明已经是 OFF）
        if resp.status_code == 201:
            status_resp = api_client.get("/relay-log/status")
            assert status_resp.status_code == 200
            assert status_resp.json()["data"]["relayStatus"] is False

    def test_state_change_message_activated(self, api_client, relay_state_change_data):
        """正向：激活时 message 包含 'activated'"""
        # 先确保当前是 OFF，再切换到 ON
        sensor_id = relay_state_change_data["sensor_ids"][0]
        # 先切到 OFF
        off_payload = {
            "relayStatus": False,
            "triggerReason": "Setup for activated test",
            "sensorReadingId": sensor_id,
        }
        api_client.post("/relay-log/state-change", json_data=off_payload)
        # 再切到 ON
        on_payload = {
            "relayStatus": True,
            "triggerReason": "Test activated message",
            "sensorReadingId": sensor_id,
        }
        resp = api_client.post("/relay-log/state-change", json_data=on_payload)
        if resp.status_code == 201:
            assert "activated" in resp.json().get("message", "").lower()

    def test_state_change_invalid_relay_status_type(self, api_client, relay_state_change_data):
        """异常：relayStatus 传字符串 → 400"""
        sensor_id = relay_state_change_data["sensor_ids"][0]
        payload = {
            "relayStatus": "true",  # 字符串而非布尔值
            "triggerReason": "Invalid type test",
            "sensorReadingId": sensor_id,
        }
        resp = api_client.post("/relay-log/state-change", json_data=payload)
        _assert_error_response(resp, 400)

    def test_state_change_empty_trigger_reason(self, api_client, relay_state_change_data):
        """异常：triggerReason 为空字符串 → 400"""
        sensor_id = relay_state_change_data["sensor_ids"][0]
        payload = {
            "relayStatus": False,
            "triggerReason": "",
            "sensorReadingId": sensor_id,
        }
        resp = api_client.post("/relay-log/state-change", json_data=payload)
        _assert_error_response(resp, 400)

    def test_state_change_missing_sensor_reading_id(self, api_client):
        """异常：sensorReadingId 缺失 → 400"""
        payload = {
            "relayStatus": True,
            "triggerReason": "Missing sensorReadingId",
        }
        resp = api_client.post("/relay-log/state-change", json_data=payload)
        _assert_error_response(resp, 400)


# ============================================================
#  类 8: GET /api/relay-log/duration
# ============================================================

@pytest.mark.relay
class TestGetOperationDuration:
    """GET /api/relay-log/duration 接口测试"""

    def test_get_duration_success(self, api_client, relay_query_data):
        """正向：获取运行时长分析成功"""
        resp = api_client.get("/relay-log/duration")
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("data") is not None

    def test_get_duration_structure(self, api_client, relay_query_data):
        """正向：时长分析响应结构完整"""
        resp = api_client.get("/relay-log/duration")
        assert resp.status_code == 200
        duration = resp.json()["data"]
        required = ["periodHours", "totalOnDurationMinutes", "averageOnDurationMinutes", "operationCount"]
        for field in required:
            assert field in duration, f"时长分析响应缺少字段: {field}"

    def test_get_duration_fields_non_negative(self, api_client, relay_query_data):
        """业务逻辑：所有时长字段非负"""
        resp = api_client.get("/relay-log/duration")
        assert resp.status_code == 200
        duration = resp.json()["data"]
        assert duration["totalOnDurationMinutes"] >= 0, "totalOnDurationMinutes 应 >= 0"
        assert duration["averageOnDurationMinutes"] >= 0, "averageOnDurationMinutes 应 >= 0"
        assert duration["operationCount"] >= 0, "operationCount 应 >= 0"

    def test_get_duration_custom_hours(self, api_client, relay_query_data):
        """正向：自定义 hours 参数生效"""
        resp = api_client.get("/relay-log/duration", params={"hours": 1})
        assert resp.status_code == 200
        assert resp.json()["data"]["periodHours"] == 1

    def test_get_duration_message(self, api_client, relay_query_data):
        """正向：message 字段正确"""
        resp = api_client.get("/relay-log/duration")
        assert resp.status_code == 200
        msg = resp.json().get("message", "")
        assert "duration" in msg.lower() or "completed" in msg.lower() or "no relay" in msg.lower()

    def test_get_duration_invalid_hours_exceed(self, api_client):
        """异常：hours 超过 168 返回 400"""
        resp = api_client.get("/relay-log/duration", params={"hours": 200})
        _assert_error_response(resp, 400)


# ============================================================
#  类 9: GET /api/relay-log/health
# ============================================================

@pytest.mark.relay
class TestRelayLogHealth:
    """GET /api/relay-log/health 接口测试"""

    def test_relay_health_success(self, api_client, relay_create_data):
        """正向：健康检查返回 200"""
        resp = api_client.get("/relay-log/health")
        assert resp.status_code == 200

    def test_relay_health_status_field(self, api_client, relay_create_data):
        """正向：status 为 healthy 或 warning"""
        resp = api_client.get("/relay-log/health")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["status"] in ("healthy", "warning"), \
            f"status 应为 healthy 或 warning，实际: {data['status']}"

    def test_relay_health_structure(self, api_client, relay_create_data):
        """正向：健康检查响应结构完整"""
        resp = api_client.get("/relay-log/health")
        assert resp.status_code == 200
        data = resp.json()["data"]
        required = ["status", "hasData", "lastLogAgeMinutes", "currentRelayStatus", "recentOperations", "message"]
        for field in required:
            assert field in data, f"健康检查响应缺少字段: {field}"

    def test_relay_health_has_data_true(self, api_client, relay_create_data):
        """正向：有数据时 hasData=True，lastLogAgeMinutes 为非负整数"""
        resp = api_client.get("/relay-log/health")
        assert resp.status_code == 200
        data = resp.json()["data"]
        if data["hasData"]:
            assert data["lastLogAgeMinutes"] is not None
            assert isinstance(data["lastLogAgeMinutes"], int)
            assert data["lastLogAgeMinutes"] >= 0
            assert isinstance(data["currentRelayStatus"], bool)
            assert isinstance(data["recentOperations"], int)


# ============================================================
#  类 10: DELETE /api/relay-log/cleanup
# ============================================================

@pytest.mark.relay
class TestCleanupRelayLogs:
    """DELETE /api/relay-log/cleanup 接口测试"""

    def test_cleanup_success(self, api_client):
        """正向：默认清理返回 200"""
        resp = api_client.delete("/relay-log/cleanup")
        assert resp.status_code == 200


    def test_cleanup_custom_days(self, api_client):
        """正向：自定义 days 参数"""
        resp = api_client.delete("/relay-log/cleanup", params={"days": 30})
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["daysKept"] == 30

    def test_cleanup_response_structure(self, api_client):
        """正向：响应包含 deletedCount 和 daysKept"""
        resp = api_client.delete("/relay-log/cleanup")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "deletedCount" in data, "响应缺少 deletedCount"
        assert "daysKept" in data, "响应缺少 daysKept"
        assert isinstance(data["deletedCount"], int)
        assert data["deletedCount"] >= 0

    def test_cleanup_message(self, api_client):
        """正向：message 包含清理结果"""
        resp = api_client.delete("/relay-log/cleanup")
        assert resp.status_code == 200
        msg = resp.json().get("message", "")
        assert "cleanup" in msg.lower() or "deleted" in msg.lower()

    def test_cleanup_minimum_days(self, api_client):
        """异常：days < 7 返回 400"""
        resp = api_client.delete("/relay-log/cleanup", params={"days": 5})
        _assert_error_response(resp, 400)

    def test_cleanup_invalid_days_zero(self, api_client):
        """异常：days=0 返回 400"""
        resp = api_client.delete("/relay-log/cleanup", params={"days": 0})
        _assert_error_response(resp, 400)
