import asyncio
import enum

import discord


class ConfirmResult(enum.Enum):
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    CANCELLED_ALL = "cancelled_all"


class ConfirmView(discord.ui.View):
    def __init__(self, invoker_id: int) -> None:
        super().__init__(timeout=120)
        self.invoker_id = invoker_id
        self._future: asyncio.Future[ConfirmResult] = asyncio.get_event_loop().create_future()

    def _is_invoker(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.invoker_id

    async def wait_result(self) -> ConfirmResult:
        """Await until user clicks a button or timeout."""
        await self.wait()
        if self._future.done():
            return self._future.result()
        return ConfirmResult.CANCELLED

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.success, emoji="✅")
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not self._is_invoker(interaction):
            await interaction.response.send_message("Only the admin can use this button.", ephemeral=True)
            return
        await interaction.response.defer()
        self._future.set_result(ConfirmResult.CONFIRMED)
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger, emoji="❌")
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not self._is_invoker(interaction):
            await interaction.response.send_message("Only the admin can use this button.", ephemeral=True)
            return
        await interaction.response.defer()
        self._future.set_result(ConfirmResult.CANCELLED)
        self.stop()

    @discord.ui.button(label="Cancel All", style=discord.ButtonStyle.danger, emoji="🛑")
    async def cancel_all(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not self._is_invoker(interaction):
            await interaction.response.send_message("Only the admin can use this button.", ephemeral=True)
            return
        await interaction.response.defer()
        self._future.set_result(ConfirmResult.CANCELLED_ALL)
        self.stop()
