import uvicorn
import threading
import logging
import asyncio
import os
from fastapi import FastAPI, WebSocket, Request, WebSocketDisconnect, Query
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional
from datetime import datetime
from decimal import Decimal, ROUND_DOWN, InvalidOperation

# --- 1. 核心模块导入 ---
try:
    from logger import setup_logger
    from config import ENABLE_DATABASE
    from strategies.market_maker import MarketMaker
    from strategies.perp_market_maker import PerpetualMarketMaker
    from strategies.maker_taker_hedge import MakerTakerHedgeStrategy
    from api.bp_client import BPClient
    # from api.aster_client import AsterClient # Removed
except ImportError as e:
    print(f"[错误] 导入核心模块失败: {e}")
    # ... (错误提示与上次相同) ...
    exit(1)
except Exception as e:
    print(f"[错误] 导入模块时发生意外错误: {e}")
    exit(1)

# -------------------------------------------------------------------
# 2. 初始化 FastAPI 和日志
# -------------------------------------------------------------------
app = FastAPI(title="MM 机器人 API 服务器")
logger = setup_logger("api_server")

RUNNING_BOTS: Dict[str, Any] = {}
BOT_THREADS: Dict[str, threading.Thread] = {}
_bot_lock = threading.Lock()


# -------------------------------------------------------------------
# 3. WebSocket 实时日志系统 (语法修正版)
# -------------------------------------------------------------------
class WebSocketLogManager:
    def __init__(self):
        # ... existing code ...
        self.active_connections: List[WebSocket] = []
        # (修正) asyncio.Lock 只能在 async 函数中使用，这里用 threading.Lock 保护列表本身
        self._list_lock = threading.Lock()

    async def connect(self, websocket: WebSocket):
        # ... existing code ...
        await websocket.accept()
        # (修正) 使用 threading.Lock 保护列表添加操作
        with self._list_lock:
            # ... existing code ...
            self.active_connections.append(websocket)
        logger.info("前端 WebSocket 已连接")
        # (修正) 添加 try-except 块
        # ... existing code ...
        try:
            await websocket.send_text("WebSocket 日志连接成功！")
        except (WebSocketDisconnect, RuntimeError) as e:  # Catch specific exceptions
            # ... existing code ...
            logger.warning(f"发送初始消息时 WebSocket 出错: {e}")
            await self.disconnect(websocket)  # Clean up if send fails

    async def disconnect(self, websocket: WebSocket):
        # ... existing code ...
        # (修正) 使用 threading.Lock 保护列表移除操作
        with self._list_lock:
            if websocket in self.active_connections:
                # ... existing code ...
                # (修正) 使用 try-except ValueError
                try:
                    self.active_connections.remove(websocket)
                    # ... existing code ...
                    logger.info("前端 WebSocket 已断开")
                except ValueError:
                    pass  # Ignore if already removed

    async def broadcast(self, message: str):
        # ... existing code ...
        # (修正) 使用 threading.Lock 保护列表复制操作
        with self._list_lock:
            # Create a snapshot of connections to iterate over
            # ... existing code ...
            connections_to_broadcast = list(self.active_connections)

        if not connections_to_broadcast:
            # ... existing code ...
            return

        # Use asyncio.gather for concurrent sends
        # ... existing code ...
        tasks = [self._send_to_websocket(connection, message) for connection in connections_to_broadcast]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Handle failed sends and cleanup disconnected clients
        # ... existing code ...
        disconnected_clients = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                # ... existing code ...
                disconnected_clients.append(connections_to_broadcast[i])

        if disconnected_clients:
            # (修正) 使用 threading.Lock 保护列表移除操作
            # ... existing code ...
            with self._list_lock:
                for client in disconnected_clients:
                    if client in self.active_connections:
                        # ... existing code ...
                        # (修正) 添加 try-except ValueError
                        try:
                            self.active_connections.remove(client)
                            # ... existing code ...
                            logger.debug("已移除断开的 WS 连接")
                        except ValueError:
                            pass  # Already removed

    async def _send_to_websocket(self, websocket: WebSocket, message: str):
        # ... existing code ...
        # (修正) 添加 try-except 块
        try:
            await websocket.send_text(message)
        # ... existing code ...
        except (WebSocketDisconnect, RuntimeError, ConnectionRefusedError) as e:  # Catch specific exceptions
            # logger.debug(f"向 WebSocket 发送消息失败: {e}") # Reduce noise
            raise  # Re-raise the exception to be caught by gather
        # ... existing code ...
        except Exception as e:  # Catch any other potential errors during send
            logger.warning(f"向 WebSocket 发送时发生未知错误: {e}")
            raise  # Re-raise


