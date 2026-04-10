import streamlit as st
import google.generativeai as genai
from docx import Document
import io
import os
import time
import re
from supabase import create_client, Client

# --- 模型配置区 (锁定版) ---
# 评审：使用最强的逻辑引擎，确保学术严谨度
#MODEL_EVAL = "gemini-2.5-flash" 
MODEL_EVAL = "gemini-3.1-pro-preview" 

# 预读与创作：使用响应极快的 2.5 版本
MODEL_ADAPTIVE = "models/gemini-2.5-flash"
MODEL_CREATIVE = "gemini-2.5-flash"

st.error("🚀 当前代码版本：测试同步专用")
# --- 顶部标题区 ---
st.set_page_config(
    page_title="NAL | 新艺文社数字化平台", 
    page_icon="nal_logo.jpg",  # 这里会让浏览器标签页也显示爷爷头像
    layout="wide"
    ) 
#page_icon="📚"  原page icon

with st.sidebar:
    # 使用 use_container_width 让图片填满侧边栏宽度
    st.image("nal_logo.jpg", use_container_width=True)
    
    # 或者手动指定像素宽度
    # st.image("nal_logo.jpg", width=200)
    
    st.markdown("<p style='text-align: center; color: gray;'>NAL 创作引擎</p>", unsafe_allow_html=True)
    st.divider()

# 品牌双行标题 (修正了参数拼写)
st.markdown("""
    <h1 style='text-align: center; margin-bottom: 0;'>NewArtLiterature Collective (NAL)</h1>
    <h3 style='text-align: center; margin-top: 0; color: #555;'>新艺文社数字化文学平台</h3>
    """, unsafe_allow_html=True) # <-- 这里已经改为 html

st.divider() # 添加一条分割线，让视觉更整洁

