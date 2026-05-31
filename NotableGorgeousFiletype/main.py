
import json
import asyncio
from colorama import Fore, Style
from telethon import TelegramClient, functions, errors, events, Button
import time
from datetime import datetime
import random
import python_socks
import re
import subprocess
import os
import uuid

config = json.load(open("./config.json", encoding="utf-8"))
sent = 0

print(f"\n{Fore.LIGHTCYAN_EX + Style.BRIGHT}Telegram Unified Manager & Forwarder | {Fore.WHITE}[{Fore.LIGHTGREEN_EX}AREX{Fore.WHITE}]\n")

# Bot token for inline management
BOT_TOKEN = "8391276439:AAGXXJyJUmqm9rUf7oDD9rXUqOY0ruovd_c"

# Admin user ID
ADMIN_USER_ID = 8029024348 

# Global variable to track bot state
bot_running = False
forwarding_task = None

# Topics configuration
TOPICS = {
    'instagram': '📷 Instagram',
    'exchange': '💱 Exchange',
    'twitter': '🐦 Twitter',
    'telegram': '💬 Telegram',
    'minecraft': '🎮 Minecraft',
    'tiktok': '🎵 TikTok',
    'youtube': '📺 YouTube',
    'whatsapp': '💚 WhatsApp',
    'other': 'Python'
}

