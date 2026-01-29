import re
import requests
import itertools
from bs4 import BeautifulSoup
from paddleocr import PaddleOCR

# 初始化OCR (使用轻量化参数，节省内存)
ocr = PaddleOCR(use_angle_cls=True, lang="ch", show_log=False)

def get_win_data(issue):
    """爬取开奖信息"""
    url = f"https://kaijiang.500.com/shtml/dlt/{issue}.shtml"
    try:
        resp = requests.get(url, timeout=10)
        resp.encoding = 'gb2312'
        soup = BeautifulSoup(resp.text, 'html.parser')
        red = [int(x.text) for x in soup.select('.ball_red')]
        blue = [int(x.text) for x in soup.select('.ball_blue')]
        # 默认奖金（浮动奖建议手动校对）
        prizes = {"grade1": 10000000, "grade2": 200000}
        return {"front": sorted(red), "back": sorted(blue), "prizes": prizes}
    except:
        return None

def extract_numbers(img_array):
    """从图片识别号码"""
    result = ocr.ocr(img_array, cls=True)
    txts = [line[1][0] for line in result[0]] if result[0] else []
    
    issue = None
    bets = []
    is_zhuijia = any("追加" in t for t in txts)
    
    # 找期号 (正则匹配5位数字)
    for t in txts:
        match = re.search(r'2\d{4}', t)
        if match: issue = match.group(); break
    
    # 找号码 (正则匹配前后区)
    pattern = re.compile(r'([\d\s]{10,})\s*[+\-－]\s*([\d\s]{4,})')
    for t in txts:
        clean_t = t.replace('o','0').replace('O','0')
        match = pattern.search(clean_t)
        if match:
            f = [int(n) for n in re.findall(r'\d+', match.group(1))]
            b = [int(n) for n in re.findall(r'\d+', match.group(2))]
            if 5 <= len(f) <= 35 and 2 <= len(b) <= 12:
                bets.append({"front": f, "back": b})
    return issue, bets, is_zhuijia

def calculate_prize(user_bet, win_data, is_zhuijia):
    """算奖算法 (支持复式)"""
    win_f, win_b = set(win_data['front']), set(win_data['back'])
    f_combos = itertools.combinations(user_bet['front'], 5)
    b_combos = itertools.combinations(user_bet['back'], 2)
    
    total = 0
    details = []
    for f in f_combos:
        for b in b_combos:
            hf, hb = len(set(f) & win_f), len(set(b) & win_b)
            # 简化版奖级判断 (9等奖制)
            money = 0
            if hf==5 and hb==2: money = win_data['prizes']['grade1']
            elif hf==5 and hb==1: money = win_data['prizes']['grade2']
            elif hf==5 and hb==0: money = 10000
            elif hf==4 and hb==2: money = 3000
            elif hf==4 and hb==1: money = 300
            elif hf==3 and hb==2: money = 200
            elif hf==4 and hb==0: money = 100
            elif (hf==3 and hb==1) or (hf==2 and hb==2): money = 15
            elif (hf==3 and hb==0) or (hf==1 and hb==2) or (hf==2 and hb==1) or (hf==0 and hb==2): money = 5
            
            if is_zhuijia and hf==5: money = int(money * 1.8) # 简单模拟追加
            total += money
    return total
