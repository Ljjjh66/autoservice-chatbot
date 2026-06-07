"""
西班牙语跨境电商智能客服 Agent（LangGraph 版本）
使用 DeepSeek-V3 + RAG + 工具调用
"""

import re
import json
import os
import sqlite3
from datetime import datetime
from typing import TypedDict, Annotated, Sequence, Optional, Dict, Any
import operator

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import (
    BaseMessage,
    HumanMessage,
    AIMessage,
    ToolMessage,
    SystemMessage,
)

from openai import OpenAI
from openai import APIError, APIConnectionError, RateLimitError

# 从同项目导入模块
from tools import (
    query_order_logistics,
    update_order_address,
    cancel_order,
    request_refund,
    estimate_shipping,
)
from rag import search, build_knowledge_base
from validators import validate_tool_args, format_validation_error_for_llm
from schemas import SCHEMA_REGISTRY


# ============================================================
# 配置常量
# ============================================================

# DeepSeek API 配置
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_MODEL = "deepseek-chat"
API_TIMEOUT = 30

# 敏感操作列表
SENSITIVE_ACTIONS = ["update_order_address", "cancel_order", "request_refund"]

# 工具定义（OpenAI 格式）
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "query_order_logistics",
            "description": "Consulta el estado de logística de un pedido. Necesita el número de pedido (formato: ESPxxxxx). Retorna información sobre el estado actual, transportista y fecha estimada de entrega.",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {
                        "type": "string",
                        "description": "Número de pedido, formato: ESPxxxxx",
                    }
                },
                "required": ["order_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_order_address",
            "description": "Modifica la dirección de entrega de un pedido. Solo funciona para pedidos con estado 'No enviado'. Necesita el número de pedido y la nueva dirección.",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {
                        "type": "string",
                        "description": "Número de pedido, formato: ESPxxxxx",
                    },
                    "new_address": {
                        "type": "string",
                        "description": "Nueva dirección de entrega",
                    },
                },
                "required": ["order_id", "new_address"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search",
            "description": "Busca información en la base de conocimiento sobre políticas de la tienda, preguntas frecuentes, devoluciones, envíos, cambios, etc. Úsalo siempre que el usuario pregunte sobre políticas o reglas.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Consulta del usuario en español",
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "Número de resultados a recuperar (por defecto 2)",
                        "default": 2,
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "cancel_order",
            "description": "Cancelar un pedido que aún no ha sido enviado. Necesita el número de pedido.",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {
                        "type": "string",
                        "description": "Número de pedido, formato: ESPxxxxx",
                    }
                },
                "required": ["order_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "request_refund",
            "description": "Solicitar un reembolso para un pedido entregado. Necesita el número de pedido y la razón (opcional).",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {
                        "type": "string",
                        "description": "Número de pedido, formato: ESPxxxxx",
                    },
                    "reason": {
                        "type": "string",
                        "description": "Razón del reembolso (opcional)",
                        "default": "",
                    },
                },
                "required": ["order_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "estimate_shipping",
            "description": "Estimar el costo de envío internacional. Necesita el país de destino y el peso en kg.",
            "parameters": {
                "type": "object",
                "properties": {
                    "country": {
                        "type": "string",
                        "description": "País de destino (en español o inglés)",
                    },
                    "weight": {
                        "type": "number",
                        "description": "Peso del paquete en kilogramos",
                    },
                },
                "required": ["country", "weight"],
            },
        },
    },
]

# 西班牙语系统提示词
SYSTEM_PROMPT = """Eres un agente de servicio al cliente profesional para una tienda de comercio electrónico internacional que opera en España.

## Tu rol y responsabilidades:
- Proporcionar atención al cliente en español de manera amigable y profesional
- Ayudar a los usuarios con consultas sobre el estado de sus pedidos
- Asistir en la modificación de direcciones de entrega
- Responder preguntas sobre políticas de la tienda

## Reglas importantes:
- Cuando el usuario pregunte sobre POLÍTICAS, REGLAS, PREGUNTAS FRECUENTES (devoluciones, envíos, cambios, etc.), **SIEMPRE** llama primero a la función 'search' para buscar en la base de conocimiento, luego responde basándote en los resultados encontrados.

- Cuando el usuario necesite CONSULTAR EL ESTADO DE UN PEDIDO o la LOGÍSTICA, llama a la función 'query_order_logistics' con el número de pedido.

- Cuando el usuario necesite CAMBIAR la DIRECCIÓN de entrega, llama a la función 'update_order_address' con el número de pedido y la nueva dirección.

- Cuando el usuario necesite CANCELAR UN PEDIDO, llama a la función 'cancel_order' con el número de pedido.

- Cuando el usuario necesite SOLICITAR UN REEMBOLSO, llama a la función 'request_refund' con el número de pedido y la razón.

- Cuando el usuario necesite CALCULAR EL COSTO DE ENVÍO, llama a la función 'estimate_shipping' con el país y el peso en kg.

- Responde SIEMPRE en español.

- Mantén un tono amigable, profesional y servicial.

- Si no tienes toda la información necesaria, pide al usuario que la proporcione.
"""


