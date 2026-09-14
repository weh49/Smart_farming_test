import pytest

# 标定值
DRY_VALUE = 2945  # 0% 湿度（完全干燥时的 ADC 读数）
WET_VALUE = 1390  # 100% 湿度（完全湿润时的 ADC 读数）

def map_adc_to_percentage(raw_value: int) -> int:
    """将土壤湿度传感器原始 ADC 值映射为 0~100 的百分比。
    
    物理原理：电阻式土壤湿度传感器，土壤越湿 → 导电性越好 → ADC 读数越低。
    即：低值 = 湿润，高值 = 干燥。
    
    Args:
        raw_value: ESP32 ADC 原始读数
        
    Returns:
        0 ~ 100 的湿度百分比（int）
    """
    if raw_value >= DRY_VALUE:
        return 0
    if raw_value <= WET_VALUE:
        return 100
    # 线性映射并向下取整（使用 //）
    return 100 * (DRY_VALUE - raw_value) // (DRY_VALUE - WET_VALUE)

@pytest.mark.parametrize("test_data,raw_value,expected_percentage",[
    ("A",1000,100),("B",2167,50),("C",3500,0),
    ("湿界—上",1390,100),("湿界—内",1391,99),("湿界—外",1389,100),
    ("干界—上",2945,0),("干界—内",2944,0),("干界—外",2946,0)
])
class TestSensorCalibration:
    def test_sensor_calibration(self,test_data,raw_value,expected_percentage):
        """传感器干湿等价和边界类测试"""
        assert map_adc_to_percentage(raw_value) == expected_percentage,\
        f"\n测试 {test_data} 失败，期望 {expected_percentage}，实际 {map_adc_to_percentage(raw_value)}"
    
LOW_THRESHOLD = 350
MEDIUM_THRESHOLD = 400
def determine_status(raw_value: int) -> str:
    if raw_value < LOW_THRESHOLD:
        return "Low"
    elif raw_value < MEDIUM_THRESHOLD:
        return "Medium"
    else:
        return "High"

@pytest.mark.parametrize("test_data,raw_value,expected_status",[
    ("A",-100,"Low"),("B",0,"Low"),("C",100,"Low"),("D",349,"Low"),
    ("a",350,"Medium"),("b",376,"Medium"),("c",399,"Medium"),
    ("1",400,"High"),("2",800,"High"),("3",1050,"High"),("4",2000,"High")
])
class TestdetermineStatus:
    def test_water_level_status(self,test_data,raw_value,expected_status):
        """测试水位状态判定函数（对齐C++现有逻辑）"""
        result = determine_status(raw_value)
        assert result == expected_status,\
        f"\n测试 {test_data} 失败，期望 {expected_status}，实际 {result}"
    
# 黑盒校验规则（完全对应C++代码的边界值）
VALIDATION_RULES = [
    # (测试标签, 待测值, 最小值, 最大值, 预期结果)
    ("Soil_ADC", 0, 0, 4095, True),
    ("Soil_ADC", 4095, 0, 4095, True),
    ("Soil_ADC", -1, 0, 4095, False),   # 硬件短路/虚焊
    ("Soil_ADC", 4096, 0, 4095, False), # ADC溢出

    ("Water_ADC", 0, 0, 4095, True),
    ("Water_ADC", -1, 0, 4095, False),  # 水位通道异常
    
    ("DHT11_Temp", -40.0, -40.0, 80.0, True),
    ("DHT11_Temp", 80.0, -40.0, 80.0, True),
    ("DHT11_Temp", -41.0, -40.0, 80.0, False), # 极寒异常
    ("DHT11_Temp", 81.0, -40.0, 80.0, False),  # 高温异常

    ("DS18B20_Temp", -55.0, -55.0, 125.0, True),
    ("DS18B20_Temp", 125.0, -55.0, 125.0, True),
    ("DS18B20_Temp", -56.0, -55.0, 125.0, False),
    ("DS18B20_Temp", 126.0, -55.0, 125.0, False),

    ("Humidity", 0.0, 0.0, 100.0, True),
    ("Humidity", 100.0, 0.0, 100.0, True),
    ("Humidity", -0.1, 0.0, 100.0, False),
    ("Humidity", 100.1, 0.0, 100.0, False),
]

@pytest.mark.parametrize("label, value, min_val, max_val, expected", VALIDATION_RULES)
def test_sensor_validation_ranges(label, value, min_val, max_val, expected):
    """测试传感器校验范围"""
    result = (min_val <= value <= max_val)
    assert result == expected, f"{label} 边界校验失败：value={value}"



  
        