"""
CLI命令模塊，提供命令行交互功能
"""
import time
import os
from typing import Optional
from datetime import datetime

from api.bp_client import BPClient
# from api.aster_client import AsterClient # Removed
from ws_client.client import BackpackWebSocket
from strategies.market_maker import MarketMaker
from strategies.perp_market_maker import PerpetualMarketMaker
from strategies.maker_taker_hedge import MakerTakerHedgeStrategy
from utils.helpers import calculate_volatility
from database.db import Database
from config import API_KEY, SECRET_KEY, ENABLE_DATABASE
from logger import setup_logger

logger = setup_logger("cli")

# 緩存客户端實例以提高性能
_client_cache = {}
USE_DATABASE = ENABLE_DATABASE


def _resolve_api_credentials(api_key: Optional[str], secret_key: Optional[str]):
    # ... existing code ...
    """根據交易所解析並返回對應的 API/Secret Key。 (Simplified for Backpack only)"""

    api_candidates = [
        # ... existing code ...
        os.getenv("BACKPACK_KEY"),
        os.getenv("API_KEY"),
    ]
    secret_candidates = [
        # ... existing code ...
        os.getenv("BACKPACK_SECRET"),
        os.getenv("SECRET_KEY"),
    ]

    resolved_api_key = next((value for value in api_candidates if value), None) or api_key
    # ... existing code ...
    resolved_secret_key = next((value for value in secret_candidates if value), None) or secret_key

    return resolved_api_key, resolved_secret_key


def _get_client(api_key=None, secret_key=None, exchange_config=None):
    # ... existing code ...
    """獲取緩存的客户端實例，避免重複創建 (Simplified for Backpack only)"""
    exchange = 'backpack'

    config = dict(exchange_config or {})
    # ... existing code ...
    config_api_key = api_key or config.get('api_key')
    config_secret_key = secret_key or config.get('secret_key')

    if config_api_key:
        # ... existing code ...
        config['api_key'] = config_api_key
    else:
        config.pop('api_key', None)

    if config_secret_key:
        # ... existing code ...
        config['secret_key'] = config_secret_key
    else:
        config.pop('secret_key', None)

    cache_suffix = (
        # ... existing code ...
        f"{config.get('api_key', '')}_{config.get('secret_key', '')}"
        if config.get('api_key') or config.get('secret_key')
        else 'public'
    )
    # ... existing code ...
    cache_key = f"{exchange}:{cache_suffix}"

    if cache_key not in _client_cache:
        client_cls = BPClient
        # ... existing code ...
        _client_cache[cache_key] = client_cls(config)

    return _client_cache[cache_key]


def get_address_command(api_key, secret_key):
    # ... existing code ...
    """獲取存款地址命令"""
    blockchain = input("請輸入區塊鏈名稱(Solana, Ethereum, Bitcoin等): ")
    result = _get_client(api_key, secret_key).get_deposit_address(blockchain)
    # ... existing code ...
    print(result)


def get_balance_command(api_key, secret_key):
    # ... existing code ...
    """獲取餘額命令"""
    c = _get_client(api_key, secret_key)
    balances = c.get_balance()
    # ... existing code ...
    collateral = c.get_collateral()
    if isinstance(balances, dict) and "error" in balances and balances["error"]:
        print(f"獲取餘額失敗: {balances['error']}")
    # ... existing code ...
    else:
        print("\n當前餘額:")
        if isinstance(balances, dict):
            # ... existing code ...
            for coin, details in balances.items():
                if float(details.get('available', 0)) > 0 or float(details.get('locked', 0)) > 0:
                    print(f"{coin}: 可用 {details.get('available', 0)}, 凍結 {details.get('locked', 0)}")
        # ... existing code ...
        else:
            print(f"獲取餘額失敗: 無法識別返回格式 {type(balances)}")

    if isinstance(collateral, dict) and "error" in collateral:
        # ... existing code ...
        print(f"獲取抵押品失敗: {collateral['error']}")
    elif isinstance(collateral, dict):
        assets = collateral.get('assets') or collateral.get('collateral', [])
        # ... existing code ...
        if assets:
            print("\n抵押品資產:")
            for item in assets:
                # ... existing code ...
                symbol = item.get('symbol', '')
                total = item.get('totalQuantity', '')
                available = item.get('availableQuantity', '')
                # ... existing code ...
                lend = item.get('lendQuantity', '')
                collateral_value = item.get('collateralValue', '')
                print(f"{symbol}: 總量 {total}, 可用 {available}, 出借中 {lend}, 抵押價值 {collateral_value}")


def get_markets_command():
    # ... existing code ...
    """獲取市場信息命令"""
    print("\n獲取市場信息...")
    markets_info = _get_client().get_markets()

    if isinstance(markets_info, dict) and "error" in markets_info:
        # ... existing code ...
        print(f"獲取市場信息失敗: {markets_info['error']}")
        return

    spot_markets = [m for m in markets_info if m.get('marketType') == 'SPOT']
    # ... existing code ...
    print(f"\n找到 {len(spot_markets)} 個現貨市場:")
    for i, market in enumerate(spot_markets):
        symbol = market.get('symbol')
        # ... existing code ...
        base = market.get('baseSymbol')
        quote = market.get('quoteSymbol')
        market_type = market.get('marketType')
        # ... existing code ...
        print(f"{i + 1}. {symbol} ({base}/{quote}) - {market_type}")


