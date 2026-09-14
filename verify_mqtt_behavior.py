"""
一次性验证脚本：观察后端对非法/合法 MQTT 消息的真实行为。
不跑 pytest，直接驱动 broker + REST 观察。
"""
import json
import time
import paho.mqtt.client as mqtt
import requests

BROKER = "localhost"
PORT = 1883
API = "http://localhost:3001/api"


def latest_sensor_id():
    """返回当前最新一条 sensor-data 的 id（字符串），没有则 None"""
    r = requests.get(f"{API}/sensor-data/latest", timeout=5)
    data = r.json().get("data")
    if not data:
        return None
    return data.get("id")


def latest_relay_id():
    r = requests.get(f"{API}/relay-log/latest", timeout=5)
    data = r.json().get("data")
    if not data:
        return None
    return data.get("id")


def make_client():
    c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    c.connect(BROKER, PORT)
    c.loop_start()
    time.sleep(0.5)
    return c


def publish(c, topic, payload):
    info = c.publish(topic, payload, qos=0)
    info.wait_for_publish(timeout=5)
    return info.is_published()


def step(msg):
    print(f"\n=== {msg} ===")


# ---- 开始观察 ----
c = make_client()

# 基线
step("基线：记录当前最新 id")
sid_before = latest_sensor_id()
print(f"sensor latest id (before) = {sid_before}")

# 实验1：非 JSON 消息
step("实验1：发布【非 JSON 消息】到 sf/verify/sensor")
ok = publish(c, "sf/verify/sensor", "plain text not json")
print(f"publish 发出: {ok}")
time.sleep(2)
sid_after = latest_sensor_id()
print(f"sensor latest id (after)  = {sid_after}")
print(f"→ 结论: {'id 没变，消息被丢弃 ✅（无 HTTP 响应）' if sid_after == sid_before else 'id 变了，消息被存储 ❌'}")

# 实验2：缺必填字段的 JSON
step("实验2：发布【缺 temperature 的 JSON】到 sf/verify/sensor")
ok = publish(c, "sf/verify/sensor", json.dumps({"humidity": 60, "soilMoisture": 40, "rainDetected": False, "waterLevel": "Medium"}))
print(f"publish 发出: {ok}")
time.sleep(2)
sid_after2 = latest_sensor_id()
print(f"sensor latest id (after)  = {sid_after2}")
print(f"→ 结论: {'id 没变，消息被丢弃 ✅' if sid_after2 == sid_before else 'id 变了，消息被存储 ❌'}")

# 实验3（sanity）：合法 JSON —— 证明路径本身是通的
step("实验3（对照）：发布【合法 JSON】到 sf/verify/sensor —— 证明路径能存")
ok = publish(c, "sf/verify/sensor", json.dumps({"temperature": 31.5, "humidity": 62.0, "soilMoisture": 44, "rainDetected": False, "waterLevel": "Medium"}))
print(f"publish 发出: {ok}")
time.sleep(2)
sid_after3 = latest_sensor_id()
print(f"sensor latest id (after)  = {sid_after3}")
print(f"→ 结论: {'id 变了，合法消息已存储 ✅ 路径正常' if sid_after3 != sid_before else 'id 没变 ❌ 合法消息也没存，路径有问题'}")

c.loop_stop()
c.disconnect()
print("\n验证完成。")
