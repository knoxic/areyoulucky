import streamlit as st
import numpy as np
from PIL import Image
import logic

st.set_page_config(page_title="超级大乐透自动核奖", page_icon="🧧")

st.title("🧧 大乐透自动核奖助手")
st.write("上传彩票照片（支持单注、复式、套餐票）")

files = st.file_uploader("点击上传彩票照片", type=['jpg','png','jpeg'], accept_multiple_files=True)

if files:
    all_money = 0
    for file in files:
        img = Image.open(file)
        st.image(img, caption=f"已上传: {file.name}", width=300)
        
        with st.spinner(f'正在分析 {file.name}...'):
            # 1. OCR识别
            issue, bets, is_zj = logic.extract_numbers(np.array(img))
            
            if not issue:
                st.error(f"{file.name}: 未能识别到期号")
                continue
            
            # 2. 获取开奖数据
            win_data = logic.get_win_data(issue)
            if not win_data:
                st.warning(f"期号 {issue}: 暂无开奖信息")
                continue
                
            st.info(f"期号: {issue} | 开奖号码: {' '.join(map(str, win_data['front']))} + {' '.join(map(str, win_data['back']))}")
            
            # 3. 计算结果
            file_prize = 0
            for bet in bets:
                file_prize += logic.calculate_prize(bet, win_data, is_zj)
            
            st.success(f"本张彩票中奖金额: ￥{file_prize}")
            all_money += file_prize

    st.divider()
    st.balloons()
    st.metric("总计中奖金额", f"￥{all_money}")