def get_orderbook_command(api_key, secret_key, ws_proxy=None):
    # ... existing code ...
    """獲取市場深度命令"""
    symbol = input("請輸入交易對 (例如: SOL_USDC): ")
    try:
        # ... existing code ...
        print("連接WebSocket獲取實時訂單簿...")
        ws = BackpackWebSocket(api_key, secret_key, symbol, auto_reconnect=True, proxy=ws_proxy)
        ws.connect()

        # 等待連接建立
        # ... existing code ...
        wait_time = 0
        max_wait_time = 5
        while not ws.connected and wait_time < max_wait_time:
            # ... existing code ...
            time.sleep(0.5)
            wait_time += 0.5

        if not ws.connected:
            # ... existing code ...
            print("WebSocket連接超時，使用REST API獲取訂單簿")
            depth = _get_client().get_order_book(symbol)
        else:
            # ... existing code ...
            # 初始化訂單簿並訂閲深度流
            ws.initialize_orderbook()
            ws.subscribe_depth()

            # 等待數據更新
            # ... existing code ...
            time.sleep(2)
            depth = ws.get_orderbook()

        print("\n訂單簿:")
        # ... existing code ...
        print("\n賣單 (從低到高):")
        if 'asks' in depth and depth['asks']:
            asks = sorted(depth['asks'], key=lambda x: x[0])[:10]  # 多展示幾個深度
            # ... existing code ...
            for i, (price, quantity) in enumerate(asks):
                print(f"{i + 1}. 價格: {price}, 數量: {quantity}")
        else:
            # ... existing code ...
            print("無賣單數據")

        print("\n買單 (從高到低):")
        # ... existing code ...
        if 'bids' in depth and depth['bids']:
            bids = sorted(depth['bids'], key=lambda x: x[0], reverse=True)[:10]  # 多展示幾個深度
            # ... existing code ...
            for i, (price, quantity) in enumerate(bids):
                print(f"{i + 1}. 價格: {price}, 數量: {quantity}")
        else:
            # ... existing code ...
            print("無買單數據")

        # 分析市場情緒
        if ws.connected:
            # ... existing code ...
            liquidity_profile = ws.get_liquidity_profile()
            if liquidity_profile:
                buy_volume = liquidity_profile['bid_volume']
                # ... existing code ...
                sell_volume = liquidity_profile['ask_volume']
                imbalance = liquidity_profile['imbalance']

                print("\n市場流動性分析:")
                # ... existing code ...
                print(f"買單量: {buy_volume:.4f}")
                print(f"賣單量: {sell_volume:.4f}")
                print(f"買賣比例: {(buy_volume / sell_volume):.2f}") if sell_volume > 0 else print("買賣比例: 無限")

                # 判斷市場情緒
                # ... existing code ...
                sentiment = "買方壓力較大" if imbalance > 0.2 else "賣方壓力較大" if imbalance < -0.2 else "買賣壓力平衡"
                print(f"市場情緒: {sentiment} ({imbalance:.2f})")

        # 關閉WebSocket連接
        # ... existing code ...
        ws.close()

    except Exception as e:
        print(f"獲取訂單簿失敗: {str(e)}")
        # ... existing code ...
        # 嘗試使用REST API
        try:
            depth = _get_client().get_order_book(symbol)
            # ... existing code ...
            if isinstance(depth, dict) and "error" in depth:
                print(f"獲取訂單簿失敗: {depth['error']}")
                return

            print("\n訂單簿 (REST API):")
            # ... existing code ...
            print("\n賣單 (從低到高):")
            if 'asks' in depth and depth['asks']:
                asks = sorted([
                    # ... existing code ...
                    [float(price), float(quantity)] for price, quantity in depth['asks']
                ], key=lambda x: x[0])[:10]
                for i, (price, quantity) in enumerate(asks):
                    # ... existing code ...
                    print(f"{i + 1}. 價格: {price}, 數量: {quantity}")
            else:
                print("無賣單數據")

            print("\n買單 (從高到低):")
            # ... existing code ...
            if 'bids' in depth and depth['bids']:
                bids = sorted([
                    [float(price), float(quantity)] for price, quantity in depth['bids']
                    # ... existing code ...
                ], key=lambda x: x[0], reverse=True)[:10]
                for i, (price, quantity) in enumerate(bids):
                    # ... existing code ...
                    print(f"{i + 1}. 價格: {price}, 數量: {quantity}")
            else:
                print("無買單數據")
        # ... existing code ...
        except Exception as e:
            print(f"使用REST API獲取訂單簿也失敗: {str(e)}")


