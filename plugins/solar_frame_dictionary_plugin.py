# -*- coding: utf-8 -*-
"""
=============================================================================
PLC Table Toolkit - 意大利光伏组件自动化产线行业专有词典插件
(Solar Module Framing Automation Line Dictionary Plugin)
=============================================================================
适用项目：
  - 意大利国家电网 (Enel - 3Sun Gigafactory) SC1847 光伏后道自动化封装线
  - 覆盖：边框缓存机、组框机、放框机、裁切机、胶带机、修边机、贴护脚机、接线盒焊接机等
  - 支持中->英 (EN) 及中->意 (IT) 工业术语精准映射与替换
=============================================================================
"""

import os
import sys
import re
from typing import Dict, List, Tuple, Union, Callable, Optional

# Ensure core and workflow root are in sys.path
_CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
_WORKFLOW_ROOT = os.path.dirname(_CURRENT_DIR)
_CORE_DIR = os.path.join(_WORKFLOW_ROOT, "core")
for p in [_CORE_DIR, _WORKFLOW_ROOT, _CURRENT_DIR]:
    if p not in sys.path:
        sys.path.insert(0, p)

from plc_table_toolkit import DictionaryProviderPlugin



class SolarFrameDictionaryPlugin(DictionaryProviderPlugin):
    plugin_id = "solar_frame_dictionary_plugin"
    plugin_name = "Solar Frame Automation Line Dictionary (Enel Project)"
    version = "1.0.0"
    priority = 20  # 高于通用词典 (100)，优先匹配光伏专有术语

    # 精确短语映射 (中文 -> 英文)
    EXACT_PHRASES_EN: Dict[str, str] = {
        "边框缓存机": "Frame Buffer Machine",
        "边框取料位接近开关1": "Frame Pick Position Proximity Switch 1",
        "边框取料位接近开关2": "Frame Pick Position Proximity Switch 2",
        "边框满料检测1": "Frame Full Detection 1",
        "边框满料检测2": "Frame Full Detection 2",
        "阻挡前到位传感器": "Stopper Front In-Position Sensor",
        "阻挡气缸上位1": "Stopper Cylinder Up Position 1",
        "阻挡气缸上位2": "Stopper Cylinder Up Position 2",
        "阻挡气缸下位1": "Stopper Cylinder Down Position 1",
        "阻挡气缸下位2": "Stopper Cylinder Down Position 2",
        "阻挡气缸": "Stopper Cylinder",
        "分料气缸上位1": "Separating Cylinder Up Position 1",
        "分料气缸上位2": "Separating Cylinder Up Position 2",
        "分料气缸下位1": "Separating Cylinder Down Position 1",
        "分料气缸下位2": "Separating Cylinder Down Position 2",
        "输送线正转": "Conveyor Line FWD",
        "输送线慢速": "Conveyor Line Slow Speed",
        "输送线反转": "Conveyor Line REV",
        "放框机长边1出料请求": "Frame Feeder L1 Outfeed Request",
        "放框机长边2出料请求": "Frame Feeder L2 Outfeed Request",
        "放框机短边1出料请求": "Frame Feeder S1 Outfeed Request",
        "放框机短边2出料请求": "Frame Feeder S2 Outfeed Request",
        "（4根）边框放料完成": "(4 Pcs) Frame Placement Done",
        "(4根)边框放料完成": "(4 Pcs) Frame Placement Done",
        "底部升降上1": "Bottom Lifter Up 1",
        "夹产品": "Clamp Product",
        "真空到达": "Vacuum Reached",
        "翻转完成": "Turnover Done",
        "原点回归": "Homing",
        "自动运行": "Auto Running",
        "1周停止": "Cycle Stop",
        "申请stop": "Request Stop",
        "HMI静音": "HMI Mute",
        "请求取料": "Request Pick Material",
        "取料完成": "Pick Material Done",
        "初始时间值": "Initial Time Value",
        "计时器输入输出": "Timer Input Output",
        "送料分料初始化": "Feeding Separating Init",
        "送料分料自动运行": "Feeding Separating Auto Run",
        "异常停机信号": "Abnormal Stop Signal",
        "流程状态": "Flow Status",
        "取料机构在安全区区域": "Pick Mechanism In Safety Area",
        "退料": "Material Return",
        "分料送料超时报警": "Separating Feeding Timeout Alarm",
    }

    # 意大利语短语映射 (中文 -> 意大利语 Italiano)
    EXACT_PHRASES_IT: Dict[str, str] = {
        "边框缓存机": "Buffer Telai",
        "边框取料位接近开关1": "Finecorsa Prelievo Telaio 1",
        "边框取料位接近开关2": "Finecorsa Prelievo Telaio 2",
        "边框满料检测1": "Sensore Pieno Telai 1",
        "边框满料检测2": "Sensore Pieno Telai 2",
        "阻挡前到位传感器": "Sensore Arresto Presenza",
        "阻挡气缸上位1": "Cilindro Arresto Alto 1",
        "阻挡气缸上位2": "Cilindro Arresto Alto 2",
        "阻挡气缸下位1": "Cilindro Arresto Basso 1",
        "阻挡气缸下位2": "Cilindro Arresto Basso 2",
        "阻挡气缸": "Cilindro di Arresto",
        "分料气缸上位1": "Cilindro Separatore Alto 1",
        "分料气缸上位2": "Cilindro Separatore Alto 2",
        "分料气缸下位1": "Cilindro Separatore Basso 1",
        "分料气缸下位2": "Cilindro Separatore Basso 2",
        "输送线正转": "Trasportatore Avanti",
        "输送线慢速": "Trasportatore Bassa Velocita",
        "输送线反转": "Trasportatore Indietro",
        "放框机长边1出料请求": "Richiesta Scarico Alimentatore L1",
        "放框机长边2出料请求": "Richiesta Scarico Alimentatore L2",
        "放框机短边1出料请求": "Richiesta Scarico Alimentatore S1",
        "放框机短边2出料请求": "Richiesta Scarico Alimentatore S2",
        "（4根）边框放料完成": "Posa (4) Telai Completata",
        "底部升降上1": "Sollevatore Inferiore Su 1",
        "夹产品": "Bloccaggio Prodotto",
        "真空到达": "Vuoto Raggiunto",
        "翻转完成": "Ribaltamento Completato",
        "原点回归": "Ritorno a Zero",
        "自动运行": "Funzionamento Automatico",
        "手动": "Manuale",
        "自动": "Automatico",
        "准备": "Pronto",
        "停止": "Arresto",
        "异常": "Anomalia",
        "HMI静音": "Silenziamento HMI",
        "1周停止": "Arresto Ciclo",
        "请求取料": "Richiesta Prelievo Materiale",
        "取料完成": "Prelievo Materiale Completato",
        "初始时间值": "Valore Tempo Iniziale",
        "计时器输入输出": "Ingresso Uscita Timer",
        "送料分料初始化": "Inizializzazione Alimentazione Separazione",
        "送料分料自动运行": "Funzionamento Auto Alimentazione Separazione",
        "异常停机信号": "Segnale Arresto Anomalo",
        "流程状态": "Stato Sequenza",
        "取料机构在安全区区域": "Meccanismo Prelievo in Area di Sicurezza",
        "退料": "Ritorno Materiale",
        "分料送料超时报警": "Allarme Timeout Separazione Alimentazione",
    }

    # 贪婪词素对 (中文, 英文)
    WORD_PAIRS_EN: List[Tuple[str, str]] = [
        ("边框缓存机", "Frame Buffer Machine"),
        ("边框取料位", "Frame Pick Position"),
        ("接近开关", "Proximity Switch"),
        ("满料检测", "Full Material Detection"),
        ("放框机", "Frame Feeder"),
        ("组框机", "Framing Machine"),
        ("搓角机", "Corner Grinding Machine"),
        ("贴护脚机", "Corner Box Machine"),
        ("接线盒焊接机", "Junction Box Soldering Machine"),
        ("边框放料", "Frame Placement"),
        ("请求取料", "Request Pick Material"),
        ("取料机构", "Pick Mechanism"),
        ("取料完成", "Pick Material Done"),
        ("取料位", "Pick Position"),
        ("取料", "Pick Material"),
        ("在安全区区域", "In Safety Area"),
        ("安全区区域", "Safety Area"),
        ("在安全区", "In Safety Area"),
        ("安全区", "Safety Area"),
        ("计时器输入输出", "Timer Input Output"),
        ("计时器", "Timer"),
        ("初始时间值", "Initial Time Value"),
        ("初始时间", "Initial Time"),
        ("时间值", "Time Value"),
        ("初始值", "Initial Value"),
        ("初始化", "Initialization"),
        ("初始", "Initial"),
        ("送料分料初始化", "Feeding Separating Init"),
        ("送料分料自动运行", "Feeding Separating Auto Run"),
        ("分料送料超时报警", "Separating Feeding Timeout Alarm"),
        ("送料分料", "Feeding Separating"),
        ("分料送料", "Separating Feeding"),
        ("分料气缸", "Separating Cylinder"),
        ("阻挡气缸", "Stopper Cylinder"),
        ("到位传感器", "In-Position Sensor"),
        ("底部升降", "Bottom Lifter"),
        ("真空到达", "Vacuum Reached"),
        ("翻转完成", "Turnover Done"),
        ("出料请求", "Outfeed Request"),
        ("入料请求", "Infeed Request"),
        ("申请stop", "Request Stop"),
        ("1周停止", "Cycle Stop"),
        ("原点回归", "Homing"),
        ("自动运行", "Auto Running"),
        ("超时报警", "Timeout Alarm"),
        ("超时", "Timeout"),
        ("送料", "Feeding"),
        ("分料", "Separating"),
        ("退料", "Material Return"),
        ("异常停机信号", "Abnormal Stop Signal"),
        ("异常停机", "Abnormal Stop"),
        ("停机信号", "Stop Signal"),
        ("停机", "Stop"),
        ("流程状态", "Flow Status"),
        ("流程", "Flow"),
        ("机构", "Mechanism"),
        ("区域", "Area"),
        ("短边2#点", "Short Side #2 Point"),
        ("短边1#点", "Short Side #1 Point"),
        ("长边2#点", "Long Side #2 Point"),
        ("长边1#点", "Long Side #1 Point"),
        ("边框", "Frame"),
        ("短边", "Short Side"),
        ("长边", "Long Side"),
        ("夹产品", "Clamp Product"),
        ("静音", "Mute"),
    ]

    def get_exact_phrases(self) -> Dict[str, str]:
        return dict(self.EXACT_PHRASES_EN)

    def get_exact_phrases_italian(self) -> Dict[str, str]:
        return dict(self.EXACT_PHRASES_IT)

    def get_word_pairs(self) -> List[Tuple[str, str]]:
        return list(self.WORD_PAIRS_EN)

    def get_regex_rules(self) -> List[Tuple[Union[re.Pattern, str], Callable]]:
        def handle_frame_side(match: re.Match, translate_fn: Callable[[str], str]) -> str:
            side = "Long Side" if "长" in match.group(1) else "Short Side"
            num = match.group(2)
            pt = match.group(3)
            return f"{side} {num} Point {pt}"

        return [
            (re.compile(r'^(长|短)边(\d+)#点$'), handle_frame_side),
        ]
