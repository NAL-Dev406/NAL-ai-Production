import streamlit as st
import google.generativeai as genai
from docx import Document
import io
import os
import time
import re
from supabase import create_client, Client

# --- 🌟 强力文本清洗器 ---
def clean_text(text):
    if not isinstance(text, str): return ""
    return re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', text)

st.set_page_config(page_title="NAL 数字化文学平台", layout="wide", page_icon="📚")

# --- 🚀 初始化 Session State ---
init_keys = {
    "user": None, "access_granted": False, "is_vip": False, 
    "e_report": None, "e_score": 0, "e_date": "", "e_work_title": "",
    "c_guide": None, "leaderboard": [], "last_eval_time": 0.0,
    "last_creative_prompt": "", "last_eval_text": ""
}
for key, value in init_keys.items():
    if key not in st.session_state:
        st.session_state[key] = value

# --- 🔒 生产环境安全配置 ---
try:
    api_key = os.getenv("GEMINI_API_KEY")
    if api_key:
        genai.configure(api_key=api_key)
    else:
        st.error("❌ 错误：未检测到 GEMINI_API_KEY。")
        st.stop()
except Exception as e:
    st.error(f"无法配置 Gemini API: {e}")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- 🗄️ 数据归档核心逻辑 ---
def save_to_nal_archive(archive_type, title, content, score=0):
    """将生成内容自动保存到 Supabase"""
    if st.session_state.get('user'):
        try:
            data = {
                "user_id": st.session_state['user'].id,
                "archive_type": archive_type,
                "work_title": title,
                "content": content,
                "score": score
            }
            supabase.table("nal_archives").insert(data).execute()
        except Exception as e:
            st.sidebar.error(f"💾 归档失败: {e}")

MODEL_CREATIVE = "gemini-2.5-flash"
MODEL_EVAL = "gemini-3.1-pro-preview"

# --- 路由逻辑与支付墙拦截 ---
is_saas_mode = st.query_params.get("mode") == "saas"
if is_saas_mode:
    if st.session_state['user'] is None:
        st.title("🌟 NAL 商业版 (SaaS)")
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("🔑 现有会员登录")
            l_e = st.text_input("邮箱")
            l_p = st.text_input("密码", type="password")
            if st.button("立即登录"): 
                try:
                    res = supabase.auth.sign_in_with_password({"email": l_e, "password": l_p})
                    st.session_state['user'] = res.user
                    st.rerun()
                except Exception as e: st.error(f"登录失败，原因: {e}")
        with c2:
            st.subheader("📝 注册新会员")
            r_e = st.text_input("常用邮箱")
            r_p = st.text_input("设置密码")
            if st.button("免费注册"):
                try:
                    supabase.auth.sign_up({"email": r_e, "password": r_p})
                    st.success("注册成功！请检查邮箱或直接登录。")
                except Exception as e: st.error(f"注册错误: {e}")
        st.stop()
    else:
        if not st.session_state['is_vip']:
            st.title("🚀 解锁 NAL 专业版双擎系统")
            st.markdown(f"欢迎您，**{st.session_state['user'].email}**！")
            c_pay1, c_pay2, c_pay3 = st.columns([1, 2, 1])
            with c_pay2:
                st.info("💎 **NAL Pro 创作者订阅**\n\n- 开启无限次金牌创作推演\n- 启动极其严苛的 3.1 Pro 深度评审")
                if st.button("🛠️ [开发者通道] 模拟支付成功，一键激活", use_container_width=True):
                    st.session_state['is_vip'] = True
                    st.rerun()
            st.stop()
else:
    if not st.session_state["access_granted"]:
        st.title("🔒 NAL 内部测试系统")
        inv = st.text_input("评委/作者邀请码：", type="password")
        if st.button("确认进入"): 
            env_codes = os.getenv("NAL_INVITE_CODES")
            VALID_CODES = [c.strip() for c in env_codes.split(",")] if env_codes else ["NAL2026"]
            if inv in VALID_CODES: 
                st.session_state["access_granted"] = True
                st.rerun()
            else: 
                st.error("邀请码无效。")
        st.stop()

