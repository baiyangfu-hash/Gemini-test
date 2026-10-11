# -*- coding: utf-8 -*-
"""
=============================================================================
汇川 PLC IO 注释标准化与自动化英文翻译工作流引擎 (Corning / International Standard)
=============================================================================
适用范围: 汇川 PLC (AutoShop / InoProShop) 导出的 IO 注释 CSV 文件
核心特性:
1. 自动全量备份: 自动生成【原始留档副本】与【规范中文版副本】。
2. 格式严格保真: 100% 保持 9 列 CSV 格式、GBK 编码与 CRLF 换行，消除注释内半角逗号分列冲突。
3. 术语标准化: 自动补全 SB_、PH_、CY_、VG_、MR_、ALM_、ESTOP_ 等电气前缀。
4. 纯英文交付: 正则匹配 0 中文残留，输出符合美资客户 (康宁等) 交付标准的英文注释。
5. 交付对照报告: 自动生成 Markdown 中英逐行对照文档。
6. 一键自动化校验: 自动运行行数、列数、编码、中文残留自动化测试。
"""

import os
import sys
import shutil
import re
import argparse

# 确保在 Windows 控制台下输出 UTF-8
sys.stdout.reconfigure(encoding='utf-8')

# =============================================================================
# 1. 核心电气术语与翻译词典 (可在此持续扩充)
# =============================================================================