def configure_rebalance_settings():
    # ... existing code ...
    """配置重平設置"""
    print("\n=== 重平設置配置 ===")

    # 是否開啟重平功能
    # ... existing code ...
    while True:
        enable_input = input("是否開啟重平功能? (y/n，默認: y): ").strip().lower()
        if enable_input in ['', 'y', 'yes']:
            # ... existing code ...
            enable_rebalance = True
            break
        elif enable_input in ['n', 'no']:
            # ... existing code ...
            enable_rebalance = False
            break
        else:
            # ... existing code ...
            print("請輸入 y 或 n")

    base_asset_target_percentage = 30.0  # 默認值
    # ... existing code ...
    rebalance_threshold = 15.0  # 默認值

    if enable_rebalance:
        # 設置基礎資產目標比例
        # ... existing code ...
        while True:
            try:
                percentage_input = input("請輸入基礎資產目標比例 (0-100，默認: 30): ").strip()
                # ... existing code ...
                if percentage_input == '':
                    base_asset_target_percentage = 30.0
                    break
                # ... existing code ...
                else:
                    percentage = float(percentage_input)
                    if 0 <= percentage <= 100:
                        # ... existing code ...
                        base_asset_target_percentage = percentage
                        break
                    else:
                        # ... existing code ...
                        print("比例必須在 0-100 之間")
            except ValueError:
                print("請輸入有效的數字")

        # 設置重平觸發閾值
        # ... existing code ...
        while True:
            try:
                threshold_input = input("請輸入重平觸發閾值 (>0，默認: 15): ").strip()
                # ... existing code ...
                if threshold_input == '':
                    rebalance_threshold = 15.0
                    break
                # ... existing code ...
                else:
                    threshold = float(threshold_input)
                    if threshold > 0:
                        # ... existing code ...
                        rebalance_threshold = threshold
                        break
                    else:
                        # ... existing code ...
                        print("閾值必須大於 0")
            except ValueError:
                print("請輸入有效的數字")

        quote_asset_target_percentage = 100.0 - base_asset_target_percentage

        print(f"\n重平設置:")
        # ... existing code ...
        print(f"重平功能: 開啟")
        print(f"目標比例: {base_asset_target_percentage}% 基礎資產 / {quote_asset_target_percentage}% 報價資產")
        print(f"觸發閾值: {rebalance_threshold}%")
    # ... existing code ...
    else:
        print(f"\n重平設置:")
        print(f"重平功能: 關閉")

    return enable_rebalance, base_asset_target_percentage, rebalance_threshold


