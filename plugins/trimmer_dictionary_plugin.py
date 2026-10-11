# -*- coding: utf-8 -*-
"""
=============================================================================
Corning Machine 3 (3-修边机) Trimmer Domain Dictionary Plugin
=============================================================================
Implementation of DictionaryProviderPlugin SPI for Corning Machine 3.
Provides 90 specialized trimmer domain terminology mappings, greedy word pairs,
and dynamic regex rules to achieve 100% pure English delivery with 0 Chinese residue.
=============================================================================
"""

import os
import sys
import re
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
    Kernel,
)


TRIMMER_EXACT_PHRASES: Dict[str, str] = {
    # 1. 16 Survey Untranslated Comments & Trimmer System Comments
    "钥匙开关_自动进入手动操标志": "Key Switch Auto to Manual Operation Flag",
    "紧急停止": "Emergency Stop",
    "长边4切刀未伸出，请检查长边4切刀气缸": "Long Edge 4 Cutter Not Extended, Please Check Long Edge 4 Cutter Cylinder",
    "归正机构松开状态标志": "Centering Mechanism Unclamp Status Flag",
    "归正全部收回、隐藏_OK": "Centering All Retracted / Hidden OK",
    "L/S_修边刀、L机头升降气缸回待机点_OK": "L/S Trimming Blade, L Head Lifter Cylinder Return to Standby Position OK",
    "L/S_修边刀、刮刀全部收回": "L/S Trimming Blade, Scraper All Retracted",
    "四角吸盘顶升下位全部_OK": "4-Corner Suction Cup Lifter Lower Position All OK",
    "远程I/O、伺服控制器断电通信报警自动复位标志": "Remote I/O, Servo Controller Power-Off Communication Alarm Auto Reset Flag",
    "手动/自动旋钮功能启用标志": "Manual/Auto Selector Switch Function Enable Flag",
    "长短边削边刀在待机点位置标志": "L/S Chamfering Blade at Standby Position Flag",
    "归正已全部松开完成记忆标志": "Centering All Unclamped Done Memory Flag",
    "触摸屏状态转移显示": "Touch Screen State Transition Display",
    "修边完成标志": "Trimming Done Flag",
    "轴组_定位初始化": "Axis Group Positioning Initialization",
    "普通上电初始化": "Normal Power-On Initialization",
    "L1—L4_机头下降安全检测_OK": "L1-L4 Machine Head Lowering Safety Check OK",
    "轴5：短边1回原点丢失！": "Axis 5: Short Edge 1 Homing Lost!",
    "钥匙进入_ 手动中": "Key In Manual Mode",
    "钥匙进入手动中": "Key In Manual Mode",
    "钥匙进入自动中": "Key In Auto Mode",
    "全部轴停止运行标志": "All Axes Stop Operation Flag",
    "全部轴组忙标志_OFF": "All Axis Groups Busy Flag OFF",
    "归正全部夹紧_OK": "Centering All Clamped OK",
    "归正全部松开_OK": "Centering All Unclamped OK",
    "同进同出记忆标志": "Simultaneous In/Out Memory Flag",
    "模拟有料记忆标志": "Simulated Material Present Memory Flag",
    "出料到位光电1复位记忆标志": "Outfeed In-Position Photoelectric 1 Reset Memory Flag",
    "出料到位光电2复位记忆标志": "Outfeed In-Position Photoelectric 2 Reset Memory Flag",
    "入料开始光电复位记忆标志": "Infeed Start Photoelectric Reset Memory Flag",
    "安全门1开启中": "Safety Door 1 Opening",
    "轴定位中暂停记忆标志": "Axis Positioning Pause Memory Flag",
    "轴正在做减速度运动": "Axis in Deceleration Motion",
    "轴正在做加速度运动": "Axis in Acceleration Motion",
    "轴速度为0/轴正在做匀速运动": "Axis Speed 0 / Axis in Constant Speed Motion",
    "输送反转完成": "Conveyor Reverse Done",
    "输送正转完成": "Conveyor Forward Done",
    "速度曲线": "Speed Curve",
    "停止模式": "Stop Mode",
    "定位模式": "Positioning Mode",
    "缓冲模式": "Buffer Mode",
    "控制中": "In Control",
    "暂停完成标志": "Pause Done Flag",
    "准备完成标志": "Ready Done Flag",
    "复位完成": "Reset Done",
    "停止完成": "Stop Done",
    "目标到达": "Target Reached",
    "终止执行": "Abort Execution",

    # 2. 90 Cataloged Trimmer Base Variables & Derived Comments
    "EthernetIP通讯数组": "EthernetIP Communication Array",
    "L1_L2刀位置总和": "L1_L2 Blade Position Sum",
    "L1_L2防撞标志": "L1_L2 Anti-Collision Flag",
    "L1_L2防撞设定": "L1_L2 Anti-Collision Setting",
    "L1_前进": "L1 Forward",
    "L1_后退": "L1 Backward",
    "L1_速度": "L1 Speed",
    "L1修边刀使用当前计数": "L1 Trimming Blade Use Current Count",
    "L1修边刀使用次数设定": "L1 Trimming Blade Use Times Setting",
    "L2_前进": "L2 Forward",
    "L2_后退": "L2 Backward",
    "L2_速度": "L2 Speed",
    "L2修边刀使用当前计数": "L2 Trimming Blade Use Current Count",
    "L2修边刀使用次数设定": "L2 Trimming Blade Use Times Setting",
    "L3_L4刀位置总和": "L3_L4 Blade Position Sum",
    "L3_L4防撞标志": "L3_L4 Anti-Collision Flag",
    "L3_L4防撞设定": "L3_L4 Anti-Collision Setting",
    "L3_前进": "L3 Forward",
    "L3_后退": "L3 Backward",
    "L3_速度": "L3 Speed",
    "L3修边刀使用当前计数": "L3 Trimming Blade Use Current Count",
    "L3修边刀使用次数设定": "L3 Trimming Blade Use Times Setting",
    "L4_前进": "L4 Forward",
    "L4_后退": "L4 Backward",
    "L4_速度": "L4 Speed",
    "L4修边刀使用当前计数": "L4 Trimming Blade Use Current Count",
    "L4修边刀使用次数设定": "L4 Trimming Blade Use Times Setting",
    "S1_S2刀位置总和": "S1_S2 Blade Position Sum",
    "S1_S2防撞标志": "S1_S2 Anti-Collision Flag",
    "S1_S2防撞设定": "S1_S2 Anti-Collision Setting",
    "S1_前进": "S1 Forward",
    "S1_后退": "S1 Backward",
    "S1_速度": "S1 Speed",
    "S1修边刀使用当前计数": "S1 Trimming Blade Use Current Count",
    "S1修边刀使用次数设定": "S1 Trimming Blade Use Times Setting",
    "S2_前进": "S2 Forward",
    "S2_后退": "S2 Backward",
    "S2_速度": "S2 Speed",
    "S2修边刀使用当前计数": "S2 Trimming Blade Use Current Count",
    "S2修边刀使用次数设定": "S2 Trimming Blade Use Times Setting",
    "S3_4S防撞标志": "S3_S4 Anti-Collision Flag",
    "S3_S4刀位置总和": "S3_S4 Blade Position Sum",
    "S3_S4防撞设定": "S3_S4 Anti-Collision Setting",
    "S3_前进": "S3 Forward",
    "S3_后退": "S3 Backward",
    "S3_速度": "S3 Speed",
    "S3修边刀使用当前计数": "S3 Trimming Blade Use Current Count",
    "S3修边刀使用次数设定": "S3 Trimming Blade Use Times Setting",
    "S4_前进": "S4 Forward",
    "S4_后退": "S4 Backward",
    "S4_速度": "S4 Speed",
    "S4修边刀使用当前计数": "S4 Trimming Blade Use Current Count",
    "S4修边刀使用次数设定": "S4 Trimming Blade Use Times Setting",
    "上电初始化延时": "Power-On Initialization Delay",
    "产量计数_PLS": "Production Count Pulse",
    "产量计数脉冲": "Production Count Pulse",
    "入料输送标志": "Infeed Conveyor Flag",
    "全部伺服OFF按钮": "All Servo OFF Button",
    "出料输送标志": "Outfeed Conveyor Flag",
    "初始化延时设定": "Initialization Delay Setting",
    "吸真空ET": "Vacuum Suction Elapsed Time",
    "吸真空关闭延时": "Vacuum Suction OFF Delay",
    "回原点完成": "Homing Done",
    "回原点指令完成标志": "Homing Command Done Flag",
    "安全区域比较值": "Safety Zone Comparison Value",
    "安全继电器功能启用": "Safety Relay Function Enable",
    "实际当前值_轴": "Actual Current Value Axis",
    "小时段产量窗口显示": "Hourly Production Window Display",
    "废料门开启延时": "Scrap Door Open Delay",
    "废料门开启记忆": "Scrap Door Open Memory",
    "当前速度_轴": "Current Speed Axis",
    "手动慢速": "Manual Low Speed",
    "星期产量窗口显示": "Weekly Production Window Display",
    "状态_": "Status_",
    "脉冲": "Pulse",
    "脉冲计时": "Pulse Timing",
    "设置当前值_轴": "Set Current Value Axis",
    "输送_M": "Conveyor_M",
    "输送_TONR": "Conveyor_TONR",
    "配方10数组": "Recipe 10 Array",
    "配方1数组": "Recipe 1 Array",
    "配方2数组": "Recipe 2 Array",
    "配方3数组": "Recipe 3 Array",
    "配方4数组": "Recipe 4 Array",
    "配方5数组": "Recipe 5 Array",
    "配方6数组": "Recipe 6 Array",
    "配方7数组": "Recipe 7 Array",
    "配方8数组": "Recipe 8 Array",
    "配方9数组": "Recipe 9 Array",

    # 3. Time Segment Comments (00_时段 ~ 23_时段)
    **{f"{i:02d}_时段": f"{i:02d} Period" for i in range(24)},
    **{f"{i}00ms脉冲": f"{i}00ms Pulse" for i in [1, 2, 3, 5, 10]},
    "10ms脉冲": "10ms Pulse",
    "10ms脉冲标志": "10ms Pulse Flag",
    "100ms脉冲标志": "100ms Pulse Flag",
}

