import os
import sys
import asyncio
import platform
import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

# ================== الإعدادات ==================
# حدد هنا ID السيرفر الذي تختبر فيه (لظهور الأوامر بسرعة)
# اتركه فارغاً (None) للمزامنة العامة (قد تستغرق دقائق)
GUILD_ID = None  # مثال: 123456789012345678

# ===============================================

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
STEAM_USER = os.getenv("STEAM_USERNAME")
STEAM_PASS = os.getenv("STEAM_PASSWORD")

if not TOKEN or not STEAM_USER or not STEAM_PASS:
    raise ValueError("❌ الرجاء التأكد من تعبئة TOKEN و USERNAME و PASSWORD في ملف .env")

APP_ID = "431960"

# تحديد مسار SteamCMD بناءً على نظام التشغيل
# نفترض أن مجلد SteamCMD موجود في نفس مجلد البوت
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

if platform.system() == "Windows":
    STEAMCMD_PATH = os.path.join(BASE_DIR, "SteamCMD", "steamcmd.exe")
else:  # Linux / macOS
    STEAMCMD_PATH = os.path.join(BASE_DIR, "SteamCMD", "steamcmd")
    # منح صلاحية التنفيذ (قد تحتاجها في Linux)
    if os.path.exists(STEAMCMD_PATH):
        os.chmod(STEAMCMD_PATH, 0o755)

# التحقق من وجود الملف
if not os.path.exists(STEAMCMD_PATH):
    print(f"⚠️ تحذير: لم يتم العثور على SteamCMD في المسار: {STEAMCMD_PATH}")
    print("تأكد من رفع مجلد SteamCMD مع البوت على السيرفر.")

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

download_lock = asyncio.Lock()

def get_folder_size_mb(folder_path):
    total_size = 0
    if os.path.exists(folder_path):
        for dirpath, dirnames, filenames in os.walk(folder_path):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                if os.path.exists(fp):
                    total_size += os.path.getsize(fp)
    return round(total_size / (1024 * 1024), 2)

@bot.event
async def on_ready():
    print(f"✅ البوت دخل كـ {bot.user}")
    
    try:
        if GUILD_ID:
            guild = discord.Object(id=GUILD_ID)
            synced = await bot.tree.sync(guild=guild)
            print(f"✅ تم تفعيل {len(synced)} أمر(أمر) سلاش في السيرفر {GUILD_ID}")
        else:
            synced = await bot.tree.sync()
            print(f"✅ تم تفعيل {len(synced)} أمر(أمر) سلاش عام")
    except Exception as e:
        print(f"❌ فشل التزامن: {e}")
    
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name="/download <ID>"
        )
    )

@bot.tree.command(
    name="download",
    description="تحميل ورق حائط من ورشة عمل Steam باستخدام الـ ID"
)
@app_commands.describe(workshop_id="معرف الـ Workshop المكون من أرقام (مثال: 3769527496)")
async def download(interaction: discord.Interaction, workshop_id: str):
    await interaction.response.defer(thinking=True)

    if not workshop_id.isdigit():
        embed = discord.Embed(
            title="❌ خطأ في الإدخال",
            description="يجب أن يحتوي المعرف على أرقام فقط.",
            color=discord.Color.red()
        )
        await interaction.followup.send(embed=embed)
        return

    async with download_lock:
        loading_embed = discord.Embed(
            title="⏳ جاري التحميل...",
            description=f"جاري تحميل الـ Workshop ID: `{workshop_id}`\nيرجى الانتظار...",
            color=discord.Color.blue()
        )
        await interaction.followup.send(embed=loading_embed)
        
        # التأكد من وجود SteamCMD قبل التشغيل
        if not os.path.exists(STEAMCMD_PATH):
            embed = discord.Embed(
                title="❌ SteamCMD غير موجود",
                description=f"لم يتم العثور على البرنامج في المسار: `{STEAMCMD_PATH}`\nتأكد من رفع مجلد SteamCMD مع البوت.",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed)
            return

        cmd = [
            STEAMCMD_PATH,
            "+login", STEAM_USER, STEAM_PASS,
            "+workshop_download_item", APP_ID, workshop_id,
            "+quit"
        ]

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await process.communicate()
            output = stdout.decode('utf-8', errors='ignore')

            if "Success. Downloaded item" in output:
                try:
                    start = output.find("to \"") + 4
                    end = output.find("\"", start)
                    download_path = output[start:end]
                except:
                    download_path = os.path.join(BASE_DIR, "steamapps", "workshop", "content", APP_ID, workshop_id)

                folder_size_mb = get_folder_size_mb(download_path)

                embed = discord.Embed(
                    title="✅ تم التحميل بنجاح!",
                    description=f"[👆 اضغط هنا لفتح صفحة الـ Workshop في المتصفح](https://steamcommunity.com/sharedfiles/filedetails/?id={workshop_id})",
                    color=discord.Color.green()
                )
                embed.add_field(name="🆔 رقم الـ Workshop", value=f"`{workshop_id}`", inline=True)
                embed.add_field(name="📁 مسار التخزين", value=f"`{download_path}`", inline=False)
                
                if folder_size_mb > 0:
                    embed.add_field(name="📦 حجم الملفات", value=f"`{folder_size_mb} ميجابايت`", inline=True)
                else:
                    embed.add_field(name="⚠️ تنبيه", value="المجلد موجود لكن حجمه **0 ميجابايت**! قد يكون العنصر غير متاح.", inline=False)
                    embed.color = discord.Color.orange()
                    
                embed.set_footer(text="Wallpaper Engine Downloader")

                view = discord.ui.View()
                button = discord.ui.Button(
                    label="🌐 فتح في متصفح Steam",
                    url=f"https://steamcommunity.com/sharedfiles/filedetails/?id={workshop_id}",
                    style=discord.ButtonStyle.link
                )
                view.add_item(button)

                await interaction.followup.send(embed=embed, view=view)

            elif "Invalid workshop item" in output or "not found" in output:
                embed = discord.Embed(
                    title="❌ العنصر غير موجود",
                    description="الـ ID الذي أدخلته غير صحيح أو أن العنصر غير متاح للعامة.",
                    color=discord.Color.red()
                )
                embed.add_field(name="ID المدخل", value=f"`{workshop_id}`", inline=False)
                await interaction.followup.send(embed=embed)

            elif "Login failed" in output or "password" in output.lower():
                embed = discord.Embed(
                    title="❌ فشل تسجيل الدخول إلى Steam",
                    description="تأكد من صحة اسم المستخدم وكلمة المرور في ملف `.env` أو متغيرات البيئة.",
                    color=discord.Color.red()
                )
                await interaction.followup.send(embed=embed)

            else:
                embed = discord.Embed(
                    title="⚠️ حدث خطأ غير متوقع",
                    description="لم يتمكن البوت من تحميل العنصر. تحقق من اللوج التالي:",
                    color=discord.Color.orange()
                )
                embed.add_field(name="📋 المخرجات (آخر 1000 حرف)", value=f"```{output[-1000:]}```", inline=False)
                await interaction.followup.send(embed=embed)

        except FileNotFoundError:
            embed = discord.Embed(
                title="❌ SteamCMD غير موجود",
                description=f"لم يتم العثور على البرنامج في المسار: `{STEAMCMD_PATH}`\nتأكد من رفع مجلد SteamCMD مع البوت.",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed)

        except Exception as e:
            embed = discord.Embed(
                title="💥 عطل داخلي في البوت",
                description=f"حدث خطأ غير متوقع:\n`{str(e)}`",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed)

if __name__ == "__main__":
    bot.run(TOKEN)