# --- 🌟 1. 强力文本清洗器 ---
def clean_text(text):
    if not isinstance(text, str): return ""
    # 扩展过滤范围，确保 XML 兼容性
    return "".join(c for c in text if c.isprintable() or c in "\n\r\t")
    
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
    NAL 档案室核心归档函数 (V17.0 稳定版)
    功能：将 AI 生成内容同步至 Supabase 云端数据库
    """
    # 1. 权限预检：仅在 SaaS 模式登录状态下执行归档
    if st.session_state.get('user'):
        u_id = st.session_state['user'].id
        
        # 使用 spinner 提供加载反馈，避免用户在写入时重复点击
        with st.spinner(f"💾 正在同步《{title}》至云端档案室..."):
            try:
                # 2. 构造数据负载 (user_id 必须与数据库中的 uuid 类型对应)
                payload = {
                    "user_id": u_id,
                    "archive_type": archive_type,
                    "work_title": title,
                    "content": content,
                    "score": score
                }
                
                # 3. 执行插入操作
                response = supabase.table("nal_archives").insert(payload).execute()
                
                # 4. 结果验证与缓冲
                if response.data:
                    st.toast(f"✅ 存档成功：{title}", icon="📁")
                    # 关键：留出 1 秒物理缓冲时间，防止后续的 st.rerun() 强行切断未完成的网络连接
                    import time
                    time.sleep(1.0) 
                    return True
                return False

            except Exception as e:
                # 仅在发生崩溃时显示错误，方便运维排查
                st.error(f"🚨 档案系统同步失败: {e}")
                return False
    
    # 未登录状态静默跳过（或根据需要添加提示）
    return False
    
# --- 从数据库获取评审模型配置 ---
def get_eval_model_from_db(model_name):
    """
    从 Supabase 获取完整的评审模型配置
    """
    try:
        response = supabase.table("evaluation_models") \
            .select("system_instruction, parameters, description") \
            .eq("name", model_name) \
            .single() \
            .execute()
        return response.data
    except Exception as e:
        st.error(f"无法调取数据库模型 '{model_name}': {e}")
        return None

# --- 自适应权重逻辑 ---
def get_adaptive_instruction(model_data, current_text, user_note=""):
    """
    NAL 自适应引擎：修正了变量定义顺序与模型路径一致性
    """
    # 1. 优先获取基础参数，防止后续引用报错
    base_params = model_data.get('parameters', {})
    if not base_params:
        return model_data.get('system_instruction', '')
    
    # 2. 预读特征提取：统一使用顶部定义的快熟模型
    sense_prompt = """你是一个文本特征分析器。请严谨分析该儿童文学文本指标(0.0-1.0)：
    1.fantasy(幻想感) 2.reality(现实/时代感) 3.character(人物心理深度)。
    必须仅输出纯 JSON 格式：{"fantasy": 0.5, "reality": 0.5, "character": 0.5}"""

    # 预读特征提取
    try:
        # 直接使用我们在顶部配好的 2.5 Flash
        feature_model = genai.GenerativeModel(MODEL_ADAPTIVE) 
        
        f_res = feature_model.generate_content(
            f"{sense_prompt}\n内容：{current_text[:2000]}",  # 此时它就能正确找到上方的 prompt 了
            generation_config=genai.types.GenerationConfig(
                response_mime_type="application/json",
                temperature=0.1
            )
        )
        import json
        features = json.loads(f_res.text)
    except Exception as e:
        st.write(f"⚠️ 预读引擎自动降级: {e}")
        features = {"fantasy": 0.5, "reality": 0.5, "character": 0.5}
    
    # 3. 语义映射调权逻辑 (不依赖固定名称)
    adjusted_weights = base_params.copy()

    # 降低自适应的敏感度（从30降至15），找回 NAL 模型的硬度
    sensitivity = 15
    
    # --- 语义指纹感应矩阵 (NAL 2026 全维版) ---
    mapping = {
        # 1. 偏向“感性/艺术/想象”轴线的指纹
        "fantasy": [
        "跨界", "共鸣", "幻想", "想象", "诗意", "隐喻", "对位", 
        "意象", "视觉", "分镜", "审美", "张力", "形式", "艺术",
        "留白", "介入", "童话", "超自然", "虚构"
        ],
    
        # 2. 偏向“时代/社会/伦理”轴线的指纹
        "reality": [
        "时代", "社会", "技术", "异化", "现实", "真相", "背景", 
        "偏见", "价值观", "文化", "伦理", "生态", "教育", "批判",
        "成人主义", "意识形态", "显性", "潜意识", "病灶"
        ],
    
        # 3. 偏向“主体/心理/构造”轴线的指纹
        "character": [
        "人物", "心理", "契合", "塑造", "成长", "主体", "非人类", 
        "尊严", "读者", "共生", "视角", "动机", "弧光", "自我",
        "生命本位", "空间", "体验", "共情"
        ]
    }

    for dim in adjusted_weights.keys():
        # A. 根据幻想度调权
        if any(k in dim for k in mapping["fantasy"]):
            adjusted_weights[dim] = max(1, adjusted_weights[dim] + (features.get('fantasy', 0.5) - 0.5) * sensitivity)
        
        # B. 根据现实度调权
        if any(k in dim for k in mapping["reality"]):
            adjusted_weights[dim] = max(1, adjusted_weights[dim] + (features.get('reality', 0.5) - 0.5) * sensitivity)
            
        # C. 根据人物深度调权
        if any(k in dim for k in mapping["character"]):
            adjusted_weights[dim] = max(1, adjusted_weights[dim] + (features.get('character', 0.5) - 0.5) * sensitivity)

    # 4. 人工干预偏置 (最高优先级)
    intervention_log = ""
    if user_note:
        for dim in adjusted_weights.keys():
            # 只要备注里提到了维度的前两个字，就暴力提权
            if dim[:2] in user_note:
                adjusted_weights[dim] += 25
                intervention_log += f"【已根据备注强化‘{dim}’】 "

    # 5. 归一化
    total = sum(adjusted_weights.values())
    final_weights = {k: round((v/total)*100, 1) for k, v in adjusted_weights.items()}
    
    # 6. 合成
    weight_desc = "\n".join([f"- {k}: {v}%" for k, v in final_weights.items()])
    return f"""{model_data['system_instruction']}

