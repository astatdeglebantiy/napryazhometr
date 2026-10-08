import asyncio
from datetime import datetime, timedelta
import logging
import sys
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import FSInputFile
import pytz

from bot.handlers import router
from config import config
from models.power import VoltageAlert, FrequencyAlert
from services.event_card_service import EventCardService
from services.graph_service import GraphService
from services.ha_client import HomeAssistantClient
from services.power_service import PowerService
from services.schedule_service import ScheduleService
from storage.state_store import StateStore

# Логирование
log_level = logging.DEBUG if config.is_dev else logging.INFO
logging.basicConfig(
    level=log_level,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("napryazhometr")


async def handle_schedule_update(
    bot: Bot,
    ha_client: HomeAssistantClient,
    schedule_srv: ScheduleService,
    graph_srv: GraphService,
    store: StateStore,
):
    """Публикация графика одним сообщением: видео + подпись с цитатами."""
    tz = pytz.timezone(config.timezone)
    now = datetime.now(tz)
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)

    for attempt in range(1, 7):
        logger.info("Перевірка оновлення графіка (спроба %d з 6)...", attempt)
        planned = await ha_client.get_calendar_events(config.calendar_planned, today, 48)
        scheduled = await ha_client.get_calendar_events(config.calendar_scheduled, today, 48)

        signature = schedule_srv.compute_signature(planned, scheduled, today.date())
        if signature != store.last_schedule_hash:
            logger.info("Виявлено новий графік! Формування повідомлення...")
            store.last_schedule_hash = signature
            store.save()

            # Округление вольтажа (226 V)
            voltage_state = await ha_client.get_entity_state(config.voltage_sensor)
            freq_state = await ha_client.get_entity_state(config.frequency_sensor)

            try:
                raw_v = voltage_state.get("state") if voltage_state else None
                current_v = f"{int(round(float(raw_v)))} V" if raw_v else "—"
            except (ValueError, TypeError):
                current_v = "—"

            try:
                raw_hz = freq_state.get("state") if freq_state else None
                current_hz = f"{float(raw_hz):.1f} Hz" if raw_hz else ""
            except (ValueError, TypeError):
                current_hz = ""

            # Генерация видео с плавным горизонтальным сдвигом
            logger.info("Генерація MP4 графіка...")
            graph_srv.generate_chart(
                planned=planned,
                scheduled=scheduled,
                out_path=config.output_image_path,
                voltage_val=current_v.replace(" V", ""),
                frequency_val=current_hz.replace(" Hz", ""),
                group_name=config.group_name,
            )
            logger.info("Відео згенеровано.")

            today_text = schedule_srv.build_day_timeline(planned, today.date(), False)
            tomorrow_text = schedule_srv.build_day_timeline(
                planned, (today + timedelta(days=1)).date(), True
            )

            upd_sensor = await ha_client.get_entity_state(config.dtek_schedule_updated_on)
            upd_str = "—"
            if upd_sensor:
                try:
                    dt = datetime.fromisoformat(
                        upd_sensor["state"].replace("Z", "+00:00")
                    ).astimezone(tz)
                    upd_str = dt.strftime("%H:%M")
                except Exception:
                    upd_str = str(upd_sensor["state"])[:5]

            net_status = f"{current_v}" + (f" • {current_hz}" if current_hz else "")
            caption = (
                f"<b>ГРАФІК ВІДКЛЮЧЕНЬ | {config.group_name}</b>\n"
                f"<i>Оновлено: {upd_str} • Мережа: {net_status}</i>\n\n"
                f"<b>Сьогодні ({now.strftime('%d.%m')}):</b>\n"
                f"{today_text}\n\n"
                f"<b>Завтра ({(today + timedelta(days=1)).strftime('%d.%m')}):</b>\n"
                f"{tomorrow_text}"
            )

            # Отправка ОДНОГО сообщения (анимация + подпись к ней)
            await bot.send_animation(
                chat_id=config.target_chat_id,
                animation=FSInputFile(config.output_image_path),
                caption=config.msg_prefix + caption.strip(),
                parse_mode=ParseMode.HTML,
            )
            logger.info("Повідомлення успішно надіслано в Telegram.")
            break

        await asyncio.sleep(10)