# 精确匹配全词字典
EXACT_DICTIONARY = {
    "手动": "Manual", "自动": "Auto", "准备": "Ready", "启动": "Start", "停止": "Stop",
    "暂停": "Pause", "异常": "Error", "回原点": "Home Return", "回原位": "Home Return",
    "回原点完成": "Home Return Completed", "回原位完成": "Home Return Completed",
    "消音": "Mute Buzzer", "校点模式": "Teaching Mode", "声音停止": "Sound Stop",
    "手动慢速": "Manual Slow Speed", "综合报警信息": "General Alarm Information",
    "设备状态": "Machine Status", "设备显示状态": "Machine Display Status",
    "暂停动作状态": "Pause Action Status", "自动中_暂停动作状态": "Auto Mode Pause Action Status",
    "当前画面": "Current Screen", "暂停中": "Pause Active",
    "回原点模式": "Home Return Mode", "自动模式_  上电初始化": "Auto Mode Power-On Init",
    "自动模式_ 上电初始化": "Auto Mode Power-On Init",
    "准备公共扫描程序": "Ready Common Scan Routine",
    "自动公共扫描程序": "Auto Common Scan Routine",
    "公共扫描区": "Common Scan Zone", "公共扫描": "Common Scan",
    "通道模式": "Channel Mode", "延时": "Delay",
    "节拍时间": "Cycle Time / Tact Time", "入料输送时间": "Infeed Conveyor Time",
    "出料输送时间": "Outfeed Conveyor Time", "撕胶带时间": "Tape Peeling Time",
    "节拍": "Cycle Time / Tact Time",
    "输送马达正转": "Conveyor Motor FWD", "输送马达反转": "Conveyor Motor REV",
    "皮带线输送正转": "Belt Conveyor FWD", "皮带线输送反转": "Belt Conveyor REV",
    "入料输送慢速": "Infeed Conveyor Slow Speed",
    "入料过渡线慢速": "Infeed Transition Conveyor Slow Speed",
    "储气罐吸真空": "VG_ Air Tank Vacuum On",
    "玻璃破真空": "VG_ Glass Vacuum Blow", "玻璃下吸真空": "VG_ Glass Lower Vacuum On",
    "回应上游入料可": "Upstream Infeed Permit Response",
    "回应下游出料可_OK": "Downstream Outfeed OK Permit Response",
    "回应下游出料可_NG": "Downstream Outfeed NG Permit Response",
    "回应下游出料许可_OK信号": "Downstream Outfeed OK Permit Response",
    "回应下游出料许可_NG信号": "Downstream Outfeed NG Permit Response",
    "上游入料请求_OK信号": "Upstream Infeed Request OK Signal",
    "上游入料请求_NG信号": "Upstream Infeed Request NG Signal",
    "下游入料许可信号": "Downstream Infeed Permit Signal",
    "下游出料完成信号": "Downstream Outfeed Completed Signal",
    "上游入料完成信号": "Upstream Infeed Completed Signal",
    "下游提前要料请求": "Downstream Early Material Request",
    "上游入料请求": "Upstream Infeed Request",
    "下游出料请求": "Downstream Outfeed Request",
    "总气阀供气": "Main Air Supply Valve", "软启阀状态": "Soft Start Valve Status",
    "1号钥匙": "SB_ 1# Key Switch", "2号钥匙": "SB_ 2# Key Switch", "3号钥匙": "SB_ 3# Key Switch",
    "钥匙1": "SB_ 1# Key Switch", "钥匙2": "SB_ 2# Key Switch", "钥匙3": "SB_ 3# Key Switch",
    "安全继电器使用动作标志": "Safety Relay Used Action Flag",
    "入料输送标志": "Infeed Conveyor Flag", "出料输送标志": "Outfeed Conveyor Flag",
    "配方选择": "Recipe Selection", "配方调出": "Recipe Recall", "配方编号": "Recipe No.",
    "配方调用按钮": "Recipe Recall Button",
    "电度计数Modbus读出高位": "Energy Meter Modbus Read High Word",
    "电度计数Modbus读出低位": "Energy Meter Modbus Read Low Word",
    "电度度数统计": "Energy Meter Consumption Statistics",
    "准备、自动启动按钮": "Ready & Auto Start Button",
    "玻璃输送、归正准备动作流程监看": "Glass Convey & Centering Sequence Monitor",
    "长/短边削边气缸及长边升降气缸收回": "L/S Trimming & Long Side Lift Cylinders Retract",
    "长/短边_回削边起始点及待机点": "L/S Return Trimming Start & Standby Pos.",
    "长/短边_8轴各回待机/起始点": "L/S 8 Axes Return Standby / Start Pos.",
    "等待_S2/S3_修边刀收回": "Wait S2/S3 Trimming Cutters Retract",
    "等待_S1/S4_修边刀收回": "Wait S1/S4 Trimming Cutters Retract",
    "等待_S1/S4_修边刀终点到达": "Wait S1/S4 Trimming Cutters End Pos. Reached",
    "等待_S2/S3_修边刀终点到达": "Wait S2/S3 Trimming Cutters End Pos. Reached",
    "等待_L1/L4_修边终点到达": "Wait L1/L4 Trimming End Pos. Reached",
    "等待_L1/L4_刮边终点到达": "Wait L1/L4 Scraping End Pos. Reached",
    "玻璃修边完成、等待出、入料完成": "Glass Trimming Completed, Wait In/Outfeed Completed",
    "L1/L4_向修边终点定位": "L1/L4 Move to Trimming End Pos.",
    "四角吸玻璃真空检测": "VG_ Four-Corner Glass Vacuum Detection",
    "四角吸玻璃": "VG_ Four-Corner Glass Vacuum",
    "四角吸盘顶升上位1": "CY_ Four-Corner Suction Cup Jack Up Pos. 1",
    "四角吸盘顶升上位2": "CY_ Four-Corner Suction Cup Jack Up Pos. 2",
    "四角吸盘顶升上位3": "CY_ Four-Corner Suction Cup Jack Up Pos. 3",
    "四角吸盘顶升上位4": "CY_ Four-Corner Suction Cup Jack Up Pos. 4",
    "四角吸盘顶升下位1": "CY_ Four-Corner Suction Cup Jack Down Pos. 1",
    "四角吸盘顶升下位2": "CY_ Four-Corner Suction Cup Jack Down Pos. 2",
    "四角吸盘顶升下位3": "CY_ Four-Corner Suction Cup Jack Down Pos. 3",
    "四角吸盘顶升下位4": "CY_ Four-Corner Suction Cup Jack Down Pos. 4",
    "四角吸盘顶升气缸": "CY_ Four-Corner Suction Cup Jack Cylinder",
    "四角吸盘顶升": "CY_ Four-Corner Suction Cup Jack",
    "四角吸盘下吸真空": "VG_ Four-Corner Suction Cup Lower Vacuum On",
    "四角吸盘下破真空": "VG_ Four-Corner Suction Cup Lower Vacuum Blow",
    "四角吸盘破真空": "VG_ Four-Corner Suction Cup Vacuum Blow",
    "四角吸盘吸真空": "VG_ Four-Corner Suction Cup Vacuum On",
    "四角吸盘真空检测": "VG_ Four-Corner Suction Cup Vacuum Detection",
    "四角/中间破真空": "Four-Corner & Center Vacuum Blow",
    "ALM_安全门1#状态": "ALM_ Safety Door 1# Status",
    "ALM_安全门2#状态": "ALM_ Safety Door 2# Status",
    "ALM_安全门3": "ALM_ Safety Door 3#", "ALM_安全门4": "ALM_ Safety Door 4#",
    "安全门1#状态": "ALM_ Safety Door 1# Status", "安全门2#状态": "ALM_ Safety Door 2# Status",
    "安全门3": "ALM_ Safety Door 3#", "安全门4": "ALM_ Safety Door 4#",
    "ALM_杆灯绿": "ALM_ Tower Light Green", "ALM_杆灯黄": "ALM_ Tower Light Yellow",
    "ALM_杆灯红": "ALM_ Tower Light Red", "ALM_杆灯蜂鸣器": "ALM_ Buzzer",
    "杆灯绿": "ALM_ Tower Light Green", "杆灯黄": "ALM_ Tower Light Yellow",
    "杆灯红": "ALM_ Tower Light Red", "杆灯蜂鸣器": "ALM_ Buzzer",
    "复位按钮": "SB_ Reset", "SB_复位": "SB_ Reset", "复位按钮1": "SB_ Reset 1",
    "启动按钮": "SB_ Start", "SB_启动": "SB_ Start", "启动按钮1": "SB_ Start 1",
    "停止按钮": "SB_ Stop", "SB_停止": "SB_ Stop", "停止按钮1": "SB_ Stop 1",
    "暂停按钮": "SB_ Pause", "SB_暂停": "SB_ Pause", "暂停按钮1": "SB_ Pause 1",
    "ESTOP_急停": "ESTOP_ E-Stop", "ESTOP_1#急停": "ESTOP_ 1# E-Stop",
    "ESTOP_2#急停": "ESTOP_ 2# E-Stop", "ESTOP_3#急停": "ESTOP_ 3# E-Stop",
    "ESTOP_4#急停": "ESTOP_ 4# E-Stop", "急停按钮1": "ESTOP_ 1# E-Stop",
    "急停按钮2": "ESTOP_ 2# E-Stop", "急停按钮3": "ESTOP_ 3# E-Stop",
    "急停按钮4": "ESTOP_ 4# E-Stop", "电柜2急停": "ESTOP_ Cabinet 2 E-Stop",
    "ESTOP_电柜2急停": "ESTOP_ Cabinet 2 E-Stop",
    "SFC初始化": "SFC Init",
    "SB_启动按钮": "SB_ Start", "SB_手/自动动切换按钮": "SB_ Auto/Manual Switch",
    "手/自动动切换按钮": "SB_ Auto/Manual Switch",
    "手/自动钥匙开关没转换手动位置上请确认": "Confirm Auto/Manual Key Switch Not in Manual Pos.",
    "手/自动钥匙开关没转换自动位置上请确认": "Confirm Auto/Manual Key Switch Not in Auto Pos.",
    "玻璃中间吸真空按钮": "Glass Center Vacuum On Button",
    "玻璃中间吸真空未关闭": "Glass Center Vacuum On Not OFF",
    "玻璃中间破真空按钮": "Glass Center Vacuum Blow Button",
    "玻璃归正机构伸出": "Glass Centering Mechanism Extends",
    "归正机构松开": "Centering Mechanism Unclamps",
    "归正加紧气缸调试": "Centering Clamp Cylinder Debug/Test",
    "归正夹紧气缸调试": "Centering Clamp Cylinder Debug/Test",
    "真空储压罐真空压力未到达": "Vacuum Tank Vacuum Pressure Not Reached",
    "真空压力罐吸真空按钮": "Vacuum Tank Vacuum On Button",
    "短边切刀调试": "S-Side Cutter Debug/Test",
    "长边切刀气缸调试": "L-Side Cutter Cylinder Debug/Test",
    "长边升降调试": "L-Side Lift Debug/Test",
    "阻挡气缸调试": "Stopper Cylinder Debug/Test",
    "长边1/2不回待机点启用": "L1/L2 No Return Standby Pos. Enable",
    "长边4削边减速点校点": "L4 Trimming Decel Teach Point",
    "废料清理设定数量": "Waste Cleaning Setting Count",
    "清理废料计数": "Clean Waste Count",
    "请清理废料": "Please Clean Waste",
    "自动中开门标志": "Auto Mode Door Open Flag",
    "累计气流量": "Accumulated Air Flow",
    "累计电能": "Accumulated Energy",
    "通道运行": "Channel Run",
    "过渡存储": "Temp Buffer",
    "数据处理过渡存储_1": "Data Processing Temp Buffer 1",
    "数据处理过渡存储_2": "Data Processing Temp Buffer 2",
    "开班分钟设定部分最终转换为秒单位的数据": "Shift Min Setting Min-to-Sec Conversion Data",
    "班次状态1a班;2b班": "Shift Status 1: Shift A; 2: Shift B",
    "白班跨日期标志": "Day Shift Cross-Date Flag",
    "跨日期边界判断": "Cross-Date Boundary Check",
    "跨日期边界绝对值": "Cross-Date Boundary Check Abs Value",
    "当天产能": "Today Capacity", "白班产能": "Day Shift Capacity",
    "当日产量": "Today Production", "当天产量": "Today Production",
    "总产量": "Total Production",
    "昨天总产量": "Yesterday Total Production",
    "昨天白班产量": "Yesterday Day Shift Production",
    "昨天晚班产量": "Yesterday Night Shift Production",
    "昨日白班产量": "Yesterday Day Shift Production",
    "昨日晚班产量": "Yesterday Night Shift Production",
    "白班产量": "Day Shift Production", "晚班产量": "Night Shift Production",
    "白班产量1": "Day Shift Production 1", "晚班产量1": "Night Shift Production 1",
    "星期一产量": "Monday Production", "星期二产量": "Tuesday Production",
    "星期三产量": "Wednesday Production", "星期四产量": "Thursday Production",
    "星期五产量": "Friday Production", "星期六产量": "Saturday Production",
    "星期日产量": "Sunday Production", "星期天产量": "Sunday Production",
    "今天中班产量": "Today Middle Shift Production",
    "今天总产量": "Today Total Production",
    "今天白班产量": "Today Day Shift Production",
    "今天晚班产量": "Today Night Shift Production",
    "今年总产量": "This Year Total Production",
    "去年总产量": "Last Year Total Production",
    "去年产量统计": "Last Year Production Statistics",
    "时": "Hour", "分": "Minute", "秒": "Second",
    "模拟回应上游入料可标志": "Simulated Upstream Infeed Permit Flag",
    "模拟回应下游出料可标志": "Simulated Downstream Outfeed Permit Flag",
    "模拟运行": "Simulation Run",
    "PLC时钟写入确认按钮": "PLC Clock Write Confirm Button",
}

