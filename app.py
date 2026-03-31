import streamlit as st
import google.generativeai as genai
from docx import Document
import io
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
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
except:
    st.error("❌ 错误：未检测到 API Key。请在 Streamlit 控制台配置。")

SUPABASE_URL = "https://hwprweoyqvkwlbqffngh.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imh3cHJ3ZW95cXZrd2xicWZmbmdoIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzQ5MDY5ODQsImV4cCI6MjA5MDQ4Mjk4NH0.zLr6zdJALR8p2xmjtueENFsGUtEpginY_vsYMUgM2us"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

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
# session = stripe.checkout.Session.create(
#     payment_method_types=['card'],
#     line_items=[{'price': 'price_1XXX', 'quantity': 1}],
#     mode='subscription',
#     success_url='https://your-app-url.com/?mode=saas&pay=success',
#     cancel_url='https://your-app-url.com/?mode=saas',
#     client_reference_id=st.session_state['user'].id
# )
# 自动跳转到 session.url
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
            VALID_CODES = ["NAL2026", "EDITOR_ZXW", "EDITOR_CBT", "EDITOR_GFR"]
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
tab1, tab2, tab3 = st.tabs(["💡 创作伴侣", "⚖️ 深度评审", "🏆 评审排行榜"])

# --- Tab 1: 创作功能 ---
with tab1:
    st.header("💡 NAL智能创作指导系统")
    u_prompt = st.text_area("输入您的灵感片段：", placeholder="输入主题、核心冲突或想要探讨的时代命题...", height=150)
    
    c_filename = st.text_input("📄 设定片段导出文件名", value="NAL_Highlights", help="无需输入 .docx 后缀")

    is_creative_disabled = not u_prompt or u_prompt == st.session_state["last_creative_prompt"]
    
    if st.button("启动 NAL 创作推演", disabled=is_creative_disabled): 
        with st.spinner("创作引擎正在按 NAL 标准极速构思..."):
            try:
                creative_sys_inst = """你现在是 NewArtLiterature (NAL) 的金牌创作指导。
你的任务是协助作者进行儿童文学的构思与大纲策划。请确保你给出的创作建议，完美契合 NAL 的极高文学标准：
1. 【破除人造儿童】：提供的人物设定必须具备当代儿童的真实心理与生理特征，拒绝说教与低幼化。
2. 【时代与技术异化】：在情节构思中，主动引导作者探讨新媒体、新技术如何影响成人（父母的焦虑、缺席），并转嫁给儿童。
3. 【跨界共鸣】：大纲的内核必须具备“双重阅读价值”，表面写儿童，深层要能刺痛或抚慰成人的灵魂。
4. 【生理心理同频】：设定的叙事视角和语言风格，必须符合目标年龄段。

【强制输出格式要求】
请严格按照以下四个部分的结构依次输出，绝不允许省略或缩水：
【核心立意升华】
（深入阐述立意）
【人物弧光设定】
（详细设定人物）
【情节大纲建议】
（提供具体情节脉络）

===片段分割线===

【高光片段试写】
（在此处，你必须实打实地撰写一段 500-800 字的纯粹文学选段！必须包含极强的画面感和情绪张力，绝不能偷懒或只写短句！）"""

                model = genai.GenerativeModel(model_name=MODEL_CREATIVE, system_instruction=creative_sys_inst)
                res = model.generate_content(u_prompt, generation_config=genai.types.GenerationConfig(temperature=0.7))
                
                if not res.candidates or not res.candidates[0].content.parts:
                    st.warning("⚠️ 创作引擎由于过于发散导致生成卡壳了。请对您的灵感片段稍微增减几个字，然后再次点击生成！")
                else:
                    st.session_state['c_guide'] = res.text
                    st.session_state["last_creative_prompt"] = u_prompt
                    st.rerun() 
            except Exception as e: 
                if "finish_reason is 1" in str(e) or "valid Part" in str(e):
                    st.warning("⚠️ AI 引擎偷懒返回了空文本。请稍微修改您的输入后重试！")
                else:
                    st.error(f"创作引擎异常: {e}")

    if st.session_state.get('c_guide'):
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
                snippet_content = "⚠️ 未识别到高光片段内容，AI 可能因算力限制中断了输出。请稍加修改后重试。"

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
    eval_intervention = st.text_area("在此输入您对本次评审的特殊要求或想对作者说的话（可选）：", 
                                    placeholder="例如：请特别关注文中对祖孙关系的描写，或在此加入评委的人工寄语...", height=100)
    
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
            with st.spinner("3.1 Pro 首席评审专家正在整合人工指令进行严苛审查..."):
                try:
                    eval_sys_inst = """你现在是 NewArtLiterature (NAL) 首席儿童文学评审专家。
你的评审标准极其严苛，拒绝空洞说教，兼具时代批判精神与人文关怀。请严格按照以下结构输出报告，且第一行必须是评分：

【综合评分】: [在此处仅输出一个0-100的纯数字，50分为及格，85分以上为杰作]

【一、 儿童观与人物塑造 (破除“人造儿童”)】
- 严厉排查并批判作品中是否出现了由成人主观臆想、拼凑的“人造儿童”。
- 评估人物是否具备真实的当代儿童心理与身体变化特征，拒绝对儿童的“低幼化”或“成人化”扭曲。

【二、 时代镜像与技术异化】
- 关注当代性：是否敏锐捕捉到了新媒体、新设备、新技术对当代儿童认知、社交与生活方式的直接冲击。
- 深度挖掘间接影响：技术与新媒介如何异化了书中的成人（如父母/老师的焦虑、缺席或注意力分散），并最终将这种隐性伤害转嫁给儿童。

【三、 跨界共鸣与灵魂触及】
- 深度剖析作品是否透过孩子纯粹的人性、心理、语言、思考和行为，成功击穿了年龄壁垒。
- 评估文本是否具有“双重阅读价值”：在吸引孩子的同时，是否能引起成人读者的强烈共鸣，像镜子一样触及并反思成人的心灵世界。

【四、 读者心理与生理同频】
- 分析文本的叙事节奏、审美和情感深度，是否与目标年龄段儿童的“真实心理发展阶段”和“身体发育特征”深度契合。

【五、 NAL 首席修改建议】
- 针对上述暴露出的短板，给出具体、犀利、可落地的文学修辞、视角转换或情节重构建议。"""

                    model = genai.GenerativeModel(model_name=MODEL_EVAL, system_instruction=eval_sys_inst)
                    eval_prompt = f"作品内容：\n{current_text}\n\n【人工干预指令/评委备注】：\n{eval_intervention if eval_intervention else '无'}"
                    
                    res = model.generate_content(eval_prompt, generation_config=genai.types.GenerationConfig(temperature=0.1))
                    
                    st.session_state['e_report'] = res.text
                    st.session_state["last_eval_time"] = time.time()
                    st.session_state["last_eval_text"] = current_text
                    st.session_state["e_date"] = time.strftime('%Y-%m-%d %H:%M:%S')
                    
                    clean_filename = up.name.rsplit('.', 1)[0] if '.' in up.name else up.name
                    st.session_state["e_work_title"] = clean_filename
                    
                    score = 0
                    clean_res_text = res.text.replace('*', '') 
                    match = re.search(r"综合评分[\]】]?\s*[:：]\s*\[?(\d{1,3})\]?", clean_res_text)
                    if match:
                        score = int(match.group(1))
                    else:
                        fallback_match = re.search(r"\b(\d{1,3})\b", clean_res_text)
                        if fallback_match:
                            score = int(fallback_match.group(1))
                            
                    st.session_state['e_score'] = score
                    
                    found = False
                    for item in st.session_state['leaderboard']:
                        if item["作品"] == up.name:
                            found = True
                            if score > item["分数"]:
                                item["分数"] = score; item["日期"] = st.session_state["e_date"]
                            break
                    if not found:
                        st.session_state['leaderboard'].append({"作品": up.name, "分数": score, "日期": st.session_state["e_date"]})
                    st.rerun() 
                except Exception as e: 
                    if "finish_reason is 1" in str(e) or "valid Part" in str(e):
                        st.warning("⚠️ 评审引擎本次提取遇阻，请尝试在文本末尾加个回车或简单修改后重新提交！")
                    else:
                        st.error(f"评审异常: {e}")

    if st.session_state.get('e_report'):
        work_name = st.session_state.get('e_work_title', '未知作品')
        
        col_res1, col_res2 = st.columns([1, 3])
        with col_res1:
            st.metric("NAL 综合评分", f"{st.session_state['e_score']} / 100")
        with col_res2:
            st.caption(f"📅 报告生成时间：{st.session_state['e_date']}")
            st.caption(f"📁 评审作品：{work_name}")
        
        raw_report = st.session_state['e_report']
        if "【一、" in raw_report:
            display_report = "【一、" + raw_report.split("【一、", 1)[1]
        else:
            display_report = re.sub(r"[*#\s]*【?综合评分】?[:：\s]*\[?\d{1,3}\]?(?:分)?\n*", "", raw_report, count=1).strip()
            
        st.write(display_report)
        
        rd = Document()
        rd.add_heading(f'NAL 评审报告 - {work_name}', 0)
        rd.add_paragraph(f"生成日期：{st.session_state['e_date']}")
        rd.add_paragraph(f"综合评分：{st.session_state['e_score']} / 100")
        rd.add_paragraph("-" * 50)
        
        safe_report = clean_text(display_report)
        rd.add_paragraph(safe_report)
        rbio = io.BytesIO(); rd.save(rbio)
        
        st.download_button("📥 导出评审报告 (.docx)", rbio.getvalue(), f"NAL_Report_{work_name}.docx") 

# --- Tab 3: 排行榜 ---
with tab3:
    st.header("🏆 NAL 评审作品排行榜")
    if st.session_state['leaderboard']:
        lb = sorted(st.session_state['leaderboard'], key=lambda x: x['分数'], reverse=True)
        st.table(lb)
