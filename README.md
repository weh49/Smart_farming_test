# Smart Farming IoT 测试实践

基于开源 IoT 项目 [agungferdi/Smart_Farming](https://github.com/agungferdi/Smart_Farming) 的测试实践仓库。

> 被测系统是一条完整的 IoT 数据链路：ESP32 传感器 → MQTT Broker → Node.js 后端 → Web 仪表盘。
> 本仓库聚焦于在这套系统之上构建的 MQTT 协议测试与接口自动化测试工程。

## 一、被测系统

```
ESP32（传感器 / 执行器）  ⇄  MQTT Broker  ⇄  Node.js 后端  ⇄  PostgreSQL
                                                  ⇅
                                           Web 仪表盘（前端）
```

| 层 | 技术 |
|---|---|
| 设备端 | ESP32 + PlatformIO（环境采集、继电器控制） |
| 通信协议 | MQTT（HiveMQ Cloud / Mosquitto） |
| 后端 | Node.js + TypeScript + Hono |
| 数据库 | PostgreSQL（Prisma ORM） |

## 二、测试技术栈

`pytest` · `requests` · `paho-mqtt` · `Locust` · `Allure`

## 三、测试内容

- **MQTT 协议测试**：发布 / 订阅链路、QoS 等级、遗嘱消息、保留消息
- **RESTful API 接口测试**：传感器数据、继电器日志、传感器校准等接口
- **数据链路全流程验证**：设备上报 → MQTT → 后端入库 → API 查询一致性
- **异常与边界场景**：非法 payload、数值越界、连接中断与恢复
- **性能测试**：Locust 压测脚本与测试报告

## 四、目录结构

```
iot-devices/               # ESP32 固件（PlatformIO）
iot-backend/               # 被测后端（Node.js + TypeScript + Prisma）
iot-dashboard/             # Web 仪表盘
test/                      # 测试工程
├── config/settings.py     # 环境配置
├── conftest.py            # fixtures
├── testcases/             # 测试用例（传感器数据 / MQTT / 继电器日志 / 校准）
├── utils/                 # api_client、mqtt_client 封装
└── xingnengTest/          # Locust 性能测试
verify_mqtt_behavior.py    # MQTT 行为验证脚本
sensor_report.html         # 性能测试报告
.github/workflows/ci.yml   # CI 流水线
```

## 五、本地运行

```bash
# 1. 启动 MQTT Broker（如 Mosquitto，监听 1883）
# 2. 启动被测后端（默认 3001 端口）
cd iot-backend
npm install
npx tsx src/index.ts

# 3. 安装测试依赖并执行
pip install -r test/requirements.txt
pytest -v
```

## 六、CI/CD

`.github/workflows/ci.yml`（GitHub Actions）：

```
push 到 main → 启动 PostgreSQL + Mosquitto 服务容器
             → 安装后端依赖 → 建库迁移（prisma migrate）
             → 启动后端与 MQTT 订阅进程
             → 安装测试依赖 → 执行 pytest
```

用服务容器把数据库和 MQTT Broker 直接起在 CI 环境内，保证测试套件在干净环境中可复现。
