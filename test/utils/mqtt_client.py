"""
MQTT 测试客户端封装
基于 paho-mqtt v2.x，提供连接管理、消息发布/订阅、消息接收队列。
"""
import queue
import threading
import paho.mqtt.client as mqtt


class MqttTestClient:
    """MQTT 测试客户端，用于集成测试中与 Broker 交互。"""

    def __init__(self, topic_prefix, host, port, username=None, password=None):
        """
        初始化并连接 MQTT 客户端。

        Args:
            topic_prefix: 测试主题前缀，用于隔离不同测试 session
            host: MQTT Broker 地址
            port: MQTT Broker 端口
            username: 认证用户名（可选）
            password: 认证密码（可选）

        Raises:
            ConnectionError: 5 秒内未连接成功
        """
        self.topic_prefix = topic_prefix
        self.message_queue = queue.Queue()
        self.connected_event = threading.Event()

        # paho-mqtt v2.x 要求第一个参数为 CallbackAPIVersion
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1)

        if username:
            self.client.username_pw_set(username, password)

        # 注册回调
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message

        self.client.connect(host, port)
        self.client.loop_start()

        # 等待连接就绪，最多 5 秒
        if not self.connected_event.wait(timeout=5):
            self.client.loop_stop()
            self.client.disconnect()
            raise ConnectionError(
                f"MQTT Broker {host}:{port} 连接超时（5秒）"
            )

    def _on_connect(self, client, userdata, flags, rc, properties=None):
        """连接成功回调（paho v2 回调签名）"""
        if rc == 0:
            self.connected_event.set()

    def _on_message(self, msg):
        """收到消息回调，放入队列"""    
        self.message_queue.put(msg)

    def make_topic(self, suffix):
        """根据后缀生成完整主题"""
        return f"{self.topic_prefix}/{suffix}"

    def publish(self, suffix, payload, qos=0, retain=False):
        """
        发布测试消息。

        Args:
            suffix: 主题后缀（会自动拼接 topic_prefix）
            payload: 消息内容（字符串或 JSON 字符串）
            qos: QoS 等级（0/1/2），默认 0
            retain: 是否保留消息，默认 False

        Returns:
            tuple: (topic, MQTTMessageInfo)
                - topic: 完整的主题字符串
                - MQTTMessageInfo: paho 返回的发布结果对象，可调用 is_published() 检查
        """
        topic = self.make_topic(suffix)
        result = self.client.publish(topic, payload, qos, retain)
        return topic, result

    def subscribe(self, suffix, qos=1):
        """
        订阅测试主题。

        Args:
            suffix: 主题后缀
            qos: QoS 等级，默认 1

        Returns:
            str: 完整的主题字符串
        """
        topic = self.make_topic(suffix)
        self.client.subscribe(topic, qos)
        return topic

    def get_one_message(self, timeout=2):
        """
        从消息队列获取一条消息（阻塞等待）。

        Args:
            timeout: 超时时间（秒），默认 2

        Returns:
            tuple: (topic, payload_str) 或 (None, None)（超时）
        """
        try:
            msg = self.message_queue.get(timeout=timeout)
            return msg.topic, msg.payload.decode()
        except queue.Empty:
            return None, None

    def close(self):
        """关闭客户端连接，停止网络循环。"""
        self.client.loop_stop()
        self.client.disconnect()