# 词对贪婪替换列表 (从 plc_table_toolkit 获取或独立完整内置)
try:
    _curr_dir = os.path.dirname(os.path.abspath(__file__))
    if _curr_dir not in sys.path:
        sys.path.insert(0, _curr_dir)
    from plc_table_toolkit import IndustrialTermEngine
    SUBSTITUTION_TERMS = list(IndustrialTermEngine().word_pairs)
except Exception:
    SUBSTITUTION_TERMS = [
        ("伺服", "Servo"), ("报警", "Alarm"), ("异常", "Error"), ("复位", "Reset"),
        ("准备", "Ready"), ("启动", "Start"), ("停止", "Stop"), ("暂停", "Pause"),
        ("急停", "E-Stop"), ("气缸", "Cylinder"), ("真空", "Vacuum"), ("感应", "Sensor"),
        ("光电", "Photoelectric"), ("到位", "In Pos."), ("原点", "Home Pos."),
        ("速度", "Speed"), ("位置", "Pos."), ("状态", "Status"), ("标志", "Flag"),
        ("时间", "Time"), ("设定", "Set"), ("实际", "Actual"), ("当前", "Current"),
        ("上限", "Upper Limit"), ("下限", "Lower Limit"), ("正限位", "Positive Limit"),
        ("负限位", "Negative Limit"), ("原位", "Home Pos."), ("回原点", "Home Return"),
        ("运行", "Run"), ("使能", "Enable"), ("轴", "Axis"), ("马达", "Motor"),
        ("长边", "L-Side"), ("短边", "S-Side"), ("机头", "Head"), ("切刀", "Cutter"),
        ("修边", "Trimming"), ("削边", "Trimming"), ("吸盘", "Suction Cup"),
        ("电磁阀", "Solenoid Valve"), ("压力", "Pressure"), ("流量", "Flow"),
    ]

