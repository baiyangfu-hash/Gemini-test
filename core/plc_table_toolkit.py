# -*- coding: utf-8 -*-
"""
=============================================================================
PLC Table Toolkit - 工业级微内核与可扩展插件化表格处理套件 (Corning Standard)
=============================================================================
支持：
  1. 微内核 4 层架构：
     - 文件解析层 (TableParserPlugin / GVLTableParser / IOTableParser)
     - 规则与翻译引擎层 (DictionaryProviderPlugin / MultiStageTranslationEngine)
     - 格式化导出层 (TableExporterPlugin / GVLCsvExporter / MarkdownReportExporter)
     - 质量验收层 (PostVerifyRulePlugin / TableVerifier 5-Fold Checks)
  2. 插件化系统 (SPI/Hook/Registry)：
     - 支持外部第三方 IDE、HMI 与 CI/CD 插件动态扩展
     - 支持动态注入自定义字典源、解析器与后置校验规则
  3. 100% 向后兼容性：
     - Python API 兼容门面: VarTableProcessor, IOTableProcessor, IndustrialTermEngine, TableVerifier
     - CLI 命令兼容: vars, io, verify, machine 及新增 --plugin / --plugins-dir 参数
  4. 工业级数据保真：
     - 严格保持 GBK/CP936 编码、Windows CRLF (\\r\\n) 换行符与标准 9 列 CSV 结构
     - 逗号/分号防错位清洗与 100% 纯英文 0 中文残留交付
"""

import os
import sys
import re
import abc
import argparse
import importlib.util
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional, Any, Callable, Type, Union

# Ensure standard UTF-8 console output when possible
try:
    if sys.stdout.encoding != 'utf-8':
        sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass


# =============================================================================
# 1. 规范化内存数据模型 (Canonical In-Memory Data Models)
# =============================================================================

@dataclass
class TableRow:
    """标准表格行内存对象 (兼容 GVL 9 列结构与 IO 注释结构)"""
    no: str = ""                         # 序号 (Col 0)
    name: str = ""                       # 变量名 / 软元件地址 (Col 1 或 Col 0)
    data_type: str = ""                  # 数据类型 (Col 2)
    init_hide: str = ""                  # 隐藏初始值 (Col 3)
    init_val: str = ""                   # 初始值 (Col 4)
    retain: str = ""                     # 掉电保持 (Col 5)
    publish: str = ""                    # 网络公开 (Col 6)
    comment: str = ""                    # 原始注释 (Col 7 或 Col 1)
    addr: str = ""                       # 软元件地址 / 附加列 (Col 8)
    raw_parts: List[str] = field(default_factory=list)  # 原始拆分 token
    raw_line: str = ""                   # 原始未拆分行文本
    extra: Dict[str, Any] = field(default_factory=dict) # 扩展上下文属性


@dataclass
class TableDocument:
    """标准表格文档对象 (内存中间表现模型)"""
    file_path: str = ""
    table_type: str = "var"              # 'var' (GVL 变量表) 或 'io' (IO 注释表)
    headers: List[str] = field(default_factory=list)
    rows: List[TableRow] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    raw_lines: List[str] = field(default_factory=list)


# =============================================================================
# 2. 插件服务提供者接口 (Plugin Service Provider Interfaces - SPI)
# =============================================================================

class BasePlugin(abc.ABC):
    """所有插件的抽象扩展基类"""
    plugin_id: str = "base_plugin"
    plugin_name: str = "Base Plugin"
    version: str = "1.0.0"
    priority: int = 100  # 优先级数值越小，执行优先级越高 (如 10 优于 100)

    def on_load(self, kernel: "Kernel") -> None:
        """插件加载并注入微内核上下文时的生命周期钩子"""
        pass

    def initialize(self, config: Optional[Dict[str, Any]] = None) -> None:
        """插件初始化配置钩子"""
        pass

    def on_unload(self) -> None:
        """插件卸载清理钩子"""
        pass


class TableParserPlugin(BasePlugin):
    """表格文件解析器插件抽象接口"""

    @abc.abstractmethod
    def can_parse(self, file_path: str, raw_bytes: bytes = b"") -> bool:
        """判断是否能处理给定的源文件"""
        pass

    @abc.abstractmethod
    def parse(self, file_path: str, encoding: str = "gbk") -> TableDocument:
        """将源文件解析为标准的 TableDocument 内存对象"""
        pass


class DictionaryProviderPlugin(BasePlugin):
    """工业电气术语词典与规则提供者插件接口"""

    @abc.abstractmethod
    def get_exact_phrases(self) -> Dict[str, str]:
        """返回精确全词匹配映射字典 {中文: 英文}"""
        pass

    @abc.abstractmethod
    def get_word_pairs(self) -> List[Tuple[str, str]]:
        """返回多词素贪婪子串替换对列表 [(中文, 英文), ...]"""
        pass

    @abc.abstractmethod
    def get_regex_rules(self) -> List[Tuple[Union[re.Pattern, str], Callable[[re.Match, Callable[[str], str]], Optional[str]]]]:
        """返回动态正则规则列表: [(pattern, handler_func(match, translate_fn))]"""
        pass


class TableExporterPlugin(BasePlugin):
    """表格导出序列化器插件接口"""

    @abc.abstractmethod
    def can_export(self, format_name: str) -> bool:
        """判断是否支持该导出格式"""
        pass

    @abc.abstractmethod
    def export(self, doc: TableDocument, output_path: str, **kwargs) -> None:
        """将 TableDocument 序列化并保存至磁盘"""
        pass