---
【NAL 通用自适应校准报告】
文本指纹：幻想({features.get('fantasy')})，现实({features.get('reality')})，人物({features.get('character')})
{intervention_log}
动态权重矩阵：
{weight_desc}
---
请按此分配执行评审。"""

# UI 下拉菜单的顺序（NAL 永远在第一个）
MODEL_OPTIONS = [
    "全景综合-通用基准模型",     # 👈 默认安全牌，融合各家之长
    "NAL-首席专家锐评模型",
    "李利芳-儿童文学生命本位模型",
    "朱自强-本质论评审模型",
    "视觉叙事-图文对位模型",
    "霍林代尔-意识形态批判模型",
    "后人类/生态主义先锋模型"
]

# 极简的数据库抓取（只管转换格式，不管排序）
@st.cache_data(ttl=3600)
def fetch_nal_models_from_db():
    res = supabase.table("evaluation_models").select("name, parameters, description").execute()
    # 用一行字典推导式直接搞定数据重组
    matrix = {row["name"]: row["parameters"] for row in res.data}
    descriptions = {row["name"]: row.get("description", "暂无简介") for row in res.data}
    return matrix, descriptions

EVAL_SYSTEM_MATRIX, MODEL_DESCRIPTIONS = fetch_nal_models_from_db()

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
            st.markdown(f"欢迎您，**{st.session_state['user'].email}**！您目前使用的是未激活账户，请订阅以获取 AI 引擎的完整算力支持。")
            c_pay1, c_pay2, c_pay3 = st.columns([1, 2, 1])
            with c_pay2:
                st.info("💎 **NAL Pro 创作者订阅**\n\n- 开启无限次创作推演\n- 启动极其严苛的 智能专家 评审")
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

with tab1:
    st.header("💡 NAL/学术体系 智能创作指导系统")
    
    # 1. 体系选择
    # 1. 体系选择 (动态读取)
    mentor_options = list(MODEL_DESCRIPTIONS.keys())
    mentor_type = st.selectbox("💡 请选择您的创作指导导师体系：", MODEL_OPTIONS, key="mentor_select")
    # 动态展示导师风格
    st.info(f"**导师风格**：{MODEL_DESCRIPTIONS.get(mentor_type, '')}")
            
    u_prompt = st.text_area("输入您的灵感片段：", placeholder="输入主题、核心冲突或想要探讨的时代命题...", height=150, key="u_input_2026")
    c_filename = st.text_input("📄 设定片段导出文件名", value="NAL_Highlights", key="f_input_2026")

    # 初始化状态
    if "c_guide" not in st.session_state: st.session_state['c_guide'] = ""
    if "last_creative_prompt" not in st.session_state: st.session_state["last_creative_prompt"] = ""

    # 2. 创作触发
    btn_disabled = not u_prompt or u_prompt == st.session_state["last_creative_prompt"]
    if st.button("启动 创作推演", disabled=btn_disabled, key="run_creative_2026"): 
        with st.spinner(f"正在调动【{mentor_type}】进行深度构思与 800 字试写..."):
            try:
                # 🚀 动态提取当前选中模型的“灵魂”和“维度”
                mentor_desc = MODEL_DESCRIPTIONS[mentor_type]
                focus_dimensions = "、".join(EVAL_SYSTEM_MATRIX.get(mentor_type, {}).keys())
                
                # 动态注入标准，彻底告别硬编码
                expert_standard = f"""
                【核心指导思想】：{mentor_desc}
                【重点发力维度】：你的大纲和试写必须极力展现以下学术特质：{focus_dimensions}。
                """

                creative_sys_inst = f"""你现在是儿童文学领域的金牌创作指导。
                任务：协助作者构思并实打实撰写长片段。
                标准：{expert_standard}

                【输出格式要求】
                1. 前半部分：包含【核心立意升华】、【人物弧光设定】、【情节大纲建议】。
                2. 中间必须插入一行：===片段分割线===
                3. 后半部分：【高光片段试写】。

                注意：试写片段必须达到 600-800 字，要求极强的画面感和文学性，绝不准敷衍！"""
                # 使用当前最稳健的 ID
                model = genai.GenerativeModel(model_name=MODEL_CREATIVE, system_instruction=creative_sys_inst)
                
                # 🚀 核心修复：调高 Tokens 至 8192，确保长文本不被截断
                res = model.generate_content(
                    u_prompt, 
                    generation_config=genai.types.GenerationConfig(
                        temperature=0.7,
                        max_output_tokens=8192,
                        top_p=0.95
                    )
                )
                
                if res.text:
                    st.session_state['c_guide'] = res.text
                    st.session_state["last_creative_prompt"] = u_prompt
                    save_to_nal_archive("creative", c_filename, res.text)
                    st.rerun()

            except Exception as e:
                st.error(f"❌ 创作引擎异常: {e}")

    # 3. 增强型分块展示与下载逻辑
    if st.session_state.get('c_guide'):
        guide_text = st.session_state.get('c_guide')
        
        # --- 🚀 多级兜底切分算法 ---
        outline_content = ""
        snippet_content = ""
        
        # 第一级：硬分割线匹配
        if "===片段分割线===" in guide_text:
            parts = guide_text.split("===片段分割线===")
            outline_content = parts[0].strip()
            snippet_content = parts[1].strip() if len(parts) > 1 else ""
        
        # 第二级：如果一级失败，按标题关键字切分
        if not snippet_content or len(snippet_content) < 50:
            fallback_parts = re.split(r'【高光片段试写】', guide_text)
            if len(fallback_parts) > 1:
                outline_content = fallback_parts[0].strip()
                snippet_content = "【高光片段试写】\n" + fallback_parts[1].strip()
        
        # 第三级：全挂了，直接显示全部
        if not outline_content:
            outline_content = guide_text
            snippet_content = "（系统未能自动切分片段，请在上方完整内容中查看）"

        st.divider()
        
        # 分栏显示：左侧大纲，右侧片段
        col_show1, col_show2 = st.columns([2, 3])
        with col_show1:
            st.markdown("#### 📌 创作策划大纲")
            st.info(outline_content)
            
            d1 = Document(); d1.add_heading('NAL 创作大纲', 0); d1.add_paragraph(clean_text(outline_content))
            b1 = io.BytesIO(); d1.save(b1)
            st.download_button("📥 导出大纲 (.docx)", b1.getvalue(), f"Outline_{c_filename}.docx", key="dl_o_2026")

        with col_show2:
            st.markdown("#### 📖 高光片段试写")
            st.success(snippet_content)
            
            d2 = Document(); d2.add_heading('NAL 高光片段', 0); d2.add_paragraph(clean_text(snippet_content))
            b2 = io.BytesIO(); d2.save(b2)
            st.download_button("📥 导出片段 (.docx)", b2.getvalue(), f"{c_filename}.docx", key="dl_s_2026")
        
# --- Tab 2: 深度评审系统 (自适应架构 2026 版) ---
with tab2:
    st.header("⚖️ 深度评审系统")
    
    # 1. 状态管理与冷却
    curr_t = time.time()
    last_model = st.session_state.get("last_eval_model", "")
    cd_time = 15 - (curr_t - st.session_state.get("last_eval_time", 0))
    
    # 模型选择 (需确保与数据库 name 字段一字不差)
    selected_model = st.selectbox("⚖️ 请选择评审学术体系：", MODEL_OPTIONS, key="eval_select")
    # 动态展示对应模型的“学术灵魂”
    st.info(f"**学术底色**：{MODEL_DESCRIPTIONS.get(selected_model, '暂无描述')}")
    
    # 获取该模型对应的基础权重 (传给自适应引擎使用)
    base_weights = EVAL_SYSTEM_MATRIX.get(selected_model, {})
    
    # 2. 输入区
    up_file = st.file_uploader("上传作品文本 (.docx)", type=["docx"], key="eval_uploader")
    st.markdown("##### 📝 人工干预与评审备注")
    eval_note = st.text_area(
        "在此输入评委备注（系统将根据语义自动调整权重）：", 
        placeholder="例如：请重点关注‘时代性’，考察技术对童年的异化...", 
        height=100
    )
    
    raw_text = ""
    if up_file:
        try:
            up_file.seek(0)
            doc = Document(up_file)
            raw_text = "\n".join([p.text for p in doc.paragraphs])
        except Exception as e: 
            st.error(f"文件读取失败: {e}")

    # 3. 评审触发逻辑 (允许：模型变更 OR 文本变更)
    text_is_new = raw_text != st.session_state.get("last_eval_text", "")
    model_is_new = selected_model != last_model
    can_proceed = up_file is not None and (text_is_new or model_is_new)
    
    if st.button("启动 智能 评审", disabled=not can_proceed):
        if cd_time > 0:
            st.warning(f"系统冷却中: {int(cd_time)}秒，请稍后再试。")
        elif raw_text:
            with st.spinner(f"正在调取【{selected_model}】并启动自适应引擎..."):
                try:
                    # 从数据库获取模型基准
                    m_data = get_eval_model_from_db(selected_model)
                    if m_data:
                        # --- 🚨 核心指令拼装区 (已应用防呆与强制填分策略) ---
                        
                        # 动态生成高分示范模板，彻底打破 AI 的“填空题瘫痪”
                        example_dims = ""
                        for k, v in base_weights.items():
                            example_score = int(v * 0.8) # 模拟 80% 的得分示范
                            example_dims += f"* **{k}**：{example_score}/{v}分 - 这里的描写非常生动，完美契合了该维度的要求...\n"

                        # 全新的 Tab 2 评审核心 Prompt
                        eval_sys_inst = f"""你现在是 NAL 数字化平台的顶级学术评审专家。你的评审风格以【犀利、冷峻、见血】著称。
                        当前执行的评审体系：【{selected_model}】
                        这四个维度的【最高满分】分别是：{base_weights}

                        【核心任务】
                        你必须像一位严苛但真实的评委，阅读用户的作品，进行心算，并输出真实的个位数字分数！
                        绝不允许抄写模板占位符，绝不允许全部打0分！

                        【第一阶段：前置硬伤排查】
                        1. 逻辑与事实核查：检查故事逻辑漏洞与科学/历史事实准确性。
                        2. 原创性评估：审视是否落入常见套路。

                        【评审准则：严禁平庸】
                        1. 你的默认立场是“寻找瑕疵”，而非“寻找美感”。对于平庸但无硬伤的作品，综合评分基准定在 60-65 分。
                        2. 对于落入俗套的情节、说教式的口吻、成人主义的傲慢，对应维度的分数必须直接削减 50%。
                        3. 原创性是核心门槛。若概念陈旧，即使文笔优美，总分也绝对不得超过 70 分。
                        4. 综合学术评分中，85分以上代表“具备传世潜力”，绝不轻易给出。

                        【强制输出规范】
                        请直接输出你的最终评审报告，严格使用下方的排版格式。
                        （👇 注意：下方只是一个格式范例，请将分数和评语替换为你对本文的【真实评估结果】！）

                        ### 📊 综合学术评分：85/100

                        ### 💡 逻辑与原创性审查
                        * **事实与逻辑排查**：逻辑严密，无明显硬伤。（或者指出具体漏洞）
                        * **原创性评估**：8/10分。设定新颖，视角独特。

                        ### 🧮 维度解析与单项得分
                        （注意：这四项的实际得分相加，必须等于上方的综合评分！）
                        {example_dims}
                        
                        ### 📝 核心修改建议
                        1. 建议在结尾处增加...
                        2. 建议削弱某些冗余的对话...
                        """

                        # 🚀 执行自适应算法 (获取动态权重的指令)
                        final_inst = get_adaptive_instruction(m_data, raw_text, eval_note)
                        
                        # 🚨 关键修复：将自适应指令与强约束模板合并
                        combined_system_instruction = final_inst + "\n\n" + eval_sys_inst
                        
                        # 调用大模型 (使用合并后的系统指令)
                        eval_model = genai.GenerativeModel(
                            model_name=MODEL_EVAL, 
                            system_instruction=combined_system_instruction
                        )
                        
                        # 组装用户输入
                        prompt = f"【需要评审的作品内容】：\n{raw_text}\n\n【评委备注】：{eval_note if eval_note else '无'}\n\n请严格照着 System Instruction 中的范例格式，给我真实的打分数字！"
                        
                        # 🚨 关键修复：temperature 提高到 0.4，释放计算与评价能力
                        res_obj = eval_model.generate_content(
                            prompt, 
                            generation_config=genai.types.GenerationConfig(temperature=0.4)
                        )
                        
                        # --- 数据存储与排行榜持久化 ---
                        st.session_state['e_report'] = res_obj.text
                        st.session_state["last_eval_time"] = time.time()
                        st.session_state["last_eval_text"] = raw_text
                        st.session_state["last_eval_model"] = selected_model
                        st.session_state["e_date"] = time.strftime('%Y-%m-%d %H:%M:%S')
                        st.session_state["e_work_title"] = up_file.name.rsplit('.', 1)[0]
                        
                        # 分数提取正则化 (支持提取 85/100 或 综合学术评分：85 等多种变体)
                        score_val = 0
                        clean_txt = res_obj.text.replace('*', '').replace(' ', '')
                        m_score = re.search(r"(?:综合学术评分|综合评分|总分)[】\]]?[:：]?\[?(\d{1,3})\]?(?:/100|分)?", clean_txt)
                        if m_score: 
                            score_val = int(m_score.group(1))
                        st.session_state['e_score'] = score_val
                        
                        # 更新排行榜 (确保在 rerun 前写入)
                        if "leaderboard" not in st.session_state: 
                            st.session_state["leaderboard"] = []
                        st.session_state['leaderboard'].append({
                            "作品": up_file.name, 
                            "分数": score_val, 
                            "日期": st.session_state["e_date"], 
                            "体系": selected_model
                        })
                        
                        # 异步归档数据库 (假设 save_to_nal_archive 函数已在顶部定义)
                        save_to_nal_archive("evaluation", up_file.name, res_obj.text, score_val)
                        
                        st.rerun()
                    else: 
                        st.error("数据库连接失败或未找到模型数据。")
                except Exception as e: 
                    st.error(f"评审发生异常: {e}")

    # 4. 结果展示区
    if st.session_state.get('e_report'):
        r_title = st.session_state.get("last_eval_model", selected_model)
        r_work = st.session_state.get('e_work_title', '未知')
        
        col_m1, col_m2 = st.columns([1, 3])
        with col_m1:
            st.metric(f"{r_title} 评分", f"{st.session_state.get('e_score', 0)} / 100")
        with col_m2:
            st.caption(f"📅 {st.session_state.get('e_date')} | 📁 {r_work}")
        
        st.divider()
        
        # 提取报告主体：稳健切分，过滤掉可能存在的冗余部分
        full_rpt = st.session_state['e_report']
        display_content = full_rpt.split("---")[-1].strip() if "---" in full_rpt else full_rpt
        
        if len(display_content) < 100: 
            display_content = full_rpt
            
        st.markdown(display_content)
        
        # 导出为 Word 文档
        rd_doc = Document()
        rd_doc.add_heading(f'{r_title} 评审报告', 0)
        rd_doc.add_paragraph(f"作品：{r_work}\n日期：{st.session_state.get('e_date')}\n")
        # 假设 clean_text 是已定义的清洗函数，若未定义请使用 display_content.replace(...) 等进行基本清洗
        try:
            rd_doc.add_paragraph(clean_text(display_content))
        except NameError:
            rd_doc.add_paragraph(display_content) # 如果没有 clean_text 函数的兜底方案
            
        rb = io.BytesIO()
        rd_doc.save(rb)
        
        # 防止因特殊字符导致文件名下载报错
        safe_r_work = re.sub(r'[\\/*?:"<>|]', "", r_work)
        
        st.download_button(
            label=f"📥 下载《{safe_r_work}》评审报告", 
            data=rb.getvalue(), 
            file_name=f"NAL_Report_{safe_r_work}.docx", 
            use_container_width=True
        )
        
# --- Tab 3: 排行榜 ---
with tab3:
    st.header("🏆 NAL 评审作品排行榜")
    if st.session_state['leaderboard']:
        st.table(sorted(st.session_state['leaderboard'], key=lambda x: x['分数'], reverse=True))

# --- Tab 4: 我的档案室 ---
with tab4:
    st.header("📁 NAL 云端档案库")
    
    # 🚀 获取当前用户状态
    user_obj = st.session_state.get('user')
    
    if user_obj:
        try:
            # 获取当前用户档案
            res_db = supabase.table("nal_archives").select("*").eq("user_id", user_obj.id).order("created_at", desc=True).execute()
            
            if res_db.data:
                for arc in res_db.data:
                    # --- 外部布局：标题 + 快捷删除 ---
                    col_main, col_del = st.columns([0.85, 0.15])
                    
                    with col_main:
                        exp = st.expander(f"【{arc['archive_type']}】{arc['work_title']} - {arc['created_at'][:10]}")
                    
                    with col_del:
                        # 🔴 关键：恢复快捷删除按钮，使用 type="primary" 突出显示
                        if st.button("🗑️", key=f"fast_del_{arc['id']}", type="primary", help="永久删除此条记录"):
                            supabase.table("nal_archives").delete().eq("id", arc['id']).execute()
                            st.toast(f"已从云端移除：{arc['work_title']}")
                            time.sleep(0.5)
                            st.rerun()

                    # --- 展开器内部逻辑 ---
                    with exp:
                        st.write(arc['content'])
                        st.divider()
                        
                        col_action, col_danger = st.columns([0.7, 0.3])
                        with col_action:
                            # 导出功能
                            doc = Document()
                            doc.add_paragraph(clean_text(arc['content']))
                            bio = io.BytesIO()
                            doc.save(bio)
                            st.download_button("📥 重新导出 Docx", bio.getvalue(), f"Arc_{arc['id'][:4]}.docx", key=f"dl_{arc['id']}")
                        
                        with col_danger:
                            # 🔴 二次确认删除
                            if st.button("🚨 确认永久删除", key=f"final_del_{arc['id']}", type="primary"):
                                supabase.table("nal_archives").delete().eq("id", arc['id']).execute()
                                st.success("记录已永久移除")
                                time.sleep(0.5)
                                st.rerun()
            else:
                st.info("📂 云端档案室暂无记录。")
        except Exception as e:
            st.error(f"档案加载失败: {e}")
    else:
        # 邀请码模式下的提示
        st.warning("💡 档案库管理权限仅对注册会员开放。当前模式仅支持浏览本次会话历史。")
        if st.session_state.get('leaderboard'):
            st.markdown("### 🕒 本次会话评审历史")
            st.table(st.session_state['leaderboard'])
