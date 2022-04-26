import random
import disnake
import json
from disnake.ext import tasks, commands
from lib.veryimporantlib.modules import *
import os
import datetime
import asyncio


# Подключение клиента
intents = disnake.Intents.default()
client = disnake.ext.commands.Bot(intents=intents)
client.remove_command('help')

# Подключение логера классов
error = Error(client=client)
users = Users(client=client)
mes_helper = CountMessages(client=client)
voice_helper = CountVoiceActivity()

# Подключение json
settings = json.load(open("settings.json", encoding='utf-8-sig'))

shop_roles_list = {settings['shop_roles'][role]['name']: role for role in settings['shop_roles']}


# Запуск бота
@client.event
async def on_ready():
    await client.wait_until_ready()
    await client.change_presence(activity=disnake.Game(name=settings['main_settings']['activity']))
    print('Бот запущен как {0.user}'.format(client))
    print('===========================')
    await users.init()
    await task_checks.start()


@tasks.loop(minutes=10)
async def task_checks():
    pass


@client.event
async def on_voice_state_update(member, before, after):
    if after.afk:
        voice_helper.on_voice_disconnection(user_id=member.id)
        return
    elif before.channel is not None and after.channel is not None:
        return
    elif before.channel is None and after.channel is not None:
        voice_helper.on_voice_connection(user_id=member.id)
    elif before.channel is not None and after.channel is None:
        time = voice_helper.on_voice_disconnection(user_id=member.id)
        if time:
            await users.add_voice(user_id=member.id, seconds=time)


@client.event
async def on_message_delete(message):
    if client.user.id == message.author.id:
        return
    await audit(title="Сообщение удалено",
                description=f"**Автор:** {message.author.mention} (`{message.author.name}`)\n"
                            f"**Сообщение:**\n{message.content}",
                color=disnake.Colour.red(),
                thumbnail=message.author.display_avatar.url)


@client.event
async def on_message(message):
    if client.user.id == message.author.id:
        return
    await users.add_message(user_id=message.author.id)
    count = mes_helper.send_message(member=message.author)
    if not count:
        return
    await users.add_coins(user_id=message.author.id, count=count)


@client.event
async def on_message_edit(before, after):
    if client.user.id == before.author.id:
        return
    await audit(title="Сообщение изменено",
                description=f"**Автор:** {before.author.mention} (`{before.author.name}`)\n"
                            f"**Старое содержимое:**\n{before.content}\n**Новое содержимое:**\n{after.content}",
                color=disnake.Colour.blurple(),
                thumbnail=before.author.display_avatar.url)


@client.event
async def on_member_join(member):
    await audit(title="Участник зашёл на сервер",
                description=f"**Участник:** {member.mention} (`{member.name}`)\n",
                color=disnake.Colour.green(),
                thumbnail=member.display_avatar.url)


@client.event
async def on_member_remove(member):
    await audit(title="Участник покинул сервер",
                description=f"**Участник:** {member.mention} (`{member.name}`)\n",
                color=disnake.Colour.orange(),
                thumbnail=member.display_avatar.url)


@client.event
async def on_member_ban(guild, user):
    await audit(title="Участник был забанен",
                description=f"**Участник:** {user.mention} (`{user.name}`)\n",
                color=disnake.Colour.dark_orange(),
                thumbnail=user.display_avatar.url)


@client.event
async def on_member_unban(guild, user):
    await audit(title="Участник был разбанен",
                description=f"**Участник:** {user.mention} (`{user.name}`)\n",
                color=disnake.Colour.green(),
                thumbnail=user.display_avatar.url)


async def audit(title: str, description: str, color, thumbnail):
    embed = disnake.Embed(title=title, description=description, color=color)
    embed.set_thumbnail(url=thumbnail)
    channel = await client.fetch_channel(settings['main_settings']['log_channel_id'])
    await channel.send(embed=embed)


@client.slash_command(
    name="warn",
    description="Выдать предупреждение участнику.")
