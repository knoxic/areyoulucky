import re
import requests
import itertools
import streamlit as st
from bs4 import BeautifulSoup
import easyocr
import numpy as np

@st.cache_resource
def get_ocr_reader():
    """
    初始化 EasyOCR 实例。
    第一次运行会下载模型（约 80MB），之后会从缓存读取。
    """
    # ['ch_sim', 'en'] 表示支持简体中文和英文数字识别
    return easyocr.Reader(['ch_sim', 'en'], gpu=False)

def get_win_data(issue):
    """根据期号爬取开奖信息"""
    url = f"https://kaijiang.500.com/shtml/dlt/{issue}.shtml"
    try:
        resp = requests.get(url, timeout=10)
        resp.encoding = 'gb2312'
        soup = BeautifulSoup(resp.text, 'html.parser')
        red = [int(x.text) for x in soup.select('.ball_red')]
        blue = [int(x.text) for x in soup.select('.ball_blue')]
        # 默认一、二等奖奖金（建议用户在界面手动核对）
        prizes = {"grade1": 10000000, "grade2": 200000}
        if not red: return None
        return {"front": sorted(red), "back": sorted(blue), "prizes": prizes}
    except:
        return None

def extract_numbers(img_array):
    """使用 EasyOCR 识别并提取号码"""
    reader = get_ocr_reader()
    # 识别图片，detail=0 只返回文字内容
    txts = reader.readtext(img_array, detail=0)
    
    issue = None
    bets = []
    is_zhuijia = any("追加" in t for t in txts)
    
    # 匹配期号
    for t in txts:
        match = re.search(r'2\d{4}', t)
        if match:
            issue = match.group()
            break
            
    # 号码提取正则 (兼容多种分隔符)
    pattern = re.compile(r'(\d[\d\s,]{8,})\s*[+\-－—]\s*(\d[\d\s,]{2,})')
    
    for t in txts:
        # 常见错误字符修正
        clean_t = t.replace('o','0').replace('O','0').replace('l','1').replace('I','1').replace('s','5').replace('S','5')
        match = pattern.search(clean_t)
        if match:
            f = [int(n) for n in re.findall(r'\d+', match.group(1))]
            b = [int(n) for n in re.findall(r'\d+', match.group(2))]
            # 校验范围
            if 5 <= len(f) <= 35 and 2 <= len(b) <= 12:
                if all(1 <= x <= 35 for x in f) and all(1 <= x <= 12 for x in b):
                    bets.append({"front": f, "back": b})
    
    return issue, bets, is_zhuijia

def calculate_prize(user_bet, win_data, is_zhuijia):
    """计算中奖金额"""
    win_f = set(win_data['front'])
    win_b = set(win_data['back'])
    f_combos = itertools.combinations(user_bet['front'], 5)
    b_combos = itertools.combinations(user_bet['back'], 2)
    
    total_prize = 0
    for f in f_combos:
        for b in b_combos:
            hit_f = len(set(f) & win_f)
            hit_b = len(set(b) & win_b)
            prize = 0
            # 标准奖级判定
            if hit_f == 5 and hit_b == 2: prize = win_data['prizes']['grade1']
            elif hit_f == 5 and hit_b == 1: prize = win_data['prizes']['grade2']
            elif hit_f == 5 and hit_b == 0: prize = 10000
            elif hit_f == 4 and hit_b == 2: prize = 3000
            elif hit_f == 4 and hit_b == 1: prize = 300
            elif hit_f == 3 and hit_b == 2: prize = 200
            elif hit_f == 4 and hit_b == 0: prize = 100
            elif (hit_f == 3 and hit_b == 1) or (hit_f == 2 and hit_b == 2): prize = 15
            elif (hit_f == 3 and hit_b == 0) or (hit_f == 1 and hit_b == 2) or (hit_f == 2 and hit_b == 1) or (hit_f == 0 and hit_b == 2): prize = 5
            
            # 追加逻辑
            if is_zhuijia and hit_f == 5 and (hit_b == 2 or hit_b == 1):
                prize = int(prize * 1.8)
            total_prize += prize
    return total_prize
