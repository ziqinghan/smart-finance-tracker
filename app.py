import streamlit as st
import pandas as pd
import pdfplumber
import plotly.express as px
import os
import re

# 页面配置
st.set_page_config(page_title="Shareable 智能财务管家", page_icon="🌍", layout="wide")

# ==========================================
# 常量与全局设定
# ==========================================
GLOBAL_KNOWLEDGE_FILE = "shared_knowledge.csv"

# 【个人隐私黑名单】：包含这些关键词的交易，绝对不会被上传到公共大脑
PERSONAL_BLACKLIST = ["zelle", "venmo", "transfer", "online banking", "payment", "epay", "check", "deposit", "payroll", "ach"]

CATEGORIES = [
    "☕️ 咖啡奶茶", "🍱 餐饮外卖", "🛍️ 购物超市", "🛒 宠物消费", "🚗 交通油费",
    "✈️ 旅行住宿", "🧘🏻‍♀️ 运动健身", "🎿 娱乐票务", "🏥 医疗健康", "🏠 房租水电",
    "📦 生活杂项", "🏦 银行手续费", "💳 信用卡还款", "💰 内部转账", "其他", "其他收入"
]

# 初始内置字典（Fallback）
KEYWORD_MAPPING = {
    "☕️ 咖啡奶茶": ["voyager", "coffee", "moon tea", "umetea", "dr.ink", "molly tea", "matcha town", "naisnow", "shuyi", "chicha", "taningca", "minglewood", "little bear cafe", "tea", "starbucks", "peets"],
    "🍱 餐饮外卖": ["bafang", "dumpling", "chipotle", "doordash", "dd *", "fantuan", "seamless", "hunan mifen", "malatang", "sweetgreen", "lee's sandwiches", "snack*", "uep*", "restaurant", "dining", "mcdonald", "wendy", "popeyes", "kfc", "noodle", "kitchen", "sushi", "bistro", "cafe", "pizza", "waiter.com"],
    "🛍️ 购物超市": ["amazon", "amzn", "sephora", "lancome", "sports basement", "parallel mountian", "target", "walmart", "costco whse", "safeway", "99 ranch", "weee", "wholefds", "whole foods", "trader joe", "grocery"],
    "🛒 宠物消费": ["petsmart", "chewy", "petco"],
    "🚗 交通油费": ["gas", "chevron", "shell", "exxon", "uber", "lyft", "caltrain", "parking", "fastrak", "toll", "transit", "bart"],
    "✈️ 旅行住宿": ["alaska air", "united", "delta", "american air", "southwest", "hotel", "resort", "airbnb", "marriott", "hilton", "hyatt", "motel", "expedia", "booking.com", "outrigger"],
    "🧘🏻‍♀️ 运动健身": ["pilates", "glowlab", "yoga", "gym", "golf", "golfnow", "golf cour"],
    "🎿 娱乐票务": ["palisades", "tahoe", "ski", "movie", "steam games", "tm *", "ticketmaster", "livenation", "amc", "cinemark", "stubhub", "concert"],
    "🏥 医疗健康": ["quest diagnostics", "qdi", "cvs", "pharmacy", "walgreens", "hospital", "pets best", "pet insurance", "kaiser", "sutter"],
    "🏠 房租水电": ["jpmorgan-bzb312", "jpmorgan-bzo4312", "yardi service", "ladwp", "pgande", "rent", "water", "trash", "sewer"],
    "📦 生活杂项": ["usps", "comcast", "utilities", "apple", "google", "openai"],
    "🏦 银行手续费": ["annual membership fee", "fee", "interest"],
    "💳 信用卡还款": ["payment thank you", "autopay", "payment to", "chase card", "credit card bill payment", "chase credit crd", "american express des:ach", "epay", "online banking payment to crd"],
    "💰 内部转账": ["online banking transfer", "zelle payment", "venmo"]
}

# ==========================================
# 会话状态管理 (确保用户数据不污染服务器)
# ==========================================
if 'my_df' not in st.session_state:
    st.session_state['my_df'] = pd.DataFrame(columns=["日期", "交易描述", "金额", "类别"])

