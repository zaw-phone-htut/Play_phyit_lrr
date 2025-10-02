import discord
from discord.ext import commands
import logging
from dotenv import load_dotenv
from collections import defaultdict
import os
import webserver

load_dotenv()
token = os.environ("discordkey")
POLL_CHANNEL_ID = 1173262644854145154
TARGET_ROLE_NAME = "Gate Mhuu"

handler = logging.FileHandler(
    filename="discord.log", encoding="utf-8", mode="w")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.reactions = True

bot = commands.Bot(command_prefix="!", intents=intents)

TIME_CHOICES = {
    "8️⃣": "8pm JST",
    "9️⃣": "9pm JST",
    "0️⃣": "9pm JST and later",
    "❌": "No"
}
# Game Poll Options
GAME_CHOICES = {
    "🐱": "PalWorld",
    "6️⃣": "RainBow Six: Siege",
    "💀": "Project Zomboid",
}

poll_state = {
    'time_poll_id': None,          # The message ID of the active time poll
    'game_poll_id': None,          # The message ID of the active game poll
    'time_poll_votes': defaultdict(set),  # {'emoji_str': {user_id1, user_id2}}
    'game_poll_votes': defaultdict(int),  # {'emoji_str': vote_count}
    'time_voters': set(),          # Set of unique user IDs who voted in the time poll
    'poll_channel_id': None        # The channel where the polls were started
}


# --- Utility Functions ---

async def create_time_poll(ctx):
    """Creates and sends the 'Can we play?' poll."""
    global poll_state

    # Reset state for a new poll sequence
    poll_state = {
        'time_poll_id': None,
        'game_poll_id': None,
        'time_poll_votes': defaultdict(set),
        'game_poll_votes': defaultdict(int),
        'time_voters': set(),
        'poll_channel_id': ctx.channel.id
    }

    target_role = discord.utils.get(ctx.guild.roles, name=TARGET_ROLE_NAME)
    role_mention = target_role.mention if target_role else "**Hey everyone**"

    description = "**Time choices:**\n" + "\n".join(
        f"{emoji}: {choice}" for emoji, choice in TIME_CHOICES.items()
    )

    embed = discord.Embed(
        title="📢 Play Phyit Lr?",
        description=description,
        color=discord.Color.blue()
    )
    embed.set_footer(
        text="React with your preferred time. We need at least 2 unique voters to continue!")

    poll_msg = await ctx.send(f"{role_mention}! Play Phyit Lrr? Ma Play Phyit Buu Lrr? Vote now:", embed=embed)
    poll_state['time_poll_id'] = poll_msg.id

    # Add reactions for voting
    for emoji in TIME_CHOICES.keys():
        await poll_msg.add_reaction(emoji)

    print(f"Time poll started with ID: {poll_msg.id}")


async def create_game_poll(channel: discord.TextChannel):
    """Creates and sends the 'Which game?' poll."""
    global poll_state

    # Check if a game poll is already running
    if poll_state['game_poll_id'] is not None:
        return

    description = "**Br Play Mr Lal?:**\n" + "\n".join(
        f"{emoji}: {choice}" for emoji, choice in GAME_CHOICES.items()
    )

    embed = discord.Embed(
        title="🎮 Br Play Mr Lal?",
        description=description,
        color=discord.Color.green()
    )
    embed.set_footer(text="React with the game you want to play!")

    poll_msg = await channel.send(embed=embed)
    poll_state['game_poll_id'] = poll_msg.id

    # Add reactions for voting
    for emoji in GAME_CHOICES.keys():
        await poll_msg.add_reaction(emoji)
        # Initialize game poll votes
        poll_state['game_poll_votes'][emoji] = 0

    print(f"Game poll started with ID: {poll_msg.id}")


async def finalize_poll_results(channel: discord.TextChannel, forced_no_end: bool = False):
    """
    Tally votes, announce results, and clear state.
    forced_no_end: True if the poll ended automatically because 2+ users voted 'No'.
    """
    global poll_state

    # 1. Tally Time Votes
    time_results_list = []

    # Need to fetch the guild to resolve member names for mentions
    if not channel.guild:
        return await channel.send("Error: Cannot fetch guild members for result announcement.")

    for emoji, users in poll_state['time_poll_votes'].items():
        time_choice = TIME_CHOICES.get(emoji, "Unknown Time")

        # Resolve user IDs to user objects and mention strings
        voter_mentions = []
        for user_id in users:
            # Fetch the member object from the guild for accurate mention
            member = channel.guild.get_member(user_id)
            if member:
                # Use member.mention for the proper Discord mention
                voter_mentions.append(member.mention)
            else:
                # Fallback if member is not found in the cache
                voter_mentions.append(f"<@{user_id}>")

        voters_str = ", ".join(
            voter_mentions) if voter_mentions else "No votes"
        # Using bold for the choice name for better formatting
        time_results_list.append(f"**{time_choice}**: {voters_str}")

    # 2. Tally Game Votes
    winning_game = "Undecided (No votes recorded)"

    if forced_no_end:
        # If forced_no_end is True, the game poll never started
        game_result_section = ""
    else:
        max_votes = -1

        if poll_state['game_poll_id']:
            game_votes = poll_state['game_poll_votes']

            # Check if anyone voted at all in the game poll
            total_game_votes = sum(game_votes.values())

            if total_game_votes > 0:
                # Find the choice with the maximum votes
                for emoji, count in game_votes.items():
                    if count > max_votes:
                        max_votes = count
                        winning_game = GAME_CHOICES.get(emoji, "Unknown Game")
                    elif count == max_votes and max_votes > 0:
                        # Handle ties: just list the first one found as the winner
                        winning_game = f"{winning_game} (Tie)"

        game_result_section = f"""
---
**Game - {winning_game}**
"""

    # 3. Announce Results

    # Mention all unique users who participated in the time poll
    all_time_voters = ", ".join(
        f"<@{uid}>" for uid in poll_state['time_voters'])

    final_message = f"""
{all_time_voters}
---
** POLL RESULTS! **
---
**Play Phyit Lrr?**
{' (No one voted for time!)' if not poll_state['time_voters'] else ''}
{'\n'.join(time_results_list)}
{game_result_section}
"""
    await channel.send(final_message)

    # 4. Clear state after completion
    poll_state['time_poll_id'] = None
    poll_state['game_poll_id'] = None
    poll_state['time_voters'].clear()


