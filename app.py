import streamlit as st
import google.generativeai as genai
from docx import Document
import io
import os
import time
import re
from supabase import create_client, Client

# --- 🌟 1. 保持原有的强力文本清洗器 ---
def clean_text(text):
    if not isinstance(text, str): return ""
    return re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', text)

st.set_page_config(page_title="NAL 数字化文学平台", layout="wide", page_icon="📚")

# --- 🌟 2. 保持原有的 Session State 初始化 ---
init_keys = {
    "user": None, "access_granted": False, "is_vip": False, 
    "e_report": None, "e_score": 0, "e_date": "", "e_work_title": "",
    "c_guide": None, "leaderboard": [], "last_eval_time": 0.0,
    "last_creative_prompt": "", "last_eval_text": ""
}
for key, value in init_keys.items():
    if key not in st.session_state:
        st.session_state[key] = value

# --- 🌟 3. 保持原有的 API 配置逻辑 (适配 Render/Streamlit) ---
try:
    # 兼容性读取：优先 secrets (Streamlit), 次选 env (Render)
    api_key = st.secrets.get("GEMINI_API_KEY") or os.getenv("GEMINI_API_KEY")
    if api_key:
        genai.configure(api_key=api_key)
    else:
        st.error("❌ 错误：未检测到 GEMINI_API_KEY。")
        st.stop()
except Exception as e:
    st.error(f"无法配置 Gemini API: {e}")