# ==========================================
# 全局大脑逻辑 (Federated Learning)
# ==========================================
def load_global_knowledge():
    """读取所有用户的共享分类记忆"""
    if os.path.exists(GLOBAL_KNOWLEDGE_FILE):
        return pd.read_csv(GLOBAL_KNOWLEDGE_FILE)
    return pd.DataFrame(columns=["交易描述", "类别", "贡献次数"])

def save_global_knowledge(df):
    df.to_csv(GLOBAL_KNOWLEDGE_FILE, index=False)

def update_global_knowledge(description, category):
    """
    当任何用户修正分类时，尝试更新到全局大脑。
    返回 True 表示共享成功，False 表示命中隐私黑名单未共享。
    """
    desc_lower = str(description).lower()
    
    # 1. 隐私保护拦截！
    if any(black_word in desc_lower for black_word in PERSONAL_BLACKLIST):
        return False
        
    global_df = load_global_knowledge()
    
    # 2. 查找是否已存在
    match_idx = global_df[global_df['交易描述'].str.lower() == desc_lower].index
    
    if not match_idx.empty:
        # 如果存在，覆写最新类别，并增加贡献次数
        idx = match_idx[0]
        global_df.at[idx, '类别'] = category
        global_df.at[idx, '贡献次数'] += 1
    else:
        # 新增到全局大脑
        new_row = pd.DataFrame([{"交易描述": description, "类别": category, "贡献次数": 1}])
        global_df = pd.concat([global_df, new_row], ignore_index=True)
        
    save_global_knowledge(global_df)
    return True

# ==========================================
# 分类引擎
# ==========================================
def auto_categorize(description, amount):
    """结合全局大脑和本地字典的分类引擎"""
    desc = str(description).lower()
    
    # 1. 优先去查询【全局共享大脑】
    global_df = load_global_knowledge()
    if not global_df.empty:
        global_df['lower_desc'] = global_df['交易描述'].str.lower()
        
        # 精确匹配
        valid_history = global_df[global_df['类别'].isin(CATEGORIES)]
        if not valid_history.empty:
            match = valid_history[valid_history['lower_desc'] == desc]
            if not match.empty:
                return match.iloc[-1]['类别']
                
            # 模糊匹配 (前两个单词)
            desc_words = desc.split()
            if len(desc_words) >= 2:
                for _, row in valid_history.iterrows():
                    hist_words = row['lower_desc'].split()
                    if len(hist_words) >= 2:
                        if hist_words[0] == desc_words[0] and hist_words[1] == desc_words[1]:
                            return row['类别']
    
    # 2. 如果公共大脑不知道，去问【本地内置字典】
    for category, keywords in KEYWORD_MAPPING.items():
        for keyword in keywords:
            if keyword in desc or keyword.replace(' ', '') in desc.replace(' ', ''):
                return category
            
    # 3. 兜底逻辑
    try:
        if float(amount) > 0:
             return "其他收入"
    except:
        pass

    return "其他"

def batch_update_category(target_desc, new_category, current_df):
    """在用户当前会话中批量更新分类"""
    target_desc_lower = str(target_desc).lower()
    target_words = target_desc_lower.split()
    
    target_prefix = None
    if len(target_words) >= 2:
        target_prefix = f"{target_words[0]} {target_words[1]}"
        
    changed_count = 0
    for idx, row in current_df.iterrows():
        r_desc = str(row['交易描述']).lower()
        
        # 1. 精确匹配
        if r_desc == target_desc_lower:
            if current_df.at[idx, '类别'] != new_category:
                current_df.at[idx, '类别'] = new_category
                changed_count += 1
            continue
            
        # 2. 模糊匹配 (前两个单词一样)
        if target_prefix:
            r_words = r_desc.split()
            if len(r_words) >= 2 and f"{r_words[0]} {r_words[1]}" == target_prefix:
                if current_df.at[idx, '类别'] != new_category:
                    current_df.at[idx, '类别'] = new_category
                    changed_count += 1
                    
    return current_df, changed_count

