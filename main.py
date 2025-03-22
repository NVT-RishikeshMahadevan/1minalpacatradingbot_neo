import streamlit as st
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest, GetOrdersRequest
from alpaca.trading.enums import OrderSide, TimeInForce, OrderType, QueryOrderStatus
import pandas as pd
from datetime import datetime, timedelta
import json
import os
import time

# File to store bot state
STATE_FILE = "bot_state.json"

def load_bot_state():
    try:
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, 'r') as f:
                return json.load(f)
        return {"is_active": False, "last_run": None}
    except:
        return {"is_active": False, "last_run": None}

def save_bot_state(state):
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f)

@st.cache_resource(ttl=60)  # Cache for 60 seconds
def create_trading_client():
    api_key = "PK25YZNBYBYX0XQJNK5A"
    secret_key = "CfZx1CtNITOdYKpwxVYCec02k6WBT0EJBYSS5WgZ"
    return TradingClient(api_key=api_key, secret_key=secret_key, paper=True)

def can_place_order():
    account = get_account_info()
    return float(account.buying_power) >= 100  # Minimum required buying power

def auto_buy_btc():
    if not can_place_order():
        return False, "Insufficient buying power"
    try:
        result = place_market_order("BTC/USD", 0.01, OrderSide.BUY)
        return True, result
    except Exception as e:
        return False, str(e)

def place_market_order(symbol, qty, side):
    client = create_trading_client()
    try:
        symbol = symbol.upper()
        order_request = MarketOrderRequest(
            symbol=symbol,
            qty=qty,
            side=side,
            time_in_force=TimeInForce.GTC,
            type=OrderType.MARKET
        )
        order = client.submit_order(order_request)
        return f"Order placed successfully: {side.value.title()} {qty} {symbol}"
    except Exception as e:
        return f"Error placing order: {str(e)}"

def get_account_info():
    client = create_trading_client()
    return client.get_account()

def get_positions():
    client = create_trading_client()
    try:
        positions = client.get_all_positions()
        positions_data = []
        for position in positions:
            side = "Long" if float(position.qty) > 0 else "Short"
            positions_data.append({
                "Symbol": position.symbol,
                "Side": side,
                "Quantity": abs(float(position.qty)),
                "Market Value": f"${float(position.market_value):,.2f}",
                "Average Entry": f"${float(position.avg_entry_price):,.2f}",
                "Unrealized P/L": f"${float(position.unrealized_pl):,.2f}",
                "Current Price": f"${float(position.current_price):,.2f}"
            })
        return positions_data
    except Exception as e:
        return f"Error fetching positions: {str(e)}"

def get_orders(start_date=None, end_date=None, status=QueryOrderStatus.ALL):
    client = create_trading_client()
    try:
        request_params = GetOrdersRequest(
            status=status,
            after=start_date,
            until=end_date,
            limit=100
        )
        
        orders = client.get_orders(request_params)
        
        orders_data = []
        for order in orders:
            orders_data.append({
                "Symbol": order.symbol,
                "Side": order.side.value.title(),
                "Quantity": order.qty,
                "Order Type": order.type.value.title(),
                "Status": order.status.value.title(),
                "Submitted At": order.submitted_at.strftime("%Y-%m-%d %H:%M:%S") if order.submitted_at else "N/A",
                "Filled At": order.filled_at.strftime("%Y-%m-%d %H:%M:%S") if order.filled_at else "Not Filled",
                "Filled Price": f"${float(order.filled_avg_price):,.2f}" if order.filled_avg_price else "Not Filled"
            })
        return orders_data
    except Exception as e:
        return f"Error fetching orders: {str(e)}"

def calculate_performance_metrics(positions_data):
    if not positions_data or not isinstance(positions_data, list):
        return {}
    
    try:
        total_value = sum(float(pos['Market Value'].replace('$', '').replace(',', '')) 
                         for pos in positions_data)
        total_pl = sum(float(pos['Unrealized P/L'].replace('$', '').replace(',', '')) 
                       for pos in positions_data)
        
        return {
            "Total Portfolio Value": f"${total_value:,.2f}",
            "Total Unrealized P/L": f"${total_pl:,.2f}",
            "Return %": f"{(total_pl/total_value)*100:.2f}%" if total_value > 0 else "0.00%"
        }
    except:
        return {}

