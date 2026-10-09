from datetime import datetime, timedelta
import math
import os
from pathlib import Path
import random
import shutil
import subprocess
import PIL.Image as Image
import PIL.ImageDraw as ImageDraw
import PIL.ImageFont as ImageFont
import PIL.ImageSequence as ImageSequence
import pytz

import messages
from models.schedule import CalendarEvent


class EventCardService:
    BASE_WIDTH, BASE_HEIGHT = 1200, 650
    SCALE = 2
    WIDTH = BASE_WIDTH * SCALE
    HEIGHT = BASE_HEIGHT * SCALE

    # Color Palette
    COLOR_BG = (243, 244, 246)
    COLOR_CARD = (255, 255, 255)
    COLOR_CARD_BORDER = (209, 213, 219)
    COLOR_ON = (34, 197, 94)
    COLOR_OFF = (31, 41, 55)
    COLOR_DIMMED = (229, 231, 235)
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
        """Searches for the project logo in assets or root directory."""
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
        """Draws unified brand header with automatic logo placement."""
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
        """Loads TTF fonts with graceful fallbacks."""
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
        """Generates a 3-scene animation: Meme intro -> Status details -> Plan vs Fact comparison."""
        now = datetime.now(self.tz)

        # Pre-render static frames for scenes 2 and 3
        frame_status = self._render_status_card(
            is_power_on, voltage_val, freq_val, duration_str, plan_badge_text, now, group_name
        )
        frame_comparison = self._render_plan_vs_fact(
            planned_events, fact_history or [], now, group_name
        )

        fps = 30
        meme_hold = int(1.3 * fps)        # 1.3 sec meme display
        fade_frames = int(0.4 * fps)      # 0.4 sec fade to status card
        status_hold = int(2.4 * fps)      # 2.4 sec status card display
        slide_frames = int(0.6 * fps)     # 0.6 sec horizontal slide transition
        comp_hold = int(3.5 * fps)        # 3.5 sec comparison card display

        frames: list[Image.Image] = []

        # === SCENE 1: MEME INTRO ===
        meme_frames = self._load_meme_frames(is_power_on, meme_hold)
        frames.extend(meme_frames)

        # Dissolve meme into status card
        last_meme = meme_frames[-1]
        for i in range(1, fade_frames + 1):
            alpha = i / (fade_frames + 1)
            frames.append(Image.blend(last_meme, frame_status, alpha))

        # === SCENE 2: STATUS DETAILS ===
        frames.extend([frame_status] * status_hold)

        # Horizontal push transition to Plan vs Fact
        for i in range(1, slide_frames + 1):
            t = i / (slide_frames + 1)
            eased = 0.5 * (1.0 - math.cos(math.pi * t))
            dx = int(eased * self.BASE_WIDTH)
            c = Image.new("RGB", (self.BASE_WIDTH, self.BASE_HEIGHT), self.COLOR_BG)
            c.paste(frame_status, (-dx, 0))
            c.paste(frame_comparison, (self.BASE_WIDTH - dx, 0))
            frames.append(c)

        # === SCENE 3: PLAN VS FACT ===
        frames.extend([frame_comparison] * comp_hold)

        # Loop transition back to first meme frame
        first_meme = meme_frames[0]
        for i in range(1, fade_frames + 1):
            alpha = i / (fade_frames + 1)
            frames.append(Image.blend(frame_comparison, first_meme, alpha))

        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        self._encode_video(frames, out_path, fps)
        return out_path

    # ==================== MEME PROCESSING ====================
    def _fit_to_canvas(self, raw_m: Image.Image) -> Image.Image:
        """Centers meme image on the standard canvas maintaining aspect ratio."""
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
        """Loads and extracts frames from animated GIFs, MP4 videos, or static images."""
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

        # 1. MP4 Video clip (decoded natively via ffmpeg)
        if ext == ".mp4":
            try:
                return self._extract_mp4_frames(chosen, target_count)
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning("Failed to decode MP4 meme %s: %s", chosen, e)

        # 2. Animated GIF
        elif ext == ".gif":
            try:
                with Image.open(chosen) as g:
                    raw_frames = [self._fit_to_canvas(f.convert("RGBA")) for f in ImageSequence.Iterator(g)]
                if raw_frames:
                    return [raw_frames[i % len(raw_frames)] for i in range(target_count)]
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning("Failed to decode GIF meme %s: %s", chosen, e)

        # 3. Static image (PNG, JPG, WEBP)
        else:
            try:
                with Image.open(chosen) as img:
                    single_frame = self._fit_to_canvas(img.convert("RGBA"))
                    return [single_frame] * target_count
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning("Failed to load static meme %s: %s", chosen, e)

        default_f = self._render_default_meme(is_power_on)
        return [default_f] * target_count

    def _render_default_meme(self, is_power_on: bool) -> Image.Image:
        """Fallback graphic drawn with clean vector shapes without broken font emojis."""
        img = Image.new("RGB", (self.WIDTH, self.HEIGHT), color=self.COLOR_BG)
        draw = ImageDraw.Draw(img)
        f_title = self._get_font(44, bold=True)

        col = self.COLOR_ON if is_power_on else self.COLOR_OFF
        title = messages.DEFAULT_MEME_TITLE_ON if is_power_on else messages.DEFAULT_MEME_TITLE_OFF

        # Draw a clean glowing vector circle indicator instead of a font emoji
        cx, cy = self.WIDTH // 2, int(220 * self.SCALE)
        r = int(50 * self.SCALE)
        draw.ellipse([(cx - r, cy - r), (cx + r, cy + r)], fill=col)

        b_title = draw.textbbox((0, 0), title, font=f_title)
        tw = b_title[2] - b_title[0]
        draw.text(((self.WIDTH - tw) // 2, int(330 * self.SCALE)), title, fill=col, font=f_title)
        return img.resize((self.BASE_WIDTH, self.BASE_HEIGHT), resample=Image.Resampling.LANCZOS)

    # ==================== SCENE 2: STATUS CARD ====================
    def _render_status_card(
        self, is_power_on: bool, voltage_val: str, freq_val: str,
        dur_str: str, plan_badge: str, now: datetime, group_name: str
    ) -> Image.Image:
        img = Image.new("RGB", (self.WIDTH, self.HEIGHT), color=self.COLOR_BG)
        draw = ImageDraw.Draw(img)

        f_title = self._get_font(48, bold=True)
        f_stat = self._get_font(26, bold=True)
        f_desc = self._get_font(22, bold=False)

        # Header with single right-text placement
        rx_text = f"{group_name} • {now.strftime('%H:%M')}"
        self._draw_header(img, draw, messages.CARD_HEADER_TITLE, messages.CARD_SUBTITLE_EVENT, right_text=rx_text)

        # Main background container
        card_y = int(120 * self.SCALE)
        card_h = int(470 * self.SCALE)
        draw.rounded_rectangle(
            [(int(40 * self.SCALE), card_y), (self.WIDTH - int(40 * self.SCALE), card_y + card_h)],
            radius=int(16 * self.SCALE), fill=self.COLOR_CARD, outline=self.COLOR_CARD_BORDER, width=2 * self.SCALE
        )

        color_theme = self.COLOR_ON if is_power_on else self.COLOR_RED
        status_text = messages.CARD_STATUS_ON if is_power_on else messages.CARD_STATUS_OFF

        # Vector status indicator dot
        dot_r = int(14 * self.SCALE)
        dot_x = int(80 * self.SCALE)
        title_y = card_y + int(45 * self.SCALE)
        dot_center_y = title_y + int(24 * self.SCALE)
        draw.ellipse([(dot_x, dot_center_y - dot_r), (dot_x + dot_r * 2, dot_center_y + dot_r)], fill=color_theme)
        draw.text((dot_x + dot_r * 2 + int(18 * self.SCALE), title_y), status_text, fill=color_theme, font=f_title)

        # Recorded time and duration
        t_label = messages.CARD_LABEL_RECORDED_TIME.format(time_str=now.strftime("%H:%M"))
        draw.text((int(80 * self.SCALE), card_y + int(125 * self.SCALE)), t_label, fill=self.COLOR_TEXT, font=f_stat)

        if dur_str:
            draw.text((int(80 * self.SCALE), card_y + int(175 * self.SCALE)), dur_str, fill=self.COLOR_TEXT_MUTED, font=f_desc)

        # Clean plan badge (stripping non-renderable emoji characters)
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

        draw.rounded_rectangle(
            [(int(80 * self.SCALE), badge_y), (int(80 * self.SCALE) + bw, badge_y + bh)],
            radius=int(8 * self.SCALE), fill=self.COLOR_BG
        )

        badge_dot_col = self.COLOR_ON if ("планом" in clean_badge.lower() or "пощастило" in clean_badge.lower()) else self.COLOR_RED
        b_dot_r = int(6 * self.SCALE)
        draw.ellipse(
            [(int(100 * self.SCALE), badge_y + int(19 * self.SCALE)),
             (int(100 * self.SCALE) + b_dot_r * 2, badge_y + int(19 * self.SCALE) + b_dot_r * 2)],
            fill=badge_dot_col
        )
        draw.text((int(122 * self.SCALE), badge_y + int(10 * self.SCALE)), clean_badge, fill=self.COLOR_TEXT, font=f_stat)

        # Power grid metrics
        net_info = f"Напруга: {voltage_val} V" + (f"   •   Частота: {freq_val} Hz" if freq_val and freq_val != "—" else "")
        draw.text((int(80 * self.SCALE), card_y + int(360 * self.SCALE)), net_info, fill=self.COLOR_TEXT_MUTED, font=f_desc)

        return img.resize((self.BASE_WIDTH, self.BASE_HEIGHT), resample=Image.Resampling.LANCZOS)

    # ==================== SCENE 3: PLAN VS FACT ====================
    def _render_plan_vs_fact(
        self,
        planned_events: list[CalendarEvent],
        fact_history: list[dict],
        now: datetime,
        group_name: str
    ) -> Image.Image:
        img = Image.new("RGB", (self.WIDTH, self.HEIGHT), color=self.COLOR_BG)
        draw = ImageDraw.Draw(img)

        f_lbl = self._get_font(26, bold=True)
        f_time = self._get_font(18, bold=False)
        f_badge = self._get_font(20, bold=True)

        sub_title = messages.CARD_SUBTITLE_PLAN_VS_FACT.format(date=now.strftime("%d.%m"), group_name=group_name)
        self._draw_header(img, draw, messages.CARD_TITLE_PLAN_VS_FACT, sub_title)

        # Centered container card
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

        # Vertical positioning for the two comparison bars
        bar_h = int(54 * self.SCALE)
        p_y = card_y + int(110 * self.SCALE)  # Plan bar
        f_y = card_y + int(240 * self.SCALE)  # Fact bar

        # --- 1. DTEK SCHEDULED PLAN BAR ---
        draw.text((int(70 * self.SCALE), p_y + int(12 * self.SCALE)), messages.CARD_LABEL_PLAN, fill=self.COLOR_TEXT, font=f_lbl)
        draw.rounded_rectangle(
            [(chart_x, p_y), (chart_x + chart_w, p_y + bar_h)],
            radius=int(8 * self.SCALE), fill=self.COLOR_CARD, outline=self.COLOR_CARD_BORDER, width=int(1.5 * self.SCALE)
        )

        day_events = [e for e in planned_events if e.start.date() == now.date() or e.end.date() == now.date()]
        for e in day_events:
            s = max(today_start, e.start)
            f = min(today_end, e.end)
            if f > s:
                x1 = chart_x + int(((s - today_start).total_seconds() / 86400) * chart_w)
                x2 = chart_x + int(((f - today_start).total_seconds() / 86400) * chart_w)
                draw.rectangle([(x1, p_y + 1), (x2, p_y + bar_h - 1)], fill=self.COLOR_OFF)

        # --- 2. FACTUAL TELEMETRY BAR ---
        draw.text((int(70 * self.SCALE), f_y + int(12 * self.SCALE)), messages.CARD_LABEL_FACT, fill=self.COLOR_TEXT, font=f_lbl)
        draw.rounded_rectangle(
            [(chart_x, f_y), (chart_x + chart_w, f_y + bar_h)],
            radius=int(8 * self.SCALE), fill=self.COLOR_DIMMED
        )

        intervals = self._parse_ha_history(fact_history, today_start, now)
        for s_dt, e_dt, state_on in intervals:
            x1 = chart_x + int(((s_dt - today_start).total_seconds() / 86400) * chart_w)
            x2 = chart_x + int(((e_dt - today_start).total_seconds() / 86400) * chart_w)
            if x2 > x1:
                color = self.COLOR_ON if state_on else self.COLOR_OFF
                draw.rectangle([(x1, f_y + 1), (x2, f_y + bar_h - 1)], fill=color)

        # Current time cursor (NOW)
        now_x = chart_x + int(now_ratio * chart_w)
        draw.line([(now_x, p_y - int(10 * self.SCALE)), (now_x, f_y + bar_h + int(10 * self.SCALE))], fill=self.COLOR_YELLOW, width=3 * self.SCALE)
        draw.text((now_x - int(25 * self.SCALE), f_y + bar_h + int(15 * self.SCALE)), messages.CARD_BADGE_NOW, fill=self.COLOR_YELLOW, font=f_badge)

        # Hour ticks (00:00 - 24:00)
        for h in [0, 6, 12, 18, 24]:
            hx = chart_x + int((h / 24) * chart_w)
            draw.line([(hx, p_y + bar_h), (hx, p_y + bar_h + int(8 * self.SCALE))], fill=self.COLOR_CARD_BORDER, width=int(1.5 * self.SCALE))
            draw.text((hx - int(16 * self.SCALE), p_y + bar_h + int(12 * self.SCALE)), f"{h:02d}:00", fill=self.COLOR_TEXT_MUTED, font=f_time)

        return img.resize((self.BASE_WIDTH, self.BASE_HEIGHT), resample=Image.Resampling.LANCZOS)

    def _parse_ha_history(self, history: list[dict], today_start: datetime, now: datetime) -> list[tuple[datetime, datetime, bool]]:
        """Parses raw Home Assistant state history into contiguous segments (start, end, is_on)."""
        current_state = (history[-1].get("state") == "on") if history else False
        if not history:
            return [(today_start, now, current_state)]

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

        intervals.append((last_dt, now, last_state))
        return intervals

    # ==================== VIDEO ENCODING ====================
    def _encode_video(self, frames: list[Image.Image], out_path: str, fps: int):
        """Encodes sequence of PIL images to H.264 MP4 using system ffmpeg or imageio."""
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

    def _extract_mp4_frames(self, video_path: Path, target_count: int) -> list[Image.Image]:
        """Extracts and scales frames from an MP4 video using system ffmpeg directly."""
        ffmpeg_bin = shutil.which("ffmpeg") or "ffmpeg"
        bg_hex = "0xF3F4F6"

        # ffmpeg filter scales and pads video to canvas preserving aspect ratio
        vf = (
            f"scale={self.BASE_WIDTH}:{self.BASE_HEIGHT}:force_original_aspect_ratio=decrease,"
            f"pad={self.BASE_WIDTH}:{self.BASE_HEIGHT}:(ow-iw)/2:(oh-ih)/2:color={bg_hex}"
        )
        cmd = [
            ffmpeg_bin,
            "-y",
            "-loglevel", "error",
            "-i", str(video_path),
            "-vf", vf,
            "-vframes", str(target_count),
            "-f", "rawvideo",
            "-pix_fmt", "rgb24",
            "-",
        ]

        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        raw_bytes, stderr = proc.communicate()

        if proc.returncode != 0 or not raw_bytes:
            raise RuntimeError(f"ffmpeg frame extraction failed: {stderr.decode(errors='ignore')}")

        frame_size = self.BASE_WIDTH * self.BASE_HEIGHT * 3
        extracted: list[Image.Image] = []
        for i in range(0, len(raw_bytes), frame_size):
            chunk = raw_bytes[i:i + frame_size]
            if len(chunk) == frame_size:
                extracted.append(Image.frombytes("RGB", (self.BASE_WIDTH, self.BASE_HEIGHT), chunk))

        if not extracted:
            raise RuntimeError(f"No frames decoded from {video_path}")

        # Loop frames if the meme clip is shorter than target duration
        return [extracted[i % len(extracted)] for i in range(target_count)]