# --- 主功能界面 ---
st.sidebar.title("🎨 NAL 控制台")
if is_saas_mode:
    st.sidebar.success(f"已登录: {st.session_state['user'].email}")
    if st.sidebar.button("🚪 退出登录"):
        supabase.auth.sign_out()
        st.session_state['user'] = None
        st.session_state['is_vip'] = False
        st.rerun()
else:
    st.sidebar.info("模式：内部邀请评测")

st.title("NAL 数字化文学双擎系统")
tab1, tab2, tab3, tab4 = st.tabs(["💡 创作伴侣", "⚖️ 深度评审", "🏆 评审排行榜", "📁 我的档案室"])

# --- Tab 1: 创作功能 ---
with tab1:
    st.header("💡 NAL智能创作指导系统")
    u_prompt = st.text_area("输入您的灵感片段：", height=150)
    c_filename = st.text_input("📄 设定片段导出文件名", value="NAL_Highlights")

    if st.button("启动 NAL 创作推演"): 
        with st.spinner("创作引擎正在极速构思..."):
            try:
                creative_sys_inst = """你现在是 NewArtLiterature (NAL) 的金牌创作指导... (此处保持 V13.0 指令)"""
                model = genai.GenerativeModel(model_name=MODEL_CREATIVE, system_instruction=creative_sys_inst)
                res = model.generate_content(u_prompt, generation_config=genai.types.GenerationConfig(temperature=0.7))
                
                if res.text:
                    st.session_state['c_guide'] = res.text
                    # 🌟 自动归档
                    save_to_nal_archive("creative", c_filename, res.text)
                    st.rerun() 
            except Exception as e: st.error(f"错误: {e}")

    if st.session_state.get('c_guide'):
        st.write(st.session_state['c_guide'])
        # ... (导出 Docx 逻辑保持不变)

# --- Tab 2: 评审功能 ---
with tab2:
    st.header("⚖️ 深度评审系统")
    up = st.file_uploader("上传作品文本 (.docx)", type=["docx"])
    eval_intervention = st.text_area("📝 人工干预与评审备注")
    
    if st.button("启动 3.1 Pro 评审") and up: 
        with st.spinner("3.1 Pro 正在严苛审查..."):
            try:
                # ... (评审逻辑与分数提取保持不变)
                eval_sys_inst = """你现在是 NAL 首席评审专家... (此处保持 V13.0 指令)"""
                model = genai.GenerativeModel(model_name=MODEL_EVAL, system_instruction=eval_sys_inst)
                res = model.generate_content(f"{up.name}\n{eval_intervention}", generation_config=genai.types.GenerationConfig(temperature=0.1))
                
                if res.text:
                    st.session_state['e_report'] = res.text
                    # 🌟 自动归档
                    save_to_nal_archive("evaluation", up.name, res.text, st.session_state.get('e_score', 0))
                    st.rerun()
            except Exception as e: st.error(f"错误: {e}")

# --- Tab 3: 排行榜 (代码同 V13.0) ---

# --- Tab 4: 我的档案室 (🌟 新增) ---
with tab4:
    st.header("📁 NAL 文学档案库")
    if st.session_state['user']:
        try:
            response = supabase.table("nal_archives").select("*").order("created_at", desc=True).execute()
            archives = response.data
            
            if archives:
                for arc in archives:
                    with st.expander(f"【{arc['archive_type'].upper()}】 {arc['work_title']} - {arc['created_at'][:10]}"):
                        st.markdown(f"**得分：{arc['score']}**" if arc['archive_type'] == 'evaluation' else "")
                        st.write(arc['content'][:500] + "...")
                        
                        # 提供重新导出的能力
                        doc = Document()
                        doc.add_heading(arc['work_title'], 0)
                        doc.add_paragraph(clean_text(arc['content']))
                        bio = io.BytesIO(); doc.save(bio)
                        st.download_button(f"📥 重新导出 {arc['work_title']}", bio.getvalue(), f"Archive_{arc['work_title']}.docx", key=arc['id'])
            else:
                st.info("暂无历史档案。您的每一次生成都将自动保存至此。")
        except Exception as e:
            st.error(f"无法读取档案: {e}")
    else:
        st.warning("请在 SaaS 模式下登录以开启云端档案同步。")