# ============================================================
# Agent 状态定义
# ============================================================


class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], operator.add]
    pending_action: Optional[Dict[str, Any]]


# ============================================================
# 工具函数：生成确认消息
# ============================================================


def _generate_confirmation_message(tool_call) -> str:
    """
    生成操作确认消息（西班牙语）

    Args:
        tool_call: 工具调用对象

    Returns:
        str: 西班牙语确认消息
    """
    function_name = tool_call["name"]
    function_args = tool_call.get("args", {})

    if function_name == "cancel_order":
        order_id = function_args.get("order_id", "desconocido")
        return f"¿Confirmas que deseas cancelar el pedido {order_id}? Responde 'sí' para confirmar o 'no' para cancelar."

    elif function_name == "update_order_address":
        order_id = function_args.get("order_id", "desconocido")
        new_address = function_args.get("new_address", "desconocida")
        return f"¿Confirmas que deseas cambiar la dirección del pedido {order_id} a: '{new_address}'? Responde 'sí' para confirmar o 'no' para cancelar."

    elif function_name == "request_refund":
        order_id = function_args.get("order_id", "desconocido")
        reason = function_args.get("reason", "no especificada")
        return f"¿Confirmas que deseas solicitar un reembolso para el pedido {order_id}? Razón: '{reason}'. Responde 'sí' para confirmar o 'no' para cancelar."

    return "¿Confirmas esta acción? Responde 'sí' para confirmar o 'no' para cancelar."


# ============================================================
# LangGraph 节点函数
# ============================================================


def call_model(state: AgentState, openai_client: OpenAI):
    """
    调用 LLM 模型节点

    Args:
        state: Agent 状态
        openai_client: OpenAI 客户端实例

    Returns:
        更新后的状态
    """
    messages = state["messages"]
    pending_action = state.get("pending_action")

    # 检查是否是确认消息
    if pending_action:
        last_msg = messages[-1] if messages else None
        if isinstance(last_msg, HumanMessage):
            user_input = last_msg.content.lower().strip()
            # 用户确认
            if user_input in ["sí", "si", "sí, confirmo", "si, confirmo", "confirmo"]:
                # 恢复之前的工具调用
                tool_calls = [pending_action]
                return {
                    "messages": [
                        AIMessage(
                            content="Confirmando operación...",
                            tool_calls=[
                                {
                                    "name": tc["name"],
                                    "args": tc["args"],
                                    "id": tc.get("id", f"manual_{tc['name']}"),
                                }
                                for tc in tool_calls
                            ],
                        )
                    ],
                    "pending_action": None,
                }
            # 用户取消
            elif user_input in ["no", "no, cancelo", "cancelo", "cancelar"]:
                return {
                    "messages": [
                        AIMessage(content="Operación cancelada. ¿En qué puedo ayudarte ahora?")
                    ],
                    "pending_action": None,
                }

    # 构建消息上下文
    chat_messages = []
    # 添加系统消息
    chat_messages.append({"role": "system", "content": SYSTEM_PROMPT})
    # 转换 LangChain 消息到 OpenAI 格式
    for msg in messages:
        if isinstance(msg, SystemMessage):
            chat_messages.append({"role": "system", "content": msg.content})
        elif isinstance(msg, HumanMessage):
            chat_messages.append({"role": "user", "content": msg.content})
        elif isinstance(msg, AIMessage):
            ai_msg = {"role": "assistant", "content": msg.content}
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                ai_msg["tool_calls"] = [
                    {
                        "id": tc.get("id", f"tc_{i}"),
                        "type": "function",
                        "function": {
                            "name": tc["name"],
                            "arguments": json.dumps(tc["args"], ensure_ascii=False),
                        },
                    }
                    for i, tc in enumerate(msg.tool_calls)
                ]
            chat_messages.append(ai_msg)
        elif isinstance(msg, ToolMessage):
            chat_messages.append(
                {
                    "role": "tool",
                    "tool_call_id": msg.tool_call_id,
                    "content": msg.content,
                }
            )

    # 调用 DeepSeek API
    try:
        response = openai_client.chat.completions.create(
            model=DEEPSEEK_MODEL,
            messages=chat_messages,
            tools=TOOLS,
            tool_choice="auto",
            stream=False,
            timeout=API_TIMEOUT,
        )

        response_message = response.choices[0].message

        # 构建 LangChain AIMessage
        ai_msg = AIMessage(content=response_message.content)

        # 处理 tool calls
        if hasattr(response_message, "tool_calls") and response_message.tool_calls:
            ai_msg.tool_calls = [
                {
                    "name": tc.function.name,
                    "args": json.loads(tc.function.arguments),
                    "id": tc.id,
                }
                for tc in response_message.tool_calls
            ]

        return {"messages": [ai_msg]}

    except Exception as e:
        print(f"Error al llamar al modelo: {e}")
        return {
            "messages": [
                AIMessage(
                    content="Lo siento, ha ocurrido un error inesperado. Por favor, inténtalo de nuevo más tarde."
                )
            ],
        }


