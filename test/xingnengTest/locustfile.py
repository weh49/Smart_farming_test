from locust import HttpUser, task, between

class XingnengUser(HttpUser):
    """获取最近一条数据的性能测试"""
    host = "http://localhost:3001/api"
    wait_time = between(1, 5)

    @task(1)
    def get_latest_data(self):
        """获取最近一条数据"""
        self.client.get("/sensor-data/latest", name="GET /sensor-data/latest", timeout=3)