def run_market_maker_command(api_key, secret_key, ws_proxy=None):
    # ... existing code ...
    """執行做市策略命令"""
    # [整合功能] 1. 增加交易所選擇 (Removed)
    # exchange_input = input("請選擇交易所 (backpack/aster，默認 backpack): ").strip().lower()
    exchange = 'backpack'  # Hardcoded
    # ... existing code ...
    print(f"已選擇交易所: {exchange}")

    # [整合功能] 2. 根據選擇配置交易所信息
    api_key, secret_key = _resolve_api_credentials(api_key, secret_key)

    if not api_key or not secret_key:
        # ... existing code ...
        print("錯誤：未找到 Backpack API Key 或 Secret Key，請先設置環境變數或配置檔案。")
        return

    exchange_config = {
        # ... existing code ...
        'api_key': api_key,
        'secret_key': secret_key,
        'base_url': os.getenv('BASE_URL', 'https://api.backpack.work'),
        # ... existing code ...
        'api_version': 'v1',
        'default_window': '5000'
    }

    market_type_input = input("請選擇市場類型 (spot/perp，默認 spot): ").strip().lower()
    # ... existing code ...
    market_type = market_type_input if market_type_input in ("spot", "perp") else "spot"

    strategy_input = input("請選擇策略 (standard/maker_hedge，默認 standard): ").strip().lower()
    # ... existing code ...
    strategy = strategy_input if strategy_input in ("standard", "maker_hedge") else "standard"
    print(f"已選擇策略: {strategy}")

    symbol = input("請輸入要做市的交易對 (例如: SOL_USDC): ")
    # ... existing code ...
    client = _get_client(exchange_config=exchange_config)
    market_limits = client.get_market_limits(symbol)
    if not market_limits:
        # ... existing code ...
        print(f"交易對 {symbol} 不存在或不可交易")
        return

    base_asset = market_limits.get('base_asset') or symbol
    # ... existing code ...
    quote_asset = market_limits.get('quote_asset') or ''
    market_desc = f"{symbol}" if not quote_asset else f"{symbol} ({base_asset}/{quote_asset})"

    if market_type == "spot":
        # ... existing code ...
        print(f"已選擇現貨市場 {market_desc}")
    else:
        print(f"已選擇永續合約市場 {market_desc}")

    spread_percentage = float(input("請輸入價差百分比 (例如: 0.5 表示0.5%): "))
    # ... existing code ...
    quantity_input = input("請輸入每個訂單的數量 (留空則自動根據餘額計算): ")
    quantity = float(quantity_input) if quantity_input.strip() else None
    max_orders = int(input("請輸入每側(買/賣)最大訂單數 (例如: 3): "))

    # (新) 智能策略参数
    stale_threshold_input = input("(智能策略) 請輸入過時訂單閾值 (百分比, 例如 0.5, 留空使用默認值): ").strip()
    stale_threshold = float(stale_threshold_input) if stale_threshold_input else None

    if market_type == "perp":
        try:
            # ... existing code ...
            target_position_input = input("請輸入目標持倉量 (絕對值, 例如 1.0, 默認 1): ").strip()
            target_position = float(target_position_input) if target_position_input else 1.0

            max_position_input = input("最大允許持倉量(絕對值) (默認 1.0): ").strip()
            # ... existing code ...
            max_position = float(max_position_input) if max_position_input else 1.0

            threshold_input = input("倉位調整觸發值 (默認 0.1): ").strip()
            # ... existing code ...
            position_threshold = float(threshold_input) if threshold_input else 0.1

            skew_input = input("倉位偏移調整係數 (0-1，默認 0.0): ").strip()
            # ... existing code ...
            inventory_skew = float(skew_input) if skew_input else 0.0

            stop_loss_input = input("未實現止損閾值 (報價資產金額，支援輸入負值，例如 -25，留空不啟用): ").strip()
            # ... existing code ...
            stop_loss = float(stop_loss_input) if stop_loss_input else None

            take_profit_input = input("未實現止盈閾值 (報價資產金額，留空不啟用): ").strip()
            # ... existing code ...
            take_profit = float(take_profit_input) if take_profit_input else None

            if max_position <= 0:
                # ... existing code ...
                raise ValueError("最大持倉量必須大於0")
            if position_threshold <= 0:
                raise ValueError("倉位調整觸發值必須大於0")
            # ... existing code ...
            if not 0 <= inventory_skew <= 1:
                raise ValueError("倉位偏移調整係數需介於0-1之間")
            if stop_loss is not None:
                # ... existing code ...
                if stop_loss >= 0:
                    raise ValueError("止損閾值必須輸入負值 (例如 -25)")
            if take_profit is not None and take_profit <= 0:
                # ... existing code ...
                raise ValueError("止盈閾值必須大於0")
        except ValueError as exc:
            print(f"倉位參數輸入錯誤: {exc}")
            # ... existing code ...
            return

        enable_rebalance = False
        base_asset_target_percentage = 0.0
        # ... existing code ...
        rebalance_threshold = 0.0
    else:
        if strategy == "maker_hedge":
            enable_rebalance = False
            # ... existing code ...
            base_asset_target_percentage = 0.0
            rebalance_threshold = 0.0
        else:
            # ... existing code ...
            enable_rebalance, base_asset_target_percentage, rebalance_threshold = configure_rebalance_settings()
        target_position = 0.0
        max_position = 0.0
        # ... existing code ...
        position_threshold = 0.0
        inventory_skew = 0.0
        stop_loss = None
        # ... existing code ...
        take_profit = None

    duration = int(input("請輸入運行時間(秒) (例如: 3600 表示1小時): "))
    interval = int(input("請輸入更新間隔(秒) (例如: 60 表示1分鐘): "))

    if not USE_DATABASE:
        # ... existing code ...
        print("提示: 資料庫寫入已停用，本次執行僅在記憶體中追蹤統計。")

    db = None
    try:
        # ... existing code ...
        if USE_DATABASE:
            db = Database()
        # 原有的 exchange_config 創建邏輯已被新的動態配置取代

        if market_type == "perp":
            # ... existing code ...
            if strategy == "maker_hedge":
                market_maker = MakerTakerHedgeStrategy(
                    api_key=api_key,
                    # ... existing code ...
                    secret_key=secret_key,
                    symbol=symbol,
                    db_instance=db if USE_DATABASE else None,
                    # ... existing code ...
                    base_spread_percentage=spread_percentage,
                    order_quantity=quantity,
                    target_position=target_position,
                    # ... existing code ...
                    max_position=max_position,
                    position_threshold=position_threshold,
                    inventory_skew=inventory_skew,
                    # ... existing code ...
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    ws_proxy=ws_proxy,
                    # ... existing code ...
                    # exchange=exchange, # Removed
                    # exchange_config=exchange_config, # Removed
                    enable_database=USE_DATABASE,
                    market_type="perp",
                    # (新) 传递智能策略参数
                    stale_threshold_percent=stale_threshold
                )
            else:
                market_maker = PerpetualMarketMaker(
                    # ... existing code ...
                    api_key=api_key,
                    secret_key=secret_key,
                    symbol=symbol,
                    # ... existing code ...
                    db_instance=db if USE_DATABASE else None,
                    base_spread_percentage=spread_percentage,
                    order_quantity=quantity,
                    # ... existing code ...
                    max_orders=max_orders,
                    target_position=target_position,
                    max_position=max_position,
                    # ... existing code ...
                    position_threshold=position_threshold,
                    inventory_skew=inventory_skew,
                    stop_loss=stop_loss,
                    # ... existing code ...
                    take_profit=take_profit,
                    ws_proxy=ws_proxy,
                    # exchange=exchange, # Removed
                    # ... existing code ...
                    # exchange_config=exchange_config, # Removed
                    enable_database=USE_DATABASE,
                    # (新) 传递智能策略参数
                    stale_threshold_percent=stale_threshold
                )
        else:
            if strategy == "maker_hedge":
                # ... existing code ...
                market_maker = MakerTakerHedgeStrategy(
                    api_key=api_key,
                    secret_key=secret_key,
                    # ... existing code ...
                    symbol=symbol,
                    db_instance=db if USE_DATABASE else None,
                    base_spread_percentage=spread_percentage,
                    # ... existing code ...
                    order_quantity=quantity,
                    ws_proxy=ws_proxy,
                    # exchange=exchange, # Removed
                    # ... existing code ...
                    # exchange_config=exchange_config, # Removed
                    enable_database=USE_DATABASE,
                    market_type="spot",
                    # (新) 传递智能策略参数
                    stale_threshold_percent=stale_threshold
                )
            else:
                market_maker = MarketMaker(
                    # ... existing code ...
                    api_key=api_key,
                    secret_key=secret_key,
                    symbol=symbol,
                    # ... existing code ...
                    db_instance=db if USE_DATABASE else None,
                    base_spread_percentage=spread_percentage,
                    order_quantity=quantity,
                    # ... existing code ...
                    max_orders=max_orders,
                    enable_rebalance=enable_rebalance,
                    base_asset_target_percentage=base_asset_target_percentage,
                    # ... existing code ...
                    rebalance_threshold=rebalance_threshold,
                    ws_proxy=ws_proxy,
                    # exchange=exchange, # Removed
                    # ... existing code ...
                    # exchange_config=exchange_config, # Removed
                    enable_database=USE_DATABASE,
                    # (新) 传递智能策略参数
                    stale_threshold_percent=stale_threshold
                )

        market_maker.run(duration_seconds=duration, interval_seconds=interval)

    # ... existing code ...
    except Exception as e:
        print(f"做市過程中發生錯誤: {str(e)}")
        import traceback
        # ... existing code ...
        traceback.print_exc()
    finally:
        if db is not None:
            # ... existing code ...
            try:
                db.close()
            except Exception:
                # ... existing code ...
                pass


