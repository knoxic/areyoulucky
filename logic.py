import re
import requests
import itertools
import streamlit as st
from bs4 import BeautifulSoup
import numpy as np

# 注意：为了避免初始化冲突，PaddleOCR 的 import 放在了函数内部

@st.cache_resource
def get_ocr_instance():
    """
    使用 Streamlit 缓存机制加载 OCR 模型。
    这样模型只会在 App 启动时加载一次，避免了重复初始化的报错。
    """
    from paddleocr import PaddleOCR
    # 强制不使用 PaddleX 模式以节省内存并提高稳定性
    return PaddleOCR(use_angle_cls=True, lang="ch", show_log=False)

def get_win_data(issue):
    """根据期号从500彩票网爬取开奖信息"""
    url = f"https://kaijiang.500.com/shtml/dlt/{issue}.shtml"
    try:
        # 设置合理的超时，防止网页无响应导致 App 卡死
        resp = requests.get(url, timeout=10)
        resp.encoding = 'gb2312'
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        red = [int(x.text) for x in soup.select('.ball_red')]
        blue = [int(x.text) for x in soup.select('.ball_blue')]
        
        # 默认奖金逻辑
        prizes = {"grade1": 10000000, "grade2": 200000}
        
        if not red:
            return None
            
        return {"front": sorted(red), "back": sorted(blue), "prizes": prizes}
    except Exception as e:
        print(f"爬虫出错: {e}")
        return None

def extract_numbers(img_array):
    """从图片识别号码、期号和是否追加"""
    # 获取缓存中的 OCR 实例
    ocr = get_ocr_instance()
    
    # 执行识别
    result = ocr.ocr(img_array, cls=True)
    if not result or not result[0]:
        return None, [], False
        
    txts = [line[1][0] for line in result[0]]
    
    issue = None
    bets = []
    is_zhuijia = any("追加" in t for t in txts)
    
    # 1. 识别期号：匹配 5 位数字，通常是大乐透的期号特征
    for t in txts:
        match = re.search(r'2\d{4}', t)
        if match:
            issue = match.group()
            break
    
    # 2. 识别号码：匹配 "数字... + 数字..." 的结构
    # 增加了对全角字符和不同分隔符的兼容
    pattern = re.compile(r'([\d\s,]{10,})\s*[+\-－—]\s*([\d\s,]{4,})')
    
    for t in txts:
        # 常见 OCR 误识别修正
        clean_t = t.replace('o','0').replace('O','0').replace('l','1').replace('I','1')
        match = pattern.search(clean_t)
        
        if match:
            # 提取数字并过滤
            f_part = re.findall(r'\d+', match.group(1))
            b_part = re.findall(r'\d+', match.group(2))
            
            f = [int(n) for n in f_part]
            b = [int(n) for n in b_part]
            
            # 基础校验：前区 5-35 个球，后区 2-12 个球
            if 5 <= len(f) <= 35 and 2 <= len(b) <= 12:
                # 排除明显不是号码的数字（如站号或流水号）
                if all(1 <= x <= 35 for x in f) and all(1 <= x <= 12 for x in b):
                    bets.append({"front": f, "back": b})
    
    return issue, bets, is_zhuijia

def calculate_prize(user_bet, win_data, is_zhuijia):
    """
    大乐透算奖算法逻辑。
    支持复式投注：将复式拆解为单注组合进行比对。
    """
    win_f = set(win_data['front'])
    win_b = set(win_data['back'])
    
    # 使用迭代器生成所有单注组合，节省内存
    f_combos = itertools.combinations(user_bet['front'], 5)
    b_combos = itertools.combinations(user_bet['back'], 2)
    
    total_prize = 0
    
    for f in f_combos:
        for b in b_combos:
            # 计算当前组合的命中数
            hit_f = len(set(f) & win_f)
            hit_b = len(set(b) & win_b)
            
            prize = 0
            # 2024年现行大乐透中奖规则
            if hit_f == 5 and hit_b == 2: prize = win_data['prizes']['grade1']
            elif hit_f == 5 and hit_b == 1: prize = win_data['prizes']['grade2']
            elif hit_f == 5 and hit_b == 0: prize = 10000
            elif hit_f == 4 and hit_b == 2: prize = 3000
            elif hit_f == 4 and hit_b == 1: prize = 300
            elif hit_f == 3 and hit_b == 2: prize = 200
            elif hit_f == 4 and hit_b == 0: prize = 100
            elif (hit_f == 3 and hit_b == 1) or (hit_f == 2 and hit_b == 2): prize = 15
            elif (hit_f == 3 and hit_b == 0) or (hit_f == 1 and hit_b == 2) or (hit_f == 2 and hit_b == 1) or (hit_f == 0 and hit_b == 2): prize = 5
            
            # 追加投注逻辑：一、二等奖追加奖金为基本奖金的 80%
            if is_zhuijia and prize > 0:
                if hit_f == 5 and (hit_b == 2 or hit_b == 1):
                    prize = int(prize * 1.8)
                # 注：固定奖追加在特定派奖期间有特殊规则，此处按常规逻辑
            
            total_prize += prize
            
    return total_prize
