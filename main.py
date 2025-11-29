import discord
from discord.ext import commands
import json
import os

TOKEN = os.getenv("TOKEN")

PREFIXO = "!"
CARGO_ADMIN_ID = 1441627740569735298
CATEGORIA_TICKET = 1442727787180851362
DB = "produtos.json"

intents = discord.Intents.all()
bot = commands.Bot(command_prefix=PREFIXO, intents=intents)

# ------------------- BANCO -------------------
def load():
    if not os.path.exists(DB):
        with open(DB, "w") as f:
            json.dump({}, f)
    with open(DB, "r", encoding="utf-8") as f:
        return json.load(f)

def save(data):
    with open(DB, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def is_admin(member):
    return any(r.id == CARGO_ADMIN_ID for r in member.roles)

# ------------------- VIEW PERSISTENTE -------------------
class LojaView(discord.ui.View):
    def __init__(self, canal_id):
        super().__init__(timeout=None)
        self.canal_id = str(canal_id)
        self.add_item(LojaMenu(self.canal_id))

class LojaMenu(discord.ui.Select):
    def __init__(self, canal_id):
        data = load()
        produtos = data.get(canal_id, {})

        options = []
        for nome, info in produtos.items():
            options.append(
                discord.SelectOption(
                    label=nome,
                    description=f"R${info['preco']} | Estoque: {info['estoque']}",
                    value=nome
                )
            )

        if not options:
            options.append(discord.SelectOption(label="Sem produtos", value="nulo"))

        super().__init__(placeholder="Escolha um produto", options=options)

    async def callback(self, interaction: discord.Interaction):
        nome = self.values[0]
        if nome == "nulo":
            return await interaction.response.send_message("Nenhum produto.", ephemeral=True)
        await abrir_ticket(interaction, nome)

# ------------------- TICKET -------------------
async def abrir_ticket(interaction, produto):
    data = load()
    canal_id = str(interaction.channel.id)
    info = data[canal_id][produto]

    guild = interaction.guild
    categoria = guild.get_channel(CATEGORIA_TICKET)
    admin = guild.get_role(CARGO_ADMIN_ID)

    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        interaction.user: discord.PermissionOverwrite(view_channel=True),
        admin: discord.PermissionOverwrite(view_channel=True)
    }

    canal = await guild.create_text_channel(
        name=f"ticket-{interaction.user.name}",
        category=categoria,
        overwrites=overwrites
    )

    embed = discord.Embed(title="🛒 Nova Compra", color=0x2ecc71)
    embed.add_field(name="Produto", value=produto)
    embed.add_field(name="Preço", value=info['preco'])
    embed.add_field(name="Estoque", value=info['estoque'])

    await canal.send(embed=embed, view=TicketView(canal_id, produto))
    await interaction.response.send_message("✅ Ticket criado!", ephemeral=True)

# ------------------- VIEW TICKET -------------------
class TicketView(discord.ui.View):
    def __init__(self, canal_id, produto):
        super().__init__(timeout=None)
        self.canal_id = canal_id
        self.produto = produto

        self.add_item(ConfirmarCompra())
        self.add_item(FecharTicket())

class ConfirmarCompra(discord.ui.Button):
    def __init__(self):
        super().__init__(label="✅ Confirmar", style=discord.ButtonStyle.green)

    async def callback(self, interaction: discord.Interaction):
        if not is_admin(interaction.user):
            return await interaction.response.send_message("Apenas admin.", ephemeral=True)

        data = load()
        info = data[self.view.canal_id][self.view.produto]

        if info['estoque'] <= 0:
            return await interaction.response.send_message("Sem estoque!", ephemeral=True)

        info['estoque'] -= 1
        save(data)

        await interaction.channel.send(f"✅ Compra confirmada por {interaction.user.mention}")
        await interaction.response.send_message("Estoque atualizado.", ephemeral=True)

class FecharTicket(discord.ui.Button):
    def __init__(self):
        super().__init__(label="🔒 Fechar", style=discord.ButtonStyle.red)

    async def callback(self, interaction: discord.Interaction):
        if not is_admin(interaction.user):
            return await interaction.response.send_message("Apenas admin.", ephemeral=True)
        await interaction.channel.delete()

# ------------------- COMANDOS -------------------
@bot.command()
async def vendas(ctx):
    canal_id = str(ctx.channel.id)
    data = load()
    data.setdefault(canal_id, {})
    save(data)

    embed = discord.Embed(title="🛍 LOJA", description="Escolha um produto abaixo")
    await ctx.send(embed=embed, view=LojaView(canal_id))

@bot.command()
async def addproduto(ctx, *, texto):
    if not is_admin(ctx.author):
        return await ctx.send("Apenas admins.")

    try:
        nome, preco, estoque = texto.split("|")
    except:
        return await ctx.send("Uso: !addproduto Nome | Preço | Estoque")

    data = load()
    canal_id = str(ctx.channel.id)

    data.setdefault(canal_id, {})
    data[canal_id][nome.strip()] = {
        "preco": preco.strip(),
        "estoque": int(estoque.strip())
    }

    save(data)
    await ctx.send("✅ Produto cadastrado e menu atualizado!")

@bot.command()
async def estoque(ctx):
    if not is_admin(ctx.author):
        return

    data = load()
    canal_id = str(ctx.channel.id)

    if canal_id not in data:
        return await ctx.send("Nenhum produto.")

    msg = ""
    for p, i in data[canal_id].items():
        msg += f"{p} → {i['estoque']}\n"

    await ctx.send(f"📦 Estoque atual:\n{msg}")

@bot.command()
async def limpar(ctx):
    if not is_admin(ctx.author):
        return

    data = load()
    canal_id = str(ctx.channel.id)
    data[canal_id] = {}
    save(data)

    await ctx.send("🗑 Produtos apagados neste canal!")

# ------------------- START -------------------
@bot.event
async def on_ready():
    print("✅ BOT ONLINE")
    for guild in bot.guilds:
        print(f"Conectado: {guild.name}")

bot.run(TOKEN)
