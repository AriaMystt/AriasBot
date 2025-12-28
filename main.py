import discord
from discord.ext import commands
from discord import app_commands
import random
from datetime import datetime, timedelta, timezone
import json
import os
import asyncio
from dotenv import load_dotenv

load_dotenv()

# Timezone configuration (GMT -3)
GMT_MINUS_3 = timezone(timedelta(hours=-3))

# ======================
# CONFIGURAÇÕES
# ======================
TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.invites = True

# IDs de Canais e Cargos
BUY_CATEGORY_ID = 1449312175448391833
CLOSED_CATEGORY_ID = 1449319381422051400
STAFF_ROLE_ID = 1449319423780458597
LOG_CHANNEL_ID = 1449319519733551245
CLIENT_ROLE_ID = 1449248434317164608  # ADICIONE AQUI O ID DO CARGO PARA CLIENTES

# Taxas de Conversão
ROBUX_RATE = 0.035  # 1 Robux = R$ 0,035
ROBLOX_TAX = 0.30   # Roblox pega 30% da gamepass

# Arquivos JSON
TICKETS_FILE = "tickets.json"
PURCHASE_COUNT_FILE = "compras.json"
GIVEAWAYS_FILE = "giveaways.json"
DISCOUNT_CODES_FILE = "discount_codes.json"

# Sistema de Tiers
TIERS = [
    {"name": "Base", "min_spent": 0.0, "discount": 0.0},
    {"name": "Bronze", "min_spent": 10.0, "discount": 0.01},
    {"name": "Prata", "min_spent": 35.0, "discount": 0.02},
    {"name": "Ouro", "min_spent": 70.0, "discount": 0.04},
    {"name": "Platina", "min_spent": 120.0, "discount": 0.06},
    {"name": "Diamante", "min_spent": 180.0, "discount": 0.08},
    {"name": "Elite", "min_spent": 250.0, "discount": 0.10},
]

# Sistema de Bonus de Entries para Giveaways
GIVEAWAY_ROLE_BONUSES = {
    # Role ID: bonus entries
    1449248434317164608: 1,  # CLIENT_ROLE_ID - Clients get +2 entries
    # Add more role bonuses here as needed
    # Example: 123456789012345678: 3,  # Some role gets +3 entries
}

# Sistema de Bonus de Entries por Convites
GIVEAWAY_INVITE_BONUS = 1  # +1 entry por convite válido
MIN_ACCOUNT_AGE_DAYS = 7  # Conta deve ter pelo menos 7 dias
MIN_LAST_SEEN_HOURS = 48  # Usuário deve ter ficado online nas últimas 48 horas

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

def get_user_tier(user_id):
    """Retorna o tier do usuário e o desconto baseado no total gasto."""
    data = load_json(PURCHASE_COUNT_FILE, {})
    spent = data.get(str(user_id), {}).get("total", 0.0)
    
    # Encontra o tier apropriado baseado no total gasto
    for tier in reversed(TIERS):  # Começa do maior para o menor
        if spent >= tier["min_spent"]:
            return tier["name"], tier["discount"]
    
    # Fallback para o primeiro tier
    return TIERS[0]["name"], TIERS[0]["discount"]

def get_tier_by_spent(spent):
    """Retorna o tier baseado no total gasto."""
    for tier in reversed(TIERS):  # Começa do maior para o menor
        if spent >= tier["min_spent"]:
            return tier
    return TIERS[0]

def get_tier_by_name(name):
    """Retorna o tier baseado no nome, case-insensitive."""
    for tier in TIERS:
        if tier["name"].lower() == name.lower():
            return tier
    return None

def get_giveaway_entries(member: discord.Member, giveaway_data: dict = None) -> int:
    """Calcula o número total de entries para um usuário baseado em seus roles e convites válidos."""
    base_entries = 1  # Everyone gets 1 base entry
    bonus_entries = 0

    # Check giveaway settings
    enable_roles = True
    enable_invites = True
    
    if giveaway_data and "settings" in giveaway_data:
        enable_roles = giveaway_data["settings"].get("enable_role_bonuses", True)
        enable_invites = giveaway_data["settings"].get("enable_invite_bonuses", True)

    # Check each role the user has (only if role bonuses are enabled)
    if enable_roles:
        for role in member.roles:
            if role.id in GIVEAWAY_ROLE_BONUSES:
                bonus_entries += GIVEAWAY_ROLE_BONUSES[role.id]

    # Add invite bonuses if giveaway data is provided and invites are enabled
    if giveaway_data and enable_invites:
        invite_bonus = calculate_invite_bonus(member, giveaway_data)
        bonus_entries += invite_bonus

    return base_entries + bonus_entries


def calculate_invite_bonus(member: discord.Member, giveaway_data: dict) -> int:
    """Calcula o bônus de entries baseado em convites válidos feitos durante o giveaway."""
    user_id = str(member.id)
    bonus_entries = 0

    # Check if user has invite tracking data
    if "invite_tracking" in giveaway_data and user_id in giveaway_data["invite_tracking"]:
        user_invites = giveaway_data["invite_tracking"][user_id]

        for invite_code, invite_data in user_invites.items():
            # Check if invite was created during giveaway period
            invite_created = datetime.fromisoformat(invite_data["created_at"]).replace(tzinfo=GMT_MINUS_3)
            giveaway_start = datetime.fromisoformat(giveaway_data["created_at"]).replace(tzinfo=GMT_MINUS_3)
            giveaway_end = datetime.fromisoformat(giveaway_data["end_time"]).replace(tzinfo=GMT_MINUS_3)

            if giveaway_start <= invite_created <= giveaway_end:
                # Count valid uses
                valid_uses = 0
                for use_data in invite_data.get("uses", []):
                    invited_user_id = use_data["user_id"]

                    # Check if invited user is still in server
                    invited_member = member.guild.get_member(int(invited_user_id))
                    if invited_member and is_valid_invited_user(invited_member):
                        valid_uses += 1

                bonus_entries += valid_uses * GIVEAWAY_INVITE_BONUS

    return bonus_entries


def is_valid_invited_user(member: discord.Member) -> bool:
    """Verifica se um usuário convidado é válido (não é bot, conta antiga, etc.)."""
    # Check if user is a bot
    if member.bot:
        return False

    # Check account age (must be at least MIN_ACCOUNT_AGE_DAYS old)
    account_age = datetime.now(GMT_MINUS_3) - member.created_at.replace(tzinfo=GMT_MINUS_3)
    if account_age.days < MIN_ACCOUNT_AGE_DAYS:
        return False

    # Check if user has been seen recently (last message or status update)
    # Discord.py doesn't provide direct last seen, but we can check if they have recent activity
    # For now, we'll assume they're valid if they're not offline and have been in server for some time
    if member.status == discord.Status.offline:
        # If offline, check how long they've been in the server
        time_in_server = datetime.now(GMT_MINUS_3) - member.joined_at.replace(tzinfo=GMT_MINUS_3)
        if time_in_server.total_seconds() < MIN_LAST_SEEN_HOURS * 3600:
            return False

    return True


def select_weighted_winner(participants: dict) -> str:
    """Seleciona um vencedor baseado no número de entries (weighted random)."""
    # Create weighted list
    weighted_list = []
    for user_id, data in participants.items():
        entries = data.get("entries", 1)
        weighted_list.extend([user_id] * entries)
    
    if not weighted_list:
        return None
    
    return random.choice(weighted_list)


def validate_discount_code(code: str) -> tuple:
    """Valida um código de desconto e retorna (is_valid, percentage, uses_left)."""
    if not code:
        return False, 0, 0
    
    codes = load_json(DISCOUNT_CODES_FILE, {})
    code_upper = code.upper().strip()
    
    if code_upper in codes:
        code_data = codes[code_upper]
        if code_data.get("uses", 0) > 0:
            return True, code_data.get("percentage", 0), code_data.get("uses", 0)
    
    return False, 0, 0


def apply_discount(price: float, discount_percentage: int) -> float:
    """Aplica desconto percentual ao preço."""
    if discount_percentage <= 0:
        return price
    return price * (1 - discount_percentage / 100)


def decrement_discount_uses(code: str):
    """Decrementa as uses de um código de desconto."""
    if not code:
        return
    
    codes = load_json(DISCOUNT_CODES_FILE, {})
    code_upper = code.upper().strip()
    
    if code_upper in codes:
        codes[code_upper]["uses"] = max(0, codes[code_upper].get("uses", 0) - 1)
        save_json(DISCOUNT_CODES_FILE, codes)


# ======================
# MODAIS PARA COMPRAS (MANTIDO)
# ======================