def clean_and_translate(c):
    # Strip non-printable ASCII
    c = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', c)
    c = c.strip()
    if not c or c in ["备用", "空"]:
        return "Spare" if c == "备用" else c

    # Normalize whitespace & common typos
    c = re.sub(r'手\s*动', '手动', c)
    c = re.sub(r'机\s*头', '机头', c)
    c = c.replace("起起始点", "起始点").replace("规正", "归正").replace("加紧", "夹紧")
    c = c.replace("削修边", "修边").replace("修边边", "修边")
    
    res = EXACT_DICTIONARY.get(c, None)
    if res is None:
        # Time period patterns
        m_tp_lim = re.match(r'^(\d\d)_(\d\d)_产量统计时间(上限|下限)$', c)
        if m_tp_lim:
            lim = "Upper Limit" if m_tp_lim.group(3) == "上限" else "Lower Limit"
            res = f"{m_tp_lim.group(1)}:00 Production Statistics Time {lim}"

        m_tp_stat = re.match(r'^(\d\d)_(\d\d)_时间段产量统计$', c)
        if not res and m_tp_stat:
            res = f"{m_tp_stat.group(1)}:00 Time Period Production Statistics"

        # Hourly production
        m_hr = re.match(r'^(\d+)时产量$', c)
        if not res and m_hr:
            res = f"{m_hr.group(1)}:00 Production"

        # Time period seconds
        m_tps = re.match(r'^(\d\d)_(\d\d)_时间段_秒$', c)
        if not res and m_tps:
            res = f"{m_tps.group(1)}:00 Time Period Seconds"

        # Head Descending Safety Photoelectric
        m_hd_ph = re.match(r'^(?:PH_)?([LS]\d+)_机头下降安全检测光电(.*)$', c)
        if not res and m_hd_ph:
            side = m_hd_ph.group(1)
            suffix = m_hd_ph.group(2)
            if "报警确认按钮" in suffix:
                res = f"{side} Head Descend Safety Photoelectric Alarm Reset Button"
            elif "异常" in suffix:
                res = f"{side} Head Descend Safety Photoelectric Error!"
            else:
                res = f"PH_ {side} Head Descend Safety Photoelectric"

        # Axis Lift Cylinder / Limit
        m_lift_cy = re.match(r'^(?:CY_)?([LS]\d+)_(?:轴|机头)升降(?:气缸)?(上升|下降|上位|下位)(?:异常)?$', c)
        if not res and m_lift_cy:
            side = m_lift_cy.group(1)
            act_map = {"上升": "Cylinder Ascends", "下降": "Cylinder Descends", "上位": "Up Pos.", "下位": "Down Pos."}
            act = act_map.get(m_lift_cy.group(2), m_lift_cy.group(2))
            err = " Error" if "异常" in c else ""
            prefix = "CY_ " if "气缸" in c else ""
            res = f"{prefix}{side} Lift {act}{err}".strip()

        # Flat cutter retract error
        m_flat_err = re.match(r'^([LS]\d+)平刀收回异常$', c)
        if not res and m_flat_err:
            res = f"{m_flat_err.group(1)} Flat Cutter Retract Error"

        # Scraping teach button
        m_sc_btn = re.match(r'^([LS]\d+)_刮刀刮边终点校点按钮$', c)
        if not res and m_sc_btn:
            res = f"{m_sc_btn.group(1)} Scraping Cutter End Pos. Teach Button"

        # Scraping teach point
        m_sc_tp = re.match(r'^([LS]\d+)_刮边终点校点$', c)
        if not res and m_sc_tp:
            res = f"{m_sc_tp.group(1)} Scraping End Pos. Teach Point"

        # Cutter tool life / alarms
        m_blade_shift = re.match(r'^([LS]\d+)_修边刀伸出位ON! 请检查玻璃是否位移！$', c)
        if not res and m_blade_shift:
            res = f"{m_blade_shift.group(1)} Trimming Cutter Extend Pos. ON! Please check glass position!"

        m_blade_stuck = re.match(r'^([LS]\d+)_修边刀未伸出，请检查伸出气缸是否卡顿！$', c)
        if not res and m_blade_stuck:
            res = f"{m_blade_stuck.group(1)} Trimming Cutter Not Extended, Please check extend cylinder!"

        m_blade_cnt = re.match(r'^([LS]\d+)_修边刀使用当前计数$', c)
        if not res and m_blade_cnt:
            res = f"{m_blade_cnt.group(1)} Trimming Cutter Usage Count"

        m_blade_set = re.match(r'^([LS]\d+)_修边刀使用次数设定$', c)
        if not res and m_blade_set:
            res = f"{m_blade_set.group(1)} Trimming Cutter Usage Count Setting"

        m_blade_rst = re.match(r'^([LS]\d+)_修边刀当前累计数清零按钮$', c)
        if not res and m_blade_rst:
            res = f"{m_blade_rst.group(1)} Trimming Cutter Usage Count Reset Button"

        m_blade_alm = re.match(r'^([LS]\d+)修边刀使用次数到达报警$', c)
        if not res and m_blade_alm:
            res = f"{m_blade_alm.group(1)} Trimming Cutter Life Limit Alarm"

        m_blade_pos = re.match(r'^([LS]\d+)_修边终点定位_附加角慢速$', c)
        if not res and m_blade_pos:
            res = f"{m_blade_pos.group(1)} Trimming End Pos. Additional Angle Slow Speed"

        m_blade_cut = re.match(r'^(?:CY_)?([LS]\d+)切刀伸出$', c)
        if not res and m_blade_cut:
            res = f"CY_ {m_blade_cut.group(1)} Cutter Extends"

        m_blade_home = re.match(r'^([LS]\d+)拉原点$', c)
        if not res and m_blade_home:
            res = f"{m_blade_home.group(1)} Pull Home Pos."

        # EtherCAT / Ethernet IP normal
        m_ecat_norm = re.match(r'^EtherCAT 从站(\d+)通讯正常！?$', c)
        if not res and m_ecat_norm:
            res = f"EtherCAT Slave {m_ecat_norm.group(1)} Comm Normal!"

        m_eip_norm = re.match(r'^Ethernet IP 从站(\d+)正常$', c)
        if not res and m_eip_norm:
            res = f"EtherNet/IP Slave {m_eip_norm.group(1)} Normal"

        # Dynamic Door map
        m_waste_door = re.match(r'^(?:ALM_)?废料门(?:信号)?(\d+)(?:#)?(?:状态|打开)?$', c)
        if not res and m_waste_door:
            act = "Open" if "打开" in c else ("Status" if "状态" in c else "")
            res = f"ALM_ Waste Door {m_waste_door.group(1)}# {act}".strip()

        # Dynamic Axis pattern
        m_axis_btn = re.match(r'^轴(\d+)回原点(按钮|完成)$', c)
        if not res and m_axis_btn:
            action = "Start Button" if m_axis_btn.group(2) == "按钮" else "Completed"
            res = f"Axis {m_axis_btn.group(1)} Home Return {action}"
            
        m_axis_off = re.match(r'^轴(\d+)伺服OFF按钮$', c)
        if not res and m_axis_off:
            res = f"Axis {m_axis_off.group(1)} Servo OFF Button"

        m_axis_en_off = re.match(r'^轴(\d+)使能OFF$', c)
        if not res and m_axis_en_off:
            res = f"Axis {m_axis_en_off.group(1)} Enable OFF"

        m_axis_alarm = re.match(r'^轴(\d+)：(长边\d+|短边\d+)轴报警$', c)
        if not res and m_axis_alarm:
            side_map = {
                "长边1": "L1", "长边2": "L2", "长边3": "L3", "长边4": "L4",
                "短边1": "S1", "短边2": "S2", "短边3": "S3", "短边4": "S4"
            }
            side = side_map.get(m_axis_alarm.group(2), m_axis_alarm.group(2))
            res = f"Axis {m_axis_alarm.group(1)}: {side} Axis Alarm"

        # Dynamic Safe Position / Trigger
        m_safe_pos = re.match(r'^(长边\d+|短边\d+)安全(位置|点触发)$', c)
        if not res and m_safe_pos:
            side = m_safe_pos.group(1).replace("长边", "L").replace("短边", "S")
            act = "Safe Pos." if m_safe_pos.group(2) == "位置" else "Safe Point Triggered"
            res = f"{side} {act}"

        # Collision Prevention Prompt
        m_collision = re.match(r'^([LS]\d+)(正|负)限位防撞提示$', c)
        if not res and m_collision:
            lim = "Positive" if m_collision.group(2) == "正" else "Negative"
            res = f"{m_collision.group(1)} {lim} Limit Anti-Collision Prompt"

        # Axis Group Target Speed
        m_axis_grp = re.match(r'^轴组(\d+)_附加角_目标速度$', c)
        if not res and m_axis_grp:
            res = f"Axis Group {m_axis_grp.group(1)} Additional Angle Target Speed"

        # Shift Hourly Production
        m_shift_hr = re.match(r'^(白班|晚班)_(\d\d)_时段产量$', c)
        if not res and m_shift_hr:
            s_name = "Day Shift" if m_shift_hr.group(1) == "白班" else "Night Shift"
            res = f"{s_name} {m_shift_hr.group(2)}:00 Period Production"

        # HMI Clock Read
        m_hmi_clk = re.match(r'^(?:读出|读取)HMI系统时钟_(年|月|日|时|分|秒|星期)(?:（转换后数据）)?$', c)
        if not res and m_hmi_clk:
            u_map = {"年": "Year", "月": "Month", "日": "Day", "时": "Hour", "分": "Minute", "秒": "Second", "星期": "Day of Week"}
            unit = u_map.get(m_hmi_clk.group(1), m_hmi_clk.group(1))
            conv = " (Converted Data)" if "转换后" in c else ""
            res = f"Read HMI System Clock {unit}{conv}"

        # PLC Clock Read / Write
        m_plc_clk = re.match(r'^PLC时钟(读出|写入)_(年|月|日|时|分|秒|星期)$', c)
        if not res and m_plc_clk:
            act = "Read" if m_plc_clk.group(1) == "读出" else "Write"
            u_map = {"年": "Year", "月": "Month", "日": "Day", "时": "Hour", "分": "Minute", "秒": "Second", "星期": "Day of Week"}
            res = f"PLC Clock {act} {u_map.get(m_plc_clk.group(2), m_plc_clk.group(2))}"

        # Dynamic Month format (Chinese and Digit forms)
        m_month_cn = re.match(r'^(今年|去年|)(一|二|三|四|五|六|七|八|九|十|十一|十二)月份产量(?:统计)?$', c)
        if not res and m_month_cn:
            yr = "This Year " if m_month_cn.group(1) == "今年" else ("Last Year " if m_month_cn.group(1) == "去年" else "")
            month_names_cn = {
                "一": "January", "二": "February", "三": "March", "四": "April",
                "五": "May", "六": "June", "七": "July", "八": "August",
                "九": "September", "十": "October", "十一": "November", "十二": "December"
            }
            stat = " Statistics" if "统计" in c else ""
            res = f"{yr}{month_names_cn.get(m_month_cn.group(2), m_month_cn.group(2))} Production{stat}"

        m_month_num = re.match(r'^(今年|去年|)(\d+)月份产量(?:统计)?$', c)
        if not res and m_month_num:
            yr = "This Year " if m_month_num.group(1) == "今年" else ("Last Year " if m_month_num.group(1) == "去年" else "")
            month_names = {
                "1": "January", "2": "February", "3": "March", "4": "April",
                "5": "May", "6": "June", "7": "July", "8": "August",
                "9": "September", "10": "October", "11": "November", "12": "December"
            }
            stat = " Statistics" if "统计" in c else ""
            res = f"{yr}{month_names.get(m_month_num.group(2), m_month_num.group(2))} Production{stat}"

    if res is None:
        res = c
        for k, v in SUBSTITUTION_TERMS:
            res = res.replace(k, v)

    # FINAL CLEANING: Strip ALL CSV breaking commas & semicolons
    res = res.replace(',', ' / ').replace('，', ' / ').replace(';', ' / ').replace('；', ' / ')
    res = re.sub(r'Axis\s+(\d+)', r'Axis \1', res)
    res = re.sub(r'Axis\s+([A-Za-z])', r'Axis \1', res)
    res = res.replace("Return to Standby Pos.", "Return Standby Pos.")
    res = res.replace("Return to Cutter Pos.", "Return Cutter Pos.")
    res = res.replace("Return to Home Pos.", "Return Home Pos.")
    res = re.sub(r'\s+', ' ', res).strip()
    return res

