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
            st.sidebar.error(f"💾 自动归档失败: {e}")

MODEL_CREATIVE = "gemini-2.5-flash"
MODEL_EVAL = "gemini-3.1-pro-preview"

# --- 路由逻辑与身份拦截 (保持 V13.0 逻辑) ---
is_saas_mode = st.query_params.get("mode") == "saas"
if is_saas_mode:
    if st.session_state['user'] is None:
        st.title("🌟 NAL 商业版 (SaaS)")
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("🔑 会员登录")
            l_e = st.text_input("邮箱")
            l_p = st.text_input("密码", type="password")
            if st.button("立即登录"): 
                try:
                    res = supabase.auth.sign_in_with_password({"email": l_e, "password": l_p})
                    st.session_state['user'] = res.user
                    st.rerun()
                except Exception as e: st.error(f"登录失败: {e}")
        with c2:
            st.subheader("📝 注册")
            r_e = st.text_input("常用邮箱")
            r_p = st.text_input("设置密码")
            if st.button("免费注册"):
                try:
                    supabase.auth.sign_up({"email": r_e, "password": r_p})
                    st.success("注册成功！")
                except Exception as e: st.error(f"注册错误: {e}")
        st.stop()
    else:
        if not st.session_state['is_vip']:
            st.title("🚀 解锁 NAL 专业版")
            st.info(f"欢迎，{st.session_state['user'].email}！请激活账户。")
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
            else: st.error("邀请码无效。")
        st.stop()

# --- 主界面 ---
st.sidebar.title("🎨 NAL 控制台")
if is_saas_mode:
    if st.sidebar.button("🚪 退出登录"):
        supabase.auth.sign_out(); st.session_state['user'] = None; st.session_state['is_vip'] = False; st.rerun()

st.title("NAL 数字化文学双擎系统")
tab1, tab2, tab3, tab4 = st.tabs(["💡 创作伴侣", "⚖️ 深度评审", "🏆 评审排行榜", "📁 我的档案室"])

# --- Tab 1: 创作功能 ---
with tab1:
    st.header("💡 NAL智能创作指导系统")
    u_prompt = st.text_area("输入您的灵感片段：", height=150)
    c_filename = st.text_input("📄 设定片段导出文件名", value="NAL_Highlights")

    if st.button("启动 NAL 创作推演") and u_prompt: 
        with st.spinner("创作引擎构思中..."):
            try:
                creative_sys_inst = """你现在是 NAL 金牌创作指导... (保持 V13.0 指令)"""
                model = genai.GenerativeModel(model_name=MODEL_CREATIVE, system_instruction=creative_sys_inst)
                res = model.generate_content(u_prompt, generation_config=genai.types.GenerationConfig(temperature=0.7))
                if res.text:
                    st.session_state['c_guide'] = res.text
                    save_to_nal_archive("creative", c_filename, res.text)
                    st.rerun()
            except Exception as e: st.error(f"引擎异常: {e}")

    if st.session_state.get('c_guide'):
        st.markdown("---")
        st.write(st.session_state['c_guide'])
        # 导出逻辑
        parts = re.split(r'\**[=\-]{2,}\s*片段分割线\s*[=\-]{2,}\**', st.session_state['c_guide'])
        outline = parts[0] if len(parts) > 1 else st.session_state['c_guide']
        snippet = parts[1] if len(parts) > 1 else ""
        
        c1, c2 = st.columns(2)
        with c1:
            d1 = Document(); d1.add_heading('NAL 大纲', 0); d1.add_paragraph(clean_text(outline))
            b1 = io.BytesIO(); d1.save(b1)
            st.download_button("📥 导出作品大纲", b1.getvalue(), "Outline.docx")
        with c2:
            if snippet:
                d2 = Document(); d2.add_heading('NAL 高光片段', 0); d2.add_paragraph(clean_text(snippet))
                b2 = io.BytesIO(); d2.save(b2)
                st.download_button("📥 导出高光片段", b2.getvalue(), f"{c_filename}.docx")

# --- Tab 2: 评审功能 ---
with tab2:
    st.header("⚖️ 深度评审系统")
    up = st.file_uploader("上传作品文本 (.docx)", type=["docx"])
    eval_intervention = st.text_area("📝 评审备注")
    
    if st.button("启动 3.1 Pro 评审") and up:
        with st.spinner("3.1 Pro 评审中..."):
            try:
                word = Document(up); text = "\n".join([p.text for p in word.paragraphs])
                eval_sys_inst = """你现在是 NAL 首席评审专家... (保持 V13.0 指令)"""
                model = genai.GenerativeModel(model_name=MODEL_EVAL, system_instruction=eval_sys_inst)
                res = model.generate_content(f"{text}\n备注：{eval_intervention}", generation_config=genai.types.GenerationConfig(temperature=0.1))
                
                # 分数提取
                score = 0; match = re.search(r"综合评分[\]】]?\s*[:：]\s*\[?(\d{1,3})\]?", res.text.replace('*', ''))
                if match: score = int(match.group(1))
                
                st.session_state['e_report'] = res.text
                st.session_state['e_score'] = score
                st.session_state['e_work_title'] = up.name.rsplit('.', 1)[0]
                st.session_state['e_date'] = time.strftime('%Y-%m-%d %H:%M:%S')
                
                # 记录排行榜
                st.session_state['leaderboard'].append({"作品": up.name, "分数": score, "日期": st.session_state['e_date']})
                save_to_nal_archive("evaluation", up.name, res.text, score)
                st.rerun()
            except Exception as e: st.error(f"评审失败: {e}")

    if st.session_state.get('e_report'):
        st.metric("NAL 综合评分", f"{st.session_state['e_score']} / 100")
        st.write(st.session_state['e_report'])
        rd = Document(); rd.add_heading('NAL 评审报告', 0); rd.add_paragraph(clean_text(st.session_state['e_report']))
        rb = io.BytesIO(); rd.save(rb)
        st.download_button("📥 导出评审报告", rb.getvalue(), f"Report_{st.session_state['e_work_title']}.docx")

# --- Tab 3: 排行榜 ---
with tab3:
    st.header("🏆 NAL 排行榜")
    if st.session_state['leaderboard']:
        st.table(sorted(st.session_state['leaderboard'], key=lambda x: x['分数'], reverse=True))

# --- Tab 4: 我的档案室 ---
with tab4:
    st.header("📁 NAL 云端档案")
    if st.session_state['user']:
        res = supabase.table("nal_archives").select("*").order("created_at", desc=True).execute()
        for arc in res.data:
            with st.expander(f"【{arc['archive_type']}】 {arc['work_title']} - {arc['created_at'][:10]}"):
                st.write(arc['content'][:300] + "...")
                rd = Document(); rd.add_paragraph(clean_text(arc['content']))
                rb = io.BytesIO(); rd.save(rb)
                st.download_button("📥 重新导出", rb.getvalue(), f"Arc_{arc['id'][:4]}.docx", key=arc['id'])
    else: st.warning("登录 SaaS 模式以开启档案同步")
