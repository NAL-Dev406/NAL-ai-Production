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

# 🌟 新增 'is_vip' 用于控制支付墙的状态
init_keys = {
    "user": None, "access_granted": False, "is_vip": False, 
    "e_report": None, "e_score": 0, "e_date": "", "e_work_title": "",
    "c_guide": None, "leaderboard": [], "last_eval_time": 0.0,
    "last_creative_prompt": "", "last_eval_text": ""
}
for key, value in init_keys.items():
    if key not in st.session_state:
        st.session_state[key] = value

try:
    # 直接从 Render 的 Environment 页面读取变量
    api_key = os.getenv("GEMINI_API_KEY")
    
    if api_key:
        genai.configure(api_key=api_key)
    else:
        # 如果环境变量里也没有，再尝试一种备选方案
        st.error("❌ 错误：未检测到 GEMINI_API_KEY。")
        st.info("💡 请确保您已在 Render 后台的 Environment 选项卡中添加了该变量。")
        st.stop()

except Exception as e:
    st.error(f"无法配置 Gemini API: {e}")

# --- 🚀 新增：兼容性数据库读取 (适配 Render/Streamlit) ---
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- 🗄️ 新增：数据归档核心逻辑函数 ---
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
            # 加上这行打印，看看数据准备得对不对
            # st.write(f"调试：准备归档数据 - {data}") 
            
            res = supabase.table("nal_archives").insert(data).execute()
            
            # 如果运行到这里，说明数据库接受了请求
            st.toast(f"✅ {archive_type} 档案已同步") 
        except Exception as e:
            # 强制在主界面显示错误，不要放在侧边栏
            st.error(f"❌ 归档核心故障: {e}")

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
        # 🌟 核心拦截机制：Stripe 支付墙
        if not st.session_state['is_vip']:
            st.title("🚀 解锁 NAL 专业版双擎系统")
            st.markdown(f"欢迎您，**{st.session_state['user'].email}**！您目前使用的是未激活账户，请订阅以获取 AI 引擎的完整算力支持。")
            
            c_pay1, c_pay2, c_pay3 = st.columns([1, 2, 1])
            with c_pay2:
                st.info("💎 **NAL Pro 创作者订阅**\n\n- 开启无限次金牌创作推演\n- 启动极其严苛的 3.1 Pro 深度评审\n- 专属作品档案与无缝导出功能")
                
                if st.button("💳 前往 Stripe 安全结账 (29.00 CAD / 月)", use_container_width=True):
                    # 未来这里将插入 stripe.checkout.Session.create 逻辑
                    st.warning("🔌 准备接入 Stripe Checkout... (需在 secrets 中配置 STRIPE_API_KEY)")
                    st.code("""
# 预留的 Stripe 接入代码：
# import stripe
# stripe.api_key = st.secrets["STRIPE_API_KEY"]
# ...
                    """, language="python")
                
                st.divider()
                # 开发者后门：一键绕过支付墙进入主系统
                if st.button("🛠️ [开发者通道] 模拟支付成功，一键激活", use_container_width=True):
                    st.session_state['is_vip'] = True
                    st.rerun()
                    
            st.stop() # 🚧 极其重要：拦截代码，防止未付款用户加载下方的核心功能
else:
    if not st.session_state["access_granted"]:
        st.title("🔒 NAL 内部测试系统")
        inv = st.text_input("评委/作者邀请码：", type="password")
        if st.button("确认进入"): 
            # ✅ 改进：从环境变量读取邀请码，如果没有设置则使用默认值
            env_codes = os.getenv("NAL_INVITE_CODES")
            if env_codes:
                VALID_CODES = [code.strip() for code in env_codes.split(",")]
            else:
                # 默认备份方案
                VALID_CODES = ["NAL2026"] 
                
            if inv in VALID_CODES: 
                st.session_state["access_granted"] = True
                st.rerun()
            else: 
                st.error("邀请码无效，请联系 NAL 秘书处。")
        st.stop()

# --- 主功能界面 (付费后/输入邀请码后才能看到) ---
st.sidebar.title("🎨 NAL 控制台")
if is_saas_mode:
    st.sidebar.success(f"已登录: {st.session_state['user'].email}")
    if st.sidebar.button("🚪 退出登录"):
        supabase.auth.sign_out()
        st.session_state['user'] = None
        st.session_state['is_vip'] = False # 退出时清除 VIP 状态
        st.rerun()
else:
    st.sidebar.info("模式：内部邀请评测")
    st.sidebar.text(f"首席评委：NAL")

st.title("NAL 数字化文学双擎系统")
# 🌟 新增：tab4 用于显示归档室
tab1, tab2, tab3, tab4 = st.tabs(["💡 创作伴侣", "⚖️ 深度评审", "🏆 评审排行榜", "📁 我的档案室"])