log_manager = WebSocketLogManager()


class WebSocketLogHandler(logging.Handler):
    # ... existing code ...
    # (修正) 移除 self.loop 初始化，依赖 call_soon_threadsafe
    def __init__(self, manager: WebSocketLogManager):
        super().__init__()
        # ... existing code ...
        self.manager = manager

    def emit(self, record):
        # ... existing code ...
        if record.levelno < logging.INFO:
            return
        # (修正) 确保 try-except 覆盖整个 emit 逻辑
        # ... existing code ...
        try:
            log_entry = self.format(record)
            # ... existing code ...
            # Get the running loop in the main thread (where FastAPI runs) if possible
            try:
                loop = asyncio.get_running_loop()
                # ... existing code ...
                # If called from a different thread, use call_soon_threadsafe
                if loop and loop.is_running():
                    if threading.current_thread() is threading.main_thread():
                        # ... existing code ...
                        # If in main thread, schedule directly
                        asyncio.create_task(self.manager.broadcast(log_entry))
                    else:
                        # ... existing code ...
                        # If in another thread (like the bot thread), use threadsafe version
                        loop.call_soon_threadsafe(
                            asyncio.create_task,
                            # ... existing code ...
                            self.manager.broadcast(log_entry)
                        )
                else:
                    # ... existing code ...
                    # Fallback if no loop is running (less ideal)
                    logger.warning("事件循环未运行，尝试同步广播 (可能阻塞)")
                    # ... existing code ...
                    asyncio.run(self.manager.broadcast(log_entry))

            except RuntimeError:  # No running loop in current context
                # ... existing code ...
                # Try getting the main event loop if available (might work depending on setup)
                try:
                    main_loop = asyncio.get_event_loop()
                    # ... existing code ...
                    if main_loop and main_loop.is_running():
                        main_loop.call_soon_threadsafe(
                            asyncio.create_task,
                            # ... existing code ...
                            self.manager.broadcast(log_entry)
                        )
                    else:
                        # ... existing code ...
                        logger.warning("主事件循环未运行，尝试同步广播")
                        asyncio.run(self.manager.broadcast(log_entry))
                except RuntimeError as loop_err:
                    # ... existing code ...
                    print(f"WS Log Handler Loop Error: {loop_err}")
                    print(log_entry)  # Print log if loop fails entirely

        except Exception as e:
            # ... existing code ...
            print(f"WebSocketLogHandler 错误: {e}")
            # Ensure the log is still visible somewhere
            print(log_entry)


@app.on_event("startup")
async def startup_event():
    # ... existing code ...
    root_logger = logging.getLogger()
    if root_logger.level > logging.INFO:
        root_logger.setLevel(logging.INFO)

    if not any(isinstance(h, WebSocketLogHandler) for h in root_logger.handlers):
        # ... existing code ...
        ws_handler = WebSocketLogHandler(log_manager)
        ws_handler.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        # ... existing code ...
        ws_handler.setFormatter(formatter)
        root_logger.addHandler(ws_handler)
        logger.info("FastAPI 启动，WebSocket 日志处理器已附加")
    # ... existing code ...
    else:
        logger.info("FastAPI 重载，WebSocket 日志处理器已存在")


@app.websocket("/ws/logs")
async def websocket_logs(websocket: WebSocket):
    # ... existing code ...
    await log_manager.connect(websocket)
    try:
        while True:
            # ... existing code ...
            # Keep connection alive, wait for disconnect
            await websocket.receive_text()
    except WebSocketDisconnect:
        # ... existing code ...
        logger.info("WebSocket 客户端主动断开")
    except Exception as e:
        # ... existing code ...
        logger.warning(f"WebSocket 连接异常: {e}")
    finally:
        # Ensure disconnection cleanup
        # ... existing code ...
        await log_manager.disconnect(websocket)