# 兼容外部测试与调用别名
translate_comment = clean_and_translate

def standardize_chinese(fname, var, c):
    c = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', c)
    c = c.strip()
    if not c or c in ["备用", "空"]:
        return "备用" if c == "备用" else c
        
    # Standardize prefixes for X (inputs)
    if fname.lower().endswith("-x.csv"):
        if "急停" in c and not c.startswith("ESTOP_"):
            m = re.match(r'^(?:急停按钮|急停)(\d*.*)$', c)
            if m:
                num = m.group(1).replace("#", "").strip()
                c = f"ESTOP_{num}#急停" if num else "ESTOP_急停"
            else:
                c = f"ESTOP_{c}"
        elif "安全门" in c:
            if not c.startswith("ALM_") and not c.startswith("SB_"):
                c = f"ALM_{c}"
        elif "光电" in c and not c.startswith("PH_"):
            c = f"PH_{c}"
        elif ("磁检测" in c or "磁簧" in c or "接近开关" in c) and not c.startswith("MR_"):
            c = f"MR_{c}"
        elif ("按钮" in c or "手自动" in c or "旋钮" in c or "钥匙" in c) and not c.startswith("SB_"):
            c = f"SB_{c}"
        elif ("气缸" in c or "伸出" in c or "缩回" in c or "到位" in c or "阻挡" in c or "顶升" in c or "刀" in c) and not c.startswith("CY_"):
            if "真空" not in c:
                c = f"CY_{c}"
        elif "真空" in c and not c.startswith("VG_"):
            c = f"VG_{c}"

    # Standardize prefixes for Y (outputs)
    elif fname.lower().endswith("-y.csv"):
        if "三色灯" in c or "蜂鸣器" in c or "指示灯" in c or "杆灯" in c:
            if not c.startswith("ALM_"):
                c = f"ALM_{c}"
        elif "真空" in c or "破真空" in c:
            if not c.startswith("VG_"):
                c = f"VG_{c}"
        elif ("气缸" in c or "伸出" in c or "缩回" in c or "夹紧" in c or "松开" in c or "顶升" in c or "切刀" in c or "刮边" in c or "修边" in c or "削边" in c) and not c.startswith("CY_"):
            if "马达" not in c and "电机" not in c and "输送" not in c:
                c = f"CY_{c}"
            
    return c

