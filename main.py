import discord
from discord.ext import commands
from discord import app_commands
import random
from datetime import datetime
import json
import os
from dotenv import load_dotenv

load_dotenv()

# ======================
# CONFIGURAÇÕES
# ======================
TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

# IDs de Canais e Cargos
BUY_CATEGORY_ID = 1449312175448391833
CLOSED_CATEGORY_ID = 1449319381422051400
STAFF_ROLE_ID = 1449319423780458597
LOG_CHANNEL_ID = 1449319519733551245

# Taxas de Conversão
ROBUX_RATE = 0.035  # 1 Robux = R$ 0,035
ROBLOX_TAX = 0.30   # Roblox pega 30% da gamepass

# Arquivos JSON
TICKETS_FILE = "tickets.json"
PURCHASE_COUNT_FILE = "compras.json"

# ======================
# FUNÇÕES DE CÁLCULO
# ======================

def calcular_valor_gamepass(robux):
    """Calcula o valor da gamepass considerando a taxa de 30% do Roblox."""
    valor_gamepass = robux / (1 - ROBLOX_TAX)
    return round(valor_gamepass)

def calcular_robux_liquidos(valor_gamepass):
    """Calcula quantos robux líquidos recebe de uma gamepass."""
    robux_liquidos = valor_gamepass * (1 - ROBLOX_TAX)
    return round(robux_liquidos)

# ======================
# MODAIS PARA COMPRAS
# ======================

class RobuxPurchaseModal(discord.ui.Modal, title="💎 Comprar Robux"):
    quantidade = discord.ui.TextInput(
        label="🎯 Quantos Robux você quer comprar?",
        placeholder="Digite apenas números (ex: 1000, 5000, 10000)",
        required=True,
        max_length=10
    )

    async def on_submit(self, interaction: discord.Interaction):
        try:
            quantidade = int(self.quantidade.value)
            
            if quantidade <= 0:
                await interaction.response.send_message(
                    "🤔 **Oops!** Você precisa digitar um número maior que zero!",
                    ephemeral=True
                )
                return
            
            # Armazenar a quantidade no modal para uso posterior
            self.quantidade_robux = quantidade
            
            # Criar o ticket
            await self.criar_ticket(interaction, "robux", quantidade)
            
        except ValueError:
            await interaction.response.send_message(
                "❌ **Formato inválido!**\nPor favor, digite apenas números (ex: 1000, 5000, 10000)",
                ephemeral=True
            )
    
    async def criar_ticket(self, interaction: discord.Interaction, tipo: str, quantidade: int):
        """Cria um ticket para compra de Robux."""
        data = load_json(TICKETS_FILE, {"usuarios": {}})
        uid = str(interaction.user.id)

        if uid in data["usuarios"] and data["usuarios"][uid].get("ticket_aberto"):
            await interaction.response.send_message(
                "🔄 **Você já tem um ticket aberto!**\n"
                "Por favor, use o ticket atual antes de abrir um novo. "
                "Nossa equipe está pronta para te atender lá! 🚀",
                ephemeral=True
            )
            return

        guild = interaction.guild
        user = interaction.user
        category = guild.get_channel(BUY_CATEGORY_ID)

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            user: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
            guild.get_role(STAFF_ROLE_ID): discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)
        }

        tipo_compra = "Robux"
        emoji_tipo = "💎"
        
        channel = await guild.create_text_channel(
            name=f"{emoji_tipo}┃{user.name}-{tipo_compra}-{random.randint(100,999)}",
            category=category,
            overwrites=overwrites,
            topic=f"🎫 Ticket de {tipo_compra} • Cliente: {user.name} • Quantidade: {quantidade:,} Robux • Aberto em: {datetime.now().strftime('%d/%m %H:%M')}"
        )

        data["usuarios"].setdefault(uid, {"tickets": [], "ticket_aberto": False})
        data["usuarios"][uid]["tickets"].append({
            "canal_id": channel.id,
            "tipo": tipo,
            "status": "aberto",
            "criado_em": datetime.utcnow().isoformat(),
            "cliente_nome": user.name,
            "quantidade": quantidade
        })
        data["usuarios"][uid]["ticket_aberto"] = True
        save_json(TICKETS_FILE, data)

        embed_ticket = discord.Embed(
            title=f"🎫 **TICKET DE {tipo_compra.upper()} ABERTO!**",
            description=f"""
            ✨ **Olá {user.mention}!** Seja muito bem-vindo(a) ao seu ticket! ✨
            
            **📋 INFORMAÇÕES DO SEU ATENDIMENTO:**
            • **Tipo:** {tipo_compra} {emoji_tipo}
            • **Quantidade:** {quantidade:,} Robux
            • **Ticket:** #{channel.name}
            • **Horário:** {datetime.now().strftime('%d/%m/%Y às %H:%M')}
            • **Status:** 🔵 **EM ANDAMENTO**
            
            **🎯 PRÓXIMOS PASSOS:**
            1. **Aguarde nossa equipe** - Vamos te atender rapidinho! ⚡
            2. **Siga as instruções** - Vamos guiar você passo a passo!
            3. **Realize o pagamento** - Envie o comprovante quando solicitado
            """,
            color=discord.Color.green(),
            timestamp=datetime.utcnow()
        )
        
        # Adicionar valor em reais calculado
        valor_reais = quantidade * ROBUX_RATE
        embed_ticket.add_field(
            name="💰 **VALOR ESTIMADO**",
            value=f"```💵 R$ {valor_reais:,.2f}```",
            inline=True
        )
        
        embed_ticket.add_field(
            name="📞 **ATENDIMENTO RÁPIDO**",
            value="Nossa equipe foi notificada e já vai te atender! ⚡",
            inline=True
        )
        
        embed_ticket.set_footer(
            text=f"Atendimento VIP para {user.name} • Obrigado por escolher nossa loja!",
            icon_url=user.avatar.url if user.avatar else None
        )
        embed_ticket.set_thumbnail(url="https://cdn.discordapp.com/emojis/1128316432067063838.gif")

        await channel.send(
            content=f"👋 **Olá {user.mention}!** <@&{STAFF_ROLE_ID}>\n\n**📋 DETALHES DA COMPRA:**\n• **Tipo:** {tipo_compra}\n• **Quantidade:** {quantidade:,} Robux",
            embed=embed_ticket,
            view=TicketButtons()
        )

        embed_confirma = discord.Embed(
            title="✅ **TICKET CRIADO COM SUCESSO!**",
            description=f"""
            🎉 **Perfeito! Seu ticket foi criado e já está pronto!**
            
            **📋 DETALHES:**
            • **Ticket:** {channel.mention}
            • **Tipo:** {tipo_compra} {emoji_tipo}
            • **Quantidade:** {quantidade:,} Robux
            • **Valor estimado:** R$ {valor_reais:,.2f}
            • **Aberto em:** {datetime.now().strftime('%H:%M')}
            
            **🚀 VÁ ATÉ O TICKET:**
            Clique no link acima ou vá até o canal {channel.mention} para continuar!
            
            **⏳ AGUARDE...**
            Nossa equipe foi notificada e já vai te atender!
            """,
            color=discord.Color.green()
        )
        
        await interaction.response.send_message(embed=embed_confirma, ephemeral=True)


