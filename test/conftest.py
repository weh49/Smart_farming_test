"""
pytest 公共配置
提供通用 fixtures 和测试环境设置
"""
import pytest
import random
from uuid import uuid4
from faker import Faker
from test.utils.api_client import ApiClient
from test.utils.mqtt_client import MqttTestClient
from test.config.settings import (
    API_BASE_URL,
    MQTT_BROKER_HOST,
    MQTT_BROKER_PORT,
    MQTT_BROKER_USERNAME,
    MQTT_BROKER_PASSWORD,
)

fake = Faker()


# ============================================================
#  Faker 辅助函数：生成逼真的传感器和继电器数据
# ============================================================
def generate_sensor_record():
    """使用 faker 生成一条传感器数据"""
    return {
        "temperature": round(random.uniform(-10, 45), 2),
        "humidity": round(random.uniform(10, 95), 2),
        "soilMoisture": random.randint(0, 100),
        "soilTemperature": round(random.uniform(-5, 40), 2),
        "rainDetected": random.choice([True, False]),
        "waterLevel": random.choice(["Low", "Medium", "High"]),
    }


RELAY_ON_REASONS = [
    "Soil moisture below threshold, activating pump",
    "Automatic irrigation triggered by low soil moisture",
    "Scheduled watering cycle started",
    "Manual override: pump activated",
    "Emergency irrigation due to extreme dryness",
]

RELAY_OFF_REASONS = [
    "Soil moisture recovered to adequate level",
    "Rain detected, deactivating pump for water conservation",
    "Scheduled watering cycle completed",
    "Manual override: pump deactivated",
    "Water level low, stopping pump to prevent dry run",
]


def generate_relay_log_record(sensor_id: str, relay_status: bool = None):
    """使用 faker 生成一条继电器日志数据"""
    if relay_status is None:
        relay_status = random.choice([True, False])
    reason = random.choice(RELAY_ON_REASONS if relay_status else RELAY_OFF_REASONS)
    return {
        "relayStatus": relay_status,
        "triggerReason": reason,
        "sensorReadingId": sensor_id,
    }


# ============================================================
#  基础 Fixtures
# ============================================================
@pytest.fixture(scope="session")
def api_base_url():
    """API 基础 URL fixture"""
    return API_BASE_URL


@pytest.fixture(scope="function")
def api_client():
    """API 客户端 fixture - 每个测试函数创建新的客户端"""
    client = ApiClient()
    yield client
    client.close()


@pytest.fixture(scope="session")
def session_api_client():
    """API 客户端 fixture - 整个测试会话共享"""
    client = ApiClient()
    yield client
    client.close()


# ============================================================
#  传感器数据 Fixtures（sensor-data 测试用）
# ============================================================
@pytest.fixture(scope="module")
def sensor_test_data(session_api_client):
    """
    模块级传感器测试数据 fixture
    在测试模块开始前通过 POST 创建测试数据，模块结束后清理。

    返回:
        dict: {
            "records": 创建的原始数据列表,
            "ids": 创建的数据 ID 列表（字符串）,
            "responses": 创建时的完整响应列表
        }
    """
    created_ids = []
    responses = []

    test_records = [
        # 数据 A: 正常晴天
        {
            "temperature": 28.5,
            "humidity": 55.0,
            "soilMoisture": 40,
            "soilTemperature": 24.0,
            "rainDetected": False,
            "waterLevel": "Medium",
        },
        # 数据 B: 雨天高湿
        {
            "temperature": 18.0,
            "humidity": 92.0,
            "soilMoisture": 85,
            "soilTemperature": 17.5,
            "rainDetected": True,
            "waterLevel": "High",
        },
        # 数据 C: 边界值（无土壤温度）
        {
            "temperature": -5.0,
            "humidity": 15.0,
            "soilMoisture": 10,
            "rainDetected": False,
            "waterLevel": "Low",
        },
    ]

    for record in test_records:
        resp = session_api_client.post("/sensor-data", json_data=record)
        responses.append(resp)
        if resp.status_code == 201:
            data = resp.json().get("data", {})
            created_ids.append(str(data.get("id", "")))

    yield {
        "records": test_records,
        "ids": created_ids,
        "responses": responses,
    }