# ==========================================
# 解析器与清理逻辑
# ==========================================
# (保持原有的解析逻辑，节省篇幅，重点关注架构变化)
def parse_chase_pdf(uploaded_file):
    transactions = []
    try:
        with pdfplumber.open(uploaded_file) as pdf:
            text = ""
            for page in pdf.pages:
                extracted = page.extract_text()
                if extracted:
                    text += extracted + "\n"
        
        year = "2026"
        year_match = re.search(r'Opening/Closing Date.*?(\d{2})$', text, re.MULTILINE)
        if year_match:
            year = "20" + year_match.group(1)

        pattern = re.compile(r'^(\d{2}/\d{2})\s+(.+?)\s+(-?[\d,]+\.\d{2})$', re.MULTILINE)
        matches = pattern.findall(text)
        
        for match in matches:
            date_str, desc, amount_str = match
            amount = float(amount_str.replace(',', '')) * -1
            full_date = f"{year}/{date_str}"
            transactions.append({"日期": full_date, "交易描述": desc.strip(), "金额": amount})
    except Exception as e:
        st.error(f"解析 PDF 失败: {str(e)}")
        return pd.DataFrame()
        
    df = pd.DataFrame(transactions)
    if not df.empty:
        df['日期'] = pd.to_datetime(df['日期']).dt.date
        df['类别'] = df.apply(lambda x: auto_categorize(x['交易描述'], x['金额']), axis=1)
    return df

def parse_csv(uploaded_file):
    try:
        raw_lines = uploaded_file.getvalue().decode('utf-8').splitlines()
        header_row_index = 0
        is_boa = False
        is_chase = False
        
        for i, line in enumerate(raw_lines[:20]):
            if 'Transaction Date' in line and 'Description' in line and 'Amount' in line:
                header_row_index = i
                is_chase = True
                break
            elif 'Date' in line and 'Description' in line and 'Amount' in line and 'Running Bal.' in line:
                header_row_index = i
                is_boa = True
                break
        
        uploaded_file.seek(0)
        df = pd.read_csv(uploaded_file, skiprows=header_row_index)
        extracted_df = pd.DataFrame()
        
        if is_chase:
            extracted_df = pd.DataFrame({"日期": df['Transaction Date'], "交易描述": df['Description'], "金额": df['Amount']})
        elif is_boa:
            extracted_df = pd.DataFrame({"日期": df['Date'], "交易描述": df['Description'], "金额": df['Amount']})
            extracted_df = extracted_df.dropna(subset=['金额'])
        else:
            st.error("未能识别的 CSV 格式")
            return pd.DataFrame()
            
        extracted_df['日期'] = pd.to_datetime(extracted_df['日期'], errors='coerce').dt.date
        extracted_df = extracted_df.dropna(subset=['日期'])
        
        if extracted_df['金额'].dtype == 'O': 
            extracted_df['金额'] = extracted_df['金额'].str.replace(',', '').astype(float)
        else:
            extracted_df['金额'] = extracted_df['金额'].astype(float)
            
        extracted_df['类别'] = extracted_df.apply(lambda x: auto_categorize(x['交易描述'], x['金额']), axis=1)
        return extracted_df
        
    except Exception as e:
        st.error(f"解析 CSV 失败: {str(e)}")
        return pd.DataFrame()

def apply_refund_cancellation(df):
    """应用退款抵消魔法"""
    if df.empty: return df, 0
    refund_candidates = df[(df['金额'] > 0) & (~df['类别'].isin(['💳 信用卡还款', '💰 内部转账', '其他收入']))].copy()
    expense_candidates = df[df['金额'] < 0].copy()
    drop_indices = set()
    
    for r_idx, refund in refund_candidates.iterrows():
        r_amount = refund['金额']
        r_desc = str(refund['交易描述']).lower()
        r_words = [w for w in re.split(r'[^a-zA-Z]', r_desc) if len(w) > 2]
        if not r_words: continue
        core_keyword = r_words[0]
        
        matching_expenses = expense_candidates[
            (abs(expense_candidates['金额'] + r_amount) < 0.01) & 
            (expense_candidates['交易描述'].str.lower().str.contains(core_keyword)) &
            (~expense_candidates.index.isin(drop_indices)) 
        ]
        
        if not matching_expenses.empty:
            e_idx = matching_expenses.index[0]
            drop_indices.add(r_idx)
            drop_indices.add(e_idx)
            
    if drop_indices:
        df = df.drop(index=list(drop_indices)).reset_index(drop=True)
        return df, len(drop_indices)//2
    return df, 0