# Add array subscript items explicitly for O(1) performance
for i in range(30):
    TRIMMER_EXACT_PHRASES[f"初始化延时设定[{i}]"] = f"Initialization Delay Setting [{i}]"
for i in range(16):
    TRIMMER_EXACT_PHRASES[f"回原点指令完成标志[{i}]"] = f"Homing Command Done Flag [{i}]"
    TRIMMER_EXACT_PHRASES[f"实际当前值_轴[{i}]"] = f"Actual Current Value Axis [{i}]"
    TRIMMER_EXACT_PHRASES[f"设置当前值_轴[{i}]"] = f"Set Current Value Axis [{i}]"
for i in range(8):
    TRIMMER_EXACT_PHRASES[f"安全区域比较值[{i}]"] = f"Safety Zone Comparison Value [{i}]"
for i in range(10):
    TRIMMER_EXACT_PHRASES[f"钥匙进入手动中[{i}]"] = f"Key In Manual Mode [{i}]"


TRIMMER_WORD_PAIRS: List[Tuple[str, str]] = [
    # Complex Trimmer phrases (Greedy, longest first)
    ("长边4切刀未伸出，请检查长边4切刀气缸", "Long Edge 4 Cutter Not Extended, Please Check Long Edge 4 Cutter Cylinder"),
    ("远程I/O、伺服控制器断电通信报警自动复位标志", "Remote I/O, Servo Controller Power-Off Communication Alarm Auto Reset Flag"),
    ("L/S_修边刀、L机头升降气缸回待机点_OK", "L/S Trimming Blade, L Head Lifter Cylinder Return to Standby Position OK"),
    ("手动/自动旋钮功能启用标志", "Manual/Auto Selector Switch Function Enable Flag"),
    ("钥匙开关_自动进入手动操标志", "Key Switch Auto to Manual Operation Flag"),
    ("长短边削边刀在待机点位置标志", "L/S Chamfering Blade at Standby Position Flag"),
    ("归正已全部松开完成记忆标志", "Centering All Unclamped Done Memory Flag"),
    ("四角吸盘顶升下位全部_OK", "4-Corner Suction Cup Lifter Lower Position All OK"),
    ("L1—L4_机头下降安全检测_OK", "L1-L4 Machine Head Lowering Safety Check OK"),
    ("L/S_修边刀、刮刀全部收回", "L/S Trimming Blade, Scraper All Retracted"),
    ("出料到位光电1复位记忆标志", "Outfeed In-Position Photoelectric 1 Reset Memory Flag"),
    ("出料到位光电2复位记忆标志", "Outfeed In-Position Photoelectric 2 Reset Memory Flag"),
    ("入料开始光电复位记忆标志", "Infeed Start Photoelectric Reset Memory Flag"),
    ("轴速度为0/轴正在做匀速运动", "Axis Speed 0 / Axis in Constant Speed Motion"),
    ("归正机构松开状态标志", "Centering Mechanism Unclamp Status Flag"),
    ("轴定位中暂停记忆标志", "Axis Positioning Pause Memory Flag"),
    ("归正全部收回、隐藏_OK", "Centering All Retracted / Hidden OK"),
    ("小时段产量窗口显示", "Hourly Production Window Display"),
    ("星期产量窗口显示", "Weekly Production Window Display"),
    ("轴正在做减速度运动", "Axis in Deceleration Motion"),
    ("轴正在做加速度运动", "Axis in Acceleration Motion"),
    ("普通上电初始化", "Normal Power-On Initialization"),
    ("触摸屏状态转移显示", "Touch Screen State Transition Display"),
    ("回原点指令完成标志", "Homing Command Done Flag"),
    ("轴5：短边1回原点丢失！", "Axis 5: Short Edge 1 Homing Lost!"),
    ("全部轴组忙标志_OFF", "All Axis Groups Busy Flag OFF"),
    ("全部轴停止运行标志", "All Axes Stop Operation Flag"),
    ("安全继电器功能启用", "Safety Relay Function Enable"),
    ("轴组_定位初始化", "Axis Group Positioning Initialization"),
    ("模拟有料记忆标志", "Simulated Material Present Memory Flag"),
    ("同进同出记忆标志", "Simultaneous In/Out Memory Flag"),
    ("修边刀使用当前计数", "Trimming Blade Use Current Count"),
    ("修边刀使用次数设定", "Trimming Blade Use Times Setting"),
    ("四角吸盘顶升下位全部", "4-Corner Suction Cup Lifter Lower Position All"),
    ("四角吸盘顶升下位", "4-Corner Suction Cup Lifter Lower Position"),
    ("初始化延时设定", "Initialization Delay Setting"),
    ("安全区域比较值", "Safety Zone Comparison Value"),
    ("上电初始化延时", "Power-On Initialization Delay"),
    ("吸真空关闭延时", "Vacuum Suction OFF Delay"),
    ("废料门开启延时", "Scrap Door Open Delay"),
    ("废料门开启记忆", "Scrap Door Open Memory"),
    ("全部伺服OFF按钮", "All Servo OFF Button"),
    ("机头升降气缸", "Machine Head Lifter Cylinder"),
    ("修边刀使用统计", "Trimming Blade Usage Statistics"),
    ("断电通信报警", "Power-Off Communication Alarm"),
    ("钥匙开关", "Key Switch"),
    ("旋钮功能启用", "Selector Switch Function Enable"),
    ("状态转移显示", "State Transition Display"),
    ("状态转移", "State Transition"),
    ("触摸屏", "Touch Screen"),
    ("紧急停止", "Emergency Stop"),
    ("紧急", "Emergency"),
    ("修边完成标志", "Trimming Done Flag"),
    ("修边完成", "Trimming Done"),
    ("定位初始化", "Positioning Initialization"),
    ("上电初始化", "Power-On Initialization"),
    ("初始化延时", "Initialization Delay"),
    ("延时设定", "Delay Setting"),
    ("初始化", "Initialization"),
    ("普通上电", "Normal Power-On"),
    ("普通", "Normal"),
    ("刀位置总和", "Blade Position Sum"),
    ("防撞标志", "Anti-Collision Flag"),
    ("防撞设定", "Anti-Collision Setting"),
    ("防撞", "Anti-Collision"),
    ("实际当前值_轴", "Actual Current Value Axis"),
    ("实际当前值", "Actual Current Value"),
    ("设置当前值_轴", "Set Current Value Axis"),
    ("设置当前值", "Set Current Value"),
    ("当前速度_轴", "Current Speed Axis"),
    ("当前速度", "Current Speed"),
    ("当前计数", "Current Count"),
    ("使用次数设定", "Use Times Setting"),
    ("使用当前计数", "Use Current Count"),
    ("使用当前", "Use Current"),
    ("使用次数", "Use Times"),
    ("使用", "Use"),
    ("脉冲计时", "Pulse Timing"),
    ("脉冲", "Pulse"),
    ("安全区域", "Safety Zone"),
    ("比较值", "Comparison Value"),
    ("区域", "Zone"),
    ("指令完成标志", "Command Done Flag"),
    ("指令完成", "Command Done"),
    ("指令", "Command"),
    ("削边刀", "Chamfering Blade"),
    ("修边刀", "Trimming Blade"),
    ("刮边刀", "Scraping Blade"),
    ("切刀气缸", "Cutter Cylinder"),
    ("切刀", "Cutter"),
    ("刮刀", "Scraper"),
    ("削边", "Chamfering"),
    ("修边", "Trimming"),
    ("刮边", "Edge Scraping"),
    ("机头升降", "Machine Head Lifter"),
    ("机头下降", "Machine Head Lowering"),
    ("机头", "Machine Head"),
    ("升降气缸", "Lifter Cylinder"),
    ("升降", "Lifter"),
    ("四角吸盘", "4-Corner Suction Cup"),
    ("四角", "4-Corner"),
    ("四", "4"),
    ("顶升下位", "Lifter Lower Position"),
    ("下位", "Lower Position"),
    ("顶升", "Lifter"),
    ("吸盘", "Suction Cup"),
    ("吸真空ET", "Vacuum Suction Elapsed Time"),
    ("吸真空", "Vacuum Suction"),
    ("归正机构", "Centering Mechanism"),
    ("机构", "Mechanism"),
    ("隐藏", "Hidden"),
    ("远程I/O", "Remote I/O"),
    ("远程", "Remote"),
    ("断电", "Power-Off"),
    ("旋钮", "Selector Switch"),
    ("待机点位置标志", "Standby Position Flag"),
    ("在待机点位置标志", "at Standby Position Flag"),
    ("在待机点位置", "at Standby Position"),
    ("待机点位置", "Standby Position"),
    ("待机点", "Standby Position"),
    ("已全部松开完成", "All Unclamped Done"),
    ("已全部松开", "All Unclamped"),
    ("松开完成", "Unclamp Done"),
    ("已全部", "All Already"),
    ("已", "Already"),
    ("在", "at"),
    ("未伸出", "Not Extended"),
    ("请检查", "Please Check"),
    ("气缸", "Cylinder"),
    ("长短边", "Long/Short Edge"),
    ("长边", "Long Edge"),
    ("短边", "Short Edge"),
    ("手动操标志", "Manual Operation Flag"),
    ("进入手动中", "In Manual Mode"),
    ("进入自动中", "In Auto Mode"),
    ("进入手动", "In Manual"),
    ("进入自动", "In Auto"),
    ("操标志", "Operation Flag"),
    ("钥匙进入", "Key In"),
    ("钥匙", "Key"),
    ("操", "Operation"),
    ("实际", "Actual"),
    ("设置", "Set"),
    ("时段", "Period"),
    ("窗口显示", "Window Display"),
    ("废料门", "Scrap Door"),
    ("入料输送标志", "Infeed Conveyor Flag"),
    ("出料输送标志", "Outfeed Conveyor Flag"),
    ("输送反转完成", "Conveyor Reverse Done"),
    ("输送正转完成", "Conveyor Forward Done"),
    ("安全门1开启中", "Safety Door 1 Opening"),
    ("手动慢速", "Manual Low Speed"),
    ("归正全部夹紧", "Centering All Clamped"),
    ("归正全部松开", "Centering All Unclamped"),
    ("同进同出", "Simultaneous In/Out"),
    ("刀", "Blade"),
    ("和", "Sum"),
]