# ============================================================
#  传感器数据池（继电器日志测试用，session 级共享）
# ============================================================
@pytest.fixture(scope="session")
def sensor_data_pool(session_api_client):
    """
    Session 级传感器数据池
    使用 faker 生成 20 条多样化传感器数据，供所有继电器日志 fixture 使用。

    返回:
        dict: {
            "ids": 传感器数据 ID 列表（字符串）,
            "records": 原始数据列表,
            "count": 成功创建的记录数
        }
    """
    created_ids = []
    records = []

    for _ in range(20):
        record = generate_sensor_record()
        resp = session_api_client.post("/sensor-data", json_data=record)
        if resp.status_code == 201:
            data = resp.json().get("data", {})
            created_ids.append(str(data.get("id", "")))
            records.append(record)

    yield {
        "ids": created_ids,
        "records": records,
        "count": len(created_ids),
    }


# ============================================================
#  继电器日志 Fixtures - POST /api/relay-log 专用
# ============================================================
@pytest.fixture(scope="module")
def relay_create_data(session_api_client, sensor_data_pool):
    """
    为 POST /api/relay-log 测试创建数据。
    隔离于 state-change 测试。

    创建 3 条基础继电器日志，用于验证创建接口的基本功能。

    返回:
        dict: {
            "ids": 创建的继电器日志 ID 列表,
            "records": 原始请求数据列表,
            "sensor_ids": 使用的传感器 ID 列表
        }
    """
    sensor_ids = sensor_data_pool["ids"]
    created_ids = []
    records = []

    # 固定 3 条场景数据，确保测试可预测
    scenarios = [
        {"relayStatus": True, "triggerReason": "Soil moisture below threshold, activating pump"},
        {"relayStatus": False, "triggerReason": "Soil moisture recovered to adequate level"},
        {"relayStatus": True, "triggerReason": "Automatic irrigation triggered by low soil moisture"},
    ]

    for i, scenario in enumerate(scenarios):
        sensor_id = sensor_ids[i % len(sensor_ids)]
        record = {**scenario, "sensorReadingId": sensor_id}
        resp = session_api_client.post("/relay-log", json_data=record)
        if resp.status_code == 201:
            data = resp.json().get("data", {})
            created_ids.append(str(data.get("id", "")))
            records.append(record)

    yield {
        "ids": created_ids,
        "records": records,
        "sensor_ids": sensor_ids[:3],
    }
    for rid in created_ids:
        try:
            session_api_client.delete(f"/relay-log/{rid}")
        except Exception:
            pass


# ============================================================
#  继电器日志 Fixtures - POST /api/relay-log/state-change 专用
# ============================================================
@pytest.fixture(scope="module")
def relay_state_change_data(session_api_client, sensor_data_pool):
    """
    为 POST /api/relay-log/state-change 测试创建数据。
    隔离于 basic creation 测试。

    state-change 端点有状态冲突校验：
    - 如果当前状态与请求状态相同 → 返回 400
    - 因此需要先创建一条初始日志设置当前状态

    返回:
        dict: {
            "sensor_ids": 可用的传感器 ID 列表,
            "initial_relay_id": 初始继电器日志 ID,
            "initial_status": 初始继电器状态
        }
    """
    sensor_ids = sensor_data_pool["ids"]

    # 创建一条初始继电器日志，设置当前状态为 ON
    initial_record = {
        "relayStatus": True,
        "triggerReason": "Initial pump activation for state-change test setup",
        "sensorReadingId": sensor_ids[0],
    }
    resp = session_api_client.post("/relay-log", json_data=initial_record)
    initial_id = ""
    initial_status = True
    if resp.status_code == 201:
        data = resp.json().get("data", {})
        initial_id = str(data.get("id", ""))
        initial_status = data.get("relayStatus", True)

    yield {
        "sensor_ids": sensor_ids,
        "initial_relay_id": initial_id,
        "initial_status": initial_status,
    }
    if initial_id:
        try:
            session_api_client.delete(f"/relay-log/{initial_id}")
        except Exception:
            pass

