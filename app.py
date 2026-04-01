import streamlit as st
import google.generativeai as genai
from docx import Document
import io
import os
import time
import re
from supabase import create_client, Client

# --- 🌟 1. 强力文本清洗器 ---
def clean_text(text):
    if not isinstance(text, str): return ""
    return re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', text)

st.set_page_config(page_title="NAL 数字化文学平台", layout="wide", page_icon="📚")

# --- 🌟 2. Session State 初始化 ---
init_keys = {
    "user": None, "access_granted": False, "is_vip": False, 
    "e_report": None, "e_score": 0, "e_date": "", "e_work_title": "",
    "c_guide": None, "leaderboard": [], "last_eval_time": 0.0,
    "last_creative_prompt": "", "last_eval_text": ""
}
for key, value in init_keys.items():
    if key not in st.session_state:
        st.session_state[key] = value

# --- 🔒 3. 环境变量与 API 配置 ---
try:
    api_key = os.getenv("GEMINI_API_KEY")
    if api_key:
        genai.configure(api_key=api_key)
    else:
        st.error("❌ 错误：未检测到 GEMINI_API_KEY。请在 Render 环境中配置。")
        st.stop()
except Exception as e:
    st.error(f"无法配置 Gemini API: {e}")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- 🗄️ 4. 新增：自动归档核心逻辑 ---
def save_to_nal_archive(archive_type, title, content, score=0):
    """
    NAL 档案室核心归档函数 (V16.9 深度调试版)
    解决 42501 权限错误与 st.rerun() 冲突问题
    """
    # 1. 权限预检：必须在 SaaS 模式登录下才能归档
    if st.session_state.get('user'):
        current_uid = st.session_state['user'].id
        with st.spinner(f"📡 正在将《{title}》存入云端档案库..."):
            try:
                # 2. 构造数据负载
                payload = {
                    "user_id": current_uid,
                    "archive_type": archive_type,
                    "work_title": title,
                    "content": content,
                    "score": score
                }
                
                # 3. 执行插入并等待响应
                # 注意：这里不使用 .execute() 后的异步处理，确保同步阻塞
                response = supabase.table("nal_archives").insert(payload).execute()
                
                # 4. 结果判定
                if response.data:
                    st.toast(f"✅ 归档成功：{title}")
                    # 关键：物理停顿 0.8 秒，确保数据库 I/O 彻底完成再允许外部调用 st.rerun()
                    time.sleep(0.8) 
                    return True
                else:
                    st.sidebar.error("⚠️ 数据库响应为空，请检查表结构。")
                    return False

            except Exception as e:
                # 5. 错误捕获：将 42501 等错误强制停留在屏幕上
                st.error(f"🚨 NAL 档案系统写入崩溃！")
                st.code(f"错误详情: {e}") # 使用 code 块方便您复制报错内容
                
                st.info("""
                💡 **排查指南：**
                1. **RLS 策略**：确保已在 Supabase 运行了 `FOR ALL TO authenticated` 的 Debug SQL。
                2. **环境变量**：检查 Render 中的 `SUPABASE_KEY` 是否带了引号或空格。
                3. **字段类型**：确认数据库中 `user_id` 列的类型是 `uuid` 而非 `text`。
                """)
                
                # 强制停止脚本执行，防止被 st.rerun() 刷掉错误信息
                st.stop() 
    else:
        st.sidebar.warning("⚠️ 未检测到登录状态，本次生成未归档。")
        return False

MODEL_CREATIVE = "gemini-2.5-flash"
MODEL_EVAL = "gemini-3.1-pro-preview"

# --- 🌟 5. 路由逻辑与支付墙拦截 ---
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
            st.markdown(f"欢迎您，**{st.session_state['user'].email}**！您目前使用的是未激活账户。")
            c_pay1, c_pay2, c_pay3 = st.columns([1, 2, 1])
            with c_pay2:
                st.info("💎 **NAL Pro 创作者订阅**\n\n- 开启无限次创作推演\n- 启动极其严苛的 3.1 Pro 评审")
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
            VALID_CODES = [code.strip() for code in env_codes.split(",")] if env_codes else ["NAL2026"]
            if inv in VALID_CODES: 
                st.session_state["access_granted"] = True
                st.rerun()
            else: st.error("邀请码无效。")
        st.stop()

