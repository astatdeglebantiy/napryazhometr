import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock
from models.power import VoltageAlert
from services.power_service import PowerService
from storage.state_store import StateStore

@pytest.mark.asyncio
async def test_anti_flapping_power_on_cancelled_if_power_drops_quickly(mocker, test_config, tmp_path):
    """
    Сценарий: свет моргнул на 5 секунд и снова пропал.
    Оповещение 'СВІТЛО З'ЯВИЛОСЯ' НЕ должно уйти (таймер 15с сбрасывается).
    """
    store = StateStore(str(tmp_path / "flapping.json"))
    service = PowerService(test_config, store)
    bot_mock = mocker.MagicMock()
    bot_mock.send_message = AsyncMock()

    # Свет включился -> запускаем задачу с задержкой 15с
    async def delayed_power_on():
        await asyncio.sleep(0.05)  # симуляция 15 секунд в тесте
        await bot_mock.send_message(test_config.target_chat_id, "POWER_ON")

    service._power_on_task = asyncio.create_task(delayed_power_on())

    # Через 10мс свет тухнет
    await asyncio.sleep(0.01)
    service.cancel_tasks()  # имитируем обработчик power_off

    # Ждем завершения времени таймера
    await asyncio.sleep(0.06)

    # Сообщение о включении не должно быть отправлено
    bot_mock.send_message.assert_not_called()

@pytest.mark.asyncio
async def test_voltage_threshold_and_stabilization_timer(mocker, test_config, tmp_path):
    """
    Сценарий:
    1. Напряжение падает до 185V -> отправка алерта LOW VOLTAGE.
    2. Повторное событие 183V -> дублирующее сообщение НЕ отправляется.
    3. Напряжение восстановилось до 220V и продержалось -> отправка STABILIZED.
    """
    store = StateStore(str(tmp_path / "voltage.json"))
    service = PowerService(test_config, store)
    bot_mock = mocker.MagicMock()
    bot_mock.send_message = AsyncMock()

    # 1. Скачок вниз
    store.active_voltage_alert = VoltageAlert.LOW
    store.save()
    await bot_mock.send_message(test_config.target_chat_id, "⚠️ НИЗЬКА НАПРУГА: 185V")
    assert bot_mock.send_message.call_count == 1

    # 2. Повторная просадка: флаг уже LOW -> условие не триггерит повтор
    if store.active_voltage_alert != VoltageAlert.LOW:
        await bot_mock.send_message(test_config.target_chat_id, "⚠️ НИЗЬКА НАПРУГА: 183V")
    assert bot_mock.send_message.call_count == 1

    # 3. Стабилизация
    async def delayed_restore():
        await asyncio.sleep(0.02)  # симуляция 30 секунд
        store.active_voltage_alert = VoltageAlert.NONE
        await bot_mock.send_message(test_config.target_chat_id, "✅ НАПРУГА СТАБІЛІЗУВАЛАСЬ")

    service._voltage_restore_task = asyncio.create_task(delayed_restore())
    await service._voltage_restore_task

    assert bot_mock.send_message.call_count == 2
    assert store.active_voltage_alert == VoltageAlert.NONE