def execute_tools(state: AgentState):
    """
    执行工具节点

    Args:
        state: Agent 状态

    Returns:
        更新后的状态
    """
    messages = state["messages"]
    last_message = messages[-1] if messages else None

    if not isinstance(last_message, AIMessage) or not hasattr(last_message, "tool_calls"):
        return {"messages": []}

    tool_calls = last_message.tool_calls
    if not tool_calls:
        return {"messages": []}

    tool_messages = []
    new_pending_action = None

    for tool_call in tool_calls:
        function_name = tool_call["name"]
        function_args = tool_call.get("args", {})

        # 【第一步】先验证参数
        print(f"[Agente] Validando parámetros para: {function_name}")
        is_valid, error_msg, validated_args = validate_tool_args(function_name, function_args)
        
        if not is_valid:
            # 参数验证失败，返回错误提示
            print(f"[Agente] Validación fallida: {error_msg}")
            llm_error_msg = format_validation_error_for_llm(error_msg)
            tool_messages.append(
                ToolMessage(
                    content=llm_error_msg,
                    tool_call_id=tool_call.get("id", f"manual_{function_name}"),
                    name=function_name,
                )
            )
            continue  # 继续处理下一个 tool call
        
        # 验证通过，使用验证后的参数
        function_args = validated_args if validated_args is not None else function_args

        # 检查是否是敏感操作
        if function_name in SENSITIVE_ACTIONS:
            # 需要确认，暂存并返回提示
            new_pending_action = {
                "name": function_name,
                "args": function_args,
                "id": tool_call.get("id", f"manual_{function_name}"),
            }
            confirmation_msg = _generate_confirmation_message(tool_call)

            # 直接返回确认消息（不执行工具）
            return {
                "messages": [
                    AIMessage(content=confirmation_msg),
                ],
                "pending_action": new_pending_action,
            }

        # 非敏感操作直接执行
        print(f"[Agente] Ejecutando herramienta: {function_name}")

        try:
            if function_name == "search":
                result = search(function_args.get("query", ""))
            elif function_name == "query_order_logistics":
                result = query_order_logistics(function_args.get("order_id", ""))
            elif function_name == "update_order_address":
                result = update_order_address(
                    function_args.get("order_id", ""),
                    function_args.get("new_address", ""),
                )
            elif function_name == "cancel_order":
                result = cancel_order(function_args.get("order_id", ""))
            elif function_name == "request_refund":
                result = request_refund(
                    function_args.get("order_id", ""),
                    function_args.get("reason", ""),
                )
            elif function_name == "estimate_shipping":
                result = estimate_shipping(
                    function_args.get("country", ""),
                    function_args.get("weight", 0),
                )
            else:
                result = {"error": "Función desconocida"}

            # 确保结果是字符串
            if isinstance(result, (dict, list)):
                result_str = json.dumps(result, ensure_ascii=False)
            else:
                result_str = str(result)

            tool_messages.append(
                ToolMessage(
                    content=result_str,
                    tool_call_id=tool_call.get("id", f"manual_{function_name}"),
                    name=function_name,
                )
            )

        except Exception as e:
            print(f"Error al ejecutar herramienta {function_name}: {e}")
            tool_messages.append(
                ToolMessage(
                    content=f"Error al ejecutar la herramienta: {str(e)}",
                    tool_call_id=tool_call.get("id", f"manual_{function_name}"),
                    name=function_name,
                )
            )

    return {"messages": tool_messages, "pending_action": None}