# -------------------------------------------------------------------
# 4. Pydantic 模型 (与上次相同)
# -------------------------------------------------------------------
class BotConfig(BaseModel):  # ... (代码与上次相同) ...
    symbol: str = Field(...)
    # exchange: str = Field(default='backpack') # Removed
    market_type: str = Field(default='spot')
    strategy: str = Field(default='standard')
    spread: float = Field(...)
    quantity: Optional[float] = Field(default=None)
    max_orders: int = Field(default=3)
    duration: int = Field(default=86400)
    interval: int = Field(default=60)
    target_volume: Optional[float] = Field(default=None)
    target_position: float = Field(default=0.0)
    max_position: float = Field(default=1.0)
    position_threshold: float = Field(default=0.1)
    inventory_skew: float = Field(default=0.0)
    stop_loss: Optional[float] = Field(default=None)
    take_profit: Optional[float] = Field(default=None)
    enable_rebalance: bool = Field(default=True)
    base_asset_target: float = Field(default=30.0)
    rebalance_threshold: float = Field(default=15.0)
    # --- (新) 智能策略参数 ---
    stale_threshold_percent: Optional[float] = Field(default=None)
    volatility_config: Optional[Dict[str, float]] = Field(default=None)
    depth_weights: Optional[List[float]] = Field(default=None)


# -------------------------------------------------------------------
# 5. API 端点 (包含所有语法修正)
# -------------------------------------------------------------------

def _get_api_credentials():  # ... (代码与上次相同) ...
    # ... existing code ...
    # Simplified: Always return Backpack credentials
    return os.getenv("BACKPACK_KEY"), os.getenv("BACKPACK_SECRET"), os.getenv(
        'BACKPACK_PROXY_WEBSOCKET'), os.getenv('BASE_URL', 'https://api.backpack.work')


def _format_balance(value_str: Any, decimals: int = 8) -> str:
    # ... existing code ...
    # (修正) 确保 try-except 结构正确
    try:
        if value_str is None or str(value_str).strip() == "": return "0.0"
        # ... existing code ...
        d_value = Decimal(str(value_str))
        quantizer = Decimal('1e-' + str(decimals))
        # ... existing code ...
        formatted = d_value.quantize(quantizer, rounding=ROUND_DOWN)
        formatted_str = formatted.to_eng_string()
        if '.' in formatted_str: formatted_str = formatted_str.rstrip('0').rstrip('.')
        # ... existing code ...
        return formatted_str if formatted_str and formatted_str != '-' else "0"
    # (修正) 添加 except (InvalidOperation, TypeError, ValueError):
    except (InvalidOperation, TypeError, ValueError):
        # ... existing code ...
        return "0.0"


def run_bot_thread(bot_instance: MarketMaker, duration: int, interval: int, bot_id: str):
    # ... existing code ...
    # (修正) 确保 try-except-finally 结构正确
    try:
        if hasattr(bot_instance, 'run') and callable(bot_instance.run):
            # ... existing code ...
            logger.info(f"启动机器人线程: {bot_id} (Duration: {duration}s, Interval: {interval}s)")
            bot_instance.run(duration_seconds=duration, interval_seconds=interval)
            logger.info(f"机器人线程 {bot_id} run() 方法执行完毕。")
        # ... existing code ...
        else:
            logger.error(f"机器人实例 {bot_id} 没有 'run' 方法!")
    except Exception as e:
        # ... existing code ...
        logger.error(f"机器人线程 {bot_id} 运行时发生未捕获异常: {e}", exc_info=True)
    finally:
        # ... existing code ...
        logger.info(f"机器人线程 {bot_id} 结束。")
        with _bot_lock:
            # (修正) 使用 try-except 包装 pop
            # ... existing code ...
            try:
                RUNNING_BOTS.pop(bot_id, None)
                BOT_THREADS.pop(bot_id, None)
            # ... existing code ...
            except Exception as cleanup_err:
                logger.error(f"清理机器人 {bot_id} 时发生意外错误: {cleanup_err}")


