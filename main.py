import discord
from discord.ext import commands
from discord.ui import View, Button, Modal, TextInput, Select
import json
import os

# ========== CONFIGURAÇÃO ==========
PREFIXO = "!"
CARGO_ADMIN_ID = 1441627740569735298
CATEGORIA_TICKET_ID = 1442727787180851362
ARQUIVO = "produtos.json"
# ================================

# ✅ TOKEN SEGURO (NÃO APARECE NO CÓDIGO)
TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.all()
bot = commands.Bot(command_prefix=PREFIXO, intents=intents)


# ========= KEEP ALIVE =========
from keep_alive import keep_alive
keep_alive()
# ==============================


# ========= UTIL =========
def carregar():
    if not os.path.exists(ARQUIVO):
        with open(ARQUIVO, "w", encoding="utf-8") as f:
            json.dump({}, f)
    with open(ARQUIVO, encoding="utf-8") as f:
        return json.load(f)

def salvar(dados):
    with open(ARQUIVO, "w", encoding="utf-8") as f:
        json.dump(dados, f, indent=4, ensure_ascii=False)

def is_admin(member):
    return any(role.id == CARGO_ADMIN_ID for role in member.roles)


# ========= BOT ONLINE =========
@bot.event
async def on_ready():
    print(f"✅ BOT ONLINE: {bot.user}")


# ========= MODAL PAINEL =========
class PainelModal(Modal):
    def __init__(self):
        super().__init__(title="Criar Painel")
        self.titulo = TextInput(label="Titulo")
        self.desc = TextInput(label="Descrição", style=discord.TextStyle.long)
        self.img = TextInput(label="Imagem topo (opcional)", required=False)
        self.rodape = TextInput(label="Rodapé")
        self.cor = TextInput(label="Cor HEX ex: #8e44ad")

        self.add_item(self.titulo)
        self.add_item(self.desc)
        self.add_item(self.img)
        self.add_item(self.rodape)
        self.add_item(self.cor)

    async def on_submit(self, interaction):
        try:
            cor = int(self.cor.value.replace("#", ""), 16)
            embed = discord.Embed(
                title=self.titulo.value,
                description=self.desc.value,
                color=cor
            )

            if self.img.value.startswith("http"):
                embed.set_image(url=self.img.value)

            embed.set_footer(text=self.rodape.value)

            await interaction.channel.send(embed=embed, view=PainelView())
            await interaction.response.send_message("✅ Painel criado!", ephemeral=True)

        except:
            await interaction.response.send_message("❌ Erro ao criar painel. Verifique a cor ou imagem.", ephemeral=True)


# ========= PRODUTO MODAL =========
class ProdutoModal(Modal):
    def __init__(self):
        super().__init__(title="Adicionar Produto")
        self.nome = TextInput(label="Nome")
        self.preco = TextInput(label="Preço")
        self.estoque = TextInput(label="Estoque")
        self.cupom = TextInput(label="Cupom(opcional)", required=False)

        for item in [self.nome, self.preco, self.estoque, self.cupom]:
            self.add_item(item)

    async def on_submit(self, interaction):
        dados = carregar()
        dados[self.nome.value] = {
            "preco": self.preco.value,
            "estoque": int(self.estoque.value),
            "cupom": self.cupom.value
        }
        salvar(dados)
        await interaction.response.send_message("✅ Produto adicionado!", ephemeral=True)