class PostVerifyRulePlugin(BasePlugin):
    """后置质量验收与断言扩展规则插件接口"""

    @abc.abstractmethod
    def verify(self, src_path: str, tgt_path: str, doc: TableDocument, context: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """执行自定义质量校验断言，返回 (是否通过, 错误信息列表)"""
        pass


# =============================================================================
# 3. 核心内置工业术语词库 (IEC / PLCopen / Corning Built-in Terminology)
# =============================================================================

BUILTIN_EXACT_PHRASES: Dict[str, str] = {
    # Motion control & Function Blocks
    "Group_加速度": "Group Acceleration",
    "Group_目标位置": "Group Target Position",
    "Group_目标速度": "Group Target Speed",
    "ABS加速度": "ABS Acceleration",
    "ABS减速度": "ABS Deceleration",
    "ABS目标位置": "ABS Target Position",
    "ABS目标速度": "ABS Target Speed",
    "ABS定位启动": "ABS Positioning Start",
    "ABS定位中": "ABS Positioning Active",
    "ABS定位完成": "ABS Positioning Done",
    "ABS报错": "ABS Error",
    "ABS错误代码": "ABS Error Code",
    "REL加速度": "REL Acceleration",
    "REL减速度": "REL Deceleration",
    "REL目标位置": "REL Target Position",
    "REL目标速度": "REL Target Speed",
    "REL定位启动": "REL Positioning Start",
    "REL定位中": "REL Positioning Active",
    "REL定位完成": "REL Positioning Done",
    "REL中断执行": "REL Abort Execution",
    "REL报错": "REL Error",
    "REL错误代码": "REL Error Code",
    
    # Timers & Counters
    "预设定时": "Preset Time",
    "计时器复位": "Timer Reset",
    "经过时间": "Elapsed Time",
    "计时执行": "Timing Execution",
    "时间到达": "Time Reached",
    "计时器": "Timer",
    
    # Flags & Execution
    "忙标志": "Busy Flag",
    "繁忙标志": "Busy Flag",
    "目标转矩": "Target Torque",
    "目标斜坡率": "Target Ramp Rate",
    "力矩到达": "Torque Reached",
    "速度限制": "Speed Limit",
    "故障标志": "Fault Flag",
    "故障代码": "Fault Code",
    "故障码": "Fault Code",
    "减速度": "Deceleration",
    "加速度": "Acceleration",
    "指令故障标志": "Instruction Fault Flag",
    "指令执行": "Instruction Execution",
    "完成标志": "Done Flag",
    "终止执行标志": "Abort Execution Flag",
    "力矩指令执行": "Torque Instruction Execution",
    "中断标志": "Command Aborted Flag",
    "错误标志": "Error Flag",
    "错误代码": "Error Code",
    "中断执行": "Abort Execution",
    "原点到达时的位置": "Position at Origin Reached",
    "停止忙中": "Stop Busy",
    "使能执行": "Enable Execution",
    "轴使能标志": "Axis Enable Flag",
    "复位中": "Resetting Active",
    
    # PLCopen State Machine
    "PLCOpen状态机，去使能": "PLCopen State Machine: Disabled",
    "PLCOpen状态机，故障停机": "PLCopen State Machine: ErrorStop",
    "PLCOpen状态机，停止运行": "PLCopen State Machine: Stopping",
    "PLCOpen状态机，使能且非运行状态": "PLCopen State Machine: Standstill",
    "PLCOpen状态机，点位运行模式": "PLCopen State Machine: DiscreteMotion",
    "PLCOpen状态机，连续运行模式": "PLCopen State Machine: ContinuousMotion",
    "PLCOpen状态机，同步运行模式": "PLCopen State Machine: SynchronizedMotion",
    "PLCOpen状态机，原点回归模式": "PLCopen State Machine: Homing",
    
    # System Constants & Keywords
    "三班产量": "3-Shift Production",
    "产量计数_PLS": "Production Count Pulse",
    "全部轴组_Busy_OFF状态": "All Axis Groups Busy OFF Status",
    "安全继电器功能启用": "Safety Relay Function Enable",
    "常开触点 (SM400)": "Always ON Contact (SM400)",
    "sm400": "Always ON Contact (SM400)",
    "配方地址变址寄存器": "Recipe Address Index Register",
    "减速曲线类型：0，T型；1，S型": "Decel Curve Type: 0 = T-Curve / 1 = S-Curve",
    "加速曲线类型：0，T型；1，S型": "Accel Curve Type: 0 = T-Curve / 1 = S-Curve",
    "曲线类型：0，T型；1，S型": "Curve Type: 0 = T-Curve / 1 = S-Curve",
    "减速曲线类型：0，T型;1，S型": "Decel Curve Type: 0 = T-Curve / 1 = S-Curve",
    "加速曲线类型：0，T型;1，S型": "Accel Curve Type: 0 = T-Curve / 1 = S-Curve",
    "三班倒设置": "3-Shift Setting",
    "报警自动复位动作记忆标志": "Alarm Auto Reset Action Memory Flag",
    "PLC时钟读出": "PLC Clock Readout",
    "PLC时钟写入": "PLC Clock Write",
    "报警": "Alarm",
    "准备完成": "Ready Completed",
    "轴组0插补定位数据": "Axis Group 0 Interpolation Positioning Data",
    "轴组1插补定位数据": "Axis Group 1 Interpolation Positioning Data",
    "轴组2插补定位数据": "Axis Group 2 Interpolation Positioning Data",
    "轴组3插补定位数据": "Axis Group 3 Interpolation Positioning Data",
    "轴组4插补定位数据": "Axis Group 4 Interpolation Positioning Data",
    "轴组5插补定位数据": "Axis Group 5 Interpolation Positioning Data",
    "轴组6插补定位数据": "Axis Group 6 Interpolation Positioning Data",
    "轴组7插补定位数据": "Axis Group 7 Interpolation Positioning Data",
    # Trimmer & Machine 3 delivery keywords
    "准备执行": "Preparation Execution",
    "系统准备": "System Preparation",
    "系统准备完成": "System Preparation Done",
    "系统准备完成标志": "System Preparation Done Flag",
    "急停按钮输入": "Emergency Stop Button Input",
    "急停按钮": "Emergency Stop Button",
    "急停": "Emergency Stop",
    "当前班次产量": "Current Shift Production",
    "产量清零触发": "Production Clear Trigger",
    "轴1指令位置": "Axis 1 Command Position",
    "修边刀上升到位": "Trimming Cutter Up In-Position",
    "修边刀使用统计": "Trimming Cutter Usage Statistics",
    "报警指示灯输出": "Alarm Indicator Light Output",
}

BUILTIN_WORD_PAIRS: List[Tuple[str, str]] = [
    ("温度设定", "Temperature Setting"),
    ("温度", "Temperature"),
    ("旋转角度", "Rotation Angle"),
    ("角度", "Angle"),
    ("公差", "Tolerance"),
    ("严重", "Severe"),
    ("修边刀使用统计", "Trimming Cutter Usage Statistics"),
    ("修边刀上升到位", "Trimming Cutter Up In-Position"),
    ("修边刀伺服", "Trimming Cutter Servo"),
    ("修边刀", "Trimming Cutter"),
    ("削边刀", "Trimming Cutter"),
    ("刮边刀", "Scraping Cutter"),
    ("刮刀", "Scraping Cutter"),
    ("修边", "Trimming"),
    ("削边", "Trimming"),
    ("刮边", "Edge Scraping"),
    ("切刀", "Cutter"),
    ("急停按钮", "Emergency Stop Button"),
    ("指示灯", "Indicator Light"),
    ("输入", "Input"),
    ("输出", "Output"),
    ("电机", "Motor"),
    ("准备执行", "Preparation Execution"),
    ("系统准备", "System Preparation"),
    ("当前班次", "Current Shift"),
    ("清零触发", "Clear Trigger"),
    ("指令位置", "Command Position"),
    ("刀", "Cutter"),
    ("削", "Trim"),
    ("刮", "Scrape"),
    ("修", "Trim"),
    ("轴组0插补定位数据", "Axis Group 0 Interpolation Positioning Data"),
    ("轴组1插补定位数据", "Axis Group 1 Interpolation Positioning Data"),
    ("轴组2插补定位数据", "Axis Group 2 Interpolation Positioning Data"),
    ("轴组3插补定位数据", "Axis Group 3 Interpolation Positioning Data"),
    ("轴组4插补定位数据", "Axis Group 4 Interpolation Positioning Data"),
    ("轴组5插补定位数据", "Axis Group 5 Interpolation Positioning Data"),
    ("轴组6插补定位数据", "Axis Group 6 Interpolation Positioning Data"),
    ("轴组7插补定位数据", "Axis Group 7 Interpolation Positioning Data"),
    ("累计数量", "Total Count"),
    ("累计数", "Total Count"),
    ("累计", "Total"),
    ("插补", "Interpolation"),
    ("累", "Total"),
    ('废料箱废料已满请清理', 'Waste Box Full Please Clean Up'),
    ('自动运行步进状态字', 'Auto Run Stepping Status Word'),
    ('轴力矩模式定位数据', 'Axis Torque Mode Positioning Data'),
    ('点动慢速切换比较值', 'JOG Slow Speed Switch Comparison Value'),
    ('回捋胶带起始点速度', 'Return Peeling Stroke Start Point Speed'),
    ('清废料报警提醒计数', 'Clear Waste Alarm Prompt Count'),
    ('长短边机头脱料计数', 'L/S Head Stripping Count'),
    ('废料已清理记忆标志', 'Waste Cleared Memory Flag'),
    ('轴插补定位判断选择', 'Axis Interpolation Positioning Decision Select'),
    ('插补附加角定位数据', 'Interpolation Additional Angle Positioning Data'),
    ('回撕胶带起始点速度', 'Return Peeling Start Point Speed'),
    ('断带判断区域起始点', 'Tape Break Decision Zone Start Point'),
    ('组件不良统计数量', 'Module Defect Statistics Count'),
    ('回捋胶带起始速度', 'Return Peeling Stroke Start Speed'),
    ('撕胶带起始点速度', 'Tape Peeling Start Point Speed'),
    ('断带判断区域终点', 'Tape Break Decision Zone End Point'),
    ('没转换手动位置上', 'Not Switched to Manual Position'),
    ('轴撕胶带断掉报警', 'Axis Tape Peeling Break Alarm'),
    ('没转换自动位置上', 'Not Switched to Auto Position'),
    ('长短边捋胶带开始', 'L/S Tape Peeling Stroke Start'),
    ('轴未缩回到安全位', 'Axis Not Retracted to Safe Position'),
    ('废料报警复位计时', 'Waste Alarm Reset Timer'),
    ('捋胶回待机点速度', 'Return to Standby Position Speed'),
    ('同进同出记忆标志', 'Simultaneous In/Out Memory Flag'),
    ('长短边撕胶带未成', 'L/S Tape Peeling Incomplete'),
    ('轴撕胶带速度限制', 'Axis Tape Peeling Speed Limit'),
    ('轴旋转圈数累计数', 'Axis Rotation Turns Total Count'),
    ('星期产量窗口显示', 'Weekly Production Window Display'),
    ('捋胶带起始点速度', 'Tape Peeling Stroke Start Point Speed'),
    ('入料输送超时报警', 'Infeed Conveyor Timeout Alarm'),
    ('轴在待机点标志', 'Axis at Standby Position Flag'),
    ('慢速切换比较值', 'Slow Speed Switch Comparison Value'),
    ('轴旋转原点开关', 'Axis Rotation Origin Switch'),
    ('轴强行收卷标志', 'Axis Forced Winding Flag'),
    ('机头脱废料下位', 'Head Waste Stripping Down Position'),
    ('清废料报警标志', 'Clear Waste Alarm Flag'),
    ('长短边机头上升', 'L/S Head Up'),
    ('回捋胶带起始点', 'Return Peeling Stroke Start Point'),
    ('轴捋胶带起始点', 'Axis Tape Peeling Stroke Start Point'),
    ('回撕胶带起始点', 'Return Peeling Start Point'),
    ('机头脱废料上位', 'Head Waste Stripping Up Position'),
    ('玻璃未入料到位', 'Glass Infeed Not In-Position'),
    ('推废料收集计数', 'Push Waste Collection Count'),
    ('轴捋胶带终点', 'Axis Tape Peeling Stroke End Point'),
    ('不良统计数量', 'Defect Statistics Count'),
    ('绝对定位指令', 'Absolute Positioning Command'),
    ('归正步进流程', 'Centering Stepping Sequence'),
    ('机头在待机点', 'Head at Standby Position'),
    ('脱料气缸计数', 'Stripping Cylinder Count'),
    ('自动钥匙开关', 'Auto Key Switch'),
    ('撕胶带起始点', 'Tape Peeling Start Point'),
    ('入料输送计时', 'Infeed Conveyor Timer'),
    ('入料开始光电', 'Infeed Start Photoelectric'),
    ('空载报警力矩', 'No-Load Alarm Torque'),
    ('出料输送计时', 'Outfeed Conveyor Timer'),
    ('转成的浮点数', 'Converted Float'),
    ('位置定位数据', 'Position Positioning Data'),
    ('轴组定位指令', 'Axis Group Positioning Command'),
    ('输送周期时间', 'Conveyor Cycle Time'),
    ('速度定位数据', 'Speed Positioning Data'),
    ('无异常再复位', 'Reset Only After Clearing Fault'),
    ('轴捋胶带起点', 'Axis Tape Peeling Stroke Start Point'),
    ('捋胶带起始点', 'Tape Peeling Stroke Start Point'),
    ('软启阀报警', 'Soft Start Valve Alarm'),
    ('轴回待机点', 'Axis Return to Standby Position'),
    ('上电初始化', 'Power-On Init'),
    ('步进状态号', 'Stepping Status No.'),
    ('撕胶带终点', 'Tape Peeling End Point'),
    ('轴定位完成', 'Axis Positioning Done'),
    ('捋胶带终点', 'Tape Peeling Stroke End Point'),
    ('准备未完成', 'Ready Incomplete'),
    ('撕胶带计时', 'Tape Peeling Timer'),
    ('计时器复位', 'Timer Reset'),
    ('数据轴定位', 'Data Axis Positioning'),
    ('不停机报警', 'Non-Stop Alarm'),
    ('速度轴定位', 'Speed Axis Positioning'),
    ('转成浮点数', 'Convert to Float'),
    ('计时执行', 'Timing Execution'),
    ('终止执行', 'Abort Execution'),
    ('不良统计', 'Defect Statistics'),
    ('输送计时', 'Conveyor Timer'),
    ('缓冲模式', 'Buffer Mode'),
    ('脱料计数', 'Stripping Count'),
    ('检测异常', 'Detection Error'),
    ('停机报警', 'Stop Alarm'),
    ('预设定时', 'Preset Time'),
    ('速度曲线', 'Speed Profile'),
    ('经过时间', 'Elapsed Time'),
    ('时间到达', 'Time Reached'),
    ('定位数据', 'Positioning Data'),
    ('轴未使能', 'Axis Not Enabled'),
    ('定位模式', 'Positioning Mode'),
    ('指令执行', 'Instruction Execution'),
    ('百分比', 'Percentage'),
    ('附加角', 'Additional Angle'),
    ('定位忙', 'Positioning Busy'),
    ('长短边', 'L/S Edges'),
    ('长边短', 'L/S'),
    ('请确认', 'Please Confirm'),
    ('软启阀', 'Soft Start Valve'),
    ('旋转', 'Rotation'),
    ('圈数', 'Turns'),
    ('收卷', 'Winding'),
    ('强行', 'Forced'),
    ('脱料', 'Stripping'),
    ('切换', 'Switch'),
    ('变址', 'Index'),
    ('开关', 'Switch'),
    ('计数', 'Count'),
    ('准备', 'Ready'),
    ('短边', 'Short Edge'),
    ('状态', 'Status'),
    ('异常', 'Abnormal'),
    ('手动', 'Manual'),
    ('长边', 'Long Edge'),
    ('繁忙', 'Busy'),
    ('报错', 'Error'),
    ('轴组', 'Axis Group'),
    ('统计', 'Statistics'),
    ('轴', 'Axis'),
    ('手', 'Manual'),
    ('脱', 'Strip'),
    ('卷', 'Reel'),
    ('废', 'Waste'),
    ("轴断带判断力矩超出撕胶带设定力矩值", "Axis Tape Break Detection Torque Exceeds Peeling Set Value"),
    ("长短边机头捋胶带平移气缸伸出", "L/S Head Tape Peeling Shift Cylinder Extend"),
    ("长短边撕胶带断掉综合报警标志", "L/S Tape Peeling Break Combined Alarm Flag"),
    ("长短边机头定位数据寄存器变址", "L/S Head Positioning Data Register Index"),
    ("轴断带判断力矩重新检测计数", "Axis Tape Break Detection Torque Re-detection Count"),
    ("轴捋胶带提前预置位完成标志", "Axis Tape Peeling Advance Preset Done Flag"),
    ("入料开始光电复位记忆标志", "Infeed Start Photoelectric Reset Memory Flag"),
    ("下游线体出料请求信号中断", "Downstream Line Outfeed Request Interrupted"),
    ("轴撕胶带起头快速定位数据", "Axis Tape Peeling Lead Fast Positioning Data"),
    ("请检查进出料输送是否异常", "Please Check Infeed/Outfeed Conveyor"),
    ("请检查机构是否有卡顿现象", "Please Check Mechanism for Jamming"),
    ("轴回原点指令打断记忆标志", "Axis Homing Command Interrupted Memory Flag"),
    ("轴撕胶带起头慢速定位数据", "Axis Tape Peeling Lead Slow Positioning Data"),
    ("撕胶带力矩设置太小报警", "Tape Peeling Torque Setting Too Low Alarm"),
    ("轴力矩指令打断记忆标志", "Axis Torque Command Interrupted Memory Flag"),
    ("短边速度运算临时寄出器", "Short Edge Speed Calculation Temp Register"),
    ("短边速度运算临时寄存器", "Short Edge Speed Calculation Temp Register"),
    ("长边速度运算临时寄存器", "Long Edge Speed Calculation Temp Register"),
    ("轴后位门型光电检测异常", "Axis Rear Slot Photoelectric Error"),
    ("轴教点反转标定动作标志", "Axis Teach Point REV Calibration Action Flag"),
    ("轴空转力矩检测完成标志", "Axis Idling Torque Detection Done Flag"),
    ("回原点扭力到达记忆标志", "Homing Torque Reached Memory Flag"),
    ("轴空卷料力矩设定比较值", "Axis Empty Reel Torque Setting Comparison Value"),
    ("轴原点门型光电检测异常", "Axis Origin Slot Photoelectric Error"),
    ("自动运行步进待机中状态", "Auto Run Stepping Standby Active Status"),
    ("模拟回应下游出料可标志", "Simulated Downstream Outfeed Permit Flag"),
    ("模拟回应上游入料可标志", "Simulated Upstream Infeed Permit Flag"),
    ("全部轴定位中断暂停状态", "All Axes Positioning Aborted Pause Status"),
    ("轴回预置安全比较点速度", "Axis Return Preset Safe Comparison Point Speed"),
    ("轴预置安全比较点速度", "Axis Preset Safe Comparison Point Speed"),
    ("废料箱废料已满请清理", "Waste Box Full Please Clean Up"),
    ("撕胶带起始点定位数据", "Tape Peeling Start Point Positioning Data"),
    ("撕胶带机头下降位异常", "Tape Peeling Head Down Position Error"),
    ("撕胶带机头上升位异常", "Tape Peeling Head Up Position Error"),
    ("长短边机头捋胶带夹紧", "L/S Head Tape Peeling Clamp"),
    ("请检查机构是否有卡顿", "Please Check Mechanism for Jamming"),
    ("断带力矩判断动作标志", "Tape Break Torque Decision Action Flag"),
    ("轴捋胶带伸出教点超出", "Axis Tape Peeling Extend Teach Point Exceeded"),
    ("组件今天良品累计数量", "Module Today Good Total Count"),
    ("组件昨天良品累计数量", "Module Yesterday Good Total Count"),
    ("组件生产良品累计数量", "Module Production Good Total Count"),
    ("组件今天不良累计数量", "Module Today NG Total Count"),
    ("组件昨天不良累计数量", "Module Yesterday NG Total Count"),
    ("撕胶带起头松胶带回撤", "Tape Peeling Lead Release Tape Retract"),
    ("长短废料收集门磁检测", "L/S Waste Collection Door Switch Detection"),
    ("长短边废料收集门磁检测", "L/S Waste Collection Door Switch Detection"),
    ("轴回原点扭力到达标志", "Axis Homing Torque Reached Flag"),
    ("未检测胶带头累计数量", "Undetected Tape Leader Total Count"),
    ("轴撕胶带断带动作标志", "Axis Tape Peeling Break Action Flag"),
    ("轴空转力矩重教标志", "Axis Idling Torque Re-Teach Flag"),
    ("全部定位轴暂停状态", "All Positioning Axes Pause Status"),
    ("入料侧阻挡顶升下位", "Infeed Side Stopper Lifter Down Position"),
    ("入料侧阻挡顶升上位", "Infeed Side Stopper Lifter Up Position"),
    ("短边撕胶带断料报警", "Short Edge Tape Peeling Runout Alarm"),
    ("长边撕胶带断料报警", "Long Edge Tape Peeling Runout Alarm"),
    ("小时段产量窗口显示", "Hourly Production Window Display"),
    ("产量统计区间时间段", "Production Statistics Interval Period"),
    ("小时转秒为单位", "Hours to Seconds Conversion"),
    ("断带报警NG数量减一记忆标志", "Broken Tape NG Count Minus 1 Flag"),
    ("远程I/O模块链接异常", "Remote I/O Module Link Error"),
    ("减速曲线类型", "Deceleration Curve Type"),
    ("加速曲线类型", "Acceleration Curve Type"),
    ("曲线类型", "Curve Type"),
    ("断带比较力矩", "Tape Break Comparison Torque"),
    ("空转力矩读取值", "Idling Torque Read Value"),
    ("断带检测起始点", "Tape Break Detection Start Point"),
    ("断带检测起终点", "Tape Break Detection End Point"),
    ("空卷料力矩设定", "Empty Reel Torque Setting"),
    ("短边1机头准备寄存器变址", "S1 Head Ready Register Index"),
    ("短边2机头准备寄存器变址", "S2 Head Ready Register Index"),
    ("长边1机头准备寄存器变址", "L1 Head Ready Register Index"),
    ("长边2机头准备寄存器变址", "L2 Head Ready Register Index"),
    ("插补附加角", "Interpolation Additional Angle"),
    ("附加角", "Additional Angle"),
    ("附加", "Additional"),
    ("百分比", "Percentage"),
    ("代码", "Code"),
    ("伺服", "Servo"),
    ("时钟", "Clock"),
    ("脉冲", "Pulse"),
    ("丢失", "Loss"),
    ("开启", "Open"),
    ("判断", "Decision"),
    ("操作", "Operation"),
    ("突出光电", "Protrusion Photoelectric"),
    ("突出", "Protrusion"),
    ("强制", "Forced"),
    ("多圈", "Multi-Turn"),
    ("消除", "Clear"),
    ("地址", "Address"),
    ("过载", "Overload"),
    ("控制", "Control"),
    ("待机", "Standby"),
    ("按钮", "Button"),
    ("钥匙", "Key Switch"),
    ("就绪", "Ready"),
    ("有玻璃", "Glass Present"),
    ("玻璃", "Glass"),
    ("提醒", "Prompt"),
    ("生产", "Production"),
    ("绝对", "Absolute"),
    ("变频", "Inverter"),
    ("频率", "Frequency"),
    ("毫秒", "Millisecond"),
    ("星期", "Day of Week"),
    ("寄存器变址", "Register Index"),
    ("变址", "Index"),
    ("安全继电器", "Safety Relay"),
    ("断带检测", "Tape Break Detection"),
    ("同步调整", "Sync Adjustment"),
    ("良率统计", "Yield Statistics"),
    ("良率", "Yield"),
    ("产量统计", "Production Statistics"),
    ("产量计数", "Production Count"),
    ("常开触点", "Normally-Open Contact"),
    ("轴使能", "Axis Enable"),
    ("轴正在做减速度运动", "Axis Decelerating"),
    ("轴正在做加速度运动", "Axis Accelerating"),
    ("轴速度为0/轴正在做匀速运动", "Axis Speed 0 / Constant Speed"),
    ("阻挡顶升", "Stopper Lifter"),
    ("从站", "Slave"),
    ("通讯异常", "Comm Error"),
    ("链接异常", "Link Error"),
    ("光电检测", "Photoelectric Detection"),
    ("门型光电", "Slot Photoelectric"),
    ("插补定位", "Interpolation Positioning"),
    ("插补启动", "Interpolation Start"),
    ("插补暂停", "Interpolation Pause"),
    ("插补停止", "Interpolation Stop"),
    ("定位完成", "Positioning Done"),
    ("定位启动", "Positioning Start"),
    ("定位中", "Positioning Active"),
    ("待机点", "Standby Position"),
    ("回待机点", "Return to Standby Position"),
    ("待机位", "Standby Position"),
    ("回待机位", "Return to Standby Position"),
    ("准备OK标志", "Ready OK Flag"),
    ("准备完成", "Ready Completed"),
    ("回原点", "Homing"),
    ("原点", "Origin"),
    ("软极限", "Soft Limit"),
    ("硬极限", "Hard Limit"),
    ("正极限", "Positive Limit"),
    ("负极限", "Negative Limit"),
    ("正限定值", "Positive Limit Value"),
    ("负限定值", "Negative Limit Value"),
    ("正限", "Positive Limit"),
    ("负限", "Negative Limit"),
    ("正向", "FWD"),
    ("反向", "REV"),
    ("正转", "FWD"),
    ("反转", "REV"),
    ("点动", "JOG"),
    ("微调", "Fine Tuning"),
    ("慢速", "Slow Speed"),
    ("快速", "Fast Speed"),
    ("速度", "Speed"),
    ("位置", "Position"),
    ("扭矩", "Torque"),
    ("力矩", "Torque"),
    ("扭力", "Torque"),
    ("脉冲", "Pulse"),
    ("延时", "Delay"),
    ("超时", "Timeout"),
    ("经过", "Elapsed"),
    ("预设", "Preset"),
    ("预置", "Preset"),
    ("复位", "Reset"),
    ("清除", "Clear"),
    ("清零", "Clear"),
    ("启动", "Start"),
    ("停止", "Stop"),
    ("暂停", "Pause"),
    ("急停", "E-Stop"),
    ("故障", "Fault"),
    ("错误", "Error"),
    ("报警", "Alarm"),
    ("警告", "Warning"),
    ("异常", "Abnormal"),
    ("使能", "Enable"),
    ("去使能", "Disable"),
    ("状态", "Status"),
    ("标志", "Flag"),
    ("记忆", "Memory"),
    ("动作", "Action"),
    ("模式", "Mode"),
    ("步序", "Step"),
    ("步进", "Stepping"),
    ("自动", "Auto"),
    ("手动", "Manual"),
    ("准备", "Ready"),
    ("运行", "Running"),
    ("执行", "Execute"),
    ("中断", "Abort"),
    ("打断", "Interrupt"),
    ("气缸", "Cylinder"),
    ("电磁阀", "Solenoid Valve"),
    ("感应器", "Sensor"),
    ("传感器", "Sensor"),
    ("光电", "Photoelectric"),
    ("真空", "Vacuum"),
    ("破真空", "Vacuum Blow"),
    ("吸真空", "Vacuum On"),
    ("吸嘴", "Suction Cup"),
    ("吸盘", "Suction Cup"),
    ("输送", "Conveyor"),
    ("出料", "Outfeed"),
    ("入料", "Infeed"),
    ("上料", "Loading"),
    ("下料", "Unloading"),
    ("归正", "Centering"),
    ("换型", "Model Change"),
    ("长边1", "L1"),
    ("长边2", "L2"),
    ("短边1", "S1"),
    ("短边2", "S2"),
    ("长边", "Long Edge"),
    ("短边", "Short Edge"),
    ("长短边", "L/S Edges"),
    ("长1", "L1"),
    ("长2", "L2"),
    ("短1", "S1"),
    ("短2", "S2"),
    ("撕胶带机", "Tape Peeling Machine"),
    ("撕胶带", "Tape Peeling"),
    ("贴胶带", "Tape Apply"),
    ("捋胶带", "Tape Peeling Stroke"),
    ("回捋", "Return Peeling Stroke"),
    ("捋带", "Tape Peeling Stroke"),
    ("压带", "Tape Pressing"),
    ("送带", "Tape Feeding"),
    ("收带", "Tape Reeling"),
    ("卷带", "Tape Winding"),
    ("断带", "Broken Tape"),
    ("断料", "Material Runout"),
    ("胶带头", "Tape Leader"),
    ("胶带", "Tape"),
    ("废料", "Waste"),
    ("废料箱", "Waste Box"),
    ("收集", "Collection"),
    ("门磁", "Door Switch"),
    ("安全门", "Safety Door"),
    ("安全", "Safety"),
    ("防撞", "Anti-Collision"),
    ("屏蔽", "Mask"),
    ("组件", "Module"),
    ("不良品", "Defect"),
    ("良品", "Good"),
    ("不良", "NG"),
    ("累计", "Total"),
    ("数量", "Count"),
    ("比例", "Ratio"),
    ("今天", "Today"),
    ("昨天", "Yesterday"),
    ("班次", "Shift"),
    ("三班", "3-Shift"),
    ("星期", "Day of Week"),
    ("小时", "Hour"),
    ("时段", "Period"),
    ("分", "Minute"),
    ("秒", "Second"),
    ("时", "Hour"),
    ("时钟", "Clock"),
    ("读出", "Readout"),
    ("写入", "Write"),
    ("配方", "Recipe"),
    ("数据", "Data"),
    ("寄存器", "Register"),
    ("寄存", "Register"),
    ("寄出器", "Register"),
    ("地址", "Address"),
    ("当前", "Current"),
    ("设定", "Setting"),
    ("目标", "Target"),
    ("比较", "Comparison"),
    ("上限", "Upper Limit"),
    ("下限", "Lower Limit"),
    ("上位", "Up Position"),
    ("下位", "Down Position"),
    ("伸出", "Extend"),
    ("缩回", "Retract"),
    ("收回", "Retract"),
    ("上升", "Rise"),
    ("下降", "Descend"),
    ("前进", "Advance"),
    ("后退", "Retract"),
    ("夹紧", "Clamp"),
    ("松开", "Unclamp"),
    ("打开", "Open"),
    ("关闭", "Close"),
    ("到位", "In-Position"),
    ("未到位", "Not In-Position"),
    ("未检测", "Undetected"),
    ("检测", "Detection"),
    ("测", "Measure"),
    ("感应", "Sensor"),
    ("常开", "Normally-Open"),
    ("触点", "Contact"),
    ("电", "Power"),
    ("机头", "Head"),
    ("平移", "Shift"),
    ("起头", "Lead"),
    ("回撤", "Retract"),
    ("松", "Release"),
    ("压", "Press"),
    ("拉", "Pull"),
    ("卷料", "Reel"),
    ("空卷", "Empty Reel"),
    ("空转", "Idling"),
    ("重教", "Re-Teach"),
    ("标定", "Calibration"),
    ("教点", "Teach Point"),
    ("临时", "Temp"),
    ("临", "Temp"),
    ("加", "Add"),
    ("减", "Minus"),
    ("转成浮点数", "Convert to Float"),
    ("浮点数", "Float"),
    ("超出", "Exceeded"),
    ("重新", "Re-"),
    ("提前", "Advance"),
    ("综合", "Combined"),
    ("信号", "Signal"),
    ("请检查", "Please Check"),
    ("是否有", "Check For"),
    ("卡顿", "Jamming"),
    ("现象", "Condition"),
    ("太小", "Too Low"),
    ("太大", "Too High"),
    ("已满", "Full"),
    ("请清理", "Please Clean"),
    ("后位", "Rear Position"),
    ("门型", "Slot"),
    ("模拟", "Simulated"),
    ("回应", "Response"),
    ("下游", "Downstream"),
    ("上游", "Upstream"),
    ("线体", "Line"),
    ("侧", "Side"),
    ("阻挡", "Stopper"),
    ("顶升", "Lifter"),
    ("全", "All"),
    ("部", "Part"),
    ("各", "Each"),
    ("总", "Total"),
    ("组", "Group"),
    ("轴组", "Axis Group"),
    ("轴", "Axis"),
    ("工位", "Station"),
    ("站", "Station"),
    ("保护", "Guard"),
    ("有效", "Valid"),
    ("忙", "Busy"),
    ("完", "Done"),
    ("成", "Done"),
    ("到达", "Reached"),
    ("请求", "Request"),
    ("可", "Permit"),
    ("允许", "Permit"),
    ("禁止", "Prohibit"),
    ("确认", "Ack"),
    ("读", "Read"),
    ("写", "Write"),
    ("选", "Select"),
    ("用", "Use"),
    ("开", "ON"),
    ("关", "OFF"),
    ("出", "Out"),
    ("入", "In"),
    ("进", "In"),
    ("回", "Return"),
    ("上", "Up"),
    ("下", "Down"),
    ("左", "Left"),
    ("右", "Right"),
    ("前", "Front"),
    ("后", "Rear"),
    ("中", "Active"),
    ("且", "And"),
    ("非", "Non-"),
    ("去", "De-"),
    ("值", "Value"),
    ("点", "Point"),
    ("位", "Position"),
    ("间", "Interval"),
    ("期", "Period"),
    ("器", "Device"),
    ("机", "Machine"),
    ("型", "Type"),
    ("条", "Bar"),
    ("带", "Tape"),
    ("段", "Segment"),
    ("料", "Material"),
    ("箱", "Box"),
    ("头", "Head"),
    ("端", "End"),
    ("层", "Layer"),
    ("块", "Block"),
    ("包", "Package"),
    ("件", "Piece"),
    ("品", "Product"),
    ("率", "Rate"),
    ("量", "Quantity"),
    ("数", "Count"),
    ("次", "Times"),
    ("门", "Door"),
    ("磁", "Magnetic"),
    ("锁", "Lock"),
    ("窗", "Window"),
    ("口", "Port"),
    ("路", "Channel"),
    ("通", "Pass"),
    ("讯", "Comm"),
    ("信", "Signal"),
    ("线", "Line"),
    ("弧", "Arc"),
    ("圆", "Circle"),
    ("度", "Degree"),
    ("角", "Angle"),
    ("年", "Year"),
    ("月", "Month"),
    ("日", "Day"),
    ("毫", "Milli"),
    ("钩", "Hook"),
    ("圈", "Turn"),
    ("没", "No"),
    ("再", "Then"),
    ("不", "Not"),
    ("有", "With"),
    ("的", ""),
    ("绝", "Absolute"),
    ("频", "Freq"),
    ("到", "To"),
]


# =============================================================================
# 4. 内置插件实现 (Built-in Plugin Implementations)
# =============================================================================

class BuiltinDictionaryPlugin(DictionaryProviderPlugin):
    """核心内置词典与动态正则规则插件"""
    plugin_id = "builtin_dictionary"
    plugin_name = "Core IEC / Corning Built-in Dictionary Provider"
    version = "1.0.0"
    priority = 100

    def get_exact_phrases(self) -> Dict[str, str]:
        return dict(BUILTIN_EXACT_PHRASES)

    def get_word_pairs(self) -> List[Tuple[str, str]]:
        return list(BUILTIN_WORD_PAIRS)

    def get_regex_rules(self) -> List[Tuple[Union[re.Pattern, str], Callable]]:
        # 定义 8 类参数化动态正则处理句柄
        def handle_clk(m: re.Match, tr: Callable[[str], str]) -> str:
            op = 'Read' if m.group(1) == '读出' else 'Write'
            tag_map = {
                '年': 'Year', '月': 'Month', '日': 'Day', '时': 'Hour',
                '分': 'Minute', '秒': 'Second', '星期': 'Day of Week', '毫秒': 'Millisecond'
            }
            return f"PLC Clock {op} {tag_map.get(m.group(2), m.group(2))}"

        def handle_hourly(m: re.Match, tr: Callable[[str], str]) -> str:
            hr = m.group(1)
            k = m.group(2)
            tag_map = {
                '产量统计区间时间段': 'Production Statistics Interval Period',
                '分': 'Minute', '小时转秒为单位': 'Hours to Seconds Conversion',
                '时': 'Hour', '时段': 'Period', '秒': 'Second'
            }
            return f"{hr}:00 {tag_map.get(k, k)}"

        def handle_rio(m: re.Match, tr: Callable[[str], str]) -> str:
            return f"#{m.group(1)} Remote I/O Module Link Error!"

        def handle_ecat(m: re.Match, tr: Callable[[str], str]) -> str:
            return f"EtherCAT Slave {m.group(1)} Comm Error!"

        def handle_alm(m: re.Match, tr: Callable[[str], str]) -> str:
            code = m.group(1)
            sub = tr(m.group(2))
            return f"({code}) {sub}"

        def handle_multi_axis(m: re.Match, tr: Callable[[str], str]) -> str:
            ax = m.group(1)
            rest = tr(m.group(2))
            return f"Axis {ax} {rest}".strip()

        def handle_single_axis(m: re.Match, tr: Callable[[str], str]) -> str:
            ax = m.group(1)
            rest = tr(m.group(2))
            return f"Axis {ax}: {rest}".strip()

        def handle_array(m: re.Match, tr: Callable[[str], str]) -> str:
            base = m.group(1)
            idx = m.group(2)
            trans_base = tr(base)
            return f"{trans_base} [{idx}]"

        return [
            (re.compile(r'^PLC时钟(读出|写入)_(年|月|日|时|分|秒|星期|毫秒)$'), handle_clk),
            (re.compile(r'^(\d\d)_(产量统计区间时间段|分|小时转秒为单位|时|时段|秒)$'), handle_hourly),
            (re.compile(r'^(\d+)#远程I/O模块链接异常[！!]?$'), handle_rio),
            (re.compile(r'^EtherCAT\s*从站(\d+)\'?通讯异常[！!]?$'), handle_ecat),
            (re.compile(r'^\((F\d+)\)_(.+)$'), handle_alm),
            (re.compile(r'^([\d/]+)轴(.+)$'), handle_multi_axis),
            (re.compile(r'^轴(\d+)[：:](.+)$'), handle_single_axis),
            (re.compile(r'^(.*)\[(\d+)\]$'), handle_array),
        ]


class GVLTableParser(TableParserPlugin):
    """InoProShop / CODESYS 9 列标准 GVL 变量表解析器"""
    plugin_id = "gvl_table_parser"
    plugin_name = "InoProShop GVL 9-Col CSV Parser"
    version = "1.0.0"
    priority = 100

    def can_parse(self, file_path: str, raw_bytes: bytes = b"") -> bool:
        if not file_path.lower().endswith('.csv'):
            return False
        if not raw_bytes and os.path.exists(file_path):
            try:
                with open(file_path, "rb") as f:
                    raw_bytes = f.read(2048)
            except Exception:
                raw_bytes = b""
        if raw_bytes.startswith(b'\xff\xfe') or raw_bytes.startswith(b'\xfe\xff'):
            return False
        if b'\t' in raw_bytes[:512]:
            return False
        fn = os.path.basename(file_path)
        if "变量表" in fn:
            return True
        header = raw_bytes[:256].decode('gbk', errors='ignore')
        return "序号" in header and "变量名" in header

    def parse(self, file_path: str, encoding: str = "gbk") -> TableDocument:
        with open(file_path, "rb") as f:
            raw = f.read()
        text = raw.decode(encoding, errors='replace')
        lines = text.splitlines(keepends=False)

        headers = []
        rows = []
        raw_lines = lines

        for idx, line in enumerate(lines):
            if idx == 0:
                headers = [p.strip() for p in line.split(',')]
                continue
            if not line.strip():
                rows.append(TableRow(raw_line=line))
                continue

            parts = line.split(',')
            if len(parts) >= 8:
                if len(parts) > 10:
                    joined_c = ','.join(parts[7:-2]).strip()
                    c_val = joined_c if any(p.strip() for p in parts[7:-2]) else ""
                    addr_val = parts[-2].strip()
                else:
                    c_val = parts[7].strip() if len(parts) > 7 else ""
                    addr_val = parts[8].strip() if len(parts) > 8 else ""

                row = TableRow(
                    no=parts[0].strip() if len(parts) > 0 else "",
                    name=parts[1].strip() if len(parts) > 1 else "",
                    data_type=parts[2].strip() if len(parts) > 2 else "",
                    init_hide=parts[3].strip() if len(parts) > 3 else "",
                    init_val=parts[4].strip() if len(parts) > 4 else "",
                    retain=parts[5].strip() if len(parts) > 5 else "",
                    publish=parts[6].strip() if len(parts) > 6 else "",
                    comment=c_val,
                    addr=addr_val,
                    raw_parts=parts,
                    raw_line=line
                )
                rows.append(row)
            else:
                rows.append(TableRow(raw_line=line, raw_parts=parts))

        return TableDocument(
            file_path=file_path,
            table_type="var",
            headers=headers,
            rows=rows,
            raw_lines=raw_lines,
            metadata={"encoding": encoding, "line_count": len(lines)}
        )


class IOTableParser(TableParserPlugin):
    """AutoShop / InoProShop 硬件软元件 IO 注释表解析器"""
    plugin_id = "io_table_parser"
    plugin_name = "AutoShop/InoProShop IO Comment CSV Parser"
    version = "1.0.0"
    priority = 100

    def can_parse(self, file_path: str, raw_bytes: bytes = b"") -> bool:
        if not file_path.lower().endswith('.csv'):
            return False
        if not raw_bytes and os.path.exists(file_path):
            try:
                with open(file_path, "rb") as f:
                    raw_bytes = f.read(2048)
            except Exception:
                raw_bytes = b""
        if raw_bytes.startswith(b'\xff\xfe') or raw_bytes.startswith(b'\xfe\xff'):
            return False
        if b'\t' in raw_bytes[:512]:
            return False
        fn = os.path.basename(file_path)
        if fn.startswith(("io", "IO", "io注释", "IO注释")):
            return True
        return False

    def parse(self, file_path: str, encoding: str = "gbk") -> TableDocument:
        with open(file_path, "rb") as f:
            raw = f.read()
        text = raw.decode(encoding, errors='replace')
        lines = text.splitlines(keepends=False)

        def is_io_header(line: str) -> bool:
            parts = line.split(',')
            first = parts[0].strip()
            if re.match(r'^[XYMDBWxymdbw]\d+', first):
                return False
            if any(k in first for k in ["软元件", "地址", "序号", "名称", "变量", "Device", "Address"]):
                return True
            if len(parts) > 1 and any(k in parts[1] for k in ["注释", "说明", "Comment", "类型"]):
                return True
            return False

        has_header = is_io_header(lines[0]) if lines else False
        headers = [p.strip() for p in lines[0].split(',')] if (has_header and lines) else []
        rows = []

        start_idx = 1 if has_header else 0
        for idx in range(start_idx, len(lines)):
            line = lines[idx]
            if not line.strip():
                rows.append(TableRow(raw_line=line))
                continue

            parts = line.split(',')
            c_idx = 7 if len(parts) >= 8 else 1
            addr = parts[0].strip() if len(parts) > 0 else ""
            c = parts[c_idx].strip() if len(parts) > c_idx else ""
            row = TableRow(
                no=str(idx),
                name=addr,
                comment=c,
                addr=addr,
                raw_parts=parts,
                raw_line=line,
                extra={"c_idx": c_idx}
            )
            rows.append(row)

        return TableDocument(
            file_path=file_path,
            table_type="io",
            headers=headers,
            rows=rows,
            raw_lines=lines,
            metadata={"encoding": encoding, "line_count": len(lines), "has_header": has_header}
        )


class GVLCsvExporter(TableExporterPlugin):
    """GVL 9 列标准 CSV 导出器 (强制 GBK 编码与 Windows CRLF 换行)"""
    plugin_id = "gvl_csv_exporter"
    plugin_name = "GVL 9-Column CSV Exporter (GBK/CRLF)"
    version = "1.0.0"
    priority = 100

    def can_export(self, format_name: str) -> bool:
        return format_name.lower() in ["gvl_csv", "var_csv", "csv"]

    def export(self, doc: TableDocument, output_path: str, **kwargs) -> None:
        lines = []
        if doc.raw_lines:
            lines.append(doc.raw_lines[0])
        elif doc.headers:
            lines.append(','.join(doc.headers))

        is_chinese_backup = kwargs.get("is_chinese_backup", False)
        mode = kwargs.get("mode", "B").upper()

        for row in doc.rows:
            if not row.raw_line.strip() or not row.raw_parts:
                lines.append(row.raw_line)
                continue

            parts = list(row.raw_parts)
            if len(parts) >= 8:
                if is_chinese_backup:
                    cn_c = row.extra.get("new_cn_c", row.comment)
                    parts[7] = cn_c.replace(',', '，')
                else:
                    en_c = row.extra.get("new_en_c", row.comment)
                    parts[7] = en_c.replace(',', ' / ').replace('，', ' / ')
                    if mode == "A":
                        parts[1] = row.extra.get("new_en_var", row.name)

                # 保持 9 列及尾随逗号保真
                lines.append(','.join(parts[:9]) + ',')
            else:
                lines.append(row.raw_line)

        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        content = '\r\n'.join(lines) + '\r\n'
        with open(output_path, "wb") as f_out:
            f_out.write(content.encode('gbk'))


class IOCsvExporter(TableExporterPlugin):
    """IO 注释表 CSV 导出器 (严格保持 GBK 与 CRLF)"""
    plugin_id = "io_csv_exporter"
    plugin_name = "IO Table CSV Exporter (GBK/CRLF)"
    version = "1.0.0"
    priority = 100

    def can_export(self, format_name: str) -> bool:
        return format_name.lower() in ["io_csv"]

    def export(self, doc: TableDocument, output_path: str, **kwargs) -> None:
        lines = []
        has_header = doc.metadata.get("has_header", bool(doc.headers))
        if has_header and doc.raw_lines:
            lines.append(doc.raw_lines[0])
        elif has_header and doc.headers:
            lines.append(','.join(doc.headers))

        is_chinese_backup = kwargs.get("is_chinese_backup", False)

        for row in doc.rows:
            if not row.raw_line.strip() or not row.raw_parts:
                lines.append(row.raw_line)
                continue

            parts = list(row.raw_parts)
            c_idx = row.extra.get("c_idx", 7 if len(parts) >= 8 else 1)
            if len(parts) > c_idx:
                if is_chinese_backup:
                    cn_c = row.extra.get("new_cn_c", row.comment)
                    parts[c_idx] = cn_c.replace(',', '，')
                else:
                    en_c = row.extra.get("new_en_c", row.comment)
                    parts[c_idx] = en_c.replace(',', ' / ').replace('，', ' / ')
                lines.append(','.join(parts))
            else:
                lines.append(row.raw_line)

        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        content = '\r\n'.join(lines) + '\r\n'
        with open(output_path, "wb") as f_out:
            f_out.write(content.encode('gbk'))


class MarkdownReportExporter(TableExporterPlugin):
    """单一中英双语对照交付总表生成器 (含文首交互式目录与锚点跳转)"""
    plugin_id = "markdown_report_exporter"
    plugin_name = "Consolidated Delivery Markdown Report Exporter"
    version = "1.0.0"
    priority = 100

    def can_export(self, format_name: str) -> bool:
        return format_name.lower() in ["markdown", "md", "report"]

    def export(self, doc: TableDocument, output_path: str, **kwargs) -> None:
        all_records = kwargs.get("all_records", {})
        project_title = kwargs.get("project_title", "Corning Project CT173")
        mode = kwargs.get("mode", "B")

        self.generate_report(all_records, output_path, project_title=project_title, mode=mode)

    def generate_report(self, all_records: Dict[str, List[Tuple]], report_path: str,
                        project_title: str = "Corning Project CT173", mode: str = "B") -> None:
        lines = []
        lines.append(f"# 变量表中英文对照全表 ({project_title})\n")
        lines.append(f"> **项目交付**：美国康宁 (Corning Incorporated - {project_title})")
        lines.append("> **规范标准**：《电气术语定义标准与命名规范 (20251105-EN)》")
        lines.append(f"> **实施策略**：**方案 {mode}**（变量名保持原始符号不变；已有注释 100% 翻译为纯专业英文；缺失注释的变量根据变量名规范补齐注释）。")
        lines.append("> **文件保真**：全部变量表 CSV 文件严格保持 9 列结构、GBK 编码与 CRLF 换行，支持汇川 PLC 直接无损导入。\n")
        lines.append("---\n")

        lines.append("## 目录与汇总导航 (Table of Contents)\n")
        lines.append("| 章节序号 | 变量表文件名 | 数据行数 | 快速跳转 |")
        lines.append("| :---: | :--- | :---: | :--- |")

        total_rows = 0
        file_list = list(all_records.items())
        for idx, (fname, rows) in enumerate(file_list, 1):
            total_rows += len(rows)
            anchor = f"section-{idx}"
            lines.append(f"| 第 {idx} 章 | `{fname}` | {len(rows):,} 行 | [点击查看详细对照](#{anchor}) |")

        lines.append(f"| **合计** | **全部 {len(file_list)} 个变量表** | **{total_rows:,} 行** | - |\n")
        lines.append("---\n")

        for idx, (fname, rows) in enumerate(file_list, 1):
            anchor = f"section-{idx}"
            lines.append(f'<span id="{anchor}"></span>\n')
            lines.append(f"## {idx}. {fname} (共 {len(rows):,} 行数据)\n")
            lines.append("| 序号 | 变量名 (Variable Name) | 数据类型 | 规范中文注释 (Chinese) | 交付英文注释 (English Standard) |")
            lines.append("| :---: | :--- | :---: | :--- | :--- |")
            for no, var, dtype, cn_c, en_c in rows:
                no_str = no if no else "-"
                lines.append(f"| {no_str} | `{var}` | `{dtype}` | {cn_c} | **`{en_c}`** |")
            lines.append("\n[返回目录](#目录与汇总导航-table-of-contents)\n")
            lines.append("---\n")

        os.makedirs(os.path.dirname(os.path.abspath(report_path)), exist_ok=True)
        with open(report_path, "w", encoding="utf-8") as f_out:
            f_out.write("\n".join(lines))
        print(f"\n[ReportGenerator] 交付报告已生成: {report_path} (共包含 {len(file_list)} 张表，{total_rows:,} 行数据)")


class MitsubishiGXWorks3Parser(TableParserPlugin):
    """三菱电机 GX Works3 27 列 UTF-16 TSV 标签与 IO 注释表解析器"""
    plugin_id = "mitsubishi_gx_works3_parser"
    plugin_name = "Mitsubishi GX Works3 Parser"
    version = "1.0.0"
    priority = 50  # 优于通用解析器 (100)

    def can_parse(self, file_path: str, raw_bytes: bytes = b"") -> bool:
        if not file_path.lower().endswith(('.csv', '.tsv')):
            return False
        if not raw_bytes and os.path.exists(file_path):
            try:
                with open(file_path, "rb") as f:
                    raw_bytes = f.read(2048)
            except Exception:
                raw_bytes = b""
        if raw_bytes.startswith(b'\xff\xfe') or raw_bytes.startswith(b'\xfe\xff'):
            return True
        try:
            chunk_u16 = raw_bytes[:1024].decode('utf-16', errors='ignore')
            if '\t' in chunk_u16 and any(k in chunk_u16 for k in ["类", "标签名", "软元件名", "VAR_INPUT", "VAR_OUTPUT", "English"]):
                return True
        except Exception:
            pass
        try:
            chunk_u8 = raw_bytes[:1024].decode('utf-8', errors='ignore')
            if '\t' in chunk_u8 and any(k in chunk_u8 for k in ["类", "标签名", "软元件名", "VAR_INPUT", "VAR_OUTPUT", "English"]):
                return True
        except Exception:
            pass
        return False

    def parse(self, file_path: str, encoding: str = "utf-16") -> TableDocument:
        with open(file_path, "rb") as f:
            raw = f.read()

        if raw.startswith(b'\xff\xfe') or raw.startswith(b'\xfe\xff'):
            text = raw.decode("utf-16", errors="replace")
            actual_enc = "utf-16"
        else:
            try:
                text = raw.decode("utf-16")
                actual_enc = "utf-16"
            except Exception:
                try:
                    text = raw.decode("utf-8")
                    actual_enc = "utf-8"
                except Exception:
                    text = raw.decode("gbk", errors="replace")
                    actual_enc = "gbk"

        lines = text.splitlines(keepends=False)

        pou_title = ""
        headers = []
        rows = []
        table_type = "var"

        start_idx = 0
        if lines and lines[0].strip().startswith('"') and '\t' not in lines[0]:
            pou_title = lines[0].strip().strip('"')
            start_idx = 1

        if len(lines) > start_idx:
            header_line = lines[start_idx]
            headers = [p.strip().strip('"') for p in header_line.split('\t')]
            start_idx += 1
            if "软元件名" in headers:
                table_type = "io"

        for idx in range(start_idx, len(lines)):
            line = lines[idx]
            if not line.strip():
                rows.append(TableRow(raw_line=line))
                continue
            parts = [p.strip().strip('"') for p in line.split('\t')]

            if table_type == "io":
                dev_addr = parts[0] if len(parts) > 0 else ""
                comm = parts[1] if len(parts) > 1 else ""
                row = TableRow(
                    no=str(idx - start_idx + 1),
                    name=dev_addr,
                    addr=dev_addr,
                    comment=comm,
                    raw_parts=parts,
                    raw_line=line
                )
                rows.append(row)
            else:
                v_class = parts[0] if len(parts) > 0 else ""
                v_name = parts[1] if len(parts) > 1 else ""
                v_type = parts[2] if len(parts) > 2 else ""
                v_init = parts[4] if len(parts) > 4 else ""
                v_alloc = parts[5] if len(parts) > 5 else ""
                v_addr = parts[6] if len(parts) > 6 else ""
                v_comm = parts[7] if len(parts) > 7 else ""
                v_en = parts[13] if len(parts) > 13 else ""
                v_cn = parts[14] if len(parts) > 14 else ""
                v_it = parts[18] if len(parts) > 18 else ""

                effective_comm = v_cn or v_comm
                if not effective_comm and any('\u4e00' <= c <= '\u9fff' for c in v_name):
                    effective_comm = v_name

                row = TableRow(
                    no=str(idx - start_idx + 1),
                    name=v_name,
                    data_type=v_type,
                    init_val=v_init,
                    comment=effective_comm,
                    addr=v_alloc or v_addr,
                    raw_parts=parts,
                    raw_line=line,
                    extra={
                        "class": v_class,
                        "comment_orig": v_comm,
                        "comment_en": v_en,
                        "comment_cn": v_cn,
                        "comment_it": v_it,
                        "tokens_count": len(parts)
                    }
                )
                rows.append(row)

        return TableDocument(
            file_path=file_path,
            table_type=table_type,
            headers=headers,
            rows=rows,
            raw_lines=lines,
            metadata={
                "encoding": actual_enc,
                "delimiter": "\t",
                "platform": "mitsubishi",
                "pou_title": pou_title,
                "line_count": len(lines)
            }
        )


class MitsubishiGXWorks3Exporter(TableExporterPlugin):
    """三菱 GX Works3 27 列 TSV 导出序列化器 (严格保持 UTF-16 LE 与 制表符)"""
    plugin_id = "mitsubishi_gx_works3_exporter"
    plugin_name = "Mitsubishi GX Works3 Exporter"
    version = "1.0.0"
    priority = 50

    def can_export(self, format_name: str) -> bool:
        return format_name.lower() in ["mitsubishi", "gx_works3", "gx3", "gxworks3"]

    def export(self, doc: TableDocument, output_path: str, target_lang: str = "en", update_comment_col: bool = True, **kwargs) -> None:
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        lines = []

        pou_title = doc.metadata.get("pou_title", "")
        if pou_title:
            lines.append(f'"{pou_title}"\r\n')

        # 写入表头
        if doc.headers:
            header_str = '\t'.join([f'"{h}"' for h in doc.headers]) + '\r\n'
            lines.append(header_str)

        for row in doc.rows:
            if not row.raw_parts:
                lines.append(row.raw_line + ('\r\n' if not row.raw_line.endswith('\n') else ''))
                continue

            parts = list(row.raw_parts)

            if doc.table_type == "io":
                addr = row.addr or row.name
                comm = row.extra.get("new_en_c", row.comment)
                line_str = f'"{addr}"\t"{comm}"\r\n'
                lines.append(line_str)
            else:
                while len(parts) < 27:
                    parts.append("")

                translated = row.extra.get("new_en_c", row.comment)
                if target_lang == "it":
                    parts[18] = translated  # Col 18: Italian/Italiano
                else:
                    parts[13] = translated  # Col 13: English

                cn_c = row.extra.get("new_cn_c", row.extra.get("comment_cn", row.comment))
                if cn_c and not parts[14]:
                    parts[14] = cn_c

                if update_comment_col:
                    parts[7] = translated

                line_str = '\t'.join([f'"{p}"' for p in parts]) + '\r\n'
                lines.append(line_str)

        with open(output_path, "w", encoding="utf-16", newline="") as f:
            f.writelines(lines)


def detect_table_platform(file_path: str) -> str:
    """智能嗅探 CSV/TSV 文件的 PLC 编程平台类型 ('autoshop' | 'inoproshop' | 'mitsubishi' | 'inovance' | 'unknown')"""
    if not file_path or not os.path.exists(file_path):
        return "unknown"
    try:
        with open(file_path, "rb") as f:
            chunk = f.read(2048)
        if chunk.startswith(b'\xff\xfe') or chunk.startswith(b'\xfe\xff'):
            return "mitsubishi"
        if b'\t' in chunk:
            return "mitsubishi"

        parent_dir = os.path.dirname(os.path.abspath(file_path))
        machine_dir = os.path.dirname(parent_dir) if os.path.basename(parent_dir) in ["变量表", "IO注释", "io注释_备份_原始留档", "io注释_备份_规范中文版"] else parent_dir
        has_hcp = False
        try:
            if os.path.exists(machine_dir):
                for root, dirs, files in os.walk(machine_dir):
                    if any(f.endswith(('.hcp', '.hcpp')) for f in files):
                        has_hcp = True
                        break
        except Exception:
            pass

        for enc in ["gbk", "utf-8"]:
            try:
                t = chunk.decode(enc, errors="ignore")
                # AutoShop 8列 IO 注释表特征: 数据值1,数据值2...
                if "数据值1" in t or "数据值" in t:
                    return "autoshop"
                # AutoShop 软元件注释表特征
                if "软元件" in t and "," in t:
                    return "autoshop"
                # 汇川 9 列变量表: 序号,变量名,数据类型,隐藏初始值...
                if "序号" in t and "变量名" in t:
                    return "autoshop" if has_hcp else "inoproshop"
                if "类" in t and "标签名" in t:
                    return "mitsubishi"
            except Exception:
                pass
    except Exception:
        pass
    return "autoshop"


# =============================================================================
# 5. 插件注册中心与微内核引擎 (Plugin Registry & Microkernel Core)
# =============================================================================

T = Any

class PluginRegistry:
    """管理插件全生命周期、优先级排序与动态加载的注册中心"""

    def __init__(self):
        self._plugins: Dict[str, BasePlugin] = {}

    def register(self, plugin: BasePlugin, kernel: Optional["Kernel"] = None) -> None:
        if not isinstance(plugin, BasePlugin):
            raise TypeError(f"Expected BasePlugin instance, got {type(plugin).__name__}")
        self._plugins[plugin.plugin_id] = plugin
        try:
            plugin.on_load(kernel or self)
        except Exception:
            pass

    def unregister(self, plugin_id: str) -> Optional[BasePlugin]:
        plugin = self._plugins.pop(plugin_id, None)
        if plugin:
            try:
                plugin.on_unload()
            except Exception:
                pass
        return plugin

    def get_plugin(self, plugin_id: str) -> Optional[BasePlugin]:
        return self._plugins.get(plugin_id)

    def get_plugins(self) -> List[BasePlugin]:
        """返回所有已注册插件，按优先级数值升序排列 (数值越小优先级越高)"""
        return sorted(self._plugins.values(), key=lambda p: getattr(p, "priority", 100))

    def get_plugins_by_type(self, plugin_type: Type[T]) -> List[T]:
        matched = [p for p in self._plugins.values() if isinstance(p, plugin_type)]
        # 按 priority 升序排序 (数值越小优先级越高)
        return sorted(matched, key=lambda p: getattr(p, "priority", 100))

    def load_from_file(self, file_path: str, kernel: Optional["Kernel"] = None) -> List[BasePlugin]:
        abs_path = os.path.abspath(file_path)
        if not os.path.exists(abs_path):
            raise FileNotFoundError(f"插件文件不存在: {abs_path}")

        module_name = f"plc_plugin_{os.path.splitext(os.path.basename(abs_path))[0]}_{abs(hash(abs_path))}"
        spec = importlib.util.spec_from_file_location(module_name, abs_path)
        if spec is None or spec.loader is None:
            raise ImportError(f"无法加载插件模块规范: {abs_path}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)

        loaded_plugins = []
        # 1. 检查模块是否导出 register_plugins 声明
        if hasattr(module, "register_plugins") and callable(module.register_plugins):
            res = module.register_plugins(kernel or self)
            if isinstance(res, list):
                loaded_plugins.extend(res)

        # 2. 自动扫描模块内的 BasePlugin 实例与子类
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if isinstance(attr, BasePlugin) and attr not in loaded_plugins:
                self.register(attr, kernel=kernel)
                loaded_plugins.append(attr)
            elif (isinstance(attr, type) and issubclass(attr, BasePlugin) and
                  attr not in [BasePlugin, TableParserPlugin, DictionaryProviderPlugin, TableExporterPlugin, PostVerifyRulePlugin]):
                try:
                    inst = attr()
                    if inst.plugin_id not in self._plugins:
                        self.register(inst, kernel=kernel)
                        loaded_plugins.append(inst)
                except Exception:
                    pass

        return loaded_plugins

    def load_from_directory(self, dir_path: str, kernel: Optional["Kernel"] = None) -> List[BasePlugin]:
        if not os.path.isdir(dir_path):
            return []
        loaded = []
        for fn in sorted(os.listdir(dir_path)):
            if fn.endswith(".py") and not fn.startswith((".", "_")):
                fp = os.path.join(dir_path, fn)
                try:
                    loaded.extend(self.load_from_file(fp, kernel=kernel))
                except Exception as ex:
                    print(f"[WARN] 加载插件失败 {fp}: {ex}")
        return loaded


class MultiStageTranslationEngine:
    """级联式多阶段工业电气翻译引擎 (支持插件字典热加载与优先级仲裁)"""

    def __init__(self, kernel: Optional["Kernel"] = None):
        self.kernel = kernel
        self._cache_dirty = True
        self._merged_exact: Dict[str, str] = {}
        self._merged_word_pairs: List[Tuple[str, str]] = []
        self._merged_regex_rules: List[Tuple[Any, Callable]] = []

    def invalidate_cache(self) -> None:
        self._cache_dirty = True

    def _rebuild_cache_if_needed(self) -> None:
        if not self._cache_dirty:
            return

        exact_map: Dict[str, str] = {}
        word_pairs: List[Tuple[str, str]] = []
        regex_rules: List[Tuple[Any, Callable]] = []

        if self.kernel:
            providers = self.kernel.registry.get_plugins_by_type(DictionaryProviderPlugin)
            # 1. 降序遍历收集精确匹配短语：高优先级（较小 priority）在后执行，从而覆盖低优先级
            for p in reversed(providers):
                plugin_id = getattr(p, "plugin_id", type(p).__name__)
                try:
                    phrases = p.get_exact_phrases()
                    if phrases and isinstance(phrases, dict):
                        # 防御性更新，确保键值均为有效字符串
                        for k, v in phrases.items():
                            if k and v is not None:
                                exact_map[str(k)] = str(v)
                    elif phrases is not None and not isinstance(phrases, dict):
                        print(f"[WARN] 插件 [{plugin_id}] get_exact_phrases 返回类型非法 (期望 dict, 实际 {type(phrases).__name__})，已跳过")
                except Exception as ex:
                    print(f"[WARN] 插件 [{plugin_id}] get_exact_phrases 发生异常: {ex}")

            # 2. 收集词对与正则规则（按高优先级在前）
            for p in providers:
                plugin_id = getattr(p, "plugin_id", type(p).__name__)
                # 词对提取隔离与格式清洗
                try:
                    wp = p.get_word_pairs()
                    if wp and isinstance(wp, (list, tuple)):
                        for item in wp:
                            if isinstance(item, (list, tuple)) and len(item) == 2:
                                ch, en = item
                                if ch and en is not None:
                                    word_pairs.append((str(ch), str(en)))
                    elif wp is not None and not isinstance(wp, (list, tuple)):
                        print(f"[WARN] 插件 [{plugin_id}] get_word_pairs 返回类型非法 (期望 list, 实际 {type(wp).__name__})，已跳过")
                except Exception as ex:
                    print(f"[WARN] 插件 [{plugin_id}] get_word_pairs 发生异常: {ex}")

                # 正则规则提取与编译隔离
                try:
                    rules = p.get_regex_rules()
                    if rules and isinstance(rules, (list, tuple)):
                        for item in rules:
                            try:
                                if not isinstance(item, (list, tuple)) or len(item) != 2:
                                    continue
                                pat, handler = item
                                if not callable(handler):
                                    continue
                                compiled_pat = re.compile(pat) if isinstance(pat, str) else pat
                                regex_rules.append((compiled_pat, handler))
                            except Exception as rx_err:
                                print(f"[WARN] 插件 [{plugin_id}] 正则规则编译失败: {item}, {rx_err}")
                    elif rules is not None and not isinstance(rules, (list, tuple)):
                        print(f"[WARN] 插件 [{plugin_id}] get_regex_rules 返回类型非法 (期望 list, 实际 {type(rules).__name__})，已跳过")
                except Exception as ex:
                    print(f"[WARN] 插件 [{plugin_id}] get_regex_rules 发生异常: {ex}")
        else:
            exact_map.update(BUILTIN_EXACT_PHRASES)
            word_pairs.extend(BUILTIN_WORD_PAIRS)
            builtin_plugin = BuiltinDictionaryPlugin()
            for pat, handler in builtin_plugin.get_regex_rules():
                regex_rules.append((pat, handler))

        # 词对按长度降序排序 (保证最长匹配优先)
        word_pairs.sort(key=lambda x: len(x[0]), reverse=True)

        self._merged_exact = exact_map
        self._merged_word_pairs = word_pairs
        self._merged_regex_rules = regex_rules
        self._cache_dirty = False

    def translate(self, text: str, custom_dict: Optional[Dict[str, str]] = None, target_lang: str = "en") -> str:
        """多阶段级联翻译：Exact -> Regex -> Greedy -> Normalization (支持 EN / IT 语言)"""
        if not text:
            return ""
        s = text.strip()
        if not re.search(r'[\u4e00-\u9fff]', s):
            return s

        # 用户显式传入的临时自定义字典具有最高仲裁权
        if custom_dict and s in custom_dict:
            return custom_dict[s]

        # 针对意大利语 (target_lang == 'it')，优先匹配意大利专有短语
        if target_lang == "it" and self.kernel:
            providers = self.kernel.registry.get_plugins_by_type(DictionaryProviderPlugin)
            for p in providers:
                if hasattr(p, "get_exact_phrases_italian"):
                    try:
                        it_map = p.get_exact_phrases_italian()
                        if it_map and s in it_map:
                            return it_map[s]
                    except Exception:
                        pass
            try:
                from solar_frame_dictionary_plugin import SolarFrameDictionaryPlugin
                if s in SolarFrameDictionaryPlugin.EXACT_PHRASES_IT:
                    return SolarFrameDictionaryPlugin.EXACT_PHRASES_IT[s]
            except Exception:
                pass

        self._rebuild_cache_if_needed()

        # Tier 1: Exact Match (O(1))
        if s in self._merged_exact:
            return self._merged_exact[s]

        # Tier 2: Dynamic Regex Pattern Handlers
        for pat, handler in self._merged_regex_rules:
            m = pat.match(s)
            if m:
                try:
                    res = handler(m, lambda t: self.translate(t, custom_dict=custom_dict))
                    if res is not None:
                        return res
                except Exception:
                    continue

        # Tier 3: Greedy Multi-Word Substring Substitution
        res = s
        for ch, en in self._merged_word_pairs:
            if ch in res:
                res = res.replace(ch, f" {en} ")

        # Tier 4: Delimiter & Punctuation Sanitization
        res = res.replace('：', ': ').replace('，', ' / ').replace(',', ' / ').replace('；', ' / ').replace(';', ' / ')
        res = res.replace('！', '!').replace('（', ' (').replace('）', ') ').replace('？', '?')
        res = re.sub(r'\s*/\s*', ' / ', res)
        res = re.sub(r'\s+', ' ', res).strip()
        res = re.sub(r'\s+([:!,\?\)])', r'\1', res)
        res = re.sub(r'([\(])\s+', r'\1', res)

        return res

    def derive_chinese_comment(self, var_name: str, existing_comment: str) -> str:
        """规范中文版注释推导补全逻辑"""
        if existing_comment and existing_comment.strip():
            return existing_comment.strip()
        var = var_name.strip()
        if re.search(r'[\u4e00-\u9fff]', var):
            return var
        return ""


class Kernel:
    """微内核核心 (Central Coordinator)"""

    def __init__(self):
        self.registry = PluginRegistry()
        self.engine = MultiStageTranslationEngine(kernel=self)
        self._register_builtins()

    def _register_builtins(self) -> None:
        self.registry.register(BuiltinDictionaryPlugin(), kernel=self)
        self.registry.register(GVLTableParser(), kernel=self)
        self.registry.register(IOTableParser(), kernel=self)
        self.registry.register(MitsubishiGXWorks3Parser(), kernel=self)
        self.registry.register(GVLCsvExporter(), kernel=self)
        self.registry.register(IOCsvExporter(), kernel=self)
        self.registry.register(MitsubishiGXWorks3Exporter(), kernel=self)
        self.registry.register(MarkdownReportExporter(), kernel=self)
        self.engine.invalidate_cache()

    def register_plugin(self, plugin: BasePlugin) -> None:
        self.registry.register(plugin, kernel=self)
        if isinstance(plugin, DictionaryProviderPlugin):
            self.engine.invalidate_cache()

    # 兼容快捷别名
    register = register_plugin

    def unregister_plugin(self, plugin_id: str) -> Optional[BasePlugin]:
        """注销已注册插件；若该插件提供词典扩展，则主动触发翻译引擎缓存失效"""
        plugin = self.registry.unregister(plugin_id)
        if plugin and isinstance(plugin, DictionaryProviderPlugin):
            self.engine.invalidate_cache()
        return plugin

    # 兼容快捷别名
    unregister = unregister_plugin

    def load_plugin_file(self, file_path: str) -> List[BasePlugin]:
        plugins = self.registry.load_from_file(file_path, kernel=self)
        if any(isinstance(p, DictionaryProviderPlugin) for p in plugins):
            self.engine.invalidate_cache()
        return plugins

    def load_plugins_dir(self, dir_path: str) -> List[BasePlugin]:
        plugins = self.registry.load_from_directory(dir_path, kernel=self)
        if any(isinstance(p, DictionaryProviderPlugin) for p in plugins):
            self.engine.invalidate_cache()
        return plugins

    def parse(self, file_path: str, encoding: str = "gbk") -> TableDocument:
        with open(file_path, "rb") as f:
            header_bytes = f.read(1024)

        parsers = self.registry.get_plugins_by_type(TableParserPlugin)
        for parser in parsers:
            if parser.can_parse(file_path, header_bytes):
                return parser.parse(file_path, encoding=encoding)
        raise ValueError(f"未找到可处理该文件格式的解析器插件: {file_path}")

    def translate_text(self, text: str, custom_dict: Optional[Dict[str, str]] = None, target_lang: str = "en") -> str:
        return self.engine.translate(text, custom_dict=custom_dict, target_lang=target_lang)

    def derive_chinese_comment(self, var_name: str, existing_comment: str) -> str:
        return self.engine.derive_chinese_comment(var_name, existing_comment)

    def export(self, doc: TableDocument, output_path: str, format_name: str = "csv", **kwargs) -> None:
        exporters = self.registry.get_plugins_by_type(TableExporterPlugin)
        for exporter in exporters:
            if exporter.can_export(format_name):
                exporter.export(doc, output_path, **kwargs)
                return
        raise ValueError(f"未找到支持格式 '{format_name}' 的导出器插件: {output_path}")

    def verify(self, src_path: str, tgt_path: str, mode: str = "B", is_var_table: bool = True,
               context: Optional[Dict[str, Any]] = None) -> Tuple[bool, List[str]]:
        """执行 5 重核心断言质检并调度所有后置验证插件 (支持汇川与三菱)"""
        errors = []
        if not os.path.exists(tgt_path):
            return False, [f"目标交付文件不存在: {tgt_path}"]

        with open(src_path, "rb") as f1:
            src_bytes = f1.read()
        with open(tgt_path, "rb") as f2:
            tgt_bytes = f2.read()

        is_mitsubishi = (
            tgt_bytes.startswith(b'\xff\xfe') or
            tgt_bytes.startswith(b'\xfe\xff') or
            b'\t' in tgt_bytes[:1024]
        )

        if is_mitsubishi:
            src_lines = src_bytes.decode('utf-16', errors='replace').splitlines(keepends=False)
            tgt_lines = tgt_bytes.decode('utf-16', errors='replace').splitlines(keepends=False)
        else:
            src_lines = src_bytes.decode('gbk', errors='replace').splitlines(keepends=False)
            tgt_lines = tgt_bytes.decode('gbk', errors='replace').splitlines(keepends=False)

        # 1. Line count assertion
        if len(src_lines) != len(tgt_lines):
            errors.append(f"行数不吻合: 原始 {len(src_lines)} 行 != 目标 {len(tgt_lines)} 行")

        # 2. CRLF line ending assertion
        has_crlf = (b'\r\n' in tgt_bytes) or (b'\r\x00\n\x00' in tgt_bytes)
        if not has_crlf:
            errors.append("未检测到 Windows CRLF (\\r\\n) 换行符")

        # 3. CSV/TSV 格式与数据保真检查
        sep = '\t' if is_mitsubishi else ','
        start_row = 3 if (is_mitsubishi and len(src_lines) > 2 and '\t' not in src_lines[0]) else 2
        for idx in range(start_row, min(len(src_lines), len(tgt_lines)) + 1):
            sl = src_lines[idx - 1]
            tl = tgt_lines[idx - 1]
            if not tl.strip():
                continue
            sp = [p.strip().strip('"') for p in sl.split(sep)]
            tp = [p.strip().strip('"') for p in tl.split(sep)]

            if is_var_table:
                if is_mitsubishi:
                    if len(tp) < 15:
                        errors.append(f"第 {idx} 行 TSV 列数不足: {len(tp)} 列")
                        break
                    if mode == "B" and len(sp) > 1 and len(tp) > 1:
                        if sp[1] != tp[1]:
                            errors.append(f"第 {idx} 行标签名被意外修改: '{sp[1]}' -> '{tp[1]}'")
                            break
                    # 检查交付列中文残留 (Col 13 English 或 Col 18 Italian 或 Col 7 注释)
                    en_c = tp[13] if len(tp) > 13 else ""
                    it_c = tp[18] if len(tp) > 18 else ""
                    comm_c = tp[7] if len(tp) > 7 else ""
                    check_c = en_c or it_c or comm_c
                    m_ch = re.search(r'[\u4e00-\u9fff]', check_c)
                    if m_ch and (en_c or it_c):
                        errors.append(f"第 {idx} 行交付多语言列包含中文字符 [{m_ch.group()}]: {check_c}")
                        break
                else:
                    if len(tp) < 9:
                        errors.append(f"第 {idx} 行 CSV 列数不足 9 列: {len(tp)} 列")
                        break
                    if mode == "B" and len(sp) > 1 and len(tp) > 1:
                        if sp[1] != tp[1]:
                            errors.append(f"第 {idx} 行变量名被意外修改: '{sp[1]}' -> '{tp[1]}'")
                            break
                    if len(tp) > 7:
                        comment = tp[7]
                        m_ch = re.search(r'[\u4e00-\u9fff]', comment)
                        if m_ch:
                            errors.append(f"第 {idx} 行注释列包含中文字符 [{m_ch.group()}]: {comment}")
                            break
            else:
                # IO 注释表检查
                c_idx = 1 if is_mitsubishi else (7 if len(tp) >= 8 else 1)
                if len(tp) > c_idx:
                    comment = tp[c_idx]
                    m_ch = re.search(r'[\u4e00-\u9fff]', comment)
                    if m_ch:
                        errors.append(f"第 {idx} 行 IO 注释列包含中文字符 [{m_ch.group()}]: {comment}")
                        break

        # 4. 执行所有已注册的后置校验插件 (PostVerifyRulePlugin SPI)
        verify_context = context or {}
        verify_context.update({"mode": mode, "is_var_table": is_var_table, "kernel": self})
        try:
            doc = self.parse(tgt_path, encoding="gbk")
        except Exception:
            doc = TableDocument(file_path=tgt_path, table_type="var" if is_var_table else "io")

        rule_plugins = self.registry.get_plugins_by_type(PostVerifyRulePlugin)
        for rp in rule_plugins:
            try:
                ok, rule_errs = rp.verify(src_path, tgt_path, doc, verify_context)
                if not ok:
                    errors.extend(rule_errs)
            except Exception as ex:
                errors.append(f"校验插件 [{rp.plugin_id}] 发生异常: {ex}")

        return (len(errors) == 0), errors


def find_plugins_dir() -> Optional[str]:
    """智能查找标准 plugins/ 扩展目录"""
    curr = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(os.path.dirname(curr), "plugins"),
        os.path.join(curr, "plugins"),
        os.path.join(os.getcwd(), "plugins"),
        os.path.join(os.getcwd(), "自动翻译与规范化工具_Workflow", "plugins"),
    ]
    for c in candidates:
        if os.path.isdir(c):
            return c
    return None

def auto_load_domain_plugins(kernel: Kernel) -> None:
    """自动挂载核心机台专有领域词典插件 (修边机与意大利光伏边框产线)"""
    pdir = find_plugins_dir()
    if not pdir:
        return
    for fn in ["trimmer_dictionary_plugin.py", "solar_frame_dictionary_plugin.py"]:
        fp = os.path.join(pdir, fn)
        if os.path.isfile(fp):
            try:
                kernel.load_plugin_file(fp)
            except Exception:
                pass

# 全局默认单例微内核实例
_DEFAULT_KERNEL = Kernel()

def get_default_kernel() -> Kernel:
    return _DEFAULT_KERNEL



# =============================================================================
# 6. Python API 100% 向后兼容门面层 (Legacy Backward Compatibility Facades)
# =============================================================================

class IndustrialTermEngine:
    """工业自动化术语与翻译引擎 (100% 兼容历史 API 与属性访问)"""

    def __init__(self, custom_dict: Optional[Dict[str, str]] = None, kernel: Optional[Kernel] = None):
        self.kernel = kernel or get_default_kernel()
        # 兼容历史属性直接访问 self.exact_phrases 和 self.word_pairs
        self.exact_phrases: Dict[str, str] = dict(BUILTIN_EXACT_PHRASES)
        self.word_pairs: List[Tuple[str, str]] = list(BUILTIN_WORD_PAIRS)
        self.custom_dict: Dict[str, str] = dict(custom_dict) if custom_dict else {}

        if custom_dict:
            for k, v in custom_dict.items():
                self.exact_phrases[k] = v

        self.word_pairs.sort(key=lambda x: len(x[0]), reverse=True)

    def translate(self, text: str, target_lang: str = "en") -> str:
        """纯英文/多语言翻译引擎：输入任意中文或中英混杂文本，返回目标语言翻译"""
        if not text:
            return ""
        s = text.strip()
        if not re.search(r'[\u4e00-\u9fff]', s):
            return s

        # 用户显式传入的自定义字典具有最高仲裁权
        if self.custom_dict and s in self.custom_dict:
            return self.custom_dict[s]

        # 若用户手动向 engine.exact_phrases 注入了非内置自定义词条
        if s in self.exact_phrases and self.exact_phrases.get(s) != BUILTIN_EXACT_PHRASES.get(s):
            return self.exact_phrases[s]

        # 委托给微内核翻译引擎
        if self.kernel:
            return self.kernel.translate_text(s, custom_dict=self.custom_dict, target_lang=target_lang)

        if s in self.exact_phrases:
            return self.exact_phrases[s]

        return s

    def derive_chinese_comment(self, var_name: str, existing_comment: str) -> str:
        """为规范中文版补齐中文注释"""
        return self.kernel.derive_chinese_comment(var_name, existing_comment)


class VarTableProcessor:
    """GVL 全局变量表 (9列结构 / 27列结构) 处理与转换器 (100% 兼容历史 API)"""

    def __init__(self, mode: str = "B", term_engine: Optional[IndustrialTermEngine] = None, kernel: Optional[Kernel] = None):
        self.mode = mode.upper()
        self.kernel = kernel or get_default_kernel()
        self.term_engine = term_engine or IndustrialTermEngine(kernel=self.kernel)

    def process_file(self, src_path: str, dst_en_path: str, dst_cn_path: Optional[str] = None,
                     platform: str = "auto", target_lang: str = "en") -> List[Tuple]:
        """
        处理单个 GVL 变量表文件 (支持汇川 9 列 CSV 与三菱 GX Works3 27 列 TSV)
        返回该文件的逐行变更记录列表: [(序号, 变量名, 数据类型, 规范中文注释, 交付英文注释), ...]
        """
        actual_plat = detect_table_platform(src_path) if platform == "auto" else platform
        doc = self.kernel.parse(src_path)
        file_records = []

        for row in doc.rows:
            if not row.raw_line.strip():
                continue
            if actual_plat in ["inovance", "autoshop", "inoproshop"] and len(row.raw_parts) < 8:
                continue

            no = row.no
            var = row.name
            dtype = row.data_type
            old_c = row.comment

            # 1. 规范中文注释推导
            new_cn_c = self.term_engine.derive_chinese_comment(var, old_c)

            # 2. 交付注释翻译
            if old_c:
                new_en_c = self.term_engine.translate(old_c, target_lang=target_lang)
            elif re.search(r'[\u4e00-\u9fff]', var):
                new_en_c = self.term_engine.translate(var, target_lang=target_lang)
            else:
                new_en_c = ""

            # 逗号转义清洗
            new_en_c_clean = new_en_c.replace(',', ' / ').replace('，', ' / ')
            new_cn_c_clean = new_cn_c.replace(',', '，')

            row.extra["new_cn_c"] = new_cn_c_clean
            row.extra["new_en_c"] = new_en_c_clean
            if self.mode == "A":
                row.extra["new_en_var"] = self.term_engine.translate(var, target_lang=target_lang).replace(' ', '_')

            file_records.append((no, var, dtype, new_cn_c_clean, new_en_c_clean))

        # 根据平台类型智能导出
        if actual_plat == "mitsubishi":
            self.kernel.export(doc, dst_en_path, format_name="mitsubishi", target_lang=target_lang)
            if dst_cn_path:
                self.kernel.export(doc, dst_cn_path, format_name="mitsubishi", target_lang="cn", update_comment_col=False)
        else:
            self.kernel.export(doc, dst_en_path, format_name="gvl_csv", mode=self.mode, is_chinese_backup=False)
            if dst_cn_path:
                self.kernel.export(doc, dst_cn_path, format_name="gvl_csv", mode=self.mode, is_chinese_backup=True)

        return file_records

    def process_directory(self, src_dir: str, dst_en_dir: str, dst_cn_dir: Optional[str] = None,
                          report_md_path: Optional[str] = None, project_title: str = "Corning Delivery",
                          platform: str = "auto", target_lang: str = "en") -> Dict[str, List[Tuple]]:
        """批量处理整个目录下的全部变量表 CSV/TSV 文件，并可选生成统一 Markdown 对照表"""
        os.makedirs(dst_en_dir, exist_ok=True)
        if dst_cn_dir:
            os.makedirs(dst_cn_dir, exist_ok=True)

        all_records = {}
        csv_files = [f for f in sorted(os.listdir(src_dir)) if f.endswith(('.csv', '.tsv')) and not f.endswith('_new.csv')]

        print(f"\n[VarTableProcessor] 启动批量处理: 共 {len(csv_files)} 个变量表文件")
        for fname in csv_files:
            src_fp = os.path.join(src_dir, fname)
            dst_en_fp = os.path.join(dst_en_dir, fname)
            dst_cn_fp = os.path.join(dst_cn_dir, fname) if dst_cn_dir else None

            records = self.process_file(src_fp, dst_en_fp, dst_cn_fp, platform=platform, target_lang=target_lang)
            all_records[fname] = records
            print(f"  -> 完成: {fname:24s} | 数据行数: {len(records):5d}")

        if report_md_path:
            self.generate_markdown_report(all_records, report_md_path, project_title)

        return all_records

    def generate_markdown_report(self, all_records: Dict[str, List[Tuple]], report_path: str,
                                 project_title: str = "Corning Project CT173") -> None:
        """生成单一、完整的中英文对照交付总表 (含文首交互式目录与锚点)"""
        exporter = MarkdownReportExporter()
        exporter.generate_report(all_records, report_path, project_title=project_title, mode=self.mode)


class IOTableProcessor:
    """IO 注释表 (软元件位/字映射) 处理与转换器 (100% 兼容历史 API)"""

    def __init__(self, term_engine: Optional[IndustrialTermEngine] = None, kernel: Optional[Kernel] = None):
        self.kernel = kernel or get_default_kernel()
        self.term_engine = term_engine or IndustrialTermEngine(kernel=self.kernel)

    def process_file(self, src_path: str, dst_en_path: str, dst_cn_path: Optional[str] = None,
                     platform: str = "auto", target_lang: str = "en") -> List[Tuple]:
        """处理单个 IO 注释文件 (以 软元件地址,注释 为核心)"""
        actual_plat = detect_table_platform(src_path) if platform == "auto" else platform
        doc = self.kernel.parse(src_path)
        records = []

        for row in doc.rows:
            if not row.raw_line.strip() or not row.raw_parts:
                continue

            parts = row.raw_parts
            if actual_plat == "mitsubishi":
                addr = parts[0].strip() if len(parts) > 0 else ""
                old_c = parts[1].strip() if len(parts) > 1 else ""
            else:
                c_idx = row.extra.get("c_idx", 7 if len(parts) >= 8 else 1)
                addr = parts[0].strip() if len(parts) > 0 else ""
                old_c = parts[c_idx].strip() if len(parts) > c_idx else ""

            new_en_c = self.term_engine.translate(old_c, target_lang=target_lang).replace(',', ' / ')
            new_cn_c = old_c.replace(',', '，')

            row.extra["new_en_c"] = new_en_c
            row.extra["new_cn_c"] = new_cn_c
            records.append((addr, old_c, new_en_c))

        if actual_plat == "mitsubishi":
            self.kernel.export(doc, dst_en_path, format_name="mitsubishi", target_lang=target_lang)
            if dst_cn_path:
                self.kernel.export(doc, dst_cn_path, format_name="mitsubishi", target_lang="cn")
        else:
            self.kernel.export(doc, dst_en_path, format_name="io_csv", is_chinese_backup=False)
            if dst_cn_path:
                self.kernel.export(doc, dst_cn_path, format_name="io_csv", is_chinese_backup=True)

        return records


class TableVerifier:
    """严苛自动化验收与质检模块 (100% 兼容历史 API)"""

    @staticmethod
    def verify_file(src_path: str, target_path: str, mode: str = "B", is_var_table: bool = True,
                    kernel: Optional[Kernel] = None) -> Tuple[bool, List[str]]:
        """对单个文件执行 5 重核心质量检测 + 插件后置规则"""
        k = kernel or get_default_kernel()
        return k.verify(src_path, target_path, mode=mode, is_var_table=is_var_table)

    @classmethod
    def verify_directory(cls, src_dir: str, target_dir: str, mode: str = "B", is_var_table: bool = True,
                         kernel: Optional[Kernel] = None) -> bool:
        """对整个目录执行全量自动化验收"""
        k = kernel or get_default_kernel()
        print(f"\n================ 启动自动化质量验收 ({target_dir}) ================")
        all_passed = True
        files = [f for f in sorted(os.listdir(src_dir)) if f.endswith('.csv')]

        for fname in files:
            sp = os.path.join(src_dir, fname)
            tp = os.path.join(target_dir, fname)
            ok, errs = cls.verify_file(sp, tp, mode=mode, is_var_table=is_var_table, kernel=k)
            if ok:
                print(f"[PASS] {fname:24s} | 校验项全部通过 (行数吻合 / CRLF / 9列保真 / 0中文残留)")
            else:
                all_passed = False
                print(f"[FAIL] {fname:24s} | 发现异常:")
                for e in errs:
                    print(f"       ! {e}")

        print("-----------------------------------------------------------------")
        if all_passed:
            print(f"FINAL RESULT: ALL {len(files)} FILES PASSED 100% QUALITY CHECKS!\n")
        else:
            print("FINAL RESULT: VERIFICATION FAILED!\n")
        return all_passed


# 自动挂载领域插件至全局默认微内核 (在所有 Facade 类定义完毕后安全执行，避免循环引用)
auto_load_domain_plugins(_DEFAULT_KERNEL)


# =============================================================================
# 7. CLI 命令行主入口 (Command-Line Interface)
# =============================================================================

def _add_plugin_args(p: argparse.ArgumentParser, is_subparser: Optional[bool] = None) -> None:
    """为解析器注册 --plugin 与 --plugins-dir 参数。

    针对子解析器使用 default=argparse.SUPPRESS，避免子解析器未传参时静默用默认值覆写父级命名空间中的有效入参。
    """
    if is_subparser is None:
        # 自动探测是否为子解析器（子解析器的 prog 通常包含空格，如 'plc_table_toolkit.py vars'）
        is_subparser = (" " in getattr(p, "prog", ""))

    if is_subparser:
        p.add_argument("--plugin", action="append", default=argparse.SUPPRESS, help="加载外部第三方 Python 插件文件 (.py)")
        p.add_argument("--plugins-dir", default=argparse.SUPPRESS, help="加载指定目录下所有插件文件 (.py)")
    else:
        p.add_argument("--plugin", action="append", default=[], help="加载外部第三方 Python 插件文件 (.py)")
        p.add_argument("--plugins-dir", default=None, help="加载指定目录下所有插件文件 (.py)")


def main():
    parser = argparse.ArgumentParser(description="PLC 工业表格通用规范化与翻译微内核套件 (API & CLI & Plugin SPI)")
    _add_plugin_args(parser, is_subparser=False)
    subparsers = parser.add_subparsers(dest="command", help="子命令: vars, io, verify, machine")

    # Command: vars
    p_vars = subparsers.add_parser("vars", help="批量翻译 GVL 变量表")
    p_vars.add_argument("--src-dir", required=True, help="源变量表目录")
    p_vars.add_argument("--dst-dir", required=True, help="目标英文交付目录")
    p_vars.add_argument("--backup-cn", default=None, help="规范中文备份目录")
    p_vars.add_argument("--mode", default="B", choices=["A", "B"], help="方案 B(默认，保持变量名不变) / 方案 A(变量名英化)")
    p_vars.add_argument("--report", default=None, help="输出统一 Markdown 对照表文件路径")
    p_vars.add_argument("--title", default="Corning Project Delivery", help="报告标题")
    _add_plugin_args(p_vars, is_subparser=True)

    # Command: io
    p_io = subparsers.add_parser("io", help="批量翻译 IO 注释表")
    p_io.add_argument("--src-dir", required=True, help="源 IO 注释表目录")
    p_io.add_argument("--dst-dir", required=True, help="目标交付目录")
    p_io.add_argument("--backup-cn", default=None, help="规范中文备份目录")
    _add_plugin_args(p_io, is_subparser=True)

    # Command: verify
    p_ver = subparsers.add_parser("verify", help="全量质量验收测试")
    p_ver.add_argument("--src", required=True, help="原始留档目录")
    p_ver.add_argument("--target", required=True, help="待检测交付目录")
    p_ver.add_argument("--type", default="var", choices=["var", "io"], help="表格类型: var / io")
    p_ver.add_argument("--mode", default="B", choices=["A", "B"], help="交付方案: A / B")
    _add_plugin_args(p_ver, is_subparser=True)

    # Command: machine
    p_mac = subparsers.add_parser("machine", help="整台机器一键批量处理")
    p_mac.add_argument("--machine-dir", required=True, help="机器根目录 (如 .../康宁/2-撕胶带机)")
    p_mac.add_argument("--mode", default="B", choices=["A", "B"], help="交付方案: A / B")
    _add_plugin_args(p_mac, is_subparser=True)

    args = parser.parse_args()

    # 动态加载外部插件
    kernel = get_default_kernel()
    plugin_files = getattr(args, "plugin", []) or []
    plugins_dir = getattr(args, "plugins_dir", None)

    for pf in plugin_files:
        if pf:
            kernel.load_plugin_file(pf)
    if plugins_dir:
        kernel.load_plugins_dir(plugins_dir)

    if args.command == "vars":
        proc = VarTableProcessor(mode=args.mode, kernel=kernel)
        proc.process_directory(args.src_dir, args.dst_dir, args.backup_cn, report_md_path=args.report, project_title=args.title)
    elif args.command == "io":
        proc = IOTableProcessor(kernel=kernel)
        for fname in sorted(os.listdir(args.src_dir)):
            if fname.endswith(".csv"):
                sp = os.path.join(args.src_dir, fname)
                dp = os.path.join(args.dst_dir, fname)
                cp = os.path.join(args.backup_cn, fname) if args.backup_cn else None
                proc.process_file(sp, dp, cp)
        print("IO 表格批量处理完成！")
    elif args.command == "verify":
        is_var = (args.type == "var")
        ok = TableVerifier.verify_directory(args.src, args.target, mode=args.mode, is_var_table=is_var, kernel=kernel)
        sys.exit(0 if ok else 1)
    elif args.command == "machine":
        # One-click machine processor
        m_dir = args.machine_dir
        var_src = os.path.join(m_dir, "io注释_备份_原始留档", "变量表")
        var_dst = os.path.join(m_dir, "变量表")
        var_cn = os.path.join(m_dir, "io注释_备份_规范中文版", "变量表")
        report_md = os.path.join(var_dst, "变量表中英文对照表_Corning交付版.md")

        if os.path.exists(var_src):
            proc = VarTableProcessor(mode=args.mode, kernel=kernel)
            proc.process_directory(var_src, var_dst, var_cn, report_md_path=report_md, project_title=os.path.basename(m_dir))
            TableVerifier.verify_directory(var_src, var_dst, mode=args.mode, is_var_table=True, kernel=kernel)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