@app.get("/api/balance")
async def get_account_balance():  # Removed exchange parameter
    # ... existing code ...
    logger.info(f"收到获取余额请求: Backpack")
    api_key, secret_key, _, base_url = _get_api_credentials()
    # ... existing code ...
    exchange = "backpack"

    if not api_key or not secret_key: return JSONResponse(status_code=401,
                                                          # ... existing code ...
                                                          content={"error": f"未配置 {exchange.upper()} API 密钥"})

    response_data = {"exchange": exchange, "spot_balances": {}, "futures_balances": {}}
    # ... existing code ...
    # (修正) 确保 try-except 结构正确
    try:
        client: Any = None
        # ... existing code ...
        exchange_config = {'api_key': api_key, 'secret_key': secret_key}
        if base_url: exchange_config['base_url'] = base_url

        # Simplified: Removed Aster logic, only Backpack logic remains
        # ... existing code ...
        client = BPClient(exchange_config)
        spot_raw = client.get_balance();
        # ... existing code ...
        collateral_raw = client.get_collateral();
        temp_balances = {}
        # ... existing code ...
        if isinstance(spot_raw, dict) and "error" not in spot_raw:
            for asset, details in spot_raw.items():
                try:
                    # ... existing code ...
                    temp_balances[asset] = {'available': Decimal(details.get('available', '0')),
                                            'locked': Decimal(details.get('locked', '0')),
                                            'collateral_available': Decimal('0'), 'collateral_total': Decimal('0')}
                except Exception as e:
                    # ... existing code ...
                    logger.warning(f"解析 BP 现货 {asset} 失败: {e}")
        elif isinstance(spot_raw, dict):
            logger.error(f"获取 BP 现货余额失败: {spot_raw.get('error')}")
        # ... existing code ...
        if isinstance(collateral_raw, dict) and "error" not in collateral_raw:
            for item in collateral_raw.get('assets', []):
                symbol = item.get('symbol')
                # ... existing code ...
                if symbol:
                    try:
                        coll_avail = Decimal(item.get('availableQuantity', '0'));
                        # ... existing code ...
                        coll_total = Decimal(item.get('totalQuantity', '0'))
                        if symbol not in temp_balances: temp_balances[symbol] = {'available': Decimal('0'),
                                                                                 'locked': Decimal('0'),
                                                                                 # ... existing code ...
                                                                                 'collateral_available': Decimal(
                                                                                     '0'),
                                                                                 'collateral_total': Decimal('0')}
                        # ... existing code ...
                        temp_balances[symbol]['collateral_available'] = coll_avail;
                        temp_balances[symbol]['collateral_total'] = coll_total
                    except Exception as e:
                        # ... existing code ...
                        logger.warning(f"解析 BP 抵押品 {symbol} 失败: {e}")
        elif isinstance(collateral_raw, dict):
            logger.warning(f"获取 BP 抵押品失败: {collateral_raw.get('error')}")
        # ... existing code ...
        for asset, details in temp_balances.items():
            available = details.get('available', Decimal('0'));
            # ... existing code ...
            collateral_available = details.get('collateral_available', Decimal('0'));
            locked = details.get('locked', Decimal('0'));
            # ... existing code ...
            collateral_total = details.get('collateral_total', Decimal('0'))
            total_available = available + collateral_available;
            # ... existing code ...
            total_locked = locked;
            total_all = available + locked + collateral_total
            # ... existing code ...
            if total_all > Decimal('1e-9'): response_data["spot_balances"][asset] = {
                "available": _format_balance(str(total_available)), "locked": _format_balance(str(total_locked)),
                "total": _format_balance(str(total_all))}
        # (修正) 将 get_positions 放入 try-except
        # ... existing code ...
        try:
            positions_raw = client.get_positions()
            # ... existing code ...
            if isinstance(positions_raw, list):
                for pos in positions_raw: asset = pos.get('symbol');
                # ... existing code ...
                if asset and asset not in response_data["futures_balances"]: response_data["futures_balances"][
                    asset] = {"available": "N/A", "locked": "N/A", "total": "N/A"}
            # ... existing code ...
            elif isinstance(positions_raw, dict) and positions_raw.get("error") and "404" not in positions_raw.get(
                    "error", ""):
                logger.warning(f"获取 BP 仓位失败: {positions_raw.get('error')}")
        # ... existing code ...
        except Exception as pos_err:
            logger.warning(f"获取 BP 仓位出错: {pos_err}")

        logger.info(f"成功获取 {exchange} 余额信息");
        # ... existing code ...
        return response_data
    # (修正) 添加 except Exception as e:
    except Exception as e:
        # ... existing code ...
        logger.error(f"获取余额时发生意外错误 ({exchange}): {e}", exc_info=True)
        return JSONResponse(status_code=500, content={"error": f"服务器内部错误: {str(e)}"})


