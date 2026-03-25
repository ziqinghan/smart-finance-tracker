import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import random

# --- 页面全局配置 ---
st.set_page_config(page_title="Smart Finance Tracker", page_icon="💰", layout="wide")

# ==========================================
# 核心数据处理与隐私功能 (Core Functions)
# ==========================================

def apply_privacy_firewall(desc):
    """隐私防火墙：过滤敏感交易"""
    blacklist = ['zelle', 'venmo', 'payroll', 'direct dep']
    desc_lower = str(desc).lower()
    if any(word in desc_lower for word in blacklist):
        return "Private/Hidden Transaction"
    return desc

def cancel_refunds(df):
    """退款抵消逻辑 (Placeholder for Refund Cancellation)"""
    # 实际逻辑可以在这里实现：寻找金额互为正负且日期相近的记录
    return df

# ==========================================
# 新增：灵活月份分析与导出模块
# ==========================================

def render_export_and_analysis_module(df):
    st.markdown("---")
    st.header("📊 自定义月份分析与导出 (Custom Analysis & Export)")
    
    # 1. 预处理时间数据
    if not pd.api.types.is_datetime64_any_dtype(df['Date']):
        df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
    
    df = df.dropna(subset=['Date']).copy()
    df['Month'] = df['Date'].dt.strftime('%Y-%m')
    available_months = sorted(df['Month'].unique(), reverse=True)
    
    if not available_months:
        st.warning("没有可用的月份数据。")
        return
        
    # 2. UI：自由选择月份（单月/多月组合）
    selected_months = st.multiselect(
        "📅 请选择需要分析和导出的月份（支持单选或多选组合）：", 
        options=available_months,
        default=available_months[:1] # 默认选中最近的一个月
    )
    
    if not selected_months:
        st.info("请至少选择一个月份进行分析。")
        return

    # 3. 过滤数据并提取支出
    filtered_df = df[df['Month'].isin(selected_months)].copy()
    
    # 注意：这里假设支出金额 (Amount) 为负数。如果你的账单支出是正数，请调整条件为 > 0
    expenses_df = filtered_df[filtered_df['Amount'] < 0].copy()
    expenses_df['Abs_Amount'] = expenses_df['Amount'].abs()

    if expenses_df.empty:
        st.warning("所选月份没有支出记录。")
        return

    # --- 图表展示区 ---
    col1, col2 = st.columns(2)
    
    # 图表 A：总支出占比饼图 (Pie Chart)
    category_sum = expenses_df.groupby('Category')['Abs_Amount'].sum().reset_index()
    fig_pie = px.pie(
        category_sum, 
        values='Abs_Amount', 
        names='Category', 
        hole=0.4,
        title=f"总支出占比 ({', '.join(selected_months)})"
    )
    
    with col1:
        st.plotly_chart(fig_pie, use_container_width=True)

    fig_trend = None
    with col2:
        if len(selected_months) > 1:
            # 如果选了多个月 -> 展示趋势分析折线图
            trend_df = expenses_df.groupby(['Month', 'Category'])['Abs_Amount'].sum().reset_index()
            trend_df = trend_df.sort_values(by='Month') 
            fig_trend = px.line(
                trend_df, 
                x='Month', 
                y='Abs_Amount', 
                color='Category', 
                markers=True,
                title="📈 分类支出趋势分析 (多月对比)"
            )
            st.plotly_chart(fig_trend, use_container_width=True)
        else:
            # 如果只选了单月 -> 展示金额明细排行榜
            st.markdown(f"**🏆 {selected_months[0]} 支出分类排行**")
            display_sum = category_sum.sort_values(by='Abs_Amount', ascending=False)
            st.dataframe(
                display_sum.style.format({'Abs_Amount': '${:.2f}'}),
                hide_index=True,
                use_container_width=True
            )

    # --- Tracker 明细区 ---
    st.markdown(f"#### 📝 所选月份分类明细 Tracker ({len(filtered_df)} 笔交易)")
    st.dataframe(filtered_df.drop(columns=['Month', 'Abs_Amount'], errors='ignore'), use_container_width=True)

    # --- 导出功能区 ---
    st.markdown("### 📥 导出报告 (Export)")
    export_col1, export_col2 = st.columns(2)
    
    with export_col1:
        # 1. 导出 CSV 数据
        export_csv = filtered_df.drop(columns=['Month', 'Abs_Amount'], errors='ignore')
        csv_data = export_csv.to_csv(index=False).encode('utf-8-sig') # utf-8-sig 防止 Excel 中文乱码
        st.download_button(
            label="📄 导出分类明细数据 (CSV)",
            data=csv_data,
            file_name=f"finance_tracker_{'_'.join(selected_months)}.csv",
            mime="text/csv",
            help="导出纯净的交易记录，可在 Excel / Numbers 中进一步处理。"
        )
        
    with export_col2:
        # 2. 导出交互式 HTML 图表报告
        html_content = f"""
        <html>
        <head><meta charset="utf-8"><title>Finance Report</title></head>
        <body style="font-family: sans-serif; padding: 20px;">
            <h1>个人财务分析报告 / Finance Report</h1>
            <p><strong>包含月份:</strong> {', '.join(selected_months)}</p>
            <p><strong>生成时间:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            <hr>
            <h2>1. 支出占比 (Expense Breakdown)</h2>
            {fig_pie.to_html(full_html=False, include_plotlyjs='cdn')}
        """
        if fig_trend:
            html_content += f"""
            <h2>2. 支出趋势 (Expense Trends)</h2>
            {fig_trend.to_html(full_html=False, include_plotlyjs='cdn')}
            """
        html_content += "</body></html>"
        
        st.download_button(
            label="📈 导出可视化图表报告 (HTML)",
            data=html_content,
            file_name=f"finance_report_{'_'.join(selected_months)}.html",
            mime="text/html",
            help="下载包含动态饼图和折线图的独立网页文件，双击即可在浏览器中查看，绝对保护隐私。"
        )

