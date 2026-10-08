import os
import shutil
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import Sequence
import PIL.Image as Image
import PIL.ImageDraw as ImageDraw
import PIL.ImageFont as ImageFont
import pytz

from models.schedule import CalendarEvent


class GraphService:
    BASE_WIDTH, BASE_HEIGHT = 1200, 650
    SCALE = 2
    WIDTH = BASE_WIDTH * SCALE
    HEIGHT = BASE_HEIGHT * SCALE

    # Палитра TrueColor
    COLOR_BG = (243, 244, 246)
    COLOR_CARD = (255, 255, 255)
    COLOR_CARD_BORDER = (209, 213, 219)
    COLOR_OFF = (31, 41, 55)
    COLOR_UNKNOWN = (156, 163, 175)
    COLOR_GRID = (229, 231, 235)
    COLOR_TEXT = (17, 24, 39)
    COLOR_TEXT_MUTED = (107, 114, 128)
    COLOR_YELLOW = (245, 158, 11)
    COLOR_RED_WARN = (239, 68, 68)
    COLOR_GREEN_OK = (16, 185, 129)
    COLOR_MIDNIGHT = (99, 102, 241)

    def __init__(
        self,
        tz_name: str = "Europe/Kyiv",
        font_path: str = "./font.ttf",
        logo_path: str = "./logo.png",
    ):
        self.tz = pytz.timezone(tz_name)
        self.font_path = font_path
        self.logo_path = logo_path

    def _get_font(self, size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
        scaled_size = size * self.SCALE
        candidates = [self.font_path]
        if bold:
            candidates.extend([
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
                "DejaVuSans-Bold.ttf",
                "Arial Bold.ttf",
            ])
        else:
            candidates.extend([
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                "/usr/share/fonts/truetype/ubuntu/Ubuntu-R.ttf",
                "/usr/share/fonts/TTF/DejaVuSans.ttf",
                "DejaVuSans.ttf",
                "Arial.ttf",
            ])

        for path in candidates:
            if os.path.exists(path):
                try:
                    return ImageFont.truetype(path, scaled_size)
                except Exception:
                    continue
        return ImageFont.load_default()

    def generate_chart(
        self,
        planned: Sequence[CalendarEvent] | list[dict],
        scheduled: Sequence[CalendarEvent] | list[dict] | None = None,
        out_path: str = "./svitlo_graph.mp4",
        voltage_val: float | str | None = None,
        frequency_val: float | str | None = None,
        group_name: str = "Група 4.1",
    ) -> str:
        """Создает чистое видео MP4 с плавным горизонтальным перемещением (Slide Transition)."""
        import math

        events = self._normalize_events(planned)
        now = datetime.now(self.tz).replace(second=0, microsecond=0)

        # 1. Рендерим 3 экрана
        s1 = self._render_slide_current(events, now, voltage_val, group_name)
        s2 = self._render_slide_week(events, now, group_name)
        s3 = self._render_slide_status_card(now, voltage_val, frequency_val, group_name)

        fps = 30
        # Длительность показа каждого слайда (в секундах)
        hold_s1 = int(7.0 * fps)  # 7 сек на оперативный таймлайн
        hold_s2 = int(8.0 * fps)  # 8 сек на график недели
        hold_s3 = int(4.0 * fps)  # 4 сек на статус и вольтметр

        # Длительность сдвига: 0.6 сек на переход
        transition_frames = int(0.6 * fps)

        video_frames: list[Image.Image] = []

        def add_smooth_slide(img_from: Image.Image, img_to: Image.Image):
            """Плавное горизонтальное перемещение со сглаживанием Ease-in-out."""
            for i in range(1, transition_frames + 1):
                t = i / (transition_frames + 1)
                # Функция синусоидального сглаживания (плавный старт и мягкая остановка)
                eased_progress = 0.5 * (1.0 - math.cos(math.pi * t))
                offset_x = int(eased_progress * self.BASE_WIDTH)

                # Создаем кадр со смещением: старый уезжает влево, новый въезжает справа
                canvas = Image.new("RGB", (self.BASE_WIDTH, self.BASE_HEIGHT), self.COLOR_BG)
                canvas.paste(img_from, (-offset_x, 0))
                canvas.paste(img_to, (self.BASE_WIDTH - offset_x, 0))
                video_frames.append(canvas)

        # Слайд 1 -> Сдвиг -> Слайд 2
        video_frames.extend([s1] * hold_s1)
        add_smooth_slide(s1, s2)

        # Слайд 2 -> Сдвиг -> Слайд 3
        video_frames.extend([s2] * hold_s2)
        add_smooth_slide(s2, s3)

        # Слайд 3 -> Сдвиг -> Закольцовка на Слайд 1
        video_frames.extend([s3] * hold_s3)
        add_smooth_slide(s3, s1)

        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        self._encode_video(video_frames, out_path, fps)
        return out_path

    def _encode_video(self, frames: list[Image.Image], out_path: str, fps: int):
        """Кодирует кадры в H.264 yuv420p через системный ffmpeg или imageio."""
        ffmpeg_bin = shutil.which("ffmpeg")

        # Если ffmpeg установлен в системе (самый быстрый и надежный путь)
        if ffmpeg_bin:
            cmd = [
                ffmpeg_bin,
                "-y",
                "-f", "rawvideo",
                "-vcodec", "rawvideo",
                "-s", f"{self.BASE_WIDTH}x{self.BASE_HEIGHT}",
                "-pix_fmt", "rgb24",
                "-r", str(fps),
                "-i", "-",
                "-an",
                "-vcodec", "libx264",
                "-pix_fmt", "yuv420p",
                "-preset", "faster",
                "-crf", "22",
                out_path,
            ]
            proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
            )
            for f in frames:
                proc.stdin.write(f.tobytes())
            proc.stdin.close()
            proc.wait()
            if proc.returncode == 0:
                return

        # Запасной вариант через imageio / imageio-ffmpeg
        try:
            import imageio.v3 as iio
            import numpy as np

            arr_frames = [np.asarray(f) for f in frames]
            iio.imwrite(out_path, arr_frames, fps=fps, codec="libx264")
            return
        except Exception as e:
            raise RuntimeError(
                f"Не удалось закодировать MP4. Установите ffmpeg в систему (sudo apt/pacman install ffmpeg) "
                f"или pip install imageio-ffmpeg. Ошибка: {e}"
            )

    # ==================== СЛАЙД 1: ТАЙМЛАЙН ====================
    def _render_slide_current(self, events: list[CalendarEvent], now: datetime, voltage_val, group_name: str) -> Image.Image:
        img = Image.new("RGBA", (self.WIDTH, self.HEIGHT), color=self.COLOR_BG)
        draw = ImageDraw.Draw(img)

        start_dt = now - timedelta(hours=12)
        end_dt = now + timedelta(hours=12)
        start_ts, end_ts = start_dt.timestamp(), end_dt.timestamp()
        total_sec = end_ts - start_ts
        tomorrow_start_ts = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0).timestamp()

        def get_x(ts: float) -> int:
            return int(((ts - start_ts) / total_sec) * self.WIDTH)

        bar_y = int(320 * self.SCALE)
        bar_h = int(105 * self.SCALE)
        bar_r = int(12 * self.SCALE)

        draw.rounded_rectangle([(0, bar_y), (self.WIDTH, bar_y + bar_h)], radius=bar_r, fill=self.COLOR_CARD, outline=self.COLOR_CARD_BORDER, width=2 * self.SCALE)

        has_tomorrow = any(e.end.timestamp() > tomorrow_start_ts for e in events)
        if not has_tomorrow and end_ts > tomorrow_start_ts:
            x_unk = max(0, get_x(tomorrow_start_ts))
            if x_unk < self.WIDTH:
                draw.rectangle([(x_unk, bar_y), (self.WIDTH, bar_y + bar_h)], fill=self.COLOR_UNKNOWN)

        for e in events:
            s_ts, e_ts = e.start.timestamp(), e.end.timestamp()
            if e_ts < start_ts or s_ts > end_ts:
                continue
            x1, x2 = max(0, get_x(s_ts)), min(self.WIDTH, get_x(e_ts))
            if x2 > x1:
                draw.rectangle([(x1, bar_y), (x2, bar_y + bar_h)], fill=self.COLOR_OFF)

        curr = start_dt.replace(minute=0, second=0, microsecond=0)
        f_time = self._get_font(22, bold=False)
        f_date = self._get_font(18, bold=True)
        while curr.timestamp() < end_ts:
            xg = get_x(curr.timestamp())
            if curr.hour == 0:
                draw.line([(xg, bar_y - 20 * self.SCALE), (xg, bar_y + bar_h + 10 * self.SCALE)], fill=self.COLOR_MIDNIGHT, width=3 * self.SCALE)
                draw.text((xg + 6 * self.SCALE, bar_y - 22 * self.SCALE), curr.strftime("%d.%m"), fill=self.COLOR_MIDNIGHT, font=f_date)
            else:
                draw.line([(xg, bar_y), (xg, bar_y + bar_h)], fill=self.COLOR_GRID, width=1 * self.SCALE)

            if curr.hour % 2 == 0:
                t_str = curr.strftime("%H:%M")
                bbox = draw.textbbox((0, 0), t_str, font=f_time)
                draw.text((xg - (bbox[2] - bbox[0]) // 2, bar_y + bar_h + 10 * self.SCALE), t_str, fill=self.COLOR_TEXT_MUTED, font=f_time)
            curr += timedelta(hours=1)

        mid_x = self.WIDTH // 2
        draw.line([(mid_x, bar_y - 12 * self.SCALE), (mid_x, bar_y + bar_h + 8 * self.SCALE)], fill=self.COLOR_YELLOW, width=3 * self.SCALE)

        f_now = self._get_font(18, bold=True)
        now_str = "ЗАРАЗ"
        bb = draw.textbbox((0, 0), now_str, font=f_now)
        tw, th = bb[2] - bb[0], bb[3] - bb[1]
        pad_x, pad_y = int(14 * self.SCALE), int(6 * self.SCALE)
        bw, bh = tw + pad_x * 2, th + pad_y * 2
        badge_bot = bar_y - int(14 * self.SCALE)
        badge_top = badge_bot - bh

        draw.polygon([(mid_x, bar_y - int(3 * self.SCALE)), (mid_x - int(7 * self.SCALE), badge_bot), (mid_x + int(7 * self.SCALE), badge_bot)], fill=self.COLOR_YELLOW)
        draw.rounded_rectangle([(mid_x - bw // 2, badge_top), (mid_x + bw // 2, badge_bot)], radius=int(8 * self.SCALE), fill=self.COLOR_YELLOW)
        draw.text((mid_x - tw // 2, badge_top + pad_y - int(2 * self.SCALE)), now_str, fill=(25, 25, 25), font=f_now)

        self._draw_voltmeter(draw, mid_x, badge_top - int(35 * self.SCALE), voltage_val)
        self._draw_header(img, draw, group_name, now, subtitle="Оперативний зріз (24 години)")
        self._draw_legend(draw)

        return img.resize((self.BASE_WIDTH, self.BASE_HEIGHT), resample=Image.Resampling.LANCZOS).convert("RGB")

    # ==================== СЛАЙД 2: ТИЖДЕНЬ ====================
    def _render_slide_week(self, events: list[CalendarEvent], now: datetime, group_name: str) -> Image.Image:
        img = Image.new("RGBA", (self.WIDTH, self.HEIGHT), color=self.COLOR_BG)
        draw = ImageDraw.Draw(img)

        self._draw_header(img, draw, group_name, now, subtitle="Тижневий графік відключень")

        f_day = self._get_font(20, bold=True)
        f_sub = self._get_font(16, bold=False)

        # Украинские названия дней недели (0 = Понеділок, 6 = Неділя)
        UA_WEEKDAYS = [
            "Понеділок",
            "Вівторок",
            "Середа",
            "Четвер",
            "П'ятниця",
            "Субота",
            "Неділя"
        ]

        today = now.date()
        days = [today + timedelta(days=i) for i in range(6)]

        # Сдвигаем начало полос чуть правее (175 вместо 160), чтобы длинные слова (Понеділок/П'ятниця) не прилипали
        chart_x = int(175 * self.SCALE)
        chart_w = self.WIDTH - chart_x - int(40 * self.SCALE)
        start_y = int(140 * self.SCALE)
        row_h = int(58 * self.SCALE)
        bar_h = int(36 * self.SCALE)

        for idx, d in enumerate(days):
            ry = start_y + idx * row_h
            d_start = self.tz.localize(datetime.combine(d, datetime.min.time()))
            d_end = d_start + timedelta(days=1)

            d_label = d.strftime("%d.%m")

            # Первые два дня — Сьогодні и Завтра, начиная с 3-го дня — украинский день недели
            if idx == 0:
                name_label = "Сьогодні"
            elif idx == 1:
                name_label = "Завтра"
            else:
                name_label = UA_WEEKDAYS[d.weekday()]

            draw.text((int(35 * self.SCALE), ry), name_label, fill=self.COLOR_TEXT, font=f_day)
            draw.text((int(35 * self.SCALE), ry + int(22 * self.SCALE)), d_label, fill=self.COLOR_TEXT_MUTED,
                      font=f_sub)

            # Базовая полоса суток
            bx1, bx2 = chart_x, chart_x + chart_w
            draw.rounded_rectangle([(bx1, ry), (bx2, ry + bar_h)], radius=int(6 * self.SCALE), fill=self.COLOR_CARD,
                                   outline=self.COLOR_CARD_BORDER, width=int(1.5 * self.SCALE))

            day_events = [e for e in events if e.start < d_end and e.end > d_start]

            if not day_events and d > today + timedelta(days=1):
                draw.rounded_rectangle([(bx1, ry), (bx2, ry + bar_h)], radius=int(6 * self.SCALE),
                                       fill=self.COLOR_UNKNOWN)
            else:
                for e in day_events:
                    s = max(d_start, e.start)
                    f = min(d_end, e.end)
                    sec_s = (s - d_start).total_seconds()
                    sec_f = (f - d_start).total_seconds()
                    x1 = bx1 + int((sec_s / 86400) * chart_w)
                    x2 = bx1 + int((sec_f / 86400) * chart_w)
                    if x2 > x1:
                        draw.rectangle([(x1, ry + 1), (x2, ry + bar_h - 1)], fill=self.COLOR_OFF)

        f_axis = self._get_font(18, bold=False)
        axis_y = start_y + len(days) * row_h + int(10 * self.SCALE)
        for h in [0, 6, 12, 18, 24]:
            ax_x = chart_x + int((h / 24) * chart_w)
            draw.line([(ax_x, start_y - int(10 * self.SCALE)), (ax_x, axis_y)], fill=self.COLOR_GRID,
                      width=int(1.5 * self.SCALE))
            draw.text((ax_x - int(18 * self.SCALE), axis_y + int(4 * self.SCALE)), f"{h:02d}:00",
                      fill=self.COLOR_TEXT_MUTED, font=f_axis)

        self._draw_legend(draw)
        return img.resize((self.BASE_WIDTH, self.BASE_HEIGHT), resample=Image.Resampling.LANCZOS).convert("RGB")

    # ==================== СЛАЙД 3: КАРТКА СТАТУСУ ====================
    def _render_slide_status_card(self, now: datetime, voltage_val, frequency_val, group_name: str) -> Image.Image:
        img = Image.new("RGBA", (self.WIDTH, self.HEIGHT), color=self.COLOR_BG)
        draw = ImageDraw.Draw(img)

        self._draw_header(img, draw, group_name, now, subtitle="Діагностика напруги в реальному часі")

        f_big_v = self._get_font(120, bold=True)
        f_big_unit = self._get_font(130, bold=True)
        f_card_title = self._get_font(28, bold=True)
        f_card_desc = self._get_font(22, bold=False)

        # 1. Парсинг вольтажа
        try:
            val_f = float(voltage_val) if voltage_val not in (None, "unknown", "unavailable", "", "—") else 0.0
            v_num = str(int(round(val_f))) if val_f > 0 else "--"
        except Exception:
            val_f, v_num = 0.0, "--"

        # 2. Парсинг частоты
        try:
            freq_f = float(frequency_val) if frequency_val not in (None, "unknown", "unavailable", "", "—") else 0.0
            freq_display = f"{freq_f:.1f} Hz" if freq_f > 0 else "—"
        except Exception:
            freq_display = "—"

        # 3. Корректные статусы (свет есть / света нет / отклонение)
        if val_f == 0 or v_num == "--":
            status_color = self.COLOR_TEXT_MUTED  # Спокойный серый
            status_text = "ЖИВЛЕННЯ ВІДСУТНЄ (МЕРЕЖА ЗНЕСТРУМЛЕНА)"
            unit_color = self.COLOR_TEXT_MUTED
            num_color = self.COLOR_TEXT_MUTED
        elif 200 <= val_f <= 245:
            status_color = self.COLOR_GREEN_OK  # Зеленый
            status_text = "МЕРЕЖА СТАБІЛЬНА (НОРМА)"
            unit_color = self.COLOR_YELLOW
            num_color = self.COLOR_TEXT
        else:
            status_color = self.COLOR_RED_WARN  # Красный (реальная авария по напряжению)
            status_text = "УВАГА: ВІДХИЛЕННЯ НАПРУГИ"
            unit_color = self.COLOR_RED_WARN
            num_color = self.COLOR_RED_WARN

        # Большая белая карточка
        card_w = int(1000 * self.SCALE)
        card_h = int(360 * self.SCALE)
        cx1 = (self.WIDTH - card_w) // 2
        cy1 = int(140 * self.SCALE)

        draw.rounded_rectangle(
            [(cx1, cy1), (cx1 + card_w, cy1 + card_h)],
            radius=int(20 * self.SCALE),
            fill=self.COLOR_CARD,
            outline=self.COLOR_CARD_BORDER,
            width=2 * self.SCALE,
        )

        # Цифры вольтметра
        b_num = draw.textbbox((0, 0), v_num, font=f_big_v)
        b_unit = draw.textbbox((0, 0), "V", font=f_big_unit)
        wn, wu = b_num[2] - b_num[0], b_unit[2] - b_unit[0]
        tot_w = wn + int(20 * self.SCALE) + wu
        vx = (self.WIDTH - tot_w) // 2
        vy = cy1 + int(45 * self.SCALE)

        draw.text((vx, vy), v_num, fill=num_color, font=f_big_v)
        draw.text((vx + wn + int(20 * self.SCALE), vy - int(10 * self.SCALE)), "V", fill=unit_color,
                  font=f_big_unit)

        # Центральный бейдж статуса
        badge_y = cy1 + int(210 * self.SCALE)
        bb_st = draw.textbbox((0, 0), status_text, font=f_card_title)
        btw = bb_st[2] - bb_st[0]
        bx = (self.WIDTH - btw) // 2
        draw.rounded_rectangle(
            [(bx - int(25 * self.SCALE), badge_y),
             (bx + btw + int(25 * self.SCALE), badge_y + int(50 * self.SCALE))],
            radius=int(10 * self.SCALE),
            fill=status_color,
        )
        draw.text((bx, badge_y + int(8 * self.SCALE)), status_text, fill=(255, 255, 255), font=f_card_title)

        # ОДНА ровная строка внизу: датчик и частота сети (автоматически по центру)
        bottom_desc = f"Моніторинг реле PZEM • Частота: {freq_display}"
        bb_desc = draw.textbbox((0, 0), bottom_desc, font=f_card_desc)
        dw = bb_desc[2] - bb_desc[0]
        draw.text(
            ((self.WIDTH - dw) // 2, cy1 + int(290 * self.SCALE)),
            bottom_desc,
            fill=self.COLOR_TEXT_MUTED,
            font=f_card_desc,
        )

        self._draw_legend(draw)
        return img.resize((self.BASE_WIDTH, self.BASE_HEIGHT), resample=Image.Resampling.LANCZOS).convert("RGB")

    def _draw_voltmeter(self, draw: ImageDraw.ImageDraw, mid_x: int, top_anchor_y: int, voltage_val):
        f_num = self._get_font(84, bold=True)
        f_unit = self._get_font(110, bold=True)
        try:
            val_f = float(voltage_val) if voltage_val not in (None, "unknown", "unavailable", "") else 0.0
            v_num = str(int(round(val_f))) if val_f > 0 else "--"
        except Exception:
            val_f, v_num = 0.0, "--"

        is_warn = val_f > 50 and (val_f < 195 or val_f > 253)
        uc = self.COLOR_RED_WARN if is_warn else self.COLOR_YELLOW
        nc = self.COLOR_RED_WARN if is_warn else self.COLOR_TEXT

        bn = draw.textbbox((0, 0), v_num, font=f_num)
        bu = draw.textbbox((0, 0), "V", font=f_unit)
        wn, hn = bn[2] - bn[0], bn[3] - bn[1]
        wu, hu = bu[2] - bu[0], bu[3] - bu[1]

        total_w = wn + int(12 * self.SCALE) + wu
        sx = mid_x - total_w // 2
        base_y = top_anchor_y - int(35 * self.SCALE)

        draw.text((sx, base_y - hn), v_num, fill=nc, font=f_num)
        draw.text((sx + wn + int(12 * self.SCALE), base_y - hu - int(6 * self.SCALE)), "V", fill=uc, font=f_unit)

    def _find_logo_path(self) -> str | None:
        """Автоматически ищет файл логотипа в проекте."""
        candidates = [
            self.logo_path,
            "./logo.png",
            "./assets/logo.png",
        ]
        for p in candidates:
            if p and os.path.exists(p):
                return p
        return None

    def _draw_header(self, img: Image.Image, draw: ImageDraw.ImageDraw, group_name: str, now: datetime, subtitle: str):
        f_title = self._get_font(30, bold=True)
        f_sub = self._get_font(20, bold=False)
        mx = int(35 * self.SCALE)
        ty = int(25 * self.SCALE)

        # Отрисовка логотипа (если найден файл)
        logo_file = self._find_logo_path()
        if logo_file:
            try:
                logo = Image.open(logo_file).convert("RGBA")
                target_h = int(52 * self.SCALE)
                target_w = int(target_h * (logo.width / logo.height))
                logo = logo.resize((target_w, target_h), Image.Resampling.LANCZOS)

                # Вставляем логотип с поддержкой прозрачности
                img.paste(logo, (mx, ty), logo)
                mx += target_w + int(14 * self.SCALE)
            except Exception:
                pass

        # Название и подзаголовок слева
        draw.text((mx, ty), "@Napryazhometr", fill=self.COLOR_TEXT, font=f_title)
        draw.text((mx, ty + int(36 * self.SCALE)), subtitle, fill=self.COLOR_TEXT_MUTED, font=f_sub)

        # Группа и время справа
        r_sub = f"Оновлено о {now.strftime('%H:%M')}"
        bt = draw.textbbox((0, 0), group_name, font=f_title)
        bs = draw.textbbox((0, 0), r_sub, font=f_sub)

        rx = self.WIDTH - int(35 * self.SCALE)
        draw.text((rx - (bt[2] - bt[0]), ty), group_name, fill=self.COLOR_TEXT, font=f_title)
        draw.text((rx - (bs[2] - bs[0]), ty + int(36 * self.SCALE)), r_sub, fill=self.COLOR_TEXT_MUTED, font=f_sub)

    def _draw_legend(self, draw: ImageDraw.ImageDraw):
        f_leg = self._get_font(24, bold=False)
        items = [("Світло є", self.COLOR_CARD, self.COLOR_CARD_BORDER), ("Відключення", self.COLOR_OFF, None), ("Графік відсутній", self.COLOR_UNKNOWN, None)]
        box_sz = int(24 * self.SCALE)
        gap_txt = int(10 * self.SCALE)
        gap_item = int(40 * self.SCALE)
        ly = self.HEIGHT - int(60 * self.SCALE)

        total_w = sum(draw.textbbox((0, 0), txt, font=f_leg)[2] + box_sz + gap_txt for txt, _, _ in items) + gap_item * (len(items) - 1)
        cx = (self.WIDTH - total_w) // 2

        for txt, fill_col, out_col in items:
            draw.rounded_rectangle([(cx, ly), (cx + box_sz, ly + box_sz)], radius=int(4 * self.SCALE), fill=fill_col, outline=out_col, width=int(1.5 * self.SCALE) if out_col else 0)
            draw.text((cx + box_sz + gap_txt, ly - int(2 * self.SCALE)), txt, fill=self.COLOR_TEXT, font=f_leg)
            cx += box_sz + gap_txt + draw.textbbox((0, 0), txt, font=f_leg)[2] + gap_item

    def _normalize_events(self, raw_events: Sequence) -> list[CalendarEvent]:
        events = []
        for e in raw_events:
            if isinstance(e, CalendarEvent):
                events.append(e)
            elif isinstance(e, dict):
                s = e.get("start")
                f = e.get("end")
                if isinstance(s, str):
                    s = datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(self.tz)
                if isinstance(f, str):
                    f = datetime.fromisoformat(f.replace("Z", "+00:00")).astimezone(self.tz)
                events.append(CalendarEvent(start=s, end=f, summary=e.get("summary", "")))
        return events
