"""
测试环境配置
支持通过环境变量覆盖默认配置
"""
import os

# API 基础 URL - 默认指向本地开发环境
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:3001/api")

# 请求超时时间（秒）
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "10"))

# MQTT 服务 URL（如需要）
MQTT_SERVICE_URL = os.getenv("MQTT_SERVICE_URL", "http://localhost:3002")
# MQTT Broker 连接配置（用于集成测试）
MQTT_BROKER_HOST = os.getenv("MQTT_BROKER_HOST", "localhost")
MQTT_BROKER_PORT = int(os.getenv("MQTT_BROKER_PORT", "1883"))
MQTT_BROKER_USERNAME = os.getenv("MQTT_BROKER_USERNAME", "")
MQTT_BROKER_PASSWORD = os.getenv("MQTT_BROKER_PASSWORD", "")
MQTT_BROKER_PROTOCOL = os.getenv("MQTT_BROKER_PROTOCOL", "mqtt")

# API Key（如需要）
API_KEY = os.getenv("API_KEY", "")