async def command_warn(inter: disnake.ApplicationCommandInteraction,
                       user: disnake.User = commands.Param(description="Выберите участника."),
                       rule: str = commands.Param(description="Выберите пунк правила.",
                                                  choices=settings['rules']),
                       time: int = commands.Param(description="Выберите через сколько дней истечет предупреждение.",
                                                  default=0)):
    can_add_warn = True
    for role in inter.author.roles:
        if str(role.id) in settings['moderation_roles']:
            if settings['moderation_roles'][str(role.id)]['warn']:
                can_add_warn = False
                break
    if can_add_warn:
        await error.print(inter=inter, description="У вас нету прав для выдачи предупреждения!")
        return
    if time < 0:
        await error.print(inter=inter, description="Колличество дней не должно быть отрицательным!")
        return
    if inter.author.id == user.id:
        await error.print(inter=inter, description="Вы не можете выдать предупреждение самому себе!")
        return
    warn_time = ""
    if time != 0:
        time = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=time)
        warn_time = f"Истекает <t:{int(time.timestamp())}:R>"
    warn_number = await users.add_warn(moderator_id=inter.author.id, user_id=user.id, reason=rule, days=time)
    embed = disnake.Embed(description=f"**id:** `{warn_number}`\n**Модератор:** {inter.author.name}"
                                      f"\n**Причина:** {rule}\n\n{warn_time}",
                          colour=disnake.Colour.blurple())
    embed.set_author(name=f"{user.name} получил предупреждение!", icon_url=user.display_avatar.url)
    await users.punishment(member=user, reason=rule)
    await inter.send(embed=embed)
    try:
        await user.send(f"Вы получили предупреждение №{warn_number+1}!\nПричина: {rule}\n{warn_time}")
    except:
        pass
    await audit(title="Участник получил предупреждение!",
                description=f"**Участник:** {user.mention} (`{user.name}`)\n",
                color=disnake.Colour.green(),
                thumbnail=user.display_avatar.url)


@client.slash_command(
    name="unwarn",
    description="Снять предупреждение участнику.")
async def command_unwarn(inter: disnake.ApplicationCommandInteraction,
                         user: disnake.User = commands.Param(description="Выберите участника."),
                         id: int = commands.Param(description="Выберите id предупреждения.")):
    can_unwarn = True
    for role in inter.author.roles:
        if str(role.id) in settings['moderation_roles']:
            if settings['moderation_roles'][str(role.id)]['warn']:
                can_unwarn = False
                break
    if can_unwarn:
        await error.print(inter=inter, description="У вас нету прав для снятия предупреждения!")
        return
    if inter.author.id == user.id:
        await error.print(inter=inter, description="Вы не можете снять предупреждение самому себе!")
        return
    status = await users.remove_warn(user_id=user.id, index=id)
    if status:
        await error.print(inter=inter, description=status)
        return
    embed = disnake.Embed(description=f"Предупреждение под номером {id} было успешно снято!",
                          colour=disnake.Colour.blurple())
    embed.set_author(name=f"{inter.author.name} снял предупреждение c {user.name}!", icon_url=user.display_avatar.url)
    await inter.send(embed=embed)


@client.slash_command(
    name="warns",
    description="Посмотреть предупреждения участника.")
async def command_warns(inter: disnake.ApplicationCommandInteraction,
                        user: disnake.User = commands.Param(description="Выберите участника.",
                                                            default=None)):
    if user is None:
        user = inter.author
    warns = await users.get_warns(user_id=user.id)
    if not warns:
        embed = disnake.Embed(description=f"Пользователь {user.name} не имеет предупреждений!",
                              colour=disnake.Colour.blurple())
        embed.set_author(name=f"Предупреждения {user.name}", icon_url=user.display_avatar.url)
        await inter.send(embed=embed)
        return
    warns_txt = []
    for count, warn in enumerate(warns):
        if count % 5 == 0:
            warns_txt.append("")
        time_str = "\n"
        if warn['time'] is not None:
            time_str = f"**Истекает:** <t:{int(warn['time'].timestamp())}:R>\n\n"
        moderator = await client.fetch_user(warn['moderator_id'])
        warns_txt[count//5] += (f"**id:** {count}\n"
                                f"**Модератор:** {moderator.name}\n"
                                f"**Причина:** {warn['reason']}\n{time_str}")
    page = 1
    embed = disnake.Embed(description=warns_txt[page-1],
                          colour=disnake.Colour.blurple())
    embed.set_author(name=f"Предупреждения {user.name}", icon_url=user.display_avatar.url)
    embed.set_footer(text=f"страница {page}/{len(warns_txt)}")
    view = disnake.ui.View()
    view.add_item(disnake.ui.Button(style=disnake.ButtonStyle.blurple, disabled=page <= 1,
                                    custom_id="left", emoji="◀️", row=0))
    view.add_item(disnake.ui.Button(style=disnake.ButtonStyle.blurple, disabled=page >= len(warns_txt),
                                    custom_id="right", emoji="▶️", row=0))
    await inter.send(embed=embed, view=view)
    msg = await inter.original_message()
    while True:
        def check(res):
            return inter.author == res.user and res.channel.id == inter.channel_id and res.message.id == msg.id

        try:
            responce = await client.wait_for('button_click', check=check, timeout=120.0)
        except asyncio.TimeoutError:
            view.clear_items()
            await msg.edit(view=None)
            return

        if responce.component.custom_id == "left":
            page -= 1
        elif responce.component.custom_id == "right":
            page += 1
        view = disnake.ui.View()
        view.add_item(disnake.ui.Button(style=disnake.ButtonStyle.blurple, disabled=page <= 1,
                                        custom_id="left", emoji="◀️", row=0))
        view.add_item(disnake.ui.Button(style=disnake.ButtonStyle.blurple, disabled=page >= len(warns_txt),
                                        custom_id="right", emoji="▶️", row=0))
        embed = disnake.Embed(description=warns_txt[page - 1],
                              colour=disnake.Colour.blurple())
        embed.set_author(name=f"Предупреждения {user.name}", icon_url=user.display_avatar.url)
        embed.set_footer(text=f"страница {page}/{len(warns_txt)}")
        await inter.edit_original_message(embed=embed, view=view)
        await responce.response.defer()