class GamepassPurchaseModal(discord.ui.Modal, title="🎮 Comprar Gamepass"):
    jogo = discord.ui.TextInput(
        label="🎯 Nome do Jogo",
        placeholder="Ex: Adopt Me, Blox Fruits, Brookhaven",
        required=True,
        max_length=100
    )
    
    gamepass = discord.ui.TextInput(
        label="💎 Nome da Gamepass",
        placeholder="Ex: 1.000 Robux, VIP Pass, Super Booster",
        required=True,
        max_length=100
    )

    async def on_submit(self, interaction: discord.Interaction):
        jogo = self.jogo.value.strip()
        gamepass = self.gamepass.value.strip()
        
        if not jogo or not gamepass:
            await interaction.response.send_message(
                "🤔 **Oops!** Preencha todos os campos corretamente!",
                ephemeral=True
            )
            return
        
        # Armazenar os valores para uso posterior
        self.jogo_info = jogo
        self.gamepass_info = gamepass
        
        # Criar o ticket
        await self.criar_ticket(interaction, "gamepass", jogo, gamepass)
    
    async def criar_ticket(self, interaction: discord.Interaction, tipo: str, jogo: str, gamepass: str):
        """Cria um ticket para compra de Gamepass."""
        data = load_json(TICKETS_FILE, {"usuarios": {}})
        uid = str(interaction.user.id)

        if uid in data["usuarios"] and data["usuarios"][uid].get("ticket_aberto"):
            await interaction.response.send_message(
                "🔄 **Você já tem um ticket aberto!**\n"
                "Por favor, use o ticket atual antes de abrir um novo. "
                "Nossa equipe está pronta para te atender lá! 🚀",
                ephemeral=True
            )
            return

        guild = interaction.guild
        user = interaction.user
        category = guild.get_channel(BUY_CATEGORY_ID)

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            user: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
            guild.get_role(STAFF_ROLE_ID): discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)
        }

        tipo_compra = "Gamepass"
        emoji_tipo = "🎮"
        
        channel = await guild.create_text_channel(
            name=f"{emoji_tipo}┃{user.name}-{tipo_compra}-{random.randint(100,999)}",
            category=category,
            overwrites=overwrites,
            topic=f"🎫 Ticket de {tipo_compra} • Cliente: {user.name} • Jogo: {jogo} • Gamepass: {gamepass} • Aberto em: {datetime.now().strftime('%d/%m %H:%M')}"
        )

        data["usuarios"].setdefault(uid, {"tickets": [], "ticket_aberto": False})
        data["usuarios"][uid]["tickets"].append({
            "canal_id": channel.id,
            "tipo": tipo,
            "status": "aberto",
            "criado_em": datetime.utcnow().isoformat(),
            "cliente_nome": user.name,
            "jogo": jogo,
            "gamepass": gamepass
        })
        data["usuarios"][uid]["ticket_aberto"] = True
        save_json(TICKETS_FILE, data)

        embed_ticket = discord.Embed(
            title=f"🎫 **TICKET DE {tipo_compra.upper()} ABERTO!**",
            description=f"""
            ✨ **Olá {user.mention}!** Seja muito bem-vindo(a) ao seu ticket! ✨
            
            **📋 INFORMAÇÕES DO SEU ATENDIMENTO:**
            • **Tipo:** {tipo_compra} {emoji_tipo}
            • **Jogo:** {jogo}
            • **Gamepass:** {gamepass}
            • **Ticket:** #{channel.name}
            • **Horário:** {datetime.now().strftime('%d/%m/%Y às %H:%M')}
            • **Status:** 🔵 **EM ANDAMENTO**
            
            **🎯 PRÓXIMOS PASSOS:**
            1. **Informe o preço da gamepass** - Quanto custa no Roblox?
            2. **Aguarde nossa equipe** - Vamos te atender rapidinho! ⚡
            3. **Siga as instruções** - Vamos guiar você passo a passo!
            4. **Realize o pagamento** - Envie o comprovante quando solicitado
            """,
            color=discord.Color.blue(),
            timestamp=datetime.utcnow()
        )
        
        embed_ticket.add_field(
            name="📞 **ATENDIMENTO RÁPIDO**",
            value="Nossa equipe foi notificada e já vai te atender! ⚡",
            inline=True
        )
        
        embed_ticket.add_field(
            name="💡 **DICA IMPORTANTE**",
            value="Use `/calculadora` para calcular o valor exato da gamepass!",
            inline=True
        )
        
        embed_ticket.set_footer(
            text=f"Atendimento VIP para {user.name} • Obrigado por escolher nossa loja!",
            icon_url=user.avatar.url if user.avatar else None
        )
        embed_ticket.set_thumbnail(url="https://cdn.discordapp.com/emojis/1128316432067063838.gif")

        await channel.send(
            content=f"👋 **Olá {user.mention}!** <@&{STAFF_ROLE_ID}>\n\n**📋 DETALHES DA COMPRA:**\n• **Tipo:** {tipo_compra}\n• **Jogo:** {jogo}\n• **Gamepass:** {gamepass}",
            embed=embed_ticket,
            view=TicketButtons()
        )

        embed_confirma = discord.Embed(
            title="✅ **TICKET CRIADO COM SUCESSO!**",
            description=f"""
            🎉 **Perfeito! Seu ticket foi criado e já está pronto!**
            
            **📋 DETALHES:**
            • **Ticket:** {channel.mention}
            • **Tipo:** {tipo_compra} {emoji_tipo}
            • **Jogo:** {jogo}
            • **Gamepass:** {gamepass}
            • **Aberto em:** {datetime.now().strftime('%H:%M')}
            
            **🚀 VÁ ATÉ O TICKET:**
            Clique no link acima ou vá até o canal {channel.mention} para continuar!
            
            **⏳ AGUARDE...**
            Nossa equipe foi notificada e já vai te atender!
            
            **💡 LEMBRETE:**
            Não se esqueça de informar o preço da gamepass no ticket!
            """,
            color=discord.Color.blue()
        )
        
        await interaction.response.send_message(embed=embed_confirma, ephemeral=True)