@app.post("/api/start_bot")
async def start_bot(config: BotConfig):
    # ... existing code ...
    symbol = config.symbol
    exchange = 'backpack'  # Hardcoded

    if config.market_type == 'perp' and not symbol.endswith('_PERP'):
        # ... existing code ...
        symbol = f"{symbol}_PERP";
        logger.info(f"修正 BP 永续交易对: {config.symbol} -> {symbol}")

    bot_id = f"{symbol}_{config.market_type}"
    # ... existing code ...
    logger.info(f"收到启动请求: {bot_id} (策略: {config.strategy})")
    with _bot_lock:
        if bot_id in RUNNING_BOTS: return JSONResponse(status_code=400, content={"error": f"{bot_id} 已在运行"})

    api_key, secret_key, ws_proxy, base_url = _get_api_credentials()
    # ... existing code ...
    if not api_key or not secret_key: return JSONResponse(status_code=400, content={
        "error": f"未配置 {exchange.upper()} API 密钥"})

    market_maker: Optional[MarketMaker] = None
    # ... existing code ...
    # (修正) 确保整个过程在 try 块内
    try:
        exchange_config = {'api_key': api_key, 'secret_key': secret_key};
        # ... existing code ...
        if base_url: exchange_config['base_url'] = base_url
        db_enabled = ENABLE_DATABASE

        common_args = {"symbol": symbol, "api_key": api_key, "secret_key": secret_key,
                       "base_spread_percentage": config.spread, "order_quantity": config.quantity, "ws_proxy": ws_proxy,
                       # "exchange": config.exchange, # Removed
                       "exchange_config": exchange_config, "enable_database": db_enabled,
                       # --- (新) 传递智能策略参数 ---
                       "stale_threshold_percent": config.stale_threshold_percent,
                       "volatility_config": config.volatility_config,
                       "depth_weights": config.depth_weights
                       }

        if config.market_type == 'perp':
            # ... existing code ...
            perp_args = {**common_args, "target_position": config.target_position, "max_position": config.max_position,
                         "position_threshold": config.position_threshold, "inventory_skew": config.inventory_skew,
                         "stop_loss": config.stop_loss, "take_profit": config.take_profit,
                         # ... existing code ...
                         "max_orders": config.max_orders}
            valid_perp_args = {k: v for k, v in perp_args.items() if v is not None}
            if config.strategy == 'maker_hedge':
                # ... existing code ...
                valid_perp_args.pop("max_orders", None);
                market_maker = MakerTakerHedgeStrategy(**valid_perp_args,
                                                       market_type='perp')
            else:
                # ... existing code ...
                market_maker = PerpetualMarketMaker(**valid_perp_args)
        else:  # spot
            spot_args = {**common_args, "max_orders": config.max_orders, "enable_rebalance": config.enable_rebalance,
                         # ... existing code ...
                         "base_asset_target_percentage": config.base_asset_target,
                         "rebalance_threshold": config.rebalance_threshold}
            valid_spot_args = {k: v for k, v in spot_args.items() if v is not None}
            # ... existing code ...
            if config.strategy == 'maker_hedge':
                valid_spot_args.pop("max_orders", None);
                # ... existing code ...
                valid_spot_args.pop("enable_rebalance", None);
                valid_spot_args.pop("base_asset_target_percentage", None);
                valid_spot_args.pop("rebalance_threshold", None)
                # ... existing code ...
                market_maker = MakerTakerHedgeStrategy(**valid_spot_args, market_type='spot')
            else:
                market_maker = MarketMaker(**valid_spot_args)

        if not market_maker: raise ValueError("无法创建机器人实例")

        # ... existing code ...
        thread = threading.Thread(target=run_bot_thread, args=(market_maker, config.duration, config.interval, bot_id),
                                  daemon=True)
        with _bot_lock:
            # ... existing code ...
            if bot_id in RUNNING_BOTS: return JSONResponse(status_code=400, content={"error": f"{bot_id} 刚刚已被启动"})
            RUNNING_BOTS[bot_id] = market_maker;
            BOT_THREADS[bot_id] = thread
        # ... existing code ...
        thread.start()
        return {"status": "success", "message": f"{bot_id} 已启动"}
    # (修正) 添加 except (TypeError, ValueError) as config_err:
    # ... existing code ...
    except (TypeError, ValueError) as config_err:
        logger.error(f"启动 {bot_id} 配置/初始化错误: {config_err}", exc_info=True)
        return JSONResponse(status_code=400, content={"error": f"配置/初始化错误: {str(config_err)}"})
    # ... existing code ...
    # (修正) 添加 except Exception as e:
    except Exception as e:
        logger.error(f"启动 {bot_id} 未知错误: {e}", exc_info=True)
        # ... existing code ...
        with _bot_lock:
            RUNNING_BOTS.pop(bot_id, None);
            BOT_THREADS.pop(bot_id, None)
        # ... existing code ...
        return JSONResponse(status_code=500, content={"error": f"启动失败: {str(e)}"})