@client.slash_command(
    name="ban",
    description="Забанить участника.")
async def command_ban(inter: disnake.ApplicationCommandInteraction,
                      user: disnake.User = commands.Param(description="Выберите участника."),
                      rule: str = commands.Param(description="Выберите пунк правила.",
                                                 choices=settings['rules'])):
    can_ban = True
    for role in inter.author.roles:
        if str(role.id) in settings['moderation_roles']:
            if settings['moderation_roles'][str(role.id)]['kick_ban']:
                can_ban = False
                break
    if can_ban:
        await error.print(inter=inter, description="У вас нету прав!")
        return
    if inter.author.id == user.id:
        await error.print(inter=inter, description="Вы не можете забанить самого себя!")
        return
    await users.ban(member=user, reason=rule)
    embed = disnake.Embed(description=f"\n**Модератор:** {inter.author.name}"
                                      f"\n**Причина:** {rule}",
                          colour=disnake.Colour.red())
    embed.set_author(name=f"{user.name} был забанен!", icon_url=user.display_avatar.url)
    await inter.send(embed=embed)


@client.slash_command(
    name="kick",
    description="Выгнать участника.")
async def command_kick(inter: disnake.ApplicationCommandInteraction,
                       user: disnake.User = commands.Param(description="Выберите участника."),
                       rule: str = commands.Param(description="Выберите пунк правила.",
                                                  choices=settings['rules'])):
    can_kick = True
    for role in inter.author.roles:
        if str(role.id) in settings['moderation_roles']:
            if settings['moderation_roles'][str(role.id)]['kick_ban']:
                can_kick = False
                break
    if can_kick:
        await error.print(inter=inter, description="У вас нету прав!")
        return
    if inter.author.id == user.id:
        await error.print(inter=inter, description="Вы не можете кикнуть самого себя!")
        return
    await users.kick(member=user, reason=rule)
    embed = disnake.Embed(description=f"\n**Модератор:** {inter.author.name}"
                                      f"\n**Причина:** {rule}",
                          colour=disnake.Colour.red())
    embed.set_author(name=f"{user.name} был выгнат!", icon_url=user.display_avatar.url)
    await inter.send(embed=embed)


@client.slash_command(
    name="mute",
    description="Замутить участника.")
async def command_mute(inter: disnake.ApplicationCommandInteraction,
                       user: disnake.User = commands.Param(description="Выберите участника."),
                       minutes: int = commands.Param(description="Выберите кол-во минут.",
                                                     default=0),
                       hours: int = commands.Param(description="Выберите кол-во часов.",
                                                   default=0),
                       days: int = commands.Param(description="Выберите кол-во дней.",
                                                  default=0)):
    can_mute = True
    for role in inter.author.roles:
        if str(role.id) in settings['moderation_roles']:
            if settings['moderation_roles'][str(role.id)]['mute']:
                can_mute = False
                break
    if can_mute:
        await error.print(inter=inter, description="У вас нету прав!")
        return
    if inter.author.id == user.id:
        await error.print(inter=inter, description="Вы не можете замутить самого себя!")
        return
    if minutes == 0 and hours == 0 and days == 0:
        await error.print(inter=inter, description="Вы не указали время")
        return
    if minutes < 0 or hours < 0 or days < 0:
        await error.print(inter=inter, description="Время не может быть отрицательным!")
        return
    time = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=days, hours=hours, minutes=minutes)
    await users.timeout(member=user, timedelta=datetime.timedelta(days=days, hours=hours, minutes=minutes))
    embed = disnake.Embed(description=f"\n**Модератор:** {inter.author.name}"
                                      f"\n**Мут истекает:** <t:{int(time.timestamp())}:R>",
                          colour=disnake.Colour.red())
    embed.set_author(name=f"{user.name} был замучен!", icon_url=user.display_avatar.url)
    await inter.send(embed=embed)
    await audit(title="Участник был замучен!",
                description=f"**Участник:** {user.mention} (`{user.name}`)\n",
                color=disnake.Colour.green(),
                thumbnail=user.display_avatar.url)