SUPABASE_URL = st.secrets.get("SUPABASE_URL") or os.getenv("SUPABASE_URL")
SUPABASE_KEY = st.secrets.get("SUPABASE_KEY") or os.getenv("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- 🗄️ 新增：数据归档核心函数 (不干扰原有逻辑) ---
def save_to_nal_archive(archive_type, title, content, score=0):
    if st.session_state.get('user'):
        try:
            supabase.table("nal_archives").insert({
                "user_id": st.session_state['user'].id,
                "archive_type": archive_type,
                "work_title": title,
                "content": content,
                "score": score
            }).execute()
        except Exception as e:
            st.sidebar.error(f"💾 归档失败: {e}")

MODEL_CREATIVE = "gemini-2.5-flash"
MODEL_EVAL = "gemini-3.1-pro-preview"

# --- 🌟 4. 保持原有的路由逻辑与支付墙拦截 ---
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
            else: st.error("邀请码无效。")
        st.stop()

# --- 🌟 5. 保持原有的主功能界面 ---
st.sidebar.title("🎨 NAL 控制台")
if is_saas_mode:
    st.sidebar.success(f"已登录: {st.session_state['user'].email}")
    if st.sidebar.button("🚪 退出登录"):
        supabase.auth.sign_out(); st.session_state['user'] = None; st.session_state['is_vip'] = False; st.rerun()
else:
    st.sidebar.info("模式：内部邀请评测")
    st.sidebar.text(f"首席评委：NAL")

st.title("NAL 数字化文学双擎系统")
tab1, tab2, tab3, tab4 = st.tabs(["💡 创作伴侣", "⚖️ 深度评审", "🏆 评审排行榜", "📁 我的档案室"])

# --- Tab 1: 创作功能 (完全保留您的 Prompt 和逻辑) ---
with tab1:
    st.header("💡 NAL智能创作指导系统")
    u_prompt = st.text_area("输入您的灵感片段：", placeholder="输入主题...", height=150)
    c_filename = st.text_input("📄 设定片段导出文件名", value="NAL_Highlights")

    if st.button("启动 NAL 创作推演"): 
        with st.spinner("创作引擎构思中..."):
            try:
                creative_sys_inst = """你现在是 NewArtLiterature (NAL) 的金牌创作指导...""" # 此处省略，实际部署请粘贴您的完整 Prompt
                model = genai.GenerativeModel(model_name=MODEL_CREATIVE, system_instruction=creative_sys_inst)
                res = model.generate_content(u_prompt, generation_config=genai.types.GenerationConfig(temperature=0.7))
                if res.text:
                    st.session_state['c_guide'] = res.text
                    save_to_nal_archive("creative", c_filename, res.text)
                    st.rerun()
            except Exception as e: st.error(f"引擎异常: {e}")

    if st.session_state.get('c_guide'):
        st.write(st.session_state['c_guide'])
        # 保持您原有的正则表达式拆分下载逻辑
        parts = re.split(r'\**[=\-]{2,}\s*片段分割线\s*[=\-]{2,}\**', st.session_state['c_guide'])
        outline_content = parts[0].strip() if len(parts) > 1 else st.session_state['c_guide']
        snippet_content = parts[1].strip() if len(parts) > 1 else ""
        
        col_d1, col_d2 = st.columns(2)
        with col_d1:
            d1 = Document(); d1.add_heading('NAL 创作大纲', 0); d1.add_paragraph(clean_text(outline_content))
            b1 = io.BytesIO(); d1.save(b1)
            st.download_button("📥 导出作品大纲", b1.getvalue(), "NAL_Outline.docx")
        with col_d2:
            if snippet_content:
                d2 = Document(); d2.add_heading('NAL 创作高光片段', 0); d2.add_paragraph(clean_text(snippet_content))
                b2 = io.BytesIO(); d2.save(b2)
                st.download_button("📥 导出高光片段", b2.getvalue(), f"{c_filename}.docx")

# --- Tab 2: 评审功能 (完全保留您的 Prompt 和逻辑) ---
with tab2:
    st.header("⚖️ 深度评审系统")
    up = st.file_uploader("上传作品文本 (.docx)", type=["docx"])
    eval_intervention = st.text_area("📝 评审备注")
    
    if st.button("启动 3.1 Pro 评审") and up:
        with st.spinner("3.1 Pro 评审中..."):
            try:
                word = Document(up); current_text = "\n".join([p.text for p in word.paragraphs])
                eval_sys_inst = """你现在是 NewArtLiterature (NAL) 首席评审专家...""" # 此处省略，实际部署请粘贴您的完整 Prompt
                model = genai.GenerativeModel(model_name=MODEL_EVAL, system_instruction=eval_sys_inst)
                res = model.generate_content(f"{current_text}\n备注：{eval_intervention}", generation_config=genai.types.GenerationConfig(temperature=0.1))
                
                # 保持您原有的分数提取逻辑
                score = 0; clean_res = res.text.replace('*', '')
                match = re.search(r"综合评分[\]】]?\s*[:：]\s*\[?(\d{1,3})\]?", clean_res)
                if match: score = int(match.group(1))
                
                st.session_state['e_report'] = res.text
                st.session_state['e_score'] = score
                st.session_state['e_work_title'] = up.name.rsplit('.', 1)[0]
                st.session_state['e_date'] = time.strftime('%Y-%m-%d %H:%M:%S')
                st.session_state['leaderboard'].append({"作品": up.name, "分数": score, "日期": st.session_state['e_date']})
                
                save_to_nal_archive("evaluation", up.name, res.text, score)
                st.rerun()
            except Exception as e: st.error(f"评审失败: {e}")

    if st.session_state.get('e_report'):
        st.metric("NAL 综合评分", f"{st.session_state['e_score']} / 100")
        st.write(st.session_state['e_report'])
        rd = Document(); rd.add_heading(f"NAL 评审报告 - {st.session_state['e_work_title']}", 0)
        rd.add_paragraph(clean_text(st.session_state['e_report']))
        rb = io.BytesIO(); rd.save(rb)
        st.download_button("📥 导出评审报告", rb.getvalue(), f"NAL_Report_{st.session_state['e_work_title']}.docx")

# --- Tab 3: 排行榜 (保持原样) ---
with tab3:
    st.header("🏆 NAL 评审作品排行榜")
    if st.session_state['leaderboard']:
        st.table(sorted(st.session_state['leaderboard'], key=lambda x: x['分数'], reverse=True))

# --- Tab 4: 我的档案室 (基于您上传代码的环境变量和用户逻辑) ---
with tab4:
    st.header("📁 NAL 云端档案库")
    if st.session_state['user']:
        try:
            res = supabase.table("nal_archives").select("*").order("created_at", desc=True).execute()
            if res.data:
                for arc in res.data:
                    with st.expander(f"【{arc['archive_type'].upper()}】 {arc['work_title']} - {arc['created_at'][:10]}"):
                        st.write(arc['content'][:300] + "...")
                        doc = Document(); doc.add_paragraph(clean_text(arc['content']))
                        bio = io.BytesIO(); doc.save(bio)
                        st.download_button("📥 重新导出 Docx", bio.getvalue(), f"Arc_{arc['id'][:4]}.docx", key=arc['id'])
            else: st.info("暂无档案。")
        except Exception as e: st.error(f"读取失败: {e}")
    else: st.warning("请在 SaaS 模式下登录以查看档案。")