@app.post("/api/stop_bot")
async def stop_bot(request: Request):
    # ... existing code ...
    bot_id: Optional[str] = None
    # (修正) 添加 try-except 块来解析 JSON
    try:
        # ... existing code ...
        data = await request.json()
        bot_id = data.get("bot_id")
    except Exception:
        # ... existing code ...
        return JSONResponse(status_code=400, content={"error": "无效请求体"})

    if not bot_id: return JSONResponse(status_code=400, content={"error": "缺少 'bot_id'"})
    # ... existing code ...
    logger.info(f"收到停止请求: {bot_id}")

    with _bot_lock:
        # ... existing code ...
        market_maker_instance = RUNNING_BOTS.get(bot_id)

    if not market_maker_instance: return {"status": "success", "message": f"{bot_id} 未在运行"}

    # (修正) 添加 try-except 块来调用 stop
    # ... existing code ...
    try:
        if hasattr(market_maker_instance, 'stop') and callable(market_maker_instance.stop):
            market_maker_instance.stop()
            # ... existing code ...
            return {"status": "success", "message": f"已向 {bot_id} 发送停止信号"}
        else:
            logger.error(f"{bot_id} 没有 'stop' 方法！")
            # ... existing code ...
            return JSONResponse(status_code=500, content={"error": "无法停止：代码缺少 stop 方法"})
    # (修正) 添加 except Exception as e:
    except Exception as e:
        # ... existing code ...
        logger.error(f"发送停止信号给 {bot_id} 失败: {e}", exc_info=True)
        return JSONResponse(status_code=500, content={"error": f"停止失败: {str(e)}"})