async def main():
    if not config.bot_token or not config.target_chat_id:
        logger.error("Не задано токен або ID чату (is_dev=%s)", config.is_dev)
        sys.exit(1)

    bot = Bot(
        token=config.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()

    store = StateStore(config.state_file_path)
    ha_client = HomeAssistantClient(
        config.ha_base_url, config.ha_ws_url, config.ha_token, config.timezone
    )
    power_service = PowerService(config, store)
    schedule_service = ScheduleService(config.timezone)
    graph_service = GraphService(
        tz_name=config.timezone,
        font_path=config.font_path,
        logo_path=config.logo_path,
    )
    event_card_service = EventCardService(
        tz_name=config.timezone,
        font_path=config.font_path,
        logo_path=config.logo_path,
    )

    dp["ha_client"] = ha_client
    dp["power_service"] = power_service
    dp["store"] = store
    dp.include_router(router)

    tz = pytz.timezone(config.timezone)
    _schedule_task: asyncio.Task | None = None
    _freq_restore_task: asyncio.Task | None = None

    async def on_ha_event(data: dict):
        nonlocal _schedule_task, _freq_restore_task
        entity_id = data.get("entity_id")
        new_state = data.get("new_state")
        old_state = data.get("old_state")

        if not new_state or not old_state or new_state.get("state") in ("unknown", "unavailable"):
            return

        # 1. ОБНОВЛЕНИЕ ГРАФИКА ДТЭК
        if entity_id == config.dtek_schedule_updated_on:
            if _schedule_task is None or _schedule_task.done():
                _schedule_task = asyncio.create_task(
                    handle_schedule_update(
                        bot, ha_client, schedule_service, graph_service, store
                    )
                )

        # 2. ПИТАНИЕ (СВЕТ ВКЛ/ВЫКЛ)
        elif entity_id == config.power_binary_sensor:
            if new_state["state"] == "on" and old_state["state"] != "on":
                power_service.cancel_tasks()

                async def power_on():
                    store.active_voltage_alert = VoltageAlert.NONE
                    store.last_power_on_ts = datetime.now().timestamp()
                    store.save()

                    v_state = await ha_client.get_entity_state(config.voltage_sensor)
                    dtek_state = await ha_client.get_entity_state(config.dtek_electricity_status)
                    planned_events = await ha_client.get_calendar_events(config.calendar_planned, datetime.now(tz), 24)

                    voltage = float(v_state["state"]) if v_state else 0.0
                    dtek_status = dtek_state.get("state", "normal") if dtek_state else "normal"

                    if dtek_status == "planned_outage":
                        plan_badge = "🎰 Нам пощастило! (Поза планом)"
                    elif dtek_status == "normal":
                        plan_badge = "✅ Все за планом ДТЕК"
                    else:
                        plan_badge = "⚠️ Завершення аварійних робіт"

                    event_anim_path = "./event_power_on.mp4"
                    dur_str = f"Світла не було: {power_service.format_duration(int(datetime.now().timestamp() - store.last_power_off_ts))}" if store.last_power_off_ts else ""

                    today_start = datetime.now(tz).replace(hour=0, minute=0, second=0, microsecond=0)
                    fact_history = await ha_client.get_entity_history(
                        config.power_binary_sensor, today_start, datetime.now(tz)
                    )

                    event_card_service.generate_event_video(
                        is_power_on=True,
                        voltage_val=f"{int(round(voltage))}",
                        freq_val="50.0",
                        duration_str=dur_str,
                        plan_badge_text=plan_badge,
                        planned_events=planned_events,
                        fact_history=fact_history,
                        out_path=event_anim_path,
                        group_name=config.group_name
                    )

                    msg = config.msg_prefix + power_service.build_power_on_message(voltage, dtek_status, None)

                    # Отправляем анимацию с сообщением
                    await bot.send_animation(
                        config.target_chat_id,
                        animation=FSInputFile(event_anim_path),
                        caption=msg,
                        parse_mode=ParseMode.HTML
                    )

                power_service._power_on_task = asyncio.create_task(power_on())


            elif new_state["state"] == "off" and old_state["state"] != "off":
                power_service.cancel_tasks()
                store.active_voltage_alert = VoltageAlert.NONE
                store.last_power_off_ts = datetime.now().timestamp()
                store.save()
                dtek_state = await ha_client.get_entity_state(config.dtek_electricity_status)
                planned_events = await ha_client.get_calendar_events(config.calendar_planned, datetime.now(tz), 24)
                dtek_status = dtek_state.get("state", "normal") if dtek_state else "normal"
                if dtek_status == "normal":
                    plan_badge = "🤬 Світло зникло раніше графіка"
                elif dtek_status == "planned_outage":
                    plan_badge = "✅ Чітко за планом ДТЕК"
                else:
                    plan_badge = "⚠️ Аварійне відключення"
                event_anim_path = "./event_power_off.mp4"
                dur_str = f"Світло було: {power_service.format_duration(int(datetime.now().timestamp() - store.last_power_on_ts))}" if store.last_power_on_ts else ""

                today_start = datetime.now(tz).replace(hour=0, minute=0, second=0, microsecond=0)
                fact_history = await ha_client.get_entity_history(
                    config.power_binary_sensor, today_start, datetime.now(tz)
                )

                event_card_service.generate_event_video(
                    is_power_on=False,
                    voltage_val="0",
                    freq_val="—",
                    duration_str=dur_str,
                    plan_badge_text=plan_badge,
                    planned_events=planned_events,
                    fact_history=fact_history,
                    out_path=event_anim_path,
                    group_name=config.group_name
                )
                msg = config.msg_prefix + power_service.build_power_off_message(dtek_status, None)
                await bot.send_animation(
                    config.target_chat_id,
                    animation=FSInputFile(event_anim_path),
                    caption=msg,
                    parse_mode=ParseMode.HTML
                )

        # 3. КОНТРОЛЬ НАПРЯЖЕНИЯ
        elif entity_id == config.voltage_sensor:
            try:
                v = float(new_state["state"])
            except (ValueError, TypeError):
                return

            p_state = await ha_client.get_entity_state(config.power_binary_sensor)
            power_is_on = (p_state.get("state") == "on") if p_state else False
            if not power_is_on:
                return

            # 1. КРИТИЧНО НИЗЬКА (< 175 V)
            if v < 175 and store.active_voltage_alert != VoltageAlert.CRITICAL_LOW:
                store.active_voltage_alert = VoltageAlert.CRITICAL_LOW
                store.save()
                await bot.send_message(
                    config.target_chat_id,
                    f"🚨 <b>КРИТИЧНО НИЗЬКА НАПРУГА</b>\n\n"
                    f"📉 Поточна: <code>{v:.1f} V</code>\n\n"
                    f"⛔️ <b>Терміново знеструмте техніку!</b>\n"
                    f"<i>Компресори холодильників та насоси можуть перегрітися і згоріти.</i>",
                )

            # 2. ПРОСТО НИЗЬКА (175..194 V)
            elif 175 <= v < 195 and store.active_voltage_alert not in (
                    VoltageAlert.LOW,
                    VoltageAlert.CRITICAL_LOW,
            ):
                store.active_voltage_alert = VoltageAlert.LOW
                store.save()
                await bot.send_message(
                    config.target_chat_id,
                    f"⚠️ <b>НИЗЬКА НАПРУГА</b>\n\n"
                    f"📉 Поточна: <code>{v:.1f} V</code>\n\n"
                    f"🔌 <i>Радимо вимкнути чутливі прилади.</i>",
                )

            # 3. КРИТИЧНО ВИСОКА (>= 265 V)
            elif 265 <= v < 320 and store.active_voltage_alert != VoltageAlert.CRITICAL_HIGH:
                store.active_voltage_alert = VoltageAlert.CRITICAL_HIGH
                store.save()
                await bot.send_message(
                    config.target_chat_id,
                    f"🚨 <b>КРИТИЧНО ВИСОКА НАПРУГА</b>\n\n"
                    f"📈 Поточна: <code>{v:.1f} V</code>\n\n"
                    f"⛔️ <b>Загроза виходу техніки з ладу або пожежі!</b>\n",
                )

            # 4. ПРОСТО ВИСОКА (253..264 V)
            elif 253 < v < 265 and store.active_voltage_alert not in (
                    VoltageAlert.HIGH,
                    VoltageAlert.CRITICAL_HIGH,
            ):
                store.active_voltage_alert = VoltageAlert.HIGH
                store.save()
                await bot.send_message(
                    config.target_chat_id,
                    f"⚠️ <b>ВИСОКА НАПРУГА</b>\n\n"
                    f"📈 Поточна: <code>{v:.1f} V</code>\n\n"
                    f"🔌 <i>Радимо вимкнути енергоємні прилади.</i>",
                )

            # 5. СТАБІЛІЗАЦІЯ (200..245 V с выдержкой 30 секунд)
            elif 200 <= v <= 245 and store.active_voltage_alert != VoltageAlert.NONE:
                if (
                        not power_service._voltage_restore_task
                        or power_service._voltage_restore_task.done()
                ):
                    async def delayed_restore():
                        await asyncio.sleep(30)
                        store.active_voltage_alert = VoltageAlert.NONE
                        store.save()
                        await bot.send_message(
                            config.target_chat_id,
                            f"✅ <b>НАПРУГА СТАБІЛІЗУВАЛАСЬ</b>\n\n"
                            f"📊 Поточна: <code>{v:.1f} V</code>\n\n"
                            f"🔌 <i>Мережа в нормі, можна поступово вмикати техніку.</i>",
                        )

                    power_service._voltage_restore_task = asyncio.create_task(
                        delayed_restore()
                    )
            else:
                # Если напряжение снова вышло из нормы до истечения 30 секунд
                if (
                        power_service._voltage_restore_task
                        and not power_service._voltage_restore_task.done()
                ):
                    power_service._voltage_restore_task.cancel()

        # 4. КОНТРОЛЬ ЧАСТОТИ МЕРЕЖІ
        elif entity_id == config.frequency_sensor:
            try:
                hz = float(new_state["state"])
            except (ValueError, TypeError):
                return

            # Игнорируем показания, если свет выключен или датчик выдает 0.0 Hz
            p_state = await ha_client.get_entity_state(config.power_binary_sensor)
            power_is_on = (p_state.get("state") == "on") if p_state else False
            if not power_is_on or hz < 40.0:
                return

            # 1. КРИТИЧЕСКИ НИЗКАЯ ЧАСТОТА (< 49.20 Гц) — угроза срабатывания САВН/блэкаута
            if hz < 49.20 and store.active_frequency_alert != FrequencyAlert.CRITICAL_LOW:
                store.active_frequency_alert = FrequencyAlert.CRITICAL_LOW
                store.save()
                await bot.send_message(
                    config.target_chat_id,
                    f"🚨 <b>КРИТИЧНО НИЗЬКА ЧАСТОТА МЕРЕЖІ</b>\n\n"
                    f"📉 Поточна: <code>{hz:.2f} Hz</code> (Норма: 50.00 Hz)\n\n"
                    f"⛔️ <b>Гострий дефіцит потужності в енергосистемі!</b>\n"
                    f"<i>Високий ризик системної аварії та екстрених відключень.</i>",
                )

            # 2. НИЗКАЯ ЧАСТОТА (49.20 .. 49.79 Гц) — дефицит генерации
            elif 49.20 <= hz < 49.80 and store.active_frequency_alert not in (
                    FrequencyAlert.LOW,
                    FrequencyAlert.CRITICAL_LOW,
            ):
                store.active_frequency_alert = FrequencyAlert.LOW
                store.save()
                await bot.send_message(
                    config.target_chat_id,
                    f"⚠️ <b>ПРОСАДКА ЧАСТОТИ МЕРЕЖІ</b>\n\n"
                    f"📉 Поточна: <code>{hz:.2f} Hz</code> (Норма: 50.00 Hz)\n\n"
                    f"⚡️ <i>В енергосистемі фіксується перевантаження та дефіцит генерації.</i>",
                )

            # 3. ВЫСОКАЯ ЧАСТОТА (> 50.25 Гц) — профицит генерации
            elif hz > 50.25 and store.active_frequency_alert != FrequencyAlert.HIGH:
                store.active_frequency_alert = FrequencyAlert.HIGH
                store.save()
                await bot.send_message(
                    config.target_chat_id,
                    f"⚠️ <b>ВИСОКА ЧАСТОТА МЕРЕЖІ</b>\n\n"
                    f"📈 Поточна: <code>{hz:.2f} Hz</code> (Норма: 50.00 Hz)\n\n"
                    f"⚡️ <i>Фіксується надлишок генерації в ОЕС України.</i>",
                )

            # 4. СТАБИЛИЗАЦИЯ (49.90 .. 50.10 Гц с выдержкой 30 секунд)
            elif 49.90 <= hz <= 50.10 and store.active_frequency_alert != FrequencyAlert.NONE:
                if not _freq_restore_task or _freq_restore_task.done():
                    async def delayed_freq_restore():
                        await asyncio.sleep(30)
                        store.active_frequency_alert = FrequencyAlert.NONE
                        store.save()
                        await bot.send_message(
                            config.target_chat_id,
                            f"✅ <b>ЧАСТОТА МЕРЕЖІ СТАБІЛІЗУВАЛАСЬ</b>\n\n"
                            f"📊 Поточна: <code>{hz:.2f} Hz</code>\n\n"
                            f"🔌 <i>Енергосистема синхронізована та збалансована (50.00 Hz).</i>",
                        )

                    _freq_restore_task = asyncio.create_task(delayed_freq_restore())
            else:
                if _freq_restore_task and not _freq_restore_task.done():
                    _freq_restore_task.cancel()

    ws_task = asyncio.create_task(ha_client.listen_events(on_ha_event))

    try:
        await dp.start_polling(bot)
    finally:
        ws_task.cancel()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
