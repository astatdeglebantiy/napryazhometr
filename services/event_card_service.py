from datetime import datetime, timedelta
import math
import os
from pathlib import Path
import random
import shutil
import subprocess
from typing import Sequence
import PIL.Image as Image
import PIL.ImageDraw as ImageDraw
import PIL.ImageFont as ImageFont
import PIL.ImageSequence as ImageSequence
import pytz

from models.schedule import CalendarEvent


class EventCardService:
    BASE_WIDTH, BASE_HEIGHT = 1200, 650
    SCALE = 2
    WIDTH = BASE_WIDTH * SCALE
    HEIGHT = BASE_HEIGHT * SCALE

    COLOR_BG = (243, 244, 246)
    COLOR_CARD = (255, 255, 255)
    COLOR_CARD_BORDER = (209, 213, 219)
    COLOR_ON = (34, 197, 94)            # Сочный зеленый для факта наличия света
    COLOR_OFF = (31, 41, 55)            # Темно-графитовый для отключений
    COLOR_DIMMED = (229, 231, 235)      # Серый для будущих часов
    COLOR_TEXT = (17, 24, 39)
    COLOR_TEXT_MUTED = (107, 114, 128)
    COLOR_RED = (239, 68, 68)
    COLOR_YELLOW = (245, 158, 11)

    def __init__(
        self,
        tz_name: str = "Europe/Kyiv",
        font_path: str = "./assets/font.ttf",
        logo_path: str = "./assets/logo.png",
    ):
        self.tz = pytz.timezone(tz_name)
        self.font_path = font_path
        self.logo_path = logo_path

    def _find_logo_path(self) -> str | None:
        """Ищет логотип в assets или корне проекта."""
        candidates = [self.logo_path, "./assets/logo.png", "./logo.png"]
        for p in candidates:
            if p and os.path.exists(p):
                return p
        return None

    def _draw_header(
        self,
        img: Image.Image,
        draw: ImageDraw.ImageDraw,
        title: str,
        subtitle: str,
        right_text: str | None = None,
    ):
        """Единая шапка с автоматическим встраиванием логотипа."""
        f_hdr = self._get_font(32, bold=True)
        f_sub = self._get_font(22, bold=False)
        mx = int(40 * self.SCALE)
        ty = int(30 * self.SCALE)

        logo_file = self._find_logo_path()
        if logo_file:
            try:
                logo = Image.open(logo_file).convert("RGBA")
                target_h = int(54 * self.SCALE)
                target_w = int(target_h * (logo.width / logo.height))
                logo = logo.resize((target_w, target_h), Image.Resampling.LANCZOS)
                img.paste(logo, (mx, ty), logo)
                mx += target_w + int(14 * self.SCALE)
            except Exception:
                pass

        draw.text((mx, ty), title, fill=self.COLOR_TEXT, font=f_hdr)
        draw.text((mx, ty + int(36 * self.SCALE)), subtitle, fill=self.COLOR_TEXT_MUTED, font=f_sub)

        if right_text:
            b_rx = draw.textbbox((0, 0), right_text, font=f_hdr)
            draw.text(
                (self.WIDTH - int(40 * self.SCALE) - (b_rx[2] - b_rx[0]), ty),
                right_text,
                fill=self.COLOR_TEXT,
                font=f_hdr,
            )

    def _get_font(self, size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
        scaled_size = size * self.SCALE
        candidates = [self.font_path]
        if bold:
            candidates.extend([
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
                "DejaVuSans-Bold.ttf",
            ])
        else:
            candidates.extend([
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                "/usr/share/fonts/TTF/DejaVuSans.ttf",
                "DejaVuSans.ttf",
            ])
        for p in candidates:
            if os.path.exists(p):
                try:
                    return ImageFont.truetype(p, scaled_size)
                except Exception:
                    pass
        return ImageFont.load_default()

    def generate_event_video(
        self,
        is_power_on: bool,
        voltage_val: str,
        freq_val: str,
        duration_str: str,
        plan_badge_text: str,
        planned_events: list[CalendarEvent],
        fact_history: list[dict],
        out_path: str,
        group_name: str = "Група 4.1",
    ) -> str:
        """Генерирует 3-сценное видео: Живой мем -> Карточка статуса -> План vs Факт."""
        now = datetime.now(self.tz)

        # 1. Рендерим кадр статуса (Сцена 2)
        frame_status = self._render_status_card(
            is_power_on, voltage_val, freq_val, duration_str, plan_badge_text, now, group_name
        )

        # 2. Рендерим кадр "План vs Факт" (Сцена 3)
        frame_comparison = self._render_plan_vs_fact(
            planned_events, fact_history or [], is_power_on, now, group_name
        )

        fps = 30
        meme_hold = int(1.3 * fps)        # 1.3 сек держится мем
        fade_frames = int(0.4 * fps)      # 0.4 сек растворение мема в статус
        status_hold = int(2.4 * fps)      # 2.4 сек показ статуса
        slide_frames = int(0.6 * fps)     # 0.6 сек сдвиг в "План vs Факт"
        comp_hold = int(3.5 * fps)        # 3.5 сек показ "План vs Факт"

        frames: list[Image.Image] = []

        # === СЦЕНА 1: МЕМ (.GIF, .MP4 или картинка) ===
        meme_frames = self._load_meme_frames(is_power_on, meme_hold)
        frames.extend(meme_frames)

        # Растворение мема в карточку статуса
        last_meme = meme_frames[-1]
        for i in range(1, fade_frames + 1):
            alpha = i / (fade_frames + 1)
            frames.append(Image.blend(last_meme, frame_status, alpha))

        # === СЦЕНА 2: ДЕТАЛИ СОБЫТИЯ ===
        frames.extend([frame_status] * status_hold)

        # Плавный сдвиг карточки статуса в "План vs Факт" (Push-карусель)
        for i in range(1, slide_frames + 1):
            t = i / (slide_frames + 1)
            eased = 0.5 * (1.0 - math.cos(math.pi * t))
            dx = int(eased * self.BASE_WIDTH)
            c = Image.new("RGB", (self.BASE_WIDTH, self.BASE_HEIGHT), self.COLOR_BG)
            c.paste(frame_status, (-dx, 0))
            c.paste(frame_comparison, (self.BASE_WIDTH - dx, 0))
            frames.append(c)

        # === СЦЕНА 3: ПЛАН VS ФАКТ ===
        frames.extend([frame_comparison] * comp_hold)

        # Мягкая закольцовка обратно на мем
        first_meme = meme_frames[0]
        for i in range(1, fade_frames + 1):
            alpha = i / (fade_frames + 1)
            frames.append(Image.blend(frame_comparison, first_meme, alpha))

        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        self._encode_video(frames, out_path, fps)
        return out_path

    # ==================== ОБРАБОТКА МЕМОВ ====================
    def _fit_to_canvas(self, raw_m: Image.Image) -> Image.Image:
        """Центрирует изображение мема на холсте 1200x650 с сохранением пропорций."""
        canvas = Image.new("RGB", (self.BASE_WIDTH, self.BASE_HEIGHT), self.COLOR_BG)
        target_h = int(self.BASE_HEIGHT * 0.85)
        target_w = int(target_h * (raw_m.width / raw_m.height))
        if target_w > self.BASE_WIDTH * 0.9:
            target_w = int(self.BASE_WIDTH * 0.9)
            target_h = int(target_w * (raw_m.height / raw_m.width))

        resized = raw_m.resize((target_w, target_h), Image.Resampling.LANCZOS)
        cx = (self.BASE_WIDTH - target_w) // 2
        cy = (self.BASE_HEIGHT - target_h) // 2
        canvas.paste(resized, (cx, cy), resized if resized.mode == "RGBA" else None)
        return canvas

    def _load_meme_frames(self, is_power_on: bool, target_count: int) -> list[Image.Image]:
        """Загружает мем (.gif, .mp4, .png, .jpg) и возвращает нужные N кадров анимации."""
        subfolder = "on" if is_power_on else "off"
        meme_dir = Path(f"./assets/memes/{subfolder}")
        candidates = (
            list(meme_dir.glob("*.gif"))
            + list(meme_dir.glob("*.mp4"))
            + list(meme_dir.glob("*.png"))
            + list(meme_dir.glob("*.jpg"))
            + list(meme_dir.glob("*.webp"))
        )

        if not candidates:
            default_f = self._render_default_meme(is_power_on)
            return [default_f] * target_count

        chosen = random.choice(candidates)
        ext = chosen.suffix.lower()

        # 1. Анимированный GIF
        if ext == ".gif":
            try:
                with Image.open(chosen) as g:
                    raw_frames = [self._fit_to_canvas(f.convert("RGBA")) for f in ImageSequence.Iterator(g)]
                if raw_frames:
                    return [raw_frames[i % len(raw_frames)] for i in range(target_count)]
            except Exception:
                pass

        # 2. Видео MP4
        elif ext == ".mp4":
            try:
                import imageio.v3 as iio
                raw_frames = []
                for arr in iio.imiter(chosen):
                    pil_img = Image.fromarray(arr).convert("RGBA")
                    raw_frames.append(self._fit_to_canvas(pil_img))
                    if len(raw_frames) >= target_count:
                        break
                if raw_frames:
                    return [raw_frames[i % len(raw_frames)] for i in range(target_count)]
            except Exception:
                pass

        # 3. Статичные картинки (PNG, JPG, WEBP)
        try:
            with Image.open(chosen) as img:
                single_frame = self._fit_to_canvas(img.convert("RGBA"))
                return [single_frame] * target_count
        except Exception:
            pass

        default_f = self._render_default_meme(is_power_on)
        return [default_f] * target_count

    def _render_default_meme(self, is_power_on: bool) -> Image.Image:
        """Авто-заставка, если пользователь еще не добавил мемы."""
        img = Image.new("RGB", (self.WIDTH, self.HEIGHT), color=self.COLOR_BG)
        draw = ImageDraw.Draw(img)
        f_huge = self._get_font(110, bold=True)
        f_sub = self._get_font(32, bold=False)

        icon = "💡" if is_power_on else "🔌"
        title = "СВІТЛО ПОВЕРНУЛОСЯ!" if is_power_on else "ТЕМРЯВА НАСТАЛА..."
        col = self.COLOR_ON if is_power_on else self.COLOR_OFF

        b1 = draw.textbbox((0, 0), icon, font=f_huge)
        draw.text(((self.WIDTH - (b1[2]-b1[0])) // 2, int(180 * self.SCALE)), icon, font=f_huge)
        b2 = draw.textbbox((0, 0), title, font=f_sub)
        draw.text(((self.WIDTH - (b2[2]-b2[0])) // 2, int(350 * self.SCALE)), title, fill=col, font=f_sub)
        return img.resize((self.BASE_WIDTH, self.BASE_HEIGHT), resample=Image.Resampling.LANCZOS)

    # ==================== СЦЕНА 2: ДЕТАЛИ ====================
    def _render_status_card(
            self, is_power_on: bool, voltage_val: str, freq_val: str,
            dur_str: str, plan_badge: str, now: datetime, group_name: str
    ) -> Image.Image:
        img = Image.new("RGB", (self.WIDTH, self.HEIGHT), color=self.COLOR_BG)
        draw = ImageDraw.Draw(img)

        f_hdr = self._get_font(32, bold=True)
        f_sub = self._get_font(22, bold=False)
        f_title = self._get_font(48, bold=True)
        f_stat = self._get_font(26, bold=True)
        f_desc = self._get_font(22, bold=False)

        # Шапка
        rx_text = f"{group_name} • {now.strftime('%H:%M')}"
        self._draw_header(img, draw, "@Napryazhometr", "Оперативне сповіщення мережі", right_text=rx_text)

        rx_text = f"{group_name} • {now.strftime('%H:%M')}"
        b_rx = draw.textbbox((0, 0), rx_text, font=f_hdr)
        draw.text((self.WIDTH - int(40 * self.SCALE) - (b_rx[2] - b_rx[0]), int(30 * self.SCALE)), rx_text,
                  fill=self.COLOR_TEXT, font=f_hdr)

        # Главная карточка
        card_y = int(120 * self.SCALE)
        card_h = int(470 * self.SCALE)
        draw.rounded_rectangle(
            [(int(40 * self.SCALE), card_y), (self.WIDTH - int(40 * self.SCALE), card_y + card_h)],
            radius=int(16 * self.SCALE), fill=self.COLOR_CARD, outline=self.COLOR_CARD_BORDER, width=2 * self.SCALE
        )

        color_theme = self.COLOR_ON if is_power_on else self.COLOR_RED
        status_text = "СВІТЛО З'ЯВИЛОСЯ" if is_power_on else "СВІТЛО ВИМКНУЛИ"

        # Векторный круглый индикатор статуса (вместо неработающего эмодзи 🟢/🔴)
        dot_r = int(14 * self.SCALE)
        dot_x = int(80 * self.SCALE)
        title_y = card_y + int(45 * self.SCALE)
        dot_center_y = title_y + int(24 * self.SCALE)
        draw.ellipse([(dot_x, dot_center_y - dot_r), (dot_x + dot_r * 2, dot_center_y + dot_r)], fill=color_theme)

        # Текст статуса рядом с индикатором
        draw.text((dot_x + dot_r * 2 + int(18 * self.SCALE), title_y), status_text, fill=color_theme, font=f_title)

        # Время и статус
        t_label = f"Час фіксації: {now.strftime('%H:%M')}"
        draw.text((int(80 * self.SCALE), card_y + int(125 * self.SCALE)), t_label, fill=self.COLOR_TEXT,
                  font=f_stat)

        if dur_str:
            draw.text((int(80 * self.SCALE), card_y + int(175 * self.SCALE)), dur_str, fill=self.COLOR_TEXT_MUTED,
                      font=f_desc)

        # Очищаем текст бейджа от непечатаемых смайлов
        clean_badge = (
            plan_badge.replace("🎰", "")
            .replace("✅", "")
            .replace("⚠️", "")
            .replace("🤬", "")
            .strip()
        )

        badge_y = card_y + int(240 * self.SCALE)
        bb_b = draw.textbbox((0, 0), clean_badge, font=f_stat)
        bw = bb_b[2] - bb_b[0] + int(50 * self.SCALE)
        bh = int(50 * self.SCALE)

        draw.rounded_rectangle([(int(80 * self.SCALE), badge_y), (int(80 * self.SCALE) + bw, badge_y + bh)],
                               radius=int(8 * self.SCALE), fill=self.COLOR_BG)

        # Точка внутри бейджа
        badge_dot_col = self.COLOR_ON if (
                    "планом" in clean_badge.lower() or "пощастило" in clean_badge.lower()) else self.COLOR_RED
        b_dot_r = int(6 * self.SCALE)
        draw.ellipse([(int(100 * self.SCALE), badge_y + int(19 * self.SCALE)),
                      (int(100 * self.SCALE) + b_dot_r * 2, badge_y + int(19 * self.SCALE) + b_dot_r * 2)],
                     fill=badge_dot_col)
        draw.text((int(122 * self.SCALE), badge_y + int(10 * self.SCALE)), clean_badge, fill=self.COLOR_TEXT,
                  font=f_stat)

        # Параметры сети без ломающихся символов
        net_info = f"Напруга: {voltage_val} V" + (
            f"   •   Частота: {freq_val} Hz" if freq_val and freq_val != "—" else "")
        draw.text((int(80 * self.SCALE), card_y + int(360 * self.SCALE)), net_info, fill=self.COLOR_TEXT_MUTED,
                  font=f_desc)

        return img.resize((self.BASE_WIDTH, self.BASE_HEIGHT), resample=Image.Resampling.LANCZOS)

    # ==================== СЦЕНА 3: ПЛАН VS ФАКТ ====================
    def _render_plan_vs_fact(
            self,
            planned_events: list[CalendarEvent],
            fact_history: list[dict],
            is_power_on: bool,
            now: datetime,
            group_name: str
    ) -> Image.Image:
        img = Image.new("RGB", (self.WIDTH, self.HEIGHT), color=self.COLOR_BG)
        draw = ImageDraw.Draw(img)

        f_hdr = self._get_font(32, bold=True)
        f_sub = self._get_font(22, bold=False)
        f_lbl = self._get_font(26, bold=True)
        f_time = self._get_font(18, bold=False)
        f_badge = self._get_font(20, bold=True)

        self._draw_header(img, draw, "@Napryazhometr • ПЛАН ПРОТИ ФАКТУ", f"Аналіз доби ({now.strftime('%d.%m')}) | {group_name}")

        # Центрируем карточку
        card_y = int(120 * self.SCALE)
        card_h = int(470 * self.SCALE)
        draw.rounded_rectangle(
            [(int(40 * self.SCALE), card_y), (self.WIDTH - int(40 * self.SCALE), card_y + card_h)],
            radius=int(16 * self.SCALE), fill=self.COLOR_CARD, outline=self.COLOR_CARD_BORDER, width=2 * self.SCALE
        )

        chart_x = int(180 * self.SCALE)
        chart_w = self.WIDTH - chart_x - int(80 * self.SCALE)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + timedelta(days=1)
        now_sec = (now - today_start).total_seconds()
        now_ratio = min(1.0, max(0.0, now_sec / 86400))

        # Выравниваем две полосы по вертикали по центру карточки
        bar_h = int(54 * self.SCALE)
        p_y = card_y + int(110 * self.SCALE)  # Шкала плана
        f_y = card_y + int(240 * self.SCALE)  # Шкала факта

        # --- 1. ШКАЛА ПЛАНА (ДТЕК) ---
        draw.text((int(70 * self.SCALE), p_y + int(12 * self.SCALE)), "ПЛАН", fill=self.COLOR_TEXT, font=f_lbl)
        draw.rounded_rectangle([(chart_x, p_y), (chart_x + chart_w, p_y + bar_h)], radius=int(8 * self.SCALE),
                               fill=self.COLOR_CARD, outline=self.COLOR_CARD_BORDER, width=int(1.5 * self.SCALE))

        day_events = [e for e in planned_events if e.start.date() == now.date() or e.end.date() == now.date()]
        for e in day_events:
            s = max(today_start, e.start)
            f = min(today_end, e.end)
            if f > s:
                x1 = chart_x + int(((s - today_start).total_seconds() / 86400) * chart_w)
                x2 = chart_x + int(((f - today_start).total_seconds() / 86400) * chart_w)
                draw.rectangle([(x1, p_y + 1), (x2, p_y + bar_h - 1)], fill=self.COLOR_OFF)

        # --- 2. ШКАЛА ФАКТА (РЕАЛЬНОСТЬ) ---
        draw.text((int(70 * self.SCALE), f_y + int(12 * self.SCALE)), "ФАКТ", fill=self.COLOR_TEXT, font=f_lbl)
        draw.rounded_rectangle([(chart_x, f_y), (chart_x + chart_w, f_y + bar_h)], radius=int(8 * self.SCALE),
                               fill=self.COLOR_DIMMED)

        intervals = self._parse_ha_history(fact_history, today_start, now, is_power_on)
        for s_dt, e_dt, state_on in intervals:
            x1 = chart_x + int(((s_dt - today_start).total_seconds() / 86400) * chart_w)
            x2 = chart_x + int(((e_dt - today_start).total_seconds() / 86400) * chart_w)
            if x2 > x1:
                color = self.COLOR_ON if state_on else self.COLOR_OFF
                draw.rectangle([(x1, f_y + 1), (x2, f_y + bar_h - 1)], fill=color)

        # Маркер ЗАРАЗ
        now_x = chart_x + int(now_ratio * chart_w)
        draw.line([(now_x, p_y - int(10 * self.SCALE)), (now_x, f_y + bar_h + int(10 * self.SCALE))],
                  fill=self.COLOR_YELLOW, width=3 * self.SCALE)
        draw.text((now_x - int(25 * self.SCALE), f_y + bar_h + int(15 * self.SCALE)), "ЗАРАЗ",
                  fill=self.COLOR_YELLOW, font=f_badge)

        # Часовые засечки снизу
        for h in [0, 6, 12, 18, 24]:
            hx = chart_x + int((h / 24) * chart_w)
            draw.line([(hx, p_y + bar_h), (hx, p_y + bar_h + int(8 * self.SCALE))], fill=self.COLOR_CARD_BORDER,
                      width=int(1.5 * self.SCALE))
            draw.text((hx - int(16 * self.SCALE), p_y + bar_h + int(12 * self.SCALE)), f"{h:02d}:00",
                      fill=self.COLOR_TEXT_MUTED, font=f_time)

        # Лишний текст снизу полностью удален — остается чистое сравнение

        return img.resize((self.BASE_WIDTH, self.BASE_HEIGHT), resample=Image.Resampling.LANCZOS)

    def _parse_ha_history(self, history: list[dict], today_start: datetime, now: datetime, current_is_on: bool):
        """Превращает сырые события HA в непрерывные отрезки (start, end, is_on)."""
        if not history:
            return [(today_start, now, current_is_on)]

        intervals = []
        last_dt = today_start
        last_state = (history[0].get("state") == "on")

        for item in history:
            raw_t = item.get("last_changed")
            if not raw_t:
                continue
            dt = datetime.fromisoformat(raw_t.replace("Z", "+00:00")).astimezone(self.tz)
            if dt > now:
                break
            if dt > today_start:
                intervals.append((last_dt, dt, last_state))
                last_dt = dt
                last_state = (item.get("state") == "on")

        intervals.append((last_dt, now, current_is_on))
        return intervals

    # ==================== КОДИРОВАНИЕ MP4 ====================
    def _encode_video(self, frames: list[Image.Image], out_path: str, fps: int):
        ffmpeg_bin = shutil.which("ffmpeg")
        if ffmpeg_bin:
            cmd = [
                ffmpeg_bin, "-y", "-loglevel", "error",
                "-f", "rawvideo", "-vcodec", "rawvideo",
                "-s", f"{self.BASE_WIDTH}x{self.BASE_HEIGHT}",
                "-pix_fmt", "rgb24", "-r", str(fps), "-i", "-",
                "-an", "-vcodec", "libx264", "-pix_fmt", "yuv420p",
                "-preset", "ultrafast", "-crf", "22", out_path,
            ]
            proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            raw_data = b"".join(f.tobytes() for f in frames)
            proc.communicate(input=raw_data)
            return

        import imageio.v3 as iio
        import numpy as np
        iio.imwrite(out_path, [np.asarray(f) for f in frames], fps=fps, codec="libx264")