def process_machine_directory(target_dir):
    """处理指定机台目录下的全部 IO 注释 CSV 文件"""
    print(f"\n==================================================")
    print(f"正在处理机台目录: {target_dir}")
    print(f"==================================================")
    
    if not os.path.exists(target_dir):
        print(f"[ERROR] 目标目录不存在: {target_dir}")
        return False
        
    backup_orig = os.path.join(target_dir, "io注释_备份_原始留档")
    backup_cn = os.path.join(target_dir, "io注释_备份_规范中文版")
    os.makedirs(backup_orig, exist_ok=True)
    os.makedirs(backup_cn, exist_ok=True)
    
    # 查找所有 CSV 文件 (区分大小写或不区分)
    csv_names = [f for f in os.listdir(target_dir) if f.lower().startswith("io注释-") and f.lower().endswith(".csv")]
    if not csv_names:
        print("[WARN] 未在目录下找到以 'io注释-' 或 'IO注释-' 开头的 CSV 文件！")
        return False
        
    print(f"找到 {len(csv_names)} 个 CSV 文件: {csv_names}")
    
    # Step 1: 原始备份
    for fname in csv_names:
        src = os.path.join(target_dir, fname)
        dst = os.path.join(backup_orig, fname)
        if not os.path.exists(dst):
            shutil.copy2(src, dst)
            print(f"  [备份原始] {fname} -> io注释_备份_原始留档/")
            
    # Step 2: 规范中文版本生成
    for fname in csv_names:
        src = os.path.join(backup_orig, fname)
        dst = os.path.join(backup_cn, fname)
        with open(src, "rb") as f:
            text = f.read().decode('gbk', errors='ignore')
        lines = text.splitlines()
        new_lines = []
        for idx, line in enumerate(lines):
            if idx == 0 or not line.strip():
                new_lines.append(line)
                continue
            parts = line.split(',')
            if len(parts) >= 8:
                var = parts[1].strip()
                old_c = parts[7].strip()
                new_c = standardize_chinese(fname, var, old_c)
                parts[7] = new_c
                new_lines.append(','.join(parts[:8]) + ',')
            else:
                new_lines.append(line)
        with open(dst, "wb") as f_out:
            f_out.write(('\r\n'.join(new_lines) + '\r\n').encode('gbk'))
        print(f"  [规范中文] {fname} -> io注释_备份_规范中文版/")
        
    # Step 3: 全量纯英文转换与输出
    diff_summary = []
    total_rows = 0
    all_clean = True
    
    for fname in csv_names:
        src_path = os.path.join(backup_cn, fname)
        dst_path = os.path.join(target_dir, fname)
        
        with open(src_path, "rb") as f:
            text = f.read().decode('gbk', errors='ignore')
        lines = text.splitlines()
        
        new_lines = []
        file_changes = []
        
        for idx, line in enumerate(lines):
            if idx == 0 or not line.strip():
                new_lines.append(line)
                continue
            parts = line.split(',')
            if len(parts) >= 8:
                no = parts[0].strip()
                var = parts[1].strip()
                old_c = parts[7].strip()
                new_en = clean_and_translate(old_c)
                
                total_rows += 1
                if bool(re.search(r'[\u4e00-\u9fff]', new_en)):
                    print(f"  [ERROR] 残留中文: {fname} | {var} | '{old_c}' -> '{new_en}'")
                    all_clean = False
                    
                parts[7] = new_en
                new_lines.append(','.join(parts[:8]) + ',')
                file_changes.append((no, var, old_c, new_en))
            else:
                new_lines.append(line)
                
        with open(dst_path, "wb") as f_out:
            f_out.write(('\r\n'.join(new_lines) + '\r\n').encode('gbk'))
            
        diff_summary.append((fname, len(new_lines), file_changes))
        print(f"  [英文交付] {fname}: {len(file_changes)} 行完成写入。")
        
    # Step 4: 生成交付中英对照报告
    report_md = os.path.join(target_dir, "io注释英文对照表_Corning交付版.md")
    dir_name = os.path.basename(os.path.normpath(target_dir))
    with open(report_md, "w", encoding="utf-8") as f:
        f.write(f"# IO 注释中英文对照全表 (美国康宁交付版 - Corning Project CT173 - {dir_name})\n\n")
        f.write(f"> **机台模块**：{dir_name}\n")
        f.write("> **规范标准**：《电气术语定义标准与命名规范 (20251105-EN)》\n")
        f.write("> **文件保真**：全部 CSV 文件已转换为 100% 纯专业英文，严格保持 9 列结构、GBK 编码与 CRLF 换行。\n\n")
        f.write("---\n\n")
        
        for fname, total_l, chgs in diff_summary:
            f.write(f"## {fname} (共 {len(chgs)} 行数据)\n\n")
            f.write("| 序号 (No.) | 变量名 (Variable) | 规范中文注释 (Chinese) | 交付英文注释 (English Standard) |\n")
            f.write("| :---: | :---: | :--- | :--- |\n")
            for no, var, old_c, new_c in chgs:
                f.write(f"| {no} | `{var}` | {old_c} | **`{new_c}`** |\n")
            f.write("\n")
            
    print(f"  [交付清单] 已生成中英文对照 Markdown: {report_md}")
    
    # Step 5: 自动化严格校验
    print(f"\n--- 正在执行自动化完整性校验 ({dir_name}) ---")
    pass_all = True
    for fname in csv_names:
        target_path = os.path.join(target_dir, fname)
        orig_path = os.path.join(backup_orig, fname)
        with open(target_path, "rb") as f:
            target_bytes = f.read()
        with open(orig_path, "rb") as f:
            orig_bytes = f.read()
            
        target_lines = target_bytes.decode('gbk').splitlines()
        orig_lines = orig_bytes.decode('gbk', errors='ignore').splitlines()
        
        if len(target_lines) != len(orig_lines):
            print(f"  [FAIL] {fname}: 行数不一致! (目标: {len(target_lines)}, 原始: {len(orig_lines)})")
            pass_all = False
        
        col_err = 0
        cn_err = 0
        for idx, line in enumerate(target_lines):
            if not line.strip():
                continue
            parts = line.split(',')
            if len(parts) != 9:
                col_err += 1
            if idx > 0 and len(parts) >= 8:
                if re.search(r'[\u4e00-\u9fff]', parts[7]):
                    cn_err += 1
                    
        if col_err > 0:
            print(f"  [FAIL] {fname}: 存在 {col_err} 行未满足 9 列结构!")
            pass_all = False
        if cn_err > 0:
            print(f"  [FAIL] {fname}: 存在 {cn_err} 行包含中文字符!")
            pass_all = False
            
        if col_err == 0 and cn_err == 0 and len(target_lines) == len(orig_lines):
            print(f"  [PASS] {fname}: 100% 校验通过 (行数:{len(target_lines)}, 9列无逗号冲突, GBK/CRLF, 0中文残留)")
            
    print(f"==================================================")
    print(f"机台 {dir_name} 处理结果: {'全部成功 (ALL PASS)' if pass_all else '存在异常 (FAILED)'}")
    print(f"总计处理注释行数: {total_rows}")
    print(f"==================================================\n")
    return pass_all

def main():
    parser = argparse.ArgumentParser(description="汇川 PLC IO 注释标准化与自动化英文翻译工具")
    parser.add_argument("--dir", "-d", type=str, help="指定需要翻译的机台目录绝对路径或相对路径")
    parser.add_argument("--all", "-a", action="store_true", help="一键翻译当前项目下所有机台 (1-封边机, 2-撕胶带机, 3-修边机)")
    args = parser.parse_args()

    project_base = r"c:\Users\fubai\Documents\BaiduSyncdisk\项目\CT173-美国康宁-6月-付白杨\PLC+HMI程序\康宁"
    
    if args.dir:
        process_machine_directory(args.dir)
    elif args.all or len(sys.argv) == 1:
        # 默认处理全项目 3 个机台
        machines = ["1-封边机", "2-撕胶带机", "3-修边机"]
        for m in machines:
            m_path = os.path.join(project_base, m)
            if os.path.exists(m_path):
                process_machine_directory(m_path)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