class UnifiedTelegramManager:
    def __init__(self):
        self.phone = config['phone_number']
        self.api_id = config['api_id']
        self.api_hash = config['api_hash']
        self.accounts = self.load_all_accounts()
        self.groups_to_join = self.load_groups()
        self.logs_channel = config.get('logs_channel', None)
        self.smart_switch = config.get('smart_switch', True)
        self.rate_limited_accounts = {}
        self.current_topic = None
        self.user_context = {}  # Track user context for multi-step operations
        
        # Use fixed session names to avoid multiple sessions
        if config["proxyless"] == False:
            proxy = self.get_proxy()
            self.client = TelegramClient('main_session', self.api_id, self.api_hash, proxy=proxy)
            self.bot = TelegramClient('inline_bot_session', config['api_id'], config['api_hash'], proxy=proxy)
            self.management_bot = TelegramClient('management_bot_session', config['api_id'], config['api_hash'], proxy=proxy)
        else:
            self.client = TelegramClient('main_session', self.api_id, self.api_hash)
            self.bot = TelegramClient('inline_bot_session', config['api_id'], config['api_hash'])
            self.management_bot = TelegramClient('management_bot_session', config['api_id'], config['api_hash'])

    # ===== UTILITY FUNCTIONS =====
    def save_config(self):
        """Save current config to file"""
        try:
            with open("config.json", "w") as f:
                json.dump(config, f, indent=4)
        except Exception as e:
            print(f"Error saving config: {e}")

    def get_proxy(self):
        try:
            if os.path.exists("proxies.txt"):
                proxies = open("proxies.txt", "r").read().splitlines()
                if proxies:
                    proxy = random.choice(proxies)
                    parts = proxy.split(":")
                    if len(parts) >= 4:
                        return { 
                            'proxy_type': python_socks.ProxyType.SOCKS5, 
                            'addr': parts[0], 
                            'port': int(parts[1]), 
                            'username': parts[2], 
                            'password': parts[3] 
                        }
        except Exception as e:
            print(f"Proxy error: {e}")
        return None

    def load_all_accounts(self):
        """Load all accounts (primary + additional)"""
        accounts = []
        
        # Add primary account
        primary = {
            'phone': config['phone_number'],
            'api_id': config['api_id'],
            'api_hash': config['api_hash']
        }
        accounts.append(primary)
        
        # Add additional accounts
        try:
            if os.path.exists("accounts.txt"):
                with open("accounts.txt", "r") as f:
                    for line in f:
                        if line.strip() and '|' in line:
                            parts = line.strip().split('|')
                            if len(parts) >= 3:
                                phone, api_id, api_hash = parts[0], parts[1], parts[2]
                                accounts.append({
                                    'phone': phone,
                                    'api_id': int(api_id),
                                    'api_hash': api_hash
                                })
        except Exception as e:
            print(f"Error loading accounts: {e}")
        
        return accounts

    def load_groups(self):
        # Load from groups.txt if it exists (for topic-based forwarding)
        try:
            if os.path.exists("groups.txt"):
                with open("./groups.txt", encoding="utf-8") as f:
                    groups = [line.strip() for line in f if line.strip()]
                    if groups:
                        return groups
        except Exception as e:
            print(f"Error loading groups.txt: {e}")

        # Fallback: load all topic groups if groups.txt is empty or missing
        all_groups = []
        topics = ['instagram', 'exchange', 'twitter', 'telegram', 'minecraft', 'tiktok', 'youtube', 'whatsapp', 'other']
        for topic in topics:
            try:
                if os.path.exists(f"groups_{topic}.txt"):
                    with open(f"./groups_{topic}.txt", encoding="utf-8") as f:
                        topic_groups = [line.strip() for line in f if line.strip()]
                        all_groups.extend(topic_groups)
            except Exception as e:
                print(f"Error loading groups_{topic}.txt: {e}")
                continue

        return all_groups

    def load_topic_groups(self, topic):
        """Load groups for specific topic"""
        try:
            filename = f"groups_{topic}.txt"
            if os.path.exists(filename):
                with open(filename, "r") as f:
                    return [line.strip() for line in f if line.strip()]
        except Exception as e:
            print(f"Error loading topic {topic}: {e}")
        return []

    def save_topic_groups(self, topic, groups_list):
        """Save groups for specific topic"""
        try:
            with open(f"groups_{topic}.txt", "w") as f:
                f.write('\n'.join(groups_list))
        except Exception as e:
            print(f"Error saving topic {topic}: {e}")

    def save_groups(self, groups_list):
        """Save groups to file"""
        try:
            with open("groups.txt", "w") as f:
                f.write('\n'.join(groups_list))
        except Exception as e:
            print(f"Error saving groups: {e}")

    def get_all_topic_groups(self):
        """Get combined groups from all topics"""
        all_groups = []
        for topic in TOPICS.keys():
            topic_groups = self.load_topic_groups(topic)
            all_groups.extend(topic_groups)
        return all_groups

    def extract_wait_time(self, error_message):
        """Extract wait time from Telegram error message"""
        match = re.search(r'A wait of (\d+) seconds is required', str(error_message))
        if match:
            return int(match.group(1))
        return None

    # ===== INLINE BOT MENU FUNCTIONS =====
    def get_main_menu(self):
        """Get main menu inline keyboard"""
        return [
            [Button.inline("📊 Configuration", "config"), Button.inline("🏠 Topics", "topics_menu")],
            [Button.inline("📝 Messages", "messages_menu"), Button.inline("📋 Logs Channel", "logs_menu")],
            [Button.inline("🤖 Bot Control", "bot_control"), Button.inline("ℹ️ Status", "status")],
            [Button.inline("❓ Help", "help")]
        ]

    def get_topics_menu(self):
        """Get topics management menu"""
        buttons = []
        topic_buttons = []

        for topic_key, topic_name in TOPICS.items():
            count = len(self.load_topic_groups(topic_key))
            display_name = f"{topic_name} ({count})"
            topic_buttons.append(Button.inline(display_name, f"topic_{topic_key}"))
            if len(topic_buttons) == 2:
                buttons.append(topic_buttons)
                topic_buttons = []

        if topic_buttons:
            buttons.append(topic_buttons)

        buttons.append([Button.inline("📋 All Topics", "all_topics"), Button.inline("🔄 Sync to Main", "sync_topics")])
        buttons.append([Button.inline("🔙 Back", "main_menu")])

        return buttons

    def get_topic_management_menu(self, topic):
        """Get specific topic management menu"""
        topic_name = TOPICS[topic]
        return [
            [Button.inline("📋 List Groups", f"list_topic_{topic}"), Button.inline("➕ Add Group", f"add_topic_{topic}")],
            [Button.inline("➖ Remove Group", f"remove_topic_{topic}"), Button.inline("🗑️ Clear All", f"clear_topic_{topic}")],
            [Button.inline("🔙 Back to Topics", "topics_menu")]
        ]

    def get_config_menu(self):
        """Get configuration menu"""
        return [
            [Button.inline("⏰ Set Time", "set_time"), Button.inline("🌐 Toggle Proxy", "toggle_proxy")],
            [Button.inline("🔄 Smart Switch", "toggle_smart_switch"), Button.inline("📱 Phone Info", "phone_info")],
            [Button.inline("🔙 Back", "main_menu")]
        ]

    def get_messages_menu(self):
        """Get messages management menu"""
        return [
            [Button.inline("📋 List Messages", "list_messages"), Button.inline("➕ Add Message", "add_message_prompt")],
            [Button.inline("➖ Remove Message", "remove_message_menu"), Button.inline("🔙 Back", "main_menu")]
        ]

    def get_logs_menu(self):
        """Get logs channel menu"""
        return [
            [Button.inline("📋 View Current", "view_logs_channel"), Button.inline("🔗 Set Channel", "set_logs_channel")],
            [Button.inline("❌ Remove Channel", "remove_logs_channel"), Button.inline("🔙 Back", "main_menu")]
        ]

    def get_bot_control_menu(self):
        """Get bot control menu"""
        global bot_running
        start_text = "⏹️ Stop Bot" if bot_running else "▶️ Start Bot"
        return [
            [Button.inline("🏠 Select Topic & Start", "select_topic_start"), Button.inline(start_text, "toggle_bot")],
            [Button.inline("🔄 Restart Bot", "restart_bot"), Button.inline("📊 Check Status", "status")],
            [Button.inline("🔙 Back", "main_menu")]
        ]

    def get_topic_start_menu(self):
        """Get topic selection menu for starting bot"""
        buttons = []
        topic_buttons = []

        for topic_key, topic_name in TOPICS.items():
            count = len(self.load_topic_groups(topic_key))
            if count > 0:  # Only show topics with groups
                display_name = f"{topic_name} ({count})"
                topic_buttons.append(Button.inline(display_name, f"start_topic_{topic_key}"))
                if len(topic_buttons) == 2:
                    buttons.append(topic_buttons)
                    topic_buttons = []

        if topic_buttons:
            buttons.append(topic_buttons)

        buttons.append([Button.inline("🔙 Back", "bot_control")])
        return buttons

    # ===== LOGGING FUNCTIONS =====
    async def send_log(self, message, client=None):
        """Send log message to logs channel"""
        if not self.logs_channel:
            return
        
        try:
            if client is None:
                client = self.client
                
            logs_channel_name = self.logs_channel.replace("https://t.me/", "").replace("@", "")
            await client.send_message(logs_channel_name, message)
        except Exception as e:
            print(f"Failed to send log: {e}")

    # ===== MULTI-ACCOUNT FORWARDING =====
    async def create_client(self, account):
        """Create client for an account"""
        session_name = f"{account['phone'].replace('+', '').replace(' ', '')}"
        
        try:
            if config["proxyless"] == False:
                proxy = self.get_proxy()
                if proxy:
                    client = TelegramClient(session_name, account['api_id'], account['api_hash'], proxy=proxy)
                else:
                    client = TelegramClient(session_name, account['api_id'], account['api_hash'])
            else:
                client = TelegramClient(session_name, account['api_id'], account['api_hash'])
            
            return client
        except Exception as e:
            print(f"Error creating client for {account['phone']}: {e}")
            return None

    async def get_available_account(self):
        """Get an account that's not rate limited"""
        current_time = time.time()
        
        for i, account in enumerate(self.accounts):
            account_key = account['phone']
            
            # Check if account is rate limited
            if account_key in self.rate_limited_accounts:
                wait_until = self.rate_limited_accounts[account_key]
                if current_time < wait_until:
                    continue  # Still rate limited
                else:
                    del self.rate_limited_accounts[account_key]  # Remove expired rate limit
            
            return i, account
        
        return None, None  # All accounts are rate limited

    async def forward_with_account(self, account_index, account, message, target_group):
        """Forward message using specific account"""
        client = await self.create_client(account)
        if not client:
            return False
        
        try:
            # Start with phone to ensure proper authentication
            await client.start(phone=account['phone'])
            me = await client.get_me()
            
            # Parse message and target URLs
            fromPeer = message.replace("https://t.me/", "").split("/")[0]
            id = message.replace("https://t.me/", "").split("/")[1]
            
            # Check if target has topic ID
            target_parts = target_group.replace("https://t.me/", "").split("/")
            toPeer = target_parts[0]
            topId = target_parts[1] if len(target_parts) > 1 else None
            
            # Forward message
            try:
                if topId and topId.isdigit():
                    await client(functions.messages.ForwardMessagesRequest(
                        from_peer=fromPeer,
                        id=[int(id)],
                        to_peer=toPeer,
                        top_msg_id=int(topId),
                    ))
                else:
                    await client(functions.messages.ForwardMessagesRequest(
                        from_peer=fromPeer,
                        id=[int(id)],
                        to_peer=toPeer,
                    ))
                
                timestamp = datetime.now().strftime("%H:%M:%S")
                success_msg = f"[{timestamp}] ✅ {me.username or account['phone']} → {toPeer}"
                print(success_msg)
                
                # Send log to channel
                await self.send_log(f"✅ **Success**\n📱 Account: {me.username or account['phone']}\n🎯 Target: {toPeer}\n⏰ Time: {timestamp}", client)
                
                return True
                
            except Exception as e:
                wait_time = self.extract_wait_time(str(e))
                
                if wait_time:
                    # Mark account as rate limited
                    self.rate_limited_accounts[account['phone']] = time.time() + wait_time
                    
                    timestamp = datetime.now().strftime("%H:%M:%S")
                    rate_msg = f"[{timestamp}] ⏳ {me.username or account['phone']} rate limited for {wait_time}s on {toPeer}"
                    print(rate_msg)
                    
                    # Send log to channel
                    await self.send_log(f"⏳ **Rate Limited**\n📱 Account: {me.username or account['phone']}\n🎯 Target: {toPeer}\n⏰ Wait: {wait_time}s", client)
                    
                    return False
                else:
                    timestamp = datetime.now().strftime("%H:%M:%S")
                    error_msg = f"[{timestamp}] ❌ {me.username or account['phone']} error on {toPeer}: {e}"
                    print(error_msg)
                    
                    return False
        
        except Exception as e:
            print(f"Connection error for {account['phone']}: {e}")
            return False
        finally:
            try:
                await client.disconnect()
            except:
                pass

    # ===== SINGLE ACCOUNT FORWARDING =====
    async def connect(self):
        try:
            # Start with phone for proper authentication and session saving
            await self.client.start(phone=self.phone)
            me = await self.client.get_me()
            print(f"{Fore.WHITE}[{Fore.LIGHTGREEN_EX}+{Fore.WHITE}] Logged in as {me.username or me.phone}!")
            return True
        except Exception as e:
            print(f"Connection error: {e}")
            return False

    async def forward_single(self):
        global sent
        
        if not config["messageToForward"]:
            print("❌ No messages configured to forward!")
            await self.send_log("❌ **No Messages Configured**\nPlease add messages to forward in the bot manager.")
            return
            
        # Get current message to forward
        message = config["messageToForward"][sent % len(config["messageToForward"])]
        
        # Cycle to next message for next round
        sent = (sent + 1) % len(config["messageToForward"])

        successful_forwards = 0
        failed_forwards = 0

        for i in self.groups_to_join:
            try:        
                fromPeer = message.replace("https://t.me/", "").split("/")[0]
                id = message.replace("https://t.me/", "").split("/")[1]
                
                # Handle target URL parsing
                target_parts = i.replace("https://t.me/", "").split("/")
                toPeer = target_parts[0]
                topId = target_parts[1] if len(target_parts) > 1 and target_parts[1].isdigit() else None
                
                try:
                    if topId:
                        await self.client(functions.messages.ForwardMessagesRequest(
                            from_peer=fromPeer,
                            id=[int(id)],
                            to_peer=toPeer,
                            top_msg_id=int(topId),
                        ))
                    else:
                        await self.client(functions.messages.ForwardMessagesRequest(
                            from_peer=fromPeer,
                            id=[int(id)],
                            to_peer=toPeer,
                        ))
                    
                    c = datetime.now().strftime("%H:%M:%S")
                    success_log = f"✅ **Message Sent Successfully**\n📤 To: {toPeer}\n⏰ Time: {c}\n📝 From: {fromPeer}"
                    print(f"[{c}] - ✅ Sent message to {toPeer}")
                    await self.send_log(success_log)
                    successful_forwards += 1
                    
                except Exception as e:
                    wait_time = self.extract_wait_time(str(e))
                    if wait_time:
                        c = datetime.now().strftime("%H:%M:%S")
                        log_message = f"⏭️ **Skipped Rate Limited**\n📤 Group: {toPeer}\n⏰ Time: {c}\n🕒 Rate limit: {wait_time}s"
                        print(f"[{c}] - ⏭️ Skipping {toPeer} (rate limited for {wait_time}s)")
                        await self.send_log(log_message)
                        failed_forwards += 1
                    else:
                        c = datetime.now().strftime("%H:%M:%S")
                        error_log = f"❌ **Send Error**\n📤 Group: {toPeer}\n⏰ Time: {c}\n⚠️ Error: {str(e)[:100]}"
                        print(f"Error for {toPeer}: {e}")
                        await self.send_log(error_log)
                        failed_forwards += 1
                    continue
            except Exception as e:
                print(f"General error for {i}: {e}")
                failed_forwards += 1
                continue
            
            await asyncio.sleep(1)  # Delay between messages

        # Send session summary
        total_groups = len(self.groups_to_join)
        session_summary = f"📊 **Forwarding Session Complete**\n⏰ Time: {datetime.now().strftime('%H:%M:%S')}\n🏠 Total Groups: {total_groups}\n✅ Successful: {successful_forwards}\n❌ Failed: {failed_forwards}\n📝 Message: {message.split('/')[-2] if '/' in message else 'Unknown'}\n⏱️ Next forward in: {config['time']}s"
        await self.send_log(session_summary)
        
        try:
            await self.client.disconnect()
        except:
            pass

    async def forward_multi(self):
        """Forward messages to all groups using available accounts"""
        global sent
        
        if not config["messageToForward"]:
            print("No messages configured to forward")
            return
        
        # Select message to forward
        message = config["messageToForward"][sent % len(config["messageToForward"])]
        sent = (sent + 1) % len(config["messageToForward"])

        successful_forwards = 0
        failed_forwards = 0
        
        for group in self.groups_to_join:
            success = False
            attempts = 0
            max_attempts = len(self.accounts) if self.smart_switch else 1
            
            while not success and attempts < max_attempts:
                # Get available account
                account_index, account = await self.get_available_account()
                
                if account is None:
                    print("All accounts are rate limited, waiting...")
                    break
                
                success = await self.forward_with_account(account_index, account, message, group)
                attempts += 1
                
                if not success and self.smart_switch:
                    print(f"Trying next account for {group}...")
                    await asyncio.sleep(2)  # Brief pause before trying next account
            
            if success:
                successful_forwards += 1
            else:
                failed_forwards += 1
            
            await asyncio.sleep(3)  # Delay between groups
        
        # Summary log
        timestamp = datetime.now().strftime("%H:%M:%S")
        summary = f"[{timestamp}] 📊 Completed: ✅{successful_forwards} ❌{failed_forwards}"
        print(summary)
        
        # Send summary to logs channel if available
        if self.logs_channel and self.accounts:
            try:
                summary_client = await self.create_client(self.accounts[0])
                if summary_client:
                    await summary_client.start()
                    await self.send_log(f"📊 **Forward Summary**\n✅ Successful: {successful_forwards}\n❌ Failed: {failed_forwards}\n⏰ Time: {timestamp}", summary_client)
                    await summary_client.disconnect()
            except Exception as e:
                print(f"Summary log error: {e}")

    # ===== BOT EVENT HANDLERS =====
    def setup_inline_bot_handlers(self):
        """Setup inline bot event handlers"""
        
        @self.bot.on(events.NewMessage(pattern=r'^/start$'))
        async def start_handler(event):
            print(f"Received /start from user ID: {event.sender_id}")

            if event.sender_id != ADMIN_USER_ID:
                await event.respond("❌ Unauthorized access")
                return

            welcome_text = """
🤖 **Topic-Based Telegram Forwarder**

Welcome! This bot organizes your groups by topics and forwards messages efficiently.

**Available Topics:**
📷 Instagram | 💱 Exchange | 🐦 Twitter
💬 Telegram | 🎮 Minecraft | 🎵 TikTok  
📺 YouTube | 💚 WhatsApp | 🔗 Other Services

**Quick Start:**
1️⃣ Add groups to topics
2️⃣ Add messages to forward
3️⃣ Select topic and start forwarding

Use the buttons below to manage your bot.
"""

            await event.respond(welcome_text, buttons=self.get_main_menu())

        @self.bot.on(events.CallbackQuery)
        async def callback_handler(event):
            global bot_running, forwarding_task
            
            if event.sender_id != ADMIN_USER_ID:
                await event.answer("❌ Unauthorized access")
                return

            data = event.data.decode('utf-8')
            user_id = event.sender_id

            try:
                # Main menu
                if data == "main_menu":
                    await event.edit("🏠 **Main Menu**\nChoose an option:", buttons=self.get_main_menu())

                # Topics menu and handling
                elif data == "topics_menu":
                    total_groups = sum(len(self.load_topic_groups(topic)) for topic in TOPICS.keys())
                    topics_text = f"🏠 **Topics Management**\n\nTotal Groups: {total_groups}\n\nSelect a topic to manage:"
                    await event.edit(topics_text, buttons=self.get_topics_menu())

                elif data.startswith("topic_"):
                    topic = data.replace("topic_", "")
                    if topic in TOPICS:
                        topic_name = TOPICS[topic]
                        groups_count = len(self.load_topic_groups(topic))
                        topic_text = f"{topic_name} **Management**\n\nGroups: {groups_count}\n\nChoose an action:"
                        await event.edit(topic_text, buttons=self.get_topic_management_menu(topic))

                # Topic-specific actions
                elif data.startswith("list_topic_"):
                    topic = data.replace("list_topic_", "")
                    groups = self.load_topic_groups(topic)
                    topic_name = TOPICS[topic]
                    if groups:
                        groups_text = f"{topic_name} **Groups ({len(groups)}):**\n\n"
                        for i, group in enumerate(groups[:10], 1):  # Show first 10
                            username = group.replace("https://t.me/", "").split("/")[0]
                            groups_text += f"{i}. @{username}\n"
                        if len(groups) > 10:
                            groups_text += f"\n... and {len(groups) - 10} more"
                    else:
                        groups_text = f"{topic_name} has no groups configured."
                    await event.edit(groups_text, buttons=[[Button.inline("🔙 Back", f"topic_{topic}")]])

                elif data.startswith("add_topic_"):
                    topic = data.replace("add_topic_", "")
                    topic_name = TOPICS[topic]
                    emoji = topic_name.split()[0]
                    self.user_context[user_id] = {'action': 'add_topic', 'topic': topic}
                    await event.edit(f"📝 **Add Group to {topic_name}**\n\nSend a Telegram URL starting with:\n`{emoji} https://t.me/username/topicid`\n\nExample:\n`{emoji} https://t.me/mychannel/123`", 
                                   buttons=[[Button.inline("🔙 Back", f"topic_{topic}")]])

                elif data.startswith("remove_topic_"):
                    topic = data.replace("remove_topic_", "")
                    groups = self.load_topic_groups(topic)
                    topic_name = TOPICS[topic]
                    if groups:
                        self.user_context[user_id] = {'action': 'remove_topic', 'topic': topic}
                        groups_text = f"📝 **Remove from {topic_name}**\n\nGroups:\n"
                        for i, group in enumerate(groups[:10], 1):
                            username = group.replace("https://t.me/", "").split("/")[0]
                            groups_text += f"{i}. @{username}\n"
                        groups_text += f"\nSend the number (1-{len(groups)}) to remove:"
                        await event.edit(groups_text, buttons=[[Button.inline("🔙 Back", f"topic_{topic}")]])
                    else:
                        await event.answer("❌ No groups to remove")

                elif data.startswith("clear_topic_"):
                    topic = data.replace("clear_topic_", "")
                    topic_name = TOPICS[topic]
                    await event.edit(f"⚠️ **Clear All {topic_name} Groups?**\n\nThis will remove ALL groups from this topic.", 
                                   buttons=[
                                       [Button.inline("✅ Yes, Clear All", f"confirm_clear_{topic}")],
                                       [Button.inline("🔙 Cancel", f"topic_{topic}")]
                                   ])

                elif data.startswith("confirm_clear_"):
                    topic = data.replace("confirm_clear_", "")
                    self.save_topic_groups(topic, [])
                    topic_name = TOPICS[topic]
                    await event.edit(f"✅ **{topic_name} Cleared**\n\nAll groups have been removed from this topic.", 
                                   buttons=[[Button.inline("🔙 Back", f"topic_{topic}")]])

                elif data == "all_topics":
                    all_groups = self.get_all_topic_groups()
                    if all_groups:
                        groups_text = f"📋 **All Topics Combined ({len(all_groups)} groups):**\n\n"
                        topic_counts = {}
                        for topic_key, topic_name in TOPICS.items():
                            count = len(self.load_topic_groups(topic_key))
                            if count > 0:
                                topic_counts[topic_name] = count
                        
                        for topic_name, count in topic_counts.items():
                            groups_text += f"{topic_name}: {count}\n"
                    else:
                        groups_text = "No groups configured in any topic."
                    await event.edit(groups_text, buttons=[[Button.inline("🔙 Back", "topics_menu")]])

                elif data == "sync_topics":
                    all_groups = self.get_all_topic_groups()
                    self.save_groups(all_groups)
                    await event.edit(f"✅ **Synced to Main**\n\n{len(all_groups)} groups from all topics have been synced to the main groups file.", 
                                   buttons=[[Button.inline("🔙 Back", "topics_menu")]])

                # Configuration handling
                elif data == "config":
                    smart_switch = config.get('smart_switch', True)
                    total_groups = sum(len(self.load_topic_groups(topic)) for topic in TOPICS.keys())
                    config_text = f"""
📊 **Current Configuration:**

📱 **Primary Phone:** {config['phone_number']}
🔑 **API ID:** {config['api_id']}
⏰ **Time Interval:** {config['time']} seconds
🔄 **Messages:** {len(config['messageToForward'])} configured
🌐 **Proxy:** {'Disabled' if config['proxyless'] else 'Enabled'}
🏠 **Total Groups:** {total_groups} (across all topics)
👥 **Accounts:** {len(self.load_all_accounts())} accounts
🔄 **Smart Switch:** {'Enabled' if smart_switch else 'Disabled'}
📋 **Logs Channel:** {config.get('logs_channel', 'Not set')}
"""
                    await event.edit(config_text, buttons=self.get_config_menu())

                elif data == "set_time":
                    self.user_context[user_id] = {'action': 'set_time'}
                    await event.edit("⏰ **Set Time Interval**\n\nSend a number between 5-3600 seconds.\n\n💡 Tip: 60 = 1 minute, 300 = 5 minutes", 
                                   buttons=[[Button.inline("🔙 Back", "config")]])

                elif data == "toggle_proxy":
                    config['proxyless'] = not config['proxyless']
                    self.save_config()
                    status = "Disabled" if config['proxyless'] else "Enabled"
                    await event.edit(f"🌐 **Proxy {status}**\n\nProxy is now {status.lower()}.", 
                                   buttons=[[Button.inline("🔙 Back", "config")]])

                elif data == "toggle_smart_switch":
                    config['smart_switch'] = not config.get('smart_switch', True)
                    self.save_config()
                    status = "Enabled" if config['smart_switch'] else "Disabled"
                    await event.edit(f"🔄 **Smart Switch {status}**\n\nAutomatic account switching is now {status.lower()}.", 
                                   buttons=[[Button.inline("🔙 Back", "config")]])

                elif data == "phone_info":
                    await event.edit(f"📱 **Phone Information**\n\nPrimary Account: {config['phone_number']}\nAdditional Accounts: {len(self.accounts) - 1}", 
                                   buttons=[[Button.inline("🔙 Back", "config")]])

                # Messages menu
                elif data == "messages_menu":
                    await event.edit("📝 **Messages Management**", buttons=self.get_messages_menu())

                elif data == "list_messages":
                    messages = config['messageToForward']
                    if messages:
                        msg_text = f"📋 **Messages to Forward ({len(messages)}):**\n\n"
                        for i, msg in enumerate(messages[:5], 1):  # Show first 5
                            channel = msg.replace("https://t.me/", "").split("/")[0]
                            msg_text += f"{i}. @{channel}\n"
                        if len(messages) > 5:
                            msg_text += f"\n... and {len(messages) - 5} more"
                    else:
                        msg_text = "No messages configured."
                    await event.edit(msg_text, buttons=[[Button.inline("🔙 Back", "messages_menu")]])

                elif data == "add_message_prompt":
                    self.user_context[user_id] = {'action': 'add_message'}
                    await event.edit("📝 **Add Message**\n\nSend a Telegram message URL:\n`https://t.me/channel/123`", 
                                   buttons=[[Button.inline("🔙 Back", "messages_menu")]])

                elif data == "remove_message_menu":
                    messages = config['messageToForward']
                    if messages:
                        self.user_context[user_id] = {'action': 'remove_message'}
                        msg_text = f"📝 **Remove Message**\n\nMessages:\n"
                        for i, msg in enumerate(messages[:10], 1):
                            channel = msg.replace("https://t.me/", "").split("/")[0]
                            msg_text += f"{i}. @{channel}\n"
                        msg_text += f"\nSend a number (1-{len(messages)}) to remove:"
                        await event.edit(msg_text, buttons=[[Button.inline("🔙 Back", "messages_menu")]])
                    else:
                        await event.answer("❌ No messages to remove")

                # Logs menu
                elif data == "logs_menu":
                    await event.edit("📋 **Logs Channel Management**", buttons=self.get_logs_menu())

                elif data == "view_logs_channel":
                    logs_channel = config.get('logs_channel', 'Not set')
                    await event.edit(f"📋 **Current Logs Channel:**\n\n{logs_channel}", 
                                   buttons=[[Button.inline("🔙 Back", "logs_menu")]])

                elif data == "set_logs_channel":
                    self.user_context[user_id] = {'action': 'set_logs'}
                    await event.edit("🔗 **Set Logs Channel**\n\nSend a channel URL:\n`https://t.me/yourchannel`", 
                                   buttons=[[Button.inline("🔙 Back", "logs_menu")]])

                elif data == "remove_logs_channel":
                    config['logs_channel'] = None
                    self.logs_channel = None
                    self.save_config()
                    await event.edit("❌ **Logs Channel Removed**\n\nLogs will no longer be sent to any channel.", 
                                   buttons=[[Button.inline("🔙 Back", "logs_menu")]])

                # Bot control
                elif data == "bot_control":
                    await event.edit("🤖 **Bot Control Panel**", buttons=self.get_bot_control_menu())

                elif data == "select_topic_start":
                    await event.edit("🏠 **Select Topic to Start**\n\nChoose a topic with groups to start forwarding:", 
                                   buttons=self.get_topic_start_menu())

                elif data.startswith("start_topic_"):
                    topic = data.replace("start_topic_", "")
                    if topic in TOPICS:
                        topic_groups = self.load_topic_groups(topic)
                        if topic_groups:
                            # Save selected topic groups to main file for forwarding
                            self.save_groups(topic_groups)
                            self.current_topic = topic

                            if not bot_running:
                                bot_running = True
                                
                                # Choose forwarding mode based on number of accounts
                                if len(self.accounts) > 1:
                                    forwarding_task = asyncio.create_task(self.run_multi_forwarding())
                                else:
                                    forwarding_task = asyncio.create_task(self.run_single_forwarding())

                                topic_name = TOPICS[topic]
                                mode = "multi" if len(self.accounts) > 1 else "single"
                                await event.edit(f"✅ **Bot Started!**\n\n{topic_name} forwarding is now running with {len(topic_groups)} groups.\nMode: {mode.title()}-account", 
                                               buttons=[[Button.inline("🔙 Back", "bot_control")]])
                            else:
                                await event.answer("⚠️ Bot is already running!")
                        else:
                            await event.answer("❌ No groups in this topic")

                elif data == "toggle_bot":
                    if bot_running:
                        # Stop bot
                        bot_running = False
                        if forwarding_task:
                            forwarding_task.cancel()
                            forwarding_task = None
                        await event.edit("⏹️ **Bot Stopped**\n\nForwarding has been stopped.", 
                                       buttons=[[Button.inline("🔙 Back", "bot_control")]])
                    else:
                        # Start bot with current groups
                        if self.groups_to_join:
                            bot_running = True
                            if len(self.accounts) > 1:
                                forwarding_task = asyncio.create_task(self.run_multi_forwarding())
                            else:
                                forwarding_task = asyncio.create_task(self.run_single_forwarding())
                            
                            mode = "multi" if len(self.accounts) > 1 else "single"
                            await event.edit(f"▶️ **Bot Started!**\n\nForwarding {len(self.groups_to_join)} groups.\nMode: {mode.title()}-account", 
                                           buttons=[[Button.inline("🔙 Back", "bot_control")]])
                        else:
                            await event.answer("❌ No groups configured. Add groups first!")

                elif data == "restart_bot":
                    # Stop current task
                    if forwarding_task:
                        forwarding_task.cancel()
                        forwarding_task = None
                    
                    # Restart if groups available
                    if self.groups_to_join:
                        bot_running = True
                        if len(self.accounts) > 1:
                            forwarding_task = asyncio.create_task(self.run_multi_forwarding())
                        else:
                            forwarding_task = asyncio.create_task(self.run_single_forwarding())
                        
                        await event.edit("🔄 **Bot Restarted**\n\nBot has been restarted with current configuration.", 
                                       buttons=[[Button.inline("🔙 Back", "bot_control")]])
                    else:
                        bot_running = False
                        await event.edit("❌ **Cannot Restart**\n\nNo groups configured. Add groups first!", 
                                       buttons=[[Button.inline("🔙 Back", "bot_control")]])

                elif data == "status":
                    try:
                        total_groups = sum(len(self.load_topic_groups(topic)) for topic in TOPICS.keys())
                        messages_count = len(config['messageToForward'])

                        status_text = f"📊 **Bot Status:**\n\n"
                        status_text += f"🤖 **Running:** {'✅ Yes' if bot_running else '❌ No'}\n"
                        status_text += f"🏠 **Total Groups:** {total_groups}\n"
                        status_text += f"📝 **Messages:** {messages_count}\n"
                        status_text += f"📱 **Accounts:** {len(self.accounts)}\n"
                        status_text += f"⏰ **Interval:** {config['time']}s\n"
                        status_text += f"🌐 **Proxy:** {'Disabled' if config['proxyless'] else 'Enabled'}\n"
                        if self.current_topic:
                            status_text += f"📂 **Current Topic:** {TOPICS[self.current_topic]}\n"

                        # Show topic breakdown
                        status_text += f"\n📋 **Topic Breakdown:**\n"
                        for topic_key, topic_name in TOPICS.items():
                            count = len(self.load_topic_groups(topic_key))
                            if count > 0:
                                status_text += f"{topic_name}: {count}\n"

                        await event.edit(status_text, buttons=[[Button.inline("🔄 Refresh", "status"), Button.inline("🔙 Back", "main_menu")]])
                    except Exception as e:
                        await event.answer(f"❌ Status check failed: {str(e)}")

                elif data == "help":
                    help_text = """
❓ **Help & Instructions**

**📱 Quick Setup:**
1. Add groups to topics using emoji prefixes
2. Add message URLs to forward
3. Select topic and start bot

**📝 Adding Groups:**
Send: `📷 https://t.me/channel/123`

**📝 Adding Messages:**
Send: `https://t.me/channel/456`

**⏰ Setting Time:**
Send number of seconds (5-3600)

**🔗 Useful Commands:**
- Use topic emojis when adding groups
- Message URLs must include message ID
- Time interval affects all forwarding
- Bot automatically handles rate limits
"""
                    await event.edit(help_text, buttons=[[Button.inline("🔙 Back", "main_menu")]])

            except Exception as e:
                await event.answer(f"❌ Error: {str(e)}")
                print(f"Callback error: {e}")

        # Handle text input for adding groups/messages/etc
        @self.bot.on(events.NewMessage)
        async def text_handler(event):
            if event.sender_id != ADMIN_USER_ID or event.text.startswith('/'):
                return

            text = event.text.strip()
            user_id = event.sender_id

            try:
                # Check if user has a pending action
                if user_id in self.user_context:
                    context = self.user_context[user_id]
                    action = context['action']

                    if action == 'add_topic':
                        topic = context['topic']
                        topic_name = TOPICS[topic]
                        emoji = topic_name.split()[0]
                        
                        if text.startswith(emoji) and 'https://t.me/' in text:
                            clean_url = text[len(emoji):].strip()
                            groups = self.load_topic_groups(topic)
                            if clean_url not in groups:
                                groups.append(clean_url)
                                self.save_topic_groups(topic, groups)
                                username = clean_url.replace("https://t.me/", "").split("/")[0]
                                await event.respond(f"✅ **Added to {topic_name}:**\n@{username}\n{clean_url}", buttons=self.get_main_menu())
                            else:
                                await event.respond("⚠️ **Already exists** in this topic", buttons=self.get_main_menu())
                        else:
                            await event.respond(f"❌ **Invalid format**\nUse: `{emoji} https://t.me/channel/123`", buttons=self.get_main_menu())
                        
                        del self.user_context[user_id]

                    elif action == 'remove_topic':
                        topic = context['topic']
                        if text.isdigit():
                            index = int(text) - 1
                            groups = self.load_topic_groups(topic)
                            if 0 <= index < len(groups):
                                removed_group = groups.pop(index)
                                self.save_topic_groups(topic, groups)
                                username = removed_group.replace("https://t.me/", "").split("/")[0]
                                await event.respond(f"✅ **Removed from {TOPICS[topic]}:**\n@{username}", buttons=self.get_main_menu())
                            else:
                                await event.respond(f"❌ **Invalid number**\nUse 1-{len(groups)}", buttons=self.get_main_menu())
                        else:
                            await event.respond("❌ **Send a valid number**", buttons=self.get_main_menu())
                        
                        del self.user_context[user_id]

                    elif action == 'add_message':
                        if text.startswith('https://t.me/') and len(text.split('/')) >= 3:
                            if text not in config['messageToForward']:
                                config['messageToForward'].append(text)
                                self.save_config()
                                from_channel = text.replace("https://t.me/", "").split("/")[0]
                                await event.respond(f"✅ **Message Added!**\n\nFrom: @{from_channel}\nURL: {text}", buttons=self.get_main_menu())
                            else:
                                await event.respond("⚠️ **Message already exists**", buttons=self.get_main_menu())
                        else:
                            await event.respond("❌ **Invalid URL**\nUse: `https://t.me/channel/123`", buttons=self.get_main_menu())
                        
                        del self.user_context[user_id]

                    elif action == 'remove_message':
                        if text.isdigit():
                            index = int(text) - 1
                            messages = config['messageToForward']
                            if 0 <= index < len(messages):
                                removed_msg = messages.pop(index)
                                self.save_config()
                                channel = removed_msg.replace("https://t.me/", "").split("/")[0]
                                await event.respond(f"✅ **Message Removed!**\n\nRemoved: @{channel}\n\n{len(messages)} messages remaining", buttons=self.get_main_menu())
                            else:
                                await event.respond(f"❌ **Invalid number**\nUse 1-{len(messages)}", buttons=self.get_main_menu())
                        else:
                            await event.respond("❌ **Send a valid number**", buttons=self.get_main_menu())
                        
                        del self.user_context[user_id]

                    elif action == 'set_time':
                        if text.isdigit():
                            number = int(text)
                            if 5 <= number <= 3600:
                                config['time'] = number
                                self.save_config()
                                await event.respond(f"✅ **Time Interval Updated!**\n\n⏰ New interval: {number} seconds\n📊 That's {number/60:.1f} minutes between forwards", buttons=self.get_main_menu())
                            else:
                                await event.respond("❌ **Invalid range**\nUse 5-3600 seconds", buttons=self.get_main_menu())
                        else:
                            await event.respond("❌ **Send a valid number**", buttons=self.get_main_menu())
                        
                        del self.user_context[user_id]

                    elif action == 'set_logs':
                        if text.startswith('https://t.me/') or text.startswith('@'):
                            config['logs_channel'] = text
                            self.logs_channel = text
                            self.save_config()
                            channel_name = text.replace("https://t.me/", "").replace("@", "")
                            await event.respond(f"✅ **Logs Channel Set!**\n\n📋 Channel: @{channel_name}\n🔗 URL: {text}", buttons=self.get_main_menu())
                        else:
                            await event.respond("❌ **Invalid format**\nUse: `https://t.me/channel` or `@channel`", buttons=self.get_main_menu())
                        
                        del self.user_context[user_id]

                else:
                    # No pending action - handle auto-detection
                    if text.startswith('https://t.me/'):
                        # Check if message starts with topic emoji
                        detected_topic = None
                        for topic_key, topic_name in TOPICS.items():
                            emoji = topic_name.split()[0]  # Get emoji part
                            if text.startswith(emoji):
                                detected_topic = topic_key
                                # Remove emoji and space from URL
                                clean_url = text[len(emoji):].strip()
                                break

                        if detected_topic:
                            # Add to specific topic
                            groups = self.load_topic_groups(detected_topic)
                            if clean_url not in groups:  # Prevent duplicates
                                groups.append(clean_url)
                                self.save_topic_groups(detected_topic, groups)
                                topic_name = TOPICS[detected_topic]
                                username = clean_url.replace("https://t.me/", "").split("/")[0]
                                await event.respond(f"✅ **Added to {topic_name}:**\n@{username}\n{clean_url}", buttons=self.get_main_menu())
                            else:
                                await event.respond("⚠️ **Already exists** in this topic", buttons=self.get_main_menu())
                        else:
                            # Auto-detect URL type
                            url_parts = text.replace("https://t.me/", "").split("/")

                            # Message URL (has message ID)
                            if len(url_parts) >= 2 and url_parts[1].isdigit():
                                if text not in config['messageToForward']:  # Prevent duplicates
                                    config['messageToForward'].append(text)
                                    self.save_config()
                                    from_channel = url_parts[0]
                                    await event.respond(f"✅ **Message Added!**\n\nFrom: @{from_channel}\nURL: {text}", buttons=self.get_main_menu())
                                else:
                                    await event.respond("⚠️ **Message already exists**", buttons=self.get_main_menu())
                            else:
                                # Channel URL for logs
                                config['logs_channel'] = text
                                self.logs_channel = text
                                self.save_config()
                                channel_name = url_parts[0]
                                await event.respond(f"✅ **Logs Channel Set!**\n\n📋 Channel: @{channel_name}\n🔗 URL: {text}", buttons=self.get_main_menu())

                    elif text.isdigit():
                        number = int(text)
                        if 5 <= number <= 3600:
                            config['time'] = number
                            self.save_config()
                            await event.respond(f"✅ **Time Interval Updated!**\n\n⏰ New interval: {number} seconds\n📊 That's {number/60:.1f} minutes between forwards", buttons=self.get_main_menu())
                        else:
                            await event.respond("❌ **Invalid Number**\n\nUse:\n• 5-3600 for time (seconds)", buttons=self.get_main_menu())

                    else:
                        await event.respond("ℹ️ **Input Help:**\n\n📝 Send Telegram URLs\n🔢 Send numbers for time\n\nUse /start for main menu", buttons=self.get_main_menu())

            except Exception as e:
                await event.respond(f"❌ **Error processing input:** {str(e)}", buttons=self.get_main_menu())
                print(f"Text handler error: {e}")

    # ===== MAIN EXECUTION FUNCTIONS =====
    async def run_single_forwarding(self):
        """Run single account forwarding continuously"""
        global bot_running
        print("🚀 Starting single-account forwarding...")
        
        while bot_running:
            try:
                print(f"🔄 Connecting and forwarding... ({datetime.now().strftime('%H:%M:%S')})")
                if await self.connect():
                    await self.forward_single()
                    print(f"✅ Forward cycle completed, waiting {config['time']} seconds...")
                else:
                    print("❌ Connection failed, retrying in 30 seconds...")
                    await asyncio.sleep(30)
                    continue
                    
                await asyncio.sleep(config["time"])
            except asyncio.CancelledError:
                print("Single forwarding cancelled")
                break
            except Exception as e:
                print(f"Single forwarding error: {e}")
                await asyncio.sleep(30)  # Wait before retrying

    async def run_multi_forwarding(self):
        """Run multi account forwarding continuously"""
        global bot_running
        print("🚀 Starting multi-account forwarding...")
        
        while bot_running:
            try:
                print(f"🔄 Multi-account forwarding... ({datetime.now().strftime('%H:%M:%S')})")
                await self.forward_multi()
                print(f"✅ Forward cycle completed, waiting {config['time']} seconds...")
                await asyncio.sleep(config["time"])
            except asyncio.CancelledError:
                print("Multi forwarding cancelled")
                break
            except Exception as e:
                print(f"Multi forwarding error: {e}")
                await asyncio.sleep(30)  # Wait before retrying

    async def run_inline_bot(self):
        """Run the inline management bot"""
        try:
            self.setup_inline_bot_handlers()
            # Start with bot token for proper session handling
            await self.bot.start(bot_token=BOT_TOKEN)
            print("🤖 Inline Bot Manager started!")
            print(f"Bot info: {await self.bot.get_me()}")
            print("Send /start to begin using the bot")
            
            # Manual start only - no auto-forwarding
            print("⚠️ Auto-start disabled - use /start command to manually control forwarding")
                
            await self.bot.run_until_disconnected()
        except Exception as e:
            print(f"Inline bot error: {e}")
            raise

    async def run_management_bot(self):
        """Run the command-based management bot"""
        try:
            await self.management_bot.start()
            print("Management bot started! Send /start to begin.")
            await self.management_bot.run_until_disconnected()
        except Exception as e:
            print(f"Management bot error: {e}")
            raise

    async def start_forwarding_mode(self, mode="auto"):
        """Start forwarding in specified mode"""
        global bot_running
        
        if mode == "auto":
            # Auto-detect mode based on number of accounts
            if len(self.accounts) > 1:
                mode = "multi"
            else:
                mode = "single"
        
        print(f"Starting {mode}-account forwarding mode...")
        bot_running = True
        
        if mode == "multi":
            await self.run_multi_forwarding()
        else:
            await self.run_single_forwarding()

# ===== MAIN EXECUTION =====
async def main():
    import sys
    
    try:
        manager = UnifiedTelegramManager()
        
        # Check command line arguments for mode selection
        if len(sys.argv) > 1:
            mode = sys.argv[1].lower()
            
            if mode == "inline":
                await manager.run_inline_bot()
            elif mode == "command":
                await manager.run_management_bot()
            elif mode == "forward":
                forwarding_mode = sys.argv[2] if len(sys.argv) > 2 else "auto"
                await manager.start_forwarding_mode(forwarding_mode)
            else:
                print("Available modes: inline, command, forward [single/multi/auto]")
        else:
            # Default: run inline bot manager
            await manager.run_inline_bot()
    except Exception as e:
        print(f"Main execution error: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())
