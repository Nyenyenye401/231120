import threading
import time
import streamlit as st
import json
import random
import string
from datetime import datetime, timedelta
import bcrypt
import os
import aiohttp
import asyncio
from typing import Dict, Any
from main_bot import run_autopost_task
from main_bot import run_monitor, monitoring_clients
import pickle
import os.path

 ## ------------------------------------------------------------------------------



## ------------------------------------------------------------------------------

# Initialize session state
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'user_id' not in st.session_state:
    st.session_state.user_id = None

# File path
DATA_FILE = 'peruserdata.json'
        
## ------------------------------------------------------------------------------

async def fetch_bot_info(token: str) -> Dict[Any, Any]:
    """Fetch user information using Discord API"""
    async with aiohttp.ClientSession() as session:
        headers = {'Authorization': token}  # Remove 'Bot ' prefix
        try:
            async with session.get('https://discord.com/api/v9/users/@me', headers=headers) as response:
                if response.status == 200:
                    return await response.json()
                return None
        except Exception as e:
            print(f"Error fetching user info: {e}")
            return None
        
## ------------------------------------------------------------------------------

async def fetch_servers(token: str) -> Dict[Any, Any]:
    """Fetch servers for a bot token"""
    async with aiohttp.ClientSession() as session:
        headers = {'Authorization': token}  # Remove 'Bot ' prefix
        try:
            async with session.get('https://discord.com/api/v9/users/@me/guilds', headers=headers) as response:
                if response.status == 200:
                    return await response.json()
                print(f"Error fetching servers: {response.status}")
                return None
        except Exception as e:
            print(f"Error fetching servers: {e}")
            return None
        
## ------------------------------------------------------------------------------

async def fetch_channels(token: str, server_id: str) -> Dict[Any, Any]:
    """Fetch channels for a server"""
    async with aiohttp.ClientSession() as session:
        headers = {'Authorization': token}  # Remove 'Bot ' prefix
        try:
            async with session.get(f'https://discord.com/api/v9/guilds/{server_id}/channels', headers=headers) as response:
                if response.status == 200:
                    return await response.json()
                print(f"Error fetching channels: {response.status}")
                return None
        except Exception as e:
            print(f"Error fetching channels: {e}")
            return None
        
## ------------------------------------------------------------------------------

