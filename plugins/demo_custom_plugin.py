# -*- coding: utf-8 -*-
"""
=============================================================================
第三方扩展插件示例: 激光测距传感器词库与康宁 HMI 命名合规性校验插件
=============================================================================
本示例演示第三方开发者（如传感器厂商、外部系统集成商、质量把关部门）
如何基于 plc_table_toolkit 的微内核 SPI 体系，无需侵入核心代码即可实现：
  1. 动态注入专有领域词典与参数化正则规则 (DictionaryProviderPlugin)
  2. 动态注入自定义后置质量断言规则 (PostVerifyRulePlugin)
  3. 通过 Kernel 统一注册中心热加载并完成自动化处理与质检验收
=============================================================================
"""

import os
import sys
import re
import tempfile
from typing import List, Dict, Tuple, Optional, Any, Callable, Union

# Ensure core and workflow root are in sys.path
_CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
_WORKFLOW_ROOT = os.path.dirname(_CURRENT_DIR)
_CORE_DIR = os.path.join(_WORKFLOW_ROOT, "core")
for p in [_CORE_DIR, _WORKFLOW_ROOT, _CURRENT_DIR]:
    if p not in sys.path:
        sys.path.insert(0, p)

from plc_table_toolkit import (
    BasePlugin,
    DictionaryProviderPlugin,
    PostVerifyRulePlugin,
    TableDocument,
    Kernel,
    VarTableProcessor,
    TableVerifier,
    get_default_kernel,
)


# =============================================================================
# 1. 自定义专有字典插件 (Custom Dictionary Provider Plugin)
# =============================================================================

class LaserSensorDictionaryPlugin(DictionaryProviderPlugin):
    """激光测距与修边机专有术语扩展词典插件"""
    plugin_id = "laser_sensor_trimmer_dictionary"
    plugin_name = "Laser Sensor & Trimmer Extension Dictionary"
    version = "1.0.0"
    priority = 20  # 高优先级 (优于内置词库的 priority 100)

    def get_exact_phrases(self) -> Dict[str, str]:
        """精确匹配短语 (优先于内置词库匹配)"""
        return {
            "激光测距位移传感器通讯异常": "Laser Distance Displacement Sensor Comm Error!",
            "激光测距位移传感器通讯正常": "Laser Distance Displacement Sensor Comm Normal",
            "修边刀使用统计": "Trimming Cutter Usage Statistics",
            "削边深度微调": "Trimming Depth Fine Tuning",
            "四角吸盘真空检测": "Four-Corner Suction Cup Vacuum Detection",
        }

    def get_word_pairs(self) -> List[Tuple[str, str]]:
        """多词素贪婪子串替换对"""
        return [
            ("激光测距传感器", "Laser Distance Sensor"),
            ("激光位移计", "Laser Displacement Gauge"),
            ("激光传感器", "Laser Sensor"),
            ("修边刀伺服", "Trimming Cutter Servo"),
            ("修边刀", "Trimming Cutter"),
            ("削边刀", "Trimming Cutter"),
            ("刮边刀", "Scraping Cutter"),
            ("削边", "Trimming"),
            ("刮边", "Edge Scraping"),
            ("位移计", "Displacement Gauge"),
            ("测距", "Distance Measurement"),
        ]

    def get_regex_rules(self) -> List[Tuple[Union[re.Pattern, str], Callable]]:
        """参数化动态正则规则"""
        def handle_laser_sensor(m: re.Match, tr: Callable[[str], str]) -> str:
            sensor_id = m.group(1)
            raw_state = m.group(2)
            state_map = {"正常": "Normal", "异常": "Error!", "报警": "Alarm!"}
            state = state_map.get(raw_state, tr(raw_state))
            return f"Laser Distance Sensor #{sensor_id} {state}"

        return [
            (re.compile(r'^激光测距传感器(\d+)#?(异常|正常|报警)$'), handle_laser_sensor),
        ]


# =============================================================================
# 2. 自定义后置校验规则插件 (Custom Post-Verification Rule Plugin)
# =============================================================================

