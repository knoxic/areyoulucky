import re
import requests
import itertools
import streamlit as st
from bs4 import BeautifulSoup

# --- 核心：获取开奖数据 ---
@st.cache_data(ttl=3600)  # 缓存1小时，避免重复请求被封IP
def get_win_data(issue):
    """根据期号从500彩票网爬取开奖信息"""
    url = f"https://kaijiang.500.com/shtml/dlt/{issue}.shtml"
    try:
        resp = requests.get(url, timeout=10)
        resp.encoding = 'gb2312'
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        red = [int(x.text) for x in soup.select('.ball_red')]
        blue = [int(x.text) for x in soup.select('.ball_blue')]
        
        # 实时抓取一、二等奖单注奖金，若抓取失败则使用预设值
        prizes = {"grade1": 10000000, "grade2": 150000}
        try:
            table = soup.find('table', attrs={'class': 'kj_tablelist02'})
            if table:
                rows = table.find_all('tr')
                g1 = rows[2].find_all('td')[3].text.replace(',', '').replace('元', '')
                g2 = rows[3].find_all('td')[3].text.replace(',', '').replace('元', '')
                prizes["grade1"] = int(g1)
                prizes["grade2"] = int(g2)
        except:
            pass
            
        if not red: return None
        return {"front": sorted(red), "back": sorted(blue), "prizes": prizes}
    except Exception:
        return None

# --- 核心：OCR 逻辑 (轻量化处理) ---
def extract_numbers(img_array):
    """
    为了避免服务器内存崩溃，我们在 app.py 中调用此函数前
    会提醒用户：如果自动识别不成功，可以点击手动输入。
    """
    try:
        import easyocr
        # 强制只使用英文模型（识别数字绰绰有余），体积仅为中文模型的 1/10
        reader = easyocr.Reader(['en'], gpu=False, model_storage_directory='./model')
        result = reader.readtext(img_array, detail=0)
    except Exception as e:
        # 如果服务器内存实在撑不住，返回空列表，由 app.py 引导手动输入
        return None, [], False

    txts = result
    issue = None
    bets = []
    is_zhuijia = any(re.search(r'追加|ZJ|ZUI', t.upper()) for t in txts)
    
    # 1. 提取期号 (寻找5位数字，如 24010)
    for t in txts:
        match = re.search(r'2\d{4}', t)
        if match:
            issue = match.group()
            break
    
    # 2. 提取号码 (大乐透核心正则)
    # 匹配模式：(5-7个数字) 分隔符 (2-3个数字)
    # 分隔符兼容: +, -, -, *, /, |
    pattern = re.compile(r'(\d[\d\s,]{8,})\s*[+\-－—*|/]\s*(\d[\d\s,]{2,})')
    
    for t in txts:
        # 纠正 OCR 常见错误
        clean_t = t.replace('o','0').replace('O','0').replace('l','1').replace('I','1').replace('s','5').replace('S','5')
        match = pattern.search(clean_t)
        if match:
            f_nums = [int(n) for n in re.findall(r'\d+', match.group(1))]
            b_nums = [int(n) for n in re.findall(r'\d+', match.group(2))]
            
            # 校验是否为合法大乐透注数范围
            if 5 <= len(f_nums) <= 15 and 2 <= len(b_nums) <= 12:
                if all(1 <= x <= 35 for x in f_nums) and all(1 <= x <= 12 for x in b_nums):
                    bets.append({"front": sorted(list(set(f_nums))), "back": sorted(list(set(b_nums)))})
    
    return issue, bets, is_zhuijia

# --- 核心：算奖算法 ---
def calculate_prize(user_bet, win_data, is_zhuijia):
    """计算中奖金额 (支持单注、复式)"""
    win_f = set(win_data['front'])
    win_b = set(win_data['back'])
    
    # 使用组合算法展开复式
    f_combos = itertools.combinations(user_bet['front'], 5)
    b_combos = itertools.combinations(user_bet['back'], 2)
    
    total_prize = 0
    for f in f_combos:
        for b in b_combos:
            hit_f = len(set(f) & win_f)
            hit_b = len(set(b) & win_b)
            
            prize = 0
            if hit_f == 5 and hit_b == 2: prize = win_data['prizes']['grade1']
            elif hit_f == 5 and hit_b == 1: prize = win_data['prizes']['grade2']
            elif hit_f == 5 and hit_b == 0: prize = 10000
            elif hit_f == 4 and hit_b == 2: prize = 3000
            elif hit_f == 4 and hit_b == 1: prize = 300
            elif hit_f == 3 and hit_b == 2: prize = 200
            elif hit_f == 4 and hit_b == 0: prize = 100
            elif (hit_f == 3 and hit_b == 1) or (hit_f == 2 and hit_b == 2): prize = 15
            elif (hit_f == 3 and hit_f == 0) or (hit_f == 1 and hit_b == 2) or (hit_f == 2 and hit_b == 1) or (hit_f == 0 and hit_b == 2): 
                prize = 5
            
            # 追加逻辑 (仅针对一、二等奖)
            if is_zhuijia and prize > 0:
                if hit_f == 5 and (hit_b == 2 or hit_b == 1):
                    prize = int(prize * 1.8)
            
            total_prize += prize
            
    return total_prize