# ======================
# CLASSES DE UI (ATUALIZADAS)
# ======================

class RobuxToReaisModal(discord.ui.Modal, title="💎 Conversor: Robux → Reais"):
    robux = discord.ui.TextInput(
        label="🎯 Quantos Robux você quer receber?",
        placeholder="Digite apenas números (ex: 1000, 5000, 10000)",
        required=True,
        max_length=10
    )

    async def on_submit(self, interaction: discord.Interaction):
        try:
            robux_liquidos = int(self.robux.value)
            
            if robux_liquidos <= 0:
                await interaction.response.send_message(
                    "🤔 **Oops!** Você precisa digitar um número maior que zero!",
                    ephemeral=True
                )
                return
            
            valor_reais = robux_liquidos * ROBUX_RATE
            valor_gamepass = calcular_valor_gamepass(robux_liquidos)
            taxa_roblox = valor_gamepass - robux_liquidos
            percentual_taxa = (taxa_roblox / valor_gamepass) * 100
            
            embed = discord.Embed(
                title="🎮 **CONVERSÃO ROBUX → REAIS** 🎮",
                color=0x00ff00,
                timestamp=datetime.utcnow()
            )
            
            embed.description = "✨ **Aqui está o seu cálculo detalhado!** ✨"
            embed.add_field(
                name="📦 **SEU PEDIDO**",
                value=f"```💎 {robux_liquidos:,} Robux Líquidos```",
                inline=False
            )
            embed.add_field(
                name="💵 **VALOR EM REAIS**",
                value=f"```💰 R$ {valor_reais:,.2f}```",
                inline=False
            )
            embed.add_field(name="\u200b", value="━━━━━━━━━━━━━━━━━━━━", inline=False)
            embed.add_field(
                name="🎯 **VALOR DA GAMEPASS**",
                value=f"```🎮 {valor_gamepass:,} Robux```",
                inline=False
            )
            embed.add_field(
                name="🏛️ **TAXA DO ROBLOX**",
                value=f"```📉 {taxa_roblox:,} Robux ({percentual_taxa:.0f}%)```",
                inline=True
            )
            embed.add_field(
                name="🎁 **VOCÊ RECEBE**",
                value=f"```💎 {robux_liquidos:,} Robux```",
                inline=True
            )
            embed.add_field(name="\u200b", value="━━━━━━━━━━━━━━━━━━━━", inline=False)
            embed.add_field(
                name="💡 **COMO FUNCIONA?**",
                value=f"""
                • **Para receber {robux_liquidos:,} Robux líquidos**, você precisa criar uma gamepass de **{valor_gamepass:,} Robux**
                • O Roblox retém **{percentual_taxa:.0f}%** ({taxa_roblox:,} Robux) como taxa
                • Você fica com **{robux_liquidos:,} Robux** (70% do valor da gamepass)
                • **Preço final:** R$ {valor_reais:,.2f}
                """,
                inline=False
            )
            embed.set_footer(
                text=f"✨ Cálculo feito para {interaction.user.name} • 💰",
                icon_url=interaction.user.avatar.url if interaction.user.avatar else None
            )
            embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/1128316432609128488.gif")

            await interaction.response.send_message(embed=embed, ephemeral=True)
        except ValueError:
            await interaction.response.send_message(
                "❌ **Formato inválido!**\nPor favor, digite apenas números (ex: 1000, 5000, 10000)",
                ephemeral=True
            )


class ReaisToRobuxModal(discord.ui.Modal, title="💸 Conversor: Reais → Robux"):
    reais = discord.ui.TextInput(
        label="💵 Quanto você quer investir em Reais?",
        placeholder="Ex: 35.00, 50, 100.50",
        required=True,
        max_length=10
    )

    async def on_submit(self, interaction: discord.Interaction):
        try:
            valor_reais = float(self.reais.value)
            
            if valor_reais <= 0:
                await interaction.response.send_message(
                    "🤔 **Hmm...** O valor precisa ser maior que zero! Tente novamente!",
                    ephemeral=True
                )
                return
            
            robux_liquidos = round(valor_reais / ROBUX_RATE)
            valor_gamepass = calcular_valor_gamepass(robux_liquidos)
            taxa_roblox = valor_gamepass - robux_liquidos
            percentual_taxa = (taxa_roblox / valor_gamepass) * 100
            
            embed = discord.Embed(
                title="💎 **CONVERSÃO REAIS → ROBUX** 💎",
                color=0x5865F2,
                timestamp=datetime.utcnow()
            )
            
            embed.description = "✨ **Transformando seu dinheiro em Robux!** ✨"
            embed.add_field(
                name="💵 **SEU INVESTIMENTO**",
                value=f"```💰 R$ {valor_reais:,.2f}```",
                inline=False
            )
            embed.add_field(
                name="🎁 **ROBUX QUE VOCÊ RECEBE**",
                value=f"```💎 {robux_liquidos:,} Robux```",
                inline=False
            )
            embed.add_field(name="\u200b", value="━━━━━━━━━━━━━━━━━━━━", inline=False)
            embed.add_field(
                name="🎯 **VALOR DA GAMEPASS**",
                value=f"```🎮 {valor_gamepass:,} Robux```",
                inline=False
            )
            embed.add_field(
                name="🏛️ **TAXA DO ROBLOX**",
                value=f"```📉 {taxa_roblox:,} Robux ({percentual_taxa:.0f}%)```",
                inline=True
            )
            embed.add_field(
                name="💎 **VOCÊ RECEBE**",
                value=f"```💎 {robux_liquidos:,} Robux```",
                inline=True
            )
            embed.set_footer(
                text=f"✨ Conversão para {interaction.user.name} • ⚡",
                icon_url=interaction.user.avatar.url if interaction.user.avatar else None
            )
            embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/1128316432609128488.gif")

            await interaction.response.send_message(embed=embed, ephemeral=True)
        except ValueError:
            await interaction.response.send_message(
                "❌ **Valor inválido!**\nDigite um número válido (ex: 35, 50.00, 100.50)",
                ephemeral=True
            )


