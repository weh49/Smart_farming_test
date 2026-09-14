"""
测试 MQTT 服务
"""
from datetime import datetime
import pytest

# ============================================================
#  类 1: `TestMqttHealth` | GET /api/mqtt/health 
# ============================================================

@pytest.mark.mqtt
class TestMqttHealth:
    def test_mqtt_health(self,api_client):
        """正向：返回 200 | 基本可达性"""
        resp = api_client.get("/mqtt/health")
        assert resp.status_code == 200, f"MQTT health check failed: {resp.status_code}"
        assert resp.json()["success"] is True, f"MQTT health check failed: {resp.json()['success']}"
    
    def test_mqtt_health_response_structure(self,api_client):
        """结构：包含 success/mqtt/timestamp | 字段完整性"""
        resp = api_client.get("/mqtt/health")
        data = resp.json()
        assert "success" in data, f"MQTT health check failed: {data}"
        assert "mqtt" in data, f"MQTT health check failed: {data}"
        assert "connected" in data["mqtt"], f"MQTT health check failed: {data['mqtt']}"
        
    def test_mqtt_health_response_bool(self,api_client):
        """mqtt.connected 为bool"""
        resp = api_client.get("/mqtt/health")
        data = resp.json()
        assert isinstance(data["mqtt"]["connected"], bool), f"MQTT health check failed: {data['mqtt']['connected']}"

    def test_mqtt_health_response_timestamp(self,api_client):
        """mqtt.timestamp 为有效 ISO 时间"""
        resp = api_client.get("/mqtt/health")
        data = resp.json()["timestamp"]
        assert isinstance(data, str), f"MQTT health check failed: {data}"
        if data.endswith('Z'):
            data = data.replace('Z', '+00:00')
        datetime.fromisoformat(data)

# ============================================================
#  类 2: `TestMqttPublish` | POST /api/mqtt/publish 
# ============================================================

@pytest.mark.mqtt
class TestMqttPublish:
    def test_mqtt_publish(self,api_client):
        """正向：参数完整性的校验"""
        resp = api_client.post("/mqtt/publish", json_data={"topic": "test/topic", "payload": "test payload"})
        assert resp.status_code == 200, f"MQTT publish failed: {resp.status_code}"
    def test_mqtt_write_log(self,api_client):
        """正向: 自动计入继电器日志"""
        resp = api_client.post("/mqtt/publish", json_data={"topic": "test/topic", "payload": "test payload"})
        assert resp.status_code == 200, f"MQTT publish failed: {resp.status_code}"
        assert resp.json()["success"] is True, f"MQTT publish failed: {resp.json()['success']}"
    def test_mqtt_json_response(self,api_client):
        """正向: 响应 mqtt结构格式验证"""
        resp = api_client.post("/mqtt/publish", json_data={"topic": "test/topic", "payload": "test payload"})
        assert isinstance(resp.json()["timestamp"], str), f"MQTT publish failed: {resp.json()['timestamp']}"    
    def test_mqtt_error_response(self,api_client):
        """负向: 缺少参数"""
        resp = api_client.post("/mqtt/publish", json_data={"topic": "sf/devices/relay/command","qos":"3"})
        assert resp.status_code == 400, f"MQTT publish failed: {resp.status_code}"
        
    def test_mqtt_relayPersisted(self,api_client,sensor_data_pool):
        """正向: 继计继电器日志relayPersisted字段验证（显式关联一条已存在的传感器数据）"""
        current = api_client.get("/relay-log/status").json()["data"]["relayStatus"]
        target = not current
        sensor_id = sensor_data_pool["ids"][0]
        resp = api_client.post("/mqtt/publish", 
            json_data={"topic": "sf/devices/relay/command",
                       "payload": {"status": target, "sensorReadingId": sensor_id}}) 
        assert resp.json()["relayPersisted"] == True, f"MQTT publish failed: {resp.json()}"
        
    
