# sendmessage.py
import discord
from discord.ext import commands
import os
import logging

def setup_sendmessage(bot, state):
    """Setup sendmessage command for bot owner"""
    
    @bot.command(name="sendmessage")
    @commands.is_owner()
    async def send_message(ctx):
        """Send message from message.txt to all servers"""
        
        # Check if message.txt exists
        if not os.path.exists("message.txt"):
            await ctx.send("❌ Файл `message.txt` не знайдено!")
            return
        
        try:
            # Read message from file
            with open("message.txt", "r", encoding="utf-8") as f:
                message_content = f.read().strip()
            
            if not message_content:
                await ctx.send("❌ Файл `message.txt` порожній!")
                return
            
            # Create embed for the message
            embed = discord.Embed(
                title="📢 Важливе повідомлення від адміністрації GamerBot",
                description=message_content,
                color=discord.Color.from_str("#08ffea")
            )
            embed.set_footer(text=f"Відправлено через GamerBot{bot.user.name}")
            
            sent_count = 0
            failed_count = 0
            
            # Send initial status
            status_msg = await ctx.send(f"⏳ Розпочинаю розсилку повідомлення на {len(bot.guilds)} серверів...")
            
            # Send to all guilds
            for guild in bot.guilds:
                try:
                    guild_id = str(guild.id)
                    
                    # Try to find a suitable channel in this order:
                    # 1. word_channel
                    # 2. count_channel
                   
                    
                    channel = None
                    
                    # Check word channel
                    if guild_id in state and state[guild_id].get("word_channel"):
                        word_channel_id = state[guild_id]["word_channel"]
                        word_channel = guild.get_channel(word_channel_id)
                        if word_channel and word_channel.permissions_for(guild.me).send_messages:
                            channel = word_channel
                    
                    # Check count channel
                    if not channel and guild_id in state and state[guild_id].get("count_channel"):
                        count_channel_id = state[guild_id]["count_channel"]
                        count_channel = guild.get_channel(count_channel_id)
                        if count_channel and count_channel.permissions_for(guild.me).send_messages:
                            channel = count_channel
                    
                 
                    if channel:
                        await channel.send(embed=embed)
                        sent_count += 1
                        logging.info(f"✅ Повідомлення відправлено на сервер: {guild.name} ({guild.id}) в канал: {channel.name}")
                    else:
                        failed_count += 1
                        logging.warning(f"❌ Не вдалося знайти підходящий канал на сервері: {guild.name} ({guild.id})")
                        
                except Exception as e:
                    failed_count += 1
                    logging.error(f"❌ Помилка при відправці на сервер {guild.name} ({guild.id}): {e}")
            
            # Update status message
            result_embed = discord.Embed(
                title="📊 Результат розсилки",
                color=discord.Color.green() if failed_count == 0 else discord.Color.orange()
            )
            result_embed.add_field(name="✅ Успішно відправлено", value=f"{sent_count} серверів", inline=True)
            result_embed.add_field(name="❌ Не відправлено", value=f"{failed_count} серверів", inline=True)
            result_embed.add_field(name="📝 Загальна кількість", value=f"{len(bot.guilds)} серверів", inline=True)
            
            if failed_count > 0:
                result_embed.add_field(
                    name="⚠️ Увага", 
                    value="Деяким серверам не вдалося відправити повідомлення. Перевірте лог для деталей.", 
                    inline=False
                )
            
            await status_msg.edit(content=None, embed=result_embed)
            
        except Exception as e:
            await ctx.send(f"❌ Сталася помилка: {e}")
            logging.error(f"Помилка в команді sendmessage: {e}")
    
    @send_message.error
    async def send_message_error(ctx, error):
        """Error handler for sendmessage command"""
        if isinstance(error, commands.NotOwner):
            await ctx.send("❌ Ця команда доступна тільки власнику бота!")
        else:
            await ctx.send(f"❌ Сталася помилка: {error}")