def should_continue(state: AgentState) -> str:
    """
    决定下一步：继续调用工具还是结束

    Args:
        state: Agent 状态

    Returns:
        str: "tools" 或 END
    """
    messages = state["messages"]
    pending_action = state.get("pending_action")

    # 如果有待确认的操作，直接结束
    if pending_action:
        return END

    last_message = messages[-1] if messages else None

    if (
        isinstance(last_message, AIMessage)
        and hasattr(last_message, "tool_calls")
        and last_message.tool_calls
    ):
        return "tools"

    return END


# ============================================================
# Agent 类
# ============================================================


class CustomerServiceAgent:
    """
    西班牙语跨境电商客服 Agent（LangGraph 版本）

    使用 DeepSeek-V3 模型，结合 RAG 检索和业务工具，
    为西班牙语客户提供订单查询、地址修改、政策咨询等服务。
    """

    def __init__(self):
        """
        初始化客服 Agent
        - 初始化 OpenAI 客户端连接 DeepSeek API
        - 构建知识库索引
        - 编译 LangGraph 图
        - 初始化 SQLite 数据库
        """
        # 从环境变量读取 API Key
        api_key = os.getenv("DEEPSEEK_API_KEY")
        if not api_key:
            raise ValueError(
                "No se encontró la variable de entorno DEEPSEEK_API_KEY. "
                "Por favor, configure su API key de DeepSeek."
            )

        # 初始化 OpenAI 客户端
        self.client = OpenAI(
            api_key=api_key,
            base_url=DEEPSEEK_BASE_URL,
            timeout=API_TIMEOUT,
        )

        # 构建知识库
        print("Inicializando base de conocimiento...")
        try:
            build_knowledge_base()
        except Exception as e:
            print(f"Error al inicializar la base de conocimiento: {e}")
        print("Agente de servicio al cliente listo!")

        # 构建 LangGraph 图
        workflow = StateGraph(AgentState)

        # 添加节点
        workflow.add_node("agent", lambda state: call_model(state, self.client))
        workflow.add_node("tools", execute_tools)

        # 设置入口点
        workflow.set_entry_point("agent")

        # 添加条件边
        workflow.add_conditional_edges(
            "agent",
            should_continue,
            {
                "tools": "tools",
                END: END,
            },
        )

        # 添加从 tools 回到 agent 的边
        workflow.add_edge("tools", "agent")

        # 添加记忆
        memory = MemorySaver()

        # 编译图
        self.app = workflow.compile(checkpointer=memory)

        # 线程 ID，用于区分不同的对话
        self.thread_id = "thread-0"

        # SQLite 数据库配置
        self.db_path = "conversations.db"
        self.init_db()

    def init_db(self):
        """
        初始化 SQLite 数据库，创建对话记录表
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.commit()
        conn.close()
        print("Database initialized successfully.")

    def save_message(self, session_id, role, content):
        """
        保存单条消息到数据库

        Args:
            session_id: 会话 ID
            role: 角色（user 或 assistant）
            content: 消息内容
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO conversations (session_id, role, content) VALUES (?, ?, ?)",
                (session_id, role, content),
            )
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Error saving message to database: {e}")

    def load_history(self, session_id) -> list[dict]:
        """
        从数据库加载会话历史

        Args:
            session_id: 会话 ID

        Returns:
            消息列表，格式为 [{"role": role, "content": content}, ...]
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT role, content FROM conversations WHERE session_id = ? ORDER BY timestamp ASC",
                (session_id,),
            )
            rows = cursor.fetchall()
            conn.close()
            return [{"role": role, "content": content} for (role, content) in rows]
        except Exception as e:
            print(f"Error loading conversation history: {e}")
            return []

    def chat(self, user_message: str, session_id="default_user") -> str:
        """
        处理用户消息并生成回复（非流式）

        Args:
            user_message: 用户输入的西班牙语消息
            session_id: 会话 ID（用于持久化）

        Returns:
            str: Agent 生成的西班牙语回复
        """
        try:
            # 保存用户消息到数据库
            self.save_message(session_id, "user", user_message)

            # 配置对话线程
            config = {"configurable": {"thread_id": self.thread_id}}

            # 调用 LangGraph
            output = self.app.invoke(
                {"messages": [HumanMessage(content=user_message)]},
                config=config,
            )

            # 提取最后一条助理消息
            messages = output["messages"]
            reply = "Lo siento, no puedo responder en este momento."
            for msg in reversed(messages):
                if isinstance(msg, AIMessage):
                    reply = msg.content
                    break

            # 保存助理回复到数据库
            self.save_message(session_id, "assistant", reply)

            return reply

        except Exception as e:
            print(f"Error en el chat: {e}")
            return "Lo siento, ha ocurrido un error inesperado. Por favor, inténtalo de nuevo más tarde."

    def chat_stream(self, user_message: str, session_id="default_user"):
        """
        处理用户消息并生成流式回复

        Args:
            user_message: 用户输入的西班牙语消息
            session_id: 会话 ID（用于持久化）

        Yields:
            str: 流式输出的片段
        """
        try:
            # 保存用户消息到数据库
            self.save_message(session_id, "user", user_message)

            # 配置对话线程
            config = {"configurable": {"thread_id": self.thread_id}}

            # 输入状态
            input_state = {"messages": [HumanMessage(content=user_message)]}

            # 流式执行 LangGraph
            full_reply = ""
            for event in self.app.stream(input_state, config=config, stream_mode="values"):
                messages = event["messages"]
                last_msg = messages[-1]
                
                # 如果是 LLM 正在生成回复（流式 token）
                if isinstance(last_msg, AIMessage):
                    # 这里我们用非流式的，但在实际场景中
                    # 可以用 LLM 的流式接口逐字 yield
                    if last_msg.content and last_msg.content != full_reply:
                        delta = last_msg.content[len(full_reply):]
                        if delta:
                            full_reply = last_msg.content
                            yield delta
                    elif last_msg.tool_calls:
                        # 如果是工具调用，提示用户
                        yield "\n[Agent: Llamando a herramientas...]\n"
            
            # 保存最终回复到数据库
            self.save_message(session_id, "assistant", full_reply)

        except Exception as e:
            print(f"Error en el chat_stream: {e}")
            yield "Lo siento, ha ocurrido un error inesperado. Por favor, inténtalo de nuevo más tarde."


# ============================================================
# 主程序入口
# ============================================================

if __name__ == "__main__":
    """
    交互式测试程序
    启动客服 Agent，等待用户输入并生成回复
    """
    print("=" * 60)
    print("跨境电商客服 Agent - LangGraph 版本 - Modo de Prueba")
    print("=" * 60)
    print()

    try:
        # 初始化 Agent
        print("Inicializando agente...")
        agent = CustomerServiceAgent()

        print()
        print("=" * 60)
        print("¡Bienvenido! Soy tu asistente de servicio al cliente.")
        print("Puedo ayudarte con:")
        print("  - Consultas sobre el estado de tus pedidos")
        print("  - Modificación de direcciones de entrega")
        print("  - Cancelación de pedidos (requiere confirmación)")
        print("  - Solicitudes de reembolso (requieren confirmación)")
        print("  - Estimación de costos de envío")
        print("  - Información sobre políticas de la tienda")
        print()
        print("Escribe 'salir' para terminar la conversación.")
        print("=" * 60)
        print()

        # 交互式循环
        while True:
            # 等待用户输入
            user_input = input("Usted: ").strip()

            # 检查退出命令
            if user_input.lower() == "salir":
                print("\n¡Gracias por usar nuestro servicio! ¡Hasta luego!")
                break

            # 检查空输入
            if not user_input:
                print("Por favor, ingresa un mensaje.\n")
                continue

            # 调用 Agent 处理消息
            response = agent.chat(user_input)
            print(f"\nAgente: {response}\n")

    except ValueError as e:
        # API Key 未配置
        print(f"\nError de configuración: {e}")
        print("\nPor favor, configura la variable de entorno DEEPSEEK_API_KEY")
        print("En Windows: set DEEPSEEK_API_KEY=tu_api_key")
        print("En Linux/Mac: export DEEPSEEK_API_KEY=tu_api_key")

    except KeyboardInterrupt:
        print("\n\nPrograma interrumpido por el usuario.")
        print("¡Hasta luego!")

    except Exception as e:
        # 其他错误
        print(f"\nError inesperado: {e}")
        import traceback

        traceback.print_exc()

