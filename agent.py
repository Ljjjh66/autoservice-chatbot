"""
西班牙语跨境电商客服 Agent
使用 DeepSeek-V3 模型，结合 RAG 检索和业务工具
"""

import re
import time
from types import SimpleNamespace

import os
import json
from openai import OpenAI
from openai import APIError, APIConnectionError, RateLimitError

# 从同项目导入模块
from tools import query_order_logistics, update_order_address, cancel_order, request_refund, estimate_shipping
from rag import search, build_knowledge_base


# ============================================================
# 配置常量
# ============================================================

# DeepSeek API 配置
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_MODEL = "deepseek-chat"
API_TIMEOUT = 30  # 超时时间（秒）

# 敏感操作列表
SENSITIVE_ACTIONS = ["update_order_address", "cancel_order", "request_refund"]


# ============================================================
# 西班牙语系统提示词
# ============================================================

SYSTEM_PROMPT = """Eres un agente de servicio al cliente profesional para una tienda de comercio electrónico internacional que opera en España.

## Tu rol y responsabilidades:
- Proporcionar atención al cliente en español de manera amable y profesional
- Ayudar a los usuarios con consultas sobre el estado de sus pedidos
- Asistir en la modificación de direcciones de entrega
- Responder preguntas sobre políticas de la tienda

## Reglas importantes:
- Cuando el usuario pregunte sobre POLÍTICAS, REGLAS, PREGUNTAS FRECUENTES (devoluciones, envío, cambios, etc.), **SIEMPRE** llama primero a la función 'search' para buscar en la base de conocimiento, luego responde basándote en los resultados encontrados.

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
# Agent 类定义
# ============================================================

class CustomerServiceAgent:
    """
    西班牙语跨境电商客服 Agent

    使用 DeepSeek-V3 模型，结合 RAG 检索和业务工具，
    为西班牙语客户提供订单查询、地址修改、政策咨询等服务。
    """

    def __init__(self):
        """
        初始化客服 Agent
        - 初始化 OpenAI 客户端连接 DeepSeek API
        - 构建知识库索引
        - 初始化对话历史列表
        - 初始化待确认操作存储
        """
        # 从环境变量读取 API Key
        api_key = os.getenv("DEEPSEEK_API_KEY")
        if not api_key:
            raise ValueError(
                "No se encontró la variable de entorno DEEPSEEK_API_KEY. "
                "Por favor, configure su API key de DeepSeek."
            )

        # 初始化 OpenAI 客户端（连接到 DeepSeek）
        self.client = OpenAI(
            api_key=api_key,
            base_url=DEEPSEEK_BASE_URL,
            timeout=API_TIMEOUT
        )

        # 模型名称
        self.model = DEEPSEEK_MODEL

        # 构建或加载知识库索引
        print("Inicializando base de conocimiento...")
        try:
            build_knowledge_base()
        except Exception as e:
            print(f"Error al inicializar la base de conocimiento: {e}")
        print("Agente de servicio al cliente listo!")

        # 初始化对话历史列表
        self.messages = [{"role": "system", "content": SYSTEM_PROMPT}]

        # 初始化待确认操作
        self.pending_action = None


    def _generate_confirmation_message(self, tool_call) -> str:
        """
        生成操作确认消息

        Args:
            tool_call: 工具调用对象

        Returns:
            str: 西班牙语确认消息
        """
        function_name = tool_call.function.name
        function_args = json.loads(tool_call.function.arguments)

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


    def chat(self, user_message: str) -> str:
        """
        处理用户消息并生成回复

        Args:
            user_message: 用户输入的西班牙语消息

        Returns:
            str: Agent 生成的西班牙语回复
        """
        try:
            # 检查是否是对确认操作的响应
            user_message_lower = user_message.strip().lower()
            
            if self.pending_action is not None:
                # 用户确认操作
                if user_message_lower in ["sí", "si", "sí, confirmo", "si, confirmo", "confirmo"]:
                    print(f"[Agente] Confirmando operación pendiente...")
                    
                    # 执行暂存的操作
                    tool_call = self.pending_action
                    function_name = tool_call.function.name
                    function_args = json.loads(tool_call.function.arguments)
                    
                    # 将暂存的工具调用加入历史
                    self.messages.append({
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": tool_call.id,
                                "type": "function",
                                "function": {
                                    "name": tool_call.function.name,
                                    "arguments": tool_call.function.arguments
                                }
                            }
                        ]
                    })
                    
                    # 执行对应的函数
                    if function_name == "search":
                        function_result = search(function_args.get("query", ""))
                    elif function_name == "query_order_logistics":
                        function_result = query_order_logistics(function_args.get("order_id", ""))
                    elif function_name == "update_order_address":
                        function_result = update_order_address(
                            function_args.get("order_id", ""),
                            function_args.get("new_address", "")
                        )
                    elif function_name == "cancel_order":
                        function_result = cancel_order(function_args.get("order_id", ""))
                    elif function_name == "request_refund":
                        function_result = request_refund(
                            function_args.get("order_id", ""),
                            function_args.get("reason", "")
                        )
                    elif function_name == "estimate_shipping":
                        function_result = estimate_shipping(
                            function_args.get("country", ""),
                            function_args.get("weight", 0)
                        )
                    else:
                        function_result = {"error": "Función desconocida"}
                    
                    # 将工具执行结果加入历史
                    self.messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(function_result, ensure_ascii=False)
                    })
                    
                    # 清空待确认操作
                    self.pending_action = None
                    
                    # 再次调用模型生成最终回复
                    final_response = self.client.chat.completions.create(
                        model="deepseek-chat",
                        messages=self.messages,
                        max_tokens=300,
                        temperature=0.7,
                        stream=False,
                        timeout=30
                    )
                    reply = final_response.choices[0].message.content
                    
                    # 将最终回复加入历史
                    self.messages.append({"role": "assistant", "content": reply})
                    return reply
                
                # 用户取消操作
                elif user_message_lower in ["no", "no, cancelo", "cancelo", "cancelar"]:
                    print(f"[Agente] Operación cancelada por el usuario")
                    self.pending_action = None
                    self.messages.append({
                        "role": "user",
                        "content": user_message
                    })
                    reply = "Operación cancelada."
                    self.messages.append({
                        "role": "assistant",
                        "content": reply
                    })
                    return reply
            
            # 正常处理用户消息
            # 步骤 a: 将用户消息加入对话历史
            self.messages.append({
                "role": "user",
                "content": user_message
            })

            # 步骤 c: 工具函数定义（OpenAI 格式）
            tools = [
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
                                    "description": "Número de pedido, formato: ESPxxxxx"
                                }
                            },
                            "required": ["order_id"]
                        }
                    }
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
                                    "description": "Número de pedido, formato: ESPxxxxx"
                                },
                                "new_address": {
                                    "type": "string",
                                    "description": "Nueva dirección de entrega"
                                }
                            },
                            "required": ["order_id", "new_address"]
                        }
                    }
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
                                    "description": "Consulta del usuario en español"
                                },
                                "top_k": {
                                    "type": "integer",
                                    "description": "Número de resultados a recuperar (por defecto 2)",
                                    "default": 2
                                }
                            },
                            "required": ["query"]
                        }
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "cancel_order",
                        "description": "Cancelar un pedido que aún no ha sido enviado. Requiere order_id.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "order_id": {
                                    "type": "string",
                                    "description": "Número de pedido, formato: ESPxxxxx"
                                }
                            },
                            "required": ["order_id"]
                        }
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "request_refund",
                        "description": "Solicitar un reembolso para un pedido entregado. Requiere order_id y razón.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "order_id": {
                                    "type": "string",
                                    "description": "Número de pedido, formato: ESPxxxxx"
                                },
                                "reason": {
                                    "type": "string",
                                    "description": "Razón del reembolso (opcional)"
                                }
                            },
                            "required": ["order_id"]
                        }
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "estimate_shipping",
                        "description": "Estimar el costo de envío internacional. Requiere país y peso en kg.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "country": {
                                    "type": "string",
                                    "description": "País de destino (en español o inglés)"
                                },
                                "weight": {
                                    "type": "number",
                                    "description": "Peso del paquete en kilogramos"
                                }
                            },
                            "required": ["country", "weight"]
                        }
                    }
                }
            ]

            # 步骤 d: 第一次调用：让模型决定是否需要调用工具
            response = self.client.chat.completions.create(
                model=self.model,
                messages=self.messages,
                tools=tools,
                tool_choice="auto",
                stream=False,
                timeout=API_TIMEOUT
            )

            # Procesar la respuesta del modelo
            response_message = response.choices[0].message

            # 容错修复：如果标准字段里没有 tool_calls，但模型在文本中输出了 function call
            if not response_message.tool_calls and hasattr(response_message, 'content') and response_message.content:
                content = response_message.content
                if '<｜｜DSML｜｜invoke name="' in content:
                    # 先添加模型的文本回复到历史（作为 assistant 消息，无 tool_calls）
                    self.messages.append({
                        "role": "assistant",
                        "content": response_message.content
                    })

                    # 解析并执行工具
                    invokes = re.findall(r'<｜｜DSML｜｜invoke name="(\w+)">(.*?)</｜｜DSML｜｜invoke>', content, re.DOTALL)
                    for func_name, params_str in invokes:
                        params = {}
                        for param_match in re.finditer(r'<｜｜DSML｜｜parameter name="(\w+)"[^>]*>(.*?)</｜｜DSML｜｜parameter>', params_str, re.DOTALL):
                            pname = param_match.group(1)
                            pvalue = param_match.group(2)
                            try:
                                pvalue = json.loads(pvalue)
                            except:
                                pass
                            params[pname] = pvalue

                        print(f"[Agente] Reparación manual: llamando a {func_name}")
                        
                        # 检查是否是敏感操作
                        if func_name in SENSITIVE_ACTIONS:
                            # 构建模拟的 tool_call
                            mock_tool_call = SimpleNamespace(
                                id=f"manual_{func_name}_{int(time.time())}",
                                function=SimpleNamespace(
                                    name=func_name,
                                    arguments=json.dumps(params, ensure_ascii=False)
                                )
                            )
                            self.pending_action = mock_tool_call
                            confirmation_msg = self._generate_confirmation_message(mock_tool_call)
                            self.messages.append({
                                "role": "assistant",
                                "content": confirmation_msg
                            })
                            return confirmation_msg
                        
                        # 非敏感操作直接执行
                        if func_name == "search":
                            function_result = search(params.get("query", ""))
                        elif func_name == "query_order_logistics":
                            function_result = query_order_logistics(params.get("order_id", ""))
                        elif func_name == "update_order_address":
                            function_result = update_order_address(params.get("order_id", ""), params.get("new_address", ""))
                        elif func_name == "cancel_order":
                            function_result = cancel_order(params.get("order_id", ""))
                        elif func_name == "request_refund":
                            function_result = request_refund(params.get("order_id", ""), params.get("reason", ""))
                        elif func_name == "estimate_shipping":
                            function_result = estimate_shipping(params.get("country", ""), params.get("weight", 0))
                        else:
                            function_result = {"error": "Función desconocida"}

                        # 添加 tool 消息到历史
                        self.messages.append({
                            "role": "tool",
                            "tool_call_id": f"manual_{func_name}",
                            "content": json.dumps(function_result, ensure_ascii=False)
                        })

                    # 用更新后的历史再次调用模型生成最终回复
                    try:
                        final_response = self.client.chat.completions.create(
                            model="deepseek-chat",
                            messages=self.messages,
                            max_tokens=300,
                            temperature=0.7,
                            stream=False,
                            timeout=30
                        )
                        reply = final_response.choices[0].message.content
                    except Exception as e:
                        print(f"Error en la respuesta final: {e}")
                        reply = "Lo siento, encontré un problema al procesar la respuesta."

                    # 将最终回复加入历史
                    self.messages.append({"role": "assistant", "content": reply})
                    return reply

            # 检查模型是否要求调用工具
            if response_message.tool_calls:
                # 检查是否有敏感操作需要确认
                has_sensitive_action = False
                for tool_call in response_message.tool_calls:
                    if tool_call.function.name in SENSITIVE_ACTIONS:
                        has_sensitive_action = True
                        break
                
                if has_sensitive_action:
                    # 对于敏感操作，暂存并请求确认
                    for tool_call in response_message.tool_calls:
                        if tool_call.function.name in SENSITIVE_ACTIONS:
                            self.pending_action = tool_call
                            confirmation_msg = self._generate_confirmation_message(tool_call)
                            
                            # 将模型的消息加入历史
                            self.messages.append({
                                "role": "assistant",
                                "content": response_message.content
                            })
                            
                            # 将确认消息加入历史
                            self.messages.append({
                                "role": "assistant",
                                "content": confirmation_msg
                            })
                            
                            return confirmation_msg
                
                # 非敏感操作直接执行
                # 将模型的工具调用请求加入历史
                self.messages.append({
                    "role": "assistant",
                    "content": response_message.content,
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments
                            }
                        } for tc in response_message.tool_calls
                    ]
                })

                # 逐个执行工具调用
                for tool_call in response_message.tool_calls:
                    function_name = tool_call.function.name
                    function_args = json.loads(tool_call.function.arguments)

                    print(f"[Agente] Llamando a herramienta: {function_name}")

                    # 执行对应的函数
                    if function_name == "search":
                        function_result = search(function_args.get("query", ""))
                    elif function_name == "query_order_logistics":
                        function_result = query_order_logistics(function_args.get("order_id", ""))
                    elif function_name == "update_order_address":
                        function_result = update_order_address(
                            function_args.get("order_id", ""),
                            function_args.get("new_address", "")
                        )
                    elif function_name == "cancel_order":
                        function_result = cancel_order(function_args.get("order_id", ""))
                    elif function_name == "request_refund":
                        function_result = request_refund(
                            function_args.get("order_id", ""),
                            function_args.get("reason", "")
                        )
                    elif function_name == "estimate_shipping":
                        function_result = estimate_shipping(
                            function_args.get("country", ""),
                            function_args.get("weight", 0)
                        )
                    else:
                        function_result = {"error": "Función desconocida"}

                    # 将工具执行结果以正确的格式加入历史
                    self.messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(function_result, ensure_ascii=False)
                    })

                # 用更新后的历史再次调用模型，生成最终回复
                try:
                    final_response = self.client.chat.completions.create(
                        model="deepseek-chat",
                        messages=self.messages,
                        max_tokens=300,
                        temperature=0.7,
                        stream=False,
                        timeout=30
                    )
                    reply = final_response.choices[0].message.content
                except Exception as e:
                    print(f"Error en la respuesta final: {e}")
                    reply = "Lo siento, encontré un problema al procesar la respuesta."

            else:
                # 模型没有请求工具，直接使用其回复
                reply = response_message.content

            # Respuesta final
            self.messages.append({"role": "assistant", "content": reply})
            return reply

        except Exception as e:
            error_message = f"Error inesperado: {str(e)}"
            print(error_message)
            return "Lo siento, ha ocurrido un error inesperado. Por favor, inténtelo de nuevo más tarde."


# ============================================================
# 主程序入口
# ============================================================

if __name__ == "__main__":
    """
    交互式测试程序
    启动客服 Agent，等待用户输入并生成回复
    """
    print("=" * 60)
    print("跨境电商客服 Agent - Modo de Prueba")
    print("=" * 60)
    print()

    try:
        # 初始化 Agent
        print("Inicializando agente...")
        agent = CustomerServiceAgent()

        print()
        print("=" * 60)
        print("¡Bienvenido! Soy su asistente de servicio al cliente.")
        print("Puedo ayudarle con:")
        print("  - Consultas sobre el estado de sus pedidos")
        print("  - Modificación de direcciones de entrega")
        print("  - Cancelación de pedidos (requiere confirmación)")
        print("  - Solicitudes de reembolso (requieren confirmación)")
        print("  - Estimación de costos de envío")
        print("  - Información sobre políticas de la tienda")
        print()
        print("Escriba 'salir' para terminar la conversación.")
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
                print("Por favor, ingrese un mensaje.\n")
                continue

            # 调用 Agent 处理消息
            response = agent.chat(user_input)
            print(f"\nAgente: {response}\n")

    except ValueError as e:
        # API Key 未配置
        print(f"\nError de configuración: {e}")
        print("\nPor favor, configure la variable de entorno DEEPSEEK_API_KEY")
        print("En Windows: set DEEPSEEK_API_KEY=su_api_key")
        print("En Linux/Mac: export DEEPSEEK_API_KEY=su_api_key")

    except KeyboardInterrupt:
        print("\n\nPrograma interrumpido por el usuario.")
        print("¡Hasta luego!")

    except Exception as e:
        # 其他错误
        print(f"\nError inesperado: {e}")