class CalculatorView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Robux → Reais",
        style=discord.ButtonStyle.success,
        emoji="💎"
    )
    async def robux_to_reais(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(RobuxToReaisModal())

    @discord.ui.button(
        label="Reais → Robux",
        style=discord.ButtonStyle.primary,
        emoji="💸"
    )
    async def reais_to_robux(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ReaisToRobuxModal())


class PurchaseView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Comprar Robux",
        style=discord.ButtonStyle.success,
        emoji="💎",
        row=0
    )
    async def comprar_robux(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(RobuxPurchaseModal())

    @discord.ui.button(
        label="Comprar Gamepass",
        style=discord.ButtonStyle.primary,
        emoji="🎮",
        row=0
    )
    async def comprar_gamepass(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(GamepassPurchaseModal())


class TicketButtons(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    def is_staff(self, member):
        return STAFF_ROLE_ID in [r.id for r in member.roles]

    def get_ticket_data(self, channel_id):
        data = load_json(TICKETS_FILE, {"usuarios": {}})
        for uid, udata in data["usuarios"].items():
            for ticket in udata["tickets"]:
                if ticket["canal_id"] == channel_id:
                    return uid, ticket, data
        return None, None, data

    async def send_log(self, guild, embed):
        channel = guild.get_channel(LOG_CHANNEL_ID)
        if channel:
            await channel.send(embed=embed)

    @discord.ui.button(
        label="Confirmar Pagamento",
        style=discord.ButtonStyle.success,
        emoji="✅",
        row=0
    )
    async def confirm_payment(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.is_staff(interaction.user):
            await interaction.response.send_message(
                "🔒 **Acesso restrito!**\nApenas membros da equipe podem confirmar pagamentos.",
                ephemeral=True
            )
            return

        uid, ticket, data = self.get_ticket_data(interaction.channel.id)
        if not ticket or ticket["status"] == "fechado":
            await interaction.response.send_message(
                "⚠️ **Este ticket já foi finalizado!**\nNão é possível alterar o status.",
                ephemeral=True
            )
            return

        ticket["status"] = "confirmado"
        ticket["confirmado_por"] = interaction.user.id
        ticket["confirmado_por_nome"] = interaction.user.name
        ticket["confirmado_em"] = datetime.utcnow().isoformat()
        data["usuarios"][uid]["ticket_aberto"] = False
        save_json(TICKETS_FILE, data)

        compras = load_json(PURCHASE_COUNT_FILE, {})
        compras[uid] = compras.get(uid, 0) + 1
        save_json(PURCHASE_COUNT_FILE, compras)

        cliente = interaction.guild.get_member(int(uid))
        if cliente:
            try:
                embed_dm = discord.Embed(
                    title="🎉 **PAGAMENTO CONFIRMADO!** 🎉",
                    description=f"""
                    **✅ ÓTIMA NOTÍCIA! Seu pagamento foi confirmado com sucesso!**
                    
                    **📋 DETALHES DA TRANSAÇÃO:**
                    • **Status:** ✅ **APROVADO**
                    • **Confirmado por:** {interaction.user.mention}
                    • **Horário:** {datetime.now().strftime('%d/%m/%Y às %H:%M')}
                    • **Ticket:** #{interaction.channel.id}
                    
                    **📦 DETALHES DA COMPRA:**
                    """,
                    color=discord.Color.green()
                )
                
                # Adicionar informações específicas da compra
                if ticket["tipo"] == "robux":
                    quantidade = ticket.get("quantidade", "N/A")
                    embed_dm.add_field(
                        name="**Tipo:** Robux 💎",
                        value=f"**Quantidade:** {quantidade:,} Robux",
                        inline=False
                    )
                else:
                    jogo = ticket.get("jogo", "N/A")
                    gamepass = ticket.get("gamepass", "N/A")
                    embed_dm.add_field(
                        name="**Tipo:** Gamepass 🎮",
                        value=f"**Jogo:** {jogo}\n**Gamepass:** {gamepass}",
                        inline=False
                    )
                
                embed_dm.add_field(
                    name="**🙏 AGRADECIMENTO:**",
                    value="Muito obrigado por comprar conosco! Sua satisfação é nossa prioridade! ✨",
                    inline=False
                )
                
                embed_dm.add_field(
                    name="**🎁 PRÓXIMOS PASSOS:**",
                    value="""
                    1. **Aguarde** a equipe comprar sua gamepass
                    2. **Receba seus Robux** em 5-7 dias após compra! 
                    2.5. **Sua Gamepass** cai na hora! 
                    3. **Verifique seus Robux** em `https://www.roblox.com/transactions` ⭐
                    """,
                    inline=False
                )
                
                embed_dm.set_footer(text="⭐ Volte sempre!")
                await cliente.send(embed=embed_dm)
            except:
                pass

        log = discord.Embed(
            title="📋 **LOG: PAGAMENTO CONFIRMADO**",
            description="Um pagamento foi confirmado com sucesso! ✅",
            color=discord.Color.green(),
            timestamp=datetime.utcnow()
        )
        log.add_field(name="🎫 Ticket", value=f"`{interaction.channel.name}`", inline=True)
        log.add_field(name="👤 Cliente", value=cliente.mention if cliente else f"`{uid}`", inline=True)
        log.add_field(name="💰 Tipo", value=ticket["tipo"].capitalize(), inline=True)
        
        # Adicionar informações específicas da compra no log
        if ticket["tipo"] == "robux":
            quantidade = ticket.get("quantidade", "N/A")
            log.add_field(name="📦 Quantidade", value=f"`{quantidade:,} Robux`", inline=True)
        else:
            jogo = ticket.get("jogo", "N/A")
            gamepass = ticket.get("gamepass", "N/A")
            log.add_field(name="🎮 Jogo", value=f"`{jogo}`", inline=True)
            log.add_field(name="💎 Gamepass", value=f"`{gamepass}`", inline=True)
        
        log.add_field(name="🕒 Aberto em", value=datetime.fromisoformat(ticket["criado_em"]).strftime('%d/%m %H:%M'), inline=True)
        log.add_field(name="✅ Confirmado por", value=interaction.user.mention, inline=True)
        log.add_field(name="📊 Total de compras", value=f"`{compras.get(uid, 0)}` compras", inline=True)
        log.set_footer(text=f"Staff: {interaction.user.name} • Sistema de Logs")
        await self.send_log(interaction.guild, log)

        embed_confirma = discord.Embed(
            title="✅ **PAGAMENTO CONFIRMADO COM SUCESSO!**",
            description=f"""
            **🎉 PARABÉNS!** O pagamento foi confirmado e a transação está **APROVADA**!
            
            **📋 STATUS DA TRANSAÇÃO:**
            • **Status:** 🟢 **CONFIRMADO**
            • **Por:** {interaction.user.mention}
            • **Em:** {datetime.now().strftime('%d/%m às %H:%M')}
            • **Cliente:** {cliente.mention if cliente else 'Usuário não encontrado'}
            
            **📦 DETALHES DA COMPRA:**
            """,
            color=discord.Color.green()
        )
        
        # Adicionar informações específicas da compra
        if ticket["tipo"] == "robux":
            quantidade = ticket.get("quantidade", "N/A")
            embed_confirma.add_field(
                name="**Tipo:** Robux 💎",
                value=f"**Quantidade:** {quantidade:,} Robux",
                inline=False
            )
        else:
            jogo = ticket.get("jogo", "N/A")
            gamepass = ticket.get("gamepass", "N/A")
            embed_confirma.add_field(
                name="**Tipo:** Gamepass 🎮",
                value=f"**Jogo:** {jogo}\n**Gamepass:** {gamepass}",
                inline=False
            )
        
        embed_confirma.add_field(
            name="**🚀 PRÓXIMOS PASSOS:**",
            value="A equipe já vai processar sua solicitação e liberar seu produto!\nAguarde as instruções finais. ⚡",
            inline=False
        )
        
        await interaction.channel.send(embed=embed_confirma)
        await interaction.response.send_message(
            "✅ **Pagamento confirmado!** O cliente foi notificado e o log foi registrado.",
            ephemeral=True
        )

    @discord.ui.button(
        label="Pendente",
        style=discord.ButtonStyle.secondary,
        emoji="⏳",
        row=0
    )
    async def pending_payment(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.is_staff(interaction.user):
            await interaction.response.send_message(
                "🔒 **Acesso restrito!**\nApenas membros da equipe podem marcar como pendente.",
                ephemeral=True
            )
            return

        uid, ticket, data = self.get_ticket_data(interaction.channel.id)
        if not ticket or ticket["status"] == "fechado":
            await interaction.response.send_message(
                "⚠️ **Este ticket já foi finalizado!**",
                ephemeral=True
            )
            return

        ticket["status"] = "pendente"
        save_json(TICKETS_FILE, data)

        log = discord.Embed(
            title="📋 **LOG: PAGAMENTO PENDENTE**",
            description="Um pagamento foi marcado como pendente. ⏳",
            color=discord.Color.orange(),
            timestamp=datetime.utcnow()
        )
        log.add_field(name="🎫 Ticket", value=f"`{interaction.channel.name}`", inline=True)
        log.add_field(name="👤 Staff", value=interaction.user.mention, inline=True)
        
        # Adicionar informações específicas da compra no log
        if ticket["tipo"] == "robux":
            quantidade = ticket.get("quantidade", "N/A")
            log.add_field(name="💰 Tipo", value=f"Robux ({quantidade:,})", inline=True)
        else:
            jogo = ticket.get("jogo", "N/A")
            gamepass = ticket.get("gamepass", "N/A")
            log.add_field(name="💰 Tipo", value=f"Gamepass", inline=True)
            log.add_field(name="🎮 Jogo", value=f"`{jogo}`", inline=True)
            log.add_field(name="💎 Gamepass", value=f"`{gamepass}`", inline=True)
        
        log.add_field(name="📌 Status", value="🟡 **PENDENTE**", inline=True)
        await self.send_log(interaction.guild, log)

        await interaction.response.send_message(
            "⏳ **Status atualizado!** O pagamento foi marcado como pendente.",
            ephemeral=True
        )

    @discord.ui.button(
        label="Cancelar",
        style=discord.ButtonStyle.danger,
        emoji="❌",
        row=1
    )
    async def cancel_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        uid, ticket, data = self.get_ticket_data(interaction.channel.id)
        if not ticket or ticket["status"] == "fechado":
            await interaction.response.send_message(
                "⚠️ **Este ticket já foi finalizado!**",
                ephemeral=True
            )
            return

        if interaction.user.id != int(uid):
            await interaction.response.send_message(
                "🔒 **Apenas o comprador pode cancelar!**\n"
                "Somente o cliente que abriu este ticket pode cancelá-lo.",
                ephemeral=True
            )
            return

        ticket["status"] = "cancelado"
        ticket["fechado_em"] = datetime.utcnow().isoformat()
        ticket["fechado_por"] = interaction.user.id
        data["usuarios"][uid]["ticket_aberto"] = False
        save_json(TICKETS_FILE, data)

        log = discord.Embed(
            title="📋 **LOG: COMPRA CANCELADA**",
            description="Uma compra foi cancelada pelo cliente. ❌",
            color=discord.Color.red(),
            timestamp=datetime.utcnow()
        )
        log.add_field(name="🎫 Ticket", value=f"`{interaction.channel.name}`", inline=True)
        log.add_field(name="👤 Cliente", value=interaction.user.mention, inline=True)
        
        # Adicionar informações específicas da compra no log
        if ticket["tipo"] == "robux":
            quantidade = ticket.get("quantidade", "N/A")
            log.add_field(name="💰 Tipo", value=f"Robux ({quantidade:,})", inline=True)
        else:
            jogo = ticket.get("jogo", "N/A")
            gamepass = ticket.get("gamepass", "N/A")
            log.add_field(name="💰 Tipo", value=f"Gamepass", inline=True)
            log.add_field(name="🎮 Jogo", value=f"`{jogo}`", inline=True)
            log.add_field(name="💎 Gamepass", value=f"`{gamepass}`", inline=True)
        
        log.add_field(name="📌 Status", value="🔴 **CANCELADO**", inline=True)
        await self.send_log(interaction.guild, log)

        embed_cancelado = discord.Embed(
            title="❌ **COMPRA CANCELADA**",
            description=f"""
            **📌 ESTA COMPRA FOI CANCELADA PELO CLIENTE**
            
            **📋 DETALHES:**
            • **Cancelado por:** {interaction.user.mention}
            • **Horário:** {datetime.now().strftime('%d/%m às %H:%M')}
            • **Motivo:** Solicitado pelo cliente
            
            **📦 DETALHES DA COMPRA:**
            """,
            color=discord.Color.red()
        )
        
        # Adicionar informações específicas da compra
        if ticket["tipo"] == "robux":
            quantidade = ticket.get("quantidade", "N/A")
            embed_cancelado.add_field(
                name="**Tipo:** Robux 💎",
                value=f"**Quantidade:** {quantidade:,} Robux",
                inline=False
            )
        else:
            jogo = ticket.get("jogo", "N/A")
            gamepass = ticket.get("gamepass", "N/A")
            embed_cancelado.add_field(
                name="**Tipo:** Gamepass 🎮",
                value=f"**Jogo:** {jogo}\n**Gamepass:** {gamepass}",
                inline=False
            )
        
        embed_cancelado.add_field(
            name="**ℹ️ INFORMAÇÕES:**",
            value="""
            • Ticket será arquivado automaticamente
            • Para nova compra, abra um novo ticket
            • Dúvidas? Entre em contato com nossa equipe
            """,
            inline=False
        )
        
        embed_cancelado.add_field(
            name="**🙏 AGRADECIMENTO:**",
            value="Esperamos vê-lo novamente em uma próxima compra! ✨",
            inline=False
        )
        
        await interaction.channel.send(embed=embed_cancelado)
        await move_to_closed(interaction.channel)
        await interaction.response.send_message(
            "❌ **Compra cancelada!** O ticket será arquivado.",
            ephemeral=True
        )

    @discord.ui.button(
        label="Fechar Ticket",
        style=discord.ButtonStyle.primary,
        emoji="🔐",
        row=1
    )
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.is_staff(interaction.user):
            await interaction.response.send_message(
                "🔒 **Acesso restrito!**\nApenas membros da equipe podem fechar tickets.",
                ephemeral=True
            )
            return

        uid, ticket, data = self.get_ticket_data(interaction.channel.id)
        if not ticket or ticket["status"] == "fechado":
            await interaction.response.send_message(
                "⚠️ **Este ticket já está finalizado!**",
                ephemeral=True
            )
            return

        ticket["status"] = "fechado"
        ticket["fechado_em"] = datetime.utcnow().isoformat()
        ticket["fechado_por"] = interaction.user.id
        ticket["fechado_por_nome"] = interaction.user.name
        data["usuarios"][uid]["ticket_aberto"] = False
        save_json(TICKETS_FILE, data)

        log = discord.Embed(
            title="📋 **LOG: TICKET FECHADO**",
            description="Um ticket foi fechado pela equipe. 🔒",
            color=discord.Color.blurple(),
            timestamp=datetime.utcnow()
        )
        log.add_field(name="🎫 Ticket", value=f"`{interaction.channel.name}`", inline=True)
        log.add_field(name="👤 Staff", value=interaction.user.mention, inline=True)
        log.add_field(name="👤 Cliente", value=f"<@{uid}>", inline=True)
        
        # Adicionar informações específicas da compra no log
        if ticket["tipo"] == "robux":
            quantidade = ticket.get("quantidade", "N/A")
            log.add_field(name="💰 Tipo", value=f"Robux ({quantidade:,})", inline=True)
        else:
            jogo = ticket.get("jogo", "N/A")
            gamepass = ticket.get("gamepass", "N/A")
            log.add_field(name="💰 Tipo", value=f"Gamepass", inline=True)
            log.add_field(name="🎮 Jogo", value=f"`{jogo}`", inline=True)
            log.add_field(name="💎 Gamepass", value=f"`{gamepass}`", inline=True)
        
        log.add_field(name="📌 Status", value="🔵 **FECHADO**", inline=True)
        log.add_field(name="⏰ Duração", value=f"`{(datetime.utcnow() - datetime.fromisoformat(ticket['criado_em'])).seconds//60} minutos`", inline=True)
        await self.send_log(interaction.guild, log)

        embed_fechado = discord.Embed(
            title="🔒 **TICKET ENCERRADO**",
            description=f"""
            **📌 ESTE TICKET FOI OFICIALMENTE ENCERRADO**
            
            **📋 DETALHES DO ENCERRAMENTO:**
            • **Encerrado por:** {interaction.user.mention}
            • **Horário:** {datetime.now().strftime('%d/%m às %H:%M')}
            • **Status:** 🟢 **CONCLUÍDO**
            
            **📦 DETALHES DA COMPRA:**
            """,
            color=discord.Color.blurple()
        )
        
        # Adicionar informações específicas da compra
        if ticket["tipo"] == "robux":
            quantidade = ticket.get("quantidade", "N/A")
            embed_fechado.add_field(
                name="**Tipo:** Robux 💎",
                value=f"**Quantidade:** {quantidade:,} Robux",
                inline=False
            )
        else:
            jogo = ticket.get("jogo", "N/A")
            gamepass = ticket.get("gamepass", "N/A")
            embed_fechado.add_field(
                name="**Tipo:** Gamepass 🎮",
                value=f"**Jogo:** {jogo}\n**Gamepass:** {gamepass}",
                inline=False
            )
        
        embed_fechado.add_field(
            name="**🎯 ATENDIMENTO FINALIZADO:**",
            value="""
            • Todas as etapas foram concluídas
            • Ticket será arquivado automaticamente
            • Histórico preservado para consulta
            """,
            inline=False
        )
        
        embed_fechado.add_field(
            name="**⭐ AVALIAÇÃO:**",
            value="Esperamos que tenha tido uma ótima experiência!\nVolte sempre para novas compras! ✨",
            inline=False
        )
        
        await interaction.channel.send(embed=embed_fechado)
        await move_to_closed(interaction.channel)
        await interaction.response.send_message(
            "🔒 **Ticket fechado!** O canal foi movido para arquivados.",
            ephemeral=True
        )


# ======================
# FUNÇÕES UTILITÁRIAS (MANTIDAS)
# ======================

def load_json(path, default):
    """Carrega dados de um arquivo JSON, criando-o se não existir."""
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(default, f, indent=4)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data):
    """Salva dados em um arquivo JSON."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)


async def move_to_closed(channel: discord.TextChannel):
    """Move um canal para a categoria de tickets fechados."""
    guild = channel.guild
    closed_category = guild.get_channel(CLOSED_CATEGORY_ID)
    staff_role = guild.get_role(STAFF_ROLE_ID)

    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        staff_role: discord.PermissionOverwrite(view_channel=True, send_messages=False, read_message_history=True),
        guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True)
    }

    await channel.edit(category=closed_category, overwrites=overwrites)


# ======================
# INICIALIZAÇÃO DO BOT
# ======================

bot = commands.Bot(command_prefix="!", intents=intents)


# ======================
# COMANDOS HÍBRIDOS (PREFIXO E SLASH) - MANTIDOS
# ======================

@bot.hybrid_command(name="calcular", description="Calcula o valor da gamepass necessário para obter X robux líquidos")
@app_commands.describe(valor="Valor em Robux ou Reais (ex: 1000 ou 35,00)")
async def calcular(ctx, valor: str):
    """Calcula o valor da gamepass necessário para obter X robux líquidos."""
    try:
        valor_clean = valor.replace('.', '').replace(',', '.')
        
        if '.' in valor_clean:
            valor_reais = float(valor_clean)
            robux_liquidos = round(valor_reais / ROBUX_RATE)
            valor_gamepass = calcular_valor_gamepass(robux_liquidos)
            taxa_roblox = valor_gamepass - robux_liquidos
            percentual_taxa = (taxa_roblox / valor_gamepass) * 100
            
            embed = discord.Embed(
                title="**CALCULADORA DE ROBUX**",
                description=f"✨ **Cálculo para R$ {valor_reais:,.2f}** ✨",
                color=0x5865F2,
                timestamp=datetime.utcnow()
            )
            
            embed.add_field(
                name="💵 **VALOR INVESTIDO**",
                value=f"```💰 R$ {valor_reais:,.2f}```",
                inline=False
            )
            embed.add_field(
                name="💎 **ROBUX QUE VOCÊ RECEBE**",
                value=f"```💎 {robux_liquidos:,} Robux```",
                inline=True
            )
            embed.add_field(
                name="🎮 **VALOR DA GAMEPASS**",
                value=f"```🎮 {valor_gamepass:,} Robux```",
                inline=True
            )
            
        else:
            robux_liquidos = int(valor_clean)
            valor_reais = robux_liquidos * ROBUX_RATE
            valor_gamepass = calcular_valor_gamepass(robux_liquidos)
            taxa_roblox = valor_gamepass - robux_liquidos
            percentual_taxa = (taxa_roblox / valor_gamepass) * 100
            
            embed = discord.Embed(
                title="# CALCULADORA DE ROBUX",
                description=f"✨ **Cálculo para {robux_liquidos:,} Robux** ✨",
                color=0x00ff00,
                timestamp=datetime.utcnow()
            )
            
            embed.add_field(
                name="💎 **ROBUX DESEJADOS**",
                value=f"```💎 {robux_liquidos:,} Robux```",
                inline=False
            )
            embed.add_field(
                name="💵 **VALOR EM REAIS**",
                value=f"```💰 R$ {valor_reais:,.2f}```",
                inline=True
            )
            embed.add_field(
                name="🎮 **VALOR DA GAMEPASS**",
                value=f"```🎮 {valor_gamepass:,} Robux```",
                inline=True
            )
        
        embed.set_footer(
            text=f"✨ Calculado para {ctx.author.name} • ⚡ Use /comprar para abrir um ticket!",
            icon_url=ctx.author.avatar.url if ctx.author.avatar else None
        )
        
        await ctx.send(embed=embed)
        
    except ValueError:
        embed_erro = discord.Embed(
            title="❌ **VALOR INVÁLIDO!**",
            description="""
            **📝 FORMATOS ACEITOS:**
            • `/calcular 1000` → Calcula quanto custa 1000 Robux
            • `/calcular 35,00` → Calcula quantos Robux você compra com R$ 35
            
            **💡 DICA:**
            Use `/calculadora` para uma experiência mais fácil com botões!
            """,
            color=discord.Color.red()
        )
        await ctx.send(embed=embed_erro)


@bot.hybrid_command(name="compras", description="Mostra o histórico de compras")
@app_commands.describe(usuario="Usuário para verificar histórico (opcional)")
@commands.has_permissions(administrator=True)
async def compras(ctx, usuario: discord.Member = None):
    """Mostra o histórico de compras de um usuário ou de todos."""
    with open("compras.json", "r", encoding="utf-8") as f:
        dados = json.load(f)

    if usuario:
        total = dados.get(str(usuario.id), 0)
        
        embed = discord.Embed(
            title=f"📊 **HISTÓRICO DE COMPRAS**",
            description=f"**👤 CLIENTE:** {usuario.mention}",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="🎯 **ESTATÍSTICAS**",
            value=f"""
            **🛍️ Total de Compras:** `{total}`
            **⭐ Nível do Cliente:** `{'VIP' if total >= 10 else 'Regular' if total >= 5 else 'Novo'}`
            """,
            inline=False
        )
        
        embed.add_field(
            name="📈 **DESEMPENHO**",
            value=f"""
            • **Primeira compra:** {'Sim' if total > 0 else 'Não'}
            • **Frequência:** {'Alta' if total >= 5 else 'Média' if total >= 2 else 'Baixa'}
            • **Status:** {'Cliente VIP 🏆' if total >= 10 else 'Cliente Fiel ⭐' if total >= 5 else 'Cliente Novo 🌱'}
            """,
            inline=True
        )
        
        embed.set_footer(text=f"Consultado por {ctx.author.name}")
        
        await ctx.send(embed=embed)
    else:
        if not dados:
            embed = discord.Embed(
                title="📭 **SEM HISTÓRICO**",
                description="Nenhuma compra registrada ainda! O primeiro cliente está por vir! 🎉",
                color=discord.Color.orange()
            )
            await ctx.send(embed=embed)
            return

        embed = discord.Embed(
            title="📊 **HISTÓRICO GERAL DE COMPRAS**",
            description="Aqui estão todas as compras realizadas na nossa loja! 📈",
            color=discord.Color.blue()
        )
        
        dados_ordenados = sorted(dados.items(), key=lambda x: x[1], reverse=True)
        
        total_compras = sum(dados.values())
        clientes_unicos = len(dados)
        media_compras = total_compras / clientes_unicos
        
        embed.add_field(
            name="📈 **ESTATÍSTICAS GERAIS**",
            value=f"""
            **🛍️ Total de Compras:** `{total_compras}`
            **👥 Clientes Únicos:** `{clientes_unicos}`
            **📊 Média por Cliente:** `{media_compras:.1f} compras`
            **💰 Faturamento estimado:** `R$ {total_compras * 35:,.2f}`
            """,
            inline=False
        )
        
        top_clientes = []
        for i, (uid, total) in enumerate(dados_ordenados[:10], 1):
            membro = ctx.guild.get_member(int(uid))
            nome = membro.mention if membro else f"`Usuário {uid[:8]}...`"
            
            medalha = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"**{i}.**"
            top_clientes.append(f"{medalha} {nome} → **{total}** compras")
        
        embed.add_field(
            name="🏆 **TOP 10 CLIENTES**",
            value="\n".join(top_clientes) if top_clientes else "Nenhum cliente ainda!",
            inline=False
        )
        
        embed.set_footer(text=f"✨ {total_compras} compras realizadas com sucesso!")
        await ctx.send(embed=embed)


# ======================
# COMANDOS SLASH ESPECÍFICOS (ATUALIZADOS)
# ======================

@bot.tree.command(name="calculadora", description="Abre a calculadora interativa de Robux/Reais")
async def calculadora(interaction: discord.Interaction):
    """Slash command para abrir a calculadora."""
    embed = discord.Embed(
        title="**CALCULADORA DE ROBUX**",
        description="""
        **🎯 COMO FUNCIONA?**
        Nosso sistema calcula **automaticamente** o valor da gamepass necessária,
        considerando a **taxa de 30%** que o Roblox cobra!
        
        **💰 ROBUX → REAIS**
        • Descubra quanto custa X Robux em Reais
        • Veja o valor exato da gamepass necessária
        
        **💸 REAIS → ROBUX**
        • Veja quantos Robux você compra com X Reais
        • Veja o valor exato da gamepass necessária
        """,
        color=discord.Color.gold()
    )
    
    embed.set_footer(text="Também use `/calcular [valor]` - Ex: `/calcular 1000` ou `/calcular 35,00`")
    embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/1128316432609128488.gif")

    await interaction.response.send_message(embed=embed, view=CalculatorView(), ephemeral=True)


@bot.tree.command(name="comprar", description="Abre um ticket para comprar Robux ou Gamepass")
async def comprar(interaction: discord.Interaction):
    """Slash command para abrir um ticket de compra."""
    embed = discord.Embed(
        title="**PAINEL DE COMPRAS**",
        description="""
        ✨ **SEJA BEM-VINDO À NOSSA LOJA!** ✨
        
        **🚀 COMO FUNCIONA?**
        1. Escolha abaixo o que quer comprar
        2. Preencha as informações solicitadas
        3. Abra um ticket de atendimento
        4. Nossa equipe te atende rapidinho!
        5. Receba seu produto em minutos! ⏰
        """,
        color=discord.Color.blurple()
    )
    
    embed.set_footer(text="💡 Use nossa calculadora com `/calculadora` para calcular o valor exato da gamepass!")
    embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/1128316432067063838.gif")
    
    await interaction.response.send_message(embed=embed, view=PurchaseView(), ephemeral=True)


# ======================
# COMANDOS ADMINISTRATIVOS (MANTIDOS)
# ======================

@bot.hybrid_command(name="painelcompras", description="Envia o painel de compras em um canal específico")
@app_commands.describe(canal="Canal onde enviar o painel (opcional)")
@commands.has_permissions(administrator=True)
async def painelcompras(ctx, canal: discord.TextChannel = None):
    """Envia o painel de compras em um canal específico."""
    if canal is None:
        canal = ctx.channel
    
    embed = discord.Embed(
        title="**PAINEL DE COMPRAS**",
        description="""
        ✨ **SEJA BEM-VINDO À NOSSA LOJA!** ✨
        
        **🚀 COMO FUNCIONA?**
        1. Escolha abaixo o que quer comprar
        2. Preencha as informações solicitadas
        3. Abra um ticket de atendimento
        4. Nossa equipe te atende rapidinho!
        5. Receba seu produto em minutos! ⏰
        
        **💎 ROBUX:**
        • Compre Robux com desconto
        • Receba diretamente na sua conta
        
        **🎮 GAMEPASS:**
        • Compre gamepasses de qualquer jogo
        • Pagamento facilitado
        """,
        color=discord.Color.blurple()
    )
    
    embed.set_footer(text="💡 Use nossa calculadora em #💱〃calculadora para calcular o valor exato da gamepass!")
    embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/1128316432067063838.gif")
    
    await canal.send(embed=embed, view=PurchaseView())
    
    embed_confirma = discord.Embed(
        title="✅ **PAINEL ENVIADO!**",
        description=f"✨ **Perfeito!** O painel de compras foi enviado para {canal.mention}!",
        color=discord.Color.green()
    )
    await ctx.send(embed=embed_confirma, ephemeral=True)


@bot.hybrid_command(name="painelcalculadora", description="Envia o painel da calculadora de conversão")
@app_commands.describe(canal="Canal onde enviar o painel (opcional)")
@commands.has_permissions(administrator=True)
async def painelcalculadora(ctx, canal: discord.TextChannel = None):
    """Envia o painel da calculadora de conversão em um canal específico."""
    if canal is None:
        canal = ctx.channel
    
    embed = discord.Embed(
        title="**CALCULADORA DE ROBUX**",
        description="""
        **🎯 COMO FUNCIONA?**
        Nosso sistema calcula **automaticamente** o valor da gamepass necessária,
        considerando a **taxa de 30%** que o Roblox cobra!
        
        **💰 ROBUX → REAIS**
        • Descubra quanto custa X Robux em Reais
        • Veja o valor exato da gamepass necessária
        
        **💸 REAIS → ROBUX**
        • Veja quantos Robux você compra com X Reais
        • Veja o valor exato da gamepass necessária
        """,
        color=discord.Color.gold()
    )
    
    embed.set_footer(text="Também use `/calcular [valor]` - Ex: `/calcular 1000` ou `/calcular 35,00`")
    embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/1128316432609128488.gif")

    await canal.send(embed=embed, view=CalculatorView())
    
    embed_confirma = discord.Embed(
        title="✅ **CALCULADORA ENVIADA!**",
        description=f"✨ **Perfeito!** A calculadora foi enviada para {canal.mention}!",
        color=discord.Color.green()
    )
    await ctx.send(embed=embed_confirma, ephemeral=True)


@bot.hybrid_command(name="limpartickets", description="Limpa todos os dados de tickets")
@commands.has_permissions(administrator=True)
async def limpartickets(ctx):
    """Limpa o arquivo de tickets."""
    data = {"usuarios": {}}
    with open("tickets.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

    await ctx.send("🧹 tickets.json limpo com sucesso.", ephemeral=True)


@bot.hybrid_command(name="adicionarcompra", description="Adiciona uma compra ao histórico de um usuário")
@app_commands.describe(usuario="Usuário para adicionar compra")
@commands.has_permissions(administrator=True)
async def adicionarcompra(ctx, usuario: discord.User):
    """Adiciona uma compra ao histórico de um usuário."""
    try:
        with open("compras.json", "r", encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        data = {}

    uid = str(usuario.id)

    if uid not in data:
        data[uid] = 0

    data[uid] += 1

    with open("compras.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

    await ctx.send(f"🧾 Compra adicionada com sucesso para {usuario.mention}.", ephemeral=True)


@bot.hybrid_command(name="sync", description="Sincroniza os comandos slash (apenas dono)")
@commands.is_owner()
async def sync(ctx):
    """Sincroniza os comandos slash com o Discord."""
    await bot.tree.sync()
    await ctx.send("✅ Comandos slash sincronizados com sucesso!", ephemeral=True)


# ======================
# EVENTOS DO BOT (MANTIDOS)
# ======================

@bot.event
async def on_ready():
    """Evento disparado quando o bot está pronto."""
    print(f"✨ Bot conectado como: {bot.user}")
    print(f"🆔 ID do Bot: {bot.user.id}")
    print(f"📊 Servidores: {len(bot.guilds)}")
    print(f"👥 Usuários: {sum(g.member_count for g in bot.guilds)}")
    print("✅ Bot está pronto para uso! 🚀")
    
    # Sincronizar comandos slash
    await bot.tree.sync()
    print("✅ Comandos slash sincronizados!")
    
    # Definir status do bot
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name="Robux barato e seguro 💎"
        ),
        status=discord.Status.online
    )


# ======================
# EXECUÇÃO DO BOT
# ======================

if __name__ == "__main__":
    print("🚀 Iniciando bot...")
    print("🔧 Carregando configurações...")
    print("💾 Verificando arquivos JSON...")
    bot.run(TOKEN)