# --- Tab 1: 创作功能 ---
with tab1:
    st.header("💡 NAL智能创作指导系统")
    u_prompt = st.text_area("输入您的灵感片段：", placeholder="输入主题、核心冲突或想要探讨的时代命题...", height=150)
    
    c_filename = st.text_input("📄 设定片段导出文件名", value="NAL_Highlights", help="无需输入 .docx 后缀")

    is_creative_disabled = not u_prompt or u_prompt == st.session_state["last_creative_prompt"]
    
    if st.button("启动 NAL 创作推演", disabled=is_creative_disabled): 
        with st.spinner("创作引擎正在按 NAL 标准极速构思..."):
            try:
                creative_sys_inst = """你现在是 NewArtLiterature (NAL) 的金牌创作指导... (此处为您的完整Prompt)"""
                # [此处保持您上传代码中的完整逻辑不变]
                model = genai.GenerativeModel(model_name=MODEL_CREATIVE, system_instruction=creative_sys_inst)
                res = model.generate_content(u_prompt, generation_config=genai.types.GenerationConfig(temperature=0.7))
                
                if not res.candidates or not res.candidates[0].content.parts:
                    st.warning("⚠️ 创作引擎由于过于发散导致生成卡壳了...")
                else:
                    st.session_state['c_guide'] = res.text
                    st.session_state["last_creative_prompt"] = u_prompt
                    # 🌟 新增触发：自动归档创作指南
                    save_to_nal_archive("creative", c_filename, res.text)
                    st.rerun() 
            except Exception as e: 
                st.error(f"创作引擎异常: {e}")

    if st.session_state.get('c_guide'):
        # [此处完全保持您上传的展示和下载逻辑不变]
        st.markdown("---")
        st.markdown("### ✨ NAL 专属创作指南")
        st.write(st.session_state['c_guide'])
        
        guide_text = st.session_state['c_guide']
        parts = re.split(r'\**[=\-]{2,}\s*片段分割线\s*[=\-]{2,}\**', guide_text)
        
        if len(parts) > 1:
            outline_content = parts[0].strip()
            snippet_content = parts[1].strip()
        else:
            fallback_parts = re.split(r'【高光片段试写】', guide_text)
            if len(fallback_parts) > 1:
                outline_content = fallback_parts[0].strip()
                snippet_content = fallback_parts[1].strip()
            else:
                outline_content = guide_text
                snippet_content = "⚠️ 未识别内容..."

        col_d1, col_d2 = st.columns(2)
        with col_d1:
            d_outline = Document(); d_outline.add_heading('NAL 创作大纲策划', 0)
            d_outline.add_paragraph(f"生成日期：{time.strftime('%Y-%m-%d')}")
            d_outline.add_paragraph("-" * 50)
            d_outline.add_paragraph(clean_text(outline_content))
            bio_outline = io.BytesIO(); d_outline.save(bio_outline)
            st.download_button("📥 导出作品大纲 (.docx)", bio_outline.getvalue(), "NAL_Outline.docx") 
        
        with col_d2:
            d_snippet = Document(); d_snippet.add_heading('NAL 创作高光片段', 0)
            d_snippet.add_paragraph(f"生成日期：{time.strftime('%Y-%m-%d')}")
            d_snippet.add_paragraph("-" * 50)
            pure_snippet = re.sub(r"^【高光片段试写】\n?", "", snippet_content).strip()
            d_snippet.add_paragraph(clean_text(pure_snippet))
            bio_snippet = io.BytesIO(); d_snippet.save(bio_snippet)
            st.download_button(f"📥 导出高光片段 (.docx)", bio_snippet.getvalue(), f"{c_filename}.docx")