# --- 🌟 6. 主功能界面 ---
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
    st.sidebar.text(f"首席评委：NAL")

st.title("NAL 数字化文学双擎系统")
tab1, tab2, tab3, tab4 = st.tabs(["💡 创作伴侣", "⚖️ 深度评审", "🏆 评审排行榜", "📁 我的档案室"])

# --- Tab 1: 创作功能 (完整 Prompt 还原) ---
with tab1:
    st.header("💡 NAL智能创作指导系统")
    u_prompt = st.text_area("输入您的灵感片段：", placeholder="输入主题、核心冲突或想要探讨的时代命题...", height=150)
    c_filename = st.text_input("📄 设定片段导出文件名", value="NAL_Highlights", help="无需输入 .docx 后缀")

    if st.button("启动 NAL 创作推演", disabled=not u_prompt or u_prompt == st.session_state["last_creative_prompt"]): 
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
【人物弧光设定】
【情节大纲建议】
===片段分割线===
【高光片段试写】
（在此处，你必须实打实地撰写一段 500-800 字的纯粹文学选段！必须包含极强的画面感和情绪张力，绝不能偷懒或只写短句！）"""

                model = genai.GenerativeModel(model_name=MODEL_CREATIVE, system_instruction=creative_sys_inst)
                res = model.generate_content(u_prompt, generation_config=genai.types.GenerationConfig(temperature=0.7))
                
                if res.text:
                    st.session_state['c_guide'] = res.text
                    # 先同步，同步成功后再执行后续逻辑
                    if save_to_nal_archive("creative", c_filename, res.text):
                        st.rerun()
                    st.session_state["last_creative_prompt"] = u_prompt
                    # 🌟 调试改动：使用阻塞式归档
                    with st.status("🚀 正在同步至 NAL 云端档案室...", expanded=True) as status:
                        try:
                            # 调用归档函数
                            save_to_nal_archive("creative", c_filename, res.text)
                            status.update(label="✅ 归档已完成！", state="complete", expanded=False)
                            time.sleep(1) # 给数据库 1 秒缓冲时间
                            st.rerun() 
                        except Exception as e:
                            status.update(label="❌ 归档发生错误", state="error")
                            st.error(f"具体错误信息: {e}")
                            st.stop() # 强制停止，防止错误信息消失
                   # save_to_nal_archive("creative", c_filename, res.text)
                 #   st.rerun() 
            except Exception as e: st.error(f"引擎异常: {e}")

    if st.session_state.get('c_guide'):
        st.markdown("---")
        st.write(st.session_state['c_guide'])
        
        # 🌟 逐字还原您的切分逻辑
        guide_text = st.session_state['c_guide']
        parts = re.split(r'\**[=\-]{2,}\s*片段分割线\s*[=\-]{2,}\**', guide_text)
        
        if len(parts) > 1:
            outline_content = parts[0].strip()
            snippet_content = parts[1].strip()
        else:
            fallback_parts = re.split(r'【高光片段试写】', guide_text)
            outline_content = fallback_parts[0].strip() if len(fallback_parts) > 1 else guide_text
            snippet_content = fallback_parts[1].strip() if len(fallback_parts) > 1 else "未识别到片段"

        col_d1, col_d2 = st.columns(2)
        with col_d1:
            d1 = Document(); d1.add_heading('NAL 创作大纲', 0); d1.add_paragraph(clean_text(outline_content))
            b1 = io.BytesIO(); d1.save(b1); st.download_button("📥 导出作品大纲 (.docx)", b1.getvalue(), "NAL_Outline.docx")
        with col_d2:
            d2 = Document(); d2.add_heading('NAL 创作高光片段', 0); d2.add_paragraph(clean_text(snippet_content))
            b2 = io.BytesIO(); d2.save(b2); st.download_button(f"📥 导出高光片段 (.docx)", b2.getvalue(), f"{c_filename}.docx")

# --- Tab 2: 评审功能 (完整 Prompt 与人工干预还原) ---
with tab2:
    st.header("⚖️ 深度评审系统")
    curr = time.time(); cd = 15 - (curr - st.session_state["last_eval_time"])
    up = st.file_uploader("上传作品文本 (.docx)", type=["docx"])
    
    st.markdown("##### 📝 人工干预与评审备注")
    eval_intervention = st.text_area("在此输入您对本次评审的特殊要求或想对作者说的话（可选）：",  placeholder="例如：请特别关注文中对祖孙关系的描写，或在此加入评委的人工寄语...", height=100)
    
    current_text = ""
    if up:
        try:
            up.seek(0); word = Document(up); current_text = "\n".join([p.text for p in word.paragraphs])
        except Exception: st.error("无法读取此文档。。")
            
    if st.button("启动 智能 评审", disabled=not up or (current_text != "" and current_text == st.session_state["last_eval_text"])): 
        if cd > 0: st.warning(f"冷却中: {int(cd)}s")
        elif current_text:
            with st.spinner("NAL 首席评审专家正在整合人工指令进行严苛审查..."):
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
                    st.session_state["e_work_title"] = up.name.rsplit('.', 1)[0]
                    
                    # 分数提取
                    score = 0; clean_res = res.text.replace('*', '')
                    match = re.search(r"综合评分[\]】]?\s*[:：]\s*\[?(\d{1,3})\]?", clean_res)
                    if match: score = int(match.group(1))
                    st.session_state['e_score'] = score
                    # 🌟 关键：同步成功后再刷新
                    if save_to_nal_archive("evaluation", up.name, res.text, score):
                        st.rerun()
                    st.session_state['leaderboard'].append({"作品": up.name, "分数": score, "日期": st.session_state["e_date"]})
                  
                    st.rerun() 
                except Exception as e: st.error(f"异常: {e}")

    if st.session_state.get('e_report'):
        work_name = st.session_state.get('e_work_title', '未知')
        col_res1, col_res2 = st.columns([1, 3])
        with col_res1: st.metric("NAL 综合评分", f"{st.session_state['e_score']} / 100")
        with col_res2: st.caption(f"📅 时间：{st.session_state['e_date']} | 📁 作品：{work_name}")
        
        raw_report = st.session_state['e_report']
        display_report = "【一、" + raw_report.split("【一、", 1)[1] if "【一、" in raw_report else raw_report
        st.write(display_report)
        
        rd = Document(); rd.add_heading(f'NAL 评审报告 - {work_name}', 0)
        rd.add_paragraph(clean_text(display_report))
        rbio = io.BytesIO(); rd.save(rbio)
        st.download_button("📥 导出评审报告 (.docx)", rbio.getvalue(), f"Report_{work_name}.docx") 

# --- Tab 3: 排行榜 ---
with tab3:
    st.header("🏆 NAL 评审作品排行榜")
    if st.session_state['leaderboard']:
        st.table(sorted(st.session_state['leaderboard'], key=lambda x: x['分数'], reverse=True))

# --- Tab 4: 我的档案室 ---
with tab4:
    st.header("📁 NAL 云端档案库")
    if st.session_state['user']:
        try:
            res_db = supabase.table("nal_archives").select("*").order("created_at", desc=True).execute()
            if res_db.data:
                for arc in res_db.data:
                    with st.expander(f"【{arc['archive_type']}】{arc['work_title']} - {arc['created_at'][:10]}"):
                        st.write(arc['content'])
                        doc = Document(); doc.add_paragraph(clean_text(arc['content']))
                        bio = io.BytesIO(); doc.save(bio)
                        st.download_button("📥 重新导出 Docx", bio.getvalue(), f"Arc_{arc['id'][:4]}.docx", key=arc['id'])
            else: st.info("暂无历史档案。")
        except Exception: pass
    else: st.warning("请登录 SaaS 模式以查看云端档案。")