# ============================================================
#  继电器日志 Fixtures - GET 端点分页测试用
# ============================================================
@pytest.fixture(scope="module")
def relay_query_data(session_api_client, sensor_data_pool):
    """
    为 GET 端点测试创建足够多的继电器日志数据（15+ 条）。
    用于分页、过滤、统计等测试。

    使用 faker 生成多样化的继电器日志，确保：
    - 数量 > 10（覆盖默认分页 limit=10）
    - 有 ON 和 OFF 两种状态（覆盖 status 过滤）
    - triggerReason 多样化（覆盖不同业务场景）

    返回:
        dict: {
            "ids": 所有创建的继电器日志 ID 列表,
            "on_ids": relayStatus=True 的 ID 列表,
            "off_ids": relayStatus=False 的 ID 列表,
            "sensor_ids": 使用的传感器 ID 列表,
            "total_count": 总创建数
        }
    """
    sensor_ids = sensor_data_pool["ids"]
    created_ids = []
    on_ids = []
    off_ids = []

    # 创建 18 条继电器日志，约一半 ON 一半 OFF
    for i in range(18):
        relay_status = i % 2 == 0  # 交替 ON/OFF
        sensor_id = sensor_ids[i % len(sensor_ids)]
        record = generate_relay_log_record(sensor_id, relay_status)
        resp = session_api_client.post("/relay-log", json_data=record)
        if resp.status_code == 201:
            data = resp.json().get("data", {})
            rid = str(data.get("id", ""))
            created_ids.append(rid)
            if relay_status:
                on_ids.append(rid)
            else:
                off_ids.append(rid)

    yield {
        "ids": created_ids,
        "on_ids": on_ids,
        "off_ids": off_ids,
        "sensor_ids": sensor_ids,
        "total_count": len(created_ids),
    }
    for rid in created_ids:
        try:
            session_api_client.delete(f"/relay-log/{rid}")
        except Exception:
            pass

# ============================================================
#  MQTT Fixtures - 集成测试设计
# ============================================================
@pytest.fixture(scope="session")
def mqtt_test_topic_prefix():
    """生成唯一的测试主题前缀，避免测试间干扰"""
    return f"sf/test-{uuid4().hex[:8]}"


@pytest.fixture(scope="session")
def mqtt_client(mqtt_test_topic_prefix):
    """
    Session 级 MQTT 测试客户端，连接 Broker 用于集成测试。

    使用 MqttTestClient 封装，提供：
    - 自动连接等待（5 秒超时）
    - publish() 返回 (topic, MQTTMessageInfo)
    - get_one_message() 从队列接收消息

    依赖 mqtt_test_topic_prefix fixture 提供唯一主题前缀。
    """
    client = MqttTestClient(
        topic_prefix=mqtt_test_topic_prefix,
        host=MQTT_BROKER_HOST,
        port=MQTT_BROKER_PORT,
        username=MQTT_BROKER_USERNAME or None,
        password=MQTT_BROKER_PASSWORD or None,
    )
    yield client
    client.close()


# ============================================================
#  pytest 配置钩子
# ============================================================
def pytest_configure(config):
    """pytest 配置钩子 - 注册自定义 markers"""
    config.addinivalue_line("markers", "smoke: 冒烟测试")
    config.addinivalue_line("markers", "health: 健康检查相关测试")
    config.addinivalue_line("markers", "sensor: 传感器数据相关测试")
    config.addinivalue_line("markers", "relay: 继电器日志相关测试")
    config.addinivalue_line("markers", "mqtt: MQTT 相关测试")