# ==========================================
# UI 布局
# ==========================================

# --- 侧边栏：安全的数据管理 ---
with st.sidebar:
    st.markdown("### 🔒 隐私与数据安全")
    st.info("欢迎使用公共版看板！为了您的隐私，您的账单数据**仅存在于本次浏览器会话中**，关闭网页即销毁，绝不会上传到服务器。")
    
    st.markdown("---")
    st.markdown("### 📂 我的历史记录")
    st.write("上传您之前下载的个人历史记录，以恢复您的账单数据。")
    history_file = st.file_uploader("导入 personal_history.csv", type="csv")
    if history_file is not None:
        try:
            hist_df = pd.read_csv(history_file)
            hist_df['日期'] = pd.to_datetime(hist_df['日期']).dt.date
            st.session_state['my_df'] = hist_df
            st.success("历史记录导入成功！")
        except:
            st.error("导入失败，文件格式不正确。")
            
    st.markdown("---")
    if not st.session_state['my_df'].empty:
        st.write(f"当前在算记录：**{len(st.session_state['my_df'])}** 条")
        csv_data = st.session_state['my_df'].to_csv(index=False).encode('utf-8')
        st.download_button(
            label="💾 下载最新数据到本地",
            data=csv_data,
            file_name="personal_history.csv",
            mime="text/csv",
            help="离开网页前请务必下载保存，否则数据将丢失！"
        )
    if st.button("🗑️ 清空当前面板"):
        st.session_state['my_df'] = pd.DataFrame(columns=["日期", "交易描述", "金额", "类别"])
        st.rerun()

# --- 主界面 ---
st.title("🌍 智能财务管家 (Cloud & Crowdsourced)")
st.markdown("在这里，每一次人工修正都会让 AI 大脑变得更聪明，并共享给所有使用者！*(Zelle等隐私转账将被自动识别拦截，不会上传全局)*")

tab_import, tab_dashboard, tab_trends = st.tabs(["📥 账单导入与修正", "📊 月度消费概览", "📈 历史支出趋势追踪"])

with tab_import:
    st.header("1. 上传新账单 (PDF或CSV)")
    uploaded_file = st.file_uploader("支持 Chase PDF, Chase CSV, 以及 BoA CSV 格式", type=["pdf", "csv"], key="new_statement")
    
    if uploaded_file is not None:
        with st.spinner("正在呼叫全局大脑进行智能分类..."):
            filename_lower = uploaded_file.name.lower()
            if filename_lower.endswith('.pdf'):
                new_df = parse_chase_pdf(uploaded_file)
            elif filename_lower.endswith('.csv'):
                new_df = parse_csv(uploaded_file)
            else:
                new_df = pd.DataFrame()
            
            if new_df.empty:
                st.warning("未能提取到记录。")
            else:
                st.success(f"成功提取 {len(new_df)} 条交易记录！")
                st.subheader("2. 人工修正窗口 (双击类别修改，将同步至云端大脑 🧠)")
                
                edited_df = st.data_editor(
                    new_df,
                    column_config={
                        "类别": st.column_config.SelectboxColumn("消费类别", options=CATEGORIES, required=True),
                        "金额": st.column_config.NumberColumn("金额 (负数表示支出)", format="%.2f"),
                        "日期": st.column_config.DateColumn("交易日期")
                    },
                    hide_index=True,
                    num_rows="dynamic",
                    use_container_width=True
                )
                
                if st.button("💾 确认无误，并入我的看板", type="primary"):
                    # 合并到 Session State
                    combined_df = pd.concat([st.session_state['my_df'], edited_df]).drop_duplicates(subset=['日期', '交易描述', '金额'])
                    
                    # 触发退款清理魔法
                    cleaned_df, cleaned_count = apply_refund_cancellation(combined_df)
                    st.session_state['my_df'] = cleaned_df
                    
                    if cleaned_count > 0:
                        st.toast(f"🧹 自动清理魔法：成功抵消了 {cleaned_count} 对退款与消费记录！")
                    
                    # --- 贡献到全局大脑 ---
                    # 寻找用户在第一页就修改了的数据
                    diff = edited_df['类别'] != new_df['类别']
                    if diff.any():
                        changed_rows = edited_df[diff]
                        shared_count = 0
                        blocked_count = 0
                        for _, row in changed_rows.iterrows():
                            is_shared = update_global_knowledge(row['交易描述'], row['类别'])
                            if is_shared: shared_count += 1
                            else: blocked_count += 1
                        
                        if shared_count > 0:
                            st.toast(f"🌍 感谢贡献！您更正的 {shared_count} 条商户信息已上传至公共大脑。")
                        if blocked_count > 0:
                            st.toast(f"🔒 {blocked_count} 条转账类信息触发隐私保护，仅在本地生效。")

                    st.balloons()
                    st.success("数据已入库！请前往「月度概览」查看，离开前别忘了去左侧边栏下载数据备份哦。")

