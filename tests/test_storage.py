import json
from models.power import VoltageAlert
from storage.state_store import StateStore

def test_state_store_initial_state(tmp_path):
    p = tmp_path / "empty_store.json"
    store = StateStore(str(p))
    assert store.last_power_on_ts is None
    assert store.last_power_off_ts is None
    assert store.active_voltage_alert == VoltageAlert.NONE
    assert store.last_schedule_hash == ""

def test_state_store_save_and_load(tmp_path):
    p = tmp_path / "store.json"
    store = StateStore(str(p))
    store.last_power_on_ts = 1700000000.0
    store.last_power_off_ts = 1700003600.0
    store.active_voltage_alert = VoltageAlert.LOW
    store.last_schedule_hash = "hash_123"
    store.save()

    # Загружаем заново из того же файла
    new_store = StateStore(str(p))
    assert new_store.last_power_on_ts == 1700000000.0
    assert new_store.last_power_off_ts == 1700003600.0
    assert new_store.active_voltage_alert == VoltageAlert.LOW
    assert new_store.last_schedule_hash == "hash_123"

def test_state_store_corrupted_json(tmp_path):
    p = tmp_path / "corrupted.json"
    p.write_text("{invalid_json...", encoding="utf-8")
    store = StateStore(str(p))
    # Должен деградировать до дефолтных значений без падения
    assert store.last_power_on_ts is None
    assert store.active_voltage_alert == VoltageAlert.NONE