# ========= PAINEL VIEW =========
class PainelView(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(ProdutoMenu())
        self.add_item(AddProduto())


class AddProduto(Button):
    def __init__(self):
        super().__init__(label="➕ Adicionar Produto", style=discord.ButtonStyle.blurple)

    async def callback(self, interaction):
        if not is_admin(interaction.user):
            return await interaction.response.send_message("❌ Apenas admins.", ephemeral=True)
        await interaction.response.send_modal(ProdutoModal())


# ========= MENU PRODUTOS =========
class ProdutoMenu(Select):
    def __init__(self):
        dados = carregar()
        options = []

        for nome, info in dados.items():
            desc = f"Preço: {info['preco']} | Estoque: {info['estoque']}"
            options.append(discord.SelectOption(label=nome, description=desc))

        if not options:
            options.append(discord.SelectOption(label="Sem produtos", description="Nenhum cadastrado", value="0"))

        super().__init__(placeholder="Escolha o produto", options=options)

    async def callback(self, interaction):
        produto = self.values[0]
        if produto == "0":
            return await interaction.response.send_message("Nenhum produto disponível.", ephemeral=True)

        await abrir_ticket(interaction, produto)


# ========= TICKET =========
async def abrir_ticket(interaction, produto):
    dados = carregar()
    info = dados[produto]

    guild = interaction.guild
    categoria = guild.get_channel(CATEGORIA_TICKET_ID)
    cargo = guild.get_role(CARGO_ADMIN_ID)

    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        interaction.user: discord.PermissionOverwrite(view_channel=True),
        cargo: discord.PermissionOverwrite(view_channel=True)
    }

    canal = await guild.create_text_channel(f"ticket-{interaction.user.name}", category=categoria, overwrites=overwrites)

    embed = discord.Embed(title="🛒 COMPRA ABERTA", color=0x2ecc71)
    embed.add_field(name="Produto", value=produto)
    embed.add_field(name="Preço", value=info["preco"])
    embed.add_field(name="Estoque", value=info["estoque"])
    embed.add_field(name="Cupom", value=info["cupom"] or "Nenhum")

    await canal.send(embed=embed, view=ConfirmarView(produto))
    await interaction.response.send_message("✅ Ticket criado!", ephemeral=True)


# ========= CONFIRMAR =========
class ConfirmarView(View):
    def __init__(self, produto):
        super().__init__(timeout=None)
        self.produto = produto
        self.add_item(Confirmar())
        self.add_item(Fechar())


class Confirmar(Button):
    def __init__(self):
        super().__init__(label="✅ Confirmar Compra", style=discord.ButtonStyle.green)

    async def callback(self, interaction):
        if not is_admin(interaction.user):
            return await interaction.response.send_message("❌ Apenas admin.", ephemeral=True)

        dados = carregar()
        if dados[self.view.produto]["estoque"] <= 0:
            return await interaction.response.send_message("❌ Sem estoque!", ephemeral=True)

        dados[self.view.produto]["estoque"] -= 1
        salvar(dados)

        await interaction.channel.send(f"✅ Compra confirmada por {interaction.user.mention}")
        await interaction.response.send_message("✅ Estoque atualizado!", ephemeral=True)


class Fechar(Button):
    def __init__(self):
        super().__init__(label="🔒 Fechar Ticket", style=discord.ButtonStyle.red)

    async def callback(self, interaction):
        if not is_admin(interaction.user):
            return await interaction.response.send_message("❌ Apenas admin.", ephemeral=True)
        await interaction.channel.delete()


# ========= COMANDOS =========
@bot.command()
async def vendas(ctx):
    if not is_admin(ctx.author):
        return await ctx.send("❌ Sem permissão.")
    await ctx.send("Clique para criar o painel:", view=CriarPainel())


class CriarPainel(View):
    def __init__(self):
        super().__init__()
        self.add_item(BotaoPainel())


class BotaoPainel(Button):
    def __init__(self):
        super().__init__(label="🎨 Criar Painel", style=discord.ButtonStyle.green)

    async def callback(self, interaction):
        if not is_admin(interaction.user):
            return await interaction.response.send_message("❌ Apenas admins.", ephemeral=True)
        await interaction.response.send_modal(PainelModal())


@bot.command()
async def rvendas(ctx):
    dados = carregar()
    for p in dados:
        dados[p]["estoque"] = 0
    salvar(dados)
    await ctx.send("✅ Estoques resetados!")


@bot.command()
async def pvendas(ctx):
    salvar({})
    await ctx.send("🗑 Produtos apagados!")


# ========= INICIAR =========
bot.run(TOKEN)