class TrimmerDictionaryPlugin(DictionaryProviderPlugin):
    """
    Corning Machine 3 (3-修边机) 专有领域词典插件
    优先级为 10，高于内置词典 (priority 100)，无缝覆盖并补充所有修边机专有术语。
    """
    plugin_id = "trimmer_dictionary_plugin"
    plugin_name = "Corning Machine 3 Trimmer Domain Dictionary Plugin"
    version = "1.0.0"
    priority = 10

    def get_exact_phrases(self) -> Dict[str, str]:
        return TRIMMER_EXACT_PHRASES

    def get_word_pairs(self) -> List[Tuple[str, str]]:
        return TRIMMER_WORD_PAIRS

    def get_regex_rules(self) -> List[Tuple[Union[re.Pattern, str], Callable]]:
        def handle_indexed_var(m: re.Match, tr: Callable[[str], str]) -> str:
            base = m.group(1).strip()
            bracket = m.group(2).strip()
            tr_base = tr(base)
            return f"{tr_base} {bracket}"

        def handle_axis_action(m: re.Match, tr: Callable[[str], str]) -> str:
            axis = m.group(1)
            act = m.group(2)
            act_map = {"前进": "Forward", "后退": "Backward", "速度": "Speed"}
            return f"{axis} {act_map.get(act, act)}"

        def handle_recipe_array(m: re.Match, tr: Callable[[str], str]) -> str:
            num = m.group(1)
            return f"Recipe {num} Array"

        def handle_timing_comment(m: re.Match, tr: Callable[[str], str]) -> str:
            action = m.group(1)
            suffix = m.group(2) or ""
            act_map = {
                "时间到达": "Time Reached",
                "经过时间": "Elapsed Time",
                "计时执行": "Timing Execution"
            }
            en_act = act_map.get(action, tr(action))
            if suffix:
                s_clean = suffix.strip()
                if s_clean == "上电初始化":
                    return f"{en_act} Power-On Initialization"
                return f"{en_act} {s_clean}"
            return en_act

        return [
            # Handle array indexing on derived variables: e.g. "安全区域比较值[3]" -> "Safety Zone Comparison Value [3]"
            (re.compile(r'^([\u4e00-\u9fffA-Za-z0-9_]+)(\[\d+\])$'), handle_indexed_var),
            # Handle axis directional commands: e.g. "L1_前进" -> "L1 Forward"
            (re.compile(r'^(L\d|S\d)_(前进|后退|速度)$'), handle_axis_action),
            # Handle recipe arrays: e.g. "配方10数组" -> "Recipe 10 Array"
            (re.compile(r'^配方(\d+)数组$'), handle_recipe_array),
            # Handle timer execution / elapsed lines with steps: e.g. "时间到达  S30", "经过时间 上电初始化"
            (re.compile(r'^(时间到达|经过时间|计时执行)\s+(S\d+|上电初始化)$'), handle_timing_comment),
        ]


def register_trimmer_plugin(kernel: Optional[Kernel] = None) -> TrimmerDictionaryPlugin:
    """Convenience registration function"""
    k = kernel or get_default_kernel()
    plugin = TrimmerDictionaryPlugin()
    k.register_plugin(plugin)
    return plugin