# --- Bot Events ---


@bot.event
async def on_ready():
    print(f"We are ready to go!!! {bot.user.name}")


@bot.event
async def on_raw_reaction_add(payload):
    """Handles reactions for both polls."""
    user = bot.get_user(payload.user_id)
    if user.bot:
        return

    emoji_str = str(payload.emoji)
    message_id = payload.message_id
    channel = bot.get_channel(payload.channel_id)

    # 1. Handle Time Poll Votes
    if message_id == poll_state['time_poll_id']:
        if emoji_str in TIME_CHOICES:
            # OPTIONAL: Remove previous votes by this user to ensure they only vote once for time
            for key in TIME_CHOICES.keys():
                if payload.user_id in poll_state['time_poll_votes'][key]:
                    poll_state['time_poll_votes'][key].discard(payload.user_id)

            poll_state['time_poll_votes'][emoji_str].add(payload.user_id)
            poll_state['time_voters'].add(payload.user_id)
            print(
                f"Time vote recorded: {user.name} voted for {TIME_CHOICES[emoji_str]}")

            # Check for the 2 user minimum trigger
            num_voters = len(poll_state['time_voters'])
            if num_voters >= 2 and poll_state['game_poll_id'] is None:
                no_voters = poll_state['time_poll_votes'].get("❌", set())

                # If ALL unique voters (2 or more) voted 'No', automatically end the poll
                if no_voters == poll_state['time_voters']:
                    await channel.send("❌ Two or more users have voted 'No'. The poll is ending automatically.")
                    await finalize_poll_results(channel, forced_no_end=True)

                # If 2 or more users voted, and at least one person voted for a time/later
                else:
                    await create_game_poll(channel)

    # 2. Handle Game Poll Votes
    elif message_id == poll_state['game_poll_id']:
        if emoji_str in GAME_CHOICES:
            # Simple count for game votes (since we don't need to track unique users for the final announcement)
            poll_state['game_poll_votes'][emoji_str] += 1
            print(
                f"Game vote recorded: {user.name} voted for {GAME_CHOICES[emoji_str]}")


@bot.event
async def on_raw_reaction_remove(payload):
    """Handles removing reactions from both polls to ensure accurate results."""
    user = bot.get_user(payload.user_id)
    if user.bot:
        return

    emoji_str = str(payload.emoji)
    message_id = payload.message_id

    # 1. Handle Time Poll Unvotes
    if message_id == poll_state['time_poll_id']:
        if emoji_str in TIME_CHOICES:
            if payload.user_id in poll_state['time_poll_votes'][emoji_str]:
                poll_state['time_poll_votes'][emoji_str].discard(
                    payload.user_id)

                # Check if the user has any remaining votes in the time poll
                user_is_still_voted = any(
                    payload.user_id in voters for voters in poll_state['time_poll_votes'].values())

                if not user_is_still_voted:
                    poll_state['time_voters'].discard(payload.user_id)

                print(
                    f"Time unvote recorded: {user.name} unvoted from {TIME_CHOICES.get(emoji_str, 'unknown')}")

    # 2. Handle Game Poll Unvotes
    elif message_id == poll_state['game_poll_id']:
        if emoji_str in GAME_CHOICES:
            if poll_state['game_poll_votes'][emoji_str] > 0:
                poll_state['game_poll_votes'][emoji_str] -= 1
                print(
                    f"Game unvote recorded: {user.name} unvoted from {GAME_CHOICES.get(emoji_str, 'unknown')}")


# --- Bot Commands ---

@bot.command(name='ppl', help='Starts the "Play Phyit Lr?" poll.')
async def start_poll(ctx):
    """Command to start the poll sequence."""
    await create_time_poll(ctx)


@bot.command(name='endppl', help='Ends the poll sequence and announces the results.')
async def end_poll(ctx):
    """Command to finalize and announce results."""

    # 1. Validation
    if poll_state['time_poll_id'] is None:
        return await ctx.send("No active poll sequence to end. Start one with `!ppl`.")

    if ctx.channel.id != poll_state['poll_channel_id']:
        return await ctx.send("Please run this command in the same channel where the poll was started.")

    # Finalize the results
    await finalize_poll_results(ctx.channel)


# --- Run Bot ---
try:
    webserver.keep_alive()
    bot.run(token, log_handler=handler, log_level=logging.DEBUG)
except discord.HTTPException as e:
    print(f"An HTTPException occurred. Check your bot token and intents: {e}")
except Exception as e:
    print(f"An unexpected error occurred: {e}")