def rebalance_settings_command():
    # ... existing code ...
    """重平設置管理命令"""
    print("\n=== 重平設置管理 ===")
    print("1 - 查看重平設置説明")
    # ... existing code ...
    print("2 - 測試重平設置")
    print("3 - 返回主菜單")

    choice = input("請選擇操作: ")

    if choice == '1':
        # ... existing code ...
        print("\n=== 重平設置説明 ===")
        print("重平功能用於保持資產配置的平衡，避免因市場波動導致的資產比例失衡。")
        print("\n主要參數:")
        # ... existing code ...
        print("1. 重平功能開關: 控制是否啟用自動重平衡")
        print("2. 基礎資產目標比例: 基礎資產應佔總資產的百分比 (0-100%)")
        print("3. 重平觸發閾值: 當實際比例偏離目標比例超過此閾值時觸發重平衡")
        # ... existing code ...
        print("\n範例:")
        print("- 目標比例 30%: 假設總資產價值 1000 USDC，則理想基礎資產價值為 300 USDC")
        print("- 觸發閾值 15%: 當偏差超過總資產的 15% 時觸發重平衡")
        # ... existing code ...
        print("- 如果基礎資產價值變為 450 USDC，偏差為 150 USDC (15%)，將觸發重平衡")
        print("\n注意事項:")
        print("- 重平衡會產生交易手續費")
        # ... existing code ...
        print("- 過低的閾值可能導致頻繁重平衡")
        print("- 過高的閾值可能無法及時控制風險")

    elif choice == '2':
        # ... existing code ...
        print("\n=== 測試重平設置 ===")
        enable_rebalance, base_asset_target_percentage, rebalance_threshold = configure_rebalance_settings()

        # 模擬計算示例
        # ... existing code ...
        if enable_rebalance:
            print(f"\n=== 模擬計算示例 ===")
            total_assets = 1000  # 假設總資產 1000 USDC
            # ... existing code ...
            ideal_base_value = total_assets * (base_asset_target_percentage / 100)
            quote_asset_target_percentage = 100 - base_asset_target_percentage

            print(f"假設總資產: {total_assets} USDC")
            # ... existing code ...
            print(f"理想基礎資產價值: {ideal_base_value} USDC ({base_asset_target_percentage}%)")
            print(f"理想報價資產價值: {total_assets - ideal_base_value} USDC ({quote_asset_target_percentage}%)")
            print(f"重平觸發閾值: {rebalance_threshold}% = {total_assets * (rebalance_threshold / 100)} USDC")

            # 示例偏差情況
            # ... existing code ...
            print(f"\n觸發重平衡的情況示例:")
            trigger_amount = total_assets * (rebalance_threshold / 100)
            high_threshold = ideal_base_value + trigger_amount
            # ... existing code ...
            low_threshold = ideal_base_value - trigger_amount

            print(f"- 當基礎資產價值 > {high_threshold:.2f} USDC 時，將賣出基礎資產")
            print(f"- 當基礎資產價值 < {low_threshold:.2f} USDC 時，將買入基礎資產")
            # ... existing code ...
            print(f"- 在 {low_threshold:.2f} - {high_threshold:.2f} USDC 範圍內不會觸發重平衡")

    elif choice == '3':
        return
    # ... existing code ...
    else:
        print("無效選擇")