@client.slash_command(
    name="like",
    description="Лайкнуть участника.")
async def command_like(inter: disnake.ApplicationCommandInteraction,
                       user: disnake.User = commands.Param(description="Выберите участника."),
                       option: str = commands.Param(description="Выберите действие.",
                                                    choices=["add", "remove"])):
    if inter.author.id == user.id:
        await error.print(inter=inter, description="Вы не можете лайкнуть самого себя!")
        return
    result = await users.like(liker_id=inter.author.id, user_id=user.id, option=option)
    if result:
        await error.print(inter=inter, description=result)
        return
    if option == "add":
        embed = disnake.Embed(colour=disnake.Colour.green())
        embed.set_author(name=f"{inter.author.name} лайкнул {user.name}!", icon_url=inter.author.display_avatar.url)
    else:
        embed = disnake.Embed(colour=disnake.Colour.red())
        embed.set_author(name=f"{inter.author.name} убрал лайк у {user.name}.", icon_url=inter.author.display_avatar.url)
    await inter.send(embed=embed)


@client.slash_command(
    name="card",
    description="Посмотреть профиль участника.")
async def command_card(inter: disnake.ApplicationCommandInteraction,
                       user: disnake.User = commands.Param(description="Выберите участника.", default=None)):
    if user is None:
        user = inter.author
    user_settings = await users.get_user(user_id=user.id)
    time_sec = "0"+str(user_settings['voice'] % 60) if len(str(user_settings['voice'] % 60)) == 1 \
        else user_settings['voice'] % 60
    all_time = f"{time_sec}"
    if user_settings['voice'] // 60 > 0:
        time_min = "0" + str(user_settings['voice'] // 60 % 60) if len(str(user_settings['voice'] // 60 % 60)) == 1 \
            else user_settings['voice'] // 60 % 60
        all_time = f"{time_min}:{all_time}"
        if user_settings['voice'] // 3600 > 0:
            time_hour = user_settings['voice'] // 3600
            all_time = f"{time_hour}:{all_time}"
    if len(user_settings['warns']) == 0:
        color = disnake.Colour.green()
    elif 0 < len(user_settings['warns']) < 3:
        color = disnake.Colour.blurple()
    else:
        color = disnake.Colour.red()
    embed = disnake.Embed(description=f"┌<:money:963840698686246962> ･ **Монеток:** {round(user_settings['coins'], 1)}\n"
                                      f"├<:chat:963840698732408892> ･ **Сообщений:** {user_settings['messages']}\n"
                                      f"├<:voice:963840698711425024> ･ **Время в войсе:** {all_time}\n"
                                      f"├<:like:963840698489126952> ･ **Лайков:** {len(user_settings['likes'])}\n"
                                      f"└<:warn:963840698505916536> ･ **Предупреждений:** {len(user_settings['warns'])}\n",
                          colour=color)
    embed.set_author(name=f"{user.name}", icon_url=user.display_avatar.url)
    await inter.send(embed=embed)


@client.slash_command(
    name="shop",
    description="Посмотреть магазин.")
async def command_shop(inter: disnake.ApplicationCommandInteraction):
    all_desc = ""
    for count, role in enumerate(settings['shop_roles']):
        all_desc += f"**<@&{role}>** - {settings['shop_roles'][role]['price']} <:money:963840698686246962>" \
                    f"\n```{settings['shop_roles'][role]['description']}```\n"
    embed = disnake.Embed(description=all_desc,
                          colour=disnake.Colour.blurple())
    embed.set_author(name=f"Магазин")
    await inter.send(embed=embed)


@client.slash_command(
    name="buy",
    description="Посмотреть магазин.")
async def command_buy(inter: disnake.ApplicationCommandInteraction,
                      role=commands.Param(description="Выберите роль для покупки.",
                                          choices=shop_roles_list)):
    user = await users.get_user(user_id=inter.author.id)
    if role in [str(rile.id) for rile in inter.author.roles]:
        await error.print(inter=inter, description="У вас уже есть данная роль!")
        return
    elif user['coins'] < settings['shop_roles'][role]['price']:
        await error.print(inter=inter, description="У вас не хватает денег!")
        return
    await users.remove_coins(user_id=inter.author.id, count=settings['shop_roles'][role]['price'])
    roles = inter.guild.get_role(int(role))
    await inter.author.add_roles(roles)
    embed = disnake.Embed(description=f"Вы успешно купили роль {roles.mention}!",
                          colour=disnake.Colour.blurple())
    embed.set_author(name=inter.author.name, icon_url=inter.author.display_avatar.url)
    await inter.send(embed=embed)


client.run(settings['main_settings']['token'])