global_df = st.session_state['my_df'].copy()

with tab_dashboard:
    if global_df.empty:
        st.info("暂无数据，请先上传账单或从左侧边栏导入历史记录。")
    else:
        global_df['年月'] = pd.to_datetime(global_df['日期']).dt.to_period('M')
        available_months = sorted([str(m) for m in global_df['年月'].unique()], reverse=True)
        selected_month = st.selectbox("📅 选择要分析的月份", available_months)
        current_month_df = global_df[global_df['年月'] == pd.Period(selected_month, freq='M')]
        
        valid_expense_df = current_month_df[(current_month_df['金额'] < 0) & 
                                            (~current_month_df['类别'].isin(['💳 信用卡还款', '💰 内部转账']))]
        total_expense = valid_expense_df['金额'].sum()
        
        st.metric(f"💸 {selected_month} 真实总支出", f"$ {abs(total_expense):.2f}")
        st.markdown("---")
        
        st.subheader(f"🏆 {selected_month} 高额消费 Top 5")
        if not valid_expense_df.empty:
            top_5 = valid_expense_df.nsmallest(5, '金额')[['日期', '交易描述', '类别', '金额']]
            top_5['金额'] = top_5['金额'].abs()
            for i, row in enumerate(top_5.itertuples(), 1):
                col1, col2, col3, col4 = st.columns([1, 4, 3, 2])
                col1.markdown(f"**#{i}**")
                col2.text(row.交易描述)
                col3.text(row.类别)
                col4.markdown(f"**$ {row.金额:.2f}**")
        else:
            st.info("本月暂无消费记录")
            
        st.markdown("---")
        st.subheader(f"日常支出构成图 ({selected_month}) - *不含房租*")
        
        pie_expense_df = valid_expense_df[valid_expense_df['类别'] != '🏠 房租水电'].copy()
        pie_expense_df['绝对金额'] = pie_expense_df['金额'].abs()
        
        if not pie_expense_df.empty:
            idx_max = pie_expense_df.groupby('类别')['绝对金额'].idxmax()
            top_items = pie_expense_df.loc[idx_max][['类别', '交易描述', '绝对金额']].rename(columns={'交易描述': '最大单笔', '绝对金额': '最大单笔金额'})
            pie_data = pie_expense_df.groupby('类别')['绝对金额'].sum().reset_index()
            pie_data = pd.merge(pie_data, top_items, on='类别')
            pie_data['hover_text'] = pie_data.apply(lambda x: f"最大单笔: {x['最大单笔']} (${x['最大单笔金额']:.2f})", axis=1)
            
            fig_pie = px.pie(pie_data, values='绝对金额', names='类别', hole=0.4, color_discrete_sequence=px.colors.qualitative.Pastel, custom_data=['hover_text'])
            fig_pie.update_traces(hovertemplate="<b>%{label}</b><br>总计: $%{value:.2f}<br>占比: %{percent}<br><br>%{customdata[0]}<extra></extra>")
            st.plotly_chart(fig_pie, use_container_width=True)
            
            st.markdown("#### 📝 本月所有消费明细 (💡 神奇修正：双击修改类别，即刻更新全域图表！)")
            all_month_categories = current_month_df['类别'].unique()
            for category in sorted(all_month_categories):
                cat_df = current_month_df[current_month_df['类别'] == category].sort_values(by='金额')
                expense_only = cat_df[cat_df['金额'] < 0]['金额'].sum()
                
                exp_title = f"{category} (非消费项，共 {len(cat_df)} 笔)" if category in ['💳 信用卡还款', '💰 内部转账', '其他收入'] else f"{category} (总支出: $ {abs(expense_only):.2f})"
                
                with st.expander(exp_title):
                    detail_df = cat_df[['日期', '交易描述', '金额', '类别']].copy().reset_index(drop=True)
                    edited_df = st.data_editor(
                        detail_df,
                        column_config={
                            "日期": st.column_config.DateColumn("交易日期", disabled=True),
                            "交易描述": st.column_config.TextColumn("交易描述", disabled=True),
                            "金额": st.column_config.NumberColumn("金额", format="%.2f", disabled=True),
                            "类别": st.column_config.SelectboxColumn("分类 (双击修改 ✍️)", options=CATEGORIES, required=True)
                        },
                        hide_index=True, use_container_width=True, key=f"editor_{category}_{selected_month}"
                    )
                    
                    diff = edited_df['类别'] != detail_df['类别']
                    if diff.any():
                        changed_rows = edited_df[diff]
                        my_df = st.session_state['my_df']
                        for _, row in changed_rows.iterrows():
                            target_desc = row['交易描述']
                            new_cat = row['类别']
                            
                            # 1. 批量更新当前用户的 Session State (引入模糊匹配魔法)
                            my_df, affected_count = batch_update_category(target_desc, new_cat, my_df)
                            
                            # 2. 尝试推送到服务器全局大脑
                            is_shared = update_global_knowledge(target_desc, new_cat)
                            if is_shared:
                                st.toast(f"🌍 感谢贡献！'{target_desc}' 及 {affected_count} 条相似记录已全网同步为 {new_cat}")
                            else:
                                st.toast(f"🔒 隐私保护：'{target_desc}' 及 {affected_count} 条相似记录仅在本地为您修正为 {new_cat}")
                                
                        st.session_state['my_df'] = my_df
                        st.rerun()