def show_server_config(user_data):
    st.markdown("""
        <div style='background-color: rgba(49, 51, 56, 0.2); padding: 20px; border-radius: 15px; margin-bottom: 20px;'>
            <h2>Server Configuration</h2>
            <p style="margin-top: 0.1px; color: #d1d1d1; font-size: 14px;">
                Configure and manage your servers and channels
            </p>
        </div>
    """, unsafe_allow_html=True)

    accounts = user_data.get('accounts', {})
    if not accounts:
        st.warning("No accounts available. Please add an account first.")
        return

    # Statistics Overview
    col1, col2, col3 = st.columns(3)
    
    total_servers = sum(len(acc.get('servers', {})) for acc in accounts.values())
    total_channels = sum(
        len(server.get('channels', {}))
        for acc in accounts.values()
        for server in acc.get('servers', {}).values()
    )
    configured_channels = sum(
        1 for acc in accounts.values()
        for server in acc.get('servers', {}).values()
        for channel in server.get('channels', {}).values()
        if channel.get('message') and channel.get('delay')
    )

    with col1:
        st.markdown(f"""
            <div style='background-color: rgba(49, 51, 56, 0.2); padding: 20px; border-radius: 15px;'>
                <h4>Total Servers</h4>
                <p style='font-size: 24px; color: #5865F2;'>{total_servers}</p>
            </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown(f"""
            <div style='background-color: rgba(49, 51, 56, 0.2); padding: 20px; border-radius: 15px;'>
                <h4>Total Channels</h4>
                <p style='font-size: 24px; color: #43B581;'>{total_channels}</p>
            </div>
        """, unsafe_allow_html=True)

    with col3:
        st.markdown(f"""
            <div style='background-color: rgba(49, 51, 56, 0.2); padding: 20px; border-radius: 15px;'>
                <h4>Configured Channels</h4>
                <p style='font-size: 24px; color: #FAA61A;'>{configured_channels}</p>
            </div>
        """, unsafe_allow_html=True)

    # Configuration Sections
    st.markdown("""
        <div style='background-color: rgba(49, 51, 56, 0.2); padding: 20px; border-radius: 15px; margin: 20px 0;'>
            <h3>Add Configuration</h3>
        </div>
    """, unsafe_allow_html=True)

    # Account selection
    selected_bot = st.selectbox("Select Bot", list(accounts.keys()))
    bot_data = accounts[selected_bot]

    # Server fetching and selection
    with st.spinner("Fetching servers..."):
        servers = run_async(fetch_servers(bot_data['token']))
        
    if servers:
        server_choices = {server['id']: server['name'] for server in servers}
        selected_server_id = st.selectbox(
            "Select Server",
            options=list(server_choices.keys()),
            format_func=lambda x: f"{server_choices[x]} ({x})"
        )
        
        # Channel fetching and selection
        with st.spinner("Fetching channels..."):
            channels = run_async(fetch_channels(bot_data['token'], selected_server_id))
        
        if channels:
            text_channels = [ch for ch in channels if ch['type'] == 0]
            channel_choices = {ch['id']: ch['name'] for ch in text_channels}
            
            selected_channels = st.multiselect(
                "Select Channels",
                options=list(channel_choices.keys()),
                format_func=lambda x: f"{channel_choices[x]} ({x})"
            )

            if selected_channels:
                # Initialize configurations
                if 'servers' not in bot_data:
                    bot_data['servers'] = {}
                
                if selected_server_id not in bot_data['servers']:
                    bot_data['servers'][selected_server_id] = {
                        "name": server_choices[selected_server_id],
                        "channels": {},
                        "autoposting": False
                    }

                # Add selected channels
                for channel_id in selected_channels:
                    if channel_id not in bot_data['servers'][selected_server_id]['channels']:
                        bot_data['servers'][selected_server_id]['channels'][channel_id] = {
                            "name": channel_choices[channel_id],
                            "message": "",
                            "delay": 60
                        }

                if st.button("Save Configuration", key="save_config"):
                    data = load_data()
                    data[st.session_state.user_id]['accounts'][selected_bot] = bot_data
                    save_data(data)
                    st.success(f"""
                        Configuration saved successfully!
                        Server: {server_choices[selected_server_id]}
                        Channels: {len(selected_channels)}
                    """)

    # Remove Configuration Section
    st.markdown("""
        <div style='background-color: rgba(49, 51, 56, 0.2); padding: 20px; border-radius: 15px; margin: 20px 0;'>
            <h3>Remove Configuration</h3>
        </div>
    """, unsafe_allow_html=True)

    # Account selection for removal
    selected_account_remove = st.selectbox("Select Account", list(accounts.keys()), key="remove_account")
    account_data = accounts[selected_account_remove]

    col1, col2 = st.columns(2)

    with col1:
        if account_data.get("servers"):
            server_to_remove = st.selectbox(
                "Select Server to Remove",
                options=[(sid, sinfo.get('name', 'Unknown Server')) for sid, sinfo in account_data["servers"].items()],
                format_func=lambda x: f"{x[1]} ({x[0]})",
                key="remove_server"
            )
            
            if st.button("Remove Server", key="remove_server_btn"):
                try:
                    data = load_data()
                    del data[st.session_state.user_id]['accounts'][selected_account_remove]['servers'][server_to_remove[0]]
                    save_data(data)
                    st.success(f"Server '{server_to_remove[1]}' removed successfully!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error removing server: {str(e)}")

    with col2:
        if account_data.get("servers"):
            # First select server
            server_for_channel = st.selectbox(
                "Select Server",
                options=[(sid, sinfo.get('name', 'Unknown Server')) for sid, sinfo in account_data["servers"].items()],
                format_func=lambda x: f"{x[1]} ({x[0]})",
                key="server_for_channel"
            )

            # Then select channel from that server
            if server_for_channel:
                server_info = account_data["servers"][server_for_channel[0]]
                if server_info.get("channels"):
                    channel_to_remove = st.selectbox(
                        "Select Channel to Remove",
                        options=[(cid, cinfo.get('name', 'Unknown Channel')) for cid, cinfo in server_info["channels"].items()],
                        format_func=lambda x: f"{x[1]} ({x[0]})",
                        key="remove_channel"
                    )
                    
                    if st.button("Remove Channel", key="remove_channel_btn"):
                        try:
                            data = load_data()
                            del data[st.session_state.user_id]['accounts'][selected_account_remove]['servers'][server_for_channel[0]]['channels'][channel_to_remove[0]]
                            save_data(data)
                            st.success(f"Channel '{channel_to_remove[1]}' removed successfully!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error removing channel: {str(e)}")

    # Refresh button
    if st.button("Refresh Configuration"):
        st.rerun()


        
## ------------------------------------------------------------------------------

def show_login_page():
    # Custom CSS for the login page
    st.markdown("""
        <style>
        .login-container {
            max-width: 400px;
            margin: 0 auto;
            padding: 2rem;
            background-color: rgba(49, 51, 56, 0.2);
            border-radius: 20px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        }
        .login-header {
            text-align: center;
            margin-bottom: 2rem;
            color: white;
        }
        .login-footer {
            text-align: center;
            margin-top: 1rem;
            font-size: 0.8rem;
            color: #d1d1d1;
        }
        .stButton>button {
            width: 100%;
            background-color: #5865F2;
            color: white;
            border-radius: 10px;
            padding: 15px 0;
            font-weight: bold;
            border: none;
            margin-top: 20px;
        }
        .input-container {
            display: flex;
            align-items: center;
            margin-bottom: 15px;
            background-color: rgba(64, 68, 75, 0.8);
            padding: 10px;
            border-radius: 8px;
        }
        .input-icon {
            margin-right: 10px;
            width: 24px;
        }
        .discord-logo:hover {
            transform: scale(1.1);
        }
        .input-field {
            background-color: transparent;
            border: none;
            color: white;
            width: 100%;
        }
        .stTextInput>div>div>input {
            background-color: rgba(64, 68, 75, 0.8) !important;
            color: white !important;
            border: none !important;
            padding: 10px !important;
            border-radius: 8px !important;
        }

        </style>
    """, unsafe_allow_html=True)

    # Center the login form
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        
        
        # Login header
        st.markdown("""
            <div class="login-header">
                <h1></h1>
                <p style="color: #d1d1d1;"></p>
            </div>
        """, unsafe_allow_html=True)

        # Login form
        with st.form("login_form"):
            # Username input with icon
            st.markdown("""
                <div style="display: flex; align-items: center; margin-bottom: 5px;">
                    <img src="https://cdn.discordapp.com/emojis/1308056946263461989.webp" style="width: 15px; margin-right: 5px;">
                    <span style="color: #d1d1d1;">Username</span>
                </div>
            """, unsafe_allow_html=True)
            username = st.text_input("", placeholder="Enter your username", label_visibility="collapsed")

            # Password input with icon
            st.markdown("""
                <div style="display: flex; align-items: center; margin-bottom: 5px;">
                    <img src="https://cdn.discordapp.com/emojis/1328958222710603831.webp?size=128" style="width: 18px; margin-right: 5px;">
                    <span style="color: #d1d1d1;">Password</span>
                </div>
            """, unsafe_allow_html=True)
            password = st.text_input("", type="password", placeholder="Enter your password", label_visibility="collapsed")
            
            submit = st.form_submit_button("Login")
            

            if submit:
                data = load_data()
                # Find user by username
                user_id = None
                for uid, user_data in data.items():
                    if user_data.get('username') == username and user_data.get('password') == password:
                        user_id = uid
                        break
                
                if user_id:
                    st.session_state.logged_in = True
                    st.session_state.user_id = user_id
                    save_session(username, user_id)
                    st.rerun()
                else:
                    st.error("Invalid username or password")

        # Login footer with Discord link
        st.markdown("""
            <div class="login-footer">
                <p>Need help? Join our <a href="https://discord.gg/wSYRJVM5ZF" target="_blank" style="color: #5865F2;">Discord Server</a></p>
            </div>
        """, unsafe_allow_html=True)
        
        st.markdown('</div>', unsafe_allow_html=True)


        
## ------------------------------------------------------------------------------

def run_async(coro):
    """Run an async function synchronously"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()
        
## ------------------------------------------------------------------------------

# Load and save data functions
def load_data():
    try:
        with open(DATA_FILE, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {"admin": {"bots": {}}}

def save_data(data):
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f, indent=4)


        
## ------------------------------------------------------------------------------

def show_dashboard():
    data = load_data()
    user_data = data[st.session_state.user_id]
        
    # Navigation using st.selectbox
    pages = ["Overview", "Bot Management", "Bot Status", "Bot Control", "Bot Server Config", "Bot Setting", "DM Tracker", "Token Management"]
    selected = st.sidebar.selectbox("", pages)



    # Single logout button at the bottom
    if st.sidebar.button("Logout", help="Click to logout", key="logout_button"):
        st.session_state.logged_in = False
        st.session_state.user_id = None
        clear_session()
        st.rerun()

    # Show selected page content
    if selected == "Overview":
        show_overview(user_data)
    elif selected == "Bot Management":
        show_bot_management(user_data)
    elif selected == "Bot Server Config":
        show_server_config(user_data)
    elif selected == "Bot Setting":
        show_settings(user_data)    
    elif selected == "Bot Control":
        show_control(user_data)
    elif selected == "Bot Status":
        show_bot_status(user_data)
    elif selected == "DM Tracker":
        show_dm_tracker(user_data)
    elif selected == "Token Management":
        show_token_management(user_data)


## ------------------------------------------------------------------------------

def show_bot_management(user_data):
    accounts = user_data.get('accounts', {})
    max_bots = user_data.get('max_bots', 0)

    # Custom CSS for bot management
    st.markdown("""
        <style>
        .bot-card {
            background-color: rgba(49, 51, 56, 0.2);
            border-radius: 15px;
            padding: 20px;
            margin-bottom: 20px;
            transition: transform 0.2s;
        }
        .bot-card:hover {
            transform: translateY(-5px);
        }
        .bot-header {
            display: flex;
            align-items: center;
            margin-bottom: 10px;
        }
        .bot-info {
            color: #d1d1d1;
            font-size: 14px;
            margin: 5px 0;
        }
        .bot-actions {
            display: flex;
            gap: 10px;
            margin-top: 15px;
        }
        .remove-button {
            background-color: #ED4245 !important;
            color: white !important;
        }
        .add-button {
            background-color: #5865F2 !important;
            color: white !important;
        }
        </style>
    """, unsafe_allow_html=True)

    # Header
    st.markdown("""
        <div style='background-color: rgba(49, 51, 56, 0.2); padding: 20px; border-radius: 15px; margin-bottom: 20px;'>
            <h2>Bot Management</h2>
            <p style="margin-top: 0.1px; color: #d1d1d1; font-size: 14px;">
                Manage your Discord bots here
            </p>
        </div>
    """, unsafe_allow_html=True)

    # Stats
    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"""
            <div style='background-color: rgba(49, 51, 56, 0.2); padding: 20px; border-radius: 15px; margin-bottom: 20px;'>
                <h3>Current Bots</h3>
                <p style="font-size: 24px; color: #5865F2;">{len(accounts)}/{max_bots}</p>
            </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown(f"""
            <div style='background-color: rgba(49, 51, 56, 0.2); padding: 20px; border-radius: 15px; margin-bottom: 20px;'>
                <h3>Slots Available</h3>
                <p style="font-size: 24px; color: #43B581;">{max_bots - len(accounts)}</p>
            </div>
        """, unsafe_allow_html=True)

    # Add new bot
    if len(accounts) < max_bots:
        with st.expander("Add New Bot"):
            with st.form("add_account_form"):
                col1, col2 = st.columns(2)
                with col1:
                    account_name = st.text_input("Bot Name", help="Enter a name for this bot")
                with col2:
                    token = st.text_input("User Token", help="Enter your Discord user token", type="password")
                
                submit = st.form_submit_button("Add Bot", use_container_width=True)
                
                if submit and token and account_name:
                    with st.spinner("Verifying token..."):
                        user_info = run_async(fetch_bot_info(token))
                        if user_info:
                            data = load_data()
                            if 'accounts' not in data[st.session_state.user_id]:
                                data[st.session_state.user_id]['accounts'] = {}
                            
                            data[st.session_state.user_id]['accounts'][account_name] = {
                                "token": token,
                                "status": "offline",
                                "start_time": None,
                                "messages_sent": 0,
                                "servers": {},
                                "webhook": None,
                                "dm_monitoring": False,
                                "dm_webhook": None,
                                "user_info": {
                                    "username": user_info.get('username', ''),
                                    "discriminator": user_info.get('discriminator', ''),
                                    "id": user_info.get('id', ''),
                                    "added_at": datetime.now().strftime("%Y-%m-%d | %H:%M:%S")
                                }
                            }
                            
                            save_data(data)
                            st.success("Bot added successfully!")
                            st.rerun()
                        else:
                            st.error("Invalid token")
                elif submit:
                    st.error("Please fill in all fields")

    # Display existing bots
    if accounts:
        st.markdown("""
            <div style='background-color: rgba(49, 51, 56, 0.2); padding: 20px; border-radius: 15px; margin: 15px 0;'>
                <h3>Your Bots</h3>
            </div>
        """, unsafe_allow_html=True)

        for account_name, account_data in accounts.items():
            user_info = account_data.get('user_info', {})
            
            # Bot card
            st.markdown(f"""
                <div class="bot-card">
                    <div class="bot-header">
                        <img src="https://cdn.discordapp.com/emojis/1308056946263461989.webp?size=128" style="width: 25px; margin-right: 10px;">
                        <h3 style="color: white; margin: 0;">{account_name}</h3>
                    </div>
                    <div class="bot-info">
                        <p>Username: {user_info.get('username', 'N/A')}</p>
                        <p>ID: {user_info.get('id', 'N/A')}</p>
                        <p>Added: {user_info.get('added_at', 'N/A')}</p>
                        <p>Status: {'Online' if account_data.get('status') == 'online' else ' Offline'}</p>
                    </div>
                </div>
            """, unsafe_allow_html=True)

            # Remove bot button
            if st.button("🗑️ Remove Bot", key=f"remove_{account_name}", help=f"Remove {account_name} from your account"):
                try:
                    data = load_data()
                    del data[st.session_state.user_id]['accounts'][account_name]
                    save_data(data)
                    st.success(f"Bot '{account_name}' removed successfully!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error removing bot: {str(e)}")
    else:
        st.info("You haven't added any bots yet. Add your first bot using the form above!")


## ------------------------------------------------------------------------------

## ------------------------------------------------------------------------------

def show_overview(user_data):
    # Custom CSS for overview cards
    st.markdown("""
        <style>
        .card {
            padding: 20px;
            border-radius: 10px;
            background-color: rgba(49, 51, 56, 0.2);
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            margin-bottom: 20px;
        }
        .stat-value {
            font-size: 24px;
            font-weight: bold;
            color: white;
        }
        .stat-label {
            color: #666;
            font-size: 14px;
        }
        </style>
    """, unsafe_allow_html=True)

    st.markdown("""
        <div style='background-color: rgba(49, 51, 56, 0.2); padding: 20px; border-radius: 15px; margin-bottom: 20px;'>
            <h1>Welcome To Autopost Dashboard</h1>
            <p style="margin-left: 2px; margin-top: 0.1px; color: #d1d1d1; font-size: 14px;">
                Thanks for choosing us
            </p>
        </div>
    """, unsafe_allow_html=True)
    # Create three columns for stats
    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("""
            <div class="card">
                <img src="https://cdn.discordapp.com/emojis/1308056946263461989.webp?size=128" width="21">
                <div class="stat-value">{}/{}</div>
                <div class="stat-label">Max Bots</div>
            </div>
        """.format(len(user_data.get('accounts', {})), user_data.get('max_bots', 0)), unsafe_allow_html=True)

    with col2:
        st.markdown("""
            <div class="card">
                <img src="https://cdn.discordapp.com/emojis/1309124972899340348.webp?size=128" width="30">
                <div class="stat-value">{}</div>
                <div class="stat-label">Expiry Date</div>
            </div>
        """.format(user_data.get('expiry', 'N/A')), unsafe_allow_html=True)

    with col3:
        active_bots = sum(1 for acc in user_data.get('accounts', {}).values() 
                         if any(server.get('autoposting', False) 
                              for server in acc.get('servers', {}).values()))
        st.markdown("""
            <div class="card">
                <img src="https://cdn.discordapp.com/emojis/1315112774350803066.gif" width="30">
                <div class="stat-value">{}</div>
                <div class="stat-label">Running Bots</div>
            </div>
        """.format(active_bots), unsafe_allow_html=True)

        
## ------------------------------------------------------------------------------
def show_settings(user_data):
    st.markdown("""
    <div style='background-color: rgba(49, 51, 56, 0.2); padding: 20px; border-radius: 15px; margin-bottom: 20px;'>
        <h2>
            Settings
        </h2>
        <p style="margin-top: 0.1px; color: #d1d1d1; font-size: 14px;">
            Configure your messages, delays and webhooks here
        </p>
    </div>
""", unsafe_allow_html=True)
    
# Server and Channel Configuration (existing code)
    st.markdown("""
        <div style='background-color: rgba(49, 51, 56, 0.2); padding: 20px; border-radius: 10px; margin: 20px 0;'>
        <h2>Channel Configuration</h2>
        </div>
    """, unsafe_allow_html=True)

    accounts = user_data.get('accounts', {})
    if not accounts:
        st.warning("No accounts available. Please add an account first.")
        return
    
    # Account selection
    selected_account = st.selectbox("Select Account", list(accounts.keys()))
    account_data = accounts[selected_account]

    if not account_data.get('servers'):
        st.warning("No servers configured. Please configure servers first.")
        return

    # Server selection
    server_options = [(server_id, server_info.get('name', 'Unknown Server')) 
                     for server_id, server_info in account_data['servers'].items()]
    
    selected_server = st.selectbox(
        "Select Server",
        options=[s[0] for s in server_options],
        format_func=lambda x: next((s[1] for s in server_options if s[0] == x), x)
    )

    server_data = account_data['servers'].get(selected_server)
    if not server_data:
        st.warning("No configuration found for this server.")
        return

    # Channel Settings
    for channel_id, channel_info in server_data.get('channels', {}).items():
        with st.expander(f"{channel_info.get('name', 'Channel')} | {channel_id}"):
            # Message configuration
            message = st.text_area(
                "Message Content",
                value=channel_info.get('message', ''),
                key=f"msg_{channel_id}",
                help="Enter the message to be sent in this channel"
            )

            # Delay configuration
            delay = st.number_input(
                "Delay (seconds)",
                min_value=60,
                value=channel_info.get('delay', 60),
                key=f"delay_{channel_id}",
                help="Minimum delay is 60 seconds"
            )

            if st.button("Save Channel Settings", key=f"save_{channel_id}"):
                try:
                    data = load_data()
                    data[st.session_state.user_id]['accounts'][selected_account]['servers'][selected_server]['channels'][channel_id].update({
                        'message': message,
                        'delay': delay
                    })
                    save_data(data)
                    st.success("Channel settings updated successfully!")
                except Exception as e:
                    st.error(f"Error saving settings: {str(e)}")

     
    # Add webhook configuration section
    st.markdown("""
        <div style='background-color: rgba(49, 51, 56, 0.2); padding: 20px; border-radius: 10px; margin:20px 0;'>
        <h2>Autopost Webhook Configuration</h2>
        </div>
    """, unsafe_allow_html=True)
    
    webhook_url = st.text_input(
            "Webhook URL",
            value=account_data.get('webhook', ''),
            key="autopost_webhook",
            help="Enter Discord webhook URL for autopost notifications"
        )


    if st.button("Save Webhook"):
        try:
            data = load_data()
            data[st.session_state.user_id]['accounts'][selected_account]['webhook'] = webhook_url
            save_data(data)
            st.success("Webhook updated successfully!")
        except Exception as e:
            st.error(f"Error saving webhook: {str(e)}")

                 
## ------------------------------------------------------------------------------
def show_control(user_data):
    st.markdown("""
        <div style='background-color: rgba(49, 51, 56, 0.2); padding: 20px; border-radius: 15px; margin-bottom: 20px;'>
            <h2>Control Panel</h2>
            <p style="margin-top: 0.1px; color: #d1d1d1; font-size: 14px;">
                Start or stop your autoposting bots
            </p>
        </div>
    """, unsafe_allow_html=True)

    accounts = user_data.get('accounts', {})
    if not accounts:
        st.warning("No accounts available. Please add an account first.")
        return

    # Statistics Overview
    col1, col2, col3 = st.columns(3)
    
    total_accounts = len(accounts)
    running_accounts = sum(1 for acc in accounts.values() 
                         if any(server.get('autoposting', False) 
                              for server in acc.get('servers', {}).values()))
    running_servers = sum(
        sum(1 for server in acc.get('servers', {}).values() if server.get('autoposting', False))
        for acc in accounts.values()
    )

    with col1:
        st.markdown(f"""
            <div style='background-color: rgba(49, 51, 56, 0.2); padding: 20px; border-radius: 15px;'>
                <h4>Total Accounts</h4>
                <p style='font-size: 24px; color: #5865F2;'>{total_accounts}</p>
            </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown(f"""
            <div style='background-color: rgba(49, 51, 56, 0.2); padding: 20px; border-radius: 15px;'>
                <h4>Running Accounts</h4>
                <p style='font-size: 24px; color: #43B581;'>{running_accounts}</p>
            </div>
        """, unsafe_allow_html=True)

    with col3:
        st.markdown(f"""
            <div style='background-color: rgba(49, 51, 56, 0.2); padding: 20px; border-radius: 15px;'>
                <h4>Active Servers</h4>
                <p style='font-size: 24px; color: #FAA61A;'>{running_servers}</p>
            </div>
        """, unsafe_allow_html=True)

    # Account Status Cards
    st.markdown("""
        <div style='background-color: rgba(49, 51, 56, 0.2); padding: 20px; border-radius: 15px; margin: 20px 0;'>
            <h3>Account Control Panel</h3>
        </div>
    """, unsafe_allow_html=True)

    for acc_name, acc_data in accounts.items():
        active_servers = [
            (server_id, server_info) 
            for server_id, server_info in acc_data.get('servers', {}).items()
            if server_info.get('autoposting', False)
        ]
        
        inactive_servers = [
            (server_id, server_info) 
            for server_id, server_info in acc_data.get('servers', {}).items()
            if not server_info.get('autoposting', False)
        ]

        st.markdown(f"""
            <div style='background-color: rgba(49, 51, 56, 0.2); padding: 20px; border-radius: 15px; margin: 10px 0;'>
                <div style='display: flex; justify-content: space-between; align-items: center;'>
                    <div>
                        <h4 style='margin: 0;'>
                            <img src="https://cdn.discordapp.com/emojis/1308056946263461989.webp?size=128" 
                                 style="width: 25px; margin-right: 10px;">{acc_name}
                        </h4>
                        <p style='color: {"#43B581" if active_servers else "#ED4245"}'>
                            {"🟢 Running" if active_servers else "🔴 Stopped"}
                        </p>
                    </div>
                    <div style='text-align: right;'>
                        <p style='margin: 0;'>Active Servers: {len(active_servers)}</p>
                        <p style='margin: 0;'>Available Servers: {len(inactive_servers)}</p>
                    </div>
                </div>
            </div>
        """, unsafe_allow_html=True)

        # Control Section
        col1, col2 = st.columns(2)
        
        with col1:
            if inactive_servers:
                server_to_start = st.selectbox(
                    "Select Server to Start",
                    options=inactive_servers,
                    format_func=lambda x: f"{x[1].get('name', 'Unknown')}",
                    key=f"start_{acc_name}"
                )
                
                if st.button("Start Server", key=f"start_btn_{acc_name}"):
                    try:
                        # Your existing start logic here
                        data = load_data()
                        server_data = data[st.session_state.user_id]['accounts'][acc_name]['servers'][server_to_start[0]]
                        
                        # Check channel configurations
                        channels_without_config = [
                            channel_info.get('name', channel_id)
                            for channel_id, channel_info in server_data['channels'].items()
                            if not channel_info.get('message') or not channel_info.get('delay')
                        ]
                        
                        if channels_without_config:
                            st.error(f"Please configure these channels first: {', '.join(channels_without_config)}")
                            return

                        # Start autoposting
                        server_data['autoposting'] = True
                        data[st.session_state.user_id]['accounts'][acc_name]['start_time'] = time.time()
                        save_data(data)

                        # Start the autopost task
                        threading.Thread(
                            target=run_autopost_task,
                            args=(st.session_state.user_id, acc_name, acc_data['token'], server_to_start[0]),
                            daemon=True
                        ).start()

                        st.success(f"Started autoposting for {server_to_start[1].get('name')}")
                        time.sleep(1)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error starting server: {str(e)}")

        with col2:
            if active_servers:
                server_to_stop = st.selectbox(
                    "Select Server to Stop",
                    options=active_servers,
                    format_func=lambda x: f"{x[1].get('name', 'Unknown')}",
                    key=f"stop_{acc_name}"
                )
                
                if st.button("Stop Server", key=f"stop_btn_{acc_name}"):
                    try:
                        data = load_data()
                        data[st.session_state.user_id]['accounts'][acc_name]['servers'][server_to_stop[0]]['autoposting'] = False
                        save_data(data)
                        st.success(f"Stopped autoposting for {server_to_stop[1].get('name')}")
                        time.sleep(1)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error stopping server: {str(e)}")

    # Refresh button


    


## ------------------------------------------------------------------------------
def show_bot_status(user_data):
    # Add custom CSS for bot status page
    st.markdown("""
        <style>
        .status-card {
            background-color: rgba(49, 51, 56, 0.2);
            border-radius: 15px;
            padding: 20px;
            margin-bottom: 15px;
            transition: all 0.3s ease;
        }
        .status-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 5px 15px rgba(0,0,0,0.3);
        }
        .status-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 10px;
        }
        .status-title {
            color: white;
            font-size: 18px;
            font-weight: bold;
            margin: 0;
        }
        .status-stats {
            display: flex;
            justify-content: space-between;
            margin-top: 10px;
        }
        .status-stat {
            text-align: center;
            flex: 1;
        }
        .status-value {
            font-size: 24px;
            font-weight: bold;
            margin: 5px 0;
        }
        .status-label {
            color: #d1d1d1;
            font-size: 14px;
        }
        .status-indicator {
            padding: 5px 10px;
            border-radius: 10px;
            font-size: 14px;
            font-weight: bold;
        }
        .status-online {
            background-color: rgba(67, 181, 129, 0.2);
            color: #43B581;
        }
        .status-offline {
            background-color: rgba(237, 66, 69, 0.2);
            color: #ED4245;
        }
        .server-list {
            background-color: rgba(49, 51, 56, 0.1);
            border-radius: 10px;
            padding: 10px;
            margin-top: 10px;
        }
        .refresh-button {
            background-color: #5865F2;
            color: white;
            padding: 10px 20px;
            border-radius: 5px;
            border: none;
            cursor: pointer;
            transition: background-color 0.3s ease;
        }
        .refresh-button:hover {
            background-color: #4752C4;
        }
        </style>
    """, unsafe_allow_html=True)

    st.markdown("""
        <div style='background-color: rgba(49, 51, 56, 0.2); padding: 20px; border-radius: 15px; margin-bottom: 20px;'>
            <h2>Bot Status Monitor</h2>
            <p style="margin-top: 0.1px; color: #d1d1d1; font-size: 14px;">
                Monitor your bots status and performance in real-time
            </p>
        </div>
    """, unsafe_allow_html=True)

    accounts = user_data.get('accounts', {})
    if not accounts:
        st.warning("No accounts available to monitor.")
        return

    # Status Overview Cards
    col1, col2, col3 = st.columns(3)
    
    # Calculate statistics
    total_bots = len(accounts)
    active_bots = sum(1 for acc in accounts.values() 
                     if any(server.get('autoposting', False) 
                           for server in acc.get('servers', {}).values()))
    total_messages = sum(acc.get('messages_sent', 0) for acc in accounts.values())

    with col1:
        st.markdown(f"""
            <div style='background-color: rgba(49, 51, 56, 0.2); padding: 20px; border-radius: 15px;'>
                <h4>Total Bots</h4>
                <p style='font-size: 24px; color: #5865F2;'>{total_bots}</p>
            </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown(f"""
            <div style='background-color: rgba(49, 51, 56, 0.2); padding: 20px; border-radius: 15px;'>
                <h4>Active Bots</h4>
                <p style='font-size: 24px; color: #43B581;'>{active_bots}</p>
            </div>
        """, unsafe_allow_html=True)

    with col3:
        st.markdown(f"""
            <div style='background-color: rgba(49, 51, 56, 0.2); padding: 20px; border-radius: 15px;'>
                <h4>Total Messages</h4>
                <p style='font-size: 24px; color: #FAA61A;'>{total_messages:,}</p>
            </div>
        """, unsafe_allow_html=True)

    # Detailed Bot Status
    st.markdown("""
        <div style='background-color: rgba(49, 51, 56, 0.2); padding: 20px; border-radius: 15px; margin-top: 20px;'>
            <h3>Detailed Bot Status</h3>
        </div>
    """, unsafe_allow_html=True)

    for acc_name, acc_data in accounts.items():
        # Calculate bot-specific stats
        active_servers = sum(1 for server in acc_data.get('servers', {}).values() 
                           if server.get('autoposting', False))
        total_servers = len(acc_data.get('servers', {}))
        total_channels = sum(len(server.get('channels', {})) 
                           for server in acc_data.get('servers', {}).values())
        messages_sent = acc_data.get('messages_sent', 0)

        # Calculate uptime if bot is active
        uptime_str = "Not running"
        if acc_data.get('start_time'):
            uptime = int(time.time() - acc_data['start_time'])
            days = uptime // 86400
            hours = (uptime % 86400) // 3600
            minutes = (uptime % 3600) // 60
            uptime_str = f"{days}d {hours}h {minutes}m"

        # Bot Status Card
        st.markdown(f"""
            <div style='background-color: rgba(49, 51, 56, 0.2); padding: 20px; border-radius: 15px; margin: 10px 0;'>
                <div style='display: flex; justify-content: space-between; align-items: center;'>
                    <div>
                        <h4 style='margin: 0;'><img src="https://cdn.discordapp.com/emojis/1308056946263461989.webp?size=128" style="width: 25px; margin-right: 10px;">{acc_name}</h4>
                        <p style='color: {"#43B581" if active_servers > 0 else "#ED4245"}'>
                            {"🟢 Online" if active_servers > 0 else "🔴 Offline"}
                        </p>
                    </div>
                    <div style='text-align: right;'>
                        <p style='margin: 0;'>Uptime: {uptime_str}</p>
                        <p style='margin: 0;'>Messages: {messages_sent:,}</p>
                    </div>
                </div>
                <div style='margin-top: 10px;'>
                    <p>Active Servers: {active_servers}/{total_servers}</p>
                    <p>Total Channels: {total_channels}</p>
                </div>
            </div>
        """, unsafe_allow_html=True)

        # Show active servers if any
        if active_servers > 0:
            with st.expander(f"View Active Servers for {acc_name}"):
                for server_id, server_data in acc_data.get('servers', {}).items():
                    if server_data.get('autoposting', False):
                        st.markdown(f"""
                            <div style='background-color: rgba(49, 51, 56, 0.1); padding: 10px; border-radius: 10px; margin: 5px 0;'>
                                <p style='margin: 0;'><strong>{server_data.get('name', 'Unknown Server')}</strong></p>
                                <p style='margin: 0; font-size: 0.9em;'>Channels: {len(server_data.get('channels', {}))}</p>
                            </div>
                        """, unsafe_allow_html=True)

    # Auto-refresh button
    if st.button("Refresh Status"):
        st.rerun()


## ------------------------------------------------------------------------------
def save_session(username, user_id):
    """Save session data to a file with expiration"""
    session_data = {
        'username': username,
        'user_id': user_id,
        'logged_in': True,
        'expires': datetime.now() + timedelta(days=1)  # Session expires in 7 days
    }
    with open('.session', 'wb') as f:
        pickle.dump(session_data, f)

def load_session():
    """Load session data from file with expiration check"""
    try:
        if os.path.exists('.session'):
            with open('.session', 'rb') as f:
                session_data = pickle.load(f)
                if datetime.now() < session_data['expires']:
                    return session_data
                else:
                    clear_session()  # Remove expired session
    except Exception:
        pass
    return None


def load_session():
    """Load session data from file"""
    try:
        if os.path.exists('.session'):
            with open('.session', 'rb') as f:
                return pickle.load(f)
    except Exception:
        pass
    return None

def clear_session():
    """Clear session data"""
    if os.path.exists('.session'):
        os.remove('.session')

## ------------------------------------------------------------------------------
def show_dm_tracker(user_data):
    st.markdown("""
        <div style='background-color: rgba(49, 51, 56, 0.2); padding: 20px; border-radius: 15px; margin-bottom: 20px;'>
            <h2>Direct Message Tracker</h2>
            <p style="margin-top: 0.1px; color: #d1d1d1; font-size: 14px;">
                Monitor your Discord DMs
            </p>
        </div>
        
        <style>
        .status-card {
            background-color: rgba(49, 51, 56, 0.2);
            border-radius: 15px;
            padding: 20px;
            margin-bottom: 15px;
            transition: all 0.3s ease;
        }
        .status-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 5px 15px rgba(0,0,0,0.3);
        }
        .status-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 10px;
        }
        .status-title {
            color: white;
            font-size: 18px;
            font-weight: bold;
            margin: 0;
        }
        .dm-tracker-button {
            width: 100%;
            padding: 10px 20px;
            border-radius: 8px;
            font-weight: bold;
            transition: all 0.3s ease;
        }
        </style>
    """, unsafe_allow_html=True)

    accounts = user_data.get('accounts', {})
    if not accounts:
        st.warning("No accounts available. Please add an account first.")
        return

    # Status Overview
    total_monitoring = sum(1 for acc in accounts.values() if acc.get('dm_monitoring', False))
    
    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"""
            <div style='background-color: rgba(49, 51, 56, 0.2); padding: 20px; border-radius: 15px;'>
                <h4>Total Bots</h4>
                <p style='font-size: 24px; color: #5865F2;'>{len(accounts)}</p>
            </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown(f"""
            <div style='background-color: rgba(49, 51, 56, 0.2); padding: 20px; border-radius: 15px;'>
                <h4>Monitoring Active</h4>
                <p style='font-size: 24px; color: #43B581;'>{total_monitoring}</p>
            </div>
        """, unsafe_allow_html=True)

    # Bot Status Cards
    st.markdown("""
        <div style='background-color: rgba(49, 51, 56, 0.2); padding: 20px; border-radius: 15px; margin-top: 25px; margin-bottom:20px; '>
            <h3>DM Monitor Status</h3>
        </div>
    """, unsafe_allow_html=True)

    for acc_name, acc_data in accounts.items():
        monitoring_status = acc_data.get('dm_monitoring', False)
        webhook_url = acc_data.get('dm_webhook', '')
        user_info = acc_data.get('user_info', {})

        st.markdown(f"""
            <div class='status-card'>
                <div class='status-header'>
                    <div>
                        <h4 style='margin: 0;'><img src="https://cdn.discordapp.com/emojis/1308056946263461989.webp?size=128" style="width: 25px; margin-right: 10px;">{acc_name}</h4>
                        <p style='color: {"#43B581" if monitoring_status else "#ED4245"}'>
                            {"🟢 Monitoring" if monitoring_status else "🔴 Not Monitoring"}
                        </p>
                    </div>
                    <div style='text-align: right;'>
                        <p style='margin: 0;'>Username: {user_info.get('username', 'N/A')}</p>
                        <p style='margin: 0;'>ID: {user_info.get('id', 'N/A')}</p>
                    </div>
                </div>
            </div>
        """, unsafe_allow_html=True)

        # Control buttons and webhook input
        col1, col2 = st.columns([3, 1])
        with col1:
            new_webhook = st.text_input(
                "Webhook Url",
                value=webhook_url,
                type="password",
                key=f"webhook_{acc_name}"
            )
        with col2:
            if not monitoring_status:
                st.markdown('<div style="dm-tracker-button">', unsafe_allow_html=True)
                if st.button("Start Monitoring", key=f"start_{acc_name}"):
                    if not new_webhook:
                        st.error("Please set a webhook URL first!")
                        st.markdown('</div>', unsafe_allow_html=True)
                    else:
                        try:
                            data = load_data()
                            data[st.session_state.user_id]['accounts'][acc_name]['dm_webhook'] = new_webhook
                            data[st.session_state.user_id]['accounts'][acc_name]['dm_monitoring'] = True
                            save_data(data)
                            
                            threading.Thread(
                                target=run_monitor,
                                args=(acc_data, acc_name),
                                daemon=True
                            ).start()
                            
                            st.success("Monitoring started!")
                            time.sleep(1)
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error: {e}")
            else:
                st.markdown('<div class="dm-tracker-button">', unsafe_allow_html=True)
                if st.button("Stop Monitoring", key=f"stop_{acc_name}"):
                    try:
                        data = load_data()
                        data[st.session_state.user_id]['accounts'][acc_name]['dm_monitoring'] = False
                        save_data(data)
                        
                        if acc_name in monitoring_clients:
                            monitoring_clients[acc_name].gateway.close()
                            del monitoring_clients[acc_name]
                        
                        st.success("Monitoring stopped!")
                        time.sleep(1)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")
                    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="dm-tracker-button">', unsafe_allow_html=True)
    if st.button("Refresh Status"):
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)