@app.get("/api/status")
async def get_status():
    # ... existing code ...
    status_list = []
    with _bot_lock:
        running_bots_copy = list(RUNNING_BOTS.items())

    for bot_id, instance in running_bots_copy:
        # ... existing code ...
        bot_data = {"bot_id": bot_id, "symbol": "Unknown", "status": "running", "quote_asset": "USD"}
        # (修正) 将所有属性访问和方法调用放入 try 块
        try:
            # ... existing code ...
            bot_data.update(
                {"symbol": instance.symbol, "quote_asset": instance.quote_asset, "base_asset": instance.base_asset,
                 "session_start_time": instance.session_start_time.isoformat() if instance.session_start_time else None})
            # ... existing code ...
            pnl_data = instance.calculate_pnl()
            if pnl_data and len(pnl_data) == 7:
                (rpnl, upnl, tf, npnl, srpnl, sf, snpnl) = pnl_data
                # ... existing code ...
                bot_data.update(
                    {"session_net_pnl": f"{snpnl:.4f}", "unrealized_pnl": f"{upnl:.4f}", "total_fees": f"{tf:.4f}",
                     "session_realized_pnl": f"{srpnl:.4f}", "session_fees": f"{sf:.4f}"})
            # ... existing code ...
            else:
                logger.warning(f"机器人 {bot_id} PnL 数据格式错误")
                bot_data["status"] = "running (PnL 格式错误)"

            bot_data.update({"trades_executed": getattr(instance, 'trades_executed', 0),
                             # ... existing code ...
                             "total_bought": f"{getattr(instance, 'total_bought', 0):.3f}",
                             "total_sold": f"{getattr(instance, 'total_sold', 0):.3f}"})
        # (修正) 添加 except Exception as e:
        # ... existing code ...
        except Exception as e:
            logger.warning(f"获取 {bot_id} 状态时出错: {e}")
            bot_data["status"] = "running (状态获取失败)"
        # ... existing code ...
        status_list.append(bot_data)
    return {"running_bots": status_list}


# -------------------------------------------------------------------
# 6. 挂载前端文件
# -------------------------------------------------------------------
frontend_dir = "frontend"
# ... existing code ...
index_path = os.path.join(frontend_dir, "index.html")

# (修正) 确保 try-except 覆盖 makedirs 和文件写入
try:
    # ... existing code ...
    if not os.path.exists(frontend_dir):
        os.makedirs(frontend_dir)
        logger.info(f"已创建 '{frontend_dir}' 文件夹")
# (修正) 添加 except OSError as e:
# ... existing code ...
except OSError as e:
    logger.error(f"创建 frontend 文件夹失败: {e}")
    exit(1)

if not os.path.exists(index_path):
    # ... existing code ...
    logger.warning(f"警告: 在 '{frontend_dir}' 文件夹中未找到 'index.html' 文件！")
    # (修正) 将文件写入放入 try-except IOError
    try:
        # ... existing code ...
        # (修正) 使用 with open(...) as f:
        with open(index_path, "w", encoding="utf-8") as f:
            f.write("<h1>请将前端 index.html 文件放入 'frontend' 文件夹</h1>")
        # ... existing code ...
        logger.info(f"已创建临时的 '{index_path}'")
    # (修正) 添加 except IOError as e:
    except IOError as e:
        # ... existing code ...
        logger.error(f"创建临时 index.html 失败: {e}")
    # (修正) 添加通用 except Exception as e:
    except Exception as e:
        # ... existing code ...
        logger.error(f"创建临时 index.html 时发生意外错误: {e}")

# (修正) 确保 StaticFiles 挂载在 try 块外部或有备用方案
try:
    # ... existing code ...
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="static")
except Exception as e:
    logger.critical(f"挂载静态文件目录 '{frontend_dir}' 失败: {e}", exc_info=True)


    # Define a fallback root path handler ONLY if mounting fails
    # ... existing code ...
    @app.get("/")
    async def root_fallback():
        return HTMLResponse(content=f"<h1>错误: 无法提供前端文件</h1><p>错误详情: {e}</p>", status_code=500)

# -------------------------------------------------------------------
# 7. 运行服务器
# -------------------------------------------------------------------
if __name__ == "__main__":
    # ... existing code ...
    logger.info("启动 FastAPI 服务器...")
    print("-----------------------------------------------------")
    print(f"  日志级别: {logging.getLevelName(logger.getEffectiveLevel())}")
    # ... existing code ...
    print("  访问控制面板: http://localhost:8000")
    print("  按 CTRL+C 停止服务器")
    print("-----------------------------------------------------")
    # ... existing code ...
    uvicorn.run("api_server:app", host="0.0.0.0", port=8000, reload=True, log_level="info")
