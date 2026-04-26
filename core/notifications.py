import discord


class NotificationSender:
    """Helper for sending Discord update notifications."""

    @staticmethod
    async def send_update_notification(
        channel: discord.TextChannel,
        title: str,
        url: str,
        image_url: str,
        old_date: str,
        new_date: str,
        description: str,
    ) -> None:
        embed = discord.Embed(
            title=f"📅 Game Update: {title}",
            url=url,
            description=description,
            color=discord.Color.gold(),
        )
        embed.add_field(name="Old Date", value=f"`{old_date}`", inline=True)
        embed.add_field(name="New Date", value=f"`{new_date}`", inline=True)
        if image_url != "N/A":
            embed.set_thumbnail(url=image_url)
        embed.set_footer(text=f"URL: {url}")

        button = discord.ui.Button(
            label="Go to Game",
            url=url,
            style=discord.ButtonStyle.link,
        )
        view = discord.ui.View()
        view.add_item(button)

        await channel.send(embed=embed, view=view)