def trading_stats_command(api_key, secret_key):
    # ... existing code ...
    """查看交易統計命令"""
    if not USE_DATABASE:
        print("資料庫功能已關閉，無法查詢交易統計。請啟用資料庫後再試。")
        # ... existing code ...
        return

    symbol = input("請輸入要查看統計的交易對 (例如: SOL_USDC): ")

    try:
        # ... existing code ...
        # 初始化數據庫
        db = Database()

        # 獲取今日統計
        # ... existing code ...
        today = datetime.now().strftime('%Y-%m-%d')
        today_stats = db.get_trading_stats(symbol, today)

        print("\n=== 做市商交易統計 ===")
        # ... existing code ...
        print(f"交易對: {symbol}")

        if today_stats and len(today_stats) > 0:
            stat = today_stats[0]
            # ... existing code ...
            maker_buy = stat['maker_buy_volume']
            maker_sell = stat['maker_sell_volume']
            taker_buy = stat['taker_buy_volume']
            # ... existing code ...
            taker_sell = stat['taker_sell_volume']
            profit = stat['realized_profit']
            fees = stat['total_fees']
            # ... existing code ...
            net = stat['net_profit']
            avg_spread = stat.get('avg_spread', 0)
            volatility = stat.get('volatility', 0)

            total_volume = maker_buy + maker_sell + taker_buy + taker_sell
            # ... existing code ...
            maker_percentage = ((maker_buy + maker_sell) / total_volume * 100) if total_volume > 0 else 0

            print(f"\n今日統計 ({today}):")
            print(f"總成交量: {total_volume}")
            # ... existing code ...
            print(f"Maker買入量: {maker_buy}")
            print(f"Maker賣出量: {maker_sell}")
            print(f"Taker買入量: {taker_buy}")
            # ... existing code ...
            print(f"Taker賣出量: {taker_sell}")
            print(f"Maker佔比: {maker_percentage:.2f}%")
            print(f"平均價差: {avg_spread:.4f}%")
            # ... existing code ...
            print(f"波動率: {volatility:.4f}%")
            print(f"毛利潤: {profit:.8f}")
            print(f"總手續費: {fees:.8f}")
            # ... existing code ...
            print(f"凈利潤: {net:.8f}")
        else:
            print(f"今日沒有 {symbol} 的交易記錄")

        # 獲取所有時間的統計
        # ... existing code ...
        all_time_stats = db.get_all_time_stats(symbol)

        if all_time_stats:
            maker_buy = all_time_stats['total_maker_buy']
            # ... existing code ...
            maker_sell = all_time_stats['total_maker_sell']
            taker_buy = all_time_stats['total_taker_buy']
            taker_sell = all_time_stats['total_taker_sell']
            # ... existing code ...
            profit = all_time_stats['total_profit']
            fees = all_time_stats['total_fees']
            net = all_time_stats['total_net_profit']
            # ... existing code ...
            avg_spread = all_time_stats.get('avg_spread_all_time', 0)

            total_volume = maker_buy + maker_sell + taker_buy + taker_sell
            maker_percentage = ((maker_buy + maker_sell) / total_volume * 100) if total_volume > 0 else 0

            print(f"\n累計統計:")
            # ... existing code ...
            print(f"總成交量: {total_volume}")
            print(f"Maker買入量: {maker_buy}")
            print(f"Maker賣出量: {maker_sell}")
            # ... existing code ...
            print(f"Taker買入量: {taker_buy}")
            print(f"Taker賣出量: {taker_sell}")
            print(f"Maker佔比: {maker_percentage:.2f}%")
            # ... existing code ...
            print(f"平均價差: {avg_spread:.4f}%")
            print(f"毛利潤: {profit:.8f}")
            print(f"總手續費: {fees:.8f}")
            # ... existing code ...
            print(f"凈利潤: {net:.8f}")
        else:
            print(f"沒有 {symbol} 的歷史交易記錄")

        # 獲取最近交易
        # ... existing code ...
        recent_trades = db.get_recent_trades(symbol, 10)

        if recent_trades and len(recent_trades) > 0:
            print("\n最近10筆成交:")
            # ... existing code ...
            for i, trade in enumerate(recent_trades):
                maker_str = "Maker" if trade['maker'] else "Taker"
                print(
                    # ... existing code ...
                    f"{i + 1}. {trade['timestamp']} - {trade['side']} {trade['quantity']} @ {trade['price']} ({maker_str}) 手續費: {trade['fee']:.8f}")
        else:
            print(f"沒有 {symbol} 的最近成交記錄")

        # 關閉數據庫連接
        # ... existing code ...
        db.close()

    except Exception as e:
        print(f"查看交易統計時發生錯誤: {str(e)}")
        # ... existing code ...
        import traceback
        traceback.print_exc()


def toggle_database_command():
    # ... existing code ...
    """互動式切換資料庫寫入功能"""
    global USE_DATABASE

    status_text = "開啟" if USE_DATABASE else "關閉"
    # ... existing code ...
    print(f"當前資料庫寫入狀態: {status_text}")

    choice = input("是否要啟用資料庫寫入? (y=啟用, n=停用, Enter=維持原狀): ").strip().lower()

    if choice == "":
        # ... existing code ...
        print("設定未變更。")
        return

    if choice in ("y", "yes", "是"):
        # ... existing code ...
        if USE_DATABASE:
            print("資料庫寫入已經是開啟狀態。")
            return

        try:
            # ... existing code ...
            db = Database()
            db.close()
            USE_DATABASE = True
            # ... existing code ...
            print("已啟用資料庫寫入，後續操作將紀錄交易資訊。")
        except Exception as exc:
            print(f"啟用資料庫寫入失敗: {exc}")
            # ... existing code ...
            print("請確認資料庫設定後再嘗試。")
    elif choice in ("n", "no", "否"):
        if not USE_DATABASE:
            # ... existing code ...
            print("資料庫寫入已經是關閉狀態。")
        else:
            USE_DATABASE = False
            # ... existing code ...
            print("已停用資料庫寫入，僅保留記憶體內統計資料。")
    else:
        print("輸入無效，設定未變更。")


