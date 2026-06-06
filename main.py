"""
Streamlit 界面：西班牙语跨境电商客服
"""
import os
import streamlit as st

# 尝试导入 Agent
try:
    from agent import CustomerServiceAgent
except Exception as e:
    st.error(f"Error al importar el agente: {e}")
    st.stop()


# 页面配置
st.set_page_config(
    page_title="AutoService - Atención al Cliente",
    page_icon="🌐",
    layout="centered",
    initial_sidebar_state="expanded"
)


# CSS 样式：聊天气泡
st.markdown("""
<style>
/* 用户消息样式 */
[data-testid="stChatMessage"][data-testid="user"] {
    background-color: #DCF8C6;
    border-radius: 15px;
    padding: 10px 15px;
    margin: 5px 0;
}

/* 客服消息样式 */
[data-testid="stChatMessage"][data-testid="assistant"] {
    background-color: #F1F0F0;
    border-radius: 15px;
    padding: 10px 15px;
    margin: 5px 0;
}

/* 用户消息右对齐 */
[data-testid="stChatMessage"][data-testid="user"] [data-testid="stMarkdownContainer"] {
    text-align: right;
}

/* 按钮样式 */
.quick-btn button {
    width: 100%;
    border-radius: 10px;
}
</style>
""", unsafe_allow_html=True)


# 侧边栏：客户信息
with st.sidebar:
    st.title("🌐 AutoService")
    
    # 客户当前信息
    st.subheader("👤 Cliente Actual")
    order_number = st.text_input(
        "Número de Pedido",
        value="ESP12345",
        placeholder="Ej: ESP12345"
    )
    
    # 订单号格式验证
    if order_number.strip():
        if order_number.upper().startswith("ESP"):
            st.success("✅ Formato válido")
        else:
            st.warning("⚠️ Formato inválido. El número de pedido debe comenzar con 'ESP'.")
    
    st.markdown("---")
    
    # 工具列表
    st.subheader("🛠️ Herramientas")
    st.markdown("""
    - 📦 Consultar estado de pedido
    - 📝 Modificar dirección de entrega
    - 📋 Consultar políticas de la tienda
    """)


# 主界面标题
st.title("🌐 AutoService - Atención al Cliente")
st.subheader("Comercio Electrónico Internacional")


# 检查 API Key
if not os.getenv("DEEPSEEK_API_KEY"):
    st.error("""
    ⚠️ Variable de entorno `DEEPSEEK_API_KEY` no configurada.
    
    **Cómo configurar:**
    1. Obtén tu API Key de DeepSeek
    2. Establece la variable de entorno:
       - Windows: `set DEEPSEEK_API_KEY=tu-api-key`
       - Linux/Mac: `export DEEPSEEK_API_KEY=tu-api-key`
    3. Reinicia la aplicación Streamlit
    """)
    st.stop()


# 缓存 Agent 实例（只加载一次）
@st.cache_resource
def get_agent():
    try:
        return CustomerServiceAgent()
    except Exception as e:
        st.error(f"Error al inicializar el agente: {e}")
        return None


agent = get_agent()

if not agent:
    st.stop()


# 获取 session_id
# 默认使用 "default_user"，也可以从 st.query_params 获取（未来扩展）
session_id = "default_user"
try:
    if "session_id" in st.query_params:
        session_id = st.query_params["session_id"]
except:
    pass


# 初始化会话状态
if "messages" not in st.session_state:
    # 首先尝试从数据库加载历史
    try:
        history = agent.load_history(session_id)
        if history:
            st.session_state.messages = history
        else:
            # 没有历史，添加默认欢迎消息
            st.session_state.messages = [
                {
                    "role": "assistant",
                    "content": "¡Hola! Soy tu asistente de AutoService. Puedo ayudarte con tu pedido, modificar direcciones y responder tus dudas sobre nuestras políticas. ¿En qué puedo ayudarte hoy? 😊"
                }
            ]
    except Exception as e:
        # 加载失败时使用默认欢迎消息
        st.session_state.messages = [
            {
                "role": "assistant",
                "content": "¡Hola! Soy tu asistente de AutoService. Puedo ayudarte con tu pedido, modificar direcciones y responder tus dudas sobre nuestras políticas. ¿En qué puedo ayudarte hoy? 😊"
            }
        ]

# 快捷问题按钮点击状态
if "quick_question" not in st.session_state:
    st.session_state.quick_question = None


# 快捷问题按钮
st.markdown("### 💡 Preguntas Frecuentes")
col1, col2, col3 = st.columns(3)

with col1:
    if st.button("📦 ¿Dónde está mi pedido?", use_container_width=True):
        st.session_state.quick_question = "¿Dónde está mi pedido?"

with col2:
    if st.button("📝 Cambiar dirección", use_container_width=True):
        st.session_state.quick_question = "Quiero cambiar mi dirección de entrega"

with col3:
    if st.button("📋 Política devoluciones", use_container_width=True):
        st.session_state.quick_question = "¿Cuál es la política de devoluciones?"

st.markdown("---")


# 显示所有历史消息
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])


# 输入框上方的提示文字
st.caption("Operaciones como modificar dirección o cancelar pedido requieren confirmación.")


# 处理快捷问题
if st.session_state.quick_question:
    user_input = st.session_state.quick_question
    st.session_state.quick_question = None  # 重置
    
    # 添加用户消息
    st.session_state.messages.append({
        "role": "user",
        "content": user_input
    })
    
    # 显示用户消息
    with st.chat_message("user"):
        st.markdown(user_input)
    
    # 调用 Agent 获取回复
    with st.chat_message("assistant"):
        with st.spinner("Pensando..."):
            try:
                reply = agent.chat(user_input, session_id)
                st.markdown(reply)
                
                # 添加回复到历史（Agent 已经保存到数据库，但这里也要更新 session_state）
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": reply
                })
                
            except Exception as e:
                error_msg = f"Lo siento, ha ocurrido un error: {str(e)}"
                st.error(error_msg)
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": error_msg
                })
    
    # 刷新界面
    st.rerun()


# 底部输入框
if user_input := st.chat_input("Escribe tu pregunta en español..."):
    # 添加用户消息
    st.session_state.messages.append({
        "role": "user",
        "content": user_input
    })
    
    # 显示用户消息
    with st.chat_message("user"):
        st.markdown(user_input)
    
    # 调用 Agent 获取回复
    with st.chat_message("assistant"):
        with st.spinner("Pensando..."):
            try:
                reply = agent.chat(user_input, session_id)
                st.markdown(reply)
                
                # 添加回复到历史（Agent 已经保存到数据库，但这里也要更新 session_state）
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": reply
                })
                
            except Exception as e:
                error_msg = f"Lo siento, ha ocurrido un error: {str(e)}"
                st.error(error_msg)
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": error_msg
                })
    
    # 刷新界面
    st.rerun()


# 底部状态栏
st.markdown("---")
st.caption("Powered by DeepSeek + RAG | AutoService 2026")