class RobuxPurchaseModal(discord.ui.Modal, title="💎 Comprar Robux"):
    quantidade = discord.ui.TextInput(
        label="🎯 Quantos Robux você quer comprar?",
        placeholder="Digite apenas números (ex: 1000, 5000, 10000)",
        required=True,
        max_length=10
    )
    
    discount_code = discord.ui.TextInput(
        label="🎟️ Código de Desconto (opcional)",
        placeholder="Digite o código ou deixe vazio",
        required=False,
        max_length=20
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
            
            # Validar código de desconto
            discount_code = self.discount_code.value.strip() if self.discount_code.value else ""
            discount_percentage = 0
            discount_valid = False
            
            if discount_code:
                discount_valid, discount_percentage, uses_left = validate_discount_code(discount_code)
                if not discount_valid:
                    await interaction.response.send_message(
                        "❌ **Código de desconto inválido ou esgotado!**\n"
                        "Verifique o código e tente novamente, ou deixe o campo vazio.",
                        ephemeral=True
                    )
                    return
            
            # Calcular preço com desconto
            valor_base = quantidade * ROBUX_RATE
            valor_final = apply_discount(valor_base, discount_percentage)
            
            # Armazenar valores no modal para uso posterior
            self.quantidade_robux = quantidade
            self.discount_code_used = discount_code.upper() if discount_valid else ""
            self.discount_percentage = discount_percentage
            self.valor_final = valor_final
            
            # Criar o ticket
            await self.criar_ticket(interaction, "robux", quantidade, discount_code if discount_valid else None, valor_final)
            
        except ValueError:
            await interaction.response.send_message(
                "❌ **Formato inválido!**\nPor favor, digite apenas números (ex: 1000, 5000, 10000)",
                ephemeral=True
            )
    
    async def criar_ticket(self, interaction: discord.Interaction, tipo: str, quantidade: int, discount_code: str = None, valor_final: float = None):
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
        ticket_data = {
            "canal_id": channel.id,
            "tipo": tipo,
            "status": "aberto",
            "criado_em": datetime.now(GMT_MINUS_3).isoformat(),
            "cliente_nome": user.name,
            "quantidade": quantidade
        }
        
        if discount_code:
            ticket_data["discount_code"] = discount_code.upper()
            ticket_data["discount_percentage"] = getattr(self, 'discount_percentage', 0)
            ticket_data["valor_final"] = valor_final
        
        data["usuarios"][uid]["tickets"].append(ticket_data)
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
            timestamp=datetime.now(GMT_MINUS_3)
        )
        
        # Adicionar valor em reais calculado
        if discount_code and valor_final is not None:
            valor_reais = valor_final
            valor_original = quantidade * ROBUX_RATE
            embed_ticket.add_field(
                name="💰 **VALOR COM DESCONTO**",
                value=f"```💵 R$ {valor_reais:,.2f}```\n~~R$ {valor_original:,.2f}~~\n🎟️ **Código:** `{discount_code.upper()}`",
                inline=True
            )
        else:
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
    
    discount_code = discord.ui.TextInput(
        label="🎟️ Código de Desconto (opcional)",
        placeholder="Digite o código ou deixe vazio",
        required=False,
        max_length=20
    )

    async def on_submit(self, interaction: discord.Interaction):
        jogo = self.jogo.value.strip()
        gamepass = self.gamepass.value.strip()
        discount_code = self.discount_code.value.strip() if self.discount_code.value else ""
        
        if not jogo or not gamepass:
            await interaction.response.send_message(
                "🤔 **Oops!** Preencha todos os campos corretamente!",
                ephemeral=True
            )
            return
        
        # Validar código de desconto
        discount_percentage = 0
        discount_valid = False
        
        if discount_code:
            discount_valid, discount_percentage, uses_left = validate_discount_code(discount_code)
            if not discount_valid:
                await interaction.response.send_message(
                    "❌ **Código de desconto inválido ou esgotado!**\n"
                    "Verifique o código e tente novamente, ou deixe o campo vazio.",
                    ephemeral=True
                )
                return
        
        # Armazenar os valores para uso posterior
        self.jogo_info = jogo
        self.gamepass_info = gamepass
        self.discount_code_used = discount_code.upper() if discount_valid else ""
        self.discount_percentage = discount_percentage
        
        # Criar o ticket
        await self.criar_ticket(interaction, "gamepass", jogo, gamepass, discount_code if discount_valid else None)
    
    async def criar_ticket(self, interaction: discord.Interaction, tipo: str, jogo: str, gamepass: str, discount_code: str = None):
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
        ticket_data = {
            "canal_id": channel.id,
            "tipo": tipo,
            "status": "aberto",
            "criado_em": datetime.now(GMT_MINUS_3).isoformat(),
            "cliente_nome": user.name,
            "jogo": jogo,
            "gamepass": gamepass
        }
        
        if discount_code:
            ticket_data["discount_code"] = discount_code.upper()
            ticket_data["discount_percentage"] = getattr(self, 'discount_percentage', 0)
        
        data["usuarios"][uid]["tickets"].append(ticket_data)
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
            timestamp=datetime.now(GMT_MINUS_3)
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
        
        if discount_code:
            embed_ticket.add_field(
                name="🎟️ **CÓDIGO DE DESCONTO**",
                value=f"**Código:** `{discount_code.upper()}`\n**Desconto:** {getattr(self, 'discount_percentage', 0)}%",
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
            # aceitar separadores de milhares como '.' e ',' e limpar entrada
            robux_raw = self.robux.value.strip()
            robux_clean = robux_raw.replace('.', '').replace(',', '')
            robux_liquidos = int(robux_clean)

            if robux_liquidos <= 0:
                await interaction.response.send_message(
                    "🤔 **Oops!** Você precisa digitar um número maior que zero!",
                    ephemeral=True
                )
                return
            
            # Verificar tier do usuário
            tier, discount = get_user_tier(interaction.user.id)
            
            valor_reais = robux_liquidos * ROBUX_RATE
            valor_reais_desconto = valor_reais * (1 - discount)
            valor_gamepass = calcular_valor_gamepass(robux_liquidos)
            taxa_roblox = valor_gamepass - robux_liquidos
            percentual_taxa = (taxa_roblox / valor_gamepass) * 100
            
            embed = discord.Embed(
                title="🎮 **CONVERSÃO ROBUX → REAIS** 🎮",
                color=0x00ff00,
                timestamp=datetime.now(GMT_MINUS_3)
            )
            
            embed.description = f"✨ **Aqui está o seu cálculo detalhado!** ✨\n\n🏆 **Seu Tier:** {tier} ({'Sem desconto' if discount == 0 else f'{discount*100:.0f}% de desconto'})"
            embed.add_field(
                name="📦 **SEU PEDIDO**",
                value=f"```💎 {robux_liquidos:,} Robux```",
                inline=False
            )
            embed.add_field(
                name="💵 **VALOR EM REAIS**",
                value=f"```💰 R$ {valor_reais:,.2f}```",
                inline=True
            )
            if discount > 0:
                embed.add_field(
                    name="💸 **COM DESCONTO**",
                    value=f"```💰 R$ {valor_reais_desconto:,.2f}```",
                    inline=True
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
            # Determinar preço final exibido com ou sem desconto
            preco_final = valor_reais_desconto if discount > 0 else valor_reais
            embed.add_field(
                name="💡 **COMO FUNCIONA?**",
                value=f"""
                • **Para receber {robux_liquidos:,} Robux líquidos**, você precisa criar uma gamepass de **{valor_gamepass:,} Robux**
                • O Roblox retém **{percentual_taxa:.0f}%** ({taxa_roblox:,} Robux) como taxa
                • Você fica com **{robux_liquidos:,} Robux** (70% do valor da gamepass)
                • **Preço final:** R$ {preco_final:,.2f}
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
            # aceitar vírgulas como separador decimal
            reais_raw = self.reais.value.strip()
            reais_clean = reais_raw.replace(',', '.')
            valor_reais = float(reais_clean)
            
            if valor_reais <= 0:
                await interaction.response.send_message(
                    "🤔 **Hmm...** O valor precisa ser maior que zero! Tente novamente!",
                    ephemeral=True
                )
                return
            
            # Verificar tier do usuário
            tier, discount = get_user_tier(interaction.user.id)
            
            effective_rate = ROBUX_RATE * (1 - discount)
            robux_with_discount = round(valor_reais / effective_rate)
            robux_without_discount = round(valor_reais / ROBUX_RATE)
            valor_gamepass = calcular_valor_gamepass(robux_with_discount)
            taxa_roblox = valor_gamepass - robux_with_discount
            percentual_taxa = (taxa_roblox / valor_gamepass) * 100
            
            embed = discord.Embed(
                title="💎 **CONVERSÃO REAIS → ROBUX** 💎",
                color=0x5865F2,
                timestamp=datetime.now(GMT_MINUS_3)
            )
            
            embed.description = f"✨ **Transformando seu dinheiro em Robux!** ✨\n\n🏆 **Seu Tier:** {tier} ({'Sem desconto' if discount == 0 else f'{discount*100:.0f}% de desconto'})"
            embed.add_field(
                name="💵 **SEU INVESTIMENTO**",
                value=f"```💰 R$ {valor_reais:,.2f}```",
                inline=False
            )
            embed.add_field(
                name="🎁 **ROBUX" + (" COM SEU DESCONTO**" if discount > 0 else "**"),
                value=f"```💎 {robux_with_discount:,} Robux```",
                inline=False
            )
            if discount > 0:
                embed.add_field(
                    name="💸 **ROBUX SEM DESCONTO**",
                    value=f"```💎 {robux_without_discount:,} Robux```",
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
                value=f"```💎 {robux_with_discount:,} Robux```",
                inline=True
            )
            if discount > 0:
                embed.add_field(name="\u200b", value="━━━━━━━━━━━━━━━━━━━━", inline=False)
                embed.add_field(
                    name="💸 **COM DESCONTO APLICADO**",
                    value=f"Taxa efetiva: R$ {effective_rate:.3f} por Robux\n**Você economiza:** R$ {(robux_without_discount - robux_with_discount) * ROBUX_RATE:,.2f}",
                    inline=False
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


class PaymentConfirmationModal(discord.ui.Modal, title="💰 Confirmar Valor Pago"):
    valor_pago = discord.ui.TextInput(
        label="💵 Valor pago pelo cliente (em Reais)",
        placeholder="Ex: 35.00, 50, 100.50",
        required=True,
        max_length=10
    )

    def __init__(self, uid, ticket, data, interaction, button, view):
        super().__init__()
        self.uid = uid
        self.ticket = ticket
        self.data = data
        self.original_interaction = interaction
        self.button = button
        self.view = view

    async def on_submit(self, interaction: discord.Interaction):
        try:
            valor_pago = float(self.valor_pago.value.replace(',', '.'))
            
            if valor_pago <= 0:
                await interaction.response.send_message(
                    "❌ **Valor inválido!** O valor deve ser maior que zero.",
                    ephemeral=True
                )
                return
            
            # Agora fazer a confirmação
            self.ticket["status"] = "confirmado"
            self.ticket["valor_pago"] = valor_pago
            self.ticket["confirmado_por"] = interaction.user.id
            self.ticket["confirmado_por_nome"] = interaction.user.name
            self.ticket["confirmado_em"] = datetime.now(GMT_MINUS_3).isoformat()
            self.data["usuarios"][self.uid]["ticket_aberto"] = False
            save_json(TICKETS_FILE, self.data)

            # Decrementar uses do código de desconto se foi usado
            if "discount_code" in self.ticket:
                decrement_discount_uses(self.ticket["discount_code"])

            compras = load_json(PURCHASE_COUNT_FILE, {})
            user_compras = compras.get(self.uid, {"count": 0, "total": 0.0})
            user_compras["count"] += 1
            user_compras["total"] += valor_pago
            compras[self.uid] = user_compras
            save_json(PURCHASE_COUNT_FILE, compras)

            cliente = interaction.guild.get_member(int(self.uid))
            
            # Adicionar cargo ao cliente
            cargo_adicionado = False
            if cliente:
                cargo_adicionado = await self.view.adicionar_cargo_cliente(interaction, cliente)
                
            try:
                embed_dm = discord.Embed(
                    title="🎉 **PAGAMENTO CONFIRMADO!** 🎉",
                    description=f"""
                    **✅ ÓTIMA NOTÍCIA! Seu pagamento foi confirmado com sucesso!**
                    
                    **📋 DETALHES DA TRANSAÇÃO:**
                    • **Status:** ✅ **APROVADO**
                    • **Valor Pago:** R$ {valor_pago:,.2f}
                    • **Confirmado por:** {interaction.user.mention}
                    • **Horário:** {datetime.now().strftime('%d/%m/%Y às %H:%M')}
                    • **Ticket:** #{interaction.channel.id}
                    
                    **📦 DETALHES DA COMPRA:**
                    """,
                    color=discord.Color.green()
                )
                
                # Adicionar informações específicas da compra
                if self.ticket["tipo"] == "robux":
                    quantidade = self.ticket.get("quantidade", "N/A")
                    robux_info = f"**Quantidade:** {quantidade}"
                    if "discount_code" in self.ticket:
                        robux_info += f"\n**Código:** `{self.ticket['discount_code']}` ({self.ticket.get('discount_percentage', 0)}% off)"
                    embed_dm.add_field(
                        name="**Tipo:** Robux 💎",
                        value=robux_info,
                        inline=True
                    )
                elif self.ticket["tipo"] == "gamepass":
                    gamepass_nome = self.ticket.get("gamepass", "N/A")
                    gamepass_info = f"**Nome:** {gamepass_nome}"
                    if "discount_code" in self.ticket:
                        gamepass_info += f"\n**Código:** `{self.ticket['discount_code']}` ({self.ticket.get('discount_percentage', 0)}% off)"
                    embed_dm.add_field(
                        name="**Tipo:** Gamepass 🎮",
                        value=gamepass_info,
                        inline=True
                    )
                
                embed_dm.add_field(
                    name="**🏆 Seu Tier Atual:**",
                    value=f"**{get_user_tier(int(self.uid))[0]}**",
                    inline=True
                )
                
                embed_dm.set_footer(text="Obrigado por comprar conosco! Volte sempre! ✨")
                
                await cliente.send(embed=embed_dm)
            except discord.Forbidden:
                pass  # Cliente não permite DM
            
            # Log no canal de logs
            log_channel = discord.utils.get(interaction.guild.channels, name="logs")
            if log_channel:
                user_compras = compras.get(self.uid, {"count": 0, "total": 0.0})
                log = discord.Embed(
                    title="📋 **LOG: PAGAMENTO CONFIRMADO**",
                    description="Um pagamento foi confirmado com sucesso! ✅",
                    color=discord.Color.green(),
                    timestamp=datetime.now(GMT_MINUS_3)
                )
                
                log.add_field(name="👤 Cliente", value=cliente.mention if cliente else f"`{self.uid}`", inline=True)
                log.add_field(name="💰 Valor Pago", value=f"R$ {valor_pago:,.2f}", inline=True)
                log.add_field(name="✅ Confirmado por", value=interaction.user.mention, inline=True)
                log.add_field(name="📊 Total de compras", value=f"`{user_compras['count']}` compras (R$ {user_compras['total']:,.2f})", inline=True)
                log.add_field(name="🏆 Tier Atual", value=f"`{get_user_tier(int(self.uid))[0]}`", inline=True)
                log.add_field(name="🎫 Ticket", value=f"#{interaction.channel.id}", inline=True)
                
                await log_channel.send(embed=log)
            
            # Embed de confirmação no ticket
            embed_confirma = discord.Embed(
                title="✅ **PAGAMENTO CONFIRMADO COM SUCESSO!**",
                description=f"""
                **🎉 PARABÉNS!** O pagamento foi confirmado e a transação está **APROVADA**!
                
                **💰 Valor Pago:** R$ {valor_pago:,.2f}
                **👤 Cliente:** {cliente.mention if cliente else f'`{self.uid}`'}
                **✅ Confirmado por:** {interaction.user.mention}
                **⏰ Horário:** {datetime.now().strftime('%d/%m/%Y às %H:%M')}
                """,
                color=discord.Color.green()
            )
            
            embed_confirma.set_footer(text="🎉 Pagamento confirmado! O ticket permanecerá aberto para acompanhamento.")
            
            await interaction.response.send_message(embed=embed_confirma)
            
            # Botões permanecem ativos para controle adicional
            
        except ValueError:
            await interaction.response.send_message(
                "❌ **Valor inválido!** Digite um número válido (ex: 35.00, 50, 100.50)",
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

    async def adicionar_cargo_cliente(self, interaction: discord.Interaction, cliente):
        """Adiciona o cargo de cliente ao usuário."""
        try:
            # Obter o objeto do cargo
            cliente_role = interaction.guild.get_role(CLIENT_ROLE_ID)
            if not cliente_role:
                print(f"❌ Cargo com ID {CLIENT_ROLE_ID} não encontrado!")
                return False
            
            # Verificar se o cliente já tem o cargo
            if cliente_role in cliente.roles:
                print(f"✅ Cliente {cliente.name} já possui o cargo {cliente_role.name}")
                return True
            
            # Adicionar o cargo
            await cliente.add_roles(cliente_role)
            print(f"✅ Cargo {cliente_role.name} adicionado para {cliente.name}")
            return True
            
        except Exception as e:
            print(f"❌ Erro ao adicionar cargo para {cliente.name}: {str(e)}")
            return False

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

        modal = PaymentConfirmationModal(uid, ticket, data, interaction, button, self)
        await interaction.response.send_modal(modal)

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
            timestamp=datetime.now(GMT_MINUS_3)
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
        ticket["fechado_em"] = datetime.now(GMT_MINUS_3).isoformat()
        ticket["fechado_por"] = interaction.user.id
        data["usuarios"][uid]["ticket_aberto"] = False
        save_json(TICKETS_FILE, data)

        log = discord.Embed(
            title="📋 **LOG: COMPRA CANCELADA**",
            description="Uma compra foi cancelada pelo cliente. ❌",
            color=discord.Color.red(),
            timestamp=datetime.now(GMT_MINUS_3)
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
        ticket["fechado_em"] = datetime.now(GMT_MINUS_3).isoformat()
        ticket["fechado_por"] = interaction.user.id
        ticket["fechado_por_nome"] = interaction.user.name
        data["usuarios"][uid]["ticket_aberto"] = False
        save_json(TICKETS_FILE, data)

        log = discord.Embed(
            title="📋 **LOG: TICKET FECHADO**",
            description="Um ticket foi fechado pela equipe. 🔒",
            color=discord.Color.blurple(),
            timestamp=datetime.now(GMT_MINUS_3)
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
        log.add_field(name="⏰ Duração", value=f"`{(datetime.now(GMT_MINUS_3) - datetime.fromisoformat(ticket['criado_em']).replace(tzinfo=GMT_MINUS_3)).seconds//60} minutos`", inline=True)
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
# SISTEMA DE GIVEAWAYS
# ======================

class GiveawayModal(discord.ui.Modal, title="🎉 Criar Giveaway"):
    giveaway_name = discord.ui.TextInput(
        label="Nome do Giveaway",
        placeholder="Ex: 1000 Robux Grátis",
        required=True,
        max_length=100
    )
    
    end_time = discord.ui.TextInput(
        label="Tempo de Duração",
        placeholder="Ex: 1h, 30m, 2d (h=hora, m=minuto, d=dia)",
        required=True,
        max_length=20
    )
    
    prize = discord.ui.TextInput(
        label="Prêmio",
        placeholder="Ex: 1000 Robux",
        required=True,
        max_length=200
    )
    
    enable_role_bonuses = discord.ui.TextInput(
        label="Bônus por Cargos (sim/não)",
        placeholder="sim (padrão) ou não",
        required=False,
        max_length=3,
        default="sim"
    )
    
    enable_invite_bonuses = discord.ui.TextInput(
        label="Bônus por Convites (sim/não)",
        placeholder="sim (padrão) ou não",
        required=False,
        max_length=3,
        default="sim"
    )

    def __init__(self, interaction):
        super().__init__()
        self.interaction = interaction

    async def on_submit(self, interaction: discord.Interaction):
        # Validar tempo
        time_str = self.end_time.value.lower().strip()
        total_seconds = 0
        
        try:
            if time_str.endswith('d'):
                days = int(time_str[:-1])
                total_seconds = days * 24 * 60 * 60
            elif time_str.endswith('h'):
                hours = int(time_str[:-1])
                total_seconds = hours * 60 * 60
            elif time_str.endswith('m'):
                minutes = int(time_str[:-1])
                total_seconds = minutes * 60
            else:
                await interaction.response.send_message(
                    "❌ **Formato de tempo inválido!**\nUse: `1h` (1 hora), `30m` (30 minutos), `2d` (2 dias)",
                    ephemeral=True
                )
                return
            
            if total_seconds < 60:  # Mínimo 1 minuto
                await interaction.response.send_message(
                    "❌ **Duração muito curta!**\nO giveaway deve durar pelo menos 1 minuto.",
                    ephemeral=True
                )
                return
                
            if total_seconds > 30 * 24 * 60 * 60:  # Máximo 30 dias
                await interaction.response.send_message(
                    "❌ **Duração muito longa!**\nO giveaway não pode durar mais de 30 dias.",
                    ephemeral=True
                )
                return
        
        except ValueError:
            await interaction.response.send_message(
                "❌ **Formato de tempo inválido!**\nUse: `1h` (1 hora), `30m` (30 minutos), `2d` (2 dias)",
                ephemeral=True
            )
            return

        # Validar opções de bônus
        enable_roles = self.enable_role_bonuses.value.lower().strip() in ['sim', 's', 'yes', 'y', 'on', '1', 'true']
        enable_invites = self.enable_invite_bonuses.value.lower().strip() in ['sim', 's', 'yes', 'y', 'on', '1', 'true']
        
        if not self.enable_role_bonuses.value.strip():
            enable_roles = True  # Default to enabled
        if not self.enable_invite_bonuses.value.strip():
            enable_invites = True  # Default to enabled

        # Calcular horário de fim
        end_datetime = datetime.now(GMT_MINUS_3) + timedelta(seconds=total_seconds)
        
        # Criar embed do giveaway
        embed = discord.Embed(
            title=f"🎉 **{self.giveaway_name.value}** 🎉",
            description="",
            color=0xFFD700,
            timestamp=datetime.now(GMT_MINUS_3)
        )
        
        embed.add_field(
            name="🏆 **Prêmio**",
            value=self.prize.value,
            inline=False
        )
        
        embed.add_field(
            name="⏰ **Termina em**",
            value=f"<t:{int(end_datetime.timestamp())}:R>",
            inline=True
        )
        
        embed.add_field(
            name="👥 **Participantes**",
            value="`0`",
            inline=True
        )
        
        # Only show entries information if at least one bonus type is enabled
        if enable_roles or enable_invites:
            embed.add_field(
                name="🎯 **Total Entries**",
                value="`0`",
                inline=True
            )
            
            # Construir descrição do sistema de entries dinamicamente
            entries_description = "• **Base:** 1 entry"
            
            if enable_roles:
                entries_description += "\n• **Clientes:** +1 entries\n• **Booster:** +1 entries"
            
            if enable_invites:
                entries_description += "\n• **Convites:** +1 por convite válido"
            
            embed.add_field(
                name="🎯 **Sistema de Entries**",
                value=entries_description,
                inline=False
            )
            
            # Construir explicação detalhada do sistema de entries
            explanation_parts = []
            
            # Explain what entries are
            explanation_parts.append("🎯 **O que são Entries?** Cada entry representa uma chance! Quanto mais entries você tiver, maiores são suas chances de ganhar!")
            
            # Always explain base entries
            explanation_parts.append("⭐ **Entry Básica:** Todo participante recebe automaticamente 1 entry ao clicar no botão de participação!")

            # Always explain updates
            explanation_parts.append("🔄 **Sistema Automático:** Suas entries são recalculadas automaticamente a cada 1 hora para refletir convites e mudanças de cargo. Ou você pode clicar no botão de novo para atualizar manualmente!")
            
            embed.add_field(
                name="📖 **Como Aumentar suas Chances**",
                value="\n\n".join(explanation_parts),
                inline=False
            )
        else:
            # If no bonuses are enabled, just show a simple message
            embed.add_field(
                name="🎯 **Como Participar**",
                value="Clique no botão abaixo para participar!",
                inline=False
            )
        
        embed.set_footer(text="Boa sorte! 🍀")
        
        # Criar botão de participação
        view = GiveawayView(self.giveaway_name.value, end_datetime.isoformat(), self.prize.value)
        
        # Enviar mensagem
        message = await interaction.channel.send(embed=embed, view=view)
        
        # Salvar dados do giveaway
        giveaway_data = {
            "message_id": message.id,
            "channel_id": interaction.channel.id,
            "name": self.giveaway_name.value,
            "prize": self.prize.value,
            "end_time": end_datetime.isoformat(),
            "created_at": datetime.now(GMT_MINUS_3).isoformat(),
            "created_by": interaction.user.id,
            "participants": {},
            "invite_tracking": {},  # Track invites per user
            "settings": {
                "enable_role_bonuses": enable_roles,
                "enable_invite_bonuses": enable_invites
            },
            "active": True
        }
        
        data = load_json(GIVEAWAYS_FILE, {"giveaways": {}})
        data["giveaways"][str(message.id)] = giveaway_data
        save_json(GIVEAWAYS_FILE, data)
        
        await interaction.response.send_message(
            f"✅ **Giveaway criado com sucesso!**\nNome: {self.giveaway_name.value}\nPrêmio: {self.prize.value}\nDuração: {time_str}\n\n🎯 **Bônus Ativados:**\n• Cargos: {'✅' if enable_roles else '❌'}\n• Convites: {'✅' if enable_invites else '❌'}",
            ephemeral=True
        )


class GiveawayView(discord.ui.View):
    def __init__(self, name, end_time, prize):
        super().__init__(timeout=None)
        self.giveaway_name = name
        self.end_time = end_time
        self.prize = prize

    @discord.ui.button(
        label="Participar 🎉",
        style=discord.ButtonStyle.primary,
        emoji="🎯",
        custom_id="join_giveaway"
    )
    async def join_giveaway(self, interaction: discord.Interaction, button: discord.ui.Button):
        # This will be handled by the global on_interaction event
        pass


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
@app_commands.describe(
    valor="Valor em Robux ou Reais (ex: 1000 para robux ou 35,00 para reais)",
    tier="Tier para preview (opcional: Base, Bronze, Ouro, Platina, Diamante, Elite)"
)
async def calcular(ctx, valor: str, tier: str = None):
    """Calcula o valor da gamepass necessário para obter X robux líquidos."""
    try:
        # Verificar tier do usuário ou usar o especificado
        if tier:
            tier_info = get_tier_by_name(tier)
            if not tier_info:
                await ctx.send(f"❌ **Tier inválido!** Tiers disponíveis: {', '.join([t['name'] for t in TIERS])}")
                return
            tier_name, discount = tier_info["name"], tier_info["discount"]
            is_preview = True
        else:
            tier_name, discount = get_user_tier(ctx.author.id)
            is_preview = False
        
        valor_clean = valor.replace('.', '').replace(',', '.')
        
        if '.' in valor_clean:
            valor_reais = float(valor_clean)
            effective_rate = ROBUX_RATE * (1 - discount)
            robux_liquidos = round(valor_reais / effective_rate)
            valor_gamepass = calcular_valor_gamepass(robux_liquidos)
            taxa_roblox = valor_gamepass - robux_liquidos
            percentual_taxa = (taxa_roblox / valor_gamepass) * 100
            
            embed = discord.Embed(
                title="**CALCULADORA DE ROBUX**",
                description=f"✨ **Cálculo para R$ {valor_reais:,.2f}** ✨\n\n🏆 **Tier:** {tier_name} ({'Sem desconto' if discount == 0 else f'{discount*100:.0f}% de desconto'}){' (Preview)' if is_preview else ''}",
                color=0x5865F2,
                timestamp=datetime.now(GMT_MINUS_3)
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
            valor_reais_desconto = valor_reais * (1 - discount)
            valor_gamepass = calcular_valor_gamepass(robux_liquidos)
            taxa_roblox = valor_gamepass - robux_liquidos
            percentual_taxa = (taxa_roblox / valor_gamepass) * 100
            
            embed = discord.Embed(
                title="CALCULADORA DE ROBUX",
                description=f"✨ **Cálculo para {robux_liquidos:,} Robux** ✨\n\n🏆 **Tier:** {tier_name} ({'Sem desconto' if discount == 0 else f'{discount*100:.0f}% de desconto'}){' (Preview)' if is_preview else ''}",
                color=0x00ff00,
                timestamp=datetime.now(GMT_MINUS_3)
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
            if discount > 0:
                embed.add_field(
                    name="💸 **COM DESCONTO**",
                    value=f"```💰 R$ {valor_reais_desconto:,.2f}```",
                    inline=True
                )
            embed.add_field(
                name="🎮 **VALOR DA GAMEPASS**",
                value=f"```🎮 {valor_gamepass:,} Robux```",
                inline=True
            )
        
        embed.set_footer(
            text=f"✨ Calculado {'(Preview)' if is_preview else ''} para {ctx.author.name} • ⚡ Use /comprar para abrir um ticket!",
            icon_url=ctx.author.avatar.url if ctx.author.avatar else None
        )
        
        await ctx.send(embed=embed)
        
    except ValueError:
        embed_erro = discord.Embed(
            title="❌ **VALOR INVÁLIDO!**",
            description=f"""
            **📝 FORMATOS ACEITOS:**
            • `/calcular 1000` → Calcula quanto custa 1000 Robux
            • `/calcular 35,00` → Calcula quantos Robux você compra com R$ 35
            • `/calcular 1000 Elite` → Preview do preço para tier Elite
            
            **🏆 TIERS DISPONÍVEIS:** {', '.join([t['name'] for t in TIERS])}
            
            **💡 DICA:**
            Use `/calculadora` para uma experiência mais fácil com botões!
            """,
            color=discord.Color.red()
        )
        await ctx.send(embed=embed_erro)


@bot.hybrid_command(name="compras", description="Mostra o histórico de compras")
@app_commands.describe(usuario="Usuário para verificar histórico (opcional)")
async def compras(ctx, usuario: discord.Member = None):
    """Mostra o histórico de compras de um usuário."""
    with open("compras.json", "r", encoding="utf-8") as f:
        dados = json.load(f)

    if not usuario:
        usuario = ctx.author

    if usuario != ctx.author:
        if STAFF_ROLE_ID not in [r.id for r in ctx.author.roles]:
            await ctx.send("❌ **Acesso negado!** Você só pode ver seu próprio histórico de compras.")
            return

    user_data = dados.get(str(usuario.id), {"count": 0, "total": 0.0})
    total = user_data["count"]
    total_spent = user_data["total"]
    
    embed = discord.Embed(
        title=f"📊 **HISTÓRICO DE COMPRAS**",
        description=f"**👤 CLIENTE:** {usuario.mention}",
        color=discord.Color.blue()
    )
    
    tier_info = get_tier_by_spent(total_spent)
    
    embed.add_field(
        name="🎯 **ESTATÍSTICAS**",
        value=f"""
        **🛍️ Total de Compras:** `{total}`
        **💰 Total Gasto:** `R$ {total_spent:,.2f}`
        **⭐ Nível do Cliente:** `{tier_info['name']}`
        **💸 Desconto:** `{tier_info['discount']*100:.0f}%`
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

@bot.hybrid_command(name="loja", description="Mostra estatísticas gerais da loja")
@commands.has_permissions(administrator=True)
async def loja(ctx):
    """Mostra estatísticas gerais da loja."""
    with open("compras.json", "r", encoding="utf-8") as f:
        dados = json.load(f)

    if not dados:
        embed = discord.Embed(
            title="📭 **SEM HISTÓRICO**",
            description="Nenhuma compra registrada ainda! O primeiro cliente está por vir! 🎉",
            color=discord.Color.orange()
        )
        await ctx.send(embed=embed)
        return

    embed = discord.Embed(
        title="🏪 **ESTATÍSTICAS DA LOJA**",
        description="Aqui estão todas as estatísticas da nossa loja! 📈",
        color=discord.Color.blue()
    )
    
    dados_ordenados = sorted(dados.items(), key=lambda x: x[1]["total"] if isinstance(x[1], dict) else 0, reverse=True)
    
    total_compras = sum(d["count"] if isinstance(d, dict) else d for d in dados.values())
    total_faturamento = sum(d["total"] if isinstance(d, dict) else 0 for d in dados.values())
    clientes_unicos = len(dados)
    
    # Calcular médias
    avg_order_value = total_faturamento / total_compras if total_compras > 0 else 0
    avg_customer_value = total_faturamento / clientes_unicos if clientes_unicos > 0 else 0
    
    # Distribuição de tiers
    tier_counts = {}
    tier_revenue = {}
    for uid, user_data in dados.items():
        if isinstance(user_data, dict):
            spent = user_data["total"]
        else:
            spent = 0.0
        tier = get_tier_by_spent(spent)["name"]
        tier_counts[tier] = tier_counts.get(tier, 0) + 1
        tier_revenue[tier] = tier_revenue.get(tier, 0) + spent
    
    tier_distribution = "\n".join([f"• **{tier}:** {count} clientes (R$ {tier_revenue[tier]:,.2f})" for tier, count in sorted(tier_counts.items(), key=lambda x: x[1], reverse=True)])
    
    embed.add_field(
        name="📈 **ESTATÍSTICAS GERAIS**",
        value=f"""
        **🛍️ Total de Compras:** `{total_compras}`
        **💰 Faturamento Total:** `R$ {total_faturamento:,.2f}`
        **👥 Clientes Únicos:** `{clientes_unicos}`
        **📊 Ticket Médio:** `R$ {avg_order_value:,.2f}`
        **💎 Valor Médio por Cliente:** `R$ {avg_customer_value:,.2f}`
        """,
        inline=False
    )
    
    embed.add_field(
        name="🏆 **DISTRIBUIÇÃO DE TIERS**",
        value=tier_distribution if tier_distribution else "Nenhum cliente ainda!",
        inline=True
    )
    
    top_clientes = []
    for i, (uid, user_data) in enumerate(dados_ordenados[:5], 1):
        if isinstance(user_data, dict):
            count = user_data["count"]
            spent = user_data["total"]
        else:
            count = user_data
            spent = 0.0  # for old data
        
        membro = ctx.guild.get_member(int(uid))
        nome = membro.mention if membro else f"`Usuário {uid[:8]}...`"
        
        tier_info = get_tier_by_spent(spent)
        percentage = (spent / total_faturamento * 100) if total_faturamento > 0 else 0
        medalha = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"**{i}.**"
        top_clientes.append(f"{medalha} {nome} → R$ {spent:,.2f} ({percentage:.1f}%) (**{tier_info['name']}**)")

    embed.add_field(
        name="💎 **TOP REVENUE CONTRIBUTORS**",
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
        
        **🏆 SISTEMA DE TIERS**
        """ + "\n".join([f"• **{tier['name']} (R$ {tier['min_spent']:,.0f}+ gastos):** {tier['discount']*100:.0f}% de desconto" for tier in TIERS]) + """
        
        **💰 ROBUX → REAIS**
        • Descubra quanto custa X Robux em Reais
        • Veja o valor exato da gamepass necessária
        
        **💸 REAIS → ROBUX**
        • Veja quantos Robux você compra com X Reais
        • Veja o valor exato da gamepass necessária
        """,
        color=discord.Color.gold()
    )
    
    embed.set_footer(text="Também use `/calcular [valor] [tier]` - Ex: `/calcular 1000` ou `/calcular 35,00 Elite`")
    embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/1128316432609128488.gif")

    await interaction.response.send_message(embed=embed, view=CalculatorView(), ephemeral=True)


@bot.tree.command(name="tiers", description="Mostra todos os tiers disponíveis e seus benefícios")
async def tiers(interaction: discord.Interaction):
    """Slash command para mostrar os tiers."""
    embed = discord.Embed(
        title="🏆 **SISTEMA DE TIERS**",
        description="Veja todos os tiers disponíveis e seus benefícios!",
        color=discord.Color.gold()
    )
    
    tier_list = []
    for tier in TIERS:
        tier_list.append(f"**{tier['name']}** (R$ {tier['min_spent']:,.0f}+ gastos) → {tier['discount']*100:.0f}% desconto")
    
    embed.add_field(
        name="📊 **TIERS DISPONÍVEIS**",
        value="\n".join(tier_list),
        inline=False
    )
    
    embed.add_field(
        name="💡 **COMO FUNCIONA?**",
        value="""
        • Gasto total determina seu tier
        • Descontos são aplicados automaticamente
        • Use `/calcular [valor] [tier]` para preview
        """,
        inline=False
    )
    
    embed.set_footer(text="Quanto mais você gasta, mais desconto você ganha! ✨")
    embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/1128316432067063838.gif")

    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="paineltiers", description="Define o painel de tiers em um canal específico")
@app_commands.describe(channel="Canal onde o painel de tiers será enviado")
async def set_tier_panel(interaction: discord.Interaction, channel: discord.TextChannel):
    """Slash command para definir o painel de tiers em um canal."""
    # Verificar permissões (apenas administradores ou gerenciar servidor)
    if not interaction.user.guild_permissions.manage_guild:
        await interaction.response.send_message("❌ Você não tem permissão para usar este comando. (Requer Gerenciar Servidor)", ephemeral=True)
        return
    
    embed = discord.Embed(
        title="🏆 **SISTEMA DE TIERS**",
        description="Veja todos os tiers disponíveis e seus benefícios!",
        color=discord.Color.gold()
    )
    
    tier_list = []
    for tier in TIERS:
        tier_list.append(f"**{tier['name']}** (R$ {tier['min_spent']:,.0f}+ gastos) → {tier['discount']*100:.0f}% desconto")
    
    embed.add_field(
        name="📊 **TIERS DISPONÍVEIS**",
        value="\n".join(tier_list),
        inline=False
    )
    
    embed.add_field(
        name="💡 **COMO FUNCIONA?**",
        value="""
        • Gasto total determina seu tier
        • Descontos são aplicados automaticamente
        • Use `/calcular [valor] [tier]` para preview
        """,
        inline=False
    )
    
    embed.set_footer(text="Quanto mais você gasta, mais desconto você ganha! ✨")
    embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/1128316432067063838.gif")
    
    try:
        await channel.send(embed=embed)
        await interaction.response.send_message(f"✅ Painel de tiers enviado com sucesso no canal {channel.mention}!", ephemeral=True)
    except discord.Forbidden:
        await interaction.response.send_message("❌ Não tenho permissão para enviar mensagens nesse canal.", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"❌ Erro ao enviar o painel: {str(e)}", ephemeral=True)

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


@bot.tree.command(name="giveaway", description="Cria um novo giveaway")
@app_commands.describe(channel="Canal onde o giveaway será criado (opcional)")
async def create_giveaway(interaction: discord.Interaction, channel: discord.TextChannel = None):
    """Slash command para criar um giveaway."""
    # Verificar permissões (apenas administradores ou gerenciar servidor)
    if not interaction.user.guild_permissions.manage_guild:
        await interaction.response.send_message(
            "❌ **Acesso restrito!**\nApenas administradores podem criar giveaways.",
            ephemeral=True
        )
        return
    
    # Usar canal atual se nenhum foi especificado
    target_channel = channel or interaction.channel
    
    # Verificar se bot tem permissões no canal
    if not target_channel.permissions_for(interaction.guild.me).send_messages:
        await interaction.response.send_message(
            "❌ **Sem permissão!**\nNão tenho permissão para enviar mensagens no canal especificado.",
            ephemeral=True
        )
        return
    
    # Abrir modal
    modal = GiveawayModal(interaction)
    await interaction.response.send_modal(modal)


@bot.hybrid_command(name="claimgiveaway", description="Marca um giveaway como resgatado (staff apenas)")
@app_commands.describe(message_id="ID da mensagem do giveaway")
async def claim_giveaway(ctx, message_id: str):
    """Marca um giveaway como resgatado por um membro da staff."""
    # Verificar permissões (apenas staff)
    if STAFF_ROLE_ID not in [r.id for r in ctx.author.roles]:
        await ctx.send("❌ **Acesso restrito!**\nApenas membros da equipe podem usar este comando.", ephemeral=True)
        return
    
    try:
        # Carregar dados dos giveaways
        data = load_json(GIVEAWAYS_FILE, {"giveaways": {}})
        
        if message_id not in data["giveaways"]:
            await ctx.send("❌ **Giveaway não encontrado!**\nVerifique o ID da mensagem.", ephemeral=True)
            return
        
        giveaway = data["giveaways"][message_id]
        
        if giveaway.get("active", True):
            await ctx.send("❌ **Este giveaway ainda está ativo!**\nAguarde o fim do giveaway para marcar como resgatado.", ephemeral=True)
            return
        
        if giveaway.get("claimed", False):
            await ctx.send("⚠️ **Este giveaway já foi marcado como resgatado!**", ephemeral=True)
            return
        
        # Marcar como resgatado
        giveaway["claimed"] = True
        giveaway["claimed_at"] = datetime.now(GMT_MINUS_3).isoformat()
        giveaway["claimed_by"] = ctx.author.id
        save_json(GIVEAWAYS_FILE, data)
        
        # Tentar atualizar embed
        try:
            channel = bot.get_channel(giveaway["channel_id"])
            if channel:
                message = await channel.fetch_message(int(message_id))
                if message:
                    embed = message.embeds[0]
                    
                    # Adicionar campo de resgatado
                    embed.add_field(
                        name="✅ **PRÊMIO resgatado**",
                        value=f"resgatado por {ctx.author.mention}",
                        inline=False
                    )
                    
                    await message.edit(embed=embed)
        except Exception as e:
            print(f"Erro ao atualizar embed do giveaway resgatado: {str(e)}")
        
        await ctx.send(f"✅ **Giveaway marcado como resgatado!**\nPrêmio: {giveaway['prize']}\nVencedor: <@{giveaway['winner']}>", ephemeral=True)
        
    except Exception as e:
        await ctx.send(f"❌ **Erro ao processar comando:** {str(e)}", ephemeral=True)


@bot.hybrid_command(name="sync", description="Sincroniza os comandos slash (apenas dono)")
@commands.is_owner()
async def sync(ctx):
    """Sincroniza os comandos slash com o Discord."""
    # Defer the response to avoid timeout for slash commands
    if hasattr(ctx, 'interaction') and ctx.interaction:
        await ctx.interaction.response.defer(ephemeral=True)
    
    await bot.tree.sync()
    
    # Handle both slash and prefix commands
    if hasattr(ctx, 'interaction') and ctx.interaction:
        # Slash command - use followup
        await ctx.interaction.followup.send("✅ Comandos slash sincronizados com sucesso!", ephemeral=True)
    else:
        # Prefix command
        await ctx.send("✅ Comandos slash sincronizados com sucesso!")


# ======================
# SISTEMA DE VERIFICAÇÃO DE GIVEAWAYS
# ======================

async def check_expired_giveaways():
    """Verifica giveaways expirados a cada 60 segundos e finaliza-os."""
    await bot.wait_until_ready()
    
    while not bot.is_closed():
        try:
            # Carregar dados dos giveaways
            data = load_json(GIVEAWAYS_FILE, {"giveaways": {}})
            current_time = datetime.now(GMT_MINUS_3)
            
            for giveaway_id, giveaway in data["giveaways"].items():
                if giveaway.get("active", True):
                    # Verificar se o giveaway expirou
                    end_time = datetime.fromisoformat(giveaway["end_time"]).replace(tzinfo=GMT_MINUS_3)
                    if current_time >= end_time:
                        # Finalizar giveaway
                        await finish_giveaway(giveaway_id, giveaway, data)
                else:
                    # Verificar se o prazo de claim expirou
                    if "claim_deadline" in giveaway and giveaway.get("status") == "finished":
                        claim_deadline = datetime.fromisoformat(giveaway["claim_deadline"]).replace(tzinfo=GMT_MINUS_3)
                        if current_time >= claim_deadline and not giveaway.get("claimed", False):
                            # Reroll automático
                            await reroll_giveaway(giveaway_id, giveaway, data)
            
            # Aguardar 60 segundos antes da próxima verificação
            await asyncio.sleep(60)
            
        except Exception as e:
            print(f"❌ Erro na verificação de giveaways: {str(e)}")
            await asyncio.sleep(60)


async def finish_giveaway(giveaway_id, giveaway, data):
    """Finaliza um giveaway selecionando um vencedor."""
    try:
        # Obter participantes
        participants = giveaway["participants"]
        
        if not participants:
            # Nenhum participante - cancelar giveaway
            giveaway["active"] = False
            giveaway["finished_at"] = datetime.now(GMT_MINUS_3).isoformat()
            giveaway["status"] = "cancelled_no_participants"
            save_json(GIVEAWAYS_FILE, data)
            
            # Tentar enviar mensagem de cancelamento
            try:
                channel = bot.get_channel(giveaway["channel_id"])
                if channel:
                    message = await channel.fetch_message(int(giveaway_id))
                    if message:
                        embed = message.embeds[0]
                        embed.color = discord.Color.red()
                        embed.add_field(
                            name="❌ **GIVEAWAY CANCELADO**",
                            value="Nenhum participante se inscreveu neste giveaway.",
                            inline=False
                        )
                        await message.edit(embed=embed, view=None)
            except Exception as e:
                print(f"Erro ao atualizar mensagem cancelada: {str(e)}")
            
            return
        
        # Selecionar vencedor baseado em entries (weighted random)
        winner_id = select_weighted_winner(participants)
        if winner_id is None:
            # Fallback to simple random if something goes wrong
            winner_id = random.choice(list(participants.keys()))
        winner_user = bot.get_user(int(winner_id))
        
        # Marcar giveaway como finalizado
        giveaway["active"] = False
        giveaway["finished_at"] = datetime.now(GMT_MINUS_3).isoformat()
        giveaway["winner"] = winner_id
        giveaway["claim_deadline"] = (datetime.now(GMT_MINUS_3) + timedelta(hours=24)).isoformat()
        giveaway["status"] = "finished"
        giveaway["claimed"] = False
        save_json(GIVEAWAYS_FILE, data)
        
        # Atualizar embed do giveaway
        try:
            channel = bot.get_channel(giveaway["channel_id"])
            if channel:
                message = await channel.fetch_message(int(giveaway_id))
                if message:
                    embed = message.embeds[0]
                    embed.color = discord.Color.green()
                    
                    # Atualizar campos
                    for i, field in enumerate(embed.fields):
                        if field.name == "⏰ **Termina em**":
                            embed.set_field_at(i, name="⏰ **Terminou**", value=f"<t:{int(datetime.fromisoformat(giveaway['finished_at']).timestamp())}:R>", inline=True)
                        elif field.name == "👥 **Participantes**":
                            embed.set_field_at(i, name="👥 **Participantes**", value=f"`{len(participants)}`", inline=True)
                    
                    embed.add_field(
                        name="🏆 **VENCEDOR**",
                        value=f"{winner_user.mention if winner_user else f'<@{winner_id}>'}",
                        inline=False
                    )
                    
                    await message.edit(embed=embed, view=None)
        except Exception as e:
            print(f"Erro ao atualizar embed do giveaway: {str(e)}")
        
        # Enviar mensagem de anúncio do vencedor
        try:
            channel = bot.get_channel(giveaway["channel_id"])
            if channel:
                winner_mention = winner_user.mention if winner_user else f"<@{winner_id}>"
                content_msg=f"**Parabéns {winner_mention}!**"
                embed_winner = discord.Embed(
                    title="🎉 **GIVEAWAY FINALIZADO** 🎉",
                    description=f"**Parabéns {winner_mention}!**",
                    color=0xFFD700,
                    timestamp=datetime.now(GMT_MINUS_3)
                )
                
                embed_winner.add_field(
                    name="🏆 **Prêmio Ganho**",
                    value=giveaway["prize"],
                    inline=False
                )
                
                embed_winner.add_field(
                    name="⏰ **Como Resgatar**",
                    value="""Abra um ticket de suporte nas próximas **24 horas** para receber seu prêmio!
                    
Se não resgatar dentro do prazo, o prêmio será sorteado novamente.""",
                    inline=False
                )
                
                embed_winner.set_footer(text="Boa sorte na próxima! 🍀")
                
                await channel.send(content=content_msg, embed=embed_winner)
                
        except Exception as e:
            print(f"Erro ao enviar anúncio do vencedor: {str(e)}")
            
    except Exception as e:
        print(f"❌ Erro ao finalizar giveaway {giveaway_id}: {str(e)}")


async def reroll_giveaway(giveaway_id, giveaway, data):
    """Faz reroll de um giveaway selecionando um novo vencedor."""
    try:
        # Obter participantes
        participants = giveaway["participants"]
        
        if len(participants) <= 1:
            # Apenas 1 participante ou menos - não há como rerollar
            giveaway["status"] = "cancelled_insufficient_participants"
            save_json(GIVEAWAYS_FILE, data)
            
            # Tentar enviar mensagem de cancelamento
            try:
                channel = bot.get_channel(giveaway["channel_id"])
                if channel:
                    embed_reroll_cancelled = discord.Embed(
                        title="🎉 **GIVEAWAY - REROLL CANCELADO** 🎉",
                        description=f"**{giveaway['name']}**",
                        color=discord.Color.red(),
                        timestamp=datetime.now(GMT_MINUS_3)
                    )
                    
                    embed_reroll_cancelled.add_field(
                        name="🏆 **Prêmio**",
                        value=giveaway["prize"],
                        inline=False
                    )
                    
                    embed_reroll_cancelled.add_field(
                        name="❌ **Motivo**",
                        value="Poucos participantes para reroll automático.",
                        inline=False
                    )
                    
                    embed_reroll_cancelled.set_footer(text="Giveaway finalizado sem vencedor.")
                    
                    await channel.send(embed=embed_reroll_cancelled)
            except Exception as e:
                print(f"Erro ao enviar mensagem de reroll cancelado: {str(e)}")
            
            return
        
        # Remover o vencedor anterior da lista de participantes
        previous_winner = giveaway.get("winner")
        available_participants = {uid: data for uid, data in participants.items() if uid != previous_winner}
        
        # Selecionar novo vencedor baseado em entries (weighted random)
        new_winner_id = select_weighted_winner(available_participants)
        if new_winner_id is None:
            # Fallback to simple random if something goes wrong
            new_winner_id = random.choice(list(available_participants.keys()))
        new_winner_user = bot.get_user(int(new_winner_id))
        
        # Atualizar dados do giveaway
        giveaway["winner"] = new_winner_id
        giveaway["claim_deadline"] = (datetime.now(GMT_MINUS_3) + timedelta(hours=24)).isoformat()
        giveaway["claimed"] = False
        giveaway["reroll_count"] = giveaway.get("reroll_count", 0) + 1
        save_json(GIVEAWAYS_FILE, data)
        
        # Enviar mensagem de reroll
        try:
            channel = bot.get_channel(giveaway["channel_id"])
            if channel:
                new_winner_mention = new_winner_user.mention if new_winner_user else f"<@{new_winner_id}>"
                
                embed_reroll = discord.Embed(
                    title="🔄 **GIVEAWAY - PRÊMIO REROLADO** 🔄",
                    description=f"**{giveaway['name']}**",
                    color=0xFF6B35,
                    timestamp=datetime.now(GMT_MINUS_3)
                )
                
                embed_reroll.add_field(
                    name="🏆 **Prêmio**",
                    value=giveaway["prize"],
                    inline=False
                )
                
                embed_reroll.add_field(
                    name="🎉 **Novo Vencedor**",
                    value=f"{new_winner_mention}",
                    inline=False
                )
                
                embed_reroll.add_field(
                    name="⏰ **Como Resgatar**",
                    value="""Abra um ticket de suporte nas próximas **24 horas** para receber seu prêmio!
                    
Se não resgatar dentro do prazo, o prêmio será sorteado novamente.""",
                    inline=False
                )
                
                embed_reroll.add_field(
                    name="📊 **Rerolls**",
                    value=f"`{giveaway['reroll_count']}`",
                    inline=True
                )
                
                embed_reroll.set_footer(text="Boa sorte na próxima! 🍀")
                
                await channel.send(embed=embed_reroll)
                
        except Exception as e:
            print(f"Erro ao enviar mensagem de reroll: {str(e)}")
            
    except Exception as e:
        print(f"❌ Erro ao fazer reroll do giveaway {giveaway_id}: {str(e)}")


async def auto_update_giveaway_entries():
    """Atualiza automaticamente as entries dos participantes a cada hora, processando lentamente."""
    await bot.wait_until_ready()
    
    while not bot.is_closed():
        try:
            # Aguardar 1 hora
            await asyncio.sleep(3600)  # 1 hour = 3600 seconds
            
            print("🔄 Iniciando auto-update de entries dos giveaways...")
            
            data = load_json(GIVEAWAYS_FILE, {"giveaways": {}})
            updated_count = 0
            
            for giveaway_id, giveaway in data["giveaways"].items():
                if not giveaway.get("active", True):
                    continue  # Skip inactive giveaways
                
                participants = giveaway["participants"]
                if not participants:
                    continue
                
                # Process each participant slowly
                for user_id, participant_data in participants.items():
                    try:
                        # Get member object
                        guild = None
                        member = None
                        
                        # Find the guild and member
                        for g in bot.guilds:
                            try:
                                member = g.get_member(int(user_id))
                                if member:
                                    guild = g
                                    break
                            except:
                                continue
                        
                        if not member:
                            continue  # Skip if member not found
                        
                        # Calculate new entries
                        new_entries = get_giveaway_entries(member, giveaway)
                        old_entries = participant_data["entries"]
                        
                        # Only update if entries changed
                        if new_entries != old_entries:
                            participant_data["entries"] = new_entries
                            participant_data["last_update"] = datetime.now(GMT_MINUS_3).isoformat()
                            updated_count += 1
                            
                            print(f"✅ Updated {member.name}#{member.discriminator}: {old_entries} → {new_entries} entries")
                        
                        # Small delay between each user to avoid rate limits
                        await asyncio.sleep(0.5)  # 500ms delay
                        
                    except Exception as e:
                        print(f"❌ Error updating user {user_id}: {str(e)}")
                        continue
                
                # Save after processing each giveaway
                save_json(GIVEAWAYS_FILE, data)
                
                # Longer delay between giveaways
                await asyncio.sleep(2)  # 2 second delay between giveaways
            
            if updated_count > 0:
                print(f"✅ Auto-update concluído! {updated_count} entries atualizadas.")
            else:
                print("✅ Auto-update concluído! Nenhuma atualização necessária.")
            
        except Exception as e:
            print(f"❌ Erro no auto-update de entries: {str(e)}")
            await asyncio.sleep(3600)  # Wait another hour if error


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
    
    # Iniciar verificação automática de giveaways
    bot.loop.create_task(check_expired_giveaways())
    bot.loop.create_task(auto_update_giveaway_entries())
    print("✅ Sistema de verificação de giveaways iniciado!")
    print("✅ Sistema de auto-update de entries iniciado!")


@bot.event
async def on_interaction(interaction: discord.Interaction):
    """Handle button interactions for giveaways."""
    if interaction.type == discord.InteractionType.component:
        custom_id = interaction.data.get("custom_id")
        if custom_id == "join_giveaway":
            # Handle giveaway join
            data = load_json(GIVEAWAYS_FILE, {"giveaways": {}})
            giveaway_id = str(interaction.message.id)
            
            if giveaway_id not in data["giveaways"]:
                await interaction.response.send_message(
                    "❌ **Giveaway não encontrado!**",
                    ephemeral=True
                )
                return
            
            giveaway = data["giveaways"][giveaway_id]
            
            # Verificar se giveaway ainda está ativo
            if not giveaway.get("active", True):
                await interaction.response.send_message(
                    "❌ **Este giveaway já terminou!**",
                    ephemeral=True
                )
                return
            
            # Calcular entries baseado em roles
            total_entries = get_giveaway_entries(interaction.user, giveaway)
            user_id = str(interaction.user.id)
            current_time = datetime.now(GMT_MINUS_3)
            
            # Verificar se usuário já participa
            if user_id in giveaway["participants"]:
                # Check cooldown (5 minutes)
                last_update = giveaway["participants"][user_id].get("last_update")
                if last_update:
                    last_update_time = datetime.fromisoformat(last_update).replace(tzinfo=GMT_MINUS_3)
                    cooldown_end = last_update_time + timedelta(minutes=5)
                    if current_time < cooldown_end:
                        remaining_time = cooldown_end - current_time
                        minutes_left = int(remaining_time.total_seconds() / 60)
                        seconds_left = int(remaining_time.total_seconds() % 60)
                        await interaction.response.send_message(
                            f"⏰ **Cooldown ativo!**\nVocê pode atualizar suas entries novamente em `{minutes_left}m {seconds_left}s`.",
                            ephemeral=True
                        )
                        return
                
                # Update entries
                old_entries = giveaway["participants"][user_id]["entries"]
                giveaway["participants"][user_id]["entries"] = total_entries
                giveaway["participants"][user_id]["last_update"] = current_time.isoformat()
                
                # Atualizar embed com novo total de entries
                embed = interaction.message.embeds[0]
                total_entries_sum = sum(p["entries"] for p in giveaway["participants"].values())
                
                for i, field in enumerate(embed.fields):
                    if field.name == "🎯 **Total Entries**":
                        embed.set_field_at(i, name="🎯 **Total Entries**", value=f"`{total_entries_sum}`", inline=True)
                        break
                
                await interaction.message.edit(embed=embed)
                save_json(GIVEAWAYS_FILE, data)
                
                await interaction.response.send_message(
                    f"✅ **Entries atualizadas!**\n🎯 **Antes:** {old_entries} entries\n🎯 **Agora:** {total_entries} entries\n🏆 **Prêmio:** {giveaway['prize']}",
                    ephemeral=True
                )
                return
            
            # Adicionar novo participante
            giveaway["participants"][user_id] = {
                "entries": total_entries,
                "joined_at": current_time.isoformat(),
                "last_update": current_time.isoformat()
            }
            
            # Atualizar contador no embed
            embed = interaction.message.embeds[0]
            participant_count = len(giveaway["participants"])
            total_entries = sum(p["entries"] for p in giveaway["participants"].values())
            
            # Encontrar e atualizar campos
            for i, field in enumerate(embed.fields):
                if field.name == "👥 **Participantes**":
                    embed.set_field_at(i, name="👥 **Participantes**", value=f"`{participant_count}`", inline=True)
                elif field.name == "🎯 **Total Entries**":
                    embed.set_field_at(i, name="🎯 **Total Entries**", value=f"`{total_entries}`", inline=True)
            
            await interaction.message.edit(embed=embed)
            save_json(GIVEAWAYS_FILE, data)
            
            await interaction.response.send_message(
                f"✅ **Você entrou no giveaway!**\n🎉 **{giveaway['name']}**\n🎯 **Suas entries:** {total_entries}\n🏆 **Prêmio:** {giveaway['prize']}",
                ephemeral=True
            )


@bot.event
async def on_invite_create(invite: discord.Invite):
    """Track invite creation for giveaway bonus system."""
    if not invite.inviter or invite.inviter.bot:
        return

    inviter_id = str(invite.inviter.id)

    # Load giveaway data
    data = load_json(GIVEAWAYS_FILE, {"giveaways": {}})
    current_time = datetime.now(GMT_MINUS_3)

    # Check active giveaways and track invite
    for giveaway_id, giveaway in data["giveaways"].items():
        if giveaway.get("active", True):
            # Check if invite bonuses are enabled for this giveaway
            enable_invites = giveaway.get("settings", {}).get("enable_invite_bonuses", True)
            if not enable_invites:
                continue
                
            # Initialize invite tracking for user if not exists
            if "invite_tracking" not in giveaway:
                giveaway["invite_tracking"] = {}

            if inviter_id not in giveaway["invite_tracking"]:
                giveaway["invite_tracking"][inviter_id] = {}

            # Track this invite
            giveaway["invite_tracking"][inviter_id][invite.code] = {
                "created_at": current_time.isoformat(),
                "max_uses": invite.max_uses,
                "uses": []
            }

            print(f"📨 Tracked invite {invite.code} by {invite.inviter.name} for giveaway {giveaway['name']}")

    save_json(GIVEAWAYS_FILE, data)


@bot.event
async def on_member_join(member: discord.Member):
    """Track member joins from invites for giveaway bonus system."""
    if member.bot:
        return

    # Try to find which invite was used
    try:
        # Get all invites for the guild
        invites_before = {}  # We can't get invites_before easily, so we'll use invite tracking

        # Load giveaway data
        data = load_json(GIVEAWAYS_FILE, {"giveaways": {}})
        current_time = datetime.now(GMT_MINUS_3)

        # Check active giveaways
        for giveaway_id, giveaway in data["giveaways"].items():
            if giveaway.get("active", True) and "invite_tracking" in giveaway:
                # Check if invite bonuses are enabled for this giveaway
                enable_invites = giveaway.get("settings", {}).get("enable_invite_bonuses", True)
                if not enable_invites:
                    continue
                    
                # Check if any tracked invite was used
                for inviter_id, user_invites in giveaway["invite_tracking"].items():
                    for invite_code, invite_data in user_invites.items():
                        # Check if this invite could have been used (we'll assume recent joins are from tracked invites)
                        invite_created = datetime.fromisoformat(invite_data["created_at"]).replace(tzinfo=GMT_MINUS_3)
                        time_since_invite = current_time - invite_created

                        # If member joined within reasonable time after invite creation
                        if time_since_invite.total_seconds() < 86400:  # 24 hours
                            # Check if this user hasn't been counted for this invite yet
                            already_counted = any(use["user_id"] == str(member.id) for use in invite_data.get("uses", []))

                            if not already_counted:
                                invite_data["uses"].append({
                                    "user_id": str(member.id),
                                    "joined_at": current_time.isoformat()
                                })
                                print(f"👥 Member {member.name} joined from invite {invite_code} by user {inviter_id} for giveaway {giveaway['name']}")

        save_json(GIVEAWAYS_FILE, data)

    except Exception as e:
        print(f"❌ Error tracking member join: {str(e)}")


# ======================
# EXECUÇÃO DO BOT
# ======================

if __name__ == "__main__":
    print("🚀 Iniciando bot...")
    print("🔧 Carregando configurações...")
    print("💾 Verificando arquivos JSON...")
    bot.run(TOKEN)