def market_analysis_command(api_key, secret_key, ws_proxy=None):
    # ... existing code ...
    """市場分析命令"""
    symbol = input("請輸入要分析的交易對 (例如: SOL_USDC): ")
    try:
        # ... existing code ...
        print("\n執行市場分析...")

        # 創建臨時WebSocket連接
        ws = BackpackWebSocket(api_key, secret_key, symbol, auto_reconnect=True, proxy=ws_proxy)
        # ... existing code ...
        ws.connect()

        # 等待連接建立
        wait_time = 0
        # ... existing code ...
        max_wait_time = 5
        while not ws.connected and wait_time < max_wait_time:
            time.sleep(0.5)
            # ... existing code ...
            wait_time += 0.5

        if not ws.connected:
            print("WebSocket連接超時，無法進行完整分析")
        # ... existing code ...
        else:
            # 初始化訂單簿
            ws.initialize_orderbook()

            # 訂閲必要數據流
            # ... existing code ...
            ws.subscribe_depth()
            ws.subscribe_bookTicker()

            # 等待數據更新
            # ... existing code ...
            print("等待數據更新...")
            time.sleep(3)

            # 獲取K線數據分析趨勢
            # ... existing code ...
            print("獲取歷史數據分析趨勢...")
            klines = _get_client().get_klines(symbol, "15m")

            # 添加調試信息查看數據結構
            # ... existing code ...
            print("K線數據結構: ")
            if isinstance(klines, dict) and "error" in klines:
                print(f"獲取K線數據出錯: {klines['error']}")
            # ... existing code ...
            else:
                print(f"收到 {len(klines) if isinstance(klines, list) else type(klines)} 條K線數據")

                # 檢查第一條記錄以確定結構
                # ... existing code ...
                if isinstance(klines, list) and len(klines) > 0:
                    print(f"第一條K線數據: {klines[0]}")

                    # 根據實際結構提取收盤價
                    # ... existing code ...
                    try:
                        if isinstance(klines[0], dict):
                            if 'close' in klines[0]:
                                # ... existing code ...
                                # 如果是包含'close'字段的字典
                                prices = [float(kline['close']) for kline in klines]
                            elif 'c' in klines[0]:
                                # ... existing code ...
                                # 另一種常見格式
                                prices = [float(kline['c']) for kline in klines]
                            else:
                                # ... existing code ...
                                print(f"無法識別的字典K線格式，可用字段: {list(klines[0].keys())}")
                                raise ValueError("無法識別的K線數據格式")
                        elif isinstance(klines[0], list):
                            # ... existing code ...
                            # 如果是列表格式，打印元素數量和數據樣例
                            print(f"K線列表格式，每條記錄有 {len(klines[0])} 個元素")
                            if len(klines[0]) >= 5:
                                # ... existing code ...
                                # 通常第4或第5個元素是收盤價
                                try:
                                    # 嘗試第4個元素 (索引3)
                                    # ... existing code ...
                                    prices = [float(kline[3]) for kline in klines]
                                    print("使用索引3作為收盤價")
                                except (ValueError, IndexError):
                                    # ... existing code ...
                                    # 如果失敗，嘗試第5個元素 (索引4)
                                    prices = [float(kline[4]) for kline in klines]
                                    print("使用索引4作為收盤價")
                            # ... existing code ...
                            else:
                                print("K線記錄元素數量不足")
                                raise ValueError("K線數據格式不兼容")
                        # ... existing code ...
                        else:
                            print(f"未知的K線數據類型: {type(klines[0])}")
                            raise ValueError("未知的K線數據類型")

                        # 計算移動平均
                        # ... existing code ...
                        short_ma = sum(prices[-5:]) / 5 if len(prices) >= 5 else sum(prices) / len(prices)
                        medium_ma = sum(prices[-20:]) / 20 if len(prices) >= 20 else short_ma
                        long_ma = sum(prices[-50:]) / 50 if len(prices) >= 50 else medium_ma

                        # 判斷趨勢
                        # ... existing code ...
                        trend = "上漲" if short_ma > medium_ma > long_ma else "下跌" if short_ma < medium_ma < long_ma else "盤整"

                        # 計算波動率
                        volatility = calculate_volatility(prices)

                        print("\n市場趨勢分析:")
                        # ... existing code ...
                        print(f"短期均價 (5週期): {short_ma:.6f}")
                        print(f"中期均價 (20週期): {medium_ma:.6f}")
                        print(f"長期均價 (50週期): {long_ma:.6f}")
                        # ... existing code ...
                        print(f"當前趨勢: {trend}")
                        print(f"波動率: {volatility:.2f}%")

                        # 獲取最新價格和波動性指標
                        # ... existing code ...
                        current_price = ws.get_current_price()
                        liquidity_profile = ws.get_liquidity_profile()

                        if current_price and liquidity_profile:
                            # ... existing code ...
                            print(f"\n當前價格: {current_price}")
                            print(f"相對長期均價: {(current_price / long_ma - 1) * 100:.2f}%")

                            # 流動性分析
                            # ... existing code ...
                            buy_volume = liquidity_profile['bid_volume']
                            sell_volume = liquidity_profile['ask_volume']
                            imbalance = liquidity_profile['imbalance']

                            print("\n市場流動性分析:")
                            # ... existing code ...
                            print(f"買單量: {buy_volume:.4f}")
                            print(f"賣單量: {sell_volume:.4f}")
                            print(
                                # ... existing code ...
                                f"買賣比例: {(buy_volume / sell_volume):.2f}" if sell_volume > 0 else "買賣比例: 無限")

                            # 判斷市場情緒
                            sentiment = "買方壓力較大" if imbalance > 0.2 else "賣方壓力較大" if imbalance < -0.2 else "買賣壓力平衡"
                            # ... existing code ...
                            print(f"市場情緒: {sentiment} ({imbalance:.2f})")

                            # 給出建議的做市參數
                            print("\n建議做市參數:")

                            # 根據波動率調整價差
                            # ... existing code ...
                            suggested_spread = max(0.2, min(2.0, volatility * 0.2))
                            print(f"建議價差: {suggested_spread:.2f}%")

                            # 根據流動性調整訂單數量
                            # ... existing code ...
                            liquidity_score = (buy_volume + sell_volume) / 2
                            orders_suggestion = 3
                            if liquidity_score > 10:
                                # ... existing code ...
                                orders_suggestion = 5
                            elif liquidity_score < 1:
                                orders_suggestion = 2
                            # ... existing code ...
                            print(f"建議訂單數: {orders_suggestion}")

                            # 根據趨勢和情緒建議執行模式
                            if trend == "上漲" and imbalance > 0:
                                # ... existing code ...
                                mode = "adaptive"
                                print("建議執行模式: 自適應模式 (跟隨上漲趨勢)")
                            elif trend == "下跌" and imbalance < 0:
                                # ... existing code ...
                                mode = "passive"
                                print("建議執行模式: 被動模式 (降低下跌風險)")
                            else:
                                # ... existing code ...
                                mode = "standard"
                                print("建議執行模式: 標準模式")

                            # 建議重平設置
                            # ... existing code ...
                            print("\n建議重平設置:")
                            if volatility > 5:
                                print("高波動率市場，建議:")
                                # ... existing code ...
                                print("- 基礎資產比例: 20-25% (降低風險暴露)")
                                print("- 重平閾值: 10-12% (更頻繁重平衡)")
                            elif volatility > 2:
                                # ... existing code ...
                                print("中等波動率市場，建議:")
                                print("- 基礎資產比例: 25-35% (標準配置)")
                                print("- 重平閾值: 12-18% (適中頻率)")
                            # ... existing code ...
                            else:
                                print("低波動率市場，建議:")
                                print("- 基礎資產比例: 30-40% (可承受更高暴露)")
                                # ... existing code ...
                                print("- 重平閾值: 15-25% (較少重平衡)")
                    except Exception as e:
                        print(f"處理K線數據時出錯: {e}")
                        # ... existing code ...
                        import traceback
                        traceback.print_exc()
                else:
                    # ... existing code ...
                    print("未收到有效的K線數據")

        # 關閉WebSocket連接
        if ws:
            # ... existing code ...
            ws.close()

    except Exception as e:
        print(f"市場分析時發生錯誤: {str(e)}")
        # ... existing code ...
        import traceback
        traceback.print_exc()