## ------------------------------------------------------------------------------
def show_token_management(user_data):
    st.markdown("""
        <div style='background-color: rgba(49, 51, 56, 0.2); padding: 20px; border-radius: 15px; margin-bottom: 20px;'>
            <h2>Token Management</h2>
            <p style="margin-top: 0.1px; color: #d1d1d1; font-size: 14px;">
                Verify and manage your Discord tokens
            </p>
        </div>
    """, unsafe_allow_html=True)

    # Token Verification Section
    st.markdown("""
        <div style='background-color: rgba(49, 51, 56, 0.2); padding: 20px; border-radius: 15px; margin-bottom: 20px;'>
            <h3>Token Verification</h3>
        </div>
    """, unsafe_allow_html=True)

    # Token input
    token = st.text_input("Enter Token to Verify", type="password")
    
    if st.button("Verify Token"):
        with st.spinner("Verifying token..."):
            user_info = run_async(verify_token(token))
            if user_info:
                st.success("Token is valid!")
                
                # Display token information in a card
                st.markdown(f"""
                    <div style='background-color: rgba(49, 51, 56, 0.2); padding: 20px; border-radius: 15px; margin: 10px 0;'>
                        <div style='display: flex; justify-content: space-between; align-items: center;'>
                            <div>
                                <h4 style='margin: 0;'>Account Information</h4>
                                <p style='margin: 5px 0;'>Username: {user_info.get('username')}#{user_info.get('discriminator')}</p>
                                <p style='margin: 5px 0;'>ID: {user_info.get('id')}</p>
                                <p style='margin: 5px 0;'>Email: {user_info.get('email', 'Not available')}</p>
                                <p style='margin: 5px 0;'>Phone: {user_info.get('phone', 'Not available')}</p>
                                <p style='margin: 5px 0;'>2FA Enabled: {user_info.get('mfa_enabled', False)}</p>
                                <p style='margin: 5px 0;'>Verified: {user_info.get('verified', False)}</p>
                            </div>
                        </div>
                    </div>
                """, unsafe_allow_html=True)
            else:
                st.error("Invalid token!")

    # Token Replacement Section
    st.markdown("""
        <div style='background-color: rgba(49, 51, 56, 0.2); padding: 20px; border-radius: 15px; margin: 20px 0;'>
            <h3>Token Replacement</h3>
        </div>
    """, unsafe_allow_html=True)

    accounts = user_data.get('accounts', {})
    if not accounts:
        st.warning("No accounts available.")
        return

    selected_account = st.selectbox("Select Account", list(accounts.keys()))
    if selected_account:
        account_data = accounts[selected_account]
        current_token = account_data.get('token', '')
        
        st.markdown(f"""
            <div style='background-color: rgba(49, 51, 56, 0.2); padding: 20px; border-radius: 15px; margin: 10px 0;'>
                <h4>Current Token Information</h4>
                <p>Account: {selected_account}</p>
                <p>Current Token : {current_token[:100]}</p>
            </div>
        """, unsafe_allow_html=True)

        new_token = st.text_input("New Token", type="password")
        
        if st.button("Replace Token"):
            with st.spinner("Verifying new token..."):
                verification = run_async(verify_token(new_token))
                if verification:
                    try:
                        data = load_data()
                        data[st.session_state.user_id]['accounts'][selected_account]['token'] = new_token
                        save_data(data)
                        st.success("Token replaced successfully!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error replacing token: {str(e)}")
                else:
                    st.error("Invalid new token!")

async def verify_token(token):
    """Verify token and return user information"""
    async with aiohttp.ClientSession() as session:
        headers = {
            'Authorization': token,
            'Content-Type': 'application/json'
        }
        try:
            async with session.get('https://discord.com/api/v9/users/@me', headers=headers) as response:
                if response.status == 200:
                    return await response.json()
                return None
        except Exception as e:
            print(f"Error verifying token: {e}")
            return None

## ------------------------------------------------------------------------------

## ------------------------------------------------------------------------------

## ------------------------------------------------------------------------------
## ------------------------------------------------------------------------------

def main():
    st.set_page_config(
        page_title="Autopost Dashboard",
        page_icon="logo.png",
        layout="wide"
    )
    
    # Check for existing session
    if not st.session_state.logged_in:
        session_data = load_session()
        if session_data:
            st.session_state.logged_in = True
            st.session_state.user_id = session_data['user_id']
    
    if not st.session_state.logged_in:
        show_login_page()
    else:
        show_dashboard()


if __name__ == "__main__":
    main()