class CorningComplianceRulePlugin(PostVerifyRulePlugin):
    """康宁项目 HMI 注释长度与数据规范性扩展校验规则插件"""
    plugin_id = "corning_compliance_verifier"
    plugin_name = "Corning HMI Tag Length & Formatting Rule"
    version = "1.0.0"
    priority = 10

    def __init__(self, max_comment_len: int = 120):
        super().__init__()
        self.max_comment_len = max_comment_len

    def verify(self, src_path: str, tgt_path: str, doc: TableDocument, context: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """执行专业领域后置质检断言"""
        errors = []
        for idx, row in enumerate(doc.rows, 1):
            if not row.raw_line.strip() or len(row.raw_parts) < 8:
                continue

            var_name = row.name
            comment = row.comment

            # 规则 1: 变量名不得含有首尾空白字符
            if var_name != var_name.strip():
                errors.append(f"第 {idx} 行变量名包含多余首尾空格: '{var_name}'")

            # 规则 2: 注释长度合规性检查 (康宁 HMI 报警显示字段长度上限)
            if len(comment) > self.max_comment_len:
                errors.append(f"第 {idx} 行英文注释超出长度限制 ({len(comment)} > {self.max_comment_len}): '{comment}'")

            # 规则 3: 英文交付注释内严禁残留未转义的半角逗号
            if ',' in comment:
                errors.append(f"第 {idx} 行英文注释包含未转义半角逗号 (会导致 CSV 分列冲突): '{comment}'")

        return (len(errors) == 0), errors


# =============================================================================
# 3. 模块级插件声明钩子 (Module Registration Hook)
# =============================================================================

def register_plugins(kernel: Kernel) -> List[BasePlugin]:
    """供 --plugin demo_custom_plugin.py 自动调用的注册入口"""
    p1 = LaserSensorDictionaryPlugin()
    p2 = CorningComplianceRulePlugin()
    kernel.register_plugin(p1)
    kernel.register_plugin(p2)
    return [p1, p2]


# =============================================================================
# 4. 独立运行验证入口 (Demonstration & Verification Runner)
# =============================================================================

def run_demo() -> bool:
    print("======================================================================")
    print(" [DEMO] 第三方扩展插件 SPI 动态注入与质量验收测试")
    print("======================================================================")

    # 1. 创建独立微内核实例
    kernel = Kernel()

    # 2. 动态加载并注册插件
    dict_plugin = LaserSensorDictionaryPlugin()
    verify_plugin = CorningComplianceRulePlugin(max_comment_len=120)
    kernel.register_plugin(dict_plugin)
    kernel.register_plugin(verify_plugin)
    print(f"[*] 已注册词库插件: [{dict_plugin.plugin_id}] (优先级: {dict_plugin.priority})")
    print(f"[*] 已注册质检插件: [{verify_plugin.plugin_id}] (优先级: {verify_plugin.priority})")

    # 3. 测试翻译引擎动态词汇匹配
    sample_texts = [
        "激光测距位移传感器通讯异常",
        "激光测距传感器1#报警",
        "修边刀使用统计",
        "削边深度微调",
    ]
    print("\n--- 1. 词典插件动态翻译验证 ---")
    for text in sample_texts:
        translated = kernel.translate_text(text)
        print(f"  中文: {text:28s} -> 英文: {translated}")
        assert not re.search(r'[\u4e00-\u9fff]', translated), f"翻译残留中文字符: {translated}"

    # 4. 生成临时测试 CSV 文件进行全流程处理与质检
    temp_dir = tempfile.mkdtemp(prefix="plc_plugin_demo_")
    src_csv = os.path.join(temp_dir, "测试工位_变量表.csv")
    dst_en_csv = os.path.join(temp_dir, "测试工位_变量表_EN.csv")
    dst_cn_csv = os.path.join(temp_dir, "测试工位_变量表_CN.csv")

    # 构造符合 InoProShop 标准 9 列结构的测试数据 (GBK 编码 + CRLF 换行)
    sample_csv_content = (
        "序号,变量名,数据类型,隐藏初始值,初始值,掉电保持,网络公开,注释,软元件地址,\r\n"
        "1,Laser_Sensor_1_Error,BOOL,False,False,False,False,激光测距位移传感器通讯异常,,\r\n"
        "2,Laser_Sensor_2_Alarm,BOOL,False,False,False,False,激光测距传感器2#报警,,\r\n"
        "3,Trimmer_Usage_Stat,DINT,False,0,True,False,修边刀使用统计,,\r\n"
        "4,Trimmer_Depth_Adj,REAL,False,0.0,False,False,削边深度微调,,\r\n"
    )
    with open(src_csv, "wb") as f:
        f.write(sample_csv_content.encode('gbk'))

    print("\n--- 2. 表格批量转换与生成 ---")
    processor = VarTableProcessor(mode="B", kernel=kernel)
    records = processor.process_file(src_csv, dst_en_csv, dst_cn_csv)
    print(f"  -> 处理完成，转换记录数: {len(records)} 行")

    print("\n--- 3. 5 重核心断言 + 插件自定义规则自动化质检 ---")
    is_ok, errors = TableVerifier.verify_file(src_csv, dst_en_csv, mode="B", is_var_table=True, kernel=kernel)
    if is_ok:
        print("  [PASS] 5 重核心检测 (行数/CRLF/9列/变量名/0中文) 全部通过！")
        print("  [PASS] 自定义插件规则 [CorningComplianceRulePlugin] 校验通过！")
    else:
        print("  [FAIL] 校验失败:")
        for err in errors:
            print(f"    ! {err}")

    # 清理临时目录
    try:
        for f in os.listdir(temp_dir):
            os.remove(os.path.join(temp_dir, f))
        os.rmdir(temp_dir)
    except Exception:
        pass

    print("\n======================================================================")
    if is_ok:
        print(" [PASS] DEMO CUSTOM PLUGIN DYNAMIC REGISTRATION & VERIFICATION PASSED!")
    else:
        print(" [FAIL] DEMO CUSTOM PLUGIN VERIFICATION FAILED!")
    print("======================================================================\n")
    return is_ok


if __name__ == "__main__":
    success = run_demo()
    sys.exit(0 if success else 1)