def main_cli(api_key=API_KEY, secret_key=SECRET_KEY, ws_proxy=None, enable_database=ENABLE_DATABASE):
    # ... existing code ...
    """主CLI函數"""
    global USE_DATABASE
    USE_DATABASE = bool(enable_database)

    if not USE_DATABASE:
        # ... existing code ...
        print("提示: 資料庫寫入功能已關閉，統計與歷史查詢功能將不可用。")

    while True:
        print("\n===== Backpack Exchange 交易程序 =====")
        # ... existing code ...
        print("1 - 查詢存款地址")
        print("2 - 查詢餘額")
        print("3 - 獲取市場信息")
        # ... existing code ...
        print("4 - 獲取訂單簿")
        print("5 - 執行現貨/合約做市策略or對沖")
        stats_label = "6 - 交易統計報表" if USE_DATABASE else "6 - 交易統計報表 (已停用)"
        # ... existing code ...
        print(stats_label)
        print("7 - 市場分析")
        print("8 - 重平設置管理")
        # ... existing code ...
        db_status = "開啟" if USE_DATABASE else "關閉"
        print(f"D - 切換資料庫寫入 (目前: {db_status})")
        print("9 - 退出")

        operation = input("請輸入操作類型: ")

        if operation == '1':
            # ... existing code ...
            get_address_command(api_key, secret_key)
        elif operation == '2':
            get_balance_command(api_key, secret_key)
        # ... existing code ...
        elif operation == '3':
            get_markets_command()
        elif operation == '4':
            # ... existing code ...
            get_orderbook_command(api_key, secret_key, ws_proxy=ws_proxy)
        elif operation == '5':
            run_market_maker_command(api_key, secret_key, ws_proxy=ws_proxy)
        # ... existing code ...
        elif operation == '6':
            trading_stats_command(api_key, secret_key)
        elif operation == '7':
            # ... existing code ...
            market_analysis_command(api_key, secret_key, ws_proxy=ws_proxy)
        elif operation == '8':
            rebalance_settings_command()
        # ... existing code ...
        elif operation.lower() == 'd':
            toggle_database_command()
        elif operation == '9':
            # ... existing code ...
            print("退出程序。")
            break
        else:
            # ... existing code ...
            print("輸入錯誤，請重新輸入。")
