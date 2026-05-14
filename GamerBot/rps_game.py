# rps_game.py
import discord
from discord import app_commands
import random
import json
import os

# Константи для гри
RPS_CHOICES = {
    "rock": {"emoji": "🪨", "beats": ["scissors"], "loses_to": ["paper"]},
    "paper": {"emoji": "📄", "beats": ["rock"], "loses_to": ["scissors"]},
    "scissors": {"emoji": "✂️", "beats": ["paper"], "loses_to": ["rock"]}
}

RPS_WIN_POINTS = 10
RPS_DRAW_POINTS = 2
RPS_LOSE_POINTS = -10  

def get_rps_ukrainian_name(choice: str) -> str:
    """Get Ukrainian name for RPS choice"""
    names = {
        "rock": "Камінь",
        "paper": "Папір",
        "scissors": "Ножиці"
    }
    return names.get(choice, choice)

def get_rps_result(player_choice: str, bot_choice: str) -> str:
    """Determine result: win, lose, or draw"""
    if player_choice == bot_choice:
        return "draw"
    elif bot_choice in RPS_CHOICES[player_choice]["beats"]:
        return "win"
    else:
        return "lose"

def update_rps_points(state: dict, gid: str, user_id: str, result: str) -> tuple:
    """Update user's RPS points based on result, returns (points_added, new_total)"""
    if gid not in state:
        state[gid] = {}
    if "rps_data" not in state[gid]:
        state[gid]["rps_data"] = {"top": {}}
    
    rps_top = state[gid]["rps_data"]["top"]
    
    if result == "win":
        points_to_add = RPS_WIN_POINTS
    elif result == "draw":
        points_to_add = RPS_DRAW_POINTS
    else:  # lose
        points_to_add = RPS_LOSE_POINTS
    
    current_points = rps_top.get(user_id, 0)
    new_total = max(0, current_points + points_to_add)  # Мінімум 0 балів
    rps_top[user_id] = new_total
    
    return points_to_add, new_total