def main():
    st.title("Crypto Trading Dashboard")

    # Auto BTC Buyer Bot Section
    st.header("Auto BTC Buyer Bot")
    
    # Load bot state
    bot_state = load_bot_state()
    
    # Create columns for bot controls
    bot_col1, bot_col2, bot_col3 = st.columns([1,2,1])
    
    with bot_col1:
        if not bot_state["is_active"]:
            if st.button("Start Bot"):
                bot_state["is_active"] = True
                bot_state["last_run"] = None
                save_bot_state(bot_state)
                st.rerun()
        else:
            if st.button("Stop Bot"):
                bot_state["is_active"] = False
                save_bot_state(bot_state)
                st.rerun()

    with bot_col2:
        status_placeholder = st.empty()
        if bot_state["is_active"]:
            status_placeholder.success("Bot Status: Running ✅")
        else:
            status_placeholder.error("Bot Status: Stopped ⛔")

    # Bot logic
    if bot_state["is_active"]:
        timer_placeholder = st.empty()
        positions_placeholder = st.empty()
        orders_placeholder = st.empty()
        
        # Check if it's time to place an order
        current_time = datetime.now()
        last_run = datetime.fromisoformat(bot_state["last_run"]) if bot_state["last_run"] else None
        
        # Calculate time since last run
        time_since_last_run = (current_time - last_run).total_seconds() if last_run else float('inf')
        
        # Only place order if more than 60 seconds have passed
        if time_since_last_run >= 60:
            bot_state["last_run"] = current_time.isoformat()
            save_bot_state(bot_state)
            
            success, message = auto_buy_btc()
            if success:
                st.success(f"Order placed successfully at {current_time.strftime('%H:%M:%S')}")
            else:
                st.error(f"Order failed: {message}")
            
            # Force refresh positions and orders immediately after order
            client = create_trading_client()
            
            # Update positions and orders
            positions_data = get_positions()
            if isinstance(positions_data, list):
                if positions_data:
                    positions_placeholder.table(pd.DataFrame(positions_data))
                else:
                    positions_placeholder.write("No open positions")
            else:
                positions_placeholder.write(positions_data)
            
            orders_data = get_orders(datetime.now() - timedelta(days=1), datetime.now())
            if isinstance(orders_data, list):
                if orders_data:
                    orders_placeholder.table(pd.DataFrame(orders_data))
                else:
                    orders_placeholder.write("No orders in the selected date range")
            else:
                orders_placeholder.write(orders_data)
        
        # Display next order time
        if bot_state["last_run"]:
            last_run = datetime.fromisoformat(bot_state["last_run"])
            next_run = last_run + timedelta(seconds=60)
            
            timer_placeholder.info(f"""
            Last order: {last_run.strftime('%H:%M:%S')}
            Next order at: {next_run.strftime('%H:%M:%S')}
            """)
            
            # Update positions and orders display
            positions_data = get_positions()
            if isinstance(positions_data, list):
                if positions_data:
                    positions_placeholder.table(pd.DataFrame(positions_data))
                else:
                    positions_placeholder.write("No open positions")
            else:
                positions_placeholder.write(positions_data)
            
            orders_data = get_orders(datetime.now() - timedelta(days=1), datetime.now())
            if isinstance(orders_data, list):
                if orders_data:
                    orders_placeholder.table(pd.DataFrame(orders_data))
                else:
                    orders_placeholder.write("No orders in the selected date range")
            else:
                orders_placeholder.write(orders_data)
        
        time.sleep(1)
        st.rerun()

    st.markdown("---")

    # Position Management Section
    st.header("Position Management")
    
    col1, col2 = st.columns(2)
    
    # Close All Positions
    with col1:
        if st.button("Close All Positions"):
            client = create_trading_client()
            try:
                client.close_all_positions(cancel_orders=True)
                st.write("All positions closed successfully")
            except Exception as e:
                st.write(f"Error closing positions: {str(e)}")
    
    # Cancel Orders
    with col2:
        if st.button("Cancel All Orders"):
            client = create_trading_client()
            try:
                client.cancel_orders()
                st.write("All orders cancelled successfully")
            except Exception as e:
                st.write(f"Error cancelling orders: {str(e)}")

    # Account Information Section
    st.header("Account Information")
    account = get_account_info()
    
    acc_col1, acc_col2 = st.columns(2)
    
    with acc_col1:
        account_info = {
            "Buying Power": f"${float(account.buying_power):,.2f}",
            "Cash": f"${float(account.cash):,.2f}",
            "Portfolio Value": f"${float(account.portfolio_value):,.2f}",
            "Currency": account.currency
        }
        st.write("### Basic Info")
        for key, value in account_info.items():
            st.write(f"**{key}:** {value}")
    
    with acc_col2:
        trading_info = {
            "Pattern Day Trader": account.pattern_day_trader,
            "Trading Blocked": account.trading_blocked,
            "Transfers Blocked": account.transfers_blocked,
            "Account Blocked": account.account_blocked,
            "Multiplier": account.multiplier
        }
        st.write("### Trading Status")
        for key, value in trading_info.items():
            st.write(f"**{key}:** {value}")

    # Display Current Positions
    st.header("Current Positions")
    positions_data = get_positions()
    if isinstance(positions_data, list):
        if positions_data:
            st.table(pd.DataFrame(positions_data))
        else:
            st.write("No open positions")
    else:
        st.write(positions_data)

    # Order History Section
    st.header("Order History")

    # Date Range Selection
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input(
            "Start Date",
            datetime.now() - timedelta(days=1)
        )
    with col2:
        end_date = st.date_input(
            "End Date",
            datetime.now()
        )

    # Order Filters
    col1, col2, col3 = st.columns(3)
    
    with col1:
        order_status_filter = st.selectbox(
            "Filter by Status",
            ["All Orders", "Open", "Filled", "Canceled", "Expired", "Rejected"]
        )
    
    with col2:
        side_filter = st.selectbox(
            "Filter by Side",
            ["All", "Buy", "Sell"]
        )
    
    with col3:
        symbol_filter = st.text_input("Filter by Symbol", "")


    # Convert dates to datetime
    start_datetime = datetime.combine(start_date, datetime.min.time())
    end_datetime = datetime.combine(end_date, datetime.max.time())
    
    # Get orders
    orders_data = get_orders(start_datetime, end_datetime)
    
    if isinstance(orders_data, list):
        if orders_data:
            df = pd.DataFrame(orders_data)
            
            # Apply filters
            if order_status_filter != "All Orders":
                df = df[df['Status'] == order_status_filter.title()]
            
            if side_filter != "All":
                df = df[df['Side'] == side_filter.title()]
            
            if symbol_filter:
                df = df[df['Symbol'].str.contains(symbol_filter.upper(), case=False)]
            
            if not df.empty:
                st.table(df)
            else:
                st.write("No orders match the selected filters")
        else:
            st.write("No orders in the selected date range")
    else:
        st.write(orders_data)

if __name__ == "__main__":
    main()