# ==========================================
# 主程序 UI (Main App)
# ==========================================

def main():
    st.title("💸 Smart Finance Tracker")
    st.write("Privacy-first, crowdsourced personal finance dashboard.")
    
    # 内存初始化：确保数据不落盘
    if 'df' not in st.session_state:
        st.session_state.df = pd.DataFrame()

    # --- 侧边栏：文件上传 ---
    with st.sidebar:
        st.header("📁 上传账单")
        uploaded_file = st.file_uploader("上传银行流水 (CSV)", type=['csv'])
        if uploaded_file is not None:
            try:
                # 解析 CSV (请根据你银行账单的实际列名修改这里)
                df = pd.read_csv(uploaded_file)
                if 'Category' not in df.columns:
                    df['Category'] = 'Uncategorized' # 赋予默认分类
                if 'Description' in df.columns:
                    df['Description'] = df['Description'].apply(apply_privacy_firewall)
                
                st.session_state.df = df
                st.success("数据上传并解析成功！")
            except Exception as e:
                st.error(f"解析文件失败: {e}")
        
        # ⚠️ 测试功能：一键生成测试账单 (方便你立即预览效果)
        if st.session_state.df.empty:
            st.markdown("---")
            st.write("没有账单？先体验一下功能：")
            if st.button("🪄 生成多月测试数据 (Demo Data)"):
                dates = pd.date_range(start="2023-08-01", end="2023-10-31", freq="D")
                categories = ['Food', 'Transport', 'Entertainment', 'Utilities', 'Shopping', 'Rent']
                data = {
                    'Date': dates,
                    'Description': [f"Demo Transaction {i}" for i in range(len(dates))],
                    'Amount': [random.uniform(-150, -10) for _ in range(len(dates))], # 负数代表支出
                    'Category': [random.choice(categories) for _ in range(len(dates))]
                }
                st.session_state.df = pd.DataFrame(data)
                st.rerun()

    # --- 主界面 ---
    if not st.session_state.df.empty:
        # 功能：Real-time Global Edit
        st.subheader("🛠️ 全局交易数据编辑器 (Global Data Editor)")
        st.write("提示：双击表格修改 `Category` 分类，下方的分析图表和导出模块会**实时刷新**。")
        
        edited_df = st.data_editor(
            st.session_state.df,
            use_container_width=True,
            num_rows="dynamic",
            key="data_editor"
        )
        
        # 如果用户编辑了数据，保存回 session_state 并刷新界面
        if not edited_df.equals(st.session_state.df):
            st.session_state.df = edited_df
            st.rerun()

        # 调用核心：渲染分析与导出模块
        render_export_and_analysis_module(st.session_state.df)
        
    else:
        st.info("👈 请在左侧上传银行账单，或点击生成测试数据来查看新功能。")

if __name__ == "__main__":
    main()