def setup_rps_game(bot, state):
    """Setup Rock-Paper-Scissors commands"""
    
    async def play_rps(interaction: discord.Interaction, player_choice: str):
        gid = str(interaction.guild.id)
        user_id = str(interaction.user.id)
        
        # Bot's random choice
        bot_choice = random.choice(list(RPS_CHOICES.keys()))
        
        # Get result
        result = get_rps_result(player_choice, bot_choice)
        
        # Update points
        points_added, new_total = update_rps_points(state, gid, user_id, result)
        
        # Get language from state
        lang = state.get(gid, {}).get("language", "uk")
        
        if lang == "uk":
            choices_text = f"Твій вибір: {RPS_CHOICES[player_choice]['emoji']} **{get_rps_ukrainian_name(player_choice)}**\n"
            choices_text += f"Вибір бота: {RPS_CHOICES[bot_choice]['emoji']} **{get_rps_ukrainian_name(bot_choice)}**\n\n"
            
            if result == "win":
                result_text = f"🎉 **Ти виграв(ла)!** +{points_added} балів!"
            elif result == "draw":
                result_text = f"🤝 **Нічия!** +{points_added} балів!"
            else:
                result_text = f"😞 **Ти програв(ла)!** {points_added} балів"
                
            points_text = f"\n💎 Твої бали: **{new_total}**"
            title = "🎮 Камінь-Ножиці-Папір"
        else:
            choices_text = f"Your choice: {RPS_CHOICES[player_choice]['emoji']} **{player_choice.title()}**\n"
            choices_text += f"Bot's choice: {RPS_CHOICES[bot_choice]['emoji']} **{bot_choice.title()}**\n\n"
            
            if result == "win":
                result_text = f"🎉 **You won!** +{points_added} points!"
            elif result == "draw":
                result_text = f"🤝 **Draw!** +{points_added} points!"
            else:
                result_text = f"😞 **You lost!** {points_added} points"
                
            points_text = f"\n💎 Your points: **{new_total}**"
            title = "🎮 Rock-Paper-Scissors"
        
        # Create embed
        embed = discord.Embed(
            title=title,
            color=discord.Color.green() if result == "win" else 
                  discord.Color.orange() if result == "draw" else 
                  discord.Color.red()
        )
        
        embed.add_field(
            name="🔄 Вибір" if lang == "uk" else "🔄 Choice",
            value=choices_text,
            inline=False
        )
        
        embed.add_field(
            name="🏆 Результат" if lang == "uk" else "🏆 Result",
            value=result_text,
            inline=False
        )
        
        embed.add_field(
            name="📊 Бали" if lang == "uk" else "📊 Points",
            value=points_text,
            inline=False
        )
        
        embed.set_footer(text=f"{interaction.user.display_name}", icon_url=interaction.user.display_avatar.url)
        
        await interaction.response.send_message(embed=embed)
    
    # Create commands
    @bot.tree.command(name="g_rock", description="🎮 Play Rock-Paper-Scissors: choose Rock")
    async def rps_rock(interaction: discord.Interaction):
        await play_rps(interaction, "rock")
    
    @bot.tree.command(name="g_paper", description="🎮 Play Rock-Paper-Scissors: choose Paper")
    async def rps_paper(interaction: discord.Interaction):
        await play_rps(interaction, "paper")
    
    @bot.tree.command(name="g_scissors", description="🎮 Play Rock-Paper-Scissors: choose Scissors")
    async def rps_scissors(interaction: discord.Interaction):
        await play_rps(interaction, "scissors")
    
    @bot.tree.command(name="g_points", description="📊 Show your Rock-Paper-Scissors points")
    async def rps_points(interaction: discord.Interaction):
        gid = str(interaction.guild.id)
        user_id = str(interaction.user.id)
        
        # Ensure guild exists in state
        if gid not in state:
            state[gid] = {"rps_data": {"top": {}}}
        elif "rps_data" not in state[gid]:
            state[gid]["rps_data"] = {"top": {}}
        
        rps_top = state[gid]["rps_data"]["top"]
        user_points = rps_top.get(user_id, 0)
        
        # Get user rank
        sorted_players = sorted(rps_top.items(), key=lambda x: x[1], reverse=True)
        user_rank = None
        for i, (uid, points) in enumerate(sorted_players):
            if uid == user_id:
                user_rank = i + 1
                break
        
        # Get top 5 players
        top_5 = sorted_players[:5]
        
        # Get language
        lang = state.get(gid, {}).get("language", "uk")
        
        # Calculate statistics
        total_games = rps_top.get(f"{user_id}_games", 0)
        wins = rps_top.get(f"{user_id}_wins", 0)
        draws = rps_top.get(f"{user_id}_draws", 0)
        losses = rps_top.get(f"{user_id}_losses", 0)
        
        if lang == "uk":
            embed = discord.Embed(
                title=f"📊 Статистика {interaction.user.display_name}",
                color=discord.Color.gold()
            )
            
            embed.add_field(
                name="💎 Твої бали",
                value=f"**{user_points}** балів",
                inline=True
            )
            
            if user_rank:
                embed.add_field(
                    name="🏆 Твій ранг",
                    value=f"**#{user_rank}** з {len(sorted_players)} гравців",
                    inline=True
            )
            
            # Додаємо статистику
            if total_games > 0:
                win_rate = (wins / total_games * 100) if total_games > 0 else 0
                embed.add_field(
                    name="📈 Статистика ігор",
                    value=f"🎮 Ігор: **{total_games}**\n"
                          f"✅ Перемог: **{wins}**\n"
                          f"🤝 Нічиїх: **{draws}**\n"
                          f"❌ Поразок: **{losses}**\n"
                          f"📊 % перемог: **{win_rate:.1f}%**",
                    inline=False
                )
            
            if top_5:
                top_text = ""
                for i, (uid, points) in enumerate(top_5):
                    try:
                        member = await interaction.guild.fetch_member(int(uid))
                        name = member.display_name
                    except:
                        name = f"Користувач {uid}"
                    
                    medal = "🥇" if i == 0 else "🥈" if i == 1 else "🥉" if i == 2 else f"**{i+1}.**"
                    top_text += f"{medal} {name}: **{points}** балів\n"
                
                embed.add_field(
                    name="🏅 Топ 5 гравців",
                    value=top_text,
                    inline=False
                )
                
            # Додаємо правила системи балів
            embed.add_field(
                name="📋 Система балів",
                value=f"✅ **+{RPS_WIN_POINTS}** — за перемогу\n"
                      f"🤝 **+{RPS_DRAW_POINTS}** — за нічию\n"
                      f"❌ **{RPS_LOSE_POINTS}** — за поразку",
                inline=False
            )
            
        else:
            embed = discord.Embed(
                title=f"📊 {interaction.user.display_name}'s Statistics",
                color=discord.Color.gold()
            )
            
            embed.add_field(
                name="💎 Your Points",
                value=f"**{user_points}** points",
                inline=True
            )
            
            if user_rank:
                embed.add_field(
                    name="🏆 Your Rank",
                    value=f"**#{user_rank}** of {len(sorted_players)} players",
                    inline=True
                )
            
            # Add statistics
            if total_games > 0:
                win_rate = (wins / total_games * 100) if total_games > 0 else 0
                embed.add_field(
                    name="📈 Game Statistics",
                    value=f"🎮 Games: **{total_games}**\n"
                          f"✅ Wins: **{wins}**\n"
                          f"🤝 Draws: **{draws}**\n"
                          f"❌ Losses: **{losses}**\n"
                          f"📊 Win rate: **{win_rate:.1f}%**",
                    inline=False
                )
            
            if top_5:
                top_text = ""
                for i, (uid, points) in enumerate(top_5):
                    try:
                        member = await interaction.guild.fetch_member(int(uid))
                        name = member.display_name
                    except:
                        name = f"User {uid}"
                    
                    medal = "🥇" if i == 0 else "🥈" if i == 1 else "🥉" if i == 2 else f"**{i+1}.**"
                    top_text += f"{medal} {name}: **{points}** points\n"
                
                embed.add_field(
                    name="🏅 Top 5 Players",
                    value=top_text,
                    inline=False
                )
                
            # Add points system info
            embed.add_field(
                name="📋 Points System",
                value=f"✅ **+{RPS_WIN_POINTS}** — for win\n"
                      f"🤝 **+{RPS_DRAW_POINTS}** — for draw\n"
                      f"❌ **{RPS_LOSE_POINTS}** — for loss",
                inline=False
            )
        
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    # Додаємо команду для скидання балів (тільки для адміністраторів)
    @bot.tree.command(name="reset_rps", description="♻️ Reset RPS points for a user (Admin only)")
    @app_commands.describe(user="User to reset points for")
    async def reset_rps_points(interaction: discord.Interaction, user: discord.Member):
        gid = str(interaction.guild.id)
        
        if not (interaction.user.guild_permissions.administrator or interaction.user.id == interaction.guild.owner_id):
            lang = state.get(gid, {}).get("language", "uk")
            if lang == "uk":
                await interaction.response.send_message("❌ Ця команда доступна тільки адміністраторам!", ephemeral=True)
            else:
                await interaction.response.send_message("❌ This command is for administrators only!", ephemeral=True)
            return
        
        user_id = str(user.id)
        
        # Ensure guild exists in state
        if gid not in state:
            state[gid] = {"rps_data": {"top": {}}}
        elif "rps_data" not in state[gid]:
            state[gid]["rps_data"] = {"top": {}}
        
        rps_top = state[gid]["rps_data"]["top"]
        
        if user_id in rps_top:
            old_points = rps_top[user_id]
            rps_top[user_id] = 0
            
            # Also reset statistics
            rps_top.pop(f"{user_id}_games", None)
            rps_top.pop(f"{user_id}_wins", None)
            rps_top.pop(f"{user_id}_draws", None)
            rps_top.pop(f"{user_id}_losses", None)
            
            lang = state.get(gid, {}).get("language", "uk")
            if lang == "uk":
                await interaction.response.send_message(f"✅ Бали користувача {user.mention} скинуто!\nРаніше: **{old_points}** балів\nЗараз: **0** балів", ephemeral=True)
            else:
                await interaction.response.send_message(f"✅ Points for {user.mention} have been reset!\nPrevious: **{old_points}** points\nNow: **0** points", ephemeral=True)
        else:
            lang = state.get(gid, {}).get("language", "uk")
            if lang == "uk":
                await interaction.response.send_message(f"ℹ️ Користувач {user.mention} не має балів у цій грі.", ephemeral=True)
            else:
                await interaction.response.send_message(f"ℹ️ User {user.mention} doesn't have points in this game.", ephemeral=True)