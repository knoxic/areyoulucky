import streamlit as st
import numpy as np
from PIL import Image
import logic

st.set_page_config(page_title="大乐透助手", page_icon="🧧")

st.title("🧧 大乐透自动核奖")

# 侧边栏：手动修正选项
st.sidebar.header("手动输入/修正")
manual_mode = st.sidebar.checkbox("开启手动模式（若OCR识别失败）")

files = st.file_uploader("上传彩票照片", type=['jpg','png','jpeg'], accept_multiple_files=True)

if files:
    all_money = 0
    for file in files:
        img = Image.open(file)
        st.image(img, width=300)
        
        # 核心逻辑包裹在 try-except 里，防止整个 App 因为一张图崩溃
        try:
            with st.spinner('正在分析...'):
                issue, bets, is_zj = logic.extract_numbers(np.array(img))
                
                # 如果自动模式没找齐，或者开启了手动模式
                if manual_mode or not issue or not bets:
                    st.warning("自动识别不完整，请手动确认信息：")
                    issue = st.text_input(f"确认期号 ({file.name})", value=issue if issue else "24xxx")
                    is_zj = st.checkbox(f"是否追加 ({file.name})", value=is_zj)
                
                if issue:
                    win_data = logic.get_win_data(issue)
                    if win_data:
                        st.info(f"开奖结果：{' '.join(map(str, win_data['front']))} + {' '.join(map(str, win_data['back']))}")
                        current_total = 0
                        for b in bets:
                            current_total += logic.calculate_prize(b, win_data, is_zj)
                        st.success(f"本张中奖：￥{current_total}")
                        all_money += current_total
        except Exception as e:
            st.error(f"识别此图时发生错误，请尝试手动核对。错误信息：{e}")

    st.metric("总计中奖金额", f"￥{all_money}")