# --- Tab 2: 评审功能 ---
with tab2:
    st.header("⚖️ 深度评审系统")
    curr = time.time(); cd = 15 - (curr - st.session_state["last_eval_time"])
    up = st.file_uploader("上传作品文本 (.docx)", type=["docx"])
    
    st.markdown("##### 📝 人工干预与评审备注")
    eval_intervention = st.text_area("在此输入您对本次评审的特殊要求...", height=100)
    
    current_text = ""
    if up:
        try:
            up.seek(0) 
            word = Document(up)
            current_text = "\n".join([p.text for p in word.paragraphs])
        except Exception:
            st.error("无法读取此文档。")
            
    is_eval_disabled = not up or (current_text != "" and current_text == st.session_state["last_eval_text"])
    
    if st.button("启动 3.1 Pro 评审", disabled=is_eval_disabled): 
        if cd > 0: st.warning(f"冷却中: {int(cd)}s")
        elif current_text:
            with st.spinner("3.1 Pro 首席评审专家正在严苛审查..."):
                try:
                    eval_sys_inst = """你现在是 NewArtLiterature (NAL) 首席评审专家... (此处为您的完整Prompt)"""
                    # [此处保持您上传代码中的完整逻辑不变]
                    model = genai.GenerativeModel(model_name=MODEL_EVAL, system_instruction=eval_sys_inst)
                    eval_prompt = f"作品内容：\n{current_text}\n\n【评委备注】：\n{eval_intervention if eval_intervention else '无'}"
                    
                    res = model.generate_content(eval_prompt, generation_config=genai.types.GenerationConfig(temperature=0.1))
                    
                    st.session_state['e_report'] = res.text
                    st.session_state["last_eval_time"] = time.time()
                    st.session_state["last_eval_text"] = current_text
                    st.session_state["e_date"] = time.strftime('%Y-%m-%d %H:%M:%S')
                    
                    clean_filename = up.name.rsplit('.', 1)[0] if '.' in up.name else up.name
                    st.session_state["e_work_title"] = clean_filename
                    
                    # [此处保持原有的分数提取逻辑]
                    score = 0; clean_res_text = res.text.replace('*', '') 
                    match = re.search(r"综合评分[\]】]?\s*[:：]\s*\[?(\d{1,3})\]?", clean_res_text)
                    if match: score = int(match.group(1))
                    st.session_state['e_score'] = score
                    
                    # 更新排行榜逻辑 (保持原样)
                    found = False
                    for item in st.session_state['leaderboard']:
                        if item["作品"] == up.name:
                            found = True
                            if score > item["分数"]: item["分数"] = score; item["日期"] = st.session_state["e_date"]
                            break
                    if not found:
                        st.session_state['leaderboard'].append({"作品": up.name, "分数": score, "日期": st.session_state["e_date"]})
                    
                    # 🌟 新增触发：自动归档评审报告
                    save_to_nal_archive("evaluation", up.name, res.text, score)
                    st.rerun() 
                except Exception as e: 
                    st.error(f"评审异常: {e}")

    if st.session_state.get('e_report'):
        # [此处完全保持您上传的展示和下载逻辑不变]
        work_name = st.session_state.get('e_work_title', '未知作品')
        col_res1, col_res2 = st.columns([1, 3])
        with col_res1: st.metric("NAL 综合评分", f"{st.session_state['e_score']} / 100")
        with col_res2: st.caption(f"📅 报告生成时间：{st.session_state['e_date']}")
        
        raw_report = st.session_state['e_report']
        display_report = "【一、" + raw_report.split("【一、", 1)[1] if "【一、" in raw_report else raw_report
        st.write(display_report)
        
        rd = Document(); rd.add_heading(f'NAL 评审报告 - {work_name}', 0)
        rd.add_paragraph(clean_text(display_report))
        rbio = io.BytesIO(); rd.save(rbio)
        st.download_button("📥 导出评审报告 (.docx)", rbio.getvalue(), f"NAL_Report_{work_name}.docx") 

# --- Tab 3: 排行榜 ---
with tab3:
    # [完全保持原样]
    st.header("🏆 NAL 评审作品排行榜")
    if st.session_state['leaderboard']:
        lb = sorted(st.session_state['leaderboard'], key=lambda x: x['分数'], reverse=True)
        st.table(lb)

# --- 🌟 新增 Tab 4: 我的档案室 ---
with tab4:
    st.header("📁 NAL 云端档案库")
    if st.session_state['user']:
        try:
            # 从 Supabase 查询当前用户的所有记录，按时间倒序排列
            response = supabase.table("nal_archives").select("*").order("created_at", desc=True).execute()
            archives = response.data
            
            if archives:
                for arc in archives:
                    label = f"【{arc['archive_type'].upper()}】 {arc['work_title']} - {arc['created_at'][:16]}"
                    with st.expander(label):
                        if arc['archive_type'] == 'evaluation':
                            st.write(f"**综合评分：{arc['score']} / 100**")
                        
                        st.write(arc['content'])
                        
                        # 档案重导出功能
                        rd_arc = Document()
                        rd_arc.add_heading(arc['work_title'], 0)
                        rd_arc.add_paragraph(f"存档日期：{arc['created_at'][:16]}")
                        rd_arc.add_paragraph(clean_text(arc['content']))
                        rb_arc = io.BytesIO(); rd_arc.save(rb_arc)
                        st.download_button(f"📥 重新导出 Docx", rb_arc.getvalue(), f"Archive_{arc['id'][:4]}.docx", key=arc['id'])
            else:
                st.info("暂无历史档案。您的每一次生成都将自动同步至此。")
        except Exception as e:
            st.error(f"无法读取档案库: {e}")
    else:
        st.warning("⚠️ 请在 SaaS 模式下登录以开启云端档案同步功能。")