# ============================================================
#  类 3: `TestMqttSensorPipeline` | MQTT → sensor-data 存储 ；MQTT（mqtt_client）+ HTTP 验证 
# ============================================================
import json
import time
import logging
@pytest.mark.smoke
@pytest.mark.mqtt
class TestMqttSensorPipeline:
    def test_mqtt_sensor_pipeline(self,mqtt_client,api_client):
        """正向: 测试传感器数据管道"""

        # 1. 构造合法 JSON payload 并发布到 sf/devices/sensor 主题
        payload = json.dumps({
            "temperature": 25.0, 
            "humidity": 60.0,
            "soilMoisture": 50.0,
            "rainDetected": False,
            "waterLevel": "Medium"})
        result = mqtt_client.publish("sensor", payload)
        # time.sleep(1.0)    简单异步等待，确保数据写入数据库，获取到最新的传感器数据
        # 轮询等待 20 次，每次 0.1 秒，确保数据写入数据库，获取到最新的传感器数据

        # 2. 先确认 publish 成功，再做后续轮询（避免无意义的 2s 等待）
        result[1].wait_for_publish(timeout = 5)
        assert result[1].is_published(), f"MQTT publish failed: {result[1].mid}"

        # 3. 轮询等待数据落库（用 is not None 判断，避免浮点精度问题导致死循环）
        for _ in range(20):
            resp = api_client.get("/sensor-data/latest")
            data = resp.json().get("data") or {}
            if data.get("temperature") is not None and data.get("humidity") is not None:
                break
            time.sleep(0.1)
        else:
            pytest.fail("MQTT sensor-data timeout")
        
        # 4. 断言 + 清理，用 try/finally 保证 teardown 一定执行

        assert resp.status_code == 200,f"期望状态码是200，实际是{resp.status_code}，响应体是{resp.text[:200]}"
        body = resp.json()
        assert float(body["data"]["temperature"]) == pytest.approx(25.0,abs=0.01), f"MQTT sensor-data temperature error: {body['data']['temperature']}"
        assert float(body["data"]["humidity"]) == pytest.approx(60.0,abs=0.01), f"MQTT sensor-data humidity error: {body['data']['humidity']}"
        assert body["data"]["createdAt"] is not None, f"MQTT sensor-data createdAt error: {body['data']['createdAt']}"        
        logging.debug("sensor-data pipeline test passed %s",body)


    def test_MQTT_sensor_data_invalid_json_payload(self,mqtt_client,api_client):
        """异常: 测试传感器数据管道, payload 不是 JSON 格式"""
        # 1. 发之前，记录最新一条的 id
        time.sleep(1.0)
        before = (api_client.get("/sensor-data/latest").json().get("data") or {}).get("id")
        rc,result = mqtt_client.publish("sensor", "plain text")
        # time.sleep(1.0)    简单异步等待，确保数据写入数据库，获取到最新的传感器数据
        result.wait_for_publish(timeout = 5)
        assert result.is_published(), f"MQTT publish failed: rc = {rc}"
        # 3. 发之后，再查最新 id
        after = (api_client.get("/sensor-data/latest").json().get("data") or {}).get("id")
        # 4. id 没变 = 非法消息确实被丢弃了
        assert before == after, f"非法消息不应被存储：before={before}, after={after}"

    def test_MQTT_sensor_data_missing_fields(self,mqtt_client,api_client):
        """异常: 测试传感器数据管道, payload 缺失关键字段"""
        # 1. 发之前，记录最新一条的 id
        time.sleep(1.0)
        before = (api_client.get("/sensor-data/latest").json().get("data") or {}).get("id")
        rc,result = mqtt_client.publish("sensor", json.dumps({
            "temperature": None, 
            "humidity": None,
            "soilMoisture": 50.0,
            "rainDetected": False,
            "waterLevel": "Medium"}))
        # time.sleep(1.0)    简单异步等待，确保数据写入数据库，获取到最新的传感器数据
        result.wait_for_publish(timeout = 5)
        assert result.is_published(), f"MQTT publish failed: rc = {rc}"
        # 3. 发之后，再查最新 id
        after = (api_client.get("/sensor-data/latest").json().get("data") or {}).get("id")
        # 4. id 没变 = 非法消息确实被丢弃了
        assert before == after, f"非法消息不应被存储：before={before}, after={after}"


    def test_MQTT_relay_log(self, mqtt_client, api_client, sensor_data_pool):
        """正向: 测试继电器日志管道（关联一条真实存在的传感器数据，避免外键失败）"""
        # 1. 查当前状态，取反（避免状态冲突）
        current = api_client.get("/relay-log/status").json()["data"]["relayStatus"]
        target = not current
        sensor_id = sensor_data_pool["ids"][0]
        # 2. 记录 before id
        before = (api_client.get("/relay-log/latest").json().get("data") or {}).get("id")

        payload = json.dumps({"relayStatus": target, "sensorReadingId": sensor_id})
        rc, msg_info = mqtt_client.publish("relay", payload)
        msg_info.wait_for_publish(timeout=5)
        assert msg_info.is_published(), f"publish 失败: rc={rc}"

        # 3. 轮询：等 id 变化（有新记录落库）
        for _ in range(20):
            resp = api_client.get("/relay-log/latest")
            after_id = (resp.json().get("data") or {}).get("id")
            if after_id != before:
                break
            time.sleep(0.1)
        else:
            pytest.fail("MQTT relay-log timeout")

        # 4. 断言新记录（relayStatus 是布尔；sensorReadingId 是字符串）
        body = resp.json()
        assert body["data"]["relayStatus"] is target
        assert body["data"]["sensorReadingId"] == str(sensor_id)   # ← 字符串，BigInt
        assert body["data"]["createdAt"] is not None

    
    def test_MQTT_relay_log_missing_fields(self,mqtt_client,api_client):
        """异常: 测试继电器日志管道, 缺失状态字段，没有state/status"""
        # 1. 发之前，记录最新一条的 id
        before = (api_client.get("/relay-log/latest").json().get("data") or {}).get("id")
        payload = json.dumps({
            # "state": "",
            "sensorReadingId": "1",
            "createdAt": None
        })
        rc, msg_info = mqtt_client.publish("relay", payload)
        msg_info.wait_for_publish(timeout=5)
        assert msg_info.is_published(), f"publish 失败: rc={rc}"
         # 3. 发之后，再查最新 id
        after = (api_client.get("/relay-log/latest").json().get("data") or {}).get("id")
        # 4. id 没变 = 非法消息确实被丢弃了
        assert before == after, f"非法消息不应被存储：before={before}, after={after}"
      