with tab_trends:
    if global_df.empty:
        st.info("暂无数据，请先上传账单。")
    else:
        st.header("历史支出趋势追踪")
        trend_df = global_df[(global_df['金额'] < 0) & (~global_df['类别'].isin(['💳 信用卡还款', '💰 内部转账']))].copy()
        trend_df['绝对金额'] = trend_df['金额'].abs()
        trend_df['年月'] = trend_df['年月'].astype(str)
        monthly_summary = trend_df.groupby(['年月', '类别'])['绝对金额'].sum().reset_index()
        
        if not monthly_summary.empty:
            st.subheader("📊 总体消费趋势 (按月堆叠)")
            fig_bar = px.bar(monthly_summary, x='年月', y='绝对金额', color='类别', title="每月各类支出分布", barmode='stack', color_discrete_sequence=px.colors.qualitative.Pastel)
            st.plotly_chart(fig_bar, use_container_width=True)
            
            st.markdown("---")
            st.subheader("📈 单项分类趋势追踪")
            available_categories = sorted(monthly_summary['类别'].unique())
            if available_categories:
                selected_categories = st.multiselect("🔍 选择你要追踪的消费类别", options=available_categories, default=[available_categories[0]])
                if selected_categories:
                    filtered_trend = monthly_summary[monthly_summary['类别'].isin(selected_categories)]
                    fig_line = px.line(filtered_trend, x='年月', y='绝对金额', color='类别', markers=True, title="特定类别历史支出趋势", color_discrete_sequence=px.colors.qualitative.Pastel)
                    fig_line.update_layout(yaxis=dict(rangemode='tozero'))
                    st.plotly_chart(fig_line, use_container_width=True)
